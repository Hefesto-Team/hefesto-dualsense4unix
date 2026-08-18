"""REPLICA-03 no backend + fiação do daemon — a posse do output pelo jogo.

O que o jogo escreve no vpad chega ao FÍSICO do jogador certo:

- camada GAME no merge do desejado (`_merged_desired_for_key`): jogo vence
  override/auto/global enquanto a sessão uhid está aberta; o reassert passa a
  reafirmar a COR DO JOGO (mata a race verde-limãoazul por construção);
- trigger effects CRUS (11 bytes do DS5EffectsState_t do SDL) embutidos
  verbatim no report do físico pelo `_build_common`;
- `end_game_session_for` (UHID_CLOSE) devolve perfil/paleta/co-op, com
  `invalidate_cache()` no nó sysfs (o jogo pode ter escrito por hidraw);
- appliers/sinks do daemon miram por MAC (P1 = primary_uniq resolvido na
  hora; co-op = identity fixa), SEM broadcast (réplica no controle errado é
  o próprio bug P1-lightbar do estudo 2026-07-18).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydualsense.enums import TriggerModes
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

MAC_1 = "AA:BB:CC:00:00:01"
MAC_2 = "AA:BB:CC:00:00:02"
UNIQ_1 = "aabbcc000001"

_BLOCO = bytes([0x21, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
_BLOCO_L = bytes([0x26, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0])


class _FakeNode:
    """Nó sysfs de LED falso — grava chamadas, nunca toca o filesystem."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []
        self.invalidated = 0

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        self.invalidated += 1


def _fake_handle() -> SimpleNamespace:
    """Handle mínimo para o caminho de triggers/game-layer (sem hardware)."""
    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _ctl_com(handle: Any, node: _FakeNode | None = None) -> bp.PyDualSenseController:
    ctl = bp.PyDualSenseController()
    ctl._handles = {MAC_1: handle}
    if node is not None:
        ctl._sysfs = {MAC_1: node}
    return ctl


class TestCamadaGameNoMerge:
    def test_game_vence_override_auto_e_default(self) -> None:
        """A camada GAME é o TOPO do merge de 4 camadas (jogo vence tudo)."""
        ctl = _ctl_com(_fake_handle(), _FakeNode())
        ctl._desired_default.led = (9, 9, 9)
        ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(led=(7, 7, 7))
        ctl.set_auto_output_provider(
            lambda _uniq: bp._DesiredOutput(led=(0, 0, 153))
        )

        assert ctl.set_game_output_for(MAC_1, led=(0, 255, 0)) is True

        assert ctl._merged_desired_for_key(MAC_1).led == (0, 255, 0)

    def test_merge_por_campo_game_parcial_herda_o_resto(self) -> None:
        """GAME só com player_leds: a cor continua vindo das camadas de baixo."""
        ctl = _ctl_com(_fake_handle(), _FakeNode())
        ctl._desired_default.led = (10, 20, 30)

        ctl.set_game_output_for(MAC_1, player_leds=(True, False, False, False, True))

        merged = ctl._merged_desired_for_key(MAC_1)
        assert merged.led == (10, 20, 30)
        assert merged.player_leds == (True, False, False, False, True)

    def test_escreve_no_hardware_pela_rota_sysfs(self) -> None:
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)

        ctl.set_game_output_for(
            MAC_1, led=(1, 2, 3), player_leds=(False, True, False, False, False)
        )

        assert node.rgb_calls == [(1, 2, 3)]
        assert node.player_calls == [(False, True, False, False, False)]

    def test_reassert_reafirm_a_cor_do_jogo_nao_a_paleta(self) -> None:
        """O reassert periódico (reconnect_loop) durante a sessão reafirma a
        COR DO JOGO — não recria a race verde-limãoazul internamente."""
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)
        ctl.set_auto_output_provider(
            lambda _uniq: bp._DesiredOutput(led=(0, 0, 153))
        )
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
        node.rgb_calls.clear()

        ctl.reassert_resolved_outputs()

        assert node.rgb_calls == [(0, 255, 0)]

    def test_sem_mac_devolve_false(self) -> None:
        ctl = bp.PyDualSenseController()
        assert ctl.set_game_output_for("/dev/hidraw3", led=(1, 1, 1)) is False

    def test_desconectado_fica_registrado_para_o_hotplug(self) -> None:
        ctl = bp.PyDualSenseController()

        assert ctl.set_game_output_for(MAC_1, led=(4, 4, 4)) is True

        assert ctl._game_output_by_uniq[UNIQ_1].led == (4, 4, 4)


