"""O serviço só se diz pronto (`READY=1`) com o soquete do IPC de pé.

O defeito de 16/10/2026: a unit do daemon era `Type=simple`, então o `systemctl start` voltava
no `fork`, ~0,6 s antes de o soquete existir (diário de 16/10: «Started» às 08:43:58,634 e
`ipc_server_listening` às 08:43:59,285). Quem ligava o serviço e já falava com ele recebia a
recusa, e um chamador só (a Jogar) esperava, por remendo. A cura é o daemon dizer: `Type=notify`
e `READY=1` assim que o IPC escuta.

Tudo aqui roda com um `NOTIFY_SOCKET` de mentira (um soquete unix datagram em `tmp_path`) e um
daemon de mentira: nenhum `systemctl`, nenhum serviço de verdade.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import socket
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import subsystems
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import sd_notify

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "hefesto-dualsense4unix.service"


def _campo_da_unit(nome: str) -> str | None:
    achados = re.findall(rf"^{nome}=(\S.*?)\s*$", UNIT.read_text(encoding="utf-8"), re.M)
    return achados[0] if achados else None


# -- a unit -----------------------------------------------------------------------------


def test_a_unit_e_notify_com_o_prazo_da_subida_escrito() -> None:
    """MORDIDA: volte `Type=notify` para `simple` (ou tire o prazo) e isto reprova."""
    assert _campo_da_unit("Type") == "notify"
    assert _campo_da_unit("NotifyAccess") == "main"
    assert _campo_da_unit("TimeoutStartSec") is not None, (
        "sem o prazo escrito, o `start` de um daemon que trava na subida usa o padrão do systemd")


def test_o_prazo_da_unit_e_o_do_codigo() -> None:
    """O `TimeoutStartSec` da unit e `PRAZO_DA_PARTIDA_S` são o mesmo número (um dono)."""
    prazo = _campo_da_unit("TimeoutStartSec")
    assert prazo is not None and float(prazo.rstrip("s")) == sd_notify.PRAZO_DA_PARTIDA_S


def test_a_unit_mantem_o_restart_e_o_onfailure() -> None:
    """A cura não tira o respawn nem a devolução do controle ao Linux."""
    assert _campo_da_unit("Restart") == "on-failure"
    assert _campo_da_unit("OnFailure") == "hefesto-dualsense4unix-presenca.service"


# -- o aviso ----------------------------------------------------------------------------


@pytest.fixture
def ouvinte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[socket.socket]:
    """O `NOTIFY_SOCKET` de mentira: um datagram unix que o teste lê."""
    caminho = tmp_path / "notify"
    soquete = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    soquete.bind(str(caminho))
    soquete.setblocking(False)
    monkeypatch.setenv("NOTIFY_SOCKET", str(caminho))
    try:
        yield soquete
    finally:
        soquete.close()


def _recebidas(soquete: socket.socket) -> list[str]:
    saiu: list[str] = []
    while True:
        try:
            saiu.append(soquete.recv(256).decode("utf-8"))
        except BlockingIOError:
            return saiu


def test_pronto_e_parando_chegam_ao_soquete(ouvinte: socket.socket) -> None:
    assert sd_notify.pronto() is True
    assert sd_notify.parando() is True
    assert _recebidas(ouvinte) == ["READY=1", "STOPPING=1"]


def test_sem_notify_socket_nada_e_enviado_nem_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon avulso e o `--foreground` à mão não têm `NOTIFY_SOCKET`."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    assert sd_notify.pronto() is False
    assert sd_notify.parando() is False


def test_notify_socket_sem_ouvinte_nao_levanta(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_SOCKET", str(tmp_path / "ninguem"))
    assert sd_notify.pronto() is False


# -- o daemon ---------------------------------------------------------------------------


class _Cena:
    """O que o daemon de mentira viu, na ordem: o aviso, o IPC escutando, o resto."""

    def __init__(self) -> None:
        self.ordem: list[str] = []
        self.daemon: Daemon | None = None
        self.caminho_do_ipc: Path | None = None
        self.escutava_no_aviso: list[bool] = []
        self.tarefas_no_aviso: list[list[str]] = []


def _escuta(caminho: Path | None) -> bool:
    """O soquete do IPC aceita a conexão AGORA? Só um `listen` aceita."""
    if caminho is None or not caminho.exists():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.connect(str(caminho))
        except OSError:
            return False
    return True


@pytest.fixture
def cena(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
         ouvinte: socket.socket) -> Iterator[_Cena]:
    """Um `Daemon` real com a lista de subsystems reduzida: o IPC, um marcador depois dele e
    as paradas que fecham o laço. Nada de som, de uinput nem de rádio."""
    # O caminho do soquete unix cabe em 108 bytes: o `tmp_path` do pytest estoura isso.
    run = Path(tempfile.mkdtemp(prefix="sdr", dir="/tmp"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(run))
    c = _Cena()
    original = sd_notify.notificar

    def _vigiado(mensagem: str) -> bool:
        c.ordem.append(mensagem)
        if mensagem == "READY=1" and c.daemon is not None:
            c.escutava_no_aviso.append(_escuta(c.caminho_do_ipc))
            c.tarefas_no_aviso.append([t.get_name() for t in c.daemon._tasks])
        return original(mensagem)

    monkeypatch.setattr(sd_notify, "notificar", _vigiado)
    marcador = subsystems.Passo(
        "marcador", partida=lambda d: c.ordem.append("o-que-vem-depois-do-ipc"))
    ficam = ("ipc", "tarefas", "controle", "broker", "coop")
    reduzida = tuple(p for p in subsystems.SUBSYSTEM_REGISTRY if p.nome in ficam)
    ipc = [p for p in reduzida if p.nome == "ipc"]
    outros = [p for p in reduzida if p.nome != "ipc"]
    monkeypatch.setattr(subsystems, "SUBSYSTEM_REGISTRY", (*ipc, marcador, *outros))
    try:
        yield c
    finally:
        shutil.rmtree(run, ignore_errors=True)


def _daemon(c: _Cena, *, ipc: bool) -> Daemon:
    config = DaemonConfig(
        poll_hz=200, ipc_enabled=ipc, udp_enabled=False, autoswitch_enabled=False,
        mouse_emulation_enabled=False, keyboard_emulation_enabled=False,
        ps_button_action="none", mic_button_toggles_system=False,
    )
    d = Daemon(controller=FakeController(transport="usb"), config=config)
    c.daemon = d
    if ipc:
        from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_name, runtime_dir

        c.caminho_do_ipc = runtime_dir(ensure=True) / ipc_socket_name()
    return d


async def _subir_e_parar(d: Daemon, c: _Cena) -> None:
    tarefa = asyncio.create_task(d.run())
    for _ in range(500):
        if "o-que-vem-depois-do-ipc" in c.ordem or tarefa.done():
            break
        await asyncio.sleep(0.01)
    d.stop()
    await asyncio.wait_for(tarefa, timeout=15)


@pytest.mark.asyncio
async def test_o_ready_chega_com_o_ipc_escutando_e_antes_do_resto(
        cena: _Cena, ouvinte: socket.socket) -> None:
    """MORDIDA: mande o `READY=1` antes do `_safe_start("ipc")` e `escutava_no_aviso` é False;
    mande-o depois da lista e ele vem DEPOIS do marcador."""
    d = _daemon(cena, ipc=True)
    await _subir_e_parar(d, cena)
    assert cena.escutava_no_aviso == [True], "o READY=1 saiu sem o soquete do IPC escutando"
    assert cena.ordem.index("READY=1") < cena.ordem.index("o-que-vem-depois-do-ipc"), (
        f"o pronto esperou o que o IPC não exige: {cena.ordem}")
    assert cena.ordem.count("READY=1") == 1, "o READY=1 saiu mais de uma vez"
    assert _recebidas(ouvinte)[0] == "READY=1"


@pytest.mark.asyncio
async def test_com_o_ipc_desligado_o_ready_sai_depois_do_poll_loop(cena: _Cena) -> None:
    """Sem IPC por configuração não há soquete a esperar: o pronto é o fim da primeira fase."""
    d = _daemon(cena, ipc=False)
    await _subir_e_parar(d, cena)
    assert cena.ordem.count("READY=1") == 1
    assert cena.ordem.index("o-que-vem-depois-do-ipc") < cena.ordem.index("READY=1")
    assert cena.tarefas_no_aviso == [["poll_loop"]], "o pronto saiu antes do poll_loop"


@pytest.mark.asyncio
async def test_ipc_essencial_que_falha_nao_diz_pronto(
        cena: _Cena, monkeypatch: pytest.MonkeyPatch) -> None:
    """O systemd passa a ver a falha de subida, e não um «active» falso."""
    from hefesto_dualsense4unix.daemon.lifecycle import IpcIndisponivel

    async def _quebra(_daemon: Any) -> None:
        raise OSError("soquete ocupado")

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.ipc.start_ipc", _quebra)
    d = _daemon(cena, ipc=True)
    with pytest.raises(IpcIndisponivel):
        await asyncio.wait_for(d.run(), timeout=15)
    assert "READY=1" not in cena.ordem


@pytest.mark.asyncio
async def test_sem_notify_socket_o_daemon_sobe_e_para_calado(
        cena: _Cena, monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon avulso: nada enviado, nada levantado."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    d = _daemon(cena, ipc=True)
    await _subir_e_parar(d, cena)
    assert cena.escutava_no_aviso == [True]


def test_o_stop_diz_parando_uma_vez(cena: _Cena, ouvinte: socket.socket) -> None:
    d = _daemon(cena, ipc=False)
    d._stop_event = asyncio.Event()
    d.stop()
    d.stop()
    assert _recebidas(ouvinte) == ["STOPPING=1"]

