"""UX-05 (auditoria 24/07) — o cadeado tinha EFEITO visível e CAUSA invisível.

`autoswitch_locked` só existia na GUI como o marcador de um checkbox
(`_render_home`, `set_active`). Na máquina dela a flag estava ligada desde
24/07 20:42 e o que ela via era outra coisa: "o modo jogo não ativa", "os
perfis não mudam". Ninguém relê uma caixinha de 16 px depois de marcá-la.

A frase é gerada por uma função PURA (mesmo desenho de `vpad_degradation_text`
e `wrapper_banner_text`) e diz as DUAS metades da política LOCK-CEDE-01 —
o que congelou e o que continua entrando —, porque as duas surpreendem quem só
vê o efeito.

TESTE-HONESTO-01/E3 (13/08/2026): a fiação era medida por quatro asserts de
substring sobre o TEXTO-FONTE do método. Nenhum deles proibia bug nenhum —
eles proibiam RENOMEAR. Quem trocasse o nome da função pura, ou da variável
local `lock_hint`, via quatro testes vermelhos sem ter mudado comportamento
algum. Agora a aba é MONTADA e RENDERIZADA de verdade contra um GTK de mentira
(`_WidgetFalso`, que obedece à regra do `show_all` do GTK3) e a fiação é
observada: a função pura foi chamada com o estado, e o que ela devolveu chegou
ao rótulo. O nome dela não aparece em nenhuma string.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import (
    HomeActionsMixin,
    autoswitch_lock_text,
)


class TestDecisaoPura:
    def test_destravado_nao_diz_nada(self) -> None:
        assert autoswitch_lock_text({"autoswitch_locked": False}) == ""

    def test_campo_ausente_nao_diz_nada(self) -> None:
        assert autoswitch_lock_text({"connected": True}) == ""

    def test_offline_nao_diz_nada(self) -> None:
        # Offline não é "destravado", é "não sei" — e a aba apaga a frase.
        assert autoswitch_lock_text(None) == ""

    def test_travado_explica_a_causa(self) -> None:
        texto = autoswitch_lock_text({"autoswitch_locked": True})
        assert "não troca sozinho" in texto

    def test_travado_nomeia_o_perfil_que_ficou(self) -> None:
        """'o perfil não troca sozinho' sem dizer QUAL perfil é meia
        informação — é o perfil que ela precisa reconhecer na aba Perfis."""
        texto = autoswitch_lock_text(
            {"autoswitch_locked": True, "active_profile": "vitoria"}
        )
        assert "vitoria" in texto

    def test_travado_sem_perfil_ativo_nao_inventa_nome(self) -> None:
        texto = autoswitch_lock_text(
            {"autoswitch_locked": True, "active_profile": None}
        )
        assert "não troca sozinho" in texto
        assert "None" not in texto

    def test_diz_que_o_jogo_com_perfil_proprio_ainda_entra(self) -> None:
        """LOCK-CEDE-01: sem esta metade, "o modo jogo ligou sozinho mesmo com
        o cadeado" volta a ser um mistério sem causa visível."""
        texto = autoswitch_lock_text({"autoswitch_locked": True})
        assert "perfil próprio" in texto

    def test_payload_torto_nao_vira_frase(self) -> None:
        for torto in (0, "", [], {}):
            assert autoswitch_lock_text({"autoswitch_locked": torto}) == ""


# ---------------------------------------------------------------------------
# O GTK de mentira que MONTA a aba — e a única regra dele que importa aqui
# ---------------------------------------------------------------------------


class _EstiloFalso:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, nome: str) -> None:
        if nome not in self.classes:
            self.classes.append(nome)

    def remove_class(self, nome: str) -> None:
        if nome in self.classes:
            self.classes.remove(nome)


