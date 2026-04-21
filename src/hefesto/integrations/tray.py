r"""Tray icon GTK3 com AppIndicator (W5.4, opcional).

Depende do extra `[tray]` do pyproject (`PyGObject`) + pacotes do SO
(`gir1.2-ayatanaappindicator3-0.1` em Pop!\_OS/Ubuntu, `libappindicator-gtk3`
em Fedora). Quando a lib não está disponível, `TrayController.is_available()`
retorna `False` e a CLI `hefesto tray` mostra mensagem clara pro usuário.

Menu:
  - Status: label não-clicável com bateria/perfil atual.
  - Perfis: submenu com cada perfil (click ativa via IPC).
  - Abrir TUI: dispara `hefesto tui` em processo filho.
  - Sair: destroy do tray.

Atualiza via timer de 2s consultando `daemon.status` pelo IPC.
"""
from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

APP_ID = "hefesto-tray"
ICON_NAME = "input-gaming"  # Symbolic icon do kernel freedesktop
REFRESH_INTERVAL_SEC = 2


def probe_gi_availability() -> tuple[bool, str]:
    """Verifica se GTK3 + AppIndicator estão importáveis.

    Retorna `(ok, msg)`. `msg` descreve faltas pra mostrar ao usuário.
    """
    try:
        import gi
    except ImportError:
        return False, (
            "PyGObject nao instalado. Rode: ./scripts/dev_bootstrap.sh --with-tray"
        )
    try:
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
    except Exception as exc:
        return False, f"Gtk 3.0 indisponivel: {exc}"

    # Tenta Ayatana (Ubuntu/Debian modernos) depois AppIndicator3 (legado)
    for version_name in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(version_name, "0.1")
            from gi import repository  # noqa: F401

            return True, f"ok via {version_name}"
        except Exception:
            continue
    return False, (
        "AppIndicator/Ayatana indisponivel. Rode: sudo apt install "
        "gir1.2-ayatanaappindicator3-0.1  # Ubuntu/Pop/Debian"
    )


@dataclass
class TrayController:
    """Wrapper pro tray com lazy-load dos módulos gi."""

    app_id: str = APP_ID
    icon_name: str = ICON_NAME

    _indicator: Any = None
    _menu: Any = None
    _profile_items: list[Any] = field(default_factory=list)
    _status_item: Any = None

    def is_available(self) -> bool:
        ok, _ = probe_gi_availability()
        return ok

    def start(self) -> bool:
        """Cria o tray icon. Retorna False se gi indisponível."""
        ok, msg = probe_gi_availability()
        if not ok:
            logger.warning("tray_unavailable", msg=msg)
            return False

        import gi
        from gi.repository import Gtk

        indicator_cls, category = self._load_indicator_class(gi)

        self._indicator = indicator_cls.new(
            self.app_id, self.icon_name, category,
        )
        self._indicator.set_status(indicator_cls.IndicatorStatus.ACTIVE)

        self._menu = Gtk.Menu()
        self._status_item = Gtk.MenuItem(label="Hefesto: carregando...")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Placeholder — perfis carregados depois via _refresh_profiles
        self._profile_items = []

        self._menu.append(Gtk.SeparatorMenuItem())

        open_tui = Gtk.MenuItem(label="Abrir TUI")
        open_tui.connect("activate", self._on_open_tui)
        self._menu.append(open_tui)

        quit_item = Gtk.MenuItem(label="Sair")
        quit_item.connect("activate", self._on_quit)
        self._menu.append(quit_item)

        self._menu.show_all()
        self._indicator.set_menu(self._menu)
        logger.info("tray_created", app_id=self.app_id, icon=self.icon_name)
        return True

    def run(self) -> None:
        """Roda o Gtk main loop. Bloqueante até `quit()`."""
        from gi.repository import Gtk

        Gtk.main()

    def stop(self) -> None:
        if self._indicator is not None:
            # Tenta marcar passivo via status constant; cai em try/except
            # porque type() de MagicMock não expõe IndicatorStatus.
            with contextlib.suppress(Exception):
                passive = type(self._indicator).IndicatorStatus.PASSIVE
                self._indicator.set_status(passive)
            self._indicator = None
        try:
            from gi.repository import Gtk

            Gtk.main_quit()
        except Exception:
            pass

    def update_status(self, label: str) -> None:
        if self._status_item is not None:
            self._status_item.set_label(label)

    def update_profiles(
        self,
        profiles: list[str],
        on_select: Callable[[str], None],
    ) -> None:
        """Atualiza submenu de perfis. Remove itens antigos e cria novos."""
        if self._menu is None:
            return
        from gi.repository import Gtk

        for item in self._profile_items:
            self._menu.remove(item)
        self._profile_items = []

        # Inserir os itens após o status + separator (índices 0 e 1).
        position = 2
        for name in profiles:
            item = Gtk.MenuItem(label=f"Perfil: {name}")
            item.connect("activate", lambda _w, n=name: on_select(n))
            self._menu.insert(item, position)
            self._profile_items.append(item)
            position += 1
        self._menu.show_all()

    @staticmethod
    def _load_indicator_class(gi_mod: Any) -> tuple[Any, Any]:
        """Tenta Ayatana, depois AppIndicator3 legado. Retorna (Indicator, Category)."""
        for version_name in ("AyatanaAppIndicator3", "AppIndicator3"):
            try:
                gi_mod.require_version(version_name, "0.1")
                indicator_module = __import__(
                    "gi.repository", fromlist=[version_name]
                )
                indicator_cls = getattr(indicator_module, version_name).Indicator
                category = getattr(
                    indicator_module, version_name
                ).IndicatorCategory.APPLICATION_STATUS
                return indicator_cls, category
            except Exception:
                continue
        raise RuntimeError("nenhum AppIndicator encontrado")

    def _on_open_tui(self, _widget: Any) -> None:
        subprocess.Popen(["hefesto", "tui"])

    def _on_quit(self, _widget: Any) -> None:
        self.stop()


__all__ = ["APP_ID", "ICON_NAME", "TrayController", "probe_gi_availability"]
