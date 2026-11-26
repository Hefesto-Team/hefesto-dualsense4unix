"""INSTALL-HEADLESS-01 (auditoria 21/07) — install/uninstall sem TTY."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")


def _extract_bash_function(source: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}\(\) \{{\n", source, re.MULTILINE)
    assert match is not None, f"função {name}() não encontrada"
    end_match = re.search(r"^\}\n", source[match.end() :], re.MULTILINE)
    assert end_match is not None, f"fim de {name}() não encontrado"
    return source[match.start() : match.end() + end_match.end()]


def _run_ask_yn(default: str) -> str:
    """Roda o `ask_yn` real de install.sh sob `set -euo pipefail`, stdin fechado"""
    fn = _extract_bash_function(INSTALL, "ask_yn")
    script = (
        "set -euo pipefail\n"
        "AUTO_YES=0\n"
        f"{fn}\n"
        f'ask_yn "pergunta" "$AUTO_YES" "{default}"\n'
        'printf "%s" "$REPLY"\n'
    )
    resultado = subprocess.run(
        ["bash", "-c", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert resultado.returncode == 0, (
        "ask_yn sem TTY MATOU o script (set -e no EOF do read): "
        f"rc={resultado.returncode} {resultado.stderr}"
    )
    return resultado.stdout


class TestAskYnHeadless:
    def test_sem_tty_usa_default_y(self) -> None:
        assert _run_ask_yn("y") == "y"

    def test_sem_tty_usa_default_n(self) -> None:
        assert _run_ask_yn("n") == "n"

    def test_ask_yn_tem_guarda_de_tty(self) -> None:
        fn = _extract_bash_function(INSTALL, "ask_yn")
        assert "! -t 0" in fn
        pos_guarda = fn.index("! -t 0")
        pos_read = fn.index("read -r")
        assert pos_guarda < pos_read, "a guarda de TTY tem de vir antes do read"


class TestAcquireSudoAskpass:
    """O-UNINSTALL-TENTA-O-ASKPASS-DO-SUDO-CONF-01.

    D-2611-O-UNINSTALL-TENTA-O-ASKPASS-DO-SUDO-CONF: o `acquire_sudo` do install e o do uninstall
    tentam `sudo -A -v` sem depender de `SUDO_ASKPASS`, porque o askpass pode estar declarado só
    no `sudo.conf`.
    """

    @pytest.mark.parametrize("script_text", [INSTALL, UNINSTALL], ids=["install", "uninstall"])
    def test_acquire_sudo_suporta_askpass(self, script_text: str) -> None:
        """D-2611-O-UNINSTALL-TENTA-O-ASKPASS-DO-SUDO-CONF: os dois tentam o askpass."""
        fn = _extract_bash_function(script_text, "acquire_sudo")
        assert "sudo -A -v" in fn
        assert "SUDO_ASKPASS" not in fn, (
            "acquire_sudo precisa tentar `sudo -A -v` mesmo sem SUDO_ASKPASS no ambiente "
            "(o askpass pode vir do sudo.conf)"
        )

    @pytest.mark.parametrize("script_text", [INSTALL, UNINSTALL], ids=["install", "uninstall"])
    def test_sem_a_variavel_e_sem_terminal_o_askpass_do_sudo_conf_vale(
        self, script_text: str, tmp_path: Path
    ) -> None:
        """D-2611-O-UNINSTALL-TENTA-O-ASKPASS-DO-SUDO-CONF: com um `sudo` que só aceita `-A -v`
        e sem `SUDO_ASKPASS`, o `acquire_sudo` segue com a credencial e não pede senha."""
        chamadas = tmp_path / "chamadas.log"
        fn = _extract_bash_function(script_text, "acquire_sudo")
        script = (
            "set -uo pipefail\n"
            "EUID=1000\nDRY_RUN=0\n_NEEDS_SUDO=1\nunset SUDO_ASKPASS\n"
            f'sudo() {{ echo "sudo $*" >> "{chamadas}"; [[ "$*" == "-A -v" ]]; }}\n'
            '_start_sudo_keepalive() { echo "credencial-mantida"; }\n'
            'log() { echo "log: $*"; }\nwarn() { echo "warn: $*"; }\n'
            f"{fn}\n"
            "acquire_sudo\n"
        )
        resultado = subprocess.run(
            ["bash", "-c", script], stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=15, check=False,
        )
        assert resultado.returncode == 0, resultado
        assert "credencial-mantida" in resultado.stdout, resultado
        pedidas = chamadas.read_text(encoding="utf-8").splitlines()
        assert "sudo -A -v" in pedidas, pedidas
        assert "sudo -v" not in pedidas, pedidas


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
