"""DIÁLOGO-QUE-MATA-A-JANELA-01 — o aviso que deixou a janela dela morta (06/08)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("diálogo que não mata a janela")

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_APP = _RAIZ / "src" / "hefesto_dualsense4unix" / "app"

_PRAZO_S = 30.0


_PRELUDIO = """
import json, sys, time
sys.path.insert(0, {raiz!r})
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.app import gui_dialogs

assert Gtk.init_check(None)[0], "o GTK falhou ao iniciar sob o Xvfb"


def _o_dialogo():
    vivos = [
        w for w in Gtk.Window.list_toplevels()
        if isinstance(w, Gtk.MessageDialog)
    ]
    return vivos[0] if vivos else None


marcas = {{}}
pai = Gtk.Window()
pai.set_title("janela principal de mentira")
pai.show_all()
"""

_EPILOGO = """
marcas["dialogos_restantes"] = sum(
    1 for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.MessageDialog)
)
print("HEFESTO_JSON " + json.dumps(marcas))
"""


def _sob_xvfb(corpo: str, tmp_path: Path) -> dict:
    """Roda ``corpo`` com GTK real num display descartável; devolve as marcas."""
    if shutil.which("xvfb-run") is None:  # pragma: no cover — máquina sem xvfb
        pytest.skip("sem `xvfb-run` — este teste exige um display descartável")

    script = _PRELUDIO.format(raiz=str(_RAIZ / "src")) + corpo + _EPILOGO
    ambiente = dict(os.environ)
    ambiente["HOME"] = str(tmp_path)
    ambiente["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    ambiente["XDG_DATA_HOME"] = str(tmp_path / "data")
    ambiente["GDK_BACKEND"] = "x11"
    ambiente.pop("WAYLAND_DISPLAY", None)
    try:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=_PRAZO_S,
            check=False,
            env=ambiente,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o diálogo ESTRANGULOU a janela: o processo passou de "
            f"{_PRAZO_S:.0f}s dentro do laço sem devolver resposta — é o "
            "defeito de 06/08/2026 (`nem consigo fazer nada nem fechar`) "
            "voltando. O vigia de `gui_dialogs.executar_dialogo` está no lugar?"
        )
    if proc.returncode != 0:
        pytest.fail(f"o subprocesso GTK falhou (rc={proc.returncode}):\n{proc.stderr}")
    for linha in proc.stdout.splitlines():
        if linha.startswith("HEFESTO_JSON "):
            return dict(json.loads(linha[len("HEFESTO_JSON ") :]))
    pytest.fail(f"o subprocesso não imprimiu as marcas:\n{proc.stdout}\n{proc.stderr}")


_RECEPTORES_QUE_NAO_SAO_DIALOGO = {"subprocess", "asyncio"}

_AUTORIZADOS_A_BLOQUEAR = {
    "app.py::main",
    "gui_dialogs.py::executar_dialogo",
    "main.py::main",
}


def _chamadas_a_run(caminho: Path, raiz: Path | None = None) -> dict[str, list[int]]:
    """``{"arquivo::função": [linhas]}`` para cada ``x.run()`` de ``caminho``."""
    relativo = caminho.relative_to(raiz or _APP).as_posix()
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: dict[str, list[int]] = {}

    def _andar(no: ast.AST, funcao: str) -> None:
        for filho in ast.iter_child_nodes(no):
            dentro = funcao
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dentro = filho.name
            if (
                isinstance(filho, ast.Call)
                and isinstance(filho.func, ast.Attribute)
                and filho.func.attr == "run"
            ):
                receptor = ast.unparse(filho.func.value).split(".")[0]
                if receptor not in _RECEPTORES_QUE_NAO_SAO_DIALOGO:
                    achados.setdefault(f"{relativo}::{dentro}", []).append(
                        filho.lineno
                    )
            _andar(filho, dentro)

    _andar(arvore, "<módulo>")
    return achados


def test_nenhum_dialogo_bloqueante_fora_do_envelope_da_casa() -> None:
    """Quem escrever o próximo aviso não precisa lembrar de nada."""
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        for chave, linhas in _chamadas_a_run(caminho).items():
            if chave in _AUTORIZADOS_A_BLOQUEAR:
                continue
            ofensores[chave] = linhas

    assert ofensores == {}, (
        "`.run()` bloqueante fora do envelope (DIÁLOGO-QUE-MATA-A-JANELA-01): "
        f"{ofensores} — use `gui_dialogs.executar_dialogo(dialog, nome=...)`. "
        "Um diálogo que nasce invisível com `run()` cru deixa a janela dela "
        "morta, e foi o que aconteceu em 06/08/2026 às 20h22"
    )


def test_a_lista_de_autorizados_a_bloquear_nao_cresce_em_silencio() -> None:
    """Sem esta trava o portão se dissolveria por acréscimo."""
    assert sorted(_AUTORIZADOS_A_BLOQUEAR) == [
        "app.py::main",
        "gui_dialogs.py::executar_dialogo",
        "main.py::main",
    ]


def test_o_portao_pegaria_um_dialogo_novo_com_run_cru(tmp_path: Path) -> None:
    """O portão MORDE — provado contra um arquivo forjado, não por fé."""
    forjado = tmp_path / "aviso_novo.py"
    forjado.write_text(
        "import subprocess\n"
        "\n"
        "def confirmar_algo(dialog):\n"
        "    subprocess.run(['true'])\n"
        "    return dialog.run()\n",
        encoding="utf-8",
    )
    achados = _chamadas_a_run(forjado, raiz=tmp_path)

    assert achados == {"aviso_novo.py::confirmar_algo": [5]}
    assert "aviso_novo.py::confirmar_algo" not in _AUTORIZADOS_A_BLOQUEAR


_AUTORIZADOS_A_MOSTRAR_MODAL = frozenset({
    "gui_dialogs.py::_mostrar_e_vigiar",
})


