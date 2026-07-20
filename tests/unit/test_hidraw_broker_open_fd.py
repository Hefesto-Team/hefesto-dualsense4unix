"""cmd `open` + SCM_RIGHTS do broker (BROKER-01, desenho 2026-07-20 §1) — hermético.

A espinha dorsal da Onda S: o broker valida o nó, abre O_RDWR|O_CLOEXEC como
root e devolve o fd via SCM_RIGHTS NA MESMA mensagem da resposta. Prova:
- `_cmd_open` via `handle_line`: fd só em `ok:true`; erro NUNCA carrega fd;
  `open` é ortogonal a lease/refcount (funciona escondido OU exposto);
- `_send_with_fd` com socketpair REAL: o fd chega apontando o MESMO inode
  (os.fstat), nasce CLOEXEC no receptor (MSG_CMSG_CLOEXEC) e a cópia local do
  servidor é fechada SEMPRE (sucesso E falha de envio);
- ponta a ponta (Broker + register_client): linha JSON + exatamente 1 fd em
  ancillary; recusa não manda ancillary nenhum;
- `FsAclOps`: revalidação pós-open no PRÓPRIO fd (lição 5, minor-reuse) —
  nome reciclado vira `StaleNodeError` sem vazar fd; O_NOFOLLOW nega symlink;
  `_pin`/hide/restore tratam nó não-char como gone; `is_exposed_to` validado
  contra o KERNEL real (setxattr do blob ACL em arquivo próprio).
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import socket
import stat
import struct
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import (
    Broker,
    BrokerState,
    FsAclOps,
    StaleNodeError,
    encode_access_acl,
)

UID = 1000
_FD_INT_SIZE = struct.calcsize("i")
_ANCILLARY_SPACE = socket.CMSG_SPACE(2 * _FD_INT_SIZE)


class FakeOpenOps:
    """Dublê de fs cujo `open_node` abre um ARQUIVO comum real.

    O fd é de verdade (dá para mandar via SCM_RIGHTS e comparar inode); o
    /dev real nunca é tocado. `open_exc` injeta a falha da vez.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        self.calls: list[tuple[Any, ...]] = []
        self.open_exc: Exception | None = None

    def hide(self, node: str, base: str) -> None:
        self.calls.append(("hide", node, base))

    def restore(self, node: str, base: str, uid: int) -> None:
        self.calls.append(("restore", node, base, uid))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return True

    def open_node(self, node: str, base: str) -> int:
        self.calls.append(("open_node", node, base))
        if self.open_exc is not None:
            raise self.open_exc
        return os.open(self.target, os.O_RDONLY | os.O_CLOEXEC)


def _validator(node: str) -> str | None:
    base = node.rsplit("/", 1)[-1]
    return base if base in {"hidraw3", "hidraw7"} else None


def make_state(tmp_path: Path) -> tuple[BrokerState, FakeOpenOps, str]:
    target = tmp_path / "alvo-do-fd"
    target.write_bytes(b"conteudo do hidraw fake")
    ops = FakeOpenOps(str(target))
    state = BrokerState(
        allowed_uid=UID,
        ops=ops,
        validator=_validator,
        log=lambda *a, **k: None,
        sleep_fn=lambda _s: None,
    )
    return state, ops, str(target)


def req_fd(
    state: BrokerState, conn: int, payload: dict[str, Any]
) -> tuple[dict[str, Any], int | None]:
    response, fd = state.handle_line(conn, UID, json.dumps(payload).encode())
    return dict(response), fd


def _recv_json_with_fds(sock: socket.socket) -> tuple[dict[str, Any], list[int]]:
    """Uma linha de resposta + fds do ancillary (MSG_CMSG_CLOEXEC, como o cliente)."""
    fds: list[int] = []
    buf = bytearray()
    while b"\n" not in buf:
        data, ancdata, flags, _addr = sock.recvmsg(4096, _ANCILLARY_SPACE, socket.MSG_CMSG_CLOEXEC)
        assert not flags & socket.MSG_CTRUNC
        for level, ctype, cdata in ancdata:
            if level == socket.SOL_SOCKET and ctype == socket.SCM_RIGHTS:
                n = len(cdata) // _FD_INT_SIZE
                fds.extend(struct.unpack(f"{n}i", cdata[: n * _FD_INT_SIZE]))
        assert data, "broker fechou a conexão no meio da resposta"
        buf.extend(data)
    resposta = json.loads(bytes(buf).split(b"\n")[0])
    assert isinstance(resposta, dict)
    return resposta, fds


