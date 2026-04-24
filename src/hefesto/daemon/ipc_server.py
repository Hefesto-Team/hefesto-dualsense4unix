"""IPC Unix socket JSON-RPC 2.0 (V2-3, ADR-005, `docs/protocol/ipc-unix-socket.md`).

NDJSON UTF-8, uma mensagem por linha. Métodos v1 + extensões:

    profile.switch       {name: str} -> {active_profile: str}
    profile.list         {}          -> {profiles: [{name, priority, match_type}]}
    profile.apply_draft  {triggers?, leds?, rumble?, mouse?} -> {status, applied: [str]}
    trigger.set          {side, mode, params} -> {status}
    trigger.reset        {side?}               -> {status}
    led.set              {rgb}                 -> {status}
    led.player_set       {bits: [bool]*5}      -> {status, bits}
    rumble.set           {weak, strong}        -> {status, weak, strong}
    rumble.stop          {}                    -> {status}
    rumble.passthrough   {enabled: bool}       -> {status}
    daemon.status        {}          -> {connected, transport, active_profile, battery_pct}
    daemon.state_full    {}          -> {... estado + mouse_emulation se daemon expõe}
    controller.list      {}          -> {controllers: [{connected, transport}]}
    daemon.reload        {}          -> {status}
    mouse.emulation.set  {enabled, speed?, scroll_speed?} -> {status, enabled}

Erros seguem JSON-RPC 2.0; códigos do domínio em `docs/protocol/ipc-unix-socket.md`.

AUDIT-FINDING-IPC-SERVER-SPLIT-01: handlers concretos moradores em
`ipc_handlers.py` (mixin `IpcHandlersMixin`); política de rumble em
`ipc_rumble_policy.py` (`apply_rumble_policy`). Este arquivo concentra o
contrato de IO, probe de socket, dispatcher e helpers JSON-RPC 2.0.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket as _socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto.core.controller import IController
from hefesto.daemon.ipc_handlers import DraftApplier, IpcHandlersMixin
from hefesto.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.manager import ProfileManager
from hefesto.utils.logging_config import get_logger
from hefesto.utils.xdg_paths import ipc_socket_path

logger = get_logger(__name__)

PROTOCOL_VERSION = "2.0"

CODE_CONTROLLER_DISCONNECTED = -32001
CODE_PROFILE_NOT_FOUND = -32002
CODE_INVALID_PARAMS = -32003
CODE_CONTROLLER_LOST = -32004
CODE_INTERNAL = -32603
CODE_METHOD_NOT_FOUND = -32601
CODE_PARSE_ERROR = -32700
CODE_INVALID_REQUEST = -32600

# Limite explícito de bytes por request JSON-RPC no dispatch. Cobre handler
# atuais (payloads tipicamente ~1-2 KiB) com folga generosa e protege contra
# payload gigante de cliente local malicioso (socket Unix restrito ao user).
# Ajuste defensivo — HARDEN-IPC-PAYLOAD-LIMIT-01.
MAX_PAYLOAD_BYTES = 32_768


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


# Compat: módulo re-exporta `_apply_rumble_policy` para testes ou chamadas
# legadas que ainda façam `from hefesto.daemon.ipc_server import _apply_rumble_policy`.
# Código novo deve importar de `hefesto.daemon.ipc_rumble_policy`.
_apply_rumble_policy = apply_rumble_policy


@dataclass
class IpcServer(IpcHandlersMixin):
    controller: IController
    store: StateStore
    profile_manager: ProfileManager
    socket_path: Path = field(default_factory=ipc_socket_path)
    # FEAT-MOUSE-01: ref opcional ao Daemon dono para habilitar/desabilitar
    # subsistemas dinamicamente (mouse emulation). Mantida como Any pra evitar
    # import circular; o Daemon faz o binding em _start_ipc.
    daemon: Any = None

    _handlers: dict[str, Handler] = field(default_factory=dict)
    _server: asyncio.base_events.Server | None = None
    _socket_inode: int | None = None

    def __post_init__(self) -> None:
        self._handlers = {
            "profile.switch": self._handle_profile_switch,
            "profile.list": self._handle_profile_list,
            "profile.apply_draft": self._handle_profile_apply_draft,
            "trigger.set": self._handle_trigger_set,
            "trigger.reset": self._handle_trigger_reset,
            "led.set": self._handle_led_set,
            "rumble.set": self._handle_rumble_set,
            "rumble.stop": self._handle_rumble_stop,
            "rumble.passthrough": self._handle_rumble_passthrough,
            "rumble.policy_set": self._handle_rumble_policy_set,
            "rumble.policy_custom": self._handle_rumble_policy_custom,
            "daemon.status": self._handle_daemon_status,
            "daemon.state_full": self._handle_daemon_state_full,
            "controller.list": self._handle_controller_list,
            "daemon.reload": self._handle_daemon_reload,
            "mouse.emulation.set": self._handle_mouse_emulation_set,
            "led.player_set": self._handle_led_player_set,
            "plugin.list": self._handle_plugin_list,
            "plugin.reload": self._handle_plugin_reload,
        }

    async def start(self) -> None:
        """Inicia o servidor.

        Antes de apagar qualquer arquivo no `socket_path`, executa um probe
        `AF_UNIX`/`SOCK_STREAM` com `connect()` e timeout de 0.1s para detectar
        se outro daemon já escuta no mesmo path:

        - Sucesso no `connect` -> socket vivo, outro daemon ativo.
          Levanta `RuntimeError` e NÃO toca o filesystem.
        - `ConnectionRefusedError` -> socket-resto (arquivo sem listener).
          Aplica `unlink()` e cria o listener novo.
        - `FileNotFoundError` -> path livre. Cria o listener direto.

        Registra o inode do socket recém-criado para permitir `stop()` verificar
        a propriedade antes de `unlink()` — evita apagar socket que outro
        processo tenha (re)criado no mesmo path após nosso bind.
        """
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._probe_socket_and_cleanup()

        self._server = await asyncio.start_unix_server(
            self._serve_client, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        with contextlib.suppress(FileNotFoundError):
            self._socket_inode = self.socket_path.stat().st_ino
        logger.info("ipc_server_listening", path=str(self.socket_path))

    def _probe_socket_and_cleanup(self) -> None:
        """Probe ativo para distinguir socket vivo de resto-morto.

        Lógica canônica (meta-regra 9.3, soberania de subsistema): jamais
        apagar recurso de outro daemon. Se o probe conectar, recusamos o start.
        """
        if not self.socket_path.exists():
            return

        probe = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        probe.settimeout(0.1)
        try:
            probe.connect(str(self.socket_path))
        except (ConnectionRefusedError, FileNotFoundError):
            # Socket-resto: arquivo sem listener. Seguro apagar.
            with contextlib.suppress(FileNotFoundError):
                self.socket_path.unlink()
            logger.info(
                "ipc_socket_stale_removido", path=str(self.socket_path)
            )
            return
        except OSError as exc:
            # Path existe mas não é socket válido (ex.: arquivo regular).
            # Fallback conservador: remove e segue.
            with contextlib.suppress(FileNotFoundError):
                self.socket_path.unlink()
            logger.warning(
                "ipc_socket_probe_os_error",
                path=str(self.socket_path),
                err=str(exc),
            )
            return
        else:
            msg = f"socket ocupado por outro daemon em {self.socket_path}"
            logger.error("ipc_socket_ocupado", path=str(self.socket_path))
            raise RuntimeError(msg)
        finally:
            with contextlib.suppress(Exception):
                probe.close()

    async def stop(self) -> None:
        """Encerra o servidor e remove o socket apenas se ainda formos o owner.

        Compara `st_ino` atual do path com o inode registrado em `start()`.
        Se divergir (outro daemon recriou o socket nesse path no meio-tempo),
        o `unlink()` é abortado. Atende meta-regra 9.3 (soberania de subsistema).
        """
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None

        if self._socket_inode is None:
            return
        try:
            current_inode = self.socket_path.stat().st_ino
        except FileNotFoundError:
            self._socket_inode = None
            return
        if current_inode == self._socket_inode:
            with contextlib.suppress(FileNotFoundError):
                self.socket_path.unlink()
        else:
            logger.warning(
                "ipc_socket_inode_divergente_skip_unlink",
                path=str(self.socket_path),
                inode_esperado=self._socket_inode,
                inode_atual=current_inode,
            )
        self._socket_inode = None

    async def _serve_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while not reader.at_eof():
                raw = await reader.readline()
                if not raw:
                    break
                response = await self._dispatch(raw)
                if response is not None:
                    writer.write(response + b"\n")
                    await writer.drain()
        except Exception as exc:
            logger.warning("ipc_client_error", err=str(exc), exc_info=True)
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _dispatch(self, raw: bytes) -> bytes | None:
        if len(raw) > MAX_PAYLOAD_BYTES:
            logger.warning(
                "ipc_payload_excede_limite", size=len(raw), limit=MAX_PAYLOAD_BYTES
            )
            return _json_rpc_error(
                None,
                CODE_INVALID_REQUEST,
                f"request excede limite de {MAX_PAYLOAD_BYTES} bytes",
            )
        try:
            payload = json.loads(raw.decode("utf-8").strip() or "null")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _json_rpc_error(None, CODE_PARSE_ERROR, f"parse: {exc}")
        if not isinstance(payload, dict):
            return _json_rpc_error(None, CODE_PARSE_ERROR, "payload não é objeto")

        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        if not isinstance(method, str):
            return _json_rpc_error(req_id, CODE_PARSE_ERROR, "method ausente")
        if not isinstance(params, dict):
            return _json_rpc_error(req_id, CODE_INVALID_PARAMS, "params não é objeto")

        handler = self._handlers.get(method)
        if handler is None:
            return _json_rpc_error(req_id, CODE_METHOD_NOT_FOUND, f"método desconhecido: {method}")

        try:
            result = await handler(params)
        except FileNotFoundError as exc:
            return _json_rpc_error(req_id, CODE_PROFILE_NOT_FOUND, str(exc))
        except ValueError as exc:
            return _json_rpc_error(req_id, CODE_INVALID_PARAMS, str(exc))
        except Exception as exc:
            # AUDIT-FINDING-PROFILE-PATH-TRAVERSAL-01: `str(exc)` podia vazar
            # path absoluto, valores internos e payload reconstituído via
            # ValidationError/OSError. Mensagem genérica com nome da classe;
            # detalhe integral fica nos logs (logger.exception abaixo).
            logger.exception("ipc_handler_error", method=method)
            return _json_rpc_error(
                req_id,
                CODE_INTERNAL,
                f"erro interno ({type(exc).__name__})",
            )

        if req_id is None:
            return None
        return _json_rpc_result(req_id, result)


def _json_rpc_result(req_id: Any, result: Any) -> bytes:
    payload = {"jsonrpc": PROTOCOL_VERSION, "id": req_id, "result": result}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _json_rpc_error(req_id: Any, code: int, message: str) -> bytes:
    payload = {
        "jsonrpc": PROTOCOL_VERSION,
        "id": req_id,
        "error": {"code": code, "message": message},
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


__all__ = [
    "CODE_CONTROLLER_DISCONNECTED",
    "CODE_CONTROLLER_LOST",
    "CODE_INTERNAL",
    "CODE_INVALID_PARAMS",
    "CODE_INVALID_REQUEST",
    "CODE_METHOD_NOT_FOUND",
    "CODE_PARSE_ERROR",
    "CODE_PROFILE_NOT_FOUND",
    "MAX_PAYLOAD_BYTES",
    "PROTOCOL_VERSION",
    "DraftApplier",
    "IpcServer",
    "_apply_rumble_policy",
    "apply_rumble_policy",
]
