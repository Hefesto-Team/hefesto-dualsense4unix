"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import glob
import os
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.constants import ROOT_DIR
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor, call_async, run_in_thread
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
        # FEAT-HOTKEY-PROFILE-CYCLE-01: os combos PS+D-pad ciclam o perfil
        # (next=PS+↑, prev=PS+↓), aplicando triggers/LEDs/bindings e piscando o
        # lightbar como feedback. Ligado em subsystems/hotkey.py.
        self._get("emulation_combo_next_label").set_markup(
            "PS + ↑ (D-pad) — próximo perfil"
        )
        self._get("emulation_combo_prev_label").set_markup(
            "PS + ↓ (D-pad) — perfil anterior"
        )
        self._get("emulation_combo_buffer_label").set_text(str(DEFAULT_BUFFER_MS))
        self._get("emulation_passthrough_label").set_text("Não")
        self._refresh_emulation_view()
        self._refresh_mic_status()
        self._refresh_gamepad_and_gamemode()
        self._refresh_steam_input_status()

    # --- handlers ---

    def on_emulation_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_emulation_tab()
        self._toast_emulation("Atualizado")

    def _refresh_emulation_tab(self) -> None:
        """Reconcilia TODOS os status da aba Emulação de uma vez.

        Idempotente e seguro de chamar ao ENTRAR na aba (switch-page chama este
        agregador via getattr — o nome precisa ser exatamente
        ``_refresh_emulation_tab``) e pelo botão "Atualizar". Cada refresh só
        LÊ estado e atualiza labels — uinput/js (sysfs), gamepad+modo-jogo (IPC
        read-only ``daemon.state_full``), mic (drop-ins do WirePlumber) e Steam
        Input (localconfig.vdf) — sem NENHUM efeito colateral no hardware. Cada
        chamada é guardada defensivamente (getattr) porque a Sprint 1 aciona
        este método por nome via switch-page.
        """
        for name in (
            "_refresh_emulation_view",
            "_refresh_gamepad_and_gamemode",
            "_refresh_mic_status",
            "_refresh_steam_input_status",
        ):
            fn = getattr(self, name, None)
            if callable(fn):
                fn()

    def _sync_uinput_card(self, active_key: str) -> None:
        """Atualiza device/VID:PID do cartão UINPUT conforme a máscara REAL."""
        from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS

        name_label = self._get("emulation_device_name_label")
        vid_label = self._get("emulation_vidpid_label")
        if active_key in FLAVORS:
            spec = FLAVORS[active_key]
            nice = "DualSense" if active_key == "dualsense" else "Xbox 360"
            if name_label is not None:
                name_label.set_text(str(spec["name"]))
            if vid_label is not None:
                vid_label.set_text(
                    f"{spec['vendor']:04X}:{spec['product']:04X} ({nice})"
                )
        else:
            if name_label is not None:
                name_label.set_text("— (gamepad virtual desligado)")
            if vid_label is not None:
                vid_label.set_text("—")

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

    # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: o quirk de áudio USB
    # (usbcore.quirks=054c:0ce6:gn) é o que segura o storm -71 COM o mic ligado.
    _USB_QUIRK_MARKER = "054c:0ce6:gn"
    _USB_QUIRK_PATHS: ClassVar[tuple[str, ...]] = (
        "/proc/cmdline",
        "/sys/module/usbcore/parameters/quirks",
    )

    @staticmethod
    def _usb_quirk_active() -> bool:
        """True se o quirk de áudio USB protege a SESSÃO ATUAL.

        Só /proc/cmdline (ATIVO) ou /sys/module/usbcore/parameters/quirks
        (runtime) valem agora; o agendado no bootloader só pega no próximo boot.
        Espelha o check_usb_quirk do doctor.sh, restrito aos sinais da sessão.
        """
        marker = EmulationActionsMixin._USB_QUIRK_MARKER
        for path in EmulationActionsMixin._USB_QUIRK_PATHS:
            with contextlib.suppress(OSError):
                if marker in Path(path).read_text(encoding="utf-8", errors="ignore"):
                    return True
        return False

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
        # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: a GUI não vê o stderr do script —
        # então, se o quirk de áudio USB não estiver ativo nesta sessão, o aviso
        # vai na mensagem FINAL (persiste no status bar). Um toast ANTES de ligar
        # seria sobrescrito pelo "aplicando no microfone..." do _run_mic e ficaria
        # invisível. Ligar sem o quirk pode reabrir o storm -71; não bloqueia e
        # NÃO mexemos no cmdline (gerido pela toolchain pessoal Aurora).
        if self._usb_quirk_active():
            done = "Mic do DualSense ligado"
        else:
            done = (
                "Mic ligado — ATENÇÃO: sem o quirk de áudio USB ativo isso pode "
                "reabrir o storm -71; rode scripts/install_usb_quirk.sh "
                "(vale no próximo boot)"
            )
        self._run_mic("--enable-mic", done)

    def on_emulation_mic_off(self, _btn: Gtk.Button) -> None:
        self._run_mic("--disable-source", "Mic do DualSense desligado")

    # --- gamepad virtual + modo-jogo (FEAT-DSX-GAMEPAD-FLAVOR-01) ---
    # Tudo via IPC pro daemon (gamepad.emulation.set / daemon.pause|resume),
    # que é o único leitor do controle — sem o input dobrado do bridge avulso.

    # Seletor de gamepad: 3 botões = 3 modos. Realçamos o ativo (GtkButton não
    # tem :checked, então marcamos a classe .hefesto-active-mode via código).
    _GAMEPAD_BUTTON_IDS: ClassVar[dict[str, str]] = {
        "off": "emulation_gamepad_off_button",
        "dualsense": "emulation_gamepad_dualsense_button",
        "xbox": "emulation_gamepad_xbox_button",
    }

    def _highlight_gamepad(self, active_key: str | None) -> None:
        """Destaca o botão do modo de gamepad atual (off/dualsense/xbox).

        ``None`` (daemon offline / estado desconhecido) limpa o realce de todos.
        """
        for key, wid in self._GAMEPAD_BUTTON_IDS.items():
            btn = self._get(wid)
            if btn is None:
                continue
            ctx = btn.get_style_context()
            if key == active_key:
                ctx.add_class("hefesto-active-mode")
            else:
                ctx.remove_class("hefesto-active-mode")

    def _refresh_gamepad_and_gamemode(self) -> None:
        """Lê daemon.state_full e atualiza os labels de gamepad + modo-jogo."""
        def _on_state(state: Any) -> bool:
            gp = state.get("gamepad_emulation") if isinstance(state, dict) else None
            gp_label = self._get("emulation_gamepad_status_label")
            if isinstance(gp, dict) and gp.get("enabled"):
                flavor = gp.get("flavor") or "?"
                active_key = "xbox" if flavor == "xbox" else "dualsense"
                nice = "DualSense (PS)" if active_key == "dualsense" else "Xbox 360"
                if gp_label is not None:
                    gp_label.set_markup(f'<span foreground="#2d8">ligado — {nice}</span>')
            else:
                active_key = "off"
                if gp_label is not None:
                    gp_label.set_markup('<span foreground="#999">desligado</span>')
            self._highlight_gamepad(active_key)
            # BUG-EMULATION-UINPUT-CARD-STALE-01: o cartão UINPUT mostrava
            # SEMPRE "X-Box 360 / 045E:028E" (constantes de install) mesmo com
            # a máscara real em DualSense — informação contraditória na mesma
            # tela. Reflete o device/VID:PID do vpad REALMENTE ativo.
            self._sync_uinput_card(active_key)
            gm_label = self._get("emulation_gamemode_status_label")
            if gm_label is not None and isinstance(state, dict):
                # BUG-GAMEMODE-LABEL-AMBIGUO-01: o label dizia "ativo" quando o
                # modo jogo estava DESLIGADO (referia-se à emulação) — lido como
                # "Modo jogo: ativo", significava o CONTRÁRIO do exibido.
                if state.get("emulation_suppressed"):
                    gm_label.set_markup(
                        '<span foreground="#c90">LIGADO — mouse/teclado suspensos</span>'
                    )
                elif state.get("paused"):
                    gm_label.set_markup('<span foreground="#c90">daemon pausado</span>')
                else:
                    gm_label.set_markup(
                        '<span foreground="#2d8">desligado — emulação normal</span>'
                    )
            return False

        def _on_err(_exc: Exception) -> bool:
            lbl = self._get("emulation_gamepad_status_label")
            if lbl is not None:
                lbl.set_markup('<span foreground="#999">daemon offline</span>')
            self._highlight_gamepad(None)
            return False

        call_async("daemon.state_full", {}, on_success=_on_state, on_failure=_on_err)

    def _set_gamepad(self, enabled: bool, flavor: str | None, msg: str) -> None:
        params: dict[str, Any] = {"enabled": enabled}
        if flavor is not None:
            params["flavor"] = flavor

        def _on_ok(_res: Any) -> bool:
            self._refresh_gamepad_and_gamemode()
            self._toast_emulation(msg)
            return False

        def _on_err(exc: Exception) -> bool:
            self._toast_emulation(f"daemon offline — gamepad não alterado ({exc})")
            return False

        call_async("gamepad.emulation.set", params, on_success=_on_ok, on_failure=_on_err)

    def on_emulation_gamepad_off(self, _btn: Gtk.Button) -> None:
        self._set_gamepad(False, None, "Gamepad virtual desligado")

    def on_emulation_gamepad_dualsense(self, _btn: Gtk.Button) -> None:
        self._set_gamepad(True, "dualsense", "Gamepad DualSense ligado (prompts PS)")

    def on_emulation_gamepad_xbox(self, _btn: Gtk.Button) -> None:
        self._set_gamepad(True, "xbox", "Gamepad Xbox 360 ligado (fallback)")

    def _set_suppress(self, suppressed: bool, msg: str) -> None:
        def _on_ok(_res: Any) -> bool:
            self._refresh_gamepad_and_gamemode()
            self._toast_emulation(msg)
            return False

        def _on_err(exc: Exception) -> bool:
            self._toast_emulation(f"daemon offline ({exc})")
            return False

        call_async(
            "daemon.emulation.suppress",
            {"suppressed": suppressed},
            on_success=_on_ok,
            on_failure=_on_err,
        )

    def on_emulation_pause(self, _btn: Gtk.Button) -> None:
        # FEAT-DSX-GAMEMODE-SUPPRESS-01: o botão "Modo jogo" usa
        # daemon.emulation.suppress (transitório, paridade real com o combo
        # PS+Options) em vez de daemon.pause. daemon.pause persistia paused.flag
        # e o daemon RENASCIA pausado no boot (controle morto no jogo até
        # "Retomar"), além de ser um kill-switch mais amplo (parava gatilhos/LED/
        # edges). Suppress suspende SÓ mouse/teclado e NÃO persiste; o gamepad
        # segue vivo no jogo (FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01). Como o label
        # 'Modo jogo' lê emulation_suppressed, ele passa a refletir o estado certo.
        self._set_suppress(True, "Modo jogo: mouse/teclado suspensos (gamepad ativo)")

    def on_emulation_resume(self, _btn: Gtk.Button) -> None:
        self._set_suppress(False, "Modo jogo desligado: mouse/teclado retomados")

    # --- Steam Input (FEAT-STEAM-INPUT-SELF-HEAL-01 via GUI) ---
    # Steam Input PSSupport ligado SEQUESTRA o controle e conflita com o daemon
    # (touchpad/teclado vazam, mic spam). Botão pra verificar/desligar.

    def _steam_input_script(self) -> Path | None:
        for cand in (
            ROOT_DIR / "scripts" / "disable_steam_input.sh",
            Path("/usr/share/hefesto-dualsense4unix/scripts/disable_steam_input.sh"),
            Path("/usr/local/share/hefesto-dualsense4unix/scripts/disable_steam_input.sh"),
        ):
            if cand.is_file():
                return cand
        return None

    @staticmethod
    def _steam_input_is_on() -> bool | None:
        """True/False se Steam Input PSSupport está ligado; None se indeterminado.

        Lê os localconfig.vdf por-usuário: PSSupport/UseSteamControllerConfig em
        "1" ou "2" = ligado (espelha o grep do disable_steam_input.sh).
        """
        import re

        vdfs = glob.glob(
            str(Path.home() / ".steam" / "steam" / "userdata" / "*" / "config" / "localconfig.vdf")
        )
        if not vdfs:
            return None
        pat = re.compile(
            r'"(SteamController_PSSupport|UseSteamControllerConfig)"\s+"[12]"'
        )
        for vdf in vdfs:
            with contextlib.suppress(OSError):
                if pat.search(Path(vdf).read_text(encoding="utf-8", errors="ignore")):
                    return True
        return False

    def _refresh_steam_input_status(self) -> None:
        label = self._get("emulation_steam_input_status_label")
        if label is None:
            return

        def _check() -> bool | None:
            return self._steam_input_is_on()

        def _on_ok(on: bool | None) -> bool:
            if on is None:
                label.set_markup('<span foreground="#999">Steam não encontrado</span>')
            elif on:
                label.set_markup('<span foreground="#c90">ligado (conflita!)</span>')
            else:
                label.set_markup('<span foreground="#2d8">desligado (ok)</span>')
            return False

        run_in_thread(_check, on_success=_on_ok)

    def on_emulation_steam_input_check(self, _btn: Gtk.Button) -> None:
        self._refresh_steam_input_status()
        self._toast_emulation("Steam Input verificado")

    def on_emulation_steam_input_disable(self, _btn: Gtk.Button) -> None:
        script = self._steam_input_script()
        if script is None:
            self._toast_emulation("script disable_steam_input.sh não encontrado")
            return
        self._toast_emulation("desligando Steam Input (fecha e reabre a Steam)...")

        def _worker() -> None:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["bash", str(script), "--apply-quiet"], check=False, timeout=60
                )
            GLib.idle_add(self._on_steam_input_done)

        _get_executor().submit(_worker)

    def _on_steam_input_done(self) -> bool:
        self._refresh_steam_input_status()
        self._toast_emulation("Steam Input desligado")
        return False

    def _toast_emulation(self, msg: str) -> None:
        self._status_toast("emulation", msg)
