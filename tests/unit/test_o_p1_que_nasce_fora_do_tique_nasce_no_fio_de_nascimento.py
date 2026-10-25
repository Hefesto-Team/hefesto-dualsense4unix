"""O-P1-QUE-NASCE-FORA-DO-TIQUE-NASCE-NO-FIO-DE-NASCIMENTO-01 — todo P1 nasce no fio.

O `Daemon` REAL, com o `CoopManager` real, o fio de nascimento do daemon
(`virtual_pad.FioDeNascimento`) e o broker de mentira que leva 2 s para responder ao
pedido do P1 (o teto do cliente, `hidraw_broker_client._TIMEOUT_S`). O laço do tique é
emulado a 60 Hz na thread do teste: a cada volta, o `forward_all` dos secundários, o
`fechar_o_p1_que_nasceu` que o `_poll_loop` roda depois dele, e a entrada do White.

Os cinco caminhos que sobem o P1 fora do `reerguer_o_p1` (o passo `coop_gamepad`, o
PS + R3, a troca de roupa, a saída do Modo Nativo e a IPC) voltam na hora, o White
recebe a entrada a cada volta enquanto o P1 nasce, e o P1 nasce quando a resposta chega.
A IPC responde o desfecho de verdade, depois de o pad existir.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Iterator
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM, ROUPA_PADRAO
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
# a importação fria do loader (o `_devolver_as_tabelas_do_perfil`) não é custo do tique
from hefesto_dualsense4unix.profiles import loader as _loader  # noqa: F401
from hefesto_dualsense4unix.testing import FakeController

_P1 = "aabbcc000001"
_WHITE = "aabbcc000002"
_CALIB = bytes([0x05]) + bytes([0xAB]) * 40
_BROKER_S = 2.0
_TIQUE_S = 1.0 / 60.0
#: o caminho que sobe o P1 volta antes disto; com o `start` no laço, ele leva os 2 s do broker
_NA_HORA_S = _BROKER_S / 4
#: o maior buraco na entrada do White enquanto o P1 nasce: dois tiques e a folga da máquina
_BURACO_S = 2 * _TIQUE_S + 0.05


class _Pad:
    """O pad de mentira: anota quando recebe entrada e quando para."""

    def __init__(self, identity: str | None, flavor: Any, caminho: Any, roupa: Any) -> None:
        self.identity = identity
        self.flavor = flavor
        self.backend = "uhid"
        self.caminho = caminho
        self.product = ROUPA_PADRAO if roupa is None else roupa
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


class _Ipc(IpcHandlersMixin):  # type: ignore[misc]
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon


@pytest.fixture
def mesa(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(prr, "PhysicalReportReader", lambda **_k: None)
    for nome in ("_materialize_launch_env", "_broker_hide_player",
                 "_start_player_motion_reader", "_armar_sossego_do_launch_env"):
        monkeypatch.setattr(coop_mod.CoopManager, nome, lambda self, *a, **k: None)
    for nome in ("_set_controller_grab", "start_motion_reader", "stop_motion_reader",
                 "_materialize_launch_env", "soltar_a_ativacao", "notify_vpad_degradado"):
        monkeypatch.setattr(gp, nome, lambda *a, **k: None)
    monkeypatch.setattr(gp, "read_primary_calibration", lambda _d: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    # o jogo em foco se lê das janelas e dos atalhos da máquina: fora da mesa de mentira
    monkeypatch.setattr(gp, "_ha_jogo_em_foco", lambda _d: False)
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda _d: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda _d: {})
    estado = SimpleNamespace(falhar=False, pedidos=[], pads={})

    def _fabrica(flavor: Any, **kwargs: Any) -> _Pad | None:
        """A fábrica do pad: o do P1 espera o broker de mentira (2 s); o do White, não."""
        identidade = kwargs.get("identity")
        if identidade is None:
            estado.pedidos.append(threading.current_thread().name)
            time.sleep(_BROKER_S)
            if estado.falhar:
                return None
        pad = _Pad(identidade, flavor, kwargs.get("caminho"), kwargs.get("roupa"))
        estado.pads[str(identidade)] = pad
        return pad

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    daemon = Daemon(controller=FakeController())
    daemon.config.coop_enabled = True
    daemon._fio_de_nascimento = vp.FioDeNascimento()
    gravados: list[tuple[str, Any]] = []
    monkeypatch.setattr(daemon, "gravar_o_modo_escolhido", lambda modo, **_k: gravados.append(
        (modo, daemon._gamepad_device)))
    manager = coop_mod.get_coop_manager(daemon)
    coop_mod.calibration_cache(daemon)[_WHITE] = _CALIB
    white = coop_mod._SecondaryPlayer(
        identity=_WHITE, evdev_path="/dev/input/event92", reader=_Leitor(), player_index=2,
    )
    manager._players[_WHITE] = white
    m = SimpleNamespace(daemon=daemon, manager=manager, white=white, gravados=gravados,
                        estado=estado)
    _ate(m, lambda: white.vpad is not None)
    yield m
    daemon._fio_de_nascimento.parar()


def _fechar(daemon: Any) -> None:
    """O passo do `_poll_loop` depois do `forward_all` (ausente na medida de antes)."""
    fechar = getattr(gp, "fechar_o_p1_que_nasceu", None)
    if fechar is not None:
        fechar(daemon)


def _tique(m: SimpleNamespace) -> None:
    """Uma volta do laço, na ordem do `_poll_loop`: os secundários e o que nasceu."""
    inicio = time.monotonic()
    m.manager.forward_all()
    _fechar(m.daemon)
    if m.white.vpad is not None:
        m.white.vpad.forward_buttons(frozenset())
    sobra = _TIQUE_S - (time.monotonic() - inicio)
    if sobra > 0:
        time.sleep(sobra)


def _ate(m: SimpleNamespace, pronto: Callable[[], bool], prazo_s: float = 4 * _BROKER_S) -> None:
    limite = time.monotonic() + prazo_s
    while not pronto():
        assert time.monotonic() < limite, "o pad não nasceu no prazo"
        _tique(m)


def _o_p1_vivo(m: SimpleNamespace, velho: Any = None) -> Any:
    """O pad do P1 que o broker de mentira entregou, já instalado no daemon."""
    novo = m.estado.pads.get("None")
    atual = m.daemon._gamepad_device
    return atual if atual is not None and atual is novo and atual is not velho else None


def _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
    m: SimpleNamespace, gesto: Callable[[], Any], *, velho: Any = None,
) -> Any:
    """O caminho volta na hora, o White joga a cada tique, e o P1 nasce quando o broker
    responde. Devolve o que o gesto devolveu."""
    inicio = time.monotonic()
    devolvido = gesto()
    gasto = time.monotonic() - inicio
    assert gasto < _NA_HORA_S, f"o P1 nasceu no laço do tique ({gasto * 1000:.0f} ms)"
    antes = len(m.white.vpad.entradas)
    _ate(m, lambda: _o_p1_vivo(m, velho) is not None)
    assert len(m.estado.pedidos) == 1, m.estado.pedidos
    assert m.estado.pedidos[0] == "hefesto-nascimento-do-pad", "o P1 não nasceu no fio"
    buraco = max((b - a for a, b in pairwise(m.white.vpad.entradas[antes:])), default=0.0)
    assert buraco <= _BURACO_S, f"o White parou {buraco * 1000:.0f} ms enquanto o P1 nascia"
    assert m.daemon.config.gamepad_emulation_enabled
    return devolvido


# --- os cinco caminhos ---------------------------------------------------------------------


def test_o_segundo_controle_que_chega_liga_a_emulacao_pelo_fio(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O passo `coop_gamepad`: dois controles na mão, a emulação desligada."""
    monkeypatch.setattr(mesa.daemon, "contar_controles_fisicos", lambda: 2)
    mesa.daemon._gamepad_device = None
    estado = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, mesa.daemon.aplicar_gamepad_para_multiplos_controles)
    assert estado == "aplicado"


