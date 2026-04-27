"""Subsystem de poll loop — leitura de estado do controle e publicação de eventos.

Responsabilidades:
  - Ler estado do IController a cada 1/poll_hz segundos.
  - Publicar STATE_UPDATE, BATTERY_CHANGE, BUTTON_DOWN, BUTTON_UP no EventBus.
  - Chamar _reassert_rumble a cada 200ms.
  - Despachar eventos para mouse e hotkey_manager (via referência no Daemon).
  - Reconectar automaticamente em caso de falha de leitura.

Nota: este módulo implementa Subsystem mas também expõe BatteryDebouncer
e as constantes de debounce que são importadas por testes externos.
"""
from __future__ import annotations

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

BATTERY_DEBOUNCE_SEC = 5.0
BATTERY_MIN_INTERVAL_SEC = 0.1
BATTERY_DELTA_THRESHOLD_PCT = 1


class BatteryDebouncer:
    """Debounce de eventos de bateria (V2-17 + ADR-008).

    Dispara se:
      - nunca disparou (primeiro valor); ou
      - abs(delta_pct) >= BATTERY_DELTA_THRESHOLD_PCT (e respeita min interval); ou
      - elapsed_since_last_emit >= BATTERY_DEBOUNCE_SEC.

    Sempre respeita BATTERY_MIN_INTERVAL_SEC entre disparos consecutivos.
    """

    def __init__(self) -> None:
        self.last_emitted_value: int | None = None
        self.last_emit_at: float = 0.0

    def should_emit(self, value: int, now: float) -> bool:
        if self.last_emitted_value is None:
            return True
        interval = now - self.last_emit_at
        if interval < BATTERY_MIN_INTERVAL_SEC:
            return False
        delta = abs(value - self.last_emitted_value)
        return delta >= BATTERY_DELTA_THRESHOLD_PCT or interval >= BATTERY_DEBOUNCE_SEC

    def mark_emitted(self, value: int, now: float) -> None:
        self.last_emitted_value = value
        self.last_emit_at = now


def evdev_buttons_once(daemon: object) -> frozenset[str]:
    """Snapshot dos botões físicos via evdev — chamado 1x por tick no poll loop.

    Retorna frozenset vazio se evdev não está disponível ou falha.
    Exceções são logadas em debug para não poluir logs de produção.
    """
    evdev = getattr(getattr(daemon, "controller", None), "_evdev", None)
    if evdev is None or not evdev.is_available():
        return frozenset()
    try:
        return frozenset(evdev.snapshot().buttons_pressed)
    except Exception as exc:
        logger.debug("evdev_snapshot_falhou", err=str(exc))
        return frozenset()


class PollSubsystem:
    """Subsystem que encapsula o poll loop do daemon.

    Não executa o loop diretamente — ele é criado como asyncio.Task pelo Daemon
    e referenciado em daemon._tasks. A lógica de poll permanece em Daemon._poll_loop
    por compatibilidade com testes existentes que monkeypatching esse método.

    start() é chamado pelo Daemon.run() mas o loop real é iniciado via
    asyncio.create_task no Daemon. stop() é noop aqui (o loop para pelo stop_event).
    """

    name = "poll"

    async def start(self, ctx: object) -> None:
        """Noop: loop é criado como Task pelo Daemon."""
        logger.debug("poll_subsystem_start")

    async def stop(self) -> None:
        """Noop: loop para via stop_event do Daemon."""
        logger.debug("poll_subsystem_stop")

    def is_enabled(self, config: object) -> bool:
        return True


__all__ = [
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "BatteryDebouncer",
    "PollSubsystem",
    "evdev_buttons_once",
]
