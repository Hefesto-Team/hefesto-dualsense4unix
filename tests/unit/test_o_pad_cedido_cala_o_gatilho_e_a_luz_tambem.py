"""O-PAD-CEDIDO-CALA-O-GATILHO-E-A-LUZ-TAMBEM-01 — nenhuma saída do pad que cedeu.

Quando o controle de um jogador vira o primário (`ceder_ao_primario`), o aparelho
dele passa a dirigir o pad 1. A O-PAD-CEDIDO-AO-P1-NAO-FALA-COM-O-APARELHO-QUE-CEDEU-01
calou só a vibração; o gatilho, a luz, o LED de jogador, o microfone e o fim de
sessão do pad que cedeu ainda chegavam ao aparelho que agora é do P1, e o
recolhimento devolvia o LED dele ao perfil do jogador que saiu. P2 a P4, cabo e
rádio: o corte é por identidade, e o transporte não entra.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

IDENTIDADES = ("AA:BB:CC:00:00:02", "AA:BB:CC:00:00:03", "AA:BB:CC:00:00:04")
_BLOCO = bytes(11)


class _Aparelho:
    """O backend com a API por `uniq`: anota tudo o que chega a cada aparelho."""

    def __init__(self) -> None:
        self.chegou: list[tuple[str, Any]] = []
        self.primary_uniq: str | None = None

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.chegou.append(("gatilho", uniq))
        return True

    def set_game_output_for(self, uniq: str, *, led: Any = None,
                            player_leds: Any = None) -> bool:
        self.chegou.append(("luz" if led is not None else "led_de_jogador", uniq))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.chegou.append(("fim_de_sessao", uniq))
        return True


class _Leitor:
    grab_state = "held"

    def set_grab(self, _ligado: bool) -> None:
        return None

    def stop(self) -> None:
        return None


class _Barramento:
    def __init__(self, aparelho: _Aparelho) -> None:
        self.aparelho = aparelho

    def publish(self, _topico: Any, evento: dict[str, Any]) -> None:
        self.aparelho.chegou.append(("microfone", evento.get("uniq")))


def _mesa(identity: str) -> tuple[CoopManager, _Aparelho, dict[str, Any]]:
    aparelho = _Aparelho()
    daemon = SimpleNamespace(controller=aparelho, bus=_Barramento(aparelho),
                             display_authority="game")
    mgr = CoopManager(daemon)  # type: ignore[arg-type]
    mgr._players[identity] = _SecondaryPlayer(
        identity=identity, evdev_path="/dev/input/event-de-mentira",
        reader=_Leitor(), player_index=1)  # type: ignore[arg-type]
    return mgr, aparelho, mgr._make_player_replica_sinks(identity)


def _tudo(ralos: dict[str, Any]) -> None:
    ralos["trigger_sink"]("left", _BLOCO)
    ralos["lightbar_sink"](10, 20, 30)
    ralos["player_led_sink"]((False, True, False, False, False))
    ralos["mic_led_sink"](1)
    ralos["mic_mute_sink"](True)
    ralos["session_end_sink"]()


@pytest.fixture(autouse=True)
def _calado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(coop_mod.INTERRUPTOR_DO_RECOLHIMENTO, raising=False)


@pytest.mark.parametrize("identity", IDENTIDADES)
def test_o_jogador_que_nao_cedeu_fala_com_o_aparelho_dele(identity: str) -> None:
    _mgr, aparelho, ralos = _mesa(identity)
    _tudo(ralos)
    canais = {canal for canal, uniq in aparelho.chegou}
    assert canais == {"gatilho", "luz", "led_de_jogador", "microfone", "fim_de_sessao"}


@pytest.mark.parametrize("identity", IDENTIDADES)
def test_o_pad_cedido_nao_chega_ao_aparelho_que_agora_e_do_p1(identity: str) -> None:
    mgr, aparelho, ralos = _mesa(identity)
    mgr.ceder_ao_primario(None, identity)
    _tudo(ralos)
    assert aparelho.chegou == []


@pytest.mark.parametrize("identity", IDENTIDADES)
def test_o_recolhimento_nao_toca_o_led_nem_fecha_a_sessao_do_p1(
    identity: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr, aparelho, ralos = _mesa(identity)
    devolvidos: list[str] = []
    monkeypatch.setattr(mgr, "_revert_single_player_led", devolvidos.append)
    monkeypatch.setattr(mgr, "_broker_restore_player", lambda _i: None)
    monkeypatch.setattr(mgr, "_materialize_launch_env", lambda: None)
    mgr.ceder_ao_primario(None, identity)
    mgr._teardown_player(identity)
    ralos["session_end_sink"]()
    assert devolvidos == []
    assert aparelho.chegou == []


def test_o_interruptor_com_parada_devolve_o_de_antes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(coop_mod.INTERRUPTOR_DO_RECOLHIMENTO, coop_mod.RECOLHER_COM_PARADA)
    mgr, aparelho, ralos = _mesa(IDENTIDADES[0])
    mgr.ceder_ao_primario(None, IDENTIDADES[0])
    ralos["trigger_sink"]("left", _BLOCO)
    assert aparelho.chegou == [("gatilho", IDENTIDADES[0])]