class TestGameTriggersCrus:
    def test_pendura_o_bloco_no_handle(self) -> None:
        handle = _fake_handle()
        ctl = _ctl_com(handle)

        assert ctl.set_game_trigger_for(MAC_1, "right", _BLOCO) is True

        assert handle._raw_trigger_right == _BLOCO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": _BLOCO}

    def test_bloco_de_tamanho_errado_e_recusado(self) -> None:
        handle = _fake_handle()
        ctl = _ctl_com(handle)

        assert ctl.set_game_trigger_for(MAC_1, "right", b"\x21\x01") is False

        assert handle._raw_trigger_right is None
        assert ctl._game_triggers_by_uniq == {}

    def test_build_common_embute_o_bloco_verbatim(self) -> None:
        """common[10..20] (R) / [21..31] (L) — a rota DSTrigger só representa
        7 forças e espalharia zeros nos parâmetros 8/9/10 do efeito do jogo."""
        from pydualsense.enums import ConnectionType

        inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
        inst.leftMotor = 0
        inst.rightMotor = 0
        inst.light = DSLight()
        inst.audio = DSAudio()
        inst.triggerL = DSTrigger()
        inst.triggerR = DSTrigger()
        inst.conType = ConnectionType.USB
        inst._suppress_leds = True
        inst._rumble_active = False
        inst._rumble_stop_pending = False
        inst._bt_seq = 0
        inst._raw_trigger_right = _BLOCO
        inst._raw_trigger_left = _BLOCO_L

        report = inst.prepareReport()

        # Report USB: envelope [0]=0x02, common em [1..47] → offsets +1.
        assert bytes(report[11:22]) == _BLOCO
        assert bytes(report[22:33]) == _BLOCO_L

    def test_hotplug_rependura_o_trigger_do_jogo(self) -> None:
        """Reconexão (wake BT) no meio da sessão: a posse sobrevive ao handle
        novo — `_reapply_desired` rependura os blocos crus registrados."""
        ctl = bp.PyDualSenseController()
        ctl.set_game_trigger_for(MAC_1, "right", _BLOCO)  # desconectado: registra
        handle = _fake_handle()
        ctl._handles = {MAC_1: handle}

        ctl._reapply_desired(MAC_1, handle)

        assert handle._raw_trigger_right == _BLOCO


class TestFimDaSessao:
    def test_devolve_paleta_player_e_invalida_o_cache(self) -> None:
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)
        ctl.set_auto_output_provider(
            lambda _uniq: bp._DesiredOutput(
                led=(0, 0, 153), player_leds=(True, False, False, False, False)
            )
        )
        ctl.set_game_output_for(
            MAC_1, led=(0, 255, 0), player_leds=(False, False, True, False, False)
        )
        node.rgb_calls.clear()
        node.player_calls.clear()

        assert ctl.end_game_session_for(MAC_1) is True

        # O jogo pode ter escrito por hidraw (classe LED stale): cache fora.
        assert node.invalidated == 1
        assert node.rgb_calls == [(0, 0, 153)]
        assert node.player_calls == [(True, False, False, False, False)]
        assert ctl._game_output_by_uniq == {}

    def test_trigger_volta_ao_perfil_quando_ha_perfil(self) -> None:
        handle = _fake_handle()
        ctl = _ctl_com(handle)
        ctl._desired_default.trigger_right = TriggerEffect(
            mode=2, forces=(15, 30, 0, 0, 0, 0, 0)
        )
        ctl.set_game_trigger_for(MAC_1, "right", _BLOCO)

        ctl.end_game_session_for(MAC_1)

        assert handle._raw_trigger_right is None
        assert handle.triggerR.mode == TriggerModes(2)
        assert handle.triggerR.forces[0] == 15
        assert ctl._game_triggers_by_uniq == {}

    def test_trigger_sem_perfil_volta_a_off(self) -> None:
        """Efeito de jogo não sobrevive à sessão: sem perfil por baixo, Off."""
        handle = _fake_handle()
        ctl = _ctl_com(handle)
        ctl.set_game_trigger_for(MAC_1, "left", _BLOCO_L)
        handle.triggerL.forces[0] = 99  # sujeira que o Off precisa limpar

        ctl.end_game_session_for(MAC_1)

        assert handle._raw_trigger_left is None
        assert handle.triggerL.mode == TriggerModes.Off
        assert handle.triggerL.forces == [0] * 7

    def test_sem_posse_e_no_op(self) -> None:
        """Controle que o jogo nunca tocou: nada é reescrito no fim da sessão."""
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)
        ctl.set_auto_output_provider(
            lambda _uniq: bp._DesiredOutput(led=(0, 0, 153))
        )

        assert ctl.end_game_session_for(MAC_1) is True

        assert node.rgb_calls == []
        assert node.invalidated == 0

    def test_paleta_sem_opiniao_nao_escreve_cor(self) -> None:
        """desired.led None (sem perfil/paleta): a cor do jogo fica — melhor
        que apagar o LED de um controle aceso."""
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))
        node.rgb_calls.clear()

        ctl.end_game_session_for(MAC_1)

        assert node.rgb_calls == []
        assert node.invalidated == 1  # o cache ainda é invalidado (posse retomada)


