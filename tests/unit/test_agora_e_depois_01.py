"""AGORA E DEPOIS — a escolha dela para de voltar sozinha, e o clique para de aplicar."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("AGORA-E-DEPOIS-01: a escolha pendente")

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import (
    daemon_actions,
    footer_actions,
    home_actions,
    mode_transition,
    relancar,
)
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig


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
    """O subconjunto de `Gtk` que o `_render_home` toca."""

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

    def get_active_id(self) -> str | None:
        return self.active_id

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


class _Janela:
    """A aba Início com os widgets falsos — render E handlers na mesma casca."""

    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _on_home_mode_changed = HomeActionsMixin._on_home_mode_changed
    _on_home_flavor_changed = HomeActionsMixin._on_home_flavor_changed

    def __init__(self) -> None:
        self._home_installed = True
        self._home_inflight = False
        self._home_guard = False
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = None
        self._mascara_vigente_do_daemon: str | None = None
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_flavor_custo = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()
        self._home_pendente_label = _FakeWidget()
        self._home_vpad_banner = _FakeWidget()
        self._home_wrapper_banner = _FakeWidget()
        self._home_shutdown_btn = _FakeWidget()
        self._home_offline = False
        self._home_reconciliar_btn = _FakeWidget()
        self._home_reconciliar_hint = _FakeWidget()
        self.toasts: list[str] = []

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_home_tab(self) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


@pytest.fixture()
def sem_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Grava toda chamada IPC dos dois módulos que a aba Início usava."""
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None = None,
        _done: Any = None,
        _fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))

    monkeypatch.setattr(home_actions, "call_async", _fake)
    monkeypatch.setattr(mode_transition, "call_async", _fake)
    return chamadas


def _estado(
    *, modo: str = "gamepad", mascara: str = "dualsense", jogo: bool = False
) -> dict[str, Any]:
    return {
        "gamepad_emulation": {"enabled": modo == "gamepad", "flavor": mascara},
        "native_mode": modo == "native",
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
        ],
        "game_signal": {"authority": "game" if jogo else "daemon"},
    }


class TestAEscolhaDelaNaoVoltaSozinha:
    def test_dois_tiques_seguidos_nao_mexem_no_que_o_seletor_mostra(
        self, fake_gtk: None
    ) -> None:
        """O teste do plano, literal — e o coração do desenho."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="gamepad"))
        janela._render_home(_estado(modo="gamepad"))

        assert janela._home_mode_selector.active_id == "desktop", (
            "o tique do daemon reescreveu a escolha dela — é o defeito que "
            "derrubou a cura óbvia do defeito 2 da OITO-DEFEITOS-01."
        )

    def test_a_mascara_escolhida_tambem_resiste_ao_tique(
        self, fake_gtk: None
    ) -> None:
        janela = _Janela()
        janela._render_home(_estado(mascara="dualsense"))
        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        janela._render_home(_estado(mascara="dualsense"))

        assert janela._home_flavor_selector.active_id == "xbox"

    def test_sem_pendencia_a_caixa_continua_ecoando_o_daemon(
        self, fake_gtk: None
    ) -> None:
        """O contrapeso, e ele é obrigatório."""
        janela = _Janela()

        janela._render_home(_estado(modo="native", mascara="xbox"))

        assert janela._home_mode_selector.active_id == "native"
        assert janela._home_flavor_selector.active_id == "xbox"

    def test_a_caixa_da_mascara_nasce_com_a_escolha_dela(
        self, fake_gtk: None
    ) -> None:
        """Decisão 2 dela, REVISTA em 08/08 à noite — vendo a tela."""
        janela = _Janela()
        janela._render_home(_estado(modo="desktop"))
        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="desktop"))

        assert janela._home_gamepad_opts.visible is True, (
            "a caixa da máscara sumiu depois de ela escolher 'Jogar pelo "
            "Hefesto' — é o defeito que ela viu na tela em 08/08."
        )

    def test_saindo_do_modo_jogo_a_caixa_da_mascara_some(
        self, fake_gtk: None
    ) -> None:
        """O contrapeso: seguir a escolha vale para os DOIS lados."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="gamepad"))

        assert janela._home_gamepad_opts.visible is False

    def test_o_custo_mostrado_e_o_da_mascara_que_ela_escolheu(
        self, fake_gtk: None
    ) -> None:
        """MASCARA-CUSTO-01 continua respondendo a pergunta certa."""
        janela = _Janela()
        janela._render_home(_estado(mascara="dualsense"))
        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        janela._render_home(_estado(mascara="dualsense"))

        esperado = home_actions.texto_do_custo_da_mascara("xbox")
        assert janela._home_flavor_custo.label == esperado

    def test_quando_o_daemon_alcanca_a_escolha_a_pendencia_some(
        self, fake_gtk: None
    ) -> None:
        """A pendência é uma DIVERGÊNCIA, não uma marca permanente."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)
        assert janela._escolha_pendente == {"modo": "desktop"}

        janela._render_home(_estado(modo="desktop"))

        assert janela._escolha_pendente is None
        assert janela._home_pendente_label.visible is False

    def test_daemon_desligado_esconde_a_linha_e_preserva_a_escolha(
        self, fake_gtk: None
    ) -> None:
        """Offline não é "ela desistiu"."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(None)

        assert janela._home_pendente_label.visible is False
        assert janela._escolha_pendente == {"modo": "desktop"}


