"""Handlers da aba Início vs contrato do sinal "changed" do SegmentedSelector.

BUG-HOME-SEGMENTED-SIGNATURE-01: o sinal "changed" do SegmentedSelector é
emitido SEM argumentos (espelha ``GtkComboBox::changed``); o handler recebe só
o widget e deve ler ``get_active_id()``. Os handlers da Início pediam um 2º
argumento (``mode_id``/``flavor_id``) — o PyGObject engolia o ``TypeError`` e
os botões do comutador de modo e da máscara mudavam de visual sem NUNCA
disparar o IPC. Estes testes chamam os handlers com a aridade real do sinal.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions, mode_transition
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin


class _FakeSelector:
    """Espelha o subconjunto usado do SegmentedSelector (API por-ID).

    ``set_active_id`` emite "changed" chamando o callback com UM argumento (o
    próprio widget) — a mesma aridade do sinal GObject real e do stub puro.
    """

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
    """Grava as chamadas IPC dos handlers sem tocar o daemon.

    HARM-01: a troca de modo passou a ser despachada por `mode_transition` (dono
    único da sequência), então o fake precisa cobrir os DOIS módulos — a Início
    ainda chama `call_async` direto para co-op e máscara.
    """
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


def test_sinal_changed_dispara_ipc_do_modo_nativo(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Fluxo real: clique no seletor emite "changed" com 1 arg e chega ao IPC."""
    stub = _HomeStub()
    selector = stub._home_mode_selector
    selector.connect("changed", stub._on_home_mode_changed)

    selector.set_active_id("native")

    assert ("native.mode.set", {"enabled": True}) in ipc_calls


def test_modo_gamepad_sai_do_nativo_e_liga_com_flavor(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    stub = _HomeStub()
    stub._home_flavor_selector = _FakeSelector("xbox")
    stub._home_mode_selector.set_active_id("gamepad")

    stub._on_home_mode_changed(stub._home_mode_selector)

    assert ipc_calls == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"}),
    ]


def test_modo_desktop_desliga_nativo_e_gamepad_preservando_coop(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """FEAT-COOP-DEFAULT-ON-01: desktop NÃO desliga o co-op (preferência
    preservada — desligar o gamepad já desmonta os jogadores).

    HARM-06: e desktop LIGA o mouse (conforme a preferência persistida) — o
    modo é o dono da emulação de mouse/teclado, não a aba Mouse.
    """
    stub = _HomeStub()
    stub._home_mode_selector.set_active_id("desktop")

    stub._on_home_mode_changed(stub._home_mode_selector)

    assert ipc_calls == [
        ("native.mode.set", {"enabled": False}),
        ("gamepad.emulation.set", {"enabled": False}),
        ("mouse.emulation.restore", {}),
    ]


def test_guard_de_render_nao_dispara_ipc(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """set_active_id programático (render) roda sob guard e vira no-op."""
    stub = _HomeStub()
    stub._home_guard = True
    stub._home_mode_selector.set_active_id("native")

    stub._on_home_mode_changed(stub._home_mode_selector)

    assert ipc_calls == []


def test_flavor_changed_reaplica_gamepad_com_a_mascara(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    stub = _HomeStub()
    stub._home_mode_selector.set_active_id("gamepad")
    ipc_calls.clear()
    flavor = stub._home_flavor_selector
    flavor.connect("changed", stub._on_home_flavor_changed)

    flavor.set_active_id("xbox")

    assert ipc_calls == [
        ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"}),
    ]


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
    """LEIGO-01 — o opt-out não existe mais em nenhuma porta da aba Início.

    Pedido literal da mantenedora: "esse quadrado do click não deveria aparecer,
    ninguém conecta dois controles no pc esperando que os dois controles
    controlem a mesma pessoa". Um handler sobrevivente seria um caminho para
    gravar `coop_disabled.flag` — o defeito de volta por outra porta.
    """

    def test_nao_ha_handler_de_toggle_de_coop(self) -> None:
        assert not hasattr(HomeActionsMixin, "_on_home_coop_toggled")

    def test_nenhum_caminho_da_aba_chama_coop_set(
        self, ipc_calls: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Os três modos + a máscara: nenhum deles fala em `coop.set`."""
        for modo in ("desktop", "gamepad", "native"):
            stub = _HomeStub()
            stub._home_mode_selector.set_active_id(modo)
            stub._on_home_mode_changed(stub._home_mode_selector)

        assert [method for method, _ in ipc_calls] != []
        assert not [method for method, _ in ipc_calls if method == "coop.set"]
