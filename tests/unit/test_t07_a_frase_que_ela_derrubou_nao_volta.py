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
import io
import tokenize
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
}

#: Onde a frase morta PODE aparecer, e por quê. Só documento histórico —
#: apagar a nota datada seria apagar a decisão, que é o oposto da regra.
ARQUIVOS_ISENTOS = {
    # A nota datada do glade é o REGISTRO da morte da frase: ela cita a frase
    # para dizer que ela morreu. Apagá-la faria a próxima pessoa reescrever o
    # enquadramento antigo sem saber que ele já foi derrubado uma vez.
    SRC / "gui" / "main.glade",
}


def _arquivos_python() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p not in ARQUIVOS_ISENTOS)


def _linhas_que_apenas_explicam(texto: str) -> set[int]:
    """Linhas de comentário e de docstring — as que EXPLICAM, não pintam.

    A distinção não é de estilo, é a regra inteira deste portão. Uma frase
    derrubada CITADA num comentário é a nota datada da casa: ela impede a
    próxima pessoa de reescrever o enquadramento antigo achando que é
    novidade. A mesma frase dentro de uma string que chega à tela é o defeito.

    Comentário sai do `tokenize`; docstring sai da árvore sintática. Nenhum
    dos dois se descobre por indentação — e foi tentando descobrir por
    indentação que a primeira versão deste arquivo se reprovou sozinha.

    **Comentário de FIM DE LINHA não conta**, e isso não é detalhe: a mordida
    deste portão foi arrancada com um `# CURA ARRANCADA` no fim da linha de
    código, e a primeira versão da regra perdoou a linha inteira por causa
    dele. Um `#` no fim não transforma o que vem antes em explicação — e
    perdoar por isso seria dar a qualquer pessoa um jeito de pintar a frase
    morta na tela e manter o portão verde.
    """
    linhas: set[int] = set()

    corpo_da_linha = texto.splitlines()
    for token in tokenize.generate_tokens(io.StringIO(texto).readline):
        if token.type != tokenize.COMMENT:
            continue
        numero = token.start[0]
        if corpo_da_linha[numero - 1].lstrip().startswith("#"):
            linhas.add(numero)

    for no in ast.walk(ast.parse(texto)):
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
            alvo = corpo[0]
            linhas.update(range(alvo.lineno, (alvo.end_lineno or alvo.lineno) + 1))

    return linhas


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
        if frase.lower() not in texto.lower():
            continue
        explicam = _linhas_que_apenas_explicam(texto)
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if frase.lower() in linha.lower() and numero not in explicam:
                achados.append(
                    f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()}"
                )

    assert not achados, (
        f"a frase {frase!r} foi derrubada em {quando} e voltou a ser PINTADA:\n  "
        + "\n  ".join(achados)
        + f"\n\n{o_que_dizer}"
    )


def test_o_portao_sabe_recusar_uma_frase_pintada(tmp_path: Path) -> None:
    """Régua que só sabe passar não é régua.

    Exercita o caminho de erro com um arquivo plantado: a MESMA frase, uma vez
    em comentário (permitida) e uma vez numa string de código (proibida). Se o
    portão não distinguir os dois, ele é inútil nas duas direções.
    """
    alvo = tmp_path / "falso.py"
    alvo.write_text(
        "# jogos cujo DualSense é entregue pela Steam — nota datada\n"
        "def f() -> str:\n"
        '    """Docstring citando entregue pela Steam."""\n'
        '    return "o controle é entregue pela Steam"\n'
        '    x = "entregue pela Steam"  # comentário de fim de linha\n',
        encoding="utf-8",
    )
    texto = alvo.read_text(encoding="utf-8")
    explicam = _linhas_que_apenas_explicam(texto)

    assert 1 in explicam, "comentário tem de ser reconhecido como explicação"
    assert 3 in explicam, "docstring tem de ser reconhecida como explicação"
    assert 4 not in explicam, "string de código NÃO é explicação — é tela"
    assert 5 not in explicam, (
        "um `#` no FIM da linha não transforma o código que vem antes em "
        "explicação — foi assim que a mordida quase passou despercebida"
    )


def test_a_nota_datada_da_decisao_continua_no_glade() -> None:
    """Régua que sabe ACEITAR — e que protege o REGISTRO da decisão.

    *"Não se apaga decisão medida"*: a nota datada de 09/08 no `main.glade` é
    o que impede a próxima pessoa de reescrever o enquadramento antigo
    achando que é novidade. Se alguém "limpar" a nota para deixar o portão
    acima verde, este teste reprova — a cura pelo lado errado.

    O `main.glade` é território de outra frente nesta madrugada; este teste
    apenas o LÊ, e existe justamente para que ninguém o edite por engano.
    """
    glade = SRC / "gui" / "main.glade"
    texto = glade.read_text(encoding="utf-8")

    assert "ESCONDER-EM-VEZ-DE-SAIR-01" in texto
    assert "entregue pela Steam" in texto, (
        "a nota datada que registra a morte da frase sumiu do glade"
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
