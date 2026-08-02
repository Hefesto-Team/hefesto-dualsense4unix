"""BT-E-VPAD-01 — o que só existe no cabo, e os furos do gamepad virtual.

A hipótese dela, com o controle no Bluetooth, ao ver a lightbar apagada e o
botão do microfone desobedecendo:

    "engraçado que os gatilhos funcionam no BT. Talvez algo não esteja pareado
     pra tudo funcionar via BT — cada uma das features esteja setada pra
     funcionar só via cabo, o que é um erro de design nosso."

**Está certa**, e esta casa já tem isso registrado com nome: *"a premissa
USB-é-o-mundo"*, listada como bug recorrente.
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid


# ---------------------------------------------------------------------------
# Defeito 1 — o botão do mic alternava o microfone ERRADO no Bluetooth
# ---------------------------------------------------------------------------


class _AudioDeBancada:
    """Um `AudioControl` com o subprocess trocado por uma resposta fixa."""

    def __init__(self, backend: str, saida: str) -> None:
        from hefesto_dualsense4unix.integrations.audio_control import AudioControl

        self.real = AudioControl()
        self.real._backend = backend
        self.comandos: list[list[str]] = []

        class _Resultado:
            stdout = saida

        def _run(argv: list[str]) -> Any:
            self.comandos.append(argv)
            return _Resultado()

        self.real._run = _run  # type: ignore[method-assign]


def test_a_fonte_padrao_do_controle_e_reconhecida() -> None:
    """Com o cabo, a fonte padrão É o controle — e o botão pode agir.

    Mordida: fazer `fonte_padrao_e_o_controle` devolver False sempre. O botão
    do microfone para de funcionar até no cabo, que é o caso que sempre
    funcionou.
    """
    for backend, saida in (
        ("pactl", "alsa_input.usb-Sony_DualSense_Wireless_Controller-00.mono"),
        ("wpctl", 'node.description = "DualSense Wireless Controller Mono"'),
    ):
        bancada = _AudioDeBancada(backend, saida)
        assert bancada.real.fonte_padrao_e_o_controle() is True, backend


def test_a_fonte_padrao_de_outro_dispositivo_nao_e_confundida() -> None:
    """O defeito, em uma linha.

    **Medido em 01/08/2026:** com o controle no Bluetooth,
    `pactl list short cards | grep -i dualsense` devolve ZERO — no BT o
    DualSense **não tem placa de som nenhuma**, porque o áudio vai dentro dos
    reports HID e depende da ponte deste projeto, que é opt-in e estava
    desligada.

    Então a fonte padrão era outra coisa: nesta máquina, o microfone da
    placa-mãe. O botão do microfone DO CONTROLE alternava aquele, e o LED do
    controle acendia para refletir um estado que não era dele. O log de três
    toques dela mostra a assinatura — sempre o mesmo resultado:

        20:15:54  mic_hotkey_toggle  muted=True
        20:16:31  mic_hotkey_toggle  muted=True
        20:16:43  mic_hotkey_toggle  muted=True

    Mordida: trocar a comparação por `return True`.
    """
    bancada = _AudioDeBancada(
        "pactl", "alsa_input.pci-0000_00_1f.3.analog-stereo"
    )
    assert bancada.real.fonte_padrao_e_o_controle() is False


def test_sem_backend_de_audio_a_resposta_e_nao_mexer() -> None:
    """Em caso de dúvida, False — e o chamador não mexe em nada.

    Não fazer nada é sempre melhor que mutar o microfone errado. É a mesma
    disciplina do resto da casa: uma tela que não sabe diz que não sabe, e um
    botão que não sabe não age.

    Mordida: devolver True no ramo do backend ausente.
    """
    bancada = _AudioDeBancada("none", "DualSense")
    assert bancada.real.fonte_padrao_e_o_controle() is False


def test_o_botao_do_mic_so_age_quando_a_fonte_e_o_controle() -> None:
    """A fiação, e não só a função — o gate tem de estar NO LOOP.

    Das três saídas que a sprint desenhou, esta é a **(a)**: o botão só age
    quando a fonte padrão é o controle. É a mais honesta e a mais barata.

    A **(b)** — mutar o registrador do firmware (`power_save_control` bit4),
    que existe nos dois transportes — foi recusada porque TOMA A POSSE e faz
    o botão físico parar de valer, que é o oposto do que se espera de um
    botão físico.

    Mordida: apagar o `if not pertence: continue` do `mic_button_loop`.
    """
    import inspect

    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    fonte = inspect.getsource(hotkey.mic_button_loop)

    assert "fonte_padrao_e_o_controle" in fonte
    pos_gate = fonte.index("fonte_padrao_e_o_controle")
    pos_toggle = fonte.index("toggle_default_source_mute")
    assert pos_gate < pos_toggle, (
        "a pergunta 'a fonte é o controle?' tem de vir ANTES do toggle — "
        "depois dele o microfone errado já foi mutado"
    )
    # E tem de haver um DESVIO entre as duas: perguntar e ignorar a resposta
    # é o mesmo que não perguntar. A primeira versão deste teste travava só a
    # ordem, e não mordia — apagar o `if not pertence: continue` deixava a
    # chamada do gate no lugar e a asserção de ordem passava.
    entre = fonte[pos_gate:pos_toggle]
    assert "continue" in entre, (
        "entre a pergunta e o toggle tem de haver um `continue`: sem ele a "
        "resposta é lida e descartada, e o microfone errado é mutado do mesmo "
        "jeito"
    )


# ---------------------------------------------------------------------------
# Furo 1 — o nome do vpad não continha "Wireless Controller"
# ---------------------------------------------------------------------------


def test_o_nome_do_vpad_contem_a_substring_que_os_jogos_procuram() -> None:
    """Sob Proton o nome vira o `FriendlyName` do lado Windows.

    Jogos casam pela substring "Wireless Controller" para achar o controle e
    o device de áudio associado a ele. A incoerência interna denunciava o
    furo: o fallback uinput já acertava (`Sony Interactive Entertainment
    DualSense Edge Wireless Controller`) e o uhid, que é o caminho bom, não.

    Mordida: voltar para `Hefesto Virtual DualSense P{n}`.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    nome = UhidDualSense(player=2, blueprint=None).name

    assert "Wireless Controller" in nome
    # E a distinção humana continua: é o que separa este device do físico na
    # lista do sistema, e é o que ela vê.
    assert "Hefesto" in nome
    assert "P2" in nome


