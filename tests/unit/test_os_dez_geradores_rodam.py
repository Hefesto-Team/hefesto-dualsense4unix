#!/usr/bin/env python3
"""A RÉGUA DA BANCADA: os dez geradores RODAM, e o que sai é o desenho de hoje.

POR QUE ELA NASCEU, e o número é o argumento: em 01/09/2026, medidos um a um,
**os DEZ estavam quebrados**. Nenhum rodava. E ninguém sabia.

O que os quebrou foi um commit só — `6f7e0119`, o que mudou a interface de
`layout/` para dentro de `src/`. Ele levou três coisas junto:

  * `monta.R` passou de "a raiz do repositório" para "a pasta deste módulo", e
    com ela `assets/glyphs/` e `docs/data/` foram procurados dentro de
    `interface/`. Seis geradores morreram em `FileNotFoundError`;
  * `player_slot_color` saiu do bloco de import do `monta.py` no caminho. Quatro
    geradores morreram em `ImportError`;
  * `aba08` e `aba09` mantiveram um `parents[2]` próprio, que virou `src/`.

POR QUE PORTÃO NENHUM VIU, e é a parte que importa para quem herdar isto: o
`check_o_desenho_aprovado.py` compara **dois arquivos parados** — a bancada e o
publicado. Se o gerador não roda, os dois continuam iguais, e ele fica verde
para sempre sobre uma bancada que ninguém consegue mais reproduzir. É o mesmo
buraco que deixou a `novo-layout/` divergir 25 KB calada, com outra roupa.

O QUE ELA COBRA, e são duas coisas separadas:

1. **RODAR.** Cada gerador termina sem exceção. Isto sozinho teria acusado os
   dez no dia em que caíram.
2. **REPRODUZIR.** O que sai é byte a byte o que está em `mockup/`. Sem isto, um
   gerador editado e nunca rodado deixa a bancada para trás — e a próxima pessoa
   que o rodar leva um diff que não fez.

O SEGUNDO ACHOU UM DEFEITO VISÍVEL no mesmo dia: `aba03.py` tinha o marcador
`# (noqa-acento)` DENTRO de uma f-string, e as quatro colunas da aba Gatilhos
nasciam com `# noqa-acento` como TEXTO no topo, em letra de título. Está na foto
de 01/09.

ONDE ELA ESCREVE: num diretório temporário, pelo `HEFESTO_BANCADA`. Ela **não
toca** a bancada dela — que é a razão de aquele desvio existir.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(RAIZ / "src"))

#: OS GERADORES, DERIVADOS DO DISCO — nunca uma lista escrita aqui. O gerador
#: número onze nasce coberto, e nenhuma frente precisa lembrar de vir avisar
#: este arquivo. É a mesma disciplina do `_DECORADORES_DE_FRAMEWORK`.
GERADORES = sorted(p.name for p in INTERFACE.glob("aba[0-9][0-9].py"))


def test_os_geradores_existem() -> None:
    """Zero geradores é ERRO, não silêncio — senão os casos abaixo passam vazios."""
    assert len(GERADORES) >= 10, (
        f"achei {len(GERADORES)} geradores em {INTERFACE}, e as dez abas têm um "
        f"cada: {GERADORES}. Se o padrão do `glob` deixou de casar, esta régua "
        f"inteira fica verde sem medir nada.")


@pytest.fixture(scope="module")
def bancada_de_prova(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Uma bancada de mentira, com as páginas de hoje dentro.

    AS PÁGINAS VÃO JUNTO porque alguns geradores CONFEREM a vizinhança: o
    `aba02` recusa se o `mapa-do-controle.html` não estiver ao lado, e está
    certo — um botão que aponta para página inexistente é um botão que mente.
    Uma pasta vazia faria este caso reprovar por um motivo que não é o dele.
    """
    destino = tmp_path_factory.mktemp("bancada")
    for p in (RAIZ / "mockup").glob("*.html"):
        shutil.copy2(p, destino / p.name)
    return destino


def _rodar(nome: str, destino: pathlib.Path) -> subprocess.CompletedProcess[str]:
    ambiente = dict(os.environ)
    # O DESVIO DA ESCRITA (`interface/onde.py`). Sem ele o gerador escreveria na
    # bancada DELA, e uma régua que muda o que mede não é régua.
    ambiente["HEFESTO_BANCADA"] = str(destino)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    return subprocess.run(
        [sys.executable, str(INTERFACE / nome)],
        capture_output=True, text=True, timeout=180, env=ambiente, cwd=str(RAIZ),
    )


