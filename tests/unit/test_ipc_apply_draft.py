"""Testes unitarios do handler IPC profile.apply_draft (FEAT-PROFILE-STATE-01).

Cobre:
  - Handler aplica cada setor (leds, triggers, rumble, mouse).
  - Falha em um setor não bloqueia os outros (best-effort).
  - Retorna lista ``applied`` correta com setores aplicados com sucesso.
  - Handler wireado corretamente no dict _handlers (armadilha A-07).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def server_and_controller(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """IpcServer com FakeController pronto para testes de apply_draft."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))
    manager = ProfileManager(controller=fc, store=store)
    socket_path = tmp_path / "hefesto_draft.sock"

    # Daemon mock para set_mouse_emulation. Usa DaemonConfig real para que
    # rumble_policy tenha valor válido (balanceado, mult 0.7 por padrão)
    # — necessário após AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01, que faz
    # apply_draft escalar rumble via _apply_rumble_policy.
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    fake_daemon = MagicMock()
    fake_daemon.set_mouse_emulation.return_value = True
    fake_daemon.config = DaemonConfig()
    # Política "max" garante passthrough 1:1 dos valores brutos nos testes
    # que comparam set_rumble contra o payload declarado.
    fake_daemon.config.rumble_policy = "max"  # type: ignore[assignment]
    fake_daemon._rumble_engine = None

    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=fake_daemon,
    )
    await server.start()
    try:
        yield server, socket_path, fc, fake_daemon
    finally:
        await server.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DRAFT_COMPLETO: dict[str, Any] = {
    "triggers": {
        # Rigid(position, force) — 2 params
        "left": {"mode": "Rigid", "params": [0, 100]},
        # Off — 0 params
        "right": {"mode": "Off", "params": []},
    },
    "leds": {
        "lightbar_rgb": [128, 0, 255],
        "lightbar_brightness": 0.8,
        "player_leds": [True, True, True, True, True],
    },
    "rumble": {"weak": 40, "strong": 80},
    "mouse": {"enabled": True, "speed": 6, "scroll_speed": 1},
}


# ---------------------------------------------------------------------------
# Testes de wireup (A-07)
# ---------------------------------------------------------------------------


def test_handler_wireado_no_dict(tmp_path: Path) -> None:
    """profile.apply_draft deve estar no dict _handlers (armadilha A-07)."""
    fc = FakeController(transport="usb")
    store = StateStore()
    manager = MagicMock(spec=ProfileManager)
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "check.sock",
    )
    assert "profile.apply_draft" in server._handlers


# ---------------------------------------------------------------------------
# Testes de aplicação por setor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_draft_leds_aplica_lightbar(server_and_controller) -> None:
    """leds.lightbar_rgb deve chegar ao controller via set_led."""
    _server, socket_path, fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"leds": {"lightbar_rgb": [255, 0, 0], "lightbar_brightness": 1.0}},
        )
    assert result["status"] == "ok"
    assert "leds" in result["applied"]
    led_cmds = [c for c in fc.commands if c.kind == "set_led"]
    assert led_cmds, "nenhum set_led enviado ao controller"
    assert led_cmds[-1].payload == (255, 0, 0)


@pytest.mark.asyncio
async def test_apply_draft_leds_brightness_aplicada(server_and_controller) -> None:
    """brightness 0.5 deve dimmar a cor (128, 0, 0) -> (64, 0, 0)."""
    _server, socket_path, fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        await client.call(
            "profile.apply_draft",
            {"leds": {"lightbar_rgb": [128, 0, 0], "lightbar_brightness": 0.5}},
        )
    led_cmds = [c for c in fc.commands if c.kind == "set_led"]
    r, g, b = led_cmds[-1].payload
    assert r == 64
    assert g == 0
    assert b == 0


@pytest.mark.asyncio
async def test_apply_draft_player_leds_aplicados(server_and_controller) -> None:
    """player_leds deve chegar ao controller via set_player_leds."""
    _server, socket_path, fc, _ = server_and_controller
    bits = [True, False, True, False, True]
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"leds": {"player_leds": bits}},
        )
    assert "leds" in result["applied"]
    pl_cmds = [c for c in fc.commands if c.kind == "set_player_leds"]
    assert pl_cmds, "nenhum set_player_leds enviado"
    assert pl_cmds[-1].payload == (True, False, True, False, True)


