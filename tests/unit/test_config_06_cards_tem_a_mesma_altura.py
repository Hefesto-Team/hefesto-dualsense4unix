"""CONFIG-06 — cards de conteúdo diferente têm a MESMA altura alocada.

Não é estética. Um 8BitDo pede duas linhas que um DualSense não pede (o modo em
que foi ligado e o desenho dos botões), e uma fileira de cards desencontrados lê
como erro de montagem: a pessoa procura o que quebrou em vez de ler a tela.

O QUE ESTE PORTÃO MEDE, E POR QUE ELE PRECISA DE GTK DE VERDADE
----------------------------------------------------------------

Altura ALOCADA, depois de `show_all()` e do laço assentar. Altura PEDIDA
(`get_preferred_height`) não serve: ela é do card sozinho, e o que esta sprint
promete é sobre o card DENTRO da grade — a igualdade nasce da negociação entre
o `valign=FILL` de cada card e o `row_homogeneous` do `Gtk.Grid`, e nenhuma das
duas metades aparece numa medida isolada.

`exigir_gi_real()` é a primeira linha do módulo e vem antes de qualquer import de
`gi`: `pytest.importorskip("gi")` ACEITA um stub plantado por outro arquivo de
teste, e um stub responde "sim, tenho GTK" e mede zero.

AS MORDIDAS, EXERCIDAS EM 22/08/2026 — E O QUE ELAS ENSINARAM
--------------------------------------------------------------

1. **`row_homogeneous(False)` na grade deste molde.** Reprovou
   `test_cards_de_fileiras_diferentes_tambem_se_igualam` com `[224, 224, 224,
   475, 475]` — 251px de degrau entre a primeira e a segunda fileira. E NÃO
   reprovou o teste de dois cards: numa fileira só, o `valign=FILL` sozinho já
   iguala, porque a altura da linha é a do card mais alto. As duas metades da
   receita fazem trabalhos diferentes, e é por isso que há dois testes.
2. **`Gtk.Align.START` no lugar do `FILL` do `ExternalCard`** — que é o que o
   grid de cards da aba Status faz, e o que a sprint avisa para NÃO copiar.
   Reprovou TRÊS dos quatro testes, o de dois cards com `[189, 440]`.
3. **O espaçador antes de "Jogador:".** Reprovou `test_o_seletor_de_jogador_
   ancora_no_rodape` com `[188, 439]` — 251px de diferença no pé do bloco. Aqui
   veio a lição que muda o código: o espaçador tem DUAS expansões, o
   `set_vexpand(True)` do widget e o `expand=True` do `pack_start`, e tirar
   qualquer uma sozinha NÃO reprova — o `Gtk.Box` do GTK3 honra as duas, então
   uma cobre a outra. A mordida só morde tirando as duas. Ficaram as duas no
   código: uma redundância que o teste conhece vale mais que uma linha
   silenciosamente inerte.
4. **`("macos", "macOS")` na lista de modos.** Reprovou
   `test_todo_texto_do_card_passa_no_portao_de_redacao` — é a razão pela qual o
   rótulo do quarto modo é "Apple".
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("altura dos cards da seção Os controles")

from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    COLUNAS,
    _ESPACAMENTO,
)
from hefesto_dualsense4unix.app.widgets.external_card import (
    DadosDoControle,
    ExternalCard,
)

#: A largura com que a janela abre, do próprio glade. Não é constante copiada:
#: `test_config_01_a_aba_nasce_vazia` a lê do XML pelo mesmo motivo — um número
#: duplicado vira mentira no dia em que a janela mudar de tamanho.
_LARGURA_DA_JANELA = 1180

#: A largura que a grade recebe na janela real: 1180px de janela menos o cromo,
#: as margens da moldura de seção e a barra de rolagem vertical. Arredondado para
#: baixo, porque medir com folga esconde exatamente o que se quer ver.
_LARGURA_DA_GRADE = 1080

RAIZ = Path(__file__).resolve().parents[2]

#: O card curto: um DualSense adotado. Duas linhas (cor e jogador).
_CURTO = DadosDoControle(
    chave="aabbcc0000d8",
    titulo="Jogador 1",
    subtitulo="Sony · cabo",
    uniq="aabbcc0000d8",
    slot=1,
    adotado=True,
    cor_lida="Cosmic Red",
    no_cabo=True,
    endereco="aabbcc0000d8",
)

#: O card comprido: um 8BitDo. Quatro linhas (cor, modo, botões e jogador).
_COMPRIDO = DadosDoControle(
    chave="e8473a000007",
    titulo="Jogador 5",
    subtitulo="Nintendo · Bluetooth",
    uniq="e8473a000007",
    slot=5,
    adotado=False,
    modo="switch",
    endereco="e8473a000007",
)


#: O card que mostra a LISTA de cor: nada lido do aparelho e nada declarado.
#: É onde moram os sete rótulos de cor e o campo livre, que nenhum dos outros
#: dois exercita.
_SEM_COR = DadosDoControle(
    chave="aabbcc0000a1",
    titulo="Sem número ainda",
    subtitulo="Sony · Bluetooth",
    uniq="aabbcc0000a1",
    adotado=True,
    endereco="aabbcc0000a1",
)


def _grade_montada(dados: list[DadosDoControle]) -> tuple[Any, list[Any]]:
    """A grade da seção, montada como a seção a monta, numa janela offscreen.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas, e uma `Gtk.Window` fica 1x1 para sempre — a armadilha está escrita
    em `docs/process/COMO-OLHAR-A-TELA.md` e já custou caro duas vezes.
    """
    grade = Gtk.Grid()
    grade.set_column_spacing(_ESPACAMENTO)
    grade.set_row_spacing(_ESPACAMENTO)
    grade.set_column_homogeneous(True)
    grade.set_row_homogeneous(True)
    cards = []
    for indice, item in enumerate(dados):
        card = ExternalCard(item)
        cards.append(card)
        grade.attach(card, indice % COLUNAS, indice // COLUNAS, 1, 1)

    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(grade)
    janela.set_size_request(_LARGURA_DA_GRADE, -1)
    janela.show_all()
    _assentar()
    return grade, cards


def _assentar() -> None:
    """Roda o laço até ele parar de ter o que fazer.

    Sem isto, `get_allocated_height` devolve o 1 do widget recém-realizado — e o
    teste passaria comparando 1 com 1, que é o portão virando carimbo.
    """
    for _ in range(200):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()


def test_dois_cards_de_conteudo_diferente_tem_a_mesma_altura() -> None:
    """A invariante da sprint, medida na alocação e não na promessa."""
    _grade, cards = _grade_montada([_CURTO, _COMPRIDO])
    alturas = [card.get_allocated_height() for card in cards]

    assert min(alturas) > 1, (
        f"instrumento inválido: os cards não foram alocados ({alturas}). "
        "Sem alocação de verdade este teste compara 1 com 1 e nunca reprova."
    )
    assert alturas[0] == alturas[1], (
        f"cards de alturas diferentes na mesma fileira: {alturas}. O curto tem "
        "duas linhas e o comprido tem quatro; sem o `valign=FILL` de cada card "
        "mais o `row_homogeneous` da grade, a fileira sai desencontrada e lê "
        "como erro de montagem."
    )


def test_cards_de_fileiras_diferentes_tambem_se_igualam() -> None:
    """A mesa desta casa é de CINCO, e cinco não cabem em três colunas.

    Com duas fileiras, quem iguala as alturas entre elas é o `row_homogeneous` —
    a metade da receita que o `valign` sozinho não cobre.
    """
    mesa = [_CURTO, _CURTO, _CURTO, _CURTO, _COMPRIDO]
    _grade, cards = _grade_montada(mesa)
    alturas = [card.get_allocated_height() for card in cards]

    assert min(alturas) > 1, f"instrumento inválido: {alturas}"
    assert len(set(alturas)) == 1, (
        f"a segunda fileira não casou com a primeira: {alturas}. Com cinco "
        f"cards em {COLUNAS} colunas há duas fileiras, e o card comprido caiu "
        "na segunda."
    )


def test_o_seletor_de_jogador_ancora_no_rodape() -> None:
    """"Jogador:" fica na MESMA altura de tela nos dois cards.

    É o `margin-top:auto` do desenho, e no GTK ele é um `Gtk.Box` vazio com
    `vexpand=True` antes do último bloco. Sem ele, o bloco do jogador do card
    curto sobe e a fileira ganha um degrau — os cards teriam a mesma altura e
    ainda assim leriam como desalinhados.
    """
    _grade, cards = _grade_montada([_CURTO, _COMPRIDO])
    bases = []
    for card in cards:
        corpo = card.get_child()
        rodape = corpo.get_children()[-1]
        alocacao = rodape.get_allocation()
        bases.append(alocacao.y + alocacao.height)

    assert min(bases) > 1, f"instrumento inválido: {bases}"
    assert abs(bases[0] - bases[1]) <= 2, (
        f"o bloco 'Jogador:' terminou em alturas diferentes: {bases}. O "
        "espaçador expansível antes dele é o que o ancora no rodapé de TODOS os "
        "cards, inclusive nos que têm duas linhas a menos."
    )


def test_um_card_cabe_na_largura_de_uma_coluna() -> None:
    """O card não pode empurrar a janela — a rolagem horizontal não existe.

    Três colunas mais os dois vãos têm de caber em `_LARGURA_DA_GRADE`. Se um
    card sozinho já pede mais que um terço disso, a aba inteira passa a pedir
    mais que a janela, e o portão de largura de CONFIG-01 reprova depois — com
    a causa a duas seções de distância de onde ela nasceu.
    """
    card = ExternalCard(_COMPRIDO)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _assentar()

    minima, _natural = card.get_preferred_width()
    teto = (_LARGURA_DA_GRADE - (COLUNAS - 1) * _ESPACAMENTO) // COLUNAS

    assert minima <= teto, (
        f"um card pede {minima}px de largura mínima e a coluna tem {teto}px "
        f"({minima - teto}px a mais). Com {COLUNAS} colunas isso sobe intacto "
        "até a largura mínima da janela."
    )


def test_todo_texto_do_card_passa_no_portao_de_redacao() -> None:
    """O texto do CARD, e não só o da aba vazia, sob as regras de redação.

    O buraco que este teste fecha é medido: `test_config_a_palavra_de_tela_da_
    aba_montada` monta a aba de verdade, mas monta-a SEM daemon — e sem daemon
    esta seção mostra o estado vazio. Nenhum dos rótulos do card ("Cor:",
    "Modo:", "Apple", "Vermelho") atravessa aquele portão, porque nenhum deles
    chega a existir na árvore que ele anda.

    As regras são as de lá, importadas do mesmo módulo — nunca copiadas. Duas
    listas de jargão divergem na primeira edição, e essa é a dívida que o portão
    irmão existe para não criar.
    """
    from tests.unit.test_config_a_palavra_de_tela_da_aba_montada import (
        _textos_da_arvore,
        _validador,
    )

    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    for dados in (_CURTO, _COMPRIDO, _SEM_COR):
        caixa.pack_start(ExternalCard(dados), False, False, 0)
    janela.add(caixa)
    janela.show_all()
    _assentar()

    textos = _textos_da_arvore(caixa)
    assert len(textos) > 20, (
        f"instrumento inválido: só {len(textos)} textos na árvore de três cards"
    )

    banido: dict[str, str] = _validador().JARGAO_BANIDO
    achados = []
    for origem, texto in textos:
        primeira = texto.strip()[:1]
        if primeira.isalpha() and primeira.islower():
            achados.append(f"{origem}: {texto!r} começa em minúscula")
        for termo, troca in banido.items():
            if termo.lower() in texto.lower():
                achados.append(f"{origem}: {texto!r} tem {termo!r} — use {troca!r}")

    assert not achados, "redação do card fora da regra:\n  " + "\n  ".join(achados)


def test_a_secao_monta_a_mesa_de_cinco_e_ela_cabe_na_janela() -> None:
    """A costura inteira, com o fixture da mesa de CINCO desta casa.

    Os quatro testes acima medem o card; este mede a SEÇÃO — a grade que ela
    monta, alimentada pelo mesmo dublê que a captura de tela usará. Sem ele, a
    prova pararia na peça e a montagem ficaria fora do alcance: é o defeito de
    portão que esta casa mais paga, o verde que olha para o lugar errado.

    `_controles_leitor` é o ponto de injeção da seção, irmão do `_mesa_leitor` de
    CONFIG-02. Ele existe pelo mesmo motivo: sem dublê, montar a aba num teste
    conversaria com o daemon vivo da máquina de quem roda a suíte.

    MORDIDA: troquei `COLUNAS` de 3 para 5 (que é o que o desenho mostra) e a
    largura mínima da página subiu para 1305px contra os 1180 da janela —
    reprovou, e é exatamente por isso que a grade tem três colunas.
    """
    import json

    from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG, ConfigActionsMixin
    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    fixture = json.loads(
        (RAIZ / "tests" / "fixtures" / "inventario_externos.json").read_text(
            encoding="utf-8"
        )
    )

    class _HospedeiroComMesa(ConfigActionsMixin):
        def __init__(self, builder: Any) -> None:
            self.builder = builder
            # A marca da bancada de retrato, para a seção não falar com o daemon.
            self._mesa_leitor = lambda: None
            self._controles_leitor = lambda: fixture

    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    _HospedeiroComMesa(builder).install_config_tab()

    pagina = builder.get_object("scroll_tab_config_box")
    pai = pagina.get_parent()
    if pai is not None:
        pai.remove(pagina)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(pagina)
    janela.show_all()
    _assentar()

    secao = builder.get_object(ABA_CONFIG).get_children()[1]
    cards = _cards_de(secao)

    assert len(cards) == 5, (
        f"a mesa do fixture tem quatro adotados mais um externo e a seção "
        f"montou {len(cards)} cards"
    )
    titulos = [card.dados.titulo for card in cards]
    assert len(set(titulos)) == len(titulos), (
        f"dois cards com o mesmo título: {titulos}. O controle cujo "
        "`player_slot` é nulo não pode herdar o número do vizinho — null "
        "honesto vale mais que número errado (NUMA-05)."
    )

    alturas = [card.get_allocated_height() for card in cards]
    assert min(alturas) > 1, f"instrumento inválido: {alturas}"
    assert len(set(alturas)) == 1, f"a mesa saiu desencontrada: {alturas}"

    largura, _natural = pagina.get_preferred_width()
    assert largura <= _LARGURA_DA_JANELA, (
        f"a aba com a mesa de cinco pede {largura}px e a janela abre com "
        f"{_LARGURA_DA_JANELA}px. Sem rolagem horizontal, esse mínimo sobe "
        "intacto até a janela."
    )


def _cards_de(raiz: Any) -> list[Any]:
    """Todo `ExternalCard` da árvore, na ordem em que a grade os guarda."""
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        if isinstance(widget, ExternalCard):
            achados.append(widget)
            continue
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados
