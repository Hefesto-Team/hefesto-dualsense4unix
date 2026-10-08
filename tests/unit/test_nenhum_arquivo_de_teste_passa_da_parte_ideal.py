"""Nenhum arquivo de teste passa da parte ideal (A-JANELA-ABERTA-CABE-NA-PARTE-01).

Uma parte da suíte nunca fica abaixo do maior arquivo que cai nela: o arquivo único da janela
aberta levava 217 s sozinho contra ~133 s de parte ideal (a soma de
`docs/data/tempos-da-suite.csv` dividida por 24), e a parte 00 ficava com ele só. A régua lê as
linhas `medido` do CSV e reprova o arquivo que EXISTE em `tests/unit/` acima de soma/24. A linha
de um arquivo que não existe mais não conta: o CSV só se reescreve no passo `tempos` do fecho,
depois da costura.

E quem parte um arquivo em vários precisa que os novos continuem em processo próprio: o
ajudante de `tests/unit/` (sem prefixo `test_`) que pede o `_gtk` diz `WebKit2`, o arquivo de
teste não, e o `scripts/rodar-a-suite.sh` tem de seguir a cadeia de import também por
`tests/unit/`. A régua pergunta isso ao próprio script (`LISTAR_O_WEBKIT=1`), na árvore de
verdade e numa árvore de mentira.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"
CSV_DOS_TEMPOS = RAIZ / "docs" / "data" / "tempos-da-suite.csv"
UNIT = RAIZ / "tests" / "unit"

Linha = tuple[str, int, str]


def _linhas_do_csv(texto: str) -> list[Linha]:
    """`(arquivo, milissegundos, fonte)` de cada linha de dado do CSV."""
    linhas: list[Linha] = []
    for cru in texto.splitlines():
        if not cru.strip() or cru.startswith("#") or cru.startswith("arquivo,"):
            continue
        arquivo, ms, fonte = [*cru.split(","), "", ""][:3]
        if ms.isdigit():
            linhas.append((arquivo, int(ms), fonte.strip()))
    return linhas


def _partes_do_script() -> int:
    """As partes que o script parte a suíte, lidas dele (`PARTES="${PARTES:-24}"`)."""
    achou = re.search(r'^PARTES="\$\{PARTES:-(\d+)\}"', SUITE.read_text(encoding="utf-8"), re.M)
    assert achou, "o scripts/rodar-a-suite.sh deixou de ter o PARTES com padrão"
    return int(achou.group(1))


def _parte_ideal_ms(linhas: list[Linha], partes: int) -> float:
    """A soma de TODAS as linhas (`medido` e `estimado`) dividida pelas partes."""
    return sum(ms for _, ms, _ in linhas) / partes


def acima_da_parte_ideal(
    linhas: list[Linha], partes: int, existe: Callable[[str], bool]
) -> list[tuple[str, int, int]]:
    """Os arquivos `medido` que existem e passam da parte ideal: `(arquivo, ms, ideal_ms)`."""
    ideal = _parte_ideal_ms(linhas, partes)
    return sorted(
        (arquivo, ms, round(ideal))
        for arquivo, ms, fonte in linhas
        if fonte == "medido" and ms > ideal and existe(arquivo)
    )


def test_nenhum_arquivo_de_teste_passa_da_parte_ideal() -> None:
    """A árvore de verdade: nenhum arquivo de `tests/unit/` mede mais que soma/partes."""
    linhas = _linhas_do_csv(CSV_DOS_TEMPOS.read_text(encoding="utf-8"))
    assert len(linhas) >= 500, f"o CSV traz só {len(linhas)} linha(s): a régua ficou cega"
    partes = _partes_do_script()
    passam = acima_da_parte_ideal(linhas, partes, lambda a: (RAIZ / a).is_file())
    ideal_s = _parte_ideal_ms(linhas, partes) / 1000
    assert not passam, (
        f"arquivo(s) de teste acima da parte ideal (soma/{partes} = {ideal_s:.0f} s); parta o "
        "arquivo por grupo de fixtures, com o ajudante num módulo sem prefixo `test_`:\n  "
        + "\n  ".join(f"{a}: {ms / 1000:.1f} s" for a, ms, _ in passam)
    )


def test_a_regua_pega_o_arquivo_que_existe_e_ignora_o_que_saiu() -> None:
    """Com tempos sintéticos: reprova o gigante que existe, e só ele."""
    linhas: list[Linha] = [("tests/unit/test_gigante.py", 217_000, "medido")]
    linhas += [(f"tests/unit/test_pequeno_{i}.py", 10_000, "medido") for i in range(20)]
    linhas += [("tests/unit/test_estimado_grande.py", 150_000, "estimado")]
    ideal = (217_000 + 20 * 10_000 + 150_000) / 4
    assert _parte_ideal_ms(linhas, 4) == ideal
    assert acima_da_parte_ideal(linhas, 4, lambda _a: True) == [
        ("tests/unit/test_gigante.py", 217_000, round(ideal))
    ]
    assert acima_da_parte_ideal(linhas, 4, lambda a: "gigante" not in a) == [], (
        "a linha de um arquivo que não existe mais contou"
    )


def _importados(arquivo: Path) -> set[str]:
    """Os nomes de módulo (cada ponto do caminho) que o arquivo importa."""
    nomes: set[str] = set()
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            for a in no.names:
                nomes |= set(a.name.split("."))
        elif isinstance(no, ast.ImportFrom):
            nomes |= set((no.module or "").split("."))
            nomes |= {a.name for a in no.names}
    return nomes


def _ajudantes_do_webkit() -> set[str]:
    """Os ajudantes de `tests/unit/` (sem `test_`) que dizem `WebKit2` ou importam um que diz."""
    ajudantes = {
        p.stem: p
        for p in UNIT.glob("*.py")
        if not p.name.startswith("test_") and p.name not in ("__init__.py", "conftest.py")
    }
    webkit = {nome for nome, p in ajudantes.items() if "WebKit2" in p.read_text(encoding="utf-8")}
    while novos := {n for n, p in ajudantes.items() if n not in webkit and _importados(p) & webkit}:
        webkit |= novos
    return webkit


def _ambiente() -> dict[str, str]:
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD", "PARTES", "SAIDA", "PARTIDO"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", "PY": sys.executable, "LISTAR_O_WEBKIT": "1"})
    return env


def test_o_arquivo_que_pede_o_webkit_a_um_ajudante_roda_em_processo_proprio(tmp_path: Path) -> None:
    """A árvore de verdade: todo teste que importa um ajudante do WebKit está na lista do script."""
    feito = subprocess.run(
        ["bash", str(SUITE)], cwd=RAIZ, capture_output=True, text=True, timeout=300,
        check=False, env={**_ambiente(), "SAIDA": str(tmp_path / "saida")},
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    sozinhos = set(feito.stdout.split())
    webkit = _ajudantes_do_webkit()
    assert "janela_aberta_comum" in webkit, "o ajudante da janela aberta deixou de pedir o WebKit"
    esperados = {
        p.relative_to(RAIZ).as_posix()
        for p in UNIT.glob("test_*.py")
        if _importados(p) & webkit
    }
    assert len(esperados) >= 5, f"só {len(esperados)} arquivo(s) importam um ajudante do WebKit"
    faltam = sorted(esperados - sozinhos)
    assert not faltam, (
        "importam um ajudante que carrega o WebKit e rodariam no processo da parte:\n  "
        + "\n  ".join(faltam)
    )


def test_o_script_segue_o_ajudante_de_tests_unit_numa_arvore_de_mentira(tmp_path: Path) -> None:
    """Um ajudante com `WebKit2`, um que o importa, e os testes que importam cada um."""
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(SUITE, raiz / "scripts" / "rodar-a-suite.sh")
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "__init__.py").write_text("")
    (unit / "ajudante_base.py").write_text(
        'def gtk():\n    import gi\n    gi.require_version("WebKit2", "4.1")\n'
    )
    (unit / "ajudante_filho.py").write_text("from tests.unit.ajudante_base import gtk\n")
    (unit / "ajudante_comum.py").write_text("def nada():\n    return 1\n")
    (unit / "test_pelo_filho.py").write_text("from tests.unit.ajudante_filho import gtk\n")
    (unit / "test_direto.py").write_text("from tests.unit import ajudante_base\n")
    (unit / "test_do_comum.py").write_text("from tests.unit.ajudante_comum import nada\n")
    feito = subprocess.run(
        ["bash", str(raiz / "scripts" / "rodar-a-suite.sh")], cwd=raiz, capture_output=True,
        text=True, timeout=120, check=False,
        env={**_ambiente(), "SAIDA": str(tmp_path / "saida")},
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert sorted(feito.stdout.split()) == [
        "tests/unit/test_direto.py",
        "tests/unit/test_pelo_filho.py",
    ], feito.stdout
