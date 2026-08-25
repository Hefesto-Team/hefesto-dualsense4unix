"""STATUS-DIZ-O-QUE-VÊ-01/T5 — o modo compacto do card tem de ter um dono.

`ControllerCard(compact=True)` desenha um card estreito, para dois controles
lado a lado. **Desde a EMPILHA-02 (02/08/2026) a aba não constrói card
compacto nenhum:** a decisão dela foi um card por linha, com rolagem, e cada
card recebe a largura inteira da janela.

    $ grep -rn "compact=False" src/.../actions/status_actions.py
    card = ControllerCard(compact=False, mostrar_estado_global=not compact)

O `compact` local ali é a CONTAGEM (`len(keys) >= 2`), e só decide se o frame
"Estado" volta à tela — não o desenho do card. São duas coisas com o mesmo
nome, e é parte do defeito.

Este portão pergunta o que nenhum portão desta casa perguntava: **existe
chamador de produção?** Ele é a metade pequena da T14 (a pergunta geral é da
Onda 12), com o escopo desta aba e um alvo só.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


def _chamadas_com_compact_verdadeiro() -> list[str]:
    """Toda chamada de produção que passa ``compact=True``, com o endereço.

    AST, e não `grep`: o `grep` da sprint achava a DOCSTRING de
    `ControllerCard` — o exemplo de uso que estava errado desde 02/08 — e
    teria dado o portão por vermelho pelo motivo errado, ou por verde depois
    de alguém reescrever a prosa sem tocar em código nenhum.
    """
    achados: list[str] = []
    for arquivo in sorted(_SRC.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — arquivo quebrado é outro erro
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for palavra in no.keywords:
                if (
                    palavra.arg == "compact"
                    and isinstance(palavra.value, ast.Constant)
                    and palavra.value.value is True
                ):
                    relativo = arquivo.relative_to(_SRC.parents[1])
                    achados.append(f"{relativo}:{no.lineno}")
    return achados


def test_o_modo_compacto_tem_dono() -> None:
    """Ou nenhum código de produção pede o card compacto, ou alguém o pede.

    **A mordida:** ponha um `ControllerCard(compact=True)` em qualquer lugar
    de `src/` e o portão reprova nomeando arquivo e linha. Ele fica verde de
    novo com a chamada removida — ou com ela LEGÍTIMA, e aí a próxima pessoa
    tem de vir aqui explicar quem constrói o modo compacto e quando, que é a
    conversa que faltou por 23 dias.

    O que ele NÃO faz: proibir o modo compacto de existir. Sete arquivos de
    teste ainda o medem, e a decisão sobre cada um é da T5 — ela pede motivo
    escrito por arquivo, não uma faxina em bloco.
    """
    chamadas = _chamadas_com_compact_verdadeiro()
    assert not chamadas, (
        "código de produção voltou a construir o card COMPACTO: "
        f"{chamadas}. Desde a EMPILHA-02 (02/08/2026) a aba dá a largura "
        "inteira a todo card — se a volta é intencional, escreva aqui quem "
        "constrói o modo compacto e quando"
    )


def test_a_docstring_do_card_nao_ensina_o_modo_que_ninguem_constroi() -> None:
    """O exemplo de uso tem de ser o que a aba faz — e era o oposto.

    Este é o segundo lado da T5, e o mais barato de errar: o portão de cima
    olha só para CÓDIGO, então a prosa podia continuar ensinando errado para
    sempre. Um exemplo de docstring é a primeira coisa que a próxima pessoa
    copia.

    **A mordida:** devolva o exemplo antigo (`ControllerCard(compact=True)`
    com o comentário "compact = 2+ cards") e o teste reprova.
    """
    import inspect

    from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard

    doc = inspect.getdoc(ControllerCard) or ""
    assert "compact=True" not in doc, (
        "a docstring de `ControllerCard` volta a ensinar `compact=True` como "
        "o uso normal. Produção passa `compact=False` desde 02/08/2026, e "
        "este exemplo foi a fonte dos sete arquivos de teste que travam um "
        "desenho que a janela não monta"
    )
    assert "compact=False" in doc, (
        "a docstring de `ControllerCard` parou de mostrar como a aba monta o "
        "card. O exemplo é o que a próxima pessoa copia — ele precisa ser o "
        "que produção faz"
    )
