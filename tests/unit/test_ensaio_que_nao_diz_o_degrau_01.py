"""ENSAIO-QUE-NÃO-DIZ-O-DEGRAU-01: o portão aceitava prova de IDA como prova de VOLTA.

**O buraco irmão do de 12/08.** Naquele dia um agente escreveu a afirmação mais
forte do vocabulário desta casa numa linha com ZERO ensaios, e o portão devolveu
o mesmo número de reprovações de antes. As regras 6, 9 e 13 nasceram disso.

Só que a lição foi aprendida para *"nenhum ensaio"* e não para *"o ensaio
errado"*. O casamento ensaio↔célula é `(linha_id, transporte)` e nada mais —
então uma linha que TEM ensaios podia ser promovida a QUALQUER degrau, inclusive
aos dois de ENTRADA, sustentada por medições de outra coisa inteira.

**Reproduzido à mão em 20/08/2026, em cópia descartável:** escrevendo
`ate_onde_foi = O JOGO REAGIU` nos dois lados de `luz.lightbar.cor@dualsense` —
cujos ensaios falam todos de `0x08 VALID_FLAG1_RELEASE_LEDS`, que é saída pura,
acender luz — o portão devolveu `exit 0`. O grau que afirma que um JOGO REAGIU
passou sustentado por medições de acender lightbar.

Isso importa porque a direção de entrada tem HOJE zero células. A primeira
pessoa a preenchê-las — inclusive um agente — encheria com o que já estava no
caderno, e nada pegaria.

**Por que a regra vale só para os degraus de ENTRADA:** os de saída continuam
sustentados pelo caderno como sempre estiveram. Reprovar afirmação verdadeira é
o erro que esta casa já pagou em 12/08 e 13/08, e as 21 células de
`O APARELHO OBEDECEU` são verdadeiras. A direção que ainda não tem uma célula é
onde exigir declaração explícita não machuca ninguém — e é o momento certo.

**Como estes testes MORDEM:** apague o bloco `if grau in GRAUS_DE_ENTRADA` do
`check_paridade_transporte.py` e o primeiro reprova, porque a mentira volta a
passar.
"""

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

#: A linha do estudo da lightbar: SAÍDA pura, com ensaios de sobra no caderno.
#: É o pior caso justamente por ter ensaios — a regra 6 não a pega.
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
    """Contraprova: a regra nova não machuca uma afirmação verdadeira.

    As 21 células de `O APARELHO OBEDECEU` são de saída e continuam sustentadas
    pelos 177 ensaios legados, que nascem com `degrau` VAZIO. Se este teste
    reprovar, a regra ficou larga demais e está cobrando declaração de quem não
    devia — o erro de 12/08 e 13/08 ao contrário.
    """
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
