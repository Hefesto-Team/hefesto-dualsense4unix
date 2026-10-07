"""Cliente do broker root hide-hidraw (BROKER-01, Onda S) — a conexão É a lease."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_SOCKET_PATH = "/run/hefesto-hidraw-broker/broker.sock"
#: caminho inexistente (conftest) — na máquina da mantenedora o broker REAL
SOCKET_PATH_ENV = "HEFESTO_BROKER_SOCKET"
_TIMEOUT_S = 2.0
_MAX_RESPONSE_BYTES = 65536

_FD_INT_SIZE = struct.calcsize("i")
_ANCILLARY_SPACE = socket.CMSG_SPACE(2 * _FD_INT_SIZE)

_CLIENT_CREATION_LOCK = threading.Lock()

_EXECUTOR_CREATION_LOCK = threading.Lock()

_FALLBACK_EXECUTOR: ThreadPoolExecutor | None = None


class HidrawBrokerClient:
    """Conexão-lease com o broker + hide/restore/restore_all/open_fd/status."""

    def __init__(
        self, socket_path: str | None = None, *, timeout_s: float = _TIMEOUT_S
    ) -> None:
        self._path = (
            socket_path
            if socket_path is not None
            else os.environ.get(SOCKET_PATH_ENV, DEFAULT_SOCKET_PATH)
        )
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._indisponivel_logado = False
        self._estado_por_no: dict[str, str] = {}
        self._estado_lock = threading.Lock()


    def hide(self, node: str) -> bool:
        """Esconde `node` do uid da sessão. False = não escondeu (best-effort)."""
        response = self._request({"cmd": "hide", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            if response is not None and response.get("state") == "exposed":
                self._logar_transicao(
                    "hidraw_broker_hide_adiado", node, "exposed", state="exposed"
                )
            else:
                self._logar_transicao("hidraw_broker_hidden", node, "hidden")
        else:
            self._log_falha("hide", node, response)
        return ok

    def restore(self, node: str) -> bool:
        """Restaura o acesso a `node`. False = broker indisponível/erro."""
        response = self._request({"cmd": "restore", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            estado = str(response.get("state") or "exposed") if response else "exposed"
            self._logar_transicao("hidraw_broker_restored", node, estado, state=estado)
        else:
            self._log_falha("restore", node, response)
        return ok

    def expor(self, node: str, *, entradas: bool = False) -> bool:
        """«Mantenha `node` ABERTO enquanto esta lease viver.» False = não deu.

        O-NO-NASCE-FECHADO-01 (20/09/2026). Com a regra udev da cura, o nó do
        DualSense físico nasce `0600 root` e NINGUÉM o abre por caminho — nem
        o `hidapi.Device(path=...)` do nosso próprio handle de controle, que
        não aceita fd. Este é o pedido que põe a ACL de volta.

        HIDE-SO-O-HIDRAW-02 (24/09/2026): `entradas=True` pede também os nós
        de entrada do aparelho (o evdev e o joydev), que nascem fechados como
        o hidraw. É o pedido do Modo Nativo — «só o Modo Nativo devolve» — e
        de mais ninguém: o `with exposicao` do handle de controle quer o
        hidraw e mais nada. O campo só viaja quando é verdade, e um broker
        antigo o ignora (expõe o hidraw, como antes).

        Best-effort como todo o resto: broker ausente ⇒ False, e o chamador
        segue. Num mundo sem a cura instalada, o nó já está aberto e o False
        não custa nada; num mundo COM a cura e SEM broker, nada abriria de
        qualquer forma.
        """
        pedido: dict[str, Any] = {"cmd": "expose", "node": node}
        if entradas:
            pedido["entradas"] = True
        response = self._request(pedido)
        ok = bool(response is not None and response.get("ok"))
        if ok:
            estado = str(response.get("state") or "exposed") if response else "exposed"
            self._logar_transicao("hidraw_broker_exposto", node, estado, state=estado)
        else:
            self._log_falha("expose", node, response)
        return ok

    def desexpor(self, node: str) -> bool:
        """Solta o pedido de exposição — o nó volta ao estado de NASCIMENTO."""
        response = self._request({"cmd": "unexpose", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            estado = str(response.get("state") or "fechado") if response else "fechado"
            self._logar_transicao("hidraw_broker_desexposto", node, estado, state=estado)
        else:
            self._log_falha("unexpose", node, response)
        return ok

    @contextlib.contextmanager
    def exposicao(self, node: str) -> Iterator[bool]:
        """`with client.exposicao(no):` — expõe, cede, e desexpõe SEMPRE."""
        aberto = False
        try:
            aberto = self.expor(node)
            yield aberto
        finally:
            if aberto:
                with contextlib.suppress(Exception):
                    self.desexpor(node)

    def restore_all(self) -> bool:
        """Restaura TUDO que esta lease escondeu (teardown/Modo Nativo)."""
        response = self._request({"cmd": "restore_all"})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            logger.info(
                "hidraw_broker_restored_all",
                nodes=response.get("restored") if response else None,
            )
        else:
            self._log_falha("restore_all", None, response)
        return ok

    def abrir_no(self, node: str) -> tuple[int | None, str]:
        """`(fd, motivo)` — o `open` do broker COM a razão dita em português."""
        with self._lock:
            response, fds = self._request_with_fds({"cmd": "open", "node": node})
        if response is not None and response.get("ok") and len(fds) == 1:
            estado = response.get("state")
            with contextlib.suppress(Exception):
                logger.info("hidraw_broker_fd_recebido", node=node, state=estado)
            return fds[0], f"o broker serviu o fd (nó {estado}) por {self._path}"
        for fd in fds:
            with contextlib.suppress(OSError):
                os.close(fd)
        if response is not None and response.get("ok"):
            logger.warning(
                "hidraw_broker_fd_count_invalido", node=node, count=len(fds)
            )
            return None, f"o broker devolveu {len(fds)} fds — protocolo violado"
        self._log_falha("open", node, response)
        if response is None:
            return None, f"o broker não respondeu em {self._path}"
        return None, f"o broker recusou: {response.get('error')}"

    def open_fd(self, node: str) -> int | None:
        """Pede ao broker um fd O_RDWR do nó. None = indisponível/recusado."""
        return self.abrir_no(node)[0]

    def montar_pad_usb(
        self, serial: str, descritor: bytes
    ) -> tuple[int | None, dict[str, Any] | None]:
        """``(fd do /dev/hidgN, resposta)``: o pad em USB montado pelo broker.

        O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01 (07/10/2026). A lease
        é esta conexão: se ela cai, o broker desmonta o gadget. ``None`` no fd é
        o pad que fica no uhid; a resposta diz por quê (``contrato`` quando o
        kernel não cumpre um).
        """
        with self._lock:
            response, fds = self._request_with_fds(
                {"cmd": "pad_usb_montar", "serial": serial, "descritor": descritor.hex()}
            )
        if response is not None and response.get("ok") and len(fds) == 1:
            # O broker cede o nó por ``O_PATH`` (o cgroup de device dele não
            # alcança o grupo ``hidg``); a leitura e a escrita se abrem AQUI,
            # no mesmo inode, pelo ``/proc/self/fd``.
            try:
                return reabrir_o_no_cedido(fds[0]), response
            except OSError as exc:
                response = {**response, "ok": False, "error": "pad_usb_reabrir",
                            "errno": exc.errno}
                with contextlib.suppress(OSError):
                    self.desmontar_pad_usb(str(response.get("gadget", "")))
            finally:
                with contextlib.suppress(OSError):
                    os.close(fds[0])
            fds = []
        for fd in fds:
            with contextlib.suppress(OSError):
                os.close(fd)
        self._log_falha("pad_usb_montar", serial, response)
        return None, response

    def desmontar_pad_usb(self, gadget: str) -> bool:
        """Devolve o gadget ao broker, que o desliga e desmonta."""
        response = self._request({"cmd": "pad_usb_desmontar", "gadget": gadget})
        return bool(response is not None and response.get("ok"))

    def status(self) -> dict[str, Any] | None:
        """Resposta crua do `status` (nós escondidos) — para doctor/telemetria."""
        return self._request({"cmd": "status"})

    def ping(self) -> bool:
        response = self._request({"cmd": "ping"})
        return bool(response is not None and response.get("ok"))

    def is_available(self) -> bool:
        """True se o socket existe E o broker responde (abre a lease)."""
        if not os.path.exists(self._path):
            return False
        return self.ping()

    def close(self) -> None:
        """Fecha a lease explicitamente (o broker restaura o que restou)."""
        with self._lock:
            self._close_locked()


    def _request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        line = (json.dumps(payload) + "\n").encode("utf-8")
        with self._lock:
            for tentativa in (1, 2):
                sock = self._ensure_sock_locked()
                if sock is None:
                    return None
                try:
                    sock.sendall(line)
                    raw = self._read_line_locked(sock)
                    break
                except OSError:
                    self._close_locked()
                    if tentativa == 2:
                        return None
            else:  # pragma: no cover - inalcançável (o for sempre break/return)
                return None
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return response if isinstance(response, dict) else None

    def _request_with_fds(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[int]]:
        """Uma requisição → (resposta, fds recebidos). Chamado sob `self._lock`."""
        sock = self._ensure_sock_locked()
        if sock is None:
            return None, []
        line = (json.dumps(payload) + "\n").encode("utf-8")
        fds: list[int] = []
        buf = bytearray()
        try:
            sock.sendall(line)
            while b"\n" not in buf:
                if len(buf) > _MAX_RESPONSE_BYTES:
                    raise OSError("resposta do broker sem fim de linha")
                data, ancdata, flags, _addr = sock.recvmsg(
                    4096, _ANCILLARY_SPACE, socket.MSG_CMSG_CLOEXEC
                )
                for level, ctype, cdata in ancdata:
                    if level == socket.SOL_SOCKET and ctype == socket.SCM_RIGHTS:
                        n = len(cdata) // _FD_INT_SIZE
                        fds.extend(struct.unpack(f"{n}i", cdata[: n * _FD_INT_SIZE]))
                if flags & socket.MSG_CTRUNC:
                    raise OSError("ancillary truncado (MSG_CTRUNC)")
                if not data:
                    raise OSError("broker fechou a conexão")
                buf.extend(data)
        except OSError:
            for fd in fds:
                with contextlib.suppress(OSError):
                    os.close(fd)
            self._close_locked()
            return None, []
        raw = bytes(buf[: buf.find(b"\n")])
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            response = None
        if not isinstance(response, dict):
            for fd in fds:
                with contextlib.suppress(OSError):
                    os.close(fd)
            return None, []
        return response, fds

    def _ensure_sock_locked(self) -> socket.socket | None:
        if self._sock is not None:
            return self._sock
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout_s)
        try:
            sock.connect(self._path)
        except OSError as exc:
            sock.close()
            if not self._indisponivel_logado:
                logger.info("hidraw_broker_unavailable", path=self._path, err=str(exc))
                self._indisponivel_logado = True
            else:
                logger.debug("hidraw_broker_connect_failed", err=str(exc))
            return None
        self._sock = sock
        self._indisponivel_logado = False
        logger.info("hidraw_broker_lease_open", path=self._path)
        return sock

    def _read_line_locked(self, sock: socket.socket) -> bytes:
        chunks = bytearray()
        while b"\n" not in chunks:
            if len(chunks) > _MAX_RESPONSE_BYTES:
                raise OSError("resposta do broker sem fim de linha")
            data = sock.recv(4096)
            if not data:
                raise OSError("broker fechou a conexão")
            chunks.extend(data)
        return bytes(chunks[: chunks.find(b"\n")])

    def _close_locked(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None

    def _logar_transicao(
        self, evento: str, node: str, estado: str, **campos: Any
    ) -> None:
        """`info` quando o nó MUDA de estado; `debug` quando só reafirma."""
        with self._estado_lock:
            anterior = self._estado_por_no.get(node)
            self._estado_por_no[node] = estado
        if anterior == estado:
            logger.debug(evento, node=node, reafirmacao=True, **campos)
            return
        logger.info(evento, node=node, **campos)

    def _log_falha(
        self, cmd: str, node: str | None, response: dict[str, Any] | None
    ) -> None:
        logger.debug(
            "hidraw_broker_cmd_failed",
            cmd=cmd,
            node=node,
            error=(response or {}).get("error"),
        )


def reabrir_o_no_cedido(fd_o_path: int) -> int:
    """O fd de leitura e escrita do nó que o broker cedeu por ``O_PATH``."""
    return os.open(f"/proc/self/fd/{fd_o_path}", os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)


def nos_de_entrada_do_hidraw(
    no: str,
    *,
    sys_class_hidraw: str = "/sys/class/hidraw",
    dev_input_root: str = "/dev/input",
) -> list[str]:
    """Os nós de entrada (`eventN`, `jsN`) do MESMO aparelho de um hidraw."""
    base = os.path.basename(no)
    try:
        hid = os.path.realpath(f"{sys_class_hidraw}/{base}/device")
        pastas = sorted(os.listdir(f"{hid}/input"))
    except OSError:
        return []
    saida: list[str] = []
    for pasta in pastas:
        if not pasta.startswith("input"):
            continue
        input_dir = f"{hid}/input/{pasta}"
        try:
            with open(f"{input_dir}/name", encoding="utf-8", errors="replace") as fh:
                nome = fh.read().strip()
            filhos = sorted(os.listdir(input_dir))
        except OSError:
            continue
        for filho in filhos:
            if not (filho.startswith("event") or filho.startswith("js")):
                continue
            if not filho[2 if filho.startswith("js") else 5:].isdigit():
                continue
            if filho.startswith("js") and nome.endswith("Motion Sensors"):
                continue
            saida.append(f"{dev_input_root}/{filho}")
    return saida


def broker_client_for(daemon: Any) -> Any:
    """Cliente-lease singleton por daemon (lazy) — dublês de teste passam direto."""
    client = getattr(daemon, "_hidraw_broker_client", None)
    if client is not None:
        return client
    with _CLIENT_CREATION_LOCK:
        client = getattr(daemon, "_hidraw_broker_client", None)
        if client is not None:
            return client
        client = HidrawBrokerClient()
        with contextlib.suppress(AttributeError, TypeError):
            daemon._hidraw_broker_client = client
    return client


def broker_executor_for(daemon: Any) -> ThreadPoolExecutor:
    """Executor DEDICADO (1 worker) das operações do broker, lazy por daemon."""
    global _FALLBACK_EXECUTOR
    executor = getattr(daemon, "_hidraw_broker_executor", None)
    if isinstance(executor, ThreadPoolExecutor):
        return executor
    with _EXECUTOR_CREATION_LOCK:
        executor = getattr(daemon, "_hidraw_broker_executor", None)
        if isinstance(executor, ThreadPoolExecutor):
            return executor
        novo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hefesto-broker")
        try:
            daemon._hidraw_broker_executor = novo
        except (AttributeError, TypeError):
            if _FALLBACK_EXECUTOR is None:
                _FALLBACK_EXECUTOR = novo
            else:
                novo.shutdown(wait=False)
                novo = _FALLBACK_EXECUTOR
        return novo


def broker_call_nonblocking(daemon: Any, call: Callable[[], object]) -> None:
    """Executa uma operação do cliente do broker SEM bloquear o event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        with contextlib.suppress(Exception):
            call()
        return

    def _run() -> None:
        with contextlib.suppress(Exception):
            call()

    try:
        broker_executor_for(daemon).submit(_run)
    except Exception:
        logger.debug("hidraw_broker_call_descartada", exc_info=True)


