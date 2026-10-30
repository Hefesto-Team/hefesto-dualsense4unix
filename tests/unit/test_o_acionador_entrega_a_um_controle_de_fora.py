"""O Pro Controller e o 8BitDo ganham pad virtual, e o acionador chega a ele.

D-3010-OS-EXTERNOS-GANHAM-CONTROLE-VIRTUAL (30/10/2026, «Sim, ganham virtual»): o controle de
fora entra no co-op como o DualSense, com o pad virtual e a mesma cadeia do ``forward_all``
(os acionadores, o perfil, a troca de botão). O leitor já lê pelo mapa posicional do
``hid-nintendo``: o «A» da Nintendo é o ``BTN_EAST`` e chega como ``circle``.

Um controle ativo por vez: o pad virtual só nasce depois de o broker esconder o hidraw do
controle de fora; com o esconderijo recusado, ele segue nativo, como hoje.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.

AS MORDIDAS (30/10/2026): sem o ``want.update(externos)`` do ``sync``, o Pro não nasce; sem o
ralo do externo, o rumble do jogo vai ao backend do DualSense e não ao nó do Pro.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    BOTOES_DO_LEITOR,
    ESPECIE_EXTERNAL,
    GamepadDescoberto,
)
from hefesto_dualsense4unix.core.motor_do_no import MotorDoNo
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask  # noqa: F401
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

DECISAO = "D-3010-OS-EXTERNOS-GANHAM-CONTROLE-VIRTUAL"

P1 = "aabbcc000001"
P2 = "aabbcc000002"
PRO = "aabbcc000003"
OITO = "aabbcc000004"

NO_DO_PRO = "/dev/input/event31"
HIDRAW_DO_PRO = "/dev/hidraw9"


class _DevComFF:
    def __init__(self) -> None:
        self.enviados: list[Any] = []
        self.escritos: list[tuple[int, int, int]] = []

    def upload_effect(self, efeito: Any) -> int:
        self.enviados.append(efeito)
        return 7

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritos.append((tipo, codigo, valor))


class _Leitor:
    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"
        self._active_dev = _DevComFF()
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0, buttons_pressed=frozenset()
        )

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        return self.snap


class _Vpad:
    def __init__(self, identidade: str, rumble_sink: Any = None) -> None:
        self.identidade = identidade
        self.flavor = "dualsense"
        self.rumble_sink = rumble_sink
        self.botoes: list[frozenset[str]] = []

    def stop(self) -> None:
        return None

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.botoes.append(frozenset(pressed))

    def pump_ff(self) -> None:
        return None


class _Broker:
    def __init__(self, aceita: bool = True) -> None:
        self.aceita = aceita
        self.escondidos = []
        self.devolvidos: list[str] = []

    def hide(self, node: str) -> bool:
        self.escondidos.append(node)
        return self.aceita

    def restore(self, node: str) -> bool:
        self.devolvidos.append(node)
        return True


class _Ponte(gamepad_mod.PonteDosAcionadores):
    def __init__(self, por_controle: dict[str, frozenset[str]]) -> None:
        self.por_controle = por_controle

    def andar(self, *_a: Any) -> None:
        return None

    def apertados(self, controle: object) -> frozenset[str]:
        return self.por_controle.get(str(controle), frozenset())


def _descoberto(identidade: str, vid: str, pid: str, nome: str, no: str, hidraw: str | None):
    return GamepadDescoberto(
        especie=ESPECIE_EXTERNAL,
        identidade=identidade,
        evdev_path=no,
        name=nome,
        vid=vid,
        pid=pid,
        bus="usb",
        uniq=":".join(identidade[i : i + 2] for i in range(0, 12, 2)),
        driver="nintendo",
        hidraw=hidraw,
    )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    nascimentos: list[str] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {P1: "/dev/input/event20", P2: "/dev/input/event22"},
    )
    monkeypatch.setattr(
        coop_mod, "externos_que_ganham_virtual", lambda: {PRO: (NO_DO_PRO, HIDRAW_DO_PRO)}
    )

    def _nasce(_flavor: Any, *, identity: str | None = None, **kw: Any) -> _Vpad:
        nascimentos.append(str(identity))
        return _Vpad(str(identity), kw.get("rumble_sink"))

    monkeypatch.setattr("hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _nasce)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda daemon: None
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    return nascimentos


def _daemon(broker: _Broker) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=SimpleNamespace(
            primary_uniq=P1, _evdev=SimpleNamespace(_device_path="/dev/input/event20")
        ),
        identity_registry=None,
        _coop_manager=None,
        _hidraw_broker_client=broker,
    )


def _mesa_de_pe(broker: _Broker) -> CoopManager:
    mgr = CoopManager(_daemon(broker))
    mgr.sync()
    mgr.sync(force=True)
    return mgr


def test_o_pro_ganha_pad_virtual_depois_do_esconderijo(mesa: list[str]) -> None:
    """D-3010-OS-EXTERNOS-GANHAM-CONTROLE-VIRTUAL: o Pro senta à mesa como o DualSense."""
    broker = _Broker()
    mgr = _mesa_de_pe(broker)

    assert HIDRAW_DO_PRO in broker.escondidos
    assert PRO in mesa, f"{DECISAO}: o Pro escondido ganha o pad virtual"
    pro = mgr._players[PRO]
    assert pro.externo and pro.evdev_path == NO_DO_PRO
    assert pro.reader.grab_state == "held"
    assert P2 in mesa and not mgr._players[P2].externo


def test_com_o_esconderijo_recusado_o_pro_segue_nativo(mesa: list[str]) -> None:
    """Um controle ativo por vez: sem o hidraw escondido, o jogo veria dois."""
    broker = _Broker(aceita=False)
    mgr = _mesa_de_pe(broker)

    assert HIDRAW_DO_PRO in broker.escondidos
    assert PRO not in mesa
    assert PRO not in mgr._players
    assert P2 in mesa


def test_o_pro_que_sai_devolve_o_hidraw(mesa: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    broker = _Broker()
    mgr = _mesa_de_pe(broker)
    assert PRO in mgr._players

    monkeypatch.setattr(coop_mod, "externos_que_ganham_virtual", dict)
    mgr.sync(force=True)

    assert PRO not in mgr._players
    assert HIDRAW_DO_PRO in broker.devolvidos
    assert mgr._esconderijo == {}


def test_a_tecla_do_acionador_chega_ao_pad_do_pro_e_so_a_ele(mesa: list[str]) -> None:
    """O acionador declarado para o Pro entra no pad do Pro, não no do DualSense ao lado."""
    broker = _Broker()
    mgr = _mesa_de_pe(broker)
    setattr(mgr._daemon, gamepad_mod._ATRIBUTO_DA_PONTE, _Ponte({PRO: frozenset({"circle"})}))
    mgr._players[PRO].reader.snap.buttons_pressed = frozenset({"cross"})

    mgr.forward_all()

    assert mgr._players[PRO].vpad.botoes[-1] >= {"circle", "cross"}
    assert "circle" not in mgr._players[P2].vpad.botoes[-1]


def test_o_a_da_nintendo_e_o_circulo() -> None:
    """O mapa posicional: o ``hid-nintendo`` manda o «A» (o de leste) como ``BTN_EAST``."""
    assert BOTOES_DO_LEITOR["BTN_EAST"] == "circle"
    assert BOTOES_DO_LEITOR["BTN_SOUTH"] == "cross"


def test_o_rumble_do_jogo_vai_ao_no_do_pro(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _Broker()
    mgr = _mesa_de_pe(broker)
    monkeypatch.setattr(gamepad_mod, "_mults_por_motor", lambda *_a: (1.0, 0.5))
    ao_backend: list[Any] = []
    monkeypatch.setattr(
        gamepad_mod, "apply_game_rumble", lambda *a, **kw: ao_backend.append((a, kw))
    )

    mgr._players[PRO].vpad.rumble_sink(100, 200)

    rumble = mgr._players[PRO].reader._active_dev.enviados[-1].u.ff_rumble_effect
    assert (rumble.weak_magnitude, rumble.strong_magnitude) == (100 * 257, 100 * 257)
    assert ao_backend == []


def test_so_o_pro_e_o_8bitdo_ganham_virtual() -> None:
    vistos = [
        _descoberto(PRO, "057e", "2009", "Pro Controller", NO_DO_PRO, HIDRAW_DO_PRO),
        _descoberto(OITO, "2dc8", "6001", "8BitDo SN30 Pro", "/dev/input/event32", "/dev/hidraw10"),
        _descoberto("aabbcc000005", "045e", "02ea", "Xbox", "/dev/input/event33", None),
        _descoberto("aabbcc000006", "057e", "2006", "Joy-Con (L)", "/dev/input/event34", None),
        _descoberto("dev:0005:057E:2009.0001", "057e", "2009", "Pro", "/dev/input/event35", None),
    ]

    assert coop_mod.os_que_ganham_virtual(vistos) == {
        PRO: (NO_DO_PRO, HIDRAW_DO_PRO),
        OITO: ("/dev/input/event32", "/dev/hidraw10"),
    }


def test_o_motor_vibra_o_no_que_o_leitor_tem_aberto() -> None:
    from evdev import ecodes

    leitor = SimpleNamespace(_active_dev=_DevComFF())
    motor = MotorDoNo(leitor)

    assert motor.vibrar(255, 128)
    rumble = leitor._active_dev.enviados[0].u.ff_rumble_effect
    assert (rumble.strong_magnitude, rumble.weak_magnitude) == (128 * 257, 255 * 257)
    assert leitor._active_dev.escritos == [(ecodes.EV_FF, 7, 1)]

    assert motor.vibrar(0, 0)
    assert leitor._active_dev.escritos[-1] == (ecodes.EV_FF, 7, 0)

    leitor._active_dev = None
    assert not motor.vibrar(10, 10)
