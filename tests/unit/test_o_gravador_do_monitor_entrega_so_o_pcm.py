"""O gravador do monitor entrega só PCM: o primeiro bloco de um nó mudo é mudo.

**A queixa dela, 01/10/2026**, depois de jogar com visitas (dois DualSense no
Bluetooth): *«Háptica por áudio não funcionou, nem no bt e nem aumentou a
intensidade durante o jogo.»* <!-- noqa-acento: citação literal dela -->

**A causa, medida em 02/10/2026.** O ``pw-record`` sem ``--raw`` escreve um
cabeçalho AU de 24 bytes antes do PCM. Medido num PipeWire 1.6.8 PRIVADO (o
mesmo binário da máquina dela, num diretório de execução próprio, sem tocar o
servidor dela): o argv do produto gravou ``64 6e 73 2e 18 00 00 00 ff ff ff ff
03 00 00 00 80 bb 00 00 04 00 00 00`` e depois o PCM, little-endian e alinhado
ao quadro; com ``--raw``, o PCM começa no byte 0. Os 24 bytes têm 11 não nulos,
três deles nos canais traseiros do primeiro quadro de quatro canais.

O ``OUVIDO`` (dono de «este nó tem sinal agora?», 29/09) ouvia esses bytes
como SINAL por um segundo, em todo gravador novo. O diário dela de 01/10 tem
os dois desenhos que isso faz:

* no modo Xbox (o rumble convertido em háptica), às 19h01m45: a ponte sobe em
  ``0x32-háptica`` e desce como ociosa 16 ms depois, porque o gravador novo do
  alto-falante «tinha sinal»; o rumble volta aos motores do HID, sem o ganho;
* com o jogo mandando háptica (18h22m44 a 18h22m54): a ponte alterna entre o
  ``0x35`` (1,0 s, duas escritas: o cabeçalho e o silêncio depois dele) e o
  ``0x32`` (10 a 17 ms), sem um bloco háptico no ar.

O dublê do gravador aqui faz o que o real faz, inclusive o cabeçalho sem
``--raw``: um dublê que entrega PCM puro (o ``FonteDeMentira`` das irmãs) é
mais frouxo que o ``pw-record``, e foi por ele que régua nenhuma viu isto.
Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import contextlib
import os
import struct
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import filho_de_som

#: O que o ``pw-record`` 1.6.8 escreveu ANTES do PCM, com o argv do produto
#: sem ``--raw``, ``--rate=48000 --channels=4`` (02/10/2026, PipeWire privado,
#: a saída num cano). Digitado da medida: a régua do dublê o compara com isto,
#: e não com a função que o monta.
CABECALHO_MEDIDO_48K_4CH = bytes.fromhex(
    "646e732e" "18000000" "ffffffff" "03000000" "80bb0000" "04000000"
)

#: O código com que o ``pw-record`` sai no TERM (o diário dela: ``codigo=1
#: por=saiu`` em toda ponte colhida).
CODIGO_DO_TERM = 1


def cabecalho_au(taxa: int, canais: int) -> bytes:
    """O cabeçalho que o ``pw-record`` sem ``--raw`` escreve num cano."""
    return b"dns." + struct.pack("<IIIII", 24, 0xFFFFFFFF, 3, taxa, canais)


def _valor(argv: list[str], chave: str) -> str:
    return next(a.split("=", 1)[1] for a in argv if a.startswith(f"{chave}="))


class GravadorDeMentira:
    """O ``pw-record`` do produto, com o comportamento medido do real.

    Lê o próprio argv como o real lê: ``--target`` (o serial do nó), ``--rate``,
    ``--channels`` e ``--raw``. Sem ``--raw``, o cabeçalho vai antes do PCM. O
    PCM é o que ``tocando(serial)`` diz, um bloco de 480 quadros por volta, no
    formato pedido. O TERM sai com 1, como o real.
    """

    def __init__(self, argv: list[str], tocando: Callable[[int, int], bytes]) -> None:
        self.argv = list(argv)
        cru = "--raw" in self.argv or "-a" in self.argv
        taxa = int(_valor(self.argv, "--rate"))
        canais = int(_valor(self.argv, "--channels"))
        serial = int(_valor(self.argv, "--target"))
        leitura, escrita = os.pipe()
        self.stdout = os.fdopen(leitura, "rb", buffering=0)
        self._fim = threading.Event()
        self.returncode: int | None = None

        def _escrever() -> None:
            try:
                if not cru:
                    os.write(escrita, cabecalho_au(taxa, canais))
                while not self._fim.is_set():
                    os.write(escrita, tocando(serial, canais))
                    time.sleep(0.003)
            except OSError:
                pass
            finally:
                with contextlib.suppress(OSError):
                    os.close(escrita)

        threading.Thread(target=_escrever, daemon=True).start()

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self._fim.set()
        self.returncode = CODIGO_DO_TERM

    kill = terminate

    def wait(self, timeout: float | None = None) -> int:
        self._fim.set()
        if self.returncode is None:
            self.returncode = CODIGO_DO_TERM
        return self.returncode


def _quadro(canais: int, valores: tuple[int, ...] | None) -> bytes:
    if not valores:
        return bytes(2 * canais)
    return struct.pack(f"<{canais}h", *valores)


class Gravadores:
    """Os gravadores que o produto abre, cada um com o que o nó dele toca agora."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.serial: dict[str, int] = {}
        self.toca: dict[str, tuple[int, ...] | None] = {}
        self.abertos: list[GravadorDeMentira] = []
        real_which = af.shutil.which
        monkeypatch.setattr(
            af.shutil, "which",
            lambda b: "/usr/bin/pw-record" if b == "pw-record" else real_which(b),
        )
        monkeypatch.setattr(af, "o_servidor_e_o_pipewire", lambda *_a, **_k: True)
        monkeypatch.setattr(af, "serial_do_no", self._serial_do_no)
        monkeypatch.setattr(af, "conferir_o_alvo_do_gravador", lambda _rotulo: None)
        monkeypatch.setattr(filho_de_som, "lancar_leitor", self._lancar)

    def _serial_do_no(self, nome: str) -> int:
        alvo = nome[: -len(".monitor")] if nome.endswith(".monitor") else nome
        return self.serial.setdefault(alvo, 4200 + len(self.serial))

    def _tocando(self, serial: int, canais: int) -> bytes:
        nome = next((n for n, s in self.serial.items() if s == serial), "")
        return _quadro(canais, self.toca.get(nome)) * 480

    def _lancar(self, argv: list[str]) -> GravadorDeMentira:
        assert argv and argv[0] == "pw-record", f"o produto não escolheu o pw-record: {argv}"
        gravador = GravadorDeMentira(argv, self._tocando)
        self.abertos.append(gravador)
        return gravador

    def fechar(self) -> None:
        for gravador in self.abertos:
            gravador.terminate()
            gravador.stdout.close()


