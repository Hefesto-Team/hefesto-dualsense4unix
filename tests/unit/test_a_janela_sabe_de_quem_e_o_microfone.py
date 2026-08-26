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

# O card de verdade só existe com o PyGObject REAL (`_GTK_DISPONIVEL`); com o
# stub, `ControllerCard` é a casca sem os callbacks, e o teste mediria a casca.
exigir_gi_real("a janela sabe de quem é o microfone")

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_MIC_ALVO_NAO_HONRADO,
    frase_do_alvo_do_mic,
)

#: Os dois endereços da mesa. Faixa da casa (`aa:bb:cc`, sem sequência simples)
#: e com a máscara dos octetos 4 e 5 — há portão que reprova MAC de verdade em
#: arquivo versionado, e um MAC sequencial já bateu por acaso com um literal de
#: segredo e travou dois commits.
UNIQ_ESCOLHIDO = "aa:bb:cc:00:00:f0"
UNIQ_DO_VIZINHO = "aa:bb:cc:00:00:a3"


class _JanelaDeRascunho:
    """O dono do rascunho, com o mínimo que `registrar_microfone_no_rascunho` lê."""

    def __init__(self) -> None:
        self.draft = DraftConfig()


class _CardMinimo:
    """O card sem GTK: só o callback e o que ele toca.

    O callback de sucesso do microfone é um método do ``ControllerCard``, e
    montá-lo inteiro aqui pediria display. O que este teste mede é a REGRA —
    o que entra no rascunho e o que a tela confessa —, e ela não tem widget
    dentro. O aviso é substituído por um espião que registra `show`/`hide`,
    exatamente o par que o card de verdade chama.
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            ControllerCard,
        )

        self._dono_do_rascunho = _JanelaDeRascunho()
        self.mostrou: list[bool] = []
        self._mic_aviso_alvo = self
        # Os dois métodos vêm da classe de verdade, sem instanciar o widget:
        # é o código do produto que está sendo exercido, não uma cópia dele.
        self._mic_confirmado_pelo_daemon = (
            ControllerCard._mic_confirmado_pelo_daemon.__get__(self)
        )
        self._dizer_alvo_do_mic = ControllerCard._dizer_alvo_do_mic.__get__(self)

    # -- o dublê do rótulo de aviso, e ele sabe RECUSAR ---------------------
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


# ---------------------------------------------------------------------------
# A frase, sem card: os três estados de `por_uniq`
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# A MORDIDA
# ---------------------------------------------------------------------------


def test_alvo_nao_honrado_nao_grava_no_rascunho() -> None:
    """A MORDIDA: o daemon confessa `por_uniq: False` e o rascunho NÃO muda.

    Devolvendo o card ao `mic_volume_set` simples — o invólucro `bool` —, o
    callback recebe `True`, o volume entra no rascunho dela, e este teste
    reprova nomeando os DOIS endereços: o que ela escolheu e o que de fato foi
    mexido.
    """
    card = _CardMinimo()
    antes = card.volume_no_rascunho

    _responder(
        card,
        # O corpo REAL do daemon: `status` ok — o pedido foi atendido —, e
        # `por_uniq` False, que é o daemon dizendo "não consegui mirar o que
        # você pediu". É a combinação que o `bool` da ponte apagava.
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
    """O contrapeso, e sem ele a régua acima passaria com a cura de fora.

    Uma régua que só sabe recusar não é régua: se a condição virasse "nunca
    grava", o teste da mordida continuaria verde e o produto pararia de salvar
    o microfone dela no perfil — o defeito de 18/08 ressuscitado.
    """
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
    """`por_uniq` ausente é "não sei", e "não sei" não é "não honrei".

    O caso vivo: daemon mais velho, ou uma rota que não publica o campo. Tratá-lo
    como `False` faria a tela acusar o produto de um erro que ninguém mediu — e
    faria o microfone dela parar de ser salvo contra todo daemon anterior a
    23/08/2026.
    """
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
    """`sem_fonte` é o rádio sem a ponte de áudio: o pedido NÃO ficou de pé.

    O que a tela faz com essa palavra continua sendo desenho dela — o card não
    ganha estado novo aqui. O que este teste trava é o registro: um volume que
    não foi aplicado não pode entrar no perfil.
    """
    card = _CardMinimo()

    _responder(card, {"status": "sem_fonte", "por_uniq": True}, volume=70)

    assert card.volume_no_rascunho is None, (
        "o daemon disse `sem_fonte` — nenhuma fonte de captura existe — e o "
        "volume entrou no rascunho como se tivesse sido aplicado"
    )


# ---------------------------------------------------------------------------
# O gesto do MUDO continua no `bool`, e o callback tem de aguentar os dois
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ok", [True, False])
def test_o_mudo_continua_falando_bool(ok: bool) -> None:
    """`mic.set` não mudou de rota, e o mesmo callback atende os dois gestos.

    Se o callback passasse a exigir `dict`, o botão de mudo pararia de gravar o
    estado dela no perfil — uma regressão silenciosa num gesto vizinho, que é
    exatamente como a cura de um lado quebra o outro.
    """
    card = _CardMinimo()

    card._mic_confirmado_pelo_daemon(muted=True)(ok)

    assert card._dono_do_rascunho.draft.mic.muted is (True if ok else None)
    assert card.mostrou == [False], (
        "o gesto do mudo não fala de alvo — a tela não pode confessar nada"
    )


# ---------------------------------------------------------------------------
# O CARD DE VERDADE: o gesto inteiro, do arrasto ao rascunho
# ---------------------------------------------------------------------------


def _card_com_endereco(monkeypatch: pytest.MonkeyPatch, corpo: Any) -> Any:
    """Monta o card real, com endereço, e planta a resposta do daemon.

    Card de verdade e não dublê porque a metade da cura que este teste mede é
    a ROTA: qual função da ponte o gesto chama. Um dublê do card mediria a
    minha cópia da rota, não a dela — e foi assim que esta casa já mediu a
    biblioteca errada e produziu alarme convincente e falso.
    """
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard

    if not Gtk.init_check()[0]:
        pytest.skip("sem GTK/display utilizável")

    pedidos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        ipc_bridge,
        "run_in_thread",
        lambda fn, on_success=None, on_failure=None: (
            on_success(fn()) if on_success is not None else fn()
        ),
    )
    monkeypatch.setattr(
        ipc_bridge,
        "mic_volume_set_detalhado",
        lambda **kw: (pedidos.append(kw), corpo)[1],
    )
    # A rota VELHA fica plantada com uma bomba: se o card voltar a chamá-la, o
    # teste não passa por engano — ele diz qual rota foi chamada.
    monkeypatch.setattr(
        ipc_bridge,
        "mic_volume_set",
        lambda **kw: pedidos.append({"ROTA_VELHA": kw}) or True,
    )

    card = ControllerCard(compact=False)
    janela_gtk = Gtk.OffscreenWindow()
    janela_gtk.add(card)
    janela_gtk.set_size_request(1180, 700)
    janela_gtk.show_all()
    card._janela_do_teste = janela_gtk
    card.update(
        {
            "index": 0,
            "connected": True,
            "uniq": UNIQ_ESCOLHIDO,
            "transport": "usb",
            "inputs": {},
        },
        {},
        None,
    )
    card.definir_dono_do_rascunho(_JanelaDeRascunho())
    return card, pedidos


def test_o_gesto_inteiro_recusa_o_alvo_do_vizinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA da ROTA: o card pergunta pelo alvo, e desiste quando erra.

    Arrancando a cura — devolvendo `ipc_bridge.mic_volume_set` ao
    `_enviar_volume_do_mic` — o pedido sai pela rota VELHA, o callback recebe o
    `bool` `True`, o volume vai para o rascunho DELA e a tela fica calada. As
    duas asserções abaixo reprovam, e a segunda nomeia a rota errada.
    """
    card, pedidos = _card_com_endereco(
        monkeypatch, {"status": "ok", "volume": 62, "por_uniq": False}
    )

    card._mic_escala.set_value(62)
    card._enviar_volume_do_mic()

    assert pedidos and "ROTA_VELHA" not in pedidos[0], (
        f"o gesto saiu pela rota que apaga o `por_uniq`: {pedidos}. Sem o "
        "corpo, a janela não tem como saber que mexeu no microfone de "
        f"{UNIQ_DO_VIZINHO} em vez do de {UNIQ_ESCOLHIDO}."
    )
    assert pedidos[0].get("uniq") == UNIQ_ESCOLHIDO
    assert card._dono_do_rascunho.draft.mic.volume is None, (
        f"o daemon não honrou o alvo {UNIQ_ESCOLHIDO} e o volume 62 foi "
        "gravado no rascunho DELA assim mesmo"
    )
    assert card._mic_aviso_alvo.get_visible(), (
        "a confissão não apareceu na tela: o volume dela foi para o microfone "
        "de outra pessoa e o card não disse nada"
    )


def test_o_gesto_inteiro_registra_quando_o_alvo_e_honrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O contrapeso no card real: honrado grava, e o aviso continua escondido."""
    card, pedidos = _card_com_endereco(
        monkeypatch, {"status": "ok", "volume": 62, "por_uniq": True}
    )

    card._mic_escala.set_value(62)
    card._enviar_volume_do_mic()

    assert pedidos and "ROTA_VELHA" not in pedidos[0]
    assert card._dono_do_rascunho.draft.mic.volume == 62
    assert not card._mic_aviso_alvo.get_visible()
