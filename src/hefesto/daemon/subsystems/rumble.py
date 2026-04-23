"""Subsystem Rumble — re-asserção periódica de vibração com política de intensidade.

Responsabilidades:
  - Calcular o multiplicador de política (economia/balanceado/max/auto/custom).
  - Re-aplicar rumble_active no hardware a cada ~200ms.
  - Expor _effective_mult_inline para uso pelo Daemon e por testes.

O estado de debounce da política "auto" (_last_auto_mult, _last_auto_change_at)
é mantido diretamente no objeto Daemon por compatibilidade com testes existentes.

ATENÇÃO: _effective_mult_inline é reexportada por lifecycle.py para
preservar backcompat com test_rumble_policy.py que importa diretamente de lá.
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


def _effective_mult_inline(
    config: Any,
    battery_pct: int,
    now: float,
    last_auto_mult: float,
    last_auto_change_at: float,
) -> tuple[float, float, float]:
    """Calcula multiplicador de política inline (sem importar core/rumble.py).

    Retorna (mult, novo_last_auto_mult, novo_last_auto_change_at).
    Chamado por _reassert_rumble no Daemon para aplicar política sem
    importação circular.
    """
    policy = config.rumble_policy

    if policy in RUMBLE_POLICY_MULT:
        return RUMBLE_POLICY_MULT[policy], last_auto_mult, last_auto_change_at

    if policy == "custom":
        mult = float(config.rumble_policy_custom_mult)
        return mult, last_auto_mult, last_auto_change_at

    if policy == "auto":
        if battery_pct > 50:
            target = 1.0
        elif battery_pct >= 20:
            target = 0.7
        else:
            target = 0.3

        if target != last_auto_mult:
            elapsed = now - last_auto_change_at
            if elapsed >= AUTO_DEBOUNCE_SEC or last_auto_change_at == 0.0:
                logger.info(
                    "rumble_auto_policy_change",
                    mult=target,
                    battery_pct=battery_pct,
                )
                return target, target, now
            return last_auto_mult, last_auto_mult, last_auto_change_at

        return last_auto_mult, last_auto_mult, last_auto_change_at

    # Fallback: balanceado.
    return 0.7, last_auto_mult, last_auto_change_at


def reassert_rumble(daemon: Any, now: float) -> None:
    """Re-aplica rumble_active no hardware a cada ~200ms com política.

    Idempotente. Necessário porque writes HID de LED/trigger podem zerar os
    motores de vibração involuntariamente. A re-asserção a 5Hz (200ms) garante
    que o valor fixado pelo usuário persista mesmo com outras escritas HID.

    Pula silenciosamente se:
    - rumble_active is None (passthrough — jogo/UDP controla).
    - Controle não está conectado.
    """
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

    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult_inline(
        config=cfg,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
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
    "_effective_mult_inline",
    "reassert_rumble",
]
