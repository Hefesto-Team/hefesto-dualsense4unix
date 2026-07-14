"""FEAT-PROFILE-MODE-01 — seção `mode` do perfil + política do applier.

O perfil do jogo em foco decide o MODO do sistema (nativo/gamepad/desktop +
co-op), fazendo as features coexistirem sem toggles globais brigando. Cobre:
schema, lock manual de 30s, reversão por perfil-sem-opinião, transições entre
kinds e o respeito a gesto manual.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _profile(mode: dict[str, Any] | None) -> Profile:
    data: dict[str, Any] = {
        "name": "teste_modo",
        "version": 1,
        "match": {"type": "any"},
        "priority": 10,
    }
    if mode is not None:
        data["mode"] = mode
    return Profile.model_validate(data)


class _Calls:
    """Captura as chamadas dos setters reais do daemon (política, não efeito)."""

    def __init__(self, daemon: Daemon) -> None:
        self.native: list[tuple[bool, str]] = []
        self.native_restore_stash: list[bool] = []
        self.gamepad: list[tuple[bool, str | None, str]] = []
        self.coop: list[tuple[bool, str]] = []
        self._daemon = daemon

    def bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = self._daemon

        def fake_native(
            enabled: bool,
            *,
            reapply: bool = True,
            restore_stash: bool = False,
            origin: str = "manual",
        ) -> bool:
            self.native.append((enabled, origin))
            # BUG-NATIVE-REVERT-DROPS-STASH-01: registra se a reversão pediu a
            # restauração do stash (gamepad/co-op de antes do jogo).
            self.native_restore_stash.append(restore_stash)
            d._native_mode = enabled
            return enabled

        def fake_gamepad(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> bool:
            self.gamepad.append((enabled, flavor, origin))
            d.config.gamepad_emulation_enabled = enabled
            if enabled:
                dev = type("Vpad", (), {"flavor": flavor or "dualsense"})()
                d._gamepad_device = dev
            else:
                d._gamepad_device = None
            return True

        def fake_coop(enabled: bool, *, origin: str = "manual") -> bool:
            self.coop.append((enabled, origin))
            d.config.coop_enabled = enabled
            return enabled

        monkeypatch.setattr(d, "set_native_mode", fake_native)
        monkeypatch.setattr(d, "set_gamepad_emulation", fake_gamepad)
        monkeypatch.setattr(d, "set_coop_enabled", fake_coop)


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def test_schema_aceita_secao_mode() -> None:
    p = _profile({"kind": "gamepad", "gamepad_flavor": "xbox", "coop": True})
    assert isinstance(p.mode, ProfileModeConfig)
    assert p.mode.kind == "gamepad"
    assert p.mode.gamepad_flavor == "xbox"
    assert p.mode.coop is True
    # Perfil sem a seção continua válido (aditivo ao v1).
    assert _profile(None).mode is None


def test_schema_rejeita_kind_invalido() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile({"kind": "turbo"})


def test_kind_native_liga_o_modo_nativo(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)

    assert calls.native == [(True, "profile")]
    assert daemon._mode_from_profile == "native"


def test_perfil_sem_opiniao_reverte_so_modo_de_perfil(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)
    daemon.apply_profile_mode(None)  # focou um app comum

    assert calls.native == [(True, "profile"), (False, "profile")]
    # BUG-NATIVE-REVERT-DROPS-STASH-01: a reversão por perfil-sem-opinião
    # PRECISA restaurar o stash de emulação (gamepad/co-op de antes do jogo) —
    # sem isso a usuária saía do Sackboy sem gamepad (flagrado ao vivo).
    assert calls.native_restore_stash == [False, True]
    assert daemon._mode_from_profile is None

    # Nativo de origem MANUAL não é revertido por perfil sem opinião.
    daemon._native_mode = True
    daemon._mode_from_profile = None
    calls.native.clear()
    daemon.apply_profile_mode(None)
    assert calls.native == []


def test_kind_gamepad_liga_flavor_e_coop(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(
        _profile({"kind": "gamepad", "gamepad_flavor": "dualsense", "coop": True}).mode
    )

    assert calls.gamepad == [(True, "dualsense", "profile")]
    assert calls.coop == [(True, "profile")]
    assert daemon._mode_from_profile == "gamepad"

    # Re-ativação do MESMO perfil (tick do autoswitch) é idempotente.
    calls.gamepad.clear()
    calls.coop.clear()
    daemon.apply_profile_mode(
        _profile({"kind": "gamepad", "gamepad_flavor": "dualsense", "coop": True}).mode
    )
    assert calls.gamepad == []
    assert calls.coop == []


def test_transicao_native_para_gamepad_desliga_nativo_sem_reapply(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)
    daemon.apply_profile_mode(_profile({"kind": "gamepad", "coop": False}).mode)

    assert calls.native == [(True, "profile"), (False, "profile")]
    assert calls.gamepad[-1][0] is True
    assert daemon._mode_from_profile == "gamepad"


def test_kind_desktop_limpa_tudo_inclusive_manual_expirado(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)
    # Estado manual ANTIGO (lock expirado): gamepad + coop ligados na mão.
    daemon.config.gamepad_emulation_enabled = True
    daemon._gamepad_device = object()
    daemon.config.coop_enabled = True
    daemon._emu_manual_ts = float("-inf")

    daemon.apply_profile_mode(_profile({"kind": "desktop"}).mode)

    assert calls.coop == [(False, "profile")]
    assert calls.gamepad == [(False, None, "profile")]
    assert daemon._mode_from_profile is None


def test_lock_manual_congela_o_perfil(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)
    daemon._emu_manual_ts = time.monotonic()  # gesto manual AGORA

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)
    daemon.apply_profile_mode(None)

    assert calls.native == []
    assert calls.gamepad == []
    assert calls.coop == []


def test_manager_repassa_mode_ao_applier() -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    received: list[Any] = []
    mgr = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        mode_applier=received.append,
    )
    mgr.apply_emulation(_profile({"kind": "native"}))
    mgr.apply_emulation(_profile(None))

    assert len(received) == 2
    assert received[0] is not None and received[0].kind == "native"
    assert received[1] is None
