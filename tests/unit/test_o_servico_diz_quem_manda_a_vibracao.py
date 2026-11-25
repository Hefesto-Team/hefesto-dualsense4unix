"""O serviço diz quem manda a vibração (D-2511-O-SERVICO-DIZ-QUEM-MANDA-A-VIBRACAO).

O servidor do IPC lê o PID do par do soquete uma vez por conexão; os handlers de vibração escrevem
no diário quem pediu, uma linha quando o par muda e a contagem das repetições, nunca uma linha por
pedido.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import ipc_handlers, ipc_server
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

CABO = "aa:bb:cc:dd:ee:01"
RADIO = "aa:bb:cc:dd:ee:02"
PEDIDOS = 200


class _MesaDeDois(FakeController):
    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        return True


def _o_proc(raiz: Path, pid: int, *argv: str) -> None:
    pasta = raiz / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")


@pytest.fixture
def proc_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "proc"
    raiz.mkdir()
    _o_proc(raiz, 4001, "/usr/bin/python3", "-u", "/opt/jogo/o_jogo.py", "--tela")
    _o_proc(raiz, 4002, "/usr/bin/steam_ajudante", "--x")
    monkeypatch.setattr(ipc_handlers, "_PROC", str(raiz))
    return raiz


@pytest.fixture
async def servidor(tmp_path: Path) -> AsyncIterator[IpcServer]:
    fc = _MesaDeDois(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(battery_pct=75, l2_raw=0, r2_raw=0, connected=True, transport="usb")
    )
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "s.sock",
    )
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


def _pares_em_ordem(pids: list[int | None]) -> Any:
    fila = list(pids)

    def par(_writer: Any) -> int | None:
        return fila.pop(0) if fila else None

    return par


def _linhas_de_vibracao(diario: list[Any]) -> list[Mapping[str, Any]]:
    return [e for e in diario if str(e.get("event", "")).startswith("vibracao_pedida")]


async def test_o_diario_diz_os_dois_chamadores_e_a_contagem_sem_crescer(
    servidor: IpcServer, proc_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dois clientes pedem o zero de dois controles (cabo e rádio) por 200 pedidos (dez minutos
    a cada 3 s): o diário diz os dois nomes e a contagem, e as linhas não crescem com os pedidos."""
    monkeypatch.setattr(ipc_server, "_o_par_do_soquete", _pares_em_ordem([4001, 4002]))
    with capture_logs() as diario:
        async with (
            IpcClient.connect(servidor.socket_path) as jogo,
            IpcClient.connect(servidor.socket_path) as ajudante,
        ):
            for _ in range(PEDIDOS):
                resposta = await jogo.call("rumble.set", {"weak": 0, "strong": 0, "uniq": CABO})
                await ajudante.call("rumble.set", {"weak": 0, "strong": 0, "uniq": RADIO})
    assert resposta["status"] == "ok" and resposta["weak"] == 0
    linhas = _linhas_de_vibracao(diario)
    assert len(linhas) <= 2 * 10, "o diário cresceu com a repetição"
    primeiras = {
        (e["chamador"], e["controle"]) for e in linhas if e["event"] == "vibracao_pedida_por"
    }
    assert primeiras == {
        ("o_jogo.py", "aa:bb:cc:00:00:01"),
        ("steam_ajudante", "aa:bb:cc:00:00:02"),
    }
    contagens = [e["repeticoes"] for e in linhas if e["event"] == "vibracao_pedida_repetida"]
    assert max(contagens) >= PEDIDOS // 2
    texto = repr(linhas)
    assert "dd:ee" not in texto, "o endereço do controle saiu sem máscara"


