"""SOM-ACORDADO-01 — os dois estados do som aparecem na aba Status.

A decisão dela, textual (16/08/2026, 00h): *"precisamos setar o som sempre em
todos os controles no 100% e garantir que sempre fique acordado e ligar isso a
interface na aba de status (config default)"*.

Este arquivo afere a metade **"ligar isso a interface"**. As duas outras metades
têm dono próprio: quem põe o volume é o daemon (a posse de `_volumes_audio`) e
quem impede o sono é o drop-in 54 do WirePlumber que o `install.sh` põe sem
flag (SOM-QUE-NAO-DORME-01). O que se prova aqui é que **a casa saber vira o
produto mostrar** — que é, nesta casa, o defeito mais caro que existe.

OS DOIS FATOS MEDIDOS QUE ORGANIZAM O ARQUIVO
----------------------------------------------

1. **A posse do volume é a causa do silêncio.** Com a orelha dela, no cabo, em
   15-16/08/2026: sem ninguém escrever volume o alto-falante fica MUDO (ela:
   "nenhum"); com `speaker volume 85`, o mesmo comando na mesma rota SOA (ela:
   "bep bep bep"); com volume 0, cala de novo (ela: "mudo"). Nada mais mudou
   entre as três passadas. É por isso que a tela precisa dizer **quem manda no
   volume**, e não só qual é o número.

2. **O PipeWire suspende o nó ocioso, e o religar come o começo do som.** Mesmo
   canal, mesmo volume, mesma rota: "não saiu" com o nó ocioso, "tuuuuuuuu" com
   ele acordado segundos depois. Três leituras daquela rodada foram descartadas
   por causa disto. A pergunta dela, textual: *"como garantimos durante um jogo
   que o som sempre saia?"*.

O DESENHO, E POR QUE ELE É O RÓTULO DA MOLDURA
-----------------------------------------------

Medido nesta bancada, com o card montado e ALOCADO numa `Gtk.OffscreenWindow`
(widget sem alocação devolve 1x1, e um teste de layout sobre ele passa com
qualquer desenho):

    =====================================  ============  =================
    desenho                                bloco mínimo  card mínimo
    =====================================  ============  =================
    hoje (`Alto-falante · 100 %`)          183 x 144     1040 x 429
    `... · acordado` no rótulo             186 x 144     1040 x 429
    um rótulo NOVO, sempre visível         183 x 163     1040 x 448
    =====================================  ============  =================

O rótulo da moldura custa **zero altura**. O rótulo novo custa 19px — e a
altura é o que não há: o `test_status_som_02_controle_de_volume` cobra que a
coluna do som não passe da maior coluna vizinha por mais de 12px. Foi um teste
desta casa que escolheu o desenho, e é a razão de o teste de geometria abaixo
existir: sem ele, o próximo a mexer aqui volta a gastar a altura que não tem.

Cada teste diz no docstring qual é a MORDIDA — o que arrancar do produto para
vê-lo em vermelho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules, e sem guarda nenhuma este módulo derruba a COLETA inteira no CI
# headless em vez de pular.
exigir_gi_real("som acordado 01")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.audio_saida import (
    CANAL_ACORDADO,
    CANAL_DORMINDO,
    CANAL_SEM_LEITURA,
    RotaDeSaida,
    acordar_sink,
    estado_do_canal,
    estados_crus_dos_sinks,
    estados_dos_sinks,
    tocar_confirmacao,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    DICA_CANAL_ACORDADO,
    DICA_CANAL_DORMINDO,
    DICA_CANAL_E_PADRAO,
    DICA_CANAL_SEM_A_REGRA,
    DICA_SPEAKER_POSSE_NOSSA,
    SUFIXO_CANAL_ACORDADO,
    SUFIXO_CANAL_DORMINDO,
    TEXTO_SELO_CANAL_DORMINDO,
    TEXTO_SELO_SAIDA_MUDA,
    TITULO_SPEAKER,
    ControllerCard,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: Os nomes REAIS dos dois sinks de DualSense desta bancada, copiados de
#: `pactl list sinks short` com dois controles no cabo. Nome inventado
#: esconderia o detalhe que importa: os dois só se distinguem pelo `.2`, que é
#: desempate posicional do PipeWire e NÃO é identidade.
SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
SINK_P2 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)
SINK_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"

#: A largura com que a janela ABRE. É o orçamento duro da aba Status.
LARGURA_DE_PROJETO = 1180

#: Volume com posse nossa. 255 é o que a decisão dela pede ("sempre no 100%"),
#: e é o número que o rótulo da moldura tem de mostrar como `100 %`.
POSSE_100: dict[str, Any] = {"volume": 255, "muted": False}

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080},
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}
_ESTADO: dict[str, Any] = {"native_mode": False}

#: A janela offscreen fica viva numa lista de módulo: o Python coleta a
#: referência local assim que a função retorna, e um card sem toplevel volta a
#: reportar 1x1 no meio da asserção.
_janelas_vivas: list[Any] = []


class _LeituraMic:
    """Dublê da `LeituraMic` — o card lê `nivel`, `muted` e `saida_muda`."""

    def __init__(self, saida_muda: bool | None = None) -> None:
        self.nivel = 0.6
        self.muted = False
        self.saida_muda = saida_muda


def _card(
    *,
    compact: bool = False,
    largura: int = LARGURA_DE_PROJETO,
    speaker: dict[str, Any] | None = None,
    canal: str = "",
    regra: bool | None = None,
    mic: Any = None,
) -> Any:
    """Card montado, alocado e com os dois estados do som já entregues."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    entrada = dict(_ENTRY)
    if speaker is not None:
        entrada["speaker"] = speaker
    card.update(entrada, _ESTADO, mic if mic is not None else _LeituraMic())
    card.definir_sink_de_saida(SINK_P1)
    card.definir_estado_do_canal(canal, regra_instalada=regra)
    janela.resize(largura, 900)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


