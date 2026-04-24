"""DraftApplier — aplica `profile.apply_draft` em ordem canônica.

Extraído de `_handle_profile_apply_draft` em AUDIT-FINDING-IPC-SERVER-SPLIT-01.
Cada seção (leds, triggers, rumble, mouse) é aplicada de forma best-effort:
falha em uma seção loga warning mas não bloqueia as demais. A ordem é leds ->
triggers -> rumble -> mouse (leds primeiro por ser menos transiente
visualmente).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hefesto.core.trigger_effects import build_from_name
from hefesto.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.core.controller import IController
    from hefesto.daemon.state_store import StateStore

logger = get_logger(__name__)


class DraftApplier:
    """Aplica as 4 seções de `profile.apply_draft` em ordem canônica."""

    def __init__(
        self,
        controller: IController,
        store: StateStore,
        daemon: Any,
    ) -> None:
        self.controller = controller
        self.store = store
        self.daemon = daemon

    def apply(self, params: dict[str, Any]) -> list[str]:
        applied: list[str] = []
        self._apply_section(applied, params.get("leds"), "leds", self._apply_leds)
        self._apply_section(applied, params.get("triggers"), "triggers", self._apply_triggers)
        self._apply_section(applied, params.get("rumble"), "rumble", self._apply_rumble)
        self._apply_section(applied, params.get("mouse"), "mouse", self._apply_mouse)
        return applied

    @staticmethod
    def _apply_section(
        applied: list[str],
        raw: Any,
        section: str,
        fn: Any,
    ) -> None:
        if raw is None:
            return
        try:
            fn(raw)
            applied.append(section)
        except Exception as exc:
            logger.warning(f"apply_draft_{section}_falhou", erro=str(exc))

    def _apply_leds(self, leds_raw: Any) -> None:
        if not isinstance(leds_raw, dict):
            raise ValueError("leds deve ser objeto")
        rgb_raw = leds_raw.get("lightbar_rgb")
        brightness_raw = leds_raw.get("lightbar_brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError):
            brightness = 1.0
        brightness = max(0.0, min(1.0, brightness))
        if rgb_raw is not None:
            if not isinstance(rgb_raw, list) or len(rgb_raw) != 3:
                raise ValueError("leds.lightbar_rgb deve ser lista de 3 inteiros")
            r = max(0, min(255, int(rgb_raw[0] * brightness)))
            g = max(0, min(255, int(rgb_raw[1] * brightness)))
            b = max(0, min(255, int(rgb_raw[2] * brightness)))
            self.controller.set_led((r, g, b))
        player_leds_raw = leds_raw.get("player_leds")
        if player_leds_raw is not None:
            if not isinstance(player_leds_raw, list) or len(player_leds_raw) != 5:
                raise ValueError("leds.player_leds deve ser lista de 5 booleanos")
            bits: tuple[bool, bool, bool, bool, bool] = (
                bool(player_leds_raw[0]),
                bool(player_leds_raw[1]),
                bool(player_leds_raw[2]),
                bool(player_leds_raw[3]),
                bool(player_leds_raw[4]),
            )
            self.controller.set_player_leds(bits)

    def _apply_triggers(self, triggers_raw: Any) -> None:
        if not isinstance(triggers_raw, dict):
            raise ValueError("triggers deve ser objeto")
        for side in ("left", "right"):
            side_raw = triggers_raw.get(side)
            if side_raw is None:
                continue
            if not isinstance(side_raw, dict):
                raise ValueError(f"triggers.{side} deve ser objeto")
            mode = side_raw.get("mode")
            trigger_params = side_raw.get("params", [])
            if not isinstance(mode, str):
                raise ValueError(f"triggers.{side}.mode deve ser string")
            if not isinstance(trigger_params, list):
                raise ValueError(f"triggers.{side}.params deve ser lista")
            effect = build_from_name(mode, trigger_params)
            self.controller.set_trigger(side, effect)
        self.store.mark_manual_trigger_active()

    def _apply_rumble(self, rumble_raw: Any) -> None:
        if not isinstance(rumble_raw, dict):
            raise ValueError("rumble deve ser objeto")
        weak = rumble_raw.get("weak", 0)
        strong = rumble_raw.get("strong", 0)
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.weak e rumble.strong devem ser inteiros")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        # AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01:
        # Persiste valores brutos para que o poll loop (_reassert_rumble)
        # continue reaplicando a política a cada tick. Antes de enviar ao
        # hardware, escala via apply_rumble_policy — mesmo comportamento
        # canônico de _handle_rumble_set.
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)

    def _apply_mouse(self, mouse_raw: Any) -> None:
        if not isinstance(mouse_raw, dict):
            raise ValueError("mouse deve ser objeto")
        enabled = mouse_raw.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("mouse.enabled deve ser booleano")
        speed = mouse_raw.get("speed")
        scroll_speed = mouse_raw.get("scroll_speed")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")
        self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
        )


__all__ = ["DraftApplier"]
