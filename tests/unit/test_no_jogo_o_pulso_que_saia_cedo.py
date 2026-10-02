"""NO-JOGO-SEM-FALSO-VERDE-01/T4 — os dois caminhos em que o pulso saía cedo."""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("o pulso da aba No jogo que saía cedo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import status_actions
from hefesto_dualsense4unix.app.actions.status_actions import (
    ABA_NO_JOGO,
    ABA_STATUS,
    FALHAS_ATE_ESVAZIAR_NO_JOGO,
    StatusActionsMixin,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import TEXTO_OFFLINE

PRAGMATA = 3357650

_ABAS = ("tab_home_box", ABA_STATUS, ABA_NO_JOGO, "tab_triggers_box")

#: Um DualSense na mesa. `player_slot` existe porque as chaves dos painéis saem
_PRIMARIO: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "player": 1,
    "player_slot": 1,
    "uniq": "e8473a0000c1",
}


def _estado(*, appid: int | None, com_controle: bool = True) -> dict[str, Any]:
    """Um `state_full` mínimo — só o que esta aba consulta."""
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(_PRIMARIO)] if com_controle else [],
        "rumble_ff": {"per_vpad": []},
        "jogo_steam": {"lido": True, "appid": appid},
    }


class _PopupAberto:
    """O que `Gtk.grab_get_current()` devolve enquanto um combo está aberto."""


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

    def _ir_para(self, nome: str) -> None:
        self._notebook.set_current_page(_ABAS.index(nome))


@pytest.fixture
def janela() -> _JanelaFalsa:
    """A janela no estado em que os dois defeitos aparecem: ela está NA aba."""
    app = _JanelaFalsa()
    app.install_no_jogo_tab()
    app._sync_visibilidade_no_jogo(_estado(appid=PRAGMATA))
    app._ir_para(ABA_NO_JOGO)
    return app


@pytest.fixture
def combo_aberto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um popup detendo o grab GTK, do jeito que `_popup_is_open` o enxerga."""
    monkeypatch.setattr(
        status_actions.Gtk, "grab_get_current", lambda: _PopupAberto()
    )


def test_o_combo_aberto_nao_prende_a_aba_na_tira(
    janela: _JanelaFalsa, combo_aberto: None
) -> None:
    """O jogo fecha com um combo aberto em outra aba — e a aba tem de sair."""
    janela._render_slow_state(_estado(appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._render_slow_state(_estado(appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_combo_aberto_continua_segurando_a_pintura(
    janela: _JanelaFalsa, combo_aberto: None
) -> None:
    """A contraprova, e ela é obrigatória: o gate de popup continua de pé."""
    janela._render_slow_state(_estado(appid=PRAGMATA))

    assert janela._no_jogo_contexto.get_text() == ""
    assert janela._no_jogo_paineis == {}


def test_sem_combo_a_aba_e_atendida_inteira(janela: _JanelaFalsa) -> None:
    """E sem popup nenhum o caminho feliz não mudou: painel na tela."""
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True
    assert len(janela._no_jogo_paineis) == 1
    assert janela._no_jogo_contexto.get_text() != ""


def test_as_falhas_seguidas_esvaziam_os_paineis(janela: _JanelaFalsa) -> None:
    """O daemon emudece e a aba para de dizer "no jogo agora" com número velho."""
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))
    assert len(janela._no_jogo_paineis) == 1

    for _ in range(FALHAS_ATE_ESVAZIAR_NO_JOGO):
        janela._on_profile_state_failure(TimeoutError("daemon mudo"))

    assert janela._no_jogo_paineis == {}
    assert janela._no_jogo_contexto.get_text() == TEXTO_OFFLINE


def test_uma_falha_sozinha_nao_pisca_a_aba(janela: _JanelaFalsa) -> None:
    """A contraprova do teto: uma falha isolada é ROTINA, e não pode apagar nada.

    O tique é de 2 Hz e o executor tem um worker só para os três pollers — um
    `daemon.state_full` que estoura o tempo sozinho acontece. Se o teto fosse 1,
    a aba piscaria na cara dela.

    Arranque para ver reprovar: trocar o `>=` por `>= 1` (ou apagar a contagem e
    esvaziar em toda falha).
    """
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    janela._on_profile_state_failure(TimeoutError("um poll perdido"))

    assert len(janela._no_jogo_paineis) == 1
    assert janela._no_jogo_contexto.get_text() != TEXTO_OFFLINE


def test_uma_resposta_boa_zera_a_contagem(
    janela: _JanelaFalsa, combo_aberto: None
) -> None:
    """Falha, falha, resposta boa, falha, falha: o painel continua na tela."""
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    janela._on_profile_state_failure(TimeoutError("1"))
    janela._on_profile_state_failure(TimeoutError("2"))
    janela._on_profile_state_result(_estado(appid=PRAGMATA))
    janela._on_profile_state_failure(TimeoutError("3"))
    janela._on_profile_state_failure(TimeoutError("4"))

    assert len(janela._no_jogo_paineis) == 1
    assert janela._no_jogo_contexto.get_text() != TEXTO_OFFLINE


def test_uma_resposta_inutil_nao_zera_a_contagem(janela: _JanelaFalsa) -> None:
    """`_on_profile_state_result` também recebe o que não é `dict` — e aquilo não é sucesso."""
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    janela._on_profile_state_failure(TimeoutError("1"))
    janela._on_profile_state_failure(TimeoutError("2"))
    janela._on_profile_state_result(None)
    janela._on_profile_state_failure(TimeoutError("3"))

    assert janela._no_jogo_paineis == {}


def test_a_pane_do_ipc_nao_tira_a_aba_da_tira(janela: _JanelaFalsa) -> None:
    """E a aba CONTINUA na tira, mesmo com os painéis vazios. É de propósito."""
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    for _ in range(FALHAS_ATE_ESVAZIAR_NO_JOGO):
        janela._on_profile_state_failure(TimeoutError("daemon mudo"))

    assert janela._na_tira(ABA_NO_JOGO) is True