def _lista_curta(**estados: str) -> str:
    """`pactl list sinks short` de mentira, no formato REAL de cinco colunas.

    Os cinco campos e a ordem são os desta máquina, conferidos com `cat -A`::

        35872<TAB>alsa_output...surround-40<TAB>PipeWire<TAB>s16le 4ch 48000Hz<TAB>SUSPENDED
    """
    linhas = [
        f"{100 + i}\t{nome}\tPipeWire\ts16le 4ch 48000Hz\t{estado}"
        for i, (nome, estado) in enumerate(estados.items())
    ]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Parte 1 — a LEITURA: a coluna que ninguém lia
# ---------------------------------------------------------------------------


def test_o_estado_do_canal_sai_da_ultima_coluna_do_pactl() -> None:
    """`SUSPENDED` vira `dormindo`, `RUNNING` e `IDLE` viram `acordado`.

    `IDLE` conta como acordado de propósito, e não é generosidade: nele o nó
    continua ABERTO — o hardware não precisa ser religado, e é o religar que
    come o começo do som. O que a medição condena é a suspensão.

    Mordida: mapear `IDLE` para `dormindo`, ou ler `partes[4]` por índice fixo
    em vez do último campo. A primeira asserção cai.
    """
    saida = _lista_curta(
        **{SINK_P1: "SUSPENDED", SINK_P2: "RUNNING", SINK_HDMI: "IDLE"}
    )

    assert estados_dos_sinks(saida) == {
        SINK_P1: CANAL_DORMINDO,
        SINK_P2: CANAL_ACORDADO,
        SINK_HDMI: CANAL_ACORDADO,
    }
    assert estado_do_canal(saida, SINK_P1) == CANAL_DORMINDO
    assert estado_do_canal(saida, "sink_que_nao_existe") == CANAL_SEM_LEITURA
    assert estado_do_canal(saida, "") == CANAL_SEM_LEITURA


def test_linha_sem_a_coluna_de_estado_vira_nao_sei_e_nunca_acordado() -> None:
    """A armadilha desta casa: instrumento que mente é pior que instrumento mudo.

    Sem a quinta coluna, o "último campo" da linha é o DRIVER — e `PipeWire`
    lido como estado produziria uma resposta convincente e falsa. A resposta
    certa é "não sei", que é o que mantém o rótulo da moldura calado.

    Mordida: baixar a guarda de `len(partes) < 5` para `< 2` em
    `estados_crus_dos_sinks`. `PipeWire` entra no mapa cru, e qualquer mapeamento
    generoso amanhã o transforma numa afirmação sobre o som dela.
    """
    curta = f"1\t{SINK_P1}\tPipeWire\n"

    assert estados_crus_dos_sinks(curta) == {}
    assert estados_dos_sinks(curta) == {}
    assert estado_do_canal(curta, SINK_P1) == CANAL_SEM_LEITURA


