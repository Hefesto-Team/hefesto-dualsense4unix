"""SOM-ECO-01 — escrever ZERO num bit de firmware também não é neutro."""
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
        """A cura de 02/08 não se perde para a de hoje: as duas no mesmo byte."""
        assert rep.AUDIO_CONTROL_BASE_SEGURA & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC

    def test_o_cancelamento_de_ruido_esta_ligado(self) -> None:
        """Decisão dela, 17/09/2026, diante do microfone do cabo."""
        assert rep.AUDIO_CONTROL_BASE_SEGURA & rep.AUDIO_CONTROL_NOISE_CANCEL, (
            "o cancelamento de ruído saiu da base — é a decisão dela de "
            "17/09/2026, e sem ele o microfone dela volta a não ficar limpo"
        )

    def test_o_bit_de_ruido_vale_nos_dois_transportes(self) -> None:
        """A CLASSE, não a instância: há UMA base, e os dois caminhos a usam."""
        import pathlib
        import re

        import hefesto_dualsense4unix as pacote

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
        """Os bits 4-5 são da rota e têm dono próprio (`_byte_da_rota`)."""
        assert not rep.AUDIO_CONTROL_BASE_SEGURA & rep.OUTPUT_PATH_SEL_MASK

    def test_os_bits_batem_com_a_referencia_canonica(self) -> None:
        """As constantes não podem divergir da tabela que as justifica."""
        texto = CANONICA.read_text(encoding="utf-8")
        bloco = re.search(
            r"audio_control \(byte 7\):(.*?)```", texto, re.S
        )
        assert bloco, "a tabela do `audio_control` sumiu da referência canônica"
        corpo = bloco.group(1)

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
