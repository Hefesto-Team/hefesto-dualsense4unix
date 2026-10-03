"""BT-E-VPAD-01 — o que só existe no cabo, e os furos do gamepad virtual."""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid


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
    """Com o cabo, a fonte padrão É o controle — e o botão pode agir."""
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
    """Em caso de dúvida, False — e o chamador não mexe em nada."""
    bancada = _AudioDeBancada("none", "DualSense")
    assert bancada.real.fonte_padrao_e_o_controle() is False


def test_o_botao_do_mic_nao_muta_o_aparelho_de_terceiro() -> None:
    """O DEFEITO 1 continua fechado — por CONSTRUÇÃO, e não mais pelo gate.

    Este teste exigia a saída **(a)** da sprint: o `mic_button_loop` só agia
    quando `fonte_padrao_e_o_controle()` respondia sim. Ela caiu em 01/09/2026
    (MIC-DA-MESA-ELEICAO-01), por decisão dela e por duas medições:

    1. **A guarda não separava CONTROLES.** Ela pergunta por SUBSTRING
       "dualsense" (`integrations/audio_control.py`), logo responde *"a fonte
       padrão é ALGUM DualSense"*, nunca *"é ESTE"*. Numa mesa de quatro os
       quatro respondem `True` — e o gesto novo tem endereço.
    2. **Ela estava escrita de costas para o gesto novo.** Só deixava agir
       quando a fonte padrão JÁ era o controle, que é exatamente o caso em que
       ELEGER não teria efeito nenhum.

    **O que ela protegia continua protegido, e agora sem gate: o gesto não muta
    nada.** Ele ELEGE — troca qual fonte é o padrão do sistema. Não há caminho
    por onde o botão do controle silencie o microfone de um terceiro, porque
    não existe mais um `toggle_default_source_mute` no laço.

    A saída **(b)** — mutar o registrador do firmware — continua RECUSADA pelas
    três medições de 01/08, 03/08 e 19/08.

    **FATO SUBSTITUÍDO em 02/09/2026** (recitação-da-frase-derrubada). Esta
    docstring afirmava que escrever no
    `common[9]` "faz o kernel parar de alternar na borda". É falso, e o fonte C
    desta árvore diz o contrário: o kernel alterna `ds->mic_muted` a partir do
    BIT DO BOTÃO no report de ENTRADA
    (`dualsense_parse_report` em `assets/dkms/hid-playstation/hid-playstation.c`,
    `ds_report->buttons[2] & DS_BUTTONS2_MIC_MUTE`) e não consulta nada que o
    userspace escreva. Ele continua alternando.

    O que se perde ao afirmar o byte é a LEGIBILIDADE da borda, e isso é
    consequência de uma ESCOLHA desta casa: o detector lê o mudo do FIRMWARE
    (`status[1]` BIT(2), `JACK_STATUS_OFFSET` em `core/physical_report_reader.py`),
    não o botão.
    Fixar o `common[9]` cegaria o NOSSO leitor — e nem por completo, porque o
    keepalive é limitado à janela de confirmação de 2 s
    (`OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC`, em `core/backend_pydualsense.py`).

    Mordida: repor `toggle_default_source_mute` no laço — esta régua reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    nomes: set[str] = set()
    for fn in (hotkey.mic_button_loop, hotkey._eleger_ou_devolver):
        c = fn.__code__
        nomes.update(c.co_names)
        nomes.update(c.co_varnames)
        for const in c.co_consts:
            if const is fn.__doc__:
                continue
            if isinstance(const, str):
                nomes.add(const)
            elif hasattr(const, "co_names"):
                nomes.update(const.co_names)

    assert "toggle_default_source_mute" not in nomes, (
        "o botão do controle voltou a mutar o microfone padrão do sistema — "
        "que pode ser o aparelho de terceiro (BT-E-VPAD-01, defeito 1)"
    )
    assert "set_microphone_mute" not in nomes, (
        "o laço voltou a afirmar o mudo do FIRMWARE — a saída (b), recusada "
        "pelas medições de 01/08, 03/08 e 19/08"
    )


def test_ninguem_afirma_que_o_common9_para_o_kernel_de_alternar() -> None:
    """O kernel alterna na BORDA DO BOTÃO, e nada que escrevamos muda isso."""
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[2]
    marca_de_recitacao = "recitação-da-frase-derrubada"

    fonte_c = (raiz / "assets/dkms/hid-playstation/hid-playstation.c").read_text(
        encoding="utf-8", errors="replace"
    )
    trecho = re.search(
        r"btn_mic_state\s*=.*?ds->last_btn_mic_state\s*=\s*btn_mic_state;",
        fonte_c,
        re.S,
    )
    assert trecho is not None, "o bloco do botão do mic sumiu do hid-playstation.c"
    bloco = trecho.group(0)
    assert "ds_report->buttons[2]" in bloco, (
        "o kernel deixou de decidir pelo bit do botão no report de entrada — "
        "reveja a correção de 02/09/2026 antes de reescrever a recusa"
    )
    assert "ds->mic_muted = !ds->mic_muted" in bloco, (
        "o toggle de `ds->mic_muted` na borda sumiu do driver"
    )

    proibidas = ("parar de alternar", "deixa de alternar", "para de alternar")
    reincidentes: list[str] = []
    for pasta in ("src", "tests", "docs"):
        for arq in (raiz / pasta).rglob("*"):
            if arq.suffix not in {".py", ".md"} or not arq.is_file():
                continue
            if arq.resolve() == pathlib.Path(__file__).resolve():
                continue
            linhas = arq.read_text(encoding="utf-8", errors="replace").splitlines()
            for n, linha in enumerate(linhas, 1):
                if not any(p in linha for p in proibidas):
                    continue
                janela = "\n".join(linhas[max(0, n - 8) : n + 8])
                if marca_de_recitacao in janela:
                    continue
                if "common[9]" in janela or "kernel" in janela:
                    reincidentes.append(f"{arq.relative_to(raiz)}:{n}: {linha.strip()}")

    assert not reincidentes, (
        "voltou a afirmação que a auditoria de 02/09/2026 derrubou — o kernel "
        "NÃO para de alternar quando afirmamos o `common[9]`:\n"
        + "\n".join(reincidentes)
    )


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
    assert "Hefesto" in nome
    assert "P2" in nome


def test_o_byte_53_acompanha_o_fisico_em_vez_de_sair_fixo() -> None:
    """`HP_DETECT`, `MIC_DETECT` e `MIC_MUTE` — os três bits que faltavam."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=1, blueprint=None)

    corpo = pad._encode_body()
    assert corpo[uhid._STATUS1_OFFSET] == uhid._STATUS1_NEUTRO

    pad.forward_jack(0b101)
    corpo = pad._encode_body()
    assert corpo[uhid._STATUS1_OFFSET] == 0b101


