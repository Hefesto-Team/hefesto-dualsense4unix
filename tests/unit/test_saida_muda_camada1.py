"""SENSOR-VIVO-01/E5 e SOM-02/E5 item 4 — quem PUBLICA o "saída muda".

O alto-falante do controle tem três camadas de volume. A camada 2 (o
registrador HID) ganhou controle deslizante na SOM-02; a camada 1 — o sink do
PipeWire — é quem decide se **sai som**. Com ela muda, ela move o controle, a
barra acompanha, o rótulo vira porcentagem e nada toca: a definição de
interface mentirosa.

A fiação do consumidor já existia e já era testada
(`controller_card.saida_muda_do_entry`, e o selo em
`test_status_som_02_controle_de_volume.py`). O que faltava — e é o que este
arquivo trava — é o LADO QUE PUBLICA: o `app/mic_monitor.py`, que já era o
leitor de PipeWire da janela, passou a ler também o mudo do **sink** do
controle, e não só as sources de captura.

Três regras, e cada teste diz qual arranca para ver vermelho:

* **Nada quando não houver como saber.** Sem `pactl`, com resposta traduzida
  ou com sink que não dá para casar, a resposta é ``None`` — e ``None`` não
  acende selo nenhum. "Não sei" nunca pode virar "está mudo".
* **É o sink DO CONTROLE.** Dois DualSense no cabo publicam sinks cujos nomes
  não os distinguem (medido: o desempate é um ``-00`` posicional do PipeWire,
  não a identidade). Acender no card errado é pior que não acender.
* **Informa, nunca conserta.** Mesma disciplina do `scripts/doctor.sh`: o mudo
  é escolha legítima da usuária e mora no estado do WirePlumber. Nada aqui
  escreve no PipeWire.

Os textos de `pactl` usados como base foram MEDIDOS nesta máquina em
01/08/2026, com um DualSense no cabo: o sink do controle estava
``Mute: no`` a 40 %.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.mic_monitor import (
    LeituraMic,
    MicMonitor,
    escolher_sink,
    sinks_dualsense,
)
from hefesto_dualsense4unix.app.widgets.controller_card import saida_muda_do_entry

#: `pactl list sinks short` desta máquina em 01/08/2026 (LC_ALL=C). O DualSense
#: no meio de uma saída S/PDIF e de uma HDMI que estava TOCANDO.
_SINKS = (
    "59\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    "61\talsa_output.pci-0000_0c_00.4.iec958-stereo\tPipeWire"
    "\ts32le 2ch 48000Hz\tSUSPENDED\n"
    "2915\talsa_output.pci-0000_0a_00.1.hdmi-stereo\tPipeWire"
    "\ts16le 2ch 48000Hz\tRUNNING\n"
)

#: O sink do controle, por extenso — é o que a atribuição tem que devolver.
_SINK_DO_CONTROLE = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)

#: `pactl list sources short` com a CAPTURA do controle. Entra aqui de
#: propósito: é a lista errada, e a mordida do teste que a usa é justamente
#: alguém passá-la para o lado da saída.
_SOURCES = (
    "645\talsa_output.pci-0000_0c_00.4.iec958-stereo.monitor\tPipeWire"
    "\ts32le 2ch\tIDLE\n"
    "651\talsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00."
    "mono-fallback\tPipeWire\ts16le 1ch\tSUSPENDED\n"
)

_UNIQ = "aabbcc010203"
_OUTRO_UNIQ = "aabbcc010204"

#: Uma entrada de ``state_full.controllers`` SEM a chave `speaker` — o estado
#: normal de qualquer sessão em que ninguém tomou posse do registrador HID.
#: É nele que o selo tem que aparecer mesmo assim: são duas verdades
#: diferentes, e a camada 1 não depende da camada 2.
_ENTRY_SEM_POSSE: dict[str, Any] = {"index": 0, "uniq": _UNIQ, "inputs": {}}


def _runner_de(
    *,
    sinks: str = _SINKS,
    sources: str = "",
    sink_mute: str = "Mute: no",
    registro: list[list[str]] | None = None,
) -> Any:
    """Dublê do `pactl`: um texto por pergunta, e nenhum áudio real envolvido."""

    def runner(argv: list[str]) -> str:
        if registro is not None:
            registro.append(list(argv))
        if argv[:2] == ["pactl", "list"]:
            return sinks if "sinks" in argv else sources
        if argv[:2] == ["pactl", "get-sink-mute"]:
            return sink_mute
        if argv[:2] == ["pactl", "get-source-mute"]:
            return "Mute: no"
        return ""

    return runner


def _monitor(
    controles: tuple[str, ...] = (_UNIQ,),
    *,
    ativo: bool = True,
    **kwargs: Any,
) -> MicMonitor:
    """Monitor com supervisora manual, já reconciliado uma vez."""
    monitor = MicMonitor(
        runner=_runner_de(**kwargs),
        capturador=lambda _f: None,
        auto_supervisao=False,
    )
    monitor.set_ativo(ativo)
    monitor.set_controles(controles)
    monitor.reconciliar()
    return monitor


# ---------------------------------------------------------------------------
# Descoberta do sink (função pura, sobre o texto medido)
# ---------------------------------------------------------------------------


def test_o_sink_do_controle_sai_da_lista_real_e_as_outras_saidas_nao() -> None:
    """Só o DualSense. A HDMI estava TOCANDO na hora da medição.

    Mordida: afrouxar o filtro de marcadores faz a lista trazer a HDMI, e o
    selo passaria a falar do mudo da placa de vídeo dentro do card do
    controle.
    """
    assert sinks_dualsense(_SINKS) == [_SINK_DO_CONTROLE]


def test_a_lista_de_captura_nunca_vira_sink_de_saida() -> None:
    """Um nó `alsa_input.` não é por onde sai som — nem por engano.

    Mordida: arrancar o descarte de ``alsa_input.`` (e o de ``.monitor``) faz
    a lista de SOURCES virar uma lista de sinks, e o selo da saída passaria a
    reportar o mudo do MICROFONE.
    """
    assert sinks_dualsense(_SOURCES) == []


def test_linha_malformada_nao_derruba_a_descoberta() -> None:
    assert sinks_dualsense("lixo sem tab\n\n") == []


# ---------------------------------------------------------------------------
# Casamento sink -> controle
# ---------------------------------------------------------------------------


def test_um_controle_um_sink_casa() -> None:
    assert escolher_sink([_SINK_DO_CONTROLE], _UNIQ, [_UNIQ]) == _SINK_DO_CONTROLE


def test_dois_controles_no_cabo_nao_chutam_o_sink() -> None:
    """O ``-00`` do nome é desempate posicional do PipeWire, não identidade.

    A string USB de serial do DualSense é a mesma em todos os controles, então
    com dois no cabo não há como saber de quem é o sink.
    """
    assert escolher_sink([_SINK_DO_CONTROLE], _UNIQ, [_UNIQ, _OUTRO_UNIQ]) is None


def test_um_nome_que_carrega_o_mac_casa_mesmo_com_varios_controles() -> None:
    """A conservadoria não é cega: identidade NO NOME casa com certeza.

    É a mesma regra 1 do `escolher_fonte`, e é o que faz o "não acendo com
    dois controles" ser uma consequência do nome ambíguo, e não uma desistência
    permanente.
    """
    sinks = ["bluez_output.AA_BB_CC_01_02_03", "bluez_output.AA_BB_CC_01_02_04"]

    escolhido = escolher_sink(sinks, _OUTRO_UNIQ, [_UNIQ, _OUTRO_UNIQ])

    assert escolhido == "bluez_output.AA_BB_CC_01_02_04"


def test_com_dois_controles_o_selo_nao_acende_em_ninguem() -> None:
    """Ponta a ponta: sink MUDO, dois controles, e nenhum card acende.

    Mordida: trocar a atribuição por "pega o primeiro sink da lista" acende o
    selo nos DOIS cards — inclusive no do controle que está tocando som.
    """
    monitor = _monitor((_UNIQ, _OUTRO_UNIQ), sink_mute="Mute: yes")

    for uniq in (_UNIQ, _OUTRO_UNIQ):
        assert monitor.leitura(uniq) is None
        entrada = dict(_ENTRY_SEM_POSSE, uniq=uniq)
        assert saida_muda_do_entry(entrada, monitor.leitura(uniq)) is None


# ---------------------------------------------------------------------------
# Publicação: o selo acende (e o resto do tempo fica apagado)
# ---------------------------------------------------------------------------


def test_sink_mudo_acende_o_selo_pela_fiacao_que_ja_existia() -> None:
    """A entrega: o sink do controle mudo chega ao card, sem posse do HID.

    Mordida: arrancar a publicação (`_descobrir_saidas_mudas` devolvendo `{}`,
    ou o `leitura()` deixando de casar as duas fontes) deixa o selo apagado com
    o sink mudo — que é exatamente o estado de antes desta leva.
    """
    monitor = _monitor(sink_mute="Mute: yes")

    leitura = monitor.leitura(_UNIQ)

    assert leitura is not None
    assert leitura.saida_muda is True
    assert saida_muda_do_entry(_ENTRY_SEM_POSSE, leitura) is True


def test_sink_aberto_nao_acende_e_nao_materializa_leitura() -> None:
    """`Mute: no` é o valor MEDIDO nesta máquina hoje — e não acende nada.

    A leitura nem chega a existir: criar um objeto só para dizer "a saída não
    está muda" inventaria presença de sensor para não dizer nada.
    """
    monitor = _monitor(sink_mute="Mute: no")

    assert monitor.leitura(_UNIQ) is None
    assert saida_muda_do_entry(_ENTRY_SEM_POSSE, monitor.leitura(_UNIQ)) is None


@pytest.mark.parametrize(
    ("resposta", "motivo"),
    [
        ("", "pactl ausente ou PipeWire parado"),
        ("Mudo: sim", "saída TRADUZIDA — o LC_ALL=C não pegou"),
        ("qualquer outra coisa", "formato inesperado"),
    ],
)
def test_sem_leitura_o_selo_fica_apagado(resposta: str, motivo: str) -> None:
    """"Não sei" nunca vira "está mudo". Este é o teste da regra 2.

    Mordida: tratar a ausência como mudo (por exemplo materializar a leitura
    quando `saida_muda is not False`) acende o selo nos TRÊS casos — e a tela
    passaria a culpar o PipeWire por um silêncio que ninguém mediu.
    """
    monitor = _monitor(sink_mute=resposta)

    assert monitor.leitura(_UNIQ) is None, motivo
    assert saida_muda_do_entry(_ENTRY_SEM_POSSE, monitor.leitura(_UNIQ)) is None


def test_mudo_ilegivel_nao_vira_saida_aberta() -> None:
    """Resposta ilegível é ``None``, e ``None`` não é "a saída está aberta".

    Os dois deixam o selo apagado, então a diferença não aparece no desenho de
    hoje — mas aparece no VALOR, e é ele que `saida_muda_do_entry` devolve tal
    e qual. Gravar ``False`` diria a quem for ler depois que a camada 1 foi
    medida e estava aberta; a verdade é que ela não foi medida.

    Com a captura viva o objeto existe de qualquer jeito, e é ali que dá para
    olhar o campo sem ele estar escondido atrás do `None` da leitura inteira.

    Mordida: trocar o ``if muda is not None`` por ``fora[uniq] = bool(muda)``.
    """
    monitor = _monitor(sources=_SOURCES, sink_mute="Mudo: não")
    monitor._publicar(_UNIQ, LeituraMic(nivel=0.62, muted=False, fonte="fonte-x"))

    leitura = monitor.leitura(_UNIQ)

    assert leitura is not None
    assert leitura.saida_muda is None
    assert saida_muda_do_entry(_ENTRY_SEM_POSSE, leitura) is None


def test_sem_sink_do_controle_o_selo_fica_apagado() -> None:
    """Controle por Bluetooth não publica sink nenhum (não fala A2DP)."""
    monitor = _monitor(sinks="", sink_mute="Mute: yes")

    assert monitor.leitura(_UNIQ) is None


# ---------------------------------------------------------------------------
# A carona não pode fingir microfone
# ---------------------------------------------------------------------------


def test_a_saida_muda_sem_captura_nao_finge_microfone() -> None:
    """Sem `parec` (ou sem source atribuível) o medidor tem que SUMIR.

    O card decide a presença do microfone por ``nivel is None``. Se a leitura
    que carrega o "saída muda" nascesse com ``nivel=0.0``, o card desenharia
    uma barra parada no zero fingindo silêncio — o defeito que o cabeçalho do
    `mic_monitor.py` proíbe desde que existe.

    Mordida: trocar o ``nivel=None`` desta leitura por ``0.0``.
    """
    monitor = _monitor(sink_mute="Mute: yes")

    leitura = monitor.leitura(_UNIQ)

    assert leitura is not None
    assert leitura.nivel is None
    assert leitura.muted is None
    assert leitura.fonte == ""


def test_a_saida_muda_anda_junto_com_a_captura_viva() -> None:
    """Com o microfone captando, o selo entra SEM apagar nível e mute.

    São duas fontes independentes (a thread do `parec` e a supervisora) que se
    encontram no `leitura()`; uma não pode sobrescrever a outra.

    Mordida: publicar a saída muda por cima da leitura da captura (em vez de
    casar as duas) zera o medidor toda vez que o sink for lido.
    """
    monitor = _monitor(sources=_SOURCES, sink_mute="Mute: yes")
    monitor._publicar(_UNIQ, LeituraMic(nivel=0.62, muted=False, fonte="fonte-x"))

    leitura = monitor.leitura(_UNIQ)

    assert leitura is not None
    assert leitura.nivel == pytest.approx(0.62)
    assert leitura.muted is False
    assert leitura.fonte == "fonte-x"
    assert leitura.saida_muda is True


# ---------------------------------------------------------------------------
# Ciclo de vida e a regra do "informa, nunca conserta"
# ---------------------------------------------------------------------------


def test_aba_escondida_nao_pergunta_nada_ao_pipewire() -> None:
    """Fora da aba Status nada é lido — nem sink, nem source."""
    registro: list[list[str]] = []
    monitor = _monitor(ativo=False, sink_mute="Mute: yes", registro=registro)

    assert registro == []
    assert monitor.leitura(_UNIQ) is None


def test_sair_da_aba_apaga_o_selo() -> None:
    """A leitura da camada 1 não sobrevive à saída da aba: ela é de agora."""
    monitor = _monitor(sink_mute="Mute: yes")
    assert monitor.leitura(_UNIQ) is not None

    monitor.set_ativo(False)
    monitor.reconciliar()

    assert monitor.leitura(_UNIQ) is None


def test_nada_e_escrito_no_pipewire() -> None:
    """O selo INFORMA. O mudo persistido é dela, e o `doctor` o respeita.

    Mordida: qualquer `pactl set-sink-mute` ou `wpctl set-mute` que alguém
    acrescente "para consertar sozinho" reprova aqui.
    """
    registro: list[list[str]] = []
    _monitor(sources=_SOURCES, sink_mute="Mute: yes", registro=registro)

    assert registro != []
    for argv in registro:
        assert argv[1] in {"list", "get-sink-mute", "get-source-mute"}, argv
        assert not any("set" in parte for parte in argv), argv
