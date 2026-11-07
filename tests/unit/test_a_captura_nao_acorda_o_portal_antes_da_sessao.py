"""A captura não acorda o portal antes da sessão (05/11/2026).

Medido no diário do boot de 05/11: o daemon sobe antes da sessão gráfica, e o ``CreateSession``
da captura é o primeiro pedido ao ``org.freedesktop.portal.Desktop``, que o ativa sem
``XDG_CURRENT_DESKTOP``; o portal vive a sessão inteira sem ``ScreenCast`` para todo programa.
E, com o portal de pé, o prazo da escolha esgotado e a ficha guardada recusada reabriam a janela
de escolha a cada volta da ``espera``. Aqui o barramento é um ``dbus-daemon`` particular, com um
portal ATIVÁVEL que conta as ativações, um ``systemd1`` de mentira e um relógio na mão do teste.

MORDIDA: arrancar a guarda do ``abrir`` (o ``sessao_ainda_nao_subiu``), o ``no_auto_start`` da
leitura do gerente, a troca do prazo esgotado por ``EscolhaCanceladaError`` no ``_pedir`` ou o
``_esquecer`` da ficha recusada, e a régua reprova.
"""
from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.integrations import barramento_do_sistema
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from tests.unit.test_o_portal_da_tela_responde_ao_pedido_da_captura import (
    _SEM_DBUS,
    _SEM_INTERFACE,
    _ha_pipewiresrc,
)

_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={soquete}</listen>
  <auth>EXTERNAL</auth>
  <servicedir>{servicos}</servicedir>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""

_ATIVADOR = """#!/bin/sh
echo ativado >> "{contagem}"
exit 1
"""

_SERVICO = "[D-BUS Service]\nName={nome}\nExec=/bin/sh {ativador}\n"

_CRIA = f"{tj._SCREENCAST}.CreateSession"
_ESCOLHE = f"{tj._SCREENCAST}.SelectSources"
_COMECA = f"{tj._SCREENCAST}.Start"
_FECHA = "org.freedesktop.portal.Session.Close"
_PASSO_S = 1.0 / tj.HZ_DA_TELA
_SYSTEMD = "org.freedesktop.systemd1"
_GERENTE = "org.freedesktop.systemd1.Manager"
_MOTIVO = "a sessão gráfica ainda não subiu"

_PRECISA_DO_PORTAL = pytest.mark.skipif(
    _SEM_DBUS or not _ha_pipewiresrc(),
    reason="sem dbus-daemon ou sem o pipewiresrc, a fonte nem chega a pedir")


