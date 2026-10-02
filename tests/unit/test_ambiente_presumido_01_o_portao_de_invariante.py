"""T-04 (ONDA0-Z7) — o portão que impede o payload de se contradizer."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore


class _HandlersMinimos(IpcHandlersMixin):
    """O bastante de `IpcHandlersMixin` para chamar `_window_detect_payload`."""

    def __init__(self, store: StateStore) -> None:
        self.store = store


def _invariante_violada(payload: dict[str, object]) -> bool:
    """`True` = o payload está no estado impossível ("estou bem" + "nunca vi")."""
    return (
        payload["window_detect_healthy"] is True
        and payload["window_detect_useful_age_sec"] is None
        and payload["window_detect_seeing"] is False
    )


class TestPayloadNaoSeContradiz:
    def test_estado_medido_em_3_1_nao_e_possivel_hoje(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-04: o cenário exato de §3.1 — `DISPLAY` presente, servidor"""
        monkeypatch.setenv("DISPLAY", ":1")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

        def _recusa(*_a: object, **_k: object) -> None:
            raise ConnectionRefusedError("recusado para o teste (T-04)")

        import Xlib.display

        monkeypatch.setattr(Xlib.display, "Display", _recusa)

        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import (
            _build_diag_window_reader,
        )

        store = StateStore()
        _build_diag_window_reader(store)

        handlers = _HandlersMinimos(store)
        payload = handlers._window_detect_payload()

        assert payload["window_detect_backend"] == "xlib"
        assert not _invariante_violada(payload), (
            "payload contraditório: healthy=True com useful_age_sec=None e "
            f"seeing=False -- {payload!r}"
        )
        assert payload["window_detect_healthy"] is False
        assert payload["window_detect_reason"] is None

    def test_healthy_true_com_leitura_util_recente_nao_viola(self) -> None:
        """Controle: `healthy=True` É válido quando há prova de vida — uma"""
        store = StateStore()
        store.set_window_detect_backend("xlib", healthy=True)
        store.record_window_detect_read("xlib", "Sackboy")

        handlers = _HandlersMinimos(store)
        payload = handlers._window_detect_payload()

        assert payload["window_detect_healthy"] is True
        assert payload["window_detect_useful_age_sec"] is not None
        assert not _invariante_violada(payload)

    def test_portao_sabe_denunciar_o_estado_impossivel_construido_a_mao(self) -> None:
        """O portão RECUSA quando alguém monta o estado impossível na mão —"""
        payload = {
            "window_detect_backend": "xlib",
            "window_detect_healthy": True,
            "window_detect_last_class": None,
            "window_detect_current_class": "unknown",
            "window_detect_useful_age_sec": None,
            "window_detect_seeing": False,
            "window_detect_reason": "sem_conexao_x",
        }
        assert _invariante_violada(payload) is True
