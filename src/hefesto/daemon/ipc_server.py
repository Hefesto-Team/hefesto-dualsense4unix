"""IPC Unix socket JSON-RPC 2.0 (V2-3, ADR-005, `docs/protocol/ipc-unix-socket.md`).

NDJSON UTF-8, uma mensagem por linha. Métodos v1 + extensões:

    profile.switch       {name: str} -> {active_profile: str}
    profile.list         {}          -> {profiles: [{name, priority, match_type}]}
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
from hefesto.core.trigger_effects import build_from_name
from hefesto.core.trigger_effects import off as trigger_off
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.manager import ProfileManager
from hefesto.profiles.schema import MatchAny
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


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class IpcServer:
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
            "trigger.set": self._handle_trigger_set,
            "trigger.reset": self._handle_trigger_reset,
            "led.set": self._handle_led_set,
            "rumble.set": self._handle_rumble_set,
            "rumble.stop": self._handle_rumble_stop,
            "rumble.passthrough": self._handle_rumble_passthrough,
            "daemon.status": self._handle_daemon_status,
            "daemon.state_full": self._handle_daemon_state_full,
            "controller.list": self._handle_controller_list,
            "daemon.reload": self._handle_daemon_reload,
            "mouse.emulation.set": self._handle_mouse_emulation_set,
            "led.player_set": self._handle_led_player_set,
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
            logger.warning("ipc_client_error", err=str(exc))
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _dispatch(self, raw: bytes) -> bytes | None:
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
            return _json_rpc_error(req_id, CODE_METHOD_NOT_FOUND, f"metodo desconhecido: {method}")

        try:
            result = await handler(params)
        except FileNotFoundError as exc:
            return _json_rpc_error(req_id, CODE_PROFILE_NOT_FOUND, str(exc))
        except ValueError as exc:
            return _json_rpc_error(req_id, CODE_INVALID_PARAMS, str(exc))
        except Exception as exc:
            logger.exception("ipc_handler_error", method=method)
            return _json_rpc_error(req_id, CODE_INTERNAL, str(exc))

        if req_id is None:
            return None
        return _json_rpc_result(req_id, result)

    # --- handlers --------------------------------------------------------

    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.switch exige 'name' string")
        profile = self.profile_manager.activate(name)
        # Usuário escolheu perfil explícito: libera autoswitch de novo
        # (BUG-MOUSE-TRIGGERS-01).
        self.store.clear_manual_trigger_active()
        return {"active_profile": profile.name}

    async def _handle_profile_list(self, params: dict[str, Any]) -> dict[str, Any]:
        profiles = self.profile_manager.list_profiles()
        return {
            "profiles": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": "any" if isinstance(p.match, MatchAny) else "criteria",
                }
                for p in profiles
            ]
        }

    async def _handle_trigger_set(self, params: dict[str, Any]) -> dict[str, Any]:
        side = params.get("side")
        mode = params.get("mode")
        trigger_params = params.get("params", [])
        if side not in ("left", "right"):
            raise ValueError("trigger.set: side precisa ser 'left' ou 'right'")
        if not isinstance(mode, str):
            raise ValueError("trigger.set: mode precisa ser string")
        if not isinstance(trigger_params, list):
            raise ValueError("trigger.set: params precisa ser lista")
        effect = build_from_name(mode, trigger_params)
        self.controller.set_trigger(side, effect)
        # BUG-MOUSE-TRIGGERS-01: usuário aplicou trigger manual via GUI/IPC.
        # Marca override para o autoswitch não sobrescrever (especialmente
        # ao ligar emulação de mouse, cujo movimento muda foco de janela).
        self.store.mark_manual_trigger_active()
        return {"status": "ok"}

    async def _handle_trigger_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        target = params.get("side", "both")
        if target not in ("left", "right", "both"):
            raise ValueError("trigger.reset: side deve ser left|right|both")
        if target in ("left", "both"):
            self.controller.set_trigger("left", trigger_off())
        if target in ("right", "both"):
            self.controller.set_trigger("right", trigger_off())
        # Reset explícito libera autoswitch de volta (BUG-MOUSE-TRIGGERS-01).
        self.store.clear_manual_trigger_active()
        return {"status": "ok"}

    async def _handle_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        rgb = params.get("rgb")
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("led.set: rgb precisa ser lista com 3 inteiros")
        for idx, v in enumerate(rgb):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise ValueError(f"led.set: rgb[{idx}] fora de byte")
        # brightness opcional (FEAT-LED-BRIGHTNESS-01): multiplicador 0.0-1.0.
        # Ausente ou inválido -> assume 1.0 (retrocompatível com chamadas v1).
        brightness_raw = params.get("brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("led.set: brightness precisa ser numerico") from exc
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"led.set: brightness fora de [0.0, 1.0]: {brightness}"
            )
        r = max(0, min(255, int(rgb[0] * brightness)))
        g = max(0, min(255, int(rgb[1] * brightness)))
        b = max(0, min(255, int(rgb[2] * brightness)))
        self.controller.set_led((r, g, b))
        return {"status": "ok"}

    async def _handle_led_player_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica bitmask de 5 LEDs de player no controle.

        Params:
            bits: lista de 5 booleanos (LED1..LED5).
        """
        bits_raw = params.get("bits")
        if not isinstance(bits_raw, list) or len(bits_raw) != 5:
            raise ValueError("led.player_set: 'bits' precisa ser lista com exatamente 5 booleanos")
        for idx, v in enumerate(bits_raw):
            if not isinstance(v, bool):
                raise ValueError(f"led.player_set: bits[{idx}] precisa ser booleano")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bits_raw[0], bits_raw[1], bits_raw[2], bits_raw[3], bits_raw[4]
        )
        self.controller.set_player_leds(bits)
        return {"status": "ok", "bits": list(bits)}

    async def _handle_daemon_status(self, params: dict[str, Any]) -> dict[str, Any]:
        snap = self.store.snapshot()
        controller = snap.controller
        return {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            "battery_pct": controller.battery_pct if controller else None,
        }

    async def _handle_daemon_state_full(self, params: dict[str, Any]) -> dict[str, Any]:
        """Estado completo pra GUI consumir a 20Hz.

        FEAT-CLI-PARITY-01: inclui bloco `mouse_emulation` com enabled/speed/
        scroll_speed para o subcomando `hefesto mouse status` consultar via IPC.
        Quando `self.daemon` for None (contextos de teste ou modos legados),
        o bloco é omitido e o cliente trata como "estado indisponível".
        """
        snap = self.store.snapshot()
        controller = snap.controller

        # Tenta ler buttons do evdev reader do backend, se acessivel
        buttons: list[str] = []
        try:
            evdev_reader = getattr(self.controller, "_evdev", None)
            if evdev_reader is not None and evdev_reader.is_available():
                ev_snap = evdev_reader.snapshot()
                buttons = sorted(ev_snap.buttons_pressed)
        except Exception:
            buttons = []

        result: dict[str, Any] = {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            "battery_pct": controller.battery_pct if controller else None,
            "l2_raw": controller.l2_raw if controller else 0,
            "r2_raw": controller.r2_raw if controller else 0,
            "lx": controller.raw_lx if controller else 128,
            "ly": controller.raw_ly if controller else 128,
            "rx": controller.raw_rx if controller else 128,
            "ry": controller.raw_ry if controller else 128,
            "buttons": buttons,
            "counters": snap.counters,
        }

        # Paridade CLI-GUI: expõe estado da emulação de mouse se o daemon
        # dono da IPC tiver config acessível (FEAT-CLI-PARITY-01).
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
                "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
                "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            }

        return result

    async def _handle_rumble_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica rumble e persiste estado para re-asserção contínua (BUG-RUMBLE-APPLY-IGNORED-01).

        Atualiza daemon.config.rumble_active para que o poll loop re-afirme
        os valores a cada 200ms, garantindo vibração contínua mesmo com outros
        writes HID de LED/trigger que possam zerar os motores.
        """
        weak = params.get("weak")
        strong = params.get("strong")
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.set exige 'weak' e 'strong' inteiros 0-255")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        # Persiste estado antes de aplicar para o poll loop continuar re-afirmando.
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
        self.controller.set_rumble(weak=weak, strong=strong)
        return {"status": "ok", "weak": weak, "strong": strong}

    async def _handle_rumble_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Para rumble e persiste estado (0, 0) (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera os motores imediatamente e atualiza daemon.config.rumble_active para
        (0, 0) de forma que o poll loop re-afirme o silêncio, evitando que outro
        write HID re-ative motores inadvertidamente. Use rumble.passthrough para
        liberar controle completo ao jogo.
        """
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (0, 0)
        self.controller.set_rumble(weak=0, strong=0)
        return {"status": "ok"}

    async def _handle_rumble_passthrough(self, params: dict[str, Any]) -> dict[str, Any]:
        """Libera controle de rumble para jogo/UDP (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera daemon.config.rumble_active, desativando a re-asserção do poll loop.
        O jogo retoma controle via UDP ou emulação Xbox360. Use rumble.set para
        retomar controle manual.

        Params:
            enabled: bool — True = habilitar passthrough (zerar rumble_active).
                            False = sem efeito; para fixar valores use rumble.set.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("rumble.passthrough exige 'enabled' boolean")
        if enabled:
            daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
        return {"status": "ok", "passthrough": enabled}

    async def _handle_controller_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "controllers": [
                {
                    "connected": self.controller.is_connected(),
                    "transport": self.controller.get_transport()
                    if self.controller.is_connected()
                    else None,
                }
            ]
        }

    async def _handle_daemon_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        # Placeholder: reload de config chega em W4.1+ quando tivermos daemon.toml real.
        return {"status": "ok", "reloaded": True}

    async def _handle_mouse_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01).

        Params:
            enabled: bool (obrigatório)
            speed: int 1-12 (opcional)
            scroll_speed: int 1-5 (opcional)
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("mouse.emulation.set exige 'enabled' boolean")
        speed = params.get("speed")
        scroll_speed = params.get("scroll_speed")
        if speed is not None and not isinstance(speed, int):
            raise ValueError("mouse.emulation.set: 'speed' precisa ser int")
        if scroll_speed is not None and not isinstance(scroll_speed, int):
            raise ValueError("mouse.emulation.set: 'scroll_speed' precisa ser int")

        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled, speed=speed, scroll_speed=scroll_speed
        )
        return {"status": "ok" if ok else "failed", "enabled": enabled and ok}


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
    "CODE_METHOD_NOT_FOUND",
    "CODE_PARSE_ERROR",
    "CODE_PROFILE_NOT_FOUND",
    "PROTOCOL_VERSION",
    "IpcServer",
]
