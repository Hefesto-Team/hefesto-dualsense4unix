"""A forma curta ``:N`` de uma célula de CSV anda com a inteira, e a troca é pelo lugar dela.

Fonte: o conferente da `ferramentas-1-8` (08/10/2026). A curta de CSV (``…hid-playstation.c:132,
:986, :1858-1861``) nunca foi lida; e a troca da curta era por LINHA, então um ``:5`` igual,
ancorado a outro arquivo, na mesma linha, ia junto. Os esperados abaixo são escritos à mão, a partir
do fixture: o validador não serve de prova aqui, porque ele não lê a curta de CSV.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.unit.test_as_citacoes_andam_com_o_codigo import (
    ALVO,
    _escrever_e_commitar,
    _git,
    _inserir_no_topo,
    _script,
)

RAIZ = Path(__file__).resolve().parents[2]
END = "src/hefesto_dualsense4unix/alvo.py"
FORA = "src/hefesto_dualsense4unix/outro.py"

OUTRO = '"""O outro alvo."""\n\nVALOR_B = 1\nPAR_DOS_VALORES = (1, 2)\n'

CABECALHO = "id,prosa\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    """Dois alvos e uma planilha vazia; o código anda depois que o texto nasce."""
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (pacote / "outro.py").write_text(OUTRO, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "os alvos nascem")
    yield raiz


def _planilha(raiz: Path, corpo: str) -> Path:
    return _escrever_e_commitar(raiz, "docs/data/mapa.csv", CABECALHO + corpo, "a planilha nasce")


def _rodar(raiz: Path, *, escrever: bool = True) -> tuple[list[str], list[str]]:
    return _script().reapontar(raiz, escrever=escrever)  # type: ignore[no-any-return,no-untyped-call]


def test_a_inteira_e_as_curtas_da_celula_andam_juntas(repo: Path) -> None:
    """O corpo anda 12 linhas: a inteira e as três curtas (sem crase, com crase e depois do `e`)."""
    planilha = _planilha(repo, f'a.um,"o corpo em {END}:11-12, :3, `:15-16` e :10"\n')
    _inserir_no_topo(repo, 12, commitar=True)

    modulo = _script()  # type: ignore[no-untyped-call]
    feitos, a_mao = modulo.reapontar(repo, escrever=True)

    assert a_mao == [], a_mao
    assert planilha.read_text(encoding="utf-8") == (
        CABECALHO + f'a.um,"o corpo em {END}:23-24, :15, `:27-28` e :22"\n'
    )
    assert modulo.ESTATISTICA["curtas_de_csv"] == 3, modulo.ESTATISTICA
    assert any(f"{END}:23-24" in f for f in feitos), feitos


def test_a_celula_entre_aspas_com_virgula_aspa_dobrada_e_quebra_cai_no_lugar_certo(
    repo: Path,
) -> None:
    """O ``csv.reader`` não diz o deslocamento: aspas dobradas, vírgula e quebra antes da curta."""
    planilha = _planilha(
        repo,
        'q.um,"disse ""oi"", viu, e leu\n'
        f'{END}:11-12 depois ""x"", e :3 ao fim"\n'
        f"q.dois,sem aspas {END}:10 e :15\n",
    )
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert planilha.read_text(encoding="utf-8") == (
        CABECALHO
        + 'q.um,"disse ""oi"", viu, e leu\n'
        + f'{END}:23-24 depois ""x"", e :15 ao fim"\n'
        + f"q.dois,sem aspas {END}:22 e :27\n"
    )


def test_a_curta_cuja_ancora_nao_resolve_fica_como_esta(repo: Path) -> None:
    """Arquivo de fora não é nosso, e a curta não cai numa âncora mais antiga que resolva."""
    corpo = (
        'f.um,"ver lib/audio.cpp:30-33, :3 e alvo-de-fora.c:7 e :10"\n'
        f'f.dois,"{END}:11-12 e depois lib/audio.cpp:30, :3"\n'
    )
    planilha = _planilha(repo, corpo)
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert planilha.read_text(encoding="utf-8") == CABECALHO + corpo.replace(
        f"{END}:11-12", f"{END}:23-24"
    )


def test_o_dois_pontos_de_outra_ancora_na_mesma_linha_de_md_nao_vai_junto(repo: Path) -> None:
    """``a.py:10 e :5; b.py:20 e :5``: a troca é pelo lugar, não pela linha."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/duas.md",
        f"# Duas\n\nO alvo, `{END}:11-12` e `:3`; o outro, `{FORA}:3` e `:3`.\n",
        "duas âncoras na mesma linha",
    )
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert md.read_text(encoding="utf-8") == (
        f"# Duas\n\nO alvo, `{END}:23-24` e `:15`; o outro, `{FORA}:3` e `:3`.\n"
    )


def test_a_ancora_nao_cruza_a_virgula_do_csv(repo: Path) -> None:
    """Duas células na mesma linha: o ``:3`` da segunda não tem inteira na célula dela."""
    planilha = _planilha(repo, f"x.um,{END}:11-12,:3\n")
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert planilha.read_text(encoding="utf-8") == CABECALHO + f"x.um,{END}:23-24,:3\n"


