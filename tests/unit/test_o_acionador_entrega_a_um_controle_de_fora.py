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
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import config_isolado  # noqa: F401

DECISAO = "D-3010-OS-EXTERNOS-GANHAM-CONTROLE-VIRTUAL"

P1 = "aabbcc000001"
P2 = "aabbcc000002"
PRO = "aabbcc000003"
OITO = "aabbcc000004"

NO_DO_PRO = "/dev/input/event31"
HIDRAW_DO_PRO = "/dev/hidraw9"
PAR_DO_PRO = (0x057E, 0x2009)


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
        coop_mod,
        "externos_que_ganham_virtual",
        lambda: {PRO: (NO_DO_PRO, HIDRAW_DO_PRO, PAR_DO_PRO)},
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
        PRO: (NO_DO_PRO, HIDRAW_DO_PRO, None),
        OITO: ("/dev/input/event32", "/dev/hidraw10", (0x2DC8, 0x6001)),
    }


def test_o_par_que_um_nativo_divide_nao_se_esconde() -> None:
    """O clone de endereço sintético segue nativo: esconder o 057e:2009 sumiria com ele."""
    sozinho = [_descoberto(PRO, "057e", "2009", "Pro Controller", NO_DO_PRO, HIDRAW_DO_PRO)]
    assert coop_mod.os_que_ganham_virtual(sozinho)[PRO][2] == PAR_DO_PRO

    com_o_clone = [
        *sozinho,
        _descoberto("dev:0005:057E:2009.0001", "057e", "2009", "Pro", "/dev/input/event35", None),
    ]
    assert coop_mod.os_que_ganham_virtual(com_o_clone)[PRO][2] is None


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


def _ignore(env: dict[str, str]) -> set[str]:
    return set(filter(None, env.get("SDL_GAMECONTROLLER_IGNORE_DEVICES", "").split(",")))


def _env(mascara: str, externos: Any, *, native: bool = False, fisicos: int = 2) -> dict[str, str]:
    from hefesto_dualsense4unix.daemon import launch_env as le

    modo = le.ModoAntecipado(
        native=native, emulacao=True, mascara=mascara,
        backends=("uhid",) * fisicos, motivo="teste", fisicos=fisicos,
    )
    return le.env_do_modo(modo, externos=externos)


def test_o_pro_sentado_sai_da_vista_do_jogo_pelo_ignore(mesa: list[str]) -> None:
    """O broker esconde o hidraw; o nó evdev agarrado sairia no SDL como um Pro morto."""
    mgr = _mesa_de_pe(_Broker())
    assert mgr.pares_de_fora_escondidos() == (PAR_DO_PRO,)

    env = _env("dualsense", mgr.pares_de_fora_escondidos(), fisicos=3)
    assert "0x057e/0x2009" in _ignore(env)
    assert "0x054c/0x0ce6" in _ignore(env)
    assert "0x057E" not in env.get("PROTON_DISABLE_HIDRAW", "")


def test_o_par_que_a_mascara_veste_fica_de_fora_do_ignore() -> None:
    """Na máscara Nintendo o pad virtual veste o par do Pro: escondê-lo sumiria com o pad."""
    oito = (0x2DC8, 0x6001)
    nintendo = _env("nintendo", (PAR_DO_PRO, oito))
    assert "0x057e/0x2009" not in _ignore(nintendo)
    assert "0x2dc8/0x6001" in _ignore(nintendo)

    xbox = _env("xbox", (PAR_DO_PRO, (0x045E, 0x028E)))
    assert "0x057e/0x2009" in _ignore(xbox)
    assert "0x045e/0x028e" not in _ignore(xbox)

    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in _env(
        "dualsense", (PAR_DO_PRO,), native=True, fisicos=1
    )
    assert _env("dualsense", ()) == _env("dualsense", ())


def test_o_par_da_mascara_e_o_que_o_pad_veste() -> None:
    from hefesto_dualsense4unix.daemon.launch_env import PAR_DA_MASCARA
    from hefesto_dualsense4unix.integrations import uinput_gamepad as ug

    assert PAR_DA_MASCARA == {
        "xbox": (ug.XBOX360_VENDOR, ug.XBOX360_PRODUCT),
        "nintendo": (ug.NINTENDO_VENDOR, ug.NINTENDO_PROCON_PRODUCT),
    }


