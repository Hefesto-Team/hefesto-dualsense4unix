"""O-P1-E-O-GADGET-TARDIO-DESCEM-PELA-FILA-DA-DESCIDA-01 (25/10/2026).

As duas sobras do jogador-sai. A troca de ordem do co-op derruba o P1 pelo
``stop_gamepad_emulation``, que chamava o ``stop`` do pad: o ``stop`` termina a
descida do gadget no próprio fio, e o co-op roda no ``sync`` do laço do tique.
Com o broker preso, a entrada de todos parava ~4 s. E o gadget que o pedido em
voo trazia para um pad já parado descia por ``gadget.desmontar()`` no fio do
pedido, por fora da fila da descida: o MAC do pad, o pad novo do mesmo aparelho
e o ``stop_all`` não o esperavam.

Os pads são os de VERDADE, no gadget da bancada; o cliente da descida é o
``HidrawBrokerClient`` de verdade contra o socket que aceita e não responde.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import _CHAVE_DO_P1
from hefesto_dualsense4unix.daemon.subsystems.gamepad import stop_gamepad_emulation
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from tests.unit import test_o_pad_recusado_pelo_broker_tenta_de_novo as recusado
from tests.unit.test_o_gadget_que_desce_no_tique_fala_com_o_broker_fora_dele import (
    PRESO_S,
    ClienteLento,
    _a_descida,
    _ate_a_queda,
    _fechar,
    _mesa,
)
from tests.unit.test_o_jogador_que_sai_nao_prende_o_tique_no_broker import _a_mesa_de_pe
from tests.unit.test_o_pad_que_nasce_pede_o_gadget_fora_do_tique import (
    TETO_DO_TIQUE_S,
    _guardar_o_lado_do_jogo,
    _tique,
)
from tests.unit.test_o_pad_recusado_pelo_broker_tenta_de_novo import Mesa

#: de um a quatro pads, o P1 sempre de pé; P1 e P3 no cabo, P2 e P4 no rádio.
MESAS_DO_P1 = [(1,), (1, 2), (1, 2, 3), (1, 2, 3, 4), (1, 3)]
IDS_DO_P1 = ["so-o-p1", "p1-e-p2", "p1-p2-p3", "quatro", "todos-usb"]
#: o aparelho do P1: o do cabo (o da ``MESA_MISTA``) ou o do rádio (trocado com o P2).
TRANSPORTES_DO_P1 = ("cabo", "radio")  # (noqa-acento): chave de máquina
#: quem cai e volta a pedir o gadget; o pedido dele é largado pelo ``stop``.
MESAS_DO_TARDIO = [((1, 2), 2), ((1, 2), 1), ((1, 2, 3, 4), 4), ((1, 2, 3, 4), 1),
                   ((1,), 1), ((2, 4), 2), ((1, 3), 3)]
IDS_DO_TARDIO = ["p2-bt", "p1-usb", "quatro-p4", "quatro-p1", "um-so", "todos-bt",
                 "todos-usb"]
#: o ``stop`` que não espera (o do tique) e o que espera (o da parada do daemon).
PARADAS = ("no_tique", "que_espera")  # (noqa-acento): chave de máquina


def _o_p1_no(monkeypatch: pytest.MonkeyPatch, transporte: str) -> None:
    """O P1 no aparelho do rádio: a identidade do P2 vai ao P1, e a dele ao P2."""
    if transporte == "radio":
        p1, p2 = recusado.MESA_MISTA[1], recusado.MESA_MISTA[2]
        monkeypatch.setitem(recusado.MESA_MISTA, 1, p2)
        monkeypatch.setitem(recusado.MESA_MISTA, 2, p1)


def _a_mesa_com_o_p1(
    monkeypatch: pytest.MonkeyPatch, m: Mesa, jogadores: tuple[int, ...], *,
    parando: bool = False,
) -> tuple[list[Any], Any, Any]:
    """Os pads no gadget; o do P1 é o vpad do primário, e o resto é o co-op."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    monkeypatch.setattr(gamepad, "_materialize_launch_env", lambda _d: None)
    pads, coop = _a_mesa_de_pe(m, jogadores)
    p1 = pads[jogadores.index(1)]
    daemon = coop._daemon
    daemon._gamepad_device = p1
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.rumble_active = None
    daemon._is_stopping = lambda: parando
    coop._vpad_do_p1_visto = p1
    return pads, coop, p1