def make_broker_opener(daemon: Any) -> Callable[[str], int]:
    """Opener p/ `PhysicalReportReader`: broker primeiro, `os.open` de fallback."""

    def _open(path: str) -> int:
        fd: int | None = None
        with contextlib.suppress(Exception):
            fd = broker_client_for(daemon).open_fd(path)
        if fd is not None:
            return fd
        return os.open(path, os.O_RDONLY)

    return _open


def make_exposicao_factory(daemon: Any) -> Callable[[str], AbstractContextManager[bool]]:
    """Fábrica do `with` que mantém um nó ABERTO — o injetável do backend.

    O-NO-NASCE-FECHADO-01, item 4 da medição: `hidapi.Device(path=...)` é o
    ÚNICO bloqueador real da cura. O hidapi não abre por fd, e reabrir por
    `/proc/self/fd/N` refaz a checagem de permissão no inode — não é saída.
    Então o handle de controle do daemon (barra, rumble, gatilhos, mic,
    bateria) precisa do nó exposto DURANTE o `init()`, e fechado logo depois.

    Espelho de `make_broker_opener`, e com a mesma disciplina: nunca levanta.
    Broker ausente ⇒ um contexto que não faz nada e cede `False`; o `_open_one`
    tenta abrir assim mesmo, porque numa máquina SEM a cura instalada o nó já
    está aberto e recusar ali seria inventar um defeito.
    """

    def _exposicao(path: str) -> AbstractContextManager[bool]:
        # O MODO NATIVO GANHA DO `with` TRANSITÓRIO (auditoria de 20/09/2026).
        # A lease de exposição do broker é por CONEXÃO, e este `with` sai do
        # MESMO cliente que o pedido do Modo Nativo: o `unexpose` do `finally`
        # acharia o nó no `held` da conexão, veria `refcount == 1` e mandaria o
        # nó para o REPOUSO — fechando, no meio do Modo Nativo, o nó que o
        # jogo está usando. O reconciliador reabriria em até 2 s, e 2 s é
        # exatamente a janela que a Steam usa.
        with contextlib.suppress(Exception):
            ja_aberto = getattr(daemon, "no_exposto_pelo_modo_nativo", None)
            if callable(ja_aberto) and ja_aberto(path):
                return contextlib.nullcontext(True)
        try:
            client = broker_client_for(daemon)
        except Exception:
            return contextlib.nullcontext(False)
        exposicao = getattr(client, "exposicao", None)
        if not callable(exposicao):  # dublê antigo da suíte
            return contextlib.nullcontext(False)
        return exposicao(path)  # type: ignore[no-any-return]

    return _exposicao


# ---------------------------------------------------------------------------
# A PORTA, DECLARADA — o que os INSTRUMENTOS usam (A-PORTA-QUE-A-CASA-CONSTRUIU-01)
# ---------------------------------------------------------------------------
#
# Defeito medido em 15/08/2026: com a mesa 2+2 montada, NENHUM dos quatro
# DualSense físicos abre por `open()` — o próprio Hefesto os esconde de
# propósito (`broker/hidraw_broker.py:374` — `setfacl -b` + `chmod 0600`), para
# que o jogo veja só o vpad. Os instrumentos batiam nessa porta fechada e
# imprimiam `[Errno 13] Permission denied` (ou, pior, silêncio), quando a casa
# já tinha construído a porta certa: o `cmd open` do broker, que devolve um fd
# `O_RDWR` do nó ESCONDIDO por SCM_RIGHTS.
#
# A regra desta casa é *"todo instrumento tem de declarar qual biblioteca está
# usando"*, porque medir contra a biblioteca errada produz alarme convincente e
# falso. **O mesmo vale para a porta:** medir no nó escondido produz zero
# convincente e falso. Por isso `abrir_hidraw` nunca devolve só um fd — devolve
# um `NoAberto`, que carrega por onde entrou e por quê.

#: As duas portas, com o nome que aparece NO RELATÓRIO (é este texto que a
#: mordida 2 procura — se o fallback ficar mudo, ele some da tela).
PORTA_BROKER = "broker (SCM_RIGHTS)"
PORTA_DIRETA = "open() direto"

