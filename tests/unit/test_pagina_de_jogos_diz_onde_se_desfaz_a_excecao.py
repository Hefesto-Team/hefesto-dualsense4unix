"""A página que ela lê não pode voltar a negar o botão de desfazer.

Defeito de origem: até 07/08/2026 a marca do Steam Input era mesmo de mão única
— a função que desmarca (`remove_appid_from_steam_input_allowlist`) tinha ZERO
chamadores em `src/`, e por isso os textos do produto AVISAVAM que não havia
volta. Nesse dia, por decisão dela, a volta nasceu em dois lugares: a caixinha
`profile_steam_input_check` no editor da aba Perfis, e o subcomando
`gamepad steam-input remove`.

O aviso caducou, mas frase antiga sobrevive em página — foi o que a varredura de
11/08 achou nesta mesma página, com a promessa de perda de co-op. Este arquivo
existe para que a negação do desfazer não faça o mesmo caminho.

Os casos não comparam o texto com uma constante: eles conferem que o alvo citado
EXISTE. A caixinha é lida do `gui/main.glade`; os subcomandos são lidos dos
decoradores `@app.command(...)` do `cli/cmd_steam.py`. Assim uma renomeação de
rótulo ou de subcomando também reprova, em vez de passar calada.

A MORDIDA, provada em 21/08/2026
================================
Trocada a frase do desfazer por *"não há como desfazer"*,
`test_a_pagina_nao_nega_o_desfazer` reprova nomeando a linha. Apagado o nome da
caixinha do parágrafo, `test_a_pagina_aponta_a_caixinha_que_existe_na_janela`
reprova. Trocado `remove` por um subcomando inventado,
`test_a_pagina_cita_comandos_que_existem` reprova. Desfeitas, verde.
"""
from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_PAGINA = Path("docs/usage/jogos-e-mascaras.md")
_GLADE = _RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
_CMD_STEAM = _RAIZ / "src" / "hefesto_dualsense4unix" / "cli" / "cmd_steam.py"

#: A negação que caducou em 07/08/2026. Procurada só FORA de bloco de citação:
#: uma nota datada que cite o aviso antigo para explicar o que mudou é o que a
#: casa manda escrever.
_NEGACAO = re.compile(
    r"(não (há|existe|tem) (como |jeito de |botão |maneira de )?desfaz"
    r"|não dá para desfaz"
    r"|sem como desfazer"
    r"|irreversível)",
    re.IGNORECASE,
)

#: Os comandos citados na página, como `gamepad steam-input <sub>`.
_COMANDO_CITADO = re.compile(r"gamepad steam-input (\w[\w-]*)")


def _texto() -> str:
    return (_RAIZ / _PAGINA).read_text(encoding="utf-8")


def _linhas_fora_de_citacao(texto: str) -> list[tuple[int, str]]:
    """As linhas que afirmam por conta própria, sem as de bloco `>`."""
    return [
        (n, ln)
        for n, ln in enumerate(texto.splitlines(), start=1)
        if not ln.lstrip().startswith(">")
    ]


def _rotulo_da_caixinha() -> str:
    """O rótulo vivo do `profile_steam_input_check`, lido do glade."""
    raiz = ET.parse(_GLADE).getroot()
    caixa = next(
        (
            obj
            for obj in raiz.iter("object")
            if obj.get("id") == "profile_steam_input_check"
        ),
        None,
    )
    assert caixa is not None, (
        "o `profile_steam_input_check` sumiu do glade: se a caixinha do desfazer "
        "foi removida, a página de uso volta a mentir e esta é a hora de decidir"
    )
    rotulo = caixa.find("./property[@name='label']")
    assert rotulo is not None and rotulo.text, "a caixinha do desfazer ficou sem rótulo"
    return rotulo.text


def _subcomandos_do_steam_input() -> set[str]:
    """Os `@app.command("x")` do `cli/cmd_steam.py`, sem importar typer."""
    arvore = ast.parse(_CMD_STEAM.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        for dec in no.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            alvo = dec.func
            if not (isinstance(alvo, ast.Attribute) and alvo.attr == "command"):
                continue
            if dec.args and isinstance(dec.args[0], ast.Constant):
                nomes.add(str(dec.args[0].value))
            else:
                nomes.add(no.name.removeprefix("cmd_"))
    return nomes


def test_a_pagina_nao_nega_o_desfazer() -> None:
    """Nenhuma linha afirmativa pode dizer que a marca é de mão única."""
    achados = [
        f"{_PAGINA}:{n}: {ln.strip()[:90]}"
        for n, ln in _linhas_fora_de_citacao(_texto())
        if _NEGACAO.search(ln)
    ]
    assert not achados, (
        "a página diz que não há como desfazer a exceção do Steam Input. Isso "
        "caducou em 07/08/2026: a caixinha `profile_steam_input_check` da aba "
        "Perfis e o `gamepad steam-input remove` tiram a marca.\n" + "\n".join(achados)
    )


def test_a_pagina_aponta_a_caixinha_que_existe_na_janela() -> None:
    """E diz onde: a aba, e o rótulo exato que a janela mostra hoje.

    NOTA DATADA — 28/08/2026 (S4). Este caso pegava *o primeiro* parágrafo fora
    de citação que trouxesse o rótulo, e cobrava dele "Perfis" e "Jogo da
    Steam". Amarrar a régua à ORDEM do texto a fez reprovar a S4, que
    acrescentou ACIMA do parágrafo do desfazer outro que cita a mesma caixinha
    — para dizer que não é mais preciso marcar. Reprovar quem escreve um
    parágrafo novo não é medir a página. A pergunta certa é se a página ENSINA
    o desfazer em ALGUM lugar, e é essa que ela faz agora.
    """
    texto = _texto()
    rotulo = _rotulo_da_caixinha()
    assert rotulo in texto, (
        f"a página não cita o rótulo vivo da caixinha do desfazer ({rotulo!r}). "
        "Quem lê precisa achá-la na tela pelo nome que está escrito nela"
    )
    candidatos = [
        p for p in texto.split("\n\n") if rotulo in p and not p.startswith(">")
    ]
    assert candidatos, "o parágrafo do desfazer virou bloco de citação"
    assert any("Perfis" in p for p in candidatos), (
        f"a página não diz em que aba a caixinha mora: {candidatos!r}"
    )
    assert any("Perfis" in p and "Jogo da Steam" in p for p in candidatos), (
        "a página não diz que a caixinha só aparece com 'Jogo da Steam' escolhido "
        "— sem isso, quem abrir o editor num perfil comum não a acha e conclui "
        f"que ela não existe. Parágrafos que citam a caixinha: {candidatos!r}"
    )


def test_a_pagina_cita_comandos_que_existem() -> None:
    """Os dois comandos de CLI da página têm de existir no `cmd_steam.py`."""
    citados = set(_COMANDO_CITADO.findall(_texto()))
    reais = _subcomandos_do_steam_input()
    assert citados, "a página parou de citar o caminho de linha de comando"
    inventados = citados - reais
    assert not inventados, (
        f"a página manda rodar subcomando que não existe: {sorted(inventados)}; "
        f"o `gamepad steam-input` tem {sorted(reais)}"
    )
    assert {"list", "remove"} <= citados, (
        "a página tem de citar os DOIS: `list` para descobrir o que está marcado "
        f"e `remove` para tirar a marca. Cita {sorted(citados)}"
    )