class TestRetencaoNaoSobreviveAoClose:
    """Correção pós-auditoria da Onda N: a réplica RETIDA (NUMA-02) sob
    autoridade 'daemon' — ex.: o cliente Steam escrevendo player_leds sem
    jogo nenhum, o próprio mecanismo do incidente 14:42 — não pode
    sobreviver ao UHID_CLOSE da sessão que a escreveu. Sem a purga em
    `end_game_session_for`, o valor fica pendurado em
    `_retained_game_outputs` (dict por UNIQ, não por sessão) e vaza pelo
    `replay_retained_game_outputs()` para a PRÓXIMA sessão de jogo real
    deste controle — o "player 3 verde" acendendo antes de o jogo escrever
    qualquer coisa."""

    def test_close_purga_a_retencao_do_cliente(self) -> None:
        node = _FakeNode()
        ctl = _ctl_com(_fake_handle(), node)
        autoridade = {"valor": "daemon"}
        ctl.set_game_authority_provider(lambda: autoridade["valor"])

        # Cliente Steam escreve player_leds sob 'daemon' (sem jogo): fica
        # RETIDO, nunca chega ao físico (é o veto de drop-sem-retenção).
        assert (
            ctl.set_game_output_for(
                MAC_1, player_leds=(False, False, True, False, False)
            )
            is True
        )
        assert ctl._retained_game_outputs[UNIQ_1] == {
            "player_leds": (False, False, True, False, False)
        }
        assert node.player_calls == []

        # Cliente fecha a sessão (UHID_CLOSE) — o fantasma tem de sumir
        # JUNTO com as camadas GAME/triggers (que aqui nunca existiram).
        assert ctl.end_game_session_for(MAC_1) is True
        assert ctl._retained_game_outputs == {}

        # Minutos/horas depois, um jogo de verdade e SEM RELAÇÃO nenhuma
        # com a sessão antiga abre: a autoridade sobe e o replay da
        # abertura do gate não pode entregar o valor do cliente morto.
        autoridade["valor"] = "game"
        node.player_calls.clear()
        ctl.replay_retained_game_outputs()

        assert node.player_calls == []

    def test_close_purga_a_retencao_mesmo_com_camada_game_presente(self) -> None:
        """Caso misto: o jogo já tinha escrito (camada GAME) e, além disso,
        havia uma retenção pendurada de um episódio 'daemon' anterior — o
        CLOSE tem de zerar as duas, não só a camada GAME de sempre."""
        ctl = _ctl_com(_fake_handle(), _FakeNode())
        ctl._retained_game_outputs[UNIQ_1] = {"led": (9, 9, 9)}
        ctl.set_game_output_for(MAC_1, led=(0, 255, 0))  # sem provider: jogo vence

        ctl.end_game_session_for(MAC_1)

        assert ctl._retained_game_outputs == {}

    def test_desconectado_ainda_purga_a_retencao(self) -> None:
        """Controle sem handle (desconectado no momento do CLOSE): o early
        return por `handle is None` não pode pular a purga da retenção —
        ela já foi feita antes, sob o MESMO lock."""
        ctl = bp.PyDualSenseController()
        ctl._retained_game_outputs[UNIQ_1] = {"player_leds": (True,) * 5}

        assert ctl.end_game_session_for(MAC_1) is True

        assert ctl._retained_game_outputs == {}


