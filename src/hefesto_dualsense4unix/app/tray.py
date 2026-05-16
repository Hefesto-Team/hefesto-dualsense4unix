"""Tray icon do HefestoApp: close-to-tray + atalhos rápidos.

FEAT-COSMIC-TRAY-FALLBACK-01 (v3.1.0): em COSMIC 1.0+, a criação do
`AppIndicator` precisa ser deferred via `GLib.timeout_add(500, ...)` para
dar tempo do `cosmic-applet-status-area` registrar `org.kde.StatusNotifierWatcher`
no D-Bus. Se mesmo assim o watcher não estiver presente, emitimos uma
notification D-Bus orientadora (`cosmic-applet-status-area` desabilitado)
e seguimos sem tray. A janela principal segue funcional como entrypoint.

Warning benigno conhecido:
    Em sessão COSMIC + Wayland, ~160ms após `Indicator.set_menu()` aparece:
    `Gtk-CRITICAL: gtk_widget_get_scale_factor: assertion 'GTK_IS_WIDGET (widget)' failed`
    É emitido pelo próprio `libayatana-appindicator3` durante a montagem do
    ProxyMenu D-Bus, fora do nosso código. Não há efeito visível e o tray
    funciona normalmente (quando o cosmic-applet-status-area está no painel).
    Discutido em `pop-os/cosmic-applets#1009` e relacionados. Manter como
    warning até libayatana-appindicator-glib substituir libayatana-appindicator3.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.integrations.desktop_notifications import (
    notify,
    statusnotifierwatcher_available,
)
from hefesto_dualsense4unix.integrations.tray import probe_gi_availability
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TRAY_APP_ID = "hefesto-dualsense4unix"
TRAY_ICON_NAME = "hefesto-dualsense4unix"
TRAY_ICON_FALLBACK = "input-gaming"
PROFILE_REFRESH_SEC = 3
ACTIVE_MARKER = "> "

# FEAT-COSMIC-TRAY-FALLBACK-01: delay para registrar o indicator depois que o
# cosmic-applet-status-area subir o watcher. Empírico: 500ms cobre os casos
# de race em COSMIC 1.0.6+; tempo maior é gratuito (usuário não percebe).
_INDICATOR_DEFERRED_MS = 500


def _desktop_is_cosmic() -> bool:
    """True se XDG_CURRENT_DESKTOP/XDG_SESSION_DESKTOP indicam COSMIC."""
    desktops = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + ":"
        + os.environ.get("XDG_SESSION_DESKTOP", "")
    ).lower()
    return "cosmic" in desktops

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

        # FEAT-COSMIC-TRAY-FALLBACK-01: em COSMIC, defere a criação do
        # indicator para depois do mainloop subir, garantindo que o
        # cosmic-applet-status-area já reivindicou o watcher do D-Bus. Não
        # bloqueia o startup da GUI — janela principal abre normal e o
        # indicator surge ~500ms depois.
        if _desktop_is_cosmic():
            logger.info(
                "apptray_deferred_for_cosmic",
                delay_ms=_INDICATOR_DEFERRED_MS,
                hint=(
                    "cosmic-applet-status-area registra o watcher D-Bus "
                    "alguns ms apos o login; criar o Indicator imediato "
                    "perde a primeira fase."
                ),
            )
            # GLib espera retorno bool: False = não repetir o timer.
            GLib.timeout_add(
                _INDICATOR_DEFERRED_MS,
                lambda: (self._start_deferred(), False)[1],
            )
            return True

        return self._start_deferred()

    def _start_deferred(self) -> bool:
        """Cria o indicator de fato. Roda imediatamente em GNOME/KDE/etc
        e via GLib.timeout em COSMIC."""
        import gi as _gi

        indicator_cls, category = self._resolve_indicator(_gi)

        icon = self._preferred_icon()
        self._indicator = indicator_cls.new(TRAY_APP_ID, icon, category)
        ns = indicator_cls._hefesto_ns
        self._indicator_ns = ns
        self._indicator.set_status(ns.IndicatorStatus.ACTIVE)
        self._indicator.set_title("Hefesto - Dualsense4Unix")

        self._menu = Gtk.Menu()

        self._status_item = Gtk.MenuItem(label="Hefesto - Dualsense4Unix (carregando...)")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        show = Gtk.MenuItem(label="Abrir painel")
        show.connect("activate", lambda _w: self.on_show_window())
        self._menu.append(show)

        self._menu.append(Gtk.SeparatorMenuItem())

        self._profiles_item = Gtk.MenuItem(label="Perfis")
        self._profiles_submenu = Gtk.Menu()
        # TRAY-LOADING-ZOMBIE-01: nascido vazio — `_render_profiles` é fonte
        # única de verdade do submenu. Estado inicial "(nenhum perfil)" é
        # produzido logo abaixo via `_render_profiles([])`, garantindo que
        # 100% dos itens estejam em `_profile_menu_items`.
        self._profiles_item.set_submenu(self._profiles_submenu)
        self._menu.append(self._profiles_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Sair do Hefesto - Dualsense4Unix")
        quit_item.connect("activate", lambda _w: self.on_quit())
        self._menu.append(quit_item)

        # Popula submenu Perfis via path canônico antes do show_all.
        self._render_profiles([])

        self._menu.show_all()
        self._indicator.set_menu(self._menu)

        GLib.timeout_add_seconds(PROFILE_REFRESH_SEC, self._tick_refresh)
        self._tick_refresh()

        logger.info("apptray_started", icon=icon)

        # FEAT-COSMIC-TRAY-FALLBACK-01: probe imediato do StatusNotifierWatcher.
        # Se ausente em sessão COSMIC, avisa via D-Bus notification (uma vez)
        # e segue. Não tenta workaround — o usuário precisa instalar/habilitar
        # cosmic-applet-status-area no painel.
        if _desktop_is_cosmic() and not statusnotifierwatcher_available():
            logger.warning(
                "statusnotifierwatcher_ausente",
                hint=(
                    "cosmic-applet-status-area pode estar desabilitado no "
                    "cosmic-panel. Habilite em Configurações > Painel > "
                    "Applets para o tray aparecer."
                ),
            )
            notify(
                summary="Hefesto - Dualsense4Unix",
                body=(
                    "Tray icon indisponivel no COSMIC. "
                    "Habilite o applet 'Area de status' no cosmic-panel "
                    "(Configurações > Painel) ou use a janela principal."
                ),
                icon="input-gaming",
                timeout_ms=10000,
                once_key="cosmic_tray_missing",
            )

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
            # TRAY-UNDERSCORE-MNEMONIC-01: `new_with_label` cria com
            # use_underline=False por default; reforço com setter para
            # robustez frente a backports/forks. Sem isso, labels com `_`
            # são interpretadas como mnemonics e ficam com `__` no rendering
            # dbusmenu (StatusNotifierItem).
            item = Gtk.MenuItem.new_with_label("(nenhum perfil)")
            item.set_use_underline(False)
            item.set_sensitive(False)
            self._profiles_submenu.append(item)
            self._profile_menu_items.append(item)
        else:
            for entry in profiles:
                name = str(entry.get("name", ""))
                if not name:
                    continue
                label = f"{ACTIVE_MARKER}{name}" if entry.get("active") else name
                item = Gtk.MenuItem.new_with_label(label)
                item.set_use_underline(False)
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
                f"Hefesto - Dualsense4Unix - perfil: {active}"
                if active
                else f"Hefesto - Dualsense4Unix - {len(profiles)} perfis"
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
