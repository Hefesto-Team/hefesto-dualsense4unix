"""O tique tem orçamento e a manutenção não para a entrada.

O-TIQUE-TEM-ORCAMENTO-E-A-MANUTENCAO-NAO-PARA-A-ENTRADA-01. O `_poll_loop` de
produção roda aqui, num daemon de mentira que declara tudo o que o laço usa
(`test_o_duble_do_poll_loop_acompanha_o_produto` cobra o irmão de cada uso).

Mordidas (arranque a cura, veja reprovar, devolva):

- `_agendar_o_sinal_de_jogo`: troque o `create_task(...)` por rodar
  `daemon._gather_game_signal_inputs()` no fio do laço, e a primeira reprova;
- `RELOGIOS_LENTOS`: ponha a fase `0.0` em todos, e a segunda reprova;
- `_MedidorDoTique.registrar`: tire o `bump("poll.tique.estouros")`, e a terceira
  reprova.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor, ipc_client
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal


@pytest.fixture(autouse=True)
def _o_laco_sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    """O que o laço faz e toca a máquina (co-op, máscaras, `/proc`) fica de fora."""
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)


class _Pad:
    def forward_analog(self, **_kw: int) -> None: ...
    def forward_buttons(self, _pressed: frozenset[str]) -> None: ...


class _DaemonDeLaco:
    """O `_poll_loop` de produção com o controle na mesa e o pad virtual de pé."""

    def __init__(self, *, gather_s: float = 0.0, tiques: int = 40, poll_hz: int = 60) -> None:
        estado = ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        self.config = SimpleNamespace(poll_hz=poll_hz, auto_reconnect=False)
        self.controller: Any = SimpleNamespace(
            is_connected=lambda: True, read_state=lambda: estado
        )
        self.store = StateStore()
        self.bus = SimpleNamespace(publish=lambda *_a, **_k: None)
        self._stop_event: asyncio.Event | None = None
        self._input_ready_at = 0.0
        self._external_tick_task: Any = None
        self._steam_jogo_task: Any = None
        self._game_signal: Any = GameSignal()
        self._appid_da_evidencia: Any = None
        self._last_state: Any = None
        self._gamepad_device: Any = _Pad()
        self._mouse_device: Any = None
        self._keyboard_device: Any = None
        self._touchpad_reader: Any = None
        self._hotkey_manager: Any = None
        self._plugins_subsystem: Any = None
        self._paused = False
        self._native_mode = False
        self._emulation_suppressed = False
        self._emu_calada_motivo: Any = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._coop_manager = co.CoopManager.__new__(co.CoopManager)
        self._coop_manager._players = {}
        self._coop_manager._daemon = self  # type: ignore[assignment]
        self._poll_loop = Daemon._poll_loop.__get__(self)
        self._run_blocking = MethodType(Daemon._run_blocking, self)
        self._sync_game_signal = MethodType(Daemon._sync_game_signal, self)
        self._evdev_buttons_once: Callable[[], frozenset[str]] = frozenset
        self._restantes = tiques
        self._gather_s = gather_s
        self.inicio_do_tique = 0.0
        self.numero_do_tique = 0
        self.atrasos_da_entrada: list[tuple[int, float]] = []
        self.despachos: dict[int, float] = {}
        self.tiques_do_gather: set[int] = set()

    def _is_stopping(self) -> bool:
        self.inicio_do_tique = time.perf_counter()
        self.numero_do_tique += 1
        self._restantes -= 1
        return self._restantes < 0

    def _dispatch_gamepad_emulation(self, *_a: Any) -> None:
        agora = time.perf_counter()
        self.atrasos_da_entrada.append((self.numero_do_tique, agora - self.inicio_do_tique))
        self.despachos[self.numero_do_tique] = agora

    def _gather_game_signal_inputs(self) -> dict[str, Any]:
        self.tiques_do_gather.add(self.numero_do_tique)
        time.sleep(self._gather_s)
        return {
            "window_healthy": True,
            "window_class_current": None,
            "window_seen_age": None,
            "profile_rule_match": False,
            "marker": None,
            "marker_pid_alive": False,
            "marker_pid": None,
            "exit_marker": None,
            "exit_pid": None,
            "appid_de_jogo_vivo": None,
            "session_open": False,
            "now": time.time(),
        }

    def _sync_identity_registry(self) -> None: ...
    def _seguir_a_carta(self) -> None: ...
    def aplicar_gamepad_para_multiplos_controles(self) -> None: ...
    def _amostrar_bateria(self, _agora: float) -> None: ...
    def _schedule_external_tick(self) -> None: ...
    def _schedule_steam_jogo_tick(self) -> None: ...
    def _reconciliar_exposicao_do_modo_nativo(self, **_k: object) -> None: ...
    def _drenar_modo_pendente(self) -> None: ...
    def _reassert_rumble(self, _agora: float) -> None: ...
    def _jogo_no_controle_do_desktop(self) -> None:
        return None

    def _calar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _liberar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _prime_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_mouse_emulation(self, *_a: Any) -> None: ...

    async def rodar(self) -> None:
        self._stop_event = asyncio.Event()
        try:
            await self._poll_loop()
            tarefa = getattr(self, "_game_signal_task", None)
            if tarefa is not None:
                await asyncio.gather(tarefa, return_exceptions=True)
        finally:
            self._executor.shutdown(wait=True)


def _uma_so_fase(monkeypatch: pytest.MonkeyPatch, *relogios: tuple[str, float, float]) -> None:
    monkeypatch.setattr(lc, "RELOGIOS_LENTOS", relogios)


# 1. O gather lento do sinal de jogo não segura a entrada


def test_o_gather_de_50_ms_nao_atrasa_a_entrada_do_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O sinal de jogo vira tarefa: o tique que o agenda encaminha a entrada na hora.

    MORDIDA: em `_agendar_o_sinal_de_jogo`, rode o `_gather_game_signal_inputs` no
    fio do laço em vez de `create_task` — o atraso do tique sobe a 50 ms.
    """
    _uma_so_fase(monkeypatch, ("sinal_de_jogo", 0.25, 0.0))
    daemon = _DaemonDeLaco(gather_s=0.050, tiques=70)

    asyncio.run(daemon.rodar())

    assert len(daemon.tiques_do_gather) >= 3, "o relógio do sinal de jogo não andou"
    atrasos = [
        atraso for tique, atraso in daemon.atrasos_da_entrada if tique in daemon.tiques_do_gather
    ]
    assert len(atrasos) >= 3, "nenhum tique que carregou o sinal encaminhou a entrada"
    mediana = statistics.median(atrasos)
    # O defeito é de 50 ms; 5 ms deixa folga ao jitter de uma máquina carregada.
    assert mediana < 0.005, f"a entrada esperou {mediana * 1000:.1f} ms pelo sinal de jogo"
    # E o tique SEGUINTE também não espera: o intervalo entre despachos fica no período.
    intervalos = [
        max(
            daemon.despachos.get(t + 1, 0.0) - daemon.despachos.get(t, 0.0),
            daemon.despachos.get(t, 0.0) - daemon.despachos.get(t - 1, 0.0),
        )
        for t in daemon.tiques_do_gather
        if t - 1 in daemon.despachos and t + 1 in daemon.despachos
    ]
    assert intervalos, "sem despachos vizinhos dos tiques que carregaram o sinal"
    assert statistics.median(intervalos) < 1.0 / 60.0 + 0.025, (
        f"o intervalo entre despachos chegou a {statistics.median(intervalos) * 1000:.1f} ms"
    )


