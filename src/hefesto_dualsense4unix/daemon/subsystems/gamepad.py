"""Subsystem Gamepad — gamepad virtual (DualSense/Xbox).

FEAT-DSX-GAMEPAD-FLAVOR-01. Integra o bridge — antes um processo CLI avulso
(`emulate xbox360`) que abria um SEGUNDO leitor do mesmo controle e causava
input duplicado/perdido — ao daemon como subsystem. Agora há UM leitor evdev
(o do daemon) que faz fan-out para mouse/teclado/gamepad.

Política:
  - **Mutuamente exclusivo com a emulação de mouse**: ligar o gamepad desliga o
    mouse (jogar = o controle vai pro jogo, não pro cursor do desktop). O poll
    loop, quando o gamepad está ativo, NÃO despacha mouse/teclado.
  - **Máscara (flavor)**: `dualsense` (prompts PlayStation) ou `xbox` (fallback
    p/ jogos XInput-only). Quem escolhe o BACKEND por trás da máscara (uhid ou
    uinput) é `integrations/virtual_pad.make_virtual_pad`, com o fallback e o
    motivo logado num lugar só — este subsystem não sabe em qual está.
  - **Grab do controle físico** (best-effort): enquanto o gamepad virtual está
    ativo, o daemon faz EVIOCGRAB no evdev do controle real para o jogo enxergar
    SÓ o device virtual (senão veria o controle cru + o virtual = input dobrado,
    BUG-DSX-GAMEPAD-DOUBLE-INPUT-01). Liberado ao desligar.
  - **Persistência**: liga/desliga + flavor sobrevivem a restart/reboot via
    `utils.session` (igual ao mouse).
  - **Force-feedback do jogo** (FEAT-VPAD-FF-PASSTHROUGH-01): o vpad do P1
    nasce com um `rumble_sink` que devolve o rumble pedido pelo JOGO ao
    controle físico PRIMÁRIO, passando pela mesma política global de
    intensidade do reassert. `dispatch_gamepad` bombeia o FF a cada tick.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

logger = get_logger(__name__)


class GamepadSubsystem:
    """Subsystem que gerencia o gamepad virtual. Espelha MouseSubsystem."""

    name = "gamepad"

    async def start(self, ctx: Any) -> None:
        """Cria o device virtual se gamepad_emulation_enabled=True.

        Idempotente: retorna sem erro se já existe. Lê o flavor da config.
        """
        cfg = ctx.config
        if not getattr(cfg, "gamepad_emulation_enabled", False):
            return
        daemon = getattr(ctx, "daemon", ctx)
        start_gamepad_emulation(daemon, flavor=getattr(cfg, "gamepad_flavor", None))

    async def stop(self) -> None:  # pragma: no cover - simetria de protocolo
        # O teardown real fica a cargo de stop_gamepad_emulation no shutdown do
        # daemon (que tem a referência ao device). Aqui é no-op seguro.
        return

    def is_enabled(self, config: DaemonConfig) -> bool:
        return bool(getattr(config, "gamepad_emulation_enabled", False))


def _set_controller_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Grab/ungrab do evdev do controle físico, com resultado OBSERVÁVEL.

    Sem isso, o jogo veria o controle cru (js0) + o virtual = input dobrado. O
    grab faz o daemon ser o leitor exclusivo do evdev real (ele já é o leitor),
    escondendo o controle cru dos clientes evdev (SDL2). Nunca propaga exceção:
    em FAKE mode / sem device / sem suporte, o gamepad ainda funciona. Falha de
    EVIOCGRAB deixa de ser silenciosa (BUG-COOP-GRAB-SILENT-FAIL-01): loga
    warning e conta no store — a GUI/doctor podem apontar "input dobrado".
    """
    controller = getattr(daemon, "controller", None)
    evdev = getattr(controller, "_evdev", None)
    setter = getattr(evdev, "set_grab", None)
    if setter is None:
        return
    with contextlib.suppress(Exception):
        ok = setter(grab)
        state = getattr(evdev, "grab_state", None)
        logger.info("gamepad_controller_grab", grab=grab, ok=ok, state=state)
        if grab and ok is False:
            store = getattr(daemon, "store", None)
            if store is not None:
                with contextlib.suppress(Exception):
                    store.bump("gamepad.grab.failed")


