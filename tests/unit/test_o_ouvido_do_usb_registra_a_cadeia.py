"""O ouvido do USB registra o que entra, sai, volta, muda de velocidade e não aparece.

O ``/sys`` de mentira (``tests/fixtures/cadeia_usb/``) muda sob o ouvido; o netlink é um
``socketpair`` de datagrama com as mensagens do kernel.

Mordidas:

* tirar o ``devnum`` da comparação em ``Comparador.observar``: a volta rápida some no laço sem
  netlink, e :func:`test_sem_netlink_o_laco_acha_a_volta_pelo_devnum` reprova;
* gravar o ``serial`` na foto: :func:`test_nenhum_serial_no_diario` reprova pelo portão de endereço
  de rádio;
* tirar o ``except OSError`` de ``_ouvir``: o ``ENOBUFS`` de uma rajada mata o ouvido
  para a sessão inteira, e os dois testes de ``test_o_erro_do_netlink_*`` reprovam.
"""

from __future__ import annotations

import asyncio
import errno
import importlib.util
import inspect
import socket
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento
from tests.fixtures.cadeia_usb.montar import SERIAL_FORJADO, SysDeMentira

RAIZ = Path(__file__).resolve().parents[2]
ADAPTADOR = "3-1.1.3"


class Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path / "sys")


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


def _ouvido(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio, boot: str = "boot-a",
) -> ou.Ouvido:
    return ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()),
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO,
        boot_id=boot,
        relogio=relogio,
        agora=lambda: 1_700_000_000.0 + relogio.t,
    )


def _linhas(tmp_path: Path) -> list[dict[str, Any]]:
    return du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO)


def _eventos(tmp_path: Path) -> list[tuple[str, str]]:
    return [(e["o_que"], str(e.get("no", ""))) for e in _linhas(tmp_path)]


