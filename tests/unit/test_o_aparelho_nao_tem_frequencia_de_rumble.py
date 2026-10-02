"""A régua das duas linhas de ENERGIA e VIBRAÇÃO do mapa — 03/09/2026."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.physical_report_reader import (
    BATTERY_STATUS_OFFSET,
    decodificar_bateria,
)

_RAIZ = Path(__file__).resolve().parents[2]
_DRIVER = _RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"

_ESTADOS_DE_CARGA = (
    (0x0, "case 0x0:", True),
    (0x1, "case 0x1:", True),
    (0x2, "case 0x2:", True),
    (0xA, "case 0xa:", False),
    (0xB, "case 0xb:", False),
    (0xF, "case 0xf:", False),
)


def fonte_do_driver() -> str:
    """O texto do driver da DKMS, ou pula se a cópia não veio nesta árvore."""
    if not _DRIVER.is_file():
        pytest.skip(f"a cópia DKMS do driver não está em {_DRIVER}")
    return _DRIVER.read_text(encoding="utf-8", errors="replace")


def corpo_do_struct(fonte: str, nome: str) -> str:
    """O bloco ``struct <nome> { ... }`` do fonte, sem as chaves."""
    achado = re.search(
        r"struct\s+" + re.escape(nome) + r"\s*\{(?P<corpo>.*?)\n\}",
        fonte,
        re.DOTALL,
    )
    assert achado is not None, f"o fonte não tem `struct {nome}`"
    return achado.group("corpo")


class TestOQueODriverDestaMaquinaDiz:
    """As afirmações da linha `vibracao.rumble.frequencia`."""

    def test_a_v2_e_um_bit_e_nao_um_numero(self) -> None:
        """A v2 é um BIT, e o corpo que a carrega tem 47 bytes."""
        fonte = fonte_do_driver()

        assert "DS_OUTPUT_VALID_FLAG2_COMPATIBLE_VIBRATION2\t\tBIT(2)" in fonte, (
            "a v2 deixou de ser o bit 2 do `valid_flag2` — o mapa diz que é"
        )
        assert (
            "static_assert(sizeof(struct dualsense_output_report_common) == 47)"
            in fonte
        ), "o corpo do report de saída deixou de ter 47 bytes"
        assert "DS_FEATURE_VERSION(2, 21)" in fonte, (
            "o limiar de firmware da v2 mudou; a §4.1 do documento compara "
            "este número com o 0x0224 das fontes de fora"
        )
        assert "ds->update_version = get_unaligned_le16(&buf[44])" in fonte, (
            "a versão de firmware deixou de sair do byte 44 — é o campo que "
            "os três projetos leem, e é o que torna a divergência comparável"
        )

    def test_o_bit_da_v2_entra_no_lugar_do_bit_da_v1(self) -> None:
        """v1 e v2 são exclusivos: um `if/else`, nunca os dois juntos."""
        fonte = fonte_do_driver()
        trecho = re.search(
            r"if \(ds->use_vibration_v2\)\s*\n(?P<v2>[^\n]*)\n\s*else\s*\n(?P<v1>[^\n]*)",
            fonte,
        )
        assert trecho is not None, (
            "o `if (ds->use_vibration_v2) ... else ...` sumiu do driver"
        )
        assert "VALID_FLAG2_COMPATIBLE_VIBRATION2" in trecho.group("v2")
        assert "VALID_FLAG0_COMPATIBLE_VIBRATION" in trecho.group("v1")

    def test_nenhum_campo_do_corpo_se_chama_frequencia(self) -> None:
        """A prova de COMPLETUDE: 47 bytes nomeados, e nenhum é frequência."""
        corpo = corpo_do_struct(fonte_do_driver(), "dualsense_output_report_common")
        suspeitos = [
            linha.strip()
            for linha in corpo.splitlines()
            if re.search(r"freq", linha, re.IGNORECASE)
        ]
        assert not suspeitos, (
            f"apareceu campo com cara de frequência no corpo: {suspeitos}"
        )
        assert "motor_right" in corpo and "motor_left" in corpo, (
            "os dois bytes de AMPLITUDE sumiram; são eles que existem por motor"
        )


class TestOByteDaBateria:
    """As afirmações da linha `energia.bateria.leitura_hefesto`."""

    def test_o_offset_do_produto_e_o_do_driver(self) -> None:
        """52 é o byte do CORPO, e o produto usa o mesmo número."""
        fonte = fonte_do_driver()
        assert BATTERY_STATUS_OFFSET == 52, (
            "o produto mudou de offset; o mapa diz 52 nos dois transportes"
        )
        assert "DS_STATUS0_BATTERY_CAPACITY\t\tGENMASK(3, 0)" in fonte, (
            "o nível deixou de ser o nibble BAIXO"
        )
        assert "DS_STATUS0_CHARGING\t\t\tGENMASK(7, 4)" in fonte, (
            "o estado de carga deixou de ser o nibble ALTO"
        )
        assert "battery_capacity = min(battery_data * 10 + 5, 100)" in fonte, (
            "a conta do nível mudou; o mapa e as quatro fontes de fora dizem "
            "min(nível*10+5, 100)"
        )

    @pytest.mark.parametrize(("nibble", "caso", "sabe_o_nivel"), _ESTADOS_DE_CARGA)
    def test_os_seis_estados_de_carga_batem_com_o_driver(
        self, nibble: int, caso: str, sabe_o_nivel: bool
    ) -> None:
        """Cada estado que o driver trata, o produto também sabe responder."""
        assert caso in fonte_do_driver(), (
            f"o driver deixou de tratar o estado de carga {nibble:#x}"
        )
        percentual, _carregando = decodificar_bateria((nibble << 4) | 0x7)
        if sabe_o_nivel:
            assert percentual is not None, (
                f"o estado {nibble:#x} é de leitura boa e o produto disse 'não sei'"
            )
        else:
            assert percentual is None, (
                f"o estado {nibble:#x} é de ERRO e o produto respondeu "
                f"{percentual}% como se soubesse"
            )

    def test_o_nivel_para_em_dez_e_por_isso_a_conta_satura(self) -> None:
        """O achado que veio de fora: o nibble baixo vai só até 0x0A."""
        vistos = {decodificar_bateria(nivel)[0] for nivel in range(0x0, 0x0B)}
        assert vistos == {5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 100}, (
            f"a escala de onze níveis mudou: {sorted(v for v in vistos if v)}"
        )
