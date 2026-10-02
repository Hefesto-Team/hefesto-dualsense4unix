"""`_render_home` vs o estado do daemon — os dois jeitos que a aba Início mentia."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_render_state: importa código da janela GTK")

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _render_ponte_e_divergencia = HomeActionsMixin._render_ponte_e_divergencia
    _mascara_escolhida_por_ela = HomeActionsMixin._mascara_escolhida_por_ela
    _mascara_escolhida_com_fonte = HomeActionsMixin._mascara_escolhida_com_fonte
    _refresh_home_tab = HomeActionsMixin._refresh_home_tab

    def __init__(self) -> None:
        self._home_installed = True
        self._home_inflight = False
        self._home_guard = False
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()
        self._home_vpad_banner = _FakeWidget()
        self._home_wrapper_banner = _FakeWidget()
        self._home_shutdown_btn = _FakeWidget()
        self._home_offline = False
        # "Reconciliar jogadores" + aviso de jogo aberto. (Até 06/08/2026 este
        # par se chamava `_home_renumber_btn`/`_home_renumber_hint`, quando o
        # botão só sabia renumerar.)
        self._home_reconciliar_btn = _FakeWidget()
        self._home_reconciliar_hint = _FakeWidget()
        self._home_ponte_label = _FakeWidget()
        self._home_divergencia_banner = _FakeWidget()
        self._home_flavor_pedido: str | None = None


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _state(controllers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
        "native_mode": False,
        "coop": {"enabled": True, "players": len(controllers)},
        "controllers": controllers,
    }


def _card_labels(host: _HomeStub) -> list[str]:
    return [
        str(child.label)
        for card in host._home_controllers_box.get_children()
        for child in ([card, *card.children])
    ]


class TestCardFantasma:
    def test_entrada_desconectada_nao_vira_card(self, fake_gtk: None) -> None:
        """O payload de "nenhum controle" é uma entrada com connected=False."""
        host = _HomeStub()

        host._render_home(
            _state([{"index": 0, "connected": False, "transport": None,
                     "is_primary": True}])
        )

        (placeholder,) = host._home_controllers_box.get_children()
        assert placeholder.label == "Nenhum controle conectado."

    def test_so_os_conectados_viram_card(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True, "battery_pct": 95},
                    {"index": 1, "connected": False, "transport": "bt",
                     "is_primary": False},
                ]
            )
        )

        cards = host._home_controllers_box.get_children()
        assert len(cards) == 1
        assert any("USB" in label for label in _card_labels(host))

    def test_controles_conectados_seguem_renderizando(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True},
                    {"index": 1, "connected": True, "transport": "bt",
                     "is_primary": False},
                ]
            )
        )

        assert len(host._home_controllers_box.get_children()) == 2


class TestBannerJogoSemWrapper:
    """GUI-05 item 3: o `_render_home` liga/desliga o banner do wrapper a
    partir do `gamepad_emulation.wrapper_used` (contrato da lane do daemon:
    False = jogo aberto sem o hefesto-launch; True/None/ausente = sem banner).
    """

    def _estado(self, wrapper_used: object) -> dict[str, Any]:
        estado = _state([])
        if wrapper_used is not None:
            estado["gamepad_emulation"]["wrapper_used"] = wrapper_used
        return estado

    def test_false_acende_o_banner_com_o_texto_pro_leigo(
        self, fake_gtk: None
    ) -> None:
        host = _HomeStub()

        host._render_home(self._estado(False))

        banner = host._home_wrapper_banner
        assert banner.visible is True
        assert banner.get_text() == home_actions.WRAPPER_MISSING_TEXT
        assert "atalho de inicialização" in banner.get_text()

    @pytest.mark.parametrize("valor", [True, None, "false", 0])
    def test_qualquer_coisa_que_nao_seja_false_literal_apaga(
        self, fake_gtk: None, valor: object
    ) -> None:
        """True = caso bom; None/ausente = sem jogo (ou daemon antigo sem o"""
        host = _HomeStub()

        host._render_home(self._estado(valor))

        assert host._home_wrapper_banner.visible is False

    def test_offline_apaga_o_banner(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_wrapper_banner.visible = True

        host._render_home(None)

        assert host._home_wrapper_banner.visible is False


class TestRefreshTimeout:
    def test_state_full_pede_folga_maior_que_o_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com o default de 0,25s a aba declarava o daemon morto sob carga."""
        calls: list[tuple[str, float]] = []

        def _fake_call_async(
            method: str,
            _params: dict[str, Any] | None,
            _done: Any = None,
            _fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            calls.append((method, timeout_s))

        monkeypatch.setattr(home_actions, "call_async", _fake_call_async)
        host = _HomeStub()

        host._refresh_home_tab()

        assert calls == [("daemon.state_full", home_actions._STATE_IPC_TIMEOUT_S)]
        assert home_actions._STATE_IPC_TIMEOUT_S > 0.25


def test_glossario_manda_ligar_nesta_propria_aba() -> None:
    """ONDA-U (U1): a Início GANHOU o botão de ligar — toggle in-place."""
    assert "nesta aba" in home_actions._GLOSSARY
    assert "aba Sistema" not in home_actions._GLOSSARY


class TestTogglePowerInPlace:
    """U1: o botão "Desligar Hefesto" vira "Ligar o Hefesto" quando offline —"""

    def test_offline_troca_rotulo_e_estilo_para_ligar(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(None)

        btn = host._home_shutdown_btn
        assert btn.get_label() == home_actions._BTN_LABEL_OFFLINE
        assert "suggested-action" in btn.style.classes
        assert "destructive-action" not in btn.style.classes
        assert host._home_offline is True

    def test_online_devolve_rotulo_e_estilo_de_desligar(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._render_home(None)

        host._render_home(_state([]))

        btn = host._home_shutdown_btn
        assert btn.get_label() == home_actions._BTN_LABEL_ONLINE
        assert "destructive-action" in btn.style.classes
        assert "suggested-action" not in btn.style.classes
        assert host._home_offline is False

    def test_offline_nao_manda_mais_pra_aba_sistema(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(None)

        assert host._home_session_label.get_text() == "O Hefesto está desligado."


class TestPowerClickDispatcher:
    """U1: `_on_home_power_clicked` decide entre ligar (reusa"""

    def test_offline_chama_on_daemon_start_com_o_botao(self) -> None:
        host = _HomeStub()
        host._home_offline = True
        calls: list[object] = []
        host.on_daemon_start = lambda btn: calls.append(btn)  # type: ignore[attr-defined]
        shutdown_calls: list[object] = []
        host._on_home_shutdown_clicked = lambda btn: shutdown_calls.append(btn)  # type: ignore[method-assign]
        button = object()

        HomeActionsMixin._on_home_power_clicked(host, button)  # type: ignore[arg-type]

        assert calls == [button]
        assert shutdown_calls == []

    def test_online_chama_o_fluxo_de_desligar_existente(self) -> None:
        host = _HomeStub()
        host._home_offline = False
        shutdown_calls: list[object] = []
        host._on_home_shutdown_clicked = lambda btn: shutdown_calls.append(btn)  # type: ignore[method-assign]
        button = object()

        HomeActionsMixin._on_home_power_clicked(host, button)  # type: ignore[arg-type]

        assert shutdown_calls == [button]

    def test_offline_sem_on_daemon_start_nao_quebra(self) -> None:
        """getattr defensivo: se o mixin de daemon não estiver composto (não"""
        host = _HomeStub()
        host._home_offline = True

        HomeActionsMixin._on_home_power_clicked(host, object())  # type: ignore[arg-type]


class TestReconciliarButtonGate:
    """COOP-SEM-INTERRUPTOR-01 (06/08) — "Reconciliar jogadores" fica DE PÉ com"""

    def test_offline_desabilita_sem_aviso(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(None)

        assert host._home_reconciliar_btn.sensitive is False
        assert host._home_reconciliar_hint.get_text() == ""

    def test_online_sem_jogo_habilita(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(_state([]))

        assert host._home_reconciliar_btn.sensitive is True
        assert host._home_reconciliar_hint.get_text() == ""

    def test_jogo_aberto_mantem_o_botao_e_explica_o_que_nao_muda(
        self, fake_gtk: None
    ) -> None:
        host = _HomeStub()
        estado = _state([])
        estado["game_signal"] = {"authority": "game"}

        host._render_home(estado)

        assert host._home_reconciliar_btn.sensitive is True, (
            "com jogo aberto o botão sumiu — é justamente quando o P2 cai"
        )
        assert (
            host._home_reconciliar_hint.get_text()
            == home_actions.RECONCILIAR_JOGO_ABERTO_TEXT
        )

    def test_authority_daemon_habilita(self, fake_gtk: None) -> None:
        host = _HomeStub()
        estado = _state([])
        estado["game_signal"] = {"authority": "daemon"}

        host._render_home(estado)

        assert host._home_reconciliar_btn.sensitive is True


class TestReconciliarClickHandler:
    """COOP-SEM-INTERRUPTOR-01, entrega 5: um clique = ``coop.sync`` e depois"""

    def _stub_com_toasts(self) -> _HomeStub:
        host = _HomeStub()
        host.toasts: list[str] = []  # type: ignore[attr-defined]
        host._status_toast = lambda _ctx, msg: host.toasts.append(msg)  # type: ignore[method-assign]
        host._refresh_home_tab = lambda: None  # type: ignore[method-assign]
        return host

    def _encadeia(
        self, monkeypatch: pytest.MonkeyPatch, respostas: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        """`call_async` que responde SUCESSO com a resposta gravada para cada método, na ordem."""
        chamadas: list[tuple[str, dict[str, Any]]] = []

        def _fake(
            method: str,
            params: dict[str, Any] | None,
            done: Any = None,
            _fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            chamadas.append((method, dict(params or {})))
            if done is not None and method in respostas:
                done(respostas[method])

        monkeypatch.setattr(home_actions, "call_async", _fake)
        return chamadas

    def test_a_ordem_e_a_entrega_coop_sync_antes_do_renumber(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Renumerar antes de reconciliar compactaria uma mesa incompleta."""
        chamadas = self._encadeia(
            monkeypatch,
            {
                "coop.sync": {"status": "ok", "players": 3, "active": True},
                "identity.renumber": {"ok": True, "renumbered": {}},
            },
        )
        host = self._stub_com_toasts()

        HomeActionsMixin._on_home_reconciliar_clicked(host, object())  # type: ignore[arg-type]

        assert [m for m, _p in chamadas] == ["coop.sync", "identity.renumber"]
        assert chamadas[0][1] == {} and chamadas[1][1] == {}

    def test_o_renumber_so_sai_depois_da_resposta_do_coop_sync(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Encadeado, não paralelo: sem resposta do sync, o acabamento não sai."""
        chamadas = self._encadeia(monkeypatch, {})

        HomeActionsMixin._on_home_reconciliar_clicked(  # type: ignore[arg-type]
            self._stub_com_toasts(), object()
        )

        assert [m for m, _p in chamadas] == ["coop.sync"]

    def test_toast_unico_conta_jogadores_e_numeracao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._encadeia(
            monkeypatch,
            {
                "coop.sync": {"status": "ok", "players": 4, "active": True},
                "identity.renumber": {
                    "ok": True,
                    "renumbered": {"aabbcc000001": 1, "aabbcc000002": 2},
                },
            },
        )
        host = self._stub_com_toasts()

        HomeActionsMixin._on_home_reconciliar_clicked(host, object())  # type: ignore[arg-type]

        assert host.toasts == [  # type: ignore[attr-defined]
            "Jogadores reconciliados — 4 jogador(es). "
            "Numeração compactada em 2 controle(s)."
        ]

    def test_renumber_recusado_por_jogo_aberto_nao_vira_falha_do_gesto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com os jogadores JÁ de pé, um toast de erro seria a UI mentindo."""
        self._encadeia(
            monkeypatch,
            {
                "coop.sync": {"status": "ok", "players": 2, "active": True},
                "identity.renumber": {
                    "ok": False,
                    "reason": "sessao_de_jogo_aberta",
                },
            },
        )
        host = self._stub_com_toasts()

        HomeActionsMixin._on_home_reconciliar_clicked(host, object())  # type: ignore[arg-type]

        (toast,) = host.toasts  # type: ignore[attr-defined]
        assert "Jogadores reconciliados — 2 jogador(es)." in toast
        assert "jogo fechado" in toast
        assert "Não consegui" not in toast

    def test_falha_do_coop_sync_avisa_daemon_desligado_e_nao_renumera(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamadas: list[str] = []

        def _fake(
            method: str,
            _params: dict[str, Any] | None,
            _done: Any = None,
            fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            chamadas.append(method)
            if fail is not None:
                fail(RuntimeError("timeout"))

        monkeypatch.setattr(home_actions, "call_async", _fake)
        host = self._stub_com_toasts()

        HomeActionsMixin._on_home_reconciliar_clicked(host, object())  # type: ignore[arg-type]

        assert chamadas == ["coop.sync"]
        assert any("desligado" in t for t in host.toasts)  # type: ignore[attr-defined]

    def test_cada_passo_leva_o_timeout_longo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Criar/desmontar uinput e grab não cabe nos 0,25 s do default."""
        prazos: list[float] = []

        def _fake(
            method: str,
            _params: dict[str, Any] | None,
            done: Any = None,
            _fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            prazos.append(timeout_s)
            if method == "coop.sync" and done is not None:
                done({"status": "ok", "players": 2, "active": True})

        monkeypatch.setattr(home_actions, "call_async", _fake)

        HomeActionsMixin._on_home_reconciliar_clicked(  # type: ignore[arg-type]
            self._stub_com_toasts(), object()
        )

        assert prazos == [home_actions._MODE_IPC_TIMEOUT_S] * 2


class TestReconciliarToast:
    """A frase única do gesto — função pura (06/08/2026)."""

    def test_sem_numero_de_jogadores_nao_inventa_contagem(self) -> None:
        frase = home_actions.reconciliar_toast(None, {"ok": True, "renumbered": {}})

        assert frase.startswith("Jogadores reconciliados.")
        assert "jogador(es)" not in frase

    def test_bool_nao_passa_por_contagem(self) -> None:
        """`True` é `int` em Python — "1 jogador(es)" seria mentira de tipo."""
        frase = home_actions.reconciliar_toast(True, {"ok": True, "renumbered": {}})

        assert frase.startswith("Jogadores reconciliados.")

    def test_numeracao_ja_compacta(self) -> None:
        frase = home_actions.reconciliar_toast(2, {"ok": True, "renumbered": {}})

        assert frase == (
            "Jogadores reconciliados — 2 jogador(es). "
            "A numeração já estava compacta."
        )

    def test_acabamento_sem_resposta_nao_afirma_numeracao(self) -> None:
        frase = home_actions.reconciliar_toast(2, None)

        assert "Jogadores reconciliados — 2 jogador(es)." in frase
        assert "Não consegui conferir a numeração." in frase


class TestMascaraTemUmDonoSo:
    """AUTO-01.3 — a janela ECOA a máscara do daemon; nunca escolhe por ela."""

    def test_reflete_a_mascara_que_o_daemon_reporta(self, fake_gtk: None) -> None:
        host = _HomeStub()

        estado = _state([])
        estado["gamepad_emulation"] = {"enabled": True, "flavor": "dualsense"}
        host._render_home(estado)

        assert host._home_flavor_selector.active_id == "dualsense"

    def test_payload_sem_mascara_nao_reescreve_o_seletor(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_flavor_selector.active_id = "dualsense"

        estado = _state([])
        estado["gamepad_emulation"] = {"enabled": True}
        host._render_home(estado)

        assert host._home_flavor_selector.active_id == "dualsense"


class TestOBotaoDeCoopSaiuDaAbaInicio:
    """COOP-SEM-INTERRUPTOR-01 (06/08/2026) — LÁPIDE de ``TestBotaoDeCoopNaAbaInicio``.

    Aquela classe mediu o rótulo e a sensibilidade do botão "Preparar co-op"
    (AUTO-01.2, 25/07). O botão saiu por decisão dela — o co-op deixou de ser
    opção —, então o que sobra a medir é o CONTRÁRIO: que o `_render_home` não
    voltou a procurar os widgets, e que a frase que ficou no lugar continua
    contando os jogadores a partir do `state_full`.
    """

    def test_o_render_nao_toca_mais_em_widget_de_coop(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True, "player": 1},
                    {"index": 1, "connected": True, "transport": "usb",
                     "is_primary": False, "player": 2},
                ]
            )
        )

        assert not hasattr(host, "_home_coop_prep_btn")
        assert not hasattr(host, "_home_coop_prep_hint")
        assert not hasattr(HomeActionsMixin, "_render_coop_prep")
        assert not hasattr(HomeActionsMixin, "_on_home_coop_prep_clicked")

    def test_a_frase_que_ficou_no_lugar_conta_do_state_full(
        self, fake_gtk: None
    ) -> None:
        host = _HomeStub()

        host._render_home(
            _state(
                [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True, "player": 1},
                    {"index": 1, "connected": True, "transport": "usb",
                     "is_primary": False, "player": 2},
                ]
            )
        )

        assert host._home_players_hint.get_text() == "2 controles = 2 jogadores"

    def test_daemon_desligado_cala_a_frase(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(None)

        assert host._home_players_hint.get_text() == ""
