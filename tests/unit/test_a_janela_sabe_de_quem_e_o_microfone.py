"""A janela sabe DE QUEM é o microfone que ela mexeu — MIC-DA-MESA-CHEIA-01.

**O defeito, e ele é da mesa cheia.** Com dois DualSense no cabo há DUAS placas
de som, e o ``mic.volume.set`` que não consegue mirar o controle escolhido cai
na rota GLOBAL, que pega a PRIMEIRA — o microfone de outra pessoa. O daemon já
sabe disso e já diz: ele responde ``por_uniq`` desde 23/08/2026, e a ponte já
traduz a resposta em três estados de propósito (``ipc_bridge.alvo_honrado``:
``True`` honrei, ``False`` não honrei, ``None`` não sei).

**Onde o caminho se perdia.** O card chamava ``ipc_bridge.mic_volume_set``, o
invólucro ``bool``, e o ``bool`` colapsa os dois casos no mesmo ``True``. O
callback de sucesso então gravava o volume no rascunho DELA — o perfil deste
controle ganhava um número que este controle nunca teve, porque quem mudou de
volume foi o vizinho.

**A cura, em duas metades e nenhuma sem a outra:**

1. o card chama ``mic_volume_set_detalhado`` e lê o corpo com ``alvo_honrado``;
2. alvo não honrado **não entra no rascunho**, e a tela CONFESSA
   (``TEXTO_MIC_ALVO_NAO_HONRADO``, marcado `PROVISÓRIO — decisão dela`).

``None`` — o daemon não se pronunciou — continua registrando, e essa linha é
deliberada: "não sei" não é "não honrei", e recusar por ausência de notícia
inventaria um defeito que ninguém mediu. É a mesma disciplina que fez a ponte
devolver três estados em vez de dois.

**O que este arquivo NÃO cobre, e por quê.** Separar ``sem_fonte`` de "daemon
offline" pede um ESTADO NOVO na tela — controle insensível com a dica —, e isso
é desenho: foto antes e depois, e a palavra é dela. A lápide do
``portao_a_casa_sabe_e_o_produto_nao_faz`` já dizia isso, e continua dizendo.
"""

from __future__ import annotations


import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a janela sabe de quem é o microfone")

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    TEXTO_MIC_ALVO_NAO_HONRADO,
    frase_do_alvo_do_mic,
)

UNIQ_ESCOLHIDO = "aa:bb:cc:00:00:f0"
UNIQ_DO_VIZINHO = "aa:bb:cc:00:00:a3"


class _JanelaDeRascunho:
    """O dono do rascunho, com o mínimo que `registrar_microfone_no_rascunho` lê."""

    def __init__(self) -> None:
        self.draft = DraftConfig()


class _CardMinimo:
    """O card sem GTK: só o callback e o que ele toca."""


    def show(self) -> None:
        self.mostrou.append(True)

    def hide(self) -> None:
        self.mostrou.append(False)


@pytest.mark.parametrize("honrado", [True, None])
def test_so_o_alvo_nao_honrado_produz_frase(honrado: bool | None) -> None:
    """`True` e `None` calam a tela; só `False` a faz falar."""
    assert frase_do_alvo_do_mic(honrado) == "", (
        f"a tela confessou um erro que o daemon não relatou (por_uniq={honrado!r})"
    )


def test_a_frase_do_alvo_nao_honrado_e_a_confissao() -> None:
    """E ela diz as DUAS coisas: o que aconteceu e o que NÃO aconteceu."""
    frase = frase_do_alvo_do_mic(False)
    assert frase == TEXTO_MIC_ALVO_NAO_HONRADO
    assert "OUTRO controle" in frase, "a confissão não diz o que aconteceu"
    assert "não mudou" in frase, (
        "a confissão não diz o que NÃO aconteceu — sem isso ela deixa a "
        "dúvida de o perfil ter sido gravado errado"
    )


