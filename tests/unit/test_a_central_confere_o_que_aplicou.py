"""A central CONFERE o que aplicou — MOVER-UM-POR-VEZ-01 (23/09/2026).

O coração da sprint: *"o BlueZ disse que pareou"* não é *"o controle chegou"*.
Só o ``HID_PHYS`` no adaptador pretendido E o movimento chegando dizem
«chegou»; sem os dois o estado fica «esperando».

FATO SUBSTITUÍDO (25/09/2026, A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01): aqui se
lia *«e a origem NÃO se apaga»*. Desde a lista dela de 25/09 a origem sai ANTES
do gesto (a R1 dela ao pé da letra — ligado, o controle não entra em modo de
parear, e com a chave lá ele volta sozinho). O que o CONFERIR segura continua
sendo o «chegou»: sem os dois sinais, nunca «chegou», e o diário não diz
«moveu».

O mundo é o ``radio_de_mentira`` com o botão ``pair_mente``: o ``Pair``
responde que deu e o controle não muda de host — o «aplicar que falha» da
sprint, que o BlueZ não denuncia.

O QUE ESTA RÉGUA COBRA:

1. o aplicar que falha fica «esperando», e nada se apaga — **mordida:** sem o
   CONFERIR dá «chegou» e a régua reprova;
2. o «esperando» resolve pela vigia: o ``HID_PHYS`` confirma depois → «chegou»
   (e só então a origem sai); ele volta para a origem → «não chegou»; o prazo
   acaba → «não chegou»;
3. ``HID_PHYS`` sem movimento não é chegada;
4. o que não é controle (o fone) confere pelo ``Connected`` do destino;
5. sem BlueZ é «não sei», e nada se escreve; a webcam não se move; o
   movimento em «não sei» não apaga a conexão viva do destino; um erro no meio
   não deixa a central emperrada num «esperando»;
6. sem o agente próprio, o piso atende o ``Pair`` (decisão de quem coordena);
7. os estados publicados são só os três;
8. o ``state_full`` não abre o dono nem espera a foto do rádio;
9. sob a suíte, a ponte root de verdade não roda.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit.radio_de_mentira import QUARTO, SALA, VERMELHO


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


def _da_central(diario: Path) -> list[str]:
    alvo = {cr.MOVEU_O_APARELHO, cr.O_APARELHO_NAO_CHEGOU}
    return [e["o_que"] for e in diario_do_radio.ler(caminhos=[diario]) if e["o_que"] in alvo]


# 8. o state_full não espera o rádio


class _LeitorLento(bd.LeitorDoBluez):
    """O caminho de reserva (``busctl``): cada foto custa subprocessos."""

    def __init__(self) -> None:
        self.solta = threading.Event()
        self.fotos = 0

    def pode_perguntar(self) -> bool:
        return True

    def adaptadores(self) -> tuple[bd.AdaptadorDoBluez, ...] | None:
        self.fotos += 1
        self.solta.wait(5)
        return (bd.AdaptadorDoBluez("/org/bluez/hci8", "hci8", QUARTO),)


def test_pelo_caminho_de_reserva_o_tique_nao_espera_a_foto(diario: Path) -> None:
    """Sem o dono vivo, a foto dos adaptadores se refaz num fio; o tique segue."""
    lento = _LeitorLento()
    central = cr.CentralDoRadio(dono=lento, sysfs={"listar": lambda _p: [], "raiz": "/x"})
    antes = time.monotonic()

    central.publicar([])

    assert time.monotonic() - antes < 1.0, "o tique esperou a foto do rádio"
    lento.solta.set()
    assert _esperar(lambda: central._adaptadores_em_cache is not None)
    assert lento.fotos == 1


def _esperar(condicao: Any, teto: float = 3.0) -> bool:
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


def test_sob_a_suite_o_esquecer_nao_chama_a_ponte_de_verdade(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire a guarda da suíte do ``esquecer_pela_ponte`` — o pedido"""
    pedidos: list[Any] = []

    def correr(pedido: Any) -> tuple[int, str]:
        pedidos.append(pedido)
        return 0, ""

    monkeypatch.setattr(cr, "_correr_a_ponte", correr)

    fez, motivo = cr.esquecer_pela_ponte(SALA, VERMELHO)

    assert fez is False and "suíte" in motivo
    assert pedidos == []


def test_sob_a_suite_a_janela_pela_ponte_nao_chama_sudo(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem o dono vivo, a janela da central é a da ponte (``sudo … descobrir``)."""
    from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp

    pedidos: list[Any] = []

    def abrir(pedido: Any) -> Any:
        pedidos.append(pedido)
        raise OSError("dublê: nada roda")

    monkeypatch.setattr(gp, "_abrir_de_verdade", abrir)
    leitor = bd.pelo_executor(lambda _argumentos: None)
    assert leitor.atende_o_proprio_pareamento is False
    assert cr.CentralDoRadio()._abrir_janela is cr._janela_de_busca

    janela = cr._janela_de_busca(QUARTO, 30, leitor)

    assert janela.abrir_a_janela(), "a janela da ponte abriu sob a suíte"
    assert pedidos == []
