"""Testes dos perfis preset de fábrica — as duas casas em que eles moram."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.profiles.schema import Profile

_RAIZ = Path(__file__).parent.parent.parent
FABRICA_DIR = _RAIZ / "assets" / "profiles_default"
ESTILOS_DIR = _RAIZ / "assets" / "estilos_de_jogo"
CASAS_DE_FABRICA = (FABRICA_DIR, ESTILOS_DIR)


def preset_path(nome: str) -> Path:
    """O arquivo de fábrica de `nome`, na casa em que ele estiver hoje."""
    for casa in CASAS_DE_FABRICA:
        candidato = casa / f"{nome}.json"
        if candidato.exists():
            return candidato
    return FABRICA_DIR / f"{nome}.json"


def preset_em_alguma_casa(nome: str) -> bool:
    """True se `nome` está em QUALQUER das duas casas de fábrica."""
    return any((casa / f"{nome}.json").exists() for casa in CASAS_DE_FABRICA)


EXPECTED_PRESETS = {
    "acao": {  # slug do arquivo acao.json (noqa-acento)
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
        "triggers_left_mode": "MultiPositionFeedback",
        "triggers_right_mode": "MultiPositionFeedback",
        "lightbar": (220, 170, 30),
        "lightbar_brightness": 0.7,
    },
    "corrida": {
        "name": "Corrida",
        "priority": 55,
        "triggers_left_mode": "Resistance",
        "triggers_right_mode": "MultiPositionVibration",
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
        "lightbar": None,
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
    "freestyle": {
        "name": "Freestyle",
        "priority": 1,
        "triggers_left_mode": "Rigid",
        "triggers_right_mode": "Rigid",
        "lightbar": (40, 80, 180),
        "lightbar_brightness": 1.0,
    },
    "navegacao": {
        "name": "Navegação",
        "priority": 50,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Off",
        "lightbar": (40, 80, 180),
        "lightbar_brightness": 0.4,
    },
    "point_and_click": {
        "name": "point_and_click",
        "priority": 60,
        "triggers_left_mode": "Off",
        "triggers_right_mode": "Off",
        "lightbar": (255, 170, 0),
        "lightbar_brightness": 0.6,
    },
}


@pytest.fixture(params=list(EXPECTED_PRESETS.keys()))
def preset_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _load_preset(name: str) -> Profile:
    path = preset_path(name)
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
        if expected is None:
            assert "lightbar" not in p.leds.model_fields_set, (
                f"{preset_name}: o preset voltou a opinar sobre a cor "
                f"({tuple(p.leds.lightbar)}) — a cor automática por jogador "
                "perde para ele"
            )
            return
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


class TestPresetFreestyle:
    def test_match_any(self) -> None:
        """freestyle.json deve ter match type=any (o perfil de fora do jogo)."""
        from hefesto_dualsense4unix.profiles.schema import MatchAny
        p = _load_preset("freestyle")
        assert isinstance(p.match, MatchAny), "o Freestyle deve ter MatchAny"

    def test_nome_nao_e_slug(self) -> None:
        """PERFIL-PADRAO-PERSONALIZADO-01: o asset traz NOME DE GENTE."""
        p = _load_preset("freestyle")
        assert p.name == "Freestyle"

    def test_priority_acima_do_fallback(self) -> None:
        """freestyle.json deve ter priority=1 (catch-all pessoal acima do fallback nu)."""
        p = _load_preset("freestyle")
        assert p.priority == 1

    def test_brightness_100_por_cento(self) -> None:
        """ONDA-U (U9-brightness): default de código já é 1.0; o asset"""
        p = _load_preset("freestyle")
        assert abs(p.leds.lightbar_brightness - 1.0) < 1e-6


class TestPresetFallback:
    def test_priority_intocada(self) -> None:
        """fallback.json deve manter priority=0 (valor pre-existente)."""
        p = _load_preset("fallback")
        assert p.priority == 0

    def test_match_any(self) -> None:
        from hefesto_dualsense4unix.profiles.schema import MatchAny
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
        from hefesto_dualsense4unix.profiles.schema import MatchCriteria
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


class TestPresetPointAndClick:
    """FEAT-POINT-AND-CLICK-01 — perfil default para Grim Fandango e afins."""

    def test_match_grim_fandango(self) -> None:
        p = _load_preset("point_and_click")
        for wm_class in ("GrimFandango", "grim"):
            assert p.matches({"wm_class": wm_class}), (
                f"point_and_click deveria casar wm_class={wm_class!r}"
            )
        assert not p.matches({"wm_class": "firefox"})
        assert not p.matches({"wm_class": "scummvm"})

    def test_prioridade_acima_da_navegacao(self) -> None:
        """priority 60 > navegacao (50): o jogo vence o perfil de browser/Steam."""
        p = _load_preset("point_and_click")
        nav = _load_preset("navegacao")
        assert p.priority == 60
        assert p.priority > nav.priority

    def test_key_bindings_do_jogo_sem_vazamento_desktop(self) -> None:
        """Override COMPLETO (dict = sem merge): só estes botões emitem —"""
        p = _load_preset("point_and_click")
        assert p.key_bindings == {
            "l1": ["KEY_LEFTSHIFT"],
            "r1": ["KEY_DOT"],
            "options": ["KEY_ESC"],
            "create": ["KEY_I"],
            "touchpad_left_press": ["KEY_E"],
            "touchpad_middle_press": ["KEY_U"],
            "touchpad_right_press": ["KEY_P"],
        }

    def test_secao_mouse_liga_com_speed_8(self) -> None:
        p = _load_preset("point_and_click")
        assert p.mouse is not None
        assert p.mouse.enabled is True
        assert p.mouse.speed == 8
        assert p.mouse.scroll_speed == 1

    def test_sem_supressao_de_emulacao(self) -> None:
        """O jogo é jogado COM a emulação (mouse+teclado) — suppress off."""
        p = _load_preset("point_and_click")
        assert p.suppress_desktop_emulation is False

    def test_triggers_off_para_aventura(self) -> None:
        p = _load_preset("point_and_click")
        assert p.triggers.left.mode == "Off"
        assert p.triggers.right.mode == "Off"

    def test_selecionado_para_janela_grim_fandango(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Matcher end-to-end: janela fake GrimFandango vence navegacao/fallback."""
        import shutil

        from hefesto_dualsense4unix.profiles import loader as loader_module
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.testing import FakeController

        target = tmp_path / "profiles"
        target.mkdir()
        for fname in ("point_and_click.json", "navegacao.json", "fallback.json"):
            shutil.copy(preset_path(fname.removesuffix(".json")), target / fname)
        monkeypatch.setattr(
            loader_module, "profiles_dir", lambda ensure=False: target
        )

        manager = ProfileManager(controller=FakeController())
        escolhido = manager.select_for_window({"wm_class": "GrimFandango"})
        assert escolhido is not None
        assert escolhido.name == "point_and_click"

    def test_ativacao_emite_teclas_do_jogo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critério de aceite: ativar com FakeController + teclado virtual fake"""
        import shutil

        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.integrations.uinput_keyboard import (
            SUPPORTED_KEYS,
            UinputKeyboardDevice,
        )
        from hefesto_dualsense4unix.profiles import loader as loader_module
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.testing import FakeController

        target = tmp_path / "profiles"
        target.mkdir()
        shutil.copy(
            preset_path("point_and_click"), target / "point_and_click.json"
        )
        monkeypatch.setattr(
            loader_module, "profiles_dir", lambda ensure=False: target
        )

        fake_mod = MagicMock()
        for idx, key_name in enumerate(SUPPORTED_KEYS):
            setattr(fake_mod, key_name, (1, 1000 + idx))
        fake_device = MagicMock()
        fake_mod.Device.return_value = fake_device
        monkeypatch.setitem(sys.modules, "uinput", fake_mod)
        dev = UinputKeyboardDevice()
        assert dev.start() is True

        fc = FakeController()
        fc.connect()
        manager = ProfileManager(
            controller=fc,
            store=StateStore(),
            keyboard_device_provider=lambda: dev,
        )
        manager.activate("point_and_click")

        def presses_de(code: object) -> list:
            return [
                c
                for c in fake_device.method_calls
                if c[0] == "emit" and c[1][0] == code and c[1][1] == 1
            ]

        dev.dispatch(frozenset({"touchpad_left_press"}))
        assert len(presses_de(fake_mod.KEY_E)) == 1
        dev.dispatch(frozenset({"touchpad_middle_press"}))
        assert len(presses_de(fake_mod.KEY_U)) == 1
        dev.dispatch(frozenset({"touchpad_right_press"}))
        assert len(presses_de(fake_mod.KEY_P)) == 1
        dev.dispatch(frozenset({"l1"}))
        assert len(presses_de(fake_mod.KEY_LEFTSHIFT)) == 1
        dev.dispatch(frozenset({"r1"}))
        assert len(presses_de(fake_mod.KEY_DOT)) == 1
        dev.dispatch(frozenset({"options"}))
        assert len(presses_de(fake_mod.KEY_LEFTMETA)) == 0
        assert len(presses_de(fake_mod.KEY_ESC)) == 1


class TestArquivosNaoExistem:
    def test_shooter_deletado(self) -> None:
        assert not preset_em_alguma_casa("shooter"), (
            "shooter.json deve ter sido deletado — das DUAS casas de fábrica"
        )

    def test_driving_deletado(self) -> None:
        assert not preset_em_alguma_casa("driving"), (
            "driving.json deve ter sido deletado — das DUAS casas de fábrica"
        )

    def test_todos_novos_existem(self) -> None:
        nomes = [
            "navegacao", "fps", "aventura",  # slugs de arquivo (noqa-acento)
            "acao", "corrida", "esportes",  # slugs de arquivo (noqa-acento)
        ]
        for nome in nomes:
            assert preset_em_alguma_casa(nome), (
                f"{nome}.json sumiu das duas casas de fábrica"
            )


class TestOsPodadosNaoVoltam:
    """A poda de 26/08/2026, presa em régua."""

    @pytest.mark.parametrize(
        # Slugs literais dos arquivos apagados (noqa-acento).
        "nome", ["bow", "coop_local", "sackboy_nativo"]
    )
    def test_o_preset_podado_nao_esta_na_fabrica(self, nome: str) -> None:
        assert not preset_em_alguma_casa(nome), (
            f"{nome}.json voltou à fábrica. Ele foi podado em 26/08/2026 a "
            "pedido dela — *\"em termos de perfis de jogo vamos manter os que "
            "temos ativos apenas\"* —, e nenhum dos três estava ativo no "
            "disco dela. Devolver um deles é o produto reinstalando um perfil "
            "que ela já tinha mandado para o histórico."
        )

    def test_a_fabrica_embarca_nove_em_duas_casas(self) -> None:
        """Guarda do instrumento: régua que não acha nada passa sempre."""
        semeados = sorted(p.name for p in FABRICA_DIR.glob("*.json"))
        assert semeados == [
            "freestyle.json",
        ], f"a semeadura mudou de tamanho sem passar por aqui: {semeados}"

        estilos = sorted(p.name for p in ESTILOS_DIR.glob("*.json"))
        assert estilos == [
            "acao.json",  # (noqa-acento) nome literal de arquivo
            "aventura.json",
            "corrida.json",
            "esportes.json",
            "fallback.json",
            "fps.json",
            "navegacao.json",  # (noqa-acento) nome literal de arquivo
            "point_and_click.json",
        ], f"os Estilos de Jogo mudaram de tamanho sem passar por aqui: {estilos}"
