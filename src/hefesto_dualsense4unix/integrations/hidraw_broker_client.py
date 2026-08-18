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
from dataclasses import dataclass
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
        #: Último estado CONHECIDO por nó ("hidden"/"exposed"), para logar a
        #: TRANSIÇÃO em vez da reafirmação (ver `_logar_transicao`). Lock
        #: próprio: `_request` já toma `self._lock` por dentro, e reentrar
        #: nele daqui travaria o cliente.
        self._estado_por_no: dict[str, str] = {}
        self._estado_lock = threading.Lock()

    # -- API pública -----------------------------------------------------

    def hide(self, node: str) -> bool:
        """Esconde `node` do uid da sessão. False = não escondeu (best-effort)."""
        response = self._request({"cmd": "hide", "node": node})
        ok = bool(response is not None and response.get("ok"))
        if ok:
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
        """`(fd, motivo)` — o `open` do broker COM a razão dita em português.

        A-PORTA-QUE-A-CASA-CONSTRUIU-01 (15/08/2026): `open_fd` devolve só
        `int | None`, e "None" não distingue *broker ausente* de *broker que
        recusou porque o nó é um vpad*. Para o daemon dá no mesmo — ele cai
        no `os.open` nos dois casos. Para um INSTRUMENTO não dá: um relatório
        que não diz por onde mediu é um relatório que não pode ser comparado
        com o do outro braço do ensaio, e o desenho 2+2 existe justamente
        para comparar dois braços. Toda a mecânica é a de `open_fd`; a única
        novidade é o `motivo`, que nunca é vazio.
        """
        with self._lock:
            response, fds = self._request_with_fds({"cmd": "open", "node": node})
        if response is not None and response.get("ok") and len(fds) == 1:
            # Achado Onda S #4: NADA entre a posse do fd e o `return` pode
            # levantar — um logger quebrado (stderr fechado num shutdown
            # malcronometrado, disco cheio no modo json) vazaria um fd REAL
            # do hidraw cedido pelo broker root, órfão até o processo morrer.
            estado = response.get("state")
            with contextlib.suppress(Exception):
                logger.info("hidraw_broker_fd_recebido", node=node, state=estado)
            return fds[0], f"o broker serviu o fd (nó {estado}) por {self._path}"
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
            return None, f"o broker devolveu {len(fds)} fds — protocolo violado"
        self._log_falha("open", node, response)
        if response is None:
            return None, f"o broker não respondeu em {self._path}"
        return None, f"o broker recusou: {response.get('error')}"

    def open_fd(self, node: str) -> int | None:
        """Pede ao broker um fd O_RDWR do nó. None = indisponível/recusado.

        O fd devolvido é do CHAMADOR (dono único; O_CLOEXEC garantido já na
        recepção via MSG_CMSG_CLOEXEC). Funciona com o nó ESCONDIDO — o
        broker é root, e é essa assimetria que o design explora. Nunca
        levanta e nunca re-tenta sozinho (§1.3): broker velho sem o cmd
        (`reject_unknown_cmd`), recusa, timeout ⇒ None, e o chamador
        (`make_broker_opener`) cai no `os.open` por caminho.
        """
        return self.abrir_no(node)[0]

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

    def _logar_transicao(
        self, evento: str, node: str, estado: str, **campos: Any
    ) -> None:
        """`info` quando o nó MUDA de estado; `debug` quando só reafirma.

        Medido em 15/08/2026 no journal da máquina dela: `hidraw_broker_hidden`
        saiu **717 vezes em 2 h 51** — quatro nós físicos vezes um laço de
        reconciliação a cada 30 s, sempre a mesma frase, sempre sobre nós que
        já estavam escondidos desde o primeiro minuto. O
        `daemon/battery_journal.py:55` já registrava o mesmo ruído em escala
        maior (14.105 ocorrências em 7 dias) e a casa respondeu criando um
        diário à parte, em vez de calar a origem.

        Isto não muda o que o `hide`/`restore` FAZEM — muda só o que eles
        registram. E importa porque este projeto diagnostica lendo o journal:
        um journal em que 717 de ~1.700 linhas são a mesma reafirmação enterra
        justamente o sinal raro (a transição, a falha, a porta declarada) que
        se foi ler ali.
        """
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


