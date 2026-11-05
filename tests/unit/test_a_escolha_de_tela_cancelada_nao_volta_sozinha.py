"""A escolha de tela cancelada não volta sozinha (05/11/2026).

O ``Response`` com código 1 é a pessoa que cancelou a janela de escolha; a captura guarda a
recusa e só pede de novo quando entra assinante novo de ``jogo.tela`` (ou todos saem e um volta).
O código 2 e o fluxo que para de entregar quadro são queda, e a queda tenta de novo depois da
espera. O portal é de mentira, num ``dbus-daemon`` particular, e o relógio também.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from tests.unit.test_o_portal_da_tela_responde_ao_pedido_da_captura import (  # noqa: F401
    _SEM_DBUS,
    _SEM_INTERFACE,
    _ha_pipewiresrc,
    barramento,
)

_CRIA = f"{tj._SCREENCAST}.CreateSession"
_ESCOLHE = f"{tj._SCREENCAST}.SelectSources"
_PASSO_S = 1.0 / tj.HZ_DA_TELA

_PRECISA_DO_PORTAL = pytest.mark.skipif(
    _SEM_DBUS or not _ha_pipewiresrc(),
    reason="sem dbus-daemon ou sem o pipewiresrc, a fonte nem chega a pedir")


class PortalQueResponde:
    """O ``CreateSession`` abre a sessão; o ``SelectSources`` responde com o código pedido, como a
    janela de escolha do portal: 1 quando a pessoa cancela, 2 quando o pedido acaba de outro
    jeito."""

    def __init__(self, endereco: str, codigo: int) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        self.codigo = codigo
        self.pedidos: list[str] = []
        self._parar = threading.Event()
        self._conexao = open_dbus_connection(bus=endereco)
        self._conexao.send_and_get_reply(message_bus.RequestName(tj._PORTAL, 4), timeout=5)
        self._fio = threading.Thread(target=self._atender, name="portal-que-responde",
                                     daemon=True)
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
        if interface != tj._SCREENCAST or metodo not in ("CreateSession", "SelectSources"):
            self._conexao.send(new_error(mensagem, _SEM_INTERFACE, "s", (metodo,)))
            return
        opcoes = mensagem.body[-1]
        remetente = campos[HeaderFields.sender]
        caminho = tj._caminho_do_pedido(remetente, opcoes["handle_token"][1])
        codigo, resultados = self.codigo, {}
        if metodo == "CreateSession":
            token = opcoes["session_handle_token"][1]
            codigo = 0
            resultados = {"session_handle": ("o", f"{tj._CAMINHO_DO_PORTAL}/session/m/{token}")}
        self._conexao.send(new_method_return(mensagem, "o", (caminho,)))
        sinal = new_signal(DBusAddress(caminho, interface=tj._PEDIDO), "Response", "ua{sv}",
                           (codigo, resultados))
        sinal.header.fields[HeaderFields.destination] = remetente
        self._conexao.send(sinal)

    def fechar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2)
        self._conexao.close()


@pytest.fixture
def cancela(barramento: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[PortalQueResponde]:  # noqa: F811
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", barramento)
    portal = PortalQueResponde(barramento, codigo=1)
    try:
        yield portal
    finally:
        portal.fechar()


@pytest.fixture
def acaba(barramento: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[PortalQueResponde]:  # noqa: F811
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", barramento)
    portal = PortalQueResponde(barramento, codigo=2)
    try:
        yield portal
    finally:
        portal.fechar()


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


@_PRECISA_DO_PORTAL
def test_o_cancelamento_nao_reabre_a_escolha_em_dez_segundos(
    cancela: PortalQueResponde, tmp_path: Path
) -> None:
    cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
    with structlog.testing.capture_logs() as diario:
        cena.correr(10.0)
    assert cancela.pedidos.count(_CRIA) == 1, cancela.pedidos
    assert cancela.pedidos.count(_ESCOLHE) == 1, cancela.pedidos
    assert not cena.captura.aberta
    assert len(cena.publicados) == 1
    assert all(cena.publicados[0][s] is None for s in tj.SINAIS)
    ditos = [r for r in diario if r["event"] == "tela_do_jogo_ausente"]
    assert len(ditos) == 1, diario
    assert not (tmp_path / "ficha").exists()


@_PRECISA_DO_PORTAL
def test_o_assinante_novo_pede_a_escolha_de_novo(
    cancela: PortalQueResponde, tmp_path: Path
) -> None:
    cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
    cena.correr(4.0)
    assert cancela.pedidos.count(_ESCOLHE) == 1
    cena.assinantes[0] = 2
    cena.correr(4.0)
    assert cancela.pedidos.count(_ESCOLHE) == 2, cancela.pedidos
    cena.correr(10.0)
    assert cancela.pedidos.count(_ESCOLHE) == 2, cancela.pedidos


@_PRECISA_DO_PORTAL
def test_quem_sai_nao_reabre_a_escolha_e_quem_volta_reabre(
    cancela: PortalQueResponde, tmp_path: Path
) -> None:
    cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
    cena.assinantes[0] = 2
    cena.correr(4.0)
    cena.assinantes[0] = 1
    cena.correr(4.0)
    assert cancela.pedidos.count(_ESCOLHE) == 1, cancela.pedidos
    cena.assinantes[0] = 0
    cena.correr(1.0)
    cena.assinantes[0] = 1
    cena.correr(4.0)
    assert cancela.pedidos.count(_ESCOLHE) == 2, cancela.pedidos


@_PRECISA_DO_PORTAL
def test_o_pedido_que_acaba_de_outro_jeito_tenta_de_novo(
    acaba: PortalQueResponde, tmp_path: Path
) -> None:
    cena = Cena(tj.FonteDoPortal(tmp_path / "ficha"))
    cena.correr(10.0)
    assert acaba.pedidos.count(_ESCOLHE) >= 4, acaba.pedidos
    assert len(cena.publicados) == 1


class FonteQueCai:
    """Abre e para de entregar quadro: o fluxo que fecha."""

    def __init__(self) -> None:
        self.aberturas = 0

    def abrir(self) -> bool:
        self.aberturas += 1
        return True

    def quadro(self) -> tj.Quadro | None:
        return None

    def fechar(self) -> None:
        return None

    def interromper(self) -> None:
        return None


def test_o_fluxo_que_fecha_tenta_de_novo() -> None:
    fonte = FonteQueCai()
    cena = Cena(fonte)
    cena.correr(10.0)
    assert fonte.aberturas >= 4