@pytest.fixture
def gravadores(monkeypatch: pytest.MonkeyPatch) -> Any:
    g = Gravadores(monkeypatch)
    yield g
    g.fechar()


# ---------------------------------------------------------------------------
# 0. O dublê não é mais frouxo que o real
# ---------------------------------------------------------------------------


def test_o_duble_escreve_o_cabecalho_que_o_pw_record_escreveu() -> None:
    """O cabeçalho do dublê é o byte a byte medido em 02/10, para 48 kHz e 4 canais."""
    assert cabecalho_au(48_000, 4) == CABECALHO_MEDIDO_48K_4CH
    # E ele TEM sinal pelas regras do produto: é por isso que o ouvido mentia.
    pcm = CABECALHO_MEDIDO_48K_4CH + bytes(4096 - len(CABECALHO_MEDIDO_48K_4CH))
    assert af.tem_sinal_no_pcm(pcm, canais=af.CANAIS_DA_HAPTICA)
    assert af.tem_sinal_no_pcm(pcm[:1920], canais=af.CANAIS_DO_ENCODER)


# ---------------------------------------------------------------------------
# 1. O primeiro bloco de um nó mudo é mudo, nos dois papéis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("papel", "canais", "tamanho"),
    [
        ("som", af.CANAIS_DO_ENCODER, af.BYTES_DE_PCM_POR_QUADRO),
        ("haptica", af.CANAIS_DA_HAPTICA, af.QUADROS_POR_BLOCO_HAPTICO * 2 * af.CANAIS_DA_HAPTICA),
    ],
)
def test_o_primeiro_bloco_do_monitor_mudo_e_mudo(
    gravadores: Gravadores, monkeypatch: pytest.MonkeyPatch,
    papel: str, canais: int, tamanho: int,
) -> None:
    """O gravador novo de um nó em silêncio: o ouvido diz «escutado e mudo».

    Pelo ``fonte_do_monitor_do_no`` de produção, com o argv que ele monta.

    MORDIDA: tire o ``"--raw"`` do ``pw-record`` em ``GRAVADORES_DO_MONITOR`` —
    o primeiro bloco traz o cabeçalho, o ouvido diz que o nó tem sinal, e
    reprova.
    """
    ouvido = af.OuvidoDosNos()
    monkeypatch.setattr(af, "OUVIDO", ouvido)
    no = "hefesto_som_0000ab" if papel == "som" else "endpoint-do-lugar-1"
    gravadores.toca[no] = None
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        no, uniq="aa:bb:cc:00:00:ab", papel=papel, canais=canais
    )
    assert fonte is not None and proc is not None, motivo
    try:
        ouvir = af.fonte_que_ouve(fonte, no, canais=canais)
        primeiro = ouvir(tamanho)
        assert len(primeiro) == tamanho
        assert not af.tem_sinal_no_pcm(primeiro, canais=canais), (
            f"o primeiro bloco do monitor mudo veio com bytes não nulos: "
            f"{primeiro[:24].hex()}"
        )
        assert ouvido.tem_sinal(no) is False, "o ouvido ouviu sinal num nó mudo"
    finally:
        proc.terminate()
        proc.stdout.close()


