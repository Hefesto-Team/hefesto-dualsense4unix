"""Cliente JSON-RPC 2.0 sobre Unix socket para falar com o daemon."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.protocolo_do_ipc import PROTOCOL_VERSION
from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

_LOG = logging.getLogger(__name__)

_CLOSE_TIMEOUT_S = 2.0

_CONNECT_TIMEOUT_S = 1.0


def _prazo_do_metodo(method: str) -> float:
    """O prazo do método: o dono é a tabela da ponte (`app/ipc_bridge.TETOS`).

    O import é tardio porque a ponte importa este módulo.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import teto_da_linha_de_comando

    return teto_da_linha_de_comando(method)


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

        ``timeout=None`` vale o padrão (1 s): esperar para sempre não existe.
        """
        path = socket_path or ipc_socket_path()
        prazo = _CONNECT_TIMEOUT_S if timeout is None else timeout
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(path)),
                timeout=prazo,
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise IpcError(-1, f"o daemon não aceitou a conexão em {prazo:g} s") from exc
        client = cls(reader=reader, writer=writer)
        try:
            yield client
        finally:
            await client.close()

    async def close(self, timeout: float | None = None) -> None:
        """Fecha a conexão sem nunca ficar presa."""
        prazo = _CLOSE_TIMEOUT_S if timeout is None else timeout
        with contextlib.suppress(Exception):
            self.writer.close()
        try:
            await asyncio.wait_for(self.writer.wait_closed(), timeout=prazo)
        except (TimeoutError, asyncio.TimeoutError):
            _LOG.debug(
                "fechamento do IPC excedeu %.2fs; seguindo sem esperar",
                prazo,
            )
        except Exception as exc:
            _LOG.debug("erro ignorado ao fechar o IPC: %s", exc)

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Envia RPC e aguarda a resposta.

        ``timeout=None`` vale o prazo do método (a tabela da ponte; padrão curto
        para o que não está nela): esperar para sempre não existe.
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
        prazo = _prazo_do_metodo(method) if timeout is None else timeout

        async def _enviar_e_ler() -> bytes:
            await self.writer.drain()
            return await self.reader.readline()

        try:
            raw = await asyncio.wait_for(_enviar_e_ler(), timeout=prazo)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise IpcError(-1, f"o daemon não respondeu em {prazo:g} s") from exc

        if not raw:
            raise IpcError(-1, "conexão fechada pelo servidor antes da resposta")

        response = json.loads(raw.decode("utf-8"))
        if "error" in response:
            err = response["error"]
            raise IpcError(err["code"], err["message"])
        return response.get("result")


__all__ = ["IpcClient", "IpcError"]

