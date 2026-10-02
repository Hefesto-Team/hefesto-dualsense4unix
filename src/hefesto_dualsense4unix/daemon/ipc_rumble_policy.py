"""Aplicação da política global de rumble sobre pares (weak, strong)."""
from __future__ import annotations

import time as _time
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def memoria_viva_do_auto(daemon: Any) -> tuple[float, float]:
    """O estado de debounce do "auto" que vale AGORA: (mult, instante)."""
    mult = getattr(daemon, "_last_auto_mult", None)
    quando = getattr(daemon, "_last_auto_change_at", None)
    if isinstance(mult, bool) or not isinstance(mult, (int, float)):
        mult = 0.7
    if isinstance(quando, bool) or not isinstance(quando, (int, float)):
        quando = 0.0
    return float(mult), float(quando)


def apply_rumble_policy(daemon: Any, weak: int, strong: int) -> tuple[int, int]:
    """Aplica multiplicador de política de rumble sobre (weak, strong)."""
    daemon_cfg = getattr(daemon, "config", None) if daemon else None
    if daemon_cfg is None:
        return weak, strong

    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.lifecycle import AUTO_DEBOUNCE_SEC

    battery_pct = 50
    store = getattr(daemon, "store", None)
    if store is not None:
        try:
            snap = store.snapshot()
            ctrl = snap.controller
            if ctrl is not None and ctrl.battery_pct is not None:
                battery_pct = int(ctrl.battery_pct)
        except Exception:
            logger.debug("rumble_policy_state_read_fallback", exc_info=True)

    last_auto_mult, last_auto_change_at = memoria_viva_do_auto(daemon)

    mult, new_last_auto_mult, new_last_auto_change_at = _effective_mult(
        config=daemon_cfg,
        battery_pct=battery_pct,
        now=_time.monotonic(),
        last_auto_mult=last_auto_mult,
        last_auto_change_at=last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )

    # é também a fonte da observabilidade: é dele que `state_full` tira o
    daemon._last_auto_mult = new_last_auto_mult
    daemon._last_auto_change_at = new_last_auto_change_at

    eff_weak = max(0, min(255, round(weak * mult)))
    eff_strong = max(0, min(255, round(strong * mult)))
    return eff_weak, eff_strong


def uniq_do_alvo_de_output(controller: Any) -> str | None:
    """MAC do alvo de output NESTE instante, ou None para "a mesa inteira"."""
    getter = getattr(controller, "get_output_target_uniq", None)
    if not callable(getter):
        return None
    try:
        alvo = getter()
    except Exception:
        logger.debug("output_target_uniq_indisponivel", exc_info=True)
        return None
    return alvo if isinstance(alvo, str) and alvo else None


_apply_rumble_policy = apply_rumble_policy


__all__ = [
    "_apply_rumble_policy",
    "apply_rumble_policy",
    "memoria_viva_do_auto",
    "uniq_do_alvo_de_output",
]
