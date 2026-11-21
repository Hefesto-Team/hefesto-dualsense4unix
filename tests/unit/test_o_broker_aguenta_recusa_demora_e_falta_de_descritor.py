"""O broker e o cliente aguentam recusa, demora do logind e falta de descritor.

O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR-01 (20/11/2026). A recusa diz o motivo antes
de fechar e o cliente recua em vez de reabrir a conexão; o logind lento não prende o laço nem
derruba a lease; o accept sem descritor sai do seletor por uma pausa; há teto de conexões por
conta e prazo para a conexão muda, que também não segura a graça da entrega do físico.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o cliente sem o recuo reprova o caso dos
cem pedidos; a linha de recusa por pedido reprova o mesmo caso; a pergunta ao logind de volta ao
laço reprova o caso da demora; o teto de conexões tirado reprova o caso das 64; o ``continue``
cego no accept reprova o caso do descritor; a conexão que zera a graça ao chegar reprova o caso da
conexão muda; o cliente que fecha no timeout reprova o caso da lease.
"""
from __future__ import annotations

import errno
import json
import os
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.integrations import hidraw_broker_client as cliente_mod
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient
from tests.unit.test_o_broker_serve_quem_esta_na_frente import LogindFalso

O_USUARIO = 4001
OUTRA = 4000


@pytest.fixture
def logind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LogindFalso:
    falso = LogindFalso(tmp_path)
    monkeypatch.setenv(hb.LOGINCTL_ENV, str(falso.script))
    return falso


@pytest.fixture
def pasta_curta() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="b-") as pasta:
        yield Path(pasta)


def _estado(
    agora: list[float], eventos: list[tuple[str, dict[str, object]]] | None = None,
    *, vazio: Path | None = None,
) -> hb.BrokerState:
    def log(evento: str, **campos: object) -> None:
        if eventos is not None:
            eventos.append((evento, campos))

    raizes: dict[str, Any] = {}
    if vazio is not None:
        raizes = dict(
            no_nasce_fechado=True, dev_root=str(vazio), dev_input_root=str(vazio),
            sys_class_input=str(vazio), sys_class_hidraw=str(vazio), sys_class_bluetooth=str(vazio),
        )
    return hb.BrokerState(
        allowed_uid=None, ops=object(), quem_esta_na_frente=hb.uid_da_sessao_ativa,
        relogio=lambda: agora[0], log=log, **raizes,
    )


class _Banca:
    """O Broker em socketpair: cada ``cliente(uid)`` é uma conexão com o uid dito."""

    def __init__(self, estado: hb.BrokerState, agora: list[float],
                 eventos: list[tuple[str, dict[str, object]]], graca: float = 0.0) -> None:
        self.uids: dict[int, int] = {}

        def peercred(sock: socket.socket) -> tuple[int, int, int]:
            return (1234, self.uids[sock.fileno()], 0)

        def log(evento: str, **campos: object) -> None:
            eventos.append((evento, campos))

        self.broker = hb.Broker(estado, None, peercred_fn=peercred, log=log,
                                graca_da_entrega_s=graca, relogio=lambda: agora[0])
        self.pontas: list[socket.socket] = []

    def cliente(self, uid: int) -> socket.socket:
        lado_broker, lado_cliente = socket.socketpair()
        self.uids[lado_broker.fileno()] = uid
        self.pontas.append(lado_cliente)
        self.broker.register_client(lado_broker)
        return lado_cliente


def _linhas_de(eventos: list[tuple[str, dict[str, object]]], nome: str) -> list[dict[str, object]]:
    return [campos for evento, campos in eventos if evento == nome]


