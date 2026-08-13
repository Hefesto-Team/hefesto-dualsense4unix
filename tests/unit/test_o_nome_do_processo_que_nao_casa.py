"""PROCESSO-CEGO-01 — o campo `process_name` que a tela mandava preencher e o
ambiente dela não tem como casar.

O DEFEITO, medido
-----------------
`process_name` é matcher de primeira classe no esquema de perfil, e a página
`docs/usage/jogos-e-mascaras.md` MANDAVA preenchê-lo. Só que em Wayland puro os
dois backends de janela devolvem ``exe_basename=""`` por construção —
`window_backends/wayland_portal.py` e `window_backends/wlr_toplevel.py` montam o
`WindowInfo` com a string vazia LITERAL, e o portal faz isso mesmo tendo o `pid`
na mão.

E `MatchCriteria.matches` é um **E** entre os campos preenchidos. Então o campo
não falha sozinho: ele derruba o perfil INTEIRO, inclusive a `window_class` que
casaria. Foi a causa medida (sprint PERFIL-MUDO-01, 10/08/2026, 30 dias de
journal da máquina dela) de cinco perfis de gênero — ``FPS``, ``Ação``,
``Aventura``, ``Corrida``, ``Esportes`` — nunca ativarem, **nenhuma vez**.

O QUE ESTA LEVA **NÃO** FAZ
---------------------------
Não mexe nos perfis dela e não sugere apagar campo nenhum: *"a vontade da GUI
prevalece"*, e quem escreveu o critério foi ela. O que faltava não era decisão,
era informação — e agora ela chega ANTES, na tela em que o campo é digitado (a
aba "No jogo" já contava DEPOIS, com o jogo aberto sem o perfil).

O QUE CADA TESTE MORDE
----------------------
Cada teste abaixo foi verificado ARRANCANDO a cura correspondente e vendo
reprovar. Os pontos de arranque estão nomeados nas docstrings, um por teste.

Os quatro primeiros são o cinto contra DERIVA: eles não acreditam na tabela
`BACKENDS_QUE_VEEM_O_PROCESSO`, eles a conferem contra o que cada backend
DEVOLVE. Se algum dia o portal passar a resolver `/proc/<pid>/exe`, a tabela
fica errada e o teste reprova antes de a tela mentir.
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("aviso do nome do processo no editor de perfis")


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")
    for nome in (
        "Builder", "Window", "Button", "CheckButton", "ComboBoxText", "Switch",
        "TreeView", "TreeViewColumn", "CellRendererText", "ListStore",
        "TreeSelection", "TreePath", "Box", "Label", "Frame", "Entry",
        "RadioButton", "Scale", "Stack", "MessageDialog", "MessageType",
        "ButtonsType", "ResponseType",
    ):
        setattr(gtk_mod, nome, object)
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    gobject_mod.TYPE_STRING = "str"  # type: ignore[attr-defined]
    gobject_mod.TYPE_INT = "int"  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.integrations.window_backends import (
    wayland_portal,
    wlr_toplevel,
    xlib,
)
from hefesto_dualsense4unix.integrations.window_detect import (
    BACKENDS_CEGOS_AO_PROCESSO,
    BACKENDS_QUE_VEEM_O_PROCESSO,
    backend_ve_nome_do_processo,
)
from hefesto_dualsense4unix.profiles.schema import MatchCriteria


# ---------------------------------------------------------------------------
# 1. A tabela conferida contra os backends de verdade
# ---------------------------------------------------------------------------


class TestATabelaBateComOsBackends:
    """A tabela não é crença: é conferida contra o que cada arquivo devolve."""

    def test_o_portal_devolve_exe_vazio_mesmo_tendo_o_pid(self) -> None:
        """O portal RECEBE o pid e ainda assim não resolve o executável.

        Este é o detalhe que faz o defeito parecer impossível de longe — "mas o
        Wayland manda o pid!". Manda; ninguém lê `/proc/<pid>/exe` ali.

        Morde em `BACKENDS_CEGOS_AO_PROCESSO`. Arranque: mover ``"portal"``
        para `BACKENDS_QUE_VEEM_O_PROCESSO` e o `assert` do predicado reprova.
        """
        info = wayland_portal._parse_portal_result(
            {"app-id": "steam_app_3357650", "title": "PRAGMATA", "pid": os.getpid()}
        )
        assert info is not None
        assert info.pid == os.getpid()
        assert info.exe_basename == ""
        assert info.as_dict()["exe_basename"] == ""
        nome = wayland_portal.WaylandPortalBackend.backend_name
        assert backend_ve_nome_do_processo(nome) is False

    def test_o_wlrctl_devolve_exe_vazio(self, monkeypatch: Any) -> None:
        """Mesmo com o `wlrctl` respondendo um toplevel inteiro, o campo é vazio.

        Morde em `BACKENDS_CEGOS_AO_PROCESSO`. Arranque: mover ``"wlrctl"``
        para `BACKENDS_QUE_VEEM_O_PROCESSO`.
        """

        class _Resposta:
            returncode = 0
            stdout = '[{"app_id": "steam_app_3357650", "title": "PRAGMATA"}]'
            stderr = ""

        monkeypatch.setattr(wlr_toplevel.shutil, "which", lambda _b: "/usr/bin/wlrctl")
        monkeypatch.setattr(
            wlr_toplevel.subprocess, "run", lambda *_a, **_kw: _Resposta()
        )
        info = wlr_toplevel.WlrctlBackend().get_active_window_info()
        assert info is not None
        assert info.wm_class == "steam_app_3357650"
        assert info.exe_basename == ""
        nome = wlr_toplevel.WlrctlBackend.backend_name
        assert backend_ve_nome_do_processo(nome) is False

    def test_o_xlib_resolve_o_executavel_de_verdade(self) -> None:
        """O X11 é o único que lê `/proc/<pid>/exe` — provado com o pid deste teste.

        Sem esta metade o aviso não valeria nada: um predicado que responde
        "cego" para TUDO também passaria nos dois testes acima, e a tela
        acusaria o ambiente em que o campo funciona.

        Morde em `BACKENDS_QUE_VEEM_O_PROCESSO`. Arranque: tirar ``"xlib"`` da
        tabela e o `assert` do predicado reprova.
        """
        assert xlib._exe_basename_from_pid(os.getpid()) != ""
        assert backend_ve_nome_do_processo(xlib.XlibBackend.backend_name) is True

    def test_as_duas_tabelas_nao_se_cruzam(self) -> None:
        """Um backend não pode estar nas duas listas — o predicado responderia pela ordem."""
        assert not (BACKENDS_QUE_VEEM_O_PROCESSO & BACKENDS_CEGOS_AO_PROCESSO)

    def test_backend_desconhecido_ou_ausente_nao_afirma_nada(self) -> None:
        """"Não sei" e "não casa" mandam caçar em lugares opostos.

        Daemon mais velho que o código é rotina nesta casa (install editable), e
        um `False` inventado a partir do silêncio faria a tela acusar um defeito
        que ninguém mediu.

        Morde no ramo ``return None`` de `backend_ve_nome_do_processo`.
        Arranque: trocar o `return None` final por `return False`.
        """
        assert backend_ve_nome_do_processo(None) is None
        assert backend_ve_nome_do_processo("") is None
        assert backend_ve_nome_do_processo("backend_de_terceiro") is None


# ---------------------------------------------------------------------------
# 2. O dano que o aviso descreve — o E que derruba o perfil inteiro
# ---------------------------------------------------------------------------


class TestOCampoDerrubaOPerfilInteiro:
    def test_com_a_window_class_certa_o_perfil_ainda_nao_entra(self) -> None:
        """A afirmação forte do aviso, medida: *"nem com o window_class certo"*.

        É o caso literal dos cinco perfis de gênero dela. Sem este teste o aviso
        estaria prometendo um mecanismo que ninguém conferiu.
        """
        janela_wayland = {
            "wm_class": "steam_app_3357650",
            "wm_name": "PRAGMATA",
            "exe_basename": "",  # o que portal e wlrctl SEMPRE devolvem
        }
        so_a_classe = MatchCriteria(window_class=["steam_app_3357650"])
        com_o_processo = MatchCriteria(
            window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]
        )

        assert so_a_classe.matches(janela_wayland) is True
        assert com_o_processo.matches(janela_wayland) is False


# ---------------------------------------------------------------------------
# 3. A frase da tela
# ---------------------------------------------------------------------------


class TestAFraseDoAviso:
    def test_no_wayland_diz_o_campo_o_efeito_e_a_saida(self) -> None:
        """Três coisas ou nada: qual campo, que o perfil não entra, e o que usar.

        Morde em `texto_do_processo_que_nao_casa`. Arranque: devolver `None` no
        ramo do Wayland — os quatro `assert` reprovam de uma vez.
        """
        for backend in ("portal", "wlrctl"):
            texto = pa.texto_do_processo_que_nao_casa(
                {"window_detect_backend": backend}
            )
            assert texto is not None
            assert "process_name" in texto
            assert "não entrar nunca" in texto
            assert "window_class" in texto and "title_regex" in texto

    def test_o_null_nao_acusa_so_o_process_name(self) -> None:
        """Sem leitura de janela nenhuma, trocar de campo cai no mesmo silêncio.

        Dizer só do `process_name` aqui mandaria ela reescrever o critério para
        continuar sem perfil — o aviso teria custado trabalho e não teria
        entregado nada.

        Morde no ramo ``if backend == "null"``. Arranque: apagar o ramo e a
        frase do Wayland assume, dizendo que os outros dois campos casam.
        """
        texto = pa.texto_do_processo_que_nao_casa({"window_detect_backend": "null"})
        assert texto is not None
        assert "nenhum dos três campos casa" in texto

    def test_cala_no_x11(self) -> None:
        """Onde o campo casa, a tela não tem nada a dizer sobre ele."""
        assert (
            pa.texto_do_processo_que_nao_casa({"window_detect_backend": "xlib"}) is None
        )

    def test_cala_com_daemon_velho_ou_desligado(self) -> None:
        """Campo ausente é "não sei", e "não sei" não vira alerta na tela.

        Morde na guarda de entrada. Arranque: tratar `backend` ausente como
        cego, e a aba passa a acusar Wayland num daemon que nunca respondeu.
        """
        assert pa.texto_do_processo_que_nao_casa(None) is None
        assert pa.texto_do_processo_que_nao_casa({}) is None
        assert pa.texto_do_processo_que_nao_casa("nada") is None  # type: ignore[arg-type]
        assert (
            pa.texto_do_processo_que_nao_casa({"window_detect_backend": None}) is None
        )

    def test_a_frase_nao_manda_apagar_nada(self) -> None:
        """*"A vontade da GUI prevalece"* — o aviso informa, não corrige.

        O critério é dela; o produto diz o que o campo faz aqui e para de falar.
        """
        texto = pa.texto_do_processo_que_nao_casa({"window_detect_backend": "wlrctl"})
        assert texto is not None
        minusculo = texto.lower()
        for proibida in ("apague", "remova", "errado", "corrija"):
            assert proibida not in minusculo

    def test_a_frase_atravessa_o_markup_do_pango_inteira(self) -> None:
        """A costura da tela usa `set_markup` sem escapar — as frases não podem
        levar `<`, `&` nem aspas retas (as aspas são as tipográficas “ ”)."""
        for backend in ("portal", "wlrctl", "null"):
            texto = pa.texto_do_processo_que_nao_casa(
                {"window_detect_backend": backend}
            )
            assert texto is not None
            assert "<" not in texto and "&" not in texto and '"' not in texto


# ---------------------------------------------------------------------------
# 4. A frase chega à TELA — sem isso a cura fica escrita e nunca ligada
# ---------------------------------------------------------------------------


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.visivel = False

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_visible(self, visivel: bool) -> None:
        self.visivel = bool(visivel)


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _Editor(pa.ProfilesActionsMixin):
    """Editor fake: métodos REAIS do mixin sobre widgets fake."""

    def __init__(self) -> None:
        self.aviso = _FakeLabel()
        self._widgets: dict[str, Any] = {
            "profile_process_name_aviso": self.aviso,
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "profile_name_entry": _FakeEntry(""),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
        }
        self._mode_advanced = False
        self._suppress_advanced_toggle = False
        self._profiles_cache: list[Any] = []

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    # o handler do switch chama estes dois; aqui eles não são o assunto
    def _mostrar_a_regra_nos_campos_crus(self) -> None:
        return None


def _responder_state(monkeypatch: Any, state: dict[str, Any]) -> None:
    """Faz o `call_async` responder NA HORA, com o estado dado."""

    def _falso_call_async(**kwargs: Any) -> None:
        kwargs["on_success"](state)

    monkeypatch.setattr(pa, "call_async", _falso_call_async)
    monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)


class TestOAvisoChegaNaTela:
    def test_ligar_o_avancado_acende_o_aviso(self, monkeypatch: Any) -> None:
        """A página avançada é a ÚNICA porta para o campo — é ao abri-la que a
        pergunta tem de ser feita.

        Morde na chamada de `_atualizar_aviso_do_processo` dentro de
        `on_profile_advanced_toggle`. Arranque: apagar a linha e o label fica
        invisível com o Wayland respondendo.
        """
        _responder_state(monkeypatch, {"window_detect_backend": "wlrctl"})
        ed = _Editor()

        ed.on_profile_advanced_toggle(ed._get("profile_advanced_switch"), True)

        assert ed.aviso.visivel is True
        assert ed.aviso.markup is not None
        assert "process_name" in ed.aviso.markup
        # o token de ALERTA da casa, o mesmo do `rumble_policy_aviso`
        assert "#ffb86c" in ed.aviso.markup

    def test_no_x11_o_aviso_fica_escondido(self, monkeypatch: Any) -> None:
        """Um alerta permanente que não vale para o ambiente é ruído."""
        _responder_state(monkeypatch, {"window_detect_backend": "xlib"})
        ed = _Editor()

        ed.on_profile_advanced_toggle(ed._get("profile_advanced_switch"), True)

        assert ed.aviso.visivel is False
        assert ed.aviso.markup is None

    def test_com_daemon_desligado_o_aviso_nao_aparece(self, monkeypatch: Any) -> None:
        """`call_async` que falha (daemon fora) é silêncio, não alarme.

        Morde no `on_failure` que devolve False sem tocar no label. Arranque:
        acender o aviso na falha e este teste reprova.
        """

        def _falso_call_async(**kwargs: Any) -> None:
            kwargs["on_failure"](RuntimeError("daemon fora"))

        monkeypatch.setattr(pa, "call_async", _falso_call_async)
        monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)
        ed = _Editor()

        ed.on_profile_advanced_toggle(ed._get("profile_advanced_switch"), True)

        assert ed.aviso.visivel is False
        assert ed.aviso.markup is None

    def test_resposta_que_nao_e_dicionario_nao_derruba_a_aba(
        self, monkeypatch: Any
    ) -> None:
        """Daemon que responde qualquer coisa não pode quebrar a aba Perfis."""
        _responder_state(monkeypatch, None)  # type: ignore[arg-type]
        ed = _Editor()

        ed.on_profile_advanced_toggle(ed._get("profile_advanced_switch"), True)

        assert ed.aviso.visivel is False

    def test_desligar_o_avancado_nao_pergunta_nada(self, monkeypatch: Any) -> None:
        """Sem o campo na tela não há o que avisar — e nem IPC a gastar."""
        perguntas: list[str] = []

        def _falso_call_async(**kwargs: Any) -> None:
            perguntas.append(str(kwargs.get("method")))

        monkeypatch.setattr(pa, "call_async", _falso_call_async)
        monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)
        ed = _Editor()

        ed.on_profile_advanced_toggle(ed._get("profile_advanced_switch"), False)

        assert perguntas == []


class TestOWlrctlNaoPrecisaDeCompositorNoTeste:
    """Cinto do próprio instrumento: o dublê do `wlrctl` não pode virar produto.

    "O instrumento mente mais que o produto" — se o `subprocess.run` não
    estivesse dublado, o teste do wlrctl passaria por AUSÊNCIA do binário
    (backend indisponível devolve `None`) e não por medição.
    """

    def test_sem_o_binario_o_backend_nem_tenta(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(wlr_toplevel.shutil, "which", lambda _b: None)

        def _explode(*_a: Any, **_kw: Any) -> Any:  # pragma: no cover
            raise AssertionError("não deveria chamar o wlrctl sem o binário")

        monkeypatch.setattr(wlr_toplevel.subprocess, "run", _explode)
        assert wlr_toplevel.WlrctlBackend().get_active_window_info() is None