def test_o_passo_que_se_repete_enquanto_o_p1_nasce_nao_pede_outro(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O relógio da identidade volta antes de o broker responder: o pedido em voo vale."""
    monkeypatch.setattr(mesa.daemon, "contar_controles_fisicos", lambda: 2)
    mesa.daemon._gamepad_device = None

    def _duas_vezes() -> None:
        mesa.daemon.aplicar_gamepad_para_multiplos_controles()
        _tique(mesa)
        mesa.daemon.aplicar_gamepad_para_multiplos_controles()

    _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(mesa, _duas_vezes)


def test_o_ps_r3_troca_a_ponte_pelo_fio_e_grava_o_modo_depois_do_pad(
    mesa: SimpleNamespace,
) -> None:
    velho = _Pad(None, "dualsense", vp.CAMINHO_DUALSENSE, ROUPA_PADRAO)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    de_pe = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: hotkey._aplicar_ponte(mesa.daemon, hotkey.PONTE_XBOX), velho=velho)
    assert de_pe is True
    assert velho.parado
    novo = _o_p1_vivo(mesa, velho)
    assert novo.caminho == vp.CAMINHO_XBOX, "o P1 nasceu sem o caminho pedido"
    assert mesa.gravados == [("gamepad", novo)], (
        "o modo se grava depois de o pad existir, uma vez", mesa.gravados)


def test_a_troca_de_roupa_recria_o_p1_pelo_fio(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O broker esconde o físico, e a roupa pedida vale; os secundários são do co-op."""
    monkeypatch.setattr(gp, "_o_fisico_esta_exposto", lambda _d: False)
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    monkeypatch.setattr(coop_mod.CoopManager, "vestir_a_roupa", lambda self: [])
    velho = _Pad(None, normalize_flavor("dualsense"), vp.CAMINHO_DUALSENSE, ROUPA_PADRAO)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    vestem = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: gp.vestir_a_roupa(mesa.daemon, ROUPA_COMUM), velho=velho)
    assert "p1" in vestem, "o P1 que nasce na roupa pedida conta como quem a veste"
    assert _o_p1_vivo(mesa, velho).product == ROUPA_COMUM


