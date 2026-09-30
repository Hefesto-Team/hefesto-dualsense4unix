"""A luz e o mudo do microfone obedecem ao jogo (A-LUZ-E-O-MUDO-DO-MICROFONE-OBEDECEM-AO-JOGO-01).

**A DECISÃO** (D-2909-O-MICROFONE-OBEDECE-AO-JOGO, por delegação, a validar por
ela; revoga a D-2909-A-LUZ-DO-MIC-NAO-OBEDECE-AO-JOGO). O princípio é dela, de
29/09, ~21h20: *«Garantir que o inpút do joogo chegue ao controle do  # (noqa-acento) dela
jogador. Aí se o jogo (…) desliga e liga o microfone do user (…) aí o  # (noqa-acento) dela
controle obedece»*.
Com pad virtual DualSense, P1 a P4, cabo e rádio: a luz (`common[8]`) vai ao
plástico literal; o mudo (`common[9]` 0x10) cala ou abre o microfone do
jogador; o eco do driver do pad não conta; o botão e o 🎙 dela valem na hora
(vale o último que mandou, e o instante do botão é o do aperto).

AS RÉGUAS, na ordem da sprint
------------------------------------------------------------------------------
1. o pedido de luz acende, pisca e apaga a luz do controle DAQUELE jogador, e o
   report que o handle monta (0x02 e 0x31) leva o `common[8]`;
2. o pedido de mudo cala e abre o microfone dele, com a palavra do rádio, e
   nada além (nem o eleitor, nem o disco, nem recado);
3. o eco do driver não conta; a janela é uma por aperto e se abre onde o
   report SAI;
4. o botão físico sempre vale: ou o jogo responde a ele, ou ele vale sozinho;
5. o 🎙 da tela também é dela;
6. o jogo solta;
7. quatro jogadores, no tempo;
8. sem jogo, o pedido fica retido;
9. o `state_full`.

A cena é a do produto: o `UhidDualSense` sobre o /dev/uhid de mentira da
O-BOTAO, os ralos de produção (`gamepad.make_primary_replica_sinks` e o
`CoopManager._make_player_replica_sinks`), o `EventBus` real, o laço da luz e o
laço do mudo de produção, e o handle de PRODUÇÃO de cada controle
(`_PinnedPyDualSense`, o que monta o report de saída). Os números dos bits vêm
do `hid-playstation`, escritos à mão aqui, nunca do módulo testado. Os
endereços são da faixa forjada de fixture (`aa:bb:cc`).
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
import sys
import threading
import time
import types
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey, mic_da_mesa, recado_do_microfone
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import maquina
from tests.unit.test_o_botao_do_mic_grava_no_perfil import (
    ESPERA_DAS_GUARDAS_S,
    FREESTYLE,
    _Daemon,
    _drenar,
    _Eleitor,
    _Kernel,
    _reconectar,
    casa,  # noqa: F401 — a fixture da cena do botão, a mesma da régua irmã
)
from tests.unit.test_o_botao_e_a_luz_do_microfone_no_jogo import (
    _blueprint,
    _evento_de_output,
    _UhidPorFd,
    uhid,  # noqa: F401 — o /dev/uhid de mentira da O-BOTAO
)

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"
OS_QUATRO = (P1, P2, P3, P4)

# --- os números do `hid-playstation`, escritos à mão --------------------------
#: `DS_OUTPUT_VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE` e
#: `DS_OUTPUT_VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE` (`valid_flag1`), e o
#: `LIGHTBAR_CONTROL_ENABLE`.
_FLAG1_LUZ = 0x01
_FLAG1_MUDO = 0x02
_FLAG1_BARRA = 0x04
#: `DS_OUTPUT_POWER_SAVE_CONTROL_MIC_MUTE` (`power_save_control`).
_BIT_MUDO = 0x10
#: `mute_button_led` e `power_save_control` no `struct
#: dualsense_output_report_common`: o nono e o décimo byte.
_BYTE_LUZ = 8
_BYTE_MUDO = 9
#: `UHID_START` e `UHID_CLOSE` do `linux/uhid.h`.
_UHID_START = 2
_UHID_CLOSE = 5


def _com_dois_pontos(uniq: str) -> str:
    """A forma do `uniq` do evdev (a identidade do co-op): `aa:bb:cc:…`."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2))


# ---------------------------------------------------------------------------
# O relógio do pad, os reports do jogo e do driver
# ---------------------------------------------------------------------------


class _Relogio:
    """O relógio virtual do pad (o teto de 250 Hz e a janela do eco andam nele)."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def andar(self, segundos: float) -> None:
        self.t += segundos


def _saida(
    *, luz: int | None = None, mudo: bool | None = None, flag1: int = 0,
    barra: tuple[int, int, int] | None = None,
) -> bytes:
    """O UHID_OUTPUT de um report 0x02 com a luz, o mudo e a barra pedidos."""
    corpo = bytearray(47)
    corpo[1] = flag1
    if luz is not None:
        corpo[1] |= _FLAG1_LUZ
        corpo[_BYTE_LUZ] = luz
    if mudo is not None:
        corpo[1] |= _FLAG1_MUDO
        corpo[_BYTE_MUDO] = _BIT_MUDO if mudo else 0
    if barra is not None:
        corpo[1] |= _FLAG1_BARRA
        corpo[44:47] = bytes(barra)
    return _evento_de_output(bytes(corpo))


def _eco_do_driver(mudo: bool) -> bytes:
    """O que o `dualsense_output_worker` manda ao alternar o mudo: 0x03, luz, 0x10."""
    return _saida(luz=int(mudo), mudo=mudo)


def _pad(
    jogador: int,
    ralos: dict[str, Any],
    relogio: _Relogio,
    *,
    fim_de_sessao: Callable[[], None] | None = None,
) -> UhidDualSense:
    """O pad de PRODUÇÃO, com os ralos de produção, numa sessão de jogo aberta."""
    pad = UhidDualSense(player=jogador, blueprint=_blueprint())
    pad.time_fn = relogio
    pad.mic_led_sink = ralos["mic_led_sink"]
    pad.mic_mute_sink = ralos["mic_mute_sink"]
    pad.session_end_sink = fim_de_sessao
    assert pad.start()
    pad._game_open = True
    pad._bound_at = relogio() - 10.0
    return pad


def _mandar(pad: UhidDualSense, relogio: _Relogio, evento: bytes, passo: float = 0.02) -> None:
    """O jogo escreve no hidraw do pad, e o tique entrega (o teto de 250 Hz passa)."""
    relogio.andar(passo)
    pad._handle_output(evento)
    pad.pump_ff()


# ---------------------------------------------------------------------------
# O aparelho: o handle de PRODUÇÃO de cada controle
# ---------------------------------------------------------------------------


def _handle() -> Any:
    """O `_PinnedPyDualSense` sem device: só o estado que o `_build_common` lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    return h


