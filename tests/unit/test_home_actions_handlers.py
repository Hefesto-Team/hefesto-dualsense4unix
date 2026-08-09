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

    # RELANCAR-01 (08/08/2026): os handlers passam pelo `_perguntar_antes_de_
    # relancar` da base antes de aplicar. Aqui ele devolve False — "não assumi o
    # gesto" — que é EXATAMENTE o caminho real quando não há jogo aberto, e é o
    # que estes testes exercitam. O caminho com jogo tem testes próprios em
    # `test_relancar_01.py`, sem GTK.
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


def test_sinal_changed_com_um_argumento_chega_ao_handler(
    ipc_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Fluxo real: o clique emite "changed" com 1 arg e o handler REGISTRA.

    AGORA-E-DEPOIS-01 (08/08/2026): o que ele registra deixou de ser uma chamada
    ao daemon e passou a ser a escolha dela, aplicada depois pelo "Aplicar" do
    rodapé. O que este teste guarda continua sendo o mesmo: a ARIDADE do sinal —
    um handler que peça um segundo argumento faz o PyGObject engolir o
    `TypeError`, e o botão muda de visual sem nada acontecer.
    """
    stub = _HomeStub()
    selector = stub._home_mode_selector
    selector.connect("changed", stub._on_home_mode_changed)

    selector.set_active_id("native")

    assert stub._escolha_pendente == {"modo": "native"}
    assert ipc_calls == [], "o clique voltou a falar com o daemon"


# LÁPIDE — AGORA-E-DEPOIS-01 (08/08/2026). Aqui moravam
# `test_modo_gamepad_sai_do_nativo_e_liga_com_flavor` e
# `test_modo_desktop_desliga_nativo_e_gamepad_preservando_coop`: os dois
# afirmavam a SEQUÊNCIA de IPC que o clique no seletor disparava. O clique não
# dispara mais nada — quem aplica é o botão "Aplicar" do rodapé.
#
# A sequência NÃO deixou de ser testada, e é por isso que estes dois puderam
# sair em vez de virar remendo: `test_mode_transition_um_dono.py` a trava na
# fonte (`plan_mode_transition`, incluindo o co-op preservado do
# FEAT-COOP-DEFAULT-ON-01 e o mouse religado do HARM-06), e
# `test_agora_e_depois_01.py` trava que o "Aplicar" a dispara.


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
    """AGORA-E-DEPOIS-01: o clique na máscara registra e para por aí.

    Era o defeito 2 dela, na palavra dela: *"clicar em dualsense ainda pede pra
    aplicar agora, ao invés de ser só no botão aplicar"*.
    """
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
        """Os três modos: nenhum deles fala em `coop.set`.

        AGORA-E-DEPOIS-01: a guarda de "o teste exercitou algo" era
        ``ipc_calls != []`` — e ela caducou junto com o IPC do clique. No lugar
        dela vai a prova nova de que o caminho rodou: a escolha ficou marcada.
        Sem alguma prova aqui, este teste passaria com os handlers apagados.
        """
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
