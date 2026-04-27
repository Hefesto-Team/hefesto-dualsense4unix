"""Auto-switch de perfil conforme janela X11 ativa.

Poll a 2Hz (`poll_interval_sec=0.5`), debounce de 500ms para evitar flicker
em alt-tab, aplica via ProfileManager.activate quando escolha muda.

Desligável via env `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1` (usado pelo unit headless,
V2-4 / Patch 8).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 0.5
DEFAULT_DEBOUNCE_SEC = 0.5


WindowReader = Callable[[], dict[str, Any]]


@dataclass
class AutoSwitcher:
    manager: ProfileManager
    window_reader: WindowReader
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC
    debounce_sec: float = DEFAULT_DEBOUNCE_SEC
    # BUG-MOUSE-TRIGGERS-01: opcional para permitir testes legados que
    # instanciam AutoSwitcher sem store. Em produção, o Daemon injeta o
    # store compartilhado para respeitar override de trigger manual.
    store: StateStore | None = None

    _last_candidate: str | None = None
    _candidate_since: float = 0.0
    _current_profile: str | None = None
    _stop_event: asyncio.Event | None = None
    _task: asyncio.Task[Any] | None = None

    def disabled(self) -> bool:
        return os.environ.get("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT") == "1"

    async def run(self) -> None:
        if self.disabled():
            logger.info("autoswitch_disabled_via_env")
            return

        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        while not self._stop_event.is_set():
            try:
                info = self.window_reader()
            except Exception as exc:
                logger.warning("autoswitch_window_read_failed", err=str(exc))
                info = {}

            profile = self.manager.select_for_window(info)
            candidate = profile.name if profile else None

            now = loop.time()
            if candidate != self._last_candidate:
                self._last_candidate = candidate
                self._candidate_since = now

            stable = now - self._candidate_since >= self.debounce_sec
            if stable and candidate and candidate != self._current_profile:
                self._activate(candidate, info)

            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval_sec
                )

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="autoswitch")
        return self._task

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _activate(self, name: str, info: dict[str, Any]) -> None:
        # BUG-MOUSE-TRIGGERS-01: se o usuário tem um trigger manual aplicado
        # via aba Gatilhos, autoswitch suspende até o override ser limpo por
        # trigger.reset ou profile.switch explícito. Sem isso, ao ligar a aba
        # Mouse (que move o cursor e muda o foco de janela), o autoswitch
        # reaplicaria o fallback e zeraria o trigger recém-aplicado.
        if self.store is not None and self.store.manual_trigger_active:
            logger.info(
                "autoswitch_suppressed_by_manual_override",
                candidate=name,
                wm_class=info.get("wm_class", ""),
            )
            return
        from_profile = self._current_profile
        try:
            self.manager.activate(name)
        except Exception as exc:
            logger.warning("autoswitch_activate_failed", name=name, err=str(exc))
            return
        self._current_profile = name
        logger.info(
            "profile_autoswitch",
            from_=from_profile,
            to=name,
            wm_class=info.get("wm_class", ""),
            wm_name=info.get("wm_name", ""),
        )


__all__ = [
    "DEFAULT_DEBOUNCE_SEC",
    "DEFAULT_POLL_INTERVAL_SEC",
    "AutoSwitcher",
    "WindowReader",
]
