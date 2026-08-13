"""A bancada só pode nomear coluna que o CSV realmente tem.

O DEFEITO QUE ESTE ARQUIVO GUARDA
---------------------------------
A migração v2 do mapa de canais desdobrou por transporte as colunas que antes
eram únicas: `grau` virou `cabo_grau`/`radio_grau`, `ressalva` virou
`cabo_ressalva`/`radio_ressalva`. A `bancada.py` continuou pedindo os nomes
velhos, e o `df[vis]` da linha da grade passou a levantar

    KeyError: "['grau', 'ressalva'] not in index"

na PRIMEIRA renderização — antes de qualquer clique. A grade, o caderno de
eliminação e o formulário de registro de ensaio nunca chegavam a aparecer.
Medido em 12/08/2026 rodando a bancada inteira sem navegador
(`streamlit.testing.v1.AppTest`), com a cura e sem ela.

POR QUE ELE EXISTE
------------------
A bancada é a porta oficial pela qual um fato medido no aparelho entra no
repositório, e ela ficou fora do ar sem que NENHUM portão notasse: ela não tem
teste, o `ruff` do CI (`ruff check src/ tests/`) não alcança a raiz, e nada na
árvore a importa. Uma renomeação de coluna quebrava a bancada em silêncio.

Este arquivo é a rede que faltou. Ele não roda Streamlit — Streamlit não é
dependência do produto, e o CI não o teria. Ele lê a `bancada.py` por AST,
colhe TODO nome de coluna que ela pronuncia, e cruza com o cabeçalho real dos
dois CSV. Por ler o código em vez de uma lista copiada, ele pega a PRÓXIMA
renomeação, não só esta.

MORDE? Troque `cabo_grau`/`radio_grau` de volta por `grau` em `EDITAVEIS`, ou
tire `cabo_ressalva` do CSV, ou renomeie qualquer coluna que a bancada leia por
atributo: os testes daqui reprovam nomeando a coluna que sumiu.
"""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "bancada.py"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
ENSAIOS = RAIZ / "docs" / "data" / "ensaios.csv"

#: Os nomes que, dentro da bancada, seguram um quadro do mapa de canais — ou
#: uma linha dele (`r`, do `itertuples`). Tudo que for lido como atributo de um
#: destes é nome de COLUNA, e tem de existir no cabeçalho.
#:
#: A lista é conferida pelo próprio teste (`test_os_nomes_de_quadro...`): se
#: alguém renomear `v` para outra coisa, o teste reprova em vez de emudecer —
#: régua que se desliga sozinha é pior que régua nenhuma.
NOMES_DE_QUADRO = ("df", "v", "base", "alvos", "editado", "r")

#: O que é API do pandas, e não coluna. Um método novo entra aqui no mesmo
#: gesto em que entra na bancada; o preço de esquecer é uma reprovação que diz
#: exatamente qual nome ficou sem explicação.
API_DO_PANDAS = frozenset({"copy", "to_csv", "loc", "index", "itertuples", "columns"})


def _arvore() -> ast.Module:
    return ast.parse(BANCADA.read_text(encoding="utf-8"), filename=str(BANCADA))


def _cabecalho(caminho: Path) -> list[str]:
    with open(caminho, encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _lista_literal(nome: str) -> list[str]:
    """A lista de strings atribuída a `nome`, com `*OUTRA_LISTA` já expandido."""
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Assign):
            continue
        if not any(isinstance(a, ast.Name) and a.id == nome for a in no.targets):
            continue
        if not isinstance(no.value, ast.List):
            break
        colunas: list[str] = []
        for item in no.value.elts:
            if isinstance(item, ast.Starred) and isinstance(item.value, ast.Name):
                colunas.extend(_lista_literal(item.value.id))
            elif isinstance(item, ast.Constant) and isinstance(item.value, str):
                colunas.append(item.value)
            else:
                pytest.fail(
                    f"`{nome}` em bancada.py deixou de ser uma lista de nomes "
                    "literais; este teste não consegue mais lê-la por AST"
                )
        return colunas
    pytest.fail(f"não achei a lista `{nome}` em {BANCADA.name}")


def _atributos_por_quadro() -> dict[str, set[str]]:
    """Para cada nome de quadro, os atributos lidos dele na bancada."""
    achados: dict[str, set[str]] = {nome: set() for nome in NOMES_DE_QUADRO}
    for no in ast.walk(_arvore()):
        if (
            isinstance(no, ast.Attribute)
            and isinstance(no.value, ast.Name)
            and no.value.id in achados
        ):
            achados[no.value.id].add(no.attr)
    return achados


