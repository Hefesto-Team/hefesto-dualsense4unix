"""O ouvido do USB reabre o netlink que caiu, com recuo, e o ``comecar`` não mata a tarefa calado.

O socket de uevent é um ``socketpair`` de datagrama; o erro que derruba o socket e o ``abrir`` que
falha são de mentira. O ``acordar_a_volta`` e o relógio da conexão são dublês que só anotam.

Vale para todo controle no cabo: o ``add`` da Sony de cada porta chega ao relógio com a própria
porta, antes e depois da queda do socket, e o que o ouvido guarda é só o socket e o recuo, nunca
um controle, um adaptador ou um jogador. O estado por controle é de quem ouve o ``acordar_a_volta``.

Mordidas:

* tirar a reabertura do laço (o ``elif sock is None and relogio() >= tentar_em``): o socket que
  caiu nunca volta e :func:`test_o_netlink_que_caiu_se_reabre_e_o_add_da_sony_acorda_a_volta`
  reprova;
* trocar ``min(recuo * 2, recuo_maximo)`` por ``recuo``: o recuo não dobra e
  :func:`test_o_recuo_dobra_ate_o_teto` reprova;
* trocar o mesmo por ``recuo * 2``: o recuo passa do teto e o mesmo teste reprova;
* tirar o ``try`` do ``comecar``: :func:`test_o_comecar_com_o_censo_que_falha_nao_mata_o_ouvido`
  reprova.
"""

from __future__ import annotations

import asyncio
import errno
import itertools
import socket
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo, ler_o_barramento
from tests.fixtures.cadeia_usb.montar import SysDeMentira

PORTA_A = "3-1.1.1"
PORTA_B = "3-2"
ADAPTADOR = "3-1.1.3"


class _Daemon:
    def __init__(self) -> None:
        self.parar = False

    def _is_stopping(self) -> bool:
        return self.parar


class _RelogioDaConexao:
    def __init__(self) -> None:
        self.portas: list[str] = []

    def usb_entrou(self, no: str) -> None:
        self.portas.append(no)


def _uevent(acao: str, porta: str, produto: str = "54c/ce6/100") -> bytes:
    caminho = f"/devices/pci0000:00/0000:aa:00.0/usb3/{porta}"
    return (f"{acao}@{caminho}\0ACTION={acao}\0DEVPATH={caminho}\0SUBSYSTEM=usb\0"
            f"DEVTYPE=usb_device\0PRODUCT={produto}\0SEQNUM=1\0").encode()


async def _ate(condicao: Any, prazo: float, se_faltar: str) -> None:
    fim = asyncio.get_running_loop().time() + prazo
    while not condicao():
        assert asyncio.get_running_loop().time() < fim, se_faltar
        await asyncio.sleep(0.01)


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path / "sys")


def _ouvido(sys_usb: SysDeMentira, tmp_path: Path) -> ou.Ouvido:
    return ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()),
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO, boot_id="boot-a")


def _que_cai_uma_vez(monkeypatch: pytest.MonkeyPatch, falha: int) -> list[OSError]:
    """O ``_esperar_evento`` que levanta o erro posto na fila e, fora isso, é o de verdade."""
    pendentes: list[OSError] = []
    verdadeiro = ou._esperar_evento

    async def esperar(sock: socket.socket, prazo: float, daemon: Any = None) -> bool:
        if pendentes:
            raise pendentes.pop(0)
        return await verdadeiro(sock, prazo, daemon)

    monkeypatch.setattr(ou, "_esperar_evento", esperar)
    pendentes.append(OSError(falha, "erro de mentira"))
    return pendentes


