"""O-PEDIDO-AO-SERVICO-QUE-AINDA-NAO-RESPONDEU-NAO-RODA-DE-NOVO-01.

O clique repetido pousa com o primeiro.

O `Piloto._gesto` de produção roda aqui com um piloto mínimo, a fila do GTK anotada numa lista
e o gesto da aba Sistema trocado por um que fica preso num evento. O pedido é ao serviço, não a
um controle: vale com qualquer mesa, de qualquer aba de onde o menu chama.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

SISTEMA = "09-sistema.html"
JOGAR = "01-jogar.html"
PRAZO_S = 5.0


class _Piloto:
    """O mínimo que `Piloto._gesto` lê, com o pouso de cada botão anotado."""

    def __init__(self) -> None:
        self.gestos: list[dict[str, Any]] = []
        self.recusados: list[str] = []
        self.desfechos: dict[str, tuple[str, str]] = {}
        self.pagina = SISTEMA
        self.pousos: list[tuple[str, object]] = []
        self._mesa_de_agora: list[dict[str, Any]] = []
        self._ctx_de_agora = None
        self._pintada = None

    def _com_uniq(self, o: dict[str, Any]) -> dict[str, Any]:
        return o

    def _pousou(self, voo: str, certo: object = None) -> bool:
        self.pousos.append((voo, certo))
        return False

    def _recusou_dizendo(self, *_: Any) -> bool:
        return False

    def _deu_certo_dizendo(self, *_: Any) -> bool:
        return False

    def _o_arranjo_relido(self, _pagina: str, resposta: Any) -> Any:
        return resposta


class _GestoPreso:
    """Um gesto que conta as chamadas e só volta quando o teste solta."""

    def __init__(self) -> None:
        self.chamadas = 0
        self.entrou = threading.Event()
        self.solta = threading.Event()

    def __call__(self, _ctx: Any, _o: dict[str, Any], _ipc: Any) -> None:
        self.chamadas += 1
        self.entrou.set()
        assert self.solta.wait(PRAZO_S), "o teste não soltou o gesto"


@pytest.fixture
def arnes(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    fila: list[Any] = []
    monkeypatch.setattr(hv, "GLib", SimpleNamespace(idle_add=fila.append))
    hv._registrar_o_menu()
    preso = _GestoPreso()
    monkeypatch.setitem(hv.pacotes.GESTOS, (SISTEMA, "reiniciar"), preso)

    def clicar(piloto: _Piloto, gesto: str, voo: str, pagina: str = SISTEMA) -> None:
        carga = {"gesto": gesto, "voo": voo, "pagina": pagina}  # (noqa-acento)
        hv.Piloto._gesto(piloto, carga)

    def esperar_a_fila(quantos: int) -> None:
        fim = time.monotonic() + PRAZO_S
        while len(fila) < quantos and time.monotonic() < fim:
            time.sleep(0.005)
        assert len(fila) >= quantos, f"a fila do GTK tem {len(fila)} de {quantos}"

    def rodar_a_fila() -> None:
        while fila:
            fila.pop(0)()

    return SimpleNamespace(hv=hv, a09=a09_sistema, preso=preso, clicar=clicar,
                           esperar_a_fila=esperar_a_fila, rodar_a_fila=rodar_a_fila)


def test_o_segundo_clique_antes_da_resposta_nao_roda_e_pousa_com_o_primeiro(
    arnes: SimpleNamespace, capsys: pytest.CaptureFixture[str],
) -> None:
    """D-2511-O-PEDIDO-AO-SERVICO-REPETIDO-ANTES-DA-RESPOSTA-E-O-MESMO-PEDIDO: uma chamada.

    Os dois botões pousam com o mesmo resultado.

    MORDIDA: tire do `_gesto` a guarda do pedido que voa, e o gesto roda duas vezes.
    """
    piloto = _Piloto()

    arnes.clicar(piloto, "reiniciar", "1")
    assert arnes.preso.entrou.wait(PRAZO_S)
    arnes.clicar(piloto, "reiniciar", "2")
    arnes.preso.solta.set()
    arnes.esperar_a_fila(2)
    arnes.rodar_a_fila()

    assert arnes.preso.chamadas == 1, arnes.preso.chamadas
    assert piloto.pousos == [("1", True), ("2", True)], piloto.pousos
    assert f"[gesto repetido] {SISTEMA} · reiniciar" in capsys.readouterr().err


def test_o_item_do_menu_durante_o_botao_e_o_mesmo_pedido(arnes: SimpleNamespace) -> None:
    """D-2511-O-PEDIDO-AO-SERVICO-REPETIDO-ANTES-DA-RESPOSTA-E-O-MESMO-PEDIDO: o menu de outra aba.

    MORDIDA: deixe de levar o item do menu ao gesto que ele chama, e o gesto roda duas vezes.
    """
    piloto = _Piloto()

    arnes.clicar(piloto, "reiniciar", "1")
    assert arnes.preso.entrou.wait(PRAZO_S)
    arnes.clicar(piloto, "menu-reiniciar", "2", JOGAR)
    arnes.preso.solta.set()
    arnes.esperar_a_fila(2)
    arnes.rodar_a_fila()

    assert arnes.preso.chamadas == 1, arnes.preso.chamadas
    assert piloto.pousos == [("1", True), ("2", True)], piloto.pousos


def test_o_clique_depois_do_pouso_roda_de_novo(arnes: SimpleNamespace) -> None:
    """Quem viu a resposta e clicou de novo pediu de novo.

    MORDIDA: deixe o pedido guardado depois do pouso, e o segundo clique nunca roda.
    """
    piloto = _Piloto()
    arnes.preso.solta.set()

    arnes.clicar(piloto, "reiniciar", "1")
    arnes.esperar_a_fila(2)
    arnes.rodar_a_fila()
    arnes.clicar(piloto, "reiniciar", "2")
    arnes.esperar_a_fila(2)
    arnes.rodar_a_fila()

    assert arnes.preso.chamadas == 2, arnes.preso.chamadas
    assert piloto.pousos == [("1", True), ("2", True)], piloto.pousos


def test_o_gesto_que_nao_declara_roda_a_cada_clique(
    arnes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O passo repetido de um botão segue contando: só o gesto de `UM_POR_VEZ` junta os cliques."""
    piloto = _Piloto()
    passo = _GestoPreso()
    monkeypatch.setitem(arnes.hv.pacotes.GESTOS, (SISTEMA, "passo-de-prova"), passo)

    arnes.clicar(piloto, "passo-de-prova", "1")
    assert passo.entrou.wait(PRAZO_S)
    arnes.clicar(piloto, "passo-de-prova", "2")
    passo.solta.set()
    arnes.esperar_a_fila(4)
    arnes.rodar_a_fila()

    assert passo.chamadas == 2, passo.chamadas
    assert sorted(piloto.pousos) == [("1", True), ("2", True)], piloto.pousos


def test_os_quatro_gestos_do_servico_declaram_um_por_vez(arnes: SimpleNamespace) -> None:
    """D-2511-O-PEDIDO-AO-SERVICO-REPETIDO-ANTES-DA-RESPOSTA-E-O-MESMO-PEDIDO: quem mexe no serviço.

    MORDIDA: tire o `um_por_vez=True` de um dos quatro, e ele some da lista.
    """
    pacotes = arnes.hv.pacotes
    do_servico = {chave for chave, porta in pacotes.GESTOS_QUE_MEXEM.items()
                  if porta == "_systemctl"}

    assert do_servico == {
        (SISTEMA, "autostart"), (SISTEMA, "reiniciar"), (SISTEMA, arnes.a09.DESLIGAR),
        (SISTEMA, "corrigir-modo")}, do_servico
    assert do_servico <= pacotes.UM_POR_VEZ, do_servico - pacotes.UM_POR_VEZ
    assert arnes.hv.o_pedido_de_um_por_vez(JOGAR, "menu-desligar", "") == (
        SISTEMA, "parar-ou-retomar", "")
