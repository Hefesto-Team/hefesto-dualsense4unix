"""Escape de markup do Pango, sem depender de o GLib estar completo.

MARKUP-SEM-GLIB-01 (13/08/2026)
-------------------------------
Três lugares da janela montam markup do Pango com texto que vem DELA — nome de
perfil, aviso do perfil que não entrou, linha do painel "No jogo" — e todos
chamavam ``GLib.markup_escape_text`` direto. Um perfil chamado ``Rock & Roll``
derruba a pintura da linha inteira com erro de parse se o ``&`` sair cru, e a
aba perde justamente o aviso que existe para ser lido.

O DEFEITO QUE ISTO CURA, medido no CI em 13/08: os testes de interface desta
casa plantam um stub de ``gi`` quando não há PyGObject (é o que permite exercitar
a lógica da janela num runner pelado). Esse stub tem ``timeout_add``,
``idle_add`` e ``source_remove`` — e **não** tem ``markup_escape_text``. Nas três
versões de Python do ``ci.yml`` os dois testes do escape reprovavam com
``AttributeError: module 'gi.repository.GLib' has no attribute
'markup_escape_text'``, enquanto na máquina dela passavam, porque ali o
PyGObject é real.

Proteger a chamada com ``hasattr`` NÃO resolveria: os testes afirmam que o
escape ACONTECE (``assert "&amp;" in markup``), e um ``hasattr`` falso deixaria
o texto cru — trocaria a exceção por um markup quebrado, que é pior.

A hipótese explica o que já funcionava: em produção o PyGObject é sempre real e
o ``GLib.markup_escape_text`` sempre existiu, então o defeito nunca apareceu na
mão de ninguém. Ele é do INSTRUMENTO — e é a mesma família do vpad que o ensaio
aceitava mirar: o dublê não imita o que o produto usa.

Por que não é reimplementação gratuita: escapar XML são cinco substituições
fixas e definidas pela especificação do Pango, não heurística. Quando o GLib
está inteiro ele continua sendo quem faz o trabalho — a versão local é o piso,
não a preferência.
"""

from __future__ import annotations

#: As cinco substituições que o Pango exige, na ordem que importa: o ``&`` vem
#: PRIMEIRO, senão os ``&`` que as outras produzem seriam escapados de novo e
#: ``<`` viraria ``&amp;lt;``.
_TROCAS = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ("'", "&#39;"),
    ('"', "&quot;"),
)


def escapar_markup(texto: str) -> str:
    """``texto`` seguro para ``set_markup``, com ou sem GLib completo.

    Usa ``GLib.markup_escape_text`` quando ele existe — é o comportamento de
    produção e a referência. Cai na tabela local só quando o atributo falta,
    que hoje acontece exclusivamente sob o stub de ``gi`` dos testes.
    """
    try:
        from gi.repository import GLib
    except Exception:  # pragma: no cover - sem gi nenhum, o piso já resolve
        pass
    else:
        escapar = getattr(GLib, "markup_escape_text", None)
        if callable(escapar):
            resultado = escapar(texto)
            return str(resultado)

    for cru, escapado in _TROCAS:
        texto = texto.replace(cru, escapado)
    return texto
