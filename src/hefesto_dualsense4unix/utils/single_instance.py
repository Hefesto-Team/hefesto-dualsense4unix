"""Lock de instância única — dois modelos disponíveis."""
from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import signal
import socket
import time
from collections.abc import Callable
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

logger = get_logger(__name__)

SIGTERM_GRACE_SEC = 2.0
SIGTERM_POLL_INTERVAL_SEC = 0.05

# ainda pertence ao Hefesto - DualSense4Unix (daemon ou GUI). Cobrimos dois padrões canônicos:
_HEFESTO_DUALSENSE4UNIX_PROC_MARKERS: tuple[str, ...] = ("hefesto",)

_HELD_LOCKS: dict[str, int] = {}


def _pid_file(name: str) -> Path:
    return runtime_dir(ensure=True) / f"{name}.pid"


def is_alive(pid: int) -> bool:
    """Retorna True se o processo existe e é sinalizável pelo user atual."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_proc_comm(pid: int) -> str | None:
    """Lê `/proc/<pid>/comm` (nome curto de até 16 chars). Retorna None em falha."""
    try:
        raw = Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    return raw.strip()


def _read_proc_cmdline(pid: int) -> str | None:
    """Lê `/proc/<pid>/cmdline` (args NUL-separados). Retorna None em falha."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _is_hefesto_dualsense4unix_process(pid: int) -> bool:
    """Confirma se o PID corresponde a um processo do Hefesto - DualSense4Unix.

    Defesa contra reciclagem de PID: o kernel pode reatribuir o PID a outro
    processo do mesmo usuário (firefox, script pessoal) após crash do daemon.
    Antes de enviar SIGTERM ao suposto predecessor, confirmamos via `/proc`.

    Heurística (inclusiva; qualquer match basta):
      1. `comm` contém "hefesto" (daemon rodando como entry point `hefesto`).
      2. `cmdline` contém "hefesto" (GUI rodando como
         `python3 <árvore>/scripts/abrir_interface.py` — o caminho da árvore já
         traz a palavra — ou daemon rodando como
         `python3 -m hefesto_dualsense4unix daemon start`).

    Falhas de leitura (processo sumiu, EPERM, ausência de `/proc`) retornam
    False — conservador: na dúvida, NÃO mata.
    """
    if pid <= 0:
        return False

    comm = _read_proc_comm(pid)
    if comm is not None:
        comm_lower = comm.lower()
        for marker in _HEFESTO_DUALSENSE4UNIX_PROC_MARKERS:
            if marker in comm_lower:
                return True

    cmdline = _read_proc_cmdline(pid)
    if cmdline is not None:
        cmdline_lower = cmdline.lower()
        for marker in _HEFESTO_DUALSENSE4UNIX_PROC_MARKERS:
            if marker in cmdline_lower:
                return True

    return False


def _read_existing_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("single_instance_read_falhou", path=str(path), err=str(exc))
        return None
    if not raw.isdigit():
        return None
    pid = int(raw)
    return pid if pid > 0 else None


