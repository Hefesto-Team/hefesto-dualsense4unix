"""A caixinha do Steam Input sumiu do perfil do Pragmata — 10/08/2026.

Relato dela, com o jogo aberto e o controle duplicado na mão:

    *"sumiu a opção de entregar o controle pra Steam? pq ela é que impedia o
    dual input em jogos como pragmata"*
    *"mas sumiu na interface. fui jogar pragmata pra testar o touchpad, o
    giroscópio, e ele tá duplicado"*

A cadeia, medida no perfil REAL dela
(``~/.config/hefesto-dualsense4unix/profiles/pragmata.json``):

    match = window_class ["steam_app_3357650"] + process_name ["PRAGMATA.exe"]
      -> `_detect_steam_appid` recusava por causa do `process_name`
      -> `detect_simple_preset` devolvia None
      -> `_populate_editor` caía no ramo avançado e rebaixava o seletor a "any"
      -> `_mostrar_caixa_do_steam_input(False)`
      -> a caixinha "Esconder o controle físico neste jogo" sumia da tela.

E ela não tinha outro caminho: o appid 3357650 JÁ estava no
``steam_input_apps.txt``, e desmarcar sem a caixinha exige editor de texto.

Por que este arquivo usa **GTK real e o glade real** (mesma razão do
``test_a_caixinha_que_tira_do_steam_input.py``): a caixinha nasce
``no-show-all`` e um dublê com atributo ``.visivel`` nunca pergunta pelos
FILHOS — foi assim que a ``CAMPO-QUE-NAO-NASCIA-01`` passou despercebida. Aqui
o defeito é justamente "não aparece", então medir com dublê seria medir nada.

MORDIDA: com o ``and not match.process_name`` devolvido a
``_detect_steam_appid``, os testes de reconhecimento e de tela reprovam; com
``_process_name_a_preservar`` devolvendo ``[]``, os de round-trip reprovam.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub
# (`Gtk.Box = object`) a metade de tela deste arquivo passaria sem mostrar
# nada a ninguém.
exigir_gi_real("a caixinha que sumiu do perfil do Pragmata")

import json
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    detect_simple_preset,
    from_simple_choice,
    simple_extra,
)

#: O jogo dela, e o match EXATO do disco em 10/08/2026.
APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"
EXE_DO_JOGO = "PRAGMATA.exe"

#: Um segundo jogo (Sackboy), para provar que trocar o número troca de jogo.
OUTRO_APPID = "1599660"

CABECALHO = (
    "# hefesto-dualsense4unix — allowlist do Steam Input per-app\n"
    "# (STEAM-INPUT-ALLOWLIST-01)\n"
    "#\n"
    "# Uma linha por AppID; '#' comenta.\n"
)


def _match_dela() -> MatchCriteria:
    """O match como está no disco dela — os dois campos, na mesma ordem."""
    return MatchCriteria(window_class=[WM_JOGO], process_name=[EXE_DO_JOGO])


def _perfil_dela() -> Profile:
    return Profile(name="Pragmata", match=_match_dela(), priority=85)


# ---------------------------------------------------------------------------
# 1. O reconhecimento — funções puras, sem GTK
# ---------------------------------------------------------------------------


class TestOPerfilDelaVoltaAoEditorSimples:
    def test_o_match_real_dela_e_um_jogo_da_steam(self) -> None:
        """O que estava devolvendo None, e por isso escondia a caixinha."""
        assert detect_simple_preset(_match_dela()) == "steam_game", (
            "o perfil do jogo dela abria no editor AVANÇADO, e com ele o "
            "seletor rebaixado a 'Vale sempre' — que é onde a caixinha morre"
        )
        assert simple_extra(_match_dela()) == APPID, (
            "sem o número no campo, a caixinha não sabe de qual jogo fala "
            "(`_appid_do_editor` devolve None) e nasce insensível"
        )

    def test_regex_de_titulo_junto_continua_fora_do_editor_simples(self) -> None:
        """A metade da decisão de 23/07 que NÃO caducou.

        Um regex de título ESTREITA o perfil para um subconjunto das janelas do
        jogo — uma tela, um mapa, um título traduzido. O editor simples não tem
        como exprimir esse recorte, e chamar isso de "Jogo da Steam <id>" seria
        mentir sobre o que o perfil faz. Continua indo para o avançado.
        """
        m = MatchCriteria(window_class=[WM_JOGO], window_title_regex="PRAGMATA")
        assert detect_simple_preset(m) is None
        assert simple_extra(m) == ""

    def test_regex_e_processo_juntos_tambem_ficam_no_avancado(self) -> None:
        """A recusa é do regex, e não some porque há um `process_name` junto."""
        m = MatchCriteria(
            window_class=[WM_JOGO],
            window_title_regex="PRAGMATA",
            process_name=[EXE_DO_JOGO],
        )
        assert detect_simple_preset(m) is None

    def test_duas_janelas_continuam_sendo_regra_complexa(self) -> None:
        """`window_class` com dois nomes não é "um jogo da Steam" — nunca foi."""
        m = MatchCriteria(
            window_class=[WM_JOGO, f"steam_app_{OUTRO_APPID}"],
            process_name=[EXE_DO_JOGO],
        )
        assert detect_simple_preset(m) is None


# ---------------------------------------------------------------------------
# 2. O round-trip — reconhecer não pode virar apagar (a lição do R-12)
# ---------------------------------------------------------------------------


class TestOProcessNameSobreviveAoRoundTrip:
    def test_o_programa_do_jogo_nao_evapora_ao_salvar(self, tmp_path: Path) -> None:
        """Abrir no simples e salvar não pode tirar o campo que a tela não mostra.

        A página simples tem UM campo (o número). Sem preservação, o
        `PRAGMATA.exe` sumiria do arquivo dela sem que ela tivesse tocado nele —
        que é o defeito de round-trip de onde o R-12 nasceu, de novo.
        """
        disco = _match_dela()
        novo = from_simple_choice("steam_game", custom_name=APPID, regra_do_disco=disco)

        # o ciclo do disco, como o loader faz
        caminho = tmp_path / "pragmata.json"
        perfil = Profile(name="Pragmata", match=novo, priority=85)
        caminho.write_text(
            json.dumps(perfil.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        relido = Profile.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

        assert isinstance(relido.match, MatchCriteria)
        assert relido.match.window_class == [WM_JOGO]
        assert relido.match.process_name == [EXE_DO_JOGO], (
            "o editor simples apagou um campo da regra dela sem ela pedir"
        )
        assert detect_simple_preset(relido.match) == "steam_game", (
            "o segundo round-trip tem de fechar igual ao primeiro"
        )

    def test_trocar_o_numero_troca_de_jogo_e_nao_herda_o_programa(self) -> None:
        """Outro appid é OUTRO jogo — herdar o `PRAGMATA.exe` seria pior que apagar.

        O perfil novo nasceria com um AND que nunca casa, e nada na tela diria
        por quê.
        """
        novo = from_simple_choice(
            "steam_game", custom_name=OUTRO_APPID, regra_do_disco=_match_dela()
        )
        assert isinstance(novo, MatchCriteria)
        assert novo.window_class == [f"steam_app_{OUTRO_APPID}"]
        assert novo.process_name == []

    def test_regra_do_disco_que_nao_e_jogo_nao_empresta_nada(self) -> None:
        for regra in (MatchAny(), MatchCriteria(process_name=["steam"]), None):
            novo = from_simple_choice("steam_game", custom_name=APPID, regra_do_disco=regra)
            assert isinstance(novo, MatchCriteria)
            assert novo.process_name == [], f"regra {regra!r} não devia emprestar nada"

    def test_sem_regra_do_disco_o_contrato_historico_nao_muda(self) -> None:
        """Chamador antigo (CLI, testes, duplicação) segue gravando só a janela."""
        novo = from_simple_choice("steam_game", custom_name=APPID)
        assert isinstance(novo, MatchCriteria)
        assert novo.window_class == [WM_JOGO]
        assert novo.process_name == []


# ---------------------------------------------------------------------------
# 3. A TELA — GTK real, glade real, `install_profiles_tab` real
# ---------------------------------------------------------------------------


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


sem_gtk = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: Janelas vivas até o fim do módulo: uma `OffscreenWindow` coletada no meio do
#: teste leva os widgets junto, e a medição vira sorte.
_janelas_vivas: list[Any] = []


def _assentar(vezes: int = 8) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


class _Editor(ProfilesActionsMixin):  # type: ignore[misc]
    """O mixin REAL sobre o glade REAL, montado como a janela monta."""

    def __init__(self, cache: list[Profile] | None = None) -> None:
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(MAIN_GLADE))
        raiz = self.builder.get_object("root_box")
        pai = raiz.get_parent()
        if pai is not None:
            pai.remove(raiz)
        self.janela = Gtk.OffscreenWindow()
        self.janela.add(raiz)
        self.janela.set_size_request(1180, 800)
        self.janela.show_all()
        _janelas_vivas.append(self.janela)

        self.toasts: list[str] = []
        self.avisos_ao_daemon = 0
        self._profiles_cache: list[Profile] = list(cache or [])
        self._duplicate_source = None
        self._new_profile = False
        self._regra_tocada = False
        self.selecionado: str | None = None
        self.install_profiles_tab()
        _assentar()

    # --- o que não pode sair da máquina no teste ---
    def _reload_profiles_store(self, select_name: Any = None, on_done: Any = None) -> None:
        return None

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    def _avisar_o_daemon_da_allowlist(self) -> None:
        self.avisos_ao_daemon += 1

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self.selecionado

    def _refresh_preview(self) -> None:
        return None

    # --- os gestos dela ---
    def abrir(self, profile: Profile) -> None:
        self._populate_editor(profile)
        _assentar()

    def escolher(self, id_do_botao: str) -> None:
        self._aplica_a.set_active_id(id_do_botao)
        _assentar()

    def campo_do_jogo(self) -> Any:
        return self.builder.get_object("profile_simple_custom_name")

    def caixa(self) -> Any:
        return self.builder.get_object("profile_steam_input_box")

    def check(self) -> Any:
        return self.builder.get_object("profile_steam_input_check")


@pytest.fixture
def allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME hermético com a allowlist dela — nunca a configuração de verdade.

    O appid do Pragmata JÁ está marcado, como estava no disco dela: é essa
    marca que ela precisava enxergar para poder DESmarcar.
    """
    config = tmp_path / "config"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    arquivo = config / "hefesto-dualsense4unix" / "steam_input_apps.txt"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(f"{CABECALHO}{APPID}\n", encoding="utf-8")
    return arquivo


