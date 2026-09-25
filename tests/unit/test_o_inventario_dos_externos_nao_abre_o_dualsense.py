"""O-INVENTARIO-DOS-EXTERNOS-NAO-ABRE-O-DUALSENSE-01 — quem procura externo não abre o DualSense.

Medido na máquina dela em 25/09/2026, com os quatro DualSense ligados: o
inventário dos externos abria pelo broker o nó de gamepad de cada controle a
cada 1,3 s (o tique dos externos, 2 s, e a janela, `controller.list` a cada
4 s), só para ler a identidade e descartar. Cada abertura é uma linha em cada
diário, e elas eram 95% do diário do daemon e 99% do do broker.

A MESA DE MENTIRA. Nenhuma régua daqui toca o `/dev/input` dela (ela está no
grupo `input`, e 20 nós respondem): o `/dev/input` é uma pasta de arquivos
em tmp, com os nós do DualSense `0000` quando escondidos (é o que o
`0600 root` é para ela) e `0660` quando abertos (o Nativo). O
`evdev.list_devices` lista pelo critério da biblioteca, o do acesso. O
`InputDevice` é o da biblioteca, com o `__init__` de verdade: ele recusa o nó
escondido com o `PermissionError` do próprio `os.open` e conta cada
tentativa; os ioctls respondem a identidade do nó que o fd aponta. O `sysfs`
(`SYS_CLASS_INPUT`) é uma árvore em tmp, e o `os.path.realpath` do
`/sys/class/input/*/device` fixo aponta para ela. O broker é um servidor Unix
de verdade num caminho curto, e o `HidrawBrokerClient` que fala com ele é o
real: é ele quem escreve a linha `hidraw_broker_fd_recebido state=entrada`.
Um `os.open` em `/dev/input`, `/dev/hidraw`, `/dev/uinput` ou `/dev/uhid`
reprova a régua.

A matriz é a regra dela: de um a quatro DualSense, pelo cabo, pelo rádio e
misto, com o Edge (0df2), escondidos e abertos, com e sem o Pro (057e:2009) e
o 8BitDo em modo PS4 (054c:05c4, que é Sony e não é DualSense).
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

evdev = pytest.importorskip("evdev")

from evdev import ecodes

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from tests.unit.test_hidraw_broker_client import (
    _cleanup_socket_dir,
    _ServidorRoteirizado,
    _short_socket_dir,
)

# --- os aparelhos -----------------------------------------------------------

_AXIS_DS = (128, 0, 255, 0, 0, 0)
_AXIS_PRO = (0, -32767, 32767, 250, 500, 0)
_AXIS_HAT = (0, -1, 1, 0, 0, 0)
_AXIS_IMU = (0, -32768, 32767, 16, 0, 8192)
_BOTOES = [
    ecodes.BTN_SOUTH, ecodes.BTN_EAST, ecodes.BTN_NORTH, ecodes.BTN_WEST,
    ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_TL2, ecodes.BTN_TR2,
    ecodes.BTN_SELECT, ecodes.BTN_START, ecodes.BTN_MODE,
    ecodes.BTN_THUMBL, ecodes.BTN_THUMBR,
]


def _caps_gamepad(eixo: tuple[int, ...]) -> dict[int, list[Any]]:
    return {
        ecodes.EV_KEY: list(_BOTOES),
        ecodes.EV_ABS: [
            (ecodes.ABS_X, eixo), (ecodes.ABS_Y, eixo),
            (ecodes.ABS_RX, eixo), (ecodes.ABS_RY, eixo),
            (ecodes.ABS_HAT0X, _AXIS_HAT), (ecodes.ABS_HAT0Y, _AXIS_HAT),
        ],
    }


_CAPS_MOVIMENTO = {
    ecodes.EV_ABS: [(c, _AXIS_IMU) for c in (ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_Z,
                                            ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_RZ)],
}
_CAPS_TOUCHPAD = {
    ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_TOOL_FINGER, ecodes.BTN_TOUCH],
    ecodes.EV_ABS: [(ecodes.ABS_X, (0, 0, 1919, 0, 0, 0)), (ecodes.ABS_Y, (0, 0, 1079, 0, 0, 0))],
}
_CAPS_TECLADO = {ecodes.EV_KEY: [ecodes.KEY_ESC, ecodes.KEY_A, ecodes.KEY_ENTER]}

#: O bitmap `capabilities/key` do sysfs: o do gamepad tem BTN_SOUTH..BTN_THUMBR
#: na palavra 4 (a régua da HIDE-02 usa o mesmo), o do touchpad não tem o
#: BTN_GAMEPAD, e o de movimento é vazio.
_TECLAS_GAMEPAD = "7fdb000000000000 0 0 0 0"
_TECLAS_TOUCHPAD = "e520 10000 0 0 0 0"
_TECLAS_VAZIAS = "0"
_TECLAS_TECLADO = "1 0 0 0"


@dataclass(frozen=True)
class _No:
    """Um `eventN` da mesa: o que o kernel diria dele pelo fd e pelo sysfs."""

    evento: str
    vendor: int
    product: int
    bus: int
    name: str
    uniq: str
    caps: dict[int, list[Any]]
    teclas: str
    dono: str  # o dir do aparelho no sysfs, relativo a `sys/devices`
    papel: str  # gamepad | movimento | touchpad | teclado
    dualsense: bool
    virtual: bool = False


@dataclass(frozen=True)
class _DS:
    transporte: str  # "bt" | "usb"
    pid: int = 0x0CE6


BT = _DS("bt")
USB = _DS("usb")
EDGE = _DS("usb", 0x0DF2)

#: A matriz dela: um a quatro, cabo, rádio e misto, e o Edge.
MESAS: dict[str, list[_DS]] = {
    "1-bt": [BT],
    "1-usb": [USB],
    "1-edge": [EDGE],
    "2-bt": [BT, BT],
    "2-usb-edge": [USB, EDGE],
    "2-misto": [BT, USB],
    "3-misto": [BT, BT, USB],
    "4-misto": [BT, BT, USB, EDGE],
}

MAC_PRO = "aa:bb:cc:00:be:ef"
MAC_8BITDO = "aa:bb:cc:00:84:01"


def mac_ds(k: int) -> str:
    return f"aa:bb:cc:00:d5:{k:02x}"


def _nos_do_dualsense(k: int, ds: _DS) -> list[tuple[str, dict[str, Any]]]:
    hid = f"{0x0005 if ds.transporte == 'bt' else 0x0003:04X}:054C:{ds.pid:04X}.{0x10 + k:04X}"
    dono = (
        f"virtual/misc/uhid/{hid}" if ds.transporte == "bt"
        else f"pci0000:00/0000:00:14.0/usb1/1-{k}/1-{k}:1.3/{hid}"
    )
    nome = (
        "DualSense Edge Wireless Controller" if ds.pid == 0x0DF2
        else "DualSense Wireless Controller"
    )
    comum = {
        "vendor": 0x054C, "product": ds.pid, "bus": 0x05 if ds.transporte == "bt" else 0x03,
        "uniq": mac_ds(k), "dono": dono, "dualsense": True,
    }
    return [
        ("gamepad", {**comum, "name": nome, "caps": _caps_gamepad(_AXIS_DS),
                     "teclas": _TECLAS_GAMEPAD}),
        ("movimento", {**comum, "name": f"{nome} Motion Sensors", "caps": _CAPS_MOVIMENTO,
                       "teclas": _TECLAS_VAZIAS}),
        ("touchpad", {**comum, "name": f"{nome} Touchpad", "caps": _CAPS_TOUCHPAD,
                      "teclas": _TECLAS_TOUCHPAD}),
    ]


def _nos_do_vpad(k: int) -> list[tuple[str, dict[str, Any]]]:
    """O DualSense VIRTUAL do jogador k (054c:0df2, uniq 02:fe): o daemon o
    cria e ele fica aberto na máquina dela; ninguém o abre na descoberta."""
    return [("gamepad", {
        "vendor": 0x054C, "product": 0x0DF2, "bus": 0x03,
        "uniq": f"02:fe:00:00:00:{k:02x}", "name": f"DualSense Wireless Controller (Hefesto P{k})",
        "dono": f"virtual/misc/uhid/0003:054C:0DF2.{0x80 + k:04X}", "dualsense": True,
        "virtual": True, "caps": _caps_gamepad(_AXIS_DS), "teclas": _TECLAS_GAMEPAD,
    })]


def _nos_do_pro() -> list[tuple[str, dict[str, Any]]]:
    comum = {"vendor": 0x057E, "product": 0x2009, "bus": 0x03, "uniq": MAC_PRO,
             "dono": "pci0000:00/0000:00:14.0/usb1/1-6/1-6:1.0/0003:057E:2009.0050",
             "dualsense": False}
    return [
        ("gamepad", {**comum, "name": "Nintendo Co., Ltd. Pro Controller",
                     "caps": _caps_gamepad(_AXIS_PRO), "teclas": _TECLAS_GAMEPAD}),
        ("movimento", {**comum, "name": "Nintendo Co., Ltd. Pro Controller (IMU)",
                       "caps": _CAPS_MOVIMENTO, "teclas": _TECLAS_VAZIAS}),
    ]


def _nos_do_8bitdo() -> list[tuple[str, dict[str, Any]]]:
    """O 8BitDo em modo PS4 pelo rádio: VENDOR Sony, produto de DualShock 4."""
    comum = {"vendor": 0x054C, "product": 0x05C4, "bus": 0x05, "uniq": MAC_8BITDO,
             "dono": "virtual/misc/uhid/0005:054C:05C4.0060", "dualsense": False}
    return [
        ("gamepad", {**comum, "name": "Wireless Controller",
                     "caps": _caps_gamepad(_AXIS_DS), "teclas": _TECLAS_GAMEPAD}),
        ("movimento", {**comum, "name": "Wireless Controller Motion Sensors",
                       "caps": _CAPS_MOVIMENTO, "teclas": _TECLAS_VAZIAS}),
        ("touchpad", {**comum, "name": "Wireless Controller Touchpad",
                      "caps": _CAPS_TOUCHPAD, "teclas": _TECLAS_TOUCHPAD}),
    ]


def _nos_do_teclado() -> list[tuple[str, dict[str, Any]]]:
    return [("teclado", {
        "vendor": 0x258A, "product": 0x010C, "bus": 0x03, "uniq": "",
        "name": "BY Tech Gaming Keyboard", "caps": _CAPS_TECLADO, "teclas": _TECLAS_TECLADO,
        "dono": "pci0000:00/0000:00:14.0/usb1/1-9/1-9:1.0/0003:258A:010C.0070",
        "dualsense": False,
    })]


# --- a mesa -----------------------------------------------------------------

_PORTAS_PROIBIDAS = ("/dev/input", "/dev/hidraw", "/dev/uinput", "/dev/uhid")


@dataclass
class Mesa:
    raiz: Path
    dev_input: Path
    sys_class: Path
    nos: dict[str, _No] = field(default_factory=dict)  # eventN -> nó
    #: caminho `/dev` de mentira -> papel e dono, para as asserções.
    caminho: dict[str, str] = field(default_factory=dict)  # eventN -> caminho
    tentativas: list[str] = field(default_factory=list)  # InputDevice(caminho)
    pedidos: list[dict[str, Any]] = field(default_factory=list)  # linhas no socket
    diario: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    no_dev_de_verdade: list[str] = field(default_factory=list)
    escritas_de_led: list[Any] = field(default_factory=list)

    # -- leitura para as réguas --
    def de(self, k: int, papel: str = "gamepad") -> str:
        """O caminho do nó `papel` do DualSense k (1..N)."""
        for evento, no in self.nos.items():
            if no.dualsense and not no.virtual and no.uniq == mac_ds(k) and no.papel == papel:
                return self.caminho[evento]
        raise KeyError((k, papel))

    def caminhos_de_dualsense(self) -> set[str]:
        return {self.caminho[e] for e, no in self.nos.items() if no.dualsense}

    def fd_recebidos(self) -> list[dict[str, Any]]:
        return [kw for _nivel, evento, kw in self.diario
                if evento == "hidraw_broker_fd_recebido" and kw.get("state") == "entrada"]

    def tentativas_em_dualsense(self) -> list[str]:
        ds = self.caminhos_de_dualsense()
        return [c for c in self.tentativas if c in ds]

    def pedidos_de_open(self) -> list[str]:
        return [p.get("node", "") for p in self.pedidos if p.get("cmd") == "open"]

    def sysfs_ilegivel(self, caminho: str) -> None:
        """Tira o `id/` do nó: o sysfs deixa de dizer quem ele é."""
        base = os.path.basename(caminho)
        destino = Path(os.path.realpath(self.sys_class / base / "device")) / "id"
        for arquivo in destino.iterdir():
            arquivo.unlink()
        destino.rmdir()


class _RoteiroQueConta(dict[str, Any]):
    """O roteiro do servidor, que conta TODA linha que chega ao socket.

    O `_ServidorRoteirizado` pergunta `cmd in roteiro` uma vez por linha: é
    ali que a contagem mora, e todo comando acha resposta (o `open` é servido,
    o resto é recusado como o broker velho recusa).
    """

    def __init__(self, mesa: Mesa, servir: Any) -> None:
        super().__init__()
        self._mesa = mesa
        self._servir = servir

    def __contains__(self, cmd: object) -> bool:
        return True

    def __getitem__(self, cmd: str) -> Any:
        def _atender(conn: socket.socket, pedido: dict[str, Any]) -> None:
            self._mesa.pedidos.append(dict(pedido))
            if cmd == "open":
                self._servir(conn, pedido)
                return
            conn.sendall(json.dumps(
                {"ok": False, "cmd": cmd, "error": "reject_unknown_cmd"}
            ).encode("utf-8") + b"\n")

        return _atender


class _Diario:
    """O `logger` do cliente do broker: guarda cada linha e a escreve igual."""

    def __init__(self, original: Any, linhas: list[tuple[str, str, dict[str, Any]]]) -> None:
        self._original = original
        self._linhas = linhas

    def __getattr__(self, nivel: str) -> Any:
        metodo = getattr(self._original, nivel)

        def _escrever(evento: str, *args: Any, **kw: Any) -> Any:
            self._linhas.append((nivel, evento, dict(kw)))
            return metodo(evento, *args, **kw)

        return _escrever


def _montar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dualsenses: list[_DS],
    *,
    escondidos: bool,
    externos: bool,
) -> Iterator[Mesa]:
    if escondidos and os.geteuid() == 0:  # pragma: no cover - como root o 0000 não fecha
        pytest.skip("como root todo nó abre")
    mesa = Mesa(raiz=tmp_path, dev_input=tmp_path / "dev-input",
                sys_class=tmp_path / "sys-class-input")
    mesa.dev_input.mkdir()
    mesa.sys_class.mkdir()
    sombras = tmp_path / "servidos"
    sombras.mkdir()

    # Intercalados, como na máquina dela: DualSense, externos e teclado.
    aparelhos: list[list[tuple[str, dict[str, Any]]]] = []
    for k, ds in enumerate(dualsenses, start=1):
        aparelhos.append(_nos_do_dualsense(k, ds))
        if k == 1 and externos:
            aparelhos.append(_nos_do_pro())
        if k == 2 and externos:
            aparelhos.append(_nos_do_8bitdo())
        if k == 2:
            aparelhos.append(_nos_do_teclado())
    if len(dualsenses) < 2:
        if externos:
            aparelhos.append(_nos_do_8bitdo())
        aparelhos.append(_nos_do_teclado())
    for k in range(1, len(dualsenses) + 1):
        aparelhos.append(_nos_do_vpad(k))

    realpaths: dict[str, str] = {}
    numero = 9101
    for aparelho in aparelhos:
        for indice, (papel, spec) in enumerate(aparelho):
            evento = f"event{numero}"
            numero += 1
            no = _No(evento=evento, papel=papel, **spec)
            mesa.nos[evento] = no
            # O sysfs: `<dono>/input/inputM` com id, name, uniq, phys e caps;
            # o dono tem `driver` e `hidraw/`, como a subida espera.
            dono = tmp_path / "sys" / "devices" / no.dono
            entrada = dono / "input" / f"input{numero}"
            (entrada / "id").mkdir(parents=True)
            (entrada / "id" / "vendor").write_text(f"{no.vendor:04x}\n", encoding="ascii")
            (entrada / "id" / "product").write_text(f"{no.product:04x}\n", encoding="ascii")
            (entrada / "name").write_text(no.name + "\n", encoding="utf-8")
            (entrada / "uniq").write_text(no.uniq + "\n", encoding="ascii")
            (entrada / "phys").write_text("\n", encoding="ascii")
            (entrada / "capabilities").mkdir()
            (entrada / "capabilities" / "key").write_text(no.teclas + "\n", encoding="ascii")
            if indice == 0 and not (dono / "driver").exists():
                driver = tmp_path / "sys" / "bus" / "drivers" / (
                    "nintendo" if no.vendor == 0x057E else
                    "playstation" if no.vendor == 0x054C else "hid-generic"
                )
                driver.mkdir(parents=True, exist_ok=True)
                (dono / "driver").symlink_to(driver)
                (dono / "hidraw" / f"hidraw{numero}").mkdir(parents=True)
            (mesa.sys_class / evento).mkdir()
            (mesa.sys_class / evento / "device").symlink_to(entrada)
            realpaths[f"/sys/class/input/{evento}/device"] = str(entrada)
            # O /dev/input: o físico escondido é 0000, o resto é 0660.
            arquivo = mesa.dev_input / evento
            arquivo.write_text("", encoding="ascii")
            fechado = escondidos and no.dualsense and not no.virtual
            arquivo.chmod(0o000 if fechado else 0o660)
            mesa.caminho[evento] = str(arquivo)
            (sombras / evento).write_text("", encoding="ascii")

    # -- o sysfs --
    monkeypatch.setattr(er, "SYS_CLASS_INPUT", str(mesa.sys_class))
    monkeypatch.setattr(er, "DEV_INPUT_DIR", str(mesa.dev_input))
    realpath_de_verdade = os.path.realpath

    def _realpath(caminho: Any, **kw: Any) -> str:
        texto = os.fspath(caminho)
        if isinstance(texto, str) and texto.startswith("/sys/class/input/"):
            # Nunca o sysfs dela: fora da mesa é um diretório que não existe.
            return realpaths.get(texto, str(tmp_path / "sys" / "fora-da-mesa"))
        return str(realpath_de_verdade(caminho, **kw))

    monkeypatch.setattr("os.path.realpath", _realpath)

    # -- o /dev de verdade é proibido --
    os_open_de_verdade = os.open

    def _os_open(caminho: Any, flags: int, *args: Any, **kw: Any) -> int:
        with contextlib.suppress(TypeError, ValueError):
            texto = os.fsdecode(caminho)
            if texto.startswith(_PORTAS_PROIBIDAS):
                mesa.no_dev_de_verdade.append(texto)
                raise AssertionError(f"a régua tentou abrir {texto} de verdade")
        return os_open_de_verdade(caminho, flags, *args, **kw)

    monkeypatch.setattr(os, "open", _os_open)

    # -- a biblioteca --
    def _list_devices(input_device_dir: str | None = None) -> list[str]:
        assert input_device_dir in (None, str(mesa.dev_input)), input_device_dir
        return [str(c) for c in sorted(mesa.dev_input.glob("event*"))
                if os.access(c, os.R_OK | os.W_OK)]

    monkeypatch.setattr("evdev.list_devices", _list_devices)
    init_de_verdade = evdev.InputDevice.__init__

    def _init(self: Any, dev: Any) -> None:
        texto = os.fspath(dev)
        assert os.path.dirname(texto) == str(mesa.dev_input), texto
        mesa.tentativas.append(texto)
        init_de_verdade(self, dev)

    monkeypatch.setattr(evdev.InputDevice, "__init__", _init)

    from evdev import _input

    def _no_do_fd(fd: int) -> _No:
        try:
            base = os.path.basename(os.readlink(f"/proc/self/fd/{fd}"))
        except OSError as erro:
            raise OSError(25, "Inappropriate ioctl for device") from erro
        no = mesa.nos.get(base)
        if no is None:
            raise OSError(25, "Inappropriate ioctl for device")
        return no

    def _devinfo(fd: int) -> tuple[Any, ...]:
        no = _no_do_fd(fd)
        return (no.bus, no.vendor, no.product, 0x8111, no.name, "", no.uniq)

    monkeypatch.setattr(_input, "ioctl_devinfo", _devinfo)
    monkeypatch.setattr(_input, "ioctl_EVIOCGVERSION", lambda fd: (_no_do_fd(fd), 0x010001)[1])
    monkeypatch.setattr(
        _input, "ioctl_capabilities",
        lambda fd: {tipo: list(codigos) for tipo, codigos in _no_do_fd(fd).caps.items()},
    )
    monkeypatch.setattr(_input, "ioctl_EVIOCGEFFECTS", lambda fd: (_no_do_fd(fd), 0)[1])

    # -- o broker, num socket de verdade --
    sockdir = _short_socket_dir(tmp_path)
    sock = os.path.join(sockdir, "broker.sock")
    servidos = {
        mesa.caminho[e]: str(sombras / e)
        for e, no in mesa.nos.items()
        if escondidos and no.dualsense and not no.virtual
    }

    def _servir(conn: socket.socket, pedido: dict[str, Any]) -> None:
        sombra = servidos.get(str(pedido.get("node")))
        if sombra is None:
            conn.sendall(b'{"ok": false, "cmd": "open", "error": "not_dualsense_input"}\n')
            return
        fd = os_open_de_verdade(sombra, os.O_RDONLY | os.O_CLOEXEC)
        try:
            linha = b'{"ok": true, "cmd": "open", "state": "entrada"}\n'
            conn.sendmsg([linha], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", fd))])
        finally:
            os.close(fd)

    servidor = _ServidorRoteirizado(sock, _RoteiroQueConta(mesa, _servir))
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", sock)
    monkeypatch.setattr(er, "_ABRIDOR_DO_BROKER", None)
    monkeypatch.setattr(er, "_CLIENTE_DO_BROKER", None)
    monkeypatch.setattr(hbc, "logger", _Diario(hbc.logger, mesa.diario))

    # -- nada de luz nem de IMU de verdade nos externos --
    import hefesto_dualsense4unix.core.external_leds as leds

    def _sem_escrita(nome: str) -> Any:
        def _anotar(*args: Any, **_kw: Any) -> bool:
            mesa.escritas_de_led.append((nome, args))
            return False

        return _anotar

    for nome in ("apply_player_number", "write_player_number", "enable_imu"):
        monkeypatch.setattr(leds, nome, _sem_escrita(nome))
    try:
        yield mesa
    finally:
        cliente = er._CLIENTE_DO_BROKER
        if cliente is not None:
            with contextlib.suppress(Exception):
                cliente.close()
        servidor.close()
        _cleanup_socket_dir(sockdir, sock)
        assert mesa.no_dev_de_verdade == [], mesa.no_dev_de_verdade


@pytest.fixture
def montar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    """`montar(dualsenses, escondidos=..., externos=...)` — uma mesa por teste."""
    abertas: list[Iterator[Mesa]] = []

    def _montar_uma(dualsenses: list[_DS], *, escondidos: bool, externos: bool) -> Mesa:
        gerador = _montar(monkeypatch, tmp_path, dualsenses,
                          escondidos=escondidos, externos=externos)
        abertas.append(gerador)
        return next(gerador)

    yield _montar_uma
    for gerador in abertas:
        with contextlib.suppress(StopIteration):
            next(gerador)


def _vista_de_hoje() -> list[dict[str, Any]]:
    """O que a vista dos externos devolvia antes da cura: a descoberta sem
    espécie, filtrada depois de abrir."""
    return [
        gp.como_entrada_de_inventario()
        for gp in er.discover_gamepads()
        if gp.especie == er.ESPECIE_EXTERNAL
    ]


def _vidpids(inventario: list[dict[str, Any]]) -> list[str]:
    return [f"{e['vid']}:{e['pid']}" for e in inventario]


_MATRIZ = [
    pytest.param(
        nome, escondidos, externos,
        id=f"{nome}-{'escondidos' if escondidos else 'abertos'}"
        f"-{'com-externos' if externos else 'sem-externos'}",
    )
    for nome in MESAS
    for escondidos in (True, False)
    for externos in (True, False)
]


# --- R0, a mesa alcança o broker --------------------------------------------


@pytest.mark.parametrize(("nome", "escondidos", "externos"), _MATRIZ)
def test_r0_a_mesa_alcanca_o_broker_e_acha_todos_os_dualsense(
    montar: Any, nome: str, escondidos: bool, externos: bool
) -> None:
    """O irmão que mede ANTES: quem quer o DualSense chega a cada um deles.

    Sem ele, uma mesa que não alcança o broker deixaria a R1 verde sobre
    nada. Escondidos, é um pedido ao broker por gamepad, cada um com a sua
    linha no diário; abertos, o caminho abre como sempre e o broker não é
    consultado. A MORDIDA: aplique o pulo sem olhar a espécie e esta régua
    reprova, porque os DualSense somem da descoberta de quem os quer.
    """
    dualsenses = MESAS[nome]
    mesa = montar(dualsenses, escondidos=escondidos, externos=externos)
    n = len(dualsenses)

    achados = er.discover_gamepads()

    gamepads = [mesa.de(k) for k in range(1, n + 1)]
    ds = [gp for gp in achados if gp.especie == er.ESPECIE_DUALSENSE]
    assert [gp.evdev_path for gp in ds] == gamepads
    if escondidos:
        assert mesa.pedidos_de_open() == gamepads, "um pedido por DualSense escondido"
        assert [kw["node"] for kw in mesa.fd_recebidos()] == gamepads
    else:
        assert mesa.pedidos == []
        assert set(gamepads) <= set(mesa.tentativas_em_dualsense())

    mapa = er.discover_dualsense_evdevs()
    assert mapa == {mac_ds(k).replace(":", ""): Path(mesa.de(k)) for k in range(1, n + 1)}


# --- R1, no tempo e pelos dois chamadores reais -----------------------------


def _chamadores(dualsenses: list[_DS], tmp_path: Path) -> tuple[Any, Any]:
    """O tique dos externos e o `controller.list` de verdade, sobre um só
    registro — como no daemon."""
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        ExternalIdentityRegistry,
        ExternalLedSync,
    )
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    registro = ExternalIdentityRegistry()
    slots_ds = {mac_ds(k).replace(":", ""): k for k in range(1, len(dualsenses) + 1)}
    daemon = SimpleNamespace(
        identity_registry=SimpleNamespace(snapshot=lambda: dict(slots_ds), auto_enabled=True),
        external_registry=registro,
    )
    tique = ExternalLedSync(daemon, registro)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb")
    )
    janela = IpcServer(
        controller=fc, store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "hefesto.sock", daemon=daemon,
    )
    return tique, janela


@pytest.mark.parametrize(("nome", "escondidos", "externos"), _MATRIZ)
async def test_r1_o_tique_e_a_janela_nao_abrem_o_dualsense_no_tempo(
    montar: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    nome: str, escondidos: bool, externos: bool,
) -> None:
    """Dois minutos da máquina dela, pelos dois chamadores de verdade.

    60 `ExternalLedSync.tick` a cada 2 s e 30 `controller.list
    {external: true}` a cada 4 s, intercalados. Depois de CADA passo: zero
    pedidos no socket, zero `hidraw_broker_fd_recebido state=entrada`, zero
    `InputDevice` em nó de DualSense, e o Pro com o mesmo número. A MORDIDA:
    tire o pulo da vista e a régua reprova no primeiro tique.
    """
    from hefesto_dualsense4unix.daemon import ipc_handlers as ih
    from hefesto_dualsense4unix.profiles import loader as loader_module

    dualsenses = MESAS[nome]
    mesa = montar(dualsenses, escondidos=escondidos, externos=externos)
    perfis = tmp_path / "perfis-da-janela"
    perfis.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: perfis)
    monkeypatch.setattr(ih, "_steam_hidraw_holders", lambda: {})
    tique, janela = _chamadores(dualsenses, tmp_path)

    def _foto(rotulo: str) -> tuple[str, int, int, int]:
        return (rotulo, len(mesa.pedidos), len(mesa.fd_recebidos()),
                len(mesa.tentativas_em_dualsense()))

    passos: list[tuple[str, int, int, int]] = []
    pedidos_por_chamador = {"tique": 0, "janela": 0}
    numeros_do_pro: list[Any] = []
    inventarios: list[list[str]] = []
    for passo in range(60):
        t = passo * 2.0
        antes = len(mesa.pedidos)
        tique.tick(now=t)
        pedidos_por_chamador["tique"] += len(mesa.pedidos) - antes
        passos.append(_foto(f"tique t={t:.0f}s"))
        if passo % 2 == 0:
            antes = len(mesa.pedidos)
            resposta = await janela._handle_controller_list({"external": True})
            pedidos_por_chamador["janela"] += len(mesa.pedidos) - antes
            vistos = resposta["external"]
            inventarios.append(_vidpids(vistos))
            numeros_do_pro.extend(e.get("player_slot") for e in vistos if e["vid"] == "057e")
            passos.append(_foto(f"janela t={t:.0f}s"))

    assert len(passos) == 90
    sujos = [p for p in passos if any(p[1:])]
    assert not sujos, (
        f"o primeiro passo sujo: {sujos[0][0]} (pedidos, linhas state=entrada, "
        f"InputDevice em DualSense = {sujos[0][1:]}); nos 90 passos: "
        f"{pedidos_por_chamador['tique']} pedidos no tique e "
        f"{pedidos_por_chamador['janela']} na janela, {len(mesa.fd_recebidos())} "
        f"linhas state=entrada, {len(mesa.tentativas_em_dualsense())} InputDevice "
        f"em nó de DualSense"
    )
    esperado = sorted(["057e:2009", "054c:05c4"]) if externos else []
    assert all(sorted(i) == esperado for i in inventarios), inventarios[:3]
    if externos:
        assert len(numeros_do_pro) == 30
        assert isinstance(numeros_do_pro[0], int), numeros_do_pro[:3]
        assert set(numeros_do_pro) == {numeros_do_pro[0]}, "o número do Pro andou"
        assert tique._registry.peek(MAC_PRO.replace(":", "")) == numeros_do_pro[0]


# --- R2, o oráculo ----------------------------------------------------------


@pytest.mark.parametrize(("nome", "escondidos", "externos"), _MATRIZ)
def test_r2_o_inventario_sai_identico_ao_de_hoje(
    montar: Any, nome: str, escondidos: bool, externos: bool
) -> None:
    """Os mesmos dicts, na mesma ordem. O 8BitDo em modo PS4 é Sony e
    continua externo. A MORDIDA: pule pelo vendor 054c só e ele some."""
    mesa = montar(MESAS[nome], escondidos=escondidos, externos=externos)

    hoje = _vista_de_hoje()
    agora = er.discover_external_gamepads()

    assert agora == hoje
    esperado = ["057e:2009", "054c:05c4"] if externos else []
    assert _vidpids(agora) == esperado
    if externos:
        assert agora[0]["evdev_path"] == mesa.caminho[
            next(e for e, no in mesa.nos.items() if no.vendor == 0x057E)
        ]
        assert agora[0]["driver"] == "nintendo"
        assert agora[0]["hidraw"] is not None


def test_r2_especie_desconhecida_e_recusada(montar: Any) -> None:
    """Uma espécie com erro de digitação não vira lista vazia calada — uma
    lista vazia no tique contaria ausência e tiraria o número do externo."""
    montar(MESAS["1-bt"], escondidos=True, externos=True)
    with pytest.raises(ValueError, match="espécie"):
        er.discover_gamepads(especie="externo")


# --- R3, na dúvida o nó é aberto --------------------------------------------


@pytest.mark.parametrize("escondidos", [True, False], ids=["escondidos", "abertos"])
def test_r3_o_externo_de_sysfs_ilegivel_continua_no_inventario(
    montar: Any, escondidos: bool
) -> None:
    """O sysfs que não se lê não esconde ninguém. A MORDIDA: trate o
    ilegível como DualSense e o Pro some."""
    mesa = montar(MESAS["4-misto"], escondidos=escondidos, externos=True)
    pro = mesa.caminho[next(e for e, no in mesa.nos.items()
                            if no.vendor == 0x057E and no.papel == "gamepad")]
    mesa.sysfs_ilegivel(pro)

    inventario = er.discover_external_gamepads()

    assert pro in [e["evdev_path"] for e in inventario]
    assert mesa.tentativas_em_dualsense() == [], "o pulo segue valendo para os DualSense"
    assert mesa.pedidos == []
    assert inventario == _vista_de_hoje()


@pytest.mark.parametrize("escondidos", [True, False], ids=["escondidos", "abertos"])
def test_r3_o_dualsense_de_sysfs_ilegivel_e_tratado_como_hoje(
    montar: Any, escondidos: bool
) -> None:
    """Sem o sysfs, o nó do P1 é aberto e descartado — o mesmo número de
    tentativas nele que a vista de hoje faz, e nenhum pedido ao broker."""
    mesa = montar(MESAS["4-misto"], escondidos=escondidos, externos=True)
    p1 = mesa.de(1)
    mesa.sysfs_ilegivel(p1)

    hoje = _vista_de_hoje()
    tentativas_de_hoje = mesa.tentativas.count(p1)
    pedidos_de_hoje = mesa.pedidos_de_open().count(p1)
    agora = er.discover_external_gamepads()
    tentativas_agora = mesa.tentativas.count(p1) - tentativas_de_hoje

    assert agora == hoje
    assert p1 not in [e["evdev_path"] for e in agora]
    assert tentativas_agora == tentativas_de_hoje == (0 if escondidos else 1)
    assert pedidos_de_hoje == 0
    assert mesa.pedidos_de_open().count(p1) == 0


# --- R4, quem quer o DualSense continua achando -----------------------------


@pytest.mark.parametrize("nome", ["3-misto", "4-misto"])
@pytest.mark.parametrize("escondidos", [True, False], ids=["escondidos", "abertos"])
def test_r4_localizar_o_p3_pela_identidade_continua_pedindo_ao_broker(
    montar: Any, nome: str, escondidos: bool
) -> None:
    """O leitor que perdeu o nó do P3 o reencontra pela identidade. A
    MORDIDA: aplique o pulo sem olhar a espécie e o P3 some daqui."""
    mesa = montar(MESAS[nome], escondidos=escondidos, externos=True)

    no = er.localizar_node_por_identidade(mac_ds(3).replace(":", ""))

    assert no == Path(mesa.de(3))
    if escondidos:
        assert mesa.de(3) in mesa.pedidos_de_open()
        assert mesa.de(3) in [kw["node"] for kw in mesa.fd_recebidos()]


# --- R5, a suíte não lê o sysfs dela ----------------------------------------


def test_r5_sob_teste_o_sysfs_dos_nos_de_entrada_e_uma_pasta_vazia(tmp_path: Path) -> None:
    """O `tests/conftest.py` aponta o `SYS_CLASS_INPUT` para uma pasta vazia,
    nova a cada teste. Na máquina dela o `event30` é o movimento do P1: sob
    teste, o sysfs não sabe dele. A MORDIDA: tire a linha do conftest e esta
    régua reprova em qualquer máquina."""
    raiz = Path(er.SYS_CLASS_INPUT)

    assert er.SYS_CLASS_INPUT != "/sys/class/input"
    assert raiz.is_dir()
    assert list(raiz.iterdir()) == []
    assert raiz.is_relative_to(tmp_path)
    assert er._no_de_dualsense_no_sysfs("/dev/input/event30") is False
