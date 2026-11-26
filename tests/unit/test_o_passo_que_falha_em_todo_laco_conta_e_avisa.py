"""O passo que falha em todo laço do serviço conta no store e avisa uma vez por episódio.

Um caso por laço: o passo levanta três vezes seguidas, o store soma 3 em ``<laço>.erro.<passo>``
e o diário tem um ``warning``; depois de um acerto, a próxima falha avisa de novo. A varredura
por AST reprova ``except Exception`` só com ``logger.debug`` nas funções de laço.
"""
from __future__ import annotations

import ast
import asyncio
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon import passos_do_laco
from hefesto_dualsense4unix.daemon.state_store import StateStore

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

FUNCOES_DE_LACO: tuple[tuple[str, str], ...] = (
    ("daemon/subsystems/luz_animada.py", "tique_do_laco"),
    ("daemon/subsystems/governador_do_radio.py", "_laco"),
    ("daemon/subsystems/gamepad.py", "_bater_os_eventos_do_jogo"),
    ("daemon/subsystems/gamepad.py", "andar_os_acionadores"),
    ("daemon/lifecycle.py", "_sync_external_leds"),
    ("daemon/sensor_hub.py", "_loop_manutencao"),
    ("daemon/subsystems/conexoes.py", "_laco"),
    ("daemon/subsystems/volta_dos_acessorios.py", "tique"),
    ("daemon/subsystems/external_identity.py", "tick"),
)

ROTEIRO: tuple[bool, ...] = (True, True, True, False, True)


class _Roteiro:
    """Levanta ou acerta conforme o roteiro; ``True`` levanta."""

    def __init__(self, roteiro: tuple[bool, ...] = ROTEIRO) -> None:
        self._roteiro = list(roteiro)
        self.chamadas = 0

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        self.chamadas += 1
        if self._roteiro.pop(0):
            raise KeyError("perfil antigo")
        return 0

    @property
    def acabou(self) -> bool:
        return not self._roteiro


class _EventoDoRoteiro:
    """O ``threading.Event`` do laço em fio: para quando o roteiro acaba, sem esperar."""

    def __init__(self, roteiro: _Roteiro) -> None:
        self._roteiro = roteiro

    def is_set(self) -> bool:
        return self._roteiro.acabou

    def wait(self, _timeout: float | None = None) -> bool:
        return self._roteiro.acabou


@pytest.fixture
def store_do_processo(monkeypatch: pytest.MonkeyPatch) -> StateStore:
    store = StateStore()
    monkeypatch.setattr(passos_do_laco, "_store_do_processo", store)
    return store


def _avisos(diario: list[dict[str, Any]], laco: str, passo: str) -> int:
    return sum(
        1 for e in diario
        if e.get("log_level") == "warning" and e.get("event") == "passo_do_laco_falhou"
        and e.get("laco") == laco and e.get("passo") == passo
    )


def _conferir(store: StateStore, diario: list[dict[str, Any]], laco: str, passo: str) -> None:
    assert store.counter(f"{laco}.erro.{passo}") == 4
    assert _avisos(diario, laco, passo) == 2


def _por_tique(chamar: Callable[[], Any], store: StateStore, laco: str, passo: str) -> None:
    with capture_logs() as diario:
        for _ in range(3):
            chamar()
        assert store.counter(f"{laco}.erro.{passo}") == 3
        assert _avisos(diario, laco, passo) == 1
        chamar()
        chamar()
    _conferir(store, diario, laco, passo)


def test_a_luz_animada_conta_e_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import luz_animada

    roteiro = _Roteiro()
    monkeypatch.setattr(luz_animada.Passo, "__call__", lambda self, agora: roteiro(agora))
    daemon = SimpleNamespace(store=StateStore())
    passo = luz_animada.Passo(daemon, SimpleNamespace())
    _por_tique(lambda: passo.tique_do_laco(0.0), daemon.store, "luz_animada", "tique")


def test_o_governador_do_radio_conta_e_avisa(store_do_processo: StateStore) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import GovernadorDoRadio

    governador = GovernadorDoRadio(registrar=lambda *_a, **_k: None, periodo_s=0.0)
    roteiro = _Roteiro()
    governador.tique = roteiro  # type: ignore[method-assign]
    governador.fechar_as_pontes_fantasmas = lambda: 0  # type: ignore[method-assign]
    governador._repousar_se_ocioso = lambda: roteiro.acabou  # type: ignore[method-assign]
    governador._parar = _EventoDoRoteiro(roteiro)  # type: ignore[assignment]
    with capture_logs() as diario:
        governador._laco()
    _conferir(store_do_processo, diario, "governador_do_radio", "tique")


