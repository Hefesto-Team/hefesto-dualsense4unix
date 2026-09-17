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
    corpo[1] = 0x00  # sem o bit de áudio
    corpo[prr._BT_STRUCT_BASE + prr.BATTERY_STATUS_OFFSET] = 0x07  # nibble 7 = 75%
    crc = prr.bt_crc32(bytes(corpo), seed=prr.BT_INPUT_CRC_SEED)
    return bytes(corpo) + crc.to_bytes(4, "little")


def _bt_de_audio() -> bytes:
    """O MESMO report, com o bit de áudio — e CRC igualmente válido.

    É o ponto inteiro do defeito: ele é indistinguível pelo tamanho e pelo CRC.
    Só o bit denuncia.
    """
    corpo = bytearray(_bt_valido()[:-4])
    corpo[1] = prr.INPUT_FLAG_AUDIO
    crc = prr.bt_crc32(bytes(corpo), seed=prr.BT_INPUT_CRC_SEED)
    return bytes(corpo) + crc.to_bytes(4, "little")


class TestARegua:
    def test_o_report_de_estado_passa(self) -> None:
        assert prr.eh_report_de_estado(_bt_valido()) is True

    def test_o_report_de_audio_e_recusado(self) -> None:
        """**O CASO QUE ORIGINOU TUDO.**

        Mesmo id, mesmo tamanho, CRC igualmente válido — só o bit muda. Se esta
        linha cair, a voz dela volta a virar bateria.

        MORDIDA: apagar o `if report[1] & INPUT_FLAG_AUDIO` do `_struct_base`.
        """
        assert prr.eh_report_de_estado(_bt_de_audio()) is False

    def test_o_crc_quebrado_e_recusado(self) -> None:
        mau = bytearray(_bt_valido())
        mau[-1] ^= 0xFF
        assert prr.eh_report_de_estado(bytes(mau)) is False

    def test_o_tamanho_errado_e_recusado_no_radio(self) -> None:
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_BT]) + bytes(9)) is False

    def test_o_tamanho_errado_e_recusado_tambem_no_cabo(self) -> None:
        """O furo que o juiz do desenho achou, e ele era real.

        `_struct_base` devolvia a base do USB sem olhar o tamanho: um `0x01` de
        dez bytes passava, e quem lesse `JACK_STATUS_OFFSET` leria além do fim.

        MORDIDA: tirar o `if len(report) <= _USB_STRUCT_BASE + JACK_STATUS_OFFSET`.
        """
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_USB]) + bytes(9)) is False
        #: E o suficiente PASSA — recusar um report curto porém completo
        #: calaria o cabo por rigor que nada protege.
        assert prr.eh_report_de_estado(bytes([prr.INPUT_REPORT_USB]) + bytes(59)) is True

    def test_vazio_e_id_desconhecido_sao_recusados(self) -> None:
        assert prr.eh_report_de_estado(b"") is False
        assert prr.eh_report_de_estado(bytes([0x99]) + bytes(77)) is False

    def test_a_porta_nao_e_uma_segunda_regua(self) -> None:
        """Ela delega ao `_struct_base`, e é isso que impede as duas de divergirem.

        MORDIDA: reescrever `eh_report_de_estado` com uma cópia das conferências.
        """
        import inspect

        corpo = inspect.getsource(prr.eh_report_de_estado)
        assert "_struct_base(report) is not None" in corpo
        for proibido in ("INPUT_FLAG_AUDIO", "bt_crc32", "INPUT_REPORT_BT_SIZE"):
            assert proibido not in corpo.split('"""')[-1], (
                f"a porta copiou `{proibido}` — virou a segunda régua"
            )


class _Espiao(_PinnedPyDualSense):
    """Um handle que só registra o que passou pelos dois consumidores."""

    def __new__(cls):  # o dublê nasce sem `__init__` de propósito
        return object.__new__(cls)

    def __init__(self) -> None:
        self.viu_readinput: list[bytes] = []
        self.viu_audio: list[bytes] = []

    def readInput(self, r) -> None:  # noqa: N802 — nome da pydualsense
        self.viu_readinput.append(bytes(r))

    def _captura_status_audio(self, r) -> None:
        self.viu_audio.append(bytes(r))