def test_so_os_tres_bits_conhecidos_do_byte_53_sao_encaminhados() -> None:
    """O resto do byte é do firmware, e não é nosso para repassar."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=1, blueprint=None)
    pad.forward_jack(0xFF)

    assert pad._encode_body()[uhid._STATUS1_OFFSET] == 0b111


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
    """Um vpad com a sessão de jogo ABERTA e a graça pós-bind vencida."""
    pad = _vpad_mudo()
    pad._game_open = True
    pad._bound_at = pad.time_fn() - 3600
    return pad


def test_o_jogo_que_pede_audio_deixa_carimbo() -> None:
    """O portão de medição da PARIDADE-SONY-01, como instrumento PERMANENTE."""
    pad = _vpad_em_jogo()
    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s

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
    o `UHID_OPEN` que liga `_game_open` (em `UhidDualSense._handle_event`). O estado
    que este teste monta à mão é justamente o que a máquina nunca apresenta.

    Some-se a graça de `_GAME_REPLICA_GRACE_S` = **0,5 s**, dimensionada para o
    player-LED do probe (que é imediato), e a escrita de áudio do kernel — que
    chega ~10 s depois do bind — passa pelos dois filtros. Foi medido: dois
    reinícios do daemon, com a Steam FECHADA, carimbaram `audio_do_jogo` com a
    MESMA amostra (`flag0 0xA0 · alto-falante 100 · rota 0x30`).

    Ou seja: este teste prova que o carimbo respeita o gate — **não** que o
    gate separa jogo de kernel. Ele não separa. Ver "A REFUTAÇÃO DO VEREDITO"
    na sprint `PARIDADE-SONY-01`.

    Fica como está, de propósito: o gate segue sendo o certo a exigir (é o
    mesmo da REPLICA-03, e dois gates divergiriam), e a mordida segue válida.
    O que muda é o que se pode CONCLUIR daqui — e é a terceira encarnação da
    lição da casa: **um teste que passa não prova que a pergunta é a certa.**

    Mordida: tirar o `self._replicating()` da condição do carimbo.
    """
    pad = _vpad_mudo()
    pad._game_open = False
    pad._bound_at = pad.time_fn() - 3600

    pad._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s, (
        "escrita de áudio FORA de uma sessão de jogo é o kernel adotando o "
        "device — carimbar isso faria o portão da sprint dar um falso 'sim'"
    )
    assert uhid.ATIVIDADE_OUTPUT in pad.visto_ha_s


