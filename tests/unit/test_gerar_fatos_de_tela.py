"""O gerador de fatos de tela (Z6-02) morde nos dois sentidos.

Executa a mordida de
docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01-a-medicao-chega-a-tela-por-alguem-lembrar.md
(Z6-02): "(1) Editar uma célula do CSV sem regerar → `--check` reprova com
diff. (2) Pôr coluna de texto livre na *allowlist* → o teste da fronteira
reprova."

Os dois testes de mordida rodam contra uma árvore de brinquedo (cabeçalho real
recortado, poucas linhas) — a árvore de verdade tem 308 linhas e um teste que
dependesse dela mediria a hora da última regeração, não o portão.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "scripts" / "gerar-fatos-de-tela.py"

sys.path.insert(0, str(RAIZ / "scripts"))


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "data").mkdir(parents=True)
    (tmp_path / "src" / "hefesto_dualsense4unix" / "app").mkdir(parents=True)

    for nome in ("check_paridade_transporte.py", "eliminacao.py", "gerar-fatos-de-tela.py"):
        (tmp_path / "scripts" / nome).write_bytes((RAIZ / "scripts" / nome).read_bytes())

    caminho_mapa_real = RAIZ / "docs" / "data" / "mapa-controles.csv"
    with caminho_mapa_real.open(encoding="utf-8") as arquivo_real:
        linhas_reais = list(csv.DictReader(arquivo_real))
    cabecalho = linhas_reais[0].keys()
    # três linhas reais de uma chave só (o bloco cabo/rádio de um controle) —
    # basta para exercitar o gerador sem carregar as 308 linhas do mapa real.
    recorte = linhas_reais[:1]
    with (tmp_path / "docs" / "data" / "mapa-controles.csv").open(
        "w", encoding="utf-8", newline=""
    ) as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(cabecalho))
        escritor.writeheader()
        escritor.writerows(recorte)
    # ensaios.csv vazio (só cabeçalho) — eliminacao.py o lê, mesmo que o
    # gerador de fatos não use o conteúdo.
    caminho_ensaios_real = RAIZ / "docs" / "data" / "ensaios.csv"
    ensaios_cabecalho: list[str] = []
    if caminho_ensaios_real.exists():
        with caminho_ensaios_real.open(encoding="utf-8") as arquivo_ensaios:
            primeira = next(csv.DictReader(arquivo_ensaios), None)
        ensaios_cabecalho = list(primeira.keys()) if primeira else []
    with (tmp_path / "docs" / "data" / "ensaios.csv").open(
        "w", encoding="utf-8", newline=""
    ) as arquivo:
        if ensaios_cabecalho:
            csv.DictWriter(arquivo, fieldnames=list(ensaios_cabecalho)).writeheader()
    return tmp_path


def _roda(arvore: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(arvore / "scripts" / "gerar-fatos-de-tela.py"), *args],
        cwd=arvore,
        capture_output=True,
        text=True,
    )


def test_check_passa_na_arvore_recem_gerada(arvore: Path) -> None:
    gera = _roda(arvore)
    assert gera.returncode == 0, gera.stderr
    checa = _roda(arvore, "--check")
    assert checa.returncode == 0, checa.stderr
    assert "atualizado" in checa.stdout


def test_editar_celula_sem_regerar_faz_o_check_reprovar(arvore: Path) -> None:
    """MORDIDA 1 de Z6-02: célula editada sem `python3 gerar-fatos-de-tela.py`."""
    gera = _roda(arvore)
    assert gera.returncode == 0, gera.stderr

    caminho_csv = arvore / "docs" / "data" / "mapa-controles.csv"
    linhas = list(csv.DictReader(caminho_csv.open(encoding="utf-8")))
    cabecalho = list(linhas[0].keys())
    linhas[0]["existe"] = "nao-tem" if linhas[0]["existe"] != "nao-tem" else "tem"
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=cabecalho)
        escritor.writeheader()
        escritor.writerows(linhas)

    checa = _roda(arvore, "--check")
    assert checa.returncode == 1
    assert "DESATUALIZADO" in checa.stderr
    assert "-" in checa.stderr and "+" in checa.stderr  # tem diff, não só o veredito


def test_fronteira_reprova_coluna_de_prosa_na_allowlist() -> None:
    """MORDIDA 2 de Z6-02: coluna NÃO DERIVA (prosa) entrando na allowlist.

    ARRANQUE desta mordida: comentar a chamada a `checar_fronteira` dentro de
    `monta_fatos` faz este teste passar mesmo com `rotulo` na allowlist — a
    prova de que o guarda é `checar_fronteira`, e não outra coisa.
    """
    # o nome do arquivo tem hífen; carrega por caminho em vez de `import`.
    import importlib.util

    spec = importlib.util.spec_from_file_location("gerar_fatos_de_tela_teste", GERADOR)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    with pytest.raises(ValueError, match="PROSA"):
        modulo.checar_fronteira(frozenset({"aciona", "rotulo"}))

    # a allowlist real do gerador nunca contém coluna de prosa:
    modulo.checar_fronteira(modulo.COLUNAS_DERIVAVEIS)
