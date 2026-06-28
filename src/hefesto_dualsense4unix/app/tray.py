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

import contextlib
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
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TRAY_APP_ID = "hefesto-dualsense4unix"
TRAY_ICON_NAME = "hefesto-dualsense4unix"
TRAY_ICON_FALLBACK = "input-gaming"
PROFILE_REFRESH_SEC = 3
ACTIVE_MARKER = "> "

# FEAT-COSMIC-TRAY-FALLBACK-01: delay para registrar o indicator depois que o
# cosmic-applet-status-area subir o watcher. Aumentado para 1500ms em
# BUG-TRAY-COSMIC-MISSING-NOTIFY-SPAM-01 — em COSMIC 1.0.6+ o watcher pode
# levar até ~1s para ser registrado após o login, e disparar o probe antes
# disso gerava notificação "Tray icon indisponivel" falsa a cada login.
_INDICATOR_DEFERRED_MS = 1500

#: Número de tentativas do probe `statusnotifierwatcher_available` antes de
#: notificar o usuário (BUG-TRAY-COSMIC-MISSING-NOTIFY-SPAM-01). Cada tentativa
#: separada por `_WATCHER_PROBE_RETRY_MS`. Total: até ~3s de tolerância.
_WATCHER_PROBE_RETRIES = 3
_WATCHER_PROBE_RETRY_MS = 1000

#: Flag persistente entre sessões — se existir, não emite o aviso de
#: "tray indisponível no COSMIC" novamente. Usuário pode apagar manualmente
#: para receber o aviso de novo (ou setar `HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING=1`).
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
QuitFn = Callable[[], None]
ListProfilesFn = Callable[[], list[dict[str, Any]]]
SwitchProfileFn = Callable[[str], bool]
#: Snapshot de `daemon.state_full` (ou None se offline) — usado para o tray
#: mostrar quantos controles estão conectados (FEAT-DSX-MULTI-CONTROLLER-01).
StateFn = Callable[[], dict[str, Any] | None]


@dataclass
class AppTray:
    """Controla o tray; ao clicar abre janela, 'Sair' encerra o processo."""

    on_show_window: ShowFn
    on_quit: QuitFn
    on_list_profiles: ListProfilesFn
    on_switch_profile: SwitchProfileFn
    #: Opcional: snapshot de estado para o status item mostrar "N controles".
    #: None (default) mantém o comportamento antigo (só perfil).
    on_state: StateFn | None = None

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

        self._status_item = Gtk.MenuItem(label=_("Hefesto - Dualsense4Unix (carregando...)"))
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        show = Gtk.MenuItem(label=_("Abrir painel"))
        show.connect("activate", lambda _w: self.on_show_window())
        self._menu.append(show)

        self._menu.append(Gtk.SeparatorMenuItem())

        self._profiles_item = Gtk.MenuItem(label=_("Perfis"))
        self._profiles_submenu = Gtk.Menu()
        # TRAY-LOADING-ZOMBIE-01: nascido vazio — `_render_profiles` é fonte
        # única de verdade do submenu. Estado inicial "(nenhum perfil)" é
        # produzido logo abaixo via `_render_profiles([])`, garantindo que
        # 100% dos itens estejam em `_profile_menu_items`.
        self._profiles_item.set_submenu(self._profiles_submenu)
        self._menu.append(self._profiles_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label=_("Sair do Hefesto - Dualsense4Unix"))
        quit_item.connect("activate", lambda _w: self.on_quit())
        self._menu.append(quit_item)

        # Popula submenu Perfis via path canônico antes do show_all.
        self._render_profiles([])

        self._menu.show_all()
        self._indicator.set_menu(self._menu)

        GLib.timeout_add_seconds(PROFILE_REFRESH_SEC, self._tick_refresh)
        self._tick_refresh()

        logger.info("apptray_started", icon=icon)

        # FEAT-COSMIC-TRAY-FALLBACK-01 + BUG-TRAY-COSMIC-MISSING-NOTIFY-SPAM-01:
        # probe do StatusNotifierWatcher com retries e flag persistente.
        # Antes notificava no primeiro probe falhado (race contra o subir do
        # cosmic-applet-status-area) e reemitia a cada sessão da GUI — virou
        # a fonte recorrente do "ele fica falando que tem algo não instalado"
        # ao ligar o PC. Agora: 3 tentativas com 1s entre, e flag persistente
        # — depois de avisado uma vez, nunca mais notifica até o usuário
        # apagar o arquivo (ou setar HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING=1).
        if _desktop_is_cosmic():
            GLib.timeout_add(
                _WATCHER_PROBE_RETRY_MS,
                lambda: self._probe_watcher_with_retries(0),
            )

        return True

    def _probe_watcher_with_retries(self, attempt: int) -> bool:
        """Probe StatusNotifierWatcher com retries — só notifica se TODAS falharem.

        BUG-TRAY-COSMIC-MISSING-NOTIFY-SPAM-01.

        Retorna sempre ``False`` (callback one-shot do GLib): cada tentativa
        reagenda a próxima internamente via novo ``timeout_add``, então a
        source que disparou esta chamada nunca deve se repetir sozinha.
        """
        if statusnotifierwatcher_available():
            logger.debug("statusnotifierwatcher_disponivel_apos_retry", attempt=attempt)
            return False
        if attempt + 1 < _WATCHER_PROBE_RETRIES:
            GLib.timeout_add(
                _WATCHER_PROBE_RETRY_MS,
                lambda: self._probe_watcher_with_retries(attempt + 1),
            )
            return False
        # Esgotou as tentativas: avisa SE ainda não avisou em sessão anterior.
        self._maybe_notify_tray_missing()
        return False

    @staticmethod
    def _maybe_notify_tray_missing() -> None:
        """Emite notify de tray indisponível só se ainda não avisou (flag persistente).

        BUG-TRAY-COSMIC-MISSING-NOTIFY-SPAM-01: usuário não quer receber o
        mesmo aviso a cada login. Verifica `runtime_dir/cosmic_tray_warned.flag`
        — se existe, no-op. Senão, notifica e cria a flag. Honra env opt-in
        `HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING=1` para forçar reemissão.
        """
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
            summary="Hefesto - Dualsense4Unix",
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
                    "Hefesto - Dualsense4Unix tray warning shown.\n", encoding="utf-8"
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

    def _tick_refresh(self) -> bool:
        profiles = self.on_list_profiles()
        self._render_profiles(profiles, self._controllers_suffix())
        return True

    def _controllers_suffix(self) -> str:
        """' · N controles (BT + USB)' quando há 2+ conectados; '' caso contrário.

        FEAT-DSX-MULTI-CONTROLLER-01: deixa visível no tray que mais de um
        controle está conectado (todos recebem o output em broadcast). Tolera
        daemon offline/sem o bloco `controllers` (versão antiga) caindo em ''.
        """
        if self.on_state is None:
            return ""
        try:
            state = self.on_state()
        except Exception:  # tray nunca cai por falha de IPC
            return ""
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
            # TRAY-UNDERSCORE-MNEMONIC-01: `new_with_label` cria com
            # use_underline=False por default; reforço com setter para
            # robustez frente a backports/forks. Sem isso, labels com `_`
            # são interpretadas como mnemonics e ficam com `__` no rendering
            # dbusmenu (StatusNotifierItem).
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
            label = (
                _("Hefesto - Dualsense4Unix - perfil: %s") % active
                if active
                else _("Hefesto - Dualsense4Unix - %d perfis") % len(profiles)
            )
            self._status_item.set_label(label + controllers_suffix)

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
