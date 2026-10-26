"""O nó do físico fica só com o Hefesto, mesmo quando alguém o abriu na janela.

O-NO-DO-FISICO-NAO-FICA-COM-QUEM-O-ABRIU-NA-JANELA-01: em 25/10/2026 o Hefesto parado entregou o
físico ao Linux (06:24:42 a 06:31:54), o ``cosmic-osk`` abriu o ``eventN`` e, com o Hefesto de
volta, seguiu nele: ``chmod`` não fecha fd aberto, e o ``EVIOCSFF`` dele a 20 por segundo calava a
háptica do jogo. Ao fechar o físico, o broker tira o ``eventN`` de quem não é do Hefesto
(``pidfd_getfd`` + ``EVIOCREVOKE``) e diz no diário quem segura o ``jsN`` e o hidraw. Tudo num
``/proc``, ``/dev`` e ``/sys`` de mentira; o ``pidfd_getfd`` e o ``kcmp`` reais, num filho da suíte.
"""

from __future__ import annotations

import errno
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb

RAIZ = Path(__file__).resolve().parents[2]
NOME_DO_GAMEPAD = "Sony Interactive Entertainment DualSense Wireless Controller"
UID = 1000
DAEMON, TECLADO, FILHO, LOGIND, COMPOSITOR = 5000, 4242, 5001, 700, 7000
FISICOS = (("0005", "0CE6"), ("0005", "0DF2"), ("0003", "0CE6"), ("0003", "0DF2"))


