"""As ordens só mandam mover o que a mão alcança, e o teclado da máquina conta como teclado.

D-2511-AS-ORDENS-SO-MANDAM-MOVER-O-QUE-A-MAO-ALCANCA (25/11/2026). O censo lê o encaixe da porta
(``port/connect_type``) e o ``removable`` de cada aparelho; R1, R3 e R6 só mandam mover alvo que
não é soldado, e o soldado vira nota sem ação. A R4 só diz «único» se nenhum teclado, USB soldado
ou de outro barramento de entrada, vive fora do hub. TUDO É DE MENTIRA: o ``/sys`` mora em
``tmp_path`` e as entradas do kernel entram por texto forjado.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    ler_o_barramento,
)
from tests.fixtures.cadeia_usb.montar import SysDeMentira
from tests.unit import ensaio_das_ordens as ensaio

_LETRAS = (*range(16, 26), *range(30, 39), *range(44, 51))
_MAPA_DE_TECLADO = format(sum(1 << bit for bit in _LETRAS), "x")


def _bloco(barramento: str, nome: str, sysfs: str, teclas: str) -> str:
    return (
        f"I: Bus={barramento} Vendor=0001 Product=0001 Version=0001\n"
        f'N: Name="{nome}"\n'
        f"S: Sysfs={sysfs}\n"
        "B: PROP=0\n"
        f"B: KEY={teclas}\n"
    )


def _entradas_do_kernel(*blocos: str) -> str:
    return "\n".join(blocos)


I8042 = _bloco("0011", "teclado de mentira", "/devices/platform/i8042/serio0/input/input3",
               _MAPA_DE_TECLADO)
BLUETOOTH = _bloco("0005", "teclado sem fio de mentira",
                   "/devices/pci0000:00/bluetooth/hci0/0005.0001/input/input9", _MAPA_DE_TECLADO)
BOTAO_DE_LIGAR = _bloco("0019", "botao de ligar", "/devices/LNXSYSTM:00/input/input0",
                        "10000000000000")
TECLADO_USB = _bloco("0003", "teclado usb de mentira", "/devices/pci0000:00/usb1/1-4/input/input5",
                     _MAPA_DE_TECLADO)
TECLADO_VIRTUAL = _bloco("0006", "teclado emulado", "/devices/virtual/input/input11",
                         _MAPA_DE_TECLADO)


def _soldar(censo: Censo, *nomes: str, **campos: Any) -> Censo:
    return dataclasses.replace(
        censo,
        aparelhos=tuple(
            dataclasses.replace(a, **campos) if a.nome_do_kernel in nomes else a
            for a in censo.aparelhos
        ),
    )


def _leitura(censo: Censo) -> ordens.Leitura:
    return ordens.Leitura(censo=censo, entradas=ensaio.entradas())


def _com_excesso_de_corrente(censo: Censo, nome: str, **campos: Any) -> Censo:
    def trocado(a: Aparelho) -> Aparelho:
        energia = dataclasses.replace(a.energia, excesso_de_corrente=2)
        return dataclasses.replace(a, energia=energia, **campos)

    return dataclasses.replace(
        censo,
        aparelhos=tuple(trocado(a) if a.nome_do_kernel == nome else a for a in censo.aparelhos),
    )


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path)


def test_o_censo_le_o_encaixe_e_o_removivel_de_cada_aparelho(sys_usb: SysDeMentira) -> None:
    """O encaixe vem da porta (``port/connect_type``) e o ``removable`` do próprio aparelho."""
    sys_usb.mudar("3-1.1.3", **{"port/connect_type": "hardwired"})
    sys_usb.mudar("3-1.1.2", removable="fixed")
    sys_usb.mudar("3-1.4", **{"port/connect_type": "unknown"}, removable="removable")
    por_nome = {a.nome_do_kernel: a for a in ler_o_barramento(**sys_usb.fontes()).aparelhos}
    assert por_nome["3-1.1.3"].encaixe == "hardwired" and por_nome["3-1.1.3"].soldado
    assert por_nome["3-1.1.2"].removivel == "fixed" and por_nome["3-1.1.2"].soldado
    assert not por_nome["3-1.4"].soldado, "a porta de hub externo não diz o encaixe: não é soldada"
    assert not por_nome["3-1.1.4"].soldado, "campo ilegível não é soldado"


def test_r3_nao_manda_mover_o_adaptador_soldado_atras_do_hub() -> None:
    """Os dois adaptadores BT são soldados, atrás do hub interno: a ordem fica, sem ação."""
    soldado = _soldar(ensaio.censo(), "3-1.1.4", "3-1.2", encaixe="hardwired")
    ordem = ordens.dongle_atras_de_hub(_leitura(soldado))
    assert ordem is not None
    assert ordem.acao == "" and ordem.destino == ""
    assert ordens.SEM_DESTINO not in ordem.ganho_esperado.texto


def test_r3_pelo_removable_fixo_tambem_nao_manda_mover() -> None:
    soldado = _soldar(ensaio.censo(), "3-1.1.4", "3-1.2", removivel="fixed")
    ordem = ordens.dongle_atras_de_hub(_leitura(soldado))
    assert ordem is not None and ordem.acao == ""


def test_r3_manda_mover_o_que_a_mao_alcanca_e_nunca_o_soldado() -> None:
    """Um adaptador soldado e um de encaixe: o alvo é o que a mão alcança, mesmo vindo depois."""
    censo = _soldar(ensaio.censo(), "3-1.1.4", encaixe="hardwired")
    ordem = ordens.dongle_atras_de_hub(_leitura(censo))
    assert ordem is not None
    assert ordem.alvo.caminho == "3-1.2"
    assert ordem.acao.startswith("Leve um dos adaptadores Bluetooth")


def test_r6_nao_manda_mover_a_entrada_soldada_que_reclamou_de_corrente() -> None:
    soldada = _com_excesso_de_corrente(ensaio.censo(), "3-1.2", encaixe="hardwired")
    ordem = ordens.entrada_reclamou_de_corrente(_leitura(soldada))
    assert ordem is not None and ordem.acao == ""
    movel = _com_excesso_de_corrente(ensaio.censo(), "3-1.2", encaixe="hotplug")
    ordem = ordens.entrada_reclamou_de_corrente(_leitura(movel))
    assert ordem is not None and ordem.acao.startswith("Leve esse adaptador")


def test_r1_nao_manda_mover_o_aparelho_largo_soldado() -> None:
    censo = _soldar(ensaio.censo(), "4-1.1.2", encaixe="hardwired")
    ordem = ordens.radio_largo_no_mesmo_hub(_leitura(censo))
    assert ordem is not None and ordem.acao == ""
    movel = ordens.radio_largo_no_mesmo_hub(_leitura(ensaio.censo()))
    assert movel is not None and movel.acao.startswith("Mova ")


def test_r1_manda_mover_o_largo_que_a_mao_alcanca_e_nao_o_soldado_que_veio_antes() -> None:
    outro = ensaio.aparelho(
        "4-1.1.3", pai="4-1.1", busnum=4, devpath="1.1.3", pci=ensaio.PCI_DO_HUB,
        atras_de_hub=True, classe="ff", subclasse="ff", protocolo="ff", vid="2357",
        pid="0130", velocidade=5000.0,
    )
    censo = _soldar(ensaio.censo(mais=(outro,)), "4-1.1.2", encaixe="hardwired")
    ordem = ordens.radio_largo_no_mesmo_hub(_leitura(censo))
    assert ordem is not None
    assert ordem.alvo.caminho == "4-1.1.3"
    assert ordem.acao.startswith("Mova ")


def test_r4_nao_chama_de_unico_o_teclado_quando_o_notebook_tem_o_dele() -> None:
    """Teclado USB só no hub, e um teclado de outro barramento de entrada presente: sem R4."""
    assert ordens.teclado_so_no_hub(_leitura(ensaio.censo())) is not None
    com_o_dele = dataclasses.replace(ensaio.censo(), teclados_fora_do_usb=1)
    assert ordens.teclado_so_no_hub(_leitura(com_o_dele)) is None


def test_r4_nao_manda_tirar_do_hub_o_teclado_soldado() -> None:
    censo = _soldar(ensaio.censo(), "3-1.4", removivel="fixed")
    assert ordens.teclado_so_no_hub(_leitura(censo)) is None


def test_o_censo_conta_o_teclado_de_outro_barramento_e_so_ele(sys_usb: SysDeMentira) -> None:
    """i8042 e Bluetooth contam; botão de ligar, USB e teclado virtual não."""
    entradas = _entradas_do_kernel(BOTAO_DE_LIGAR, TECLADO_USB, TECLADO_VIRTUAL)
    sem = ler_o_barramento(**sys_usb.fontes(), entradas_do_kernel=lambda: entradas)
    assert sem.teclados_fora_do_usb == 0
    com = ler_o_barramento(
        **sys_usb.fontes(),
        entradas_do_kernel=lambda: _entradas_do_kernel(
            BOTAO_DE_LIGAR, I8042, BLUETOOTH, TECLADO_USB
        ),
    )
    assert com.teclados_fora_do_usb == 2


def test_o_censo_de_mentira_nao_le_as_entradas_da_maquina_de_verdade(sys_usb: SysDeMentira) -> None:
    assert ler_o_barramento(**sys_usb.fontes()).teclados_fora_do_usb == 0
