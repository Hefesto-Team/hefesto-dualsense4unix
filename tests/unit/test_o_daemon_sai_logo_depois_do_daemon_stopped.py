"""O daemon sai logo depois do ``daemon_stopped`` (04/11/2026).

A medida: desde 02/11, com a Imersão assinando ``jogo.tela``, o ``py-spy dump`` do serviço mostrou
um fio do executor do ``asyncio`` preso em ``Captura.passo`` → ``FonteDoPortal._pedir``, à espera
da resposta do portal de captura, que não vinha. A parada da porta cancelava a tarefa e deixava o
fio; o ``asyncio.run`` esperava o executor, e o processo só saía no fim da espera do portal ou no
SIGKILL do systemd, 45 s depois. Aqui o portal é de mentira, num ``dbus-daemon`` particular: ele
aceita o ``CreateSession`` e nunca responde, como o de verdade naquele dia.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import tela_do_jogo as tj

RAIZ = Path(__file__).resolve().parents[2]

_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={soquete}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _ha_pipewiresrc() -> bool:
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
    except (ImportError, ValueError):
        return False
    Gst.init(None)
    return Gst.ElementFactory.find("pipewiresrc") is not None


pytestmark = pytest.mark.skipif(
    shutil.which("dbus-daemon") is None or not _ha_pipewiresrc(),
    reason="sem dbus-daemon ou sem o pipewiresrc, a fonte do portal nem chega a pedir",
)


class PortalMudo:
    """O portal que aceita o ``CreateSession`` e nunca manda o ``Response``."""

    def __init__(self, endereco: str) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        self.pedido = threading.Event()
        self._parar = threading.Event()
        self._conexao = open_dbus_connection(bus=endereco)
        self._conexao.send_and_get_reply(message_bus.RequestName(tj._PORTAL, 4), timeout=5)
        self._fio = threading.Thread(target=self._atender, name="portal-mudo", daemon=True)
        self._fio.start()

    def _atender(self) -> None:
        from jeepney import MessageType, new_method_return

        while not self._parar.is_set():
            try:
                mensagem = self._conexao.receive(timeout=0.2)
            except TimeoutError:
                continue
            except OSError:
                return
            cabecalho = mensagem.header
            if cabecalho.message_type != MessageType.method_call:
                continue
            caminho = f"{tj._CAMINHO_DO_PORTAL}/request/mudo/{cabecalho.serial}"
            self._conexao.send(new_method_return(mensagem, "o", (caminho,)))
            self.pedido.set()

    def fechar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2)
        self._conexao.close()


@pytest.fixture
def barramento(tmp_path: Path) -> Iterator[str]:
    soquete = tmp_path / "barramento"
    config = tmp_path / "barramento.conf"
    config.write_text(_CONFIG.format(soquete=soquete), encoding="utf-8")
    processo = subprocess.Popen(
        ["dbus-daemon", "--config-file", str(config), "--print-address", "--nofork",
         "--nopidfile"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    assert processo.stdout is not None
    endereco = processo.stdout.readline().strip()
    try:
        assert endereco, "o dbus-daemon particular não disse o endereço"
        yield endereco
    finally:
        processo.terminate()
        processo.wait(timeout=5)


@pytest.fixture
def portal(barramento: str) -> Iterator[PortalMudo]:
    mudo = PortalMudo(barramento)
    try:
        yield mudo
    finally:
        mudo.fechar()


def test_a_parada_solta_o_passo_preso_na_espera_do_portal(
    barramento: str, portal: PortalMudo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", barramento)
    publicados: list[dict[str, object]] = []
    captura = tj.Captura(tj.FonteDoPortal(tmp_path / "ficha"), tj.TelaDoJogo(),
                         publicar=publicados.append, assinantes=lambda: 1, nascidas=lambda: 1)
    fio = threading.Thread(target=captura.passo, name="passo-da-captura", daemon=True)
    fio.start()
    assert portal.pedido.wait(5), "o pedido não chegou ao portal"
    time.sleep(0.2)
    assert fio.is_alive(), "o passo devia estar na espera do portal"
    inicio = time.monotonic()
    captura.parar()
    fio.join(timeout=2)
    assert not fio.is_alive(), "o passo continuou preso na espera do portal depois da parada"
    assert time.monotonic() - inicio < 2
    assert not captura.aberta
    assert publicados == []
    captura.passo()
    assert not captura.aberta


_PROCESSO = textwrap.dedent('''
    import asyncio, os, sys, threading
    from pathlib import Path

    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
    from hefesto_dualsense4unix.mods.porta import Porta
    from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

    pasta = Path(sys.argv[1])
    tela = pasta / "drm" / "card0-HDMI-A-1"
    tela.mkdir(parents=True)
    (tela / "status").write_text(sys.argv[2], encoding="utf-8")
    tj.RAIZ_DRM = pasta / "drm"


    async def escritor(_m, _p):
        return {"status": "ok"}


    async def corrida():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        porta = Porta(pasta / "mods.sock", bus, escritor=escritor,
                      o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1,
                      fonte_da_tela=lambda: tj.FonteDoPortal(pasta / "ficha"))
        await porta.iniciar()
        porta.registrar("ficha-t", "imersao", os.getpid(), ["ler:jogo.tela"])
        cliente = _Cliente(pasta / "mods.sock")
        await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-t"})
        await asyncio.to_thread(cliente.pedir, "eventos.assinar", {"topicos": ["jogo.tela"]})
        print("assinou", flush=True)
        await asyncio.to_thread(sys.stdin.readline)
        cliente.fechar()
        await porta.parar()


    asyncio.run(corrida())
    vivos = sorted(t.name for t in threading.enumerate() if t is not threading.main_thread())
    print("vivos=" + ",".join(vivos), flush=True)
''')


def test_o_processo_da_porta_sai_logo_depois_da_parada_com_o_portal_mudo(
    barramento: str, portal: PortalMudo, tmp_path: Path
) -> None:
    roteiro = tmp_path / "porta_viva.py"
    roteiro.write_text(_PROCESSO, encoding="utf-8")
    lar = tmp_path / "lar"
    ambiente = {
        **os.environ,
        "DBUS_SESSION_BUS_ADDRESS": barramento,
        "PYTHONPATH": os.pathsep.join((str(RAIZ / "src"), str(RAIZ))),
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / ".config"),
        "XDG_DATA_HOME": str(lar / ".local" / "share"),
        "XDG_STATE_HOME": str(lar / ".local" / "state"),
        "XDG_CACHE_HOME": str(lar / ".cache"),
        "XDG_RUNTIME_DIR": str(tmp_path),
        "HEFESTO_DUALSENSE4UNIX_FAKE": "1",
    }
    processo = subprocess.Popen(
        [sys.executable, str(roteiro), str(tmp_path), "connected"], cwd=RAIZ, env=ambiente,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert processo.stdin is not None and processo.stdout is not None
    try:
        assert processo.stdout.readline().strip() == "assinou"
        assert portal.pedido.wait(5), "a captura não pediu a sessão ao portal"
        time.sleep(0.3)
        inicio = time.monotonic()
        processo.stdin.write("pare\n")
        processo.stdin.flush()
        saida, erro = processo.communicate(timeout=10)
        decorrido = time.monotonic() - inicio
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait()
    assert processo.returncode == 0, erro
    assert decorrido < 2, f"o processo levou {decorrido:.1f} s para sair depois da parada"
    assert saida.strip().splitlines()[-1] == "vivos=", saida
