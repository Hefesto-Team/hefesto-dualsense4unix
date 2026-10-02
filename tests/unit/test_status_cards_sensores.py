"""Os três módulos de sensor DENTRO do card da aba Status (S2), com GTK real.

O contrato que estes testes travam é sempre o mesmo, em três lugares
diferentes: **ausência de sensor não vira zero na tela**. Três barras de
giroscópio paradas no centro, um medidor de mic vazio ou um touchpad sem
ponto diriam "o controle está em repouso" — quando a verdade é "não tenho
esse sensor". Cada módulo some inteiro em vez disso.

Também travam a coexistência com a linha `texto_motion`, que já existia: ela
diz se o giroscópio FLUI PARA O JOGO; as barras novas mostram o VALOR. São
duas perguntas diferentes e as duas continuam respondidas.

A última seção é de STATUS-SIMETRIA-01 e mede o LAYOUT MONTADO numa
`Gtk.OffscreenWindow` — alinhamento dos analógicos, ordem horizontal da faixa e
crescimento do glifo com a escala de fonte. Ela existe porque o precedente do
rumble (teste que passou com a cura arrancada, porque chamava a peça e não a
fiação) não pode se repetir: os três asserts caem quando a cura é removida.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status cards sensores")

from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app import theme as theme_mod
from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets import controller_card as cc_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ROTULO_STICK_DIR,
    ROTULO_STICK_ESQ,
    TEXTO_MIC_AUSENTE,
    TEXTO_MIC_SEM_MUTE,
    TEXTO_SPEAKER_SEM_DADO,
    ControllerCard,
    glyph_size,
    gyro_do_inputs,
    speaker_do_entry,
    touchpad_do_inputs,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (

    COR_MIC_FALA,
    COR_MIC_PICO,
    COR_MIC_SILENCIO,
    ESCALA_GYRO_GRAUS_S,
    MIC_AMOSTRAS,
    cor_da_barra_do_mic,
    fracao_do_eixo,
    fracao_do_volume,
    historico_deslizante,
    posicao_normalizada,
    texto_eixo,
    texto_toques,
    texto_volume,
)


def _inputs(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
        "l2_raw": 0,
        "r2_raw": 0,
        "buttons": [],
    }
    base.update(extra)
    return base


def _entry(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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
        "inputs": _inputs(),
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }
    base.update(kw)
    return base


_ESTADO: dict[str, Any] = {"native_mode": False}

_GYRO = {"x": 143.2, "y": -412.0, "z": 22.8}
_TOUCH = {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080}


@pytest.fixture()
def card() -> Any:
    widget = ControllerCard(compact=True)
    widget.show_all()
    return widget


def test_gyro_do_inputs_le_os_tres_eixos() -> None:
    assert gyro_do_inputs(_inputs(gyro=_GYRO)) == (143.2, -412.0, 22.8)


@pytest.mark.parametrize(
    "inputs",
    [None, {}, _inputs(), _inputs(gyro={"x": 1.0}), _inputs(gyro="lixo")],
)
def test_gyro_ausente_ou_malformado_vira_none(inputs: Any) -> None:
    """None é o que faz o módulo SUMIR; (0,0,0) fingiria repouso."""
    assert gyro_do_inputs(inputs) is None


def test_touchpad_do_inputs_normaliza_pelos_limites_do_payload() -> None:
    lido = touchpad_do_inputs(_inputs(touchpad=_TOUCH))

    assert lido is not None
    tocando, fx, fy = lido
    assert tocando is True
    assert fx == pytest.approx(0.75)
    assert fy == pytest.approx(0.25)


def test_touchpad_com_limites_proprios_nao_usa_1920x1080() -> None:
    """Quem declara os limites é o kernel, no próprio payload."""
    bloco = {"touching": True, "x": 500, "y": 250, "width": 1000, "height": 500}

    lido = touchpad_do_inputs(_inputs(touchpad=bloco))

    assert lido is not None
    _tocando, fx, fy = lido
    assert (fx, fy) == pytest.approx((0.5, 0.5))


@pytest.mark.parametrize("inputs", [None, _inputs(), _inputs(touchpad={"x": 1})])
def test_touchpad_ausente_ou_malformado_vira_none(inputs: Any) -> None:
    assert touchpad_do_inputs(inputs) is None


def test_fracao_do_eixo_preserva_o_sinal_e_satura() -> None:
    """O sinal decide o LADO da barra; o módulo satura em vez de vazar."""
    assert fracao_do_eixo(ESCALA_GYRO_GRAUS_S / 2) == pytest.approx(0.5)
    assert fracao_do_eixo(-ESCALA_GYRO_GRAUS_S / 2) == pytest.approx(-0.5)
    assert fracao_do_eixo(ESCALA_GYRO_GRAUS_S * 10) == 1.0
    assert fracao_do_eixo(-ESCALA_GYRO_GRAUS_S * 10) == -1.0


def test_texto_do_eixo_tem_largura_fixa() -> None:
    """Campo fixo: a 10 Hz, texto que muda de largura faz o painel respirar"""
    larguras = {len(texto_eixo(v)) for v in (0.0, -9.9, 143.2, -412.0, 1999.9)}

    assert larguras == {7}


def test_posicao_normalizada_grampeia_fora_de_faixa() -> None:
    assert posicao_normalizada(9999, -50, 1920, 1080) == (1.0, 0.0)
    assert posicao_normalizada(10, 10, 0, 0) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("n", "esperado"), [(0, "Sem toque"), (1, "1 toque"), (2, "2 toques")]
)
def test_texto_toques(n: int, esperado: str) -> None:
    assert texto_toques(n) == esperado


def test_sem_sensor_nenhum_o_gyro_e_o_touchpad_somem(card: Any) -> None:
    """Giroscópio e touchpad continuam sumindo — o microfone, não.

    A regra "ausência de sensor não vira zero na tela" vale para os dois
    primeiros porque a ausência deles é do CONTROLE: um DualSense sem node de
    motion não tem giroscópio nenhum, e três barras paradas no centro diriam
    "em repouso". O microfone é outro caso e a MIC-PRESENTE-01 o separou:
    todo DualSense tem microfone, o que falta é SINAL — e some é
    indistinguível de "não existe" (ver
    `test_a_faixa_nao_muda_de_lugar_quando_o_mic_muda_de_estado`, em
    `test_status_faixa_blocos.py`).
    """
    card.update(_entry(), _ESTADO, None)

    assert card._gyro_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._mic_box.get_visible() is True


def test_gyro_no_payload_acende_as_barras(card: Any) -> None:
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)

    assert card._gyro_box.get_visible() is True
    assert card._gyro_bars._valores == (143.2, -412.0, 22.8)


def test_gyro_some_quando_o_daemon_para_de_mandar(card: Any) -> None:
    """Daemon reiniciado sem o node de motion não pode deixar o último valor"""
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)

    card.update(_entry(), _ESTADO, None)

    assert card._gyro_box.get_visible() is False
    assert card._gyro_bars._valores == (0.0, 0.0, 0.0)


def test_touchpad_com_dedo_desenha_o_ponto(card: Any) -> None:
    card.update(_entry(inputs=_inputs(touchpad=_TOUCH)), _ESTADO, None)

    assert card._touch_box.get_visible() is True
    assert card._touch_view._toque == pytest.approx((0.75, 0.25))
    assert card._touch_label.get_text() == "1 toque"


def test_touchpad_sem_dedo_apaga_o_ponto_mas_mantem_o_painel(card: Any) -> None:
    """O sensor existe (o retângulo fica); o que some é o ponto."""
    solto = dict(_TOUCH, touching=False)

    card.update(_entry(inputs=_inputs(touchpad=solto)), _ESTADO, None)

    assert card._touch_box.get_visible() is True
    assert card._touch_view._toque is None
    assert card._touch_label.get_text() == "Sem toque"


def test_mic_sem_leitura_fica_no_lugar_dizendo_sem_sinal(card: Any) -> None:
    """MIC-PRESENTE-01 — *"o espaço do icon sempre fica lá"*."""
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)

    assert card._mic_box.get_visible() is True
    assert card._mic_selo.get_visible() is True
    assert card._mic_selo.get_text() == TEXTO_MIC_AUSENTE


def test_o_espaco_do_mic_e_reservado_por_construcao() -> None:
    """A largura reservada não pode depender do texto que está no rótulo."""
    card = _card_montado()

    grupo = card._grupo_largura_mic
    assert grupo.get_mode() == Gtk.SizeGroupMode.HORIZONTAL
    assert set(grupo.get_widgets()) == {card._mic_meter, card._mic_selo}
    assert card._mic_selo.get_width_chars() == len(TEXTO_MIC_AUSENTE)
    assert card._mic_selo.get_max_width_chars() == len(TEXTO_MIC_AUSENTE)


def test_nenhum_caminho_esconde_o_bloco_do_microfone() -> None:
    """MIC-PRESENTE-01/E3, segunda metade: nenhum `hide()` no bloco do mic."""
    fonte = Path(cc_mod.__file__).read_text(encoding="utf-8")

    assert "_mic_box.hide()" not in fonte
    assert "_esconder_modulo(mic)" not in fonte


def test_mic_com_leitura_mostra_medidor_e_selo(card: Any) -> None:
    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.62, muted=False))

    assert card._mic_box.get_visible() is True
    assert card._mic_meter._nivel == pytest.approx(0.62)
    assert card._mic_selo.get_visible() is True
    assert "ATIVO" in card._mic_selo.get_label()
    assert "#50fa7b" in card._mic_selo.get_label()


def test_mic_mudo_troca_o_selo(card: Any) -> None:
    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.1, muted=True))

    assert "MUDO" in card._mic_selo.get_label()
    assert "#2b2d3a" in card._mic_selo.get_label()


def test_mic_sem_mute_lido_diz_captando_e_nao_ativo(card: Any) -> None:
    """Medidor sim (o áudio está chegando), selo colorido não: afirmar "ATIVO"
    sem ter lido o mute seria dizer que o microfone está aberto por chute.

    O rótulo continua no lugar — MIC-PRESENTE-01/E2, "nunca um medidor mudo
    sem explicação" —, só que dizendo o que se sabe: está captando.
    """
    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.4, muted=None))

    assert card._mic_box.get_visible() is True
    assert card._mic_selo.get_text() == TEXTO_MIC_SEM_MUTE
    assert "ATIVO" not in card._mic_selo.get_label()


def test_o_touchpad_some_sozinho_sem_arrastar_o_microfone(card: Any) -> None:
    """STATUS-SIMETRIA-01 — microfone e touchpad deixaram de dividir uma linha."""
    card.update(_entry(inputs=_inputs(touchpad=_TOUCH)), _ESTADO, None)
    assert card._touch_box.get_visible() is True
    assert card._mic_selo.get_text() == TEXTO_MIC_AUSENTE

    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.2, muted=False))
    assert card._touch_box.get_visible() is False
    assert card._mic_box.get_visible() is True

    card.update(_entry(), _ESTADO, None)
    assert card._touch_box.get_visible() is False
    assert card._mic_box.get_visible() is True
    assert card._linha_inferior.get_visible() is True


def test_sem_leitor_de_inputs_apaga_tambem_os_sensores(card: Any) -> None:
    """IPC mudo: o card inteiro vira "—". Sensor congelado seria movimento"""
    card.update(
        _entry(inputs=_inputs(gyro=_GYRO, touchpad=_TOUCH)),
        _ESTADO,
        LeituraMic(nivel=0.5, muted=False),
    )

    card.reset_inputs()

    assert card._gyro_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._gyro_bars._valores == (0.0, 0.0, 0.0)
    assert card._touch_view._toque is None
    assert card._mic_box.get_visible() is True
    assert card._mic_selo.get_text() == TEXTO_MIC_AUSENTE
    assert not any(card._mic_meter._historico)
    assert card._speaker_box.get_visible() is True
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO


def test_cor_da_barra_do_mic_tem_tres_faixas() -> None:
    """A cor sai da amplitude DAQUELA barra. Na escada fixa antiga, todas as"""
    assert cor_da_barra_do_mic(0.9) == COR_MIC_PICO
    assert cor_da_barra_do_mic(0.61) == COR_MIC_PICO
    assert cor_da_barra_do_mic(0.6) == COR_MIC_FALA
    assert cor_da_barra_do_mic(0.31) == COR_MIC_FALA
    assert cor_da_barra_do_mic(0.3) == COR_MIC_SILENCIO
    assert cor_da_barra_do_mic(0.0) == COR_MIC_SILENCIO


def test_historico_deslizante_mantem_o_tamanho_e_a_ordem() -> None:
    """Amostra nova entra na direita; a mais velha cai fora pela esquerda."""
    janela = tuple([0.0] * MIC_AMOSTRAS)
    for valor in (0.2, 0.9):
        janela = historico_deslizante(janela, valor)

    assert len(janela) == MIC_AMOSTRAS
    assert janela[-2:] == (0.2, 0.9)
    assert janela[0] == 0.0


def test_historico_deslizante_grampeia_a_amostra() -> None:
    janela = historico_deslizante((), 5.0)

    assert janela[-1] == 1.0
    assert historico_deslizante((), -3.0)[-1] == 0.0


def test_medidor_do_mic_muda_de_forma_a_cada_leitura(card: Any) -> None:
    """A forma é o dado: níveis diferentes têm de deixar barras diferentes."""
    for nivel in (0.1, 0.8, 0.35):
        card.update(_entry(), _ESTADO, LeituraMic(nivel=nivel, muted=False))

    assert card._mic_meter._historico[-3:] == pytest.approx((0.1, 0.8, 0.35))
    assert len(set(card._mic_meter._historico)) > 1


def test_mic_que_some_leva_a_onda_junto(card: Any) -> None:
    """Reaparecer com o traço da última captura seria mostrar áudio que não"""
    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.7, muted=False))

    card.update(_entry(), _ESTADO, None)

    assert not any(card._mic_meter._historico)


def test_lightbar_com_cor_conhecida_vira_barra_e_hex(card: Any) -> None:
    card.update(_entry(lightbar_rgb=[255, 121, 198]), _ESTADO, None)

    assert card._lightbar_box.get_visible() is True
    assert card._lightbar_bar._rgb == (255, 121, 198)
    assert card._lightbar_hex.get_text() == "#ff79c6"


def test_lightbar_sem_cor_conhecida_esconde_a_barra(card: Any) -> None:
    """"Não sei" e "apagada" não podem desenhar a mesma faixa preta."""
    card.update(_entry(lightbar_rgb=None), _ESTADO, None)

    assert card._lightbar_box.get_visible() is False


@pytest.mark.parametrize(
    "entrada",
    [
        {"speaker": {"volume": 180, "muted": False}},
        {"inputs": _inputs(speaker={"volume": 180, "muted": False})},
    ],
)
def test_speaker_lido_do_entry_ou_do_inputs(entrada: dict[str, Any]) -> None:
    """Quem publica é o daemon; o widget não pode quebrar por causa de ONDE"""
    assert speaker_do_entry(entrada) == (180, False)


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        {},
        {"speaker": "lixo"},
        {"speaker": {}},
        {"speaker": {"volume": "alto"}},
        {"speaker": {"volume": True}},
    ],
)
def test_speaker_ausente_ou_malformado_vira_none(entrada: Any) -> None:
    assert speaker_do_entry(entrada) is None


def test_speaker_sem_mute_no_payload_nao_chuta() -> None:
    assert speaker_do_entry({"speaker": {"volume": 255}}) == (255, None)


def test_bloco_do_speaker_fica_dizendo_que_ninguem_ajustou(card: Any) -> None:
    """STATUS-SIMETRIA-02, entrega 4 — *"não tem a parte do som"*.

    O bloco sumia por construção: o daemon só publica a chave ``speaker``
    depois de um ``speaker.set`` nosso (o DualSense não devolve o volume), e
    na sessão dela nunca houve um. Só que "não sei o volume" e "este controle
    não tem alto-falante" não podem desenhar a mesma coisa — e desenhar nada
    é dizer a segunda.

    O que continua proibido é o número inventado: a barra fica em repouso e o
    rótulo diz que ninguém ajustou, nunca um "0 %" fingindo volume no mínimo.
    """
    card.update(_entry(), _ESTADO, None)

    assert card._speaker_box.get_visible() is True
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO
    assert card._speaker_bar._fracao == 0.0
    assert "%" not in card._speaker_label.get_text()


def test_bloco_do_speaker_acende_com_a_chave(card: Any) -> None:
    """O bloco reage à chave — e reage com a grandeza que o OUVIDO mede.

    Este teste travava ``_fracao == 128 / 255`` e o rótulo em "50 %". A
    SOM-03 mediu o registrador no hardware (tom de 1 kHz, o microfone do
    próprio DualSense como instrumento) e **refutou a régua**: 102, 128 e 255
    devolvem a mesma magnitude (8759, 8488, 8793). Um registrador em 128 é o
    volume MÁXIMO, e "50 %" era a interface dizendo que havia o dobro de
    volume disponível quando não havia mais nada.

    O teste não foi apagado nem afrouxado: ele continua cobrando exatamente o
    que protegia — que a chave ACENDE o bloco e que barra e rótulo saem da
    mesma conta, e não de duas — só que agora contra a régua medida. Por isso
    o valor esperado é DERIVADO de `fracao_do_volume` em vez de escrito à mão:
    um número cravado aqui voltaria a travar a régua, que foi o defeito.

    A mordida: devolver ``fracao_do_volume`` a ``bruto / 255`` derruba as duas
    asserções de uma vez — a fração cai para 0,50 e o rótulo para "50 %".
    """
    card.update(
        _entry(speaker={"volume": 128, "muted": False}), _ESTADO, None
    )

    assert card._speaker_box.get_visible() is True
    assert card._speaker_bar._fracao == pytest.approx(fracao_do_volume(128))
    assert card._speaker_label.get_text() == "100 %"
    assert fracao_do_volume(128) == fracao_do_volume(255) == 1.0


def test_speaker_mudo_diz_mudo_em_vez_de_porcentagem(card: Any) -> None:
    card.update(_entry(speaker={"volume": 200, "muted": True}), _ESTADO, None)

    assert card._speaker_bar._muted is True
    assert card._speaker_label.get_text() == "Mudo"


def test_texto_volume_sem_mute_lido_mostra_so_a_porcentagem() -> None:
    assert texto_volume(255, None) == "100 %"
    assert texto_volume(0, None) == "0 %"


def test_botoes_ficam_na_linha_de_baixo_mesmo_sem_mic_nem_touchpad(
    card: Any,
) -> None:
    """A armadilha do reagrupamento: se os botões morassem DENTRO da caixa que"""
    card.update(_entry(), _ESTADO, None)

    assert card._touch_box.get_visible() is False
    assert card._linha_inferior.get_visible() is True
    assert card._glyph_grid.get_visible() is True


def test_gyro_oculto_nao_devolve_a_largura_toda_aos_gatilhos(card: Any) -> None:
    """O giroscópio nasce oculto e aparece quando há sensor. Num `Gtk.Box` os"""
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)
    while Gtk.events_pending():
        Gtk.main_iteration()
    assert card._gyro_box.get_visible() is True, (
        "premissa deste teste: com giroscópio no payload o módulo aparece"
    )
    com_gyro = card._l2_bar.get_parent().get_allocated_width()

    card.update(_entry(), _ESTADO, None)
    while Gtk.events_pending():
        Gtk.main_iteration()
    sem_gyro = card._l2_bar.get_parent().get_allocated_width()

    assert card._gyro_box.get_visible() is False
    assert card._gyro_slot.get_visible() is True
    assert com_gyro == sem_gyro, (
        f"os gatilhos mediam {com_gyro}px com o giroscópio à vista e "
        f"{sem_gyro}px sem ele: a coluna deixou de ser guardada e a tela dá "
        "um pulo a cada troca de controle"
    )

    grid = card._gyro_slot.get_parent()
    assert grid.child_get_property(card._gyro_slot, "left-attach") == 1
    assert grid.child_get_property(card._l2_bar.get_parent(), "left-attach") == 0


def test_barras_de_gyro_convivem_com_a_linha_texto_motion(card: Any) -> None:
    """São informações DIFERENTES: a linha diz se o gyro flui para o jogo,"""
    estado = {
        "native_mode": False,
        "rumble_ff": {
            "per_vpad": [{"player": 1, "motion_streaming": True, "motion_hz": 250.0}]
        },
    }

    card.update(_entry(inputs=_inputs(gyro=_GYRO)), estado, None)

    assert card._motion_label.get_visible() is True
    assert "fluindo para o jogo" in card._motion_label.get_text()
    assert card._gyro_box.get_visible() is True


_LARGURA_DO_CARD = 620

_janelas_vivas: list[Any] = []


def _card_montado(*, compact: bool = True) -> Any:
    """Card real, dentro de uma `Gtk.OffscreenWindow`, com TODOS os sensores."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(_LARGURA_DO_CARD, -1)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(
        _entry(
            inputs=_inputs(gyro=_GYRO, touchpad=_TOUCH),
            speaker={"volume": 180, "muted": False},
        ),
        _ESTADO,
        LeituraMic(nivel=0.6, muted=False),
    )
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


