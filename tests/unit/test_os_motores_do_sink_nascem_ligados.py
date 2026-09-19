"""Os canais traseiros do sink do DualSense são os MOTORES, e não nascem em zero.

HAPTICA-CABO-VOLUME-01 (Z2, prioridade zero) — 19/09/2026.

**MEDIDO NO APARELHO DELA, com o controle NO CABO**, tocando 150 Hz nos canais
3-4 do sink USB e lendo o acelerômetro do próprio controle:

    repouso             tremor =   20
    40% (como nasce)    tremor =   67
    100%                tremor = 1093     <- 16x mais forte

O WirePlumber dá 40% aos quatro canais de todo sink novo (menos 23,88 dB), e
**nenhuma linha do produto pedia outra coisa**. A vibração dos jogos da Sony
saía 16x mais fraca — em qualquer computador, porque o valor vem do servidor de
som e não do nosso código. A sprint estimava 9x; o aparelho disse 16x.

E o MESMO defeito, mais grave, no endpoint que o produto publica para o Wine:
ele nascia com os traseiros em **0%**, porque o `load-module` não dizia nada
sobre volume. É a classe que esta casa já pagou uma vez — *não escrever não é o
lado neutro*.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as bt
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

SINK = "alsa_output.usb-Sony_DualSense.HiFi__Speaker__sink"


def _pactl(volume_linha: str) -> tuple:
    """Um `pactl` de mentira que responde o `list sinks` e anota o que escrevem."""
    escritas: list[list[str]] = []

    def correr(cmd: list[str]) -> str | None:
        if cmd[:3] == ["pactl", "list", "sinks"]:
            return f"Sink #9\n\tName: {SINK}\n\t{volume_linha}\n"
        escritas.append(cmd)
        return ""

    return correr, escritas


QUARENTA = ("Volume: front-left: 26214 /  40% / -23.88 dB,   "
            "front-right: 26214 /  40% / -23.88 dB,   "
            "rear-left: 26214 /  40% / -23.88 dB,   rear-right: 26214 /  40% / -23.88 dB")
CEM = ("Volume: front-left: 65536 / 100% / 0.00 dB,   front-right: 65536 / 100% / 0.00 dB,   "
       "rear-left: 65536 / 100% / 0.00 dB,   rear-right: 65536 / 100% / 0.00 dB")
ZERO_ATRAS = ("Volume: front-left: 65536 / 100% / 0.00 dB,   "
              "front-right: 65536 / 100% / 0.00 dB,   "
              "rear-left: 0 /   0% / -inf dB,   rear-right: 0 /   0% / -inf dB")


def test_os_quarenta_por_cento_sao_levantados() -> None:
    """O caso medido no cabo dela: 40% nos quatro."""
    correr, escritas = _pactl(QUARENTA)
    assert bt.garantir_motores_audiveis(SINK, correr) is True
    assert len(escritas) == 1
    assert escritas[0][:3] == ["pactl", "set-sink-volume", SINK]
    assert escritas[0][3:] == ["40%", "40%", "100%", "100%"], (
        "os da FRENTE têm de voltar como estavam — são o alto-falante, e "
        "aquele volume é escolha dela"
    )


def test_o_zero_do_endpoint_tambem() -> None:
    """O caso do endpoint que o produto publica: traseiros em 0%."""
    correr, escritas = _pactl(ZERO_ATRAS)
    assert bt.garantir_motores_audiveis(SINK, correr) is True
    assert escritas[0][3:] == ["100%", "100%", "100%", "100%"]


def test_quem_ja_esta_no_piso_nao_e_reescrito() -> None:
    """Sem esta guarda, uma volta a cada 5 s vira uma escrita a cada 5 s."""
    correr, escritas = _pactl(CEM)
    assert bt.garantir_motores_audiveis(SINK, correr) is False
    assert escritas == []


def test_sink_estereo_nao_e_caso_deste_piso() -> None:
    """Dois canais não têm motor: o endpoint de som por rádio é `s16le 2ch`."""
    correr, escritas = _pactl("Volume: front-left: 65536 / 100% / 0.00 dB,   "
                              "front-right: 65536 / 100% / 0.00 dB")
    assert bt.garantir_motores_audiveis(SINK, correr) is False
    assert escritas == []


def test_servidor_mudo_nao_escreve() -> None:
    """`None` do runner é dúvida, e na dúvida não se mexe no som dela."""
    escritas: list[list[str]] = []

    def correr(cmd: list[str]) -> str | None:
        if cmd[:3] == ["pactl", "list", "sinks"]:
            return None
        escritas.append(cmd)
        return ""

    assert bt.garantir_motores_audiveis(SINK, correr) is False
    assert escritas == []


@pytest.mark.parametrize("linha,esperado", [
    (QUARENTA, [40, 40, 40, 40]),
    (CEM, [100, 100, 100, 100]),
    (ZERO_ATRAS, [100, 100, 0, 0]),
])
def test_o_leitor_de_volume_le_os_quatro(linha: str, esperado: list[int]) -> None:
    correr, _ = _pactl(linha)
    assert bt.volumes_do_sink(SINK, correr) == esperado


def test_o_piso_e_cem_e_esta_declarado() -> None:
    """O número é o que a medição sustenta, e mora num lugar só."""
    assert bt.PISO_DOS_MOTORES == 100
    assert eh.VOLUME_DOS_MOTORES == "100%"


def test_o_endpoint_le_a_frente_antes_de_escrever() -> None:
    """`set-sink-volume` com quatro valores define os QUATRO — a frente é dela."""
    saida = f"Sink #9\n\tName: {SINK}\n\t{QUARENTA}\n"
    assert eh._volume_da_frente(saida, SINK) == ("40%", "40%")
    assert eh._volume_da_frente(saida, "outro_sink") == ("100%", "100%")
    assert eh._volume_da_frente("", SINK) == ("100%", "100%")


def test_o_endpoint_liga_os_motores_ao_publicar() -> None:
    """Publicar o nó e não dizer o volume é o defeito — a chamada tem de estar lá.

    ESTA RÉGUA NASCEU DE UMA MORDIDA QUE NÃO PEGOU: arrancar
    `self._ligar_os_motores()` do `iniciar()` deixava as outras dez verdes. A
    função existia, era testada isoladamente, e ninguém provava que ela é
    CHAMADA — que é a única coisa que importa para o controle vibrar.
    """
    chamadas: list[list[str]] = []

    def correr(cmd: list[str]) -> str | None:
        chamadas.append(cmd)
        if cmd[:3] == ["pactl", "list", "sinks"]:
            return f"Sink #9\n\tName: hefesto_haptica_x\n\t{ZERO_ATRAS}\n"
        if cmd[:2] == ["pactl", "load-module"]:
            return "536870916"
        return ""

    quem = object.__new__(eh.EndpointDeHaptica)
    quem.uniq = "aabbcc000001"
    quem.nome = "hefesto_haptica_x"
    quem.canais = 4
    quem.taxa_hz = 48000
    quem.runner = correr
    quem._module_id = None
    quem.ancora = eh.Ancora(syspath="/sys/devices/x", declarado="/sys/devices/x/1-1:1.0")

    assert quem.iniciar() is True
    escritas = [c for c in chamadas if c[:2] == ["pactl", "set-sink-volume"]]
    assert escritas, (
        "o endpoint subiu sem dizer o volume dos motores — é o defeito de 19/09, "
        "em que os canais 3-4 nasciam em 0% e o jogo escrevia no nada"
    )
    assert escritas[0][-2:] == [eh.VOLUME_DOS_MOTORES, eh.VOLUME_DOS_MOTORES]
