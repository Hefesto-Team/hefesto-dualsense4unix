"""A versão sai do código que roda, e o ``dist-info`` só vale para a instalação por pacote.

O pacote é copiado para uma árvore e para um ``site-packages`` de mentira, e cada leitura é um
processo novo, com um ``dist-info`` de número diferente na frente do caminho de busca.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import hefesto_dualsense4unix as hefesto
from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.interface.pacotes import a09_sistema

FONTE = Path(hefesto.__file__)
RAIZ = FONTE.resolve().parents[2]
DO_DIST_INFO = "7.7.7"
PACOTE = "hefesto_dualsense4unix"


def _pyproject(numero: str, nome: str = "hefesto-dualsense4unix") -> str:
    return (f'[build-system]\nrequires = ["hatchling"]\n\n'
            f'[project]\nname = "{nome}"\nversion = "{numero}"\n\n'
            f'[tool.outra]\nversion = "0.0.0"\n')


def _dist_info(site: Path, numero: str = DO_DIST_INFO) -> None:
    pasta = site / f"{PACOTE}-{numero}.dist-info"
    pasta.mkdir(parents=True)
    (pasta / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: hefesto-dualsense4unix\nVersion: {numero}\n",
        encoding="utf-8")


def _pacote_em(pasta: Path) -> None:
    (pasta / PACOTE).mkdir(parents=True)
    shutil.copy(FONTE, pasta / PACOTE / "__init__.py")


def _ler_a_versao(*caminho: Path) -> str:
    return subprocess.run(
        [sys.executable, "-c", f"import {PACOTE} as h; print(h.__file__); print(h.__version__)"],
        capture_output=True, text=True, check=True, cwd=caminho[0],
        env={**os.environ, "PYTHONPATH": ":".join(str(c) for c in caminho)},
    ).stdout.split()[-1]


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    raiz = tmp_path / "clone"
    _pacote_em(raiz / "src")
    (raiz / "pyproject.toml").write_text(_pyproject("1.0.0"), encoding="utf-8")
    _dist_info(tmp_path / "venv")
    return raiz


def test_o_avanco_sem_install_muda_o_numero(arvore: Path, tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    assert _ler_a_versao(arvore / "src", venv) == "1.0.0"
    (arvore / "pyproject.toml").write_text(_pyproject("1.0.1"), encoding="utf-8")
    assert _ler_a_versao(arvore / "src", venv) == "1.0.1"


def test_a_instalacao_por_pacote_segue_o_numero_do_pacote(tmp_path: Path) -> None:
    site = tmp_path / "venv" / "lib" / "python3" / "site-packages"
    _pacote_em(site)
    _dist_info(site)
    assert _ler_a_versao(site) == DO_DIST_INFO


def test_um_pyproject_de_outro_projeto_nao_e_o_numero_do_produto(
    arvore: Path, tmp_path: Path,
) -> None:
    (arvore / "pyproject.toml").write_text(_pyproject("9.9.9", "outro"), encoding="utf-8")
    assert _ler_a_versao(arvore / "src", tmp_path / "venv") == DO_DIST_INFO


@pytest.mark.parametrize("texto", ["", "[project]\nname = \"hefesto-dualsense4unix\"\n", "\xff"])
def test_o_pyproject_sem_numero_cai_no_pacote(
    arvore: Path, tmp_path: Path, texto: str,
) -> None:
    (arvore / "pyproject.toml").write_bytes(texto.encode("latin-1"))
    assert _ler_a_versao(arvore / "src", tmp_path / "venv") == DO_DIST_INFO


def test_a_secao_de_outra_ferramenta_nao_da_o_numero(arvore: Path) -> None:
    (arvore / "pyproject.toml").write_text(
        '[tool.outra]\nname = "hefesto-dualsense4unix"\nversion = "9.9.9"\n', encoding="utf-8")
    assert _ler_a_versao(arvore / "src") != "9.9.9"


def test_o_numero_do_produto_e_o_do_pyproject_desta_arvore() -> None:
    assert hefesto.__version__ in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")


def test_o_comando_e_a_leitura_da_aba_dizem_o_numero_novo_depois_do_avanco(
    arvore: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(a09_sistema.perfil, "_com_o_src", lambda: None)
    monkeypatch.setattr(hefesto, "__file__", str(arvore / "src" / PACOTE / "__init__.py"))
    monkeypatch.delitem(hefesto.__dict__, "__version__", raising=False)
    assert a09_sistema._versao() == "1.0.0"

    (arvore / "pyproject.toml").write_text(_pyproject("1.0.1"), encoding="utf-8")
    monkeypatch.delitem(hefesto.__dict__, "__version__")
    assert CliRunner().invoke(app, ["version"]).stdout.strip() == "1.0.1"
    assert a09_sistema._versao() == "1.0.1"
    monkeypatch.delitem(hefesto.__dict__, "__version__")


def test_um_pacote_na_raiz_do_disco_nao_quebra_a_pergunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hefesto, "__file__", "/x/__init__.py")
    monkeypatch.delitem(hefesto.__dict__, "__version__", raising=False)
    assert isinstance(hefesto.__version__, str)
    monkeypatch.delitem(hefesto.__dict__, "__version__")
