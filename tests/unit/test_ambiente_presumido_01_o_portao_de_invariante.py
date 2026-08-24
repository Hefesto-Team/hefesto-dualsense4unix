"""T-04 (ONDA0-Z7) — o portão que impede o payload de se contradizer.

Nenhum conserto em `src/`: este é o portão que impede T-01
(`autoswitch._build_diag_window_reader`) de ser desfeito por um refactor
futuro sem que ninguém perceba.

A invariante: no bloco `window_detect_*` de `IpcHandlersMixin._window_detect_payload`
(`daemon/ipc_handlers.py:2066-2110`), **`healthy=True` com `useful_age_sec=None`
e `seeing=False` é estado impossível** — diz "estou bem" e "nunca vi nada", ao
mesmo tempo. É exatamente o que a bancada dela mediu em 23/08/2026: `DISPLAY=:1`
presente, servidor recusando, `healthy=True` a sessão inteira porque o
`initial_healthy` antigo presumia (`initial_backend == "xlib"`) em vez de provar.

Este é o único teste da sprint que TEM de reprovar contra a árvore de HOJE
(com T-01 aplicado) antes de existir — e agora que T-01 está aplicado, ele
nasce passando. A prova de que ele sabe reprovar é arrancar T-01 (a sonda de
`_build_diag_window_reader`) e ver este teste denunciar a contradição de
novo — feito manualmente durante a execução desta sprint, com a saída colada
no relatório do executor (o arranque não fica em código, para não reintroduzir
o defeito que T-01 cura só para o teste poder reprovar sozinho).
"""
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
        """T-04: o cenário exato de §3.1 — `DISPLAY` presente, servidor
        recusando — não pode produzir o payload contraditório com T-01 no
        lugar."""
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
        # E o valor real, positivo: sem prova de conexão, healthy nasce False.
        assert payload["window_detect_healthy"] is False
        assert payload["window_detect_reason"] is None  # ainda não houve leitura via reader()

    def test_healthy_true_com_leitura_util_recente_nao_viola(self) -> None:
        """Controle: `healthy=True` É válido quando há prova de vida — uma
        leitura útil recente, `useful_age_sec` numérico. A invariante só
        proíbe a COMBINAÇÃO "bem" + "nunca vi", não `healthy=True` sozinho."""
        store = StateStore()
        store.set_window_detect_backend("xlib", healthy=True)
        store.record_window_detect_read("xlib", "Sackboy")

        handlers = _HandlersMinimos(store)
        payload = handlers._window_detect_payload()

        assert payload["window_detect_healthy"] is True
        assert payload["window_detect_useful_age_sec"] is not None
        assert not _invariante_violada(payload)

    def test_portao_sabe_denunciar_o_estado_impossivel_construido_a_mao(self) -> None:
        """O portão RECUSA quando alguém monta o estado impossível na mão —
        prova que `_invariante_violada` (a régua deste teste) sabe reprovar,
        não só passar."""
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
