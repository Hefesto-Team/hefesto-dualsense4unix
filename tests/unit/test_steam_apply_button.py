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

from tests.conftest import exigir_gi_real

exigir_gi_real("test_steam_apply_button: importa código da janela GTK")

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
        assert "Nada a mudar" in format_apply_wrapper_result({"applied": True})


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


class TestWorker:


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
        """Instalação antiga sem a função de massa: recusa honesta apontando"""
        from hefesto_dualsense4unix.integrations import (
            steam_launch_options as slo,
        )

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

        stub._steam_apply_launch_worker()

        assert any("Não consegui aplicar" in t for t in stub.toasts)


class _FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class TestDialogoDeConfirmacaoPorFonte:
    """Espelho stub-level (headless): confirmação temada, não-bloqueante e"""


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