#: Estados do `EVIOCGRAB` de um nó evdev, na frase que vai ao relatório.
#: "o controle não emitiu" e "eu não posso ler" são coisas diferentes, e hoje
#: as duas saem como zero — é o que a mordida 3 cobra.
GRAB_LIVRE = "livre"
GRAB_DE_TERCEIRO = "PEGO por outro processo (EVIOCGRAB exclusivo)"
GRAB_SEM_PERMISSAO = "não posso ler (sem permissão no nó)"
GRAB_SEM_NO = "o nó não existe"
GRAB_DESCONHECIDO = "não sei dizer"

#: `EVIOCGRAB` = `_IOW('E', 0x90, int)`. O grab é EXCLUSIVO: se outro processo
#: (o co-op do daemon) já o tem, o nosso volta `EBUSY` — e é exatamente esse
#: `EBUSY` que separa "calado" de "escondido".
_EVIOCGRAB = 0x40044590


class PortaFechadaError(OSError):
    """As DUAS portas falharam — e o erro diz o que cada uma respondeu."""


@dataclass(frozen=True)
class NoAberto:
    """Um hidraw aberto E a porta por onde ele entrou. Nunca uma coisa só."""

    fd: int
    no: str
    porta: str
    motivo: str
    socket: str

    def fechar(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.fd)

    def __enter__(self) -> NoAberto:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fechar()

    @property
    def linha_de_relatorio(self) -> str:
        """A linha que vai ao cabeçalho, ao lado da biblioteca declarada."""
        return linha_da_porta(self.porta, self.motivo)


