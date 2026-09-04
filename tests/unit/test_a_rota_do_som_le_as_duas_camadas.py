""""Todo o som do PC" só acende quando as DUAS camadas concordam.

ALTO-FALANTE-DOIS-CANAIS-01 (04/09/2026). Decisão dela, meio-dia: *"sons do pc
e sons do jogo. veja como fizemo no gtk."*  # noqa-acento: citação literal dela

São dois caminhos independentes, e a janela antiga já sabia
(`app/widgets/controller_card.CANAIS_DO_SPEAKER`):

    Sons do jogo      o byte `OUTPUT_PATH_SEL` = 2 — camada 2, o firmware
    Todo o som do PC  `pactl set-default-sink` para a placa do controle
                      **E** o byte = 3 — camadas 1 + 2

E a ordem é medida: *"a camada 1 vence a camada 2 — volume e rota perfeitos num
sink mudo é trabalho invisível"*.

O DEFEITO QUE ESTA RÉGUA PEGA, e ele é de 03/09/2026
-----------------------------------------------------
O card 2 mostrava "Todo o som do PC" ACESO com o som saindo na TV. A tela
acendia o botão pelo FIRMWARE e mais nada — ninguém lia o default sink
(`a02_controles.rota_na_tela` lê só `speaker.rota`). Uma leitura de volta que
só confere o byte dá verde sobre exatamente esse estado.

A MORDIDA
---------
**Arranque a leitura do sink** — faça `botao_da_rota_aceso` devolver `"pc"` só
pelo byte, ignorando `sink_padrao` — e
`test_o_byte_sozinho_nao_acende_todo_o_som_do_pc` reprova. É o verde falso que
esta régua existe para pegar.
"""
from __future__ import annotations

import inspect

import pytest

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.audio_saida import (
    BYTE_SONS_DO_JOGO,
    BYTE_TODO_O_SOM_DO_PC,
    MOTIVO_ROTA_SO_NO_BYTE,
    RotaDasDuasCamadas,
    botao_da_rota_aceso,
    recado_da_rota,
)

#: A placa de som do controle no cabo, e a saída que ela usava antes. Nomes
#: com a forma dos reais e sem endereço nenhum — o `pactl` não publica MAC.
PLACA_DO_CONTROLE = "alsa_output.usb-Sony_DualSense-00.analog-surround-40"
A_TV = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


# ---------------------------------------------------------------------------
# A tabela inteira do botão
# ---------------------------------------------------------------------------


def test_as_duas_camadas_concordando_acendem_todo_o_som_do_pc() -> None:
    assert botao_da_rota_aceso(
        BYTE_TODO_O_SOM_DO_PC, PLACA_DO_CONTROLE, PLACA_DO_CONTROLE
    ) == "pc"


def test_o_byte_sozinho_nao_acende_todo_o_som_do_pc() -> None:
    """A MORDIDA. Byte em "todo o som do PC", som saindo na TV: APAGADO.

    Foi o estado medido em 03/09 — o botão aceso com o som na TV. Acender aqui
    é a tela afirmando o que o sistema desmente.
    """
    assert botao_da_rota_aceso(BYTE_TODO_O_SOM_DO_PC, PLACA_DO_CONTROLE, A_TV) == ""


def test_o_desacordo_vira_recado_e_nao_silencio() -> None:
    """Apagar os dois botões sem dizer nada seria o silêncio que ela reclamou."""
    frase = recado_da_rota(BYTE_TODO_O_SOM_DO_PC, PLACA_DO_CONTROLE, A_TV)
    assert frase == MOTIVO_ROTA_SO_NO_BYTE
    assert "não é ele" in frase


def test_sons_do_jogo_acende_pelo_byte_e_so_por_ele() -> None:
    """"Sons do jogo" é camada 2 e mais nada — o sink não entra na conta.

    É o caso que ela descreveu com o Zelda: *"o speaker do controle faz os
    barulhos da espada do Link enquanto na tela tem o som normal do jogo"*. O
    som do PC continua onde estava, e isso é o desenho, não um desacordo.
    """
    assert botao_da_rota_aceso(BYTE_SONS_DO_JOGO, PLACA_DO_CONTROLE, A_TV) == "jogo"
    assert botao_da_rota_aceso(BYTE_SONS_DO_JOGO, "", A_TV) == "jogo"
    assert recado_da_rota(BYTE_SONS_DO_JOGO, PLACA_DO_CONTROLE, A_TV) == ""


@pytest.mark.parametrize("byte", [0, 1])
def test_as_rotas_do_fone_apagam_os_dois(byte: int) -> None:
    """0 e 1 são rotas legítimas que estes dois botões não representam.

    Acender o mais parecido seria arredondar o byte para o botão vizinho.
    """
    assert botao_da_rota_aceso(byte, PLACA_DO_CONTROLE, PLACA_DO_CONTROLE) == ""


@pytest.mark.parametrize("byte", [None, "3", True, 7])
def test_o_que_nao_e_rota_conhecida_apaga_os_dois(byte: object) -> None:
    """`None` é "o daemon nunca publicou `speaker` para este controle".

    O `state_full` só publica o bloco depois do primeiro `speaker.set`, porque
    o DualSense não devolve o registrador. `True` está aqui porque `bool` é
    subclasse de `int` e viraria a rota 1 sem a guarda.
    """
    assert botao_da_rota_aceso(byte, PLACA_DO_CONTROLE, PLACA_DO_CONTROLE) == ""


