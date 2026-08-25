"""A bancada de mentira das ordens de serviço — nenhum caminho de `/sys` real.

Copiada da MEDIÇÃO desta casa em 24/08/2026, com os `vid:pid` de MODELO (que são
públicos), seriais sintéticos e caminhos `/mentira`. O arranjo que ela reproduz é
o que a sprint mediu e que a régua antiga não via::

    usb1  (PCI 0000:aa:00.0)  hub-raiz 2.0 — a placa
    usb2  (PCI 0000:aa:00.0)  hub-raiz 3.0 — o outro lado dos mesmos buracos
    usb3  (PCI 0000:bb:00.3)  hub-raiz 2.0
      3-1        05e3:0610  hub externo, lado 2.0
        3-1.1    05e3:0610  hub interno, lado 2.0
          3-1.1.4  2357:0604  e0/01/01  Bluetooth
        3-1.2    2357:0604  e0/01/01  Bluetooth
        3-1.4    3554:fa09  03/01/01  teclado — o único da casa
    usb4  (PCI 0000:bb:00.3)  hub-raiz 3.0
      4-1        05e3:0610  hub externo, lado 3.0
        4-1.1    05e3:0610  hub interno, lado 3.0
          4-1.1.2  2357:012d  ff/ff/ff  5 Gbps, o kernel NÃO nomeia

**O `4-1.1.2` e o `3-1.1.4` estão no MESMO chip de hub** — o `4-1.1` e o `3-1.1`
são os dois lados do mesmo plástico. `mesa_de_radio.vizinhancas_apertadas` recusa
o par no corte por `busnum`, e é por isso que R1 precisa de
`ordens_da_mesa.mesmo_hub_fisico`.

POR QUE NÃO HÁ ÁRVORE DE ARQUIVOS AQUI
---------------------------------------

Nenhuma função deste arquivo cria diretório nem lê ``/sys``. As regras de
`ordens_da_mesa` são puras sobre um `Censo` e uma lista de `NoDeEntrada`, e os
dois são dataclasses: montá-los à mão testa a REGRA em vez de testar o leitor de
sysfs, que já tem bateria própria (`test_o_censo_le_o_barramento_inteiro.py` e
`test_entradas_do_gabinete.py`).

NENHUM SERIAL DESTA BANCADA É REAL. Os quatro são sintéticos e ficam **fora** da
faixa `aabbcc…`, que tem portão próprio — a faixa de teste desta casa não pode
ser usada onde o assunto é justamente "o serial identifica a unidade dela".
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    Energia,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada

RAIZ = "/mentira/devices/pci0000:00"

#: As duas controladoras xHCI. A da placa hospeda `usb1`/`usb2`; a do hub
#: externo hospeda `usb3`/`usb4`. É a diferença entre elas que autoriza R3 a
#: oferecer um destino.
PCI_DA_PLACA = "0000:aa:00.0"
PCI_DO_HUB = "0000:bb:00.3"

#: Seriais sintéticos, fora da faixa `aabbcc…`. Os dois dongles têm o MESMO
#: `vid:pid` e seriais diferentes: é assim que a tripla os separa.
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


#: Os aparelhos da bancada, na ordem do barramento.
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

#: Quatro buracos livres na PLACA — dois nós cada, amarrados pelo `peer`. São o
#: destino que R1 e R3 podem oferecer, porque estão noutra controladora.
ENTRADAS = (
    no_de_entrada("usb1-port1", hub="usb1", numero=1, par="usb2-port1"),
    no_de_entrada("usb1-port2", hub="usb1", numero=2, par="usb2-port2"),
    no_de_entrada("usb1-port3", hub="usb1", numero=3, par="usb2-port3"),
    no_de_entrada("usb1-port4", hub="usb1", numero=4, par="usb2-port4"),
    no_de_entrada("usb2-port1", hub="usb2", numero=1, par="usb1-port1"),
    no_de_entrada("usb2-port2", hub="usb2", numero=2, par="usb1-port2"),
    no_de_entrada("usb2-port3", hub="usb2", numero=3, par="usb1-port3"),
    no_de_entrada("usb2-port4", hub="usb2", numero=4, par="usb1-port4"),
    # As do hub externo estão OCUPADAS — e é por isso que R3 tem o que dizer.
    no_de_entrada("usb3-port1", hub="usb3", numero=1, estado="configured",
                  dispositivo="3-1"),
    no_de_entrada("3-1-port2", hub="3-1", numero=2, estado="configured",
                  encaixe="unknown", dispositivo="3-1.2"),
    no_de_entrada("3-1-port4", hub="3-1", numero=4, estado="configured",
                  encaixe="unknown", dispositivo="3-1.4"),
    no_de_entrada("3-1.1-port4", hub="3-1.1", numero=4, estado="configured",
                  encaixe="unknown", dispositivo="3-1.1.4"),
    no_de_entrada("4-1.1-port2", hub="4-1.1", numero=2, estado="configured",
                  encaixe="unknown", dispositivo="4-1.1.2"),
)

#: O serial de cada nó — o dublê que `identidades` recebe. Ele NÃO sobrevive à
#: função, e é isso que um dos testes afirma.
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


#: Os oito nós que formam os quatro buracos livres da placa. Tirá-los todos é
#: como se mede "não há entrada livre nenhuma".
NOS_LIVRES = tuple(f"usb{lado}-port{n}" for lado in (1, 2) for n in range(1, 5))
