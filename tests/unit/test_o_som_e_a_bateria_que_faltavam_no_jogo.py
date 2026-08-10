"""As duas curas de 09/08/2026, à noite: o som na linha e a bateria no jogo.

Duas decisões dela, no mesmo dia e pela mesma razão de sempre — *"falo isso
ingame"*:

1. **o som do jogo aparece na linha de recursos do card.** O carimbo
   ``audio_do_jogo`` existia no vpad desde 02/08 (PARIDADE-SONY-01/E1), já
   tinha respondido **sim** ao vivo com o jogo aberto, e nada na janela o lia.
   Ela decidiu: *"sim, na linha de recursos do card"*, e **sem** o número do
   volume — a linha diz que o som está chegando, não em que volume;
2. **a bateria do controle chega ao jogo.** O ``forward_battery`` nasceu em
   15/07 (``69951a7``) e passou 25 dias com **zero chamadores em `src/`**. A
   consequência estava escrita na docstring dele desde o primeiro dia: *"o vpad
   anuncia 5% descarregando para sempre e o jogo mostra alerta de bateria fraca
   num controle cheio"*.

O segundo é irmão exato do ``forward_jack`` (curado horas antes, na
``ORFAOS-QUE-VOLTAM-01``) e tinha os **mesmos dois defeitos** — mas o segundo
numa forma mais sorrateira, e é ela que este arquivo tranca com mais cuidado:
o ``forward_battery`` **chamava** ``_emit_if_changed()``, só que sem
``from_reader``. Com ``_motion_streaming`` ligado — que é o estado normal,
porque é o reader quem liga — o gate devolve ``False`` na primeira linha e nada
sai. Fiar o chamador sem essa palavra-chave produziria uma cura que passa em
revisão e não entrega **nada**.

Nada aqui toca hardware: o hidraw do físico é um ``os.pipe()``, o ``/dev/uhid``
é o mesmo fake dos testes irmãos e o daemon é dublado.

Universalidade: o caminho vale por **USB e Bluetooth** (o ``_struct_base`` do
reader já cuida dos dois transportes, com o CRC do rádio) e para **N controles**
(um reader por jogador). As duas curas são de **DualSense**: só ele tem
alto-falante, e só ele passa pelo ``UhidDualSense`` — Pro Controller e 8BitDo
não têm o report 0x01 nem os bytes 52/53, e o ``UinputGamepad`` degrada calado
pelo contrato duck-typed.
"""
from __future__ import annotations

import os
import struct
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    SITUACAO_CHEGANDO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
    estado_do_recurso,
    resumo_do_que_chega_ao_jogo,
)
from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.core.physical_report_reader import (
    BATTERY_STATUS_OFFSET,
    INPUT_REPORT_BT_SIZE,
    PhysicalReportReader,
    decodificar_bateria,
    extract_battery_status,
)
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_INPUT2,
    UhidDualSense,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: Os nibbles altos do byte 52, do `dualsense_parse_report` (kernel 6.18).
_CARGA_DESCARREGANDO = 0x0
_CARGA_CARREGANDO = 0x1
_CARGA_CHEIO = 0x2
_CARGA_TEMPERATURA = 0xA
_CARGA_ERRO = 0xF


# ---------------------------------------------------------------------------
# Reports crus do físico e /dev/uhid falso (o mesmo desenho do
# `test_orfaos_que_voltam_a_interface`, que é o irmão desta fiação)
# ---------------------------------------------------------------------------


def _usb_report(*, bateria: int = 0, marca: int = 0) -> bytes:
    """Report 0x01 (64 B) do físico com o byte 52 pedido.

    `marca` entra no gyro para que reports consecutivos sejam DIFERENTES — sem
    isso o dedup por valor do throttle engoliria o segundo e o teste mediria o
    throttle, não a fiação.
    """
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:7] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
    raw[1 + 15] = marca & 0xFF
    raw[1 + 32] = 0x80  # sem dedo no ponto 1
    raw[1 + 36] = 0x80  # sem dedo no ponto 2
    raw[1 + BATTERY_STATUS_OFFSET] = bateria & 0xFF
    return bytes(raw)