def test_bits_de_audio_ligados_com_bytes_zerados_nao_contam() -> None:
    """A armadilha 10 da sprint: keepalive não é intenção."""
    pad = _vpad_em_jogo()

    pad._handle_output(_corpo_de_audio(0xF0, (0, 0, 0, 0)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s, (
        "bits ligados com bytes zerados é KEEPALIVE — replicar isso mandaria "
        "volume zero ao controle dela"
    )


def test_report_sem_os_bits_de_audio_nao_conta() -> None:
    """E um report de vibração com lixo nos bytes 4-7 também não."""
    pad = _vpad_em_jogo()

    pad._handle_output(_corpo_de_audio(0x01, (99, 99, 99, 99)))

    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s


def test_a_amostra_diz_quais_bytes_o_jogo_escreveu() -> None:
    """PARIDADE-SONY-01 — o dado que DESTRANCA a E2."""
    pad = _vpad_em_jogo()
    assert pad.audio_do_jogo_amostra is None, (
        "sem escrita nenhuma, a amostra tem de ser ausente — publicar zeros "
        "faria a E2 ler 'o jogo pediu volume 0', que é mandar MUDO"
    )

    pad._handle_output(_corpo_de_audio(0x20, (10, 180, 0, 2)))

    assert pad.audio_do_jogo_amostra == {
        "flag0": 0x20,
        "fone": 10,
        "alto_falante": 180,
        "microfone": 0,
        "rota": 2,
    }


def test_a_amostra_obedece_as_mesmas_guardas_do_carimbo() -> None:
    """Keepalive e probe do kernel não entram na amostra — nem no carimbo."""
    keepalive = _vpad_em_jogo()
    keepalive._handle_output(_corpo_de_audio(0xF0, (0, 0, 0, 0)))
    assert keepalive.audio_do_jogo_amostra is None

    probe = _vpad_mudo()
    probe._game_open = False
    probe._bound_at = probe.time_fn() - 3600
    probe._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))
    assert probe.audio_do_jogo_amostra is None, (
        "o que o kernel escreve no probe não é pedido de jogo — amostrar isso "
        "faria a E2 replicar a INICIALIZAÇÃO do kernel ao controle físico"
    )


def test_a_amostra_nao_sobrevive_ao_stop(tmp_path: Any) -> None:
    """A amostra morre com o device, como os carimbos que ela acompanha."""
    import os

    pad = _vpad_em_jogo()
    pad._handle_output(_corpo_de_audio(0x20, (0, 180, 0, 0)))
    assert pad.audio_do_jogo_amostra is not None

    pad._fd = os.open(tmp_path / "uhid-falso", os.O_RDWR | os.O_CREAT)
    pad.stop()

    assert pad.audio_do_jogo_amostra is None
    assert uhid.ATIVIDADE_AUDIO_DO_JOGO not in pad.visto_ha_s
