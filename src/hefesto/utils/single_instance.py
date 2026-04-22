"""Lock de instância única com modelo "última vence" (BUG-MULTI-INSTANCE-01).

Uma nova invocação de daemon ou GUI detecta o PID registrado no pid file,
envia `SIGTERM` ao predecessor (grace 2s, poll 50ms), escala para `SIGKILL`
se ainda vivo, e então adquire `fcntl.flock(LOCK_EX | LOCK_NB)` escrevendo
o próprio PID. O file descriptor é mantido aberto pelo processo — quando o
processo morre, o kernel libera o flock automaticamente.

Motivação: múltiplos daemons concorrentes criam devices `uinput` duplicados
e disputam `/dev/hidraw*`, causando cursor errático quando o toggle Mouse é
ligado. Múltiplas GUIs chamam `ensure_daemon_running()` em paralelo disparando
N `systemctl start` simultâneos. Ver armadilha A-10 em VALIDATOR_BRIEF.md.

API:
    pid = acquire_or_takeover("daemon")   # retorna PID do vencedor (os.getpid)
    alive = is_alive(pid)                 # predicado leve
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import signal
import time
from pathlib import Path

from hefesto.utils.logging_config import get_logger
from hefesto.utils.xdg_paths import runtime_dir

logger = get_logger(__name__)

SIGTERM_GRACE_SEC = 2.0
SIGTERM_POLL_INTERVAL_SEC = 0.05

# Mantém referência global ao fd para impedir GC (que fecharia o flock).
_HELD_LOCKS: dict[str, int] = {}


def _pid_file(name: str) -> Path:
    return runtime_dir(ensure=True) / f"{name}.pid"


def is_alive(pid: int) -> bool:
    """Retorna True se o processo existe e é sinalizável pelo user atual.

    `os.kill(pid, 0)` é a forma canônica POSIX. ESRCH => morto; EPERM =>
    vivo mas de outro usuário (tratamos como "vivo" por segurança).
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
    """SIGTERM com grace 2s, depois SIGKILL. No-op se já morreu."""
    if not is_alive(pid):
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
    """Adquire o lock para `name`, matando predecessor se houver.

    Retorna o PID do vencedor (sempre `os.getpid()`).

    O fd permanece aberto em `_HELD_LOCKS[name]` enquanto o processo vive.
    Em crash, o kernel libera flock automaticamente — o próximo `acquire`
    tratará o pid órfão no pid file via `is_alive()`.
    """
    path = _pid_file(name)
    predecessor = _read_existing_pid(path)
    if predecessor is not None and predecessor != os.getpid():
        if is_alive(predecessor):
            logger.info("single_instance_takeover_iniciado",
                        name=name, predecessor_pid=predecessor)
            _terminate_predecessor(predecessor)
        else:
            logger.debug("single_instance_pid_orfao", name=name, pid_antigo=predecessor)

    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                # Predecessor soltou SIGTERM mas ainda segura o flock — raro;
                # aguarda até 2s antes de escalar erro.
                deadline = time.monotonic() + SIGTERM_GRACE_SEC
                while time.monotonic() < deadline:
                    time.sleep(SIGTERM_POLL_INTERVAL_SEC)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        continue
                else:
                    os.close(fd)
                    raise RuntimeError(
                        f"Não foi possível adquirir lock {name} após takeover"
                    ) from exc
            else:
                os.close(fd)
                raise

        own_pid = os.getpid()
        os.ftruncate(fd, 0)
        os.write(fd, f"{own_pid}\n".encode("ascii"))
        os.fsync(fd)
    except Exception:
        os.close(fd)
        raise

    _HELD_LOCKS[name] = fd
    logger.info("single_instance_adquirido", name=name, pid=own_pid)
    return own_pid


def release(name: str) -> None:
    """Libera o lock explicitamente (útil para testes). No-op se ausente."""
    fd = _HELD_LOCKS.pop(name, None)
    if fd is None:
        return
    with contextlib.suppress(OSError):
        fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


__all__ = [
    "SIGTERM_GRACE_SEC",
    "acquire_or_takeover",
    "is_alive",
    "release",
]
