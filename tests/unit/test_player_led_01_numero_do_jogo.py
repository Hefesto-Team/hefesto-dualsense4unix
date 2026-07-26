"""PLAYER-LED-01 — o número que o JOGO atribui chega ao controle.

Origem: a primeira partida real com quatro controles (25/07/2026). A numeração
saía 1-2-3-4 nos nossos registros, o jogo mostrava outra coisa na tela e a luz
mostrava uma terceira — e os três estavam "certos" isoladamente. O mecanismo,
encontrado no código depois: sob autoridade de exibição 'daemon' a camada do
JOGO era descartada do merge INTEIRA, e a retenção disparava uma repintura
ativa que reescrevia o NOSSO número por cima do que o jogo tinha pedido.

Os quatro defeitos, um bloco de teste para cada:

1. a trava do log de retenção era um campo único do backend — o primeiro
   controle retido silenciava os outros três;
2. o gate era inconsistente entre categorias — gatilho escrevia sempre, luz e
   número consultavam a autoridade; duas rotas do mesmo subsistema discordando
   sobre "há jogo";
3. `uhid_replica_ativa` era emitido ANTES do gate (e até sem sink ligado):
   "a réplica ativou" nunca significou "escreveu no controle";
4. a repintura defendia o número contra quem o escreveu.

Método: o bloco `TestFiacaoDoJogoAteOFisico` entra pelo laço de verdade — o
report 0x02 do jogo é escrito no fd do vpad e drenado por `pump_ff()`, que é o
que o poll loop do daemon chama; os sinks são os REAIS (`gamepad.py`) e o
backend é o real. Nenhum método privado é chamado para "provar" que funciona: o
defeito desta sprint é de fiação ENTRE camadas, e um teste que chama a peça no
meio do caminho não teria enxergado nenhum dos quatro.

ARMADILHA DE MEDIÇÃO (documentada porque enganou a investigação ao vivo):
`/sys/class/leds` de um gamepad virtual não mostra o que o jogo escreveu — o
padrão aceso lá é o número que o KERNEL deu no probe, e a tabela de padrões do
kernel é idêntica à nossa em 1..4. Nenhum teste aqui usa padrão aceso como
prova de autoria; a prova é o log e a camada GAME.
"""
from __future__ import annotations

import struct
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _GAME_REPLICA_GRACE_S,
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
)

MAC_1 = "AA:BB:CC:00:00:01"
MAC_2 = "AA:BB:CC:00:00:02"
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

#: Padrões de player-LED. `P1` e `P4` são os da tabela do DualSense — e são
#: IDÊNTICOS aos do kernel, que é exatamente o motivo de o padrão aceso não
#: servir como prova de autoria (ver o aviso no topo do módulo).
P1 = (False, False, True, False, False)
P2 = (False, True, False, True, False)
P4 = (True, True, False, True, True)

