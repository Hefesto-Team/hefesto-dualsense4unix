"""R-10 (auditoria 23/07) — a identidade do arquivo é o SLUG, não o nome na tela.

Dois estragos, os dois SEM aviso nenhum:

1. **Guardas por nome de exibição.** `save_profile` grava
   `<slugify(name)>.json`, então "Navegacao" (sem cedilha nem acento) e
   "Navegação" são o MESMO arquivo. As duas guardas de `on_profile_save` —
   a de sobrescrita (BUG-PROFILE-SAVE-SILENT-OVERWRITE-01) e a de downgrade
   para `MatchAny` (COR-A) — comparavam `profile.name` com nomes de exibição,
   então nenhuma das duas disparava: `navegacao.json` era substituído e o
   toast dizia "Perfil salvo".

2. **Rename que não migra.** Trocar o nome no campo Nome e clicar Salvar
   gravava o arquivo NOVO e deixava o antigo em disco. Os dois nascem com o
   mesmo `match` e a mesma prioridade (BUG-RENAME-DROPS-CONFIG-01 copia a
   config do selecionado), logo passam a disputar as mesmas janelas — e o
   perfil "renomeado" continua ativando sozinho.

Hermético: stubs de `gi.repository` quando o PyGObject real falta (padrão de
`test_profiles_editor_mode.py`) e um editor fake com os métodos REAIS do mixin.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

pytest.importorskip("gi")


def _install_gi_stubs() -> None:
    """Stubs mínimos de ``gi.repository`` (armadilha A-12: venv de CI sem PyGObject)."""
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

from hefesto_dualsense4unix.app.actions import profiles_actions as pa  # noqa: E402
from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.profiles.slug import (  # noqa: E402
    find_by_slug,
    mesmo_slug,
    slugify,
)

NAVEGACAO = Profile(
    name="Navegação",
    match=MatchCriteria(window_class=["firefox"]),
    priority=50,
)
SACKBOY = Profile(
    name="sackboy_nativo",
    match=MatchCriteria(window_class=["steam_app_1599660"]),
    priority=80,
)


# ---------------------------------------------------------------------------
# Helpers puros (valem sem GTK)
# ---------------------------------------------------------------------------


class TestSlugHelpers:
    def test_navegacao_sem_acento_e_o_mesmo_arquivo(self) -> None:
        assert slugify("Navegacao") == slugify("Navegação") == "navegacao"
        assert mesmo_slug("Navegacao", "Navegação")

    def test_nomes_diferentes_nao_colidem(self) -> None:
        assert not mesmo_slug("Navegação", "Jogos")

    def test_nome_vazio_nao_e_o_mesmo_arquivo_que_nada(self) -> None:
        """`slugify` levanta em nome vazio e o editor chama isto A CADA TECLA."""
        assert mesmo_slug("", "") is False
        assert mesmo_slug("   ", "Navegação") is False

    def test_find_by_slug_devolve_o_perfil_realmente_afetado(self) -> None:
        achado = find_by_slug("Navegacao", [SACKBOY, NAVEGACAO])
        assert achado is not None and achado.name == "Navegação"

    def test_find_by_slug_tolera_nome_sem_slug(self) -> None:
        assert find_by_slug("", [NAVEGACAO]) is None
        assert find_by_slug("Navegacao", []) is None


# ---------------------------------------------------------------------------
# Editor fake: métodos REAIS do mixin sobre widgets fake
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = value

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value


class _EditorSalvar(pa.ProfilesActionsMixin):
    """Stub de `on_profile_save`: só o que a decisão de gravar consulta."""

    def __init__(
        self,
        *,
        cache: list[Profile],
        selecionado: str | None,
        nome_digitado: str,
        match_editado: MatchAny | MatchCriteria | None = None,
    ) -> None:
        self._profiles_cache = list(cache)
        self._selecionado = selecionado
        self._match_editado = match_editado
        self._duplicate_source = None
        self._new_profile = False
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(nome_digitado),
            "profile_priority_scale": _FakeScale(0),
            "main_window": object(),
        }
        # Registro do que aconteceu.
        self.salvos: list[Profile] = []
        self.deletados: list[str] = []
        self.switches: list[str] = []
        self.toasts: list[str] = []
        self.overwrite_perguntado: list[str] = []
        self.downgrade_perguntado: list[str] = []
        self.rename_perguntado: list[tuple[str, str]] = []
        # Respostas dos diálogos (default: confirma tudo).
        self.resposta_overwrite = True
        self.resposta_downgrade = True
        self.resposta_rename: str | None = "renomear"
        self.ativo = selecionado

    # --- ganchos do mixin ---
    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self._selecionado

    def _build_profile_from_editor(self) -> Profile:
        base = find_by_slug(self._selecionado or "", self._profiles_cache)
        match = self._match_editado or (
            base.match if base is not None else MatchAny()
        )
        return Profile(
            name=self._widgets["profile_name_entry"].get_text(),
            match=match,
            priority=base.priority if base is not None else 0,
        )

    def _prompt_rename_or_copy(self, antigo: str, novo: str) -> str | None:
        self.rename_perguntado.append((antigo, novo))
        return self.resposta_rename

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


def _rodar_save(
    editor: _EditorSalvar, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Executa `on_profile_save` real com disco/IPC/diálogos interceptados."""
    import hefesto_dualsense4unix.app.gui_dialogs as gd

    monkeypatch.setattr(
        gd,
        "prompt_overwrite_existing",
        lambda parent, name: (
            editor.overwrite_perguntado.append(name) or editor.resposta_overwrite
        ),
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "confirm_downgrade_match_to_any",
        lambda parent, name: (
            editor.downgrade_perguntado.append(name) or editor.resposta_downgrade
        ),
        raising=False,
    )
    monkeypatch.setattr(pa, "save_profile", lambda p: editor.salvos.append(p))
    monkeypatch.setattr(pa, "delete_profile", lambda n: editor.deletados.append(n))
    monkeypatch.setattr(pa, "active_profile_name", lambda: editor.ativo)
    monkeypatch.setattr(
        pa, "profile_switch", lambda n: bool(editor.switches.append(n)) or True
    )
    editor.on_profile_save(None)