async def test_mudar_o_par_escreve_outra_linha_e_fecha_a_contagem(
    servidor: IpcServer, proc_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero repetido seis vezes e depois um par novo: a contagem fecha na linha seguinte."""
    monkeypatch.setattr(ipc_server, "_o_par_do_soquete", _pares_em_ordem([4001]))
    with capture_logs() as diario:
        async with IpcClient.connect(servidor.socket_path) as jogo:
            for _ in range(6):
                await jogo.call("rumble.set", {"weak": 0, "strong": 0, "uniq": CABO})
            await jogo.call("rumble.set", {"weak": 90, "strong": 10, "uniq": CABO})
            await jogo.call("rumble.stop", {"uniq": CABO})
            await jogo.call("rumble.passthrough", {"enabled": True, "uniq": CABO})
            await jogo.call("rumble.motores.set", {"forte_pct": 80, "uniq": CABO})
    linhas = _linhas_de_vibracao(diario)
    eventos = [(e["event"], e["pedido"], e.get("repeticoes")) for e in linhas]
    assert eventos[:4] == [
        ("vibracao_pedida_por", "rumble.set", None),
        ("vibracao_pedida_repetida", "rumble.set", 2),
        ("vibracao_pedida_repetida", "rumble.set", 4),
        ("vibracao_pedida_repetida", "rumble.set", 5),
    ]
    assert [e[1] for e in eventos if e[0] == "vibracao_pedida_por"] == [
        "rumble.set", "rumble.set", "rumble.stop", "rumble.passthrough", "rumble.motores.set",
    ]


async def test_par_ilegivel_vale_desconhecido_e_nao_atrasa(
    servidor: IpcServer, proc_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem PID ou sem entrada no /proc o chamador é «desconhecido», sem erro."""
    monkeypatch.setattr(ipc_server, "_o_par_do_soquete", _pares_em_ordem([None, 999_999]))
    with capture_logs() as diario:
        for _ in range(2):
            async with IpcClient.connect(servidor.socket_path) as cliente:
                inicio = time.perf_counter()
                resposta = await cliente.call(
                    "rumble.set", {"weak": 0, "strong": 0, "uniq": CABO}
                )
                assert time.perf_counter() - inicio < 1.0
            assert resposta["status"] in {"ok", "recusado"}
    nomes = [e["chamador"] for e in _linhas_de_vibracao(diario)]
    assert nomes == ["desconhecido", "desconhecido"]


async def test_o_par_de_verdade_do_soquete_e_este_processo(servidor: IpcServer) -> None:
    """Sem dublê: o ``SO_PEERCRED`` do soquete real devolve o PID de quem conectou."""
    with capture_logs() as diario:
        async with IpcClient.connect(servidor.socket_path) as cliente:
            await cliente.call("rumble.set", {"weak": 0, "strong": 0, "uniq": CABO})
    (linha,) = _linhas_de_vibracao(diario)
    assert linha["pid"] == os.getpid()
    assert linha["chamador"] == ipc_handlers.nome_do_processo(os.getpid())
    assert linha["chamador"] != "desconhecido"


async def test_o_pedido_de_dentro_do_servico_se_chama_interno(servidor: IpcServer) -> None:
    """A porta das modificações chama o handler em processo, sem conexão: «interno»."""
    with capture_logs() as diario:
        await servidor._handlers["rumble.set"]({"weak": 0, "strong": 0, "uniq": RADIO})
    (linha,) = _linhas_de_vibracao(diario)
    assert (linha["chamador"], linha["pid"]) == ("interno", None)


def test_o_nome_do_interpretador_e_o_script_ou_o_modulo(
    proc_de_mentira: Path,
) -> None:
    _o_proc(proc_de_mentira, 4010, "python3.12", "-m", "hefesto_dualsense4unix.cli.app", "x")
    assert ipc_handlers.nome_do_processo(4001) == "o_jogo.py"
    assert ipc_handlers.nome_do_processo(4002) == "steam_ajudante"
    assert ipc_handlers.nome_do_processo(4010) == "hefesto_dualsense4unix.cli.app"
    assert ipc_handlers.nome_do_processo(None) == "desconhecido"
    assert ipc_handlers.nome_do_processo(31_999_999) == "desconhecido"
