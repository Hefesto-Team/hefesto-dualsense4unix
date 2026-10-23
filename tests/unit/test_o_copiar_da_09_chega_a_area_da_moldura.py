"""O «Copiar» da aba Sistema chega à área de transferência pela moldura que nasceu (23/10/2026).

A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01: a lógica (`a09_sistema`) deixou de importar
a moldura (`interface.janela`) para pôr o registro na área de transferência; a `JanelaDaAba` que
nasce entrega a função dela a `utils/area_de_transferencia`, e o «Copiar» pede por ali. Os
testes da 09 trocam o `_por_na_area_de_transferencia` por um dublê, e nenhum deles vê o elo: sem
esta régua, a janela que deixasse de entregar a função calaria o «Copiar» com tudo verde.

O filho, num X de mentira e num lar de mentira, pede o «Copiar» antes da janela (sem moldura,
`False`) e depois dela (o texto chega à área de transferência do GTK).

MORDIDA (executada em 23/10/2026): arrancar o `_area.receber(por_na_area_de_transferencia)` do
`JanelaDaAba.__init__` faz o filho dizer `depois False` e a régua reprovar.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

_FILHO = textwrap.dedent(
    """
    import pathlib, sys, time
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    from hefesto_dualsense4unix.interface import janela as jn
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    print("antes", a09._por_na_area_de_transferencia("antes da janela"), flush=True)
    tela = jn.JanelaDaAba(arquivo=pathlib.Path(sys.argv[1]), titulo_esperado="Prova do copiar",
                          ao_carregar=lambda: None, oculta=True)
    print("depois", a09._por_na_area_de_transferencia("o registro de teste"), flush=True)
    contexto = GLib.MainContext.default()
    fim = time.monotonic() + 5.0
    while contexto.pending() and time.monotonic() < fim:
        contexto.iteration(False)
    print("na-area", Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text(), flush=True)
    """
)


@skip_sem_gi_real
def test_o_copiar_da_09_chega_a_area_de_transferencia_pela_janela(tmp_path: pathlib.Path) -> None:
    if shutil.which("xvfb-run") is None:  # pragma: no cover - máquina sem xvfb
        pytest.skip("sem `xvfb-run` a janela nasceria na tela de quem roda")
    html = tmp_path / "copiar.html"
    html.write_text(
        "<!doctype html><html><head><title>Prova do copiar</title></head><body>oi</body></html>",
        encoding="utf-8",
    )
    script = tmp_path / "filho_do_copiar.py"
    script.write_text(_FILHO, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11",
                    HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path / "config"),
                    XDG_DATA_HOME=str(tmp_path / "data"), XDG_STATE_HOME=str(tmp_path / "state"),
                    XDG_CACHE_HOME=str(tmp_path / "cache"))
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", "HEFESTO_NA_TELA"):
        ambiente.pop(nome, None)
    feito = subprocess.run(
        ["xvfb-run", "-a", sys.executable, str(script), str(html)],
        env=ambiente, capture_output=True, text=True, timeout=120, check=False,
    )
    assert feito.returncode == 0, (feito.stdout[-400:], feito.stderr[-800:])
    linhas = dict(linha.split(" ", 1) for linha in feito.stdout.splitlines() if " " in linha)
    assert linhas.get("antes") == "False", ("sem moldura o «Copiar» diz que não deu", linhas)
    assert linhas.get("depois") == "True", (
        "a janela que nasce não entregou a área de transferência ao «Copiar»", linhas)
    assert linhas.get("na-area") == "o registro de teste", linhas