@pytest.mark.asyncio
async def test_apply_draft_triggers_aplicados(server_and_controller) -> None:
    """triggers.left e triggers.right devem chegar via set_trigger."""
    _server, socket_path, fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {
                "triggers": {
                    # Rigid(position, force) — 2 params
                    "left": {"mode": "Rigid", "params": [0, 100]},
                    "right": {"mode": "Off", "params": []},
                }
            },
        )
    assert result["status"] == "ok"
    assert "triggers" in result["applied"]
    trig_cmds = [c for c in fc.commands if c.kind == "set_trigger"]
    sides_enviados = {c.payload[0] for c in trig_cmds}
    assert "left" in sides_enviados
    assert "right" in sides_enviados


@pytest.mark.asyncio
async def test_apply_draft_rumble_aplicado(server_and_controller) -> None:
    """rumble.weak e rumble.strong devem chegar via set_rumble."""
    _server, socket_path, fc, _fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"rumble": {"weak": 40, "strong": 80}},
        )
    assert "rumble" in result["applied"]
    rumble_cmds = [c for c in fc.commands if c.kind == "set_rumble"]
    assert rumble_cmds, "nenhum set_rumble enviado"
    last = rumble_cmds[-1].payload
    assert last == (40, 80) or (last[0] == 40 and last[1] == 80)


@pytest.mark.asyncio
async def test_apply_draft_mouse_aplicado(server_and_controller) -> None:
    """mouse deve ser encaminhado ao daemon.set_mouse_emulation."""
    _server, socket_path, _fc, fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"mouse": {"enabled": True, "speed": 6, "scroll_speed": 1}},
        )
    assert "mouse" in result["applied"]
    fake_daemon.set_mouse_emulation.assert_called_once()


@pytest.mark.asyncio
async def test_apply_draft_keyboard_aplica_bindings(server_and_controller) -> None:
    """BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: a seção keyboard empurra os
    bindings editados ao device vivo via set_bindings, sem reativar perfil."""
    _server, socket_path, _fc, fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"keyboard": {"key_bindings": {"cross": ["KEY_SPACE"]}}},
        )
    assert "keyboard" in result["applied"]
    fake_daemon._keyboard_device.set_bindings.assert_called_once_with(
        {"cross": ("KEY_SPACE",)}
    )


@pytest.mark.asyncio
async def test_apply_draft_keyboard_none_usa_default(server_and_controller) -> None:
    """key_bindings=None (ex.: após 'Restaurar defaults') resolve para o mapa
    DEFAULT_BUTTON_BINDINGS — não fica como no-op herdando o estado antigo."""
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    _server, socket_path, _fc, fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {"keyboard": {"key_bindings": None}},
        )
    assert "keyboard" in result["applied"]
    fake_daemon._keyboard_device.set_bindings.assert_called_once_with(
        dict(DEFAULT_BUTTON_BINDINGS)
    )


@pytest.mark.asyncio
async def test_apply_draft_rumble_zero_e_passthrough(server_and_controller) -> None:
    """BUG-RUMBLE-APPLY-KILLS-GAME-01: 'Aplicar' com rumble (0,0) é passthrough
    (rumble_active=None), não silêncio forçado a 5Hz que mataria o rumble do
    jogo. Aplica (0,0) uma vez para soltar um rumble contínuo anterior."""
    _server, socket_path, fc, fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft", {"rumble": {"weak": 0, "strong": 0}}
        )
    assert "rumble" in result["applied"]
    assert fake_daemon.config.rumble_active is None, "deveria ser passthrough"
    rumble_cmds = [c for c in fc.commands if c.kind == "set_rumble"]
    assert rumble_cmds and rumble_cmds[-1].payload[:2] == (0, 0)


@pytest.mark.asyncio
async def test_apply_draft_rumble_nonzero_persiste(server_and_controller) -> None:
    """Rumble != (0,0) continua persistindo em rumble_active para o poll loop
    reasserir (vibração contínua deliberada)."""
    _server, socket_path, _fc, fake_daemon = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        await client.call(
            "profile.apply_draft", {"rumble": {"weak": 40, "strong": 80}}
        )
    assert fake_daemon.config.rumble_active == (40, 80)


