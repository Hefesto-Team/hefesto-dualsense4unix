"""R-17 (auditoria 23/07) — o alvo certo.

O R-18 (o `status: ok` do `profile.apply_draft`) saiu com o handler, em 06/10/2026:
o «Aplicar» é só o `profile.reaplicar`.
"""

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


class TestR17ApagarMandaOUniq:

    def test_led_set_aceita_uniq(self) -> None:
        """A rota por-MAC precisa existir do outro lado (PERFIL-05)."""
        import inspect

        from hefesto_dualsense4unix.app import ipc_bridge

        assert (
            "uniq" in inspect.signature(ipc_bridge.led_set_detalhado).parameters
        )

