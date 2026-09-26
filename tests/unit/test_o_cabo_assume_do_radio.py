"""O-CABO-ASSUME-DO-RADIO-01 — o controle do rádio que ganha cabo passa para o cabo.

Ela, 25/09/2026: plugou no USB um controle que estava pelo rádio, e ele
*«segue conectado no modo bt mas agora segue carregando»*. A decisão dela:
**passa para o cabo**, com o mesmo número e sem o jogo perder o controle; tirou
o cabo, volta pelo rádio. <!-- noqa-acento: citação literal dela -->

O QUE FOI MEDIDO ANTES DA CURA (e que esta régua reproduz)
=========================================================

Na mesa dela, 19:42 de 25/09, o kernel recusou o HID do cabo::

    playstation 0003:054C:0CE6.001B: Duplicate device found for MAC address …
    playstation 0003:054C:0CE6.001B: probe with driver playstation failed with error -17

e o ``connect()`` real, com a enumeração do kernel, ficou no rádio. Mais duas
camadas, medidas no caminho real do backend: com os DOIS nós visíveis ele
ficava com o que o hidapi listasse primeiro, e com o rádio saindo e o cabo
entrando num tique só ele ficava com o handle do nó MORTO do rádio.

A BANCADA
=========

Código de produto de verdade: o ``PyDualSenseController`` (``connect``,
``read_state``, ``describe_controllers``, a eleição do primário), o
``CoopManager`` (``sync``/``forward_all``), o ``ControllerIdentityRegistry``
(o número que a tela mostra), o ``vigiar_o_cabo_em_espera`` e o
``reconnect_loop`` do daemon.

Os dublês, e por que nenhum é mais frouxo que o real:

- :class:`Kernel` é o ``hid-playstation``: um aparelho HID por conexão, e a
  RECUSA por endereço repetido (``-EEXIST``) com a linha no diário. O cabo
  recusado fica no barramento HID sem driver (uma pasta de verdade, que o
  produto lê com ``os.listdir``) e sem nó nenhum. A regra 85 só roda se estiver
  "instalada", e só na SAÍDA de um físico;
- :class:`_LeitorQueSegueOMac` é o ``EvdevReader`` do co-op: perde o nó quando
  ele some, procura o controle pelo MAC, e o grab é exclusivo (``EBUSY``) —
  ele reabre no tique seguinte ou no ``request_reopen``, nunca antes;
- :class:`BlueZ` só sabe ``aparelhos()`` e ``desconectar()``: o esquecimento
  (``RemoveDevice``) nem existe nele, e a régua estouraria se o produto o
  pedisse.

O nó hidraw da bancada não mora em ``/dev``: o ``hidraw_path`` do produto só
devolve ``/dev/hidraw*``, e assim nenhum leitor de movimento, broker ou vpad
uhid abre um nó da mesa dela.

AS MORDIDAS (25/09/2026, cada uma devolvida com o md5 conferido) estão no fim
da sprint, em «O que foi feito».

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import (
    FOLGA_DEPOIS_DA_TROCA_S,
    PRAZO_DA_TROCA_DE_TRANSPORTE_S,
    PyDualSenseController,
)
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon import connection as conn_mod
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.integrations import o_cabo_em_espera as oce
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    JogoPorFora,
    Relogio,
    _LeitorDoP1,
    _VpadDaMesa,
    config_isolado,
)

RAIZ = Path(__file__).resolve().parents[2]
REGRA = RAIZ / "assets" / "85-hefesto-o-cabo-assume.rules"

#: A mesa de quatro. Faixa forjada, octetos 4 e 5 zerados.
MACS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
UNIQS = tuple(m.replace(":", "") for m in MACS)
MAC_DE = dict(zip(UNIQS, MACS, strict=True))

#: O tique lento da casa (o `sync` do co-op, o registro de identidade).
TIQUE = 2.0

#: O `derrubar_o_radio` do produto, guardado antes de qualquer monkeypatch.
_DERRUBAR_REAL = oce.derrubar_o_radio


# ---------------------------------------------------------------------------
# O mundo: o kernel, o BlueZ, os leitores e os handles
# ---------------------------------------------------------------------------


class Kernel:
    """O ``hid-playstation`` da mesa: um aparelho por conexão, e a recusa por endereço."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        raiz.mkdir(parents=True, exist_ok=True)
        #: instância -> {uniq, barramento, preso, evdev, hidraw}
        self.aparelhos: dict[str, dict[str, Any]] = {}
        #: a `ps_devices_list`: uniq -> a instância que segura o endereço.
        self.presos: dict[str, str] = {}
        self.diario: list[str] = []
        self.dono_do_grab: dict[str, str] = {}
        self.ebusy: list[str] = []
        self.regra_instalada = True
        #: a probe da regra 85 só acontece depois do próximo `connect()` — o vão
        #: em que o controle está fora da mesa, que o tique VÊ.
        self.regra_atrasa = False
        self._probes_pendentes = False
        #: o handle só percebe que o aparelho saiu na volta seguinte (o
        #: `report_thread` da pydualsense vira `connected=False` no erro de
        #: leitura seguinte). `False` = percebe na hora.
        self.handles_atrasam = False
        self.nao_percebidos: set[str] = set()
        #: quem está com energia de fora (o cabo no PC ou numa tomada).
        self.na_tomada: set[str] = set()
        self._seq = 0x20
        self._evento = 40
        self._hidraw = 20

    # -- o mundo muda -----------------------------------------------------

    def conectar(self, uniq: str, barramento: str) -> str:
        pid_bus = "0003" if barramento == "usb" else "0005"
        inst = f"{pid_bus}:054C:0CE6.{self._seq:04X}"
        self._seq += 1
        (self.raiz / inst).mkdir()
        self.aparelhos[inst] = {
            "uniq": uniq, "barramento": barramento, "preso": False, "evdev": None, "hidraw": None,
        }
        if barramento == "usb":
            self.na_tomada.add(uniq)
        self._probe(inst)
        return inst

    def desconectar(self, inst: str) -> None:
        ap = self.aparelhos.pop(inst)
        if ap["preso"]:
            self.presos.pop(ap["uniq"], None)
            self.dono_do_grab.pop(ap["evdev"], None)
            (self.raiz / inst / "driver").unlink()
        (self.raiz / inst).rmdir()
        if ap["barramento"] == "usb":
            self.na_tomada.discard(ap["uniq"])
        if self.handles_atrasam:
            self.nao_percebidos.add(inst)
        if self.regra_instalada:
            if self.regra_atrasa:
                self._probes_pendentes = True
            else:
                self.regra_85()

    def regra_85(self) -> None:
        """O `drivers_probe` de todo DualSense sem driver (o que a regra faz)."""
        for inst, ap in list(self.aparelhos.items()):
            if not ap["preso"]:
                self._probe(inst)

    def a_regra_atrasada_roda(self) -> None:
        if self._probes_pendentes:
            self._probes_pendentes = False
            self.regra_85()

    def os_handles_percebem(self) -> None:
        self.nao_percebidos.clear()

    def _probe(self, inst: str) -> None:
        ap = self.aparelhos[inst]
        if ap["uniq"] in self.presos:
            mac = MAC_DE[ap["uniq"]]
            self.diario.append(f"playstation {inst}: Duplicate device found for MAC address {mac}.")
            self.diario.append(
                f"playstation {inst}: probe with driver playstation failed with error -17"
            )
            return
        ap["preso"] = True
        self.presos[ap["uniq"]] = inst
        (self.raiz / inst / "driver").write_text("playstation", encoding="utf-8")
        ap["evdev"] = f"/dev/input/event{self._evento}"
        ap["hidraw"] = f"/bancada/hidraw{self._hidraw}".encode()
        self._evento += 1
        self._hidraw += 1

    # -- o que o produto lê ------------------------------------------------

    @property
    def nodes(self) -> dict[str, str]:
        """uniq -> nó evdev de quem tem driver — o que o `discover_dualsense_evdevs` vê."""
        return {ap["uniq"]: ap["evdev"] for ap in self.aparelhos.values() if ap["preso"]}

    def como_o_hidapi_ve(self) -> list[tuple[str, bytes, bool]]:
        return [
            (MAC_DE[ap["uniq"]], ap["hidraw"], False)
            for ap in self.aparelhos.values()
            if ap["preso"]
        ]

    def como_o_coop_ve(self) -> dict[str, Path]:
        return {uniq: Path(no) for uniq, no in self.nodes.items()}

    def aparelho_do_hidraw(self, path: bytes) -> tuple[str, dict[str, Any]]:
        for inst, ap in self.aparelhos.items():
            if ap["hidraw"] == path:
                return inst, ap
        raise AssertionError(f"o produto abriu {path!r}, que não existe")

    def instancia(self, uniq: str, barramento: str) -> str | None:
        for inst, ap in self.aparelhos.items():
            if ap["uniq"] == uniq and ap["barramento"] == barramento:
                return inst
        return None

    def grab(self, node: str, quem: str) -> bool:
        dono = self.dono_do_grab.get(node)
        if dono is not None and dono != quem:
            self.ebusy.append(f"EBUSY em {node}: '{quem}' pediu, '{dono}' segurava")
            return False
        self.dono_do_grab[node] = quem
        return True

    def ungrab(self, node: str | None, quem: str) -> None:
        if node is not None and self.dono_do_grab.get(node) == quem:
            del self.dono_do_grab[node]


