"""A faixa da aba Status medida como ELA vê: blocos, tetos e vazios."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status faixa blocos")

from itertools import pairwise
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets import controller_card as cc_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (

    LARGURA_BARRA_GATILHO_UNICO,
    LARGURA_CARD_ELASTICA,
    LARGURA_CARD_UNICO,
    LARGURA_GYRO_UNICO,
    TEXTO_SPEAKER_SEM_DADO,
    ControllerCard,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    COR_TOQUE,
    TouchpadView,
    hex_para_rgb,
)

LARGURA_DA_TELA_DELA = 1870

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
    # ONDA-CONTROLES-04: os números são MEDIDOS, não inventados — um DualSense
    "accel": {"x": -0.005, "y": 0.981, "z": 0.172},
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

_janelas_vivas: list[Any] = []


FOLGA_DE_RENDERIZACAO: int = 10


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


def test_a_faixa_nao_muda_de_lugar_quando_o_mic_muda_de_estado() -> None:
    """MIC-PRESENTE-01/E3 — **a diferença tem de ser zero pixel.**"""

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


def test_o_card_de_um_controle_nao_estica_pela_tela_inteira() -> None:
    """Defeito 4 — o card recebia 1870px para ~700px de conteúdo."""
    card = _card_na_tela_dela()

    largura = card.get_allocated_width()

    assert largura <= LARGURA_CARD_ELASTICA, (
        f"o card de um controle ocupa {largura}px numa tela de "
        f"{LARGURA_DA_TELA_DELA}px: ele voltou a esticar, e a sobra volta a "
        "ser buraco entre os blocos em vez de margem"
    )


def test_o_card_de_um_controle_cresce_com_a_janela_larga() -> None:
    """SOM-01, pedido 3 — *"permitir a expansão da janela"*."""
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
    assert estreito >= LARGURA_CARD_UNICO


def test_nenhum_vao_de_mais_de_200px_entre_os_blocos_da_faixa() -> None:
    """Critério de aceite 4 da sprint, medido bloco a bloco."""
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
    """Defeito 4 — 881px de barra para um valor de 0 a 255."""
    card = _card_na_tela_dela(compact=compact)
    metade = card._metade_esquerda.get_allocated_width()
    fim_da_metade = _faixa(card._metade_esquerda)[1]

    for nome, barra in (("L2", card._l2_bar), ("R2", card._r2_bar)):
        largura = barra.get_allocated_width()
        assert largura <= metade, (
            f"a barra do {nome} mede {largura}px e a metade esquerda da faixa "
            f"tem {metade}px: a barra saiu da coluna que a limita"
        )
        fim_da_barra = _faixa(barra)[1]
        assert abs(fim_da_barra - fim_da_metade) <= 12, (
            f"a barra do {nome} termina em {fim_da_barra} e a metade esquerda "
            f"em {fim_da_metade}: era esse alinhamento o pedido dela"
        )
    assert card.largura_da_barra_de_gatilho() <= LARGURA_BARRA_GATILHO_UNICO, (
        "o PISO da barra (o `set_size_request`) não pode subir: ele entra "
        "inteiro no mínimo do card, que já está no teto de 1040"
    )


@pytest.mark.parametrize("compact", [False, True])
def test_o_numero_do_giroscopio_fica_perto_do_nome_do_eixo(
    compact: bool,
) -> None:
    """Defeito 4 — os números do giroscópio a ~880px dos rótulos X/Y/Z."""
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import _ROTULO_GYRO_PX

    card = _card_na_tela_dela(compact=compact)

    largura = card._gyro_bars.get_allocated_width()
    distancia = _ROTULO_GYRO_PX

    assert distancia <= 40, (
        f"o número de cada eixo está a {distancia}px do nome dele. O desenho "
        "voltou a ancorar o valor na borda direita — com o giroscópio "
        f"esticado ({largura}px) isso é o defeito 4 de volta, pior"
    )
    assert card.largura_do_giroscopio() <= LARGURA_GYRO_UNICO, (
        "o PISO do desenho (o `set_size_request`) não pode subir: ele entra "
        "inteiro no mínimo do card, que já está no teto de 1040"
    )
    moldura = card._gyro_box.get_allocated_width()
    assert moldura - largura <= 60, (
        f"a moldura do giroscópio mede {moldura}px para um desenho de "
        f"{largura}px: o vazio mudou para dentro do bloco"
    )


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
    """Defeito 2 — *"o touchpad não tem um espaço próprio"*."""
    card = _card_na_tela_dela()

    bloco = getattr(card, atributo)

    assert isinstance(bloco, Gtk.Frame), (
        f"o bloco {nome} voltou a ser uma caixa nua empilhada na coluna"
    )
    assert bloco.get_shadow_type() != Gtk.ShadowType.NONE
    rotulo = bloco.get_label_widget()
    assert rotulo is not None and rotulo.get_text().startswith(nome), (
        f"o rótulo da moldura é {rotulo.get_text()!r} e tem de começar por "
        f"{nome!r}: o nome do bloco vem antes de qualquer valor"
    )


def test_o_card_compacto_nao_paga_moldura_porque_nao_cabe() -> None:
    """A contrapartida medida da moldura: ela custa largura, e com 2+ cards"""
    card = _card_na_tela_dela(compact=True, largura=600)

    assert not isinstance(card._touch_box, Gtk.Frame)
    textos = [
        filho.get_text()
        for filho in card._touch_box.get_children()
        if isinstance(filho, Gtk.Label)
    ]
    assert "Touchpad" in textos


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


def test_a_bateria_aparece_uma_vez_so_na_tela_em_qualquer_modo() -> None:
    """Com UM controle, a bateria aparecia duas vezes na mesma tela."""
    unico = _card_na_tela_dela()
    dois = _card_na_tela_dela(compact=True, largura=600)

    assert unico._battery_row.get_visible() is True
    assert dois._battery_row.get_visible() is True
    assert dois._battery_bar.get_text() == "80 %"
    assert unico._battery_bar.get_text() == "80 %"
    assert unico._battery_bar.get_show_text() is False
    assert unico._battery_pct_label is not None
    assert unico._battery_pct_label.get_text() == "80 %"


def test_o_frame_estado_e_o_card_param_no_mesmo_numero_com_a_janela_larga() -> None:
    """SOM-01 (segunda passada): os dois têm de casar na tela maximizada."""
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


PISO_DO_DESENHO_NA_TELA_LARGA = 300


def test_os_quatro_desenhos_ocupam_a_faixa_na_tela_larga() -> None:
    """CARD-OCUPA-01, E1 e E2 — *"tem muito espaço vazio aqui, dava pra"""
    card = _card_na_tela_dela()

    touch = card._touch_view.get_allocated_width()
    mic = card._mic_meter.get_allocated_width()
    lightbar = card._lightbar_bar.get_allocated_width()
    speaker = card._speaker_bar.get_allocated_width()

    assert touch >= PISO_DO_DESENHO_NA_TELA_LARGA, (
        f"o touchpad mede {touch}px num card de "
        f"{card.get_allocated_width()}px: ele voltou a ser um selo, e a "
        "largura que a janela devolve volta a ser vão lateral"
    )
    assert mic >= PISO_DO_DESENHO_NA_TELA_LARGA, (
        f"o medidor do microfone mede {mic}px num card de "
        f"{card.get_allocated_width()}px"
    )
    assert lightbar == touch, (
        f"a lightbar mede {lightbar}px debaixo de um touchpad de {touch}px: "
        "a coluna deixou de se ler alinhada"
    )
    assert speaker == mic, (
        f"o alto-falante mede {speaker}px debaixo de um medidor de {mic}px: "
        "a coluna do som deixou de se ler alinhada"
    )


