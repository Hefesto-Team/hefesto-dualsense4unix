"""PONTE-NA-TELA-01 — a aba Início não pode esconder a divergência nem a ponte.

Os dois defeitos de tela medidos na noite de 18→19/08/2026, com DON'T SCREAM
aberto:

1. ela escolheu "Xbox 360" em "O jogo vê o controle como:", e a janela seguiu
   dizendo que estava tudo certo enquanto o aparelho continuava DualSense — o
   gate R-04 do daemon havia RECUSADO a troca. O rodapé chegou a anunciar
   desfecho de sucesso sobre a recusa, porque `set_gamepad_emulation` devolve o
   mesmo ``True`` para "apliquei", "já estava" e "recusei";
2. a janela não dizia por ONDE o jogo recebia o controle. Sob a exceção de
   Steam Input o vpad é suspenso, ``gamepad_emulation.enabled`` cai para False e
   `mode_of_state` chama isso de "Controlar o PC" — a aba mostrava modo desktop
   com o jogo jogando pelo espelho da Steam.

Tudo hermético: as funções puras não tocam GTK, e os testes de render usam o
mesmo dublê de widget do `test_home_render_state`.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin

# --------------------------------------------------------------------------
# Dublês (mesmo desenho do test_home_render_state — widget burro, sem GTK)
# --------------------------------------------------------------------------


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
        self.markup: str | None = None
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
        self.markup = markup
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
    # COOP-SEM-INTERRUPTOR-01 (06/08/2026): o `_render_coop_prep` e o botão
    # "Preparar co-op" NÃO existem mais — cada controle conectado já é um
    # jogador, sempre. `test_home_render_state.py` tem portão que exige a
    # ausência dos dois. Não reponha.
    _render_ponte_e_divergencia = HomeActionsMixin._render_ponte_e_divergencia
    _mascara_escolhida_por_ela = HomeActionsMixin._mascara_escolhida_por_ela

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
        # O par foi RENOMEADO: era `_home_renumber_*`, virou `_home_reconciliar_*`
        # (o dublê desta frente nasceu de uma base anterior à renomeação). O
        # `test_home_render_state.py:140` registra a mesma história.
        self._home_reconciliar_btn = _FakeWidget()
        self._home_reconciliar_hint = _FakeWidget()
        # PONTE-NA-TELA-01
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


def _estado(
    *,
    flavor: str = "dualsense",
    enabled: bool = True,
    jogo_aberto: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    estado: dict[str, Any] = {
        "gamepad_emulation": {"enabled": enabled, "flavor": flavor},
        "native_mode": False,
        "controllers": [],
    }
    if jogo_aberto:
        estado["game_signal"] = {"authority": "game"}
    estado.update(extra)
    return estado


# --------------------------------------------------------------------------
# Defeito 1 — o desfecho: "aplicado" NUNCA sobre uma recusa
# --------------------------------------------------------------------------


class TestDesfechoDaTroca:
    def test_payload_legado_com_a_mascara_antiga_e_recusa(self) -> None:
        """A cura que vale HOJE, sem daemon novo.

        O handler já devolve ``flavor: config.gamepad_flavor``, e o daemon só
        grava esse campo DEPOIS de o vpad novo nascer — logo uma troca recusada
        pelo gate volta com a máscara ANTIGA junto de ``status: "ok"``.
        """
        recusa = {"status": "ok", "enabled": True, "flavor": "dualsense"}

        assert (
            home_actions.desfecho_da_troca(recusa, pedida="xbox")
            == home_actions.DESFECHO_BLOQUEADO
        )

    def test_payload_legado_com_a_mascara_pedida_e_aplicacao(self) -> None:
        ok = {"status": "ok", "enabled": True, "flavor": "xbox"}

        assert (
            home_actions.desfecho_da_troca(ok, pedida="xbox")
            == home_actions.DESFECHO_APLICADO
        )

    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("bloqueado_por_jogo", home_actions.DESFECHO_BLOQUEADO),
            ("blocked_by_game", home_actions.DESFECHO_BLOQUEADO),
            ("ja_estava", home_actions.DESFECHO_JA_ESTAVA),
            ("aplicado", home_actions.DESFECHO_APLICADO),
        ],
    )
    def test_campo_explicito_vence(self, bruto: str, esperado: str) -> None:
        """O contrato distinguível da lane do daemon, consumido defensivamente.

        Vence até quando a máscara devolvida diria outra coisa: quem sabe o
        desfecho é quem o produziu.
        """
        payload = {"status": "ok", "flavor": "xbox", "desfecho": bruto}

        assert home_actions.desfecho_da_troca(payload, pedida="xbox") == esperado

    def test_sem_dado_nenhum_e_incerto_nunca_aplicado(self) -> None:
        """Sem campo e sem máscara devolvida não se INFERE sucesso."""
        assert (
            home_actions.desfecho_da_troca({"status": "ok"}, pedida="xbox")
            == home_actions.DESFECHO_INCERTO
        )
        assert (
            home_actions.desfecho_da_troca(None, pedida="xbox")
            == home_actions.DESFECHO_INCERTO
        )


class TestToastDaTroca:
    def test_bloqueado_nao_diz_que_aplicou(self) -> None:
        frase = home_actions.toast_da_troca_de_mascara(
            home_actions.DESFECHO_BLOQUEADO, "xbox"
        )

        assert "agora vê" not in frase
        assert "Ainda não" in frase
        assert "Xbox 360" in frase
        assert "abrir de novo" in frase

    def test_aplicado_mantem_a_frase_que_ela_ja_conhece(self) -> None:
        assert (
            home_actions.toast_da_troca_de_mascara(
                home_actions.DESFECHO_APLICADO, "xbox"
            )
            == "O jogo agora vê: Xbox 360"
        )

    def test_incerto_nao_promete(self) -> None:
        frase = home_actions.toast_da_troca_de_mascara(
            home_actions.DESFECHO_INCERTO, "dualsense"
        )

        assert "agora vê" not in frase
        assert "Pedi a troca" in frase


# AGORA-E-DEPOIS-01 (08/08/2026) — a classe `TestHandlerDaMascara` foi REMOVIDA
# em 19/08. NÃO a reponha.
#
# Ela exercitava `_on_home_flavor_changed` esperando que o seletor da aba Início
# DISPARASSE um `gamepad.emulation.set` e anunciasse "O jogo agora vê: …". Esse
# caminho não existe mais: o commit `1c75a1a` o tirou por decisão dela —
# *"Nenhum IPC sai de um seletor da aba Início"* —, e o seletor hoje só anota a
# escolha ("Anotado. Clique em Aplicar para valer"). Um teste que exija o IPC de
# volta reprova a decisão, não o código.
#
# O QUE A FRENTE QUERIA — que uma RECUSA do gate não vire toast de sucesso —
# não se perdeu: virou as funções puras `desfecho_da_troca` e
# `toast_da_troca_de_mascara`, e a mordida delas vive em `TestDesfechoDaTroca` e
# `TestToastDaTroca`, logo acima. Quem HOJE tem a resposta do daemon na mão é o
# "Aplicar" do rodapé, e é lá que a frase é escolhida.


class TestTextoDaDivergencia:
    def test_com_jogo_aberto_diz_as_duas_mascaras_e_o_caminho(self) -> None:
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=True
        )

        assert frase is not None
        assert "Xbox 360" in frase
        assert "DualSense (botões PlayStation)" in frase
        assert "abrir de novo" in frase

    def test_sem_jogo_aberto_a_frase_e_outra(self) -> None:
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=False
        )

        assert frase is not None
        assert "não chegou ao aparelho" in frase

    def test_a_cor_vem_por_markup_e_nao_por_classe_de_css(self) -> None:
        """A armadilha que a foto offscreen pegou nesta leva.

        `.hefesto-dualsense4unix-window label { color: #f8f8f2 }`
        (`theme.css:470`, 0,1,1) vence `.hefesto-dualsense4unix-status-warn`
        (0,1,0) — a mesma armadilha que a própria theme.css documenta no
        BUG-GUI-FOOTER-LABEL-BRANCO-01. Com a classe, o aviso saía branco:
        um alerta indistinguível do texto ao lado é um alerta escondido, que é
        exatamente o defeito que esta leva existe para curar.
        """
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=True
        )

        assert frase is not None
        assert '<span foreground="#ffb86c">' in frase

    def test_iguais_nao_e_divergencia(self) -> None:
        assert (
            home_actions.texto_da_divergencia("xbox", "xbox", jogo_aberto=True)
            is None
        )

    @pytest.mark.parametrize(
        ("escolhida", "no_aparelho"),
        [(None, "xbox"), ("xbox", None), ("", "xbox"), ("xbox", "")],
    )
    def test_meia_informacao_nunca_acusa(
        self, escolhida: object, no_aparelho: object
    ) -> None:
        """Sem as duas pontas não há divergência a afirmar (nada de alarme falso)."""
        assert (
            home_actions.texto_da_divergencia(
                escolhida, no_aparelho, jogo_aberto=True
            )
            is None
        )


class TestMascaraDoAparelho:
    def test_backend_uhid_significa_dualsense_vivo(self) -> None:
        """`virtual_pad._try_uhid` recusa o uhid para Xbox — uhid é DualSense."""
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["backend"] = "uhid"

        assert home_actions.mascara_viva(estado) == "dualsense"
        assert home_actions.mascara_do_aparelho(estado) == "dualsense"

    def test_backend_uinput_e_ambiguo_e_cai_no_flavor_do_payload(self) -> None:
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["backend"] = "uinput"

        assert home_actions.mascara_viva(estado) is None
        assert home_actions.mascara_do_aparelho(estado) == "xbox"

    def test_campo_explicito_do_daemon_vence(self) -> None:
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["flavor_vivo"] = "dualsense"

        assert home_actions.mascara_do_aparelho(estado) == "dualsense"


class TestRenderDaDivergencia:
    def test_escolha_recusada_acende_o_banner(self, fake_gtk: None) -> None:
        """O defeito literal: Xbox escolhido, aparelho DualSense, jogo aberto."""
        host = _HomeStub()
        host._home_flavor_pedido = "xbox"

        host._render_home(_estado(flavor="dualsense", jogo_aberto=True))

        banner = host._home_divergencia_banner
        assert banner.visible is True
        assert "Xbox 360" in banner.get_text()
        assert "DualSense (botões PlayStation)" in banner.get_text()
        # Por MARKUP, senão o aviso sai branco (ver a nota de especificidade).
        assert banner.markup is not None
        assert '<span foreground="#ffb86c">' in banner.markup

    def test_convergencia_apaga_o_banner_e_esquece_o_pedido(
        self, fake_gtk: None
    ) -> None:
        host = _HomeStub()
        host._home_flavor_pedido = "xbox"

        host._render_home(_estado(flavor="xbox", jogo_aberto=True))

        assert host._home_divergencia_banner.visible is False
        assert host._home_flavor_pedido is None

    def test_perfil_divergente_tambem_acende(self, fake_gtk: None) -> None:
        """A divergência medida na noite: o perfil dizia xbox, o vpad dualsense."""
        host = _HomeStub()
        host.draft = SimpleNamespace(  # type: ignore[attr-defined]
            source_mode=SimpleNamespace(kind="gamepad", gamepad_flavor="xbox")
        )

        host._render_home(_estado(flavor="dualsense", jogo_aberto=True))

        assert host._home_divergencia_banner.visible is True

    def test_fora_do_modo_gamepad_nao_cobra_mascara(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_flavor_pedido = "xbox"

        host._render_home(_estado(flavor="dualsense", native_mode=True))

        assert host._home_divergencia_banner.visible is False

    def test_offline_nao_afirma_divergencia(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_flavor_pedido = "xbox"
        host._home_divergencia_banner.visible = True

        host._render_home(None)

        assert host._home_divergencia_banner.visible is False


# --------------------------------------------------------------------------
# Defeito 2 — qual ponte está de pé
# --------------------------------------------------------------------------


class TestTextoDaPonte:
    def test_steam_input_suspenso_nao_e_controlar_o_pc(self) -> None:
        """O caso mais enganoso: `mode_of_state` chama isto de desktop.

        Com a exceção ativa o vpad é suspenso e `gamepad_emulation.enabled` cai
        para False — a aba mostrava "Controlar o PC" com o jogo jogando pelo
        espelho da Steam. O dado (`_steam_input_payload`) já era publicado para
        isto e ninguém consumia.
        """
        estado = _estado(
            enabled=False,
            steam_input={"excecao_ativa": True, "vpad_suspenso": True},
        )

        frase = home_actions.texto_da_ponte(estado)

        assert "Steam Input" in frase
        assert "nenhuma" not in frase

    def test_nativo(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(native_mode=True))

        assert "direto (Sony)" in frase

    def test_gamepad_diz_a_mascara_que_o_jogo_ve(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(flavor="xbox"))

        assert "pelo Hefesto" in frase
        assert "Xbox 360" in frase

    def test_desktop_diz_nenhuma_e_aponta_o_botao(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(enabled=False))

        assert "nenhuma" in frase
        assert "Jogar pelo Hefesto" in frase

    def test_offline_nao_sabe(self) -> None:
        frase = home_actions.texto_da_ponte(None)

        assert "não sei" in frase
        assert "desligado" in frase

    def test_todas_as_frases_tem_o_prefixo(self) -> None:
        for estado in (
            None,
            _estado(),
            _estado(enabled=False),
            _estado(native_mode=True),
            _estado(
                enabled=False,
                steam_input={"excecao_ativa": True, "vpad_suspenso": True},
            ),
        ):
            assert home_actions.texto_da_ponte(estado).startswith(
                home_actions.PONTE_PREFIXO
            )


class TestRenderDaPonte:
    def test_a_linha_e_pintada_no_render(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(_estado(flavor="xbox"))

        assert "Xbox 360" in host._home_ponte_label.get_text()

    def test_offline_pinta_o_nao_sei(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(None)

        assert "não sei" in host._home_ponte_label.get_text()