def test_o_pro_sem_pad_ou_com_pad_que_veste_o_par_nao_se_esconde(mesa: list[str]) -> None:
    mgr = _mesa_de_pe(_Broker())
    vpad = mgr._players[PRO].vpad

    mgr._players[PRO].vpad = None
    assert mgr.pares_de_fora_escondidos() == ()

    mgr._players[PRO].vpad = vpad
    vpad.flavor = "nintendo"
    assert mgr.pares_de_fora_escondidos() == ()

    vpad.flavor = "dualsense"
    assert mgr.pares_de_fora_escondidos() == (PAR_DO_PRO,)


def test_o_pro_conta_como_fisico_e_o_par_vai_na_assinatura(mesa: list[str]) -> None:
    """O pad do Pro não cobre um DualSense: o Pro conta na mesa, e a troca dele rematerializa."""
    from hefesto_dualsense4unix.daemon import launch_env as le

    mgr = _mesa_de_pe(_Broker())
    daemon = mgr._daemon
    daemon._coop_manager = mgr
    daemon.controller.describe_controllers = lambda: [
        {"connected": True}, {"connected": True}
    ]

    assert le._snapshot(daemon)[4] == 3
    assert le._pares_de_fora(daemon) == (PAR_DO_PRO,)
    assert le._assinatura_da_mesa(daemon)[7] == (PAR_DO_PRO,)

    daemon.controller.describe_controllers = lambda: []
    assert le._snapshot(daemon)[4] == 0


class _PadDoP1(_Vpad):
    def __init__(self) -> None:
        super().__init__("p1")
        self.paradas = 0
        self.analogicos: list[dict[str, int]] = []

    def stop(self) -> None:
        self.paradas += 1

    def forward_analog(self, **kw: int) -> None:
        self.analogicos.append(kw)


def _mesa_so_de_fora(
    monkeypatch: pytest.MonkeyPatch, broker: _Broker
) -> tuple[CoopManager, _PadDoP1, dict[str, str]]:
    dualsenses: dict[str, str] = {}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(dualsenses),
    )
    pad = _PadDoP1()
    daemon = _daemon(broker)
    daemon._gamepad_device = pad
    daemon.controller.primary_uniq = None
    daemon.controller.is_connected = lambda: bool(dualsenses)
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    mgr.sync()
    mgr.sync(force=True)
    return mgr, pad, dualsenses


