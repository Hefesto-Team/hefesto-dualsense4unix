"""A bancada de mentira das ordens de serviço — nenhum caminho de `/sys` real."""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    Energia,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada

RAIZ = "/mentira/devices/pci0000:00"

PCI_DA_PLACA = "0000:aa:00.0"
PCI_DO_HUB = "0000:bb:00.3"

SERIAL_DO_DONGLE_INTERNO = "d0f1a2b3c4d5"
SERIAL_DO_DONGLE_EXTERNO = "d0f1a2b3c4e6"
SERIAL_DO_LARGO = "123456"
SERIAL_DO_TECLADO = "f7e6d5c4b3a2"


def aparelho(
    nome: str,
    *,
    pai: str = "",
    classe: str = "",
    subclasse: str = "",
    protocolo: str = "",
    vid: str = "",
    pid: str = "",
    velocidade: float = 480.0,
    busnum: int = 0,
    devpath: str = "",
    pci: str = "",
    e_hub: bool = False,
    e_raiz: bool = False,
    atras_de_hub: bool = False,
    controle: str = "on",
    excesso: int | None = 0,
    produto: str = "",
) -> Aparelho:
    """Um `Aparelho` do censo, com o `no` derivado do nome do kernel."""
    return Aparelho(
        no=f"{RAIZ}/{nome}",
        nome_do_kernel=nome,
        vid=vid,
        pid=pid,
        produto=produto,
        velocidade_mbps=velocidade,
        busnum=busnum,
        devpath=devpath,
        pai=f"{RAIZ}/{pai}" if pai else "",
        controlador_pci=pci,
        classe=classe,
        subclasse=subclasse,
        protocolo=protocolo,
        e_hub=e_hub,
        e_raiz=e_raiz,
        atras_de_hub=atras_de_hub,
        energia=Energia(controle=controle, excesso_de_corrente=excesso),
    )


def no_de_entrada(
    nome: str,
    *,
    hub: str,
    numero: int,
    estado: str = "not attached",
    encaixe: str = "hotplug",
    par: str = "",
    dispositivo: str = "",
) -> NoDeEntrada:
    """Um nó de entrada do `/sys`, já com o `peer` e o `device` resolvidos."""
    return NoDeEntrada(
        no=nome,
        caminho_sysfs=f"{RAIZ}/{hub}/{nome}",
        hub=hub,
        numero=numero,
        estado=estado,
        tipo_de_encaixe=encaixe,
        par=par,
        aparelho=dispositivo,
    )


APARELHOS = (
    aparelho("usb1", busnum=1, devpath="0", pci=PCI_DA_PLACA, e_hub=True, e_raiz=True,
             classe="09", vid="1d6b", pid="0002"),
    aparelho("usb2", busnum=2, devpath="0", pci=PCI_DA_PLACA, e_hub=True, e_raiz=True,
             classe="09", vid="1d6b", pid="0003", velocidade=10000.0),
    aparelho("usb3", busnum=3, devpath="0", pci=PCI_DO_HUB, e_hub=True, e_raiz=True,
             classe="09", vid="1d6b", pid="0002"),
    aparelho("3-1", pai="usb3", busnum=3, devpath="1", pci=PCI_DO_HUB, e_hub=True,
             classe="09", vid="05e3", pid="0610", produto="USB2.1 Hub"),
    aparelho("3-1.1", pai="3-1", busnum=3, devpath="1.1", pci=PCI_DO_HUB, e_hub=True,
             atras_de_hub=True, classe="09", vid="05e3", pid="0610"),
    aparelho("3-1.1.4", pai="3-1.1", busnum=3, devpath="1.1.4", pci=PCI_DO_HUB,
             atras_de_hub=True, classe="e0", subclasse="01", protocolo="01",
             vid="2357", pid="0604", produto="TP-Link Bluetooth USB Adapter"),
    aparelho("3-1.2", pai="3-1", busnum=3, devpath="1.2", pci=PCI_DO_HUB,
             atras_de_hub=True, classe="e0", subclasse="01", protocolo="01",
             vid="2357", pid="0604", produto="TP-Link UB500 Adapter"),
    aparelho("3-1.4", pai="3-1", busnum=3, devpath="1.4", pci=PCI_DO_HUB,
             atras_de_hub=True, classe="03", subclasse="01", protocolo="01",
             vid="3554", pid="fa09", produto="Teclado"),
    aparelho("usb4", busnum=4, devpath="0", pci=PCI_DO_HUB, e_hub=True, e_raiz=True,
             classe="09", vid="1d6b", pid="0003", velocidade=10000.0),
    aparelho("4-1", pai="usb4", busnum=4, devpath="1", pci=PCI_DO_HUB, e_hub=True,
             classe="09", vid="05e3", pid="0610", velocidade=5000.0),
    aparelho("4-1.1", pai="4-1", busnum=4, devpath="1.1", pci=PCI_DO_HUB, e_hub=True,
             atras_de_hub=True, classe="09", vid="05e3", pid="0610", velocidade=5000.0),
    aparelho("4-1.1.2", pai="4-1.1", busnum=4, devpath="1.1.2", pci=PCI_DO_HUB,
             atras_de_hub=True, classe="ff", subclasse="ff", protocolo="ff",
             vid="2357", pid="012d", velocidade=5000.0, produto="802.11ac NIC"),
)

