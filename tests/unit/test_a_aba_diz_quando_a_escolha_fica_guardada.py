"""Toda seção da aba Configurações diz se a escolha ficou guardada."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("a frase de quando a escolha vale")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import SECOES_DA_ABA


RASCUNHO = "_maquina_pendente"


def _fonte(secao: Any) -> str:
    return Path(inspect.getfile(secao)).read_text(encoding="utf-8")


def _escreve_no_rascunho(secao: Any) -> bool:
    """A seção atribui a `host._maquina_pendente` em algum ponto?"""
    for no in ast.walk(ast.parse(_fonte(secao))):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if isinstance(alvo, ast.Attribute) and alvo.attr == RASCUNHO:
                return True
    return False


class _HospedeiroVazio:
    """Sem builder, sem mesa, sem daemon — como o portão do item 8."""

    def __init__(self) -> None:
        self.builder = None


def _falas(secao: Any) -> list[str]:
    """Tudo que a seção DIZ à pessoa: rótulo impresso **e** dica no hover."""
    import contextlib

    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    with contextlib.suppress(Exception):
        secao.montar(_HospedeiroVazio(), caixa)

    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        dica = None
        with contextlib.suppress(Exception):
            dica = widget.get_tooltip_text()
        if dica:
            achados.append(dica)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                _andar(rotulo)
        if hasattr(widget, "get_children"):
            for filho in widget.get_children():
                _andar(filho)

    _andar(caixa)
    return achados


def _diz(secao: Any, frase: str) -> bool:
    """A seção diz esta frase — impressa ou no hover, inteira ou dentro de outra."""
    return any(frase in fala for fala in _falas(secao))


def test_a_frase_e_a_mesma_constante_nas_tres_secoes() -> None:
    """Três cópias do mesmo texto divergem na primeira revisão de redação."""
    literais = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if 'A escolha passa a valer quando você clicar' in _fonte(secao)
    ]
    assert not literais, (
        f"estas seções escrevem a frase à mão em vez de importar "
        f"`moldura.QUANDO_VALE`: {literais}"
    )
