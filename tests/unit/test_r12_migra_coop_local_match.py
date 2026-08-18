"""R-12 (auditoria 23/07) — migração one-shot do `match` do coop_local.

O preset de fábrica de 14/07 saiu com `MatchCriteria` de campos TODOS vazios —
`matches()` devolve False sem condição alguma, então o autoswitch NUNCA o
escolhe. O asset novo tem o regex de jogos de co-op, mas `seed_default_presets`
não sobrescreve (o preset está no `.seeded_presets`), então o arquivo LOCAL de
quem já tinha o preset velho fica preso.

A migração é CONSERVADORA: só reescreve quando o preset está EXATAMENTE no estado
inalcançável de fábrica (intocado). Qualquer edição da usuária = recua.
"""

from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.profiles.loader import (
    _COOP_LOCAL_MATCH_MIGRATION_MARKER,
    migrate_coop_local_match,
)

# O estado de fábrica inalcançável (14/07): criteria com tudo vazio.
FABRICA_VELHO = {
    "name": "coop_local",
    "version": 1,
    "match": {
        "type": "criteria",
        "window_class": [],
        "window_title_regex": None,
        "process_name": [],
    },
    "priority": 0,
    "leds": {"lightbar": [0, 200, 120]},
    "mode": {"kind": "gamepad", "gamepad_flavor": "xbox", "coop": True},
}

# O asset novo (fonte da verdade): regex de co-op + prioridade 45.
ASSET_NOVO = {
    "name": "coop_local",
    "version": 1,
    "match": {"type": "criteria", "window_title_regex": ".*(Sackboy|Overcooked|Cuphead).*"},
    "priority": 45,
    "leds": {"lightbar": [0, 200, 120]},
    "mode": {"kind": "gamepad", "gamepad_flavor": "xbox", "coop": True},
}


def _monta(tmp_path: Path, perfil: dict) -> tuple[Path, Path]:
    dest = tmp_path / "profiles"
    dest.mkdir()
    (dest / "coop_local.json").write_text(json.dumps(perfil), encoding="utf-8")
    src = tmp_path / "assets"
    src.mkdir()
    (src / "coop_local.json").write_text(json.dumps(ASSET_NOVO), encoding="utf-8")
    return dest, src


def _roda(dest: Path, src: Path) -> list[str]:
    # A função lê o asset via _seed_source_file(source_dirs=...) — mas a
    # assinatura pública não expõe isso; monkeypatch da cascata de fontes.
    import hefesto_dualsense4unix.profiles.loader as loader

    orig = loader._DEFAULT_SEED_SOURCE_DIRS
    loader._DEFAULT_SEED_SOURCE_DIRS = (src,)
    try:
        return migrate_coop_local_match(dest_dir=dest)
    finally:
        loader._DEFAULT_SEED_SOURCE_DIRS = orig


class TestMigracao:
    def test_preset_de_fabrica_ganha_o_match_do_asset(self, tmp_path: Path) -> None:
        dest, src = _monta(tmp_path, FABRICA_VELHO)
        migrados = _roda(dest, src)
        assert migrados == ["coop_local.json"]
        d = json.loads((dest / "coop_local.json").read_text(encoding="utf-8"))
        assert d["match"]["window_title_regex"] == ASSET_NOVO["match"]["window_title_regex"]
        assert d["priority"] == 45
        # Cor/mode intocados.
        assert d["leds"]["lightbar"] == [0, 200, 120]
        assert d["mode"]["coop"] is True

    def test_idempotente_via_marker(self, tmp_path: Path) -> None:
        dest, src = _monta(tmp_path, FABRICA_VELHO)
        assert _roda(dest, src) == ["coop_local.json"]
        assert (dest / _COOP_LOCAL_MATCH_MIGRATION_MARKER).exists()
        # 2ª vez: marker existe, não toca.
        assert _roda(dest, src) == []

    def test_editado_pela_usuaria_nao_e_tocado(self, tmp_path: Path) -> None:
        editado = dict(FABRICA_VELHO)
        editado["match"] = {"type": "criteria", "window_class": ["steam_app_1599660"]}
        dest, src = _monta(tmp_path, editado)
        assert _roda(dest, src) == []
        d = json.loads((dest / "coop_local.json").read_text(encoding="utf-8"))
        assert d["match"]["window_class"] == ["steam_app_1599660"]

    def test_match_any_explicito_nao_e_estado_de_fabrica(self, tmp_path: Path) -> None:
        outro = dict(FABRICA_VELHO)
        outro["match"] = {"type": "any"}
        dest, src = _monta(tmp_path, outro)
        assert _roda(dest, src) == []

    def test_sem_mode_coop_nao_migra(self, tmp_path: Path) -> None:
        """Só o coop_local (gamepad+coop) é o alvo — não um criteria vazio qualquer."""
        outro = dict(FABRICA_VELHO)
        outro["mode"] = {"kind": "desktop"}
        dest, src = _monta(tmp_path, outro)
        assert _roda(dest, src) == []
