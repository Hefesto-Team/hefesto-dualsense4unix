"""A luz só acende se alguém DE FORA estiver ouvindo — LUZ-DO-MIC-01, PEÇA A.

O risco central desta peça está escrito na §3 da sprint e é curto: **se o
medidor de nível do próprio Hefesto contar como ouvinte, a luz acende sozinha
e não apaga nunca.** Todo teste de exclusão aqui é sobre isso, e cada um MORDE
uma regra diferente — porque a forma do stream irmão foi vista mudar duas vezes
no mesmo dia (``parec`` pulse, com PID; ``pw-cat`` nativo, sem PID nenhum), e
uma exclusão de uma regra só morre calada na forma que ela não previu.

Os blocos de ``pactl`` deste arquivo têm a ESTRUTURA medida em 03/09/2026 nesta
máquina (indentação, ordem dos campos, aspas nos valores, a linha ``balance``
sem dois-pontos). O que foi trocado são as identidades: MAC com a máscara da
casa (octetos 4 e 5 zerados), sem nome de máquina e sem nome de usuária.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import eleicao_de_microfone
from hefesto_dualsense4unix.integrations import quem_ouve_o_microfone as qom
from hefesto_dualsense4unix.integrations.fontes_de_captura import CasamentoUSB

#: Os dois controles da mesa medida: um no cabo, um no rádio. Máscara da casa.
UNIQ_CABO = "aa:bb:cc:00:00:ab"
UNIQ_RADIO = "aa:bb:cc:00:00:f0"

#: A saída curta MEDIDA nesta máquina, com os índices reais (598..603). A fonte
#: do DualSense é a 600; a 599 é o MONITOR da saída dele, que
#: `fontes_dualsense` descarta de propósito.
SOURCES_SHORT = (
    "598\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\t"
    "PipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
    "599\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40.monitor\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    "600\talsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "601\talsa_input.usb-046d_HD_Pro_Webcam_C920-02.analog-stereo\t"
    "PipeWire\ts16le 2ch 32000Hz\tSUSPENDED\n"
)

FONTE_DO_DUALSENSE = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.iec958-stereo"
)

#: A mesa de DOIS CANAIS — um por controle, que é o modelo da §1.2 da sprint.
#: Hoje o PipeWire publica um canal só (o do cabo); esta saída é a forma que a
#: ponte de mic por Bluetooth já sabe produzir hoje
#: (``fontes_de_captura.PREFIXO_SOURCE_PONTE_BT``, com o rabo hex do MAC), e é
#: também a forma que a CANAL-POR-CONTROLE-01 vai generalizar. Escrever a mesa
#: de dois aqui é o que permite medir a pergunta que a mesa de um NÃO alcança:
#: **a luz deste controle fala deste microfone, ou do sistema?**
FONTE_DO_CABO = "hefesto_dualsense_bt_0000ab"
FONTE_DO_RADIO = "hefesto_dualsense_bt_0000f0"

SOURCES_SHORT_DOIS_CANAIS = (
    "598\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\t"
    "PipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
    f"700\t{FONTE_DO_CABO}\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
    f"701\t{FONTE_DO_RADIO}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n"
)


def bloco(
    indice: int,
    fonte: int,
    props: dict[str, str],
    *,
    corked: bool = False,
) -> str:
    """Um bloco de `pactl list source-outputs` com a forma medida.

    A ordem e a indentação são as do comando real, inclusive a linha
    ``balance 0.00``, que não tem dois-pontos e já derrubou parser ingênuo.
    """
    linhas = [
        f"Source Output #{indice}",
        "\tDriver: PipeWire",
        "\tOwner Module: n/a",
        f"\tClient: {indice - 1}",
        f"\tSource: {fonte}",
        "\tSample Specification: s16le 1ch 16000Hz",
        "\tChannel Map: mono",
        '\tFormat: pcm, format.sample_format = "\\"s16le\\""  format.rate = "16000"',
        f"\tCorked: {'yes' if corked else 'no'}",
        "\tMute: no",
        "\tVolume: mono: 65536 / 100% / 0.00 dB",
        "\t        balance 0.00",
        "\tBuffer Latency: 0 usec",
        "\tSource Latency: 0 usec",
        "\tResample method: PipeWire",
        "\tProperties:",
    ]
    linhas += [f'\t\t{chave} = "{valor}"' for chave, valor in props.items()]
    return "\n".join(linhas) + "\n"


#: Um app de terceiro gravando da FONTE PADRÃO — e o ponto é o que ele NÃO tem.
#: Medido: um cliente que não pede device explícito sai SEM `target.object`, e
#: a fonte padrão desta máquina é justamente o microfone do DualSense. Quem
#: escrever o elo com `target.object` fica cego exatamente aqui.
ALHEIO_SEM_TARGET = bloco(
    1500,
    600,
    {
        "client.api": "pipewire-pulse",
        "application.name": "Google Chrome input",
        "media.name": "Chrome input",
        "application.process.id": "999001",
        "application.process.binary": "chrome",
        "pulse.corked": "false",
        "node.name": "Google Chrome input",
        "media.class": "Stream/Input/Audio",
    },
)

#: O medidor da PEÇA B na forma `parec` pulse: tem papel, id e PID.
MEDIDOR_PULSE = bloco(
    1352,
    600,
    {
        "client.api": "pipewire-pulse",
        "application.name": "hefesto-medidor-de-nivel",
        "media.name": "luz-do-mic",
        "application.id": "br.dev.hefesto.luz_do_mic",
        "hefesto.papel": "medidor-de-nivel",
        "hefesto.uniq": "aabbcc0000ab",
        "application.process.id": "999002",
        "application.process.binary": "pacat",
        "pulse.corked": "false",
        "resample.peaks": "true",
        "node.name": "hefesto-medidor-de-nivel",
    },
)

#: O MESMO medidor na forma PipeWire nativa: sem `application.process.id`, sem
#: `application.id`, sem `client.api`. Sobram `application.name` e `node.name`
#: — e é por isso que o crivo não pode ser o PID.
MEDIDOR_NATIVO = bloco(
    1428,
    600,
    {
        "application.name": "hefesto-medidor-de-nivel",
        "node.name": "hefesto-luz-do-mic",
        "media.type": "Audio",
        "media.category": "Capture",
        "resample.peaks": "true",
        "target.object": "600",
        "media.class": "Stream/Input/Audio",
    },
)

#: O `parec` da JANELA (`app/mic_monitor.py`), que sai CRU: nome `parec`, igual
#: ao `parec` de qualquer outro programa. Só a árvore de processos o denuncia.
PAREC_DA_JANELA = bloco(
    1200,
    600,
    {
        "client.api": "pipewire-pulse",
        "application.name": "parec",
        "media.name": "parec",
        "application.process.id": "700",
        "application.process.binary": "pacat",
        "node.name": "parec",
    },
)


def _proc_falso(tmp_path: Path, arvore: dict[int, tuple[int, str]]) -> Path:
    """Monta um `/proc` de mentira: `{pid: (ppid, cmdline)}`.

    O `stat` sai com a forma do kernel — o `comm` entre parênteses no campo 2,
    o `ppid` no campo 4 — e o `comm` leva espaço e parêntese de propósito.
    """
    raiz = tmp_path / "proc"
    for pid, (ppid, cmdline) in arvore.items():
        pasta = raiz / str(pid)
        pasta.mkdir(parents=True)
        (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode())
        (pasta / "stat").write_text(
            f"{pid} (nome (com) espaco) S {ppid} 0 0 0 -1 0\n", encoding="utf-8"
        )
    return raiz


def _falar_pactl(monkeypatch: pytest.MonkeyPatch, respostas: dict[str, tuple[int, str]]) -> None:
    """Faz o `pactl` do módulo responder o que o teste mandar.

    A chave é o subcomando (`source-outputs`, `sources short`), e ninguém sai
    do processo: este arquivo não toca no áudio da máquina dela.
    """

    def falso(argv: list[str]) -> tuple[int, str]:
        chave = " ".join(argv[1:])
        return respostas.get(chave, (127, ""))

    monkeypatch.setattr(qom, "_rodar", falso)
    monkeypatch.setattr(qom, "casamento_usb_agora", lambda uniqs: None)


# --------------------------------------------------------------------------
# O ELO COM A FONTE: `Source: <índice>`, nunca `target.object`
# --------------------------------------------------------------------------


def test_o_elo_com_a_fonte_e_o_indice_e_nao_o_target_object() -> None:
    """Um app SEM `target.object` continua sendo ouvinte da fonte 600.

    Esta é a armadilha central da leitura, e ela é silenciosa: quem casar o
    stream com a fonte por `target.object` fica verde no teste em que alguém
    passa um device explícito e CEGO para o app que grava da fonte padrão —
    que nesta máquina é o microfone do DualSense.
    """
    assert "target.object" not in ALHEIO_SEM_TARGET
    ouvindo, _ = ouvintes(ALHEIO_SEM_TARGET)
    assert ouvindo == {FONTE_DO_DUALSENSE: ["Google Chrome input"]}


def ouvintes(
    saida: str, raiz_proc: Path | str = "/proc"
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Atalho: os dois mapas por nome de fonte, com a saída curta medida."""
    return qom.ouvintes_por_fonte(saida, SOURCES_SHORT, raiz_proc)


