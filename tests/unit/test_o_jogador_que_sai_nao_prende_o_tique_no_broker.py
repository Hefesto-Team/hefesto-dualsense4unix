"""O-JOGADOR-QUE-SAI-NAO-PRENDE-O-TIQUE-NO-BROKER-01 (25/10/2026).

O ``stop`` do pad termina a descida do gadget dele no próprio fio
(``_DescidaAoBroker.terminar``): com o broker preso, o ``desmontar_pad_usb`` do
cliente tenta duas vezes, de ``_TIMEOUT_S`` cada. O co-op chamava esse ``stop``
na saída do jogador (``_teardown_player``) e na troca de roupa
(``_derrubar_para_renascer``), e os dois rodam no ``sync`` do laço do tique: um
controle que saía segurava a entrada de todos os outros.

Os pads são os de VERDADE, no gadget da bancada; o cliente da descida é o
``HidrawBrokerClient`` de verdade contra o socket que aceita e não responde.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from tests.unit.test_o_gadget_que_desce_no_tique_fala_com_o_broker_fora_dele import (
    PRESO_S,
    ClienteLento,
    _a_descida,
    _ate_a_queda,
    _fechar,
    _mesa,
)
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import INTERFACE_DO_GADGET
from tests.unit.test_o_pad_que_nasce_pede_o_gadget_fora_do_tique import (
    TETO_DO_TIQUE_S,
    _guardar_o_lado_do_jogo,
    _tique,
)
from tests.unit.test_o_pad_recusado_pelo_broker_tenta_de_novo import Mesa

#: P1 e P3 no cabo, P2 e P4 no rádio (``MESA_MISTA``); o último é quem sai. O P1 é
#: o vpad do primário, que o co-op não derruba: ele só segue lendo.
MESAS = [((1, 2), 2), ((1, 2, 3, 4), 4), ((1, 2, 3, 4), 2), ((2,), 2), ((2, 4), 4),
         ((1, 3), 3)]
IDS = ["p2-bt-sai", "quatro-p4-sai", "quatro-p2-sai", "um-so", "todos-bt", "todos-usb"]
#: os caminhos do ``sync`` que param o vpad de um jogador no laço do tique.
CAMINHOS = ("saida", "troca_de_roupa", "coop_desliga")  # (noqa-acento): chave de máquina


class _Controle:
    """O backend do P1: o zero do motor de quem sai e o nó dele, sem aparelho."""

    def force_rumble_stop(self, uniq: str | None = None) -> None: ...

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return None


class _Daemon:
    def __init__(self) -> None:
        self._gamepad_device = None
        self._coop_manager = None
        self._hidraw_broker_client = SimpleNamespace(
            hide=lambda _n: True, restore=lambda _n: True, restore_all=lambda: True,
        )
        self.controller = _Controle()
        self.config = SimpleNamespace(gamepad_emulation_enabled=True)

    def is_native_mode(self) -> bool:
        return False


def _a_mesa_de_pe(m: Mesa, jogadores: tuple[int, ...]) -> tuple[list[Any], CoopManager]:
    """Os pads no gadget, enumerados; do P2 ao P4, cada um é um jogador do co-op."""
    m.sessao_aberta = True
    pads = [m.pad(j) for j in jogadores]
    for pad in pads:
        assert pad.start() and pad._gadget is not None
        _guardar_o_lado_do_jogo(m)
        m.enumerados[m.serial(pad)] = (f"hidraw{pad.player}", INTERFACE_DO_GADGET)
    assert m.b.esperar(lambda: all(p.is_bound for p in pads))
    return pads, _o_coop_de(pads)


def _o_coop_de(pads: list[Any]) -> CoopManager:
    """O co-op com um jogador por pad do P2 ao P4 (o P1 é o primário)."""
    coop = CoopManager(_Daemon())
    coop._materialize_launch_env = lambda: None
    for pad in pads:
        if pad.player == 1:
            continue
        coop._players[pad.identity] = _SecondaryPlayer(
            identity=pad.identity, evdev_path=f"/dev/input/event9{pad.player}",
            reader=SimpleNamespace(
                set_grab=lambda _g: True, stop=lambda: None, grab_state="held"),
            player_index=pad.player, vpad=pad,
        )
    return coop


def _parar(coop: CoopManager, caminho: str, identidade: str) -> None:
    """O gesto do ``sync`` que para o vpad de quem sai."""
    if caminho == "saida":
        coop._teardown_player(identidade)
    elif caminho == "troca_de_roupa":
        coop._derrubar_para_renascer(identidade)
    else:
        coop.disable()


def _de_pe(m: Mesa, pads: list[Any], caminho: str, sai: Any) -> list[Any]:
    """Os pads que seguem lendo depois do gesto (o co-op desligado deixa só o P1)."""
    if caminho == "coop_desliga":
        return [p for p in pads if p.player == 1]
    return [p for p in pads if p is not sai]


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_jogador_que_sai_nao_prende_o_tique_no_broker_preso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int, caminho: str,
) -> None:
    # D-2510-O-JOGADOR-QUE-SAI-DESCE-O-GADGET-FORA-DO-TIQUE
    """O broker aceita e não responde: o tique em que o jogador sai fica abaixo de 50 ms.

    Mordida: devolva o ``player.vpad.stop()`` ao ``_teardown_player`` (ou o
    ``jogador.vpad.stop()`` ao ``_derrubar_para_renascer``), e o tique da saída leva
    as duas tentativas do cliente preso, ~4 s.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads, coop = _a_mesa_de_pe(m, jogadores)
        sai = pads[jogadores.index(quem_sai)]
        gadget = sai._gadget
        gadget.cliente = hbc.HidrawBrokerClient()
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        antes = time.perf_counter()
        _parar(coop, caminho, sai.identity)
        seguem = _de_pe(m, pads, caminho, sai)
        duracao = time.perf_counter() - antes + _tique(m, seguem, 0.1)
        assert duracao < TETO_DO_TIQUE_S, (
            f"o tique da {caminho} levou {duracao * 1000:.2f} ms com o broker preso"
        )
        assert not sai.is_active(), "o pad de quem saiu segue no ar"
        assert max(_tique(m, seguem, 0.1) for _ in range(3)) < TETO_DO_TIQUE_S
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            "a descida de quem saiu não chegou ao broker"
        )
        assert gadget.serial not in m.ug._FILA_DA_ENUMERACAO, "a casa não soltou o gadget"
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_mac_de_quem_sai_so_volta_com_o_gadget_devolvido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int, caminho: str,
) -> None:
    """O gadget segue no kernel com o MAC do pad até o broker o desmontar: o MAC só
    se devolve depois, como no ``stop`` que espera, e o broker que responde recebe a descida.

    Mordida: devolva o MAC na parada que não espera (antes da descida), e o MAC de
    quem saiu fica livre com o gadget dele ainda montado.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta = threading.Event()
    try:
        pads, coop = _a_mesa_de_pe(m, jogadores)
        sai = pads[jogadores.index(quem_sai)]
        lento = ClienteLento(solta)
        sai._gadget.cliente = lento
        _parar(coop, caminho, sai.identity)
        vivos = m.ug._MACS_DOS_VPADS_VIVOS
        assert vivos.vestido_por(sai) is not None, (
            "o MAC de quem saiu voltou com o gadget dele ainda montado no broker"
        )
        solta.set()
        assert m.b.esperar(lambda: vivos.vestido_por(sai) is None), (
            "o MAC de quem saiu não voltou depois da descida"
        )
        assert lento.desmontados and lento.fechado, "a descida não chegou ao broker"
    finally:
        solta.set()
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_stop_do_daemon_espera_a_descida_de_quem_saiu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int,
) -> None:
    """O jogador saiu com o broker lento, e o daemon para: o ``stop_all`` do co-op só
    volta com o gadget de quem saiu devolvido, e nenhum gadget dos outros fica montado.

    Mordida: o ``stop_all`` sem a espera (o ``disable`` puro), e o daemon para com
    o gadget de quem saiu montado no broker.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta = threading.Event()
    try:
        pads, coop = _a_mesa_de_pe(m, jogadores)
        sai = pads[jogadores.index(quem_sai)]
        lento = ClienteLento(solta)
        sai._gadget.cliente = lento
        outros = [p._gadget.cliente for p in pads if p is not sai and p.player != 1]
        coop._teardown_player(sai.identity)
        assert not lento.desmontados
        threading.Timer(0.3, solta.set).start()
        antes = time.monotonic()
        coop.stop_all()
        duracao = time.monotonic() - antes
        assert lento.desmontados, (
            f"o daemon parou ({duracao:.2f} s) com o gadget de quem saiu montado no broker"
        )
        assert lento.fechado, "o daemon parou com a lease do gadget de quem saiu aberta"
        assert all(c.desmontados for c in outros), "o daemon parou com gadget montado"
        assert duracao < PRESO_S + 1.0
    finally:
        solta.set()
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_gadget_que_chegou_para_quem_sai_desce_fora_do_tique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int,
) -> None:
    """O pad de quem sai voltava ao gadget, e o pedido já trouxe o gadget novo que o tique
    ainda não leu: o ``stop`` larga o pedido, e o gadget que chegou desce fora do tique.

    Mordida: devolva o ``gadget.desmontar()`` ao ``_PedidoAoBroker.largar``, e o tique
    da saída leva as duas tentativas do cliente preso.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, jogadores, quem_sai, "caiu")
        sai = pads[jogadores.index(quem_sai)]
        m.passar(0.1, pads, assentar=False)
        assert sai._gadget is None and sai._gadget_outra_vez
        assert _a_descida(m).esperar_tudo(2.0)
        assert _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5) < TETO_DO_TIQUE_S
        pedido = sai._pedido_ao_broker
        assert pedido is not None and pedido.esperar(5.0)
        chegou = pedido._gadget
        assert chegou is not None, "a volta não trouxe o gadget"
        chegou.cliente = hbc.HidrawBrokerClient()
        coop = _o_coop_de(pads)
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        antes = time.perf_counter()
        coop._teardown_player(sai.identity)
        seguem = [p for p in pads if p is not sai]
        duracao = time.perf_counter() - antes + _tique(m, seguem, 0.1)
        assert duracao < TETO_DO_TIQUE_S, (
            f"o tique da saída levou {duracao * 1000:.2f} ms com o gadget que chegou"
        )
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            "o gadget que chegou para quem saiu não foi devolvido ao broker"
        )
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_pad_que_renasce_veste_o_mac_de_antes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int,
) -> None:
    """A troca de roupa derruba o pad e o faz nascer de novo, fora do tique: o pad novo do
    mesmo aparelho espera a descida do que parou e veste o MAC de antes, como no ``stop``
    que esperava.

    Mordida: tire o ``esperar_o_aparelho`` do ``start``, e o pad novo veste outro MAC
    (o de antes segue no gadget que o broker ainda não desmontou).
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta = threading.Event()
    try:
        pads, coop = _a_mesa_de_pe(m, jogadores)
        sai = pads[jogadores.index(quem_sai)]
        mac_de_antes = sai.mac
        lento = ClienteLento(solta)
        sai._gadget.cliente = lento
        coop._derrubar_para_renascer(sai.identity)
        novo = m.pad(quem_sai)
        pads.append(novo)
        threading.Timer(0.3, solta.set).start()
        nasceu = threading.Thread(target=novo.start, daemon=True)
        nasceu.start()
        nasceu.join(PRESO_S + 1.0)
        _guardar_o_lado_do_jogo(m)
        assert not nasceu.is_alive(), "o pad novo não nasceu"
        assert lento.desmontados, "o pad novo nasceu antes da descida do de antes"
        assert novo.mac == mac_de_antes, (
            f"o pad que renasceu vestiu {novo.mac}, e não o MAC de antes"
        )
    finally:
        solta.set()
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_sai"), MESAS, ids=IDS)
def test_o_stop_do_daemon_so_volta_com_o_mac_de_quem_saiu_devolvido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_sai: int,
) -> None:
    """A descida de quem saiu terminou, e o MAC dele ainda volta à lista no fio da descida:
    o ``stop_all`` espera também essa volta, e não só a fila esvaziar.

    Mordida: tire o ``not self._depois`` do ``esperar_tudo``, e o daemon para com o MAC
    de quem saiu ainda vestido (onde quem sai é o único do co-op; nos outros, a descida
    dos que o ``stop_all`` para segura a volta junto).
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    solta, no_gancho, segura, parou = (threading.Event() for _ in range(4))
    try:
        pads, coop = _a_mesa_de_pe(m, jogadores)
        sai = pads[jogadores.index(quem_sai)]
        sai._gadget.cliente = ClienteLento(solta)
        despir = m.ug._despir_se_parado

        def devagar(pad: Any) -> None:
            if pad is sai:
                no_gancho.set()
                segura.wait(PRESO_S)
            despir(pad)

        monkeypatch.setattr(m.ug, "_despir_se_parado", devagar)
        coop._teardown_player(sai.identity)
        solta.set()
        assert no_gancho.wait(PRESO_S), "a descida de quem saiu não terminou"

        def parar() -> None:
            coop.stop_all()
            parou.set()

        threading.Thread(target=parar, daemon=True).start()
        assert not parou.wait(0.3), "o daemon parou com o MAC de quem saiu ainda vestido"
        segura.set()
        assert parou.wait(PRESO_S), "o daemon não parou depois da volta do MAC"
        assert m.ug._MACS_DOS_VPADS_VIVOS.vestido_por(sai) is None
    finally:
        solta.set()
        segura.set()
        _fechar(m, pads)