def test_ha_um_parser_so_da_coluna_de_estado() -> None:
    """As duas vistas do mesmo dado saem do MESMO parser.

    A vista da tela quer o vocabulário da casa (`acordado`/`dormindo`); a vista
    do drop-in do WirePlumber quer o literal do `pactl` (`SUSPENDED`) para
    decidir se a regra pegou. São perguntas diferentes sobre a mesma coluna, e
    esta casa já pagou caro por leitores paralelos do mesmo dado.

    Mordida: dar a `sono_dos_sinks_do_controle` um laço próprio sobre as linhas.
    O teste continua passando hoje — e é por isso que a asserção é de
    IDENTIDADE de resultado sobre uma entrada que os separa: uma linha de
    quatro campos, que um laço novo quase certamente aceitaria.
    """
    saida = _lista_curta(**{SINK_P1: "SUSPENDED", SINK_HDMI: "RUNNING"})
    quatro_campos = f"9\t{SINK_P2}\tPipeWire\ts16le 4ch 48000Hz\n"

    crus = estados_crus_dos_sinks(saida + quatro_campos)
    assert crus == {SINK_P1: "SUSPENDED", SINK_HDMI: "RUNNING"}
    # A vista do sono é um FILTRO do mesmo mapa, não uma segunda leitura.
    assert audio_saida.sono_dos_sinks_do_controle(saida + quatro_campos) == {
        nome: cru for nome, cru in crus.items() if nome == SINK_P1
    }


def test_a_rota_traz_o_estado_de_todos_os_canais_numa_leitura_so() -> None:
    """Um leitor, um subprocesso, e o estado de TODOS os canais.

    É o que torna isto universal: 1 ou 7 controles custam a mesma leitura, e
    nada aqui depende de MAC, de ordem de conexão nem de número mágico. Ler por
    card seria um `pactl` por controle por ciclo — quatro por ciclo na mesa
    dela.

    Mordida: devolver `EstadoDaRota` sem `canais` (ou só quando o som já está
    no controle, que era como a lista viva era lida antes desta leva). A
    segunda asserção cai, e a aba perde o dado dos cards que NÃO são o alvo da
    rota.
    """
    chamadas: list[list[str]] = []

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return SINK_HDMI + "\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            return _lista_curta(
                **{SINK_P1: "RUNNING", SINK_P2: "SUSPENDED", SINK_HDMI: "IDLE"}
            )
        return ""

    estado = RotaDeSaida(
        runner=pactl, ler_memoria=lambda: "", gravar_memoria=lambda _s: None
    ).estado(SINK_P1)

    assert estado.no_controle is False, "o som está no HDMI — este é o caso comum"
    assert dict(estado.canais) == {
        SINK_P1: CANAL_ACORDADO,
        SINK_P2: CANAL_DORMINDO,
        SINK_HDMI: CANAL_ACORDADO,
    }, "o estado dos canais tem de vir mesmo com o som FORA do controle"
    listas = [a for a in chamadas if a[:3] == ["pactl", "list", "sinks"]]
    assert len(listas) == 1, (
        f"a lista viva foi lida {len(listas)} vezes num ciclo só: o estado dos "
        "canais tem de pegar carona na leitura que já existia"
    )


# ---------------------------------------------------------------------------
# Parte 2 — a REGRESSÃO DO BIPE: um som de 67 ms num nó suspenso
# ---------------------------------------------------------------------------