def linha_da_porta(porta: str, motivo: str) -> str:
    """O texto único da declaração de porta — um só formato em toda a casa."""
    return f"porta ............ {porta} — {motivo}"


def abrir_hidraw(
    no: str,
    *,
    escrita: bool = True,
    socket_path: str | None = None,
    cliente: Any | None = None,
) -> NoAberto:
    """Abre `no` pelo BROKER; se ele não servir, por `open()` — e DIZ qual foi."""
    caminho_socket = (
        socket_path
        if socket_path is not None
        else os.environ.get(SOCKET_PATH_ENV, DEFAULT_SOCKET_PATH)
    )
    fd: int | None = None
    motivo_broker = "o cliente do broker não foi consultado"
    proprio = cliente is None
    alvo = cliente if cliente is not None else HidrawBrokerClient(caminho_socket)
    try:
        fd, motivo_broker = alvo.abrir_no(no)
    except Exception as exc:
        motivo_broker = f"o cliente do broker levantou {type(exc).__name__}: {exc}"
    finally:
        if proprio:
            with contextlib.suppress(Exception):
                alvo.close()
    if fd is not None:
        return NoAberto(
            fd=fd, no=no, porta=PORTA_BROKER, motivo=motivo_broker, socket=caminho_socket
        )

    flags = (os.O_RDWR if escrita else os.O_RDONLY) | os.O_CLOEXEC
    try:
        fd = os.open(no, flags)
    except OSError as exc:
        raise PortaFechadaError(
            exc.errno,
            f"{no}: as duas portas falharam. "
            f"{PORTA_BROKER}: {motivo_broker}. "
            f"{PORTA_DIRETA}: {exc.strerror or exc}. "
            "Se o nó está 0600 sem ACL, é o Hefesto escondendo o físico do jogo "
            "(broker/hidraw_broker.py) — a regra udev NÃO está errada.",
        ) from exc
    return NoAberto(
        fd=fd,
        no=no,
        porta=PORTA_DIRETA,
        motivo=f"{motivo_broker} — caí no open() por caminho",
        socket=caminho_socket,
    )


