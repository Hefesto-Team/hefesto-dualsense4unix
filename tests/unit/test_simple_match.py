"""Testes para src/hefesto/profiles/simple_match.py."""
from __future__ import annotations

from hefesto.profiles.schema import MatchAny, MatchCriteria
from hefesto.profiles.simple_match import (
    SIMPLE_MATCH_PRESETS,
    _criteria_equal,
    detect_simple_preset,
    from_simple_choice,
)


class TestSimpleMatchPresets:
    def test_presets_tem_cinco_chaves(self) -> None:
        assert set(SIMPLE_MATCH_PRESETS.keys()) == {
            "any",
            "steam",
            "browser",
            "terminal",
            "editor",
        }

    def test_preset_any_e_match_any(self) -> None:
        assert isinstance(SIMPLE_MATCH_PRESETS["any"], MatchAny)

    def test_preset_steam_retorna_criteria_com_process_name(self) -> None:
        preset = SIMPLE_MATCH_PRESETS["steam"]
        assert isinstance(preset, MatchCriteria)
        assert preset.process_name == ["steam"]
        assert not preset.window_class
        assert preset.window_title_regex is None

    def test_preset_browser_retorna_criteria_com_window_class(self) -> None:
        preset = SIMPLE_MATCH_PRESETS["browser"]
        assert isinstance(preset, MatchCriteria)
        assert "firefox" in preset.window_class
        assert "chromium" in preset.window_class
        assert "brave" in preset.window_class
        assert "google-chrome" in preset.window_class

    def test_preset_terminal_contem_alacritty(self) -> None:
        preset = SIMPLE_MATCH_PRESETS["terminal"]
        assert isinstance(preset, MatchCriteria)
        assert "alacritty" in preset.window_class

    def test_preset_editor_contem_vscode(self) -> None:
        preset = SIMPLE_MATCH_PRESETS["editor"]
        assert isinstance(preset, MatchCriteria)
        assert "code" in preset.window_class


class TestFromSimpleChoice:
    def test_any_retorna_match_any(self) -> None:
        result = from_simple_choice("any")
        assert isinstance(result, MatchAny)

    def test_steam_retorna_criteria_steam(self) -> None:
        result = from_simple_choice("steam")
        assert isinstance(result, MatchCriteria)
        assert result.process_name == ["steam"]

    def test_browser_retorna_criteria_browser(self) -> None:
        result = from_simple_choice("browser")
        assert isinstance(result, MatchCriteria)
        assert "firefox" in result.window_class

    def test_terminal_retorna_criteria_terminal(self) -> None:
        result = from_simple_choice("terminal")
        assert isinstance(result, MatchCriteria)
        assert "kitty" in result.window_class

    def test_editor_retorna_criteria_editor(self) -> None:
        result = from_simple_choice("editor")
        assert isinstance(result, MatchCriteria)
        assert "zed" in result.window_class

    def test_game_com_custom_name_retorna_process_name(self) -> None:
        result = from_simple_choice("game", custom_name="eldenring")
        assert isinstance(result, MatchCriteria)
        assert result.process_name == ["eldenring"]
        assert not result.window_class
        assert result.window_title_regex is None

    def test_game_custom_name_normalizado_para_lowercase(self) -> None:
        result = from_simple_choice("game", custom_name="EldenRing")
        assert isinstance(result, MatchCriteria)
        assert result.process_name == ["eldenring"]

    def test_game_sem_custom_name_retorna_match_any(self) -> None:
        result = from_simple_choice("game")
        assert isinstance(result, MatchAny)

    def test_game_custom_name_apenas_espacos_retorna_match_any(self) -> None:
        result = from_simple_choice("game", custom_name="   ")
        assert isinstance(result, MatchAny)

    def test_chave_desconhecida_retorna_match_any(self) -> None:
        result = from_simple_choice("nao_existe")
        assert isinstance(result, MatchAny)


class TestDetectSimplePreset:
    def test_match_any_detecta_any(self) -> None:
        assert detect_simple_preset(MatchAny()) == "any"

    def test_steam_detecta_steam(self) -> None:
        m = MatchCriteria(process_name=["steam"])
        assert detect_simple_preset(m) == "steam"

    def test_browser_detecta_browser(self) -> None:
        m = MatchCriteria(window_class=["firefox", "chromium", "brave", "google-chrome"])
        assert detect_simple_preset(m) == "browser"

    def test_terminal_detecta_terminal(self) -> None:
        m = MatchCriteria(window_class=["gnome-terminal", "alacritty", "kitty", "konsole"])
        assert detect_simple_preset(m) == "terminal"

    def test_editor_detecta_editor(self) -> None:
        m = MatchCriteria(window_class=["code", "zed", "neovide"])
        assert detect_simple_preset(m) == "editor"

    def test_game_especifico_detecta_game(self) -> None:
        m = MatchCriteria(process_name=["eldenring"])
        assert detect_simple_preset(m) == "game"

    def test_criteria_complexo_retorna_none(self) -> None:
        # window_class + process_name ao mesmo tempo — não é nenhum preset simples
        m = MatchCriteria(window_class=["steam"], process_name=["doom"])
        assert detect_simple_preset(m) is None

    def test_criteria_vazio_retorna_none(self) -> None:
        # MatchCriteria sem campos não bate com nenhum preset
        m = MatchCriteria()
        assert detect_simple_preset(m) is None

    def test_order_window_class_independe(self) -> None:
        # Ordem diferente ainda detecta browser
        m = MatchCriteria(window_class=["brave", "firefox", "google-chrome", "chromium"])
        assert detect_simple_preset(m) == "browser"


class TestCriteriaEqual:
    def test_iguais(self) -> None:
        a = MatchCriteria(window_class=["x", "y"], process_name=["p"])
        b = MatchCriteria(window_class=["y", "x"], process_name=["p"])
        assert _criteria_equal(a, b) is True

    def test_diferentes_window_class(self) -> None:
        a = MatchCriteria(window_class=["x"])
        b = MatchCriteria(window_class=["y"])
        assert _criteria_equal(a, b) is False

    def test_diferentes_regex(self) -> None:
        a = MatchCriteria(window_title_regex="abc")
        b = MatchCriteria(window_title_regex="xyz")
        assert _criteria_equal(a, b) is False
