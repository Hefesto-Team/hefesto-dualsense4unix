"""A tabela de `COMO-OLHAR-A-TELA.md` envelheceu calada — CINCO-SCRIPTS-01.

`docs/process/COMO-OLHAR-A-TELA.md` é o arquivo que o `CLAUDE.md` manda ler
**primeiro** quando o trabalho toca a tela. Ele trazia uma seção chamada
"Os três scripts desta pasta, e qual usar", com uma tabela de três linhas —
enquanto `ls scripts/gui-captura/` devolvia **cinco** arquivos.

E o que faltava não era detalhe: faltava o `retratar_dialogos.py`, cujas
imagens o `docs/usage/interface.md` **já publica**. Quem chegasse pelo guia
não descobriria que existe maneira de fotografar diálogo, e a leva seguinte
pagaria de novo o preço que a `DIALOGO-QUE-MATA-A-JANELA-01` já pagou.

A MORDIDA
---------

Apagando uma linha da tabela (ou acrescentando um script à pasta sem
acrescentá-lo ali), este teste reprova NOMEANDO o arquivo que ficou de fora. Foi
exatamente por não existir portão nenhum que a tabela pôde ficar dois scripts
atrasada sem ninguém notar.

Por que o teste olha a PASTA, e não uma lista escrita aqui: uma lista neste
arquivo seria um terceiro dono do fato, e envelheceria pelo mesmo motivo que a
tabela envelheceu.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "scripts" / "gui-captura"
GUIA = RAIZ / "docs" / "process" / "COMO-OLHAR-A-TELA.md"

#: As extensões que fazem de um arquivo desta pasta um SCRIPT. Qualquer coisa
#: fora disto (um `README.md`, um dado de apoio) não é ferramenta e não entra
#: na tabela.
_EXTENSOES = (".py", ".sh")


def _scripts_da_pasta() -> set[str]:
    assert PASTA.is_dir(), f"{PASTA} sumiu — é a pasta das ferramentas de tela"
    return {
        caminho.name
        for caminho in PASTA.iterdir()
        if caminho.is_file() and caminho.suffix in _EXTENSOES
    }


def _tabela_do_guia() -> str:
    """O bloco da tabela — as linhas que começam com `|`."""
    assert GUIA.is_file(), f"{GUIA} sumiu — é o primeiro arquivo a ler nesta casa"
    texto = GUIA.read_text(encoding="utf-8")
    return "\n".join(
        linha for linha in texto.splitlines() if linha.lstrip().startswith("|")
    )


def test_a_tabela_nomeia_todo_script_da_pasta() -> None:
    """Script na pasta e ausente da tabela = ferramenta que ninguém acha."""
    tabela = _tabela_do_guia()
    faltando = sorted(nome for nome in _scripts_da_pasta() if nome not in tabela)

    assert not faltando, (
        f"{', '.join(faltando)} está em `scripts/gui-captura/` e NÃO aparece na "
        "tabela de `docs/process/COMO-OLHAR-A-TELA.md`. Este é o arquivo que o "
        "`CLAUDE.md` manda ler primeiro quando o trabalho toca a tela: uma "
        "ferramenta fora dele é uma ferramenta que a próxima pessoa não vai "
        "usar, e o trabalho que ela evita será refeito à mão."
    )


def test_a_tabela_nao_nomeia_script_que_nao_existe() -> None:
    """O outro lado: linha sobrevivente de script apagado manda a pessoa ao vazio."""
    tabela = _tabela_do_guia()
    da_pasta = _scripts_da_pasta()
    citados = set(re.findall(r"[\w.-]+\.(?:py|sh)", tabela))
    fantasmas = sorted(nome for nome in citados if nome not in da_pasta)

    assert not fantasmas, (
        f"a tabela de `docs/process/COMO-OLHAR-A-TELA.md` cita {', '.join(fantasmas)}, "
        "que não existe em `scripts/gui-captura/`."
    )


def test_o_titulo_da_secao_diz_o_numero_certo() -> None:
    """"Os três scripts desta pasta" com cinco no disco foi como isto começou."""
    texto = GUIA.read_text(encoding="utf-8")
    quantos = len(_scripts_da_pasta())
    por_extenso = {
        3: "três",
        4: "quatro",
        5: "cinco",
        6: "seis",
        7: "sete",
        8: "oito",
    }.get(quantos)

    titulos = [
        linha
        for linha in texto.splitlines()
        if linha.startswith("## ") and "scripts desta pasta" in linha
    ]
    assert titulos, (
        "a seção que apresenta os scripts de tela sumiu de "
        "`docs/process/COMO-OLHAR-A-TELA.md`."
    )
    assert por_extenso is not None, (
        f"a pasta passou a ter {quantos} scripts e este teste não sabe escrever "
        "esse número por extenso — acrescente-o ao mapa acima."
    )

    titulo = titulos[0]
    assert por_extenso in titulo, (
        f"o título diz {titulo.strip('# ').strip()!r}, e a pasta tem {quantos} "
        f"scripts ({por_extenso}). Um número errado no primeiro arquivo que se "
        "manda ler é pior que número nenhum: ele faz quem chega parar de "
        "procurar depois do terceiro."
    )
