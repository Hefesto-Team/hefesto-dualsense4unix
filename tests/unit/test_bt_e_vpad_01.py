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


# ---------------------------------------------------------------------------
# PARIDADE-SONY-01/E1 — o INSTRUMENTO do portão de medição
# ---------------------------------------------------------------------------


def _corpo_de_audio(flag0: int, bytes_de_audio: tuple[int, int, int, int]) -> bytes:
    """Um report 0x02 com os quatro bytes de áudio (`common[4..7]`)."""
    import struct

    corpo = bytearray(48)
    corpo[uhid._VALID_FLAG0_OFFSET] = flag0
    corpo[4:8] = bytes(bytes_de_audio)
    report = bytes([uhid._OUTPUT_REPORT_USB]) + bytes(corpo)
    dados = bytearray(4 + uhid.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    dados[4 : 4 + len(report)] = report
    struct.pack_into("<H", dados, 4 + uhid.HID_MAX_DESCRIPTOR_SIZE, len(report))
    return bytes(dados)


def _vpad_mudo() -> Any:
    """Um vpad sem fd, só para exercitar o `_handle_output`."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=1, blueprint=None)
    pad.time_fn = lambda: 1000.0
    return pad


def _vpad_em_jogo() -> Any:
    """Um vpad com a sessão de jogo ABERTA e a graça pós-bind vencida.

    Os testes que medem as OUTRAS condições do carimbo (o keepalive, os bits
    de autorização) precisam deste estado, senão passam por acidente: sem
    sessão de jogo o carimbo não sai de jeito nenhum, e a asserção fica
    verdadeira pelo motivo errado. Foi o que aconteceu na primeira versão
    deles, e o laço de mordidas pegou.
    """
    pad = _vpad_mudo()
    pad._game_open = True
    pad._bound_at = pad.time_fn() - 3600
    return pad


def test_o_jogo_que_pede_audio_deixa_carimbo() -> None:
    """O portão de medição da PARIDADE-SONY-01, como instrumento PERMANENTE.

    A pergunta da sprint: *"algum jogo que ela joga escreve `common[4]`, `[5]`,
    `[6]` ou `[7]` no gamepad virtual?"*. Ela pedia um log temporário; um
    carimbo permanente responde melhor, porque não depende de alguém lembrar
    de ligá-lo antes de jogar — ele já está lá quando ela joga.

    **Ele NÃO replica nada.** Mede. A replicação é a E2, e só acontece se esta
    medição disser que sim — como está escrito na sprint: *"um código escrito
    contra uma premissa não medida é dívida"*.

    Mordida: apagar o bloco do carimbo do `_handle_output`.
    """
    # SESSÃO DE JOGO ABERTA — sem ela o carimbo não sai, e a razão é a
    # primeira leitura do instrumento (02/08): ele apareceu com 8 segundos de
    # idade num daemon recém-reiniciado, SEM jogo nenhum. O driver
    # `hid-playstation` do kernel escreve os campos de áudio no PROBE do
    # device. Ver `test_o_probe_do_kernel_nao_conta_como_jogo`, abaixo.
    pad = _vpad_em_jogo()
    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s

    # Jogo pedindo volume de alto-falante: bit 0x20 ligado, byte 5 não-nulo.
    pad._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO in pad.visto_ha_s


def test_o_probe_do_kernel_nao_conta_como_jogo() -> None:
    """A correção que a PRIMEIRA leitura do instrumento exigiu.

    **Medido em 02/08/2026**, com o daemon recém-reiniciado e nenhum jogo
    aberto: `audio_do_jogo` apareceu com **8,3 segundos** de idade nos dois
    gamepads virtuais. A causa é o driver `hid-playstation` do kernel, que
    escreve os campos de áudio no PROBE do device — o kernel 6.18 manda rota,
    volume e pré-amp para fazer o alto-falante soar.

    Um instrumento que carimba na adoção pelo kernel responde *"sim, alguém
    escreve áudio"* **toda vez**, e a pergunta da sprint é outra: *"algum
    JOGO escreve esses bytes?"*. Sem esta correção, o portão da
    PARIDADE-SONY-01 daria um falso "sim" e a E2 seria construída sobre ele.

    É a mesma família da lição de 01/08 (*"medir contra a ferramenta errada
    produz um alarme convincente e falso"*), com outra roupa: aqui o
    instrumento estava certo e a PERGUNTA que ele respondia era outra.

    ---- O QUE ESTE TESTE **NÃO** PROVA — nota de 02/08/2026, à tarde ----

    Ele passa, e a mordida dele morde. Mas o nome promete mais do que ele
    entrega, e a diferença custou meio dia:

    **No hardware, `_game_open = False` depois do probe NÃO ACONTECE.** O
    `hid-playstation` chama `hid_hw_open()` ao adotar o device, e isso dispara
    o `UHID_OPEN` que liga `_game_open` (`uhid_gamepad.py:1542-1545`). O estado
    que este teste monta à mão é justamente o que a máquina nunca apresenta.

    Some-se a graça de `_GAME_REPLICA_GRACE_S` = **0,5 s**, dimensionada para o
    player-LED do probe (que é imediato), e a escrita de áudio do kernel — que
    chega ~10 s depois do bind — passa pelos dois filtros. Foi medido: dois
    reinícios do daemon, com a Steam FECHADA, carimbaram `audio_do_jogo` com a
    MESMA amostra (`flag0 0xA0 · alto-falante 100 · rota 0x30`).

    Ou seja: este teste prova que o carimbo respeita o gate — **não** que o
    gate separa jogo de kernel. Ele não separa. Ver "A REFUTAÇÃO DO VEREDITO"
    em `docs/process/sprints/2026-08-01-PARIDADE-SONY-01-*.md`.

    Fica como está, de propósito: o gate segue sendo o certo a exigir (é o
    mesmo da REPLICA-03, e dois gates divergiriam), e a mordida segue válida.
    O que muda é o que se pode CONCLUIR daqui — e é a terceira encarnação da
    lição da casa: **um teste que passa não prova que a pergunta é a certa.**

    Mordida: tirar o `self._replicating()` da condição do carimbo.
    """
    pad = _vpad_mudo()
    # Sem sessão de jogo: é exatamente o estado do probe do kernel.
    pad._game_open = False
    pad._bound_at = pad.time_fn() - 3600

    pad._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s, (
        "escrita de áudio FORA de uma sessão de jogo é o kernel adotando o "
        "device — carimbar isso faria o portão da sprint dar um falso 'sim'"
    )
    # E o carimbo de OUTPUT continua saindo: ele mede outra coisa (alguém
    # está escrevendo no hidraw deste vpad), e essa resposta é verdadeira.
    assert uhid.ATIVIDADE_OUTPUT in pad.visto_ha_s


def test_bits_de_audio_ligados_com_bytes_zerados_nao_contam() -> None:
    """A armadilha 10 da sprint: keepalive não é intenção.

    Bits ligados com os quatro bytes em zero é o jogo mantendo a autoridade
    sobre o bloco, não pedindo volume. Contar isso como "o jogo quer áudio"
    levaria a replicar "volume zero" ao controle dela a 60 Hz — a mesma classe
    de defeito que o `AUDIO-OWNER-01` curou noutro lugar deste projeto, e que
    o keepalive de vibração do `GUERRA-01` já produziu de verdade.

    Mordida: tirar o `any(...)` da condição.
    """
    pad = _vpad_em_jogo()

    pad._handle_output(_corpo_de_audio(0xF0, (0, 0, 0, 0)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s, (
        "bits ligados com bytes zerados é KEEPALIVE — replicar isso mandaria "
        "volume zero ao controle dela"
    )


def test_report_sem_os_bits_de_audio_nao_conta() -> None:
    """E um report de vibração com lixo nos bytes 4-7 também não.

    Sem os bits de autorização, aqueles bytes não são áudio: o firmware os
    ignora, e nós também temos de ignorar.

    Mordida: tirar o teste de `_AUDIO_FLAGS_DO_JOGO` da condição.
    """
    pad = _vpad_em_jogo()

    pad._handle_output(_corpo_de_audio(0x01, (99, 99, 99, 99)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s


def test_a_amostra_diz_quais_bytes_o_jogo_escreveu() -> None:
    """PARIDADE-SONY-01 — o dado que DESTRANCA a E2.

    O veredito do portão, em 02/08, foi "sim, alguém escreve áudio durante uma
    sessão". E a sprint trancou a E2 na pergunta seguinte, com todas as letras:

        *"Ainda não medido: o que exatamente foi escrito (quais dos quatro
        bytes, com que valores). (...) A E2 não deve começar antes disso.
        Replicar sem saber QUAL byte o jogo escreve é o mesmo erro de sempre,
        com o carimbo dando falsa confiança."*

    O carimbo responde QUANDO; esta amostra responde O QUÊ. Sem ela a E2
    escolheria no escuro qual dos quatro campos replicar — e o `common[7]`
    (roteamento) tem VETO escrito na sprint, porque ninguém sabe o valor
    neutro dele. Uma amostra distingue "o jogo pediu volume" de "o jogo mudou
    a rota do áudio", e são coisas muito diferentes de replicar.

    Mordida: apagar a atribuição de `_audio_do_jogo_amostra` do
    `_handle_output`, ou trocar a ordem de dois dos quatro bytes.
    """
    pad = _vpad_em_jogo()
    assert pad.audio_do_jogo_amostra is None, (
        "sem escrita nenhuma, a amostra tem de ser ausente — publicar zeros "
        "faria a E2 ler 'o jogo pediu volume 0', que é mandar MUDO"
    )

    # Fone 10, alto-falante 180, mic 0, rota 2 — os quatro valores distintos
    # de propósito: uma amostra que troque dois campos de lugar reprova aqui.
    pad._handle_output(_corpo_de_audio(0x20, (10, 180, 0, 2)))

    assert pad.audio_do_jogo_amostra == {
        "flag0": 0x20,
        "fone": 10,
        "alto_falante": 180,
        "microfone": 0,
        "rota": 2,
    }


def test_a_amostra_obedece_as_mesmas_guardas_do_carimbo() -> None:
    """Keepalive e probe do kernel não entram na amostra — nem no carimbo.

    Se a amostra tivesse guarda própria, ela e o carimbo divergiriam sobre o
    que é "durante um jogo" — que é exatamente o erro que o veredito do portão
    documenta ter cometido uma vez, e cuja cura foi *reusar* o `_replicating()`
    da REPLICA-03 em vez de escrever um segundo gate.

    Uma amostra que sobrevive ao keepalive é pior que amostra nenhuma: ela diz
    "o jogo pediu volume 0" quando o jogo não pediu nada, e mandar 0 ao
    controle é mandar MUDO (armadilha 10 da sprint).

    Mordida: tirar a atribuição da amostra de dentro do `if` do carimbo.
    """
    # (a) keepalive: bits ligados, bytes zerados.
    keepalive = _vpad_em_jogo()
    keepalive._handle_output(_corpo_de_audio(0xF0, (0, 0, 0, 0)))
    assert keepalive.audio_do_jogo_amostra is None

    # (b) probe do kernel: valores de verdade, mas fora de sessão de jogo.
    probe = _vpad_mudo()
    probe._game_open = False
    probe._bound_at = probe.time_fn() - 3600
    probe._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))
    assert probe.audio_do_jogo_amostra is None, (
        "o que o kernel escreve no probe não é pedido de jogo — amostrar isso "
        "faria a E2 replicar a INICIALIZAÇÃO do kernel ao controle físico"
    )


def test_a_amostra_nao_sobrevive_ao_stop(tmp_path: Any) -> None:
    """A amostra morre com o device, como os carimbos que ela acompanha.

    Um `alto_falante=180` herdado da vida anterior do vpad seria medição de um
    device que não existe mais — e a E2 seria decidida sobre bytes que outro
    gamepad virtual recebeu.

    O `stop()` é chamado DE VERDADE (com um fd de arquivo no lugar do
    `/dev/uhid`, que o `contextlib.suppress(OSError)` do próprio método
    absorve): um teste que repetisse o bloco de reset à mão passaria com a
    linha arrancada do produto, que é a definição de teste que não morde.

    Mordida: apagar a linha que zera `_audio_do_jogo_amostra` no `stop()`.
    """
    import os

    pad = _vpad_em_jogo()
    pad._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))
    assert pad.audio_do_jogo_amostra is not None

    pad._fd = os.open(tmp_path / "uhid-falso", os.O_RDWR | os.O_CREAT)
    pad.stop()

    assert pad.audio_do_jogo_amostra is None
    # E o carimbo que ela acompanha morreu junto — os dois são a mesma
    # medição, e um sobreviver ao outro seria a divergência que o veredito do
    # portão já documenta ter custado uma leitura errada.
    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s
