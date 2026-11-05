"""O portal da tela responde ao pedido da captura (04/11/2026).

A medida, no barramento da sessão: o ``xdg-desktop-portal`` vivo não exporta
``org.freedesktop.portal.ScreenCast`` (o ``cosmic.portal`` não casou com o ambiente dele), e o
``CreateSession`` volta na hora como erro ``UnknownMethod``. A fonte lia esse erro como resposta
boa e esperava ``PRAZO_DA_ESCOLHA_S`` por um ``Response`` que nunca sai. Aqui o portal é de
mentira, num ``dbus-daemon`` particular: um responde como o daquele dia, o outro abre a sessão.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import tela_do_jogo as tj

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

_SEM_INTERFACE = "org.freedesktop.DBus.Error.UnknownMethod"


def _ha_pipewiresrc() -> bool:
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
    except (ImportError, ValueError):
        return False
    Gst.init(None)
    return Gst.ElementFactory.find("pipewiresrc") is not None


_SEM_DBUS = shutil.which("dbus-daemon") is None
_POR_QUE = "sem dbus-daemon não há barramento particular para o portal de mentira"


class PortalDeMentira:
    """Atende o ``org.freedesktop.portal.Desktop`` num fio; ``com_captura`` diz se a interface
    ``ScreenCast`` existe. Sem a interface, todo pedido volta como o erro do portal medido."""

    def __init__(self, endereco: str, *, com_captura: bool) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        self.com_captura = com_captura
        self.pedidos: list[str] = []
        self.pedido = threading.Event()
        self._parar = threading.Event()
        self._conexao = open_dbus_connection(bus=endereco)
        self._conexao.send_and_get_reply(message_bus.RequestName(tj._PORTAL, 4), timeout=5)
        self._fio = threading.Thread(target=self._atender, name="portal-de-mentira", daemon=True)
        self._fio.start()

    def _atender(self) -> None:
        from jeepney import MessageType

        while not self._parar.is_set():
            try:
                mensagem = self._conexao.receive(timeout=0.2)
            except TimeoutError:
                continue
            except OSError:
                return
            if mensagem.header.message_type == MessageType.method_call:
                self._responder(mensagem)

    def _responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields, new_error, new_method_return, new_signal
        from jeepney.wrappers import DBusAddress

        campos = mensagem.header.fields
        interface = campos.get(HeaderFields.interface, "")
        metodo = campos.get(HeaderFields.member, "")
        self.pedidos.append(f"{interface}.{metodo}")
        self.pedido.set()
        if not self.com_captura or interface != tj._SCREENCAST or metodo != "CreateSession":
            self._conexao.send(new_error(
                mensagem, _SEM_INTERFACE, "s",
                (f"Nenhuma interface “{interface}” no objeto no caminho {tj._CAMINHO_DO_PORTAL}",)))
            return
        opcoes = mensagem.body[-1]
        remetente = campos[HeaderFields.sender]
        caminho = tj._caminho_do_pedido(remetente, opcoes["handle_token"][1])
        sessao = f"{tj._CAMINHO_DO_PORTAL}/session/mentira/{opcoes['session_handle_token'][1]}"
        self._conexao.send(new_method_return(mensagem, "o", (caminho,)))
        pedido = DBusAddress(caminho, interface=tj._PEDIDO)
        sinal = new_signal(pedido, "Response", "ua{sv}", (0, {"session_handle": ("o", sessao)}))
        sinal.header.fields[HeaderFields.destination] = remetente
        self._conexao.send(sinal)

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
def sem_captura(barramento: str) -> Iterator[PortalDeMentira]:
    portal = PortalDeMentira(barramento, com_captura=False)
    try:
        yield portal
    finally:
        portal.fechar()


@pytest.fixture
def com_captura(barramento: str) -> Iterator[PortalDeMentira]:
    portal = PortalDeMentira(barramento, com_captura=True)
    try:
        yield portal
    finally:
        portal.fechar()


@pytest.mark.skipif(_SEM_DBUS or not _ha_pipewiresrc(),
                    reason="sem dbus-daemon ou sem o pipewiresrc, a fonte nem chega a pedir")
def test_o_abrir_volta_logo_quando_o_portal_nao_tem_a_captura(
    barramento: str, sem_captura: PortalDeMentira, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", barramento)
    fonte = tj.FonteDoPortal(tmp_path / "ficha")
    erros: list[BaseException] = []

    def abrir() -> None:
        try:
            fonte.abrir()
        except BaseException as exc:
            erros.append(exc)

    fio = threading.Thread(target=abrir, name="abrir-a-fonte", daemon=True)
    inicio = time.monotonic()
    fio.start()
    fio.join(timeout=3)
    try:
        assert not fio.is_alive(), "o abrir ficou esperando o Response de um pedido recusado"
    finally:
        fonte.interromper()
        fio.join(timeout=2)
    assert time.monotonic() - inicio < 3
    assert f"{tj._SCREENCAST}.CreateSession" in sem_captura.pedidos
    assert len(erros) == 1 and isinstance(erros[0], RuntimeError), erros
    assert "CreateSession" in str(erros[0])
    assert fonte._conexao is None


@pytest.mark.skipif(_SEM_DBUS or not _ha_pipewiresrc(),
                    reason="sem dbus-daemon ou sem o pipewiresrc, a fonte nem chega a pedir")
def test_o_passo_publica_ausente_logo_e_tenta_de_novo_depois_da_espera(
    barramento: str, sem_captura: PortalDeMentira, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", barramento)
    agora = [100.0]
    publicados: list[dict[str, object]] = []
    fonte = tj.FonteDoPortal(tmp_path / "ficha")
    captura = tj.Captura(fonte, tj.TelaDoJogo(relogio=lambda: agora[0]),
                         publicar=publicados.append, assinantes=lambda: 1,
                         relogio=lambda: agora[0])
    fio = threading.Thread(target=captura.passo, name="passo-da-captura", daemon=True)
    fio.start()
    fio.join(timeout=3)
    try:
        assert not fio.is_alive(), "o passo ficou preso num pedido que o portal já recusou"
    finally:
        captura.parar()
        fio.join(timeout=2)
    assert not captura.aberta
    assert len(publicados) == 1
    assert all(publicados[0][s] is None for s in tj.SINAIS)
    assert captura._proxima == pytest.approx(102.0)


@pytest.mark.skipif(_SEM_DBUS, reason=_POR_QUE)
def test_o_pedido_recebe_a_sessao_do_portal_que_responde(
    barramento: str, com_captura: PortalDeMentira, tmp_path: Path
) -> None:
    from jeepney.io.blocking import open_dbus_connection

    fonte = tj.FonteDoPortal(tmp_path / "ficha")
    fonte._conexao = open_dbus_connection(bus=barramento)
    try:
        criada = fonte._pedir("CreateSession", "a{sv}", (),
                              {"session_handle_token": ("s", "sessao1")})
    finally:
        fonte.fechar()
    assert criada["session_handle"].endswith("/sessao1")


@pytest.mark.skipif(_SEM_DBUS, reason=_POR_QUE)
def test_o_pedido_recusado_vira_runtimeerror_sem_esperar(
    barramento: str, sem_captura: PortalDeMentira, tmp_path: Path
) -> None:
    from jeepney.io.blocking import open_dbus_connection

    fonte = tj.FonteDoPortal(tmp_path / "ficha")
    fonte._conexao = open_dbus_connection(bus=barramento)
    erros: list[BaseException] = []

    def pedir() -> None:
        try:
            fonte._pedir("SelectSources", "oa{sv}", ("/x",), {})
        except BaseException as exc:
            erros.append(exc)

    fio = threading.Thread(target=pedir, name="pedir", daemon=True)
    fio.start()
    fio.join(timeout=3)
    try:
        assert not fio.is_alive(), "o pedido recusado ficou esperando o Response"
    finally:
        fonte.interromper()
        fio.join(timeout=2)
        fonte.fechar()
    assert len(erros) == 1 and isinstance(erros[0], RuntimeError), erros
    assert "SelectSources" in str(erros[0])
