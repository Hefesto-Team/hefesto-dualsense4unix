"""O doctor pergunta ao daemon o modo de cada jogador e a hora em que o pad nasceu.

O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 (27/09/2026).

**O MODO.** Às 16h16 de 27/09 o fecho foi «pads no `uhid` e nenhum
`vpad_degradado`», com o Freestyle dela no modo Xbox. O `state_full` daquela
cena diz `caminho: xbox`, o P1 em `uhid` e `degraded: false`: tudo o que existia
lia íntegro. `modo_contra_o_ar` compara, por jogador, o canal que o modo pedido
dá (`virtual_pad.quer_uhid`, o dono) com o pad no ar.

As cenas daqui não são dicionários escritos à mão: o estado sai do
`_handle_daemon_state_full` REAL, com o `Daemon` de verdade, o `CoopManager` de
verdade e cada pad nascido pela FÁBRICA de verdade (`make_virtual_pad`), com o
evdev de mentira e o `uhid` que «faz bind» sem kernel. O dublê publica o que o
real publica, porque é o real que publica.

**A HORA.** Na noite de 27/09 os pads `uinput` levaram de 28,7 a 30,3 s entre o
kernel criar o nó e o daemon registrar. As linhas daqui são as do diário
daquela noite e as do boot de 28/09 (depois da cura), com o nome da máquina e
os PIDs trocados.

As mordidas (a comparação arrancada, o limite em 60 s, a folga em zero) estão
no relatório da sprint, com o vermelho que cada uma deu.
"""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import types
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import o_modo_no_ar as modo
from hefesto_dualsense4unix.core.o_modo_no_ar import (
    AVISO,
    FALHA,
    OK,
    hora_do_pad,
    modo_contra_o_ar,
)
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_vpad_ff_passthrough import _EC, _AbsInfo

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"
APP_ID = "hefesto-dualsense4unix"

#: A faixa sintética da casa: nenhum endereço de aparelho de verdade.
UNIQS = ("aabbcc0000a1", "aabbcc0000a2", "aabbcc0000a3", "aabbcc0000a4")


# ---------------------------------------------------------------------------
# A mesa real: o estado sai do handler de verdade
# ---------------------------------------------------------------------------


class _UInputDeMentira:
    """O `evdev.UInput` sem kernel: nasce, escreve em lugar nenhum e fecha."""

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        self.events = events
        self.kwargs = kwargs
        self.fd = -1

    def write(self, etype: int, code: int, value: int) -> None:
        return

    def syn(self) -> None:
        return

    def close(self) -> None:
        return

    def read_one(self) -> None:
        return None


@dataclass
class Jogador:
    """Um controle na mesa e como o pad dele nasceu.

    ``nasce``: ``pelo_modo`` (a fábrica com o caminho da sessão, o normal),
    ``sem_caminho`` (a promoção de 16h16, que reiniciava sem o caminho),
    ``no_xbox`` (o `_reerguer_o_p1` do PRAGMATA, que lia o slot Xbox) ou
    ``antigo`` (um pad `uinput` de antes da cura, que não sabe o caminho nem
    o motivo).
    """

    nasce: str = "pelo_modo"
    mascara: str | None = None


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = daemon.store
        self.controller = daemon.controller


@pytest.fixture
def fabrica(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, bool]]:
    """A fábrica real, com o `uinput` de mentira e o `uhid` que faz bind sem kernel.

    ``{"uhid": False}`` põe o `uhid` fora do ar: a fábrica cai no `uinput` e
    pendura o motivo que ela pendura na vida real.
    """
    mod = types.ModuleType("evdev")
    mod.UInput = _UInputDeMentira  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    ar = {"uhid": True}
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: ar["uhid"])

    def _uhid(flavor: str, *, player: int, identity: Any = None, **_kw: Any) -> Any:
        if not ar["uhid"]:
            return None, "uhid_indisponivel"
        return UhidDualSense(player=player, identity=identity), None

    monkeypatch.setattr(vp, "_try_uhid", _uhid)
    em._zerar_registro_de_mascaras()
    yield ar
    em._zerar_registro_de_mascaras()