ENTRADAS = (
    no_de_entrada("usb1-port1", hub="usb1", numero=1),
    no_de_entrada("usb1-port2", hub="usb1", numero=2),
    no_de_entrada("usb1-port3", hub="usb1", numero=3, par="usb2-port1"),
    no_de_entrada("usb2-port1", hub="usb2", numero=1, par="usb1-port3"),
    no_de_entrada("usb1-port4", hub="usb1", numero=4, par="usb2-port2"),
    no_de_entrada("usb2-port2", hub="usb2", numero=2, par="usb1-port4"),
    no_de_entrada("usb3-port1", hub="usb3", numero=1, estado="configured",
                  encaixe="unknown", par="usb4-port1", dispositivo="3-1"),
    no_de_entrada("usb4-port1", hub="usb4", numero=1, estado="configured",
                  encaixe="unknown", par="usb3-port1", dispositivo="4-1"),
    no_de_entrada("3-1-port1", hub="3-1", numero=1, estado="configured",
                  encaixe="unknown", par="4-1-port1", dispositivo="3-1.1"),
    no_de_entrada("4-1-port1", hub="4-1", numero=1, estado="configured",
                  encaixe="unknown", par="3-1-port1", dispositivo="4-1.1"),
    no_de_entrada("3-1-port2", hub="3-1", numero=2, estado="configured",
                  encaixe="unknown", par="4-1-port2", dispositivo="3-1.2"),
    no_de_entrada("4-1-port2", hub="4-1", numero=2, encaixe="unknown",
                  par="3-1-port2"),
    no_de_entrada("3-1-port3", hub="3-1", numero=3, encaixe="unknown",
                  par="4-1-port3"),
    no_de_entrada("4-1-port3", hub="4-1", numero=3, encaixe="unknown",
                  par="3-1-port3"),
    no_de_entrada("3-1-port4", hub="3-1", numero=4, estado="configured",
                  encaixe="unknown", par="4-1-port4", dispositivo="3-1.4"),
    no_de_entrada("4-1-port4", hub="4-1", numero=4, encaixe="unknown",
                  par="3-1-port4"),
    no_de_entrada("3-1.1-port2", hub="3-1.1", numero=2, encaixe="unknown",
                  par="4-1.1-port2"),
    no_de_entrada("4-1.1-port2", hub="4-1.1", numero=2, estado="configured",
                  encaixe="unknown", par="3-1.1-port2", dispositivo="4-1.1.2"),
    no_de_entrada("3-1.1-port4", hub="3-1.1", numero=4, estado="configured",
                  encaixe="unknown", par="4-1.1-port4", dispositivo="3-1.1.4"),
    no_de_entrada("4-1.1-port4", hub="4-1.1", numero=4, encaixe="unknown",
                  par="3-1.1-port4"),
)

