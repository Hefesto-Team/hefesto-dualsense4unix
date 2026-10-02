"""O aperto acorda o tique (O-BOTAO-CHEGA-AO-JOGO-COMO-ELE-E-01, entrada -NA-HORA)."""

from __future__ import annotations

import ast
import asyncio
import itertools
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from tests.unit.test_uinput_mouse import _rel_sum, _started_device

_UNIQ = {n: f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)}


@dataclass
class _Evento:
    type: int
    code: int
    value: int


class _Pad:
    """O pad virtual de mentira: a hora de cada conjunto de botões que chega."""

    def __init__(self) -> None:
        self.botoes: list[tuple[float, frozenset[str]]] = []

    def forward_analog(self, **_kw: int) -> None:
        pass

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.botoes.append((time.monotonic(), frozenset(pressed)))

    def chegou(self, nome: str) -> float | None:
        return next((em for em, botoes in self.botoes if nome in botoes), None)


def _leitor(n: int) -> EvdevReader:
    return EvdevReader(device_path=Path(f"/nao/existe/event-do-p{n}"))


def _apertar(leitor: EvdevReader, codigo: int, valor: int) -> None:
    leitor._handle_event(_Evento(ecodes.EV_KEY, codigo, valor), ecodes)


def _gerente(leitores: dict[int, EvdevReader], pads: dict[int, _Pad]) -> co.CoopManager:
    gerente = co.CoopManager.__new__(co.CoopManager)
    gerente._players = {}
    for n, leitor in leitores.items():
        gerente._players[_UNIQ[n]] = co._SecondaryPlayer(
            identity=_UNIQ[n],
            evdev_path=f"/dev/input/event-do-p{n}",
            reader=leitor,
            player_index=n,
            vpad=pads[n],  # type: ignore[arg-type]
        )
    return gerente


