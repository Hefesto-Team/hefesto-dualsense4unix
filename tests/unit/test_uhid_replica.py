"""REPLICA-03 no vpad uhid — replicação do output do jogo (sem /dev/uhid).

O report 0x02 que o jogo escreve no hidraw do vpad carrega, além do rumble
(que já tinha passthrough), gatilhos adaptativos, lightbar e player-LEDs.
Estes testes travam o parser (offsets do `dualsense_output_report_common` do
kernel / `DS5EffectsState_t` do SDL), a política de posse (só replica na
sessão UHID_OPEN..UHID_CLOSE, com graça pós-probe), o dedup por valor, o
rate-limit por categoria e a devolução do perfil no fim da sessão.

Mesma técnica do `test_uhid_gamepad.py`: fd falso via monkeypatch de os.*.
"""
from __future__ import annotations

import struct
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _GAME_REPLICA_GRACE_S,
    _REPLICA_MIN_INTERVAL_S,
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_CLOSE,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
)

_FEATURE_09 = bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13)


def _blueprint() -> dict[str, Any]:
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(40),
            0x09: _FEATURE_09,
            0x20: bytes([0x20]) + bytes(63),
        },
    }


class _FakeFd:
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
    event = struct.pack("<I", UHID_OUTPUT)
    event += report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
    event += struct.pack("<HB", len(report), 1)
    return event


def _evento(tipo: int) -> bytes:
    return struct.pack("<I", tipo) + bytes(8)


