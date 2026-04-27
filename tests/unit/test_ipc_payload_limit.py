"""Testes de limite de bytes no dispatch IPC (HARDEN-IPC-PAYLOAD-LIMIT-01).

Cobrem rejeição de payloads gigantes via campo arbitrário de padding, sem
afetar payloads legítimos. Não precisam de socket real — invocam `_dispatch`
diretamente sobre bytes.
"""
from __future__ import annotations

import json

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import (
    CODE_INVALID_REQUEST,
    MAX_PAYLOAD_BYTES,
    IpcServer,
)


def _make_raw(payload_dict: dict[str, object]) -> bytes:
    return (json.dumps(payload_dict) + "\n").encode("utf-8")


def _server() -> IpcServer:
    return IpcServer(controller=None, store=None, profile_manager=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_payload_pequeno_normal_nao_rejeita() -> None:
    """1 KiB — payload típico de profile.switch, deve ser aceito."""
    srv = _server()
    padding = "a" * 1024
    raw = _make_raw({"jsonrpc": "2.0", "id": 1, "method": "daemon.status", "padding": padding})
    resp = await srv._dispatch(raw)
    assert resp is not None
    body = json.loads(resp.decode("utf-8"))
    # Pode falhar por daemon=None, mas NÃO deve ser erro de tamanho (-32600).
    assert body.get("error", {}).get("code") != CODE_INVALID_REQUEST


@pytest.mark.asyncio
async def test_payload_no_limite_30kib_nao_rejeita() -> None:
    """30 KiB — abaixo do limite de 32 KiB, deve passar pelo check de tamanho."""
    srv = _server()
    padding = "a" * 30_000
    raw = _make_raw({"jsonrpc": "2.0", "id": 2, "method": "daemon.status", "padding": padding})
    assert len(raw) < MAX_PAYLOAD_BYTES
    resp = await srv._dispatch(raw)
    assert resp is not None
    body = json.loads(resp.decode("utf-8"))
    assert body.get("error", {}).get("code") != CODE_INVALID_REQUEST


@pytest.mark.asyncio
async def test_payload_acima_limite_rejeita() -> None:
    """33 KiB (acima de 32 KiB) — deve retornar erro -32600."""
    srv = _server()
    padding = "a" * 33_000
    raw = _make_raw({"jsonrpc": "2.0", "id": 3, "method": "daemon.status", "padding": padding})
    assert len(raw) > MAX_PAYLOAD_BYTES
    resp = await srv._dispatch(raw)
    assert resp is not None
    body = json.loads(resp.decode("utf-8"))
    assert body["error"]["code"] == CODE_INVALID_REQUEST
    assert "32768" in body["error"]["message"]


@pytest.mark.asyncio
async def test_payload_muito_grande_rejeita() -> None:
    """100 KiB — deve retornar erro -32600 sem nem tentar parsear."""
    srv = _server()
    padding = "a" * 100_000
    raw = _make_raw({"jsonrpc": "2.0", "id": 4, "method": "daemon.status", "padding": padding})
    resp = await srv._dispatch(raw)
    assert resp is not None
    body = json.loads(resp.decode("utf-8"))
    assert body["error"]["code"] == CODE_INVALID_REQUEST


@pytest.mark.asyncio
async def test_max_payload_bytes_exportado() -> None:
    """Constante exportada com o valor canônico (ajustável em uma linha)."""
    assert MAX_PAYLOAD_BYTES == 32_768
