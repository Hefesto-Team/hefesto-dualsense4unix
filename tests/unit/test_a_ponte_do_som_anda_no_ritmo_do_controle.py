"""A ponte do som anda no ritmo do controle — A-PONTE-DO-SOM-ANDA-NO-RITMO-DO-CONTROLE-01."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import itertools
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

SEGUNDOS_POR_REPORT_MEDIDO = Fraction(512, 48_000)
REPORTS_POR_SEGUNDO_MEDIDO = float(1 / SEGUNDOS_POR_REPORT_MEDIDO)

UNIQ = "aa:bb:cc:00:00:01"
SERIAL_DE_MENTIRA = 75833


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
            with contextlib.suppress(OSError):
                os.close(fd)


@pytest.fixture
def gravadores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Abertura]:
    """Um `pw-record` e um `parec` de mentira no PATH, que o `shutil.which` acha."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    for nome in ("pw-record", "parec"):
        caminho = pasta / nome
        caminho.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
        caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ.get('PATH', '')}")
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
    bomba = af.BombaDeSomPeloRadio(fonte=lambda n: bytes(n))
    return int(bomba.bytes_de_pcm_por_report // (2 * af.CANAIS_DO_ENCODER))


def _fonte_do_som(abertura: _Abertura, **kw: Any) -> list[str]:
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        af.nome_do_sink(UNIQ), uniq=UNIQ, abrir=abertura, **kw
    )
    assert fonte is not None and proc is not None, motivo
    proc.stdout.close()
    return abertura.argvs[-1]


