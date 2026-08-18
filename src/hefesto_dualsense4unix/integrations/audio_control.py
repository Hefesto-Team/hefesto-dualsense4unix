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

from hefesto_dualsense4unix.utils.logging_config import get_logger

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

    def fonte_padrao_e_o_controle(self) -> bool:
        """True quando o microfone padrão do sistema É o do DualSense.

        BT-E-VPAD-01, defeito 1. **Medido em 01/08/2026**: com o controle no
        Bluetooth, `pactl list short cards | grep -i dualsense` devolve ZERO —
        no BT o DualSense **não tem placa de som nenhuma**. O áudio vai dentro
        dos reports HID e depende da ponte deste projeto, que é opt-in.

        Sem esta pergunta, o botão do microfone do controle alternava o mudo
        da FONTE PADRÃO, que no Bluetooth é outra coisa: nesta máquina, o
        microfone da placa-mãe. O log de três toques dela mostra a assinatura
        do defeito — sempre o mesmo resultado, porque não era o microfone do
        controle que estava sendo alternado:

            20:15:54  mic_hotkey_toggle  muted=True
            20:16:31  mic_hotkey_toggle  muted=True
            20:16:43  mic_hotkey_toggle  muted=True

        A comparação é por SUBSTRING do nome da fonte padrão, e não por
        enumeração de placas: é uma pergunta só, na cadência de um toque de
        botão, e o nome do node do PipeWire para o controle carrega
        "DualSense" em qualquer um dos dois backends.

        Em caso de dúvida devolve **False** — e o chamador não mexe em nada.
        É a resposta segura: não fazer nada é sempre melhor que mutar o
        microfone errado.
        """
        backend = self._ensure_backend()
        try:
            if backend == "wpctl":
                # O `wpctl inspect` do source padrão traz `node.name` e
                # `node.description`; o do controle carrega "DualSense".
                saida = self._run(
                    ["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"]
                ).stdout
            elif backend == "pactl":
                saida = self._run(["pactl", "get-default-source"]).stdout
            else:
                return False
        except Exception as exc:
            logger.warning("audio_fonte_padrao_falhou", err=str(exc))
            return False
        return "dualsense" in (saida or "").lower()

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
