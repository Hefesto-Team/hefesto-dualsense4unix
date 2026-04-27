"""Testes de timeout em IpcClient.connect e IpcClient.call.

Verifica que:
  (a) connect(timeout=...) em socket inexistente levanta IpcError em < 200ms;
  (b) TimeoutError de asyncio.wait_for vira IpcError(-1, "conexão timeout");
  (c) call(timeout=...) que demora demais levanta IpcError de timeout.

Usa unittest.mock.patch para isolar de socket real.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

# ---------------------------------------------------------------------------
# Testes de connect com timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_timeout_levanta_ipc_error():
    """connect(timeout=0.1) com socket inexistente deve levantar IpcError."""
    with (
        patch("asyncio.open_unix_connection", side_effect=asyncio.TimeoutError()),
        pytest.raises(IpcError) as exc_info,
    ):
        async with IpcClient.connect(
            socket_path=Path("/tmp/hefesto-dualsense4unix-test-ausente.sock"),
            timeout=0.1,
        ):
            pass

    err = exc_info.value
    assert err.code == -1
    assert "timeout" in err.message.lower()


@pytest.mark.asyncio
async def test_connect_timeout_rapido():
    """connect com timeout curto retorna em < 200ms ao falhar."""
    with patch("asyncio.open_unix_connection", side_effect=asyncio.TimeoutError()):
        inicio = time.monotonic()
        with pytest.raises(IpcError):
            async with IpcClient.connect(
                socket_path=Path("/tmp/hefesto-dualsense4unix-test-ausente.sock"),
                timeout=0.05,
            ):
                pass
        duracao = time.monotonic() - inicio

    assert duracao < 0.2, f"connect demorou {duracao:.3f}s — timeout não honrado"


@pytest.mark.asyncio
async def test_connect_sem_timeout_repassa_file_not_found():
    """connect sem timeout deve repassar FileNotFoundError normalmente."""
    with patch(
        "asyncio.open_unix_connection",
        side_effect=FileNotFoundError("socket ausente"),
    ), pytest.raises(FileNotFoundError):
        async with IpcClient.connect(
            socket_path=Path("/tmp/hefesto-dualsense4unix-test-ausente.sock"),
        ):
            pass


# ---------------------------------------------------------------------------
# Testes de call com timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_timeout_levanta_ipc_error():
    """call(timeout=0.05) que demora levanta IpcError de timeout."""

    async def _readline_lento():
        await asyncio.sleep(10)
        return b""

    reader = AsyncMock()
    reader.readline = _readline_lento
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    client = IpcClient(reader=reader, writer=writer)

    with pytest.raises(IpcError) as exc_info:
        await client.call("daemon.status", timeout=0.05)

    err = exc_info.value
    assert err.code == -1
    assert "timeout" in err.message.lower()


@pytest.mark.asyncio
async def test_call_sem_timeout_resposta_normal():
    """call sem timeout retorna resultado quando servidor responde."""
    import json

    resposta = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}).encode() + b"\n"

    reader = AsyncMock()
    reader.readline = AsyncMock(return_value=resposta)
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    client = IpcClient(reader=reader, writer=writer)
    result = await client.call("daemon.status")

    assert result == {"ok": True}

# "A sabedoria não é saber tudo, mas saber o que ignorar." — William James (adaptado)
