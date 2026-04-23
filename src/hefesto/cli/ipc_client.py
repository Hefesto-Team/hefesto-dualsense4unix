"""Cliente JSON-RPC 2.0 sobre Unix socket para falar com o daemon.

Uso típico de CLI/TUI:
    async with IpcClient.connect() as client:
        status = await client.call("daemon.status")

Uso com timeout (recomendado na GUI):
    async with IpcClient.connect(timeout=0.25) as client:
        status = await client.call("daemon.status", timeout=1.0)
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
        cls,
        socket_path: Path | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[IpcClient]:
        """Conecta ao socket Unix do daemon.

        Parameters
        ----------
        socket_path:
            Caminho alternativo ao socket (padrão: `ipc_socket_path()`).
        timeout:
            Tempo máximo (segundos) para estabelecer a conexão. `None`
            significa sem limite. Em caso de `TimeoutError`, levanta
            `IpcError(-1, "conexão timeout")`.
        """
        path = socket_path or ipc_socket_path()
        try:
            if timeout is not None:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(str(path)),
                    timeout=timeout,
                )
            else:
                reader, writer = await asyncio.open_unix_connection(str(path))
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise IpcError(-1, "conexão timeout") from exc
        client = cls(reader=reader, writer=writer)
        try:
            yield client
        finally:
            await client.close()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            self.writer.close()
            await self.writer.wait_closed()

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Envia RPC e aguarda resposta.

        Parameters
        ----------
        method:
            Nome do método JSON-RPC (ex.: ``"daemon.status"``).
        params:
            Parâmetros da chamada (dicionário). `None` equivale a ``{}``.
        timeout:
            Tempo máximo (segundos) para receber a resposta. `None` sem
            limite. `TimeoutError` vira `IpcError(-1, "conexão timeout")`.
        """
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

        try:
            if timeout is not None:
                raw = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            else:
                raw = await self.reader.readline()
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise IpcError(-1, "conexão timeout") from exc

        if not raw:
            raise IpcError(-1, "conexão fechada pelo servidor antes da resposta")

        response = json.loads(raw.decode("utf-8"))
        if "error" in response:
            err = response["error"]
            raise IpcError(err["code"], err["message"])
        return response.get("result")


__all__ = ["IpcClient", "IpcError"]

# "O obstáculo é o caminho." — Marco Aurélio
