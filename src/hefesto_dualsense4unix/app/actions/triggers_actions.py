"""Aba Triggers: dropdown de 19 presets + sliders dinâmicos + aplicar via IPC."""
# ruff: noqa: E402
from __future__ import annotations

import re
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.trigger_specs import (
    PRESETS,
    TriggerParamSpec,
    get_spec,
    preset_to_factory_args,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.app.ipc_bridge import trigger_set_checked
from hefesto_dualsense4unix.app.widgets import SegmentedSelector
from hefesto_dualsense4unix.profiles.trigger_presets import (
    FEEDBACK_POSITION_LABELS,
    VIBRATION_POSITION_LABELS,
    resolve_feedback_preset,
    resolve_vibration_preset,
)

# HARM-19: formatos de recusa que `core/trigger_effects` levanta (ValueError ->
# CODE_INVALID_PARAMS no IPC). Traduzidos abaixo para a língua da aba.
_RE_ERRO_ORDEM = re.compile(r"(\w+) \((-?\d+)\) deve ser > (\w+) \((-?\d+)\)")
_RE_ERRO_RANGE = re.compile(r"(\w+) fora do range (-?\d+)-(-?\d+): (-?\d+)")


def _rotulo_do_param(spec: Any, nome: str) -> str:
    """Rótulo do slider para o parâmetro `nome` do preset (ex.: end -> "Fim")."""
    for param in getattr(spec, "params", ()):
        if param.name == nome:
            return str(param.label)
    return nome


def humanizar_erro_gatilho(motivo: str, spec: Any = None) -> str | None:
    """Traduz a recusa do daemon para português simples (HARM-19).

    O daemon fala a língua do `core/trigger_effects` ("end (3) deve ser > start
    (5)"); a aba fala a dos próprios sliders ("Fim"/"Início"). Devolve None
    quando a mensagem não casa com nenhum formato conhecido — aí o chamador
    mostra o texto cru do daemon, que ainda diz mais que "daemon offline?".
    """
    m = _RE_ERRO_ORDEM.search(motivo)
    if m:
        maior, v_maior, menor, v_menor = m.groups()
        return (
            f"{_rotulo_do_param(spec, maior)} ({v_maior}) precisa ser maior que "
            f"{_rotulo_do_param(spec, menor)} ({v_menor})"
        )
    m = _RE_ERRO_RANGE.search(motivo)
    if m:
        nome, lo, hi, valor = m.groups()
        return (
            f"{_rotulo_do_param(spec, nome)} precisa estar entre {lo} e {hi} "
            f"(você pediu {valor})"
        )
    return None


class TriggersActionsMixin(WidgetAccessMixin):
    """Controla a aba Triggers (duas colunas L2/R2).

    Assume widgets no builder: trigger_<side>_mode, trigger_<side>_desc,
    trigger_<side>_params_box, trigger_<side>_apply, trigger_<side>_reset.
    """

    _trigger_param_widgets: dict[str, dict[str, Gtk.Scale]]
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: seletor de modo por lado (substitui o
    # GtkComboBoxText `trigger_<side>_mode`, fechado no clique pelo cosmic-comp).
    # Mesma API por-ID do combo (set_items/get_active_id/set_active_id + "changed").
    _trigger_mode: dict[str, Any]
    # Guard para evitar loop widget->draft->refresh->widget.
    _triggers_guard_refresh: bool = False
    # Guard para evitar que a aplicação de preset dispare o handler de slider
    # e reverta o preset para "custom" imediatamente.
    _trigger_preset_applying: bool = False
    # UI-TRIGGERS-LIVE-PREVIEW-01: handle GLib.timeout pendente por side,
    # debounce de 300 ms para não inundar o hardware quando o usuário troca
    # o combobox repetidamente.
    _trigger_live_preview_timer: dict[str, int]

    # Modos que ativam o dropdown de preset por posicao.
    _MODES_COM_PRESET = frozenset({"MultiPositionFeedback", "MultiPositionVibration"})

    def install_triggers_tab(self) -> None:
        self._trigger_param_widgets = {"left": {}, "right": {}}
        self._trigger_preset_applying = False
        self._trigger_live_preview_timer = {"left": 0, "right": 0}
        self._trigger_mode = {}
        self._trigger_preset = {}
        mode_handlers = {
            "left": self.on_trigger_left_mode_changed,
            "right": self.on_trigger_right_mode_changed,
        }
        mode_items = [(spec.name, spec.label) for spec in PRESETS]
        for side in ("left", "right"):
            # FEAT-DSX-COMBO-TO-SEGMENTED-01: botões segmentados no lugar do combo.
            # wrap=True para os 19 modos quebrarem linha sem estourar a coluna.
            sel = SegmentedSelector(wrap=True)
            sel.set_items(mode_items)
            sel.connect("changed", mode_handlers[side])
            slot = self._get(f"trigger_{side}_mode_slot")
            if slot is not None:
                slot.pack_start(sel, True, True, 0)
                sel.show_all()
            self._trigger_mode[side] = sel
            # FEAT-DSX-COMBO-TO-SEGMENTED-01: o combo de PRESET também vira
            # segmentado (7/6 presets + Personalizar; wrap p/ quebrar linha).
            preset_sel = SegmentedSelector(wrap=True)
            preset_handler = (
                self.on_trigger_left_preset_changed
                if side == "left"
                else self.on_trigger_right_preset_changed
            )
            preset_sel.connect("changed", preset_handler)
            preset_slot = self._get(f"trigger_{side}_preset_slot")
            if preset_slot is not None:
                preset_slot.pack_start(preset_sel, True, True, 0)
                preset_sel.show_all()
            self._trigger_preset[side] = preset_sel
            # set_active_id EMITE "changed" (como o combo). Fazemos sob _triggers_guard_refresh
            # para o handler curto-circuitar: senão `_on_mode_changed` AGENDA um
            # live-preview (300ms) que escreve "Off" no hardware ao abrir a GUI e
            # corre com o bootstrap do perfil, ZERANDO os gatilhos do perfil ativo
            # (BUG-GUI-OPEN-OFF-TRIGGER-WRITE-01). Montamos os sliders/linha de
            # preset explicitamente, sem tocar no hardware nem no draft.
            self._triggers_guard_refresh = True
            try:
                sel.set_active_id("Off")
            finally:
                self._triggers_guard_refresh = False
            self._rebuild_params(side, "Off")
            self._update_preset_row_visibility(side, "Off")
            self._populate_preset_combo(side, "MultiPositionFeedback")

    # --- draft integration ---

    def _refresh_triggers_from_draft(self) -> None:
        """Popula widgets da aba Triggers a partir do draft.

        PERFIL-04: exibe os gatilhos EFETIVOS do alvo de edição atual — o
        override por-controle quando existe, senão a seção global. Protegido
        por _triggers_guard_refresh para não disparar handlers de signal
        durante a atualização programatica dos combos.
        """
        if self._triggers_guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        triggers_draft = draft.effective_triggers_for(
            getattr(self, "_edit_target_uniq", None)
        )
        self._triggers_guard_refresh = True
        try:
            for side in ("left", "right"):
                trigger_draft = getattr(triggers_draft, side)
                combo = self._trigger_mode.get(side)
                if combo is None:
                    continue
                combo.set_active_id(trigger_draft.mode)
                self._rebuild_params(side, trigger_draft.mode)
                # Restaura valores dos parametros
                widgets = self._trigger_param_widgets.get(side, {})
                for i, name in enumerate(widgets):
                    if i < len(trigger_draft.params):
                        widgets[name].set_value(trigger_draft.params[i])
                # O set_active_id do modo roda sob _triggers_guard_refresh, então
                # _on_mode_changed retorna cedo e a linha "Preset:" não seria
                # revelada/escondida ao carregar um perfil. Chamamos explícito:
                # é seguro sob o guard (o set_active_id("custom") interno do
                # preset combo re-entra em _on_preset_changed, que sai no guard).
                self._update_preset_row_visibility(side, trigger_draft.mode)
        finally:
            self._triggers_guard_refresh = False

    # --- signals ---

    def on_trigger_left_mode_changed(self, combo: Any) -> None:
        # `combo` é o SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01); mantém
        # a API por-ID do GtkComboBoxText (get_active_id).
        self._on_mode_changed("left", combo)

    def on_trigger_right_mode_changed(self, combo: Any) -> None:
        self._on_mode_changed("right", combo)

    def on_trigger_left_preset_changed(self, combo: Any) -> None:
        # `combo` é o SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01).
        self._on_preset_changed("left", combo)

    def on_trigger_right_preset_changed(self, combo: Any) -> None:
        self._on_preset_changed("right", combo)

    def on_trigger_left_apply(self, _btn: Gtk.Button) -> None:
        self._apply_trigger("left")

    def on_trigger_right_apply(self, _btn: Gtk.Button) -> None:
        self._apply_trigger("right")

    def on_trigger_left_reset(self, _btn: Gtk.Button) -> None:
        self._reset_trigger("left")

    def on_trigger_right_reset(self, _btn: Gtk.Button) -> None:
        self._reset_trigger("right")

    # --- helpers ---

    def _on_mode_changed(self, side: str, combo: Any) -> None:
        if self._triggers_guard_refresh:
            return
        preset_id = combo.get_active_id()
        if preset_id is None:
            return
        self._rebuild_params(side, preset_id)
        # Mostra/esconde a linha de preset conforme o modo selecionado.
        self._update_preset_row_visibility(side, preset_id)
        # BUG-TRIGGERS-DRAFT-STALE-01: grava o novo modo COM os defaults dos
        # sliders recém-montados (antes gravava params=() — "Salvar Perfil"
        # antes do live-preview de 300 ms persistia o gatilho zerado). O draft
        # passa a espelhar exatamente o que o live-preview vai aplicar.
        self._persist_params_to_draft(side)
        # UI-TRIGGERS-LIVE-PREVIEW-01: aplica o modo no hardware em 300 ms
        # para o usuário sentir o efeito sem precisar clicar "Aplicar". O
        # debounce evita inundar o IPC quando o combobox dispara mudanças
        # rapidamente (autocompletar/scroll do usuário).
        self._schedule_live_preview(side)

    def _schedule_live_preview(self, side: str) -> None:
        """Agenda `_apply_trigger(side)` em 300 ms, cancelando handle pendente."""
        timers = getattr(self, "_trigger_live_preview_timer", None)
        if timers is None:
            return
        previous = timers.get(side, 0)
        if previous:
            GLib.source_remove(previous)
        timers[side] = GLib.timeout_add(300, self._fire_live_preview, side)

    def _fire_live_preview(self, side: str) -> bool:
        import contextlib

        self._trigger_live_preview_timer[side] = 0
        # _apply_trigger já chama _toast_trigger com ok=False em paths de IPC
        # ausente; aqui suprimimos para não derrubar o loop GTK em corner cases.
        with contextlib.suppress(Exception):
            self._apply_trigger(side)
        return False  # one-shot

    def _persist_params_to_draft(self, side: str) -> None:
        """Grava modo + params posicionais correntes dos sliders no draft.

        BUG-TRIGGERS-DRAFT-STALE-01: o "Salvar Perfil" do rodapé lê
        ``self.draft`` direto — sem persistir aqui, mexer em slider/preset sem
        clicar "Aplicar" salvava o perfil com params defasados/zerados.
        Semântica: o que a usuária vê/sente é o que salva.
        BUG-TRIGGER-FLAT-MULTIPOS-01: usa SEMPRE a lista posicional plana na
        ordem do spec (== ordem dos widgets), que casa com o restore por
        índice em ``_refresh_triggers_from_draft`` e com ``build_from_name``.
        """
        combo = self._trigger_mode.get(side)
        preset_id = combo.get_active_id() if combo else None
        if preset_id is None:
            return
        spec = get_spec(preset_id)
        if spec is None:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        from hefesto_dualsense4unix.app.draft_config import TriggerDraft

        values = self._collect_values(side)
        params_list: list[int] = preset_to_positional_params(spec, values)
        new_trigger = TriggerDraft(mode=preset_id, params=tuple(params_list))
        uniq = getattr(self, "_edit_target_uniq", None)
        if uniq is None:
            new_triggers = draft.triggers.model_copy(update={side: new_trigger})
            draft = draft.model_copy(update={"triggers": new_triggers})
            # Fix HIGH do review (2026-07-16): edição em "Todos" limpa o LADO
            # editado dos overrides por-controle — espelho da regra do backend
            # ao vivo. Sem isso, "Salvar Perfil" persistia o gatilho antigo do
            # alvo e a próxima ativação o ressuscitava.
            self.draft = draft.with_override_fields_cleared("triggers", {side})
            return
        # PERFIL-04: gatilho editado com um controle selecionado no seletor
        # vai para o override por-MAC do perfil (draft.controllers[uniq]) —
        # semeado com o efetivo em tela, então o OUTRO lado preserva o que a
        # usuária vê. "Salvar Perfil" persiste dentro do mesmo perfil.
        base = draft.effective_triggers_for(uniq)
        self.draft = draft.with_controller_triggers(
            uniq, base.model_copy(update={side: new_trigger})
        )

    def _on_preset_changed(self, side: str, combo: Any) -> None:
        """Aplica o preset selecionado populando os sliders de posicao."""
        if self._triggers_guard_refresh or self._trigger_preset_applying:
            return
        preset_key = combo.get_active_id()
        if preset_key is None or preset_key == "custom":
            return

        # Determina qual dicionario de presets usar com base no modo atual.
        mode_combo = self._trigger_mode.get(side)
        mode_id = mode_combo.get_active_id() if mode_combo else None

        if mode_id == "MultiPositionFeedback":
            valores = resolve_feedback_preset(preset_key)
        elif mode_id == "MultiPositionVibration":
            valores = resolve_vibration_preset(preset_key)
        else:
            return

        if valores is None:
            return

        # Popula os sliders de posicao com guard ativo.
        self._trigger_preset_applying = True
        try:
            widgets = self._trigger_param_widgets.get(side, {})
            for _idx, (nome, scale) in enumerate(widgets.items()):
                # Pula o slider de frequência em MultiPositionVibration (primeiro param).
                if mode_id == "MultiPositionVibration" and nome == "frequency":
                    continue
                # Mapeia nome "pos_N" para o indice N.
                if nome.startswith("pos_"):
                    try:
                        pos_idx = int(nome[4:])
                    except ValueError:
                        continue
                    if pos_idx < len(valores):
                        scale.set_value(valores[pos_idx])
                        scale.queue_draw()
        finally:
            self._trigger_preset_applying = False

        # BUG-TRIGGERS-DRAFT-STALE-01: o preset recém-aplicado nos sliders
        # precisa valer para o "Salvar Perfil" do rodapé e ser sentido no
        # controle — persiste no draft e agenda o live-preview existente.
        self._persist_params_to_draft(side)
        self._schedule_live_preview(side)

    def _update_preset_row_visibility(self, side: str, mode_id: str) -> None:
        """Exibe ou oculta a linha de preset conforme o modo selecionado."""
        preset_row: Gtk.Box | None = self._get(f"trigger_{side}_preset_row")
        if preset_row is None:
            return
        deve_mostrar = mode_id in self._MODES_COM_PRESET
        preset_row.set_visible(deve_mostrar)
        if deve_mostrar:
            # Repopula o combo com os labels corretos para o modo atual.
            self._populate_preset_combo(side, mode_id)

    def _populate_preset_combo(self, side: str, mode_id: str) -> None:
        """Preenche o segmentado de preset com as entradas do modo (+ Personalizar)."""
        combo = self._trigger_preset.get(side)
        if combo is None:
            return
        if mode_id == "MultiPositionFeedback":
            labels = FEEDBACK_POSITION_LABELS
        elif mode_id == "MultiPositionVibration":
            labels = VIBRATION_POSITION_LABELS
        else:
            combo.set_items([])
            return
        # BUG-TRIGGERS-PRESET-DUP-01: os dicionários de labels JÁ contêm a
        # entrada "custom" ("Personalizar"); anexar outra fixa duplicava o
        # botão no segmentado. Reordenamos explicitamente para "Personalizar"
        # ficar sempre por último (UX), independente da ordem dos dicts.
        items = [(key, label) for key, label in labels.items() if key != "custom"]
        items.append(("custom", labels.get("custom", "Personalizar")))
        combo.set_items(items)
        combo.set_active_id("custom")

    def _on_param_slider_changed(self, side: str) -> None:
        """Handler 'value-changed' dos sliders de parâmetro do lado ``side``.

        Mantém o comportamento existente (reverter o preset para
        "Personalizar") e, quando o toque é da usuária — fora de refresh
        programático (``_triggers_guard_refresh``) e de aplicação de preset
        (``_trigger_preset_applying``, que persiste em lote ao final de
        ``_on_preset_changed``) —, grava os params correntes no draft e agenda
        o live-preview (BUG-TRIGGERS-DRAFT-STALE-01: sem isso, ajustar slider
        sem clicar "Aplicar" salvava o perfil com params defasados).
        """
        self._update_preset_to_custom(side)
        if self._triggers_guard_refresh or self._trigger_preset_applying:
            return
        self._persist_params_to_draft(side)
        self._schedule_live_preview(side)

    def _update_preset_to_custom(self, side: str) -> None:
        """Reverte o segmentado de preset para 'Personalizar' quando move slider."""
        if self._trigger_preset_applying:
            return
        combo = self._trigger_preset.get(side)
        if combo is None or not combo.get_visible():
            return
        active = combo.get_active_id()
        if active != "custom":
            # Salva/restaura o guard em vez de zerar absoluto: este método é o
            # handler 'value-changed' dos sliders e pode disparar DENTRO de
            # _refresh_triggers_from_draft (que mantém _triggers_guard_refresh=True ao
            # chamar set_value). Zerar absoluto quebraria o guard no meio do
            # refresh e deixaria o resto do laço rodar desprotegido (reentrância).
            prev_guard = self._triggers_guard_refresh
            self._triggers_guard_refresh = True
            try:
                combo.set_active_id("custom")
            finally:
                self._triggers_guard_refresh = prev_guard

    def _rebuild_params(self, side: str, preset_id: str) -> None:
        spec = get_spec(preset_id)
        box: Gtk.Box = self._get(f"trigger_{side}_params_box")
        desc: Gtk.Label = self._get(f"trigger_{side}_desc")

        for child in box.get_children():
            box.remove(child)
        self._trigger_param_widgets[side] = {}

        if spec is None:
            desc.set_text("")
            return

        desc.set_markup(f"<i>{spec.description}</i>")

        for param in spec.params:
            row = self._build_param_row(param)
            box.pack_start(row, False, False, 0)
            self._trigger_param_widgets[side][param.name] = row.scale
            # Conecta sinal que reverte o preset para "custom", persiste o
            # draft e agenda o live-preview ao mover o slider
            # (BUG-TRIGGERS-DRAFT-STALE-01).
            row.scale.connect(
                "value-changed",
                lambda _scale, _side=side: self._on_param_slider_changed(_side),
            )

        box.show_all()

    def _build_param_row(self, param: TriggerParamSpec) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_homogeneous(False)

        label = Gtk.Label(label=param.label)
        label.set_xalign(0)
        label.set_size_request(200, -1)
        row.pack_start(label, False, False, 0)

        adjust = Gtk.Adjustment(
            value=param.default,
            lower=param.min_value,
            upper=param.max_value,
            step_increment=1,
            page_increment=max(1, (param.max_value - param.min_value) // 10),
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjust)
        scale.set_digits(0)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_hexpand(True)
        row.pack_start(scale, True, True, 0)

        row.scale = scale
        return row

    def _collect_values(self, side: str) -> dict[str, int]:
        widgets = self._trigger_param_widgets.get(side, {})
        return {name: int(scale.get_value()) for name, scale in widgets.items()}

    def _apply_trigger(self, side: str) -> None:
        combo = self._trigger_mode.get(side)
        preset_id = combo.get_active_id() if combo else None
        if preset_id is None:
            return
        spec = get_spec(preset_id)
        if spec is None:
            return

        values = self._collect_values(side)
        args = preset_to_factory_args(spec, values)

        # Persiste params posicionais no draft antes de enviar via IPC.
        # BUG-TRIGGER-FLAT-MULTIPOS-01: `_persist_params_to_draft` usa SEMPRE a
        # lista posicional plana na ordem do spec (== ordem dos widgets). Para
        # MultiPosition*/Custom o `args` é dict e o código antigo gravava () ->
        # perda silenciosa de TODAS as intensidades ao salvar/aplicar perfil.
        self._persist_params_to_draft(side)

        # PERFIL-05: com um controle selecionado, o MAC viaja no pedido.
        # getattr defensivo: hosts de teste parciais montam o mixin sem o
        # seletor (sem `_edit_uniq`) — segue global, como antes.
        uniq = getattr(self, "_edit_uniq", lambda: None)()
        if isinstance(args, dict):
            # Custom e MultiPosition_* usam dict; IPC espera posicional
            # no formato aceito por build_from_name nomeado.
            ok, motivo = self._send_trigger_named(side, preset_id, args, uniq=uniq)
        else:
            ok, motivo = trigger_set_checked(side, preset_id, args, uniq=uniq)

        self._toast_trigger(side, preset_id, ok, motivo=motivo, spec=spec)

    def _send_trigger_named(
        self,
        side: str,
        preset_id: str,
        kwargs: dict[str, object],
        uniq: str | None = None,
    ) -> tuple[bool, str | None]:
        """Formato alternativo pra presets com kwargs (custom, multi_pos)."""
        if preset_id == "Custom":
            mode_val = int(kwargs.get("mode", 0) or 0)  # type: ignore[call-overload]
            forces_obj = kwargs.get("forces", ())
            forces = list(forces_obj) if isinstance(forces_obj, (list, tuple)) else []
            return trigger_set_checked(side, preset_id, [mode_val, *forces], uniq=uniq)
        if preset_id == "MultiPositionFeedback":
            strengths_obj = kwargs.get("strengths", [])
            strengths = list(strengths_obj) if isinstance(strengths_obj, (list, tuple)) else []
            return trigger_set_checked(side, preset_id, strengths, uniq=uniq)
        if preset_id == "MultiPositionVibration":
            freq = int(kwargs.get("frequency", 0) or 0)  # type: ignore[call-overload]
            strengths_obj = kwargs.get("strengths", [])
            strengths = list(strengths_obj) if isinstance(strengths_obj, (list, tuple)) else []
            return trigger_set_checked(side, preset_id, [freq, *strengths], uniq=uniq)
        return False, f"preset sem formato nomeado conhecido: {preset_id}"

    def _reset_trigger(self, side: str) -> None:
        combo = self._trigger_mode.get(side)
        if combo is not None:
            combo.set_active_id("Off")
        self._rebuild_params(side, "Off")
        trigger_set_checked(side, "Off", [])
        self._toast_trigger(side, "Off", True)

    def _toast_trigger(
        self,
        side: str,
        preset_id: str,
        ok: bool,
        *,
        motivo: str | None = None,
        spec: Any = None,
    ) -> None:
        """Mostra o resultado do apply na statusbar.

        HARM-19: `motivo` preenchido = o daemon está VIVO e recusou o pedido
        (ex.: Fim <= Início). Culpar o daemon aí ("offline?") mandava a usuária
        caçar o problema no lugar errado — o problema está nos sliders dela.
        """
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("trigger")
        # TRG-01: "LEFT -> Off" trocava a fala da usuária (o gatilho que ela
        # clicou) por id interno + lado em inglês. Nome do lado em PT-BR.
        lado = {
            "left": "Gatilho esquerdo (L2)",
            "right": "Gatilho direito (R2)",
        }.get(side, side)
        if ok:
            msg = f"{lado}: {preset_id} aplicado"
        elif motivo:
            msg = (
                f"{lado}: {preset_id} não aplicado — "
                f"{humanizar_erro_gatilho(motivo, spec) or motivo}"
            )
        else:
            msg = (
                f"{lado}: não consegui aplicar {preset_id} — o Hefesto pode "
                "estar desligado (ligue na aba Sistema)"
            )
        bar.push(ctx_id, msg)
