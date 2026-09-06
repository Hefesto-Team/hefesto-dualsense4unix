"""A máscara não custa feature: o caminho do microfone é CEGO a ela.

ONDA5-MIC-VIRTUAL-01. A afirmação é dela, 05/09/2026, e tem duas metades:

    *"Exemplo controle do Xbox não tem microfone mas se o Mic do dualsense passa
    a ser lido a parte via Mic virtual. Usaríamos essa feature do controle mesmo
    no Xbox. Mesmo problema BT. **Hj já funciona assim**, sem a parte do Mic
    virtual."*

*"Hj já funciona assim"* é uma afirmação sobre o produto. Ela foi medida e está
confirmada — e é isto que esta régua guarda: **nada pode introduzir o primeiro
gate de máscara no caminho do microfone.**

O PRINCÍPIO, e ele vale além desta régua:
`docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md`
— *o Hefesto não explica a própria falha, ele a conserta.*

POR QUE UMA RÉGUA DE AUSÊNCIA, e ela é o tipo que esta casa costuma recusar: o
defeito que ela previne não dá erro. Alguém que escrevesse
``if not native_mode: return None`` em qualquer um dos seis arquivos do caminho
produziria um microfone que some quando ela liga a máscara Xbox — e o sintoma,
do lado dela, é indistinguível de *"o controle não tem microfone"*, que é
exatamente a frase que a decisão dela proíbe o produto de dizer.

O QUE ELA **NÃO** MEDE: se o microfone funciona. Isso é da bancada, com o
aparelho na mesa. Ela mede que a MÁSCARA não aparece na conta — que é uma
propriedade do texto do caminho, e é lida, não afirmada.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: OS SEIS ARQUIVOS DO CAMINHO DO MICROFONE, e a lista é o alcance declarado.
#:
#: Não é "tudo que fala de áudio": é o caminho que responde *"o microfone deste
#: controle está ligado e sendo ouvido?"* — o subsystem que o liga, a luz que
#: diz quem escuta, a ponte de rádio, a eleição, a lista de fontes, e o dono do
#: canal por controle.
O_CAMINHO = (
    "daemon/subsystems/mic_da_mesa.py",
    "daemon/subsystems/luz_do_mic.py",
    "daemon/subsystems/bt_mic.py",
    "integrations/eleicao_de_microfone.py",
    "integrations/dualsense_bt_audio.py",
    "integrations/fontes_de_captura.py",
    "integrations/canal_do_microfone.py",
)

#: AS PALAVRAS DA MÁSCARA, e cada uma é um jeito de perguntar a mesma coisa ao
#: estado. `flavor` é o sabor da máscara (`xbox360`, `xboxone`); `native_mode` e
#: `gamepad_emulation_enabled` são as duas chaves do daemon.
PALAVRAS_DA_MASCARA = (
    "native_mode",
    "gamepad_emulation_enabled",
    "flavor",
    "mascara",
)

def _codigo_com_a_palavra(arquivo: str) -> list[tuple[int, str]]:
    """As palavras da máscara no CÓDIGO — nunca em comentário ou docstring.

    POR AST, E A RAZÃO FOI MEDIDA AO ESCREVER ESTA RÉGUA (05/09/2026): a
    primeira versão lia linha a linha e reprovou a si mesma, porque o
    `canal_do_microfone.py` **cita o documento do princípio** —
    `A-MASCARA-NAO-CUSTA-FEATURE…md` — no próprio cabeçalho. Uma régua que
    confunde a palavra com o ato é a doença que esta casa tem nome para, e aqui
    ela apareceu na primeira execução.

    Então o que se mede é: nome de variável, nome de atributo, e string que
    CHEGA AO CÓDIGO — a chave de um `state.get("native_mode")`, por exemplo. A
    prosa que EXPLICA por que a máscara não entra continua livre para dizer a
    palavra, que é o que se quer: o comentário sobre bits do `luz_do_mic` deixou
    de precisar de isenção, e a lista de isenções morreu com ele.
    """
    caminho = SRC / arquivo
    # RÉGUA QUE MEDE ARQUIVO QUE NÃO EXISTE DÁ VERDE SOBRE NADA.
    assert caminho.exists(), f"{arquivo} sumiu — o caminho do microfone mudou?"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
        and isinstance(no.body[0].value.value, str)
    }

    achadas: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            alvo = no.id
        elif isinstance(no, ast.Attribute):
            alvo = no.attr
        elif isinstance(no, ast.arg):
            alvo = no.arg
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            if id(no) in docstrings:
                continue
            alvo = no.value
        else:
            continue
        baixa = alvo.lower()
        if any(p in baixa for p in PALAVRAS_DA_MASCARA):
            achadas.append((getattr(no, "lineno", 0), alvo[:80]))
    return sorted(set(achadas))


@pytest.mark.parametrize("arquivo", O_CAMINHO)
def test_a_mascara_nao_aparece_no_caminho_do_microfone(arquivo: str) -> None:
    """Nenhuma das quatro palavras da máscara, em nenhum dos sete arquivos.

    A MORDIDA: escreva `if not state.get("native_mode"): return None` em
    qualquer um deles e esta régua nomeia o arquivo e a linha.
    """
    achadas = _codigo_com_a_palavra(arquivo)
    assert not achadas, (
        f"a máscara chegou ao caminho do microfone, em {arquivo}:\n  "
        + "\n  ".join(f"{n}: {texto}" for n, texto in achadas)
        + "\n\nA decisão dela (05/09/2026) é que a máscara NÃO custa feature: "
        "'Usaríamos essa feature do controle mesmo no Xbox'. Um gate aqui faz o "
        "microfone sumir quando ela liga a máscara, e o sintoma se lê como "
        "'este controle não tem microfone'."
    )


def test_a_regua_le_codigo_e_nao_prosa() -> None:
    """A régua de si mesma: a palavra na PROSA não pode reprovar.

    Ela nasceu reprovando o próprio módulo do canal, que cita o documento do
    princípio no cabeçalho. Se alguém trocar o AST por uma varredura de linhas,
    esta asserção reprova antes de a próxima pessoa perder meia hora achando que
    o produto ganhou um gate de máscara.
    """
    canal = SRC / "integrations/canal_do_microfone.py"
    bruto = canal.read_text(encoding="utf-8").lower()
    assert "mascara" in bruto, (
        "o módulo do canal deixou de citar o documento do princípio — se a "
        "prosa mudou, esta régua perdeu o caso que ela guarda")
    assert _codigo_com_a_palavra("integrations/canal_do_microfone.py") == [], (
        "a régua voltou a medir prosa")


def test_o_produto_ja_afirma_isto_na_tela() -> None:
    """A frase de preço da máscara promete o microfone — e a promessa tem dono.

    Se um dia alguém puser o gate no caminho, esta frase vira mentira na tela
    dela. As duas coisas têm de cair juntas ou ficar juntas.
    """
    texto = (SRC / "app/actions/home_actions.py").read_text(encoding="utf-8")
    assert "microfone e alto-falante continuam funcionando" in texto, (
        "a frase que promete o microfone sob a máscara mudou de forma — "
        "confira se ela ainda promete, e ajuste esta régua junto")
