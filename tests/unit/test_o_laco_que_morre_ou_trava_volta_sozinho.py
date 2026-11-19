"""O laço que morre ou trava volta sozinho.

O `_poll_loop`, o `reconnect_loop` e o `sync` do co-op de produção rodam com dublês só no papel
do aparelho; o `sd_notify` é dublado no ponto em que o datagrama sairia.
"""
from __future__ import annotations

import asyncio
import configparser
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.subsystems import vigia_do_laco as vl
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import sd_notify, session
from tests.unit import test_steam_no_fisico_01_o_jogo_ve_p1_a_p4 as mesa
from tests.unit.test_o_laco_mede_o_atraso import JANELA, _Laco
from tests.unit.test_steam_no_fisico_01_o_jogo_ve_p1_a_p4 import nascimentos

__all__ = ["nascimentos"]

UNIT = Path(__file__).resolve().parents[2] / "assets" / "hefesto-dualsense4unix.service"
PIOR_LACO_PARADO_MEDIDO_S = 7.9


class _LacoQueLevanta(_Laco):
    def __init__(self, passo: str) -> None:
        super().__init__(("usb", "bt", "usb", "bt"))
        self.passo = passo
        if passo == "mouse":
            self._gamepad_device = None
            self._mouse_device = object()

    def _reassert_rumble(self, _agora: float) -> None:
        if self.passo == "rumble":
            raise TypeError("'<' not supported between instances of 'int' and 'NoneType'")

    def _dispatch_mouse_emulation(self, *_a: Any) -> None:
        if self.passo == "mouse":
            raise TypeError("o mouse levantou")


