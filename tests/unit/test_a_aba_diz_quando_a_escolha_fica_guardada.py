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
from hefesto_dualsense4unix.app.actions.config.moldura import QUANDO_VALE, VALE_JA

GRAVADORES_IMEDIATOS = frozenset({"set_pref", "gravar_correcao_de_ambiente"})

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


def _grava_na_hora(secao: Any) -> bool:
    """A seção chama um escritor direto de preferência?"""
    for no in ast.walk(ast.parse(_fonte(secao))):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = (
            alvo.id
            if isinstance(alvo, ast.Name)
            else alvo.attr
            if isinstance(alvo, ast.Attribute)
            else None
        )
        if nome in GRAVADORES_IMEDIATOS:
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


def test_quem_escreve_no_rascunho_diz_que_espera_o_aplicar() -> None:
    """Seção diferida sem a frase é seção que parece não ter feito nada."""
    caladas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if _escreve_no_rascunho(secao) and not _diz(secao, QUANDO_VALE)
    ]
    assert not caladas, (
        f"estas seções acumulam no rascunho e não dizem que esperam o "
        f"'Aplicar': {caladas}. Quem clica e não vê nada acontecer conclui que "
        "não salvou."
    )


def test_quem_grava_na_hora_diz_que_nao_espera_o_aplicar() -> None:
    """A contraparte: "A janela" é a única que grava sozinha, e tem de dizer."""
    caladas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if _grava_na_hora(secao) and not _diz(secao, VALE_JA)
    ]
    assert not caladas, (
        f"estas seções gravam no próprio clique e não dizem isso: {caladas}. "
        "Numa aba em que tudo o mais espera o 'Aplicar', o silêncio aqui é lido "
        "como 'ainda não salvei'."
    )


def test_as_duas_frases_nunca_aparecem_na_mesma_secao() -> None:
    """Elas se contradizem. Uma seção com as duas é pior que uma sem nenhuma."""
    ambas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if _diz(secao, QUANDO_VALE) and _diz(secao, VALE_JA)
    ]
    assert not ambas, f"estas seções afirmam as duas coisas ao mesmo tempo: {ambas}"


def test_secao_que_so_le_nao_promete_gravacao() -> None:
    """A mentira inversa: "Está tudo certo?" não grava nada e não pode dizer que grava."""
    mentindo = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if not _escreve_no_rascunho(secao)
        and not _grava_na_hora(secao)
        and (_diz(secao, QUANDO_VALE) or _diz(secao, VALE_JA))
    ]
    assert not mentindo, (
        f"estas seções não gravam nada e mesmo assim falam de gravar: {mentindo}"
    )


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
