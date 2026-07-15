"""`_wrap_notebook_pages_in_scroll` não pode depender do TEXTO da aba (EST-10).

A aba Sistema (ex-"Daemon", `daemon_box`) é a única que NÃO deve ser envolvida
num `GtkScrolledWindow`: o
conteúdo principal dela já é um scroller (o log, com auto-scroll) e envolvê-la de
novo quebra a rolagem.

O código identificava essa aba por `label.get_text() not in {"Daemon"}`. O
`SPRINT-LEIGO-01` (LEIGO-03) renomeia a aba para "Sistema" — com a comparação por
texto, o skip pararia de casar **em silêncio** e o log ganharia um segundo
scroller. Este teste renomeia a aba de propósito: se alguém voltar a comparar por
texto, ele quebra.

O módulo `app.app` puxa `gi.repository.GdkPixbuf` no topo, que nem todo CI tem —
seguimos a convenção do `test_quit_app_stops_daemon.py`: importar lazy e pular
quando o gi falta. O notebook, as páginas e o builder são fakes, então o teste não
abre janela nenhuma.
"""
from __future__ import annotations

from typing import Any

import pytest


class _FakeLabel:
    def __init__(self, texto: str) -> None:
        self._texto = texto

    def get_text(self) -> str:
        return self._texto


class _FakePage:
    def __init__(self, nome: str) -> None:
        self.nome = nome


class _FakeScroller:
    """Só o que o wrap usa; serve também como o 'já é scroller' do glade."""

    def __init__(self) -> None:
        self.filho: Any = None

    def set_policy(self, *_a: object) -> None:
        pass

    def set_propagate_natural_width(self, _v: bool) -> None:
        pass

    def set_propagate_natural_height(self, _v: bool) -> None:
        pass

    def add(self, filho: Any) -> None:
        self.filho = filho

    def show_all(self) -> None:
        pass


class _FakeNotebook:
    def __init__(self, paginas: list[tuple[Any, _FakeLabel]]) -> None:
        self.paginas = list(paginas)

    def get_n_pages(self) -> int:
        return len(self.paginas)

    def get_nth_page(self, i: int) -> Any:
        return self.paginas[i][0]

    def get_tab_label(self, page: Any) -> _FakeLabel:
        return next(lbl for pg, lbl in self.paginas if pg is page)

    def remove_page(self, i: int) -> None:
        self.paginas.pop(i)

    def append_page(self, page: Any, label: _FakeLabel) -> None:
        self.paginas.append((page, label))


class _FakeBuilder:
    def __init__(self, objetos: dict[str, Any]) -> None:
        self.objetos = objetos

    def get_object(self, nome: str) -> Any:
        return self.objetos.get(nome)


def _load_app_module() -> Any:
    try:
        import hefesto_dualsense4unix.app.app as app_mod
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return app_mod


def _rodar_wrap(
    nome_da_aba_daemon: str, monkeypatch: pytest.MonkeyPatch
) -> _FakeNotebook:
    """Monta um notebook fake com 3 abas e roda o wrap REAL."""
    app_mod = _load_app_module()

    daemon_box = _FakePage("daemon_box")
    inicio = _FakePage("tab_home_box")
    status = _FakePage("tab_status_box")
    notebook = _FakeNotebook([
        (inicio, _FakeLabel("Início")),
        (status, _FakeLabel("Status")),
        (daemon_box, _FakeLabel(nome_da_aba_daemon)),
    ])
    builder = _FakeBuilder({"main_notebook": notebook, "daemon_box": daemon_box})

    # Só o ScrolledWindow precisa ser fake: é o widget que o wrap constrói. O
    # isinstance() contra o Gtk real continua valendo para as páginas fake (que
    # nunca são ScrolledWindow de verdade).
    gtk_falso = _GtkNamespace(app_mod.Gtk)
    monkeypatch.setattr(app_mod, "Gtk", gtk_falso)

    app = object.__new__(app_mod.HefestoApp)
    app.builder = builder  # type: ignore[attr-defined]
    app_mod.HefestoApp._wrap_notebook_pages_in_scroll(app)
    return notebook


class _GtkNamespace:
    """Gtk real, com ScrolledWindow trocado pelo fake (sem abrir janela)."""

    def __init__(self, gtk_real: Any) -> None:
        self._real = gtk_real
        self.ScrolledWindow = _FakeScroller

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._real, nome)


def _paginas_por_nome(notebook: _FakeNotebook) -> dict[str, Any]:
    return {label.get_text(): page for page, label in notebook.paginas}


class TestWrapNaoDependeDoTexto:
    def test_aba_daemon_nao_e_envolvida(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notebook = _rodar_wrap("Daemon", monkeypatch)

        paginas = _paginas_por_nome(notebook)
        assert not isinstance(paginas["Daemon"], _FakeScroller), (
            "a aba do log não pode ganhar um segundo scroller"
        )

    def test_as_outras_abas_sao_envolvidas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notebook = _rodar_wrap("Daemon", monkeypatch)

        paginas = _paginas_por_nome(notebook)
        assert isinstance(paginas["Início"], _FakeScroller)
        assert isinstance(paginas["Status"], _FakeScroller)

    def test_renomear_a_aba_nao_quebra_o_skip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O LEIGO-03 troca "Daemon" por "Sistema" — o skip tem de continuar valendo.

        Era exatamente aqui que o acoplamento a texto de UI mordia em silêncio.
        """
        notebook = _rodar_wrap("Sistema", monkeypatch)

        paginas = _paginas_por_nome(notebook)
        assert not isinstance(paginas["Sistema"], _FakeScroller), (
            "o skip da aba do log parou de casar quando o rótulo mudou — "
            "identifique a página pelo widget (id do Glade), não pelo texto"
        )