def test_o_netlink_que_caiu_se_reabre_e_o_add_da_sony_acorda_a_volta(
        sys_usb: SysDeMentira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-2111-O-NETLINK-QUE-CAIU-SE-REABRE-COM-RECUO: o ``add`` depois da queda chega.

    A primeira reabertura falha e a segunda dá o socket; o ``add`` de dois controles em portas
    diferentes, e o ``remove`` de um deles, chegam ao sino da volta e ao relógio de cada porta.
    """
    acordou: list[str] = []
    monkeypatch.setattr(
        connection, "acordar_a_volta", lambda _daemon, pelo="": acordou.append(pelo))
    relogio_da_conexao = _RelogioDaConexao()
    monkeypatch.setattr(ou, "RELOGIO", relogio_da_conexao)
    _que_cai_uma_vez(monkeypatch, errno.ECONNRESET)
    primeiro, kernel_1 = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    segundo, kernel_2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    for aberto in (primeiro, segundo):
        aberto.setblocking(False)
    sockets: list[socket.socket | None] = [primeiro, None, segundo]
    chamadas: list[float] = []

    def abrir() -> socket.socket | None:
        chamadas.append(time.monotonic())
        return sockets[len(chamadas) - 1] if len(chamadas) <= len(sockets) else segundo

    daemon = _Daemon()
    ouvido = _ouvido(sys_usb, tmp_path)

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=abrir, acomodar=0.01, intervalo=0.01, prazo=0.05,
            recuo_inicial=0.05, recuo_maximo=0.2))
        await _ate(lambda: len(chamadas) >= 3 or laco.done(), 3.0,
                   "o netlink que caiu nunca foi reaberto")
        assert not laco.done(), "a queda do socket matou o ouvido"
        assert len(chamadas) >= 3, "o netlink que caiu nunca foi reaberto"
        assert chamadas[2] - chamadas[1] >= 0.1, "a segunda abertura espera o recuo dobrado"
        kernel_2.send(_uevent("add", PORTA_A))
        await _ate(lambda: relogio_da_conexao.portas == [PORTA_A], 3.0,
                   "o add da Sony depois da reabertura não chegou ao relógio")
        kernel_2.send(_uevent("remove", PORTA_A))
        kernel_2.send(_uevent("add", PORTA_B))
        await _ate(lambda: relogio_da_conexao.portas == [PORTA_A, PORTA_B], 3.0,
                   "o add da segunda porta não chegou ao relógio")
        daemon.parar = True
        await asyncio.wait_for(laco, 3.0)

    try:
        asyncio.run(cenario())
    finally:
        for ponta in (kernel_1, kernel_2, primeiro, segundo):
            ponta.close()
    assert len(chamadas) == 3
    assert acordou.count("netlink") >= 3, "cada add e o remove tocam o sino da volta"


def test_o_recuo_dobra_ate_o_teto(sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Aberturas que falham em seguida: 0,1, 0,2, 0,4, 0,4 e 0,4 s, nunca mais que o teto."""
    chamadas: list[float] = []
    ao_fim, kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    ao_fim.setblocking(False)

    def abrir() -> socket.socket | None:
        chamadas.append(time.monotonic())
        if len(chamadas) == 1:
            return None
        return ao_fim if len(chamadas) >= 6 else None

    daemon = _Daemon()
    ouvido = _ouvido(sys_usb, tmp_path)

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=abrir, acomodar=0.01, intervalo=0.01, prazo=0.05,
            recuo_inicial=0.1, recuo_maximo=0.4))
        await _ate(lambda: len(chamadas) >= 6, 8.0, "o recuo não deixou chegar à sexta abertura")
        daemon.parar = True
        await asyncio.wait_for(laco, 3.0)

    try:
        asyncio.run(cenario())
    finally:
        kernel.close()
    intervalos = [b - a for a, b in itertools.pairwise(chamadas)]
    assert intervalos[0] >= 0.1, intervalos
    assert intervalos[1] >= 0.2, "o recuo dobra a cada abertura que falha"
    assert intervalos[2] >= 0.4, intervalos
    assert 0.4 <= intervalos[3] < 0.7, "o recuo para no teto"
    assert 0.4 <= intervalos[4] < 0.7, "o recuo segue no teto"


def test_o_comecar_com_o_censo_que_falha_nao_mata_o_ouvido(
        tmp_path: Path, sys_usb: SysDeMentira) -> None:
    """A primeira releitura que levanta vai ao log e o ouvido segue ouvindo."""
    leituras: list[int] = []

    def censo() -> Censo:
        leituras.append(1)
        if len(leituras) == 1:
            raise RuntimeError("o /sys sumiu por um instante")
        return ler_o_barramento(**sys_usb.fontes())

    ouvido = ou.Ouvido(
        ler_censo=censo, diario=tmp_path / "estado" / du.NOME_DO_DIARIO, boot_id="boot-a")
    daemon = _Daemon()

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=lambda: None, intervalo=0.01, recuo_inicial=5.0))
        await _ate(lambda: len(leituras) >= 3 or laco.done(), 3.0,
                   "o ouvido não releu o censo depois do começo")
        assert not laco.done(), "a releitura que falhou no começo matou o ouvido"
        daemon.parar = True
        await asyncio.wait_for(laco, 3.0)

    asyncio.run(cenario())
    diario = du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO)
    assert diario[0]["o_que"] == du.COMECOU_A_OUVIR
    assert diario[-1]["o_que"] == du.PAROU_DE_OUVIR

