"""Contrato do vpad uhid (SPRINT-UHID-VPAD-01) — sem tocar /dev/uhid.

O que estes testes travam são as três coisas que custaram um PoC para descobrir e
que quebram em SILÊNCIO se alguém mexer (o probe do `hid_playstation` simplesmente
não registra o controle, e a vibração volta a só funcionar na máscara Xbox):

1. **MAC próprio por jogador.** Copiar o feature 0x09 do controle físico faz o
   probe morrer com ``Duplicate device found for MAC address … / probe failed -17``.
   Os bytes 1..6 do report 0x09 são o MAC em **little-endian**.
2. **Responder UHID_GET_REPORT** com o feature capturado (senão não registra).
3. **Responder UHID_SET_REPORT** (senão o probe trava).

Mais o passthrough de rumble: o report de output 0x02 que o JOGO escreve no hidraw
do vpad tem os motores em ``body[2]`` (fraco) e ``body[3]`` (forte) — é daí que sai
o par (weak, strong) entregue ao `rumble_sink`, que vibra o controle físico.

O device é substituído por um fd falso (`os.write`/`os.read` monkeypatchados), então
o teste roda em CI sem /dev/uhid e sem hardware.
"""
from __future__ import annotations

import struct
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_GET_REPORT,
    UHID_GET_REPORT_REPLY,
    UHID_OUTPUT,
    UHID_SET_REPORT,
    UHID_SET_REPORT_REPLY,
    UHID_START,
    UhidDualSense,
    player_mac,
)

#: Feature 0x09 como o controle físico devolve: id + MAC(LE) + resto.
_FEATURE_09_FISICO = bytes([0x09]) + bytes.fromhex("f011c39cfaa0") + bytes(13)


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(40),
            0x09: _FEATURE_09_FISICO,
            0x20: bytes([0x20]) + bytes(63),
        },
    }


class _FakeFd:
    """Captura os writes e serve reads enfileirados no lugar do /dev/uhid."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.reads: list[bytes] = []


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeFd:
    fake = _FakeFd()

    monkeypatch.setattr(uhid_gamepad.os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(uhid_gamepad.os, "close", lambda _fd: None)
    monkeypatch.setattr(uhid_gamepad.os, "set_blocking", lambda _fd, _b: None)

    def _write(_fd: int, data: bytes) -> int:
        fake.writes.append(data)
        return len(data)

    def _read(_fd: int, _size: int) -> bytes:
        if not fake.reads:
            raise BlockingIOError
        return fake.reads.pop(0)

    monkeypatch.setattr(uhid_gamepad.os, "write", _write)
    monkeypatch.setattr(uhid_gamepad.os, "read", _read)
    return fake


def _output_event(report: bytes) -> bytes:
    """struct uhid_output_req { __u8 data[4096]; __u16 size; __u8 rtype; }"""
    event = struct.pack("<I", UHID_OUTPUT)
    event += report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
    event += struct.pack("<HB", len(report), 1)
    return event


#: valid_flag0 que o HARDWARE REAL manda no rumble. Os DualSense da máquina de
#: teste têm firmware 0x0630 (>= 0x0215), então o hid_playstation usa
#: `use_vibration_v2`: manda COMPATIBLE_VIBRATION2 no valid_flag2 e o valid_flag0
#: chega com HAPTICS_SELECT (0x02) SOZINHO — nunca com 0x01.
#:
#: O default deste helper já foi 0x01 e por isso a suíte ficou VERDE com um
#: `& 0x01` na produção que descartava todo o rumble no hardware alvo. Medido ao
#: vivo (report cru do kernel): rumble -> valid_flag0=0x02 flag2=0x04;
#: lightbar -> valid_flag0=0x00 flag1=0x04 com motores zerados.
_HAPTICS_SELECT = 0x02


def _rumble_report(weak: int, strong: int, *, valid_flag0: int = _HAPTICS_SELECT) -> bytes:
    body = bytearray(47)
    body[0] = valid_flag0
    body[2] = weak
    body[3] = strong
    return bytes([0x02]) + bytes(body)


class TestMacProprio:
    def test_cada_jogador_tem_mac_distinto_e_localmente_administrado(self) -> None:
        macs = [player_mac(n) for n in (1, 2, 3, 4)]
        assert len(set(macs)) == 4
        # Bit 1 do primeiro octeto = faixa localmente administrada (não colide
        # com hardware real, que é o que faz o probe recusar por duplicidade).
        for mac in macs:
            assert int(mac.split(":")[0], 16) & 0x02

    def test_create_reescreve_o_mac_do_fisico(self, fake_uhid: _FakeFd) -> None:
        """Sem isto: 'Duplicate device found for MAC address' → probe falha -17."""
        pad = UhidDualSense(player=2, blueprint=_blueprint())

        assert pad.start() is True

        esperado = bytes(reversed(bytes.fromhex(player_mac(2).replace(":", ""))))
        assert pad._features[0x09][1:7] == esperado
        # E o report do físico não vazou.
        assert pad._features[0x09][1:7] != _FEATURE_09_FISICO[1:7]

    def test_nome_e_mac_identificam_o_jogador(self) -> None:
        pad = UhidDualSense(player=3, blueprint=_blueprint())
        assert pad.name == "Hefesto Virtual DualSense P3"
        assert pad.mac == "02:fe:00:00:00:03"


class TestProbe:
    def test_get_report_responde_com_o_feature_capturado(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Sem a resposta o hid_playstation não registra o DualSense."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        fake_uhid.writes.clear()
        # id=7, rnum=0x20 (firmware)
        fake_uhid.reads.append(struct.pack("<IIBB", UHID_GET_REPORT, 7, 0x20, 3))

        pad.pump_ff()

        (reply,) = fake_uhid.writes
        tipo, request_id, err = struct.unpack("<IIH", reply[:10])
        assert (tipo, request_id, err) == (UHID_GET_REPORT_REPLY, 7, 0)
        size = struct.unpack("<H", reply[10:12])[0]
        assert reply[12:12 + size] == _blueprint()["features"][0x20]

    def test_set_report_e_respondido(self, fake_uhid: _FakeFd) -> None:
        """Sem reply o probe trava."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        fake_uhid.writes.clear()
        fake_uhid.reads.append(struct.pack("<IIBB", UHID_SET_REPORT, 9, 0x02, 2))

        pad.pump_ff()

        (reply,) = fake_uhid.writes
        assert struct.unpack("<IIH", reply[:10]) == (UHID_SET_REPORT_REPLY, 9, 0)

    def test_uhid_start_marca_o_bind(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))

        pad.pump_ff()

        assert pad._started is True

    def test_sem_blueprint_nao_cria(self) -> None:
        assert UhidDualSense(player=1, blueprint=None).start() is False


