"""ENSAIO-QUE-NÃO-DIZ-O-DEGRAU-01: o portão aceitava prova de IDA como prova de VOLTA."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_paridade_transporte.py"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
CADERNO = RAIZ / "docs" / "data" / "ensaios.csv"

LINHA_DE_SAIDA = ("luz.lightbar.cor", "dualsense")


def _rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(raiz / "scripts" / "check_paridade_transporte.py")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Cópia mínima e DESCARTÁVEL — o portão nunca roda contra a árvore real."""
    for rel in ("scripts", "docs/data"):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    for nome in ("check_paridade_transporte.py", "eliminacao.py"):
        origem = RAIZ / "scripts" / nome
        if origem.is_file():
            (tmp_path / "scripts" / nome).write_bytes(origem.read_bytes())
    for origem in (MAPA, CADERNO):
        (tmp_path / "docs" / "data" / origem.name).write_bytes(origem.read_bytes())
    return tmp_path


def _promover(mapa: Path, chave: tuple[str, str], grau: str) -> None:
    with mapa.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.reader(fh))
    ic = {c: i for i, c in enumerate(linhas[0])}
    achou = False
    for r in linhas[1:]:
        if r and (r[0], r[1]) == chave:
            r[ic["cabo_ate_onde_foi"]] = grau
            r[ic["radio_ate_onde_foi"]] = grau
            achou = True
    assert achou, f"a linha {chave} sumiu do mapa — o teste ficou cego"
    with mapa.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(linhas)


def test_o_portao_reprova_grau_de_entrada_sustentado_por_ensaio_de_saida(
    arvore: Path,
) -> None:
    """A mordida: a mentira exata que passou em 20/08 antes da cura."""
    _promover(arvore / "docs/data/mapa-controles.csv", LINHA_DE_SAIDA, "O JOGO REAGIU")

    saida = _rodar(arvore)

    assert saida.returncode != 0, (
        "o portão aceitou `O JOGO REAGIU` numa linha cujos ensaios mediram "
        "SAÍDA (acender lightbar). Prova de ida sustentando afirmação de "
        "volta é o buraco irmão do de 12/08.\n" + saida.stdout[-1500:]
    )
    assert "ensaio-nao-diz-o-degrau" in saida.stdout, (
        "reprovou, mas por outra regra — a mensagem tem de dizer que o ensaio "
        f"não declara o degrau:\n{saida.stdout[-1500:]}"
    )


def test_o_portao_continua_verde_na_arvore_de_verdade(arvore: Path) -> None:
    """Contraprova: a regra nova não machuca uma afirmação verdadeira."""
    saida = _rodar(arvore)
    assert saida.returncode == 0, (
        "o portão reprovou a árvore INTACTA depois da regra nova:\n"
        + saida.stdout[-1500:]
    )


def test_o_caderno_tem_a_coluna_que_a_regra_le(arvore: Path) -> None:
    """Portão que lê coluna inexistente passa sempre — e passa calado."""
    with (arvore / "docs/data/ensaios.csv").open(encoding="utf-8", newline="") as fh:
        cab = next(csv.reader(fh))
    assert "degrau" in cab, (
        "a coluna `degrau` sumiu do caderno. Sem ela a regra "
        "`ensaio-nao-diz-o-degrau` não tem o que ler, e um portão que não vê "
        "nada passa sempre — que é o defeito mais caro desta casa."
    )
    assert cab.index("degrau") == cab.index("transporte") + 1, (
        "`degrau` saiu de perto de `transporte`. Os dois são o mesmo tipo de "
        "eixo (o que a medição estava medindo) e ficam juntos por isso."
    )
