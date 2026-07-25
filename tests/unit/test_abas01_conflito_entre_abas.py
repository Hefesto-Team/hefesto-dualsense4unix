"""ABAS-01 — as abas brigam pelo mesmo estado (sprint 2026-07-25).

Os quatro defeitos de PERDA SILENCIOSA DE DADOS da sprint têm uma raiz comum: a
aba Perfis é a única superfície que edita e persiste perfil sem NUNCA ler nem
escrever o rascunho de edição (``self.draft``) — não havia uma única atribuição
a ele no arquivo inteiro.

- **ABAS-01** — a aba Perfis grava a seção ``mode`` direto no disco; o rodapé,
  ao salvar com o MESMO nome, reemite o ``mode`` fotografado no boot e apaga a
  seção. Vale igual para regra de janela, prioridade e supressão.
- **ABAS-02** — com o alvo em "Todos", mover o controle de brilho um pixel
  limpava o campo de cor de TODOS os ajustes por controle e não os re-semeava
  (a lista de alvos está vazia nesse ramo, porque brilho não disputa com a
  paleta automática). O evento dispara a cada movimento do arraste.
- **ABAS-03** — ao RENOMEAR, a mesclagem com o rascunho não acontecia (o nome já
  mudou, então a base vinha do disco) e o perfil antigo era apagado em seguida:
  toda edição da sessão se perdia sem aviso e sem como desfazer.
- **ABAS-04** — "Parar" e "Deixar o jogo controlar a vibração" zeravam os
  controles deslizantes mas não escreviam no rascunho.

Todos os testes entram pelo caminho PÚBLICO — o handler que o botão da tela
realmente chama, e a sequência de cliques entre abas que a sprint descreve.
Teste que chama o método privado direto passa com a cura arrancada; é a lição
que custou caro nesta casa, e ela vale mais aqui do que em qualquer outro lugar,
porque estes quatro defeitos SÓ existem na fronteira entre duas abas.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("gi")


def _install_gi_stubs() -> None:
    """Stubs mínimos de ``gi.repository`` (armadilha A-12: venv de CI sem PyGObject).

    Mesmo procedimento de ``test_r10_slug_e_rename.py``: com o PyGObject REAL
    disponível não instala nada (mutar o ``gi`` real sobrescreveria
    ``GLib.idle_add`` e faria testes de GUI pularem como "ambiente sem GTK").
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

from hefesto_dualsense4unix.app.actions import footer_actions as fa  # noqa: E402
from hefesto_dualsense4unix.app.actions import lightbar_actions as la  # noqa: E402
from hefesto_dualsense4unix.app.actions import profiles_actions as pa  # noqa: E402
from hefesto_dualsense4unix.app.actions import rumble_actions as ra  # noqa: E402
from hefesto_dualsense4unix.app.draft_config import DraftConfig  # noqa: E402
from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    RumbleConfig,
)
from hefesto_dualsense4unix.profiles.slug import slugify  # noqa: E402

#: MACs forjados da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

ROXO = (129, 61, 156)
AZUL = (0, 0, 255)
VERMELHO = (255, 0, 0)


# ---------------------------------------------------------------------------
# Perfis e disco em memória
# ---------------------------------------------------------------------------


def _perfil(
    nome: str,
    *,
    match: Any = None,
    priority: int = 5,
    mode: dict[str, Any] | None = None,
    cor: tuple[int, int, int] = ROXO,
    controllers: dict[str, ControllerOverrides] | None = None,
    rumble: RumbleConfig | None = None,
) -> Profile:
    """Perfil de teste com a paleta automática DESLIGADA.

    O automático ligado faria o D4 (COR-04/R-14) entrar em cena a cada clique de
    cor sem controles conectados conhecidos — comportamento coberto em
    ``test_lightbar_todos_por_mac_r14.py`` e ruído puro aqui, onde o que está sob
    teste é o que sobrevive ao salvar.
    """
    dados: dict[str, Any] = {
        "name": nome,
        "version": 1,
        "match": (match or MatchAny()).model_dump(mode="python"),
        "priority": priority,
        "leds": LedsConfig(lightbar=list(cor), auto_player_colors=False).model_dump(
            mode="python"
        ),
    }
    if mode is not None:
        dados["mode"] = mode
    if rumble is not None:
        dados["rumble"] = rumble.model_dump(mode="python")
    perfil = Profile.model_validate(dados)
    if controllers:
        perfil = perfil.model_copy(update={"controllers": controllers})
    return perfil


