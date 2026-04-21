"""Cliente JSON-RPC 2.0 sobre Unix socket para falar com o daemon.

Uso típico de CLI/TUI:
    async with IpcClient.connect() as client:
        status = await client.call("daemon.status")
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto.daemon.ipc_server import PROTOCOL_VERSION
from hefesto.utils.xdg_paths import ipc_socket_path


class IpcError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class IpcClient:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    _next_id: int = 0

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(
        cls, socket_path: Path | None = None
    ) -> AsyncIterator[IpcClient]:
        path = socket_path or ipc_socket_path()
        reader, writer = await asyncio.open_unix_connection(str(path))
        client = cls(reader=reader, writer=writer)
        try:
            yield client
        finally:
            await client.close()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            self.writer.close()
            await self.writer.wait_closed()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        request = {
            "jsonrpc": PROTOCOL_VERSION,
            "id": self._next_id,
            "method": method,
            "params": params or {},
        }
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
        self.writer.write(payload)
        await self.writer.drain()

        raw = await self.reader.readline()
        if not raw:
            raise IpcError(-1, "conexao fechada pelo servidor antes da resposta")

        response = json.loads(raw.decode("utf-8"))
        if "error" in response:
            err = response["error"]
            raise IpcError(err["code"], err["message"])
        return response.get("result")


__all__ = ["IpcClient", "IpcError"]