_BLOCO_R = bytes([0x21, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


class _FakeNode:
    """Nó sysfs de LED falso — grava chamadas, nunca toca o filesystem."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []
        self.invalidated = 0

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        self.invalidated += 1


def _fake_handle() -> SimpleNamespace:
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        connected=True,
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _backend(
    *macs: str,
) -> tuple[bp.PyDualSenseController, dict[str, _FakeNode], dict[str, Any]]:
    """Backend real com um handle e um nó sysfs por MAC + autoridade mutável."""
    ctl = bp.PyDualSenseController()
    nodes: dict[str, _FakeNode] = {}
    for mac in macs:
        ctl._handles[mac] = _fake_handle()
        nodes[mac] = _FakeNode()
        ctl._sysfs[mac] = nodes[mac]
    ctl._primary_key = macs[0] if macs else None
    autoridade = {"valor": "daemon"}
    ctl.set_game_authority_provider(lambda: autoridade["valor"])
    return ctl, nodes, autoridade


def _eventos(captured: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [rec for rec in captured if rec.get("event") == nome]


# --- defeito 1: a trava do log de retenção é POR CONTROLE ---------------------


class TestTravaDeLogPorControle:
    def test_dois_controles_retidos_geram_duas_linhas(self) -> None:
        """Falha-sem: com a trava global, o PRIMEIRO controle retido silencia
        os outros — foi o que fez a leitura ao vivo concluir que só um
        endereço estava afetado, quando os quatro estavam."""
        ctl, _nodes, _aut = _backend(MAC_1, MAC_2)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
            ctl.set_game_output_for(MAC_2, led=(255, 0, 0))

        eventos = _eventos(captured, "game_output_retido_sem_jogo")
        assert {rec["uniq"] for rec in eventos} == {UNIQ_1, UNIQ_2}

    def test_o_mesmo_controle_nao_floda(self) -> None:
        """A trava continua sendo 1x por episódio — só que por controle."""
        ctl, _nodes, _aut = _backend(MAC_1)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
            ctl.set_game_output_for(MAC_1, led=(1, 1, 1))
            ctl.set_game_output_for(MAC_1, led=(2, 2, 2))

        assert len(_eventos(captured, "game_output_retido_sem_jogo")) == 1

    def test_replay_rearma_todos_os_controles(self) -> None:
        ctl, _nodes, aut = _backend(MAC_1, MAC_2)
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
        ctl.set_game_output_for(MAC_2, led=(255, 0, 0))

        aut["valor"] = "game"
        ctl.replay_retained_game_outputs()
        aut["valor"] = "daemon"

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, led=(3, 3, 3))
            ctl.set_game_output_for(MAC_2, led=(4, 4, 4))

        assert len(_eventos(captured, "game_output_retido_sem_jogo")) == 2

    def test_fim_de_sessao_rearma_so_aquele_controle(self) -> None:
        ctl, _nodes, _aut = _backend(MAC_1, MAC_2)
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
        ctl.set_game_output_for(MAC_2, led=(255, 0, 0))

        ctl.end_game_session_for(MAC_1)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, led=(9, 9, 9))
            ctl.set_game_output_for(MAC_2, led=(8, 8, 8))

        eventos = _eventos(captured, "game_output_retido_sem_jogo")
        assert [rec["uniq"] for rec in eventos] == [UNIQ_1]


# --- defeito 2: um gate só, política por categoria ---------------------------


class TestOGateEUmSoParaTodasAsCategorias:
    def test_a_mesma_chamada_retem_a_cor_e_aplica_o_numero(self) -> None:
        """A decisão passou a ser POR CAMPO: sob 'daemon' a cor do escritor
        estrangeiro é retida (incidente 14:42) e o número segue para o
        hardware (é ele que a usuária vê contradizer o jogo)."""
        ctl, nodes, _aut = _backend(MAC_1)

        ctl.set_game_output_for(MAC_1, led=(0, 255, 0), player_leds=P4)

        assert ctl._retained_game_outputs[UNIQ_1] == {"led": (0, 255, 0)}
        assert P4 in nodes[MAC_1].player_calls
        assert (0, 255, 0) not in nodes[MAC_1].rgb_calls

    def test_o_numero_do_jogo_entra_no_merge_mesmo_sob_daemon(self) -> None:
        ctl, _nodes, _aut = _backend(MAC_1)
        ctl.set_coop_outputs({MAC_1: OutputSpec(player_leds=P1)})

        ctl.set_game_output_for(MAC_1, player_leds=P4)

        assert ctl._merged_desired_for_key(MAC_1).player_leds == P4

    def test_a_cor_do_jogo_continua_fora_do_merge_sob_daemon(self) -> None:
        """Regressão do NUMA-02: a camada de COR stale (cliente Steam com a
        sessão uhid aberta sem jogo) segue neutralizada no resolve."""
        ctl, _nodes, aut = _backend(MAC_1)
        ctl._desired_default.led = (10, 20, 30)
        aut["valor"] = "game"
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))

        aut["valor"] = "daemon"

        assert ctl._merged_desired_for_key(MAC_1).led == (10, 20, 30)

    def test_gatilho_passa_a_obedecer_a_mesma_politica(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A unificação de verdade: acrescentar uma categoria à política faz a
        rota do GATILHO obedecer sem nenhuma outra mudança. Falha-sem: com a
        rota do gatilho ignorando o gate (como era), o bloco é aplicado ao
        handle mesmo com a política mandando reter."""
        ctl, _nodes, _aut = _backend(MAC_1)
        monkeypatch.setattr(
            bp,
            "_GAME_LAYER_GATED_FIELDS",
            frozenset({"led", "trigger_left", "trigger_right"}),
        )

        assert ctl.set_game_trigger_for(MAC_1, "right", _BLOCO_R) is True

        assert ctl._handles[MAC_1]._raw_trigger_right is None
        assert ctl._game_triggers_by_uniq == {}

    def test_gatilho_com_a_politica_vigente_continua_escrevendo(self) -> None:
        """A decisão registrada é que gatilho NÃO é retido — este teste trava
        o comportamento para que uma mudança de política seja deliberada."""
        ctl, _nodes, _aut = _backend(MAC_1)

        assert ctl.set_game_trigger_for(MAC_1, "right", _BLOCO_R) is True

        assert ctl._handles[MAC_1]._raw_trigger_right == _BLOCO_R


# --- defeito 4: a repintura para de reescrever o número ----------------------


class TestARepinturaNaoDefendeONumeroContraOJogo:
    def _cenario(self) -> tuple[bp.PyDualSenseController, _FakeNode, dict[str, Any]]:
        """Jogo real rodando: o número dele já chegou ao controle e o NOSSO
        número (co-op) está embaixo. Em seguida o sinal cai para 'daemon' —
        o buraco conhecido (jogo fora da Steam, janela nativa)."""
        ctl, nodes, aut = _backend(MAC_1)
        ctl._desired_default.led = (10, 20, 30)
        ctl.set_coop_outputs({MAC_1: OutputSpec(player_leds=P1)})
        aut["valor"] = "game"
        ctl.set_game_output_for(MAC_1, player_leds=P4, led=(0, 255, 0))
        aut["valor"] = "daemon"
        nodes[MAC_1].player_calls.clear()
        nodes[MAC_1].rgb_calls.clear()
        return ctl, nodes[MAC_1], aut

    def test_a_repintura_reafirma_o_numero_do_jogo(self) -> None:
        """Falha-sem: com o merge tudo-ou-nada, a repintura escreve P1 (o
        NOSSO número) por cima do P4 que o jogo pediu — o flip-flop que a
        mantenedora viu."""
        ctl, node, _aut = self._cenario()

        ctl.defend_display()

        assert node.player_calls == [P4]

    def test_a_cor_continua_defendida(self) -> None:
        """Defender a COR contra o cliente da Steam é legítimo e não muda: a
        repintura escreve a paleta por baixo, não o verde do jogo."""
        ctl, node, _aut = self._cenario()

        ctl.defend_display()

        assert node.rgb_calls == [(10, 20, 30)]

    def test_sem_camada_de_jogo_a_repintura_escreve_o_nosso_numero(self) -> None:
        """Regressão: onde o jogo nunca escreveu número, quem manda é o co-op."""
        ctl, nodes, _aut = _backend(MAC_1)
        ctl.set_coop_outputs({MAC_1: OutputSpec(player_leds=P1)})
        nodes[MAC_1].player_calls.clear()

        ctl.defend_display()

        assert nodes[MAC_1].player_calls == [P1]


# --- defeito 3: os logs param de mentir --------------------------------------


class TestLogsHonestos:
    def test_game_output_aplicado_sai_no_ponto_da_escrita(self) -> None:
        ctl, _nodes, _aut = _backend(MAC_1)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, player_leds=P4)

        (evento,) = _eventos(captured, "game_output_aplicado")
        assert evento["uniq"] == UNIQ_1
        assert evento["campos"] == ["player_leds"]
        # "preferido" e não "sysfs": `_write_partial_output` cai em hidraw
        # por dentro se o nó recusar, e esta camada não vê isso acontecer.
        assert evento["destino"] == "sysfs_preferido"

    def test_campo_retido_nao_vira_game_output_aplicado(self) -> None:
        """A distinção que faltava no journal: pedido do jogo x escrita."""
        ctl, _nodes, _aut = _backend(MAC_1)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, led=(0, 255, 0))

        assert _eventos(captured, "game_output_aplicado") == []
        assert len(_eventos(captured, "game_output_retido_sem_jogo")) == 1

    def test_controle_desconectado_diz_que_so_registrou(self) -> None:
        ctl = bp.PyDualSenseController()

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, player_leds=P4)

        (evento,) = _eventos(captured, "game_output_aplicado")
        assert evento["destino"] == "registrado_sem_handle"

    def test_game_output_aplicado_nao_floda(self) -> None:
        ctl, _nodes, _aut = _backend(MAC_1)

        with structlog.testing.capture_logs() as captured:
            ctl.set_game_output_for(MAC_1, player_leds=P4)
            ctl.set_game_output_for(MAC_1, player_leds=P2)
            ctl.set_game_output_for(MAC_1, player_leds=P1)

        assert len(_eventos(captured, "game_output_aplicado")) == 1


