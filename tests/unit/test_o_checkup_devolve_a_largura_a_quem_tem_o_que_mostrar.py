"""O Check-up fica com a parte maior, e com TUDO quando não há ordem de serviço.

CHECKUP-VAO-01 — decisão dela, 19/09/2026:

    *"falta deixarmos a área sempre disponível pra ocupar o espaço vazio do
    checkup mesmo sem mostrar nada"*  ·  *"aumenta a largura aqui e resume mais
    pra ter uma linha só"*

**MEDIDO NO NAVEGADOR**, com o achado mais longo do produto injetado nas cinco
linhas, contando quantas ocupam DUAS linhas:

    =========  ===========  =========  ====================  ==============
    janela     ordem?       coluna     frase de 111 (antes)  de 90 (depois)
    =========  ===========  =========  ====================  ==============
    1600 px    com          927 px     0 de 5                0 de 5
    1200 px    com          676 px     **5 de 5**            0 de 5
     940 px    com          512 px     5 de 5                5 de 5
    1200 px    **sem**     1100 px     —                     0 de 5
     940 px    **sem**      840 px     —                     0 de 5
     820 px    **sem**      720 px     —                     0 de 5
    =========  ===========  =========  ====================  ==============

O resumo ganhou a faixa dos 1200; o alargamento ganhou a dos 940 **quando a
coluna da direita está vazia**, que é o caso que ela fotografou. Com ordem de
serviço a 940 px ainda quebra, e isso está declarado: 90 caracteres não cabem em
512 px a 12 px de fonte, e encurtar mais custaria sentido.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
EXAME = RAIZ / "src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"

#: O teto que a medição sustenta. 90 é a maior frase que sobrou; o folgado é
#: para a próxima pessoa não precisar remedir ao acrescentar um achado.
TETO_DA_FRASE = 100

REGRAS = (
    ".duas-colunas:has(.col-exame){grid-template-columns:1.7fr 1fr}",
    ".duas-colunas:has(.col-exame):has(.col-ordem:empty){grid-template-columns:1fr}",
    ".duas-colunas:has(.col-exame):has(.col-ordem:empty) > .lado-d{display:none}",
)


@pytest.mark.parametrize("regra", REGRAS)
def test_o_gerador_traz_as_tres_regras(regra: str) -> None:
    assert regra in GERADOR.read_text(encoding="utf-8"), (
        "sem esta regra a coluna do exame volta à metade exata, e o achado "
        "mais longo quebra em duas linhas a partir de 1200 px"
    )


@pytest.mark.parametrize("regra", REGRAS)
def test_a_pagina_publicada_traz_as_tres(regra: str) -> None:
    """Curar o gerador e não publicar deixa a tela dela igual."""
    if not PAGINA.exists():  # pragma: no cover — árvore sem a página publicada
        pytest.skip(f"{PAGINA.name} não está publicada nesta árvore")
    assert regra in PAGINA.read_text(encoding="utf-8"), (
        "falta `check_o_desenho_aprovado.py --publicar 08`"
    )


def frases_do_exame() -> list[str]:
    fonte = EXAME.read_text(encoding="utf-8")
    achadas = []
    for bloco in re.finditer(r'porque=\(?\s*((?:f?"[^"]*"\s*)+)\)?', fonte):
        achadas.append("".join(re.findall(r'"([^"]*)"', bloco.group(1))))
    return achadas


def test_ha_frases_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada."""
    assert len(frases_do_exame()) >= 15, "o extrator perdeu as frases do exame"


def test_nenhuma_frase_do_exame_passa_do_teto() -> None:
    """*"resume mais pra ter uma linha só"* — a ordem dela, virada número.

    A MORDIDA: devolver qualquer uma das seis frases encurtadas em 19/09 faz
    esta régua reprovar. A pior tinha 129 caracteres.
    """
    longas = [f for f in frases_do_exame() if len(f) > TETO_DA_FRASE]
    assert not longas, "\n".join(
        f"  {len(f)} caracteres: {f}" for f in longas
    ) + (
        f"\n\n{len(longas)} frase(s) acima de {TETO_DA_FRASE} — elas quebram a "
        "linha do achado, que é o que a CHECKUP-VAO-01 veio fechar"
    )