# ---------------------------------------------------------------------------
# Furo 2 — o byte 53 nunca era escrito
# ---------------------------------------------------------------------------


def test_o_byte_53_acompanha_o_fisico_em_vez_de_sair_fixo() -> None:
    """`HP_DETECT`, `MIC_DETECT` e `MIC_MUTE` — os três bits que faltavam.

    O `_encode_body` escrevia o byte 52 (bateria) e **nunca o 53**. Com valor
    fixo, o campo não acompanhava o controle de verdade: um jogo que decida
    rotear som para o alto-falante do controle **só quando não há fone
    plugado** estava lendo um número que não vinha de lugar nenhum.

    O dado está FORA da janela de motion (15..39), então precisa de caminho
    próprio — o mesmo desenho que o clique do touchpad já usa.

    Mordida: apagar a linha `body[_STATUS1_OFFSET] = ...` do `_encode_body`.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=1, blueprint=None)

    corpo = pad._encode_body()
    assert corpo[uhid._STATUS1_OFFSET] == uhid._STATUS1_NEUTRO

    # Fone plugado (bit0) e microfone mudo (bit2).
    pad.forward_jack(0b101)
    corpo = pad._encode_body()
    assert corpo[uhid._STATUS1_OFFSET] == 0b101


def test_so_os_tres_bits_conhecidos_do_byte_53_sao_encaminhados() -> None:
    """O resto do byte é do firmware, e não é nosso para repassar.

    Mandar bit desconhecido adiante é a mesma classe de erro que autorizar um
    campo de áudio sem escrever valor nele — o `AUDIO-OWNER-01` já pagou por
    essa lição noutro lugar deste projeto.

    Mordida: trocar a máscara por `0xFF`.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=1, blueprint=None)
    pad.forward_jack(0xFF)

    assert pad._encode_body()[uhid._STATUS1_OFFSET] == 0b111