def test_sozinho_o_pro_dirige_o_pad_do_p1(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem DualSense na mesa, o Pro é o jogador 1 do jogo, no pad que o jogo já vê."""
    mgr, pad, _ = _mesa_so_de_fora(monkeypatch, _Broker())

    pro = mgr._players[PRO]
    assert pro.no_p1 and pro.vpad is pad
    assert PRO not in mesa, "o Pro sozinho não cria um segundo pad ao lado do P1"
    assert mgr.numeros_de_jogador()[PRO] == 1
    from hefesto_dualsense4unix.daemon import launch_env as le

    assert len(le._snapshot(mgr._daemon)[3]) == 1, "o pad do P1 conta uma vez só"

    pro.reader.snap.buttons_pressed = frozenset({"circle"})
    mgr.forward_all()
    assert "circle" in pad.botoes[-1]


def test_o_rumble_do_p1_vai_ao_pro_que_o_dirige(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr, _pad, _ = _mesa_so_de_fora(monkeypatch, _Broker())
    monkeypatch.setattr(gamepad_mod, "_mults_por_motor", lambda *_a: (1.0, 1.0))
    ao_backend: list[Any] = []
    monkeypatch.setattr(
        gamepad_mod, "apply_game_rumble", lambda *a, **kw: ao_backend.append((a, kw))
    )

    gamepad_mod.make_primary_rumble_sink(mgr._daemon)(100, 200)

    enviados = mgr._players[PRO].reader._active_dev.enviados
    assert enviados, "o rumble do pad do P1 chega ao nó do Pro"
    assert ao_backend == []


def test_o_dualsense_que_chega_toma_o_p1_e_o_pro_ganha_o_proprio_pad(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr, pad, dualsenses = _mesa_so_de_fora(monkeypatch, _Broker())
    pad.botoes.append(frozenset({"circle"}))

    dualsenses[P1] = "/dev/input/event20"
    mgr._daemon.controller.primary_uniq = P1
    mgr.sync(force=True)
    mgr.forward_all()

    pro = mgr._players[PRO]
    assert not pro.no_p1
    assert pro.vpad is not pad and PRO in mesa
    assert pro.player_index >= 2
    assert pad.botoes[-1] == frozenset() and pad.paradas == 0
    assert HIDRAW_DO_PRO not in mgr._daemon._hidraw_broker_client.devolvidos


def test_o_pro_que_sai_do_p1_nao_derruba_o_pad_do_p1(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr, pad, _ = _mesa_so_de_fora(monkeypatch, _Broker())

    monkeypatch.setattr(coop_mod, "externos_que_ganham_virtual", dict)
    mgr.sync(force=True)

    assert PRO not in mgr._players
    assert pad.paradas == 0
    assert pad.botoes[-1] == frozenset()
    assert pad.analogicos[-1] == {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}


def test_o_segundo_de_fora_ganha_pad_proprio(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        coop_mod,
        "externos_que_ganham_virtual",
        lambda: {
            PRO: (NO_DO_PRO, HIDRAW_DO_PRO, PAR_DO_PRO),
            OITO: ("/dev/input/event32", "/dev/hidraw10", (0x2DC8, 0x6001)),
        },
    )
    mgr, pad, _ = _mesa_so_de_fora(monkeypatch, _Broker())

    no_p1 = [m for m, p in mgr._players.items() if p.no_p1]
    assert len(no_p1) == 1 and mgr._players[no_p1[0]].vpad is pad
    outro = OITO if no_p1 == [PRO] else PRO
    assert outro in mesa and mgr._players[outro].player_index == 2


def test_o_default_env_leva_os_pares_da_foto() -> None:
    """A foto do daemon carrega os pares até o `default.env` e o ambiente do comum."""
    from hefesto_dualsense4unix.daemon import launch_env as le

    modo = le.ModoAntecipado(
        native=False, emulacao=True, mascara="dualsense",
        backends=("uhid", "uhid"), motivo="teste", fisicos=2,
    )
    foto = le._FotoDoLancamento(
        ordem=0, native=False, enabled=True, flavor="dualsense", backends=("uhid", "uhid"),
        fisicos=2, modo_vivo=modo, em_cena=frozenset(), identidade=None, permite_uhid=True,
        vpads_previstos=2, leitor=SimpleNamespace(), publicar=lambda _d: None,
        carimbar=lambda: None, foto_ms=0.0, externos=(PAR_DO_PRO,),
    )

    padrao, _estado = le._o_ambiente_padrao(foto)
    assert "0x057e/0x2009" in _ignore(padrao)
    assert "0x057e/0x2009" in _ignore(le._o_ambiente_do_comum(foto, padrao))


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("mascara", ["dualsense", "xbox"])
def test_o_de_fora_sentado_nao_anda_para_o_p1_quando_o_dualsense_cai(
    mesa: list[str], monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    """D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO: o P1 que cai, com o lugar guardado, não passa o boneco
    a quem já joga."""
    dualsenses = {P1: "/dev/input/event20"}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(dualsenses),
    )
    pad = _PadDoP1()
    pad.flavor = mascara
    daemon = _daemon(_Broker())
    daemon.config.gamepad_flavor = mascara
    daemon._gamepad_device = pad
    daemon.controller.is_connected = lambda: bool(dualsenses)
    registro = ControllerIdentityRegistry(clock=lambda: 1000.0)
    registro.slot_for(P1)
    registro.sync_connected([P1])
    daemon.identity_registry = registro
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    mgr.sync()
    mgr.sync(force=True)
    pro = mgr._players[PRO]
    proprio = pro.vpad
    assert proprio is not None and proprio is not pad and not pro.no_p1
    proprio.flavor = mascara
    numero = pro.player_index

    dualsenses.clear()
    daemon.controller.primary_uniq = None
    registro.sync_connected([])
    assert registro.o_lugar_1_espera()
    mgr.sync(force=True)
    mgr.forward_all()

    assert mgr._players[PRO] is pro and not pro.no_p1
    assert pro.vpad is proprio and pro.player_index == numero
    assert mgr.o_de_fora_no_p1() is None
    assert pad.botoes == []
