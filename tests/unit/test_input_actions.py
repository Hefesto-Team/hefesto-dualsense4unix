"""Testes unitários de InputActionsMixin (FEAT-KEYBOARD-UI-01, sprint 59.3).

Cobrem a lógica PURA de CRUD de key_bindings: resolução de bindings efetivos
(defaults vs override), conversão schema↔store, e as regras de adicionar/
remover/restaurar. Não exercitam GTK real — usam stubs de ListStore e
widgets que imitam a API mínima requerida.
"""
from __future__ import annotations

from typing import Any

import pytest

# Pula o arquivo inteiro se PyGObject não estiver disponível — o mixin vive
# na camada de UI e importa `gi`, que em ambientes CI/Noble puro-venv pode
# não estar presente. A lógica pura (resolve/persist/CRUD) é a mesma que
# seria exercitada; os 10 testes aqui são opt-in para dev com GUI instalada.
pytest.importorskip("gi")

from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS


class _FakeListStore:
    """Stand-in para `Gtk.ListStore` suportando operações mínimas."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append(self, row: list[str]) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows.clear()

    def remove(self, treeiter: int) -> None:
        del self.rows[treeiter]

    def get_iter(self, path: str) -> int:
        return int(path)

    def set_value(self, treeiter: int, col: int, value: str) -> None:
        self.rows[treeiter][col] = value

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _FakeMixin:
    """Aproveita apenas a parte testável de `InputActionsMixin` sem GTK.

    Importamos os métodos como funções descobrindo via dict de classe, o que
    evita depender da cadeia de herança com MouseActionsMixin (que importa
    ipc_bridge → schema → pydantic).
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._key_bindings_store = _FakeListStore()
        self._toasts: list[str] = []

    def _get(self, _key: str) -> Any:
        return None  # TreeView/widgets indisponíveis nos testes unit

    def _toast_input(self, msg: str) -> None:
        self._toasts.append(msg)


def _build_mixin() -> Any:
    """Instancia o mixin via composição para evitar herança com GTK."""
    from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin

    instance = _FakeMixin()
    # Liga os métodos do mixin como bound methods do fake.
    for name in (
        "_resolve_effective_bindings",
        "_refresh_key_bindings_from_draft",
        "on_key_binding_add",
        "on_key_binding_remove",
        "on_key_binding_restore_defaults",
        "_persist_key_bindings_to_draft",
        "_on_key_binding_cell_edited",
    ):
        setattr(
            instance,
            name,
            InputActionsMixin.__dict__[name].__get__(instance, type(instance)),
        )
    return instance


# --- _resolve_effective_bindings ---------------------------------------


def test_resolve_effective_bindings_none_usa_defaults() -> None:
    mixin = _build_mixin()
    # draft.key_bindings default é None.
    resolved = mixin._resolve_effective_bindings()
    assert resolved == dict(DEFAULT_BUTTON_BINDINGS)


def test_resolve_effective_bindings_vazio_desativa() -> None:
    mixin = _build_mixin()
    mixin.draft = mixin.draft.model_copy(update={"key_bindings": {}})
    resolved = mixin._resolve_effective_bindings()
    assert resolved == {}


def test_resolve_effective_bindings_override() -> None:
    mixin = _build_mixin()
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {"triangle": ["KEY_C"]}}
    )
    resolved = mixin._resolve_effective_bindings()
    assert resolved == {"triangle": ("KEY_C",)}


# --- CRUD --------------------------------------------------------------


def test_on_key_binding_add_adiciona_primeiro_botao_disponivel() -> None:
    mixin = _build_mixin()
    # Simular store vazia — add deve pegar primeiro botão canônico ("cross").
    mixin.on_key_binding_add(None)
    rows = mixin._key_bindings_store.rows
    assert len(rows) == 1
    assert rows[0][0] == "cross"
    assert rows[0][1] == "KEY_SPACE"


def test_on_key_binding_add_pula_existentes() -> None:
    mixin = _build_mixin()
    mixin._key_bindings_store.rows = [["cross", "KEY_A"], ["circle", "KEY_B"]]
    mixin.on_key_binding_add(None)
    rows = mixin._key_bindings_store.rows
    # Deve adicionar "triangle" (próximo canônico após cross/circle).
    assert any(r[0] == "triangle" for r in rows)


def test_on_key_binding_restore_defaults_zera_key_bindings_no_draft() -> None:
    mixin = _build_mixin()
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {"triangle": ["KEY_C"]}}
    )
    mixin.on_key_binding_restore_defaults(None)
    assert mixin.draft.key_bindings is None


def test_persist_serializa_store_em_dict() -> None:
    mixin = _build_mixin()
    mixin._key_bindings_store.rows = [
        ["triangle", "KEY_C"],
        ["r1", "KEY_LEFTALT+KEY_TAB"],
    ]
    mixin._persist_key_bindings_to_draft()
    assert mixin.draft.key_bindings == {
        "triangle": ["KEY_C"],
        "r1": ["KEY_LEFTALT", "KEY_TAB"],
    }


def test_persist_store_vazia_resulta_em_none() -> None:
    """Store sem rows serializada vira key_bindings=None (herda defaults)."""
    mixin = _build_mixin()
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {"triangle": ["KEY_C"]}}
    )
    mixin._key_bindings_store.rows = []
    mixin._persist_key_bindings_to_draft()
    assert mixin.draft.key_bindings is None


def test_on_key_binding_cell_edited_valida_e_persiste() -> None:
    mixin = _build_mixin()
    mixin._key_bindings_store.rows = [["triangle", "KEY_A"]]
    mixin._on_key_binding_cell_edited(None, "0", "KEY_C")
    assert mixin._key_bindings_store.rows[0][1] == "KEY_C"


def test_on_key_binding_cell_edited_binding_invalido_gera_toast() -> None:
    mixin = _build_mixin()
    mixin._key_bindings_store.rows = [["triangle", "KEY_A"]]
    mixin._on_key_binding_cell_edited(None, "0", "not_valid")
    # Valor NÃO mudou.
    assert mixin._key_bindings_store.rows[0][1] == "KEY_A"
    # Toast foi emitido.
    assert any("inválido" in t for t in mixin._toasts)
