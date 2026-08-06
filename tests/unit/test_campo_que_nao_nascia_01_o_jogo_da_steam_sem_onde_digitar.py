"""CAMPO-QUE-NAO-NASCIA-01 — *"clico em jogo da steam e não aparece campo"*.

A queixa dela, em 05/08/2026: *"1599660 quando eu clico em jogo da steam não
aparece nenhum campo pra digitar"*. O número é o appid que ela tinha em mãos e
não tinha onde escrever.

O mecanismo, em três linhas:

* no ``main.glade`` o ``GtkBox id="profile_game_entry_box"`` nasce com
  ``visible=False`` **e** ``no-show-all=True`` — de propósito, para o
  ``show_all()`` da janela não revelar o campo antes da hora;
* a doutrina do GTK é que ``no_show_all`` faz o ``show_all()`` **ignorar** o
  widget, e por não descer nele os FILHOS (o rótulo "Nome do jogo:" e o
  ``GtkEntry profile_simple_custom_name``) nunca são mostrados;
* o handler fazia ``box.show()``, que revela a CAIXA e mais nada. Ela via um
  vão vazio no lugar do campo — sem erro, sem log, sem onde digitar.

**Por que a suíte inteira não pegou isso, e é esta a razão de o arquivo
existir.** Todos os testes que cobrem o "Aplica a" usam um dublê ``_FakeBox``
com um atributo ``.visivel``, e afirmam sobre a CAIXA
(``test_r12_editor_simples_gui.py``, ``test_profiles_gui_sync.py``,
``test_gui_perfil_manual_editor.py``, ``test_modo01_*``, ``test_empate01_*``,
``test_salvar_nao_rebaixa_02_*``). O dublê responde "estou visível" e **ninguém
pergunta pelos filhos** — que é exatamente onde o defeito mora. Um teste novo
com dublê aqui não valeria nada: por isso este arquivo usa **GTK real** e o
**glade real**, e toda asserção central é sobre o ``GtkEntry``, nunca sobre o
box.

Armadilha medida (``docs/process/COMO-OLHAR-A-TELA.md``): sob Xvfb não há
gerenciador de janelas e uma ``Gtk.Window`` de verdade fica 1x1 para sempre —
daí a ``Gtk.OffscreenWindow``. E o laço de eventos é drenado mais de uma vez
antes de medir, porque widget medido cedo demais reporta qualquer coisa.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, de propósito. Este
# arquivo só faz sentido contra widgets de verdade — contra o stub
# (`Gtk.Box = object`) ele passaria sem mostrar nada a ninguém.
exigir_gi_real("campo que não nascia 01")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.actions.profiles_actions import (
    ProfilesActionsMixin,
)
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.app.widgets import SegmentedSelector


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)

#: O appid que ela tinha na mão e não tinha onde digitar.
APPID_DELA = "1599660"

#: Janelas vivas até o fim do módulo: uma `OffscreenWindow` coletada no meio do
#: teste leva os widgets junto, e a medição vira sorte.
_janelas_vivas: list[Any] = []


def _assentar(vezes: int = 8) -> None:
    """Drena o laço do GTK até não haver mais o que fazer.

    Mais de uma passada de propósito (``retratar_abas.py``): a primeira monta,
    as seguintes deixam tema e tamanhos assentarem. Widget medido antes disso
    reporta 1x1 — e uma asserção sobre 1x1 passa com qualquer desenho.
    """
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


class _JanelaDeVerdade:
    """O glade REAL montado numa ``Gtk.OffscreenWindow``, como na abertura.

    Reproduz o que a janela real faz ao abrir: carrega o ``main.glade``,
    reparenta a ``root_box`` e chama ``show_all()`` na janela. É esse
    ``show_all()`` que o ``no-show-all`` do box intercepta — o ponto de partida
    do defeito.
    """

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(MAIN_GLADE))
        raiz = self.builder.get_object("root_box")
        pai = raiz.get_parent()
        if pai is not None:
            pai.remove(raiz)
        self.janela = Gtk.OffscreenWindow()
        self.janela.add(raiz)
        self.janela.set_size_request(1180, 800)
        self.janela.show_all()
        _janelas_vivas.append(self.janela)
        self._abrir_a_aba_perfis()
        _assentar()

    def _abrir_a_aba_perfis(self) -> None:
        """Põe a aba Perfis na frente — sem ela o campo nunca é MAPEADO.

        A visibilidade do widget é a medida central, mas `get_mapped()` só vira
        verdadeiro na página corrente do notebook; abrir a aba deixa a segunda
        medida disponível, que é a que responde "apareceu na tela dela?".
        """
        notebook = self.builder.get_object("main_notebook")
        alvo = self.entry()
        while alvo is not None and alvo.get_parent() is not notebook:
            alvo = alvo.get_parent()
        if alvo is not None:
            notebook.set_current_page(notebook.page_num(alvo))

    def box(self) -> Any:
        return self.builder.get_object("profile_game_entry_box")

    def entry(self) -> Any:
        return self.builder.get_object("profile_simple_custom_name")

    def rotulo(self) -> Any:
        """O ``GtkLabel`` "Nome do jogo:" — irmão do entry, sem id no glade."""
        return self.box().get_children()[0]


class _EditorDeVerdade(ProfilesActionsMixin):  # type: ignore[misc]
    """O mixin REAL sobre os widgets REAIS do glade.

    O que se exercita aqui é o handler de produção `_on_aplica_a_changed`, não
    uma descrição dele: o seletor é um `SegmentedSelector` de verdade, com os
    itens de verdade, ligado ao handler pelo mesmo `connect("changed", ...)`
    que o `_build_profiles_tab` usa.
    """

    def __init__(self, janela: _JanelaDeVerdade) -> None:
        self.builder = janela.builder
        self.janela_de_teste = janela
        self._profiles_cache: list[Any] = []
        self._duplicate_source = None
        self._mode_advanced = False
        self._new_profile = False
        self._regra_tocada = False
        self.toasts: list[str] = []
        self._aplica_a = SegmentedSelector(wrap=True)
        self._aplica_a.set_items(pa._APLICA_A_ITEMS)
        self._aplica_a.connect("changed", self._on_aplica_a_changed)
        self._aplica_a.set_active_id("any")
        _assentar()

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)

    def escolher(self, id_do_botao: str) -> None:
        """O gesto dela: clicar num botão do "Aplica a"."""
        self._aplica_a.set_active_id(id_do_botao)
        _assentar()


@pytest.fixture
def sem_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silencia o `call_async` do prefill de appid.

    O prefill é assíncrono e best-effort (preenche o appid do jogo em foco); o
    que está sob prova aqui é o campo NASCER, e uma chamada a daemon nenhum só
    acrescentaria caminho para o teste errar de lugar.
    """
    monkeypatch.setattr(pa, "call_async", lambda **_kw: None)