def _pad(jogador: Jogador, uniq: str, numero: int, caminho: str | None) -> Any:
    if jogador.nasce == "antigo":
        pad = UinputGamepad.for_flavor("dualsense", identity=uniq)
        assert pad.start()
        return pad
    nasce_com = {"pelo_modo": caminho, "sem_caminho": None, "no_xbox": "xbox"}[jogador.nasce]
    pad = vp.make_virtual_pad("dualsense", identity=uniq, player=numero, caminho=nasce_com)
    assert pad is not None, "a fábrica não entregou pad"
    return pad


async def _estado(
    caminho: str | None,
    jogadores: list[Jogador],
    *,
    nativo: bool = False,
    controlar_o_pc: bool = False,
) -> dict[str, Any]:
    """O `daemon.state_full` da mesa, pelo handler de verdade."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.controller.primary_uniq = UNIQS[0]  # type: ignore[attr-defined]
    daemon.controller.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {
            "index": i,
            "connected": True,
            "transport": "usb" if i % 2 == 0 else "bt",
            "is_primary": i == 0,
            "uniq": UNIQS[i],
        }
        for i in range(len(jogadores))
    ]
    for uniq, jogador in zip(UNIQS, jogadores, strict=False):
        if jogador.mascara is not None:
            assert em.registro_de_mascaras().set_mask(uniq, jogador.mascara)
    daemon.config.gamepad_flavor = "dualsense"
    daemon.config.gamepad_caminho = caminho
    if nativo:
        # A Conexão Nativa numera pelo registro de identidade, e o `FakeController`
        # não o traz: o registro é o de verdade, com a fila na ordem da mesa.
        daemon.identity_registry = ControllerIdentityRegistry()
        for uniq in UNIQS[: len(jogadores)]:
            daemon.identity_registry.slot_for(uniq)
        daemon._native_mode = True
        daemon.config.gamepad_emulation_enabled = False
        daemon.config.coop_enabled = False
        return await _Handlers(daemon)._handle_daemon_state_full({})
    if controlar_o_pc:
        # «Controlar o PC»: o controle mexe no PC, sem pad e sem jogador.
        daemon.config.gamepad_emulation_enabled = False
        daemon.config.coop_enabled = True
        estado = await _Handlers(daemon)._handle_daemon_state_full({})
        return json.loads(json.dumps(estado))
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.coop_enabled = True
    daemon._gamepad_device = _pad(jogadores[0], UNIQS[0], 1, caminho)
    manager = CoopManager(daemon)
    for numero, (uniq, jogador) in enumerate(zip(UNIQS[1:], jogadores[1:], strict=False), 2):
        manager._players[uniq] = _SecondaryPlayer(
            identity=uniq,
            evdev_path=f"/dev/input/event{20 + numero}",
            reader=types.SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
            player_index=numero,
            vpad=_pad(jogador, uniq, numero, caminho),
        )
    daemon._coop_manager = manager  # type: ignore[assignment]
    estado = await _Handlers(daemon)._handle_daemon_state_full({})
    # O estado tem de atravessar o socket: o servidor manda JSON.
    return json.loads(json.dumps(estado))


def _resumo(linhas: list[modo.ModoDoJogador]) -> list[tuple[int, str | None, str, str]]:
    return [(linha.jogador, linha.pedido, linha.no_ar, linha.veredito) for linha in linhas]


@pytest.mark.usefixtures("fabrica")
class TestOModoContraOAr:
    async def test_xbox_pedido_e_uinput_no_ar_e_ok(self) -> None:
        estado = await _estado("xbox", [Jogador()])
        assert _resumo(modo_contra_o_ar(estado)) == [(1, "xbox", "uinput", OK)]

    async def test_as_16h16_xbox_pedido_e_uhid_no_ar_sem_motivo_e_falha(self) -> None:
        """A cena do fecho de 27/09: o P1 renasceu sem o caminho, no `uhid`.

        O que existia antes lia íntegro, e a régua confere isso primeiro: sem
        esta checagem, nada no estado acusava.
        """
        estado = await _estado("xbox", [Jogador("sem_caminho"), Jogador(), Jogador(), Jogador()])
        emulacao = estado["gamepad_emulation"]
        assert (emulacao["caminho"], emulacao["backend"], emulacao["degraded"]) == (
            "xbox",
            "uhid",
            False,
        )
        assert _resumo(modo_contra_o_ar(estado)) == [
            (1, "xbox", "uhid", FALHA),
            (2, "xbox", "uinput", OK),
            (3, "xbox", "uinput", OK),
            (4, "xbox", "uinput", OK),
        ]

    async def test_dualsense_pedido_e_uinput_com_o_motivo_e_aviso(
        self, fabrica: dict[str, bool]
    ) -> None:
        fabrica["uhid"] = False
        (linha,) = modo_contra_o_ar(await _estado("dualsense", [Jogador()]))
        assert (linha.no_ar, linha.motivo, linha.veredito) == (
            "uinput",
            "uhid_indisponivel",
            AVISO,
        )
        assert "uhid_indisponivel" in linha.frase()

    async def test_o_pad_antigo_sem_uhid_e_aviso_com_sem_uhid(self) -> None:
        """O pad que não sabe o caminho nem o motivo: o piso do dono é `sem_uhid`."""
        (linha,) = modo_contra_o_ar(await _estado("dualsense", [Jogador("antigo")]))
        assert (linha.no_ar, linha.motivo, linha.veredito) == ("uinput", "sem_uhid", AVISO)

    async def test_conexao_nativa_sem_pad_e_ok(self) -> None:
        linhas = modo_contra_o_ar(await _estado(None, [Jogador(), Jogador()], nativo=True))
        assert linhas, "a Conexão Nativa tem jogadores, e cada um ganha a sua linha"
        assert all((ln.pedido, ln.no_ar, ln.veredito) == ("nativo", "nenhum", OK) for ln in linhas)

    async def test_quatro_jogadores_quatro_linhas_certas(self) -> None:
        """Modo DualSense, e cada jogador num estado: as quatro linhas não se misturam.

        P1 no `uhid` (certo); P2 no Xbox 360 do cartão, `uinput` (certo: o
        `uhid` não veste essa máscara); P3 no `uinput` que nasceu no Xbox com a
        máscara DualSense (o PRAGMATA de 27/09); P4 no pad antigo sem `uhid`.
        """
        estado = await _estado(
            "dualsense",
            [Jogador(), Jogador(mascara="xbox"), Jogador("no_xbox"), Jogador("antigo")],
        )
        assert _resumo(modo_contra_o_ar(estado)) == [
            (1, "dualsense", "uhid", OK),
            (2, "dualsense", "uinput", OK),
            (3, "dualsense", "uinput", FALHA),
            (4, "dualsense", "uinput", AVISO),
        ]

    async def test_o_mesmo_arranjo_no_modo_xbox(self) -> None:
        estado = await _estado(
            "xbox",
            [Jogador(), Jogador(mascara="xbox"), Jogador(), Jogador(mascara="xbox")],
        )
        assert [ln.veredito for ln in modo_contra_o_ar(estado)] == [OK, OK, OK, OK]

    async def test_o_daemon_que_nao_diz_o_modo_nunca_e_ok(self) -> None:
        estado = await _estado("xbox", [Jogador()])
        del estado["gamepad_emulation"]["caminho"]
        (linha,) = modo_contra_o_ar(estado)
        assert (linha.pedido, linha.veredito) == (None, AVISO)
        assert "não medido" in linha.frase()

    async def test_o_jogador_esperando_o_controle_e_aviso(self) -> None:
        estado = await _estado("xbox", [Jogador(), Jogador()])
        dois = next(i for i in estado["coop"]["mesa"] if i["player"] == 2)
        dois.update(vpad_backend=None, aguardando_grab=True)
        estado["rumble_ff"]["per_vpad"] = [
            b for b in estado["rumble_ff"]["per_vpad"] if b["player"] != 2
        ]
        linhas = {ln.jogador: ln for ln in modo_contra_o_ar(estado)}
        assert (linhas[2].no_ar, linhas[2].motivo, linhas[2].veredito) == (
            "nenhum",
            "aguardando_grab",
            AVISO,
        )

    async def test_controlar_o_pc_nao_tem_jogador_nem_pad(self) -> None:
        """O modo mouse e teclado: nenhum jogador numerado e nenhum pad no ar."""
        estado = await _estado(None, [Jogador(), Jogador()], controlar_o_pc=True)
        assert estado["native_mode"] is False
        assert estado["gamepad_emulation"]["enabled"] is False
        assert modo_contra_o_ar(estado) == []

    async def test_a_nativa_com_pad_no_ar_e_falha_e_concorda(self) -> None:
        estado = await _estado("xbox", [Jogador()])
        estado["native_mode"] = True
        (linha,) = modo_contra_o_ar(estado)
        assert linha.veredito == FALHA
        assert linha.frase() == "P1: Conexão Nativa pedida, pad uinput no ar, sem queda dita"

    async def test_a_frase_diz_so_jogador_modo_e_backend(self) -> None:
        estado = await _estado(
            "dualsense",
            [Jogador(), Jogador(mascara="xbox"), Jogador("no_xbox"), Jogador("antigo")],
        )
        frases = [ln.frase() for ln in modo_contra_o_ar(estado)]
        assert frases[0] == "P1: modo DualSense, pad uhid"
        assert frases[2] == "P3: modo DualSense pedido, pad uinput no ar, sem queda dita"
        for frase in frases:
            assert not re.search(r"/dev/|/sys/|event\d|input\d|hidraw|aabbcc|02:fe", frase)


# ---------------------------------------------------------------------------
# A hora do pad
# ---------------------------------------------------------------------------

_XBOX = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"
_EDGE = "Sony Interactive Entertainment DualSense Edge Wireless Controller"


def _k(hora: str, nome: str, n: int, dia: str = "2026-09-27") -> str:
    return f"{dia}T{hora}-03:00 maquina kernel: input: {nome} as /devices/virtual/input/input{n}"


def _d(
    hora: str,
    evento: str,
    nome: str | None = None,
    dia: str = "2026-09-27",
    *,
    chegou: str | None = None,
) -> str:
    """Uma linha do daemon no `journalctl -o short-iso-precise`.

    ``chegou`` é o carimbo do journald (a chegada ao diário); sem ele, o mesmo
    instante do registro.
    """
    carimbo = f"{dia}T{hora}"
    recebido = f"{dia}T{chegou}" if chegou else carimbo[:26]
    prefixo = f"{recebido}-03:00 maquina hefesto-dualsense4unix[4242]: {carimbo} [info     ] "
    if evento == "daemon_starting":
        return prefixo + "daemon_starting                paused=False poll_hz=60"
    mascara, produto, fornecedor = (
        ("xbox", "0x28e", "0x45e") if nome == _XBOX else ("dualsense", "0xdf2", "0x54c")
    )
    return (
        prefixo + f"uinput_device_created          ff=True flavor={mascara} name='{nome}' "
        f"product={produto} vendor={fornecedor}"
    )


#: A noite de 27/09, 05h20 a 05h30, com o `cosmic-osk` de pé.
NOITE_KERNEL = [
    _k("05:20:07.008124", _EDGE, 681),
    _k("05:20:12.705122", _EDGE, 682),
    _k("05:20:13.647124", _XBOX, 683),
    _k("05:20:49.575271", _EDGE, 684),
    _k("05:20:51.410124", _XBOX, 685),
    _k("05:21:23.253150", _EDGE, 686),
    _k("05:21:24.358119", "input-remapper Compx 2.4G Wireless Receiver forwarded", 687),
    _k("05:21:29.028122", _XBOX, 690),
    _k("05:28:25.205126", "Hefesto - Dualsense4Unix Virtual Keyboard", 695),
    _k("05:28:27.037122", _XBOX, 696),
    _k("05:28:28.878121", _EDGE, 697),
    _k("05:28:29.761130", _XBOX, 698),
    _k("05:28:31.115122", _EDGE, 699),
    _k("05:29:00.903119", _XBOX, 700),
    _k("05:29:32.782164", _EDGE, 701),
    _k("05:30:02.183129", _XBOX, 702),
]
NOITE_DAEMON_ANTES = [
    _d("05:20:07.686900", "uinput_device_created", _EDGE),
    _d("05:20:13.212180", "uinput_device_created", _EDGE),
    _d("05:20:43.930153", "uinput_device_created", _XBOX),
    _d("05:20:50.049183", "uinput_device_created", _EDGE),
    _d("05:21:21.116152", "uinput_device_created", _XBOX),
    _d("05:21:23.353703", "uinput_device_created", _EDGE),
    _d("05:21:59.183170", "uinput_device_created", _XBOX),
]
NOITE_DAEMON_DEPOIS = [
    _d("05:28:24.572934", "daemon_starting"),
    _d("05:28:27.503171", "uinput_device_created", _XBOX),
    _d("05:28:29.358168", "uinput_device_created", _EDGE),
    _d("05:28:30.252157", "uinput_device_created", _XBOX),
    _d("05:29:00.540162", "uinput_device_created", _EDGE),
    _d("05:29:31.087151", "uinput_device_created", _XBOX),
    _d("05:30:01.462988", "uinput_device_created", _EDGE),
    _d("05:30:02.711163", "uinput_device_created", _XBOX),
]

#: O boot de 28/09, depois da cura: o journald carimba o kernel até 1,1 ms
#: DEPOIS do registro do daemon, dentro da folga.
BOOT = "2026-09-28"
BOOT_KERNEL = [
    _k("03:01:35.422250", _XBOX, 625, BOOT),
    _k("03:27:14.799166", _EDGE, 630, BOOT),
    _k("03:27:19.951163", _EDGE, 632, BOOT),
    _k("03:27:20.491642", _EDGE, 633, BOOT),
    _k("03:27:21.493164", _XBOX, 634, BOOT),
]
BOOT_DAEMON = [
    _d("03:01:27.417737", "daemon_starting", dia=BOOT),
    _d("03:01:35.426089", "uinput_device_created", _XBOX, BOOT),
    _d("03:27:14.798617", "uinput_device_created", _EDGE, BOOT),
    _d("03:27:19.951382", "uinput_device_created", _EDGE, BOOT),
    _d("03:27:20.490557", "uinput_device_created", _EDGE, BOOT),
    _d("03:27:21.492428", "uinput_device_created", _XBOX, BOOT),
]


#: O journald parado, na noite de 27/09 (linhas reais, nome e PID trocados). O
#: Xbox das 23:46:18 chegou ao diário 1,85 s depois do registro, e a linha do
#: próprio registro chegou junto com a do kernel.
PARADA_DAEMON = [
    _d("23:37:39.482631", "daemon_starting"),
    _d("23:42:37.803397", "uinput_device_created", _XBOX, chegou="23:42:37.803458"),
    _d("23:46:14.581312", "uinput_device_created", _EDGE, chegou="23:46:14.581687"),
    _d("23:46:18.957654", "uinput_device_created", _XBOX, chegou="23:46:20.805317"),
]
PARADA_KERNEL = [
    _k("23:42:37.804161", _XBOX, 483),
    _k("23:46:14.581168", _EDGE, 491),
    _k("23:46:20.804240", _XBOX, 494),
]


def _atrasos(medidas: list[modo.HoraDoPad]) -> list[tuple[str, float | None, str]]:
    return [
        (m.hora, None if m.atraso_s is None else round(m.atraso_s, 2), m.veredito)
        for m in medidas
    ]


class TestAHoraDoPad:
    def test_a_noite_de_27_09_antes_do_restart(self) -> None:
        """O +29,7 s do sprint é o Xbox das 05:20:51; os de meio segundo passam."""
        medidas = hora_do_pad(NOITE_KERNEL, NOITE_DAEMON_ANTES)
        assert _atrasos(medidas) == [
            ("05:20:07", 0.68, OK),
            ("05:20:12", 0.51, OK),
            ("05:20:13", 30.28, FALHA),
            ("05:20:49", 0.47, OK),
            ("05:20:51", 29.71, FALHA),
            ("05:21:23", 0.1, OK),
            ("05:21:29", 30.16, FALHA),
        ]
        assert medidas[4].frase() == (
            "o pad Xbox das 05:20:51 levou 29,7 s para nascer: algo pediu vibração "
            "antes de ele estar de pé"
        )
        assert medidas[0].frase() == "o pad DualSense das 05:20:07 nasceu em 0,7 s"

    def test_so_conta_desde_o_ultimo_daemon_starting(self) -> None:
        medidas = hora_do_pad(NOITE_KERNEL, NOITE_DAEMON_ANTES + NOITE_DAEMON_DEPOIS)
        assert _atrasos(medidas) == [
            ("05:28:27", 0.47, OK),
            ("05:28:28", 0.48, OK),
            ("05:28:29", 0.49, OK),
            ("05:28:31", 29.43, FALHA),
            ("05:29:00", 30.18, FALHA),
            ("05:29:32", 28.68, FALHA),
            ("05:30:02", 0.53, OK),
        ]

    def test_depois_da_cura_o_kernel_carimbado_depois_ainda_casa(self) -> None:
        medidas = hora_do_pad(BOOT_KERNEL, BOOT_DAEMON)
        assert [m.veredito for m in medidas] == [OK] * 5
        assert all(m.atraso_s is not None and m.atraso_s < 0.01 for m in medidas)

    def test_o_journald_parado_nao_vira_nao_medido(self) -> None:
        """As duas chegadas presas no mesmo journald: o atraso é entre elas."""
        medidas = hora_do_pad(PARADA_KERNEL, PARADA_DAEMON)
        assert [m.veredito for m in medidas] == [OK, OK, OK]
        assert medidas[2].hora == "23:46:18"
        assert medidas[2].atraso_s is not None and medidas[2].atraso_s < 0.01

    def test_a_parada_so_na_linha_do_kernel_e_nao_medido(self) -> None:
        """A linha do daemon chegou na hora e a do kernel 1,85 s depois: não é a
        mesma parada, e o pad sai «não medido», nunca OK."""
        daemon = [
            *PARADA_DAEMON[:3],
            _d("23:46:18.957654", "uinput_device_created", _XBOX, chegou="23:46:18.957700"),
        ]
        assert [m.veredito for m in hora_do_pad(PARADA_KERNEL, daemon)] == [OK, OK, AVISO]

    def test_as_duas_chegadas_longe_demais_e_nao_medido(self) -> None:
        """A linha do kernel chegou 5,5 s antes da do daemon, e depois do registro:
        as duas não contam a mesma parada, e nada ali mede o nascimento."""
        daemon = [
            *PARADA_DAEMON[:3],
            _d("23:46:18.957654", "uinput_device_created", _XBOX, chegou="23:46:26.304240"),
        ]
        assert [m.veredito for m in hora_do_pad(PARADA_KERNEL, daemon)] == [OK, OK, AVISO]

    def test_pad_sem_linha_do_kernel_e_aviso_nunca_ok(self) -> None:
        (medida,) = hora_do_pad([], BOOT_DAEMON[:2])
        assert (medida.atraso_s, medida.veredito) == (None, AVISO)
        assert "não foi medido" in medida.frase()

    def test_o_nome_e_quem_casa(self) -> None:
        """O teclado virtual e o `input-remapper` nascem no mesmo lugar e não contam."""
        (medida,) = hora_do_pad(
            [_k("05:28:25.205126", "Hefesto - Dualsense4Unix Virtual Keyboard", 695)],
            [_d("05:28:27.503171", "uinput_device_created", _XBOX)],
        )
        assert medida.veredito == AVISO

    def test_o_limite_e_dois_segundos(self) -> None:
        assert modo.LIMITE_DO_NASCIMENTO_S == 2.0

    def test_le_o_dmesg_com_virgula_e_o_diario_em_json(self) -> None:
        kernel = [
            f"2026-09-27T05:20:51,410124-03:00 input: {_XBOX} as /devices/virtual/input/input685"
        ]
        daemon = [
            json.dumps(
                {
                    "ff": True,
                    "flavor": "xbox",
                    "name": _XBOX,
                    "event": "uinput_device_created",
                    "level": "info",
                    "timestamp": "2026-09-27T05:21:21.116152",
                }
            )
        ]
        (medida,) = hora_do_pad(kernel, daemon)
        assert (medida.mascara, round(medida.atraso_s or 0, 2), medida.veredito) == (
            "xbox",
            29.71,
            FALHA,
        )


# ---------------------------------------------------------------------------
# O doctor.sh: as duas checagens, pelo socket e pelo diário
# ---------------------------------------------------------------------------


@pytest.fixture
def lar() -> Iterator[Path]:
    """Diretório CURTO em `/tmp`: o caminho de um socket AF_UNIX cabe em ~108 bytes."""
    d = Path(tempfile.mkdtemp(prefix="hf-modo-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _servir(sock_path: Path, result: dict[str, Any] | list[dict[str, Any]]) -> threading.Thread:
    """Serve o `state_full`; uma lista serve um estado por leitura, e repete o último."""
    fila = list(result) if isinstance(result, list) else [result]
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(4)
    srv.settimeout(10.0)

    def _laco() -> None:
        try:
            while True:
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                with conn:
                    conn.settimeout(5.0)
                    buf = b""
                    while not buf.endswith(b"\n"):
                        pedaco = conn.recv(65536)
                        if not pedaco:
                            break
                        buf += pedaco
                    pedido = json.loads(buf or b"{}")
                    if pedido.get("method") != "daemon.state_full":
                        continue
                    atual = fila.pop(0) if len(fila) > 1 else fila[0]
                    resposta = {"jsonrpc": "2.0", "id": pedido.get("id"), "result": atual}
                    conn.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
        finally:
            srv.close()

    fio = threading.Thread(target=_laco, daemon=True)
    fio.start()
    return fio


def _bin(lar: Path, kernel: list[str], diario: list[str]) -> Path:
    """`journalctl` de mentira e o `python3` desta suíte à frente do PATH."""
    binario = lar / "bin"
    binario.mkdir(exist_ok=True)
    (lar / "kernel.txt").write_text("\n".join(kernel) + "\n", encoding="utf-8")
    (lar / "diario.txt").write_text("\n".join(diario) + "\n", encoding="utf-8")
    journal = binario / "journalctl"
    journal.write_text(
        "#!/bin/sh\n"
        f'case "$*" in\n'
        f'  *--user*) cat "{lar}/diario.txt" ;;\n'
        f'  *_TRANSPORT=kernel*) cat "{lar}/kernel.txt" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    journal.chmod(0o755)
    python = binario / "python3"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(0o755)
    return binario


def _doctor(lar: Path, funcao: str, binario: Path | None = None) -> str:
    caminho = f"{binario}:/usr/bin:/bin" if binario else "/usr/bin:/bin"
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {funcao}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            "PATH": caminho,
            "DOCTOR_SH": str(DOCTOR),
            "XDG_RUNTIME_DIR": str(lar),
            "HOME": str(lar),
        },
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


def _socket(lar: Path) -> Path:
    pasta = lar / APP_ID
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{APP_ID}.sock"


_NO_OU_ENDERECO = re.compile(
    r"/dev/|/sys/|/devices/|event\d|input\d|hidraw|aabbcc|02:fe|([0-9a-f]{2}:){3}", re.I
)


@pytest.mark.usefixtures("fabrica")
class TestODoctorPergunta:
    def test_daemon_parado_e_info(self, lar: Path) -> None:
        for funcao in ("check_o_modo_no_ar", "check_a_hora_do_pad"):
            saida = _doctor(lar, funcao, _bin(lar, NOITE_KERNEL, NOITE_DAEMON_DEPOIS))
            assert "daemon parado" in saida, funcao
            assert "[FAIL]" not in saida and "[WARN]" not in saida, funcao

    async def test_as_16h16_reprovam_no_doctor(self, lar: Path) -> None:
        estado = await _estado("xbox", [Jogador("sem_caminho"), Jogador(), Jogador(), Jogador()])
        fio = _servir(_socket(lar), estado)
        saida = _doctor(lar, "check_o_modo_no_ar", _bin(lar, [], []))
        linhas = saida.splitlines()
        assert "[FAIL] P1: modo Xbox pedido, pad uhid no ar, sem queda dita" in linhas
        assert "[ OK ] P2: modo Xbox, pad uinput" in linhas
        assert sum(1 for ln in linhas if ln.startswith("[ OK ] P")) == 3
        assert not _NO_OU_ENDERECO.search(saida), saida
        fio.join(timeout=0.1)

    async def test_a_falha_de_um_instante_nao_reprova(self, lar: Path) -> None:
        """A recriação do pad no meio da leitura: a segunda leitura já vê o certo."""
        no_meio = await _estado("xbox", [Jogador("sem_caminho"), Jogador()])
        de_pe = await _estado("xbox", [Jogador(), Jogador()])
        _servir(_socket(lar), [no_meio, de_pe])
        saida = _doctor(lar, "check_o_modo_no_ar", _bin(lar, [], []))
        assert "[FAIL]" not in saida, saida
        assert "[ OK ] P1: modo Xbox, pad uinput" in saida.splitlines()

    async def test_controlar_o_pc_no_doctor_nao_e_ipc_mudo(self, lar: Path) -> None:
        _servir(_socket(lar), await _estado(None, [Jogador(), Jogador()], controlar_o_pc=True))
        saida = _doctor(lar, "check_o_modo_no_ar", _bin(lar, [], []))
        assert "[WARN]" not in saida and "[FAIL]" not in saida, saida
        assert "[ OK ] emulação desligada: nenhum jogador com pad e nenhum pad no ar" in saida

    async def test_a_queda_com_motivo_e_aviso_no_doctor(
        self, lar: Path, fabrica: dict[str, bool]
    ) -> None:
        fabrica["uhid"] = False
        _servir(_socket(lar), await _estado("dualsense", [Jogador()]))
        saida = _doctor(lar, "check_o_modo_no_ar", _bin(lar, [], []))
        assert "[WARN] P1: modo DualSense, pad uinput (queda dita: uhid_indisponivel)" in saida

    def test_a_noite_reprova_a_hora_no_doctor(self, lar: Path) -> None:
        _servir(_socket(lar), {"connected": True})
        diario = NOITE_DAEMON_ANTES + NOITE_DAEMON_DEPOIS
        saida = _doctor(lar, "check_a_hora_do_pad", _bin(lar, NOITE_KERNEL, diario))
        falhas = [ln for ln in saida.splitlines() if ln.startswith("[FAIL]")]
        assert len(falhas) == 3, saida
        assert "[FAIL] o pad Xbox das 05:29:00 levou 30,2 s para nascer" in saida
        assert "[ OK ] o pad Xbox das 05:30:02 nasceu em 0,5 s" in saida
        assert not _NO_OU_ENDERECO.search(saida), saida

    def test_o_boot_curado_passa_e_o_sem_kernel_avisa(self, lar: Path) -> None:
        _servir(_socket(lar), {"connected": True})
        saida = _doctor(lar, "check_a_hora_do_pad", _bin(lar, BOOT_KERNEL[:1], BOOT_DAEMON))
        assert "[ OK ] o pad Xbox das 03:01:35 nasceu em 0,0 s" in saida
        assert saida.count("[WARN]") == 4, saida
        assert "[FAIL]" not in saida

    def test_o_diario_do_daemon_vazio_nao_e_nenhum_pad(self, lar: Path) -> None:
        _servir(_socket(lar), {"connected": True})
        saida = _doctor(lar, "check_a_hora_do_pad", _bin(lar, BOOT_KERNEL, []))
        assert "o diário do daemon não tem a subida dele" in saida, saida
        assert "nenhum pad uinput nasceu" not in saida

    def test_a_linha_que_a_funcao_nao_le_avisa(self, lar: Path) -> None:
        """O formato do daemon mudou (aqui, com cor): o que sobra não é «nenhum pad»."""
        colorida = (
            "2026-09-28T03:01:35.426089-03:00 maquina hefesto-dualsense4unix[4242]: "
            "\x1b[2m2026-09-28T03:01:35.426089\x1b[0m [\x1b[32m\x1b[1minfo     \x1b[0m] "
            f"\x1b[1muinput_device_created\x1b[0m flavor=xbox name='{_XBOX}'"
        )
        _servir(_socket(lar), {"connected": True})
        binario = _bin(lar, BOOT_KERNEL, [BOOT_DAEMON[0], colorida])
        saida = _doctor(lar, "check_a_hora_do_pad", binario)
        assert "[WARN] a medida da hora de cada pad quebrou" in saida, saida
        assert "nenhum pad uinput nasceu" not in saida

    def test_as_duas_estao_no_main_e_leem_o_kernel_sem_o_k(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        assert "\n    check_o_modo_no_ar\n    check_a_hora_do_pad\n" in texto
        inicio = texto.index("check_a_hora_do_pad() {")
        corpo = texto[inicio : texto.index("\n}\n", inicio)]
        assert "_TRANSPORT=kernel" in corpo
        assert not re.search(r"journalctl\s+(-b\s+)?-k\b", corpo)

    def test_as_duas_so_leem(self) -> None:
        """O doctor confere e não cura: nada de restart, nada de escrita em aparelho."""
        texto = DOCTOR.read_text(encoding="utf-8")
        for nome in ("check_o_modo_no_ar", "check_a_hora_do_pad"):
            inicio = texto.index(f"{nome}() {{")
            corpo = texto[inicio : texto.index("\n}\n", inicio)]
            corpo = corpo.replace("2>/dev/null", "").replace(">/dev/null", "")
            assert not re.search(r"systemctl|udevadm|setfacl|restart|> */dev/", corpo), nome
