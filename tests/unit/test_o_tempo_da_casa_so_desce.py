"""O tempo da casa só desce: a memória do rápido não vê o bytecode, e a catraca do tempo morde."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


RECIBO = _carregar("scripts/recibo_da_medida.py", "_recibo_do_tempo")


# --- a memória do rápido: o bytecode que os portões escrevem não muda a chave ---------------------


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore git com `src/` e `scripts/` rastreados e o bytecode ignorado, como a da casa."""
    (tmp_path / "src/pacote").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src/pacote/a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "scripts/b.py").write_text("b = 2\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "__pycache__/\n*.pyc\nscripts/dispositivo.txt\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "x")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "base")
    return tmp_path


def _chave(raiz: Path, entradas: list[str]) -> str | None:
    ent = RECIBO.Entradas(raiz)
    return RECIBO.chave_do_portao(ent, "ambiente", "um-portao", "pytest", "", entradas)


def _escreve_bytecode(raiz: Path) -> None:
    for pasta in ("src/pacote", "scripts"):
        alvo = raiz / pasta / "__pycache__"
        alvo.mkdir(exist_ok=True)
        (alvo / "x.cpython-312.pyc").write_bytes(b"\x00bytecode novo")


@pytest.mark.parametrize(
    "entradas", ([], ["src/**", "scripts/**"], ["src/pacote/*.py", "scripts/*"]),
    ids=("sem-quinta-coluna", "globs-largos", "globs-do-py-e-do-resto"))
def test_o_bytecode_escrito_durante_a_corrida_nao_muda_a_chave(
        arvore: Path, entradas: list[str]) -> None:
    antes = _chave(arvore, entradas)
    assert antes, "o portão tem de poder ser lembrado"
    _escreve_bytecode(arvore)
    assert _chave(arvore, entradas) == antes, (
        "o `.pyc` que o próprio portão escreve mudou a chave: todo verde se descarta "
        "(«a árvore mudou durante a corrida») e a memória nunca lembra")


def test_o_fonte_ignorado_de_scripts_continua_na_chave(arvore: Path) -> None:
    """Só o bytecode sai: o resto do ignorado de `scripts/` segue entrando."""
    ausente = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("um\n", encoding="utf-8")
    um = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("dois\n", encoding="utf-8")
    assert len({ausente, um, _chave(arvore, [])}) == 3


def test_o_py_mudado_continua_mudando_a_chave(arvore: Path) -> None:
    antes = _chave(arvore, ["src/**"])
    (arvore / "src/pacote/a.py").write_text("a = 2\n", encoding="utf-8")
    assert _chave(arvore, ["src/**"]) != antes


def test_mordida_com_o_bytecode_devolvido_a_chave_a_chave_muda(
        arvore: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RECIBO, "_BYTECODE", re.compile(r"(?!x)x"))
    antes = _chave(arvore, ["src/**", "scripts/**"])
    _escreve_bytecode(arvore)
    assert _chave(arvore, ["src/**", "scripts/**"]) != antes, (
        "a mordida não mordeu: com o bytecode na chave, o `.pyc` novo tinha de mudá-la")
