"""Protocolo + lease + SO_PEERCRED do broker hide-hidraw (BROKER-01) — hermético."""
from __future__ import annotations

import errno
import json
import os
import socket
from typing import Any

from hefesto_dualsense4unix.broker.hidraw_broker import (
    MAX_LINE_BYTES,
    Broker,
    BrokerState,
    decode_acl_user_uids,
    encode_access_acl,
    peer_credentials,
    restore_all_physical,
)

UID = 1000


class FakeOps:
    """Dublê das operações de fs: grava chamadas, nunca toca /dev."""

    def __init__(
        self,
        *,
        fail_hide: bool = False,
        hide_gone: bool = False,
        fail_restore: Exception | None = None,
        restore_script: list[Exception | None] | None = None,
        exposed: bool = True,
    ) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.sleeps: list[float] = []
        self.fail_hide = fail_hide
        self.hide_gone = hide_gone
        self.fail_restore = fail_restore
        self.restore_script = list(restore_script or [])
        self.exposed = exposed

    def hide(self, node: str, base: str) -> None:
        if self.hide_gone:
            raise FileNotFoundError(node)
        if self.fail_hide:
            raise OSError(errno.EPERM, "EPERM")
        self.calls.append(("hide", node, base))

    def restore(self, node: str, base: str, uid: int) -> None:
        if self.restore_script:
            exc = self.restore_script.pop(0)
            if exc is not None:
                raise exc
        elif self.fail_restore is not None:
            raise self.fail_restore
        self.calls.append(("restore", node, base, uid))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return self.exposed

    def open_node(self, node: str, base: str) -> int:  # pragma: no cover - open_fd
        raise AssertionError("open_node não pertence a esta suíte")


def _validator(node: str) -> str | None:
    """Aceita /dev/hidraw3 e /dev/hidraw7 (os 'físicos' da suíte)."""
    base = node.rsplit("/", 1)[-1]
    return base if base in {"hidraw3", "hidraw7"} else None


def make_state(**kw: Any) -> tuple[BrokerState, FakeOps]:
    ops = kw.pop("ops", FakeOps())
    state = BrokerState(
        allowed_uid=UID,
        ops=ops,
        validator=_validator,
        log=lambda *a, **k: None,
        sleep_fn=ops.sleeps.append,
        **kw,
    )
    return state, ops


def req(state: BrokerState, conn: int, payload: Any, uid: int = UID) -> dict[str, Any]:
    line = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    response, fd = state.handle_line(conn, uid, line)
    assert fd is None
    return dict(response)


