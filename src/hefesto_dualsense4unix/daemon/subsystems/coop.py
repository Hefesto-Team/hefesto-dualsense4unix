"""Subsystem Co-op local — N controles = N jogadores (FEAT-DSX-COOP-LOCAL-01).

O multi-controle base (FEAT-DSX-MULTI-CONTROLLER-01) é "N controles, 1 player":
o OUTPUT é broadcast e o INPUT vem só do primário. Isso serve para reserva/troca
de controle, mas NÃO para co-op (2 pessoas) — os dois viram o mesmo player.

Este subsystem adiciona, SEM tocar no caminho do primário (P1), uma camada de
"jogadores secundários": para cada controle FÍSICO além do primário, cria um
leitor evdev dedicado (com grab) e um gamepad virtual próprio (P2, P3, …). O
poll loop, depois de despachar o P1, chama `forward_all()` para repassar cada
secundário ao SEU gamepad virtual. Assim o jogo enxerga N devices distintos =
co-op local de verdade.

Pré-requisitos (gate em `should_be_active`):
  - `config.coop_enabled` ligado (default OFF — preserva o modo "1 player");
  - emulação de gamepad ativa (o P1 já é um gamepad virtual; os secundários
    seguem a mesma máscara/flavor);
  - 2+ controles físicos conectados.

Fora de escopo (fase futura): rumble do jogo por jogador (force-feedback nem é
roteado para o P1 hoje) e player-LED por índice (mapear cada controle ao seu
evdev por MAC).
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

logger = get_logger(__name__)


@dataclass
class _SecondaryPlayer:
    """Um jogador secundário: o evdev de um controle físico + seu gamepad virtual."""

    evdev_path: str
    reader: EvdevReader
    vpad: UinputGamepad


class CoopManager:
    """Gerencia os jogadores secundários (P2+) do co-op local.

    Aditivo e idempotente: `sync()` reconcilia o conjunto de secundários com os
    controles fisicamente plugados (hotplug-safe); `forward_all()` repassa cada
    um ao seu gamepad virtual; `disable()`/`stop_all()` desmontam tudo (solta o
    grab e fecha os uinput). Nunca propaga exceção para não derrubar o poll loop.
    """

    def __init__(self, daemon: DaemonProtocol) -> None:
        self._daemon = daemon
        self._players: dict[str, _SecondaryPlayer] = {}

    # -- estado / gate --------------------------------------------------

    def should_be_active(self) -> bool:
        """True se o co-op deve estar ativo agora (flag + gamepad + 2+ controles)."""
        cfg = getattr(self._daemon, "config", None)
        if not bool(getattr(cfg, "coop_enabled", False)):
            return False
        # co-op exige o caminho de gamepad virtual ligado (o P1 já é um vpad).
        return getattr(self._daemon, "_gamepad_device", None) is not None

    def player_count(self) -> int:
        """Total de jogadores ativos (P1 + secundários)."""
        return 1 + len(self._players)

    def _primary_evdev_path(self) -> str | None:
        ev = getattr(getattr(self._daemon, "controller", None), "_evdev", None)
        path = getattr(ev, "_device_path", None)
        return str(path) if path is not None else None

    # -- reconciliação --------------------------------------------------

    def sync(self) -> None:
        """Reconcilia os secundários com os controles plugados. Idempotente."""
        if not self.should_be_active():
            if self._players:
                self.disable()
            return

        from hefesto_dualsense4unix.core.evdev_reader import find_all_dualsense_evdevs

        primary = self._primary_evdev_path()
        want = [str(p) for p in find_all_dualsense_evdevs() if str(p) != primary]

        # hotplug-OUT: derruba secundários cujo evdev sumiu.
        for key in [k for k in self._players if k not in want]:
            self._teardown_player(key)

        # hotplug-IN: cria secundários novos.
        flavor = self._flavor()
        for path in want:
            if path not in self._players:
                self._spawn_player(path, flavor)

    def _flavor(self) -> str:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

        cfg = getattr(self._daemon, "config", None)
        return normalize_flavor(getattr(cfg, "gamepad_flavor", None))

    def _spawn_player(self, path: str, flavor: str) -> None:
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
        from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

        reader = EvdevReader(device_path=Path(path))
        if not reader.start():
            logger.debug("coop_player_reader_unavailable", evdev=path)
            return
        # Grab: o jogo deve ver SÓ o gamepad virtual deste jogador, não o cru.
        reader.set_grab(True)
        vpad = UinputGamepad.for_flavor(flavor)
        if not vpad.start():
            logger.warning("coop_player_vpad_failed", evdev=path)
            with contextlib.suppress(Exception):
                reader.set_grab(False)
            reader.stop()
            return
        self._players[path] = _SecondaryPlayer(evdev_path=path, reader=reader, vpad=vpad)
        logger.info("coop_player_added", evdev=path, players=self.player_count())

    def _teardown_player(self, key: str) -> None:
        player = self._players.pop(key, None)
        if player is None:
            return
        with contextlib.suppress(Exception):
            player.reader.set_grab(False)
        with contextlib.suppress(Exception):
            player.reader.stop()
        with contextlib.suppress(Exception):
            player.vpad.stop()
        logger.info("coop_player_removed", evdev=key, players=self.player_count())

    # -- por tick -------------------------------------------------------

    def forward_all(self) -> None:
        """Repassa cada secundário ao seu gamepad virtual. Chamado por tick."""
        for player in self._players.values():
            try:
                snap = player.reader.snapshot()
                player.vpad.forward_analog(
                    lx=snap.lx,
                    ly=snap.ly,
                    rx=snap.rx,
                    ry=snap.ry,
                    l2=snap.l2_raw,
                    r2=snap.r2_raw,
                )
                player.vpad.forward_buttons(snap.buttons_pressed)
            except Exception as exc:  # nunca derruba o poll loop
                logger.warning("coop_forward_failed", evdev=player.evdev_path, err=str(exc))

    # -- ciclo de vida --------------------------------------------------

    def disable(self) -> None:
        """Desmonta todos os secundários (solta grab, fecha uinput). Idempotente."""
        for key in list(self._players):
            self._teardown_player(key)

    # Alias semântico para o shutdown do daemon.
    stop_all = disable


def get_coop_manager(daemon: DaemonProtocol) -> CoopManager:
    """Retorna o `CoopManager` do daemon, criando-o sob demanda (lazy)."""
    manager = getattr(daemon, "_coop_manager", None)
    if manager is None:
        manager = CoopManager(daemon)
        daemon._coop_manager = manager
    return manager


__all__ = ["CoopManager", "get_coop_manager"]
