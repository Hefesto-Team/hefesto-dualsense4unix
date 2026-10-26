"""A lista única de subsystems do daemon: o que sobe, quando, e em que ordem para.

``SUBSYSTEM_REGISTRY`` é a ÚNICA fonte. ``Daemon.run()`` percorre a lista na ordem
em que ela está escrita (``subir``) e ``connection.shutdown`` a percorre pela ordem
de parada declarada em cada entrada (``parar``). Ligar um subsystem novo é
**acrescentar uma entrada aqui**: não há mais um ``_safe_start`` no ``run()`` nem um
``_stop_*`` no ``shutdown()`` para esquecer (foi assim que o ``BtMicSubsystem`` e o
``AltoFalanteSubsystem`` nasceram órfãos). A régua é
``tests/unit/test_o_subsystem_sobe_e_desce_por_uma_lista_so.py``.

Cada ``Passo`` declara o nome, a condição (``quando``, sobre a ``DaemonConfig``;
``None`` é «sempre»), a partida, a parada e a posição dela (``parar_em``). A ordem de
parada NÃO é a de partida, e é declarada de propósito: o som e o microfone caem antes
do IPC (a leitura do sysfs e do servidor de som termina antes de a porta fechar), e o
controle é a última coisa a ir (``soltar_o_controle``). O passo sem ``partida`` só
para (o co-op, o broker, as tarefas, o controle).

O ``AltoFalanteSubsystem`` ficou fora até 10/09/2026 (SOM-FIADO-01) porque publicava
um ``module-null-sink`` por controle sem ``module-loopback``: um sink mudo por
DualSense na lista de som. Hoje o ``GerenciadorDeNosDeSom.reconciliar`` guarda o par
(sem rota, sem nó), e a régua que mede isso no PRODUTO é
``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py``.
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
)
from hefesto_dualsense4unix.daemon.subsystems.base import Subsystem
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem
from hefesto_dualsense4unix.daemon.subsystems.conexoes import ConexoesSubsystem
from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem
from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig

logger = get_logger(__name__)

_TETO_DA_PARADA_DO_DSU_S = 5.0
_TETO_DA_PARADA_DO_SERVIDOR_S = 2.0


@dataclass(frozen=True)
class Passo:
    """Uma linha da lista: como o subsystem sobe, quando, e como e quando para.

    A partida e a condição são tipadas sobre o ``Daemon`` e a ``DaemonConfig`` de
    verdade: o mypy confere o ``d._start_*`` de cada ``lambda`` contra o ``Daemon``.
    """

    nome: str
    partida: Callable[[Daemon], Any] | None = None
    quando: Callable[[DaemonConfig], bool] | None = None
    parada: Callable[[Daemon], Any] | None = None
    parar_em: int | None = None
    depois_do_controle: bool = False
    essencial: Callable[[Daemon, Exception], Exception] | None = None


def _ipc_indisponivel(daemon: Any, exc: Exception) -> Exception:
    """O IPC é essencial: sem socket a janela, a bandeja e a CLI dizem «offline» com o
    processo no ar. A falha encerra o ``run()``; o systemd tenta de novo e, no limite,
    o ``OnFailure=`` devolve o controle."""
    from hefesto_dualsense4unix.daemon.lifecycle import IpcIndisponivel

    return IpcIndisponivel(daemon._caminho_do_socket(), exc)


def _hotkey(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_hotkey_manager

    return start_hotkey_manager(daemon)


def _mic_do_jogo(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_mic_do_jogo

    return start_mic_do_jogo(daemon)


def _mic_hotkey(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_mic_hotkey

    return start_mic_hotkey(daemon)


def _luz_do_mic(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import start_luz_do_mic

    return start_luz_do_mic(daemon)


def _tato_vivo(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import start_tato_vivo

    return start_tato_vivo(daemon)


def _eventos_do_perfil(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.eventos_do_perfil import (
        start_eventos_do_perfil,
    )

    return start_eventos_do_perfil(daemon)


def _luz_animada(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.luz_animada import start_luz_animada

    return start_luz_animada(daemon)


def _telemetria_do_jogo(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.telemetria_do_jogo import (
        start_telemetria_do_jogo,
    )

    return start_telemetria_do_jogo(daemon)


def _ouvinte_do_som(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems.ouvinte_do_som import (
        start_ouvinte_do_som,
    )

    return start_ouvinte_do_som(daemon)


async def _chamar_se_existe(daemon: Any, verbo: str) -> None:
    """Chama ``daemon.<verbo>()`` se o daemon o tem (o dublê de teste pode não ter)."""
    parar = getattr(daemon, verbo, None)
    if callable(parar):
        resultado = parar()
        if inspect.isawaitable(resultado):
            await resultado


async def _parar_mods(daemon: Any) -> None:
    await _chamar_se_existe(daemon, "_stop_mods")


async def _parar_bt_mic(daemon: Any) -> None:
    if getattr(daemon, "_bt_mic_subsystem", None) is not None:
        await _chamar_se_existe(daemon, "_stop_bt_mic")


async def _parar_alto_falante(daemon: Any) -> None:
    if getattr(daemon, "_alto_falante_subsystem", None) is not None:
        await _chamar_se_existe(daemon, "_stop_alto_falante")


async def _parar_central_do_radio(daemon: Any) -> None:
    central = getattr(daemon, "_central_do_radio", None)
    if central is not None:
        await asyncio.to_thread(central.fechar)


async def _parar_conexoes(daemon: Any) -> None:
    if getattr(daemon, "_conexoes_subsystem", None) is not None:
        await _chamar_se_existe(daemon, "_stop_conexoes")


async def _parar_plugins(daemon: Any) -> None:
    plugins = getattr(daemon, "_plugins_subsystem", None)
    if plugins is not None:
        try:
            await plugins.stop()
        finally:
            daemon._plugins_subsystem = None


async def _parar_metrics(daemon: Any) -> None:
    if getattr(daemon, "_metrics_subsystem", None) is not None:
        await _chamar_se_existe(daemon, "_stop_metrics")


async def _parar_hotkey(daemon: Any) -> None:
    daemon._hotkey_manager = None
    daemon._audio = None


async def _parar_coop(daemon: Any) -> None:
    gerente = getattr(daemon, "_coop_manager", None)
    if gerente is not None:
        try:
            gerente.stop_all()
        finally:
            daemon._coop_manager = None


async def _parar_mouse(daemon: Any) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.mouse import fechar_as_teclas_do_analogico

    fechar_as_teclas_do_analogico(daemon)
    dispositivo = getattr(daemon, "_mouse_device", None)
    if dispositivo is not None:
        try:
            dispositivo.stop()
        finally:
            daemon._mouse_device = None


async def _parar_gamepad(daemon: Any) -> None:
    if getattr(daemon, "_gamepad_device", None) is not None:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            stop_gamepad_emulation,
        )

        stop_gamepad_emulation(daemon, persist=False)


async def _parar_o_broker(daemon: Any) -> None:
    """O executor e, DEPOIS dele, o cliente. A falha de um não pula o outro: o ``finally``
    solta os dois, e a que sobe vira o aviso ``subsystem_parada_falhou`` do ``parar``."""
    executor = getattr(daemon, "_hidraw_broker_executor", None)
    cliente = getattr(daemon, "_hidraw_broker_client", None)
    try:
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            finally:
                daemon._hidraw_broker_executor = None
    finally:
        if cliente is not None:
            try:
                cliente.close()
            finally:
                daemon._hidraw_broker_client = None


async def _parar_teclado(daemon: Any) -> None:
    """O device do teclado e, DEPOIS dele, o teclado na tela.

    ``osk.close()`` DIRETO, e não ``stop_keyboard_emulation``: aquele derruba o
    ``virtual_token_callback`` do device, que aponta para ``osk.dispatch_token``, e
    uma limpeza quebrada nunca derruba a parada.
    """
    try:
        dispositivo = getattr(daemon, "_keyboard_device", None)
        if dispositivo is not None:
            try:
                dispositivo.stop()
            finally:
                daemon._keyboard_device = None
    finally:
        osk = getattr(daemon, "_osk_controller", None)
        if osk is not None:
            try:
                osk.close()
            finally:
                daemon._osk_controller = None


async def _parar_dsu(daemon: Any) -> None:
    parar = getattr(daemon, "_stop_dsu", None)
    if getattr(daemon, "_servidor_dsu", None) is not None and callable(parar):
        try:
            await asyncio.wait_for(parar(), timeout=_TETO_DA_PARADA_DO_DSU_S)
        except Exception as exc:
            logger.warning("dsu_stop_falhou", err=str(exc))


async def _parar_ipc(daemon: Any) -> None:
    servidor = getattr(daemon, "_ipc_server", None)
    if servidor is not None:
        try:
            await asyncio.wait_for(servidor.stop(), timeout=_TETO_DA_PARADA_DO_SERVIDOR_S)
        finally:
            daemon._ipc_server = None


async def _parar_udp(daemon: Any) -> None:
    servidor = getattr(daemon, "_udp_server", None)
    if servidor is not None:
        try:
            await asyncio.wait_for(servidor.stop(), timeout=_TETO_DA_PARADA_DO_SERVIDOR_S)
        finally:
            daemon._udp_server = None


async def _parar_autoswitch(daemon: Any) -> None:
    trocador = getattr(daemon, "_autoswitch", None)
    if trocador is not None:
        try:
            trocador.stop()
        finally:
            daemon._autoswitch = None


async def _parar_as_tarefas(daemon: Any) -> None:
    from hefesto_dualsense4unix.daemon.connection import parar_as_tarefas

    await parar_as_tarefas(daemon)


async def _soltar_o_controle(daemon: Any) -> None:
    from hefesto_dualsense4unix.daemon.connection import soltar_o_controle

    await soltar_o_controle(daemon)


SUBSYSTEM_REGISTRY: tuple[Passo, ...] = (
    Passo(
        "ipc",
        partida=lambda d: d._start_ipc(),
        quando=lambda c: c.ipc_enabled,
        parada=_parar_ipc,
        parar_em=150,
        essencial=_ipc_indisponivel,
    ),
    Passo(
        "dsu",
        partida=lambda d: d._start_dsu(),
        quando=lambda c: c.dsu_enabled,
        parada=_parar_dsu,
        parar_em=140,
    ),
    Passo(
        "udp",
        partida=lambda d: d._start_udp(),
        quando=lambda c: c.udp_enabled,
        parada=_parar_udp,
        parar_em=160,
    ),
    Passo(
        "autoswitch",
        partida=lambda d: d._start_autoswitch(),
        quando=lambda c: c.autoswitch_enabled,
        parada=_parar_autoswitch,
        parar_em=170,
    ),
    Passo(
        "mouse",
        partida=lambda d: d._start_mouse_emulation(),
        quando=lambda c: c.mouse_emulation_enabled,
        parada=_parar_mouse,
        parar_em=100,
    ),
    Passo(
        "gamepad",
        partida=lambda d: d._start_gamepad_emulation(),
        quando=lambda c: c.gamepad_emulation_enabled,
        parada=_parar_gamepad,
        parar_em=110,
    ),
    Passo(
        "keyboard",
        partida=lambda d: d._start_keyboard_emulation(),
        quando=lambda c: c.keyboard_emulation_enabled,
        parada=_parar_teclado,
        parar_em=130,
    ),
    Passo("hotkey", partida=_hotkey, parada=_parar_hotkey, parar_em=80),
    Passo("mic_do_jogo", partida=_mic_do_jogo),
    Passo(
        "mic_hotkey",
        partida=_mic_hotkey,
        quando=lambda c: c.mic_button_toggles_system,
    ),
    Passo("luz_do_mic", partida=_luz_do_mic),
    Passo("tato_vivo", partida=_tato_vivo),
    Passo("luz_animada", partida=_luz_animada),
    Passo("telemetria_do_jogo", partida=_telemetria_do_jogo),
    Passo("ouvinte_do_som", partida=_ouvinte_do_som),
    Passo(
        "bt_mic",
        partida=lambda d: d._start_bt_mic(),
        parada=_parar_bt_mic,
        parar_em=20,
    ),
    Passo(
        "alto_falante",
        partida=lambda d: d._start_alto_falante(),
        parada=_parar_alto_falante,
        parar_em=30,
    ),
    Passo(
        "conexoes",  # (noqa-acento)
        partida=lambda d: d._start_conexoes(),
        parada=_parar_conexoes,
        parar_em=50,
    ),
    Passo(
        "central_do_radio",
        partida=lambda d: d._start_central_do_radio(),
        parada=_parar_central_do_radio,
        parar_em=40,
    ),
    Passo("ouvido_do_usb", partida=lambda d: d._start_ouvido_do_usb()),
    Passo(
        "plugins",
        partida=lambda d: d._start_plugins(),
        parada=_parar_plugins,
        parar_em=60,
    ),
    Passo(
        "metrics",
        partida=lambda d: d._start_metrics(),
        parada=_parar_metrics,
        parar_em=70,
    ),
    Passo("eventos_do_perfil", partida=_eventos_do_perfil, depois_do_controle=True),
    Passo(
        "mods",
        partida=lambda d: d._start_mods(),
        parada=_parar_mods,
        parar_em=10,
        depois_do_controle=True,
    ),
    Passo("coop", parada=_parar_coop, parar_em=90),
    Passo("broker", parada=_parar_o_broker, parar_em=120),
    Passo("tarefas", parada=_parar_as_tarefas, parar_em=180),
    Passo("controle", parada=_soltar_o_controle, parar_em=190),
)


async def subir(daemon: Any, *, depois_do_controle: bool = False) -> None:
    """Sobe, na ordem da lista, os subsystems da fase pedida cuja condição vale.

    A condição é lida na hora de cada um (a config pode mudar entre dois passos). Cada
    partida passa pelo ``_safe_start`` do daemon: a falha entra em ``_failed_subsystems``
    e no diário, e só ``essencial`` derruba o ``run()``.
    """
    for passo in SUBSYSTEM_REGISTRY:
        if passo.partida is None or passo.depois_do_controle != depois_do_controle:
            continue
        if passo.quando is not None and not passo.quando(daemon.config):
            continue
        partida = passo.partida
        essencial = passo.essencial
        await daemon._safe_start(
            passo.nome,
            lambda partida=partida: partida(daemon),
            essencial=(lambda exc, essencial=essencial: essencial(daemon, exc))
            if essencial is not None
            else None,
        )


def a_ordem_de_parada() -> list[Passo]:
    """Os passos que param, na ordem em que param."""
    return sorted(
        (p for p in SUBSYSTEM_REGISTRY if p.parada is not None),
        key=lambda p: p.parar_em if p.parar_em is not None else 0,
    )


async def parar(daemon: Any) -> None:
    """Para tudo o que a lista declara parar, na ordem de parada dela.

    Uma parada que falha vira aviso no diário e as demais seguem: limpeza quebrada nunca
    derruba a parada. ``CancelledError`` passa (não é ``Exception``).
    """
    for passo in a_ordem_de_parada():
        parada = passo.parada
        if parada is None:
            continue
        try:
            resultado = parada(daemon)
            if inspect.isawaitable(resultado):
                await resultado
        except Exception as exc:
            logger.warning("subsystem_parada_falhou", subsystem=passo.nome, err=str(exc))


__all__ = [
    "SUBSYSTEM_REGISTRY",
    "AltoFalanteSubsystem",
    "BtMicSubsystem",
    "ConexoesSubsystem",
    "MetricsSubsystem",
    "Passo",
    "PluginsSubsystem",
    "Subsystem",
    "a_ordem_de_parada",
    "parar",
    "subir",
]
