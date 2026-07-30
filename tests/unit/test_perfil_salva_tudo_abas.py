"""PERFIL-SALVA-TUDO-01, a metade que vive na fronteira entre DUAS abas.

O ``mode`` do perfil ganhou um segundo escritor nesta sprint: além do seletor da
aba Perfis (``_mode_section_from_editor``), agora a aba Emulação escreve no
RASCUNHO por ``DraftConfig.with_mode`` — sem isso o gesto dela nunca chegava ao
arquivo (``grep -c 'self\\.draft'`` em ``emulation_actions.py`` = 0).

Dois escritores para a mesma seção é a classe de bug desta casa ("três
escritores do perfil sem dono", 23/07). O seletor da aba Perfis abre com o valor
do DISCO, então reescrever sempre significa: ela liga o modo jogo na aba
Emulação, salva pela aba Perfis, e o modo evapora — o SALVAR-NAO-REBAIXA-01 de
novo, na seção ``mode``.

Os testes entram pelo caminho PÚBLICO (``on_profile_save``, ``on_save_profile``),
porque este defeito SÓ existe na fronteira entre as abas: nenhum teste de módulo
isolado o veria.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no lugar de `pytest.importorskip("gi")`, que ACEITA o stub
# que outro arquivo de teste planta em sys.modules.
exigir_gi_real("PERFIL-SALVA-TUDO-01 (abas Perfis/Emulacao/rodape)")


def _install_gi_stubs() -> None:
    """Stubs mínimos de ``gi.repository`` (venv de CI sem PyGObject).

    Mesmo procedimento de ``test_abas01_conflito_entre_abas.py``: com o
    PyGObject REAL disponível não instala nada (mutar o ``gi`` real
    sobrescreveria ``GLib.idle_add`` e faria testes de GUI pularem como
    "ambiente sem GTK").
    """
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
    gdk_mod = types.ModuleType("gi.repository.Gdk")
    gobject_mod = types.ModuleType("gi.repository.GObject")
    for nome in (
        "Builder", "Window", "Button", "CheckButton", "ColorButton", "ComboBoxText",
        "DrawingArea", "Switch", "TreeView", "TreeViewColumn", "CellRendererText",
        "ListStore", "TreeSelection", "TreePath", "Box", "Label", "Frame", "Entry",
        "RadioButton", "Scale", "Stack", "MessageDialog", "MessageType",
        "ButtonsType", "ResponseType", "ToggleButton",
    ):
        setattr(gtk_mod, nome, object)
    gdk_mod.RGBA = object  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    gobject_mod.TYPE_STRING = "str"  # type: ignore[attr-defined]
    gobject_mod.TYPE_INT = "int"  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.Gdk = gdk_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.Gdk"] = gdk_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import footer_actions as fa
from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.profiles.slug import slugify

ROXO = (97, 53, 131)


def _perfil(nome: str, *, priority: int = 100, mode: Any = None) -> Profile:
    """Perfil de teste com a paleta automática DESLIGADA (ruído do COR-04 fora)."""
    return Profile(
        name=nome,
        match=MatchAny(),
        priority=priority,
        leds=LedsConfig(lightbar=ROXO, auto_player_colors=False),
        mode=mode,
    )


class _Disco:
    """Disco em memória com a identidade certa: o SLUG."""

    def __init__(self, *perfis: Profile) -> None:
        self.por_slug: dict[str, Profile] = {slugify(p.name): p for p in perfis}
        self.gravacoes: list[Profile] = []

    def salvar(self, profile: Profile) -> Path:
        self.por_slug[slugify(profile.name)] = profile
        self.gravacoes.append(profile)
        return Path(f"/perfis/{slugify(profile.name)}.json")

    def apagar(self, nome: str) -> None:
        self.por_slug.pop(slugify(nome), None)

    def todos(self) -> list[Profile]:
        return list(self.por_slug.values())

    @property
    def ultimo(self) -> Profile:
        assert self.gravacoes, "nada foi gravado — o save nem chegou ao disco"
        return self.gravacoes[-1]


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text

    def set_placeholder_text(self, _t: str) -> None:
        return None

    def set_tooltip_text(self, _t: str) -> None:
        return None


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = float(value)


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = bool(active)


class _FakeSelector:
    """Stub do SegmentedSelector: API por-ID, "changed" emitido sem argumentos."""

    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class _Janela(pa.ProfilesActionsMixin, fa.FooterActionsMixin):
    """Aba Perfis + rodapé compartilhando UM rascunho (a MRO do HefestoApp)."""

    def __init__(self, disco: _Disco, ativo: Profile) -> None:
        self._disco = disco
        self.draft = DraftConfig.from_profile(ativo)
        self._draft_baseline = self.draft
        self._active_profile_name = ativo.name
        self._profiles_cache = disco.todos()
        self._duplicate_source = None
        self._new_profile = False
        self._mode_advanced = False
        self._selecionado: str | None = ativo.name
        self._pending_brightness = float(ativo.leds.lightbar_brightness)
        self._edit_target_uniq: str | None = None
        self._refresh_guard = False
        self.resposta_overwrite = True
        self.resposta_downgrade = True
        self.resposta_rename: str | None = "renomear"
        self.nome_no_rodape = ativo.name
        self.ativo_no_daemon: str | None = ativo.name
        self.toasts: list[str] = []
        self.switches: list[str] = []

        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(ativo.name),
            "profile_priority_scale": _FakeScale(ativo.priority),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "main_window": object(),
        }
        self._aplica_a = _FakeSelector("any")
        self._mode_kind_selector = _FakeSelector("none")
        self._mode_flavor_selector = _FakeSelector("xbox")
        self._mode_gamepad_opts = None
        # PERFIL-SALVA-TUDO-01: o seletor de modo emite "changed" para os MESMOS
        # handlers do código de produção — é o que faz a marca de gesto contar.
        self._mode_kind_selector.connect("changed", self._on_mode_kind_changed)
        self._mode_flavor_selector.connect("changed", self._on_mode_flavor_changed)
        # Entrar na aba Perfis e clicar na linha do perfil ativo popula o editor.
        self._populate_editor(ativo)

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self._selecionado

    def _prompt_rename_or_copy(self, _antigo: str, _novo: str) -> str | None:
        return self.resposta_rename

    def _reload_profiles_store(
        self, select_name: str | None = None, on_done: Any | None = None
    ) -> None:
        self._profiles_cache = self._disco.todos()
        if select_name is not None:
            self._selecionado = select_name
        if on_done is not None:
            on_done()

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)


def _sync_run_in_thread(
    fn: Any, on_success: Any = None, on_failure: Any = None
) -> None:
    """``run_in_thread`` síncrono: sem loop GTK, o callback nunca rodaria."""
    try:
        resultado = fn()
    except Exception as exc:
        if on_failure is not None:
            on_failure(exc)
        return
    if on_success is not None:
        on_success(resultado)


def _ligar(janela: _Janela, monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a janela ao disco em memória e neutraliza diálogos/IPC."""
    import hefesto_dualsense4unix.app.gui_dialogs as gd

    monkeypatch.setattr(
        gd, "prompt_overwrite_existing",
        lambda parent, name: janela.resposta_overwrite, raising=False,
    )
    monkeypatch.setattr(
        gd, "confirm_downgrade_match_to_any",
        lambda parent, name: janela.resposta_downgrade, raising=False,
    )
    monkeypatch.setattr(
        gd, "prompt_profile_name",
        lambda parent, default_name="": janela.nome_no_rodape, raising=False,
    )
    monkeypatch.setattr(pa, "save_profile", janela._disco.salvar)
    monkeypatch.setattr(pa, "delete_profile", janela._disco.apagar)
    monkeypatch.setattr(pa, "active_profile_name", lambda: janela.ativo_no_daemon)
    monkeypatch.setattr(
        pa, "profile_switch", lambda n: bool(janela.switches.append(n)) or True
    )
    monkeypatch.setattr(pa, "call_async", lambda *_a, **_kw: None)
    monkeypatch.setattr(fa, "save_profile", janela._disco.salvar)
    monkeypatch.setattr(fa, "load_all_profiles", janela._disco.todos)
    monkeypatch.setattr(fa.ipc_bridge, "run_in_thread", _sync_run_in_thread)
    monkeypatch.setattr(fa.ipc_bridge, "call_async", lambda *_a, **_kw: None)


