"""FEAT-RUMBLE-POLICY-PROFILE-01 — política de rumble persistível no perfil."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.profiles.schema import Profile, RumbleConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _profile(rumble: dict[str, Any] | None) -> Profile:
    data: dict[str, Any] = {
        "name": "teste_rumble",
        "version": 1,
        "match": {"type": "any"},
        "priority": 10,
    }
    if rumble is not None:
        data["rumble"] = rumble
    return Profile.model_validate(data)


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def test_schema_aceita_policy_e_custom_mult() -> None:
    p = _profile({"policy": "custom", "custom_mult": 0.75})
    assert isinstance(p.rumble, RumbleConfig)
    assert p.rumble.policy == "custom"
    assert p.rumble.custom_mult == pytest.approx(0.75)
    legado = _profile({"passthrough": False})
    assert legado.rumble.policy is None
    assert legado.rumble.custom_mult is None
    assert legado.rumble.passthrough is False
    assert _profile(None).rumble.policy is None


def test_schema_rejeita_policy_invalida() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile({"policy": "turbo"})


def test_schema_rejeita_custom_mult_fora_do_range() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile({"policy": "custom", "custom_mult": 2.5})
    with pytest.raises(ValidationError):
        _profile({"policy": "custom", "custom_mult": -0.1})


def test_schema_rejeita_custom_mult_sem_policy_custom() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile({"policy": "max", "custom_mult": 0.5})
    with pytest.raises(ValidationError):
        _profile({"custom_mult": 0.5})


def test_applier_aplica_politica_do_perfil(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("max", None)

    assert daemon.config.rumble_policy == "max"
    assert daemon._rumble_policy_from_profile is True
    assert daemon._rumble_policy_before_profile == ("balanceado", 0.7)


def test_applier_custom_aplica_mult(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("custom", 0.4)

    assert daemon.config.rumble_policy == "custom"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.4)


def test_perfil_sem_opiniao_reverte_so_politica_de_perfil(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("max", None)
    daemon.apply_profile_rumble_policy(None, None)

    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._rumble_policy_from_profile is False
    assert daemon._rumble_policy_before_profile is None

    daemon.config.rumble_policy = "economia"
    daemon.apply_profile_rumble_policy(None, None)
    assert daemon.config.rumble_policy == "economia"


def test_reversao_volta_a_politica_pre_perfil_em_cadeia(daemon: Daemon) -> None:
    """Perfil A → perfil B → sem-opinião volta à política PRÉ-A (não à de A)."""
    daemon.config.rumble_policy = "economia"
    daemon.apply_profile_rumble_policy("max", None)
    daemon.apply_profile_rumble_policy("custom", 0.5)
    daemon.apply_profile_rumble_policy(None, None)

    assert daemon.config.rumble_policy == "economia"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.7)
    assert daemon._rumble_policy_from_profile is False


def test_lock_manual_congela_o_perfil(daemon: Daemon) -> None:
    daemon._emu_manual_ts = time.monotonic()

    daemon.apply_profile_rumble_policy("max", None)
    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._rumble_policy_from_profile is False

    daemon._emu_manual_ts = float("-inf")
    daemon.apply_profile_rumble_policy("max", None)
    daemon._emu_manual_ts = time.monotonic()
    daemon.apply_profile_rumble_policy(None, None)
    assert daemon.config.rumble_policy == "max"


def test_politica_invalida_no_applier_e_ignorada(daemon: Daemon) -> None:
    """Defensivo: o schema já barra, mas o applier é público — não corrompe."""
    daemon.apply_profile_rumble_policy("turbo", None)

    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._rumble_policy_from_profile is False


def test_applier_reaplica_rumble_ativo(daemon: Daemon) -> None:
    """Com rumble fixado (rumble_active), a nova política re-escala na hora."""
    daemon.config.rumble_active = (100, 200)
    daemon.apply_profile_rumble_policy("economia", None)

    ctrl = daemon.controller
    rumbles = [c for c in ctrl.commands if c.kind == "set_rumble"]  # type: ignore[attr-defined]
    assert rumbles, "política aplicada deve re-afirmar o rumble ativo"
    assert rumbles[-1].payload == (30, 60)


def test_gesto_manual_ipc_carimba_lock_e_limpa_origem(daemon: Daemon) -> None:
    """rumble.policy_set/policy_custom são gesto MANUAL: carimbam o lock de 30s."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=object(),
        daemon=daemon,
    )
    daemon.apply_profile_rumble_policy("max", None)

    asyncio.run(server._handle_rumble_policy_set({"policy": "economia"}))

    assert daemon.config.rumble_policy == "economia"
    assert daemon._rumble_policy_from_profile is False
    assert daemon._rumble_policy_before_profile is None
    assert time.monotonic() - daemon._emu_manual_ts < 5.0
    daemon.apply_profile_rumble_policy("max", None)
    assert daemon.config.rumble_policy == "economia"

    asyncio.run(server._handle_rumble_policy_custom({"mult": 0.4}))
    assert daemon.config.rumble_policy == "custom"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.4)
    assert daemon._rumble_policy_from_profile is False


