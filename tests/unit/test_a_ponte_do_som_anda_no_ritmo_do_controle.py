"""A ponte do som anda no ritmo do controle — A-PONTE-DO-SOM-ANDA-NO-RITMO-DO-CONTROLE-01.

O QUE ELA OUVIU (29/09/2026, 02h47): o som do jogo no alto-falante do controle
no rádio cortava a cada ~3 s, só no controle. A ponte lia 480 amostras por
report de uma fonte a 48 kHz, e o laço não dorme: 48 000 ÷ 480 = **100 reports
por segundo** (medido pelo `acl_tx` do adaptador, 100,3/s em 45 s, e pelo
kprobe de 27/09, 100,0/s). O aparelho toca cada quadro de 480 amostras em
10,667 ms: **93,75 por segundo**. A sobra enche o depósito do aparelho, e ele
joga fora ~170 ms de uma vez.

A PROVA 0 (29/09, 06h52, sem a orelha dela): um tom de 1300 Hz a 48 kHz pela
ponte saiu em **1219,35 · 1219,48 · 1219,39 Hz** no microfone de outro
controle — 1300 × 480/512. É o consumo de 93,75 quadros/s, medido.

A CURA, na origem: a fonte do som entrega no ritmo do aparelho, 45 000 Hz, e o
PipeWire faz o 512→480 no fluxo. A regra é uma só: **taxa da fonte × 512/48000
= o que o report lê dela** — 480 para o som, 512 para a háptica.

A REFERÊNCIA DESTA RÉGUA É O FATO MEDIDO, e não a constante do produto: o
aparelho consome um report a cada **512/48000 s**, digitado aqui com a
procedência (o ensaio `o_som_pelo_035.py`, 70 s contínuos com a orelha dela em
10/09/2026, e a prova 0 de 29/09). Medir o produto contra
``INTERVALO_DE_ENVIO_035`` seria a régua medindo a própria saída.

AS MORDIDAS (cada uma feita e devolvida na entrega, com o md5 conferido)
-----------------------------------------------------------------------
1. a taxa do papel «som» de volta a 48 000 → 512 ≠ 480, e a 1 reprova;
2. 45 000 para todo papel → a háptica lê 480 ≠ 512, e a 2 reprova;
3. a chamada do subsystem passando ``taxa=TAXA_DO_ENCODER`` → a 3 reprova;
4. a fonte a 48 000 → 100/s, e a 4 reprova; e o diário de saída com a
   constante no lugar do que se mediu → a montagem fora da cadência reprova;
5. o timbre do ensaio sintetizado a 48 kHz → sai em 1218,75 Hz; e o ritmo do
   ensaio de volta a ``ms_por_report`` → 100/s. As duas reprovam a 5.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import stat
import struct
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af

REPO_ROOT = Path(__file__).resolve().parents[2]

#: O FATO MEDIDO, com a procedência: o aparelho toca um report a cada 512
#: amostras de 48 kHz (10,667 ms). O ensaio `scripts/ensaios/o_som_pelo_035.py`
#: tocou 70 s contínuos assim em 10/09/2026, com a orelha dela; a prova 0 de
#: 29/09/2026 (06h52) ouviu o tom de 1300 Hz sair em 1219,4 Hz pela ponte que
#: mandava 100/s — o aparelho toca 480 amostras nesses 10,667 ms.
SEGUNDOS_POR_REPORT_MEDIDO = Fraction(512, 48_000)
REPORTS_POR_SEGUNDO_MEDIDO = float(1 / SEGUNDOS_POR_REPORT_MEDIDO)  # 93,75

#: Faixa forjada da casa: nunca um endereço real.
UNIQ = "aa:bb:cc:00:00:01"
SERIAL_DE_MENTIRA = 75833


# ---------------------------------------------------------------------------
# Os dublês — cada um publica o que o real publica
# ---------------------------------------------------------------------------


@dataclass
class _Gravador:
    """O processo que o `abrir` devolve: um `stdout` de verdade, num cano."""

    stdout: Any
    argv: list[str]


class _Abertura:
    """O `abrir` de :func:`fonte_do_monitor_do_no`: guarda o argv, não lança nada."""

    def __init__(self) -> None:
        self.argvs: list[list[str]] = []
        self._fds: list[int] = []

    def __call__(self, argv: list[str]) -> _Gravador:
        self.argvs.append(list(argv))
        leitura, escrita = os.pipe()
        self._fds.append(escrita)
        return _Gravador(stdout=os.fdopen(leitura, "rb"), argv=list(argv))

    def fechar(self) -> None:
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass


@pytest.fixture
def gravadores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Abertura]:
    """Um `pw-record` e um `parec` de mentira no PATH, que o `shutil.which` acha.

    Eles nunca rodam: o `abrir` só guarda o argv. Estão aqui para que o produto
    escolha o gravador pelo caminho de verdade (o `which`), sem depender de a
    máquina ter os dois.
    """
    pasta = tmp_path / "bin"
    pasta.mkdir()
    for nome in ("pw-record", "parec"):
        caminho = pasta / nome
        caminho.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
        caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ.get('PATH', '')}")
    # A conferência do alvo responde o que o PipeWire responde quando acerta:
    # o gravador ligado ao monitor do nó pedido.
    monkeypatch.setattr(
        af, "conferir_o_alvo_do_gravador", lambda rotulo: f"{af.nome_do_sink(UNIQ)}:monitor_FL"
    )
    abertura = _Abertura()
    yield abertura
    abertura.fechar()


def _com_pw_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(af, "o_servidor_e_o_pipewire", lambda *_a, **_k: True)
    monkeypatch.setattr(af, "serial_do_no", lambda _nome: SERIAL_DE_MENTIRA)


def _com_parec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(af, "o_servidor_e_o_pipewire", lambda *_a, **_k: True)
    monkeypatch.setattr(af, "serial_do_no", lambda _nome: None)


def _taxa_do_argv(argv: list[str]) -> int:
    """O `--rate=N` do argv. A régua exige argv não vazio ANTES de ler."""
    assert argv, "o gravador nem montou argv — a régua passaria sobre nada"
    taxas = [a.split("=", 1)[1] for a in argv if a.startswith("--rate=")]
    assert len(taxas) == 1, f"o argv não diz a taxa uma vez só: {argv}"
    return int(taxas[0])


def _amostras_que_a_fonte_entrega_por_report(taxa: int) -> Fraction:
    """O que a fonte entrega no tempo em que o aparelho toca um report."""
    return taxa * SEGUNDOS_POR_REPORT_MEDIDO


def _amostras_que_o_som_le_por_report() -> int:
    bomba = af.BombaDeSomPeloRadio(arranjo=af.ARRANJO_PADRAO, fonte=lambda n: bytes(n))
    return bomba.bytes_de_pcm_por_report // (2 * af.CANAIS_DO_ENCODER)


def _fonte_do_som(abertura: _Abertura, **kw: Any) -> list[str]:
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        af.nome_do_sink(UNIQ), uniq=UNIQ, abrir=abertura, **kw
    )
    assert fonte is not None and proc is not None, motivo
    proc.stdout.close()
    return abertura.argvs[-1]


# ---------------------------------------------------------------------------
# 1. A fonte do som pede o ritmo do aparelho
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gravador", ["pw-record", "parec"])
def test_1_a_fonte_do_som_pede_o_ritmo_do_aparelho(
    gravador: str, gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Taxa da fonte × 512/48000 = as 480 amostras que o report do `0x35` lê.

    MORDIDA: a taxa do papel «som» de volta a 48 000 dá 512 ≠ 480.
    """
    (_com_pw_record if gravador == "pw-record" else _com_parec)(monkeypatch)
    argv = _fonte_do_som(gravadores, papel="som")
    assert argv[0] == gravador, f"o produto escolheu {argv[0]}, a régua pediu {gravador}"
    taxa = _taxa_do_argv(argv)
    lidas = _amostras_que_o_som_le_por_report()
    assert lidas == 480, "o report do `0x35` lê um quadro Opus de 480 amostras"
    entrega = _amostras_que_a_fonte_entrega_por_report(taxa)
    assert entrega == lidas, (
        f"a fonte do som a {taxa} Hz entrega {float(entrega):.2f} amostras no tempo em "
        f"que o aparelho toca um report, e o report lê {lidas}: a ponte manda "
        f"{taxa / lidas:.2f} reports/s a um aparelho que consome "
        f"{REPORTS_POR_SEGUNDO_MEDIDO}"
    )


