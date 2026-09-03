"""O doctor mandava pegar o cabo por um microfone que o rádio já entrega.

PLATAFORMA-CABO-E-RADIO-01 (03/09/2026) — o defeito, e como ele passou.

O ``check_snd_audio_healthy`` conta PLACAS ALSA, e a contagem está certa: por
rádio o DualSense não anuncia A2DP/HFP/HSP e não publica placa de som nenhuma.
O erro estava no CONSELHO que saía da contagem, em duas frases::

    "conecte o controle pelo cabo — no rádio o mic e o fone não passam."
    "nada; conecte pelo cabo se quiser usar o mic e o fone do controle."

O microfone PASSA por rádio desde 25/07/2026, e passa por fora do ALSA: o áudio
vem em Opus tunelado no relatório HID 0x31 e quem o publica como fonte de
captura do PipeWire é a ponte deste produto
(``integrations/dualsense_bt_audio.py``). A própria aba de Conexões já dizia
isso à usuária — *"No rádio o microfone já é emulado hoje, com outro nome"*
(``interface/paginas/08-conexoes.html``) — enquanto o doctor lhe dizia o
contrário na mesma máquina. Duas vozes do mesmo produto, discordando.

O PADRÃO, e ele tem nome nesta casa: **o aparelho aceita, e quem recusa é o
filtro nosso**. Aqui o filtro não era um ``if``, era uma FRASE — e uma frase
que manda a pessoa trocar de transporte custa tanto quanto um gate.

A MORDIDA desta régua é dupla, de propósito:

1. **contra a volta da frase** — nenhuma resposta do check pode mandar pegar o
   cabo POR CAUSA do microfone, nem negar que ele passe por rádio;
2. **contra a evidência sumir** — a frase nova afirma que existe uma ponte de
   microfone por Bluetooth. Se alguém apagar a ponte, esta régua reprova junto,
   porque a afirmação da tela passaria a ser falsa. Régua que só olha texto
   deixaria a tela mentindo ao contrário.

O QUE ELA **NÃO** MEDE: que a ponte esteja no ar agora, ou que o firmware
obedeça. Isso é bancada, com a orelha dela. Aqui se mede só que o produto
parou de recomendar o cabo por um motivo que deixou de ser verdade.
"""

from __future__ import annotations

import re

import pytest

from hefesto_dualsense4unix.integrations import storm_doctor as sd

#: Toda resposta do check, nos cinco ramos. A chave é o ramo, para a reprovação
#: nomear qual deles voltou a mentir em vez de mandar caçar.
UMA_PLACA = "1 [Controller]: USB-Audio - DualSense Wireless Controller"


def _todas_as_frases() -> dict[str, str]:
    return {
        "sem_denominador_sem_placa": sd.check_snd_audio_healthy(
            cards_text="0 [Generic]: HDA-Intel"
        )[1],
        "sem_denominador_com_placa": sd.check_snd_audio_healthy(
            cards_text=UMA_PLACA
        )[1],
        "nenhum_no_cabo": sd.check_snd_audio_healthy(
            cards_text="", controles_no_cabo=0
        )[1],
        "todos_sem_placa": sd.check_snd_audio_healthy(
            cards_text="", controles_no_cabo=2
        )[1],
        "parte_dos_controles": sd.check_snd_audio_healthy(
            cards_text=UMA_PLACA, controles_no_cabo=2
        )[1],
    }


#: As formas em que a frase derrubada volta. Casam a NEGAÇÃO do microfone por
#: rádio, não a palavra "cabo" — o cabo é resposta legítima para o FONE, e para
#: o controle que sumiu do barramento.
_NEGA_O_MIC_NO_RADIO = (
    re.compile(r"no\s+rádio\s+o\s+mic\w*\s+e\s+o\s+fone\s+não\s+passam", re.I),
    re.compile(r"conecte\s+pelo\s+cabo\s+se\s+quiser\s+usar\s+o\s+mic", re.I),
    re.compile(r"cabo.{0,40}\bpara\s+(?:ter|usar)\s+o\s+microfone", re.I),
)


@pytest.mark.parametrize("ramo", sorted(_todas_as_frases()))
def test_nenhum_ramo_manda_pegar_o_cabo_por_causa_do_microfone(ramo: str) -> None:
    """A frase derrubada não pode voltar por nenhum dos cinco ramos."""
    frase = _todas_as_frases()[ramo]
    for padrao in _NEGA_O_MIC_NO_RADIO:
        assert not padrao.search(frase), (
            f"o ramo {ramo!r} voltou a negar o microfone por rádio: {frase!r}. "
            "O microfone por Bluetooth existe desde 25/07/2026 "
            "(integrations/dualsense_bt_audio.py) e não passa por placa ALSA — "
            "contar placas continua certo, mandar pegar o cabo por causa do "
            "microfone não."
        )


def test_os_dois_ramos_sem_placa_nomeiam_a_ponte() -> None:
    """Não basta calar a frase errada: os dois ramos têm de dizer o certo.

    Sem esta metade, apagar as duas frases inteiras passaria — e a usuária
    ficaria sem saber que o microfone dela funciona no rádio.
    """
    frases = _todas_as_frases()
    for ramo in ("sem_denominador_sem_placa", "nenhum_no_cabo"):
        frase = frases[ramo]
        assert "microfone" in frase.lower(), (
            f"o ramo {ramo!r} deixou de falar do microfone: {frase!r}"
        )
        assert "ponte" in frase.lower(), (
            f"o ramo {ramo!r} não diz por onde o microfone chega no rádio: "
            f"{frase!r}. A ponte é o nome que a aba de Conexões já usa."
        )


def test_a_ponte_que_a_frase_promete_existe_de_verdade() -> None:
    """A outra metade da mordida: arranque a ponte e esta régua cai junto.

    A frase nova afirma um fato do produto. Uma régua que só comparasse texto
    deixaria a tela prometendo um caminho apagado — é o defeito que esta casa
    já pagou com régua que digita o que devia LER.
    """
    ponte = pytest.importorskip(
        "hefesto_dualsense4unix.integrations.dualsense_bt_audio",
        reason="a ponte de microfone por Bluetooth é o que a frase promete",
    )
    assert hasattr(ponte, "montar_pedido_de_mic"), (
        "a ponte perdeu o montador do pedido de microfone — a frase do doctor "
        "passou a prometer um caminho que não existe mais"
    )
    ligar = ponte.montar_pedido_de_mic(True)
    desligar = ponte.montar_pedido_de_mic(False)
    assert ligar[0] == 0x32 and desligar[0] == 0x32, (
        "o pedido de microfone deixou de sair no report 0x32 — o caminho por "
        "rádio mudou e a frase do doctor precisa ser reconferida"
    )
    assert ligar != desligar, "ligar e desligar viraram o mesmo pedido"
