"""O-PAD-QUE-NASCE-NAO-PARA-O-TIQUE-DOS-OUTROS-01 — o nascimento do pad sai do laço do tique.

O `CoopManager` REAL, com a fábrica do pad de mentira que leva 300 ms (o `wait_for_bind`
do `uhid` e o assentamento depois dele), e o laço do tique emulado a 60 Hz: a cada
volta, o `forward_all` dos secundários e a entrada do P1. Com o fio de nascimento do
daemon (`virtual_pad.FioDeNascimento`), o P1 recebe a entrada a cada volta enquanto o
pad do outro nasce; o pad pronto entra no tique seguinte à entrega, e quem pediu antes
é instalado antes. Vale para o pad do cabo e do rádio (a fábrica é uma só) e para o
White, o Cosmic Red e o Galactic Purple, que são os secundários da mesa.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

_P1 = "aabbcc000001"
_WHITE = "aabbcc000002"
_COSMIC_RED = "aabbcc000003"
_GALACTIC_PURPLE = "aabbcc000004"
_CALIB = bytes([0x05]) + bytes([0xAB]) * 40
_NASCIMENTO_S = 0.3
_TIQUE_S = 1.0 / 60.0


class _Pad:
    """O pad de mentira: anota quando recebe entrada e quando para."""

    def __init__(self, identity: str | None) -> None:
        self.identity = identity
        self.flavor = "dualsense"
        self.backend = "uhid"
        self.caminho = vp.CAMINHO_DUALSENSE
        self.entradas: list[float] = []
        self.parado = False

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.entradas.append(time.monotonic())

    def forward_analog(self, *args: Any, **kwargs: Any) -> None:
        pass

    def forward_triggers(self, *args: Any, **kwargs: Any) -> None:
        pass

    def pump_ff(self) -> None:
        pass

    def is_active(self) -> bool:
        return not self.parado

    def stop(self) -> None:
        self.parado = True


class _Leitor:
    grab_state = "held"

    def set_grab(self, _g: bool) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=frozenset(), apertos=None)


class _Controle:
    primary_uniq = _P1

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return None

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        return _CALIB


class _Daemon:
    def __init__(self) -> None:
        self.controller = _Controle()
        self.config = DaemonConfig()
        self.config.coop_enabled = True
        self.store = StateStore()
        self._gamepad_device = _Pad(_P1)
        self._fio_de_nascimento = _o_fio()

    def is_native_mode(self) -> bool:
        return False


def _o_fio() -> Any:
    """O fio de nascimento do daemon, ou `None` onde ele não existe (a medida de antes)."""
    fabrica = getattr(vp, "FioDeNascimento", None)
    return fabrica() if fabrica is not None else None


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    monkeypatch.setattr(prr, "PhysicalReportReader", lambda **_k: None)
    for nome in ("_materialize_launch_env", "_broker_hide_player",
                 "_start_player_motion_reader", "_armar_sossego_do_launch_env"):
        monkeypatch.setattr(coop_mod.CoopManager, nome, lambda self, *a, **k: None)
    pedidos: list[tuple[str, str]] = []
    pads: dict[str, _Pad] = {}

    def _fabrica(flavor: Any, **kwargs: Any) -> _Pad:
        identidade = kwargs.get("identity")
        pedidos.append((str(identidade), threading.current_thread().name))
        time.sleep(_NASCIMENTO_S)
        pad = _Pad(identidade)
        pad.flavor = flavor
        pads[str(identidade)] = pad
        return pad

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    daemon = _Daemon()
    manager = coop_mod.CoopManager(daemon)  # type: ignore[arg-type]
    daemon._coop_manager = manager  # type: ignore[attr-defined]
    monkeypatch.setattr(coop_mod, "get_coop_manager", lambda _d: manager)
    for mac in (_WHITE, _COSMIC_RED, _GALACTIC_PURPLE):
        coop_mod.calibration_cache(daemon)[mac] = _CALIB
    yield SimpleNamespace(daemon=daemon, manager=manager, pedidos=pedidos, pads=pads)
    fio = getattr(daemon, "_fio_de_nascimento", None)
    if fio is not None:
        fio.parar()


def _jogador(mesa: SimpleNamespace, mac: str, indice: int) -> Any:
    jogador = coop_mod._SecondaryPlayer(
        identity=mac, evdev_path=f"/dev/input/event9{indice}", reader=_Leitor(),
        player_index=indice,
    )
    mesa.manager._players[mac] = jogador
    return jogador


def _tique(mesa: SimpleNamespace) -> None:
    """Uma volta do laço: os secundários primeiro, depois a entrada do P1."""
    inicio = time.monotonic()
    mesa.manager.forward_all()
    mesa.daemon._gamepad_device.forward_buttons(frozenset())
    sobra = _TIQUE_S - (time.monotonic() - inicio)
    if sobra > 0:
        time.sleep(sobra)


def _ate(mesa: SimpleNamespace, pronto: Any, prazo_s: float = 3.0) -> None:
    limite = time.monotonic() + prazo_s
    while not pronto():
        assert time.monotonic() < limite, "o pad não nasceu no prazo"
        _tique(mesa)


def _maior_intervalo(tempos: list[float]) -> float:
    return max((b - a for a, b in pairwise(tempos)), default=0.0)


def test_o_p1_recebe_a_entrada_a_cada_tique_enquanto_o_white_nasce(
    mesa: SimpleNamespace,
) -> None:
    # D-1610-O-PAD-VIRTUAL-NASCE-NUM-FIO-PROPRIO
    """Sem intervalo acima de dois tiques na entrada do P1, e o pad do White nasce."""
    for _ in range(3):
        _tique(mesa)
    white = _jogador(mesa, _WHITE, 2)
    _ate(mesa, lambda: white.vpad is not None)
    for _ in range(3):
        _tique(mesa)
    intervalo = _maior_intervalo(mesa.daemon._gamepad_device.entradas)
    assert intervalo <= 2 * _TIQUE_S + 0.02, (
        f"a entrada do P1 parou {intervalo * 1000:.0f} ms enquanto o pad do White nascia")
    assert mesa.pedidos and mesa.pedidos[0][1] != threading.current_thread().name, (
        "o pad nasceu no fio do laço")
    assert mesa.daemon.store.counter("vpad.nascimentos") == 1
    assert mesa.daemon.store.counter("vpad.nascimento_ms") >= int(_NASCIMENTO_S * 1000)


def test_o_pad_pronto_entra_no_tique_seguinte_a_entrega(mesa: SimpleNamespace) -> None:
    """O tique pede e volta; sem tique ninguém instala; o tique seguinte à entrega instala."""
    white = _jogador(mesa, _WHITE, 2)
    _tique(mesa)
    assert white.vpad is None, "o pad nasceu dentro do tique que o pediu"
    limite = time.monotonic() + 3.0
    while _WHITE not in mesa.pads:
        assert time.monotonic() < limite, "o fio não entregou o pad"
        time.sleep(0.01)
    time.sleep(0.05)
    assert white.vpad is None, "o pad entrou sem tique nenhum"
    _tique(mesa)
    assert white.vpad is mesa.pads[_WHITE], "o pad entregue não entrou no tique seguinte"


def test_quem_pediu_antes_e_instalado_antes(mesa: SimpleNamespace) -> None:
    """O White e o Cosmic Red ao mesmo tempo: o White nasce e é instalado antes."""
    for _ in range(3):
        _tique(mesa)
    white = _jogador(mesa, _WHITE, 2)
    red = _jogador(mesa, _COSMIC_RED, 3)
    instalados: list[str] = []
    limite = time.monotonic() + 3.0
    while white.vpad is None or red.vpad is None:
        assert time.monotonic() < limite, "os pads não nasceram no prazo"
        _tique(mesa)
        for jogador in (white, red):
            if jogador.vpad is not None and jogador.identity not in instalados:
                instalados.append(jogador.identity)
    assert [p[0] for p in mesa.pedidos] == [_WHITE, _COSMIC_RED]
    assert instalados == [_WHITE, _COSMIC_RED]
    intervalo = _maior_intervalo(mesa.daemon._gamepad_device.entradas)
    assert intervalo <= 2 * _TIQUE_S + 0.02, intervalo


def test_o_pad_de_quem_saiu_enquanto_nascia_para_e_nao_entra(
    mesa: SimpleNamespace,
) -> None:
    """O Galactic Purple sai no meio do nascimento: o pad dele para e ninguém o instala."""
    if getattr(mesa.daemon, "_fio_de_nascimento", None) is None:
        pytest.fail("sem fio de nascimento no daemon")
    roxo = _jogador(mesa, _GALACTIC_PURPLE, 4)
    _tique(mesa)
    mesa.manager._teardown_player(_GALACTIC_PURPLE)
    limite = time.monotonic() + 3.0
    while _GALACTIC_PURPLE not in mesa.pads or not mesa.pads[_GALACTIC_PURPLE].parado:
        assert time.monotonic() < limite, "o pad de quem saiu ficou de pé"
        _tique(mesa)
    assert roxo.vpad is None


def test_o_nascimento_que_falha_derruba_so_o_jogador_dele(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _falha(flavor: Any, **kwargs: Any) -> None:
        time.sleep(0.05)
        return None

    monkeypatch.setattr(vp, "make_virtual_pad", _falha)
    _jogador(mesa, _WHITE, 2)
    limite = time.monotonic() + 3.0
    while _WHITE in mesa.manager._players:
        assert time.monotonic() < limite, "o jogador do pad que falhou ficou na mesa"
        _tique(mesa)
    assert mesa.daemon._gamepad_device.is_active()


def test_sem_o_fio_a_borda_nasce_na_hora(mesa: SimpleNamespace) -> None:
    """O daemon sem laço (a borda de ligar a emulação) segue nascendo na hora."""
    mesa.daemon._fio_de_nascimento = None
    white = _jogador(mesa, _WHITE, 2)
    mesa.manager._promote_player(white)
    assert white.vpad is mesa.pads[_WHITE]


def test_o_p1_reerguido_no_tique_nasce_pelo_fio(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recriação do P1 no tique: o pad velho sai antes, o novo nasce pelo fio, e o
    White, que já jogava, recebe a entrada a cada tique enquanto isso."""
    white = _jogador(mesa, _WHITE, 2)
    _ate(mesa, lambda: white.vpad is not None)
    pad_do_white = white.vpad
    velho = mesa.daemon._gamepad_device
    for nome in ("_set_controller_grab", "start_motion_reader", "stop_motion_reader",
                 "_materialize_launch_env", "soltar_a_ativacao", "_guardar_o_caminho",
                 "notify_vpad_degradado"):
        monkeypatch.setattr(gp, nome, lambda *a, **k: None)
    monkeypatch.setattr(gp, "read_primary_calibration", lambda _d: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda _d: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda _d: {})
    pad_do_white.forward_buttons = lambda pressed: pad_do_white.entradas.append(  # type: ignore[method-assign]
        time.monotonic())
    mesa.daemon.config.gamepad_emulation_enabled = True
    inicio = time.monotonic()
    mesa.daemon.config.gamepad_flavor = "xbox"
    desfecho = gp.reerguer_o_p1(mesa.daemon, motivo="mascara_reconciliada")
    gasto = time.monotonic() - inicio
    assert desfecho in gp.DESFECHOS_EMULACAO_ATIVA, desfecho
    assert gasto < _NASCIMENTO_S / 2, f"o P1 nasceu no tique ({gasto * 1000:.0f} ms)"
    assert velho.parado, "o pad velho do P1 não saiu antes"
    assert mesa.manager.should_be_active(), "o co-op caiu enquanto o P1 nascia"

    def _o_p1_voltou() -> bool:
        pad_do_white.forward_buttons(frozenset())
        return mesa.daemon._gamepad_device is not None and (
            mesa.daemon._gamepad_device is not velho)

    antes = len(pad_do_white.entradas)
    limite = time.monotonic() + 3.0
    while not _o_p1_voltou():
        assert time.monotonic() < limite, "o P1 não voltou"
        inicio = time.monotonic()
        mesa.manager.forward_all()
        sobra = _TIQUE_S - (time.monotonic() - inicio)
        if sobra > 0:
            time.sleep(sobra)
    assert mesa.daemon._gamepad_device is mesa.pads[_P1]
    assert mesa.pads[_P1].flavor == normalize_flavor("xbox"), "o P1 nasceu sem a máscara pedida"
    assert mesa.daemon.config.gamepad_emulation_enabled
    assert white.vpad is pad_do_white and _WHITE in mesa.manager._players
    intervalo = _maior_intervalo(pad_do_white.entradas[antes:])
    assert intervalo <= 2 * _TIQUE_S + 0.02, intervalo