@pytest.mark.parametrize("transporte", TRANSPORTES_DO_P1)
@pytest.mark.parametrize("jogadores", MESAS_DO_P1, ids=IDS_DO_P1)
def test_a_troca_de_ordem_com_o_p1_vivo_nao_prende_o_tique_no_broker_preso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    transporte: str,
) -> None:
    # D-2510-O-P1-DA-TROCA-DE-ORDEM-DESCE-PELA-FILA
    """O broker aceita e não responde: o tique em que o co-op derruba o P1 para a troca
    de ordem fica abaixo de 50 ms, e a descida do gadget dele chega ao broker depois.

    Mordida: devolva o ``daemon._gamepad_device.stop()`` ao ``stop_gamepad_emulation``
    fora da parada do daemon, e o tique da troca leva as duas tentativas do cliente, ~4 s.
    """
    _o_p1_no(monkeypatch, transporte)
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads, coop, p1 = _a_mesa_com_o_p1(monkeypatch, m, jogadores)
        gadget = p1._gadget
        gadget.cliente = hbc.HidrawBrokerClient()
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        seguem = [p for p in pads if p is not p1]
        antes = time.perf_counter()
        coop._derrubar_para_renascer(_CHAVE_DO_P1)
        duracao = time.perf_counter() - antes + _tique(m, seguem, 0.1)
        assert duracao < TETO_DO_TIQUE_S, (
            f"o tique da troca de ordem levou {duracao * 1000:.2f} ms com o broker preso"
        )
        assert not p1.is_active() and coop._daemon._gamepad_device is None, (
            "o P1 da troca de ordem segue no ar"
        )
        if seguem:
            assert max(_tique(m, seguem, 0.1) for _ in range(3)) < TETO_DO_TIQUE_S
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            "a descida do P1 não chegou ao broker"
        )
        vivos = m.ug._MACS_DOS_VPADS_VIVOS
        assert vivos.vestido_por(p1) is not None, (
            "o MAC do P1 voltou com o gadget dele ainda montado no broker"
        )
        m.broker.fechar()
        assert _a_descida(m).esperar_tudo(2 * PRESO_S)
        assert vivos.vestido_por(p1) is None, "o MAC do P1 não voltou depois da descida"
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize("jogadores", MESAS_DO_P1, ids=IDS_DO_P1)
def test_na_parada_do_daemon_o_p1_so_volta_com_o_gadget_devolvido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
) -> None:
    """O daemon para: o ``stop_gamepad_emulation`` do P1 é o que espera, e só volta com o
    gadget dele devolvido ao broker e o MAC solto.

    Mordida: troque o ``stop`` da parada do daemon pelo que não espera, e ele volta com
    o gadget do P1 montado.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta = threading.Event()
    try:
        pads, coop, p1 = _a_mesa_com_o_p1(monkeypatch, m, jogadores, parando=True)
        lento = ClienteLento(solta)
        p1._gadget.cliente = lento
        threading.Timer(0.3, solta.set).start()
        stop_gamepad_emulation(coop._daemon, persist=False)
        assert lento.desmontados and lento.fechado, (
            "a parada do daemon voltou com o gadget do P1 montado no broker"
        )
        assert m.ug._MACS_DOS_VPADS_VIVOS.vestido_por(p1) is None
    finally:
        solta.set()
        _fechar(m, pads)


class _PedidoPreso:
    """O ``PEDIR_O_PAD_USB`` que segura o pedido até a régua soltar, e veste o
    gadget que chega com o cliente lento da descida."""

    def __init__(self, m: Mesa, lento: ClienteLento) -> None:
        self.de_verdade = m.ug.PEDIR_O_PAD_USB
        self.libera = threading.Event()
        self.no_pedido = threading.Event()
        self.lento = lento
        self.chegou: list[Any] = []

    def __call__(self, *argumentos: Any) -> Any:
        self.no_pedido.set()
        self.libera.wait(PRESO_S)
        gadget = self.de_verdade(*argumentos)
        if gadget is not None:
            gadget.cliente = self.lento
            self.chegou.append(gadget)
        return gadget


def _parar(m: Mesa, pad: Any, parada: str) -> threading.Thread | None:
    if parada == "no_tique":
        m.ug.parar_fora_do_tique(pad)
        return None
    fio = threading.Thread(target=pad.stop, daemon=True)
    fio.start()
    return fio


@pytest.mark.parametrize("parada", PARADAS)
@pytest.mark.parametrize(("jogadores", "quem_cai"), MESAS_DO_TARDIO, ids=IDS_DO_TARDIO)
def test_o_gadget_que_chega_para_o_pad_parado_desce_pela_fila(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_cai: int, parada: str,
) -> None:
    # D-2510-O-GADGET-TARDIO-DESCE-PELA-FILA
    """O pad perdeu o gadget e pede outro; ele para com o pedido em voo, e o gadget chega
    depois: ele desce pela fila, fora do fio do pedido, e o MAC, o ``stop_all`` e o pad
    novo do mesmo aparelho só seguem com a descida feita.

    Mordida: devolva o ``gadget.desmontar()`` ao ramo do largado em
    ``_PedidoAoBroker._perguntar``, e o fio do pedido fica preso no broker, o
    ``stop_all`` volta com o gadget montado e o MAC solta antes.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta = threading.Event()
    lento = ClienteLento(solta)
    preso = _PedidoPreso(m, lento)
    fio: threading.Thread | None = None
    try:
        pads = _ate_a_queda(m, jogadores, quem_cai, "caiu")
        cai = pads[jogadores.index(quem_cai)]
        m.passar(0.1, pads, assentar=False)
        assert cai._gadget is None and cai._gadget_outra_vez
        assert _a_descida(m).esperar_tudo(2.0)
        monkeypatch.setattr(m.ug, "PEDIR_O_PAD_USB", preso)
        _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)
        pedido = cai._pedido_ao_broker
        assert pedido is not None and preso.no_pedido.wait(2.0), "o pad não pediu de novo"
        vivos = m.ug._MACS_DOS_VPADS_VIVOS
        mac_de_antes = cai.mac
        fio = _parar(m, cai, parada)
        novo = m.pad(quem_cai)
        pads.append(novo)
        nasceu = threading.Thread(target=novo.start, daemon=True)
        nasceu.start()
        assert not _a_descida(m).esperar_tudo(0.2), (
            "o stop_all voltaria com o pedido do pad parado ainda em voo"
        )
        assert vivos.vestido_por(cai) is not None, (
            "o MAC do pad parado voltou com o pedido dele em voo"
        )
        preso.libera.set()
        assert pedido.esperar(1.0), "o gadget tardio desceu no fio do pedido"
        assert preso.chegou, "o pedido não trouxe o gadget"
        assert not _a_descida(m).esperar_tudo(0.2), (
            "o stop_all voltaria com o gadget tardio montado no broker"
        )
        assert vivos.vestido_por(cai) is not None, (
            "o MAC do pad parado voltou com o gadget tardio montado"
        )
        assert nasceu.is_alive(), "o pad novo do aparelho nasceu antes da descida"
        solta.set()
        assert _a_descida(m).esperar_tudo(PRESO_S), "a descida do gadget tardio não terminou"
        assert lento.desmontados == [preso.chegou[0].gadget] and lento.fechado
        assert vivos.vestido_por(cai) is None, "o MAC do pad parado não voltou"
        nasceu.join(PRESO_S)
        _guardar_o_lado_do_jogo(m)
        assert not nasceu.is_alive(), "o pad novo não nasceu depois da descida"
        assert novo.mac == mac_de_antes, f"o pad novo vestiu {novo.mac}, e não o de antes"
        if fio is not None:
            fio.join(PRESO_S)
            assert not fio.is_alive(), "o stop que espera não voltou"
    finally:
        preso.libera.set()
        solta.set()
        if fio is not None:
            fio.join(PRESO_S)
        _fechar(m, pads)


def test_o_stop_que_espera_nao_espera_o_pedido_que_ja_respondeu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """O pedido que já respondeu (o gadget nas mãos do tique) não é promessa: o ``stop``
    o desce pela fila, como antes, e volta sem esperar prazo nenhum."""
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, (1, 2), 2, "caiu")
        cai = pads[1]
        m.passar(0.1, pads, assentar=False)
        assert _a_descida(m).esperar_tudo(2.0)
        _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)
        pedido = cai._pedido_ao_broker
        assert pedido is not None and pedido.esperar(5.0)
        antes = time.monotonic()
        cai.stop()
        assert time.monotonic() - antes < 1.0
        assert _a_descida(m).esperar_tudo(1.0)
        assert m.ug._MACS_DOS_VPADS_VIVOS.vestido_por(cai) is None
    finally:
        _fechar(m, pads)

