"""apelido_do_dongle.py — dar nome a cada dongle sem derrubar o Pro Controller.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

Ela tem TRÊS adaptadores Bluetooth ``2357:0604``, todos atrás do mesmo hub.
Idênticos no barramento e no ``lsusb``. A única coisa que os separa é o BD
Address, e endereço não é nome: ninguém olha para ``AC:A7:F1:...`` e sabe qual
é o do sofá.

E **o modelo deles não é uma pergunta que o barramento responda** — MEDIDO em
22/08/2026, e é por isso que a frase acima não diz "UB500"::

    3-3.1.1   2357:0604  bcdDevice=0200  product="TP-Link UB500 Adapter"
    3-3.1.4   2357:0604  bcdDevice=0200  product="TP-Link Bluetooth USB Adapter"
    3-3.2     2357:0604  bcdDevice=0200  product="TP-Link UB500 Adapter"

O ``vid:pid`` NÃO distingue: UB500, UB5A e UB500 Plus são os três
``2357:0604``, com o mesmo chip RTL8761BUV, e aqui nem o ``bcdDevice`` os
separa. O único campo que varia é o ``product``, e ele é frágil: três unidades
da mesma bancada devolvem DUAS strings diferentes, e há na natureza uma
terceira com erro de digitação de fábrica (``TP-Lifk UB5A Adapter``).

**Consequência que precisa estar escrita:** nenhuma regra de udev, linha do
mapa de canais ou caminho de decisão deste produto pode depender de distinguir
modelo de dongle TP-Link. Não dá. O que identifica um adaptador aqui é o BD
Address; o que ela lê na tela é o apelido que ela mesma escreveu. É a mesma
recusa do ``censo_do_barramento`` a heurística por ``product`` — adivinhar por
texto é como se erra com confiança.

O BlueZ já guarda um nome por adaptador — ``org.bluez.Adapter1.Alias`` — e o
grava em ``/var/lib/bluetooth/<endereço>/settings``, então ele sobrevive a
reboot. Faltava o produto deixá-la escrever ali.

A ARMADILHA, E ELA É O CORAÇÃO DESTE MÓDULO
--------------------------------------------

O prefixo ``Nintendo`` nesse nome **não é enfeite**. O Pro Controller LÊ o nome
Bluetooth do host e, se ele não começar com ``Nintendo``, cai num modo de sniff
frágil que não manda keepalive — sob rumble e IMU os relatórios enfileiram e o
controle DESCONECTA. É a metade (1) do ``BT-NINTENDO-ACTIVE-01``, pesquisa de
22/07/2026, com três fontes independentes, e é o que
``scripts/bt_active_mode.sh:137-149`` aplica.

Renomear um adaptador que hospeda um Pro sem manter o prefixo derruba o Pro. Por
isso a decisão dela (22/08/2026) é: *"você escreve, o produto protege o
prefixo"*. O nome que a TELA mostra é o dela, limpo; o que vai ao BlueZ é o
costurado. Ela nunca precisa saber que a costura existe.

POR QUE PREFIXO, E NÃO SUFIXO — três razões, nenhuma delas de gosto
--------------------------------------------------------------------

1. **O firmware do Pro casa o COMEÇO do nome.** A verificação é ``Nintendo*``,
   literalmente o glob de ``bt_active_mode.sh:141``. Sufixo não satisfaz.
2. **O BlueZ corta pela CAUDA.** Medido nesta bancada em 22/08/2026, BlueZ 5.86:
   um alias de 300 caracteres ASCII volta com 247 — ele trunca, e o que
   desaparece é o fim. Um sufixo protetor sumiria calado justamente nos nomes
   longos; um prefixo sobrevive ao corte.
3. **Já existe outro escritor.** O ``bt_active_mode.sh`` escreve
   ``"Nintendo ${alias}"``. Qualquer outra forma faria os dois brigarem: o
   script re-prefixaria o que este módulo tivesse sufixado, e o nome cresceria
   a cada boot.

O TETO DO ALIAS, MEDIDO — e por que o produto trunca antes do BlueZ
--------------------------------------------------------------------

Nesta bancada, em 22/08/2026, BlueZ 5.86, como uid 1000::

    300 x "N"  (300 bytes)  -> aceito, volta com 247 caracteres
    123 x "á"  (246 bytes)  -> aceito inteiro
    124 x "á"  (248 bytes)  -> RECUSADO: "Invalid arguments in method call"

Uma regra só explica os três: **o teto é de 247 BYTES, o BlueZ trunca sozinho
e, quando o corte cai no meio de um caractere multibyte, a chamada inteira é
recusada.** Nome dela tem acento — "Sofá", "Salão" —, então deixar o BlueZ
truncar é deixar o salvamento falhar sem motivo visível. :func:`costurar_o_nome`
corta antes, sempre em fronteira de caractere, e sempre pela cauda: o prefixo
nunca é o sacrificado.

A ESCRITA NÃO PRECISA DE PRIVILÉGIO — medido, não suposto
----------------------------------------------------------

22/08/2026, nesta máquina: ``busctl set-property`` do ``Alias`` devolve ``0``
como uid 1000 **e também como ``nobody``**, um usuário sem sessão e sem assento.
A política do BlueZ em ``/usr/share/dbus-1/system.d/bluetooth.conf`` tem
``<policy context="default"><allow send_destination="org.bluez"/>``, e o
``Alias`` não passa por polkit. **Não há helper privilegiado a pedir aqui.**

O ponto de injeção ``executar`` existe assim mesmo, e a razão não é privilégio:
a suíte precisa de um D-Bus dublado. Dentro do Flatpak o barramento de sistema
chega pelo ``--system-talk-name=org.bluez`` do manifesto
(``flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml``,
O-FLATPAK-ALCANCA-O-BLUEZ-01), e a leitura e a escrita do ``Alias`` saem pelo
mesmo dono do BlueZ que fora dele.

**A escrita é ASSÍNCRONA.** Medido: ler a propriedade imediatamente depois de
escrever devolve o valor ANTIGO; um segundo depois, o novo. Quem quiser conferir
o que gravou tem de esperar — este módulo não confere, ele reporta o que o
``set-property`` respondeu.

O QUE ELE NÃO É
----------------

Não desenha tela: quem monta a seção da aba é outra camada, e este módulo é
puro o bastante para rodar sem GTK.

Não mexe em link policy. A metade (2) do ``BT-NINTENDO-ACTIVE-01`` — o no-sniff
por dispositivo — é do ``bt_active_mode.sh``, precisa de root e de ``hcitool``,
e é POR CONTROLE, não por adaptador. Aqui só a metade (1), a do nome, que é a
que sai sem privilégio nenhum.

Não usa ``hciN`` como identidade em lugar nenhum. O índice inverte entre boots
(``docs/usage/bluetooth-varios-adaptadores.md`` §3.1, e a cicatriz do
``bt_health_watchdog.sh``), e
por isso o caminho ``/org/bluez/hciN`` é resolvido a cada leitura a partir do
BD Address, nunca guardado.

Nunca SUBTRAI. Se um adaptador carrega o prefixo e não hospeda Nintendo nenhum,
o prefixo fica: tirar uma palavra que ela escreveu é pior que deixar uma palavra
que não faz nada. Ver :func:`limpar_o_nome`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.core.linhagem_nintendo import (
    NOMES_LINHAGEM,
    OUIS_LINHAGEM_COM_DOIS_PONTOS,
    _e_da_linhagem_nintendo,
)
from hefesto_dualsense4unix.integrations import bluez_dbus

#: de ``scripts/bt_active_mode.sh:142`` — os dois escritores têm de produzir a
PREFIXO_NINTENDO = "Nintendo"

TETO_DE_BYTES = 247

QUEM = "apelido-do-dongle"

OUIS_NINTENDO = OUIS_LINHAGEM_COM_DOIS_PONTOS

#: NÃO casa ``"DualSense Wireless Controller"``, e não casa ``"8BitDo Pro 2"``
NOMES_NINTENDO = NOMES_LINHAGEM

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

_CAMINHO_DE_ADAPTADOR = re.compile(r"/org/bluez/hci[0-9]+")

_MARCA_NOME = "HID_NAME="
_MARCA_PHYS = "HID_PHYS="
_MARCA_UNIQ = "HID_UNIQ="


@dataclass(frozen=True)
class Dongle:
    """Um adaptador Bluetooth pela ótica de quem quer dar nome a ele."""

    endereco: str
    alias: str = ""
    nome_do_sistema: str = ""
    hospeda_nintendo: bool = False
    ligado: bool = False
    objeto: str = ""

    @property
    def nome(self) -> str:
        """O nome DELA — o alias sem a costura do produto."""
        return limpar_o_nome(self.alias, hospeda_nintendo=self.hospeda_nintendo)

    @property
    def protegido(self) -> bool:
        """O alias de hoje já tira o Pro do sniff frágil?"""
        return not self.hospeda_nintendo or self.alias.startswith(PREFIXO_NINTENDO)


@dataclass(frozen=True)
class Renomeacao:
    """O que aconteceu (ou aconteceria) ao renomear um dongle."""

    endereco: str
    nome: str = ""
    alias: str = ""
    costurado: bool = False
    truncado: bool = False
    aplicado: bool = False
    porque: str = ""


def costurar_o_nome(nome: str, *, hospeda_nintendo: bool) -> str:
    """O nome dela vira o alias que vai ao BlueZ."""
    bruto = _alias_sem_tesoura(nome, hospeda_nintendo=hospeda_nintendo)
    intocavel = len(PREFIXO_NINTENDO) if hospeda_nintendo else 0
    return _caber(bruto, intocavel=intocavel)


def _alias_sem_tesoura(nome: str, *, hospeda_nintendo: bool) -> str:
    """A costura ANTES do teto — separada para que se possa dizer se cortou."""
    limpo = nome.strip()
    if not hospeda_nintendo:
        return limpo
    if limpo.startswith(PREFIXO_NINTENDO):
        return limpo
    if not limpo:
        return PREFIXO_NINTENDO
    return f"{PREFIXO_NINTENDO} {limpo}"


def limpar_o_nome(alias: str, *, hospeda_nintendo: bool) -> str:
    """O alias do BlueZ vira o nome dela — o que a tela mostra."""
    texto = alias.strip()
    if not hospeda_nintendo:
        return texto
    if texto.lower() == PREFIXO_NINTENDO.lower():
        return ""
    if not texto.lower().startswith(PREFIXO_NINTENDO.lower()):
        return texto
    resto = texto[len(PREFIXO_NINTENDO) :]
    if not resto[:1].isspace():
        return texto
    return resto.strip()


def _caber(texto: str, *, intocavel: int = 0) -> str:
    """Corta ``texto`` para :data:`TETO_DE_BYTES` bytes, sem partir caractere."""
    bruto = texto.encode("utf-8")
    if len(bruto) <= TETO_DE_BYTES:
        return texto
    cortado = bruto[:TETO_DE_BYTES].decode("utf-8", errors="ignore").rstrip()
    return cortado if cortado else texto[:intocavel]


def adaptadores_com_nintendo(
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> frozenset[str]:
    """Endereços (minúsculos, com ``:``) dos adaptadores que hospedam Nintendo."""
    leitor = _ler_texto if ler is None else ler
    try:
        nos = sorted(listar(raiz))
    except OSError:
        return frozenset()

    achados: set[str] = set()
    for no in nos:
        texto = leitor(os.path.join(raiz, no, "device", "uevent"))
        if not texto:
            continue
        phys = _valor_do_uevent(texto, _MARCA_PHYS).lower()
        if not _MAC_RE.match(phys):
            continue
        if not _e_da_linhagem_nintendo(
            nome=_valor_do_uevent(texto, _MARCA_NOME),
            uniq=_valor_do_uevent(texto, _MARCA_UNIQ),
        ):
            continue
        achados.add(phys)
    return frozenset(achados)


def ler_os_dongles(
    *,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> tuple[Dongle, ...]:
    """Todos os adaptadores, com nome, endereço e quem eles hospedam."""
    leitor = _leitor(executar)
    caminhos = leitor.caminhos()
    if caminhos is None:
        return ()
    com_nintendo = adaptadores_com_nintendo(
        raiz=raiz_hidraw, listar=listar, ler=ler
    )
    achados: list[Dongle] = []
    for caminho in caminhos:
        if not _CAMINHO_DE_ADAPTADOR.fullmatch(caminho):
            continue
        endereco = leitor.endereco_do_adaptador(caminho)
        if not endereco:
            continue
        achados.append(
            Dongle(
                endereco=endereco.upper(),
                alias=_texto(leitor.propriedade(caminho, bluez_dbus.ADAPTADOR, "Alias")),
                nome_do_sistema=_texto(
                    leitor.propriedade(caminho, bluez_dbus.ADAPTADOR, "Name")
                ),
                hospeda_nintendo=endereco.lower() in com_nintendo,
                ligado=bluez_dbus.como_booleano(
                    leitor.propriedade(caminho, bluez_dbus.ADAPTADOR, "Powered")
                ) is True,
                objeto=caminho,
            )
        )
    return tuple(sorted(achados, key=lambda d: d.endereco))


def renomear_o_dongle(
    endereco: str,
    nome: str,
    *,
    dongles: Iterable[Dongle] | None = None,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> Renomeacao:
    """Grava o nome dela num dongle, com a costura do prefixo por cima."""
    tabela = (
        tuple(dongles)
        if dongles is not None
        else ler_os_dongles(
            executar=executar, raiz_hidraw=raiz_hidraw, listar=listar, ler=ler
        )
    )
    alvo = next(
        (d for d in tabela if d.endereco.lower() == endereco.strip().lower()),
        None,
    )
    if alvo is None:
        return Renomeacao(
            endereco=endereco.upper(),
            nome=nome,
            porque="Este adaptador não está mais na mesa.",
        )

    bruto = _alias_sem_tesoura(nome, hospeda_nintendo=alvo.hospeda_nintendo)
    alias = costurar_o_nome(nome, hospeda_nintendo=alvo.hospeda_nintendo)
    costurado = bruto != nome.strip()
    truncado = alias != bruto
    if not alvo.objeto:
        return Renomeacao(
            endereco=alvo.endereco,
            nome=nome,
            alias=alias,
            costurado=costurado,
            truncado=truncado,
            porque="Não achei este adaptador no Bluetooth do sistema.",
        )
    escrita = _leitor(executar).escrever_alias(alvo.objeto, alias, quem=QUEM)
    if not escrita.feita:
        return Renomeacao(
            endereco=alvo.endereco,
            nome=nome,
            alias=alias,
            costurado=costurado,
            truncado=truncado,
            porque=(
                "O rádio estava ocupado com outro gesto; tente de novo."
                if escrita.erro == bluez_dbus.TRAVA_OCUPADA
                else "O Bluetooth do sistema recusou o nome novo."
            ),
        )
    return Renomeacao(
        endereco=alvo.endereco,
        nome=nome,
        alias=alias,
        costurado=costurado,
        truncado=truncado,
        aplicado=True,
    )


def costurar_a_mesa(
    *,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> tuple[Renomeacao, ...]:
    """O passe de reparo: põe o prefixo em TODO adaptador que hospeda Nintendo."""
    tabela = ler_os_dongles(
        executar=executar, raiz_hidraw=raiz_hidraw, listar=listar, ler=ler
    )
    feitos: list[Renomeacao] = []
    for dongle in tabela:
        if dongle.protegido:
            continue
        feitos.append(
            renomear_o_dongle(
                dongle.endereco,
                dongle.nome,
                dongles=tabela,
                executar=executar,
            )
        )
    return tuple(feitos)


def _leitor(
    executar: Callable[[Sequence[str]], str | None] | None,
) -> bluez_dbus.LeitorDoBluez:
    """O dono do BlueZ (BLUEZ-UM-DONO-01), ou um sobre o dublê de quem injetou."""
    return bluez_dbus.dono() if executar is None else bluez_dbus.pelo_executor(executar)


def _texto(valor: object) -> str:
    """O valor de uma propriedade de texto, ou ``""`` quando ela não respondeu."""
    return valor if isinstance(valor, str) else ""


def _valor_do_uevent(texto: str, marca: str) -> str:
    """O valor de uma chave do uevent — "" quando o nó não a declara."""
    for linha in texto.splitlines():
        if linha.startswith(marca):
            return linha[len(marca) :].strip()
    return ""


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "NOMES_NINTENDO",
    "OUIS_NINTENDO",
    "PREFIXO_NINTENDO",
    "TETO_DE_BYTES",
    "Dongle",
    "Renomeacao",
    "adaptadores_com_nintendo",
    "costurar_a_mesa",
    "costurar_o_nome",
    "ler_os_dongles",
    "limpar_o_nome",
    "renomear_o_dongle",
]
