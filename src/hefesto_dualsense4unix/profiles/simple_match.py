"""Presets de match humanamente legíveis para o editor simples de perfis.

Cada chave de SIMPLE_MATCH_PRESETS mapeia um radio de "Aplica a" em MatchCriteria
ou MatchAny concreto. Helper `from_simple_choice` traduz a seleção do usuário.
"""
from __future__ import annotations

from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria

# Presets prontos, indexados pela chave do radio.
SIMPLE_MATCH_PRESETS: dict[str, MatchCriteria | MatchAny] = {
    "any": MatchAny(),
    "steam": MatchCriteria(process_name=["steam"]),
    "browser": MatchCriteria(
        window_class=["firefox", "chromium", "brave", "google-chrome"]
    ),
    "terminal": MatchCriteria(
        window_class=["gnome-terminal", "alacritty", "kitty", "konsole"]
    ),
    "editor": MatchCriteria(window_class=["code", "zed", "neovide"]),
}


def from_simple_choice(
    choice: str,
    custom_name: str | None = None,
) -> MatchCriteria | MatchAny:
    """Converte escolha do radio "Aplica a" em MatchCriteria ou MatchAny.

    Regras:
    - "game" + custom_name preenchido  → MatchCriteria(process_name=[custom_name])
    - "game" sem custom_name           → MatchAny() (fallback seguro)
    - qualquer outra chave de SIMPLE_MATCH_PRESETS → preset correspondente
    - chave desconhecida               → MatchAny()
    """
    if choice == "game":
        if custom_name and custom_name.strip():
            return MatchCriteria(process_name=[custom_name.strip().lower()])
        return MatchAny()
    return SIMPLE_MATCH_PRESETS.get(choice, MatchAny())


def detect_simple_preset(
    match: MatchCriteria | MatchAny,
) -> str | None:
    """Detecta se match corresponde a algum preset simples.

    Retorna a chave do preset (ex.: "steam", "browser") ou None se nenhum bater.
    Para "game", retorna ("game", process_name[0]); empacota com `_detect_game`.
    Uso interno: profiles_actions._populate_editor_v2.
    """
    if isinstance(match, MatchAny):
        return "any"
    for key, preset in SIMPLE_MATCH_PRESETS.items():
        if key == "any":
            continue
        if isinstance(preset, MatchCriteria) and _criteria_equal(match, preset):
            return key
    # Tenta detectar "jogo específico": process_name com 1 elemento, demais vazios
    if (
        isinstance(match, MatchCriteria)
        and len(match.process_name) == 1
        and not match.window_class
        and not match.window_title_regex
    ):
        return "game"
    return None


def _criteria_equal(a: MatchCriteria, b: MatchCriteria) -> bool:
    """Compara dois MatchCriteria por igualdade de campos."""
    return (
        sorted(a.window_class) == sorted(b.window_class)
        and a.window_title_regex == b.window_title_regex
        and sorted(a.process_name) == sorted(b.process_name)
    )
