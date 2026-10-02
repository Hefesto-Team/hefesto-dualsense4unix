"""TECLADO-QUE-NAO-DIGITA-01 — a aba passa a dizer o que NÃO digita."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("teclado que não digita")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
)

_TECLAS_QUE_DIGITAM: frozenset[str] = frozenset(
    [f"KEY_{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    + [f"KEY_{d}" for d in "0123456789"]
    + ["KEY_SPACE", "KEY_COMMA", "KEY_DOT"]
)


def test_nenhum_atalho_de_fabrica_digita_caractere() -> None:
    """A frase "nenhum atalho de fábrica digita letra" é verificável, não retórica."""
    digitam = {
        botao: tokens
        for botao, tokens in DEFAULT_BUTTON_BINDINGS.items()
        if any(token in _TECLAS_QUE_DIGITAM for token in tokens)
    }
    assert digitam == {}, (
        "algum binding de fábrica passou a digitar caractere — a legenda da aba "
        f"ainda promete o contrário: {digitam}"
    )


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _FakeListStore:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append(self, row: list[str]) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows.clear()

    def __iter__(self) -> Any:
        return iter(self.rows)


class _FakeMixin:
    """Mixin por composição — evita herdar de GTK só para ler uma frase."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._key_bindings_store = _FakeListStore()
        self.legend = _FakeLabel()

    def _get(self, key: str) -> Any:
        return self.legend if key == "key_bindings_legend" else None


