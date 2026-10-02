"""T-07 (SISTEMA-O-VIGIA-VIVO-01) — a frase derrubada em 09/08, viva em 25/08.

Em **09/08/2026** ela derrubou um enquadramento inteiro
(ESCONDER-EM-VEZ-DE-SAIR-01): *"o controle passa a ser entregue pela Steam"*
**morreu**. A marca "Este jogo não funciona" inverteu de lado — em vez de
tirar o Hefesto da frente, ela **esconde o controle físico** do jogo, e os
controles virtuais do Hefesto ficam de pé, um por jogador.

O `main.glade` recebeu o recado naquele dia (a nota datada em volta do
`btn_steam_game_broken` diz, com todas as letras, que a frase morreu). **O
código que pinta, não.** Dezesseis dias depois, `storm_doctor.py` ainda
mandava para a tela *"jogos cujo DualSense é entregue pela Steam"* — o
INVERSO do que o produto faz.

Este portão existe porque a regra da casa é que fato errado sai de TODOS os
lugares onde aparece, e uma correção pela metade deixa as duas versões vivas.
Aqui a metade que faltava era a que a usuária realmente lê.

**Alcance declarado:** `src/` inteiro, não só `app/`. A linha que sobreviveu
morava em `integrations/`, fora do alcance dos dois corpos de texto que o
`scripts/validar-palavra-de-tela.py` varre — e foi exatamente por isso que ela
sobreviveu.
"""
from __future__ import annotations

import ast
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

FRASES_DERRUBADAS: dict[str, tuple[str, str]] = {
    "entregue pela Steam": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "A marca ESCONDE o controle físico do jogo — ela não entrega o "
        "controle à Steam. Diga o que a caixinha da aba Perfis diz: "
        "'o controle físico fica escondido'.",
    ),
    "a Steam entrega o controle": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "Quem entrega o controle ao jogo continua sendo o Hefesto, marcado "
        "ou não. A allowlist só impede o guarda de desligar o Steam Input "
        "daquele jogo.",
    ),
    "entrada pela Steam": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "A entrada continua vindo do gamepad virtual do Hefesto — e por isso "
        "o co-op não cai mais. Não diga que a entrada vem da Steam.",
    ),
    "controle direto pela Steam": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "Diga o que acontece de verdade: 'o controle físico fica escondido e "
        "o jogo passa a ver só os do Hefesto'.",
    ),
    "enxergar o controle físico direto": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "É o INVERSO do que o produto faz: a marca ESCONDE o físico. Quem "
        "escreve isto está descrevendo a borda que morreu em 09/08.",
    ),
}


def _strings_de_tela(texto: str) -> list[tuple[int, str]]:
    """[(linha, texto)] de toda string que PINTA — docstring excluída."""
    arvore = ast.parse(texto)
    docstrings: set[int] = set()
    for no in ast.walk(arvore):
        if not isinstance(
            no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        corpo = getattr(no, "body", [])
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            docstrings.add(id(corpo[0].value))

    saida: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docstrings
        ):
            saida.append((no.lineno, no.value))
    return saida


def test_o_portao_sabe_recusar_uma_frase_pintada() -> None:
    """Régua que só sabe passar não é régua."""
    plantado = (
        "# jogos cujo DualSense é entregue pela Steam — nota datada\n"
        "def f() -> str:\n"
        '    """Docstring citando entregue pela Steam."""\n'
        '    return "o controle é entregue pela Steam"\n'
        "def g() -> str:\n"
        '    x = "entregue pela Steam"  # comentário de fim de linha\n'
        '    return ("o controle é entregue "\n'
        '            "pela Steam, e a frase atravessa duas linhas")\n'
    )
    pintadas = [v for _, v in _strings_de_tela(plantado)]

    assert sum("entregue pela Steam" in v for v in pintadas) == 3, (
        "o portão tem de ver as TRÊS strings de código (inclusive a de fim de "
        f"linha e a quebrada em duas) e NENHUMA das explicações: {pintadas!r}"
    )
    assert not any("Docstring citando" in v for v in pintadas), (
        "docstring tem de ser reconhecida como explicação"
    )
    assert not any("nota datada" in v for v in pintadas), (
        "comentário nem chega à AST — a isenção é estrutural"
    )


