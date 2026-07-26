"""Orçamento de LARGURA e altura da janela: o conteúdo tem de caber sem barra.

O `GtkNotebook` pede como altura mínima o MAIOR mínimo entre todas as páginas —
uma aba gorda vira o piso de todas as outras. Estes testes medem o layout com
`GtkOffscreenWindow` (renderiza de verdade, sem aparecer na tela) e falham se
alguém reintroduzir um bloco que estoure o orçamento.

Histórico do que já custou caro aqui:
  - o `GtkFlowBox` dos 19 modos de gatilho reportava 606px (tudo empilhado);
  - a aba Emulação empilhava 9 blocos e pedia 674px;
  - o scroller de parâmetros reservava 220px fixos mesmo vazio.

LEGIBILIDADE-01 acrescentou duas coisas:

* **A medição usa a escala de fonte que de fato SAI** (`app/theme.py`). Antes
  ela carregava o `theme.css` cru, e o teste passava a aferir uma configuração
  que ninguém vê: quem abre a janela vê tudo 3px maior.
* **A LARGURA passou a ter teste.** Ela é a restrição dura, não a altura: a
  política de rolagem é vertical automática e horizontal `never`
  (`app/app.py`), então a barra vertical salva a altura enquanto o mínimo de
  largura sobe intacto até a janela, sem escape. Era o furo por onde uma única
  linha de botões com distribuição homogênea respondia por 1004 dos 1066px de
  largura mínima da janela inteira, sem nada acusar.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from hefesto_dualsense4unix.app.actions.status_actions import (  # noqa: E402
    _LinhaMic,
)
from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE  # noqa: E402
from hefesto_dualsense4unix.app.mic_monitor import (  # noqa: E402
    CURA_PONTE_BT,
    MOTIVO_PONTE_DESLIGADA,
    DiagnosticoMic,
)
from hefesto_dualsense4unix.app.theme import (  # noqa: E402
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (  # noqa: E402
    ControllerCard,
)


def _dimensao_da_janela(nome: str) -> int:
    """Lê `default-width`/`default-height` direto do glade.

    Constante duplicada aqui viraria mentira no dia em que alguém mudasse o
    glade: o teste continuaria verde medindo contra uma altura que a janela
    não usa mais.
    """
    import xml.etree.ElementTree as ET

    arvore = ET.parse(str(MAIN_GLADE))
    for obj in arvore.iter("object"):
        if obj.get("id") != "main_window":
            continue
        for prop in obj.findall("property"):
            if prop.get("name") == nome:
                return int((prop.text or "0").strip())
    raise AssertionError(f"{nome} não encontrado em main_window")


#: Altura com que a janela abre — é o número que decide se a barra aparece.
ALTURA_JANELA = _dimensao_da_janela("default-height")
#: Teto para o conteúdo. Abaixo disso a barra de rolagem não precisa aparecer.
TETO_CONTEUDO = ALTURA_JANELA
#: Largura de referência, também vinda do glade.
LARGURA = _dimensao_da_janela("default-width")


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


#: Um controle com TODOS os módulos de sensor presentes — é o card mais alto
#: que a aba consegue produzir, e é ele que o orçamento tem de suportar.
_INPUTS_COMPLETOS = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {
        "touching": True,
        "x": 1440,
        "y": 270,
        "width": 1920,
        "height": 1080,
    },
    "speaker": {"volume": 180, "muted": False},
}
_ENTRY_COMPLETO = {
    "index": 0,
    "connected": True,
    "transport": "bt",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": 1,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS_COMPLETOS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}
_ESTADO_COMPLETO = {
    "native_mode": False,
    "rumble_ff": {
        "per_vpad": [
            {"player": 1, "motion_streaming": True, "motion_hz": 250.0}
        ]
    },
}


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema COM a escala de fonte da sessão, e desfaz no fim.

    Os dois canais da escala, os mesmos de `app.theme.apply_theme`: o CSS com
    os `font-size` reescritos e o `gtk-font-name` para a base herdada. Sem o
    segundo, ~90% da janela continuaria medindo os 13,33px do padrão do Pango
    e o orçamento aferido não seria o da tela.

    `gtk-font-name` é global do processo; a restauração impede que as medidas
    daqui vazem para outros arquivos de teste da mesma sessão do pytest.
    """
    delta = escala_fonte()
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