def test_os_eventos_do_jogo_contam_e_avisam(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad, gatilho_do_jogo
    from hefesto_dualsense4unix.integrations import envelope_da_haptica

    monkeypatch.setattr(gatilho_do_jogo, "bater_o_gatilho", _Roteiro())
    monkeypatch.setattr(envelope_da_haptica, "bater_o_envelope", lambda _d: None)
    daemon = SimpleNamespace(store=StateStore())
    _por_tique(
        lambda: gamepad._bater_os_eventos_do_jogo(daemon), daemon.store, "poll", "eventos_do_jogo")


def test_os_acionadores_contam_e_avisam(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    ponte = SimpleNamespace(andar=_Roteiro())
    monkeypatch.setattr(gamepad, "ponte_dos_acionadores", lambda _d: ponte)
    daemon = SimpleNamespace(store=StateStore())
    _por_tique(lambda: gamepad.andar_os_acionadores(daemon), daemon.store, "poll", "acionadores")


def test_o_led_dos_externos_no_daemon_conta_e_avisa() -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    roteiro = _Roteiro()

    async def rodar(_fn: Any) -> Any:
        return roteiro()

    daemon = SimpleNamespace(
        store=StateStore(), _external_led_sync=SimpleNamespace(tick=lambda: None),
        _run_external_blocking=rodar, _external_tick_timeouts=0)

    def chamar() -> None:
        asyncio.run(Daemon._sync_external_leds(daemon))  # type: ignore[arg-type]

    _por_tique(chamar, daemon.store, "led_externo", "tique")


def test_o_hub_de_sensores_conta_e_avisa(store_do_processo: StateStore) -> None:
    from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

    hub = SensorHub(
        descobrir_motion=dict, descobrir_touch=dict, descobrir_gamepad=dict,
        auto_manutencao=False)
    roteiro = _Roteiro()
    hub.reconciliar = roteiro  # type: ignore[method-assign]
    hub._parar = _EventoDoRoteiro(roteiro)  # type: ignore[assignment]
    with capture_logs() as diario:
        hub._loop_manutencao()
    _conferir(store_do_processo, diario, "sensor_hub", "reconciliacao")


def test_o_vigia_das_conexoes_conta_e_avisa(store_do_processo: StateStore) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import ConexoesSubsystem

    vigia = ConexoesSubsystem(vigia=object(), olhador=lambda: None, intervalo_s=0.0)
    roteiro = _Roteiro()
    vigia.uma_volta = roteiro  # type: ignore[method-assign]
    vigia._parar = _EventoDoRoteiro(roteiro)  # type: ignore[assignment]
    with capture_logs() as diario:
        vigia._laco()
    _conferir(store_do_processo, diario, vigia.name, "volta")


def test_a_volta_dos_acessorios_conta_e_avisa() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.volta_dos_acessorios import (
        Ligacoes,
        VoltaDosAcessorios,
    )

    nada = lambda *_a: None  # noqa: E731
    store = StateStore()
    volta = VoltaDosAcessorios(Ligacoes(
        motores=nada, ler_luzinhas=nada, luzinhas=nada, barra=nada, soltar_barra=nada,
        pode_falar=lambda _u: True, o_jogo_pinta=lambda _u: False, estilo=lambda: None,
    ), store=store)
    volta._pulsos["aa:bb:cc:00:00:01"] = object()  # type: ignore[assignment]
    volta._andar_o_pulso = _Roteiro()  # type: ignore[method-assign]
    _por_tique(lambda: volta.tique(0.0), store, "volta_dos_acessorios", "pulso")


def test_a_enumeracao_dos_externos_conta_e_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        ExternalIdentityRegistry,
        ExternalLedSync,
    )

    roteiro = _Roteiro((True, True, True, False, True))

    def descobrir() -> list[Any]:
        roteiro()
        return []

    monkeypatch.setattr(evdev_reader, "discover_external_gamepads", descobrir)
    daemon = SimpleNamespace(store=StateStore())
    sync = ExternalLedSync(daemon, ExternalIdentityRegistry())
    monkeypatch.setattr(sync._registry, "sync_connected", lambda _u: None)
    _por_tique(lambda: sync.tick(now=0.0), daemon.store, "led_externo", "enumeracao")


def test_o_embrulho_e_seguro_entre_fios() -> None:
    """Oito fios falhando no mesmo passo: a soma fecha e o aviso sai uma vez só."""
    store = StateStore()
    passos = passos_do_laco.PassosDoLaco(store, "fios")
    largada = threading.Barrier(8)

    def falhar() -> None:
        largada.wait()
        for _ in range(200):
            passos.falhou("p", KeyError("x"))

    with capture_logs() as diario:
        fios = [threading.Thread(target=falhar) for _ in range(8)]
        for f in fios:
            f.start()
        for f in fios:
            f.join()
    assert store.counter("fios.erro.p") == 1600
    assert _avisos(diario, "fios", "p") == 1


def _so_debug(corpo: list[ast.stmt]) -> bool:
    chamadas = [s for s in corpo if not isinstance(s, (ast.Return, ast.Pass, ast.Continue))]
    if not chamadas:
        return True
    for s in chamadas:
        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)):
            return False
        alvo = s.value.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "debug"):
            return False
    return True


def _pega_tudo(tipo: ast.expr | None) -> bool:
    if tipo is None:
        return True
    nomes = tipo.elts if isinstance(tipo, ast.Tuple) else [tipo]
    return any(isinstance(n, ast.Name) and n.id in {"Exception", "BaseException"} for n in nomes)


def _funcoes(arvore: ast.AST, nome: str) -> Iterator[ast.AST]:
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            yield no


@pytest.mark.parametrize(("arquivo", "rotina"), FUNCOES_DE_LACO)
def test_nenhum_laco_engole_a_falha_em_debug(arquivo: str, rotina: str) -> None:
    """A varredura: ``except Exception`` só com ``logger.debug`` numa função de laço reprova."""
    arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    achadas = list(_funcoes(arvore, rotina))
    assert achadas, f"{arquivo}: {rotina} sumiu"
    caladas = [
        f"{arquivo}:{h.lineno}"
        for fn in achadas for h in ast.walk(fn)
        if isinstance(h, ast.ExceptHandler) and _pega_tudo(h.type) and _so_debug(h.body)
    ]
    assert not caladas, caladas