def test_o_mapa_de_indices_le_a_coluna_1_da_saida_curta() -> None:
    """`{índice: nome}` — o elo que não existia na casa até hoje."""
    mapa = qom.nomes_de_fonte_por_indice(SOURCES_SHORT)
    assert mapa[600] == FONTE_DO_DUALSENSE
    assert mapa[601].startswith("alsa_input.usb-046d")
    assert 604 not in mapa


def test_linha_ilegivel_na_saida_curta_e_pulada_e_nao_chutada() -> None:
    """Linha sem índice numérico não vira entrada com índice inventado."""
    mapa = qom.nomes_de_fonte_por_indice("lixo\nsem\ttab-numerico\n600\tnome\n")
    assert mapa == {600: "nome"}


def test_stream_de_fonte_desconhecida_e_descartado() -> None:
    """Índice que não casa com fonte nenhuma não é atribuído por proximidade."""
    orfao = bloco(1501, 977, {"application.name": "Fantasma"})
    ouvindo, pausados = ouvintes(orfao)
    assert ouvindo == {}
    assert pausados == {}


# --------------------------------------------------------------------------
# O PARSER: a forma medida do `pactl`, e o que ela tem de armadilha
# --------------------------------------------------------------------------


def test_o_parser_le_indice_fonte_e_propriedades_do_bloco_medido() -> None:
    """A forma real: `Source Latency:` não pode ser confundido com `Source:`."""
    (stream,) = qom.streams_de_captura(ALHEIO_SEM_TARGET)
    assert stream.indice == 1500
    assert stream.fonte == 600
    assert stream.corked is False
    assert stream.nome_do_cliente == "Google Chrome input"
    assert stream.pid == 999001
    assert stream.props["application.process.binary"] == "chrome"


