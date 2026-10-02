"""Testes da ONDA0-Z7 · O AMBIENTE PRESUMIDO 01 — o display gráfico (Z7-A)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app import arranque
from hefesto_dualsense4unix.integrations.window_backends import xlib

RAIZ = Path(__file__).resolve().parents[2]


class TestConexaoProvada:
    """`conexao_provada()` relata SEM tentar conectar — três estados."""

    def test_nenhuma_tentativa_ainda_devolve_none(self) -> None:
        backend = xlib.XlibBackend()
        assert backend.conexao_provada() is None

    def test_conectado_devolve_true(self) -> None:
        backend = xlib.XlibBackend()
        backend._connected = True
        assert backend.conexao_provada() is True

    def test_tentou_e_falhou_devolve_false(self) -> None:
        backend = xlib.XlibBackend()
        backend._init_attempted = True
        backend._connected = False
        assert backend.conexao_provada() is False

    def test_ensure_connected_com_display_morto_prova_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA de T-01 na origem: conexão real recusada."""
        monkeypatch.setenv("DISPLAY", ":99")

        def _recusa(*_a: object, **_k: object) -> None:
            raise ConnectionRefusedError("recusado para o teste")

        import Xlib.display

        monkeypatch.setattr(Xlib.display, "Display", _recusa)

        backend = xlib.XlibBackend()
        assert backend.conexao_provada() is None
        assert backend._ensure_connected() is False
        assert backend.conexao_provada() is False

    def test_ensure_connected_com_display_vivo_prova_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DISPLAY", ":99")

        class _DisplayFalso:
            def close(self) -> None:
                pass

        import Xlib.display

        monkeypatch.setattr(Xlib.display, "Display", lambda: _DisplayFalso())

        backend = xlib.XlibBackend()
        assert backend._ensure_connected() is True
        assert backend.conexao_provada() is True


class TestWindowReaderDiagDelegaConexaoProvada:
    """`WindowReaderDiag.conexao_provada` delega, com fallback honesto."""

    def test_delega_para_o_backend_xlib(self) -> None:
        from hefesto_dualsense4unix.integrations.window_detect import WindowReaderDiag

        backend = xlib.XlibBackend()
        backend._connected = True
        reader = WindowReaderDiag(backend)
        assert reader.conexao_provada() is True

    def test_backend_sem_o_conceito_devolve_none(self) -> None:
        """Portal/wlrctl/null/dublê sem `conexao_provada` -> None honesto."""
        from hefesto_dualsense4unix.integrations.window_detect import WindowReaderDiag

        class _BackendSemConceito:
            backend_name = "null"

            def get_active_window_info(self) -> None:
                return None

        reader = WindowReaderDiag(_BackendSemConceito())
        assert reader.conexao_provada() is None


class TestOXwaylandNaoEOPadrao:
    """O `GDK_BACKEND=x11` só entra pelo opt-in do `run.sh`, nunca pelo Python."""

    def test_a_cura_que_forcava_nao_volta(self) -> None:
        for nome in ("forcar_xwayland_no_cosmic", "x11_alcancavel", "CHAVE_SEM_XWAYLAND"):
            assert not hasattr(arranque, nome), f"{nome} voltou a `app/arranque.py`"

    def test_o_lancador_nao_escreve_gdk_backend(self) -> None:
        fonte = (RAIZ / "scripts" / "abrir_interface.py").read_text(encoding="utf-8")
        assert "GDK_BACKEND" not in fonte
        assert "forcar_xwayland" not in fonte


class TestBackoffCrescenteEWarningUnico:
    def _backend_que_sempre_falha(self, monkeypatch: pytest.MonkeyPatch) -> xlib.XlibBackend:
        monkeypatch.setenv("DISPLAY", ":99")

        def _recusa(*_a: object, **_k: object) -> None:
            raise ConnectionRefusedError("recusado para o teste")

        import Xlib.display

        monkeypatch.setattr(Xlib.display, "Display", _recusa)
        return xlib.XlibBackend()

    def test_backoff_dobra_ate_o_teto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        backend = self._backend_que_sempre_falha(monkeypatch)
        relogio = [0.0]
        monkeypatch.setattr(xlib.time, "monotonic", lambda: relogio[0])

        vistos = []
        for _ in range(10):
            backend._ensure_connected()
            vistos.append(backend._connect_backoff_sec)
            relogio[0] = backend._last_connect_fail + backend._connect_backoff_sec

        assert vistos[0] == 60.0
        assert vistos[1] == 120.0
        assert vistos[2] == 240.0
        assert vistos[-1] == xlib._RECONNECT_BACKOFF_MAX_SEC

    def test_quarenta_leituras_no_maximo_dois_warnings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA de T-03: 40 leituras com display morto -> no máximo 2"""
        backend = self._backend_que_sempre_falha(monkeypatch)
        relogio = [0.0]
        monkeypatch.setattr(xlib.time, "monotonic", lambda: relogio[0])

        warnings: list[str] = []
        monkeypatch.setattr(
            xlib.logger, "warning", lambda evento, **kw: warnings.append(evento)
        )

        primeira: float | None = None
        ultima: float | None = None
        for _ in range(40):
            backend._ensure_connected()
            if primeira is None:
                primeira = relogio[0]
            ultima = relogio[0]
            relogio[0] += 30.0

        assert len(warnings) <= 2
        assert (ultima or 0.0) - (primeira or 0.0) >= xlib._RECONNECT_BACKOFF_SEC
