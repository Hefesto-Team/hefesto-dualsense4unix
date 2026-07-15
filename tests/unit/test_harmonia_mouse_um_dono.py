"""SPRINT-HARMONIA-01 — a emulação de mouse/teclado tem UM dono: o modo desktop.

HARM-05: a aba Mouse era um segundo dono e derrubava o vpad/co-op sem aviso —
por clique (switch ligado durante "Jogar pelo Hefesto") e por descuido (o
`dirty` da seção mouse NUNCA baixava, então todo "Aplicar" do rodapé pelo resto
da sessão religava o mouse e matava o vpad no meio do jogo).

HARM-06: "Controlar o PC" só DESLIGAVA gamepad/nativo — o controle ficava sem
função nenhuma até alguém achar a aba Mouse — e o round-trip
desktop->gamepad->desktop apagava a preferência persistida.

Herméticos: sem GTK real (widgets stub), sem daemon real (FakeController +
config_dir redirecionado para tmp_path), sem uinput de verdade.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    MODE_GATE_HINT,
    MouseActionsMixin,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_sub
from hefesto_dualsense4unix.integrations import virtual_pad
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

# ---------------------------------------------------------------------------
# HARM-05 (a) — o switch da aba Mouse só existe em "Controlar o PC"
# ---------------------------------------------------------------------------


class _FakeWidget:
    def __init__(self) -> None:
        self.sensitive = True
        self.text = ""
        self.visible = True

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)

    def set_text(self, value: str) -> None:
        self.text = value

    def set_visible(self, value: bool) -> None:
        self.visible = bool(value)


class _MouseTabStub(MouseActionsMixin):
    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.toggle = _FakeWidget()
        self.hint = _FakeWidget()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "mouse_emulation_toggle":
            return self.toggle
        if widget_id == "mouse_mode_hint_label":
            return self.hint
        return None


def test_switch_do_mouse_liberado_em_controlar_o_pc() -> None:
    stub = _MouseTabStub()
    stub._sync_mouse_mode_gate("desktop")

    assert stub.toggle.sensitive is True
    assert stub.hint.text == ""
    assert stub.hint.visible is False


@pytest.mark.parametrize("mode", ["gamepad", "native"])
def test_switch_do_mouse_bloqueado_jogando_com_a_razao_ao_lado(mode: str) -> None:
    """Ligá-lo aqui derrubava o vpad e os jogadores do co-op SEM AVISO."""
    stub = _MouseTabStub()
    stub._sync_mouse_mode_gate(mode)

    assert stub.toggle.sensitive is False
    assert stub.hint.text == MODE_GATE_HINT
    assert stub.hint.visible is True
    # A razão manda para o lugar certo em vez de só proibir.
    assert "Controlar o PC" in stub.hint.text


def test_switch_do_mouse_bloqueado_com_daemon_offline_e_sem_texto() -> None:
    """Sem estado não dá para saber se ligar derrubaria um jogo em andamento."""
    stub = _MouseTabStub()
    stub._sync_mouse_mode_gate(None)

    assert stub.toggle.sensitive is False
    assert stub.hint.text == ""


def test_gate_do_modo_aplicado_mesmo_com_edicao_pendente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gate vem antes dos returns do refresh.

    Os ramos de `dirty`/`in_profile` pulam a atualização do draft (para não
    apagar a edição da usuária) — não podem pular a exclusão mútua junto.
    """
    stub = _MouseTabStub()
    stub.draft = stub.draft.model_copy(
        update={"mouse": stub.draft.mouse.model_copy(update={"dirty": True})}
    )

    def _fake(
        _method: str, _params: Any, on_success: Any, on_failure: Any = None, **_kw: Any
    ) -> None:
        on_success({"gamepad_emulation": {"enabled": True}, "mouse_emulation": {}})

    monkeypatch.setattr(ipc_bridge, "call_async", _fake)
    stub._refresh_mouse_from_daemon_async()

    assert stub.toggle.sensitive is False