class _Aparelho:
    """Os controles físicos como o daemon os vê, com o handle de produção de cada um.

    A luz e o mudo vão ao handle pelo método DELE (`set_microphone_led`,
    `set_microphone_mute`), e o report que sai é o que ele monta. O firmware
    obedece à ordem do mudo no report seguinte, como o aparelho.
    """

    def __init__(self, uniqs: tuple[str, ...], transportes: tuple[str, ...] = ()) -> None:
        self.uniqs = list(uniqs)
        self.transporte = dict(
            zip(uniqs, transportes or ("usb",) * len(uniqs), strict=True)
        )
        self.handles = {u: _handle() for u in uniqs}
        self.firmware = dict.fromkeys(uniqs, False)
        self.luzes: list[tuple[str, int | None]] = []
        self.mudos: list[tuple[str, bool | None]] = []
        #: O `common` que saiu a cada ordem de mudo (a posse de pé).
        self.commons_do_mudo: list[tuple[str, bytes]] = []
        self.primary_uniq = uniqs[0]

    def _u(self, uniq: str | None) -> str | None:
        chave = norm_mac(str(uniq or ""))
        return chave if chave in self.handles else None

    def set_microphone_led(self, valor: Any, *, uniq: str | None = None) -> bool:
        u = self._u(uniq)
        if u is None:
            return False
        self.luzes.append((u, valor))
        self.handles[u].set_microphone_led(valor)
        return True

    def set_microphone_mute(self, mudo: bool | None, *, uniq: str | None = None) -> bool:
        u = self._u(uniq)
        if u is None:
            return False
        self.mudos.append((u, mudo))
        self.handles[u].set_microphone_mute(mudo)
        if mudo is not None:
            self.firmware[u] = bool(mudo)
            self.commons_do_mudo.append((u, self.common(u)))
        return True

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        u = self._u(uniq)
        return None if u is None else self.handles[u]._mic_mute_desejado

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        u = self._u(uniq)
        if u is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": self.firmware[u]}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {"index": i, "connected": True, "transport": self.transporte[u],
             "is_primary": i == 0, "uniq": u, "battery_pct": 90}
            for i, u in enumerate(self.uniqs)
        ]

    def report(self, uniq: str) -> bytearray:
        """O report de saída que o handle monta: 0x02 no cabo, 0x31 no rádio."""
        common = self.handles[uniq]._build_common(rumble_asserted=False)
        if self.transporte[uniq] == "bt":
            return rep.build_bt_report(common)
        return rep.build_usb_report(common)

    def common(self, uniq: str) -> bytes:
        """O `common` de dentro do report que sai, lido do report e não do handle."""
        report = self.report(uniq)
        inicio = 3 if report[0] == rep.BT_REPORT_ID else 1
        return bytes(report[inicio : inicio + rep.COMMON_LEN])

    def luzes_de(self, uniq: str) -> list[int | None]:
        return [v for u, v in self.luzes if u == uniq]

    def mudos_de(self, uniq: str) -> list[bool | None]:
        return [m for u, m in self.mudos if u == uniq]


class _EleitorQueAnota:
    """Todo toque no eleitor fica anotado: o pedido do jogo não elege nada."""

    def __init__(self) -> None:
        self.__dict__["toques"] = []

    def __getattr__(self, nome: str) -> Any:
        self.toques.append(nome)
        return MagicMock()


class _DaemonDoJogo:
    """O daemon mínimo que os ralos, o laço da luz e o do mudo tocam.

    `_run_blocking` sem keywords, como o real.
    """

    def __init__(self, aparelho: _Aparelho, *, autoridade: str = "unknown") -> None:
        self.bus = EventBus()
        self.controller = aparelho
        self.display_authority = autoridade
        self.config = SimpleNamespace(mic_button_toggles_system=True)
        self._eleitor_de_microfone = _EleitorQueAnota()
        self._tasks: list[asyncio.Task[Any]] = []
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


class _Palavra:
    """A palavra do rádio: um dizedor, um esquecedor e um leitor que anotam."""

    def __init__(self) -> None:
        self.de_pe: dict[str, bool] = {}
        self.ditos: list[tuple[str, bool]] = []
        self.esquecidos: list[str] = []

    def dizer(self, uniq: str, ligado: bool) -> bool:
        chave = norm_mac(uniq) or uniq
        self.ditos.append((chave, bool(ligado)))
        self.de_pe[chave] = bool(ligado)
        return True

    def esquecer(self, uniq: str) -> bool:
        chave = norm_mac(uniq) or uniq
        self.esquecidos.append(chave)
        self.de_pe.pop(chave, None)
        return True

    def ler(self, uniq: str) -> bool | None:
        return self.de_pe.get(norm_mac(uniq) or uniq)


@pytest.fixture
def palavra() -> Iterator[_Palavra]:
    """A palavra de produção (`eleicao_de_microfone`), devolvida no fim."""
    p = _Palavra()
    anteriores = elm.registrar_dizedor_do_no_ar(p.dizer, p.esquecer, p.ler)
    try:
        yield p
    finally:
        elm.registrar_dizedor_do_no_ar(*anteriores)


@pytest.fixture(autouse=True)
def _a_bancada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O lar de mentira, as cadências da luz encolhidas e os registros limpos.

    A PEÇA A responde «ninguém ouve» (a luz decide ACESA ou APAGADA pelo mudo)
    e a PEÇA B não existe: nada disto chama `pactl`.
    """
    for nome in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(nome, str(tmp_path / nome.lower()))
    monkeypatch.setattr(luz, "INTERVALO_S", 0.001)
    monkeypatch.setattr(luz, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(luz, "ESPERA_DO_REPORT_S", 0.001)
    monkeypatch.setattr(luz, "SEGURA_A_BORDA_S", 0.2)
    monkeypatch.setattr(luz, "_fontes_para", lambda _uniqs, _mesa: {})
    peca_a = types.ModuleType(luz.MODULO_DE_QUEM_OUVE)
    peca_a.quem_ouve_agora = lambda uniqs: {u: [] for u in uniqs}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, luz.MODULO_DE_QUEM_OUVE, peca_a)
    monkeypatch.setitem(sys.modules, luz.MODULO_DO_NIVEL, types.ModuleType(luz.MODULO_DO_NIVEL))
    registros = (
        luz._LUZ_DO_JOGO, luz._A_PESSOA_MANDOU_EM, luz._DECIDIDO, luz._OUVINTES,
        hotkey._MUDO_DO_JOGO, hotkey._ECO_DO_ATO, gp._RETIDO_JA_DITO,
    )
    for r in registros:
        r.clear()
    yield
    for r in registros:
        r.clear()


async def _ate(cond: Callable[[], bool], segundos: float = 3.0) -> None:
    """Espera a condição, com o laço girando; reprova no prazo."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if cond():
            return
        await asyncio.sleep(0.002)
    assert cond(), "a condição não chegou no prazo"


