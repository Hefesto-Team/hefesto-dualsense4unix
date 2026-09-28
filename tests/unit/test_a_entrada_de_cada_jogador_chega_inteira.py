"""A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01 — o que os programas mandam aos virtuais.

**O item 2, medido em 27/09/2026.** O kernel mostrou `playstation
0003:054C:0DF2.*: Output queue is full` 47.020 vezes às 00h e 39.552 à 01h,
com o PRAGMATA aberto, e 2.013 numa partida de Pro Jank Footy. É a fila de 32
eventos do `uhid.c` de cada controle virtual nosso: o que não cabe, o kernel
descarta (vibração, gatilho e luz que o jogo pediu). O daemon só lia o fd do
uhid no `pump_ff`, chamado no tique do repasse da entrada (~60 Hz), e o
`cosmic-osk` de toda sessão do COSMIC manda um efeito a cada 50 ms a cada
virtual.

**O kernel de mentira é o `uhid.c` naquilo que mede:** uma fila de 32 lugares
(`UHID_BUFSIZE`, e cabem 31: o `uhid_queue` recusa quando a cabeça alcançaria o
rabo), um evento por `read`, e o descarte com a conta do «Output queue is
full». O fd que o produto recebe é um socket `SOCK_SEQPACKET` (a fronteira de
cada evento se preserva, e o `poll` funciona como no nó de verdade), e o
kernel conta o que está na fila pelo `FIONREAD`, que num `SEQPACKET` soma os
eventos que o produto ainda não leu. O produto chega a ele pelo caminho de
sempre (`start()` → `os.open("/dev/uhid")`).

**As réguas, e as mordidas (28/09/2026, cada uma devolvida com o md5):**

- 200 eventos de saída em ~100 ms sem nenhum tique: nenhum cai. Devolva o
  dreno ao tique (o `_criar_o_device` sem `_iniciar_o_fio_do_uhid`) e a fila
  enche: 169 descartados, e o produto não viu nenhum;
- o pedido de feature do jogo (`UHID_GET_REPORT`, em que quem pede fica
  parado até a resposta) é respondido sem tique;
- a entrega ao controle físico segue no tique: nenhum sink roda no fio do
  virtual, e o último pedido de vibração chega;
- o `stop` encerra o fio antes de fechar o fd.

Nenhum endereço real: o MAC do virtual sai do número (o piso `02:fe`).
"""
from __future__ import annotations

import array
import contextlib
import fcntl
import os
import socket
import struct
import termios
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_CREATE2,
    UHID_DESTROY,
    UHID_EVENT_SIZE,
    UHID_GET_REPORT,
    UHID_GET_REPORT_REPLY,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
)

#: `UHID_BUFSIZE` do `drivers/hid/uhid.c`. O `uhid_queue` recusa quando a
#: cabeça nova alcançaria o rabo: cabem 31.
UHID_BUFSIZE = 32

#: Quantos eventos o jogo manda, e em quanto tempo (a régua da sprint).
EVENTOS = 200
JANELA_S = 0.100

#: O prazo de quem espera o fio responder. A resposta leva microssegundos; o
#: prazo largo é para a máquina carregada, e o sem-fio nunca responde.
PRAZO_S = 0.25


