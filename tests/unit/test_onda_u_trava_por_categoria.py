"""ONDA-U F1/F2/F3 (auditoria 21/07) — trava manual POR CATEGORIA + renumber.

A trava manual era um booleano único (`_manual_trigger_active`), com duas
consequências medidas na auditoria:
- F1: o fim do "Testar motores" (`rumble.passthrough(True)`) limpava a trava
  INTEIRA — um LED/gatilho deliberado aplicado em outra aba voltava a ser
  reescrito pelo autoswitch na próxima troca de foco;
- F2: um `led.set` armava a trava para SEMPRE e silenciava inclusive a troca
  de perfil POR JOGO (`steam_app_*`), sem indicador na GUI.

O fix: categorias {"trigger", "led", "rumble"} em `StateStore`;
`rumble.passthrough` limpa SÓ "rumble"; o `AutoSwitcher._activate` cede ao
perfil de JOGO (janela `steam_app_*` + candidato != perfil ativo), limpando
as categorias ao ceder; reaplicação do perfil ativo ("perfil eterno") e
regras comuns de janela seguem suprimidas.

F3 (`identity.renumber`): `asyncio.to_thread` não é cancelável — a thread
zumbi de um `lock_timeout` compactava DEPOIS, com jogo já aberto. A
autoridade agora é re-checada DENTRO dos locks (`_RenumberAuthorityChangedError`).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_handlers import _RenumberAuthorityChangedError
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def server_store(tmp_path: Path) -> tuple[IpcServer, StateStore]:
    """`IpcServer` com `FakeController` + `StateStore` real (sem profiles I/O)."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)

    fake_daemon = MagicMock()
    fake_daemon.config = DaemonConfig()
    fake_daemon.config.rumble_policy = "max"
    fake_daemon._rumble_engine = None

    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "onda_u_categorias.sock",
        daemon=fake_daemon,
    )
    return server, store


class TestStateStoreCategorias:
    def test_arma_por_categoria_e_qualquer_uma_liga_a_propriedade(self) -> None:
        store = StateStore()
        assert store.manual_trigger_active is False
        store.mark_manual_trigger_active("led")
        assert store.manual_trigger_active is True
        assert store.manual_override_categories == frozenset({"led"})

    def test_clear_de_uma_categoria_preserva_as_outras(self) -> None:
        store = StateStore()
        store.mark_manual_trigger_active("led")
        store.mark_manual_trigger_active("rumble")
        store.clear_manual_trigger_active("rumble")
        assert store.manual_override_categories == frozenset({"led"})
        assert store.manual_trigger_active is True

    def test_clear_sem_categoria_limpa_tudo(self) -> None:
        store = StateStore()
        for categoria in ("trigger", "led", "rumble"):
            store.mark_manual_trigger_active(categoria)
        store.clear_manual_trigger_active()
        assert store.manual_trigger_active is False
        assert store.manual_override_categories == frozenset()

    def test_categoria_desconhecida_e_erro(self) -> None:
        store = StateStore()
        with pytest.raises(ValueError):
            store.mark_manual_trigger_active("mouse")


