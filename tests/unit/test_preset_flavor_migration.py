"""SPRINT-GAME-RUMBLE-01 — presets de jogo nascem/migram para a máscara xbox.

H1 da auditoria pré-release: a máscara DualSense faz o jogo ignorar o gamepad
virtual (rumble in-game morto + controle duplicado). Os presets shipados de JOGO
têm de nascer em `xbox`, e quem já os tinha semeados em `dualsense` é migrado
uma vez (sem tocar edições da usuária).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hefesto_dualsense4unix.profiles.loader import migrate_game_presets_to_xbox

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRESETS_DIR = _REPO_ROOT / "assets" / "profiles_default"


def test_presets_shipados_gamepad_nascem_xbox() -> None:
    """Todo preset default com mode.kind=='gamepad' vem com flavor 'xbox'.

    Guarda a headline do release: nenhum preset de jogo pode voltar a shipar em
    'dualsense' (rumble in-game morto)."""
    ofensores: list[str] = []
    for path in sorted(_PRESETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = data.get("mode")
        if (
            isinstance(mode, dict)
            and mode.get("kind") == "gamepad"
            and mode.get("gamepad_flavor") != "xbox"
        ):
            ofensores.append(f"{path.name}: {mode.get('gamepad_flavor')!r}")
    assert not ofensores, (
        "presets de jogo (mode.kind=gamepad) devem shipar com flavor 'xbox' "
        f"(a máscara que vibra); ainda em dualsense: {ofensores}"
    )


def test_migracao_troca_dualsense_por_xbox_uma_vez() -> None:
    d = Path(tempfile.mkdtemp())
    (d / "sackboy_nativo.json").write_text(
        json.dumps({"name": "sackboy_nativo",
                    "mode": {"kind": "gamepad", "gamepad_flavor": "dualsense", "coop": True}})
    )
    migrated = migrate_game_presets_to_xbox(d)
    assert "sackboy_nativo.json" in migrated
    got = json.loads((d / "sackboy_nativo.json").read_text())
    assert got["mode"]["gamepad_flavor"] == "xbox"
    # Idempotente: 2a passada não faz nada (marker).
    assert migrate_game_presets_to_xbox(d) == []


def test_migracao_nao_toca_edicao_da_usuaria() -> None:
    d = Path(tempfile.mkdtemp())
    # Usuária mudou para modo nativo — a migração não deve reescrever o flavor.
    (d / "coop_local.json").write_text(
        json.dumps({"name": "coop_local",
                    "mode": {"kind": "native", "gamepad_flavor": "dualsense"}})
    )
    migrate_game_presets_to_xbox(d)
    got = json.loads((d / "coop_local.json").read_text())
    assert got["mode"]["gamepad_flavor"] == "dualsense"  # intocado
