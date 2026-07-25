"""Os três sensores da aba Status (S2): giroscópio, touchpad e o hub que os serve.

Sem DualSense conectado não dá para exercitar nada ao vivo — então tudo aqui
é feito com dublês: eventos evdev sintéticos para os readers, e fábricas/
descobridores injetados para o `SensorHub`. O que estes testes travam:

  * a DECODIFICAÇÃO do giroscópio sai da `resolution` do node, não de
    constante — hardcodar 1024 daria número errado no dia em que o kernel
    mudasse a escala;
  * o leitor de touchpad da interface é OBSERVADOR: `touch_state()` não
    consome nada e o acúmulo de delta (o que move o cursor do mouse) fica
    desligado nele;
  * o hub liga reader sob demanda e o desliga sozinho quando ninguém pede,
    sem nunca varrer `/dev/input` no caminho quente;
  * os campos novos do IPC são OPCIONAIS — daemon sem sensor não quebra GUI
    nova, e GUI nova não desenha zero fingindo repouso.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_GYRO_RES_PER_DEG_S,
    MotionSensorReader,
    TouchpadReader,
    graus_por_segundo,
)
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub


class _Ecodes:
    """Só as constantes que os readers consultam (o módulo real é enorme)."""

    EV_ABS = 3
    EV_KEY = 1
    ABS_X = 0
    ABS_Y = 1
    ABS_RX = 3
    ABS_RY = 4
    ABS_RZ = 5
    BTN_LEFT = 272
    BTN_TOUCH = 330


def _evento(tipo: int, code: int, value: int) -> Any:
    return SimpleNamespace(type=tipo, code=code, value=value)


# ---------------------------------------------------------------------------
# Giroscópio: decodificação
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "resolucao", "esperado"),
    [
        (1024, 1024, 1.0),
        (-2048, 1024, -2.0),
        (512, 512, 1.0),  # escala diferente: o node manda, não a constante
        (0, 1024, 0.0),
    ],
)
def test_graus_por_segundo_usa_a_resolucao_do_node(
    valor: int, resolucao: int, esperado: float
) -> None:
    assert graus_por_segundo(valor, resolucao) == pytest.approx(esperado)


def test_graus_por_segundo_sem_resolucao_cai_no_default_do_kernel() -> None:
    """Resolução ausente/zero não pode virar valor cru na tela.

    Sem o fallback, um node que não publica `resolution` faria a interface
    exibir dezenas de milhares de "graus/s".
    """
    assert graus_por_segundo(DUALSENSE_GYRO_RES_PER_DEG_S, 0) == pytest.approx(1.0)
    assert graus_por_segundo(DUALSENSE_GYRO_RES_PER_DEG_S, -5) == pytest.approx(1.0)


def _reader_motion() -> MotionSensorReader:
    """Reader com path fixo (sem tocar em /dev/input) e escala já conhecida."""
    reader = MotionSensorReader(device_path=None)
    reader._resolucoes = {"x": 1024, "y": 1024, "z": 1024}
    return reader


def test_motion_reader_mapeia_abs_r_para_os_tres_eixos() -> None:
    reader = _reader_motion()
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_RX, 2048), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_RY, -1024), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_RZ, 512), _Ecodes)

    snap = reader.snapshot()
    assert (snap.x, snap.y, snap.z) == pytest.approx((2.0, -1.0, 0.5))


def test_motion_reader_ignora_o_acelerometro_do_mesmo_node() -> None:
    """ABS_X/Y/Z no node de motion são ACELERÔMETRO, não giroscópio.

    Os dois sensores dividem o mesmo `eventN`; ler os dois como um só faria
    as barras de giroscópio pularem com a gravidade, sem ninguém girar nada.
    """
    reader = _reader_motion()
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_X, 8192), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_Y, 8192), _Ecodes)

    snap = reader.snapshot()
    assert (snap.x, snap.y, snap.z) == (0.0, 0.0, 0.0)


def test_motion_reader_le_a_escala_do_absinfo_ao_abrir() -> None:
    reader = MotionSensorReader(device_path=None)
    dev = SimpleNamespace(
        absinfo=lambda code: SimpleNamespace(resolution={3: 1024, 4: 1024, 5: 512}[code])
    )

    reader._on_device_opened(dev)

    assert reader._resolucoes == {"x": 1024, "y": 1024, "z": 512}


def test_motion_reader_absinfo_indisponivel_nao_derruba_o_open() -> None:
    """Node atípico não pode matar a thread: sem escala, usa o default."""
    reader = MotionSensorReader(device_path=None)

    def explode(_code: int) -> Any:
        raise OSError("EINVAL")

    reader._on_device_opened(SimpleNamespace(absinfo=explode))

    assert reader._resolucoes == {}
    reader._handle_event(
        _evento(_Ecodes.EV_ABS, _Ecodes.ABS_RX, DUALSENSE_GYRO_RES_PER_DEG_S), _Ecodes
    )
    assert reader.snapshot().x == pytest.approx(1.0)


def test_motion_reader_zera_os_eixos_quando_o_controle_cai() -> None:
    """Gyro congelado no último valor seria movimento inventado."""
    reader = _reader_motion()
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_RX, 4096), _Ecodes)
    assert reader.snapshot().x != 0.0

    reader._reset_on_disconnect()

    assert reader.snapshot().x == 0.0


# ---------------------------------------------------------------------------
# Touchpad: estado observável sem roubar o movimento do cursor
# ---------------------------------------------------------------------------


def _tocar(reader: TouchpadReader, x: int, y: int, *, dedo: bool = True) -> None:
    reader._handle_event(
        _evento(_Ecodes.EV_KEY, _Ecodes.BTN_TOUCH, 1 if dedo else 0), _Ecodes
    )
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_X, x), _Ecodes)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_Y, y), _Ecodes)


def test_touch_state_reporta_dedo_e_posicao() -> None:
    reader = TouchpadReader(device_path=None, acumular_movimento=False)

    _tocar(reader, 1400, 300)

    estado = reader.touch_state()
    assert estado.touching is True
    assert (estado.x, estado.y) == (1400, 300)
    assert (estado.largura, estado.altura) == (1920, 1080)


def test_touch_state_solta_o_dedo_mas_guarda_a_ultima_posicao() -> None:
    """`touching=False` é o que decide não desenhar o ponto — não a posição."""
    reader = TouchpadReader(device_path=None, acumular_movimento=False)
    _tocar(reader, 800, 200)

    reader._handle_event(_evento(_Ecodes.EV_KEY, _Ecodes.BTN_TOUCH, 0), _Ecodes)

    estado = reader.touch_state()
    assert estado.touching is False
    assert (estado.x, estado.y) == (800, 200)


def test_touch_state_nao_consome_o_delta_do_cursor() -> None:
    """A leitura da interface é NÃO-destrutiva.

    Se `touch_state()` drenasse (como `consume_motion`), o poll loop do mouse
    receberia zero e o cursor pararia sempre que a aba Status estivesse
    aberta.
    """
    reader = TouchpadReader(device_path=None)  # acumulando, como o do cursor
    _tocar(reader, 500, 500)
    reader._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_X, 560), _Ecodes)

    reader.touch_state()
    reader.touch_state()

    assert reader.consume_motion() == (60, 0)


def test_observador_nao_acumula_delta_nenhum() -> None:
    """O leitor da aba Status abre o MESMO node do cursor.

    O kernel replica os eventos para os dois fds; com acúmulo ligado, o
    `_accum_dx/dy` deste reader cresceria a sessão inteira sem ninguém
    drenar — o salto de cursor que o poll loop já aprendeu a evitar.
    """
    observador = TouchpadReader(device_path=None, acumular_movimento=False)
    _tocar(observador, 500, 500)
    for x in range(510, 700, 10):
        observador._handle_event(_evento(_Ecodes.EV_ABS, _Ecodes.ABS_X, x), _Ecodes)

    assert observador.consume_motion() == (0, 0)
    assert observador.touch_state().x == 690  # mas a POSIÇÃO segue viva


def test_reset_do_touchpad_solta_o_dedo() -> None:
    reader = TouchpadReader(device_path=None, acumular_movimento=False)
    _tocar(reader, 100, 100)

    reader._reset_on_disconnect()

    assert reader.touch_state().touching is False


# ---------------------------------------------------------------------------
# SensorHub: demanda liga, silêncio desliga
# ---------------------------------------------------------------------------


class _ReaderFalso:
    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.iniciado = False
        self.parado = False

    def start(self) -> bool:
        self.iniciado = True
        return True

    def stop(self) -> None:
        self.parado = True

    def snapshot(self) -> Any:
        return SimpleNamespace(x=1.5, y=-2.5, z=0.25)

    def touch_state(self) -> Any:
        return SimpleNamespace(
            touching=True, x=960, y=540, largura=1920, altura=1080
        )


class _Relogio:
    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora


def _hub(nodes: dict[str, str] | None = None) -> tuple[SensorHub, dict[str, Any]]:
    """Hub com fábricas dubladas; `criados` guarda os readers por (uniq, tipo)."""
    mapa = {"aa": "/dev/input/event9"} if nodes is None else nodes
    criados: dict[str, Any] = {}

    def fabrica(tipo: str) -> Any:
        def _cria(uniq: str, node: Any) -> Any:
            # O node já descoberto chega pronto: o hub não deixa o reader
            # re-varrer /dev/input só para achar o que ele acabou de achar.
            assert node, "a fábrica tem de receber o node já resolvido"
            reader = _ReaderFalso(uniq)
            criados[f"{uniq}:{tipo}"] = reader
            return reader

        return _cria

    hub = SensorHub(
        motion_factory=fabrica("motion"),
        touch_factory=fabrica("touchpad"),
        descobrir_motion=lambda: dict(mapa),
        descobrir_touch=lambda: dict(mapa),
        relogio=_Relogio(),
        auto_manutencao=False,
    )
    return hub, criados


def test_hub_nao_abre_nada_antes_de_alguem_pedir() -> None:
    hub, criados = _hub()

    hub.reconciliar()

    assert criados == {}


def test_hub_abre_sob_demanda_e_entrega_os_dois_sensores() -> None:
    hub, criados = _hub()

    assert hub.leitura("aa") == {}  # 1ª volta: pediu, ainda não abriu
    hub.reconciliar()
    leitura = hub.leitura("aa")

    assert set(criados) == {"aa:motion", "aa:touchpad"}
    assert leitura["gyro"] == {"x": 1.5, "y": -2.5, "z": 0.25}
    assert leitura["touchpad"] == {
        "touching": True,
        "x": 960,
        "y": 540,
        "width": 1920,
        "height": 1080,
    }


def test_hub_desliga_o_reader_quando_a_demanda_expira() -> None:
    """Fechar a GUI apaga as threads sozinho — sem isso o daemon acumularia
    um reader por controle que já passou pela máquina."""
    hub, criados = _hub()
    relogio = hub._relogio
    hub.leitura("aa")
    hub.reconciliar()
    assert criados["aa:motion"].iniciado is True

    relogio.agora += SensorHub._DEMANDA_TTL_S + 1.0
    hub.reconciliar()

    assert criados["aa:motion"].parado is True
    assert criados["aa:touchpad"].parado is True
    assert hub.leitura("aa") == {}


def test_hub_nao_reprocura_node_inexistente_a_cada_volta() -> None:
    """Controle sem node não pode custar uma varredura de /dev/input por
    segundo (a lição PERF-MULTI-CONTROLLER-01)."""
    varreduras = {"n": 0}

    def descobrir() -> dict[str, Any]:
        varreduras["n"] += 1
        return {}

    hub = SensorHub(
        motion_factory=lambda u, _n: _ReaderFalso(u),
        touch_factory=lambda u, _n: _ReaderFalso(u),
        descobrir_motion=descobrir,
        descobrir_touch=lambda: {},
        relogio=_Relogio(),
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)  # /dev/input parado

    hub.leitura("zz")
    for _ in range(5):
        hub.reconciliar()

    assert varreduras["n"] == 1


def test_hub_reprocura_quando_dev_input_muda() -> None:
    """Replug tem de dar nova chance: a marca de "não achei" cai com o hotplug."""
    mapa: dict[str, str] = {}
    hub, criados = _hub(nodes=mapa)
    mudou = {"v": False}
    hub._watch = SimpleNamespace(poll=lambda: mudou["v"])

    hub.leitura("aa")
    hub.reconciliar()
    assert criados == {}

    mapa["aa"] = "/dev/input/event9"  # controle plugou
    mudou["v"] = True
    hub.leitura("aa")
    hub.reconciliar()

    assert set(criados) == {"aa:motion", "aa:touchpad"}


def test_hub_leitura_nunca_levanta_por_reader_defeituoso() -> None:
    """O `state_full` não pode cair por causa de um sensor."""

    class _Quebrado(_ReaderFalso):
        def snapshot(self) -> Any:
            raise RuntimeError("node sumiu")

    hub = SensorHub(
        motion_factory=lambda u, _n: _Quebrado(u),
        touch_factory=lambda u, _n: _ReaderFalso(u),
        descobrir_motion=lambda: {"aa": "/dev/input/event9"},
        descobrir_touch=lambda: {"aa": "/dev/input/event10"},
        relogio=_Relogio(),
        auto_manutencao=False,
    )
    hub.leitura("aa")
    hub.reconciliar()

    leitura = hub.leitura("aa")

    assert "gyro" not in leitura
    assert leitura["touchpad"]["touching"] is True


def test_hub_stop_all_derruba_tudo() -> None:
    hub, criados = _hub()
    hub.leitura("aa")
    hub.reconciliar()

    hub.stop_all()

    assert criados["aa:motion"].parado is True
    assert criados["aa:touchpad"].parado is True


# ---------------------------------------------------------------------------
# IPC: os campos novos são OPCIONAIS
# ---------------------------------------------------------------------------


class _HandlerFalso:
    """Só o suficiente para exercitar `_merge_sensores` fora do IpcServer."""

    def __init__(self, hub: Any) -> None:
        self._sensor_hub = hub

    _merge_sensores = None  # substituído abaixo pelo método real


def _handler_com_hub(hub: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    handler = _HandlerFalso(hub)
    handler._merge_sensores = IpcHandlersMixin._merge_sensores.__get__(handler)
    return handler


def test_merge_sensores_acrescenta_gyro_e_touchpad_ao_inputs() -> None:
    hub, _criados = _hub()
    hub.leitura("aa")
    hub.reconciliar()
    handler = _handler_com_hub(hub)
    entry = {"inputs": {"lx": 128, "buttons": []}}

    handler._merge_sensores(entry, "aa")

    assert entry["inputs"]["lx"] == 128  # nada do payload antigo se perde
    assert entry["inputs"]["gyro"]["x"] == 1.5
    assert entry["inputs"]["touchpad"]["touching"] is True


def test_merge_sensores_nao_inventa_inputs_para_controle_sem_leitor() -> None:
    """`inputs is None` já significa "sem leitor" — pendurar sensor ali seria
    a mesma mentira com outro nome."""
    hub, _criados = _hub()
    handler = _handler_com_hub(hub)
    entry: dict[str, Any] = {"inputs": None}

    handler._merge_sensores(entry, "aa")

    assert entry["inputs"] is None


def test_merge_sensores_ignora_controle_sem_mac() -> None:
    hub, criados = _hub()
    handler = _handler_com_hub(hub)
    entry = {"inputs": {"lx": 128}}

    handler._merge_sensores(entry, None)

    assert entry["inputs"] == {"lx": 128}
    assert criados == {}


def test_merge_sensores_sem_node_deixa_o_inputs_intacto() -> None:
    """Sem node de sensor, o payload sai IGUAL ao de antes do S2 — é o que
    permite daemon novo + GUI antiga e daemon antigo + GUI nova."""
    hub, _criados = _hub(nodes={})
    hub._watch = SimpleNamespace(poll=lambda: False)
    handler = _handler_com_hub(hub)
    entry = {"inputs": {"lx": 128, "buttons": []}}

    handler._merge_sensores(entry, "aa")
    hub.reconciliar()
    handler._merge_sensores(entry, "aa")

    assert entry["inputs"] == {"lx": 128, "buttons": []}
