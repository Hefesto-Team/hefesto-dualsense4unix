"""Os módulos de sensor DENTRO do card da aba Status (S2), com GTK real.

O contrato que estes testes travam é sempre o mesmo, em cada lugar:
**ausência de sensor não vira zero na tela**. Três barras de giroscópio
paradas no centro ou um touchpad sem ponto diriam "o controle está em
repouso" — quando a verdade é "não tenho esse sensor". Cada módulo some
inteiro em vez disso.

O MICROFONE saiu daqui na MIC-FAIXA-01 e virou faixa própria no rodapé da
aba (`tests/unit/test_mic_faixa_status.py`). O motivo é a outra metade da
mesma regra: para os sensores do card, sumir é a resposta honesta, porque a
ausência é do SENSOR; para o microfone, o sensor existe sempre e o que falta
é o caminho até ele — e aí sumir esconde a causa em vez de contá-la. Um
teste aqui trava que ele não volte.

Também travam a coexistência com a linha `texto_motion`, que já existia: ela
diz se o giroscópio FLUI PARA O JOGO; as barras novas mostram o VALOR. São
duas perguntas diferentes e as duas continuam respondidas.
"""
# ruff: noqa: E402 — gi.require_version precisa vir antes dos imports de gi
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from hefesto_dualsense4unix.app.widgets.controller_card import (
    ControllerCard,
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
    MicMeter,
    cor_da_barra_do_mic,
    fracao_do_eixo,
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


# ---------------------------------------------------------------------------
# Regras puras de leitura do payload
# ---------------------------------------------------------------------------


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
    tocando, fx, fy = touchpad_do_inputs(_inputs(touchpad=_TOUCH))

    assert tocando is True
    assert fx == pytest.approx(0.75)
    assert fy == pytest.approx(0.25)


def test_touchpad_com_limites_proprios_nao_usa_1920x1080() -> None:
    """Quem declara os limites é o kernel, no próprio payload."""
    bloco = {"touching": True, "x": 500, "y": 250, "width": 1000, "height": 500}

    _tocando, fx, fy = touchpad_do_inputs(_inputs(touchpad=bloco))

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
    """Campo fixo: a 10 Hz, texto que muda de largura faz o painel respirar
    (a mesma armadilha do BUG-STATUS-LABEL-REFLOW-01 nos sticks)."""
    larguras = {len(texto_eixo(v)) for v in (0.0, -9.9, 143.2, -412.0, 1999.9)}

    assert larguras == {7}


def test_posicao_normalizada_grampeia_fora_de_faixa() -> None:
    assert posicao_normalizada(9999, -50, 1920, 1080) == (1.0, 0.0)
    assert posicao_normalizada(10, 10, 0, 0) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("n", "esperado"), [(0, "sem toque"), (1, "1 toque"), (2, "2 toques")]
)
def test_texto_toques(n: int, esperado: str) -> None:
    assert texto_toques(n) == esperado


# ---------------------------------------------------------------------------
# Card: cada módulo aparece só quando há sensor
# ---------------------------------------------------------------------------


def test_sem_sensor_nenhum_os_modulos_do_card_somem(card: Any) -> None:
    card.update(_entry(), _ESTADO)

    assert card._gyro_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._sensores_linha.get_visible() is False


def test_o_card_nao_tem_mais_medidor_de_microfone(card: Any) -> None:
    """MIC-FAIXA-01: o microfone saiu do card e virou faixa no rodapé da aba.

    Um fato, um dono. Enquanto o medidor morasse aqui DENTRO, ele continuaria
    sumindo quando não houvesse source — e é esse sumiço que a faixa existe
    para acabar. Este teste morde se alguém reintroduzir o módulo aqui: dois
    lugares mostrando o mesmo microfone é o começo de dois lugares
    discordando.
    """
    card.update(_entry(), _ESTADO)

    assert not hasattr(card, "_mic_meter")
    assert not hasattr(card, "_mic_box")
    assert not hasattr(card, "_mic_selo")


def test_gyro_no_payload_acende_as_barras(card: Any) -> None:
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO)

    assert card._gyro_box.get_visible() is True
    assert card._gyro_bars._valores == (143.2, -412.0, 22.8)


