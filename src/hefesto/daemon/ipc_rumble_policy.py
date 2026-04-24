"""Aplicação da política global de rumble sobre pares (weak, strong).

Extraído de `ipc_server.py` em AUDIT-FINDING-IPC-SERVER-SPLIT-01 para reduzir
acoplamento entre o dispatcher JSON-RPC e a lógica de multiplicador+debounce.
Depende de `RumbleEngine.update_auto_state` (encapsulado em
AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01) para propagar o debounce de volta ao
motor sem tocar campos privados.
"""
from __future__ import annotations

import time as _time
from typing import Any


def apply_rumble_policy(daemon: Any, weak: int, strong: int) -> tuple[int, int]:
    """Aplica multiplicador de política de rumble sobre (weak, strong).

    Consulta config do daemon e o RumbleEngine (para debounce do auto).
    Se daemon ausente ou sem config, retorna valores sem alteração.
    """
    daemon_cfg = getattr(daemon, "config", None) if daemon else None
    if daemon_cfg is None:
        return weak, strong

    from hefesto.core.rumble import _effective_mult
    from hefesto.daemon.lifecycle import AUTO_DEBOUNCE_SEC

    # Bateria do estado mais recente (via store se disponível).
    battery_pct = 50
    store = getattr(daemon, "store", None)
    if store is not None:
        try:
            snap = store.snapshot()
            ctrl = snap.controller
            if ctrl is not None and ctrl.battery_pct is not None:
                battery_pct = int(ctrl.battery_pct)
        except Exception:
            pass

    # Debounce auto: lê do RumbleEngine se existir.
    rumble_engine = getattr(daemon, "_rumble_engine", None)
    last_auto_mult = getattr(rumble_engine, "_last_auto_mult", 0.7) if rumble_engine else 0.7
    last_auto_change_at = (
        getattr(rumble_engine, "_last_auto_change_at", 0.0) if rumble_engine else 0.0
    )

    mult, new_last_auto_mult, new_last_auto_change_at = _effective_mult(
        config=daemon_cfg,
        battery_pct=battery_pct,
        now=_time.monotonic(),
        last_auto_mult=last_auto_mult,
        last_auto_change_at=last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )

    # Propaga debounce de volta ao engine via método público (encapsulamento).
    # AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01: writeback antes tocava campos
    # privados diretamente; agora via RumbleEngine.update_auto_state().
    if rumble_engine is not None:
        rumble_engine.update_auto_state(
            new_last_auto_mult,
            new_last_auto_change_at,
            mult_applied=mult,
        )

    eff_weak = max(0, min(255, round(weak * mult)))
    eff_strong = max(0, min(255, round(strong * mult)))
    return eff_weak, eff_strong


# Alias mantido por compat interna — chamadas legadas via `_apply_rumble_policy`
# continuam resolvendo. Código novo deve usar `apply_rumble_policy` (sem prefixo
# underscore) visto que a função é exportada a partir deste módulo.
_apply_rumble_policy = apply_rumble_policy


__all__ = ["_apply_rumble_policy", "apply_rumble_policy"]
