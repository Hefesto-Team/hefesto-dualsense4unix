"""ouvido_do_usb.py — o daemon ouve o barramento USB e registra cada mudança da cadeia.

Um socket ``NETLINK_KOBJECT_UEVENT``, grupo do kernel, só stdlib e sem root: a cada ``add`` ou
``remove`` de um ``usb_device``, relê o censo e compara com a leitura anterior
(:class:`~hefesto_dualsense4unix.integrations.diario_do_usb.Comparador`). Sem netlink (sandbox,
ou o socket que caiu), o mesmo laço relê a cada :data:`RELEITURA_SEM_NETLINK_S`, a reenumeração se
prova pelo ``devnum``, e a abertura do socket se repete com recuo de :data:`RECUO_INICIAL_S` até
:data:`RECUO_MAXIMO_S`. O ``add`` e o ``remove`` de todo aparelho chegam ao comparador com a hora
do aviso, que decide a volta.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.relogio_da_conexao import RELOGIO
from hefesto_dualsense4unix.daemon.subsystems.identity import _read_boot_id
from hefesto_dualsense4unix.integrations import diario_do_usb
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo, ler_o_barramento
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

NETLINK_KOBJECT_UEVENT = 15
GRUPO_DO_KERNEL = 1
RELEITURA_SEM_NETLINK_S = 2.0
RECUO_INICIAL_S = 2.0
RECUO_MAXIMO_S = 60.0
ACOMODAR_S = 0.5
PRAZO_DA_ESPERA_S = 5.0
_TAMANHO_DA_MENSAGEM = 1 << 16
_ACOES = frozenset({"add", "remove"})
_ACOES_DO_HID = frozenset({"add", "remove", "bind", "unbind"})
PRODUTO_DA_SONY = "54c/"


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


def a_volta_quer_saber(dado: bytes) -> bool:
    """O barramento mudou, ou o kernel terminou (ou desfez) a probe de um HID.

    O ``bind`` de um HID é o aviso exato de «o driver terminou», e sai depois de todos os nós.
    """
    campos = eventos_de(dado)
    return interessa(dado) or (
        campos.get("SUBSYSTEM") == "hid" and campos.get("ACTION") in _ACOES_DO_HID
    )


_ASSINANTES: list[Callable[[bytes], None]] = []


def _avisar_a_volta(daemon: Any, dado: bytes) -> None:
    """O sino da volta toca assim que o kernel diz, antes de o censo assentar.

    O ``add`` e o ``remove`` de todo aparelho USB vão antes aos assinantes (o laço assina o
    :meth:`Ouvido.ouviu`), com a hora do aviso, não a da leitura do censo.
    """
    for assinante in tuple(_ASSINANTES):
        assinante(dado)
    if not a_volta_quer_saber(dado):
        return
    from hefesto_dualsense4unix.daemon.connection import acordar_a_volta

    campos = eventos_de(dado)
    if (
        campos.get("ACTION") == "add"
        and campos.get("DEVTYPE") == "usb_device"
        and campos.get("PRODUCT", "").startswith(PRODUTO_DA_SONY)
    ):
        RELOGIO.usb_entrou(campos.get("DEVPATH", "").rsplit("/", 1)[-1])
    acordar_a_volta(daemon, "netlink")


def _drenar(sock: socket.socket, daemon: Any = None) -> bool:
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
        if daemon is not None:
            _avisar_a_volta(daemon, dado)
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
            reset_da_porta=self._o_ultimo_reset_da,
            queda_da_porta=self._a_ultima_queda_da,
        )
        self._gravado: dict[str, Any] = {}

    def _o_ultimo_reset_da(self, porta: str) -> float | None:
        return diario_do_usb.ultimo_reset_da_porta(diario_do_usb.ler(self.diario), porta)

    def _a_ultima_queda_da(self, porta: str) -> float | None:
        return diario_do_usb.ultima_queda_da_porta(diario_do_usb.ler(self.diario), porta)

    def ouviu(self, dado: bytes) -> None:
        """O aviso do kernel de que um aparelho USB entrou ou saiu, com a hora em que chegou."""
        if not interessa(dado):
            return
        campos = eventos_de(dado)
        caminho = campos.get("DEVPATH", "").rsplit("/", 1)[-1]
        if not caminho:
            return
        if campos["ACTION"] == "add":
            self.comparador.chegou(caminho)
        else:
            self.comparador.partiu(caminho)

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
        try:
            self.reler()
        except Exception:
            logger.warning("ouvido_do_usb_releitura_falhou", exc_info=True)

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


async def _esperar_evento(sock: socket.socket, prazo: float, daemon: Any = None) -> bool:
    """O aviso do kernel dentro do prazo; ``False`` quando nada chegou.

    No Python 3.10 o ``asyncio.wait_for`` levanta ``asyncio.TimeoutError``, que só vira o
    ``TimeoutError`` da linguagem no 3.11: o prazo vencido sem evento matava o ouvido.
    """
    loop = asyncio.get_running_loop()
    try:
        dado = await asyncio.wait_for(loop.sock_recv(sock, _TAMANHO_DA_MENSAGEM), prazo)
    except (TimeoutError, asyncio.TimeoutError):
        return False
    if daemon is not None:
        _avisar_a_volta(daemon, dado)
    return interessa(dado)


async def _ouvir(
    sock: socket.socket, prazo: float, daemon: Any = None
) -> tuple[bool, socket.socket | None]:
    """``(mudou, o socket que segue)``. O erro do netlink nunca para o ouvido.

    ``ENOBUFS``: a rajada estourou a fila e o kernel jogou eventos fora; o que se perdeu só a
    releitura recupera. Outro erro: o socket caiu, e o laço segue pela releitura periódica até
    reabri-lo.
    """
    try:
        return await _esperar_evento(sock, prazo, daemon), sock
    except OSError as erro:
        if erro.errno == errno.ENOBUFS:
            logger.info("ouvido_do_usb_eventos_perdidos")
            return True, sock
        logger.warning("ouvido_do_usb_netlink_caiu", erro=str(erro))
        sock.close()
        return True, None


def _abrir_sem_cair(abrir: Callable[[], socket.socket | None]) -> socket.socket | None:
    try:
        return abrir()
    except Exception:
        logger.warning("ouvido_do_usb_abrir_falhou", exc_info=True)
        return None


async def ouvido_do_usb_loop(
    daemon: Any,
    ouvido: Ouvido,
    *,
    abrir: Callable[[], socket.socket | None] = abrir_o_netlink,
    intervalo: float = RELEITURA_SEM_NETLINK_S,
    acomodar: float = ACOMODAR_S,
    prazo: float = PRAZO_DA_ESPERA_S,
    recuo_inicial: float = RECUO_INICIAL_S,
    recuo_maximo: float = RECUO_MAXIMO_S,
    relogio: Callable[[], float] = time.monotonic,
) -> None:
    """Ouve o netlink; sem socket, relê a cada ``intervalo`` e tenta reabri-lo com recuo.

    O recuo dobra a cada abertura que falha, de ``recuo_inicial`` até ``recuo_maximo``, e volta ao
    inicial quando o socket cai de novo. Com o socket de volta, o laço volta a esperar o evento.
    """
    sock = _abrir_sem_cair(abrir)
    recuo = recuo_inicial
    tentar_em = relogio() + recuo
    _ASSINANTES.append(ouvido.ouviu)
    try:
        await asyncio.to_thread(ouvido.comecar, com_netlink=sock is not None)
        while not daemon._is_stopping():
            caiu = False
            if sock is None:
                await asyncio.sleep(intervalo)
                mudou = True
            else:
                mudou, sock = await _ouvir(sock, prazo, daemon)
                caiu = sock is None
                if mudou and sock is not None:
                    await asyncio.sleep(acomodar)
                    _drenar(sock, daemon)
            await asyncio.to_thread(ouvido.passo, mudou=mudou)
            if caiu:
                recuo = recuo_inicial
                tentar_em = relogio() + recuo
            elif sock is None and relogio() >= tentar_em:
                sock = _abrir_sem_cair(abrir)
                if sock is None:
                    recuo = min(recuo * 2, recuo_maximo)
                    tentar_em = relogio() + recuo
                else:
                    logger.info("ouvido_do_usb_netlink_reaberto")
                    recuo = recuo_inicial
    finally:
        with contextlib.suppress(ValueError):
            _ASSINANTES.remove(ouvido.ouviu)
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
    "RECUO_INICIAL_S",
    "RECUO_MAXIMO_S",
    "Ouvido",
    "a_volta_quer_saber",
    "abrir_o_netlink",
    "eventos_de",
    "interessa",
    "ouvido_do_usb_loop",
    "start_ouvido_do_usb",
]
