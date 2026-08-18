"""JANELA-FIEL-01/E1 — o reload que não volta não pode calar a reconciliação.

R-08 curou o caso feliz: o perfil ativo muda por fora (autoswitch ao abrir o
jogo, botão Ativar, bandeja, hotkey PS+D-pad) e o tick de 2 Hz recarrega o
rascunho. O buraco estava no caminho ruim.

`_draft_reload_for` é marcado ANTES de disparar o worker (o tick roda a 2 Hz e o
carregamento é assíncrono), e nenhum dos dois retornos o limpava. Se a leitura de
estado falhasse no instante do worker — o daemon cai ou reinicia, e o timeout é
de 0,25 s — o latch ficava marcado para o perfil novo e a janela **nunca mais
tentava**: as abas seguiam editando, o rodapé seguia pré-preenchido e o "Aplicar"
seguia empurrando as seções do perfil ANTERIOR por cima do perfil do jogo. Sem
toast, sem log, sem nada na tela. E só se soltava se o perfil ativo virasse um
TERCEIRO nome.

O que estes testes trancam, e o que os faz MORDER:

1. leitura de estado que não voltou é falha TRANSITÓRIA — solta o latch, e o
   tick seguinte tenta de novo. Com o latch de antes (marcado e nunca limpo), o
   segundo tick não dispara nada e `_active_profile_name` fica no perfil velho
   para sempre: os dois asserts do primeiro teste reprovam;
2. perfil ativo que não existe em disco é falha PERMANENTE — tenta UMA vez e
   para. Essa é a decisão escrita em `app.py` (`__init__`), e é o que a cura
   ingênua ("zerar o latch em toda falha") reabriria: viraria IPC + I/O de disco
   a 2 Hz para sempre. Zerando o latch sem distinguir, o segundo teste reprova.

Exercita o código de PRODUÇÃO de ponta a ponta — reconciliação, worker e
aplicação — sobre um dublê com a superfície mínima, com `run_in_thread` rodando
na mesma thread (não há loop GTK aqui).
"""

from __future__ import annotations

from typing import Any

import pytest


def _app_class() -> Any:
    """`HefestoApp` — ou pula quando o GTK real falta (CI headless).

    Padrão do repo (test_gui_draft_reconcilia_perfil_ativo): `app.app` importa
    `from gi.repository import GdkPixbuf, Gtk` no TOPO, e o CI headless tem `gi`
    mas não os typelibs. Importar aqui, dentro de um helper com try/except,
    evita quebrar a COLETA.
    """
    try:
        from hefesto_dualsense4unix.app.app import HefestoApp
    except (ImportError, ValueError) as exc:  # pragma: no cover - ambiente
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return HefestoApp


def _perfil(nome: str) -> Any:
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchAny,
        Profile,
        RumbleConfig,
        TriggerConfig,
        TriggersConfig,
    )

    return Profile(
        name=nome,
        match=MatchAny(),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off", params=[]),
            right=TriggerConfig(mode="Off", params=[]),
        ),
        leds=LedsConfig(
            lightbar=(10, 20, 30),
            lightbar_brightness=1.0,
            player_leds=[True, False, False, False, False],
        ),
        rumble=RumbleConfig(),
    )


