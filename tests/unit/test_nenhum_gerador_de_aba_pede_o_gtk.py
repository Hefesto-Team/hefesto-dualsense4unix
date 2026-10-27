"""Nenhum gerador de aba pede o GTK (A-ABA-SISTEMA-SE-GERA-SEM-O-GTK-01).

Um gerador escreve HTML: importar o `janela` (e com ele o `gi`) só por uma constante faz a página
exigir o PyGObject, e o `lint-test` do CI, que não tem `gi`, reprova os testes que geram as abas.

A recusa do `gi` mora no processo FILHO, que importa cada gerador do zero, com a pasta
`interface/` no `sys.path` como os próprios geradores a põem. Recusa no processo da régua não
alcança o filho, e foi assim que a medida de `91668dc62` deixou o `aba09` passar.

MORDIDA: devolva `from hefesto_dualsense4unix.interface import janela` ao `aba09.py` e o caso
`aba09` reprova nomeando `janela.py:12 ← aba09.py:18`.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
INTERFACE = SRC / "hefesto_dualsense4unix" / "interface"
PACOTE = "hefesto_dualsense4unix.interface"
OUTROS_GERADORES = ("monta", "regerar", "mapa", "calibrar", "pagina_do_mapa")
ABAS = sorted(p.stem for p in INTERFACE.glob("aba[0-9][0-9].py"))
GERADORES = (*ABAS, *OUTROS_GERADORES)

FILHO = r"""
import importlib, importlib.abc, json, os, sys, traceback

class _SemGtk(importlib.abc.MetaPathFinder):
    def find_spec(self, nome, caminho, alvo=None):
        if nome == "gi" or nome.startswith("gi."):
            raise ModuleNotFoundError(f"No module named {nome!r}", name=nome)
        return None

sys.meta_path.insert(0, _SemGtk())
importado, raizes = sys.argv[1], sys.argv[2:]
for raiz in reversed(raizes):
    sys.path.insert(0, raiz)
try:
    importlib.import_module(importado)
except BaseException as erro:
    quadros = [q for q in traceback.extract_tb(erro.__traceback__)
               if any(os.path.abspath(q.filename).startswith(r + os.sep) for r in raizes)]
    pilha = " ← ".join(f"{os.path.basename(q.filename)}:{q.lineno}" for q in reversed(quadros))
    gtk = isinstance(erro, ImportError) and (getattr(erro, "name", "") or "").split(".")[0] == "gi"
    veredito = {"ok": False, "gtk": gtk, "pilha": pilha, "erro": f"{type(erro).__name__}: {erro}"}
else:
    veredito = {"ok": True, "gtk": False, "pilha": "", "erro": ""}
print(json.dumps(veredito, ensure_ascii=False))
"""


def _importar_sem_gtk(modulo: str, *raizes: pathlib.Path) -> dict[str, object]:
    feito = subprocess.run(
        [sys.executable, "-c", FILHO, modulo, *(str(r) for r in raizes)],
        env=dict(os.environ, PYTHONPATH=str(SRC)), cwd=str(RAIZ),
        capture_output=True, text=True, timeout=120, check=False,
    )
    linhas = feito.stdout.strip().splitlines()
    assert feito.returncode == 0 and linhas, (
        f"o filho que importa `{modulo}` morreu sem veredito (rc={feito.returncode}):\n"
        f"{feito.stderr.strip()[-1200:]}")
    veredito: dict[str, object] = json.loads(linhas[-1])
    return veredito


def test_a_lista_vem_do_disco() -> None:
    """As dez abas e os outros geradores existem; a lista vazia passaria por verde."""
    assert len(ABAS) >= 10, ABAS
    faltam = [n for n in OUTROS_GERADORES if not (INTERFACE / f"{n}.py").is_file()]
    assert not faltam, f"geradores que a régua cobre e saíram do disco: {faltam}"


@pytest.mark.parametrize("gerador", GERADORES)
def test_o_gerador_importa_sem_o_gtk(gerador: str) -> None:
    """O gerador importa sem o `gi`: prova da D-2710-O-GERADOR-DE-ABA-NAO-PEDE-O-GTK."""
    veredito = _importar_sem_gtk(f"{PACOTE}.{gerador}", INTERFACE, SRC)
    assert not veredito["gtk"], (
        f"`{gerador}.py` pede o GTK para gerar uma página: {veredito['pilha']} "
        f"({veredito['erro']}). Constante sem GTK mora no `folha_da_casa.py`.")
    assert veredito["ok"], (
        f"`{gerador}.py` não importa, e não é pelo GTK: {veredito['erro']} "
        f"({veredito['pilha'] or 'sem pilha no código'})")


def test_a_regua_morde_o_modulo_que_importa_o_gtk(tmp_path: pathlib.Path) -> None:
    """Um módulo que importa o `gi` por baixo reprova pelo GTK, com a pilha até ele."""
    (tmp_path / "sonda_ponte.py").write_text("import json\nimport gi\n", encoding="utf-8")
    (tmp_path / "sonda_gerador.py").write_text("import os\nimport sonda_ponte\n", encoding="utf-8")
    veredito = _importar_sem_gtk("sonda_gerador", tmp_path)
    assert veredito["gtk"] and not veredito["ok"], veredito
    assert veredito["pilha"] == "sonda_ponte.py:2 ← sonda_gerador.py:2", veredito


def test_a_regua_nao_le_outro_erro_como_verde(tmp_path: pathlib.Path) -> None:
    """Um erro que não é o GTK reprova com o próprio texto, e não passa por verde."""
    (tmp_path / "sonda_quebrada.py").write_text("import modulo_que_nao_existe\n", encoding="utf-8")
    veredito = _importar_sem_gtk("sonda_quebrada", tmp_path)
    assert not veredito["ok"] and not veredito["gtk"], veredito
    assert "modulo_que_nao_existe" in str(veredito["erro"]), veredito