# --- entrega 5: o diagnóstico expõe a camada do jogo -------------------------


class TestDiagnosticoExpoeACamadaDoJogo:
    """`describe_controllers` é a fonte do `controller numbers` (e do card da
    GUI). Sem estes campos, o único jeito de comparar "nosso número" com
    "número do jogo" seria ler o LED — que é ambíguo por construção."""

    def test_expoe_o_numero_e_a_cor_que_o_jogo_escreveu(self) -> None:
        ctl, _nodes, aut = _backend(MAC_1)
        aut["valor"] = "game"
        ctl.set_game_output_for(MAC_1, player_leds=P4, led=(0, 255, 0))

        (entrada,) = ctl.describe_controllers()

        assert entrada["player_leds_game"] == list(P4)
        assert entrada["lightbar_game"] == [0, 255, 0]
        assert entrada["game_output_retido"] == []

    def test_expoe_o_que_o_gate_esta_retendo_agora(self) -> None:
        ctl, _nodes, _aut = _backend(MAC_1)  # autoridade 'daemon'
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0), player_leds=P4)

        (entrada,) = ctl.describe_controllers()

        assert entrada["game_output_retido"] == ["led"]
        assert entrada["lightbar_game"] is None
        assert entrada["player_leds_game"] == list(P4)

    def test_controle_intocado_pelo_jogo_declara_ausencia(self) -> None:
        """None é diferente de "apagado" — a interface admite em vez de
        inventar um número que ninguém escreveu."""
        ctl, _nodes, _aut = _backend(MAC_1)

        (entrada,) = ctl.describe_controllers()

        assert entrada["player_leds_game"] is None
        assert entrada["lightbar_game"] is None
        assert entrada["game_output_retido"] == []

    def test_a_camada_de_um_controle_nao_vaza_para_o_outro(self) -> None:
        ctl, _nodes, aut = _backend(MAC_1, MAC_2)
        aut["valor"] = "game"
        ctl.set_game_output_for(MAC_2, player_leds=P4)

        primeiro, segundo = ctl.describe_controllers()

        assert primeiro["player_leds_game"] is None
        assert segundo["player_leds_game"] == list(P4)