def test_saida_vazia_e_ninguem_capturando_e_nao_erro() -> None:
    """`rc=0` com zero byte é resposta: ninguém está com o microfone aberto."""
    assert qom.streams_de_captura("") == []


def test_a_saida_traduzida_nao_produz_bloco_nenhum() -> None:
    """Por que o `LC_ALL=C` não é opcional — o sintoma é uma lista VAZIA.

    No idioma dela o `pactl` responde `Saída da fonte #`, `Fonte:` e
    `Cork: não`. Um leitor sem o ambiente C lê zero blocos e devolve "ninguém
    está ouvindo", que é uma resposta plausível e falsa. Este teste fixa o
    sintoma; quem impede é o `_rodar` blindado, no teste seguinte.
    """
    traduzido = (
        "Saída da fonte #1500\n"
        "\tFonte: 600\n"
        "\tCork: não\n"
        "\tPropriedades:\n"
        '\t\tapplication.name = "Google Chrome input"\n'
    )
    assert qom.streams_de_captura(traduzido) == []


def test_a_leitura_usa_o_pactl_blindado_da_casa() -> None:
    """O `pactl` sai por `_rodar`, que põe `LC_ALL=C` e tem tempo limite.

    Reimplementar a chamada aqui criaria a segunda régua sobre o mesmo estado —
    e a primeira coisa que a cópia perderia é justamente o ambiente C.
    """
    assert qom._rodar is eleicao_de_microfone._rodar


def test_o_ambiente_c_chega_de_verdade_ao_pactl(monkeypatch: pytest.MonkeyPatch) -> None:
    """O antídoto da armadilha 2 tem de CHEGAR ao processo, não só existir.

    O teste acima prova que esta peça não reimplementou a chamada; ele NÃO
    prova que a chamada blindada continua blindada. Medido arrancando as duas
    linhas de ``_ambiente_c``: os 43 testes deste arquivo ficavam verdes com o
    ``LC_ALL`` fora — e o produto passaria a ler ``Saída da fonte #`` e a
    responder "ninguém está ouvindo" para sempre, sem erro nenhum.

    A régua vive AQUI, e não só do lado da eleição, porque é o cabeçalho deste
    módulo que promete o antídoto: quem herda a promessa herda a prova.
    """
    ambiente_visto: dict[str, str] = {}

    class _Proc:
        returncode = 0
        stdout = ""

    def _run(argv: list[str], **kwargs: Any) -> _Proc:
        ambiente_visto.update(kwargs["env"])
        return _Proc()

    monkeypatch.setattr(eleicao_de_microfone.shutil, "which", lambda nome: f"/usr/bin/{nome}")
    monkeypatch.setattr(eleicao_de_microfone.subprocess, "run", _run)

    assert qom._rodar(["pactl", "list", "source-outputs"]) == (0, "")
    assert ambiente_visto.get("LC_ALL") == "C", "o pactl responderia traduzido"
    assert ambiente_visto.get("LANG") == "C"


def test_bloco_sem_campo_de_fonte_e_descartado() -> None:
    """Sem `Source:` não há a que atribuir o ouvinte — e não se chuta."""
    sem_fonte = 'Source Output #1502\n\tCorked: no\n\tProperties:\n\t\tapplication.name = "X"\n'
    assert qom.streams_de_captura(sem_fonte) == []


# --------------------------------------------------------------------------
# A EXCLUSÃO DO NOSSO STREAM — o risco central, uma regra por vez
# --------------------------------------------------------------------------