def test_a_entrada_vai_antes_da_manutencao_no_mesmo_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No tique em que a identidade vence, o `dispatch` já foi ao jogo quando ela roda."""
    _uma_so_fase(monkeypatch, ("identidade", 0.10, 0.0))
    daemon = _DaemonDeLaco(tiques=20)
    ordem: list[str] = []
    antes = daemon._dispatch_gamepad_emulation

    def _manutencao() -> None:
        ordem.append("manutenção")

    def _entrada(*a: Any) -> None:
        ordem.append("entrada")
        antes(*a)

    daemon._sync_identity_registry = _manutencao  # type: ignore[method-assign]
    daemon._dispatch_gamepad_emulation = _entrada  # type: ignore[method-assign]

    asyncio.run(daemon.rodar())

    assert ordem.count("manutenção") >= 3, ordem
    assert ordem[0] == "entrada", ordem
    for i, quem in enumerate(ordem):
        if quem == "manutenção":
            assert ordem[i - 1] == "entrada", ordem[: i + 1]


# 2. A fase: um tique carrega no máximo dois relógios lentos


@pytest.mark.parametrize("poll_hz", [30, 60, 120])
def test_em_10_s_nenhum_tique_roda_mais_que_dois_relogios(poll_hz: int) -> None:
    """Dez segundos simulados: cada relógio vence do seu jeito, e nunca três juntos.

    MORDIDA: ponha `0.0` na fase de todo relógio de `RELOGIOS_LENTOS`.
    """
    periodo_do_tique = 1.0 / poll_hz
    relogios = lc._RelogiosLentos(0.0)
    disparos: dict[str, int] = {}
    pior = 0
    for passo in range(10 * poll_hz):
        vencidos = relogios.vencidos(passo * periodo_do_tique)
        pior = max(pior, len(vencidos))
        for nome in vencidos:
            disparos[nome] = disparos.get(nome, 0) + 1

    assert pior <= 2, f"um tique carregou {pior} relógios lentos"
    for nome, periodo, _fase in lc.RELOGIOS_LENTOS:
        esperados = int(10.0 / periodo)
        assert disparos.get(nome, 0) >= max(esperados - 1, 0), (
            f"o relógio {nome} disparou {disparos.get(nome, 0)}x em 10 s (período {periodo})"
        )


def test_a_fase_fica_na_grade_depois_de_um_atraso() -> None:
    """Um tique que atrasa não leva os relógios para o mesmo ponto da grade."""
    relogios = lc._RelogiosLentos(0.0)
    relogios.vencidos(0.0)
    relogios.vencidos(5.0)  # o laço ficou parado: todos vencidos, rearmados na grade
    depois = [relogios.vencidos(5.0 + i * 0.005) for i in range(1, 400)]

    assert max(len(v) for v in depois) <= 2


def test_o_relogio_retido_segue_vencido_e_dispara_ao_sair_da_retencao() -> None:
    relogios = lc._RelogiosLentos(0.0)

    assert "coop" not in relogios.vencidos(10.0, retidos=frozenset({"coop"}))
    assert "coop" in relogios.vencidos(10.01)
    assert "coop" not in relogios.vencidos(10.02)


def test_o_laco_de_producao_anda_pela_tabela_de_relogios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tabela é a do laço: um relógio de 0,1 s vence umas quatro vezes em 0,45 s."""
    _uma_so_fase(monkeypatch, ("identidade", 0.10, 0.0))
    daemon = _DaemonDeLaco(tiques=27)
    chamadas: list[float] = []
    daemon._sync_identity_registry = lambda: chamadas.append(time.monotonic())  # type: ignore[method-assign]

    asyncio.run(daemon.rodar())

    assert 3 <= len(chamadas) <= 6, chamadas


