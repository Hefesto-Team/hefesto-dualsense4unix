"""PLAT-01 (lado GUI) — botão "Travar Proton validado" com confirmação.

O botão chama `lock_proton_for_all_games()` da lane do pin
(`integrations/proton_pin`, lane paralela P-A). A GUI codifica CONTRA O
CONTRATO — retorno ``{locked, skipped, errors}`` (contagens ou listas;
``applied`` como sinônimo; ``tool`` opcional com o nome da versão pinada) —
com import lazy DENTRO do worker e o MÓDULO INTEIRO stubado nos testes (a
lane pode ainda não ter aterrissado; `sys.modules` decide, nunca o disco):

- diálogo de confirmação TEMADO e NÃO-bloqueante ANTES de tocar em qualquer
  arquivo (a ação mexe no config.vdf global da Steam);
- Steam aberta → instrui e NÃO toca em nada;
- módulo/função ausentes → recusa honesta apontando ./install.sh;
- resposta fora do contrato → recusa honesta, nunca "Pronto".

Padrão `_install_gi_stubs` (test_rumble_actions.py): roda sem PyGObject no
venv e, com o gi REAL disponível, NÃO instala stubs (GATE-SKIP-MASK-01).
"""
from __future__ import annotations

import contextlib
import inspect
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # o merge abaixo mutaria o gi REAL e faria testes de GUI pularem como
    # "ambiente sem GTK".
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    for cls_name in (
        "Builder", "Window", "Button", "MessageDialog", "TextView",
        "TextBuffer", "Label", "Box",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    # Enums usados pelos handlers de confirmação (valores do GTK real).
    if not hasattr(gtk_mod, "ResponseType"):
        gtk_mod.ResponseType = type(  # type: ignore[attr-defined]
            "ResponseType", (), {"OK": -5, "CANCEL": -6, "DELETE_EVENT": -4}
        )
    if not hasattr(gtk_mod, "MessageType"):
        gtk_mod.MessageType = type(  # type: ignore[attr-defined]
            "MessageType", (), {"QUESTION": 2}
        )
    if not hasattr(gtk_mod, "ButtonsType"):
        gtk_mod.ButtonsType = type(  # type: ignore[attr-defined]
            "ButtonsType", (), {"NONE": 0}
        )

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import daemon_actions  # noqa: E402
from hefesto_dualsense4unix.app.actions.daemon_actions import (  # noqa: E402
    DaemonActionsMixin,
    format_proton_lock_result,
)

_PP_MODNAME = "hefesto_dualsense4unix.integrations.proton_pin"

# ---------------------------------------------------------------------------
# format_proton_lock_result — pura, o miolo do toast
# ---------------------------------------------------------------------------


class TestFormatDoResultado:
    def test_contagens_int_com_tool(self) -> None:
        msg = format_proton_lock_result(
            {"locked": 3, "skipped": 1, "errors": 0, "tool": "GE-Proton10-34"}
        )
        assert "3 jogo(s)" in msg
        assert "GE-Proton10-34" in msg
        assert "backup" in msg
        assert "1 jogo(s) ficaram como estavam" in msg
        assert "falharam" not in msg

    def test_listas_no_lugar_de_contagens(self) -> None:
        """O contrato aceita listas de itens — a GUI conta, não explode."""
        msg = format_proton_lock_result(
            {"locked": ["42", "77"], "skipped": [], "errors": ["99"]}
        )
        assert "2 jogo(s)" in msg
        assert "1 jogo(s) falharam" in msg

    def test_applied_e_sinonimo_de_locked(self) -> None:
        msg = format_proton_lock_result({"applied": 2, "errors": 0})
        assert "2 jogo(s)" in msg
        assert "Pronto" in msg

    def test_nada_a_mudar(self) -> None:
        msg = format_proton_lock_result(
            {"locked": 0, "skipped": 0, "errors": 0}
        )
        assert "Nada a mudar" in msg

    def test_so_erros_nao_diz_pronto(self) -> None:
        msg = format_proton_lock_result(
            {"locked": 0, "skipped": 0, "errors": 2}
        )
        assert "Pronto" not in msg
        assert "2 jogo(s) falharam" in msg

    @pytest.mark.parametrize("torto", [None, "ok", 7, ["lista"]])
    def test_resposta_fora_do_contrato_e_recusa_honesta(
        self, torto: object
    ) -> None:
        msg = format_proton_lock_result(torto)
        assert "Pronto" not in msg
        assert "Não consegui travar o Proton" in msg

    def test_campos_ausentes_viram_zero(self) -> None:
        assert "Nada a mudar" in format_proton_lock_result({})

    def test_bool_nao_conta_como_int(self) -> None:
        # blindagem: {"locked": True} não pode virar "1 jogo(s)".
        assert "Nada a mudar" in format_proton_lock_result({"locked": True})

    def test_tool_nao_string_e_ignorada(self) -> None:
        msg = format_proton_lock_result({"locked": 1, "tool": 10})
        assert "1 jogo(s)" in msg
        assert "10" not in msg.replace("1 jogo", "")


# ---------------------------------------------------------------------------
# Fluxo do worker (Steam aberta / contrato / módulo ou função ausente / erro)
# ---------------------------------------------------------------------------


class _Stub(DaemonActionsMixin):
    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.worker_calls = 0

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)


