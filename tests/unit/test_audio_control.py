"""Testes unitarios para AudioControl (FEAT-AUDIO-CONTROL-01).

Todos os testes usam mocks para subprocess.run e shutil.which — nenhum
depende de wpctl ou pactl instalados no sistema.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from hefesto.integrations.audio_control import DEBOUNCE_SEC, AudioControl

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    """Cria um CompletedProcess simulado."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


class _FakeClock:
    """Relogio injetavel e controlavel para testes de debounce."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


# ---------------------------------------------------------------------------
# 1. Deteccao de backend
# ---------------------------------------------------------------------------


def test_detects_wpctl_when_available() -> None:
    """AudioControl._ensure_backend() retorna 'wpctl' quando which(wpctl) encontra."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/wpctl" if cmd == "wpctl" else None

    with patch("shutil.which", side_effect=_which):
        ctrl = AudioControl()
        backend = ctrl._ensure_backend()
    assert backend == "wpctl"
    assert ctrl._backend == "wpctl"


def test_falls_back_to_pactl_when_no_wpctl() -> None:
    """Fallback para pactl quando wpctl não esta disponivel."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/pactl" if cmd == "pactl" else None

    with patch("shutil.which", side_effect=_which):
        ctrl = AudioControl()
        backend = ctrl._ensure_backend()
    assert backend == "pactl"


def test_no_backend_logs_warning_once_and_returns_false() -> None:
    """Sem backend: retorna False e loga warning apenas na primeira chamada."""
    with patch("shutil.which", return_value=None):
        clock = _FakeClock(start=1.0)
        ctrl = AudioControl(clock=clock)

        # Primeira chamada — warning deve ser emitido.
        result1 = ctrl.toggle_default_source_mute()
        assert result1 is False
        assert ctrl._warned_no_backend is True

        # Segunda chamada (apos debounce passar) — warning não deve repetir.
        clock.advance(DEBOUNCE_SEC + 0.01)
        result2 = ctrl.toggle_default_source_mute()
        assert result2 is False


# ---------------------------------------------------------------------------
# 2. Subprocess correto por backend
# ---------------------------------------------------------------------------


def test_toggle_calls_wpctl_set_mute_without_shell() -> None:
    """toggle_default_source_mute() com backend wpctl chama subprocess sem shell=True."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/wpctl" if cmd == "wpctl" else None

    muted_proc = _make_proc(stdout="Volume: 1.00 [MUTED]")
    toggle_proc = _make_proc(stdout="")

    with patch("shutil.which", side_effect=_which), patch(
        "subprocess.run", side_effect=[toggle_proc, muted_proc]
    ) as mock_run:
        ctrl = AudioControl()
        result = ctrl.toggle_default_source_mute()

    # Verifica que o primeiro call e o toggle e que Não usa shell=True.
    first_call = mock_run.call_args_list[0]
    assert first_call[0][0] == ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]
    assert first_call[1].get("shell", False) is False

    # Segundo call e o get-volume para ler novo estado.
    second_call = mock_run.call_args_list[1]
    assert second_call[0][0] == ["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]
    assert second_call[1].get("shell", False) is False

    assert result is True


def test_toggle_calls_pactl_set_source_mute_without_shell() -> None:
    """toggle_default_source_mute() com backend pactl chama subprocess sem shell=True."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/pactl" if cmd == "pactl" else None

    muted_proc = _make_proc(stdout="Mute: yes\n")
    toggle_proc = _make_proc(stdout="")

    with patch("shutil.which", side_effect=_which), patch(
        "subprocess.run", side_effect=[toggle_proc, muted_proc]
    ) as mock_run:
        ctrl = AudioControl()
        result = ctrl.toggle_default_source_mute()

    first_call = mock_run.call_args_list[0]
    assert first_call[0][0] == ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"]
    assert first_call[1].get("shell", False) is False

    second_call = mock_run.call_args_list[1]
    assert second_call[0][0] == ["pactl", "get-source-mute", "@DEFAULT_SOURCE@"]
    assert second_call[1].get("shell", False) is False

    assert result is True


# ---------------------------------------------------------------------------
# 3. Parse do estado de mute
# ---------------------------------------------------------------------------


def test_parse_muted_state_from_wpctl_get_volume() -> None:
    """_query_wpctl_muted() retorna True se '[MUTED]' aparece na saida."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/wpctl" if cmd == "wpctl" else None

    with patch("shutil.which", side_effect=_which):
        ctrl = AudioControl()

        # Estado mutado.
        with patch("subprocess.run", return_value=_make_proc(stdout="Volume: 0.50 [MUTED]")):
            assert ctrl._query_wpctl_muted() is True

        # Estado ativo (sem [MUTED]).
        with patch("subprocess.run", return_value=_make_proc(stdout="Volume: 1.00")):
            assert ctrl._query_wpctl_muted() is False


def test_parse_muted_state_from_pactl_get_source_mute() -> None:
    """_query_pactl_muted() retorna True se 'yes' aparece na saida (case-insensitive)."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/pactl" if cmd == "pactl" else None

    with patch("shutil.which", side_effect=_which):
        ctrl = AudioControl()

        # Estado mutado.
        with patch("subprocess.run", return_value=_make_proc(stdout="Mute: yes\n")):
            assert ctrl._query_pactl_muted() is True

        # Estado ativo.
        with patch("subprocess.run", return_value=_make_proc(stdout="Mute: no\n")):
            assert ctrl._query_pactl_muted() is False


# ---------------------------------------------------------------------------
# 4. Debounce
# ---------------------------------------------------------------------------


def test_debounce_200ms_returns_cached_state() -> None:
    """Duas chamadas dentro de 200ms: apenas a primeira executa subprocess.

    Cenarios:
    1. clock=1.0 -> primeira chamada executa (ultima_chamada=-1.2, diff=2.2 > 0.2).
    2. clock=1.1 (diff=0.1 < 0.2) -> debounce ativo, retorna estado cacheado.
    3. clock=2.0 (diff=0.9 > 0.2) -> nova execução.
    """

    def _which(cmd: str) -> str | None:
        return "/usr/bin/wpctl" if cmd == "wpctl" else None

    toggle_proc = _make_proc(stdout="")
    muted_proc = _make_proc(stdout="Volume: 1.00 [MUTED]")
    toggle_proc2 = _make_proc(stdout="")
    active_proc = _make_proc(stdout="Volume: 1.00")

    clock = _FakeClock(start=1.0)

    with patch("shutil.which", side_effect=_which), patch(
        "subprocess.run",
        side_effect=[toggle_proc, muted_proc, toggle_proc2, active_proc],
    ) as mock_run:
        ctrl = AudioControl(clock=clock)

        # Primeira chamada em t=1.0: executa (diff = 1.0 - (-1.2) = 2.2 > 0.2).
        result1 = ctrl.toggle_default_source_mute()
        assert result1 is True
        assert mock_run.call_count == 2  # toggle + get-volume

        # Segunda chamada em t=1.1: debounce ativo (diff = 1.1 - 1.0 = 0.1 < 0.2).
        clock.advance(DEBOUNCE_SEC - 0.1)
        result2 = ctrl.toggle_default_source_mute()
        assert result2 is True  # retorna estado cacheado
        assert mock_run.call_count == 2  # nenhuma chamada adicional

        # Terceira chamada em t=2.0: debounce expirado (diff = 2.0 - 1.0 = 1.0 > 0.2).
        clock.advance(DEBOUNCE_SEC + 0.8)
        result3 = ctrl.toggle_default_source_mute()
        assert result3 is False  # novo estado: não mutado
        assert mock_run.call_count == 4  # mais toggle + get-volume


# ---------------------------------------------------------------------------
# 5. Falhas graciosas de subprocess
# ---------------------------------------------------------------------------


def test_subprocess_timeout_is_graceful() -> None:
    """TimeoutExpired não propaga: loga warning e retorna último estado."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/wpctl" if cmd == "wpctl" else None

    with patch("shutil.which", side_effect=_which), patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="wpctl", timeout=2.0),
    ):
        ctrl = AudioControl()
        result = ctrl.toggle_default_source_mute()
    # Não levanta; retorna último estado conhecido (False no primeiro erro).
    assert result is False


def test_subprocess_nonzero_exit_is_graceful() -> None:
    """Exit != 0 não levanta: _run retorna o proc; _query_* parseia normalmente."""

    def _which(cmd: str) -> str | None:
        return "/usr/bin/pactl" if cmd == "pactl" else None

    # Simula saida com codigo != 0 mas stdout legivel.
    toggle_proc = _make_proc(stdout="", returncode=1)
    # A query retorna saida vazia (exit != 0 mas check=False).
    query_proc = _make_proc(stdout="Mute: no\n", returncode=1)

    with patch("shutil.which", side_effect=_which), patch(
        "subprocess.run", side_effect=[toggle_proc, query_proc]
    ):
        ctrl = AudioControl()
        result = ctrl.toggle_default_source_mute()

    # Não levanta; retorna estado parseado da query (False = nao mutado).
    assert result is False
