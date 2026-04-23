"""Testes dos perfis preset em assets/profiles_default/.

Valida que cada JSON é aceito pelo schema pydantic e que os params de
trigger são reconhecidos por build_from_name. Cobre os 9 arquivos após
a sprint FEAT-PROFILES-PRESET-06:
  acao.json, aventura.json, bow.json, corrida.json, esportes.json,
  fallback.json, fps.json, meu_perfil.json, navegacao.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto.core.trigger_effects import build_from_name
from hefesto.profiles.schema import Profile

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "profiles_default"

EXPECTED_PRESETS = {
    "acao": {  # noqa-acento — nome do arquivo acao.json
        "name": "Ação",
        "priority": 65,
        "triggers_left_mode": "Rigid",
        "triggers_right_mode": "Vibration",
        "lightbar": (255, 80, 0),
        "lightbar_brightness": 1.0,
    },
    "aventura": {
        "name": "Aventura",
        "priority": 70,
        "triggers_left_mode": "Resistance",
        "triggers_right_mode": "Galloping",
        "lightbar": (220, 170, 30),
        "lightbar_brightness": 0.7,
    },
    "bow": {
        "name": "bow",
        "priority": 10,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Bow",
        "lightbar": (0, 180, 100),
        "lightbar_brightness": 1.0,
    },
    "corrida": {
        "name": "Corrida",
        "priority": 55,
        "triggers_left_mode": "Resistance",
        "triggers_right_mode": "SlopeFeedback",
        "lightbar": (0, 180, 220),
        "lightbar_brightness": 0.8,
    },
    "esportes": {
        "name": "Esportes",
        "priority": 55,
        "triggers_left_mode": "Vibration",
        "triggers_right_mode": "PulseA",
        "lightbar": (40, 200, 80),
        "lightbar_brightness": 0.85,
    },
    "fallback": {
        "name": "fallback",
        "priority": 0,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Off",
        "lightbar": (40, 40, 40),
        "lightbar_brightness": 1.0,
    },
    "fps": {
        "name": "FPS",
        "priority": 60,
        "triggers_left_mode": "Rigid",
        "triggers_right_mode": "SemiAutoGun",
        "lightbar": (200, 20, 20),
        "lightbar_brightness": 0.9,
    },
    "meu_perfil": {
        "name": "meu_perfil",
        "priority": 0,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Off",
        "lightbar": (40, 80, 180),
        "lightbar_brightness": 0.4,
    },
    "navegacao": {
        "name": "Navegação",
        "priority": 50,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Off",
        "lightbar": (40, 80, 180),
        "lightbar_brightness": 0.4,
    },
}


@pytest.fixture(params=list(EXPECTED_PRESETS.keys()))
def preset_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _load_preset(name: str) -> Profile:
    path = ASSETS_DIR / f"{name}.json"
    assert path.exists(), f"Arquivo ausente: {path}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


class TestPresetValida:
    def test_schema_aceita(self, preset_name: str) -> None:
        """Profile.model_validate não levanta exceção."""
        p = _load_preset(preset_name)
        assert p is not None

    def test_nome_correto(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = EXPECTED_PRESETS[preset_name]["name"]
        assert p.name == expected, f"{preset_name}: nome esperado {expected!r}, obtido {p.name!r}"

    def test_priority_correto(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = EXPECTED_PRESETS[preset_name]["priority"]
        assert p.priority == expected, (
            f"{preset_name}: priority esperado {expected}, obtido {p.priority}"
        )

    def test_triggers_reconhecidos(self, preset_name: str) -> None:
        """build_from_name não levanta exceção para ambos os lados."""
        p = _load_preset(preset_name)
        for side, tc in [("left", p.triggers.left), ("right", p.triggers.right)]:
            try:
                build_from_name(tc.mode, tc.params)
            except Exception as ex:
                pytest.fail(f"{preset_name}.{side}: build_from_name falhou: {ex}")

    def test_trigger_left_mode(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = EXPECTED_PRESETS[preset_name]["triggers_left_mode"]
        assert p.triggers.left.mode == expected, (
            f"{preset_name} L2: esperado {expected!r}, obtido {p.triggers.left.mode!r}"
        )

    def test_trigger_right_mode(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = EXPECTED_PRESETS[preset_name]["triggers_right_mode"]
        assert p.triggers.right.mode == expected, (
            f"{preset_name} R2: esperado {expected!r}, obtido {p.triggers.right.mode!r}"
        )

    def test_lightbar_correto(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = EXPECTED_PRESETS[preset_name]["lightbar"]
        got = tuple(p.leds.lightbar)
        assert got == expected, (
            f"{preset_name}: lightbar esperado {expected}, obtido {got}"
        )

    def test_lightbar_brightness_correto(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        expected = float(EXPECTED_PRESETS[preset_name]["lightbar_brightness"])
        assert abs(p.leds.lightbar_brightness - expected) < 1e-6, (
            f"{preset_name}: brightness esperado {expected}, obtido {p.leds.lightbar_brightness}"
        )

    def test_rumble_presente(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        assert p.rumble is not None
        assert isinstance(p.rumble.passthrough, bool)

    def test_version_1(self, preset_name: str) -> None:
        p = _load_preset(preset_name)
        assert p.version == 1


class TestPresetMeuPerfil:
    def test_match_any(self) -> None:
        """meu_perfil.json deve ter match type=any (slot universal)."""
        from hefesto.profiles.schema import MatchAny
        p = _load_preset("meu_perfil")
        assert isinstance(p.match, MatchAny), "meu_perfil deve ter MatchAny"

    def test_priority_zero(self) -> None:
        """meu_perfil.json deve ter priority=0 (menor que qualquer perfil de jogo)."""
        p = _load_preset("meu_perfil")
        assert p.priority == 0


class TestPresetFallback:
    def test_priority_intocada(self) -> None:
        """fallback.json deve manter priority=0 (valor pre-existente)."""
        p = _load_preset("fallback")
        assert p.priority == 0

    def test_match_any(self) -> None:
        from hefesto.profiles.schema import MatchAny
        p = _load_preset("fallback")
        assert isinstance(p.match, MatchAny)


class TestPresetNavegacao:
    def test_priority_50(self) -> None:
        p = _load_preset("navegacao")
        assert p.priority == 50

    def test_triggers_off(self) -> None:
        p = _load_preset("navegacao")
        assert p.triggers.left.mode == "Off"
        assert p.triggers.right.mode == "Off"

    def test_lightbar_azul(self) -> None:
        p = _load_preset("navegacao")
        assert tuple(p.leds.lightbar) == (40, 80, 180)

    def test_brightness_baixa(self) -> None:
        p = _load_preset("navegacao")
        assert abs(p.leds.lightbar_brightness - 0.4) < 1e-6

    def test_match_criteria_com_browsers(self) -> None:
        from hefesto.profiles.schema import MatchCriteria
        p = _load_preset("navegacao")
        assert isinstance(p.match, MatchCriteria)
        wc = p.match.window_class
        assert any("firefox" in c.lower() or "brave" in c.lower()
                   or "chromium" in c.lower() or "steam" in c.lower()
                   for c in wc), f"Nenhum browser/steam em window_class: {wc}"


class TestPresetFps:
    def test_priority_60(self) -> None:
        p = _load_preset("fps")
        assert p.priority == 60

    def test_r2_semi_auto_gun(self) -> None:
        p = _load_preset("fps")
        assert p.triggers.right.mode == "SemiAutoGun"
        assert len(p.triggers.right.params) == 3

    def test_l2_rigid(self) -> None:
        p = _load_preset("fps")
        assert p.triggers.left.mode == "Rigid"

    def test_lightbar_vermelho(self) -> None:
        p = _load_preset("fps")
        r, g, b = p.leds.lightbar
        assert r > 150 and g < 50 and b < 50


class TestArquivosNaoExistem:
    def test_shooter_deletado(self) -> None:
        path = ASSETS_DIR / "shooter.json"
        assert not path.exists(), "shooter.json deve ter sido deletado"

    def test_driving_deletado(self) -> None:
        path = ASSETS_DIR / "driving.json"
        assert not path.exists(), "driving.json deve ter sido deletado"

    def test_todos_novos_existem(self) -> None:
        # Lista contém nomes literais de arquivos JSON (acao.json, navegacao.json).
        nomes = ["navegacao", "fps", "aventura", "acao", "corrida", "esportes"]  # noqa-acento
        for nome in nomes:
            path = ASSETS_DIR / f"{nome}.json"
            assert path.exists(), f"{nome}.json deve existir"