def _bt_report(*, bateria: int = 0, corrupt: bool = False) -> bytes:
    """Report 0x31 (78 B) com CRC de INPUT (seed 0xA1) válido — ou corrompido."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = 0x31
    raw[1] = 0x01
    raw[2 + BATTERY_STATUS_OFFSET] = bateria & 0xFF
    crc = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED)
    raw[-4:] = crc.to_bytes(4, "little")
    if corrupt:
        raw[2 + BATTERY_STATUS_OFFSET] ^= 0xFF  # muda DEPOIS do CRC
    return bytes(raw)


_FEATURE_09 = bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13)


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(range(40)),
            0x09: _FEATURE_09,
            0x20: bytes([0x20]) + bytes(63),
        },
    }


class _FakeUhid:
    """Coleta o que o vpad escreve no /dev/uhid — os bytes que o jogo lê."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def bodies(self) -> list[bytes]:
        saida: list[bytes] = []
        for raw in list(self.writes):
            if len(raw) < 6:
                continue
            etype, size = struct.unpack("<IH", raw[:6])
            if etype != UHID_INPUT2:
                continue
            report = raw[6 : 6 + size]
            if report and report[0] == 0x01:
                saida.append(report[1:])
        return saida

    def bateria(self) -> int | None:
        """O byte 52 do ÚLTIMO payload escrito, ou None se nada saiu."""
        bodies = self.bodies()
        return bodies[-1][uhid_gamepad._STATUS_OFFSET] if bodies else None


#: fd sentinela do /dev/uhid falso. O fake é POR FD porque `uhid_gamepad.os` e
#: `physical_report_reader.os` são O MESMO objeto módulo — um `os.read` cego
#: cegaria também o reader, que lê o hidraw do físico por `os.read`.
_FD_UHID = 4243


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeUhid:
    fake = _FakeUhid()
    real_open, real_write = os.open, os.write
    real_read, real_close = os.read, os.close
    real_set_blocking = os.set_blocking

    def _open(path: Any, *a: Any, **k: Any) -> int:
        if str(path) == uhid_gamepad.UHID_NODE:
            return _FD_UHID
        return real_open(path, *a, **k)

    def _write(fd: int, data: bytes) -> int:
        if fd == _FD_UHID:
            fake.writes.append(bytes(data))
            return len(data)
        return real_write(fd, data)

    def _read(fd: int, size: int) -> bytes:
        if fd == _FD_UHID:
            raise BlockingIOError
        return real_read(fd, size)

    def _close(fd: int) -> None:
        if fd == _FD_UHID:
            return
        real_close(fd)

    def _set_blocking(fd: int, blocking: bool) -> None:
        if fd == _FD_UHID:
            return
        real_set_blocking(fd, blocking)

    monkeypatch.setattr(uhid_gamepad.os, "open", _open)
    monkeypatch.setattr(uhid_gamepad.os, "close", _close)
    monkeypatch.setattr(uhid_gamepad.os, "set_blocking", _set_blocking)
    monkeypatch.setattr(uhid_gamepad.os, "write", _write)
    monkeypatch.setattr(uhid_gamepad.os, "read", _read)
    return fake


