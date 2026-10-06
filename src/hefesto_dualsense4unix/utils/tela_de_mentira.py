"""A janela de instrumento não nasce na tela do usuário. TELA-DELA-02."""

from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_XVFB: subprocess.Popen[bytes] | None = None

_JA_FEITO = False


def _ha_sessao_viva() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def garantir_tela_de_mentira(*, anunciar: bool = True) -> str | None:
    """Aponta o GTK para um ``Xvfb`` próprio. Devolve o ``DISPLAY``, ou ``None``."""
    global _XVFB, _JA_FEITO

    if _JA_FEITO:
        return os.environ.get("DISPLAY")
    if os.environ.get("HEFESTO_NA_TELA") == "1":
        _JA_FEITO = True
        return None
    if not _ha_sessao_viva():
        _JA_FEITO = True
        return None

    xvfb = shutil.which("Xvfb")
    if xvfb is None:
        raise SystemExit(
            "Este instrumento abre uma janela GTK de verdade e NÃO há `Xvfb` "
            "para segurá-la: ela nasceria na sessão gráfica viva — a tela "
            "dela, que é uma só. Instale `xvfb`, ou assuma a tela com "
            "`HEFESTO_NA_TELA=1`."
        )

    for numero in range(80, 130):
        if Path(f"/tmp/.X11-unix/X{numero}").exists():
            continue
        proc = subprocess.Popen(
            [xvfb, f":{numero}", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if Path(f"/tmp/.X11-unix/X{numero}").exists() or proc.poll() is not None:
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            continue
        _XVFB = proc
        os.environ["DISPLAY"] = f":{numero}"
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ["GDK_BACKEND"] = "x11"
        os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        atexit.register(derrubar_tela_de_mentira)
        _JA_FEITO = True
        if anunciar:
            print(
                f"[tela] janela desviada para o Xvfb :{numero} — a tela dela "
                "não recebe nada. Sem gerenciador de janelas aqui: uma "
                "`Gtk.Window` pode medir 1x1. Para a sessão real: "
                "HEFESTO_NA_TELA=1",
                file=sys.stderr,
            )
        return f":{numero}"

    raise SystemExit(
        "Nenhuma tela Xvfb livre entre :80 e :129 — este instrumento não vai "
        "abrir janela na sessão dela para contornar isso."
    )


def derrubar_tela_de_mentira() -> None:
    """Mata o ``Xvfb`` **pelo PID deste processo**, e só ele."""
    global _XVFB
    proc = _XVFB
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    with contextlib.suppress(Exception):
        proc.wait(timeout=5)
    if proc.poll() is None:
        proc.kill()
    _XVFB = None
