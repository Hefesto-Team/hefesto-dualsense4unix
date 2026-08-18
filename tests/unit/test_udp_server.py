"""Testes do UDP server compat DSX."""
from __future__ import annotations

import asyncio
import json

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.udp_server import (
    DsxProtocol,
    RateLimiter,
    UdpHandler,
    UdpServer,
    parse_side,
)
from hefesto_dualsense4unix.testing import FakeController

# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_aceita_ate_o_limite():
    rl = RateLimiter(rate_global=100, rate_per_ip=10)
    for _ in range(10):
        assert rl.allow("1.2.3.4", now=0.0) is True
    assert rl.allow("1.2.3.4", now=0.0) is False


def test_rate_limiter_por_ip_isolado():
    rl = RateLimiter(rate_global=100, rate_per_ip=3)
    for _ in range(3):
        assert rl.allow("a", now=0.0) is True
    for _ in range(3):
        assert rl.allow("b", now=0.0) is True
    assert rl.allow("a", now=0.0) is False
    assert rl.allow("b", now=0.0) is False


def test_rate_limiter_global_protege():
    rl = RateLimiter(rate_global=5, rate_per_ip=100)
    for i in range(5):
        assert rl.allow(f"ip{i}", now=0.0) is True
    assert rl.allow("ip5", now=0.0) is False


def test_rate_limiter_sweep_remove_ips_inativos():
    rl = RateLimiter(rate_global=100, rate_per_ip=3)
    rl.allow("volatile", now=0.0)
    assert "volatile" in rl.per_ip
    # Avança >1s sem atividade e força sweep
    rl._sweep(now=2.0)
    assert "volatile" not in rl.per_ip


def test_rate_limiter_janela_desliza():
    rl = RateLimiter(rate_global=100, rate_per_ip=5)
    for _ in range(5):
        rl.allow("x", now=0.0)
    assert rl.allow("x", now=0.5) is False
    # Após janela de 1s passar, deve permitir de novo
    assert rl.allow("x", now=1.1) is True


# ---------------------------------------------------------------------------
# UdpHandler (dispatch lógico, sem socket real)
# ---------------------------------------------------------------------------


def _mk_handler() -> tuple[UdpHandler, FakeController, StateStore]:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    handler = UdpHandler(controller=fc, store=store)
    return handler, fc, store


def _datagram(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_trigger_update_aplica_trigger():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            {"type": "TriggerUpdate", "parameters": ["right", "Rigid", 5, 200]}
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 1
    assert triggers[0].payload[0] == "right"


def test_rgb_update_aplica_led():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "RGBUpdate", "parameters": [0, 255, 128, 0]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert leds[-1].payload == (255, 128, 0)


def test_reset_aplica_off_em_ambos():
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "ResetToUserSettings", "parameters": []}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    sides = [c.payload[0] for c in triggers]
    assert sorted(sides) == ["left", "right"]


def test_versao_invalida_dropa_com_contador():
    handler, fc, store = _mk_handler()
    payload = {"version": 2, "instructions": []}
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.unsupported_version") == 1
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert triggers == []


def test_parse_error_incrementa_contador():
    handler, _, store = _mk_handler()
    handler.handle_datagram(b"not json", ("127.0.0.1", 12345))
    assert store.counter("udp.parse_error") == 1


def test_oversize_dropa():
    handler, _, store = _mk_handler()
    big = b"x" * 5000
    handler.handle_datagram(big, ("127.0.0.1", 12345))
    assert store.counter("udp.oversize") == 1


def test_instrucao_desconhecida_incrementa_contador():
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "FutureFancy", "parameters": []}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.unknown_instruction") == 1


def test_instrucao_erro_captura_e_bump():
    handler, fc, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            # mode invalido -> build_from_name levanta
            {"type": "TriggerUpdate", "parameters": ["right", "ModeInexistente"]}
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.error.TriggerUpdate") == 1
    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert triggers == []