def test_os_dois_analogicos_desenham_na_mesma_altura() -> None:
    """1 px de degrau entre os desenhos já reprova (medido: eram 20 px)."""
    card = _card_montado()

    esquerdo = card._stick_left.get_allocation()
    direito = card._stick_right.get_allocation()

    assert esquerdo.y == direito.y, (
        f"os desenhos dos analógicos estão {abs(esquerdo.y - direito.y)}px "
        "desalinhados: o SizeGroup vertical dos títulos saiu ou parou de "
        "amarrar os dois rótulos"
    )
    assert (
        card._stick_left_xy.get_allocation().y
        == card._stick_right_xy.get_allocation().y
    )
    grupo = card._grupo_titulos_stick
    assert grupo.get_mode() == Gtk.SizeGroupMode.VERTICAL
    assert set(grupo.get_widgets()) == {
        card._stick_left_title,
        card._stick_right_title,
    }


@pytest.mark.parametrize("compact", [True, False])
def test_as_duas_legendas_de_analogico_tem_o_mesmo_numero_de_linhas(
    compact: bool,
) -> None:
    """STATUS-SIMETRIA-02, defeito 1 — *"um nome dos analógicos tem 3 linhas"""
    card = _card_montado(compact=compact)

    linhas_esq = card._stick_left_title.get_layout().get_line_count()
    linhas_dir = card._stick_right_title.get_layout().get_line_count()

    assert linhas_esq == linhas_dir, (
        f"a legenda do analógico esquerdo ocupa {linhas_esq} linhas e a do "
        f"direito, {linhas_dir}: a quebra voltou a depender da largura"
    )
    assert (
        card._stick_left_title.get_allocated_height()
        == card._stick_right_title.get_allocated_height()
    )
    assert card._stick_left._label == ROTULO_STICK_ESQ
    assert card._stick_right._label == ROTULO_STICK_DIR
    assert ROTULO_STICK_ESQ not in card._stick_left_xy.get_text()
    assert ROTULO_STICK_DIR not in card._stick_right_xy.get_text()


