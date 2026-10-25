"""O-PAD-QUE-NASCE-OU-VOLTA-PEDE-O-GADGET-FORA-DO-TIQUE-01 (25/10/2026).

O pad cujo gadget caiu (ou não enumerou) volta ao uhid no tique, e a nova
tentativa, uma varredura depois, refazia o device ali mesmo: o
``_refazer_o_device`` pedia o gadget ao broker (``PEDIR_O_PAD_USB``) dentro do
``pump_ff``. Com o broker preso, o cliente espera o ``_TIMEOUT_S`` dele (2 s), e
o tique de entrada de TODOS os controles parava junto.

O pedido é o de VERDADE (``_pedir_ao_broker`` com o ``HidrawBrokerClient``)
contra um socket que aceita e não responde; o gadget que o broker devolve vem
da bancada do gadget, o mesmo dublê das outras réguas do pad em USB.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import INTERFACE_DO_GADGET
from tests.unit.test_o_pad_recusado_pelo_broker_tenta_de_novo import Mesa

#: o teto de um tique inteiro (o ``pump_ff`` e o report de cada pad).
TETO_DO_TIQUE_S = 0.05
#: P1 e P3 no cabo, P2 e P4 no rádio (``MESA_MISTA``); o último da tupla é o que cai.
MESAS = [((1, 2), 2), ((1, 2), 1), ((1, 2, 3, 4), 4), ((1, 2, 3, 4), 3), ((1,), 1),
         ((2, 4), 2), ((1, 3), 3)]
IDS = ["p2-bt-volta", "p1-usb-volta", "quatro-p4-volta", "quatro-p3-volta", "um-so",
       "todos-bt", "todos-usb"]
QUEDAS = ("caiu", "nao_enumerou")  # (noqa-acento): chave de máquina


def _guardar_o_lado_do_jogo(m: Mesa) -> None:
    """A bancada guarda só o último lado do jogo; o que ela larga fecharia o gadget."""
    lados = m.__dict__.setdefault("lados_do_jogo", [])
    if m.b.jogo is not None and m.b.jogo not in lados:
        lados.append(m.b.jogo)


def _de_pe(m: Mesa, jogadores: tuple[int, ...], quem_volta: int, queda: str) -> list[Any]:
    """Os pads no gadget; o de ``quem_volta`` perde o dele e volta ao uhid."""
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
    m.passar(0.1, pads, assentar=False)
    assert volta._gadget is None and volta.is_active(), "o pad que perdeu o gadget sumiu"
    assert volta._gadget_outra_vez, "o pad no uhid não arma a volta ao gadget"
    return pads


def _tique(m: Mesa, pads: list[Any], segundos: float) -> float:
    """Um tique do laço: o ``pump_ff`` e o report de cada pad, na ordem. Devolve a duração."""
    m.relogio[0] += segundos
    antes = time.perf_counter()
    for pad in pads:
        pad.pump_ff()
        _guardar_o_lado_do_jogo(m)
        assert pad.send_report(m.ug._report_neutro(pad)), f"o P{pad.player} parou de ler"
        pedido = getattr(pad, "_pedido_ao_broker", None)
        if pedido is not None and pedido not in m.pedidos_vistos:
            m.pedidos_vistos.append(pedido)
    return time.perf_counter() - antes


def _fechar(m: Mesa, pads: list[Any]) -> None:
    for pad in pads:
        pad.stop()
    m.broker.fechar()
    for pedido in m.pedidos_vistos:
        pedido.esperar(5.0)
    for lado in m.__dict__.get("lados_do_jogo", []):
        lado.close()


def _preso(m: Mesa, monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """O broker que responde só quando a régua solta (o gadget vem da bancada)."""
    solta = threading.Event()
    pedir = m.ug.PEDIR_O_PAD_USB

    def preso(*args: Any) -> Any:
        solta.wait(2.0)
        return pedir(*args)

    monkeypatch.setattr(m.ug, "PEDIR_O_PAD_USB", preso)
    return solta


@pytest.mark.parametrize("queda", QUEDAS)
@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_broker_preso_nao_prende_o_tique_da_volta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int, queda: str,
) -> None:
    # D-2510-A-VOLTA-DO-GADGET-PEDE-FORA-DO-TIQUE
    """O broker aceita e não responde: o tique da volta, e o dos outros, abaixo de 50 ms.

    Mordida: refaça o device no tique (``_refazer_o_device`` no lugar do
    ``_PedidoAoBroker``), e o tique da volta leva os 2 s do cliente.
    """
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    pads: list[Any] = []
    try:
        pads = _de_pe(m, jogadores, quem_volta, queda)
        m.sessao_aberta = False
        m.broker.modo = "travado"
        tiques = [_tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)]
        tiques += [_tique(m, pads, 0.1) for _ in range(3)]
        assert max(tiques) < TETO_DO_TIQUE_S, (
            f"um tique levou {max(tiques) * 1000:.2f} ms com o broker preso"
        )
        assert m.b.esperar(lambda: m.pedidos_ao_broker == 1), (
            "a volta não pediu o gadget ao broker"
        )
        volta = pads[jogadores.index(quem_volta)]
        assert volta._gadget is None and volta.is_active()
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize("queda", QUEDAS)
@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_a_resposta_que_chega_depois_monta_o_gadget_no_tique_seguinte(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int, queda: str,
) -> None:
    """O pad segue no uhid enquanto o broker pensa; a resposta o troca no tique seguinte.

    Mordida: tire a leitura do pedido (``_ler_o_pedido``) do ``pump_ff``, e o
    gadget que chegou nunca é montado.
    """
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    pads: list[Any] = []
    try:
        pads = _de_pe(m, jogadores, quem_volta, queda)
        volta = pads[jogadores.index(quem_volta)]
        solta = _preso(m, monkeypatch)
        antes = len(m.b.pedidos)
        assert _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5) < TETO_DO_TIQUE_S
        assert volta._pedido_ao_broker is not None, "a volta não pediu fora do tique"
        assert _tique(m, pads, 0.1) < TETO_DO_TIQUE_S
        assert volta._gadget is None and volta.is_active(), "o pad trocou sem a resposta"
        solta.set()
        assert volta._pedido_ao_broker.esperar(5.0)
        assert _tique(m, pads, 0.1) < TETO_DO_TIQUE_S
        assert volta._gadget is not None, "a resposta chegou e o pad ficou no uhid"
        assert volta._pedido_ao_broker is None
        assert len(m.b.pedidos) == antes + 1
        m.enumerados[m.serial(volta)] = (f"hidraw{volta.player}", INTERFACE_DO_GADGET)
        assert m.b.esperar(lambda: volta.is_bound), "o gadget da volta não enumerou"
        for _ in range(3):
            _tique(m, pads, m.ug._GADGET_VARRE_S)
        assert len(m.b.pedidos) == antes + 1, "o pad de volta ao gadget pediu outro"
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_stop_no_meio_do_pedido_desmonta_o_gadget_que_chega_tarde(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int,
) -> None:
    """Mordida: tire o ``largar`` do ``stop``, e o gadget fica montado sem pad."""
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    pads: list[Any] = []
    try:
        pads = _de_pe(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        solta = _preso(m, monkeypatch)
        clientes = len(m.b.clientes)
        _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)
        pedido = volta._pedido_ao_broker
        assert pedido is not None, "a volta não pediu fora do tique"
        volta.stop()
        solta.set()
        assert pedido.esperar(5.0), "o pedido largado não terminou"
        assert len(m.b.clientes) == clientes + 1
        assert m.b.clientes[-1].desmontados, "o gadget que chegou depois do stop ficou montado"
        assert volta._gadget is None and not volta.is_active()
    finally:
        _fechar(m, pads)


@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_jogo_que_abre_com_o_pedido_em_voo_nao_troca_a_pele(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int,
) -> None:
    """A resposta que chega com o jogo aberto desce, e a volta espera o jogo fechar.

    Mordida: tire a pergunta pelo jogo depois da resposta, e o pad troca de
    pele embaixo do jogo.
    """
    m = Mesa(monkeypatch, tmp_path, "sem_sessao_ativa")
    pads: list[Any] = []
    try:
        pads = _de_pe(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        solta = _preso(m, monkeypatch)
        clientes = len(m.b.clientes)
        _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)
        pedido = volta._pedido_ao_broker
        assert pedido is not None
        m.b.jogo_aberto = True
        solta.set()
        assert pedido.esperar(5.0)
        for _ in range(3):
            _tique(m, pads, m.ug._GADGET_VARRE_S + 0.5)
        assert volta._gadget is None and volta.is_active(), "o pad trocou de pele no jogo"
        assert m.b.clientes[clientes].desmontados, "o gadget recusado pelo jogo ficou montado"
        assert len(m.b.clientes) == clientes + 1, "com o jogo aberto a volta pediu de novo"
        m.b.jogo_aberto = False
        m.passar(m.ug._GADGET_VARRE_S + 0.5, pads)
        assert volta._gadget is not None, "o jogo fechou e a volta não voltou ao gadget"
    finally:
        _fechar(m, pads)