class _Mundo:
    """O ``/dev``, o ``/sys`` e o ``/proc`` de mentira, com os físicos e quem os segura."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.dev = raiz / "dev"
        self.dev_input = raiz / "dev-input"
        self.sys_hidraw = raiz / "hidraw"
        self.sys_input = raiz / "input"
        self.proc = raiz / "proc"
        for pasta in (self.dev, self.dev_input, self.sys_hidraw, self.sys_input, self.proc):
            pasta.mkdir(parents=True)

    def fisico(self, n: int, bus: str, produto: str) -> str:
        """Um DualSense físico no ``bus`` (``0005`` rádio, ``0003`` cabo); devolve o hidraw."""
        hid = self.raiz / "devices" / f"usb{n}" / f"{bus}:054C:{produto}.000{n}"
        entrada = hid / "input" / f"input{n}"
        entrada.mkdir(parents=True)
        (hid / "uevent").write_text(
            f"HID_ID={bus}:0000054C:0000{produto}\nHID_PHYS=usb-0000:00:14.0-{n}/input3\n"
            "HID_UNIQ=aa:bb:cc:00:00:0" + str(n) + "\n", encoding="ascii")
        (entrada / "name").write_text(NOME_DO_GAMEPAD + "\n", encoding="utf-8")
        classe = self.sys_hidraw / f"hidraw{n}"
        classe.mkdir()
        (classe / "device").symlink_to(hid)
        (classe / "dev").write_text("0:0\n", encoding="ascii")
        for nome in (f"event{n}", f"js{n}"):
            (entrada / nome).mkdir()
            (entrada / nome / "dev").write_text("0:0\n", encoding="ascii")
            (self.sys_input / nome).mkdir()
            (self.sys_input / nome / "dev").write_text("0:0\n", encoding="ascii")
            (self.dev_input / nome).write_bytes(b"")
        (self.dev / f"hidraw{n}").write_bytes(b"")
        return str(self.dev / f"hidraw{n}")

    def abrir_a_sessao(self) -> None:
        """A entrega: os nós do físico abrem à sessão (``0660``)."""
        for no in (*self.dev.iterdir(), *self.dev_input.iterdir()):
            no.chmod(0o660)

    def fechar(self) -> None:
        """O repouso: ``0600 root``."""
        for no in (*self.dev.iterdir(), *self.dev_input.iterdir()):
            no.chmod(0o600)

    def processo(self, pid: int, comm: str, *, uid: int = UID, inicio: int = 100) -> None:
        pasta = self.proc / str(pid)
        (pasta / "fd").mkdir(parents=True, exist_ok=True)
        campos = " ".join(["S", *["0"] * 18, str(inicio), "0", "0"])
        (pasta / "stat").write_text(f"{pid} ({comm}) {campos}\n", encoding="ascii")
        (pasta / "status").write_text(
            f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="ascii")
        (pasta / "comm").write_text(comm + "\n", encoding="utf-8")

    def segura(self, pid: int, fd: int, no: str) -> None:
        (self.proc / str(pid) / "fd" / str(fd)).symlink_to(no)

    def ev(self, n: int) -> str:
        return str(self.dev_input / f"event{n}")

    def js(self, n: int) -> str:
        return str(self.dev_input / f"js{n}")


class _Ops(hb.FsAclOps):
    """O ``FsAclOps`` de verdade, com o nó regular no lugar do device, o ``0660`` no lugar da
    ACL e o kernel anotado."""

    _e_char_device = staticmethod(stat.S_ISREG)

    def __init__(self, mundo: _Mundo, mesmas: set[frozenset[tuple[int, int]]]) -> None:
        super().__init__(
            sys_class_hidraw=str(mundo.sys_hidraw), dev_input_root=str(mundo.dev_input),
            sys_class_input=str(mundo.sys_input), sys_class_bluetooth=str(mundo.raiz / "bt"),
            sys_bus_hid_drivers=str(mundo.raiz / "drivers"), proc_root=str(mundo.proc))
        self.mundo = mundo
        self.mesmas = mesmas
        self.kcmp_mudo = False
        self.tomados: list[tuple[int, int]] = []
        self.revogados: list[tuple[int, int]] = []

    def _tomar_o_fd(self, pid: int, fd: int) -> int:  # type: ignore[override]
        self.tomados.append((pid, fd))
        return os.open(os.readlink(self.mundo.proc / str(pid) / "fd" / str(fd)), os.O_RDONLY)

    def _revogar_o_fd(self, fd: int) -> None:  # type: ignore[override]
        quem = self.tomados[-1]
        if quem in self.revogados:
            raise OSError(errno.ENODEV, os.strerror(errno.ENODEV))
        self.revogados.append(quem)

    def _mesma_descricao(  # type: ignore[override]
        self, pid_a: int, fd_a: int, pid_b: int, fd_b: int
    ) -> bool | None:
        if self.kcmp_mudo:
            return None
        return frozenset({(pid_a, fd_a), (pid_b, fd_b)}) in self.mesmas

    def open_entrada(self, node: str, base: str) -> int:
        return os.open(node, os.O_RDONLY | os.O_CLOEXEC)

    def is_exposed_to(self, node: str, uid: int | None) -> bool:
        return stat.S_IMODE(os.stat(node).st_mode) == 0o660


class _Cena:
    """Um broker sobre o mundo de mentira, com o diário dele."""

    def __init__(self, tmp_path: Path, fisicos: tuple[tuple[str, str], ...] = FISICOS[:1],
                 servidos: Path | None = None) -> None:
        self.mundo = _Mundo(tmp_path / "mundo")
        self.nos = [self.mundo.fisico(n, bus, produto)
                    for n, (bus, produto) in enumerate(fisicos, start=1)]
        self.mesmas: set[frozenset[tuple[int, int]]] = set()
        self.ops = _Ops(self.mundo, self.mesmas)
        self.servidos = servidos or tmp_path / "servidos"
        self.diario: list[tuple[str, dict[str, object]]] = []
        self.estado = self.novo_broker()

    def novo_broker(self) -> hb.BrokerState:
        m = self.mundo
        return hb.BrokerState(
            allowed_uid=UID, ops=self.ops, dev_root=str(m.dev),
            dev_input_root=str(m.dev_input), sys_class_hidraw=str(m.sys_hidraw),
            sys_class_input=str(m.sys_input), sys_class_bluetooth=str(m.raiz / "bt"),
            no_nasce_fechado=True, log=lambda e, **c: self.diario.append((e, c)),
            sleep_fn=lambda _s: None, servidos_path=str(self.servidos),
            validator=lambda no: os.path.basename(no) if os.path.dirname(no) == str(m.dev)
            else None,
            validator_entrada=lambda no: os.path.basename(no),
        )

    def pedir(self, conn: int, pedido: dict[str, object]) -> dict[str, object]:
        resposta, fd = self.estado.handle_line(conn, UID, json.dumps(pedido).encode())
        if fd is not None:
            os.close(fd)
        return resposta

    def linhas(self, evento: str) -> list[dict[str, object]]:
        return [c for e, c in self.diario if e == evento]


def _a_janela_de_25_10(tmp_path: Path, fisicos: tuple[tuple[str, str], ...]) -> _Cena:
    """O físico entregue, o teclado da tela o abre, e o Hefesto volta pedindo o hide."""
    cena = _Cena(tmp_path, fisicos)
    m = cena.mundo
    m.abrir_a_sessao()
    cena.estado.entregue = True
    m.processo(TECLADO, "cosmic-osk")
    m.processo(DAEMON, "hefesto-dualsen")
    for n in range(1, len(fisicos) + 1):
        m.segura(TECLADO, 30 + n, m.ev(n))
        m.segura(TECLADO, 40 + n, m.ev(n))
        m.segura(TECLADO, 50 + n, m.js(n))
        m.segura(DAEMON, 10 + n, m.ev(n))
    cena.estado.lembrar_o_cliente(1, DAEMON)
    for no in cena.nos:
        assert cena.pedir(1, {"cmd": "hide", "node": no})["ok"] is True
    return cena


@pytest.mark.parametrize(("bus", "produto"), FISICOS, ids=["bt", "bt-edge", "cabo", "cabo-edge"])
def test_quem_abriu_o_evento_na_janela_perde_o_no_e_o_diario_diz_quem_era(
    tmp_path: Path, bus: str, produto: str
) -> None:
    cena = _a_janela_de_25_10(tmp_path, ((bus, produto),))
    assert sorted(cena.ops.revogados) == [(TECLADO, 31), (TECLADO, 41)]
    ev = cena.mundo.ev(1)
    assert cena.linhas("no_do_fisico_revogado") == [
        {"node": ev, "pid": TECLADO, "comm": "cosmic-osk"}] * 2
    assert cena.linhas("no_do_fisico_segurado") == [
        {"node": cena.mundo.js(1), "pid": TECLADO, "comm": "cosmic-osk", "motivo": "sem_revoke"}]


def test_os_quatro_controles_nos_dois_transportes_ficam_so_com_o_hefesto(
    tmp_path: Path,
) -> None:
    cena = _a_janela_de_25_10(tmp_path, FISICOS)
    assert sorted(cena.ops.revogados) == sorted(
        (TECLADO, base + n) for n in range(1, 5) for base in (30, 40))
    assert all(pid != DAEMON for pid, _fd in cena.ops.tomados)


def test_o_cliente_e_quem_divide_a_descricao_com_ele_ou_com_o_root_ficam(
    tmp_path: Path,
) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.processo(DAEMON, "hefesto-dualsen")
    m.processo(FILHO, "python3")
    m.processo(LOGIND, "systemd-logind", uid=0)
    m.processo(COMPOSITOR, "cosmic-comp")
    m.processo(os.getpid(), "hefesto-hidraw-")
    m.processo(TECLADO, "cosmic-osk")
    for pid, fd in ((DAEMON, 10), (FILHO, 3), (LOGIND, 20), (COMPOSITOR, 30),
                    (os.getpid(), 9), (TECLADO, 35)):
        m.segura(pid, fd, m.ev(1))
    cena.mesmas |= {frozenset({(FILHO, 3), (DAEMON, 10)}),
                    frozenset({(COMPOSITOR, 30), (LOGIND, 20)})}
    cena.estado.lembrar_o_cliente(1, DAEMON)
    cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.revogados == [(TECLADO, 35)]


def test_sem_resposta_do_kcmp_quem_divide_o_no_com_o_daemon_fica_e_vai_ao_diario(
    tmp_path: Path,
) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    cena.ops.kcmp_mudo = True
    m.processo(DAEMON, "hefesto-dualsen")
    m.processo(TECLADO, "cosmic-osk")
    m.segura(DAEMON, 10, m.ev(1))
    m.segura(TECLADO, 35, m.ev(1))
    cena.estado.lembrar_o_cliente(1, DAEMON)
    cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.tomados == []
    assert cena.linhas("no_do_fisico_segurado") == [
        {"node": m.ev(1), "pid": TECLADO, "comm": "cosmic-osk", "motivo": "sem_kcmp"}]


def test_o_kcmp_que_nao_responde_e_nao_sei(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hb, "_SYS_KCMP", None)
    assert hb.FsAclOps._mesma_descricao(1, 3, 2, 4) is None


def test_a_volta_nao_repete_o_revoke_nem_a_linha_do_diario(tmp_path: Path) -> None:
    cena = _a_janela_de_25_10(tmp_path, FISICOS[:1])
    antes = (list(cena.ops.revogados), list(cena.diario))
    for _volta in range(3):
        cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.revogados == antes[0]
    novas = cena.diario[len(antes[1]):]
    assert [e for e, _c in novas if e.startswith("no_do_fisico")] == []


def test_a_volta_do_hefesto_tira_o_no_antes_do_pedido_que_a_anunciou(tmp_path: Path) -> None:
    """O ``expose`` e o ``pad_usb_montar`` também desfazem a entrega, e não fecham nada depois."""
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.abrir_a_sessao()
    cena.estado.entregue = True
    m.processo(TECLADO, "cosmic-osk")
    m.segura(TECLADO, 35, m.ev(1))
    assert cena.estado.retomar_o_esconderijo() == [cena.nos[0]]
    assert cena.ops.revogados == [(TECLADO, 35)]


def test_o_hidraw_que_alguem_segura_so_vai_ao_diario(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    m.processo(TECLADO, "steam")
    m.segura(TECLADO, 70, cena.nos[0])
    cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.tomados == []
    assert cena.linhas("no_do_fisico_segurado") == [
        {"node": cena.nos[0], "pid": TECLADO, "comm": "steam", "motivo": "sem_revoke"}]


def test_o_proc_que_nao_se_le_vai_ao_diario(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    m.proc.rmdir()
    cena.estado._aplicar_entradas(cena.nos[0])
    assert [c["node"] for c in cena.linhas("revogar_falhou")] == [cena.nos[0]]


def test_o_no_aberto_a_sessao_nao_se_revoga(tmp_path: Path) -> None:
    """Exposto de propósito (o físico com o jogo), o nó é de quem o abriu."""
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.abrir_a_sessao()
    m.processo(TECLADO, "cosmic-osk")
    m.segura(TECLADO, 35, m.ev(1))
    assert cena.ops.revogar_quem_escapou(cena.nos[0], "hidraw1", lambda _p, _i: False) == []
    assert cena.ops.tomados == []


def test_o_no_que_o_daemon_pede_sai_de_quem_o_segura_de_fora(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    m.processo(TECLADO, "cosmic-osk")
    m.processo(DAEMON, "hefesto-dualsen")
    m.segura(TECLADO, 35, m.ev(1))
    cena.estado.lembrar_o_cliente(1, DAEMON)
    assert cena.pedir(1, {"cmd": "open", "node": m.ev(1)})["ok"] is True
    assert cena.ops.revogados == [(TECLADO, 35)]


def test_depois_do_reinicio_do_broker_o_daemon_segue_com_o_no(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    m.processo(DAEMON, "hefesto-dualsen", inicio=4321)
    cena.estado.lembrar_o_cliente(1, DAEMON)
    assert cena.pedir(1, {"cmd": "open", "node": m.ev(1)})["ok"] is True
    assert cena.servidos.read_text(encoding="ascii") == f"{DAEMON} 4321\n"
    m.segura(DAEMON, 10, m.ev(1))
    m.processo(TECLADO, "cosmic-osk")
    m.segura(TECLADO, 35, m.ev(1))
    cena.estado = cena.novo_broker()
    cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.revogados == [(TECLADO, 35)]


def test_o_pid_reciclado_nao_herda_o_que_o_daemon_recebeu(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    m = cena.mundo
    m.fechar()
    cena.servidos.write_text(f"{TECLADO} 1\n", encoding="ascii")
    cena.estado = cena.novo_broker()
    m.processo(TECLADO, "cosmic-osk", inicio=2)
    m.segura(TECLADO, 35, m.ev(1))
    cena.estado._aplicar_entradas(cena.nos[0])
    assert cena.ops.revogados == [(TECLADO, 35)]


def test_o_cliente_que_desconecta_deixa_de_ser_poupado(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    cena.estado.lembrar_o_cliente(1, DAEMON)
    cena.estado.on_conn_closed(1)
    assert cena.estado._poupado(DAEMON, 100) is False


def test_o_broker_registra_o_pid_de_quem_conecta() -> None:
    estado = hb.BrokerState(allowed_uid=UID, log=lambda *_a, **_k: None)
    broker = hb.Broker(estado, peercred_fn=lambda _s: (DAEMON, UID, UID),
                       log=lambda *_a, **_k: None)

    class _Sock:
        def setblocking(self, _v: bool) -> None:
            pass

        def fileno(self) -> int:
            return lido

    lido, escrito = os.pipe()
    try:
        conn = broker.register_client(_Sock())  # type: ignore[arg-type]
    finally:
        os.close(lido)
        os.close(escrito)
    assert conn is not None and estado._poupado(DAEMON, 0) is True


def test_dentro_da_suite_o_proc_do_broker_nao_e_o_da_maquina() -> None:
    assert not hb.PROC_ROOT.startswith("/proc")
    assert hb.FsAclOps()._proc_root == hb.PROC_ROOT


def test_o_eviocrevoke_e_o_ioctl_do_kernel() -> None:
    ioc_iow_e_0x91_int = (1 << 30) | (4 << 16) | (ord("E") << 8) | 0x91
    assert ioc_iow_e_0x91_int == hb.EVIOCREVOKE


@pytest.fixture
def filho_com_um_arquivo(tmp_path: Path) -> Any:
    arquivo = tmp_path / "segurado"
    arquivo.write_bytes(b"0123456789")
    filho = subprocess.Popen(
        [sys.executable, "-c",
         "import os,sys,time; fd=os.open(sys.argv[1], os.O_RDONLY); "
         "print(fd, flush=True); time.sleep(30)", str(arquivo)],
        stdout=subprocess.PIPE, text=True)
    assert filho.stdout is not None
    fd = int(filho.stdout.readline())
    try:
        yield filho.pid, fd, arquivo
    finally:
        filho.kill()
        filho.wait(timeout=5)


def test_o_pidfd_getfd_e_o_kcmp_de_verdade_tomam_a_mesma_descricao(
    filho_com_um_arquivo: tuple[int, int, Path],
) -> None:
    pid, fd, arquivo = filho_com_um_arquivo
    try:
        tomado = hb.FsAclOps._tomar_o_fd(pid, fd)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.ENOSYS):
            pytest.skip(f"o kernel desta máquina recusa o pidfd_getfd: {exc}")
        raise
    outro = os.open(arquivo, os.O_RDONLY)
    try:
        os.lseek(tomado, 4, os.SEEK_SET)
        posicao = Path(f"/proc/{pid}/fdinfo/{fd}").read_text(encoding="ascii").split()[1]
        assert posicao == "4"
        assert hb.FsAclOps._mesma_descricao(pid, fd, os.getpid(), tomado) is True
        try:
            hb._syscall(hb._SYS_KCMP, pid, os.getpid(), hb._KCMP_FILE, fd, outro)
        except OSError as exc:
            pytest.skip(f"o kernel desta máquina recusa o kcmp: {exc}")
        assert hb.FsAclOps._mesma_descricao(pid, fd, os.getpid(), outro) is False
        with pytest.raises(OSError) as erro:
            hb.FsAclOps._revogar_o_fd(tomado)
        assert erro.value.errno == errno.ENOTTY
    finally:
        os.close(tomado)
        os.close(outro)


def _diretivas(caminho: Path) -> dict[str, list[str]]:
    d: dict[str, list[str]] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith(("#", ";", "[")):
            chave, _sep, valor = linha.partition("=")
            d.setdefault(chave.strip(), []).append(valor.strip())
    return d


def test_a_regra_do_install_nao_deixa_o_no_aberto_na_janela() -> None:
    """O ``TEST==`` da regra é o socket, e nada do install o tira com o broker instalado.

    A janela medida em 25/10 foi a entrega (o Hefesto parado), não o ``TEST``: às 14:01:59
    o broker estava de pé e o ``event21`` já estava fechado. A regra fecha o nó enquanto o
    socket existir; o socket é da ``.socket`` (o ``.service`` sem ``RuntimeDirectory``),
    que o install habilita e nunca para nem reinicia, e o ``.service`` sobe no boot e
    fecha o que o coldplug abriu antes de o socket existir.
    """
    regra = (RAIZ / "assets" / "72-hefesto-touchpad-motion-uaccess.rules").read_text(
        encoding="utf-8")
    fechadas = [linha for linha in regra.splitlines()
                if not linha.startswith("#") and 'MODE="0600"' in linha]
    assert [re.search(r'KERNELS=="(\d{4})', linha).group(1)  # type: ignore[union-attr]
            for linha in fechadas] == ["0005", "0003"]
    testes = {re.search(r'TEST=="([^"]+)"', linha).group(1)  # type: ignore[union-attr]
              for linha in fechadas}
    socket_ = _diretivas(RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.socket")
    servico = _diretivas(RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service")
    assert testes == set(socket_["ListenStream"]) == {hb.DEFAULT_SOCKET_PATH}
    assert socket_.get("RemoveOnStop", ["no"]) == ["no"]
    assert "RuntimeDirectory" not in servico
    assert servico["WantedBy"] == ["multi-user.target"]
    assert any(p.endswith("--fechar-tudo-e-sair") for p in servico["ExecStartPre"])
    for script in (RAIZ / "install.sh", RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"):
        tiram = [linha for linha in script.read_text(encoding="utf-8").splitlines()
                 if "systemctl" in linha and "hefesto-hidraw-broker.socket" in linha
                 and re.search(r"\b(?:stop|restart|disable|kill|mask)\b", linha)]
        assert tiram == [], script.name


def test_a_unit_deixa_o_broker_tomar_o_descritor() -> None:
    servico = _diretivas(RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service")
    filtros = servico["SystemCallFilter"]
    assert filtros[-1] == "pidfd_getfd" and "@debug" in filtros[-2]
    assert "CAP_SYS_PTRACE" in servico["CapabilityBoundingSet"][0].split()