def _montar() -> tuple[Gtk.Builder, Gtk.Widget]:
    """Carrega o glade dentro de uma janela offscreen (tema pela fixture)."""
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    root = builder.get_object("root_box")
    pai = root.get_parent()
    if pai is not None:
        pai.remove(root)
    win = Gtk.OffscreenWindow()
    win.get_style_context().add_class("hefesto-dualsense4unix-window")
    win.add(root)
    win.set_size_request(LARGURA, -1)
    win.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    return builder, root


def test_janela_cabe_sem_rolagem() -> None:
    """Header + abas + rodapé têm de caber na altura com que a janela abre."""
    _builder, root = _montar()

    altura, _ = root.get_preferred_height_for_width(LARGURA)

    assert altura <= TETO_CONTEUDO, (
        f"o conteúdo pede {altura}px e a janela abre com {ALTURA_JANELA}px "
        f"({altura - ALTURA_JANELA}px a mais): a barra de rolagem volta a "
        "aparecer em TODAS as abas, não só na que cresceu"
    )


def test_nenhuma_aba_isolada_estoura_o_orcamento() -> None:
    """Aponta QUAL aba estourou — o teste acima só diz que a soma não cabe.

    O teto é DERIVADO, não escrito à mão: é a altura da janela menos o que fica
    fora do notebook (cabeçalho e rodapé) e menos o cromo do próprio notebook
    (a tira de abas e as bordas). Um número fixo aqui vira mentira no dia em
    que o cabeçalho ganhar uma linha — foi o que aconteceu com o teto de 600px,
    que era o orçamento de uma janela de 760px com a fonte 3px menor.

    Na medição de LEGIBILIDADE-01, com a janela em 830px e a fonte na escala
    que sai: cabeçalho 73px, rodapé 52px, cromo do notebook 51px — teto de
    654px, e a aba mais alta (Emulação) pedindo 626px.
    """
    builder, _root = _montar()
    notebook = builder.get_object("main_notebook")

    fora_do_notebook = sum(
        builder.get_object(nome).get_preferred_height_for_width(LARGURA)[0]
        for nome in ("header_bar", "footer_box")
    )
    maior_pagina = max(
        notebook.get_nth_page(i).get_preferred_height_for_width(LARGURA - 20)[0]
        for i in range(notebook.get_n_pages())
    )
    cromo_do_notebook = (
        notebook.get_preferred_height_for_width(LARGURA)[0] - maior_pagina
    )
    teto_por_aba = ALTURA_JANELA - fora_do_notebook - cromo_do_notebook

    gordas = []
    for i in range(notebook.get_n_pages()):
        page = notebook.get_nth_page(i)
        rotulo = notebook.get_tab_label_text(page) or f"#{i}"
        altura, _ = page.get_preferred_height_for_width(LARGURA - 20)
        if altura > teto_por_aba:
            gordas.append(f"{rotulo} ({altura}px)")

    assert not gordas, (
        f"abas acima do teto de {teto_por_aba}px (janela {ALTURA_JANELA} - "
        f"cabeçalho/rodapé {fora_do_notebook} - cromo do notebook "
        f"{cromo_do_notebook}): {', '.join(gordas)}. "
        "Lembre que o notebook adota o MAIOR mínimo — uma aba gorda empurra "
        "todas as outras para a rolagem."
    )


def test_nenhuma_aba_estoura_a_largura_da_janela() -> None:
    """A restrição DURA: horizontal não tem barra de rolagem para onde fugir.

    `app/app.py` define a política como vertical automática e horizontal
    `never`. Quando uma aba pede mais largura do que a janela abre, o mínimo
    sobe intacto até a janela — ela simplesmente nasce maior que o projeto, e
    em tela menor o conteúdo fica inalcançável.

    Foi assim que uma única linha de quatro botões com distribuição homogênea
    ("Deixar o jogo controlar a vibração" no meio) passou a responder por 1004
    dos 1066px de largura mínima da janela inteira, sem nada acusar. Medida de
    LEGIBILIDADE-01 depois da realocação e com a fonte na escala que sai: a aba
    mais larga é a Lightbar, com 1110px para uma janela de 1180px.
    """
    builder, _root = _montar()
    notebook = builder.get_object("main_notebook")

    largas = []
    for i in range(notebook.get_n_pages()):
        page = notebook.get_nth_page(i)
        rotulo = notebook.get_tab_label_text(page) or f"#{i}"
        largura, _ = page.get_preferred_width()
        if largura > LARGURA:
            largas.append(f"{rotulo} ({largura}px)")

    assert not largas, (
        f"abas mais largas que os {LARGURA}px com que a janela abre: "
        f"{', '.join(largas)}. Procure caixa com distribuição homogênea "
        "contendo um rótulo longo: ela dá a TODOS os filhos a largura do "
        "maior, e não há rolagem horizontal para absorver."
    )


