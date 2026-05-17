"""Janela compacta fallback quando o tray AppIndicator não funciona.

FEAT-COMPACT-WINDOW-FALLBACK-01 (v3.3.0): em Pop!_OS COSMIC e em sessões
minimalistas, o `org.kde.StatusNotifierWatcher` D-Bus que o libayatana
usa não existe, então o tray clássico fica oculto. Esta janela 320x90
sempre-on-top serve como surrogate: mostra status conectado/perfil/
bateria + 3 botões essenciais (Painel / Trocar perfil / Sair).

Gating (decisão UX 2026-05-16):
- AUTO por default quando `AppTray.start()` retorna False (sem
  AppIndicator) OU quando estamos em COSMIC sem StatusNotifierWatcher.
- Opt-out via `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0`.

Update model:
- Tick a cada `COMPACT_REFRESH_SEC` reusa `ipc_bridge.call_async` via
  `daemon.state_full` + `profiles_list` (mesmo data path do tray).
- `GLib.idle_add` no boot dispara o primeiro refresh imediato.

Reuso intencional:
- `_desktop_is_cosmic()` em `app/tray.py` — não duplicado (importado).
- `notify_*` helpers de `desktop_notifications` — não usados aqui, mas
  a CompactWindow não bloqueia o pipeline existente de notificações.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Refresh do label de estado (bateria/perfil/connected). Igual ao tray
# (3 s) para coerência visual.
COMPACT_REFRESH_SEC = 3

# Tamanho fixo intencional — 320x90 cabe em qualquer painel/canto sem
# competir com janelas reais. Sempre-on-top + sem decoração para
# parecer um widget de painel.
COMPACT_WIDTH = 320
COMPACT_HEIGHT = 90

# Env var de opt-out (default ligado).
ENV_OPT_OUT = "HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW"


def is_enabled() -> bool:
    """Compact window auto-ativa salvo HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0."""
    return os.environ.get(ENV_OPT_OUT, "1") != "0"


ShowFn = Callable[[], None]
QuitFn = Callable[[], None]
ListProfilesFn = Callable[[], list[dict[str, Any]]]
SwitchProfileFn = Callable[[str], bool]
StateFn = Callable[[], dict[str, Any] | None]


@dataclass
class CompactWindow:
    """Surrogate de tray quando AppIndicator/StatusNotifierWatcher ausente.

    API espelha `AppTray` para minimizar churn no caller (`app/app.py`):
    mesmas 4 callbacks (`on_show_window`, `on_quit`, `on_list_profiles`,
    `on_switch_profile`) + uma adicional opcional `on_state` para puxar
    `daemon.state_full` (passa o último estado via IPC quando disponível).
    """

    on_show_window: ShowFn
    on_quit: QuitFn
    on_list_profiles: ListProfilesFn
    on_switch_profile: SwitchProfileFn
    on_state: StateFn | None = None

    _window: Gtk.Window | None = None
    _status_label: Gtk.Label | None = None
    _battery_label: Gtk.Label | None = None
    _profile_menu_items: list[Gtk.MenuItem] = field(default_factory=list)
    _profiles_menu: Gtk.Menu | None = None

    def start(self) -> bool:
        """Cria a janela compacta. Retorna True se subiu."""
        if not is_enabled():
            logger.info("compact_window_opt_out", env=f"{ENV_OPT_OUT}=0")
            return False

        try:
            self._build_window()
        except Exception as exc:
            logger.warning(
                "compact_window_build_failed",
                err=str(exc),
                exc_info=True,
            )
            return False

        # Primeiro refresh imediato + tick periódico.
        GLib.idle_add(self._tick_refresh)
        GLib.timeout_add_seconds(COMPACT_REFRESH_SEC, self._tick_refresh)
        logger.info(
            "compact_window_started",
            size=f"{COMPACT_WIDTH}x{COMPACT_HEIGHT}",
        )
        return True

    def stop(self) -> None:
        if self._window is not None:
            import contextlib as _ctx

            with _ctx.suppress(Exception):
                self._window.destroy()
            self._window = None

    def _build_window(self) -> None:
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title("Hefesto - Dualsense4Unix")
        win.set_default_size(COMPACT_WIDTH, COMPACT_HEIGHT)
        win.set_resizable(False)
        win.set_keep_above(True)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_decorated(False)
        # Posiciona no canto inferior-direito (área tradicional de widget).
        win.set_gravity(Gdk.Gravity.SOUTH_EAST)
        win.connect("delete-event", lambda *_: True)  # nunca fecha

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.set_margin_top(6)
        outer.set_margin_bottom(6)
        win.add(outer)

        # Linha 1: status + bateria.
        line1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_label = Gtk.Label()
        # Glyph U+25CB (white circle) via NCR + texto inicial.
        self._status_label.set_markup(
            '<span foreground="#888">&#9675; ' + _("Iniciando...") + "</span>"
        )
        self._status_label.set_xalign(0.0)
        line1.pack_start(self._status_label, True, True, 0)

        self._battery_label = Gtk.Label()
        self._battery_label.set_markup(
            '<span font_family="monospace">— %</span>'
        )
        self._battery_label.set_xalign(1.0)
        line1.pack_end(self._battery_label, False, False, 0)
        outer.pack_start(line1, False, False, 0)

        # Linha 2: botões.
        line2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        line2.set_homogeneous(True)

        btn_panel = Gtk.Button.new_with_label(_("Painel"))
        btn_panel.connect("clicked", lambda _w: self.on_show_window())
        line2.pack_start(btn_panel, True, True, 0)

        btn_profile = Gtk.Button.new_with_label(_("Perfil"))
        btn_profile.connect("clicked", self._on_profile_button_clicked)
        line2.pack_start(btn_profile, True, True, 0)

        btn_quit = Gtk.Button.new_with_label(_("Sair"))
        btn_quit.connect("clicked", lambda _w: self.on_quit())
        line2.pack_start(btn_quit, True, True, 0)

        outer.pack_start(line2, False, False, 0)

        win.show_all()
        self._window = win

    def _on_profile_button_clicked(self, btn: Gtk.Button) -> None:
        """Abre popup menu com perfis disponíveis ancorado no botão."""
        if self._profiles_menu is None:
            self._profiles_menu = Gtk.Menu()
        # Limpa items antigos.
        for item in self._profile_menu_items:
            self._profiles_menu.remove(item)
        self._profile_menu_items = []

        profiles = self.on_list_profiles()
        if not profiles:
            item = Gtk.MenuItem.new_with_label(_("(nenhum perfil)"))
            item.set_use_underline(False)
            item.set_sensitive(False)
            self._profiles_menu.append(item)
            self._profile_menu_items.append(item)
        else:
            for entry in profiles:
                name = str(entry.get("name", ""))
                if not name:
                    continue
                # ASCII marker para não conflitar com sanitizer global.
                label = (
                    f"> {name}" if entry.get("active") else name
                )
                item = Gtk.MenuItem.new_with_label(label)
                item.set_use_underline(False)
                item.connect(
                    "activate",
                    lambda _w, n=name: self.on_switch_profile(n),
                )
                self._profiles_menu.append(item)
                self._profile_menu_items.append(item)
        self._profiles_menu.show_all()
        self._profiles_menu.popup_at_widget(
            btn,
            Gdk.Gravity.SOUTH_WEST,
            Gdk.Gravity.NORTH_WEST,
            None,
        )

    def _tick_refresh(self) -> bool:
        """Atualiza labels (status + bateria) com o último state do daemon."""
        try:
            state = self.on_state() if self.on_state else None
        except Exception as exc:
            logger.debug("compact_window_state_fetch_failed", err=str(exc))
            state = None
        self._render_state(state)
        return True  # mantém o timer vivo

    def _render_state(self, state: dict[str, Any] | None) -> None:
        if self._status_label is None or self._battery_label is None:
            return
        if state is None or not isinstance(state, dict):
            self._status_label.set_markup(
                '<span foreground="#d33">&#9675; '
                + _("Daemon offline")
                + "</span>"
            )
            self._battery_label.set_markup(
                '<span font_family="monospace">— %</span>'
            )
            return
        connected = bool(state.get("connected"))
        transport = (state.get("transport") or "").upper() or "?"
        active = state.get("active_profile") or "—"
        battery = state.get("battery_pct")
        if connected:
            self._status_label.set_markup(
                f'<span foreground="#2d8">&#9679; {transport} · {active}</span>'
            )
        else:
            self._status_label.set_markup(
                '<span foreground="#d33">&#9675; '
                + _("Controle desconectado")
                + "</span>"
            )
        if isinstance(battery, int) and 0 <= battery <= 100:
            self._battery_label.set_markup(
                f'<span font_family="monospace">{battery} %</span>'
            )
        else:
            self._battery_label.set_markup(
                '<span font_family="monospace">— %</span>'
            )


__all__ = ["COMPACT_REFRESH_SEC", "ENV_OPT_OUT", "CompactWindow", "is_enabled"]