def test_ordem_da_faixa_poe_o_microfone_a_direita_dos_analogicos() -> None:
    """A ordem pedida, lida da ESQUERDA para a DIREITA no card montado::"""
    card = _card_montado()

    def faixa(widget: Any) -> tuple[int, int]:
        alloc = widget.get_allocation()
        return (alloc.x, alloc.x + alloc.width)

    _sensores_ini, sensores_fim = faixa(card._coluna_sensores)
    esq_ini, esq_fim = faixa(card._stick_left)
    dir_ini, dir_fim = faixa(card._stick_right)
    mic_ini, mic_fim = faixa(card._mic_box)
    grid_ini, _grid_fim = faixa(card._glyph_grid)

    assert card._mic_box.get_visible() is True
    assert sensores_fim <= esq_ini, "os sensores têm de abrir a faixa"
    assert esq_fim <= dir_ini, "o analógico esquerdo vem antes do direito"
    assert dir_fim <= mic_ini, (
        f"o microfone começa em x={mic_ini} e o analógico direito só termina "
        f"em x={dir_fim}: ele voltou para a ESQUERDA dos analógicos"
    )
    assert mic_fim <= grid_ini, "os botões fecham a faixa, depois do microfone"
    assert card._mic_box.get_parent() is card._coluna_audio
    assert card._coluna_audio.get_parent() is card._miolo_inferior
    assert card._miolo_inferior.get_parent() is card._linha_inferior


