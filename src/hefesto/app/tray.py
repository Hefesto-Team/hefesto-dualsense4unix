"""Tray icon do HefestoApp: close-to-tray + atalhos rápidos."""
# ruff: noqa: E402
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto.integrations.tray import probe_gi_availability
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

TRAY_APP_ID = "hefesto"
TRAY_ICON_NAME = "hefesto"
TRAY_ICON_FALLBACK = "input-gaming"
PROFILE_REFRESH_SEC = 3
ACTIVE_MARKER = "> "

ShowFn = Callable[[], None]
QuitFn = Callable[[], None]
ListProfilesFn = Callable[[], list[dict[str, Any]]]
SwitchProfileFn = Callable[[str], bool]


@dataclass
class AppTray:
    """Controla o tray; ao clicar abre janela, 'Sair' encerra o processo."""

    on_show_window: ShowFn
    on_quit: QuitFn
    on_list_profiles: ListProfilesFn
    on_switch_profile: SwitchProfileFn

    _indicator: Any = None
    _indicator_ns: Any = None
    _menu: Gtk.Menu | None = None
    _profiles_submenu: Gtk.Menu | None = None
    _profiles_item: Gtk.MenuItem | None = None
    _status_item: Gtk.MenuItem | None = None
    _profile_menu_items: list[Gtk.MenuItem] = field(default_factory=list)

    def is_available(self) -> bool:
        ok, _ = probe_gi_availability()
        return ok

    def start(self) -> bool:
        ok, msg = probe_gi_availability()
        if not ok:
            logger.warning("apptray_unavailable", msg=msg)
            return False

        import gi as _gi

        indicator_cls, category = self._resolve_indicator(_gi)

        icon = self._preferred_icon()
        self._indicator = indicator_cls.new(TRAY_APP_ID, icon, category)
        ns = indicator_cls._hefesto_ns
        self._indicator_ns = ns
        self._indicator.set_status(ns.IndicatorStatus.ACTIVE)
        self._indicator.set_title("Hefesto")

        self._menu = Gtk.Menu()

        self._status_item = Gtk.MenuItem(label="Hefesto (carregando...)")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        show = Gtk.MenuItem(label="Abrir painel")
        show.connect("activate", lambda _w: self.on_show_window())
        self._menu.append(show)

        self._menu.append(Gtk.SeparatorMenuItem())

        self._profiles_item = Gtk.MenuItem(label="Perfis")
        self._profiles_submenu = Gtk.Menu()
        empty = Gtk.MenuItem(label="(carregando)")
        empty.set_sensitive(False)
        self._profiles_submenu.append(empty)
        self._profiles_item.set_submenu(self._profiles_submenu)
        self._menu.append(self._profiles_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Sair do Hefesto")
        quit_item.connect("activate", lambda _w: self.on_quit())
        self._menu.append(quit_item)

        self._menu.show_all()
        self._indicator.set_menu(self._menu)

        GLib.timeout_add_seconds(PROFILE_REFRESH_SEC, self._tick_refresh)
        self._tick_refresh()

        logger.info("apptray_started", icon=icon)
        return True

    def stop(self) -> None:
        if self._indicator is not None:
            try:
                ns = getattr(self, "_indicator_ns", None)
                if ns is not None:
                    self._indicator.set_status(ns.IndicatorStatus.PASSIVE)
            except Exception:
                pass
            self._indicator = None

    def _tick_refresh(self) -> bool:
        profiles = self.on_list_profiles()
        self._render_profiles(profiles)
        return True

    def _render_profiles(self, profiles: list[dict[str, Any]]) -> None:
        if self._profiles_submenu is None:
            return
        for item in self._profile_menu_items:
            self._profiles_submenu.remove(item)
        self._profile_menu_items = []

        if not profiles:
            item = Gtk.MenuItem(label="(nenhum perfil)")
            item.set_sensitive(False)
            self._profiles_submenu.append(item)
            self._profile_menu_items.append(item)
        else:
            for entry in profiles:
                name = str(entry.get("name", ""))
                if not name:
                    continue
                label = f"{ACTIVE_MARKER}{name}" if entry.get("active") else name
                item = Gtk.MenuItem(label=label)
                item.connect(
                    "activate", lambda _w, n=name: self.on_switch_profile(n)
                )
                self._profiles_submenu.append(item)
                self._profile_menu_items.append(item)

        self._profiles_submenu.show_all()

        if self._status_item is not None:
            active = next(
                (p.get("name") for p in profiles if p.get("active")),
                None,
            )
            label = (
                f"Hefesto - perfil: {active}"
                if active
                else f"Hefesto - {len(profiles)} perfis"
            )
            self._status_item.set_label(label)

    @staticmethod
    def _preferred_icon() -> str:
        theme = Gtk.IconTheme.get_default()
        if theme is not None and theme.has_icon(TRAY_ICON_NAME):
            return TRAY_ICON_NAME
        return TRAY_ICON_FALLBACK

    @staticmethod
    def _resolve_indicator(gi_mod: Any) -> tuple[Any, Any]:
        for version_name in ("AyatanaAppIndicator3", "AppIndicator3"):
            try:
                gi_mod.require_version(version_name, "0.1")
                mod = __import__("gi.repository", fromlist=[version_name])
                ns = getattr(mod, version_name)
                indicator_cls = ns.Indicator
                category = ns.IndicatorCategory.APPLICATION_STATUS
                indicator_cls._hefesto_ns = ns
                return indicator_cls, category
            except Exception:
                continue
        raise RuntimeError("AppIndicator indisponivel")


__all__ = ["AppTray"]
