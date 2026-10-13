"""As métricas contam o que a página promete.

O coletor lia contadores que ninguém escrevia. Aqui os produtores são os reais
(`IpcServer`, `EventBus`, `UdpHandler`, `StateStore`) e nenhum contador é semeado
à mão: o que a página `docs/usage/metrics.md` promete tem de subir sozinho.
"""
from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.context import DaemonContext
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.metrics import (
    ENV_METRICS_PORT,
    MetricsCollector,
    MetricsSubsystem,
)
from hefesto_dualsense4unix.daemon.udp_server import UdpHandler
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


def _servidor_de_ipc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[IpcServer, StateStore]:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    servidor = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "ipc.sock",
    )
    return servidor, store


def _coletar(store: StateStore, bus: EventBus | None = None, controller: Any = None) -> str:
    coletor = MetricsCollector(
        store=store, controller=controller or MagicMock(), bus=bus
    )
    return str(coletor.collect())


@pytest.mark.asyncio
async def test_um_pedido_daemon_status_sobe_a_serie_do_ipc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(1) Um `daemon.status` pelo `_dispatch` faz a série `{method,status="ok"}` valer 1."""
    servidor, store = _servidor_de_ipc(tmp_path, monkeypatch)
    pedido = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "daemon.status"}).encode()

    resposta = await servidor._dispatch(pedido)

    assert resposta is not None and b'"result"' in resposta
    payload = _coletar(store)
    assert 'hefesto_ipc_requests_total{method="daemon.status",status="ok"} 1' in payload


@pytest.mark.asyncio
async def test_o_pedido_que_falha_conta_como_erro_e_o_desconhecido_nao_conta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O handler que levanta soma `erro`; o método inventado não abre série nova."""
    servidor, store = _servidor_de_ipc(tmp_path, monkeypatch)

    async def estoura(_params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("falhou")

    servidor._handlers["daemon.status"] = estoura
    await servidor._dispatch(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "daemon.status"}).encode()
    )
    await servidor._dispatch(
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "metodo.que.nao.existe"}).encode()
    )

    payload = _coletar(store)
    assert 'method="daemon.status",status="erro"} 1' in payload
    assert "metodo.que.nao.existe" not in payload


def test_um_publish_sobe_a_serie_do_topico() -> None:
    """(2) O `publish` conta o tópico, com ou sem assinante."""
    bus = EventBus()
    bus.publish(EventTopic.BATTERY_CHANGE, 80)
    bus.publish(EventTopic.BATTERY_CHANGE, 79)
    bus.publish(EventTopic.BUTTON_DOWN, "cross")

    payload = _coletar(StateStore(), bus)

    assert 'hefesto_events_dispatched_total{topic="battery.change"} 2' in payload
    assert 'hefesto_events_dispatched_total{topic="button.down"} 1' in payload


