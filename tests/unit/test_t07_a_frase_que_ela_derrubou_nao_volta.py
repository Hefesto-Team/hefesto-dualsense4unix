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

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: Enquadramentos que uma decisão dela derrubou, com a data e o que dizer no
#: lugar. Não é lista de jargão (isso é o `validar-palavra-de-tela.py`): é
#: lista de afirmações que a medição ou a decisão dela tornaram FALSAS.
FRASES_DERRUBADAS: dict[str, tuple[str, str]] = {
    "entregue pela Steam": (
        "09/08/2026, ESCONDER-EM-VEZ-DE-SAIR-01 (decisão dela)",
        "A marca ESCONDE o controle físico do jogo — ela não entrega o "
        "controle à Steam. Diga o que a caixinha da aba Perfis diz: "
        "'o controle físico fica escondido'.",
    ),
    # S4 (28/08/2026). A frase de 09/08 tinha UMA redação nesta lista, e a
    # MESMA afirmação sobrevivia em outras quatro — o `cmd_steam.py` dizia "a
    # Steam entrega o controle" e "entrada pela Steam"; o toast de "Este jogo
    # não funciona" dizia "recebe o controle direto pela Steam" e "passa a
    # enxergar o controle físico direto". Régua que pega uma redação só não
    # pega o fato; é o mesmo defeito que ela existe para matar.
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

#: Onde a frase morta PODE aparecer, e por quê. Só documento histórico —
#: apagar a nota datada seria apagar a decisão, que é o oposto da regra.
ARQUIVOS_ISENTOS = {
    # A nota datada do glade é o REGISTRO da morte da frase: ela cita a frase
    # para dizer que ela morreu. Apagá-la faria a próxima pessoa reescrever o
    # enquadramento antigo sem saber que ele já foi derrubado uma vez.
    #
    # CINTO, não caminho: `_arquivos_python` varre `*.py`, então o glade já
    # está fora do alcance hoje. A linha fica para o dia em que alguém alargar
    # o glob — o que este portão precisaria, porque o `main.glade` PINTA texto
    # e nenhuma régua desta lista o alcança. Está no relato da S4.
    SRC / "gui" / "main.glade",
}


def _arquivos_python() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p not in ARQUIVOS_ISENTOS)


def _strings_de_tela(texto: str) -> list[tuple[int, str]]:
    """[(linha, texto)] de toda string que PINTA — docstring excluída.

    Por AST, e não por linha, e a diferença é a mordida deste portão: o
    interpretador já junta literais adjacentes (`"a" "b"` vira UM
    `ast.Constant`, e o mesmo vale para os pedaços de uma f-string
    concatenada), então uma frase quebrada em duas linhas chega aqui inteira.

    FATO ERRADO, SUBSTITUÍDO (28/08/2026, S4): até hoje esta varredura era
    `frase in linha`, e por isso era CEGA a exatamente esse caso — o toast de
    "Este jogo não funciona" pintava *"ele passa a enxergar o controle "* /
    *"físico direto"* em duas linhas, e nenhuma delas continha a frase. A
    correção fecha o buraco em vez de contorná-lo com uma segunda redação na
    lista.

    Comentário não existe na AST, então continua isento de graça — que é o
    ponto: uma frase derrubada CITADA num comentário é a nota datada da casa.
    """
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


@pytest.mark.parametrize("frase", sorted(FRASES_DERRUBADAS))
def test_frase_derrubada_nao_e_pintada_na_tela(frase: str) -> None:
    """A mordida: ponha a frase numa string de código e isto reprova.

    Em comentário ou docstring ela pode ficar — e deve, onde a nota datada
    explica que morreu.
    """
    quando, o_que_dizer = FRASES_DERRUBADAS[frase]

    achados: list[str] = []
    for arquivo in _arquivos_python():
        texto = arquivo.read_text(encoding="utf-8")
        for numero, valor in _strings_de_tela(texto):
            if frase.lower() in valor.lower():
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {valor!r}")

    assert not achados, (
        f"a frase {frase!r} foi derrubada em {quando} e voltou a ser PINTADA:\n  "
        + "\n  ".join(achados)
        + f"\n\n{o_que_dizer}"
    )


def test_o_portao_sabe_recusar_uma_frase_pintada() -> None:
    """Régua que só sabe passar não é régua.

    Exercita o caminho de erro com um arquivo plantado: a MESMA frase em
    comentário (permitida), em docstring (permitida), numa string de código
    (proibida), com `#` no fim da linha (proibida — um `#` no fim não
    transforma o que vem antes em explicação) e **quebrada em duas linhas**
    (proibida — foi assim que ela sobreviveu ao portão até 28/08/2026).
    """
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


def test_o_lexico_novo_e_o_mesmo_da_caixinha_de_perfis() -> None:
    """A frase da aba Sistema e a da aba Perfis marcam a MESMA coisa.

    Duas maneiras de dizer o mesmo gesto obrigam quem lê a descobrir que são
    o mesmo gesto. Este teste trava as duas na mesma palavra — "o controle
    físico fica escondido" — para que a próxima reescrita mexa nas duas ou em
    nenhuma.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        texto_da_marca_do_steam_input,
    )

    da_aba_perfis = texto_da_marca_do_steam_input("marcado", appid="2111190")
    do_storm_doctor = (SRC / "integrations" / "storm_doctor.py").read_text(
        encoding="utf-8"
    )

    assert "o controle físico fica escondido" in da_aba_perfis
    assert "o controle físico fica escondido" in do_storm_doctor