@contextlib.asynccontextmanager
async def _lacos(daemon: Any, *extras: Any) -> AsyncIterator[None]:
    """O laço da luz e o laço do mudo de produção no ar (e os extras pedidos)."""
    tarefas = [
        asyncio.create_task(luz.luz_do_mic_loop(daemon)),
        asyncio.create_task(hotkey.mic_do_jogo_loop(daemon)),
        *[asyncio.create_task(laco(daemon)) for laco in extras],
    ]
    await _ate(lambda: daemon.bus.subscriber_count(str(EventTopic.MIC_DO_JOGO)) >= 2)
    try:
        yield
    finally:
        daemon._parando = True
        todas = [*tarefas, *daemon._tasks]
        for t in todas:
            t.cancel()
        await asyncio.gather(*todas, return_exceptions=True)
        daemon._tasks.clear()
        daemon._parando = False


def _eventos(fila: asyncio.Queue[Any]) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    while True:
        try:
            saida.append(fila.get_nowait())
        except asyncio.QueueEmpty:
            return saida


# ===========================================================================
# 1. O pedido de luz acende, pisca e apaga a luz do controle daquele jogador
# ===========================================================================


class TestALuzDoJogoVaiAoPlastico:
    """Mordidas: o laço da luz ignorando o pedido; o aplicador mirando o primário."""

    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    async def test_a_luz_do_p2_chega_ao_p2_literal(
        self, uhid: _UhidPorFd, palavra: _Palavra, transporte: str  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1, P2), transportes=("usb", transporte))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(2, CoopManager(daemon)._make_player_replica_sinks(_com_dois_pontos(P2)),
                   relogio)
        try:
            async with _lacos(daemon):
                await _ate(lambda: aparelho.luzes_de(P2) == [luz.ACESA])
                for valor in (1, 2, 0):
                    _mandar(pad, relogio, _saida(luz=valor))
                    await _ate(lambda v=valor: luz.luz_do_mic_do_jogo(P2) == v)  # type: ignore[misc]
                    await _ate(lambda v=valor: aparelho.luzes_de(P2)[-1] == v)  # type: ignore[misc]
                    common = aparelho.common(P2)
                    assert common[1] & _FLAG1_LUZ, "o report não autoriza a luz"
                    assert common[_BYTE_LUZ] == valor, (
                        f"no {transporte}, o report do P2 não leva a luz {valor} do jogo"
                    )
                    # A tela segue dizendo o microfone, e não a luz do jogo.
                    assert luz.estado_da_luz_do_mic(P2) == luz.ACESA
                assert aparelho.luzes_de(P1) == [luz.ACESA], (
                    f"a luz que o jogo pediu ao P2 chegou ao P1: {aparelho.luzes_de(P1)}"
                )
                assert luz.luz_do_mic_do_jogo(P1) is None
        finally:
            pad.stop()
        assert pad.mic_led_do_jogo == 0  # o stop zera a conta


# ===========================================================================
# 2. O pedido de mudo cala e abre o microfone dele, e nada além
# ===========================================================================


@pytest.fixture
def espioes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """O disco e o recado anotam: o pedido do jogo não chega a nenhum dos dois."""
    anotados: dict[str, list[Any]] = {"disco": [], "recado": []}
    monkeypatch.setattr(
        maquina, "gravar_o_mudo_do_microfone",
        lambda *a, **k: anotados["disco"].append(a) or True,
    )
    monkeypatch.setattr(
        recado_do_microfone, "anotar", lambda *a, **k: anotados["recado"].append(k)
    )
    return anotados


class TestOMudoDoJogo:
    """Mordidas: o jogo pelo `ligar_o_microfone` (o disco e o eleitor reprovam);
    sem a palavra do rádio no calar; `dizer_no_ar(uniq, not mudo)` no abrir."""

    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    async def test_cala_e_abre_o_microfone_do_p3(
        self, uhid: _UhidPorFd, palavra: _Palavra, espioes: dict[str, list[Any]],  # noqa: F811
        transporte: str,
    ) -> None:
        aparelho = _Aparelho((P1, P3), transportes=("usb", transporte))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(3, CoopManager(daemon)._make_player_replica_sinks(_com_dois_pontos(P3)),
                   relogio)
        try:
            async with _lacos(daemon):
                _mandar(pad, relogio, _saida(mudo=True))
                await _ate(lambda: aparelho.mudos_de(P3) == [True, None])
                assert aparelho.firmware[P3] is True
                (quem, common), = aparelho.commons_do_mudo
                assert quem == P3
                assert common[1] & _FLAG1_MUDO and common[_BYTE_MUDO] & _BIT_MUDO, (
                    f"no {transporte}, o report do P3 não leva o mudo do jogo"
                )
                assert palavra.ditos == [(P3, False)], "calar não disse «não» ao rádio"

                _mandar(pad, relogio, _saida(mudo=False))
                await _ate(lambda: aparelho.mudos_de(P3) == [True, None, False, None])
                assert aparelho.firmware[P3] is False
                assert palavra.esquecidos == [P3], "abrir não esqueceu o «não» de pé"
                assert (P3, True) not in palavra.ditos, (
                    "abrir o microfone pôs no ar pelo rádio: isso é de quem ouve"
                )
        finally:
            pad.stop()
        assert aparelho.mudos_de(P1) == []
        assert daemon._eleitor_de_microfone.toques == [], "o pedido do jogo tocou o eleitor"
        assert espioes["disco"] == [], "o pedido do jogo foi ao disco"
        assert espioes["recado"] == [], "o pedido do jogo escreveu recado"

    async def test_abrir_nao_mexe_na_palavra_dela_no_ar(
        self, uhid: _UhidPorFd, palavra: _Palavra, espioes: dict[str, list[Any]]  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P3,))
        aparelho.firmware[P3] = True
        palavra.de_pe[P3] = True  # ela pôs no ar
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(3, CoopManager(daemon)._make_player_replica_sinks(P3), relogio)
        try:
            async with _lacos(daemon):
                _mandar(pad, relogio, _saida(mudo=False))
                await _ate(lambda: aparelho.mudos_de(P3) == [False, None])
        finally:
            pad.stop()
        assert palavra.ditos == [] and palavra.esquecidos == []
        assert palavra.de_pe == {P3: True}


# ===========================================================================
# 3. O eco do driver não conta
# ===========================================================================