def porta_provavel(socket_path: str | None = None) -> tuple[str, str]:
    """`(porta, motivo)` ANTES de abrir nada — para o cabeçalho do relatório."""
    caminho = (
        socket_path
        if socket_path is not None
        else os.environ.get(SOCKET_PATH_ENV, DEFAULT_SOCKET_PATH)
    )
    if not os.path.exists(caminho):
        return (PORTA_DIRETA, f"não há socket de broker em {caminho}")
    cliente = HidrawBrokerClient(caminho)
    try:
        vivo = cliente.ping()
    except Exception as exc:
        return (PORTA_DIRETA, f"o broker em {caminho} não respondeu ({exc})")
    finally:
        with contextlib.suppress(Exception):
            cliente.close()
    if vivo:
        return (PORTA_BROKER, f"o broker responde em {caminho}")
    return (PORTA_DIRETA, f"o socket {caminho} existe mas o broker não respondeu")


def estado_do_grab(
    caminho: str,
    *,
    abrir: Callable[..., int] = os.open,
    ioctl: Callable[..., Any] | None = None,
) -> str:
    """O `EVIOCGRAB` de um nó evdev está LIVRE, ou outro processo o segura?"""
    real_ioctl = ioctl
    if real_ioctl is None:
        import fcntl

        real_ioctl = fcntl.ioctl
    if not os.path.exists(caminho):
        return GRAB_SEM_NO
    try:
        fd = abrir(caminho, os.O_RDONLY | os.O_CLOEXEC)
    except PermissionError:
        return GRAB_SEM_PERMISSAO
    except OSError:
        return GRAB_DESCONHECIDO
    try:
        try:
            real_ioctl(fd, _EVIOCGRAB, 1)
        except OSError:
            return GRAB_DE_TERCEIRO
        with contextlib.suppress(OSError):
            real_ioctl(fd, _EVIOCGRAB, 0)
        return GRAB_LIVRE
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)


