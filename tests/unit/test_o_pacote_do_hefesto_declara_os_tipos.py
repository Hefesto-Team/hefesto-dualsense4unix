"""O-PACOTE-DO-HEFESTO-DECLARA-OS-TIPOS-01: o pacote leva o marcador `py.typed` (PEP 561).

Sem o marcador, o mypy de quem importa o Hefesto (uma extensão, por exemplo) pula o pacote
como «sem tipos» (`import-untyped`), e as anotações dele não valem lá fora: a extensão Lovense
precisava de `follow_untyped_imports` para o `hefesto_dualsense4unix`, um contorno do lado de
quem importa. O marcador vazio declara o pacote inteiro tipado.

Duas réguas:

1. o marcador mora no pacote e é vazio (um `partial` declararia o pacote incompleto);
2. o wheel e o sdist construídos de verdade (`uv build`, o wheel feito do sdist) o levam.

MORDIDA: apagar `src/hefesto_dualsense4unix/py.typed` reprova as duas.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MARCADOR = "hefesto_dualsense4unix/py.typed"


def _copia_da_arvore(destino: Path) -> Path:
    """A árvore de agora (o que o git rastreia, com o que está editado) num tmp, para o
    `uv build` não deixar `dist/` nem `.egg-info` no repositório."""
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


def test_o_marcador_mora_no_pacote_e_e_vazio() -> None:
    # D-2510-O-PACOTE-DECLARA-OS-TIPOS
    marcador = RAIZ / "src" / MARCADOR
    assert marcador.is_file(), f"o pacote veio sem {MARCADOR}"
    assert marcador.read_text(encoding="utf-8").strip() == "", (
        "o marcador declara o pacote parcial; o Hefesto declara os tipos do pacote inteiro"
    )


def test_o_wheel_e_o_sdist_de_verdade_levam_o_marcador(tmp_path: Path) -> None:
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
    assert f"src/{MARCADOR}" in nomes, "o sdist veio sem o py.typed"
    with zipfile.ZipFile(roda) as zf:
        assert MARCADOR in zf.namelist(), "o wheel veio sem o py.typed"
