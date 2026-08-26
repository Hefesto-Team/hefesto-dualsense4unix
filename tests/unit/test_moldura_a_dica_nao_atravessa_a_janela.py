"""MOLDURA — nenhum rótulo de apoio da aba Configurações atravessa a janela.

O defeito, medido em 23/08/2026 com a janela em 1868px: os **onze** rótulos de
apoio da aba saíam com **1818px cada um** — uma frase de ~215 caracteres numa
linha só, de borda a borda. O dobro dos paredões de Início e Sistema.

A causa é o clássico do GTK, e é por isso que este arquivo mede EFEITO e não a
linha de código: `rotulo_de_apoio` já tinha `set_xalign(0)` e
`set_max_width_chars(92)`, e os dois juntos não bastavam. `xalign` alinha o
TEXTO dentro do rótulo; `halign` é o que impede o RÓTULO de se esticar até a
largura do pai. E `max_width_chars` limita só a largura NATURAL pedida — com a
largura toda entregue pelo pai, ele nunca entra em ação.

Um teste que afirmasse `get_halign() == START` testaria a linha, não o efeito:
passaria com o `max_width_chars` arrancado, com o `line_wrap` desligado, e com
qualquer pai que continuasse esticando o rótulo por outro caminho.

Duas armadilhas de medição já pagas nesta casa, e as duas valem aqui:

* **`Gtk.OffscreenWindow`, nunca `Gtk.Window`** — sob Xvfb não há gerenciador
  de janelas e uma `Gtk.Window` fica 1x1 para sempre
  (`docs/process/COMO-OLHAR-A-TELA.md`).
* **A escala de fonte da casa muda os números.** Sem aplicar o tema pelos dois
  canais de `app.theme.apply_theme`, a medida sai nos 13,33px padrão do Pango e
  não nos da tela dela: os mesmos onze rótulos medem 635px no padrão e 919px na
  escala +3 que ela usa. O teto abaixo é escolhido sobre o número MAIOR.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceitaria o stub que outro arquivo planta em sys.modules.
exigir_gi_real("largura dos rótulos de apoio da aba Configurações")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.actions.config.mixin import ConfigActionsMixin
from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE
from hefesto_dualsense4unix.app.theme import (
    ESCALA_PADRAO,
    escalar_css,
    escalar_nome_da_fonte,
)

#: A largura em que o defeito foi medido — a janela dela, maximizada, menos o
#: cromo. É onde o paredão aparece: com a janela de projeto (1180) a frase já
#: quebra por falta de espaço, e o defeito se esconde.
LARGURA_DA_MEDIDA = 1868

#: Teto de largura de um rótulo de apoio, em pixels.
#:
#: DE ONDE VEM O NÚMERO: com a cura no lugar, o rótulo para na largura NATURAL
#: que o `max_width_chars=92` produz. O maior da aba mede 919px na escala de
#: fonte +3 (a dela) e 635px na escala padrão. 1100 dá ~20% de folga sobre o
#: maior medido — cabe uma frase mais longa ou uma fonte um pouco maior sem
#: alarme falso — e continua MUITO abaixo dos 1818px que o defeito produzia.
#: Fica também abaixo dos 1180px com que a janela abre: um rótulo mais largo que
#: a própria janela de projeto é, por definição, um paredão.
TETO_DO_ROTULO = 1100


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema pelos dois canais de `apply_theme`, e desfaz.

    A restauração impede que a escala vaze para outros arquivos da mesma sessão
    do pytest.
    """

    # A ESCALA É FIXADA — 25/08/2026. Esta fixture chamava `escala_fonte()`,
    # que lê o `gui_preferences.json` de QUEM RODA (nesta máquina, 6), e mexe
    # em `Gtk.Settings`, que é singleton do PROCESSO. Dois efeitos, os dois
    # medidos: o teste muda de veredito conforme a escala de quem roda, e a
    # escala vaza para os arquivos que rodam depois na mesma sessão do pytest.
    # Foi assim que dois testes de `test_layout_orcamento_altura.py`
    # reprovavam em lote e passavam sozinhos.
    #
    # A régua declarada é a `ESCALA_PADRAO`: é com ela que o produto nasce em
    # quem instala. A escala maior é escolha dela, e o que ela custa é OUTRA
    # pergunta, com outro teto.
    delta = ESCALA_PADRAO
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )
    yield
    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


class _HospedeiroDaAba(ConfigActionsMixin):
    def __init__(self, builder: Gtk.Builder) -> None:
        self.builder = builder


