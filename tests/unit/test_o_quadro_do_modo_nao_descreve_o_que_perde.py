"""O quadro "Modo" não mora mais na aba Perfis — e as duas frases têm dono.

**ESTA RÉGUA INVERTEU EM 11/09/2026, por ordem dela:**

    "em perfis ainda aparece modo. Isso deve aparecer só na aba jogar."

O QUE ELA COBRAVA ANTES, e cobrava certo: o quadro «Modo» nasceu em 06/09
(`PERFIL-MODO-01`) com os quatro botões e **nenhuma** das duas frases que a
janela GTK põe ao lado do modo — decisão 10-Q6 dela, executada pela
`ONDA5-10-03`. Esta régua vigiava o alcance daquele quadro.

**O QUADRO SAIU INTEIRO**, e com ele o gesto que gravava
(`a10_perfis.editor_modo`) e a regra de CSS da fileira. Uma régua que some com o
assunto é dívida; uma régua que inverte com a decisão registrada é o contrato
novo — então o que se cobra aqui agora é a AUSÊNCIA, nas duas páginas, e pelas
quatro marcas que o quadro deixava (o bloco, o atributo do botão, o endereço da
pintura e a regra do CSS). Cada uma pode voltar por um caminho diferente.

**AS DUAS FRASES CONTINUAM CERTAS ONDE ELAS MORAM.** O dono é
`app/actions/home_actions.py`, e esta régua continua perguntando a ele — nunca
digitando o texto. O que ela diz é que elas não pertencem a esta página: nem no
quadro, que saiu, nem fora dele.

**POR QUE A VARREDURA NÃO É A PÁGINA INTEIRA**, e isto não mudou: as palavras
"rádio" e "Xbox 360" aparecem legitimamente noutros pontos da aba 10 (as dicas
do Estilo de Jogo, a tabela da guarda). O que se procura é a FRASE INTEIRA do
dono, que é o que a decisão 10-Q6 baniu desta tela.

A IRMÃ DESTA RÉGUA é
`tests/unit/test_o_quadro_do_modo_grava_no_perfil.py`, e a divisão é de
assunto: aqui a TELA (o quadro não está, e as frases do dono não chegam); lá o
DADO (`Profile.mode` sobrevive à retirada, e o perfil novo nasce sem a seção).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
    texto_do_radio_fragil,
)
from hefesto_dualsense4unix.interface import onde

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: O ESTADO QUE FAZ A FRASE DO RÁDIO NASCER. Ele é o do dono
#: (`home_actions.texto_do_radio_fragil`), e é assim que esta régua obtém a
#: frase sem digitá-la: perguntando ao produto o que ele diria.
_ESTADO_DO_RADIO_FRAGIL = {
    "controllers": [{"uniq": "aabbcc000001", "connected": True, "transport": "bt"}],
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "native_bt_fragil": True,
    "native_mode": {"enabled": True},
}

#: AS QUATRO MARCAS QUE O QUADRO DEIXAVA, e nenhuma é redundante — cada uma
#: volta por um caminho diferente:
#:
#: * o bloco volta num `git revert` do gerador;
#: * o atributo do botão volta se outro controle desta aba reusar o nome — e a
#:   régua de ponteiros da casa (`test_steam_input_ponteiros`) o lê como modo;
#: * o endereço da pintura volta se o pacote for religado;
#: * a regra de CSS volta num `merge` de folha de estilo.
#:
#: O NOME DE CADA UMA NÃO SE ESCREVE EM COMENTÁRIO QUE VIAJE PARA O HTML — este
#: arquivo é `tests/`, não vai para página nenhuma, então aqui pode.
_MARCAS_DO_QUADRO = (
    ('<div class="campo modo">', "o bloco da fileira no editor"),
    ('data-modo="', "o atributo que dizia qual dos quatro"),
    ('data-hef="editor.modo"', "o endereço que o produto pintava"),
    (".campo.modo", "a regra de CSS da fileira"),
)


def _pagina(publicado: bool) -> str:
    return onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")


def _frases_proibidas() -> list[tuple[str, str]]:
    """`(nome da constante, texto)` — perguntados ao DONO, nunca digitados."""
    frases = [("home_actions.TEXTO_CUSTO_MASCARA_XBOX", TEXTO_CUSTO_MASCARA_XBOX)]
    do_radio = texto_do_radio_fragil(_ESTADO_DO_RADIO_FRAGIL)
    if do_radio:
        frases.append(("home_actions.texto_do_radio_fragil", do_radio))
    return frases


def test_as_duas_frases_do_dono_existem_de_verdade() -> None:
    """A régua abaixo só morde se as constantes ainda produzem texto.

    **RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE.** Se o dono passar a devolver
    vazio, a varredura de baixo ficaria verde sem varrer nada — o estado que
    esta casa chama de *verde por vacuidade*, e que já custou um dia aqui.
    """
    frases = _frases_proibidas()
    assert len(frases) == 2, (
        f"esperava as DUAS frases do dono e vi {[n for n, _ in frases]} — "
        "a varredura de baixo ficaria verde sem varrer nada")
    for nome, texto in frases:
        assert len(texto) > 20, f"{nome} encolheu para {texto!r}"


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
@pytest.mark.parametrize("marca,o_que_e", _MARCAS_DO_QUADRO,
                         ids=[m for m, _ in _MARCAS_DO_QUADRO])
def test_o_quadro_do_modo_nao_esta_na_aba_perfis(
    publicado: bool, marca: str, o_que_e: str
) -> None:
    """Ordem dela, 11/09/2026 — e as duas páginas respondem igual.

    AS DUAS E NÃO SÓ A BANCADA: o gerador escreve em `mockup/` e só o
    `--publicar 10` leva ao que o produto renderiza. Uma régua que olhasse só
    uma das duas daria verde sobre a tela que ela NÃO abre — é a armadilha que o
    `onde.pagina` documenta, e ela reincidiu quatro vezes num dia só.
    """
    assert marca not in _pagina(publicado), (
        f"{o_que_e} voltou à aba Perfis ({'publicada' if publicado else 'bancada'}) "
        f"— {marca!r}. O quadro «Modo» saiu do editor por ordem dela em "
        f"11/09/2026: *\"em perfis ainda aparece modo. Isso deve aparecer só na "
        f"aba jogar.\"* Se a decisão mudou, ela muda aqui primeiro."
    )


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_as_duas_frases_do_dono_nao_chegam_a_esta_pagina(publicado: bool) -> None:
    """Decisão 10-Q6 dela, e ela sobrevive à saída do quadro.

    O ALCANCE ERA O QUADRO, e virou a PÁGINA quando o quadro saiu — e pôde
    virar sem falso positivo porque o que se procura é a FRASE INTEIRA do dono,
    não as palavras dela soltas. Com o quadro fora, um alcance preso a ele seria
    uma régua medindo string vazia: verde sobre nada.
    """
    html = _pagina(publicado)
    for nome, texto in _frases_proibidas():
        assert texto not in html, (
            f"a aba Perfis carrega `{nome}` — a decisão 10-Q6 dela tirou as "
            f"DUAS frases, e o aviso pertence ao canal de recado. A frase "
            f"continua certa onde ela mora; errada é a tela.")