def test_o_sinal_que_o_jogo_toca_ainda_chega_inteiro(
    gravadores: Gravadores, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cura não come o começo do PCM: o primeiro quadro é o do jogo, no lugar dele."""
    monkeypatch.setattr(af, "OUVIDO", af.OuvidoDosNos())
    no = "endpoint-do-lugar-2"
    motor = (0, 0, 20000, -20000)
    gravadores.toca[no] = motor
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        no, uniq="aa:bb:cc:00:00:ac", papel="haptica", canais=af.CANAIS_DA_HAPTICA
    )
    assert fonte is not None and proc is not None, motivo
    try:
        bloco = fonte(af.QUADROS_POR_BLOCO_HAPTICO * 2 * af.CANAIS_DA_HAPTICA)
        assert bloco[:8] == struct.pack("<4h", *motor)
    finally:
        proc.terminate()
        proc.stdout.close()


# ---------------------------------------------------------------------------
# 2. A ponte que sobe em háptica não desce pelo gravador novo do alto-falante
# ---------------------------------------------------------------------------


def test_a_ponte_em_haptica_fica_com_o_gravador_novo_do_alto_falante(
    gravadores: Gravadores, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O desenho de 18h22m44 do diário dela, na volta de produção.

    O jogo toca nos motores do endpoint e o alto-falante fica aberto e mudo.
    A ponte sobe no ``0x35`` (o ouvido do endpoint vai junto), passa ao
    ``0x32`` quando o motor toca, e FICA nele: o gravador novo do nó do som,
    que a ponte da háptica abre só para ouvir, não pode virar sinal.

    MORDIDA: tire o ``"--raw"`` — a volta seguinte à subida em háptica ouve o
    cabeçalho no nó do som e devolve a ponte ao ``0x35``, e reprova.
    """
    from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (
        P4,
        Mesa,
        no_do,
    )

    real = af.fonte_do_monitor_do_no
    sala = Mesa(monkeypatch)
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", real)
    try:
        som, endpoint = af.nome_do_sink(P4), no_do(P4)
        gravadores.toca[som] = None
        gravadores.toca[endpoint] = (0, 0, 20000, -20000)
        sala.abrir_a_sala(P4)
        sala.volta()
        assert sala.arranjo(P4) == af.ARRANJO_035.nome
        sala.esperar(endpoint, True)
        sala.esperar(som, False)
        sala.mexer(P4)
        sala.volta()
        assert sala.arranjo(P4) == af.ARRANJO_HAPTICA_032.nome
        # O fio do ouvido da ponte nova leu o nó do som: a volta de agora é a
        # que, no diário dela, vinha 10 a 18 ms depois da subida.
        subiu = time.monotonic()
        fim = subiu + 5.0
        while time.monotonic() < fim:
            if sala.ouvido._ultima_leitura.get(som, 0.0) > subiu:
                break
            time.sleep(0.005)
        assert sala.ouvido._ultima_leitura.get(som, 0.0) > subiu, "o ouvido do som não leu"
        sala.volta()
        assert sala.arranjo(P4) == af.ARRANJO_HAPTICA_032.nome, (
            "o gravador novo do alto-falante virou sinal e tirou a ponte da háptica"
        )
    finally:
        sala.fechar()
