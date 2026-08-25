"""NO-JOGO-SEM-FALSO-VERDE-01/T4 — os dois caminhos em que o pulso saía cedo.

A aba "No jogo" TEM pulso: ela pega carona no tique lento de 2 Hz
(`_tick_profile_state` → `_render_slow_state` → `_sync_paineis_no_jogo`). O
defeito medido em 23/08 não é falta de pulso — é o pulso **sair antes** de a aba
ser atendida, por duas portas diferentes, e nas duas o desfecho é o mesmo:

1. **o gate de popup.** `_render_slow_state` devolvia na primeira linha quando
   havia qualquer combo aberto em QUALQUER aba (BUG-COMBO-POPUP-FLICKER-02). Com
   o jogo fechado nesse instante, a aba ficava na tira, e os painéis dentro dela
   congelados no último estado bom;
2. **o caminho de falha do poll.** `_on_profile_state_failure` soltava o guard de
   inflight e **não fazia mais nada** — o daemon podia estar mudo há minutos e a
   aba continuava dizendo "no jogo agora" ao lado de um número velho.

O contrato que os dois quebram está escrito na docstring de
`_sync_paineis_no_jogo`, e é a frase que dá nome à sprint: *"Painel parado com
número de três minutos atrás ao lado da palavra 'no jogo agora' é a mentira
confortável que esta aba existe para não contar."*

O notebook é REAL, pelo mesmo motivo do
`test_aba_no_jogo_entra_e_sai_da_tira`: quem esconde a ABA de uma página
escondida é o `GtkNotebook`, e dublar isso seria medir a nossa ficção.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("o pulso da aba No jogo que saía cedo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta — `gi` existe sem as
# typelibs no runner do CI, e o ImportError na COLETA derruba a suíte inteira.
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

#: As abas na ordem do glade, até a primeira depois da "No jogo" — a vizinha de
#: baixo é para onde o GTK cai sozinho se a página corrente sumir.
_ABAS = ("tab_home_box", ABA_STATUS, ABA_NO_JOGO, "tab_triggers_box")

#: Um DualSense na mesa. `player_slot` existe porque as chaves dos painéis saem
#: de `_conectados_na_ordem_dos_cards`, e ele é a chave dessa ordenação.
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
    """O que `Gtk.grab_get_current()` devolve enquanto um combo está aberto.

    Não é um dublê de widget: `_popup_is_open` só pergunta se a chamada devolveu
    **alguma coisa**, e é essa a única informação que este objeto carrega.
    """


class _JanelaFalsa(StatusActionsMixin):  # type: ignore[misc]
    """Host mínimo com os métodos de PRODUÇÃO, no molde do `retratar_abas.py`.

    Nada aqui reimplementa regra: o notebook e as páginas são GTK de verdade, e
    todo método chamado nos testes é o da mixin.
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
    """A janela no estado em que os dois defeitos aparecem: ela está NA aba.

    A ordem das duas linhas é obrigatória e foi medida aqui: o `GtkNotebook`
    **ignora** um `set_current_page` para uma página escondida, e a aba "No
    jogo" nasce fora da tira (`_nascer_aba_no_jogo_escondida`). Sem revelá-la
    antes, a página corrente continuaria sendo a Início e todo teste desta
    bancada passaria pelo motivo errado — o gate de PINTURA, e não o que se quer
    medir.

    Quem a revela é o gate de existência de PRODUÇÃO, com um jogo aberto.
    """
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


# ---------------------------------------------------------------------------
# Metade 1: o gate de popup segurava a EXISTÊNCIA da aba junto com a pintura
# ---------------------------------------------------------------------------


