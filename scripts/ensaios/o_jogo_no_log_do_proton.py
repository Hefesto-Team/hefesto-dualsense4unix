#!/usr/bin/env python3
"""o_jogo_no_log_do_proton.py — o nosso vpad atravessou a fronteira do Wine?

O DEGRAU QUE ELE SUSTENTA
--------------------------
`O JOGO RECEBEU`, o primeiro degrau da direção de ENTRADA
(`scripts/check_paridade_transporte.py`, `ESCADA`). Ele é a SEGUNDA régua desse
degrau. A primeira é `o_jogo_segura_o_nosso_no.py`, que casa o **inode** do nó
do vpad contra `/proc/<pid>/fd` — que é o critério escrito do degrau, palavra
por palavra.

POR QUE DUAS RÉGUAS, E NÃO UMA MELHOR
--------------------------------------
Porque portão em série engana (19/08/2026): consertar um deixa o sintoma
idêntico, e uma régua que olha para o lugar errado jura com a mesma cara de
quem olha para o certo. Já aconteceu aqui — o censo do `.vdf` lia a árvore
`apps` morta das três que o arquivo tem e afirmava que o jogo estava são. O que
revelou não foi uma régua mais afiada: foram duas réguas independentes
discordando.

Estas duas são independentes de verdade, e não só "diferentes":

- a do inode olha o **hospedeiro**: `/proc`, `/sys`, `os.stat`. Ela responde
  *"qual nó do kernel está na mão de quem"*;
- esta olha o que o **próprio Wine escreveu sobre si mesmo** enquanto rodava
  dentro do contêiner. Ela responde *"o que o winebus enxergou, o que ele
  registrou no PnP do Windows, e quantos reports ele empurrou pilha acima"*.

Nenhuma das duas lê a saída da outra. Uma pode ficar cega sem que a outra sinta.

AS DUAS ROTAS DE DENTRO DESTE INSTRUMENTO
------------------------------------------
E o mesmo raciocínio, um andar abaixo: este instrumento não confia numa linha
só do log. Ele lê o log por duas rotas que nascem em lados opostos do winebus.

**Rota A — o carimbo, no lado unix.** O winebus imprime, para cada nó que
considera, o `uevent` que o kernel publica::

    00b4:trace:hid:udev_add_device udev "/dev/hidraw5" syspath /sys/devices/...
    00b4:trace:hid:get_device_subsystem_info hid uevent "HID_PHYS=hefesto-vpad"
    00b4:trace:hid:get_device_subsystem_info hid uevent "HID_UNIQ=02:fe:00:00:00:01"

`HID_PHYS=hefesto-vpad` é o que o PRODUTO carimba no `UHID_CREATE2`
(`src/hefesto_dualsense4unix/integrations/uhid_gamepad.py`, `_create2_event`).
Não é nome nem endereço de aparelho: é uma palavra que só este produto escreve.

**Rota B — a instância do PDO, no lado Windows.** Do outro lado da fronteira, o
gerenciador de PnP do Wine registra o aparelho com um identificador que carrega
o `HID_UNIQ` inteiro dentro dele::

    00b4:trace:hid:driver_add_device Adding device to PDO 0000000000C51210,
        id L"USB\\VID_054C&PID_0DF2"\\L"0&02:fe:00:00:00:01&0&0&0".

Desse identificador sai o **handle** do device no Wine, e é por ele que se
contam os reports::

    00b4:trace:hid:process_hid_report device 0000000000C51210 report_buf ...

Rota A diz *"o kernel publicou o nosso carimbo neste nó"*. Rota B diz *"um
aparelho com o nosso `uniq` foi registrado do lado Windows, e N reports
atravessaram"*. **Quando as duas discordam, o veredicto é `NÃO SONDADO`** — o
instrumento não escolhe a que gosta mais.

O QUE ESTA RÉGUA NÃO OLHA, DE PROPÓSITO
----------------------------------------
- **vid/pid**, como identidade. O vpad forja `054c:0df2` (DualSense Edge) de
  propósito, e o DualSense Edge **existe de verdade**: casar por vid/pid faria
  o Edge dela virar "o nosso vpad" no dia em que um entrasse na mesa. O vid/pid
  entra como corroboração fraca, rotulado como fraca, e nunca decide;
- **topologia de sysfs**. Com BlueZ >= 5.73 o HID dos controles físicos de
  RÁDIO nasce sob `/devices/virtual/misc/uhid/`, no mesmíssimo lugar do vpad.
  Armadilha paga em 11/08/2026. O caminho no log não é crachá de ninguém;
- **o nome do aparelho**. `(Hefesto P1)` já mudou uma vez (BT-E-VPAD-01).

O QUE ELA NÃO VÊ, E ISTO TEM DE FICAR NA TELA
----------------------------------------------
- **o inode.** O log traz CAMINHO e CARIMBO, nunca inode. Quando esta régua e a
  do inode discordarem sobre QUAL nó, a do inode ganha — o critério do degrau é
  o dela. Esta ganha sobre se os reports ATRAVESSARAM, que é o que a do inode
  não consegue ver;
- **o relógio.** Sem `+timestamp` no `WINEDEBUG` não há hora em linha alguma
  deste log. Este instrumento CONTA reports e **nunca** calcula Hz. Quem quer
  taxa usa `taxa_de_entrada.py`, com o aparelho na mão;
- **o agora.** Um log é gravação, não medição ao vivo. O cabeçalho imprime a
  idade do arquivo justamente porque um log de ontem responde sobre ontem.

E UMA HONESTIDADE SOBRE A LEITURA DAS LINHAS
---------------------------------------------
`process_hid_report` e `deliver_next_report` são funções do winebus, e **o
fonte do Wine desta build não está nesta máquina** — conferido. A leitura que
este instrumento faz delas é INFERIDA do próprio traço, e ele diz isso na tela
em vez de fingir que leu o código:

- `process_hid_report device H` aparece uma vez por report, sempre na thread do
  barramento;
- `deliver_next_report device H/0xP input report length N:` aparece com o
  conteúdo do report, e — medido no log de 18/08 — em **mais de uma thread**,
  o que só faz sentido se alguém do outro lado estiver esperando por ele.

Por isso o veredicto se apoia em `process_hid_report`, que é o mais simples de
ler, e `deliver_next_report` sai ao lado como número que corrobora.

COMO GRAVAR O LOG (é ela quem grava, com o jogo aberto)
--------------------------------------------------------
    o_jogo_no_log_do_proton.py --como-gravar

COMO LER O QUE JÁ EXISTE
-------------------------
    o_jogo_no_log_do_proton.py                 # varre ~/steam-*.log
    o_jogo_no_log_do_proton.py --appid 2497900
    o_jogo_no_log_do_proton.py --log /caminho/steam-2497900.log
    o_jogo_no_log_do_proton.py --json          # o mesmo, para máquina

O QUE ELE NÃO FAZ
------------------
Não abre aparelho, não escreve em nada, não toca `/dev`, `/sys` nem `/proc`.
Ele lê UM arquivo de texto. E **não preenche célula nenhuma** de
`docs/data/mapa-controles.csv` nem de `docs/data/ensaios.csv`: um instrumento
que preenche o próprio mapa é o instrumento se confirmando.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_AQUI)
_SRC = os.path.join(os.path.dirname(_SCRIPTS), "src")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from identidade_do_vpad import VPAD_HID_PHYS, VPAD_UNIQ_PREFIXO

try:  # pragma: no cover - o caminho sem pacote é o do checkout sem venv
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        VPAD_HID_PHYS as _CARIMBO_DO_PRODUTO,
    )
except ImportError:
    _CARIMBO_DO_PRODUTO = ""

A_IRMA = Path(__file__).resolve().parent / "o_jogo_segura_o_nosso_no.py"


def _estado_da_irma() -> str:
    if A_IRMA.exists():
        return "está nesta árvore, e casa por INODE em /proc/<pid>/fd"
    return "NÃO ESTÁ nesta árvore — hoje esta é a única régua deste degrau"


ONDE_O_PROTON_GRAVA = Path.home()
PADRAO_DO_NOME = "steam-*.log"

CANAL_EXIGIDO = "hid"

V_RECEBEU = "RECEBEU DO NOSSO NÓ"
V_SO_VIU = "VIU O NOSSO NÓ, NÃO RECEBEU"
V_OUTRO = "RECEBEU DE OUTRO NÓ, NÃO DO NOSSO"
V_NENHUM = "NENHUM"
V_NAO_SONDADO = "NÃO SONDADO"

VEREDICTOS = (V_RECEBEU, V_SO_VIU, V_OUTRO, V_NENHUM, V_NAO_SONDADO)

_RX_MAC = re.compile(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")

_RX_LINHA = re.compile(
    r"^(?P<thread>[0-9a-f]{4}):"
    r"(?P<nivel>trace|warn|err|fixme):"
    r"(?P<canal>[a-z_]+):"
    r"(?P<func>\w+) "
    r"(?P<resto>.*)$"
)

_RX_UDEV_ABRE = re.compile(r'^udev "(?P<no>[^"]+)" syspath (?P<syspath>\S+)')
_RX_UDEV_FECHA = re.compile(r'^evdev "(?P<no>[^"]+)": (?P<destino>.*)$')
_RX_UEVENT = re.compile(r'^(?P<sub>\w+) uevent "(?P<chave>[^=]+)=(?P<valor>.*)"$')
_RX_HIDRAW_CRIA = re.compile(
    r'^dev 0x\w+, node "(?P<no>[^"]+)", desc \{(?P<desc>[^}]*)\}'
)
_RX_RECUSADO = re.compile(r'^Unable to open "(?P<no>[^"]+)", ignoring: (?P<motivo>.+?)\.?$')
_RX_PDO = re.compile(
    r'^Adding device to PDO (?P<handle>[0-9A-F]+), '
    r'id L"(?P<devid>[^"]*)"\\L"(?P<inst>[^"]*)"'
)
_RX_CRIOU = re.compile(r"^created device (?P<handle>[0-9A-F]+)/0x(?P<unix>[0-9a-f]+)")
_RX_PROCESSOU = re.compile(r"^device (?P<handle>[0-9A-F]+) report_buf")
_RX_ENTREGOU = re.compile(
    r"^device (?P<handle>[0-9A-F]+)/0x[0-9a-f]+ input report length (?P<tam>\d+):"
)
_RX_HEXDUMP = re.compile(r"^[0-9a-f]{8}  (?P<bytes>[0-9a-f ]+)$")
_RX_DESC = re.compile(r"\{(?P<desc>[^}]*)\}")

_DESTINOS = (
    ("in SDL ignore list", "ignorado (SDL ignore list)"),
    ("to a different backend", "adiado p/ outro backend"),
)


def mascarar(texto: str) -> str:
    """Zera os octetos 4 e 5 de todo MAC do texto — a máscara desta casa."""

    def _troca(m: re.Match[str]) -> str:
        p = m.group(1).split(":")
        return ":".join([*p[:3], "00", "00", p[5]])

    return _RX_MAC.sub(_troca, texto)


@dataclass
class NoDoLog:
    """Um nó de `/dev` que o winebus considerou, com o `uevent` que veio junto."""

    no: str = ""
    syspath: str = ""
    uevent: dict[str, str] = field(default_factory=dict)
    destino: str = ""
    desc: str = ""
    linha: int = 0

    @property
    def tipo(self) -> str:
        return "hidraw" if "hidraw" in self.no else "evdev"

    @property
    def hid_phys(self) -> str:
        return self.uevent.get("HID_PHYS", "")

    @property
    def hid_uniq(self) -> str:
        return self.uevent.get("HID_UNIQ", "").strip().lower()

    @property
    def hid_id(self) -> str:
        return self.uevent.get("HID_ID", "")

    @property
    def e_nosso(self) -> bool:
        """O carimbo do produto, e SÓ ele. Nunca vid/pid, nunca caminho."""
        if self.hid_phys.strip() == VPAD_HID_PHYS:
            return True
        return self.hid_uniq.startswith(VPAD_UNIQ_PREFIXO)

    @property
    def destino_curto(self) -> str:
        """O destino em três palavras, para a tabela caber na tela dela."""
        if not self.destino:
            return "(o log não disse)"
        for marca, curto in _DESTINOS:
            if marca in self.destino:
                return curto
        return self.destino

    @property
    def vidpid(self) -> str:
        """`054c:0df2` a partir do `HID_ID`. Corroboração FRACA, nunca régua."""
        partes = self.hid_id.split(":")
        if len(partes) != 3:
            return ""
        return f"{partes[1][-4:].lower()}:{partes[2][-4:].lower()}"


@dataclass
class DeviceDoWine:
    """Um device do lado Windows da fronteira: quem é, e quantos reports levou."""

    handle: str = ""
    devid: str = ""
    instancia: str = ""
    processou: int = 0
    entregou: int = 0
    threads: set[str] = field(default_factory=set)
    primeiro_report: list[str] = field(default_factory=list)

    @property
    def uniq(self) -> str:
        """O `HID_UNIQ` que o Wine embutiu na instância do PDO."""
        m = _RX_MAC.search(self.instancia)
        return m.group(1).lower() if m else ""

    @property
    def e_nosso(self) -> bool:
        return self.uniq.startswith(VPAD_UNIQ_PREFIXO)


@dataclass
class Log:
    """Tudo o que este instrumento conseguiu tirar de UM arquivo de log."""

    caminho: str = ""
    existe: bool = False
    erro: str = ""
    tamanho: int = 0
    mtime: float = 0.0
    linhas: int = 0
    proton: str = ""
    appid: str = ""
    comando: str = ""
    winedebug: str = ""
    winedebug_declarado: bool = False
    tem_linha_de_hid: bool = False
    enumeracao_rodou: bool = False
    bus_do_windows_rodou: bool = False
    nos: list[NoDoLog] = field(default_factory=list)
    devices: dict[str, DeviceDoWine] = field(default_factory=dict)
    recusados: dict[str, str] = field(default_factory=dict)
    sdl: list[str] = field(default_factory=list)

    @property
    def idade_em_horas(self) -> float:
        return max(0.0, (time.time() - self.mtime) / 3600.0) if self.mtime else 0.0

    @property
    def canal_hid_ligado(self) -> bool:
        """`+hid` estava no `WINEDEBUG` que gravou este log?"""
        if self.tem_linha_de_hid:
            return True
        return self.winedebug_declarado and f"+{CANAL_EXIGIDO}" in self.winedebug


def ler_log(caminho: str) -> Log:
    """O log inteiro, em uma passada. Nunca levanta: erro vira campo."""
    log = Log(caminho=caminho)
    try:
        estado = os.stat(caminho)
    except OSError as erro:
        log.erro = str(erro)
        return log
    log.existe = True
    log.tamanho = estado.st_size
    log.mtime = estado.st_mtime

    abertos: dict[str, NoDoLog] = {}
    por_no: dict[str, NoDoLog] = {}
    coletando_report_de: str | None = None

    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            for numero, bruta in enumerate(arquivo, start=1):
                linha = bruta.rstrip("\n")
                log.linhas = numero

                if linha.startswith("Proton: "):
                    log.proton = linha[len("Proton: "):].strip()
                    continue
                if linha.startswith("SteamGameId: "):
                    log.appid = linha[len("SteamGameId: "):].strip()
                    continue
                if linha.startswith("Command: "):
                    log.comando = linha[len("Command: "):].strip()
                    continue
                if linha.startswith("Effective WINEDEBUG: "):
                    log.winedebug = linha[len("Effective WINEDEBUG: "):].strip()
                    log.winedebug_declarado = True
                    continue

                m = _RX_LINHA.match(linha)
                if m is None:
                    continue
                canal = m.group("canal")
                func = m.group("func")
                resto = m.group("resto")
                thread = m.group("thread")
                if canal == "hid":
                    log.tem_linha_de_hid = True

                if func != "deliver_next_report":
                    coletando_report_de = None

                if func == "build_initial_deviceset_direct" or func == "maybe_add_devnode":
                    log.enumeracao_rodou = True

                if func == "maybe_add_devnode":
                    recusa = _RX_RECUSADO.match(resto)
                    if recusa:
                        log.recusados[recusa.group("no")] = recusa.group("motivo")
                    continue

                if func == "udev_add_device":
                    abre = _RX_UDEV_ABRE.match(resto)
                    if abre:
                        novo = NoDoLog(
                            no=abre.group("no"),
                            syspath=abre.group("syspath"),
                            linha=numero,
                        )
                        abertos[thread] = novo
                        por_no[novo.no] = novo
                        log.nos.append(novo)
                        continue
                    fecha = _RX_UDEV_FECHA.match(resto)
                    if fecha:
                        alvo = por_no.get(fecha.group("no"))
                        if alvo is not None:
                            alvo.destino = fecha.group("destino")
                            desc = _RX_DESC.search(alvo.destino)
                            if desc:
                                alvo.desc = desc.group("desc")
                        abertos.pop(thread, None)
                    continue

                if func == "get_device_subsystem_info":
                    aberto = abertos.get(thread)
                    if aberto is None:
                        continue
                    campo = _RX_UEVENT.match(resto)
                    if campo and campo.group("sub") in ("hid", "input"):
                        chave = campo.group("chave")
                        if chave not in aberto.uevent:
                            aberto.uevent[chave] = campo.group("valor").strip('"')
                    continue

                if func == "hidraw_device_create":
                    cria = _RX_HIDRAW_CRIA.match(resto)
                    if cria:
                        alvo = por_no.get(cria.group("no"))
                        if alvo is not None:
                            alvo.desc = cria.group("desc")
                            alvo.destino = "adotado como hidraw"
                        abertos.pop(thread, None)
                    continue

                if func == "bus_create_hid_device":
                    log.bus_do_windows_rodou = True
                    criou = _RX_CRIOU.match(resto)
                    if criou:
                        handle = criou.group("handle")
                        log.devices.setdefault(handle, DeviceDoWine(handle=handle))
                    continue

                if func == "driver_add_device":
                    pdo = _RX_PDO.match(resto)
                    if pdo:
                        handle = pdo.group("handle")
                        dev = log.devices.setdefault(handle, DeviceDoWine(handle=handle))
                        dev.devid = pdo.group("devid")
                        dev.instancia = pdo.group("inst")
                    continue

                if func == "process_hid_report":
                    proc = _RX_PROCESSOU.match(resto)
                    if proc:
                        handle = proc.group("handle")
                        dev = log.devices.setdefault(handle, DeviceDoWine(handle=handle))
                        dev.processou += 1
                    continue

                if func == "deliver_next_report":
                    entrega = _RX_ENTREGOU.match(resto)
                    if entrega:
                        handle = entrega.group("handle")
                        dev = log.devices.setdefault(handle, DeviceDoWine(handle=handle))
                        dev.entregou += 1
                        dev.threads.add(thread)
                        coletando_report_de = handle if not dev.primeiro_report else None
                        continue
                    dump = _RX_HEXDUMP.match(resto)
                    if dump and coletando_report_de:
                        log.devices[coletando_report_de].primeiro_report.append(
                            dump.group("bytes").strip()
                        )
                    continue

                if func == "sdl_add_device":
                    log.sdl.append(resto)
                    continue
    except OSError as erro:  # pragma: no cover - o stat já passou
        log.erro = str(erro)
    return log


def nossos_nos(log: Log) -> list[NoDoLog]:
    return [no for no in log.nos if no.e_nosso]


def nossos_devices(log: Log) -> list[DeviceDoWine]:
    return [dev for dev in log.devices.values() if dev.e_nosso]


def veredicto(log: Log) -> tuple[str, list[str]]:
    """O veredicto e as razões que o produziram — nesta ordem, sempre a mesma."""
    razoes: list[str] = []

    if _CARIMBO_DO_PRODUTO and _CARIMBO_DO_PRODUTO != VPAD_HID_PHYS:
        razoes.append(
            f"o carimbo que eu procuro ({VPAD_HID_PHYS!r}) NÃO é o que o produto "
            f"escreve ({_CARIMBO_DO_PRODUTO!r}) — a régua está velha"
        )
        return V_NAO_SONDADO, razoes

    if not log.existe:
        razoes.append(f"não consegui ler o log: {log.erro}")
        return V_NAO_SONDADO, razoes

    if not log.canal_hid_ligado:
        como = "declarado no cabeçalho" if log.winedebug_declarado else "inferido das linhas"
        razoes.append(
            f"o log foi gravado sem `+{CANAL_EXIGIDO}` no WINEDEBUG ({como}) — "
            "ele não tem como responder, e ausência de linha aqui é cegueira minha, "
            "não silêncio do jogo"
        )
        return V_NAO_SONDADO, razoes

    if not log.enumeracao_rodou:
        razoes.append(
            "o log tem o canal de HID mas nenhuma linha de enumeração de nós — "
            "truncado, ou o winebus nem chegou a varrer"
        )
        return V_NAO_SONDADO, razoes

    nos = nossos_nos(log)
    devices = nossos_devices(log)

    orfaos = sorted(
        {dev.uniq for dev in devices} - {no.hid_uniq for no in nos if no.hid_uniq}
    )
    if orfaos:
        razoes.append(
            "as duas rotas discordam: o lado Windows registrou "
            + ", ".join(mascarar(u) for u in orfaos)
            + " e o lado unix nunca publicou o carimbo desse nó"
        )
        return V_NAO_SONDADO, razoes

    if nos and not log.bus_do_windows_rodou:
        razoes.append(
            "o lado unix viu o nosso carimbo, mas o log não tem uma única linha do "
            "lado Windows (`bus_create_hid_device`) — o log acaba antes da resposta"
        )
        return V_NAO_SONDADO, razoes

    reports_nossos = sum(dev.processou for dev in devices)
    reports_totais = sum(dev.processou for dev in log.devices.values())

    if devices and reports_nossos > 0:
        razoes.append(
            f"{len(nos)} nó(s) com o nosso carimbo do lado unix, "
            f"{len(devices)} device(s) com o nosso uniq do lado Windows, "
            f"{reports_nossos} report(s) atravessaram"
        )
        return V_RECEBEU, razoes

    if nos or devices:
        razoes.append(
            f"o nosso nó apareceu ({len(nos)} do lado unix, {len(devices)} do lado "
            "Windows) e NENHUM report atravessou — enumerado, não lido"
        )
        return V_SO_VIU, razoes

    if reports_totais > 0:
        outros = sorted(
            dev.devid or dev.handle
            for dev in log.devices.values()
            if dev.processou > 0
        )
        razoes.append(
            "nenhum traço do nosso carimbo, e o jogo recebeu report de outro(s): "
            + ", ".join(mascarar(o) for o in outros)
        )
        return V_OUTRO, razoes

    razoes.append(
        f"o censo fechou ({len(log.nos)} nó(s) considerados) e nenhum aparelho "
        "entregou report algum a este jogo — nem o nosso, nem outro"
    )
    return V_NENHUM, razoes


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    if not linhas:
        larguras = [len(c) for c in cabecalho]
    else:
        larguras = [
            max(len(cabecalho[i]), *(len(str(linha[i])) for linha in linhas))
            for i in range(len(cabecalho))
        ]
    partes = ["  ".join(c.ljust(larguras[i]) for i, c in enumerate(cabecalho)).rstrip()]
    partes.append("  ".join("-" * larguras[i] for i in range(len(cabecalho))))
    for linha in linhas:
        partes.append(
            "  ".join(str(c).ljust(larguras[i]) for i, c in enumerate(linha)).rstrip()
        )
    return "\n".join(partes)


def _procedencia(nome: str) -> str:
    modulo = sys.modules.get(nome)
    if modulo is None:
        return "NÃO IMPORTADO"
    caminho = getattr(modulo, "__file__", None)
    if caminho:
        return caminho
    if nome in sys.builtin_module_names:
        return "embutido no interpretador"
    return "sem __file__"


def cabecalho(log: Log) -> str:
    """A procedência, ANTES do primeiro número. Regra da casa, e o motivo dela."""
    linhas = [
        "=" * 78,
        "  o_jogo_no_log_do_proton.py   (o vpad atravessou a fronteira do Wine?)",
        "=" * 78,
        "  degrau ........... O JOGO RECEBEU (direção de ENTRADA)",
        f"  a régua irmã ..... {A_IRMA.name} — {_estado_da_irma()}",
        f"  interpretador .... {sys.executable}",
        f"  régua do vpad .... identidade_do_vpad de {_procedencia('identidade_do_vpad')}",
        f"  carimbo procurado  HID_PHYS={VPAD_HID_PHYS!r}, HID_UNIQ começando em "
        f"{VPAD_UNIQ_PREFIXO!r}",
    ]
    if _CARIMBO_DO_PRODUTO:
        igual = "confere" if _CARIMBO_DO_PRODUTO == VPAD_HID_PHYS else "DIVERGE"
        linhas.append(
            f"  contra o produto . {_CARIMBO_DO_PRODUTO!r} ({igual}) — "
            "uhid_gamepad._create2_event"
        )
    else:
        linhas.append(
            "  contra o produto . NÃO SEI — o pacote não é importável neste "
            "interpretador"
        )
    linhas.append(f"  log .............. {log.caminho}")
    if not log.existe:
        linhas.append(f"  estado do log .... ILEGÍVEL: {log.erro}")
        linhas.append("=" * 78)
        return "\n".join(linhas)
    linhas += [
        f"  tamanho .......... {log.tamanho} bytes, {log.linhas} linhas",
        f"  gravado em ....... {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log.mtime))}"
        f"  ({log.idade_em_horas:.1f} h atrás)",
        f"  Proton ........... {log.proton or '(o cabeçalho não veio)'}",
        f"  appid ............ {log.appid or '(o cabeçalho não veio)'}",
    ]
    if log.winedebug_declarado:
        linhas.append(f"  WINEDEBUG ........ {log.winedebug}  (declarado pelo próprio log)")
    else:
        linhas.append(
            "  WINEDEBUG ........ NÃO DECLARADO — caindo na rota fraca "
            f"(há linha trace:hid? {'sim' if log.tem_linha_de_hid else 'NÃO'})"
        )
    linhas += [
        "  escreve em algo? . NÃO — leitura de um arquivo de texto, e só",
        "  preenche o mapa? . NÃO — nenhuma célula, nunca. Quem preenche é ela",
        "=" * 78,
    ]
    return "\n".join(linhas)


def _linha_do_no(no: NoDoLog) -> list[str]:
    return [
        no.no,
        no.tipo,
        mascarar(no.hid_phys) or "-",
        mascarar(no.hid_uniq) or "-",
        no.vidpid or "-",
        "SIM" if no.e_nosso else "não",
        no.destino_curto,
    ]


def imprimir(log: Log, decisao: str, razoes: list[str]) -> None:
    print(cabecalho(log))
    if not log.existe:
        print(f"\nVEREDICTO: {decisao}")
        for razao in razoes:
            print(f"  porque: {razao}")
        return

    print("\n=== ROTA A — o carimbo, do lado unix do winebus ===")
    if log.nos:
        print(
            _tabela(
                ["nó", "tipo", "HID_PHYS", "HID_UNIQ", "vid:pid", "nosso?", "destino"],
                [_linha_do_no(no) for no in log.nos],
            )
        )
    else:
        print("  (o log não traz um único bloco de uevent)")

    if log.recusados:
        print("\n  nós que o winebus NÃO conseguiu abrir:")
        for no, motivo in sorted(log.recusados.items()):
            print(f"      {no:<22} {motivo}")
        if any("Permission denied" in m for m in log.recusados.values()):
            print(
                "      LEITURA, NÃO MEDIDA: `Permission denied` num hidraw é o que o\n"
                "      broker deste produto produz de propósito (chmod 0600 + ACL\n"
                "      removida, `broker/hidraw_broker.py`). O log NÃO diz de quem é a\n"
                "      permissão — quem confere isso é `quem_e_quem.py`, na máquina."
            )

    print("\n=== ROTA B — a fronteira do Wine, do lado Windows ===")
    if log.devices:
        linhas = []
        for dev in sorted(log.devices.values(), key=lambda d: -d.processou):
            identificador = f"{dev.devid}\\{dev.instancia}".replace("\\\\", "\\")
            linhas.append(
                [
                    dev.handle,
                    mascarar(identificador) if dev.devid else "(sem PDO)",
                    "SIM" if dev.e_nosso else "não",
                    str(dev.processou),
                    str(dev.entregou),
                    ", ".join(sorted(dev.threads)) or "-",
                ]
            )
        print(
            _tabela(
                ["handle", "instância do PDO", "nosso?", "processou", "entregou", "threads"],
                linhas,
            )
        )
    else:
        print("  (o log não registrou device algum do lado Windows)")

    if log.sdl:
        print("\n  o barramento SDL do Wine também enumerou:")
        for item in log.sdl:
            print(f"      {mascarar(item)}")

    nossos = nossos_devices(log)
    com_bytes = [d for d in nossos if d.primeiro_report]
    if com_bytes:
        dev = com_bytes[0]
        print(f"\n  o PRIMEIRO report entregue no nosso device ({dev.handle}):")
        for linha in dev.primeiro_report:
            print(f"      {linha}")
        primeiro = dev.primeiro_report[0].split()
        if primeiro:
            print(f"      report id = 0x{primeiro[0]}")
        print(
            "      (isto NÃO é a régua do byte da chave — essa exige abrir o nó,\n"
            "       e abrir o nó tem disciplina que este instrumento não tem)"
        )

    print(f"\nVEREDICTO: {decisao}")
    for razao in razoes:
        print(f"  porque: {razao}")
    print(
        "\n  o que esta régua NÃO viu: o inode (o log traz caminho e carimbo, não\n"
        "  inode); o relógio (sem +timestamp não há hora, então zero Hz daqui); e o\n"
        "  agora (um log é gravação — veja a idade no cabeçalho).\n"
        "  `process_hid_report` e `deliver_next_report` são lidas como estão acima\n"
        "  por INFERÊNCIA do próprio traço: o fonte do Wine desta build não está\n"
        "  nesta máquina, e eu não o li."
    )


def como_gravar() -> str:
    """O comando exato, para ela. O instrumento não abre jogo nenhum."""
    return "\n".join(
        [
            "Para gravar um log que responda esta pergunta:",
            "",
            "  1. nas propriedades do jogo na Steam, em OPÇÕES DE INICIALIZAÇÃO:",
            "",
            "       PROTON_LOG=1 WINEDEBUG=+hid,+xinput,+plugplay %command%",
            "",
            "  2. abra o jogo, deixe chegar na TELA (o menu da Steam não enumera",
            "     controle), e mexa nos dois analógicos por uns segundos;",
            "  3. feche o jogo. O log fica em:",
            "",
            f"       {ONDE_O_PROTON_GRAVA}/steam-<appid>.log",
            "",
            "  4. rode este instrumento.",
            "",
            "O preço, dito antes: `+hid` em nível de traço escreve MUITO (um log de",
            "sessão curta já mediu 6,9 MB) e deixa o jogo mais lento. Tire a opção de",
            "inicialização depois de medir.",
            "",
            "E o que ele NÃO vai poder dizer: se o personagem andou. Isso é o degrau",
            "`O JOGO REAGIU`, e o único sensor dele é ela.",
        ]
    )


def _para_json(log: Log, decisao: str, razoes: list[str]) -> dict[str, object]:
    return {
        "log": log.caminho,
        "existe": log.existe,
        "appid": log.appid,
        "proton": log.proton,
        "winedebug": log.winedebug,
        "winedebug_declarado": log.winedebug_declarado,
        "idade_em_horas": round(log.idade_em_horas, 2),
        "degrau": "O JOGO RECEBEU",
        "veredicto": decisao,
        "razoes": [mascarar(r) for r in razoes],
        "nos": [
            {
                "no": no.no,
                "tipo": no.tipo,
                "hid_phys": mascarar(no.hid_phys),
                "hid_uniq": mascarar(no.hid_uniq),
                "vidpid": no.vidpid,
                "nosso": no.e_nosso,
                "destino": no.destino_curto,
                "desc": no.desc,
                "linha": no.linha,
            }
            for no in log.nos
        ],
        "devices": [
            {
                "handle": dev.handle,
                "instancia": mascarar(f"{dev.devid}\\{dev.instancia}".replace("\\\\", "\\")),
                "nosso": dev.e_nosso,
                "processou": dev.processou,
                "entregou": dev.entregou,
                "threads": sorted(dev.threads),
            }
            for dev in log.devices.values()
        ],
        "recusados": dict(sorted(log.recusados.items())),
        "reports_nossos": sum(d.processou for d in nossos_devices(log)),
        "reports_totais": sum(d.processou for d in log.devices.values()),
    }


def logs_candidatos(args: argparse.Namespace) -> list[str]:
    if args.log:
        return [args.log]
    if args.appid:
        return [str(ONDE_O_PROTON_GRAVA / f"steam-{args.appid}.log")]
    return [str(p) for p in sorted(ONDE_O_PROTON_GRAVA.glob(PADRAO_DO_NOME))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", help="caminho de um log específico")
    ap.add_argument("--appid", help="o appid da Steam (procura ~/steam-<appid>.log)")
    ap.add_argument("--json", action="store_true", help="a mesma leitura, para máquina")
    ap.add_argument(
        "--como-gravar",
        action="store_true",
        help="imprime o comando exato para gravar o log, e para",
    )
    args = ap.parse_args(argv)

    if args.como_gravar:
        print(como_gravar())
        return 0

    candidatos = logs_candidatos(args)
    if not candidatos:
        print(f"nenhum log em {ONDE_O_PROTON_GRAVA}/{PADRAO_DO_NOME}.")
        print("rode com --como-gravar para ver como produzir um.")
        return 1

    saida: list[dict[str, object]] = []
    houve_nosso = False
    for caminho in candidatos:
        log = ler_log(caminho)
        decisao, razoes = veredicto(log)
        houve_nosso = houve_nosso or decisao == V_RECEBEU
        if args.json:
            saida.append(_para_json(log, decisao, razoes))
        else:
            imprimir(log, decisao, razoes)
            print()

    if args.json:
        print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0 if houve_nosso else 2


if __name__ == "__main__":
    raise SystemExit(main())