class TestOCliqueSoMarca:
    def test_clicar_no_modo_nao_produz_ipc_nenhum(
        self, fake_gtk: None, sem_ipc: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O teste do passo 2, literal."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        sem_ipc.clear()

        janela._home_mode_selector.set_active_id("native")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert sem_ipc == [], (
            f"o clique no seletor de modo ainda fala com o daemon: {sem_ipc}"
        )

    def test_clicar_na_mascara_nao_produz_ipc_nenhum(
        self, fake_gtk: None, sem_ipc: list[tuple[str, dict[str, Any]]]
    ) -> None:
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))
        sem_ipc.clear()

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        assert sem_ipc == []

    def test_o_clique_marca_a_escolha_com_a_aridade_real_do_sinal(
        self, fake_gtk: None
    ) -> None:
        """BUG-HOME-SEGMENTED-SIGNATURE-01 continua travado."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)
        janela._home_mode_selector.set_active_id("native")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente == {"mascara": "xbox", "modo": "native"}

    def test_fora_de_jogar_pelo_hefesto_a_mascara_nao_marca_nada(
        self, fake_gtk: None
    ) -> None:
        """A máscara só existe DENTRO de "Jogar pelo Hefesto"."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        assert janela._escolha_pendente == {"modo": "desktop"}

    def test_o_guard_do_render_nao_vira_escolha_dela(self, fake_gtk: None) -> None:
        """O `_home_guard` continua indispensável — e não foi substituído."""
        janela = _Janela()
        janela._home_guard = True
        janela._home_mode_selector.set_active_id("native")

        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente is None

    def test_voltar_ao_que_ja_esta_valendo_desfaz_a_pendencia(
        self, fake_gtk: None
    ) -> None:
        """Escolher o que já vale não é pendência — e o rodapé diz isso."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente is None
        assert janela.toasts[-1] == relancar.TOAST_ESCOLHA_DESFEITA


class TestALinhaDoPendente:
    def test_a_frase_pura_compoe_os_dois_campos(self) -> None:
        assert relancar.texto_do_pendente() == ""
        so_modo = relancar.texto_do_pendente(modo="Jogar pelo Hefesto")
        assert "vai mudar para" in so_modo and "Jogar pelo Hefesto" in so_modo
        dois = relancar.texto_do_pendente(
            modo="Jogar pelo Hefesto", mascara="DualSense (botões PlayStation)"
        )
        assert "Jogar pelo Hefesto" in dois and "DualSense" in dois

    def test_a_frase_usa_o_lexico_da_tela_e_nao_os_ids(
        self, fake_gtk: None
    ) -> None:
        """Ela recusa nome que não deriva do que já existe na janela."""
        janela = _Janela()
        janela._render_home(_estado(modo="desktop", mascara="dualsense"))
        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        texto = str(janela._home_pendente_label.label)
        assert "Jogar pelo Hefesto" in texto
        assert "gamepad" not in texto

    def test_a_linha_acende_no_clique_e_apaga_sem_pendencia(
        self, fake_gtk: None
    ) -> None:
        """Sem esta linha o plano vira defeito."""
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        assert janela._home_pendente_label.visible is False

        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._home_pendente_label.visible is True
        assert janela.toasts[-1] == relancar.TOAST_ESCOLHA_ANOTADA


class _Dialogo:
    """Captura o diálogo em vez de abri-lo, e deixa o teste responder por ela."""

    def __init__(self) -> None:
        self.aberto = False
        self.botoes: list[str] = []
        self._on_response: Any = None

    def construir(
        self,
        _parent: Any,
        *,
        titulo: str,
        corpo: str,
        botoes: list[tuple[str, int]],
        on_response: Any,
        destrutivo: int | None = None,
    ) -> Any:
        self.aberto = True
        self.titulo = titulo
        self.corpo = corpo
        self.botoes = [rotulo for rotulo, _ in botoes]
        self._on_response = on_response
        return MagicMock()

    def responder(self, resposta: int) -> None:
        assert self._on_response is not None, "o diálogo não chegou a abrir"
        self._on_response(MagicMock(), resposta)


class _Rodape(FooterActionsMixin):
    """O rodapé com o mínimo da aba Início que ele lê — como na classe real."""

    def __init__(self, *, jogo_aberto: bool = False) -> None:
        self.draft = DraftConfig.default()
        self.window = None
        self._toasted: list[str] = []
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = "gamepad"
        self._mascara_vigente_do_daemon: str | None = "dualsense"
        self._jogo_aberto = jogo_aberto
        self._home_pendente_label = _FakeWidget()
        builder = MagicMock()
        builder.get_object.return_value = MagicMock()
        self.builder = builder

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        self._toasted.append(msg)

    def _reload_profiles_store(self, select_name: str | None = None) -> None:
        pass


@pytest.fixture()
def ipc_do_rodape(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, dict[str, Any]]]:
    """Grava o que sai pelos DOIS canos do "Aplicar": a transição e o rascunho."""
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _transicao(
        method: str,
        params: dict[str, Any] | None = None,
        on_done: Any = None,
        _on_fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))
        if on_done is not None:
            on_done({"status": "ok"})

    def _draft(
        method: str,
        params: dict[str, Any] | None = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, {}))
        if on_success is not None:
            on_success({"status": "ok", "applied": ["leds"]})

    monkeypatch.setattr(mode_transition, "call_async", _transicao)
    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _draft)
    return chamadas


class TestOBotaoVerdeAplicaOsDoisTempos:
    def test_sem_pendencia_o_aplicar_e_exatamente_o_de_sempre(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O caminho comum não pode ter ganhado peso nenhum."""
        rodape = _Rodape()

        rodape.on_apply_draft()

        assert [m for m, _ in ipc_do_rodape] == ["profile.apply_draft"]

    def test_com_pendencia_e_sem_jogo_a_transicao_vem_antes_do_rascunho(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """A ordem importa: o DEPOIS primeiro, o AGORA emendado no sucesso."""
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos
        assert metodos.index("gamepad.emulation.set") < metodos.index(
            "profile.apply_draft"
        )
        assert rodape._escolha_pendente is None

    def test_a_transicao_declara_que_o_gesto_e_dela(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """ORIGEM-QUE-MENTE-01: silêncio no protocolo significa "automático"."""
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        params = dict(ipc_do_rodape[0][1])
        for metodo, p in ipc_do_rodape:
            if metodo == "gamepad.emulation.set":
                params = dict(p)
        assert params.get("origin") == "manual"
        assert params.get("flavor") == "xbox"

    def test_o_modo_entra_no_rascunho_so_quando_o_aplicar_confirma(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Decisão 3 dela (08/08, noite)."""
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "desktop"}
        assert rodape.draft.to_profile("Perfil").mode is None

        rodape.on_apply_draft()

        salvo = rodape.draft.to_profile("Perfil")
        assert salvo.mode is not None, (
            "o modo não entrou no rascunho — 'Salvar este perfil' gravaria um "
            "perfil SEM a seção mode, em silêncio."
        )
        assert salvo.mode.kind == "desktop"

    def test_falha_na_transicao_preserva_a_escolha_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pendência FICA quando a transição falha."""

        def _falha(
            _method: str,
            _params: dict[str, Any] | None = None,
            _on_done: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(RuntimeError("daemon mudo"))

        monkeypatch.setattr(mode_transition, "call_async", _falha)
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert rodape._escolha_pendente == {"mascara": "xbox"}


class TestODialogoPerguntaUmaVezSoENoLugarCerto:
    @pytest.fixture()
    def dialogo(self, monkeypatch: pytest.MonkeyPatch) -> _Dialogo:
        dobro = _Dialogo()
        monkeypatch.setattr(
            daemon_actions, "build_consentimento_dialog", dobro.construir
        )
        return dobro

    def test_com_jogo_aberto_e_mascara_pendente_pergunta_e_nao_dispara_nada(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O teste do plano, literal — e o cenário dela."""
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert dialogo.aberto is True
        assert ipc_do_rodape == [], (
            f"algo saiu antes de ela responder: {ipc_do_rodape}"
        )
        assert dialogo.botoes == [
            relancar.ROTULO_CANCELAR,
            relancar.ROTULO_DEPOIS,
            relancar.ROTULO_FECHAR,
        ]

    def test_com_jogo_aberto_o_modo_sozinho_tambem_pergunta(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Decisão 1 dela, REVISTA em 08/08 à noite — com a tela na frente."""
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"modo": "desktop"}

        rodape.on_apply_draft()

        assert dialogo.aberto is True, (
            "trocar o modo com o jogo aberto voltou a aplicar direto, sem "
            "perguntar — é o caminho do 'Jogador 3' fantasma."
        )
        assert ipc_do_rodape == [], "algo saiu antes de ela responder"

    def test_sem_jogo_aberto_nada_pergunta(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O contrapeso do teste acima, e ele é obrigatório."""
        rodape = _Rodape(jogo_aberto=False)
        rodape._escolha_pendente = {"modo": "desktop", "mascara": "xbox"}

        rodape.on_apply_draft()

        assert dialogo.aberto is False
        assert [m for m, _ in ipc_do_rodape][:1] == ["native.mode.set"]

    def test_cancelar_recusa_o_relancamento_mas_o_agora_sai(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 — inverte o que este teste dizia."""
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(-6)

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" not in metodos, (
            "cancelar recriou o vpad — é o dano que o diálogo existe para evitar"
        )
        assert metodos == ["profile.apply_draft"], (
            "as cores/gatilhos que ela editou foram engolidos pelo Cancelar"
        )
        assert rodape._escolha_pendente == {"mascara": "xbox"}

    def test_aplicar_agora_dispara_a_transicao_e_o_rascunho(
        self,
        dialogo: _Dialogo,
        ipc_do_rodape: list[tuple[str, dict[str, Any]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        relancado: list[bool] = []
        monkeypatch.setattr(
            _Rodape, "_relancar_o_jogo", lambda self: relancado.append(True)
        )
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_FECHAR_E_ABRIR)

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos
        assert "profile.apply_draft" in metodos
        assert relancado == [True]

    def test_na_proxima_abertura_nao_recria_o_vpad_mas_aplica_o_agora(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """As duas metades desta saída, e as duas já custaram caro."""
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_DEPOIS)

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" not in metodos, (
            "o ramo 'na próxima abertura' recriou o vpad ao vivo — é o defeito "
            "DEPOIS-QUE-APLICAVA-AGORA-01 de volta."
        )
        assert metodos == ["profile.apply_draft"]

    def test_adiar_tira_a_linha_da_tela_para_ela_nao_contradizer_o_rodape(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Enquanto não houver onde guardar, a tela não pode fingir que guardou."""
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_DEPOIS)

        assert rodape._escolha_pendente is None
        assert rodape._home_pendente_label.visible is False


class TestValeParaQualquerMesa:
    """A separação dos dois tempos não pode depender de cabo nem de DualSense.

    Pedido dela, literal: *"cada decisão nossa não é pra funcionar só via cabo
    mas via bt também e deve ser universal, caso eu tenha 4 novos controles dual
    sense ou novos pro controler ou 8bitdo e afins"*.

    O modo e a máscara são do SISTEMA, não de um controle — mas isso é fácil de
    quebrar sem perceber, bastando alguém condicionar a pendência ao controle
    primário, ao transporte ou à contagem. Estes testes existem para que a
    quebra apareça no portão, e não numa partida com quatro controles.
    """

    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    @pytest.mark.parametrize("quantos", [1, 2, 4])
    def test_a_escolha_resiste_ao_tique_com_qualquer_mesa(
        self, fake_gtk: None, transporte: str, quantos: int
    ) -> None:
        janela = _Janela()
        estado = _estado(modo="gamepad", mascara="dualsense")
        estado["controllers"] = [
            {
                "index": i,
                "connected": True,
                "transport": transporte,
                "is_primary": i == 0,
                "player": i + 1,
                "player_slot": i + 1,
            }
            for i in range(quantos)
        ]
        janela._render_home(estado)

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)
        janela._render_home(estado)

        assert janela._escolha_pendente == {"mascara": "xbox"}
        assert janela._home_flavor_selector.active_id == "xbox"
        assert janela._home_pendente_label.visible is True

    def test_sem_controle_nenhum_a_escolha_continua_de_pe(
        self, fake_gtk: None
    ) -> None:
        """O caso extremo, e o que prova que NÃO há acoplamento."""
        janela = _Janela()
        estado = _estado(modo="desktop")
        estado["controllers"] = []
        janela._render_home(estado)

        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)
        janela._render_home(estado)

        assert janela._escolha_pendente == {"modo": "gamepad"}
        assert janela._home_mode_selector.active_id == "gamepad"
        assert janela._home_gamepad_opts.visible is True

    def test_o_aplicar_nao_olha_para_controle_nenhum(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O payload da transição é do SISTEMA — sem `uniq`, sem índice."""
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "gamepad", "mascara": "dualsense"}

        rodape.on_apply_draft()

        for metodo, params in ipc_do_rodape:
            assert "uniq" not in params, f"{metodo} virou por-controle: {params}"
            assert "index" not in params, f"{metodo} virou por-controle: {params}"
            assert "transport" not in params, f"{metodo} olhou o transporte"


class TestOAgoraNaoEeRefemDoDepois:
    """O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 (08/08/2026, noite)."""

    def test_transicao_que_falha_nao_engole_as_cores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O buraco principal, e ele era alcançável de verdade."""
        chamadas: list[str] = []

        def _transicao_que_falha(
            _method: str,
            _params: dict[str, Any] | None = None,
            _on_done: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(TimeoutError("2.0s"))

        def _draft(
            method: str,
            _params: dict[str, Any] | None = None,
            on_success: Any = None,
            on_failure: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            chamadas.append(method)
            if on_success is not None:
                on_success({"status": "ok", "applied": ["leds"]})

        monkeypatch.setattr(mode_transition, "call_async", _transicao_que_falha)
        monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _draft)
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert chamadas == ["profile.apply_draft"], (
            "a transição falhou e levou as sete seções junto — a cor dela some "
            "sem ninguém dizer nada."
        )
        assert rodape._escolha_pendente == {"mascara": "xbox"}

    def test_o_toast_da_falha_diz_que_o_resto_foi_aplicado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Metade da cura é o texto — senão ela fica sem saber o que valeu."""

        def _falha(
            _m: str,
            _p: dict[str, Any] | None = None,
            _d: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(TimeoutError("2.0s"))

        monkeypatch.setattr(mode_transition, "call_async", _falha)
        monkeypatch.setattr(
            footer_actions.ipc_bridge,
            "call_async",
            lambda *a, **k: None,
        )
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "gamepad"}

        rodape.on_apply_draft()

        assert any("resto dos ajustes foi aplicado" in t for t in rodape._toasted), (
            f"o toast não diz que o AGORA valeu: {rodape._toasted}"
        )

    def test_o_payload_e_montado_antes_de_congelar_a_janela(self) -> None:
        """A ordem que impede a janela de ficar com as cores insensíveis.

        `FROZEN_WIDGET_IDS` inclui `lightbar_color_button` e
        `lightbar_brightness_scale`. Congelar ANTES de montar o payload fazia
        uma falha de serialização subir com a UI travada — e os controles de cor
        ficavam mortos pelo resto da sessão. É, ao pé da letra, "não aplica mais
        as cores".

        ARRANQUE A CURA (volte o `_freeze_ui(True)` para antes do
        `to_ipc_dict()`) e este teste REPROVA.
        """
        ordem: list[str] = []

        class _RodapeQueQuebra(_Rodape):
            def _freeze_ui(self, freeze: bool) -> None:
                ordem.append(f"freeze={freeze}")

        rodape = _RodapeQueQuebra()

        class _DraftQueQuebra:
            def to_ipc_dict(self) -> dict[str, Any]:
                ordem.append("payload")
                raise RuntimeError("serialização quebrou")

        rodape.draft = _DraftQueQuebra()  # type: ignore[assignment]

        with pytest.raises(RuntimeError):
            rodape.on_apply_draft()

        assert ordem == ["payload"], (
            f"a janela foi congelada antes de o payload existir: {ordem}"
        )

    def test_dialogo_que_nao_nasce_devolve_o_gesto_em_vez_de_sumir(
        self, monkeypatch: pytest.MonkeyPatch, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Um clique que não faz nada, sem toast e sem log, é o pior desfecho."""

        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("sem tela")

        monkeypatch.setattr(daemon_actions, "build_consentimento_dialog", _explode)
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos and "profile.apply_draft" in metodos


class TestOJogoAbertoELidoNaHora:
    """JOGO-ABERTO-SO-NA-INICIO-01 (09/08/2026)."""

    def test_o_aplicar_rele_o_sinal_mesmo_sem_a_aba_inicio_ter_rodado(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ipc_do_rodape: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """O cenário exato: janela recém-aberta, ela nunca passou pela Início."""
        dialogo_falso = _Dialogo()
        monkeypatch.setattr(
            daemon_actions, "build_consentimento_dialog", dialogo_falso.construir
        )
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        monkeypatch.setattr(
            ponte,
            "_run_call",
            lambda *_a, **_k: {"game_signal": {"authority": "game"}},
        )
        rodape = _Rodape(jogo_aberto=False)
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert rodape._jogo_aberto is True, "o sinal não foi relido no clique"
        assert dialogo_falso.aberto is True, (
            "o diálogo não apareceu porque a aba Início não estava à vista — é o "
            "caminho do 'Jogador 3' fantasma de volta."
        )
        assert ipc_do_rodape == [], "algo saiu antes de ela responder"

    def test_leitura_que_falha_nao_muda_de_opiniao(
        self, monkeypatch: pytest.MonkeyPatch, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Fail-safe: IPC que engasga mantém o que já se sabia."""
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise ConnectionError("socket mudo")

        monkeypatch.setattr(ponte, "_run_call", _explode)
        rodape = _Rodape(jogo_aberto=False)
        rodape._escolha_pendente = {"modo": "desktop"}

        rodape.on_apply_draft()

        assert rodape._jogo_aberto is False
        assert [m for m, _ in ipc_do_rodape][:1] == ["native.mode.set"]

    def test_o_criterio_e_o_mesmo_da_aba_inicio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duas leituras do mesmo fato não podem discordar."""
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        for autoridade, esperado in (("game", True), ("daemon", False), (None, False)):
            monkeypatch.setattr(
                ponte,
                "_run_call",
                lambda *_a, _v=autoridade, **_k: {"game_signal": {"authority": _v}},
            )
            rodape = _Rodape(jogo_aberto=not esperado)
            assert rodape._ha_jogo_aberto_agora() is esperado, autoridade