SERIAIS = {
    f"{RAIZ}/3-1.1.4": SERIAL_DO_DONGLE_INTERNO,
    f"{RAIZ}/3-1.2": SERIAL_DO_DONGLE_EXTERNO,
    f"{RAIZ}/4-1.1.2": SERIAL_DO_LARGO,
    f"{RAIZ}/3-1.4": SERIAL_DO_TECLADO,
}


def ler_serial(no: str) -> str:
    """O dublê de leitura de serial — devolve `""` para quem não tem."""
    return SERIAIS.get(no, "")


def censo(*, sem: tuple[str, ...] = (), mais: tuple[Aparelho, ...] = ()) -> Censo:
    """A bancada inteira, opcionalmente sem alguns nós e com outros a mais."""
    return Censo(
        aparelhos=tuple(a for a in APARELHOS if a.nome_do_kernel not in sem) + mais
    )


def entradas(*, sem: tuple[str, ...] = ()) -> tuple[NoDeEntrada, ...]:
    """Os nós de entrada, opcionalmente sem alguns."""
    return tuple(e for e in ENTRADAS if e.no not in sem)


NOS_LIVRES = (
    "usb1-port1",
    "usb1-port2",
    "usb1-port3",
    "usb2-port1",
    "usb1-port4",
    "usb2-port2",
)


def bancada_do_hub_em_numeros_diferentes() -> tuple[Censo, tuple[NoDeEntrada, ...]]:
    """Um hub num buraco cujos dois lados têm NÚMEROS diferentes."""
    aparelhos = (
        aparelho("usb1", busnum=1, devpath="0", pci=PCI_DA_PLACA, e_hub=True,
                 e_raiz=True, classe="09", vid="1d6b", pid="0002"),
        aparelho("usb2", busnum=2, devpath="0", pci=PCI_DA_PLACA, e_hub=True,
                 e_raiz=True, classe="09", vid="1d6b", pid="0003",
                 velocidade=10000.0),
        aparelho("1-3", pai="usb1", busnum=1, devpath="3", pci=PCI_DA_PLACA,
                 e_hub=True, classe="09", vid="05e3", pid="0610"),
        aparelho("2-1", pai="usb2", busnum=2, devpath="1", pci=PCI_DA_PLACA,
                 e_hub=True, classe="09", vid="05e3", pid="0610",
                 velocidade=5000.0),
        aparelho("1-3.1", pai="1-3", busnum=1, devpath="3.1", pci=PCI_DA_PLACA,
                 atras_de_hub=True, classe="e0", subclasse="01", protocolo="01",
                 vid="2357", pid="0604"),
        aparelho("2-1.2", pai="2-1", busnum=2, devpath="1.2", pci=PCI_DA_PLACA,
                 atras_de_hub=True, classe="ff", subclasse="ff", protocolo="ff",
                 vid="2357", pid="012d", velocidade=5000.0),
    )
    nos = (
        no_de_entrada("usb1-port3", hub="usb1", numero=3, estado="configured",
                      par="usb2-port1", dispositivo="1-3"),
        no_de_entrada("usb2-port1", hub="usb2", numero=1, estado="configured",
                      par="usb1-port3", dispositivo="2-1"),
        no_de_entrada("1-3-port1", hub="1-3", numero=1, estado="configured",
                      encaixe="unknown", par="2-1-port1", dispositivo="1-3.1"),
        no_de_entrada("2-1-port1", hub="2-1", numero=1, encaixe="unknown",
                      par="1-3-port1"),
        no_de_entrada("1-3-port2", hub="1-3", numero=2, encaixe="unknown",
                      par="2-1-port2"),
        no_de_entrada("2-1-port2", hub="2-1", numero=2, estado="configured",
                      encaixe="unknown", par="1-3-port2", dispositivo="2-1.2"),
    )
    return Censo(aparelhos=aparelhos), nos
