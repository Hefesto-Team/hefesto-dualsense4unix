"""SOM-ECO-01 — escrever ZERO num bit de firmware também não é neutro.

A REGRESSÃO FOI NOSSA, e do mesmo dia: a `SOM-ROTA-02` passou a escrever o
`common[7]` na adoção para que o alto-falante nascesse roteado — e a base do
byte era `0x01`, só `FORCE_INTERNAL_MIC`, com um comentário afirmando que os
demais bits *"ficam em zero, que é o neutro deles"*.

**O bit2 é `ECHO_CANCEL`, e zero o DESLIGA**
(`docs/protocol/dualsense-referencia-canonica.md`, tabela do `audio_control`).
Enquanto ninguém escrevia o byte, o firmware ficava no default DELE, com o
cancelamento ligado, e não havia eco. A cura do alto-falante ligou o eco.

O QUE ELA MEDIU, e foi ela quem achou a pista::

    rádio, jogo FECHADO ... a voz dela saía pelo alto-falante do controle,
                            com atraso audível
    cabo, MESMO controle .. sem eco

*"tá errado no original via cabo com o mesmo controle ele não dá esse eco"* —
e é essa frase que derruba a hipótese do jogo. Pelo rádio a volta é lenta o
bastante para virar eco; pelo cabo, não. **Quando um sintoma aparece num
transporte e não no outro, a diferença ENTRE os dois é a pista.**

A CURA, medida no aparelho depois de ela religar o controle: eco sumiu, e o
microfone ficou MELHOR — RMS de 115,0 para 303,2 e pico de 1288 para 8627, com
ela falando as duas vezes.

A LIÇÃO, e é a da `SOM-ROTA-02` virada do avesso: lá se aprendeu que *não
escrever não é o lado neutro*; aqui, que **escrever zero também não é**. Num
byte de firmware cada BIT é uma decisão, inclusive a de deixá-lo em zero.
"""
from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.core import ds_output_report as rep

RAIZ = Path(__file__).resolve().parents[2]
CANONICA = RAIZ / "docs" / "protocol" / "dualsense-referencia-canonica.md"


class TestOCancelamentoDeEcoNasceLigado:
    def test_a_base_liga_o_cancelamento_de_eco(self) -> None:
        """A MORDIDA: tirar o `ECHO_CANCEL` da base devolve o eco ao rádio."""
        assert rep.AUDIO_CONTROL_BASE_SEGURA & rep.AUDIO_CONTROL_ECHO_CANCEL, (
            "a base do `common[7]` voltou a mandar o cancelamento de eco em ZERO"
        )

    def test_a_base_continua_forcando_o_microfone_interno(self) -> None:
        """A cura de 02/08 não se perde para a de hoje: as duas no mesmo byte.

        `FORCE_INTERNAL_MIC` foi o que curou a SOM-CANAL-01, quando escrever o
        byte com base ZERO fez o microfone parar de captar (o `parec` de 131072
        bytes para zero).
        """
        assert rep.AUDIO_CONTROL_BASE_SEGURA & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC

    def test_o_cancelamento_de_ruido_esta_ligado(self) -> None:
        """Decisão dela, 17/09/2026, diante do microfone do cabo.

            "sobre o mic do cabo ficar limpo igual o do mic no bt"

        `NOISE_CANCEL` mexe na qualidade da CAPTURA, e por isso ficou desligado
        até ela pedir. Ela pediu, e mandou valer nos DOIS transportes — ordem de
        16/09: trave a classe, não a instância.

        MORDIDA: tire `AUDIO_CONTROL_NOISE_CANCEL` da base e isto reprova.
        """
        assert rep.AUDIO_CONTROL_BASE_SEGURA & rep.AUDIO_CONTROL_NOISE_CANCEL, (
            "o cancelamento de ruído saiu da base — é a decisão dela de "
            "17/09/2026, e sem ele o microfone dela volta a não ficar limpo"
        )

    def test_o_bit_de_ruido_vale_nos_dois_transportes(self) -> None:
        """A CLASSE, não a instância: há UMA base, e os dois caminhos a usam.

        O rádio escreve `common[7]` em todo report 0x35
        (`alto_falante_bt.common_de_audio`); o cabo escreve pelo
        `_byte_da_rota` do backend. Se alguém criar uma segunda base para um
        transporte só, esta régua reprova — foi assim que o cabo passou dois
        meses sem o que o rádio tinha.
        """
        import pathlib
        import re

        import hefesto_dualsense4unix as pacote

        # O caminho sai do PACOTE, nunca digitado a partir da raiz: um arquivo
        # que mude de lugar tem de quebrar aqui, não passar em silêncio.
        raiz = pathlib.Path(pacote.__file__).parent
        bases = set()
        for relativo in (
            "integrations/alto_falante_bt.py",
            "core/backend_pydualsense.py",
        ):
            arq = raiz / relativo
            assert arq.is_file(), f"o escritor do byte 7 não está em {arq}"
            achadas = re.findall(r"AUDIO_CONTROL_BASE_\w+", arq.read_text(encoding="utf-8"))
            assert achadas, f"{relativo} parou de usar uma base nomeada do byte 7"
            bases.update(achadas)
        assert bases == {"AUDIO_CONTROL_BASE_SEGURA"}, (
            f"há mais de uma base do byte 7 em uso: {sorted(bases)} — os dois "
            "transportes têm de partir da mesma, senão um deles fica para trás"
        )

    def test_a_base_nao_invade_os_bits_da_rota(self) -> None:
        """Os bits 4-5 são da rota e têm dono próprio (`_byte_da_rota`).

        Base que já trouxesse rota embutida faria a escolha dela de «Sons do
        jogo» disputar com um valor que ninguém pediu.
        """
        assert not rep.AUDIO_CONTROL_BASE_SEGURA & rep.OUTPUT_PATH_SEL_MASK

    def test_os_bits_batem_com_a_referencia_canonica(self) -> None:
        """As constantes não podem divergir da tabela que as justifica.

        A referência é lida do fonte C dos drivers e é quem manda quando há
        desacordo. Se alguém mover um bit ali, isto reprova — que é o ponto.

        MORDIDA: troque `AUDIO_CONTROL_ECHO_CANCEL` para 0x08.
        """
        texto = CANONICA.read_text(encoding="utf-8")
        bloco = re.search(
            r"audio_control \(byte 7\):(.*?)```", texto, re.S
        )
        assert bloco, "a tabela do `audio_control` sumiu da referência canônica"
        corpo = bloco.group(1)

        #: A tabela nomeia os bits por POSIÇÃO; aqui se confere o valor.
        for nome, constante, posicao in (
            ("FORCE_INTERNAL_MIC", rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC, 0),
            ("ECHO_CANCEL", rep.AUDIO_CONTROL_ECHO_CANCEL, 2),
            ("NOISE_CANCEL", rep.AUDIO_CONTROL_NOISE_CANCEL, 3),
        ):
            assert f"bit{posicao} {nome}" in corpo, (
                f"a referência não diz mais `bit{posicao} {nome}`"
            )
            assert constante == 1 << posicao, (
                f"{nome} vale 0x{constante:02X}, e a referência o põe no bit "
                f"{posicao} (0x{1 << posicao:02X})"
            )
