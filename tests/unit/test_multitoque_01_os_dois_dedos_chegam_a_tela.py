"""MULTITOQUE-01 — os DOIS dedos do touchpad, do kernel até a bolinha.

**A QUEIXA É DO USUÁRIO, com os quatro DualSense na mesa, 18/09/2026:** *"NA
INTERFACE NA ABA CONTROLES SÓ MOSTRA UM TOQUE NO DESENHO DO SVG APESAR DO
TOUCH SER MULTITOQUE"* — e ela provou no mesmo minuto: *"SE EU USAR 3 DEDOS
DOU ZOOM E 2 DEDOS USO O SCROLL ENTÃO ELE LÊ MUITITOQUE. COMO NUM
NOTEBOOK."*  <!-- noqa-acento: citação literal -->

**O QUE A MEDIÇÃO DEVOLVEU, com os dedos do usuário no controle azul:**

- o nó do kernel declara `ABS_MT_SLOT min=0 max=1` — **dois** dedos, e o
  terceiro não chega nem ao kernel (zero `GESTURE_SWIPE` em 45 s de gesto);
- o libinput emitiu **8 pinças** e **922 eventos de rolagem**, todos com `2`
  dedos — o zoom com três funciona porque a pinça só precisa de dois;
- e o `TouchpadReader` lia `ABS_X`/`ABS_Y`/`BTN_TOUCH`, o caminho de UM
  dedo. **O desenho não estava errado: ele era fiel ao payload.** O segundo
  dedo morria no reader, três camadas antes da tela.

Estas réguas travam a cadeia inteira, e cada uma morde num elo diferente —
porque acertar um só parece certo e não muda nada na tela do usuário.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.interface.cartao_do_controle import dedos_do_inputs
from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader


class _Ecodes:
    """O módulo real, reduzido — COM os códigos multitouch."""

    EV_SYN = 0
    EV_ABS = 3
    EV_KEY = 1
    SYN_REPORT = 0
    ABS_X = 0
    ABS_Y = 1
    ABS_MT_SLOT = 47
    ABS_MT_POSITION_X = 53
    ABS_MT_POSITION_Y = 54
    ABS_MT_TRACKING_ID = 57
    BTN_LEFT = 272
    BTN_TOUCH = 330


class _EcodesPobre:
    """Um dublê SEM os códigos MT — o que as réguas de antes desta data usam."""

    EV_ABS = 3
    EV_KEY = 1
    ABS_X = 0
    ABS_Y = 1
    BTN_LEFT = 272
    BTN_TOUCH = 330


def _evento(tipo: int, code: int, value: int) -> Any:
    return SimpleNamespace(type=tipo, code=code, value=value)


def _reader() -> TouchpadReader:
    # haver (ou não haver) um DualSense na mesa de quem roda.
    return TouchpadReader(
        device_path=Path("/dev/input/event-que-nao-existe"),
        acumular_movimento=False,
    )


def _dedo(reader: TouchpadReader, slot: int, x: int, y: int, ident: int) -> None:
    """Apoia um dedo no `slot`, na ordem em que o kernel manda os eventos."""
    for code, valor in (
        (_Ecodes.ABS_MT_SLOT, slot),
        (_Ecodes.ABS_MT_TRACKING_ID, ident),
        (_Ecodes.ABS_MT_POSITION_X, x),
        (_Ecodes.ABS_MT_POSITION_Y, y),
    ):
        reader._handle_event(_evento(_Ecodes.EV_ABS, code, valor), _Ecodes)


def _levantar(reader: TouchpadReader, slot: int) -> None:
    """Levanta o dedo do `slot` — o kernel manda `TRACKING_ID = -1`."""
    reader._handle_event(
        _evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_SLOT, slot), _Ecodes
    )
    reader._handle_event(
        _evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_TRACKING_ID, -1), _Ecodes
    )


def test_os_dois_dedos_saem_do_reader_com_slot_e_posicao() -> None:
    """O defeito exato: com dois dedos apoiados, `pontos` tinha de ter dois."""
    reader = _reader()

    _dedo(reader, 0, 210, 478, ident=7)
    _dedo(reader, 1, 1603, 470, ident=8)

    pontos = reader.touch_state().pontos
    assert [(p.slot, p.x, p.y) for p in pontos] == [(0, 210, 478), (1, 1603, 470)]
    assert [p.identidade for p in pontos] == [7, 8]


def test_levantar_o_primeiro_dedo_nao_renumera_o_segundo() -> None:
    """Medido no aparelho do usuário: `1: [(1, 1865, 28)]` — o slot 1, sozinho."""
    reader = _reader()
    _dedo(reader, 0, 210, 478, ident=7)
    _dedo(reader, 1, 1865, 28, ident=8)

    _levantar(reader, 0)

    pontos = reader.touch_state().pontos
    assert [(p.slot, p.x, p.y) for p in pontos] == [(1, 1865, 28)]


def _fechar_o_quadro(reader: TouchpadReader) -> None:
    """O ``SYN_REPORT``: é nele que o kernel fecha um quadro de eventos."""
    reader._handle_event(_evento(_Ecodes.EV_SYN, _Ecodes.SYN_REPORT, 0), _Ecodes)


def test_o_dedo_levantado_guarda_a_coordenada_como_o_kernel() -> None:
    """O ``-1`` só troca a identidade; X e Y ficam, como no slot do kernel.

    O kernel não reenvia a coordenada que não mudou. Um dedo novo que cai no
    mesmo X chega com identidade nova e SEM X: o toque tem de estar lá, na
    coordenada guardada, e não sumir (E3 do servidor DSU).
    """
    reader = _reader()
    _dedo(reader, 0, 900, 300, ident=7)
    _fechar_o_quadro(reader)
    _levantar(reader, 0)
    _fechar_o_quadro(reader)

    assert reader.touch_state().pontos == ()

    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_SLOT, 0), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_TRACKING_ID, 9), _Ecodes)
    _fechar_o_quadro(reader)

    pontos = reader.touch_state().pontos
    assert [(p.slot, p.x, p.y, p.identidade) for p in pontos] == [(0, 900, 300, 9)]


def test_dois_toques_seguidos_no_mesmo_x_aparecem_os_dois() -> None:
    """O defeito medido: o segundo toque, no mesmo X do primeiro, sumia."""
    reader = _reader()
    _dedo(reader, 0, 900, 300, ident=7)
    _fechar_o_quadro(reader)
    primeiro = reader.touch_state().pontos
    _levantar(reader, 0)
    _fechar_o_quadro(reader)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_TRACKING_ID, 8), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_POSITION_Y, 301), _Ecodes)
    _fechar_o_quadro(reader)
    segundo = reader.touch_state().pontos

    assert [(p.x, p.y, p.identidade) for p in primeiro] == [(900, 300, 7)]
    assert [(p.x, p.y, p.identidade) for p in segundo] == [(900, 301, 8)]


def test_o_quadro_so_se_publica_no_syn_report() -> None:
    """Um dedo pela metade (identidade já, coordenada ainda não) não vaza."""
    reader = _reader()
    _dedo(reader, 0, 100, 200, ident=1)
    _fechar_o_quadro(reader)

    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_MT_POSITION_X, 500), _Ecodes)

    assert [(p.x, p.y) for p in reader.touch_state().pontos] == [(100, 200)]
    _fechar_o_quadro(reader)
    assert [(p.x, p.y) for p in reader.touch_state().pontos] == [(500, 200)]


def test_o_ecodes_sem_multitouch_nao_derruba_o_laco_de_eventos() -> None:
    """Dublê pobre: o caminho de um dedo continua inteiro, e nada levanta."""
    reader = _reader()

    reader._handle_event(
        _evento(_EcodesPobre.EV_KEY, _EcodesPobre.BTN_TOUCH, 1), _EcodesPobre
    )
    reader._handle_event(
        _evento(_EcodesPobre.EV_ABS, _EcodesPobre.ABS_X, 1400), _EcodesPobre
    )
    reader._handle_event(
        _evento(_EcodesPobre.EV_ABS, _EcodesPobre.ABS_Y, 300), _EcodesPobre
    )
    reader._handle_event(_evento(_EcodesPobre.EV_ABS, 47, 1), _EcodesPobre)

    estado = reader.touch_state()
    assert (estado.touching, estado.x, estado.y) == (True, 1400, 300)
    assert estado.pontos == (), "sem códigos MT não há dedo por slot a afirmar"


def test_a_queda_do_controle_apaga_os_dedos() -> None:
    """Um dedo "apoiado" num controle que saiu da mesa é toque fantasma."""
    reader = _reader()
    _dedo(reader, 0, 210, 478, ident=7)
    _dedo(reader, 1, 1603, 470, ident=8)

    reader._reset_on_disconnect()

    assert reader.touch_state().pontos == ()


def test_o_multitoque_nao_mexe_no_delta_do_cursor() -> None:
    """Os dois dedos são OBSERVAÇÃO — o cursor é do `ABS_X`/`ABS_Y`."""
    reader = TouchpadReader(
        device_path=Path("/dev/input/event-que-nao-existe"),
        acumular_movimento=True,
    )
    _dedo(reader, 0, 210, 478, ident=7)
    _dedo(reader, 1, 1603, 470, ident=8)

    assert reader.consume_motion() == (0, 0)


def _payload(pontos: list[dict[str, int]] | None, **extra: Any) -> dict[str, Any]:
    bloco: dict[str, Any] = {
        "touching": bool(pontos),
        "x": 960,
        "y": 540,
        "width": 1920,
        "height": 1080,
    }
    if pontos is not None:
        bloco["pontos"] = pontos
    bloco.update(extra)
    return {"touchpad": bloco}


def test_as_tres_respostas_do_payload_sao_diferentes() -> None:
    """`None` (não sei) · `()` (ninguém toca) · N dedos. Nunca confundir."""
    assert dedos_do_inputs({}) is None
    assert dedos_do_inputs({"touchpad": "nada disso"}) is None
    assert dedos_do_inputs(_payload([])) == ()
    assert dedos_do_inputs(
        _payload([{"slot": 0, "x": 480, "y": 270, "id": 7},
                  {"slot": 1, "x": 1440, "y": 810, "id": 8}])
    ) == ((0.25, 0.25), (0.75, 0.75))


def test_payload_velho_sem_pontos_cai_para_o_dedo_principal() -> None:
    """Daemon anterior a 18/09: um dedo é o que ele SABE dizer."""
    velho = {"touchpad": {"touching": True, "x": 960, "y": 540}}
    assert dedos_do_inputs(velho) == ((0.5, 0.5),)
    velho_sem_dedo = {"touchpad": {"touching": False, "x": 960, "y": 540}}
    assert dedos_do_inputs(velho_sem_dedo) == ()


def test_ponto_torto_no_payload_nao_derruba_os_outros() -> None:
    """Um dedo ilegível é descartado sozinho; o irmão continua na tela."""
    lido = dedos_do_inputs(
        _payload([{"slot": 0, "x": "isto não é número", "y": 270},
                  {"slot": 1, "x": 1440, "y": 810, "id": 8}])
    )
    assert lido == ((0.75, 0.75),)


def test_a_palavra_e_a_posicao_saem_por_dedo() -> None:
    """`dedos_do_controle` entrega a palavra do produto e um par por bolinha."""
    from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
        MAX_DEDOS,
        dedos_do_controle,
    )

    palavra, dedos = dedos_do_controle(
        _payload([{"slot": 0, "x": 480, "y": 270, "id": 7},
                  {"slot": 1, "x": 1440, "y": 810, "id": 8}])
    )
    assert palavra == "2 toques", "a contagem parou no 1 de antes"
    assert len(dedos) == MAX_DEDOS
    assert dedos == (("sim", (25.0, 25.0)), ("sim", (75.0, 75.0)))

    palavra, dedos = dedos_do_controle(_payload([]))
    assert palavra == "Sem toque"
    assert dedos == (("", None), ("", None)), (
        "bolinha sem dedo tem de APAGAR e não escrever posição"
    )


def test_a_pagina_tem_uma_bolinha_por_dedo_em_todo_card() -> None:
    """A página publicada, medida no disco — não o gerador, o resultado."""
    import re

    pagina = (
        Path(__file__).resolve().parents[2]
        / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"
    )
    if not pagina.exists():  # pragma: no cover - árvore sem a página publicada
        return
    html = pagina.read_text(encoding="utf-8")
    primeiras = html.count('data-campo="touch-ponto"')
    segundas = html.count('data-campo="touch-ponto-2"')
    assert primeiras == segundas, (
        f"{primeiras} bolinha(s) de dedo 1 e {segundas} de dedo 2: "
        "um card perdeu a segunda e o dedo some naquele assento"
    )
    assert segundas >= 1, "nenhuma bolinha para o segundo dedo na página"
    por_dedo = {
        dedo: len(re.findall(
            rf'data-campo="pos-touch{sufixo}" data-hef-alvo="posicao"', html))
        for dedo, sufixo in (("1", ""), ("2", "-2"))
    }
    assert por_dedo == {"1": segundas, "2": segundas}, (
        f"a posição não separa as duas bolinhas em todo card: {por_dedo}"
    )