def _terminate_predecessor(pid: int) -> None:
    """SIGTERM com grace 2s, depois SIGKILL. No-op se já morreu.

    Defesa em profundidade (AUDIT-FINDING-SINGLE-INSTANCE-PID-RECYCLE-01):
    antes de sinalizar, confirma via `/proc/<pid>/comm` e `/proc/<pid>/cmdline`
    que o processo ainda é do Hefesto - DualSense4Unix. Se o PID foi reciclado pelo kernel para
    outro processo do mesmo usuário, trata o pid file como órfão e retorna sem
    enviar nenhum sinal.
    """
    if not is_alive(pid):
        return
    if not _is_hefesto_dualsense4unix_process(pid):
        logger.warning(
            "single_instance_pid_reciclado",
            pid=pid,
            actual_comm=_read_proc_comm(pid),
            expected_marker=_HEFESTO_DUALSENSE4UNIX_PROC_MARKERS[0],
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        logger.warning("single_instance_sigterm_negado", pid=pid, err=str(exc))
        return

    deadline = time.monotonic() + SIGTERM_GRACE_SEC
    while time.monotonic() < deadline:
        if not is_alive(pid):
            logger.info("single_instance_predecessor_saiu_sigterm", pid=pid)
            return
        time.sleep(SIGTERM_POLL_INTERVAL_SEC)

    try:
        os.kill(pid, signal.SIGKILL)
        logger.warning("single_instance_sigkill_aplicado", pid=pid)
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        logger.warning("single_instance_sigkill_negado", pid=pid, err=str(exc))


def acquire_or_takeover(name: str) -> int:
    """Adquire o lock para `name`, matando predecessor se houver."""
    path = _pid_file(name)
    predecessor = _read_existing_pid(path)
    if predecessor is not None and predecessor != os.getpid():
        if is_alive(predecessor):
            logger.info("single_instance_takeover_iniciado",
                        name=name, predecessor_pid=predecessor)
            # do Hefesto - DualSense4Unix via `_is_hefesto_dualsense4unix_process`; PIDs reciclados viram no-op  # noqa: E501
            _terminate_predecessor(predecessor)
        else:
            logger.debug("single_instance_pid_orfao", name=name, pid_antigo=predecessor)

    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                deadline = time.monotonic() + SIGTERM_GRACE_SEC
                while time.monotonic() < deadline:
                    time.sleep(SIGTERM_POLL_INTERVAL_SEC)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        continue
                else:
                    raise RuntimeError(
                        f"Não foi possível adquirir lock {name} após takeover"
                    ) from exc
            else:
                raise

        own_pid = os.getpid()
        os.ftruncate(fd, 0)
        os.write(fd, f"{own_pid}\n".encode("ascii"))
        os.fsync(fd)
    except Exception:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise

    _HELD_LOCKS[name] = fd
    logger.info("single_instance_adquirido", name=name, pid=own_pid)
    return own_pid


def acquire_or_bring_to_front(
    name: str,
    bring_to_front_cb: Callable[[int], None],
    fallback_takeover_after_sec: float = 2.0,
) -> int | None:
    """Adquire o lock para `name` com modelo "primeira vence"."""
    path = _pid_file(name)
    predecessor = _read_existing_pid(path)

    if predecessor is not None and predecessor != os.getpid():
        if is_alive(predecessor) and not _is_hefesto_dualsense4unix_process(predecessor):
            logger.warning(
                "single_instance_pid_reciclado",
                name=name,
                pid=predecessor,
                actual_comm=_read_proc_comm(predecessor),
                expected_marker=_HEFESTO_DUALSENSE4UNIX_PROC_MARKERS[0],
            )
            predecessor = None
        if predecessor is not None and is_alive(predecessor):
            logger.info(
                "single_instance_bring_to_front",
                name=name,
                predecessor_pid=predecessor,
            )
            try:
                bring_to_front_cb(predecessor)
            except Exception as exc:
                logger.warning(
                    "single_instance_bring_to_front_cb_falhou",
                    pid=predecessor,
                    err=str(exc),
                )

            deadline = time.monotonic() + fallback_takeover_after_sec
            while time.monotonic() < deadline:
                if not is_alive(predecessor):
                    logger.warning(
                        "single_instance_predecessor_morreu_durante_bring_to_front",
                        pid=predecessor,
                    )
                    break
                time.sleep(SIGTERM_POLL_INTERVAL_SEC)
            else:
                logger.info(
                    "single_instance_predecessor_vivo_saindo_limpo",
                    name=name,
                    predecessor_pid=predecessor,
                )
                return None

            logger.info("single_instance_fallback_takeover", name=name, pid=predecessor)
        else:
            logger.debug("single_instance_pid_orfao", name=name, pid_antigo=predecessor)

    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                deadline = time.monotonic() + SIGTERM_GRACE_SEC
                while time.monotonic() < deadline:
                    time.sleep(SIGTERM_POLL_INTERVAL_SEC)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        continue
                else:
                    raise RuntimeError(
                        f"Não foi possível adquirir lock {name} (bring-to-front fallback)"
                    ) from exc
            else:
                raise

        own_pid = os.getpid()
        os.ftruncate(fd, 0)
        os.write(fd, f"{own_pid}\n".encode("ascii"))
        os.fsync(fd)
    except Exception:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise

    _HELD_LOCKS[name] = fd
    logger.info("single_instance_adquirido", name=name, pid=own_pid)
    return own_pid


_VARIAVEIS_DO_TOKEN: tuple[str, ...] = ("XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID")

_TETO_DO_PEDIDO = 4096

_ATENDIDO = b"ok\n"

ESPERA_PELA_RESPOSTA_SEC = 10.0

_PORTAS: dict[str, socket.socket] = {}


def _caminho_da_porta(name: str) -> Path:
    return runtime_dir(ensure=True) / f"{name}.porta"


def abrir_a_porta_de_frente(name: str) -> socket.socket:
    """Abre a porta por onde chegam os pedidos de vir à frente, e a devolve."""
    caminho = _caminho_da_porta(name)
    with contextlib.suppress(FileNotFoundError):
        caminho.unlink()
    porta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    porta.bind(str(caminho))
    os.chmod(caminho, 0o600)
    porta.listen(8)
    porta.setblocking(False)
    _PORTAS[name] = porta
    return porta


def porta_de_frente(name: str) -> socket.socket | None:
    """A porta que este processo abriu para ``name``, ou ``None``."""
    return _PORTAS.get(name)


def pedir_a_frente(name: str, pid: int) -> bool:
    """Pede ao dono da janela (``pid``) que a traga para a frente; ``True`` se ela atendeu."""
    token = next(
        (os.environ[v] for v in _VARIAVEIS_DO_TOKEN if os.environ.get(v)), ""
    )
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
            conexao.settimeout(1.0)
            conexao.connect(str(_caminho_da_porta(name)))
            conexao.sendall(token.encode("utf-8", errors="replace")[:_TETO_DO_PEDIDO - 1] + b"\n")
            conexao.settimeout(ESPERA_PELA_RESPOSTA_SEC)
            resposta = b""
            while not resposta.endswith(b"\n") and len(resposta) < len(_ATENDIDO):
                bloco = conexao.recv(len(_ATENDIDO))
                if not bloco:
                    break
                resposta += bloco
    except OSError as exc:
        logger.warning("single_instance_pedido_nao_chegou", name=name, pid=pid, err=str(exc))
        return False
    if resposta != _ATENDIDO:
        logger.warning("single_instance_janela_nao_respondeu", name=name, pid=pid)
        return False
    return True


def ler_o_pedido(porta: socket.socket) -> str | None | bool:
    """Atende UM pedido da fila da porta: o token, ``None`` sem token, ``False`` sem pedido."""
    try:
        conexao, _ = porta.accept()
    except (BlockingIOError, InterruptedError):
        return False
    with conexao:
        conexao.settimeout(0.5)
        dados = b""
        with contextlib.suppress(OSError):
            while b"\n" not in dados and len(dados) < _TETO_DO_PEDIDO:
                bloco = conexao.recv(_TETO_DO_PEDIDO)
                if not bloco:
                    break
                dados += bloco
        with contextlib.suppress(OSError):
            conexao.sendall(_ATENDIDO)
    token = dados.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
    return token or None


is_hefesto_dualsense4unix_process = _is_hefesto_dualsense4unix_process


def release(name: str) -> None:
    """Libera o lock (e a porta de frente, se houver) explicitamente. No-op se ausente."""
    porta = _PORTAS.pop(name, None)
    if porta is not None:
        with contextlib.suppress(OSError):
            porta.close()
    fd = _HELD_LOCKS.pop(name, None)
    if fd is None:
        return
    with contextlib.suppress(OSError):
        fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


__all__ = [
    "SIGTERM_GRACE_SEC",
    "_is_hefesto_dualsense4unix_process",
    "abrir_a_porta_de_frente",
    "acquire_or_bring_to_front",
    "acquire_or_takeover",
    "is_alive",
    "is_hefesto_dualsense4unix_process",
    "ler_o_pedido",
    "pedir_a_frente",
    "porta_de_frente",
    "release",
]
