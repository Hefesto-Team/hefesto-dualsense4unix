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
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from hefesto_dualsense4unix.integrations import o_que_o_jogo_ve as oqv
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations.hidraw_broker_client import SOCKET_PATH_ENV
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import (
    INTERFACE_DO_GADGET,
    BancadaDoGadget,
    _EspiaoDoDiario,
)

MESA_MISTA = {
    1: ("aa:bb:cc:00:00:11", "usb"),
    2: ("aa:bb:cc:00:00:22", "bt"),
    3: ("aa:bb:cc:00:00:33", "usb"),
    4: ("aa:bb:cc:00:00:44", "bt"),
}
RECUSAS = ("broker_ausente", "peer_recusado", "sem_sessao_ativa")
MOTIVO_DA_RECUSA = {"broker_ausente": "broker_fora_do_ar", "peer_recusado": "broker_fora_do_ar",
                    "sem_sessao_ativa": "sem_sessao_ativa"}


class BrokerAntesDoLogin:
    """O socket do broker antes de haver sessão na frente.

    ``broker_ausente``: o socket não existe. ``peer_recusado``: aceita e fecha
    (o ``register_client`` com ``nao_e_quem_esta_na_frente``). ``sem_sessao_ativa``:
    aceita, lê o pedido e recusa com o erro do ``_cmd_pad_usb_montar``.
    ``travado``: aceita e nunca responde (o broker de pé e preso), e o cliente
    espera o ``_TIMEOUT_S`` dele inteiro. ``atende``: responde ``ok`` a um pedido
    e fecha (o broker que reinicia depois de atender).
    """

    def __init__(self, caminho: Path, modo: str) -> None:
        self.caminho = caminho
        self.modo = modo
        self.conexoes = 0
        self._pare = threading.Event()
        self._sock: socket.socket | None = None
        self._fio: threading.Thread | None = None
        self._presas: list[socket.socket] = []
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
            if self.modo == "travado":
                self._presas.append(conn)
                continue
            with conn:
                if self.modo == "atende":
                    conn.settimeout(2.0)
                    with contextlib.suppress(OSError):
                        conn.recv(65536)
                        conn.sendall(b'{"ok": true}\n')
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
        for conn in self._presas:
            conn.close()
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
        self.enumerados: dict[str, tuple[str, str]] = {}
        self.broker = BrokerAntesDoLogin(tmp_path / "broker.sock", modo)
        monkeypatch.setenv(SOCKET_PATH_ENV, str(self.broker.caminho))
        monkeypatch.setattr(self.ug, "HIDRAW_DO_GADGET", self.enumerados.get)
        monkeypatch.setattr(self.ug, "QUIRK_DO_PAR", lambda _par: False)
        monkeypatch.setattr(self.ug, "_RECUSAS_DO_BROKER", {}, raising=False)
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
        self.espiao_do_cliente = _EspiaoDoDiario(hbc.logger)
        monkeypatch.setattr(hbc, "logger", self.espiao_do_cliente)
        self.pads: list[Any] = []
        self.pedidos_vistos: list[Any] = []

    def pad(self, jogador: int) -> Any:
        identidade, _transporte = MESA_MISTA[jogador]
        pad = self.b.pad(player=jogador, identity=identidade,
                         time_fn=lambda: self.relogio[0])
        self.pads.append(pad)
        return pad

    def serial(self, pad: Any) -> str:
        return str(pad_usb.serial_do_pad(pad.mac, pad.player))

    def passar(self, segundos: float, pads: list[Any], *, assentar: bool = True) -> None:
        """O relógio anda e cada pad dá um tique.

        O pedido da nova tentativa corre fora do tique, e o tique seguinte lê a
        resposta: ``assentar`` espera os pedidos em voo responderem e dá o tique
        que a lê, no mesmo instante do relógio.
        """
        self.relogio[0] += segundos
        for pad in pads:
            pad.pump_ff()
            pedido = getattr(pad, "_pedido_ao_broker", None)
            if pedido is not None and pedido not in self.pedidos_vistos:
                self.pedidos_vistos.append(pedido)
        if assentar and self.esperar_os_pedidos(pads):
            for pad in pads:
                pad.pump_ff()

    def esperar_os_pedidos(self, pads: list[Any], segundos: float = 5.0) -> bool:
        """True = havia pedido em voo, e todos já responderam."""
        em_voo = [p for p in (getattr(pad, "_pedido_ao_broker", None) for pad in pads) if p]
        for pedido in em_voo:
            assert pedido.esperar(segundos), "o pedido ao broker não voltou"
        return bool(em_voo)

    def eventos(self, nome: str) -> int:
        return sum(1 for _nivel, evento in self.espiao.eventos if evento == nome)

    def linhas_do_cliente(self) -> int:
        """As linhas de ``info`` do cliente do broker sobre a lease."""
        return sum(1 for nivel, evento in self.espiao_do_cliente.eventos
                   if nivel == "info" and evento in ("hidraw_broker_lease_open",
                                                     "hidraw_broker_unavailable"))


