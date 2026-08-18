"""ONDA-U Causa A — trava manual arma em TODOS os IPCs de aplicação.

Triagem `docs/process/estudos/2026-07-20-triagem-onda-u-gui.md`: o
`mark_manual_trigger_active()` que suprime o `AutoSwitcher` vivia só dentro
de `DraftApplier._apply_triggers` e de `_handle_trigger_set` — um "Aplicar no
controle" (ex.: só `leds`, o botão da aba Lightbar) ou os handlers de
led/rumble avulsos NUNCA armavam a trava, e o `AutoSwitcher` reescrevia a
edição não-persistida no próximo tick de troca de foco de janela ("perfil
eterno", U3/U4/U9/U11).

Falha-sem: no HEAD (antes desta leva), `store.manual_trigger_active` continua
`False` depois de `profile.apply_draft` só-com-`leds`, `led.set`,
`led.player_set`, `rumble.set`, `rumble.stop` e `rumble.passthrough`.

Fix HIGH 2026-07-20 (achado da corretora final, mesma triagem): a trava que
`rumble.set`/`rumble.stop` armam corretamente NUNCA tinha um par de
liberação fora de `profile.switch`/`trigger.reset` — o botão "Devolver ao
jogo" (`rumble.passthrough(enabled=True)`) também ARMAVA em vez de LIBERAR,
deixando o autoswitch mudo até a usuária ir na aba Perfis clicar "Ativar".
`TestRumblePassthroughLibera` cobre a liberação; a classe de armar acima
(`TestHandlersAvulsosArmamATrava`) teve `test_rumble_passthrough_arma`
substituído — `enabled=True` agora LIBERA, não arma (o achado era
justamente essa inversão de semântica).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
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
    fake_daemon.config.rumble_policy = "max"  # passthrough 1:1 (sem escala)
    fake_daemon._rumble_engine = None

    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "onda_u_trava.sock",
        daemon=fake_daemon,
    )
    return server, store


class TestApplyDraftArmaIncondicional:
    """`profile.apply_draft` arma a trava mesmo sem a seção `triggers`."""

    @pytest.mark.asyncio
    async def test_so_leds_arma_a_trava(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        assert store.manual_trigger_active is False
        resultado = await server._handle_profile_apply_draft(
            {"leds": {"lightbar_rgb": [10, 20, 30]}}
        )
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_secao_vazia_ainda_assim_arma(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        """Payload sem NENHUMA seção reconhecida (ex.: `{}`) — apply_draft é
        sempre edição manual explícita; a trava arma independente do que
        veio no corpo (as seções em si podem ser todas puladas)."""
        server, store = server_store
        await server._handle_profile_apply_draft({})
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_com_triggers_continua_armando(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        """Regressão: o caminho antigo (armar dentro de `_apply_triggers`)
        continua funcionando — só migrou de lugar."""
        server, store = server_store
        await server._handle_profile_apply_draft(
            {"triggers": {"left": {"mode": "Off", "params": []}}}
        )
        assert store.manual_trigger_active is True


class TestHandlersAvulsosArmamATrava:
    """`led.set`/`led.player_set`/`rumble.*` armam a trava (não só via draft)."""

    @pytest.mark.asyncio
    async def test_led_set_arma(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        resultado = await server._handle_led_set({"rgb": [255, 0, 0]})
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_led_player_set_arma(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        resultado = await server._handle_led_player_set(
            {"bits": [True, False, False, False, False]}
        )
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_rumble_set_arma(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        resultado = await server._handle_rumble_set({"weak": 100, "strong": 50})
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_rumble_stop_arma(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        resultado = await server._handle_rumble_stop({})
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True

    @pytest.mark.asyncio
    async def test_trigger_set_continua_armando(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        """Regressão do BUG-MOUSE-TRIGGERS-01 original — segue intocado."""
        server, store = server_store
        await server._handle_trigger_set(
            {"side": "left", "mode": "Off", "params": []}
        )
        assert store.manual_trigger_active is True


class TestRumblePassthroughLibera:
    """Fix HIGH 2026-07-20: `rumble.passthrough(enabled=True)` LIBERA a trava.

    Achado da corretora final: `rumble.set`/`rumble.stop` armam a trava
    corretamente (silêncio ou valor fixo são overrides deliberados, mesma
    semântica de `trigger.set`), mas o único gesto de liberação simétrico
    ("Devolver ao jogo" / fim do "Testar motores") também ARMAVA — o
    autoswitch ficava mudo pra sempre sem timeout e sem indicador na GUI,
    só destravável indo na aba Perfis clicar "Ativar" (ação sem relação com
    rumble). Falha-sem: no HEAD anterior a este fix,
    `store.manual_trigger_active` continuava `True` depois de
    `rumble.passthrough({"enabled": True})`.
    """

    @pytest.mark.asyncio
    async def test_passthrough_true_libera_apos_rumble_set(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        server, store = server_store
        await server._handle_rumble_set({"weak": 100, "strong": 50})
        assert store.manual_trigger_active is True

        resultado = await server._handle_rumble_passthrough({"enabled": True})
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is False

    @pytest.mark.asyncio
    async def test_fim_do_teste_500ms_libera(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        """Reproduz `_rumble_test_stop` da GUI: rumble.set -> rumble.stop ->
        rumble.passthrough(True) — o fluxo real de "Testar motores"."""
        server, store = server_store
        await server._handle_rumble_set({"weak": 160, "strong": 220})
        assert store.manual_trigger_active is True

        await server._handle_rumble_stop({})
        assert store.manual_trigger_active is True, (
            "rumble.stop preserva o silêncio deliberado (M2) — só "
            "passthrough libera"
        )

        await server._handle_rumble_passthrough({"enabled": True})
        assert store.manual_trigger_active is False

    @pytest.mark.asyncio
    async def test_passthrough_false_e_no_op_para_a_trava(
        self, server_store: tuple[IpcServer, StateStore]
    ) -> None:
        """`enabled=False` é documentado como sem efeito — não mexe na trava
        (nem arma nem libera; preserva o que já estava)."""
        server, store = server_store
        await server._handle_rumble_set({"weak": 100, "strong": 50})
        assert store.manual_trigger_active is True

        resultado = await server._handle_rumble_passthrough({"enabled": False})
        assert resultado["status"] == "ok"
        assert store.manual_trigger_active is True
