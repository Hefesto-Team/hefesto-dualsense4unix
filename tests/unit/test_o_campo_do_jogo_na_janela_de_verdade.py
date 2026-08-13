"""JOGO-QUE-SE-DIZ-01 — a fiação do campo do jogo, com GTK e glade de verdade.

Os dois arquivos irmãos provam as decisões PURAS (o extrator de appid e o
catálogo de jogos). O que este prova é o que nenhum dublê prova: que o
``GtkEntry`` do glade, com uma ``Gtk.EntryCompletion`` de verdade, faz o que
ela pediu —

* colar o endereço da loja no campo **deixa o campo com o número**;
* escolher um jogo na lista suspensa **grava o appid, não o rótulo lido** (o
  comportamento de fábrica do GTK escreveria "Café Cósmico (appid 2111190)" no
  campo, e o perfil nasceria com um ``steam_app_Café`` que nunca casa);
* o número deixa de ser mudo: o nome do jogo aparece ao lado.

A biblioteca é a de MENTIRA dos irmãos — `catalogo_de_jogos` é substituído, e a
biblioteca dela nunca é lida aqui.

Armadilha medida (`docs/process/COMO-OLHAR-A-TELA.md`): sob Xvfb não há
gerenciador de janelas, e uma `Gtk.Window` fica 1x1 para sempre. Daí a
`Gtk.OffscreenWindow`, e daí o laço drenado antes de medir.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub
# (`Gtk.EntryCompletion = object`) este arquivo passaria sem provar nada.
exigir_gi_real("jogo que se diz 01 (campo do jogo)")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.app.widgets import SegmentedSelector
from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: A biblioteca de mentira desta casa. Nomes inventados de propósito.
CATALOGO_FALSO = [
    JogoLocal(appid="851100", nome="Mar de Estrelas", fonte="steam"),
    JogoLocal(appid="2111190", nome="Café Cósmico", fonte="steam"),
    JogoLocal(appid="1599660", nome="Saco de Aventura™: O Retorno", fonte="desktop"),
]

ENDERECO_DA_LOJA = "https://store.steampowered.com/app/851100/Sea_of_Stars/"

_janelas_vivas: list[Any] = []


def _assentar(vezes: int = 8) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


class _JanelaDeVerdade:
    """O `main.glade` real numa `Gtk.OffscreenWindow`, como na abertura."""

    def __init__(self) -> None:
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
        _assentar()

    def obj(self, nome: str) -> Any:
        return self.builder.get_object(nome)


class _EditorDeVerdade(ProfilesActionsMixin):  # type: ignore[misc]
    """O mixin REAL sobre os widgets REAIS, com o "Aplica a" de verdade."""

    def __init__(self, janela: _JanelaDeVerdade) -> None:
        self.builder = janela.builder
        self._profiles_cache: list[Any] = []
        self._duplicate_source = None
        self._mode_advanced = False
        self._new_profile = False
        self._regra_tocada = False
        self._suppress_steam_input_toggle = False
        self.toasts: list[str] = []
        self._aplica_a = SegmentedSelector(wrap=True)
        self._aplica_a.set_items(pa._APLICA_A_ITEMS)
        self._aplica_a.connect("changed", self._on_aplica_a_changed)
        self._aplica_a.set_active_id("any")
        _assentar()

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)

    # O prefill fala com o daemon; aqui ele é silêncio (o daemon dela está
    # vivo, e um teste não conversa com ele).
    def _prefill_steam_appid(self) -> None:
        return None

    def _appids_do_steam_input(self) -> set[str]:
        return set()

    def escolher(self, id_do_botao: str) -> None:
        self._aplica_a.set_active_id(id_do_botao)
        _assentar()


@pytest.fixture
def editor(monkeypatch: pytest.MonkeyPatch) -> _EditorDeVerdade:
    """Editor real, com a lista já cheia da biblioteca de MENTIRA.

    `run_in_thread` vira síncrono para o teste não depender de um laço GLib
    rodando, e `catalogo_de_jogos` vira a lista fixa — a biblioteca dela não é
    lida aqui, nem por acidente.
    """
    monkeypatch.setattr(pa, "catalogo_de_jogos", lambda: list(CATALOGO_FALSO))

    def _sincrono(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        on_success(fn())

    monkeypatch.setattr(pa, "run_in_thread", _sincrono)
    ed = _EditorDeVerdade(_JanelaDeVerdade())
    ed._instalar_lista_de_jogos_do_pc()
    campo = ed._get("profile_simple_custom_name")
    campo.connect("changed", ed._on_campo_do_jogo_mudou)
    ed.escolher("steam_game")
    _assentar()
    return ed


class TestColarOEnderecoDaLoja:
    def test_o_campo_fica_com_o_numero(self, editor: _EditorDeVerdade) -> None:
        """O gesto dela: colar o endereço no campo."""
        campo = editor._get("profile_simple_custom_name")
        campo.set_text(ENDERECO_DA_LOJA)
        _assentar()
        assert campo.get_text() == "851100"

    def test_o_numero_deixa_de_ser_mudo(self, editor: _EditorDeVerdade) -> None:
        campo = editor._get("profile_simple_custom_name")
        campo.set_text(ENDERECO_DA_LOJA)
        _assentar()
        rotulo = editor._get("profile_jogo_reconhecido")
        assert rotulo.get_visible()
        assert "Mar de Estrelas" in rotulo.get_text()

    def test_o_numero_cru_continua_valendo(self, editor: _EditorDeVerdade) -> None:
        campo = editor._get("profile_simple_custom_name")
        campo.set_text("2111190")
        _assentar()
        assert campo.get_text() == "2111190", "o campo não pode mexer no que já é appid"
        assert "Café Cósmico" in editor._get("profile_jogo_reconhecido").get_text()

    def test_endereco_de_outra_loja_nao_vira_numero_e_diz_isso(
        self, editor: _EditorDeVerdade
    ) -> None:
        campo = editor._get("profile_simple_custom_name")
        campo.set_text("https://www.gog.com/game/sea_of_stars")
        _assentar()
        assert campo.get_text() == "https://www.gog.com/game/sea_of_stars"
        rotulo = editor._get("profile_jogo_reconhecido")
        assert rotulo.get_visible()
        assert "Não reconheci" in rotulo.get_text()

    def test_o_perfil_salvo_leva_a_regra_do_jogo(self, editor: _EditorDeVerdade) -> None:
        """O que importa no fim: o endereço colado vira a regra certa no disco.

        `_regra_real_do_perfil_aberto` é a MESMA conta do Salvar (é o que o
        próprio docstring dele promete), então afirmar sobre ela é afirmar
        sobre o arquivo que nasceria.
        """
        editor._regra_do_disco = None
        editor._assinatura_da_regra_ao_abrir = None
        editor._get("profile_simple_custom_name").set_text(ENDERECO_DA_LOJA)
        _assentar()
        regra = editor._regra_real_do_perfil_aberto()
        assert getattr(regra, "window_class", None) == ["steam_app_851100"]


class TestAListaDosJogosDaCasa:
    def test_a_lista_tem_os_jogos_desta_maquina(self, editor: _EditorDeVerdade) -> None:
        """A MORDIDA: sem `_guardar_jogos_do_pc`, este modelo vem VAZIO."""
        modelo = editor._jogos_store
        rotulos = [linha[0] for linha in modelo]
        assert rotulos, "a lista de jogos veio vazia — nada a sugerir para ela"
        assert "Mar de Estrelas (appid 851100)" in rotulos

    def test_a_completacao_esta_ligada_no_campo(self, editor: _EditorDeVerdade) -> None:
        campo = editor._get("profile_simple_custom_name")
        assert campo.get_completion() is not None

    def test_digitar_o_nome_filtra_a_lista(self, editor: _EditorDeVerdade) -> None:
        """"cafe" tem de achar "Café Cósmico" — ela digita sem acento."""
        completacao = editor._get("profile_simple_custom_name").get_completion()
        modelo = completacao.get_model()
        casaram = [
            linha[1]
            for linha in modelo
            if editor._jogo_casa_com_o_texto(completacao, "cafe", linha.iter)
        ]
        assert casaram == ["2111190"]

    def test_escolher_na_lista_grava_o_appid_e_nao_o_rotulo(
        self, editor: _EditorDeVerdade
    ) -> None:
        """O comportamento de fábrica do GTK escreveria o rótulo no campo."""
        completacao = editor._get("profile_simple_custom_name").get_completion()
        modelo = completacao.get_model()
        alvo = next(linha.iter for linha in modelo if linha[1] == "1599660")
        parou = editor._on_jogo_escolhido_na_lista(completacao, modelo, alvo)
        _assentar()
        assert parou is True, "sem True o GTK escreve o rótulo por cima"
        campo = editor._get("profile_simple_custom_name")
        assert campo.get_text() == "1599660"
        assert "Saco de Aventura" in editor._get("profile_jogo_reconhecido").get_text()

    def test_sem_biblioteca_o_campo_continua_aceitando_o_numero(
        self, editor: _EditorDeVerdade
    ) -> None:
        """Máquina sem Steam: lista vazia, campo inteiro. Degradar em silêncio."""
        editor._guardar_jogos_do_pc([])
        _assentar()
        campo = editor._get("profile_simple_custom_name")
        campo.set_text("851100")
        _assentar()
        assert campo.get_text() == "851100"
        assert len(list(editor._jogos_store)) == 0


class TestOOutroSignificadoDoCampo:
    """O rótulo "Nome do jogo:" serve DUAS escolhas — a frase segue a escolha."""

    def test_em_jogo_especifico_o_nome_do_jogo_da_steam_some(
        self, editor: _EditorDeVerdade
    ) -> None:
        editor._get("profile_simple_custom_name").set_text("851100")
        _assentar()
        assert editor._get("profile_jogo_reconhecido").get_visible()
        editor.escolher("game")
        _assentar()
        rotulo = editor._get("profile_jogo_reconhecido")
        assert not rotulo.get_visible(), (
            "em 'Jogo específico' o campo guarda o nome do PROGRAMA; um nome de "
            "jogo da Steam ali seria a tela afirmando outra regra"
        )