@pytest.mark.parametrize("gravador", ["pw-record", "parec"])
def test_1_a_fonte_do_som_pede_o_ritmo_do_aparelho(
    gravador: str, gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Taxa da fonte x 512/48000 = as 480 amostras que o report do `0x35` lê."""
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


@pytest.mark.parametrize("gravador", ["pw-record", "parec"])
def test_2_a_fonte_da_haptica_fica_em_48_khz(
    gravador: str, gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O bloco háptico lê 512 quadros por report: a fonte dele já anda a 93,75/s."""
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
    """A volta de produção, com o `fonte_do_monitor_do_no` VERDADEIRO embrulhado."""
    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

    _com_pw_record(monkeypatch)
    real = af.fonte_do_monitor_do_no
    papeis: list[str] = []

    def _embrulhada(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        kw.pop("abrir", None)
        papeis.append(str(kw.get("papel", "som")))
        fonte, proc, motivo = real(id_do_no, abrir=gravadores, **kw)
        return fonte, proc, str(motivo)

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


def test_3b_os_quatro_controles_do_radio_sobem_no_ritmo_do_aparelho(
    gravadores: _Abertura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1 a P4 no rádio: cada ponte tem gravador próprio, e os quatro pedem a mesma taxa."""
    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

    _com_pw_record(monkeypatch)
    monkeypatch.setattr(af, "conferir_o_alvo_do_gravador", lambda _rotulo: None)
    real = af.fonte_do_monitor_do_no
    pedidos: list[tuple[str, str]] = []

    def _embrulhada(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        kw.pop("abrir", None)
        pedidos.append((str(kw.get("uniq")), str(kw.get("papel", "som"))))
        fonte, proc, motivo = real(id_do_no, abrir=gravadores, **kw)
        return fonte, proc, str(motivo)

    class _No:
        def __init__(self, caminho: str) -> None:
            self.fd = 101

    _PonteDeMentira.criadas = []
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _embrulhada)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    todo_alto_falante_toca(monkeypatch)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: _No(no))

    uniqs = [f"aa:bb:cc:00:00:0{i}" for i in range(1, 5)]
    controles = [_Controle(u, f"/dev/hidraw-de-mentira-{i}", "bluetooth")
                 for i, u in enumerate(uniqs)]
    ger = _GerenciadorDeMentira()
    sub = mod.AltoFalanteSubsystem(gerenciador=ger, fonte_de_controles=lambda: list(controles))
    sub._gerenciador = ger
    sub._reconciliar(ger)
    try:
        assert sorted(p.uniq for p in _PonteDeMentira.criadas) == uniqs, (
            f"nem todo controle do rádio subiu a ponte: {pedidos}"
        )
        assert sorted(pedidos) == [(u, "som") for u in uniqs], pedidos
        assert len(gravadores.argvs) == 4
        for argv in gravadores.argvs:
            taxa = _taxa_do_argv(argv)
            assert _amostras_que_a_fonte_entrega_por_report(taxa) == 480, (
                f"um dos quatro lê o monitor a {taxa} Hz: {argv}"
            )
    finally:
        for ponte in _PonteDeMentira.criadas:
            ponte.descer()


class _CodificadorDeMentira:
    """Publica o que o real publica: 200 B por quadro de 1920 B, `None` fora dele."""

    def __init__(self, **_kw: Any) -> None:
        pass

    def codificar(self, pcm: bytes) -> bytes | None:
        if len(pcm) != af.BYTES_DE_PCM_POR_QUADRO:
            return None
        return bytes(b"\x01" * int(af.BYTES_POR_QUADRO_OPUS))


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
    """Uma fonte com sinal que anda o relógio pelo que entrega: n ÷ (4 x taxa) s."""

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
    """180 s de relógio: 93,75 ± 0,05 reports/s, o `[10]` anda um por report, e o diário o diz."""
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
    """A mesma ponte com uma fonte FORA da cadência (48 000, explícita): o diário diz 100."""
    escritos, diario, relogio = _correr_a_ponte(monkeypatch, 48_000)
    saida = diario.de("som_radio_ponte_saiu")
    assert len(saida) == 1, diario.linhas
    assert saida[0]["leituras_por_segundo"] == pytest.approx(100.0, abs=0.05), (
        f"a fonte entregou 100 leituras por segundo e o diário disse {saida[0]}"
    )
    assert len(escritos) / relogio.t == pytest.approx(100.0, abs=0.05)


class _VagaDeMentira:
    """A vaga do governador, com o que a bomba e a ponte perguntam a ela."""

    derrubar = False
    cedendo = False

    def __init__(self) -> None:
        self.soltas: list[str] = []

    def subiu(self, _papel: str) -> None:
        return None

    def contar_escrita(self) -> None:
        return None

    def fila_parada(self, _s: float) -> None:
        return None

    def soltar(self, por_que: str) -> None:
        self.soltas.append(por_que)


def test_4c_a_linha_de_saida_nunca_prende_a_vaga(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um relógio que levanta na saída: a linha não sai, e a vaga volta ao governador."""
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    monkeypatch.setattr(af, "CodificadorOpus", _CodificadorDeMentira)
    monkeypatch.setattr(af, "escritor_de_hidraw", lambda _fd: (lambda dados: len(dados)))
    diario = _Diario()
    monkeypatch.setattr(af, "logger", diario)
    class _Fonte:
        """Dez leituras com sinal, e seca; o relógio levanta depois de secar."""

        def __init__(self) -> None:
            self.lidas = 0
            self.secou = False

        def relogio(self) -> float:
            if self.secou:
                raise RuntimeError("o relógio caiu na saída")
            return 0.0

        def ler(self, n: int) -> bytes:
            if self.lidas >= 10:
                self.secou = True
                return b""
            self.lidas += 1
            return (b"\x01\x00" * n)[:n]

    fonte = _Fonte()
    vaga = _VagaDeMentira()
    ponte = af.PonteDeSomPorRadio(
        uniq=UNIQ,
        abrir_hidraw=lambda: os.open(os.devnull, os.O_WRONLY),
        fonte_de_pcm=fonte.ler,
        relogio=fonte.relogio,
        vaga=vaga,
    )
    assert ponte.subir() is True, ponte.motivo
    thread = ponte._thread
    assert thread is not None
    thread.join(timeout=30.0)
    assert not thread.is_alive()
    assert vaga.soltas == ["a fonte do som secou"], (
        f"a vaga não voltou ao governador: {vaga.soltas}"
    )
    assert diario.de("som_radio_ponte_saiu") == []


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
    """A frequência que o aparelho toca: 480 amostras em 512/48000 s por quadro."""
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
    trocas = sum(1 for a, b in itertools.pairwise(sinais) if a != b)
    segundos_por_amostra = float(SEGUNDOS_POR_REPORT_MEDIDO) / 480
    return trocas / 2 / (len(com_som) * segundos_por_amostra)


def test_5_o_ensaio_toca_no_ritmo_e_no_tom_do_aparelho(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`o_som_que_sai.py --escrever` com o `0x35`: 93,75 reports/s e o 1300 Hz que ele anuncia."""
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
        eu_estou_ouvindo=True, segundos=8.0, tag=bt_audio.BLOCO_SPEAKER,
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