def test_o_som_de_confirmacao_acorda_o_canal_antes_de_tocar() -> None:
    """*"hoje em dia na interface nem por cabo esse bip tá saindo"* (dela).

    Os dois lados da conta são medidos, cada um do seu lado: o arquivo escolhido
    tem **0,067 s** (o mais curto dos candidatos, escolha registrada em
    `_CANDIDATOS_DE_SOM`), e o religar de um nó suspenso come o começo do som.
    Num som de 67 ms, "o começo" é o som inteiro — e a suspensão é o estado
    NORMAL entre dois gestos dela: os dois sinks de DualSense desta bancada
    estavam `SUSPENDED` na leitura de 16/08/2026, com os controles no cabo.

    Nada disto aparecia como falha: o `paplay` abria o fluxo, saía com zero, e
    o tocador devolvia `tocou`.

    Mordida: apagar as duas linhas do `set-sink-suspend` em `tocar_confirmacao`.
    A primeira asserção cai, e o produto volta a prometer um som que ninguém
    ouve — que é exatamente o que ela relatou.
    """
    chamadas: list[list[str]] = []
    dormindo = {"sim": True}

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:4] == ["pactl", "set-sink-suspend", SINK_P1, "0"]:
            dormindo["sim"] = False
        if argv[:3] == ["pactl", "list", "sinks"]:
            estado = "SUSPENDED" if dormindo["sim"] else "RUNNING"
            return _lista_curta(**{SINK_P1: estado, SINK_HDMI: "IDLE"})
        return ""

    tocados: list[list[str]] = []
    resultado = tocar_confirmacao(
        SINK_P1,
        saida_muda=False,
        ligado=True,
        runner=pactl,
        tocador=lambda argv: (tocados.append(argv), 0)[1],
        achar=lambda _b: "/usr/bin/paplay",
    )

    assert ["pactl", "set-sink-suspend", SINK_P1, "0"] in chamadas, (
        "o canal estava dormindo e ninguém o acordou: o som de 67 ms se perde "
        "no religar do hardware"
    )
    assert tocados, "e depois de acordar, o som TEM de sair"
    posicao_acordar = chamadas.index(["pactl", "set-sink-suspend", SINK_P1, "0"])
    assert posicao_acordar < len(chamadas), "acordar vem ANTES de tocar"
    assert resultado.tocou is True


def test_o_canal_ja_acordado_nao_paga_subprocesso_nenhum() -> None:
    """O caso comum não pode ficar mais caro por causa do caso raro.

    A lista viva já é lida no degrau 5 (a guarda do sink inexistente): o estado
    sai DELA, sem um `pactl` a mais, e o `set-sink-suspend` só roda no estado
    que precisa dele.

    Mordida: chamar `acordar_sink` sem olhar o estado antes. Este teste vê dois
    comandos de escrita que não deviam existir, e a cada gesto dela o produto
    passa a gastar dois subprocessos para não mudar nada.
    """
    chamadas: list[list[str]] = []

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:3] == ["pactl", "list", "sinks"]:
            return _lista_curta(**{SINK_P1: "RUNNING", SINK_HDMI: "IDLE"})
        return ""

    tocar_confirmacao(
        SINK_P1,
        saida_muda=False,
        ligado=True,
        runner=pactl,
        tocador=lambda _argv: 0,
        achar=lambda _b: "/usr/bin/paplay",
    )

    assert not [a for a in chamadas if a[:2] == ["pactl", "set-sink-suspend"]], (
        "o canal já estava acordado e o produto mandou acordá-lo assim mesmo"
    )
    assert len([a for a in chamadas if a[:3] == ["pactl", "list", "sinks"]]) == 1


def test_acordar_confere_relendo_em_vez_de_acreditar_no_pactl() -> None:
    """A janela que acredita na própria escrita é a janela que mente na tela.

    Mesma disciplina do `RotaDeSaida._trocar`: o `pactl` responde sem erro em
    casos em que a mudança não vale.

    Mordida: fazer `acordar_sink` devolver `True` logo depois do `set-sink-
    suspend`. A segunda asserção cai — o sink continuou suspenso e a função
    disse que acordou.
    """
    teimoso = _lista_curta(**{SINK_P1: "SUSPENDED"})

    assert (
        acordar_sink(SINK_P1, runner=lambda _a: _lista_curta(**{SINK_P1: "RUNNING"}))
        is True
    )
    assert acordar_sink(SINK_P1, runner=lambda _a: teimoso) is False
    assert acordar_sink("", runner=lambda _a: teimoso) is False


# ---------------------------------------------------------------------------
# Parte 3 — a TELA: os dois estados no bloco Alto-falante
# ---------------------------------------------------------------------------


