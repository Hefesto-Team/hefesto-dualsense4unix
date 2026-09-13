"""LIGHTBAR-NA-STEAM-01 — a paleta do cliente Steam não vira camada do jogo.

O DEFEITO, MEDIDO NO JOURNAL DELA (estudo do lote 1309, de 01/09 a 13/09): a
guarda da cor não foi desligada — ela disparou 157 vezes e escreveu 169 vezes
sem falha. O que tirava a qualidade da luz no jogo era o CONTEÚDO que ela
reafirmava. Dezesseis escritas do `gatilho_da_cor_escrito` pintaram exatamente
os pares cor e padrão da paleta de jogador do SDL, a 0x40 ou 0x20 — a última
às 05:00:16 de 13/09, no Sackboy, logo depois do sinal `daemon -> game`.

O CAMINHO: sob a autoridade 'daemon' a réplica de exibição é RETIDA
(NUMA-02). Na abertura do gate, `replay_retained_game_outputs` a entregava pelo
`set_game_output_for` — e a essa altura a autoridade já é 'game', então o
valor do CLIENTE Steam entrava na camada GAME, que é o topo do merge. O
gatilho da cor pinta o que o merge devolve.

A REGRA (sprint §D, com a regra de 12/08 escrita em
`docs/protocol/pilha-steam-input-xpad-sdl.md`): a cor que o cliente deixou no
vpad antes do jogo não vira camada do jogo. A camada GAME só recebe luz escrita
com a autoridade JÁ em 'game' ou 'unknown'. O gatilho cru não passa por
retenção e continua.

AS MORDIDAS: devolver a entrega no replay faz o merge responder (64, 0, 0) e o
padrão `-x-x-`; tirar `cor`, `players` ou `autoridade` dos logs apaga a prova
que o journal precisa para separar a paleta do SDL de pintura legítima de jogo.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import structlog
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"

#: A cor e o número do PERFIL deste controle — o que ela quer ver no plástico.
COR_DO_PERFIL = (0, 0, 255)
PADRAO_DO_PERFIL = (True, False, False, False, False)

#: Um par da paleta de jogador do SDL que o journal registrou em 07/09 e em
#: 13/09: vermelho a 0x40 com o padrão `-x-x-`.
COR_DA_PALETA = (64, 0, 0)
PADRAO_DA_PALETA = (False, True, False, True, False)

#: A pintura de um JOGO de verdade, escrita com a autoridade já em 'game'.
COR_DO_JOGO = (0, 255, 0)

_BLOCO = bytes([0x21, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


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


class _Autoridade:
    """Dublê do provider de autoridade do GameSignal: responde o que se mandar."""

    def __init__(self, valor: str) -> None:
        self.valor = valor

    def __call__(self) -> str:
        return self.valor


def _handle() -> SimpleNamespace:
    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _controle_com_perfil(
    autoridade: _Autoridade,
) -> tuple[bp.PyDualSenseController, _NoDeLed, SimpleNamespace]:
    ctl = bp.PyDualSenseController()
    handle = _handle()
    no = _NoDeLed()
    ctl._handles = {MAC_1: handle}
    ctl._sysfs = {MAC_1: no}
    ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(
        led=COR_DO_PERFIL, player_leds=PADRAO_DO_PERFIL
    )
    ctl.set_game_authority_provider(autoridade)
    return ctl, no, handle


def _eventos(registros: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == nome]


class TestAPaletaRetidaNaoVoltaComoJogo:
    def test_o_retido_sob_daemon_nao_vence_o_perfil_quando_o_jogo_abre(self) -> None:
        """A MORDIDA da §V: com a entrega de volta no replay, o merge responde
        (64, 0, 0) e `-x-x-` — a cor fosca da Steam no lugar da do perfil."""
        autoridade = _Autoridade("daemon")
        ctl, no, _ = _controle_com_perfil(autoridade)

        # O cliente Steam pinta o vpad sem jogo nenhum: fica RETIDO.
        assert (
            ctl.set_game_output_for(
                MAC_1, led=COR_DA_PALETA, player_leds=PADRAO_DA_PALETA
            )
            is True
        )
        assert ctl._retained_game_outputs[UNIQ_1] == {
            "led": COR_DA_PALETA,
            "player_leds": PADRAO_DA_PALETA,
        }
        # O dublê não é vazio: sob 'daemon' o merge já dá o perfil.
        with ctl._io_lock:
            antes = ctl._merged_desired_for_key(MAC_1)
        assert antes.led == COR_DO_PERFIL

        # O jogo abre: o sinal sobe e o lifecycle chama o replay.
        autoridade.valor = "game"
        ctl.replay_retained_game_outputs()

        with ctl._io_lock:
            depois = ctl._merged_desired_for_key(MAC_1)
        assert depois.led == COR_DO_PERFIL, (
            "a cor que o cliente Steam deixou no vpad virou camada do jogo"
        )
        assert depois.player_leds == PADRAO_DO_PERFIL, (
            "o padrão da paleta do SDL virou o número do jogador"
        )
        assert UNIQ_1 not in ctl._game_output_by_uniq
        assert ctl._retained_game_outputs == {}
        assert COR_DA_PALETA not in no.rgb_calls
        assert PADRAO_DA_PALETA not in no.player_calls

    def test_o_gatilho_da_cor_pinta_o_perfil_depois_do_replay(self) -> None:
        """O que o plástico recebe pelo rádio sai do mesmo merge: o `0x31` do
        gatilho tem de levar a cor e o número do PERFIL, não os da paleta."""
        autoridade = _Autoridade("daemon")
        ctl, _no, handle = _controle_com_perfil(autoridade)
        escritos: list[list[int]] = []
        handle.writeReport = escritos.append
        handle.conType = SimpleNamespace(name="BT")
        ctl._detect_transport = lambda _h: "bt"  # type: ignore[method-assign]
        ctl.set_game_output_for(MAC_1, led=COR_DA_PALETA, player_leds=PADRAO_DA_PALETA)
        autoridade.valor = "game"
        ctl.replay_retained_game_outputs()

        with structlog.testing.capture_logs() as registros:
            resultado = ctl.reescrever_lightbar_por_hidraw()

        assert resultado == {MAC_1: True}
        escrita = _eventos(registros, "gatilho_da_cor_escrito")
        assert len(escrita) == 1
        assert escrita[0]["cor"] == COR_DO_PERFIL
        assert escrita[0]["players"] == PADRAO_DO_PERFIL

    def test_o_jogo_que_escreve_sob_game_continua_vencendo(self) -> None:
        """Caso irmão (REPLICA-03 intacta): a cura não pode calar o jogo. Uma
        escrita com a autoridade já em 'game' é camada GAME e vai ao físico."""
        autoridade = _Autoridade("daemon")
        ctl, no, _ = _controle_com_perfil(autoridade)
        ctl.set_game_output_for(MAC_1, led=COR_DA_PALETA, player_leds=PADRAO_DA_PALETA)
        autoridade.valor = "game"
        ctl.replay_retained_game_outputs()

        assert ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO) is True

        with ctl._io_lock:
            merged = ctl._merged_desired_for_key(MAC_1)
        assert merged.led == COR_DO_JOGO
        assert merged.player_leds == PADRAO_DO_PERFIL
        assert no.rgb_calls[-1] == COR_DO_JOGO

    def test_sob_unknown_o_gate_continua_aberto(self) -> None:
        """'unknown' é o fail-safe do NUMA-02: a escrita entra na camada GAME."""
        ctl, no, _ = _controle_com_perfil(_Autoridade("unknown"))

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO
        assert no.rgb_calls == [COR_DO_JOGO]

    def test_o_duble_de_autoridade_sabe_recusar(self) -> None:
        """Sob 'daemon' a escrita não chega à camada nem ao físico: o dublê
        fecha o gate de verdade — senão as asserções acima passariam por outro
        motivo. O que o nó recebe é a DEFESA (NUMA-03) repintando o perfil."""
        ctl, no, _ = _controle_com_perfil(_Autoridade("daemon"))

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        assert COR_DO_JOGO not in no.rgb_calls
        assert no.rgb_calls == [COR_DO_PERFIL]
        assert UNIQ_1 not in ctl._game_output_by_uniq
        assert ctl._retained_game_outputs[UNIQ_1] == {"led": COR_DO_JOGO}

    def test_o_gatilho_cru_do_jogo_continua_sob_qualquer_autoridade(self) -> None:
        """A cura é da LUZ: o bloco cru de gatilho nunca passou por retenção e
        segue pendurado no handle com a autoridade em 'daemon'."""
        ctl, _no, handle = _controle_com_perfil(_Autoridade("daemon"))

        assert ctl.set_game_trigger_for(MAC_1, "right", _BLOCO) is True

        assert handle._raw_trigger_right == _BLOCO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": _BLOCO}


class TestOJournalDizOValorEAAutoridade:
    def test_o_log_de_retencao_carrega_a_cor_o_padrao_e_a_autoridade(self) -> None:
        ctl, _no, _ = _controle_com_perfil(_Autoridade("daemon"))

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(
                MAC_1, led=COR_DA_PALETA, player_leds=PADRAO_DA_PALETA
            )

        retidos = _eventos(registros, "game_output_retido_sem_jogo")
        assert len(retidos) == 1
        assert retidos[0]["uniq"] == UNIQ_1
        assert retidos[0]["cor"] == COR_DA_PALETA
        assert retidos[0]["players"] == PADRAO_DA_PALETA
        assert retidos[0]["autoridade"] == "daemon"

    def test_o_descarte_na_abertura_diz_o_que_foi_descartado(self) -> None:
        autoridade = _Autoridade("daemon")
        ctl, _no, _ = _controle_com_perfil(autoridade)
        ctl.set_game_output_for(MAC_1, led=COR_DA_PALETA, player_leds=PADRAO_DA_PALETA)
        autoridade.valor = "game"

        with structlog.testing.capture_logs() as registros:
            ctl.replay_retained_game_outputs()

        descartes = _eventos(registros, "game_output_retido_descartado_na_abertura")
        assert len(descartes) == 1
        assert descartes[0]["uniq"] == UNIQ_1
        assert descartes[0]["campos"] == ["led", "player_leds"]
        assert descartes[0]["cor"] == COR_DA_PALETA
        assert descartes[0]["players"] == PADRAO_DA_PALETA
        assert descartes[0]["autoridade"] == "game"
        assert not _eventos(registros, "game_output_replicado"), (
            "o replay voltou a entregar o retido como réplica de jogo"
        )

    def test_o_log_de_replica_carrega_a_cor_e_a_autoridade(self) -> None:
        ctl, _no, _ = _controle_com_perfil(_Autoridade("game"))

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
            ctl.set_game_output_for(MAC_1, led=(0, 200, 0))  # mesma categoria
            ctl.set_game_output_for(MAC_1, player_leds=PADRAO_DA_PALETA)

        replicas = _eventos(registros, "game_output_replicado")
        assert [r["campos"] for r in replicas] == [["led"], ["player_leds"]], (
            "1x por categoria por sessão — sem inundar o journal a cada cor"
        )
        assert replicas[0]["cor"] == COR_DO_JOGO
        assert replicas[0]["players"] is None
        assert replicas[0]["autoridade"] == "game"
        assert replicas[1]["players"] == PADRAO_DA_PALETA

    def test_a_sessao_nova_volta_a_dizer_a_primeira_replica(self) -> None:
        ctl, _no, _ = _controle_com_perfil(_Autoridade("game"))
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        ctl.end_game_session_for(MAC_1)

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        assert len(_eventos(registros, "game_output_replicado")) == 1

    def test_sem_provider_o_journal_diz_que_nao_ha_fiacao_de_autoridade(self) -> None:
        ctl = bp.PyDualSenseController()
        ctl._handles = {MAC_1: _handle()}
        ctl._sysfs = {MAC_1: _NoDeLed()}

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        replicas = _eventos(registros, "game_output_replicado")
        assert replicas[0]["autoridade"] == "sem_provider"