def test_o_radio_nunca_acende_todo_o_som_do_pc() -> None:
    """Sem placa de som não há camada 1 — e é o RÁDIO, medido em 15/08/2026.

    O `mapa-controles.csv` registra o mesmo fato do outro lado
    (`audio.alto_falante`, `radio_aciona=não`), e a recusa honesta já está em
    `MOTIVO_ROTA_SEM_SINK`.
    """
    assert botao_da_rota_aceso(BYTE_TODO_O_SOM_DO_PC, "", "") == ""
    assert botao_da_rota_aceso(BYTE_TODO_O_SOM_DO_PC, "", A_TV) == ""


def test_o_sink_no_controle_com_o_byte_do_jogo_nao_e_desacordo() -> None:
    """Ela mandou o som para cá pelas configurações do sistema: sem recado.

    O botão "Todo o som do PC" apagado descreve isso sem mentir — o produto
    não foi quem trouxe o som, e não tem o que corrigir.
    """
    assert recado_da_rota(BYTE_SONS_DO_JOGO, PLACA_DO_CONTROLE, PLACA_DO_CONTROLE) == ""


# ---------------------------------------------------------------------------
# O objeto que a tela vai ler
# ---------------------------------------------------------------------------


def test_a_leitura_junta_as_duas_camadas_num_objeto_so() -> None:
    lida = RotaDasDuasCamadas(
        byte=BYTE_TODO_O_SOM_DO_PC,
        sink_do_controle=PLACA_DO_CONTROLE,
        sink_padrao=PLACA_DO_CONTROLE,
    )
    assert lida.botao_aceso == "pc"
    assert lida.no_controle is True
    assert lida.concordam is True
    assert lida.recado == ""


def test_o_objeto_denuncia_o_desacordo() -> None:
    lida = RotaDasDuasCamadas(
        byte=BYTE_TODO_O_SOM_DO_PC,
        sink_do_controle=PLACA_DO_CONTROLE,
        sink_padrao=A_TV,
    )
    assert lida.botao_aceso == ""
    assert lida.no_controle is False
    assert lida.concordam is False
    assert lida.recado == MOTIVO_ROTA_SO_NO_BYTE


def test_a_leitura_de_verdade_nao_rele_o_byte(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ler_as_duas_camadas` recebe o byte pronto — não inventa uma 2ª leitura.

    Quem publica o byte é o daemon. Reler aqui daria à tela uma segunda
    verdade sobre o mesmo fato, que é o defeito que esta casa já pagou onze
    vezes com duas réguas sobre o mesmo estado.
    """
    chamados: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        chamados.append(argv)
        if argv[:2] == ["pactl", "get-default-sink"]:
            return A_TV
        return ""

    monkeypatch.setattr(
        audio_saida, "sink_do_controle", lambda *a, **k: PLACA_DO_CONTROLE
    )
    lida = audio_saida.ler_as_duas_camadas(
        "aa:bb:cc:00:00:01", BYTE_TODO_O_SOM_DO_PC, runner=runner
    )
    assert lida.byte == BYTE_TODO_O_SOM_DO_PC
    assert lida.sink_padrao == A_TV
    assert lida.botao_aceso == ""
    assert not any("speaker" in " ".join(a) for a in chamados)


# ---------------------------------------------------------------------------
# O ENSAIO VAI E VOLTA — e a volta não é opcional
# ---------------------------------------------------------------------------


def test_o_ensaio_devolve_a_saida_e_a_devolucao_esta_no_finally() -> None:
    """`devolver_o_som_do_pc` está no ensaio, e no caminho que sempre roda.

    Sem isso o som dela fica preso no controle — é justamente por que o gesto
    `rota` estava em `PERIGOSOS` e a régua de clique nunca o tinha clicado.
    Arranque a chamada do `finally` e este teste reprova.
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[2]
    fonte = (raiz / "scripts/ensaios/a_rota_do_som_vai_e_volta.py").read_text(
        encoding="utf-8"
    )
    assert "devolver_o_som_do_pc()" in fonte, "o ensaio não devolve o som"
    depois_do_finally = fonte.split("finally:", 1)
    assert len(depois_do_finally) == 2, "a devolução não está num `finally`"
    assert "devolver_o_som_do_pc()" in depois_do_finally[1], (
        "a devolução está fora do `finally` — uma exceção no meio da medição "
        "deixaria o som dela no controle"
    )


def test_o_ensaio_le_de_volta_as_duas_camadas() -> None:
    """Ir e voltar sem LER de volta é escrever e torcer."""
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[2]
    fonte = (raiz / "scripts/ensaios/a_rota_do_som_vai_e_volta.py").read_text(
        encoding="utf-8"
    )
    assert "RotaDasDuasCamadas" in fonte
    assert "get-default-sink" in fonte
    assert "daemon.state_full" in fonte, (
        "o ensaio lê o byte da resposta do `speaker.set` em vez do `state_full`"
        " — a resposta do `set` é o eco do que mandamos, e em Modo Nativo ela "
        "volta idêntica com o aparelho parado"
    )


def test_a_funcao_do_botao_e_pura() -> None:
    """Nada de subprocesso na decisão: ela roda no tique da tela.

    Uma leitura de PipeWire aqui seria um `pactl` por card por tique.
    """
    fonte = inspect.getsource(botao_da_rota_aceso)
    for proibido in ("subprocess", "pactl", "run(", "popen"):
        assert proibido not in fonte.lower(), (
            f"`botao_da_rota_aceso` deixou de ser pura: achei {proibido!r}"
        )
