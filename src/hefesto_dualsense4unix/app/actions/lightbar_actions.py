"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import led_set, player_leds_set


class LightbarActionsMixin(WidgetAccessMixin):
    """Controla a aba Lightbar + Player LEDs."""

    _current_rgb: tuple[int, int, int] = (255, 128, 0)
    # Luminosidade em [0.0, 1.0]; 1.0 = máximo (FEAT-LED-BRIGHTNESS-01).
    _current_brightness: float = 1.0
    # Valor pendente de brightness a persistir no próximo save de perfil.
    # Usado enquanto FEAT-PROFILE-STATE-01 (DraftConfig) não está disponível.
    _pending_brightness: float = 1.0
    # Guard para bloquear o handler durante refresh programático do slider.
    _refresh_guard: bool = False

    def _edit_uniq(self) -> str | None:
        """MAC do controle em edição (PERFIL-04); None = edição global.

        Vem do seletor de alvo do banner (``StatusActionsMixin`` mantém
        ``_edit_target_uniq`` em sync com o daemon). getattr defensivo: o
        mixin pode ser instanciado sozinho em testes.
        """
        return getattr(self, "_edit_target_uniq", None)

    def _persist_leds_update(self, update: dict[str, Any]) -> None:
        """Grava campos de LEDs no draft — no GLOBAL ou no override do alvo.

        PERFIL-04 (sprint perfis-por-controle): com um controle selecionado
        no seletor do banner, a edição cai em ``draft.controllers[uniq].leds``
        — semeada com o que está NA TELA (o efetivo do alvo), então mudar só
        a cor preserva brilho/player-LEDs exibidos. É o que faz o "Salvar
        Perfil" do rodapé persistir o ajuste DENTRO do perfil, por controle
        ("configurei pro 1-BT, fica salvo pra ele dentro do meu perfil").

        Em "Todos", seção global do draft — E o campo editado sai dos
        overrides por-controle (fix HIGH do review 2026-07-16), espelhando a
        regra que o backend aplica ao vivo: sem a limpeza, "mudei todos para
        azul" + "Salvar Perfil" ressuscitava a cor antiga do alvo na próxima
        ativação. Cor e brilho saem JUNTOS (formam um único campo — o RGB
        pré-escalado — no estado desejado do backend).
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        uniq = self._edit_uniq()
        if uniq is None:
            new_leds = draft.leds.model_copy(update=update)
            draft = draft.model_copy(update={"leds": new_leds})
            campos: set[str] = set()
            if "lightbar_rgb" in update or "lightbar_brightness" in update:
                campos |= {"lightbar", "lightbar_brightness"}
            if "player_leds" in update:
                campos.add("player_leds")
            if campos:
                draft = draft.with_override_fields_cleared("leds", campos)
            self.draft = draft
            return
        base = draft.effective_leds_for(uniq)
        self.draft = draft.with_controller_leds(uniq, base.model_copy(update=update))

    def _refresh_lightbar_from_draft(self) -> None:
        """Popula widgets da aba Lightbar a partir do draft.

        PERFIL-04: exibe os LEDs EFETIVOS do alvo de edição atual — o
        override por-controle quando existe (brilho incluso, lido do PERFIL,
        não do backend), senão a seção global. Protegido por _refresh_guard
        para não disparar handlers de signal durante a atualização
        programatica dos widgets.
        """
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._refresh_guard = True
        try:
            leds = draft.effective_leds_for(self._edit_uniq())
            # Cor RGB
            if leds.lightbar_rgb is not None:
                r, g, b = leds.lightbar_rgb
                self._current_rgb = (r, g, b)
                button: Gtk.ColorButton = self._get("lightbar_color_button")
                if button is not None:
                    rgba = Gdk.RGBA()
                    rgba.red = r / 255.0
                    rgba.green = g / 255.0
                    rgba.blue = b / 255.0
                    rgba.alpha = 1.0
                    button.set_rgba(rgba)
            # Brightness
            pct = float(leds.lightbar_brightness)
            self._current_brightness = pct / 100.0
            self._pending_brightness = self._current_brightness
            scale: Gtk.Scale = self._get("lightbar_brightness_scale")
            if scale is not None:
                scale.set_value(pct)
            # Player LEDs
            for i, state in enumerate(leds.player_leds, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(bool(state))
            # Repinta preview
            preview: Gtk.DrawingArea = self._get("lightbar_preview")
            if preview is not None:
                preview.queue_draw()
        finally:
            self._refresh_guard = False

    def install_lightbar_tab(self) -> None:
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.connect("draw", self._on_lightbar_preview_draw)
        # Seta cor inicial programaticamente (Glade não suporta inline
        # RGBA com syntax "rgb(...)" sem segfault em todas as versões).
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            rgba = Gdk.RGBA()
            rgba.red = 1.0
            rgba.green = 128 / 255
            rgba.blue = 0.0
            rgba.alpha = 1.0
            button.set_rgba(rgba)
            self._current_rgb = (255, 128, 0)

    # --- signals lightbar ---

    def on_lightbar_color_set(self, button: Gtk.ColorButton) -> None:
        if self._refresh_guard:
            return
        rgba = button.get_rgba()
        self._current_rgb = (
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        # Atualiza draft (global ou override do alvo — PERFIL-04)
        self._persist_leds_update({"lightbar_rgb": self._current_rgb})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_apply(self, _btn: Gtk.Button) -> None:
        ok = led_set(self._current_rgb, brightness=self._current_brightness)
        pct = round(self._current_brightness * 100)
        self._toast_light(
            f"Cor RGB {self._current_rgb} a {pct}% aplicada"
            if ok
            else "Falha (daemon offline?)"
        )

    def on_lightbar_brightness_changed(self, scale: Gtk.Scale) -> None:
        """Slider 0-100 (%) -> atualiza luminosidade corrente e repinta prévia.

        Não aplica no hardware automaticamente; o usuário confirma via botao
        "Aplicar no controle". Assim evitamos flood de IPC durante arrasto.
        Guard _refresh_guard previne loop quando _refresh_lightbar_from_draft
        atualiza o slider programaticamente (FEAT-LED-BRIGHTNESS-03).
        """
        if self._refresh_guard:
            return
        raw = float(scale.get_value())
        # Clamp defensivo: GtkAdjustment ja limita, mas nunca confie cego.
        pct = max(0.0, min(100.0, raw))
        self._current_brightness = pct / 100.0
        self._pending_brightness = self._current_brightness
        # Atualiza draft com novo valor de brightness (global ou override do
        # alvo — PERFIL-04).
        self._persist_leds_update({"lightbar_brightness": round(pct)})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_off(self, _btn: Gtk.Button) -> None:
        self._current_rgb = (0, 0, 0)
        rgba = Gdk.RGBA()
        rgba.red = 0.0
        rgba.green = 0.0
        rgba.blue = 0.0
        rgba.alpha = 1.0
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            button.set_rgba(rgba)
        # B2: espelha a cor preta no draft (mesmo mecanismo de
        # on_lightbar_color_set). Sem isso, "Apagar" + "Salvar Perfil" gravava a
        # cor antiga e revisitar a aba repintava a cor anterior.
        self._persist_leds_update({"lightbar_rgb": self._current_rgb})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()
        ok = led_set((0, 0, 0))
        self._toast_light("Lightbar apagada" if ok else "Falha (daemon offline?)")

    # --- signals player leds ---

    def on_player_leds_preset_all(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([True] * 5)

    def on_player_leds_preset_p1(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False, False, True, False, False])

    def on_player_leds_preset_p2(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False, True, False, True, False])

    def on_player_leds_preset_p3(self, _btn: Gtk.Button) -> None:
        # FEAT-COOP-PLAYER-LED-01: padrões canônicos P3/P4 (os mesmos que o
        # co-op local aplica por controle) também disponíveis como preset.
        self._set_player_leds([True, False, True, False, True])

    def on_player_leds_preset_p4(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([True, True, False, True, True])

    def on_player_leds_preset_none(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False] * 5)

    def on_player_leds_apply(self, _btn: Gtk.Button) -> None:
        """Reenvia o padrão atual dos 5 checkboxes ao hardware
        (BUG-PLAYER-LEDS-APPLY-01).

        Botão explícito para o fluxo pedido pelo usuário: marcar o padrão,
        clicar em "Aplicar LEDs" e ver o controle refletir. Também útil para
        reemitir o bitmask após reconectar o controle ou trocar de perfil
        (quando o autoswitch já foi aplicado mas o usuário quer confirmar).
        """
        if self._refresh_guard:
            return
        bits = self.get_current_player_leds()
        # Atualiza draft — mantém consistência com on_player_led_toggled.
        self._persist_leds_update({"player_leds": bits})
        ok = player_leds_set(bits)
        label = " ".join("x" if b else "-" for b in bits)
        self._toast_light(
            f"Player LEDs aplicados: {label}"
            if ok
            else f"Player LEDs: {label} (daemon offline?)"
        )

    def on_player_led_toggled(self, _checkbox: Gtk.CheckButton) -> None:
        """Sinal de toggle de qualquer checkbox de player LED.

        Recalcula o bitmask completo dos 5 checkboxes e envia ao hardware via IPC.
        Pula silenciosamente quando `_player_leds_batch_guard` esta ativo (preset
        em andamento faz o envio final ele mesmo, evitando 5 IPCs redundantes).
        """
        if self._refresh_guard:
            return
        if getattr(self, "_player_leds_batch_guard", False):
            return
        bits = self.get_current_player_leds()
        # Atualiza draft (global ou override do alvo — PERFIL-04)
        self._persist_leds_update({"player_leds": bits})
        ok = player_leds_set(bits)
        label = " ".join("x" if b else "-" for b in bits)
        self._toast_light(
            f"Player LEDs: {label}" if ok else f"Player LEDs: {label} (daemon offline?)"
        )

    # --- helpers ---

    def _set_player_leds(self, pattern: list[bool]) -> None:
        """Atualiza checkboxes e envia bitmask ao hardware via IPC (1 chamada).

        Aplica `_player_leds_batch_guard` enquanto atualiza os 5 checkboxes para
        evitar que `on_player_led_toggled` dispare IPCs redundantes -- so envia
        o bitmask final ao fim, em uma chamada unica.
        """
        self._player_leds_batch_guard = True
        try:
            for i, state in enumerate(pattern, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(state)
        finally:
            self._player_leds_batch_guard = False
        bits: tuple[bool, bool, bool, bool, bool] = (
            pattern[0], pattern[1], pattern[2], pattern[3], pattern[4]
        )
        # Atualiza draft (global ou override do alvo — PERFIL-04)
        self._persist_leds_update({"player_leds": bits})
        ok = player_leds_set(bits)
        label = " ".join("x" if s else "-" for s in pattern)
        self._toast_light(
            f"Player LEDs: {label}" if ok else f"Player LEDs: {label} (daemon offline?)"
        )

    def get_current_player_leds(self) -> tuple[bool, bool, bool, bool, bool]:
        states: list[bool] = []
        for i in range(1, 6):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            states.append(bool(checkbox.get_active()) if checkbox is not None else False)
        return (states[0], states[1], states[2], states[3], states[4])

    def _on_lightbar_preview_draw(
        self, widget: Gtk.DrawingArea, cairo_ctx: Any
    ) -> bool:
        alloc = widget.get_allocation()
        r, g, b = self._current_rgb
        # Pré-visualização respeita a luminosidade corrente para dar feedback
        # imediato do slider antes de aplicar no hardware.
        level = max(0.0, min(1.0, self._current_brightness))
        cairo_ctx.set_source_rgb(
            (r / 255) * level,
            (g / 255) * level,
            (b / 255) * level,
        )
        cairo_ctx.rectangle(0, 0, alloc.width, alloc.height)
        cairo_ctx.fill()
        return False

    def _toast_light(self, msg: str) -> None:
        self._status_toast("light", msg)
