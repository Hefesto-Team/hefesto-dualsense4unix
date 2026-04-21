"""Aba Daemon: status systemd --user + controles."""
# ruff: noqa: E402
from __future__ import annotations

import subprocess
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.daemon.service_install import (
    SERVICE_HEADLESS,
    SERVICE_NORMAL,
    user_unit_dir,
)

UNITS = (SERVICE_NORMAL, SERVICE_HEADLESS)


class DaemonActionsMixin(WidgetAccessMixin):
    """Controla a aba Daemon."""

    _daemon_autostart_guard: bool

    def install_daemon_tab(self) -> None:
        combo: Gtk.ComboBoxText = self._get("daemon_unit_combo")
        combo.remove_all()
        for unit in UNITS:
            combo.append(unit, unit)
        combo.set_active_id(SERVICE_NORMAL)
        self._daemon_autostart_guard = False
        self._refresh_daemon_view()

    # --- handlers ---

    def on_daemon_unit_changed(self, _combo: Gtk.ComboBoxText) -> None:
        self._refresh_daemon_view()

    def on_daemon_start(self, _btn: Gtk.Button) -> None:
        self._run_systemctl("start")

    def on_daemon_stop(self, _btn: Gtk.Button) -> None:
        self._run_systemctl("stop")

    def on_daemon_restart(self, _btn: Gtk.Button) -> None:
        self._run_systemctl("restart")

    def on_daemon_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_daemon_view()

    def on_daemon_view_logs(self, _btn: Gtk.Button) -> None:
        unit = self._selected_unit()
        logs = self._journalctl_tail(unit, lines=80)
        self._set_daemon_text(logs or "(sem saída)")

    def on_daemon_autostart_toggled(
        self, _switch: Gtk.Switch, state: bool
    ) -> bool:
        if self._daemon_autostart_guard:
            return False
        action = "enable" if state else "disable"
        self._run_systemctl(action)
        return False

    # --- helpers ---

    def _selected_unit(self) -> str:
        return self._get("daemon_unit_combo").get_active_id() or SERVICE_NORMAL

    def _refresh_daemon_view(self) -> None:
        unit = self._selected_unit()
        installed = (user_unit_dir() / unit).exists()
        active = self._systemctl_oneline(["is-active", unit]) or "unknown"
        enabled = self._systemctl_oneline(["is-enabled", unit]) or "unknown"
        self._set_daemon_status_markup(installed, active, enabled)

        self._daemon_autostart_guard = True
        try:
            self._get("daemon_autostart_switch").set_active(enabled == "enabled")
        finally:
            self._daemon_autostart_guard = False

        text = self._systemctl_status_text(unit)
        self._set_daemon_text(text)

    def _set_daemon_status_markup(
        self, installed: bool, active: str, enabled: str
    ) -> None:
        label = self._get("daemon_status_label")
        if not installed:
            label.set_markup(
                '<span foreground="#d33">unit não instalada em '
                '~/.config/systemd/user/</span>'
            )
            return
        color = "#2d8" if active == "active" else "#d33"
        label.set_markup(
            f'<span foreground="{color}">● {active}</span>'
            f' <span foreground="#888">(auto-start: {enabled})</span>'
        )

    def _set_daemon_text(self, text: str) -> None:
        view: Gtk.TextView = self._get("daemon_status_text")
        buf: Gtk.TextBuffer = view.get_buffer()
        buf.set_text(text)

    def _run_systemctl(self, action: str) -> None:
        unit = self._selected_unit()
        result = self._invoke_systemctl([action, unit], capture=True)
        rc = result.returncode if result is not None else -1
        self._toast_daemon(f"systemctl {action} {unit} → rc={rc}")
        self._refresh_daemon_view()

    def _systemctl_oneline(self, args: list[str]) -> str:
        result = self._invoke_systemctl(args, capture=True, check=False)
        if result is None:
            return ""
        return (result.stdout or "").strip().splitlines()[:1][0] if result.stdout.strip() else ""

    def _systemctl_status_text(self, unit: str) -> str:
        result = self._invoke_systemctl(
            ["status", unit, "--no-pager"], capture=True, check=False
        )
        if result is None:
            return "(systemctl indisponível)"
        return (result.stdout or "") + (result.stderr or "")

    def _journalctl_tail(self, unit: str, lines: int = 80) -> str:
        try:
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    unit,
                    "-n",
                    str(lines),
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return f"journalctl indisponível: {exc}"
        return (result.stdout or "") + (result.stderr or "")

    def _invoke_systemctl(
        self,
        args: list[str],
        *,
        capture: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["systemctl", "--user", *args],
                capture_output=capture,
                text=True,
                check=check,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

    def _toast_daemon(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("daemon")
        bar.push(ctx_id, msg)