def test_refresh_da_aba_mouse_da_folga_de_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HARM-15: o state_full não cabe nos 0.25s default — sem folga o `_on_err`
    fechava o switch com o daemon VIVO e em modo desktop."""
    vistos: list[float] = []

    def _fake(
        _method: str,
        _params: Any,
        _ok: Any = None,
        _err: Any = None,
        timeout_s: float = 0.25,
        **_kw: Any,
    ) -> None:
        vistos.append(timeout_s)

    monkeypatch.setattr(ipc_bridge, "call_async", _fake)
    _MouseTabStub()._refresh_mouse_from_daemon_async()

    assert vistos == [1.0]


# ---------------------------------------------------------------------------
# HARM-05 (b) — o `dirty` baixa depois de aplicar (e só então)
# ---------------------------------------------------------------------------


class _FooterStub(FooterActionsMixin):
    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.toasts: list[str] = []
        self.widgets: dict[str, Any] = {}

    def _get(self, widget_id: str) -> Any:
        return self.widgets.get(widget_id)

    def _status_toast(self, _context: str, msg: str) -> None:
        self.toasts.append(msg)


def _com_mouse_tocado(stub: _FooterStub, **update: Any) -> None:
    stub.draft = stub.draft.model_copy(
        update={
            "mouse": stub.draft.mouse.model_copy(
                update={"enabled": True, "dirty": True, **update}
            )
        }
    )


@pytest.fixture()
def apply_result(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`profile.apply_draft` síncrono, com resultado controlável pelo teste."""
    box: dict[str, Any] = {"result": {"status": "ok"}, "erro": None, "enviados": []}

    def _fake(
        _method: str,
        params: Any,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        box["enviados"].append(params)
        if box["erro"] is not None:
            on_failure(box["erro"])
            return
        on_success(box["result"])

    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _fake)
    return box


def test_aplicar_com_sucesso_baixa_o_dirty(apply_result: dict[str, Any]) -> None:
    """Era o único `dirty=False` que faltava: sem ele, depois de tocar a aba
    Mouse UMA vez, todo "Aplicar" religava o mouse e matava o vpad."""
    stub = _FooterStub()
    _com_mouse_tocado(stub)

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is False


def test_aplicar_seguinte_nao_reenvia_a_secao_mouse(
    apply_result: dict[str, Any],
) -> None:
    """Aceite do HARM-05: nenhum "Aplicar" muda o modo do sistema.

    O PRIMEIRO Aplicar é o que importa — baixar o `dirty` no callback de
    sucesso só alcança o segundo, e o dano já foi. Nem o primeiro leva
    `enabled`: ele carrega só a edição pendente, que é a velocidade.
    """
    stub = _FooterStub()
    _com_mouse_tocado(stub)

    stub.on_apply_draft()
    stub.on_apply_draft()

    assert apply_result["enviados"][0]["mouse"] == {"speed": 6, "scroll_speed": 1}
    # Aplicada a edição, o segundo Aplicar não tem nada de mouse a dizer.
    assert apply_result["enviados"][1]["mouse"] is None


def test_aplicar_que_falhou_mantem_o_dirty(apply_result: dict[str, Any]) -> None:
    """A edição continua pendente: o daemon não a recebeu."""
    stub = _FooterStub()
    _com_mouse_tocado(stub)
    apply_result["erro"] = RuntimeError("daemon offline")

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is True


def test_aplicar_recusado_pelo_daemon_mantem_o_dirty(
    apply_result: dict[str, Any],
) -> None:
    """status=failed é resposta, não sucesso."""
    stub = _FooterStub()
    _com_mouse_tocado(stub)
    apply_result["result"] = {"status": "failed"}

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is True


def test_aplicar_nao_faz_o_salvar_perfil_perder_a_secao_mouse(
    apply_result: dict[str, Any],
) -> None:
    """Baixar o `dirty` não pode apagar a seção do perfil salvo depois
    (BUG-MOUSE-SAVE-DROPS-SECTION-01): aplicada, ela FAZ PARTE da config."""
    stub = _FooterStub()
    _com_mouse_tocado(stub, speed=9)

    stub.on_apply_draft()
    perfil = stub.draft.to_profile("meu_perfil")

    assert perfil.mouse is not None
    assert perfil.mouse.speed == 9


