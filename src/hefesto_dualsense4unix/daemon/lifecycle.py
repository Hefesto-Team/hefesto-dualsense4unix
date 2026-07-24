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
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal, cast, get_args

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

#: HANG-01 (Sprint 2026-07-19): teto de espera do tick de LED dos externos
#: (`ExternalLedSync.tick`, executado no pool DEDICADO `hefesto-ext`, ver
#: `_external_executor`). Medido ao vivo (16:08:56, PID 2835): uma
#: "debandada" (mass-unplug) faz `discover_external_gamepads` abrir/fechar
#: TODOS os nodes de /dev/input em rajada, e um wedge de GIL do CPython sob
#: esse churn de threads pode nunca devolver o controle a Python — sem
#: timeout, o poll loop ficava suspenso PARA SEMPRE em
#: `await self._run_blocking(sync.tick)` (zero read_state, zero logs, zero
#: watchdog). A THREAD presa NÃO é recuperável (é um wedge de baixo nível, não
#: uma trava lógica nossa) — o trade-off aceito é vazar o(s) worker(s) do
#: pool `hefesto-ext`.
#: CORREÇÃO PÓS-AUDITORIA (20/07): a 1ª versão deste fix rodava `sync.tick`
#: no MESMO `self._executor` ("hefesto-hid", 2 workers) do qual `read_state`
#: (SEM wait_for), `_gather_game_signal_inputs` e o watchdog evdev também
#: dependem — 2 timeouts consecutivos (o guard de reentrância permite um 2º
#: agendamento porque a task asyncio já retorna "done" ao capturar o
#: TimeoutError, mesmo com a thread ainda presa) vazavam os 2 workers do
#: MESMO pool que o poll loop usa pra ler o controle — reproduzindo o hang
#: original, só que adiado por ~2x este timeout em vez de instantâneo. Agora
#: `sync.tick` roda em `self._external_executor`, um pool PRÓPRIO e ISOLADO —
#: o pior caso vaza só ali, nunca no pool de que `read_state` depende. 10s é
#: folgado para uma enumeração normal (10-40ms) e curto o bastante para o
#: daemon nunca parecer morto por mais que isso.
EXTERNAL_TICK_TIMEOUT_SEC: float = 10.0

#: HANG-01: timeouts CONSECUTIVOS do tick de externos a partir dos quais o
#: daemon PARA de agendar `discover` (inventário congela; `external_led` para
#: de atualizar) até o próximo `input_dir_change` do `InputDirWatch` — evita
#: empilhar uma task nova a cada ~2s em cima de um pool cujo(s) worker(s) já
#: podem estar presos (dobrar/triplicar o vazamento em vez de conter em 1).
EXTERNAL_TICK_MAX_TIMEOUTS: int = 2


# ---------------------------------------------------------------------------
# DaemonConfig
# ---------------------------------------------------------------------------

