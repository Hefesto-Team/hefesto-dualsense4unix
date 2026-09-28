"""A-DESCOBERTA-LE-O-SYSFS-E-NAO-ABRE-O-NO-01 — a descoberta não abre o nó.

O que o diário de 26/09 mediu (o `journalctl` do daemon, relido em 28/09):

- das 7h52 às 10h42, com o controle de acelerômetro desligado (perfil
  Freestyle) fora da mesa, o daemon pediu ao broker o nó de movimento dos
  OUTROS dois controles a cada 5,30 s (mediana), 1.924 vezes em cada nó. É o
  leitor de movimento do ausente — que o hub mantém vivo por causa do
  sensor desligado — repetindo a descoberta no recuo que para em 5 s;
- das 10h43 às 11h49, depois do reinício do daemon, os mesmos dois nós a cada
  1,28 s (mediana), 2.851 vezes em cada um: não havia leitor do ausente, e o
  hub repetia a descoberta a cada volta de manutenção (1 s mais a volta) para
  achar a peça com o sensor desligado. É a «rajada das 11h45» da sprint, e ela
  começou às 10h43;
- das 16h16 às 18h23, o primeiro laço de novo, 1.444 vezes num dos nós.

Cada descoberta abria cada nó auxiliar de cada controle, pelo broker, só para
ler vendor, product, nome e endereço — que o sysfs publica sem abrir nada.

As réguas, com a Mesa de mentira (quatro controles, um vpad, os nós do físico
fechados como o `0600 root` e o socket do broker de pé):

1. a descoberta devolve os quatro endereços com ZERO `open` — nem pelo
   caminho, nem pelo broker. MORDIDA: devolva o `abrir_input_device` à
   descoberta e a conta passa de zero;
2. o leitor de um endereço ausente, com o aviso de `/dev/input` parado, faz no
   máximo UMA descoberta em 30 s; com o aviso disparado, descobre na hora;
3. o hub, com o sensor desligado de uma peça fora da mesa, só procura de novo
   quando `/dev/input` muda.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("evdev")

from hefesto_dualsense4unix.core import evdev_reader as er
from tests.unit.sysfs_de_entrada_de_mentira import publicar_no

#: Quatro controles de mentira (a faixa forjada da casa), um em cada lugar da
#: mesa, dois no cabo e dois no rádio — nunca só o P1.
CONTROLES = (
    ("aa:bb:cc:00:00:01", 0x03),
    ("aa:bb:cc:00:00:02", 0x03),
    ("aa:bb:cc:00:00:03", 0x05),
    ("aa:bb:cc:00:00:04", 0x05),
)
NOMES = {
    "gamepad": "DualSense Wireless Controller",
    "Motion Sensors": "DualSense Wireless Controller Motion Sensors",
    "Touchpad": "DualSense Wireless Controller Touchpad",
}
#: O vpad do próprio daemon: os mesmos nomes, o MAC forjado `02:fe`, e a
#: morada de `/devices/virtual/misc/uhid/`. Adotá-lo seria o daemon lendo a
#: própria saída.
VPAD = "02:fe:00:00:00:01"


class Mesa:
    """A mesa de mentira: sysfs, `/dev/input` e o contador de toda abertura."""

    def __init__(self, raiz: Path) -> None:
        self.sys = raiz / "sys-class-input"
        self.dev = raiz / "dev-input"
        self.devices = raiz / "devices"
        self.sys.mkdir()
        self.dev.mkdir()
        #: `/dev/input/eventN` -> (nome, uniq, bus) — o que o nó publica.
        self.nos: dict[str, tuple[str, str, int]] = {}
        #: Morada real de cada nó, para o `_is_virtual_evdev`.
        self.moradas: dict[str, str] = {}
        #: Toda abertura, venha de onde vier.
        self.aberturas: list[str] = []
        self.pedidos_ao_broker: list[str] = []
        numero = 9101
        for uniq, bus in CONTROLES:
            for nome in NOMES.values():
                self.acrescentar(f"event{numero}", nome, uniq, bus)
                numero += 1
        for nome in NOMES.values():
            self.acrescentar(f"event{numero}", nome, VPAD, 0x05, virtual=True)
            numero += 1

    def acrescentar(
        self, evento: str, nome: str, uniq: str, bus: int, *, virtual: bool = False
    ) -> str:
        caminho = str(self.dev / evento)
        publicar_no(self.sys, caminho, nome=nome, uniq=uniq, bus=bus)
        morada = (
            self.devices / "virtual" / "misc" / "uhid" / "0005:054C:0CE6.0099" / evento
            if virtual
            else self.devices / "pci0000:00" / evento
        )
        morada.mkdir(parents=True)
        (morada / "uniq").write_text(uniq + "\n", encoding="ascii")
        (morada / "phys").write_text("\n", encoding="ascii")
        self.moradas[f"/sys/class/input/{evento}/device"] = str(morada)
        no = Path(caminho)
        no.write_text("", encoding="ascii")
        no.chmod(0o000)  # o `0600 root` do físico, visto por ela
        self.nos[caminho] = (nome, uniq, bus)
        return caminho

    def remover(self, uniq: str) -> None:
        """O controle saiu da mesa: os três nós somem do sysfs e do `/dev`."""
        for caminho, (_nome, dono, _bus) in list(self.nos.items()):
            if dono != uniq:
                continue
            evento = Path(caminho).name
            for arquivo in sorted((self.sys / evento).rglob("*"), reverse=True):
                arquivo.unlink() if arquivo.is_file() else arquivo.rmdir()
            (self.sys / evento).rmdir()
            Path(caminho).unlink()
            del self.nos[caminho]

    def abrir(self, caminho: Any, **_kw: Any) -> Any:
        """O dublê do `abrir_input_device`: publica o que o real publica."""
        self.aberturas.append(str(caminho))
        nome, uniq, bus = self.nos[str(caminho)]
        return SimpleNamespace(
            info=SimpleNamespace(vendor=0x054C, product=0x0CE6, bustype=bus),
            name=nome,
            uniq=uniq,
            path=str(caminho),
            close=lambda: None,
        )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Mesa:
    if os.geteuid() == 0:  # pragma: no cover - como root o 0000 não fecha nada
        pytest.skip("como root todo nó abre")
    m = Mesa(tmp_path)
    monkeypatch.setattr(er, "SYS_CLASS_INPUT", str(m.sys))
    monkeypatch.setattr(er, "DEV_INPUT_DIR", str(m.dev))
    socket_do_broker = tmp_path / "broker.sock"
    socket_do_broker.write_text("", encoding="ascii")
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(socket_do_broker))

    # O `list_devices` da BIBLIOTECA: só o nó que o processo abre. Os do
    # físico estão fechados, e só entram pelo `_nos_de_evento` com o broker.
    def listar(*_a: Any) -> list[str]:
        return [str(c) for c in sorted(m.dev.glob("event*")) if os.access(c, os.R_OK | os.W_OK)]

    monkeypatch.setattr("evdev.list_devices", listar)

    real = os.path.realpath

    def morada(caminho: Any, *a: Any, **kw: Any) -> str:
        return m.moradas.get(str(caminho)) or real(caminho, *a, **kw)

    monkeypatch.setattr("os.path.realpath", morada)

    def input_device(caminho: Any, *_a: Any, **_kw: Any) -> Any:
        m.aberturas.append(str(caminho))
        raise PermissionError(errno.EACCES, "Permission denied", str(caminho))

    def broker(caminho: str) -> int | None:
        m.pedidos_ao_broker.append(caminho)
        return None

    monkeypatch.setattr("evdev.InputDevice", input_device)
    monkeypatch.setattr(er, "_ABRIDOR_DO_BROKER", broker)
    monkeypatch.setattr(er, "abrir_input_device", m.abrir)
    return m


# ---------------------------------------------------------------------------
# 1. A descoberta lê o sysfs e não abre o nó
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("marcador", "descobre"),
    [
        ("Motion Sensors", er.discover_dualsense_motion_evdevs),
        ("Touchpad", er.discover_dualsense_touchpad_evdevs),
    ],
)
def test_a_descoberta_devolve_os_quatro_sem_abrir_nada(
    mesa: Mesa, marcador: str, descobre: Any
) -> None:
    """Os quatro endereços, cabo e rádio, e nenhum `open`.

    **A MORDIDA:** devolva o `abrir_input_device` à descoberta (o laço de
    antes de 28/09) e a conta passa de zero — doze aberturas por volta com
    quatro controles, e o broker pedido para cada nó auxiliar fechado.
    """
    achados = descobre()

    esperado = {
        uniq.replace(":", ""): Path(caminho)
        for caminho, (nome, uniq, _bus) in mesa.nos.items()
        if nome == NOMES[marcador] and uniq != VPAD
    }
    assert len(esperado) == 4
    assert achados == esperado, f"a descoberta do nó «{marcador}» não achou os quatro"
    assert mesa.aberturas == [], (
        f"a descoberta abriu {len(mesa.aberturas)} nó(s) para ler o que o sysfs "
        "já publica"
    )
    assert mesa.pedidos_ao_broker == [], "a descoberta pediu nó ao broker"


def test_o_vpad_do_daemon_fica_de_fora(mesa: Mesa) -> None:
    """Os nós do vpad têm os MESMOS nomes: quem os separa é a morada e o `02:fe`."""
    achados = er.discover_dualsense_motion_evdevs()
    assert VPAD.replace(":", "") not in achados


def test_o_no_fechado_sem_broker_fica_de_fora(
    mesa: Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem o socket do broker, o nó fechado não tem porta: não entra no mapa.

    A descoberta continua devolvendo só o nó que alguém pode abrir depois, como
    antes — o `_nos_de_evento` é quem decide a lista, não o sysfs.
    """
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(tmp_path / "nao-ha.sock"))
    assert er.discover_dualsense_motion_evdevs() == {}
    assert mesa.aberturas == []


def test_o_controle_que_saiu_nao_aparece(mesa: Mesa) -> None:
    mesa.remover("aa:bb:cc:00:00:02")
    achados = er.discover_dualsense_motion_evdevs()
    assert set(achados) == {"aabbcc000001", "aabbcc000003", "aabbcc000004"}
    assert mesa.aberturas == []