@pytest.fixture()
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    """Executor e idle_add síncronos — o worker roda inline no teste."""
    monkeypatch.setattr(
        daemon_actions,
        "_get_executor",
        lambda: SimpleNamespace(submit=lambda fn: fn()),
    )
    monkeypatch.setattr(
        daemon_actions,
        "GLib",
        SimpleNamespace(idle_add=lambda fn, *args: fn(*args)),
    )


@pytest.fixture()
def pp_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Módulo proton_pin FAKE injetado em sys.modules (contrato PLAT-01).

    O módulo real nasce em lane paralela (P-A) e o teste do CONTRATO não
    pode depender de ele existir no disco — `sys.modules` vence o import.
    """
    caixa: dict[str, Any] = {
        "running": False,
        "result": {"locked": 2, "skipped": 0, "errors": 0,
                   "tool": "GE-Proton10-34"},
        "chamadas": 0,
    }

    mod = types.ModuleType(_PP_MODNAME)

    def fake_lock() -> Any:
        caixa["chamadas"] += 1
        resultado = caixa["result"]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    mod.lock_proton_for_all_games = fake_lock  # type: ignore[attr-defined]
    mod.steam_running = lambda: caixa["running"]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, _PP_MODNAME, mod)
    caixa["mod"] = mod
    return caixa


class TestWorker:
    def test_steam_aberta_instrui_e_nao_toca(
        self, sincrono: None, pp_fake: dict[str, Any]
    ) -> None:
        pp_fake["running"] = True
        stub = _Stub()

        stub._proton_lock_worker()

        assert pp_fake["chamadas"] == 0  # NÃO tocou em nada
        assert any("Steam está aberta" in t for t in stub.toasts)
        assert any("feche-a" in t for t in stub.toasts)

    def test_steam_fechada_trava_e_ecoa_o_contrato(
        self, sincrono: None, pp_fake: dict[str, Any]
    ) -> None:
        stub = _Stub()

        stub._proton_lock_worker()

        assert pp_fake["chamadas"] == 1
        assert any("2 jogo(s)" in t for t in stub.toasts)
        assert any("GE-Proton10-34" in t for t in stub.toasts)

    def test_modulo_ausente_recusa_com_o_caminho_do_install(
        self, sincrono: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Instalação sem a lane do pin: `None` em sys.modules faz o import
        levantar ImportError — recusa honesta, nunca traceback."""
        monkeypatch.setitem(sys.modules, _PP_MODNAME, None)
        stub = _Stub()

        stub._proton_lock_worker()

        assert any("install.sh" in t for t in stub.toasts)
        assert not any("Pronto" in t for t in stub.toasts)

    def test_funcao_ausente_recusa_com_o_caminho_do_install(
        self,
        sincrono: None,
        pp_fake: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Módulo presente mas SEM a função de lock (versão antiga): recusa
        honesta apontando o install — nunca AttributeError."""
        monkeypatch.delattr(pp_fake["mod"], "lock_proton_for_all_games")
        stub = _Stub()

        stub._proton_lock_worker()

        assert pp_fake["chamadas"] == 0
        assert any("install.sh" in t for t in stub.toasts)
        assert not any("Pronto" in t for t in stub.toasts)

    def test_sem_steam_running_proprio_usa_o_de_steam_launch_options(
        self,
        sincrono: None,
        pp_fake: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Contrato tolerante: proton_pin sem `steam_running` cai no gate de
        steam_launch_options — a recusa com a Steam viva continua valendo."""
        from hefesto_dualsense4unix.integrations import (
            steam_launch_options as slo,
        )

        monkeypatch.delattr(pp_fake["mod"], "steam_running")
        monkeypatch.setattr(slo, "steam_running", lambda: True)
        stub = _Stub()

        stub._proton_lock_worker()

        assert pp_fake["chamadas"] == 0
        assert any("Steam está aberta" in t for t in stub.toasts)

    def test_excecao_vira_toast_de_falha(
        self, sincrono: None, pp_fake: dict[str, Any]
    ) -> None:
        pp_fake["result"] = OSError("disco sumiu")
        stub = _Stub()

        stub._proton_lock_worker()  # não propaga

        assert any("Não consegui travar o Proton" in t for t in stub.toasts)


class TestModuloRealExpoeOSimbolo:
    """Achado #4: o worker faz `getattr(pp, "lock_proton_for_all_games")` e o
    chama ZERO-ARG. O `pp_fake` injeta o símbolo em sys.modules e mascarava a
    ausência dele no módulo REAL — com isso a suíte ficava verde enquanto o
    botão estava 100% morto (getattr → None → recusa "rode ./install.sh").
    Aqui importamos o proton_pin DE VERDADE e travamos o contrato do getattr.
    """

    def test_proton_pin_real_expoe_lock_proton_for_all_games(self) -> None:
        import importlib

        pp_real = importlib.import_module(_PP_MODNAME)
        lock_fn = getattr(pp_real, "lock_proton_for_all_games", None)
        assert lock_fn is not None, "o botão da GUI chama exatamente este nome"
        assert callable(lock_fn)


# ---------------------------------------------------------------------------
# Confirmação — só o OK dispara; qualquer outra resposta é no-op
# ---------------------------------------------------------------------------


class _FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class TestConfirmacao:
    def _stub_com_worker_gravado(self) -> _Stub:
        stub = _Stub()

        def _worker() -> None:
            stub.worker_calls += 1

        stub._proton_lock_worker = _worker  # type: ignore[method-assign]
        return stub

    def test_ok_dispara_o_worker_e_fecha(self) -> None:
        from gi.repository import Gtk

        stub = self._stub_com_worker_gravado()
        dlg = _FakeDialog()

        stub._on_proton_lock_confirm_response(dlg, int(Gtk.ResponseType.OK))

        assert dlg.destroyed is True
        assert stub.worker_calls == 1

    @pytest.mark.parametrize("resposta", [-6, -4, 0])  # CANCEL, DELETE, outro
    def test_qualquer_outra_resposta_so_fecha(self, resposta: int) -> None:
        stub = self._stub_com_worker_gravado()
        dlg = _FakeDialog()

        stub._on_proton_lock_confirm_response(dlg, resposta)

        assert dlg.destroyed is True
        assert stub.worker_calls == 0


class TestDialogoDeConfirmacaoPorFonte:
    """Espelho stub-level (headless): confirmação temada, não-bloqueante e
    com o texto honesto — o assert GTK-real vive na classe guardada abaixo."""

    def test_confirmacao_e_temada_e_nao_bloqueante(self) -> None:
        src = inspect.getsource(
            DaemonActionsMixin._build_proton_lock_confirm_dialog
        ) + inspect.getsource(DaemonActionsMixin.on_proton_lock)
        compacto = src.replace("\n", "").replace(" ", "")
        assert 'add_class("hefesto-dualsense4unix-window")' in compacto
        assert 'connect("response"' in compacto  # nunca run() (imkillable)
        assert ".run()" not in src
        assert "backup" in src  # promessa do PLAT-01 no texto pro leigo
        assert "FECHADA" in src  # o pré-requisito da Steam explícito

    def test_worker_importa_lazy_dentro_do_handler(self) -> None:
        src = inspect.getsource(DaemonActionsMixin._proton_lock_worker)
        assert "hefesto_dualsense4unix.integrations.proton_pin" in src
        assert "lock_proton_for_all_games" in src
        assert "getattr" in src  # defensivo contra instalação antiga


_DISPLAY_OK = False
with contextlib.suppress(Exception):
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk as _Gdk

    _DISPLAY_OK = _Gdk.Display.get_default() is not None


@pytest.mark.skipif(
    not _DISPLAY_OK, reason="sem display GTK — construção real do diálogo"
)
class TestDialogoGtkReal:
    def test_confirmacao_temada_com_botoes(self) -> None:
        from gi.repository import Gtk

        stub = _Stub()
        dlg = stub._build_proton_lock_confirm_dialog()
        try:
            assert isinstance(dlg, Gtk.MessageDialog)
            assert dlg.get_style_context().has_class(
                "hefesto-dualsense4unix-window"
            )
            assert "Proton" in (dlg.get_property("text") or "")
            corpo = dlg.get_property("secondary-text") or ""
            assert "backup" in corpo
            assert "FECHADA" in corpo
            for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
                assert dlg.get_widget_for_response(response) is not None
        finally:
            dlg.destroy()
