"""O device de áudio KS do DualSense — o alvo que a RE Engine procura para vibrar.

HAPTICA-NATIVA-01 (17/09/2026). Lido no trace do PRAGMATA
(`PROTON_LOG=+setupapi,+mmdevapi`), o jogo acha o alvo da vibração assim:

1. `EnumAudioEndpoints` → lê o `ContainerId` de cada endpoint de áudio;
2. `SetupDiGetClassDevsExW(KSCATEGORY_AUDIO, PRESENT|DEVICEINTERFACE)` → lê o
   `ContainerId` (SPDRP 36) e o `HardwareID` (SPDRP 1) de cada device KS;
3. casou → ativa o endpoint do controle em 4 canais (máscara `0x33`) e toca a
   háptica nos canais 3 e 4, que são os dois motores.

No Windows o driver USB Audio publica esse device KS sozinho. No Wine ninguém o
publica: o GE-Proton o cria só para o Monster Hunter Wilds (patch 0003) e
EXCLUI o DualSense de propósito (`!is_dualsense_device_path`); e ainda apaga
todo device MEDIA de DualSense a cada início. Sem o device, o passo 2 volta
vazio e o jogo desiste antes de olhar o HID. **Com ele, vibrou** — com o físico
direto e em modo produto (vpad `uhid`), na mão dela.

O QUE ESTE MÓDULO GRAVA, POR CONTROLE NO CABO
---------------------------------------------

No `system.reg` do prefixo, a mesma forma que o `setupapi` do Wine lê
(`devinst.c`, `SETUPDI_EnumerateMatchingInterfaces`):

- `Enum\\USB\\VID_054C&PID_<pid>\\HEFESTOKS&<bus>&<dev>&<n>` com `Class`,
  **`ClassGUID`** (sem ele o `setupapi` descarta o device — medido: "found
  instance ID" e o conjunto voltou vazio), `ContainerId`, `FriendlyName`,
  `HardwareID`;
- a interface em `DeviceClasses\\{6994AD04…}` com `DeviceInstance`, a subchave
  `#` com `SymbolicLink` e `#\\Control` com `Linked=1`.

A classe é **USB, e não MEDIA**, porque o GE apaga os MEDIA de DualSense.

O `ContainerId` é a conta do `winepulse`: `{(pid<<16|vid)-BUSNUM-DEVNUM-Data4}`.
O Data4 é o `USEC_INITIALIZED` do udev QUANDO o runtime da Steam enxerga o
`/run/udev` — no GE-Proton11-7 (SLR4) não enxerga e sai zero; no GE10-34
(sniper) saiu diferente de zero, na mesma máquina. Então, nesta ordem:

1. **perguntar ao dono** — se o próprio prefixo já registrou um `ContainerId`
   Sony com o mesmo pid/bus/dev (o endpoint de áudio da sessão anterior, ou o
   HID do winebus), usar o valor dele;
2. senão, gravar as duas variantes (zero e `USEC`), cada uma na sua instância —
   só a que casar com o endpoint é usada.

POR QUE A CADA LANÇAMENTO
-------------------------

- o `DEVNUM` muda a cada replug, e com ele o `ContainerId`;
- uma sessão SEM `PROTON_ENABLE_MHWILDS_USB_AUDIO=1` enumera a interface
  escondida e o `setupapi` APAGA os valores da chave (`devinst.c:2046`).

Idempotente: o texto novo só é escrito se for diferente do atual. Um backup só,
rotativo (`system.reg.bak.hefesto-audio-ks`) — este passo roda em TODO
lançamento, e um backup por lançamento encheria o disco. Recusa com o
`wineserver` DAQUELE prefixo vivo: ele regravaria o registro por cima, e o
próximo lançamento refaz.

PELO RÁDIO, E O FATO MUDOU EM 18/09/2026
----------------------------------------

Até aqui esta página dizia *"por Bluetooth não há placa de áudio: nenhum
controle no rádio entra aqui"*. A primeira metade continua verdadeira — o
controle no rádio não tem placa de som nenhuma —, e a segunda caiu: quem
publica o endpoint passa a ser o PRODUTO, com um `module-null-sink` vestido de
DualSense (`scripts/ensaios/o_endpoint_de_mentira.py`, medido). O jogo não
pergunta pelo transporte do controle; ele lê o proplist do SINK.

Então, no rádio, o `ContainerId` não sai do controle: sai do **`sysfs.path` que
o nó declara** — um `usb_device` real sem placa de som, a ÂNCORA. É a mesma
conta que o `winepulse` faz, com a mesma entrada, e por isso nenhum acerto
precisa ser combinado entre o daemon e o lançador: os dois lados leem o nó.

Este módulo é **100% stdlib de propósito**, como o `camadas_vulkan`: o
`install.sh` o materializa em `~/.local/share/hefesto-dualsense4unix/bin/` e o
`assets/hefesto-launch.sh` o roda com o `python3` do sistema, antes do Proton
subir o `wineserver`.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: KSCATEGORY_AUDIO — a pergunta que o jogo faz ao `setupapi`.
KS = "{6994AD04-93EF-11D0-A3CC-00A0C9223196}"

#: A classe USB do Windows. NÃO a MEDIA (`{4d36e96c…}`), que o GE apaga para
#: todo caminho de DualSense (`remove_dualsense_media_devices`).
CLASSE_USB = "{36FC9E60-C465-11CF-8056-444553540000}"

VID_SONY = 0x054C

#: Os DualSense que têm placa USB Audio de 4 canais, e o nome que cada um usa.
MODELOS: dict[int, str] = {
    0x0CE6: "DualSense Wireless Controller",
    0x0DF2: "DualSense Edge Wireless Controller",
}

#: O marcador da instância. Não colide com o wineusb (`<n>&<n>&<n>&<n>`) nem com
#: o winebus (`…&MI_03\\<serial>…`), e é por ele que as rodadas seguintes acham
#: o que é nosso.
MARCADOR = "HEFESTOKS"

#: A forma das instâncias gravadas à mão na prova de 17/09
#: (`<nó do pipewire>&<8 hex do endpoint>`) — saem na primeira rodada.
_LEGADO_DA_PROVA = re.compile(r"^\d+&[0-9A-F]{8}$", re.I)

_BACKUP = ".bak.hefesto-audio-ks"
_TMP = ".hefesto-audio-ks-tmp"

_GUID_TXT = re.compile(
    r"\{([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})\}", re.I
)
#: O `ContainerId` que o mmdevapi guarda no endpoint: blob VT_CLSID (tipo
#: `0xBEEF0048`, um dword e os 16 bytes do GUID), com as continuações de linha
#: já juntadas.
_BLOB_CONTAINER = re.compile(
    r'"\{8c7ed206-3f8a-4827-b3ab-ae9e1faefc6c\},2"=hex:((?:[0-9a-f]{2},?)+)', re.I
)


@dataclass(frozen=True)
class Controle:
    """O aparelho de onde sai um `ContainerId` — o controle, ou a âncora dele.

    No CABO os campos são do próprio DualSense, que é quem tem a placa de som.
    No RÁDIO o endpoint é o nó que nós publicamos, e então `bus`, `dev`, `usec`
    e o par `container_*` são os do `usb_device` que o nó declara em
    `sysfs.path`. O `pid` continua sendo o do controle: ele é quem dá o nome e
    o `HardwareID`, que é o que o jogo lê para saber que aquilo é um DualSense.
    """

    pid: int
    bus: int
    dev: int
    #: `USEC_INITIALIZED` do udev para o `usb_device`, se o banco o tiver.
    usec: int | None
    #: O par vid/pid que entra na CONTA do `ContainerId`. No cabo é o do
    #: próprio controle; no rádio é o da âncora, porque é dela que o
    #: `winepulse` lê o `PRODUCT`.
    container_vid: int = VID_SONY
    container_pid: int | None = None

    @property
    def nome(self) -> str:
        return MODELOS[self.pid]

    def prefixo_do_container(self) -> str:
        """Os três primeiros campos do `ContainerId`, sem o Data4.

        **O `& 0xFF` não é zelo:** na origem (`create_usb_dev_container_id`) o
        barramento e o device são `uint8_t`, e um `devnum` acima de 255 — que
        acontece em host cheio — dobra ali. Sem a máscara esta conta divergiria
        da do Wine exatamente nos casos raros, que são os piores de achar.
        """
        pid = self.pid if self.container_pid is None else self.container_pid
        data1 = ((pid & 0xFFFF) << 16) | (self.container_vid & 0xFFFF)
        return f"{{{data1:08x}-{self.bus & 0xFF:04x}-{self.dev & 0xFF:04x}-"


def container_id(controle: Controle, data4: bytes) -> str:
    """A conta do `winepulse`: `Data4` são 8 bytes little-endian."""
    if len(data4) != 8:
        raise ValueError("Data4 tem 8 bytes")
    return controle.prefixo_do_container() + f"{data4[:2].hex()}-{data4[2:].hex()}}}"


def _ler(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return None


def _usec_do_udev(dev_sysfs: Path, udev_data: Path) -> int | None:
    """O `I:` do banco do udev para o `usb_device` (`/run/udev/data/c<maj>:<min>`)."""
    majmin = _ler(dev_sysfs / "dev")
    if not majmin or ":" not in majmin:
        return None
    try:
        linhas = (udev_data / f"c{majmin}").read_text(errors="replace").splitlines()
    except OSError:
        return None
    for linha in linhas:
        if linha.startswith("I:"):
            try:
                return int(linha[2:])
            except ValueError:
                return None
    return None


def controles_no_cabo(
    sysfs: Path = Path("/sys"), udev_data: Path = Path("/run/udev/data")
) -> list[Controle]:
    """Os DualSense ligados por USB COM placa de som, lidos do sysfs.

    A raiz é injetável de propósito: a suíte nunca pode ler o controle dela
    (memória "subsystem novo faz a suíte tocar o aparelho dela").
    """
    raiz = sysfs / "bus" / "usb" / "devices"
    achados: list[Controle] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return achados
    for dev in entradas:
        vendor = _ler(dev / "idVendor")
        produto = _ler(dev / "idProduct")
        if vendor is None or produto is None:
            continue
        try:
            vid, pid = int(vendor, 16), int(produto, 16)
        except ValueError:
            continue
        if vid != VID_SONY or pid not in MODELOS:
            continue
        # Sem placa de som não há endpoint para casar (controle de outra
        # revisão, ou a interface de áudio desautorizada pela regra 75).
        if not any(dev.glob("*/sound/card*")):
            continue
        bus, num = _ler(dev / "busnum"), _ler(dev / "devnum")
        if not (bus and num and bus.isdigit() and num.isdigit()):
            continue
        achados.append(
            Controle(pid=pid, bus=int(bus), dev=int(num), usec=_usec_do_udev(dev, udev_data))
        )
    return achados


# --------------------------------------------------------------------------
# O rádio: o endpoint é um nó nosso, e o ContainerId sai da âncora dele
# --------------------------------------------------------------------------

#: As marcas que o nó carrega no proplist, e são as MESMAS que o GE lê para
#: dizer "isto é um DualSense" (`fill_device_info`, `pulse.c:668`).
_PROP_VID = "device.vendor.id"
_PROP_PID = "device.product.id"
_PROP_SYSFS = "sysfs.path"

_NOME_DO_SINK = re.compile(r"^\tName: (.+)$", re.M)


def _pactl(argv: list[str]) -> str | None:
    """Roda um `pactl` curto. None em qualquer falha — ausência é resposta."""
    try:
        # argv fixo e sem shell: o único argumento é literal.
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _propriedade(bloco: str, chave: str) -> str:
    m = re.search(rf'^\s*{re.escape(chave)} = "(.*)"\s*$', bloco, re.M)
    return m.group(1) if m else ""


def endpoints_de_mentira(
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[tuple[int, str]]:
    """(pid do controle, `sysfs.path`) de cada nó que se diz DualSense.

    Só o que o `winepulse` também leria: o VID/PID do proplist e o
    `sysfs.path`. Um nó sem `sysfs.path` fica de fora de propósito — dele o
    Wine tiraria `GUID_NULL`, que é o `ContainerId` de toda saída que não é
    USB, e um device KS declarando zero casaria com a caixa de som da pessoa.
    """
    saida = runner(["pactl", "list", "sinks"]) or ""
    achados: list[tuple[int, str]] = []
    for bloco in re.split(r"\n(?=Sink #\d+)", saida):
        if not _NOME_DO_SINK.search(bloco):
            continue
        try:
            vid = int(_propriedade(bloco, _PROP_VID) or "0", 16)
            pid = int(_propriedade(bloco, _PROP_PID) or "0", 16)
        except ValueError:
            continue
        caminho = _propriedade(bloco, _PROP_SYSFS)
        if vid != VID_SONY or pid not in MODELOS or not caminho:
            continue
        achados.append((pid, caminho))
    return achados


def pai_usb_device(sysfs_path: str, sysfs: Path = Path("/sys")) -> Path | None:
    """O `usb_device` acima de um caminho do sysfs — o que o udev acharia.

    É a tradução de `udev_device_get_parent_with_subsystem_devtype(…, "usb",
    "usb_device")`: sobe até o primeiro pai que tem `busnum` e `devnum`, que é
    o que distingue um `usb_device` de uma interface. Nada é escrito ali.
    """
    try:
        raiz = sysfs.resolve()
        atual = (sysfs / sysfs_path.lstrip("/")).resolve()
    except OSError:
        return None
    if atual != raiz and raiz not in atual.parents:
        return None
    while True:
        if (atual / "busnum").is_file() and (atual / "devnum").is_file():
            return atual
        if atual == raiz:
            return None
        atual = atual.parent


def controles_no_radio(
    sysfs: Path = Path("/sys"),
    udev_data: Path = Path("/run/udev/data"),
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[Controle]:
    """Um `Controle` por endpoint de mentira vivo, com os campos da ÂNCORA.

    A conta é a do `winepulse` com a MESMA entrada: o `PRODUCT`, o `BUSNUM`, o
    `DEVNUM` e o `USEC_INITIALIZED` do `usb_device` que o nó declara. Por isso
    não há nada a combinar entre quem monta o nó e quem grava o registro — os
    dois leem o mesmo lugar.
    """
    achados: list[Controle] = []
    for pid, caminho in endpoints_de_mentira(runner):
        ancora = pai_usb_device(caminho, sysfs)
        if ancora is None:
            continue
        # ÂNCORA COM PLACA DE SOM É O CABO, e não entra aqui: o `sysfs.path` de
        # um DualSense ligado por USB sobe ao PRÓPRIO controle, e o
        # `controles_no_cabo` já o conhece. Sem esta linha, o mesmo aparelho
        # sairia nas duas listas e as duas gravariam a MESMA chave do registro.
        # É a mesma regra que escolhe as âncoras no ensaio, dita uma vez.
        if any(ancora.glob("*/sound/card*")):
            continue
        vendor, produto = _ler(ancora / "idVendor"), _ler(ancora / "idProduct")
        bus, num = _ler(ancora / "busnum"), _ler(ancora / "devnum")
        if not (vendor and produto and bus and num and bus.isdigit() and num.isdigit()):
            continue
        try:
            a_vid, a_pid = int(vendor, 16), int(produto, 16)
        except ValueError:
            continue
        controle = Controle(
            pid=pid,
            bus=int(bus),
            dev=int(num),
            usec=_usec_do_udev(ancora, udev_data),
            container_vid=a_vid,
            container_pid=a_pid,
        )
        if controle not in achados:
            achados.append(controle)
    return achados


# --------------------------------------------------------------------------
# O registro
# --------------------------------------------------------------------------


def _blocos(texto: str) -> list[str]:
    """O `system.reg` em blocos: o cabeçalho do arquivo e um bloco por chave."""
    return re.split(r"\n(?=\[)", texto)


def _cabecalho(bloco: str) -> str:
    """`[chave]`, sem o carimbo de hora."""
    primeira = bloco.split("\n", 1)[0]
    fim = primeira.find("] ")
    return primeira[: fim + 1] if fim >= 0 else primeira


def _instancia_da_chave(cabecalho: str) -> str | None:
    """A última parte da instância, numa chave nossa ou legada — ou None."""
    # A subchave opcional no fim: o Wine pode criar `Properties\…` debaixo do
    # device, e ela tem de sair junto — senão fica órfã no registro.
    m = re.match(
        r"^\[System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_(?:0CE6|0DF2)"
        r"\\\\([^\\\]]+)(?:\\\\[^\]]*)?\]$",
        cabecalho,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.match(
        r"^\[System\\\\ControlSet001\\\\Control\\\\DeviceClasses\\\\"
        + re.escape(KS)
        + r"\\\\##\?#USB#VID_054C&PID_(?:0CE6|0DF2)#([^#]+)#",
        cabecalho,
        re.I,
    )
    return m.group(1) if m else None


def e_bloco_nosso(bloco: str) -> bool:
    """Bloco gravado por nós (marcador) ou pela prova à mão de 17/09 (legado)."""
    inst = _instancia_da_chave(_cabecalho(bloco))
    if inst is None:
        return False
    return inst.upper().startswith(MARCADOR + "&") or bool(_LEGADO_DA_PROVA.match(inst))


def data4_do_dono(texto_sem_os_nossos: str, controle: Controle) -> list[bytes]:
    """Os Data4 que o PRÓPRIO prefixo já registrou para este pid/bus/dev.

    Procura nas duas formas em que o Wine guarda um `ContainerId`: o texto
    `{…}` das chaves `Enum` (o HID do winebus) e o blob VT_CLSID do endpoint no
    `MMDevices` (o `winepulse`). Os nossos blocos já saíram do texto, senão a
    pergunta responderia a si mesma.
    """
    alvo = controle.prefixo_do_container().lower()
    achados: list[bytes] = []
    for m in _GUID_TXT.finditer(texto_sem_os_nossos):
        guid = m.group(0).lower()
        if guid.startswith(alvo):
            d4 = bytes.fromhex(m.group(4) + m.group(5))
            if d4 not in achados:
                achados.append(d4)
    juntado = re.sub(r"\\\n\s*", "", texto_sem_os_nossos)
    for m in _BLOB_CONTAINER.finditer(juntado):
        bs = bytes(int(x, 16) for x in m.group(1).strip(",").split(","))
        if len(bs) < 16:
            continue
        g = bs[-16:]
        d1 = int.from_bytes(g[0:4], "little")
        d2 = int.from_bytes(g[4:6], "little")
        d3 = int.from_bytes(g[6:8], "little")
        guid = f"{{{d1:08x}-{d2:04x}-{d3:04x}-"
        if guid == alvo and g[8:] not in achados:
            achados.append(g[8:])
    return achados


def variantes_de_data4(controle: Controle, dono: list[bytes]) -> list[bytes]:
    """A política do Data4: o dono manda; sem dono, zero e `USEC`."""
    if dono:
        return dono
    variantes = [bytes(8)]
    if controle.usec is not None:
        usec = controle.usec.to_bytes(8, "little")
        if usec not in variantes:
            variantes.append(usec)
    return variantes


def _esc(valor: str) -> str:
    return valor.replace("\\", "\\\\")


def blocos_do_controle(controle: Controle, data4s: list[bytes], carimbo: int) -> list[str]:
    """Os quatro blocos por variante, no formato do `system.reg`."""
    base_id = f"USB\\VID_054C&PID_{controle.pid:04X}"
    saida: list[str] = []
    for n, d4 in enumerate(data4s):
        inst = f"{base_id}\\{MARCADOR}&{controle.bus:03d}&{controle.dev:03d}&{n}"
        iface = "##?#" + inst.replace("\\", "#") + "#" + KS
        link = "\\\\?\\" + inst.replace("\\", "#") + "#" + KS
        enum = "System\\\\ControlSet001\\\\Enum\\\\" + _esc(inst)
        dc = "System\\\\ControlSet001\\\\Control\\\\DeviceClasses\\\\" + KS + "\\\\" + _esc(iface)
        saida += [
            f"[{enum}] {carimbo}\n"
            '"Class"="USB"\n'
            f'"ClassGUID"="{CLASSE_USB}"\n'
            f'"ContainerId"="{container_id(controle, d4)}"\n'
            f'"DeviceDesc"="{controle.nome}"\n'
            f'"FriendlyName"="{controle.nome}"\n'
            f'"HardwareID"=str(7):"{_esc(base_id)}\\0"\n',
            f"[{dc}] {carimbo}\n" f'"DeviceInstance"="{_esc(inst)}"\n',
            f"[{dc}\\\\#] {carimbo}\n" f'"SymbolicLink"="{_esc(link)}"\n',
            f"[{dc}\\\\#\\\\Control] {carimbo}\n" '"Linked"=dword:00000001\n',
        ]
    return saida


def texto_novo(texto: str, controles: list[Controle], carimbo: int) -> str:
    """O `system.reg` com os nossos blocos refeitos, e só eles.

    Pura: nenhuma E/S, para a régua medir byte a byte.
    """
    blocos = _blocos(texto)
    fica = [b for b in blocos if not e_bloco_nosso(b)]
    sem_os_nossos = "\n".join(fica)
    novos: list[str] = []
    for c in controles:
        variantes = variantes_de_data4(c, data4_do_dono(sem_os_nossos, c))
        novos += blocos_do_controle(c, variantes, carimbo)
    if not novos:
        saida = sem_os_nossos
    else:
        base = sem_os_nossos if sem_os_nossos.endswith("\n") else sem_os_nossos + "\n"
        saida = base + "\n" + "\n".join(novos)
    return saida if saida.endswith("\n") else saida + "\n"


def _mesmos_blocos(a: str, b: str) -> bool:
    """O mesmo CONJUNTO de blocos, a menos de carimbo, `#time=` e ordem.

    O `wineserver` regrava o registro em ordem alfabética e acrescenta
    `#time=` a cada chave; comparar o texto cru faria este passo reescrever os
    megabytes do `system.reg` em todo lançamento, sem nada ter mudado.
    """

    def normal(texto: str) -> list[str]:
        saida = []
        for bloco in _blocos(texto):
            linhas = [ln for ln in bloco.rstrip("\n").split("\n") if not ln.startswith("#time=")]
            if linhas and linhas[0].startswith("["):
                linhas[0] = _cabecalho(linhas[0])
            saida.append("\n".join(linhas))
        return sorted(saida)

    return normal(a) == normal(b)


# --------------------------------------------------------------------------
# O prefixo
# --------------------------------------------------------------------------


def wineserver_do_prefixo_vivo(pfx: Path, proc: Path = Path("/proc")) -> bool:
    """Há um `wineserver` servindo ESTE prefixo? (o `WINEPREFIX` no environ dele)"""
    alvo = os.path.normpath(str(pfx))
    try:
        pids = [p for p in proc.iterdir() if p.name.isdigit()]
    except OSError:
        return False
    for p in pids:
        try:
            if (p / "comm").read_text().strip() != "wineserver":
                continue
            env = (p / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        for kv in env:
            if kv.startswith(b"WINEPREFIX="):
                valor = kv[len(b"WINEPREFIX=") :].decode(errors="replace")
                if os.path.normpath(valor) == alvo:
                    return True
    return False


@dataclass
class Resultado:
    controles: int = 0
    variantes: int = 0
    escreveu: bool = False
    #: "sem-registro" · "ocupado" · "" (quando fez o que tinha de fazer)
    motivo: str = ""


def aplicar(
    compatdata: Path,
    *,
    controles: list[Controle],
    proc: Path = Path("/proc"),
    carimbo: int | None = None,
) -> Resultado:
    """Refaz os nossos blocos no `system.reg` do prefixo, se algo mudou."""
    pfx = compatdata / "pfx"
    registro = pfx / "system.reg"
    resultado = Resultado(controles=len(controles))
    if not registro.is_file():
        resultado.motivo = "sem-registro"
        return resultado
    if wineserver_do_prefixo_vivo(pfx, proc):
        resultado.motivo = "ocupado"
        return resultado
    trava_caminho = compatdata / "pfx.lock"
    try:
        trava = os.open(trava_caminho, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        trava = -1
    try:
        if trava >= 0:
            try:
                fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                resultado.motivo = "ocupado"
                return resultado
        texto = registro.read_text(encoding="utf-8", errors="surrogateescape")
        novo = texto_novo(texto, controles, carimbo if carimbo is not None else int(time.time()))
        resultado.variantes = sum(1 for b in _blocos(novo) if e_bloco_nosso(b)) // 4
        if _mesmos_blocos(novo, texto):
            return resultado
        backup = registro.with_name(registro.name + _BACKUP)
        backup.write_bytes(registro.read_bytes())
        tmp = registro.with_name(registro.name + _TMP)
        tmp.write_text(novo, encoding="utf-8", errors="surrogateescape")
        os.replace(tmp, registro)
        resultado.escreveu = True
        return resultado
    finally:
        if trava >= 0:
            os.close(trava)


def prefixos_de_todas_as_bibliotecas() -> list[Path] | None:
    """Todo `compatdata/<appid>` com registro, ou None se esta cópia não sabe listar.

    Reusa o `camadas_vulkan.pastas_compatdata`, que já resolve biblioteca em
    outro disco e o mesmo `steamapps` por dois caminhos. Import TARDE e nas duas
    formas, como lá; na cópia avulsa instalada nenhuma resolve, e a resposta
    honesta é None — não uma lista vazia disfarçada de "não achei nada".
    """
    try:
        from . import camadas_vulkan as cv
    except ImportError:  # pragma: no cover - rodando como script da pasta
        try:
            import camadas_vulkan as cv  # type: ignore[no-redef]
        except ImportError:
            return None
    if not cv.sabe_enumerar():
        return None
    return [
        appid
        for compatdata in cv.pastas_compatdata()
        for appid in sorted(compatdata.iterdir())
        if (appid / "pfx" / "system.reg").is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    """CLI stdlib, usada pelo gancho de lançamento e pelo uninstall.

    Saídas: 0 feito (ou nada a fazer) · 1 erro · 2 não sei listar · 3 ocupado.
    """
    parser = argparse.ArgumentParser(
        description="Device de áudio KS do DualSense no prefixo Wine (háptica nativa)."
    )
    alvo = parser.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--prefixo", metavar="COMPATDATA",
                      help="compatdata/<appid> (o STEAM_COMPAT_DATA_PATH)")
    alvo.add_argument("--remover-de-todos", action="store_true",
                      help="uninstall: tira os nossos blocos de todo prefixo")
    parser.add_argument("--remover", action="store_true",
                        help="tira os nossos blocos e não grava nenhum")
    parser.add_argument("--sysfs", default="/sys", help=argparse.SUPPRESS)
    parser.add_argument("--udev-data", default="/run/udev/data", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.remover_de_todos:
        prefixos = prefixos_de_todas_as_bibliotecas()
        if prefixos is None:
            print("esta cópia não consegue listar os jogos; só o modo --prefixo funciona",
                  file=sys.stderr)
            return 2
        adiados = 0
        for compat in prefixos:
            try:
                if aplicar(compat, controles=[]).motivo == "ocupado":
                    adiados += 1
            except OSError as erro:
                print(f"{compat.name}: erro: {erro}", file=sys.stderr)
        if adiados:
            print(f"{adiados} prefixo(s) com jogo aberto — rode de novo com o jogo fechado",
                  file=sys.stderr)
            return 3
        return 0

    if args.remover:
        controles: list[Controle] = []
    else:
        sysfs, udev = Path(args.sysfs), Path(args.udev_data)
        # O cabo e o rádio, nesta ordem, e nunca o mesmo aparelho duas vezes:
        # quem tem placa de som fica com o cabo (ver `controles_no_radio`).
        controles = controles_no_cabo(sysfs, udev) + controles_no_radio(sysfs, udev)
    try:
        resultado = aplicar(Path(args.prefixo), controles=controles)
    except OSError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    if resultado.motivo == "ocupado":
        print("prefixo ocupado (wineserver vivo): o próximo lançamento refaz", file=sys.stderr)
        return 3
    if resultado.escreveu:
        print(f"device KS: {resultado.controles} controle(s), {resultado.variantes} instância(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script avulso
    raise SystemExit(main())
