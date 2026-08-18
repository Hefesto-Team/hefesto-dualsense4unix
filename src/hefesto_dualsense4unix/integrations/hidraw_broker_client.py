"""Cliente do broker root hide-hidraw (BROKER-01, Onda S) — a conexão É a lease.

O daemon abre UMA conexão longeva ao socket do broker
(`/run/hefesto-hidraw-broker/broker.sock`) e a mantém pela vida do processo.
Se o daemon morrer por QUALQUER via (crash, SIGKILL, OOM, takeover), o kernel
fecha o fd → o broker vê EOF → restaura todo hidraw que ESTA lease escondeu.
Por isso o cliente NUNCA fecha a conexão entre chamadas.

Contrato best-effort sagrado ("duplicado > zero controles"): broker ausente,
socket recusado, timeout — NADA levanta para o chamador; `hide`/`restore`
devolvem False, `open_fd` devolve None e o daemon segue como hoje (sem
esconder / abrindo por caminho). Protocolo JSON-por-linha, o mesmo do IPC do
daemon (spec §3 do estudo 2026-07-18-estudo-broker-hide-hidraw.md).

Onda S (desenho 2026-07-20 §1.3): o cmd `open` devolve um fd O_RDWR do nó
via SCM_RIGHTS na MESMA mensagem da resposta — o motion reader NUNCA reabre
o hidraw por caminho (o hide deixa de interagir com o ciclo de vida do gyro).
`make_broker_opener` é o opener injetável do `PhysicalReportReader`: broker
primeiro, `os.open` de fallback.

Lição 3 da auditoria que parkou a 1ª versão (§4.4 do desenho): a criação do
singleton em `broker_client_for` é feita sob lock de módulo (double-checked)
— duas threads do daemon criando clientes simultâneos faziam a lease
perdedora ser GC'd e desfazer hides. E `HidrawBrokerClient` NÃO tem `__del__`
de propósito: só `close()` explícito fecha a lease.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import struct
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Onde o systemd (hefesto-hidraw-broker.socket) escuta.
DEFAULT_SOCKET_PATH = "/run/hefesto-hidraw-broker/broker.sock"
#: Override do socket (testes/debug). A suíte hermética APONTA isto para um
#: caminho inexistente (conftest) — na máquina da mantenedora o broker REAL
#: está de pé e um teste que resolvesse o default esconderia hidraw de verdade.
SOCKET_PATH_ENV = "HEFESTO_BROKER_SOCKET"
#: Timeout por operação — o hide roda no caminho do start da emulação; um
#: broker travado não pode congelar o daemon.
_TIMEOUT_S = 2.0
#: Resposta maior que isto é lixo — corta e derruba a conexão.
_MAX_RESPONSE_BYTES = 65536

#: Um fd serializado no ancillary (SCM_RIGHTS empacota int32 nativo).
_FD_INT_SIZE = struct.calcsize("i")
#: Espaço de ancillary para ATÉ 2 fds DE PROPÓSITO (§1.3): se o broker (ou um
#: impostor no socket) mandar 2+, queremos RECEBÊ-los para poder FECHÁ-los —
#: com espaço para só 1 o excesso seria descartado pelo kernel com MSG_CTRUNC
#: (também tratado: a conexão inteira é abortada).
_ANCILLARY_SPACE = socket.CMSG_SPACE(2 * _FD_INT_SIZE)

#: Lição 3 (§4.4a): criação do singleton por daemon sob lock de módulo —
#: sem ele, duas threads criariam duas leases e a perdedora, ao ser GC'd,
#: fecharia o socket (EOF) e o broker restauraria hides da vida ativa.
_CLIENT_CREATION_LOCK = threading.Lock()

#: Achados Onda S #5/#6/#10: criação do executor DEDICADO (1 worker) das
#: operações do broker, sob o mesmo padrão de double-check do cliente.
_EXECUTOR_CREATION_LOCK = threading.Lock()

#: Fallback de módulo para daemon exótico sem atributo gravável — nunca criar
#: um executor NOVO por chamada (vazaria uma thread por hide/restore).
_FALLBACK_EXECUTOR: ThreadPoolExecutor | None = None


class HidrawBrokerClient:
    """Conexão-lease com o broker + hide/restore/restore_all/open_fd/status.

    Thread-safe (lock único): os hooks chamam do executor do daemon, do event
    loop e da thread do motion reader. Reconexão lazy com UMA retentativa por
    chamada de hide/restore — se o broker reiniciou (a lease velha morreu, e
    com ela o estado escondido foi restaurado pelo próprio broker), a chamada
    seguinte abre lease nova. `open_fd` NÃO re-tenta (§1.3): quem re-tenta é
    o loop do reader, com o backoff próprio — evita dupla-espera no caminho
    do gyro. Sem `__del__` de propósito (lição 3): GC de um cliente duplicado
    acidental nunca dispara restore.
    """

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

    # -- API pública -----------------------------------------------------

    def hide(self, node: str) -> bool:
        """Esconde `node` do uid da sessão. False = não escondeu (best-effort)."""
        response = self._request({"cmd": "hide", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            logger.info("hidraw_broker_hidden", node=node)
        else:
            self._log_falha("hide", node, response)
        return ok

    def restore(self, node: str) -> bool:
        """Restaura o acesso a `node`. False = broker indisponível/erro."""
        response = self._request({"cmd": "restore", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
            logger.info(
                "hidraw_broker_restored",
                node=node,
                state=response.get("state") if response else None,
            )
        else:
            self._log_falha("restore", node, response)
        return ok

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

    def open_fd(self, node: str) -> int | None:
        """Pede ao broker um fd O_RDWR do nó. None = indisponível/recusado.

        O fd devolvido é do CHAMADOR (dono único; O_CLOEXEC garantido já na
        recepção via MSG_CMSG_CLOEXEC). Funciona com o nó ESCONDIDO — o
        broker é root, e é essa assimetria que o design explora. Nunca
        levanta e nunca re-tenta sozinho (§1.3): broker velho sem o cmd
        (`reject_unknown_cmd`), recusa, timeout ⇒ None, e o chamador
        (`make_broker_opener`) cai no `os.open` por caminho.
        """
        with self._lock:
            response, fds = self._request_with_fds({"cmd": "open", "node": node})
        if response is not None and response.get("ok") and len(fds) == 1:
            # Achado Onda S #4: NADA entre a posse do fd e o `return` pode
            # levantar — um logger quebrado (stderr fechado num shutdown
            # malcronometrado, disco cheio no modo json) vazaria um fd REAL
            # do hidraw cedido pelo broker root, órfão até o processo morrer.
            with contextlib.suppress(Exception):
                logger.info(
                    "hidraw_broker_fd_recebido", node=node, state=response.get("state")
                )
            return fds[0]
        # Qualquer outra combinação é anomalia: fecha TUDO que veio (mais de
        # um fd = protocolo violado; fd com ok:false = broker bugado). Nunca
        # sai daqui com fd órfão.
        for fd in fds:
            with contextlib.suppress(OSError):
                os.close(fd)
        if response is not None and response.get("ok"):
            logger.warning(
                "hidraw_broker_fd_count_invalido", node=node, count=len(fds)
            )
        else:
            self._log_falha("open", node, response)
        return None

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

    # -- interno ---------------------------------------------------------

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
                    # Lease morta (broker reiniciou?): derruba e tenta UMA vez.
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
        """Uma requisição → (resposta, fds recebidos). Chamado sob `self._lock`.

        Diferente de `_request`: SEM retentativa (dupla-espera no caminho do
        gyro é proibida) e com recepção de ancillary (SCM_RIGHTS). Decisões
        obrigatórias do §1.3, todas aqui:
          - `MSG_CMSG_CLOEXEC`: o kernel instala O_CLOEXEC no fd JÁ NA
            RECEPÇÃO — sem janela em que um fork/exec do daemon vazaria o
            hidraw para um filho;
          - `MSG_CTRUNC` derruba a conexão inteira (fds possivelmente
            descartados pelo kernel do NOSSO lado — não dá para saber o que
            se perdeu; lease nova na próxima chamada);
          - EINTR: PEP 475 — `recvmsg` re-tenta sozinho; timeout do socket
            vira `socket.timeout` (subclasse de OSError) ⇒ fecha tudo;
          - fds parciais: se a resposta chegou em pedaços e o erro veio no
            meio, TODO fd já acumulado é fechado no except. Nenhum caminho
            de código sai daqui com fd órfão.
        """
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
                # Colhe os fds ENTREGUES antes de qualquer veredito: fd que
                # chegou no ancillary já está aberto no NOSSO processo — se o
                # raise viesse primeiro, o except não saberia fechá-los.
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
                # Uma vez por vida do cliente: broker ausente é degradação
                # esperada (install antigo/CI) — o resto vai em DEBUG.
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

    def _log_falha(
        self, cmd: str, node: str | None, response: dict[str, Any] | None
    ) -> None:
        # DEBUG de propósito: com o broker ausente TODO grab/reopen logaria —
        # o rastro visível é o `hidraw_broker_unavailable` único da conexão.
        logger.debug(
            "hidraw_broker_cmd_failed",
            cmd=cmd,
            node=node,
            error=(response or {}).get("error"),
        )


def broker_client_for(daemon: Any) -> Any:
    """Cliente-lease singleton por daemon (lazy) — dublês de teste passam direto.

    O cliente vive em `daemon._hidraw_broker_client`; testes injetam um fake
    ali e ele é respeitado. Criação sob lock de módulo com double-check
    (lição 3/§4.4a): duas threads correndo aqui criavam duas leases e a
    perdedora, GC'd, desfazia hides da vencedora. Nunca levanta: daemon sem o
    atributo gravável devolve o cliente sem cachear (funciona, só não reusa a
    lease — caso teórico).
    """
    client = getattr(daemon, "_hidraw_broker_client", None)
    if client is not None:
        return client
    with _CLIENT_CREATION_LOCK:
        client = getattr(daemon, "_hidraw_broker_client", None)
        if client is not None:
            return client
        client = HidrawBrokerClient()
        # Daemon exótico sem atributo gravável funciona igual (sem cache).
        with contextlib.suppress(AttributeError, TypeError):
            daemon._hidraw_broker_client = client
    return client


def broker_executor_for(daemon: Any) -> ThreadPoolExecutor:
    """Executor DEDICADO (1 worker) das operações do broker, lazy por daemon.

    Achados Onda S #5/#6/#10: 1 worker de propósito — a fila FIFO preserva a
    ordem hide/restore submetida pela thread do event loop (dois workers
    poderiam reordenar um hide atrás do restore do mesmo nó). Vive em
    `daemon._hidraw_broker_executor` (o shutdown do daemon o desliga com
    `cancel_futures=True` antes de fechar a lease). Daemon exótico sem
    atributo gravável cai num fallback de módulo (nunca um executor novo por
    chamada — vazaria uma thread por hide).

    PÚBLICO desde o corretor final (interação S x HANG-01, achado #6): o
    `rehide_physical_hidraw` do reconnect_loop também precisa rodar AQUI —
    despachá-lo no pool compartilhado 'hefesto-hid' (2 workers) deixava um
    broker lento (até ~8s por nó) ocupando o pool do qual read_state/
    _gather_game_signal_inputs/heal dependem, o mesmo padrão que o HANG-01
    baniu ao isolar `_sync_external_leds`.
    """
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
    """Executa uma operação do cliente do broker SEM bloquear o event loop.

    Achados Onda S #5/#6/#10 (a mesma classe do HANG-01): `hide`/`restore`/
    `restore_all` fazem I/O de socket bloqueante — timeout de 2 s vezes até
    2 tentativas, ~4 s no pior caso. Rodando na thread do event loop (poll
    loop via `coop.sync()`, handlers IPC via `set_gamepad_emulation`/
    `set_coop_enabled`), um broker lento congelava TODOS os jogadores e o
    IPC inteiro. Regra (desenho da onda §9: "hide/restore best-effort jamais
    bloqueiam start/stop da emulação"):

    - NA thread do event loop ⇒ AGENDA no executor dedicado de 1 worker
      (FIFO preserva a ordem hide/restore) e retorna na hora;
    - FORA do event loop (rehide via `_run_blocking`, shutdown síncrono,
      testes) ⇒ executa INLINE — o comportamento síncrono que esses
      chamadores já esperam.

    Best-effort integral: nenhuma exceção escapa (duplicado > zero
    controles); executor já desligado (shutdown) descarta em silêncio — o
    close/EOF da lease restaura o que restou.
    """
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
    """Opener p/ `PhysicalReportReader`: broker primeiro, `os.open` de fallback.

    - broker responde `open` ⇒ fd root-aberto (funciona com o nó ESCONDIDO);
    - broker ausente/recusa/timeout/dublê sem `open_fd` ⇒ `os.open` por
      caminho (o comportamento de hoje; se o nó estiver escondido isso dá
      EACCES e o backoff do reader cobre — só acontece na janela
      broker-morto, em que o próprio broker/systemd já restaurou tudo via
      EOF/ExecStopPost).

    Contrato com o reader (§6.2): devolve fd pronto para select/read; levanta
    OSError em falha (o loop trata com o backoff existente). O fd via broker
    já chega CLOEXEC (MSG_CMSG_CLOEXEC) — GYRO-FD-01 intacto: quem abre/fecha
    é sempre a própria thread do reader.
    """

    def _open(path: str) -> int:
        fd: int | None = None
        with contextlib.suppress(Exception):
            fd = broker_client_for(daemon).open_fd(path)
        if fd is not None:
            return fd
        return os.open(path, os.O_RDONLY)

    return _open


__all__ = [
    "DEFAULT_SOCKET_PATH",
    "SOCKET_PATH_ENV",
    "HidrawBrokerClient",
    "broker_call_nonblocking",
    "broker_client_for",
    "broker_executor_for",
    "make_broker_opener",
]
