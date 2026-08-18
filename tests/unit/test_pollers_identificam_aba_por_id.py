"""JANELA-FIEL-01/E2 — os dois relógios mais quentes olham o ID da aba, não o número.

A casa escreveu a regra (EST-10, em `app.py`: "identificar pelo WIDGET, não pelo
índice — a fusão de 'Mouse' e 'Teclado' renumerou as páginas, e um mapa por
índice teria passado a chamar o refresher errado em silêncio") e depois a violou
nos dois pollers mais quentes: o de 10 Hz da aba Status comparava
`get_current_page() != 1` e o de 2 s da aba Início comparava `== 0`.

Hoje bate por sorte: `tab_home_box` é a página 0 e `tab_status_box` é a 1. No dia
em que alguém inserir, remover ou reordenar uma aba no Glade, o tick de 10 Hz
passa a rodar numa aba onde não pinta nada (saturando o executor de UM worker) e
a aba Início para de reconciliar — sem exceção, sem log, sem ninguém saber.

MORDIDA: o notebook destes testes tem uma aba A MAIS ANTES da Início, então os
índices 0 e 1 apontam para as abas ERRADAS. Com o gate por índice de volta, o
tick de 10 Hz não roda na Status e o da Início não reconcilia na Início: os dois
testes de reordenação reprovam.

O notebook é REAL de propósito: um dublê sem `Gtk.Buildable` responde `None` para
tudo e o teste passaria com qualquer coisa.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("pollers por id de aba")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta — `gi` existe sem as
# typelibs no runner do CI, e o ImportError na COLETA derruba a suíte inteira.
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import status_actions
from hefesto_dualsense4unix.app.actions.home_actions import (
    ABA_INICIO,
    HomeActionsMixin,
    id_da_pagina,
    id_da_pagina_corrente,
)
from hefesto_dualsense4unix.app.actions.status_actions import (
    ABA_STATUS,
    StatusActionsMixin,
)


def _pagina(nome: str) -> Gtk.Widget:
    page = Gtk.Box()
    Gtk.Buildable.set_name(page, nome)
    return page


def _notebook(*ids: str, embrulhar: bool = True) -> Gtk.Notebook:
    """Monta um notebook com as páginas na ordem pedida.

    `embrulhar` reproduz `_wrap_notebook_pages_in_scroll`, que envolve oito das
    nove páginas num `GtkScrolledWindow` — e o GTK ainda insere um `GtkViewport`
    no meio, porque `GtkBox` não rola sozinho.
    """
    notebook = Gtk.Notebook()
    for nome in ids:
        pagina: Gtk.Widget = _pagina(nome)
        if embrulhar:
            scroller = Gtk.ScrolledWindow()
            scroller.add(pagina)
            pagina = scroller
        notebook.append_page(pagina, Gtk.Label(label=nome))
    notebook.show_all()
    return notebook


class _AppFalsa:
    """Superfície mínima que os dois ticks tocam, com os métodos de PRODUÇÃO."""

    def __init__(self, notebook: Gtk.Notebook) -> None:
        self._notebook = notebook
        self._live_inflight = False
        self.home_refreshes = 0
        self._tick_live_state = StatusActionsMixin._tick_live_state.__get__(self)
        self._tick_home_state = HomeActionsMixin._tick_home_state.__get__(self)

    def _get(self, widget_id: str) -> Any:
        return self._notebook if widget_id == "main_notebook" else None

    def _refresh_home_tab(self) -> None:
        self.home_refreshes += 1

    def _on_live_state_result(self, _state: Any) -> bool:
        return False

    def _on_live_state_failure(self, _exc: Exception) -> bool:
        return False


@pytest.fixture
def sem_ipc(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Conta as chamadas de estado do tick rápido, sem falar com o daemon."""
    chamadas: list[str] = []

    def _call_async(metodo: str, *_args: Any, **_kwargs: Any) -> None:
        chamadas.append(metodo)

    monkeypatch.setattr(status_actions, "call_async", _call_async)
    return chamadas


