"""O leitor do controle ressincroniza no ``SYN_DROPPED``.

Quando a fila do nó transborda, o kernel descarta eventos: o soltar perdido não volta sozinho, e o
botão fica preso no retrato até um novo aperto. A régua conduz o laço de leitura de verdade
(``_read_until_signaled``) com um nó que entrega lotes prontos e guarda o estado como o kernel.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core.evdev_reader import (
    EvdevReader,
    MotionSensorReader,
    TouchpadReader,
)

EIXOS_DO_DUALSENSE = {ecodes.ABS_X: (0, 255), ecodes.ABS_Y: (0, 255), ecodes.ABS_RX: (0, 255),
                      ecodes.ABS_RY: (0, 255), ecodes.ABS_Z: (0, 255), ecodes.ABS_RZ: (0, 255),
                      ecodes.ABS_HAT0X: (-1, 1), ecodes.ABS_HAT0Y: (-1, 1)}
EIXOS_DO_PRO = {ecodes.ABS_X: (-32767, 32767), ecodes.ABS_Y: (-32767, 32767),
                ecodes.ABS_RX: (-32767, 32767), ecodes.ABS_RY: (-32767, 32767),
                ecodes.ABS_HAT0X: (-1, 1), ecodes.ABS_HAT0Y: (-1, 1)}
FAMILIAS = {"dualsense": EIXOS_DO_DUALSENSE, "edge": EIXOS_DO_DUALSENSE, "pro": EIXOS_DO_PRO,
            "8bitdo": EIXOS_DO_PRO}
MESAS = {
    "tres_cabos_e_um_radio": ("dualsense", "edge", "pro", "8bitdo"),
    "um_cabo_e_tres_radios": ("8bitdo", "pro", "dualsense", "edge"),
    "dois_e_dois": ("pro", "dualsense", "8bitdo", "edge"),
    "so_o_p3": (None, None, "pro", None),
}


def _evento(tipo: int, codigo: int, valor: int = 0) -> Any:
    return SimpleNamespace(type=tipo, code=codigo, value=valor, sec=0, usec=0)


def _tecla(codigo: int, valor: int) -> Any:
    return _evento(ecodes.EV_KEY, codigo, valor)


def _eixo(codigo: int, valor: int) -> Any:
    return _evento(ecodes.EV_ABS, codigo, valor)


FIM_DO_QUADRO = _evento(ecodes.EV_SYN, ecodes.SYN_REPORT)
BURACO = _evento(ecodes.EV_SYN, ecodes.SYN_DROPPED)


class _No:
    """O nó aberto: lotes de eventos e o estado que o ``input_dev`` guarda à parte da fila."""

    def __init__(self, eixos: dict[int, tuple[int, int]], lotes: Iterable[list[Any]],
                 leitor: Any, *, teclas_falham: bool = False) -> None:
        self.eixos = eixos
        self.lotes = list(lotes)
        self.leitor = leitor
        self.teclas: set[int] = set()
        self.valores: dict[int, int] = {}
        self.teclas_falham = teclas_falham
        self.pedidos = 0
        self.fd = 0

    def capabilities(self) -> dict[int, Any]:
        return {ecodes.EV_ABS: [
            (code, SimpleNamespace(min=faixa[0], max=faixa[1], flat=0, fuzz=0, resolution=0))
            for code, faixa in self.eixos.items()]}

    def active_keys(self) -> list[int]:
        self.pedidos += 1
        if self.teclas_falham:
            raise OSError(19, "No such device")
        return sorted(self.teclas)

    def absinfo(self, codigo: int) -> Any:
        if codigo not in self.eixos:
            raise OSError(22, "Invalid argument")
        return SimpleNamespace(value=self.valores.get(codigo, 0))

    def read(self) -> Any:
        lote = self.lotes.pop(0)
        try:
            yield from lote
        finally:
            if not self.lotes:
                self.leitor._stop_flag.set()


def _conduzir(leitor: Any, no: _No) -> None:
    """O laço de leitura de verdade, até o nó acabar."""
    leitor._wait_ready = lambda dev: [dev]
    leitor._stop_flag.clear()
    assert leitor._read_until_signaled(no, ecodes) == "stop"


def _aberto(eixos: dict[int, tuple[int, int]]) -> tuple[EvdevReader, _No]:
    leitor = EvdevReader(device_path=Path("/nao/existe"), target_uniq="aabbcc000011")
    no = _No(eixos, [], leitor)
    no.valores = {code: (lo + hi) // 2 for code, (lo, hi) in eixos.items()}
    no.valores.update({ecodes.ABS_Z: 0, ecodes.ABS_RZ: 0})
    leitor._on_device_opened(no)
    return leitor, no


def _apertar(leitor: EvdevReader, no: _No, codigo: int) -> None:
    no.lotes = [[_tecla(codigo, 1), FIM_DO_QUADRO]]
    no.teclas.add(codigo)
    _conduzir(leitor, no)


def test_o_soltar_perdido_sai_solto_pelo_kernel() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    _apertar(leitor, no, ecodes.BTN_SOUTH)
    assert "cross" in leitor.snapshot().buttons_pressed

    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "cross" not in leitor.snapshot().buttons_pressed


def test_o_lote_lido_antes_da_releitura_nao_prende_o_botao() -> None:
    """O ``EVIOCGKEY`` esvazia as teclas da fila: o soltar que estava ali não chega mais, e o
    aperto já lido no mesmo lote não pode voltar por cima do que o kernel acabou de dizer."""
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.lotes = [[BURACO, FIM_DO_QUADRO, _tecla(ecodes.BTN_SOUTH, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "cross" not in leitor.snapshot().buttons_pressed


def test_o_lote_de_depois_da_releitura_continua_valendo() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.lotes = [[BURACO, FIM_DO_QUADRO], [_tecla(ecodes.BTN_SOUTH, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "cross" in leitor.snapshot().buttons_pressed


def test_sem_a_releitura_o_resto_do_lote_e_o_que_ha() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    no.teclas_falham = True

    no.lotes = [[BURACO, FIM_DO_QUADRO, _tecla(ecodes.BTN_SOUTH, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "cross" in leitor.snapshot().buttons_pressed


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def info(self, evento: str, **campos: Any) -> None:
        self.linhas.append((evento, campos))


def test_a_linha_da_ressincronia_diz_qual_no_transbordou(
        monkeypatch: pytest.MonkeyPatch) -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    pad, no_do_touchpad = _touchpad()
    diario = _Diario()
    monkeypatch.setattr(evdev_reader, "logger", diario)

    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    no_do_touchpad.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(pad, no_do_touchpad)

    assert diario.linhas == [
        ("evdev_ressincronizado", {"path": "/nao/existe", "botoes": 0, "mudou": False}),
        ("touchpad_ressincronizado", {"path": "/nao/existe", "dedo": True})]


def test_o_direcional_perdido_tambem_sai() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    no.valores[ecodes.ABS_HAT0Y] = -1
    no.lotes = [[_eixo(ecodes.ABS_HAT0Y, -1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    assert "dpad_up" in leitor.snapshot().buttons_pressed

    no.valores[ecodes.ABS_HAT0Y] = 0
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "dpad_up" not in leitor.snapshot().buttons_pressed


def test_o_gatilho_digital_perdido_volta_a_zero() -> None:
    leitor, no = _aberto(EIXOS_DO_PRO)
    _apertar(leitor, no, ecodes.BTN_TL2)
    assert leitor.snapshot().l2_raw == 255

    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot().l2_raw == 0
    assert "l2_btn" not in leitor.snapshot().buttons_pressed


def test_o_gatilho_digital_apertado_no_buraco_vai_ao_talo() -> None:
    leitor, no = _aberto(EIXOS_DO_PRO)

    no.teclas.add(ecodes.BTN_TR2)
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot().r2_raw == 255 and leitor.snapshot().l2_raw == 0


def test_o_gatilho_analogico_vem_do_eixo_e_nao_do_botao() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.teclas.add(ecodes.BTN_TL2)
    no.valores[ecodes.ABS_Z] = 140
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot().l2_raw == 140


def test_os_eixos_voltam_mesmo_no_talo_do_minimo() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.valores.update({ecodes.ABS_X: 0, ecodes.ABS_RY: 200, ecodes.ABS_RZ: 90})
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    retrato = leitor.snapshot()
    assert (retrato.lx, retrato.ry, retrato.r2_raw) == (0, 200, 90)


def test_o_resto_do_quadro_perdido_nao_entra() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.lotes = [[BURACO, _tecla(ecodes.BTN_EAST, 1), _eixo(ecodes.ABS_X, 7), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    retrato = leitor.snapshot()
    assert "circle" not in retrato.buttons_pressed and retrato.lx != 7
    assert retrato.apertos == {}


def test_o_quadro_seguinte_ao_buraco_vale_inteiro() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.lotes = [[BURACO, FIM_DO_QUADRO, _tecla(ecodes.BTN_EAST, 1), FIM_DO_QUADRO]]
    no.teclas.add(ecodes.BTN_EAST)
    _conduzir(leitor, no)

    retrato = leitor.snapshot()
    assert "circle" in retrato.buttons_pressed
    assert retrato.apertos == {"circle": 1}


def test_o_aperto_do_buraco_conta_uma_borda_so() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)

    no.teclas.add(ecodes.BTN_NORTH)
    no.valores[ecodes.ABS_HAT0X] = 1
    no.lotes = [[BURACO, FIM_DO_QUADRO, _tecla(ecodes.BTN_NORTH, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot().apertos == {"triangle": 1, "dpad_right": 1}


def test_o_retrato_que_muda_acorda_quem_entrega(monkeypatch: pytest.MonkeyPatch) -> None:
    acordou: list[int] = []
    monkeypatch.setattr(evdev_reader, "_acordar_quem_entrega_ao_jogo", lambda: acordou.append(1))
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    _apertar(leitor, no, ecodes.BTN_SOUTH)
    acordou.clear()

    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    assert acordou == []

    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    assert acordou == [1]


def test_as_teclas_ilegiveis_nao_derrubam_nem_mexem_no_retrato() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    _apertar(leitor, no, ecodes.BTN_SOUTH)
    antes = leitor.snapshot()

    no.teclas_falham = True
    no.valores[ecodes.ABS_X] = 3
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot() == antes


def test_o_eixo_ilegivel_fica_como_estava_e_o_botao_sai() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    _apertar(leitor, no, ecodes.BTN_SOUTH)
    lx = leitor.snapshot().lx

    def absinfo_falha(_codigo: int) -> Any:
        raise OSError(19, "No such device")

    no.absinfo = absinfo_falha  # type: ignore[method-assign]
    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.snapshot().lx == lx and leitor.snapshot().buttons_pressed == frozenset()


def test_sem_buraco_o_handle_event_ve_os_mesmos_eventos_e_ninguem_relê() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    vistos: list[Any] = []
    original = leitor._handle_event
    leitor._handle_event = lambda e, c: (vistos.append(e), original(e, c))[1]  # type: ignore[method-assign]
    lote = [_tecla(ecodes.BTN_SOUTH, 1), _eixo(ecodes.ABS_X, 10), FIM_DO_QUADRO,
            _tecla(ecodes.BTN_SOUTH, 0), FIM_DO_QUADRO]

    no.lotes = [list(lote)]
    _conduzir(leitor, no)

    assert vistos[:5] == lote
    assert no.pedidos == 0


def test_o_buraco_aberto_nao_atravessa_a_reconexao() -> None:
    leitor, no = _aberto(EIXOS_DO_DUALSENSE)
    leitor._no_buraco = True

    no.lotes = [[_tecla(ecodes.BTN_EAST, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "circle" in leitor.snapshot().buttons_pressed and no.pedidos == 0


@pytest.mark.parametrize(
    ("mesa", "no_buraco"),
    [(mesa, posicao) for mesa in MESAS.values()
     for posicao, familia in enumerate(mesa) if familia is not None],
    ids=[f"{nome}-p{posicao + 1}" for nome, mesa in MESAS.items()
         for posicao, familia in enumerate(mesa) if familia is not None])
def test_um_leitor_transbordando_nao_mexe_nos_outros(
        mesa: tuple[str | None, ...], no_buraco: int) -> None:
    leitores = {
        posicao: _aberto(FAMILIAS[familia])
        for posicao, familia in enumerate(mesa) if familia is not None
    }
    for leitor, no in leitores.values():
        _apertar(leitor, no, ecodes.BTN_SOUTH)
    retratos = {posicao: par[0].snapshot() for posicao, par in leitores.items()}

    leitor, no = leitores[no_buraco]
    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert "cross" not in leitor.snapshot().buttons_pressed
    for posicao, (outro, _no) in leitores.items():
        if posicao != no_buraco:
            assert outro.snapshot() == retratos[posicao]


def _touchpad() -> tuple[TouchpadReader, _No]:
    leitor = TouchpadReader(device_path=Path("/nao/existe"), target_uniq="aabbcc000011",
                            acumular_movimento=True)
    no = _No({ecodes.ABS_X: (0, 1919), ecodes.ABS_Y: (0, 1079), ecodes.ABS_MT_SLOT: (0, 1)},
             [], leitor)
    no.lotes = [[_tecla(ecodes.BTN_TOUCH, 1), _eixo(ecodes.ABS_MT_SLOT, 0),
                 _eixo(ecodes.ABS_MT_TRACKING_ID, 5), _eixo(ecodes.ABS_MT_POSITION_X, 100),
                 _eixo(ecodes.ABS_MT_POSITION_Y, 200), _eixo(ecodes.ABS_X, 100),
                 _eixo(ecodes.ABS_Y, 200), FIM_DO_QUADRO]]
    no.teclas.add(ecodes.BTN_TOUCH)
    no.valores.update({ecodes.ABS_X: 100, ecodes.ABS_Y: 200})
    _conduzir(leitor, no)
    leitor.consume_motion()
    assert leitor.touch_state().touching and len(leitor.touch_state().pontos) == 1
    return leitor, no


def test_o_dedo_que_saiu_no_buraco_nao_prende_o_toque() -> None:
    leitor, no = _touchpad()

    no.teclas.clear()
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    estado = leitor.touch_state()
    assert not estado.touching and estado.pontos == ()


def test_o_dedo_que_andou_no_buraco_nao_vira_salto_do_cursor() -> None:
    leitor, no = _touchpad()

    no.valores.update({ecodes.ABS_X: 1500, ecodes.ABS_Y: 900})
    no.lotes = [[BURACO, _eixo(ecodes.ABS_X, 1490), FIM_DO_QUADRO],
                [_eixo(ecodes.ABS_X, 1510), _eixo(ecodes.ABS_Y, 910), FIM_DO_QUADRO,
                 _eixo(ecodes.ABS_X, 1520), _eixo(ecodes.ABS_Y, 915), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.consume_motion() == (10, 5)
    assert leitor.touch_state().touching and leitor.touch_state().x == 1520


def test_o_clique_solto_no_buraco_nao_prende_a_regiao() -> None:
    leitor, no = _touchpad()
    no.teclas.add(ecodes.BTN_LEFT)
    no.lotes = [[_tecla(ecodes.BTN_LEFT, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)
    assert leitor.regions_pressed() == {"touchpad_left_press"}

    no.teclas.discard(ecodes.BTN_LEFT)
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.regions_pressed() == frozenset()


def test_o_clique_mantido_no_buraco_fica_na_regiao_do_aperto() -> None:
    leitor, no = _touchpad()
    no.teclas.add(ecodes.BTN_LEFT)
    no.lotes = [[_tecla(ecodes.BTN_LEFT, 1), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    no.valores[ecodes.ABS_X] = 1500
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.regions_pressed() == {"touchpad_left_press"}


def test_o_clique_apertado_no_buraco_nasce_na_regiao_do_dedo() -> None:
    leitor, no = _touchpad()

    no.teclas.add(ecodes.BTN_LEFT)
    no.valores[ecodes.ABS_X] = 1500
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.regions_pressed() == {"touchpad_right_press"}


def test_o_slot_perdido_volta_do_kernel() -> None:
    leitor, no = _touchpad()

    no.valores[ecodes.ABS_MT_SLOT] = 1
    no.lotes = [[BURACO, FIM_DO_QUADRO],
                [_eixo(ecodes.ABS_MT_TRACKING_ID, 9), _eixo(ecodes.ABS_MT_POSITION_X, 300),
                 _eixo(ecodes.ABS_MT_POSITION_Y, 400), FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert [ponto.slot for ponto in leitor.touch_state().pontos] == [1]


def test_as_teclas_ilegiveis_nao_derrubam_o_touchpad() -> None:
    leitor, no = _touchpad()
    antes = leitor.touch_state()

    no.teclas_falham = True
    no.lotes = [[BURACO, FIM_DO_QUADRO]]
    _conduzir(leitor, no)

    assert leitor.touch_state().touching == antes.touching


def test_o_movimento_segue_descontando_a_taxa_sem_reler_o_kernel() -> None:
    leitor = MotionSensorReader(device_path=Path("/nao/existe"), target_uniq="aabbcc000011")
    no = _No({}, [[BURACO, _eixo(ecodes.ABS_RX, 10), FIM_DO_QUADRO]], leitor)
    vistos: list[Any] = []
    leitor._handle_event = lambda e, c: vistos.append(e)  # type: ignore[method-assign]

    _conduzir(leitor, no)

    assert vistos[:3] == [BURACO, _eixo(ecodes.ABS_RX, 10), FIM_DO_QUADRO]
    assert no.pedidos == 0