class TestF1PassthroughNaoApagaOutrasCategorias:
    """O cenário exato do F1: LED manual sobrevive ao fim do Testar motores."""

    @pytest.mark.asyncio
    async def test_led_sobrevive_ao_passthrough(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        await server._handle_led_set({"rgb": [10, 20, 30]})
        await server._handle_rumble_set({"weak": 100, "strong": 100})
        assert store.manual_override_categories == frozenset({"led", "rumble"})
        # Fim do "Testar motores": libera SÓ o rumble.
        await server._handle_rumble_passthrough({"enabled": True})
        assert store.manual_override_categories == frozenset({"led"})
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_trigger_reset_segue_limpando_tudo(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        await server._handle_led_set({"rgb": [10, 20, 30]})
        await server._handle_trigger_set({"side": "left", "mode": "Off", "params": []})
        await server._handle_trigger_reset({})
        assert store.manual_trigger_active is False


class TestCategoriasDosHandlers:
    @pytest.mark.asyncio
    async def test_mapa_handler_para_categoria(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        await server._handle_trigger_set({"side": "left", "mode": "Off", "params": []})
        assert store.manual_override_categories == frozenset({"trigger"})
        store.clear_manual_trigger_active()
        await server._handle_led_player_set(
            {"bits": [True, False, True, False, True]}
        )
        assert store.manual_override_categories == frozenset({"led"})
        store.clear_manual_trigger_active()
        await server._handle_rumble_stop({})
        assert store.manual_override_categories == frozenset({"rumble"})

    @pytest.mark.asyncio
    async def test_apply_draft_arma_so_as_secoes_presentes(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        await server._handle_profile_apply_draft(
            {"leds": {"lightbar_rgb": [10, 20, 30]}}
        )
        assert store.manual_override_categories == frozenset({"led"})

    @pytest.mark.asyncio
    async def test_apply_draft_sem_secao_mapeavel_arma_tudo(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        # Preserva o incondicional da cura original (Causa A): payload sem
        # led/trigger/rumble (ex.: só mouse) arma as três categorias.
        server, store = server_store
        await server._handle_profile_apply_draft({"mouse": {"enabled": False}})
        assert store.manual_override_categories == frozenset(
            {"led", "trigger", "rumble"}
        )


class TestF2AutoswitchCedeAoJogo:
    def _switcher(self, store: StateStore) -> tuple[AutoSwitcher, MagicMock]:
        manager = MagicMock(spec=ProfileManager)
        switcher = AutoSwitcher(
            manager=manager, window_reader=lambda: {}, store=store
        )
        return switcher, manager

    def test_reaplicacao_do_perfil_ativo_segue_suprimida(self) -> None:
        # O "perfil eterno" da Causa A: candidato == perfil ATIVO + troca de
        # foco NÃO pode reescrever a edição manual.
        store = StateStore()
        store.set_active_profile("fallback")
        store.mark_manual_trigger_active("led")
        switcher, manager = self._switcher(store)
        switcher._activate("fallback", {"wm_class": "Inkscape"})
        manager.activate.assert_not_called()
        assert store.manual_trigger_active is True

    def test_regra_comum_de_janela_segue_suprimida(self) -> None:
        # Semântica histórica do BUG-MOUSE-TRIGGERS-01 preservada para
        # candidato não-jogo (mesmo diferente do ativo).
        store = StateStore()
        store.set_active_profile("fallback")
        store.mark_manual_trigger_active("trigger")
        switcher, manager = self._switcher(store)
        switcher._activate("navegacao", {"wm_class": "firefox"})
        manager.activate.assert_not_called()
        assert store.manual_trigger_active is True

    def test_perfil_de_jogo_vence_o_override_e_limpa_categorias(self) -> None:
        # F2: janela steam_app_* com perfil PRÓPRIO ativa mesmo com a trava
        # armada — e limpa as categorias (o perfil do jogo reescreve tudo).
        store = StateStore()
        store.set_active_profile("fallback")
        store.mark_manual_trigger_active("led")
        switcher, manager = self._switcher(store)
        switcher._activate("perfil_do_jogo", {"wm_class": "steam_app_1599660"})
        manager.activate.assert_called_once_with(
            "perfil_do_jogo", origin="autoswitch"
        )
        assert store.manual_trigger_active is False

    def test_jogo_reaplicando_o_proprio_perfil_ativo_nao_cede(self) -> None:
        # Candidato == ativo mesmo em janela de jogo = reaplicação, não troca;
        # a supressão protege a edição manual feita durante o jogo.
        store = StateStore()
        store.set_active_profile("perfil_do_jogo")
        store.mark_manual_trigger_active("led")
        switcher, manager = self._switcher(store)
        switcher._activate("perfil_do_jogo", {"wm_class": "steam_app_1599660"})
        manager.activate.assert_not_called()
        assert store.manual_trigger_active is True


class TestF3RenumberReChecaAutoridadeNoLock:
    def test_renumber_locked_aborta_com_jogo(self) -> None:
        with pytest.raises(_RenumberAuthorityChangedError):
            IpcServer._renumber_locked(
                None, None, authority_check=lambda: "game"
            )

    def test_renumber_locked_segue_sem_jogo(self) -> None:
        assert (
            IpcServer._renumber_locked(
                None, None, authority_check=lambda: "daemon"
            )
            == {}
        )

    @pytest.mark.asyncio
    async def test_handler_reporta_abort_quando_jogo_abre_durante_a_espera(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        # Pré-check passa ("daemon"); a re-checagem dentro do lock vê "game"
        # (o jogo abriu enquanto a thread esperava) → abort limpo.
        server, _store = server_store
        type(server.daemon).display_authority = PropertyMock(
            side_effect=["daemon", "game"]
        )
        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": False, "reason": "sessao_de_jogo_aberta"}