# --- fiação: report do jogo -> vpad -> sinks reais -> backend -> hardware -----


class _FakeFd:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.reads: list[bytes] = []


@pytest.fixture()
def fake_uhid(monkeypatch: pytest.MonkeyPatch) -> _FakeFd:
    """fd de /dev/uhid falso — mesma técnica de `test_uhid_replica.py`."""
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


def _blueprint() -> dict[str, Any]:
    """Blueprint mínimo aceito pelo `start()` (mesmo de `test_uhid_replica`).

    A feature 0x09 é obrigatória: é dela que sai o MAC que o vpad publica.
    """
    return {
        "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
        "features": {
            0x05: bytes([0x05]) + bytes(40),
            0x09: bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13),
            0x20: bytes([0x20]) + bytes(63),
        },
    }


def _evento(tipo: int) -> bytes:
    return struct.pack("<I", tipo) + bytes(8)


def _output_event(report: bytes) -> bytes:
    event = struct.pack("<I", UHID_OUTPUT)
    event += report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
    event += struct.pack("<HB", len(report), 1)
    return event


def _report_do_jogo(
    *, player_mask: int | None = None, rgb: tuple[int, int, int] | None = None
) -> bytes:
    """Report 0x02 do jogo (layout do `dualsense_output_report_common`)."""
    body = bytearray(47)
    flag1 = 0
    if player_mask is not None:
        flag1 |= 0x10  # PLAYER_INDICATOR_CONTROL_ENABLE
        body[43] = player_mask
    if rgb is not None:
        flag1 |= 0x04  # LIGHTBAR_CONTROL_ENABLE
        body[44:47] = bytes(rgb)
    body[1] = flag1
    return bytes([0x02]) + bytes(body)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _vpad_em_sessao(fake: _FakeFd, **kwargs: Any) -> tuple[UhidDualSense, _Clock]:
    clock = _Clock()
    pad = UhidDualSense(
        player=1,
        blueprint=_blueprint(),
        time_fn=clock,
        sleep_fn=lambda _s: None,
        **kwargs,
    )
    assert pad.start() is True
    fake.reads.append(_evento(UHID_START))
    fake.reads.append(_evento(UHID_OPEN))
    pad.pump_ff()
    clock.t = _GAME_REPLICA_GRACE_S + 0.5
    fake.writes.clear()
    return pad, clock