@pytest.fixture(params=RECUSAS)
def mesa(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
         tmp_path: Path) -> Iterator[Mesa]:
    m = Mesa(monkeypatch, tmp_path, request.param)
    try:
        yield m
    finally:
        m.broker.fechar()
        for pedido in m.pedidos_vistos:
            pedido.esperar(5.0)


@pytest.mark.parametrize("jogadores", [(1, 2), (1, 2, 3, 4), (1,), (2, 4), (1, 3)],
                         ids=["p1-usb+p2-bt", "quatro-mistos", "um-so", "todos-bt", "todos-usb"])
class TestARecusaDoBrokerTentaDeNovo:
    def test_sem_jogo_cada_pad_acaba_no_gadget_quando_a_sessao_abre(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        """Mordida: tire o ``_gadget_outra_vez = True`` do ramo da recusa, e o pad fica no uhid.

        Prova da D-2410-O-PAD-RECUSADO-PELA-SESSAO-PEDE-DE-NOVO.
        """
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

    def test_120_tiques_recusados_dao_uma_linha_por_pad_tambem_no_cliente(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        """Mordida: grave a linha da lease em toda conexão, e o cliente dá três por pad.

        Prova da D-2410-O-PAD-RECUSADO-NAO-ENCHE-O-DIARIO.
        """
        pads = [mesa.pad(j) for j in jogadores]
        try:
            for pad in pads:
                assert pad.start() and pad._gadget is None
            for _ in range(120):
                mesa.passar(0.1, pads)
            assert mesa.pedidos_ao_broker == 3 * len(pads)
            assert mesa.eventos("pad_usb_indisponivel_fica_o_uhid") == len(pads)
            assert mesa.linhas_do_cliente() == len(pads), (
                "o cliente do broker gravou a lease a cada nova tentativa"
            )
        finally:
            for pad in pads:
                pad.stop()

    def test_o_pad_montado_de_novo_diz_a_recusa_de_novo(
        self, mesa: Mesa, jogadores: tuple[int, ...]
    ) -> None:
        """O mesmo serial, o mesmo motivo: o pad que parou e voltou grava a recusa.

        Mordida: tire a limpeza da recusa do ``stop``, e a volta fica muda no diário.
        """
        pads = [mesa.pad(j) for j in jogadores]
        try:
            for pad in pads:
                assert pad.start() and pad._gadget is None
            for pad in pads:
                pad.stop()
            for pad in pads:
                assert pad.start() and pad._gadget is None
            assert mesa.pedidos_ao_broker == 2 * len(pads)
            assert mesa.eventos("pad_usb_indisponivel_fica_o_uhid") == 2 * len(pads), (
                "o pad que voltou com o mesmo serial ficou mudo na recusa"
            )
            assert mesa.linhas_do_cliente() == 2 * len(pads)
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


TETO_DO_TIQUE_S = 0.05


@pytest.mark.parametrize("jogadores", [(1, 2), (1, 2, 3, 4), (1,), (2, 4), (1, 3)],
                         ids=["p1-usb+p2-bt", "quatro-mistos", "um-so", "todos-bt", "todos-usb"])
def test_o_broker_preso_nao_prende_o_tique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...]
) -> None:
    """O broker aceita e não responde: nenhum tique passa de 50 ms.

    O pad nasce recusado pela sessão; depois o broker fica preso, e cada nova
    tentativa esperaria o ``_TIMEOUT_S`` do cliente (2 s) dentro do tique de
    entrada. Mordida: peça ao broker de dentro do tique, e o tique leva 2 s.

    Prova da D-2410-O-PEDIDO-DE-NOVO-SAI-DO-TIQUE.
    """
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    pads = [m.pad(j) for j in jogadores]
    tiques: list[float] = []
    try:
        for pad in pads:
            assert pad.start() and pad._gadget is None
        m.broker.modo = "travado"
        for volta in range(3):
            m.relogio[0] += m.ug._GADGET_VARRE_S + 0.5 if volta == 0 else 0.1
            for pad in pads:
                antes = time.perf_counter()
                pad.pump_ff()
                tiques.append(time.perf_counter() - antes)
                pedido = getattr(pad, "_pedido_ao_broker", None)
                if pedido is not None and pedido not in m.pedidos_vistos:
                    m.pedidos_vistos.append(pedido)
        assert m.b.esperar(lambda: m.pedidos_ao_broker == 2 * len(pads)), (
            "a nova tentativa não pediu ao broker"
        )
        assert max(tiques) < TETO_DO_TIQUE_S, (
            f"um tique levou {max(tiques) * 1000:.2f} ms com o broker preso"
        )
        assert all(pad.is_active() and pad._gadget is None for pad in pads)
    finally:
        for pad in pads:
            pad.stop()
        m.broker.fechar()
        for pedido in m.pedidos_vistos:
            pedido.esperar(5.0)


