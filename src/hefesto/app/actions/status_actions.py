"""Aba Status: polling ao vivo de daemon.state_full + update dos widgets."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from hefesto.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    STATE_POLL_INTERVAL_MS,
)
from hefesto.app.ipc_bridge import daemon_state_full


class StatusActionsMixin:
    """Atualiza a aba Status em tempo real.

    Assume que `self.builder` contém os widgets do `main.glade`:
        status_connection, status_transport, status_battery_bar,
        status_active_profile, status_daemon,
        live_l2_bar, live_r2_bar, live_lx_label, live_ly_label,
        live_rx_label, live_ry_label, live_buttons_label,
        header_connection.
    """

    def install_status_polling(self) -> None:
        """Liga os 2 timers da aba Status. Chamado uma vez no on_mount."""
        GLib.timeout_add(LIVE_POLL_INTERVAL_MS, self._tick_live_state)
        GLib.timeout_add(STATE_POLL_INTERVAL_MS, self._tick_profile_state)

    def _tick_live_state(self) -> bool:
        """Roda a ~20 Hz: atualiza gatilhos, sticks, botões."""
        state = daemon_state_full()
        if state is None:
            self._render_offline()
            return True  # mantém o timer vivo

        self._render_live_state(state)
        return True

    def _tick_profile_state(self) -> bool:
        """Roda a 2 Hz: perfil ativo + metadata que muda devagar."""
        state = daemon_state_full()
        if state is None:
            return True
        self._render_slow_state(state)
        return True

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        header.set_markup(
            '<span foreground="#d33">○ daemon offline</span>'
        )
        self._set_label("status_daemon", "offline")
        self._set_label("status_connection", "—")
        self._set_label("status_transport", "—")
        self._set_label("status_active_profile", "—")
        self._get("status_battery_bar").set_fraction(0.0)
        self._get("status_battery_bar").set_text("— %")
        self._reset_live_widgets()

    def _render_live_state(self, state: dict[str, Any]) -> None:
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        header = self._get("header_connection")
        if connected:
            header.set_markup(
                f'<span foreground="#2d8">● conectado via {transport}</span>'
            )
        else:
            header.set_markup(
                '<span foreground="#d33">○ controle desconectado</span>'
            )

        l2 = int(state.get("l2_raw", 0))
        r2 = int(state.get("r2_raw", 0))
        l2_bar = self._get("live_l2_bar")
        r2_bar = self._get("live_r2_bar")
        l2_bar.set_fraction(l2 / 255)
        l2_bar.set_text(f"{l2} / 255")
        r2_bar.set_fraction(r2 / 255)
        r2_bar.set_text(f"{r2} / 255")

        self._set_label("live_lx_label", str(state.get("lx", 128)))
        self._set_label("live_ly_label", str(state.get("ly", 128)))
        self._set_label("live_rx_label", str(state.get("rx", 128)))
        self._set_label("live_ry_label", str(state.get("ry", 128)))

        buttons = state.get("buttons", [])
        buttons_markup = (
            ", ".join(f"<b>{b}</b>" for b in buttons)
            if buttons
            else "<i>nenhum</i>"
        )
        self._get("live_buttons_label").set_markup(buttons_markup)

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "nenhum"

        self._set_label(
            "status_connection", "conectado" if connected else "desconectado"
        )
        self._set_label("status_transport", transport)
        self._set_label("status_active_profile", active_profile)
        self._set_label("status_daemon", "online")

        battery_bar = self._get("status_battery_bar")
        if battery is None:
            battery_bar.set_fraction(0.0)
            battery_bar.set_text("— %")
        else:
            battery_bar.set_fraction(battery / 100)
            battery_bar.set_text(f"{battery} %")

    def _reset_live_widgets(self) -> None:
        self._get("live_l2_bar").set_fraction(0.0)
        self._get("live_l2_bar").set_text("0 / 255")
        self._get("live_r2_bar").set_fraction(0.0)
        self._get("live_r2_bar").set_text("0 / 255")
        for wid in ("live_lx_label", "live_ly_label",
                    "live_rx_label", "live_ry_label"):
            self._set_label(wid, "128")
        self._get("live_buttons_label").set_markup("<i>nenhum</i>")

    def _get(self, widget_id: str) -> Any:
        return self.builder.get_object(widget_id)  # type: ignore[attr-defined]

    def _set_label(self, widget_id: str, text: str) -> None:
        w = self._get(widget_id)
        if w is not None:
            w.set_text(text)