def test_o_rotulo_da_moldura_diz_o_volume_e_o_canal() -> None:
    """*"ligar isso a interface na aba de status"* — e é aqui que ele aparece.

    `Alto-falante · 100 % · acordado`: o número só existe com POSSE (o daemon
    só publica a chave `speaker` enquanto nós mandamos o volume), então o
    rótulo diz as duas coisas que ela pediu de uma vez — que o volume é 100 e
    que quem o manda somos nós.

    Mordida: apagar o `partes.append(estado)` de `_titulo_do_speaker`. O rótulo
    volta a `Alto-falante · 100 %` e o canal desaparece da tela — a casa
    continua sabendo e o produto volta a não mostrar.
    """
    acordado = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=True)
    dormindo = _card(speaker=POSSE_100, canal=CANAL_DORMINDO, regra=True)

    assert acordado._speaker_titulo.get_text() == (
        f"{TITULO_SPEAKER} · 100 % · {SUFIXO_CANAL_ACORDADO}"
    )
    assert dormindo._speaker_titulo.get_text() == (
        f"{TITULO_SPEAKER} · 100 % · {SUFIXO_CANAL_DORMINDO}"
    )
    # O rótulo de valor continua sendo o DONO do número, cru e sem sufixo: é
    # ele que o card compacto mostra e é ele que os outros testes leem.
    assert acordado._speaker_label.get_text() == "100 %"


def test_sem_leitura_do_canal_a_moldura_fica_calada() -> None:
    """"" é **não sei**, e não "acordado".

    É o caso do RÁDIO, medido em 15/08/2026: pelo Bluetooth o DualSense não
    publica placa de som nenhuma, e não há canal a descrever. Afirmar
    "acordado" ali seria prometer que o som sai inteiro num controle que não
    tem por onde tocá-lo.

    Mordida: trocar o `if estado:` de `_titulo_do_speaker` por um sufixo
    padrão. O rótulo passa a afirmar um estado que ninguém leu.
    """
    sem_canal = _card(speaker=POSSE_100, canal="")

    assert sem_canal._speaker_titulo.get_text() == f"{TITULO_SPEAKER} · 100 %"
    assert SUFIXO_CANAL_ACORDADO not in sem_canal._speaker_titulo.get_text()
    assert not sem_canal._speaker_selo_saida.get_visible()


def test_o_selo_denuncia_o_canal_dormindo_e_a_saida_muda_vence() -> None:
    """O selo é o ALARME, e só acende no estado ruim.

    Ele não diz "acordado" em toda sessão normal: custaria 19px de altura para
    não informar nada, e a altura é o recurso que este bloco não tem (ver o
    teste de geometria abaixo). Quem diz o estado bom é o rótulo da moldura.

    A prioridade não é arbitrária: uma saída muda cala o som venha o canal de
    onde vier; um canal dormindo só come o começo. Ganha o fato que explica o
    silêncio ANTES do outro.

    Mordida: pôr o `elif dormindo` na frente do `if saida_muda` em
    `_aplicar_selo_do_som`. A última asserção cai, e o selo passa a apontar
    para a causa menor enquanto a maior fica escondida.
    """
    dormindo = _card(speaker=POSSE_100, canal=CANAL_DORMINDO, regra=True)
    assert dormindo._speaker_selo_saida.get_visible()
    assert dormindo._speaker_selo_saida.get_text() == TEXTO_SELO_CANAL_DORMINDO
    # O selo diz QUE; a dica do bloco diz POR QUÊ, com a medição inteira. É a
    # mesma disciplina do `Sem som`, e é o que mantém o selo curto o bastante
    # para não decidir a largura do card.
    assert DICA_CANAL_DORMINDO in dormindo._speaker_box.get_tooltip_text()

    acordado = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=True)
    assert not acordado._speaker_selo_saida.get_visible()

    os_dois = _card(
        speaker=POSSE_100,
        canal=CANAL_DORMINDO,
        regra=True,
        mic=_LeituraMic(saida_muda=True),
    )
    assert os_dois._speaker_selo_saida.get_text() == TEXTO_SELO_SAIDA_MUDA