class _Disco:
    """Disco em memória: ``save_profile`` grava aqui, ``load_all_profiles`` lê daqui.

    A identidade é o SLUG, como no disco de verdade (``save_profile`` grava
    ``<slugify(name)>.json``) — é o que faz o rename apagar o arquivo certo.
    """

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


# ---------------------------------------------------------------------------
# Widgets fake (mesma API por-ID do SegmentedSelector; sem GTK real)
# ---------------------------------------------------------------------------


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


class _FakeRGBA:
    def __init__(self, r: float, g: float, b: float) -> None:
        self.red = r
        self.green = g
        self.blue = b
        self.alpha = 1.0


class _FakeColorButton:
    """Botão de cor da aba Lightbar (só o que ``on_lightbar_color_set`` lê)."""

    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgba = _FakeRGBA(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

    def get_rgba(self) -> _FakeRGBA:
        return self._rgba

    def set_rgba(self, rgba: Any) -> None:
        self._rgba = rgba


# ---------------------------------------------------------------------------
# A janela: as MESMAS abas da tela, na mesma MRO do HefestoApp
# ---------------------------------------------------------------------------


class _Janela(pa.ProfilesActionsMixin, la.LightbarActionsMixin, fa.FooterActionsMixin):
    """Aba Perfis + aba Lightbar + rodapé compartilhando UM rascunho.

    É a montagem mínima que reproduz o conflito da sprint: os três mixins
    convivem na MRO do ``HefestoApp`` de verdade e disputam ``self.draft``.
    Testar cada um isolado é justamente o que deixou os quatro defeitos
    passarem — nenhum deles existe dentro de um único arquivo.
    """

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
        # Respostas dos diálogos (default: confirma tudo, como quem clica "sim").
        self.resposta_overwrite = True
        self.resposta_downgrade = True
        self.resposta_rename: str | None = "renomear"
        self.nome_no_rodape = ativo.name
        self.ativo_no_daemon: str | None = ativo.name
        # Registro do que aconteceu.
        self.toasts: list[str] = []
        self.switches: list[str] = []
        self.renames_perguntados: list[tuple[str, str]] = []

        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(ativo.name),
            "profile_priority_scale": _FakeScale(ativo.priority),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "lightbar_color_button": _FakeColorButton(ROXO),
            "main_window": object(),
        }
        self._aplica_a = _FakeSelector("any")
        self._mode_kind_selector = _FakeSelector("none")
        self._mode_flavor_selector = _FakeSelector("xbox")
        self._mode_gamepad_opts = None
        # Entrar na aba Perfis e clicar na linha do perfil ativo é o gesto que
        # popula o editor — inclusive a seção "Modo" e o "Aplica a".
        self._populate_editor(ativo)

    # --- ganchos do host ---

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self._selecionado

    def _prompt_rename_or_copy(self, antigo: str, novo: str) -> str | None:
        self.renames_perguntados.append((antigo, novo))
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
    except Exception as exc:  # espelha o run_in_thread real
        if on_failure is not None:
            on_failure(exc)
        return
    if on_success is not None:
        on_success(resultado)


