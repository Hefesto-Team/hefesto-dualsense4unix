"""FEAT-STEAM-SIMPLES-01 — dois botões que escondem os dois mecanismos."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_steam_modo_simples: importa código da janela GTK")

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions
from hefesto_dualsense4unix.app.actions.daemon_actions import (
    DaemonActionsMixin,
    format_fix_safe_result,
    format_game_broken_result,
    format_steam_janela_recusa,
)


class TestFormatSteamJanelaRecusa:
    def test_ok_nao_e_recusa(self) -> None:
        assert format_steam_janela_recusa("ok") is None


    def test_nao_fechou_explica_o_porque(self) -> None:
        msg = format_steam_janela_recusa("nao_fechou")
        assert msg and "regrava o arquivo ao sair" in msg

    @pytest.mark.parametrize("torto", [None, "", "qualquer", 7])
    def test_status_desconhecido_e_recusa_honesta(self, torto: object) -> None:
        msg = format_steam_janela_recusa(torto)
        assert msg and "Pronto" not in msg


class TestFormatFixSafe:
    def test_adiado_diz_que_adiou_e_aponta_o_botao_certo(self) -> None:
        """O bug: dizia "Correções aplicadas" mesmo quando NADA foi aplicado."""
        msg = format_fix_safe_result(
            {
                "ran": 2,
                "missing": 0,
                "steam_input": (0, "[steam-input] resultado=adiado-steam-aberta\n"),
            }
        )
        assert "NÃO foi desligado" in msg
        assert "Deixar tudo pronto" in msg

    def test_aplicado_relata_o_que_mudou(self) -> None:
        """NOTA DATADA (05/08/2026, D-33): este teste exigia a frase literal"""
        msg = format_fix_safe_result(
            {
                "ran": 2,
                "missing": 0,
                "steam_input": (0, "[steam-input] resultado=aplicado\n"),
                "steam_input_jogos": ["Sackboy (appid 1599660)"],
            }
        )
        assert "Sackboy (appid 1599660)" in msg
        assert "voltou a ser entregue pelo Hefesto" in msg
        assert "sequestra" not in msg
        assert "Deixar tudo pronto" not in msg

    def test_erro_do_script_nao_vira_sucesso(self) -> None:
        msg = format_fix_safe_result(
            {"ran": 2, "missing": 0, "steam_input": (1, "[steam-input] resultado=erro\n")}
        )
        assert "NÃO mudou" in msg
        assert "erro 1" in msg

    def test_scripts_ausentes(self) -> None:
        msg = format_fix_safe_result({"ran": 0, "missing": 2, "steam_input": None})
        assert "Não encontrei os scripts" in msg

    @pytest.mark.parametrize("torto", [None, "ok", 7, []])
    def test_fora_do_contrato_e_recusa(self, torto: object) -> None:
        msg = format_fix_safe_result(torto)
        assert "Não consegui aplicar" in msg


class TestFormatGameBroken:
    def test_adicionado_diz_o_proximo_passo(self) -> None:
        msg = format_game_broken_result(status="adicionado", appid=2111190)
        assert "2111190" in msg
        assert "Feche e abra o jogo" in msg

    def test_ja_estava_nao_finge_novidade(self) -> None:
        msg = format_game_broken_result(status="ja_estava", appid=620)
        assert "já estava marcado" in msg

    def test_sem_jogo_pede_o_que_falta(self) -> None:
        msg = format_game_broken_result(status="sem_jogo")
        assert "Não descobri qual é o jogo" in msg

    def test_erro_nao_vira_sucesso(self) -> None:
        assert "Não consegui anotar" in format_game_broken_result(status="erro")

    def test_nunca_pronuncia_steam_input_nem_launch_option(self) -> None:
        for status in ("adicionado", "ja_estava", "sem_jogo", "erro"):
            msg = format_game_broken_result(status=status, appid=1)
            assert "Steam Input" not in msg
            assert "inicialização" not in msg

    def test_nao_promete_o_que_ela_mediu_ao_contrario(self) -> None:
        """NOTA DATADA — 07/08/2026: o toast dizia "o Hefesto sai da frente"."""
        for status in ("adicionado", "ja_estava"):
            msg = format_game_broken_result(status=status, appid=2111190)
            assert "sai da frente" not in msg
            assert "dobrado" in msg, "o defeito que a marca cura é o dobrado"
        adicionado = format_game_broken_result(status="adicionado", appid=2111190)
        assert "gatilhos continuam valendo" in adicionado


class _Stub(DaemonActionsMixin):
    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.diag_refreshes = 0
        self.window = None

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_storm_diag(self) -> None:  # type: ignore[override]
        self.diag_refreshes += 1


@pytest.fixture()
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        daemon_actions,
        "_get_executor",
        lambda: SimpleNamespace(submit=lambda fn: fn()),
    )
    monkeypatch.setattr(
        daemon_actions,
        "GLib",
        SimpleNamespace(idle_add=lambda fn, *args: fn(*args)),
    )


@pytest.fixture()
def slo_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    caixa: dict[str, Any] = {
        "steam": False,
        "jogo": False,
        "parou": 0,
        "reabriu": 0,
        "wrapper": {"applied": 2, "skipped": 0, "errors": 0},
        "runs": [],
        "script_rc": 0,
        "script_saida": "[steam-input] resultado=aplicado\n",
    }
    monkeypatch.setattr(slo, "steam_running", lambda: caixa["steam"])
    monkeypatch.setattr(slo, "steam_game_running", lambda: caixa["jogo"])

    def _stop() -> bool:
        caixa["parou"] += 1
        caixa["steam"] = False
        return True

    monkeypatch.setattr(slo, "stop_steam", _stop)
    monkeypatch.setattr(
        slo, "reopen_steam", lambda: caixa.__setitem__("reabriu", caixa["reabriu"] + 1)
    )
    monkeypatch.setattr(
        slo, "apply_wrapper_to_all_games", lambda: caixa["wrapper"], raising=False
    )

    def _run(args, **_kwargs):
        caixa["runs"].append(list(args))
        return SimpleNamespace(
            returncode=caixa["script_rc"], stdout=caixa["script_saida"], stderr=""
        )

    monkeypatch.setattr(
        daemon_actions,
        "subprocess",
        SimpleNamespace(run=_run, SubprocessError=Exception),
    )
    return caixa


