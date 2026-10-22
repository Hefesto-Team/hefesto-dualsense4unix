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
direto e em modo produto (vpad `uhid`), na mão do usuário.

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

O REGISTRO É DOS APARELHOS, E TEM UM DONO DA LISTA — 02/10/2026
---------------------------------------------------------------

A-HAPTICA-E-POR-APARELHO-01, pela palavra de 29/09 (*«todas as features
são um por aparelho. sempre.»*). Os endpoints são um por DualSense da mesa
(`endpoint_de_haptica`), e o registro grava, no lançamento, um bloco por
endpoint vivo: um por aparelho. De 28/09 a 02/10 eram os quatro lugares, de pé
desde o primeiro DualSense (A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01). O preço,
que o usuário aceitou na pergunta: com o jogo aberto (`wineserver` vivo) nada se
grava, e o aparelho que chega depois não tem bloco até o jogo reabrir.

O cabo cujo aparelho tem endpoint SAI da lista: um laço nosso leva o endpoint
à placa dele (`integrations/haptica_do_cabo.py`), e placa e endpoint seriam
dois alvos para o mesmo controle. Quem diz que placa um endpoint serve é o
SERVIDOR (:func:`placas_servidas`), e não uma segunda conta aqui. O cabo sem
endpoint ancorado segue pela placa, pelo `BUSNUM-DEVNUM`, como sempre.

A lista tem UM dono, :func:`controles_do_registro`: o `main` deste curador (o
gancho de lançamento) e o `daemon/launch_env._device_ks_nos_lancadores` leem a
mesma função.

Este módulo é **100% stdlib de propósito**, como o `camadas_vulkan`: o
`install.sh` o materializa em `~/.local/share/hefesto-dualsense4unix/bin/` e o
`assets/hefesto-launch.sh` o roda com o `python3` do sistema, antes do Proton
subir o `wineserver`.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

KS = "{6994AD04-93EF-11D0-A3CC-00A0C9223196}"

#: todo caminho de DualSense (`remove_dualsense_media_devices`).
CLASSE_USB = "{36FC9E60-C465-11CF-8056-444553540000}"

VID_SONY = 0x054C

#: Os DualSense que têm placa USB Audio de 4 canais, e o nome que cada um usa.
MODELOS: dict[int, str] = {
    0x0CE6: "DualSense Wireless Controller",
    0x0DF2: "DualSense Edge Wireless Controller",
}

MARCADOR = "HEFESTOKS"

#: A classe MEDIA do Windows: a do device que o GE-Proton11-8 registra para os
#: caminhos Sony (patch 0206), na chave `Enum\\USB\\VID_054C&PID_…`. Com o
#: MEDIA vivo do Proton para o `ContainerId` de um controle, o dono é ele, e o
#: nosso não se escreve (:func:`containers_do_proton`).
CLASSE_MEDIA = "{4D36E96C-E325-11CE-BFC1-08002BE10318}"

_LEGADO_DA_PROVA = re.compile(r"^\d+&[0-9A-F]{8}$", re.I)

_BACKUP = ".bak.hefesto-audio-ks"
_TMP = ".hefesto-audio-ks-tmp"

_GUID_TXT = re.compile(
    r"\{([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})\}", re.I
)
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
    usec: int | None
    container_vid: int = VID_SONY
    container_pid: int | None = None

    @property
    def nome(self) -> str:
        return MODELOS[self.pid]

    def prefixo_do_container(self) -> str:
        """Os três primeiros campos do `ContainerId`, sem o Data4."""
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


