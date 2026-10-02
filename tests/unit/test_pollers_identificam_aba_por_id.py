"""JANELA-FIEL-01/E2 — os dois relógios mais quentes olham o ID da aba, não o número."""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("pollers por id de aba")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import status_actions


def _pagina(nome: str) -> Gtk.Widget:
    page = Gtk.Box()
    Gtk.Buildable.set_name(page, nome)
    return page


def _notebook(*ids: str, embrulhar: bool = True) -> Gtk.Notebook:
    """Monta um notebook com as páginas na ordem pedida."""
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


    def _get(self, widget_id: str) -> Any:
        return self._notebook if widget_id == "main_notebook" else None

    def _refresh_home_tab(self) -> None:
        self.home_refreshes += 1

    def _maybe_fetch_externos(self) -> None:
        """I5 (25/08/2026): o tique lento da Início passou a inventariar externos."""
        self.inventarios_de_externos += 1

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


def test_sem_notebook_o_tick_rapido_nao_e_gateado(sem_ipc: list[str]) -> None:
    """Sem notebook não há aba à vista para consultar — o gate não se aplica."""
    app = _AppFalsa(None)  # type: ignore[arg-type]

    _tick_rapido(app)
    app._tick_home_state()

    assert sem_ipc == ["daemon.state_full"]
    assert app.home_refreshes == 0