def test_o_piso_de_largura_do_card_nao_subiu_com_os_desenhos_maiores() -> None:
    """A outra metade da cura, e a que impede a cura ERRADA."""
    card = _card_na_tela_dela()

    minimo, natural = card.get_preferred_width()

    teto = LARGURA_CARD_UNICO + FOLGA_DE_RENDERIZACAO
    assert minimo <= teto, (
        f"o card de um controle passou a pedir {minimo}px de MÍNIMO (o piso "
        f"é {LARGURA_CARD_UNICO}px, e o teto com a folga de renderização é "
        f"{teto}px): o crescimento foi parar no `set_size_request`, e o "
        "mínimo da janela sobe junto"
    )
    assert natural > minimo, (
        f"o card pede {natural}px de natural para {minimo}px de mínimo: os "
        "desenhos voltaram a ter natural igual ao piso e param de crescer "
        "com a janela"
    )
    assert natural <= LARGURA_CARD_ELASTICA, (
        f"o natural do card ({natural}px) passou do teto elástico "
        f"({LARGURA_CARD_ELASTICA}px)"
    )


def test_com_a_janela_no_tamanho_de_projeto_os_desenhos_encolhem_sem_atropelo() -> None:
    """O outro lado do elástico: apertado, ele volta para o piso."""
    for largura in (1180, 1062):
        card = _card_na_tela_dela(largura=largura)
        blocos = [
            ("sensores", card._coluna_sensores),
            ("analógico esquerdo", card._stick_left),
            ("analógico direito", card._stick_right),
            ("microfone", card._mic_box),
            ("botões", card._glyph_grid),
        ]
        for (nome_a, wa), (nome_b, wb) in pairwise(blocos):
            vao = _faixa(wb)[0] - _faixa(wa)[1]
            assert vao >= 0, (
                f"com a janela em {largura}px, {nome_a} e {nome_b} se "
                f"atropelam em {-vao}px: o natural do desenho passou por "
                "cima do vizinho"
            )
        touch = card._touch_view.get_allocated_width()
        piso, _ = cc_mod._TOUCHPAD_PX_UNICO
        assert piso <= touch <= cc_mod._DESENHO_NATURAL_PX_UNICO, (
            f"com a janela em {largura}px o touchpad mede {touch}px, fora da "
            f"faixa entre o piso ({piso}px) e o teto "
            f"({cc_mod._DESENHO_NATURAL_PX_UNICO}px)"
        )

    apertado = _card_na_tela_dela(largura=1062)._touch_view.get_allocated_width()
    folgado = _card_na_tela_dela()._touch_view.get_allocated_width()
    assert folgado > apertado, (
        f"o touchpad mede {folgado}px na tela de {LARGURA_DA_TELA_DELA}px e "
        f"{apertado}px na janela mínima: ele voltou a ter um tamanho só, e a "
        "largura que a janela larga devolve volta a ser vão"
    )