def _ligar(janela: _Janela, monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a janela ao disco em memória e neutraliza diálogos/IPC."""
    import hefesto_dualsense4unix.app.gui_dialogs as gd

    monkeypatch.setattr(
        gd,
        "prompt_overwrite_existing",
        lambda parent, name: janela.resposta_overwrite,
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "confirm_downgrade_match_to_any",
        lambda parent, name: janela.resposta_downgrade,
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "prompt_profile_name",
        lambda parent, default_name="": janela.nome_no_rodape,
        raising=False,
    )
    # Aba Perfis.
    monkeypatch.setattr(pa, "save_profile", janela._disco.salvar)
    monkeypatch.setattr(pa, "delete_profile", janela._disco.apagar)
    monkeypatch.setattr(pa, "active_profile_name", lambda: janela.ativo_no_daemon)
    monkeypatch.setattr(
        pa, "profile_switch", lambda n: bool(janela.switches.append(n)) or True
    )
    monkeypatch.setattr(pa, "call_async", lambda *_a, **_kw: None)
    # Rodapé.
    monkeypatch.setattr(fa, "save_profile", janela._disco.salvar)
    monkeypatch.setattr(fa, "load_all_profiles", janela._disco.todos)
    monkeypatch.setattr(fa.ipc_bridge, "run_in_thread", _sync_run_in_thread)
    monkeypatch.setattr(fa.ipc_bridge, "call_async", lambda *_a, **_kw: None)
    # Aba Lightbar (o clique na cor não pode tentar falar com o daemon).
    monkeypatch.setattr(la, "led_set", lambda *_a, **_kw: True)
    monkeypatch.setattr(la, "player_leds_set", lambda *_a, **_kw: True)


# ---------------------------------------------------------------------------
# ABAS-01 — o "Salvar Perfil" do rodapé apagava o que a aba Perfis gravou
# ---------------------------------------------------------------------------


class TestABAS01ModoNaoEvapora:
    def test_o_modo_da_aba_perfis_sobrevive_ao_salvar_do_rodape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reprodução literal da sprint, clique a clique.

        aba Perfis → Modo = "Jogar pelo Hefesto" → Salvar *(grava certo)* → aba
        Lightbar → muda a cor → rodapé "Salvar Perfil" → a seção ``mode`` SOME.

        Sem a cura, o rodapé reemite o ``source_mode`` fotografado no boot da
        janela (``None``, porque o perfil ainda não tinha modo) por cima do que
        a aba Perfis acabou de gravar. É o MODO-01 visto de outro ângulo: ela
        faz tudo certo e o modo do perfil evapora.
        """
        perfil = _perfil("vitoria")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        # Aba Perfis: "Jogar pelo Hefesto" com os botões do PlayStation.
        janela._mode_kind_selector.set_active_id("gamepad")
        janela._mode_flavor_selector.set_active_id("dualsense")
        janela.on_profile_save(None)

        gravado_pela_aba = disco.ultimo
        assert gravado_pela_aba.mode is not None
        assert gravado_pela_aba.mode.kind == "gamepad"

        # Aba Lightbar: ela muda a cor (handler real do botão de cor).
        janela.on_lightbar_color_set(_FakeColorButton(AZUL))
        assert janela.draft.leds.lightbar_rgb == AZUL

        # Rodapé: "Salvar Perfil" com o MESMO nome.
        janela.on_save_profile(None)

        salvo = disco.ultimo
        assert salvo.name == "vitoria"
        assert tuple(salvo.leds.lightbar) == AZUL, "a cor nova tinha de ir junto"
        assert salvo.mode is not None and salvo.mode.kind == "gamepad", (
            "o rodapé reemitia o `mode` do boot (None) e apagava a seção que a "
            "aba Perfis tinha acabado de gravar"
        )
        assert salvo.mode.gamepad_flavor == "dualsense"

    def test_regra_e_prioridade_da_aba_perfis_tambem_sobrevivem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Vale igual para critério de janela, prioridade e supressão."

        Mesma sequência, outras seções: o rodapé reemitia ``source_match`` e
        ``source_priority`` do boot, então o perfil voltava a ser "Sempre" com
        a prioridade antiga — e o perfil do jogo parava de entrar sozinho.
        """
        perfil = _perfil("vitoria", priority=5)
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        # Aba Perfis: "Jogo da Steam" + appid + prioridade alta.
        janela._aplica_a.set_active_id("steam_game")
        janela._widgets["profile_simple_custom_name"].set_text("1599660")
        janela._widgets["profile_priority_scale"].set_value(80)
        janela.on_profile_save(None)

        assert isinstance(disco.ultimo.match, MatchCriteria)
        assert disco.ultimo.match.window_class == ["steam_app_1599660"]
        assert disco.ultimo.priority == 80

        # Aba Lightbar + rodapé.
        janela.on_lightbar_color_set(_FakeColorButton(AZUL))
        janela.on_save_profile(None)

        salvo = disco.ultimo
        assert isinstance(salvo.match, MatchCriteria), (
            "o rodapé devolvia o perfil para 'Sempre' e o jogo perdia a regra"
        )
        assert salvo.match.window_class == ["steam_app_1599660"]
        assert salvo.priority == 80
        assert tuple(salvo.leds.lightbar) == AZUL


# ---------------------------------------------------------------------------
# ABAS-03 — renomear na aba Perfis descartava o rascunho inteiro
# ---------------------------------------------------------------------------


class TestABAS03RenomearNaoDescartaORascunho:
    def test_renomear_preserva_a_cor_editada_na_sessao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O pior dos quatro: a perda é irreversível.

        A mesclagem com o rascunho só ocorria quando o nome batia com o do
        perfil ativo. Ao renomear, o nome JÁ mudou — a base vinha do disco — e
        logo depois ``on_profile_save`` apaga o perfil antigo. Toda a edição de
        cor, gatilho, vibração e teclado da sessão ia junto, sem aviso e sem o
        arquivo de origem para voltar atrás.
        """
        perfil = _perfil("sackboy_nativo", priority=80, cor=ROXO)
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        # Aba Lightbar: a edição da sessão, que só existe no rascunho.
        janela.on_lightbar_color_set(_FakeColorButton(AZUL))

        # Aba Perfis: ela troca o nome no campo Nome e clica Salvar.
        janela._widgets["profile_name_entry"].set_text("Sackboy")
        janela.on_profile_save(None)

        assert janela.renames_perguntados == [("sackboy_nativo", "Sackboy")]
        salvo = disco.ultimo
        assert salvo.name == "Sackboy"
        assert tuple(salvo.leds.lightbar) == AZUL, (
            "renomear descartava o rascunho e gravava a cor do DISCO — e o "
            "perfil de origem já tinha sido apagado"
        )
        assert disco.por_slug.get("sackboy_nativo") is None, "o antigo migra"

    def test_renomear_preserva_os_ajustes_por_controle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Os overrides por-MAC também moram no rascunho (PERFIL-04)."""
        perfil = _perfil("sackboy_nativo")
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        # Aba Lightbar com o Controle 2 selecionado no banner.
        janela._edit_target_uniq = UNIQ_2
        janela.on_lightbar_color_set(_FakeColorButton(VERMELHO))
        janela._edit_target_uniq = None

        janela._widgets["profile_name_entry"].set_text("Sackboy")
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.controllers is not None, (
            "o ajuste por controle da sessão tinha de viajar com o rename"
        )
        assert tuple(salvo.controllers[UNIQ_2].leds.lightbar) == VERMELHO

    def test_o_nome_do_perfil_ativo_migra_com_o_rename(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Depois do rename, o rascunho descreve o perfil NOVO.

        Sem migrar o nome, o rodapé continuaria oferecendo o nome antigo (cujo
        arquivo já não existe) e a reconciliação do tick de 2 Hz leria o
        ``profile.switch`` de migração como "trocaram de perfil por fora".
        """
        perfil = _perfil("sackboy_nativo", mode={"kind": "native"})
        disco = _Disco(perfil)
        janela = _Janela(disco, perfil)
        _ligar(janela, monkeypatch)

        janela._widgets["profile_name_entry"].set_text("Sackboy")
        janela.on_profile_save(None)

        assert janela._active_profile_name == "Sackboy"
        assert janela.draft.source_name == "Sackboy"
        assert janela.draft.source_mode is not None
        assert janela.draft.source_mode.kind == "native"

        # E o "Salvar Perfil" do rodapé, logo em seguida, mantém o modo.
        janela.nome_no_rodape = "Sackboy"
        janela.on_lightbar_color_set(_FakeColorButton(AZUL))
        janela.on_save_profile(None)
        assert disco.ultimo.mode is not None
        assert disco.ultimo.mode.kind == "native"


class TestOutroPerfilNaoRoubaORascunho:
    def test_salvar_outro_perfil_pela_aba_nao_usa_o_rascunho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A contrapartida da cura: a mesclagem é do perfil DO rascunho, e só.

        Salvar um perfil que não é o que as demais abas estão editando não pode
        levar a configuração delas junto — seria trocar uma perda de dados por
        uma contaminação silenciosa entre perfis (a mesma classe do R-09).
        """
        ativo = _perfil("vitoria", cor=ROXO)
        outro = _perfil("navegacao", cor=VERMELHO)
        disco = _Disco(ativo, outro)
        janela = _Janela(disco, ativo)
        _ligar(janela, monkeypatch)

        # Ela mexe na cor (rascunho do perfil ATIVO)...
        janela.on_lightbar_color_set(_FakeColorButton(AZUL))
        # ...e depois seleciona OUTRO perfil na lista e o salva.
        janela._selecionado = "navegacao"
        janela._populate_editor(outro)
        janela.on_profile_save(None)

        salvo = disco.ultimo
        assert salvo.name == "navegacao"
        assert tuple(salvo.leds.lightbar) == VERMELHO, (
            "a cor do rascunho é do perfil ativo — não pode vazar para outro"
        )
        assert janela._active_profile_name == "vitoria"
        assert janela.draft.source_name == "vitoria"


# ---------------------------------------------------------------------------
# ABAS-02 — arrastar o brilho em "Todos" destruía as cores por controle
# ---------------------------------------------------------------------------


class _AbaLightbar(la.LightbarActionsMixin):
    """Só a aba Lightbar, com o alvo do banner controlável."""

    def __init__(self, draft: DraftConfig, uniq: str | None) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        self._refresh_guard = False
        self.toasts: list[str] = []

    def _get(self, _widget_id: str) -> None:
        return None

    def _toast_light(self, msg: str) -> None:
        self.toasts.append(msg)


def _draft_com_duas_cores_proprias() -> DraftConfig:
    """Controle 1 azul e Controle 2 vermelho, sobre um global roxo."""
    perfil = _perfil("vitoria", cor=ROXO)
    draft = DraftConfig.from_profile(perfil)
    for uniq, cor in ((UNIQ_1, AZUL), (UNIQ_2, VERMELHO)):
        base = draft.effective_leds_for(uniq)
        draft = draft.with_controller_leds(
            uniq, base.model_copy(update={"lightbar_rgb": cor})
        )
    return draft


class TestABAS02BrilhoEmTodosNaoApagaAsCores:
    def test_um_pixel_de_brilho_nao_destroi_as_cores_por_controle(self) -> None:
        """Repro: alvo em "Todos", um movimento do controle de brilho.

        O campo de cor saía de TODOS os overrides junto com o brilho (cor e
        brilho formam um único campo no estado desejado do backend) e não era
        re-semeado: a lista de alvos fica vazia neste ramo, porque brilho não
        disputa com a paleta automática. Controle 1 azul e Controle 2 vermelho
        viravam nada — e o "Salvar Perfil" persistia a perda.
        """
        host = _AbaLightbar(_draft_com_duas_cores_proprias(), None)  # alvo: Todos

        host.on_lightbar_brightness_changed(_FakeScale(37.0))

        assert host.draft.leds.lightbar_brightness == 37, "o brilho global mudou"
        assert host.draft.effective_leds_for(UNIQ_1).lightbar_rgb == AZUL
        assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == VERMELHO
        # E o brilho novo vale para os dois — é o que "Todos" quer dizer.
        assert host.draft.effective_leds_for(UNIQ_1).lightbar_brightness == 37
        assert host.draft.effective_leds_for(UNIQ_2).lightbar_brightness == 37

    def test_o_arraste_inteiro_e_idempotente(self) -> None:
        """O evento dispara a CADA movimento — bastava encostar no controle."""
        host = _AbaLightbar(_draft_com_duas_cores_proprias(), None)

        for pct in (95.0, 80.0, 61.0, 44.0, 30.0):
            host.on_lightbar_brightness_changed(_FakeScale(pct))

        assert host.draft.leds.lightbar_brightness == 30
        assert host.draft.effective_leds_for(UNIQ_1).lightbar_rgb == AZUL
        assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == VERMELHO

    def test_o_brilho_editado_em_todos_vence_o_brilho_proprio(self) -> None:
        """A limpeza continua existindo — do campo EDITADO, e só dele.

        Uma edição em "Todos" vale para todo mundo: quem tinha brilho próprio
        passa a herdar o global. Sem esta parte, "abaixei o brilho de todos" e
        um controle continuaria estourado na próxima ativação.
        """
        draft = _draft_com_duas_cores_proprias()
        base = draft.effective_leds_for(UNIQ_1)
        draft = draft.with_controller_leds(
            UNIQ_1, base.model_copy(update={"lightbar_brightness": 20})
        )
        assert draft.effective_leds_for(UNIQ_1).lightbar_brightness == 20

        host = _AbaLightbar(draft, None)
        host.on_lightbar_brightness_changed(_FakeScale(70.0))

        assert host.draft.effective_leds_for(UNIQ_1).lightbar_brightness == 70
        assert host.draft.effective_leds_for(UNIQ_1).lightbar_rgb == AZUL

    def test_mudar_a_cor_em_todos_preserva_o_brilho_proprio(self) -> None:
        """A recíproca: cor editada em "Todos" não apaga o brilho de ninguém.

        Sem controles conectados conhecidos o fluxo cai no caminho degradado do
        D4 (a cor única só aparece desligando a paleta) — o que importa aqui é
        que o brilho próprio do Controle 1 continua de pé.
        """
        draft = _draft_com_duas_cores_proprias()
        base = draft.effective_leds_for(UNIQ_1)
        draft = draft.with_controller_leds(
            UNIQ_1, base.model_copy(update={"lightbar_brightness": 20})
        )

        host = _AbaLightbar(draft, None)
        host.on_lightbar_color_set(_FakeColorButton((0, 255, 0)))

        assert host.draft.leds.lightbar_rgb == (0, 255, 0)
        assert host.draft.effective_leds_for(UNIQ_1).lightbar_brightness == 20


# ---------------------------------------------------------------------------
# ABAS-04 — "Parar" não pegava, e a vibração voltava sozinha
# ---------------------------------------------------------------------------


class _AbaRumble(ra.RumbleActionsMixin):
    """Só a aba Rumble, com os dois deslizantes e o rascunho compartilhado."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._rumble_guard_refresh = False
        self._rumble_policy = "balanceado"
        self._rumble_test_source: int | None = None
        self._widgets: dict[str, Any] = {
            "rumble_weak_scale": _FakeScale(0.0),
            "rumble_strong_scale": _FakeScale(0.0),
        }
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)


