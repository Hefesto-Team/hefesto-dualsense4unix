"""O diff do CSV se lê por célula, a linha de troca diz «curta», e o validador lê a curta de CSV.

Fonte: a costura da citacoes-1-9 (08/10/2026). O ``_pares_do_diff`` lia a linha FÍSICA do diff, e a
curta ``:N`` de uma célula sem inteira se prendia à inteira de OUTRA célula (148 curtas a mais em
`docs/data` pela linha física que pela célula); a curta de célula com quebra de linha perdia a
âncora; a linha de troca não separava a curta da inteira; e o `validar-citacoes-de-linha.py` não
lia a curta de CSV. Os esperados são escritos à mão, a partir do fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_as_citacoes_andam_com_o_codigo import (
    ALVO,
    _escrever_e_commitar,
    _git,
    _inserir_no_topo,
    _script,
    _validar,
)

END = "src/hefesto_dualsense4unix/alvo.py"
PLANILHA = "docs/data/mapa.csv"
CABECALHO = "id,ref,nota,outra\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    yield raiz


def _pares(raiz: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    """O par do diff do último commit da planilha, pelo script de verdade."""
    mod: ModuleType = _script()  # type: ignore[no-untyped-call]
    val = mod._validador(raiz)
    sha = _git(raiz, "rev-parse", "HEAD").strip()
    pares: tuple[dict[str, set[str]], dict[str, str]] = mod._pares_do_diff(
        raiz, val, "csv", mod._resolvedor(raiz, val), sha, PLANILHA
    )
    return pares


def test_a_curta_de_uma_celula_sem_inteira_nao_se_prende_a_outra_celula(repo: Path) -> None:
    """``x,src/a.py:10,y,`:5``` : a ``:5`` está numa célula sem inteira, e não é do ``alvo.py``."""
    _escrever_e_commitar(repo, PLANILHA, f"{CABECALHO}r1,{END}:10,y,`:5`\n", "nasce")
    _escrever_e_commitar(repo, PLANILHA, f"{CABECALHO}r1,{END}:22,y,`:7`\n", "anda")

    trocados, sem_par = _pares(repo)

    assert trocados == {f"{END}:22": {f"{END}:10"}}, trocados
    assert f"{END}:7" not in sem_par, sem_par


def test_a_curta_da_celula_com_quebra_de_linha_guarda_a_ancora(repo: Path) -> None:
    """A célula entre aspas ocupa duas linhas físicas: a curta da segunda é da inteira da 1ª."""
    antes = f'{CABECALHO}r1,"o corpo em {END}:10\ne o fim, :12",y,z\n'
    depois = f'{CABECALHO}r1,"o corpo em {END}:22\ne o fim, :24",y,z\n'
    _escrever_e_commitar(repo, PLANILHA, antes, "nasce")
    _escrever_e_commitar(repo, PLANILHA, depois, "anda")

    trocados, sem_par = _pares(repo)

    assert trocados == {f"{END}:22": {f"{END}:10"}, f"{END}:24": {f"{END}:12"}}, (
        trocados,
        sem_par,
    )


def test_so_a_segunda_linha_da_celula_muda_e_o_par_e_da_celula(repo: Path) -> None:
    """O hunk toca só a linha física de baixo: o par ainda é o da célula inteira."""
    antes = f'{CABECALHO}r1,"o corpo em {END}:10\ne o fim, :12",y,z\n'
    depois = f'{CABECALHO}r1,"o corpo em {END}:10\ne o fim, :16",y,z\n'
    _escrever_e_commitar(repo, PLANILHA, antes, "nasce")
    _escrever_e_commitar(repo, PLANILHA, depois, "uma curta muda")

    trocados, _sem_par = _pares(repo)

    assert trocados == {f"{END}:16": {f"{END}:12"}}, trocados


def test_a_celula_que_ganha_endereco_fica_sem_par_com_o_motivo(repo: Path) -> None:
    _escrever_e_commitar(repo, PLANILHA, f"{CABECALHO}r1,{END}:10,y,z\n", "nasce")
    _escrever_e_commitar(repo, PLANILHA, f"{CABECALHO}r1,{END}:22,y,{END}:3\n", "ganha")

    trocados, sem_par = _pares(repo)

    assert trocados == {f"{END}:22": {f"{END}:10"}}, trocados
    assert "célula tinha 0 endereço(s) e passou a ter 1" in sem_par[f"{END}:3"], sem_par


def test_a_linha_de_troca_diz_que_a_curta_e_curta_e_a_que_inteira_se_prende(repo: Path) -> None:
    _escrever_e_commitar(repo, PLANILHA, f"{CABECALHO}r1,{END}:3 e :10,y,z\n", "nasce")
    _inserir_no_topo(repo, 12, commitar=True)

    feitos, _a_mao = _script().reapontar(repo, escrever=False)  # type: ignore[no-untyped-call]

    curta = [f for f in feitos if f"`{END}:10` -> `{END}:22`" in f]
    inteira = [f for f in feitos if f"`{END}:3` -> `{END}:15`" in f]
    assert len(curta) == 1 and curta[0].endswith(f"(curta, presa a `{END}`)"), feitos
    assert len(inteira) == 1 and "(curta" not in inteira[0], feitos


def test_o_validador_le_a_curta_de_csv_presa_a_inteira_da_celula(repo: Path) -> None:
    """A curta que aponta para a linha sem o símbolo prometido reprova; a certa e a solta, não."""
    corpo = (
        f"r1,{END}:3 (`VALOR`) e :6 (`segunda`),`:6` (`segunda`),z\n"
        f"r2,{END}:3 (`VALOR`) e :10 (`segunda`),y,z\n"
        f"r3,{END}:3; :99,y,z\n"
    )
    _escrever_e_commitar(repo, PLANILHA, CABECALHO + corpo, "nasce")

    feito = _validar(repo)

    queixas = [linha for linha in feito.stdout.splitlines() if " -- " in linha]
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert len(queixas) == 2, queixas
    assert any(
        f"`{END}:6` (forma curta na célula) -- a faixa não contém `segunda`" in q for q in queixas
    ), queixas
    assert any(f"`{END}:99` (forma curta na célula) -- a linha não existe" in q for q in queixas)
