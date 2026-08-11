"""ABA-DO-JOGO-01 — a aba "No jogo" entrando e saindo da tira, com GTK de verdade.

A bancada irmã (`test_aba_no_jogo_so_com_jogo_aberto`) trava o FATO: o daemon
sonda, o `state_full` leva, a `jogo_steam_aberto` lê. Aqui se cobra o que ela vê:
a aba na tira, ou fora dela.

O notebook é REAL de propósito, e é a única forma de este arquivo valer alguma
coisa. Três comportamentos do GTK3 decidem esta cura, e nenhum deles pode ser
dublado sem virar ficção:

1. o `GtkNotebook` esconde a ABA de uma página escondida (é assim que a aba sai
   da tira sem ninguém remover página nenhuma);
2. `_wrap_notebook_pages_in_scroll` (em `app.py`) embrulha a página num
   `GtkScrolledWindow` — quem tem de ser escondido é o EMBRULHO, e esconder a
   caixa de dentro deixaria uma aba clicável abrindo uma página em branco;
3. esconder a página CORRENTE faz o notebook cair sozinho na página SEGUINTE.
   Medido aqui: com o layout de hoje ela estaria lendo o que atravessa para o
   jogo e acordaria em "Gatilhos". É por isso que o foco é levado para a Status
   ANTES de a página sumir.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("aba No jogo entrando e saindo da tira")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta — `gi` existe sem as
# typelibs no runner do CI, e o ImportError na COLETA derruba a suíte inteira.
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.status_actions import (
    ABA_NO_JOGO,
    ABA_STATUS,
    StatusActionsMixin,
)

PRAGMATA = 3357650

#: As abas na ordem do glade, até a primeira depois da "No jogo" — é a vizinha
#: de baixo que o GTK escolhe sozinho quando a página corrente some, e ter uma
#: aba DEPOIS é o que torna o teste do foco capaz de reprovar.
_ABAS = ("tab_home_box", ABA_STATUS, ABA_NO_JOGO, "tab_triggers_box")


def _estado(*, lido: bool, appid: int | None) -> dict[str, Any]:
    """Um `state_full` mínimo — só o que a visibilidade da aba consulta."""
    return {
        "connected": True,
        "controllers": [],
        "jogo_steam": {"lido": lido, "appid": appid},
    }


class _JanelaFalsa(StatusActionsMixin):  # type: ignore[misc]
    """Host mínimo com os métodos de PRODUÇÃO, no molde do `retratar_abas.py`.

    O notebook reproduz o da janela real em tudo o que importa aqui: as páginas
    embrulhadas em `GtkScrolledWindow` (como `_wrap_notebook_pages_in_scroll` as
    deixa) e uma aba depois da "No jogo".
    """

    def __init__(self) -> None:
        self._paginas: dict[str, Gtk.Widget] = {}
        self._notebook = Gtk.Notebook()
        for nome in _ABAS:
            pagina = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            Gtk.Buildable.set_name(pagina, nome)
            self._paginas[nome] = pagina
            scroller = Gtk.ScrolledWindow()
            scroller.add(pagina)
            self._notebook.append_page(scroller, Gtk.Label(label=nome))
        self._notebook.show_all()

    def _get(self, nome: str) -> Any:
        if nome == "main_notebook":
            return self._notebook
        return self._paginas.get(nome)

    # O embrulho da página — o filho DIRETO do notebook, que é quem o GTK
    # consulta para decidir se a aba aparece na tira. Sobe pelo `GtkViewport`
    # que o GTK insere sozinho entre o `GtkScrolledWindow` e a caixa.
    def _embrulho(self, nome: str) -> Gtk.Widget:
        alvo = self._paginas[nome]
        while alvo.get_parent() is not self._notebook:
            alvo = alvo.get_parent()
        return alvo

    def _na_tira(self, nome: str) -> bool:
        return bool(self._embrulho(nome).get_visible())

    def _aba_corrente(self) -> str:
        indice = self._notebook.get_current_page()
        pagina = self._notebook.get_nth_page(indice)
        return str(Gtk.Buildable.get_name(pagina.get_child().get_child()))


@pytest.fixture
def janela() -> _JanelaFalsa:
    app = _JanelaFalsa()
    app.install_no_jogo_tab()
    return app


# ---------------------------------------------------------------------------


def test_a_aba_nasce_fora_da_tira(janela: _JanelaFalsa) -> None:
    """O boot sem jogo aberto não pode mostrar a aba nem por um quadro.

    Arranque para ver reprovar: tirar o `_nascer_aba_no_jogo_escondida()` do
    fim de `install_no_jogo_tab` — é o estado do HEAD antes desta leva, e a
    asserção reprova na primeira linha.
    """
    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_show_all_da_janela_nao_traz_a_aba_de_volta(
    janela: _JanelaFalsa,
) -> None:
    """`app.show()` roda um `window.show_all()` DEPOIS de toda montagem.

    Arranque para ver reprovar: tirar o `set_no_show_all(True)` de
    `_nascer_aba_no_jogo_escondida`. A aba volta para a tira em todo boot.
    """
    janela._notebook.show_all()

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_jogo_abrindo_traz_a_aba(janela: _JanelaFalsa) -> None:
    """O pedido dela, do lado que a faz aparecer.

    Arranque para ver reprovar: fazer `_sync_visibilidade_no_jogo` devolver
    antes do `alvo.show()`.
    """
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_sem_jogo_a_aba_sai_da_tira(janela: _JanelaFalsa) -> None:
    """E o jogo fechando a leva embora — o pedido dela, do lado que ele nomeia.

    Arranque para ver reprovar: tratar `False` como `None` (não mexer quando
    não há jogo).
    """
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_gate_de_pintura_nao_engole_o_gate_de_existencia(
    janela: _JanelaFalsa,
) -> None:
    """A aba escondida NUNCA é a aba à vista — e mesmo assim tem de voltar.

    Este é o teste da ordem das duas chamadas dentro de `_sync_paineis_no_jogo`,
    que é a cura inteira. Com a aba fora da tira, a página corrente é outra:
    posto ATRÁS do gate de pintura (`id_da_pagina_corrente != ABA_NO_JOGO`), o
    gate de existência nunca mais rodaria, e a aba não voltaria nem com o jogo
    aberto — a cura teria trocado um defeito por outro pior.

    Arranque para ver reprovar: mover o `self._sync_visibilidade_no_jogo(state)`
    para DEPOIS do `return` do gate de pintura.
    """
    janela._notebook.set_current_page(0)  # ela está no Início
    assert janela._na_tira(ABA_NO_JOGO) is False

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_a_aba_nao_some_debaixo_dela_sem_levar_o_foco(
    janela: _JanelaFalsa,
) -> None:
    """Ela está NA aba quando o jogo fecha. O GTK a jogaria em "Gatilhos".

    O efeito colateral é do GTK3 e está medido nesta bancada: esconder a página
    corrente faz o notebook cair sozinho na página SEGUINTE. A Status é o
    destino escolhido — é a vizinha e a outra metade da mesma pergunta.

    Arranque para ver reprovar: tirar a chamada de `_sair_da_aba_no_jogo()` de
    `_sync_visibilidade_no_jogo`. A aba some do mesmo jeito (a primeira asserção
    passa) e a segunda reprova com "tab_triggers_box".
    """
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    janela._notebook.set_current_page(_ABAS.index(ABA_NO_JOGO))
    assert janela._aba_corrente() == ABA_NO_JOGO

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False
    assert janela._aba_corrente() == ABA_STATUS


def test_quem_ainda_nao_perguntou_nao_mexe_na_aba(janela: _JanelaFalsa) -> None:
    """O tri-estado chegando na tela: `lido=False` deixa tudo como está.

    É o restart do daemon com o jogo dela aberto. Sem isto a aba pisca.

    Arranque para ver reprovar: tirar o `if aberto is None: return` de
    `_sync_visibilidade_no_jogo` — com `appid=None` a aba passa a sumir, e a
    segunda asserção reprova.
    """
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._sync_paineis_no_jogo(_estado(lido=False, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_daemon_desligado_deixa_a_aba_como_estava(janela: _JanelaFalsa) -> None:
    """`state=None` é o daemon caindo — e a aba não é dele para levar embora.

    A aba desligada já tem a sua resposta ("O Hefesto está desligado.", escrita
    por `_sync_paineis_no_jogo`); tirá-la da tira junto trocaria uma frase
    honesta por um sumiço sem explicação.
    """
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    janela._sync_paineis_no_jogo(None)

    assert janela._na_tira(ABA_NO_JOGO) is True
