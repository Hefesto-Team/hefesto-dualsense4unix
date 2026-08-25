"""P10 — quatro caminhos desta aba não tinham UMA mordida.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/10 (24/08/2026), medido assim:

    $ for f in on_profile_remove on_profile_duplicate _ao_tirar_outro_marcado \\
               _refazer_as_abas_apos_ativar; do
        echo "$f -> $(grep -rl "$f" tests/ | wc -l)"; done
    on_profile_remove            -> 0
    on_profile_duplicate         -> 0
    _ao_tirar_outro_marcado      -> 0
    _refazer_as_abas_apos_ativar -> 0

Zero cada um. **Remover** apaga arquivo dela. **Duplicar** já foi quebrado uma
vez pela MASCARA-QUE-GRUDA-01. O **"Tirar"** escreve na allowlist da Steam. E o
**refazer das seis abas** é o mais caro dos quatro: é ele que reconstrói
Lightbar, Gatilhos, Rumble, Navegação, Início e Emulação a cada ativação, e é
o motivo de esta onda vir DEPOIS das quatro que decidem contrato.

Cada teste daqui morde uma invariante que hoje só existe em COMENTÁRIO. A
docstring de cada um diz qual linha do produto arrancar para vê-lo reprovar.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _instalar_gi_falso() -> None:
    """GTK de mentira: a suíte não pode criar janela nem nó de uinput."""
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


_instalar_gi_falso()

from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)

#: O perfil-fonte do "Duplicar": tem cor e tem regra, e as duas TÊM de viajar.
#: A MASCARA-QUE-GRUDA-01 já quebrou este caminho uma vez.
SACKBOY = Profile(
    name="Sackboy",
    match=MatchCriteria(window_class=["steam_app_1599660"]),
    priority=80,
    leds=LedsConfig(lightbar=(0, 255, 0)),
)


class _Entry:
    def __init__(self, texto: str = "") -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, texto: str) -> None:
        self._t = texto


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    """A aba, com o disco e os diálogos na mão do teste."""

    def __init__(self, selecionado: str | None = "Sackboy") -> None:
        self._profiles_cache: list[Profile] = [SACKBOY]
        self._selecionado = selecionado
        self._duplicate_source: Profile | None = None
        self._new_profile = False
        self._alvo_do_salvar: str | None = "Sackboy"
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _Entry("Sackboy"),
            "main_window": object(),
        }
        self.toasts: list[str] = []
        self.recarregou: list[Any] = []
        self.abas_refeitas = 0
        self.avisou_launch_env = 0

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_profile_name(self, _selection: Any = None) -> str | None:
        return self._selecionado

    def _reload_profiles_store(self, **kw: Any) -> None:
        self.recarregou.append(kw)

    def _notify_launch_env_refresh(self) -> None:
        self.avisou_launch_env += 1

    def _recarregar_as_abas_do_perfil_ativo(self) -> None:
        self.abas_refeitas += 1

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


# ---------------------------------------------------------------------------
# 1. Remover — apaga ARQUIVO dela, e tinha zero teste
# ---------------------------------------------------------------------------


class TestRemover:
    def test_cancelar_nao_toca_o_disco(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MORDE a confirmação (BUG-DELETE-NO-CONFIRM-01).

        Arranque o `if not gui_dialogs.confirm_delete_profile(...)` e o perfil
        dela some com um clique só, sem uma palavra.
        """
        aba = _Aba()
        apagados: list[str] = []
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name: False
        )
        monkeypatch.setattr(pa, "delete_profile", lambda n: apagados.append(n))

        aba.on_profile_remove(None)

        assert apagados == [], "cancelar apagou o arquivo dela"
        assert aba.toasts == ["Remoção cancelada."]

    def test_confirmar_apaga_e_avisa_o_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `launch_env` do perfil apagado tem de sumir junto (DEDUP-04).

        Arranque o `_notify_launch_env_refresh` do fim e o `steam_app_<id>.env`
        do perfil morto fica rançoso no disco — o primeiro lançamento seguinte
        do jogo lê um bilhete de um perfil que não existe mais.
        """
        aba = _Aba()
        apagados: list[str] = []
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name: True
        )
        monkeypatch.setattr(pa, "delete_profile", lambda n: apagados.append(n))

        aba.on_profile_remove(None)

        assert apagados == ["Sackboy"]
        assert aba.toasts == ["Perfil removido: Sackboy"]
        assert aba.avisou_launch_env == 1

    def test_o_alvo_do_salvar_nao_e_zerado_e_isso_e_decisao_medida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NUNCA-TROCA-O-ALVO-01: a decisão foi medida, e este teste a trava.

        Zerar `_alvo_do_salvar` aqui faz o alvo cair no fallback (a linha
        selecionada), que depois da recarga é OUTRO perfil — e um Salvar em
        seguida viraria um RENAME dele, com o diálogo do R-10 se oferecendo
        para apagá-lo. O comentário de `on_profile_remove` explica; nada
        travava. Agora trava.
        """
        aba = _Aba()
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name: True
        )
        monkeypatch.setattr(pa, "delete_profile", lambda _n: None)

        aba.on_profile_remove(None)

        assert aba._alvo_do_salvar == "Sackboy"

    def test_falha_de_disco_vira_frase_e_nao_excecao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nada aqui pode subir exceção pela thread do GTK."""
        aba = _Aba()

        def _explode(_n: str) -> None:
            raise OSError("permissão negada")

        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name: True
        )
        monkeypatch.setattr(pa, "delete_profile", _explode)

        aba.on_profile_remove(None)

        assert aba.toasts[-1].startswith("Falha ao remover:")
        assert aba.recarregou == [], "a lista não recarrega depois de falhar"

    def test_sem_linha_selecionada_nao_apaga_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _Aba(selecionado=None)
        monkeypatch.setattr(
            gui_dialogs,
            "confirm_delete_profile",
            lambda parent, name: pytest.fail("perguntou sem perfil selecionado"),
        )
        aba.on_profile_remove(None)
        assert aba.toasts == ["Selecione um perfil para remover"]


# ---------------------------------------------------------------------------
# 2. Duplicar — as TRÊS invariantes que só existiam em comentário
# ---------------------------------------------------------------------------


class TestDuplicar:
    def test_a_fonte_inteira_viaja_e_nao_so_o_nome(self) -> None:
        """MORDE o BUG-DUPLICATE-NO-CONFIG-COPY-01.

        Arranque o `self._duplicate_source = self._find_cached_profile(name)`
        e a cópia muda só o nome: gatilhos, lightbar, LEDs e o resto viram
        default. É perda da configuração REAL dela, calada.
        """
        aba = _Aba()
        aba.on_profile_duplicate(None)

        assert aba._duplicate_source is SACKBOY, (
            "sem a fonte, `_build_profile_from_editor` não tem de onde copiar"
        )

    def test_duplicar_sai_do_estado_perfil_novo(self) -> None:
        """R-09: duplicar É partir de uma fonte. Arranque e a cópia nasce vazia."""
        aba = _Aba()
        aba._new_profile = True
        aba.on_profile_duplicate(None)
        assert aba._new_profile is False

    def test_o_salvar_deixa_de_mirar_a_fonte_no_mesmo_instante(self) -> None:
        """MORDE a linha mais perigosa das três (NUNCA-TROCA-O-ALVO-01).

        A cópia vai para um arquivo NOVO. Arranque o `_alvo_do_salvar = None`
        e o próximo Salvar grava por cima do perfil-FONTE — que é o perfil
        que ela quis preservar ao clicar em Duplicar.
        """
        aba = _Aba()
        assert aba._alvo_do_salvar == "Sackboy"
        aba.on_profile_duplicate(None)
        assert aba._alvo_do_salvar is None

    def test_o_nome_ganha_o_sufixo_de_copia(self) -> None:
        aba = _Aba()
        aba.on_profile_duplicate(None)
        assert aba._get("profile_name_entry").get_text() == "Sackboy (cópia)"
        assert aba.toasts[-1].startswith("Editor preenchido com cópia completa")

    def test_sem_linha_selecionada_nao_duplica(self) -> None:
        aba = _Aba(selecionado=None)
        aba.on_profile_duplicate(None)
        assert aba._duplicate_source is None
        assert aba.toasts == ["Selecione um perfil para duplicar"]


# ---------------------------------------------------------------------------
# 3. O "Tirar" da lista — escreve na allowlist da Steam
# ---------------------------------------------------------------------------


class TestTirarDaLista:
    def test_passa_pelo_escritor_unico_e_nao_pelo_remove_direto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE o dono único da escrita.

        `_gravar_marca_do_steam_input` é quem dá o toast, avisa o daemon e relê
        o disco. Arranque a delegação (chamando `remove_...` direto daqui) e
        nasce o SEGUNDO escritor da mesma lista — que é metade do defeito que
        a A-LISTA-QUE-FALTAVA-01 fechou.
        """
        aba = _Aba()
        gravados: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_gravar_marca_do_steam_input",
            lambda self, appid, marcar: gravados.append((appid, marcar)),
        )

        aba._ao_tirar_outro_marcado(None, "1599660")

        assert gravados == [("1599660", False)]

    def test_tirar_nao_pergunta_do_relancar_e_a_diferenca_e_medida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pergunta do RELANCAR-01 é para o jogo DESTE editor, não para os outros.

        Ela existe porque marcar/desmarcar o jogo que está ABERTO tira dele o
        dispositivo que ele já enumerou. Estes são os OUTROS jogos. Se alguém
        somar a pergunta aqui, o "Tirar" vira dois cliques para nada.
        """
        aba = _Aba()
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_perguntar_antes_de_relancar",
            lambda self, **kw: pytest.fail("o Tirar perguntou do relançamento"),
        )
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_gravar_marca_do_steam_input",
            lambda self, appid, marcar: None,
        )

        aba._ao_tirar_outro_marcado(None, "1599660")


# ---------------------------------------------------------------------------
# 4. O refazer das SEIS abas — o caminho mais caro dos quatro
# ---------------------------------------------------------------------------


class _AbaComEdicao(_Aba):
    def __init__(self, pendente: bool) -> None:
        super().__init__()
        self._pendente = pendente
        self._active_profile_name = "vitoria"
        self.perguntou: list[tuple[str, str | None]] = []
        self.resposta = False

    def _tem_edicao_pendente(self) -> bool:
        return self._pendente


class TestRefazerAsAbasAposAtivar:
    def _armar(
        self, aba: _AbaComEdicao, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            gui_dialogs,
            "confirm_discard_pending_edits",
            lambda parent, ativado, editando=None: (
                aba.perguntou.append((ativado, editando)) or aba.resposta
            ),
        )

    def test_sem_edicao_pendente_refaz_as_abas_sem_perguntar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _AbaComEdicao(pendente=False)
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == [], "perguntou sem haver o que proteger"
        assert aba.abas_refeitas == 1

    def test_com_edicao_pendente_a_decisao_e_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE o portão da edição pendente.

        Arranque o `if pendente:` e a ativação recarrega o rascunho do disco
        por cima da cor que ela mexeu e não salvou — trocar um jeito de perder
        trabalho por outro, que é o que a R-08 já tinha decidido para o tique.
        """
        aba = _AbaComEdicao(pendente=True)
        aba.resposta = False  # ela recusa: MANTER o que está na tela
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == [("Sackboy", "vitoria")]
        assert aba.abas_refeitas == 0, (
            "a recusa dela tem de deixar as abas exatamente como estavam"
        )
        assert "não salvas" in aba.toasts[-1], (
            "e a tela tem de DIZER que as abas seguem mostrando o rascunho dela"
        )
        assert "vitoria" in aba.toasts[-1], "sem dizer QUAL, é meia informação"

    def test_ela_aceita_descartar_e_as_abas_passam_a_mostrar_o_ativado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _AbaComEdicao(pendente=True)
        aba.resposta = True
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.abas_refeitas == 1

    def test_a_guarda_que_estoura_nao_impede_a_pergunta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_tem_edicao_pendente` que levanta não pode virar "não há edição".

        É a mesma disciplina do "não sei" do P1: uma exceção aqui é ausência
        de RESPOSTA, e o caminho seguro é o que NÃO recarrega calado... só que
        o produto de hoje trata o estouro como "sem edição". Este teste
        registra o comportamento de HOJE — se alguém o mudar, a mudança vem
        com decisão, não por acidente.
        """
        aba = _AbaComEdicao(pendente=False)

        def _explode(self: Any) -> bool:
            raise RuntimeError("rascunho ilegível")

        monkeypatch.setattr(_AbaComEdicao, "_tem_edicao_pendente", _explode)
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == []
        assert aba.abas_refeitas == 1
