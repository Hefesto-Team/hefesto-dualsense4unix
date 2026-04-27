"""Roundtrip: criar perfil via modo simples → salvar JSON → recarregar → mesma seleção.

Simula o ciclo que ProfilesActionsMixin._build_profile_from_editor (modo simples)
+ _populate_editor executa, sem subir GTK — usa as funções puras de schema e
simple_match diretamente.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.simple_match import detect_simple_preset, from_simple_choice


def _build_simple_profile(
    name: str,
    priority: int,
    choice: str,
    custom_name: str | None = None,
) -> Profile:
    """Replica o que _build_profile_from_editor faz no modo simples."""
    match = from_simple_choice(choice=choice, custom_name=custom_name)
    return Profile(name=name, priority=priority, match=match)


def _save_and_reload(profile: Profile, tmp: Path) -> Profile:
    """Persiste perfil em JSON e recarrega via model_validate (simula loader)."""
    path = tmp / f"{profile.name}.json"
    path.write_text(
        json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


class TestRoundtripSimplePresets:
    """Para cada preset, o ciclo criar → salvar → recarregar → detectar mantém a chave."""

    @pytest.fixture()
    def tmp_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    @pytest.mark.parametrize(
        "choice",
        ["any", "steam", "browser", "terminal", "editor"],
    )
    def test_preset_roundtrip(self, tmp_dir: Path, choice: str) -> None:
        profile = _build_simple_profile("meu_perfil", 10, choice)
        reloaded = _save_and_reload(profile, tmp_dir)
        detected = detect_simple_preset(reloaded.match)
        assert detected == choice, (
            f"Preset '{choice}' não foi detectado após roundtrip; "
            f"detectado: {detected!r}, match: {reloaded.match!r}"
        )

    def test_game_roundtrip(self, tmp_dir: Path) -> None:
        profile = _build_simple_profile("jogo", 50, "game", custom_name="eldenring")
        reloaded = _save_and_reload(profile, tmp_dir)
        detected = detect_simple_preset(reloaded.match)
        assert detected == "game"
        assert isinstance(reloaded.match, MatchCriteria)
        assert reloaded.match.process_name == ["eldenring"]

    def test_game_nome_maiusculo_normalizado(self, tmp_dir: Path) -> None:
        profile = _build_simple_profile("jogo_caps", 5, "game", custom_name="EldenRing")
        reloaded = _save_and_reload(profile, tmp_dir)
        assert isinstance(reloaded.match, MatchCriteria)
        assert reloaded.match.process_name == ["eldenring"]

    def test_game_sem_custom_vira_any(self, tmp_dir: Path) -> None:
        profile = _build_simple_profile("sem_nome", 0, "game", custom_name=None)
        reloaded = _save_and_reload(profile, tmp_dir)
        # game sem custom_name → MatchAny; detect retorna "any"
        assert detect_simple_preset(reloaded.match) == "any"


class TestRoundtripCriterioComplexo:
    """Match complexo (não preset) deve ser detectado como None (modo avançado)."""

    @pytest.fixture()
    def tmp_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_criteria_complexo_detecta_none(self, tmp_dir: Path) -> None:
        match = MatchCriteria(
            window_class=["minha_app"],
            window_title_regex="Projeto.*",
            process_name=["meu_processo"],
        )
        profile = Profile(name="complexo", priority=20, match=match)
        reloaded = _save_and_reload(profile, tmp_dir)
        detected = detect_simple_preset(reloaded.match)
        assert detected is None

    def test_dados_nao_perdidos_apos_roundtrip(self, tmp_dir: Path) -> None:
        match = MatchCriteria(
            window_class=["code"],
            window_title_regex="hefesto-dualsense4unix",
            process_name=["code"],
        )
        profile = Profile(name="dev_hefesto", priority=30, match=match)
        reloaded = _save_and_reload(profile, tmp_dir)
        assert isinstance(reloaded.match, MatchCriteria)
        assert reloaded.match.window_class == ["code"]
        assert reloaded.match.window_title_regex == "hefesto-dualsense4unix"
        assert reloaded.match.process_name == ["code"]


class TestRoundtripPriority:
    @pytest.fixture()
    def tmp_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_prioridade_preservada(self, tmp_dir: Path) -> None:
        profile = _build_simple_profile("prio_test", 75, "steam")
        reloaded = _save_and_reload(profile, tmp_dir)
        assert reloaded.priority == 75

    def test_prioridade_zero(self, tmp_dir: Path) -> None:
        profile = _build_simple_profile("prio_zero", 0, "any")
        reloaded = _save_and_reload(profile, tmp_dir)
        assert reloaded.priority == 0