class _Relogio:
    """Relógio do teste — o prazo do latch em voo é atravessado de propósito."""

    def __init__(self, agora: float = 1000.0) -> None:
        self.agora = agora

    def monotonic(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


class _AppFalsa:
    """Dublê que roda os métodos REAIS de `HefestoApp`.

    Os quatro métodos do caminho de reconciliação vêm da classe de produção,
    ligados tarde (o import só acontece quando um teste roda, nunca na coleta).
    """

    def __init__(self, ativo: str = "FPS") -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        app_cls = _app_class()
        for nome in (
            "_reconciliar_draft_com_perfil_ativo",
            "_tem_edicao_pendente",
            "_bootstrap_draft_async",
            "_compute_draft_from_active_profile",
        ):
            setattr(self, nome, getattr(app_cls, nome).__get__(self))
        self.draft = DraftConfig.default()
        self._draft_baseline: Any = self.draft
        self._active_profile_name = ativo
        self._draft_reload_for: str | None = None
        self._draft_reload_inflight = False
        self._draft_reload_inflight_since = 0.0
        self.toasts: list[tuple[str, str]] = []

    def _status_toast(self, contexto: str, msg: str) -> None:
        self.toasts.append((contexto, msg))


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    _app_class()  # pula quando o GTK real falta, antes de importar o módulo
    from hefesto_dualsense4unix.app import app as app_mod

    falso = _Relogio()
    monkeypatch.setattr(app_mod, "time", falso)
    return falso


@pytest.fixture
def disparos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Roda o worker na mesma thread e conta cada disparo.

    `run_in_thread` real usa `GLib.idle_add` para voltar à thread GTK; sem loop
    GTK nos testes os callbacks nunca rodariam.
    """
    _app_class()
    from hefesto_dualsense4unix.app import ipc_bridge

    contagem: list[str] = []

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        contagem.append(getattr(fn, "__name__", "?"))
        try:
            resultado = fn()
        except Exception as exc:  # espelha o run_in_thread real
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(ipc_bridge, "run_in_thread", _sync)
    return contagem


def test_leitura_que_nao_voltou_solta_o_latch_e_a_janela_tenta_de_novo(
    monkeypatch: pytest.MonkeyPatch, relogio: _Relogio, disparos: list[str]
) -> None:
    """O caso da sprint: o daemon cai no instante do worker e volta em seguida.

    MORDIDA: com o `_draft_reload_for` de antes — marcado antes do disparo e
    nunca limpo — o segundo tick não dispara nada e a janela fica no "FPS" pelo
    resto da sessão. Os dois asserts finais reprovam.
    """
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.profiles import loader

    app = _AppFalsa(ativo="FPS")
    monkeypatch.setattr(loader, "load_all_profiles", lambda: [_perfil("Pragmata")])
    # O socket sumiu: `daemon_state_full` devolve None (daemon offline/timeout).
    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: None)

    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 1
    assert app._active_profile_name == "FPS", "nada carregou — o draft segue o antigo"

    # Tick seguinte, ainda com o daemon mudo: tem de tentar de novo.
    relogio.avancar(0.5)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 2, "o latch ficou preso e a janela parou de reconciliar"

    # O daemon voltou: o tick seguinte carrega o perfil do jogo.
    monkeypatch.setattr(
        ipc_bridge, "daemon_state_full", lambda: {"active_profile": "Pragmata"}
    )
    relogio.avancar(0.5)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert app._active_profile_name == "Pragmata"
    assert app.draft.leds.lightbar_rgb == (10, 20, 30), (
        "as abas continuariam mostrando e salvando o perfil ANTERIOR"
    )


def test_perfil_ativo_ausente_do_disco_tenta_uma_vez_e_para(
    monkeypatch: pytest.MonkeyPatch, relogio: _Relogio, disparos: list[str]
) -> None:
    """A decisão que a cura NÃO pode reabrir (`app.py`, `__init__`).

    MORDIDA: soltar o latch em toda falha — a cura ingênua — faria a janela
    redisparar IPC + leitura de disco a 2 Hz para sempre, com um perfil ativo
    que não existe em disco. O relógio avança além do prazo do latch em voo de
    propósito: nem ele pode transformar isto em loop.
    """
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.profiles import loader

    app = _AppFalsa(ativo="FPS")
    monkeypatch.setattr(loader, "load_all_profiles", lambda: [_perfil("Pragmata")])
    monkeypatch.setattr(
        ipc_bridge, "daemon_state_full", lambda: {"active_profile": "fantasma"}
    )

    for _ in range(10):
        relogio.avancar(0.5)
        app._reconciliar_draft_com_perfil_ativo({"active_profile": "fantasma"})

    assert len(disparos) == 1, "redisparo em loop de IPC + I/O de disco"
    assert app._active_profile_name == "FPS"


def test_worker_que_nunca_volta_e_dado_por_perdido_no_prazo(
    monkeypatch: pytest.MonkeyPatch, relogio: _Relogio
) -> None:
    """A rede de segurança: `run_in_thread` que não chama callback nenhum.

    MORDIDA: sem prazo no `_draft_reload_inflight`, o latch fica ligado para
    sempre e a reconciliação morre em silêncio — o assert final reprova. É a
    mesma lição já paga uma vez no `_home_inflight` da aba Início.
    """
    from hefesto_dualsense4unix.app import app as app_mod
    from hefesto_dualsense4unix.app import ipc_bridge

    app = _AppFalsa(ativo="FPS")
    disparos: list[Any] = []
    monkeypatch.setattr(
        ipc_bridge,
        "run_in_thread",
        lambda fn, on_success, on_failure=None: disparos.append(fn),
    )

    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 1
    assert app._draft_reload_inflight is True

    # Antes do prazo, ninguém insiste.
    relogio.avancar(app_mod.DRAFT_RELOAD_INFLIGHT_TIMEOUT_S - 0.1)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 1

    relogio.avancar(0.2)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 2, "chamada que nunca voltou calava a janela para sempre"


def test_edicao_pendente_continua_avisando_em_vez_de_descartar(
    monkeypatch: pytest.MonkeyPatch, relogio: _Relogio, disparos: list[str]
) -> None:
    """O gate de R-08 sobrevive à E1: soltar latch não é recarregar por cima."""
    from hefesto_dualsense4unix.app import ipc_bridge

    app = _AppFalsa(ativo="FPS")
    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: None)
    app.draft = app.draft.model_copy(
        update={"leds": app.draft.leds.model_copy(update={"lightbar_rgb": [9, 9, 9]})}
    )

    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})

    assert disparos == [], "recarregar por baixo da edição é perda de trabalho"
    assert len(app.toasts) == 1
    assert app.toasts[0][0] == "draft-reload"
