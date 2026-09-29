"""Lock de instância única — dois modelos disponíveis.

BUG-MULTI-INSTANCE-01: modelo "última vence" (`acquire_or_takeover`).
  Nova invocação detecta o PID registrado no pid file, envia `SIGTERM` ao
  predecessor (grace 2s, poll 50ms), escala para `SIGKILL` se ainda vivo, e
  então adquire `fcntl.flock(LOCK_EX | LOCK_NB)` escrevendo o próprio PID.
  Usado pelo daemon — ali "última vence" é desejado porque corrige disputas
  de hardware (cursor errático, dois uinput simultâneos).

BUG-TRAY-SINGLE-FLASH-01: modelo "primeira vence" (`acquire_or_bring_to_front`).
  Novo processo detecta predecessor vivo, chama `bring_to_front_cb(pid)` para
  trazer a janela ao foco e retorna None — o caller deve chamar `sys.exit(0)`.
  Se o predecessor não responder dentro de `fallback_takeover_after_sec`, aplica
  takeover como fallback (evita GUI zumbi travada). Usado pelo lançador da
  interface (`scripts/abrir_interface.py`) desde 28/09/2026: abrir o Hefesto com
  a janela já aberta traz a janela para a frente em vez de abrir outra.

  O PEDIDO VIAJA POR UM SOCKET UNIX, NUNCA POR SINAL (`abrir_a_porta_de_frente`,
  `pedir_a_frente` e `ler_o_pedido`, abaixo). O dono da janela escuta em
  ``<runtime>/<name>.porta``; o novo processo conecta e manda o token de
  ativação que o ambiente lhe deu (``XDG_ACTIVATION_TOKEN`` no Wayland,
  ``DESKTOP_STARTUP_ID`` no X), com o qual a janela se apresenta. Sem o token o
  compositor pode recusar o foco a uma janela que não recebeu clique.

  POR QUE NÃO O ``SIGUSR1`` DA JANELA GTK ANTIGA — medido em 28/09/2026 na
  bancada de tela: o JavaScriptCore do WebKit toma o ``SIGUSR1`` para o coletor
  de lixo (*"Overriding existing handler for signal 10"*), e o pedido do
  segundo clique DERRUBOU a janela aberta com falha de segmentação. Sinal é um
  recurso do processo inteiro, e a interface nova divide o processo com o
  WebKit; o socket é só nosso, e um pedido perdido nele custa no máximo a
  janela não vir à frente — nunca a janela.

  A JANELA RESPONDE, e quem pediu espera a resposta (``pedir_a_frente`` devolve
  ``True`` só com ela). Dono vivo não quer dizer janela viva: um laço do GTK
  parado aceita a conexão pelo kernel e nunca a atende. Sem resposta, o
  lançador abre a janela dele em vez de deixar o clique sem janela nenhuma.
"""
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

# Defesa em profundidade contra reciclagem de PID: antes de enviar SIGTERM ao
# predecessor declarado no pid file, confirmamos que o processo correspondente
# ainda pertence ao Hefesto - DualSense4Unix (daemon ou GUI). Cobrimos dois padrões canônicos:
#   - daemon: `comm` == "hefesto" (entry point instalado).
#   - GUI:    `comm` == "python3" e cmdline contém "hefesto" — hoje o caminho
#             é `python3 <árvore>/scripts/abrir_interface.py` (06/09/2026: era
#             `-m hefesto_dualsense4unix.app.main`, e esse módulo saiu com a
#             janela GTK, `D-0609-GTK-LEVA-INTEIRA`).
# Limite de `/proc/<pid>/comm` é 16 chars; "hefesto" cabe.
_HEFESTO_DUALSENSE4UNIX_PROC_MARKERS: tuple[str, ...] = ("hefesto",)

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
    # Argumentos são separados por NUL; trocamos por espaço para busca textual.
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
            # `_terminate_predecessor` valida internamente se o PID é realmente
            # do Hefesto - DualSense4Unix via `_is_hefesto_dualsense4unix_process`; PIDs reciclados viram no-op  # noqa: E501
            # (pid file tratado como órfão, sem SIGTERM ao alheio).
            _terminate_predecessor(predecessor)
        else:
            logger.debug("single_instance_pid_orfao", name=name, pid_antigo=predecessor)

    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    # BUG-SINGLE-INSTANCE-DOUBLE-CLOSE-01: os ramos internos de erro fazem
    # `os.close(fd); raise`, e o `except Exception` externo também fechava
    # → o segundo close levantava OSError(EBADF) que mascarava o erro
    # original e derrubava o daemon no boot, gerando ciclo de restart pelo
    # systemd (visível como "controle conecta/desconecta"). Centralizamos
    # o cleanup com `contextlib.suppress(OSError)` para tolerar double-close.
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
    """Adquire o lock para `name` com modelo "primeira vence".

    Se há predecessor vivo:
      1. Chama `bring_to_front_cb(predecessor_pid)` para trazer a janela ao foco.
      2. Aguarda até `fallback_takeover_after_sec` para confirmar que o predecessor
         respondeu (ainda vivo). Se ainda vivo após esse prazo, considera que o
         callback cumpriu seu papel — retorna None.
      3. Se o predecessor morreu durante a espera (zumbi/crash), aplica takeover
         como fallback, adquire o lock e retorna `os.getpid()`.

    Se não há predecessor vivo (ou pid file ausente/órfão):
      Adquire o lock normalmente e retorna `os.getpid()`.

    Retorna:
        `os.getpid()` se este processo se tornou o detentor do lock.
        `None` se um predecessor vivo foi encontrado e trazido ao foco —
        o caller deve chamar `sys.exit(0)`.

    Motivação (armadilha A-11): udev ADD dispara a unit `hefesto-dualsense4unix-gui-hotplug`
    duas vezes em <200ms. Com "última vence" a GUI2 matava a GUI1 causando
    efeito visual de "abre e fecha" no tray. Ver BUG-TRAY-SINGLE-FLASH-01.
    """
    path = _pid_file(name)
    predecessor = _read_existing_pid(path)

    if predecessor is not None and predecessor != os.getpid():
        if is_alive(predecessor) and not _is_hefesto_dualsense4unix_process(predecessor):
            # PID reciclado para processo alheio: trata como órfão.
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
            except Exception as exc:  # callback não deve travar o fluxo
                logger.warning(
                    "single_instance_bring_to_front_cb_falhou",
                    pid=predecessor,
                    err=str(exc),
                )

            # Aguarda `fallback_takeover_after_sec` verificando se predecessor
            # ainda responde. Se ainda vivo, retorna None (callback cumpriu papel).
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
                # Predecessor ainda vivo após prazo — callback funcionou.
                logger.info(
                    "single_instance_predecessor_vivo_saindo_limpo",
                    name=name,
                    predecessor_pid=predecessor,
                )
                return None

            # Fallback: predecessor morreu — adquire o lock abaixo.
            logger.info("single_instance_fallback_takeover", name=name, pid=predecessor)
        else:
            logger.debug("single_instance_pid_orfao", name=name, pid_antigo=predecessor)

    # Sem predecessor vivo: adquire o lock normalmente.
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    # BUG-SINGLE-INSTANCE-DOUBLE-CLOSE-01: mesmo cleanup centralizado de
    # acquire_or_takeover — evita EBADF no caminho de erro.
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


