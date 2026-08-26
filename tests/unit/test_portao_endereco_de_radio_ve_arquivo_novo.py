"""Os dois buracos do `scripts/check_endereco_de_radio.py`, medidos em 26/08/2026.

O portão pega endereço de rádio por FORMA, sem consultar OUI nenhum — é a
segunda régua, irmã independente do `tests/unit/test_docs_mac_anonimato.py`. Só
que ele tinha dois pontos cegos, e a docstring dele AFIRMAVA que o primeiro
estava curado:

1. **A listagem lia só o ÍNDICE.** `git ls-files -z` pelado não traz arquivo
   novo. Arquivo recém-escrito por um agente, ainda sem `git add`, passava
   VERDE — que é exatamente quando ninguém revisou nada. A cura estava pronta
   no irmão desde 15/08 (`_tracked_files`, cicatriz
   ANONIMATO-CEGO-A-ARQUIVO-NOVO-02): `--cached --others --exclude-standard`.
2. **`.svg` estava no `EXCLUIR_SUFIXO`,** ao lado de `.png` e `.zip`. SVG é XML
   de texto puro — são 49 arquivos versionados nesta árvore, todos texto — e um
   endereço dentro de um deles passava **mesmo já commitado**. Este não era
   cegueira a arquivo novo: era buraco permanente.

O TERCEIRO teste é a outra metade da cura 1: `--exclude-standard` não pode ser
esquecido, senão o portão passa a acusar `.venv/`, build e captura, e portão que
grita falso é portão que se desliga.

**Nenhum endereço de seis grupos aparece LITERAL neste arquivo**, e isso é de
propósito: o próprio portão varre `tests/`, e um literal aqui se acusaria. O
endereço é montado em tempo de execução a partir de dois pedaços.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_REL = "scripts/check_endereco_de_radio.py"

#: Endereço que NÃO identifica ninguém e que o portão TEM de acusar.
#:
#: O primeiro octeto `06` tem o bit 1 ligado: é da faixa **localmente
#: administrada**, que a IEEE nunca atribui a fabricante — logo não há unidade
#: no mundo com ele. E ele não é nenhuma das isenções do portão: não é `02:`
#: (o fabricado pelo driver), não é `AA:BB:` (o didático), não é broadcast nem
#: nulo, e os octetos 4 e 5 não estão zerados (a máscara da casa).
_OUI_DE_MENTIRA = "06:DE:AD"
_SUFIXO_DE_MENTIRA = "BE:EF:01"
MAC_DE_MENTIRA = f"{_OUI_DE_MENTIRA}:{_SUFIXO_DE_MENTIRA}"


@pytest.fixture
def repo_falso(tmp_path: Path) -> Path:
    """Repo de mentira com o portão copiado e um `git init` de verdade.

    O portão resolve a raiz por `__file__`, então a cópia em `scripts/` faz a
    árvore temporária virar a raiz varrida.
    """
    origem = Path(__file__).resolve().parents[2] / SCRIPT_REL
    if not origem.exists():
        pytest.skip(f"{SCRIPT_REL} não encontrado no repo")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copy2(origem, tmp_path / SCRIPT_REL)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


def rodar(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT_REL],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def test_arquivo_novo_sem_git_add_e_pego(repo_falso: Path) -> None:
    """O portão enxerga o arquivo NOVO, antes de qualquer `git add`."""
    (repo_falso / "docs" / "ja-revisado.md").write_text(
        "nada de endereço aqui\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=repo_falso, check=True, capture_output=True)

    # Este NUNCA passa por `git add`: é o arquivo que o agente acabou de colar.
    (repo_falso / "docs" / "recem-colado.md").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )

    r = rodar(repo_falso)
    assert r.returncode == 1, (
        "arquivo novo com endereço passou VERDE: a listagem voltou a olhar só "
        f"o índice.\nsaída:\n{r.stdout}"
    )
    assert "recem-colado.md" in r.stdout, r.stdout


def test_arquivo_que_o_gitignore_manda_ignorar_nao_reprova(repo_falso: Path) -> None:
    """A outra metade: `--exclude-standard` não pode ser esquecido."""
    (repo_falso / ".gitignore").write_text("lixo/\n", encoding="utf-8")
    (repo_falso / "lixo").mkdir()
    (repo_falso / "lixo" / "captura.txt").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )

    r = rodar(repo_falso)
    assert r.returncode == 0, (
        "o portão acusou o que o `.gitignore` manda ignorar — sem "
        f"`--exclude-standard` ele grita falso.\nsaída:\n{r.stdout}"
    )


def test_svg_e_varrido(repo_falso: Path) -> None:
    """SVG é texto, e mesmo COMMITADO o endereço dentro dele passava."""
    (repo_falso / "docs" / "diagrama.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        f"<text>adaptador {MAC_DE_MENTIRA}</text></svg>\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo_falso, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "svg"],
        cwd=repo_falso, check=True, capture_output=True,
    )

    r = rodar(repo_falso)
    assert r.returncode == 1, (
        "endereço dentro de um SVG COMMITADO passou verde: `.svg` voltou ao "
        f"EXCLUIR_SUFIXO.\nsaída:\n{r.stdout}"
    )
    assert "diagrama.svg" in r.stdout, r.stdout
