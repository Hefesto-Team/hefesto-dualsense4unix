"""A faixa da aba Status medida como ELA vê: blocos, tetos e vazios.

STATUS-SIMETRIA-02 nasceu de uma frase dela olhando a tela: *"só distanciou
as coisas mas um nome dos analógicos tem 3 linhas outro dois. não tem a parte
do som, o touchpad não tem um espaço próprio, os botões não tão bem
distribuídos e tem vários espaços vazios."* Distanciar não é organizar.

Os testes daqui medem o card MONTADO numa `Gtk.OffscreenWindow` com a largura
da tela dela (1920 maximizada), porque foi assim que os defeitos apareceram:
widget sem alocação devolve 1x1 em tudo, e um teste de geometria sobre ele
passaria com qualquer layout. Cada um deles cai quando a cura correspondente é
arrancada — está escrito no docstring de cada um qual é a mordida.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("status faixa blocos")

from itertools import pairwise
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import (

    LARGURA_BARRA_GATILHO_UNICO,
    LARGURA_CARD_ELASTICA,
    LARGURA_CARD_UNICO,
    LARGURA_GYRO_UNICO,
    TEXTO_SPEAKER_SEM_DADO,
    ControllerCard,
)

#: A largura que a aba Status recebe na tela dela, maximizada em 1920x1080.
#: É esta medida que produziu os "vários espaços vazios": o card esticava até
#: aqui com ~700px de conteúdo dentro.
LARGURA_DA_TELA_DELA = 1870

#: Teto do vão entre dois blocos vizinhos da faixa, em px. Sai do critério de
#: aceite 4 da STATUS-SIMETRIA-02: *"não há faixa de mais de 200 px sem nada
#: entre dois módulos"*. Medido antes da cura: 673px de nada entre o fim do
#: microfone e o começo do grid de botões, e outros 673 do outro lado.
VAO_MAXIMO_ENTRE_BLOCOS = 200

_INPUTS: dict[str, Any] = {
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
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}
_ESTADO: dict[str, Any] = {"native_mode": False}

#: A janela offscreen fica viva numa lista de módulo: o Python coleta a
#: referência local assim que a função retorna, e um card sem toplevel volta a
#: reportar 1x1 no meio da asserção.
_janelas_vivas: list[Any] = []


def _card_na_tela_dela(
    *, compact: bool = False, largura: int = LARGURA_DA_TELA_DELA
) -> Any:
    """Card montado numa janela da largura da tela dela, com todos os dados."""
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


def _faixa(widget: Any) -> tuple[int, int]:
    alloc = widget.get_allocation()
    return (alloc.x, alloc.x + alloc.width)


# ---------------------------------------------------------------------------
# Entrega 1 — o microfone não sai da faixa (MIC-PRESENTE-01/E3)
# ---------------------------------------------------------------------------


def test_a_faixa_nao_muda_de_lugar_quando_o_mic_muda_de_estado() -> None:
    """MIC-PRESENTE-01/E3 — **a diferença tem de ser zero pixel.**

    Este teste substitui a muralha que estava em
    `test_status_cards_sensores.py`, que exigia
    ``card._mic_box.get_visible() is False`` sem sinal: ela AFIRMAVA o defeito
    que a mantenedora relatou, e travava a correção — enquanto existisse, a
    única forma de passar era continuar escondendo o microfone.

    O que importa não é o widget e sim a FAIXA: esconder um bloco de uma caixa
    horizontal muda o lugar de todos os vizinhos, então o microfone sumindo
    não fazia só ele desaparecer — os analógicos pulavam 42px para a direita a
    cada vez que ele saía ou voltava. E por Bluetooth ele sai quase sempre (a
    captura é Opus tunelado em HID, instável), então esse pulo era o estado
    normal da tela dela.

    Duas armadilhas de medição estão desarmadas aqui, e as duas foram
    medidas antes de o teste ficar de pé:

    * o card tem de ser o LARGO (um controle). No compacto, a folga é pequena
      e o `Gtk.Box` não redistribui o suficiente para o pulo aparecer — o
      teste passaria com o `hide()` de volta;
    * cada estado monta a sua própria janela, e o `update` vem DEPOIS do
      `show_all`. Aplicar o estado antes faria o `show_all` revelar de novo um
      bloco que o `hide()` tinha escondido, e o teste voltaria a passar com a
      cura arrancada.
    """

    def geometria(mic: Any) -> dict[str, tuple[int, int]]:
        card = ControllerCard(compact=False)
        janela = Gtk.OffscreenWindow()
        janela.add(card)
        janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
        janela.show_all()
        _janelas_vivas.append(janela)
        card.update(_ENTRY, _ESTADO, mic)
        janela.resize(LARGURA_DA_TELA_DELA, 900)
        while Gtk.events_pending():
            Gtk.main_iteration()
        return {
            nome: _faixa(widget)
            for nome, widget in (
                ("analógico esquerdo", card._stick_left),
                ("analógico direito", card._stick_right),
                ("grid de botões", card._glyph_grid),
                ("miolo da faixa", card._miolo_inferior),
            )
        }

    captando = geometria(LeituraMic(nivel=0.6, muted=False))
    sem_sinal = geometria(None)

    assert captando == sem_sinal, (
        "a faixa mudou de lugar entre o microfone captando e o microfone sem "
        f"sinal: {captando} contra {sem_sinal}"
    )


# ---------------------------------------------------------------------------
# Entrega 5 — o vazio vira margem, não distância entre as coisas
# ---------------------------------------------------------------------------


def test_o_card_de_um_controle_nao_estica_pela_tela_inteira() -> None:
    """Defeito 4 — o card recebia 1870px para ~700px de conteúdo.

    A sobra não sumia: virava buraco DENTRO da faixa (dois vãos de 673px, um
    de cada lado dos analógicos, medidos na captura maximizada). Com teto de
    largura e o card centrado, a mesma sobra vira margem da página.

    SOM-01 trocou o teto RÍGIDO (960px fixos, com ~950px de margem morta na
    tela dela) por um ELÁSTICO: o que este teste cobra agora é o teto de cima,
    e o de baixo está no teste seguinte. Sem os dois lados a medida não vale —
    um card travado em 960 passa por este assert e reprova no outro.

    A mordida: tirar o corte do `do_size_allocate` faz a largura alocada saltar
    para a da janela (1870) e este teste cai.
    """
    card = _card_na_tela_dela()

    largura = card.get_allocated_width()

    assert largura <= LARGURA_CARD_ELASTICA, (
        f"o card de um controle ocupa {largura}px numa tela de "
        f"{LARGURA_DA_TELA_DELA}px: ele voltou a esticar, e a sobra volta a "
        "ser buraco entre os blocos em vez de margem"
    )


def test_o_card_de_um_controle_cresce_com_a_janela_larga() -> None:
    """SOM-01, pedido 3 — *"permitir a expansão da janela"*.

    O outro lado do teste acima, e o que ele sozinho não pega: com o teto
    rígido de 960px o card ficava do mesmo tamanho numa janela de 1180 e numa
    de 1920, e sobravam ~950px de margem morta na tela dela. A janela crescia
    e o conteúdo não.

    Mede o card nas DUAS larguras, e cobra as duas coisas: que ele seja maior
    na tela larga, e que chegue ao teto elástico (crescer 10px também seria
    "maior", e não é o que ela pediu).

    A mordida: devolver `set_size_request(LARGURA_CARD_UNICO, -1)` com
    `halign=CENTER` (o desenho da rodada anterior) faz as duas medidas
    empatarem em 1040 e este teste cai.
    """
    largo = _card_na_tela_dela().get_allocated_width()
    estreito = _card_na_tela_dela(largura=1180).get_allocated_width()

    assert largo > estreito, (
        f"o card mede {largo}px na tela de {LARGURA_DA_TELA_DELA}px e "
        f"{estreito}px numa janela de 1180px: ele voltou a ficar travado num "
        "número só, e a janela larga volta a ser margem morta"
    )
    assert largo == LARGURA_CARD_ELASTICA, (
        f"o card devia usar o teto elástico inteiro ({LARGURA_CARD_ELASTICA}px)"
        f" e usou {largo}px"
    )
    # E o piso continua valendo: numa janela estreita ele não encolhe abaixo
    # do que o conteúdo pede, que é o número repetido no glade.
    assert estreito >= LARGURA_CARD_UNICO


def test_nenhum_vao_de_mais_de_200px_entre_os_blocos_da_faixa() -> None:
    """Critério de aceite 4 da sprint, medido bloco a bloco.

    Percorre a faixa da esquerda para a direita — sensores, analógico
    esquerdo, analógico direito, microfone, botões — e cobra o vão entre cada
    par de vizinhos. Antes da cura, o vão entre o microfone e o grid de botões
    era de 673px.

    **É este teste que impede o teto elástico da SOM-01 de desfazer a cura da
    rodada anterior.** O card agora chega a 1400px na tela dela, e não a 960:
    se o conteúdo não crescesse junto (glifos de 58px, analógicos de 140,
    medidores maiores) e se a sobra não fosse repartida entre os TRÊS blocos da
    faixa, os 440px a mais voltariam a ser buraco. Medido depois da leva:
    143px de vão máximo, contra 112px antes dela e 673px antes da anterior.

    A mordida: sem o teto elástico do `do_size_allocate`, os dois vãos voltam
    aos 673px; devolvendo `expand=False` à coluna de sensores e ao grid de
    botões, eles vão a ~215px. A mensagem de erro diz entre quais blocos.
    """
    card = _card_na_tela_dela()

    blocos = [
        ("sensores", card._coluna_sensores),
        ("analógico esquerdo", card._stick_left),
        ("analógico direito", card._stick_right),
        ("microfone", card._mic_box),
        ("botões", card._glyph_grid),
    ]
    vaos = []
    for (nome_a, wa), (nome_b, wb) in pairwise(blocos):
        vao = _faixa(wb)[0] - _faixa(wa)[1]
        if vao > VAO_MAXIMO_ENTRE_BLOCOS:
            vaos.append(f"{vao}px entre {nome_a} e {nome_b}")

    assert not vaos, (
        "a faixa tem vão maior que o aceite de "
        f"{VAO_MAXIMO_ENTRE_BLOCOS}px: {', '.join(vaos)}"
    )


@pytest.mark.parametrize("compact", [False, True])
def test_a_barra_do_gatilho_nao_toma_a_largura_do_card(compact: bool) -> None:
    """Defeito 4 — 881px de barra para um valor de 0 a 255.

    O "0 / 255" é desenhado no MEIO da barra, então a largura da barra é a
    distância entre o número e as duas pontas: com 881px ele ficava boiando
    no vazio, longe do "L2" que o nomeia.

    Vale nos DOIS cards. Com quatro controles em co-op — o caso normal desta
    casa — os cards vão lado a lado e cada um continuava com uma barra de
    ~800px na tela de 1920: o mesmo defeito, no caminho que ela não estava
    olhando naquele dia.

    A mordida: devolver o `set_hexpand(True)` no lugar do teto faz a barra
    voltar a receber a largura inteira do card e este teste cai.
    """
    card = _card_na_tela_dela(compact=compact)
    teto = card.largura_da_barra_de_gatilho()

    for nome, barra in (("L2", card._l2_bar), ("R2", card._r2_bar)):
        largura = barra.get_allocated_width()
        assert largura <= teto, (
            f"a barra do {nome} mede {largura}px (teto de {teto}px): o valor "
            "volta a flutuar no meio do vazio"
        )
    assert card.largura_da_barra_de_gatilho() <= LARGURA_BARRA_GATILHO_UNICO


@pytest.mark.parametrize("compact", [False, True])
def test_o_numero_do_giroscopio_fica_perto_do_nome_do_eixo(
    compact: bool,
) -> None:
    """Defeito 4 — os números do giroscópio a ~880px dos rótulos X/Y/Z.

    O desenho põe a letra do eixo na borda ESQUERDA do widget e o número
    colado na borda DIREITA (`fim_barra + 4`, em `sensor_widgets`), então a
    largura alocada É a distância entre os dois. Ela leu isso como "rótulos
    apertados à esquerda e números jogados na borda direita".

    A medida é uma FAIXA, com piso e teto, porque a cura erra para os dois
    lados: sem o `set_size_request` o desenho encolhe até quase sumir (a
    moldura abraça o conteúdo, e um `DrawingArea` não tem largura natural);
    sem o `halign` que o prende à esquerda ele volta a receber a coluna
    inteira do grid.

    E a moldura tem de acompanhar o desenho: uma moldura larga com um
    desenho estreito dentro só mudaria o vazio de lugar, para DENTRO do
    bloco — que é a definição do defeito que ela nomeou.
    """
    card = _card_na_tela_dela(compact=compact)
    teto = card.largura_do_giroscopio()

    largura = card._gyro_bars.get_allocated_width()
    piso = teto * 3 // 4

    assert piso <= largura <= teto, (
        f"o giroscópio ocupa {largura}px de largura (faixa esperada: {piso} a "
        f"{teto}px), então o número de cada eixo está a "
        f"{largura}px do nome dele — ou o desenho encolheu a ponto de não se "
        "ler"
    )
    assert card.largura_do_giroscopio() <= LARGURA_GYRO_UNICO
    moldura = card._gyro_box.get_allocated_width()
    assert moldura - largura <= 60, (
        f"a moldura do giroscópio mede {moldura}px para um desenho de "
        f"{largura}px: o vazio mudou para dentro do bloco"
    )


def test_o_frame_estado_tem_a_mesma_largura_do_card() -> None:
    """A aba passa a ter UMA coluna de conteúdo, não duas larguras.

    O frame "Estado" é do glade e recebia a tela inteira: 1870px para cinco
    linhas de rótulo, com a barra de bateria esticando 1730px para dizer
    "80 %" — exatamente o defeito que ela apontou nas barras de L2/R2, no
    bloco logo acima delas. Um card de 960px centrado embaixo de um frame de
    1870px leria como "o card encolheu", e não como "a aba se organizou".

    O número mora no `controller_card.py` e é repetido no glade; este teste é
    o que impede a repetição de virar mentira no dia em que um dos dois mudar.

    SOM-01: o número compartilhado passou a ser o PISO dos dois (1040px, o que
    o conteúdo do card pede depois de os desenhos crescerem).

    SOM-01 (segunda passada): o `halign` do frame tem de ser `fill`. Com
    `center` mais um mínimo declarado, o GTK3 trava o widget no número exato —
    e o frame ficava em 1040px acima de um card que ia a 1400px, visivelmente
    desalinhados na tela maximizada. O TETO dos dois passou a vir do MESMO
    mecanismo: a `CaixaDeTetoElastico`, que o `app.py` põe em volta do frame.
    """
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    arvore = ET.parse(str(MAIN_GLADE))
    for obj in arvore.iter("object"):
        if obj.get("id") != "frame_status_estado":
            continue
        props = {
            p.get("name"): (p.text or "").strip() for p in obj.findall("property")
        }
        assert props.get("halign") == "fill", (
            "com halign=center o frame trava no mínimo declarado e para de "
            "acompanhar o card — ver CaixaDeTetoElastico"
        )
        assert props.get("width-request") == str(LARGURA_CARD_UNICO), (
            "o frame Estado e o card de um controle têm de ter a MESMA "
            f"largura: o glade pede {props.get('width-request')}px e o card, "
            f"{LARGURA_CARD_UNICO}px"
        )
        return
    raise AssertionError("frame_status_estado não existe mais no glade")


# ---------------------------------------------------------------------------
# Entrega 3 — cada assunto num bloco, não seis itens numa lista
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "atributo"),
    [
        ("Touchpad", "_touch_box"),
        ("Lightbar", "_lightbar_box"),
        ("Alto-falante", "_speaker_box"),
        ("Microfone", "_mic_box"),
        ("Giroscópio (graus/s)", "_gyro_box"),
    ],
)
def test_cada_sensor_tem_moldura_propria_no_card_de_um_controle(
    nome: str, atributo: str
) -> None:
    """Defeito 2 — *"o touchpad não tem um espaço próprio"*.

    Touchpad, o retângulo dele, "sem toque", Lightbar, a barra de cor e o
    o hex dela eram SEIS elementos empilhados numa coluna, sem nada separando
    os dois assuntos — lidos de cima para baixo, uma lista só. Agora cada
    assunto é um bloco com moldura e o próprio nome no alto dela.

    A mordida: fazer `_bloco` devolver a caixa nua (o que ele faz no card
    compacto, onde a moldura não cabe na largura) derruba os cinco casos.
    """
    card = _card_na_tela_dela()

    bloco = getattr(card, atributo)

    assert isinstance(bloco, Gtk.Frame), (
        f"o bloco {nome} voltou a ser uma caixa nua empilhada na coluna"
    )
    assert bloco.get_shadow_type() != Gtk.ShadowType.NONE
    rotulo = bloco.get_label_widget()
    assert rotulo is not None and rotulo.get_text() == nome


def test_o_card_compacto_nao_paga_moldura_porque_nao_cabe() -> None:
    """A contrapartida medida da moldura: ela custa largura, e com 2+ cards
    lado a lado não há largura.

    Não é preferência — é o orçamento de
    `test_dois_cards_lado_a_lado_cabem_na_largura_da_janela`, que dá 26px de
    folga para a aba inteira. A moldura custa ~50px por coluna. Este teste
    existe para que a diferença entre os dois cards seja uma decisão escrita,
    e não um esquecimento.
    """
    card = _card_na_tela_dela(compact=True, largura=600)

    assert not isinstance(card._touch_box, Gtk.Frame)
    # E o assunto continua nomeado, agora numa linha dentro da caixa.
    textos = [
        filho.get_text()
        for filho in card._touch_box.get_children()
        if isinstance(filho, Gtk.Label)
    ]
    assert "Touchpad" in textos


# ---------------------------------------------------------------------------
# Entrega 4 — o alto-falante existe na tela
# ---------------------------------------------------------------------------


def test_o_alto_falante_aparece_mesmo_sem_ninguem_ter_ajustado() -> None:
    """*"não tem a parte do som (acho que vem depois)"* — e vem.

    O daemon só publica a chave `speaker` depois de um `speaker.set` nosso: o
    DualSense não devolve o volume, então antes disso qualquer número seria
    chute. O card escondia o bloco inteiro nesse caso — e a sessão dela nunca
    teve um `speaker.set`, então o alto-falante simplesmente não existia na
    tela.

    A mordida: devolver o `self._speaker_box.hide()` ao caminho sem a chave
    faz o bloco sumir e este teste cai.
    """
    entrada = dict(_ENTRY)
    entrada.pop("speaker", None)
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(entrada, _ESTADO, None)
    while Gtk.events_pending():
        Gtk.main_iteration()

    assert card._speaker_box.get_visible() is True
    assert card._speaker_box.get_allocated_width() > 1
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO


# ---------------------------------------------------------------------------
# Entrega 6 — a bateria aparece UMA vez
# ---------------------------------------------------------------------------


def test_a_bateria_do_card_sai_quando_o_frame_estado_ja_a_mostra() -> None:
    """Com UM controle, a bateria aparecia duas vezes na mesma tela.

    As duas regras já eram complementares e ninguém as tinha juntado: a linha
    do frame "Estado" só fica visível com 0 ou 1 controle
    (`_set_battery_row_visible`), e o card só é compacto com 2+. Quem sai no
    caso de um controle é a linha do CARD — a do frame Estado responde também
    quando não há controle nenhum, e aí não existe card.

    A mordida: tirar o `_esconder_modulo(linha_bateria)` do card único faz a
    repetição voltar e este teste cai.
    """
    unico = _card_na_tela_dela()
    dois = _card_na_tela_dela(compact=True, largura=600)

    assert unico._battery_row.get_visible() is False
    assert dois._battery_row.get_visible() is True
    # E o valor continua sendo calculado nos dois — o card compacto é o que
    # responde pela bateria quando há 2+ controles.
    assert dois._battery_bar.get_text() == "80 %"


def test_o_frame_estado_e_o_card_param_no_mesmo_numero_com_a_janela_larga() -> None:
    """SOM-01 (segunda passada): os dois têm de casar na tela maximizada.

    Este é o teste que MEDE — o de cima só lê o glade. Sem a
    `CaixaDeTetoElastico` em volta do frame, o card vai a 1400px e o frame fica
    no piso de 1040px: 360px de degrau, que é o que ela veria.
    """
    from gi.repository import Gtk

    from hefesto_dualsense4unix.app.widgets.controller_card import (
        LARGURA_CARD_ELASTICA,
        CaixaDeTetoElastico,
    )

    frame = Gtk.Frame()
    frame.set_halign(Gtk.Align.FILL)
    frame.set_hexpand(True)
    frame.set_size_request(LARGURA_CARD_UNICO, -1)

    caixa = CaixaDeTetoElastico(frame)
    janela = Gtk.OffscreenWindow()
    caixa_externa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    caixa_externa.pack_start(caixa, False, False, 0)
    janela.add(caixa_externa)
    janela.set_default_size(1870, 400)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    largura = frame.get_allocation().width
    assert largura <= LARGURA_CARD_ELASTICA, (
        f"o frame Estado esticou pela tela: {largura}px"
    )
    assert largura > LARGURA_CARD_UNICO, (
        "o frame Estado ficou travado no piso e não acompanha o card: "
        f"{largura}px, piso {LARGURA_CARD_UNICO}px"
    )
