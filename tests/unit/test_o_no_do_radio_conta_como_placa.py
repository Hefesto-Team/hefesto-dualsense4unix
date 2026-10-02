"""SOM-RADIO-PLACA-01 — o nó que esta casa publica CONTA como placa de som."""

from __future__ import annotations

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

UNIQ_RADIO = "02fe00d4c311"
UNIQ_CABO = "aabbcc0000d8"

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
    """MORDIDA: devolva `""` quando `sinks_dualsense` vier vazio, como antes."""
    no = nome_do_sink(UNIQ_RADIO)
    curtos = "\n".join([_linha(61, "alsa_output.pci-0000_0a_00.1.hdmi-stereo"),
                        _linha(97, no)])
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == no


def test_no_cabo_quem_manda_continua_sendo_a_placa_de_verdade() -> None:
    """MORDIDA: prefira o nó desta casa antes de `escolher_sink`."""
    no = nome_do_sink(UNIQ_CABO)
    curtos = "\n".join([_linha(107, _PLACA_SONY), _linha(131, no)])
    assert audio_saida.sink_do_controle(
        UNIQ_CABO, (UNIQ_CABO,), runner=_pactl(curtos)) == _PLACA_SONY


def test_sem_no_e_sem_placa_a_resposta_continua_sendo_nao_sei() -> None:
    """MORDIDA: devolva o nome do nó sem conferir se ele está na lista."""
    curtos = _linha(61, "alsa_output.pci-0000_0a_00.1.hdmi-stereo")
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == ""


def test_o_monitor_na_lista_nao_e_confundido_com_o_no() -> None:
    """MORDIDA: troque a conferência por campo por um `in` na saída inteira."""
    no = nome_do_sink(UNIQ_RADIO)
    curtos = _linha(98, f"{no}.monitor")
    assert audio_saida.sink_do_controle(
        UNIQ_RADIO, (UNIQ_RADIO,), runner=_pactl(curtos)) == ""


def test_o_botao_todo_o_som_do_pc_deixa_de_recusar_no_radio() -> None:
    """A queixa inteira, do clique ao desfecho."""
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
