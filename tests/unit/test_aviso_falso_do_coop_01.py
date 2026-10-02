"""AVISO-FALSO-DO-COOP-01 (09/08/2026) — o aviso fala de CONTROLE, não de vpad."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    CoopManager,
    secundarios_fora_da_mesa,
)
from tests.unit.test_coop_nao_cai_em_silencio import (
    APPID,
    _daemon_real_com_coop,
    _DaemonDublado,
    _encerrar_vigia,
    _Handlers,
)
from tests.unit.test_coop_nao_cai_em_silencio import (
    config_em_tmp,  # noqa: F401  (fixture reexportada — pytest a resolve aqui)
)
from tests.unit.test_coop_nao_cai_em_silencio import (
    sem_disco_nem_broker,  # noqa: F401
)

P2 = "aa:bb:cc:00:00:00"
P3 = "aa:bb:cc:00:00:01"


class _WatchDublado:
    """O detector barato de mudança em /dev/input, com a resposta na mão."""

    def __init__(self, mudou: bool) -> None:
        self.mudou = mudou
        self.consultas = 0

    def poll(self) -> bool:
        self.consultas += 1
        return self.mudou


def _daemon_suspenso(sentados: tuple[str, ...]) -> Any:
    """Daemon mínimo no estado "vpads suspensos": co-op ligado, sem vpad."""
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True),
        _gamepad_device=None,
        _steam_input_coop_caidos=sentados,
        _steam_input_coop_derrubados=0,
        controller=SimpleNamespace(primary_uniq="aa:bb:cc:00:00:ff"),
    )


class TestARegraDaMesa:
    def test_com_todos_os_controles_conectados_o_numero_e_zero(self) -> None:
        """LADO A: vpad recolhido não é ninguém saindo da mesa."""
        assert secundarios_fora_da_mesa((P2, P3), {P2, P3, "aa:bb:cc:00:00:ff"}) == 0

    def test_controle_que_sumiu_de_verdade_conta(self) -> None:
        """LADO B (o CONTRAPESO): sumir com o aviso aqui seria o defeito pior."""
        assert secundarios_fora_da_mesa((P2, P3), {P2}) == 1
        assert secundarios_fora_da_mesa((P2, P3), set()) == 2

    def test_identidade_por_path_nunca_acusa_queda(self) -> None:
        """Node evdev é volátil por construção: uma re-enumeração troca"""
        assert secundarios_fora_da_mesa(("path:/dev/input/event9",), set()) == 0


@pytest.mark.usefixtures("sem_disco_nem_broker")
class TestOLadoQueCala:
    async def test_suspender_os_vpads_nao_acende_o_aviso(self) -> None:
        """A MORDIDA. Com a cura arrancada (o `_steam_input_coop_derrubados`"""
        daemon = _DaemonDublado(secundarios=2)

        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        assert gp.steam_input_coop_derrubados(daemon) == 0
        assert gp.coop_sentados_na_suspensao(daemon) == (P2, P3)

    async def test_o_tique_com_os_controles_na_mesa_mantem_o_silencio(self) -> None:
        """Medir e continuar calado é diferente de nunca medir."""
        daemon = _DaemonDublado(secundarios=2)
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        assert gp.reavaliar_coop_fora_da_mesa(daemon, {P2, P3}) == 0
        assert gp.steam_input_coop_derrubados(daemon) == 0

    async def test_o_journal_continua_contando_os_vpads_recolhidos(self) -> None:
        """A cura cala a JANELA, não o diagnóstico."""
        daemon = _DaemonDublado(secundarios=2)

        with structlog.testing.capture_logs() as registros:
            assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        queda = next(
            r
            for r in registros
            if r["event"] == "coop_derrubado_pela_excecao_steam_input"
        )
        assert queda["secundarios_derrubados"] == 2
        assert queda["log_level"] == "warning"
        assert "gamepad.steam_input.coop_derrubado" in daemon.store.contadores
        assert gp.steam_input_coop_derrubados(daemon) == 0


@pytest.mark.usefixtures("sem_disco_nem_broker")
class TestOLadoQueFala:
    async def test_controle_que_cai_durante_a_suspensao_acende_o_aviso(self) -> None:
        daemon = _DaemonDublado(secundarios=2)
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)
        assert gp.steam_input_coop_derrubados(daemon) == 0

        with structlog.testing.capture_logs() as registros:
            assert gp.reavaliar_coop_fora_da_mesa(daemon, {P2}) == 1

        assert gp.steam_input_coop_derrubados(daemon) == 1
        assert [r for r in registros if r["event"] == "coop_controles_fora_da_mesa"], (
            "o aviso acendendo também é um fato — a falta deste registro foi o"
            " que fez o defeito durar um dia"
        )

    async def test_o_controle_voltando_apaga_o_aviso_sozinho(self) -> None:
        """Simétrico: a mesma medição que acende é a que apaga."""
        daemon = _DaemonDublado(secundarios=2)
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        assert gp.reavaliar_coop_fora_da_mesa(daemon, {P2}) == 1
        assert gp.reavaliar_coop_fora_da_mesa(daemon, {P2, P3}) == 0

    def test_o_tique_do_coop_e_quem_mede_no_produto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA do CONTRAPESO no caminho real."""
        daemon = _daemon_suspenso((P2, P3))
        manager = CoopManager(daemon)
        manager._watch = _WatchDublado(True)  # type: ignore[assignment]
        monkeypatch.setattr(
            er, "discover_dualsense_evdevs", lambda: {P2: Path("/dev/input/event3")}
        )

        manager.sync()

        assert gp.steam_input_coop_derrubados(daemon) == 1

    def test_sem_mudanca_em_dev_input_o_tique_nao_paga_a_enumeracao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERF-MULTI-CONTROLLER-01 continua de pé: a enumeração cara"""
        daemon = _daemon_suspenso((P2, P3))
        manager = CoopManager(daemon)
        manager._watch = _WatchDublado(False)  # type: ignore[assignment]

        def _proibida() -> dict[str, Path]:
            raise AssertionError("enumeração cara em tique quieto")

        monkeypatch.setattr(er, "discover_dualsense_evdevs", _proibida)

        manager.sync()

        assert manager._watch.consultas == 1  # type: ignore[attr-defined]

    def test_sem_suspensao_em_curso_o_tique_nem_consulta_o_watch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caso comum (co-op desligado, nenhuma suspensão): custo zero."""
        daemon = _daemon_suspenso(())
        manager = CoopManager(daemon)
        manager._watch = _WatchDublado(True)  # type: ignore[assignment]

        manager.sync()

        assert manager._watch.consultas == 0  # type: ignore[attr-defined]


# O contrato que a JANELA lê — os dois lados no `state_full`


@pytest.mark.usefixtures("config_em_tmp")
class TestOStateFullDizAVerdade:
    async def test_as_duas_chaves_seguem_os_controles_e_nao_os_vpads(self) -> None:
        """`derrubado_por_steam_input` é o gatilho do banner e
        `secundarios_derrubados` é o número que ele mostra
        (`status_actions.texto_do_coop_derrubado`). Com os dois controles na
        mesa a janela cala; com um fora, ela fala."""
        daemon = _daemon_real_com_coop(2)
        daemon._steam_input_excecao = True
        daemon._steam_input_coop_caidos = (P2, P3)
        h = _Handlers(daemon, daemon.store, daemon.controller)

        gp.reavaliar_coop_fora_da_mesa(daemon, {P2, P3})
        cheio = await h._handle_daemon_state_full({})
        assert cheio["coop"]["derrubado_por_steam_input"] is False
        assert cheio["coop"]["secundarios_derrubados"] == 0

        gp.reavaliar_coop_fora_da_mesa(daemon, {P2})
        cheio = await h._handle_daemon_state_full({})
        assert cheio["coop"]["derrubado_por_steam_input"] is True
        assert cheio["coop"]["secundarios_derrubados"] == 1


@pytest.mark.usefixtures("sem_disco_nem_broker")
class TestASaidaLimpaAMesa:
    async def test_sair_da_excecao_apaga_a_lista_dos_sentados(self) -> None:
        """Deixar a lista de pé faria o tique reabrir a conta de uma suspensão"""
        daemon = _DaemonDublado(secundarios=2)
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)
        assert gp.reavaliar_coop_fora_da_mesa(daemon, set()) == 2

        assert gp.resume_vpads_after_steam_input(daemon) is True

        assert gp.coop_sentados_na_suspensao(daemon) == ()
        assert gp.steam_input_coop_derrubados(daemon) == 0
        assert gp.reavaliar_coop_fora_da_mesa(daemon, set()) == 0

    async def test_religar_a_emulacao_na_mao_tambem_apaga_a_mesa(self) -> None:
        """A SEGUNDA saída da suspensão (gesto manual dela, com o jogo aberto)."""
        daemon = _DaemonDublado(secundarios=2)
        daemon._steam_input_excecao = True
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)
        assert gp.reavaliar_coop_fora_da_mesa(daemon, set()) == 2

        gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")

        assert gp.coop_sentados_na_suspensao(daemon) == ()
        assert gp.steam_input_coop_derrubados(daemon) == 0

    async def test_leitura_blindada_contra_lixo_na_lista(self) -> None:
        """`state_full` roda a 10 Hz: dublê com mock no atributo não pode virar
        identidade de controle nenhum."""
        daemon = _DaemonDublado()
        assert gp.coop_sentados_na_suspensao(daemon) == ()
        daemon._steam_input_coop_caidos = "aa:bb:cc:00:00:00"
        assert gp.coop_sentados_na_suspensao(daemon) == ()
        daemon._steam_input_coop_caidos = (P2, object(), None)
        assert gp.coop_sentados_na_suspensao(daemon) == (P2,)