# ---------------------------------------------------------------------------
# 2. A háptica não muda
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gravador", ["pw-record", "parec"])
def test_2_a_fonte_da_haptica_fica_em_48_khz(
    gravador: str, gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O bloco háptico lê 512 quadros por report: a fonte dele já anda a 93,75/s.

    MORDIDA: 45 000 para todo papel dá 480 ≠ 512 — a vibração ficaria 6,25%
    mais lenta que o jogo, e ela sempre andou certa (18/09, «se eu atirei x
    vezes vibrou x vezes»).
    """
    (_com_pw_record if gravador == "pw-record" else _com_parec)(monkeypatch)
    argv = _fonte_do_som(gravadores, papel="haptica", canais=af.CANAIS_DA_HAPTICA)
    assert f"--channels={af.CANAIS_DA_HAPTICA}" in argv
    taxa = _taxa_do_argv(argv)
    entrega = _amostras_que_a_fonte_entrega_por_report(taxa)
    assert entrega == af.QUADROS_POR_BLOCO_HAPTICO, (
        f"a fonte da háptica a {taxa} Hz entrega {float(entrega):.2f} quadros por "
        f"report, e o bloco lê {af.QUADROS_POR_BLOCO_HAPTICO}"
    )


def test_2b_quem_da_a_taxa_explicita_manda(gravadores: _Abertura,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """O papel escolhe só quando o chamador não diz: a taxa explícita atravessa."""
    _com_parec(monkeypatch)
    argv = _fonte_do_som(gravadores, papel="som", taxa=af.TAXA_DO_ENCODER)
    assert _taxa_do_argv(argv) == af.TAXA_DO_ENCODER


# ---------------------------------------------------------------------------
# 3. Pelo subsystem: a volta de produção que sobe a ponte
# ---------------------------------------------------------------------------


@dataclass
class _Controle:
    uniq: str
    caminho: str
    transporte: str


class _PonteDeMentira:
    """Responde como a ponte real e não abre nada. O que se mede é o argv."""

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.gravador = kw.get("gravador")
        self.motivo = ""
        self.subiu = False
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        self.subiu = True
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        if self.gravador is not None:
            self.gravador.stdout.close()
        return True

    def esta_de_pe(self) -> bool:
        return self.subiu and not self.desceu

    def terminou_sozinha(self) -> bool:
        return False


class _GerenciadorDeMentira:
    def reconciliar(self, controles: list[Any] | None = None) -> None:
        return None

    def dormir(self, _s: float) -> bool:
        return False

    def parar(self) -> None:
        return None


def test_3_a_ponte_do_subsystem_sobe_com_o_ritmo_do_aparelho(
    gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A volta de produção, com o `fonte_do_monitor_do_no` VERDADEIRO embrulhado.

    O embrulho só troca o `abrir` (o molde de
    `test_o_gravador_da_ponte_morre_antes_do_no.py`) e repassa tudo o que o
    subsystem mandou: um dublê que engolisse os kwargs seria mais pobre que o
    produto.

    MORDIDA: a chamada do subsystem passando ``taxa=TAXA_DO_ENCODER`` reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

    _com_pw_record(monkeypatch)
    real = af.fonte_do_monitor_do_no
    papeis: list[str] = []

    def _embrulhada(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        kw.pop("abrir", None)
        papeis.append(str(kw.get("papel", "som")))
        return real(id_do_no, abrir=gravadores, **kw)

    class _No:
        def __init__(self, caminho: str) -> None:
            self.fd = 101

    _PonteDeMentira.criadas = []
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _embrulhada)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    todo_alto_falante_toca(monkeypatch)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: _No(no))

    controles = [_Controle(UNIQ, "/dev/hidraw-de-mentira", "bluetooth")]
    ger = _GerenciadorDeMentira()
    sub = mod.AltoFalanteSubsystem(gerenciador=ger, fonte_de_controles=lambda: list(controles))
    sub._gerenciador = ger
    sub._reconciliar(ger)
    try:
        assert papeis == ["som"], f"o subsystem pediu os papéis {papeis}"
        assert [p.uniq for p in _PonteDeMentira.criadas] == [UNIQ], "a ponte não subiu"
        argv = gravadores.argvs[-1]
        assert argv[0] == "pw-record"
        taxa = _taxa_do_argv(argv)
        assert _amostras_que_a_fonte_entrega_por_report(taxa) == 480, (
            f"a ponte do subsystem lê o monitor a {taxa} Hz: "
            f"{taxa / 480:.2f} reports/s a um aparelho que consome "
            f"{REPORTS_POR_SEGUNDO_MEDIDO}"
        )
    finally:
        for ponte in _PonteDeMentira.criadas:
            ponte.descer()


# ---------------------------------------------------------------------------
# 4. No tempo: 180 s de relógio pela ponte de verdade
# ---------------------------------------------------------------------------


class _CodificadorDeMentira:
    """Publica o que o real publica: 200 B por quadro de 1920 B, `None` fora dele."""

    def __init__(self, **_kw: Any) -> None:
        pass

    def codificar(self, pcm: bytes) -> bytes | None:
        if len(pcm) != af.BYTES_DE_PCM_POR_QUADRO:
            return None
        return b"\x01" * af.BYTES_POR_QUADRO_OPUS


class _Diario:
    """O `logger` do módulo, anotando o que a ponte diz."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def _anotar(self, evento: str, **kw: Any) -> None:
        self.linhas.append((evento, kw))

    info = warning = debug = error = _anotar

    def de(self, evento: str) -> list[dict[str, Any]]:
        return [kw for nome, kw in self.linhas if nome == evento]


class _Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


SEGUNDOS_DE_RELOGIO = 180.0


def _fonte_no_relogio(relogio: _Relogio, taxa: int) -> Any:
    """Uma fonte com sinal que anda o relógio pelo que entrega: n ÷ (4 × taxa) s.

    É o que o monitor do nó faz: pedir n bytes estéreo s16 bloqueia até o nó
    ter tocado n ÷ 4 amostras à taxa pedida. Seca em 180 s de relógio.
    """

    def _ler(n: int) -> bytes:
        if relogio.t >= SEGUNDOS_DE_RELOGIO:
            return b""
        relogio.t += n / (4 * taxa)
        return (b"\x01\x00" * n)[:n]

    return _ler


def _correr_a_ponte(monkeypatch: pytest.MonkeyPatch, taxa: int) -> tuple[list[bytes], _Diario,
                                                                          _Relogio]:
    """A `PonteDeSomPorRadio` de verdade, o laço de verdade, o hidraw em /dev/null."""
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    monkeypatch.setattr(af, "CodificadorOpus", _CodificadorDeMentira)
    escritos: list[bytes] = []

    def _escritor(_fd: int) -> Any:
        def _escrever(dados: bytes) -> int:
            escritos.append(bytes(dados))
            return len(dados)

        return _escrever

    monkeypatch.setattr(af, "escritor_de_hidraw", _escritor)
    diario = _Diario()
    monkeypatch.setattr(af, "logger", diario)
    relogio = _Relogio()
    ponte = af.PonteDeSomPorRadio(
        uniq=UNIQ,
        abrir_hidraw=lambda: os.open(os.devnull, os.O_WRONLY),
        fonte_de_pcm=_fonte_no_relogio(relogio, taxa),
        relogio=relogio,
    )
    assert ponte.subir() is True, ponte.motivo
    thread = ponte._thread
    assert thread is not None
    thread.join(timeout=120.0)
    assert not thread.is_alive(), "a fonte secou e a ponte não terminou"
    return escritos, diario, relogio


def _taxa_da_regua_1(gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch) -> int:
    _com_parec(monkeypatch)
    return _taxa_do_argv(_fonte_do_som(gravadores, papel="som"))


def test_4_no_tempo_a_ponte_manda_93_75_por_segundo(
    gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """180 s de relógio: 93,75 ± 0,05 reports/s, o `[10]` anda um por report, e o diário diz o mesmo.

    O N da fonte é o do argv da régua 1 — a montagem mede a ponte com a taxa
    que o produto pede, não com um número digitado.

    MORDIDA: a fonte a 48 000 dá 100/s.
    """
    taxa = _taxa_da_regua_1(gravadores, monkeypatch)
    escritos, diario, relogio = _correr_a_ponte(monkeypatch, taxa)

    assert escritos, "a ponte não escreveu nada — a régua não mede nada"
    por_segundo = len(escritos) / relogio.t
    assert por_segundo == pytest.approx(REPORTS_POR_SEGUNDO_MEDIDO, abs=0.05), (
        f"a ponte mandou {por_segundo:.2f} reports/s em {relogio.t:.1f} s de relógio; "
        f"o aparelho consome {REPORTS_POR_SEGUNDO_MEDIDO}"
    )
    contadores = [r[10] for r in escritos]
    assert contadores == [i & 0xFF for i in range(len(escritos))], (
        "o contador de quadros `[10]` não anda um por report"
    )
    saidas = diario.de("som_radio_ponte_saiu")
    assert len(saidas) == 1, f"a ponte saiu sem dizer o que fez: {diario.linhas}"
    saida = saidas[0]
    assert saida["leituras_por_segundo"] == pytest.approx(por_segundo, abs=0.05), saida
    assert saida["segundos_de_pe"] == pytest.approx(relogio.t, abs=0.01), saida
    assert saida["escritas_aceitas"] == len(escritos), saida
    assert saida["cedidos"] == 0, saida
    de_pe = diario.de("som_radio_ponte_de_pe")
    assert len(de_pe) == 1 and "reports_por_segundo" not in de_pe[0], (
        "a linha de subida voltou a imprimir a constante com o nome do que a ponte faz"
    )


def test_4b_o_diario_diz_o_que_a_ponte_fez_e_nao_a_constante(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mesma ponte com uma fonte FORA da cadência (48 000, explícita): o diário diz 100.

    Com a fonte da cura, o diário e a constante dizem os dois 93,75, e um
    diário de volta à constante passaria na régua de cima. Esta montagem não
    depende da cura da taxa.

    MORDIDA: a linha de saída com ``1 / intervalo_de_envio_s`` no lugar das
    leituras contadas.
    """
    escritos, diario, relogio = _correr_a_ponte(monkeypatch, 48_000)
    saida = diario.de("som_radio_ponte_saiu")
    assert len(saida) == 1, diario.linhas
    assert saida[0]["leituras_por_segundo"] == pytest.approx(100.0, abs=0.05), (
        f"a fonte entregou 100 leituras por segundo e o diário disse {saida[0]}"
    )
    assert len(escritos) / relogio.t == pytest.approx(100.0, abs=0.05)


# ---------------------------------------------------------------------------
# 5. O outro chamador: o ensaio de bancada toca no ritmo e no tom do aparelho
# ---------------------------------------------------------------------------


def _carregar_o_ensaio() -> Any:
    caminho = REPO_ROOT / "scripts" / "ensaios" / "o_som_que_sai.py"
    pasta = str(caminho.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    espec = importlib.util.spec_from_file_location("o_som_que_sai_no_ritmo", caminho)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


class _TempoDeMentira:
    """O `time` do módulo: o relógio só anda quando alguém dorme."""

    def __init__(self) -> None:
        self.t = 1000.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += max(0.0, s)


def _frequencia_tocada(pcms: list[bytes]) -> float:
    """A frequência que o aparelho toca: 480 amostras em 512/48000 s por quadro.

    Conta as trocas de sinal no canal esquerdo e divide pelo tempo em que o
    aparelho tocou as amostras com som. A porta do pulsado (um trecho longo de
    zero exato) sai da conta; o zero de uma amostra só, que o seno dá ao passar
    pelo eixo, fica, porque ele também dura 1/45 000 s no aparelho. Nada aqui
    usa a taxa do produto.
    """
    amostras: list[int] = []
    for pcm in pcms:
        amostras.extend(struct.unpack(f"<{len(pcm) // 2}h", pcm)[0::2])
    com_som: list[int] = []
    zeros: list[int] = []
    for a in amostras:
        if a == 0:
            zeros.append(a)
            continue
        if len(zeros) < 4:
            com_som.extend(zeros)
        zeros = []
        com_som.append(a)
    sinais = [a > 0 for a in com_som if a != 0]
    trocas = sum(1 for a, b in zip(sinais, sinais[1:]) if a != b)
    segundos_por_amostra = float(SEGUNDOS_POR_REPORT_MEDIDO) / 480
    return trocas / 2 / (len(com_som) * segundos_por_amostra)


def test_5_o_ensaio_toca_no_ritmo_e_no_tom_do_aparelho(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`o_som_que_sai.py --escrever` com o `0x35`: 93,75 reports/s e o 1300 Hz que ele anuncia.

    O ensaio inteiro, pela porta dele, com a bancada, o hidraw, o relógio e o
    codificador de mentira (o codificador guarda o PCM que recebeu).

    MORDIDAS: o timbre sintetizado a 48 kHz sai em 1218,75 Hz; o ritmo de volta
    a ``ms_por_report`` dá 100/s.
    """
    ensaio = _carregar_o_ensaio()
    import hefesto_dualsense4unix.daemon.subsystems.alto_falante as sub
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt_audio

    class _Uno:
        uniq, caminho, transporte = ensaio.MAC_SINTETICO, "/dev/hidraw99", "rádio"

    pcms: list[bytes] = []

    class _Codificador(_CodificadorDeMentira):
        def codificar(self, pcm: bytes) -> bytes | None:
            pcms.append(bytes(pcm))
            return super().codificar(pcm)

    escritos: list[bytes] = []

    def _escritor(_fd: int) -> Any:
        def _escrever(dados: bytes) -> int:
            escritos.append(bytes(dados))
            return len(dados)

        return _escrever

    tempo = _TempoDeMentira()
    monkeypatch.setattr(sub, "controles_na_lista", lambda *a, **k: [_Uno()])
    monkeypatch.setattr(ensaio, "_exigir_bancada", lambda: (True, ""))
    monkeypatch.setattr(bt_audio, "abrir_hidraw_rw", lambda _c: os.open(os.devnull, os.O_WRONLY))
    monkeypatch.setattr(af, "CodificadorOpus", _Codificador)
    monkeypatch.setattr(af, "escritor_de_hidraw", _escritor)
    monkeypatch.setattr(af, "time", tempo)

    argumentos = argparse.Namespace(
        exigir_mac=ensaio.MAC_SINTETICO, arranjo=af.ARRANJO_035.nome,
        eu_estou_ouvindo=True, segundos=8.0, tag=af.BLOCO_SPEAKER,
    )
    assert ensaio.escrever_no_aparelho(argumentos) == 0
    saida = capsys.readouterr().out

    assert escritos, "o ensaio não escreveu nada — a régua não mede nada"
    por_segundo = len(escritos) / 8.0
    assert por_segundo == pytest.approx(REPORTS_POR_SEGUNDO_MEDIDO, abs=0.25), (
        f"o ensaio mandou {por_segundo:.2f} reports/s; o aparelho consome "
        f"{REPORTS_POR_SEGUNDO_MEDIDO}"
    )
    tocada = _frequencia_tocada(pcms)
    assert tocada == pytest.approx(ensaio.BANCADA_HZ, abs=ensaio.BANCADA_HZ * 0.01), (
        f"o ensaio anuncia {ensaio.BANCADA_HZ:.0f} Hz e o aparelho toca {tocada:.1f} Hz"
    )
    assert "93.75 reports/s" in saida or "93,75 reports/s" in saida, saida


def test_5b_a_regua_da_frequencia_morde() -> None:
    """A régua de cima distingue o tom certo do grave: sem isto ela mediria nada."""
    def _tom(taxa: float, quadros: int) -> list[bytes]:
        saida = []
        fase = 0
        for _ in range(quadros):
            amostras: list[int] = []
            for _i in range(480):
                v = int(12000 * math.sin(2 * math.pi * 1300.0 * fase / taxa))
                amostras.extend((v, v))
                fase += 1
            saida.append(struct.pack(f"<{len(amostras)}h", *amostras))
        return saida

    assert _frequencia_tocada(_tom(45_000, 400)) == pytest.approx(1300.0, abs=2.0)
    assert _frequencia_tocada(_tom(48_000, 400)) == pytest.approx(1218.75, abs=2.0)
