"""SOM-RADIO-PLACA-01 — o nó que esta casa publica CONTA como placa de som.

**A queixa dela, 10/09/2026, com o controle no rádio tocando o som do PC:**
*"ele tá metendo essa frase quando tá nesse exato segundo reproduzindo todo o
som do meu pc via bt"*.  <!-- noqa-acento: citação literal dela -->

A frase era «este controle não publica placa de som para o sistema», e ela
tinha sido verdade até a manhã do mesmo dia. Depois de `SOM-FIADO-01` o
`AltoFalanteSubsystem` cria um `hefesto_som_<hex6>` por controle e a ponte 0x35
carrega o monitor dele para o aparelho — mas os três lugares que perguntam
*"qual é o sink deste controle?"* seguiam olhando só para os `alsa_output` da
Sony. Uma pergunta mal respondida, três sintomas: a frase, o botão «Todo o som
do PC» recusando e a onda do alto-falante sem leitura.

**A MORDIDA de cada teste está na sua docstring.**

Nenhum aparelho aqui: o `pactl` é um dublê, e os endereços são sintéticos.
"""

from __future__ import annotations

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

#: Um controle no rádio: nenhuma placa da Sony na lista, só o nó desta casa.
UNIQ_RADIO = "a0fa9c02fe00"
#: Um controle no cabo, com a placa de verdade e o nó desta casa ao lado.
UNIQ_CABO = "d42f4baabbcc"

_PLACA_SONY = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)


def _pactl(sinks_curtos: str, longa: str = "") -> object:
    """Um `pactl` de mentira que só sabe responder as duas leituras usadas."""

    def rodar(argv: list[str]) -> str:
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return sinks_curtos
        if argv[:3] == ["pactl", "list", "sinks"]:
            return longa
        return ""

    return rodar


def _linha(indice: int, nome: str) -> str:
    return f"{indice}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tIDLE"


def test_o_no_desta_casa_e_o_sink_do_controle_no_radio() -> None:
    """MORDIDA: devolva `""` quando `sinks_dualsense` vier vazio, como antes.

    O nó existe, está na lista viva e é DESTE controle — responder "não sei" é
    o que punha a frase de recusa na tela com a música tocando.
    """
    no = nome_do_sink(UNIQ_RADIO)
    curtos = "\n".join([_linha(61, "alsa_output.pci-0000_0a_00.1.hdmi-stereo"),
                        _linha(97, no)])
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == no


def test_no_cabo_quem_manda_continua_sendo_a_placa_de_verdade() -> None:
    """MORDIDA: prefira o nó desta casa antes de `escolher_sink`.

    No cabo o `hefesto_som_<hex6>` é só a boca de um `module-loopback` que
    termina naquela mesma placa. Preferi-lo aqui trocaria, sem ganho, o destino
    que a casa mede desde agosto — e o recuo deixaria de ser recuo.
    """
    no = nome_do_sink(UNIQ_CABO)
    curtos = "\n".join([_linha(107, _PLACA_SONY), _linha(131, no)])
    assert audio_saida.sink_do_controle(
        UNIQ_CABO, (UNIQ_CABO,), runner=_pactl(curtos)) == _PLACA_SONY


def test_sem_no_e_sem_placa_a_resposta_continua_sendo_nao_sei() -> None:
    """MORDIDA: devolva o nome do nó sem conferir se ele está na lista.

    Um nome montado por aritmética de string é uma afirmação sobre o servidor
    que ninguém conferiu: `set-default-sink` num sink que não existe é aceito
    e o som fica onde estava.
    """
    curtos = _linha(61, "alsa_output.pci-0000_0a_00.1.hdmi-stereo")
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == ""


def test_o_monitor_na_lista_nao_e_confundido_com_o_no() -> None:
    """MORDIDA: troque a conferência por campo por um `in` na saída inteira.

    `hefesto_som_<hex6>` é prefixo de `hefesto_som_<hex6>.monitor`. Casar por
    substring devolveria o monitor de uma lista de sources — e mandar o som do
    PC para um monitor é mandá-lo para lugar nenhum.
    """
    no = nome_do_sink(UNIQ_RADIO)
    curtos = _linha(98, f"{no}.monitor")
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == ""


def test_o_botao_todo_o_som_do_pc_deixa_de_recusar_no_radio() -> None:
    """A queixa inteira, do clique ao desfecho.

    MORDIDA: faça `sink_do_controle` devolver `""` no rádio — o desfecho volta
    a ser `MOTIVO_ROTA_SEM_SINK`, que é a frase que ela fotografou.
    """
    no = nome_do_sink(UNIQ_RADIO)
    curtos = _linha(97, no)
    pedidos: list[list[str]] = []

    def rodar(argv: list[str]) -> str:
        pedidos.append(argv)
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return curtos
        if argv[:2] == ["pactl", "get-default-sink"]:
            return no if any(a[:2] == ["pactl", "set-default-sink"]
                             for a in pedidos) else "alsa_output.hdmi"
        return ""

    desfecho = audio_saida.mandar_o_som_do_pc(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=rodar)
    assert desfecho.ok, desfecho.motivo
    assert desfecho.sink == no
    assert ["pactl", "set-default-sink", no] in pedidos
