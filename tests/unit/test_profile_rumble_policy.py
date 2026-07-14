"""FEAT-RUMBLE-POLICY-PROFILE-01 — política de rumble persistível no perfil.

A política de intensidade (economia/balanceado/max/auto/custom) passa a morar
na seção `rumble` do perfil e é aplicada na ativação, em paridade com a seção
`mode`: lock manual de 30s, reversão por perfil-sem-opinião (volta à política
vigente antes de o perfil mexer), repasse pelo ProfileManager e round-trip
draft→profile→draft.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
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


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_schema_aceita_policy_e_custom_mult() -> None:
    p = _profile({"policy": "custom", "custom_mult": 1.5})
    assert isinstance(p.rumble, RumbleConfig)
    assert p.rumble.policy == "custom"
    assert p.rumble.custom_mult == pytest.approx(1.5)
    # Perfil v1 (só passthrough) continua válido — aditivo, sem opinião.
    legado = _profile({"passthrough": False})
    assert legado.rumble.policy is None
    assert legado.rumble.custom_mult is None
    assert legado.rumble.passthrough is False
    # Perfil sem a seção idem.
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

    # custom_mult só faz sentido com policy="custom" — o valor seria
    # silenciosamente ignorado; o schema rejeita cedo.
    with pytest.raises(ValidationError):
        _profile({"policy": "max", "custom_mult": 0.5})
    with pytest.raises(ValidationError):
        _profile({"custom_mult": 0.5})


# ---------------------------------------------------------------------------
# Applier (Daemon.apply_profile_rumble_policy)
# ---------------------------------------------------------------------------


def test_applier_aplica_politica_do_perfil(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("max", None)

    assert daemon.config.rumble_policy == "max"
    assert daemon._rumble_policy_from_profile is True
    # A política anterior (default balanceado/0.7) fica guardada p/ reversão.
    assert daemon._rumble_policy_before_profile == ("balanceado", 0.7)


def test_applier_custom_aplica_mult(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("custom", 0.4)

    assert daemon.config.rumble_policy == "custom"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.4)


def test_perfil_sem_opiniao_reverte_so_politica_de_perfil(daemon: Daemon) -> None:
    daemon.apply_profile_rumble_policy("max", None)
    daemon.apply_profile_rumble_policy(None, None)  # focou um app comum

    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._rumble_policy_from_profile is False
    assert daemon._rumble_policy_before_profile is None

    # Política de origem MANUAL não é revertida por perfil sem opinião.
    daemon.config.rumble_policy = "economia"
    daemon.apply_profile_rumble_policy(None, None)
    assert daemon.config.rumble_policy == "economia"


def test_reversao_volta_a_politica_pre_perfil_em_cadeia(daemon: Daemon) -> None:
    """Perfil A → perfil B → sem-opinião volta à política PRÉ-A (não à de A)."""
    daemon.config.rumble_policy = "economia"  # estado manual antigo (lock expirado)
    daemon.apply_profile_rumble_policy("max", None)  # perfil A
    daemon.apply_profile_rumble_policy("custom", 0.5)  # perfil B
    daemon.apply_profile_rumble_policy(None, None)  # app comum

    assert daemon.config.rumble_policy == "economia"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.7)
    assert daemon._rumble_policy_from_profile is False


def test_lock_manual_congela_o_perfil(daemon: Daemon) -> None:
    daemon._emu_manual_ts = time.monotonic()  # gesto manual AGORA

    daemon.apply_profile_rumble_policy("max", None)
    assert daemon.config.rumble_policy == "balanceado"
    assert daemon._rumble_policy_from_profile is False

    # A reversão por perfil-sem-opinião também congela dentro do lock.
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
    # economia = mult 0.3 → (100, 200) vira (30, 60).
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
    daemon.apply_profile_rumble_policy("max", None)  # política de perfil vigente

    asyncio.run(server._handle_rumble_policy_set({"policy": "economia"}))

    assert daemon.config.rumble_policy == "economia"
    # Origem "perfil" limpa: perfil sem opinião não reverte mais a escolha.
    assert daemon._rumble_policy_from_profile is False
    assert daemon._rumble_policy_before_profile is None
    # Lock manual armado: perfis ficam congelados por 30s.
    assert time.monotonic() - daemon._emu_manual_ts < 5.0
    daemon.apply_profile_rumble_policy("max", None)
    assert daemon.config.rumble_policy == "economia"

    asyncio.run(server._handle_rumble_policy_custom({"mult": 0.4}))
    assert daemon.config.rumble_policy == "custom"
    assert daemon.config.rumble_policy_custom_mult == pytest.approx(0.4)
    assert daemon._rumble_policy_from_profile is False


# ---------------------------------------------------------------------------
# ProfileManager repassa ao applier
# ---------------------------------------------------------------------------


def test_manager_repassa_politica_ao_applier() -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    received: list[tuple[str | None, float | None]] = []

    def applier(policy: str | None, custom_mult: float | None) -> None:
        received.append((policy, custom_mult))

    mgr = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_policy_applier=applier,
    )
    mgr.apply_emulation(_profile({"policy": "custom", "custom_mult": 0.5}))
    mgr.apply_emulation(_profile(None))

    # O applier recebe SEMPRE o par — inclusive (None, None) do perfil sem
    # opinião, que é o gatilho da reversão no daemon.
    assert received == [("custom", 0.5), (None, None)]


# ---------------------------------------------------------------------------
# Passthrough do perfil (SPRINT-GAME-RUMBLE-01)
# ---------------------------------------------------------------------------


def test_applier_passthrough_solta_rumble_fixado(daemon: Daemon) -> None:
    # Rumble FIXADO pela GUI (ex.: "Aplicar" na aba Rumble).
    daemon.config.rumble_active = (100, 120)
    daemon.apply_profile_rumble_passthrough(True)
    # Ativar um perfil com passthrough=true DEVOLVE a vibração ao jogo — senão o
    # FF do jogo seria ignorado por apply_game_rumble mesmo com a máscara certa.
    assert daemon.config.rumble_active is None


def test_applier_passthrough_false_preserva_rumble_fixado(daemon: Daemon) -> None:
    daemon.config.rumble_active = (100, 120)
    daemon.apply_profile_rumble_passthrough(False)
    # passthrough=false não solta o rumble fixado.
    assert daemon.config.rumble_active == (100, 120)


def test_applier_passthrough_preserva_silencio_deliberado(daemon: Daemon) -> None:
    # M2 (auditoria): "Parar" fixa (0,0) como silêncio deliberado. Ativar um
    # perfil (todo perfil tem passthrough=True) NÃO pode religar o jogo — senão
    # um alt-tab logo após "Parar" volta a sacudir o controle.
    daemon.config.rumble_active = (0, 0)
    daemon.apply_profile_rumble_passthrough(True)
    assert daemon.config.rumble_active == (0, 0)


def test_applier_passthrough_noop_quando_ja_em_passthrough(daemon: Daemon) -> None:
    daemon.config.rumble_active = None
    # Já em passthrough: no-op silencioso (não quebra, não escreve à toa).
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
    mgr.apply_emulation(_profile(None))  # sem seção → default True
    assert received == [True, False, True]


# ---------------------------------------------------------------------------
# Round-trip draft → profile → draft
# ---------------------------------------------------------------------------


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
