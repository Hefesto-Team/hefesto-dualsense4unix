"""P3 + P3b — o Salvar segurava a janela, e comemorava o que não aconteceu.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/2 e §2.2/3 (24/08/2026). Dois defeitos na
mesma linha de código, e o botão VIZINHO já tinha os dois curados:

**A thread.** `on_profile_save` chamava `profile_switch()` — síncrono — na
thread do GTK. O handler `profile.switch` levou **~1,2 s MEDIDOS no journal
dela**, número escrito no comentário de `on_profile_activate`, e foi por ele
que o **Ativar** virou `call_async` na ATIVAR-NAO-MENTE-01. O Salvar ficou.

**A promessa.** `profile_switch()` devolve um booleano cujo significado a
própria docstring declara: *"o daemon não confirmou"*. Nunca *"as seções
entraram"*. O Salvar lia o `True` como a segunda coisa e escrevia **"Perfil
salvo e reaplicado no controle"**. Com o jogo aberto, o gate R-04 recusa
seções: o daemon responde, o booleano é `True`, nada chega ao controle, e a
janela comemora. Cem linhas acima, no mesmo arquivo, o Ativar já sabia dizer
o que ficou de fora.

**Por que as duas curas são uma só costura**, e este arquivo trava isso: a
peça que devolve o CORPO do daemon numa chamada síncrona (`_corpo_do_daemon`)
sai com o teto de LEITURA de 250 ms, e o `profile.switch` não cabe nele.
Trocar só o texto, mantendo a chamada síncrona, ressuscitaria a
ATIVAR-NAO-MENTE-01 pelo avesso — todo Salvar cairia no caminho de falha por
timeout, com a ativação acontecendo.

**O que este arquivo NÃO afirma.** Que o Salvar inteiro saiu da thread do GTK.
`save_profile` continua lá (e continua sendo a exceção datada ao
`ProfileWriterMixin`). O que saiu é a perna de ~1,2 s, que é a que a medição
nomeia.
"""
from __future__ import annotations

import sys
import time
import types
from typing import Any

import pytest


from tests.conftest import skip_sem_gi_real


def _instalar_gi_falso() -> None:
    """GTK de mentira: nada aqui desenha, e a suíte não pode criar janela."""
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
        "ButtonsType", "ResponseType", "Grid", "Align",
    ):
        setattr(gtk_mod, nome, object)
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a: fn(*a)  # type: ignore[attr-defined]
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


# GUARDA-GI-REAL-01 (posto na integração de 25/08/2026): este arquivo planta um
# `gi` FALSO para medir o handler sem GTK de verdade. Sem uma guarda declarada
# ele rodaria verde contra widgets de mentira no job `lint-test` e NUNCA entraria
# no `gtk-real`, que seleciona os arquivos de interface por
# `grep -rlE 'exigir_gi_real|skip_sem_gi_real'`. O marcador abaixo é o que o
# portão `test_guarda_gi_falso_precisa_de_exigir_gi_real` aceita por AST —
# menção em comentário não vale, e é de propósito.
pytestmark = skip_sem_gi_real

_instalar_gi_falso()

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

#: O relatório que o daemon manda quando o gate R-04 recusa UMA seção e deixa
#: outra passar — é o cenário do §2.2/2, e é a razão de o toast existir.
RECUSA_DO_R04: dict[str, Any] = {
    "secoes": {"mode": "aplicado", "rumble_policy": "adiado_lock_manual"}
}
#: E quando o lock manual dela recusa TUDO: aí não sobra o que celebrar.
RECUSA_TOTAL: dict[str, Any] = {"secoes": {"rumble_policy": "adiado_lock_manual"}}
#: E o relatório de quando tudo entrou.
TUDO_ENTROU: dict[str, Any] = {"secoes": {"rumble_policy": "aplicado"}}


# ---------------------------------------------------------------------------
# A frase — função PURA, lida sem GTK e sem daemon
# ---------------------------------------------------------------------------