def test_rate_limit_drop_conta_em_store():
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    # Rate limit bem restrito
    rl = RateLimiter(rate_global=2, rate_per_ip=2)
    handler = UdpHandler(controller=fc, store=store, rate_limiter=rl)
    payload = _datagram({"version": 1, "instructions": []})
    for _ in range(5):
        handler.handle_datagram(payload, ("127.0.0.1", 1))
    # 2 aceitos + 3 dropados
    assert store.counter("udp.rate_limited") == 3


# ---------------------------------------------------------------------------
# Handlers UDP propagam ao hardware — AUDIT-FINDING-UDP-PLACEHOLDER-HANDLERS-01
# ---------------------------------------------------------------------------


def test_player_led_propaga_bitmask_ao_controller():
    """PlayerLED decodifica bitmask em tuple[bool x5] e chama set_player_leds."""
    handler, fc, store = _mk_handler()
    # 0b10101 = 21 decimal: bits 0, 2, 4 acesos; 1 e 3 apagados.
    payload = {
        "version": 1,
        "instructions": [{"type": "PlayerLED", "parameters": [0, 21]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    pl_cmds = [c for c in fc.commands if c.kind == "set_player_leds"]
    assert len(pl_cmds) == 1, "set_player_leds deve ser chamado exatamente 1x"
    assert pl_cmds[0].payload == (True, False, True, False, True)
    assert fc.last_player_leds == (True, False, True, False, True)
    assert store.counter("udp.applied.PlayerLED") == 1
    assert store.counter("udp.player_led.21") == 1


def test_mic_led_propaga_estado_ao_controller():
    """MicLED decodifica bool e chama set_mic_led."""
    handler, fc, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "MicLED", "parameters": [1]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    mic_cmds = [c for c in fc.commands if c.kind == "set_mic_led"]
    assert len(mic_cmds) == 1, "set_mic_led deve ser chamado exatamente 1x"
    assert mic_cmds[0].payload is True
    assert fc.mic_led_history == [True]
    assert store.counter("udp.applied.MicLED") == 1
    assert store.counter("udp.mic_led.1") == 1


def test_rgb_update_clampa_valores_fora_de_range():
    """RGBUpdate faz clamp silencioso em [0, 255] (achado 19 auditoria V23)."""
    handler, fc, _ = _mk_handler()
    payload = {
        "version": 1,
        # -10 abaixo de 0, 300 acima de 255, 128 ok, 999 acima.
        "instructions": [{"type": "RGBUpdate", "parameters": [0, -10, 300, 128]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert len(leds) == 1
    assert leds[-1].payload == (0, 255, 128)


# ---------------------------------------------------------------------------
# TriggerThreshold — UDP-TRIGGER-THRESHOLD-01
#
# A instrução era um contador vazio: validava o lado, fazia `bump` e descartava.
# Um mod recebia "sucesso" e nada acontecia. Agora ela é a deadzone do gatilho
# no gamepad virtual — o MESMO que a instrução significa no DSX
# (`L2_Analog >= threshold ? L2_Analog : 0`, corte seco, sem reescala).
# ---------------------------------------------------------------------------


def test_trigger_threshold_grava_limiar_no_store():
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "TriggerThreshold", "parameters": ["right", 128]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.udp_trigger_thresholds == (0, 128)
    assert store.counter("udp.applied.TriggerThreshold") == 1


def test_trigger_threshold_aceita_layout_canonico_do_dsx():
    """`[controllerIndex, side, value]` com side no ordinal do enum `Trigger`.

    É o que o SDK C# do DSX emite (`Instruction.TriggerThreshold`): 1=Left,
    2=Right. Antes isso virava `udp.error.TriggerThreshold` porque o parser
    fazia `str(0).lower()` e não achava "left"/"right".
    """
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [{"type": "TriggerThreshold", "parameters": [0, 1, 200]}],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.udp_trigger_thresholds == (200, 0)
    assert store.counter("udp.error.TriggerThreshold") == 0


def test_trigger_threshold_clampa_e_rejeita_lado_invalido():
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            {"type": "TriggerThreshold", "parameters": ["left", 999]},
            {"type": "TriggerThreshold", "parameters": ["meio", 10]},
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.udp_trigger_thresholds == (255, 0)
    assert store.counter("udp.error.TriggerThreshold") == 1


def test_reset_to_user_settings_zera_a_deadzone():
    """A deadzone é parte do que o mod mudou — "voltar ao do usuário" a inclui."""
    handler, _, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            {"type": "TriggerThreshold", "parameters": ["left", 90]},
            {"type": "TriggerThreshold", "parameters": ["right", 90]},
            {"type": "ResetToUserSettings", "parameters": []},
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.udp_trigger_thresholds == (0, 0)


def test_envelope_dsx_autentico_sem_version_e_type_inteiro():
    """O pacote que o SDK do DSX emite de verdade, byte a byte.

    `Packet.cs` do SDK não tem campo `version`, e `type` é o ordinal do enum
    `InstructionType` (1=TriggerUpdate, 2=RGBUpdate, 3=PlayerLED, 4=Trigger
    Threshold, 5=MicLED). Antes, ESTE pacote morria em
    `udp.unsupported_version` sem nenhuma instrução ser sequer lida.
    """
    handler, fc, store = _mk_handler()
    pkt = {
        "instructions": [
            # Instruction.Galloping(Trigger.Right, 0, 9, 6, 7, 10)
            {"type": 1, "parameters": [0, 2, 15, 0, 9, 6, 7, 10]},
            # Instruction.RGBUpdate(255, 80, 0)
            {"type": 2, "parameters": [0, 255, 80, 0]},
            # Instruction.PlayerLED(true, false, true, false, true)
            {"type": 3, "parameters": [0, True, False, True, False, True]},
            # Instruction.TriggerThreshold(Trigger.Left, 128)
            {"type": 4, "parameters": [0, 1, 128]},
            # Instruction.MicLED(MicLEDMode.On)
            {"type": 5, "parameters": [0, 0]},
        ]
    }
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))

    assert store.counter("udp.unsupported_version") == 0
    assert store.counter("udp.dsx_envelope") == 1
    for nome in ("TriggerUpdate", "RGBUpdate", "PlayerLED", "TriggerThreshold", "MicLED"):
        assert store.counter(f"udp.applied.{nome}") == 1, nome
        assert store.counter(f"udp.error.{nome}") == 0, nome

    gatilhos = [c for c in fc.commands if c.kind == "set_trigger"]
    assert gatilhos[-1].payload[0] == "right"
    assert [c for c in fc.commands if c.kind == "set_led"][-1].payload == (255, 80, 0)
    assert fc.last_player_leds == (True, False, True, False, True)
    assert fc.mic_led_history == [True]
    assert store.udp_trigger_thresholds == (128, 0)


def test_trigger_update_dsx_traduz_modos_com_assinatura_identica():
    """Ordinais 13-18 do `TriggerMode` do DSX -> presets do Hefesto."""
    from hefesto_dualsense4unix.core.trigger_effects import galloping, resistance

    handler, fc, store = _mk_handler()
    pkt = {
        "instructions": [
            {"type": 1, "parameters": [0, 1, 13, 5, 6]},  # Resistance(5, 6)
            {"type": 1, "parameters": [0, 2, 15, 0, 9, 6, 7, 10]},  # Galloping
        ]
    }
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    gatilhos = [c for c in fc.commands if c.kind == "set_trigger"]
    assert gatilhos[0].payload[1] == resistance(5, 6)
    assert gatilhos[1].payload[1] == galloping(0, 9, 6, 7, 10)
    assert store.counter("udp.error.TriggerUpdate") == 0


def test_trigger_update_dsx_custom_value_vira_custom_do_hefesto():
    """`CustomTriggerValue` (12): o 1º param é o `CustomTriggerValueMode`."""
    handler, fc, _ = _mk_handler()
    # CustomTriggerValueMode.RigidB = 3 -> modo HID 0x01|0x04 = 5.
    pkt = {"instructions": [{"type": 1, "parameters": [0, 1, 12, 3, 10, 200]}]}
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    efeito = [c for c in fc.commands if c.kind == "set_trigger"][-1].payload[1]
    assert efeito.mode == 0x05
    # Forças completadas com zero até 7, como o servidor do DSX faz.
    assert efeito.forces == (10, 200, 0, 0, 0, 0, 0)


def test_trigger_update_dsx_modo_pronto_falha_alto_sem_aproximar():
    """`Hard`, `Soft`, `Rigid` & cia são curvas fechadas do DSX.

    Sem tabela de bytes sob licença utilizável, aproximar mudaria a sensação
    no gatilho sem o mod saber. Erro barulhento é a resposta honesta.
    """
    handler, fc, store = _mk_handler()
    pkt = {"instructions": [{"type": 1, "parameters": [0, 1, 4]}]}  # Hard
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    assert store.counter("udp.error.TriggerUpdate") == 1
    assert [c for c in fc.commands if c.kind == "set_trigger"] == []


def test_ordinal_ambiguo_do_racingdsx_nao_age_errado():
    """O fork RacingDSX usa 6=TriggerThreshold; a maioria usa 6=PlayerLEDNew.

    Com a divergência sem desempate seguro, 6 não é mapeado: vira instrução
    desconhecida (barulhenta) em vez de mexer no que o mod não pediu.
    """
    handler, fc, store = _mk_handler()
    pkt = {"instructions": [{"type": 6, "parameters": [0, 1, 128]}]}
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    assert store.counter("udp.unknown_instruction") == 1
    assert store.udp_trigger_thresholds == (0, 0)
    assert [c for c in fc.commands if c.kind != "connect"] == []


def test_mic_led_pulse_degrada_com_contador_proprio():
    handler, fc, store = _mk_handler()
    pkt = {"instructions": [{"type": 5, "parameters": [0, 1]}]}  # MicLEDMode.Pulse
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    assert store.counter("udp.mic_led.pulse_degradado") == 1
    assert fc.mic_led_history == [True]


def test_controller_index_diferente_de_zero_e_auditavel():
    """Com 4 controles, endereçar o P2 e acertar o P1 não pode ser silencioso."""
    handler, _, store = _mk_handler()
    pkt = {"instructions": [{"type": 2, "parameters": [1, 10, 20, 30]}]}
    handler.handle_datagram(_datagram(pkt), ("127.0.0.1", 12345))
    assert store.counter("udp.controller_index_ignorado") == 1
    assert store.counter("udp.applied.RGBUpdate") == 1


def test_dialeto_do_hefesto_intacto_com_version_e_type_string():
    """Regressão dura: a GUI, o CLI e os testes existentes usam este dialeto."""
    handler, fc, store = _mk_handler()
    payload = {
        "version": 1,
        "instructions": [
            {"type": "TriggerUpdate", "parameters": ["right", "Rigid", 5, 200]},
            {"type": "PlayerLED", "parameters": [0, 21]},
            {"type": "MicLED", "parameters": [1]},
        ],
    }
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.dsx_envelope") == 0
    assert fc.last_player_leds == (True, False, True, False, True)
    assert fc.mic_led_history == [True]
    assert [c for c in fc.commands if c.kind == "set_trigger"][-1].payload[0] == "right"


def test_version_presente_e_diferente_de_1_continua_dropando():
    handler, fc, store = _mk_handler()
    payload = {"version": 2, "instructions": [{"type": 2, "parameters": [0, 1, 2, 3]}]}
    handler.handle_datagram(_datagram(payload), ("127.0.0.1", 12345))
    assert store.counter("udp.unsupported_version") == 1
    assert [c for c in fc.commands if c.kind != "connect"] == []


def test_parse_side_cobre_os_dois_dialetos():
    assert parse_side("Left") == "left"
    assert parse_side("right") == "right"
    assert parse_side(1) == "left"
    assert parse_side(2) == "right"
    assert parse_side("2") == "right"
    # 0 é `Trigger.Invalid` no DSX; True não pode virar "left" por ser int.
    assert parse_side(0) is None
    assert parse_side(True) is None
    assert parse_side("meio") is None
    assert parse_side(None) is None


def test_deadzone_corta_o_gatilho_no_gamepad_virtual():
    """Prova o efeito REAL: o limiar muda o que o jogo recebe do pad virtual.

    Sem este teste a instrução seria de novo um valor guardado que ninguém lê
    — que era exatamente o defeito original.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    class _Pad:
        def __init__(self) -> None:
            self.analog: dict[str, int] = {}

        def forward_analog(self, **kw: int) -> None:
            self.analog = kw

        def forward_buttons(self, pressed: frozenset) -> None:
            return

    handler, _, store = _mk_handler()
    pad = _Pad()
    # `_launch_reconcile_next_at` no infinito: a reconciliação de launch é um
    # extra do dispatch (lê marker no disco) e não é o que este teste mede.
    daemon = SimpleNamespace(
        store=store, _gamepad_device=pad, _launch_reconcile_next_at=float("inf")
    )
    estado = SimpleNamespace(
        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=100, r2_raw=100
    )

    # Sem limiar o valor bruto passa intacto.
    gp.dispatch_gamepad(daemon, estado, frozenset())
    assert (pad.analog["l2"], pad.analog["r2"]) == (100, 100)

    # Mod pede limiar 150 no esquerdo: 100 < 150 -> o jogo lê zero.
    handler.handle_datagram(
        _datagram(
            {
                "version": 1,
                "instructions": [
                    {"type": "TriggerThreshold", "parameters": ["left", 150]}
                ],
            }
        ),
        ("127.0.0.1", 12345),
    )
    gp.dispatch_gamepad(daemon, estado, frozenset())
    assert (pad.analog["l2"], pad.analog["r2"]) == (0, 100)

    # No limiar em diante o valor bruto passa SEM reescala (corte seco do DSX).
    estado.l2_raw = 150
    gp.dispatch_gamepad(daemon, estado, frozenset())
    assert pad.analog["l2"] == 150


# ---------------------------------------------------------------------------
# DsxProtocol.connection_made — BUG-UDP-01 (A-02)
# ---------------------------------------------------------------------------


def test_connection_made_nao_levanta_assertion_com_mock_transport():
    """Regressão BUG-UDP-01: em Python 3.10 o objeto real é
    `_SelectorDatagramTransport`, que falhava no `isinstance` contra
    `asyncio.DatagramTransport`. A atribuição direta deve aceitar qualquer
    `BaseTransport` sem levantar AssertionError.
    """
    handler, _, _ = _mk_handler()
    proto = DsxProtocol(handler)

    class _FakeTransport(asyncio.BaseTransport):
        pass

    fake = _FakeTransport()
    # Não deve levantar AssertionError nem qualquer outra exceção.
    proto.connection_made(fake)
    assert proto.transport is fake


# ---------------------------------------------------------------------------
# UdpServer ponta-a-ponta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_udp_server_recebe_datagrama_real(tmp_path):
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    UdpServer(controller=fc, store=store, host="127.0.0.1", port=0)
    # Sobrescreve porta 0 (auto-atribui) — vamos descobrir
    loop = asyncio.get_running_loop()

    # Re-implementa start para capturar a porta
    from hefesto_dualsense4unix.daemon.udp_server import DsxProtocol
    from hefesto_dualsense4unix.daemon.udp_server import UdpHandler as UdpHandlerCls

    handler = UdpHandlerCls(controller=fc, store=store, rate_limiter=RateLimiter())
    transport, _ = await loop.create_datagram_endpoint(
        lambda: DsxProtocol(handler),
        local_addr=("127.0.0.1", 0),
    )
    try:
        addr = transport.get_extra_info("sockname")
        port = addr[1]

        # Manda um datagrama
        send_transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=("127.0.0.1", port)
        )
        payload = {
            "version": 1,
            "instructions": [
                {"type": "TriggerUpdate", "parameters": ["left", "Rigid", 3, 150]}
            ],
        }
        send_transport.sendto(json.dumps(payload).encode("utf-8"))
        # Dá tempo pro datagrama chegar
        await asyncio.sleep(0.05)
        send_transport.close()

        triggers = [c for c in fc.commands if c.kind == "set_trigger"]
        assert len(triggers) >= 1
    finally:
        transport.close()
