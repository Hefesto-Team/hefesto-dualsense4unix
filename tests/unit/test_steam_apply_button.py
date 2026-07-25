"""PATH-06 (lado GUI) — botão "Aplicar aos jogos da Steam" com confirmação.

O botão deixou de ser só migração das linhas envenenadas: chama a função de
massa `apply_wrapper_to_all_games()` (integrations/steam_launch_options, lane
própria). A GUI codifica CONTRA O CONTRATO — retorno ``{applied, skipped,
errors}`` (contagens ou listas) — com import lazy DENTRO do handler e a
função stubada nos testes (a lane pode ainda não ter aterrissado):

- diálogo de confirmação TEMADO e NÃO-bloqueante ANTES de tocar em qualquer
  arquivo (a ação agora mexe em TODOS os jogos);
- resposta fora do contrato → recusa honesta, nunca "Pronto".

HONESTIDADE-STEAM-01 (25/07) — POLÍTICA NOVA, e este arquivo era a muralha da
antiga. Ele congelava, com `slo_fake["chamadas"] == 0` + a string "feche-a",
que a GUI NUNCA poderia fechar a Steam: com ela aberta, o único desfecho
possível era mandar a usuária embora. Só que a usuária clica no Hefesto
JUSTAMENTE com a Steam aberta, e a maquinaria de fechar/reabrir já existia e
era exercitada pelo `install.sh --migrate --stop-steam`.

A política nova mantém o que era certo e troca o que era parede:

- JOGO da Steam aberto ⇒ RECUSA, sempre (fechar mataria o jogo). Continua
  proibido tocar em qualquer coisa;
- só a Steam aberta ⇒ a GUI PERGUNTA ("preciso fechar por ~20 s; pause
  downloads") e só age com o sim. Sem consentimento, `stop_steam()` (que
  escala para `pkill -TERM/-KILL` depois de 30 s) nunca roda;
- Steam fechada ⇒ aplica direto, sem diálogo nenhum.

Os asserts abaixo travam a política NOVA — inclusive a parte que não mudou:
o zero-toque com jogo aberto e o zero-fechamento sem sim explícito.
"""
from __future__ import annotations

import contextlib
import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions
from hefesto_dualsense4unix.app.actions.daemon_actions import (
    DaemonActionsMixin,
    format_apply_wrapper_result,
)
from tests.conftest import skip_sem_gtk_response

# ---------------------------------------------------------------------------
# format_apply_wrapper_result — pura, o miolo do toast
# ---------------------------------------------------------------------------


class TestFormatDoResultado:
    def test_contagens_int(self) -> None:
        msg = format_apply_wrapper_result(
            {"applied": 3, "skipped": 1, "errors": 0}
        )
        assert "3 jogo(s)" in msg
        assert "hefesto-launch" in msg
        assert "preservadas" in msg
        assert "1 jogo(s) ficaram como estavam" in msg
        assert "falharam" not in msg

    def test_listas_no_lugar_de_contagens(self) -> None:
        """O contrato aceita listas de itens — a GUI conta, não explode."""
        msg = format_apply_wrapper_result(
            {"applied": ["42", "77"], "skipped": [], "errors": ["99"]}
        )
        assert "2 jogo(s)" in msg
        assert "1 jogo(s) falharam" in msg

    def test_nada_a_mudar(self) -> None:
        msg = format_apply_wrapper_result(
            {"applied": 0, "skipped": 0, "errors": 0}
        )
        assert "Nada a mudar" in msg

    def test_so_erros_nao_diz_pronto(self) -> None:
        msg = format_apply_wrapper_result(
            {"applied": 0, "skipped": 0, "errors": 2}
        )
        assert "Pronto" not in msg
        assert "2 jogo(s) falharam" in msg

    @pytest.mark.parametrize("torto", [None, "ok", 7, ["lista"]])
    def test_resposta_fora_do_contrato_e_recusa_honesta(
        self, torto: object
    ) -> None:
        msg = format_apply_wrapper_result(torto)
        assert "Pronto" not in msg
        assert "Não consegui aplicar" in msg

    def test_campos_ausentes_viram_zero(self) -> None:
        assert "Nada a mudar" in format_apply_wrapper_result({})

    def test_bool_nao_conta_como_int(self) -> None:
        # blindagem: {"applied": True} não pode virar "1 jogo(s)".
        assert "Nada a mudar" in format_apply_wrapper_result({"applied": True})