def test_alargar_o_touchpad_nao_muda_o_lugar_do_dedo() -> None:
    """O aceite 3 da sprint, medido nos PIXELS que o Cairo pintou."""

    def fracao_do_ponto(largura: int) -> float:
        painel = TouchpadView()
        painel.set_size_request(largura, 80)
        janela = Gtk.OffscreenWindow()
        janela.add(painel)
        janela.show_all()
        _janelas_vivas.append(janela)
        painel.set_toque((0.75, 0.25))
        janela.resize(largura, 80)
        while Gtk.events_pending():
            Gtk.main_iteration()

        pixbuf = janela.get_pixbuf()
        assert pixbuf is not None, "a OffscreenWindow não devolveu pixbuf"
        dados = pixbuf.get_pixels()
        passo = pixbuf.get_rowstride()
        canais = pixbuf.get_n_channels()
        alvo = tuple(round(canal * 255) for canal in hex_para_rgb(COR_TOQUE))
        colunas = [
            x
            for y in range(painel.get_allocated_height())
            for x in range(painel.get_allocated_width())
            if all(
                abs(dados[y * passo + x * canais + canal] - alvo[canal]) < 12
                for canal in (0, 1, 2)
            )
        ]
        assert colunas, (
            f"o ponto do toque não foi pintado no desenho de {largura}px"
        )
        centro = (min(colunas) + max(colunas)) / 2
        return (centro - 2) / (painel.get_allocated_width() - 4)

    estreito = fracao_do_ponto(cc_mod._TOUCHPAD_PX_UNICO[0])
    largo = fracao_do_ponto(cc_mod._DESENHO_NATURAL_PX_UNICO)

    assert abs(estreito - largo) < 0.02, (
        f"o dedo a 75% do touchpad aparece a {estreito:.1%} do desenho "
        f"estreito e a {largo:.1%} do largo: alargar passou a mentir a "
        "posição do toque"
    )
    assert abs(largo - 0.75) < 0.02, (
        f"o dedo a 75% do touchpad aparece a {largo:.1%} do desenho largo"
    )
