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

from typing import Any

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

    @property
    def volume_no_rascunho(self) -> int | None:
        return self._dono_do_rascunho.draft.mic.volume


def _responder(card: _CardMinimo, corpo: Any, *, volume: int) -> None:
    """Entrega ao callback do card a resposta que o daemon deu."""
    card._mic_confirmado_pelo_daemon(volume=volume)(corpo)


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


def test_alvo_nao_honrado_nao_grava_no_rascunho() -> None:
    """A MORDIDA: o daemon confessa `por_uniq: False` e o rascunho NÃO muda."""
    card = _CardMinimo()
    antes = card.volume_no_rascunho

    _responder(
        card,
        {"status": "ok", "volume": 62, "fonte": "alsa_input.pci-0000_00", "por_uniq": False},
        volume=62,
    )

    assert card.volume_no_rascunho == antes, (
        "o gesto mirava o controle "
        f"{UNIQ_ESCOLHIDO} e o daemon mexeu no microfone de "
        f"{UNIQ_DO_VIZINHO} (rota global, `por_uniq: False`) — mesmo assim o "
        f"volume {card.volume_no_rascunho} foi gravado no rascunho DELA. O "
        "perfil deste controle passa a carregar um número que este controle "
        "nunca teve."
    )
    assert card.mostrou == [True], (
        "a tela não confessou: o volume foi para o microfone de outra pessoa "
        "e o card ficou calado"
    )


def test_alvo_honrado_grava_e_a_tela_fica_calada() -> None:
    """O contrapeso, e sem ele a régua acima passaria com a cura de fora."""
    card = _CardMinimo()

    _responder(
        card,
        {"status": "ok", "volume": 62, "por_uniq": True},
        volume=62,
    )

    assert card.volume_no_rascunho == 62, (
        "o daemon honrou o alvo e o volume dela não foi para o rascunho"
    )
    assert card.mostrou == [False], (
        "a tela confessou um erro que não aconteceu"
    )


def test_daemon_calado_sobre_o_alvo_continua_registrando() -> None:
    """`por_uniq` ausente é "não sei", e "não sei" não é "não honrei"."""
    card = _CardMinimo()

    _responder(card, {"status": "ok", "volume": 55}, volume=55)

    assert card.volume_no_rascunho == 55
    assert card.mostrou == [False]


def test_daemon_offline_nao_registra_e_nao_confessa() -> None:
    """`None` = o daemon não respondeu. Não há o que gravar nem o que confessar."""
    card = _CardMinimo()

    _responder(card, None, volume=70)

    assert card.volume_no_rascunho is None
    assert card.mostrou == [False]


def test_sem_fonte_nao_registra() -> None:
    """`sem_fonte` é o rádio sem a ponte de áudio: o pedido NÃO ficou de pé."""
    card = _CardMinimo()

    _responder(card, {"status": "sem_fonte", "por_uniq": True}, volume=70)

    assert card.volume_no_rascunho is None, (
        "o daemon disse `sem_fonte` — nenhuma fonte de captura existe — e o "
        "volume entrou no rascunho como se tivesse sido aplicado"
    )


@pytest.mark.parametrize("ok", [True, False])
def test_o_mudo_continua_falando_bool(ok: bool) -> None:
    """`mic.set` não mudou de rota, e o mesmo callback atende os dois gestos."""
    card = _CardMinimo()

    card._mic_confirmado_pelo_daemon(muted=True)(ok)

    assert card._dono_do_rascunho.draft.mic.muted is None, (
        "o mudo entrou no rascunho — o «Salvar» o levaria ao perfil, e o mudo "
        "é do controle")
    assert card.mostrou == [False], (
        "o gesto do mudo não fala de alvo — a tela não pode confessar nada"
    )