@pytest.fixture
def sem_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silencia o `call_async` do prefill de appid (best-effort, assíncrono)."""
    monkeypatch.setattr(pa, "call_async", lambda **_kw: None)


@sem_gtk
class TestACaixinhaVoltaParaATela:
    def test_abrir_o_perfil_dela_mostra_a_caixinha_inteira(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        """O sintoma dela, do jeito que ela o vê: clicar no perfil e ter o gesto.

        Não basta a CAIXA aparecer — a lição da `CAMPO-QUE-NAO-NASCIA-01` é que
        um `show()` seco revela a caixa e deixa os filhos escondidos, e ela vê
        um vão vazio. Por isso a asserção é sobre o CHECK.
        """
        editor = _Editor(cache=[_perfil_dela()])
        editor.abrir(_perfil_dela())

        assert editor._aplica_a.get_active_id() == "steam_game", (
            "o perfil do jogo dela abria como 'Vale sempre'"
        )
        assert editor.campo_do_jogo().get_text() == APPID
        assert editor.caixa().get_visible() is True, (
            "a caixinha 'Esconder o controle físico neste jogo' continua sumida"
        )
        assert editor.check().get_visible() is True, (
            "a caixa apareceu sem o filho — é o vão vazio da CAMPO-QUE-NAO-NASCIA-01"
        )

    def test_a_caixinha_abre_ja_marcada_porque_o_jogo_esta_na_lista(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        """Ela precisa DESMARCAR: a caixa tem de chegar dizendo a verdade do disco."""
        editor = _Editor(cache=[_perfil_dela()])
        editor.abrir(_perfil_dela())

        assert editor.check().get_active() is True
        assert editor.check().get_sensitive() is True
        # abrir o perfil não pode reescrever a allowlist dela
        assert allowlist.read_text(encoding="utf-8").count(APPID) == 1
        assert editor.avisos_ao_daemon == 0

    def test_o_editor_abre_na_pagina_simples(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        editor = _Editor(cache=[_perfil_dela()])
        editor.abrir(_perfil_dela())

        stack = editor.builder.get_object("profile_editor_stack")
        assert stack.get_visible_child_name() == "simples"
        assert editor.builder.get_object("profile_advanced_switch").get_active() is False

    def test_com_regex_de_titulo_a_caixinha_continua_escondida(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        """A decisão que FICA, medida na tela e não só na função."""
        complexo = Profile(
            name="Pragmata menu",
            match=MatchCriteria(window_class=[WM_JOGO], window_title_regex="PRAGMATA"),
            priority=85,
        )
        editor = _Editor(cache=[complexo])
        editor.abrir(complexo)

        stack = editor.builder.get_object("profile_editor_stack")
        assert stack.get_visible_child_name() == "avancado"
        assert editor.caixa().get_visible() is False


@sem_gtk
class TestOSalvarPelaJanelaNaoApagaOPrograma:
    def test_mexer_no_seletor_e_salvar_preserva_o_process_name(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        """O round-trip pela JANELA, com a guarda SALVAR-NAO-REBAIXA fora do caminho.

        Quando ela não toca na regra, quem preserva tudo é a guarda de 05/08
        (`regra_final = regra_do_disco`). O caso perigoso é o outro: ela MEXE no
        seletor — e aí o que vale é o que o editor simples monta, que é onde o
        `process_name` evaporaria por falta de campo na tela.
        """
        editor = _Editor(cache=[_perfil_dela()])
        editor.abrir(_perfil_dela())

        # o gesto dela: sair do jogo da Steam e voltar
        editor.escolher("any")
        editor.escolher("steam_game")
        assert editor._regra_foi_mexida() is True, (
            "sem gesto registrado a guarda preservaria tudo e o teste não "
            "mediria a preservação nova"
        )

        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == [WM_JOGO]
        assert salvo.match.process_name == [EXE_DO_JOGO], (
            "salvar pela janela apagou o PRAGMATA.exe da regra dela"
        )

    def test_apagar_o_programa_no_avancado_continua_sendo_gesto_dela(
        self, allowlist: Path, sem_daemon: None
    ) -> None:
        """A preservação vale para o campo INVISÍVEL, nunca por cima do visível.

        No editor avançado o `process_name` está na tela. Apagá-lo ali é uma
        decisão dela, e devolver o valor do disco desfaria a exclusão que ela
        acabou de fazer.
        """
        editor = _Editor(cache=[_perfil_dela()])
        editor.abrir(_perfil_dela())
        editor.escolher("any")  # sai do simples sem mexer nos campos crus

        editor.builder.get_object("profile_advanced_switch").set_active(True)
        editor._mode_advanced = True
        editor.builder.get_object("profile_window_class_entry").set_text(WM_JOGO)
        editor.builder.get_object("profile_process_name_entry").set_text("")
        _assentar()

        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == [WM_JOGO]
        assert salvo.match.process_name == []
