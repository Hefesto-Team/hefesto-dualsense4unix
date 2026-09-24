"""A entrada do computador não repete o nome — STORM-USB-02, 24/09/2026.

Sem nome dado por ela e sem número no desenho, a porta se chama pelo
``devpath`` («Entrada 4.1.4», o desenho aprovado). Mas a entrada do PRÓPRIO
computador é um ``devpath`` de um número só, e cada hub-raiz numera as dele a
partir de 1: na mesa dela, com dois controladores USB, o ``1-4`` (o adaptador
do rádio) e o ``3-4`` (o hub) saíam os dois «Entrada 4» — no doctor e na seção
do rádio. O dono do nome (``entrada_a_entrada``) desempata: numa máquina com
mais de um controlador, a entrada do computador leva o barramento.

AS MORDIDAS (arranque a cura, veja reprovar, devolva):

* :func:`test_as_duas_entradas_4_nao_se_chamam_igual` — volte o
  ``_rotulo_de_reserva`` a ``rotulo_do_numero(devpath)``;
* :func:`test_o_doctor_diz_o_nome_uma_vez_so` — tire a guarda do
  ``Aparelho.onde``, e a frase sai «Entrada 3-4 (3-4)».

Controladores PCI forjados (``0000:0a``/``0000:0b``); nada lê o ``/sys`` dela.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.exame_da_mesa import storm_por_porta
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

PCI_DO_RADIO = "0000:0b:00.0"
PCI_DO_HUB = "0000:0a:00.0"
#: A mesa dela: dois controladores, cada um com o lado 2.0 e o 3.x.
DOIS = {1: PCI_DO_RADIO, 2: PCI_DO_RADIO, 3: PCI_DO_HUB, 4: PCI_DO_HUB}
UM = {3: PCI_DO_HUB, 4: PCI_DO_HUB}
VAZIA = MaquinaConfig()


def test_as_duas_entradas_4_nao_se_chamam_igual() -> None:
    """Pelas duas chaves da casa — o caminho e o lugar — e pelos dois leitores."""
    assert ee.nome_da_porta("1-4", maquina=VAZIA, controladores=DOIS) == "Entrada 1-4"
    assert ee.nome_da_porta("3-4", maquina=VAZIA, controladores=DOIS) == "Entrada 3-4"
    assert ee.nome_da_porta(f"pci-{PCI_DO_RADIO}-usb-0:4", maquina=VAZIA, controladores=DOIS) == (
        "Entrada 1-4"
    )
    # A seção do rádio pergunta por aqui (`a08_conexoes`, o rótulo da face).
    rotulo = ee.rotulo_da_entrada
    assert rotulo(f"pci-{PCI_DO_HUB}-usb-0:4", maquina=VAZIA, controladores=DOIS) == "Entrada 3-4"
    assert rotulo(f"pci-{PCI_DO_RADIO}-usb-0:4", maquina=VAZIA, controladores=DOIS) == (
        "Entrada 1-4"
    )


def test_os_dois_lados_da_entrada_usb3_sao_a_mesma_entrada() -> None:
    """O ``4-4`` é o lado 3.x do ``3-4``: o mesmo buraco, o mesmo nome."""
    assert ee.nome_da_porta("4-4", maquina=VAZIA, controladores=DOIS) == "Entrada 3-4"


def test_atras_de_um_hub_o_rotulo_e_o_do_desenho() -> None:
    """A cadeia do hub já separa: «Entrada 4.1.4», como o desenho aprovado mostra."""
    assert ee.nome_da_porta("3-4.1.4", maquina=VAZIA, controladores=DOIS) == "Entrada 4.1.4"
    assert ee.rotulo_da_entrada(
        f"pci-{PCI_DO_HUB}-usb-0:4.1.4", maquina=VAZIA, controladores=DOIS
    ) == "Entrada 4.1.4"


def test_com_um_controlador_so_nada_muda() -> None:
    assert ee.nome_da_porta("3-4", maquina=VAZIA, controladores=UM) == "Entrada 4"
    assert ee.rotulo_da_entrada(f"pci-{PCI_DO_HUB}-usb-0:4", maquina=VAZIA, controladores=UM) == (
        "Entrada 4"
    )


def test_o_nome_que_ela_deu_vence_o_desempate() -> None:
    maquina = MaquinaConfig.model_validate(
        {"lugares": {f"pci-{PCI_DO_HUB}-usb-0:4": {"nome": "Frente, a de cima"}}}
    )
    assert ee.nome_da_porta("3-4", maquina=maquina, controladores=DOIS) == "Frente, a de cima"


def _raiz_com_dois_controladores(tmp_path: Path) -> Path:
    raiz = tmp_path / "sys" / "bus" / "usb" / "devices"
    raiz.mkdir(parents=True)
    for bus, pci in DOIS.items():
        alvo = tmp_path / "sys" / "devices" / "pci0000:00" / pci / f"usb{bus}"
        alvo.mkdir(parents=True)
        os.symlink(alvo, raiz / f"usb{bus}")
    return raiz


def test_o_doctor_diz_o_nome_uma_vez_so(tmp_path: Path) -> None:
    """O doctor nomeia as duas entradas 4, e o nome que já é o caminho não se repete."""
    linhas = [
        "2026-09-24T12:55:51-03:00 [USB-71] usb 1-4: device descriptor read/64, error -71",
        "2026-09-24T12:55:52-03:00 [USB-71] usb 3-4: device descriptor read/64, error -71",
        "2026-09-24T12:55:53-03:00 [USB-71] usb 3-4.1.3: device descriptor read/64, error -71",
    ]
    laudo = storm_por_porta(
        linhas=linhas,
        hoje=datetime.date(2026, 9, 24),
        raiz_usb=_raiz_com_dois_controladores(tmp_path),
    )
    porque = {p.porta: p.porque for p in laudo.portas}
    assert porque["1-4"].startswith("Entrada 1-4 — 1 evento"), porque["1-4"]
    assert porque["3-4"].startswith("Entrada 3-4 — 1 evento"), porque["3-4"]
    assert porque["3-4.1.3"].startswith("Entrada 4.1.3 (3-4.1.3) — 1 evento"), porque["3-4.1.3"]
    assert all("Entrada 3-4 (3-4)" not in frase for frase in porque.values()), porque