def _aba_rumble(
    monkeypatch: pytest.MonkeyPatch, draft: DraftConfig | None = None
) -> _AbaRumble:
    monkeypatch.setattr(ra, "rumble_set", lambda *_a, **_kw: True)
    monkeypatch.setattr(ra, "rumble_stop", lambda *_a, **_kw: True)
    monkeypatch.setattr(ra, "rumble_passthrough", lambda *_a, **_kw: True)
    monkeypatch.setattr(ra, "call_async", lambda *_a, **_kw: None)
    return _AbaRumble(draft if draft is not None else DraftConfig.default())


class TestABAS04PararPega:
    def test_parar_zera_o_rascunho_e_o_proximo_aplicar_nao_re_trava(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Aplicar" trava a vibração; "Parar" tinha de soltá-la do rascunho.

        ``to_ipc_dict`` emite a seção ``rumble`` SEMPRE, então o próximo
        "Aplicar" de qualquer aba — mexer no brilho já basta — reenviava os
        valores travados que ela acabara de mandar parar.
        """
        aba = _aba_rumble(monkeypatch)
        aba._set_scales(200, 180)
        aba.on_rumble_apply(None)
        assert aba.draft.rumble.weak == 200

        aba.on_rumble_stop(None)

        assert (aba.draft.rumble.weak, aba.draft.rumble.strong) == (0, 0)
        assert aba.draft.to_ipc_dict()["rumble"] == {"weak": 0, "strong": 0}, (
            "o 'Aplicar' de qualquer aba re-travava a vibração parada"
        )

    def test_voltar_a_aba_nao_repinta_os_valores_travados(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A aba MENTIA sobre o estado parado.

        ``_refresh_rumble_from_draft`` roda ao exibir a aba e repinta os
        deslizantes a partir do rascunho — que seguia com os valores antigos.
        """
        aba = _aba_rumble(monkeypatch)
        aba._set_scales(200, 180)
        aba.on_rumble_apply(None)
        aba.on_rumble_stop(None)

        aba._refresh_rumble_from_draft()

        assert aba._read_scales() == (0, 0), (
            "voltar à aba Rumble ressuscitava os valores que ela parou"
        )

    def test_devolver_ao_jogo_tambem_zera_o_rascunho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _aba_rumble(monkeypatch)
        aba._set_scales(160, 220)
        aba.on_rumble_apply(None)

        aba.on_rumble_passthrough(None)

        assert (aba.draft.rumble.weak, aba.draft.rumble.strong) == (0, 0)
        aba._refresh_rumble_from_draft()
        assert aba._read_scales() == (0, 0)

    def test_o_fim_do_teste_de_motores_tambem_zera(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O "Testar motores" termina em passthrough — o rascunho segue junto.

        Sem isto, os valores do teste ficavam no rascunho e o próximo "Aplicar"
        de qualquer aba os reenviava como se fossem escolha dela.
        """
        perfil = _perfil("vitoria", rumble=RumbleConfig(passthrough=False))
        aba = _aba_rumble(monkeypatch, DraftConfig.from_profile(perfil))
        aba._set_scales(200, 180)
        aba.on_rumble_apply(None)  # trava a vibração: rascunho em 200/180
        aba.on_rumble_test_500ms(None)
        assert (aba.draft.rumble.weak, aba.draft.rumble.strong) == (200, 180)

        aba._rumble_test_stop()  # o timer de meio segundo dispara

        assert (aba.draft.rumble.weak, aba.draft.rumble.strong) == (0, 0)
        assert aba.draft.rumble.passthrough is True


class TestABAS04PassthroughEhEscrito:
    def test_o_botao_grava_o_campo_que_ninguem_editava(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``RumbleDraft.passthrough`` existe desde a v1 e NENHUMA superfície o
        escrevia, apesar de o botão estar na tela.

        Num perfil que trazia ``passthrough: false``, o clique em "Deixar o jogo
        controlar a vibração" não sobrevivia ao "Salvar Perfil": a ativação
        seguinte re-travava a vibração.
        """
        perfil = _perfil("vitoria", rumble=RumbleConfig(passthrough=False))
        aba = _aba_rumble(monkeypatch, DraftConfig.from_profile(perfil))
        assert aba.draft.rumble.passthrough is False  # pré-condição

        aba.on_rumble_passthrough(None)

        assert aba.draft.rumble.passthrough is True
        assert aba.draft.to_profile("vitoria").rumble.passthrough is True

    def test_travar_a_vibracao_nao_mexe_no_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regra deliberada, e é o oposto do que parece intuitivo.

        ``passthrough=True`` no perfil é o que SOLTA um rumble fixado em valor
        não-zero na ativação — a cura do "testei os motores e o jogo não vibra
        mais" (SPRINT-GAME-RUMBLE-01) e a rede de segurança do RUMBLE-PRESO-01.
        Gravar ``False`` a partir do "Aplicar"/"Parar" congelaria a trava no
        JSON e ressuscitaria as duas queixas; o silêncio deliberado do "Parar"
        já sobrevive à ativação por conta própria (o applier preserva ``(0,0)``).
        Escrever ``True`` também seria mentira — travar não é devolver ao jogo.
        Logo: os dois botões NÃO TOCAM o campo, nas duas direções.

        Guarda de não-ação: pinado nos dois sentidos justamente porque nenhuma
        asserção sobre o valor final o pegaria sozinha.
        """
        for inicial in (True, False):
            perfil = _perfil("vitoria", rumble=RumbleConfig(passthrough=inicial))
            aba = _aba_rumble(monkeypatch, DraftConfig.from_profile(perfil))
            aba._set_scales(200, 180)

            aba.on_rumble_apply(None)
            assert aba.draft.rumble.passthrough is inicial
            aba.on_rumble_stop(None)
            assert aba.draft.rumble.passthrough is inicial