#: Blocos de trigger effect sintéticos (modo + 10 parâmetros), estilo SDL.
_BLOCO_R = bytes([0x21, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
_BLOCO_L = bytes([0x26, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])


def _edge_report(
    *,
    flag0: int = 0,
    flag1: int = 0,
    trigger_r: bytes | None = None,
    trigger_l: bytes | None = None,
    rgb: tuple[int, int, int] | None = None,
    player_mask: int | None = None,
    weak: int = 0,
    strong: int = 0,
) -> bytes:
    """Report 0x02 sintético do Edge — layout do dualsense_output_report_common."""
    body = bytearray(47)
    body[0] = flag0
    body[1] = flag1
    body[2] = weak
    body[3] = strong
    if trigger_r is not None:
        body[10:21] = trigger_r
    if trigger_l is not None:
        body[21:32] = trigger_l
    if player_mask is not None:
        body[43] = player_mask
    if rgb is not None:
        body[44:47] = bytes(rgb)
    return bytes([0x02]) + bytes(body)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _pad_em_sessao(
    fake: _FakeFd, **kwargs: Any
) -> tuple[UhidDualSense, _Clock]:
    """Vpad com bind + sessão aberta (START, OPEN) e a graça pós-probe vencida."""
    clock = _Clock()
    pad = UhidDualSense(
        player=1, blueprint=_blueprint(), time_fn=clock, sleep_fn=lambda _s: None,
        **kwargs,
    )
    assert pad.start() is True
    fake.reads.append(_evento(UHID_START))
    fake.reads.append(_evento(UHID_OPEN))
    pad.pump_ff()
    clock.t = _GAME_REPLICA_GRACE_S + 0.5
    fake.writes.clear()
    return pad, clock


class _Sinks:
    """Coletores de todas as categorias, prontos para injeção via kwargs."""

    def __init__(self) -> None:
        self.triggers: list[tuple[str, bytes]] = []
        self.cores: list[tuple[int, int, int]] = []
        self.players: list[tuple[bool, ...]] = []
        self.session_ends = 0
        self.rumbles: list[tuple[int, int]] = []

    def kwargs(self) -> dict[str, Any]:
        return {
            "trigger_sink": lambda side, block: self.triggers.append((side, block)),
            "lightbar_sink": lambda r, g, b: self.cores.append((r, g, b)),
            "player_led_sink": lambda bits: self.players.append(tuple(bits)),
            "session_end_sink": self._session_end,
            "rumble_sink": lambda w, s: self.rumbles.append((w, s)),
        }

    def _session_end(self) -> None:
        self.session_ends += 1


class TestParserDoReport:
    def test_trigger_direito_replica_o_bloco_cru(self, fake_uhid: _FakeFd) -> None:
        """flag0 bit 0x04 (SDL: "Enable right trigger effect") + [10..20]."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag0=0x04, trigger_r=_BLOCO_R))
        )

        pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R)]
        assert pad.trigger_replicas == 1

    def test_trigger_esquerdo_replica_o_bloco_cru(self, fake_uhid: _FakeFd) -> None:
        """flag0 bit 0x08 (SDL: "Enable left trigger effect") + [21..31]."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag0=0x08, trigger_l=_BLOCO_L))
        )

        pad.pump_ff()

        assert sinks.triggers == [("left", _BLOCO_L)]

    def test_lightbar_replica_o_rgb(self, fake_uhid: _FakeFd) -> None:
        """flag1 bit 0x04 (kernel: LIGHTBAR_CONTROL_ENABLE) + rgb em [44..46]."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(10, 200, 30)))
        )

        pad.pump_ff()

        assert sinks.cores == [(10, 200, 30)]
        assert pad.lightbar_replicas == 1

    def test_player_leds_replicam_e_o_bit_de_fade_e_ignorado(
        self, fake_uhid: _FakeFd
    ) -> None:
        """flag1 bit 0x10 (kernel: PLAYER_INDICATOR_CONTROL_ENABLE) + [43].

        O 0x20 do byte é o "sem fade" do firmware, não um sexto LED — o kernel
        também manda `player_leds & 0x1F` do lado de lá.
        """
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x10, player_mask=0x20 | 0x0A))
        )

        pad.pump_ff()

        assert sinks.players == [(False, True, False, True, False)]
        assert pad.player_led_replicas == 1

    def test_report_combinado_replica_todas_as_categorias(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Um único 0x02 pode carregar rumble + gatilhos + LED + player juntos."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(
                _edge_report(
                    flag0=0x02 | 0x04 | 0x08,
                    flag1=0x04 | 0x10,
                    trigger_r=_BLOCO_R,
                    trigger_l=_BLOCO_L,
                    rgb=(1, 2, 3),
                    player_mask=0x04,
                    weak=100,
                    strong=50,
                )
            )
        )

        pad.pump_ff()

        assert sinks.rumbles == [(100, 50)]
        assert sinks.triggers == [("right", _BLOCO_R), ("left", _BLOCO_L)]
        assert sinks.cores == [(1, 2, 3)]
        assert sinks.players == [(False, False, True, False, False)]

    def test_flag_desligada_nao_replica_a_categoria(self, fake_uhid: _FakeFd) -> None:
        """Bytes presentes SEM o bit de valid_flag não são pedido nenhum."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(
                _edge_report(flag0=0, flag1=0, trigger_r=_BLOCO_R, rgb=(9, 9, 9))
            )
        )

        pad.pump_ff()

        assert sinks.triggers == []
        assert sinks.cores == []
        assert pad.output_count == 1

    def test_report_truncado_nao_explode(self, fake_uhid: _FakeFd) -> None:
        """Jogo mandando report curto (flags ligados sem payload) não derruba."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        curto = bytes([0x02, 0x04 | 0x08, 0x04 | 0x10])  # só os flags
        fake_uhid.reads.append(_output_event(curto))

        pad.pump_ff()  # não levanta

        assert sinks.triggers == []
        assert sinks.cores == []
        assert sinks.players == []


class TestPosseDaSessao:
    def test_sem_uhid_open_nao_replica(self, fake_uhid: _FakeFd) -> None:
        """Fora da sessão (nenhum usuário abriu o device) o jogo não existe."""
        sinks = _Sinks()
        clock = _Clock()
        pad = UhidDualSense(
            player=1, blueprint=_blueprint(), time_fn=clock, **sinks.kwargs()
        )
        pad.start()
        fake_uhid.reads.append(_evento(UHID_START))
        pad.pump_ff()
        clock.t = _GAME_REPLICA_GRACE_S + 1.0
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(1, 1, 1)))
        )

        pad.pump_ff()

        assert sinks.cores == []

    def test_graca_pos_probe_filtra_o_output_do_kernel(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O probe do hid_playstation emite player-LED com a numeração DO KERNEL
        logo após o START — replicá-lo renumeraria o físico a cada boot de vpad
        (o P3 que o REPLICA-03 cura). Dentro da graça: descarta."""
        sinks = _Sinks()
        clock = _Clock()
        pad = UhidDualSense(
            player=1, blueprint=_blueprint(), time_fn=clock, **sinks.kwargs()
        )
        pad.start()
        fake_uhid.reads.append(_evento(UHID_START))
        fake_uhid.reads.append(_evento(UHID_OPEN))
        # Ainda dentro da graça: o "output do probe".
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x10, player_mask=0x15))
        )
        pad.pump_ff()
        assert sinks.players == []

        # Graça vencida: o output do JOGO replica normalmente.
        clock.t = _GAME_REPLICA_GRACE_S + 0.1
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x10, player_mask=0x02))
        )
        pad.pump_ff()
        assert sinks.players == [(False, True, False, False, False)]

    def test_close_devolve_a_posse_via_session_end_sink(
        self, fake_uhid: _FakeFd
    ) -> None:
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(0, 255, 0)))
        )
        pad.pump_ff()
        assert sinks.cores == [(0, 255, 0)]

        fake_uhid.reads.append(_evento(UHID_CLOSE))
        pad.pump_ff()

        assert sinks.session_ends == 1

    def test_close_sem_replica_nenhuma_nao_chama_o_sink(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Teardown de vpad que o jogo nunca tocou não pode reescrever perfil."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())

        fake_uhid.reads.append(_evento(UHID_CLOSE))
        pad.pump_ff()

        assert sinks.session_ends == 0

    def test_stop_do_vpad_encerra_a_sessao(self, fake_uhid: _FakeFd) -> None:
        """Emulação desligada no meio do jogo: a posse volta ao perfil."""
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag0=0x04, trigger_r=_BLOCO_R))
        )
        pad.pump_ff()

        pad.stop()

        assert sinks.session_ends == 1

    def test_sessao_nova_reentrega_o_mesmo_valor(self, fake_uhid: _FakeFd) -> None:
        """CLOSE zera o dedup: o 1º valor do próximo jogo sai mesmo repetido."""
        sinks = _Sinks()
        pad, clock = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(5, 5, 5)))
        )
        pad.pump_ff()
        fake_uhid.reads.append(_evento(UHID_CLOSE))
        pad.pump_ff()
        fake_uhid.reads.append(_evento(UHID_OPEN))
        clock.t += 1.0
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(5, 5, 5)))
        )

        pad.pump_ff()

        assert sinks.cores == [(5, 5, 5), (5, 5, 5)]
        assert sinks.session_ends == 1


