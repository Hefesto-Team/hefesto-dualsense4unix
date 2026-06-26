"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import glob
import os
import subprocess
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.constants import ROOT_DIR
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_BUFFER_MS,
    DEFAULT_PS_LONG_PRESS_MS,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DEVICE_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
)
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

UINPUT_DEV = "/dev/uinput"


class EmulationActionsMixin(WidgetAccessMixin):
    """Controla a aba Emulação."""

    def install_emulation_tab(self) -> None:
        self._get("emulation_device_name_label").set_text(DEVICE_NAME)
        self._get("emulation_vidpid_label").set_text(
            f"{XBOX360_VENDOR:04X}:{XBOX360_PRODUCT:04X} (Xbox 360)"
        )
        # BUG-EMULATION-COMBO-MISLEADING-01: o daemon desativa next/prev
        # (HotkeyConfig(next_profile=(), prev_profile=()) — disabled_until_wired),
        # então PS+D-pad NÃO troca de perfil; D-pad volta a emular as setas.
        # Não anunciar um combo que não funciona — ver subsystems/hotkey.py.
        self._get("emulation_combo_next_label").set_markup(
            "<i>troca por hotkey: em desenvolvimento</i>"
        )
        self._get("emulation_combo_prev_label").set_markup(
            "<i>troca por hotkey: em desenvolvimento</i>"
        )
        self._get("emulation_combo_buffer_label").set_text(str(DEFAULT_BUFFER_MS))
        self._get("emulation_passthrough_label").set_text("Não")
        self._refresh_emulation_view()
        self._refresh_mic_status()

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
            from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

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
        # BUG-DAEMON-TOML-DEAD-01: o daemon NÃO lê daemon.toml (config vem de
        # variáveis de ambiente + IPC daemon.reload). O arquivo é só referência;
        # deixamos isso explícito no cabeçalho e não escrevemos chaves mortas
        # (next_profile/prev_profile estão disabled_until_wired no daemon).
        path = config_dir(ensure=True) / "daemon.toml"
        if not path.exists():
            path.write_text(
                "# REFERÊNCIA — o daemon NÃO lê este arquivo.\n"
                "# Configuração efetiva: variáveis de ambiente + IPC daemon.reload.\n"
                "[hotkey]\n"
                f'buffer_ms = {DEFAULT_BUFFER_MS}\n'
                f'ps_long_press_ms = {DEFAULT_PS_LONG_PRESS_MS}  # 0 = desliga o modo jogo\n'
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
            # ADR-011: &#9679; (BLACK CIRCLE) via NCR — sobrevive ao sanitizer.
            uinput_label.set_markup(
                '<span foreground="#2d8">&#9679; Disponível</span>'
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

    # --- microfone do DualSense (FEAT-DUALSENSE-MIC-TOGGLE-01) ---
    # Liga/desliga o mic embutido reusando o mesmo caminho do CLI/install
    # (scripts/fix_wireplumber_default_source.sh). Mic ON = sem os drop-ins de
    # supressão 52/53; OFF = com eles. O quirk segura o storm com o mic ligado.

    _WP_DROPIN_DIR = Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
    _WP_DISABLE_DROPINS = (
        "52-hefesto-dualsense-disable-source.conf",
        "53-hefesto-dualsense-disable-output.conf",
    )

    def _mic_script(self) -> Path | None:
        for cand in (
            ROOT_DIR / "scripts" / "fix_wireplumber_default_source.sh",
            Path("/usr/share/hefesto-dualsense4unix/scripts/fix_wireplumber_default_source.sh"),
            Path(
                "/usr/local/share/hefesto-dualsense4unix/scripts/"
                "fix_wireplumber_default_source.sh"
            ),
        ):
            if cand.is_file():
                return cand
        return None

    def _mic_is_on(self) -> bool:
        """Mic ON quando nenhum drop-in de supressão (52/53) está presente."""
        return not any(
            (self._WP_DROPIN_DIR / name).exists() for name in self._WP_DISABLE_DROPINS
        )

    def _refresh_mic_status(self) -> None:
        label = self._get("emulation_mic_status_label")
        if label is None:
            return
        if self._mic_is_on():
            label.set_markup('<span foreground="#2d8">ligado</span>')
        else:
            label.set_markup('<span foreground="#c90">desligado (suprimido)</span>')

    def _run_mic(self, flag: str, done_msg: str) -> None:
        script = self._mic_script()
        if script is None:
            self._toast_emulation("script do WirePlumber não encontrado")
            return
        self._toast_emulation("aplicando no microfone...")

        def _worker() -> None:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(["bash", str(script), flag], check=False, timeout=30)
            GLib.idle_add(self._on_mic_done, done_msg)

        _get_executor().submit(_worker)

    def _on_mic_done(self, msg: str) -> bool:
        self._refresh_mic_status()
        self._toast_emulation(msg)
        return False

    def on_emulation_mic_on(self, _btn: Gtk.Button) -> None:
        self._run_mic("--enable-mic", "Mic do DualSense ligado")

    def on_emulation_mic_off(self, _btn: Gtk.Button) -> None:
        self._run_mic("--disable-source", "Mic do DualSense desligado")

    def _toast_emulation(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("emulation")
        bar.push(ctx_id, msg)