def _usec_do_udev(dev_sysfs: Path) -> int | None:
    """O `USEC_INITIALIZED` do `usb_device`, perguntado à `libudev` (None = não sei).

    Desde 08/10/2026 não se lê mais o arquivo do banco do udev: o systemd o
    declara interno e muda o formato quando quer. Este módulo é copiado SOZINHO
    pelo `install.sh`, então a pergunta é um `ctypes` mínimo aqui dentro, e não
    um import do pacote (a mesma pergunta mora em `core/banco_do_udev.py`).
    """
    import ctypes

    try:
        lib = ctypes.CDLL("libudev.so.1")
        lib.udev_new.restype = ctypes.c_void_p
        lib.udev_unref.argtypes = [ctypes.c_void_p]
        lib.udev_device_new_from_syspath.restype = ctypes.c_void_p
        lib.udev_device_new_from_syspath.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.udev_device_get_property_value.restype = ctypes.c_char_p
        lib.udev_device_get_property_value.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.udev_device_unref.argtypes = [ctypes.c_void_p]
    except (OSError, AttributeError):
        return None
    contexto = lib.udev_new()
    if not contexto:
        return None
    try:
        dispositivo = lib.udev_device_new_from_syspath(contexto, str(dev_sysfs).encode())
        if not dispositivo:
            return None
        try:
            valor = lib.udev_device_get_property_value(dispositivo, b"USEC_INITIALIZED")
        finally:
            lib.udev_device_unref(dispositivo)
        return int(valor) if valor else None
    except (ValueError, ctypes.ArgumentError):
        return None
    finally:
        lib.udev_unref(contexto)


#: quem responde o `USEC_INITIALIZED` de um `usb_device` (injetável: a suíte
#: nunca pergunta ao udev da máquina).
LeitorDoUsec = Callable[[Path], "int | None"]