def test_a_dica_do_bloco_diz_que_e_o_padrao_so_com_a_regra_no_lugar() -> None:
    """*"config default"* — a tela mostra o estado, não pede que ela ligue.

    E a frase do padrão é CONDICIONADA: um nó pode estar acordado por acaso
    (alguém acabou de tocar algo) com o drop-in do WirePlumber fora do lugar, e
    chamar isso de "é o padrão" seria a tela dando por curado o que só está
    momentaneamente de pé. Com a cura arrancada, a tela DENUNCIA — o sintoma
    no jogo é silencioso, e ninguém o descobre sozinho.

    Mordida: trocar o `if self._speaker_regra_do_sono is True` por um `if`
    incondicional em `_frases_do_canal`. A terceira asserção cai, e a interface
    passa a afirmar que está tudo automático numa máquina onde não está.
    """
    com_regra = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=True)
    dica = com_regra._speaker_box.get_tooltip_text()
    assert DICA_CANAL_ACORDADO in dica
    assert DICA_CANAL_E_PADRAO in dica
    assert "nada a ligar" in dica.lower(), (
        "a decisão dela é 'config default': a dica tem de dizer que não há "
        "interruptor a procurar"
    )

    sem_regra = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=False)
    dica_sem = sem_regra._speaker_box.get_tooltip_text()
    assert DICA_CANAL_SEM_A_REGRA in dica_sem
    assert DICA_CANAL_E_PADRAO not in dica_sem

    nao_perguntou = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=None)
    dica_nada = nao_perguntou._speaker_box.get_tooltip_text()
    assert DICA_CANAL_E_PADRAO not in dica_nada
    assert DICA_CANAL_SEM_A_REGRA not in dica_nada
    assert DICA_CANAL_ACORDADO in dica_nada, "o estado é lido; só o padrão não é"


def test_a_dica_para_de_dizer_que_o_volume_e_do_firmware_quando_e_nosso() -> None:
    """A frase antiga passaria a MENTIR justamente no estado que vira o normal.

    `DICA_BLOCO_SPEAKER` diz *"o volume é do firmware do controle e ele não o
    devolve; mover o controle deslizante passa a mandá-lo"*. Ela é verdade sem
    posse — e com o daemon pondo 100 % em todo controle, o estado sem posse
    deixa de ser o comum.

    Mordida: voltar a primeira linha da dica para `DICA_BLOCO_SPEAKER` fixo. A
    segunda asserção cai: a tela pede um gesto que já aconteceu.
    """
    com_posse = _card(speaker=POSSE_100, canal=CANAL_ACORDADO, regra=True)
    dica = com_posse._speaker_box.get_tooltip_text()

    assert DICA_SPEAKER_POSSE_NOSSA in dica
    assert "passa a mandá-lo" not in dica, (
        "com posse nossa, a dica não pode pedir o gesto que já foi dado"
    )
    assert "não devolve" in dica, (
        "o preço da camada 2 continua valendo: o número é o que mandamos"
    )

    sem_posse = _card(canal=CANAL_ACORDADO, regra=True)
    assert "passa a mandá-lo" in sem_posse._speaker_box.get_tooltip_text()


def test_os_dois_estados_custam_zero_altura_no_card() -> None:
    """O teste que ESCOLHEU o desenho, e o que impede o próximo de desfazê-lo.

    A coluna do som é a mais apertada do card, e o
    `test_status_som_02_controle_de_volume` cobra que ela não passe da maior
    coluna vizinha por mais de 12px. Um rótulo novo custa 19px (medido nesta
    bancada) e estoura isso; o rótulo da moldura custa ZERO.

    Mordida: pôr o estado do canal num `Gtk.Label` próprio, sempre visível, no
    miolo do bloco — que é o desenho "óbvio". A asserção de altura cai aqui e
    a folga de 12px cai lá.
    """
    for compact in (False, True):
        antes = _card(compact=compact, speaker=POSSE_100, canal="")
        depois = _card(
            compact=compact, speaker=POSSE_100, canal=CANAL_ACORDADO, regra=True
        )
        alt_antes = antes.get_preferred_height()[0]
        alt_depois = depois.get_preferred_height()[0]
        assert alt_depois == alt_antes, (
            f"o estado do canal custou altura no card "
            f"{'compacto' if compact else 'de um controle'}: "
            f"{alt_antes} -> {alt_depois}px"
        )
        larg_antes = antes.get_preferred_width()[0]
        larg_depois = depois.get_preferred_width()[0]
        assert larg_depois == larg_antes, (
            f"o estado do canal mexeu na largura mínima do card: "
            f"{larg_antes} -> {larg_depois}px, num teto de {LARGURA_DE_PROJETO}"
        )
        assert larg_depois <= LARGURA_DE_PROJETO


