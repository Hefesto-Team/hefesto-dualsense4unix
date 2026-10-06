"""TELA-DELA-01 — a suíte não abre janela na sessão gráfica dela. NUNCA."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def test_a_suite_nao_enxerga_o_wayland_dela() -> None:
    """Dentro de um teste, o compositor dela não existe."""
    assert os.environ.get("WAYLAND_DISPLAY") is None, (
        "a suíte está enxergando o compositor VIVO — toda `Gtk.Window` daqui "
        "nasce na tela dela. É o defeito de 04/09/2026."
    )
    if os.environ.get("DISPLAY") is None:
        pytest.skip("sem sessão gráfica: não há tela para desviar")
    assert os.environ.get("GDK_BACKEND") == "x11", os.environ.get("GDK_BACKEND")
    display = os.environ.get("DISPLAY")
    assert display and display != ":1", (
        f"a suíte está apontada para a tela real ({display!r})."
    )


def test_o_escape_existe_e_tem_nome() -> None:
    """Quem PRECISA ver a janela declara — e o padrão seguro fica de pé."""
    codigo = (
        "import os; print(os.environ.get('WAYLAND_DISPLAY'), "
        "os.environ.get('GDK_BACKEND'))"
    )
    sonda = RAIZ / "tests" / "unit" / "conftest.py"
    assert not sonda.exists(), "um conftest local aqui mascararia a guarda"

    env = dict(os.environ)
    env["HEFESTO_NA_TELA"] = "1"
    env["WAYLAND_DISPLAY"] = "wayland-1"
    env["DISPLAY"] = ":1"
    env["GDK_BACKEND"] = "wayland,x11"
    env["PYTHONPATH"] = str(RAIZ / "src")
    r = subprocess.run(
        [sys.executable, "-c", f"import tests.conftest; {codigo}"],
        cwd=RAIZ, capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "wayland-1" in r.stdout, (
        "`HEFESTO_NA_TELA=1` não devolveu a sessão viva:\n" + r.stdout
    )


def test_sem_o_escape_a_guarda_age_mesmo_com_sessao_viva() -> None:
    """A METADE QUE IMPORTA: sessão viva no ambiente e a guarda desvia assim mesmo."""
    env = dict(os.environ)
    env.pop("HEFESTO_NA_TELA", None)
    env["WAYLAND_DISPLAY"] = "wayland-1"
    env["DISPLAY"] = ":1"
    env["GDK_BACKEND"] = "wayland,x11"
    env["PYTHONPATH"] = str(RAIZ / "src")
    r = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tests.conftest, os; "
            "print(os.environ.get('WAYLAND_DISPLAY'), os.environ.get('DISPLAY'))",
        ],
        cwd=RAIZ, capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "None" in r.stdout and ":1" not in r.stdout, (
        "a guarda deixou a sessão viva de pé — a próxima suíte vai abrir "
        "janela na tela dela.\n" + r.stdout
    )


def test_o_xvfb_morre_com_a_sessao_e_e_morto_pelo_pid() -> None:
    """Nada de processo órfão, e nada de `pkill -f` (que já derrubou o dela)."""
    from hefesto_dualsense4unix.utils import tela_de_mentira as tm

    assert "garantir_tela_de_mentira" in (
        RAIZ / "tests" / "conftest.py"
    ).read_text(encoding="utf-8")
    fonte = Path(tm.__file__ or "").read_text(encoding="utf-8")
    assert "atexit.register(derrubar_tela_de_mentira)" in fonte
    for forma in ('"pkill"', "'pkill'", "pkill -"):
        assert forma not in fonte.replace("um `pkill -f` já derrubou", ""), (
            f"o conftest chama {forma} — matar por padrão é proibido nesta "
            "casa: um `pkill -f` derrubou o compositor dela em 04/09/2026."
        )
    assert "proc.terminate()" in fonte and "proc.kill()" in fonte
