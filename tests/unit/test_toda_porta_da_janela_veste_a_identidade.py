"""Toda porta que abre a janela veste a identidade ANTES de ela nascer.

O-ICONE-DO-DOCK-E-O-DO-HEFESTO-01 (07/10/2026, item B1.9 da bancada: «a logo some»). A janela abria
por duas portas e só uma vestia o nome: o `run.sh --gui` passava por `scripts/abrir_interface.py`
(prgname, classe, ícone), e o console script `hefesto-dualsense4unix-gui` ia direto ao piloto, que
se anunciava `hefesto-dualsense4unix-gui` — nome que nenhum `.desktop` casa. A bandeja, que herda o
`PATH` da `.venv`, abre o painel por essa segunda porta.

A fonte da verdade é o `.desktop` versionado (o nome do arquivo e o `StartupWMClass`) e o do
Flatpak, lidos do disco: nunca `identidade.py`, que é o que o código diz de si.

Três réguas, medidas num SUBPROCESSO em lar de mentira (HOME, XDG_STATE_HOME e XDG_RUNTIME_DIR
desviados; sem `WAYLAND_DISPLAY`; o piloto trocado por um dublê que só registra no momento em que a
janela nasceria):

1. o alvo do console script, lido do `pyproject.toml`, chega ao piloto com o prgname do `.desktop`,
   a classe do `StartupWMClass`, `HEFESTO_NA_TELA=1` por padrão e o `DISPLAY` que o teste deu;
2. a porta `scripts/abrir_interface.py` dá nos mesmos três valores;
3. a ordem: nenhum `gi.repository` quando o saneamento do GdkPixbuf roda, e nenhum piloto carregado
   antes da identidade (o dublê registra cada vez que roda, e roda uma vez só, já vestido).

MORDIDAS: o alvo do console script de volta a `hefesto_vivo:main` reprova a 1; a chamada de
`vestir_a_identidade` arrancada reprova a 1 e a 2; `import hefesto_vivo` no topo de `abrir.py`
reprova a 3; a entrada sem o `HEFESTO_NA_TELA` padrão reprova a 1; a guarda de tela de volta ao
import de `abrir.py` reprova a 1 (o `DISPLAY` muda); o piloto importado antes de
`tomar_a_vez` reprova a 3.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o filho roda a entrada de verdade: a identidade é do GLib e do Gdk")

RAIZ = Path(__file__).resolve().parents[2]
DESKTOP = RAIZ / "packaging" / "hefesto-dualsense4unix.desktop"
DESKTOP_FLATPAK = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.desktop"
CONSOLE_SCRIPT = "hefesto-dualsense4unix-gui"
TETO_DO_FILHO_SEC = 90.0

_DUBLE = '''
"""O piloto de mentira: registra o que a janela veria e sai."""
import json, os, sys
import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib
with open(os.environ["HEFESTO_REGISTRO"], "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "prgname": GLib.get_prgname(),
        "classe": Gdk.get_program_class(),
        "na_tela": os.environ.get("HEFESTO_NA_TELA"),
        "display": os.environ.get("DISPLAY"),
        "wayland": os.environ.get("WAYLAND_DISPLAY"),
    }) + "\\n")
'''

_FILHO = '''
import importlib, json, os, sys, threading, time
vigia = threading.Timer(float(os.environ["HEFESTO_VIGIA"]), lambda: os._exit(3))
vigia.daemon = True
vigia.start()
registro = os.environ["HEFESTO_REGISTRO"]
porta, alvo = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.environ["HEFESTO_DUBLE_DIR"])

from hefesto_dualsense4unix.app import arranque

_real = arranque.sanear_loaders_do_gdk_pixbuf
def _espiao():
    com_gi = sorted(m for m in sys.modules if m.startswith("gi.repository"))
    pilotos = sorted(m for m in sys.modules if m.endswith(
        ("hefesto_vivo", "controles_vivos", "piloto_de_registro")))
    with open(registro + ".ordem", "w", encoding="utf-8") as f:
        json.dump({"gi": com_gi, "pilotos": pilotos}, f)
    return _real()
arranque.sanear_loaders_do_gdk_pixbuf = _espiao

def _dubla(mod_):
    if hasattr(mod_, "CANDIDATOS_DO_PILOTO"):
        mod_.CANDIDATOS_DO_PILOTO = ("piloto_de_registro",)

if porta == "console":
    mod_nome, func = alvo.split(":")
    mod_ = importlib.import_module(mod_nome)
    _dubla(mod_)
    sys.argv = ["hefesto-dualsense4unix-gui"]
    sys.exit(getattr(mod_, func)())
else:
    sys.path.insert(0, os.path.join(os.environ["HEFESTO_RAIZ"], "scripts"))
    import abrir_interface
    from hefesto_dualsense4unix.interface import abrir
    _dubla(abrir)
    sys.argv = ["abrir_interface.py"]
    sys.exit(abrir_interface.main([]))
'''


def _chave(arquivo: Path, nome: str) -> str:
    achado = re.search(rf"^{nome}=(.*)$", arquivo.read_text(encoding="utf-8"), re.M)
    assert achado, f"{arquivo.name} não tem `{nome}=`"
    return achado.group(1).strip()


def _alvo_do_console_script() -> str:
    try:
        import tomllib
    except ImportError:  # pragma: no cover — 3.10 (o pytest traz o tomli)
        import tomli as tomllib  # type: ignore[no-redef]
    dados = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["scripts"][CONSOLE_SCRIPT])


@pytest.fixture(scope="module")
def lar() -> Iterator[Path]:
    """Um lar de mentira curto: o diário e o lock da vez única moram aqui."""
    pasta = Path(tempfile.mkdtemp(prefix="hf-porta-", dir="/tmp"))
    pasta.chmod(0o700)
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def _abrir_por(porta: str, lar: Path, *, na_tela: str | None) -> dict[str, Any]:
    """Roda a porta num filho, e devolve o que o dublê viu e o que o saneamento viu."""
    display = os.environ.get("DISPLAY")
    if not display:
        pytest.skip("sem tela de mentira (Xvfb) para o filho: a suíte a sobe no conftest")
    casa = lar / porta
    runtime = casa / "run"
    for pasta in (casa / "home", casa / "state", casa / "config", casa / "data", runtime):
        pasta.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)
    registro = casa / "registro.json"
    (casa / "piloto_de_registro.py").write_text(_DUBLE, encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(RAIZ / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(casa / "home"),
        "XDG_STATE_HOME": str(casa / "state"),
        "XDG_CONFIG_HOME": str(casa / "config"),
        "XDG_DATA_HOME": str(casa / "data"),
        "XDG_RUNTIME_DIR": str(runtime),
        "DISPLAY": display,
        "GDK_BACKEND": "x11",
        "HEFESTO_REGISTRO": str(registro),
        "HEFESTO_DUBLE_DIR": str(casa),
        "HEFESTO_RAIZ": str(RAIZ),
        "HEFESTO_VIGIA": "40",
    }
    if na_tela is not None:
        env["HEFESTO_NA_TELA"] = na_tela
    alvo = _alvo_do_console_script() if porta == "console" else ""
    proc = subprocess.run(
        [sys.executable, "-c", _FILHO, porta, alvo],
        env=env, cwd=casa, capture_output=True, text=True, timeout=TETO_DO_FILHO_SEC,
    )
    saida: dict[str, Any] = {"rc": proc.returncode, "texto": proc.stdout + proc.stderr,
                             "display_dado": display}
    ordem = Path(str(registro) + ".ordem")
    saida["ordem"] = json.loads(ordem.read_text()) if ordem.is_file() else None
    saida["janelas"] = (
        [json.loads(linha) for linha in registro.read_text().splitlines() if linha.strip()]
        if registro.is_file() else []
    )
    saida["janela"] = saida["janelas"][-1] if saida["janelas"] else None
    for diario in (casa / "state").rglob("interface.log"):
        saida["texto"] += "\n--- diário ---\n" + diario.read_text(errors="replace")
    return saida


@pytest.fixture(scope="module")
def pela_console(lar: Path) -> dict[str, Any]:
    """O console script do pyproject, sem `HEFESTO_NA_TELA` no ambiente de quem chamou."""
    return _abrir_por("console", lar, na_tela=None)


@pytest.fixture(scope="module")
def pelo_lancador(lar: Path) -> dict[str, Any]:
    """`scripts/abrir_interface.py`, a porta do `run.sh --gui`, com a tela declarada."""
    return _abrir_por("lancador", lar, na_tela="1")


def _a_janela(medida: dict[str, Any], porta: str) -> dict[str, Any]:
    assert medida["janela"] is not None, (
        f"a porta `{porta}` não chegou ao piloto (rc={medida['rc']}):\n{medida['texto'][-3000:]}"
    )
    assert medida["rc"] == 0, (
        f"a porta `{porta}` não saiu limpa (rc={medida['rc']}; 3 é o vigia):\n"
        f"{medida['texto'][-3000:]}"
    )
    return medida["janela"]  # type: ignore[no-any-return]


class TestOAlvoDoConsoleScriptPassaPelaIdentidade:
    """Régua 1 — o que o console script abre se anuncia como o `.desktop`."""

    def test_o_alvo_nao_e_o_piloto_nu(self) -> None:
        alvo = _alvo_do_console_script()
        assert "hefesto_vivo" not in alvo and "controles_vivos" not in alvo, (
            f"o console script `{CONSOLE_SCRIPT}` aponta para o piloto nu ({alvo}): a janela "
            "se anuncia pelo argv[0] e nenhum `.desktop` casa"
        )

    def test_o_prgname_e_o_nome_do_desktop(self, pela_console: dict[str, Any]) -> None:
        janela = _a_janela(pela_console, "console")
        assert janela["prgname"] == DESKTOP.stem, (
            "o app_id do Wayland é o prgname: tem de ser o nome do `.desktop`, ou o dock mostra "
            f"a engrenagem e a dica `{janela['prgname']}`"
        )

    def test_a_classe_e_o_startupwmclass_letra_por_letra(
        self, pela_console: dict[str, Any]
    ) -> None:
        janela = _a_janela(pela_console, "console")
        assert janela["classe"] == _chave(DESKTOP, "StartupWMClass")
        assert janela["classe"] == _chave(DESKTOP_FLATPAK, "StartupWMClass"), (
            "o Flatpak chama o mesmo console script: a classe tem de casar o `.desktop` dele"
        )

    def test_a_janela_vai_para_a_tela_de_quem_pediu(self, pela_console: dict[str, Any]) -> None:
        """A bandeja não declara `HEFESTO_NA_TELA`: a entrada do produto é que a põe."""
        janela = _a_janela(pela_console, "console")
        assert janela["na_tela"] == "1", (
            "sem `HEFESTO_NA_TELA=1` por padrão a bandeja abriria o painel num Xvfb"
        )
        assert janela["display"] == pela_console["display_dado"], (
            "a guarda desviou o painel para um Xvfb próprio: a janela não nasce na tela de quem "
            "clicou"
        )


class TestAsDuasPortasDaoNoMesmo:
    """Régua 2 — `scripts/abrir_interface.py` e o console script não divergem."""

    def test_os_tres_valores_sao_os_mesmos(
        self, pela_console: dict[str, Any], pelo_lancador: dict[str, Any]
    ) -> None:
        a = _a_janela(pela_console, "console")
        b = _a_janela(pelo_lancador, "lancador")
        for campo in ("prgname", "classe", "na_tela"):
            assert a[campo] == b[campo], (
                f"as portas divergem em `{campo}`: console={a[campo]!r} lançador={b[campo]!r}"
            )
        assert b["display"] == pelo_lancador["display_dado"]
        assert b["prgname"] == DESKTOP.stem and b["classe"] == _chave(DESKTOP, "StartupWMClass"), (
            "as duas portas iguais não bastam: as duas podem estar sem a identidade. O lançador "
            f"se anunciou {b['prgname']!r}/{b['classe']!r}, e o `.desktop` diz "
            f"{DESKTOP.stem!r}/{_chave(DESKTOP, 'StartupWMClass')!r}"
        )


class TestAIdentidadeVemAntesDoPiloto:
    """Régua 3 — a ordem que o GTK cobra."""

    @pytest.mark.parametrize("porta", ["console", "lancador"])
    def test_o_saneamento_roda_antes_de_qualquer_gtk_e_de_qualquer_piloto(
        self, porta: str, pela_console: dict[str, Any], pelo_lancador: dict[str, Any]
    ) -> None:
        medida = pela_console if porta == "console" else pelo_lancador
        _a_janela(medida, porta)
        ordem = medida["ordem"]
        assert ordem is not None, f"a porta `{porta}` não chamou o saneamento do GdkPixbuf"
        assert ordem["gi"] == [], (
            "o GdkPixbuf só se sanea ANTES de qualquer `gi.repository`; já estavam: "
            f"{ordem['gi']}"
        )
        assert ordem["pilotos"] == [], (
            f"o piloto já estava carregado antes da identidade: {ordem['pilotos']}"
        )
        nome, classe = DESKTOP.stem, _chave(DESKTOP, "StartupWMClass")
        assert [(j["prgname"], j["classe"]) for j in medida["janelas"]] == [(nome, classe)], (
            "o piloto rodou mais de uma vez, ou rodou antes da identidade: "
            f"{medida['janelas']}"
        )