def test_o_medidor_pulse_nao_conta_como_ouvinte() -> None:
    """A forma `parec` do medidor da PEÇA B sai da conta."""
    ouvindo, pausados = ouvintes(MEDIDOR_PULSE)
    assert ouvindo == {}
    assert pausados == {}


def test_o_medidor_nativo_tambem_nao_conta_como_ouvinte() -> None:
    """A forma `pw-cat` não publica PID nenhum — e ainda assim sai da conta.

    É a junta entre a PEÇA A e a PEÇA B: uma exclusão escrita por PID daria
    verde no teste da forma pulse e deixaria a luz acesa para sempre na forma
    nativa, sem nenhum teste de nenhuma das duas peças reprovar.
    """
    (stream,) = qom.streams_de_captura(MEDIDOR_NATIVO)
    assert stream.pid is None
    assert qom.e_stream_do_hefesto(stream) is True


@pytest.mark.parametrize(
    ("chave", "valor"),
    [
        ("hefesto.papel", "medidor-de-nivel"),
        ("hefesto.uniq", "aabbcc0000ab"),
        ("application.id", "br.dev.hefesto.luz_do_mic"),
        ("application.name", "hefesto-medidor-de-nivel"),
        ("node.name", "hefesto-luz-do-mic"),
        (qom.CHAVE_DO_MODO_DE_PICO, "true"),
    ],
)
def test_cada_marca_sozinha_ja_exclui_o_stream(chave: str, valor: str) -> None:
    """Cinco redes independentes, e cada uma pega sozinha.

    Independentes porque a forma do stream irmão ainda não está fixada: a
    nativa não tem `application.id` nem PID, a pulse tem tudo. Uma rede só
    seria uma aposta em qual das duas vence.
    """
    stream = qom.StreamDeCaptura(indice=1, fonte=600, corked=False, props={chave: valor})
    assert qom.e_stream_do_hefesto(stream) is True


def test_o_modo_de_pico_exclui_ate_medidor_de_terceiro() -> None:
    """`resample.peaks` é INTRÍNSECO, não convenção nossa.

    Um stream em modo de pico recebe `max|x|` por bloco — um envelope, não
    áudio. Ele estruturalmente não consegue ouvir o que ela diz, seja de quem
    for, e por isso não é ouvinte.
    """
    medidor_alheio = qom.StreamDeCaptura(
        indice=2,
        fonte=600,
        corked=False,
        props={"application.name": "VU Meter", "resample.peaks": "true"},
    )
    assert qom.e_stream_do_hefesto(medidor_alheio) is True


def test_app_alheio_com_nome_parecido_continua_contando() -> None:
    """A exclusão não pode ser um peneirão: quem não é nosso conta."""
    alheio = qom.StreamDeCaptura(
        indice=3,
        fonte=600,
        corked=False,
        props={"application.name": "parec", "application.id": "org.exemplo.gravador"},
    )
    assert qom.e_stream_do_hefesto(alheio) is False


def test_o_parec_cru_da_janela_e_pego_pela_arvore_de_processos(tmp_path: Path) -> None:
    """O buraco que nenhuma marca alcança — e o sintoma seria acusar a aba.

    A janela do Hefesto já captura hoje, e o `parec` que ela lança sai sem
    marca nenhuma. Sem esta rede, abrir a aba Status acenderia a luz — e isso
    se lê como *"a aba está me espionando"*, não como *"a régua é curta"*.
    """
    raiz = _proc_falso(
        tmp_path,
        {
            700: (701, "parec --device=alsa_input.usb-Sony"),
            701: (1, "/usr/bin/python3 -m hefesto_dualsense4unix.app"),
        },
    )
    ouvindo, _ = ouvintes(PAREC_DA_JANELA, raiz)
    assert ouvindo == {}


def test_parec_alheio_com_a_mesma_cara_continua_contando(tmp_path: Path) -> None:
    """A mordida do teste acima: o `parec` de OUTRO programa não sai da conta."""
    raiz = _proc_falso(
        tmp_path,
        {
            700: (701, "parec --device=alsa_input.usb-Sony"),
            701: (1, "/usr/bin/gravador-de-voz"),
        },
    )
    ouvindo, _ = ouvintes(PAREC_DA_JANELA, raiz)
    assert ouvindo == {FONTE_DO_DUALSENSE: ["parec"]}


def test_a_subida_pela_arvore_de_processos_tem_teto(tmp_path: Path) -> None:
    """Sem teto a regra pegaria a máquina inteira.

    O `systemd --user` é ancestral de tudo o que ela roda; se um dia o nome do
    Hefesto aparecer num ancestral remoto, subir sem limite excluiria todo
    stream da sessão dela — e a luz nunca mais acenderia.
    """
    arvore: dict[int, tuple[int, str]] = {}
    for pid in range(800, 808):
        arvore[pid] = (pid + 1, "/usr/bin/inocente")
    arvore[808] = (1, "/usr/bin/hefesto-dualsense4unix daemon start")
    raiz = _proc_falso(tmp_path, arvore)
    assert qom.descende_do_hefesto(800, raiz) is False
    assert qom.descende_do_hefesto(806, raiz) is True


