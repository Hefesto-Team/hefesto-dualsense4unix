"""Cliente-lease do broker (BROKER-01, Onda S) — ponta a ponta em socket real.

O servidor é o Broker de verdade (thread própria) com fs FAKE e validador
injetado — nenhum /dev real é tocado; e um servidor ROTEIRIZADO cobre as
anomalias que o broker são nunca produziria. Prova:
- hide/restore/restore_all/status/ping viajam pelo protocolo JSON-por-linha;
- a conexão é UMA e longeva (a lease): fechar o cliente restaura no servidor;
- broker AUSENTE = best-effort silencioso (False/None, nunca exceção) — a
  regra sagrada "duplicado > zero controles";
- `open_fd` (§1.3 do desenho 2026-07-20): exatamente 1 fd por resposta ok,
  CLOEXEC já na recepção, mesmo inode do alvo; 2+ fds ⇒ fecha TUDO e devolve
  None; MSG_CTRUNC ⇒ conexão abortada; fd junto de ok:false ⇒ fechado;
  broker velho sem o cmd (`reject_unknown_cmd`) ⇒ None; timeout ⇒ None.
  O vazamento é detectado por EOF de pipe: se o cliente NÃO fechar as cópias
  recebidas, o read-end nunca vê EOF e o teste falha;
- `broker_client_for` respeita o dublê injetado, cacheia o real e cria o
  singleton sob lock (lição 3: corrida de criação nunca gera duas leases);
  `HidrawBrokerClient` NÃO tem `__del__` (GC de duplicata nunca fecha lease).
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import select
import socket
import struct
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc


class FakeOps:
    """Dublê de fs com as assinaturas REAIS do FsAclOps (nada de /dev)."""

    def __init__(self, target: str | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.target = target

    def hide(self, node: str, base: str) -> None:
        self.calls.append(("hide", node))

    def restore(self, node: str, base: str, uid: int) -> None:
        self.calls.append(("restore", node, uid))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return True

    def open_node(self, node: str, base: str) -> int:
        self.calls.append(("open_node", node))
        assert self.target is not None
        return os.open(self.target, os.O_RDONLY | os.O_CLOEXEC)


def _validator(node: str) -> str | None:
    base = node.rsplit("/", 1)[-1]
    return base if base in {"hidraw3", "hidraw7"} else None


def _short_socket_dir(tmp_path: Path) -> str:
    """Diretório curto para o socket: sun_path tem limite de ~108 bytes.

    O tmp_path do pytest pode morar num TMPDIR profundo (o scratchpad desta
    máquina passa de 100 chars) — nesse caso caímos num mkdtemp direto em
    /tmp, limpo pelo próprio teste.
    """
    candidato = tmp_path / "bk"
    if len(str(candidato / "broker.sock")) <= 90:
        candidato.mkdir(exist_ok=True)
        return str(candidato)
    return tempfile.mkdtemp(prefix="hefesto-bk-", dir="/tmp")


def _cleanup_socket_dir(sockdir: str, path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)
    if sockdir.startswith("/tmp/hefesto-bk-"):
        os.rmdir(sockdir)


def _espera(cond: Callable[[], bool], timeout: float = 2.0) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


def _eof_no_pipe(read_fd: int, timeout: float = 2.0) -> bool:
    """True quando TODAS as cópias do write-end fecharam (EOF no read-end).

    É o detector de vazamento de fd dos testes de `open_fd`: o servidor envia
    cópias do write-end e fecha as locais — se o CLIENTE não fechar as que
    recebeu, o EOF nunca chega e isto devolve False.
    """

    def _ver() -> bool:
        pronto, _, _ = select.select([read_fd], [], [], 0)
        if not pronto:
            return False
        return os.read(read_fd, 1) == b""

    return _espera(_ver, timeout)


@pytest.fixture()
def live_broker(tmp_path: Path) -> Any:
    """Broker real numa thread + socket unix real; fs é o FakeOps."""
    sockdir = _short_socket_dir(tmp_path)
    path = os.path.join(sockdir, "broker.sock")
    target = tmp_path / "alvo-do-fd"
    target.write_bytes(b"hidraw fake")
    listen = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listen.bind(path)
    listen.listen(4)
    ops = FakeOps(target=str(target))
    state = BrokerState(
        allowed_uid=os.getuid(), ops=ops, validator=_validator, log=lambda *a, **k: None
    )
    broker = Broker(state, listen, log=lambda *a, **k: None)
    thread = threading.Thread(target=broker.run, daemon=True)
    thread.start()
    try:
        yield path, state, ops, str(target)
    finally:
        broker.stopping = True
        # Acorda o selector (senão o run espera o timeout de 1s inteiro).
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as poke,
            contextlib.suppress(OSError),
        ):
            poke.connect(path)
        thread.join(timeout=3.0)
        listen.close()
        _cleanup_socket_dir(sockdir, path)


class TestClienteVivo:
    def test_hide_e_status(self, live_broker: Any) -> None:
        path, _state, ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            assert cliente.ping() is True
            assert cliente.hide("/dev/hidraw3") is True
            assert ("hide", "/dev/hidraw3") in ops.calls
            status = cliente.status()
            assert status is not None and status["hidden"] == ["/dev/hidraw3"]
        finally:
            cliente.close()

    def test_hide_recusado_para_nao_fisico(self, live_broker: Any) -> None:
        path, _state, ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            assert cliente.hide("/dev/hidraw6") is False  # "vpad" do validador
            assert ops.calls == []
        finally:
            cliente.close()

    def test_restore_e_restore_all(self, live_broker: Any) -> None:
        path, state, ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            cliente.hide("/dev/hidraw3")
            cliente.hide("/dev/hidraw7")
            assert cliente.restore("/dev/hidraw3") is True
            assert cliente.restore_all() is True
            assert state.hidden == {}
            assert len([c for c in ops.calls if c[0] == "restore"]) == 2
        finally:
            cliente.close()

    def test_close_da_lease_restaura_no_servidor(self, live_broker: Any) -> None:
        # O fail-safe visto do lado do cliente: fechar a lease (= daemon
        # morrendo) restaura tudo sem nenhum comando extra.
        path, state, ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        cliente.hide("/dev/hidraw3")
        assert "/dev/hidraw3" in state.hidden
        cliente.close()
        assert _espera(lambda: state.hidden == {})
        assert ("restore", "/dev/hidraw3", os.getuid()) in ops.calls

    def test_conexao_unica_e_longeva(self, live_broker: Any) -> None:
        path, state, _ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            cliente.ping()
            cliente.hide("/dev/hidraw3")
            cliente.status()
            cliente.open_fd("/dev/hidraw6")  # recusado — mas na MESMA lease
            # UMA lease só: o estado por-conexão do servidor tem 1 entrada.
            assert _espera(lambda: len(state.by_conn) == 1)
        finally:
            cliente.close()


class TestOpenFdContraOBrokerReal:
    def test_fd_chega_cloexec_e_do_mesmo_inode(self, live_broker: Any) -> None:
        path, _state, ops, target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            fd = cliente.open_fd("/dev/hidraw3")
            assert fd is not None
            try:
                assert os.fstat(fd).st_ino == os.stat(target).st_ino
                # CLOEXEC instalado JÁ na recepção (MSG_CMSG_CLOEXEC).
                assert fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
            finally:
                os.close(fd)
            assert ("open_node", "/dev/hidraw3") in ops.calls
        finally:
            cliente.close()

    def test_open_funciona_com_o_no_escondido(self, live_broker: Any) -> None:
        # A razão da onda: hide NÃO bloqueia o caminho de fd do reader.
        path, state, _ops, target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            assert cliente.hide("/dev/hidraw3") is True
            assert "/dev/hidraw3" in state.hidden
            fd = cliente.open_fd("/dev/hidraw3")
            assert fd is not None
            assert os.fstat(fd).st_ino == os.stat(target).st_ino
            os.close(fd)
        finally:
            cliente.close()

    def test_recusa_devolve_none_sem_fd(self, live_broker: Any) -> None:
        path, _state, ops, _target = live_broker
        cliente = hbc.HidrawBrokerClient(path)
        try:
            assert cliente.open_fd("/dev/hidraw6") is None
            assert not any(c[0] == "open_node" for c in ops.calls)
        finally:
            cliente.close()


class _ServidorRoteirizado:
    """Servidor unix mínimo: responde cada linha pelo roteiro por cmd.

    roteiro[cmd] = callable(conn, request) que envia a resposta (com ou sem
    fds); roteiro[cmd] = None simula broker TRAVADO (nunca responde); cmd
    fora do roteiro recebe `reject_unknown_cmd` (como o broker real faz).
    """

    def __init__(self, path: str, roteiro: dict[str, Any]) -> None:
        self.path = path
        self.roteiro = roteiro
        self._listen = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listen.bind(path)
        self._listen.listen(2)
        self._listen.settimeout(0.2)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._listen.accept()
            except (TimeoutError, OSError):
                continue
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        buf = bytearray()
        try:
            while not self._stop.is_set():
                data = conn.recv(4096)
                if not data:
                    return
                buf.extend(data)
                while b"\n" in buf:
                    line, _, resto = bytes(buf).partition(b"\n")
                    buf = bytearray(resto)
                    request = json.loads(line)
                    cmd = request.get("cmd")
                    if cmd not in self.roteiro:
                        resposta = {"ok": False, "cmd": cmd, "error": "reject_unknown_cmd"}
                        conn.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
                        continue
                    handler = self.roteiro[cmd]
                    if handler is None:
                        continue  # broker "travado": nunca responde
                    handler(conn, request)
        except OSError:
            return
        finally:
            with contextlib.suppress(OSError):
                conn.close()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._listen.close()
        with contextlib.suppress(OSError):
            os.unlink(self.path)


def _responde_ping(conn: socket.socket, _req: dict[str, Any]) -> None:
    conn.sendall(b'{"ok": true, "cmd": "ping"}\n')


def _handler_fds(payload: dict[str, Any], write_fd: int, copias: int) -> Any:
    """Handler que envia `copias` duplicatas de `write_fd` junto da resposta
    e fecha a cópia local NA HORA — a partir daí, só o cliente segura o pipe
    aberto (o EOF do read-end denuncia vazamento)."""

    def _h(conn: socket.socket, _req: dict[str, Any]) -> None:
        line = json.dumps(payload).encode("utf-8") + b"\n"
        packed = struct.pack(f"{copias}i", *([write_fd] * copias))
        conn.sendmsg([line], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, packed)])
        os.close(write_fd)

    return _h


@pytest.fixture()
def sock_path(tmp_path: Path) -> Any:
    sockdir = _short_socket_dir(tmp_path)
    path = os.path.join(sockdir, "roteiro.sock")
    yield path
    _cleanup_socket_dir(sockdir, path)


class TestOpenFdAnomalias:
    def test_dois_fds_fecha_tudo_e_devolve_none(self, sock_path: str) -> None:
        # Contrato §1.3: MAIS de um fd = protocolo violado ⇒ fecha todos.
        lido, escrita = os.pipe()
        servidor = _ServidorRoteirizado(
            sock_path,
            {
                "ping": _responde_ping,
                "open": _handler_fds(
                    {"ok": True, "cmd": "open", "state": "exposed"}, escrita, 2
                ),
            },
        )
        cliente = hbc.HidrawBrokerClient(sock_path)
        try:
            assert cliente.ping() is True
            assert cliente.open_fd("/dev/hidraw3") is None
            # As DUAS cópias recebidas foram fechadas: EOF no read-end.
            assert _eof_no_pipe(lido)
        finally:
            cliente.close()
            servidor.close()
            with contextlib.suppress(OSError):
                os.close(lido)

    def test_msg_ctrunc_aborta_a_conexao_sem_vazar(self, sock_path: str) -> None:
        # 3 fds não cabem no CMSG_SPACE de 2 do cliente ⇒ MSG_CTRUNC: o que
        # foi entregue é fechado, o resto o kernel descarta, e a LEASE cai.
        lido, escrita = os.pipe()
        servidor = _ServidorRoteirizado(
            sock_path,
            {
                "ping": _responde_ping,
                "open": _handler_fds(
                    {"ok": True, "cmd": "open", "state": "exposed"}, escrita, 3
                ),
            },
        )
        cliente = hbc.HidrawBrokerClient(sock_path)
        try:
            assert cliente.ping() is True
            assert cliente.open_fd("/dev/hidraw3") is None
            assert _eof_no_pipe(lido)
            assert cliente._sock is None  # conexão inteira abortada
        finally:
            cliente.close()
            servidor.close()
            with contextlib.suppress(OSError):
                os.close(lido)

    def test_fd_junto_de_ok_false_e_fechado(self, sock_path: str) -> None:
        lido, escrita = os.pipe()
        servidor = _ServidorRoteirizado(
            sock_path,
            {
                "open": _handler_fds(
                    {"ok": False, "cmd": "open", "error": "open_failed"}, escrita, 1
                )
            },
        )
        cliente = hbc.HidrawBrokerClient(sock_path)
        try:
            assert cliente.open_fd("/dev/hidraw3") is None
            assert _eof_no_pipe(lido)
        finally:
            cliente.close()
            servidor.close()
            with contextlib.suppress(OSError):
                os.close(lido)

    def test_broker_velho_sem_cmd_open_vira_none(self, sock_path: str) -> None:
        # §1.4: reject_unknown_cmd ⇒ None ⇒ o opener cai no os.open — nunca
        # há janela de versão que quebre o gyro.
        servidor = _ServidorRoteirizado(sock_path, {"ping": _responde_ping})
        cliente = hbc.HidrawBrokerClient(sock_path)
        try:
            assert cliente.open_fd("/dev/hidraw3") is None
            assert cliente.ping() is True  # a lease sobreviveu à recusa limpa
        finally:
            cliente.close()
            servidor.close()

    def test_timeout_devolve_none_e_derruba_a_lease(self, sock_path: str) -> None:
        servidor = _ServidorRoteirizado(
            sock_path, {"ping": _responde_ping, "open": None}
        )
        cliente = hbc.HidrawBrokerClient(sock_path, timeout_s=0.2)
        try:
            assert cliente.ping() is True
            inicio = time.monotonic()
            assert cliente.open_fd("/dev/hidraw3") is None
            assert (time.monotonic() - inicio) < 1.5
            assert cliente._sock is None
        finally:
            cliente.close()
            servidor.close()

    def test_logger_quebrado_nao_vaza_o_fd(
        self, sock_path: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Achado Onda S #4: com o fd JÁ recebido, um `logger.info` que
        # levanta (stderr fechado num shutdown malcronometrado, disco cheio)
        # não pode custar o fd — antes a exceção escapava entre a recepção e
        # o `return`, o chamador (`make_broker_opener`) a engolia com
        # suppress(Exception) e o fd ficava órfão para sempre.
        lido, escrita = os.pipe()
        servidor = _ServidorRoteirizado(
            sock_path,
            {
                "ping": _responde_ping,
                "open": _handler_fds(
                    {"ok": True, "cmd": "open", "state": "hidden"}, escrita, 1
                ),
            },
        )
        cliente = hbc.HidrawBrokerClient(sock_path)
        # A lease abre ANTES do logger quebrar (o cenário do achado: o stderr
        # morre no meio da vida do daemon, com a conexão já de pé).
        assert cliente.ping() is True

        class _LoggerQuebrado:
            def info(self, *a: Any, **k: Any) -> None:
                raise OSError("stderr fechado")

            def debug(self, *a: Any, **k: Any) -> None: ...

            def warning(self, *a: Any, **k: Any) -> None: ...

        monkeypatch.setattr(hbc, "logger", _LoggerQuebrado())
        try:
            fd = cliente.open_fd("/dev/hidraw3")
            # O fd chega MESMO com o logger explodindo — e é do chamador.
            assert fd is not None
            os.close(fd)
            assert _eof_no_pipe(lido)
        finally:
            cliente.close()
            servidor.close()
            with contextlib.suppress(OSError):
                os.close(lido)

    def test_resposta_nao_json_fecha_fds(self, sock_path: str) -> None:
        lido, escrita = os.pipe()

        def _lixo(conn: socket.socket, _req: dict[str, Any]) -> None:
            packed = struct.pack("i", escrita)
            conn.sendmsg([b"isto nao e json\n"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, packed)])
            os.close(escrita)

        servidor = _ServidorRoteirizado(sock_path, {"open": _lixo})
        cliente = hbc.HidrawBrokerClient(sock_path)
        try:
            assert cliente.open_fd("/dev/hidraw3") is None
            assert _eof_no_pipe(lido)
        finally:
            cliente.close()
            servidor.close()
            with contextlib.suppress(OSError):
                os.close(lido)


class TestClienteSemBroker:
    def test_tudo_best_effort_sem_excecao(self, tmp_path: Path) -> None:
        cliente = hbc.HidrawBrokerClient(str(tmp_path / "nao-existe.sock"))
        assert cliente.is_available() is False
        assert cliente.hide("/dev/hidraw3") is False
        assert cliente.restore("/dev/hidraw3") is False
        assert cliente.restore_all() is False
        assert cliente.ping() is False
        assert cliente.status() is None
        assert cliente.open_fd("/dev/hidraw3") is None
        cliente.close()  # idempotente

    def test_default_honra_env_de_isolamento(self, tmp_path: Path) -> None:
        # O conftest aponta HEFESTO_BROKER_SOCKET para um caminho inexistente:
        # o cliente DEFAULT nunca alcança o broker real da máquina.
        cliente = hbc.HidrawBrokerClient()
        assert cliente._path == os.environ["HEFESTO_BROKER_SOCKET"]
        assert cliente.is_available() is False


class TestBrokerClientFor:
    def test_respeita_duble_injetado(self) -> None:
        class Daemon:
            _hidraw_broker_client = "fake-injetado"

        assert hbc.broker_client_for(Daemon()) == "fake-injetado"

    def test_cria_e_cacheia_no_daemon(self) -> None:
        class Daemon:
            _hidraw_broker_client: Any = None

        daemon = Daemon()
        cliente = hbc.broker_client_for(daemon)
        assert isinstance(cliente, hbc.HidrawBrokerClient)
        assert daemon._hidraw_broker_client is cliente
        assert hbc.broker_client_for(daemon) is cliente

    def test_criacao_concorrente_produz_um_singleton(self) -> None:
        # Lição 3 (§4.4a): a corrida de criação não pode gerar duas leases —
        # a perdedora seria GC'd e (sem a regra do no-__del__) desfaria hides.
        class Daemon:
            _hidraw_broker_client: Any = None

        daemon = Daemon()
        resultados: list[Any] = []
        barreira = threading.Barrier(8)

        def corrida() -> None:
            barreira.wait()
            resultados.append(hbc.broker_client_for(daemon))

        threads = [threading.Thread(target=corrida) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)
        assert len(resultados) == 8
        assert len({id(c) for c in resultados}) == 1
        assert daemon._hidraw_broker_client is resultados[0]

    def test_cliente_nao_tem_del(self) -> None:
        # Lição 3 (§4.4b): GC de um cliente duplicado acidental NUNCA pode
        # fechar conexão (só close() explícito) — logo, nada de __del__.
        assert "__del__" not in hbc.HidrawBrokerClient.__dict__