class TestRumblePassthrough:
    def test_rumble_do_jogo_chega_ao_controle_fisico(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O que era impossível no uinput: vibrar com a máscara DualSense."""
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        for weak, strong in ((200, 100), (0, 255), (0, 0)):
            fake_uhid.reads.append(_output_event(_rumble_report(weak, strong)))

        pad.pump_ff()

        assert recebido == [(200, 100), (0, 255), (0, 0)]
        assert pad.ff_last_sent == (0, 0)
        assert pad.ff_play_count == 3

    def test_valor_repetido_nao_reenvia(self, fake_uhid: _FakeFd) -> None:
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        for _ in range(3):
            fake_uhid.reads.append(_output_event(_rumble_report(120, 120)))

        pad.pump_ff()

        assert recebido == [(120, 120)]

    def test_report_de_outro_tipo_e_ignorado(self, fake_uhid: _FakeFd) -> None:
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        fake_uhid.reads.append(_output_event(bytes([0x31]) + bytes(10)))

        pad.pump_ff()

        assert recebido == []

    @pytest.mark.parametrize(
        ("valid_flag0", "firmware"),
        [
            (0x02, "firmware novo (>=0x0215, use_vibration_v2): HAPTICS_SELECT só"),
            (0x01, "firmware antigo: COMPATIBLE_VIBRATION"),
            (0x03, "SDL/HIDAPI: os dois bits"),
        ],
    )
    def test_rumble_chega_em_qualquer_firmware(
        self, fake_uhid: _FakeFd, valid_flag0: int, firmware: str
    ) -> None:
        """O `& 0x01` matava o rumble nos DualSense de firmware novo — que são os
        desta máquina (0x0630). A checagem tem de ser MÁSCARA."""
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        fake_uhid.reads.append(
            _output_event(_rumble_report(64, 128, valid_flag0=valid_flag0))
        )

        pad.pump_ff()

        assert recebido == [(64, 128)], f"rumble descartado — {firmware}"

    def test_report_sem_a_flag_de_vibracao_nao_zera_o_rumble(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O jogo usa o MESMO report 0x02 para lightbar/gatilhos, com motores em 0.

        Sem checar DS_OUTPUT_VALID_FLAG0_COMPATIBLE_VIBRATION, acender um LED no
        meio de uma explosão MATAVA a vibração.
        """
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        fake_uhid.reads.append(_output_event(_rumble_report(220, 180)))
        # Agora um report SÓ de lightbar: motores zerados, sem a flag de vibração.
        fake_uhid.reads.append(_output_event(_rumble_report(0, 0, valid_flag0=0x04)))

        pad.pump_ff()

        assert recebido == [(220, 180)]
        assert pad.ff_last_sent == (220, 180)

    def test_contador_de_rumble_nao_conta_report_de_led(
        self, fake_uhid: _FakeFd
    ) -> None:
        """ff_play_count responde "o jogo pediu vibração?" — LED não é vibração."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        fake_uhid.reads.append(_output_event(_rumble_report(0, 0, valid_flag0=0x04)))
        fake_uhid.reads.append(_output_event(_rumble_report(10, 20)))

        pad.pump_ff()

        assert pad.ff_play_count == 1
        assert pad.output_count == 2

    def test_sink_que_explode_nao_derruba_o_pump(self, fake_uhid: _FakeFd) -> None:
        def _boom(_w: int, _s: int) -> None:
            raise RuntimeError("controle sumiu no meio")

        pad = UhidDualSense(player=1, blueprint=_blueprint(), rumble_sink=_boom)
        pad.start()
        fake_uhid.reads.append(_output_event(_rumble_report(10, 20)))

        pad.pump_ff()  # não propaga

        assert pad.ff_last_sent == (10, 20)


class TestCicloDeVida:
    def test_stop_zera_o_rumble_antes_de_sumir(self, fake_uhid: _FakeFd) -> None:
        """O vpad some; ninguém mais mandaria o stop e o controle ficaria vibrando."""
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        fake_uhid.reads.append(_output_event(_rumble_report(180, 90)))
        pad.pump_ff()

        pad.stop()

        assert recebido[-1] == (0, 0)
        assert pad.is_active() is False

    def test_stop_sem_rumble_pendente_nao_chama_o_sink(
        self, fake_uhid: _FakeFd
    ) -> None:
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()

        pad.stop()

        assert recebido == []

    def test_start_duas_vezes_e_idempotente(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        assert pad.start() is True
        writes = len(fake_uhid.writes)

        assert pad.start() is True
        assert len(fake_uhid.writes) == writes

    def test_pump_sem_device_e_no_op(self) -> None:
        UhidDualSense(player=1, blueprint=_blueprint()).pump_ff()

    def test_stop_sem_start_e_no_op(self) -> None:
        UhidDualSense(player=1, blueprint=_blueprint()).stop()

    def test_uhid_stop_do_kernel_zera_o_rumble(self, fake_uhid: _FakeFd) -> None:
        """rmmod/unbind: ninguém mais mandaria o stop e o controle ficaria vibrando."""
        recebido: list[tuple[int, int]] = []
        pad = UhidDualSense(player=1, blueprint=_blueprint(),
                            rumble_sink=lambda w, s: recebido.append((w, s)))
        pad.start()
        fake_uhid.reads.append(_output_event(_rumble_report(255, 255)))
        pad.pump_ff()
        fake_uhid.reads.append(struct.pack("<I", uhid_gamepad.UHID_STOP) + bytes(8))

        pad.pump_ff()

        assert recebido[-1] == (0, 0)

    def test_stop_concorrente_no_meio_do_pump_nao_explode(
        self, fake_uhid: _FakeFd, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O poll loop bombeia enquanto a GUI troca de modo (stop em outra thread).

        Antes o pump relia self._fd a cada volta: com o fd já None, o os.read(None)
        levantava TypeError — que, ao contrário do OSError, ninguém pegava.
        """
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        chamadas = {"n": 0}
        real_read = uhid_gamepad.os.read

        def _read_que_para_o_pad(fd: int, size: int) -> bytes:
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                pad.stop()  # outra thread desliga o modo bem aqui
                return _output_event(_rumble_report(1, 2))
            return real_read(fd, size)

        monkeypatch.setattr(uhid_gamepad.os, "read", _read_que_para_o_pad)

        pad.pump_ff()  # não pode levantar

        assert pad.is_active() is False

    def test_blueprint_com_feature_09_curto_nao_abre_o_device(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Slice assign em bytearray curto REDIMENSIONA o report em vez de escrever.

        E o fd de /dev/uhid não pode vazar quando a validação reprova.
        """
        bp = _blueprint()
        bp["features"][0x09] = bytes([0x09, 0x11])  # 2 bytes: não cabe o MAC

        assert UhidDualSense(player=1, blueprint=bp).start() is False
        assert fake_uhid.writes == []  # nem chegou a abrir/escrever

    def test_blueprint_sem_feature_09_nao_vaza_fd(self, fake_uhid: _FakeFd) -> None:
        bp = _blueprint()
        del bp["features"][0x09]

        assert UhidDualSense(player=1, blueprint=bp).start() is False
        assert fake_uhid.writes == []


class TestBateria:
    """Sem o byte de status o vpad anuncia 5% descarregando PARA SEMPRE.

    O `dualsense_parse_report` lê ``battery_data = status & 0x0F`` e
    ``capacity = min(battery_data * 10 + 5, 100)``: payload zerado = 5%, e o jogo
    mostra alerta de bateria fraca num controle carregado. Medido: o controle
    físico manda 0x29 (95%); o vpad mandava 0x00.
    """

    def test_sem_dado_nasce_cheio_e_carregando(self, fake_uhid: _FakeFd) -> None:
        """A mentira menos daninha: não dispara alerta de bateria fraca."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**_NEUTRO)

        payload = _ultimo_payload(fake_uhid)
        assert payload[uhid_gamepad._STATUS_OFFSET] == uhid_gamepad._STATUS_DESCONHECIDO
        assert payload[uhid_gamepad._STATUS_OFFSET] != 0x00, "0x00 = 5% descarregando"

    @pytest.mark.parametrize(
        ("percent", "esperado_kernel"),
        [
            (100, 100),  # cheio tem de aparecer como cheio (truncar dava 95)
            (95, 95),
            (30, 35),  # ±5%: o formato só tem 11 níveis
            (5, 5),
            (0, 5),  # o mínimo representável
        ],
    )
    def test_percentual_vira_o_nivel_representavel_mais_proximo(
        self, fake_uhid: _FakeFd, percent: int, esperado_kernel: int
    ) -> None:
        """Confere pela CONTA DO KERNEL, não pelo byte cru — é ela que a pessoa vê.

        Validado no hardware: forward_battery(100) -> o power_supply do vpad
        mostrou 100%; forward_battery(30) -> 35%.
        """
        pad = _pad_ligado(fake_uhid)

        pad.forward_battery(percent)

        status = _ultimo_payload(fake_uhid)[uhid_gamepad._STATUS_OFFSET]
        battery_data = status & 0x0F
        assert min(battery_data * 10 + 5, 100) == esperado_kernel

    def test_carregando_muda_o_nibble_alto(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)

        pad.forward_battery(50, charging=True)

        status = _ultimo_payload(fake_uhid)[uhid_gamepad._STATUS_OFFSET]
        assert (status & 0xF0) >> 4 == 0x1

    def test_valor_repetido_nao_reemite(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)
        pad.forward_battery(80)
        fake_uhid.writes.clear()

        pad.forward_battery(80)

        assert fake_uhid.writes == []


class TestSendReport:
    def test_manda_o_report_cru_sem_padding_de_4kb(self, fake_uhid: _FakeFd) -> None:
        """4 KB por evento x 250 Hz x 4 controles = ~4 MB/s de cópia à toa.

        O uhid_char_write copia min(count, sizeof(event)) e zera o resto —
        verificado no kernel real: o report cru é aceito.
        """
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()
        fake_uhid.writes.clear()
        report = bytes([0x01]) + bytes(63)

        assert pad.send_report(report) is True

        (event,) = fake_uhid.writes
        tipo, size = struct.unpack("<IH", event[:6])
        assert tipo == uhid_gamepad.UHID_INPUT2
        assert size == len(report)
        assert event[6:] == report
        assert len(event) < 200  # não 4 KB

    def test_sem_device_devolve_false(self) -> None:
        assert UhidDualSense(player=1, blueprint=_blueprint()).send_report(b"\x01") is False

    def test_report_maior_que_o_maximo_e_recusado(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())
        pad.start()

        assert pad.send_report(bytes(HID_MAX_DESCRIPTOR_SIZE + 1)) is False


class TestBlueprint:
    def test_hidraw_que_nao_e_dualsense_e_recusado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Apontar para o hidraw de um teclado dava um "blueprint" que só
        quebrava lá na frente, com erro que não diz nada da causa."""
        monkeypatch.setattr(uhid_gamepad, "_is_dualsense", lambda _node: False)

        assert uhid_gamepad.capture_dualsense_blueprint("/dev/hidraw9") is None

    @pytest.mark.parametrize(
        "path", ["/dev/../etc/passwd", "/dev/hidrawX", "/dev/input/js0", ""]
    )
    def test_path_fora_do_padrao_e_recusado(self, path: str) -> None:
        assert uhid_gamepad.capture_dualsense_blueprint(path) is None


def _payloads(fake: _FakeFd) -> list[bytes]:
    """Payloads dos input reports 0x01 emitidos (sem o cabeçalho UHID_INPUT2)."""
    saidas = []
    for event in fake.writes:
        tipo, size = struct.unpack("<IH", event[:6])
        if tipo == uhid_gamepad.UHID_INPUT2 and event[6] == 0x01:
            saidas.append(event[7:6 + size])
    return saidas


def _ultimo_payload(fake: _FakeFd) -> bytes:
    payloads = _payloads(fake)
    assert payloads, "nenhum input report foi emitido"
    return payloads[-1]


def _pad_ligado(fake: _FakeFd, **kwargs: Any) -> UhidDualSense:
    pad = UhidDualSense(player=1, blueprint=_blueprint(), **kwargs)
    assert pad.start() is True
    fake.writes.clear()
    return pad


#: Neutro do encoder: sticks centrados, gatilhos soltos, nada apertado.
_NEUTRO = {"lx": 0x80, "ly": 0x80, "rx": 0x80, "ry": 0x80, "l2": 0, "r2": 0}
_NEUTRO_BYTES = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])


class TestEncoderAnalogico:
    def test_repouso_espelha_o_report_do_controle_fisico(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Medido no hardware: 01 7f 7f 7d 7c 00 00 <seq> 08 ...

        Sticks perto de 128, gatilhos 0 e d-pad no neutro (8) — não zero, que é o
        canto do stick.
        """
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(lx=127, ly=127, rx=125, ry=124, l2=0, r2=0)

        payload = _ultimo_payload(fake_uhid)
        assert payload[0:6] == bytes([127, 127, 125, 124, 0, 0])
        assert payload[7] & 0x0F == 0x08
        assert payload[8] == 0
        assert payload[9] == 0
        # 63 + o report id = 64 = DS_INPUT_REPORT_USB_SIZE. O driver compara o
        # tamanho e DESCARTA CALADO o que não bate: com 62 (a conta do descriptor
        # arredondando os campos de bits para baixo) o vpad nascia mudo — o kernel
        # aceitava o INPUT2 sem erro e o evdev nunca saía do repouso. Só o teste
        # no hardware pegou; este assert existe para não voltar.
        assert len(payload) == 63
        assert len(payload) + 1 == 64

    @pytest.mark.parametrize(
        ("eixo", "offset"),
        [("lx", 0), ("ly", 1), ("rx", 2), ("ry", 3), ("l2", 4), ("r2", 5)],
    )
    def test_cada_eixo_vai_no_seu_offset(
        self, fake_uhid: _FakeFd, eixo: str, offset: int
    ) -> None:
        """Trocar dois offsets dá um controle que anda de lado — e a suíte passa
        se os testes só olharem "algum byte mudou"."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**{**_NEUTRO, eixo: 200})

        payload = _ultimo_payload(fake_uhid)
        assert payload[offset] == 200
        for outro in range(6):
            if outro != offset:
                assert payload[outro] == _NEUTRO_BYTES[outro]

    def test_gatilhos_no_fundo(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**{**_NEUTRO, "l2": 255, "r2": 255})

        assert _ultimo_payload(fake_uhid)[4:6] == bytes([255, 255])

    def test_touchpad_nasce_sem_toque_fantasma(self, fake_uhid: _FakeFd) -> None:
        """O byte de contato é INVERTIDO no hid_playstation:
        ``active = !(contact & 0x80)``. Payload zerado = dedo preso em (0,0), e o
        jogo veria um toque eterno no canto do touchpad.

        Os offsets são **32 e 36** — medidos num report cru do controle físico com
        o dedo fora do touchpad. O `reserved2` do struct fica no 31 e empurra os
        pontos; a versão anterior carimbava 31/35 e o assert passava verde
        justamente nos bytes errados (os dois toques fantasma continuavam).
        """
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**_NEUTRO)

        payload = _ultimo_payload(fake_uhid)
        assert uhid_gamepad._TOUCH_POINT_OFFSETS == (32, 36)
        for offset in uhid_gamepad._TOUCH_POINT_OFFSETS:
            assert payload[offset] & 0x80, f"ponto de toque em {offset} nasceu ativo"

    def test_valor_fora_da_faixa_nao_estoura_o_byte(self, fake_uhid: _FakeFd) -> None:
        """Um valor sujo derrubaria o vpad inteiro com struct.error/ValueError."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**{**_NEUTRO, "lx": 300, "ly": -1})

        payload = _ultimo_payload(fake_uhid)
        assert payload[0] == 300 & 0xFF
        assert payload[1] == 0xFF


class TestEncoderBotoes:
    @pytest.mark.parametrize(
        ("botão", "offset", "bit"),
        [
            ("square", 7, 0x10), ("cross", 7, 0x20),
            ("circle", 7, 0x40), ("triangle", 7, 0x80),
            ("l1", 8, 0x01), ("r1", 8, 0x02),
            ("l2_btn", 8, 0x04), ("r2_btn", 8, 0x08),
            ("create", 8, 0x10), ("options", 8, 0x20),
            ("l3", 8, 0x40), ("r3", 8, 0x80),
            ("ps", 9, 0x01), ("mic_btn", 9, 0x04),
            ("touchpad_left_press", 9, 0x02),
            ("touchpad_middle_press", 9, 0x02),
            ("touchpad_right_press", 9, 0x02),
        ],
    )
    def test_cada_botao_liga_so_o_seu_bit(
        self, fake_uhid: _FakeFd, botão: str, offset: int, bit: int
    ) -> None:
        """Nomes vindos do EvdevReader.BUTTON_MAP — inventar nome aqui daria um
        botão que nunca acende, sem erro nenhum."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_buttons(frozenset({botão}))

        payload = _ultimo_payload(fake_uhid)
        assert payload[offset] & bit == bit
        # E não acendeu nada além disso (o d-pad segue neutro).
        assert payload[7] & 0xF0 == (bit if offset == 7 else 0)
        assert payload[7] & 0x0F == 0x08
        assert payload[8] == (bit if offset == 8 else 0)
        assert payload[9] == (bit if offset == 9 else 0)

    def test_combinação_de_botoes_soma_os_bits(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)

        pad.forward_buttons(frozenset({"cross", "circle", "l1", "r3", "ps"}))

        payload = _ultimo_payload(fake_uhid)
        assert payload[7] & 0xF0 == 0x20 | 0x40
        assert payload[8] == 0x01 | 0x80
        assert payload[9] == 0x01

    def test_nome_desconhecido_e_ignorado(self, fake_uhid: _FakeFd) -> None:
        """O daemon manda nomes que o DualSense não tem (ex.: teclas do remap)."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_buttons(frozenset({"nao_existe", "cross"}))

        payload = _ultimo_payload(fake_uhid)
        assert payload[7] == 0x20 | 0x08

    def test_soltar_apaga_o_bit(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)
        pad.forward_buttons(frozenset({"cross"}))

        pad.forward_buttons(frozenset())

        payload = _ultimo_payload(fake_uhid)
        assert payload[7] == 0x08
        assert len(_payloads(fake_uhid)) == 2


class TestEncoderDpad:
    @pytest.mark.parametrize(
        ("direcoes", "hat"),
        [
            (("dpad_up",), 0),
            (("dpad_up", "dpad_right"), 1),
            (("dpad_right",), 2),
            (("dpad_down", "dpad_right"), 3),
            (("dpad_down",), 4),
            (("dpad_down", "dpad_left"), 5),
            (("dpad_left",), 6),
            (("dpad_up", "dpad_left"), 7),
            ((), 8),
        ],
    )
    def test_os_oito_sentidos_mais_o_neutro(
        self, fake_uhid: _FakeFd, direcoes: tuple[str, ...], hat: int
    ) -> None:
        """D-pad é HAT (0=N, horário até 7=NW, 8=neutro), não bitmask — tratar
        como bitmask da diagonais aleatórias no jogo."""
        pad = _pad_ligado(fake_uhid)
        pad.forward_buttons(frozenset({"cross"}))  # tira o neutro do delta

        pad.forward_buttons(frozenset(direcoes))

        assert _ultimo_payload(fake_uhid)[7] & 0x0F == hat

    def test_opostos_simultaneos_resolvem_igual_ao_uinput(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O hat não tem como dizer "cima+baixo". Esquerda e cima vencem, que é a
        precedência do UinputGamepad._dpad_vector: a mesma tecla tem de dar o
        mesmo resultado nos dois backends, senão trocar de backend vira bug."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_buttons(frozenset({"dpad_up", "dpad_down", "dpad_left", "dpad_right"}))

        assert _ultimo_payload(fake_uhid)[7] & 0x0F == 7  # NW = (esquerda, cima)

    def test_dpad_convive_com_os_botoes_no_mesmo_byte(self, fake_uhid: _FakeFd) -> None:
        """Nibble baixo = hat, nibble alto = cross/circle/square/triangle."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_buttons(frozenset({"dpad_right", "triangle"}))

        assert _ultimo_payload(fake_uhid)[7] == 0x80 | 0x02


class TestSequencia:
    def test_seq_anda_a_cada_report_emitido(self, fake_uhid: _FakeFd) -> None:
        """O hid_playstation usa o seq para detectar perda de pacote."""
        pad = _pad_ligado(fake_uhid)

        for valor in (10, 20, 30):
            pad.forward_analog(**{**_NEUTRO, "lx": valor})

        assert [p[6] for p in _payloads(fake_uhid)] == [1, 2, 3]

    def test_seq_da_wrap_em_255(self, fake_uhid: _FakeFd) -> None:
        """Byte: 256 estouraria o struct e derrubaria o vpad depois de ~1s."""
        pad = _pad_ligado(fake_uhid)
        pad._seq = 254

        pad.forward_analog(**{**_NEUTRO, "lx": 1})
        pad.forward_analog(**{**_NEUTRO, "lx": 2})
        pad.forward_analog(**{**_NEUTRO, "lx": 3})

        assert [p[6] for p in _payloads(fake_uhid)] == [255, 0, 1]

    def test_report_suprimido_nao_gasta_seq(self, fake_uhid: _FakeFd) -> None:
        """Furar a contagem seria reportar ao driver uma perda que não houve."""
        pad = _pad_ligado(fake_uhid)
        pad.forward_analog(**_NEUTRO)

        for _ in range(5):
            pad.forward_analog(**_NEUTRO)
        pad.forward_analog(**{**_NEUTRO, "lx": 9})

        assert [p[6] for p in _payloads(fake_uhid)] == [1, 2]


class TestDelta:
    def test_estado_parado_nao_reemite(self, fake_uhid: _FakeFd) -> None:
        """O forward roda a cada tick por vpad: sem delta eram ~250 writes/s no
        /dev/uhid por controle com tudo parado."""
        pad = _pad_ligado(fake_uhid)
        pad.forward_analog(**_NEUTRO)
        pad.forward_buttons(frozenset())
        emitidos = len(_payloads(fake_uhid))

        for _ in range(10):
            pad.forward_analog(**_NEUTRO)
            pad.forward_buttons(frozenset())

        assert len(_payloads(fake_uhid)) == emitidos

    def test_analog_e_buttons_no_mesmo_tick_emitem_uma_vez_cada(
        self, fake_uhid: _FakeFd
    ) -> None:
        """forward_buttons logo após forward_analog não pode reemitir o mesmo
        payload: o report 0x01 já carrega os dois."""
        pad = _pad_ligado(fake_uhid)

        pad.forward_analog(**{**_NEUTRO, "lx": 5})
        pad.forward_buttons(frozenset())

        assert len(_payloads(fake_uhid)) == 1

    def test_botoes_diferentes_com_o_mesmo_bit_nao_reemitem(
        self, fake_uhid: _FakeFd
    ) -> None:
        """As três regiões do touchpad são invenção nossa: no report do DualSense
        dão o MESMO bit. Delta por (axes, buttons) cru reemitiria a toa."""
        pad = _pad_ligado(fake_uhid)
        pad.forward_buttons(frozenset({"touchpad_left_press"}))

        pad.forward_buttons(frozenset({"touchpad_right_press"}))

        assert len(_payloads(fake_uhid)) == 1

    def test_mudanca_volta_a_emitir(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)
        pad.forward_analog(**_NEUTRO)

        pad.forward_analog(**{**_NEUTRO, "ry": 3})

        assert len(_payloads(fake_uhid)) == 2

    def test_pad_parado_nao_emite_nem_guarda_estado(self, fake_uhid: _FakeFd) -> None:
        """Sem device os forwards são no-op: o daemon chama por tick e um warning
        por chamada seria flood no log."""
        pad = UhidDualSense(player=1, blueprint=_blueprint())

        pad.forward_analog(**_NEUTRO)
        pad.forward_buttons(frozenset({"cross"}))

        assert _payloads(fake_uhid) == []

    def test_stop_zera_o_delta(self, fake_uhid: _FakeFd) -> None:
        """Depois do stop/start o kernel não sabe nada do estado anterior — o
        primeiro report tem de sair mesmo que o estado seja igual."""
        pad = _pad_ligado(fake_uhid)
        pad.forward_analog(**{**_NEUTRO, "lx": 7})
        pad.stop()
        pad.start()
        fake_uhid.writes.clear()

        pad.forward_analog(**{**_NEUTRO, "lx": 7})

        assert len(_payloads(fake_uhid)) == 1


class TestForFlavor:
    def test_dualsense_devolve_o_vpad_uhid(self) -> None:
        pad = UhidDualSense.for_flavor("dualsense", player=2)

        assert pad is not None
        assert pad.player == 2

    def test_xbox_devolve_none_para_o_chamador_cair_no_uinput(self) -> None:
        """O hid_playstation só faz bind em 054c:0ce6: um "Xbox por uhid" não
        viraria gamepad nenhum. Xbox é trabalho do UinputGamepad."""
        assert UhidDualSense.for_flavor("xbox") is None

    @pytest.mark.parametrize("flavor", ["ps", "playstation", "ds", "DualSense", " ds "])
    def test_sinonimos_de_playstation_sao_aceitos(self, flavor: str) -> None:
        assert UhidDualSense.for_flavor(flavor) is not None

    @pytest.mark.parametrize("flavor", ["xbox360", "x360", "xinput", "XBOX"])
    def test_sinonimos_de_xbox_recusam(self, flavor: str) -> None:
        assert UhidDualSense.for_flavor(flavor) is None

    def test_sem_flavor_e_dualsense_e_nao_o_default_xbox_do_uinput(self) -> None:
        """Armadilha: normalize_flavor(None) == "xbox". Herdar aquele default aqui
        desligaria o backend uhid em silêncio justo no caso comum."""
        assert UhidDualSense.for_flavor() is not None
        assert UhidDualSense.for_flavor(None) is not None

    def test_repassa_sink_e_blueprint(self) -> None:
        sink = lambda w, s: None  # noqa: E731
        blueprint = _blueprint()

        pad = UhidDualSense.for_flavor("dualsense", rumble_sink=sink, blueprint=blueprint)

        assert pad is not None
        assert pad.rumble_sink is sink
        assert pad.blueprint is blueprint

    def test_flavor_desconhecido_recusa(self) -> None:
        """normalize_flavor cai no default xbox — que aqui significa "não é meu"."""
        assert UhidDualSense.for_flavor("nintendo") is None


class TestWaitForBind:
    def test_bind_confirmado_devolve_true(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)
        fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))

        assert pad.wait_for_bind(timeout_s=1.0) is True
        assert pad.is_bound is True

    def test_sem_bind_devolve_false_no_timeout(self, fake_uhid: _FakeFd) -> None:
        """start() só diz que o CREATE2 foi aceito. Sem esta espera o fallback do
        UHID-06 seria desonesto: "deu certo" com o jogo sem controle."""
        relogio = iter([0.0, 0.0, 0.5, 1.5])
        pad = _pad_ligado(fake_uhid, time_fn=lambda: next(relogio),
                          sleep_fn=lambda _s: None)

        assert pad.wait_for_bind(timeout_s=1.0) is False
        assert pad.is_bound is False

    def test_bind_que_chega_atrasado_e_esperado(self, fake_uhid: _FakeFd) -> None:
        """O probe faz várias idas e voltas (GET_REPORT 0x09/0x20/0x05) antes do
        UHID_START — desistir na primeira bombeada perderia todo bind real."""
        tempo = [0.0]

        def _sleep(segundos: float) -> None:
            tempo[0] += segundos
            if tempo[0] >= 0.05:
                fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))

        pad = _pad_ligado(fake_uhid, time_fn=lambda: tempo[0], sleep_fn=_sleep)

        assert pad.wait_for_bind(timeout_s=5.0) is True

    def test_pad_parado_nao_espera(self, fake_uhid: _FakeFd) -> None:
        pad = UhidDualSense(player=1, blueprint=_blueprint())

        assert pad.wait_for_bind(timeout_s=99.0) is False

    def test_probe_que_recusa_depois_do_start_devolve_false(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O UHID_START chega no COMEÇO do probe, não no fim.

        Medido ao vivo com dois vpads de MAC igual: o segundo recebeu
        ``START, OPEN, GET_REPORT, GET_REPORT, CLOSE, STOP`` em 2 ms, enquanto o
        kernel logava ``Failed to create dualsense / probe failed -17``. Parar no
        START devolvia True para um device natimorto — e o fallback para o uinput,
        que é a razão de existir deste método, nunca aconteceria: o jogo ficaria
        sem controle nenhum.
        """
        tempo = [0.0]

        def _sleep(segundos: float) -> None:
            tempo[0] += segundos
            # O probe desiste logo depois do START (CLOSE+STOP), como no hardware.
            if tempo[0] >= 0.02 and not fake_uhid.reads:
                fake_uhid.reads.append(struct.pack("<I", uhid_gamepad.UHID_STOP)
                                       + bytes(8))

        pad = _pad_ligado(fake_uhid, time_fn=lambda: tempo[0], sleep_fn=_sleep)
        fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))

        assert pad.wait_for_bind(timeout_s=1.0) is False
        assert pad.is_bound is False

    def test_bind_estavel_sobrevive_ao_intervalo_de_graca(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O probe que dá certo NUNCA manda STOP — o settle não pode reprovar."""
        tempo = [0.0]

        def _sleep(segundos: float) -> None:
            tempo[0] += segundos

        pad = _pad_ligado(fake_uhid, time_fn=lambda: tempo[0], sleep_fn=_sleep)
        fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))

        assert pad.wait_for_bind(timeout_s=1.0) is True
        assert tempo[0] >= uhid_gamepad._BIND_SETTLE_S  # esperou de fato

    def test_stop_derruba_o_bind(self, fake_uhid: _FakeFd) -> None:
        pad = _pad_ligado(fake_uhid)
        fake_uhid.reads.append(struct.pack("<I", UHID_START) + bytes(8))
        pad.wait_for_bind(timeout_s=1.0)

        pad.stop()

        assert pad.is_bound is False

    @pytest.mark.parametrize("combo", range(16))
    def test_dpad_concorda_com_o_backend_uinput_em_todo_combo(self, combo: int) -> None:
        """Trava os dois backends juntos: para QUALQUER combinação de d-pad, o hat
        do uhid tem de significar o mesmo vetor que o uinput emite. Sem isto, um
        dos dois pode driftar e só a Vitória descobre, no jogo."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import _HAT_BY_VECTOR
        from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

        nomes = ("dpad_up", "dpad_down", "dpad_left", "dpad_right")
        pressed = frozenset(n for i, n in enumerate(nomes) if combo & (1 << i))

        hat = UhidDualSense._dpad_hat(pressed)

        assert hat == _HAT_BY_VECTOR[UinputGamepad._dpad_vector(pressed)]