@pytest.mark.parametrize("jogadores", [(1, 2), (1, 2, 3, 4), (1,), (2, 4), (1, 3)],
                         ids=["p1-usb+p2-bt", "quatro-mistos", "um-so", "todos-bt", "todos-usb"])
def test_o_gadget_que_chega_depois_do_stop_volta_ao_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...]
) -> None:
    """O pad para com a nova tentativa em voo: o gadget que chega tarde se desmonta.

    A-REGUA-DO-GADGET-TARDIO-NAO-CORRE-CONTRA-O-PRAZO-DO-STOP-01 (28/10/2026): o
    ``stop`` espera o pedido largado por ``_DESCIDA_ESPERA_S``, e o dublê preso
    esperava o mesmo prazo; o caminho saía no sorteio, e no do gadget depois do
    ``stop`` a régua lia o broker antes de o fio da descida devolvê-lo. Zerado o
    prazo, o gadget chega sempre depois do ``stop``, e a régua espera a descida
    pela porta do daemon que para (``esperar_as_descidas``).

    Mordida: tire o ``desmontar`` do pedido largado, e o gadget fica montado sem pad.
    """
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    monkeypatch.setattr(m.ug, "_DESCIDA_AO_BROKER", m.ug._DescidaAoBroker())
    monkeypatch.setattr(m.ug, "_DESCIDA_ESPERA_S", 0.0)
    solta = threading.Event()
    pedir = m.ug.PEDIR_O_PAD_USB

    def preso(*args: Any) -> Any:
        solta.wait(5.0)
        return pedir(*args)

    pads = [m.pad(j) for j in jogadores]
    try:
        for pad in pads:
            assert pad.start() and pad._gadget is None
        m.sessao_aberta = True
        monkeypatch.setattr(m.ug, "PEDIR_O_PAD_USB", preso)
        m.passar(m.ug._GADGET_VARRE_S + 0.5, pads, assentar=False)
        assert all(pad._pedido_ao_broker is not None for pad in pads)
        for pad in pads:
            pad.stop()
        solta.set()
        for pedido in m.pedidos_vistos:
            assert pedido.esperar(5.0), "o pedido largado não terminou"
        assert m.ug.esperar_as_descidas(5.0), "a descida do gadget tardio não terminou"
        assert len(m.b.clientes) == len(pads)
        assert all(cliente.desmontados for cliente in m.b.clientes), (
            "o gadget que chegou depois do stop ficou montado sem pad"
        )
        assert all(pad._gadget is None and not pad.is_active() for pad in pads)
        assert not any(m.serial(pad) in m.ug._RECUSAS_DO_BROKER for pad in pads)
    finally:
        solta.set()
        for pad in pads:
            pad.stop()
        m.broker.fechar()
        for pedido in m.pedidos_vistos:
            pedido.esperar(5.0)