#: Máscara que o jogo escreve para "jogador 4" no report 0x02 (bits 0..4).
_MASCARA_P4 = sum(1 << i for i, aceso in enumerate(P4) if aceso)


class TestFiacaoDoJogoAteOFisico:
    """Entra pelo laço de verdade: `pump_ff()` é o que o poll loop chama.

    Nenhum método privado do backend é chamado aqui — o report do jogo entra
    pelo fd do vpad e a asserção é sobre a escrita no nó sysfs do controle
    FÍSICO. É o único formato de teste que teria enxergado este defeito: as
    peças isoladas (parser, sink, backend) estavam todas corretas.
    """

    def _monta(
        self, fake: _FakeFd
    ) -> tuple[UhidDualSense, bp.PyDualSenseController, _FakeNode, dict[str, Any]]:
        from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod

        ctl, nodes, aut = _backend(MAC_1)
        daemon = SimpleNamespace(controller=ctl)
        sinks = gp_mod.make_primary_replica_sinks(daemon)
        pad, _clock = _vpad_em_sessao(fake, **sinks)
        return pad, ctl, nodes[MAC_1], aut

    def test_o_numero_do_jogo_chega_ao_controle_sob_autoridade_daemon(
        self, fake_uhid: _FakeFd
    ) -> None:
        """O teste que resume a sprint. Falha-sem: com o número dentro do
        gate, este report do jogo é RETIDO e o físico nunca é escrito —
        exatamente a medição de 21:18 de 25/07."""
        pad, ctl, node, aut = self._monta(fake_uhid)
        assert aut["valor"] == "daemon"
        fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=_MASCARA_P4)))

        pad.pump_ff()

        assert node.player_calls == [P4]
        assert ctl._game_output_by_uniq[UNIQ_1].player_leds == P4

    def test_a_cor_do_jogo_continua_retida_sob_autoridade_daemon(
        self, fake_uhid: _FakeFd
    ) -> None:
        """A mesma fiação, na categoria que a política protege: a cor do
        escritor sem jogo não chega ao hardware."""
        pad, ctl, node, _aut = self._monta(fake_uhid)
        fake_uhid.reads.append(_output_event(_report_do_jogo(rgb=(0, 255, 0))))

        pad.pump_ff()

        assert node.rgb_calls == []
        assert ctl._retained_game_outputs[UNIQ_1] == {"led": (0, 255, 0)}

    def test_o_journal_distingue_pedido_de_escrita(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Os dois eventos que faltavam para datar "o jogo pediu" contra "o
        controle recebeu" sem inferir nada do padrão aceso."""
        pad, _ctl, _node, _aut = self._monta(fake_uhid)
        fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=_MASCARA_P4)))

        with structlog.testing.capture_logs() as captured:
            pad.pump_ff()

        (ativa,) = _eventos(captured, "uhid_replica_ativa")
        assert ativa["categoria"] == "player_leds"
        assert ativa["estagio"] == "entregue_ao_sink"
        (aplicado,) = _eventos(captured, "game_output_aplicado")
        assert aplicado["campos"] == ["player_leds"]


