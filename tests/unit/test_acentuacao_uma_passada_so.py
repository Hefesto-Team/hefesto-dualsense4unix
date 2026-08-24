"""O portão de acentuação faz UMA passada por linha, não 314.

**O DEFEITO, medido em 23/08/2026.** `varre_arquivo` compilava 314 regex — um
por par de correção — e passava TODAS elas por CADA linha de 27,9 MB de árvore.
Medição do dia: **157,5 s de um orçamento de 181 s**, ou 87% do custo de todos
os portões não-pytest juntos. Nesta sessão o comando estourou o teto de 2 min
várias vezes, e a versão antiga voltou a estourar quando foi cronometrada
lado a lado — a nova, no mesmo instante, respondeu em **37,6 s**.

**Por que isso é defeito e não lentidão.** Um portão que cobra dois minutos e
meio é um portão que a pessoa aprende a pular, e portão pulado protege menos que
portão nenhum. Ninguém põe isso num `git push`.

**A cura é a lei do storm dela aplicada a um script:** *achar a causa raiz apaga
N gambiarras*. A causa não era "o script é grande" — era **313 passadas
desnecessárias sobre a mesma linha**. Uma alternância única faz o motor de regex
percorrer a linha uma vez, e o ganho é de ordem, não de constante.

**A PROVA QUE ESTE ARQUIVO GUARDA é a igualdade**, não a velocidade: as duas
implementações têm de devolver **exatamente o mesmo conjunto** de achados. A
ordem muda de propósito (a nova reporta na ordem em que a palavra aparece na
linha, que é a ordem em que a pessoa lê), e por isso a comparação é de conjunto.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-acentuacao.py"


def _modulo():
    spec = importlib.util.spec_from_file_location("validar_acentuacao", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _do_jeito_antigo(mod, texto: str, *, eh_python: bool = False) -> set[tuple]:
    """A implementação de 314 passadas, preservada como REFERÊNCIA.

    Ela é o padrão-ouro deste teste: se a alternância divergir dela, a
    alternância está errada — não o contrário.
    """
    achados: set[tuple] = set()
    for idx, linha in enumerate(texto.splitlines()):
        for errada, correta in mod._CORRECOES.items():
            for m in mod._PATTERNS[errada].finditer(linha):
                if mod._is_uppercase_snake_token(linha, m.start(), m.end()):
                    continue
                if mod._esta_em_identificador_snake(linha, m.start(), m.end()):
                    continue
                if m.group().lower() == correta.lower():
                    continue
                achados.add((idx + 1, m.group(), correta))
    return achados


def _do_jeito_novo(mod, texto: str) -> set[tuple]:
    achados: set[tuple] = set()
    for idx, linha in enumerate(texto.splitlines()):
        for m in mod._ALTERNANCIA.finditer(linha):
            correta = mod._CORRECOES.get(m.group().lower())
            if correta is None:
                continue
            if mod._is_uppercase_snake_token(linha, m.start(), m.end()):
                continue
            if mod._esta_em_identificador_snake(linha, m.start(), m.end()):
                continue
            if m.group().lower() == correta.lower():
                continue
            achados.add((idx + 1, m.group(), correta))
    return achados


#: Casos que exercitam o que a alternância poderia quebrar: a ordem de
#: first-match, as guardas de identificador, e o `IGNORECASE`.
CASOS = [
    "Uma decisao mal escrita, uma acao sem acento, uma opcao.",
    "CHORE-ACAO-01 é identificador e nao deve acusar.",
    "nome_de_variavel_com_acao_dentro também nao.",
    "A memoria, a referencia, o criterio, o proprio, o codigo, o modulo.",
    "MAIUSCULA: DECISAO ACAO OPCAO — o IGNORECASE tem de pegar.",
    "def funcao_com_decisao(): pass",
    "portugues e portugues no meio da frase, duas vezes.",
    "",
    "linha sem nenhuma palavra errada nenhuma mesmo",
]


@pytest.mark.parametrize("texto", CASOS)
def test_a_alternancia_devolve_o_mesmo_que_as_314_passadas(texto: str) -> None:
    """MORDE: qualquer divergência entre as duas implementações.

    Em especial: se alguém tirar a ordenação por comprimento da alternância,
    `acao` passa a casar antes de uma palavra mais longa que a contenha, e o
    achado sai truncado — este teste reprova.
    """
    mod = _modulo()
    assert _do_jeito_novo(mod, texto) == _do_jeito_antigo(mod, texto), (
        "a alternância divergiu das 314 passadas neste texto:\n  "
        + repr(texto)
    )


def test_a_arvore_inteira_da_o_mesmo_resultado() -> None:
    """A igualdade sobre dado real, e não só sobre casos escolhidos por mim.

    Amostra os arquivos versionados de `docs/` e `src/` — o teste inteiro leva
    segundos porque a implementação nova é rápida, que é o ponto.
    """
    mod = _modulo()
    amostra = sorted(RAIZ.glob("docs/**/*.md"))[:60] + sorted(RAIZ.glob("src/**/*.py"))[:40]
    assert amostra, "instrumento inválido: a amostra ficou vazia"

    divergentes = []
    for f in amostra:
        texto = f.read_text(encoding="utf-8", errors="replace")
        if _do_jeito_novo(mod, texto) != _do_jeito_antigo(mod, texto):
            divergentes.append(str(f.relative_to(RAIZ)))

    assert not divergentes, (
        "a alternância diverge das 314 passadas nestes arquivos:\n  "
        + "\n  ".join(divergentes)
    )


def test_a_ordenacao_por_comprimento_esta_la() -> None:
    """A trava que impede o achado truncado.

    A alternância do Python é *first-match*: sem ordenar da palavra mais longa
    para a mais curta, um prefixo casa antes do termo inteiro.

    MORDE: tirar o `sorted(..., key=len, reverse=True)`.
    """
    mod = _modulo()
    fonte = inspect.getsource(mod)
    assert "key=len" in fonte and "reverse=True" in fonte, (
        "a alternância perdeu a ordenação por comprimento: um prefixo passa a "
        "casar antes do termo inteiro e o achado sai truncado"
    )


def test_o_laco_de_314_passadas_nao_voltou() -> None:
    """MORDE: reintroduzir o laço sobre `_CORRECOES` dentro do laço de linhas.

    Confere pela ÁRVORE SINTÁTICA, não por texto: um comentário que mencione
    `_CORRECOES.items()` não pode reprovar, e uma reintrodução disfarçada não
    pode passar.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))

    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef) or no.name != "checar_arquivo":
            continue
        for interno in ast.walk(no):
            if not isinstance(interno, ast.For):
                continue
            alvo = ast.dump(interno.iter)
            assert "_CORRECOES" not in alvo, (
                "`checar_arquivo` voltou a iterar sobre `_CORRECOES` dentro do "
                "laço de linhas: são 314 passadas por linha de novo, e o "
                "portão volta a custar dois minutos e meio"
            )
        return

    pytest.fail("instrumento inválido: não achei `checar_arquivo` no script")


def test_a_alternancia_e_um_regex_so() -> None:
    """MORDE: trocar a alternância por uma lista de padrões."""
    mod = _modulo()
    assert isinstance(mod._ALTERNANCIA, re.Pattern), (
        "`_ALTERNANCIA` deixou de ser um único padrão compilado"
    )
    assert mod._ALTERNANCIA.flags & re.IGNORECASE, (
        "a alternância perdeu o IGNORECASE: `DECISAO` em maiúscula deixaria de acusar"
    )