class KernelDoUhid:
    """O lado do kernel do `/dev/uhid`: a fila de 32 lugares, e só.

    ``cheia`` conta o «Output queue is full» — o que o kernel descartou. O fio
    do kernel lê o que o produto escreve: responde o `UHID_CREATE2` como o
    probe do `hid_playstation` (`START`, e o `OPEN` do `hid_hw_open` do probe)
    e anota as respostas de feature.
    """

    def __init__(self) -> None:
        self.lado_do_kernel, self.lado_do_produto = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )
        # A fila de 31 eventos de 4 KB tem de caber no buffer do socket: quem
        # limita é a conta do `uhid_queue`, e nunca o socket.
        with contextlib.suppress(OSError):
            self.lado_do_kernel.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 22)
        self.lado_do_kernel.setblocking(False)
        self._trava = threading.Lock()
        self.cheia = 0
        self.enfileirados = 0
        self.destruido = False
        self.respostas_de_feature: dict[int, float] = {}
        self._pare = threading.Event()
        self._fio = threading.Thread(target=self._ler_o_produto, daemon=True)
        self._fio.start()

    # -- o que o produto escreve ------------------------------------------

    def _ler_o_produto(self) -> None:
        while not self._pare.is_set():
            try:
                dado = self.lado_do_kernel.recv(UHID_EVENT_SIZE + 64)
            except BlockingIOError:
                time.sleep(0.0005)
                continue
            except OSError:
                return
            if len(dado) < 4:
                continue
            tipo = struct.unpack("<I", dado[:4])[0]
            if tipo == UHID_CREATE2:
                # O probe do `hid_playstation`: o START e o OPEN do `hid_hw_open`.
                self.enfileirar(struct.pack("<I", UHID_START))
                self.enfileirar(struct.pack("<I", UHID_OPEN))
            elif tipo == UHID_DESTROY:
                self.destruido = True
            elif tipo == UHID_GET_REPORT_REPLY:
                pedido = struct.unpack("<I", dado[4:8])[0]
                self.respostas_de_feature.setdefault(pedido, time.monotonic())

    # -- a fila do `uhid.c` -----------------------------------------------

    def pendentes(self) -> int:
        """Quantos eventos o produto ainda não leu (o `FIONREAD` soma o SEQPACKET)."""
        conta = array.array("i", [0])
        fcntl.ioctl(self.lado_do_produto.fileno(), termios.FIONREAD, conta)
        return conta[0] // UHID_EVENT_SIZE

    def enfileirar(self, evento: bytes) -> bool:
        """O `uhid_queue`: entra se couber, e o que não cabe é descartado."""
        with self._trava:
            if self.pendentes() >= UHID_BUFSIZE - 1:
                self.cheia += 1
                return False
            try:
                self.lado_do_kernel.send(evento.ljust(UHID_EVENT_SIZE, b"\0"))
            except BlockingIOError:
                self.cheia += 1
                return False
            self.enfileirados += 1
            return True

    def fd_do_produto(self) -> int:
        return os.dup(self.lado_do_produto.fileno())

    def fechar(self) -> None:
        self._pare.set()
        self._fio.join(timeout=1.0)
        for lado in (self.lado_do_kernel, self.lado_do_produto):
            with contextlib.suppress(OSError):
                lado.close()