class TestProtocolo:
    def test_ping(self) -> None:
        state, _ = make_state()
        assert req(state, 1, {"cmd": "ping"}) == {"ok": True, "cmd": "ping", "peer_uid": UID}

    def test_status_vazio_e_com_no(self) -> None:
        state, _ = make_state()
        assert req(state, 1, {"cmd": "status"})["hidden"] == []
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert req(state, 1, {"cmd": "status"})["hidden"] == ["/dev/hidraw3"]

    def test_hide_fisico_ok(self) -> None:
        state, ops = make_state()
        resposta = req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert resposta == {"ok": True, "cmd": "hide", "node": "/dev/hidraw3", "state": "hidden"}
        assert ops.calls == [("hide", "/dev/hidraw3", "hidraw3")]

    def test_hide_repetido_reaplica_o_fs(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "hidden"
        assert ops.calls == [
            ("hide", "/dev/hidraw3", "hidraw3"),
            ("hide", "/dev/hidraw3", "hidraw3"),
        ]
        assert state.hidden["/dev/hidraw3"].refcount == 1
        assert req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})["state"] == "exposed"
        assert state.hidden == {}

    def test_hide_caminho_ruim(self) -> None:
        state, ops = make_state()
        for ruim in ("/dev/foo/../hidraw3", "/etc/passwd", "hidraw3", "", None, 7):
            resposta = req(state, 1, {"cmd": "hide", "node": ruim})
            assert resposta["ok"] is False and resposta["error"] == "reject_bad_path"
        assert ops.calls == []

    def test_hide_nao_fisico(self) -> None:
        state, ops = make_state()
        resposta = req(state, 1, {"cmd": "hide", "node": "/dev/hidraw6"})
        assert resposta["ok"] is False
        assert resposta["error"] == "reject_not_physical_dualsense"
        assert ops.calls == []

    def test_hide_falha_de_fs_nao_rastreia(self) -> None:
        state, ops = make_state(ops=FakeOps(fail_hide=True))
        resposta = req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "hide_failed"
        assert state.hidden == {} and ops.calls == []

    def test_hide_no_sumiu_nao_rastreia(self) -> None:
        state, ops = make_state(ops=FakeOps(hide_gone=True))
        resposta = req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "hide_node_gone"
        assert state.hidden == {} and ops.calls == []

    def test_restore_devolve_com_uid_do_hide(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"}, uid=UID)
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["state"] == "exposed"
        assert ("restore", "/dev/hidraw3", "hidraw3", UID) in ops.calls
        assert state.hidden == {}

    def test_restore_nao_rastreado_valida_identidade(self) -> None:
        state, ops = make_state()
        ok = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw7"})
        assert ok["ok"] is True and ok["state"] == "exposed"
        ruim = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw6"})
        assert ruim["ok"] is False and ruim["error"] == "reject_not_physical_dualsense"
        assert ops.calls == [("restore", "/dev/hidraw7", "hidraw7", UID)]

    def test_restore_node_sumiu_enoent(self) -> None:
        state, _ = make_state(ops=FakeOps(fail_restore=FileNotFoundError()))
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "gone"
        assert state.hidden == {}

    def test_restore_all_da_conexao(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw7"})
        resposta = req(state, 1, {"cmd": "restore_all"})
        assert resposta["ok"] is True
        assert resposta["restored"] == ["/dev/hidraw3", "/dev/hidraw7"]
        assert resposta["failed"] == []
        assert state.hidden == {}
        restores = [c for c in ops.calls if c[0] == "restore"]
        assert len(restores) == 2

    def test_comando_desconhecido(self) -> None:
        state, _ = make_state()
        resposta = req(state, 1, {"cmd": "format_disk"})
        assert resposta["ok"] is False and resposta["error"] == "reject_unknown_cmd"

    def test_malformado(self) -> None:
        state, _ = make_state()
        assert req(state, 1, b"{nao json")["error"] == "reject_malformed"
        assert req(state, 1, b"[1, 2]")["error"] == "reject_malformed"
        assert req(state, 1, b"\xff\xfe")["error"] == "reject_malformed"

    def test_oversize(self) -> None:
        state, _ = make_state()
        gigante = b'{"cmd": "hide", "node": "' + b"A" * MAX_LINE_BYTES + b'"}'
        assert req(state, 1, gigante)["error"] == "reject_oversize"


class TestRestoreResiliente:
    """Lição 2: retry + verificação; nó só sai do rastreio com fs OK."""

    def test_restore_falho_mantem_rastreado_e_retry_posterior_cura(self) -> None:
        ops = FakeOps(restore_script=[OSError(errno.EIO, "EIO")] * 3)
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "restore_failed"
        assert "/dev/hidraw3" in state.hidden
        assert "/dev/hidraw3" in state.by_conn[1]
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "exposed"
        assert state.hidden == {} and state.by_conn[1] == set()

    def test_retry_com_backoff_dentro_do_mesmo_restore(self) -> None:
        ops = FakeOps(restore_script=[OSError(errno.EIO, "1"), OSError(errno.EIO, "2"), None])
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "exposed"
        assert state.hidden == {}
        assert ops.sleeps == [0.05, 0.2]

    def test_restore_verify_failed_mantem_rastreado(self) -> None:
        ops = FakeOps(exposed=False)
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is False and resposta["error"] == "restore_verify_failed"
        assert "/dev/hidraw3" in state.hidden

    def test_restore_all_parcial_nao_aborta_o_loop(self) -> None:
        class OpsParcial(FakeOps):
            def restore(self, node: str, base: str, uid: int) -> None:
                if base == "hidraw3":
                    raise OSError(errno.EIO, "EIO")
                super().restore(node, base, uid)

        ops = OpsParcial()
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw7"})
        resposta = req(state, 1, {"cmd": "restore_all"})
        assert resposta["ok"] is True
        assert resposta["restored"] == ["/dev/hidraw7"]
        assert resposta["failed"] == ["/dev/hidraw3"]
        assert "/dev/hidraw3" in state.hidden and "/dev/hidraw7" not in state.hidden
        assert state.by_conn[1] == {"/dev/hidraw3"}


class TestLeaseRefcount:
    def test_eof_restaura_tudo_da_conexao(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw7"})
        restaurados = state.on_conn_closed(1)
        assert restaurados == ["/dev/hidraw3", "/dev/hidraw7"]
        assert state.hidden == {} and state.by_conn == {}
        assert ("restore", "/dev/hidraw3", "hidraw3", UID) in ops.calls
        assert ("restore", "/dev/hidraw7", "hidraw7", UID) in ops.calls

    def test_eof_parcial_nao_aborta_nem_destrackea_o_falho(self) -> None:
        class OpsParcial(FakeOps):
            def restore(self, node: str, base: str, uid: int) -> None:
                if base == "hidraw3":
                    raise OSError(errno.EIO, "EIO")
                super().restore(node, base, uid)

        ops = OpsParcial()
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw7"})
        assert state.on_conn_closed(1) == ["/dev/hidraw7"]
        assert "/dev/hidraw3" in state.hidden
        assert state.by_conn == {}

    def test_refcount_duas_conexoes_takeover(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert len([c for c in ops.calls if c[0] == "hide"]) == 2
        assert state.hidden["/dev/hidraw3"].refcount == 2
        assert state.on_conn_closed(1) == []
        assert "/dev/hidraw3" in state.hidden
        assert state.on_conn_closed(2) == ["/dev/hidraw3"]
        assert state.hidden == {}

    def test_restore_de_no_seguro_por_outra_conexao(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 2, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "hidden"
        assert not any(c[0] == "restore" for c in ops.calls)

    def test_restore_everything_belt_do_shutdown(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        req(state, 2, {"cmd": "hide", "node": "/dev/hidraw7"})
        assert state.restore_everything() == ["/dev/hidraw3", "/dev/hidraw7"]
        assert state.hidden == {} and state.by_conn == {}
        assert len([c for c in ops.calls if c[0] == "restore"]) == 2


class TestLeaseOrfa:
    """Achado Onda S #3: nó órfão de lease fechada com restore de fs falho."""

    def _estado_com_orfao(self) -> tuple[BrokerState, FakeOps]:
        ops = FakeOps(restore_script=[OSError(errno.EIO, "EIO")] * 3)
        state, _ = make_state(ops=ops)
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert state.on_conn_closed(1) == []
        assert "/dev/hidraw3" in state.hidden
        assert all("/dev/hidraw3" not in held for held in state.by_conn.values())
        return state, ops

    def test_adocao_por_conexao_nova_nao_infla_o_refcount(self) -> None:
        state, _ops = self._estado_com_orfao()
        req(state, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert state.hidden["/dev/hidraw3"].refcount == 1

    def test_restore_all_da_conexao_nova_restaura_o_orfao_adotado(self) -> None:
        state, ops = self._estado_com_orfao()
        req(state, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 2, {"cmd": "restore_all"})
        assert resposta["restored"] == ["/dev/hidraw3"]
        assert state.hidden == {}
        assert any(c[0] == "restore" for c in ops.calls)

    def test_restore_explicito_de_orfao_toca_o_fs(self) -> None:
        state, ops = self._estado_com_orfao()
        resposta = req(state, 2, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True and resposta["state"] == "exposed"
        assert state.hidden == {}
        assert any(c[0] == "restore" for c in ops.calls)

    def test_no_seguro_por_lease_viva_segue_intocado(self) -> None:
        state, ops = make_state()
        req(state, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        resposta = req(state, 2, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["state"] == "hidden"
        assert not any(c[0] == "restore" for c in ops.calls)
        req(state, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert state.hidden["/dev/hidraw3"].refcount == 2


class TestPeerCred:
    def test_socketpair_devolve_uid_real(self) -> None:
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            pid, uid, gid = peer_credentials(a)
            assert uid == os.getuid()
            assert gid == os.getgid()
            assert pid > 0
        finally:
            a.close()
            b.close()

    def test_broker_recusa_uid_errado(self) -> None:
        state, ops = make_state()
        state.allowed_uid = os.getuid() + 1
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            assert broker.register_client(a) is None
            b.settimeout(1.0)
            assert b.recv(64) == b""
            assert ops.calls == []
        finally:
            b.close()

    def test_broker_aceita_uid_da_sessao(self) -> None:
        state, _ = make_state()
        state.allowed_uid = os.getuid()
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            assert broker.register_client(a) == 1
            b.settimeout(2.0)
            b.sendall(b'{"cmd": "ping"}\n')
            broker.step(timeout=2.0)
            resposta = json.loads(b.recv(4096).split(b"\n")[0])
            assert resposta["ok"] is True and resposta["peer_uid"] == os.getuid()
        finally:
            a.close()
            b.close()


class TestBrokerLoopEOF:
    def _wired(self) -> tuple[Broker, BrokerState, FakeOps, socket.socket]:
        state, ops = make_state()
        state.allowed_uid = os.getuid()
        broker = Broker(state, None, log=lambda *a, **k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        assert broker.register_client(a) is not None
        b.settimeout(2.0)
        return broker, state, ops, b

    def test_eof_do_daemon_restaura(self) -> None:
        broker, state, ops, cliente = self._wired()
        cliente.sendall(b'{"cmd": "hide", "node": "/dev/hidraw3"}\n')
        broker.step(timeout=2.0)
        assert json.loads(cliente.recv(4096).split(b"\n")[0])["ok"] is True
        assert "/dev/hidraw3" in state.hidden
        cliente.close()
        broker.step(timeout=2.0)
        assert state.hidden == {}
        assert ("restore", "/dev/hidraw3", "hidraw3", os.getuid()) in ops.calls

    def test_linha_gigante_fecha_e_restaura(self) -> None:
        broker, state, ops, cliente = self._wired()
        cliente.sendall(b'{"cmd": "hide", "node": "/dev/hidraw3"}\n')
        broker.step(timeout=2.0)
        cliente.recv(4096)
        cliente.sendall(b"A" * (MAX_LINE_BYTES * 2))
        broker.step(timeout=2.0)
        broker.step(timeout=2.0)
        resposta = json.loads(cliente.recv(4096).split(b"\n")[0])
        assert resposta["error"] == "reject_oversize"
        assert state.hidden == {}
        assert any(c[0] == "restore" for c in ops.calls)
        cliente.close()

    def test_duas_requisicoes_na_mesma_leitura(self) -> None:
        broker, _state, _ops, cliente = self._wired()
        cliente.sendall(b'{"cmd": "ping"}\n{"cmd": "status"}\n')
        broker.step(timeout=2.0)
        linhas = cliente.recv(8192).split(b"\n")
        respostas = [json.loads(linha) for linha in linhas if linha.strip()]
        assert [r["cmd"] for r in respostas] == ["ping", "status"]
        cliente.close()


class TestAclBlob:
    def test_roundtrip_do_blob(self) -> None:
        blob = encode_access_acl(1000)
        assert len(blob) == 44
        assert decode_acl_user_uids(blob) == {1000}

    def test_blob_identico_ao_do_setfacl_real(self) -> None:
        esperado = bytes.fromhex(
            "0200000001000600ffffffff02000600e8030000"
            "04000600ffffffff10000600ffffffff20000000ffffffff"
        )
        assert encode_access_acl(1000) == esperado

    def test_decode_rejeita_versao_errada(self) -> None:
        assert decode_acl_user_uids(b"\x01\x00\x00\x00") == set()
        assert decode_acl_user_uids(b"") == set()


class TestRestoreAllPhysical:
    def test_baseline_restaura_so_fisico_nao_exposto(self, tmp_path: Any) -> None:
        sys_hidraw = tmp_path / "sys"
        for base in ("hidraw3", "hidraw6", "hidraw7"):
            (sys_hidraw / base).mkdir(parents=True)

        class Ops(FakeOps):
            def is_exposed_to(self, node: str, uid: int) -> bool:
                return node.endswith("hidraw7")

        ops = Ops()
        restaurados = restore_all_physical(
            uid=UID,
            ops=ops,
            dev_root="/dev",
            sys_class_hidraw=str(sys_hidraw),
            validator=_validator,
            log=lambda *a, **k: None,
        )
        assert restaurados == ["/dev/hidraw3"]
        assert ops.calls == [("restore", "/dev/hidraw3", "hidraw3", UID)]

    def test_baseline_falha_num_no_segue_para_os_demais(self, tmp_path: Any) -> None:
        sys_hidraw = tmp_path / "sys"
        for base in ("hidraw3", "hidraw7"):
            (sys_hidraw / base).mkdir(parents=True)

        class Ops(FakeOps):
            def is_exposed_to(self, node: str, uid: int) -> bool:
                return False

            def restore(self, node: str, base: str, uid: int) -> None:
                if base == "hidraw3":
                    raise OSError(errno.EIO, "EIO")
                super().restore(node, base, uid)

        ops = Ops()
        restaurados = restore_all_physical(
            uid=UID,
            ops=ops,
            dev_root="/dev",
            sys_class_hidraw=str(sys_hidraw),
            validator=_validator,
            log=lambda *a, **k: None,
        )
        assert restaurados == ["/dev/hidraw7"]
        assert ops.calls == [("restore", "/dev/hidraw7", "hidraw7", UID)]