def test_a_saida_do_modo_nativo_devolve_o_p1_pelo_fio(mesa: SimpleNamespace) -> None:
    mesa.daemon._gamepad_device = None
    mesa.daemon._native_mode = True
    mesa.daemon._native_emu_stash = {"gamepad": [True, "dualsense"], "mouse": [False, None, None]}
    _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: mesa.daemon.set_native_mode(
            False, origin="manual", reapply=False, restore_stash=True))
    assert not mesa.daemon.is_native_mode()


def _ipc_com_o_laco_no_ar(m: SimpleNamespace, params: dict[str, Any]) -> tuple[Any, float]:
    """O pedido pela IPC no mesmo laço do asyncio que roda o tique, como no daemon."""

    async def _correr() -> tuple[Any, float]:
        parar = asyncio.Event()

        async def _laco() -> None:
            while not parar.is_set():
                _tique_sem_dormir(m)
                await asyncio.sleep(_TIQUE_S)

        laco = asyncio.create_task(_laco())
        await asyncio.sleep(_TIQUE_S)
        inicio = time.monotonic()
        try:
            resposta = await _Ipc(m.daemon)._handle_gamepad_emulation_set(params)
        finally:
            gasto = time.monotonic() - inicio
            parar.set()
            await laco
        return resposta, gasto

    return asyncio.run(_correr())


def _tique_sem_dormir(m: SimpleNamespace) -> None:
    m.manager.forward_all()
    _fechar(m.daemon)
    if m.white.vpad is not None:
        m.white.vpad.forward_buttons(frozenset())


def test_a_ipc_liga_pelo_fio_e_responde_depois_do_pad_existir(mesa: SimpleNamespace) -> None:
    mesa.daemon._gamepad_device = None
    antes = len(mesa.white.vpad.entradas)
    resposta, gasto = _ipc_com_o_laco_no_ar(
        mesa, {"enabled": True, "caminho": "xbox", "origin": "manual"})
    assert mesa.estado.pedidos == ["hefesto-nascimento-do-pad"], "o P1 não nasceu no fio"
    buraco = max((b - a for a, b in pairwise(mesa.white.vpad.entradas[antes:])), default=0.0)
    assert buraco <= _BURACO_S + _TIQUE_S, (
        f"o White parou {buraco * 1000:.0f} ms enquanto a IPC esperava o P1")
    assert gasto >= _BROKER_S, "a IPC respondeu antes de o pad existir"
    assert resposta["status"] == "ok" and resposta["enabled"] is True, resposta
    assert resposta["caminho"] == vp.CAMINHO_XBOX, resposta
    assert _o_p1_vivo(mesa) is not None


def test_a_ipc_diz_falhou_quando_o_pad_nao_nasce(mesa: SimpleNamespace) -> None:
    """O desfecho de verdade: o broker respondeu sem pad, e a IPC não diz «ok»."""
    mesa.daemon._gamepad_device = None
    mesa.estado.falhar = True
    resposta, _gasto = _ipc_com_o_laco_no_ar(mesa, {"enabled": True, "origin": "manual"})
    assert resposta["status"] == "failed" and resposta["enabled"] is False, resposta
    assert mesa.daemon._gamepad_device is None
    assert mesa.gravados == [], "o modo que não ficou de pé não se grava"


def test_fora_do_laco_a_borda_nasce_na_hora(mesa: SimpleNamespace) -> None:
    """Fora do fio do laço (a borda, um executor), o P1 nasce na hora, como antes."""
    mesa.daemon._gamepad_device = None
    feito: list[Any] = []
    fio = threading.Thread(target=lambda: feito.append(mesa.daemon.set_gamepad_emulation(
        True, origin="profile")))
    fio.start()
    fio.join(timeout=4 * _BROKER_S)
    assert feito == [True]
    assert mesa.estado.pedidos == [fio.name]
    assert mesa.daemon._gamepad_device is mesa.estado.pads["None"]
