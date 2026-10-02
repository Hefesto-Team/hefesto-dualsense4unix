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

exigir_gi_real("aba No jogo entrando e saindo da tira")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.status_actions import (
    ABA_NO_JOGO,
    ABA_STATUS,
    StatusActionsMixin,
)

PRAGMATA = 3357650

_ABAS = ("tab_home_box", ABA_STATUS, ABA_NO_JOGO, "tab_triggers_box")


def _estado(*, lido: bool, appid: int | None) -> dict[str, Any]:
    """Um `state_full` mínimo — só o que a visibilidade da aba consulta."""
    return {
        "connected": True,
        "controllers": [],
        "jogo_steam": {"lido": lido, "appid": appid},
    }


class _JanelaFalsa(StatusActionsMixin):  # type: ignore[misc]
    """Host mínimo com os métodos de PRODUÇÃO, no molde do `retratar_abas.py`."""

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


def test_a_aba_nasce_fora_da_tira(janela: _JanelaFalsa) -> None:
    """O boot sem jogo aberto não pode mostrar a aba nem por um quadro."""
    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_show_all_da_janela_nao_traz_a_aba_de_volta(
    janela: _JanelaFalsa,
) -> None:
    """`app.show()` roda um `window.show_all()` DEPOIS de toda montagem."""
    janela._notebook.show_all()

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_jogo_abrindo_traz_a_aba(janela: _JanelaFalsa) -> None:
    """O pedido dela, do lado que a faz aparecer."""
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_sem_jogo_a_aba_sai_da_tira(janela: _JanelaFalsa) -> None:
    """E o jogo fechando a leva embora — o pedido dela, do lado que ele nomeia."""
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_gate_de_pintura_nao_engole_o_gate_de_existencia(
    janela: _JanelaFalsa,
) -> None:
    """A aba escondida NUNCA é a aba à vista — e mesmo assim tem de voltar."""
    janela._notebook.set_current_page(0)
    assert janela._na_tira(ABA_NO_JOGO) is False

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_a_aba_nao_some_debaixo_dela_sem_levar_o_foco(
    janela: _JanelaFalsa,
) -> None:
    """Ela está NA aba quando o jogo fecha. O GTK a jogaria em "Gatilhos"."""
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    janela._notebook.set_current_page(_ABAS.index(ABA_NO_JOGO))
    assert janela._aba_corrente() == ABA_NO_JOGO

    janela._sync_paineis_no_jogo(_estado(lido=True, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False
    assert janela._aba_corrente() == ABA_STATUS


def test_quem_ainda_nao_perguntou_nao_mexe_na_aba(janela: _JanelaFalsa) -> None:
    """O tri-estado chegando na tela: `lido=False` deixa tudo como está."""
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._sync_paineis_no_jogo(_estado(lido=False, appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is True


def test_daemon_desligado_deixa_a_aba_como_estava(janela: _JanelaFalsa) -> None:
    """`state=None` é o daemon caindo — e a aba não é dele para levar embora."""
    janela._sync_paineis_no_jogo(_estado(lido=True, appid=PRAGMATA))

    janela._sync_paineis_no_jogo(None)

    assert janela._na_tira(ABA_NO_JOGO) is True