class Relogio:
    """O relógio do virtual (`time_fn`): a graça da réplica anda sem `sleep`."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avancar(self, segundos: float) -> None:
        self.t += segundos


def _evento_de_saida(report: bytes) -> bytes:
    """`struct uhid_output_req { __u8 data[4096]; __u16 size; __u8 rtype; }`."""
    evento = struct.pack("<I", UHID_OUTPUT)
    evento += report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
    evento += struct.pack("<HB", len(report), 1)
    return evento


def _vibracao(fraco: int, forte: int) -> bytes:
    """O report 0x02 de vibração que o `hid_playstation` monta (firmware v2)."""
    corpo = bytearray(47)
    corpo[0] = 0x02  # HAPTICS_SELECT, o que o hardware real manda sozinho
    corpo[2] = fraco
    corpo[3] = forte
    return bytes([0x02]) + bytes(corpo)


def _luz(r: int, g: int, b: int) -> bytes:
    """O report 0x02 de luz (valid_flag1 = LIGHTBAR_CONTROL_ENABLE)."""
    corpo = bytearray(47)
    corpo[1] = 0x04
    corpo[44], corpo[45], corpo[46] = r, g, b
    return bytes([0x02]) + bytes(corpo)


def _pedido_de_feature(pedido: int, numero: int) -> bytes:
    """`struct uhid_get_report_req { __u32 id; __u8 rnum; __u8 rtype; }`."""
    return struct.pack("<IIBB", UHID_GET_REPORT, pedido, numero, 0)


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoUhid]:
    """O `/dev/uhid` de mentira: o `os.open` do nó devolve o lado do produto."""
    k = KernelDoUhid()
    abrir = os.open

    def _abrir(caminho: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if os.fsdecode(caminho) == uhid_gamepad.UHID_NODE:
            return k.fd_do_produto()
        return abrir(caminho, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _abrir)
    try:
        yield k
    finally:
        k.fechar()


class Fisico:
    """Os sinks do controle físico, com a thread de cada entrega anotada."""

    def __init__(self) -> None:
        self.vibracao: list[tuple[int, int]] = []
        self.luz: list[tuple[int, int, int]] = []
        self.fios: set[int] = set()

    def sinks(self) -> dict[str, Any]:
        def _vib(fraco: int, forte: int) -> None:
            self.fios.add(threading.get_ident())
            self.vibracao.append((fraco, forte))

        def _luz(r: int, g: int, b: int) -> None:
            self.fios.add(threading.get_ident())
            self.luz.append((r, g, b))

        return {"rumble_sink": _vib, "lightbar_sink": _luz}


def _virtual(relogio: Relogio, fisico: Fisico | None = None) -> UhidDualSense:
    """O virtual do P2, nascido pelo caminho do produto, e esperado até o bind."""
    pad = UhidDualSense(
        player=2,
        blueprint=canonical_blueprint(),
        time_fn=relogio,
        **(fisico.sinks() if fisico is not None else {}),
    )
    assert pad.start() is True
    inicio = time.monotonic()
    while not pad.is_bound and time.monotonic() - inicio < 1.0:
        # O tique de antes da cura é quem bombeia o bind; com a cura, o fio.
        # A régua não depende disso: ela só começa com o virtual de pé.
        pad.pump_ff()
        time.sleep(0.002)
    assert pad.is_bound, "o virtual não fez bind no kernel de mentira"
    relogio.avancar(1.0)  # a graça pós-bind da réplica (`_GAME_REPLICA_GRACE_S`)
    return pad


def _esperar(condicao: Any, prazo_s: float) -> float:
    inicio = time.monotonic()
    while not condicao() and time.monotonic() - inicio < prazo_s:
        time.sleep(0.001)
    return time.monotonic() - inicio


def test_duzentos_eventos_sem_tique_nenhum_cai(kernel: KernelDoUhid) -> None:
    """A régua da sprint: 200 eventos de saída em ~100 ms sem tique de entrada.

    MORDE: devolva o dreno ao tique (tire o `_iniciar_o_fio_do_uhid` do
    `_criar_o_device`) — a fila de 31 enche, o kernel descarta 169, e o
    produto não viu nenhum.
    """
    pad = _virtual(Relogio())
    try:
        inicio = time.monotonic()
        for n in range(EVENTOS):
            kernel.enfileirar(_evento_de_saida(_vibracao(n % 256, 0)))
            # O jogo (ou o `cosmic-osk`) escrevendo sem parar, ~2.000 por segundo.
            time.sleep(JANELA_S / EVENTOS)
        durou = time.monotonic() - inicio
        _esperar(lambda: pad.output_count >= EVENTOS, 1.0)
        assert kernel.cheia == 0, (
            f"o kernel descartou {kernel.cheia} de {EVENTOS} eventos em "
            f"{durou * 1000:.0f} ms («Output queue is full»): a saída que o jogo "
            "manda esperava o tique do repasse da entrada"
        )
        assert pad.output_count == EVENTOS, (
            f"o virtual atendeu {pad.output_count} de {EVENTOS} sem tique"
        )
    finally:
        pad.stop()


def test_o_pedido_de_feature_e_respondido_sem_tique(kernel: KernelDoUhid) -> None:
    """O jogo pede um feature report (0x09) e fica parado até a resposta.

    No `uhid.c`, o `uhid_hid_get_report` espera a resposta por até 5 s com o
    jogo parado na chamada. Sem o fio, ela só saía no tique seguinte.

    MORDE: sem o `_iniciar_o_fio_do_uhid`, ninguém responde dentro do prazo.
    """
    pad = _virtual(Relogio())
    try:
        pedido = 77
        pediu_em = time.monotonic()
        assert kernel.enfileirar(_pedido_de_feature(pedido, 0x09))
        _esperar(lambda: pedido in kernel.respostas_de_feature, PRAZO_S)
        assert pedido in kernel.respostas_de_feature, (
            "o pedido de feature do jogo ficou sem resposta sem o tique"
        )
        assert kernel.respostas_de_feature[pedido] - pediu_em < PRAZO_S
    finally:
        pad.stop()


def test_a_entrega_ao_fisico_segue_no_tique(kernel: KernelDoUhid) -> None:
    """O fio atende; quem fala com o controle físico é o tique, com o dedup de sempre.

    MORDE: chame os sinks no fio do virtual (o `_emit_rumble` sem o
    `_no_fio_do_uhid`) — a vibração chega antes do tique, e de outra thread.
    """
    fisico = Fisico()
    relogio = Relogio()
    pad = _virtual(relogio, fisico)
    try:
        for fraco in (10, 20, 30):
            kernel.enfileirar(_evento_de_saida(_vibracao(fraco, 5)))
        kernel.enfileirar(_evento_de_saida(_luz(1, 2, 3)))
        _esperar(lambda: pad.output_count >= 4, 1.0)
        assert pad.output_count == 4
        assert fisico.vibracao == [], "o fio do virtual falou com o controle físico"
        assert fisico.luz == []

        pad.pump_ff()  # o tique

        assert fisico.vibracao == [(30, 5)], (
            f"o tique não entregou o último pedido: {fisico.vibracao}"
        )
        assert fisico.luz == [(1, 2, 3)]
        assert fisico.fios == {threading.get_ident()}, (
            "o controle físico ouviu de outra thread que não a do tique"
        )
        pad.pump_ff()  # nada de novo: o dedup não reenvia
        assert fisico.vibracao == [(30, 5)]
    finally:
        pad.stop()


def test_o_stop_encerra_o_fio_antes_de_fechar(kernel: KernelDoUhid) -> None:
    """O fio do virtual sai antes do fd fechar, e o kernel recebe o `UHID_DESTROY`."""
    pad = _virtual(Relogio())
    fio = pad._fio_do_uhid
    assert fio is not None and fio.is_alive(), "o virtual nasceu sem o fio que o atende"
    pad.stop()
    assert not fio.is_alive()
    assert pad._fio_do_uhid is None
    _esperar(lambda: kernel.destruido, 1.0)
    assert kernel.destruido


def test_o_dublê_sem_fd_de_verdade_segue_no_tique(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem descritor de verdade (os dublês da suíte), o tique atende, como antes."""
    lidos: list[bytes] = [struct.pack("<I", UHID_START)]
    monkeypatch.setattr(os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(os, "close", lambda _fd: None)
    monkeypatch.setattr(os, "set_blocking", lambda _fd, _b: None)
    monkeypatch.setattr(os, "write", lambda _fd, dado: len(dado))

    def _ler(_fd: int, _tamanho: int) -> bytes:
        if not lidos:
            raise BlockingIOError
        return lidos.pop(0)

    monkeypatch.setattr(os, "read", _ler)
    pad = UhidDualSense(player=3, blueprint=canonical_blueprint())
    assert pad.start() is True
    try:
        assert pad._fio_do_uhid is None
        pad.pump_ff()
        assert pad.is_bound
    finally:
        pad.stop()