@pytest.fixture(autouse=True)
def _o_laco_sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O que o laço faz e toca a máquina, ou não é o caminho do botão: a"""
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    yield
    er.definir_o_despertador(None)


class _LacoForaDaMesa:
    """O `_poll_loop` de produção com o primário fora da mesa: só o co-op anda."""

    def __init__(self, gerente: co.CoopManager, poll_hz: int) -> None:
        self.config = SimpleNamespace(poll_hz=poll_hz)
        self.controller: Any = SimpleNamespace(is_connected=lambda: False)
        self.store = StateStore()
        self._stop_event: asyncio.Event | None = None
        self._input_ready_at = 0.0
        self._external_tick_task: Any = None
        self._steam_jogo_task: Any = None
        self._coop_manager = gerente
        gerente._daemon = self
        self._poll_loop = Daemon._poll_loop.__get__(self)

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    def _sync_identity_registry(self) -> None: ...
    def _seguir_a_carta(self) -> None: ...
    def aplicar_gamepad_para_multiplos_controles(self) -> None: ...
    def _amostrar_bateria(self, _agora: float) -> None: ...
    def _schedule_external_tick(self) -> None: ...
    async def _sync_game_signal(self) -> None: ...
    def _schedule_steam_jogo_tick(self) -> None: ...
    def _reconciliar_exposicao_do_modo_nativo(self, **_k: object) -> None: ...
    def _drenar_modo_pendente(self) -> None: ...

    async def rodar(self, cenario: Callable[[], Awaitable[Any]]) -> Any:
        self._stop_event = asyncio.Event()
        laco = asyncio.create_task(self._poll_loop())
        try:
            return await cenario()
        finally:
            self._stop_event.set()
            await asyncio.wait_for(laco, timeout=3.0)


class _LacoNaMesa(_LacoForaDaMesa):
    """O mesmo laço com o primário na mesa, o analógico esquerdo parado no"""

    def __init__(
        self, gerente: co.CoopManager, poll_hz: int, leitor: EvdevReader, mouse: Any
    ) -> None:
        super().__init__(gerente, poll_hz)
        estado = ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb", raw_lx=255
        )
        self.controller = SimpleNamespace(
            is_connected=lambda: True, read_state=lambda: estado, _evdev=leitor
        )
        self.bus = SimpleNamespace(publish=lambda *_a, **_k: None)
        self._last_state: Any = None
        self._gamepad_device: Any = None
        self._mouse_device = mouse
        self._keyboard_device: Any = None
        self._touchpad_reader: Any = None
        self._hotkey_manager: Any = None
        self._plugins_subsystem: Any = None
        self._paused = False
        self._native_mode = False
        self._emulation_suppressed = False
        self._emu_calada_motivo: Any = None
        self._evdev_buttons_once = MethodType(Daemon._evdev_buttons_once, self)
        self._dispatch_gamepad_emulation = MethodType(Daemon._dispatch_gamepad_emulation, self)
        self._dispatch_mouse_emulation = MethodType(Daemon._dispatch_mouse_emulation, self)

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        return fn(*args)

    def _reassert_rumble(self, _agora: float) -> None: ...
    def _jogo_no_controle_do_desktop(self) -> None:
        return None

    def _calar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _liberar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _prime_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_keyboard_emulation(self, *_a: Any) -> None: ...


def _numa_thread(alvo: Callable[[], None]) -> threading.Thread:
    """Os eventos chegam numa thread, como a do leitor de verdade."""
    fio = threading.Thread(target=alvo, name="leitor-de-mentira", daemon=True)
    fio.start()
    return fio


def test_regua_6_os_jogadores_2_a_4_pelo_laco_de_producao() -> None:
    """Com o período em 1 s, o X do P3 chega ao pad dele em menos de 50 ms."""
    leitores = {n: _leitor(n) for n in (2, 3, 4)}
    pads = {n: _Pad() for n in (2, 3, 4)}
    daemon = _LacoForaDaMesa(_gerente(leitores, pads), poll_hz=1)
    apertou: dict[str, float] = {}

    def apertar() -> None:
        apertou["em"] = time.monotonic()
        _apertar(leitores[3], ecodes.BTN_SOUTH, 1)

    async def cenario() -> None:
        await asyncio.sleep(0.2)
        _numa_thread(apertar).join()
        await asyncio.sleep(0.15)

    asyncio.run(daemon.rodar(cenario))
    chegou = pads[3].chegou("cross")
    assert chegou is not None, "o X não chegou antes da volta do relógio"
    assert chegou - apertou["em"] < 0.050, f"{(chegou - apertou['em']) * 1000:.1f} ms"
    assert pads[2].chegou("cross") is None and pads[4].chegou("cross") is None


def test_regua_6_o_p1_pela_espera_com_o_vpad_de_pe() -> None:
    """O P1 na mesa, com o vpad de pé: o X chega pelo `dispatch_gamepad` de"""
    leitor = _leitor(1)
    pad = _Pad()
    daemon = SimpleNamespace(
        controller=SimpleNamespace(_evdev=leitor, is_connected=lambda: True),
        store=StateStore(),
        _gamepad_device=pad,
        _mouse_device=None,
        _input_ready_at=0.0,
        _last_state=ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        ),
        _coop_manager=_gerente({}, {}),
    )
    daemon._coop_manager._daemon = daemon
    daemon._evdev_buttons_once = MethodType(Daemon._evdev_buttons_once, daemon)
    daemon._dispatch_gamepad_emulation = MethodType(Daemon._dispatch_gamepad_emulation, daemon)
    apertou: dict[str, float] = {}

    def apertar() -> None:
        apertou["em"] = time.monotonic()
        _apertar(leitor, ecodes.BTN_SOUTH, 1)

    async def cenario() -> None:
        parada = asyncio.Event()
        espera = asyncio.create_task(lc._esperar_o_tique(daemon, parada, 1.0))
        await asyncio.sleep(0.1)
        _numa_thread(apertar).join()
        await asyncio.sleep(0.1)
        parada.set()
        await espera

    asyncio.run(cenario())
    chegou = pad.chegou("cross")
    assert chegou is not None and chegou - apertou["em"] < 0.050


def test_regua_6_no_assentamento_o_aperto_nao_vai_ao_jogo() -> None:
    """Dentro do grace (`_input_ready_at` no futuro), a volta acordada não"""
    leitores = {2: _leitor(2)}
    pads = {2: _Pad()}
    daemon = _LacoForaDaMesa(_gerente(leitores, pads), poll_hz=1)
    daemon._input_ready_at = float("inf")

    async def cenario() -> None:
        await asyncio.sleep(0.1)
        _numa_thread(lambda: _apertar(leitores[2], ecodes.BTN_SOUTH, 1)).join()
        await asyncio.sleep(0.1)

    asyncio.run(daemon.rodar(cenario))
    assert pads[2].botoes == []


def test_a_espera_tem_o_contrato_da_que_ela_substitui() -> None:
    """Sem aperto, o prazo acaba em `asyncio.TimeoutError`; com a parada, ela"""

    async def cenario() -> None:
        daemon = SimpleNamespace()
        parada = asyncio.Event()
        laco = asyncio.get_running_loop()
        inicio = laco.time()
        with pytest.raises(asyncio.TimeoutError):
            await lc._esperar_o_tique(daemon, parada, 0.05)
        assert 0.045 <= laco.time() - inicio < 0.2
        laco.call_later(0.02, parada.set)
        await lc._esperar_o_tique(daemon, parada, 5.0)

    asyncio.run(cenario())


def _esperas_do_poll_loop() -> tuple[int, int]:
    """(chamadas a `_esperar_o_tique`, esperas diretas na parada) no `_poll_loop`."""
    fonte = Path(lc.__file__).read_text(encoding="utf-8")
    laco = next(
        no
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop"
    )
    pelo_aperto = diretas = 0
    for no in ast.walk(laco):
        if not isinstance(no, ast.Call):
            continue
        if isinstance(no.func, ast.Name) and no.func.id == "_esperar_o_tique":
            pelo_aperto += 1
        elif (
            isinstance(no.func, ast.Attribute)
            and no.func.attr == "wait_for"
            and no.args
            and "stop_event" in ast.dump(no.args[0])
        ):
            diretas += 1
    return pelo_aperto, diretas


def test_regua_6_as_tres_esperas_do_laco_acordam_com_o_aperto() -> None:
    """As três esperas do `_poll_loop` (fora da mesa, assentamento, fim do"""
    assert _esperas_do_poll_loop() == (3, 0)


def test_regua_7_quatro_leitores_a_100_apertos_nao_passam_de_250_voltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro leitores (o do P1 fora da mesa também acorda) a 100 apertos por"""
    leitores = {n: _leitor(n) for n in (2, 3, 4)}
    pads = {n: _Pad() for n in (2, 3, 4)}
    todos = [_leitor(1), *leitores.values()]
    daemon = _LacoForaDaMesa(_gerente(leitores, pads), poll_hz=1)
    voltas: list[float] = []
    original = lc._volta_do_aperto

    def contar(d: Any) -> None:
        voltas.append(time.monotonic())
        original(d)

    monkeypatch.setattr(lc, "_volta_do_aperto", contar)
    duracao = 1.0

    def martelar() -> None:
        fim = time.monotonic() + duracao
        while time.monotonic() < fim:
            for leitor in todos:
                _apertar(leitor, ecodes.BTN_SOUTH, 1)
                _apertar(leitor, ecodes.BTN_SOUTH, 0)
            time.sleep(0.01)

    async def cenario() -> None:
        await asyncio.sleep(0.05)
        fio = _numa_thread(martelar)
        while fio.is_alive():
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.05)

    asyncio.run(daemon.rodar(cenario))
    assert len(voltas) >= 20, f"o aperto não acordou o laço ({len(voltas)} voltas)"
    menor = min(b - a for a, b in itertools.pairwise(voltas))
    assert menor >= lc.INTERVALO_MINIMO_DA_VOLTA_S, f"{menor * 1000:.2f} ms"
    assert len(voltas) <= 250 * (duracao + 0.2)


