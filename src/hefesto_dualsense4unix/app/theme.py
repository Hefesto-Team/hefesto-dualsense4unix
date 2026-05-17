"""Aplicação do tema Drácula ao Hefesto - Dualsense4Unix via Gtk.CssProvider.

Prioridade GTK_STYLE_PROVIDER_PRIORITY_APPLICATION (600) sobrepõe o tema
do sistema (PRIORITY_THEME = 200) sem vazar para outras janelas GTK.
"""
# ruff: noqa: E402
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_CSS_PATH = GUI_DIR / "theme.css"


def apply_theme(window: Gtk.Window) -> None:
    """Carrega theme.css e aplica à janela principal com classe .hefesto-dualsense4unix-window.

    Registra aviso via logger se o arquivo não for encontrado; nunca levanta
    exceção para não impedir a GUI de abrir sem tema.
    """
    if not _CSS_PATH.exists():
        logger.warning("theme_css_ausente", path=str(_CSS_PATH))
        return

    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(_CSS_PATH))
    except Exception as exc:  # GLib.Error
        logger.warning("theme_css_falha_carga", erro=str(exc))
        return

    screen = Gdk.Screen.get_default()
    if screen is None:
        logger.warning("theme_sem_display_disponivel")
        return

    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    window.get_style_context().add_class("hefesto-dualsense4unix-window")

    # FEAT-A11Y-HIGH-CONTRAST-01 (v3.4.0): detecta tema HighContrast do
    # sistema (GNOME/COSMIC Accessibility > Contraste alto) e aplica nossa
    # classe de override. GTK3 nao tem @media (prefers-contrast: more)
    # nativo — o canal real e essa classe.
    settings = Gtk.Settings.get_default()
    if settings is not None:
        theme_name = settings.get_property("gtk-theme-name") or ""
        if "highcontrast" in theme_name.lower():
            window.get_style_context().add_class(
                "hefesto-dualsense4unix-high-contrast"
            )
            logger.info("theme_high_contrast_aplicado", system_theme=theme_name)

    logger.info("theme_aplicado", css=str(_CSS_PATH))