class TestDedupERateLimit:
    def test_valor_repetido_nao_reenvia(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, clock = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        for _ in range(3):
            fake_uhid.reads.append(
                _output_event(_edge_report(flag1=0x04, rgb=(7, 7, 7)))
            )
            pad.pump_ff()
            clock.t += 1.0  # rate-limit fora da equação: o filtro é o dedup

        assert sinks.cores == [(7, 7, 7)]
        assert pad.lightbar_replicas == 1

    def test_rajada_e_segurada_pelo_rate_limit_e_sai_no_pump_seguinte(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Mais de ~250 Hz numa categoria: o valor NOVO fica pendente (não é
        perdido) e é entregue no próximo pump com o intervalo vencido."""
        sinks = _Sinks()
        pad, clock = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(1, 1, 1)))
        )
        pad.pump_ff()
        # Mesmo instante: acima do rate — retido.
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(2, 2, 2)))
        )
        pad.pump_ff()
        assert sinks.cores == [(1, 1, 1)]

        clock.t += _REPLICA_MIN_INTERVAL_S * 2
        pad.pump_ff()  # flush do pendente, sem output novo

        assert sinks.cores == [(1, 1, 1), (2, 2, 2)]

    def test_rajada_coalesce_no_ultimo_valor(self, fake_uhid: _FakeFd) -> None:
        """Vários valores dentro da janela: só o ÚLTIMO importa (coalescência)."""
        sinks = _Sinks()
        pad, clock = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        for cor in ((1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0)):
            fake_uhid.reads.append(_output_event(_edge_report(flag1=0x04, rgb=cor)))
        pad.pump_ff()
        clock.t += _REPLICA_MIN_INTERVAL_S * 2
        pad.pump_ff()

        assert sinks.cores == [(1, 0, 0), (4, 0, 0)]

    def test_categorias_tem_rate_limit_independente(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(
                _edge_report(flag0=0x04, flag1=0x04, trigger_r=_BLOCO_R, rgb=(6, 6, 6))
            )
        )

        pad.pump_ff()

        # Duas categorias no mesmo instante: nenhuma atrasa a outra.
        assert sinks.triggers == [("right", _BLOCO_R)]
        assert sinks.cores == [(6, 6, 6)]


class TestRobustez:
    def test_sink_que_explode_nao_derruba_o_pump(self, fake_uhid: _FakeFd) -> None:
        def _boom(*_a: Any) -> None:
            raise RuntimeError("controle sumiu")

        pad, _ = _pad_em_sessao(
            fake_uhid,
            trigger_sink=_boom,
            lightbar_sink=_boom,
            player_led_sink=_boom,
        )
        fake_uhid.reads.append(
            _output_event(
                _edge_report(
                    flag0=0x04 | 0x08,
                    flag1=0x04 | 0x10,
                    trigger_r=_BLOCO_R,
                    trigger_l=_BLOCO_L,
                    rgb=(1, 1, 1),
                    player_mask=0x01,
                )
            )
        )

        pad.pump_ff()  # não propaga

        assert pad.trigger_replicas == 2  # a entrega foi tentada (contada)

    def test_sem_sinks_nao_conta_replica(self, fake_uhid: _FakeFd) -> None:
        """Sem sink não há replicação — o contador não pode mentir."""
        pad, _ = _pad_em_sessao(fake_uhid)
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04 | 0x10, rgb=(1, 1, 1), player_mask=1))
        )

        pad.pump_ff()

        assert pad.lightbar_replicas == 0
        assert pad.player_led_replicas == 0

    def test_session_end_sink_que_explode_nao_derruba(
        self, fake_uhid: _FakeFd
    ) -> None:
        def _boom() -> None:
            raise RuntimeError("backend fora do ar")

        sinks = _Sinks()
        pad, _ = _pad_em_sessao(
            fake_uhid, session_end_sink=_boom, **{
                k: v for k, v in sinks.kwargs().items() if k != "session_end_sink"
            },
        )
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(3, 3, 3)))
        )
        pad.pump_ff()
        fake_uhid.reads.append(_evento(UHID_CLOSE))

        pad.pump_ff()  # não propaga

    def test_for_flavor_repassa_os_sinks_novos(self) -> None:
        kwargs = _Sinks().kwargs()
        pad = UhidDualSense.for_flavor("dualsense", blueprint=_blueprint(), **kwargs)

        assert pad is not None
        assert pad.rumble_sink is kwargs["rumble_sink"]
        assert pad.trigger_sink is kwargs["trigger_sink"]
        assert pad.lightbar_sink is kwargs["lightbar_sink"]
        assert pad.player_led_sink is kwargs["player_led_sink"]
        assert pad.session_end_sink is kwargs["session_end_sink"]

    def test_contadores_zeram_no_stop(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, _ = _pad_em_sessao(fake_uhid, **sinks.kwargs())
        fake_uhid.reads.append(
            _output_event(_edge_report(flag1=0x04, rgb=(8, 8, 8)))
        )
        pad.pump_ff()
        assert pad.lightbar_replicas == 1

        pad.stop()

        assert pad.lightbar_replicas == 0
        assert pad.trigger_replicas == 0
        assert pad.player_led_replicas == 0