def test_cem_pedidos_em_dez_segundos_viram_poucas_conexoes_e_uma_linha(
    logind: LogindFalso, pasta_curta: Path
) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: recusa recuada."""
    logind.na_frente("c9", os.getuid() + 1)
    eventos: list[tuple[str, dict[str, object]]] = []
    conexoes: list[int] = []

    def peercred(sock: socket.socket) -> tuple[int, int, int]:
        conexoes.append(1)
        return hb.peer_credentials(sock)

    caminho = str(pasta_curta / "s")
    escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    escuta.bind(caminho)
    escuta.listen(8)
    agora = [100.0]
    broker = hb.Broker(
        _estado(agora, eventos), escuta, peercred_fn=peercred,
        log=lambda e, **c: eventos.append((e, c)), graca_da_entrega_s=0,
    )
    parar = threading.Event()

    def laco() -> None:
        while not parar.is_set():
            broker.step(timeout=0.02)

    thread = threading.Thread(target=laco, daemon=True)
    thread.start()
    relogio = [0.0]
    cliente = HidrawBrokerClient(caminho, relogio=lambda: relogio[0])
    try:
        respostas = []
        for _ in range(100):
            respostas.append(cliente.ping())
            relogio[0] += 0.1
    finally:
        parar.set()
        thread.join(timeout=5)
        cliente.close()
        escuta.close()
    assert not any(respostas)
    assert 1 <= len(conexoes) <= 5, f"{len(conexoes)} conexões para 100 pedidos"
    recusas = _linhas_de(eventos, "peer_rejected")
    assert len(recusas) == 1 and recusas[0]["motivo"] == "nao_e_quem_esta_na_frente"


def test_a_recusa_diz_o_motivo_antes_de_fechar(logind: LogindFalso) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: motivo dito."""
    logind.na_frente("c2", O_USUARIO)
    eventos: list[tuple[str, dict[str, object]]] = []
    estado = _estado([100.0], eventos)
    banca = _Banca(estado, [100.0], eventos)
    ponta = banca.cliente(OUTRA)
    ponta.settimeout(2.0)
    assert json.loads(ponta.recv(256).split(b"\n")[0]) == {
        "ok": False, "error": "reject_nao_e_quem_esta_na_frente"}
    logind.vazio()
    estado.esquecer_a_sessao_lida()
    ponta = banca.cliente(O_USUARIO)
    ponta.settimeout(2.0)
    assert json.loads(ponta.recv(256).split(b"\n")[0])["error"] == "reject_sem_sessao_ativa"


def test_o_cliente_recua_cinco_segundos_depois_da_recusa(pasta_curta: Path) -> None:
    caminho = str(pasta_curta / "s")
    escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    escuta.bind(caminho)
    escuta.listen(8)
    chegaram: list[int] = []

    def servidor() -> None:
        escuta.settimeout(2.0)
        while True:
            try:
                conexao, _ = escuta.accept()
            except OSError:
                return
            chegaram.append(1)
            conexao.recv(256)
            conexao.sendall(b'{"ok": false, "error": "reject_sem_sessao_ativa"}\n')
            conexao.close()

    thread = threading.Thread(target=servidor, daemon=True)
    thread.start()
    relogio = [10.0]
    cliente = HidrawBrokerClient(caminho, relogio=lambda: relogio[0])
    try:
        assert cliente.ping() is False
        relogio[0] += cliente_mod.RECUO_DA_RECUSA_S - 0.1
        assert cliente.ping() is False
        assert len(chegaram) == 1, "dentro do recuo o cliente não bate de novo"
        relogio[0] += 0.2
        assert cliente.ping() is False
        assert len(chegaram) == 2
    finally:
        cliente.close()
        escuta.close()
        thread.join(timeout=5)


def test_o_logind_que_demora_nao_prende_o_laco_nem_derruba_a_lease(logind: LogindFalso) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: logind lento."""
    logind.na_frente("c2", O_USUARIO)
    agora = [100.0]
    eventos: list[tuple[str, dict[str, object]]] = []
    banca = _Banca(_estado(agora, eventos), agora, eventos)
    primeira = banca.cliente(O_USUARIO)
    assert _linhas_de(eventos, "peer_accepted")
    logind.script.write_text("#!/bin/sh\nsleep 2.5\nexit 1\n", encoding="utf-8")
    agora[0] += 5 * hb.VALIDADE_DA_SESSAO_S
    antes = time.monotonic()
    segunda = banca.cliente(O_USUARIO)
    gasto = time.monotonic() - antes
    assert gasto < 0.8, f"o laço esperou {gasto:.2f} s pelo logind"
    assert [c["peer_uid"] for c in _linhas_de(eventos, "peer_accepted")] == [O_USUARIO, O_USUARIO]
    assert not _linhas_de(eventos, "peer_rejected")
    assert not _linhas_de(eventos, "peer_solto")
    del primeira, segunda


def test_sessenta_e_quatro_conexoes_do_mesmo_uid_viram_dezesseis(logind: LogindFalso) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: teto por conta."""
    logind.na_frente("c2", O_USUARIO)
    eventos: list[tuple[str, dict[str, object]]] = []
    banca = _Banca(_estado([100.0], eventos), [100.0], eventos)
    pontas = [banca.cliente(O_USUARIO) for _ in range(64)]
    assert len(_linhas_de(eventos, "peer_accepted")) == hb.MAX_CONEXOES_POR_UID == 16
    recusas = _linhas_de(eventos, "peer_rejected")
    assert [c["motivo"] for c in recusas] == ["conexoes_demais"]
    pontas[-1].settimeout(2.0)
    assert json.loads(pontas[-1].recv(256))["error"] == "reject_conexoes_demais"


class _EscutaSemDescritor(socket.socket):
    """Uma escuta que sempre tem conexão esperando e nunca tem descritor para aceitá-la."""

    chamadas = 0

    def accept(self) -> tuple[socket.socket, object]:
        self.chamadas += 1
        raise OSError(errno.EMFILE, "Too many open files")


