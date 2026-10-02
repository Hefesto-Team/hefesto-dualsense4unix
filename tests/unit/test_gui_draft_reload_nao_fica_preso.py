"""JANELA-FIEL-01/E1 — o reload que não volta não pode calar a reconciliação."""

from __future__ import annotations

from typing import Any

import pytest


def _app_class() -> Any:
    """`HefestoApp` — ou pula quando o GTK real falta (CI headless)."""
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
    """Dublê que roda os métodos REAIS de `HefestoApp`."""

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
    _app_class()
    from hefesto_dualsense4unix.app import app as app_mod

    falso = _Relogio()
    monkeypatch.setattr(app_mod, "time", falso)
    return falso


@pytest.fixture
def disparos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Roda o worker na mesma thread e conta cada disparo."""
    _app_class()
    from hefesto_dualsense4unix.app import ipc_bridge

    contagem: list[str] = []

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        contagem.append(getattr(fn, "__name__", "?"))
        try:
            resultado = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(ipc_bridge, "run_in_thread", _sync)
    return contagem


def test_leitura_que_nao_voltou_solta_o_latch_e_a_janela_tenta_de_novo(
    monkeypatch: pytest.MonkeyPatch, relogio: _Relogio, disparos: list[str]
) -> None:
    """O caso da sprint: o daemon cai no instante do worker e volta em seguida."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.profiles import loader

    app = _AppFalsa(ativo="FPS")
    monkeypatch.setattr(loader, "load_all_profiles", lambda: [_perfil("Pragmata")])
    # O socket sumiu: `daemon_state_full` devolve None (daemon offline/timeout).
    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: None)

    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 1
    assert app._active_profile_name == "FPS", "nada carregou — o draft segue o antigo"

    relogio.avancar(0.5)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "Pragmata"})
    assert len(disparos) == 2, "o latch ficou preso e a janela parou de reconciliar"

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
    """A decisão que a cura NÃO pode reabrir (`app.py`, `__init__`)."""
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
    """A rede de segurança: `run_in_thread` que não chama callback nenhum."""
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