def linha_do_grab(caminho: str, estado: str) -> str:
    """A linha de cabeçalho do grab, no mesmo formato da porta."""
    return f"grab do evdev .... {caminho}: {estado}"


def leitura_de_zero(estado_grab: str) -> str:
    """O que escrever numa célula que contou ZERO — e isso DEPENDE do grab."""
    if estado_grab == GRAB_DE_TERCEIRO:
        return "MUDO (EVIOCGRAB de terceiro)"
    if estado_grab == GRAB_SEM_PERMISSAO:
        return "MUDO (sem permissão de leitura)"
    if estado_grab == GRAB_SEM_NO:
        return "MUDO (o nó sumiu)"
    if estado_grab == GRAB_DESCONHECIDO:
        return "0? (não sei dizer se pude ler)"
    return "0 (o controle não emitiu)"


__all__ = [
    "DEFAULT_SOCKET_PATH",
    "GRAB_DESCONHECIDO",
    "GRAB_DE_TERCEIRO",
    "GRAB_LIVRE",
    "GRAB_SEM_NO",
    "GRAB_SEM_PERMISSAO",
    "PORTA_BROKER",
    "PORTA_DIRETA",
    "SOCKET_PATH_ENV",
    "HidrawBrokerClient",
    "NoAberto",
    "PortaFechadaError",
    "abrir_hidraw",
    "broker_call_nonblocking",
    "broker_client_for",
    "broker_executor_for",
    "estado_do_grab",
    "leitura_de_zero",
    "linha_da_porta",
    "linha_do_grab",
    "make_broker_opener",
    "make_exposicao_factory",
    "porta_provavel",
]
