"""Subsystem DSU: o servidor que leva o toque e o movimento ao emulador.

O servidor (``daemon/servidor_dsu.py``) mora numa thread e só LÊ. Quem monta a
tabela de slots e resolve o hub de sensores é a tarefa deste módulo, no laço do
daemon, a no máximo 10 Hz: o ``resolve_player_numbers`` e o
``_garantir_sensor_hub`` não são seguros fora do laço.

Slot é o número que o jogo vê menos um, o mesmo que o ``Controle N`` da casa.
Controle sem número («Controlar o PC») não tem slot, e o MAC que o emulador vê é
o do vpad (``vpad_mac``), nunca o do físico.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

from hefesto_dualsense4unix.daemon.servidor_dsu import ServidorDsu, SlotDsu
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

INTERVALO_DA_TABELA_S: Final = 0.1
SLOTS: Final = 4


def montar_a_tabela(
    daemon: Any, entradas: Sequence[Mapping[str, object]] | None = None
) -> dict[int, SlotDsu]:
    """Slot (0..3) -> controle, pelos números que o jogo vê. Roda no laço.

    Co-op desligado: o ``resolve_player_numbers`` devolve 1 para todos, e o slot
    0 fica com o primário; os outros ficam sem slot.
    """
    from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers
    from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

    if entradas is None:
        descrever = getattr(daemon.controller, "describe_controllers", None)
        entradas = descrever() if callable(descrever) else []
    numeros = resolve_player_numbers(daemon, entradas)
    tabela: dict[int, SlotDsu] = {}
    for entrada, numero in zip(entradas, numeros, strict=False):
        uniq = entrada.get("uniq")
        if not entrada.get("connected") or not isinstance(uniq, str) or not uniq:
            continue
        if numero is None or not 1 <= numero <= SLOTS:
            continue
        slot = numero - 1
        if slot in tabela and not entrada.get("is_primary"):
            continue
        tabela[slot] = SlotDsu(uniq=uniq, mac=vpad_mac(uniq, numero))
    return tabela


def hub_do_laco(daemon: Any) -> Any:
    """O ``SensorHub`` da sessão (o mesmo do IPC), ou o hub ausente."""
    from hefesto_dualsense4unix.daemon.lifecycle import HUB_AUSENTE

    garantir = getattr(daemon, "_garantir_sensor_hub", None)
    if not callable(garantir):
        return HUB_AUSENTE
    return garantir()


def _publicar_uma_vez(daemon: Any, servidor: ServidorDsu) -> None:
    try:
        servidor.publicar(montar_a_tabela(daemon), hub_do_laco(daemon))
    except Exception as exc:
        logger.debug("dsu_tabela_falhou", err=str(exc))


async def _manter_a_tabela(daemon: Any, servidor: ServidorDsu) -> None:
    """Publica (tabela, hub) no servidor a cada ``INTERVALO_DA_TABELA_S``."""
    while True:
        _publicar_uma_vez(daemon, servidor)
        await asyncio.sleep(INTERVALO_DA_TABELA_S)


def _porta_ocupada(porta: int, exc: OSError) -> OSError:
    return OSError(
        f"a porta UDP {porta} do servidor DSU já tem dono ({exc.strerror}); "
        'troque-a em "servidor_dsu" do maquina.json, ou veja quem a usa com '
        f"`ss -ulpn 'sport = :{porta}'`"
    )


async def start_dsu(daemon: DaemonProtocol) -> None:
    """Abre a porta e liga a tarefa da tabela. Porta ocupada levanta ``OSError``."""
    porta = int(daemon.config.dsu_port)
    servidor = ServidorDsu(porta=porta, store=daemon.store)
    try:
        servidor.iniciar()
    except OSError as exc:
        raise _porta_ocupada(porta, exc) from exc
    daemon._servidor_dsu = servidor
    daemon._tarefa_dsu = asyncio.create_task(_manter_a_tabela(daemon, servidor), name="dsu_tabela")


async def stop_dsu(daemon: DaemonProtocol) -> None:
    """Para a tarefa da tabela e o servidor (com o pacote neutro). Idempotente."""
    tarefa, daemon._tarefa_dsu = getattr(daemon, "_tarefa_dsu", None), None
    if tarefa is not None:
        tarefa.cancel()
        try:
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa
        except Exception as exc:
            logger.debug("dsu_tarefa_da_tabela_falhou", err=str(exc))
    servidor, daemon._servidor_dsu = daemon._servidor_dsu, None
    if servidor is not None:
        try:
            await asyncio.to_thread(servidor.parar)
        except Exception as exc:
            logger.warning("dsu_parar_falhou", err=str(exc))


class DsuSubsystem:
    """Subsystem que gerencia o servidor DSU do daemon."""

    name = "dsu"
    _daemon: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        daemon = getattr(ctx, "daemon", None)
        if daemon is None:
            logger.warning("dsu_subsystem_sem_daemon")
            return
        self._daemon = daemon
        await start_dsu(daemon)

    async def stop(self) -> None:
        if self._daemon is not None:
            await stop_dsu(self._daemon)
            self._daemon = None

    def is_enabled(self, config: DaemonConfig) -> bool:
        return bool(config.dsu_enabled)


__all__ = [
    "DsuSubsystem",
    "hub_do_laco",
    "montar_a_tabela",
    "start_dsu",
    "stop_dsu",
]