class _WidgetFalso:
    """Widget de mentira que obedece à REGRA do ``gtk_widget_show_all``.

    A regra é uma só, e é a que a aba depende: ``show_all()`` num widget com
    ``no-show-all`` ligado **não faz nada** — nem nele, nem nos filhos dele
    (`gtk_widget_show_all`: ``if (gtk_widget_get_no_show_all (widget)) return;``).
    Sem ela, o `show_all()` do fim do `install_home_tab` acenderia o rótulo do
    cadeado, e a aba nasceria com uma linha de texto vazia ocupando espaço.

    Nasce INVISÍVEL, como todo widget GTK antes do primeiro ``show``.
    """

    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_WidgetFalso] = []
        self.style = _EstiloFalso()
        self.visible = False
        self.no_show_all = False
        self.sensitive = True
        self.active = False
        self.active_id: str | None = None
        self.tooltip: str | None = None
        self.handlers: list[tuple[str, Any]] = []
        self.items: list[tuple[str, str]] = []

    # --- leitura ---------------------------------------------------------
    def get_style_context(self) -> _EstiloFalso:
        return self.style

    def get_text(self) -> str:
        return str(self.label or "")

    def get_label(self) -> str:
        return str(self.label or "")

    def get_children(self) -> list[_WidgetFalso]:
        return list(self.children)

    def get_active_id(self) -> str | None:
        return self.active_id

    # --- escrita ---------------------------------------------------------
    def set_text(self, texto: str) -> None:
        self.label = texto

    def set_label(self, texto: str) -> None:
        self.label = texto

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_visible(self, valor: bool) -> None:
        self.visible = valor

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = valor

    def set_sensitive(self, valor: bool) -> None:
        self.sensitive = valor

    def set_active(self, valor: bool) -> None:
        self.active = valor

    def set_active_id(self, valor: str) -> None:
        self.active_id = valor

    def set_items(self, itens: list[tuple[str, str]]) -> None:
        self.items = list(itens)

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def __getattr__(self, nome: str) -> Any:
        """Qualquer OUTRO ajuste de layout é no-op — e isso é deliberado.

        `set_xalign`, `set_line_wrap`, `set_max_width_chars`, `set_margin_*`:
        nenhum deles muda o que esta medida observa (texto e visibilidade), e
        um dublê que quebrasse a cada propriedade nova que a aba ganhasse
        seria a mesma fragilidade que esta entrega veio tirar. O que ele MEDE
        está declarado explicitamente acima; leitura (`get_*`) continua
        levantando `AttributeError`, porque ali um silêncio viraria medida
        falsa.
        """
        if nome.startswith(("set_", "add_", "queue_", "override_")):
            return lambda *_args, **_kwargs: None
        raise AttributeError(nome)

    # --- árvore ----------------------------------------------------------
    def pack_start(self, filho: _WidgetFalso, *_args: object) -> None:
        self.children.append(filho)

    def add(self, filho: _WidgetFalso) -> None:
        self.children.append(filho)

    def remove(self, filho: _WidgetFalso) -> None:
        self.children.remove(filho)

    def reorder_child(self, _filho: _WidgetFalso, _pos: int) -> None:
        pass

    def connect(self, sinal: str, callback: Any) -> None:
        self.handlers.append((sinal, callback))

    def show_all(self) -> None:
        if self.no_show_all:
            return
        self.visible = True
        for filho in self.children:
            filho.show_all()


class _JanelaFalsa(HomeActionsMixin):
    """A janela real, com os handlers reais — só o toolkit é de mentira.

    Herda o mixin inteiro (e não copia método por método) por dois motivos: os
    `connect` do build precisam dos handlers de verdade existindo, e um dublê
    parcial esconderia exatamente o defeito que estes testes procuram — uma
    chamada que sumiu do `install_home_tab`/`_render_home`.
    """

    def __init__(self) -> None:
        self.tab_home_box = _WidgetFalso()
        self.timeouts: list[tuple[int, Any]] = []

    def _get(self, widget_id: str) -> Any:
        # Só a caixa da aba vem do Glade neste dublê; os widgets opcionais
        # (co-op) são ausência LEGÍTIMA — o `install_home_tab` a tolera de
        # propósito, e é essa tolerância que o dublê exercita.
        return self.tab_home_box if widget_id == "tab_home_box" else None


@pytest.fixture()
def gtk_de_mentira(monkeypatch: pytest.MonkeyPatch) -> None:
    """Planta `gi.repository` e o seletor segmentado, os dois de mentira.

    O seletor entra na lista porque a régua tem de declarar contra o que mede:
    `segmented_selector` decide na IMPORTAÇÃO se é a subclasse de `Gtk.Box` ou
    o stub puro, e o teste não pode depender de haver PyGObject real no
    processo — nem instanciar um `Gtk.Box` de verdade sem display.
    """
    repo = types.ModuleType("gi.repository")
    repo.Gtk = types.SimpleNamespace(  # type: ignore[attr-defined]
        Label=_WidgetFalso,
        Box=_WidgetFalso,
        Frame=_WidgetFalso,
        Button=_WidgetFalso,
        CheckButton=_WidgetFalso,
        Orientation=types.SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    repo.GLib = types.SimpleNamespace(  # type: ignore[attr-defined]
        timeout_add=lambda ms, cb: 0,
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)

    seletor = types.ModuleType(
        "hefesto_dualsense4unix.app.widgets.segmented_selector"
    )
    seletor.SegmentedSelector = _WidgetFalso  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "hefesto_dualsense4unix.app.widgets.segmented_selector",
        seletor,
    )


@pytest.fixture()
def aba(gtk_de_mentira: None) -> _JanelaFalsa:
    """A aba Início MONTADA — o mesmo `install_home_tab` que a janela roda."""
    janela = _JanelaFalsa()
    janela.install_home_tab()
    return janela