@pytest.mark.asyncio
async def test_apply_draft_completo_retorna_todos_aplicados(
    server_and_controller,
) -> None:
    """Draft completo deve retornar applied com 4 setores."""
    _server, socket_path, _fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.apply_draft", _DRAFT_COMPLETO)
    assert result["status"] == "ok"
    assert set(result["applied"]) == {"leds", "triggers", "rumble", "mouse"}


# ---------------------------------------------------------------------------
# Testes de resiliencia: falha em um setor não bloqueia os outros
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_falha_em_leds_nao_bloqueia_triggers(
    server_and_controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mesmo que set_led levante excecao, triggers ainda devem ser aplicados."""
    _server, socket_path, fc, _ = server_and_controller

    def set_led_falha(rgb: Any) -> None:
        raise RuntimeError("simulando falha de led")
    monkeypatch.setattr(fc, "set_led", set_led_falha)

    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {
                "leds": {"lightbar_rgb": [255, 0, 0]},
                "triggers": {
                    "left": {"mode": "Off", "params": []},
                    "right": {"mode": "Off", "params": []},
                },
            },
        )
    assert result["status"] == "ok"
    # leds falhou, triggers deve ter sido aplicado
    assert "leds" not in result["applied"]
    assert "triggers" in result["applied"]


@pytest.mark.asyncio
async def test_falha_em_triggers_nao_bloqueia_rumble(
    server_and_controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mesmo que set_trigger levante excecao, rumble ainda deve ser aplicado."""
    _server, socket_path, fc, _ = server_and_controller

    def set_trigger_falha(side: Any, effect: Any) -> None:
        raise RuntimeError("simulando falha de trigger")
    monkeypatch.setattr(fc, "set_trigger", set_trigger_falha)

    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {
                "triggers": {"left": {"mode": "Rigid", "params": [0, 100]}},
                "rumble": {"weak": 60, "strong": 120},
            },
        )
    assert result["status"] == "ok"
    assert "triggers" not in result["applied"]
    assert "rumble" in result["applied"]


@pytest.mark.asyncio
async def test_draft_vazio_retorna_applied_vazio(server_and_controller) -> None:
    """Sem secoes no draft, applied deve ser lista vazia."""
    _server, socket_path, _fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.apply_draft", {})
    assert result["status"] == "ok"
    assert result["applied"] == []


@pytest.mark.asyncio
async def test_apply_draft_ordem_leds_primeiro(server_and_controller) -> None:
    """leds deve aparecer em applied antes de triggers (ordem canonica)."""
    _server, socket_path, _fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.apply_draft", _DRAFT_COMPLETO)
    applied = result["applied"]
    if "leds" in applied and "triggers" in applied:
        assert applied.index("leds") < applied.index("triggers")


# ---------------------------------------------------------------------------
# PERFIL-04: seção `controllers` — overrides por-controle no apply_draft
# ---------------------------------------------------------------------------

#: MAC forjado da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
_UNIQ_2 = "aabbcc000002"


