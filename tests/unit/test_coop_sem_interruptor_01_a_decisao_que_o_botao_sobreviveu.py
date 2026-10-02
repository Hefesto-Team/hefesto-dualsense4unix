"""COOP-SEM-INTERRUPTOR-01 (06/08/2026) — o co-op deixa de ser uma opção."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import (
    COOP_SEMPRE_LIGADO_MOTIVO,
    IpcHandlersMixin,
)


class _Handlers(IpcHandlersMixin):
    """Só a superfície que os dois handlers de co-op tocam: `self.daemon`."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon


class _CoopFalso:
    """`CoopManager` dublê — conta os ciclos forçados sem criar uinput nenhum."""

    def __init__(self, players: int = 2, *, active: bool = True) -> None:
        self._players = players
        self._active = active
        self.syncs: list[bool] = []
        self.disables = 0

    def sync(self, *, force: bool = False, origem: str | None = None) -> None:
        self.syncs.append(force)

    def disable(self) -> None:
        self.disables += 1

    def player_count(self) -> int:
        return self._players

    def should_be_active(self) -> bool:
        return self._active


def _daemon(coop: _CoopFalso, *, enabled: bool = True) -> Any:
    """Daemon dublê com o `set_coop_enabled` REAL espionado."""
    chamadas: list[bool] = []

    def _set_coop_enabled(valor: bool, *, origin: str = "manual") -> bool:
        chamadas.append(valor)
        d.config.coop_enabled = bool(valor)
        return bool(valor)

    d = SimpleNamespace(
        config=SimpleNamespace(coop_enabled=enabled),
        _coop_manager=coop,
        set_coop_enabled=_set_coop_enabled,
        setters=chamadas,
    )
    return d


class TestCoopSetRecusaDesligar:
    @pytest.mark.asyncio
    async def test_desligar_e_recusado_em_voz_alta(self) -> None:
        coop = _CoopFalso(players=3)
        d = _daemon(coop)

        resultado = await _Handlers(d)._handle_coop_set({"enabled": False})

        assert resultado["status"] == "recusado"
        assert resultado["enabled"] is True
        assert resultado["motivo"] == COOP_SEMPRE_LIGADO_MOTIVO
        assert d.setters == [], "o daemon chegou a desligar o co-op"
        assert d.config.coop_enabled is True
        assert coop.disables == 0

    @pytest.mark.asyncio
    async def test_a_recusa_preserva_o_contrato_players(self) -> None:
        """A CLI lê ``result["players"]``. Quebrar a forma quebraria quem só"""
        resultado = await _Handlers(_daemon(_CoopFalso(players=4)))._handle_coop_set(
            {"enabled": False}
        )

        assert resultado["players"] == 4

    @pytest.mark.asyncio
    async def test_ligar_continua_ligando_e_reconciliando(self) -> None:
        """O outro lado: a recusa não pode ter matado o caminho que funciona."""
        coop = _CoopFalso(players=2)
        d = _daemon(coop, enabled=False)

        resultado = await _Handlers(d)._handle_coop_set({"enabled": True})

        assert resultado == {"status": "ok", "enabled": True, "players": 2}
        assert d.setters == [True]

    @pytest.mark.asyncio
    async def test_enabled_nao_booleano_continua_sendo_erro(self) -> None:
        with pytest.raises(ValueError, match="boolean"):
            await _Handlers(_daemon(_CoopFalso()))._handle_coop_set({"enabled": "talvez"})


class TestCoopSyncTemDono:
    """O ciclo FORÇADO precisava de dono ANTES de o botão sair."""

    @pytest.mark.asyncio
    async def test_roda_o_ciclo_cheio_e_devolve_os_jogadores(self) -> None:
        coop = _CoopFalso(players=4)

        resultado = await _Handlers(_daemon(coop))._handle_coop_sync({})

        assert coop.syncs == [True], "o ciclo não foi FORÇADO — o tick quieto não recria"
        assert resultado == {"status": "ok", "players": 4, "active": True}

    @pytest.mark.asyncio
    async def test_nao_liga_nao_desliga_e_nao_persiste(self) -> None:
        """Reconciliar não é um gesto de MODO."""
        coop = _CoopFalso()
        d = _daemon(coop)

        await _Handlers(d)._handle_coop_sync({})

        assert d.setters == [], "o reconciliador chamou `set_coop_enabled`"
        assert coop.disables == 0

    @pytest.mark.asyncio
    async def test_com_o_coop_suspenso_reconciliar_nao_ressuscita_nada(self) -> None:
        """Dentro da exceção de Steam Input o gate está fechado (`active=False`)."""
        coop = _CoopFalso(players=1, active=False)

        resultado = await _Handlers(_daemon(coop))._handle_coop_sync({})

        assert resultado["active"] is False
        assert resultado["players"] == 1

    @pytest.mark.asyncio
    async def test_sem_daemon_falha_com_mensagem(self) -> None:
        with pytest.raises(ValueError, match="daemon não disponível"):
            await _Handlers(None)._handle_coop_sync({})


class TestCliCoopOff:
    def test_off_explica_e_nao_desliga(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from typer.testing import CliRunner

        import hefesto_dualsense4unix.app.ipc_bridge as bridge
        from hefesto_dualsense4unix.cli.cmd_coop import app as coop_app

        chamadas: list[str] = []

        def _bomba(method: str, *_a: Any, **_k: Any) -> Any:
            chamadas.append(method)
            raise AssertionError(f"o `coop off` falou com o daemon: {method}")

        monkeypatch.setattr(bridge, "_run_call", _bomba)

        resultado = CliRunner().invoke(coop_app, ["off"])

        assert chamadas == []
        assert resultado.exit_code == 2, (
            "um `0` silencioso faria um script achar que desligou o co-op"
        )
        assert "não desliga mais" in resultado.stdout
        assert "cada controle conectado é um jogador" in resultado.stdout
        assert "desconectado" in resultado.stdout

    def test_on_continua_falando_com_o_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        import hefesto_dualsense4unix.app.ipc_bridge as bridge
        from hefesto_dualsense4unix.cli.cmd_coop import app as coop_app

        chamadas: list[tuple[str, dict[str, Any] | None]] = []

        def _fake(
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float | None = None,
        ) -> Any:
            chamadas.append((method, params))
            return {"status": "ok", "enabled": True, "players": 3}

        monkeypatch.setattr(bridge, "_run_call", _fake)

        resultado = CliRunner().invoke(coop_app, ["on"])

        assert resultado.exit_code == 0
        assert chamadas == [("coop.set", {"enabled": True})]
        assert "3" in resultado.stdout