class TestFiacaoNaAbaInicio:
    def test_render_home_consome_a_funcao_pura(
        self, aba: _JanelaFalsa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O rótulo diz o que a FUNÇÃO PURA decidiu, não o que a aba inventou.

        O dublê entra pelo `__name__` da própria função — de propósito. Congelar
        o nome numa string é o que fazia este teste reprovar um `rename` que não
        muda comportamento nenhum (TESTE-HONESTO-01/E3).
        """
        estado = {"autoswitch_locked": True, "active_profile": "vitoria"}
        espiao = MagicMock(return_value="FRASE-DO-CADEADO")
        monkeypatch.setattr(home_actions, autoswitch_lock_text.__name__, espiao)

        aba._render_home(estado)

        assert estado in [chamada.args[0] for chamada in espiao.call_args_list]
        assert aba._home_autoswitch_lock_hint.get_text() == "FRASE-DO-CADEADO"
        assert aba._home_autoswitch_lock_hint.visible is True

    def test_destravado_apaga_a_frase(self, aba: _JanelaFalsa) -> None:
        """Sem cadeado não há causa a explicar — e sobra de texto é mentira."""
        aba._render_home({"autoswitch_locked": True, "active_profile": "v"})
        assert aba._home_autoswitch_lock_hint.visible is True

        aba._render_home({"autoswitch_locked": False})

        assert aba._home_autoswitch_lock_hint.get_text() == ""
        assert aba._home_autoswitch_lock_hint.visible is False

    def test_offline_apaga_a_frase(self, aba: _JanelaFalsa) -> None:
        """Estado morto nunca deixa uma afirmação viva na tela."""
        aba._render_home({"autoswitch_locked": True, "active_profile": "v"})
        assert aba._home_autoswitch_lock_hint.visible is True

        aba._render_home(None)

        assert aba._home_autoswitch_lock_hint.get_text() == ""
        assert aba._home_autoswitch_lock_hint.visible is False

    def test_o_cadeado_reflete_o_estado_do_daemon(self, aba: _JanelaFalsa) -> None:
        """O marcador continua sendo o EFEITO — a frase é a causa ao lado dele."""
        aba._render_home({"autoswitch_locked": True})
        assert aba._home_autoswitch_lock.active is True

        aba._render_home({"autoswitch_locked": False})
        assert aba._home_autoswitch_lock.active is False

    def test_o_rotulo_nasce_invisivel_e_o_show_all_do_build_nao_o_acende(
        self, aba: _JanelaFalsa
    ) -> None:
        """Mesmo desenho dos banners de vpad/wrapper.

        O `install_home_tab` termina com `box.show_all()`. Sem o `no-show-all`
        no rótulo, esse `show_all` acende uma linha VAZIA no meio do frame — e
        desfaz, no ato do build, o que o `_render_home` mandaria depois.
        """
        rotulo = aba._home_autoswitch_lock_hint

        assert rotulo.visible is False
        assert rotulo.get_text() == ""


class TestEstadoDoDaemonCarregaOCampo:
    """A frase depende do campo chegar nos DOIS payloads que a GUI lê.

    Medido no payload de verdade (`daemon.status` e `daemon.state_full` de um
    daemon montado com controle falso), e não no texto do handler: o que
    interessa é o que sai na resposta, por qualquer caminho que ela seja
    montada. O fecho é a própria função pura consumindo o payload — se o campo
    sumir de um dos dois, a aba fica muda e o teste diz qual dos dois.
    """

    def _handlers(self) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon
        from hefesto_dualsense4unix.testing import FakeController

        daemon = Daemon(controller=FakeController(transport="usb"))

        class _Handlers(IpcHandlersMixin):
            def __init__(self, alvo: Any) -> None:
                self.daemon = alvo
                self.store = alvo.store
                self.controller = alvo.controller

        return daemon, _Handlers(daemon)

    @pytest.mark.asyncio
    async def test_status_e_state_full_expoem_autoswitch_locked(self) -> None:
        daemon, handlers = self._handlers()
        daemon.store.set_autoswitch_locked(True)
        daemon.store.set_active_profile("vitoria")

        for nome in ("_handle_daemon_status", "_handle_daemon_state_full"):
            payload = await getattr(handlers, nome)({})
            assert "autoswitch_locked" in payload, f"{nome} não expõe o cadeado"
            assert "active_profile" in payload, f"{nome} não expõe o perfil ativo"
            assert payload["autoswitch_locked"] is True, nome
            assert payload["active_profile"] == "vitoria", nome
            # E o fecho: com esse payload, a aba TEM frase para mostrar.
            assert "vitoria" in autoswitch_lock_text(payload), nome

    @pytest.mark.asyncio
    async def test_destravado_chega_como_false_nos_dois(self) -> None:
        daemon, handlers = self._handlers()
        daemon.store.set_autoswitch_locked(False)

        for nome in ("_handle_daemon_status", "_handle_daemon_state_full"):
            payload = await getattr(handlers, nome)({})
            assert "autoswitch_locked" in payload, f"{nome} não expõe o cadeado"
            assert payload["autoswitch_locked"] is False, nome
            assert autoswitch_lock_text(payload) == "", nome