def controles_no_cabo(
    sysfs: Path = Path("/sys"), usec_do: LeitorDoUsec | None = None
) -> list[Controle]:
    """Os DualSense ligados por USB COM placa de som, lidos do sysfs.

    A raiz é injetável de propósito: a suíte nunca pode ler o controle do usuário
    (memória "subsystem novo faz a suíte tocar o aparelho do usuário").
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
        if not any(dev.glob("*/sound/card*")):
            continue
        bus, num = _ler(dev / "busnum"), _ler(dev / "devnum")
        if not (bus and num and bus.isdigit() and num.isdigit()):
            continue
        achados.append(
            Controle(pid=pid, bus=int(bus), dev=int(num), usec=(usec_do or _usec_do_udev)(dev))
        )
    return achados


#: dizer "isto é um DualSense" (`fill_device_info`, `pulse.c:668`).
_PROP_VID = "device.vendor.id"
_PROP_PID = "device.product.id"
_PROP_SYSFS = "sysfs.path"

def _pactl(argv: list[str]) -> str | None:
    """Roda um `pactl` curto. None em qualquer falha — ausência é resposta."""
    retrato = sys.modules.get("hefesto_dualsense4unix.integrations.retrato_do_som")
    resposta = retrato.responder(argv) if retrato is not None else None
    if resposta is not None:
        return resposta if isinstance(resposta, str) else None
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if retrato is not None:
            retrato.escreveu(argv)
    return proc.stdout if proc.returncode == 0 else None


@dataclass(frozen=True)
class _Item:
    """Um nó (`sink`) ou um fluxo (`sink-input`) do `pactl --format=json list`."""

    indice: int
    nome: str
    alvo: str
    propriedades: dict[str, str]

    def carrega(self, marca: str) -> bool:
        """A ``marca`` aparece em alguma propriedade (o nome que o dono deu)?"""
        return bool(marca) and any(marca in v for v in self.propriedades.values())


def _lista_do_pactl(
    tipo: str, runner: Callable[[list[str]], str | None]
) -> list[_Item] | None:
    """Os itens de ``sinks``/``sink-inputs`` pela porta do JSON; ``None`` = não sei.

    Este módulo é MATERIALIZADO sozinho ao lado do wrapper (só a stdlib, ver
    acima), então não importa a porta do pacote (`integrations/porta_do_som.py`,
    o leitor do daemon): lê o mesmo JSON, pelo mesmo contrato, em quinze linhas.
    Sem a porta do JSON o `pactl` imprime erro e a resposta é «não sei».
    """
    texto = runner(["pactl", "--format=json", "list", tipo])
    if texto is None or not texto.strip():
        return None
    try:
        bruto = json.loads(texto)
    except ValueError:
        return None
    if not isinstance(bruto, list):
        return None
    itens: list[_Item] = []
    for o in bruto:
        if not isinstance(o, dict) or not isinstance(o.get("index"), int):
            continue
        props = o.get("properties")
        alvo = o.get("sink") if "sink" in o else None
        itens.append(_Item(
            indice=o["index"],
            nome=_sem_nulo(o.get("name")),
            alvo="" if alvo is None else str(alvo),
            propriedades={str(k): _sem_nulo(v) for k, v in (
                props.items() if isinstance(props, dict) else ())},
        ))
    return itens


def _hexa(valor: str | None) -> int:
    """``0x054c`` ou ``054c`` como número; ausente ou ilegível é ``0`` (nó de ninguém)."""
    try:
        return int(valor or "0", 16)
    except ValueError:
        return 0


def _sem_nulo(valor: object) -> str:
    """O texto de um campo; ausente e `(null)` (o que o `pactl` põe no acento) são vazios."""
    texto = "" if valor is None else str(valor)
    return "" if texto == "(null)" else texto


def endpoints_de_mentira(
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[tuple[int, str]]:
    """(pid do controle, `sysfs.path`) de cada nó que se diz DualSense.

    Só o que o `winepulse` também leria: o VID/PID do proplist e o
    `sysfs.path`. Um nó sem `sysfs.path` fica de fora de propósito — dele o
    Wine tiraria `GUID_NULL`, que é o `ContainerId` de toda saída que não é
    USB, e um device KS declarando zero casaria com a caixa de som da pessoa.
    """
    nos = _lista_do_pactl("sinks", runner) or ()
    achados: list[tuple[int, str]] = []
    for no in nos:
        if not no.nome:
            continue
        vid = _hexa(no.propriedades.get(_PROP_VID))
        pid = _hexa(no.propriedades.get(_PROP_PID))
        caminho = no.propriedades.get(_PROP_SYSFS, "")
        if vid != VID_SONY or pid not in MODELOS or not caminho:
            continue
        achados.append((pid, caminho))
    return achados


def pai_usb_device(sysfs_path: str, sysfs: Path = Path("/sys")) -> Path | None:
    """O `usb_device` ACIMA de um caminho do sysfs — o que o udev acharia."""
    try:
        raiz = sysfs.resolve()
        atual = (sysfs / sysfs_path.lstrip("/")).resolve()
    except OSError:
        return None
    if atual != raiz and raiz not in atual.parents:
        return None
    while atual != raiz:
        atual = atual.parent
        if (atual / "busnum").is_file() and (atual / "devnum").is_file():
            return atual
    return None


def controles_no_radio(
    sysfs: Path = Path("/sys"),
    usec_do: LeitorDoUsec | None = None,
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[Controle]:
    """Um `Controle` por endpoint de mentira vivo, com os campos da ÂNCORA.

    A conta é a do `winepulse` com a MESMA entrada: o `PRODUCT`, o `BUSNUM`, o
    `DEVNUM` e o `USEC_INITIALIZED` do `usb_device` que o nó declara. Por isso
    não há nada a combinar entre quem monta o nó e quem grava o registro — os
    dois leem o mesmo lugar.

    **Desde 02/10/2026 os nós são os APARELHOS** (um por DualSense da mesa, em
    qualquer transporte; de 28/09 a 02/10 eram os quatro lugares), e o nome
    desta função ficou do tempo em que eram só do rádio. Quem monta a lista do
    registro é :func:`controles_do_registro`.
    """
    achados: list[Controle] = []
    for pid, caminho in endpoints_de_mentira(runner):
        ancora = pai_usb_device(caminho, sysfs)
        if ancora is None:
            continue
        # um DualSense ligado por USB sobe ao PRÓPRIO controle, e o
        # `controles_no_cabo` já o conhece. Sem esta linha, o mesmo aparelho
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
            usec=(usec_do or _usec_do_udev)(ancora),
            container_vid=a_vid,
            container_pid=a_pid,
        )
        if controle not in achados:
            achados.append(controle)
    return achados


FAMILIA_DO_LACO_DO_CABO = "haptica-do-cabo"
MARCA_DO_LACO_DO_CABO = f"hefesto-{FAMILIA_DO_LACO_DO_CABO}-"

def _lembrando(
    runner: Callable[[list[str]], str | None],
) -> Callable[[list[str]], str | None]:
    """O mesmo `runner`, com UMA pergunta por argv e o servidor mudo lembrado."""
    respostas: dict[tuple[str, ...], str | None] = {}
    mudo = False

    def perguntar(argv: list[str]) -> str | None:
        nonlocal mudo
        chave = tuple(argv)
        if chave in respostas:
            return respostas[chave]
        if mudo:
            return None
        resposta = runner(argv)
        respostas[chave] = resposta
        if resposta is None:
            mudo = True
        return resposta

    return perguntar


def placas_servidas(
    sysfs: Path = Path("/sys"),
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[tuple[int, int]]:
    """`(BUSNUM, DEVNUM)` de cada placa de DualSense que o endpoint de um aparelho já serve.

    A pergunta é ao SERVIDOR, e não a uma conta de assento: o laço do cabo é
    um fluxo que toca na placa do controle, e o nome dele carrega
    :data:`MARCA_DO_LACO_DO_CABO`. Do fluxo sai o sink; do sink, o
    `sysfs.path`; e do `sysfs.path`, o `usb_device` — a mesma subida que o
    `winepulse` faz (:func:`pai_usb_device`). Servidor mudo é lista vazia: o
    cabo segue pela placa, que é o caminho que já vibrava.
    """
    entradas = _lista_do_pactl("sink-inputs", runner) or ()
    alvos = {f.alvo for f in entradas if f.alvo and f.carrega(MARCA_DO_LACO_DO_CABO)}
    if not alvos:
        return []
    achadas: list[tuple[int, int]] = []
    for no in _lista_do_pactl("sinks", runner) or ():
        if str(no.indice) not in alvos:
            continue
        aparelho = pai_usb_device(no.propriedades.get(_PROP_SYSFS, ""), sysfs)
        if aparelho is None:
            continue
        bus, num = _ler(aparelho / "busnum"), _ler(aparelho / "devnum")
        if bus and num and bus.isdigit() and num.isdigit():
            par = (int(bus), int(num))
            if par not in achadas:
                achadas.append(par)
    return achadas


def indice_do_fluxo(
    marca: str,
    runner: Callable[[list[str]], str | None] = _pactl,
) -> str | None:
    """O índice do fluxo (sink-input) cujo bloco carrega ``marca``. ``None`` = não achei.

    O portão dos motores do cabo é o volume do fluxo do laço
    (`integrations/haptica_do_cabo`), e o índice muda a cada laço que sobe; o
    nome que o dono dos laços dá ao nó (:data:`MARCA_DO_LACO_DO_CABO` mais a
    marca do aparelho) aparece nas propriedades do fluxo, e é por ele que se acha.
    Mora aqui, ao lado de :func:`placas_servidas`, porque as duas leem o MESMO
    fluxo pela mesma marca: uma para o registro, a outra para o portão.
    """
    if not marca:
        return None
    for fluxo in _lista_do_pactl("sink-inputs", runner) or ():
        if fluxo.carrega(marca):
            return str(fluxo.indice)
    return None


def controles_do_registro(
    sysfs: Path = Path("/sys"),
    usec_do: LeitorDoUsec | None = None,
    runner: Callable[[list[str]], str | None] = _pactl,
) -> list[Controle]:
    """A lista que o registro grava — o DONO dela, desde 28/09/2026."""
    perguntar = _lembrando(runner)
    endpoints = controles_no_radio(sysfs, usec_do, perguntar)
    cabo = controles_no_cabo(sysfs, usec_do)
    if cabo:
        servidas = set(placas_servidas(sysfs, perguntar))
        cabo = [c for c in cabo if (c.bus, c.dev) not in servidas]
    return cabo + endpoints


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


def _data4_do_presente(controle: Controle, d4: bytes) -> bool:
    """O Data4 pode ser o deste aparelho? Zero sempre pode; outro, só o `USEC` dele.

    O GE-Proton11-8 (patch 0207) deixa de apagar os endpoints Sony persistidos,
    e o par bus/dev se repete depois de um reinício: sem esta pergunta, o
    `ContainerId` de um aparelho que já saiu manda no do que está na mesa. Sem
    o `USEC` à mão não há como dizer que não é este, e o dono continua valendo.
    """
    if d4 == bytes(8) or controle.usec is None:
        return True
    return d4 == controle.usec.to_bytes(8, "little")


def data4_do_dono(texto_sem_os_nossos: str, controle: Controle) -> list[bytes]:
    """Os Data4 que o PRÓPRIO prefixo já registrou para este pid/bus/dev, e que casam com ele."""
    alvo = controle.prefixo_do_container().lower()
    achados: list[bytes] = []
    for m in _GUID_TXT.finditer(texto_sem_os_nossos):
        guid = m.group(0).lower()
        if guid.startswith(alvo):
            d4 = bytes.fromhex(m.group(4) + m.group(5))
            if d4 not in achados and _data4_do_presente(controle, d4):
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
        if guid == alvo and g[8:] not in achados and _data4_do_presente(controle, g[8:]):
            achados.append(g[8:])
    return achados


_ENUM_SONY = re.compile(
    r"^\[System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_(?:0CE6|0DF2)"
    r"\\\\[^\\\]]+\]$",
    re.I,
)
_CONTAINER_DO_BLOCO = re.compile(r'^"ContainerId"="(\{[^}]+\})"$', re.I | re.M)
_CLASSE_DO_BLOCO = re.compile(r'^"(?:ClassGUID|Class)"="([^"]*)"$', re.I | re.M)


def containers_do_proton(texto_sem_os_nossos: str) -> set[str]:
    """Os `ContainerId` dos devices MEDIA que o próprio Proton registrou num DualSense."""
    achados: set[str] = set()
    for bloco in _blocos(texto_sem_os_nossos):
        if not _ENUM_SONY.match(_cabecalho(bloco)):
            continue
        classes = {c.upper() for c in _CLASSE_DO_BLOCO.findall(bloco)}
        container = _CONTAINER_DO_BLOCO.search(bloco)
        if container and classes & {CLASSE_MEDIA, "MEDIA"}:
            achados.add(container.group(1).lower())
    return achados


def o_proton_ja_cria(containers: set[str], controle: Controle) -> bool:
    """O Proton já tem um MEDIA VIVO para este aparelho? Então o dono é ele.

    Vivo é o mesmo pid/bus/dev com um Data4 que pode ser o deste aparelho: o
    0207 deixa no registro os de aparelhos que já saíram.
    """
    alvo = controle.prefixo_do_container().lower()
    for guid in containers:
        m = _GUID_TXT.fullmatch(guid)
        if (
            m
            and guid.startswith(alvo)
            and _data4_do_presente(controle, bytes.fromhex(m.group(4) + m.group(5)))
        ):
            return True
    return False


def controles_que_o_proton_cria(texto: str, controles: list[Controle]) -> list[Controle]:
    """Os controles cujo device KS o Proton já cria, no `system.reg` de `texto`."""
    sem_os_nossos = "\n".join(b for b in _blocos(texto) if not e_bloco_nosso(b))
    containers = containers_do_proton(sem_os_nossos)
    return [c for c in controles if o_proton_ja_cria(containers, c)]


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
    """O `system.reg` com os nossos blocos refeitos, e só eles."""
    blocos = _blocos(texto)
    fica = [b for b in blocos if not e_bloco_nosso(b)]
    sem_os_nossos = "\n".join(fica)
    novos: list[str] = []
    do_proton = containers_do_proton(sem_os_nossos)
    for c in controles:
        if o_proton_ja_cria(do_proton, c):
            continue
        variantes = variantes_de_data4(c, data4_do_dono(sem_os_nossos, c))
        novos += blocos_do_controle(c, variantes, carimbo)
    if not novos:
        saida = sem_os_nossos
    else:
        base = sem_os_nossos if sem_os_nossos.endswith("\n") else sem_os_nossos + "\n"
        saida = base + "\n" + "\n".join(novos)
    return saida if saida.endswith("\n") else saida + "\n"


def _mesmos_blocos(a: str, b: str) -> bool:
    """O mesmo CONJUNTO de blocos, a menos de carimbo, `#time=` e ordem."""

    def normal(texto: str) -> list[str]:
        saida = []
        for bloco in _blocos(texto):
            linhas = [ln for ln in bloco.rstrip("\n").split("\n") if not ln.startswith("#time=")]
            if linhas and linhas[0].startswith("["):
                linhas[0] = _cabecalho(linhas[0])
            saida.append("\n".join(linhas))
        return sorted(saida)

    return normal(a) == normal(b)


# A poda (O-REGISTRO-DO-PREFIXO-PERDE-O-SOM-QUE-NAO-EXISTE-MAIS-01, 15/10/2026):
# o Wine guarda toda saída e entrada de som que já viu, e o jogo com a biblioteca
# da Sony varre todas. Só o caminho `MMDevices\Audio\{Render,Capture}` entra.
_CHAVE_DO_SOM = re.compile(
    r"^\[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\MMDevices\\\\Audio\\\\"
    r"(?:Render|Capture)\\\\(\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\})(\\\\[^\]]*)?\]$",
    re.I,
)
_RAIZ_DO_SOM = "[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\MMDevices\\\\Audio"
_ESTADO = re.compile(r'^"DeviceState"=dword:([0-9a-f]{8})$', re.I | re.M)

#: `DEVICE_STATE_NOTPRESENT`: o endpoint que o Wine já viu e que não está mais lá.
AUSENTE = 0x4

#: o mapa nó → GUID do `winepulse`, no `user.reg` (o fluxo 0 é Render, o 1 é Capture).
_MAPA_DO_PULSE = re.compile(
    r"^\[Software\\\\Wine\\\\Drivers\\\\winepulse\.drv\\\\devices\\\\\d+,([^\]]*)\]$", re.I
)
_GUID_DO_MAPA = re.compile(r'^"guid"=hex:((?:[0-9a-f]{2},){15}[0-9a-f]{2})$', re.I | re.M)

#: onde o `mmdevapi` guarda a saída e a entrada padrão escolhidas.
_CHAVES_DO_PADRAO = (
    "[Software\\\\Wine\\\\Drivers]",
    "[Software\\\\Wine\\\\Drivers\\\\winepulse.drv]",
)
_VALOR_DO_PADRAO = re.compile(r'^"(?:Default\w*|Role\w*)"=', re.I)


def e_no_da_casa(nome: str) -> bool:
    """O nó é do Hefesto? `hefesto_som_*` e o `…_HEFESTO…` do endpoint de háptica."""
    return nome.startswith("hefesto_som_") or "_HEFESTO" in nome


def nos_vivos(runner: Callable[[list[str]], str | None] = _pactl) -> set[str] | None:
    """O nome de todo sink e source vivo; ``None`` = o servidor não respondeu."""
    sinks = _lista_do_pactl("sinks", runner)
    sources = _lista_do_pactl("sources", runner)
    if sinks is None or sources is None:
        return None
    return {i.nome for i in (*sinks, *sources) if i.nome}


def _guid_do_mapa(bloco: str) -> str | None:
    """O GUID de uma entrada do mapa (`"guid"=hex:`, 16 bytes na ordem do Windows)."""
    m = _GUID_DO_MAPA.search(re.sub(r"\\\n\s*", "", bloco))
    if m is None:
        return None
    g = bytes(int(x, 16) for x in m.group(1).split(","))
    d1 = int.from_bytes(g[0:4], "little")
    d2 = int.from_bytes(g[4:6], "little")
    d3 = int.from_bytes(g[6:8], "little")
    return f"{{{d1:08X}-{d2:04X}-{d3:04X}-{g[8:10].hex().upper()}-{g[10:].hex().upper()}}}"


def _sem_o_padrao_podado(bloco: str, podados: set[str]) -> str:
    """O bloco sem a linha do padrão (`Default*`/`Role*`) que aponta para um GUID podado."""
    cabecalho = _cabecalho(bloco)
    if not (cabecalho.startswith(_RAIZ_DO_SOM) or cabecalho in _CHAVES_DO_PADRAO):
        return bloco
    linhas = bloco.split("\n")
    fica = [
        ln for ln in linhas
        if not (_VALOR_DO_PADRAO.match(ln) and any(g in ln.upper() for g in podados))
    ]
    return bloco if len(fica) == len(linhas) else "\n".join(fica)


@dataclass(frozen=True)
class Poda:
    sistema: str
    usuario: str | None
    podados: int


def podar_o_som(sistema: str, usuario: str | None, vivos: set[str] | None) -> Poda:
    """Os dois registros sem o som ausente e sem o nó da casa que não está vivo.

    ``vivos`` é :func:`nos_vivos`; ``None`` (o servidor calado) poda só os
    ausentes, porque não saber não é saber que morreu. A contagem é de GUIDs.
    """
    guids: set[str] = set()
    for bloco in _blocos(sistema):
        m = _CHAVE_DO_SOM.match(_cabecalho(bloco))
        estado = _ESTADO.search(bloco) if m and not m.group(2) else None
        if m and estado and int(estado.group(1), 16) == AUSENTE:
            guids.add(m.group(1).upper())
    usuario_novo = usuario
    removidos: set[str] = set()
    if usuario is not None and vivos is not None:
        fica_usuario: list[str] = []
        for bloco in _blocos(usuario):
            m = _MAPA_DO_PULSE.match(_cabecalho(bloco))
            guid = _guid_do_mapa(bloco) if m and e_no_da_casa(m.group(1)) else None
            if m and guid and m.group(1) not in vivos:
                guids.add(guid)
                removidos.add(guid)
                continue
            fica_usuario.append(bloco)
        usuario_novo = "\n".join(fica_usuario)
    if not guids:
        return Poda(sistema, usuario, 0)
    fica_sistema: list[str] = []
    for bloco in _blocos(sistema):
        m = _CHAVE_DO_SOM.match(_cabecalho(bloco))
        if m and m.group(1).upper() in guids:
            removidos.add(m.group(1).upper())
            continue
        fica_sistema.append(_sem_o_padrao_podado(bloco, guids))
    if usuario_novo is not None:
        usuario_novo = "\n".join(_sem_o_padrao_podado(b, guids) for b in _blocos(usuario_novo))
    return Poda("\n".join(fica_sistema), usuario_novo, len(removidos))


# O controle que o prefixo guardou (22/10/2026). O InControl pula, no DirectInput, o
# VID:PID que o WMI do Wine marca com `&IG_`, e o `wbemprox` lista toda chave de `Enum`,
# presente ou não: o gêmeo XInput de um controle de meses atrás esconde o DualSense de hoje.
_ENUM_XINPUT = re.compile(
    r"^\[System\\\\(?:ControlSet\d+|CurrentControlSet)\\\\Enum\\\\WINEXINPUT"
    r"(?:\\\\([^\\\]]*))?(?:\\\\[^\]]*)?\]$",
    re.I,
)
_ENUM_COM_IG = re.compile(
    r"^\[System\\\\(?:ControlSet\d+|CurrentControlSet)\\\\Enum\\\\[^\\\]]+"
    r"\\\\([^\\\]]*&IG_[^\\\]]*)(?:\\\\[^\]]*)?\]$",
    re.I,
)
_INTERFACE_COM_IG = re.compile(
    r"^\[System\\\\(?:ControlSet\d+|CurrentControlSet)\\\\Control\\\\DeviceClasses"
    r"\\\\\{[^}\\\]]+\}\\\\([^\\\]]*&IG_[^\\\]]*)(?:\\\\[^\]]*)?\]$",
    re.I,
)


_VID_PID = re.compile(r"VID_[0-9A-F]{4}&PID_[0-9A-F]{4}", re.I)
# A chave do driver de cada aparelho (`"Driver"="{classe}\\NNNN"`): o Wine numera uma nova
# a cada aparelho que nasce, e a do aparelho esquecido ficaria órfã a cada lançamento.
_DRIVER = re.compile(r'^"Driver"="(\{[^"]+\}\\\\\d{4})"$', re.M)
_CLASSE = re.compile(
    r"^\[System\\\\(?:ControlSet\d+|CurrentControlSet)\\\\Control\\\\Class\\\\"
    r"(\{[^}\\\]]+\}\\\\\d{4})(?:\\\\[^\]]*)?\]$",
    re.I,
)


def _controle_esquecido(cabecalho: str) -> str | None:
    """O VID:PID da lembrança de controle XInput (vazio se não diz); ``None`` se a chave não é."""
    m = _ENUM_XINPUT.match(cabecalho)
    if m:
        achado = m.group(1) or ""
    else:
        m = _ENUM_COM_IG.match(cabecalho) or _INTERFACE_COM_IG.match(cabecalho)
        if m is None:
            return None
        achado = m.group(1)
    vid_pid = _VID_PID.search(achado)
    return vid_pid.group(0).upper() if vid_pid else ""


def esquecer_os_controles_que_se_foram(texto: str) -> tuple[str, int]:
    """O `system.reg` sem a lembrança de controle XInput, e quantos VID:PID saíram.

    Sai toda chave sob `Enum\\WINEXINPUT\\`, toda chave de `Enum` com `&IG_` no id e toda
    interface de `DeviceClasses` com `&IG_` (com as subchaves), e a chave de `Control\\Class`
    do driver de cada aparelho que saiu; o resto fica byte a byte.
    Roda em toda chamada de :func:`aplicar`: com o `wineserver` fora, só sobra lembrança.
    """
    fica: list[str] = []
    ids: set[str] = set()
    drivers_que_saem: set[str] = set()
    saiu = False
    for bloco in _blocos(texto):
        achado = _controle_esquecido(_cabecalho(bloco))
        if achado is None:
            fica.append(bloco)
        else:
            saiu = True
            drivers_que_saem.update(d.lower() for d in _DRIVER.findall(bloco))
            if achado:
                ids.add(achado)
    if not saiu:
        return texto, 0
    drivers_que_saem -= {d.lower() for b in fica for d in _DRIVER.findall(b)}

    def orfa(bloco: str) -> bool:
        m = _CLASSE.match(_cabecalho(bloco))
        return m is not None and m.group(1).lower() in drivers_que_saem

    return "\n".join(b for b in fica if not orfa(b)), len(ids)


def _gravar_com_backup(registro: Path, texto: str) -> None:
    """Um backup rotativo só, e a troca atômica."""
    backup = registro.with_name(registro.name + _BACKUP)
    backup.write_bytes(registro.read_bytes())
    tmp = registro.with_name(registro.name + _TMP)
    tmp.write_text(texto, encoding="utf-8", errors="surrogateescape")
    os.replace(tmp, registro)


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
    motivo: str = ""
    podados: int = 0
    do_proton: int = 0
    esquecidos: int = 0


def aplicar(
    compatdata: Path,
    *,
    controles: list[Controle],
    proc: Path = Path("/proc"),
    carimbo: int | None = None,
    podar: bool = False,
    vivos: set[str] | None = None,
) -> Resultado:
    """Refaz os nossos blocos no `system.reg` do prefixo, se algo mudou.

    Com ``podar``, o som que não existe mais sai antes (:func:`podar_o_som`),
    sob a mesma recusa e a mesma trava, e o `user.reg` também se grava. O
    controle XInput que o prefixo lembra sai SEMPRE, com ou sem ``podar``
    (:func:`esquecer_os_controles_que_se_foram`).
    """
    pfx = compatdata / "pfx"
    registro = pfx / "system.reg"
    usuario = pfx / "user.reg"
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
        base, resultado.esquecidos = esquecer_os_controles_que_se_foram(texto)
        usuario_txt, usuario_novo = None, None
        if podar:
            if usuario.is_file():
                usuario_txt = usuario.read_text(encoding="utf-8", errors="surrogateescape")
            poda = podar_o_som(base, usuario_txt, vivos)
            base, usuario_novo, resultado.podados = poda.sistema, poda.usuario, poda.podados
        novo = texto_novo(base, controles, carimbo if carimbo is not None else int(time.time()))
        resultado.do_proton = len(controles_que_o_proton_cria(base, controles))
        resultado.variantes = sum(1 for b in _blocos(novo) if e_bloco_nosso(b)) // 4
        if not _mesmos_blocos(novo, texto):
            _gravar_com_backup(registro, novo)
            resultado.escreveu = True
        if usuario_novo is not None and usuario_novo != usuario_txt:
            _gravar_com_backup(usuario, usuario_novo)
            resultado.escreveu = True
        return resultado
    finally:
        if trava >= 0:
            os.close(trava)


def prefixos_de_todas_as_bibliotecas() -> list[Path] | None:
    """Todo prefixo wine com registro, ou None se esta cópia não sabe listar."""
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
        prefixo
        for prefixo in cv.raizes_de_prefixo()
        if (prefixo / "pfx" / "system.reg").is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    """CLI stdlib, usada pelo gancho de lançamento e pelo uninstall."""
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

    vivos: set[str] | None = None
    if args.remover:
        controles: list[Controle] = []
    else:
        controles = controles_do_registro(Path(args.sysfs))
        vivos = nos_vivos()
    try:
        resultado = aplicar(Path(args.prefixo), controles=controles,
                            podar=not args.remover, vivos=vivos)
    except OSError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    if resultado.motivo == "ocupado":
        print("prefixo ocupado (wineserver vivo): o próximo lançamento refaz", file=sys.stderr)
        return 3
    if resultado.escreveu:
        print(f"device KS: {resultado.controles} controle(s), {resultado.variantes} instância(s), "
              f"podados={resultado.podados}, esquecidos={resultado.esquecidos}")
    if resultado.do_proton:
        print(f"o Proton já cria o device de {resultado.do_proton} controle(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script avulso
    raise SystemExit(main())
