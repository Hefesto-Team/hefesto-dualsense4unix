"""Aba Triggers: dropdown de 19 presets + sliders dinâmicos + aplicar via IPC."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.actions.trigger_specs import (
    PRESETS,
    TriggerParamSpec,
    get_spec,
    preset_to_factory_args,
)
from hefesto.app.ipc_bridge import trigger_set


class TriggersActionsMixin(WidgetAccessMixin):
    """Controla a aba Triggers (duas colunas L2/R2).

    Assume widgets no builder: trigger_<side>_mode, trigger_<side>_desc,
    trigger_<side>_params_box, trigger_<side>_apply, trigger_<side>_reset.
    """

    _trigger_param_widgets: dict[str, dict[str, Gtk.Scale]]
    # Guard para evitar loop widget->draft->refresh->widget.
    _guard_refresh: bool = False

    def install_triggers_tab(self) -> None:
        self._trigger_param_widgets = {"left": {}, "right": {}}
        for side in ("left", "right"):
            combo: Gtk.ComboBoxText = self._get(f"trigger_{side}_mode")
            combo.remove_all()
            for spec in PRESETS:
                combo.append(spec.name, spec.label)
            combo.set_active_id("Off")
            self._rebuild_params(side, "Off")

    # --- draft integration ---

    def _refresh_triggers_from_draft(self) -> None:
        """Popula widgets da aba Triggers a partir de self.draft.triggers.

        Protegido por _guard_refresh para nao disparar handlers de signal
        durante a atualizacao programatica dos combos.
        """
        if self._guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._guard_refresh = True
        try:
            for side in ("left", "right"):
                trigger_draft = getattr(draft.triggers, side)
                combo: Gtk.ComboBoxText = self._get(f"trigger_{side}_mode")
                if combo is None:
                    continue
                combo.set_active_id(trigger_draft.mode)
                self._rebuild_params(side, trigger_draft.mode)
                # Restaura valores dos parametros
                widgets = self._trigger_param_widgets.get(side, {})
                for i, name in enumerate(widgets):
                    if i < len(trigger_draft.params):
                        widgets[name].set_value(trigger_draft.params[i])
        finally:
            self._guard_refresh = False

    # --- signals ---

    def on_trigger_left_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        self._on_mode_changed("left", combo)

    def on_trigger_right_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        self._on_mode_changed("right", combo)

    def on_trigger_left_apply(self, _btn: Gtk.Button) -> None:
        self._apply_trigger("left")

    def on_trigger_right_apply(self, _btn: Gtk.Button) -> None:
        self._apply_trigger("right")

    def on_trigger_left_reset(self, _btn: Gtk.Button) -> None:
        self._reset_trigger("left")

    def on_trigger_right_reset(self, _btn: Gtk.Button) -> None:
        self._reset_trigger("right")

    # --- helpers ---

    def _on_mode_changed(self, side: str, combo: Gtk.ComboBoxText) -> None:
        if self._guard_refresh:
            return
        preset_id = combo.get_active_id()
        if preset_id is None:
            return
        self._rebuild_params(side, preset_id)
        # Atualiza draft com novo modo (params zerados ate usuario ajustar sliders)
        draft = getattr(self, "draft", None)
        if draft is not None:
            from hefesto.app.draft_config import TriggerDraft

            new_trigger = TriggerDraft(mode=preset_id, params=())
            new_triggers = draft.triggers.model_copy(update={side: new_trigger})
            self.draft = draft.model_copy(update={"triggers": new_triggers})

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
        combo: Gtk.ComboBoxText = self._get(f"trigger_{side}_mode")
        preset_id = combo.get_active_id()
        if preset_id is None:
            return
        spec = get_spec(preset_id)
        if spec is None:
            return

        values = self._collect_values(side)
        args = preset_to_factory_args(spec, values)

        # Persiste params posicionais no draft antes de enviar via IPC.
        draft = getattr(self, "draft", None)
        if draft is not None:
            from hefesto.app.draft_config import TriggerDraft

            params_list: list[int] = args if isinstance(args, list) else []
            new_trigger = TriggerDraft(mode=preset_id, params=tuple(params_list))
            new_triggers = draft.triggers.model_copy(update={side: new_trigger})
            self.draft = draft.model_copy(update={"triggers": new_triggers})

        if isinstance(args, dict):
            # Custom e MultiPosition_* usam dict; IPC espera posicional
            # no formato aceito por build_from_name nomeado.
            ok = self._send_trigger_named(side, preset_id, args)
        else:
            ok = trigger_set(side, preset_id, args)

        self._toast_trigger(side, preset_id, ok)

    def _send_trigger_named(
        self, side: str, preset_id: str, kwargs: dict[str, object]
    ) -> bool:
        """Formato alternativo pra presets com kwargs (custom, multi_pos)."""
        if preset_id == "Custom":
            mode_val = int(kwargs.get("mode", 0) or 0)  # type: ignore[call-overload]
            forces_obj = kwargs.get("forces", ())
            forces = list(forces_obj) if isinstance(forces_obj, (list, tuple)) else []
            return trigger_set(side, preset_id, [mode_val, *forces])
        if preset_id == "MultiPositionFeedback":
            strengths_obj = kwargs.get("strengths", [])
            strengths = list(strengths_obj) if isinstance(strengths_obj, (list, tuple)) else []
            return trigger_set(side, preset_id, strengths)
        if preset_id == "MultiPositionVibration":
            freq = int(kwargs.get("frequency", 0) or 0)  # type: ignore[call-overload]
            strengths_obj = kwargs.get("strengths", [])
            strengths = list(strengths_obj) if isinstance(strengths_obj, (list, tuple)) else []
            return trigger_set(side, preset_id, [freq, *strengths])
        return False

    def _reset_trigger(self, side: str) -> None:
        combo: Gtk.ComboBoxText = self._get(f"trigger_{side}_mode")
        combo.set_active_id("Off")
        self._rebuild_params(side, "Off")
        trigger_set(side, "Off", [])
        self._toast_trigger(side, "Off", True)

    def _toast_trigger(self, side: str, preset_id: str, ok: bool) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("trigger")
        msg = (
            f"{side.upper()} -> {preset_id} aplicado"
            if ok
            else f"{side.upper()} -> {preset_id} falhou (daemon offline?)"
        )
        bar.push(ctx_id, msg)
