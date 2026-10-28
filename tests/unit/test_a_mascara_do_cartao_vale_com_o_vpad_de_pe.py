"""MODO-DE-CONEXAO-01 — a máscara do cartão vale com o vpad de pé e o jogo aberto.

A regra, 13/09/2026, está citada na sprint: *"eles precisam funcionar
durante o jogo"*. O estudo mediu que o `gamepad.mask.set` gravava o registro e o
perfil e **não recriava o vpad**: o cartão acendia «Xbox 360» e o jogo seguia
recebendo o DualSense, e reativar o perfil também não recriava. O §D.6 decidiu:
depois de gravar, o daemon recria o vpad DAQUELE controle com origem manual — o
P1 por `start_gamepad_emulation_desfecho`, os outros pelo ciclo forçado do
co-op. O ato mora em `Daemon.vestir_a_mascara_do_aparelho`; o handler só o chama.

A bancada junta as duas de antes: os métodos REAIS do `lifecycle.Daemon` (a do
`test_o_modo_nao_escreve_a_mascara.py`) e um `CoopManager` REAL com o P2 e o P3
na mesa (a do `test_mascara_por_controle_manda_no_vpad.py`). Dublados só o vpad,
o reader evdev, a descoberta de `/dev/input`, o sysfs de LED, o grab, o launch
env e as flags de sessão. `display_authority="game"`: o jogo está aberto.

NOTA DATADA, 27/10/2026 (O-MODO-UNICO-VALE-PARA-TODOS-OS-CONTROLES-01): a máscara é o
modo único, e o `gamepad.mask.set` de QUALQUER cartão leva os três controles ao modo novo,
com o jogo aberto, pelo escritor único `Daemon.escolher_o_modo_unico`, que grava o par
(caminho, máscara) no perfil ativo.

MORDE: troque, no handler, o `escolher_o_modo_unico` pelo `set_gamepad_emulation` sem o
caminho — o P2 e o P3 ficam no canal de antes; ou devolva o degrau por identidade à
`mascara_efetiva` — o vpad nasce na máscara velha.
"""
from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile, ProfileModeConfig
from hefesto_dualsense4unix.utils import session, xdg_paths

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
PERFIL = "Bancada"


class _Vpad:
    """O vpad de mentira. Conta as criações; o canal sai de `quer_uhid`."""

    criados: ClassVar[list[_Vpad]] = []

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))
        self.parado = False
        type(self).criados.append(self)

    def stop(self) -> None:
        self.parado = True

    def forward_analog(self, **_kw: int) -> None:
        return

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        return

    def pump_ff(self) -> None:
        return


def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
    return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)


def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
    if daemon._gamepad_device is not None:
        daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False