class _FakeReplicaBackend:
    """Backend com a API por-uniq do REPLICA-03 — registra as chamadas."""

    def __init__(self, primary: str = MAC_1) -> None:
        self.primary_uniq: str | None = primary
        self.triggers: list[tuple[str, str, bytes]] = []
        self.outputs: list[tuple[str, Any, Any]] = []
        self.ends: list[str] = []

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.triggers.append((uniq, side, bytes(block)))
        return True

    def set_game_output_for(
        self, uniq: str, *, led: Any = None, player_leds: Any = None
    ) -> bool:
        self.outputs.append((uniq, led, player_leds))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.ends.append(uniq)
        return True


def _daemon(backend: Any | None = None) -> Any:
    return SimpleNamespace(controller=backend if backend is not None else _FakeReplicaBackend())


class TestFiacaoP1:
    def test_sinks_do_p1_miram_o_primario_resolvido_na_hora(self) -> None:
        backend = _FakeReplicaBackend()
        sinks = gp_mod.make_primary_replica_sinks(_daemon(backend))

        sinks["trigger_sink"]("right", _BLOCO)
        sinks["lightbar_sink"](1, 2, 3)
        sinks["player_led_sink"]((True, False, False, False, False))
        sinks["session_end_sink"]()

        assert backend.triggers == [(MAC_1, "right", _BLOCO)]
        assert backend.outputs == [
            (MAC_1, (1, 2, 3), None),
            (MAC_1, None, (True, False, False, False, False)),
        ]
        assert backend.ends == [MAC_1]

    def test_hotplug_muda_o_alvo_do_p1(self) -> None:
        """O MAC do primário é resolvido NA HORA de cada réplica."""
        backend = _FakeReplicaBackend()
        daemon = _daemon(backend)
        sinks = gp_mod.make_primary_replica_sinks(daemon)
        sinks["lightbar_sink"](1, 1, 1)
        backend.primary_uniq = MAC_2  # hotplug trocou o primário

        sinks["lightbar_sink"](2, 2, 2)

        assert [o[0] for o in backend.outputs] == [MAC_1, MAC_2]

    def test_close_encerra_todo_replicado_apos_troca_de_primario(self) -> None:
        """BT-hotplug: o primário CAI/TROCA no meio do jogo ANTES do CLOSE.

        A camada GAME grudou no controle que RECEBEU a réplica (A), não no
        primário do instante do CLOSE (B). O CLOSE tem de encerrar a sessão de
        TODO controle replicado — encerrar só o primário corrente vazaria a
        camada de A, que voltaria como TOPO do merge quando A reconecta (a
        writer-war de paleta que o REPLICA-03 mata). Exercita o backend REAL
        para provar que os dicionários de posse ficam VAZIOS e o merge de A já
        não traz a cor do jogo.
        """
        ctl = bp.PyDualSenseController()
        ctl._primary_key = MAC_1  # o primário é o A
        sinks = gp_mod.make_primary_replica_sinks(_daemon(ctl))

        # A recebe a cor e o gatilho do jogo enquanto é primário.
        sinks["lightbar_sink"](0, 255, 0)
        sinks["trigger_sink"]("right", _BLOCO)
        assert ctl._game_output_by_uniq[UNIQ_1].led == (0, 255, 0)
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": _BLOCO}

        # A cai no BT e o primário é promovido para B ANTES do CLOSE.
        ctl._primary_key = MAC_2
        sinks["lightbar_sink"](255, 0, 0)  # agora B recebe a cor

        sinks["session_end_sink"]()  # fim da sessão uhid do P1

        # Nenhuma posse do jogo pode sobrar (hoje o A vaza nos dois dicts).
        assert ctl._game_output_by_uniq == {}
        assert ctl._game_triggers_by_uniq == {}

        # Ao reconectar A, o merge não traz mais a camada game — paleta limpa.
        ctl._handles = {MAC_1: _fake_handle()}
        assert ctl._merged_desired_for_key(MAC_1).led is None

    def test_sem_primario_descarta_sem_broadcast(self) -> None:
        """Réplica sem alvo NUNCA vira broadcast (pintaria o jogador errado —
        o rumble faz broadcast, LED/trigger NÃO)."""
        backend = _FakeReplicaBackend(primary=MAC_1)
        backend.primary_uniq = None
        sinks = gp_mod.make_primary_replica_sinks(_daemon(backend))

        sinks["lightbar_sink"](9, 9, 9)
        sinks["trigger_sink"]("left", _BLOCO_L)
        sinks["session_end_sink"]()

        assert backend.outputs == []
        assert backend.triggers == []
        assert backend.ends == []

    def test_backend_sem_api_nao_explode(self) -> None:
        daemon = _daemon(SimpleNamespace(primary_uniq=MAC_1))
        sinks = gp_mod.make_primary_replica_sinks(daemon)

        sinks["trigger_sink"]("right", _BLOCO)  # não levanta
        sinks["lightbar_sink"](1, 2, 3)
        sinks["player_led_sink"]((True, True, True, True, True))
        sinks["session_end_sink"]()

    def test_start_gamepad_emulation_passa_os_sinks(self) -> None:
        """Contrato de fiação: o vpad do P1 nasce com os sinks de replicação."""
        fonte = Path(gp_mod.__file__).read_text(encoding="utf-8")
        assert "**make_primary_replica_sinks(daemon)" in fonte


