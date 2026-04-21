"""Testes do UDP server compat DSX."""
from __future__ import annotations

import asyncio
import json

import pytest

from hefesto.daemon.state_store import StateStore
from hefesto.daemon.udp_server import (
    DsxProtocol,
    RateLimiter,
    UdpHandler,
    UdpServer,
)
from tests.fixtures.fake_controller import FakeController

# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_aceita_ate_o_limite():
    rl = RateLimiter(rate_global=100, rate_per_ip=10)
    for _ in range(10):
        assert rl.allow("1.2.3.4", now=0.0) is True
    assert rl.allow("1.2.3.4", now=0.0) is False


def test_rate_limiter_por_ip_isolado():
    rl = RateLimiter(rate_global=100, rate_per_ip=3)
    for _ in range(3):
        assert rl.allow("a", now=0.0) is True
    for _ in range(3):
        assert rl.allow("b", now=0.0) is True
    assert rl.allow("a", now=0.0) is False
    assert rl.allow("b", now=0.0) is False


def test_rate_limiter_global_protege():
    rl = RateLimiter(rate_global=5, rate_per_ip=100)
    for i in range(5):
        assert rl.allow(f"ip{i}", now=0.0) is True
    assert rl.allow("ip5", now=0.0) is False


def test_rate_limiter_sweep_remove_ips_inativos():
    rl = RateLimiter(rate_global=100, rate_per_ip=3)
    rl.allow("volatile", now=0.0)
    assert "volatile" in rl.per_ip
    # Avança >1s sem atividade e força sweep
    rl._sweep(now=2.0)
    assert "volatile" not in rl.per_ip


def test_rate_limiter_janela_desliza():
    rl = RateLimiter(rate_global=100, rate_per_ip=5)
    for _ in range(5):
        rl.allow("x", now=0.0)
    assert rl.allow("x", now=0.5) is False
    # Após janela de 1s passar, deve permitir de novo
    assert rl.allow("x", now=1.1) is True


# ---------------------------------------------------------------------------
# UdpHandler (dispatch lógico, sem socket real)
# ---------------------------------------------------------------------------


def _mk_handler() -> tuple[UdpHandler, FakeController, StateStore]:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    handler = UdpHandler(controller=fc, store=store)
    return handler, fc, store


def _datagram(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_trigger_update_aplica_trigger():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            {"type": "TriggerUpdate", "parameters": ["right", "Rigid", 5, 200]}
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 1
    assert triggers[0].payload[0] == "right"


def test_rgb_update_aplica_led():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "RGBUpdate", "parameters": [0, 255, 128, 0]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert leds[-1].payload == (255, 128, 0)


def test_reset_aplica_off_em_ambos():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "ResetToUserSettings", "parameters": []}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    sides = [c.payload[0] for c in triggers]
    assert sorted(sides) == ["left", "right"]


def test_versao_invalida_dropa_com_contador():
    handler, fc, store = _mk_handler()
    payload = {"version": 2, "instructions": []}
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.unsupported_version") == 1
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert triggers == []


def test_parse_error_incrementa_contador():
    handler, _, store = _mk_handler()
    handler.handle_datagram(b"not json", ("127.0.0.1", 12345))
    assert store.counter("udp.parse_error") == 1


def test_oversize_dropa():
    handler, _, store = _mk_handler()
    big = b"x" * 5000
    handler.handle_datagram(big, ("127.0.0.1", 12345))
    assert store.counter("udp.oversize") == 1


def test_instrucao_desconhecida_incrementa_contador():
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "FutureFancy", "parameters": []}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.unknown_instruction") == 1


def test_instrucao_erro_captura_e_bump():
    handler, fc, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            # mode invalido -> build_from_name levanta
            {"type": "TriggerUpdate", "parameters": ["right", "ModeInexistente"]}
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.error.TriggerUpdate") == 1
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert triggers == []


def test_rate_limit_drop_conta_em_store():
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    # Rate limit bem restrito
    rl = RateLimiter(rate_global=2, rate_per_ip=2)
    handler = UdpHandler(controller=fc, store=store, rate_limiter=rl)
    payload = _datagram({"version": 1, "instructions": []})
    for _ in range(5):
        handler.handle_datagram(payload, ("127.0.0.1", 1))
    # 2 aceitos + 3 dropados
    assert store.counter("udp.rate_limited") == 3


# ---------------------------------------------------------------------------
# DsxProtocol.connection_made — BUG-UDP-01 (A-02)
# ---------------------------------------------------------------------------


def test_connection_made_nao_levanta_assertion_com_mock_transport():
    """Regressão BUG-UDP-01: em Python 3.10 o objeto real é
    `_SelectorDatagramTransport`, que falhava no `isinstance` contra
    `asyncio.DatagramTransport`. A atribuição direta deve aceitar qualquer
    `BaseTransport` sem levantar AssertionError.
    """
    handler, _, _ = _mk_handler()
    proto = DsxProtocol(handler)

    class _FakeTransport(asyncio.BaseTransport):
        pass

    fake = _FakeTransport()
    # Não deve levantar AssertionError nem qualquer outra exceção.
    proto.connection_made(fake)
    assert proto.transport is fake


# ---------------------------------------------------------------------------
# UdpServer ponta-a-ponta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_udp_server_recebe_datagrama_real(tmp_path):
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    UdpServer(controller=fc, store=store, host="127.0.0.1", port=0)
    # Sobrescreve porta 0 (auto-atribui) — vamos descobrir
    loop = asyncio.get_running_loop()

    # Re-implementa start para capturar a porta
    from hefesto.daemon.udp_server import DsxProtocol
    from hefesto.daemon.udp_server import UdpHandler as UdpHandlerCls

    handler = UdpHandlerCls(controller=fc, store=store, rate_limiter=RateLimiter())
    transport, _ = await loop.create_datagram_endpoint(
        lambda: DsxProtocol(handler),
        local_addr=("127.0.0.1", 0),
    )
    try:
        addr = transport.get_extra_info("sockname")
        port = addr[1]

        # Manda um datagrama
        send_transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=("127.0.0.1", port)
        )
        payload = {
            "version": 1,
            "instructions": [
                {"type": "TriggerUpdate", "parameters": ["left", "Rigid", 3, 150]}
            ],
        }
        send_transport.sendto(json.dumps(payload).encode("utf-8"))
        # Dá tempo pro datagrama chegar
        await asyncio.sleep(0.05)
        send_transport.close()

        triggers = [c for c in fc.commands if c.kind == "set_trigger"]
        assert len(triggers) >= 1
    finally:
        transport.close()