def test_descongelar_nao_reabre_o_switch_fora_do_modo_desktop(
    monkeypatch: pytest.MonkeyPatch, apply_result: dict[str, Any]
) -> None:
    """HARM-05: `_freeze_ui(False)` liberava o switch do mouse às cegas —
    inclusive em "Jogar pelo Hefesto", ressuscitando o clique que derruba o
    vpad. A classe real tem os dois mixins; aqui espelhamos essa composição."""

    class _AppStub(FooterActionsMixin, MouseActionsMixin):
        def __init__(self) -> None:
            self.draft = DraftConfig.default()
            self.toggle = _FakeWidget()
            self.hint = _FakeWidget()
            self.toasts: list[str] = []

        def _get(self, widget_id: str) -> Any:
            if widget_id == "mouse_emulation_toggle":
                return self.toggle
            if widget_id == "mouse_mode_hint_label":
                return self.hint
            return None

        def _status_toast(self, _context: str, msg: str) -> None:
            self.toasts.append(msg)

    def _state_full(
        _method: str, _params: Any, on_success: Any = None, **_kw: Any
    ) -> None:
        on_success({"gamepad_emulation": {"enabled": True}})

    stub = _AppStub()
    monkeypatch.setattr(ipc_bridge, "call_async", _state_full)

    stub._freeze_ui(False)

    assert stub.toggle.sensitive is False


# ---------------------------------------------------------------------------
# HARM-06 — a preferência de mouse sobrevive ao round-trip pelo jogo
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


class _FakeMouseDevice:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def set_speed(self, **_kw: Any) -> None:
        pass


def _daemon() -> Daemon:
    return Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )


@pytest.fixture()
def daemon(monkeypatch: pytest.MonkeyPatch) -> Daemon:
    """Daemon com o start do mouse dublado (sem uinput de verdade)."""
    d = _daemon()

    def _start(target: Any) -> bool:
        target._mouse_device = _FakeMouseDevice()
        target.config.mouse_emulation_enabled = True
        session.save_mouse_emulation(
            True,
            speed=target.config.mouse_speed,
            scroll_speed=target.config.mouse_scroll_speed,
        )
        return True

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.mouse.start_mouse_emulation", _start
    )
    return d


def test_preferencia_nunca_configurada_liga_o_mouse(
    tmp_config: Path, daemon: Daemon
) -> None:
    """Aceite do HARM-06: entrar em "Controlar o PC" deixa o cursor
    funcionando. Sem flag = nunca configurada; a alternativa é o controle mudo."""
    assert session.load_mouse_preference() == (None, None, None)

    assert daemon.restore_mouse_preference() is True
    assert daemon.config.mouse_emulation_enabled is True


def test_preferencia_desligada_de_proposito_e_respeitada(
    tmp_config: Path, daemon: Daemon
) -> None:
    """"Desligado pela usuária" não pode virar "nunca configurada" — senão o
    modo desktop religa o mouse contra a vontade dela."""
    session.save_mouse_emulation(False)

    assert daemon.restore_mouse_preference() is False
    assert daemon.config.mouse_emulation_enabled is False


def test_restore_reaplica_as_velocidades_persistidas(
    tmp_config: Path, daemon: Daemon
) -> None:
    session.save_mouse_emulation(True, speed=11, scroll_speed=4)

    daemon.restore_mouse_preference()

    assert daemon.config.mouse_speed == 11
    assert daemon.config.mouse_scroll_speed == 4


def test_ligar_o_gamepad_nao_apaga_a_preferencia_de_mouse(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A causa-raiz do HARM-06: a exclusão mútua gravava "off" e o round-trip
    desktop->gamepad->desktop devolvia o controle sem função nenhuma."""
    session.save_mouse_emulation(True, speed=9, scroll_speed=2)
    d = _daemon()
    d._mouse_device = _FakeMouseDevice()
    d.config.mouse_emulation_enabled = True
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: None)

    # O start do vpad falha (make_virtual_pad -> None), mas a exclusão mútua já
    # rodou — que é o ponto: ela não pode custar a preferência.
    gamepad_sub.start_gamepad_emulation(d, flavor="xbox")

    assert d._mouse_device is None  # o device saiu do caminho do jogo
    assert d.config.mouse_emulation_enabled is False
    # ... mas a PREFERÊNCIA (e as velocidades) sobreviveram.
    assert session.load_mouse_preference() == (True, 9, 2)


def test_round_trip_desktop_gamepad_desktop_preserva(
    tmp_config: Path, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aceite do HARM-06: sair e voltar preserva."""
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: None)
    daemon.restore_mouse_preference()  # desktop: liga por default
    assert daemon.config.mouse_emulation_enabled is True

    gamepad_sub.start_gamepad_emulation(daemon, flavor="xbox")  # foi jogar
    assert daemon.config.mouse_emulation_enabled is False

    assert daemon.restore_mouse_preference() is True  # voltou pro desktop
    assert daemon.config.mouse_emulation_enabled is True


