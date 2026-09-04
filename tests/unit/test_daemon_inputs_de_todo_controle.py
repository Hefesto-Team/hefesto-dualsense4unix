"""STATUS-04 — `state_full` publica `inputs` de TODO controle, não só do primário.

A queixa dela, com dois DualSense na mesa: *"não funciona o touch, analogicos
... nem giroscopio e acelerometro"*. Parte era taxa de pintura. A outra parte
estava no daemon, e não era falta de dado: era DESENHO.

**O que o `_enrich_controllers_per_controller` fazia** — `inputs` só para o
PRIMÁRIO (do `daemon._last_state`) e para o secundário que o co-op tivesse
promovido (`live_snapshots()`). Todo o resto saía `None`, e o `_merge_sensores`
só pendura giro/acelerômetro/touchpad em quem JÁ tem `inputs` — então um
controle sem fonte de entrada perdia os sensores junto, mesmo com os nodes de
motion e touchpad abertos e legíveis ao lado.

**A razão estava escrita, e era medida** (sprint STATUS, 17/07/2026, item
STATUS-04, adiado de P1 para P2): *"co-op é DEFAULT ON, o checkbox saiu da UI
(…) no estado normal da máquina dela, TODO secundário já tem reader e o card
dele já terá inputs só com STATUS-01/02. O buraco real é o modo Nativo (…) e
emulação-off — cenários em que ela está jogando fullscreen, não olhando a
GUI."* A aposta continua verdadeira: medido em 04/09/2026 com os dois DualSense
dela em USB e co-op ligado, os DOIS controles já traziam `inputs` com giro,
acelerômetro e touchpad.

**O que caducou foi tratar o buraco como hipotético.** Nos modos em que o co-op
se desmonta — Nativo, emulação off, suspensão por Steam Input — metade da mesa
emudece, e são exatamente os modos em que ela está jogando.

O que estes testes travam:

  * com co-op DESLIGADO e dois controles, `controllers[1]["inputs"]` é dict
    (o critério de aceite literal do STATUS-04);
  * o reader passivo NUNCA faz `set_grab(True)` — com grab, o daemon vira
    leitor exclusivo e o JOGO deixa de ver o controle: o card acenderia à
    custa da partida dela;
  * o hub NÃO abre reader de gamepad para controle que o co-op já segura
    (inclusive o pendente de grab): o node está sob `EVIOCGRAB` e o fd
    passivo publicaria os `128` de fábrica como se fossem leitura;
  * o PRIMÁRIO nunca cai no reader passivo (armadilha A-09): o card e o topo
    do payload têm de dizer a mesma coisa sobre o mesmo controle;
  * os sensores viajam junto — é `inputs` virar dict que abre a porta do
    `_merge_sensores`.

Hermético: nada aqui toca `/dev/input`. Fábricas e descobridores do
`SensorHub` são injetados; MACs são fake (regra da casa).
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

# MACs fake — a regra da casa proíbe endereço real em arquivo versionado.
MAC1 = "aabbcc000001"
MAC2 = "aabbcc000002"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------


class _SnapFalso:
    """O que `EvdevReader.snapshot()` devolve, com os campos que importam."""

    def __init__(self, **kw: Any) -> None:
        self.lx = kw.get("lx", 128)
        self.ly = kw.get("ly", 128)
        self.rx = kw.get("rx", 128)
        self.ry = kw.get("ry", 128)
        self.l2_raw = kw.get("l2_raw", 0)
        self.r2_raw = kw.get("r2_raw", 0)
        self.buttons_pressed = frozenset(kw.get("buttons", ()))


class _ReaderDeGamepadFalso:
    """`EvdevReader` de mentira que ANOTA se alguém pediu grab.

    O `set_grab` existe aqui só para o teste poder provar que ele nunca é
    chamado — é a linha que separa STATUS-04 de um defeito.
    """

    def __init__(self, uniq: str, node: Any, **kw: Any) -> None:
        self.uniq = uniq
        self.node = node
        self.iniciado = False
        self.parado = False
        self.grabs: list[bool] = []
        self._snap = _SnapFalso(**kw)

    def start(self) -> bool:
        self.iniciado = True
        return True

    def stop(self) -> None:
        self.parado = True

    def set_grab(self, grab: bool) -> bool:  # pragma: no cover - nunca chamado
        self.grabs.append(grab)
        return True

    def snapshot(self) -> _SnapFalso:
        return self._snap


class _ReaderDeSensorFalso:
    """Motion/touchpad: só o que `SensorHub.leitura` consulta."""

    def __init__(self, uniq: str, node: Any) -> None:
        self.uniq = uniq
        self.node = node
        self.parado = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def snapshot(self) -> Any:
        return SimpleNamespace(x=1.5, y=-2.0, z=0.25)

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=0.0, y=0.0, z=1.0)

    def touch_state(self) -> Any:
        return SimpleNamespace(touching=True, x=100, y=200, largura=1920, altura=1080)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _hub(
    *,
    gamepads: dict[str, str] | None = None,
    sensores: dict[str, str] | None = None,
    **snap_kw: Any,
) -> tuple[SensorHub, dict[str, Any]]:
    """Hub com tudo injetado; `criados` guarda cada reader por `uniq:tipo`."""
    criados: dict[str, Any] = {}
    nodes_gp = {MAC2: "/dev/input/event9"} if gamepads is None else gamepads
    nodes_sensor = {MAC1: "/dev/input/event7", MAC2: "/dev/input/event8"}
    if sensores is not None:
        nodes_sensor = sensores

    def fabrica_gamepad(uniq: str, node: Any) -> Any:
        criados[f"{uniq}:gamepad"] = _ReaderDeGamepadFalso(uniq, node, **snap_kw)
        return criados[f"{uniq}:gamepad"]

    def fabrica_sensor(tipo: str) -> Callable[[str, Any], Any]:
        def cria(uniq: str, node: Any) -> Any:
            criados[f"{uniq}:{tipo}"] = _ReaderDeSensorFalso(uniq, node)
            return criados[f"{uniq}:{tipo}"]

        return cria

    hub = SensorHub(
        motion_factory=fabrica_sensor("motion"),
        touch_factory=fabrica_sensor("touchpad"),
        gamepad_factory=fabrica_gamepad,
        descobrir_motion=lambda: dict(nodes_sensor),
        descobrir_touch=lambda: dict(nodes_sensor),
        descobrir_gamepad=lambda: dict(nodes_gp),
        relogio=_Relogio(),
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub, criados


def _make_state(**kw: Any) -> ControllerState:
    base: dict[str, Any] = {
        "battery_pct": 80,
        "l2_raw": 0,
        "r2_raw": 0,
        "connected": True,
        "transport": "usb",
        "raw_lx": 128,
        "raw_ly": 128,
        "raw_rx": 128,
        "raw_ry": 128,
        "buttons_pressed": frozenset(),
    }
    base.update(kw)
    return ControllerState(**base)


# ---------------------------------------------------------------------------
# Servidor IPC real (o padrão de contrato da casa)
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    fc.describe_controllers = lambda: [
        {"index": 0, "connected": True, "transport": "usb",
         "is_primary": True, "uniq": MAC1},
        {"index": 1, "connected": True, "transport": "bt",
         "is_primary": False, "uniq": MAC2},
    ]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
    )
    # Co-op DESMONTADO: é o estado do modo Nativo e da emulação off — os
    # cenários que o STATUS-04 nomeou como "o buraco real".
    daemon_mock._coop_manager = SimpleNamespace(
        live_snapshots=lambda: {}, _players={}, player_count=lambda: 1
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield server, socket_path, fc, daemon_mock
    finally:
        await server.stop()


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    assert isinstance(result, dict)
    return result


def _armar(server: Any, hub: SensorHub, *, gamepads: tuple[str, ...] = (MAC2,)) -> None:
    """Pendura o hub no handler e deixa os readers JÁ ABERTOS.

    Abrir antes não é conveniência, é o que faz as réguas morderem: no daemon
    vivo o reader nasce na thread de manutenção, e um teste que não o abrisse
    veria `None` pelo motivo errado — "o reader ainda não nasceu" em vez de "o
    handler recusou". Foi assim que a mordida da recusa do primário passou
    verde na primeira redação deste arquivo.
    """
    server._sensor_hub = hub
    for uniq in gamepads:
        hub.entradas(uniq)
    hub.leitura(MAC2)
    hub.leitura(MAC1)
    hub.reconciliar()


# ---------------------------------------------------------------------------
# A entrega: o critério de aceite literal do STATUS-04
# ---------------------------------------------------------------------------


class TestOSegundoControleFala:
    @pytest.mark.asyncio
    async def test_coop_desmontado_o_secundario_traz_inputs(
        self, running_server: Any
    ) -> None:
        """O critério de aceite escrito em 17/07/2026, cobrado em 04/09/2026.

        *"com co-op DESLIGADO e 2 controles fake: `controllers[1].inputs !=
        None` e NENHUM `set_grab(True)` foi chamado no reader do secundário"*.
        """
        server, socket_path, _fc, _daemon = running_server
        hub, criados = _hub(lx=10, ly=20, rx=30, ry=40, l2_raw=50, r2_raw=60,
                            buttons=("square", "l1"))
        _armar(server, hub)

        result = await _state_full(socket_path)

        c2 = result["controllers"][1]
        assert c2["inputs"] is not None, "metade da mesa continua muda"
        assert c2["inputs"]["lx"] == 10
        assert c2["inputs"]["ly"] == 20
        assert c2["inputs"]["rx"] == 30
        assert c2["inputs"]["ry"] == 40
        assert c2["inputs"]["l2_raw"] == 50
        assert c2["inputs"]["r2_raw"] == 60
        assert c2["inputs"]["buttons"] == ["l1", "square"]
        # A outra metade do critério: nenhum grab, nunca.
        assert criados[f"{MAC2}:gamepad"].grabs == []

    @pytest.mark.asyncio
    async def test_os_sensores_viajam_junto_com_o_inputs(
        self, running_server: Any
    ) -> None:
        """É `inputs` virar dict que abre a porta do `_merge_sensores`.

        Sem esta cadeia o card do P2 mostrava "—" em giroscópio, acelerômetro
        e touchpad com os nodes abertos e legíveis ao lado — a queixa dela,
        inteira, numa linha de código.
        """
        server, socket_path, _fc, _daemon = running_server
        hub, _criados = _hub()
        _armar(server, hub)

        result = await _state_full(socket_path)

        inputs = result["controllers"][1]["inputs"]
        assert inputs["gyro"] == {"x": 1.5, "y": -2.0, "z": 0.25}
        assert inputs["accel"] == {"x": 0.0, "y": 0.0, "z": 1.0}
        assert inputs["touchpad"]["touching"] is True


# ---------------------------------------------------------------------------
# As três recusas — cada uma evita uma mentira diferente
# ---------------------------------------------------------------------------


class TestAsRecusas:
    @pytest.mark.asyncio
    async def test_o_primario_nunca_cai_no_reader_passivo(
        self, running_server: Any
    ) -> None:
        """Armadilha A-09: dois números para o mesmo controle no mesmo tique.

        Com `daemon._last_state` None o primário fica em `None` — que é o que
        o TOPO do payload também mostra. Cair no reader passivo aqui faria o
        card contradizer o resto da tela.

        O reader do primário está ABERTO e respondendo (`lx=7`): a régua mede
        a recusa do handler, não a ausência do dado.
        """
        server, socket_path, _fc, daemon = running_server
        daemon._last_state = None
        hub, _criados = _hub(
            gamepads={MAC1: "/dev/input/event9", MAC2: "/dev/input/event10"},
            lx=7,
        )
        _armar(server, hub, gamepads=(MAC1, MAC2))
        aberto = hub.entradas(MAC1)
        assert aberto is not None and aberto["lx"] == 7, "o dado ESTÁ lá"

        result = await _state_full(socket_path)

        assert result["controllers"][0]["inputs"] is None
        # E o secundário, que TEM direito à fonte 3, continua falando — a
        # recusa é do primário, não do caminho.
        assert result["controllers"][1]["inputs"]["lx"] == 7

    @pytest.mark.asyncio
    async def test_o_primario_com_state_continua_espelhando_o_topo(
        self, running_server: Any
    ) -> None:
        """A fonte 1 não perdeu a precedência para a fonte 3.

        O reader passivo do primário está aberto e diz `lx=7`; o `state` diz
        200. Quem tem de sair no payload é o 200, nos dois lugares.
        """
        server, socket_path, _fc, daemon = running_server
        daemon._last_state = _make_state(raw_lx=200, buttons_pressed=frozenset({"ps"}))
        hub, _criados = _hub(gamepads={MAC1: "/dev/input/event9"}, lx=7)
        _armar(server, hub, gamepads=(MAC1,))

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["inputs"]["lx"] == 200 == result["lx"]
        assert c1["inputs"]["buttons"] == ["ps"] == result["buttons"]

    @pytest.mark.asyncio
    async def test_controle_que_o_coop_segura_nao_ganha_reader_passivo(
        self, running_server: Any
    ) -> None:
        """O jogador PENDENTE de grab: o node está sob `EVIOCGRAB` alheio.

        `live_snapshots()` o exclui de propósito (sem vpad, o jogo também não
        o vê), mas o reader do co-op JÁ está com o node. Um fd passivo ali não
        receberia evento nenhum e publicaria os `128` de fábrica como se
        fossem leitura — o "zero fingindo repouso" que esta casa proíbe.
        """
        server, socket_path, _fc, daemon = running_server
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {},                     # sem vpad ainda
            _players={MAC2: SimpleNamespace(vpad=None)},   # mas com o node
            player_count=lambda: 2,
        )
        hub, criados = _hub(lx=7)
        _armar(server, hub)
        aberto = hub.entradas(MAC2)
        assert aberto is not None and aberto["lx"] == 7, "o reader responde"

        result = await _state_full(socket_path)

        # O reader existe e responde — e mesmo assim o payload diz "—".
        # É a recusa do handler, não a ausência de reader.
        assert result["controllers"][1]["inputs"] is None
        assert criados[f"{MAC2}:gamepad"].grabs == []

    @pytest.mark.asyncio
    async def test_coop_promovido_continua_mandando_no_secundario(
        self, running_server: Any
    ) -> None:
        """A fonte 2 tem precedência sobre a 3 — o reader do jogo é o dono."""
        server, socket_path, _fc, daemon = running_server
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {
                MAC2: _SnapFalso(lx=99, buttons=("cross",))
            },
            _players={MAC2: SimpleNamespace(vpad=object())},
            player_count=lambda: 2,
        )
        hub, _criados = _hub(lx=7)
        _armar(server, hub)

        result = await _state_full(socket_path)

        assert result["controllers"][1]["inputs"]["lx"] == 99
        assert result["controllers"][1]["inputs"]["buttons"] == ["cross"]

    @pytest.mark.asyncio
    async def test_controle_desconectado_nao_abre_node(
        self, running_server: Any
    ) -> None:
        server, socket_path, fc, _daemon = running_server
        fc.describe_controllers = lambda: [
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "uniq": MAC1},
            {"index": 1, "connected": False, "transport": "bt",
             "is_primary": False, "uniq": MAC2},
        ]
        hub, _criados = _hub()
        server._sensor_hub = hub

        result = await _state_full(socket_path)

        assert result["controllers"][1]["inputs"] is None


# ---------------------------------------------------------------------------
# O hub por dentro
# ---------------------------------------------------------------------------


class TestOHubPorDentro:
    def test_entradas_devolve_none_antes_do_reader_nascer(self) -> None:
        """A descoberta é cara e o event loop é único: nada abre no caminho."""
        hub, criados = _hub()

        assert hub.entradas(MAC2) is None
        assert criados == {}

    def test_entradas_devolve_o_snapshot_depois_de_reconciliar(self) -> None:
        hub, _criados = _hub(lx=11, buttons=("triangle",))
        hub.entradas(MAC2)
        hub.reconciliar()

        assert hub.entradas(MAC2) == {
            "lx": 11, "ly": 128, "rx": 128, "ry": 128,
            "l2_raw": 0, "r2_raw": 0, "buttons": ["triangle"],
        }

    def test_pedir_sensor_nao_abre_reader_de_gamepad(self) -> None:
        """Os dois registros de demanda são separados DE PROPÓSITO.

        O `state_full` pede sensor de todo controle que já tem `inputs`; se a
        demanda fosse uma só, cada um deles ganharia um reader de gamepad
        inútil — thread e fd por controle, para nada.
        """
        hub, criados = _hub()
        hub.leitura(MAC2)
        hub.reconciliar()

        assert f"{MAC2}:motion" in criados
        assert f"{MAC2}:gamepad" not in criados

    def test_o_reader_de_gamepad_morre_sozinho_quando_ninguem_pede(self) -> None:
        """Fechar a GUI apaga a thread e o fd — sem isso, um daemon de dias
        acumularia um reader por controle que já passou pela máquina."""
        hub, criados = _hub()
        hub.entradas(MAC2)
        hub.reconciliar()
        assert criados[f"{MAC2}:gamepad"].iniciado is True

        hub._relogio.agora += SensorHub._DEMANDA_TTL_S + 1.0
        hub.reconciliar()

        assert criados[f"{MAC2}:gamepad"].parado is True
        assert hub.entradas(MAC2) is None

    def test_entradas_nunca_levanta_por_reader_defeituoso(self) -> None:
        """O `state_full` não pode cair por causa de um node que sumiu."""

        class _Quebrado(_ReaderDeGamepadFalso):
            def snapshot(self) -> Any:
                raise RuntimeError("node sumiu")

        criados: dict[str, Any] = {}

        def fabrica(uniq: str, node: Any) -> Any:
            criados[uniq] = _Quebrado(uniq, node)
            return criados[uniq]

        hub = SensorHub(
            motion_factory=lambda u, n: _ReaderDeSensorFalso(u, n),
            touch_factory=lambda u, n: _ReaderDeSensorFalso(u, n),
            gamepad_factory=fabrica,
            descobrir_motion=lambda: {},
            descobrir_touch=lambda: {},
            descobrir_gamepad=lambda: {MAC2: "/dev/input/event9"},
            relogio=_Relogio(),
            auto_manutencao=False,
        )
        hub._watch = SimpleNamespace(poll=lambda: False)
        hub.entradas(MAC2)
        hub.reconciliar()

        assert hub.entradas(MAC2) is None

    def test_so_o_tipo_que_falta_paga_a_descoberta(self) -> None:
        """Cada descobridor abre todos os nodes de `/dev/input` (~10-40 ms —
        PERF-MULTI-CONTROLLER-01). Pedir só sensor não pode custar a varredura
        do gamepad."""
        varreduras = {"motion": 0, "touchpad": 0, "gamepad": 0}

        def conta(tipo: str, mapa: dict[str, str]) -> Callable[[], dict[str, Any]]:
            def descobrir() -> dict[str, Any]:
                varreduras[tipo] += 1
                return dict(mapa)

            return descobrir

        hub = SensorHub(
            motion_factory=lambda u, n: _ReaderDeSensorFalso(u, n),
            touch_factory=lambda u, n: _ReaderDeSensorFalso(u, n),
            gamepad_factory=lambda u, n: _ReaderDeGamepadFalso(u, n),
            descobrir_motion=conta("motion", {MAC2: "/dev/input/event7"}),
            descobrir_touch=conta("touchpad", {MAC2: "/dev/input/event8"}),
            descobrir_gamepad=conta("gamepad", {MAC2: "/dev/input/event9"}),
            relogio=_Relogio(),
            auto_manutencao=False,
        )
        hub._watch = SimpleNamespace(poll=lambda: False)

        hub.leitura(MAC2)
        hub.reconciliar()

        assert varreduras["motion"] == 1
        assert varreduras["touchpad"] == 1
        assert varreduras["gamepad"] == 0

    def test_a_fabrica_real_entrega_um_reader_sem_grab(self) -> None:
        """A régua sobre o código de PRODUÇÃO, não sobre o dublê.

        Os testes acima provam que o handler não pede grab; este prova que a
        fábrica também não o embute. `EvdevReader` nasce com `_grab=False` e
        só graba por `set_grab` — a ausência da chamada em
        `_gamepad_reader_real` é a entrega, e uma régua tem de morder se
        alguém a acrescentar "para o reader funcionar melhor".

        Hermético: com `device_path` explícito o construtor não chama o
        finder, então nada aqui varre `/dev/input`.
        """
        reader = SensorHub._gamepad_reader_real(MAC2, Path("/dev/input/event999"))
        try:
            assert reader.grab_state == "off"
            assert reader._grab is False
            assert reader._target_uniq == MAC2
        finally:
            reader.stop()

    def test_stop_all_derruba_o_reader_de_gamepad_tambem(self) -> None:
        hub, criados = _hub()
        hub.entradas(MAC2)
        hub.leitura(MAC2)
        hub.reconciliar()

        hub.stop_all()

        assert criados[f"{MAC2}:gamepad"].parado is True
        assert criados[f"{MAC2}:motion"].parado is True
