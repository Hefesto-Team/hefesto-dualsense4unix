"""ATIVAR-NAO-MENTE-01 — o botão "Ativar" parecia falhar, e não refazia nada.

Três defeitos do MESMO clique, medidos em 05/08 no journal do ensaio:

1. **O timeout.** `on_profile_activate` chamava `call_async` sem `timeout_s`, e
   o default da ponte é o de LEITURA: 250 ms. O handler `profile.switch` do
   daemon leva ~1,2 s (activate + save_active_marker + materialize_launch_env).
   Toda ativação caía em `_on_profile_switch_failure` — *"Falha (daemon
   offline?)"* com o perfil JÁ ativo —, o caminho de sucesso nunca rodava, e
   quem usa clicava de novo: cada clique uma ativação real. O applet COSMIC tinha o
   MESMO defeito, com a mesma constante de leitura.

2. **As abas não eram refeitas.** `on_profile_activate` não chamava refresh
   nenhum. As abas só acompanhavam pelo tique de 2 Hz, e esse caminho
   (`_reconciliar_draft_com_perfil_ativo`) DESISTE quando há edição pendente:
   com uma cor mexida e não salva, a ativação explícita não mudava a tela
   nunca. A queixa: o perfil ativado não aplicava na hora as features das
   abas.

3. **O relatório do daemon ia para o lixo.** A resposta do `profile.switch`
   conta a verdade desde a R-03 (`secoes`), e o callback era
   `lambda _result:` — os únicos leitores no repositório eram testes. O toast
   dizia "Perfil ativado" mesmo quando o lock de gesto manual fizera os
   appliers descartarem a seção que quem usa SENTE.

Hermético: stubs de `gi.repository` quando falta PyGObject, dublês com a mesma
API por-ID da aba. Nenhum GTK real, nenhum daemon, nenhuma escrita no
~/.config do usuário.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("ATIVAR-NAO-MENTE-01 (o botão Ativar)")

import sys
import types
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
        except Exception:  # pragma: no cover
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


RESPOSTA_COM_MODO_ADIADO: dict[str, Any] = {
    "active_profile": "pessoal",
    "mode_aplicado": False,
    "motivo": "adiado_lock_manual",
    "secoes": {
        "mouse": "aplicado",
        "suppression": "aplicado",
        "mode": "adiado_lock_manual",
    },
}
RESPOSTA_INTEIRA: dict[str, Any] = {
    "active_profile": "pessoal",
    "mode_aplicado": True,
    "secoes": {"mouse": "aplicado", "mode": "aplicado"},
}
RESPOSTA_SEM_NADA: dict[str, Any] = {
    "active_profile": "pessoal",
    "mode_aplicado": False,
    "secoes": {"mouse": "falhou", "mode": "adiado_lock_manual"},
}


class _Janela(pa.ProfilesActionsMixin):
    """Só o que o clique em "Ativar" consulta — com os métodos REAIS do mixin."""

    def __init__(self, *, pendente: bool = False, editando: str = "pessoal") -> None:
        self._widgets: dict[str, Any] = {"main_window": object()}
        self._pendente = pendente
        self._active_profile_name = editando
        self.toasts: list[str] = []
        self.negritos: list[str | None] = []
        self.sincronizados = 0
        self.recarregou = 0
        self.perguntou: list[tuple[str, str | None]] = []
        self.resposta_descartar = True
        self.selecionado: str | None = "pessoal"

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

    def _tem_edicao_pendente(self) -> bool:
        return self._pendente

    def _bootstrap_draft_async(self) -> None:
        self.recarregou += 1


class TestOTimeoutDaAtivacao:

    def test_a_folga_e_maior_que_a_leitura(self) -> None:
        assert ipc_bridge.PROFILE_SWITCH_TIMEOUT_S > 0.25

    def test_o_helper_sincrono_tambem_usa_a_folga(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`profile_switch` é o que a CLI e o Salvar da aba Perfis leem."""
        vistos: list[Any] = []

        def _falso(method: str, params: Any = None, timeout: Any = None) -> Any:
            vistos.append((method, timeout))
            return {"active_profile": "pessoal"}

        monkeypatch.setattr(ipc_bridge, "_run_call", _falso)

        assert ipc_bridge.profile_switch("pessoal") is True
        assert vistos == [
            ("profile.switch", ipc_bridge.PROFILE_SWITCH_TIMEOUT_S)
        ]


class TestAJanelaLeORelatorio:
    def test_tudo_aplicado_mantem_a_frase_de_sempre(self) -> None:
        assert pa.mensagem_de_ativacao("pessoal", RESPOSTA_INTEIRA) == (
            "Perfil ativado: pessoal"
        )

    def test_daemon_sem_relatorio_nao_levanta_suspeita(self) -> None:
        """Daemon antigo, ou o `True` cru da ponte: sem informação, sem alarme."""
        for resposta in (None, True, {}, {"active_profile": "pessoal"}):
            assert pa.mensagem_de_ativacao("pessoal", resposta) == (
                "Perfil ativado: pessoal"
            )

    def test_secao_adiada_aparece_com_o_nome_que_o_usuario_le(self) -> None:
        """O caso do journal do ensaio: o modo ficou de fora e o toast dizia "ativado"."""
        msg = pa.mensagem_de_ativacao("pessoal", RESPOSTA_COM_MODO_ADIADO)

        assert msg != "Perfil ativado: pessoal", (
            "a resposta dizia que o MODO não entrou e a janela calou"
        )
        assert "modo" in msg
        assert "pessoal" in msg
        assert "mouse" not in msg, "o que ENTROU não é notícia"

    def test_nada_aplicado_diz_o_que_o_rodape_diria(self) -> None:
        msg = pa.mensagem_de_ativacao("pessoal", RESPOSTA_SEM_NADA)
        assert fa._mensagem_de_aplicacao({"applied": []}) in msg

    def test_o_texto_do_que_nao_entrou_e_o_do_rodape(self) -> None:
        """Vocabulário REUSADO, nunca reescrito: dois donos da frase derivam."""
        relato = pa.relato_da_ativacao(RESPOSTA_COM_MODO_ADIADO)
        assert relato is not None
        assert fa._mensagem_de_aplicacao(relato) in pa.mensagem_de_ativacao(
            "pessoal", RESPOSTA_COM_MODO_ADIADO
        )

    def test_o_relato_traduz_secoes_para_applied_e_failed(self) -> None:
        relato = pa.relato_da_ativacao(RESPOSTA_COM_MODO_ADIADO)
        assert relato == {
            "applied": ["mouse", "suppression"],
            "failed": {"modo": "adiado_lock_manual"},
        }

    def test_secao_desconhecida_aparece_com_o_nome_tecnico(self) -> None:
        """Daemon mais novo que a janela: termo estranho > omitir que ficou de"""
        relato = pa.relato_da_ativacao(
            {"secoes": {"telepatia": "falhou"}}
        )
        assert relato == {"applied": [], "failed": {"telepatia": "falhou"}}