class _Handle:
    """O handle pydualsense: o nó que ele abriu, o transporte e a carga que o report diz."""

    def __init__(self, kernel: Kernel, path: bytes) -> None:
        self._kernel = kernel
        self._pinned_path = path
        self._inst, ap = kernel.aparelho_do_hidraw(path)
        self._uniq = ap["uniq"]
        self.conType = SimpleNamespace(name=ap["barramento"].upper())
        self.closed = False
        self.state = SimpleNamespace()

    @property
    def connected(self) -> bool:
        if self.closed:
            return False
        return self._inst in self._kernel.aparelhos or self._inst in self._kernel.nao_percebidos

    @property
    def battery(self) -> SimpleNamespace:
        # nibble alto do byte de bateria: 0x0 descarregando, 0x1 carregando.
        return SimpleNamespace(Level=55, State=1 if self._uniq in self._kernel.na_tomada else 0)

    def close(self) -> None:
        self.closed = True


class _LeitorQueSegueOMac:
    """O `EvdevReader` de um jogador do co-op, com o reencontro pelo MAC do real."""

    kernel: ClassVar[Kernel | None] = None
    vivos: ClassVar[list[_LeitorQueSegueOMac]] = []

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.target_uniq = target_uniq
        self.node: str | None = str(device_path) if device_path is not None else None
        self._quer_grab = False
        self.grab_state = "off"
        self.stopped = False
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0, buttons_pressed=frozenset()
        )
        type(self).vivos.append(self)

    @property
    def _k(self) -> Kernel:
        kernel = type(self).kernel
        assert kernel is not None
        return kernel

    @property
    def _quem(self) -> str:
        return f"coop:{self.target_uniq}"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self._quer_grab = grab
        if not grab:
            self._k.ungrab(self.node, self._quem)
            self.grab_state = "off"
            return True
        if self.node is None:
            self.grab_state = "pending"
            return True
        if not self._k.grab(self.node, self._quem):
            self.grab_state = "failed"
            return False
        self.grab_state = "held"
        return True

    def stop(self) -> None:
        self._k.ungrab(self.node, self._quem)
        self.stopped = True

    def request_reopen(self, reason: str = "") -> None:
        self._reabrir()

    def a_thread_anda(self) -> None:
        """Uma volta da thread do leitor: o nó que sumiu é largado, e o do MAC é procurado."""
        if self.stopped:
            return
        if self.node is not None and self.node not in self._k.nodes.values():
            self.node = None
            if self._quer_grab:
                self.grab_state = "pending"
        if self.node is None:
            self._reabrir()

    def _reabrir(self) -> None:
        novo = self._k.nodes.get(self.target_uniq or "")
        if novo == self.node:
            return
        self._k.ungrab(self.node, self._quem)
        self.node = novo
        if novo is None:
            if self._quer_grab:
                self.grab_state = "pending"
            return
        if self._quer_grab:
            self.grab_state = "held" if self._k.grab(novo, self._quem) else "failed"

    def snapshot(self) -> Any:
        return self.snap


class BlueZ:
    """O dono do BlueZ: lista os aparelhos ligados e derruba a conexão. Esquecer não existe."""

    def __init__(self, kernel: Kernel) -> None:
        self.kernel = kernel
        self.desconectados: list[str] = []

    def aparelhos(self) -> tuple[SimpleNamespace, ...]:
        return tuple(
            SimpleNamespace(
                caminho="/org/bluez/hci0/dev_" + MAC_DE[ap["uniq"]].upper().replace(":", "_"),
                endereco=MAC_DE[ap["uniq"]],
                conectado=True,
            )
            for ap in self.kernel.aparelhos.values()
            if ap["barramento"] == "bt"
        )

    def desconectar(self, caminho: str, *, quem: str) -> SimpleNamespace:
        assert quem == oce.QUEM
        mac = caminho.rsplit("dev_", 1)[1].replace("_", ":").lower()
        uniq = mac.replace(":", "")
        inst = self.kernel.instancia(uniq, "bt")
        assert inst is not None, f"o produto derrubou o rádio de {mac}, que não está no rádio"
        self.desconectados.append(uniq)
        self.kernel.desconectar(inst)
        return SimpleNamespace(feita=True, erro="", mensagem="")


