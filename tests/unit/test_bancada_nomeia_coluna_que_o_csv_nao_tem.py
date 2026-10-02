"""A bancada só pode nomear coluna que o CSV realmente tem."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "scripts" / "bancada_do_mapa.py"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
ENSAIOS = RAIZ / "docs" / "data" / "ensaios.csv"

NOMES_DE_QUADRO = ("df", "v", "base", "alvos", "editado", "r")

API_DO_PANDAS = frozenset({"copy", "to_csv", "loc", "index", "itertuples", "columns"})


def _arvore() -> ast.Module:
    return ast.parse(BANCADA.read_text(encoding="utf-8"), filename=str(BANCADA))


def _cabecalho(caminho: Path) -> list[str]:
    with open(caminho, encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _constantes_de_texto() -> dict[str, str]:
    """As strings atribuídas no topo do módulo, por nome."""
    achados: dict[str, str] = {}
    for no in _arvore().body:
        if not isinstance(no, ast.Assign):
            continue
        if isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
            for a in no.targets:
                if isinstance(a, ast.Name):
                    achados[a.id] = no.value.value
    return achados


def _importado_de_scripts(nome: str) -> list[str] | None:
    """O valor de `nome`, quando o `bancada_do_mapa.py` o IMPORTA de `scripts/`."""
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.ImportFrom) or not no.module:
            continue
        if not any(a.name == nome or a.asname == nome for a in no.names):
            continue
        import importlib
        import sys as _sys

        caminho = str(BANCADA.parent / "scripts")
        if caminho not in _sys.path:
            _sys.path.insert(0, caminho)
        modulo = importlib.import_module(no.module)
        valor = getattr(modulo, nome, None)
        if valor is None:
            return None
        return [str(x) for x in valor]
    return None


def _lista_literal(nome: str) -> list[str]:
    """A lista de strings atribuída a `nome`."""
    constantes = _constantes_de_texto()
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
                importado = _importado_de_scripts(item.value.id)
                if importado is not None:
                    colunas.extend(importado)
                else:
                    colunas.extend(_lista_literal(item.value.id))
            elif isinstance(item, ast.Constant) and isinstance(item.value, str):
                colunas.append(item.value)
            elif isinstance(item, ast.Name) and item.id in constantes:
                colunas.append(constantes[item.id])
            else:
                pytest.fail(
                    f"`{nome}` em bancada_do_mapa.py deixou de ser uma lista de nomes "
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


def _dict_do_column_config() -> ast.Dict:
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "data_editor"):
            continue
        for kw in no.keywords:
            if kw.arg == "column_config" and isinstance(kw.value, ast.Dict):
                return kw.value
    pytest.fail("não achei o `column_config` do `st.data_editor` em bancada_do_mapa.py")


def _chaves_do_column_config() -> list[str]:
    return [
        c.value
        for c in _dict_do_column_config().keys
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    ]


def _options_por_coluna() -> dict[str, str]:
    """Para cada coluna com `SelectboxColumn`, o NOME da lista passada em `options`."""
    achados: dict[str, str] = {}
    conf = _dict_do_column_config()
    for chave, valor in zip(conf.keys, conf.values, strict=True):
        if not (isinstance(chave, ast.Constant) and isinstance(chave.value, str)):
            continue
        if not (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Attribute)):
            continue
        if valor.func.attr != "SelectboxColumn":
            continue
        nomes = [
            kw.value.id
            for kw in valor.keywords
            if kw.arg == "options" and isinstance(kw.value, ast.Name)
        ]
        if not nomes:
            pytest.fail(
                f"o `SelectboxColumn` de `{chave.value}` não recebe `options` como o "
                "nome de uma lista do módulo; esta régua deixaria de conferi-lo em "
                "silêncio, que é exatamente o defeito que ela guarda"
            )
        achados[chave.value] = nomes[0]
    return achados


def _valores_da_coluna(caminho: Path, coluna: str) -> list[str]:
    """Os valores não vazios que a coluna REALMENTE tem, na ordem em que aparecem."""
    with open(caminho, encoding="utf-8", newline="") as fh:
        vistos: dict[str, None] = {}
        for linha in csv.DictReader(fh):
            valor = linha[coluna]
            if valor.strip():
                vistos.setdefault(valor, None)
        return list(vistos)


def _curto(valor: str, teto: int = 96) -> str:
    return valor if len(valor) <= teto else f"{valor[:teto]}… (+{len(valor) - teto} car.)"


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
    pytest.fail("não achei o dicionário `novo` do formulário de ensaio em bancada_do_mapa.py")


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
    for sufixo in ("ate_onde_foi", "ressalva"):
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


def test_todo_selectbox_da_grade_oferece_os_valores_que_o_mapa_ja_tem() -> None:
    """Um seletor cego ao dado não consegue devolver o dado que já estava lá."""
    orfaos: list[str] = []
    for coluna, lista in sorted(_options_por_coluna().items()):
        oferecidos = set(_lista_literal(lista))
        for valor in _valores_da_coluna(MAPA, coluna):
            if valor not in oferecidos:
                orfaos.append(f"  · `{coluna}` (options=`{lista}`): {_curto(valor)}")
    assert not orfaos, (
        "o mapa de canais tem valores que o seletor da bancada não oferece, e a "
        "gravação regrava a coluna com o que voltou da grade — o que não está em "
        "`options` não tem como voltar:\n"
        + "\n".join(orfaos)
        + f"\n\nsome cada valor à lista citada em bancada_do_mapa.py — como {MAPA.name} é "
        "quem manda, é a lista que se ajusta ao dado, nunca o contrário"
    )


def test_a_regua_dos_selectbox_ainda_alcanca_a_grade() -> None:
    """Régua que se desliga sozinha é pior que régua nenhuma — como a de quadros."""
    assert _options_por_coluna(), (
        "nenhuma coluna da grade usa `SelectboxColumn` com `options`: ou a bancada "
        "trocou de mecanismo, e então o teste acima virou decoração, ou a régua "
        "deixou de enxergar o `column_config`"
    )


def test_o_formulario_de_ensaio_escreve_o_cabecalho_de_ensaios_em_ordem() -> None:
    """O `DictWriter` anexa por POSIÇÃO — ordem trocada desalinha o caderno calado."""
    assert _campos_do_ensaio() == _cabecalho(ENSAIOS), (
        "o formulário de ensaio da bancada não grava exatamente o cabeçalho de "
        f"{ENSAIOS.relative_to(RAIZ)}, na mesma ordem"
    )