def test_o_ppid_e_lido_depois_do_ultimo_parenteses(tmp_path: Path) -> None:
    """O `comm` do kernel leva espaço e parêntese — cortar no primeiro erra."""
    raiz = _proc_falso(tmp_path, {900: (901, "filho"), 901: (1, "hefesto-vivo")})
    assert qom._ppid(900, raiz) == 901


def test_proc_ausente_nao_levanta_e_responde_nao(tmp_path: Path) -> None:
    """Ausência é resposta: sem `/proc` legível, o stream não é nosso por aqui."""
    assert qom.descende_do_hefesto(4242, tmp_path / "nao-existe") is False
    assert qom.descende_do_hefesto(None) is False


def test_a_peca_a_reconhece_o_que_a_peca_b_realmente_declara() -> None:
    """O ENCONTRO das duas peças — e é este teste que impede a luz acesa eterna.

    O defeito da junta não mora dentro de peça nenhuma: cada uma passa nos
    próprios testes e a luz acende sozinha. A única régua que o pega é a que
    pergunta à PEÇA B o que ela publica DE VERDADE e manda a PEÇA A julgar.

    Ele já pagou por si: escrito, ele mostrou que as duas peças tinham
    inventado nomes diferentes um do outro (`br.com.hefesto.dualsense4unix`
    contra `br.dev.hefesto.luz_do_mic`, `nivel-do-mic` contra
    `medidor-de-nivel`). A cura não foi combinar a string — foi a PEÇA A parar
    de combinar nome e passar a reconhecer o ESPAÇO DE NOME.
    """
    nivel = pytest.importorskip(
        "hefesto_dualsense4unix.integrations.nivel_do_microfone",
        reason="a PEÇA B nasce na mesma leva; sem ela não há junta a medir",
    )
    props = nivel.propriedades_do_medidor("aabbcc0000ab")
    stream = qom.StreamDeCaptura(indice=4, fonte=600, corked=False, props=props)
    assert qom.e_stream_do_hefesto(stream) is True, (
        f"a PEÇA A não reconheceu o que a PEÇA B publica: {props}"
    )


def test_a_peca_c_acha_esta_peca_pelo_endereco_que_ela_guarda() -> None:
    """A outra junta: o ENDEREÇO (módulo + nome) e o TIPO do retorno.

    O laço da luz não importa esta peça: ele guarda o caminho e o nome em
    duas constantes e resolve por ``importlib`` + ``getattr``
    (``luz_do_mic._da_peca``). Nada nas duas peças reprova quando esse
    endereço aponta para o vazio — o sintoma é um ``luz_do_mic_peca_sem_funcao``
    no journal dela e a luz apagada para sempre. É este teste que fecha isso,
    e ele já pagou por si duas vezes na leva de 03/09: o nome do lado da PEÇA C
    mudou enquanto as duas eram escritas.

    Por isso a régua lê o que a PEÇA C DECLARA — nunca uma string redigitada
    aqui — e aceita a constante do nome tanto como texto quanto como lista,
    que são as duas formas em que ela já apareceu. O que não se negocia é o
    fim da linha: o endereço tem de resolver numa função DESTE módulo, e ela
    tem de prometer ``dict``, porque o laço descarta em silêncio tudo o que
    não for ``dict``.
    """
    luz = pytest.importorskip(
        "hefesto_dualsense4unix.daemon.subsystems.luz_do_mic",
        reason="a PEÇA C nasce na mesma leva",
    )
    assert qom.__name__ == luz.MODULO_DE_QUEM_OUVE, (
        f"a PEÇA C procura a PEÇA A em {luz.MODULO_DE_QUEM_OUVE}, e ela mora em {qom.__name__}"
    )
    declarado = luz.NOME_DE_QUEM_OUVE
    nomes = [declarado] if isinstance(declarado, str) else list(declarado)
    escolhida = next((f for n in nomes if callable(f := getattr(qom, n, None))), None)
    assert escolhida is not None, f"a PEÇA C procura {nomes} e esta peça não tem nenhum"
    assert escolhida is qom.quem_ouve_agora
    anotado = escolhida.__annotations__["return"]
    assert "dict" in str(anotado), f"a PEÇA C só aceita dict; esta peça promete {anotado}"


# --------------------------------------------------------------------------
# PAUSADO NÃO É OUVINTE — e a decisão fica visível
# --------------------------------------------------------------------------


