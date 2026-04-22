"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import glob
import os
import subprocess
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.gui.widgets.button_glyph import BUTTON_GLYPH_LABELS
from hefesto.integrations.hotkey_daemon import (
    DEFAULT_BUFFER_MS,
    DEFAULT_COMBO_NEXT,
    DEFAULT_COMBO_PREV,
)
from hefesto.integrations.uinput_gamepad import (
    DEVICE_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
)
from hefesto.utils.xdg_paths import config_dir

UINPUT_DEV = "/dev/uinput"


class EmulationActionsMixin(WidgetAccessMixin):
    """Controla a aba Emulação."""

    @staticmethod
    def _traduzir_combo(partes: tuple[str, ...]) -> str:
        """Traduz nomes técnicos do combo para PT-BR usando BUTTON_GLYPH_LABELS."""
        return " + ".join(BUTTON_GLYPH_LABELS.get(p, p.upper()) for p in partes)

    def install_emulation_tab(self) -> None:
        self._get("emulation_device_name_label").set_text(DEVICE_NAME)
        self._get("emulation_vidpid_label").set_text(
            f"{XBOX360_VENDOR:04X}:{XBOX360_PRODUCT:04X} (Xbox 360)"
        )
        self._get("emulation_combo_next_label").set_text(
            self._traduzir_combo(DEFAULT_COMBO_NEXT)
        )
        self._get("emulation_combo_prev_label").set_text(
            self._traduzir_combo(DEFAULT_COMBO_PREV)
        )
        self._get("emulation_combo_buffer_label").set_text(str(DEFAULT_BUFFER_MS))
        self._get("emulation_passthrough_label").set_text("Não")
        self._refresh_emulation_view()

    # --- handlers ---

    def on_emulation_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_emulation_view()
        self._toast_emulation("Atualizado")

    def on_emulation_test_device(self, _btn: Gtk.Button) -> None:
        try:
            import uinput  # noqa: F401
        except ImportError:
            self._toast_emulation(
                "python-uinput não instalado — pip install python-uinput"
            )
            return
        if not os.access(UINPUT_DEV, os.W_OK):
            self._toast_emulation(
                f"sem permissão em {UINPUT_DEV} — carregue módulo uinput "
                "e configure udev rule (ver README)"
            )
            return
        try:
            from hefesto.integrations.uinput_gamepad import UinputGamepad

            gp = UinputGamepad()
            ok = gp.start()
            gp.stop()
        except (OSError, RuntimeError) as exc:
            self._toast_emulation(f"Falha: {exc}")
            return
        if ok:
            self._toast_emulation("Device virtual criado com sucesso")
        else:
            self._toast_emulation("start() retornou False — veja logs do daemon")
        self._refresh_emulation_view()

    def on_emulation_open_toml(self, _btn: Gtk.Button) -> None:
        path = config_dir(ensure=True) / "daemon.toml"
        if not path.exists():
            path.write_text(
                "[hotkey]\n"
                f'buffer_ms = {DEFAULT_BUFFER_MS}\n'
                f'next_profile = {list(DEFAULT_COMBO_NEXT)}\n'
                f'prev_profile = {list(DEFAULT_COMBO_PREV)}\n'
                "passthrough_in_emulation = false\n",
                encoding="utf-8",
            )
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self._toast_emulation(f"xdg-open indisponível; edite manualmente: {path}")
            return
        self._toast_emulation(f"Abrindo {path}")

    # --- helpers ---

    def _refresh_emulation_view(self) -> None:
        uinput_label = self._get("emulation_uinput_label")
        try:
            import uinput  # noqa: F401
            module_ok = True
        except ImportError:
            module_ok = False

        dev_exists = os.path.exists(UINPUT_DEV)
        dev_writable = os.access(UINPUT_DEV, os.W_OK) if dev_exists else False

        if module_ok and dev_writable:
            uinput_label.set_markup(
                '<span foreground="#2d8">● Disponível</span>'
            )
        elif module_ok and dev_exists:
            uinput_label.set_markup(
                f'<span foreground="#c90">Módulo ok, sem permissão em {UINPUT_DEV}</span>'
            )
        elif module_ok:
            uinput_label.set_markup(
                f'<span foreground="#c90">Módulo ok, {UINPUT_DEV} ausente '
                '(modprobe uinput)</span>'
            )
        else:
            uinput_label.set_markup(
                '<span foreground="#d33">python-uinput não instalado</span>'
            )

        js_nodes = sorted(glob.glob("/dev/input/js*"))
        if js_nodes:
            self._get("emulation_js_label").set_text(", ".join(js_nodes))
        else:
            self._get("emulation_js_label").set_markup(
                '<i>Nenhum /dev/input/js* detectado</i>'
            )

    def _toast_emulation(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("emulation")
        bar.push(ctx_id, msg)