class _Reader:
    """Reader evdev de mentira (o mesmo contrato do dublê do co-op)."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return

    def snapshot(self) -> Any:
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self, sessao: str) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor=sessao,
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
            coop_enabled=True,
            rumble_active=(0, 0),
        )
        self.controller = SimpleNamespace(primary_uniq=P1)
        self._gamepad_device: Any = None
        self._mouse_device = None
        self._coop_manager: Any = None
        self.store = None
        self._emu_lock = threading.Lock()
        self._native_mode = False
        self._emu_manual_ts = 0.0
        self._mode_from_profile = None
        self.display_authority = "unknown"
        self._devolver_as_tabelas_do_perfil = lambda: None
        for nome in (
            "set_gamepad_emulation",
            "set_gamepad_emulation_desfecho",
            "escolher_o_modo_unico",
            "gravar_o_modo_escolhido",
        ):
            setattr(self, nome, functools.partial(getattr(lifecycle.Daemon, nome), self))

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def _esquecer_mascara_adiada(self, _m: Any) -> None:
        return

    def set_mouse_emulation(self, enabled: bool, *_a: Any, **_kw: Any) -> bool:
        return bool(enabled)


class _Handlers(ih.IpcHandlersMixin):
    """O mixin REAL do IPC, com o perfil ativo que o daemon sabe."""

    def __init__(self, daemon: _Daemon) -> None:
        self.store = SimpleNamespace(active_profile=PERFIL)  # type: ignore[assignment]
        self.controller = SimpleNamespace(describe_controllers=lambda: [])  # type: ignore[assignment]
        self.daemon = daemon  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _Vpad.criados = []
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: False,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda ativo, flavor=None: None)
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda caminho, *, origem=None: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Reader)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {P1: "/dev/input/event90", P2: "/dev/input/event91", P3: "/dev/input/event92"},
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    monkeypatch.setattr(CoopManager, "_calibration_pronta", lambda self, identity: (True, None))
    (xdg_paths.config_dir(ensure=True) / em.ARQUIVO_DE_MASCARAS_DE_ANTES).unlink(missing_ok=True)
    yield


def _mesa_com_o_jogo_aberto() -> _Daemon:
    """P1 com o vpad de pé, P2 e P3 no co-op, todos em DualSense — e o jogo aberto."""
    loader.save_profile(
        Profile(
            name=PERFIL,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        ),
        origem="teste",
    )
    d = _Daemon("dualsense")
    d.store = SimpleNamespace(active_profile=PERFIL)
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO
    d._coop_manager = CoopManager(d)  # type: ignore[arg-type]
    d._coop_manager.sync(force=True)
    d.display_authority = "game"
    return d


def _vpad_do(identity: str) -> _Vpad:
    vivos = [v for v in _Vpad.criados if v.identity == identity and not v.parado]
    assert len(vivos) == 1, f"{identity}: {len(vivos)} vpads de pé"
    return vivos[0]


def _cartao(d: _Daemon, uniq: str, mascara: str) -> dict[str, Any]:
    """O chip do cartão: `gamepad.mask.set {uniq, flavor}` pelo handler REAL."""
    return asyncio.run(
        ih.IpcHandlersMixin._handle_gamepad_mask_set(
            _Handlers(d), {"uniq": uniq, "flavor": mascara}
        )
    )


@pytest.mark.parametrize("quem", [P1, P2, P3, None])
def test_o_cartao_de_qualquer_controle_leva_os_tres_ao_modo_novo(quem: str | None) -> None:
    d = _mesa_com_o_jogo_aberto()
    antes = [d._gamepad_device, _vpad_do(P2), _vpad_do(P3)]
    assert [v.flavor for v in antes] == ["dualsense"] * 3, "premissa"

    params = {"flavor": "xbox"} if quem is None else {"uniq": quem, "flavor": "xbox"}
    resposta = asyncio.run(ih.IpcHandlersMixin._handle_gamepad_mask_set(_Handlers(d), params))

    assert resposta["status"] == "ok", resposta
    assert all(v.parado for v in antes), (
        "o modo único mudou e um vpad ficou de pé na máscara velha, com o jogo aberto"
    )
    agora = [d._gamepad_device, _vpad_do(P2), _vpad_do(P3)]
    assert [(v.flavor, v.backend) for v in agora] == [("xbox", "uinput")] * 3
    assert (d.config.gamepad_flavor, d.config.gamepad_caminho) == ("xbox", "xbox")
    modo = loader.load_profile(PERFIL).mode
    assert (modo.caminho, modo.gamepad_flavor) == ("xbox", "xbox"), "o par não foi ao perfil"


@pytest.mark.parametrize("flavor", ["", "wiimote", None])
def test_o_modo_vazio_ou_desconhecido_e_recusado(flavor: str | None) -> None:
    d = _mesa_com_o_jogo_aberto()
    with pytest.raises(ValueError, match="modo desconhecido"):
        asyncio.run(
            ih.IpcHandlersMixin._handle_gamepad_mask_set(_Handlers(d), {"flavor": flavor})
        )
    assert d.config.gamepad_flavor == "dualsense"


def test_o_nintendo_pro_sobe_sem_caminho_para_os_tres() -> None:
    d = _mesa_com_o_jogo_aberto()

    asyncio.run(ih.IpcHandlersMixin._handle_gamepad_mask_set(_Handlers(d), {"flavor": "nintendo"}))

    agora = [d._gamepad_device, _vpad_do(P2), _vpad_do(P3)]
    assert [(v.flavor, v.backend) for v in agora] == [("nintendo", "uinput")] * 3
    modo = loader.load_profile(PERFIL).mode
    assert (modo.caminho, modo.gamepad_flavor) == (None, "nintendo")
