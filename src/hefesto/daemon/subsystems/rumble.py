"""Subsystem Rumble — re-asserção periódica de vibração com política de intensidade.

Responsabilidades:
  - Re-aplicar rumble_active no hardware a cada ~200ms.
  - Delegar cálculo de multiplicador para `hefesto.core.rumble._effective_mult`
    (fonte canônica única — AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01).

O estado de debounce da política "auto" (_last_auto_mult, _last_auto_change_at)
é mantido diretamente no objeto Daemon por compatibilidade com testes existentes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.daemon.context import DaemonContext

logger = get_logger(__name__)

# FEAT-RUMBLE-POLICY-01
AUTO_DEBOUNCE_SEC = 5.0
RUMBLE_POLICY_MULT: dict[str, float] = {
    "economia": 0.3,
    "balanceado": 0.7,
    "max": 1.0,
}


def reassert_rumble(daemon: Any, now: float) -> None:
    """Re-aplica rumble_active no hardware a cada ~200ms com política.

    Idempotente. Necessário porque writes HID de LED/trigger podem zerar os
    motores de vibração involuntariamente. A re-asserção a 5Hz (200ms) garante
    que o valor fixado pelo usuário persista mesmo com outras escritas HID.

    Pula silenciosamente se:
    - rumble_active is None (passthrough — jogo/UDP controla).
    - Controle não está conectado.
    """
    # Import local: core/rumble.py -> daemon/lifecycle.py (TYPE_CHECKING) ->
    # daemon/subsystems/rumble.py. Import no topo criaria ciclo em runtime.
    from hefesto.core.rumble import _effective_mult

    cfg = daemon.config
    active = cfg.rumble_active
    if active is None:
        return
    weak_raw, strong_raw = active

    battery_pct = 50  # fallback neutro
    try:
        snap = daemon.store.snapshot()
        ctrl = snap.controller
        if ctrl is not None and ctrl.battery_pct is not None:
            battery_pct = int(ctrl.battery_pct)
    except Exception:
        pass

    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult(
        config=cfg,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    weak = max(0, min(255, round(weak_raw * mult)))
    strong = max(0, min(255, round(strong_raw * mult)))

    try:
        daemon.controller.set_rumble(weak=weak, strong=strong)
    except Exception as exc:
        logger.warning("rumble_reassert_failed", err=str(exc))


class RumbleSubsystem:
    """Subsystem sentinela para o registry — lógica real está em reassert_rumble().

    A re-asserção periódica de rumble é integrada diretamente no poll loop
    do Daemon por requisitos de timing (a cada 200ms dentro do tick). Este
    subsystem existe para completar o registry e servir como ponto de extensão
    para futuras políticas de rumble desacopladas do poll loop.
    """

    name = "rumble"

    async def start(self, ctx: DaemonContext) -> None:
        """Noop: re-asserção é integrada ao poll loop."""
        logger.debug("rumble_subsystem_start")

    async def stop(self) -> None:
        """Noop: não há recurso externo para liberar."""
        logger.debug("rumble_subsystem_stop")

    def is_enabled(self, config: Any) -> bool:
        return True


__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "RUMBLE_POLICY_MULT",
    "RumbleSubsystem",
    "reassert_rumble",
]