# ---------------------------------------------------------------------------
# A premissa: como o box nasce no glade
# ---------------------------------------------------------------------------


def test_o_box_do_glade_nasce_invisivel_e_surdo_ao_show_all() -> None:
    """O ponto de partida do defeito, lido do glade de verdade.

    As duas propriedades juntas são a armadilha: `visible=False` esconde, e
    `no-show-all=True` faz o `show_all()` da janela passar por cima sem descer
    nos filhos. Depois da abertura, NEM a caixa NEM o campo existem para ela.
    """
    janela = _JanelaDeVerdade()

    assert janela.box().get_no_show_all() is True, (
        "a premissa do defeito é o `no-show-all` do glade; sem ele esta "
        "família de testes perde o sentido e o handler pode ser simplificado"
    )
    assert janela.box().get_visible() is False
    assert janela.entry().get_visible() is False, (
        "o `show_all()` da janela não desce num box com `no-show-all`: o "
        "campo de digitar nasce invisível"
    )


# ---------------------------------------------------------------------------
# A contraprova — é ela que faz o resto MORDER
# ---------------------------------------------------------------------------


def test_show_sozinho_revela_a_caixa_e_deixa_o_campo_invisivel() -> None:
    """CONTRAPROVA: o código ANTIGO (`box.show()`) e o vão vazio que ela viu.

    Sem este caso, as asserções sobre o entry passariam por acidente e ninguém
    saberia distinguir a cura do defeito. Ele fixa a diferença: `show()` sobe a
    caixa e NÃO desce nos filhos — a tela fica com um espaço reservado e nada
    dentro, que é literalmente o que ela relatou.

    Este caso não depende do nosso código: é doutrina do GTK, e é o que
    autoriza os casos do handler a afirmarem sobre o ENTRY.
    """
    janela = _JanelaDeVerdade()

    janela.box().show()
    _assentar()

    assert janela.box().get_visible() is True, "o `show()` revela a CAIXA"
    assert janela.entry().get_visible() is False, (
        "e para na caixa: o campo de digitar continua invisível — o vão vazio "
        "da queixa dela"
    )
    assert janela.rotulo().get_visible() is False, (
        "nem o rótulo \"Nome do jogo:\" aparece; ela não tinha nem a dica"
    )
    assert janela.entry().get_mapped() is False, (
        "invisível de verdade: o campo nem chega a ser mapeado na tela"
    )


def test_show_all_com_no_show_all_ainda_armado_tambem_nao_mostra_nada() -> None:
    """A ORDEM da cura importa, e este caso é o que a justifica.

    Trocar `box.show()` por `box.show_all()` seco parece a correção óbvia e não
    corrige nada: `no_show_all` faz o `show_all()` ignorar o widget INCLUSIVE
    quando chamado nele mesmo. Desarmar primeiro não é ornamento.
    """
    janela = _JanelaDeVerdade()

    janela.box().show_all()
    _assentar()

    assert janela.box().get_visible() is False
    assert janela.entry().get_visible() is False, (
        "`show_all()` sem desarmar o `no_show_all` é um no-op — a cura precisa "
        "das DUAS chamadas, nesta ordem"
    )


