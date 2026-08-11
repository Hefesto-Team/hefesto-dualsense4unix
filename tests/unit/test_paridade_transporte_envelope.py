"""PARIDADE-BYTE-01 — a honestidade do INSTRUMENTO, antes de medir o produto.

Este arquivo não mede feature nenhuma: mede a fixture `transporte` do
`tests/conftest.py`. Ele existe por causa da armadilha nº 1 desta casa — *o
instrumento pode estar brigando com o produto* — e da regra que dela nasceu:
**todo instrumento tem de declarar contra qual biblioteca está medindo**.

A fixture declara: os valores dela ou são constantes importadas de
`core/ds_output_report.py`, ou são MEDIDOS chamando o builder de produção. Os
testes abaixo travam essa declaração: se alguém trocar a fixture por uma que
monta o 0x31 sozinha, ela para de concordar com o módulo de produção e este
arquivo reprova antes que qualquer teste de feature meça a si mesmo.

MORDIDA PROVADA (11/08/2026, `src/` copiado para fora da árvore, `PYTHONPATH`
apontado para a cópia — a árvore de trabalho nunca foi mutada). As três
mutações clássicas de envelope, medidas contra a LEVA INTEIRA (116 casos), com
o número que o diagnóstico de 10/08 mediu contra os 8589 ao lado:

    mutação em `ds_output_report.py`      esta leva      suíte de 10/08
    payload deslocado 1 byte no BT ....      30                 5
    CRC gravado em big-endian .........      31                 6
    tag 0x10 trocado por 0xFF .........      29                 6

O envelope já estava travado, e continua: o ganho aqui não é pegar o que
ninguém pegava, é que agora **cada feature** vai junto quando o envelope cai —
e o id do caso diz em qual transporte.

**SOBRE OS BYTES DE BLUETOOTH DESTE ARQUIVO (e de toda a leva):** eles são
**MONTADOS** pelo builder de produção, nunca CAPTURADOS de um controle. O
`hid_capture_bt.bin` que o ADR-008 afirma existir **nunca existiu** — a única
captura HID gravada na suíte é USB. Chamar um buffer sintético de "captura"
seria medição inventada, que é a doença que esta casa mais paga caro; então
está dito no nome, no comentário e no relatório: **montado**.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

#: Um common MONTADO com todos os 47 offsets distinguíveis — o mesmo marcador
#: que a fixture usa para MEDIR onde o payload cai dentro do envelope.
COMMON_MARCADO = bytes(range(rep.COMMON_LEN))


class TestOInstrumentoConcordaComOProduto:
    """A fixture não pode ser uma segunda implementação do envelope."""

    def test_o_report_id_e_o_do_modulo_de_producao(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        esperado = {"usb": rep.USB_REPORT_ID, "bt": rep.BT_REPORT_ID}[transporte.nome]
        assert transporte.report_id == esperado, (
            f"o instrumento diz que o report id do {transporte.nome} é "
            f"{transporte.report_id:#04x}; a produção diz {esperado:#04x}"
        )

    def test_o_tamanho_e_o_do_modulo_de_producao(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        esperado = {"usb": rep.USB_REPORT_LEN, "bt": rep.BT_REPORT_LEN}[transporte.nome]
        assert transporte.tamanho_do_report == esperado

    def test_o_deslocamento_do_common_foi_medido_no_builder(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        """O offset não está escrito na fixture — ela o acha dentro do report."""
        report = transporte.montar(COMMON_MARCADO)
        inicio = transporte.deslocamento_do_common
        assert bytes(report[inicio : inicio + rep.COMMON_LEN]) == COMMON_MARCADO
        # E o valor medido é o do layout do `hid-playstation`: 1 no cabo (só o
        # report id na frente), 3 no rádio (id + seq + tag).
        assert inicio == {"usb": 1, "bt": 3}[transporte.nome]

    def test_a_semente_do_crc_e_a_do_modulo(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        esperado = {"usb": None, "bt": rep.BT_CRC_SEED}[transporte.nome]
        assert transporte.semente_do_crc == esperado

    def test_extrair_common_devolve_o_que_foi_montado(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        report = transporte.montar(COMMON_MARCADO)
        assert transporte.extrair_common(report) == COMMON_MARCADO

    def test_os_params_do_decorador_nao_divergem_da_lista_da_casa(self) -> None:
        """Os dois nomes estão escritos duas vezes — aqui eles não podem brigar.

        O decorador da fixture repete `["usb", "bt"]` à mão para que o CENSO
        (que lê o código com `ast`) enxergue a parametrização; `TRANSPORTES` é a
        lista que o resto do conftest usa. Duplicação que ninguém vigia é
        duplicação que diverge — este caso é a vigia.
        """
        import tests.conftest as conf

        # O pytest 9 guarda o marcador em `_fixture_function_marker`; versões
        # antigas o penduravam como `_pytestfixturefunction`. Os dois nomes são
        # privados, então o caso aceita qualquer um dos dois e só reprova
        # quando ACHA os params e eles divergem.
        marcador = getattr(
            conf.transporte,
            "_fixture_function_marker",
            getattr(conf.transporte, "_pytestfixturefunction", None),
        )
        params = getattr(marcador, "params", None)
        assert params is not None, (
            "não achei os params da fixture `transporte` — o pytest mudou o "
            "atributo privado e esta vigia precisa ser atualizada"
        )
        assert tuple(params) == conf.TRANSPORTES


class TestOEnvelopeInteiro:
    """`problemas_do_envelope` só fica vazio para envelope BEM-FORMADO."""

    def test_report_de_producao_nao_tem_problema_nenhum(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        report = transporte.montar(COMMON_MARCADO, seq=7)
        assert transporte.problemas_do_envelope(report) == []

    def test_report_truncado_reprova(self, transporte: EnvelopeDeTransporte) -> None:
        report = transporte.montar(COMMON_MARCADO)
        assert transporte.problemas_do_envelope(bytes(report)[:-1]) != []

    def test_report_id_trocado_reprova(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        report = bytearray(transporte.montar(COMMON_MARCADO))
        report[0] ^= 0xFF
        assert transporte.problemas_do_envelope(report) != []

    def test_payload_deslocado_um_byte_reprova(
        self, transporte: EnvelopeDeTransporte
    ) -> None:
        """O off-by-one da pydualsense 0.7.5 — o defeito que criou o BTREPORT-02."""
        report = bytearray(transporte.montar(COMMON_MARCADO))
        deslocado = bytearray(report)
        inicio = transporte.deslocamento_do_common
        deslocado[inicio + 1 : inicio + 1 + rep.COMMON_LEN] = COMMON_MARCADO
        assert transporte.extrair_common(deslocado) != COMMON_MARCADO


class TestOQueSoOBluetoothTem:
    """CRC e nibble de sequência: presentes no rádio, ausentes no cabo."""

    def test_o_cabo_nao_tem_crc_nem_sequencia(
        self, transportes: tuple[EnvelopeDeTransporte, ...]
    ) -> None:
        usb = next(t for t in transportes if t.nome == "usb")
        report = usb.montar(COMMON_MARCADO, seq=9)
        assert usb.semente_do_crc is None
        assert usb.crc_do_report(report) is None
        assert usb.sequencia_de(report) is None
        assert usb.tag is None

    def test_o_radio_tem_tag_crc_e_sequencia(
        self, transportes: tuple[EnvelopeDeTransporte, ...]
    ) -> None:
        bt = next(t for t in transportes if t.nome == "bt")
        report = bt.montar(COMMON_MARCADO, seq=9)
        assert bt.tag == rep.BT_TAG
        assert bytes(report)[2] == rep.BT_TAG
        assert bt.sequencia_de(report) == 9
        assert bt.crc_do_report(report) == bt.crc_esperado(report)

    @pytest.mark.parametrize("seq", [0, 1, 9, 15])
    def test_o_carimbo_de_sequencia_mexe_so_em_seq_e_crc(self, seq: int) -> None:
        from tests.conftest import envelope_de

        bt = envelope_de("bt")
        report = bt.montar(COMMON_MARCADO, seq=0)
        antes = bytes(report)
        rep.stamp_bt_seq(report, seq)
        assert bt.sequencia_de(report) == seq
        assert bt.crc_do_report(report) == bt.crc_esperado(report)
        assert bytes(report)[2:74] == antes[2:74]

    def test_crc_invertido_reprova(self) -> None:
        from tests.conftest import envelope_de

        bt = envelope_de("bt")
        report = bytearray(bt.montar(COMMON_MARCADO, seq=0))
        report[-4:] = bytes(reversed(report[-4:]))
        # Um CRC palíndromo passaria — este vetor não é (conferido aqui mesmo).
        if bytes(report[-4:]) != bytes(reversed(report[-4:])):
            assert bt.problemas_do_envelope(report) != []


class TestABancadaNaoPodeMedirAPyDualSense:
    """O `except Exception` do `prepareReport` cai no report do UPSTREAM.

    Sem a mordaça que a fixture instala, uma bancada incompleta mediria a
    pydualsense (cujo 0x31 é malformado) e chamaria isso de produto. Aqui se
    prova que a mordaça está viva: o fallback EXPLODE.
    """

    def test_o_fallback_do_upstream_explode_em_vez_de_mentir(
        self, ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
    ) -> None:
        # Quebra o handle de um jeito que o `_build_common` não sobrevive:
        # sem `light` não há como montar os bytes de LED.
        del ds5_de_bancada.light
        with pytest.raises(AssertionError, match="fallback do upstream"):
            ds5_de_bancada.prepareReport()

    def test_a_bancada_inteira_monta_o_envelope_do_seu_transporte(
        self, ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
    ) -> None:
        report = ds5_de_bancada.prepareReport()
        assert transporte.problemas_do_envelope(report) == []
        assert len(report) == transporte.tamanho_do_report
