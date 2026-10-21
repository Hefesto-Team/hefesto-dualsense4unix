"""Nenhuma pasta versionada é só casca: pacote vazio, `.gitkeep` e README de uma linha saem.

O git não guarda pasta vazia; guarda a casca que sobra dela: um `__init__.py` de 0 bytes, um
`.gitkeep` ou um README de uma linha sozinhos numa pasta sem mais nada. Foi assim que
`tui/screens/` ficou, sem que ninguém o importasse (a janela antiga saiu e o pacote ficou). A
régua mede os arquivos VERSIONADOS (`git ls-files`) e reprova a pasta cujo único conteúdo é
casca. Pasta com subpasta que tem arquivo não é casca (um pacote-pai com `__init__.py` vazio e
subpacotes é legítimo). Exceção, se houver, entra em `EXCECOES` com o motivo.
"""
from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[2]

# pasta (relativa à raiz) -> motivo de a casca ser necessária. Vazia de propósito: nenhuma hoje.
EXCECOES: dict[str, str] = {}


def _versionados(raiz: Path = RAIZ) -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=raiz, check=True, capture_output=True
    ).stdout
    return [c for c in saida.decode().split("\0") if c]


def _e_casca(raiz: Path, caminho: str) -> bool:
    """`__init__.py` de 0 bytes, `.gitkeep` ou README de uma linha: não dizem nada sozinhos."""
    nome = PurePosixPath(caminho).name
    if nome == ".gitkeep":
        return True
    arquivo = raiz / caminho
    if nome == "__init__.py":
        return arquivo.is_file() and arquivo.stat().st_size == 0
    if nome.lower().startswith("readme"):
        if not arquivo.is_file():
            return False
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        return len([x for x in texto.splitlines() if x.strip()]) <= 1
    return False


def pastas_so_casca(arquivos: list[str], raiz: Path = RAIZ) -> list[str]:
    """As pastas cujo único conteúdo versionado é casca e que não têm subpasta com arquivo."""
    por_pasta: dict[str, list[str]] = {}
    for caminho in arquivos:
        por_pasta.setdefault(str(PurePosixPath(caminho).parent), []).append(caminho)
    pais = {str(p) for pasta in por_pasta for p in PurePosixPath(pasta).parents}
    achadas = []
    for pasta, itens in sorted(por_pasta.items()):
        if pasta == "." or pasta in pais or pasta in EXCECOES:
            continue
        if all(_e_casca(raiz, c) for c in itens):
            achadas.append(pasta)
    return achadas


def test_nenhuma_pasta_versionada_e_so_casca() -> None:
    achadas = pastas_so_casca(_versionados())
    assert not achadas, (
        "pasta versionada cujo único conteúdo é casca (`__init__.py` vazio, `.gitkeep` ou "
        "README de uma linha); tire a pasta do git, ou declare a exceção com o motivo em "
        "EXCECOES: " + ", ".join(achadas)
    )


def test_a_regua_pega_cada_forma_de_casca(tmp_path: Path) -> None:
    (tmp_path / "pacote").mkdir()
    (tmp_path / "pacote" / "__init__.py").write_bytes(b"")
    (tmp_path / "guarda").mkdir()
    (tmp_path / "guarda" / ".gitkeep").write_bytes(b"")
    (tmp_path / "nota").mkdir()
    (tmp_path / "nota" / "README.md").write_text("# nota\n", encoding="utf-8")
    versionados = ["pacote/__init__.py", "guarda/.gitkeep", "nota/README.md"]
    assert pastas_so_casca(versionados, tmp_path) == ["guarda", "nota", "pacote"]


def test_a_regua_deixa_passar_o_que_tem_conteudo(tmp_path: Path) -> None:
    (tmp_path / "pai" / "filho").mkdir(parents=True)
    (tmp_path / "pai" / "__init__.py").write_bytes(b"")
    (tmp_path / "pai" / "filho" / "__init__.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "README.md").write_text("# a\n\nb\n", encoding="utf-8")
    (tmp_path / "util").mkdir()
    (tmp_path / "util" / "__init__.py").write_bytes(b"")
    (tmp_path / "util" / "mod.py").write_text("Y = 2\n", encoding="utf-8")
    versionados = [
        "pai/__init__.py",
        "pai/filho/__init__.py",
        "doc/README.md",
        "util/__init__.py",
        "util/mod.py",
    ]
    assert pastas_so_casca(versionados, tmp_path) == []
