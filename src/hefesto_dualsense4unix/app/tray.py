"""Tray icon do HefestoApp: close-to-tray + atalhos rápidos."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.integrations.desktop_notifications import (
    notify,
    statusnotifierwatcher_available,
)
from hefesto_dualsense4unix.integrations.tray import probe_gi_availability
from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TRAY_APP_ID = identidade.atual().app_id

TRAY_ICON_NAME = f"{identidade.atual().icone}-symbolic"

TRAY_ICON_NAME_LEGADO = identidade.atual().icone

TRAY_ICON_FALLBACK = "input-gaming"
PROFILE_REFRESH_SEC = 3
ACTIVE_MARKER = "> "

_INDICATOR_DEFERRED_MS = 1500

_WATCHER_PROBE_RETRIES = 3
_WATCHER_PROBE_RETRY_MS = 1000

_TRAY_WARNED_FLAG_NAME = "cosmic_tray_warned.flag"


def _desktop_is_cosmic() -> bool:
    """True se XDG_CURRENT_DESKTOP/XDG_SESSION_DESKTOP indicam COSMIC."""
    desktops = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + ":"
        + os.environ.get("XDG_SESSION_DESKTOP", "")
    ).lower()
    return "cosmic" in desktops

ShowFn = Callable[[], None]
def _painel_recolore_simbolico() -> bool:
    """O painel desta sessão sabe desenhar o ícone SIMBÓLICO em SVG?"""
    sessao = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + " "
        + os.environ.get("XDG_SESSION_DESKTOP", "")
    ).upper()
    if "COSMIC" in sessao:
        return True
    return "GNOME" not in sessao


QuitFn = Callable[[], None]
ListProfilesFn = Callable[[], list[dict[str, Any]]]
SwitchProfileFn = Callable[[str], bool]
#: Snapshot de `daemon.state_full` (ou None se offline) — usado para o tray
StateFn = Callable[[], dict[str, Any] | None]

#: <!-- noqa-acento: citação literal dela -->
ModoFn = Callable[[bool], bool]
ReconectarFn = Callable[[], bool]
ServicoFn = Callable[[str], bool]


@dataclass
class AppTray:
    """Controla o tray; ao clicar abre janela, 'Sair' encerra o processo."""

    on_show_window: ShowFn
    on_quit: QuitFn
    on_list_profiles: ListProfilesFn
    on_switch_profile: SwitchProfileFn
    on_state: StateFn | None = None
    on_set_modo: ModoFn | None = None
    on_reconectar: ReconectarFn | None = None
    on_servico: ServicoFn | None = None

    _indicator: Any = None
    _indicator_ns: Any = None
    _menu: Gtk.Menu | None = None
    _profiles_submenu: Gtk.Menu | None = None
    _profiles_item: Gtk.MenuItem | None = None
    _status_item: Gtk.MenuItem | None = None
    _profile_menu_items: list[Gtk.MenuItem] = field(default_factory=list)
    _refresh_inflight: bool = False
    _modo_ligado_item: Any = None
    _modo_desligado_item: Any = None
    _servico_item: Any = None
    _servico_de_pe: bool = False
    _pintando_o_modo: bool = False

    def is_available(self) -> bool:
        ok, _ = probe_gi_availability()
        return ok

    def start(self) -> bool:
        ok, msg = probe_gi_availability()
        if not ok:
            logger.warning("apptray_unavailable", msg=msg)
            return False

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
            GLib.timeout_add(
                _INDICATOR_DEFERRED_MS,
                lambda: (self._start_deferred(), False)[1],
            )
            return True

        return self._start_deferred()

    def _start_deferred(self) -> bool:
        """Cria o indicator de fato. Roda imediatamente em GNOME/KDE/etc"""
        import gi as _gi

        indicator_cls, category = self._resolve_indicator(_gi)

        icon = self._preferred_icon()
        self._indicator = indicator_cls.new(TRAY_APP_ID, icon, category)
        self._ensinar_o_caminho_do_icone(icon)
        ns = indicator_cls._hefesto_ns
        self._indicator_ns = ns
        self._indicator.set_status(ns.IndicatorStatus.ACTIVE)
        self._indicator.set_title(identidade.atual().nome_longo)

        self._menu = Gtk.Menu()

        self._status_item = Gtk.MenuItem(label=_("Hefesto - DualSense4Unix (carregando...)"))
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        show = Gtk.MenuItem(label=_("Abrir painel"))
        show.connect("activate", lambda _w: self.on_show_window())
        self._menu.append(show)

        self._montar_os_atos_do_jogo()

        self._menu.append(Gtk.SeparatorMenuItem())

        self._profiles_item = Gtk.MenuItem(label=_("Perfis"))
        self._profiles_submenu = Gtk.Menu()
        self._profiles_item.set_submenu(self._profiles_submenu)
        self._menu.append(self._profiles_item)

        self._montar_os_atos_do_servico()

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label=_("Sair do Hefesto - DualSense4Unix"))
        quit_item.connect("activate", lambda _w: self.on_quit())
        self._menu.append(quit_item)

        self._render_profiles([])

        self._menu.show_all()
        self._indicator.set_menu(self._menu)

        GLib.timeout_add_seconds(PROFILE_REFRESH_SEC, self._tick_refresh)
        self._tick_refresh()

        logger.info("apptray_started", icon=icon)

        if _desktop_is_cosmic():
            GLib.timeout_add(
                _WATCHER_PROBE_RETRY_MS,
                lambda: self._probe_watcher_with_retries(0),
            )

        return True

    def _probe_watcher_with_retries(self, attempt: int) -> bool:
        """Probe StatusNotifierWatcher com retries — só notifica se TODAS falharem."""
        if statusnotifierwatcher_available():
            logger.debug("statusnotifierwatcher_disponivel_apos_retry", attempt=attempt)
            return False
        if attempt + 1 < _WATCHER_PROBE_RETRIES:
            GLib.timeout_add(
                _WATCHER_PROBE_RETRY_MS,
                lambda: self._probe_watcher_with_retries(attempt + 1),
            )
            return False
        self._maybe_notify_tray_missing()
        return False

    @staticmethod
    def _maybe_notify_tray_missing() -> None:
        """Emite notify de tray indisponível só se ainda não avisou (flag persistente)."""
        from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

        try:
            flag_path = runtime_dir(ensure=True) / _TRAY_WARNED_FLAG_NAME
        except Exception as exc:
            logger.debug("tray_warned_flag_path_falhou", err=str(exc))
            flag_path = None

        reset = os.environ.get(
            "HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING", ""
        ).strip() in ("1", "true", "yes")
        if reset and flag_path is not None:
            with contextlib.suppress(OSError):
                flag_path.unlink()

        if flag_path is not None and flag_path.exists():
            logger.debug("tray_warning_ja_avisado_em_sessao_anterior")
            return

        logger.warning(
            "statusnotifierwatcher_ausente",
            hint=(
                "cosmic-applet-status-area pode estar desabilitado no "
                "cosmic-panel. Habilite em Configurações > Painel > "
                "Applets para o tray aparecer."
            ),
        )
        notify(
            summary=identidade.atual().nome_longo,
            body=(
                "Tray icon indisponivel no COSMIC. "
                "Habilite o applet 'Area de status' no cosmic-panel "
                "(Configurações > Painel) ou use a janela principal. "
                "Este aviso só aparece uma vez."
            ),
            icon="input-gaming",
            timeout_ms=10000,
            once_key="cosmic_tray_missing",
        )
        if flag_path is not None:
            with contextlib.suppress(OSError):
                flag_path.write_text(
                    "Hefesto - DualSense4Unix tray warning shown.\n", encoding="utf-8"
                )

    def stop(self) -> None:
        if self._indicator is not None:
            try:
                ns = getattr(self, "_indicator_ns", None)
                if ns is not None:
                    self._indicator.set_status(ns.IndicatorStatus.PASSIVE)
            except Exception:
                pass
            self._indicator = None

    # coisa."* <!-- noqa-acento: citação literal dela -->
    def _montar_os_atos_do_jogo(self) -> None:
        """«Ligado/Desligado» e «Reconectar controles» — os da aba Jogar."""
        if self._menu is None:
            return
        if self.on_set_modo is None and self.on_reconectar is None:
            return

        self._menu.append(Gtk.SeparatorMenuItem())

        if self.on_set_modo is not None:
            self._modo_ligado_item = Gtk.RadioMenuItem(label=_("Ligado"))
            self._modo_ligado_item.set_use_underline(False)
            self._modo_desligado_item = Gtk.RadioMenuItem(
                label=_("Desligado"), group=self._modo_ligado_item)
            self._modo_desligado_item.set_use_underline(False)
            for item, ligado in ((self._modo_ligado_item, True),
                                 (self._modo_desligado_item, False)):
                item.connect("activate", self._ao_escolher_o_modo, ligado)
                self._menu.append(item)

        if self.on_reconectar is not None:
            item = Gtk.MenuItem(label=_("Reconectar controles"))
            item.set_use_underline(False)
            item.connect("activate", lambda _w: self._chamar_sem_cair(
                self.on_reconectar))
            self._menu.append(item)

    def _montar_os_atos_do_servico(self) -> None:
        """«Reiniciar o serviço» e o par «Parar»/«Ativar» — os da aba Sistema."""
        if self._menu is None or self.on_servico is None:
            return

        self._menu.append(Gtk.SeparatorMenuItem())

        reiniciar = Gtk.MenuItem(label=_("Reiniciar o serviço"))
        reiniciar.set_use_underline(False)
        reiniciar.connect("activate", lambda _w: self._chamar_sem_cair(
            lambda: self.on_servico("restart")))
        self._menu.append(reiniciar)

        self._servico_item = Gtk.MenuItem(label=_("Parar o serviço"))
        self._servico_item.set_use_underline(False)
        self._servico_item.connect("activate", self._ao_mexer_no_servico)
        self._menu.append(self._servico_item)

    def _ao_escolher_o_modo(self, item: Any, ligado: bool) -> None:
        """Só age no rádio que ACABOU de ser marcado, e nunca no eco da pintura."""
        if self._pintando_o_modo or not item.get_active():
            return
        if self.on_set_modo is not None:
            self._chamar_sem_cair(lambda: self.on_set_modo(ligado))

    def _ao_mexer_no_servico(self, _item: Any) -> None:
        """Para quando está de pé; liga quando está parado."""
        if self.on_servico is None:
            return
        self._chamar_sem_cair(
            lambda: self.on_servico("stop" if self._servico_de_pe else "start"))

    @staticmethod
    def _chamar_sem_cair(acao: Any) -> None:
        """O tray NUNCA cai por causa de um clique — nem por IPC, nem por bug."""
        try:
            acao()
        except Exception as erro:
            logger.warning("apptray_acao_falhou", erro=str(erro))

    def _pintar_o_estado_dos_atos(self, state: dict[str, Any] | None) -> None:
        """Põe os rótulos e as posições no estado de AGORA, a cada tique."""
        de_pe = isinstance(state, dict)
        self._servico_de_pe = de_pe
        if self._servico_item is not None:
            self._servico_item.set_label(
                _("Parar o serviço") if de_pe else _("Ativar o serviço"))

        if self._modo_ligado_item is None:
            return
        ligado = self._modo_de_agora(state)
        if ligado is None:
            return
        alvo = self._modo_ligado_item if ligado else self._modo_desligado_item
        if alvo is not None and not alvo.get_active():
            self._pintando_o_modo = True
            try:
                alvo.set_active(True)
            finally:
                self._pintando_o_modo = False

    @staticmethod
    def _modo_de_agora(state: dict[str, Any] | None) -> bool | None:
        """`True` Ligado · `False` Desligado · `None` não se sabe."""
        if not isinstance(state, dict):
            return None
        try:
            from hefesto_dualsense4unix.app.actions.jogar import painel
        except Exception:  # pragma: no cover — ambiente sem o motor
            return None
        try:
            return painel.hefesto_ligado(state)
        except Exception:
            return None

    def _tick_refresh(self) -> bool:
        """Dispara a coleta de perfis + estado em thread worker (não bloqueia GTK)."""
        if self._refresh_inflight:
            return True
        self._refresh_inflight = True
        from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread

        run_in_thread(
            self._collect_refresh_data,
            self._on_refresh_done,
            self._on_refresh_failed,
        )
        return True

    def _collect_refresh_data(
        self,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Coleta perfis e estado no worker (bloqueante, FORA da thread GTK)."""
        profiles = self.on_list_profiles()
        state: dict[str, Any] | None = None
        if self.on_state is not None:
            try:
                state = self.on_state()
            except Exception:
                state = None
        return profiles, state

    def _on_refresh_done(self, data: Any) -> bool:
        """Callback de sucesso (thread GTK via GLib.idle_add): renderiza tudo."""
        self._refresh_inflight = False
        profiles, state = data
        self._render_profiles(
            profiles, self._controllers_suffix_from_state(state)
        )
        self._pintar_o_estado_dos_atos(state)
        return False

    def _on_refresh_failed(self, _exc: Exception) -> bool:
        """Callback de falha (thread GTK): só libera o guard; mantém UI estável."""
        self._refresh_inflight = False
        return False


    @staticmethod
    def _controllers_suffix_from_state(state: dict[str, Any] | None) -> str:
        """' · N controles (BT + USB)' quando há 2+ conectados; '' caso contrário."""
        if not isinstance(state, dict):
            return ""
        controllers = state.get("controllers")
        if not isinstance(controllers, list):
            return ""
        conectados = [
            c for c in controllers if isinstance(c, dict) and c.get("connected")
        ]
        if len(conectados) <= 1:
            return ""
        transportes = " + ".join(
            (c.get("transport") or "?").upper() for c in conectados
        )
        return _(" · %(n)d controles (%(t)s)") % {
            "n": len(conectados),
            "t": transportes,
        }

    def _render_profiles(
        self, profiles: list[dict[str, Any]], controllers_suffix: str = ""
    ) -> None:
        if self._profiles_submenu is None:
            return
        for item in self._profile_menu_items:
            self._profiles_submenu.remove(item)
        self._profile_menu_items = []

        if not profiles:
            item = Gtk.MenuItem.new_with_label(_("(nenhum perfil)"))
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
            # remover o numero de perfis"*. <!-- noqa-acento: citação dela -->
            label = (
                _("Hefesto - DualSense4Unix - perfil: %s") % active
                if active
                else _("Hefesto - DualSense4Unix")
            )
            self._status_item.set_label(label + controllers_suffix)

    def _ensinar_o_caminho_do_icone(self, icone: str) -> None:
        """Diz ao PAINEL onde o arquivo do ícone mora, em vez de só o nome."""
        definir_caminho = getattr(self._indicator, "set_icon_theme_path", None)
        if definir_caminho is None:
            return
        bases = (
            Path.home() / ".local/share/icons/hicolor",
            Path("/usr/share/icons/hicolor"),
            Path("/usr/local/share/icons/hicolor"),
        )
        for base in bases:
            for sufixo in ("symbolic/apps", "scalable/apps", "256x256/apps"):
                pasta = base / sufixo
                for ext in (".svg", ".png"):
                    if (pasta / f"{icone}{ext}").is_file():
                        definir_caminho(str(pasta))
                        logger.info("tray_icon_theme_path", pasta=str(pasta), icone=icone)
                        return
        logger.info("tray_icon_sem_arquivo_no_disco", icone=icone)

    @staticmethod
    def _preferred_icon() -> str:
        """Nome do ícone a pedir ao painel, em ordem de preferência."""
        theme = Gtk.IconTheme.get_default()
        if theme is None:
            return TRAY_ICON_FALLBACK
        ordem = (
            (TRAY_ICON_NAME, TRAY_ICON_NAME_LEGADO)
            if _painel_recolore_simbolico()
            else (TRAY_ICON_NAME_LEGADO, TRAY_ICON_NAME)
        )
        for nome in ordem:
            if theme.has_icon(nome):
                return nome
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