#: As variáveis em que o ambiente entrega o token de ativação a quem ele abriu,
#: na ordem de preferência: a do Wayland (``xdg-activation-v1``) e a do X
#: (startup-notification).
_VARIAVEIS_DO_TOKEN: tuple[str, ...] = ("XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID")

#: O teto de um pedido, em bytes: um token é uma linha curta.
_TETO_DO_PEDIDO = 4096

#: A resposta da janela que atendeu o pedido. Ela sai do laço do GLib da
#: janela, e é a única prova de que esse laço está girando.
_ATENDIDO = b"ok\n"

#: Quanto quem pede espera pela resposta, em segundos. Largo de propósito: um
#: segundo clique no meio do arranque espera a janela chegar ao laço do GTK
#: (o WebKit leva segundos para subir numa máquina lenta), e só uma janela que
#: passa disso sem responder conta como travada.
ESPERA_PELA_RESPOSTA_SEC = 10.0

#: As portas abertas por este processo, pelo mesmo motivo de ``_HELD_LOCKS``.
_PORTAS: dict[str, socket.socket] = {}


def _caminho_da_porta(name: str) -> Path:
    return runtime_dir(ensure=True) / f"{name}.porta"


def abrir_a_porta_de_frente(name: str) -> socket.socket:
    """Abre a porta por onde chegam os pedidos de vir à frente, e a devolve.

    Quem chama é o processo que VENCEU ``acquire_or_bring_to_front``, logo
    depois de vencer: a porta velha de um dono que morreu é apagada, e a nova
    nasce 0600, não bloqueante e fora dos filhos (``SOCK_CLOEXEC`` é o padrão
    do Python). Pedido que chega antes de o laço da janela escutar fica na fila
    do kernel e é atendido quando ele escutar — o arranque não perde pedido.
    """
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
    """Pede ao dono da janela (``pid``) que a traga para a frente; ``True`` se ela atendeu.

    É o ``bring_to_front_cb`` do lançador. Conecta na porta de ``name``, manda
    uma linha com o token de ativação deste processo (vazia se o ambiente não
    deu um) e espera a resposta, que sai do laço do GLib da janela
    (``ler_o_pedido``). Porta fechada, recusa ou silêncio viram ``False`` e só
    se registram: quem chama decide o que fazer com uma janela que não
    responde, e nunca a derruba.

    O ``False`` é o que separa a janela TRAVADA da janela que atendeu: o dono
    pode estar vivo (é o que ``acquire_or_bring_to_front`` confere) com o laço
    da janela parado, e aí não há o que trazer à frente.
    """
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
    """Atende UM pedido da fila da porta: o token, ``None`` sem token, ``False`` sem pedido.

    ``False`` quer dizer que não havia conexão esperando (a fila já foi
    esvaziada). Uma conexão que não manda a linha em meio segundo conta como
    pedido sem token: a janela vem à frente do mesmo jeito. Lido o pedido, a
    resposta volta a quem pediu (``pedir_a_frente`` espera por ela).
    """
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


# Alias público (CLUSTER-TRAY-POLISH-01): callers externos ao módulo usam o
# nome sem underscore. A função original (`_is_hefesto_dualsense4unix_process`)
# permanece como nome canônico interno e é referenciada pelos testes existentes
# em `tests/unit/test_single_instance.py`.
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
