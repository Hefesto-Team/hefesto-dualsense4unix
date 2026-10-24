"""O-PAD-QUE-NASCE-ANTES-DO-BROKER-ACEITAR-FICA-SEM-PORTA-01 (24/10/2026).

Medido no diário dos boots de 24/10: o daemon de usuário sobe antes do login,
o broker de root recusa o uid (``nao_e_quem_esta_na_frente``), e o pad grava
``pad_usb_indisponivel_fica_o_uhid motivo=broker_fora_do_ar`` às 02:45:23 e às
14:36:58. Nada tentava de novo: o pad passava a sessão no uhid, sem a porta
própria, até o daemon reiniciar.

O pedido ao broker é o de VERDADE (``uhid_gamepad._pedir_ao_broker`` com o
``HidrawBrokerClient`` de verdade) contra um socket de mentira que faz o que o
broker faz antes do login: não existe, aceita e fecha (o peer recusado), ou
responde ``sem_sessao_ativa``. Aberta a sessão, o gadget vem da bancada do
gadget, o mesmo dublê das outras réguas do pad em USB.
"""

from __future__ import annotations

import contextlib
import os
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import o_que_o_jogo_ve as oqv
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations.hidraw_broker_client import SOCKET_PATH_ENV
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import (
    INTERFACE_DO_GADGET,
    BancadaDoGadget,
    _EspiaoDoDiario,
)

#: P1 e P3 no cabo, P2 e P4 no rádio: a identidade é do plástico, nunca do transporte.
MESA_MISTA = {
    1: ("aa:bb:cc:00:00:11", "usb"),
    2: ("aa:bb:cc:00:00:22", "bt"),
    3: ("aa:bb:cc:00:00:33", "usb"),
    4: ("aa:bb:cc:00:00:44", "bt"),
}
RECUSAS = ("broker_ausente", "peer_recusado", "sem_sessao_ativa")
#: o motivo que o pad anota em cada recusa: o socket que não existe e o peer
#: recusado não respondem, e o cliente lê os dois como broker fora do ar.
MOTIVO_DA_RECUSA = {"broker_ausente": "broker_fora_do_ar", "peer_recusado": "broker_fora_do_ar",
                    "sem_sessao_ativa": "sem_sessao_ativa"}


class BrokerAntesDoLogin:
    """O socket do broker antes de haver sessão na frente.

    ``broker_ausente``: o socket não existe. ``peer_recusado``: aceita e fecha
    (o ``register_client`` com ``nao_e_quem_esta_na_frente``). ``sem_sessao_ativa``:
    aceita, lê o pedido e recusa com o erro do ``_cmd_pad_usb_montar``.
    """

    def __init__(self, caminho: Path, modo: str) -> None:
        self.caminho = caminho
        self.modo = modo
        self.conexoes = 0
        self._pare = threading.Event()
        self._sock: socket.socket | None = None
        self._fio: threading.Thread | None = None
        if modo == "broker_ausente":
            return
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(8)
        self._sock.settimeout(0.05)
        self._fio = threading.Thread(target=self._atender, daemon=True)
        self._fio.start()

    def _atender(self) -> None:
        assert self._sock is not None
        while not self._pare.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            self.conexoes += 1
            with conn:
                if self.modo == "sem_sessao_ativa":
                    conn.settimeout(2.0)
                    with contextlib.suppress(OSError):
                        conn.recv(65536)
                        conn.sendall(b'{"ok": false, "cmd": "pad_usb_montar", '
                                     b'"error": "sem_sessao_ativa"}\n')

    def fechar(self) -> None:
        self._pare.set()
        if self._fio is not None:
            self._fio.join(timeout=2.0)
        if self._sock is not None:
            self._sock.close()