class TestAFraseDoSalvar:
    def test_sem_reaplicar_nao_diz_uma_palavra_sobre_o_controle(self) -> None:
        """O perfil salvo não era o ativo: o disco mudou, o controle não."""
        assert pa.mensagem_do_salvar("Sackboy") == "Perfil salvo: Sackboy"

    def test_reaplicado_sem_relatorio_mantem_a_frase_que_ela_aprovou(self) -> None:
        """Daemon antigo, ou resposta sem `secoes`: sem informação, sem alarme."""
        assert pa.mensagem_do_salvar("Sackboy", reaplicou=True) == (
            "Perfil salvo e reaplicado no controle: Sackboy"
        )

    def test_reaplicado_com_tudo_dentro_mantem_a_frase_de_sempre(self) -> None:
        assert pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=TUDO_ENTROU
        ) == "Perfil salvo e reaplicado no controle: Sackboy"

    def test_secao_recusada_e_nomeada_em_vez_de_comemorada(self) -> None:
        """MORDE o P3b: com a cura arrancada sai o texto plano de hoje."""
        frase = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_DO_R04
        )
        assert "reaplicado no controle" not in frase, (
            "o gate R-04 recusou a seção e a janela disse que aplicou"
        )
        assert "vibração" in frase, "o toast não nomeia o que ficou de fora"

    def test_a_frase_do_que_ficou_de_fora_e_a_mesma_do_botao_ativar(self) -> None:
        """Igualdade, não semelhança: dois donos da mesma frase derivam.

        A ATIVAR-NAO-MENTE-01 já escolheu as palavras e ela já as viu. Se
        alguém reescrever aqui, nasce o par F5 número nove — a mesma tela
        dizendo o mesmo fato com duas redações.
        """
        do_salvar = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_DO_R04
        )
        do_ativar = pa.mensagem_de_ativacao("Sackboy", RECUSA_DO_R04)
        cauda_salvar = do_salvar.split(" — ", 1)[1]
        cauda_ativar = do_ativar.split(" — ", 1)[1]
        assert cauda_salvar == cauda_ativar

    def test_o_rename_diz_os_dois_nomes_nos_tres_estados(self) -> None:
        assert pa.mensagem_do_salvar("Sackboy", "sackboy_nativo") == (
            "Perfil renomeado: sackboy_nativo → Sackboy"
        )
        assert pa.mensagem_do_salvar(
            "Sackboy", "sackboy_nativo", reaplicou=True
        ) == "Perfil renomeado: sackboy_nativo → Sackboy (reaplicado no controle)"
        com_recusa = pa.mensagem_do_salvar(
            "Sackboy", "sackboy_nativo", reaplicou=True, result=RECUSA_DO_R04
        )
        assert "sackboy_nativo → Sackboy" in com_recusa
        assert "reaplicado no controle" not in com_recusa
        assert "vibração" in com_recusa

    def test_com_tudo_recusado_a_frase_diz_que_nada_chegou(self) -> None:
        """O caso mais caro: o lock manual dela recusa a troca inteira."""
        frase = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_TOTAL
        )
        assert frase == "Perfil salvo: Sackboy — Nada foi aplicado ao controle."


# ---------------------------------------------------------------------------
# A fiação: o editor de verdade, com o disco e os diálogos interceptados
# ---------------------------------------------------------------------------


class _Entry:
    def __init__(self, texto: str = "") -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, texto: str) -> None:
        self._t = texto


class _Escala:
    def get_value(self) -> float:
        return 0.0

    def set_value(self, _v: float) -> None: ...


class _Editor(pa.ProfilesActionsMixin):  # type: ignore[misc]
    """Só o que a decisão de gravar consulta — mesmo molde do R-10."""

    def __init__(self, nome: str = "Sackboy", ativo: str | None = "Sackboy") -> None:
        self._profiles_cache: list[Profile] = []
        self._duplicate_source = None
        self._new_profile = True
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _Entry(nome),
            "profile_priority_scale": _Escala(),
            "main_window": object(),
        }
        self.ativo = ativo
        self.toasts: list[str] = []
        self.salvos: list[Profile] = []

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_profile_name(self, _selection: Any = None) -> str | None:
        return None

    def _build_profile_from_editor(self) -> Profile:
        return Profile(
            name=self._widgets["profile_name_entry"].get_text(),
            match=MatchAny(),
            priority=0,
        )

    def _reload_profiles_store(self, **_kw: Any) -> None: ...

    def _notify_launch_env_refresh(self) -> None: ...

    def _reconciliar_rascunho_com_perfil_salvo(self, *_a: Any) -> None: ...

    def pegar_carona_no_gesto(self, _gesto: str = "") -> None: ...

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


