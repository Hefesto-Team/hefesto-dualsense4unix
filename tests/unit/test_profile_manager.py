"""Testes do ProfileManager."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
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


def _mk_profile(name: str, priority: int = 10, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": priority,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30), player_leds=[True] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


def test_activate_aplica_trigger_e_led(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    applied = manager.activate("shooter")
    assert applied.name == "shooter"
    assert store.active_profile == "shooter"

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2
    # Right = Rigid (RIGID_B = 5 bits), forces[1] = 200 (force cru)
    right_call = next(c for c in triggers if c.payload[0] == "right")
    assert right_call.payload[1].forces == (5, 200, 0, 0, 0, 0, 0)

    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert len(leds) == 1
    assert leds[0].payload == (10, 20, 30)


def test_list_profiles_ordenado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("driving"))
    save_profile(_mk_profile("shooter"))
    save_profile(_mk_profile("bow"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    names = [p.name for p in manager.list_profiles()]
    assert names == ["bow", "driving", "shooter"]


def test_select_for_window_retorna_maior_prioridade(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("driving", priority=10, match=MatchCriteria(window_class=["Forza"]))
    )
    save_profile(
        _mk_profile(
            "shooter",
            priority=20,
            match=MatchCriteria(window_class=["Forza"]),
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Forza"})
    assert picked is not None
    assert picked.name == "shooter"  # maior priority


def test_select_for_window_fallback(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("shooter", match=MatchCriteria(window_class=["DoomEternal"]))
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Inkscape"})
    assert picked is not None
    assert picked.name == "fallback"


def test_select_for_window_sem_match_sem_fallback(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["X"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Nada"})
    assert picked is None


def test_delete_do_ativo_reseta_active_profile(isolated_profiles_dir: Path):
    save_profile(_mk_profile("tmp"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("tmp")
    assert store.active_profile == "tmp"
    manager.delete("tmp")
    assert store.active_profile is None


def test_create_persiste_no_disco(isolated_profiles_dir: Path):
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    profile = _mk_profile("new_one")
    manager.create(profile)
    assert (isolated_profiles_dir / "new_one.json").exists()


def test_apply_propaga_brightness(isolated_profiles_dir: Path):
    """FEAT-LED-BRIGHTNESS-02: brightness do perfil chega ao hardware via FakeController.

    Cria perfil com lightbar_brightness=0.25 (25%) e lightbar=(200, 100, 50).
    Apos apply(), verifica que o set_led recebeu valores escalados a 25%.
    """
    profile = _mk_profile(
        "dim_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=0.25),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None, "set_led não foi chamado"
    # RGB escalado: 200*0.25=50, 100*0.25=25, 50*0.25=12
    r, g, b = fc.last_led.color
    assert r == 50, f"canal R esperado 50, recebeu {r}"
    assert g == 25, f"canal G esperado 25, recebeu {g}"
    assert b == 12, f"canal B esperado 12, recebeu {b}"


def test_apply_propaga_multi_position(isolated_profiles_dir: Path):
    """SCHEMA-MULTI-POSITION-PARAMS-01 / A-06: params aninhado chega ao controller.

    Cria perfil com `left` = MultiPositionFeedback (params aninhado de 10)
    e `right` = MultiPositionVibration (params aninhado de 10). Após apply(),
    verifica que `set_trigger` foi chamado para ambos os lados com o
    `TriggerEffect` idêntico ao que a factory canônica produz.
    """
    from hefesto_dualsense4unix.core.trigger_effects import (
        TriggerMode,
        multi_position_feedback,
        multi_position_vibration,
    )

    left_nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
    right_nested = [[0], [0], [2], [2], [4], [5], [6], [7], [8], [8]]
    profile = _mk_profile(
        "multi_pos",
        triggers=TriggersConfig(
            left=TriggerConfig(mode="MultiPositionFeedback", params=left_nested),
            right=TriggerConfig(mode="MultiPositionVibration", params=right_nested),
        ),
    )

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2

    # Left: feedback — compara byte a byte com a factory direta.
    left_call = next(c for c in triggers if c.payload[0] == "left")
    expected_left = multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
    assert left_call.payload[1].mode == TriggerMode.RIGID_AB
    assert left_call.payload[1].forces == expected_left.forces

    # Right: vibration com frequency=0 (default do formato aninhado).
    right_call = next(c for c in triggers if c.payload[0] == "right")
    expected_right = multi_position_vibration(0, [0, 0, 2, 2, 4, 5, 6, 7, 8, 8])
    assert right_call.payload[1].mode == TriggerMode.PULSE_A
    assert right_call.payload[1].forces == expected_right.forces


def test_apply_brightness_maximo_nao_escala(isolated_profiles_dir: Path):
    """Brightness 1.0 (padrão) não altera os valores RGB."""
    profile = _mk_profile(
        "full_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=1.0),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None
    assert fc.last_led.color == (200, 100, 50)


def test_apply_propaga_player_leds_ao_controller(isolated_profiles_dir: Path):
    """BUG-PLAYER-LEDS-APPLY-01 / A-06: player_leds do perfil chega ao hardware
    via ProfileManager.apply → apply_led_settings → controller.set_player_leds.

    Cenário alvo: usuário marca padrão `0b10101` no editor, salva perfil, troca
    de janela e o autoswitch reaplica o perfil — os 5 LEDs do controle devem
    refletir exatamente o bitmask salvo. Sem a propagação em `apply_led_settings`,
    o perfil aparece correto na GUI mas o hardware mantém a configuração antiga.
    """
    profile = _mk_profile(
        "player_leds_test",
        leds=LedsConfig(
            lightbar=(10, 20, 30),
            player_leds=[True, False, True, False, True],  # 0b10101
        ),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_player_leds == (True, False, True, False, True)
    pl_cmds = [c for c in fc.commands if c.kind == "set_player_leds"]
    assert len(pl_cmds) == 1, "apply() deve chamar set_player_leds exatamente 1x"


def test_apply_propaga_player_leds_todos_apagados(isolated_profiles_dir: Path):
    """Perfil com player_leds=[False]*5 propaga ao controller (apaga os 5 LEDs)."""
    profile = _mk_profile(
        "player_leds_off",
        leds=LedsConfig(
            lightbar=(0, 0, 0),
            player_leds=[False, False, False, False, False],
        ),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_player_leds == (False, False, False, False, False)


def test_activate_propaga_player_leds(isolated_profiles_dir: Path):
    """`activate()` (caminho de profile.switch) também chega ao controller.

    `activate` delega a `apply`; o teste garante que o caminho comum do
    trocar-de-perfil-pela-GUI reenvia os 5 LEDs ao hardware em vez de deixar
    o controle com o padrão antigo.
    """
    save_profile(
        _mk_profile(
            "p2_canonico",
            leds=LedsConfig(
                lightbar=(100, 100, 100),
                player_leds=[False, True, False, True, False],  # 0b01010 = Player 2
            ),
        )
    )
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("p2_canonico")
    assert fc.last_player_leds == (False, True, False, True, False)
