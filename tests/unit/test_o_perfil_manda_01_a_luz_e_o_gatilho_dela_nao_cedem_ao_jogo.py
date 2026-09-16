"""PERFIL-MANDA-01 — o que ela escolheu para o controle não cede ao jogo.

A QUEIXA, palavra dela em 16/09/2026 com o Sackboy aberto: *"pq jogos tipo
sackboy seguem não aplicando as configs setadas na interface?"* — e, depois de
medido: *"meu perfil manda"*.

O QUE O JOURNAL DELA MOSTROU, e é o contrário do que a queixa sugeria: o perfil
ENTROU inteiro. Às 00:18:34 o `launch_perfil_ativado` trouxe `secoes={'led':
'aplicado', 'trigger': 'aplicado', …}` e a cor de cada controle chegou ao nó
(`(255,255,0)` e `(0,255,128)`). Dezenove segundos depois, o
`game_output_replicado autoridade=game` trocou as duas pela paleta de jogador do
SDL — `(0,64,0)` e `(32,0,32)`, os mesmos 0x40/0x20 que a LIGHTBAR-NA-STEAM-01
mediu — e às 00:20:26 o `uhid_replica_ativa categoria=trigger_left/right` trocou
os gatilhos. Trinta minutos depois os nós estavam em `(0,0,64)` e `(64,0,0)`.

Não era a trava manual (essa saiu em 14/09 e o log prova que nada foi ignorado):
era a camada GAME sendo o TOPO do merge, por desenho, desde a REPLICA-03.

A REGRA: campo com DONO declarado para aquele controle — `perfil` ou `usuaria`,
o carimbo do R-20 — é recusado ao jogo na ENTRADA e removido da camada GAME no
MERGE. O que não tem dono (o broadcast global, a cor automática do número)
continua cedendo: um perfil que nunca escolheu cor não pode APAGAR a barra
dentro do jogo, e quem nunca configurou nada não perde a luz que o jogo pinta.

É o §I.4 da LIGHTBAR-NA-STEAM-01 — escrito em 13/09, adiado com a condição
*"só se a telemetria do passo 2 mostrar a paleta chegando já sob `game`"*. A
telemetria mostrou.

AS MORDIDAS: arrancar a peneira da entrada devolve a cor do jogo ao nó sysfs;
arrancar a do merge devolve a cor do jogo ao resolve (e com ela ao reassert e ao
`0x31` do gatilho da cor, que é a única rota que chega ao plástico pelo rádio).
As duas foram feitas, uma de cada vez, e as duas reprovaram.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import structlog
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"

#: O que ELA escolheu para este controle — a cor do perfil do Sackboy.
COR_DELA = (255, 255, 0)
PADRAO_DELA = (True, False, False, False, False)

#: O que o JOGO pinta: a paleta de jogador do SDL, a 0x40.
COR_DO_JOGO = (0, 64, 0)
PADRAO_DO_JOGO = (True, False, True, False, True)

#: Os onze bytes (modo + 10 parâmetros) de um trigger effect do jogo.
BLOCO_DO_JOGO = bytes([0x26, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


class _NoDeLed:
    """Nó sysfs falso — grava as chamadas, nunca toca o filesystem."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return None


def _handle() -> SimpleNamespace:
    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _controle(
    *,
    campos_dela: dict[str, Any] | None = None,
    autoridade: str = "game",
) -> tuple[bp.PyDualSenseController, _NoDeLed, SimpleNamespace]:
    """Controle com o jogo no comando e os campos DELA já carimbados.

    O carimbo é o que distingue esta régua das irmãs da REPLICA-03, que montam
    `_desired_by_uniq` sem dono nenhum: lá o jogo vence porque ninguém
    reivindicou o campo, e isso continua verdade.
    """
    ctl = bp.PyDualSenseController()
    handle = _handle()
    no = _NoDeLed()
    ctl._handles = {MAC_1: handle}
    ctl._sysfs = {MAC_1: no}
    ctl.set_game_authority_provider(lambda: autoridade)
    if campos_dela:
        ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(**campos_dela)
        ctl._desired_owner_by_uniq[UNIQ_1] = dict.fromkeys(
            campos_dela, bp._LAYER_PROFILE
        )
    return ctl, no, handle