def _corrida_da_navegacao(
    monkeypatch: pytest.MonkeyPatch, *, com_apertos: bool
) -> tuple[int, int, int]:
    """(`poll.tick`, REL_X somado, voltas acordadas) em 1 s de laço a 60 Hz."""
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)
    mouse, modulo, no_do_mouse = _started_device(monkeypatch, poll_hz=60)
    leitor = _leitor(1)
    daemon = _LacoNaMesa(_gerente({}, {}), 60, leitor, mouse)

    def martelar() -> None:
        fim = time.monotonic() + 1.0
        while time.monotonic() < fim:
            _apertar(leitor, ecodes.BTN_NORTH, 1)
            time.sleep(0.005)
            _apertar(leitor, ecodes.BTN_NORTH, 0)
            time.sleep(0.005)

    async def cenario() -> None:
        if com_apertos:
            fio = _numa_thread(martelar)
            while fio.is_alive():
                await asyncio.sleep(0.02)
        else:
            await asyncio.sleep(1.0)

    asyncio.run(daemon.rodar(cenario))
    return (
        daemon.store.counter("poll.tick"),
        _rel_sum(no_do_mouse, modulo.REL_X),
        daemon.store.counter("poll.volta_do_aperto"),
    )


def test_regua_9_a_volta_acordada_nao_mexe_no_relogio_do_resto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mouse emulado ligado e o analógico parado no fundo: 100 apertos por"""
    tiques_sem, rel_x_sem, voltas_sem = _corrida_da_navegacao(monkeypatch, com_apertos=False)
    tiques_com, rel_x_com, voltas_com = _corrida_da_navegacao(monkeypatch, com_apertos=True)
    assert tiques_sem >= 30 and rel_x_sem > 0
    folga = max(3, tiques_sem // 10)
    assert abs(tiques_com - tiques_sem) <= folga, (tiques_sem, tiques_com)
    por_tique = rel_x_sem / tiques_sem
    assert abs(rel_x_com - rel_x_sem) <= folga * por_tique + 2, (rel_x_sem, rel_x_com)
    assert voltas_sem == 0 and voltas_com >= 20, (voltas_sem, voltas_com)
