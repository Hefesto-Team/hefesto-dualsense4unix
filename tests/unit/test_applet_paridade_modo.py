"""O applet reimplementa o plano de modo em Rust — não pode divergir da GUI.

`plan_mode_transition` (app/actions/mode_transition.py) é o dono único do plano na
GUI. O applet, sendo outro processo em outra linguagem, tem a sequência duplicada
no `apply_system_mode` (packaging/cosmic-applet/src/app.rs) — e ela **já divergiu**:
o ramo Desktop ficou sem o `mouse.emulation.restore` (HARM-06), então "Controlar o
PC" pelo applet deixava o controle sem função nenhuma enquanto a GUI o curava.

Não dá para compartilhar código entre Python e Rust, mas dá para travar o
contrato: cada método que o plano da GUI dispara tem de aparecer no ramo
correspondente do applet. Este teste falha quando alguém muda um lado só.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    plan_mode_transition,
)

_APP_RS = (
    Path(__file__).resolve().parents[2]
    / "packaging" / "cosmic-applet" / "src" / "app.rs"
)

#: Método IPC -> a chamada equivalente no applet (Rust).
_EQUIVALENTE_RUST = {
    "native.mode.set": "set_native_mode",
    "gamepad.emulation.set": "set_gamepad_emulation",
    "mouse.emulation.restore": "restore_mouse",
}


def _ramo_do_applet(modo: str) -> str:
    """Corpo do `SystemMode::<Modo> =>` dentro do apply_system_mode."""
    fonte = _APP_RS.read_text(encoding="utf-8")
    inicio = fonte.index("async fn apply_system_mode")
    corpo = fonte[inicio:inicio + 2000]
    nome = {MODE_DESKTOP: "Desktop", MODE_GAMEPAD: "Gamepad", MODE_NATIVE: "Native"}[modo]
    match = re.search(
        rf"SystemMode::{nome} =>(.*?)(?=SystemMode::|\n    \}})", corpo, re.DOTALL
    )
    assert match is not None, f"ramo SystemMode::{nome} sumiu do applet"
    return match.group(1)


@pytest.mark.parametrize("modo", [MODE_DESKTOP, MODE_GAMEPAD, MODE_NATIVE])
def test_o_applet_dispara_os_mesmos_passos_que_a_gui(modo: str) -> None:
    ramo = _ramo_do_applet(modo)

    for metodo, _params in plan_mode_transition(modo):
        rust = _EQUIVALENTE_RUST[metodo]
        assert rust in ramo, (
            f"o applet não faz `{rust}` no modo {modo!r}, mas o plano da GUI "
            f"dispara `{metodo}` — as duas superfícies divergiram"
        )


def test_o_desktop_do_applet_restaura_o_mouse() -> None:
    """O caso concreto que divergiu: sem isto o controle fica sem função nenhuma."""
    assert "restore_mouse" in _ramo_do_applet(MODE_DESKTOP)


def test_o_applet_sai_do_nativo_antes_de_ligar_o_gamepad() -> None:
    """HARM-01 no applet: a ordem também importa fora da GUI."""
    ramo = _ramo_do_applet(MODE_GAMEPAD)

    assert ramo.index("set_native_mode") < ramo.index("set_gamepad_emulation")


# --- INSTALL-APPLET-HEADLESS-01: o `just install` do applet precisa funcionar
# sem TTY (install.sh headless via SUDO_ASKPASS). O `sudo` puro do justfile
# falhava na 1a linha de instalação de arquivo e derrubava o passo 9. -----------

_JUSTFILE = (
    Path(__file__).resolve().parents[2] / "packaging" / "cosmic-applet" / "justfile"
)
_INSTALL_SH = Path(__file__).resolve().parents[2] / "install.sh"


def test_justfile_usa_sudo_parametrizavel() -> None:
    """O justfile declara `sudo := "sudo"` e usa {{sudo}} nas recipes install/
    uninstall — nunca `sudo` puro (que falha headless)."""
    text = _JUSTFILE.read_text(encoding="utf-8")
    assert re.search(r'^sudo\s*:=\s*"sudo"', text, re.M), (
        "justfile deve declarar a variável parametrizável `sudo := \"sudo\"`"
    )
    # Nenhuma linha de recipe pode chamar `sudo ` puro (fora da declaração e de
    # comentários) — todas via {{sudo}}.
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("#") or s.startswith("sudo :="):
            continue
        assert not re.match(r"^sudo\s", s), f"recipe usa sudo puro (headless quebra): {ln!r}"
    assert "{{sudo}} install -Dm755" in text


def test_install_passa_askpass_ao_just_quando_headless() -> None:
    """install.sh passa `--set sudo "sudo -A"` ao just quando SUDO_ASKPASS está
    setado (headless) — senão o `sudo` puro do just falha sem TTY."""
    text = _INSTALL_SH.read_text(encoding="utf-8")
    assert '--set sudo "sudo -A"' in text, (
        "install.sh deve passar --set sudo 'sudo -A' ao just no caminho headless"
    )
    assert 'SUDO_ASKPASS:-' in text