# ---------------------------------------------------------------------------
# Fluxo do worker (Steam aberta / contrato / função ausente / exceção)
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
def slo_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Steam fechada + apply_wrapper_to_all_games stubada (contrato PATH-06).

    `raising=False` no setattr da função de massa: ela nasce em lane paralela
    e o teste do CONTRATO não pode depender de ela já existir no módulo.

    `parou`/`reabriu` contam o fechamento REAL da Steam — é por eles que os
    testes provam que nada foi derrubado sem consentimento.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    caixa: dict[str, Any] = {
        "running": False,
        "jogo": False,
        "result": {"applied": 2, "skipped": 0, "errors": 0},
        "chamadas": 0,
        "parou": 0,
        "reabriu": 0,
    }
    monkeypatch.setattr(slo, "steam_running", lambda: caixa["running"])
    monkeypatch.setattr(slo, "steam_game_running", lambda: caixa["jogo"])

    def fake_stop() -> bool:
        caixa["parou"] += 1
        caixa["running"] = False
        return True

    monkeypatch.setattr(slo, "stop_steam", fake_stop)
    monkeypatch.setattr(
        slo, "reopen_steam", lambda: caixa.__setitem__("reabriu", caixa["reabriu"] + 1)
    )

    def fake_apply() -> Any:
        caixa["chamadas"] += 1
        resultado = caixa["result"]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    monkeypatch.setattr(
        slo, "apply_wrapper_to_all_games", fake_apply, raising=False
    )
    return caixa