def test_um_pacote_dsx_valido_sobe_o_accepted() -> None:
    """(3) O pacote que passa do limitador soma `{result="accepted"}`."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    handler = UdpHandler(controller=fc, store=store)
    pacote = json.dumps(
        {"version": 1, "instructions": [{"type": "RGBUpdate", "parameters": [0, 255, 128, 0]}]}
    ).encode()

    handler.handle_datagram(pacote, ("127.0.0.1", 40000))

    payload = _coletar(store)
    assert 'hefesto_udp_packets_total{result="accepted"} 1' in payload
    assert 'hefesto_udp_packets_total{result="rate_limited"} 0' in payload


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _ler_metricas(porta: int) -> str:
    """Lê até o servidor fechar: quem fecha primeiro fica com a porta em TIME_WAIT.

    O cliente que fecha antes (o `urllib` faz isso quando já leu o `Content-Length`)
    deixa o TIME_WAIT do lado dele e o teste não prova nada, então aqui o cliente
    espera o FIN do servidor e só então fecha.
    """
    with socket.create_connection(("127.0.0.1", porta), timeout=5) as conexao:
        conexao.sendall(b"GET /metrics HTTP/1.0\r\n\r\n")
        pedacos: list[bytes] = []
        while pedaco := conexao.recv(4096):
            pedacos.append(pedaco)
    resposta = b"".join(pedacos).decode("utf-8")
    assert resposta.startswith("HTTP/1.0 200"), resposta[:80]
    return resposta


def _ctx(porta: int) -> DaemonContext:
    return DaemonContext(
        controller=MagicMock(),
        bus=EventBus(),
        store=StateStore(),
        config=SimpleNamespace(metrics_enabled=True, metrics_port=porta),
    )


@pytest.mark.asyncio
async def test_dois_starts_na_mesma_porta_com_conexao_aceita_entre_eles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(4) O `allow_reuse_address` vale no bind: a porta em TIME_WAIT sobe de novo."""
    monkeypatch.delenv(ENV_METRICS_PORT, raising=False)
    porta = _porta_livre()
    ctx = _ctx(porta)

    primeiro = MetricsSubsystem()
    await primeiro.start(ctx)
    try:
        assert primeiro._server is not None
        assert _ler_metricas(porta)
    finally:
        await primeiro.stop()

    segundo = MetricsSubsystem()
    await segundo.start(ctx)
    try:
        assert segundo._server is not None, "a porta em TIME_WAIT derrubou o segundo start"
        assert _ler_metricas(porta)
    finally:
        await segundo.stop()


class _DoisControles:
    """Dublê de backend com duas entradas, no formato do `describe_controllers`."""

    def describe_controllers(self) -> list[dict[str, object]]:
        return [
            {"index": 0, "connected": True, "transport": "usb", "battery_pct": 85,
             "uniq": "aabbcc000001"},
            {"index": 1, "connected": True, "transport": "bt", "battery_pct": 40,
             "uniq": "aabbcc000002"},
        ]


def test_dois_controles_saem_em_duas_linhas_de_bateria_uma_por_jogador() -> None:
    """(5) Uma linha de bateria e de conexão por jogador, não só a do topo."""
    payload = _coletar(StateStore(), controller=_DoisControles())

    assert re.findall(r'^hefesto_battery_pct\{jogador="(\d)"\} (-?\d+)$', payload, re.M) == [
        ("1", "85"),
        ("2", "40"),
    ]
    assert 'hefesto_controller_connected{jogador="1",transport="usb"} 1' in payload
    assert 'hefesto_controller_connected{jogador="2",transport="bt"} 1' in payload


def test_o_numero_do_jogador_e_o_slot_da_sessao_quando_ele_existe() -> None:
    """O rótulo é o do cartão «Controle N»: o slot da sessão vence a posição."""
    registro = SimpleNamespace(
        slot_for=lambda uniq, assign=False: {"aabbcc000001": 4, "aabbcc000002": 1}[uniq]
    )
    daemon = SimpleNamespace(identity_registry=registro)
    coletor = MetricsCollector(
        store=StateStore(), controller=_DoisControles(), bus=None, daemon=daemon
    )

    payload = coletor.collect()

    assert re.findall(r'^hefesto_battery_pct\{jogador="(\d)"\} (-?\d+)$', payload, re.M) == [
        ("1", "40"),
        ("4", "85"),
    ]


def test_sem_controle_conectado_sai_uma_linha_so_com_bateria_desconhecida() -> None:
    """A lista de «ao menos um item» do backend vira `jogador="1"`, conexão 0 e bateria -1."""

    class _Vazio:
        def describe_controllers(self) -> list[dict[str, object]]:
            return [{"connected": False, "transport": None, "is_primary": False}]

    payload = _coletar(StateStore(), controller=_Vazio())

    assert 'hefesto_battery_pct{jogador="1"} -1' in payload
    assert 'hefesto_controller_connected{jogador="1",transport="unknown"} 0' in payload
