"""Aba Mouse: liga/desliga emulação de mouse+teclado via DualSense (FEAT-MOUSE-01)."""
# ruff: noqa: E402
from __future__ import annotations

import os
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

UINPUT_DEV = "/dev/uinput"

MAPPING_LEGEND = (
    # ADR-011: glyphs Geometric Shape via NCR (&#...;) — o sanitizer de
    # anonimato strippa o literal /; a entidade Pango renderiza igual.
    "<b>Mapeamento:</b>\n"
    "Cruz (X) ou L2 → botão esquerdo\n"
    "Triângulo (&#9651;) ou R2 → botão direito\n"
    "R3 (clique no analógico direito) → botão do meio\n"
    "Círculo (&#9675;) → Enter\n"
    "Quadrado (&#9633;) → Esc\n"
    "D-pad (↑↓←→) → setas do teclado\n"
    "Analógico esquerdo → movimento do cursor\n"
    "Analógico direito → rolagem vertical e horizontal\n"
    "\n"
    "<b>Modo jogo:</b> segure o botão PS para suspender a emulação de "
    "mouse/teclado (e segure de novo para retomar)."
)


class MouseActionsMixin(WidgetAccessMixin):
    """Controla a aba Mouse."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _guard_refresh: bool = False

    # Coalescing dos sliders (BUG-MOUSE-GUI-SYNC-01): um RPC em voo por
    # parâmetro; valores emitidos durante o voo guardam só o ÚLTIMO.
    # Lazy-init em _send_mouse_param_async (mixin não tem __init__ próprio).
    _mouse_inflight: dict[str, bool] | None = None
    _mouse_pending: dict[str, int] | None = None

    def _refresh_mouse_from_draft(self) -> None:
        """Popula widgets da aba Mouse a partir de self.draft.mouse.

        Protegido por _guard_refresh para não disparar handlers de signal
        durante a atualização programatica dos widgets.
        """
        if self._guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._guard_refresh = True
        try:
            mouse = draft.mouse
            toggle: Gtk.Switch = self._get("mouse_emulation_toggle")
            if toggle is not None:
                toggle.set_active(mouse.enabled)
            speed_scale: Gtk.Scale = self._get("mouse_speed_scale")
            if speed_scale is not None:
                speed_scale.set_value(float(mouse.speed))
            scroll_scale: Gtk.Scale = self._get("mouse_scroll_speed_scale")
            if scroll_scale is not None:
                scroll_scale.set_value(float(mouse.scroll_speed))
        finally:
            self._guard_refresh = False

    def install_mouse_tab(self) -> None:
        # mouse_legend_label foi substituído por GtkFrame estático (UI-MOUSE-CLEANUP-01).
        # Mantém compatibilidade caso o widget ainda exista em alguma versão do GLADE.
        legend = self._get("mouse_legend_label")
        if legend is not None:
            legend.set_markup(MAPPING_LEGEND)
        self._refresh_mouse_view()

    # --- sincronização com o estado vivo do daemon (BUG-MOUSE-GUI-SYNC-01 A1) ---

    def _refresh_mouse_tab(self) -> None:
        """Refresh completo da aba Mouse: draft imediato + estado vivo assíncrono."""
        self._refresh_mouse_from_draft()
        self._refresh_mouse_from_daemon_async()

    def _refresh_mouse_from_daemon_async(self) -> None:
        """Sincroniza a aba Mouse com o bloco ``mouse_emulation`` vivo do daemon.

        A1: o draft nasce do PERFIL (que não tem seção mouse) — sem esta rota a
        aba mente quando a emulação foi ligada por CLI/applet/flag de boot.
        Assíncrono (call_async) para não bloquear a thread GTK; widgets são
        atualizados sob ``_guard_refresh`` via ``_refresh_mouse_from_draft``.
        NÃO marca ``dirty`` — sincronização programática não é toque da usuária.
        """
        def _on_state(state: Any) -> bool:
            me = state.get("mouse_emulation") if isinstance(state, dict) else None
            if not isinstance(me, dict):
                return False
            draft = getattr(self, "draft", None)
            if draft is None:
                return False
            # BUG-MOUSE-SLIDER-PREF-LOSS-01: se a usuária tem uma edição pendente
            # (dirty — ex.: arrastou o slider com a emulação OFF, que só atualiza
            # o draft sem IPC), NÃO sobrepor com o estado vivo: sobrescrever
            # apagaria a preferência e ainda persistiria o valor do daemon como
            # se fosse escolha dela. O estado vivo re-sincroniza após Aplicar.
            # BUG-MOUSE-OVERLAY-CLOBBERS-SECTION-01: idem para perfil COM seção
            # mouse (in_profile) — a aba mostra o valor do PERFIL (= o que será
            # salvo); sobrepor o vivo faria o Salvar Perfil clobberar a seção.
            if draft.mouse.dirty or draft.mouse.in_profile:
                return False
            try:
                new_mouse = draft.mouse.model_copy(
                    update={
                        "enabled": bool(me.get("enabled", False)),
                        "speed": int(me.get("speed", draft.mouse.speed)),
                        "scroll_speed": int(
                            me.get("scroll_speed", draft.mouse.scroll_speed)
                        ),
                    }
                )
            except (TypeError, ValueError) as exc:
                logger.warning("mouse_state_full_bloco_invalido", erro=str(exc))
                return False
            self.draft = draft.model_copy(update={"mouse": new_mouse})
            self._refresh_mouse_from_draft()
            return False

        def _on_err(_exc: Exception) -> bool:
            # Daemon offline: mantém o draft atual (defaults seguros).
            return False

        ipc_bridge.call_async(
            "daemon.state_full", {}, on_success=_on_state, on_failure=_on_err
        )

    # --- handlers de UI ---

    def on_mouse_toggle_set(self, switch: Gtk.Switch, _state: Any) -> bool:
        if self._guard_refresh:
            return False
        enabled = bool(switch.get_active())
        speed = self._read_speed("mouse_speed_scale", DEFAULT_MOUSE_SPEED)
        scroll = self._read_speed("mouse_scroll_speed_scale", DEFAULT_SCROLL_SPEED)

        def _on_ok(result: Any) -> bool:
            if isinstance(result, dict) and result.get("status") != "ok":
                return _on_err(RuntimeError("daemon respondeu status=failed"))
            draft = getattr(self, "draft", None)
            if draft is not None:
                new_mouse = draft.mouse.model_copy(
                    update={
                        "enabled": enabled,
                        "speed": speed,
                        "scroll_speed": scroll,
                        "dirty": True,
                    }
                )
                self.draft = draft.model_copy(update={"mouse": new_mouse})
            status = "ligado" if enabled else "desligado"
            self._toast_mouse(f"Mouse emulado {status}")
            self._refresh_mouse_view()
            return False

        def _on_err(_exc: Exception) -> bool:
            self._toast_mouse(
                "Falha ao comunicar com o daemon. Mouse não alterado."
            )
            # BUG-MOUSE-TOGGLE-STALE-REVERT-01: reverte para o último estado
            # CONFIRMADO (draft.mouse.enabled só muda no sucesso), não para
            # ``not enabled`` capturado no clique — com dois toggles rápidos e
            # daemon travado, ``not enabled`` do 2º RPC deixava o switch preso
            # ON. Reverter para o confirmado converge ao estado real do daemon.
            draft = getattr(self, "draft", None)
            confirmed = draft.mouse.enabled if draft is not None else not enabled
            self._revert_mouse_toggle(confirmed)
            return False

        ipc_bridge.call_async(
            "mouse.emulation.set",
            {"enabled": enabled, "speed": speed, "scroll_speed": scroll},
            on_success=_on_ok,
            on_failure=_on_err,
        )
        # Otimista: o default handler aplica o estado; falha reverte no callback.
        return False

    def _revert_mouse_toggle(self, active: bool) -> None:
        """Reverte o switch sem reentrar no handler (BUG-MOUSE-GUI-SYNC-01 A3).

        Em GTK3, ``set_active`` reemite ``state-set`` SINCRONAMENTE (``return
        True`` no handler não evita — repro real: 999 reentradas +
        RecursionError). Salva/restaura ``_guard_refresh`` em vez de zerar
        absoluto: o revert pode disparar dentro de um refresh programático que
        mantém o guard True (padrão do fix ``_update_preset_to_custom``).
        """
        switch = self._get("mouse_emulation_toggle")
        if switch is None:
            return
        prev_guard = self._guard_refresh
        self._guard_refresh = True
        try:
            switch.set_active(active)
        finally:
            self._guard_refresh = prev_guard

    def on_mouse_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._guard_refresh:
            return
        speed = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_mouse = draft.mouse.model_copy(update={"speed": speed, "dirty": True})
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        self._send_mouse_param_async("speed", speed)

    def on_mouse_scroll_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._guard_refresh:
            return
        scroll = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_mouse = draft.mouse.model_copy(
                update={"scroll_speed": scroll, "dirty": True}
            )
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        self._send_mouse_param_async("scroll_speed", scroll)

    def _send_mouse_param_async(self, param: str, value: int) -> None:
        """Envia UM parâmetro de velocidade via IPC, SEM ``enabled`` (A4).

        O payload speed-only cai na rota do daemon que atualiza config e device
        (se existir) sem start/stop nem persistir o flag — religar a emulação
        pelo slider é impossível por construção, mesmo com toggle stale-ON.

        Coalescing simples: um RPC em voo por parâmetro; mudanças durante o voo
        guardam só o último valor, reenviado ao terminar. Falha é silenciosa
        (slider é gesto contínuo; toast por tick poluiria a statusbar).
        """
        if self._mouse_inflight is None or self._mouse_pending is None:
            self._mouse_inflight = {}
            self._mouse_pending = {}
        inflight = self._mouse_inflight
        pending = self._mouse_pending
        if inflight.get(param):
            pending[param] = value
            return
        inflight[param] = True

        def _finish() -> None:
            inflight[param] = False
            próximo = pending.pop(param, None)
            if próximo is not None and próximo != value:
                self._send_mouse_param_async(param, próximo)

        def _on_ok(_result: Any) -> bool:
            _finish()
            return False

        def _on_err(exc: Exception) -> bool:
            logger.debug("mouse_param_async_falhou", param=param, erro=str(exc))
            _finish()
            return False

        ipc_bridge.call_async(
            "mouse.emulation.set",
            {param: int(value)},
            on_success=_on_ok,
            on_failure=_on_err,
        )

    # --- helpers ---

    def _read_speed(self, widget_id: str, default: int) -> int:
        w = self._get(widget_id)
        if w is None:
            return default
        return int(w.get_value())

    def _mouse_is_enabled(self) -> bool:
        toggle = self._get("mouse_emulation_toggle")
        return bool(toggle and toggle.get_active())

    def _refresh_mouse_view(self) -> None:
        label = self._get("mouse_uinput_status_label")
        if label is None:
            return
        try:
            import uinput  # noqa: F401
            module_ok = True
        except ImportError:
            module_ok = False

        dev_exists = os.path.exists(UINPUT_DEV)
        dev_writable = os.access(UINPUT_DEV, os.W_OK) if dev_exists else False

        if module_ok and dev_writable:
            label.set_markup(
                '<span foreground="#2d8">uinput disponível</span>'
            )
        elif module_ok and dev_exists:
            label.set_markup(
                '<span foreground="#d33">sem permissão em /dev/uinput — '
                'rode ./scripts/install_udev.sh</span>'
            )
        elif module_ok:
            label.set_markup(
                '<span foreground="#c90">módulo ok, /dev/uinput ausente '
                '(modprobe uinput)</span>'
            )
        else:
            label.set_markup(
                '<span foreground="#d33">python-uinput não instalado '
                '(pip install python-uinput)</span>'
            )

    def _toast_mouse(self, msg: str) -> None:
        self._status_toast("mouse", msg)


__all__ = ["MAPPING_LEGEND", "UINPUT_DEV", "MouseActionsMixin"]

# "Conhece-te a ti mesmo." — Sócrates
