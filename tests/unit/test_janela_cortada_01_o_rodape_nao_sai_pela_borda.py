"""JANELA-CORTADA-01 (17/08/2026) — o rodapé não pode sair pela borda de baixo.

**A queixa dela, na foto de 02h44:** *"altura e largura dos botões, em todas as
abas, ficam quebrados e não aparecem corretamente em qualquer resolução que
seja. nem com tela maximizada"*. O retângulo verde cercava a faixa em que
Aplicar / Salvar Perfil / Importar / Restaurar Default apareciam cortados ao
meio, junto com a statusbar.

**Por que a primeira medição não achou nada.** O sprint mediu
`get_preferred_height` — o que o widget PEDE — e concluiu que o rodapé cabia com
87px de folga. Cabia mesmo: o defeito está no que ele RECEBE. E havia um segundo
cego, este de instrumento: o `main` do `retratar_abas.py` arranca o
`main_notebook` do `root_box` e fotografa pelo notebook (`:1058-1060`), então
**nenhuma das dez fotos da documentação jamais mostrou o rodapé**. A casa já
tinha descoberto isso para o cabeçalho em 14/08 (`_fotografar_o_cabecalho`) e o
rodapé continuou invisível.

**O mecanismo, medido forçando a alocação da raiz (17/08):**

    altura da janela |  header  notebook  RODAPÉ | veredito
                 560 |      73       697      52 | FORA por 262px
                 650 |      73       697      52 | FORA por 172px
                 750 |      73       697      52 | FORA por  72px
                 822 |      73       697      52 | inteiro

O `main_notebook` trava no mínimo dele (697px) e **empurra o rodapé para fora da
borda de baixo**, com os 52px dele intactos. Ele não é esmagado — ele sai. Daí o
"cortado ao meio" em vez de "sumiu".

E o glade autorizava: `height-request = 560` numa janela cujo conteúdo pedia
822. Ninguém mentiu para o GTK. Isso também explica o *"em qualquer resolução"*:
não depende da tela, depende da altura da JANELA.

**A cura, decidida por ela (17/08), foi dupla:** cada página do notebook virou
um `GtkScrolledWindow` (`scroll_tab_*`, com `propagate-natural-height` para as
dez fotos da documentação não encolherem), e o `height-request` subiu de 560
para 620 — um piso honesto, agora que o miolo cede.

**O que este portão mede, e por que é diferente do
`test_layout_orcamento_altura.py`:** lá a pergunta é "o conteúdo cabe na janela
de abertura?" e a régua é o tamanho PREFERIDO. Aqui a pergunta é "o rodapé sai
pela borda?" e a régua é a ALOCAÇÃO — em várias alturas, incluindo abaixo do
mínimo do conteúdo, que é o regime em que o defeito vivia.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# `import gi` CRU aceita o stub que outro arquivo de teste planta em
# `sys.modules` — e com o stub dentro, o `Gtk.init_check()` do `_gtk_pronto()`
# estoura antes de qualquer teste rodar, derrubando a COLETA do módulo inteiro.
# Dois sintomas, uma causa só:
#
# 1. no runner headless o módulo não coleta (o portão do CI reprova a leva);
# 2. nesta bancada ele reprova por ORDEM — verde sozinho, vermelho depois do
#    `test_layout_orcamento_altura.py`, sempre com `fim = 1080`, porque o
#    `_alocar` não pegou. Quem mentiu foi o arquivo anterior.
#
# `exigir_gi_real()` limpa o stub quando o ambiente tem PyGObject de verdade, e
# pula o módulo quando não tem. Tem de vir ANTES do `import gi`.
exigir_gi_real("JANELA-CORTADA-01 (o rodapé na janela inteira)")

from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

RAIZ = Path(__file__).resolve().parents[2]
MAIN_GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"

#: As alturas que importam. As três primeiras estão ABAIXO do mínimo que o
#: conteúdo pedia antes da cura (822px) — é exatamente o regime em que o rodapé
#: saía pela borda, e um portão que só medisse a janela de abertura passaria
#: verde com o defeito vivo.
ALTURAS = (560, 620, 650, 750, 822, 830, 1080)

#: A largura de projeto. Não é ajustável: dois cards lado a lado somam direto
#: no mínimo da janela (`controller_card.py`, limite de 590px por card).
LARGURA = 1180


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


def _assentar(vezes: int = 6) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _montar():  # type: ignore[no-untyped-def]
    """A janela INTEIRA — header + notebook + rodapé — numa OffscreenWindow.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sem gerenciador de janelas a
    `Gtk.Window` fica 1x1 para sempre (armadilha nº 2 do `COMO-OLHAR-A-TELA`).
    E o `root_box` inteiro, não o notebook: é o recorte pelo notebook que
    escondeu este defeito por uma sessão inteira.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    raiz = builder.get_object("root_box")
    assert raiz is not None, "root_box sumiu do glade"
    pai = raiz.get_parent()
    if pai is not None:
        pai.remove(raiz)
    janela = Gtk.OffscreenWindow()
    janela.add(raiz)
    janela.set_size_request(LARGURA, ALTURAS[-1])
    janela.show_all()
    _assentar()
    return builder, raiz, janela