# ---------------------------------------------------------------------------
# O modo que ela ligou na aba Emulação x o seletor da aba Perfis
# ---------------------------------------------------------------------------


class TestModoDaAbaEmulacaoNaoEvapora:
    def test_salvar_pela_aba_perfis_preserva_o_modo_do_rascunho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sequência dela, clique a clique.

        aba Emulação → máscara "PlayStation" *(escreve no rascunho)* → aba
        Perfis → Salvar. O seletor de modo daqui abriu em "Não mexer no modo"
        (o que o disco dizia) e ela não o tocou — reescrever com essa leitura
        apagaria o gesto que ela acabou de fazer na outra aba.

        Sem a cura (``modo_do_rascunho_vence``), o arquivo nasce ``mode: null``,
        exatamente como ``pragmata2.json`` no disco dela.
        """
        perfil = _perfil("Pragmata")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        # Aba Emulação (o contrato que ela vai chamar: with_mode no rascunho).
        janela.draft = janela.draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        )

        # Aba Perfis: Salvar, sem tocar no seletor de modo.
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.mode is not None, (
            "a aba Perfis reescreveu o `mode` com a leitura da tela e apagou o "
            "gesto da aba Emulação"
        )
        assert salvo.mode.kind == "gamepad"
        assert salvo.mode.gamepad_flavor == "dualsense"

    def test_o_seletor_da_aba_perfis_continua_mandando_quando_ela_mexe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida do outro lado: FEAT-PROFILE-MODE-GUI-01 intacto.

        Se a cura fosse "o rascunho sempre vence", o seletor de modo da aba
        Perfis viraria enfeite — ela escolheria "Jogar direto (Sony)" e o
        arquivo nasceria com o gamepad da outra aba.
        """
        perfil = _perfil("Pragmata")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        janela.draft = janela.draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        )
        # Agora ELA mexe no seletor da aba Perfis: este é o gesto mais novo.
        janela._mode_kind_selector.set_active_id("native")
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.mode is not None and salvo.mode.kind == "native"

    def test_trocar_so_a_mascara_no_editor_tambem_conta_como_gesto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A máscara é gesto de modo — sem o sinal dela, o rascunho venceria."""
        perfil = _perfil(
            "Pragmata", mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
        )
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        janela.draft = janela.draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
        )
        janela._mode_flavor_selector.set_active_id("dualsense")
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.mode is not None
        assert salvo.mode.gamepad_flavor == "dualsense"

    def test_perfil_novo_continua_nascendo_com_o_modo_do_editor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Perfil NOVO: a base é o disco e o editor segue sendo a fonte.

        PERFIL-NASCE-CERTO-01 prefila "Jogar pelo Hefesto" no perfil novo. Se a
        exceção do ``mode`` valesse também aqui, o prefill deixaria de ser
        gravado e o perfil do jogo voltaria a nascer sem ligar nada.
        """
        perfil = _perfil("Pragmata")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        janela.draft = janela.draft.with_mode(ProfileModeConfig(kind="native"))
        janela._new_profile = True
        janela._widgets["profile_name_entry"].set_text("Jogo Novo")
        janela._esquecer_a_fotografia_do_editor()
        # O prefill do modo jogo, programático (não é gesto dela no seletor).
        janela._set_mode_editor(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        )
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.name == "Jogo Novo"
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"


class TestRodapeSalvaOModoDaAbaEmulacao:
    def test_salvar_perfil_no_rodape_leva_o_modo_e_o_modo_jogo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho do rodapé, com o MESMO nome do perfil ativo.

        É o gesto da queixa dela ("salvei o perfil"): o diálogo do rodapé abre
        pré-preenchido com o nome do perfil ativo. Antes desta sprint nem a aba
        Emulação escrevia no rascunho, nem o rascunho tinha onde guardar o
        "modo jogo" — o arquivo nascia ``mode: null`` /
        ``suppress_desktop_emulation: false`` em cima do trabalho dela.
        """
        perfil = _perfil("Pragmata")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        janela.draft = janela.draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        ).with_suppress(True)

        janela.nome_no_rodape = "Pragmata"
        janela.on_save_profile(None)

        salvo = disco.ultimo
        assert salvo.name == "Pragmata"
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"
        assert salvo.suppress_desktop_emulation is True
        # E a prioridade dela não virou 5 (a assinatura digital do defeito).
        assert salvo.priority == 100
