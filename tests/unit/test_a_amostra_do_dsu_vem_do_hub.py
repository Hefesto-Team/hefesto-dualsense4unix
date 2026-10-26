"""A amostra que o servidor DSU lê do hub de sensores (E3 do servidor DSU).

Os leitores são os de verdade (``TouchpadReader`` e ``MotionSensorReader``) com
os eventos do kernel entrando por ``_handle_event``, sem thread e sem nó; o que
é dublê são as fábricas do hub, e os dublês RECUSAM: quem drena o ângulo ou o
delta do cursor anota e a régua reprova.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader, TouchpadReader
from hefesto_dualsense4unix.daemon.lifecycle import HUB_AUSENTE
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub


class _Ecodes:
    EV_SYN = 0
    EV_KEY = 1
    EV_ABS = 3
    EV_MSC = 4
    SYN_REPORT = 0
    MSC_TIMESTAMP = 5
    ABS_X = 0
    ABS_Y = 1
    ABS_Z = 2
    ABS_RX = 3
    ABS_RY = 4
    ABS_RZ = 5
    ABS_MT_SLOT = 47
    ABS_MT_POSITION_X = 53
    ABS_MT_POSITION_Y = 54
    ABS_MT_TRACKING_ID = 57
    BTN_TOUCH = 330


def _ev(tipo: int, code: int, value: int) -> Any:
    return SimpleNamespace(type=tipo, code=code, value=value, sec=0, usec=0)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _LeitorDeVerdade:
    """Embrulha um leitor real: sem thread, com grab anotado e drenagem recusada."""

    def __init__(self, real: Any) -> None:
        self.real = real
        self.parado = False
        self.grab_state = "off"
        self.grabs: list[bool] = []
        self.drenou: list[str] = []

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def set_grab(self, valor: bool) -> None:
        self.grabs.append(valor)
        self.grab_state = "held" if valor else "off"

    def consume_angulo(self) -> Any:
        self.drenou.append("consume_angulo")
        raise AssertionError("a amostra do DSU não drena o ângulo")

    def consume_motion(self) -> Any:
        self.drenou.append("consume_motion")
        raise AssertionError("a amostra do DSU não drena o cursor")

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.real, nome)


def _toque_real() -> TouchpadReader:
    return TouchpadReader(device_path=Path("/dev/input/nao-existe"), acumular_movimento=False)


def _movimento_real() -> MotionSensorReader:
    return MotionSensorReader(device_path=Path("/dev/input/nao-existe"))


def _dedo(leitor: TouchpadReader, slot: int, ident: int, x: int | None, y: int | None) -> None:
    e = _Ecodes
    eventos = [(e.ABS_MT_SLOT, slot), (e.ABS_MT_TRACKING_ID, ident)]
    if x is not None:
        eventos.append((e.ABS_MT_POSITION_X, x))
    if y is not None:
        eventos.append((e.ABS_MT_POSITION_Y, y))
    for code, valor in eventos:
        leitor._handle_event(_ev(e.EV_ABS, code, valor), e)
    leitor._handle_event(_ev(e.EV_SYN, e.SYN_REPORT, 0), e)


def _hub(
    relogio: _Relogio, *, motion: Any = None, touch: Any = None
) -> tuple[SensorHub, dict[str, _LeitorDeVerdade]]:
    criados: dict[str, _LeitorDeVerdade] = {}

    def fabrica(tipo: str, real: Any) -> Any:
        def _cria(uniq: str, _node: Any) -> Any:
            leitor = _LeitorDeVerdade(real)
            criados[tipo] = leitor
            return leitor

        return _cria

    hub = SensorHub(
        motion_factory=fabrica("motion", motion or _movimento_real()),
        touch_factory=fabrica("touchpad", touch or _toque_real()),
        descobrir_motion=lambda: {"aa": "/dev/input/event9"},
        descobrir_touch=lambda: {"aa": "/dev/input/event10"},
        relogio=relogio,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    hub._sensores_desligados = lambda mudou=False: set()  # type: ignore[method-assign]
    return hub, criados


def test_sem_leitor_a_amostra_e_none() -> None:
    hub, _ = _hub(_Relogio())

    assert hub.amostra_do_dsu("aa") is None


def test_dois_toques_seguidos_no_mesmo_x_aparecem_os_dois() -> None:
    toque = _toque_real()
    hub, _ = _hub(_Relogio(), touch=toque)
    hub.amostra_do_dsu("aa")
    hub.reconciliar()

    _dedo(toque, 0, 7, 900, 300)
    primeiro = hub.amostra_do_dsu("aa")
    _dedo(toque, 0, -1, None, None)
    _dedo(toque, 0, 8, None, 301)
    segundo = hub.amostra_do_dsu("aa")

    assert primeiro is not None and segundo is not None
    assert [(p.x, p.y, p.identidade) for p in primeiro.toques] == [(900, 300, 7)]
    assert [(p.x, p.y, p.identidade) for p in segundo.toques] == [(900, 301, 8)]


def test_o_movimento_que_levanta_nao_derruba_o_toque() -> None:
    class _Quebrado:
        def amostra_do_movimento(self) -> Any:
            raise RuntimeError("node sumiu")

    toque = _toque_real()
    hub, _ = _hub(_Relogio(), motion=_Quebrado(), touch=toque)
    hub.amostra_do_dsu("aa")
    hub.reconciliar()
    _dedo(toque, 0, 7, 10, 20)

    amostra = hub.amostra_do_dsu("aa")

    assert amostra is not None
    assert amostra.com_toque and not amostra.com_movimento
    assert [(p.x, p.y) for p in amostra.toques] == [(10, 20)]


def test_o_toque_que_levanta_nao_derruba_o_movimento_e_sem_nenhum_e_none() -> None:
    class _ToqueQuebrado:
        def touch_state(self) -> Any:
            raise RuntimeError("node sumiu")

    class _MovimentoQuebrado:
        def amostra_do_movimento(self) -> Any:
            raise RuntimeError("node sumiu")

    hub, _ = _hub(_Relogio(), touch=_ToqueQuebrado())
    hub.amostra_do_dsu("aa")
    hub.reconciliar()
    amostra = hub.amostra_do_dsu("aa")
    assert amostra is not None and amostra.com_movimento and not amostra.com_toque

    hub2, _ = _hub(_Relogio(), motion=_MovimentoQuebrado(), touch=_ToqueQuebrado())
    hub2.amostra_do_dsu("aa")
    hub2.reconciliar()
    assert hub2.amostra_do_dsu("aa") is None


def test_a_amostra_mantem_o_leitor_vivo_e_cinco_segundos_sem_pedido_o_matam() -> None:
    relogio = _Relogio()
    hub, criados = _hub(relogio)
    hub.amostra_do_dsu("aa")
    hub.reconciliar()
    assert not criados["motion"].parado

    for _ in range(12):
        relogio.agora += 0.5
        assert hub.amostra_do_dsu("aa") is not None
        hub.reconciliar()
    assert not criados["motion"].parado, "o pedido tem de renovar a demanda"

    relogio.agora += 5.5
    hub.reconciliar()
    assert criados["motion"].parado and criados["touchpad"].parado


def test_a_amostra_nao_drena_nada() -> None:
    relogio = _Relogio()
    hub, criados = _hub(relogio)
    hub.amostra_do_dsu("aa")
    hub.reconciliar()

    for _ in range(3):
        hub.amostra_do_dsu("aa")

    assert criados["motion"].drenou == [] and criados["touchpad"].drenou == []


def test_o_carimbo_atravessa_a_volta_do_u32_e_a_epoca_sobe_na_reabertura() -> None:
    leitor = _movimento_real()
    dev = SimpleNamespace(absinfo=lambda code: (_ for _ in ()).throw(OSError("sem node")))
    leitor._on_device_opened(dev)
    assert leitor.amostra_do_movimento().carimbo_us is None
    primeira = leitor.amostra_do_movimento().epoca

    for valor in (0xFFFFFFF0, 0xFFFFFFF8, 0x00000008):
        leitor._handle_event(_ev(_Ecodes.EV_MSC, _Ecodes.MSC_TIMESTAMP, valor), _Ecodes)
    assert leitor.amostra_do_movimento().carimbo_us == 0xFFFFFFF0 + 8 + 16

    leitor._on_device_opened(dev)
    depois = leitor.amostra_do_movimento()
    assert depois.epoca == primeira + 1
    assert depois.carimbo_us is None


def test_o_carimbo_negativo_do_evdev_e_lido_como_u32() -> None:
    leitor = _movimento_real()
    leitor._handle_event(_ev(_Ecodes.EV_MSC, _Ecodes.MSC_TIMESTAMP, -16), _Ecodes)
    leitor._handle_event(_ev(_Ecodes.EV_MSC, _Ecodes.MSC_TIMESTAMP, 16), _Ecodes)

    assert leitor.amostra_do_movimento().carimbo_us == (0xFFFFFFF0) + 32


def test_o_hub_ausente_responde_none() -> None:
    assert HUB_AUSENTE.amostra_do_dsu("aa") is None  # type: ignore[func-returns-value]
    HUB_AUSENTE.segurar_o_dedo("aa")


def test_segurar_o_dedo_grava_o_nó_do_touchpad_e_solta_ao_vencer_o_prazo() -> None:
    relogio = _Relogio()
    hub, criados = _hub(relogio)

    hub.segurar_o_dedo("aa")
    hub.reconciliar()
    assert criados["touchpad"].grabs == [True]
    assert "motion" not in criados

    relogio.agora += 4.0
    hub.segurar_o_dedo("aa")
    relogio.agora += 4.0
    hub.reconciliar()
    assert criados["touchpad"].grabs == [True], "renovado, segue segurado"

    relogio.agora += 5.5
    hub.reconciliar()
    assert criados["touchpad"].parado, "sem demanda, o leitor fecha e o fd solta o grab"


def test_o_prazo_vencido_solta_o_grab_com_o_leitor_vivo() -> None:
    relogio = _Relogio()
    hub, criados = _hub(relogio)
    hub.amostra_do_dsu("aa")
    hub.segurar_o_dedo("aa")
    hub.reconciliar()
    assert criados["touchpad"].grabs == [True]

    for _ in range(4):
        relogio.agora += 2.0
        hub.amostra_do_dsu("aa")
        hub.reconciliar()

    assert not criados["touchpad"].parado
    assert criados["touchpad"].grabs == [True, False]


def test_o_grab_do_movimento_e_o_do_toque_sao_independentes() -> None:
    relogio = _Relogio()
    hub, criados = _hub(relogio)
    hub._sensores_desligados = lambda mudou=False: {"aa"}  # type: ignore[method-assign]
    hub.amostra_do_dsu("aa")
    hub.segurar_o_dedo("aa")
    hub.reconciliar()
    assert criados["motion"].grabs == [True]
    assert criados["touchpad"].grabs == [True]

    hub._sensores_desligados = lambda mudou=False: set()  # type: ignore[method-assign]
    relogio.agora += 1.0
    hub.amostra_do_dsu("aa")
    hub.segurar_o_dedo("aa")
    hub.reconciliar()
    assert criados["motion"].grabs == [True, False], "o movimento solta sozinho"
    assert criados["touchpad"].grabs == [True], "e o toque segue segurado"

    hub._sensores_desligados = lambda mudou=False: {"aa"}  # type: ignore[method-assign]
    relogio.agora += 5.5
    hub.amostra_do_dsu("aa")
    hub.reconciliar()
    assert criados["motion"].grabs == [True, False, True]
    assert criados["touchpad"].grabs[-1] is False, "o prazo do toque venceu sem o pedido"


def test_o_stop_all_solta_tudo() -> None:
    hub, criados = _hub(_Relogio())
    hub.amostra_do_dsu("aa")
    hub.segurar_o_dedo("aa")
    hub.reconciliar()

    hub.stop_all()

    assert criados["motion"].parado and criados["touchpad"].parado
    assert hub._dedo_segurado == {}
