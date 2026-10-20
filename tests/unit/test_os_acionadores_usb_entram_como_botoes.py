"""OS-ACIONADORES-USB-ENTRAM-COMO-BOTOES-DO-CONTROLE-01 — a tecla do acionador sai no pad.

Um aparelho de entrada qualquer (acionador adaptado, pedal, teclado no lugar deles), declarado no
``maquina.json`` como fonte de botões de um controle, tem cada tecla somada aos botões que a mão
aperta naquele controle. A mesa tem quatro controles no backend do produto (dois no cabo, dois no
rádio), o P1 no ``dispatch_gamepad`` e o P2 a P4 no ``forward_all`` do co-op, nas máscaras DualSense
e Xbox; o que se lê é o ``EV_KEY`` e o ``ABS_Z`` que o jogo veria em cada pad virtual.

A régua nunca abre o ``/dev/input`` nem o ``/sys`` da máquina: o ``/sys/class/input`` é uma pasta
de mentira e o aparelho, um evdev de mentira; a ponte para no fim de cada caso.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    BOTOES_POR_FLAVOR,
    BUTTON_TO_UINPUT,
    UinputGamepad,
)
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    chave_do_acionador,
    fundir_declaracao,
)

MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
TRANSPORTES = (ConnectionType.USB, ConnectionType.BT, ConnectionType.USB, ConnectionType.BT)
MASCARAS = ("dualsense", "xbox")

NOME = "Acionador de mentira"
FISICO = "usb-0000:00:14.0-9/input0"
VENDOR, PRODUCT = "1234", "abcd"
CHAVE = chave_do_acionador(VENDOR, PRODUCT, NOME, FISICO)
TECLA_1 = ecodes.KEY_ENTER
PEDAL = ecodes.KEY_SPACE


def _handle(transporte: ConnectionType) -> Any:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = transporte
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    inst.connected = True
    return inst


class _No:
    """O nó do uinput de mentira: as teclas que o jogo leria e o último ``ABS_Z`` (o L2)."""

    def __init__(self) -> None:
        self.teclas: set[int] = set()
        self.l2: int | None = None

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_KEY:
            (self.teclas.add if valor else self.teclas.discard)(codigo)
        elif tipo == ecodes.EV_ABS and codigo == ecodes.ABS_Z:
            self.l2 = valor

    def syn(self) -> None:
        pass


def _botao_do_pad(pad: UinputGamepad, nome: str) -> str:
    """O nome evdev do botão ``nome`` no pad, pela tabela da máscara que o jogo vê."""
    return BOTOES_POR_FLAVOR.get(pad.mascara_no_jogo, BUTTON_TO_UINPUT)[nome]


def _pad(mascara: str) -> tuple[UinputGamepad, _No]:
    no = _No()
    pad = UinputGamepad(flavor=mascara)
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


class _Leitor:
    grab_state = "held"

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=frozenset())


class _Acionador:
    """O evdev de mentira do acionador: a fila de eventos, o grab e o fechar."""

    def __init__(self) -> None:
        self.fila: list[Any] = []
        self.preso = False
        self.fechado = False
        self.saiu = False

    def apertar(self, codigo: int, valor: int = 1) -> None:
        self.fila.append(SimpleNamespace(type=ecodes.EV_KEY, code=codigo, value=valor))

    def read(self) -> list[Any]:
        if self.saiu:
            raise OSError(19, "No such device")
        if not self.fila:
            raise BlockingIOError
        lidos, self.fila = self.fila, []
        return lidos

    def grab(self) -> None:
        self.preso = True

    def ungrab(self) -> None:
        self.preso = False

    def close(self) -> None:
        self.fechado = True


def _sys_de_mentira(raiz: Path) -> Path:
    """Um ``/sys/class/input`` com o teclado da casa e o acionador (só o acionador é declarado)."""
    for evento, nome, fisico, vendor, product in (
            ("event3", "Teclado da casa", "usb-0000:00:14.0-1/input0", "046d", "c31c"),
            ("event7", NOME, FISICO, VENDOR, PRODUCT)):
        dentro = raiz / evento / "device"
        (dentro / "id").mkdir(parents=True)
        (dentro / "name").write_text(nome + "\n")
        (dentro / "phys").write_text(fisico + "\n")
        (dentro / "id" / "vendor").write_text(vendor + "\n")
        (dentro / "id" / "product").write_text(product + "\n")
    return raiz


class _Mesa:
    """Quatro pads, a ponte com o ``/sys`` de mentira e o acionador declarado para ``controle``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mascara: str,
                 controle: str | None, teclas: dict[str, str] | None = None) -> None:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        reader = EvdevReader(device_path=None)
        reader._device_path = None
        backend = bp.PyDualSenseController(evdev_reader=reader)
        backend._handles = {mac: _handle(t) for mac, t in zip(MACS, TRANSPORTES, strict=True)}
        backend._primary_key = MACS[0]
        pads = [_pad(mascara) for _ in UNIQS]
        self.pads = [pad for pad, _ in pads]
        self.nos = [no for _, no in pads]
        self.acionador = _Acionador()
        self.abertos: list[str] = []
        self.em_jogo = False
        self.agora = 0.0

        def abrir(evento: str) -> Any:
            self.abertos.append(evento)
            return self.acionador

        self.ponte = gp.PonteDosAcionadores(
            raiz=_sys_de_mentira(tmp_path / "input"), abrir=abrir, relogio=lambda: self.agora)
        declarado = {} if controle is None else {CHAVE: {
            "nome": NOME, "controle": controle,
            "teclas": teclas if teclas is not None else {str(TECLA_1): "cross",
                                                         str(PEDAL): "l2"}}}
        self.daemon = SimpleNamespace(
            store=StateStore(),
            controller=SimpleNamespace(primary_uniq=UNIQS[0]),
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor=mascara),
            identity_registry=None,
            _gamepad_device=self.pads[0],
            _coop_manager=None,
            _hotkey_manager=None,
            _maquina=MaquinaConfig.model_validate({"acionadores": declarado}),
            _ponte_dos_acionadores=self.ponte,
            _janela_de_jogo_em_foco=lambda: self.em_jogo,
        )
        self.coop = CoopManager(self.daemon)
        for n, uniq in enumerate(UNIQS[1:], 2):
            self.coop._players[uniq] = _SecondaryPlayer(
                identity=uniq, evdev_path=f"/dev/input/event{n + 10}",
                reader=cast(Any, _Leitor()), player_index=n, vpad=self.pads[n - 1])

    def tique(self) -> None:
        estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
                                 l2_raw=0, r2_raw=0)
        gp.dispatch_gamepad(self.daemon, estado, frozenset())
        self.coop.forward_all()

    def com_a_cruz(self) -> list[bool]:
        """Em quais dos quatro pads o jogo vê a Cruz apertada."""
        cruz = [cast(int, getattr(ecodes, _botao_do_pad(pad, "cross"))) for pad in self.pads]
        return [c in no.teclas for c, no in zip(cruz, self.nos, strict=True)]