# 3. A medida: o estouro sobe o contador e o doctor diz a linha


def test_um_tique_de_30_ms_sobe_o_contador_e_o_doctor_imprime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um relógio lento que dorme 30 ms estoura o orçamento de 16,7 ms.

    MORDIDA: tire o `bump("poll.tique.estouros")` de `_MedidorDoTique.registrar`.
    """
    _uma_so_fase(monkeypatch, ("identidade", 0.10, 0.0))
    monkeypatch.setattr(lc, "JANELA_DO_MEDIDOR_DO_TIQUE", 16)
    daemon = _DaemonDeLaco(tiques=40)
    daemon._sync_identity_registry = lambda: time.sleep(0.030)  # type: ignore[method-assign]

    asyncio.run(daemon.rodar())

    contadores = daemon.store.snapshot().counters
    assert contadores["poll.tique.estouros"] >= 2, contadores
    assert contadores["poll.tique.medidos"] >= 16
    assert contadores["poll.tique.pior_us"] >= 30_000
    assert contadores["poll.tique.p99_us"] >= 30_000
    assert contadores["poll.tique.relogio.identidade"] >= 30_000
    assert contadores["poll.tique.relogio.entrada"] < 30_000

    class _Cliente:
        async def __aenter__(self) -> _Cliente:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

        async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            if metodo == "daemon.state_full":
                return {"counters": contadores}
            return {"profiles": []} if metodo == "profile.list" else {"paused": False}

    monkeypatch.setattr(ipc_client.IpcClient, "connect", lambda *_a, **_k: _Cliente())

    linhas = asyncio.run(cmd_doctor._daemon_checks())

    do_tique = [m for _tag, m in linhas if m.startswith("tique do laço")]
    assert len(do_tique) == 1, linhas
    assert "acima de 16,7 ms" in do_tique[0]
    assert "«identidade»" in do_tique[0], do_tique[0]
    assert f"{contadores['poll.tique.estouros']} de {contadores['poll.tique.medidos']}" in (
        do_tique[0]
    )


def test_o_doctor_sem_medida_nao_inventa_a_linha() -> None:
    assert cmd_doctor._linha_do_tique(None) is None
    assert cmd_doctor._linha_do_tique({}) is None
    assert cmd_doctor._linha_do_tique({"poll.tique.medidos": 0}) is None


def test_o_p99_da_janela_e_o_pior_de_cada_relogio() -> None:
    store = StateStore()
    medidor = lc._MedidorDoTique(store)
    for i in range(lc.JANELA_DO_MEDIDOR_DO_TIQUE):
        medidor.registrar(0.001 if i != 7 else 0.040, ["coop"] if i == 7 else [])

    c = store.snapshot().counters
    assert c["poll.tique.estouros"] == 1
    assert c["poll.tique.pior_us"] == 40_000
    assert c["poll.tique.p99_us"] == 1_000
    assert c["poll.tique.relogio.coop"] == 40_000
    assert c["poll.tique.relogio.entrada"] == 1_000


def test_a_falha_do_sinal_de_jogo_vai_ao_diario_e_nao_derruba_o_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O corpo da tarefa engole e registra: ninguém espera por ele para tratar o erro."""
    _uma_so_fase(monkeypatch, ("sinal_de_jogo", 0.05, 0.0))
    daemon = _DaemonDeLaco(tiques=12)

    async def _quebra() -> None:
        raise RuntimeError("falha de mentira")

    daemon._sync_game_signal = _quebra  # type: ignore[assignment]

    asyncio.run(daemon.rodar())

    assert daemon.numero_do_tique >= 12
    assert daemon.store.counter("poll.tique.medidos") >= 11


