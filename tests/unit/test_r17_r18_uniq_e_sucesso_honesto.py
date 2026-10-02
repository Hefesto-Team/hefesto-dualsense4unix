"""R-17 e R-18 (auditoria 23/07) — alvo certo e sucesso honesto."""

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


class TestR18SucessoHonesto:


    def test_status_ok_foi_mantido_de_proposito(self) -> None:
        """Trocar para "partial"/"failed" faria a GUI dizer "daemon offline?"."""
        fonte = (
            REPO / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        assert '"status": "ok", "applied": applied' in fonte