@pytest.fixture
def mesas() -> Any:
    criadas: list[_Mesa] = []
    yield criadas
    for mesa in criadas:
        mesa.ponte.parar()


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("jogador", range(4))
def test_a_tecla_do_acionador_sai_como_o_botao_escolhido_no_pad_daquele_controle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa], mascara: str,
    jogador: int,
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, mascara, UNIQS[jogador])
    mesas.append(mesa)
    mesa.tique()
    assert mesa.abertos == ["event7"], "a ponte abre só o aparelho declarado, achado pelo /sys"
    assert mesa.com_a_cruz() == [False] * 4

    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    esperado = [n == jogador for n in range(4)]
    assert mesa.com_a_cruz() == esperado

    mesa.acionador.apertar(TECLA_1, 2)  # a repetição do teclado não solta nada
    mesa.tique()
    assert mesa.com_a_cruz() == esperado

    mesa.acionador.apertar(TECLA_1, 0)
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_pedal_no_l2_aperta_o_gatilho_inteiro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa], mascara: str,
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, mascara, UNIQS[1])
    mesas.append(mesa)
    mesa.acionador.apertar(PEDAL)
    mesa.tique()
    assert [no.l2 for no in mesa.nos] == [0, 255, 0, 0]
    mesa.acionador.apertar(PEDAL, 0)
    mesa.tique()
    assert [no.l2 for no in mesa.nos] == [0, 0, 0, 0]


