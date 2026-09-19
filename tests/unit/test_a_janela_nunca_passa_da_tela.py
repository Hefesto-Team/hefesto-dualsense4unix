"""A `.janela` nunca é mais alta que a vista — o rodapé não sai pela borda.

A QUEIXA DELA — 19/09/2026, com a janela LADRILHADA ao lado do terminal: os
quatro botões do rodapé (Aplicar · Salvar Perfil · Importar · Exportar) cortados
ao meio pela borda de baixo. *"tem esse outro bug aqui"*
<!-- noqa-acento: citação literal dela -->

O NÚMERO É EXATO, e foi medido antes da cura: a altura é
``clamp(--piso-da-vista, 100dvh - recuo*2, --teto-da-vista)``, com piso de
777 px e recuo de 16 — logo **809** é o ponto de virada. Acima dele a janela
encolhe junto com a vista e nada se perde; abaixo ela TRAVA em 777 e passa da
viewport:

==========  ==================  =====================
vista       altura da `.janela`  rodapé fora da tela
==========  ==================  =====================
1200x809    777                 0
1200x790    777                 **19 px**
1200x760    777                 **49 px**
1200x700    777                 **109 px**
==========  ==================  =====================

A CURA É UMA LINHA, e usa o que já existia: `max-height:calc(100dvh - recuo*2)`
na `.janela`. O `.miolo` já é ``flex:1; min-height:0; overflow-y:auto`` e rola
por dentro; o `.rodape` é irmão dele, colado no fim. Limitar a janela faz o
miolo absorver a diferença.

**UMA CURA ANTERIOR FOI DESCARTADA POR ESTA MEDIÇÃO, e o registro fica porque
custou:** a primeira tentativa pôs `overflow-y:auto` no `body`. Medida lado a
lado com a página sem cura, deu **exatamente o mesmo resultado** — a página já
rolava (a legenda mora abaixo da `.janela`) e o rodapé já era alcançável
rolando. *Régua que não separa a cura do nada é o instrumento falso que esta
casa mais pega* — e aqui ela pegou a minha antes de a cura ser entregue.

ONDE ELA MORDE: tire o `max-height` da `.janela` no `interface/topo.html`, rode
os dez geradores, e as vistas estreitas voltam a empurrar o rodapé para fora.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import onde

#: AS VISTAS QUE IMPORTAM, e as três estreitas são as que ela produz ao
#: ladrilhar: o COSMIC dá à janela menos altura que o piso pedido em código —
#: *"o COSMIC que ladrilha não o lê"*, medido em 13/09/2026. Por isso a cura é
#: da TELA e não do Python: o gesto é dela e não vai ser revogado.
VISTAS = (900, 809, 790, 760, 700)

#: O RECUO DO CORPO, que entra DUAS vezes na conta. Lido da folha, nunca
#: digitado: um número copiado aqui apodrece na primeira mudança do desenho.
_RECUO = re.compile(r"--recuo-do-corpo:\s*(\d+)px")


def _folha() -> str:
    return (pathlib.Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/interface/topo.html").read_text(encoding="utf-8")


def test_a_folha_ainda_declara_o_recuo() -> None:
    """A premissa da conta. Sem ela, o resto mede o próprio palpite."""
    assert _RECUO.search(_folha()), (
        "`--recuo-do-corpo` sumiu da folha comum — a conta da altura da janela "
        "mudou de forma, e esta régua está medindo o mundo de ontem")


def test_a_janela_tem_teto_de_vista() -> None:
    """O `max-height` existe e é calculado a partir da vista, não fixo.

    MORDE: troque por um número em pixels e a janela volta a passar da tela na
    vista que for menor que ele.
    """
    folha = _folha()
    assert re.search(
        r"\.janela\{[^}]*max-height:\s*calc\(\s*100dvh\s*-\s*var\(--recuo-do-corpo\)\s*\*\s*2\s*\)",
        folha, re.S), (
        "a `.janela` perdeu o teto de vista: sem ele, toda vista abaixo de 809 px "
        "empurra o rodapé para fora da tela, e os quatro botões de ação ficam "
        "inalcançáveis sem rolar")


@pytest.mark.parametrize("aba", [p.name for p in onde.paginas()])
def test_toda_aba_carrega_o_teto(aba: str) -> None:
    """As DEZ, e não só a que se olhou.

    A folha é comum, mas quem a injeta é o gerador de cada aba — e uma aba que
    não tenha sido regerada fica com a folha velha. Foi assim que a `aba06`
    divergiu calada em 01/09/2026.
    """
    doc = onde.pagina(aba).read_text(encoding="utf-8")
    # SÓ QUEM TEM `.janela`, e o critério é o FATO e não o nome do arquivo. As
    # telas auxiliares (`mapa-do-controle`, `mapa-das-portas`,
    # `calibrar-sensores`) têm layout próprio e nenhuma `.janela` — cobrar delas
    # o teto seria a régua reprovando o que não existe. Quem nascer com
    # `.janela` amanhã entra nesta conta sozinho, que é o ponto de medir assim.
    if 'class="janela"' not in doc:
        pytest.skip(f"{aba} não usa a `.janela` — tela auxiliar")
    assert "max-height:calc(100dvh - var(--recuo-do-corpo) * 2)" in doc, (
        f"{aba} está com a folha VELHA — rode o gerador dela. Sem o teto, a "
        f"janela estreita corta o rodapé desta aba")
