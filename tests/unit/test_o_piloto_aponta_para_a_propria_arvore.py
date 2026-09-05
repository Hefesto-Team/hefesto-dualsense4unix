"""A aritmética de caminho dos instrumentos, e o `rc` que não pode mentir.

DOIS DEFEITOS MEDIDOS EM 04/09/2026, e os dois estavam vivos há tempo:

1. **`RAIZ = AQUI.parents[1]` estava errado por um.** Com `AQUI` em
   `<árvore>/src/hefesto_dualsense4unix/interface`, `parents[1]` é o **`src`** —
   não a árvore. Logo `RAIZ / "src"` resolvia para `<árvore>/src/src`, que não
   existe. Duas consequências, as duas caladas:

   - o `sys.path.insert` virava no-op, e o piloto rodado à mão importava o
     produto de OUTRA árvore pelo `.pth` do editable install. É o
     `SRC-DESTA-ARVORE-01` pela TERCEIRA porta — a suíte e os portões já
     tinham sido curados no mesmo dia, e o script à mão não;
   - `sistema_viva.PAGINA` e `controles_vivos.PAGINA` apontavam para um HTML
     inexistente.

   É a assinatura de 03/09 de novo: **as pastas mudaram de nome e a aritmética
   não foi junto.** Estes arquivos nasceram em `novo-layout/_ferramentas/`,
   onde `parents[1]` ERA a árvore.

2. **`--prova-de-mockup` imprimia `ERRO DE CARGA` e saía `rc=0` sem medir uma
   aba.** Quem a chamasse num portão leria VERDE sobre o vazio. A causa era uma
   corrida — a régua navegava antes de a carga inicial confirmar — e o estrago
   era a forma de sair, não a corrida.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: Os arquivos que calculam a árvore a partir de si mesmos.
_COM_RAIZ = ("hefesto_vivo.py", "controles_vivos.py", "sistema_viva.py", "casamento.py")


@pytest.mark.parametrize("nome", _COM_RAIZ)
def test_a_raiz_calculada_e_a_arvore_e_nao_o_src(nome: str) -> None:
    """A METADE QUE MEDE: a conta é REFEITA aqui, não lida no texto."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r"^RAIZ = AQUI\.parents\[(\d)\]", fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da RAIZ"
    nivel = int(m.group(1))

    aqui = INTERFACE
    raiz = aqui.parents[nivel]
    assert (raiz / "src").is_dir(), (
        f"{nome}: `AQUI.parents[{nivel}] / 'src'` dá {raiz / 'src'}, que NÃO "
        "EXISTE. Com `[1]` a conta cai no próprio `src` e o `RAIZ / \"src\"` "
        "vira `src/src` — o defeito de 04/09/2026."
    )
    assert raiz == RAIZ, f"{nome}: a RAIZ calculada ({raiz}) não é a árvore"


@pytest.mark.parametrize("nome", ("controles_vivos.py", "sistema_viva.py"))
def test_a_pagina_que_o_instrumento_abre_existe_no_disco(nome: str) -> None:
    """E o efeito visível do erro: um HTML que não está lá."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r'^PAGINA = RAIZ / "src" / (.+?)(?:  #|$)', fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da PAGINA"
    pedacos = [p.strip().strip('"') for p in m.group(1).split(" / ")]
    caminho = RAIZ / "src"
    for p in pedacos:
        caminho = caminho / p
    assert caminho.is_file(), (
        f"{nome}: `PAGINA` aponta para {caminho}, que não existe no disco. "
        "O instrumento abriria o vazio."
    )


def test_a_regua_do_mockup_nao_sai_verde_sobre_o_vazio() -> None:
    """A MORDIDA: sem esta guarda, `ERRO DE CARGA` convivia com `rc=0`."""
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    # A FRASE SOZINHA NÃO BASTA, e a mordida provou: `piloto.tela.morreu is
    # not None` aparece DUAS vezes — na espera da carga e na guarda de saída.
    # Arrancar a guarda deixava a régua verde pela ocorrência da outra. O que
    # se mede é o PAR: a condição de régua e o `SystemExit` que ela dispara.
    assert re.search(
        r"if e_regua and piloto\.tela\.morreu is not None:.*?raise SystemExit\(1\)",
        fonte, re.S,
    ), (
        "o piloto voltou a ignorar a morte da página: uma régua que imprime "
        "`ERRO DE CARGA` e sai `rc=0` é pior que régua nenhuma."
    )
    assert re.search(
        r"if args\.prova_de_mockup and not piloto\.visitadas:.*?raise SystemExit\(1\)",
        fonte, re.S,
    ), (
        "sumiu a guarda do ZERO: `--prova-de-mockup` sem visitar aba nenhuma "
        "tem de REPROVAR. Zero é erro, não silêncio."
    )
    # E a corrida que a causou: a régua espera a PÁGINA, não o relógio.
    assert "if not piloto.tela.na_aba:" in fonte, (
        "a régua voltou a partir de um `timeout` fixo: ela navegava antes de a "
        "carga inicial confirmar, e a confirmação chegava com o título vazio."
    )


def test_a_janela_guarda_o_motivo_da_morte() -> None:
    """A outra metade, no dono: sem o atributo, o piloto não teria o que ler."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "ponte_da_tela.py"
    ).read_text(encoding="utf-8")
    assert "self.morreu: str | None = None" in fonte
    assert "self.morreu = motivo" in fonte