class Barramento:
    """O ``dbus-daemon`` particular com o portal ativável: cada ativação vira uma linha em
    ``contagem``, e o ativador sai sem tomar o nome, como o portal que não sobe. O ``systemd1``
    também é ativável, como no barramento da sessão (o ``org.freedesktop.systemd1.service`` do
    systemd), e as ativações dele vão para ``contagem_do_gerente``."""

    def __init__(self, pasta: Path) -> None:
        servicos = pasta / "ativaveis"
        servicos.mkdir()
        self.contagem = pasta / "ativacoes"
        self.contagem_do_gerente = pasta / "ativacoes-do-gerente"
        for nome, contagem in ((tj._PORTAL, self.contagem),
                               (_SYSTEMD, self.contagem_do_gerente)):
            ativador = pasta / f"ativador-{nome}.sh"
            ativador.write_text(_ATIVADOR.format(contagem=contagem), encoding="utf-8")
            (servicos / f"{nome}.service").write_text(
                _SERVICO.format(nome=nome, ativador=ativador), encoding="utf-8")
        config = pasta / "barramento.conf"
        config.write_text(_CONFIG.format(soquete=pasta / "barramento", servicos=servicos),
                          encoding="utf-8")
        self._processo = subprocess.Popen(
            ["dbus-daemon", "--config-file", str(config), "--print-address", "--nofork",
             "--nopidfile"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        assert self._processo.stdout is not None
        self.endereco = self._processo.stdout.readline().strip()
        assert self.endereco, "o dbus-daemon particular não disse o endereço"

    def ativacoes(self) -> int:
        return _linhas(self.contagem)

    def ativacoes_do_gerente(self) -> int:
        return _linhas(self.contagem_do_gerente)

    def fechar(self) -> None:
        self._processo.terminate()
        self._processo.wait(timeout=5)


def _linhas(contagem: Path) -> int:
    if not contagem.exists():
        return 0
    return len(contagem.read_text(encoding="utf-8").splitlines())


class Atendente:
    """Um dono de nome no barramento particular, num fio; ``responder`` atende cada chamada."""

    def __init__(self, endereco: str, nome: str) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        self.pedidos: list[str] = []
        self._parar = threading.Event()
        self._conexao = open_dbus_connection(bus=endereco)
        self._conexao.send_and_get_reply(message_bus.RequestName(nome, 4), timeout=5)
        self._fio = threading.Thread(target=self._atender, name=f"atende-{nome}", daemon=True)
        self._fio.start()

    def _atender(self) -> None:
        from jeepney import HeaderFields, MessageType

        while not self._parar.is_set():
            try:
                mensagem = self._conexao.receive(timeout=0.2)
            except TimeoutError:
                continue
            except OSError:
                return
            if mensagem.header.message_type != MessageType.method_call:
                continue
            campos = mensagem.header.fields
            self.pedidos.append(
                f"{campos.get(HeaderFields.interface, '')}.{campos.get(HeaderFields.member, '')}")
            self.responder(mensagem)

    def responder(self, mensagem: Any) -> None:
        raise NotImplementedError

    def fechar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2)
        self._conexao.close()


class GerenteDeMentira(Atendente):
    """O ``org.freedesktop.systemd1`` do usuário: só lê o ``Manager.Environment``."""

    def __init__(self, endereco: str, ambiente: list[str]) -> None:
        self.ambiente = ambiente
        super().__init__(endereco, _SYSTEMD)

    def responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields, new_error, new_method_return

        campos = mensagem.header.fields
        if (campos.get(HeaderFields.member) == "Get"
                and tuple(mensagem.body) == (_GERENTE, "Environment")):
            self._conexao.send(new_method_return(mensagem, "v", (("as", self.ambiente),)))
            return
        self._conexao.send(new_error(mensagem, _SEM_INTERFACE, "s", ("só leitura",)))


class PortalDeTeste(Atendente):
    """O portal de pé: ``respostas`` diz o código do ``Response`` de cada método (``None``: o
    ``Response`` nunca sai, como a janela que ninguém responde); ``erro_em`` volta como erro do
    barramento; ``sem_fluxo`` faz o ``Start`` responder 0 sem fluxo. ``levados`` guarda o que
    cada pedido levou."""

    def __init__(self, endereco: str, *, respostas: dict[str, int | None] | None = None,
                 erro_em: frozenset[str] = frozenset(), sem_fluxo: bool = False) -> None:
        self.respostas = respostas or {}
        self.erro_em = erro_em
        self.sem_fluxo = sem_fluxo
        self.levados: list[tuple[str, dict[str, Any]]] = []
        super().__init__(endereco, tj._PORTAL)

    def responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields, new_error, new_method_return, new_signal
        from jeepney.wrappers import DBusAddress

        campos = mensagem.header.fields
        interface = campos.get(HeaderFields.interface, "")
        metodo = campos.get(HeaderFields.member, "")
        if interface != tj._SCREENCAST or metodo in self.erro_em or metodo not in (
                "CreateSession", "SelectSources", "Start"):
            self._conexao.send(new_error(mensagem, _SEM_INTERFACE, "s", (metodo,)))
            return
        opcoes = mensagem.body[-1]
        self.levados.append((metodo, dict(opcoes)))
        remetente = campos[HeaderFields.sender]
        caminho = tj._caminho_do_pedido(remetente, opcoes["handle_token"][1])
        self._conexao.send(new_method_return(mensagem, "o", (caminho,)))
        codigo = self.respostas.get(metodo, 0)
        if codigo is None:
            return
        resultados: dict[str, tuple[str, Any]] = {}
        if metodo == "CreateSession":
            token = opcoes["session_handle_token"][1]
            resultados["session_handle"] = ("o", f"{tj._CAMINHO_DO_PORTAL}/session/t/{token}")
        elif metodo == "Start" and not self.sem_fluxo:
            resultados["streams"] = ("a(ua{sv})", [(7, {})])
            resultados["restore_token"] = ("s", "ficha-nova")
        sinal = new_signal(DBusAddress(caminho, interface=tj._PEDIDO), "Response", "ua{sv}",
                           (codigo, resultados))
        sinal.header.fields[HeaderFields.destination] = remetente
        self._conexao.send(sinal)


class Cena:
    """A captura com o relógio e o número de assinantes na mão do teste."""

    def __init__(self, fonte: tj.FonteDaTela) -> None:
        self.agora = [100.0]
        self.assinantes = [1]
        self.publicados: list[dict[str, Any]] = []
        self.captura = tj.Captura(fonte, tj.TelaDoJogo(relogio=lambda: self.agora[0]),
                                  publicar=self.publicados.append,
                                  assinantes=lambda: self.assinantes[0],
                                  relogio=lambda: self.agora[0])

    def correr(self, segundos: float) -> None:
        for _ in range(round(segundos / _PASSO_S)):
            self.captura.passo()
            self.agora[0] += _PASSO_S


@pytest.fixture
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Barramento]:
    vivo = Barramento(tmp_path)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", vivo.endereco)
    try:
        yield vivo
    finally:
        vivo.fechar()