class _Ralos:
    """Os dois ralos do microfone, anotando (e a barra, para o eco que a traz)."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, Any]] = []

    def ligar(self, pad: UhidDualSense) -> None:
        pad.mic_led_sink = lambda v: self.chamadas.append(("luz", v)) or True
        pad.mic_mute_sink = lambda m: self.chamadas.append(("mudo", m)) or True
        pad.lightbar_sink = lambda r, g, b: self.chamadas.append(("barra", (r, g, b)))

    def do_microfone(self) -> list[tuple[str, Any]]:
        return [c for c in self.chamadas if c[0] in ("luz", "mudo")]


@pytest.fixture
def pad_e_ralos(uhid: _UhidPorFd) -> Iterator[tuple[UhidDualSense, _Ralos, _Relogio]]:  # noqa: F811
    relogio = _Relogio()
    ralos = _Ralos()
    pad = UhidDualSense(player=1, blueprint=_blueprint())
    pad.time_fn = relogio
    ralos.ligar(pad)
    assert pad.start()
    pad._game_open = True
    pad._bound_at = relogio() - 10.0
    try:
        yield pad, ralos, relogio
    finally:
        pad.stop()


class TestOEcoDoDriver:
    """Mordidas: todo 0x03 como eco; nenhum como eco; a janela sem teto; a janela
    que não se consome; a janela aberta no `forward_mic_button`."""

    def test_o_eco_depois_da_borda_nao_conta(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        pad.forward_mic_button(True)
        antes = pad.output_count
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.005)
        assert ralos.chamadas == []
        assert pad.mic_eco_do_driver == 1
        assert pad.output_count == antes, "o eco puro contou como escrita de jogo"

    def test_o_mesmo_report_sem_borda_e_o_jogo(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        _mandar(pad, relogio, _eco_do_driver(True))
        assert ralos.do_microfone() == [("luz", 1), ("mudo", True)], (
            "o jogo que fala a língua da Sony (o 0x03 inteiro) foi jogado fora"
        )
        assert pad.mic_eco_do_driver == 0

    def test_a_janela_vencida_e_o_jogo(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(True), passo=uhid_gamepad.ECO_DO_DRIVER_S + 0.1)
        assert ralos.do_microfone() == [("luz", 1), ("mudo", True)]
        assert pad.mic_eco_do_driver == 0

    def test_a_resposta_do_jogo_depois_do_eco_chega(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.005)
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.02)
        assert pad.mic_eco_do_driver == 1, "a janela é uma por aperto"
        assert ralos.do_microfone() == [("luz", 1), ("mudo", True)], (
            "a resposta do jogo ao aperto sumiu como se fosse eco"
        )

    def test_o_eco_com_a_barra_entrega_so_a_barra(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        pad.forward_mic_button(True)
        relogio.andar(0.005)
        corpo = _saida(luz=1, mudo=True, barra=(1, 2, 3))
        pad._handle_output(corpo)
        assert ralos.chamadas == [("barra", (1, 2, 3))]
        assert pad.mic_eco_do_driver == 1

    def test_o_dedo_reentregue_depois_do_start_abre_janela(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio]
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.005)
        # Driver novo (o `UHID_START`), com o dedo ainda no botão: o próximo
        # report que SAIR é borda para ele, sem `forward_mic_button` novo.
        pad._handle_event(struct.pack("<I", _UHID_START))
        pad._bound_at = relogio() - 10.0
        pad.forward_buttons(frozenset({"cross"}))
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.005)
        assert pad.mic_eco_do_driver == 2, "a reentrega depois do START não abriu janela"
        assert ralos.do_microfone() == []

    def test_o_eco_que_chega_antes_de_o_write_voltar_e_eco(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O kernel agenda o eco DENTRO do `write` do report que traz a borda.

        O `kworker` pode entregar o 0x02 ao fio do uhid antes de o `write`
        voltar à thread que emitiu; o fio o atende na hora. A janela tem de
        estar aberta para ele nesse instante, e não só depois do `write`.
        Mordida: a janela aberta sem a trava do emissor (o fio acha o deque
        vazio e entrega o eco aos ralos como se fosse o jogo).
        """
        pad, ralos, relogio = pad_e_ralos
        real = pad.send_report
        fios: list[threading.Thread] = []

        def _send_com_o_eco_no_meio(report: bytes) -> bool:
            ok = real(report)
            fio = threading.Thread(
                target=pad._handle_output, args=(_eco_do_driver(True),), daemon=True
            )
            fios.append(fio)
            fio.start()
            # O fio do uhid atende enquanto o emissor ainda está no `write`.
            fio.join(timeout=0.3)
            return ok

        monkeypatch.setattr(pad, "send_report", _send_com_o_eco_no_meio)
        relogio.andar(0.005)
        pad.forward_mic_button(True)
        monkeypatch.setattr(pad, "send_report", real)
        for fio in fios:
            fio.join(timeout=5.0)
            assert not fio.is_alive()
        pad.pump_ff()
        assert ralos.do_microfone() == [], (
            "o eco que chegou antes de o write voltar foi entregue como pedido do jogo"
        )
        assert pad.mic_eco_do_driver == 1

    def test_o_report_que_nao_saiu_nao_abre_janela(
        self, pad_e_ralos: tuple[UhidDualSense, _Ralos, _Relogio], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pad, ralos, relogio = pad_e_ralos
        monkeypatch.setattr(pad, "send_report", lambda _r: False)
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.005)
        assert pad.mic_eco_do_driver == 0
        assert ralos.do_microfone() == [("luz", 1), ("mudo", True)]


# ===========================================================================
# 4. O botão físico sempre vale
# ===========================================================================


class _KernelComLuz(_Kernel):
    """O `_Kernel` da régua irmã, com o instante do aperto e a luz do plástico.

    `segurar` deixa o laço das bordas sem ver o aperto até `soltar_a_borda`:
    é a cena em que o jogo responde antes de o Hefesto processar a borda.
    """

    def __init__(self, uniqs: tuple[str, ...], **kw: Any) -> None:
        super().__init__(uniqs, **kw)
        self._em: dict[str, float] = {}
        self._seq_visto = dict(self._seq)
        self.segurar = False
        self.luzes: list[tuple[str, Any]] = []

    @property
    def primary_uniq(self) -> str:
        return self.uniqs[0]

    def apertar(self, uniq: str) -> float:
        super().apertar(uniq)
        self._em[uniq] = time.monotonic()
        if not self.segurar:
            self._seq_visto[uniq] = self._seq[uniq]
        return self._em[uniq]

    def soltar_a_borda(self, uniq: str) -> None:
        self._seq_visto[uniq] = self._seq[uniq]

    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {
            u: (self._seq_visto[u], self._pedido.get(u, self._firmware_mudo[u]), self._em.get(u))
            for u in self.uniqs
        }

    def set_microphone_led(self, valor: Any, *, uniq: str | None = None) -> bool:
        self.luzes.append((norm_mac(str(uniq or "")) or str(uniq), valor))
        return True

    def luzes_de(self, uniq: str) -> list[Any]:
        return [v for u, v in self.luzes if u == uniq]