class TestGuardaDeSobrescritaPorSlug:
    def test_navegacao_sem_acento_pergunta_nomeando_a_vitima(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso medido: "Novo perfil" chamado "Navegacao" com "Navegação" no disco."""
        ed = _EditorSalvar(
            cache=[NAVEGACAO, SACKBOY],
            selecionado="Navegação",
            nome_digitado="Navegacao",
        )
        ed._new_profile = True  # é um perfil NOVO, não a edição da Navegação
        ed.resposta_overwrite = False  # ela cancela ao ver o aviso
        _rodar_save(ed, monkeypatch)

        assert ed.overwrite_perguntado == ["Navegação"], (
            "sem a guarda por slug, navegacao.json era substituído sem aviso; "
            "e o aviso tem de citar o perfil REALMENTE afetado"
        )
        assert ed.salvos == [], "cancelar não pode tocar o arquivo"

    def test_edicao_in_place_nao_pergunta_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Salvar o próprio perfil selecionado segue sendo 1 clique."""
        ed = _EditorSalvar(
            cache=[NAVEGACAO],
            selecionado="Navegação",
            nome_digitado="Navegação",
        )
        _rodar_save(ed, monkeypatch)
        assert ed.overwrite_perguntado == []
        assert ed.rename_perguntado == []
        assert [p.name for p in ed.salvos] == ["Navegação"]

    def test_trocar_so_a_acentuacao_e_edicao_do_mesmo_arquivo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Navegação" → "Navegacao" com a própria linha selecionada não é rename."""
        ed = _EditorSalvar(
            cache=[NAVEGACAO],
            selecionado="Navegação",
            nome_digitado="Navegacao",
        )
        _rodar_save(ed, monkeypatch)
        assert ed.rename_perguntado == []
        assert ed.deletados == [], "é o MESMO arquivo — não há antigo a apagar"
        assert [p.name for p in ed.salvos] == ["Navegacao"]


class TestGuardaDeDowngradePorSlug:
    def test_downgrade_para_any_pergunta_mesmo_com_nome_sem_acento(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COR-A comparava por nome de exibição e não via a vítima pelo slug."""
        ed = _EditorSalvar(
            cache=[NAVEGACAO],
            selecionado="Navegação",
            nome_digitado="Navegacao",
            match_editado=MatchAny(),
        )
        ed.resposta_downgrade = False
        _rodar_save(ed, monkeypatch)

        assert ed.downgrade_perguntado == ["Navegação"]
        assert ed.salvos == [], "cancelar não pode apagar o alvo do perfil"


class TestRenameMigra:
    def test_renomear_apaga_o_antigo_depois_do_save(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ed = _EditorSalvar(
            cache=[SACKBOY],
            selecionado="sackboy_nativo",
            nome_digitado="Sackboy",
        )
        _rodar_save(ed, monkeypatch)

        assert ed.rename_perguntado == [("sackboy_nativo", "Sackboy")]
        assert [p.name for p in ed.salvos] == ["Sackboy"]
        assert ed.deletados == ["sackboy_nativo"], (
            "sem a migração ficam DOIS perfis com o mesmo match e a mesma "
            "prioridade disputando a janela do jogo"
        )

    def test_salvar_como_copia_preserva_os_dois(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ed = _EditorSalvar(
            cache=[SACKBOY],
            selecionado="sackboy_nativo",
            nome_digitado="Sackboy",
        )
        ed.resposta_rename = "copia"
        _rodar_save(ed, monkeypatch)

        assert [p.name for p in ed.salvos] == ["Sackboy"]
        assert ed.deletados == []

    def test_cancelar_o_rename_nao_grava_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ed = _EditorSalvar(
            cache=[SACKBOY],
            selecionado="sackboy_nativo",
            nome_digitado="Sackboy",
        )
        ed.resposta_rename = None
        _rodar_save(ed, monkeypatch)

        assert ed.salvos == []
        assert ed.deletados == []

    def test_marker_do_perfil_ativo_acompanha_o_rename(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem migrar o marker, o boot seguinte procura um perfil apagado."""
        ed = _EditorSalvar(
            cache=[SACKBOY],
            selecionado="sackboy_nativo",
            nome_digitado="Sackboy",
        )
        ed.ativo = "sackboy_nativo"
        _rodar_save(ed, monkeypatch)

        assert ed.switches == ["Sackboy"]

    def test_perfil_novo_nao_dispara_rename(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Novo perfil" com uma linha selecionada não pode APAGAR aquela linha."""
        ed = _EditorSalvar(
            cache=[NAVEGACAO],
            selecionado="Navegação",
            nome_digitado="Jogos",
        )
        ed._new_profile = True
        _rodar_save(ed, monkeypatch)

        assert ed.rename_perguntado == []
        assert ed.deletados == []

    def test_duplicar_nao_dispara_rename(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ed = _EditorSalvar(
            cache=[NAVEGACAO],
            selecionado="Navegação",
            nome_digitado="Navegação (cópia)",
        )
        ed._duplicate_source = NAVEGACAO
        _rodar_save(ed, monkeypatch)

        assert ed.rename_perguntado == []
        assert ed.deletados == []
