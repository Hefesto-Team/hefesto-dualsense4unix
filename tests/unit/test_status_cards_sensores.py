"""Os três módulos de sensor DENTRO do card da aba Status (S2), com GTK real.

O contrato que estes testes travam é sempre o mesmo, em três lugares
diferentes: **ausência de sensor não vira zero na tela**. Três barras de
giroscópio paradas no centro, um medidor de mic vazio ou um touchpad sem
ponto diriam "o controle está em repouso" — quando a verdade é "não tenho
esse sensor". Cada módulo some inteiro em vez disso.

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

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ControllerCard,
    gyro_do_inputs,
    touchpad_do_inputs,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    ESCALA_GYRO_GRAUS_S,
    fracao_do_eixo,
    posicao_normalizada,
    texto_eixo,
    texto_toques,
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


def test_sem_sensor_nenhum_os_tres_modulos_somem(card: Any) -> None:
    card.update(_entry(), _ESTADO, None)

    assert card._gyro_box.get_visible() is False
    assert card._mic_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._sensores_linha.get_visible() is False


def test_gyro_no_payload_acende_as_barras(card: Any) -> None:
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)

    assert card._gyro_box.get_visible() is True
    assert card._gyro_bars._valores == (143.2, -412.0, 22.8)


def test_gyro_some_quando_o_daemon_para_de_mandar(card: Any) -> None:
    """Daemon reiniciado sem o node de motion não pode deixar o último valor
    na tela como se o controle ainda estivesse girando."""
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
    assert card._touch_label.get_text() == "sem toque"


def test_mic_sem_leitura_nao_mostra_modulo(card: Any) -> None:
    card.update(_entry(inputs=_inputs(gyro=_GYRO)), _ESTADO, None)

    assert card._mic_box.get_visible() is False
    assert card._sensores_linha.get_visible() is False


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


def test_mic_sem_mute_lido_mostra_medidor_sem_selo(card: Any) -> None:
    """Medidor sim (o áudio está chegando), selo não: afirmar "ATIVO" sem ter
    lido o mute seria dizer que o microfone está aberto por chute."""
    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.4, muted=None))

    assert card._mic_box.get_visible() is True
    assert card._mic_selo.get_visible() is False


def test_linha_de_sensores_acompanha_quem_sobrou(card: Any) -> None:
    """A linha "Microfone + Touchpad" existe enquanto UM dos dois existir."""
    card.update(_entry(inputs=_inputs(touchpad=_TOUCH)), _ESTADO, None)
    assert card._sensores_linha.get_visible() is True

    card.update(_entry(), _ESTADO, LeituraMic(nivel=0.2, muted=False))
    assert card._sensores_linha.get_visible() is True

    card.update(_entry(), _ESTADO, None)
    assert card._sensores_linha.get_visible() is False


def test_sem_leitor_de_inputs_apaga_tambem_os_sensores(card: Any) -> None:
    """IPC mudo: o card inteiro vira "—". Sensor congelado seria movimento
    inventado, e o medidor parado, silêncio inventado."""
    card.update(
        _entry(inputs=_inputs(gyro=_GYRO, touchpad=_TOUCH)),
        _ESTADO,
        LeituraMic(nivel=0.5, muted=False),
    )

    card.reset_inputs()

    assert card._gyro_box.get_visible() is False
    assert card._touch_box.get_visible() is False
    assert card._mic_box.get_visible() is False
    assert card._gyro_bars._valores == (0.0, 0.0, 0.0)
    assert card._touch_view._toque is None


def test_barras_de_gyro_convivem_com_a_linha_texto_motion(card: Any) -> None:
    """São informações DIFERENTES: a linha diz se o gyro flui para o jogo,
    as barras dizem quanto ele está girando. Uma não substitui a outra."""
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