@pytest.fixture
def laco_sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    for nome in ("sync", "_recolher_os_cedidos", "_promote_pending"):
        monkeypatch.setattr(co.CoopManager, nome, lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(lc, "JANELA_DO_MEDIDOR_DO_TIQUE", JANELA)
    monkeypatch.setattr(lc, "RELOGIOS_LENTOS", ())


@pytest.mark.usefixtures("laco_sem_a_maquina")
@pytest.mark.parametrize("passo", ["rumble", "mouse"])
def test_o_passo_que_levanta_diz_a_pilha_e_o_tique_segue(passo: str) -> None:
    """D-1911-O-LACO-QUE-MORRE-OU-TRAVA-VOLTA-SOZINHO: o passo que levanta não para o tique."""
    daemon = _LacoQueLevanta(passo)
    with capture_logs() as linhas:
        asyncio.run(daemon.rodar())
    falhas = [linha for linha in linhas if linha["event"] == "passo_do_laco_falhou"]
    assert daemon.contadores().get("poll.tick", 0) >= JANELA - 1, daemon.contadores()
    assert len(falhas) == 1 and falhas[0]["exc_info"] is not None, falhas


def _daemon_da_volta(controle: Any) -> tuple[SimpleNamespace, ThreadPoolExecutor]:
    fios = ThreadPoolExecutor(2)
    parar = asyncio.Event()

    async def _bloqueante(funcao: Any, *args: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(fios, funcao, *args)

    daemon = SimpleNamespace(
        controller=controle, bus=EventBus(), store=None, _stop_event=parar,
        _is_stopping=parar.is_set, _run_blocking=_bloqueante, _arm_input_grace=lambda: None,
        is_native_mode=lambda: False, _tasks=[], _hidraw_broker_executor=fios,
    )
    return daemon, fios


def test_a_volta_da_reconexao_que_levanta_e_refeita(monkeypatch: pytest.MonkeyPatch) -> None:
    connects: list[float] = []
    controle = SimpleNamespace(
        connect=lambda: connects.append(time.monotonic()), is_connected=lambda: False,
        primary_uniq=None, get_transport=lambda: "usb",
    )
    levantou: list[bool] = []

    async def vigiar_que_levanta(*_a: Any, **_k: Any) -> int:
        if not levantou:
            levantou.append(True)
            raise RuntimeError("a varredura de /proc levantou")
        return 0

    monkeypatch.setattr(conn, "vigiar_escritor_cru", vigiar_que_levanta)
    monkeypatch.setattr(conn, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    async def _ensaio() -> asyncio.Task[None]:
        daemon, fios = _daemon_da_volta(controle)
        tarefa = asyncio.create_task(
            conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
        )
        fim = time.monotonic() + 3.0
        while len(connects) < 3 and not tarefa.done() and time.monotonic() < fim:
            await asyncio.sleep(0.01)
        daemon._stop_event.set()
        await asyncio.wait({tarefa}, timeout=2.0)
        fios.shutdown(wait=False)
        return tarefa

    with capture_logs() as linhas:
        tarefa = asyncio.run(_ensaio())
    assert tarefa.done() and not tarefa.cancelled() and tarefa.exception() is None
    assert len(connects) >= 3, f"a volta que levantou não foi refeita: {len(connects)}"
    falhas = [linha for linha in linhas if linha["event"] == "volta_da_reconexao_falhou"]
    assert len(falhas) == 1 and falhas[0]["exc_info"] is not None, falhas


def test_o_terceiro_que_levanta_no_sync_nao_para_os_outros(
    nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    comeca = mesa._Leitor.start

    def comeca_menos_o_terceiro(leitor: Any) -> bool:
        if leitor.target_uniq == mesa.P3:
            raise OSError("o evdev do terceiro levantou")
        return bool(comeca(leitor))

    monkeypatch.setattr(mesa._Leitor, "start", comeca_menos_o_terceiro)
    mgr = CoopManager(mesa._daemon())
    with capture_logs() as linhas:
        mgr.sync()
        mgr.sync(force=True)
        mgr.forward_all()
    eventos = [linha["event"] for linha in linhas]
    assert nascimentos == [mesa.P2, mesa.P4], (nascimentos, eventos)
    falhas = [linha for linha in linhas if linha["event"] == "coop_jogador_falhou"]
    assert len(falhas) == 1 and falhas[0]["exc_info"] is not None, eventos


class _DaemonDeMentira:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._codigo_de_saida: int | None = None
        self._reconnect_task: Any = None

    def _is_stopping(self) -> bool:
        return self._stop_event.is_set()

    def stop(self) -> None:
        self._stop_event.set()


def test_o_laco_que_morre_volta_e_alem_do_teto_sai_com_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lc, "RECUO_DO_LACO_S", 0.001)
    monkeypatch.setattr(lc, "TETO_DO_RECUO_DO_LACO_S", 0.004)
    nascidos: list[float] = []

    async def laco_que_morre() -> None:
        nascidos.append(time.monotonic())
        raise TypeError("o laço levantou")

    async def _ensaio() -> tuple[_DaemonDeMentira, list[Any]]:
        daemon = _DaemonDeMentira()
        tarefas = lc._TarefasVigiadas(daemon)
        tarefas.nascer("poll_loop", laco_que_morre, "laco_morreu")
        await asyncio.wait_for(daemon._stop_event.wait(), 3.0)
        return daemon, tarefas

    with capture_logs() as linhas:
        daemon, tarefas = asyncio.run(_ensaio())
    mortes = [linha for linha in linhas if linha["event"] == "laco_morreu"]
    assert len(nascidos) == lc.TETO_DE_MORTES_SEGUIDAS + 1, nascidos
    assert len(mortes) == len(nascidos) and mortes[0]["exc_info"] is not None
    assert not tarefas, f"o laço morto ficou na lista com a pilha: {len(tarefas)}"
    assert daemon._codigo_de_saida == lc.CODIGO_DO_LACO_QUE_NAO_VOLTA != 0
    with pytest.raises(SystemExit) as saida:
        lc._sair_se_o_laco_nao_volta(daemon)
    assert saida.value.code == lc.CODIGO_DO_LACO_QUE_NAO_VOLTA


def test_o_servico_cujo_laco_nao_volta_sai_com_o_codigo_de_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lc, "RECUO_DO_LACO_S", 0.001)
    monkeypatch.setattr(lc, "TETO_DO_RECUO_DO_LACO_S", 0.004)
    monkeypatch.setattr(session, "load_paused_state", lambda: False)

    async def laco_que_morre(_self: Any) -> None:
        raise TypeError("o laço levantou")

    monkeypatch.setattr(lc.Daemon, "_poll_loop", laco_que_morre)
    config = lc.DaemonConfig(
        poll_hz=200, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        mouse_emulation_enabled=False, keyboard_emulation_enabled=False,
        ps_button_action="none", mic_button_toggles_system=False,
    )
    daemon = lc.Daemon(controller=FakeController(transport="usb"), config=config)
    with pytest.raises(SystemExit) as saida:
        asyncio.run(asyncio.wait_for(daemon.run(), 10.0))
    assert saida.value.code == lc.CODIGO_DO_LACO_QUE_NAO_VOLTA


def test_a_tarefa_do_servico_que_morre_vai_ao_diario_com_a_pilha() -> None:
    async def _ensaio() -> None:
        tarefas = lc._TarefasVigiadas(_DaemonDeMentira())

        async def morre() -> None:
            raise ValueError("o tato vivo levantou")

        tarefas.append(asyncio.create_task(morre(), name="tato_vivo_loop"))
        await asyncio.sleep(0.01)

    with capture_logs() as linhas:
        asyncio.run(_ensaio())
    mortes = [linha for linha in linhas if linha["event"] == "tarefa_morreu"]
    assert len(mortes) == 1 and mortes[0]["tarefa"] == "tato_vivo_loop"
    assert mortes[0]["exc_info"] is not None


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


@pytest.mark.parametrize(
    ("batida_ha_s", "tique_ha_s", "bate"),
    [(0.0, 0.0, True), (20.0, 0.0, False), (0.0, 20.0, False)],
    ids=["laco-vivo", "laco-parado", "poll-loop-morto"],
)
def test_o_watchdog_so_bate_com_o_laco_e_o_tique_andando(
    monkeypatch: pytest.MonkeyPatch, batida_ha_s: float, tique_ha_s: float, bate: bool
) -> None:
    enviados: list[str] = []
    monkeypatch.setattr(sd_notify, "notificar", lambda msg: enviados.append(msg) or True)
    monkeypatch.setattr(sd_notify, "prazo_do_watchdog", lambda: 30.0)
    relogio = _Relogio()
    vigia = vl.VigiaDoLaco(relogio=relogio, avisar=lambda *_a, **_k: None)
    relogio.agora += 40.0
    vigia._batida = relogio.agora - batida_ha_s
    vigia.tique()
    vigia._ultimo_tique = relogio.agora - tique_ha_s
    vigia.alimentar_o_watchdog(relogio.agora)
    assert (enviados == ["WATCHDOG=1"]) is bate, enviados


@pytest.mark.usefixtures("laco_sem_a_maquina")
def test_cada_tique_avisa_o_vigia_e_grava_a_hora(monkeypatch: pytest.MonkeyPatch) -> None:
    relogio = _Relogio()
    vigia = vl.VigiaDoLaco(relogio=relogio, avisar=lambda *_a, **_k: None)
    relogio.agora += 40.0
    monkeypatch.setattr(vl, "_ativo", vigia)
    daemon = _LacoQueLevanta("nenhum")
    antes_ms = time.time() * 1000
    asyncio.run(daemon.rodar())
    assert vigia._ultimo_tique == relogio.agora, "o tique não avisou o vigia"
    ultimo_ms = daemon.contadores().get("poll.tique.ultimo_ms", 0)
    assert antes_ms - 1 <= ultimo_ms <= time.time() * 1000 + 1, daemon.contadores()


def test_o_prazo_do_watchdog_sobrevive_a_limpeza_do_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sd_notify, "_guardadas", {})
    monkeypatch.setenv("NOTIFY_SOCKET", "/nao-existe/notify")
    monkeypatch.setenv("WATCHDOG_USEC", "30000000")
    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()))
    sd_notify.guardar_o_soquete()
    assert "WATCHDOG_USEC" not in os.environ
    assert sd_notify.prazo_do_watchdog() == 30.0
    monkeypatch.setitem(sd_notify._guardadas, "WATCHDOG_PID", str(os.getpid() + 1))
    assert sd_notify.prazo_do_watchdog() is None


def test_a_unit_tem_watchdog_acima_do_pior_laco_parado() -> None:
    unit = configparser.ConfigParser(strict=False, interpolation=None)
    unit.read(UNIT, encoding="utf-8")
    prazo = float(unit["Service"]["WatchdogSec"])
    assert prazo > PIOR_LACO_PARADO_MEDIDO_S * 2, prazo
    assert unit["Service"]["Restart"] == "on-failure"


def test_o_doctor_nao_diz_ok_com_o_tique_velho() -> None:
    agora_ms = round(time.time() * 1000)
    contadores = {"poll.tique.medidos": 900, "poll.tique.estouros": 0}
    vivo = cmd_doctor._linha_do_tique({**contadores, "poll.tique.ultimo_ms": agora_ms})
    parado = cmd_doctor._linha_do_tique({**contadores, "poll.tique.ultimo_ms": agora_ms - 60_000})
    assert vivo is not None and vivo[0] == "[ OK ]", vivo
    assert parado is not None and parado[0] != "[ OK ]" and "60" in parado[1], parado