def _game_rumble_mult(daemon: DaemonProtocol, now: float) -> float:
    """Multiplicador da política global de rumble para o rumble do JOGO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o FF do vpad passa pela MESMA política
    (economia/balanceado/max/auto/custom) do slider "Intensidade global" —
    espelho fiel de `subsystems.rumble.reassert_rumble` (bateria do snapshot
    do store + `_effective_mult` com o estado de debounce compartilhado do
    daemon). Duplicado aqui de propósito: o reassert é do caminho do rumble
    FIXADO e este é do rumble do jogo; a fonte canônica do cálculo segue
    sendo `core.rumble._effective_mult`.
    """
    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.subsystems.rumble import AUTO_DEBOUNCE_SEC

    battery_pct = 50  # fallback neutro (igual ao reassert)
    try:
        ctrl = daemon.store.snapshot().controller
        if ctrl is not None and ctrl.battery_pct is not None:
            battery_pct = int(ctrl.battery_pct)
    except Exception:
        logger.debug("game_rumble_state_read_fallback", exc_info=True)
    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult(
        config=daemon.config,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    return mult


def _resolve_output_index(controller: Any, uniq: str) -> int | None:
    """Posição do controle de MAC `uniq` em `describe_controllers`, ou None.

    É o mesmo índice que `set_output_target` espera
    (FEAT-DSX-CONTROLLER-SELECTOR-01). None = backend sem introspecção
    (ex.: FakeController) ou controle não encontrado.
    """
    describe = getattr(controller, "describe_controllers", None)
    if not callable(describe):
        return None
    try:
        for entry in describe():
            if entry.get("uniq") == uniq:
                index = entry.get("index")
                return index if isinstance(index, int) else None
    except Exception:
        logger.debug("game_rumble_describe_failed", exc_info=True)
    return None


def apply_game_rumble(
    daemon: DaemonProtocol,
    weak: int,
    strong: int,
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no controle FÍSICO o rumble vindo do jogo (FF do vpad).

    FEAT-VPAD-FF-PASSTHROUGH-01. Decisões (documentadas):
      - `rumble_active` FIXADO manual VENCE: com rumble fixado (usuária
        testando os motores pela GUI), o FF do jogo é IGNORADO — o reassert
        de 200ms manteria o valor fixado de qualquer forma; ignorar evita
        briga de escrita HID. Em passthrough (`rumble_active is None`) o
        reassert é no-op e o FF do jogo manda sozinho.
      - A política global de intensidade é aplicada AQUI (mesmo multiplicador
        do reassert) — o slider vale também para o rumble do jogo.
      - `target_uniq` (MAC) mira o controle de UM jogador via o seletor
        público do backend (`set_output_target` por índice, resolvido por
        `describe_controllers`), salvando e restaurando o alvo anterior. O
        bloco todo é síncrono (sem await), então nenhuma outra task do event
        loop intercala um output no alvo trocado. Sem targeting público
        (ex.: FakeController) ou sem MAC, cai no broadcast histórico —
        limitação documentada: TODOS os controles vibram juntos.
    """
    if daemon.config.rumble_active is not None:
        return  # rumble fixado manual vence o FF do jogo
    controller = daemon.controller
    mult = _game_rumble_mult(daemon, time.monotonic())
    weak_eff = max(0, min(255, round(weak * mult)))
    strong_eff = max(0, min(255, round(strong * mult)))

    # Any: métodos de targeting são opcionais no backend (só o PyDualSense os
    # tem; IController/FakeController não) — o gate é o callable() abaixo.
    set_target: Any = getattr(controller, "set_output_target", None)
    get_target: Any = getattr(controller, "get_output_target_index", None)
    index: int | None = None
    if target_uniq is not None and callable(set_target) and callable(get_target):
        index = _resolve_output_index(controller, target_uniq)
    if index is None:
        try:
            controller.set_rumble(weak=weak_eff, strong=strong_eff)
        except Exception as exc:
            logger.warning("game_rumble_failed", err=str(exc))
        return
    previous: int | None = None
    try:
        previous = get_target()
        set_target(index)
        controller.set_rumble(weak=weak_eff, strong=strong_eff)
    except Exception as exc:
        logger.warning("game_rumble_target_failed", err=str(exc), target=target_uniq)
    finally:
        # Restaura o alvo anterior mesmo em falha (o seletor da usuária não
        # pode ficar sequestrado pelo rumble de um jogador).
        with contextlib.suppress(Exception):
            set_target(previous)


def resolve_hidraw_path(daemon: DaemonProtocol, uniq: str | None) -> str | None:
    """Nó hidraw do controle `uniq` (None = primário), ou None se indisponível.

    SPRINT-UHID-VPAD-01: é o que o backend uhid precisa para copiar o blueprint
    do controle físico. `hidraw_path` só existe no backend pydualsense (o
    FakeController e o IController não têm) — sem ele, o vpad simplesmente nasce
    no uinput, que é o comportamento de hoje.
    """
    getter = getattr(daemon.controller, "hidraw_path", None)
    if not callable(getter):
        return None
    try:
        path = getter(uniq)
    except Exception as exc:
        logger.debug("hidraw_path_falhou", err=str(exc), uniq=uniq)
        return None
    return path if isinstance(path, str) else None


def make_primary_rumble_sink(daemon: DaemonProtocol) -> Callable[[int, int], None]:
    """Sink de FF do vpad do P1 → rumble físico do controle PRIMÁRIO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o MAC do primário é resolvido NA HORA do
    rumble (`primary_uniq` muda em hotplug); com o co-op ativo isso garante
    que o rumble do P1 não sacode o controle dos outros jogadores. Backend
    sem `primary_uniq` (ex.: FakeController) cai em broadcast.
    """

    def _sink(weak: int, strong: int) -> None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        apply_game_rumble(
            daemon,
            weak,
            strong,
            target_uniq=uniq if isinstance(uniq, str) and uniq else None,
        )

    return _sink


def start_gamepad_emulation(daemon: DaemonProtocol, flavor: str | None = None) -> bool:
    """Cria o gamepad virtual com a máscara `flavor`. Idempotente.

    Desliga a emulação de mouse (mútua exclusão) e faz grab do controle real.
    Retorna True se ativo ao final; False se falhou ao iniciar.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
    from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

    key = normalize_flavor(
        flavor if flavor is not None else getattr(daemon.config, "gamepad_flavor", None)
    )

    existing = daemon._gamepad_device
    if existing is not None:
        if getattr(existing, "flavor", None) == key:
            return True
        # Flavor mudou: recria sem repersistir/regrab intermediário.
        stop_gamepad_emulation(daemon, persist=False, release_grab=False)

    # Mútua exclusão: o controle vai pro jogo, não pro cursor.
    if getattr(daemon, "_mouse_device", None) is not None:
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(daemon)

    # FEAT-VPAD-FF-PASSTHROUGH-01: o rumble que o JOGO pedir no vpad volta
    # para os motores do controle físico primário.
    # SPRINT-UHID-VPAD-01: a factory prefere o backend uhid (DualSense com hidraw
    # de verdade = vibração in-game na máscara DualSense) e cai no uinput sozinha
    # quando o uhid não sobe; o P1 é sempre o jogador 1.
    # Limitação conhecida: o backend é escolhido AQUI, uma vez. Ligar o gamepad
    # com o controle desconectado não tem hidraw de onde copiar o blueprint, e o
    # P1 fica no uinput até alguém religar a emulação (o `set_gamepad_emulation`
    # recria o vpad). Plugar o controle depois não promove o vpad sozinho.
    device: VirtualPad | None = make_virtual_pad(
        key,
        rumble_sink=make_primary_rumble_sink(daemon),
        player=1,
        hidraw_path=resolve_hidraw_path(daemon, None),
    )
    if device is None:
        logger.warning("gamepad_emulation_start_failed", flavor=key)
        return False

    daemon._gamepad_device = device
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = key
    _set_controller_grab(daemon, True)
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

        save_gamepad_emulation(True, key)
    logger.info("gamepad_emulation_started", flavor=key)
    return True


def stop_gamepad_emulation(
    daemon: DaemonProtocol, *, persist: bool = True, release_grab: bool = True
) -> None:
    """Para e descarta o gamepad virtual. Idempotente.

    `persist=False` e `release_grab=False` são usados na troca de flavor (a
    recriação imediata reaplica ambos).
    """
    if daemon._gamepad_device is None:
        # Garante config/flag coerentes mesmo sem device (ex.: falha no start).
        daemon.config.gamepad_emulation_enabled = False
        if release_grab:
            _set_controller_grab(daemon, False)
        if persist:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

                save_gamepad_emulation(False)
        return
    with contextlib.suppress(Exception):
        daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False
    if release_grab:
        _set_controller_grab(daemon, False)
    if persist:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

            save_gamepad_emulation(False)
    logger.info("gamepad_emulation_stopped")


def dispatch_gamepad(
    daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]
) -> None:
    """Repassa o estado do controle ao gamepad virtual.

    Chamado pelo poll loop a cada tick quando _gamepad_device != None.
    Não relança exceções — falhas viram warning.
    """
    device = daemon._gamepad_device
    if device is None:
        return
    try:
        device.forward_analog(
            lx=state.raw_lx,
            ly=state.raw_ly,
            rx=state.raw_rx,
            ry=state.raw_ry,
            l2=state.l2_raw,
            r2=state.r2_raw,
        )
        device.forward_buttons(buttons_pressed)
        # FEAT-VPAD-FF-PASSTHROUGH-01: drena o FF (rumble do jogo) do vpad e
        # repassa ao controle físico. getattr defensivo: fakes/devices sem
        # pump_ff degradam sem crash.
        pump = getattr(device, "pump_ff", None)
        if pump is not None:
            pump()
    except Exception as exc:
        logger.warning("gamepad_dispatch_failed", err=str(exc))


__all__ = [
    "GamepadSubsystem",
    "apply_game_rumble",
    "dispatch_gamepad",
    "make_primary_rumble_sink",
    "start_gamepad_emulation",
    "stop_gamepad_emulation",
]
