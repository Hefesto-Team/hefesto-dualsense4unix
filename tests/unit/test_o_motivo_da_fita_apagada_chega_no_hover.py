"""A fita apagada diz por quê — no hover, e nunca pintada (24/08/2026).

A DECISÃO, e ela tem duas metades que brigam
--------------------------------------------

A Z2-8 fez SEIS abas esmaecerem a fita "Ajustes vão para:" (Início, No jogo,
Perfis, Sistema, Emulação, Navegação), além da Configurações que já esmaecia.
O motivo de cada uma era **guardado e nunca mostrado**: existia só para o
portão da Z2-9 ler. Quem usasse o produto via a fita apagada e não tinha como
saber se aquilo era escolha ou defeito.

A outra metade é a decisão dela de 23/08/2026, que continua inteira: **o
cabeçalho não ganha um pixel**. A versão que pendurava um rótulo ao lado da
fita empurrava altura e largura, cobria o subtítulo do produto e deixava a aba
visivelmente mais larga que as outras dez — ela mandou tirar, e o motivo é
válido para qualquer explicação que ocupe espaço.

Tooltip resolve as duas: aparece só com o ponteiro parado em cima, e ocupa
zero.

A ARMADILHA, medida ANTES de escrever a cura
--------------------------------------------

**No GTK3, um widget insensível não recebe evento de mouse.** Pôr o tooltip na
própria fita (que é quem leva ``set_sensitive(False)``) deixaria a propriedade
posta e a frase nunca exibida:

    >>> caixa.set_tooltip_text("motivo"); caixa.set_sensitive(False)
    >>> caixa.get_property("has-tooltip")   # True  — parece que funcionou
    >>> caixa.is_sensitive()                # False — e por isso nunca dispara

Seria cura escrita e nunca ligada, que é o defeito mais caro desta casa. Por
isso a fita vai dentro de um ``Gtk.EventBox`` que fica SENSÍVEL e carrega o
tooltip; ``set_visible_window(False)`` o mantém sem pintura própria, para o
cabeçalho continuar com o mesmo tamanho de sempre.

AS MORDIDAS
-----------

* Mova o ``set_tooltip_text`` de volta para a fita (``_target_strip``) em vez
  do ``EventBox``: ``test_o_tooltip_mora_em_widget_que_recebe_o_ponteiro``
  reprova, porque o dono do tooltip volta a ser insensível.
* Apague a chamada de ``set_tooltip_text`` de ``set_alvo_inativo``:
  ``test_a_aba_que_nao_le_o_alvo_explica_no_hover`` reprova — é o estado de
  antes desta data, com o motivo guardado e mudo.
* Faça o ``EventBox`` pintar (``set_visible_window(True)``):
  ``test_a_moldura_do_hover_nao_pinta_nada`` reprova, porque o cabeçalho
  passaria a ter um retângulo que ele não tinha.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o tooltip da fita do alvo")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config.mixin import (
    MOTIVO_ALVO_NAO_SE_APLICA,
)


class _HostDaFita:
    """O mínimo que `set_alvo_inativo` toca: a fita e a moldura do hover.

    Monta a MESMA estrutura que `status_actions._init_controller_target_combo`
    monta em produção — fita dentro de `EventBox` —, porque é justamente a
    relação entre os dois que este arquivo cobra.
    """

    def __init__(self) -> None:
        self._target_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._target_strip.pack_start(Gtk.Label(label="Ajustes vão para:"), False, False, 0)
        self._target_strip_hover = Gtk.EventBox()
        self._target_strip_hover.set_visible_window(False)
        self._target_strip_hover.add(self._target_strip)


def _set_alvo_inativo(host: Any, inativo: bool, motivo: str = "") -> None:
    """Chama o método REAL do produto contra o host de teste."""
    from hefesto_dualsense4unix.app.actions.config.mixin import ConfigActionsMixin

    ConfigActionsMixin.set_alvo_inativo(host, inativo, motivo)


def test_a_aba_que_nao_le_o_alvo_explica_no_hover() -> None:
    """A MORDIDA principal: esmaecer sem dizer por quê é o estado de antes."""
    host = _HostDaFita()
    _set_alvo_inativo(host, True, MOTIVO_ALVO_NAO_SE_APLICA)

    assert host._target_strip_hover.get_tooltip_text() == MOTIVO_ALVO_NAO_SE_APLICA, (
        "a fita ficou apagada e não diz por quê. O motivo era guardado desde a "
        "Z2-5 e nunca chegava à tela; a decisão dela de 24/08 mandou ligá-lo no "
        "hover."
    )


def test_o_tooltip_mora_em_widget_que_recebe_o_ponteiro() -> None:
    """A armadilha do GTK3: quem leva o tooltip não pode ser o insensível.

    Esta é a régua que separa "cura ligada" de "cura escrita e nunca ligada" —
    um tooltip na fita apagada existe como propriedade e não aparece nunca.
    """
    host = _HostDaFita()
    _set_alvo_inativo(host, True, MOTIVO_ALVO_NAO_SE_APLICA)

    assert host._target_strip.get_sensitive() is False, (
        "a fita tinha de estar insensível — é o próprio assunto do tooltip"
    )
    assert host._target_strip_hover.get_sensitive() is True, (
        "o dono do tooltip está insensível: no GTK3 ele não recebe o ponteiro, "
        "e a frase nunca apareceria. Ela tem de morar no EventBox."
    )
    assert host._target_strip.get_tooltip_text() is None, (
        "o tooltip foi parar na fita insensível — é onde ele NÃO funciona"
    )


def test_a_fita_viva_nao_tem_o_que_explicar() -> None:
    """Nas quatro abas que leem o alvo, o tooltip sai — não fica frase velha."""
    host = _HostDaFita()
    _set_alvo_inativo(host, True, MOTIVO_ALVO_NAO_SE_APLICA)
    _set_alvo_inativo(host, False)

    assert host._target_strip.get_sensitive() is True
    assert host._target_strip_hover.get_tooltip_text() is None, (
        "a fita voltou a valer e o tooltip do estado anterior ficou grudado — "
        "explicaria uma coisa que não é mais verdade"
    )


def test_a_moldura_do_hover_nao_pinta_nada() -> None:
    """A decisão dela de 23/08 continua de pé: o cabeçalho não ganha um pixel."""
    host = _HostDaFita()
    assert host._target_strip_hover.get_visible_window() is False, (
        "o EventBox está pintando: o cabeçalho ganharia um retângulo que não "
        "tinha, que é exatamente o defeito do rótulo que ela mandou tirar"
    )


def test_os_dois_motivos_falam_a_lingua_da_tela() -> None:
    """O texto é para ela, não para quem escreveu o código.

    Os dois nasceram em linguagem de dev — *"o seletor de controle do
    cabeçalho"*, *"o alvo de edição"* — e foram reescritos em 24/08 saindo do
    léxico que já está na tela ("Ajustes vão para:", "mesa", "controle").
    Esta régua trava o vocabulário interno de voltar por descuido.
    """
    from hefesto_dualsense4unix.app.app import HefestoApp

    proibidas = ("alvo de edição", "seletor de controle", "_ALVO_POR_ABA", "leitor")
    for texto in (MOTIVO_ALVO_NAO_SE_APLICA, HefestoApp._MOTIVO_ALVO_AINDA_NAO_LIGADO):
        assert texto, "motivo vazio — `set_alvo_inativo(True)` recusaria"
        assert texto[0].isupper(), f"frase de tela começa com maiúscula: {texto!r}"
        assert texto.rstrip().endswith("."), f"frase de tela termina com ponto: {texto!r}"
        for palavra in proibidas:
            assert palavra not in texto.lower(), (
                f"{palavra!r} é como NÓS chamamos, não o que ela lê na tela: {texto!r}"
            )


def test_esmaecer_sem_motivo_continua_recusado() -> None:
    """O contrato da Z2 §5 não afrouxou por causa do tooltip."""
    host = _HostDaFita()
    with pytest.raises(ValueError, match="exige motivo"):
        _set_alvo_inativo(host, True, "")