class Mesa:
    """A bancada do gadget com o broker de verdade recusando até a sessão abrir."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, modo: str) -> None:
        self.b = BancadaDoGadget(monkeypatch, tmp_path)
        self.ug = self.b.ug
        self.relogio = [100.0]
        self.sessao_aberta = False
        self.pedidos_ao_broker = 0
        #: ``{serial: (hidraw, interface)}``: quem enumerou pelo vhci.
        self.enumerados: dict[str, tuple[str, str]] = {}
        self.broker = BrokerAntesDoLogin(tmp_path / "broker.sock", modo)
        monkeypatch.setenv(SOCKET_PATH_ENV, str(self.broker.caminho))
        monkeypatch.setattr(self.ug, "HIDRAW_DO_GADGET", self.enumerados.get)
        monkeypatch.setattr(self.ug, "QUIRK_DO_PAR", lambda _par: False)
        monkeypatch.setattr(self.ug, "_RECUSAS_DO_BROKER", {}, raising=False)
        # o cliente recusado guarda o socket da mesa em que nasceu: sem esta
        # troca, a mesa seguinte do mesmo serial pede ao socket da anterior.
        monkeypatch.setattr(self.ug, "_CLIENTES_RECUSADOS", {}, raising=False)
        monkeypatch.setattr(pad_usb, "_SEM_PORTA", {})
        do_gadget = self.ug.PEDIR_O_PAD_USB
        de_verdade = self.ug._pedir_ao_broker

        def pedir(serial: str, descritor: bytes, identidade: str, par: tuple[int, int]) -> Any:
            if self.sessao_aberta:
                return do_gadget(serial, descritor, identidade, par)
            self.pedidos_ao_broker += 1
            return de_verdade(serial, descritor, identidade, par)

        monkeypatch.setattr(self.ug, "PEDIR_O_PAD_USB", pedir)
        self.espiao = _EspiaoDoDiario(self.ug.logger)
        monkeypatch.setattr(self.ug, "logger", self.espiao)

    def pad(self, jogador: int) -> Any:
        identidade, _transporte = MESA_MISTA[jogador]
        return self.b.pad(player=jogador, identity=identidade,
                          time_fn=lambda: self.relogio[0])

    def serial(self, pad: Any) -> str:
        return str(pad_usb.serial_do_pad(pad.mac, pad.player))

    def passar(self, segundos: float, pads: list[Any]) -> None:
        self.relogio[0] += segundos
        for pad in pads:
            pad.pump_ff()

    def eventos(self, nome: str) -> int:
        return sum(1 for _nivel, evento in self.espiao.eventos if evento == nome)


@pytest.fixture(params=RECUSAS)
def mesa(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
         tmp_path: Path) -> Iterator[Mesa]:
    m = Mesa(monkeypatch, tmp_path, request.param)
    try:
        yield m
    finally:
        m.broker.fechar()


@pytest.mark.parametrize("jogadores", [(1, 2), (1, 2, 3, 4), (1,), (2, 4), (1, 3)],
                         ids=["p1-usb+p2-bt", "quatro-mistos", "um-so", "todos-bt", "todos-usb"])
class TestARecusaDoBrokerTentaDeNovo:
    def test_sem_jogo_cada_pad_acaba_no_gadget_quando_a_sessao_abre(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        # D-2410-O-PAD-RECUSADO-PELA-SESSAO-PEDE-DE-NOVO
        """Mordida: tire o ``_gadget_outra_vez = True`` do ramo da recusa, e o pad fica no uhid."""
        pads = [mesa.pad(j) for j in jogadores]
        try:
            for pad in pads:
                assert pad.start() and pad._gadget is None and pad.is_active()
            assert mesa.pedidos_ao_broker == len(pads)
            assert {pad_usb.porque_sem_porta(pad.identity) for pad in pads} == {
                MOTIVO_DA_RECUSA[mesa.broker.modo]
            }, "o pedido não chegou ao broker desta mesa"
            mesa.passar(mesa.ug._GADGET_VARRE_S + 0.5, pads)
            assert mesa.pedidos_ao_broker == 2 * len(pads), "a recusa não pediu de novo"
            assert all(pad._gadget is None for pad in pads), "a recusa montou um gadget"
            assert mesa.eventos("uhid_device_created") == len(pads), (
                "o pad recusado refez o uhid embaixo do jogo"
            )
            assert mesa.eventos("pad_usb_indisponivel_fica_o_uhid") == len(pads), (
                "a recusa repetida virou uma linha por volta"
            )

            mesa.sessao_aberta = True
            mesa.passar(mesa.ug._GADGET_VARRE_S + 0.5, pads)
            assert all(pad._gadget is not None for pad in pads), "a sessão abriu e o pad ficou"
            assert len(mesa.b.pedidos) == len(pads)
            for pad in pads:
                mesa.enumerados[mesa.serial(pad)] = (f"hidraw{pad.player}", INTERFACE_DO_GADGET)
            assert mesa.b.esperar(lambda: all(pad.is_bound for pad in pads))
            mesa.passar(3 * mesa.ug._GADGET_VARRE_S, pads)
            assert len(mesa.b.pedidos) == len(pads), "o pad no gadget pediu outro"
        finally:
            for pad in pads:
                pad.stop()

    def test_a_recusa_nao_martela_o_broker_entre_as_varreduras(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        """O ``pump_ff`` roda a cada tique: entre duas varreduras, nenhum pedido a mais.

        Mordida: tire o prazo (``_gadget_outra_vez_em``) que a recusa arma, e o
        primeiro tique depois do ``start`` já pede de novo.
        """
        pads = [mesa.pad(j) for j in jogadores]
        try:
            for pad in pads:
                assert pad.start() and pad._gadget is None
            for _ in range(120):
                mesa.passar(0.1, pads)
            assert mesa.pedidos_ao_broker == 3 * len(pads), (
                "a recusa pediu fora da varredura de _GADGET_VARRE_S"
            )
        finally:
            for pad in pads:
                pad.stop()

    def test_com_o_jogo_aberto_nenhum_troca_de_pele(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        pads = [mesa.pad(j) for j in jogadores]
        try:
            for pad in pads:
                assert pad.start() and pad._gadget is None
            mesa.sessao_aberta = True
            mesa.b.jogo_aberto = True
            for _ in range(4):
                mesa.passar(mesa.ug._GADGET_VARRE_S + 0.5, pads)
            assert mesa.b.pedidos == [], "com o jogo aberto o pad trocou de pele"
            assert all(pad._gadget is None and pad.is_active() for pad in pads)
            mesa.b.jogo_aberto = False
            mesa.passar(mesa.ug._GADGET_VARRE_S + 0.5, pads)
            assert all(pad._gadget is not None for pad in pads)
        finally:
            for pad in pads:
                pad.stop()


def test_a_recusa_que_nao_passa_nao_pede_de_novo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O descritor recusado não é a sessão que falta: pedir de novo não muda nada."""
    m = Mesa(monkeypatch, tmp_path, "broker_ausente")
    respostas: list[dict[str, Any]] = []

    def recusa(_cliente: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
        respostas.append(payload)
        return {"ok": False, "cmd": payload.get("cmd"), "error": "reject_bad_descriptor"}, []

    from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient

    monkeypatch.setattr(HidrawBrokerClient, "_request_with_fds", recusa)
    pad = m.pad(1)
    try:
        assert pad.start() and pad._gadget is None
        m.passar(3 * m.ug._GADGET_VARRE_S, [pad])
        assert len(respostas) == 1
        assert pad_usb.porque_sem_porta(MESA_MISTA[1][0]) == "reject_bad_descriptor"
    finally:
        pad.stop()
        m.broker.fechar()


@pytest.mark.parametrize("jogador", sorted(MESA_MISTA))
def test_o_que_o_jogo_ve_diz_a_haptica_pela_porta_do_pad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogador: int
) -> None:
    """Mordida: devolva ``nativo`` fixo na háptica, e o pad sem porta reprova."""
    m = Mesa(monkeypatch, tmp_path, "peer_recusado")
    identidade, transporte = MESA_MISTA[jogador]
    pad = m.pad(jogador)
    try:
        assert pad.start() and pad._gadget is None
        visto = oqv.o_que_o_jogo_ve(pad, transporte=transporte)
        assert visto is not None
        assert visto["forma"] == "dualsense" and visto["canal"] == "uhid"
        assert visto["funcoes"]["haptica"] != oqv.NATIVO  # (noqa-acento): chave ASCII
        assert visto["porta_motivo"] == "broker_fora_do_ar"
        assert visto["porta_motivo"] == pad_usb.porque_sem_porta(identidade)

        m.sessao_aberta = True
        m.passar(m.ug._GADGET_VARRE_S + 0.5, [pad])
        assert pad._gadget is not None
        m.enumerados[m.serial(pad)] = (f"hidraw{jogador}", INTERFACE_DO_GADGET)
        assert m.b.esperar(lambda: pad.is_bound)
        visto = oqv.o_que_o_jogo_ve(pad, transporte=transporte)
        assert visto is not None
        assert visto["funcoes"]["haptica"] == oqv.NATIVO  # (noqa-acento): chave ASCII
        assert visto["porta_motivo"] is None
    finally:
        pad.stop()
        m.broker.fechar()


def test_o_socket_de_mentira_cabe_no_limite_do_unix(tmp_path: Path) -> None:
    """O ``sun_path`` tem 108 bytes: um TMPDIR comprido faria a régua medir o bind."""
    assert len(os.fsencode(tmp_path / "broker.sock")) < 108
