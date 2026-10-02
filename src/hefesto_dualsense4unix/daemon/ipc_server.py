"""IPC Unix socket JSON-RPC 2.0 (V2-3, ADR-005, `docs/protocol/ipc-unix-socket.md`).

NDJSON UTF-8, uma mensagem por linha. Métodos v1 + extensões:

    profile.switch       {name: str} -> {active_profile: str}
    profile.list         {}          -> {profiles: [{name, priority, match_type}]}
    profile.apply_draft  {triggers?, leds?, rumble?, mouse?}
                         -> {status, applied: [str], failed: {str: str}}
    profile.reaplicar    {name: str} -> {active_profile, mode_aplicado, secoes}
    trigger.set    {side, mode, params, uniq?} -> {status, aplicado_em, guardado_em}
    trigger.reset  {side?, uniq?}              -> {status, aplicado_em, guardado_em}
    led.set              {rgb}                 -> {status}
    led.player_set       {bits: [bool]*5}      -> {status, bits}
    identity.renumber    {}          -> {ok, renumbered: {uniq: slot}} | {ok: false, reason}
    identity.number.set  {uniq, number} -> {ok, number, changed} | {ok: false, reason}
    rumble.set           {weak, strong}        -> {status, weak, strong}
    rumble.stop          {}                    -> {status}
    rumble.passthrough   {enabled: bool}       -> {status}
    rumble.motores.set   {uniq?, forte_pct?, fraco_pct?} -> {status, uniq, perfil,
                                                     gravado, forte_pct, fraco_pct}
    daemon.status        {}          -> {connected, transport, active_profile, battery_pct}
    daemon.state_full    {}          -> {... estado + mouse_emulation se daemon expõe}
    controller.list      {}          -> {controllers: [{index, connected, transport, is_primary?}]}
    controller.target.set {index|null} -> {status, target_index}
    daemon.reload        {}          -> {status}
    launch_env.refresh   {}          -> {status}
    mouse.emulation.set  {enabled, speed?, scroll_speed?} -> {status, enabled}
    mouse.emulation.restore {}                            -> {status, enabled}
    desktop.arranjo.apply {origin?}                       -> {status, arranjo}
                         O modo Navegação carregando o que a aba Navegação
                         gravou no perfil ATIVO — teclas, botões,
                         `teclado_emulado` e a queda da supressão —, e o mouse
                         LIGADO com as velocidades do perfil: entrar na
                         Navegação liga o mouse, pelo chip e pelo PS + R3
                         (D-2909-A-NAVEGACAO-LIGA-O-MOUSE). `arranjo` é
                         `seção → estado` no vocabulário de
                         `apply_profile_suppression`. Com `origin: manual` o
                         modo e o mouse ligado vão ao perfil ativo.
    keyboard.emulation.set {enabled: bool} -> {status, enabled, keyboard_emulation}
    desktop.status.set   {enabled: bool, origin?}
                         -> {status, enabled, mouse_emulation, keyboard_emulation,
                             perfil, gravado}
                         O «Status do Modo» da aba Navegação: o mouse, depois o
                         teclado, e com `origin: manual` o `mouse.enabled` e o
                         `teclado_emulado` no perfil ativo, numa gravação só.
    coop.set             {enabled: bool}       -> {status, enabled, players}
                         `enabled:false` é RECUSADO ({status: "recusado", motivo})
    coop.sync            {}                    -> {status, players, active}
    speaker.set          {volume?: 0-255, muted?: bool, rota?: 0-3,
                          fonte?: "mix"|"sfx", release?: bool, uniq?}
                         -> {status, speaker, fonte?}
                         `rota` é o OUTPUT_PATH_SEL do firmware: 0 estéreo no
                         fone · 1 mono no fone · 2 L=fone/TV, R=alto-falante
                         («Efeitos do Jogo») · 3 só no alto-falante. Ela estava
                         implementada e validada desde a SOM-ROTA-01 e FALTAVA
                         nesta linha — o contrato mentia por omissão, e foi
                         preciso ler o handler para descobrir que dava para
                         pedi-la (16/09/2026).
                         `fonte` é a CAMADA 1 (o PipeWire): `sfx` deixa o nó
                         daquele controle livre para o que o jogo endereçar a
                         ele, `mix` derrama nele todo o som da máquina sem
                         tirá-lo da TV. Ela exige `uniq` e não toma a posse do
                         volume. Entrou em 20/09/2026: até ali a escolha dela
                         só chegava ao nó pelo PERFIL ATIVO, e sem perfil ativo
                         não chegava nunca.
    mic.set              {muted: bool|null, uniq?} -> {status, audio, mic_mudo_desejado}
    mic.canal.set        {ligado: bool, uniq?}
                         -> {status, uniq, ligado, canal_feito, canal_motivo,
                             firmware_pedido, firmware_motivo, ativo, motivo}
                         `status` só é "ok" com as DUAS metades feitas
    mic.led.set          {aceso: bool|null, uniq?} -> {status, aceso}
    sensor.set           {uniq?, giroscopio?: bool, acelerometro?: bool}
                         -> {status, uniq, perfil, gravado, giroscopio,
                             acelerometro, alcance: {report, evdev}, ressalva}
                         `alcance` diz QUAL metade pegou: em Modo Nativo o jogo
                         lê o movimento pelo hidraw do FÍSICO e o daemon não
                         escreve ali — a `ressalva` carrega esse limite

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
import select
import socket as _socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.ipc_handlers import DraftApplier, IpcHandlersMixin
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
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

logger = get_logger(__name__)

# A versão do protocolo, os códigos de erro e o teto do payload moram em

#: O-APP-RESPONDE-NA-HORA-01 (02/10/2026): o pedido que passa deste teto vai ao
#: do laço (10 s): a materialização segurava o laço de 0,4 a 2,8 s por gesto, e
TETO_DO_PEDIDO_MS = 100.0

#: (02/10/2026): o `state_full` e o `controller.list` só leem (contadores e
PERGUNTAS_QUE_NAO_RODAM_ABANDONADAS = frozenset(
    {"daemon.state_full", "controller.list", "profile.list"}
)


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


# legadas que ainda façam `from hefesto_dualsense4unix.daemon.ipc_server import _apply_rumble_policy`.  # noqa: E501
_apply_rumble_policy = apply_rumble_policy


@dataclass
class IpcServer(IpcHandlersMixin):
    controller: IController
    store: StateStore
    profile_manager: ProfileManager
    socket_path: Path = field(default_factory=ipc_socket_path)
    # import circular; o Daemon faz o binding em _start_ipc.
    daemon: Any = None

    _handlers: dict[str, Handler] = field(default_factory=dict)
    _server: asyncio.base_events.Server | None = None
    _socket_inode: int | None = None
    _escrevente: Any = None

    def __post_init__(self) -> None:
        self._handlers = {
            "profile.switch": self._handle_profile_switch,
            "profile.list": self._handle_profile_list,
            "profile.apply_draft": self._handle_profile_apply_draft,
            "profile.reaplicar": self._handle_profile_reaplicar,
            "trigger.set": self._handle_trigger_set,
            "trigger.reset": self._handle_trigger_reset,
            "led.set": self._handle_led_set,
            # janela. `trigger` tinha o `trigger.reset`, `rumble` tinha o
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
            # de ~3,4 s, e o controle negativo, fora dela, não travou.
            "lightbar.reset": self._handle_lightbar_reset,
            "debug.player_leds": self._handle_debug_player_leds,
            # D4: volume/mudo do alto-falante do DualSense (assume a posse dos
            "speaker.set": self._handle_speaker_set,
            "mic.set": self._handle_mic_set,
            "mic.canal.set": self._handle_mic_canal_set,
            "mic.led.set": self._handle_mic_led_set,
            "mic.volume.set": self._handle_mic_volume_set,
            "mouse.emulation.set": self._handle_mouse_emulation_set,
            "mouse.emulation.restore": self._handle_mouse_emulation_restore,
            # modo Navegação. Ele SUBSTITUI o `mouse.emulation.restore` no
            "desktop.arranjo.apply": self._handle_desktop_arranjo_apply,
            "keyboard.emulation.set": self._handle_keyboard_emulation_set,
            "desktop.status.set": self._handle_desktop_status_set,
            "gamepad.emulation.set": self._handle_gamepad_emulation_set,
            "gamepad.mask.set": self._handle_gamepad_mask_set,
            "coop.set": self._handle_coop_set,
            "coop.sync": self._handle_coop_sync,
            "daemon.emulation.suppress": self._handle_emulation_suppress,
            "led.player_set": self._handle_led_player_set,
            "led.player_brightness_set": self._handle_led_player_brightness_set,
            "identity.renumber": self._handle_identity_renumber,
            "identity.number.set": self._handle_identity_number_set,
            # `daemon.reload` LEVANTA em chave que não é campo do `DaemonConfig`.
            "machine.declare": self._handle_machine_declare,
            "plugin.list": self._handle_plugin_list,
            "plugin.reload": self._handle_plugin_reload,
            "radio.ponte.ligar_aqui": self._handle_radio_ponte_ligar_aqui,
            "radio.mover": self._handle_radio_mover,
            "mira.set": self._handle_mira_set,
            "haptica.testar": self._handle_haptica_testar,
            "radio.busca.set": self._handle_radio_busca_set,
            "radio.dispensar": self._handle_radio_dispensar,
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
        try:
            result = await handler(params)
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
            ms = (time.perf_counter() - t0) * 1000
            if ms > TETO_DO_PEDIDO_MS:
                logger.info("ipc_lento", metodo=method, ms=round(ms))

        if req_id is None:
            return None
        return _json_rpc_result(req_id, result)


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
    "DraftApplier",
    "IpcServer",
    "_apply_rumble_policy",
    "apply_rumble_policy",
]
