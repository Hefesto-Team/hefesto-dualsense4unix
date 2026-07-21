"""INSTALL-HEADLESS-01 (auditoria 21/07) — install/uninstall sem TTY.

`install.sh` roda com `set -euo pipefail`. O `ask_yn` fazia `read` de um
prompt; sem TTY (stdin em /dev/null — CI, pipe, headless) o `read` batia EOF,
retornava não-zero e o `set -e` MATAVA o script no 1o prompt (passo 4,
atalho/launcher), pulando os passos seguintes. O fix: sem TTY, `ask_yn` usa o
default seguro (o mesmo que o `-y` usaria) e nunca mata o script.

Também prova o suporte a SUDO_ASKPASS no `acquire_sudo` (install e uninstall):
com o helper setado, a credencial é validada por `-A` (sem exigir TTY).
"""
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
    """Roda o `ask_yn` real de install.sh sob `set -euo pipefail`, stdin fechado
    (headless), e devolve o REPLY. Se o script morresse no EOF do read, o
    subprocess sairia !=0 e o teste falharia com o rc."""
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
        # A guarda `[[ ! -t 0 ]]` precisa existir ANTES do read — é ela que
        # impede o EOF de matar o set -e.
        fn = _extract_bash_function(INSTALL, "ask_yn")
        assert "! -t 0" in fn
        pos_guarda = fn.index("! -t 0")
        pos_read = fn.index("read -r")
        assert pos_guarda < pos_read, "a guarda de TTY tem de vir antes do read"


class TestAcquireSudoAskpass:
    @pytest.mark.parametrize("script_text", [INSTALL, UNINSTALL])
    def test_acquire_sudo_suporta_askpass(self, script_text: str) -> None:
        fn = _extract_bash_function(script_text, "acquire_sudo")
        assert "SUDO_ASKPASS" in fn, (
            "acquire_sudo precisa tentar `sudo -A -v` quando SUDO_ASKPASS "
            "está setado (execução headless sem TTY)"
        )
        assert "sudo -A -v" in fn


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
