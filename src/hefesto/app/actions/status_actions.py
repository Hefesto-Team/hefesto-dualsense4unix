"""Aba Status: polling ao vivo de daemon.state_full + update dos widgets.

Inclui a máquina de estado de reconnect (UX-RECONNECT-01): um tick dedicado
a cada 2s (`RECONNECT_POLL_INTERVAL_S`) observa o IPC e move o header entre
três estados visuais — `online`, `reconnecting`, `offline`. O polling rápido
dos widgets de live-state é independente e preserva a fluidez da aba Status.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.constants import (
    LIVE_POLL_INTERVAL_MS,
    RECONNECT_FAIL_THRESHOLD,
    RECONNECT_POLL_INTERVAL_S,
    STATE_POLL_INTERVAL_MS,
)
from hefesto.app.ipc_bridge import daemon_state_full


class StatusActionsMixin(WidgetAccessMixin):
    """Atualiza a aba Status em tempo real.

    Assume que `self.builder` contém os widgets do `main.glade`:
        status_connection, status_transport, status_battery_bar,
        status_active_profile, status_daemon,
        live_l2_bar, live_r2_bar, live_lx_label, live_ly_label,
        live_rx_label, live_ry_label, live_buttons_label,
        header_connection.

    Estados do reconnect (`_reconnect_state`):
        - ``"online"``: último poll retornou dict; header mostra ● verde.
        - ``"reconnecting"``: IPC falhou 1..N-1 vezes consecutivas; header
          mostra ◐ laranja com texto "tentando reconectar...".
        - ``"offline"``: N falhas consecutivas (N=RECONNECT_FAIL_THRESHOLD);
          header mostra ○ vermelho "daemon offline".
    """

    _reconnect_state: str = "online"
    _consecutive_failures: int = 0

    def install_status_polling(self) -> None:
        """Liga os timers da aba Status. Chamado uma vez no on_mount."""
        GLib.timeout_add(LIVE_POLL_INTERVAL_MS, self._tick_live_state)
        GLib.timeout_add(STATE_POLL_INTERVAL_MS, self._tick_profile_state)
        GLib.timeout_add_seconds(
            RECONNECT_POLL_INTERVAL_S, self._tick_reconnect_state
        )

    def _tick_live_state(self) -> bool:
        """Roda a ~20 Hz: atualiza gatilhos, sticks, botões."""
        state = daemon_state_full()
        if state is None:
            return True  # mantém o timer vivo; header é gerido pelo reconnect

        self._render_live_state(state)
        return True

    def _tick_profile_state(self) -> bool:
        """Roda a 2 Hz: perfil ativo + metadata que muda devagar."""
        state = daemon_state_full()
        if state is None:
            return True
        self._render_slow_state(state)
        return True

    def _tick_reconnect_state(self) -> bool:
        """Roda a 0.5 Hz: coordena a máquina de estado do header."""
        state = daemon_state_full()
        self._update_reconnect_state(state)
        return True

    def _update_reconnect_state(self, state_full: dict[str, Any] | None) -> None:
        """Avança a máquina de estado de reconnect e repinta o header.

        Transições:
            * sucesso (state_full != None): qualquer estado → ``online``.
            * falha: incrementa `_consecutive_failures`.
              - < threshold: estado vai para ``reconnecting``.
              - >= threshold: estado vai para ``offline``.
        """
        if state_full is not None:
            self._consecutive_failures = 0
            self._reconnect_state = "online"
            self._render_online(state_full)
            return

        self._consecutive_failures += 1
        if self._consecutive_failures >= RECONNECT_FAIL_THRESHOLD:
            if self._reconnect_state != "offline":
                self._reconnect_state = "offline"
            self._render_offline()
        else:
            if self._reconnect_state != "reconnecting":
                self._reconnect_state = "reconnecting"
            self._render_reconnecting()

    def _render_online(self, state: dict[str, Any]) -> None:
        """Header canônico de estado ONLINE — ● verde + transport.

        Delega o pinta-completo-da-aba a `_render_live_state` e
        `_render_slow_state` (já chamados pelos ticks rápidos). Aqui só
        firma o header de forma idempotente.
        """
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
        self._set_label("status_daemon", "online")

    def _render_reconnecting(self) -> None:
        """Header intermediário — ◐ laranja + "tentando reconectar...".

        U+25D0 CIRCLE WITH LEFT HALF BLACK é Geometric Shape, não emoji.
        """
        header = self._get("header_connection")
        header.set_markup(
            '<span foreground="#d90">◐ tentando reconectar...</span>'
        )
        self._set_label("status_daemon", "reconectando")

    def _render_offline(self) -> None:
        header = self._get("header_connection")
        header.set_markup(
            '<span foreground="#d33">○ Daemon Offline</span>'
        )
        self._set_label("status_daemon", "Offline")
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
        # Só pintamos o header aqui se estamos em estado ONLINE; isso evita
        # que o tick rápido sobrescreva "Tentando Reconectar..." durante a
        # janela em que a máquina de reconnect ainda está tentando recuperar
        # o IPC (UX-RECONNECT-01 + POLISH-CAPS-01).
        if getattr(self, "_reconnect_state", "online") == "online":
            if connected:
                header.set_markup(
                    f'<span foreground="#2d8">● Conectado Via {transport.upper()}</span>'
                )
            else:
                header.set_markup(
                    '<span foreground="#d33">○ Controle Desconectado</span>'
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
            else "<i>Nenhum</i>"
        )
        self._get("live_buttons_label").set_markup(buttons_markup)

    def _render_slow_state(self, state: dict[str, Any]) -> None:
        connected = bool(state.get("connected"))
        transport = state.get("transport") or "—"
        battery = state.get("battery_pct")
        active_profile = state.get("active_profile") or "Nenhum"

        self._set_label(
            "status_connection", "Conectado" if connected else "Desconectado"
        )
        self._set_label("status_transport", transport.upper() if transport != "—" else "—")
        self._set_label("status_active_profile", active_profile)
        self._set_label("status_daemon", "Online")

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
        self._get("live_buttons_label").set_markup("<i>Nenhum</i>")