@pytest.mark.asyncio
async def test_ipc_restore_liga_o_mouse_e_esta_no_contrato(
    tmp_config: Path, daemon: Daemon
) -> None:
    """O passo `mouse.emulation.restore` do plano do modo desktop tem que EXISTIR
    no contrato IPC — método não registrado faria a Início pintar "Falha ao mudar
    o modo" com o modo já aplicado."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    handler = server._handlers["mouse.emulation.restore"]

    assert await handler({}) == {"status": "ok", "enabled": True}
    assert daemon.config.mouse_emulation_enabled is True


@pytest.mark.asyncio
async def test_ipc_restore_com_daemon_sem_o_metodo_nao_estoura(
    tmp_config: Path,
) -> None:
    """Daemon antigo/dublado: o modo desktop vale sem o mouse — mas a resposta
    não pode mentir "ok"."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    class _DaemonSemRestore:
        config = DaemonConfig()

    server = IpcServer(
        controller=FakeController(transport="usb"),
        store=StateStore(),
        profile_manager=MagicMock(),
        daemon=_DaemonSemRestore(),
    )

    assert await server._handlers["mouse.emulation.restore"]({}) == {
        "status": "failed",
        "enabled": False,
    }


def test_desligar_o_mouse_na_mao_persiste_off(tmp_config: Path, daemon: Daemon) -> None:
    """O gesto MANUAL da aba Mouse continua gravando a preferência — é ele que
    a exclusão mútua não pode imitar."""
    daemon.restore_mouse_preference()

    daemon.set_mouse_emulation(False)

    assert session.load_mouse_preference()[0] is False


# ---------------------------------------------------------------------------
# HARM-05 (c) — o "Aplicar" não derruba o vpad (do draft até o daemon)
# ---------------------------------------------------------------------------


def _applier(daemon: Daemon) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    return DraftApplier(controller=daemon.controller, store=daemon.store, daemon=daemon)


def test_aplicar_jogando_nao_derruba_o_vpad(
    tmp_config: Path, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O repro do revisor, do draft ao daemon (aceite do item HIGH).

    Início em "Controlar o PC" -> a aba Mouse liga o switch -> "Jogar pelo
    Hefesto" -> um "Aplicar" qualquer (mudou um gatilho). O payload levava
    `mouse.enabled=true`, o daemon aplicava a exclusão mútua e o vpad morria no
    meio da partida. Aqui o draft está do jeito exato daquele momento: mouse
    `enabled=True` (de quando ela estava no desktop) e `dirty` de um slider.
    """
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: object())
    gamepad_sub.start_gamepad_emulation(daemon, flavor="xbox")
    assert daemon._gamepad_device is not None

    sujo = DraftConfig.default()
    sujo = sujo.model_copy(
        update={
            "mouse": sujo.mouse.model_copy(
                update={"enabled": True, "speed": 9, "dirty": True}
            )
        }
    )

    _applier(daemon).apply(sujo.to_ipc_dict())

    assert daemon._gamepad_device is not None
    assert daemon._mouse_device is None
    assert daemon.config.gamepad_emulation_enabled is True


def test_aplicar_jogando_ainda_aplica_a_velocidade_editada(
    tmp_config: Path, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tirar `enabled` do payload não pode custar a edição que ele carregava.

    A seção só viaja por causa dos sliders — se ela virasse no-op, o item HIGH
    teria sido "consertado" jogando a feature fora (e o applier engole a
    exceção da seção, então a perda seria SILENCIOSA).
    """
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: object())
    gamepad_sub.start_gamepad_emulation(daemon, flavor="xbox")

    sujo = DraftConfig.default()
    sujo = sujo.model_copy(
        update={
            "mouse": sujo.mouse.model_copy(
                update={"speed": 11, "scroll_speed": 4, "dirty": True}
            )
        }
    )

    aplicadas = _applier(daemon).apply(sujo.to_ipc_dict())

    assert "mouse" in aplicadas
    assert daemon.config.mouse_speed == 11
    assert daemon.config.mouse_scroll_speed == 4
