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
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_PAGINA = Path("docs/usage/jogos-e-mascaras.md")
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
