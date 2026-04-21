"""HefestoApp GTK: janela principal + Notebook de abas.

Começa com a aba Status 100% funcional; abas futuras (Triggers, Lightbar,
Rumble, Player LEDs, Perfis, Daemon, Emulação) serão adicionadas em fases
seguintes do HEFESTO-GUI.
"""
# ruff: noqa: E402
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto import __version__
from hefesto.app.actions.status_actions import StatusActionsMixin
from hefesto.app.constants import ICON_PATH, MAIN_GLADE


class HefestoApp(StatusActionsMixin):
    """Aplicação GTK do Hefesto."""

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        if not MAIN_GLADE.exists():
            raise FileNotFoundError(f"main.glade não encontrado em {MAIN_GLADE}")
        self.builder.add_from_file(str(MAIN_GLADE))

        self.window = self.builder.get_object("main_window")
        if self.window is None:
            raise RuntimeError("main_window não encontrada em main.glade")

        self.window.set_title(f"Hefesto v{__version__}")
        self.window.set_wmclass("hefesto", "Hefesto")
        if ICON_PATH.exists():
            self.window.set_icon_from_file(str(ICON_PATH))

        self.builder.connect_signals(self._signal_handlers())

    def _signal_handlers(self) -> dict[str, object]:
        return {
            "on_window_destroy": self.on_window_destroy,
        }

    # --- handlers ---

    def on_window_destroy(self, _widget: object) -> None:
        Gtk.main_quit()

    # --- run ---

    def show(self) -> None:
        self.window.show_all()
        self.install_status_polling()

    def run(self) -> None:
        self.show()
        Gtk.main()


def main() -> None:
    app = HefestoApp()
    app.run()


if __name__ == "__main__":
    main()
