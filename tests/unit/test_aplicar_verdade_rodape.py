"""APLICAR-VERDADE-01 — o rodapé para de dizer que aplicou quando não aplicou."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("aplicar verdade rodape")

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


MSG_SUCESSO = "Perfil aplicado ao controle."


def _fake_daemon() -> MagicMock:
    daemon = MagicMock()
    daemon.config = DaemonConfig()
    daemon.config.rumble_policy = "max"
    daemon._rumble_engine = None
    return daemon


@pytest.fixture
def applier() -> DraftApplier:
    """`DraftApplier` com FakeController conectado e StateStore real."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    return DraftApplier(controller=fc, store=store, daemon=_fake_daemon())


@pytest.fixture
def server(tmp_path: Path) -> IpcServer:
    """`IpcServer` com FakeController — o handler é chamado direto, sem socket."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "aplicar_verdade.sock",
        daemon=_fake_daemon(),
    )


class TestApplierRegistraAFalha:
    def test_secao_que_falhou_entra_em_failed(self, applier: DraftApplier) -> None:
        """A seção inválida some de `applied` E aparece em `failed` com motivo."""
        aplicadas = applier.apply({"leds": "isto não é um objeto"})

        assert aplicadas == []
        assert "leds" in applier.failed
        assert applier.failed["leds"]

    def test_seguir_aplicando_as_outras_continua_valendo(
        self, applier: DraftApplier
    ) -> None:
        """Best-effort intacto: a falha de uma seção não derruba as demais."""
        aplicadas = applier.apply(
            {"leds": "isto não é um objeto", "rumble": {"weak": 10, "strong": 20}}
        )

        assert aplicadas == ["rumble"]
        assert set(applier.failed) == {"leds"}

    def test_sucesso_nao_registra_falha(self, applier: DraftApplier) -> None:
        aplicadas = applier.apply({"leds": {"lightbar_rgb": [10, 20, 30]}})

        assert aplicadas == ["leds"]
        assert applier.failed == {}

    def test_failed_nao_acumula_entre_dois_applies(
        self, applier: DraftApplier
    ) -> None:
        """O mesmo applier reusado não pode arrastar a falha do pedido anterior."""
        applier.apply({"leds": "isto não é um objeto"})
        applier.apply({"leds": {"lightbar_rgb": [10, 20, 30]}})

        assert applier.failed == {}


class TestHandlerDevolveFailed:
    @pytest.mark.asyncio
    async def test_resposta_carrega_as_secoes_que_nao_entraram(
        self, server: IpcServer
    ) -> None:
        resposta = await server._handle_profile_apply_draft(
            {
                "leds": "isto não é um objeto",
                "triggers": 5,
                "rumble": {"weak": 10, "strong": 20},
            }
        )

        assert resposta["applied"] == ["rumble"]
        assert set(resposta["failed"]) == {"leds", "triggers"}

    @pytest.mark.asyncio
    async def test_status_continua_ok_mesmo_com_tudo_falhando(
        self, server: IpcServer
    ) -> None:
        """Contrato ADITIVO: applet, CLI e TUI leem `status` e quebrariam."""
        resposta = await server._handle_profile_apply_draft(
            {"leds": "x", "triggers": 5, "mouse": 7}
        )

        assert resposta["status"] == "ok"
        assert resposta["applied"] == []
        assert set(resposta["failed"]) == {"leds", "triggers", "mouse"}

    @pytest.mark.asyncio
    async def test_tudo_certo_devolve_failed_vazio(self, server: IpcServer) -> None:
        resposta = await server._handle_profile_apply_draft(
            {"leds": {"lightbar_rgb": [10, 20, 30]}}
        )

        assert resposta["applied"] == ["leds"]
        assert resposta["failed"] == {}


