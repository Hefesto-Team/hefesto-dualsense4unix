"""Aba Rumble: política global (Economia/Balanceado/Máximo/Auto) + Testar motores.

FEAT-RUMBLE-POLICY-01: aba reestruturada em 2 cards:
  1. "Política de rumble" — 4 GtkToggleButton agrupados + slider intensidade + label Auto.
  2. "Testar motores" — sliders weak/strong + botões Testar/Aplicar/Parar.

Política define multiplicador global aplicado pelo daemon sobre todo rumble,
inclusive passthrough de jogo (XInput virtual). Slider de intensidade ajusta
"custom" em 0-100%.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.ipc_bridge import (
    call_async,
    rumble_policy_custom,
    rumble_policy_set,
    rumble_set,
    rumble_stop,
)

# Mapeamento política -> mult canônico (para mover slider ao clicar preset).
_POLICY_MULT: dict[str, float] = {
    "economia": 0.3,
    "balanceado": 0.7,
    "max": 1.0,
    "auto": 1.0,  # Slider vai para 100% no auto (indicativo; não é custom).
}

_LABEL_AUTO = (
    "Modo Auto: ajusta intensidade conforme a bateria do controle.\n"
    "Bateria >50%: 100% (Máximo).  20-50%: 70% (Balanceado).  <20%: 30% (Economia).\n"
    "Transições com debounce de 5 segundos para evitar oscilação."
)


class RumbleActionsMixin(WidgetAccessMixin):
    """Controla a aba Rumble."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _guard_refresh: bool = False
    # Política corrente (espelhada localmente para guard de toggle).
    _rumble_policy: str = "balanceado"

    # --- instalação ---

    def install_rumble_tab(self) -> None:
        """Inicializa estado da aba Rumble a partir de state_full ou defaults.

        Configura o toggle ativo conforme política e atualiza slider.
        """
        self._sync_policy_from_state()

    def _sync_policy_from_state(self) -> None:
        """Lê política atual via state_full e sincroniza widgets."""
        def _on_state(result: Any) -> bool:
            if isinstance(result, dict):
                policy = result.get("rumble_policy", "balanceado")
                custom_mult = result.get("rumble_policy_custom_mult", 0.7)
            else:
                policy = "balanceado"
                custom_mult = 0.7
            self._apply_policy_to_widgets(str(policy), float(custom_mult))
            return False

        def _on_err(exc: Exception) -> bool:
            self._apply_policy_to_widgets("balanceado", 0.7)
            return False

        call_async("daemon.state_full", {}, on_success=_on_state, on_failure=_on_err)

    def _apply_policy_to_widgets(self, policy: str, custom_mult: float) -> None:
        """Reflete política e mult nos widgets sem disparar callbacks de sinal."""
        if self._guard_refresh:
            return
        self._guard_refresh = True
        self._rumble_policy = policy
        try:
            # Ativa o toggle correto.
            btn_id = {
                "economia": "rumble_policy_economia",
                "balanceado": "rumble_policy_balanceado",
                "max": "rumble_policy_max",
                "auto": "rumble_policy_auto",
                "custom": None,
            }.get(policy)

            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(pid == btn_id)

            # Slider de intensidade.
            slider: Gtk.Scale = self._get("rumble_policy_slider")
            if slider is not None:
                if policy == "custom":
                    slider.set_value(custom_mult * 100.0)
                elif policy in _POLICY_MULT:
                    slider.set_value(_POLICY_MULT[policy] * 100.0)

            # Label Auto: visível só em modo auto.
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(policy == "auto")
        finally:
            self._guard_refresh = False

    # --- handlers dos toggles de política ---

    def on_rumble_policy_economia(self, btn: Gtk.ToggleButton) -> None:
        if self._guard_refresh or not btn.get_active():
            return
        self._set_policy("economia")

    def on_rumble_policy_balanceado(self, btn: Gtk.ToggleButton) -> None:
        if self._guard_refresh or not btn.get_active():
            return
        self._set_policy("balanceado")

    def on_rumble_policy_max(self, btn: Gtk.ToggleButton) -> None:
        if self._guard_refresh or not btn.get_active():
            return
        self._set_policy("max")

    def on_rumble_policy_auto(self, btn: Gtk.ToggleButton) -> None:
        if self._guard_refresh or not btn.get_active():
            return
        self._set_policy("auto")

    def _set_policy(self, policy: str) -> None:
        """Envia política ao daemon e atualiza slider para valor canônico."""
        self._rumble_policy = policy
        # Mover slider para valor canônico do preset (feedback visual).
        slider: Gtk.Scale = self._get("rumble_policy_slider")
        if slider is not None:
            pct = int(_POLICY_MULT.get(policy, 0.7) * 100)
            self._guard_refresh = True
            try:
                slider.set_value(float(pct))
            finally:
                self._guard_refresh = False

        # Label Auto.
        lbl: Gtk.Label = self._get("rumble_policy_auto_label")
        if lbl is not None:
            lbl.set_visible(policy == "auto")

        ok = rumble_policy_set(policy)
        self._toast_rumble(
            f"Política de rumble: {policy}"
            if ok
            else "Falha ao alterar política (daemon offline?)"
        )

    # --- handler do slider de intensidade ---

    def on_rumble_policy_slider_changed(self, slider: Gtk.Scale) -> None:
        """Slider movido: política vira "custom" com mult = valor/100."""
        if self._guard_refresh:
            return
        mult = slider.get_value() / 100.0
        # Se o mult coincide exatamente com um preset, escolhê-lo.
        for policy, canon_mult in _POLICY_MULT.items():
            if policy == "auto":
                continue
            if abs(mult - canon_mult) < 0.005:
                if self._rumble_policy != policy:
                    self._guard_refresh = True
                    try:
                        self._activate_policy_toggle(policy)
                    finally:
                        self._guard_refresh = False
                    self._set_policy(policy)
                return

        # Mult não é preset: modo custom.
        self._guard_refresh = True
        try:
            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(False)
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(False)
        finally:
            self._guard_refresh = False

        self._rumble_policy = "custom"
        rumble_policy_custom(mult)

    def _activate_policy_toggle(self, policy: str) -> None:
        """Ativa o toggle correspondente à política (sem guard)."""
        btn_map = {
            "economia": "rumble_policy_economia",
            "balanceado": "rumble_policy_balanceado",
            "max": "rumble_policy_max",
            "auto": "rumble_policy_auto",
        }
        target_id = btn_map.get(policy)
        for pid in btn_map.values():
            btn: Gtk.ToggleButton = self._get(pid)
            if btn is not None:
                btn.set_active(pid == target_id)

    # --- handlers de teste de motores ---

    def on_rumble_apply(self, _btn: Gtk.Button) -> None:
        weak, strong = self._read_scales()
        # Persiste no draft antes de enviar via IPC.
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_rumble = draft.rumble.model_copy(update={"weak": weak, "strong": strong})
            self.draft = draft.model_copy(update={"rumble": new_rumble})
        ok = rumble_set(weak, strong)
        self._toast_rumble(
            f"Rumble aplicado: weak={weak}, strong={strong}"
            if ok
            else "Falha (daemon offline?)"
        )

    def on_rumble_test_500ms(self, _btn: Gtk.Button) -> None:
        weak, strong = self._read_scales()
        if weak == 0 and strong == 0:
            weak = 160
            strong = 220
            self._set_scales(weak, strong)
        ok = rumble_set(weak, strong)
        if not ok:
            self._toast_rumble("Falha (daemon offline?)")
            return
        self._toast_rumble(f"Testando por 500 ms (weak={weak}, strong={strong})")
        GLib.timeout_add(500, self._rumble_test_stop)

    def on_rumble_stop(self, _btn: Gtk.Button) -> None:
        """Para rumble via rumble.stop (BUG-RUMBLE-APPLY-IGNORED-01).

        Usa rumble_stop() em vez de rumble_set(0, 0) para que o daemon
        persista (0, 0) e o poll loop re-afirme silêncio continuamente,
        evitando que write HID residual reative os motores.
        """
        self._set_scales(0, 0)
        rumble_stop()
        self._toast_rumble("Rumble parado")

    # --- refresh do draft ---

    def _refresh_rumble_from_draft(self) -> None:
        """Popula widgets da aba Rumble a partir de self.draft.rumble e state_full.

        Protegido por _guard_refresh para não disparar handlers de sinal
        durante a atualização programática dos sliders.
        """
        if self._guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._guard_refresh = True
        try:
            rumble = draft.rumble
            weak_scale: Gtk.Scale = self._get("rumble_weak_scale")
            strong_scale: Gtk.Scale = self._get("rumble_strong_scale")
            if weak_scale is not None:
                weak_scale.set_value(float(rumble.weak))
            if strong_scale is not None:
                strong_scale.set_value(float(rumble.strong))
        finally:
            self._guard_refresh = False
        # Sincroniza política do daemon (async — não bloqueia GTK).
        self._sync_policy_from_state()

    # --- helpers ---

    def _read_scales(self) -> tuple[int, int]:
        weak = int(self._get("rumble_weak_scale").get_value())
        strong = int(self._get("rumble_strong_scale").get_value())
        return weak, strong

    def _set_scales(self, weak: int, strong: int) -> None:
        self._get("rumble_weak_scale").set_value(weak)
        self._get("rumble_strong_scale").set_value(strong)

    def _rumble_test_stop(self) -> bool:
        # Teste de 500ms encerrado: para via rumble_stop para garantir persistência do zero.
        rumble_stop()
        self._set_scales(0, 0)
        self._toast_rumble("Teste encerrado (motores zerados)")
        return False

    def _toast_rumble(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("rumble")
        bar.push(ctx_id, msg)
