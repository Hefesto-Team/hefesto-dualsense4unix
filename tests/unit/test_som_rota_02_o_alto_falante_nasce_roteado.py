"""SOM-ROTA-02 — o alto-falante nasce ROTEADO, não só com volume.

O DEFEITO, medido na bancada dela em 16/09/2026 com os dois DualSense no cabo e
ela do lado do controle: o `SOM-SEMPRE-01` (16/08) punha o volume em 100% em
todo controle adotado e deixava a rota de saída em branco **de propósito** —
`common[7]` carrega também o caminho do microfone, e mexer nele sem opinião
pareceu decidir por ela.

A premissa caiu: **o default do firmware não é neutro.** Ele é
`SAIDA_ESTEREO_NO_FONE` (0), o conector de fone — que está vazio. Não escrever
a rota É escolher o fone. O volume ia inteiro para lugar nenhum:

    rota=None, volume=102, tom de 880 Hz no sink do controle ... ela: nada
    `speaker.set {"rota": 3}`, o MESMO tom .................... ela: "Saiu som"

Efeito por inteiro: a decisão dela de 16/08 — *"precisamos setar o som sempre em
todos os controles no 100%"* — nunca se cumpriu. Cem por cento mandados para
lugar nenhum é silêncio. **Cura que cobre metade do par não cura.**

O VALOR é decisão dela, 16/09/2026, entre os três botões da aba Controles:
«Sons do jogo» (2), e não «Só no controle» (3), porque a rota 3 calaria a TV
assim que qualquer controle conectasse.

AS MORDIDAS: devolver `rota=None` à adoção faz o controle nascer no fone de
novo; e trocar o padrão por 3 cala a televisão dela.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep


#: Dublê e montagem vêm da régua IRMÃ, `test_som_sempre_01_...`: as duas medem
#: o mesmo caminho de adoção e não podem divergir na definição do que é um
#: handle adotado — duas noções de "adotado" dariam verde sobre produtos
#: diferentes.
from tests.unit.test_som_sempre_01_o_volume_nasce_em_cem import (
    _backend_com_um_handle,
)

CHAVE = "AA:BB:CC:00:00:01"


def _rota_escrita(handle: Any) -> int | None:
    """O `OUTPUT_PATH_SEL` do `common[7]` que a adoção deixou no handle."""
    byte = handle._volumes_audio[3]
    if byte is None:
        return None
    return (int(byte) & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT


class TestOAltoFalanteNasceRoteado:
    def test_a_adocao_escreve_a_rota(self) -> None:
        """A MORDIDA: com `rota=None`, isto volta a ser `SAIDA_ESTEREO_NO_FONE`."""
        inst, handle = _backend_com_um_handle()

        inst.assumir_volume_padrao_na_adocao(CHAVE, handle)

        assert _rota_escrita(handle) == rep.SAIDA_L_FONE_R_ALTO_FALANTE

    def test_a_rota_nao_e_o_fone(self) -> None:
        """Dito pelo efeito: o que a bancada mediu como silêncio não pode voltar."""
        inst, handle = _backend_com_um_handle()

        inst.assumir_volume_padrao_na_adocao(CHAVE, handle)

        assert _rota_escrita(handle) not in (
            rep.SAIDA_ESTEREO_NO_FONE,
            rep.SAIDA_MONO_NO_FONE,
        )

    def test_o_volume_continua_nos_cem_por_cento(self) -> None:
        """A cura de 16/08 não se perde para a de hoje: as duas no mesmo report."""
        inst, handle = _backend_com_um_handle()

        inst.assumir_volume_padrao_na_adocao(CHAVE, handle)

        assert handle._volumes_audio[1] == bp.VOLUME_PADRAO_DO_SOM

    def test_o_padrao_nao_cala_a_televisao_dela(self) -> None:
        """A MORDIDA: trocar o padrão por 3 manda TODO o som para o controle.

        Decisão dela de 16/09/2026, e é sobre o som que sai na sala: um controle
        que conecta não pode emudecer a TV sem ela ter pedido.
        """
        assert bp.ROTA_PADRAO_DO_SOM != rep.SAIDA_SO_NO_ALTO_FALANTE
        assert bp.ROTA_PADRAO_DO_SOM == rep.SAIDA_L_FONE_R_ALTO_FALANTE

    def test_os_bits_do_microfone_sobrevivem(self) -> None:
        """A razão que tornava a omissão prudente continua honrada.

        `common[7]` carrega a rota (bits 4-5) e o caminho do microfone (o
        resto). Escrever a rota não pode apagar o `FORCE_INTERNAL_MIC` — foi
        assim que o microfone ficou mudo em 2026-08, com o `parec` em ZERO.
        """
        inst, handle = _backend_com_um_handle()

        inst.assumir_volume_padrao_na_adocao(CHAVE, handle)

        byte = handle._volumes_audio[3]
        assert byte is not None
        fora_da_rota = int(byte) & ~rep.OUTPUT_PATH_SEL_MASK
        assert fora_da_rota == (
            rep.AUDIO_CONTROL_BASE_SEGURA & ~rep.OUTPUT_PATH_SEL_MASK
        )