def test_cenario_journal_policy_max_reporta_o_mult_da_politica(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cenário exato do journal 2026-07-18 19:59:48: perfil `vitoria` com
    `rumble.policy=max` ativado em passthrough ocioso. O log dizia
    `profile_rumble_policy_applied mult=0.7 policy=max` (o campo carregava o
    custom_mult default) e o state_full expunha `rumble_mult_applied=0.7`
    (`_last_auto_mult` nunca sincronizado em política fixa). O mult do Máximo
    tem de aparecer nos dois lugares."""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod

    spy = MagicMock()
    monkeypatch.setattr(lifecycle_mod, "logger", spy)

    daemon.config.rumble_active = None
    daemon.apply_profile_rumble_policy("max", None)

    # Fonte do `rumble_mult_applied` do state_full.
    assert daemon._last_auto_mult == pytest.approx(RUMBLE_POLICY_MULT["max"])

    aplicados = [
        c
        for c in spy.info.call_args_list
        if c[0][0] == "profile_rumble_policy_applied"
    ]
    assert len(aplicados) == 1
    assert aplicados[0].kwargs["policy"] == "max"
    assert aplicados[0].kwargs["mult"] == pytest.approx(RUMBLE_POLICY_MULT["max"])


def test_state_full_reporta_o_mult_da_politica_com_policy_max(
    daemon: Daemon,
) -> None:
    """A evidência do state_full ao vivo (`rumble_policy=max` +
    `rumble_mult_applied=0.7`) vira regressão de ponta a ponta."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    daemon.apply_profile_rumble_policy("max", None)

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=object(),
        daemon=daemon,
    )
    result = asyncio.run(server._handle_daemon_state_full({}))
    assert result["rumble_policy"] == "max"
    assert result["rumble_mult_applied"] == pytest.approx(
        RUMBLE_POLICY_MULT["max"]
    )


def test_seed_observavel_custom_e_reversao(daemon: Daemon) -> None:
    """Custom seeda o mult observável com o custom_mult; perfil sem opinião"""
    daemon.apply_profile_rumble_policy("custom", 0.4)
    assert daemon._last_auto_mult == pytest.approx(0.4)

    daemon.apply_profile_rumble_policy(None, None)
    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._last_auto_mult == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])


def test_manager_repassa_politica_ao_applier() -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    received: list[tuple[str | None, float | None]] = []
    quem_mandou: list[str | None] = []

    def applier(
        policy: str | None,
        custom_mult: float | None,
        *,
        profile: object | None = None,
        origin: str = "autoswitch",
    ) -> None:
        # ativação — "manual" (profile.switch/hotkey) fura o lock de gesto
        received.append((policy, custom_mult))
        quem_mandou.append(getattr(profile, "name", None))

    mgr = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_policy_applier=applier,
    )
    mgr.apply_emulation(_profile({"policy": "custom", "custom_mult": 0.5}))
    mgr.apply_emulation(_profile(None))

    assert received == [("custom", 0.5), (None, None)]
    assert quem_mandou == ["teste_rumble", "teste_rumble"]


def test_applier_passthrough_solta_rumble_fixado(daemon: Daemon) -> None:
    daemon.config.rumble_active = (100, 120)
    daemon.apply_profile_rumble_passthrough(True)
    assert daemon.config.rumble_active is None


def test_applier_passthrough_false_preserva_rumble_fixado(daemon: Daemon) -> None:
    daemon.config.rumble_active = (100, 120)
    daemon.apply_profile_rumble_passthrough(False)
    assert daemon.config.rumble_active == (100, 120)


def test_applier_passthrough_preserva_silencio_deliberado(daemon: Daemon) -> None:
    daemon.config.rumble_active = (0, 0)
    daemon.apply_profile_rumble_passthrough(True)
    assert daemon.config.rumble_active == (0, 0)


def test_applier_passthrough_noop_quando_ja_em_passthrough(daemon: Daemon) -> None:
    daemon.config.rumble_active = None
    daemon.apply_profile_rumble_passthrough(True)
    assert daemon.config.rumble_active is None


def test_manager_repassa_passthrough_ao_applier() -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    received: list[bool] = []
    mgr = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_passthrough_applier=received.append,
    )
    mgr.apply_emulation(_profile({"passthrough": True}))
    mgr.apply_emulation(_profile({"passthrough": False}))
    mgr.apply_emulation(_profile(None))
    assert received == [True, False, True]


def test_roundtrip_draft_profile_draft_com_politica() -> None:
    original = _profile(
        {"policy": "custom", "custom_mult": 0.5, "passthrough": False}
    )
    draft = DraftConfig.from_profile(original)
    assert draft.rumble.policy == "custom"
    assert draft.rumble.custom_mult == pytest.approx(0.5)
    assert draft.rumble.passthrough is False

    salvo = draft.to_profile("teste_rumble", priority=10)
    assert salvo.rumble.policy == "custom"
    assert salvo.rumble.custom_mult == pytest.approx(0.5)
    assert salvo.rumble.passthrough is False

    de_volta = DraftConfig.from_profile(salvo)
    assert de_volta.rumble == draft.rumble


def test_roundtrip_perfil_sem_opiniao_continua_sem_opiniao() -> None:
    """Salvar um perfil sem política NÃO inventa opinião (policy=None persiste)."""
    draft = DraftConfig.from_profile(_profile(None))
    assert draft.rumble.policy is None

    salvo = draft.to_profile("teste_rumble", priority=10)
    assert salvo.rumble.policy is None
    assert salvo.rumble.custom_mult is None
    assert salvo.rumble.passthrough is True
