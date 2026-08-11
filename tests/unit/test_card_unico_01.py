"""CARD-ÚNICO-01 — o frame "Estado" apaga e o que sobra dele entra no card.

As cinco anotações do print dela, em ordem de leitura:

1. *"apaga estado, a bateria fica ao lado do hertz do giroscópio até o final e
   adicionamos as duas linhas"*;
2. *"conexão e perfil acima do giroscópio hertz — sem o conexão"*;
3. *"unir os dois blocos num só"*;
4. *"remover o não ajustado"*;
5. *"L3 e R3 saem do X: e vão ficar no centro do desenho do analógico com
   transparência 70% e grande ao fundo"*.

Toda medida de geometria é feita com a janela montada e ALOCADA: widget sem
alocação devolve 1x1, e uma asserção sobre 1x1 passa com qualquer desenho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("card único 01")

import math
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.status_actions import (
    StatusActionsMixin,
)
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_SPEAKER_SEM_DADO,
    TITULO_SPEAKER,
    ControllerCard,
)
from hefesto_dualsense4unix.gui.widgets.stick_preview_gtk import (
    BORDA_COLOR,
    FUNDO_COLOR,
    StickPreviewGtk,
)
from tests.unit.test_status_faixa_blocos import _ENTRY, _ESTADO


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_janelas_vivas: list[Any] = []


#: A tela dela maximizada. O número importa: ele é MAIOR que o
#: `LARGURA_CARD_ELASTICA`, e é isso que permite medir o corte do teto. Numa
#: janela do tamanho do teto, um teste de teto passa com ou sem o corte.
LARGURA_DA_TELA_DELA = 1920


def _card(*, compact: bool = False, largura: int = LARGURA_DA_TELA_DELA) -> Any:
    """Card montado e ALOCADO na largura da tela dela, com dados completos."""
    from hefesto_dualsense4unix.app.mic_monitor import LeituraMic

    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, _ESTADO, LeituraMic(nivel=0.6, muted=False))
    janela.resize(largura, 900)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


class _Host(StatusActionsMixin):  # type: ignore[misc]
    """A aba Status com o mínimo que estes dois métodos precisam.

    Sem IPC e sem tique: o que se afere aqui é ciclo de vida de widget, e um
    daemon dublado só acrescentaria caminho para o teste errar de lugar.
    """

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(MAIN_GLADE))
        self._status_cards: dict[Any, Any] = {}
        self._status_card_keys: list[Any] = []
        root = self.builder.get_object("root_box")
        pai = root.get_parent()
        if pai is not None:
            pai.remove(root)
        self.janela = Gtk.OffscreenWindow()
        self.janela.add(root)
        self.janela.set_size_request(1180, 800)
        self.janela.show_all()
        _janelas_vivas.append(self.janela)
        self._assentar()

    def _get(self, nome: str) -> Any:
        return self.builder.get_object(nome)

    @staticmethod
    def _assentar() -> None:
        while Gtk.events_pending():
            Gtk.main_iteration()

    def sincronizar(self, quantos: int) -> None:
        """Recria os cards como a aba faz quando o conjunto muda."""
        slot = self._get("status_players_slot")
        self._rebuild_status_cards(slot, [(f"c{i}",) for i in range(quantos)])
        self._assentar()


# ---------------------------------------------------------------------------
# Entrega 1 — o frame "Estado" apaga, e o card diz o que ele dizia
# ---------------------------------------------------------------------------


def test_o_frame_estado_some_com_um_controle_e_volta_sem_card_unico() -> None:
    """*"apaga estado"* — e ele só apaga quando alguém o substitui.

    A regra tem três casos e os três importam:

    * **um controle** — o frame some inteiro. O card passou a dizer perfil,
      daemon e bateria, e mantê-lo seria a repetição que ela apontou;
    * **nenhum controle** — o frame VOLTA, porque não há card nenhum para
      falar. É justamente o momento em que a aba mais precisa explicar (o
      daemon parado, o botão da rota de som), e uma aba em branco ali seria
      pior que o frame repetido;
    * **dois ou mais** — o frame volta porque perfil ativo e daemon são fatos
      GLOBAIS. Num card por controle eles apareceriam duplicados, que é
      exatamente o defeito que a bateria teve e que a STATUS-SIMETRIA-02
      curou.

    Mordida: trocar o `compact or not keys` do `_rebuild_status_cards` por um
    `False` fixo. O caso do meio cai — a aba fica muda sem controle nenhum.
    """
    host = _Host()
    frame = host._get("frame_status_estado")

    host.sincronizar(1)
    assert frame.get_visible() is False, (
        "com UM controle o frame Estado tem de sair da tela: o card diz tudo "
        "o que ele dizia"
    )

    host.sincronizar(2)
    assert frame.get_visible() is True, (
        "com 2+ controles perfil e daemon são fatos globais e voltam para o "
        "frame — num card por controle eles apareceriam repetidos"
    )

    host._clear_status_cards()
    host._assentar()
    assert frame.get_visible() is True, (
        "sem card nenhum o frame Estado é a ÚNICA voz da aba"
    )


def test_o_card_unico_mostra_perfil_e_daemon_e_o_compacto_nao() -> None:
    """As duas linhas novas, e por que elas não entram no card compacto.

    `Conexão:` e `Transporte:` NÃO vêm junto, e o motivo não é espaço: a
    conexão já está no cabeçalho da janela e o transporte no título deste
    mesmo card ("Controle 1 — USB"). Era o frame Estado dizendo o que o resto
    da aba já dizia.

    Mordida: tirar o `if self._compact: return` do `_montar_estado_global`.
    Dois controles passam a mostrar "Perfil ativo" duas vezes na tela e a
    última asserção cai.
    """
    unico = _card()
    dois = _card(compact=True)

    assert unico._linha_estado_global is not None
    assert unico._perfil_ativo_label is not None
    assert unico._daemon_label is not None

    unico.definir_estado_global("ação", "Ligado")
    assert unico._perfil_ativo_label.get_text() == "ação"
    assert unico._daemon_label.get_text() == "Ligado"

    assert dois._linha_estado_global is None, (
        "perfil ativo e daemon são fatos GLOBAIS: num card por controle eles "
        "apareceriam repetidos na mesma tela"
    )
    # E o card compacto não explode ao receber a chamada — a aba escreve nos
    # dois sem perguntar qual é qual.
    dois.definir_estado_global("ação", "Ligado")


def test_a_aba_escreve_o_par_global_no_card_e_no_frame_de_uma_vez() -> None:
    """Um escritor só para os dois lugares que mostram perfil e daemon.

    Esta casa tem defeito registrado de *"a config que eu deixo nunca é
    respeitada"* cuja causa foi três escritores sem dono. Aqui o par tem duas
    casas (o card e o frame de fallback) e UM ponto de escrita.

    E ele alcança o card que nasce DEPOIS: o `_render_state` escreve o par
    antes de sincronizar os cards, então sem o espelho o card recém-criado
    passaria um tique inteiro mostrando "Nenhum / Consultando...".

    Mordida: trocar `_set_estado_global` de volta por `_set_label` em
    qualquer um dos oito pontos de escrita — o card para de acompanhar.
    """
    host = _Host()
    host._set_estado_global("status_active_profile", "fps")
    host._set_estado_global("status_daemon", "Reconectando")

    assert host._get("status_active_profile").get_text() == "fps"
    assert host._get("status_daemon").get_text() == "Reconectando"

    # O card nasce DEPOIS da escrita, e mesmo assim nasce certo.
    host.sincronizar(1)
    card = next(iter(host._status_cards.values()))
    assert card._perfil_ativo_label.get_text() == "fps"
    assert card._daemon_label.get_text() == "Reconectando"


def test_a_bateria_do_card_unico_nao_desenha_o_proprio_texto() -> None:
    """O número sai da barra e vira rótulo ao lado dela.

    O `GtkProgressBar` desenha o próprio texto CENTRADO. Numa barra larga o
    "80 %" fica a centenas de pixels de cada borda — é o defeito que ela
    apontou nas barras de L2/R2, e é por isso que a barra do frame Estado já
    tinha `show-text=False` desde a ESTADO-TRES-LINHAS-01.

    A barra continua recebendo `set_text`: ela é a DONA do valor, e é o que
    `get_text()` lê. Quem espelha no rótulo é `_update_bateria`, e é o único.

    Mordida: religar o `set_show_text(True)` no ramo do card único.
    """
    unico = _card()

    assert unico._battery_bar.get_show_text() is False
    assert unico._battery_pct_label is not None
    assert unico._battery_pct_label.get_text() == unico._battery_bar.get_text()
    assert unico._battery_pct_label.get_text() == "80 %"


def test_a_bateria_fica_a_direita_e_o_giroscopio_a_esquerda_na_mesma_linha() -> None:
    """*"a bateria fica ao lado do hertz do giroscópio"* — na mesma linha.

    E o slot do giroscópio fica SEMPRE visível, mesmo com o rótulo dele
    escondido (ele só aparece com o espelho de motion ativo). Um widget
    oculto não ocupa espaço: sem o slot, a bateria saltaria da direita para a
    esquerda no instante em que o giroscópio parasse de espelhar — reflow
    visível a cada troca de modo. É o mesmo mecanismo do `_gyro_slot` da
    linha de cima, e pelo mesmo motivo.

    Mordida: empacotar o `_motion_label` direto na faixa, sem o slot. Com o
    dublê deste teste (que não espelha motion) a bateria encosta na esquerda
    e a asserção de posição cai.
    """
    unico = _card()
    faixa = unico._faixa_gyro_bateria
    largura_da_faixa = faixa.get_allocated_width()
    bateria = unico._battery_row.get_allocation()

    assert largura_da_faixa > 1, "faixa sem alocação: a medida não vale nada"
    assert bateria.x > largura_da_faixa / 2, (
        f"a bateria começa em x={bateria.x} numa faixa de {largura_da_faixa}px "
        "— ela devia estar na metade DIREITA, com o giroscópio à esquerda"
    )


# ---------------------------------------------------------------------------
# Entrega 2 — o "· não ajustado" sai do título do alto-falante
# ---------------------------------------------------------------------------


def test_o_titulo_do_alto_falante_nao_diz_nao_ajustado() -> None:
    """*"remover o não ajustado"*.

    Das duas opções escritas na sprint, esta é a literal: o sufixo some no
    estado SEM DADO e continua quando há valor (`Alto-falante · 71 %`). A
    outra — tirar o sufixo sempre — obrigaria o valor a achar um terceiro
    lugar, e os três candidatos já foram medidos na ALINHA-DUAS-LINHAS-01;
    todos cobram pixel numa faixa que já é a mais apertada da aba.

    O `_speaker_label` continua recebendo o texto CRU, inclusive "não
    ajustado": ele é o dono do valor e é o que os testes leem. O que mudou é
    só o que a moldura mostra.

    Mordida: voltar o `f"Alto-falante · {texto}"` incondicional.
    """
    unico = _card()

    unico._escrever_valor_do_speaker(TEXTO_SPEAKER_SEM_DADO)
    assert unico._speaker_titulo.get_text() == TITULO_SPEAKER
    assert TEXTO_SPEAKER_SEM_DADO not in unico._speaker_titulo.get_text()
    # O dono do valor não perde o texto — quem o esconde é a moldura.
    assert unico._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO

    unico._escrever_valor_do_speaker("71 %")
    assert unico._speaker_titulo.get_text() == f"{TITULO_SPEAKER} · 71 %"


# ---------------------------------------------------------------------------
# Entrega 3 — L3 e R3 viram marca d'água no centro do analógico
# ---------------------------------------------------------------------------


def _pintar(label: str, lado: int = 120) -> Any:
    """Renderiza o desenho do analógico numa superfície de verdade.

    É a única forma honesta de aferir um `DrawingArea`: o desenho é Cairo, e
    perguntar ao widget "você tem um rótulo?" não prova que ele foi PINTADO.
    """
    preview = StickPreviewGtk(label=label)
    preview.set_size_request(lado, lado)
    janela = Gtk.OffscreenWindow()
    janela.add(preview)
    janela.set_size_request(lado, lado)
    janela.show_all()
    _janelas_vivas.append(janela)
    while Gtk.events_pending():
        Gtk.main_iteration()

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    ctx = cairo.Context(surface)
    preview._on_draw(preview, ctx)
    surface.flush()
    return surface


def _tinta_fora_do_fundo(surface: Any, lado: int) -> int:
    """Quantos pixels do MIOLO não são a cor de fundo.

    O miolo (o quadrado central) exclui a borda do círculo de propósito: ela
    é pintada com ou sem marca d'água, e contá-la afogaria a diferença que se
    quer medir.
    """
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    fundo = tuple(round(c * 255) for c in FUNDO_COLOR)
    inicio, fim = lado // 3, 2 * lado // 3
    tinta = 0
    for y in range(inicio, fim):
        for x in range(inicio, fim):
            base = y * stride + x * 4
            # ARGB32 em little-endian: os bytes saem B, G, R, A.
            b, g, r = dados[base], dados[base + 1], dados[base + 2]
            if (r, g, b) != fundo:
                tinta += 1
    return tinta


def test_a_marca_dagua_e_realmente_pintada_dentro_do_circulo() -> None:
    """*"L3 e R3 (...) no centro do desenho do analógico (...) ao fundo"*.

    Este teste RENDERIZA. Perguntar ao widget se ele guardou o rótulo provaria
    só que o construtor funciona — e o rótulo já chegava aqui antes desta
    sprint, sem nunca ser desenhado.

    O método é comparar o mesmo desenho com e sem rótulo e contar a tinta que
    não é fundo no MIOLO. A cruz do centro existe nos dois casos e não
    interfere: ela é a linha de base, e o que se mede é o excedente.

    Mordida: apagar a chamada a `_desenhar_marca_dagua` do `_on_draw`. As duas
    contagens se igualam e a asserção cai.
    """
    lado = 120
    com = _tinta_fora_do_fundo(_pintar("L3", lado), lado)
    sem = _tinta_fora_do_fundo(_pintar("", lado), lado)

    assert com > sem, (
        f"o miolo do desenho tem {com} pixels de tinta com rótulo e {sem} sem "
        "ele: a marca d'água não está sendo pintada"
    )


def test_a_marca_dagua_e_fundo_e_nao_cobre_a_cruz() -> None:
    """A ordem de pintura é a entrega: ela vem ANTES da cruz e do ponto.

    Num alpha de 0,3, um texto desenhado por CIMA não lê como "atrás" — lê
    como sujeira sobre o que o widget existe para mostrar. A prova é de
    ordem, e ordem se prova pelo código-fonte do desenho: a chamada da marca
    d'água tem de aparecer antes do arco da borda.

    Mordida: mover a chamada para depois do ponto do stick.
    """
    import inspect

    fonte = inspect.getsource(StickPreviewGtk._on_draw)
    pos_marca = fonte.index("_desenhar_marca_dagua")
    pos_borda = fonte.index("ctx.arc(cx, cy, raio_externo")
    pos_ponto = fonte.index("ctx.arc(px, py")

    assert pos_marca < pos_borda < pos_ponto, (
        "a marca d'água é FUNDO: ela tem de ser pintada antes da borda, da "
        "cruz e do ponto"
    )


def test_o_tamanho_da_marca_dagua_acompanha_o_desenho() -> None:
    """Nada de literal em px: o card inteiro obedece à escala de fonte dela.

    O desenho do analógico tem dois tamanhos (card único e compacto) e o card
    responde à `theme.escala_fonte()`. Um `set_font_size(28)` ficaria certo
    num dos dois e errado no outro, e quebraria na primeira vez que ela
    mudasse a escala. Derivando do raio ALOCADO, a marca acompanha os dois
    eixos de variação de graça.

    Mordida: trocar `raio * MARCA_DAGUA_FRACAO_DO_RAIO` por um número. O
    desenho grande e o pequeno passam a ter a MESMA tinta e a asserção cai.
    """
    grande = _tinta_fora_do_fundo(_pintar("L3", 180), 180)
    pequeno = _tinta_fora_do_fundo(_pintar("L3", 90), 90)

    assert grande > pequeno * 2, (
        f"a marca d'água rendeu {grande} pixels no desenho grande e "
        f"{pequeno} no pequeno: ela não está acompanhando o tamanho"
    )


#: Fração do raio que delimita o anel onde se procura a "barra quebrada".
#:
#: O piso (0,55) fica FORA do maior glifo medido — a marca d'água de "R3" a
#: 0,95 do raio chega a ~0,50 do raio no canto mais distante — e o teto (0,93)
#: fica dentro da borda, cujo traço vive entre `raio-1` e `raio+1`. No meio
#: desse anel, com o stick centrado, não há NADA a pintar.
ANEL_DA_BARRA = (0.55, 0.93)

#: Tolerância por canal para reconhecer o traço do anel, em 0-255.
#:
#: A distinção não é de lugar, é de OPACIDADE, e a folga entre os dois casos é
#: enorme: o segmento espúrio sai da mesma chamada que a borda, opaco
#: (`set_source_rgb`, ~153 por canal). Tudo o que pode legitimamente cair no
#: anel é translúcido sobre o fundo escuro — a marca d'água a 0,3 dá ~74 e a
#: cruz a 0,35 dá ~79. Vinte de folga separa 153 de 79 sem encostar em nenhum.
TOLERANCIA_DO_TRACO = 20


def _tinta_opaca_da_borda_no_anel(surface: Any, lado: int) -> int:
    """Quantos pixels do ANEL estão pintados com a borda OPACA.

    Ver `ANEL_DA_BARRA` e `TOLERANCIA_DO_TRACO` para o porquê dos números.
    """
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    cx = cy = lado / 2
    raio = lado / 2 - 4
    dentro, fora = (f * raio for f in ANEL_DA_BARRA)
    alvo = tuple(round(c * 255) for c in BORDA_COLOR)
    tinta = 0
    for y in range(lado):
        for x in range(lado):
            dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if not dentro <= dist <= fora:
                continue
            base = y * stride + x * 4
            # ARGB32 em little-endian: os bytes saem B, G, R, A.
            b, g, r = dados[base], dados[base + 1], dados[base + 2]
            canais = zip((r, g, b), alvo, strict=True)
            if all(abs(c - a) <= TOLERANCIA_DO_TRACO for c, a in canais):
                tinta += 1
    return tinta


@pytest.mark.parametrize("label", ["L3", "R3"])
@pytest.mark.parametrize("lado", [90, 120, 180])
def test_a_marca_dagua_nao_deixa_barra_atravessando_o_circulo(
    label: str, lado: int
) -> None:
    """Ela viu e fotografou: uma barra riscando o círculo do L3 e do R3.

    A causa é de ESTADO, não de desenho: `show_text` deixa um ponto corrente
    no fim do glifo, na baseline. O `ctx.arc` da borda, três linhas adiante,
    encontra esse ponto e o Cairo o LIGA ao início do arco com um segmento de
    reta; o `stroke` seguinte pinta o segmento com a cor e a espessura do
    anel. Por isso a barra sempre saía do meio da letra em direção à direita
    do círculo — e por isso ela só apareceu quando a marca d'água nasceu
    (CARD-ÚNICO-01, entrega 3): antes, o `arc` da borda era a primeira coisa
    a tocar o caminho depois do `paint`, e o caminho estava vazio.

    A medida não é de lugar, é de OPACIDADE: no anel entre a letra e a borda,
    com o stick centrado, nada legítimo é pintado OPACO. A marca d'água mora
    em alpha 0,3 e a cruz em 0,35; o segmento espúrio herda o
    `set_source_rgb` da borda e sai cheio.

    Mordida: arrancar o `ctx.new_path()` de `_desenhar_marca_dagua`. Medido
    em 10/08/2026: 31/48/63 pixels opacos no anel para "L3" nos três
    tamanhos, contra 0 com a cura.
    """
    barra = _tinta_opaca_da_borda_no_anel(_pintar(label, lado), lado)

    assert barra == 0, (
        f"{barra} pixels da cor OPACA da borda no anel do desenho {lado}x{lado} "
        f"de {label!r}: há um traço atravessando o círculo — o ponto corrente "
        "deixado por `show_text` está sendo ligado ao início do arco da borda"
    )


# ---------------------------------------------------------------------------
# ROTA-ÓRFÃ-01 — achado desta leva, medido antes de ser curado
# ---------------------------------------------------------------------------


def test_o_botao_da_rota_nao_migra_mais_para_o_card() -> None:
    """SOM-CANAL-01/E3 (02/08/2026): o "Ouvir no controle" DEIXOU de migrar.

    **O registro do que este teste travava antes fica**, porque foi um defeito
    real e medido: com um controle o botão era reparentado para o bloco
    "Alto-falante" do card, e plugar um segundo controle recriava os cards —
    o `child.destroy()` do card antigo deixava o botão ÓRFÃO (`get_parent()
    is None`), vivo mas fora da tela. Ela perdia o "desfazer" da rota no co-op.

    O que mudou: o comando NASCE no card agora, como um dos dois estados do
    seletor de canal. Ela pediu — *"ele deixa de existir como botão isolado.
    Vira o estado 'Todo o som do PC' do seletor"* — e com isso o
    reparenteamento inteiro deixou de fazer sentido: não há mais para onde
    migrar, e o botão do glade fica no berço dele.

    Mordida: devolver o `_speaker_rota_slot` ao card. O botão volta a migrar,
    e volta o risco de ficar órfão na troca de conjunto.
    """
    host = _Host()
    botao = host._get("btn_som_no_controle")
    berco = host._get("status_grid")

    for quantos in (1, 2, 1):
        host.sincronizar(quantos)
        assert botao.get_parent() is berco, (
            f"com {quantos} controle(s) o botão fica no berço: ele não migra "
            "mais para o card, porque o comando agora nasce lá"
        )

    # E o card NÃO oferece mais slot para ele — é isso que impede a migração
    # de voltar por acidente.
    host.sincronizar(1)
    card = next(iter(host._status_cards.values()))
    assert card._speaker_rota_slot is None

def test_os_cards_ficam_um_em_cima_do_outro_e_nao_lado_a_lado() -> None:
    """*"os dois blocos não deveriam estar lado a lado mas um em cima do outro
    de forma que o scroll surgisse pra comportar os diferentes controles"*.

    Isto REVISA a STATUS-GRID-2COL-01, e a decisão antiga não é apagada: ela
    dizia que "empilhado, cada card somava a própria altura e dois já
    estouravam a janela — a aba só respondia com rolagem, justamente o que as
    sprints S3/S5 tiraram das outras abas". A observação continua correta; o
    que mudou foi o julgamento sobre ela, e é dela: a rolagem vertical AQUI é
    aceitável, e ler dois controles lado a lado não é.

    Um card por linha também é o que escala para os quatro jogadores do co-op
    sem espremer nada.

    Mordida: devolver o `colunas = 2 if compact else 1`.
    """
    host = _Host()
    host.sincronizar(2)

    cards = list(host._status_cards.values())
    assert len(cards) == 2

    esquerdo, direito = (c.get_allocation() for c in cards)
    assert esquerdo.x == direito.x, (
        f"os dois cards começam em x diferentes ({esquerdo.x} e {direito.x}): "
        "eles voltaram a ficar lado a lado"
    )
    assert direito.y > esquerdo.y, "o segundo card fica ABAIXO do primeiro"


def test_o_card_compacto_tambem_para_de_esticar_pela_tela_toda() -> None:
    """Empilhado, cada card recebe a janela inteira — e precisa do teto.

    Sem ele, um card de dois controles esticaria por 1900px com ~900px de
    conteúdo: exatamente o buraco que o teto do card único veio curar, e o
    mesmo defeito que ela apontou na STATUS-SIMETRIA-02.

    Mordida: devolver o `not self._compact` ao `do_size_allocate`.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        LARGURA_CARD_ELASTICA,
    )

    assert LARGURA_DA_TELA_DELA > LARGURA_CARD_ELASTICA, (
        "a bancada precisa de uma tela MAIOR que o teto: numa janela do "
        "tamanho do teto, este teste passaria com ou sem o corte"
    )
    card = _card(compact=True)
    assert card.get_allocated_width() == LARGURA_CARD_ELASTICA


def test_a_bateria_do_card_compacto_tambem_nao_desenha_o_proprio_texto() -> None:
    """O empilhamento trouxe de volta o número flutuando no vazio.

    A barra do card compacto ficava com `show-text` LIGADO, e a justificativa
    era medida: com dois cards dividindo a largura em duas colunas, a barra
    era estreita e o texto centrado cabia. Numa coluna só ela ficou larga, e o
    "80 %" voltou para o meio do nada — o defeito que ela apontou nas barras
    de L2/R2.

    Mordida: religar o `set_show_text(True)` para o compacto.
    """
    compacto = _card(compact=True)

    assert compacto._battery_bar.get_show_text() is False
    assert compacto._battery_pct_label is not None
    assert compacto._battery_pct_label.get_text() == compacto._battery_bar.get_text()
