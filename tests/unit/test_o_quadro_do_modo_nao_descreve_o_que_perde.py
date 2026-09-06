"""O quadro "Modo" entrega os quatro botões — e NENHUMA das duas frases.

**A ENCOMENDA É DA `ONDA5-10-03`, decisão 10-Q6 dela**, e a `PERFIL-MODO-01` a
cumpre no mesmo dia em que o quadro nasce. As duas frases que a janela GTK põe
ao lado do modo NÃO atravessam:

* **o preço da máscara Xbox** — `home_actions.TEXTO_CUSTO_MASCARA_XBOX`, o
  tooltip que diz o que o Xbox 360 não faz (giroscópio, touchpad, vibração
  fina). Na janela estável ele vive no seletor de máscara do editor de perfil
  (`profiles_actions._install_mode_section`, `flavor_sel.set_tooltips`);
* **o rádio frágil no Nativo** — `home_actions.texto_do_radio_fragil`, a linha
  condicional que a aba Perfis passou a mostrar em 24/08 ao oferecer "Conexão
  Nativa (Sony)".

**ELA LÊ AS CONSTANTES, NUNCA AS DIGITA**, e a razão é a armadilha desta casa:
uma régua que carregasse o texto se desligaria sozinha no dia em que a frase
mudasse uma vírgula — e ficaria VERDE sobre a frase nova, que é o pior estado
de um portão. O dono das duas é `app/actions/home_actions.py`, e ele continua
sendo o dono: as duas frases estão CERTAS na janela GTK, e o que esta régua diz
é que elas não pertencem a ESTE quadro.

**O ALCANCE É O QUADRO, NÃO A PÁGINA.** As palavras "rádio" e "Xbox 360"
aparecem legitimamente noutros pontos da aba 10 (as dicas do Estilo de Jogo, a
tabela da guarda). Medir a página inteira daria um portão que reprova por
motivo errado — e um portão assim é desligado por quem for mexer nele.

MORDIDA (as duas colhidas em 06/09/2026, com a cura arrancada e devolvida):
ponha `title="{TEXTO_CUSTO_MASCARA_XBOX}"` num dos quatro botões do
`aba10.botoes_do_modo` e a primeira asserção reprova nomeando a constante.
"""
from __future__ import annotations

import re

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


def _quadro_do_modo(publicado: bool) -> str:
    """Só o `<div class="campo modo">` — o alcance desta régua.

    `""` quando o quadro ainda não existe naquela página: na PUBLICADA ele
    espera o `--publicar 10`, que é ato dela, e um `assert` sobre a página que o
    produto renderiza hoje reprovaria por uma ausência que é o desenho.
    """
    html = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    achado = re.search(r'<div class="campo modo">.*?</div>', html, re.S)
    return achado.group(0) if achado else ""


def _frases_proibidas() -> list[tuple[str, str]]:
    """`(nome da constante, texto)` — perguntados ao DONO, nunca digitados."""
    frases = [("home_actions.TEXTO_CUSTO_MASCARA_XBOX", TEXTO_CUSTO_MASCARA_XBOX)]
    do_radio = texto_do_radio_fragil(_ESTADO_DO_RADIO_FRAGIL)
    if do_radio:
        frases.append(("home_actions.texto_do_radio_fragil", do_radio))
    return frases


def test_as_duas_frases_do_dono_existem_de_verdade() -> None:
    """A régua acima só morde se as constantes ainda produzem texto.

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
def test_o_quadro_do_modo_nao_descreve_o_que_perde(publicado: bool) -> None:
    """Decisão 10-Q6 dela: o quadro entrega os quatro botões e nada mais."""
    quadro = _quadro_do_modo(publicado)
    if not quadro:
        pytest.skip(
            "o quadro Modo ainda não existe nesta página — na PUBLICADA ele "
            "espera o `--publicar 10`, que é ato dela")
    for nome, texto in _frases_proibidas():
        assert texto not in quadro, (
            f"o quadro Modo carrega `{nome}` — a decisão 10-Q6 dela tirou as "
            f"DUAS frases, e o aviso pertence ao canal de recado. A frase "
            f"continua certa onde ela mora (a janela GTK); errada é a tela.")


def test_o_quadro_do_modo_existe_na_bancada() -> None:
    """E o `skip` acima não pode virar o portão inteiro se calando.

    Se o quadro sumir da BANCADA, o teste de cima passa a pular nos dois casos e
    a decisão 10-Q6 fica sem quem a guarde. Esta asserção é o que impede isso.
    """
    assert _quadro_do_modo(publicado=False), (
        "o quadro Modo sumiu da bancada — com ele some a régua acima, que "
        "passaria a pular nas duas páginas e a dar verde sobre nada")
