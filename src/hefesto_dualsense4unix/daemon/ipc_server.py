"""O servidor IPC do daemon: JSON-RPC 2.0 em socket Unix, NDJSON UTF-8, uma mensagem por linha.

Aqui moram o contrato de IO, a sondagem do socket, o dispatcher (`_handlers`) e os ajudantes do
JSON-RPC 2.0; os handlers estão em `ipc_handlers.py` (`IpcHandlersMixin`) e a política de rumble
em `ipc_rumble_policy.py`. O contrato (métodos, parâmetros, retornos e códigos de erro) tem um
lugar só, `docs/protocol/ipc-unix-socket.md`, cuja lista de métodos se gera deste dispatcher.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import select
import socket as _socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import (
    CODE_CONTROLLER_DISCONNECTED,
    CODE_CONTROLLER_LOST,
    CODE_INTERNAL,
    CODE_INVALID_PARAMS,
    CODE_INVALID_REQUEST,
    CODE_METHOD_NOT_FOUND,
    CODE_PARSE_ERROR,
    CODE_PROFILE_NOT_FOUND,
    MAX_PAYLOAD_BYTES,
    PROTOCOL_VERSION,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.loader import gesto_de_agora
from hefesto_dualsense4unix.profiles.manager import ProfileManager, gravacao_do_pedido
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

logger = get_logger(__name__)

TETO_DO_PEDIDO_MS = 100.0

PERGUNTAS_QUE_NAO_RODAM_ABANDONADAS = frozenset(
    {"daemon.state_full", "controller.list", "profile.list"}
)


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


_apply_rumble_policy = apply_rumble_policy


@dataclass
class IpcServer(IpcHandlersMixin):
    controller: IController
    store: StateStore
    profile_manager: ProfileManager
    socket_path: Path = field(default_factory=ipc_socket_path)
    daemon: Any = None

    _handlers: dict[str, Handler] = field(default_factory=dict)
    _server: asyncio.base_events.Server | None = None
    _socket_inode: int | None = None
    _escrevente: Any = None

    def __post_init__(self) -> None:
        self._handlers = {
            "profile.switch": self._handle_profile_switch,
            "profile.list": self._handle_profile_list,
            "profile.reaplicar": self._handle_profile_reaplicar,
            "trigger.set": self._handle_trigger_set,
            "trigger.reset": self._handle_trigger_reset,
            "led.set": self._handle_led_set,
            "led.auto_release": self._handle_led_auto_release,
            "rumble.set": self._handle_rumble_set,
            "rumble.stop": self._handle_rumble_stop,
            "rumble.passthrough": self._handle_rumble_passthrough,
            "rumble.policy_set": self._handle_rumble_policy_set,
            "rumble.policy_custom": self._handle_rumble_policy_custom,
            "rumble.motores.set": self._handle_rumble_motores_set,
            "sensor.set": self._handle_sensor_set,
            "daemon.status": self._handle_daemon_status,
            "daemon.state_full": self._handle_daemon_state_full,
            "daemon.pause": self._handle_daemon_pause,
            "daemon.resume": self._handle_daemon_resume,
            "freestyle.set": self._handle_freestyle_set,
            "native.mode.set": self._handle_native_mode_set,
            "controller.list": self._handle_controller_list,
            "controller.target.set": self._handle_controller_target_set,
            "daemon.reload": self._handle_daemon_reload,
            "launch_env.refresh": self._handle_launch_env_refresh,
            "lightbar.reset": self._handle_lightbar_reset,
            "debug.player_leds": self._handle_debug_player_leds,
            "speaker.set": self._handle_speaker_set,
            "mic.set": self._handle_mic_set,
            "mic.canal.set": self._handle_mic_canal_set,
            "mic.led.set": self._handle_mic_led_set,
            "mic.volume.set": self._handle_mic_volume_set,
            "mouse.emulation.set": self._handle_mouse_emulation_set,
            "mouse.emulation.restore": self._handle_mouse_emulation_restore,
            "desktop.arranjo.apply": self._handle_desktop_arranjo_apply,
            "desktop.arranjo.repor": self._handle_desktop_arranjo_repor,
            "keyboard.emulation.set": self._handle_keyboard_emulation_set,
            "desktop.status.set": self._handle_desktop_status_set,
            "navegacao.interna.set": self._handle_navegacao_interna_set,
            "navegacao.foco": self._handle_navegacao_foco,
            "navegacao.big_picture.set": self._handle_navegacao_big_picture_set,
            "gamepad.emulation.set": self._handle_gamepad_emulation_set,
            "gamepad.mask.set": self._handle_gamepad_mask_set,
            "coop.set": self._handle_coop_set,
            "coop.sync": self._handle_coop_sync,
            "daemon.emulation.suppress": self._handle_emulation_suppress,
            "led.player_set": self._handle_led_player_set,
            "led.player_brightness_set": self._handle_led_player_brightness_set,
            "identity.renumber": self._handle_identity_renumber,
            "identity.number.set": self._handle_identity_number_set,
            "machine.declare": self._handle_machine_declare,
            "plugin.list": self._handle_plugin_list,
            "plugin.reload": self._handle_plugin_reload,
            "mods.agora": self._handle_mods_agora,
            "mods.parar_tudo": self._handle_mods_parar_tudo,
            "mods.jogos": self._handle_mods_jogos,
            "mods.acao": self._handle_mods_acao,
            "mods.livre": self._handle_mods_livre,
            "mods.opcao": self._handle_mods_opcao,
            "mods.mensagem": self._handle_mods_mensagem,
            "radio.ponte.ligar_aqui": self._handle_radio_ponte_ligar_aqui,
            "radio.mover": self._handle_radio_mover,
            "mira.set": self._handle_mira_set,
            "haptica.testar": self._handle_haptica_testar,
            "radio.busca.set": self._handle_radio_busca_set,
            "radio.dispensar": self._handle_radio_dispensar,
            "motion.calibrate": self._handle_motion_calibrate,
            "perfil.ativacao.set": self._handle_perfil_ativacao_set,
            "perfil.analogicos.set": self._handle_perfil_analogicos_set,
            "perfil.cursor.set": self._handle_perfil_cursor_set,
            "sequencia.gravar": self._handle_sequencia_gravar,
            "sequencia.tocar": self._handle_sequencia_tocar,
            "motion.sinal": self._handle_motion_sinal,
            "motion.rampa": self._handle_motion_rampa,
        }

    async def start(self) -> None:
        """Inicia o servidor."""
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._probe_socket_and_cleanup()

        self._server = await asyncio.start_unix_server(
            self._serve_client, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        with contextlib.suppress(FileNotFoundError):
            self._socket_inode = self.socket_path.stat().st_ino
        logger.info("ipc_server_listening", path=str(self.socket_path))
        laco = asyncio.get_running_loop()

        def devolver(acao: Callable[[], None]) -> None:
            with contextlib.suppress(RuntimeError):
                laco.call_soon_threadsafe(acao)

        self._escrevente = launch_env.armar_o_escrevente(devolver, laco)

    def _probe_socket_and_cleanup(self) -> None:
        """Probe ativo para distinguir socket vivo de resto-morto."""
        if not self.socket_path.exists():
            return

        probe = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        probe.settimeout(0.1)
        try:
            probe.connect(str(self.socket_path))
        except (ConnectionRefusedError, FileNotFoundError):
            with contextlib.suppress(FileNotFoundError):
                self.socket_path.unlink()
            logger.info(
                "ipc_socket_stale_removido", path=str(self.socket_path)
            )
            return
        except OSError as exc:
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
        """Encerra o servidor e remove o socket apenas se ainda formos o owner."""
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        self._tirar_o_socket()
        escrevente, self._escrevente = self._escrevente, None
        if escrevente is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(launch_env.desarmar_o_escrevente, escrevente)
        hub = self._sensor_hub
        if hub is not None:
            await asyncio.to_thread(hub.stop_all)

    def _tirar_o_socket(self) -> None:
        """Remove o socket do disco só se ainda formos o owner (o inode do `start`)."""
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
                response = await self._dispatch(
                    raw, abandonado=lambda: _o_cliente_ja_foi(writer)
                )
                if response is not None:
                    writer.write(response + b"\n")
                    await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            logger.debug("ipc_client_disconnect", err=str(exc))
        except Exception as exc:
            logger.warning("ipc_client_error", err=str(exc), exc_info=True)
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _dispatch(
        self, raw: bytes, abandonado: Callable[[], bool] | None = None
    ) -> bytes | None:
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

        if (
            method in PERGUNTAS_QUE_NAO_RODAM_ABANDONADAS
            and abandonado is not None
            and abandonado()
        ):
            logger.debug("ipc_pergunta_abandonada", metodo=method)
            return None

        t0 = time.perf_counter()
        marca_do_gesto = gesto_de_agora.set(f"ipc:{method}")
        status = "erro"
        try:
            result = await handler(params)
            await _o_perfil_em_dia()
            status = "ok"
        except FileNotFoundError as exc:
            return _json_rpc_error(req_id, CODE_PROFILE_NOT_FOUND, str(exc))
        except ValueError as exc:
            return _json_rpc_error(req_id, CODE_INVALID_PARAMS, str(exc))
        except Exception as exc:
            logger.exception("ipc_handler_error", method=method)
            return _json_rpc_error(
                req_id,
                CODE_INTERNAL,
                f"erro interno ({type(exc).__name__})",
            )
        finally:
            gesto_de_agora.reset(marca_do_gesto)
            self.store.bump(f"ipc.{method}.{status}")
            ms = (time.perf_counter() - t0) * 1000
            if ms > TETO_DO_PEDIDO_MS:
                logger.info("ipc_lento", metodo=method, ms=round(ms))

        if req_id is None:
            return None
        return _json_rpc_result(req_id, result)


async def _o_perfil_em_dia() -> None:
    """A resposta do gesto sai com o modo no disco; só ele espera, e nunca o laço.

    A pergunta de outro cliente não paga o disco do gesto: era o `[daemon mudo]` por outra porta.
    O ``shield`` guarda a gravação da fila: quem desiste de esperar não a cancela.
    """
    feito = gravacao_do_pedido()
    if feito is not None:
        await asyncio.shield(asyncio.wrap_future(feito))


def _o_cliente_ja_foi(writer: asyncio.StreamWriter) -> bool:
    """O cliente FECHOU a conexão? (O-APP-RESPONDE-NA-HORA-01)"""
    sock = writer.get_extra_info("socket")
    try:
        fd = sock.fileno() if sock is not None else -1
    except Exception:
        return False
    if fd < 0:
        return sock is not None
    sonda = select.poll()
    sonda.register(fd, select.POLLIN)
    return any(
        evento & (select.POLLHUP | select.POLLERR) for _fd, evento in sonda.poll(0)
    )


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
    "PERGUNTAS_QUE_NAO_RODAM_ABANDONADAS",
    "PROTOCOL_VERSION",
    "TETO_DO_PEDIDO_MS",
    "IpcServer",
    "_apply_rumble_policy",
    "apply_rumble_policy",
]