def _colunas_por_atributo() -> set[str]:
    lidos: set[str] = set()
    for atributos in _atributos_por_quadro().values():
        lidos |= atributos
    return lidos - API_DO_PANDAS


def _chaves_do_column_config() -> list[str]:
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "data_editor"):
            continue
        for kw in no.keywords:
            if kw.arg == "column_config" and isinstance(kw.value, ast.Dict):
                return [
                    c.value
                    for c in kw.value.keys
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)
                ]
    pytest.fail("não achei o `column_config` do `st.data_editor` em bancada.py")


def _campos_do_ensaio() -> list[str]:
    """As chaves do dicionário que o formulário de ensaio grava, EM ORDEM."""
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Assign):
            continue
        if not any(isinstance(a, ast.Name) and a.id == "novo" for a in no.targets):
            continue
        if isinstance(no.value, ast.Dict):
            return [
                c.value
                for c in no.value.keys
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            ]
    pytest.fail("não achei o dicionário `novo` do formulário de ensaio em bancada.py")


def test_o_que_a_bancada_edita_existe_no_mapa_de_canais() -> None:
    """`EDITAVEIS` é o que a bancada ESCREVE de volta — errar aqui é gravar no vazio."""
    cabecalho = set(_cabecalho(MAPA))
    faltando = [c for c in _lista_literal("EDITAVEIS") if c not in cabecalho]
    assert not faltando, (
        f"a bancada quer editar {faltando}, e o mapa de canais não tem essas "
        f"colunas ({MAPA.relative_to(RAIZ)})"
    )


def test_o_que_a_grade_mostra_existe_no_mapa_de_canais() -> None:
    """A lista `vis` é o `df[vis]` que derrubava a bancada na primeira renderização."""
    cabecalho = set(_cabecalho(MAPA))
    faltando = [c for c in _lista_literal("vis") if c not in cabecalho]
    assert not faltando, (
        f"a grade pede {faltando}; `df[vis]` levanta KeyError e a bancada não "
        "abre — foi assim que a migração v2 a derrubou"
    )


def test_o_que_a_bancada_le_por_atributo_existe_no_mapa_de_canais() -> None:
    """Os filtros, a busca e o caderno leem coluna como `v.chave` — sem lista nenhuma."""
    cabecalho = set(_cabecalho(MAPA))
    faltando = sorted(c for c in _colunas_por_atributo() if c not in cabecalho)
    assert not faltando, (
        f"a bancada lê {faltando} de um quadro do mapa, e o cabeçalho não tem "
        "essas colunas (se for método novo do pandas, declare-o em API_DO_PANDAS)"
    )


def test_os_nomes_de_quadro_declarados_ainda_existem_na_bancada() -> None:
    """A régua acima só morde os nomes que ela conhece; um rename não pode emudecê-la."""
    vazios = sorted(n for n, atrs in _atributos_por_quadro().items() if not atrs)
    assert not vazios, (
        f"NOMES_DE_QUADRO cita {vazios}, que a bancada não usa mais: as colunas "
        "lidas por esse nome deixaram de ser conferidas em silêncio"
    )


def test_o_grau_e_a_ressalva_sao_editados_nos_dois_transportes() -> None:
    """Desde a v2 o que é por transporte vem EM PAR — como `aceita` e `aciona`."""
    editaveis = _lista_literal("EDITAVEIS")
    for sufixo in ("grau", "ressalva"):
        assert f"cabo_{sufixo}" in editaveis and f"radio_{sufixo}" in editaveis, (
            f"a bancada edita só um lado de `{sufixo}`: um lado editável e o "
            "outro não é a assimetria que a v2 existe para não deixar acontecer"
        )


def test_o_column_config_so_configura_coluna_que_a_grade_mostra() -> None:
    """Configuração de coluna ausente da grade é regra desligada em silêncio."""
    vis = _lista_literal("vis")
    orfas = [c for c in _chaves_do_column_config() if c not in vis]
    assert not orfas, (
        f"o `column_config` configura {orfas}, que não estão em `vis`: o "
        "selectbox de vocabulário simplesmente não aparece"
    )


def test_o_formulario_de_ensaio_escreve_o_cabecalho_de_ensaios_em_ordem() -> None:
    """O `DictWriter` anexa por POSIÇÃO — ordem trocada desalinha o caderno calado."""
    assert _campos_do_ensaio() == _cabecalho(ENSAIOS), (
        "o formulário de ensaio da bancada não grava exatamente o cabeçalho de "
        f"{ENSAIOS.relative_to(RAIZ)}, na mesma ordem"
    )