def _descer(widget: Any) -> Iterator[Any]:
    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def _e_rotulo_de_apoio(widget: Any) -> bool:
    """A assinatura do que `rotulo_de_apoio` produz, sem perguntar pelo halign.

    Perguntar pelo `halign` aqui faria o teste sumir com o próprio alvo quando a
    cura fosse arrancada: zero rótulos encontrados, zero afirmações, verde.
    """
    return (
        isinstance(widget, Gtk.Label)
        and widget.get_line_wrap()
        and widget.get_max_width_chars() > 0
        and "dim-label" in widget.get_style_context().list_classes()
    )


@pytest.fixture(scope="module")
def aba_montada() -> Any:
    """A aba de VERDADE, montada pelo mixin, numa janela da largura da medida."""
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    _HospedeiroDaAba(builder).install_config_tab()

    pagina = builder.get_object("scroll_tab_config_box")
    pai = pagina.get_parent()
    if pai is not None:
        pai.remove(pagina)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(pagina)
    janela.set_size_request(LARGURA_DA_MEDIDA, 1000)
    janela.show_all()
    for _ in range(3000):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()
    return pagina


def _rotulos_de_apoio(pagina: Any) -> list[Any]:
    achados = [w for w in _descer(pagina) if _e_rotulo_de_apoio(w) and w.get_mapped()]
    #: O PISO existe para o teste não passar por não achar nada — "um teste que
    #: não acha o alvo passa sempre" é o defeito de instrumento que esta casa
    #: mais paga. Ele NÃO é uma trava contra a página emagrecer.
    #:
    #: **DESCEU de 8 para 3 em 26/08/2026**, e o que mudou foi a PÁGINA, não a
    #: régua: a LEX-2 tirou quatro parágrafos de apoio da aba de propósito
    #: (8 únicos → 4), levando-os para dica, a pedido dela — *"tudo isso em azul
    #: deveria ser tooltip"*. O piso velho reprovava justamente o emagrecimento
    #: que era o objetivo da frente. Um piso que sobe com a página vira trava
    #: contra o próprio trabalho; o que ele tem de garantir é só que a
    #: assinatura de `_e_rotulo_de_apoio` continua casando com o que
    #: `rotulo_de_apoio` produz.
    PISO = 3
    assert len(achados) >= PISO, (
        f"a bancada achou {len(achados)} rótulos de apoio mapeados na aba, e o "
        f"piso é {PISO}. Menos que isso é sinal de que a assinatura de "
        "`_e_rotulo_de_apoio` deixou de casar com o que `rotulo_de_apoio` "
        "produz — e um teste que não acha o alvo passa sempre."
    )
    return achados


def test_nenhum_rotulo_de_apoio_atravessa_a_janela(aba_montada: Any) -> None:
    """Com a janela em 1868px, nenhuma dica passa de 1100px.

    Mordida: arrancar o `set_halign(Gtk.Align.START)` de `rotulo_de_apoio`
    devolve os onze rótulos a 1818px cada.
    """
    largos = [
        (w.get_allocation().width, w.get_text()[:60])
        for w in _rotulos_de_apoio(aba_montada)
        if w.get_allocation().width > TETO_DO_ROTULO
    ]
    assert not largos, (
        f"{len(largos)} rótulo(s) de apoio passaram do teto de "
        f"{TETO_DO_ROTULO}px numa janela de {LARGURA_DA_MEDIDA}px: {largos}. "
        "O `max_width_chars` só limita a largura NATURAL pedida — sem o "
        "`set_halign(Gtk.Align.START)` o pai entrega a largura toda ao rótulo e "
        "a frase sai numa linha só, de borda a borda."
    )


def test_o_rotulo_de_apoio_para_no_natural_e_nao_no_pai(aba_montada: Any) -> None:
    """A mesma cura, medida sem depender de nenhum número em pixels.

    O teto acima é um número escolhido, e número escolhido envelhece com a
    escala de fonte. Esta afirmação não: um rótulo com `halign=START` recebe
    `min(natural, disponível)`, e com `halign=FILL` recebe a largura do pai.
    Se um dia a fonte crescer a ponto de o natural passar de 1100px, o teste
    acima vira alarme falso e este continua medindo a cura.

    Mordida: a mesma — sem o `halign`, a alocação é a do pai, muito acima do
    natural.
    """
    esticados = []
    for rotulo in _rotulos_de_apoio(aba_montada):
        natural = rotulo.get_preferred_width()[1]
        alocada = rotulo.get_allocation().width
        if alocada > natural + 1:
            esticados.append((alocada, natural, rotulo.get_text()[:60]))
    assert not esticados, (
        "rótulo(s) de apoio receberam mais que a própria largura natural "
        f"(alocada, natural, texto): {esticados}. O pai esticou o rótulo, que é "
        "o que o `set_halign(Gtk.Align.START)` existe para impedir."
    )
