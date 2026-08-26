"""Z6-07 — o `id` para de poder sumir em silêncio, e a ref que não resolve
reprova alto.

As duas mordidas do aceite: (1) renomear um `id` reprova; acrescentar a nota
(`id_v1`) e ver passar. (2) `git clone --depth 1` faz o portão reprovar
pedindo histórico, em vez de sair 0 — replicado aqui SEM clonar de verdade
(mais rápido): apontando `--contra` para uma ref que não existe no repo de
teste, que é o mesmo sintoma que um clone raso produz (`git show REF:...`
falha do mesmo jeito nos dois casos).
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

def _specs_de(raiz: Path) -> Path:
    """O caminho do `specs.html` numa árvore de brinquedo, com a pasta criada.

    A página mudou da raiz para `html/` em 25/08/2026, e as árvores de teste
    passaram a precisar da pasta ANTES do `write_text` — senão o erro é um
    `FileNotFoundError` de diretório, que não diz nada sobre o que se testa.

    Existe como função, e não como duas linhas repetidas em cada caso, pelo
    motivo de sempre nesta casa: no dia em que o caminho mudar de novo, muda
    num lugar só.
    """
    pasta = raiz / "html"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "specs.html"


RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"

CABECALHO = [
    "chave",
    "controle",
    "existe",
    "cabo_aciona",
    "radio_aciona",
    "cabo_de_onde_sei",
    "radio_de_onde_sei",
    "cabo_canal",
    "radio_canal",
    "cabo_ate_onde_foi",
    "radio_ate_onde_foi",
    "ponte_alcanca",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "id",
    "id_v1",
]

TESTE_FALSO = '''\
"""Arquivo de teste de mentira, só para o índice por AST ter o que ler."""


def test_a_lightbar_acende():
    assert True
'''


def _linha(**mudancas: str) -> dict[str, str]:
    base = {
        "chave": "luz.lightbar.cor",
        "controle": "dualsense",
        "existe": "tem",
        "cabo_aciona": "",
        "radio_aciona": "",
        "teste_que_morde": "",
        "id": "luz.lightbar.cor@dualsense",
        "id_v1": "",
    }
    base.update(mudancas)
    return base


def _escreve_csv(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in CABECALHO})


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "teste",
            "GIT_AUTHOR_EMAIL": "teste@example.com",
            "GIT_COMMITTER_NAME": "teste",
            "GIT_COMMITTER_EMAIL": "teste@example.com",
            "PATH": "/usr/bin:/bin",
            "HOME": str(cwd),
        },
    )


def monta_repo(tmp_path: Path) -> Path:
    _git("init", "-q", cwd=tmp_path)
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    _escreve_csv(caminho_csv, [_linha()])
    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_exemplo.py").write_text(TESTE_FALSO, encoding="utf-8")
    _specs_de(tmp_path).write_text(
        "<html><body>luz.lightbar.cor@dualsense</body></html>", encoding="utf-8"
    )
    _git("add", "-A", cwd=tmp_path)
    _git("commit", "-q", "-m", "primeiro commit", cwd=tmp_path)
    return tmp_path


def rodar(raiz: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--exigir-id-estavel", *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def test_sem_mudanca_de_id_passa_contra_head(tmp_path: Path) -> None:
    raiz = monta_repo(tmp_path)
    processo = rodar(raiz, "--contra", "HEAD")
    assert "id-sumiu-sem-nota" not in processo.stdout
    assert "contra-nao-resolve" not in processo.stdout


def test_id_renomeado_sem_nota_reprova(tmp_path: Path) -> None:
    """MORDIDA 1a."""
    raiz = monta_repo(tmp_path)
    caminho_csv = raiz / "docs" / "data" / "mapa-controles.csv"
    _escreve_csv(caminho_csv, [_linha(id="luz.lightbar.cor@dualsense_novo")])
    processo = rodar(raiz, "--contra", "HEAD")
    assert processo.returncode == 1
    assert "id-sumiu-sem-nota" in processo.stdout
    assert "luz.lightbar.cor@dualsense" in processo.stdout


def test_id_renomeado_com_id_v1_passa(tmp_path: Path) -> None:
    """MORDIDA 1b — acrescentar a nota e ver passar."""
    raiz = monta_repo(tmp_path)
    caminho_csv = raiz / "docs" / "data" / "mapa-controles.csv"
    _escreve_csv(
        caminho_csv,
        [_linha(id="luz.lightbar.cor@dualsense_novo", id_v1="luz.lightbar.cor@dualsense")],
    )
    # o specs.html também precisa publicar o novo id (regra 5) — não é o foco
    # deste teste, então republica aqui.
    _specs_de(raiz).write_text(
        "<html><body>luz.lightbar.cor@dualsense_novo</body></html>", encoding="utf-8"
    )
    processo = rodar(raiz, "--contra", "HEAD")
    assert "id-sumiu-sem-nota" not in processo.stdout


def test_ref_que_nao_resolve_reprova_alto_nunca_sai_calada(tmp_path: Path) -> None:
    """MORDIDA 2 — o sintoma de `git clone --depth 1`: a ref não existe."""
    raiz = monta_repo(tmp_path)
    processo = rodar(raiz, "--contra", "refs/nao-existe-de-jeito-nenhum")
    assert processo.returncode == 1
    assert "contra-nao-resolve" in processo.stdout
    assert "refs/nao-existe-de-jeito-nenhum" in processo.stdout