def test_gyro_some_quando_o_daemon_para_de_mandar(card: Any) -> None:
    """Daemon reiniciado sem o node de motion não pode deixar o último valor
    na tela como se o controle ainda estivesse girando."""
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO)

    card.update(_entry(), _ESTADO)

    assert card._gyro_box.get_visible() is False
    assert card._gyro_bars._valores == (0.0, 0.0, 0.0)


def test_touchpad_com_dedo_desenha_o_ponto(card: Any) -> None:
    card.update(_entry(inputs=_inputs(touchpad=_TOUCH)), _ESTADO)

    assert card._touch_box.get_visible() is True
    assert card._touch_view._toque == pytest.approx((0.75, 0.25))
    assert card._touch_label.get_text() == "1 toque"


def test_touchpad_sem_dedo_apaga_o_ponto_mas_mantem_o_painel(card: Any) -> None:
    """O sensor existe (o retângulo fica); o que some é o ponto."""
    solto = dict(_TOUCH, touching=False)

    card.update(_entry(inputs=_inputs(touchpad=solto)), _ESTADO)

    assert card._touch_box.get_visible() is True
    assert card._touch_view._toque is None
    assert card._touch_label.get_text() == "sem toque"


def test_linha_de_sensores_acompanha_o_touchpad(card: Any) -> None:
    """Com o microfone fora do card, a linha de sensores é o touchpad."""
    card.update(_entry(inputs=_inputs(touchpad=_TOUCH)), _ESTADO)
    assert card._sensores_linha.get_visible() is True

    card.update(_entry(), _ESTADO)
    assert card._sensores_linha.get_visible() is False


def test_sem_leitor_de_inputs_apaga_tambem_os_sensores(card: Any) -> None:
    """IPC mudo: o card inteiro vira "—". Sensor congelado seria movimento
    inventado, e o medidor parado, silêncio inventado."""
    card.update(_entry(inputs=_inputs(gyro=_GYRO, touchpad=_TOUCH)), _ESTADO)

    card.reset_inputs()

    assert card._gyro_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._gyro_bars._valores == (0.0, 0.0, 0.0)
    assert card._touch_view._toque is None


# ---------------------------------------------------------------------------
# Medidor do microfone: onda de amplitude, não escada fixa
# ---------------------------------------------------------------------------


def test_cor_da_barra_do_mic_tem_tres_faixas() -> None:
    """A cor sai da amplitude DAQUELA barra. Na escada fixa antiga, todas as
    barras acesas usavam a mesma cor e o verde de pico não aparecia nunca."""
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


def test_medidor_do_mic_muda_de_forma_a_cada_leitura() -> None:
    """A forma é o dado: níveis diferentes têm de deixar barras diferentes.
    Antes, o desenho era sempre a mesma escada e só mudava quantas acendiam."""
    medidor = MicMeter()
    for nivel in (0.1, 0.8, 0.35):
        medidor.set_nivel(nivel)

    assert medidor._historico[-3:] == pytest.approx((0.1, 0.8, 0.35))
    assert len(set(medidor._historico)) > 1


def test_mic_que_para_de_medir_leva_a_onda_junto() -> None:
    """Reaparecer com o traço da última captura seria mostrar áudio que não
    está mais entrando."""
    medidor = MicMeter()
    medidor.set_nivel(0.7)

    medidor.set_inativo()

    assert not any(medidor._historico)
    assert medidor._inativo is True


# ---------------------------------------------------------------------------
# Lightbar como BARRA na linha de baixo (mesma fonte do swatch do título)
# ---------------------------------------------------------------------------


def test_lightbar_com_cor_conhecida_vira_barra_e_hex(card: Any) -> None:
    card.update(_entry(lightbar_rgb=[255, 121, 198]), _ESTADO)

    assert card._lightbar_box.get_visible() is True
    assert card._lightbar_bar._rgb == (255, 121, 198)
    assert card._lightbar_hex.get_text() == "#ff79c6"


