"""A borda do sinal de jogo arma a cor (o ensaio de jogo sem régua, item 3, 31/10/2026).

`GameSignal.na_borda` é a borda única da troca de autoridade: arma o gatilho da cor com o
motivo `game_signal:<anterior>-><novo>` e depois cuida das saídas retidas (`defend_display`
quando a autoridade volta ao daemon, `replay_retained_game_outputs` quando sai dele). Até
31/10 só as saídas tinham régua, e arrancar o passo da cor não reprovava nada.

O daemon aqui é de mentira só no aparelho: o controle anota as saídas e o gatilho da cor é
o de verdade (`connection.armar_gatilho_da_cor_por_evento`, com o registro de gatilhos do
próprio daemon), lido pelo diário `gatilho_armado`. O tique e o encerramento são os do
`Daemon` de verdade, chamados sobre esse daemon; o veredito cru do `classify` é dado pela
régua.

MORDIDA: arranque o `_sem_derrubar_o_tique("cor", cor)` de `na_borda` e os testes da cor
reprovam.
"""
from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import structlog.testing

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import game_signal as gs
from hefesto_dualsense4unix.daemon.subsystems.game_signal import HYSTERESIS_SEC, GameSignal

NOME_DA_COR = connection.NOME_DO_GATILHO_DA_LIGHTBAR


class _ControleDeMentira:
    def __init__(self) -> None:
        self.saidas: list[str] = []

    def defend_display(self) -> None:
        self.saidas.append("defend_display")

    def replay_retained_game_outputs(self) -> None:
        self.saidas.append("replay_retained_game_outputs")


class _DaemonDeMentira:
    def __init__(self, sinal: GameSignal) -> None:
        self.controller = _ControleDeMentira()
        self._game_signal = sinal
        self._pad_travado_pelo_lancamento: Any = None
        self._appid_da_evidencia: int | None = None
        self.veredito: str = "unknown"
        self.sessao_aberta = True
        self.falha: Exception | None = None

    def _gather_game_signal_inputs(self) -> dict[str, Any]:
        if self.falha is not None:
            raise self.falha
        return {"session_open": self.sessao_aberta}

    async def _run_blocking(self, leitura: Any) -> Any:
        return leitura()


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _as_cores(diario: list[dict[str, Any]]) -> list[str]:
    return [
        str(linha.get("evento"))
        for linha in diario
        if linha.get("event") == "gatilho_armado" and linha.get("nome") == NOME_DA_COR
    ]


def _montar(monkeypatch: pytest.MonkeyPatch) -> tuple[_DaemonDeMentira, _Relogio]:
    relogio = _Relogio()
    d = _DaemonDeMentira(GameSignal(time_fn=relogio))
    monkeypatch.setattr(gs, "classify", lambda **_entradas: d.veredito)
    return d, relogio


def _tique(d: _DaemonDeMentira) -> list[str]:
    with structlog.testing.capture_logs() as diario:
        asyncio.run(Daemon._sync_game_signal(cast(Any, d)))
    return _as_cores(diario)


@pytest.mark.parametrize(
    ("anterior", "novo", "saidas"),
    [
        ("daemon", "game", ["replay_retained_game_outputs"]),
        ("game", "daemon", ["defend_display"]),
        ("game", "unknown", []),
        ("unknown", "daemon", ["defend_display"]),
    ],
)
def test_cada_borda_arma_a_cor_uma_vez_com_o_proprio_motivo(
    anterior: str, novo: str, saidas: list[str],
) -> None:
    d = _DaemonDeMentira(GameSignal())
    with structlog.testing.capture_logs() as diario:
        d._game_signal.na_borda(d, anterior, novo)
    assert _as_cores(diario) == [f"game_signal:{anterior}->{novo}"]
    assert d.controller.saidas == saidas


def test_o_tique_arma_a_cor_uma_vez_por_troca_e_nenhuma_sem_troca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d, relogio = _montar(monkeypatch)

    d.veredito = "game"
    assert _tique(d) == ["game_signal:unknown->game"]
    assert _tique(d) == []

    d.veredito = "daemon"
    assert _tique(d) == []
    relogio.agora += HYSTERESIS_SEC + 1
    assert _tique(d) == ["game_signal:game->daemon"]

    d.veredito = "game"
    assert _tique(d) == ["game_signal:daemon->game"]

    d.falha = OSError("varredura caiu")
    assert _tique(d) == ["game_signal:game->unknown"]
    assert _tique(d) == []
    assert d.controller.saidas == ["defend_display", "replay_retained_game_outputs"]


def test_o_encerramento_pelo_lancamento_arma_a_cor_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d, _relogio = _montar(monkeypatch)
    d.veredito = "game"
    _tique(d)
    d.controller.saidas.clear()

    with structlog.testing.capture_logs() as diario:
        assert Daemon.encerrar_a_autoridade_do_jogo(cast(Any, d), "daemon_outro_lancamento")
        assert not Daemon.encerrar_a_autoridade_do_jogo(cast(Any, d), "daemon_outro_lancamento")
    assert _as_cores(diario) == ["game_signal:game->daemon"]
    assert d.controller.saidas == ["defend_display"]


@pytest.mark.parametrize(
    ("anterior", "novo", "saidas"),
    [
        ("game", "daemon", ["defend_display"]),
        ("daemon", "game", ["replay_retained_game_outputs"]),
    ],
)
def test_a_cor_que_levanta_nao_impede_as_saidas(
    monkeypatch: pytest.MonkeyPatch, anterior: str, novo: str, saidas: list[str],
) -> None:
    def _cor_que_cai(_daemon: Any, _evento: str) -> None:
        raise RuntimeError("lightbar caiu")

    monkeypatch.setattr(connection, "armar_gatilho_da_cor_por_evento", _cor_que_cai)
    d = _DaemonDeMentira(GameSignal())
    with structlog.testing.capture_logs() as diario:
        d._game_signal.na_borda(d, anterior, novo)
    assert d.controller.saidas == saidas
    falhas = [linha for linha in diario if linha.get("event") == "game_signal_borda_falhou"]
    assert [linha.get("passo") for linha in falhas] == ["cor"]
