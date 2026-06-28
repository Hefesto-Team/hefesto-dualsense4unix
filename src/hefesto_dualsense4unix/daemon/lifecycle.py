"""Ciclo de vida do daemon: orquestrador slim (ADR-015).

O daemon é composto por:
  - 1 IController (real ou fake) conectado ao dispositivo.
  - 1 EventBus global.
  - 1 StateStore global.
  - Tasks async: poll_loop e subsystems opcionais.

Daemon.run() orquestra connect → subsystems → run_until_stopped → shutdown.
Toda lógica interna foi extraída para src/hefesto_dualsense4unix/daemon/subsystems/.

Backcompat (REFACTOR-LIFECYCLE-01): todos os nomes públicos que existiam antes
do refactor são reexportados aqui para que imports externos continuem funcionando
sem alteração.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import signal
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from hefesto_dualsense4unix.core.controller import ControllerState, IController
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.state_store import StateStore

# ---------------------------------------------------------------------------
# Reexportações de backcompat — NÃO remover (testes importam diretamente).
# ---------------------------------------------------------------------------
from hefesto_dualsense4unix.daemon.subsystems.poll import (
    BATTERY_DEBOUNCE_SEC,
    BATTERY_DELTA_THRESHOLD_PCT,
    BATTERY_MIN_INTERVAL_SEC,
    BatteryDebouncer,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    AUTO_DEBOUNCE_SEC,
    RUMBLE_POLICY_MULT,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_HZ = 60

#: Período de assentamento (settling/grace) pós-conexão em segundos
#: (BUG-DAEMON-CONNECT-GHOST-INPUT-01). Enquanto ativo, o poll loop continua
#: lendo estado/bateria e publicando STATE_UPDATE, mas NÃO despacha
#: teclado/mouse/hotkey nem publica BUTTON_DOWN/UP. Cobre a janela em que o
#: HID-raw ainda está cru (ex.: micBtn fantasma) e o snapshot evdev ainda
#: popula após o plug — barrando o mute fantasma e os "comandos aleatórios"
#: na origem. ~0.3s é compromisso entre cobrir o settling do firmware e a
#: latência percebida até o input ficar responsivo.
INPUT_GRACE_SEC: float = 0.3

#: FEAT-DSX-EVDEV-WATCHDOG-01: intervalo entre checagens de "node de evdev
#: obsoleto" no poll loop. Cada checagem escaneia /dev/input, então não roda
#: todo tick; 2s é folgado o bastante para não pesar e rápido para recuperar o
#: controle logo após uma re-enumeração (storm -71 / replug).
EVDEV_WATCHDOG_SEC: float = 2.0


# ---------------------------------------------------------------------------
# DaemonConfig
# ---------------------------------------------------------------------------


@dataclass
class DaemonConfig:
    poll_hz: int = DEFAULT_POLL_HZ
    auto_reconnect: bool = True
    reconnect_backoff_sec: float = 2.0
    ipc_enabled: bool = True
    udp_enabled: bool = True
    udp_host: str = "127.0.0.1"
    udp_port: int = 6969
    autoswitch_enabled: bool = True
    # FEAT-MOUSE-01
    mouse_emulation_enabled: bool = False
    mouse_speed: int = 6
    mouse_scroll_speed: int = 1
    # FEAT-DSX-GAMEPAD-FLAVOR-01 — gamepad virtual integrado ao daemon (1 leitor
    # → fan-out, sem o conflito de 2 leitores do `emulate xbox360` avulso).
    # Mutuamente exclusivo com mouse_emulation: ligar o gamepad desliga o mouse
    # (jogar = controle vai pro jogo, não pro cursor). flavor: dualsense|xbox.
    gamepad_emulation_enabled: bool = False
    gamepad_flavor: str = "dualsense"
    # FEAT-DSX-COOP-LOCAL-01 — co-op local: cada controle físico vira um jogador
    # (P1, P2, …) com seu próprio gamepad virtual, em vez do modo "N controles, 1
    # player" (broadcast). OFF por default (preserva o uso de reserva/troca de
    # controle). Só tem efeito com a emulação de gamepad ligada + 2+ controles.
    coop_enabled: bool = False
    # FEAT-KEYBOARD-EMULATOR-01 — emula teclado virtual a partir de botões
    # do DualSense. Default True: infraestrutura já sobe com os bindings
    # default (Options/Share/L1/R1). Sub-sprints futuras expõem UI+persist.
    keyboard_emulation_enabled: bool = True
    # FEAT-HOTKEY-STEAM-01
    ps_button_action: Literal["steam", "none", "custom"] = "steam"
    ps_button_command: list[str] = field(default_factory=list)
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01 — ms de hold do PS para alternar o
    # modo-jogo (supressão da emulação mouse/teclado). 0 = desliga o gesto (PS
    # então só faz a ação solo, ex. abrir Steam). Default 0: o modo jogo é só
    # pelo combo PS+Options; o long-press de 1000ms causava toggle ACIDENTAL
    # quando o toque de "abrir Steam" passava de ~1s.
    ps_long_press_ms: int = 0
    # BUG-RUMBLE-APPLY-IGNORED-01
    rumble_active: tuple[int, int] | None = None
    # FEAT-RUMBLE-POLICY-01
    rumble_policy: Literal["economia", "balanceado", "max", "auto", "custom"] = "balanceado"
    rumble_policy_custom_mult: float = 0.7
    # FEAT-HOTKEY-MIC-01
    mic_button_toggles_system: bool = True
    # FEAT-METRICS-01
    metrics_enabled: bool = False
    metrics_port: int = 9090
    # FEAT-PLUGIN-01 — opt-in: código de usuário arbitrario, desativado por padrao.
    plugins_enabled: bool = False


# ---------------------------------------------------------------------------
# Daemon (orquestrador)
# ---------------------------------------------------------------------------


@dataclass
class Daemon:
    """Orquestrador do daemon. API pública preservada (REFACTOR-LIFECYCLE-01).

    Atributos públicos (mantidos para backcompat de testes):
      controller, bus, store, config, _hotkey_manager, _audio, _mouse_device,
      _ipc_server, _udp_server, _autoswitch, _last_auto_mult, _last_auto_change_at.
    """

    controller: IController
    bus: EventBus = field(default_factory=EventBus)
    store: StateStore = field(default_factory=StateStore)
    config: DaemonConfig = field(default_factory=DaemonConfig)

    _stop_event: asyncio.Event | None = None
    _executor: ThreadPoolExecutor | None = None
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _ipc_server: Any = None
    _udp_server: Any = None
    _autoswitch: Any = None
    _mouse_device: Any = None
    _keyboard_device: Any = None
    # FEAT-DSX-GAMEPAD-FLAVOR-01 — UinputGamepad criado em runtime por
    # start_gamepad_emulation; None quando o gamepad virtual está desligado.
    _gamepad_device: Any = None
    # FEAT-DSX-COOP-LOCAL-01 — CoopManager: jogadores secundários (P2+) do co-op
    # local. Criado sob demanda por `get_coop_manager`; None até o 1º uso.
    _coop_manager: Any = None
    _hotkey_manager: Any = None
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: quando True, o poll loop não despacha
    # mouse/teclado (devices ficam vivos; hotkeys seguem ativos). Alternado pelo
    # long-press do PS. Transitório — não persiste entre boots.
    _emulation_suppressed: bool = False
    _audio: Any = None
    _plugins_subsystem: Any = None
    # BUG-DAEMON-NO-DEVICE-FATAL-01 — task de probe de conexão em background
    # (substitui connect_with_retry bloqueante no boot). Cancelada em shutdown.
    _reconnect_task: asyncio.Task[Any] | None = None
    _last_auto_mult: float = field(default=0.7)
    _last_auto_change_at: float = field(default=0.0)
    # BUG-DAEMON-CONNECT-GHOST-INPUT-01 — instante (loop.time()) a partir do
    # qual o input emulado volta a ser despachado após uma (re)conexão. Setado
    # pelo poll loop na borda desconectado→conectado e rearmado em reconexão.
    # Enquanto loop.time() < _input_ready_at, BUTTON_DOWN/UP + dispatch de
    # teclado/mouse/hotkey ficam suprimidos (settling/grace). 0.0 = sem grace
    # pendente (estado inicial, antes da 1ª conexão; o poll loop só arma o
    # grace ao detectar a borda de conexão).
    _input_ready_at: float = field(default=0.0)
    # CLUSTER-IPC-STATE-PROFILE-01 (Bug A) — cache do último estado lido pelo
    # _poll_loop. Permite que `daemon.state_full` reflita o tick atual em vez
    # de só o snapshot do StateStore (que pode estar estagnado em fallback HID
    # se o evdev_reader não conectou). Atualizado 1x por tick em _poll_loop;
    # zerado em shutdown.
    _last_state: ControllerState | None = None
    # FEAT-KEYBOARD-EMULATOR-01: criados em runtime por start_keyboard_emulation
    # (OSK helper + touchpad reader). Declarados aqui para satisfazer mypy
    # strict via DaemonProtocol (PYDANTIC-PROTOCOL-DAEMON-01).
    _osk_controller: Any = None
    _touchpad_reader: Any = None
    # FEAT-DAEMON-PAUSE-RESUME-01: pausado, o poll loop segue lendo estado/
    # bateria e publicando STATE_UPDATE, mas NÃO despacha input (gatilhos/
    # teclado/mouse/hotkey) nem publica BUTTON_DOWN/UP — daemon vivo, sem afetar
    # o sistema. Reusa o gate do grace-period; persistido via utils.session.
    _paused: bool = field(default=False)
    # FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01: subsystems que falharam ao iniciar
    # (nome -> erro). Um subsystem quebrado é isolado aqui em vez de derrubar o
    # daemon (poll/IPC/perfis seguem). Exposto para diagnóstico (doctor/status).
    _failed_subsystems: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Ciclo de vida público
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Entry point: subsystems → reconnect_loop em background → wait → shutdown.

        BUG-DAEMON-NO-DEVICE-FATAL-01: a tentativa inicial de conexão deixou
        de ser bloqueante. Subsystems (IPC, UDP, autoswitch, hotkey, plugins)
        sobem ANTES do `reconnect_loop`, garantindo que o socket IPC exista
        em ≤5s mesmo sem hardware plugado. Plug do controle posterior é
        detectado pelo probe e dispara `restore_last_profile` uma única vez.
        """
        from hefesto_dualsense4unix.daemon.connection import (
            reconnect_loop,
            shutdown,
        )
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            start_mic_hotkey,
        )

        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        self._stop_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hefesto-hid")
        self._install_signal_handlers(loop)
        # FEAT-DAEMON-PAUSE-RESUME-01: retoma pausado se a sessão anterior
        # terminou pausada (o poll loop nasce respeitando _paused).
        from hefesto_dualsense4unix.utils.session import load_paused_state
        self._paused = load_paused_state()
        # FEAT-MOUSE-PERSIST-01: restaura a emulação de mouse se a sessão anterior
        # a deixou ligada — antes o toggle voltava ao default (off) a cada restart
        # do daemon (reboot, takeover, reload). Só liga; nunca força off.
        from hefesto_dualsense4unix.utils.session import load_mouse_emulation_enabled
        if load_mouse_emulation_enabled():
            self.config.mouse_emulation_enabled = True
        # FEAT-DSX-GAMEPAD-FLAVOR-01: restaura o gamepad virtual (liga + flavor)
        # se a sessão anterior o deixou ligado. Mútua exclusão: o gamepad tem
        # precedência sobre o mouse (jogar = controle vai pro jogo).
        from hefesto_dualsense4unix.utils.session import load_gamepad_emulation
        gp_enabled, gp_flavor = load_gamepad_emulation()
        if gp_enabled:
            self.config.gamepad_emulation_enabled = True
            if gp_flavor:
                self.config.gamepad_flavor = gp_flavor
            self.config.mouse_emulation_enabled = False
        # FEAT-DSX-COOP-LOCAL-01: restaura o co-op local se a sessão anterior o
        # deixou ligado (só tem efeito com gamepad + 2+ controles; o poll loop
        # reconcilia via CoopManager.sync).
        from hefesto_dualsense4unix.utils.session import load_coop_enabled
        if load_coop_enabled():
            self.config.coop_enabled = True
        logger.info("daemon_starting", poll_hz=self.config.poll_hz, paused=self._paused)
        try:
            self._tasks = [asyncio.create_task(self._poll_loop(), name="poll_loop")]
            # FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01: cada subsystem sobe isolado —
            # uma falha é registrada em _failed_subsystems e o boot segue
            # (poll/IPC/perfis sobrevivem a um subsystem quebrado).
            if self.config.ipc_enabled:
                await self._safe_start("ipc", self._start_ipc)
            if self.config.udp_enabled:
                await self._safe_start("udp", self._start_udp)
            if self.config.autoswitch_enabled:
                await self._safe_start("autoswitch", self._start_autoswitch)
            if self.config.mouse_emulation_enabled:
                await self._safe_start("mouse", self._start_mouse_emulation)
            if self.config.gamepad_emulation_enabled:
                await self._safe_start("gamepad", self._start_gamepad_emulation)
            if self.config.keyboard_emulation_enabled:
                await self._safe_start("keyboard", self._start_keyboard_emulation)
            await self._safe_start("hotkey", lambda: start_hotkey_manager(self))
            if self.config.mic_button_toggles_system:
                await self._safe_start("mic_hotkey", lambda: start_mic_hotkey(self))
            await self._safe_start("plugins", self._start_plugins)
            # FEAT-CONFIG-AUDIT-BOOT-01: valida os perfis no boot e avisa se houver
            # corrompidos (em vez de só pulá-los silenciosamente no fallback).
            self._audit_config_on_boot()
            # FEAT-SYSTEM-AUTOREPAIR-BOOT-01: detecta infra quebrada (udev/WirePlumber)
            # e AVISA o comando de reparo — nunca roda sudo sozinho.
            self._check_system_on_boot()
            # BUG-DAEMON-NO-DEVICE-FATAL-01: tentativa inicial best-effort.
            # No caminho real, se o controle estiver ausente, o backend
            # PyDualSenseController.connect() trata "No device detected" em
            # silencio (offline-OK). Outros erros (permissão hidraw, USB
            # transitório) sao logados aqui e o reconnect_loop reassume em
            # background. No caminho FAKE, conecta imediatamente.
            try:
                await self._run_blocking(self.controller.connect)
                if self.controller.is_connected():
                    transport = self.controller.get_transport()
                    self.bus.publish(
                        EventTopic.CONTROLLER_CONNECTED, {"transport": transport}
                    )
                    logger.info("controller_connected", transport=transport)
                    # FEAT-COSMIC-NOTIFICATIONS-01: opt-in via env var.
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.integrations.desktop_notifications import (
                            notify_controller_connected,
                        )
                        notify_controller_connected(transport or "usb")
                    from hefesto_dualsense4unix.daemon.connection import (
                        restore_last_profile,
                    )

                    with contextlib.suppress(Exception):
                        await restore_last_profile(self)
            except Exception as exc:
                logger.warning(
                    "controller_initial_connect_failed",
                    err=str(exc),
                    exc_info=True,
                )
            # Reconnect probe em background — não bloqueia o boot e cobre
            # transicoes onlineoffline em runtime.
            self._reconnect_task = asyncio.create_task(
                reconnect_loop(self), name="reconnect_loop"
            )
            self._tasks.append(self._reconnect_task)
            await self._stop_event.wait()
        finally:
            await shutdown(self)

    def stop(self) -> None:
        """Sinaliza parada; idempotente."""
        if self._stop_event is not None and not self._stop_event.is_set():
            logger.info("daemon_stop_requested")
            self._stop_event.set()

    def pause(self) -> None:
        """Pausa o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01).

        O daemon segue vivo: lê estado/bateria, publica STATE_UPDATE e atende o
        IPC, mas para de despachar gatilhos/teclado/mouse/hotkey e de publicar
        BUTTON_DOWN/UP. Idempotente; persiste para retomar pausado após restart.
        """
        if not self._paused:
            self._paused = True
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(True)
            logger.info("daemon_paused")

    def resume(self) -> None:
        """Retoma o despacho de input. Idempotente.

        O baseline de botões ficou sincronizado durante a pausa (o poll loop
        seguiu primando o edge-tracker e atualizando previous_buttons), então
        botões segurados ao retomar não disparam — só após soltar e
        re-pressionar (mesma garantia do fim do grace-period).
        """
        if self._paused:
            self._paused = False
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(False)
            logger.info("daemon_resumed")

    def is_paused(self) -> bool:
        """True se o despacho de input está pausado."""
        return self._paused

    def reload_config(self, new_config: DaemonConfig) -> None:
        """Aplica nova configuração em runtime sem reiniciar o daemon."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            stop_hotkey_manager,
        )

        old = self.config
        self.config = new_config
        stop_hotkey_manager(self)
        start_hotkey_manager(self)
        if old.mouse_emulation_enabled != new_config.mouse_emulation_enabled:
            self.set_mouse_emulation(
                new_config.mouse_emulation_enabled,
                speed=new_config.mouse_speed,
                scroll_speed=new_config.mouse_scroll_speed,
            )
        if old.keyboard_emulation_enabled != new_config.keyboard_emulation_enabled:
            if new_config.keyboard_emulation_enabled:
                self._start_keyboard_emulation()
            else:
                self._stop_keyboard_emulation()
        keys_changed = [
            k for k in new_config.__dataclass_fields__
            if getattr(old, k, None) != getattr(new_config, k)
        ]
        logger.info("daemon_config_reloaded", keys_changed=keys_changed)

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Liga/desliga emulação de mouse e atualiza velocidades. Usado pelo IPC."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import (
            start_mouse_emulation,
            stop_mouse_emulation,
        )

        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))
        if enabled:
            # FEAT-DSX-GAMEPAD-FLAVOR-01: mútua exclusão — ligar o mouse desliga
            # o gamepad virtual (e libera o grab do controle).
            if self._gamepad_device is not None:
                self._stop_gamepad_emulation()
            ok = start_mouse_emulation(self)
            if ok and self._mouse_device is not None:
                self._mouse_device.set_speed(
                    mouse_speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed,
                )
            return ok
        stop_mouse_emulation(self)
        return True

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None
    ) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara. Usado pelo IPC.

        FEAT-DSX-GAMEPAD-FLAVOR-01. `flavor` em ('dualsense','xbox'); None mantém
        o atual. Ligar desliga a emulação de mouse (mútua exclusão). Retorna True
        se o estado pedido foi alcançado.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            start_gamepad_emulation,
            stop_gamepad_emulation,
        )

        if enabled:
            return start_gamepad_emulation(self, flavor=flavor)
        stop_gamepad_emulation(self)
        return True

    def set_coop_enabled(self, enabled: bool) -> bool:
        """Liga/desliga o co-op local (FEAT-DSX-COOP-LOCAL-01). Usado pelo IPC.

        Persiste o toggle (sobrevive reboot) e reconcilia na hora: ligar sobe os
        jogadores secundários (se gamepad on + 2+ controles); desligar desmonta
        todos (solta grab/uinput). Retorna o estado efetivo de `coop_enabled`.
        """
        self.config.coop_enabled = bool(enabled)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_coop_enabled

            save_coop_enabled(self.config.coop_enabled)
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self)
        if self.config.coop_enabled:
            coop.sync()
        else:
            coop.disable()
        logger.info(
            "coop_enabled_set",
            enabled=self.config.coop_enabled,
            players=coop.player_count(),
        )
        return self.config.coop_enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        """Liga/desliga a supressão da emulação de mouse/teclado (modo jogo).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. `value=None` faz toggle; caso
        contrário, define explicitamente. Os devices uinput permanecem vivos —
        só o despacho no poll loop é pulado, e os hotkeys continuam ativos.
        Notifica o usuário e retorna o novo estado (True = emulação suprimida).
        """
        from hefesto_dualsense4unix.integrations.desktop_notifications import (
            notify_emulation_suppressed,
        )

        new_state = (not self._emulation_suppressed) if value is None else bool(value)
        self._emulation_suppressed = new_state
        if new_state:
            # FEAT-EMULATION-GAMEMODE-FLUSH-01: ao suprimir, solta tudo que estiver
            # pressionado nos devices virtuais — senão um modificador (ex.: Meta de
            # 'options' no PS+Options) fica preso, já que o poll loop para de
            # despachar e nunca envia o release.
            self._flush_emulation_devices()
        logger.info("emulation_suppressed_changed", suppressed=new_state)
        notify_emulation_suppressed(new_state)
        return new_state

    def _flush_emulation_devices(self) -> None:
        """Solta todas as teclas/botões dos devices virtuais (mouse+teclado).

        Idempotente e best-effort. Usado ao ligar a supressão (modo jogo) para
        não deixar modificador/click preso, e disponível p/ limpeza defensiva.
        """
        kbd = self._keyboard_device
        if kbd is not None:
            with contextlib.suppress(Exception):
                kbd.dispatch(frozenset())
        mouse = self._mouse_device
        if mouse is not None:
            with contextlib.suppress(Exception):
                mouse.dispatch(
                    lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset()
                )

    # ------------------------------------------------------------------
    # Métodos privados preservados para backcompat de testes
    # ------------------------------------------------------------------

    def _start_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat para testes que chamam daemon._start_hotkey_manager()."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_hotkey_manager

        start_hotkey_manager(self)

    def _stop_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import stop_hotkey_manager

        stop_hotkey_manager(self)

    def _start_mouse_emulation(self) -> bool:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import start_mouse_emulation

        return start_mouse_emulation(self)

    def _stop_mouse_emulation(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(self)

    def _start_gamepad_emulation(self) -> bool:
        """Thin wrapper — gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import start_gamepad_emulation

        return start_gamepad_emulation(self, flavor=self.config.gamepad_flavor)

    def _stop_gamepad_emulation(self) -> None:
        """Thin wrapper — para o gamepad virtual e libera o grab."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import stop_gamepad_emulation

        stop_gamepad_emulation(self)

    def _dispatch_gamepad_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import dispatch_gamepad

        dispatch_gamepad(self, state, buttons_pressed)

    def _start_keyboard_emulation(self) -> bool:
        """Thin wrapper — wire-up A-07 para FEAT-KEYBOARD-EMULATOR-01."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import start_keyboard_emulation

        return start_keyboard_emulation(self)

    def _stop_keyboard_emulation(self) -> None:
        """Thin wrapper — backcompat e cleanup."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import stop_keyboard_emulation

        stop_keyboard_emulation(self)

    def _dispatch_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import dispatch_keyboard

        dispatch_keyboard(self, buttons_pressed)

    def _prime_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — semeia o edge-tracker do teclado sem emitir.

        Chamado pelo poll loop durante o settling pós-conexão
        (BUG-DAEMON-CONNECT-GHOST-INPUT-01).
        """
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import prime_keyboard

        prime_keyboard(self, buttons_pressed)

    def _reassert_rumble(self, now: float) -> None:
        """Thin wrapper — backcompat e chamado pelo poll loop."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import reassert_rumble

        reassert_rumble(self, now)

    async def _start_ipc(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.ipc import start_ipc

        await start_ipc(self)

    async def _start_udp(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.udp import start_udp

        await start_udp(self)

    async def _start_autoswitch(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import start_autoswitch

        await start_autoswitch(self)

    def _start_mic_hotkey(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_mic_hotkey

        start_mic_hotkey(self)

    async def _start_plugins(self) -> None:
        """Inicializa o PluginsSubsystem se plugins_enabled ou env var ativo."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem

        ps = PluginsSubsystem()
        if not ps.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ps.start(ctx)
        self._plugins_subsystem = ps

    async def _stop_plugins(self) -> None:
        """Para o PluginsSubsystem de forma limpa."""
        if self._plugins_subsystem is not None:
            await self._plugins_subsystem.stop()
            self._plugins_subsystem = None

    async def _safe_start(self, name: str, starter: Callable[[], Any]) -> None:
        """Inicia um subsystem isolando falhas (FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01).

        Se `starter` levantar (dep nativa ausente, permissão negada, porta em
        uso...), registra o erro em `_failed_subsystems` e segue — um subsystem
        quebrado não derruba o daemon. Aceita starters síncronos e assíncronos.
        """
        try:
            result = starter()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self._failed_subsystems[name] = str(exc)
            logger.error(
                "subsystem_start_failed", subsystem=name, err=str(exc), exc_info=True
            )

    def _audit_config_on_boot(self) -> None:
        """Valida os perfis no boot e avisa o usuário se houver corrompidos
        (FEAT-CONFIG-AUDIT-BOOT-01). Best-effort: nunca derruba o boot.
        """
        try:
            from hefesto_dualsense4unix.profiles.loader import audit_profiles

            invalid = audit_profiles()
            if not invalid:
                return
            logger.warning(
                "config_audit_invalid_profiles",
                count=len(invalid),
                profiles=[name for name, _err in invalid],
            )
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_config_errors,
                )

                notify_config_errors(invalid)
        except Exception as exc:
            logger.debug("config_audit_failed", err=str(exc))

    def _check_system_on_boot(self) -> None:
        """Detecta problemas de infra no boot (udev/WirePlumber) e AVISA o comando
        de reparo (FEAT-SYSTEM-AUTOREPAIR-BOOT-01). Nunca roda sudo/reparo sozinho.
        Best-effort: nunca derruba o boot.

        BUG-SYSTEM-CHECK-BOOT-SPAM-01: a notificação visual é silenciada por
        default (`HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY=0`). O usuário
        reclamava de receber aviso "tem algo não instalado" toda vez que ligava
        o PC (WirePlumber pinava o DualSense como mic padrão — coisa que ele
        já sabia, mas não queria ser lembrado a cada login). O log em `warning`
        permanece — quem quiser pode rodar `journalctl --user -u
        hefesto-dualsense4unix.service | grep system_check_warning` para ver.
        Para reativar a notify, setar a env var para "1".
        """
        try:
            from hefesto_dualsense4unix.core.system_check import system_warnings

            infra_warnings = system_warnings()
            if not infra_warnings:
                return
            for detail in infra_warnings:
                logger.warning("system_check_warning", detail=detail)
            notify_enabled = os.environ.get(
                "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY", ""
            ).strip() in ("1", "true", "yes")
            if not notify_enabled:
                return
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_system_warnings,
                )

                notify_system_warnings(infra_warnings)
        except Exception as exc:
            logger.debug("system_check_failed", err=str(exc))

    def _evdev_buttons_once(self) -> frozenset[str]:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once

        return evdev_buttons_once(self)

    def _dispatch_mouse_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import dispatch_mouse

        dispatch_mouse(self, state, buttons_pressed)

    # ------------------------------------------------------------------
    # Poll loop (permanece aqui: testes fazem monkeypatch de daemon._poll_loop)
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        period = 1.0 / max(1, self.config.poll_hz)
        battery = BatteryDebouncer()
        loop = asyncio.get_running_loop()
        next_rumble_assert_at: float = 0.0
        evdev_watchdog_next_at: float = 0.0
        # FEAT-DSX-COOP-LOCAL-01: reconcilia os jogadores secundários (P2+) a cada
        # ~2s (enumerar evdevs todo tick é caro); o forward roda todo tick.
        coop_sync_next_at: float = 0.0
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager
        previous_buttons: frozenset[str] = frozenset()
        # BUG-DAEMON-CONNECT-GHOST-INPUT-01: rastreia a borda
        # desconectado→conectado. Começa False (boot pode ser sem hardware);
        # vira True na 1ª leitura bem-sucedida, quando armamos o grace.
        was_connected = False

        while not self._is_stopping():
            tick_started = loop.time()
            # BUG-DAEMON-NO-DEVICE-FATAL-01: se o controller ainda não está
            # conectado (boot sem hardware ou pós-unplug), pula o tick
            # silenciosamente. O `reconnect_loop` cuida de retentar; quando
            # conectar, o tick seguinte volta a ler estado normalmente.
            if not self.controller.is_connected():
                # BUG-DAEMON-CONNECT-GHOST-INPUT-01: desconexão detectada via
                # is_connected() (probe/unplug). Zera o baseline e rearma a
                # borda para que a próxima conexão refaça o settling.
                was_connected = False
                previous_buttons = frozenset()
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=period)
                    break
                continue
            try:
                state = await self._run_blocking(self.controller.read_state)
            except Exception as exc:
                logger.warning("poll_read_failed", err=str(exc), exc_info=True)
                self.bus.publish(EventTopic.CONTROLLER_DISCONNECTED, {"reason": str(exc)})
                if self.config.auto_reconnect:
                    from hefesto_dualsense4unix.daemon.connection import reconnect

                    previous_buttons = frozenset()
                    was_connected = False
                    await reconnect(self)
                    continue
                break

            # BUG-DAEMON-CONNECT-GHOST-INPUT-01: borda desconectado→conectado.
            # Esta é a 1ª leitura após (re)conectar. Arma o grace-period: até
            # `_input_ready_at`, todo input emulado fica suprimido (ver gate
            # `input_ready` abaixo). O baseline de `previous_buttons` e do
            # edge-tracker do teclado é semeado a cada tick do grace (abaixo),
            # cobrindo o HID-raw cru (ex.: micBtn) e o snapshot evdev ainda
            # populando.
            if not was_connected:
                self._input_ready_at = tick_started + INPUT_GRACE_SEC
                was_connected = True
                logger.info(
                    "input_settling_started",
                    grace_sec=INPUT_GRACE_SEC,
                    transport=state.transport,
                )

            self.store.update_controller_state(state)
            # CLUSTER-IPC-STATE-PROFILE-01 (Bug A): publica o último state
            # no slot `_last_state` para `daemon.state_full` consumir
            # (em paralelo ao store, que mantém snapshot consolidado).
            self._last_state = state
            self.bus.publish(EventTopic.STATE_UPDATE, state)
            self.store.bump("poll.tick")

            if tick_started >= next_rumble_assert_at:
                self._reassert_rumble(tick_started)
                next_rumble_assert_at = tick_started + 0.200

            # FEAT-DSX-EVDEV-WATCHDOG-01: cross-check HID x evdev. Chegamos aqui só
            # com o HID conectado (gate acima) e lendo estado — se o evdev reader
            # ficou preso num node OBSOLETO (re-enumeração pós storm -71 / replug
            # rápido) sem receber ENODEV, o read_loop zumbi não levanta erro e o
            # controle fica "morto" sem sinal. Forçamos reabrir. IDLE-SAFE: só
            # dispara por TROCA real de node, nunca por ociosidade. Throttle p/
            # não escanear /dev/input todo tick; offload via _run_blocking.
            if tick_started >= evdev_watchdog_next_at:
                evdev_watchdog_next_at = tick_started + EVDEV_WATCHDOG_SEC
                heal = getattr(self.controller, "heal_evdev_if_stale", None)
                if heal is not None:
                    with contextlib.suppress(Exception):
                        if await self._run_blocking(heal):
                            self.store.bump("evdev.watchdog.reopen")

            buttons_pressed = self._evdev_buttons_once()
            current_buttons = state.buttons_pressed

            # FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01: o forward pro gamepad virtual é a
            # ROTA do controle pro JOGO — precisa sobreviver TANTO ao 'pause'
            # (daemon.pause) QUANTO ao 'modo jogo' (_emulation_suppressed). Antes
            # o dispatch do gamepad morava DENTRO dos dois gates de emulação de
            # DESKTOP: o `continue` do gate de pausa (abaixo) ocorria antes dele,
            # e ele ainda exigia `emu_active` (não-suprimido). Resultado: entrar
            # em modo jogo, pausar, ou renascer pausado no boot deixava o controle
            # MORTO no jogo — o controle físico fica EVIOCGRAB-grabado (gamepad =
            # fonte única) e o virtual parava de receber input = real escondido +
            # virtual mudo. Agora o gamepad é despachado AQUI, gateado SÓ pelo
            # grace-period (anti-ghost-input), com os botões CRUS: o jogo quer
            # PS/Options/dpad crus; a subtração de combo (abaixo) é proteção
            # contra vazamento pro DESKTOP e não se aplica ao gamepad.
            grace_passed = tick_started >= self._input_ready_at
            gamepad_dispatched = False
            if grace_passed and self._gamepad_device is not None:
                self._dispatch_gamepad_emulation(state, buttons_pressed)
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
                gamepad_dispatched = True

            # FEAT-DSX-COOP-LOCAL-01: co-op local — repassa cada controle
            # SECUNDÁRIO ao SEU gamepad virtual (P2+). Como o P1 acima, sobrevive
            # a pause/modo-jogo (é rota pro jogo) e é gateado só pelo grace. A
            # reconciliação (sync, throttada ~2s) cria/derruba os secundários e
            # também desmonta tudo se o co-op/gamepad for desligado.
            if grace_passed:
                coop = get_coop_manager(self)
                if tick_started >= coop_sync_next_at:
                    coop.sync()
                    coop_sync_next_at = tick_started + 2.0
                coop.forward_all()

            # BUG-DAEMON-CONNECT-GHOST-INPUT-01: gate de assentamento. Enquanto
            # `loop.time() < _input_ready_at`, NÃO despacha teclado/mouse/hotkey
            # nem publica BUTTON_DOWN/UP. Continua lendo estado, atualizando o
            # store e publicando STATE_UPDATE/bateria normalmente. Durante o
            # grace, mantemos `previous_buttons` sincronizado ao estado atual e
            # semeamos o edge-tracker do teclado SEM emitir, de modo que ao fim
            # do settling botões fantasma/segurados na conexão sejam o baseline
            # (só disparam quando soltos e re-pressionados).
            # FEAT-DAEMON-PAUSE-RESUME-01: além do grace, respeita _paused — mas
            # isso gateia mouse/teclado/hotkey/edges; o gamepad já foi despachado
            # acima e NÃO é congelado por pausa/supressão.
            input_ready = grace_passed and not self._paused
            if not input_ready:
                if self._keyboard_device is not None:
                    self._prime_keyboard_emulation(buttons_pressed)
                previous_buttons = current_buttons
                self.store.bump("input.settling.tick")
                if battery.should_emit(state.battery_pct, tick_started):
                    self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                    battery.mark_emitted(state.battery_pct, tick_started)
                    self.store.bump("battery.change.emitted")
                    if self._plugins_subsystem is not None:
                        self._plugins_subsystem.dispatch_battery_change(state.battery_pct)
                elapsed = loop.time() - tick_started
                sleep_for = period - elapsed
                if sleep_for > 0:
                    stop_event = self._stop_event
                    assert stop_event is not None
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                        break
                continue

            # FEAT-HOTKEY-COMBO-NO-LEAK-01: não despacha à emulação de DESKTOP os
            # botões de um combo de hotkey em formação (PS+Options, PS+dpad).
            # Senão 'options'→Meta (e dpad→setas) vazam pro desktop ao usar o
            # combo, e se a supressão ligar no mesmo tick o release nunca é
            # enviado → o modificador trava ("Control/Meta sempre segurado").
            emu_buttons = buttons_pressed
            if self._hotkey_manager is not None:
                blocked = self._hotkey_manager.combo_buttons_active(buttons_pressed)
                if blocked:
                    emu_buttons = buttons_pressed - blocked

            # Mouse/teclado de DESKTOP: gateados por emu_active (modo jogo) e só
            # quando o gamepad NÃO foi despachado (exclusão mútua — com o gamepad
            # ligado, o controle vai pro jogo, não pro cursor/teclado).
            emu_active = not self._emulation_suppressed
            if not gamepad_dispatched:
                if self._mouse_device is not None and emu_active:
                    self._dispatch_mouse_emulation(state, emu_buttons)
                elif self._touchpad_reader is not None:
                    # B4: emulação off/suprimida → descarta o movimento do
                    # touchpad acumulado, senão o cursor pula ao religar.
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)

                if self._keyboard_device is not None and emu_active:
                    self._dispatch_keyboard_emulation(emu_buttons)

            if self._hotkey_manager is not None:
                self._hotkey_manager.observe(buttons_pressed, now=tick_started)

            if self._plugins_subsystem is not None:
                active_profile = self.store.active_profile
                self._plugins_subsystem.tick(state, active_profile)

            pressed_now = current_buttons - previous_buttons
            released_now = previous_buttons - current_buttons
            for name in sorted(pressed_now):
                self.bus.publish(EventTopic.BUTTON_DOWN, {"button": name, "pressed": True})
                self.store.bump("button.down.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_button_down(name)
            for name in sorted(released_now):
                self.bus.publish(EventTopic.BUTTON_UP, {"button": name, "pressed": False})
                self.store.bump("button.up.emitted")
            previous_buttons = current_buttons

            if battery.should_emit(state.battery_pct, tick_started):
                self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                battery.mark_emitted(state.battery_pct, tick_started)
                self.store.bump("battery.change.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_battery_change(state.battery_pct)

            elapsed = loop.time() - tick_started
            sleep_for = period - elapsed
            if sleep_for > 0:
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                    break

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self.stop)

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        assert self._executor is not None, "executor não inicializado"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    def _arm_input_grace(self) -> None:
        """Rearma o período de assentamento pós-conexão (BUG-DAEMON-CONNECT-
        GHOST-INPUT-01).

        Usado por `connection.reconnect`/`reconnect_loop` na transição online
        para garantir que o input emulado fique suprimido por `INPUT_GRACE_SEC`
        mesmo quando o poll loop não chega a observar `is_connected() == False`
        entre o unplug e o replug (ex.: reconexão rápida via probe). Encapsula
        a constante e o relógio do event loop para não vazar aritmética de
        tempo para `connection.py`.

        Best-effort fora de um event loop (ex.: chamado em teardown): se não
        houver loop rodando, não há grace a armar.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._input_ready_at = loop.time() + INPUT_GRACE_SEC



__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "DEFAULT_POLL_HZ",
    "RUMBLE_POLICY_MULT",
    "BatteryDebouncer",
    "Daemon",
    "DaemonConfig",
]