def _eventos(registros: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == nome]


class TestALuzDelaNaoCede:
    def test_a_cor_do_perfil_nao_vira_a_cor_do_jogo(self) -> None:
        """A MORDIDA: sem a peneira, o merge responde a cor do SDL."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        assert ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO) is True

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA
        assert COR_DO_JOGO not in no.rgb_calls
        assert UNIQ_1 not in ctl._game_output_by_uniq

    def test_o_recusado_nao_fica_retido_para_entrar_depois(self) -> None:
        """Recusa não é retenção: o valor não pode voltar pelo replay."""
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        assert ctl._retained_game_outputs == {}

    def test_o_numero_do_jogador_dela_nao_cede(self) -> None:
        ctl, no, _ = _controle(campos_dela={"player_leds": PADRAO_DELA})

        ctl.set_game_output_for(MAC_1, player_leds=PADRAO_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == PADRAO_DELA
        assert PADRAO_DO_JOGO not in no.player_calls

    def test_a_recusa_dispara_a_defesa_que_repinta_o_perfil(self) -> None:
        """O aparelho não se corrige sozinho: o jogo pode ter pintado antes."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        assert no.rgb_calls == [COR_DELA]


class TestOQueNaoEDelaContinuaSendoDoJogo:
    def test_sem_dono_o_jogo_continua_vencendo(self) -> None:
        """REPLICA-03 intacta: quem não configurou nada não perde a luz."""
        ctl, no, _ = _controle()
        ctl._desired_default.led = (9, 9, 9)

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO
        assert no.rgb_calls == [COR_DO_JOGO]

    def test_o_valor_sem_carimbo_nao_defende(self) -> None:
        """Override por-uniq SEM dono é a camada de compatibilidade das irmãs:
        o jogo vence, e é o que impede esta cura de mudar teste alheio por
        baixo do pano."""
        ctl, _no, _ = _controle()
        ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(led=COR_DELA)

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO

    def test_a_defesa_e_por_campo_o_resto_passa(self) -> None:
        """Ela escolheu a cor e não o número: o número continua sendo do jogo."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(
            MAC_1, led=COR_DO_JOGO, player_leds=PADRAO_DO_JOGO
        )

        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == COR_DELA
        assert resolvido.player_leds == PADRAO_DO_JOGO
        assert no.player_calls == [PADRAO_DO_JOGO]
        assert COR_DO_JOGO not in no.rgb_calls

    def test_a_camada_do_jogo_guarda_so_o_que_passou(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(
            MAC_1, led=COR_DO_JOGO, player_leds=PADRAO_DO_JOGO
        )

        camada = ctl._game_output_by_uniq[UNIQ_1]
        assert camada.led is None
        assert camada.player_leds == PADRAO_DO_JOGO


class TestOGatilhoDelaNaoCede:
    def test_o_lado_que_ela_escolheu_recusa_o_bloco_do_jogo(self) -> None:
        efeito = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
        ctl, _no, handle = _controle(campos_dela={"trigger_right": efeito})

        assert ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO) is True

        assert handle._raw_trigger_right is None
        assert UNIQ_1 not in ctl._game_triggers_by_uniq

    def test_o_lado_sem_dono_continua_do_jogo(self) -> None:
        """A recusa é POR LADO: um perfil que só escolheu o L2 não cala o R2."""
        efeito = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
        ctl, _no, handle = _controle(campos_dela={"trigger_left": efeito})

        assert ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO) is True

        assert handle._raw_trigger_right == BLOCO_DO_JOGO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": BLOCO_DO_JOGO}

    def test_o_recusado_nao_fica_registrado_para_o_hotplug(self) -> None:
        """Quem está em `_game_triggers_by_uniq` é re-pendurado na reconexão:
        um bloco recusado que ficasse lá voltaria ao controle no replug."""
        efeito = bp.TriggerEffect(mode=1, forces=(6, 0, 0, 0, 0, 0, 0))
        ctl, _no, _ = _controle(campos_dela={"trigger_left": efeito})

        ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)

        assert ctl._game_triggers_by_uniq.get(UNIQ_1, {}) == {}


class TestOGestoDelaNoMeioDoJogo:
    """A ordem inversa, e é a que ela vive: o jogo pinta ANTES do carimbo.

    Ela abre a interface com o jogo rodando e clica. A camada GAME já existe e
    o bloco cru já está pendurado — a peneira da ENTRADA não alcança nada disso,
    porque a escrita do jogo já aconteceu. Quem cura aqui é a peneira do MERGE
    (a luz) e o solta-o-bloco do `_stamp_owner_locked` (o gatilho).
    """

    def test_a_cor_que_ela_escolhe_agora_vence_a_camada_do_jogo(self) -> None:
        """A MORDIDA da peneira do MERGE: sem ela, o resolve devolve a do jogo —
        e com o resolve vão o reassert e o `0x31` do gatilho da cor, que é a
        única rota que chega ao plástico pelo rádio."""
        ctl, _no, _ = _controle()
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        assert ctl._game_output_by_uniq[UNIQ_1].led == COR_DO_JOGO

        # O gesto dela: o campo ganha valor e dono, como no `led.set` da aba.
        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(led=COR_DELA)
            ctl._stamp_owner_locked(UNIQ_1, ("led",), bp._LAYER_USER)
            resolvido = ctl._merged_desired_for_key(MAC_1)

        assert resolvido.led == COR_DELA

    def test_o_reassert_repinta_a_cor_dela_e_nao_a_do_jogo(self) -> None:
        ctl, no, _ = _controle()
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(led=COR_DELA)
            ctl._stamp_owner_locked(UNIQ_1, ("led",), bp._LAYER_USER)
        no.rgb_calls.clear()

        ctl.reassert_resolved_outputs()

        assert no.rgb_calls == [COR_DELA]

    def test_o_gatilho_dela_solta_o_bloco_cru_do_jogo(self) -> None:
        """`_build_common` dá precedência ao bloco cru: sem soltá-lo, o efeito
        dela é gravado no handle e NÃO sai no fio."""
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)
        assert handle._raw_trigger_right == BLOCO_DO_JOGO

        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(
                trigger_right=bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
            )
            ctl._stamp_owner_locked(UNIQ_1, ("trigger_right",), bp._LAYER_USER)

        assert handle._raw_trigger_right is None
        assert ctl._game_triggers_by_uniq.get(UNIQ_1, {}) == {}

    def test_o_outro_lado_do_jogo_fica_de_pe(self) -> None:
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(
                trigger_left=bp.TriggerEffect(mode=1, forces=(6, 0, 0, 0, 0, 0, 0))
            )
            ctl._stamp_owner_locked(UNIQ_1, ("trigger_left",), bp._LAYER_USER)

        assert handle._raw_trigger_left is None
        assert handle._raw_trigger_right == BLOCO_DO_JOGO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": BLOCO_DO_JOGO}


class TestOJournalDizOQueFoiDefendido:
    def test_a_recusa_da_luz_diz_a_cor_e_a_autoridade(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        ditos = _eventos(registros, "game_output_recusado_o_perfil_manda")
        assert len(ditos) == 1
        assert ditos[0]["campos"] == ["led"]
        assert ditos[0]["cor"] == COR_DO_JOGO
        assert ditos[0]["autoridade"] == "game"

    def test_a_recusa_do_gatilho_diz_o_lado(self) -> None:
        efeito = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
        ctl, _no, _ = _controle(campos_dela={"trigger_right": efeito})

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        ditos = _eventos(registros, "game_trigger_recusado_o_perfil_manda")
        assert len(ditos) == 1
        assert ditos[0]["lado"] == "right"

    def test_o_journal_nao_vira_tapete(self) -> None:
        """Um jogo escreve a dezenas de Hz: 1x por categoria por sessão."""
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})

        with structlog.testing.capture_logs() as registros:
            for _ in range(20):
                ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        assert len(_eventos(registros, "game_output_recusado_o_perfil_manda")) == 1

    def test_a_sessao_seguinte_volta_a_dizer(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        ctl.end_game_session_for(MAC_1)

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        assert len(_eventos(registros, "game_output_recusado_o_perfil_manda")) == 1