# ---------------------------------------------------------------------------
# A PORTA, DECLARADA — o que os INSTRUMENTOS usam (A-PORTA-QUE-A-CASA-CONSTRUIU-01)
# ---------------------------------------------------------------------------
#
# Defeito medido em 15/08/2026: com a mesa 2+2 montada, NENHUM dos quatro
# DualSense físicos abre por `open()` — o próprio Hefesto os esconde de
# propósito (`broker/hidraw_broker.py:416` — `setfacl -b` + `chmod 0600`), para
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
    """As DUAS portas falharam — e o erro diz o que cada uma respondeu.

    Nunca é levantado no lugar de um fallback: o fallback acontece, e só
    quando ele TAMBÉM falha é que isto sobe. A mensagem carrega as duas
    tentativas porque um instrumento que só diz "Permission denied" manda a
    próxima pessoa consertar a regra udev — que é o lugar errado, e foi o que
    aconteceu em 15/08/2026.
    """


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
    """Abre `no` pelo BROKER; se ele não servir, por `open()` — e DIZ qual foi.

    A ordem não é negociável: o broker primeiro, porque é o único caminho que
    funciona com o nó escondido (o estado normal da mesa com o co-op ligado).
    O `open()` direto é a queda para o caso em que o broker não existe (CI,
    install antigo, máquina de quem só rodou o checkout) — e para o vpad, que
    o broker recusa DE PROPÓSITO (`reject_not_physical_dualsense`: é por ele
    que o jogo fala com o controle, e escondê-lo seria o defeito).

    **Queda silenciosa é proibida.** O `motivo` nunca é vazio, nem no sucesso:
    quem lê o relatório tem de poder dizer se os dois braços do ensaio 2+2
    mediram pela mesma porta. Se as duas falharem, levanta `PortaFechadaError`
    com as duas respostas — nunca um `EACCES` pelado, que já mandou gente
    consertar a regra udev quando a regra estava certa.

    `cliente` é o ponto de injeção dos testes (qualquer objeto com `abrir_no`
    e `close`); `socket_path` aponta outro socket sem mexer no ambiente.
    """
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
    except Exception as exc:  # o instrumento nunca morre por causa da porta
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
    """`(porta, motivo)` ANTES de abrir nada — para o cabeçalho do relatório.

    Não abre nó nenhum: só pergunta se o socket do broker existe e responde.
    Serve ao instrumento que precisa declarar a porta no cabeçalho, antes da
    primeira linha de medição, e ao que nem chega a abrir hidraw (mas cuja
    medição depende de o físico estar escondido ou não).
    """
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
    except Exception as exc:  # diagnóstico nunca derruba instrumento
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
    """O `EVIOCGRAB` de um nó evdev está LIVRE, ou outro processo o segura?

    Existe porque *"o controle não emitiu"* e *"eu não posso ler"* saem os dois
    como zero, e um instrumento que não os separa produz calúnia contra o
    aparelho. Medido em 15/08/2026: com o co-op ativo, evento nenhum sai dos
    nós físicos — o daemon faz `EVIOCGRAB` neles, que é exclusivo, e isso é o
    produto FUNCIONANDO.

    Não existe consulta de estado do grab no kernel: a única prova é tentar.
    Então é isso que se faz — e o grab é **solto no mesmo instante**, dentro do
    `finally`, para que a janela em que este instrumento tira o controle de
    quem estava lendo seja de microssegundos. Se outro processo já o tem, a
    tentativa falha com `EBUSY` e NADA é tirado de ninguém, que é o caso que
    interessa.
    """
    real_ioctl = ioctl
    if real_ioctl is None:
        import fcntl  # local: nem todo instrumento que importa este módulo o usa

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
            # EBUSY (o caso do co-op) e qualquer outra recusa: alguém segura o
            # nó, ou o nó não aceita grab. Nos dois casos, o zero que este
            # instrumento medisse ali NÃO seria sobre o aparelho.
            return GRAB_DE_TERCEIRO
        with contextlib.suppress(OSError):
            real_ioctl(fd, _EVIOCGRAB, 0)  # devolve NA HORA o que se pegou
        return GRAB_LIVRE
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)


def linha_do_grab(caminho: str, estado: str) -> str:
    """A linha de cabeçalho do grab, no mesmo formato da porta."""
    return f"grab do evdev .... {caminho}: {estado}"


def leitura_de_zero(estado_grab: str) -> str:
    """O que escrever numa célula que contou ZERO — e isso DEPENDE do grab.

    A frase muda porque o fato muda. Com o grab de terceiro, zero não é uma
    medição do aparelho: é a marca de que este instrumento não estava lendo
    coisa alguma. Chamar os dois de "0" é a calúnia que a mordida 3 impede.
    """
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
    "porta_provavel",
]