@pytest.mark.parametrize("nome", GERADORES)
def test_o_gerador_roda(nome: str, bancada_de_prova: pathlib.Path) -> None:
    """Ele termina sem exceção. É o degrau que os dez perderam em 01/09/2026."""
    r = _rodar(nome, bancada_de_prova)
    assert r.returncode == 0, (
        f"`{nome}` não roda:\n{r.stderr.strip()[-1200:]}\n\n"
        f"A BANCADA É A FONTE DO DESENHO. Um gerador que não roda congela a aba "
        f"dele: o `check_o_desenho_aprovado` continua verde comparando dois "
        f"arquivos parados, e ninguém consegue mais mudar aquela tela.")


@pytest.mark.parametrize("nome", GERADORES)
def test_o_gerador_reproduz_a_bancada(nome: str, bancada_de_prova: pathlib.Path) -> None:
    """O que sai é, byte a byte, o `mockup/` que está no disco.

    A DIFERENÇA ENTRE ESTE CASO E O DE CIMA é o defeito que cada um pega: o de
    cima pega o gerador MORTO, este pega o gerador EDITADO E NUNCA RODADO — e os
    dois aconteceram. O segundo é o que revelou, em 01/09/2026, que a aba
    Gatilhos mostrava `# noqa-acento` como texto no topo das quatro colunas.
    """
    r = _rodar(nome, bancada_de_prova)
    if r.returncode != 0:
        pytest.skip(f"{nome} não roda — quem acusa isso é o caso irmão")

    saiu = sorted(p for p in bancada_de_prova.glob("*.html")
                  if p.name.startswith(nome[3:5]))
    assert saiu, (
        f"`{nome}` rodou e não escreveu página nenhuma que comece com "
        f"{nome[3:5]!r}. O desvio `HEFESTO_BANCADA` deixou de valer, e este "
        f"caso passaria por AUSÊNCIA — o modo mais silencioso de um teste "
        f"deixar de medir.")
    for gerado in saiu:
        na_bancada = RAIZ / "mockup" / gerado.name
        assert na_bancada.exists(), f"{gerado.name} saiu do gerador e não está em mockup/"
        assert gerado.read_bytes() == na_bancada.read_bytes(), (
            f"`{nome}` produz um {gerado.name} DIFERENTE do que está em "
            f"`mockup/`. O gerador foi editado e nunca rodado — a bancada ficou "
            f"para trás, e a próxima pessoa que o rodar leva um diff que não "
            f"fez.\nRODE `python3 src/hefesto_dualsense4unix/interface/{nome}` e "
            f"olhe o `git diff mockup/`.")


def test_nenhuma_pagina_publicada_carrega_marcador_de_lint(monkeypatch) -> None:
    """`# noqa` não é conteúdo de tela — e já foi, em letra de título.

    MEDIDO em 01/09/2026: `aba03.py` tinha `# (noqa-acento) id` dentro de uma
    f-string de várias linhas, logo depois de `data-conectado="{...}">`. O
    marcador saía do lado de fora da tag, virava TEXTO, e as quatro colunas da
    aba Gatilhos abriam com `# noqa-acento` escrito no topo.

    O marcador tem de ficar na MESMA linha física da palavra que ele isenta —
    então a cura não é tirá-lo: é tirar o VALOR da f-string, calculá-lo numa
    linha de código, e marcar essa linha.

    ELE CONTINUA VALENDO DENTRO DE COMENTÁRIO. As três aparições em
    `01-jogar.html` e a de `10-perfis.html` moram dentro de `/* … */` e de
    `<!-- … -->`, e não chegam aos olhos — recusá-las seria a régua brigando com
    quem documenta o CSS.
    """
    import re

    from hefesto_dualsense4unix.interface import onde

    fora: list[str] = []
    for pagina in sorted(onde.PUBLICADO.glob("[0-9][0-9]-*.html")):
        texto = pagina.read_text(encoding="utf-8")
        # Tira os dois tipos de comentário ANTES de procurar: o que sobra é o
        # que a página mostra.
        visivel = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
        visivel = re.sub(r"/\*.*?\*/", "", visivel, flags=re.S)
        for linha in visivel.splitlines():
            if "noqa" in linha:
                fora.append(f"{pagina.name}: {linha.strip()[:100]}")
    assert not fora, (
        "há marcador de lint FORA de comentário nas páginas publicadas — ele "
        "chega aos olhos de quem abre a aba:\n  " + "\n  ".join(fora) +
        "\nA cura é tirar o valor da f-string do gerador e marcar a linha de "
        "código que o calcula, não a linha de dentro do texto.")