def test_o_mesmo_endereco_inteiro_e_curto_na_celula_anda_nas_duas_formas(repo: Path) -> None:
    """A guarda de ``escritas``/``atuais`` conta a curta dos dois lados: nada vai à mão por isso."""
    planilha = _planilha(repo, f'g.um,"o valor em {END}:3 e :3"\n')
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert planilha.read_text(encoding="utf-8") == (
        CABECALHO + f'g.um,"o valor em {END}:15 e :15"\n'
    )


def test_a_curta_de_csv_que_o_codigo_nao_moveu_fica_e_nao_e_listada(repo: Path) -> None:
    corpo = f'k.um,"o outro em {FORA}:3, :4"\n'
    planilha = _planilha(repo, corpo)
    _inserir_no_topo(repo, 12, commitar=True)

    feitos, a_mao = _rodar(repo)

    assert planilha.read_text(encoding="utf-8") == CABECALHO + corpo
    assert not any("mapa.csv" in f for f in (*feitos, *a_mao)), (feitos, a_mao)


def test_sem_escrever_a_curta_de_csv_aparece_no_plano_e_nada_muda(repo: Path) -> None:
    planilha = _planilha(repo, f'p.um,"{END}:11-12, :3"\n')
    _inserir_no_topo(repo, 12, commitar=True)
    antes = planilha.read_bytes()

    feitos, _a_mao = _rodar(repo, escrever=False)

    assert any(f"{END}:3` -> `{END}:15`" in f for f in feitos), feitos
    assert planilha.read_bytes() == antes


def test_a_linha_final_diz_quantas_curtas_de_csv_foram_lidas(repo: Path) -> None:
    import subprocess
    import sys

    _planilha(repo, f'r.um,"{END}:11-12, :3, :10"\n')
    _inserir_no_topo(repo, 12, commitar=True)

    feito = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "reapontar-citacoes.py"), "--root", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "2 forma(s) curta(s) lida(s) em CSV" in feito.stdout, feito.stdout


def test_o_help_diz_onde_a_curta_vale() -> None:
    import subprocess
    import sys

    feito = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "reapontar-citacoes.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    ajuda = " ".join(feito.stdout.split())
    assert "A forma curta" in ajuda and ".csv" in ajuda and "MAIS PRÓXIMA" in ajuda, ajuda


TEXTOS_DE_CSV = [
    "a,b,c\n",
    'a,"b,c",d\n',
    'a,"dis ""oi"" e\nquebra",d\n',
    "a,b,\n",
    "a,b,",
    "\n\na,b\n\n",
    'a,"",c\n',
    'a,"x"y,"z"\n',
    "a,b\r\nc,d\r\n",
    'a,"b\r\nc",d\r\n',
    'sem,aspas "no meio",ok\n',
    'abre,"nunca fecha\n',
]


@pytest.mark.parametrize("texto", TEXTOS_DE_CSV)
def test_o_recorte_le_as_celulas_como_o_csv_reader(texto: str) -> None:
    modulo = _script()  # type: ignore[no-untyped-call]
    esperado = list(csv.reader(io.StringIO(texto, newline="")))

    lido = [[c for c, _inicio, _mapa in registro] for registro in modulo._registros_do_csv(texto)]

    assert lido == esperado, (lido, esperado)


@pytest.mark.parametrize("texto", TEXTOS_DE_CSV)
def test_o_recorte_diz_onde_cada_letra_esta_no_texto_cru(texto: str) -> None:
    for registro in _script()._registros_do_csv(texto):  # type: ignore[no-untyped-call]
        for celula, inicio, mapa in registro:
            for k, letra in enumerate(celula):
                onde = inicio + k if mapa is None else mapa[k]
                assert texto[onde] == letra, (texto, celula, k, onde)


def test_o_recorte_le_as_planilhas_de_verdade_como_o_csv_reader() -> None:
    modulo = _script()  # type: ignore[no-untyped-call]
    for planilha in sorted((RAIZ / "docs" / "data").glob("*.csv")):
        texto = planilha.read_text(encoding="utf-8")
        esperado = list(csv.reader(io.StringIO(texto, newline="")))
        lido = [[(c, i, m) for c, i, m in registro] for registro in modulo._registros_do_csv(texto)]
        assert [[c for c, _i, _m in r] for r in lido] == esperado, planilha.name
        for registro in lido:
            for celula, inicio, mapa in registro:
                if ":" not in celula:
                    continue
                for k, letra in enumerate(celula):
                    onde = inicio + k if mapa is None else mapa[k]
                    assert texto[onde] == letra, (planilha.name, celula[:40], k)


def test_toda_curta_achada_na_arvore_de_verdade_tem_o_trecho_no_lugar_certo() -> None:
    """O trecho guardado é o ``:N`` no texto cru do documento, e há um por escrita."""
    modulo = _script()  # type: ignore[no-untyped-call]
    curtas = [c for c in modulo.cruas(RAIZ) if c.curta]
    assert any(c.documento.suffix == ".csv" for c in curtas), "a premissa: há curta de CSV"
    for cit in curtas:
        texto = cit.documento.read_text(encoding="utf-8")
        esperado = cit.texto[len(cit.arquivo) :]
        assert len(cit.trechos) == cit.vezes, (cit.documento.name, cit.texto)
        for inicio, fim in cit.trechos:
            assert texto[inicio:fim] == esperado, (cit.documento.name, cit.texto, inicio)