def test_lightbar_sem_cor_conhecida_esconde_a_barra(card: Any) -> None:
    """"Não sei" e "apagada" não podem desenhar a mesma faixa preta."""
    card.update(_entry(lightbar_rgb=None), _ESTADO)

    assert card._lightbar_box.get_visible() is False


# ---------------------------------------------------------------------------
# Alto-falante: consumo defensivo enquanto o backend não existe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entrada",
    [
        {"speaker": {"volume": 180, "muted": False}},
        {"inputs": _inputs(speaker={"volume": 180, "muted": False})},
    ],
)
def test_speaker_lido_do_entry_ou_do_inputs(entrada: dict[str, Any]) -> None:
    """Quem publica é o daemon; o widget não pode quebrar por causa de ONDE
    a chave mora."""
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


def test_bloco_do_speaker_some_sem_a_chave(card: Any) -> None:
    """A FRENTE D ainda está construindo o backend: sem a chave, o módulo não
    aparece — nunca uma barra em zero fingindo volume no mínimo."""
    card.update(_entry(), _ESTADO)

    assert card._speaker_box.get_visible() is False


def test_bloco_do_speaker_acende_com_a_chave(card: Any) -> None:
    card.update(_entry(speaker={"volume": 128, "muted": False}), _ESTADO)

    assert card._speaker_box.get_visible() is True
    assert card._speaker_bar._fracao == pytest.approx(128 / 255)
    assert card._speaker_label.get_text() == "50 %"


def test_speaker_mudo_diz_mudo_em_vez_de_porcentagem(card: Any) -> None:
    card.update(_entry(speaker={"volume": 200, "muted": True}), _ESTADO)

    assert card._speaker_bar._muted is True
    assert card._speaker_label.get_text() == "mudo"


def test_texto_volume_sem_mute_lido_mostra_so_a_porcentagem() -> None:
    assert texto_volume(255, None) == "100 %"
    assert texto_volume(0, None) == "0 %"


# ---------------------------------------------------------------------------
# Arranjo em 3 linhas (STATUS-3-LINHAS-01)
# ---------------------------------------------------------------------------


def test_botoes_ficam_na_linha_de_baixo_mesmo_sem_mic_nem_touchpad(
    card: Any,
) -> None:
    """A armadilha do reagrupamento: se os botões morassem DENTRO de
    `_sensores_linha`, sumiriam junto com ela no caso mais comum — controle
    sem microfone atribuível e com o dedo fora do touchpad."""
    card.update(_entry(), _ESTADO)

    assert card._sensores_linha.get_visible() is False
    assert card._linha_inferior.get_visible() is True
    assert card._glyph_grid.get_visible() is True


def test_gyro_oculto_nao_devolve_a_largura_toda_aos_gatilhos(card: Any) -> None:
    """O giroscópio nasce oculto e aparece quando há sensor. Num `Gtk.Box` os
    gatilhos pulariam para a largura inteira e voltariam para metade — reflow
    visível. O grid homogêneo guarda a coluna pelo `_gyro_slot`, que fica
    visível mesmo com o módulo escondido."""
    card.update(_entry(), _ESTADO)

    assert card._gyro_box.get_visible() is False
    assert card._gyro_slot.get_visible() is True

    grid = card._gyro_slot.get_parent()
    assert grid.get_column_homogeneous() is True
    assert grid.child_get_property(card._gyro_slot, "left-attach") == 1
    assert grid.child_get_property(card._l2_bar.get_parent(), "left-attach") == 0


def test_barras_de_gyro_convivem_com_a_linha_texto_motion(card: Any) -> None:
    """São informações DIFERENTES: a linha diz se o gyro flui para o jogo,
    as barras dizem quanto ele está girando. Uma não substitui a outra."""
    estado = {
        "native_mode": False,
        "rumble_ff": {
            "per_vpad": [{"player": 1, "motion_streaming": True, "motion_hz": 250.0}]
        },
    }

    card.update(_entry(inputs=_inputs(gyro=_GYRO)), estado)

    assert card._motion_label.get_visible() is True
    assert "fluindo para o jogo" in card._motion_label.get_text()
    assert card._gyro_box.get_visible() is True
