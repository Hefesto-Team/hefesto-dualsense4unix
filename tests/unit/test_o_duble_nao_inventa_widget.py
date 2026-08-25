"""Todo id de widget que um dublê publica tem de existir de verdade.

**GATILHO-NÃO-PERDIDO-01 (25/08/2026).** A sprint que dá nome a este arquivo
fechou com uma regra e sem máquina nenhuma para cobrá-la:

    O `.get()` de um campo que não existe devolve `None`, e `None` parece
    defeito. Antes de abrir uma frente contra uma ausência, confira que o nome
    perguntado é o nome do campo.

Este é o mesmo defeito virado do avesso, e ele custou mais caro: **o dublê
INVENTA o campo, e aí nada parece defeito.** Medido nesta árvore, na aba
Gatilhos: `_mk_widgets` publicava `trigger_{lado}_preset_combo`, um id que o
glade não tem e que o produto nunca pede. Sobrou da
FEAT-DSX-COMBO-TO-SEGMENTED-01, que trocou o combo do preset por um segmentado
num slot — a troca foi feita no seletor de MODO e esquecida no de PRESET.

**O preço não era cosmético.** O órfão era um `_FakeComboBox`, cujo
`set_active_id` aceita QUALQUER id; o segmentado real RECUSA id que não está
entre os itens. Três testes pegavam o órfão, mandavam `rampa_crescente` nele e
ficavam verdes **sem que a aba tivesse publicado esse preset**. É "o dublê que
só sabe passar" (`COMO-REGER-AGENTES.md`, A2), e o dublê inventado é a forma
dele que nenhuma revisão de linha enxerga: o teste passa, o nome parece certo, e
só quem abre o glade descobre que aquele widget não existe.

**A régua é dupla, e é de propósito** (mesma disciplina dos dois portões de MAC
do `CLAUDE.md`): um id vale se o **glade** o declara **ou** se o **produto** o
pede por `_get`/`get_object`. Só o glade reprovaria widget montado em código; só
o produto reprovaria id que existe na tela e ainda não tem leitor.

**A DÍVIDA nasce declarada, e não reprovando** — precedente do
`check_colisao_de_sprints.py`: um portão que reprova o que já estava lá é um
portão que alguém desliga com `--no-verify` na segunda-feira. O que já existia
entra em `DIVIDA_DECLARADA`, com data, dono e motivo; **o que nascer novo
reprova.**

Mordida: publicar um id qualquer num `_widgets` de teste, sem pôr no glade.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
SRC = RAIZ / "src"
TESTES = RAIZ / "tests"

#: Os nomes de variável que este portão entende como "mapa de widget da
#: janela". `_trigger_param_widgets` fica DE FORA de propósito: as chaves dele
#: são nomes de parâmetro de gatilho (`pos_0`, `force`), não ids de widget —
#: incluí-lo faria o portão acusar quem não errou, que é como uma régua vira
#: ruído e depois vira dispensa permanente.
MAPAS_DE_WIDGET = frozenset({"widgets", "_widgets"})

#: Variáveis de molde que os dublês usam em f-string de id, e o que cada uma
#: pode valer. Sem isto, `trigger_{side}_desc` nunca casaria com o glade.
MOLDES: dict[str, tuple[str, ...]] = {
    "side": ("left", "right"),
    "lado": ("left", "right"),
    "n": ("1", "2", "3", "4"),
    "i": tuple(str(k) for k in range(10)),
}

#: O que JÁ estava na árvore quando este portão nasceu (25/08/2026, E4). Cada
#: linha é um defeito real, não uma dispensa: o id é publicado por um dublê e
#: **ninguém no produto o pede**. Ficou aqui, e não curado, porque o arquivo é
#: de outra frente desta leva (regra R1 do `COMO-REGER-AGENTES.md`: quando o
#: conserto pede arquivo alheio, o agente RELATA em vez de editar).
#:
#: Sair desta lista é o conserto. Entrar nela exige a mesma prova: quem é o
#: dono, e por que não foi curado agora.
DIVIDA_DECLARADA: dict[str, str] = {
    "profile_preview_label": (
        "tests/unit/test_r12_editor_simples_gui.py:190 — publicado pelo dublê "
        "`_Editor._widgets`; nenhum `_get`/`get_object` do produto o pede e o "
        "glade não o declara. Território da aba Perfis (frente B7 desta leva); "
        "registrado como aberto no relatório da E4 em 25/08/2026."
    ),
}


def _ids_do_glade() -> set[str]:
    return set(re.findall(r'id="([^"]+)"', GLADE.read_text(encoding="utf-8")))


def _expandir(molde: str) -> set[str]:
    """`trigger_{side}_desc` -> {trigger_left_desc, trigger_right_desc}."""
    saida = {molde}
    for var, valores in MOLDES.items():
        marca = "{" + var + "}"
        proximo: set[str] = set()
        for texto in saida:
            if marca in texto:
                proximo.update(texto.replace(marca, v) for v in valores)
            else:
                proximo.add(texto)
        saida = proximo
    return {t for t in saida if "{" not in t}


def _ids_que_o_produto_pede() -> set[str]:
    """Todo id passado a `_get(...)` ou `get_object(...)` em `src/`."""
    pedidos: set[str] = set()
    padroes = (
        r'_get\(\s*f?"([a-z0-9_{}]+)"',
        r'get_object\(\s*f?"([a-z0-9_{}]+)"',
    )
    for arquivo in SRC.rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        for padrao in padroes:
            for bruto in re.findall(padrao, texto):
                pedidos |= _expandir(bruto)
    return pedidos


def _chaves_do_no(chave: ast.expr) -> set[str]:
    """Extrai os ids de uma chave literal ou de uma f-string de molde."""
    if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
        return {chave.value}
    if isinstance(chave, ast.JoinedStr):
        partes: list[str] = []
        for pedaco in chave.values:
            if isinstance(pedaco, ast.Constant):
                partes.append(str(pedaco.value))
            elif isinstance(pedaco, ast.FormattedValue):
                nome = getattr(pedaco.value, "id", None)
                if nome is None:
                    return set()
                partes.append("{" + str(nome) + "}")
        return _expandir("".join(partes))
    return set()


def _nome_do_alvo(no: ast.expr) -> str:
    return str(getattr(no, "id", None) or getattr(no, "attr", None) or "")


def _ids_publicados_pelos_dubles() -> list[tuple[str, int, str]]:
    """Todo id que um teste grava num mapa de widget. (arquivo, linha, id)."""
    achados: list[tuple[str, int, str]] = []
    for arquivo in sorted(TESTES.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        try:
            arvore = ast.parse(texto)
        except SyntaxError:  # pragma: no cover — fixture proposital
            continue
        relativo = str(arquivo.relative_to(RAIZ))
        for no in ast.walk(arvore):
            # `self._widgets: dict[str, Any] = {...}` é AnnAssign, não Assign —
            # e é a forma que os dublês de janela mais usam. Ler só `Assign`
            # deixava o portão cego para eles, o que este arquivo descobriu de
            # si mesmo: o `profile_preview_label` da dívida não aparecia.
            alvo: ast.expr
            valor: ast.expr
            if isinstance(no, ast.AnnAssign):
                if no.value is None:
                    continue
                alvo = no.target
                valor = no.value
            elif isinstance(no, ast.Assign) and len(no.targets) == 1:
                alvo = no.targets[0]
                valor = no.value
            else:
                continue
            # forma 1: widgets["id"] = ...
            if isinstance(alvo, ast.Subscript):
                if _nome_do_alvo(alvo.value) not in MAPAS_DE_WIDGET:
                    continue
                for identificador in _chaves_do_no(alvo.slice):
                    achados.append((relativo, no.lineno, identificador))
                continue
            # forma 2: self._widgets = {"id": ..., ...}
            if _nome_do_alvo(alvo) not in MAPAS_DE_WIDGET:
                continue
            if not isinstance(valor, ast.Dict):
                continue
            for chave in valor.keys:
                if chave is None:
                    continue
                for identificador in _chaves_do_no(chave):
                    achados.append((relativo, no.lineno, identificador))
    return achados


def test_nenhum_duble_publica_widget_que_o_produto_nao_conhece() -> None:
    """Id de dublê tem de estar no glade OU ser pedido pelo produto.

    Mordida: acrescentar `widgets["nao_existe_na_tela"] = _Box()` a qualquer
    `_mk_widgets` desta suíte.
    """
    conhecidos = _ids_do_glade() | _ids_que_o_produto_pede()
    orfaos = [
        (arquivo, linha, identificador)
        for arquivo, linha, identificador in _ids_publicados_pelos_dubles()
        if identificador not in conhecidos
        and identificador not in DIVIDA_DECLARADA
    ]
    assert not orfaos, (
        "dublê publicando widget que o produto não conhece — nem o glade o "
        "declara, nem nenhum `_get`/`get_object` o pede. Um dublê assim "
        "responde por um widget que não existe, e o teste que falar com ele "
        "fica verde sem medir a tela:\n"
        + "\n".join(
            f"  {arq}:{lin}  ->  {ident!r}"
            for arq, lin, ident in sorted(orfaos)
        )
    )


@pytest.mark.parametrize("identificador", sorted(DIVIDA_DECLARADA))
def test_a_divida_declarada_ainda_e_divida(identificador: str) -> None:
    """A lista de dívida não pode envelhecer em silêncio.

    Quando alguém curar o id — pondo no glade, dando-lhe leitor no produto, ou
    apagando do dublê —, este teste reprova pedindo que a linha SAIA da lista.
    Sem isto a dívida vira uma dispensa permanente, que é como a lista de
    exceção de um portão acaba maior que o portão.

    Mordida: apagar `profile_preview_label` do dublê sem tirá-lo da lista.
    """
    conhecidos = _ids_do_glade() | _ids_que_o_produto_pede()
    assert identificador not in conhecidos, (
        f"{identificador!r} deixou de ser órfão — o produto passou a "
        f"conhecê-lo. Tire a linha de `DIVIDA_DECLARADA`."
    )
    publicados = {i for _a, _l, i in _ids_publicados_pelos_dubles()}
    assert identificador in publicados, (
        f"{identificador!r} não é mais publicado por dublê nenhum. Tire a "
        f"linha de `DIVIDA_DECLARADA`: motivo: {DIVIDA_DECLARADA[identificador]}"
    )
