"""Toda seção da aba Configurações diz se a escolha ficou guardada.

O DEFEITO, MEDIDO EM 22/08/2026 olhando a aba montada. A aba nasceu com TRÊS
comportamentos de salvar e só UM deles escrito na tela:

* **"Orçamento"** acumula no rascunho e DIZ que espera o "Aplicar";
* **"Os controles"** e **"A mesa"** acumulam no MESMO rascunho e não diziam
  nada;
* **"A janela"** grava NA HORA (`set_pref`, `gravar_correcao_de_ambiente`) e
  também não dizia nada. A única frase dela — *"o tamanho novo vale na próxima
  vez que você abrir o Hefesto"* — responde QUANDO o tema é aplicado, nunca se
  a escolha foi guardada.

Três semânticas numa tela só, duas caladas. Quem clica e não vê nada acontecer
conclui uma de duas coisas, e as duas são ruins: que salvou quando não salvou,
ou que não salvou quando já salvou. É a mesma família do que ela relatou em
22/08 sobre o Sackboy — *"eu seto, clico em salvar, e não aplica"* — pelo lado
de dentro: a tela não diz o que fez com o gesto.

A RÉGUA É MECÂNICA, e é o que faz este portão valer para a seção que ainda não
existe: **quem escreve no rascunho tem de mostrar `QUANDO_VALE`; quem grava na
hora tem de mostrar `VALE_JA`; e quem não faz nem uma coisa nem outra não
mostra nenhuma das duas** — uma seção só de leitura ("Está tudo certo?") que
prometesse gravar seria a mentira inversa.

Quem escreve é lido do FONTE, por AST, e não de uma lista escrita à mão: uma
lista à mão caduca na próxima seção e o portão volta a mentir dizendo que está
tudo certo.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("a frase de quando a escolha vale")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import SECOES_DA_ABA
from hefesto_dualsense4unix.app.actions.config.moldura import QUANDO_VALE, VALE_JA

#: Os nomes que, chamados por uma seção, significam "isto foi ao disco AGORA".
#: São os escritores diretos de preferência — não passam pelo rodapé.
GRAVADORES_IMEDIATOS = frozenset({"set_pref", "gravar_correcao_de_ambiente"})

#: O atributo do hospedeiro em que as seções DIFERIDAS acumulam. Quem o escreve
#: espera o "Aplicar".
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


def _textos(secao: Any) -> list[str]:
    """Todo texto de rótulo que a seção põe na caixa, montada de verdade."""
    import contextlib

    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    with contextlib.suppress(Exception):
        secao.montar(_HospedeiroVazio(), caixa)

    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        if hasattr(widget, "get_children"):
            for filho in widget.get_children():
                _andar(filho)

    _andar(caixa)
    return achados


def test_quem_escreve_no_rascunho_diz_que_espera_o_aplicar() -> None:
    """Seção diferida sem a frase é seção que parece não ter feito nada.

    Mordida: tirar o `pack_start(rotulo_de_apoio(QUANDO_VALE), ...)` de
    `secao_mesa`, `secao_controles` ou `secao_orcamento`.
    """
    caladas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if _escreve_no_rascunho(secao) and QUANDO_VALE not in _textos(secao)
    ]
    assert not caladas, (
        f"estas seções acumulam no rascunho e não dizem que esperam o "
        f"'Aplicar': {caladas}. Quem clica e não vê nada acontecer conclui que "
        "não salvou."
    )


def test_quem_grava_na_hora_diz_que_nao_espera_o_aplicar() -> None:
    """A contraparte: "A janela" é a única que grava sozinha, e tem de dizer.

    Mordida: tirar o `pack_start(rotulo_de_apoio(VALE_JA), ...)` de
    `secao_janela`.
    """
    caladas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if _grava_na_hora(secao) and VALE_JA not in _textos(secao)
    ]
    assert not caladas, (
        f"estas seções gravam no próprio clique e não dizem isso: {caladas}. "
        "Numa aba em que tudo o mais espera o 'Aplicar', o silêncio aqui é lido "
        "como 'ainda não salvei'."
    )


def test_as_duas_frases_nunca_aparecem_na_mesma_secao() -> None:
    """Elas se contradizem. Uma seção com as duas é pior que uma sem nenhuma.

    Mordida: pôr `VALE_JA` em qualquer seção que já mostra `QUANDO_VALE`.
    """
    ambas = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if QUANDO_VALE in _textos(secao) and VALE_JA in _textos(secao)
    ]
    assert not ambas, f"estas seções afirmam as duas coisas ao mesmo tempo: {ambas}"


def test_secao_que_so_le_nao_promete_gravacao() -> None:
    """A mentira inversa: "Está tudo certo?" não grava nada e não pode dizer que grava.

    Mordida: pôr qualquer uma das duas frases na `secao_exame`.
    """
    mentindo = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if not _escreve_no_rascunho(secao)
        and not _grava_na_hora(secao)
        and (QUANDO_VALE in _textos(secao) or VALE_JA in _textos(secao))
    ]
    assert not mentindo, (
        f"estas seções não gravam nada e mesmo assim falam de gravar: {mentindo}"
    )


def test_a_frase_e_a_mesma_constante_nas_tres_secoes() -> None:
    """Três cópias do mesmo texto divergem na primeira revisão de redação.

    Este é o portão contra o retorno do defeito pela porta dos fundos: alguém
    reescreve a frase numa seção só, e a aba volta a ter duas maneiras de dizer
    a mesma coisa.

    Mordida: escrever a frase literal dentro de uma das seções em vez de
    importar `moldura.QUANDO_VALE`.
    """
    literais = [
        secao.TITULO
        for secao in SECOES_DA_ABA
        if 'A escolha passa a valer quando você clicar' in _fonte(secao)
    ]
    assert not literais, (
        f"estas seções escrevem a frase à mão em vez de importar "
        f"`moldura.QUANDO_VALE`: {literais}"
    )