def test_o_selo_dormindo_cabe_no_teto_de_largura_do_selo() -> None:
    """O terceiro informante do selo não pode decidir a largura do bloco.

    O selo já tem teto (`_SELO_CHARS`) e o texto novo entra dentro dele — mas o
    teto é calculado a partir dos textos, então um texto longo amanhã o
    ALARGARIA em vez de ser cortado por ele. A asserção é sobre o efeito: o
    selo aceso não muda a largura mínima do card.

    Mordida: pôr a frase inteira do canal dormindo no selo em vez do rótulo
    curto. Foi o que a SOM-04 mediu com a frase do recado: o mínimo do card
    saltou de 1040 para 1223px, numa janela que abre com 1180.
    """
    for compact in (False, True):
        antes = _card(compact=compact, speaker=POSSE_100, canal=CANAL_ACORDADO)
        depois = _card(compact=compact, speaker=POSSE_100, canal=CANAL_DORMINDO)
        assert depois.get_preferred_width()[0] == antes.get_preferred_width()[0], (
            f"o selo do canal dormindo mexeu na largura mínima do card "
            f"{'compacto' if compact else 'de um controle'}"
        )
        assert depois.get_preferred_width()[0] <= LARGURA_DE_PROJETO


# ---------------------------------------------------------------------------
# Parte 4 — a FIAÇÃO: cada card recebe o canal DELE, e ninguém lê o PipeWire
#           na thread do GTK
# ---------------------------------------------------------------------------


class _CardEspiao:
    """Card de mentira que só anota o que a aba lhe entregou."""

    def __init__(self) -> None:
        self.canal: str | None = None
        self.regra: Any = "não perguntaram"
        self.sink = ""

    def update(self, *_a: Any, **_k: Any) -> None:
        pass

    def definir_sink_de_saida(self, sink: str) -> None:
        self.sink = sink

    def definir_estado_do_canal(
        self, estado: str, *, regra_instalada: bool | None = None
    ) -> None:
        self.canal = estado
        self.regra = regra_instalada


class _MonitorDeMentira:
    """Dublê do `MicMonitor` — só o que a aba pergunta a ele."""

    def __init__(self, sinks: dict[str, str]) -> None:
        self._sinks = sinks

    def set_controles(self, _uniqs: tuple[str, ...]) -> None:
        pass

    def sink_de(self, uniq: str) -> str:
        return self._sinks.get(uniq, "")

    def leitura(self, _uniq: str) -> Any:
        return None


class _SlotComAttach:
    def attach(self, *_a: Any, **_k: Any) -> None:  # pragma: no cover - inerte
        raise AssertionError("rebuild não devia acontecer com as chaves estáveis")


class _BuilderDaAba:
    def __init__(self, slot: Any) -> None:
        self._slot = slot

    def get_object(self, wid: str) -> Any:
        return self._slot if wid == "status_players_slot" else None


class _AbaStatus(StatusActionsMixin):
    """A janela do produto reduzida ao que este caminho toca (mixin REAL)."""

    def __init__(self, cards: dict[Any, Any], monitor: Any) -> None:
        self.builder = _BuilderDaAba(_SlotComAttach())
        self._mic_monitor = monitor
        self._status_cards = dict(cards)
        self._status_card_keys = list(cards)


#: Dois controles com endereços FORJADOS (faixa `aa:bb:cc`, que é a desta
#: suíte). Nada aqui depende de MAC: eles são só a chave que o `mic_monitor`
#: usa para dizer qual placa é de qual controle.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"


def _estado_com_dois_controles() -> dict[str, Any]:
    p1 = dict(_ENTRY, index=0, uniq=UNIQ_P1)
    p2 = dict(_ENTRY, index=1, uniq=UNIQ_P2, is_primary=False, player_slot=2)
    return {"controllers": [p1, p2]}