def test_o_glifo_cresce_quando_a_escala_de_fonte_cresce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A/B com escala 0 e escala 3, medindo o glifo ALOCADO no card montado."""
    medidas: dict[int, tuple[int, int]] = {}
    for escala in (0, 3):
        monkeypatch.setattr(theme_mod, "_escala_aplicada", escala)
        card = _card_montado()
        medidas[escala] = (
            card._glyphs["triangle"].get_allocated_width(),
            card._glyph_grid.get_allocated_width(),
        )

    glifo_0, grid_0 = medidas[0]
    glifo_3, grid_3 = medidas[3]

    assert glifo_3 > glifo_0, (
        f"o glifo mede {glifo_3}px com a escala 3 e {glifo_0}px com a escala 0 "
        "— ele voltou a ser px cru, fora do alcance do ajuste de fonte"
    )
    assert grid_3 > grid_0, "o grid 4x4 tem de crescer junto com o glifo"
    assert glifo_0 == glyph_size(0) > 20


_LARGURA_DO_GRID_COM_GLIFO_CRU = 4 * 20 + 3 * 2


def test_o_grid_de_botoes_ocupa_parte_do_vao_que_era_buraco() -> None:
    """Entrega 4: os botões deixam de ser 9,2% da largura do card."""
    card = _card_montado()

    largura_do_grid = card._glyph_grid.get_allocated_width()

    assert largura_do_grid > _LARGURA_DO_GRID_COM_GLIFO_CRU, (
        f"o grid 4x4 mede {largura_do_grid}px, o mesmo dos "
        f"{_LARGURA_DO_GRID_COM_GLIFO_CRU}px do glifo cru: ele parou de ocupar "
        "o vão do meio do card"
    )
