"""APLICAR-VERDADE-01 — o rodapé para de dizer que aplicou quando não aplicou.

A cadeia do defeito, medida antes da cura:

- ``DraftApplier._apply_section`` engolia a exceção da seção com um
  ``logger.warning`` e não registrava a falha em lugar nenhum — só os
  sucessos entravam em ``applied``;
- o handler ``profile.apply_draft`` respondia ``{"status": "ok", ...}``
  SEMPRE, mesmo com todas as seções falhando;
- ``FooterActionsMixin._on_ok`` decidia pela chave ``status`` e nunca olhava
  ``applied`` — com as sete seções fora, a statusbar dizia "Perfil aplicado
  ao controle.".

Os testes aqui cobrem os três elos e o contrato que NÃO pode mudar: ``status``
continua ``"ok"`` (applet, CLI e TUI decidem por ele) e resposta de daemon
antigo, sem os campos novos, continua sendo lida como sucesso.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

MSG_SUCESSO = "Perfil aplicado ao controle."


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


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


class _FooterStub(FooterActionsMixin):
    """Mixin do rodapé sem GTK: widgets ausentes e statusbar em memória."""

    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return None

    def _status_toast(self, _context: str, msg: str) -> None:
        self.toasts.append(msg)


def _aplicar(
    monkeypatch: pytest.MonkeyPatch, resultado: Any
) -> _FooterStub:
    """Roda `on_apply_draft` com o daemon respondendo `resultado`."""
    stub = _FooterStub()

    def _fake(
        _method: str,
        _params: Any,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _fake)
    stub.on_apply_draft()
    return stub


# ---------------------------------------------------------------------------
# Elo 1 — o applier registra a falha
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Elo 2 — o handler devolve o que ficou de fora
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Elo 3 — o rodapé nomeia o que não entrou
# ---------------------------------------------------------------------------


class TestRodapeNaoMenteMais:
    def test_parte_falhou_nomeia_as_secoes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = _aplicar(
            monkeypatch,
            {
                "status": "ok",
                "applied": ["leds"],
                "failed": {"triggers": "boom", "rumble": "boom"},
            },
        )

        msg = stub.toasts[-1]
        assert MSG_SUCESSO not in stub.toasts
        assert "gatilhos" in msg
        assert "vibração" in msg

    def test_nada_aplicou_nao_promete_sucesso(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = _aplicar(
            monkeypatch,
            {
                "status": "ok",
                "applied": [],
                "failed": {
                    "leds": "boom",
                    "triggers": "boom",
                    "controllers": "boom",
                    "rumble": "boom",
                    "mouse": "boom",
                    "keyboard": "boom",
                    "mic": "boom",
                },
            },
        )

        assert MSG_SUCESSO not in stub.toasts
        assert "Nada foi aplicado" in stub.toasts[-1]

    def test_texto_cabe_na_statusbar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Meia tela trunca com reticências: a lista longa vira "e mais N"."""
        stub = _aplicar(
            monkeypatch,
            {
                "status": "ok",
                "applied": ["leds"],
                "failed": {
                    "triggers": "boom",
                    "controllers": "boom",
                    "rumble": "boom",
                    "mouse": "boom",
                    "keyboard": "boom",
                    "mic": "boom",
                },
            },
        )

        msg = stub.toasts[-1]
        assert MSG_SUCESSO not in stub.toasts
        assert "e mais 3" in msg
        assert len(msg) <= 80

    def test_secao_desconhecida_aparece_com_o_nome_tecnico(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Daemon mais novo que a GUI: melhor termo estranho que omissão."""
        stub = _aplicar(
            monkeypatch,
            {"status": "ok", "applied": ["leds"], "failed": {"haptics": "boom"}},
        )

        assert MSG_SUCESSO not in stub.toasts
        assert "haptics" in stub.toasts[-1]

    def test_tudo_aplicou_mantem_a_frase_de_sempre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = _aplicar(
            monkeypatch,
            {"status": "ok", "applied": ["leds", "rumble"], "failed": {}},
        )

        assert stub.toasts[-1] == MSG_SUCESSO


class TestCaminhosPreservados:
    def test_daemon_antigo_sem_os_campos_novos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem `applied`/`failed` não há do que desconfiar: segue sucesso."""
        stub = _aplicar(monkeypatch, {"status": "ok"})

        assert stub.toasts[-1] == MSG_SUCESSO

    def test_resultado_booleano_verdadeiro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = _aplicar(monkeypatch, True)

        assert stub.toasts[-1] == MSG_SUCESSO

    def test_resultado_booleano_falso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = _aplicar(monkeypatch, False)

        assert stub.toasts[-1] == "ERRO ao aplicar perfil (daemon offline?)."

    def test_status_diferente_de_ok_continua_erro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = _aplicar(monkeypatch, {"status": "failed"})

        assert stub.toasts[-1] == "ERRO ao aplicar perfil (daemon offline?)."