def _tick_rapido(app: _AppFalsa) -> None:
    """Um tick de 10 Hz. O latch de inflight é do outro defeito — some daqui."""
    app._live_inflight = False
    app._tick_live_state()


def test_id_da_pagina_desembrulha_rolador_e_viewport() -> None:
    """Sem desembrulhar, NENHUMA aba seria reconhecida: o widget é o rolador."""
    scroller = Gtk.ScrolledWindow()
    scroller.add(_pagina("tab_status_box"))

    assert id_da_pagina(scroller) == "tab_status_box"
    assert id_da_pagina(_pagina("tab_home_box")) == "tab_home_box"
    assert id_da_pagina(None) is None
    assert id_da_pagina(object()) is None, "o que não é Buildable não tem id"


def test_id_da_pagina_corrente_segue_a_pagina_a_vista() -> None:
    notebook = _notebook(ABA_INICIO, ABA_STATUS)

    notebook.set_current_page(0)
    assert id_da_pagina_corrente(notebook) == ABA_INICIO
    notebook.set_current_page(1)
    assert id_da_pagina_corrente(notebook) == ABA_STATUS
    assert id_da_pagina_corrente(None) is None


def test_tick_rapido_roda_na_status_mesmo_com_aba_nova_antes(
    sem_ipc: list[str],
) -> None:
    """Uma aba a mais antes da Início: a Status vira a página 2, não a 1."""
    notebook = _notebook("aba_nova_box", ABA_INICIO, ABA_STATUS)
    app = _AppFalsa(notebook)

    notebook.set_current_page(2)  # Status
    _tick_rapido(app)
    assert sem_ipc == ["daemon.state_full"], (
        "com gate por índice, o tick de 10 Hz para de rodar na aba Status"
    )

    notebook.set_current_page(1)  # Início
    _tick_rapido(app)
    notebook.set_current_page(0)  # a aba nova
    _tick_rapido(app)
    assert sem_ipc == ["daemon.state_full"], (
        "10 Hz de state_full fora da Status só saturam o worker compartilhado"
    )


def test_tick_da_inicio_reconcilia_na_inicio_mesmo_com_aba_nova_antes(
    sem_ipc: list[str],
) -> None:
    """A mesma reordenação, do outro lado: Início vira a página 1, não a 0."""
    notebook = _notebook("aba_nova_box", ABA_INICIO, ABA_STATUS)
    app = _AppFalsa(notebook)

    notebook.set_current_page(1)  # Início
    app._tick_home_state()
    assert app.home_refreshes == 1, (
        "com gate por índice, a aba Início para de reconciliar pelo tick"
    )

    notebook.set_current_page(0)  # a aba nova
    app._tick_home_state()
    notebook.set_current_page(2)  # Status
    app._tick_home_state()
    assert app.home_refreshes == 1


def test_ordem_de_hoje_continua_funcionando(sem_ipc: list[str]) -> None:
    """A ordem do glade de hoje (Início 0, Status 1) não muda de comportamento."""
    notebook = _notebook(ABA_INICIO, ABA_STATUS)
    app = _AppFalsa(notebook)

    notebook.set_current_page(1)
    _tick_rapido(app)
    app._tick_home_state()
    assert sem_ipc == ["daemon.state_full"]
    assert app.home_refreshes == 0

    notebook.set_current_page(0)
    _tick_rapido(app)
    app._tick_home_state()
    assert sem_ipc == ["daemon.state_full"]
    assert app.home_refreshes == 1


def test_sem_notebook_o_tick_rapido_nao_e_gateado(sem_ipc: list[str]) -> None:
    """Sem notebook não há aba à vista para consultar — o gate não se aplica.

    É o comportamento de antes, preservado: quem monta a mixin sem o glade
    (dublê) continua vendo o tick rodar.
    """
    app = _AppFalsa(None)  # type: ignore[arg-type]

    _tick_rapido(app)
    app._tick_home_state()

    assert sem_ipc == ["daemon.state_full"]
    assert app.home_refreshes == 0