@pytest.fixture()
def dialogo_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Intercepta o consentimento de fechar a Steam sem subir widget real."""
    capturado: dict[str, Any] = {}

    def _build(_parent: Any, **kwargs: Any) -> Any:
        capturado.update(kwargs)
        capturado["montado"] = capturado.get("montado", 0) + 1
        return SimpleNamespace(show_all=lambda: None)

    monkeypatch.setattr(
        daemon_actions, "build_steam_close_consent_dialog", _build
    )
    return capturado


class TestWorker:
    def test_jogo_aberto_recusa_e_nao_fecha_a_steam(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        dialogo_fake: dict[str, Any],
    ) -> None:
        """A recusa que NÃO virou pergunta: com jogo aberto, `steam -shutdown`
        mataria o jogo (progresso não salvo perdido). Nem aplica, nem fecha,
        nem sequer pergunta."""
        slo_fake["running"] = True
        slo_fake["jogo"] = True
        stub = _Stub()

        stub._steam_apply_launch_worker()

        assert slo_fake["chamadas"] == 0  # NÃO tocou em nada
        assert slo_fake["parou"] == 0  # NÃO derrubou a Steam
        assert not dialogo_fake.get("montado")  # nem ofereceu fechar
        assert any("jogo aberto" in t for t in stub.toasts)
        assert any("progresso" in t for t in stub.toasts)

    def test_steam_aberta_pergunta_e_nao_fecha_sozinha(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        dialogo_fake: dict[str, Any],
    ) -> None:
        """A parede virou pergunta — mas até o sim, nada acontece."""
        slo_fake["running"] = True
        stub = _Stub()

        stub._steam_apply_launch_worker()

        assert dialogo_fake.get("montado") == 1
        assert "20 segundos" in dialogo_fake["titulo"]
        assert "pause os downloads" in dialogo_fake["corpo"].lower()
        assert slo_fake["chamadas"] == 0
        assert slo_fake["parou"] == 0

    @skip_sem_gtk_response
    def test_cancelar_o_fechamento_nao_muda_nada(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        dialogo_fake: dict[str, Any],
    ) -> None:
        from gi.repository import Gtk

        slo_fake["running"] = True
        stub = _Stub()
        stub._steam_apply_launch_worker()

        dialogo_fake["on_response"](
            _FakeDialog(), int(Gtk.ResponseType.CANCEL)
        )

        assert slo_fake["chamadas"] == 0
        assert slo_fake["parou"] == 0
        assert any("Nada foi mudado" in t for t in stub.toasts)

    @skip_sem_gtk_response
    def test_consentimento_fecha_aplica_e_reabre(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        dialogo_fake: dict[str, Any],
    ) -> None:
        from gi.repository import Gtk

        slo_fake["running"] = True
        stub = _Stub()
        stub._steam_apply_launch_worker()

        dialogo_fake["on_response"](_FakeDialog(), int(Gtk.ResponseType.OK))

        assert slo_fake["parou"] == 1
        assert slo_fake["chamadas"] == 1
        assert slo_fake["reabriu"] == 1
        assert any("2 jogo(s)" in t for t in stub.toasts)

    def test_steam_que_nao_fecha_nao_edita_nada(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`with_steam_closed` devolvendo 'nao_fechou': recusa honesta, zero
        edição (editar com a Steam viva é edição perdida)."""
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        monkeypatch.setattr(slo, "stop_steam", lambda: False)
        slo_fake["running"] = True
        stub = _Stub()

        stub._steam_apply_launch_fechando()

        assert slo_fake["chamadas"] == 0
        assert any("não fechou" in t for t in stub.toasts)
        assert not any("Pronto" in t for t in stub.toasts)

    def test_steam_fechada_aplica_e_ecoa_o_contrato(
        self, sincrono: None, slo_fake: dict[str, Any]
    ) -> None:
        stub = _Stub()

        stub._steam_apply_launch_worker()

        assert slo_fake["chamadas"] == 1
        assert any("2 jogo(s)" in t for t in stub.toasts)

    def test_funcao_ausente_recusa_com_o_caminho_do_install(
        self,
        sincrono: None,
        slo_fake: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Instalação antiga sem a função de massa: recusa honesta apontando
        o install — nunca AttributeError nem toast de sucesso."""
        from hefesto_dualsense4unix.integrations import (
            steam_launch_options as slo,
        )

        # `None` simula o atributo ausente (getattr(..., None) do handler).
        monkeypatch.setattr(
            slo, "apply_wrapper_to_all_games", None, raising=False
        )
        stub = _Stub()

        stub._steam_apply_launch_worker()

        assert any("install.sh" in t for t in stub.toasts)
        assert not any("Pronto" in t for t in stub.toasts)

    def test_excecao_vira_toast_de_falha(
        self, sincrono: None, slo_fake: dict[str, Any]
    ) -> None:
        slo_fake["result"] = OSError("disco sumiu")
        stub = _Stub()

        stub._steam_apply_launch_worker()  # não propaga

        assert any("Não consegui aplicar" in t for t in stub.toasts)


# ---------------------------------------------------------------------------
# Confirmação — só o OK dispara; qualquer outra resposta é no-op
# ---------------------------------------------------------------------------


class _FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


@skip_sem_gtk_response
class TestConfirmacao:
    def _stub_com_worker_gravado(self) -> _Stub:
        stub = _Stub()

        def _worker() -> None:
            stub.worker_calls += 1

        stub._steam_apply_launch_worker = _worker  # type: ignore[method-assign]
        return stub

    def test_ok_dispara_o_worker_e_fecha(self) -> None:
        from gi.repository import Gtk

        stub = self._stub_com_worker_gravado()
        dlg = _FakeDialog()

        stub._on_steam_apply_confirm_response(dlg, int(Gtk.ResponseType.OK))

        assert dlg.destroyed is True
        assert stub.worker_calls == 1

    @pytest.mark.parametrize("resposta", [-6, -4, 0])  # CANCEL, DELETE, outro
    def test_qualquer_outra_resposta_so_fecha(self, resposta: int) -> None:
        stub = self._stub_com_worker_gravado()
        dlg = _FakeDialog()

        stub._on_steam_apply_confirm_response(dlg, resposta)

        assert dlg.destroyed is True
        assert stub.worker_calls == 0


class TestDialogoDeConfirmacaoPorFonte:
    """Espelho stub-level (headless): confirmação temada, não-bloqueante e
    com o texto honesto — o assert GTK-real vive na classe guardada abaixo."""

    def test_confirmacao_e_temada_e_nao_bloqueante(self) -> None:
        src = inspect.getsource(
            DaemonActionsMixin._build_steam_apply_confirm_dialog
        ) + inspect.getsource(DaemonActionsMixin.on_steam_apply_launch)
        compacto = src.replace("\n", "").replace(" ", "")
        assert 'add_class("hefesto-dualsense4unix-window")' in compacto
        assert 'connect("response"' in compacto  # nunca run() (imkillable)
        assert ".run()" not in src
        assert "preservadas" in src  # promessa do PATH-06 no texto
        # HONESTIDADE-STEAM-01: o texto dizia "A Steam precisa estar
        # FECHADA — se estiver aberta, eu aviso e não mexo em nada". O
        # botão passou a saber fechá-la COM consentimento, então o que o
        # diálogo tem de prometer agora é a PERMISSÃO, não a parede.
        assert "permissão" in src
        assert "20 segundos" in src

    def test_worker_importa_lazy_dentro_do_handler(self) -> None:
        src = inspect.getsource(DaemonActionsMixin._steam_apply_launch_worker)
        assert "from hefesto_dualsense4unix.integrations import" in src
        assert "apply_wrapper_to_all_games" in src


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
        dlg = stub._build_steam_apply_confirm_dialog()
        try:
            assert isinstance(dlg, Gtk.MessageDialog)
            assert dlg.get_style_context().has_class(
                "hefesto-dualsense4unix-window"
            )
            assert "hefesto-launch" in (dlg.get_property("text") or "")
            corpo = dlg.get_property("secondary-text") or ""
            assert "preservadas" in corpo
            assert "permissão" in corpo
            assert "20 segundos" in corpo
            for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
                assert dlg.get_widget_for_response(response) is not None
        finally:
            dlg.destroy()