def test_sem_o_mapeamento_a_tecla_nao_chega_a_pad_nenhum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    """A mordida da declaração: sem acionador declarado, nada abre e nada chega."""
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", None)
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.abertos == []
    assert mesa.com_a_cruz() == [False] * 4


def test_a_tecla_sem_botao_escolhido_nao_vira_botao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0], {str(PEDAL): "circle"})
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4


def test_fora_do_jogo_o_aparelho_e_do_sistema_e_no_jogo_fica_preso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.tique()
    assert not mesa.acionador.preso
    mesa.em_jogo, mesa.agora = True, gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert mesa.acionador.preso
    mesa.em_jogo, mesa.agora = False, 2 * gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert not mesa.acionador.preso
    mesa.em_jogo, mesa.agora = True, 3 * gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert mesa.acionador.preso
    # O modo que sai do pad virtual devolve o aparelho ao sistema (o resto da parada fica mudo).
    from hefesto_dualsense4unix.daemon.subsystems import rumble

    for nome in ("_largar_o_p1_que_nasce", "stop_motion_reader", "soltar_a_ativacao",
                 "_materialize_launch_env"):
        monkeypatch.setattr(gp, nome, lambda d: None)
    monkeypatch.setattr(rumble, "zero_motors_on_mode_exit", lambda d: None)
    mesa.daemon._gamepad_device = None
    gp.stop_gamepad_emulation(cast(Any, mesa.daemon), persist=False, release_grab=False)
    assert not mesa.acionador.preso and mesa.acionador.fechado


def test_o_aparelho_que_sai_da_porta_solta_a_tecla_e_volta_quando_volta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.com_a_cruz()[0]
    mesa.acionador.saiu = True
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4
    mesa.acionador.saiu = False
    mesa.agora = gp.PROCURAR_O_ACIONADOR_A_CADA_S
    mesa.tique()
    assert mesa.abertos == ["event7", "event7"]


def test_a_declaracao_que_esquece_o_acionador_fecha_o_aparelho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.tique()
    bruto = fundir_declaracao(mesa.daemon._maquina.model_dump(), {"acionadores": {CHAVE: None}})
    mesa.daemon._maquina = MaquinaConfig.model_validate(bruto)
    mesa.tique()
    assert mesa.acionador.fechado


def test_daemon_sem_declaracao_nao_cria_ponte_nem_le_o_sys() -> None:
    """Custo zero sem acionador, e um ``_maquina`` de dublê qualquer não liga a ponte."""
    for maquina in (None, MaquinaConfig(), SimpleNamespace(acionadores=object())):
        daemon = SimpleNamespace(_maquina=maquina)
        gp.andar_os_acionadores(daemon)
        assert gp.ponte_dos_acionadores(daemon) is None
        assert not hasattr(daemon, "_ponte_dos_acionadores")


def test_o_maquina_json_guarda_o_acionador_pela_chave_sem_endereco() -> None:
    assert CHAVE.startswith(f"{VENDOR}:{PRODUCT}:") and len(CHAVE) == 18
    assert FISICO not in CHAVE
    doc = MaquinaConfig.model_validate({"acionadores": {CHAVE: {
        "controle": UNIQS[2], "teclas": {"28": "cross", "57": "l2"}}}})
    assert doc.acionadores[CHAVE].teclas == {"28": "cross", "57": "l2"}
    junto = fundir_declaracao(doc.model_dump(), {"acionadores": {CHAVE: {"teclas": {"57": None}}}})
    assert MaquinaConfig.model_validate(junto).acionadores[CHAVE].teclas == {"28": "cross"}
    for ruim in ({"x": {}}, {CHAVE: {"teclas": {"28": "ps"}}},
                 {CHAVE: {"teclas": {"tecla": "cross"}}}, {CHAVE: {"controle": "02bbcc0000ff"}}):
        with pytest.raises(ValueError):
            MaquinaConfig.model_validate({"acionadores": ruim})
    assert json.loads(doc.model_dump_json())["acionadores"][CHAVE]["controle"] == UNIQS[2]
