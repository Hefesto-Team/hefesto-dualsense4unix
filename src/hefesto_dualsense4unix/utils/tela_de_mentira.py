"""A janela de instrumento não nasce na tela dela. TELA-DELA-02.

Ela reportou duas vezes em 04/09/2026: *"segue tudo abrindo na Meow ao invés
da OS"*. A metade da suíte foi curada no `tests/conftest.py` (TELA-DELA-01,
`Xvfb` próprio antes de qualquer import). Sobrava a outra metade, e ela é a que
os agentes disparam a mão: **24 scripts de `scripts/` abrem `Gtk.Window` de
verdade**, cada um numa execução, na sessão gráfica viva.

Nenhum script de workspace resolve isso: o `park` move a janela DEPOIS de ela
existir. A cura tem de ser ANTES — a janela não pode ter para onde nascer.

O QUE ESTE MÓDULO FAZ, e por que é redirecionar em vez de recusar: recusar
deixaria os 24 instrumentos inúteis até alguém acrescentar bandeira em cada um
(e o que falhou até aqui foi justamente "alguém lembrar"). Redirecionar mantém
os 24 funcionando e tira a tela dela do caminho.

O CUSTO, declarado: sob `Xvfb` não há gerenciador de janelas, e uma
`Gtk.Window` pode ficar 1x1 — é armadilha conhecida desta casa
(`COMO-OLHAR-A-TELA.md`). Por isso o desvio **se anuncia em stderr**: uma
medição estranha fica explicável em vez de virar diagnóstico errado. Quem
precisa de janela com gerente declara `HEFESTO_NA_TELA=1` — e aí a
responsabilidade pela tela dela é de quem declarou.

Quem usa `Gtk.OffscreenWindow` (o `--oculta` desta casa) não precisa de nada
disto e não é afetado: offscreen não toca compositor nenhum.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: O `Xvfb` deste processo. Guardado para matar **por PID** — nunca por padrão
#: de linha de comando (matar por padrão já derrubou o compositor dela).
_XVFB: subprocess.Popen[bytes] | None = None

#: Uma vez por processo, e só.
_JA_FEITO = False


def _ha_sessao_viva() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def garantir_tela_de_mentira(*, anunciar: bool = True) -> str | None:
    """Aponta o GTK para um ``Xvfb`` próprio. Devolve o ``DISPLAY``, ou ``None``.

    ``None`` quer dizer *"não havia nada a desviar"* — já era headless, ou quem
    chamou declarou ``HEFESTO_NA_TELA=1``.

    Chamar de novo é barato e não faz nada: uma tela por processo.
    """
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
        for _ in range(100):  # até 5 s; o socket é o sinal de "pronto"
            if Path(f"/tmp/.X11-unix/X{numero}").exists() or proc.poll() is not None:
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            continue  # esta tela não subiu; tenta a próxima
        _XVFB = proc
        os.environ["DISPLAY"] = f":{numero}"
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ["GDK_BACKEND"] = "x11"
        # Sob Xvfb não há GPU: o modo composto do WebKit TRAVA em vez de
        # reprovar, e um instrumento travado é pior que um vermelho.
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