def _daemon_da_casa(casa: Any, kernel: _KernelComLuz) -> Any:  # noqa: F811
    store = StateStore()
    store.set_active_profile(FREESTYLE)
    daemon = _Daemon(kernel, store, _Eleitor())
    casa.subsystem._config = daemon.config
    return daemon


def _atos(registros: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in registros if r.get("event") == "mic_ato"]


class TestOBotaoFisicoSempreVale:
    """Mordidas: o pad esquecendo o dedup no aperto (cena 1); a borda sem o
    `a_pessoa_mandou` (cena 1b); o laço do botão sem adotar a resposta (cena 2);
    o ato carimbando a hora dele em vez do `em` da borda (cena 2); um pedido mais
    velho vencendo (cena 3)."""

    async def _cena(self, casa: Any, kernel: _KernelComLuz) -> tuple[Any, UhidDualSense, _Relogio]:  # noqa: F811
        daemon = _daemon_da_casa(casa, kernel)
        relogio = _Relogio()
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio)
        return daemon, pad, relogio

    @staticmethod
    def _o_aperto_no_pad(pad: UhidDualSense, relogio: _Relogio, mudo_do_driver: bool) -> None:
        """O jogo vê o botão; o driver do pad ecoa; o dedo sobe."""
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(mudo_do_driver), passo=0.004)
        pad.forward_mic_button(False)

    async def test_o_jogo_que_reafirma_nao_desfaz_o_aperto(
        self, casa: Any, uhid: _UhidPorFd  # noqa: F811
    ) -> None:
        casa.perfil(FREESTYLE)
        kernel = _KernelComLuz((P1,), transportes=("bt",))
        daemon, pad, relogio = await self._cena(casa, kernel)
        assert await hotkey.nascer_no_ar(daemon, P1) is True
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        quadro = _saida(luz=0, mudo=False)  # a língua da Sony: aberto

        async def _quadros(n: int) -> None:
            for _ in range(n):
                _mandar(pad, relogio, quadro, passo=1 / 60)
                await asyncio.sleep(0)

        try:
            async with _lacos(daemon, hotkey.mic_button_loop, mic_da_mesa.mic_da_mesa_loop):
                await _drenar(ESPERA_DAS_GUARDAS_S)
                await _quadros(30)
                await _ate(lambda: luz.luz_do_mic_do_jogo(P1) == 0)
                with structlog.testing.capture_logs() as registros:
                    kernel.apertar(P1)
                    self._o_aperto_no_pad(pad, relogio, mudo_do_driver=True)
                    await _quadros(300)  # cinco segundos do jogo reafirmando
                    await _ate(lambda: len(_atos(registros)) == 1)
                    await _drenar(0.4)
                assert _atos(registros)[0]["ligado"] is False, "o aperto não calou"
                assert kernel.mudo_no_firmware(P1) is True, (
                    "o jogo que só reafirma o «aberto» desfez o mudo que ela pediu"
                )
                assert luz.luz_do_mic_do_jogo(P1) is None
                assert luz.estado_da_luz_do_mic(P1) == luz.APAGADA
                assert kernel.luzes_de(P1)[-1] == luz.APAGADA
                assert [sorted(e) for e in _eventos(espiao)] == [
                    ["em", "luz", "uniq"], ["em", "mudo", "uniq"]
                ], "os reportes repetidos chegaram aos ralos"
                # O jogo MUDA o pedido: a luz volta ao jogo.
                _mandar(pad, relogio, _saida(luz=1, mudo=False))
                await _ate(lambda: kernel.luzes_de(P1)[-1:] == [1])
                assert luz.luz_do_mic_do_jogo(P1) == 1
                assert kernel.mudo_no_firmware(P1) is True
        finally:
            pad.stop()

    async def test_o_aperto_devolve_a_luz_a_ela_mesmo_sem_o_ato(
        self, casa: Any, uhid: _UhidPorFd  # noqa: F811
    ) -> None:
        """Cena 1b: com o botão fora do sistema, a borda ainda é ordem dela."""
        casa.perfil(FREESTYLE)
        kernel = _KernelComLuz((P1,))
        daemon, pad, relogio = await self._cena(casa, kernel)
        daemon.config.mic_button_toggles_system = False
        try:
            async with _lacos(daemon, hotkey.mic_button_loop, mic_da_mesa.mic_da_mesa_loop):
                await _drenar(ESPERA_DAS_GUARDAS_S)
                _mandar(pad, relogio, _saida(luz=2))
                await _ate(lambda: kernel.luzes_de(P1)[-1:] == [2])
                kernel.apertar(P1)
                await _ate(lambda: luz.luz_do_mic_do_jogo(P1) is None)
                await _ate(lambda: kernel.luzes_de(P1)[-1] != 2)
        finally:
            pad.stop()

    async def _cena_calada(self, casa: Any) -> tuple[Any, UhidDualSense, _Relogio, _KernelComLuz]:  # noqa: F811
        """P1 calado pelo dono e fora do ar: o aperto dela pede LIGAR."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P1)
        kernel = _KernelComLuz((P1,), transportes=("usb",))
        daemon, pad, relogio = await self._cena(casa, kernel)
        assert await _reconectar(daemon, P1) is False
        assert kernel.mudo_no_firmware(P1) is True
        return daemon, pad, relogio, kernel

    async def test_o_jogo_que_responde_antes_do_ato_decide_o_aperto(
        self, casa: Any, uhid: _UhidPorFd  # noqa: F811
    ) -> None:
        daemon, pad, relogio, kernel = await self._cena_calada(casa)
        try:
            async with _lacos(daemon, hotkey.mic_button_loop, mic_da_mesa.mic_da_mesa_loop):
                await _drenar(ESPERA_DAS_GUARDAS_S)
                with structlog.testing.capture_logs() as registros:
                    kernel.segurar = True
                    kernel.apertar(P1)  # o aperto pede LIGAR
                    self._o_aperto_no_pad(pad, relogio, mudo_do_driver=True)
                    # A resposta do jogo ao aperto, na língua da Sony: calado.
                    _mandar(pad, relogio, _saida(luz=1, mudo=True))
                    await _ate(lambda: P1 in hotkey._MUDO_DO_JOGO)
                    kernel.soltar_a_borda(P1)
                    await _ate(lambda: len(_atos(registros)) == 1)
                    await _drenar(0.5)
                assert _atos(registros)[0]["ligado"] is False, "o ato não adotou a resposta"
                assert any(r.get("event") == "mic_ato_segue_o_jogo" for r in registros)
                assert kernel.mudo_no_firmware(P1) is True, (
                    "a luz do jogo diz calado e o microfone ficou aberto"
                )
                assert kernel.luzes_de(P1)[-1] == 1, "a luz da resposta do jogo caiu"
                assert casa.mudo_no_dono(P1) is True, "o disco não guardou o sentido do aperto"
        finally:
            pad.stop()

    async def test_a_resposta_depois_do_ato_fica_com_o_jogo(
        self, casa: Any, uhid: _UhidPorFd  # noqa: F811
    ) -> None:
        daemon, pad, relogio, kernel = await self._cena_calada(casa)
        try:
            async with _lacos(daemon, hotkey.mic_button_loop, mic_da_mesa.mic_da_mesa_loop):
                await _drenar(ESPERA_DAS_GUARDAS_S)
                with structlog.testing.capture_logs() as registros:
                    kernel.apertar(P1)
                    self._o_aperto_no_pad(pad, relogio, mudo_do_driver=True)
                    await _ate(lambda: len(_atos(registros)) == 1)
                assert _atos(registros)[0]["ligado"] is True
                _mandar(pad, relogio, _saida(luz=1, mudo=True))
                await _ate(lambda: kernel.mudo_no_firmware(P1) is True)
                await _ate(lambda: kernel.luzes_de(P1)[-1:] == [1])
                await _drenar(0.3)
                assert kernel.mudo_no_firmware(P1) is True, "o estado final não é o do jogo"
        finally:
            pad.stop()

    async def test_o_pedido_velho_nao_ganha_a_luz_nem_o_ato(
        self, casa: Any, uhid: _UhidPorFd  # noqa: F811
    ) -> None:
        daemon, pad, _relogio, kernel = await self._cena_calada(casa)
        try:
            async with _lacos(daemon, hotkey.mic_button_loop, mic_da_mesa.mic_da_mesa_loop):
                await _drenar(ESPERA_DAS_GUARDAS_S)
                with structlog.testing.capture_logs() as registros:
                    kernel.segurar = True
                    em = kernel.apertar(P1)  # o aperto pede LIGAR
                    velho = em - 0.5
                    topico = str(EventTopic.MIC_DO_JOGO)
                    daemon.bus.publish(topico, {"uniq": P1, "luz": 2, "em": velho})
                    daemon.bus.publish(topico, {"uniq": P1, "mudo": True, "em": velho})
                    await _ate(lambda: P1 in hotkey._MUDO_DO_JOGO)
                    await _ate(lambda: luz.luz_do_mic_do_jogo(P1) == 2)
                    kernel.soltar_a_borda(P1)
                    await _ate(lambda: len(_atos(registros)) == 1)
                    await _drenar(0.4)
                assert _atos(registros)[0]["ligado"] is True, (
                    "o pedido mais velho que o aperto decidiu o sentido dele"
                )
                assert luz.luz_do_mic_do_jogo(P1) is None, "o pedido velho ficou com a luz"
                assert kernel.luzes_de(P1)[-1] == luz.ACESA
                assert kernel.mudo_no_firmware(P1) is False
                # E o velho que só chega depois do ato não o desfaz.
                daemon.bus.publish(
                    str(EventTopic.MIC_DO_JOGO), {"uniq": P1, "mudo": True, "em": velho}
                )
                await _drenar(0.3)
                assert kernel.mudo_no_firmware(P1) is False, (
                    "um pedido do jogo mais velho que o aperto desfez o aperto"
                )
        finally:
            pad.stop()


# ===========================================================================
# 5. O 🎙 da tela também é dela
# ===========================================================================


async def test_o_clique_da_tela_derruba_o_pedido_do_jogo(
    casa: Any, uhid: _UhidPorFd  # noqa: F811
) -> None:
    """Mordida: tirar o `a_pessoa_mandou` do `ligar_o_microfone`."""
    casa.perfil(FREESTYLE)
    kernel = _KernelComLuz((P1,))
    daemon = _daemon_da_casa(casa, kernel)
    async with _lacos(daemon):
        daemon.bus.publish(
            str(EventTopic.MIC_DO_JOGO), {"uniq": P1, "luz": 2, "em": time.monotonic()}
        )
        await _ate(lambda: kernel.luzes_de(P1)[-1:] == [2])
        await hotkey.ligar_o_microfone(daemon, _com_dois_pontos(P1), ligado=True)
        assert luz.luz_do_mic_do_jogo(P1) is None, "o clique dela não derrubou o pedido"
        await _ate(lambda: kernel.luzes_de(P1)[-1] == luz.ACESA)


# ===========================================================================
# 6. O jogo solta
# ===========================================================================


class TestOJogoSolta:
    """Mordidas: sem o `mic_led_sink(None)` no fim da sessão; a marca da luz
    dentro do `if not self._game_dirty: return`; a entrega do microfone
    ligando o `_game_dirty`."""

    async def test_o_close_devolve_a_luz_e_o_mudo_fica(
        self, uhid: _UhidPorFd, palavra: _Palavra  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1,))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        fins: list[int] = []
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio,
                   fim_de_sessao=lambda: fins.append(1))
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        try:
            async with _lacos(daemon):
                _mandar(pad, relogio, _saida(luz=1, mudo=True))
                await _ate(lambda: aparelho.luzes_de(P1)[-1:] == [1])
                await _ate(lambda: aparelho.mudos_de(P1) == [True, None])
                pad._handle_event(struct.pack("<I", _UHID_CLOSE))
                eventos = _eventos(espiao)
                assert [k for e in eventos for k in ("luz", "mudo", "solta") if k in e] == [
                    "luz", "mudo", "solta"
                ], f"o fim da sessão não soltou a luz: {eventos}"
                await _ate(lambda: aparelho.luzes_de(P1)[-1] == luz.APAGADA)
                assert luz.luz_do_mic_do_jogo(P1) is None
                assert aparelho.firmware[P1] is True, "o fim da sessão mexeu no mudo"
                assert fins == [], "a sessão que só falou do microfone repintou o perfil"
        finally:
            pad.stop()

    async def test_sem_luz_na_sessao_nada_e_publicado(
        self, uhid: _UhidPorFd, palavra: _Palavra  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1,))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio)
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        try:
            _mandar(pad, relogio, _saida(mudo=True))
            pad._handle_event(struct.pack("<I", _UHID_CLOSE))
            assert ["solta" in e for e in _eventos(espiao)] == [False]
        finally:
            pad.stop()

    async def test_no_fio_do_uhid_o_tique_entrega_a_soltura(
        self, uhid: _UhidPorFd, palavra: _Palavra  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1,))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio)
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        try:
            _mandar(pad, relogio, _saida(luz=3))
            pad._fio_do_uhid = threading.current_thread()  # o CLOSE chega pelo fio
            pad._handle_event(struct.pack("<I", _UHID_CLOSE))
            assert ["solta" in e for e in _eventos(espiao)] == [False]
            pad.pump_ff()  # o tique
            assert ["solta" in e for e in _eventos(espiao)] == [True]
        finally:
            pad._fio_do_uhid = None
            pad.stop()


class TestOEnderecoDoPedido:
    """O pedido vai ao controle do jogador pelo endereço dele, e só a ele.

    Mordidas: o laço da luz esquecendo o pedido do controle que saiu da mesa (o
    rádio que cai e volta no meio do jogo perde a luz do jogo, e o dedup do pad
    não a reenvia); o aplicador caindo no primário quando o alvo não é MAC.
    """

    async def test_o_radio_que_cai_e_volta_traz_a_luz_do_jogo(
        self, uhid: _UhidPorFd, palavra: _Palavra  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1, P2), transportes=("usb", "bt"))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        pad = _pad(2, CoopManager(daemon)._make_player_replica_sinks(_com_dois_pontos(P2)),
                   relogio)
        try:
            async with _lacos(daemon):
                _mandar(pad, relogio, _saida(luz=2))
                await _ate(lambda: aparelho.luzes_de(P2)[-1:] == [2])
                # O rádio do P2 cai (sai da mesa) e volta com o handle novo; o
                # pad virtual fica, e o jogo não repete o que já pediu.
                aparelho.uniqs.remove(P2)
                await _ate(lambda: luz.estado_da_luz_do_mic(P2) is None)
                aparelho.handles[P2] = _handle()
                aparelho.uniqs.append(P2)
                _mandar(pad, relogio, _saida(luz=2))  # o jogo reafirma: o dedup segura
                await _ate(lambda: aparelho.common(P2)[_BYTE_LUZ] == 2)
                assert aparelho.luzes_de(P2)[-1] == 2
                assert luz.luz_do_mic_do_jogo(P2) == 2
                assert pad.mic_led_do_jogo == 1, "o dedup do pad reenviou o mesmo pedido"
        finally:
            pad.stop()

    async def test_o_jogador_sem_mac_nunca_difunde(
        self, uhid: _UhidPorFd, palavra: _Palavra  # noqa: F811
    ) -> None:
        aparelho = _Aparelho((P1,))
        daemon = _DaemonDoJogo(aparelho)
        relogio = _Relogio()
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        pad = _pad(2, CoopManager(daemon)._make_player_replica_sinks("path:/dev/input/event9"),
                   relogio)
        try:
            _mandar(pad, relogio, _saida(luz=1, mudo=True))
            assert _eventos(espiao) == [], "o pedido de um jogador sem MAC foi difundido"
            assert pad.mic_led_do_jogo == 0 and pad.mic_mudo_do_jogo == 0
            # «Retido» é a pergunta da prova 5 (quem escreve sem jogo?); o
            # jogador sem MAC não a responde.
            assert pad.mic_do_jogo_retido == 0, "o descartado sem endereço contou como retido"
        finally:
            pad.stop()


# ===========================================================================
# 7. Quatro jogadores, no tempo
# ===========================================================================


async def test_quatro_jogadores_trinta_segundos(uhid: _UhidPorFd, palavra: _Palavra) -> None:  # noqa: F811
    """Mordida: o ralo do co-op mirando o P1."""
    aparelho = _Aparelho(OS_QUATRO, transportes=("usb", "bt", "bt", "bt"))
    daemon = _DaemonDoJogo(aparelho)
    coop = CoopManager(daemon)
    relogio = _Relogio()
    pads = [_pad(1, gp.make_primary_replica_sinks(daemon), relogio)] + [
        _pad(i + 1, coop._make_player_replica_sinks(_com_dois_pontos(u)), relogio)
        for i, u in enumerate(OS_QUATRO[1:], start=1)
    ]
    luz_de: dict[str, int | None] = dict.fromkeys(OS_QUATRO)
    mudo_de: dict[str, bool] = dict.fromkeys(OS_QUATRO, False)
    try:
        async with _lacos(daemon):
            t = 0.0
            passo = 0
            while t < 30.0:
                dono = passo % 4
                u = OS_QUATRO[dono]
                if (passo // 4) % 2:
                    aparelho.transporte[u] = "usb" if aparelho.transporte[u] == "bt" else "bt"
                if passo % 2 == 0:
                    valor = (passo // 2 + dono) % 4
                    _mandar(pads[dono], relogio, _saida(luz=valor), passo=1.5)
                    luz_de[u] = valor
                    await _ate(lambda u=u, v=valor: luz.luz_do_mic_do_jogo(u) == v)  # type: ignore[misc]
                    await _ate(lambda u=u, v=valor: aparelho.luzes_de(u)[-1] == v)  # type: ignore[misc]
                    assert aparelho.common(u)[_BYTE_LUZ] == valor
                else:
                    mudo = not mudo_de[u]
                    _mandar(pads[dono], relogio, _saida(mudo=mudo), passo=1.5)
                    mudo_de[u] = mudo
                    await _ate(lambda u=u, m=mudo: aparelho.firmware[u] is m)  # type: ignore[misc]
                for outro in OS_QUATRO:
                    assert luz.luz_do_mic_do_jogo(outro) == luz_de[outro], (
                        f"t={t:.1f}s: o pedido do P{dono + 1} chegou ao {outro}"
                    )
                    assert aparelho.firmware[outro] is mudo_de[outro], (
                        f"t={t:.1f}s: o mudo do P{dono + 1} chegou ao {outro}"
                    )
                t += 1.5
                passo += 1
            await _ate(lambda: all(aparelho.microphone_mute_for(u) is None for u in OS_QUATRO))
            for p in pads:
                p.pump_ff()
                assert p._replica_pending == {}, "ficou pedido preso no pad"
    finally:
        for p in pads:
            p.stop()


# ===========================================================================
# 8. Sem jogo, o pedido fica retido
# ===========================================================================


class TestSemJogoORetido:
    """Mordidas: sem o portão da autoridade; contar antes do `_replicating()`."""

    @pytest.mark.parametrize(
        ("autoridade", "aplica"), [("daemon", False), ("game", True), ("unknown", True)]
    )
    def test_a_autoridade_decide(
        self, uhid: _UhidPorFd, autoridade: str, aplica: bool  # noqa: F811
    ) -> None:
        daemon = _DaemonDoJogo(_Aparelho((P1,)), autoridade=autoridade)
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        relogio = _Relogio()
        ralos = gp.make_primary_replica_sinks(daemon)
        pad = _pad(1, ralos, relogio)
        try:
            _mandar(pad, relogio, _saida(luz=2, mudo=True))
            eventos = _eventos(espiao)
            if aplica:
                assert [e.get("luz", e.get("mudo")) for e in eventos] == [2, True]
                assert (pad.mic_led_do_jogo, pad.mic_mudo_do_jogo) == (1, 1)
                assert pad.mic_do_jogo_retido == 0
            else:
                assert eventos == [], "sem jogo, o pedido do cliente chegou aos donos"
                assert pad.mic_do_jogo_retido == 2
                assert (pad.mic_led_do_jogo, pad.mic_mudo_do_jogo) == (0, 0)
                assert ralos["mic_led_sink"](2) is False
        finally:
            pad.stop()

    def test_o_retido_vale_quando_o_jogo_chega(self, uhid: _UhidPorFd) -> None:  # noqa: F811
        """O mesmo pedido, reafirmado com o jogo em foco, chega (o retido não deduplica)."""
        daemon = _DaemonDoJogo(_Aparelho((P1,)), autoridade="daemon")
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        relogio = _Relogio()
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio)
        try:
            _mandar(pad, relogio, _saida(luz=2))
            daemon.display_authority = "game"
            _mandar(pad, relogio, _saida(luz=2))
            assert [e.get("luz") for e in _eventos(espiao)] == [2]
        finally:
            pad.stop()

    def test_antes_da_carencia_nada_e_lido(self, uhid: _UhidPorFd) -> None:  # noqa: F811
        daemon = _DaemonDoJogo(_Aparelho((P1,)))
        espiao = daemon.bus.subscribe(str(EventTopic.MIC_DO_JOGO))
        relogio = _Relogio()
        pad = _pad(1, gp.make_primary_replica_sinks(daemon), relogio)
        pad._bound_at = relogio()  # o probe ainda escreve
        try:
            pad._handle_output(_saida(luz=2, mudo=True))
            pad.pump_ff()
            assert _eventos(espiao) == []
            assert pad.mic_led_do_jogo_amostra is None
            assert pad.mic_mudo_do_jogo_amostra is None
            assert (pad.mic_led_do_jogo, pad.mic_do_jogo_retido) == (0, 0)
        finally:
            pad.stop()


# ===========================================================================
# 9. O `state_full`
# ===========================================================================


class _ControleComMicrofone(FakeController):  # type: ignore[misc]
    """O `FakeController` que diz a mesa e o estado de áudio do P1."""

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"index": 0, "connected": True, "transport": "usb",
                 "is_primary": True, "uniq": P1, "battery_pct": 90}]

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": False}


@pytest.fixture
async def servidor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uhid: _UhidPorFd  # noqa: F811
) -> AsyncIterator[tuple[Path, Any]]:
    perfis = tmp_path / "profiles"
    perfis.mkdir()

    def _perfis(ensure: bool = False) -> Path:
        if ensure:
            perfis.mkdir(parents=True, exist_ok=True)
        return perfis

    monkeypatch.setattr(loader_module, "profiles_dir", _perfis)
    fc = _ControleComMicrofone(transport="usb")
    fc.connect()
    store = StateStore()
    daemon = MagicMock()
    daemon._last_state = None
    daemon.config = MagicMock(
        mouse_emulation_enabled=False, mouse_speed=6, mouse_scroll_speed=1,
        rumble_policy="balanceado", rumble_policy_custom_mult=0.7, rumble_active=None,
    )
    daemon._motion_reader = SimpleNamespace(emit_hz=0.0)
    daemon._coop_manager = None
    caminho = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc, store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=caminho, daemon=daemon,
    )
    await server.start()
    try:
        yield caminho, daemon
    finally:
        await server.stop()


async def _state_full(caminho: Path) -> dict[str, Any]:
    async with IpcClient.connect(caminho) as cliente:
        resultado: dict[str, Any] = await cliente.call("daemon.state_full")
    return resultado


_CHAVES_DO_PAD = (
    "mic_led_do_jogo", "mic_led_do_jogo_amostra", "mic_mudo_do_jogo",
    "mic_mudo_do_jogo_amostra", "mic_eco_do_driver", "mic_do_jogo_retido",
)


class TestOStateFull:
    """Mordida: sem uma das chaves (no pad ou no controle), reprova."""

    async def test_o_pad_e_o_controle_dizem_o_que_o_jogo_pediu(
        self, servidor: tuple[Path, Any]
    ) -> None:
        caminho, daemon = servidor
        relogio = _Relogio()
        ralos = _Ralos()
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.time_fn = relogio
        ralos.ligar(pad)
        assert pad.start()
        pad._game_open = True
        pad._bound_at = relogio() - 10.0
        pad.forward_mic_button(True)
        _mandar(pad, relogio, _eco_do_driver(True), passo=0.004)
        _mandar(pad, relogio, _saida(luz=2, mudo=True))
        daemon._gamepad_device = pad
        luz._LUZ_DO_JOGO[P1] = (2, time.monotonic())
        try:
            resultado = await _state_full(caminho)
        finally:
            pad.stop()
        item = dict(resultado["rumble_ff"]["per_vpad"][0])
        assert {k: item[k] for k in _CHAVES_DO_PAD} == {
            "mic_led_do_jogo": 1, "mic_led_do_jogo_amostra": 2,
            "mic_mudo_do_jogo": 1, "mic_mudo_do_jogo_amostra": True,
            "mic_eco_do_driver": 1, "mic_do_jogo_retido": 0,
        }
        assert "mic_led_do_jogo_recusado" not in item
        (controle,) = resultado["controllers"]
        assert controle["audio"]["luz_do_mic_do_jogo"] == 2

    async def test_o_pad_dublado_publica_zero_e_nada(self, servidor: tuple[Path, Any]) -> None:
        caminho, daemon = servidor
        daemon._gamepad_device = SimpleNamespace(
            backend="uinput", flavor="xbox360",
            **{nome: MagicMock() for nome in _CHAVES_DO_PAD},
        )
        resultado = await _state_full(caminho)
        item = dict(resultado["rumble_ff"]["per_vpad"][0])
        assert {k: item[k] for k in _CHAVES_DO_PAD} == {
            "mic_led_do_jogo": 0, "mic_led_do_jogo_amostra": None,
            "mic_mudo_do_jogo": 0, "mic_mudo_do_jogo_amostra": None,
            "mic_eco_do_driver": 0, "mic_do_jogo_retido": 0,
        }
        (controle,) = resultado["controllers"]
        assert "luz_do_mic_do_jogo" not in controle["audio"], (
            "sem pedido do jogo de pé, a chave apareceu no controle"
        )