class TestFiacaoCoop:
    def test_sinks_do_jogador_miram_o_mac_dele(self) -> None:
        backend = _FakeReplicaBackend()
        mgr = CoopManager(_daemon(backend))
        sinks = mgr._make_player_replica_sinks(MAC_2)

        sinks["trigger_sink"]("left", _BLOCO_L)
        sinks["lightbar_sink"](4, 5, 6)
        sinks["player_led_sink"]((False, True, False, False, False))
        sinks["session_end_sink"]()

        assert backend.triggers == [(MAC_2, "left", _BLOCO_L)]
        assert backend.outputs == [
            (MAC_2, (4, 5, 6), None),
            (MAC_2, None, (False, True, False, False, False)),
        ]
        assert backend.ends == [MAC_2]

    def test_identidade_sem_mac_descarta_sem_broadcast(self) -> None:
        backend = _FakeReplicaBackend()
        mgr = CoopManager(_daemon(backend))
        sinks = mgr._make_player_replica_sinks("path:/dev/input/event9")

        sinks["lightbar_sink"](1, 1, 1)
        sinks["session_end_sink"]()

        assert backend.outputs == []
        assert backend.ends == []

    def test_promote_player_passa_os_sinks(self) -> None:
        """Contrato de fiação: o vpad de cada jogador do co-op nasce com os
        sinks de replicação da identidade DELE."""
        import hefesto_dualsense4unix.daemon.subsystems.coop as coop_mod

        fonte = Path(coop_mod.__file__).read_text(encoding="utf-8")
        assert "**self._make_player_replica_sinks(player.identity)" in fonte


class TestContadoresPorVpadNoStateFull:
    """Padrão do repo para contratos de fiação do state_full (o handler
    completo exige um daemon inteiro — ver TestFiacaoNoStateFull do
    test_dedup_guard): a fonte prova que o bloco per_vpad existe e carrega
    os 5 contadores por vpad."""

    def test_state_full_publica_per_vpad_com_os_contadores(self) -> None:
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
        assert '"per_vpad": per_vpad' in fonte
        for chave in (
            "ff_play_count",
            "output_count",
            "trigger_replicas",
            "lightbar_replicas",
            "player_led_replicas",
        ):
            assert f'"{chave}"' in fonte

    def test_vpad_uhid_expoe_os_contadores(self) -> None:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        pad = UhidDualSense(player=3)
        assert pad.ff_play_count == 0
        assert pad.output_count == 0
        assert pad.trigger_replicas == 0
        assert pad.lightbar_replicas == 0
        assert pad.player_led_replicas == 0