def test_a_janela_inteira_cabe_na_largura_de_projeto() -> None:
    """O mesmo, na soma — pega também cabeçalho e rodapé, que ficam fora do
    notebook. O cabeçalho é o caso perigoso: com quatro controles, a fita de
    chips, o badge de edição e o aviso de vibração dividiam UMA linha com a
    marca e exigiam 1597px (1893px com a fonte em +3). Por isso ele passou a
    ser vertical, com a fita em faixa própria."""
    _builder, root = _montar()

    largura, _ = root.get_preferred_width()

    assert largura <= LARGURA, (
        f"o conteúdo pede {largura}px de largura e a janela abre com "
        f"{LARGURA}px ({largura - LARGURA}px a mais)"
    )


def test_card_de_controle_cabe_na_faixa_que_a_aba_status_da() -> None:
    """O card de UM controle tem de caber na altura que a aba Status lhe dá.

    Os cards não estão no glade (nascem em `_sync_status_cards`), então os
    dois testes acima não os enxergam — e foi por aí que a aba voltou a
    precisar de rolagem: empilhado em seis blocos de largura total, o card
    pedia 457px para uma faixa de ~429px, e giroscópio e touchpad ficavam
    abaixo do corte em toda sessão com 2 controles (o caso normal desta casa).
    A medida é feita com TODOS os módulos de sensor acesos, que é o card mais
    alto que a aba consegue produzir.
    """
    builder, root = _montar()
    slot = builder.get_object("status_players_slot")
    card = ControllerCard(compact=True)  # compact = 2+ controles, lado a lado
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.START)
    slot.attach(card, 0, 0, 1, 1)
    # A janela é forçada ao tamanho com que ABRE: é essa alocação — e não a
    # altura natural do conteúdo — que decide quanto sobra para os cards.
    janela = root.get_toplevel()
    janela.set_size_request(LARGURA, ALTURA_JANELA)
    janela.show_all()
    janela.resize(LARGURA, ALTURA_JANELA)
    card.update(_ENTRY_COMPLETO, _ESTADO_COMPLETO)
    while Gtk.events_pending():
        Gtk.main_iteration()

    faixa = builder.get_object("status_players_scroll").get_allocated_height()
    pedido = card.get_preferred_height_for_width(LARGURA // 2)[0]

    assert pedido <= faixa, (
        f"o card pede {pedido}px e a aba Status só tem {faixa}px de faixa "
        f"({pedido - faixa}px a mais): o rodapé do card (giroscópio, "
        "touchpad, botões) volta a ficar abaixo do corte da janela"
    )


def test_card_de_um_controle_so_tambem_cabe_na_faixa() -> None:
    """O MESMO orçamento vale para o card sozinho — e ele é o mais alto.

    O teste acima mede o card `compact=True`, que só existe quando há 2+
    controles lado a lado. Com UM controle o slot vira uma coluna só e o card
    passa a usar `STICK_SIZE_SINGLE`, ficando mais alto que o compacto — o
    caminho mais comum de quem tem um controle só era justamente o que
    ninguém aferia, e a aba voltava a cortar os botões abaixo da dobra.
    """
    builder, root = _montar()
    slot = builder.get_object("status_players_slot")
    card = ControllerCard(compact=False)  # compact=False = UM controle
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.START)
    slot.attach(card, 0, 0, 1, 1)
    janela = root.get_toplevel()
    janela.set_size_request(LARGURA, ALTURA_JANELA)
    janela.show_all()
    janela.resize(LARGURA, ALTURA_JANELA)
    card.update(_ENTRY_COMPLETO, _ESTADO_COMPLETO)
    while Gtk.events_pending():
        Gtk.main_iteration()

    faixa = builder.get_object("status_players_scroll").get_allocated_height()
    # Um controle só ocupa a largura inteira do slot, não a metade.
    pedido = card.get_preferred_height_for_width(LARGURA)[0]

    assert pedido <= faixa, (
        f"com UM controle o card pede {pedido}px e a aba Status só tem "
        f"{faixa}px ({pedido - faixa}px a mais): os botões voltam a ficar "
        "abaixo do corte da janela"
    )