@pytest.fixture
def editor(monkeypatch: pytest.MonkeyPatch) -> _Editor:
    ed = _Editor()
    monkeypatch.setattr(pa, "save_profile", lambda p: ed.salvos.append(p))
    monkeypatch.setattr(pa, "delete_profile", lambda _n: None)
    monkeypatch.setattr(pa, "active_profile_name", lambda: ed.ativo)
    return ed


class TestOSalvarNaoSeguraAJanela:
    def test_o_switch_sai_pela_ponte_assincrona_com_a_folga_dele(
        self, editor: _Editor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE a fiação: a chamada certa no timeout errado não cura nada.

        É a lição literal da ATIVAR-NAO-MENTE-01 — o `profile.switch` mandado
        no teto de LEITURA (250 ms) reporta falha de uma troca que aconteceu.
        """
        vistos: list[tuple[str, Any, float]] = []

        def _call_async(
            method: str,
            params: dict[str, Any] | None = None,
            on_success: Any = None,
            on_failure: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            vistos.append((method, params, timeout_s))

        monkeypatch.setattr(pa, "call_async", _call_async)
        editor.on_profile_save(None)

        assert vistos == [
            ("profile.switch", {"name": "Sackboy"}, pa.PROFILE_SWITCH_TIMEOUT_S)
        ]

    def test_o_salvar_volta_em_menos_de_100_ms_com_o_daemon_lento(
        self, editor: _Editor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE o P3: com a chamada síncrona de volta, isto leva ~1,2 s.

        O 1,2 s não é inventado — é o número medido no journal dela, o mesmo
        que o comentário de `on_profile_activate` registra.
        """
        def _daemon_lento(
            method: str, params: Any = None, timeout: Any = None
        ) -> Any:
            time.sleep(1.2)
            return TUDO_ENTROU

        monkeypatch.setattr(ipc_bridge, "_run_call", _daemon_lento)

        comeco = time.monotonic()
        editor.on_profile_save(None)
        gasto = time.monotonic() - comeco

        assert gasto < 0.1, (
            f"o Salvar segurou a thread do GTK por {gasto:.2f} s — é o "
            "congelamento que a ATIVAR-NAO-MENTE-01 já tinha tirado do Ativar"
        )
        assert editor.salvos, "e o perfil tem de estar gravado ANTES de voltar"


class TestOToastDoSalvarLeORelatorio:
    def test_a_secao_recusada_chega_ao_rodape(
        self, editor: _Editor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho inteiro: Salvar → daemon recusa uma seção → a tela diz."""
        monkeypatch.setattr(
            pa,
            "call_async",
            lambda method, params=None, on_success=None, on_failure=None,
            timeout_s=0.25: on_success(RECUSA_DO_R04),
        )
        editor.on_profile_save(None)

        assert editor.toasts[-1] == pa.mensagem_do_salvar(
            "Sackboy", None, reaplicou=True, result=RECUSA_DO_R04
        )
        assert "reaplicado no controle" not in editor.toasts[-1]

    def test_daemon_que_nao_responde_nao_vira_falha_do_salvar(
        self, editor: _Editor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O arquivo foi gravado, e isso é fato. Quem calou foi o daemon."""
        monkeypatch.setattr(
            pa,
            "call_async",
            lambda method, params=None, on_success=None, on_failure=None,
            timeout_s=0.25: on_failure(OSError("daemon offline")),
        )
        editor.on_profile_save(None)

        assert editor.toasts[-1] == "Perfil salvo: Sackboy"
        assert editor.salvos, "o disco mudou mesmo com o daemon calado"

    def test_perfil_que_nao_era_o_ativo_nem_chama_o_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reaplicar o que não estava valendo trocaria o perfil dela sem gesto."""
        ed = _Editor(nome="Outro", ativo="Sackboy")
        monkeypatch.setattr(pa, "save_profile", lambda p: ed.salvos.append(p))
        monkeypatch.setattr(pa, "delete_profile", lambda _n: None)
        monkeypatch.setattr(pa, "active_profile_name", lambda: ed.ativo)
        chamou: list[str] = []
        monkeypatch.setattr(
            pa,
            "call_async",
            lambda method, params=None, on_success=None, on_failure=None,
            timeout_s=0.25: chamou.append(method),
        )
        ed.on_profile_save(None)

        assert chamou == []
        assert ed.toasts[-1] == "Perfil salvo: Outro"
