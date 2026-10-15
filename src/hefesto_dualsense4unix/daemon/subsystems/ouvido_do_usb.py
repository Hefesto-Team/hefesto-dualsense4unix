"""ouvido_do_usb.py — o daemon ouve o barramento USB e registra cada mudança da cadeia.

Um socket ``NETLINK_KOBJECT_UEVENT``, grupo do kernel, só stdlib e sem root: a cada ``add`` ou
``remove`` de um ``usb_device``, relê o censo e compara com a leitura anterior
(:class:`~hefesto_dualsense4unix.integrations.diario_do_usb.Comparador`). Sem netlink (sandbox),
o mesmo laço relê a cada :data:`RELEITURA_SEM_NETLINK_S`, e a reenumeração se prova pelo
``devnum``.
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.identity import _read_boot_id
from hefesto_dualsense4unix.integrations import diario_do_usb
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo, ler_o_barramento
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

NETLINK_KOBJECT_UEVENT = 15
GRUPO_DO_KERNEL = 1
RELEITURA_SEM_NETLINK_S = 2.0
#: depois do ``add``, o tempo para os drivers se ligarem às interfaces antes da releitura
ACOMODAR_S = 0.5
#: sem evento, o laço acorda neste prazo para conferir os ausentes
PRAZO_DA_ESPERA_S = 5.0
_TAMANHO_DA_MENSAGEM = 1 << 16
_ACOES = frozenset({"add", "remove"})


def abrir_o_netlink() -> socket.socket | None:
    """O socket de uevent do kernel, sem bloquear; ``None`` quando o sistema não o dá."""
    try:
        sock = socket.socket(
            socket.AF_NETLINK, socket.SOCK_RAW | socket.SOCK_NONBLOCK | socket.SOCK_CLOEXEC,
            NETLINK_KOBJECT_UEVENT)
    except (OSError, AttributeError) as erro:
        logger.info("ouvido_do_usb_sem_netlink", erro=str(erro))
        return None
    try:
        sock.bind((0, GRUPO_DO_KERNEL))
    except OSError:
        sock.close()
        return None
    return sock


def eventos_de(dado: bytes) -> dict[str, str]:
    """Os campos ``CHAVE=valor`` de uma mensagem do kernel (``add@/devices/…\\0ACTION=add\\0…``)."""
    campos: dict[str, str] = {}
    for parte in dado.split(b"\0")[1:]:
        chave, igual, valor = parte.partition(b"=")
        if igual:
            campos[chave.decode("ascii", "replace")] = valor.decode("utf-8", "replace")
    return campos


def interessa(dado: bytes) -> bool:
    """Um aparelho USB inteiro entrou ou saiu (não uma interface, não outro subsistema)."""
    campos = eventos_de(dado)
    return (
        campos.get("SUBSYSTEM") == "usb"
        and campos.get("DEVTYPE") == "usb_device"
        and campos.get("ACTION") in _ACOES
    )


def _drenar(sock: socket.socket) -> bool:
    """Lê o que ficou na fila sem esperar; diz se algo ali interessa."""
    algum = False
    while True:
        try:
            dado = sock.recv(_TAMANHO_DA_MENSAGEM)
        except (BlockingIOError, InterruptedError):
            return algum
        except OSError:
            return algum
        if not dado:
            return algum
        algum = algum or interessa(dado)


class Ouvido:
    """O censo, o comparador e o diário, sem o laço: o que o teste dirige direto."""

    def __init__(
        self,
        *,
        ler_censo: Callable[[], Censo] = ler_o_barramento,
        diario: Path | None = None,
        boot_id: str | None = None,
        relogio: Callable[[], float] = time.monotonic,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self._ler_censo = ler_censo
        self.diario = diario or diario_do_usb.caminho_do_diario()
        self._vistos_em = diario_do_usb.caminho_dos_vistos(self.diario)
        self.boot_id = (_read_boot_id() or "") if boot_id is None else boot_id
        self._agora = agora
        self.comparador = diario_do_usb.Comparador(
            boot_id=self.boot_id,
            vistos=diario_do_usb.carregar_os_vistos(self._vistos_em),
            registro=self._registrar,
            subiu_em=relogio(),
            relogio=relogio,
            agora=agora,
        )
        self._gravado: dict[str, Any] = {}

    def _registrar(self, o_que: str, campos: dict[str, Any], **extras: Any) -> None:
        diario_do_usb.registrar(
            o_que, campos, boot_id=self.boot_id, caminho=self.diario, agora=self._agora(),
            **extras)

    def _gravar_os_vistos(self) -> None:
        if self.comparador.vistos != self._gravado:
            diario_do_usb.gravar_os_vistos(self._vistos_em, self.comparador.vistos)
            self._gravado = {k: dict(v) for k, v in self.comparador.vistos.items()}

    def comecar(self, *, com_netlink: bool) -> None:
        como = "netlink" if com_netlink else f"releitura a cada {RELEITURA_SEM_NETLINK_S:g} s"
        self._registrar(diario_do_usb.COMECOU_A_OUVIR, {"como": como})
        self.reler()

    def reler(self) -> list[tuple[str, diario_do_usb.Foto]]:
        eventos = self.comparador.observar(diario_do_usb.fotos_do_censo(self._ler_censo()))
        self._gravar_os_vistos()
        return eventos

    def conferir_ausentes(self) -> list[tuple[str, diario_do_usb.Foto]]:
        eventos = self.comparador.conferir_ausentes()
        if eventos:
            self._gravar_os_vistos()
        return eventos

    def passo(self, *, mudou: bool) -> None:
        """Uma volta do laço: relê se o kernel avisou e confere os ausentes; a falha vai ao log."""
        try:
            if mudou:
                self.reler()
            self.conferir_ausentes()
        except Exception:
            logger.warning("ouvido_do_usb_releitura_falhou", exc_info=True)

    def parar(self) -> None:
        self._registrar(diario_do_usb.PAROU_DE_OUVIR, {})


async def _esperar_evento(sock: socket.socket, prazo: float) -> bool:
    loop = asyncio.get_running_loop()
    try:
        dado = await asyncio.wait_for(loop.sock_recv(sock, _TAMANHO_DA_MENSAGEM), prazo)
    except TimeoutError:
        return False
    return interessa(dado)


async def ouvido_do_usb_loop(
    daemon: Any,
    ouvido: Ouvido,
    *,
    abrir: Callable[[], socket.socket | None] = abrir_o_netlink,
    intervalo: float = RELEITURA_SEM_NETLINK_S,
    acomodar: float = ACOMODAR_S,
    prazo: float = PRAZO_DA_ESPERA_S,
) -> None:
    sock = abrir()
    try:
        await asyncio.to_thread(ouvido.comecar, com_netlink=sock is not None)
        while not daemon._is_stopping():
            if sock is None:
                await asyncio.sleep(intervalo)
                mudou = True
            else:
                mudou = await _esperar_evento(sock, prazo)
                if mudou:
                    await asyncio.sleep(acomodar)
                    _drenar(sock)
            await asyncio.to_thread(ouvido.passo, mudou=mudou)
    finally:
        if sock is not None:
            sock.close()
        try:
            ouvido.parar()
        except Exception:
            logger.warning("ouvido_do_usb_parar_falhou", exc_info=True)


def start_ouvido_do_usb(daemon: Any) -> None:
    """Sobe o laço; a tarefa vai para ``daemon._tasks`` e desce com o daemon."""
    ouvido = Ouvido()
    task = asyncio.create_task(ouvido_do_usb_loop(daemon, ouvido), name="ouvido_do_usb_loop")
    daemon._tasks.append(task)
    logger.info("ouvido_do_usb_iniciado", diario=str(ouvido.diario))


__all__ = [
    "NETLINK_KOBJECT_UEVENT",
    "Ouvido",
    "abrir_o_netlink",
    "eventos_de",
    "interessa",
    "ouvido_do_usb_loop",
    "start_ouvido_do_usb",
]