def _esperar(cond: Any, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


# ===========================================================================
# CURA 1 — o som do jogo entra na linha de recursos do card
# ===========================================================================


def _entry() -> dict[str, Any]:
    return {"player": 1, "is_primary": True}


def _estado(**vpad: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"player": 1, "visto_ha_s": {}}
    item.update(vpad)
    return {"rumble_ff": {"per_vpad": [item]}}


class TestOSomDoJogoNaLinhaDeRecursos:
    def test_som_chegando_agora(self) -> None:
        """MORDIDA: apagar a entrada `alto_falante` de `_CATEGORIA_DO_RECURSO`.

        Sem ela o `estado_do_recurso` devolve `None` (recurso desconhecido não
        inventa frase) e o recurso SOME da linha — que é o estado em que a
        auditoria de hoje encontrou o carimbo: medido, publicado no soquete, e
        invisível na janela.
        """
        estado = estado_do_recurso(
            "alto_falante", _entry(), _estado(visto_ha_s={"audio_do_jogo": 0.4})
        )
        assert estado is not None
        assert estado.situacao == SITUACAO_CHEGANDO
        assert estado.frase == "som do controle"

    def test_som_que_parou(self) -> None:
        """O carimbo velho — o caso medido ao vivo hoje (`audio_do_jogo: 5032.8`)."""
        estado = estado_do_recurso(
            "alto_falante", _entry(), _estado(visto_ha_s={"audio_do_jogo": 5032.8})
        )
        assert estado is not None
        assert estado.situacao == SITUACAO_PARADO

    def test_jogo_que_nunca_pediu_som(self) -> None:
        """"Sem pedido ainda" aqui significa mesmo *nenhum jogo pediu*.

        E não "o kernel ainda não passou por aqui": o carimbo exige sessão de
        jogo aberta (`_replicating()`), que foi a correção de 02/08 — o probe
        do `hid-playstation` escreve áudio no nascimento do vpad e carimbava
        "sim" sem jogo nenhum.
        """
        estado = estado_do_recurso("alto_falante", _entry(), _estado())
        assert estado is not None
        assert estado.situacao == SITUACAO_NUNCA

    def test_a_frase_nao_carrega_o_volume(self) -> None:
        """Decisão dela: a linha diz que o som chega, não em que volume.

        A amostra (`audio_do_jogo_amostra`, `alto_falante: 100`) continua sendo
        dado de diagnóstico — ela não vira texto de tela.
        """
        estado = estado_do_recurso(
            "alto_falante",
            _entry(),
            _estado(
                visto_ha_s={"audio_do_jogo": 0.1},
                audio_do_jogo_amostra={"alto_falante": 100, "rota": 48},
            ),
        )
        assert estado is not None
        assert not any(d.isdigit() for d in estado.frase)

    def test_a_linha_inteira_mostra_o_som(self) -> None:
        """A entrega que ela vê: o som na MESMA lista, com o mesmo desenho."""
        frase = resumo_do_que_chega_ao_jogo(
            _entry(),
            _estado(
                visto_ha_s={"audio_do_jogo": 0.4, "rumble": 0.2},
                motion_streaming=False,
                motion_forwards=0,
            ),
        )
        assert frase is not None
        assert "No jogo agora: vibração, som do controle" in frase

    def test_a_categoria_e_a_mesma_dos_dois_lados(self) -> None:
        """O reader e o vpad falam do MESMO carimbo, e é o teste que os prende.

        Divergir aqui não quebra nada visível: a linha diria "sem pedido ainda"
        para sempre, com o carimbo saindo do daemon a cada partida. É o mesmo
        travamento que o offset do jack e a janela de motion já têm.
        """
        from hefesto_dualsense4unix.app.widgets import controller_card

        assert (
            controller_card._CATEGORIA_DO_RECURSO["alto_falante"]
            == uhid_gamepad.ATIVIDADE_AUDIO_DO_JOGO
        )


# ===========================================================================
# CURA 2 — a bateria do controle chega ao jogo
# ---------------------------------------------------------------------------
# 1. O parser do byte 52 (mesma disciplina de transporte do clique e do jack)
# ===========================================================================


class TestExtrairABateriaDoReportCru:
    def test_usb(self) -> None:
        assert extract_battery_status(_usb_report(bateria=0x05)) == 0x05

    def test_bt_com_crc_valido(self) -> None:
        assert extract_battery_status(_bt_report(bateria=0x1A)) == 0x1A

    def test_bt_com_crc_corrompido_nao_diz_nada(self) -> None:
        """``None`` e não ``0``: rádio corrompido não descarrega o controle.

        ``0x00`` é um controle real descarregando com 5% — o valor que dispara
        o alerta de bateria fraca no jogo. Transformar "não sei" em "quase
        acabando" faria um pacote ruim de rádio interromper a partida dela.
        """
        assert extract_battery_status(_bt_report(bateria=0x1A, corrupt=True)) is None

    def test_report_de_outro_id_nao_diz_nada(self) -> None:
        assert extract_battery_status(bytes([0x05]) + bytes(63)) is None

    def test_report_curto_demais_nao_diz_nada(self) -> None:
        assert extract_battery_status(bytes([0x01, 0x00])) is None

    def test_report_vazio_nao_diz_nada(self) -> None:
        assert extract_battery_status(b"") is None


def test_o_offset_da_bateria_e_o_mesmo_nos_dois_lados() -> None:
    """O reader e o vpad falam do MESMO byte, e é o teste que os prende."""
    assert BATTERY_STATUS_OFFSET == uhid_gamepad._STATUS_OFFSET


# ---------------------------------------------------------------------------
# 2. A escala — o ponto em que "não converta no chute" foi cobrado
# ---------------------------------------------------------------------------


class TestAEscalaDaBateria:
    """A conta é a do kernel 6.18 (`dualsense_parse_report`), grau ALTA.

    Não é uma porcentagem: são **11 níveis** num nibble (5, 15, ..., 95, 100).
    """

    @pytest.mark.parametrize("nivel", list(range(11)))
    @pytest.mark.parametrize(
        "carga", [_CARGA_DESCARREGANDO, _CARGA_CARREGANDO]
    )
    def test_a_ida_e_a_volta_sao_o_mesmo_byte(
        self, fake_uhid: _FakeUhid, nivel: int, carga: int
    ) -> None:
        """MORDIDA: trocar a conta por `percent = nibble` (o chute óbvio).

        Os 22 casos passam a errar: um controle em 95% (nível 9) chegaria ao
        jogo como 15%, e o alerta de bateria fraca que esta cura existe para
        apagar acenderia com o controle quase cheio.

        Percorre os ONZE níveis nos dois estados de carga que o report do vpad
        sabe escrever: se a ida e a volta não fossem o inverso exato uma da
        outra, algum destes 22 bytes voltaria diferente.
        """
        status0 = (carga << 4) | nivel
        pct, carregando = decodificar_bateria(status0)

        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_battery(pct, charging=carregando, from_reader=True)

        assert fake_uhid.bateria() == status0

    def test_cheio_na_base_nao_vira_descarregando(self) -> None:
        """0x2 é "cheio" — o report do vpad só sabe dizer dois estados.

        `(100, carregando)` é o mais próximo que o campo consegue, e é honesto
        no que importa: o controle está na base, cheio, e nenhum alerta deve
        aparecer. "100% descarregando" inventaria um consumo que não existe.
        """
        assert decodificar_bateria((_CARGA_CHEIO << 4) | 0x0A) == (100, True)

    @pytest.mark.parametrize("carga", [_CARGA_TEMPERATURA, 0xB, _CARGA_ERRO, 0x7])
    def test_erro_de_carga_vira_nao_sei_e_nao_zero(self, carga: int) -> None:
        """MORDIDA: devolver a capacidade 0 do kernel nesses casos.

        O kernel devolve **0** para tensão/temperatura fora de faixa e erro de
        carga. Repassar zero acenderia alerta de bateria crítica por causa de
        um controle quente. "Não sei" é a resposta que a casa já escolheu para
        este byte (`_STATUS_DESCONHECIDO`), e ela não dispara alerta nenhum.
        """
        assert decodificar_bateria((carga << 4) | 0x03) == (None, False)

    def test_nao_sei_vira_o_byte_que_nao_alerta(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_battery(50, charging=False, from_reader=True)

        pad.forward_battery(None, from_reader=True)

        assert fake_uhid.bateria() == uhid_gamepad._STATUS_DESCONHECIDO
        assert pad.bateria_anunciada == (None, False)


# ---------------------------------------------------------------------------
# 3. O vpad: o `forward_battery` passa a EMITIR de verdade
# ---------------------------------------------------------------------------


class TestOEncoderDaBateria:
    def test_emite_com_o_reader_como_relogio(self, fake_uhid: _FakeUhid) -> None:
        """MORDIDA: trocar `from_reader=from_reader` por `from_reader=False`.

        Este é o segundo defeito de 15/07, e o sorrateiro: o método CHAMAVA
        `_emit_if_changed()`, só que sem a palavra-chave. Com
        `_motion_streaming` ligado — o estado NORMAL, porque é o reader quem o
        liga — o gate devolve `False` na primeira linha e nada sai. Fiar o
        chamador sem isto seria uma cura que passa em revisão e não entrega
        nada.
        """
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        antes = len(fake_uhid.bodies())

        pad.forward_battery(55, charging=False, from_reader=True)

        assert len(fake_uhid.bodies()) > antes, (
            "a bateria mudou e NENHUM report saiu — o gate do motion_streaming "
            "engoliu a emissão, que é o defeito de 15/07"
        )
        assert fake_uhid.bateria() == 0x05
        assert pad.battery_forward_count == 1

    def test_o_poll_loop_continua_sendo_so_cache(self, fake_uhid: _FakeUhid) -> None:
        """O contrato do `set_motion_streaming` fica de pé.

        `from_reader` é PARÂMETRO e não `True` fixo justamente por isto: quem
        vem do poll loop continua governado pelo gate, e o report do reader
        carrega o cache junto no tick seguinte. Sem o parâmetro, este arranjo
        viraria uma emissão a mais por tick de poll.
        """
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        antes = len(fake_uhid.bodies())

        pad.forward_battery(55)

        assert len(fake_uhid.bodies()) == antes
        assert pad.battery_forward_count == 0

    def test_valor_repetido_nao_reemite(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_battery(55, from_reader=True)
        antes = len(fake_uhid.bodies())

        pad.forward_battery(55, from_reader=True)

        assert len(fake_uhid.bodies()) == antes
        assert pad.battery_forward_count == 1

    def test_perder_o_fisico_volta_para_nao_sei(self, fake_uhid: _FakeUhid) -> None:
        """MORDIDA: apagar `self._status_byte = _STATUS_DESCONHECIDO` do
        `set_motion_streaming`.

        Um controle que caiu com 8% ficaria 8% no report do vpad para sempre —
        o jogo passaria a partida inteira piscando alerta de bateria fraca por
        um controle que já foi embora.
        """
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.set_motion_streaming(True)
        pad.forward_battery(5, charging=False, from_reader=True)
        assert pad.bateria_anunciada == (5, False)

        pad.set_motion_streaming(False)

        assert pad.bateria_anunciada == (None, False)
        assert fake_uhid.bateria() == uhid_gamepad._STATUS_DESCONHECIDO

    def test_a_sessao_nova_nao_herda_a_bateria(self, fake_uhid: _FakeUhid) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        pad.forward_battery(55, from_reader=True)
        pad.stop()
        assert pad.bateria_anunciada == (None, False)
        assert pad.battery_forward_count == 0


# ---------------------------------------------------------------------------
# 4. O chamador que faltava por 25 dias — a bateria atravessa até o jogo
# ---------------------------------------------------------------------------


class TestABateriaChegaAoJogo:
    def _rodar_fluxo(self, fake: _FakeUhid, reports: list[bytes]) -> list[bytes]:
        """O hidraw do físico é um pipe; o /dev/uhid é o fake da fixture."""
        lido, escrita = os.pipe()
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake",
            vpad=pad,
            max_hz=0,
            opener=lambda _path: os.dup(lido),
        )
        try:
            assert reader.start() is True
            assert _esperar(lambda: pad.motion_streaming)
            for report in reports:
                os.write(escrita, report)
                # Um report por vez: o pipe é um stream e o reader lê 128 B de
                # cada vez — escrever tudo junto colaria dois reports num read.
                time.sleep(0.01)
            assert _esperar(lambda: reader.reports_seen >= len(reports))
            assert _esperar(lambda: reader.battery_forwards >= 1, timeout_s=1.0)
        finally:
            reader.stop()
            pad.stop()
            os.close(escrita)
            os.close(lido)
        return fake.bodies()

    def test_a_carga_do_fisico_atravessa_ate_o_report_do_jogo(
        self, fake_uhid: _FakeUhid
    ) -> None:
        """O teste que MORDE o chamador, ponta a ponta.

        Arrancar o `self._observe_battery(data)` do `_read_until_lost` — o
        chamador que faltou por 25 dias — derruba a conta a zero.

        O que se conta é o que o JOGO lê: um payload escrito no /dev/uhid com o
        byte 52 dizendo 95% descarregando, e não o `_STATUS_DESCONHECIDO` de
        nascença.
        """
        cheio = (_CARGA_DESCARREGANDO << 4) | 0x09  # nível 9 = 95%
        fluxo = [_usb_report(bateria=cheio, marca=1), _usb_report(bateria=cheio, marca=2)]

        bodies = self._rodar_fluxo(fake_uhid, fluxo)

        com_carga = [b for b in bodies if b[uhid_gamepad._STATUS_OFFSET] == cheio]
        assert com_carga, (
            "nenhum report saiu com a bateria do físico — o jogo continua lendo "
            "o valor de nascença (forward_battery órfão desde 15/07)"
        )

    def test_a_bateria_caindo_atravessa(self, fake_uhid: _FakeUhid) -> None:
        """A carga desce e o jogo vê descer, na ordem.

        O último report do fluxo é o do FAIL-SAFE (`_STATUS_DESCONHECIDO`, que
        o `reader.stop()` do teardown provoca) — por isso a asserção é sobre a
        SEQUÊNCIA de valores distintos, e não sobre o último byte.
        """
        fluxo = [
            _usb_report(bateria=0x09, marca=1),  # 95%
            _usb_report(bateria=0x02, marca=2),  # 25%
        ]
        bodies = self._rodar_fluxo(fake_uhid, fluxo)
        assert bodies, "o vpad não emitiu nada"

        vistos: list[int] = []
        for body in bodies:
            valor = body[uhid_gamepad._STATUS_OFFSET]
            if not vistos or vistos[-1] != valor:
                vistos.append(valor)

        assert vistos == [
            0x09,
            0x02,
            uhid_gamepad._STATUS_DESCONHECIDO,  # fail-safe do reader parando
        ]

    def test_a_carga_viaja_mesmo_com_o_controle_parado(
        self, fake_uhid: _FakeUhid
    ) -> None:
        """MORDIDA: tirar o `from_reader` do `_emit_if_changed` do vpad.

        Este é o caso que separa "chega" de "chega por acaso", e é ele que o
        segundo defeito de 15/07 quebrava. Com o controle PARADO, os dois
        reports trazem a MESMA janela de motion — o dedup por valor do
        `_maybe_emit` engole a segunda, e nenhum report de outra coisa sai. Se
        o `forward_battery` só mexesse no cache, a carga nova ficaria esperando
        um report que pode nunca vir (é o que acontece com o rádio BT em
        repouso, onde o firmware emudece).

        A conta é: reports que o JOGO leu com a carga NOVA.
        """
        fluxo = [
            _usb_report(bateria=0x09, marca=7),
            _usb_report(bateria=0x02, marca=7),  # mesma janela: dedup engole
        ]

        bodies = self._rodar_fluxo(fake_uhid, fluxo)

        assert [b for b in bodies if b[uhid_gamepad._STATUS_OFFSET] == 0x02], (
            "a carga nova não saiu com o controle parado — o gate do "
            "motion_streaming engoliu a emissão e a bateria ficou esperando "
            "uma janela de motion que não veio"
        )


class TestOReaderNaoInventaBateria:
    """As três defesas do `_observe_battery`, sem thread nenhuma."""

    def _reader(self, vpad: Any) -> PhysicalReportReader:
        return PhysicalReportReader(path_provider=lambda: None, vpad=vpad, max_hz=0)

    def test_report_ruim_nao_mexe_no_estado(self) -> None:
        recebidos: list[tuple[int | None, bool]] = []
        vpad = SimpleNamespace(
            forward_battery=lambda pct, *, charging=False, from_reader=False: (
                recebidos.append((pct, charging))
            )
        )
        reader = self._reader(vpad)
        reader._observe_battery(_usb_report(bateria=0x09))
        reader._observe_battery(_bt_report(bateria=0x00, corrupt=True))
        assert recebidos == [(95, False)], (
            "um report com CRC ruim descarregou o controle — 'não sei' virou "
            "'quase acabando'"
        )

    def test_vpad_sem_o_metodo_degrada_calado(self) -> None:
        """Contrato duck-typed: o `UinputGamepad` NÃO tem `forward_battery`.

        Não é hipótese de teste — é o backend que roda com máscara Xbox 360, e
        ele não carrega bateria no mesmo canal.
        """
        reader = self._reader(SimpleNamespace())
        reader._observe_battery(_usb_report(bateria=0x09))
        assert reader.battery_forwards == 0

    def test_reabrir_reentrega_a_carga(self) -> None:
        """MORDIDA: apagar o `_reset_battery()` do fail-safe do `_run`.

        O vpad volta para "não sei" ao perder o fd. Sem o reset local, o reader
        compararia o novo report com o cache antigo, veria "igual" e nunca
        reentregaria — o jogo passaria a partida inteira achando que o controle
        está cheio e carregando.
        """
        recebidos: list[int | None] = []
        vpad = SimpleNamespace(
            forward_battery=lambda pct, *, charging=False, from_reader=False: (
                recebidos.append(pct)
            )
        )
        reader = self._reader(vpad)
        reader._observe_battery(_usb_report(bateria=0x09))
        reader._reset_battery()
        reader._observe_battery(_usb_report(bateria=0x09))
        assert recebidos == [95, 95]


# ---------------------------------------------------------------------------
# 5. O `state_full` carrega a bateria que o vpad ANUNCIA
# ---------------------------------------------------------------------------


def _vpad_completo(**extra: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "backend": "uhid",
        "flavor": "dualsense",
        "ff_supported": True,
        "ff_play_count": 0,
        "output_count": 0,
        "trigger_replicas": 0,
        "lightbar_replicas": 0,
        "player_led_replicas": 0,
        "ff_last_sent": (0, 0),
        "motion_streaming": True,
        "motion_forward_count": 0,
        "touchpad_click": False,
        "touchpad_click_count": 0,
        "jack_forward_count": 0,
        "jack": {"fone": False, "microfone": False, "mudo": False},
        "rumble_no_fisico": None,
        "rumble_no_fisico_ha_s": None,
        "bateria_anunciada": (None, False),
        "battery_forward_count": 0,
    }
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def servidor(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        rumble_active=None,
    )
    daemon_mock._gamepad_device = _vpad_completo()
    daemon_mock._motion_reader = SimpleNamespace(emit_hz=0.0)
    daemon_mock._coop_manager = None

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield socket_path, daemon_mock
    finally:
        await server.stop()


async def _item_do_p1(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    per_vpad = result["rumble_ff"]["per_vpad"]
    assert isinstance(per_vpad, list) and per_vpad
    return per_vpad[0]


@pytest.mark.asyncio
async def test_state_full_publica_a_bateria_do_vpad(servidor: Any) -> None:
    """MORDIDA: apagar a chave `bateria_no_jogo` do `per_vpad`.

    Diferente do `battery_pct` do controle FÍSICO que a aba Status já mostra:
    esta é a que o JOGO lê. Com o `forward_battery` órfão, o físico podia estar
    em 95% e o jogo lia "cheio e carregando" fixo.
    """
    socket_path, daemon = servidor
    daemon._gamepad_device = _vpad_completo(
        bateria_anunciada=(95, False), battery_forward_count=4
    )

    item = await _item_do_p1(socket_path)

    assert item["bateria_no_jogo"] == {"pct": 95, "carregando": False}
    assert item["battery_forwards"] == 4


@pytest.mark.asyncio
async def test_state_full_nao_inventa_bateria_quando_o_vpad_e_mock(
    servidor: Any,
) -> None:
    """A blindagem de sempre deste payload: MagicMock não vira dado.

    Um vpad uinput não tem nenhuma destas propriedades, e um dublê devolve algo
    truthy e comparável com qualquer coisa — sem a tipagem estrita, a janela
    publicaria uma bateria que ninguém mediu.
    """
    socket_path, daemon = servidor
    daemon._gamepad_device = _vpad_completo(
        bateria_anunciada=MagicMock(), battery_forward_count=MagicMock()
    )

    item = await _item_do_p1(socket_path)

    assert item["bateria_no_jogo"] is None
    assert item["battery_forwards"] == 0