def test_a_primeira_leitura_so_diz_desde_quando_ouve(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    _ouvido(sys_usb, tmp_path, relogio).comecar(com_netlink=True)
    linhas = _linhas(tmp_path)
    assert [e["o_que"] for e in linhas] == [du.COMECOU_A_OUVIR]
    assert linhas[0]["boot_id"] == "boot-a"


def test_entrou_saiu_e_voltou(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    adaptador = dict(sys_usb.nos[ADAPTADOR])

    sys_usb.tirar(ADAPTADOR)
    ouvido.reler()
    relogio.t += 3
    sys_usb.por(ADAPTADOR, adaptador)
    sys_usb.mudar(ADAPTADOR, devnum="21")
    ouvido.reler()
    sys_usb.tirar(ADAPTADOR)
    ouvido.reler()
    relogio.t += 30
    sys_usb.por(ADAPTADOR, adaptador)
    ouvido.reler()

    assert _eventos(tmp_path)[1:] == [
        (du.SAIU, ADAPTADOR), (du.VOLTOU, ADAPTADOR), (du.SAIU, ADAPTADOR), (du.ENTROU, ADAPTADOR)]
    saida = _linhas(tmp_path)[1]
    assert saida["tipo"] == "Bluetooth"
    assert saida["fabricante_da_base"] == "Rádios de Mentira"
    assert saida["produto"] == "Adaptador de rádio"
    assert saida["driver"] == "btusb"
    assert saida["velocidade_mbps"] == 12.0
    assert saida["hub_fisico"] == "3-1", "a linha diz o hub físico, não o nó interno"


def test_mudou_de_velocidade_contra_a_ultima_registrada(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    wifi = dict(sys_usb.nos["3-1.4"])
    sys_usb.tirar("3-1.4")
    ouvido.reler()
    relogio.t += 2
    sys_usb.por("3-1.4", wifi)
    sys_usb.mudar("3-1.4", speed="12", devnum="30")
    ouvido.reler()

    eventos = _linhas(tmp_path)[1:]
    assert [e["o_que"] for e in eventos] == [du.SAIU, du.VOLTOU, du.MUDOU_DE_VELOCIDADE]
    assert (eventos[-1]["antes"], eventos[-1]["depois"]) == (480.0, 12.0)


def test_a_velocidade_de_outro_boot_vale(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    _ouvido(sys_usb, tmp_path, relogio, "boot-a").comecar(com_netlink=True)
    sys_usb.mudar("3-1.4", speed="12")
    _ouvido(sys_usb, tmp_path, relogio, "boot-b").comecar(com_netlink=True)
    assert (du.MUDOU_DE_VELOCIDADE, "3-1.4") in _eventos(tmp_path)


def test_nao_apareceu_neste_inicio_uma_vez_por_boot(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    _ouvido(sys_usb, tmp_path, relogio, "boot-a").comecar(com_netlink=True)
    sys_usb.tirar(ADAPTADOR)
    sys_usb.tirar("3-1.1.2")  # o receptor também falta, mas não é dos que se esperam

    relogio.t = 0.0
    segundo = _ouvido(sys_usb, tmp_path, relogio, "boot-b")
    segundo.comecar(com_netlink=True)
    relogio.t = 30.0
    assert segundo.conferir_ausentes() == []
    relogio.t = 61.0
    ausentes = segundo.conferir_ausentes()
    assert [(o, f.no, f.tipo) for o, f in ausentes] == [
        (du.NAO_APARECEU, ADAPTADOR, "Bluetooth")]
    relogio.t = 200.0
    assert segundo.conferir_ausentes() == []

    relogio.t = 0.0
    reinicio = _ouvido(sys_usb, tmp_path, relogio, "boot-b")
    reinicio.comecar(com_netlink=True)
    relogio.t = 61.0
    assert reinicio.conferir_ausentes() == [], "o daemon que reinicia no mesmo boot não repete"
    assert [e for e, _c in _eventos(tmp_path)].count(du.NAO_APARECEU) == 1


def _portao_de_endereco() -> ModuleType:
    especie = importlib.util.spec_from_file_location(
        "check_endereco_de_radio", RAIZ / "scripts" / "check_endereco_de_radio.py")
    assert especie is not None and especie.loader is not None
    modulo = importlib.util.module_from_spec(especie)
    especie.loader.exec_module(modulo)
    return modulo


def test_nenhum_serial_no_diario(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    portao = _portao_de_endereco()
    assert portao.acusa_serial(SERIAL_FORJADO), (
        "o serial forjado tem de ser da forma que o portão acusa")
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    sys_usb.tirar(ADAPTADOR)
    ouvido.reler()

    for arquivo in (tmp_path / "estado").iterdir():
        texto = arquivo.read_text(encoding="utf-8")
        acusados = [a for linha in texto.splitlines() for a in portao.acusa_serial(linha)]
        assert acusados == [], (arquivo.name, acusados)
        assert SERIAL_FORJADO not in texto


class _Daemon:
    def __init__(self) -> None:
        self.parar = False

    def _is_stopping(self) -> bool:
        return self.parar


async def _ate(condicao: Any, prazo: float = 5.0) -> None:
    fim = asyncio.get_running_loop().time() + prazo
    while not condicao():
        assert asyncio.get_running_loop().time() < fim, "o ouvido não chegou lá no prazo"
        await asyncio.sleep(0.01)


def test_sem_netlink_o_laco_acha_a_volta_pelo_devnum(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    daemon = _Daemon()

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=lambda: None, intervalo=0.02))
        await _ate(lambda: _linhas(tmp_path))
        sys_usb.mudar(ADAPTADOR, devnum="44")
        await _ate(lambda: (du.VOLTOU, ADAPTADOR) in _eventos(tmp_path), prazo=2.0)
        daemon.parar = True
        await asyncio.wait_for(laco, 2.0)

    asyncio.run(cenario())
    eventos = _eventos(tmp_path)
    assert eventos[0][0] == du.COMECOU_A_OUVIR
    assert _linhas(tmp_path)[0]["como"] == "releitura a cada 2 s"
    assert eventos[-1][0] == du.PAROU_DE_OUVIR
    assert du.SAIU not in [e for e, _c in eventos], "a volta entre duas leituras não é saída"


def _uevent(acao: str, devtype: str) -> bytes:
    return (f"{acao}@/devices/usb3/3-1/3-1.1/3-1.1.3\0ACTION={acao}\0"
            f"DEVPATH=/devices/usb3/3-1/3-1.1/3-1.1.3\0SUBSYSTEM=usb\0DEVTYPE={devtype}\0"
            "SEQNUM=1\0").encode()


def test_com_netlink_o_remove_do_aparelho_rele_e_o_da_interface_nao(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    daemon = _Daemon()
    nosso, kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    nosso.setblocking(False)

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=lambda: nosso, acomodar=0.01, prazo=0.05))
        await _ate(lambda: _linhas(tmp_path))
        sys_usb.tirar(ADAPTADOR)
        kernel.send(_uevent("remove", "usb_interface"))
        await asyncio.sleep(0.3)
        assert du.SAIU not in [e for e, _c in _eventos(tmp_path)], "interface não relê"
        kernel.send(_uevent("remove", "usb_device"))
        await _ate(lambda: (du.SAIU, ADAPTADOR) in _eventos(tmp_path), prazo=2.0)
        daemon.parar = True
        await asyncio.wait_for(laco, 2.0)

    try:
        asyncio.run(cenario())
    finally:
        kernel.close()
    assert _linhas(tmp_path)[0]["como"] == "netlink"


def _espera_que_falha(pendentes: list[OSError]) -> Any:
    """O ``_esperar_evento`` de mentira: levanta o erro posto na fila, senão nada chega."""

    async def esperar(_sock: socket.socket, _prazo: float) -> bool:
        if pendentes:
            raise pendentes.pop(0)
        await asyncio.sleep(0.01)
        return False

    return esperar


@pytest.mark.parametrize(
    ("falha", "como_segue"), [(errno.ENOBUFS, "netlink"), (errno.EBADF, "releitura")])
def test_o_erro_do_netlink_rele_e_o_ouvido_segue(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio,
        monkeypatch: pytest.MonkeyPatch, falha: int, como_segue: str) -> None:
    """A saída cujo aviso o kernel jogou fora (``ENOBUFS``) se acha pela releitura; com o socket
    caído (``EBADF``), o laço passa à releitura periódica e ainda acha a volta pelo ``devnum``."""
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    daemon = _Daemon()
    pendentes: list[OSError] = []
    monkeypatch.setattr(ou, "_esperar_evento", _espera_que_falha(pendentes))
    nosso, kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    nosso.setblocking(False)

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=lambda: nosso, acomodar=0.01, intervalo=0.02, prazo=0.05))
        await _ate(lambda: _linhas(tmp_path))
        adaptador = dict(sys_usb.nos[ADAPTADOR])
        sys_usb.tirar(ADAPTADOR)
        pendentes.append(OSError(falha, "erro de mentira"))
        await _ate(lambda: (du.SAIU, ADAPTADOR) in _eventos(tmp_path), prazo=2.0)
        assert not laco.done(), "o erro do netlink matou o ouvido"
        if como_segue == "releitura":
            sys_usb.por(ADAPTADOR, adaptador)
            await _ate(lambda: (du.VOLTOU, ADAPTADOR) in _eventos(tmp_path), prazo=2.0)
        daemon.parar = True
        await asyncio.wait_for(laco, 2.0)

    try:
        asyncio.run(cenario())
    finally:
        kernel.close()
        nosso.close()
    assert _eventos(tmp_path)[-1][0] == du.PAROU_DE_OUVIR


def test_a_mensagem_do_kernel_se_le_por_campo() -> None:
    campos = ou.eventos_de(_uevent("add", "usb_device"))
    assert (campos["ACTION"], campos["SUBSYSTEM"], campos["DEVTYPE"]) == (
        "add", "usb", "usb_device")
    assert ou.interessa(_uevent("add", "usb_device"))
    assert not ou.interessa(_uevent("bind", "usb_device"))
    assert not ou.interessa(b"libudev\0qualquer coisa")


def test_o_daemon_liga_o_ouvido_pelo_safe_start() -> None:
    assert '_safe_start("ouvido_do_usb"' in inspect.getsource(Daemon.run)