#: FEAT-RUMBLE-POLICY-PROFILE-01: políticas válidas de intensidade de rumble.
#: Fonte única para `DaemonConfig.rumble_policy` e para a validação defensiva
#: em `Daemon.apply_profile_rumble_policy` (o schema de perfil replica o
#: Literal para não importar o daemon — sem ciclo de import).
RumblePolicy = Literal["economia", "balanceado", "max", "auto", "custom"]
RUMBLE_POLICIES: tuple[str, ...] = get_args(RumblePolicy)


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
    # HARMONIA-MASK-01 (22/07, decisão da mantenedora): default dualsense — o
    # vpad é DualSense Edge por arquitetura (UHID-04) e a máscara dualsense
    # foi validada em jogo real (Sackboy/Mad King/Pragmata). Este default só
    # governa instalação nova/flag ausente: `gamepad_emulation.flag` persiste
    # a escolha da usuária e vence sempre (load_gamepad_emulation, abaixo).
    # (Histórico: era "xbox" desde SPRINT-GAME-RUMBLE-01, de antes da máscara
    # dualsense vibrar — superado pela validação da Onda Harmonia.)
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
    rumble_policy: RumblePolicy = "balanceado"
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
    # HANG-01 (correção pós-auditoria 20/07): pool DEDICADO e ISOLADO do tick
    # de LED dos externos (`ExternalLedSync.tick`, via `_sync_external_leds`)
    # — nunca compartilhado com `_executor`. Um wedge de GIL travando a única
    # thread deste pool não pode mais esgotar o pool de que `read_state`/
    # `_gather_game_signal_inputs`/o watchdog evdev dependem (ver comentário
    # de `EXTERNAL_TICK_TIMEOUT_SEC`).
    _external_executor: ThreadPoolExecutor | None = None
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _ipc_server: Any = None
    _udp_server: Any = None
    _autoswitch: Any = None
    _mouse_device: Any = None
    _keyboard_device: Any = None
    # FEAT-DSX-GAMEPAD-FLAVOR-01 — UinputGamepad criado em runtime por
    # start_gamepad_emulation; None quando o gamepad virtual está desligado.
    _gamepad_device: Any = None
    # GYRO-01 — PhysicalReportReader do vpad do P1 (espelho de motion: hidraw
    # do físico → forward_motion). Criado/parado por start/stop_motion_reader
    # junto do vpad uhid; None com a emulação desligada ou no fallback uinput.
    _motion_reader: Any = None
    # BROKER-01 — lease-cliente do broker root hide-hidraw
    # (`integrations.hidraw_broker_client.HidrawBrokerClient`). Criado sob
    # demanda por `broker_client_for` (lazy, lock de módulo); a conexão É a
    # lease (EOF restaura tudo). None até o 1º hide/open; o shutdown fecha e
    # zera explicitamente.
    _hidraw_broker_client: Any = None
    # Achados Onda S #5/#6/#10 — executor DEDICADO (1 worker, FIFO) das
    # operações hide/restore do broker (`broker_call_nonblocking`): I/O de
    # socket com timeout de 2 s jamais roda na thread do event loop. Lazy
    # (criado no 1º uso a partir do loop); o shutdown o desliga com
    # `cancel_futures=True` antes de fechar a lease.
    _hidraw_broker_executor: Any = None
    # FEAT-DSX-COOP-LOCAL-01 — CoopManager: jogadores secundários (P2+) do co-op
    # local. Criado sob demanda por `get_coop_manager`; None até o 1º uso.
    _coop_manager: Any = None
    _hotkey_manager: Any = None
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: quando True, o poll loop não despacha
    # mouse/teclado (devices ficam vivos; hotkeys seguem ativos). Alternado pelo
    # long-press do PS. Transitório — não persiste entre boots.
    _emulation_suppressed: bool = False
    # FEAT-POINT-AND-CLICK-01: instante (time.monotonic) do último toggle MANUAL
    # do modo-jogo (hotkey PS+Options, IPC `daemon.emulation.suppress`, GUI).
    # -inf = nunca houve toggle manual (boot). Consultado por
    # `apply_profile_suppression`: perfil não mexe na supressão dentro da
    # janela de MANUAL_PROFILE_LOCK_SEC após um gesto manual.
    _suppress_manual_ts: float = field(default=float("-inf"))
    # FEAT-POINT-AND-CLICK-01: True quando a supressão ATUAL foi ligada (ou
    # adotada) por um perfil com suppress_desktop_emulation=True. Perfis sem o
    # campo só LIBERAM a supressão quando este flag é True — toggle manual da
    # usuária nunca é revertido por autoswitch/troca de perfil.
    _suppress_from_profile: bool = False
    # BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: instante (time.monotonic) do último
    # toggle MANUAL da EMULAÇÃO (mouse ou gamepad via IPC/GUI/CLI/hotkey). -inf =
    # nunca. Consultado por `apply_profile_mouse`: um perfil não liga/desliga a
    # emulação dentro de MANUAL_PROFILE_LOCK_SEC após um gesto manual — não
    # sequestra um gamepad virtual ligado na mão no meio do jogo.
    _emu_manual_ts: float = field(default=float("-inf"))
    # FEAT-NATIVE-MODE-01: Modo Nativo ativo ("release total" do controle). Não
    # persiste no dataclass — é restaurado do flag no boot. O poll loop gateia o
    # dispatch por este flag (independente de pause/resume).
    _native_mode: bool = False
    # Estado de emulação (mouse/gamepad) capturado ANTES do Modo Nativo, para
    # restaurar ao desligar (o release apaga os flags próprios).
    _native_emu_stash: dict[str, Any] = field(default_factory=dict)
    # FEAT-PROFILE-MODE-01: qual MODO o perfil ativo ligou ("native"|"gamepad"|
    # None). Perfis sem seção `mode` só revertem modo cuja origem foi PERFIL —
    # gesto manual da usuária nunca é derrubado por autoswitch (mesma semântica
    # do `_suppress_from_profile`).
    _mode_from_profile: str | None = None
    # FEAT-RUMBLE-POLICY-PROFILE-01: True quando a política de rumble VIGENTE
    # foi aplicada por um perfil (`apply_profile_rumble_policy`). Perfis sem
    # opinião (rumble.policy=None) só revertem política cuja origem foi
    # PERFIL — gesto manual da usuária (IPC rumble.policy_set/policy_custom)
    # nunca é derrubado por autoswitch (paridade com `_mode_from_profile`).
    _rumble_policy_from_profile: bool = False
    # Política global vigente ANTES de o 1º perfil-com-opinião mexer, como
    # par (policy, custom_mult) — é para ela que um perfil sem opinião
    # reverte. None = nenhum perfil mexeu na política.
    _rumble_policy_before_profile: tuple[RumblePolicy, float] | None = None
    # BUG-EMU-DEVICE-RACE-01: serializa as transições de device de emulação
    # (start/stop de mouse e gamepad virtuais). A wave passou a chamar
    # set_mouse_emulation também da thread do executor (hotkey de ciclo via
    # _run_blocking(activate)), concorrendo com a thread do event loop (IPC/
    # autoswitch); o check-then-act sem lock em start_mouse_emulation podia criar
    # 2 devices uinput e vazar 1. RLock (reentrante: set_mouse_emulation chama
    # _stop_gamepad_emulation na mesma thread).
    _emu_lock: Any = field(default_factory=threading.RLock)
    _audio: Any = None
    _plugins_subsystem: Any = None
    # FEAT-METRICS-01: MetricsSubsystem (servidor HTTP Prometheus) ou None.
    # Instanciado por `_start_metrics` quando metrics_enabled; None até o 1º uso.
    _metrics_subsystem: Any = None
    # BUG-DAEMON-NO-DEVICE-FATAL-01 — task de probe de conexão em background
    # (substitui connect_with_retry bloqueante no boot). Cancelada em shutdown.
    _reconnect_task: asyncio.Task[Any] | None = None
    _last_auto_mult: float = field(default=0.7)
    _last_auto_change_at: float = field(default=0.0)
    # VPAD-01/VPAD-02: instante (time.monotonic) da última tentativa de trocar
    # o backend do vpad do P1 (uinput→uhid); -inf = nunca tentou. O cooldown
    # (`gamepad.REBACKEND_COOLDOWN_SEC`) é UM SÓ para a promoção do hotplug
    # (reconnect_loop) e a re-seleção pela GUI: o precheck `uhid_available()`
    # não pega o uhid que aceita o CREATE2 mas nunca faz bind (kernel sem
    # hid_playstation) — sem a trava, cada borda derrubaria e recriaria o vpad
    # uinput que funciona (input drop em loop no meio do jogo).
    _last_rebackend_ts: float = field(default=float("-inf"))
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
    # COR-01/COR-03: registro de identidade MAC→slot de sessão ("Controle N"
    # estável + cor automática por controle). Fiado em `run()` SÓ quando o
    # backend suporta o provider (`set_auto_output_provider`) — com o
    # FakeController fica None e nada de controllers.json é lido/escrito
    # (testes herméticos). O reconcile roda no tick lento do poll loop.
    identity_registry: Any = None
    # EXT-04: registro de identidade dos controles EXTERNOS (uniq→slot global
    # de co-op, namespace `externals` do controllers.json) + aplicador de LED
    # do tick lento. Fiados JUNTO com o identity_registry (backend real) —
    # com o FakeController ficam None: nenhuma enumeração de /dev/input nem
    # escrita de LED em teste/smoke (hermeticidade por construção).
    external_registry: Any = None
    _external_led_sync: Any = None
    # HANG-01: task auxiliar do tick de LED dos externos — `_sync_external_
    # leds` deixou de ser aguardado inline pelo poll loop (ver `_schedule_
    # external_tick`). None = nenhum tick em voo agora.
    _external_tick_task: asyncio.Task[Any] | None = None
    # HANG-01: timeouts CONSECUTIVOS do tick (zerado por um tick que termina
    # dentro do prazo). >= EXTERNAL_TICK_MAX_TIMEOUTS degrada.
    _external_tick_timeouts: int = 0
    # HANG-01: True após degradar (2+ timeouts seguidos) — o poll loop para
    # de chamar `_schedule_external_tick` até o `InputDirWatch` observar
    # mudança real em /dev/input (replug: o inventário pode ter mudado).
    _external_tick_degraded: bool = False
    # HANG-01: ciclos do poll loop que PULARAM o agendamento porque o tick
    # anterior ainda não tinha terminado (guard de reentrância) — só
    # observabilidade, nunca lido por lógica de gate.
    _external_tick_skipped: int = 0
    # HANG-01: watch barato de /dev/input (mesma classe do EVDEV_WATCHDOG)
    # usado só para destravar a degradação; criado sob demanda.
    _external_tick_watch: Any = None
    # NUMA-01: casca do sinal "jogo real ativo" (`game`|`daemon`|`unknown`) —
    # ao contrário de identity/external_registry, SEMPRE nasce (mesmo com
    # FakeController): é ela quem sustenta o contrato público
    # `display_authority`. Só a INJEÇÃO no backend (`set_game_authority_
    # provider`) é gateada por `hasattr` — sem o método, o backend fica
    # byte-idêntico ao HEAD (fail-safe da síntese da Onda N).
    _game_signal: Any = None

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
        # HANG-01: pool próprio p/ o tick de externos — NUNCA o mesmo de cima
        # (ver comentário de `_external_executor` e `EXTERNAL_TICK_TIMEOUT_
        # SEC`; 1 worker basta, o guard de reentrância nunca deixa 2 ticks
        # concorrentes de verdade).
        self._external_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="hefesto-ext"
        )
        self._install_signal_handlers(loop)
        # FEAT-DAEMON-PAUSE-RESUME-01: retoma pausado se a sessão anterior
        # terminou pausada (o poll loop nasce respeitando _paused).
        from hefesto_dualsense4unix.utils.session import load_paused_state
        self._paused = load_paused_state()
        # FEAT-NATIVE-MODE-01: se a sessão anterior terminou em Modo Nativo, sobe
        # SOLTO — o controle fica com o jogo. Implica pausado e NÃO restaura
        # emulação nem re-aplica perfil (os `not self._native_mode` abaixo e o
        # gate em `restore_last_profile`).
        from hefesto_dualsense4unix.utils.session import load_native_mode
        self._native_mode, self._native_emu_stash = load_native_mode()
        if self._native_mode:
            # O gate de dispatch é o próprio _native_mode (consultado no poll
            # loop); não força _paused (evita conflatar com o pause manual).
            self.store.set_native_mode_active(True)
        # FEAT-MOUSE-PERSIST-01: restaura a emulação de mouse se a sessão anterior
        # a deixou ligada — antes o toggle voltava ao default (off) a cada restart
        # do daemon (reboot, takeover, reload). Só liga; nunca força off.
        # FEAT-MOUSE-CURSOR-FEEL-01 (A5): restaura também speed/scroll do flag
        # JSON, com clamp ao contrato (1-12 / 1-5); flag legado sem velocidades
        # (`"1\n"`) mantém os defaults da config.
        from hefesto_dualsense4unix.utils.session import load_mouse_emulation
        mouse_on, mouse_speed, mouse_scroll = load_mouse_emulation()
        if mouse_on and not self._native_mode:
            self.config.mouse_emulation_enabled = True
            if mouse_speed is not None:
                self.config.mouse_speed = max(1, min(12, int(mouse_speed)))
            if mouse_scroll is not None:
                self.config.mouse_scroll_speed = max(1, min(5, int(mouse_scroll)))
        # FEAT-DSX-GAMEPAD-FLAVOR-01: restaura o gamepad virtual (liga + flavor)
        # se a sessão anterior o deixou ligado. Mútua exclusão: o gamepad tem
        # precedência sobre o mouse (jogar = controle vai pro jogo).
        from hefesto_dualsense4unix.utils.session import load_gamepad_emulation
        gp_enabled, gp_flavor = load_gamepad_emulation()
        if gp_enabled and not self._native_mode:
            self.config.gamepad_emulation_enabled = True
            if gp_flavor:
                self.config.gamepad_flavor = gp_flavor
            self.config.mouse_emulation_enabled = False
        # FEAT-DSX-COOP-LOCAL-01: restaura o co-op local se a sessão anterior o
        # deixou ligado (só tem efeito com gamepad + 2+ controles; o poll loop
        # reconcilia via CoopManager.sync).
        # LEIGO-01: a migração vem ANTES da leitura — o checkbox saiu da UI, e o
        # opt-out gravado por uma versão antiga deixaria o co-op desligado sem
        # nenhum caminho de volta na interface.
        from hefesto_dualsense4unix.utils.session import (
            load_coop_enabled,
            migrate_coop_optout,
        )
        migrate_coop_optout()
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
            # FEAT-METRICS-01: sobe o servidor de métricas Prometheus (gate
            # interno respeita metrics_enabled). Antes nunca era iniciado —
            # metrics_enabled/metrics_port eram config morta.
            await self._safe_start("metrics", self._start_metrics)
            # FEAT-CONFIG-AUDIT-BOOT-01: valida os perfis no boot e avisa se houver
            # corrompidos (em vez de só pulá-los silenciosamente no fallback).
            self._audit_config_on_boot()
            # FEAT-SYSTEM-AUTOREPAIR-BOOT-01: detecta infra quebrada (udev/WirePlumber)
            # e AVISA o comando de reparo — nunca roda sudo sozinho.
            self._check_system_on_boot()
            # COR-01/COR-03: fiação do registro de identidade + provider de
            # cor automática ANTES do connect inicial — o 1º reconcile do
            # backend (`_reapply_desired`) já resolve com o provider e os
            # slots restaurados do disco (a cor nasce certa no mesmo tick de
            # hotplug, D1). Fora do caminho quente (o load é um read único).
            self._wire_identity_registry()
            # EXT-04: identidade + LED dos externos, no MESMO gate de backend
            # real do identity_registry (fake => tudo desligado).
            self._wire_external_registry()
            # NUMA-01: sinal "jogo real ativo" — ATIVA o gate NUMA-02/03
            # (dormente até aqui). Ao contrário dos dois acima, nasce SEMPRE
            # (ver docstring de `_wire_game_signal`).
            self._wire_game_signal()
            # S-5: opener broker-aware da leitura de calibração 0x05 — sem ele
            # o `read_calibration` dá EACCES no hidraw ESCONDIDO (promoção
            # VPAD-02, respawn de coop) e o vpad herda calibração canônica
            # (drift do gyro). Mesmo gate de backend real dos wirings acima.
            self._wire_feature_opener()
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
                    # SPRINT-UHID-VPAD-01 + VPAD-03: com o blueprint canônico o
                    # vpad do P1 já nasce uhid no boot (isto aqui é no-op no
                    # caminho feliz). A chamada fica como REDE DE SEGURANÇA:
                    # recupera um vpad que degradou para uinput por razão
                    # transitória (ex.: /dev/uhid sem ACL na 1ª sessão).
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                            upgrade_primary_vpad_to_uhid,
                        )

                        upgrade_primary_vpad_to_uhid(self)
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

    def is_native_mode(self) -> bool:
        """True se o Modo Nativo está ativo (controle solto para o jogo)."""
        return self._native_mode

    def set_native_mode(
        self,
        enabled: bool,
        *,
        reapply: bool = True,
        restore_stash: bool = False,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga o Modo Nativo — "release total" do controle.

        FEAT-NATIVE-MODE-01. Para jogar Sackboy & cia com os gatilhos adaptativos
        NATIVOS da Sony (dirigidos pelo jogo), sem o hefesto no meio.

        `enabled=True`: solta o controle — gatilhos Off/Off (o jogo impõe os
        seus), rumble em passthrough (`rumble_active=None`, o hefesto não
        re-asserta), emulação de mouse E gamepad desligada (libera grab/uinput) —
        o ESTADO de emulação é guardado (stash) para restaurar depois. Gate
        `native_mode_active` (autoswitch/hotkey NÃO re-aplicam perfil). O poll
        loop consulta `_native_mode` DIRETAMENTE (não via `pause()`), então o
        dispatch fica congelado independente de pause/resume. Persiste flag+stash.

        `enabled=False`: limpa o gate, zera os motores (o jogo não é mais o dono
        do rumble — HARM-16), re-ativa o último perfil (gatilhos/rumble) e
        restaura a emulação do stash (gamepad tem precedência sobre mouse).
        `reapply=False` quando o chamador NÃO quer o last_profile re-aplicado
        (reversão por perfil: o perfil novo acabou de aplicar triggers/LEDs).
        `restore_stash=True` com `reapply=False` restaura SÓ a emulação do
        stash (BUG-NATIVE-REVERT-DROPS-STASH-01: a reversão por
        perfil-sem-opinião deixava a usuária SEM gamepad ao sair do jogo —
        flagrado ao vivo no Sackboy: alt-tab → nativo off → gamepad nunca
        voltava).

        NOTA (BUG-NATIVE-* da auditoria): o Modo Nativo NÃO usa mais `pause()` —
        gateia o dispatch pelo próprio flag. Assim `daemon.resume` não "des-solta"
        o controle e um pause manual anterior não é pisado.

        Idempotente. Retorna o novo estado.
        """
        from hefesto_dualsense4unix.utils.session import (
            load_gamepad_emulation,
            load_mouse_emulation,
            save_native_mode,
        )

        if origin == "manual":
            # FEAT-PROFILE-MODE-01: gesto manual de Modo Nativo entra na mesma
            # janela de respeito dos toggles de emulação — um perfil (autoswitch)
            # não liga/desliga o nativo por 30s após a usuária mexer na mão.
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: a POSSE do eixo de modo passa para a usuária aqui, ANTES
            # do early-return de idempotência abaixo. A limpeza que já existia
            # no fim da função é inalcançável quando `enabled` não muda — e aí
            # o flag "modo veio de perfil" ficava pendurado: passados os 30 s do
            # carimbo, o primeiro perfil sem `mode` revertia o que ela ligou na
            # mão. Carimbo e posse andam juntos, sempre.
            self._mode_from_profile = None
        if enabled == self._native_mode:
            return self._native_mode
        if enabled:
            # Captura o estado de emulação ANTES do release (o release apaga os
            # flags próprios). BUG-NATIVE-DESTROYS-GAMEPAD-01.
            m_on, m_speed, m_scroll = load_mouse_emulation()
            g_on, g_flavor = load_gamepad_emulation()
            self._native_emu_stash = {
                "mouse": [bool(m_on), m_speed, m_scroll],
                "gamepad": [bool(g_on), g_flavor],
            }
            self._native_mode = True
            self.store.set_native_mode_active(True, origin=origin)
            save_native_mode(True, emu_stash=self._native_emu_stash)
            self._release_controller_to_game()
        else:
            self._native_mode = False
            self.store.set_native_mode_active(False)
            save_native_mode(False)
            # FEAT-NATIVE-OUTPUT-MUTE-01: desmuta ANTES do reapply — o
            # perfil/rumble/LED re-aplicados precisam chegar ao controle.
            unmute = getattr(self.controller, "set_output_mute", None)
            if callable(unmute):
                with contextlib.suppress(Exception):
                    unmute(False)
            # HARM-16: quem estava vibrando era o JOGO (escrevendo direto no
            # hidraw, com o nosso output mutado). Ao sair, ninguém zera esses
            # motores: `rumble_active` está em passthrough (None), então o
            # reassert do poll loop é no-op e a vibração fica FIXA para sempre.
            self._zero_rumble_motors()
            if reapply:
                self._reapply_last_profile()
            if reapply or restore_stash:
                self._restore_emulation_from_stash()
            self._native_emu_stash = {}
        if origin == "manual":
            self._mode_from_profile = None
        # DEDUP-04: o Modo Nativo muda o conteúdo das envs de launch
        # (sem DISABLE/IGNORE — o jogo fala com o hidraw do FÍSICO,
        # GUERRA-01). Os hooks de start/stop do gamepad não cobrem o caso
        # "nativo ligado com emulação já desligada", então regrava aqui, no
        # fim da transição inteira.
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self)
        logger.info("native_mode_changed", native=enabled, origin=origin)
        return self._native_mode

    def _release_controller_to_game(self) -> None:
        """Neutraliza a saída do hefesto no controle (FEAT-NATIVE-MODE-01)."""
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        # Gatilhos Off/Off: o hefesto não impõe resistência; o jogo sobrescreve.
        with contextlib.suppress(Exception):
            off = build_from_name("Off", [])
            self.controller.set_trigger("left", off)
            self.controller.set_trigger("right", off)
        # Rumble passthrough: reassert_rumble pula quando rumble_active é None.
        self.config.rumble_active = None
        # Emulação off: libera grab de evdev / device uinput. origin="profile"
        # de propósito: desligar a emulação no release NÃO é um gesto manual da
        # usuária — se carimbasse `_emu_manual_ts`, o lock de 30s BLOQUEARIA o
        # restore ao desligar (BUG-NATIVE-RELEASE-LOCKS-RESTORE-01).
        with contextlib.suppress(Exception):
            self.set_mouse_emulation(False, origin="profile")
        with contextlib.suppress(Exception):
            self.set_gamepad_emulation(False, origin="profile")
        # FEAT-NATIVE-OUTPUT-MUTE-01: release TOTAL inclui o output HID — sem
        # isto o keepalive do report_thread pisoteava o rumble/gatilhos/LED que
        # o JOGO escrevia no hidraw (rumble morto no Sackboy, ao vivo).
        mute = getattr(self.controller, "set_output_mute", None)
        if callable(mute):
            with contextlib.suppress(Exception):
                mute(True)

    def _reapply_last_profile(self) -> None:
        """Re-ativa o perfil corrente ao sair do Modo Nativo (gatilhos/teclado).

        PERFIL-03: prefere `store.active_profile` (o perfil ATIVO — inclusive
        um escolhido pelo autoswitch pela janela em foco) e só cai no
        session.json quando não há ativo em memória. Com a semântica nova
        (session.json = última escolha MANUAL), a ordem antiga re-aplicaria a
        última escolha manual por cima do perfil que o autoswitch ativou —
        mudança não intencional apontada pela tabela dos 5 call sites. A
        ativação vai com `origin="system"`: sair do nativo não é escolha nova
        de perfil e NÃO regrava a intenção manual.
        """
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.utils.session import load_last_profile

        name = self.store.active_profile or load_last_profile()
        if not name:
            return
        manager = ProfileManager(
            controller=self.controller,
            store=self.store,
            keyboard_device_provider=lambda: getattr(self, "_keyboard_device", None),
            mouse_applier=self.apply_profile_mouse,
            suppression_applier=self.apply_profile_suppression,
            # FEAT-PROFILE-MODE-01: SEM mode_applier aqui de propósito — este
            # caminho roda ao SAIR do Modo Nativo; se o last_profile tiver
            # `mode.kind=native`, o applier o religaria na hora (loop). O gesto
            # de sair é soberano; o próximo autoswitch/switch re-avalia o modo.
        )
        with contextlib.suppress(Exception):
            manager.activate(name, origin="system")

    def _zero_rumble_motors(self) -> None:
        """Zera os motores ao SAIR de um modo (HARM-16). Thin wrapper."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            zero_motors_on_mode_exit,
        )

        zero_motors_on_mode_exit(self)

    def _restore_emulation_from_stash(self) -> None:
        """Restaura a emulação capturada antes do Modo Nativo (FEAT-NATIVE-MODE-01).

        Gamepad tem precedência sobre mouse (mesma regra do boot: jogar = controle
        vai pro jogo). Roda DEPOIS de `_reapply_last_profile` para vencer uma seção
        mouse do perfil (o estado pré-nativo da usuária manda).
        BUG-NATIVE-DESTROYS-GAMEPAD-01.
        """
        stash = getattr(self, "_native_emu_stash", None) or {}
        g = stash.get("gamepad") or [False, None]
        m = stash.get("mouse") or [False, None, None]
        if g[0]:
            with contextlib.suppress(Exception):
                self.set_gamepad_emulation(True, g[1], origin="profile")
        elif m[0]:
            with contextlib.suppress(Exception):
                self.set_mouse_emulation(
                    True, m[1], m[2], origin="profile"
                )

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
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga emulação de mouse e atualiza velocidades. Usado pelo IPC.

        BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: `origin` distingue o gesto MANUAL
        (IPC/GUI/CLI/hotkey — default, preserva todos os callers) da aplicação
        por PERFIL (`apply_profile_mouse`). Manual carimba `_emu_manual_ts`,
        travando o applier de perfil por `MANUAL_PROFILE_LOCK_SEC`.
        """
        from hefesto_dualsense4unix.daemon.subsystems.mouse import (
            start_mouse_emulation,
            stop_mouse_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))
        # BUG-EMU-DEVICE-RACE-01: serializa a transição de device (create/destroy)
        # para não colidir com set_gamepad_emulation/outra thread.
        with self._emu_lock:
            if enabled:
                # FEAT-DSX-GAMEPAD-FLAVOR-01: mútua exclusão — ligar o mouse
                # desliga o gamepad virtual (e libera o grab do controle).
                if self._gamepad_device is not None:
                    self._stop_gamepad_emulation()
                ok = start_mouse_emulation(self)
                if ok and self._mouse_device is not None:
                    self._mouse_device.set_speed(
                        mouse_speed=self.config.mouse_speed,
                        scroll_speed=self.config.mouse_scroll_speed,
                    )
                    # FEAT-MOUSE-CURSOR-FEEL-01 (A5): com device JÁ vivo,
                    # start_mouse_emulation retorna cedo sem persistir — re-salva
                    # o flag para que "ligar de novo com speed nova" sobreviva a
                    # restart (no start de verdade a escrita é redundante).
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.utils.session import (
                            save_mouse_emulation,
                        )

                        save_mouse_emulation(
                            True,
                            speed=self.config.mouse_speed,
                            scroll_speed=self.config.mouse_scroll_speed,
                        )
                return ok
            stop_mouse_emulation(self)
            return True

    def restore_mouse_preference(self) -> bool:
        """Aplica a preferência de mouse persistida (HARM-06). Retorna se ligou.

        É o que faz "Controlar o PC" ser um modo de verdade, e não só o
        desligar dos outros dois: entrar nele devolve o cursor conforme a última
        escolha da usuária. Sem isto o controle ficava sem função NENHUMA até
        alguém achar a aba Mouse.

        Nunca configurada (flag ausente) liga por default — a alternativa é o
        controle mudo. "Desligado de propósito" é respeitado, e é por isso que
        `load_mouse_preference` distingue os dois casos.

        A leitura mora aqui, no daemon, porque é ele quem grava a preferência —
        um segundo leitor na GUI seria um segundo dono do mesmo conceito.
        """
        from hefesto_dualsense4unix.utils.session import load_mouse_preference

        pref, speed, scroll_speed = load_mouse_preference()
        if pref is None:
            pref = True
        ok = self.set_mouse_emulation(pref, speed, scroll_speed)
        logger.info("mouse_preference_restored", enabled=pref, ok=ok)
        return bool(pref and ok)

    def set_mouse_speed(
        self,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Atualiza velocidades da emulação SEM ligar/desligar (speed-only).

        BUG-MOUSE-GUI-SYNC-01 (A4): rota dos sliders da GUI — nunca faz
        start/stop nem CRIA o flag de emulação. Com device vivo aplica na
        hora; sem device só atualiza a config (vale quando ligar). Religar a
        emulação (e matar o gamepad virtual) por slider é impossível aqui.

        FEAT-MOUSE-CURSOR-FEEL-01 (A5): com a emulação JÁ LIGADA, re-persiste
        o flag existente com as velocidades novas — mudança de speed com o
        mouse ligado tem que sobreviver a restart. Com a emulação desligada
        nada é escrito (criar o flag aqui religaria a emulação no boot — a
        regressão exata do A4).
        """
        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))
        if self._mouse_device is not None:
            self._mouse_device.set_speed(
                mouse_speed=self.config.mouse_speed,
                scroll_speed=self.config.mouse_scroll_speed,
            )
        if self.config.mouse_emulation_enabled:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_mouse_emulation

                save_mouse_emulation(
                    True,
                    speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed,
                )
        return True

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara. Usado pelo IPC.

        FEAT-DSX-GAMEPAD-FLAVOR-01. `flavor` em ('dualsense','xbox'); None mantém
        o atual. Ligar desliga a emulação de mouse (mútua exclusão) e SAI do Modo
        Nativo (idem). Retorna True se o estado pedido foi alcançado.

        BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: um `gamepad on` manual carimba
        `_emu_manual_ts` — assim um perfil point-and-click focado logo em seguida
        (autoswitch) NÃO mata o gamepad ligado na mão (lock de 30s).

        HARM-01: sair do nativo antes de ligar o vpad é garantido AQUI porque o
        daemon é o único ponto por onde todas as superfícies passam (GUI, applet,
        CLI, perfil, hotkey, autoswitch) — a CLI não pode importar o
        `app.actions.mode_transition` sem arrastar GTK. Sem isto, um `gamepad on`
        com o nativo ligado deixava os dois ligados juntos: o físico grabado pelo
        vpad e o dispatch congelado pelo gate do nativo = jogo sem controle
        nenhum. O caminho inverso (`native.mode.set True` com o vpad ligado) já
        era coberto pelo `_release_controller_to_game`.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            start_gamepad_emulation,
            stop_gamepad_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: gesto manual toma a POSSE do eixo de modo — paridade com
            # `_suppress_from_profile` (set_emulation_suppressed) e
            # `_rumble_policy_from_profile` (mark_rumble_policy_manual), que já
            # faziam isso. Sem esta linha, o carimbo protegia por só 30 s: depois
            # o primeiro perfil sem seção `mode` — quase todos os dela — chamava
            # `set_gamepad_emulation(False, origin="profile")` sobre um vpad que
            # ela tinha ligado na mão.
            self._mode_from_profile = None
        # BUG-EMU-DEVICE-RACE-01: mesma serialização do set_mouse_emulation.
        with self._emu_lock:
            if enabled:
                # HARM-01: a MESMA saída que a GUI já pede no passo 1 do plano
                # dela (`native.mode.set False`) — não uma segunda semântica de
                # "sair do nativo". Quando a GUI manda o passo, este vira no-op
                # (o setter é idempotente). O restore do stash que ele dispara
                # não reentra aqui: `_native_mode` já é False quando roda.
                if self._native_mode:
                    self.set_native_mode(False, origin=origin)
                # BT-04(b): `origin` segue até o gate da promoção uinput→uhid —
                # só o gesto manual da usuária recria um vpad degradado; o
                # apply de perfil/autoswitch (a cada troca de janela) nunca.
                # MISC-08 item 3 (2026-07-18): assinatura ANTES do apply — um
                # apply IDÊNTICO (mesmo flavor, mesmo device) não pode custar
                # teardown+respawn de vpad nenhum. Ao vivo, recriar os vpads
                # mid-game invalidou os handles do jogo (a Steam nunca reabriu
                # o hidraw do vpad P1). O `start_gamepad_emulation` já é
                # no-op por (flavor, backend); o guard aqui poupa também o
                # ciclo FORÇADO do co-op (que reescreve player-LEDs via sysfs
                # a cada força — ruído de escrita sem mudança nenhuma).
                device_antes = self._gamepad_device
                ok = start_gamepad_emulation(self, flavor=flavor, origin=origin)
                # SPRINT-GAME-RUMBLE-01: repropaga a máscara recém-aplicada aos
                # vpads de co-op já criados. Trocar o flavor não muda /dev/input,
                # então o watch do coop não dispara sozinho — force=True roda o
                # ciclo cheio e o teardown por flavor-mismatch recria cada
                # secundário com a nova máscara (senão P2+ ficam no flavor antigo,
                # com rumble morto e prompts divergentes do P1).
                if ok and self._gamepad_device is not device_antes:
                    from hefesto_dualsense4unix.daemon.subsystems.coop import (
                        get_coop_manager,
                    )

                    with contextlib.suppress(Exception):
                        get_coop_manager(self).sync(force=True)
                elif ok:
                    # Config efetiva não mudou: nenhum vpad foi recriado e o
                    # co-op segue no ciclo normal (~2s) do poll loop.
                    logger.debug("gamepad_apply_identico_sem_recriacao")
                return ok
            # HARM-16: o zero dos motores vem de dentro do stop (parar o vpad é
            # o que deixa o motor sem dono), não de um passo extra aqui.
            # R-07: só gesto manual apaga a preferência em disco. Um perfil sem
            # seção `mode` desligando o gamepad fazia `flag.unlink()` — e no
            # boot seguinte não nascia vpad nenhum, obrigando a religar tudo na
            # mão. O runtime continua desligando; a PREFERÊNCIA sobrevive.
            stop_gamepad_emulation(self, persist=(origin == "manual"))
            return True

    def set_coop_enabled(
        self,
        enabled: bool,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga o co-op local (FEAT-DSX-COOP-LOCAL-01). Usado pelo IPC.

        Persiste o toggle (sobrevive reboot) e reconcilia na hora: ligar sobe os
        jogadores secundários (se gamepad on + 2+ controles); desligar desmonta
        todos (solta grab/uinput). Retorna o estado efetivo de `coop_enabled`.
        """
        self.config.coop_enabled = bool(enabled)
        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: idem `set_gamepad_emulation` — o co-op é parte do mesmo
            # eixo (`mode.coop`), então ligá-lo na mão também toma a posse.
            self._mode_from_profile = None
            # FEAT-COOP-DEFAULT-ON-01: só gesto MANUAL persiste a escolha —
            # perfil ligando/desligando co-op não pode virar opt-out da usuária.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_coop_enabled

                save_coop_enabled(self.config.coop_enabled)
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self)
        if self.config.coop_enabled:
            coop.sync(force=True)
        else:
            coop.disable()
        logger.info(
            "coop_enabled_set",
            enabled=self.config.coop_enabled,
            players=coop.player_count(),
        )
        return self.config.coop_enabled

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga a supressão da emulação de mouse/teclado (modo jogo).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. `value=None` faz toggle; caso
        contrário, define explicitamente. Os devices uinput permanecem vivos —
        só o despacho no poll loop é pulado, e os hotkeys continuam ativos.
        Notifica o usuário e retorna o novo estado (True = emulação suprimida).

        FEAT-POINT-AND-CLICK-01: `origin` distingue o gesto MANUAL da usuária
        (hotkey/IPC/GUI — default, preserva todos os callers existentes) da
        aplicação por PERFIL (`apply_profile_suppression`). Toggle manual
        carimba `_suppress_manual_ts` e zera `_suppress_from_profile` — a
        partir daí perfis não revertem a escolha (ver
        `apply_profile_suppression`).
        """
        from hefesto_dualsense4unix.integrations.desktop_notifications import (
            notify_emulation_suppressed,
        )

        new_state = (not self._emulation_suppressed) if value is None else bool(value)
        self._emulation_suppressed = new_state
        if origin == "manual":
            self._suppress_manual_ts = time.monotonic()
            self._suppress_from_profile = False
        if new_state:
            # FEAT-EMULATION-GAMEMODE-FLUSH-01: ao suprimir, solta tudo que estiver
            # pressionado nos devices virtuais — senão um modificador (ex.: Meta de
            # 'options' no PS+Options) fica preso, já que o poll loop para de
            # despachar e nunca envia o release.
            self._flush_emulation_devices()
        logger.info("emulation_suppressed_changed", suppressed=new_state)
        notify_emulation_suppressed(new_state)
        return new_state

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any | None = None
    ) -> None:
        """Aplica `suppress_desktop_emulation` de um perfil recém-ativado.

        FEAT-POINT-AND-CLICK-01. Injetado como `suppression_applier` do
        `ProfileManager` — chamado a CADA ativação de perfil (IPC, autoswitch,
        hotkey de ciclo, restore no boot), sempre com o valor do campo
        (inclusive o default False).

        Semântica escolhida (documentada aqui como fonte canônica):

        1. **Lock manual** — se a usuária alternou o modo-jogo manualmente
           (PS+Options, IPC, GUI) há menos de ``MANUAL_PROFILE_LOCK_SEC``
           (30s, mesma constante do lock de perfil manual), o perfil NÃO mexe
           na supressão em NENHUMA direção (nem liga, nem libera). Log
           informativo e retorno.
        2. **desired=True** — liga a supressão (idempotente: só chama o setter
           se o estado muda, evitando flush/notificação repetidos a cada tick
           do autoswitch) e marca origem "perfil". Se a supressão já estava
           ligada por gesto manual ANTIGO (lock expirado), o perfil a ADOTA:
           ao sair do jogo, o perfil do desktop libera — é a UX esperada do
           autoswitch dono do estado após a janela de respeito.
        3. **desired=False** — LIBERA a supressão apenas se ela veio de perfil
           (`_suppress_from_profile`). Supressão de origem manual (lock já
           expirado, sem perfil que a adotasse) permanece intocada: quem ligou
           na mão, desliga na mão.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if now - self._suppress_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_suppression_skipped_manual_lock",
                desired=desired,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._suppress_manual_ts), 1
                ),
            )
            return
        if desired:
            if not self._emulation_suppressed:
                self.set_emulation_suppressed(True, origin="profile")
            self._suppress_from_profile = True
        elif self._emulation_suppressed and self._suppress_from_profile:
            # R-02: mesma regra do modo — LIBERAR a supressão é uma decisão, e
            # um catch-all não tem autoridade para tomá-la. Sem esta guarda, o
            # `vitoria` (suppress=False, o default) soltava a emulação de
            # desktop dentro do jogo: o mouse/teclado emulado voltava a
            # disputar com o jogo enquanto ela jogava.
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                )
                return
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                )
                return
            self.set_emulation_suppressed(False, origin="profile")
            self._suppress_from_profile = False

    def apply_profile_mouse(
        self, enabled: bool, speed: int, scroll_speed: int
    ) -> None:
        """Aplica a seção `mouse` de um perfil recém-ativado (BUG-PROFILE-MOUSE-
        KILLS-GAMEPAD-01). Injetado como `mouse_applier` nas rotas de ativação
        (IPC switch, autoswitch, hotkey de ciclo). NÃO é usado no restore do
        boot (lá os flags persistidos governam — ver connection.py).

        Semântica (espelha `apply_profile_suppression`):

        1. **Lock manual** — se a usuária mexeu na emulação (mouse OU gamepad)
           manualmente há menos de `MANUAL_PROFILE_LOCK_SEC`, o perfil NÃO toca
           no estado: não sequestra um gamepad virtual ligado na mão no meio do
           jogo (o bug original: focar um ScummVM matava o gamepad).
        2. **Idempotente** — só chama `set_mouse_emulation` quando o estado
           muda; com o mouse já no estado desejado e ligado, atualiza apenas as
           velocidades (evita destruir/recriar o device a cada tick do
           autoswitch e o tear-down repetido do gamepad).
        3. `origin="profile"` — não re-carimba o lock manual.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_mouse_skipped_manual_lock",
                enabled=enabled,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                ),
            )
            return
        # BUG-PROFILE-MOUSE-IDEMPOTENT-STALE-CONFIG-01: o estado REAL de "ligado"
        # é config E device vivo. No boot, run() seta config=True do flag ANTES do
        # start; se start_mouse_emulation falha (uinput indisponível no boot),
        # fica config=True/_mouse_device=None. Confiar só na config faria o ramo
        # idempotente pular a (re)criação e o mouse nunca ligaria apesar do perfil
        # pedir. Checar o device restaura a auto-recuperação por ativação de perfil.
        actual_on = self.config.mouse_emulation_enabled and self._mouse_device is not None
        if enabled == actual_on:
            if enabled:
                self.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            return
        self.set_mouse_emulation(
            enabled, speed, scroll_speed, origin="profile"
        )

    def _perfil_tem_opiniao(self, profile: Any | None) -> bool:
        """False quando o perfil é catch-all (`MatchAny` ou criteria vazio).

        R-02 (auditoria 23/07). Um catch-all não é "o perfil deste app": é o
        que sobra quando NENHUMA regra casou. Tratar a ausência de opinião dele
        como ordem de reverter era o que desligava o vpad no meio da partida do
        Mullet Mad Jack — jogo sem perfil próprio cai no `vitoria`, que tem
        `mode=null`, e o ramo de reversão executava
        `set_gamepad_emulation(False, origin="profile")` com o jogo em foco.

        `getattr` defensivo: os dublês de teste injetam appliers e perfis
        parciais, e a ausência do atributo não pode virar exceção no meio de
        uma ativação. Na dúvida (sem `match` legível) o perfil é tratado como
        SEM opinião — fail-safe: não derruba o modo da usuária.
        """
        if profile is None:
            return False
        e_catch_all = getattr(profile, "e_catch_all", None)
        if e_catch_all is None:
            return False
        return not e_catch_all

    def _janela_de_jogo_em_foco(self) -> bool:
        """True quando a janela em foco AGORA é de um jogo Steam.

        R-02, decisão 3 do plano: leitura CRUA da janela, deliberadamente
        diferente do `display_authority` (que é sticky por 30 s). Aqui a
        pergunta é "reverter para desktop agora seria absurdo?", e para isso o
        sinal sticky congelaria a reversão legítima ao sair do jogo. O sinal
        sticky continua sendo o certo para operação DESTRUTIVA (recriar/parar
        vpad), onde fail-safe é não destruir.
        """
        from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

        wm_class = getattr(self.store, "window_detect_current_class", None)
        return steam_appid_from_wm_class(str(wm_class or "")) is not None

    def apply_profile_mode(self, mode: Any | None, *, profile: Any | None = None) -> None:
        """Aplica a seção `mode` de um perfil recém-ativado (FEAT-PROFILE-MODE-01).

        Injetado como `mode_applier` nas rotas de ativação (IPC switch,
        autoswitch, hotkey de ciclo). NÃO usado no restore do boot (lá os flags
        persistidos governam — ver connection.py). É o que faz as features
        COEXISTIREM: o perfil do jogo em foco decide o modo, em vez de toggles
        globais brigando.

        Semântica (espelha `apply_profile_suppression`/`apply_profile_mouse`):

        1. **Lock manual** — gesto manual (gamepad/mouse/nativo/co-op) há menos
           de `MANUAL_PROFILE_LOCK_SEC` congela: o perfil não mexe no modo.
        2. **mode=None (perfil sem opinião)** — REVERTE apenas modo que outro
           PERFIL ligou (`_mode_from_profile`); estado de origem manual fica.
        3. **kind="native"** — liga o Modo Nativo (release total) com origem
           perfil; sair do foco (outro perfil ativar) reverte pelo item 2.
        4. **kind="gamepad"** — desliga nativo-de-perfil se preciso, liga o
           gamepad com a máscara pedida e sincroniza o co-op ao campo `coop`.
        5. **kind="desktop"** — declaração explícita: desliga nativo/gamepad
           mesmo os de origem manual JÁ EXPIRADA do lock (o perfil está
           dizendo "este app é desktop puro").

        LEIGO-01: a PREFERÊNCIA de co-op nunca é desligada por perfil que sai do
        gamepad (itens 2 e 5) — sem gamepad não há jogadores para desmontar, e
        zerá-la aqui deixaria o co-op morto pelo resto da sessão.

        Idempotente por checagem de estado antes de cada setter (autoswitch
        re-ativa o mesmo perfil sem flap).
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        kind = getattr(mode, "kind", None) if mode is not None else None
        now = time.monotonic()
        if now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if kind is not None:
                logger.info(
                    "profile_mode_skipped_manual_lock",
                    kind=kind,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            return

        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )

        if kind is None:
            # R-02 (auditoria 23/07): "sem opinião" NÃO é ordem de reverter
            # quando quem chegou é um catch-all. Jogo sem perfil próprio cai no
            # `vitoria` (MatchAny, mode=null) e o ramo abaixo desligava o vpad
            # COM O JOGO EM FOCO — zero controles no meio da partida. Duas
            # guardas independentes, ambas fail-safe:
            #   1. catch-all nunca reverte (ausência de regra ≠ ordem);
            #   2. com janela de jogo em foco, nenhum perfil reverte modo —
            #      cobre o caso em que uma regra específica casa por engano
            #      (ex.: regex solto) enquanto ela joga.
            # Reversão legítima continua acontecendo: perfil `criteria` de
            # desktop (Navegação no Firefox) e `kind="desktop"` explícito.
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return
            # Perfil sem opinião: reverte só o que veio de perfil.
            if self._mode_from_profile == "native" and self._native_mode:
                # restore_stash: devolve o gamepad/co-op que a usuária tinha
                # ANTES do jogo (sem re-aplicar last_profile — o perfil novo
                # acabou de aplicar os triggers/LEDs dele).
                self.set_native_mode(
                    False, reapply=False, restore_stash=True, origin="profile"
                )
            # LEIGO-01: sair do gamepad NÃO desliga o co-op — desligar o gamepad
            # já desmonta os jogadores (`CoopManager.should_be_active`), e zerar
            # a preferência aqui a deixava desligada pela sessão inteira, sem
            # caminho de volta agora que o checkbox saiu da tela. Mesma decisão
            # do `mode_transition.plan_mode_transition` (desktop).
            elif self._mode_from_profile == "gamepad" and gamepad_on:
                self.set_gamepad_emulation(False, origin="profile")
            self._mode_from_profile = None
            return

        if kind == "native":
            if not self._native_mode:
                self.set_native_mode(True, origin="profile")
            self._mode_from_profile = "native"
            return

        if kind == "gamepad":
            if self._native_mode:
                # Sem reapply: o perfil ATUAL acabou de aplicar triggers/LEDs;
                # re-aplicar o last_profile/stash desfaria a ativação corrente.
                self.set_native_mode(False, reapply=False, origin="profile")
            flavor = getattr(mode, "gamepad_flavor", None)
            flavor_atual = getattr(self._gamepad_device, "flavor", None)
            if not gamepad_on or (flavor is not None and flavor != flavor_atual):
                self.set_gamepad_emulation(True, flavor, origin="profile")
            # LEIGO-01: o default do campo é True (esquema) — o fallback do
            # getattr acompanha, senão um `mode` dublado sem o campo voltaria a
            # significar "desliga o co-op".
            want_coop = bool(getattr(mode, "coop", True))
            if want_coop != bool(self.config.coop_enabled):
                self.set_coop_enabled(want_coop, origin="profile")
            self._mode_from_profile = "gamepad"
            return

        # kind == "desktop": declaração explícita — limpa qualquer modo.
        # LEIGO-01: o co-op fica de fora da limpeza pelo mesmo motivo do ramo
        # `kind is None` — desligar o gamepad abaixo já desmonta os jogadores, e
        # a preferência tem de sobreviver ao app de desktop para o co-op voltar
        # sozinho no próximo jogo.
        if self._native_mode:
            self.set_native_mode(False, reapply=False, origin="profile")
        if gamepad_on:
            self.set_gamepad_emulation(False, origin="profile")
        self._mode_from_profile = None

    def apply_profile_rumble_policy(
        self, policy: str | None, custom_mult: float | None = None
    ) -> None:
        """Aplica a política de rumble de um perfil recém-ativado
        (FEAT-RUMBLE-POLICY-PROFILE-01). Injetado como `rumble_policy_applier`
        nas rotas de ativação (IPC switch, autoswitch, hotkey de ciclo e
        restore do boot — a política não tem flag persistido próprio, então o
        perfil é a única fonte para restaurá-la).

        Semântica (espelha `apply_profile_mode`):

        1. **Lock manual** — gesto manual há menos de `MANUAL_PROFILE_LOCK_SEC`
           congela: o perfil não mexe na política. O gesto manual DA POLÍTICA
           é o IPC `rumble.policy_set`/`rumble.policy_custom`, que carimba o
           mesmo `_emu_manual_ts` dos toggles de emulação (via
           `mark_rumble_policy_manual`).
        2. **policy=None (perfil sem opinião)** — REVERTE apenas política que
           outro PERFIL aplicou: volta ao par (policy, custom_mult) vigente
           ANTES de o 1º perfil-com-opinião mexer. Política de origem manual
           fica intocada.
        3. **policy preenchida** — guarda a política anterior (1ª intervenção
           de perfil), grava no `DaemonConfig` e re-aplica o rumble ATIVO via
           `apply_rumble_policy` para efeito imediato. Se a política vigente
           já era a pedida (gesto manual antigo, lock expirado), o perfil a
           ADOTA — mesma UX do `apply_profile_suppression`.

        Idempotente: re-ativação do mesmo perfil (tick do autoswitch) não
        re-aplica nem loga de novo.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if policy is not None:
                logger.info(
                    "profile_rumble_policy_skipped_manual_lock",
                    policy=policy,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            return

        if policy is None:
            # Perfil sem opinião: reverte só política que veio de perfil.
            if self._rumble_policy_from_profile:
                before = self._rumble_policy_before_profile
                if before is not None:
                    self.config.rumble_policy = before[0]
                    self.config.rumble_policy_custom_mult = before[1]
                    logger.info(
                        "profile_rumble_policy_reverted",
                        policy=before[0],
                        mult=before[1],
                    )
                self._rumble_policy_from_profile = False
                self._rumble_policy_before_profile = None
                self._seed_rumble_mult_observability()
                self._reapply_rumble_policy_to_active()
            return

        if policy not in RUMBLE_POLICIES:
            # Defensivo: o schema do perfil já rejeita, mas o applier é
            # público — política desconhecida não pode corromper a config.
            logger.warning("profile_rumble_policy_invalida", policy=policy)
            return
        policy_lit = cast("RumblePolicy", policy)

        if not self._rumble_policy_from_profile:
            # 1ª intervenção de perfil: guarda a política vigente para o
            # perfil-sem-opinião reverter depois.
            self._rumble_policy_before_profile = (
                self.config.rumble_policy,
                self.config.rumble_policy_custom_mult,
            )
        desired_mult = (
            max(0.0, min(2.0, float(custom_mult)))
            if custom_mult is not None
            else self.config.rumble_policy_custom_mult
        )
        changed = (
            self.config.rumble_policy != policy_lit
            or self.config.rumble_policy_custom_mult != desired_mult
        )
        self.config.rumble_policy = policy_lit
        self.config.rumble_policy_custom_mult = desired_mult
        self._rumble_policy_from_profile = True
        self._seed_rumble_mult_observability()
        if changed:
            # MISC-08 item 1 (2026-07-18): o campo `mult` carregava o
            # custom_mult vigente (0.7 default) mesmo em política fixa —
            # "mult=0.7 policy=max" no journal parecia atenuação real do
            # rumble. Loga o mult EFETIVO da política aplicada (para "auto"
            # não há valor fixo: é resolvido por bateria a cada tick).
            logger.info(
                "profile_rumble_policy_applied",
                policy=policy_lit,
                mult=(
                    desired_mult
                    if policy_lit == "custom"
                    else RUMBLE_POLICY_MULT.get(policy_lit)
                ),
                custom_mult=desired_mult,
            )
            self._reapply_rumble_policy_to_active()

    def apply_profile_rumble_passthrough(self, passthrough: bool) -> None:
        """Aplica `rumble.passthrough` de um perfil recém-ativado (SPRINT-GAME-RUMBLE-01).

        passthrough=True (default de TODO perfil) devolve a vibração ao JOGO:
        solta o rumble FIXADO pela GUI (`rumble_active=None`) e zera os motores
        uma vez. Sem isto, um "Aplicar"/"Parar" na aba Rumble deixava o rumble
        travado e `apply_game_rumble` ignorava o FF do jogo mesmo com a máscara
        Xbox correta — a segunda metade do "testei os motores e o jogo não vibra".

        Só age quando há rumble fixado em valor NÃO-ZERO (`rumble_active` com
        weak/strong > 0 — o caso do "Aplicar"/teste que deixou motor ligado). Em
        passthrough já ativo é no-op.

        M2 (auditoria): NÃO desfaz o silêncio DELIBERADO (`rumble_active == (0,0)`,
        o "Parar" da GUI). Antes, como todo perfil tem `passthrough=True`, um
        alt-tab/PS+dpad/reconexão logo após "Parar" religava o passthrough e o
        jogo voltava a sacudir o controle — contrariando o gesto da usuária. O
        silêncio fixo é intencional e sobrevive à troca de perfil; para devolver
        ao jogo, a usuária usa "Devolver ao jogo" (ou aplica um rumble de teste).
        """
        if not passthrough:
            return
        active = self.config.rumble_active
        if active is None:
            return
        if active == (0, 0):
            # Silêncio deliberado (botão "Parar") — preserva; não religa o jogo.
            return
        self.config.rumble_active = None
        with contextlib.suppress(Exception):
            self.controller.set_rumble(weak=0, strong=0)
        logger.info("profile_rumble_passthrough_released")

    def mark_rumble_policy_manual(self) -> None:
        """Registra gesto MANUAL na política de rumble
        (FEAT-RUMBLE-POLICY-PROFILE-01).

        Chamado pelos handlers IPC `rumble.policy_set`/`rumble.policy_custom`:
        carimba `_emu_manual_ts` (lock de 30s — perfis não pisam a escolha
        recente da usuária, paridade com os toggles de emulação) e limpa a
        origem "perfil" (a política vigente passa a ser manual; perfil sem
        opinião não a reverte mais — quem mexeu na mão, desfaz na mão).
        """
        self._emu_manual_ts = time.monotonic()
        self._rumble_policy_from_profile = False
        self._rumble_policy_before_profile = None

    def _seed_rumble_mult_observability(self) -> None:
        """Sincroniza `_last_auto_mult` com o mult efetivo da política vigente.

        MISC-08 item 1 (2026-07-18): `daemon._last_auto_mult` é a fonte do
        `rumble_mult_applied` do state_full, mas só era atualizado quando um
        caminho de rumble de fato COMPUTAVA (`reassert_rumble` exige rumble
        fixado; `_game_rumble_mult` exige FF do jogo). Em passthrough ocioso,
        aplicar um perfil com política fixa deixava o campo preso no default
        0.7 — ao vivo, `policy=max` + `rumble_mult_applied=0.7` no state_full
        parecia atenuação real do rumble do jogo. Política "auto" fica de
        fora de propósito: o valor dela é resolvido por bateria (com
        debounce) no próximo cômputo.
        """
        policy = self.config.rumble_policy
        if policy == "custom":
            self._last_auto_mult = float(self.config.rumble_policy_custom_mult)
        elif policy in RUMBLE_POLICY_MULT:
            self._last_auto_mult = RUMBLE_POLICY_MULT[policy]

    def _reapply_rumble_policy_to_active(self) -> None:
        """Re-aplica a política vigente ao rumble ATIVO (efeito imediato).

        Sem rumble fixado (`rumble_active=None`, passthrough) é no-op — o
        multiplicador da política é aplicado na entrada de cada write
        (`rumble.set`/reassert do poll loop). Best-effort: falha de hardware
        não aborta a ativação do perfil.
        """
        active = self.config.rumble_active
        if active is None:
            return
        from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
            apply_rumble_policy,
        )

        with contextlib.suppress(Exception):
            eff_weak, eff_strong = apply_rumble_policy(self, active[0], active[1])
            self.controller.set_rumble(weak=eff_weak, strong=eff_strong)

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
        """Thin wrapper — gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01).

        R-07: `origin="profile"` de propósito. Este é o restore do BOOT — ele
        LÊ a flag persistida e a reaplica; não é gesto novo da usuária. Com o
        default "manual" ele regravaria em disco o que acabou de ler (inócuo
        hoje, mas é a mesma confusão de origem que fazia o perfil apagar a
        escolha dela).
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import start_gamepad_emulation

        return start_gamepad_emulation(
            self, flavor=self.config.gamepad_flavor, origin="profile"
        )

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

    async def _start_metrics(self) -> None:
        """Inicializa o MetricsSubsystem se metrics_enabled (FEAT-METRICS-01).

        Espelha `_start_plugins`: o `MetricsSubsystem.start` espera um
        `DaemonContext` (não é um starter sem-arg), então montamos o contexto
        aqui. O gate `is_enabled(config)` é respeitado — o servidor HTTP só
        sobe quando `metrics_enabled=True`.
        """
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem

        ms = MetricsSubsystem()
        if not ms.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ms.start(ctx)
        self._metrics_subsystem = ms

    async def _stop_metrics(self) -> None:
        """Para o MetricsSubsystem de forma limpa. Idempotente."""
        if self._metrics_subsystem is not None:
            await self._metrics_subsystem.stop()
            self._metrics_subsystem = None

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
    # Identidade dos controles (COR-01/COR-03)
    # ------------------------------------------------------------------

    def _wire_identity_registry(self) -> None:
        """Cria o registro de identidade e injeta o provider de cor no backend.

        COR-01/COR-03: SÓ quando o backend suporta a injeção
        (`set_auto_output_provider` — o PyDualSenseController real). Com o
        FakeController fica tudo desligado: `identity_registry` permanece
        None, nenhum `controllers.json` é lido/escrito e o reconcile do poll
        loop é no-op — testes/smoke herméticos por construção. Best-effort:
        falha aqui loga warning e o daemon segue (LEDs caem no broadcast
        histórico).
        """
        if not hasattr(self.controller, "set_auto_output_provider"):
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
                make_auto_output_provider,
            )

            registry = get_identity_registry()
            registry.load()
            self.identity_registry = registry
            self.controller.set_auto_output_provider(
                make_auto_output_provider(registry)
            )
            logger.info("identity_registry_wired")
        except Exception as exc:
            logger.warning("identity_registry_wire_failed", err=str(exc))

    def _sync_identity_registry(self) -> None:
        """Reconcilia o registro com os controles conectados (tick lento ~2s).

        COR-01 (D2): marca desconectados (slot vira RESERVA do MAC) e expira
        as reservas quando a sessão esvazia — por isso roda TAMBÉM offline
        (o gate de `is_connected` do poll loop não pode engolir a transição
        para zero controles). Fonte do conjunto: `describe_controllers` do
        backend (getattrs baratos, sem HID I/O) — nunca no caminho quente
        por evento. No-op sem registro (backend fake) ou sem a API.
        """
        registry = self.identity_registry
        if registry is None:
            return
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
            uniqs = {
                info["uniq"]
                for info in infos
                if isinstance(info, dict)
                and info.get("connected")
                and isinstance(info.get("uniq"), str)
            }
            registry.sync_connected(uniqs)
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("identity_sync_falhou", err=str(exc))

    # ------------------------------------------------------------------
    # Identidade + LED dos controles EXTERNOS (EXT-04)
    # ------------------------------------------------------------------

    def _wire_external_registry(self) -> None:
        """Cria o registro de externos + o aplicador de LED do tick lento.

        EXT-04: gate = `identity_registry` já fiado (backend real). Com o
        FakeController fica tudo None — nenhuma enumeração de /dev/input,
        nenhuma escrita de LED, nenhum controllers.json em teste/smoke.
        Best-effort: falha loga warning e o daemon segue (externos ficam sem
        número, como um kernel sem a regra udev 79).
        """
        if self.identity_registry is None:
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
                ExternalIdentityRegistry,
                ExternalLedSync,
            )

            registry = ExternalIdentityRegistry()
            registry.load()
            self.external_registry = registry
            self._external_led_sync = ExternalLedSync(self, registry)
            # EXT-04: numeração global ÚNICA — o registro dos DualSense passa a
            # pular os slots já reservados pelos externos ao numerar um
            # DualSense novo (evita duas frentes acenderem o mesmo "Controle
            # N" no co-op misto). Mão dupla do `reserve` que os externos já
            # leem do lado DualSense; ninguém renumera quem já tem slot.
            self.identity_registry.set_external_reserve_provider(
                lambda: set(registry.snapshot().values())
            )
            logger.info("external_registry_wired")
        except Exception as exc:
            logger.warning("external_registry_wire_failed", err=str(exc))

    def _schedule_external_tick(self) -> None:
        """Agenda o tick de LED dos externos como TASK auxiliar (HANG-01).

        Chamado pelo poll loop a cada ~2s; NUNCA aguarda o tick — antes disto
        o `await self._sync_external_leds()` inline suspendia o POLL LOOP
        INTEIRO para sempre se `sync.tick()` travasse no executor (mecanismo
        do incidente 19/07 16:08: zero read_state, zero logs, zero watchdog,
        por 10 minutos). Guard de reentrância: se a task anterior ainda não
        terminou, pula este ciclo (só conta — nunca empilha 2 ticks
        concorrentes brigando pelo mesmo `ExternalLedSync`).

        Degradado (2+ timeouts consecutivos em `_sync_external_leds`): fica
        mudo até o `InputDirWatch` observar uma mudança REAL em /dev/input —
        aí destrava e volta a agendar (o replug pode ter corrigido o que
        travou o worker, ou pelo menos justifica tentar de novo).
        """
        if self._external_led_sync is None:
            return
        if self._external_tick_degraded:
            watch = self._external_tick_watch
            if watch is None:
                from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

                watch = InputDirWatch()
                self._external_tick_watch = watch
                watch.poll()  # baseline — não destrava no MESMO tick que degradou
                return
            if not watch.poll():
                return
            logger.info("external_tick_recuperado", motivo="input_dir_change")
            self._external_tick_degraded = False
            self._external_tick_timeouts = 0
        task = self._external_tick_task
        if task is not None and not task.done():
            self._external_tick_skipped += 1
            return
        self._external_tick_task = asyncio.create_task(
            self._sync_external_leds(), name="external_led_tick"
        )

    async def _sync_external_leds(self) -> None:
        """Corpo da TASK do tick de LED dos externos (HANG-01).

        EXT-04 item 3: o `tick()` enumera /dev/input (10-40 ms) e escreve
        sysfs, então roda no executor DEDICADO (`_run_external_blocking`,
        pool `hefesto-ext`) — NUNCA no `self._executor` ("hefesto-hid") de
        que `read_state`/`_gather_game_signal_inputs`/o watchdog evdev
        dependem — sob `asyncio.wait_for`: a THREAD presa não é recuperável
        (é um wedge de baixo nível do CPython sob churn extremo de threads,
        não uma trava lógica nossa — trade-off aceito do projeto, mesmo
        espírito do `INIT_TIMEOUT_SEC` de `backend_pydualsense.py`: vaza o
        worker do pool `hefesto-ext`, isolado do pool que o poll loop usa
        pra ler o controle). Correção pós-auditoria: a versão anterior
        reusava `self._executor` — 2 timeouts consecutivos (possíveis pelo
        guard de reentrância, que só olha a task asyncio "done", não o
        worker) esgotavam os 2 workers do MESMO pool do `read_state`,
        reproduzindo o hang original de forma adiada. 1º timeout: WARNING;
        2º+ CONSECUTIVO: ERROR + degrada (`_schedule_external_tick` para de
        agendar até o próximo hotplug). Nunca propaga exceção para o
        chamador (`asyncio.create_task` — uma exceção aqui viraria
        "exception never retrieved" silencioso, então capturamos tudo).
        """
        sync = self._external_led_sync
        if sync is None:
            return
        try:
            await asyncio.wait_for(
                self._run_external_blocking(sync.tick),
                timeout=EXTERNAL_TICK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            self._external_tick_timeouts += 1
            log = (
                logger.warning
                if self._external_tick_timeouts == 1
                else logger.error
            )
            log(
                "external_tick_pendurado",
                timeout_sec=EXTERNAL_TICK_TIMEOUT_SEC,
                consecutivos=self._external_tick_timeouts,
            )
            if self._external_tick_timeouts >= EXTERNAL_TICK_MAX_TIMEOUTS:
                self._external_tick_degraded = True
                logger.info(
                    "external_tick_degradado",
                    consecutivos=self._external_tick_timeouts,
                    instrucao=(
                        "inventário de externos congelado até o próximo "
                        "hotplug em /dev/input; ver doctor/reiniciar o serviço"
                    ),
                )
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("external_led_sync_falhou", err=str(exc))
        else:
            self._external_tick_timeouts = 0

    # ------------------------------------------------------------------
    # Sinal "jogo real ativo" (NUMA-01)
    # ------------------------------------------------------------------

    @property
    def display_authority(self) -> str:
        """Autoridade de exibição CORRENTE ('game'|'daemon'|'unknown').

        NUMA-01 — contrato PÚBLICO explícito (síntese da Onda N: "sem
        `getattr` de privado no consumidor"). 'unknown' quando o
        `GameSignal` ainda não foi fiado (antes de `run()`, ou backend sem
        `set_game_authority_provider` — mesmo default fail-safe do sinal).
        """
        signal = self._game_signal
        return signal.authority if signal is not None else "unknown"

    def _wire_game_signal(self) -> None:
        """Cria o `GameSignal` (NUMA-01) e injeta a autoridade no backend real.

        Diferente de `_wire_identity_registry`/`_wire_external_registry`: o
        objeto `GameSignal` SEMPRE nasce (mesmo com FakeController) — é ele
        quem sustenta `display_authority`. Só a injeção no controller
        (`set_game_authority_provider`) é gateada por `hasattr` (padrão
        `set_auto_output_provider`, acima): sem o método, o backend fica
        byte-idêntico ao HEAD — fail-safe da síntese ("remover 1 linha
        desliga a onda inteira" — aqui seria remover a chamada abaixo).
        """
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal

        self._game_signal = GameSignal()
        if not hasattr(self.controller, "set_game_authority_provider"):
            return
        try:
            self.controller.set_game_authority_provider(
                lambda: self._game_signal.authority
            )
            logger.info("game_signal_wired")
        except Exception as exc:
            logger.warning("game_signal_wire_failed", err=str(exc))

    def _wire_feature_opener(self) -> None:
        """S-5: injeta o opener broker-aware no backend p/ a calibração 0x05.

        Gate por `hasattr` (FakeController não tem o setter → no-op, testes
        herméticos). `make_broker_opener` tenta o broker (fd root via
        SCM_RIGHTS, funciona com o nó ESCONDIDO) e cai no `os.open` por
        caminho quando o broker está ausente. Best-effort: falha aqui loga e
        o backend segue com `os.open` (comportamento histórico).
        """
        if not hasattr(self.controller, "set_feature_opener"):
            return
        try:
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                make_broker_opener,
            )

            self.controller.set_feature_opener(make_broker_opener(self))
            logger.info("feature_opener_wired")
        except Exception as exc:
            logger.warning("feature_opener_wire_failed", err=str(exc))

    def _any_game_session_open(self) -> bool:
        """Agregado `game_open` de TODOS os vpads (P1 + co-op, NUMA-01).

        Usado SÓ para modular a histerese da queda em `GameSignal.evaluate`
        — veto permanente honrado: sessão uhid JAMAIS alimenta `classify`
        (é o mecanismo do incidente 14:42: o cliente Steam também abre
        sessão). Espelha a varredura de vpads de `launch_env._snapshot`.
        """
        vpads: list[Any] = []
        primary = self._gamepad_device
        if primary is not None:
            vpads.append(primary)
        players = getattr(self._coop_manager, "_players", None)
        if isinstance(players, dict):
            for player in players.values():
                vpad = getattr(player, "vpad", None)
                if vpad is not None:
                    vpads.append(vpad)
        return any(bool(getattr(vpad, "game_open", False)) for vpad in vpads)

    def _profile_rule_matches_game(self, wm_class: str | None) -> bool:
        """NUMA-01 evidência #2: `wm_class` corrente casa regra de jogo do
        autoswitch (`mode.kind == "gamepad"`, match ESPECÍFICO — não o
        `MatchAny` catch-all do perfil fallback). Cobre GOG/Heroic fora da
        Steam pelo MESMO mecanismo de seleção do autoswitch
        (`ProfileManager.select_for_window`). Best-effort: qualquer falha
        ao carregar perfis do disco devolve False — o chamador
        (`_gather_game_signal_inputs`) já roda protegido por try/except no
        tick.
        """
        if not wm_class:
            return False
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        manager = ProfileManager(controller=self.controller)
        profile = manager.select_for_window({"wm_class": wm_class})
        if profile is None:
            return False
        mode = getattr(profile, "mode", None)
        match = getattr(profile, "match", None)
        return (
            mode is not None
            and getattr(mode, "kind", None) == "gamepad"
            and getattr(match, "type", None) == "criteria"
        )

    def _gather_game_signal_inputs(self) -> dict[str, Any]:
        """Reúne TODA evidência de `classify()` (NUMA-01) — roda no executor.

        O I/O de disco (marker do wrapper, perfis) e a sondagem de pid
        moram AQUI, nunca no provider injetado (que precisa ser leitura de
        bool cacheado, zero I/O — contrato de
        `backend_pydualsense.set_game_authority_provider`). Propaga
        qualquer exceção para o chamador (`_sync_game_signal`), que
        degrada para `unknown` (fail-safe).
        """
        from hefesto_dualsense4unix.daemon.launch_env import (
            pid_is_alive,
            read_last_exit_marker,
            read_last_exit_pid,
            read_last_run_marker,
            read_last_run_pid,
        )

        mono_now = time.monotonic()
        window_healthy = self.store.window_detect_healthy
        window_class_current = self.store.window_detect_current_class
        seen_at = self.store.game_window_seen_at
        window_seen_age = (mono_now - seen_at) if seen_at is not None else None
        marker = read_last_run_marker()
        marker_pid = read_last_run_pid()
        exit_marker = read_last_exit_marker()
        # Correção pós-auditoria da Onda N: `marker_pid`/`exit_pid` correlacionam
        # um `last_exit` (arquivo GLOBAL) ao MESMO launch do `last_run` corrente
        # — sem isso, o `last_exit` tardio de um launch concorrente que falhou o
        # próprio `exec` invalidaria um `last_run` legítimo e mais novo (ver
        # `wrapper_game_running`).
        exit_pid = read_last_exit_pid()
        marker_pid_alive = pid_is_alive(marker_pid)
        return {
            "window_healthy": window_healthy,
            "window_class_current": window_class_current,
            "window_seen_age": window_seen_age,
            "profile_rule_match": self._profile_rule_matches_game(window_class_current),
            "marker": marker,
            "marker_pid_alive": marker_pid_alive,
            "marker_pid": marker_pid,
            "exit_marker": exit_marker,
            "exit_pid": exit_pid,
            "session_open": self._any_game_session_open(),
            "now": time.time(),
        }

    async def _sync_game_signal(self) -> None:
        """Tick lento (~2s) do sinal "jogo real ativo" (NUMA-01).

        É esta fiação que ATIVA o gate NUMA-02/03 (dormente sem ela — os
        3684 testes da suíte REPLICA-03 passam byte-idênticos sem
        provider). Todo I/O mora em `_gather_game_signal_inputs` (roda no
        executor); a classificação em si (`classify` + histerese) é pura e
        barata, direto no event loop. Callbacks de transição são
        best-effort (`contextlib.suppress`) — falha de um passo não aborta
        o tick nem o outro callback.
        """
        signal = self._game_signal
        if signal is None:
            return
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify

        anterior = signal.authority
        try:
            inputs = await self._run_blocking(self._gather_game_signal_inputs)
        except Exception as exc:
            logger.warning("game_signal_degradado", motivo=str(exc))
            signal.mark_degraded(str(exc))
        else:
            raw = classify(**inputs)
            signal.evaluate(raw, session_open=bool(inputs["session_open"]))
        novo = signal.authority
        if novo == anterior:
            return
        if novo == "daemon":
            with contextlib.suppress(Exception):
                defend = getattr(self.controller, "defend_display", None)
                if callable(defend):
                    defend()
        elif anterior == "daemon":
            with contextlib.suppress(Exception):
                replay = getattr(self.controller, "replay_retained_game_outputs", None)
                if callable(replay):
                    replay()

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
        # COR-01: reconcilia o registro de identidade (slots de sessão) a cada
        # ~2s. ANTES do gate de conexão de propósito: é este reconcile que
        # observa a sessão ESVAZIAR (zero controles → reservas expiram, D2) —
        # depois do gate ele nunca rodaria desconectado. Custo por tick: uma
        # comparação de float; o describe (getattrs) só no tick lento.
        identity_sync_next_at: float = 0.0
        # EXT-04: LED dos EXTERNOS no tick lento do daemon (leitura IPC virou
        # pura). Também ANTES do gate de conexão: o 8BitDo/Pro Controller
        # merece número mesmo sem nenhum DualSense plugado. No-op sem fiação
        # (backend fake) — custo por tick: uma comparação de float.
        external_led_next_at: float = 0.0
        # NUMA-01: sinal "jogo real ativo" no MESMO tick lento (~2s), TAMBÉM
        # antes do gate de conexão — o marker do wrapper e a janela do jogo
        # independem do controle estar plugado neste instante.
        game_signal_next_at: float = 0.0
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager
        previous_buttons: frozenset[str] = frozenset()
        # BUG-DAEMON-CONNECT-GHOST-INPUT-01: rastreia a borda
        # desconectado→conectado. Começa False (boot pode ser sem hardware);
        # vira True na 1ª leitura bem-sucedida, quando armamos o grace.
        was_connected = False

        while not self._is_stopping():
            tick_started = loop.time()
            if tick_started >= identity_sync_next_at:
                identity_sync_next_at = tick_started + 2.0
                self._sync_identity_registry()
            if tick_started >= external_led_next_at:
                external_led_next_at = tick_started + 2.0
                # HANG-01: nunca mais `await` inline — só AGENDA a task (o
                # poll loop segue SEMPRE, mesmo se o tick anterior travar).
                self._schedule_external_tick()
            if tick_started >= game_signal_next_at:
                game_signal_next_at = tick_started + 2.0
                await self._sync_game_signal()
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
            # FEAT-NATIVE-MODE-01: o Modo Nativo congela o mesmo dispatch pelo
            # próprio flag (não via pause), então `daemon.resume` NÃO "des-solta"
            # o controle enquanto o Modo Nativo estiver ativo.
            input_ready = grace_passed and not self._paused and not self._native_mode
            if not input_ready:
                # FEAT-PARITY-REVIEW-01 (touchpad/nativo): enquanto o input está
                # congelado (Modo Nativo, pausa ou grace-period) ninguém drena o
                # touchpad. Sem isto o _accum_dx/dy do TouchpadReader cresce a
                # sessão inteira e vira um SALTO de cursor quando a emulação de
                # mouse volta (a saída do Nativo restaura o mouse do stash). Drena
                # a cada tick — no-op quando não há touchpad reader.
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
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

        # HANG-01: ao sair do poll loop (stop pedido ou erro fatal), não
        # deixa a task do tick de externos pendurada — best-effort (só pede
        # o cancelamento; ninguém aqui espera por ela, `shutdown()` já cancela
        # `_tasks` e derruba o executor).
        tick_task = self._external_tick_task
        if tick_task is not None and not tick_task.done():
            tick_task.cancel()

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

    async def _run_external_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Como `_run_blocking`, mas no pool DEDICADO `hefesto-ext` (HANG-01).

        Isola o tick de LED dos externos (`_sync_external_leds`) do pool
        `hefesto-hid` de que `read_state`/`_gather_game_signal_inputs`/o
        watchdog evdev dependem — um wedge aqui vaza no máximo o(s)
        worker(s) deste pool próprio, nunca aquele.
        """
        assert self._external_executor is not None, (
            "external executor não inicializado"
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._external_executor, fn, *args)

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