def test_sem_descritor_o_accept_sai_do_seletor_e_o_laco_nao_gira(pasta_curta: Path) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: sem descritor."""
    caminho = str(pasta_curta / "s")
    escuta = _EscutaSemDescritor(socket.AF_UNIX, socket.SOCK_STREAM)
    escuta.bind(caminho)
    escuta.listen(8)
    esperando = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    esperando.connect(caminho)
    agora = [100.0]
    eventos: list[tuple[str, dict[str, object]]] = []
    broker = hb.Broker(
        _estado(agora, eventos), escuta, log=lambda e, **c: eventos.append((e, c)),
        graca_da_entrega_s=0, relogio=lambda: agora[0],
    )
    for _ in range(200):
        broker.step(timeout=0)
        agora[0] += 0.01
    assert escuta.chamadas <= 3, f"{escuta.chamadas} voltas em 2 s"
    assert _linhas_de(eventos, "accept_sem_descritor")
    esperando.close()
    escuta.close()


def test_conexao_muda_nao_segura_a_entrega_do_fisico_e_cai_no_prazo(
    logind: LogindFalso, tmp_path: Path
) -> None:
    logind.na_frente("c2", O_USUARIO)
    vazio = tmp_path / "hidraw"
    vazio.mkdir()
    agora = [100.0]
    eventos: list[tuple[str, dict[str, object]]] = []
    estado = _estado(agora, eventos, vazio=vazio)
    banca = _Banca(estado, agora, eventos, graca=5.0)
    pedinte = banca.cliente(O_USUARIO)
    pedinte.sendall(b'{"cmd": "ping"}\n')
    banca.broker.step(timeout=0.5)
    pedinte.close()
    banca.broker.step(timeout=0.5)
    muda = banca.cliente(O_USUARIO)
    agora[0] += 5.0 + 1.0
    banca.broker.tique_da_entrega()
    assert estado.entregue, "a conexão que só chegou e calou segurou a graça"
    agora[0] += hb.PRAZO_DA_CONEXAO_MUDA_S
    banca.broker.tique_da_entrega()
    assert [c["motivo"] for c in _linhas_de(eventos, "peer_solto")] == ["sem_pedido_no_prazo"]
    muda.settimeout(2.0)
    assert muda.recv(16) == b""


def test_a_conexao_que_pediu_algo_nao_cai_por_prazo(logind: LogindFalso) -> None:
    logind.na_frente("c2", O_USUARIO)
    agora = [100.0]
    eventos: list[tuple[str, dict[str, object]]] = []
    banca = _Banca(_estado(agora, eventos), agora, eventos, graca=30.0)
    ponta = banca.cliente(O_USUARIO)
    ponta.sendall(b'{"cmd": "ping"}\n')
    banca.broker.step(timeout=0.5)
    agora[0] += 10 * hb.PRAZO_DA_CONEXAO_MUDA_S
    banca.broker.tique_da_entrega()
    assert not _linhas_de(eventos, "peer_solto")


def test_o_timeout_de_uma_resposta_nao_fecha_a_lease(pasta_curta: Path) -> None:
    """D-2011-O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR: a lease fica."""
    caminho = str(pasta_curta / "s")
    escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    escuta.bind(caminho)
    escuta.listen(8)
    conexoes: list[int] = []

    def servidor() -> None:
        escuta.settimeout(5.0)
        try:
            conexao, _ = escuta.accept()
        except OSError:
            return
        conexoes.append(1)
        leitor = conexao.makefile("rb")
        leitor.readline()
        time.sleep(0.5)
        conexao.sendall(b'{"ok": true, "atrasada": true}\n')
        leitor.readline()
        conexao.sendall(b'{"ok": true}\n')
        try:
            escuta.settimeout(0.5)
            segunda, _ = escuta.accept()
            conexoes.append(1)
            segunda.close()
        except OSError:
            return

    thread = threading.Thread(target=servidor, daemon=True)
    thread.start()
    cliente = HidrawBrokerClient(caminho, timeout_s=0.2)
    try:
        assert cliente.ping() is False
        time.sleep(0.6)
        assert cliente.ping() is True, "a resposta atrasada tem de ser descartada, não lida"
    finally:
        cliente.close()
        thread.join(timeout=5)
        escuta.close()
    assert len(conexoes) == 1, "o timeout de uma resposta fechou a conexão, que é a lease"


def test_a_unit_diz_o_teto_de_descritores() -> None:
    raiz = Path(hb.__file__).resolve().parents[3]
    unit = raiz / "assets" / "systemd" / "hefesto-hidraw-broker.service"
    linhas = unit.read_text(encoding="utf-8").splitlines()
    assert "LimitNOFILE=4096" in linhas
