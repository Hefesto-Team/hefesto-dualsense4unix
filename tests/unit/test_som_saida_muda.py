"""SOM-SAIDA-MUDA-01: pedir som no controle tem de deixar a saída audível.

MEDIDO com ela em 04/08/2026. Ela clicou nos dois estados do seletor de canal
("Sons do jogo" e "Todo o som do PC"), o daemon escreveu o byte de rota, o
`pactl` trocou o sink padrão — e **não saiu som nenhum**.

O sink do DualSense estava `MUTED` no PipeWire:

    *   45. DualSense wireless controller (PS5) Surround analógico 4.0
            [vol: 1.00 MUTED]

Estado que o WirePlumber PERSISTE por rota (``default-routes``) e restaura a
cada conexão sem escrever nada em log nenhum. A casa já conhecia o mecanismo
pelo lado da CAPTURA — é a "camada 1" do microfone mudo, que o `doctor.sh`
confere e cura — e já tinha a doutrina escrita no próprio card:

    *"A camada 1 vence a camada 2: volume e rota perfeitos num sink mudo é
    trabalho invisível."*

O que faltava era alguém AGIR. O `tocar_confirmacao` recusa com recado quando
o mute foi LIDO (``MOTIVO_SAIDA_MUDA``), mas o mapa de mudos só guarda o que
casou com certeza: ausência é "não sei" — e "não sei" seguia para o tocador,
que gastava um processo para produzir silêncio e devolvia sucesso.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.audio_saida import (
    RotaDeSaida,
    garantir_saida_audivel,
)

SINK = "alsa_output.usb-Sony_DualSense-00.analog-surround-40"
OUTRO = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


class _Pactl:
    """Um `pactl` de mentira que LEMBRA o mute e a saída padrão."""

    def __init__(self, *, mudo: bool | None = True, padrao: str = OUTRO) -> None:
        self.mudo = mudo
        self.padrao = padrao
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "get-sink-mute"]:
            if self.mudo is None:
                return "resposta que o parser não entende"
            return f"Mute: {'yes' if self.mudo else 'no'}"
        if argv[:2] == ["pactl", "set-sink-mute"]:
            self.mudo = argv[3] != "0"
            return ""
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.padrao = argv[2]
            return ""
        if argv[:3] == ["pactl", "list", "sinks"]:
            # formato de `pactl list sinks short`: índice TAB nome TAB ...
            return f"45\t{SINK}\tmodule\n74\t{OUTRO}\tmodule\n"
        return ""


class TestGarantirSaidaAudivel:
    def test_o_sink_mudo_fica_audivel(self) -> None:
        """Mordida: sem a chamada de `set-sink-mute`, este teste reprova."""
        pactl = _Pactl(mudo=True)
        assert garantir_saida_audivel(SINK, runner=pactl) is True
        assert pactl.mudo is False

    def test_diz_a_verdade_sobre_o_que_encontrou(self) -> None:
        """Devolver True sem ter havido mute faria a tela contar história.

        O retorno existe para quem quiser dizer "estava mudo, e eu resolvi" —
        não para confirmar que a chamada aconteceu.
        """
        pactl = _Pactl(mudo=False)
        assert garantir_saida_audivel(SINK, runner=pactl) is False
        assert pactl.mudo is False

    def test_mute_ilegivel_desmuta_do_mesmo_jeito_e_nao_afirma_nada(self) -> None:
        """"Não sei" é o caso que produziu o defeito — e ele TEM de desmutar.

        Era exatamente aqui que o produto vazava: o mapa de mudos do
        `mic_monitor` guarda só o que casou com certeza, a ausência virava
        "não está mudo" no consumidor, e o tocador ia tocar no silêncio. O
        pedido dela não muda de natureza por o mute estar ilegível.
        """
        pactl = _Pactl(mudo=None)
        assert garantir_saida_audivel(SINK, runner=pactl) is False
        assert ["pactl", "set-sink-mute", SINK, "0"] in pactl.chamadas

    def test_sem_sink_nao_toca_no_sistema(self) -> None:
        """Sink vazio é o "não sei quem é" do `escolher_sink` com 2 controles.

        Um `pactl set-sink-mute "" 0` cairia no sink PADRÃO — desmutaria a
        televisão dela para confirmar um pedido feito ao controle.
        """
        pactl = _Pactl(mudo=True)
        assert garantir_saida_audivel("", runner=pactl) is False
        assert pactl.chamadas == []


class _Memoria:
    """A lembrança de "de onde o som veio" — injetável, fora do disco dela."""

    def __init__(self) -> None:
        self.valor = ""

    def ler(self) -> str:
        return self.valor

    def gravar(self, valor: str) -> None:
        self.valor = valor


def _rota(pactl: _Pactl) -> tuple[RotaDeSaida, _Memoria]:
    mem = _Memoria()
    return (
        RotaDeSaida(runner=pactl, ler_memoria=mem.ler, gravar_memoria=mem.gravar),
        mem,
    )


class TestMandarParaOControle:
    def test_mandar_o_som_ao_controle_desmuta_o_destino(self) -> None:
        """Mordida: mover o sink padrão para um destino mudo é o defeito dela.

        A troca "funcionava" — `get-default-sink` confirmava o controle — e o
        silêncio era lido por ela como alto-falante quebrado.
        """
        pactl = _Pactl(mudo=True, padrao=OUTRO)
        rota, _mem = _rota(pactl)
        assert rota.mandar_para_o_controle(SINK) is True
        assert pactl.padrao == SINK
        assert pactl.mudo is False

    def test_a_ordem_e_desmutar_antes_de_trocar(self) -> None:
        """Trocar primeiro deixa uma janela audível-em-lugar-nenhum.

        Entre o `set-default-sink` e o `set-sink-mute` o som do sistema já
        estaria indo para um destino mudo — curto, mas é a janela em que um
        som de sistema se perde sem deixar rastro.
        """
        pactl = _Pactl(mudo=True, padrao=OUTRO)
        _rota(pactl)[0].mandar_para_o_controle(SINK)
        nomes = [c[1] for c in pactl.chamadas if len(c) > 1]
        assert nomes.index("set-sink-mute") < nomes.index("set-default-sink")

    def test_a_memoria_do_caminho_de_volta_continua_correta(self) -> None:
        """A cura não pode custar o desfazer honesto (o `voltar_ao_anterior`).

        Guardar de onde veio ANTES de trocar é decisão antiga e medida; o
        desmute entrou no meio e não pode ter mudado a ordem.
        """
        pactl = _Pactl(mudo=True, padrao=OUTRO)
        rota, _mem = _rota(pactl)
        rota.mandar_para_o_controle(SINK)
        assert rota.voltar_ao_anterior() is True
        assert pactl.padrao == OUTRO

    @pytest.mark.parametrize("sink", ["", "alsa_output.que-nao-existe"])
    def test_sink_invalido_continua_recusado_sem_mexer_em_nada(self, sink: str) -> None:
        """A guarda antiga vence a cura nova: nada de desmutar às cegas."""
        pactl = _Pactl(mudo=True, padrao=OUTRO)
        assert _rota(pactl)[0].mandar_para_o_controle(sink) is False
        assert pactl.padrao == OUTRO
        assert pactl.mudo is True