class TestUhidReplicaAtivaNaoMente:
    def test_sem_sink_nao_ha_replica_ativa(self, fake_uhid: _FakeFd) -> None:
        """Falha-sem: emitido no topo do `_forward_replica`, o log saía
        anunciando "ativa" com o sink ausente — nada chegava a lugar nenhum."""
        pad, _clock = _vpad_em_sessao(fake_uhid)  # nenhum sink injetado
        fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=_MASCARA_P4)))

        with structlog.testing.capture_logs() as captured:
            pad.pump_ff()

        assert _eventos(captured, "uhid_replica_ativa") == []
        assert pad.player_led_replicas == 0

    def test_sink_que_levanta_nao_gera_replica_ativa(
        self, fake_uhid: _FakeFd
    ) -> None:
        def _explode(_bits: Any) -> None:
            raise OSError("hidraw sumiu")

        pad, _clock = _vpad_em_sessao(fake_uhid, player_led_sink=_explode)
        fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=_MASCARA_P4)))

        with structlog.testing.capture_logs() as captured:
            pad.pump_ff()

        assert _eventos(captured, "uhid_replica_ativa") == []
        assert len(_eventos(captured, "uhid_replica_sink_failed")) == 1

    def test_com_sink_a_linha_sai_uma_vez_por_categoria(
        self, fake_uhid: _FakeFd
    ) -> None:
        recebidos: list[tuple[bool, ...]] = []
        pad, clock = _vpad_em_sessao(
            fake_uhid, player_led_sink=lambda bits: recebidos.append(tuple(bits))
        )
        fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=_MASCARA_P4)))

        with structlog.testing.capture_logs() as captured:
            pad.pump_ff()
            clock.t += 60.0
            fake_uhid.reads.append(_output_event(_report_do_jogo(player_mask=0x01)))
            pad.pump_ff()

        assert len(recebidos) == 2
        assert len(_eventos(captured, "uhid_replica_ativa")) == 1


# --- entrega 4: a evidência do sinal de jogo também SEM transição ------------


