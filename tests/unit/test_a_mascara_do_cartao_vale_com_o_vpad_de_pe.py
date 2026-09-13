"""MODO-DE-CONEXAO-01 — a máscara do cartão vale com o vpad de pé e o jogo aberto.

A regra dela, 13/09/2026, está citada na sprint: *"eles precisam funcionar
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

MORDE: tirar do `_handle_gamepad_mask_set` a chamada `_vestir_a_mascara_na_hora`
— o registro e o perfil gravam, e nenhum vpad é recriado.
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

#: A faixa sintética da casa — nada de endereço real em arquivo versionado.
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
        for nome in (
            "set_gamepad_emulation",
            "set_gamepad_emulation_desfecho",
            "vestir_a_mascara_do_aparelho",
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
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda caminho: None)
    # O co-op REAL, sem /dev/input: as bordas do `test_mascara_por_controle_manda_no_vpad`.
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
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    yield
    em._zerar_registro_de_mascaras()


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


def test_o_cartao_do_p1_em_xbox_360_recria_o_vpad_dele_com_o_jogo_aberto() -> None:
    d = _mesa_com_o_jogo_aberto()
    p1_antes = d._gamepad_device
    p2_antes, p3_antes = _vpad_do(P2), _vpad_do(P3)
    assert (p1_antes.flavor, p2_antes.flavor, p3_antes.flavor) == ("dualsense",) * 3

    resposta = _cartao(d, P1, "xbox")

    vivo = d._gamepad_device
    assert vivo is not p1_antes and p1_antes.parado, (
        "o cartão gravou e o vpad do P1 continuou o mesmo — o jogo segue vendo o "
        f"DualSense com o cartão aceso em Xbox 360. Resposta: {resposta}"
    )
    assert vivo.flavor == "xbox", "o vpad recriado não veste a máscara do cartão"
    assert resposta["vestiu"] == gp.EMU_APLICADO
    assert not p2_antes.parado and not p3_antes.parado, "o cartão do P1 recriou um secundário"
    assert d.config.gamepad_flavor == "dualsense", "o cartão trocou a máscara da sessão"


def test_o_cartao_do_p2_recria_so_o_p2_pelo_ciclo_forcado_do_coop() -> None:
    d = _mesa_com_o_jogo_aberto()
    p1_antes = d._gamepad_device
    p2_antes, p3_antes = _vpad_do(P2), _vpad_do(P3)

    resposta = _cartao(d, P2, "xbox")

    assert resposta["vestiu"] == "coop"
    assert p2_antes.parado, (
        "o cartão do P2 gravou e o vpad dele não foi recriado — o ciclo forçado "
        f"do co-op não rodou. Resposta: {resposta}"
    )
    assert _vpad_do(P2).flavor == "xbox"
    assert d._gamepad_device is p1_antes and not p1_antes.parado, "recriou o P1"
    assert _vpad_do(P3) is p3_antes, "recriou o P3, que não escolheu nada"