@pytest.fixture
def gerente_sem_desktop(barramento: Barramento) -> Iterator[GerenteDeMentira]:
    gerente = GerenteDeMentira(barramento.endereco, ["HOME=/lar", "PATH=/usr/bin"])
    try:
        yield gerente
    finally:
        gerente.fechar()


@pytest.fixture
def gerente_com_desktop(barramento: Barramento) -> Iterator[GerenteDeMentira]:
    gerente = GerenteDeMentira(barramento.endereco,
                               ["HOME=/lar", "XDG_CURRENT_DESKTOP=COSMIC", "WAYLAND_DISPLAY=w-1"])
    try:
        yield gerente
    finally:
        gerente.fechar()


def _abrir(fonte: tj.FonteDoPortal) -> BaseException | None:
    try:
        fonte.abrir()
    except Exception as erro:
        return erro
    return None


@_PRECISA_DO_PORTAL
def test_sem_o_desktop_no_gerente_o_abrir_recusa_sem_acordar_o_portal(
    barramento: Barramento, gerente_sem_desktop: GerenteDeMentira, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC")
    fonte = tj.FonteDoPortal(tmp_path / "ficha")
    erro = _abrir(fonte)
    assert isinstance(erro, RuntimeError), erro
    assert _MOTIVO in str(erro)
    assert barramento.ativacoes() == 0
    assert fonte._conexao is None
    assert gerente_sem_desktop.pedidos == ["org.freedesktop.DBus.Properties.Get"]


@_PRECISA_DO_PORTAL
def test_com_o_desktop_no_gerente_o_abrir_chega_ao_create_session(
    barramento: Barramento, gerente_com_desktop: GerenteDeMentira, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    erro = _abrir(tj.FonteDoPortal(tmp_path / "ficha"))
    assert isinstance(erro, RuntimeError), erro
    assert "CreateSession" in str(erro)
    assert _MOTIVO not in str(erro)
    assert barramento.ativacoes() == 1


@_PRECISA_DO_PORTAL
@pytest.mark.parametrize("desktop", [None, "", "COSMIC"])
def test_sem_o_gerente_vale_o_ambiente_do_proprio_processo(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    desktop: str | None
) -> None:
    if desktop is None:
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    else:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    erro = _abrir(tj.FonteDoPortal(tmp_path / "ficha"))
    assert isinstance(erro, RuntimeError), erro
    if desktop:
        assert "CreateSession" in str(erro)
        assert barramento.ativacoes() == 1
    else:
        assert _MOTIVO in str(erro)
        assert barramento.ativacoes() == 0
    assert barramento.ativacoes_do_gerente() == 0


@_PRECISA_DO_PORTAL
def test_a_captura_espera_a_sessao_e_abre_quando_a_sessao_sobe(
    barramento: Barramento, gerente_sem_desktop: GerenteDeMentira, tmp_path: Path
) -> None:
    cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
    with structlog.testing.capture_logs() as diario:
        cena.correr(10.0)
    assert barramento.ativacoes() == 0
    assert len(cena.publicados) == 1
    assert all(cena.publicados[0][s] is None for s in tj.SINAIS)
    ditos = [r for r in diario if r["event"] == "tela_do_jogo_ausente"]
    assert len(ditos) == 1 and _MOTIVO in ditos[0]["motivo"], diario
    gerente_sem_desktop.ambiente.append("XDG_CURRENT_DESKTOP=COSMIC")
    cena.correr(3.0)
    assert barramento.ativacoes() >= 1
    portal = PortalDeTeste(barramento.endereco)
    try:
        cena.correr(3.0)
    finally:
        portal.fechar()
    assert portal.pedidos.count(_CRIA) >= 1, portal.pedidos
    assert portal.pedidos.count(_COMECA) >= 1, portal.pedidos
    assert (tmp_path / "ficha").read_text(encoding="utf-8") == "ficha-nova"


@_PRECISA_DO_PORTAL
def test_o_portal_sem_a_captura_diz_o_conserto_e_ninguem_o_reinicia(
    barramento: Barramento, gerente_sem_desktop: GerenteDeMentira, tmp_path: Path
) -> None:
    portal = PortalDeTeste(barramento.endereco, erro_em=frozenset({"CreateSession"}))
    try:
        erro = _abrir(tj.FonteDoPortal(tmp_path / "ficha"))
    finally:
        portal.fechar()
    assert isinstance(erro, RuntimeError), erro
    assert "CreateSession" in str(erro)
    assert "systemctl --user restart xdg-desktop-portal" in str(erro)
    assert gerente_sem_desktop.pedidos == []
    assert barramento.ativacoes() == 0


@_PRECISA_DO_PORTAL
def test_o_prazo_esgotado_nao_reabre_a_escolha_em_laco(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    portal = PortalDeTeste(barramento.endereco, respostas={"Start": None})
    try:
        cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
        cena.correr(10.0)
        cena.agora[0] += tj.PRAZO_DA_ESCOLHA_S + 125.0
        cena.correr(10.0)
        assert portal.pedidos.count(_ESCOLHE) == 1, portal.pedidos
        assert portal.pedidos.count(_FECHA) == 1, portal.pedidos
        assert len(cena.publicados) == 1
        assert not cena.captura.aberta
        cena.assinantes[0] = 2
        cena.correr(4.0)
        assert portal.pedidos.count(_ESCOLHE) == 2, portal.pedidos
    finally:
        portal.fechar()


@_PRECISA_DO_PORTAL
@pytest.mark.parametrize("recusa", ["dois", "sem_fluxo", "erro", "prazo", "cancelada"])
def test_a_ficha_recusada_se_apaga_e_nao_vira_janela_pela_espera(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recusa: str
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-velha", encoding="utf-8")
    jeitos: dict[str, dict[str, Any]] = {
        "dois": {"respostas": {"Start": 2}},
        "sem_fluxo": {"sem_fluxo": True},
        "erro": {"erro_em": frozenset({"Start"})},
        "prazo": {"respostas": {"Start": None}},
        "cancelada": {"respostas": {"Start": 1}},
    }
    portal = PortalDeTeste(barramento.endereco, **jeitos[recusa])
    try:
        cena = Cena(tj.FonteDoPortal(ficha))
        cena.correr(10.0)
        escolhas = [o for m, o in portal.levados if m == "SelectSources"]
        assert len(escolhas) == 1, portal.pedidos
        assert escolhas[0]["restore_token"] == ("s", "ficha-velha")
        assert not ficha.exists()
        assert len(cena.publicados) == 1
        cena.assinantes[0] = 2
        cena.correr(1.0)
        escolhas = [o for m, o in portal.levados if m == "SelectSources"]
        assert len(escolhas) == 2, portal.pedidos
        assert "restore_token" not in escolhas[1]
    finally:
        portal.fechar()


@_PRECISA_DO_PORTAL
def test_a_ficha_recusada_sem_ficha_guardada_segue_como_queda(
    barramento: Barramento, tmp_path: Path
) -> None:
    portal = PortalDeTeste(barramento.endereco, sem_fluxo=True)
    try:
        cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
        cena.correr(10.0)
    finally:
        portal.fechar()
    assert portal.pedidos.count(_ESCOLHE) >= 4, portal.pedidos
    assert len(cena.publicados) == 1


@_PRECISA_DO_PORTAL
def test_a_parada_no_meio_da_escolha_nao_apaga_a_ficha(
    barramento: Barramento, tmp_path: Path
) -> None:
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    portal = PortalDeTeste(barramento.endereco, respostas={"Start": None})
    fonte = tj.FonteDoPortal(ficha)
    erros: list[BaseException | None] = []
    fio = threading.Thread(target=lambda: erros.append(_abrir(fonte)), name="abrir",
                           daemon=True)
    try:
        fio.start()
        prazo = time.monotonic() + 5
        while _COMECA not in portal.pedidos and time.monotonic() < prazo:
            time.sleep(0.02)
        assert _COMECA in portal.pedidos, portal.pedidos
        fonte.interromper()
        fio.join(timeout=3)
        assert not fio.is_alive()
    finally:
        portal.fechar()
    assert erros and erros[0] is not None
    assert not isinstance(erros[0], tj.EscolhaCanceladaError), erros
    assert ficha.read_text(encoding="utf-8") == "ficha-boa"


def test_o_ambiente_do_gerente_casa_so_o_desktop_com_valor() -> None:
    assert barramento_do_sistema.tem_o_desktop(["XDG_CURRENT_DESKTOP=COSMIC"])
    assert not barramento_do_sistema.tem_o_desktop(["XDG_CURRENT_DESKTOP="])
    assert not barramento_do_sistema.tem_o_desktop(["XDG_CURRENT_DESKTOPX=COSMIC", "HOME=/lar"])
    assert not barramento_do_sistema.tem_o_desktop([])