class _AuthorityController:
    """FakeController + os pontos de contato do NUMA-01/02/03."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.testing import FakeController

        self._fake = FakeController(transport="usb")
        self.defend_calls = 0
        self.replay_calls = 0

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._fake, nome)

    def set_game_authority_provider(self, fn: Any) -> None:
        self.provider = fn

    def defend_display(self) -> None:
        self.defend_calls += 1

    def replay_retained_game_outputs(self) -> None:
        self.replay_calls += 1


def _daemon_com_sinal() -> Any:
    from concurrent.futures import ThreadPoolExecutor

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig

    daemon = Daemon(
        controller=_AuthorityController(),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    daemon._wire_game_signal()
    return daemon


class TestTelemetriaDaEvidenciaDoSinal:
    """Sem isto, uma queda de autoridade no meio da partida só aparecia pelo
    SINTOMA — sem hora e sem a evidência ao lado. Era o que impedia datar a
    queda seguinte em vez de descobri-la pelo número piscando."""

    async def test_a_evidencia_sai_na_transicao(self) -> None:
        daemon = _daemon_com_sinal()
        daemon.store.set_window_detect_backend("xlib", healthy=True)

        with structlog.testing.capture_logs() as captured:
            await daemon._sync_game_signal()

        (evento,) = _eventos(captured, "game_signal_evidencia")
        assert evento["autoridade"] == "daemon"
        assert evento["motivo"] == "transicao"
        assert evento["janela_saudavel"] is True

    async def test_a_evidencia_sai_de_novo_quando_muda_sem_transicao(self) -> None:
        """A autoridade tem histerese de 30 s: a evidência pode mudar sem a
        autoridade mudar, e era justamente essa janela que ficava invisível."""
        daemon = _daemon_com_sinal()
        daemon.store.set_window_detect_backend("xlib", healthy=True)
        await daemon._sync_game_signal()
        anterior = daemon.display_authority

        # Janela de DESKTOP: a evidência muda (a classe deixa de ser
        # desconhecida) e a autoridade continua 'daemon'.
        daemon.store.record_window_detect_read("xlib", "org.mozilla.firefox")
        with structlog.testing.capture_logs() as captured:
            await daemon._sync_game_signal()

        assert daemon.display_authority == anterior, (
            "o cenário exige que a autoridade NÃO mude — senão o teste vira "
            "outro teste de transição"
        )
        (evento,) = _eventos(captured, "game_signal_evidencia")
        assert evento["motivo"] == "mudanca"
        assert evento["janela_classe"] == "org.mozilla.firefox"

    async def test_tique_identico_nao_floda_o_journal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O tique é de ~2 s: registrar tudo seria o laço de log a 1 Hz que
        este repositório já pagou caro para matar."""
        from hefesto_dualsense4unix.daemon import lifecycle as lc_mod

        monkeypatch.setattr(lc_mod, "_GAME_SIGNAL_EVIDENCIA_HEARTBEAT_S", 3600.0)
        daemon = _daemon_com_sinal()
        daemon.store.set_window_detect_backend("xlib", healthy=True)
        await daemon._sync_game_signal()

        with structlog.testing.capture_logs() as captured:
            await daemon._sync_game_signal()
            await daemon._sync_game_signal()

        assert _eventos(captured, "game_signal_evidencia") == []

    async def test_batimento_dá_marco_temporal_com_tudo_parado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon import lifecycle as lc_mod

        monkeypatch.setattr(lc_mod, "_GAME_SIGNAL_EVIDENCIA_HEARTBEAT_S", 0.0)
        daemon = _daemon_com_sinal()
        daemon.store.set_window_detect_backend("xlib", healthy=True)
        await daemon._sync_game_signal()

        with structlog.testing.capture_logs() as captured:
            await daemon._sync_game_signal()

        (evento,) = _eventos(captured, "game_signal_evidencia")
        assert evento["motivo"] == "batimento"

    async def test_gather_quebrado_registra_a_degradacao_como_evidencia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon = _daemon_com_sinal()

        def _explode() -> dict[str, Any]:
            raise OSError("disco cheio")

        monkeypatch.setattr(daemon, "_gather_game_signal_inputs", _explode)

        with structlog.testing.capture_logs() as captured:
            await daemon._sync_game_signal()

        (evento,) = _eventos(captured, "game_signal_evidencia")
        assert evento["evidencia"] == "gather_falhou"
