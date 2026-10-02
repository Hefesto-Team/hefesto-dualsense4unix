"""BATERIA-QUE-PULA-01 — o áudio do microfone virava o número da bateria.

    "esse numero da bateria fica oscilando sem parar de 75 a 0 a 90 a 100"

O KERNEL ESTÁ ESTÁVEL, E O DEFEITO É NOSSO
-------------------------------------------
``/sys/class/power_supply/ps-controller-battery-…/capacity`` deu **75 em 300
leituras**, sem uma variação. O aparelho não oscila; o número que chega à tela,
sim.

A CAUSA: ``self.readInput(in_report)`` era chamado sobre TODO report cru, e o
``readInput`` da pydualsense **não confere nada** — nem report id, nem tamanho,
nem o CRC-32 do BT, nem o bit ``INPUT_FLAG_AUDIO``. Com a ponte de microfone por
rádio de pé, o DualSense manda Opus no MESMO report ``0x31``, com os MESMOS 78
bytes. ``states[53]`` — o byte da bateria — cai dentro da janela do Opus.

MEDIDO no aparelho: 600 amostras de ``daemon.state_full`` em 61 s, com a ponte
de pé, deram **14,8 % dos valores diferentes de 75**::

    75 -> 511x   100 -> 42x   85 -> 8x   25 -> 8x   95 -> 6x
    35 ->   6x    15 ->  5x   55 -> 5x    5 -> 4x   65 -> 3x   45 -> 2x

E o estado da carga trouxe **58 leituras fora dos seis valores que existem** —
só byte aleatório faz isso.

**A BATERIA É O MENOR DOS CAMPOS ENVENENADOS.** Tudo que o ``readInput``
escreve aceitava Opus como estado, e o pior é o ``state.micBtn``: ele **fecha um
laço**, porque o botão do microfone liga e desliga a ponte que produz o áudio
que o envenena.

E O 90 NÃO EXISTE — uma correção ao que ela viu
------------------------------------------------
Toda régua de bateria desta casa é ``nibble * 10 + 5``, que só produz
``{5, 15, …, 95, 100}``. O agente mediu **85** e **95**; a dez repinturas por
segundo, isso se lê como "90". Ela viu certo; o número é que não era 90.

O QUE A CASA JÁ SABIA, E COBRIU PELA METADE
--------------------------------------------
``core/backend_pydualsense.py`` descreve este mecanismo por escrito desde
**16/08/2026** (PS-PRESO-01, quando o botão PS e o do microfone ficaram presos).
A cura de então cobriu UM consumidor — o ``_captura_status_audio``, que passou a
conferir antes de ler — e deixou o ``readInput`` de fora. *Quando a cura conhece
a causa, ela cobre TODOS os chamadores*, e aqui só havia um: ``readInput`` tem um
único chamador em todo o ``src/``.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _PinnedPyDualSense,
)


def _bt_valido() -> bytes:
    """Um ``0x31`` de estado com CRC que fecha — o que o aparelho manda."""
    corpo = bytearray(prr.INPUT_REPORT_BT_SIZE - 4)
    corpo[0] = prr.INPUT_REPORT_BT
    corpo[1] = 0x00
    corpo[prr._BT_STRUCT_BASE + prr.BATTERY_STATUS_OFFSET] = 0x07
    crc = prr.bt_crc32(bytes(corpo), seed=prr.BT_INPUT_CRC_SEED)
    return bytes(corpo) + crc.to_bytes(4, "little")


def _bt_de_audio() -> bytes:
    """O MESMO report, com o bit de áudio — e CRC igualmente válido."""
    corpo = bytearray(_bt_valido()[:-4])
    corpo[1] = prr.INPUT_FLAG_AUDIO
    crc = prr.bt_crc32(bytes(corpo), seed=prr.BT_INPUT_CRC_SEED)
    return bytes(corpo) + crc.to_bytes(4, "little")


class TestARegua:
    def test_o_report_de_estado_passa(self) -> None:
        assert prr.eh_report_de_estado(_bt_valido()) is True

    def test_o_report_de_audio_e_recusado(self) -> None:
        """**O CASO QUE ORIGINOU TUDO.**"""
        assert prr.eh_report_de_estado(_bt_de_audio()) is False

    def test_o_crc_quebrado_e_recusado(self) -> None:
        mau = bytearray(_bt_valido())
        mau[-1] ^= 0xFF
        assert prr.eh_report_de_estado(bytes(mau)) is False

    def test_o_tamanho_errado_e_recusado_no_radio(self) -> None:
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_BT]) + bytes(9)) is False

    def test_o_tamanho_errado_e_recusado_tambem_no_cabo(self) -> None:
        """O furo que o juiz do desenho achou, e ele era real."""
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_USB]) + bytes(9)) is False
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_USB]) + bytes(59)) is True

    def test_vazio_e_id_desconhecido_sao_recusados(self) -> None:
        assert prr.eh_report_de_estado(b"") is False
        assert prr.eh_report_de_estado(bytes([0x99]) + bytes(77)) is False

    def test_a_porta_nao_e_uma_segunda_regua(self) -> None:
        """Ela delega ao `_struct_base`, e é isso que impede as duas de divergirem."""
        import inspect

        corpo = inspect.getsource(prr.eh_report_de_estado)
        assert "_struct_base(report) is not None" in corpo
        for proibido in ("INPUT_FLAG_AUDIO", "bt_crc32", "INPUT_REPORT_BT_SIZE"):
            assert proibido not in corpo.split('"""')[-1], (
                f"a porta copiou `{proibido}` — virou a segunda régua"
            )


