"""A janela reconhece a página do produto pelo conteúdo, não pelo prefixo do título.

O-PILOTO-RECONHECE-A-PAGINA-PELO-CONTEUDO-01 (14/11/2026): o `hefesto_vivo` só dava a página por
carregada quando o título trazia «Hefesto — aba », e a primeira carga da `mapa-do-controle.html`
(«Hefesto — o mapa do controle») matava a janela com «carregou OUTRA página». Com
`titulo_esperado=None`, a página se reconhece por morar na pasta das páginas da janela, num
arquivo que existe, com o vocabulário que o piloto dirige (`data-campo`, `data-gesto`).

MORDIDA: devolver ao `_confirmar_a_pagina` a conferência pelo prefixo «Hefesto — aba » reprova o
caso do mapa (a janela morre na primeira carga).

Tudo roda num filho sob `xvfb-run`, num lar de mentira: nada fala com a sessão de quem roda.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("O-PILOTO-RECONHECE-A-PAGINA-PELO-CONTEUDO-01")

from hefesto_dualsense4unix.interface import janela as jn

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("xvfb-run") is None,
    reason="sem `xvfb-run` a janela nasceria na tela de quem roda",
)

DA_CASA = ('<!doctype html><meta charset="utf-8"><title>{titulo}</title>'
           '<body><button data-gesto="ir">Ir</button><b data-campo="nome">x</b>'
           '<script>document.title = {depois};</script></body>')
SEM_VOCABULARIO = ('<!doctype html><meta charset="utf-8"><title>Hefesto — aba JOGAR</title>'
                   '<body><p>sem nada que o piloto dirija</p></body>')

_FILHO = textwrap.dedent(
    """
    import json, pathlib, sys
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import GLib, Gtk
    alvo = pathlib.Path(sys.argv[1])
    fim = {}
    def carregou():
        fim["carregou"] = True
        Gtk.main_quit()
    def falhou(motivo):
        fim["falhou"] = motivo
        Gtk.main_quit()
    tela = jn.JanelaDaAba(arquivo=alvo, titulo_esperado=None, ao_carregar=carregou,
                          ao_falhar=falhou, oculta=True)
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()
    print("FIM " + json.dumps(fim), flush=True)
    """
)


@pytest.fixture
def lar() -> Iterator[Path]:
    pasta = Path(tempfile.mkdtemp(prefix="pag-", dir="/tmp"))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _ambiente_do_lar(lar: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER",
                        "PIPEWIRE_REMOTE", "HEFESTO_SEM_JANELA", "HEFESTO_NA_TELA"}}
    env.update(
        HOME=str(lar), XDG_CONFIG_HOME=str(lar / "c"), XDG_DATA_HOME=str(lar / "d"),
        XDG_STATE_HOME=str(lar / "s"), XDG_CACHE_HOME=str(lar / "k"),
        XDG_RUNTIME_DIR=str(lar / "r"), GDK_BACKEND="x11",
        DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={lar / 'r' / 'sem-barramento'}",
        HEFESTO_BROKER_SOCKET=str(lar / "r" / "sem-broker.sock"),
        PYTHONPATH=str(RAIZ / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
    )
    for pasta in ("c", "d", "s", "k", "r"):
        (lar / pasta).mkdir(exist_ok=True)
    (lar / "r").chmod(0o700)
    return env


def _abrir(lar: Path, alvo: Path) -> dict[str, object]:
    script = lar / "filho.py"
    script.write_text(_FILHO, encoding="utf-8")
    feito = subprocess.run(
        ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24", sys.executable, str(script), str(alvo)],
        env=_ambiente_do_lar(lar), capture_output=True, text=True, timeout=90, check=False)
    linhas = [x for x in feito.stdout.splitlines() if x.startswith("FIM ")]
    assert linhas, f"o filho não terminou: rc {feito.returncode}\n{feito.stderr[-2000:]}"
    resultado: dict[str, object] = json.loads(linhas[-1][4:])
    return resultado


@pytest.mark.parametrize(("titulo", "depois"), [
    ("Hefesto — o mapa do controle", "'Hefesto — Trocar os botões'"),
    ("Hefesto — calibrar giroscópio", "document.title"),
    ("Hefesto — aba JOGAR", "document.title"),
], ids=("mapa-com-ancora", "calibrar", "aba"))
def test_a_primeira_carga_de_uma_pagina_da_casa_confirma(
        lar: Path, titulo: str, depois: str) -> None:
    telas = lar / "telas"
    telas.mkdir()
    alvo = telas / "mapa.html"
    alvo.write_text(DA_CASA.format(titulo=titulo, depois=depois), encoding="utf-8")
    assert _abrir(lar, alvo) == {"carregou": True}


def test_a_pagina_sem_o_vocabulario_do_piloto_morre(lar: Path) -> None:
    alvo = lar / "sem.html"
    alvo.write_text(SEM_VOCABULARIO, encoding="utf-8")
    fim = _abrir(lar, alvo)
    assert "carregou OUTRA página" in str(fim.get("falhou")), fim


def test_o_arquivo_que_nao_existe_morre(lar: Path) -> None:
    fim = _abrir(lar, lar / "sumida.html")
    assert "falhou" in fim and "carregou" not in fim, fim


@pytest.mark.parametrize(("resposta", "esperado"), [
    ({"titulo": "x", "caminho": "/pasta/a.html", "da_casa": True}, True),
    ({"titulo": "x", "caminho": "/outra/a.html", "da_casa": True}, False),
    ({"titulo": "x", "caminho": "/pasta/a.html", "da_casa": False}, False),
    ({"titulo": "x", "caminho": "", "da_casa": True}, False),
], ids=("da-casa", "outra-pasta", "sem-vocabulario", "about-blank"))
def test_o_veredito_da_pagina(tmp_path: Path, resposta: dict[str, object], esperado: bool) -> None:
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    (pasta / "a.html").write_text("x", encoding="utf-8")
    (tmp_path / "outra").mkdir()
    (tmp_path / "outra" / "a.html").write_text("x", encoding="utf-8")
    caminho = str(resposta["caminho"])
    if caminho:
        resposta = {**resposta, "caminho": str(tmp_path) + caminho}
    assert jn.e_pagina_da_casa(json.dumps(resposta), pasta)[0] is esperado
