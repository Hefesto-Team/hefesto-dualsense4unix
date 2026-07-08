"""FEAT-POINT-AND-CLICK-01 — seção opcional `mouse` do perfil.

Cobre os três andares da feature:
  1. Schema: `ProfileMouseConfig` (ranges, defaults, extra=forbid) e os campos
     aditivos em `Profile` (JSONs v1 sem os campos continuam válidos).
  2. `ProfileManager.activate`: appliers de mouse/supressão chamados com os
     valores do perfil; `mouse=None` NÃO toca no estado; falha do applier não
     aborta a ativação.
  3. Draft (GUI): `from_profile` popula `MouseDraft` (dirty=False);
     `to_profile` inclui a seção SOMENTE quando dirty; perfil legado faz
     round-trip inalterado.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.app.draft_config import DraftConfig, MouseDraft
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileMouseConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, **kw: object) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


# --- 1. Schema ---------------------------------------------------------------


def test_json_v1_sem_campos_novos_continua_valido() -> None:
    """Aditivo sem bump de versão: JSON antigo valida e ganha defaults."""
    raw = {
        "name": "legado",
        "version": 1,
        "match": {"type": "any"},
        "priority": 0,
        "triggers": {
            "left": {"mode": "Off", "params": []},
            "right": {"mode": "Off", "params": []},
        },
        "leds": {"lightbar": [1, 2, 3], "player_leds": [False] * 5},
        "rumble": {"passthrough": True},
    }
    p = Profile.model_validate(raw)
    assert p.mouse is None
    assert p.suppress_desktop_emulation is False


def test_secao_mouse_valida_com_defaults() -> None:
    cfg = ProfileMouseConfig(enabled=True)
    assert (cfg.enabled, cfg.speed, cfg.scroll_speed) == (True, 6, 1)


@pytest.mark.parametrize("speed", [0, 13])
def test_speed_fora_do_range_rejeitado(speed: int) -> None:
    with pytest.raises(ValidationError):
        ProfileMouseConfig(enabled=True, speed=speed)


@pytest.mark.parametrize("scroll", [0, 6])
def test_scroll_speed_fora_do_range_rejeitado(scroll: int) -> None:
    with pytest.raises(ValidationError):
        ProfileMouseConfig(enabled=True, scroll_speed=scroll)


def test_secao_mouse_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        ProfileMouseConfig(enabled=True, velocidade=9)  # type: ignore[call-arg]


def test_profile_com_secao_mouse_roundtrip_json() -> None:
    p = _mk_profile(
        "pnc", mouse={"enabled": True, "speed": 8, "scroll_speed": 2}
    )
    p2 = Profile.model_validate(p.model_dump(mode="json"))
    assert p2.mouse is not None
    assert (p2.mouse.enabled, p2.mouse.speed, p2.mouse.scroll_speed) == (True, 8, 2)


# --- 2. ProfileManager.activate ----------------------------------------------


class _Spy:
    def __init__(self) -> None:
        self.mouse_calls: list[tuple[bool, int, int]] = []
        self.suppression_calls: list[bool] = []

    def mouse(self, enabled: bool, speed: int, scroll: int) -> bool:
        self.mouse_calls.append((enabled, speed, scroll))
        return True

    def suppression(self, desired: bool) -> None:
        self.suppression_calls.append(desired)


def _manager_com_spy(spy: _Spy) -> ProfileManager:
    fc = FakeController()
    fc.connect()
    return ProfileManager(
        controller=fc,
        store=StateStore(),
        mouse_applier=spy.mouse,
        suppression_applier=spy.suppression,
    )


def test_activate_aplica_secao_mouse(isolated_profiles_dir: Path) -> None:
    save_profile(
        _mk_profile("pnc", mouse={"enabled": True, "speed": 8, "scroll_speed": 1})
    )
    spy = _Spy()
    _manager_com_spy(spy).activate("pnc")
    assert spy.mouse_calls == [(True, 8, 1)]


def test_activate_mouse_enabled_false_desliga(isolated_profiles_dir: Path) -> None:
    save_profile(
        _mk_profile("sem_mouse", mouse={"enabled": False, "speed": 4})
    )
    spy = _Spy()
    _manager_com_spy(spy).activate("sem_mouse")
    assert spy.mouse_calls == [(False, 4, 1)]


def test_activate_sem_secao_mouse_nao_toca_no_estado(
    isolated_profiles_dir: Path,
) -> None:
    """Regressão: perfil v1 sem seção mouse não liga nem desliga a emulação."""
    save_profile(_mk_profile("v1_puro"))
    spy = _Spy()
    _manager_com_spy(spy).activate("v1_puro")
    assert spy.mouse_calls == []


def test_activate_supressao_sempre_propagada(isolated_profiles_dir: Path) -> None:
    """O applier de supressão recebe o valor do campo em TODA ativação —
    inclusive o default False (é assim que trocar de perfil libera)."""
    save_profile(_mk_profile("game", suppress_desktop_emulation=True))
    save_profile(_mk_profile("desktop"))
    spy = _Spy()
    manager = _manager_com_spy(spy)
    manager.activate("game")
    manager.activate("desktop")
    assert spy.suppression_calls == [True, False]


def test_activate_sem_appliers_nao_quebra(isolated_profiles_dir: Path) -> None:
    """CLI/testes sem daemon: appliers None = seção ignorada, ativação ok."""
    save_profile(
        _mk_profile("pnc", mouse={"enabled": True}, suppress_desktop_emulation=True)
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc, store=StateStore())
    profile = manager.activate("pnc")
    assert profile.name == "pnc"


def test_activate_applier_que_levanta_nao_aborta(
    isolated_profiles_dir: Path,
) -> None:
    """Best-effort: falha no applier loga warning e a ativação completa."""
    save_profile(_mk_profile("pnc", mouse={"enabled": True}))

    def boom(*_a: object) -> None:
        raise RuntimeError("uinput indisponível")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(
        controller=fc, store=store, mouse_applier=boom, suppression_applier=boom
    )
    profile = manager.activate("pnc")
    assert profile.name == "pnc"
    assert store.active_profile == "pnc"


# --- 3. Draft (GUI) ------------------------------------------------------------


def test_from_profile_popula_mouse_draft_sem_dirty() -> None:
    profile = _mk_profile(
        "pnc", mouse={"enabled": True, "speed": 8, "scroll_speed": 2}
    )
    draft = DraftConfig.from_profile(profile)
    assert draft.mouse.enabled is True
    assert draft.mouse.speed == 8
    assert draft.mouse.scroll_speed == 2
    # Carga programática NÃO é toque da usuária (BUG-MOUSE-GUI-SYNC-01).
    assert draft.mouse.dirty is False


def test_from_profile_sem_mouse_usa_defaults() -> None:
    draft = DraftConfig.from_profile(_mk_profile("legado"))
    assert draft.mouse == MouseDraft()


def test_to_profile_inclui_mouse_somente_quando_dirty() -> None:
    draft = DraftConfig().model_copy(
        update={
            "mouse": MouseDraft(enabled=True, speed=9, scroll_speed=3, dirty=True)
        }
    )
    profile = draft.to_profile("editado")
    assert profile.mouse is not None
    assert (profile.mouse.enabled, profile.mouse.speed, profile.mouse.scroll_speed) == (
        True,
        9,
        3,
    )


def test_to_profile_sem_dirty_omite_secao_mouse() -> None:
    draft = DraftConfig().model_copy(
        update={
            "mouse": MouseDraft(enabled=True, speed=9, scroll_speed=3, dirty=False)
        }
    )
    assert draft.to_profile("intocado").mouse is None


def test_roundtrip_perfil_com_mouse_preserva_secao() -> None:
    """BUG-MOUSE-SAVE-DROPS-SECTION-01: salvar um perfil que JÁ possui seção mouse
    (ex.: point_and_click) SEM tocar a aba Mouse PRESERVA a seção. Antes,
    ``to_profile`` só emitia com ``dirty=True`` — o fluxo default de "Salvar
    Perfil" (nome pré-preenchido do perfil ativo) descartava a seção e matava a
    feature. ``in_profile`` (setado por ``from_profile``) resolve."""
    original = _mk_profile(
        "pnc", mouse={"enabled": True, "speed": 8, "scroll_speed": 2}
    )
    draft = DraftConfig.from_profile(original)
    assert draft.mouse.in_profile is True
    assert draft.mouse.dirty is False  # carga programática, não toque
    salvo = draft.to_profile("pnc", priority=10)
    assert salvo.mouse is not None
    assert (salvo.mouse.enabled, salvo.mouse.speed, salvo.mouse.scroll_speed) == (
        True,
        8,
        2,
    )


def test_to_ipc_dict_gate_e_so_dirty_nao_in_profile() -> None:
    """A rota IPC (Aplicar) continua gateada SÓ por ``dirty``: um draft carregado
    de um perfil com mouse (in_profile=True, dirty=False) NÃO emite a seção no
    ``to_ipc_dict`` — senão o Aplicar desligaria a emulação viva
    (BUG-MOUSE-GUI-SYNC-01 A2). Persistência (to_profile) preserva; o IPC não."""
    draft = DraftConfig().model_copy(
        update={
            "mouse": MouseDraft(
                enabled=True, speed=8, in_profile=True, dirty=False
            )
        }
    )
    assert draft.to_ipc_dict()["mouse"] is None
    assert draft.to_profile("pnc").mouse is not None


def test_roundtrip_perfil_legado_inalterado() -> None:
    """Perfil sem seção mouse atravessa from_profile→to_profile sem ganhá-la."""
    original = Profile(
        name="legado",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(lightbar=(10, 20, 30), player_leds=[False] * 5),
    )
    draft = DraftConfig.from_profile(original)
    salvo = draft.to_profile("legado", priority=5)
    assert salvo.mouse is None
    assert salvo.suppress_desktop_emulation is False
    assert salvo.model_dump(mode="json") == original.model_dump(mode="json")
