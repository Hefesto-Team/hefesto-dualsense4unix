"""Controle de mute do microfone padrão do sistema via wpctl ou pactl.

Auto-detecta o backend disponivel (wpctl para PipeWire/WirePlumber,
pactl para PulseAudio legado). Nunca levanta excecao: falhas de
subprocess viram warning + retorno do último estado conhecido.

Regras:
- Nunca usa shell=True (invariante do projeto).
- Debounce 200ms com clock injetavel para testes.
- Logging via structlog (get_logger).
"""
from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Literal

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

DEBOUNCE_SEC = 0.2
SUBPROCESS_TIMEOUT_SEC = 2.0
Backend = Literal["wpctl", "pactl", "none"]


class AudioControl:
    """Controla mute do microfone padrão do sistema via wpctl ou pactl.

    Auto-detecta backend no primeiro uso. Não levanta: falhas viram
    warning + retorno do último estado conhecido.

    Args:
        clock: função que retorna tempo monotonic em segundos. Injetavel
               para testes. Default: time.monotonic.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock: Callable[[], float] = clock or time.monotonic
        self._backend: Backend | None = None
        # Inicializado suficientemente negativo para que a primeira chamada
        # nunca seja bloqueada pelo debounce, independente do clock injetado.
        self._last_call_at: float = -(DEBOUNCE_SEC + 1.0)
        self._last_known_muted: bool = False
        self._warned_no_backend: bool = False

    # ------------------------------------------------------------------
    # Deteccao de backend
    # ------------------------------------------------------------------

    def _detect_backend(self) -> Backend:
        """Detecta qual utilitario de audio esta disponivel no PATH."""
        if shutil.which("wpctl"):
            return "wpctl"
        if shutil.which("pactl"):
            return "pactl"
        return "none"

    def _ensure_backend(self) -> Backend:
        """Detecta e cacheia o backend na primeira chamada."""
        if self._backend is None:
            self._backend = self._detect_backend()
            logger.info("audio_backend_detectado", backend=self._backend)
        return self._backend

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def toggle_default_source_mute(self) -> bool:
        """Alterna mute do microfone padrão do sistema.

        Aplica debounce de 200ms: chamadas consecutivas dentro desse
        intervalo ignoram o subprocess e retornam o último estado.

        Returns:
            True se o microfone agora esta mutado; False se esta ativo.
        """
        now = self._clock()
        if (now - self._last_call_at) < DEBOUNCE_SEC:
            logger.debug("audio_toggle_debounced")
            return self._last_known_muted
        self._last_call_at = now

        backend = self._ensure_backend()
        if backend == "none":
            if not self._warned_no_backend:
                logger.warning("audio_backend_indisponivel")
                self._warned_no_backend = True
            return False

        try:
            if backend == "wpctl":
                self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
                self._last_known_muted = self._query_wpctl_muted()
            else:
                self._run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"])
                self._last_known_muted = self._query_pactl_muted()
        except Exception as exc:
            logger.warning("audio_toggle_falhou", backend=backend, err=str(exc))
        return self._last_known_muted

    # ------------------------------------------------------------------
    # Métodos internos de subprocess
    # ------------------------------------------------------------------

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Executa comando como lista de args, sem shell=True."""
        return subprocess.run(
            argv,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            capture_output=True,
            text=True,
        )

    def _query_wpctl_muted(self) -> bool:
        """Consulta estado de mute via wpctl get-volume.

        O wpctl inclui '[MUTED]' na saida quando o source esta mutado.
        """
        result = self._run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"])
        return "[MUTED]" in (result.stdout or "")

    def _query_pactl_muted(self) -> bool:
        """Consulta estado de mute via pactl get-source-mute.

        A saida padrão e 'Mute: yes' ou 'Mute: no'.
        """
        result = self._run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"])
        return "yes" in (result.stdout or "").lower()


__all__ = ["DEBOUNCE_SEC", "SUBPROCESS_TIMEOUT_SEC", "AudioControl", "Backend"]