def test_cada_card_recebe_o_canal_do_proprio_controle() -> None:
    """Universal por construção: vale para 1, 2, 4 ou 7 controles.

    O estado vem de UMA leitura da lista de sinks, e cada card pega dela a
    linha do SEU sink. Um controle acordado e outro dormindo na mesma mesa é o
    caso que separa "a aba tem o dado" de "a aba entrega o dado certo".

    Mordida: entregar `self._canais_de_som` inteiro a todos os cards, ou usar o
    `_rota_sink` (que é o alvo GLOBAL do botão de rota, e fica "" assim que há
    dois sinks distintos). A segunda asserção cai — os dois cards passam a
    dizer a mesma coisa, ou a não dizer nada.
    """
    c1, c2 = _CardEspiao(), _CardEspiao()
    aba = _AbaStatus(
        {(0, UNIQ_P1): c1, (1, UNIQ_P2): c2},
        _MonitorDeMentira({UNIQ_P1: SINK_P1, UNIQ_P2: SINK_P2}),
    )
    aba._canais_de_som = {SINK_P1: CANAL_ACORDADO, SINK_P2: CANAL_DORMINDO}
    aba._regra_do_sono = True

    aba._sync_status_cards(_estado_com_dois_controles())

    assert (c1.sink, c2.sink) == (SINK_P1, SINK_P2)
    assert (c1.canal, c2.canal) == (CANAL_ACORDADO, CANAL_DORMINDO)
    assert (c1.regra, c2.regra) == (True, True)


def test_controle_sem_placa_de_som_recebe_nao_sei() -> None:
    """O caso do RÁDIO, e ele é a maioria da mesa dela.

    Sem sink não há canal a descrever, e o card tem de receber "" — não o
    estado de outro sink qualquer, e não `acordado` por omissão.

    Mordida: trocar o `if sink_do_card else ""` por um `.get(sink, CANAL_
    ACORDADO)`. A asserção cai, e o card de um controle no rádio passa a
    prometer que o som sai inteiro por um alto-falante que o sistema nem vê.
    """
    c1, c2 = _CardEspiao(), _CardEspiao()
    aba = _AbaStatus(
        {(0, UNIQ_P1): c1, (1, UNIQ_P2): c2},
        _MonitorDeMentira({UNIQ_P1: SINK_P1}),  # o P2 está no rádio
    )
    aba._canais_de_som = {SINK_P1: CANAL_ACORDADO}

    aba._sync_status_cards(_estado_com_dois_controles())

    assert c1.canal == CANAL_ACORDADO
    assert c2.canal == CANAL_SEM_LEITURA
    assert c2.sink == ""


def test_a_aba_nao_le_o_pipewire_na_thread_do_gtk() -> None:
    """A regra desta janela, e ela já congelou por chamada bloqueante num tique.

    O tique dos cards é de 10 Hz: um `pactl` ali seriam dez subprocessos por
    segundo por controle. A leitura mora na worker de 0,5 Hz da rota, e ao
    tique de 10 Hz só chega uma consulta a dicionário.

    Mordida: chamar `audio_saida.estado_do_canal(...)` (ou
    `regra_nunca_dorme_instalada()`) de dentro do `_sync_status_cards`. A
    asserção do fonte cai — e ela olha o FONTE de propósito, porque um dublê de
    `pactl` deixaria a versão lenta passar em silêncio.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(StatusActionsMixin._sync_status_cards))
    # A leitura é por AST e não por texto: comentários e docstrings deste
    # método falam de `pactl` e de `subprocess` justamente para explicar por que
    # eles NÃO estão aqui, e uma busca em texto cru reprovaria a explicação.
    nomes = {
        no.id if isinstance(no, ast.Name) else no.attr
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, (ast.Name, ast.Attribute))
    }

    # `audio_saida` cobre o módulo inteiro de uma vez — é ele que fala com o
    # `pactl` e com o disco. O nome do MÉTODO do card
    # (`definir_estado_do_canal`) não conta: ele é a entrega do dado já lido,
    # que é exatamente o que este tique pode fazer.
    for proibido in (
        "audio_saida",
        "rodar_leitura",
        "estado_do_canal",
        "estados_dos_sinks",
        "regra_nunca_dorme_instalada",
        "subprocess",
        "run",
    ):
        assert proibido not in nomes, (
            f"`{proibido}` no tique de 10 Hz dos cards: a leitura do PipeWire "
            "mora na worker de 0,5 Hz da rota, e aqui só chega o resultado"
        )
    assert "_canais_de_som" in nomes, "o tique consulta o dicionário já lido"