class TestAGuardaNoLaco:
    def test_o_report_de_estado_chega_aos_dois_consumidores(self) -> None:
        e = _Espiao()
        e._consumir_report(_bt_valido())
        assert len(e.viu_readinput) == 1
        assert len(e.viu_audio) == 1
        assert e._reports_aceitos == 1
        assert e._reports_recusados == 0

    def test_o_report_de_audio_nao_chega_ao_readinput(self) -> None:
        """**A cura, na ponta que importa.**

        MORDIDA: trocar `_consumir_report` de volta por `readInput` direto.
        """
        e = _Espiao()
        e._consumir_report(_bt_de_audio())
        assert e.viu_readinput == [], "o Opus chegou ao leitor de estado"
        assert e.viu_audio == [], "o report de áudio passou pelo captador de estado"
        assert e._reports_recusados == 1

    def test_a_guarda_nao_congela_o_controle(self) -> None:
        """O risco que dói na mesa dela: guarda estrita demais = controle morto.

        `_reports_aceitos` subindo é a prova viva do contrário, e é por isso
        que o contador existe.
        """
        e = _Espiao()
        for _ in range(50):
            e._consumir_report(_bt_valido())
        assert e._reports_aceitos == 50
        assert e._reports_recusados == 0
        assert len(e.viu_readinput) == 50

    def test_avisa_uma_vez_por_handle(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mais de cem reports de áudio por segundo — um aviso por report afoga.

        MORDIDA: tirar o `if self._recusa_avisada: return`.
        """
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
        """Dezesseis dublês desta suíte constroem o handle por `__new__`.

        Um dublê mais POBRE que o produto esconde defeito em vez de revelar —
        regra desta casa.

        MORDIDA: mover os três para o `__init__`.
        """
        assert _PinnedPyDualSense._reports_aceitos == 0
        assert _PinnedPyDualSense._reports_recusados == 0
        assert _PinnedPyDualSense._recusa_avisada is False
        nu = object.__new__(_PinnedPyDualSense)
        assert nu._reports_aceitos == 0, "o dublê por __new__ nasce sem o contador"


class TestACuraEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa.

    **ESTA CLASSE NASCEU DE UMA MORDIDA QUE NÃO MORDEU.** A primeira versão
    desta régua exercitava `_consumir_report` por um espião — e quando o laço
    foi trocado de volta por `readInput` direto, os dezessete casos passaram
    VERDES. A régua olhava o método e não o caminho; a cura podia ser desligada
    sem ninguém ver, que é o mesmo buraco por onde a `sentinela_do_wrapper`
    passou (19 testes e zero chamadores).
    """

    def _fonte(self) -> str:
        from pathlib import Path

        from hefesto_dualsense4unix.core import backend_pydualsense as bp

        return Path(bp.__file__).read_text(encoding="utf-8")

    def test_o_laco_chama_a_guarda_e_nao_o_readinput(self) -> None:
        """MORDIDA: devolver `self.readInput(in_report)` ao laço de `sendReport`.

        O `readInput` continua existindo — ele é chamado DE DENTRO da guarda,
        depois de o report ser aprovado. O que não pode voltar é a chamada
        NUA no laço.
        """
        fonte = self._fonte()
        assert "self._consumir_report(in_report)" in fonte, (
            "o laço não passa mais pela guarda — a voz dela volta a ser bateria"
        )
        #: A chamada nua tinha esta forma exata, com a captura de áudio ao lado.
        assert (
            "                    self.readInput(in_report)\n"
            "                    self._captura_status_audio(in_report)"
        ) not in fonte, "a chamada NUA voltou ao laço"

    def test_o_readinput_so_e_chamado_de_dentro_da_guarda(self) -> None:
        """Um único chamador executável, e ele é o `_consumir_report`.

        É o que torna esta cura completa: cobrir aqui cobre TODOS os campos que
        o `readInput` escreve — bateria, `micBtn`, botões, eixos, IMU.
        """
        fonte = self._fonte()
        chamadas = [
            linha for linha in fonte.splitlines()
            if "self.readInput(" in linha and not linha.strip().startswith("#")
        ]
        assert len(chamadas) == 1, f"o readInput ganhou outro chamador: {chamadas}"
        alvo = fonte.index(chamadas[0])
        antes = fonte[:alvo]
        assert antes.rindex("def _consumir_report") > antes.rindex("def sendReport"), (
            "a única chamada do readInput não está dentro do `_consumir_report`"
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
        `_consumir_report`.
        """
        fonte = self._fonte()
        marca = (
            "self._registrar_leitura_viva()\n"
            "                    self._consumir_report"
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
        """`DSBattery.__init__` nasce com `Level = 0`.

        Todo handle recém-aberto — ou seja, toda reconexão de rádio — publicava
        0% até o primeiro report. A função IRMÃ já tinha esta guarda.

        MORDIDA: tirar o `if value <= 0: return None`.
        """
        assert PyDualSenseController._read_battery_opt(self._DS(0)) is None

    def test_um_valor_de_verdade_passa(self) -> None:
        assert PyDualSenseController._read_battery_opt(self._DS(75)) == 75
        #: O mínimo que um DualSense reporta é 5 (`nibble 0 -> 0*10+5`).
        assert PyDualSenseController._read_battery_opt(self._DS(5)) == 5

    def test_sem_objeto_de_bateria_continua_none(self) -> None:
        assert PyDualSenseController._read_battery_opt(object()) is None

    def test_a_docstring_parou_de_prometer_o_que_nao_fazia(self) -> None:
        """Ela dizia *"Preserva a distinção 'sem dado ainda' (None) de '0%'"*.

        Não preservava. Promessa em docstring que o código não cumpre é pior que
        silêncio: manda a próxima pessoa confiar.
        """
        import inspect

        doc = inspect.getdoc(PyDualSenseController._read_battery_opt) or ""
        assert "16/09/2026" in doc, "a correção não ficou datada"
        assert "DSBattery" in doc