def _connect_na_mesa(inst: PyDualSenseController, kernel: Kernel) -> None:
    """O `connect()` real com a enumeração e a abertura vindas do :class:`Kernel`."""
    with patch.object(
        PyDualSenseController,
        "_enumerate_device_keys",
        return_value=kernel.como_o_hidapi_ve(),
    ), patch.object(
        PyDualSenseController,
        "_open_one",
        side_effect=lambda path, *, is_edge: _Handle(kernel, path),
    ):
        inst.connect()


# ---------------------------------------------------------------------------
# A mesa: o backend, o co-op, o registro e o laço do cabo, de verdade
# ---------------------------------------------------------------------------


class MesaDoCabo:
    """Backend real + co-op real + registro real + o vigia do cabo, sobre o :class:`Kernel`."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        *,
        coop: bool = True,
        jogo: bool = True,
        mascara: str = "dualsense",
        diario_legivel: bool = True,
        regra_instalada: bool = True,
    ) -> None:
        self.relogio = Relogio()
        self.kernel = Kernel(tmp_path / "sys-bus-hid-devices")
        self.kernel.regra_instalada = regra_instalada
        self.bluez = BlueZ(self.kernel)
        self.diario_legivel = diario_legivel
        self.nativo = False
        regra = tmp_path / "rules.d" / oce.NOME_DA_REGRA
        if regra_instalada:
            regra.parent.mkdir(parents=True, exist_ok=True)
            regra.write_text("", encoding="utf-8")
        monkeypatch.setattr(oce, "RAIZ_DO_BARRAMENTO_HID", str(self.kernel.raiz))
        monkeypatch.setattr(oce, "REGRAS_QUE_RELIGAM", (str(regra),))

        self.leitor_p1 = _LeitorDoP1(self.kernel)  # type: ignore[arg-type]
        self.inst = PyDualSenseController(evdev_reader=self.leitor_p1)  # type: ignore[arg-type]
        self.inst._relogio = self.relogio
        self.inst.read_calibration = lambda _uniq=None: None  # type: ignore[assignment]
        self.reg = ControllerIdentityRegistry(clock=self.relogio)
        self.jogo = JogoPorFora(
            lambda: getattr(getattr(self, "daemon", None), "display_authority", None) == "game"
        )
        self.vpad_do_p1 = _VpadDaMesa(1, self.jogo)
        self.vpad_do_p1.flavor = mascara
        self.vpads: list[Any] = [self.vpad_do_p1]
        self.daemon = SimpleNamespace(
            config=DaemonConfig(coop_enabled=coop, gamepad_flavor=mascara),
            _gamepad_device=self.vpad_do_p1,
            controller=self.inst,
            _coop_manager=None,
            identity_registry=self.reg,
            display_authority="game" if jogo else "daemon",
            _last_auto_mult=0.7,
            _last_auto_change_at=0.0,
            is_native_mode=lambda: self.nativo,
        )
        self.coop = CoopManager(self.daemon)  # type: ignore[arg-type]
        self.daemon._coop_manager = self.coop
        _LeitorQueSegueOMac.kernel = self.kernel
        _LeitorQueSegueOMac.vivos = []
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorQueSegueOMac
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            self.kernel.como_o_coop_ve,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda _self: True
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", self._nascer_vpad
        )
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})

    def _nascer_vpad(
        self, flavor: Any, *, player: int = 1, identity: str | None = None, **_kw: Any
    ) -> Any:
        vpad = _VpadDaMesa(player, self.jogo)
        vpad.mac = vpad_mac(identity, player)
        vpad.identidade = identity  # type: ignore[attr-defined]
        vpad.flavor = flavor
        self.vpads.append(vpad)
        return vpad

    def ler_o_diario(self) -> str | None:
        return "\n".join(self.kernel.diario) if self.diario_legivel else None

    # -- os laços do daemon, na ordem do `reconnect_loop` ---------------------

    def connect(self) -> None:
        _connect_na_mesa(self.inst, self.kernel)

    def tique(self, segundos: float = TIQUE) -> None:
        self.relogio.avancar(segundos)
        self.kernel.os_handles_percebem()
        self.connect()
        # A probe atrasada da regra 85 cai DEPOIS deste `connect()`: ele viu o
        # controle fora da mesa, que é o vão que esta bancada quer medir.
        self.kernel.a_regra_atrasada_roda()
        asyncio.run(
            conn_mod.vigiar_o_cabo_em_espera(
                self.daemon,  # type: ignore[arg-type]
                agora=self.relogio.t,
                leitor_do_bluez=self.bluez,
                ler_o_diario=self.ler_o_diario,
            )
        )
        self.inst.read_state()
        self.reg.sync_connected(
            [u for u in self.inst.alvos_conectados().values() if isinstance(u, str)]
        )
        for leitor in list(_LeitorQueSegueOMac.vivos):
            leitor.a_thread_anda()
        self.coop.sync()
        self.coop.forward_all()
        self.coop.forward_all()
        self.conferir_invariantes()

    def conferir_invariantes(self) -> None:
        assert not self.kernel.ebusy, "; ".join(self.kernel.ebusy)
        macs = [v.mac for v in self.vpads if getattr(v, "vivo", False)]
        assert len(macs) == len(set(macs)), f"dois vpads vivos com o mesmo MAC: {macs}"

    # -- a leitura ------------------------------------------------------------

    def transporte_de(self, uniq: str) -> str | None:
        for item in self.inst.describe_controllers():
            if item.get("uniq") == uniq and item.get("connected"):
                return str(item["transport"])
        return None

    def numeros(self) -> dict[str, int]:
        return self.reg.numeros_da_mesa()

    def boneco_de(self, uniq: str) -> Any:
        """O vpad que alimenta o jogador deste controle: o do P1 ou o do co-op."""
        if self.inst.primary_uniq == uniq:
            return self.daemon._gamepad_device
        jogador = self.coop._players.get(uniq)
        return jogador.vpad if jogador is not None else None

    def dono_do_vpad_do_p1(self) -> str | None:
        from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once

        metades = (self.inst.read_state().buttons_pressed, evdev_buttons_once(self.daemon))
        donos = {b[3:] for metade in metades for b in metade if b.startswith("de:")}
        assert len(donos) <= 1, f"o vpad do P1 recebe de dois controles: {donos}"
        return next(iter(donos), None)

    def o_jogo_ve(self) -> dict[int, int]:
        """Lugar do jogo -> id do vpad naquele lugar (o que o jogo enxerga por fora)."""
        return {lugar: id(v) for lugar, v in self.jogo.ve()[1].items()}

    def mortes_de_vpad(self) -> int:
        return sum(1 for v in self.vpads if not getattr(v, "vivo", True))


def montar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transportes: tuple[str, ...],
    *,
    na_tomada: frozenset[str] = frozenset(),
    **opcoes: Any,
) -> MesaDoCabo:
    """A mesa na ordem, um controle por tique; `na_tomada` já carregava ANTES de tudo."""
    mesa = MesaDoCabo(monkeypatch, tmp_path, **opcoes)
    mesa.kernel.na_tomada |= na_tomada
    for uniq, via in zip(UNIQS, transportes, strict=False):
        mesa.kernel.conectar(uniq, via)
        mesa.tique()
    for _ in range(3):
        mesa.tique()
    assert mesa.inst.primary_uniq == UNIQS[0]
    assert mesa.numeros() == {UNIQS[n]: n + 1 for n in range(len(transportes))}
    return mesa


def plugar_o_cabo_e_esperar(
    mesa: MesaDoCabo, uniq: str, *, tiques: int = 4
) -> list[dict[str, Any]]:
    """O gesto dela: o cabo no controle que está no rádio. Devolve a foto de cada tique."""
    mesa.kernel.conectar(uniq, "usb")
    fotos: list[dict[str, Any]] = []
    for _ in range(tiques):
        mesa.tique()
        fotos.append(
            {
                "numeros": mesa.numeros(),
                "jogo": mesa.o_jogo_ve(),
                "primario": mesa.inst.primary_uniq,
            }
        )
    return fotos


# ---------------------------------------------------------------------------
# A matriz: de 1 a 4 jogadores, o controle em qualquer lugar, rádio e misto
# ---------------------------------------------------------------------------

OUTROS = {
    "todos-no-radio": ("bt", "bt", "bt", "bt"),
    "mesa-mista": ("usb", "bt", "usb", "bt"),
}
POSICOES = [(n, p, o) for n in (1, 2, 3, 4) for p in range(n) for o in OUTROS]
MATRIZ = pytest.mark.parametrize(
    ("quantos", "posicao", "outros"),
    POSICOES,
    ids=[f"{n}-jogadores-P{p + 1}-{o}" for n, p, o in POSICOES],
)


def _transportes(quantos: int, posicao: int, outros: str) -> tuple[str, ...]:
    """A mesa com o controle da `posicao` no RÁDIO (é o caso dela) e os outros como a matriz diz."""
    base = list(OUTROS[outros][:quantos])
    base[posicao] = "bt"
    return tuple(base)


@pytest.mark.usefixtures("config_isolado")
class TestOCaboAssume:
    """A decisão dela: o cabo assume, o número fica, o boneco do jogo não cai."""

    @MATRIZ
    @pytest.mark.parametrize("vao", [False, True], ids=["num-tique", "com-vao"])
    @pytest.mark.parametrize(
        ("coop", "jogo"),
        [(True, True), (True, False), (False, True)],
        ids=["co-op-com-jogo", "co-op-sem-jogo", "sem-co-op"],
    )
    def test_o_cabo_assume_com_o_mesmo_numero_e_o_mesmo_boneco(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        quantos: int,
        posicao: int,
        outros: str,
        vao: bool,
        coop: bool,
        jogo: bool,
    ) -> None:
        transportes = _transportes(quantos, posicao, outros)
        mesa = montar(monkeypatch, tmp_path, transportes, coop=coop, jogo=jogo)
        mesa.kernel.regra_atrasa = vao
        alvo = UNIQS[posicao]
        numeros_antes = mesa.numeros()
        bonecos_antes = {u: mesa.boneco_de(u) for u in numeros_antes}
        jogo_antes = mesa.o_jogo_ve()
        mortes_antes = mesa.mortes_de_vpad()

        fotos = plugar_o_cabo_e_esperar(mesa, alvo)

        # A MORDIDA PRINCIPAL: a escolha de antes (o rádio fica) reprova aqui.
        assert mesa.transporte_de(alvo) == "usb", (
            f"o controle {posicao + 1} continua no {mesa.transporte_de(alvo)} com o cabo "
            "plugado — o rádio devia ter saído para o cabo assumir"
        )
        assert mesa.bluez.desconectados == [alvo], (
            f"o produto derrubou o rádio de {mesa.bluez.desconectados}; só o de {alvo}"
        )
        assert mesa.numeros() == numeros_antes, "alguém trocou de número na troca de transporte"
        for uniq, boneco in bonecos_antes.items():
            assert mesa.boneco_de(uniq) is boneco, f"o boneco de {uniq} foi trocado na troca"
        assert mesa.o_jogo_ve() == jogo_antes, "o jogo viu a mesa mudar"
        assert mesa.mortes_de_vpad() == mortes_antes, "um vpad morreu na troca de transporte"
        for foto in fotos:
            # Em NENHUM instante outro controle dirige o jogador de alguém.
            assert foto["jogo"] == jogo_antes, f"no meio da troca o jogo viu {foto['jogo']}"
            # Sozinho na mesa, o vão é mesa vazia: sem posto, e sem ninguém para tomá-lo.
            assert foto["primario"] == UNIQS[0] or (quantos == 1 and foto["primario"] is None), (
                f"o posto de P1 passou para {foto['primario']} no meio da troca"
            )
            for uniq, numero in foto["numeros"].items():
                assert numero == numeros_antes[uniq], f"{uniq} mudou de número no meio da troca"
        if alvo == UNIQS[0]:
            assert mesa.dono_do_vpad_do_p1() == alvo
            assert mesa.inst.get_transport() == "usb"
        # Os outros não saíram do transporte deles.
        for n, uniq in enumerate(UNIQS[:quantos]):
            if uniq != alvo:
                assert mesa.transporte_de(uniq) == transportes[n]

    @MATRIZ
    def test_tirou_o_cabo_volta_pelo_radio_com_o_mesmo_numero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        quantos: int,
        posicao: int,
        outros: str,
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, _transportes(quantos, posicao, outros), jogo=False)
        alvo = UNIQS[posicao]
        plugar_o_cabo_e_esperar(mesa, alvo)
        # Ela joga um tempo no cabo: a folga da ida acaba antes de o cabo sair,
        # e quem segura a volta é a volta, não a sobra da ida.
        for _ in range(int(FOLGA_DEPOIS_DA_TROCA_S / TIQUE) + 1):
            mesa.tique()
        assert not mesa.inst.em_troca_de_transporte(alvo)
        numeros_antes = mesa.numeros()
        bonecos_antes = {u: mesa.boneco_de(u) for u in numeros_antes}
        jogo_antes = mesa.o_jogo_ve()

        inst = mesa.kernel.instancia(alvo, "usb")
        assert inst is not None
        mesa.kernel.desconectar(inst)  # ela tira o cabo
        mesa.tique()
        assert mesa.inst.em_troca_de_transporte(alvo), (
            "o cabo saiu de um controle que veio do rádio e o lugar dele não espera"
        )
        mesa.tique()
        assert mesa.o_jogo_ve() == jogo_antes, "o jogo perdeu o controle enquanto ele voltava"
        assert mesa.inst.primary_uniq == (None if quantos == 1 else UNIQS[0]), (
            "com o controle fora, o posto de P1 foi para outro"
        )
        mesa.kernel.conectar(alvo, "bt")  # e o controle volta sozinho pelo pareamento
        for _ in range(3):
            mesa.tique()

        assert mesa.transporte_de(alvo) == "bt"
        assert mesa.numeros() == numeros_antes
        for uniq, boneco in bonecos_antes.items():
            assert mesa.boneco_de(uniq) is boneco, f"o boneco de {uniq} foi trocado na volta"
        assert mesa.o_jogo_ve() == jogo_antes
        assert mesa.bluez.desconectados == [alvo], "a volta pelo rádio derrubou alguém"

    @pytest.mark.parametrize("mascara", ["dualsense", "xbox", "nintendo"])
    @pytest.mark.parametrize("posicao", [0, 3])
    def test_em_toda_mascara(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mascara: str, posicao: int
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "usb", "bt", "bt"), mascara=mascara)
        alvo = UNIQS[posicao]
        bonecos = {u: mesa.boneco_de(u) for u in UNIQS}
        plugar_o_cabo_e_esperar(mesa, alvo)
        assert mesa.transporte_de(alvo) == "usb"
        assert {u: mesa.boneco_de(u) for u in UNIQS} == bonecos
        assert all(getattr(b, "flavor", None) == mascara for b in bonecos.values())

    @pytest.mark.parametrize("diario_legivel", [True, False], ids=["com-diario", "sem-diario"])
    @pytest.mark.parametrize(
        ("quantos", "posicao"),
        [(1, 0), (2, 1), (4, 0), (4, 3)],
        ids=["1-jogador-P1", "2-jogadores-P2", "4-jogadores-P1", "4-jogadores-P4"],
    )
    def test_o_cabo_posto_de_novo_logo_depois_assume_de_novo(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        quantos: int,
        posicao: int,
        diario_legivel: bool,
    ) -> None:
        """Conferência de 25/09: pôr, tirar e pôr de novo dentro do teto.

        O teto de uma derrubada por controle a cada `TETO_POR_CONTROLE_S` é
        contra o LAÇO (o rádio cai e o cabo não sobe). Com a troca que deu
        certo ele não pode valer: ela ajeitou o cabo, e o controle ficaria no
        rádio carregando — a queixa de 25/09 inteira, de volta.
        """
        mesa = montar(
            monkeypatch,
            tmp_path,
            ("bt", "bt", "bt", "bt")[:quantos],
            diario_legivel=diario_legivel,
        )
        alvo = UNIQS[posicao]
        numeros = mesa.numeros()
        plugar_o_cabo_e_esperar(mesa, alvo, tiques=6)
        assert mesa.transporte_de(alvo) == "usb"
        primeira_derrubada = mesa.relogio.t
        inst = mesa.kernel.instancia(alvo, "usb")
        assert inst is not None
        mesa.kernel.desconectar(inst)  # ela tira o cabo
        mesa.tique()
        mesa.kernel.conectar(alvo, "bt")  # e o controle volta pelo pareamento
        for _ in range(3):
            mesa.tique()
        assert mesa.transporte_de(alvo) == "bt"
        # A régua só mede o teto se o segundo cabo cair DENTRO dele.
        assert mesa.relogio.t - primeira_derrubada < oce.TETO_POR_CONTROLE_S
        plugar_o_cabo_e_esperar(mesa, alvo, tiques=6)  # e põe de novo, logo depois

        assert mesa.transporte_de(alvo) == "usb", (
            "o cabo posto de novo dentro do teto deixou o controle no rádio carregando"
        )
        assert mesa.bluez.desconectados == [alvo, alvo]
        assert mesa.numeros() == numeros


@pytest.mark.usefixtures("config_isolado")
class TestQuandoOCaboNaoAssume:
    """A dúvida vale «fica no rádio», que é o comportamento de antes."""

    def test_no_modo_nativo_o_cabo_espera_o_jogo_soltar(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt"))
        mesa.nativo = True
        plugar_o_cabo_e_esperar(mesa, UNIQS[1])
        assert mesa.transporte_de(UNIQS[1]) == "bt"
        assert mesa.bluez.desconectados == []
        mesa.nativo = False
        for _ in range(3):
            mesa.tique()
        assert mesa.transporte_de(UNIQS[1]) == "usb"

    def test_sem_a_regra_que_religa_o_radio_nao_cai(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt"), regra_instalada=False)
        plugar_o_cabo_e_esperar(mesa, UNIQS[0])
        assert mesa.bluez.desconectados == [], (
            "sem a regra 85 o controle ficaria sem rádio e sem cabo"
        )
        assert mesa.transporte_de(UNIQS[0]) == "bt"

    def test_sem_o_diario_a_borda_da_carga_acha_o_par(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # O P3 está na base de carga desde antes: energia de fora, sem borda.
        mesa = montar(
            monkeypatch,
            tmp_path,
            ("bt", "bt", "bt"),
            na_tomada=frozenset({UNIQS[2]}),
            diario_legivel=False,
        )
        plugar_o_cabo_e_esperar(mesa, UNIQS[1], tiques=6)
        assert mesa.bluez.desconectados == [UNIQS[1]]
        assert mesa.transporte_de(UNIQS[1]) == "usb"
        assert mesa.transporte_de(UNIQS[2]) == "bt"

    def test_sem_o_diario_e_com_dois_cabos_ninguem_cai(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt", "bt"), diario_legivel=False)
        mesa.kernel.conectar(UNIQS[0], "usb")
        mesa.kernel.conectar(UNIQS[1], "usb")
        for _ in range(6):
            mesa.tique()
        assert mesa.bluez.desconectados == [], (
            "a borda da carga apontava dois controles e o produto derrubou um rádio"
        )

    def test_um_controle_novo_no_cabo_nao_derruba_ninguem(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt", "bt"))
        mesa.kernel.conectar(UNIQS[3], "usb")
        for _ in range(4):
            mesa.tique()
        assert mesa.bluez.desconectados == []
        assert mesa.transporte_de(UNIQS[3]) == "usb"

    def test_quem_nunca_esteve_no_radio_sai_do_cabo_como_sempre(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "usb"))
        inst = mesa.kernel.instancia(UNIQS[1], "usb")
        assert inst is not None
        mesa.kernel.desconectar(inst)
        mesa.tique()
        assert not mesa.inst.em_troca_de_transporte(UNIQS[1])

    def test_a_troca_que_nao_volta_vence_no_prazo(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Sem jogo: o posto só espera pela troca, e não pelo lugar guardado.
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt"), jogo=False)
        mesa.kernel.regra_instalada = False  # o cabo NÃO entra: nada religa
        assert mesa.inst.iniciar_troca_de_transporte(UNIQS[0], motivo="teste")
        inst = mesa.kernel.instancia(UNIQS[0], "bt")
        assert inst is not None
        mesa.kernel.desconectar(inst)
        mesa.tique()
        assert mesa.inst.primary_uniq == UNIQS[0], "o posto não esperou quem trocava"
        for _ in range(int(PRAZO_DA_TROCA_DE_TRANSPORTE_S / TIQUE) + 1):
            mesa.tique()
        assert not mesa.inst.em_troca_de_transporte(UNIQS[0])
        assert mesa.inst.primary_uniq == UNIQS[1], "passado o prazo, a NUM-01 volta"


# ---------------------------------------------------------------------------
# As peças, uma a uma
# ---------------------------------------------------------------------------


class TestOCaboEmEspera:
    def test_so_o_hid_do_cabo_sem_driver_espera(self, tmp_path: Path) -> None:
        raiz = tmp_path / "hid"
        (raiz / "0003:054C:0CE6.001B").mkdir(parents=True)  # o cabo recusado
        (raiz / "0003:054C:0CE6.0010").mkdir()
        (raiz / "0003:054C:0CE6.0010" / "driver").write_text("")  # cabo com driver
        (raiz / "0005:054C:0CE6.0011").mkdir()  # rádio órfão: é do bt_rebind_orphans
        virtual = tmp_path / "devices" / "virtual" / "misc" / "uhid" / "0003:054C:0DF2.0012"
        virtual.mkdir(parents=True)
        (raiz / "0003:054C:0DF2.0012").symlink_to(virtual)  # o vpad do produto
        (raiz / "0003:3554:FA07.0013").mkdir()  # um teclado
        assert oce.cabos_em_espera(raiz) == [oce.CaboEmEspera("0003:054C:0CE6.001B")]

    def test_a_linha_do_kernel_da_o_endereco(self) -> None:
        texto = (
            "playstation 0003:054C:0CE6.001B: hidraw1: USB HID v1.11 Gamepad\n"
            "playstation 0003:054C:0CE6.001B: Duplicate device found for MAC address "
            "aa:bb:cc:00:00:02.\n"
            "playstation 0003:054C:0CE6.001B: probe with driver playstation failed with error -17\n"
        )
        assert oce.enderecos_recusados(texto) == {"0003:054C:0CE6.001B": UNIQS[1]}

    def test_o_diario_que_nao_se_deixa_ler_e_nao_sei(self) -> None:
        assert oce.ler_o_diario_do_kernel(lambda _cmd: "") is None
        assert oce.ler_o_diario_do_kernel(lambda _cmd: None) is None

    def test_a_regra_instalada_e_lida_na_chamada(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        regra = tmp_path / oce.NOME_DA_REGRA
        monkeypatch.setattr(oce, "REGRAS_QUE_RELIGAM", (str(regra),))
        assert oce.impedimentos_da_troca() != []
        regra.write_text("", encoding="utf-8")
        assert oce.impedimentos_da_troca() == []

    def test_derrubar_so_desconecta_e_so_quem_esta_ligado(self) -> None:
        chamadas: list[str] = []

        class _Leitor:
            def aparelhos(self) -> tuple[SimpleNamespace, ...]:
                return (
                    SimpleNamespace(
                        caminho="/org/bluez/hci0/dev_X", endereco=MACS[0], conectado=False
                    ),
                    SimpleNamespace(
                        caminho="/org/bluez/hci1/dev_X", endereco=MACS[0], conectado=True
                    ),
                    SimpleNamespace(
                        caminho="/org/bluez/hci1/dev_Y", endereco=MACS[1], conectado=True
                    ),
                )

            def desconectar(self, caminho: str, *, quem: str) -> SimpleNamespace:
                chamadas.append(caminho)
                return SimpleNamespace(feita=True, erro="", mensagem="")

        assert oce.derrubar_o_radio(UNIQS[0], leitor=_Leitor()) == (True, "")
        assert chamadas == ["/org/bluez/hci1/dev_X"]

    def test_a_vigia_espera_a_probe_e_desiste_de_quem_nao_e_gemeo(self) -> None:
        vigia = oce.VigiaDoCabo()
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0030")
        vigia.observar_os_cabos([cabo], 100.0)
        no_radio: dict[str, str | None] = {UNIQS[0]: "carregando"}
        cedo = vigia.decidir(cabo, diario={}, no_radio=no_radio, agora=101.0)
        assert cedo.par is None and not cedo.desistir
        tarde = vigia.decidir(
            cabo, diario={}, no_radio=no_radio, agora=100.0 + oce.ESPERA_PARA_SER_ORFAO_S
        )
        assert tarde.par is None and tarde.desistir

    def test_o_teto_nao_derruba_o_mesmo_radio_em_laco(self) -> None:
        vigia = oce.VigiaDoCabo()
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0031")
        vigia.observar_os_cabos([cabo], 0.0)
        diario = {cabo.instancia: UNIQS[0]}
        no_radio: dict[str, str | None] = {UNIQS[0]: None}
        assert vigia.decidir(cabo, diario=diario, no_radio=no_radio, agora=0.0).par == UNIQS[0]
        vigia.derrubou(UNIQS[0], 0.0)
        de_novo = vigia.decidir(cabo, diario=diario, no_radio=no_radio, agora=10.0)
        assert de_novo.par is None and de_novo.desistir

    def test_o_teto_sai_quando_o_cabo_assumiu(self) -> None:
        vigia = oce.VigiaDoCabo()
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0032")
        vigia.observar_os_cabos([cabo], 0.0)
        diario = {cabo.instancia: UNIQS[0]}
        no_radio: dict[str, str | None] = {UNIQS[0]: None}
        vigia.derrubou(UNIQS[0], 0.0)
        vigia.observar_quem_esta_no_cabo([UNIQS[1]])  # outro controle no cabo não solta
        assert vigia.decidir(cabo, diario=diario, no_radio=no_radio, agora=10.0).desistir
        vigia.observar_quem_esta_no_cabo([UNIQS[0]])  # a troca dele deu certo
        assert vigia.decidir(cabo, diario=diario, no_radio=no_radio, agora=10.0).par == UNIQS[0]


class TestAEnumeracaoPrefereOCabo:
    """Um kernel que deixasse os dois nós: a escolha não é mais do sorteio."""

    @pytest.mark.parametrize("ordem", ["radio-primeiro", "cabo-primeiro"])
    def test_o_mesmo_controle_nos_dois_barramentos_abre_o_cabo(
        self, monkeypatch: pytest.MonkeyPatch, ordem: str
    ) -> None:
        radio = SimpleNamespace(product_id=0x0CE6, path=b"/dev/hidraw10", serial_number=MACS[0])
        cabo = SimpleNamespace(product_id=0x0CE6, path=b"/dev/hidraw1", serial_number=MACS[0])
        vistos = [radio, cabo] if ordem == "radio-primeiro" else [cabo, radio]
        fake_hidapi = SimpleNamespace(enumerate=lambda vendor_id: list(vistos))
        monkeypatch.setitem(sys.modules, "hidapi", fake_hidapi)
        monkeypatch.setattr(backend_mod, "_is_virtual_hidraw", lambda _p: False)
        monkeypatch.setattr(
            backend_mod,
            "_hidraw_uevent",
            lambda no: {"HID_ID": "0003:x" if no == "hidraw1" else "0005:x"},
        )
        assert PyDualSenseController._enumerate_device_keys() == [
            (MACS[0], b"/dev/hidraw1", False)
        ]


@pytest.mark.usefixtures("config_isolado")
class TestONoQueMudaNumTiqueSo:
    """A key que segue na mesa por outro nó troca o handle no MESMO lugar."""

    def test_o_handle_do_no_morto_nao_fica(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mesa = montar(monkeypatch, tmp_path, ("bt", "bt"))
        antigo = mesa.inst._handles[MACS[0]]
        inst = mesa.kernel.instancia(UNIQS[0], "bt")
        assert inst is not None
        mesa.kernel.regra_instalada = False
        mesa.kernel.desconectar(inst)
        mesa.kernel.conectar(UNIQS[0], "usb")  # o cabo entra antes do próximo connect()
        reaplicados: list[tuple[str, Any]] = []
        reaplicar = mesa.inst._reapply_desired

        def _espiar(key: str, handle: Any) -> None:
            reaplicados.append((key, handle))
            reaplicar(key, handle)

        monkeypatch.setattr(mesa.inst, "_reapply_desired", _espiar)
        mesa.connect()
        novo = mesa.inst._handles[MACS[0]]
        assert novo is not antigo and antigo.closed, "o connect() ficou com o handle do nó morto"
        assert reaplicados == [(MACS[0], novo)], (
            "o handle do cabo não recebeu a cor e o perfil do controle"
        )
        assert list(mesa.inst._handles) == [MACS[0], MACS[1]], "a ordem da mesa andou"
        assert mesa.inst.primary_uniq == UNIQS[0]
        assert mesa.inst.get_transport() == "usb"
        assert mesa.inst.em_troca_de_transporte(UNIQS[0]), (
            "a troca que ninguém pediu não deixou a folga para o co-op"
        )
        mesa.relogio.avancar(FOLGA_DEPOIS_DA_TROCA_S)
        assert not mesa.inst.em_troca_de_transporte(UNIQS[0])


# ---------------------------------------------------------------------------
# O laço de verdade: sem queda publicada, e o som de volta no controle
# ---------------------------------------------------------------------------


class _DaemonDoLaco:
    """O que o `reconnect_loop` usa do daemon, com o backend REAL por baixo."""

    def __init__(self, mesa: MesaDoCabo, voltas: int) -> None:
        self.controller = mesa.inst
        self.bus = EventBus()
        self.voltas = 0
        self._voltas = voltas
        self._hidraw_broker_executor = ThreadPoolExecutor(max_workers=1)
        self._mesa = mesa

    def _is_stopping(self) -> bool:
        return self.voltas >= self._voltas

    def _arm_input_grace(self) -> None:
        return None

    def is_native_mode(self) -> bool:
        return False

    async def _run_blocking(self, fn, *args):  # type: ignore[no-untyped-def]
        if fn == self.controller.connect:
            _connect_na_mesa(self.controller, self._mesa.kernel)
            return None
        return fn(*args)


def _derrubar_na_bancada(mesa: MesaDoCabo, uniq: str) -> tuple[bool, str]:
    """O `derrubar_o_radio` de verdade, falando com o :class:`BlueZ` da bancada."""
    return _DERRUBAR_REAL(uniq, leitor=mesa.bluez)


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("quantos", [1, 2])
@pytest.mark.parametrize(
    ("vao", "handles_atrasam"),
    [(True, False), (False, False), (False, True)],
    ids=["com-vao", "num-tique", "num-tique-com-o-handle-atrasado"],
)
def test_o_laco_nao_publica_queda_e_devolve_o_som(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    quantos: int,
    vao: bool,
    handles_atrasam: bool,
) -> None:
    """Ponta a ponta no `reconnect_loop`: com um controle só, a mesa fica vazia no vão.

    Os três caminhos da volta: o controle fora da mesa por um tique (a probe
    da regra atrasa), o handle trocado no mesmo lugar (a probe na hora), e o
    handle do rádio que ainda diz `connected` quando o cabo já está lá (o
    `report_thread` só percebe no erro de leitura seguinte) — este último é
    a borda que nenhum `alvo_sumiu` vê, e só a foto do transporte pega.
    """
    mesa = montar(monkeypatch, tmp_path, ("bt", "bt")[:quantos])
    mesa.kernel.regra_atrasa = vao
    mesa.kernel.handles_atrasam = handles_atrasam
    reaplicados: list[str | None] = []

    async def _reaplicar(_daemon: Any, *, uniq: str | None = None) -> None:
        reaplicados.append(uniq)

    async def _nada(*_a: Any, **_k: Any) -> int:
        return 0

    monkeypatch.setattr(conn_mod, "reapply_speaker_after_connect", _reaplicar)
    monkeypatch.setattr(conn_mod, "reapply_mic_after_connect", _nada)
    monkeypatch.setattr(conn_mod, "nascer_o_microfone_ao_conectar", lambda *_a, **_k: None)
    monkeypatch.setattr(conn_mod, "registrar_gatilho_da_lightbar", lambda d: None)
    monkeypatch.setattr(conn_mod, "armar_gatilho_da_cor", lambda d: 0)
    monkeypatch.setattr(conn_mod, "armar_gatilho_da_cor_por_numeracao", lambda d: False)
    monkeypatch.setattr(conn_mod, "vigiar_escritor_cru", _nada)
    monkeypatch.setattr(conn_mod, "carimbar_o_nascimento", _nada)
    # O re-hide fala com o broker: nesta bancada ele não existe, e o dela não se toca.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.gamepad.rehide_physical_hidraw",
        lambda _d: None,
    )
    monkeypatch.setattr(oce, "ler_o_diario_do_kernel", mesa.ler_o_diario)
    monkeypatch.setattr(
        oce, "derrubar_o_radio", lambda uniq, leitor=None: _derrubar_na_bancada(mesa, uniq)
    )
    estado = {"armada": False}

    async def _espera(daemon_: _DaemonDoLaco, _watch: object) -> bool:
        daemon_.voltas += 1
        mesa.relogio.avancar(TIQUE)
        mesa.kernel.os_handles_percebem()
        # A probe atrasada cai uma espera DEPOIS da derrubada: o `connect()` do
        # meio vê o controle fora da mesa.
        if estado["armada"]:
            mesa.kernel.a_regra_atrasada_roda()
        estado["armada"] = mesa.kernel._probes_pendentes
        if daemon_.voltas == 1:
            mesa.kernel.conectar(UNIQS[0], "usb")  # ela pluga o cabo no P1
        return True

    async def _espera_offline(daemon_: Any, _t: float) -> None:
        await _espera(daemon_, None)

    monkeypatch.setattr(conn_mod, "_wait_online_or_hotplug", _espera)
    monkeypatch.setattr(conn_mod, "_wait_or_stop", _espera_offline)

    class _WatchMudo:
        def poll(self) -> bool:
            return False

    async def _rodar() -> list[Any]:
        daemon = _DaemonDoLaco(mesa, voltas=6)
        quedas = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)
        try:
            await asyncio.wait_for(
                conn_mod.reconnect_loop(daemon, input_watch=_WatchMudo()),  # type: ignore[arg-type]
                10.0,
            )
        finally:
            daemon._hidraw_broker_executor.shutdown(wait=False)
        publicadas = []
        while not quedas.empty():
            publicadas.append(quedas.get_nowait())
        return publicadas

    publicadas = asyncio.run(_rodar())
    assert publicadas == [], f"a troca de transporte virou queda: {publicadas}"
    assert mesa.bluez.desconectados == [UNIQS[0]]
    assert mesa.transporte_de(UNIQS[0]) == "usb"
    assert reaplicados == [UNIQS[0]], (
        f"o som foi reaplicado em {reaplicados} — o handle do cabo nasce sem a posse do áudio"
    )


# ---------------------------------------------------------------------------
# A regra 85: o texto que o udev roda, rodado de verdade num barramento forjado
# ---------------------------------------------------------------------------


def _programas_da_regra() -> list[tuple[str, str]]:
    """(a linha inteira, o programa do `sh -c` como o udev o entrega)."""
    achados = []
    for linha in REGRA.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or not linha.strip():
            continue
        casou = re.search(r"RUN\+=\"/bin/sh -c '(?P<prog>[^']*)'\"", linha)
        assert casou is not None, f"linha da regra sem o RUN esperado: {linha}"
        # O udev troca `$$` por `$` antes de executar.
        achados.append((linha, casou.group("prog").replace("$$", "$")))
    return achados


class TestARegraQueReligaOCabo:
    def test_a_regra_so_age_na_saida_de_um_dualsense_fisico(self) -> None:
        linhas = [linha for linha, _ in _programas_da_regra()]
        assert len(linhas) == 2
        for linha in linhas:
            assert 'ACTION=="remove"' in linha and 'SUBSYSTEM=="hid"' in linha
        assert 'KERNEL=="0005:054C:0CE6.*|0005:054C:0DF2.*"' in linhas[0]
        assert 'KERNEL=="0003:054C:0CE6.*|0003:054C:0DF2.*"' in linhas[1]
        assert 'DEVPATH!="/devices/virtual/*"' in linhas[1], "o vpad do produto dispararia a regra"

    def test_o_programa_pede_a_probe_so_de_quem_espera(self, tmp_path: Path) -> None:
        hid = tmp_path / "sys" / "bus" / "hid"
        devices = hid / "devices"
        devices.mkdir(parents=True)
        (devices / "0003:054C:0CE6.001B").mkdir()  # o cabo que espera
        (devices / "0005:054C:0CE6.0011").mkdir()  # um rádio órfão
        (devices / "0005:054C:0CE6.0012").mkdir()
        (devices / "0005:054C:0CE6.0012" / "driver").write_text("")  # quem tem driver
        (devices / "0003:3554:FA07.0013").mkdir()  # um teclado sem driver: não é nosso
        sondas = hid / "drivers_probe"
        for _linha, programa in _programas_da_regra():
            sondas.write_text("", encoding="utf-8")
            # O `drivers_probe` do kernel recebe UMA escrita por vez; aqui ele é
            # arquivo comum, e o `>>` guarda todas para contar.
            forjado = programa.replace("/sys/bus/hid", str(hid)).replace(" > ", " >> ")
            feito = subprocess.run(
                ["sh", "-c", forjado], capture_output=True, text=True, check=False
            )
            assert feito.returncode == 0, feito.stderr
            assert sorted(sondas.read_text(encoding="utf-8").split()) == [
                "0003:054C:0CE6.001B",
                "0005:054C:0CE6.0011",
            ]

    def test_o_programa_nao_falha_sem_ninguem_esperando(self, tmp_path: Path) -> None:
        hid = tmp_path / "hid"
        (hid / "devices").mkdir(parents=True)
        for _linha, programa in _programas_da_regra():
            forjado = programa.replace("/sys/bus/hid", str(hid))
            feito = subprocess.run(
                ["sh", "-c", forjado], capture_output=True, text=True, check=False
            )
            assert feito.returncode == 0
            assert not (hid / "drivers_probe").exists()