# ---------------------------------------------------------------------------
# O par de chamadas da cura, medido no ENTRY
# ---------------------------------------------------------------------------


def test_desarmar_e_mostrar_faz_o_campo_de_digitar_nascer() -> None:
    """O par da cura (`set_no_show_all(False)` + `show_all()`) no box real.

    A asserção é no ENTRY, nunca no box: é aí que a cura e o defeito diferem, e
    é aí que os testes de dublê da casa não olhavam.
    """
    janela = _JanelaDeVerdade()

    janela.box().set_no_show_all(False)
    janela.box().show_all()
    _assentar()

    assert janela.entry().get_visible() is True, (
        "depois da cura ela tem onde digitar o appid"
    )
    assert janela.rotulo().get_visible() is True, (
        "e o rótulo \"Nome do jogo:\" volta junto — o campo sem rótulo não "
        "diria o que ele quer"
    )
    assert janela.entry().get_mapped() is True, (
        "visível de verdade na aba aberta, não só um sinalizador ligado"
    )


# ---------------------------------------------------------------------------
# O handler REAL — é ele que precisa estar certo
# ---------------------------------------------------------------------------


def test_jogo_da_steam_faz_o_campo_nascer_pelo_handler_real(
    sem_daemon: None,
) -> None:
    """A queixa dela, do gesto ao pixel: clicar em "Jogo da Steam" dá campo.

    Nada de chamadas soltas: o `SegmentedSelector` real emite "changed" e o
    `_on_aplica_a_changed` de produção decide. Se ele voltar a fazer só
    `box.show()`, este caso cai.
    """
    janela = _JanelaDeVerdade()
    editor = _EditorDeVerdade(janela)

    editor.escolher("steam_game")

    assert janela.entry().get_visible() is True, (
        "\"clico em jogo da steam não aparece nenhum campo pra digitar\": o "
        "handler tem de fazer NASCER o campo, não só a caixa dele"
    )
    assert janela.entry().get_mapped() is True
    assert janela.rotulo().get_visible() is True

    # E o campo tem de aceitar o número que ela tinha na mão.
    janela.entry().set_text(APPID_DELA)
    assert janela.entry().get_text() == APPID_DELA


def test_jogo_da_steam_traz_a_dica_do_appid_junto_com_o_campo(
    sem_daemon: None,
) -> None:
    """Campo visível E dica certa: sem o número, um campo em branco não ajuda.

    R-12: "jogo" e "jogo da Steam" compartilham o widget e pedem coisas
    diferentes (basename do executável x appid). A dica é a única coisa que
    desambigua — e ela só serve para alguma coisa se o campo estiver visível.
    """
    janela = _JanelaDeVerdade()
    editor = _EditorDeVerdade(janela)

    editor.escolher("steam_game")

    assert janela.entry().get_visible() is True
    assert janela.entry().get_placeholder_text() == f"ex.: {APPID_DELA}"


def test_jogo_especifico_tambem_faz_o_campo_nascer(sem_daemon: None) -> None:
    """A outra escolha com campo livre ("Jogo específico") tem o mesmo direito.

    As duas passam pelo mesmo ramo do handler; cobrir só a da Steam deixaria
    metade do caminho sem guarda.
    """
    janela = _JanelaDeVerdade()
    editor = _EditorDeVerdade(janela)

    editor.escolher("game")

    assert janela.entry().get_visible() is True
    assert janela.entry().get_placeholder_text() == "ex.: eldenring"


def test_qualquer_esconde_o_campo_e_jogo_da_steam_o_traz_de_volta(
    sem_daemon: None,
) -> None:
    """A cura não pode virar um campo que nunca mais some — nem que só vem uma vez.

    Três gestos, nesta ordem, porque o defeito e o excesso moram em pontas
    opostas: mostra, esconde, mostra DE NOVO. O terceiro é o que garante que
    desarmar o `no_show_all` no primeiro clique não quebrou o ciclo.

    A medida do "escondeu" é `is_visible()`, não `get_visible()`: o `hide()` do
    GTK baixa a bandeira do BOX e não desce nos filhos — o entry continua com a
    própria bandeira levantada, e só a visibilidade EFETIVA (que olha a cadeia
    de pais) diz a verdade sobre o que está na tela.
    """
    janela = _JanelaDeVerdade()
    editor = _EditorDeVerdade(janela)

    editor.escolher("steam_game")
    assert janela.entry().is_visible() is True

    editor.escolher("any")
    assert janela.box().get_visible() is False, (
        "\"Qualquer\" não tem alvo para digitar: a linha inteira sai da tela"
    )
    assert janela.entry().is_visible() is False, (
        "e o campo sai junto — um campo órfão de contexto convida a digitar o "
        "que não vai ser salvo"
    )
    assert janela.entry().get_mapped() is False

    editor.escolher("steam_game")
    assert janela.entry().is_visible() is True, (
        "e ela pode voltar atrás: o campo nasce outra vez, não só na primeira "
        "escolha da sessão"
    )
    assert janela.entry().get_mapped() is True