def _alocar(raiz, altura: int, janela=None) -> None:  # type: ignore[no-untyped-def]
    """Põe a raiz na altura pedida — e faz a JANELA concordar com ela.

    Sem o `janela`, este ajudante era instável POR ORDEM DE EXECUÇÃO: verde
    sozinho, vermelho depois do `test_layout_orcamento_altura.py`, sempre com
    `fim = 1080` nas primeiras alturas — que é o `ALTURAS[-1]` que o `_montar`
    pede à `OffscreenWindow`.

    A causa é uma disputa, não o produto: o `size_allocate` aqui empurra o
    FILHO para a altura do ensaio, e o `_assentar` logo abaixo drena eventos —
    entre eles o ciclo de alocação da PRÓPRIA janela, que devolve o filho aos
    1080 dela. Quem chega primeiro depende de haver trabalho pendente no GTK
    quando o teste começa, e isso o arquivo anterior decide.

    Então a janela passa a pedir a mesma altura antes: as duas concordam, e não
    há corrida para perder. Não afrouxa a mordida — a medição continua sendo a
    alocação REAL do rodapé depois que o GTK assentou.
    """
    if janela is not None:
        janela.set_size_request(LARGURA, altura)
    r = Gdk.Rectangle()
    r.x, r.y, r.width, r.height = 0, 0, LARGURA, altura
    raiz.size_allocate(r)
    _assentar(3)


class TestORodapeNaoSai:
    def test_o_rodape_fica_dentro_em_toda_altura(self) -> None:
        """A MORDIDA. Tire o scroller das páginas e isto fica vermelho.

        É o defeito de 17/08 inteiro: os quatro botões de ação global e a
        statusbar saindo pela borda de baixo sem que nada no GTK reclame.
        """
        builder, raiz, janela = _montar()
        rodape = builder.get_object("footer_box")
        assert rodape is not None, "footer_box sumiu do glade"

        fora = []
        for altura in ALTURAS:
            _alocar(raiz, altura, janela)
            a = rodape.get_allocation()
            fim = a.y + a.height
            if fim > altura:
                fora.append(f"{altura}px: rodapé termina em {fim} ({fim - altura}px fora)")

        assert not fora, (
            "o rodapé saiu pela borda de baixo em: " + "; ".join(fora)
            + ". Os quatro botões de ação global ficam invisíveis, e o GTK não "
            "acusa nada — foi assim que o defeito sobreviveu a uma sessão de "
            "vinte horas."
        )

    def test_o_rodape_nunca_e_esmagado(self) -> None:
        """A outra metade: ficar dentro por ter altura zero não vale.

        Sem este par, a cura "espreme o rodapé até caber" passaria — e ela é
        pior que o defeito, porque some sem deixar rastro na alocação.
        """
        builder, raiz, janela = _montar()
        rodape = builder.get_object("footer_box")
        botoes = builder.get_object("footer_buttons_box")

        magros = []
        for altura in ALTURAS:
            _alocar(raiz, altura, janela)
            if rodape.get_allocation().height < 20:
                magros.append(f"{altura}px: rodapé com {rodape.get_allocation().height}px")
            if botoes.get_allocation().height < 20:
                magros.append(f"{altura}px: botões com {botoes.get_allocation().height}px")

        assert not magros, "rodapé espremido em: " + "; ".join(magros)

    def test_o_miolo_e_quem_cede(self) -> None:
        """Quem encolhe quando falta espaço tem de ser o notebook, não o rodapé.

        É a afirmação positiva da cura, e ela distingue "o rodapé cabe porque a
        janela está grande" de "o rodapé cabe porque o miolo abre mão". Sem
        isto, os dois testes acima passariam numa janela que simplesmente nunca
        encolhe — e o defeito voltaria no dia em que alguém a deixasse encolher.
        """
        builder, raiz, janela = _montar()
        notebook = builder.get_object("main_notebook")

        alturas_do_miolo = []
        for altura in (620, 750, 1080):
            _alocar(raiz, altura, janela)
            alturas_do_miolo.append(notebook.get_allocation().height)

        assert alturas_do_miolo == sorted(alturas_do_miolo), (
            f"o miolo não acompanhou a janela: {alturas_do_miolo} para as "
            "alturas 620/750/1080. Se ele trava num mínimo, é o rodapé que sai."
        )
        assert alturas_do_miolo[0] < alturas_do_miolo[-1], (
            "o miolo tem o MESMO tamanho na janela pequena e na grande — ele "
            "não está cedendo, e o rodapé volta a ser empurrado para fora."
        )


class TestOPisoDaJanela:
    def test_o_height_request_nao_promete_o_que_nao_cabe(self) -> None:
        """O `height-request` é uma promessa ao gerenciador de janelas.

        Era 560 quando o conteúdo pedia 822 — e foi essa promessa que autorizou
        o WM a entregar uma janela em que o rodapé não cabia. Agora que o miolo
        rola, o piso existe para a janela não NASCER inútil; o número tem de
        continuar acomodando cabeçalho + rodapé com folga para algum miolo.
        """
        import xml.etree.ElementTree as ET

        arvore = ET.parse(str(MAIN_GLADE))
        piso = None
        for obj in arvore.iter("object"):
            if obj.get("id") != "main_window":
                continue
            for prop in obj.findall("property"):
                if prop.get("name") == "height-request":
                    piso = int((prop.text or "0").strip())
        assert piso is not None, "height-request sumiu de main_window"

        builder, raiz, janela = _montar()
        _alocar(raiz, piso, janela)
        fixos = sum(
            builder.get_object(n).get_allocation().height
            for n in ("header_bar", "footer_box")
        )
        assert piso >= fixos + 200, (
            f"o piso da janela é {piso}px e cabeçalho + rodapé já ocupam "
            f"{fixos}px: sobram {piso - fixos}px de miolo, que não é uma janela "
            "utilizável. O piso não é o mínimo técnico, é o menor tamanho em "
            "que o produto ainda serve para alguma coisa."
        )
