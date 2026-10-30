from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
NOME = "hefesto-dualsense4unix"
TABELA = "docs/data/cores-do-dualsense.csv"


def _alvos() -> dict:
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return projeto["tool"]["hatch"]["build"]["targets"]


def _copia_da_arvore(destino: Path) -> Path:
    listados = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(RAIZ), capture_output=True, check=True
    ).stdout.split(b"\0")
    for bruto in listados:
        if not bruto:
            continue
        origem = RAIZ / bruto.decode("utf-8")
        if not origem.is_file():
            continue
        alvo = destino / bruto.decode("utf-8")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo, follow_symlinks=False)
    return destino


def test_o_wheel_declara_a_tabela_no_share() -> None:
    dados = _alvos()["wheel"]["shared-data"]
    assert dados.get(TABELA) == f"share/{NOME}/{TABELA}", dados.get(TABELA)
    assert (RAIZ / TABELA).is_file()


def test_o_sdist_lista_a_tabela() -> None:
    assert TABELA in _alvos()["sdist"]["only-include"]


def test_o_wheel_montado_fora_do_repo_tem_a_tabela_com_linhas(tmp_path: Path) -> None:
    if shutil.which("uv") is None:
        pytest.skip("sem uv neste ambiente")
    fonte = _copia_da_arvore(tmp_path / "fonte")
    saida = tmp_path / "saida"
    proc = subprocess.run(
        ["uv", "build", "--out-dir", str(saida)],
        cwd=str(fonte),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    (sdist,) = list(saida.glob("*.tar.gz"))
    (roda,) = list(saida.glob("*.whl"))
    with tarfile.open(sdist) as tar:
        nomes = {n.split("/", 1)[1] for n in tar.getnames() if "/" in n}
    assert TABELA in nomes, "o sdist veio sem a tabela das cores"

    prefixo = tmp_path / "prefixo"
    pacotes = tmp_path / "pacotes"
    with zipfile.ZipFile(roda) as zf:
        for membro in zf.namelist():
            if membro.endswith("/"):
                continue
            if ".data/data/" in membro:
                alvo = prefixo / membro.split(".data/data/", 1)[1]
            else:
                alvo = pacotes / membro
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(zf.read(membro))
    assert (prefixo / "share" / NOME / TABELA).is_file(), "o wheel veio sem a tabela das cores"

    lar = tmp_path / "lar"
    lar.mkdir()
    ambiente = {
        **os.environ,
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / "c"),
        "XDG_DATA_HOME": str(lar / "d"),
        "XDG_STATE_HOME": str(lar / "s"),
        "XDG_CACHE_HOME": str(lar / "k"),
    }
    ambiente.pop("PYTHONPATH", None)
    programa = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(pacotes)!r})\n"
        f"sys.prefix = {str(prefixo)!r}\n"
        "from hefesto_dualsense4unix.integrations import cor_do_plastico as c\n"
        "assert c.__file__.startswith(sys.path[0]), c.__file__\n"
        "print(json.dumps({'tabela': str(c.TABELA_DAS_CORES), 'linhas': len(c.TABELA),\n"
        "                  'tons': len(c.TONS)}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", programa],
        cwd=str(tmp_path),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    achado = json.loads(proc.stdout.strip().splitlines()[-1])
    assert achado["tabela"].startswith(str(prefixo)), achado
    assert achado["linhas"] > 0, f"a tabela chegou vazia: {achado}"
    assert achado["tons"] > 0, achado