def test_stream_pausado_sai_do_mapa_de_ouvintes_e_entra_no_de_pausados() -> None:
    """`Corked: yes` é microfone aberto e PARADO — não é alguém te ouvindo.

    O caso `yes` não apareceu na mesa em 03/09; o campo foi lido e separado
    para que a PEÇA C possa decidir sem reabrir o parser.
    """
    parado = bloco(1503, 600, {"application.name": "Gravador"}, corked=True)
    ouvindo, pausados = ouvintes(parado)
    assert ouvindo == {}
    assert pausados == {FONTE_DO_DUALSENSE: ["Gravador"]}


# --------------------------------------------------------------------------
# A LEITURA INTEIRA: os três estados que ela tem de saber separar
# --------------------------------------------------------------------------


def test_nao_saber_nao_e_ninguem_ouvindo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `pactl` a resposta é `lida=False`, nunca a lista vazia.

    As duas se pareceriam na tela — a luz apagada —, e só uma delas é honesta.
    """
    _falar_pactl(monkeypatch, {})
    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.lida is False
    assert leitura.por_uniq == {}
    assert leitura.alguem_ouve(UNIQ_CABO) is None


def test_medi_e_ninguem_ouve_e_uma_lista_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rc=0` com corpo vazio: sei, e a resposta é ninguém."""
    _falar_pactl(
        monkeypatch,
        {"list source-outputs": (0, ""), "list sources short": (0, SOURCES_SHORT)},
    )
    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.lida is True
    assert leitura.por_uniq == {UNIQ_CABO: []}
    assert leitura.alguem_ouve(UNIQ_CABO) is False


def test_o_controle_do_radio_vai_para_sem_canal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem canal publicado não há o que medir — e isso não é "ninguém ouve".

    Medido em 03/09 com dois controles na mesa: o PipeWire publica UM canal de
    DualSense, o do cabo. Colapsar o rádio em `[]` faria a ausência de canal
    parecer defeito da luz (a §1.2 da sprint tem a nota).
    """
    monkeypatch.setattr(
        qom,
        "casamento_usb_agora",
        lambda uniqs: CasamentoUSB(
            por_uniq={UNIQ_CABO: "/sys/devices/usb3/3-1", UNIQ_RADIO: ""},
            por_no={FONTE_DO_DUALSENSE: "/sys/devices/usb3/3-1"},
        ),
    )

    def falso(argv: list[str]) -> tuple[int, str]:
        chave = " ".join(argv[1:])
        if chave == "list source-outputs":
            return (0, ALHEIO_SEM_TARGET + MEDIDOR_PULSE)
        if chave == "list sources short":
            return (0, SOURCES_SHORT)
        return (127, "")

    monkeypatch.setattr(qom, "_rodar", falso)

    leitura = qom.ler_quem_ouve([UNIQ_CABO, UNIQ_RADIO])
    assert leitura.por_uniq == {UNIQ_CABO: ["Google Chrome input"]}
    assert leitura.sem_canal == (UNIQ_RADIO,)
    assert leitura.alguem_ouve(UNIQ_CABO) is True
    assert leitura.alguem_ouve(UNIQ_RADIO) is None


def test_a_luz_de_um_controle_nao_fala_pelo_outro(monkeypatch: pytest.MonkeyPatch) -> None:
    """§1.2 da sprint: cada luz fala DAQUELE microfone, nunca do sistema.

    Este é o único teste do arquivo com DOIS canais na mesa, e é por isso que
    ele existe: com um canal só, uma peça que somasse os ouvintes de todas as
    fontes dá exatamente a mesma resposta que a peça certa. Medido arrancando
    a cura — trocando a atribuição por fonte pela soma de
    ``ouvindo.values()`` —, os 43 testes anteriores ficavam TODOS verdes, e o
    defeito que passava era o pior possível para ela: abrir o microfone de um
    controle acenderia a luz dos QUATRO.

    A mesa de dois canais é a de hoje pela ponte de Bluetooth e a de amanhã
    pela CANAL-POR-CONTROLE-01, e o casamento uniq→fonte aqui é o rabo hex do
    MAC (regra 2 de ``escolher_fonte``), não uma string combinada neste
    arquivo.
    """
    no_cabo = bloco(1600, 700, {"application.name": "Google Chrome input"})
    _falar_pactl(
        monkeypatch,
        {
            "list source-outputs": (0, no_cabo),
            "list sources short": (0, SOURCES_SHORT_DOIS_CANAIS),
        },
    )
    leitura = qom.ler_quem_ouve([UNIQ_CABO, UNIQ_RADIO])
    assert leitura.por_uniq == {UNIQ_CABO: ["Google Chrome input"], UNIQ_RADIO: []}
    assert leitura.sem_canal == ()
    assert leitura.alguem_ouve(UNIQ_CABO) is True
    assert leitura.alguem_ouve(UNIQ_RADIO) is False


def test_o_pausado_chega_a_peca_c_separado_e_por_uniq(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Corked: yes` sai do mapa de ouvintes E entra no de pausados, por uniq.

    A separação já era medida um nível abaixo (`ouvintes_por_fonte`), mas o
    mapa por ``uniq`` da leitura inteira não tinha régua nenhuma: apagar a
    linha que preenche ``pausados_por_uniq`` deixava os 43 testes verdes.
    Quem decide se pausado conta é a PEÇA C — e ela não pode decidir sobre um
    campo que chega sempre vazio.

    Um gravador com o microfone dela ABERTO e parado não é alguém ouvindo:
    ``alguem_ouve`` tem de dizer ``False``, não ``True``.
    """
    parado = bloco(1601, 700, {"application.name": "Gravador"}, corked=True)
    _falar_pactl(
        monkeypatch,
        {
            "list source-outputs": (0, parado),
            "list sources short": (0, SOURCES_SHORT_DOIS_CANAIS),
        },
    )
    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.por_uniq == {UNIQ_CABO: []}
    assert leitura.pausados_por_uniq == {UNIQ_CABO: ["Gravador"]}
    assert leitura.alguem_ouve(UNIQ_CABO) is False