def test_o_sinal_de_jogo_nao_empilha_tarefas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enquanto a anterior não voltou, o relógio seguinte não agenda outra."""
    _uma_so_fase(monkeypatch, ("sinal_de_jogo", 0.02, 0.0))
    daemon = _DaemonDeLaco(gather_s=0.200, tiques=25)

    asyncio.run(daemon.rodar())

    assert len(daemon.tiques_do_gather) <= 3, daemon.tiques_do_gather


def test_a_reconciliacao_do_lancamento_sai_do_dispatch_e_do_await() -> None:
    """O `dispatch_gamepad` não varre mais o `/proc`, e o laço não espera pelo sinal.

    MORDIDA: devolva `_reconciliar_launch(daemon)` à primeira linha do `dispatch_gamepad`.
    """
    fonte = Path(gp.__file__).read_text(encoding="utf-8")
    corpo = fonte.split("def dispatch_gamepad(", 1)[1].split("\ndef ", 1)[0]
    assert "_reconciliar_launch(" not in corpo
    laco = Path(lc.__file__).read_text(encoding="utf-8").split("async def _poll_loop", 1)[1]
    laco = laco.split("    def _install_signal_handlers", 1)[0]
    assert "await self._sync_game_signal()" not in laco
    assert "_reconciliar_launch(self)" in laco

