"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import led_set, player_leds_set

#: Aviso D4 (sprint cores-e-led-automaticos): cor única em "Todos" com o
#: automático ligado seria INVISÍVEL (a paleta vence o global no merge do
#: backend) — então o fluxo desliga o toggle e avisa, nunca em popup.
_AVISO_D4 = "Cores automáticas desligadas para aplicar uma cor única"


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

    def _auto_preview_slot(self) -> int | None:
        """Slot do controle em edição QUANDO a prévia deve mostrar a cor
        AUTOMÁTICA (achado ao vivo 2026-07-17).

        Com "Cores automáticas por controle" LIGADO e um controle específico
        selecionado no seletor do banner, o que ele EXIBE é a cor da paleta
        (azul/vermelho...), não a cor manual global — mas a prévia mostrava a
        manual (roxo), MENTINDO. O número vem do rótulo do alvo mantido pela
        aba Status (``_edit_target_label`` = "Controle N — BT"). ``None`` =
        mostrar a cor manual (automático desligado, ou alvo "Todos").
        """
        import re

        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return None
        if self._edit_uniq() is None:
            return None
        label = getattr(self, "_edit_target_label", None)
        if not isinstance(label, str):
            return None
        match = re.search(r"Controle\s+(\d+)", label)
        return int(match.group(1)) if match else None

    def _persist_leds_update(self, update: dict[str, Any]) -> bool:
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

        COR-04 (semântica D4): COR (``lightbar_rgb``) editada em "Todos" com
        o automático ligado também DESLIGA ``auto_player_colors`` no draft —
        senão a cor única seria invisível (a paleta automática vence o global
        no merge). Brilho e player-LEDs NÃO disparam o D4 (o brilho escala a
        própria paleta — D11 — e os player-LEDs não são cor). Devolve True
        quando o D4 desligou o automático AGORA (o chamador compõe o aviso
        ``_AVISO_D4`` no toast — visível, nunca popup); o checkbox da aba é
        sincronizado aqui mesmo, sob guard.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return False
        uniq = self._edit_uniq()
        if uniq is None:
            campos_update = dict(update)
            d4_disparou = bool(
                "lightbar_rgb" in campos_update and draft.leds.auto_player_colors
            )
            if d4_disparou:
                campos_update["auto_player_colors"] = False
            new_leds = draft.leds.model_copy(update=campos_update)
            draft = draft.model_copy(update={"leds": new_leds})
            campos: set[str] = set()
            if "lightbar_rgb" in update or "lightbar_brightness" in update:
                campos |= {"lightbar", "lightbar_brightness"}
            if "player_leds" in update:
                campos.add("player_leds")
            if campos:
                draft = draft.with_override_fields_cleared("leds", campos)
            self.draft = draft
            if d4_disparou:
                self._sync_auto_checkbox(False)
            return d4_disparou
        base = draft.effective_leds_for(uniq)
        self.draft = draft.with_controller_leds(uniq, base.model_copy(update=update))
        return False

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
            # COR-04: o checkbox "Cores automáticas por controle" reflete o
            # GLOBAL do draft (campo do PERFIL), nunca o efetivo do alvo — um
            # override por-controle não tem opinião sobre o toggle.
            auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
            if auto_check is not None:
                auto_check.set_active(bool(draft.leds.auto_player_colors))
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
            # Prévia HONESTA (achado ao vivo): com automático ligado + um
            # controle específico em edição, mostra a cor REAL da paleta desse
            # controle (o brilho é aplicado no draw, como no caminho manual) —
            # antes a prévia ficava roxa enquanto o controle estava azul.
            auto_slot = self._auto_preview_slot()
            if auto_slot is not None:
                from hefesto_dualsense4unix.core.led_control import player_slot_color

                self._current_rgb = player_slot_color(auto_slot)
                auto_btn: Gtk.ColorButton = self._get("lightbar_color_button")
                if auto_btn is not None:
                    ar, ag, ab = self._current_rgb
                    auto_rgba = Gdk.RGBA()
                    auto_rgba.red = ar / 255.0
                    auto_rgba.green = ag / 255.0
                    auto_rgba.blue = ab / 255.0
                    auto_rgba.alpha = 1.0
                    auto_btn.set_rgba(auto_rgba)
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
        # COR-04: widgets do automático conectados em CÓDIGO (não pelo Glade)
        # — o dict de ``_signal_handlers()`` vive em app.py, e a fiação aqui
        # segue o precedente do install_triggers_tab (SegmentedSelector).
        auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if auto_check is not None:
            auto_check.connect("toggled", self.on_auto_player_colors_toggled)
        reset_target: Gtk.Button = self._get("lightbar_auto_reset_target")
        if reset_target is not None:
            reset_target.connect("clicked", self.on_lightbar_auto_reset_target)
        reset_all: Gtk.Button = self._get("lightbar_auto_reset_all")
        if reset_all is not None:
            reset_all.connect("clicked", self.on_lightbar_auto_reset_all)

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
        # Atualiza draft (global ou override do alvo — PERFIL-04). Em "Todos"
        # com o automático ligado, o D4 desliga o toggle — aviso visível
        # (COR-04; sem outro toast por cima: escolher cor não tem toast).
        if self._persist_leds_update({"lightbar_rgb": self._current_rgb}):
            self._toast_light(_AVISO_D4)
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_apply(self, _btn: Gtk.Button) -> None:
        """Envia a cor da tela ao hardware.

        COR-04: em "Todos", a cor viaja JUNTO com o toggle do automático num
        único ``profile.apply_draft`` parcial (seção ``leds``) — o ``led.set``
        clássico gravaria só o default e a paleta automática (se ligada no
        daemon) venceria no próximo reassert ("apliquei e voltou colorido").
        O D4 roda antes: auto ligado é desligado no draft, com aviso composto
        no toast. Com um controle selecionado (ou sem draft — hosts parciais
        de teste), o fluxo por-controle clássico permanece: ``led.set``
        respeita o alvo do seletor e não mexe no toggle.
        """
        pct = round(self._current_brightness * 100)
        draft = getattr(self, "draft", None)
        d4_disparou = False
        if self._edit_uniq() is None and draft is not None:
            d4_disparou = self._d4_disable_auto_for_single_color()
            ok = ipc_bridge.apply_draft(
                {
                    "leds": {
                        "lightbar_rgb": list(self._current_rgb),
                        "lightbar_brightness": self._current_brightness,
                        "auto_player_colors": self.draft.leds.auto_player_colors,
                    }
                }
            )
        else:
            ok = led_set(self._current_rgb, brightness=self._current_brightness)
        msg = (
            f"Cor aplicada no controle ({pct}% de brilho)"
            if ok
            else "não consegui aplicar a cor — o Hefesto pode estar desligado "
            "(ligue na aba Sistema)"
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)

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
        # COR-04 (D4): apagar é aplicar a cor única preta — em "Todos" com o
        # automático ligado, o toggle desliga (senão a paleta reacenderia por
        # cima no próximo reassert) e o preto viaja com o toggle num único
        # apply_draft parcial, como no on_lightbar_apply.
        d4_disparou = self._persist_leds_update({"lightbar_rgb": self._current_rgb})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()
        draft = getattr(self, "draft", None)
        if self._edit_uniq() is None and draft is not None:
            ok = ipc_bridge.apply_draft(
                {
                    "leds": {
                        "lightbar_rgb": [0, 0, 0],
                        "auto_player_colors": draft.leds.auto_player_colors,
                    }
                }
            )
        else:
            ok = led_set((0, 0, 0))
        msg = "Lightbar apagada" if ok else "Falha (daemon offline?)"
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)

    # --- signals cores automáticas por controle (COR-04) ---

    def on_auto_player_colors_toggled(self, checkbox: Gtk.CheckButton) -> None:
        """Checkbox "Cores automáticas por controle" → ``draft.leds``.

        Campo do PERFIL: grava SEMPRE na seção GLOBAL do draft, mesmo com um
        controle selecionado no seletor (um override por-controle não tem
        opinião sobre o toggle — regra do schema). Persiste no "Salvar
        Perfil" (``to_profile``) e viaja no "Aplicar" (``to_ipc_dict``).
        RELIGAR o automático NÃO apaga cores explícitas por-controle: elas
        continuam vencendo onde existirem (merge do backend, D5) — quem as
        remove são os botões "Voltar ao automático".
        """
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = bool(checkbox.get_active())
        if bool(draft.leds.auto_player_colors) == ativo:
            return  # sem mudança real (eco de set_active programático)
        self.draft = draft.model_copy(
            update={
                "leds": draft.leds.model_copy(update={"auto_player_colors": ativo})
            }
        )
        if ativo:
            self._toast_light(
                "Cores automáticas ligadas — cores escolhidas por controle "
                "continuam valendo onde existirem"
            )
        else:
            self._toast_light(
                "Cores automáticas desligadas — vale a cor única do perfil"
            )

    def on_lightbar_auto_reset_target(self, _btn: Gtk.Button) -> None:
        """"Voltar ao automático" — remove a cor explícita do ALVO selecionado.

        Só a cor (``lightbar`` + ``lightbar_brightness``, que formam UM campo
        no backend) sai do override do controle; player-LEDs e gatilhos
        próprios ficam. A automática volta a valer nele no próximo Aplicar
        (ou na próxima ativação do perfil salvo). Com o alvo em "Todos" não
        há controle selecionado: orienta pelo toast, sem popup.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        uniq = self._edit_uniq()
        if uniq is None:
            self._toast_light(
                'Sem um controle escolhido, use o botão '
                '"Voltar todos ao automático".'
            )
            return
        self.draft = draft.with_controller_fields_cleared(
            uniq, "leds", {"lightbar", "lightbar_brightness"}
        )
        self._refresh_lightbar_from_draft()
        if self.draft.leds.auto_player_colors:
            self._toast_light(
                "Cor própria removida — a cor automática volta a valer "
                "neste controle no próximo Aplicar"
            )
        else:
            self._toast_light(
                'Cor própria removida — ligue "Cores automáticas por '
                'controle" para valer a paleta'
            )

    def on_lightbar_auto_reset_all(self, _btn: Gtk.Button) -> None:
        """"Voltar todos ao automático" — limpa as cores explícitas e religa o auto.

        Remove ``lightbar``/``lightbar_brightness`` de TODOS os overrides
        por-controle do draft (player-LEDs e gatilhos explícitos ficam) e
        religa ``auto_player_colors`` — a paleta automática volta a valer em
        todo mundo no próximo Aplicar/Salvar.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        novo = draft.with_override_fields_cleared(
            "leds", {"lightbar", "lightbar_brightness"}
        )
        novo = novo.model_copy(
            update={"leds": novo.leds.model_copy(update={"auto_player_colors": True})}
        )
        self.draft = novo
        self._refresh_lightbar_from_draft()
        self._toast_light(
            "Cores automáticas religadas para todos os controles — aplique "
            "ou salve o perfil para valer"
        )

    def _d4_disable_auto_for_single_color(self) -> bool:
        """D4 fora do ``_persist_leds_update``: desliga o auto no draft.

        Usado pelos caminhos que APLICAM a cor da tela sem editá-la
        (``on_lightbar_apply``): religou o automático e clicou "Aplicar no
        controle" em "Todos" → o toggle desliga aqui, e o chamador compõe o
        ``_AVISO_D4`` no toast do resultado. Devolve True quando desligou
        AGORA; False se já estava desligado (ou sem draft).
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return False
        self.draft = draft.model_copy(
            update={"leds": draft.leds.model_copy(update={"auto_player_colors": False})}
        )
        self._sync_auto_checkbox(False)
        return True

    def _sync_auto_checkbox(self, active: bool) -> None:
        """Reflete ``active`` no checkbox SEM disparar o handler (guard)."""
        check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if check is None:
            return
        prev = self._refresh_guard
        self._refresh_guard = True
        try:
            check.set_active(active)
        finally:
            self._refresh_guard = prev

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
        descricao = self._descreve_player_leds(bits)
        self._toast_light(
            f"LEDs de jogador aplicados — {descricao}"
            if ok
            else "não consegui aplicar os LEDs de jogador — o Hefesto pode "
            "estar desligado (ligue na aba Sistema)"
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
        descricao = self._descreve_player_leds(bits)
        self._toast_light(
            f"LEDs de jogador atualizados — {descricao}"
            if ok
            else "não consegui atualizar os LEDs de jogador — o Hefesto pode "
            "estar desligado (ligue na aba Sistema)"
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
        descricao = self._descreve_player_leds(pattern)
        self._toast_light(
            f"LEDs de jogador atualizados — {descricao}"
            if ok
            else "não consegui atualizar os LEDs de jogador — o Hefesto pode "
            "estar desligado (ligue na aba Sistema)"
        )

    def get_current_player_leds(self) -> tuple[bool, bool, bool, bool, bool]:
        states: list[bool] = []
        for i in range(1, 6):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            states.append(bool(checkbox.get_active()) if checkbox is not None else False)
        return (states[0], states[1], states[2], states[3], states[4])

    @staticmethod
    def _descreve_player_leds(bits: list[bool] | tuple[bool, ...]) -> str:
        """Padrão dos LEDs de jogador em palavras (LB-03).

        Troca a antiga notação "x - - - -" (parecia depuração) por texto que
        casa com os rótulos "LED 1".."LED 5" das caixas: "LEDs acesos: 1 e 3".
        """
        acesos = [str(i) for i, ligado in enumerate(bits, start=1) if ligado]
        if not acesos:
            return "todos os LEDs apagados"
        if len(acesos) == 1:
            return f"LED aceso: {acesos[0]}"
        return "LEDs acesos: " + ", ".join(acesos[:-1]) + " e " + acesos[-1]

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
