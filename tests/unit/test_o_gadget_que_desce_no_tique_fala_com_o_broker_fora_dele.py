"""O-GADGET-QUE-DESCE-NO-TIQUE-FALA-COM-O-BROKER-FORA-DELE-01 (25/10/2026).

A volta do gadget já pedia ao broker fora do tique (``_PedidoAoBroker``); a
descida, não. O pad cujo gadget caiu (ou não enumerou) volta ao uhid no
``pump_ff``, e o ``_soltar_o_gadget`` chamava ``gadget.desmontar()`` ali mesmo:
o ``desmontar_pad_usb`` do cliente espera o ``_TIMEOUT_S`` dele (2 s) e tenta
duas vezes. A sobra do ``_refazer_o_device`` (o gadget na mão quando o pad
retoma um estacionado) descia do mesmo jeito. Com o broker preso, a entrada de
TODOS os controles parava junto, justo quando um deles perdeu a porta.

O cliente da descida é o de VERDADE (``HidrawBrokerClient``) contra um socket
que aceita e não responde; o resto do gadget vem da bancada do gadget, o mesmo
dublê das outras réguas do pad em USB.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from hefesto_dualsense4unix.integrations import pad_usb
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import INTERFACE_DO_GADGET, ClienteDeMentira
from tests.unit.test_o_pad_que_nasce_pede_o_gadget_fora_do_tique import (
    IDS,
    MESAS,
    QUEDAS,
    TETO_DO_TIQUE_S,
    _guardar_o_lado_do_jogo,
    _tique,
)
from tests.unit.test_o_pad_recusado_pelo_broker_tenta_de_novo import Mesa

#: o pior caso do cliente preso: duas tentativas de ``_TIMEOUT_S`` cada.
PRESO_S = 2 * hbc._TIMEOUT_S


class ClienteLento:
    """O broker que responde ao ``desmontar`` só quando a régua solta."""

    def __init__(self, solta: threading.Event) -> None:
        self.solta = solta
        self.desmontados: list[str] = []
        self.fechado = False

    def desmontar_pad_usb(self, gadget: str) -> bool:
        self.solta.wait(PRESO_S)
        self.desmontados.append(gadget)
        return True

    def close(self) -> None:
        self.fechado = True


def _a_descida(m: Mesa) -> Any:
    """O dono da descida desta mesa, novo: a fila da mesa anterior não entra nesta."""
    return m.ug.__dict__.get("_DESCIDA_AO_BROKER")


def _ate_a_queda(m: Mesa, jogadores: tuple[int, ...], quem_volta: int, queda: str) -> list[Any]:
    """Os pads no gadget; o de ``quem_volta`` perde o dele, e o tique seguinte o desce."""
    m.sessao_aberta = True
    pads = [m.pad(j) for j in jogadores]
    for pad in pads:
        assert pad.start() and pad._gadget is not None
        _guardar_o_lado_do_jogo(m)
    volta = pads[jogadores.index(quem_volta)]
    for pad in pads:
        if pad is not volta or queda == "caiu":
            m.enumerados[m.serial(pad)] = (f"hidraw{pad.player}", INTERFACE_DO_GADGET)
    assert m.b.esperar(lambda: all(p.is_bound for p in pads if p is not volta or
                                   queda == "caiu"))
    if queda == "caiu":
        gadget = volta._gadget
        m.enumerados.pop(m.serial(volta))
        gadget.falhas_seguidas = 1
        m.ug._o_gadget_caiu(volta, gadget)
        assert volta._gadget_caiu
    else:
        # o prazo da enumeração conta a fila: quem nasceu atrás espera mais
        m.relogio[0] = volta._gadget_prazo + 1.0
        assert m.b.esperar(lambda: volta._gadget_falhou)
    return pads


def _fechar(m: Mesa, pads: list[Any]) -> None:
    """O broker fecha antes: a descida presa nele termina, e o ``stop`` não a espera."""
    m.broker.fechar()
    descida = _a_descida(m)
    if descida is not None:
        assert descida.esperar_tudo(2 * PRESO_S), "a descida não terminou com o broker fechado"
    for pad in pads:
        pad.stop()
    for pedido in m.pedidos_vistos:
        pedido.esperar(5.0)
    for lado in m.__dict__.get("lados_do_jogo", []):
        lado.close()


def _mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Mesa:
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    if hasattr(m.ug, "_DescidaAoBroker"):
        monkeypatch.setattr(m.ug, "_DESCIDA_AO_BROKER", m.ug._DescidaAoBroker())
    return m


@pytest.mark.parametrize("queda", QUEDAS)
@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_tique_em_que_o_gadget_cai_nao_espera_o_broker_preso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int, queda: str,
) -> None:
    # D-2510-A-DESCIDA-DO-GADGET-FALA-COM-O-BROKER-FORA-DO-TIQUE
    """O broker aceita e não responde: o tique da queda, e os seguintes, abaixo de 50 ms.

    Mordida: devolva o ``gadget.desmontar()`` ao ``_soltar_o_gadget`` (a descida
    no tique), e o tique da queda leva as duas tentativas do cliente, ~4 s.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, jogadores, quem_volta, queda)
        volta = pads[jogadores.index(quem_volta)]
        gadget = volta._gadget
        gadget.cliente = hbc.HidrawBrokerClient()
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        tiques = [_tique(m, pads, 0.1)]
        assert volta._gadget is None and volta.is_active(), (
            "o pad que perdeu o gadget não está no uhid quando a descida começa"
        )
        tiques += [_tique(m, pads, 0.1) for _ in range(3)]
        assert max(tiques) < TETO_DO_TIQUE_S, (
            f"um tique levou {max(tiques) * 1000:.2f} ms com o broker preso na descida"
        )
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            "a descida não chegou ao broker"
        )
        # a parte da casa desce no tique: a fila da enumeração e a âncora do som
        assert gadget.serial not in m.ug._FILA_DA_ENUMERACAO
        assert pad_usb.interface_do_aparelho(volta.identity) != INTERFACE_DO_GADGET
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_a_sobra_do_refazer_desce_fora_do_tique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int,
) -> None:
    """O pad que volta retoma o estacionado; o gadget na mão é a sobra, e desce fora do tique.

    Mordida: devolva o ``sobra.desmontar()`` ao ``_refazer_o_device``, e o tique
    da troca leva as duas tentativas do cliente preso.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        m.passar(0.1, pads, assentar=False)
        assert volta._gadget is None and volta._gadget_outra_vez
        assert _a_descida(m).esperar_tudo(2.0)
        # o estacionado do aparelho, que o refazer retoma antes do gadget na mão
        nosso, jogo = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        os.set_blocking(nosso.fileno(), False)
        m.__dict__.setdefault("lados_do_jogo", []).append(jogo)
        estacionado = m.ug._GadgetDoPad(
            cliente=ClienteDeMentira(), fd=nosso.detach(), gadget="hefesto-pad-9",
            serial=m.serial(volta), identidade=volta.identity or "",
            hidraw=f"hidraw{volta.player}", interface=INTERFACE_DO_GADGET,
            par=(m.ug.DUALSENSE_VENDOR, volta.product),
        )
        chave = pad_usb._so_hex(volta.identity or "")
        m.ug._GADGETS_ESTACIONADOS._por_aparelho[chave] = m.ug._Estacionado(estacionado)
        pedir = m.ug.PEDIR_O_PAD_USB
        presos: list[Any] = []

        def na_mao_preso(*args: Any) -> Any:
            gadget = pedir(*args)
            if gadget is not None:
                gadget.cliente = hbc.HidrawBrokerClient()
                presos.append(gadget)
            return gadget

        monkeypatch.setattr(m.ug, "PEDIR_O_PAD_USB", na_mao_preso)
        assert _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5) < TETO_DO_TIQUE_S
        pedido = volta._pedido_ao_broker
        assert pedido is not None and pedido.esperar(5.0)
        assert presos, "a volta não trouxe o gadget na mão"
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        duracao = _tique(m, pads, 0.1)
        assert volta._gadget is estacionado, "o refazer não retomou o estacionado"
        assert duracao < TETO_DO_TIQUE_S, (
            f"o tique da troca levou {duracao * 1000:.2f} ms com o broker preso na sobra"
        )
        assert _tique(m, pads, 0.1) < TETO_DO_TIQUE_S
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            "a sobra não foi devolvida ao broker"
        )
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize("troca", ("outra_roupa", "features_recusadas"))
@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_as_outras_descidas_do_refazer_saem_fora_do_tique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int, troca: str,
) -> None:
    """As outras duas descidas que o refazer do tique faz: o estacionado de outra roupa e o
    gadget na mão cujas features o ``f_hid`` recusa. Nenhuma espera o broker no tique, e o
    ``stop`` do pad espera as duas (o dono é ele).

    Mordida: devolva o ``achado.gadget.desmontar()`` ao ``retomar`` (ou o
    ``gadget.desmontar()`` às features recusadas), e o tique da troca leva ~4 s;
    desça o de outra roupa sem dono, e o ``stop`` não o espera.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        m.passar(0.1, pads, assentar=False)
        assert volta._gadget is None and volta._gadget_outra_vez
        descida = _a_descida(m)
        assert descida.esperar_tudo(2.0)
        preso = None
        if troca == "outra_roupa":
            nosso, jogo = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            os.set_blocking(nosso.fileno(), False)
            m.__dict__.setdefault("lados_do_jogo", []).append(jogo)
            preso = m.ug._GadgetDoPad(
                cliente=hbc.HidrawBrokerClient(), fd=nosso.detach(), gadget="hefesto-pad-9",
                serial=m.serial(volta), identidade=volta.identity or "",
                hidraw=f"hidraw{volta.player}", interface=INTERFACE_DO_GADGET,
                par=(m.ug.DUALSENSE_VENDOR, volta.product ^ 1),
            )
            chave = pad_usb._so_hex(volta.identity or "")
            m.ug._GADGETS_ESTACIONADOS._por_aparelho[chave] = m.ug._Estacionado(preso)
        pedir = m.ug.PEDIR_O_PAD_USB
        presos: list[Any] = []

        def na_mao(*args: Any) -> Any:
            gadget = pedir(*args)
            if gadget is not None and troca == "features_recusadas":
                gadget.cliente = hbc.HidrawBrokerClient()
            if gadget is not None:
                presos.append(gadget)
            return gadget

        monkeypatch.setattr(m.ug, "PEDIR_O_PAD_USB", na_mao)
        assert _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5) < TETO_DO_TIQUE_S
        pedido = volta._pedido_ao_broker
        assert pedido is not None and pedido.esperar(5.0)
        assert presos, "a volta não trouxe o gadget na mão"
        if troca == "features_recusadas":
            def recusa(*_args: Any) -> None:
                raise OSError("o f_hid recusou")

            monkeypatch.setattr(m.ug.pad_usb, "escrever_get_report", recusa)
        m.broker.modo = "travado"
        conexoes = m.broker.conexoes
        duracao = _tique(m, pads, 0.1)
        assert duracao < TETO_DO_TIQUE_S, (
            f"o tique da troca levou {duracao * 1000:.2f} ms com o broker preso ({troca})"
        )
        if troca == "outra_roupa":
            assert volta._gadget is presos[0], "o pad não vestiu o gadget na mão"
        else:
            assert volta._gadget is None and volta.is_active(), "o pad não ficou no uhid"
        assert _tique(m, pads, 0.1) < TETO_DO_TIQUE_S
        assert m.b.esperar(lambda: m.broker.conexoes > conexoes), (
            f"a descida ({troca}) não chegou ao broker"
        )
        assert m.b.esperar(lambda: descida.em_voo_de(volta)), (
            f"a descida ({troca}) não é do pad: o stop dele não a espera"
        )
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize("vez", ("em_voo", "na_fila"))
@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_stop_com_a_descida_em_voo_nao_larga_gadget_montado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int, vez: str,
) -> None:
    """O ``stop`` só volta com o gadget do pad devolvido ao broker, esteja a descida onde estiver.

    ``em_voo``: o fio já fala com o broker lento, e o ``stop`` espera a resposta.
    ``na_fila``: o fio está preso na descida de outro gadget, e o ``stop`` desce o
    do pad ele mesmo, sem esperar a do outro.

    Mordida: tire o ``terminar`` do ``stop``, e o pad parado deixa o gadget
    montado no broker.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    descida = _a_descida(m)
    solta_o_outro = threading.Event()
    try:
        pads = _ate_a_queda(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        solta = threading.Event()
        lento = ClienteLento(solta)
        volta._gadget.cliente = lento
        if vez == "na_fila":
            solta.set()
            nosso, jogo = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            jogo.close()
            outro = m.ug._GadgetDoPad(cliente=ClienteLento(solta_o_outro), fd=nosso.detach(),
                                      gadget="hefesto-pad-8", serial="hefesto-pad-de-outro")
            descida.descer(outro, None)
        assert _tique(m, pads, 0.1) < TETO_DO_TIQUE_S
        assert volta._gadget is None and volta.is_active()
        if vez == "em_voo":
            assert m.b.esperar(lambda: descida.em_voo_de(volta)), "a descida não saiu"
            threading.Timer(0.3, solta.set).start()
        antes = time.monotonic()
        volta.stop()
        duracao = time.monotonic() - antes
        assert lento.desmontados, "o pad parou com o gadget montado no broker"
        assert lento.fechado, "o pad parou com a lease do gadget aberta"
        if vez == "na_fila":
            assert duracao < 1.0, (
                f"o stop esperou a descida de outro gadget ({duracao:.2f} s)"
            )
            assert not solta_o_outro.is_set()
        assert not descida.em_voo_de(volta)
    finally:
        solta_o_outro.set()
        _fechar(m, pads)


def test_o_pedido_do_mesmo_serial_espera_a_descida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """O broker recusa o serial repetido: o pedido novo do serial só sai com a descida feita.

    Mordida: tire o ``esperar`` do pedido (``_pedir_na_vez``), e o pedido chega
    ao broker com a descida do mesmo serial ainda em voo.
    """
    m = _mesa(monkeypatch, tmp_path)
    descida = _a_descida(m)
    solta = threading.Event()
    lento = ClienteLento(solta)
    nosso, jogo = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    jogo.close()
    serial = "hefesto-pad-aabbcc000011"
    descida.descer(m.ug._GadgetDoPad(cliente=lento, fd=nosso.detach(),
                                     gadget="hefesto-pad-0", serial=serial), None)
    vistos: list[bool] = []

    def pedir(*args: Any) -> None:
        vistos.append(bool(lento.desmontados))

    try:
        threading.Timer(0.3, solta.set).start()
        assert m.ug._pedir_na_vez(pedir, (serial, b"", "", (0, 0))) is None
        assert vistos == [True], "o pedido do serial saiu antes da descida dele"
    finally:
        solta.set()
        m.broker.fechar()
        assert descida.esperar_tudo(PRESO_S)