class _Espiao(_PinnedPyDualSense):
    """Um handle que só registra o que passou pelos dois consumidores."""

    def __new__(cls):
        return object.__new__(cls)

    def __init__(self) -> None:
        self.viu_readinput: list[bytes] = []
        self.viu_audio: list[bytes] = []

    def readInput(self, r) -> None:  # noqa: N802 — nome da pydualsense
        self.viu_readinput.append(bytes(r))

    def _captura_status_audio(self, r) -> bool:
        aceito = super()._captura_status_audio(r)
        if aceito:
            self.viu_audio.append(bytes(r))
        return aceito


class TestAGuardaNoLaco:
    def test_o_report_de_estado_chega_aos_dois_consumidores(self) -> None:
        e = _Espiao()
        e._consumir_report(_bt_valido())
        assert len(e.viu_readinput) == 1
        assert len(e.viu_audio) == 1
        assert e._reports_aceitos == 1
        assert e._reports_recusados == 0

    def test_o_report_de_audio_nao_chega_ao_readinput(self) -> None:
        """**A cura, na ponta que importa.**"""
        e = _Espiao()
        e._consumir_report(_bt_de_audio())
        assert e.viu_readinput == [], "o Opus chegou ao leitor de estado"
        assert e.viu_audio == [], "o report de áudio passou pelo captador de estado"
        assert e._reports_recusados == 1

    def test_a_guarda_nao_congela_o_controle(self) -> None:
        """O risco que dói na mesa dela: guarda estrita demais = controle morto."""
        e = _Espiao()
        for _ in range(50):
            e._consumir_report(_bt_valido())
        assert e._reports_aceitos == 50
        assert e._reports_recusados == 0
        assert len(e.viu_readinput) == 50

    def test_avisa_uma_vez_por_handle(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mais de cem reports de áudio por segundo — um aviso por report afoga."""
        e = _Espiao()
        for _ in range(200):
            e._consumir_report(_bt_de_audio())
        assert e._reports_recusados == 200
        assert e._recusa_avisada is True

    def test_lixo_que_nao_vira_bytes_nao_derruba_o_laco(self) -> None:
        e = _Espiao()
        e._consumir_report(object())
        assert e.viu_readinput == []

    def test_os_contadores_sao_default_de_classe(self) -> None:
        """Dezesseis dublês desta suíte constroem o handle por `__new__`."""
        assert _PinnedPyDualSense._reports_aceitos == 0
        assert _PinnedPyDualSense._reports_recusados == 0
        assert _PinnedPyDualSense._recusa_avisada is False
        nu = object.__new__(_PinnedPyDualSense)
        assert nu._reports_aceitos == 0, "o dublê por __new__ nasce sem o contador"


class TestACuraEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def _fonte(self) -> str:
        from pathlib import Path

        from hefesto_dualsense4unix.core import backend_pydualsense as bp

        return Path(bp.__file__).read_text(encoding="utf-8")

    def test_o_laco_chama_a_guarda_e_nao_o_readinput(self) -> None:
        """MORDIDA: devolver `self.readInput(in_report)` ao laço de `sendReport`."""
        fonte = self._fonte()
        assert "self._consumir_lote(lidos)" in fonte, (
            "o laço não passa mais pela guarda — a voz dela volta a ser bateria"
        )
        assert "self._consumir_lote((in_report,))" in fonte, (
            "a porta de UM report não passa mais pela guarda do lote"
        )
        assert (
            "                    self.readInput(in_report)\n"
            "                    self._captura_status_audio(in_report)"
        ) not in fonte, "a chamada NUA voltou ao laço"

    def test_o_readinput_so_e_chamado_de_dentro_da_guarda(self) -> None:
        """Um único chamador executável, e ele é o `_consumir_lote`."""
        fonte = self._fonte()
        chamadas = [
            linha for linha in fonte.splitlines()
            if "self.readInput(" in linha and not linha.strip().startswith("#")
        ]
        assert len(chamadas) == 1, f"o readInput ganhou outro chamador: {chamadas}"
        alvo = fonte.index(chamadas[0])
        antes = fonte[:alvo]
        assert antes.rindex("def _consumir_lote") > antes.rindex("def sendReport"), (
            "a única chamada do readInput não está dentro do `_consumir_lote`"
        )
        assert antes.rindex("def _consumir_lote") > antes.rindex("def _esvaziar_a_fila"), (
            "a única chamada do readInput não está dentro do `_consumir_lote`"
        )

    def test_a_captura_de_audio_tambem_passa_pela_guarda(self) -> None:
        """Ela já conferia por dentro desde 01/09 — agora nem é chamada à toa."""
        fonte = self._fonte()
        chamadas = [
            linha for linha in fonte.splitlines()
            if "self._captura_status_audio(" in linha
            and not linha.strip().startswith("#")
        ]
        assert len(chamadas) == 1, f"a captura ganhou outro chamador: {chamadas}"

    def test_a_leitura_viva_fica_fora_da_guarda(self) -> None:
        """Um report de áudio é prova de que o aparelho está FALANDO.

        Registrá-lo depois da guarda faria um controle com a ponte do microfone
        de pé ser anunciado como «entrada muda» — trocaria um defeito por outro.

        MORDIDA: mover o `_registrar_leitura_viva()` para dentro do
        `_consumir_lote`. Desde 29/09/2026 ela conta na drenagem, report a
        report, antes de o lote chegar à guarda (`_esvaziar_a_fila`).
        """
        fonte = self._fonte()
        marca = (
            "self._registrar_leitura_viva()\n"
            "            lidos.append(in_report)"
        )
        i_viva = fonte.index(marca)
        assert i_viva > 0, (
            "o `_registrar_leitura_viva` saiu de antes da guarda; "
            "um controle falando por áudio passaria por mudo"
        )


class TestOZeroPorCentoTemDonoProprio:
    """A segunda causa, e é a única que explica o **0** literal do relato dela."""

    class _DS:
        def __init__(self, level):
            self.battery = type("B", (), {"Level": level})()

    def test_level_zero_e_sem_dado_ainda_e_nao_bateria_vazia(self) -> None:
        """`DSBattery.__init__` nasce com `Level = 0`."""
        assert PyDualSenseController._read_battery_opt(self._DS(0)) is None

    def test_um_valor_de_verdade_passa(self) -> None:
        assert PyDualSenseController._read_battery_opt(self._DS(75)) == 75
        #: O mínimo que um DualSense reporta é 5 (`nibble 0 -> 0*10+5`).
        assert PyDualSenseController._read_battery_opt(self._DS(5)) == 5

    def test_sem_objeto_de_bateria_continua_none(self) -> None:
        assert PyDualSenseController._read_battery_opt(object()) is None

    def test_a_docstring_parou_de_prometer_o_que_nao_fazia(self) -> None:
        """Ela dizia *"Preserva a distinção 'sem dado ainda' (None) de '0%'"*."""
        import inspect

        doc = inspect.getdoc(PyDualSenseController._read_battery_opt) or ""
        assert "16/09/2026" in doc, "a correção não ficou datada"
        assert "DSBattery" in doc