def test_o_combo_aberto_nao_prende_a_aba_na_tira(
    janela: _JanelaFalsa, combo_aberto: None
) -> None:
    """O jogo fecha com um combo aberto em outra aba — e a aba tem de sair.

    É o defeito inteiro em três linhas: ela abre o seletor de perfil na aba
    Início, o jogo fecha, e o tique lento devolve na primeira linha por causa do
    grab. A aba "No jogo" fica na tira apontando para painéis congelados.

    Arranque para ver reprovar: mover o `self._sync_visibilidade_no_jogo(state)`
    de `_render_slow_state` para DEPOIS do `if self._popup_is_open(): return`.
    """
    janela._render_slow_state(_estado(appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    janela._render_slow_state(_estado(appid=None))

    assert janela._na_tira(ABA_NO_JOGO) is False


def test_o_combo_aberto_continua_segurando_a_pintura(
    janela: _JanelaFalsa, combo_aberto: None
) -> None:
    """A contraprova, e ela é obrigatória: o gate de popup continua de pé.

    Mostrar/esconder uma página do notebook não toca a árvore de widgets do
    popup — é por isso que a existência da aba pode passar na frente do gate.
    Escrever nos rótulos DENTRO da aba é outra história, e é o re-layout que o
    BUG-COMBO-POPUP-FLICKER-02 mede: aquilo continua atrás do `return`.

    Sem esta asserção, a cura da T4 poderia ter sido "tirar o gate de popup", que
    é trocar um defeito por um pior — o combo dela fechando sozinho a 2 Hz.
    """
    janela._render_slow_state(_estado(appid=PRAGMATA))

    assert janela._no_jogo_contexto.get_text() == ""
    assert janela._no_jogo_paineis == {}


def test_sem_combo_a_aba_e_atendida_inteira(janela: _JanelaFalsa) -> None:
    """E sem popup nenhum o caminho feliz não mudou: painel na tela.

    A régua tem de saber as duas respostas. Se ela só soubesse dizer "a aba saiu
    da tira", uma cura que nunca desenhasse painel nenhum passaria.
    """
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    assert janela._na_tira(ABA_NO_JOGO) is True
    assert len(janela._no_jogo_paineis) == 1
    assert janela._no_jogo_contexto.get_text() != ""


# ---------------------------------------------------------------------------
# Metade 2: o poll que falha não esvaziava painel nenhum
# ---------------------------------------------------------------------------


def test_as_falhas_seguidas_esvaziam_os_paineis(janela: _JanelaFalsa) -> None:
    """O daemon emudece e a aba para de dizer "no jogo agora" com número velho.

    Arranque para ver reprovar: tirar o bloco
    `if self._profile_falhas_seguidas >= FALHAS_ATE_ESVAZIAR_NO_JOGO:` de
    `_on_profile_state_failure` — o guard de inflight continua sendo solto (que
    era tudo o que ele fazia até esta leva) e os painéis ficam na tela.
    """
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
    """Falha, falha, resposta boa, falha, falha: o painel continua na tela.

    A contagem é de falhas **SEGUIDAS**. Sem o zeramento ela seria cumulativa, e
    uma janela aberta a manhã inteira acabaria esvaziando a aba por causa de
    falhas espalhadas por horas — cada uma delas já perdoada por uma resposta boa
    logo depois.

    O `combo_aberto` está aqui como instrumento, e é declarado: o
    `_on_profile_state_result` chama `_render_slow_state`, que nesta bancada mínima não
    tem os widgets do resto da aba Status. O grab o faz devolver logo depois do
    gate de existência — que é justamente o trecho que interessa.

    Arranque para ver reprovar: tirar o `self._profile_falhas_seguidas = 0` de
    `_on_profile_state_result`.
    """
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    janela._on_profile_state_failure(TimeoutError("1"))
    janela._on_profile_state_failure(TimeoutError("2"))
    janela._on_profile_state_result(_estado(appid=PRAGMATA))
    janela._on_profile_state_failure(TimeoutError("3"))
    janela._on_profile_state_failure(TimeoutError("4"))

    assert len(janela._no_jogo_paineis) == 1
    assert janela._no_jogo_contexto.get_text() != TEXTO_OFFLINE


def test_uma_resposta_inutil_nao_zera_a_contagem(janela: _JanelaFalsa) -> None:
    """`_on_profile_state_result` também recebe o que não é `dict` — e aquilo não é sucesso.

    Tratar um payload inaproveitável como resposta boa manteria o painel
    congelado para sempre: a contagem nunca chegaria ao teto.

    Arranque para ver reprovar: mover o `self._profile_falhas_seguidas = 0` de
    `_on_profile_state_result` para fora do `if isinstance(state, dict):`.
    """
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))

    janela._on_profile_state_failure(TimeoutError("1"))
    janela._on_profile_state_failure(TimeoutError("2"))
    janela._on_profile_state_result(None)
    janela._on_profile_state_failure(TimeoutError("3"))

    assert janela._no_jogo_paineis == {}


def test_a_pane_do_ipc_nao_tira_a_aba_da_tira(janela: _JanelaFalsa) -> None:
    """E a aba CONTINUA na tira, mesmo com os painéis vazios. É de propósito.

    Sumir com a aba porque o nosso IPC falhou seria afirmar que o jogo dela
    fechou a partir de um silêncio NOSSO — o mesmo erro que o tri-estado de
    `jogo_steam_aberto` existe para não cometer. O que o silêncio autoriza a
    dizer é "não sei o que está chegando ao jogo", que é o painel vazio; não
    autoriza "o jogo fechou", que é a aba sumindo.
    """
    janela._sync_paineis_no_jogo(_estado(appid=PRAGMATA))
    assert janela._na_tira(ABA_NO_JOGO) is True

    for _ in range(FALHAS_ATE_ESVAZIAR_NO_JOGO):
        janela._on_profile_state_failure(TimeoutError("daemon mudo"))

    assert janela._na_tira(ABA_NO_JOGO) is True
