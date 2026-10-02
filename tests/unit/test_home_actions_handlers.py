"""Handlers da aba Início vs contrato do sinal "changed" do SegmentedSelector."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_actions_handlers: importa código da janela GTK")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions, mode_transition
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin


class _FakeSelector:
    """Espelha o subconjunto usado do SegmentedSelector (API por-ID)."""

    def __init__(self, active_id: str | None = None) -> None:
        self._active_id = active_id
        self._handlers: list[Any] = []

    def connect(self, signal: str, callback: Any) -> None:
        if signal == "changed":
            self._handlers.append(callback)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for cb in list(self._handlers):
            cb(self)


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text


class _HomeStub:
    """Instância mínima com os atributos que os handlers da Início tocam."""

    _on_home_mode_changed = HomeActionsMixin._on_home_mode_changed
    _on_home_flavor_changed = HomeActionsMixin._on_home_flavor_changed

    def _perguntar_antes_de_relancar(self, **_kw: object) -> bool:
        return False

    def __init__(self) -> None:
        self._home_guard = False
        self._home_mode_desc = _FakeLabel()
        self._home_mode_selector = _FakeSelector()
        self._home_flavor_selector = _FakeSelector("dualsense")
        self.toasts: list[str] = []
        self.refreshed = 0

    def _status_toast(self, _origin: str, message: str) -> None:
        self.toasts.append(message)

    def _refresh_home_tab(self) -> None:
        self.refreshed += 1


@pytest.fixture()
def ipc_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Grava as chamadas IPC dos handlers sem tocar o daemon."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def _fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        _done: Any = None,
        _fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {})))

    monkeypatch.setattr(home_actions, "call_async", _fake_call_async)
    monkeypatch.setattr(mode_transition, "call_async", _fake_call_async)
    return calls


def test_sinal_changed_com_um_argumento_chega_ao_handler(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Fluxo real: o clique emite "changed" com 1 arg e o handler REGISTRA."""
    stub = _HomeStub()
    selector = stub._home_mode_selector
    selector.connect("changed", stub._on_home_mode_changed)

    selector.set_active_id("native")

    assert stub._escolha_pendente == {"modo": "native"}
    assert ipc_calls == [], "o clique voltou a falar com o daemon"


def test_guard_de_render_nao_dispara_ipc(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """set_active_id programático (render) roda sob guard e vira no-op."""
    stub = _HomeStub()
    stub._home_guard = True
    stub._home_mode_selector.set_active_id("native")

    stub._on_home_mode_changed(stub._home_mode_selector)

    assert ipc_calls == []


def test_flavor_changed_marca_a_mascara_sem_falar_com_o_daemon(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """AGORA-E-DEPOIS-01: o clique na máscara registra e para por aí."""
    stub = _HomeStub()
    stub._home_mode_selector.set_active_id("gamepad")
    ipc_calls.clear()
    flavor = stub._home_flavor_selector
    flavor.connect("changed", stub._on_home_flavor_changed)

    flavor.set_active_id("xbox")

    assert stub._escolha_pendente == {"mascara": "xbox"}
    assert ipc_calls == []


def test_flavor_changed_fora_do_modo_gamepad_e_no_op(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    stub = _HomeStub()
    stub._home_mode_selector.set_active_id("desktop")
    ipc_calls.clear()

    stub._home_flavor_selector.set_active_id("xbox")
    stub._on_home_flavor_changed(stub._home_flavor_selector)

    assert ipc_calls == []


class TestCheckboxDeCoopSumiu:
    """LEIGO-01 — o opt-out não existe mais em nenhuma porta da aba Início."""

    def test_nao_ha_handler_de_toggle_de_coop(self) -> None:
        assert not hasattr(HomeActionsMixin, "_on_home_coop_toggled")

    def test_nenhum_caminho_da_aba_chama_coop_set(
        self, ipc_calls: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Os três modos: nenhum deles fala em `coop.set`."""
        marcadas: list[dict[str, str] | None] = []
        for modo in ("desktop", "gamepad", "native"):
            stub = _HomeStub()
            stub._home_mode_selector.set_active_id(modo)
            stub._on_home_mode_changed(stub._home_mode_selector)
            marcadas.append(stub._escolha_pendente)

        assert marcadas == [
            {"modo": "desktop"},
            {"modo": "gamepad"},
            {"modo": "native"},
        ]
        assert not [method for method, _ in ipc_calls if method == "coop.set"]
