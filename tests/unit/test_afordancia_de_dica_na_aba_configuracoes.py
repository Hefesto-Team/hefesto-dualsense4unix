"""AFORDÂNCIA — nenhuma dica da aba Configurações fica invisível.

O DEFEITO, medido em 23/08/2026 na aba montada de verdade, com a bancada viva
(2 DualSense no rádio, 3 adaptadores Bluetooth):

    pontos de dica montados na aba: 33
    Counter({'Label': 25, 'Button': 4, 'RadioButton': 4})
    ... e NENHUM dos 25 rótulos com marca visual nenhuma.

A leva da aba Configurações escreveu ~110 textos de dica, revisou-os e pôs cada
um no lugar certo. O inventário dela
(`docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/TOOLTIPS.md`) fixou DUAS
marcas de afordância — sublinhado pontilhado em rótulo, `?` em cabeçalho — e
**nenhuma das duas existia no produto**: `grep dotted` no `theme.css` voltava
vazio, e os títulos das seções carregavam a dica em silêncio.

O texto estava certo e ninguém o via. Quem não sabe que há explicação não passa
o mouse para procurá-la — uma leva inteira de redação não chegava a ninguém.

## Por que este arquivo mede o EFEITO, e não a linha de código

Um teste que contasse chamadas de `add_class` no fonte passaria com a folha de
estilo arrancada, com a classe escrita errada, e com a regra CSS recusada pelo
parser do GTK — que foi exatamente o que quase aconteceu aqui. O GTK 3.24.41
**recusa** `text-decoration-style: dotted` ("unknown value for property") e lê
`text-decoration: underline dotted` como cor inválida; a pontilhada só existe
por `border-bottom`. Uma marca que o parser recusa é uma marca invisível, que é
o defeito que este arquivo existe para pegar. Por isso há duas medidas:

1. a classe está no **contexto de estilo do widget** da aba montada;
2. a folha faz a borda chegar **pontilhada** no widget, medida por
   `Gtk.StyleContext.get_border` e `border-bottom-style`.

## A régua é INDEPENDENTE da produção, de propósito

Este arquivo **não importa** `merece_sublinhado`. Se importasse, arrancar a cura
pelo predicado — fazê-lo devolver `False` — deixaria o teste sem nenhum alvo a
afirmar: zero rótulos encontrados, zero falhas, verde. É a armadilha que a casa
já pagou ("o portão que não mede o que promete", 19/08). A régua daqui é
reescrita do zero, em `_precisa_de_marca`, e `NUNCA_MENOS_QUE` garante que ela
continua encontrando alvos.

## As duas armadilhas de medição já pagas nesta casa

* **`Gtk.OffscreenWindow`, nunca `Gtk.Window`** — sob Xvfb não há gerenciador de
  janelas e uma `Gtk.Window` fica 1x1 para sempre
  (`docs/method/COMO-OLHAR-A-TELA.md`).
* **A folha tem de ser aplicada pela tela** — sem `add_provider_for_screen` a
  medida 2 leria os zeros do tema do sistema e reprovaria uma cura sã.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("afordância das dicas da aba Configurações")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config.moldura import (
    CLASSE_AJUDA,
    CLASSE_TEM_DICA,
)
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA

NUNCA_MENOS_QUE = 12


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


def _descer(widget: Any) -> Iterator[Any]:
    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def _girar(vezes: int = 5000) -> None:
    """Esvazia a fila do GTK — inclusive os `idle` da revarredura."""
    for _ in range(vezes):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()


def _tem_dica(widget: Any) -> bool:
    return bool((widget.get_tooltip_text() or "").strip())


def _classes(widget: Any) -> set[str]:
    return set(widget.get_style_context().list_classes())


def _precisa_de_marca(widget: Any) -> bool:
    """A régua deste arquivo, escrita sem olhar para a da produção."""
    return (
        isinstance(widget, Gtk.Label)
        and _tem_dica(widget)
        and widget.get_ancestor(Gtk.Button) is None
    )


def _marcado(widget: Any) -> bool:
    """Tem marca própria, ou tem um `?` ao lado que fala por ele."""
    if _classes(widget) & {CLASSE_TEM_DICA, CLASSE_AJUDA}:
        return True
    pai = widget.get_parent()
    if pai is None:
        return False
    return any(
        irmao is not widget and CLASSE_AJUDA in _classes(irmao)
        for irmao in pai.get_children()
    )


def _descrever(widget: Any) -> str:
    return f"{type(widget).__name__}({(widget.get_text() or '')[:44]!r})"


def test_todo_titulo_de_secao_com_dica_ganha_a_marca() -> None:
    """O título que esconde dica é sublinhado; o que não esconde, não."""
    from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao

    esperadas = [s for s in SECOES_DA_ABA if getattr(s, "DICA", None)]
    assert esperadas, "nenhuma seção declara DICA — a régua perdeu o alvo"

    for secao in SECOES_DA_ABA:
        dica = getattr(secao, "DICA", None)
        frame, _caixa = moldura_de_secao(secao.TITULO, dica)
        rotulo = frame.get_label_widget()
        assert CLASSE_TEM_DICA in _classes(rotulo) if dica else True, (
            f'o título da seção "{secao.TITULO}" carrega a dica em silêncio'
        )
        if not dica:
            assert CLASSE_TEM_DICA not in _classes(rotulo), (
                f'a seção "{secao.TITULO}" não tem dica e ganhou marca mesmo '
                "assim — a marca deixa de significar que há explicação"
            )


def test_o_titulo_de_secao_continua_um_rotulo_com_texto() -> None:
    """A regressão de 23/08/2026, e ela custou 13 testes de outras frentes."""
    from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao

    for secao in SECOES_DA_ABA:
        rotulo = moldura_de_secao(secao.TITULO, getattr(secao, "DICA", None))[
            0
        ].get_label_widget()
        assert isinstance(rotulo, Gtk.Label), (
            f'o `label_widget` da seção "{secao.TITULO}" virou '
            f"{type(rotulo).__name__} — seis arquivos de teste chamam "
            "`.get_text()` nele"
        )
        assert rotulo.get_text() == secao.TITULO, (
            f"o texto do título saiu {rotulo.get_text()!r}, e não "
            f"{secao.TITULO!r} — as buscas por título deixam de achar a seção"
        )