class _CtrlPorUniq:
    """Stub de backend que registra as chamadas da API por-uniq."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def apply_output_for(self, uniq: str, spec: Any) -> None:
        self.calls.append((uniq, spec))


def _applier_com_stub() -> tuple[Any, _CtrlPorUniq]:
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    ctrl = _CtrlPorUniq()
    return DraftApplier(controller=ctrl, store=MagicMock(), daemon=None), ctrl


def test_apply_controllers_aplica_por_uniq_com_brilho_escalado() -> None:
    """A seção controllers vira `apply_output_for(uniq, spec)` — a API
    por-uniq do PERFIL-01 (nunca o seletor global) — com o RGB escalado
    pelo brilho no MESMO caminho da seção global de leds."""
    applier, ctrl = _applier_com_stub()
    applied = applier.apply(
        {
            "controllers": {
                _UNIQ_2: {
                    "leds": {
                        "lightbar_rgb": [0, 100, 255],
                        "lightbar_brightness": 0.5,
                        "player_leds": [True, False, False, False, False],
                    },
                    "triggers": {"right": {"mode": "Rigid", "params": [5, 200]}},
                }
            }
        }
    )
    assert applied == ["controllers"]
    assert len(ctrl.calls) == 1
    uniq, spec = ctrl.calls[0]
    assert uniq == _UNIQ_2
    assert spec.led == (0, 50, 127)  # escalado por 0.5 (mesmo caminho)
    assert spec.player_leds == (True, False, False, False, False)
    assert spec.trigger_right is not None
    assert spec.trigger_left is None  # lado sem opinião não viaja
    assert spec.mic_led is None  # mic jamais colateral


def test_apply_controllers_entrada_vazia_nao_chama_backend() -> None:
    """Entrada sem seções ({}) não gera chamada (nada a aplicar)."""
    applier, ctrl = _applier_com_stub()
    applied = applier.apply({"controllers": {_UNIQ_2: {}}})
    assert applied == ["controllers"]
    assert ctrl.calls == []


def test_apply_controllers_invalido_nao_bloqueia_outras_secoes() -> None:
    """Seção controllers malformada falha best-effort (warning) e as demais
    seções seguem aplicadas — contrato do DraftApplier."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    fc = FakeController(transport="usb")
    fc.connect()
    applier = DraftApplier(controller=fc, store=MagicMock(), daemon=None)
    applied = applier.apply(
        {
            "controllers": ["não sou um objeto"],
            "leds": {"lightbar_rgb": [255, 0, 0]},
        }
    )
    assert "controllers" not in applied
    assert "leds" in applied


def test_apply_draft_global_com_alvo_selecionado_atinge_todos() -> None:
    """Fix do review (2026-07-16, MED): as seções GLOBAIS do apply_draft vão
    por broadcast REAL (`apply_output_defaults`, a mesma medicina do
    `ProfileManager.apply`). Antes, com um alvo selecionado no seletor (o
    estado normal do fluxo de edição por-controle), os setters clássicos
    gravavam a seção GLOBAL no OVERRIDE do alvo: o `_desired_default` nunca
    era atualizado (replug do outro controle reassertava estado velho) e o
    outro controle não recebia NADA."""
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        PyDualSenseController,
    )
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
    from tests.unit.test_backend_multi_controller import (
        KEY_1,
        KEY_2,
        _FakeHandle,
        _null_evdev,
    )

    backend = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    backend._handles = {KEY_1: h1, KEY_2: h2}
    backend._primary_key = KEY_1
    backend.set_output_target(1)  # usuária editando o Controle 2 (fluxo novo)

    applier = DraftApplier(controller=backend, store=MagicMock(), daemon=None)
    applied = applier.apply(
        {
            "leds": {
                "lightbar_rgb": [129, 61, 156],
                "lightbar_brightness": 1.0,
                "player_leds": [True, False, False, False, False],
            },
            "triggers": {"right": {"mode": "Rigid", "params": [5, 200]}},
        }
    )
    assert applied == ["leds", "triggers"]
    for h in (h1, h2):  # os DOIS controles receberam a seção global
        assert h.light.colors[-1] == (129, 61, 156)
        assert h.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]
    # O default foi atualizado (o replug reasserta o estado NOVO)...
    assert backend._desired_default.led == (129, 61, 156)
    assert backend._desired_default.trigger_right is not None
    # ...e a seção global NÃO virou override do alvo.
    assert backend._desired_by_uniq == {}
    # O seletor da usuária segue como estava (estado de UI preservado).
    assert backend.get_output_target_index() == 1


@pytest.mark.asyncio
async def test_apply_draft_controllers_fim_a_fim_com_backend_sem_estado(
    server_and_controller,
) -> None:
    """Fim a fim via IPC: backend sem estado por-controle (FakeController)
    herda o no-op seguro do IController — a seção aplica sem erro (aditivo,
    daemon antigo simplesmente ignora a chave)."""
    _server, socket_path, _fc, _ = server_and_controller
    async with IpcClient.connect(socket_path) as client:
        result = await client.call(
            "profile.apply_draft",
            {
                "controllers": {
                    _UNIQ_2: {"leds": {"lightbar_rgb": [0, 0, 255]}}
                }
            },
        )
    assert result["status"] == "ok"
    assert "controllers" in result["applied"]