def test_a_faixa_de_microfone_cheia_nao_come_a_faixa_dos_cards() -> None:
    """MIC-FAIXA-01: a faixa do rodapé é permanente, então ela cobra altura.

    E cobra a altura de QUEM: o `status_players_scroll` é o irmão que expande,
    logo cada pixel da faixa sai da área dos cards. Com quatro controles são
    duas linhas de faixa (grade de 2 colunas), e é essa a medida que este
    teste trava — a versão vazia do glade não custa quase nada e esconderia
    o problema.

    Medido ao escrever: faixa de 48px, banda de 391px, card compacto de 382px.
    O teste morde se a faixa engordar (um botão de 34px por linha, um título
    em linha própria, texto que quebre em duas linhas) a ponto de o card não
    caber — que é a rolagem que a LEGIBILIDADE-01 tirou da aba.
    """
    builder, root = _montar()
    slot_mic = builder.get_object("status_mic_slot")
    for pos in range(4):
        linha = _LinhaMic(f"Controle {pos + 1} — BT")
        linha.aplicar(
            DiagnosticoMic(
                motivo=MOTIVO_PONTE_DESLIGADA,
                texto=(
                    "Por rádio o DualSense não publica placa de áudio: o som "
                    "dele vem em quadros Opus dentro dos reports HID."
                ),
                cura=CURA_PONTE_BT,
            )
        )
        slot_mic.attach(linha.box, pos % 2, pos // 2, 1, 1)
        linha.box.show_all()
    slot = builder.get_object("status_players_slot")
    cards = []
    for pos in range(4):
        card = ControllerCard(compact=True)
        card.set_hexpand(True)
        card.set_valign(Gtk.Align.START)
        slot.attach(card, pos % 2, pos // 2, 1, 1)
        cards.append(card)
    janela = root.get_toplevel()
    janela.set_size_request(LARGURA, ALTURA_JANELA)
    janela.show_all()
    janela.resize(LARGURA, ALTURA_JANELA)
    for card in cards:
        card.update(_ENTRY_COMPLETO, _ESTADO_COMPLETO)
    while Gtk.events_pending():
        Gtk.main_iteration()

    faixa = builder.get_object("status_players_scroll").get_allocated_height()
    pedido = cards[0].get_preferred_height_for_width(LARGURA // 2)[0]

    assert pedido <= faixa, (
        f"com a faixa de microfone cheia (4 controles) o card pede {pedido}px "
        f"e a aba Status só tem {faixa}px ({pedido - faixa}px a mais): a "
        "faixa do rodapé engordou além do que os cards têm para dar"
    )


def test_dois_cards_lado_a_lado_cabem_na_largura_da_janela() -> None:
    """A aba Status é a única cujo conteúdo NÃO está no glade — e era o único
    orçamento de largura que ninguém aferia.

    Com 2+ controles o `status_players_slot` vira uma grade de DUAS COLUNAS
    homogêneas, e a rolagem do `status_players_scroll` é horizontal `never`:
    a largura de dois cards sobe somada até a janela. Nesta casa o caso normal
    é quatro controles — que é a mesma largura de dois, em 2x2.

    É esta conta que decidiu o desenho do card em LEGIBILIDADE-01: com os
    analógicos numa faixa só deles e o estado de cada sensor ao LADO do título,
    o card pedia 588px com a fonte em +3, e dois deles não cabiam em 1180. Com
    os analógicos na faixa de baixo (o pedido da mantenedora) e o estado embaixo
    do desenho, ele pede 485px.
    """
    builder, root = _montar()
    slot = builder.get_object("status_players_slot")
    for coluna in (0, 1):
        card = ControllerCard(compact=True)
        card.set_hexpand(True)
        card.set_valign(Gtk.Align.START)
        slot.attach(card, coluna, 0, 1, 1)
        card.update(_ENTRY_COMPLETO, _ESTADO_COMPLETO)
    janela = root.get_toplevel()
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    aba = builder.get_object("tab_status_box")
    largura, _ = aba.get_preferred_width()

    assert largura <= LARGURA, (
        f"a aba Status com dois controles pede {largura}px e a janela abre "
        f"com {LARGURA}px ({largura - LARGURA}px a mais): sem rolagem "
        "horizontal, a janela nasce maior que o projeto"
    )