def test_sem_fonte_de_dualsense_ninguem_tem_canal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum DualSense publicado: todo controle vai para `sem_canal`.

    E a terceira chamada de `pactl` (a longa, do casamento USB) nem acontece —
    não há o que casar.
    """
    chamadas: list[str] = []

    def falso(argv: list[str]) -> tuple[int, str]:
        chave = " ".join(argv[1:])
        chamadas.append(chave)
        if chave == "list source-outputs":
            return (0, "")
        if chave == "list sources short":
            return (0, "601\talsa_input.usb-046d_HD_Pro_Webcam_C920-02\tPipeWire\tx\tIDLE\n")
        return (127, "")

    monkeypatch.setattr(qom, "_rodar", falso)

    def nao_deveria(uniqs: list[str]) -> CasamentoUSB | None:
        raise AssertionError("o casamento USB não devia ser pedido sem fonte nenhuma")

    monkeypatch.setattr(qom, "casamento_usb_agora", nao_deveria)

    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.lida is True
    assert leitura.sem_canal == (UNIQ_CABO,)
    assert leitura.por_uniq == {}
    assert chamadas == ["list source-outputs", "list sources short"]


def test_a_mesa_vazia_nao_gasta_uma_chamada_de_pactl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem controle na mesa não há pergunta a fazer — e o laço roda a 1 Hz."""

    def nao_deveria(argv: list[str]) -> tuple[int, str]:
        raise AssertionError("sem controle na mesa não se chama o pactl")

    monkeypatch.setattr(qom, "_rodar", nao_deveria)
    leitura = qom.ler_quem_ouve([])
    assert leitura.lida is True
    assert leitura.por_uniq == {}


def test_o_uniq_vale_nos_dois_formatos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com e sem dois-pontos dão a mesma resposta — a armadilha 2 da sprint.

    Pedir com o formato errado não dá erro: dá silêncio, que se lê como "não
    há controle na mesa". A normalização vem do `escolher_fonte`, e este teste
    é o que impede alguém de introduzir um casamento por string crua aqui.
    """
    respostas = {
        "list source-outputs": (0, ALHEIO_SEM_TARGET),
        "list sources short": (0, SOURCES_SHORT),
    }
    _falar_pactl(monkeypatch, respostas)
    com_pontos = qom.quem_ouve_agora([UNIQ_CABO])
    sem_pontos = qom.quem_ouve_agora([UNIQ_CABO.replace(":", "")])
    assert com_pontos is not None and sem_pontos is not None
    assert list(com_pontos.values()) == [["Google Chrome input"]]
    assert list(sem_pontos.values()) == [["Google Chrome input"]]


def test_o_medidor_da_peca_b_nao_acende_a_luz_sozinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teste que a sprint pede com todas as letras, de ponta a ponta.

    Com o medidor da PEÇA B no ar — nas DUAS formas — e mais nada, a resposta
    para o controle dela tem de ser "ninguém está me ouvindo".
    """
    _falar_pactl(
        monkeypatch,
        {
            "list source-outputs": (0, MEDIDOR_PULSE + MEDIDOR_NATIVO),
            "list sources short": (0, SOURCES_SHORT),
        },
    )
    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.alguem_ouve(UNIQ_CABO) is False