def _leases(espiao: Any) -> int:
    return sum(1 for nivel, evento in espiao.eventos
               if nivel == "info" and evento == "hidraw_broker_lease_open")


def test_a_lease_se_diz_de_novo_depois_de_ok_e_depois_do_broker_fora(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A lease calada é só a reabertura sem resposta; as outras voltas se dizem.

    O cliente principal do daemon recebe ``ok`` e, quando o broker reinicia, diz a
    lease nova; o peer recusado que volta depois do broker fora do ar também.
    Mordida: tire o ``_lease_dita = False`` do ``ok`` ou do connect que falhou, e
    a volta fica muda.
    """
    espiao = _EspiaoDoDiario(hbc.logger)
    monkeypatch.setattr(hbc, "logger", espiao)
    caminho = tmp_path / "broker.sock"

    atende = BrokerAntesDoLogin(caminho, "atende")
    try:
        cliente = hbc.HidrawBrokerClient(str(caminho), timeout_s=1.0)
        for _ in range(3):
            assert cliente.ping()
        assert _leases(espiao) == 3, "o broker que atendeu e reiniciou ficou sem a lease nova"
        cliente.close()
    finally:
        atende.fechar()
    caminho.unlink()

    espiao.eventos.clear()
    recusa = BrokerAntesDoLogin(caminho, "peer_recusado")
    cliente = hbc.HidrawBrokerClient(str(caminho), timeout_s=1.0)
    try:
        for _ in range(5):
            assert not cliente.ping()
        assert _leases(espiao) == 1, "a reabertura recusada se disse a cada volta"
    finally:
        recusa.fechar()
    assert not cliente.ping()
    caminho.unlink()
    volta = BrokerAntesDoLogin(caminho, "peer_recusado")
    try:
        assert not cliente.ping()
        assert _leases(espiao) == 2, "o broker que voltou depois de fora do ar ficou mudo"
    finally:
        volta.fechar()
        cliente.close()


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
        assert visto["funcoes"]["haptica"] != oqv.NATIVO  # (noqa-acento)
        assert visto["porta_motivo"] == "broker_fora_do_ar"
        assert visto["porta_motivo"] == pad_usb.porque_sem_porta(identidade)

        m.sessao_aberta = True
        m.passar(m.ug._GADGET_VARRE_S + 0.5, [pad])
        assert pad._gadget is not None
        m.enumerados[m.serial(pad)] = (f"hidraw{jogador}", INTERFACE_DO_GADGET)
        assert m.b.esperar(lambda: pad.is_bound)
        visto = oqv.o_que_o_jogo_ve(pad, transporte=transporte)
        assert visto is not None
        assert visto["funcoes"]["haptica"] == oqv.NATIVO  # (noqa-acento)
        assert visto["porta_motivo"] is None
    finally:
        pad.stop()
        m.broker.fechar()


def test_o_socket_de_mentira_cabe_no_limite_do_unix(tmp_path: Path) -> None:
    """O ``sun_path`` tem 108 bytes: um TMPDIR comprido faria a régua medir o bind."""
    assert len(os.fsencode(tmp_path / "broker.sock")) < 108
