"""Subsystem opcional: microfone do DualSense por Bluetooth (BT-MIC-01).

Embrulha `integrations/dualsense_bt_audio.py` no contrato `Subsystem` do
daemon (`start`/`stop`/`is_enabled`). É fino de propósito — toda a lógica de
protocolo, Opus e PipeWire mora no módulo de integração, que roda igual pelo
CLI (`mic bt`), pela GUI ou por aqui.

**Por que ele nasce DESLIGADO.** Ligar o mic significa mandar o controle
capturar áudio o tempo todo, e isso tem dois preços que só a usuária pode
aceitar:

1. **Privacidade.** Um microfone que liga sozinho quando o daemon sobe é
   inaceitável, por melhor que seja a intenção. A ponte é um gesto explícito.
2. **Banda do rádio.** Medido ao vivo (2026-07-25, DualSense por BT nesta
   máquina): com o mic desligado o controle entrega ~260 reports de input/s;
   com o mic ligado a MESMA banda passa a carregar ~106 quadros de áudio/s e
   os reports de input caem para ~170/s. O total de pacotes fica igual — o
   áudio não é de graça, ele divide o link. 170 Hz continua muito acima do
   poll de 60 Hz do daemon, mas quem usa gyro aiming perde resolução de
   integração (o espelho de motion mira 250 Hz). Trade-off da usuária, não do
   programa.

Gate: `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` (ou `config.bt_mic_enabled`, se algum
dia virar campo do `DaemonConfig` — lemos por `getattr` para não exigir que
ele exista).

O laço de reconciliação vive num `threading.Thread` e DORME num `Event` entre
as varreduras — nunca um laço apertado, nunca um `sleep` de polling de dados.
O áudio em si não passa por aqui: cada ponte tem a própria thread bloqueada no
`read()` do hidraw (o áudio é o relógio).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: Opt-in explícito. Sem isto o subsystem nem importa a libopus.
ENV_HABILITA = "HEFESTO_DUALSENSE4UNIX_BT_MIC"

#: Cadência da varredura de hotplug (sysfs). Ver o cabeçalho: não é polling de
#: áudio, é só "apareceu/sumiu controle em BT?".
RECONCILIA_S = 5.0

_VALORES_LIGADOS = ("1", "true", "yes", "on")


def habilitado_por_env(ambiente: dict[str, str] | None = None) -> bool:
    """True se a env de opt-in está ligada (função pura, testável)."""
    env = ambiente if ambiente is not None else os.environ
    return env.get(ENV_HABILITA, "").strip().lower() in _VALORES_LIGADOS


class BtMicSubsystem:
    """Mantém uma ponte de microfone por DualSense conectado em Bluetooth."""

    name = "bt_mic"

    def __init__(self, *, gerenciador: Any = None) -> None:
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Opt-in por env OU por campo de config (se ele existir um dia)."""
        return bool(getattr(config, "bt_mic_enabled", False)) or habilitado_por_env()

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a criação do gerenciador é barata e a
        varredura do sysfs (mais o `pactl` do load-module) roda na thread.
        """
        del ctx  # a ponte descobre os controles pelo sysfs, não pelo contexto
        if self._thread is not None and self._thread.is_alive():
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            GerenciadorMicBluetooth,
        )

        self._gerenciador = self._gerenciador_injetado or GerenciadorMicBluetooth()
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-btmic-sup", daemon=True
        )
        self._thread.start()
        logger.info("bt_mic_subsystem_iniciado")

    async def stop(self) -> None:
        """Derruba as pontes (o que DESLIGA o mic em cada controle). Idempotente.

        O `join` sai do event loop por `to_thread`: ele espera até 2 s por
        varredura em curso, e segurar o loop do daemon nesse tempo atrasaria o
        shutdown inteiro.
        """
        self._parar.set()
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
        self._gerenciador = None
        logger.info("bt_mic_subsystem_parado")

    # -- laço -------------------------------------------------------------

    def _loop(self) -> None:
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        while not self._parar.is_set():
            try:
                gerenciador.reconciliar()
            except Exception as exc:  # nunca derruba a thread
                logger.debug("bt_mic_reconciliacao_falhou", err=str(exc))
            if gerenciador.dormir(RECONCILIA_S):
                return


__all__ = ["ENV_HABILITA", "RECONCILIA_S", "BtMicSubsystem", "habilitado_por_env"]
