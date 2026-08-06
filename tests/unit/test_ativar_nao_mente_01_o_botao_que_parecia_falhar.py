"""ATIVAR-NAO-MENTE-01 — o botão "Ativar" parecia falhar, e não refazia nada.

Três defeitos do MESMO clique, medidos em 05/08 no journal dela:

1. **O timeout.** `on_profile_activate` chamava `call_async` sem `timeout_s`, e
   o default da ponte é o de LEITURA: 250 ms. O handler `profile.switch` do
   daemon leva ~1,2 s (activate + save_active_marker + materialize_launch_env).
   Toda ativação caía em `_on_profile_switch_failure` — *"Falha (daemon
   offline?)"* com o perfil JÁ ativo —, o caminho de sucesso nunca rodava, e
   ela clicava de novo: cada clique uma ativação real. O applet COSMIC tinha o
   MESMO defeito, com a mesma constante de leitura.

2. **As abas não eram refeitas.** `on_profile_activate` não chamava refresh
   nenhum. As abas só acompanhavam pelo tique de 2 Hz, e esse caminho
   (`_reconciliar_draft_com_perfil_ativo`) DESISTE quando há edição pendente:
   com uma cor mexida e não salva, a ativação explícita dela não mudava a tela
   nunca. Queixa literal: *"o perfil que eu ativei não aplica imediatamente as
   features das abas"*.

3. **O relatório do daemon ia para o lixo.** A resposta do `profile.switch`
   conta a verdade desde a R-03 (`secoes`), e o callback era
   `lambda _result:` — os únicos leitores no repositório eram testes. O toast
   dizia "Perfil ativado" mesmo quando o lock de gesto manual fizera os
   appliers descartarem a seção que ela SENTE.

Hermético: stubs de `gi.repository` quando falta PyGObject, dublês com a mesma
API por-ID da aba. Nenhum GTK real, nenhum daemon, nenhuma escrita no
~/.config dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("ATIVAR-NAO-MENTE-01 (o botão Ativar)")

import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("gi")


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover - ambientes sem GTK
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

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions as fa
from hefesto_dualsense4unix.app.actions import profiles_actions as pa

RAIZ = Path(__file__).resolve().parents[2]
IPC_RS = RAIZ / "packaging" / "cosmic-applet" / "src" / "ipc.rs"

#: O que o daemon respondeu no journal dela quando o lock manual estava armado:
#: o perfil ENTROU, mas a seção que ela sente ficou de fora.
RESPOSTA_COM_MODO_ADIADO: dict[str, Any] = {
    "active_profile": "vitoria",
    "mode_aplicado": False,
    "motivo": "adiado_lock_manual",
    "secoes": {
        "mouse": "aplicado",
        "suppression": "aplicado",
        "mode": "adiado_lock_manual",
    },
}
RESPOSTA_INTEIRA: dict[str, Any] = {
    "active_profile": "vitoria",
    "mode_aplicado": True,
    "secoes": {"mouse": "aplicado", "mode": "aplicado"},
}
RESPOSTA_SEM_NADA: dict[str, Any] = {
    "active_profile": "vitoria",
    "mode_aplicado": False,
    "secoes": {"mouse": "falhou", "mode": "adiado_lock_manual"},
}


class _Janela(pa.ProfilesActionsMixin):
    """Só o que o clique em "Ativar" consulta — com os métodos REAIS do mixin."""

    def __init__(self, *, pendente: bool = False, editando: str = "vitoria") -> None:
        self._widgets: dict[str, Any] = {"main_window": object()}
        self._pendente = pendente
        self._active_profile_name = editando
        self.toasts: list[str] = []
        self.negritos: list[str | None] = []
        self.sincronizados = 0
        self.recarregou = 0
        self.perguntou: list[tuple[str, str | None]] = []
        self.resposta_descartar = True
        self.selecionado: str | None = "vitoria"

    # --- ganchos do mixin ---
    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self.selecionado

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)

    def _mark_active_profile_row(self, active: str | None) -> None:
        self.negritos.append(active)

    def _sync_selection_with_active_profile(self) -> None:
        self.sincronizados += 1

    # --- o que a janela de verdade traz (HefestoApp) ---
    def _tem_edicao_pendente(self) -> bool:
        return self._pendente

    def _bootstrap_draft_async(self) -> None:
        self.recarregou += 1


def _sem_dialogo(janela: _Janela, monkeypatch: pytest.MonkeyPatch) -> None:
    """Intercepta o diálogo de descarte (nenhum GTK sobe no teste)."""
    import hefesto_dualsense4unix.app.gui_dialogs as gd

    monkeypatch.setattr(
        gd,
        "confirm_discard_pending_edits",
        lambda parent, ativado, editando=None: (
            janela.perguntou.append((ativado, editando))
            or janela.resposta_descartar
        ),
        raising=False,
    )


# ---------------------------------------------------------------------------
# 1. O timeout
# ---------------------------------------------------------------------------


class TestOTimeoutDaAtivacao:
    def test_ativar_pede_a_folga_e_nao_o_timeout_de_leitura(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida direta: sem `timeout_s`, a chamada herda os 250 ms.

        250 ms é o timeout de LEITURA da ponte, e o handler do daemon leva
        ~1,2 s medidos — a ativação inteira estourava, e a janela acusava um
        daemon vivo de estar morto.
        """
        chamadas: list[dict[str, Any]] = []
        monkeypatch.setattr(pa, "call_async", lambda **kw: chamadas.append(kw))
        janela = _Janela()

        janela.on_profile_activate(None)

        assert len(chamadas) == 1
        assert chamadas[0]["method"] == "profile.switch"
        folga = chamadas[0]["timeout_s"]
        assert folga >= 1.5, (
            "o handler `profile.switch` leva ~1,2 s: menos que isso volta a "
            "transformar toda ativação em 'Falha (daemon offline?)'"
        )
        assert folga == ipc_bridge.PROFILE_SWITCH_TIMEOUT_S

    def test_a_folga_e_maior_que_a_leitura(self) -> None:
        assert ipc_bridge.PROFILE_SWITCH_TIMEOUT_S > 0.25

    def test_o_helper_sincrono_tambem_usa_a_folga(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`profile_switch` é o que a CLI e o Salvar da aba Perfis leem.

        Com os 250 ms, os três anunciavam falha de uma troca que ACONTECEU.
        """
        vistos: list[Any] = []

        def _falso(method: str, params: Any = None, timeout: Any = None) -> Any:
            vistos.append((method, timeout))
            return {"active_profile": "vitoria"}

        monkeypatch.setattr(ipc_bridge, "_run_call", _falso)

        assert ipc_bridge.profile_switch("vitoria") is True
        assert vistos == [
            ("profile.switch", ipc_bridge.PROFILE_SWITCH_TIMEOUT_S)
        ]


class TestOAppletEspelhaAJanela:
    """Os dois falam com o MESMO daemon — divergir cura um lado só."""

    def test_o_applet_tem_folga_propria_para_trocar_de_perfil(self) -> None:
        fonte = IPC_RS.read_text(encoding="utf-8")
        achado = re.search(
            r"const SWITCH_IPC_TIMEOUT: Duration = Duration::from_secs\((\d+)\)",
            fonte,
        )
        assert achado is not None, (
            "o applet voltou a mandar `profile.switch` no timeout de leitura"
        )
        assert float(achado.group(1)) == ipc_bridge.PROFILE_SWITCH_TIMEOUT_S

    def test_o_switch_do_applet_usa_a_folga(self) -> None:
        """Morde a FIAÇÃO: a constante certa e a chamada errada não curam nada."""
        fonte = IPC_RS.read_text(encoding="utf-8")
        corpo = fonte.split("pub async fn switch_profile", 1)[1].split("\n}\n", 1)[0]
        assert "SWITCH_IPC_TIMEOUT" in corpo

    def test_a_leitura_do_applet_continua_curta(self) -> None:
        """O painel não pode pendurar 3 s num daemon morto — por isso a folga
        é uma constante PRÓPRIA, e não o `IPC_TIMEOUT` esticado."""
        fonte = IPC_RS.read_text(encoding="utf-8")
        achado = re.search(
            r"const IPC_TIMEOUT: Duration = Duration::from_millis\((\d+)\)", fonte
        )
        assert achado is not None
        assert int(achado.group(1)) <= 250


# ---------------------------------------------------------------------------
# 2. As abas passam a ser refeitas na hora
# ---------------------------------------------------------------------------


class TestAtivarRefazAsAbas:
    def test_ativar_recarrega_as_abas_do_perfil_ativado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem edição pendente, a ativação repinta tudo sem perguntar nada."""
        janela = _Janela(pendente=False)
        _sem_dialogo(janela, monkeypatch)

        janela._on_profile_switch_success("vitoria", RESPOSTA_INTEIRA)

        assert janela.recarregou == 1, (
            "as abas seguiram no perfil anterior — a queixa literal dela"
        )
        assert janela.perguntou == [], "sem edição pendente não há o que perguntar"

    def test_com_edicao_pendente_a_decisao_e_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recarregar por baixo de uma edição é perda de trabalho (R-08).

        Ignorar em silêncio é o que o tique de 2 Hz faz — e é o que deixava as
        abas mentindo. Então: pergunta.
        """
        janela = _Janela(pendente=True, editando="Pragmata")
        _sem_dialogo(janela, monkeypatch)
        janela.resposta_descartar = False

        janela._on_profile_switch_success("vitoria", RESPOSTA_INTEIRA)

        assert janela.perguntou == [("vitoria", "Pragmata")]
        assert janela.recarregou == 0, "ela mandou MANTER e o trabalho sumiu"
        assert any("não salvas" in t for t in janela.toasts), (
            "manter as alterações sem dizer nada deixa as abas mentindo calado"
        )

    def test_ela_pode_mandar_descartar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela = _Janela(pendente=True, editando="Pragmata")
        _sem_dialogo(janela, monkeypatch)
        janela.resposta_descartar = True

        janela._on_profile_switch_success("vitoria", RESPOSTA_INTEIRA)

        assert janela.perguntou == [("vitoria", "Pragmata")]
        assert janela.recarregou == 1

    def test_sem_recarregador_ainda_repinta_o_que_esta_em_memoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dublê/mixin sozinho: cai no `_refresh_all_tabs`, nunca em nada."""
        refeitas: list[Any] = []
        monkeypatch.setattr(fa, "_refresh_all_tabs", refeitas.append)
        janela = _Janela(pendente=False)
        monkeypatch.delattr(_Janela, "_bootstrap_draft_async")

        janela._recarregar_as_abas_do_perfil_ativo()

        assert refeitas == [janela]

    def test_o_dialogo_novo_nasce_com_o_tema_do_app(self) -> None:
        """GUI-05/P5: diálogo sem a classe abre CLARO no COSMIC (XWayland)."""
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_discard_pending_edits)
        assert "_apply_app_theme(" in src

    def test_o_default_do_dialogo_e_manter_o_que_ela_nao_salvou(self) -> None:
        """Um Enter distraído não pode custar edição não salva."""
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_discard_pending_edits)
        assert "set_default_response(Gtk.ResponseType.CANCEL)" in src

    def test_o_negrito_e_a_selecao_continuam_acontecendo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura nova não pode custar o comportamento que já existia."""
        janela = _Janela(pendente=False)
        _sem_dialogo(janela, monkeypatch)

        janela._on_profile_switch_success("vitoria", RESPOSTA_INTEIRA)

        assert janela.negritos == ["vitoria"]
        assert janela.sincronizados == 1


# ---------------------------------------------------------------------------
# 3. A janela LÊ o relatório do daemon
# ---------------------------------------------------------------------------


class TestAJanelaLeORelatorio:
    def test_tudo_aplicado_mantem_a_frase_de_sempre(self) -> None:
        assert pa.mensagem_de_ativacao("vitoria", RESPOSTA_INTEIRA) == (
            "Perfil ativado: vitoria"
        )

    def test_daemon_sem_relatorio_nao_levanta_suspeita(self) -> None:
        """Daemon antigo, ou o `True` cru da ponte: sem informação, sem alarme."""
        for resposta in (None, True, {}, {"active_profile": "vitoria"}):
            assert pa.mensagem_de_ativacao("vitoria", resposta) == (
                "Perfil ativado: vitoria"
            )

    def test_secao_adiada_aparece_com_o_nome_que_ela_le(self) -> None:
        """O caso do journal dela: o modo ficou de fora e o toast dizia "ativado"."""
        msg = pa.mensagem_de_ativacao("vitoria", RESPOSTA_COM_MODO_ADIADO)

        assert msg != "Perfil ativado: vitoria", (
            "a resposta dizia que o MODO não entrou e a janela calou"
        )
        assert "modo" in msg
        assert "vitoria" in msg
        assert "mouse" not in msg, "o que ENTROU não é notícia"

    def test_nada_aplicado_diz_o_que_o_rodape_diria(self) -> None:
        msg = pa.mensagem_de_ativacao("vitoria", RESPOSTA_SEM_NADA)
        assert fa._mensagem_de_aplicacao({"applied": []}) in msg

    def test_o_texto_do_que_nao_entrou_e_o_do_rodape(self) -> None:
        """Vocabulário REUSADO, nunca reescrito: dois donos da frase derivam.

        Se alguém escrever aqui uma segunda frase para a mesma ideia, este
        teste reprova — que é exatamente o ponto.
        """
        relato = pa.relato_da_ativacao(RESPOSTA_COM_MODO_ADIADO)
        assert relato is not None
        assert fa._mensagem_de_aplicacao(relato) in pa.mensagem_de_ativacao(
            "vitoria", RESPOSTA_COM_MODO_ADIADO
        )

    def test_o_relato_traduz_secoes_para_applied_e_failed(self) -> None:
        relato = pa.relato_da_ativacao(RESPOSTA_COM_MODO_ADIADO)
        assert relato == {
            "applied": ["mouse", "suppression"],
            "failed": {"modo": "adiado_lock_manual"},
        }

    def test_secao_desconhecida_aparece_com_o_nome_tecnico(self) -> None:
        """Daemon mais novo que a janela: termo estranho > omitir que ficou de
        fora (a mesma regra do `_lista_de_secoes` do rodapé)."""
        relato = pa.relato_da_ativacao(
            {"secoes": {"telepatia": "falhou"}}
        )
        assert relato == {"applied": [], "failed": {"telepatia": "falhou"}}

    def test_o_toast_da_ativacao_carrega_o_relatorio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho público: é o `_result` que era jogado fora."""
        janela = _Janela(pendente=False)
        _sem_dialogo(janela, monkeypatch)

        janela._on_profile_switch_success("vitoria", RESPOSTA_COM_MODO_ADIADO)

        assert any("modo" in t for t in janela.toasts)

    def test_o_callback_do_ativar_repassa_a_resposta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fiação: `lambda _result:` descartava o relatório antes de chegar aqui."""
        capturado: list[Any] = []
        monkeypatch.setattr(pa, "call_async", lambda **kw: capturado.append(kw))
        janela = _Janela(pendente=False)
        _sem_dialogo(janela, monkeypatch)

        janela.on_profile_activate(None)
        capturado[0]["on_success"](RESPOSTA_COM_MODO_ADIADO)

        assert any("modo" in t for t in janela.toasts)