def test_o_alheio_aparece_mesmo_com_o_nosso_medidor_no_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E a mordida do anterior: excluir o nosso não pode excluir o dela."""
    _falar_pactl(
        monkeypatch,
        {
            "list source-outputs": (0, MEDIDOR_PULSE + ALHEIO_SEM_TARGET + MEDIDOR_NATIVO),
            "list sources short": (0, SOURCES_SHORT),
        },
    )
    leitura = qom.ler_quem_ouve([UNIQ_CABO])
    assert leitura.por_uniq == {UNIQ_CABO: ["Google Chrome input"]}


def test_a_leitura_nao_abre_stream_de_captura(monkeypatch: pytest.MonkeyPatch) -> None:
    """Só comandos de LEITURA saem daqui.

    Abrir um stream prenderia o nó em `RUNNING` — e a régua passaria a medir a
    si mesma. Todo argv que sai deste módulo é `pactl list …`.
    """
    vistos: list[list[str]] = []

    def falso(argv: list[str]) -> tuple[int, str]:
        vistos.append(argv)
        chave = " ".join(argv[1:])
        if chave == "list sources short":
            return (0, SOURCES_SHORT)
        return (0, "")

    monkeypatch.setattr(qom, "_rodar", falso)
    monkeypatch.setattr(qom, "casamento_usb_agora", lambda uniqs: None)
    qom.quem_ouve_agora([UNIQ_CABO])
    assert vistos, "a leitura tem de perguntar alguma coisa"
    for argv in vistos:
        assert argv[0] == "pactl"
        assert argv[1] == "list", f"argv que não é leitura: {argv}"


def test_o_custo_e_de_tres_chamadas_no_pior_caso(monkeypatch: pytest.MonkeyPatch) -> None:
    """O alvo de custo da §3 é ~1 Hz sem processo permanente.

    O laço não pode crescer com o número de controles: uma chamada de
    `source-outputs` lista os streams de TODAS as fontes de uma vez, então
    quatro controles custam a mesma leitura que um.
    """
    contagem: dict[str, int] = {}

    def falso(argv: list[str]) -> tuple[int, str]:
        chave = " ".join(argv[1:])
        contagem[chave] = contagem.get(chave, 0) + 1
        if chave == "list sources short":
            return (0, SOURCES_SHORT)
        if chave == "list source-outputs":
            return (0, ALHEIO_SEM_TARGET)
        return (127, "")

    monkeypatch.setattr(qom, "_rodar", falso)
    monkeypatch.setattr(qom, "casamento_usb_agora", lambda uniqs: None)
    quatro = [UNIQ_CABO, UNIQ_RADIO, "aa:bb:cc:00:00:11", "aa:bb:cc:00:00:22"]
    qom.quem_ouve_agora(quatro)
    assert contagem == {"list source-outputs": 1, "list sources short": 1}


def test_o_modulo_nao_escreve_no_controle() -> None:
    """A PEÇA A só LÊ. Quem decide e escreve é a PEÇA C.

    A separação é o que permite as quatro peças serem construídas ao mesmo
    tempo — e o que impede esta régua de virar mais um dono do `common[8]`.
    """
    fonte = Path(qom.__file__).read_text(encoding="utf-8")
    for proibido in ("set_mic_led", "set_microphone_led", "common[8]", "hidraw"):
        assert proibido not in fonte, f"a PEÇA A não pode tocar em {proibido}"


def test_a_estrutura_e_dado_e_nao_texto(monkeypatch: pytest.MonkeyPatch) -> None:
    """A §3 pede `{uniq: [nomes dos clientes]}` — estrutura, não frase pronta."""
    _falar_pactl(
        monkeypatch,
        {
            "list source-outputs": (0, ALHEIO_SEM_TARGET),
            "list sources short": (0, SOURCES_SHORT),
        },
    )
    resposta = qom.quem_ouve_agora([UNIQ_CABO])
    assert isinstance(resposta, dict)
    assert resposta == {UNIQ_CABO: ["Google Chrome input"]}


def test_nao_sei_chega_a_peca_c_como_none_e_nao_como_dicionario_vazio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`None` e `{}` são coisas diferentes na porta da PEÇA C.

    `{}` faria o laço ler `dict.get(uniq)` → `None` por controle, que também é
    "não sei" — mas só por acidente. `None` diz a mesma coisa de propósito, e é
    o que o `_perguntar` já trata como peça que não respondeu.
    """
    _falar_pactl(monkeypatch, {})
    assert qom.quem_ouve_agora([UNIQ_CABO]) is None


def test_a_leitura_e_imutavel() -> None:
    """Congelada: quem consome não altera a leitura de quem produz."""
    leitura = qom.LeituraDeOuvintes()
    with pytest.raises(FrozenInstanceError):
        leitura.lida = False  # type: ignore[misc]


def test_o_nome_do_cliente_cai_para_node_name_quando_falta_o_primeiro() -> None:
    """Cliente nativo sem `application.name` ainda tem de ter nome na luz."""
    stream = qom.StreamDeCaptura(
        indice=5, fonte=600, corked=False, props={"node.name": "gravador-nativo"}
    )
    assert stream.nome_do_cliente == "gravador-nativo"


def test_pid_ilegivel_nao_levanta() -> None:
    """Propriedade estranha é ausência de dado, não exceção."""
    stream = qom.StreamDeCaptura(
        indice=6, fonte=600, corked=False, props={"application.process.id": "n/a"}
    )
    assert stream.pid is None