class TestCmdOpen:
    def test_ok_devolve_fd_do_mesmo_inode(self, tmp_path: Path) -> None:
        state, _ops, target = make_state(tmp_path)
        resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw3"})
        assert resposta == {"ok": True, "cmd": "open", "node": "/dev/hidraw3",
                            "state": "exposed"}
        assert fd is not None
        try:
            assert os.fstat(fd).st_ino == os.stat(target).st_ino
        finally:
            os.close(fd)

    def test_state_ecoa_hidden(self, tmp_path: Path) -> None:
        # O open funciona nos DOIS estados (a assimetria root do design);
        # `state` é telemetria do momento.
        state, _ops, _target = make_state(tmp_path)
        req_fd(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "hidden"
        assert fd is not None
        os.close(fd)

    def test_open_nao_altera_lease_nem_refcount(self, tmp_path: Path) -> None:
        state, _ops, _target = make_state(tmp_path)
        req_fd(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        antes = dict(state.by_conn), state.hidden["/dev/hidraw3"].refcount
        _resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw3"})
        assert fd is not None
        os.close(fd)
        _resposta, fd7 = req_fd(state, 2, {"cmd": "open", "node": "/dev/hidraw7"})
        assert fd7 is not None
        os.close(fd7)
        assert (dict(state.by_conn), state.hidden["/dev/hidraw3"].refcount) == antes
        assert "/dev/hidraw7" not in state.hidden

    def test_reject_bad_path_sem_fd(self, tmp_path: Path) -> None:
        state, ops, _target = make_state(tmp_path)
        for ruim in ("/etc/passwd", "hidraw3", "/dev/foo/../hidraw3", "", None):
            resposta, fd = req_fd(state, 1, {"cmd": "open", "node": ruim})
            assert resposta["ok"] is False and resposta["error"] == "reject_bad_path"
            assert fd is None
        assert ops.calls == []

    def test_reject_nao_fisico_sem_fd(self, tmp_path: Path) -> None:
        # hidraw6 = vpad na convenção do validador fake.
        state, ops, _target = make_state(tmp_path)
        resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw6"})
        assert resposta["ok"] is False
        assert resposta["error"] == "reject_not_physical_dualsense"
        assert fd is None and ops.calls == []

    def test_open_failed_propaga_errno(self, tmp_path: Path) -> None:
        state, ops, _target = make_state(tmp_path)
        ops.open_exc = OSError(errno.ENODEV, "sumiu")
        resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "open_failed"
        assert resposta["errno"] == errno.ENODEV
        assert fd is None

    def test_reject_stale_node(self, tmp_path: Path) -> None:
        # Lição 5 (minor-reuse): nome reciclado entre validar e abrir.
        state, ops, _target = make_state(tmp_path)
        ops.open_exc = StaleNodeError("/dev/hidraw3")
        resposta, fd = req_fd(state, 1, {"cmd": "open", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "reject_stale_node"
        assert fd is None


class TestSendWithFd:
    def test_fd_viaja_com_a_resposta_e_local_fecha(self, tmp_path: Path) -> None:
        target = tmp_path / "alvo"
        target.write_bytes(b"x")
        state, _ops, _t = make_state(tmp_path)
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            fd = os.open(target, os.O_RDONLY | os.O_CLOEXEC)
            assert broker._send_with_fd(a, {"ok": True, "cmd": "open"}, fd) is True
            # A cópia LOCAL fechou (a duplicata do kernel já está em trânsito).
            with pytest.raises(OSError):
                os.fstat(fd)
            b.settimeout(2.0)
            resposta, fds = _recv_json_with_fds(b)
            assert resposta == {"ok": True, "cmd": "open"}
            assert len(fds) == 1
            # Mesmo inode + CLOEXEC já instalado na recepção.
            assert os.fstat(fds[0]).st_ino == os.stat(target).st_ino
            assert fcntl.fcntl(fds[0], fcntl.F_GETFD) & fcntl.FD_CLOEXEC
            os.close(fds[0])
        finally:
            a.close()
            b.close()

    def test_falha_de_envio_fecha_o_fd_mesmo_assim(self, tmp_path: Path) -> None:
        target = tmp_path / "alvo"
        target.write_bytes(b"x")
        state, _ops, _t = make_state(tmp_path)
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        b.close()  # peer morto: sendmsg → EPIPE
        try:
            fd = os.open(target, os.O_RDONLY | os.O_CLOEXEC)
            assert broker._send_with_fd(a, {"ok": True}, fd) is False
            with pytest.raises(OSError):  # nunca vaza fd, nem na falha
                os.fstat(fd)
        finally:
            a.close()


class TestOpenPontaAPonta:
    def _wired(self, tmp_path: Path) -> tuple[Broker, BrokerState, FakeOpenOps, str, socket.socket]:
        state, ops, target = make_state(tmp_path)
        state.allowed_uid = os.getuid()
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        assert broker.register_client(a) is not None
        b.settimeout(2.0)
        return broker, state, ops, target, b

    def test_open_entrega_exatamente_um_fd(self, tmp_path: Path) -> None:
        broker, _state, _ops, target, cliente = self._wired(tmp_path)
        cliente.sendall(b'{"cmd": "open", "node": "/dev/hidraw3"}\n')
        broker.step(timeout=2.0)
        resposta, fds = _recv_json_with_fds(cliente)
        assert resposta["ok"] is True and resposta["cmd"] == "open"
        assert resposta["node"] == "/dev/hidraw3" and resposta["state"] == "exposed"
        assert len(fds) == 1
        assert os.fstat(fds[0]).st_ino == os.stat(target).st_ino
        os.close(fds[0])
        cliente.close()

    def test_open_de_no_escondido_funciona(self, tmp_path: Path) -> None:
        # A razão da onda: com o físico ESCONDIDO, o fd continua saindo.
        broker, state, _ops, target, cliente = self._wired(tmp_path)
        cliente.sendall(b'{"cmd": "hide", "node": "/dev/hidraw3"}\n')
        broker.step(timeout=2.0)
        assert json.loads(cliente.recv(4096).split(b"\n")[0])["ok"] is True
        assert "/dev/hidraw3" in state.hidden
        cliente.sendall(b'{"cmd": "open", "node": "/dev/hidraw3"}\n')
        broker.step(timeout=2.0)
        resposta, fds = _recv_json_with_fds(cliente)
        assert resposta["ok"] is True and resposta["state"] == "hidden"
        assert len(fds) == 1
        assert os.fstat(fds[0]).st_ino == os.stat(target).st_ino
        os.close(fds[0])
        cliente.close()

    def test_recusa_nao_carrega_ancillary(self, tmp_path: Path) -> None:
        broker, _state, _ops, _target, cliente = self._wired(tmp_path)
        cliente.sendall(b'{"cmd": "open", "node": "/dev/hidraw6"}\n')
        broker.step(timeout=2.0)
        resposta, fds = _recv_json_with_fds(cliente)
        assert resposta["ok"] is False
        assert resposta["error"] == "reject_not_physical_dualsense"
        assert fds == []
        cliente.close()


class TestFsAclOpsPinado:
    """Lição 5 no fs REAL possível sem root: arquivos comuns + sysfs fake."""

    def _ops(self, tmp_path: Path, *, dev: str = "237:3") -> tuple[FsAclOps, str]:
        sys_hidraw = tmp_path / "sys" / "class" / "hidraw"
        (sys_hidraw / "hidraw3").mkdir(parents=True)
        (sys_hidraw / "hidraw3" / "dev").write_text(dev + "\n", encoding="ascii")
        node = tmp_path / "dev" / "hidraw3"
        node.parent.mkdir()
        node.write_bytes(b"")
        return FsAclOps(sys_class_hidraw=str(sys_hidraw)), str(node)

    def test_sysfs_rdev_parse(self, tmp_path: Path) -> None:
        ops, _node = self._ops(tmp_path)
        assert ops._sysfs_rdev("hidraw3") == (237, 3)
        assert ops._sysfs_rdev("hidraw9") is None  # sem entrada no sysfs
        (tmp_path / "sys" / "class" / "hidraw" / "hidraw3" / "dev").write_text(
            "lixo\n", encoding="ascii"
        )
        assert ops._sysfs_rdev("hidraw3") is None

    def test_hide_e_restore_tratam_nao_char_como_gone(self, tmp_path: Path) -> None:
        # O _pin exige S_ISCHR + rdev casando o sysfs; arquivo comum (o que um
        # atacante conseguiria plantar sem root) vira FileNotFoundError (gone)
        # — nunca chmod/ACL num inode que não é o device validado.
        ops, node = self._ops(tmp_path)
        with pytest.raises(FileNotFoundError):
            ops.hide(node, "hidraw3")
        with pytest.raises(FileNotFoundError):
            ops.restore(node, "hidraw3", UID)

    def test_open_node_nao_char_e_stale_sem_vazar_fd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A revalidação pós-open NO fd rejeita inode que não é o device — e
        # fecha o fd recém-aberto (nenhum caminho de erro vaza fd).
        ops, node = self._ops(tmp_path)
        abertos: list[int] = []
        real_open = os.open

        def registrando(*args: Any, **kwargs: Any) -> int:
            fd = real_open(*args, **kwargs)
            abertos.append(fd)
            return fd

        monkeypatch.setattr(os, "open", registrando)
        with pytest.raises(StaleNodeError):
            ops.open_node(node, "hidraw3")
        monkeypatch.undo()
        assert len(abertos) == 1
        with pytest.raises(OSError):
            os.fstat(abertos[0])  # fechado — não vazou

    def test_open_node_nofollow_nega_symlink(self, tmp_path: Path) -> None:
        ops, node = self._ops(tmp_path)
        link = tmp_path / "dev" / "hidraw4"
        link.symlink_to(node)
        with pytest.raises(OSError) as excinfo:
            ops.open_node(str(link), "hidraw4")
        assert excinfo.value.errno == errno.ELOOP
        assert not isinstance(excinfo.value, StaleNodeError)

    def test_is_exposed_to_contra_o_kernel_real(self, tmp_path: Path) -> None:
        # O blob do encode_access_acl é ACEITO pelo kernel (setxattr real) e
        # o is_exposed_to o lê de volta — validação viva do formato v2.
        ops = FsAclOps(sys_class_hidraw=str(tmp_path / "sys"))
        node = tmp_path / "no-comum"
        node.write_bytes(b"")
        os.chmod(node, 0o600)
        assert ops.is_exposed_to(str(node), os.getuid()) is False  # modo errado
        os.chmod(node, 0o660)
        assert ops.is_exposed_to(str(node), os.getuid()) is False  # sem ACL
        os.setxattr(str(node), "system.posix_acl_access", encode_access_acl(os.getuid()))
        assert ops.is_exposed_to(str(node), os.getuid()) is True
        assert ops.is_exposed_to(str(node), os.getuid() + 1) is False  # uid alheio

    def test_pin_exige_rdev_casando_o_sysfs(self, tmp_path: Path) -> None:
        # Minor-reuse simulável sem root: um FIFO tem st_rdev 0 e não é char;
        # e mesmo o stat falso não passa — aqui provamos a recusa via fs real
        # com o sysfs apontando outro (major, minor).
        ops, node = self._ops(tmp_path, dev="237:9")  # sysfs diz OUTRO minor
        assert ops._pin(node, "hidraw3") is None
        assert stat.S_ISREG(os.stat(node).st_mode)  # segue intacto (só O_PATH)
