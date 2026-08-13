"""Leitor de input do DualSense via evdev.

Contorna o conflito com `hid_playstation` kernel driver: quando o kernel
assume o controle como joystick (`/dev/input/event*`), `pydualsense` não
recebe reports de input — mas o próprio kernel expõe tudo via evdev.

Usado pelo `PyDualSenseController` como fonte primária de input; o
pydualsense mantém o caminho de output (`set_trigger`, `set_led`,
`set_rumble`), que continua funcionando via HID-raw.

Thread dedicada lê eventos e atualiza um snapshot protegido por RLock.
"""
from __future__ import annotations

import contextlib
import os
import select
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DUALSENSE_VENDOR = 0x054C
DUALSENSE_PIDS = {0x0CE6, 0x0DF2}  # DualSense + DualSense Edge

#: Unidades evdev por grau/s do giroscópio (`DS_GYRO_RES_PER_DEG_S` do
#: `hid-playstation.c`). É só o FALLBACK: a escala real vem do `absinfo` do
#: node aberto — ver `MotionSensorReader._on_device_opened`.
DUALSENSE_GYRO_RES_PER_DEG_S = 1024


#: Teto da faixa canônica do domínio Hefesto para eixos e gatilhos (0..255) —
#: é o que o DualSense já entrega CRU, e é a escala em que todo o resto do
#: projeto fala (perfis, curvas, vpad, repasse ao jogo). O normalizador existe
#: para que um aparelho com OUTRA faixa chegue aqui sem que nada abaixo saiba.
EIXO_MAX_HEFESTO = 255


@dataclass
class EvdevSnapshot:
    """Snapshot imutável do estado lido via evdev."""

    l2_raw: int = 0
    r2_raw: int = 0
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class EixoAbsoluto:
    """A faixa que um node evdev DECLARA para um eixo, lida do `absinfo`.

    Não é metadado decorativo: é o que separa "centro do analógico" de "talo à
    esquerda". O DualSense declara `0..255` e o Nintendo Pro declara
    `-32767..32767` — o mesmo valor CRU `0` significa *extremo esquerdo* num e
    *centro* no outro (medição de 06/08/2026, LUGAR-À-MESA-01).

    `flat` (zona morta declarada pelo aparelho; 0 no DualSense, 500 no Pro) e
    `fuzz` viajam junto porque quem for tratá-los depois precisa do número do
    APARELHO, não de uma tabela de "controles conhecidos" — que é a versão que
    só funciona nesta bancada. **Nenhum dos dois é aplicado hoje**, e isso é
    escolha declarada: aplicar zona morta é decisão de produto, não de leitura.
    """

    minimo: int = 0
    maximo: int = 0
    flat: int = 0
    fuzz: int = 0
    resolucao: int = 0

    @property
    def e_a_faixa_do_dualsense(self) -> bool:
        """True se a faixa declarada já É a faixa canônica da casa (0..255)."""
        return self.minimo == 0 and self.maximo == EIXO_MAX_HEFESTO


def normalizar_eixo(valor: int, faixa: EixoAbsoluto | None) -> int:
    """Converte o valor CRU de um eixo para os 0..255 do domínio Hefesto.

    Sem isto, `EvdevReader._handle_abs` fazia `valor & 0xFF` — que é a
    identidade para quem já nasce em 0..255 e um moedor de carne para quem não
    nasce: no Nintendo Pro (-32767..32767) o CENTRO do analógico vira `0`, que
    em 0..255 significa **talo à esquerda e para cima**. O personagem anda
    sozinho para o canto e não para.

    Duas propriedades, e as duas têm teste:

    1. **O DualSense sai bit a bit idêntico ao de hoje.** Faixa `0..255` (e
       faixa ilegível/ausente) cai no MESMO `& 0xFF` de sempre — inclusive para
       valor fora da faixa, onde `& 0xFF` e um `clamp` discordariam. Este é um
       caminho quente de input de TODOS os controles: mudar o número de quem já
       funcionava para consertar quem não funciona é o defeito, não a cura.
    2. **A conversão é do APARELHO**, montada do `absinfo` do node aberto — não
       de uma lista de VID/PID conhecidos, que funcionaria só nesta mesa.

    Aritmética inteira com arredondamento meio-para-cima
    (`(x*510 + span) // (2*span)`): o centro do Pro dá exatamente **128**, e não
    os 127 que um `//` cru devolveria. Valor fora da faixa é grampeado — vindo
    de um aparelho com faixa declarada, ele é ruído, não intenção.
    """
    if faixa is None or faixa.maximo <= faixa.minimo or faixa.e_a_faixa_do_dualsense:
        return valor & 0xFF
    span = faixa.maximo - faixa.minimo
    cru = min(max(valor, faixa.minimo), faixa.maximo)
    return ((cru - faixa.minimo) * (2 * EIXO_MAX_HEFESTO) + span) // (2 * span)


def faixas_de_eixo(caps: Any, ev_abs: int) -> dict[int, EixoAbsoluto]:
    """Mapa `código evdev -> faixa declarada` a partir do `capabilities()`.

    Uma leitura só: o `capabilities()` do python-evdev já traz o `absinfo`
    junto (default `absinfo=True`), então não custa um ioctl por eixo. Ler isto
    DENTRO do `_handle_event` custaria um ioctl por evento, a 250-765 Hz — é o
    mesmo motivo pelo qual o `MotionSensorReader` lê a resolução no open.

    Tolerante por contrato: `capabilities()` ilegível, entrada em formato
    inesperado ou valor não-inteiro deixa o eixo FORA do mapa, e quem consome
    cai no comportamento histórico (`& 0xFF`). Num caminho quente de input, o
    único modo de falha aceitável é **degradar para o que já rodava**.

    Um eixo PRESENTE mas sem faixa utilizável (dublê que lista só o código)
    entra no mapa mesmo assim: a presença é o que decide se o gatilho digital
    precisa ser sintetizado, e ela é verdadeira mesmo sem o `absinfo`.
    """
    faixas: dict[int, EixoAbsoluto] = {}
    try:
        entradas = caps.get(ev_abs, ())
    except Exception:
        return faixas
    if not isinstance(entradas, (list, tuple)):
        return faixas
    for entrada in entradas:
        if isinstance(entrada, tuple) and len(entrada) == 2:
            code, info = entrada
        else:
            code, info = entrada, None
        with contextlib.suppress(Exception):
            faixas[int(code)] = EixoAbsoluto(
                minimo=int(getattr(info, "min", 0) or 0),
                maximo=int(getattr(info, "max", 0) or 0),
                flat=int(getattr(info, "flat", 0) or 0),
                fuzz=int(getattr(info, "fuzz", 0) or 0),
                resolucao=int(getattr(info, "resolution", 0) or 0),
            )
    return faixas


def _read_input_attr(device_dir: str, attr: str) -> str:
    """Atributo (`phys`/`uniq`) do input device no sysfs ("" se ilegível)."""
    try:
        with open(f"{device_dir}/{attr}", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _is_virtual_evdev(event_path: str) -> bool:
    """True se o evdev é virtual NOSSO (vpad/teclado) ou de uinput, não físico.

    FEAT-DSX-GAMEPAD-FLAVOR-01 — CRÍTICO: o gamepad virtual com máscara DualSense
    tem o MESMO VID/PID/nome/caps do controle real, então sem este filtro o
    `find_dualsense_evdev` poderia retornar o PRÓPRIO device virtual do daemon
    (feedback loop: o daemon lendo a própria saída). Devices uinput vivem sob
    `/sys/devices/virtual/input/` — esses seguem SEMPRE virtuais (Steam Input,
    teclado do daemon).

    BLUEZ-UHID-01 (2026-07-19): a subárvore `/devices/virtual/misc/uhid/` deixou
    de implicar "nosso vpad" — com BlueZ ≥5.73 (UserspaceHID default) o
    bluetoothd cria os HIDs dos controles BT FÍSICOS via /dev/uhid, no mesmo
    lugar. Nela, quem decide é a IDENTIDADE do vpad: uniq com o prefixo do MAC
    forjado 02:fe. Atributos ilegíveis → True (na dúvida, o risco maior é o
    feedback loop de auto-adoção).

    PERNA-MORTA-PHYS-01 (2026-08-12) — **a perna do `phys` não decide nada
    aqui, e isto é MEDIDO**. Este texto dizia "phys `hefesto-vpad` (blueprint)
    **ou** uniq 02:fe", como se fossem dois sinais independentes. São um só: o
    `ps_allocate_input_dev` do `hid_playstation` copia `bustype`, `vendor`,
    `product`, `version`, `uniq` e `name` para o `input_dev`, e **não copia
    `phys`** (`assets/dkms/hid-playstation/hid-playstation.c:691-718`; a cópia
    do `uniq` está na 704, e não existe linha equivalente para `phys` — fonte
    conferido contra o `srcversion` do módulo carregado). Na mesa de 12/08, os
    22 nós de entrada com pai `DRIVER=playstation` (vpads, cabo e rádio) traziam
    `phys` VAZIO, contra 10 nós de `DRIVER=hid-generic` da mesma máquina com o
    `phys` preenchido — o `hidinput_allocate` genérico faz a cópia que o
    `hid_playstation` não faz.

    Arrancar a perna do `phys` das duas linhas abaixo não muda **nenhum** dos 55
    vereditos desta máquina; arrancar a do `uniq` muda 6, e todos para pior (os
    dois DualSense de rádio viram "virtual" e somem do daemon — a regressão
    BLUEZ-UHID-01 de volta). A linha fica de propósito, e por uma razão que não
    é hid_playstation: sem o driver DKMS carregado, o vpad cai no `hid-generic`,
    que preenche `phys` — e aí ela volta a valer. Ela é rede de outro cenário,
    não a segunda perna deste.

    **O que isto custa, e é dela decidir:** a redundância que o texto prometia
    não existe hoje. Se o `player_mac` mudasse de prefixo, ou se um controle de
    rádio chegasse com `uniq` ilegível, não há segunda perna — o produto
    classificaria um aparelho de VERDADE como virtual. Restaurá-la é trivial e
    já tem molde nesta casa: ler `HID_PHYS` do `uevent` do HID **pai**, que vem
    preenchido, como `core/backend_pydualsense.py:187` e
    `broker/hidraw_broker.py:272` já fazem. Não foi feito aqui porque mudaria
    comportamento sem que ninguém tenha pedido.
    """
    import os

    try:
        name = os.path.basename(event_path)  # ex.: "event12"
        link = os.path.realpath(f"/sys/class/input/{name}/device")
    except Exception:
        return False
    if "/devices/virtual/" not in link:
        return False
    if "/misc/uhid/" not in link:
        return True  # uinput puro (Steam Input, teclado do daemon)
    phys = _read_input_attr(link, "phys")
    uniq = _read_input_attr(link, "uniq").lower().replace(":", "")
    if not phys and not uniq:
        return True
    return phys.startswith("hefesto-vpad") or uniq.startswith("02fe")


#: Base do udev: um arquivo por device, nomeado `<tipo><major>:<minor>` ("c" de
#: char device, que é o que todo `/dev/input/event*` é). As linhas `E:` são as
#: PROPRIEDADES do nó — exatamente as que `udevadm info -q property` imprime.
#: Lemos o arquivo em vez de chamar o `udevadm` porque isto roda no open de um
#: reader, dentro do daemon: um fork por (re)conexão de controle seria caro e
#: acrescentaria uma dependência de binário externo onde basta um `open()`.
UDEV_DB_DIR = Path("/run/udev/data")


def libinput_ignora_device(event_path: Path | str | None) -> bool:
    """True se o udev marcou `LIBINPUT_IGNORE_DEVICE` neste nó de entrada.

    TOUCHPAD-DO-SISTEMA-01 (2026-08-09). É a pergunta "de quem é o cursor?":
    marcado, o libinput não enxerga o nó e o hefesto é a única fonte possível de
    ponteiro; desmarcado, quem move o cursor é o SISTEMA — e o hefesto tem de
    ficar fora, senão o mesmo dedo move o cursor duas vezes (o "engasgo" medido
    em 26/06 em `assets/76-dualsense-touchpad-libinput-ignore.rules`).

    Medido no nó vivo dela em 09/08/2026 (`/run/udev/data/c13:68`, o touchpad do
    DualSense por USB): a linha é literalmente ``E:LIBINPUT_IGNORE_DEVICE=1``.

    Falha de leitura (sem udev rodando, base ausente, nó sumido no meio do
    caminho) devolve **False**, e isso não é um chute: sem base do udev nenhuma
    regra foi aplicada ao nó, então o libinput o está enxergando — "o sistema é
    o dono" é a resposta FISICAMENTE correta, e é também a conservadora, porque
    o pior caso dela é o hefesto não mover o cursor, nunca movê-lo em dobro.
    """
    if event_path is None:
        return False
    try:
        st = os.stat(event_path)
        arquivo = UDEV_DB_DIR / f"c{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
        with open(arquivo, encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                if not linha.startswith("E:LIBINPUT_IGNORE_DEVICE="):
                    continue
                valor = linha.split("=", 1)[1].strip()
                # O udev grava "1"; qualquer valor não-vazio e não-"0" vale
                # como marcado (é como o próprio libinput lê a propriedade).
                return valor not in ("", "0")
    except OSError:
        return False
    return False


def _event_num(path: Path) -> int:
    """Número do node evdev (`event12` → 12) para ordenação determinística."""
    import re

    m = re.search(r"(\d+)$", path.name)
    return int(m.group(1)) if m else 0


class InputDirWatch:
    """Detector barato de mudança em /dev/input (PERF-MULTI-CONTROLLER-01).

    A enumeração completa (`discover_dualsense_evdevs`) abre TODOS os nodes de
    input (open + ioctls + close, ~10-40ms) — caro demais para rodar em timer
    de 2s no event loop (era o hitch rítmico do co-op). O conjunto de nodes só
    muda em hotplug/re-enumeração, e isso é observável por um `os.listdir`
    (~µs). Cada consumidor tem a SUA instância (o "mudou?" é relativo ao último
    `poll()` DESTE watch).
    """

    def __init__(self, root: str = "/dev/input") -> None:
        self._root = root
        self._last: frozenset[str] | None = None

    def poll(self) -> bool:
        """True se o conteúdo de /dev/input mudou desde o último poll (ou 1ª vez)."""
        import os

        try:
            current = frozenset(os.listdir(self._root))
        except OSError:
            current = frozenset()
        changed = current != self._last
        self._last = current
        return changed


def discover_dualsense_evdevs() -> dict[str, Path]:
    """Mapeia IDENTIDADE (MAC normalizado) -> node evdev de cada DualSense físico.

    FEAT-DSX-CONTROLLER-IDENTITY-01: a identidade universal de um controle no
    projeto é o MAC (o `uniq` do evdev == `serial_number` do hidapi, ambos
    normalizados via `norm_mac`). Nodes evdev são VOLÁTEIS (re-enumeração pós
    storm/replug muda `eventN`); a chave por MAC sobrevive. Nodes sem `uniq`
    legível (não deveria acontecer com hid_playstation) usam o próprio path
    como chave-fallback, prefixado com "path:" para nunca colidir com um MAC.

    Aqui o MAC pode ser tratado como identidade — diferente do inventário de
    externos, que precisa de `_external_dedup_key`. O endereço SINTÉTICO que
    colide entre aparelhos nasce no `hid-nintendo` degradado, e esta função é
    fechada em `DUALSENSE_VENDOR`/`DUALSENSE_PIDS`: quem chega até o
    `setdefault` passou pelo `hid_playstation`, cujo patch DKMS (0001, retry de
    feature report) não fabrica endereço nenhum — sem MAC do firmware o probe
    falha e o device nem aparece. Vale igual para
    `_discover_dualsense_por_nome`, que tem o mesmo filtro de vendor.

    Filtra devices virtuais (uinput, ver `_is_virtual_evdev`) e nodes sem caps
    de gamepad (touchpad/motion sensors ficam de fora).

    LUGAR-À-MESA-01/E2: passou a ser uma VISTA da descoberta única
    (`discover_gamepads`) — o laço, os filtros e a regra de chave continuam
    exatamente os mesmos, mas moram num lugar só. `com_sysfs=False` porque
    este caminho nunca leu driver/hidraw e não vai começar a pagar por eles.
    """
    return {
        gp.identidade: Path(gp.evdev_path)
        for gp in discover_gamepads(com_sysfs=False)
        if gp.especie == ESPECIE_DUALSENSE
    }


def find_all_dualsense_evdevs() -> list[Path]:
    """Todos os evdevs principais (gamepad) de DualSense FÍSICOS, ordenados.

    Compat: wrapper de `discover_dualsense_evdevs` que descarta a identidade.
    Ordena por número do node para eleição estável entre execuções.
    """
    return sorted(discover_dualsense_evdevs().values(), key=_event_num)


def find_dualsense_evdev() -> Path | None:
    """Retorna path do evdev principal do DualSense FÍSICO; None se não houver.

    Ignora devices virtuais (uinput) — ver `_is_virtual_evdev`. É o primeiro
    (ordem determinística) de `find_all_dualsense_evdevs`.
    """
    paths = find_all_dualsense_evdevs()
    return paths[0] if paths else None


# --- 8BIT-01: inventário READ-ONLY de gamepads externos -----------------

#: Nomes de barramento (linux/input.h). Hardcoded de propósito: python-evdev
#: nem sempre reexporta as constantes `BUS_*`; os dois valores são ABI estável
#: do kernel. Barramentos fora do mapa saem como hex ("0x06" etc.) — o
#: contrato é `usb | bluetooth | outro`, nunca um chute de nome.
_BUS_NAMES: dict[int, str] = {0x03: "usb", 0x05: "bluetooth"}

#: Teto da subida no sysfs ao procurar driver/hidraw a partir do input device.
#: A hierarquia real é rasa (input/inputN -> HID -> interface -> ...); 10
#: níveis cobrem USB e Bluetooth com folga sem risco de varrer /sys inteiro.
_SYSFS_WALK_MAX_LEVELS = 10


def _bus_name(bustype: int) -> str:
    """Nome legível do barramento evdev ("usb" | "bluetooth" | "0xNN")."""
    return _BUS_NAMES.get(bustype, f"0x{bustype:02x}")


def _sysfs_driver_hidraw(device_dir: str) -> tuple[str | None, str | None]:
    """(driver, hidraw) subindo o sysfs a partir do dir do input device.

    O evdev de um gamepad vive em `.../<pai>/input/inputN`; o driver do kernel
    e o nó hidraw irmão ficam em um ANCESTRAL (o HID device para hid-nintendo/
    hid-playstation, a interface USB para o xpad — que é USB-only e nem tem
    hidraw). Sobe até `_SYSFS_WALK_MAX_LEVELS` níveis colhendo:

    - ``driver``: basename do realpath do primeiro symlink `driver` encontrado
      (o driver MAIS PRÓXIMO do device — "nintendo", "xpad", ...).
    - ``hidraw``: primeiro nó de um subdir `hidraw/` (ex.: "/dev/hidraw6").

    Tolerante a ausência por contrato (8BIT-01): qualquer campo irresolvível
    sai None — inventário read-only nunca falha por sysfs incompleto.
    """
    import os

    driver: str | None = None
    hidraw: str | None = None
    current = device_dir
    for _ in range(_SYSFS_WALK_MAX_LEVELS):
        if driver is None:
            drv_link = os.path.join(current, "driver")
            if os.path.islink(drv_link):
                with contextlib.suppress(OSError):
                    driver = os.path.basename(os.path.realpath(drv_link)) or None
        if hidraw is None:
            hidraw_dir = os.path.join(current, "hidraw")
            if os.path.isdir(hidraw_dir):
                nodes: list[str] = []
                with contextlib.suppress(OSError):
                    nodes = sorted(
                        n for n in os.listdir(hidraw_dir) if n.startswith("hidraw")
                    )
                if nodes:
                    hidraw = f"/dev/{nodes[0]}"
        if driver is not None and hidraw is not None:
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return driver, hidraw


def _external_device_sysfs(event_path: str) -> tuple[str | None, str | None]:
    """Resolve (driver, hidraw) de um node evdev via /sys/class/input.

    Mesmo ponto de partida do `_is_virtual_evdev`: o realpath de
    `/sys/class/input/<eventN>/device` cai no dir do input device físico;
    a subida fica com `_sysfs_driver_hidraw`. Falha qualquer -> (None, None).
    """
    import os

    try:
        name = os.path.basename(event_path)
        device_dir = os.path.realpath(f"/sys/class/input/{name}/device")
    except Exception:
        return None, None
    return _sysfs_driver_hidraw(device_dir)


def _is_synthetic_uniq(uniq_raw: str | None, vendor: int, product: int) -> bool:
    """True se o `uniq` é o endereço SINTÉTICO do `hid-nintendo`, não o do aparelho.

    O patch `0003-HID-nintendo-pad-USB-commands-and-survive-no-dev-inf.patch`
    (parâmetro `usb_probe_degrade`) FABRICA um endereço quando o controle não
    responde ao `REQ_DEV_INFO` no cabo — o caso dos clones. A receita é
    `02` + VID + PID + número do barramento: o `02` marca "administrado
    localmente" (nunca colide com OUI de fabricante) e o resto é só a tupla
    VID/PID/bus. Não há um bit do APARELHO ali, e o próprio comentário do patch
    admite: "two identical clones plugged at once would share it".

    Casamos só os cinco primeiros octetos (`02` + VID + PID). O sexto é o
    `hdev->bus` visto pelo hid-core, que não temos como reproduzir com garantia
    a partir do `bustype` do evdev — exigi-lo faria a detecção falhar em
    SILÊNCIO, que é exatamente o modo de falha que este código existe para
    impedir. Um endereço real que casasse esse prefixo por acaso teria de ser
    localmente administrado E carregar o próprio VID/PID: não acontece.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    hexs = norm_mac(uniq_raw)
    if hexs is None or len(hexs) != 12:
        return False
    return hexs[:10] == f"02{vendor:04x}{product:04x}"


def _evdev_owner_dir(event_path: str) -> str | None:
    """Diretório sysfs do APARELHO dono deste node evdev (None se irresolvível).

    `/sys/class/input/<eventN>/device` cai em `<dono>/input/inputN`; o dono é a
    instância HID (`0005:054C:0CE6.0008`) para tudo que passa pelo hid-core —
    USB e Bluetooth — ou a interface USB (`3-1:1.0`) para o `xpad`, que não é
    HID. Serve de identidade de aparelho por duas propriedades observadas no
    sysfs vivo:

    - é ÚNICO por construção: o hid-core numera as instâncias em sequência, então
      dois clones idênticos ligados juntos caem em dirs diferentes
      (`...:2009.0001` contra `...:2009.0006`);
    - é COMPARTILHADO pelos vários nodes evdev do MESMO aparelho — gamepad, IMU,
      touchpad e headset jack são todos filhos da mesma instância HID. É isso que
      mantém a deduplicação colapsando um controle numa entrada só.

    Deliberadamente NÃO usamos `phys` para este papel: ele vem VAZIO em TODO
    aparelho da classe DualSense, porque o `ps_allocate_input_dev` do
    `hid_playstation` não copia `hdev->phys` para o `input_dev`
    (`assets/dkms/hid-playstation/hid-playstation.c:691-718`).

    PERNA-MORTA-PHYS-01 (2026-08-12): este texto dizia "nos controles por
    Bluetooth (que o BlueZ cria via /dev/uhid) ele vem VAZIO", atribuindo a
    ausência ao TRANSPORTE. Medido na mesa de 12/08: o `phys` vem vazio também
    nos DualSense por CABO, que nem passam por uhid — nos 22 nós com pai
    `DRIVER=playstation` sem exceção. A causa é o driver, não o transporte, e a
    diferença importa: quem lesse o texto velho poderia concluir que `phys`
    serve de identidade no cabo. Não serve em lugar nenhum desta classe.
    """
    import os

    try:
        name = os.path.basename(event_path)
        device_dir = os.path.realpath(f"/sys/class/input/{name}/device")
    except Exception:
        return None
    if not device_dir:
        return None
    parent = os.path.dirname(device_dir)
    if os.path.basename(parent) == "input":
        # Layout canônico `<dono>/input/inputN`: sobe os dois níveis.
        return os.path.dirname(parent) or None
    # Layout inesperado: fica no dir do próprio input device, que ainda é
    # por-aparelho (só que mais fino — pode não colapsar nodes irmãos).
    return device_dir


def _external_dedup_key(
    event_path: str, uniq_raw: str, vendor: int, product: int
) -> str:
    """Chave de IDENTIDADE DE APARELHO para deduplicar o inventário de externos.

    Ordem de preferência:

    1. o MAC (`uniq`) QUANDO ele identifica o aparelho — é a identidade universal
       do projeto (FEAT-DSX-CONTROLLER-IDENTITY-01): sobrevive a replug e casa a
       sessão USB com a sessão Bluetooth do MESMO controle;
    2. o dono no sysfs (`dev:<instância HID>`) quando o `uniq` falta ou é o
       endereço sintético do `hid-nintendo` degradado — que é a MESMA string para
       dois clones idênticos (ver `_is_synthetic_uniq`). Sem esta perna o segundo
       clone era ENGOLIDO pelo `setdefault` e sumia do inventário inteiro: não
       aparecia na GUI, não recebia número de jogador, sem uma linha de log. Com
       o alvo de quatro controles simultâneos e dois aparelhos Nintendo-class
       (Pro genuíno + 8BitDo, ambos 057e:2009), isso é rotina, não borda;
    3. o próprio node (`path:`), último recurso quando nem o sysfs responde.

    Os três espaços são disjuntos por prefixo: um MAC normalizado é só dígito hex
    minúsculo, então nunca colide com `dev:` nem com `path:`.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    mac = norm_mac(uniq_raw)
    if mac is not None and not _is_synthetic_uniq(uniq_raw, vendor, product):
        return mac
    dono = _evdev_owner_dir(event_path)
    return f"dev:{dono}" if dono else f"path:{event_path}"


#: As duas espécies que a descoberta única distingue. Não é taxonomia de
#: marca: é DE QUEM É O CAMINHO. `dualsense` é o domínio do caminho existente
#: (co-op, vpad, hidraw broker); `external` é todo o resto do plástico da mesa.
ESPECIE_DUALSENSE = "dualsense"
ESPECIE_EXTERNAL = "external"


@dataclass(frozen=True)
class GamepadDescoberto:
    """Um controle FÍSICO visto pela descoberta única, com tudo o que se sabe.

    Um registro por PLÁSTICO (os vários nodes de um mesmo aparelho — gamepad,
    IMU, touchpad — colapsam num só), com a `identidade` já resolvida pela
    regra da própria espécie. É o que a LUGAR-À-MESA-01 chama de *um produtor
    de identidade em vez de dois*.
    """

    especie: str
    identidade: str
    evdev_path: str
    name: str
    vid: str
    pid: str
    bus: str
    uniq: str | None
    driver: str | None
    hidraw: str | None
    #: `código evdev -> faixa declarada` (ver `EixoAbsoluto`). É o que o
    #: normalizador consome; vazio quando o node não declara `absinfo` legível.
    eixos: dict[int, EixoAbsoluto] = field(default_factory=dict)

    def como_entrada_de_inventario(self) -> dict[str, Any]:
        """O dict do inventário 8BIT-01, com as MESMAS oito chaves de sempre.

        O `eixos` fica DE FORA de propósito: este dict viaja no JSON-RPC e é
        mutado pelos consumidores (`holders`, identidade carimbada). Chave nova
        num payload que a GUI já lê é mudança que ninguém pediu.
        """
        return {
            "name": self.name,
            "vid": self.vid,
            "pid": self.pid,
            "bus": self.bus,
            "uniq": self.uniq,
            "driver": self.driver,
            "evdev_path": self.evdev_path,
            "hidraw": self.hidraw,
        }


def _int_ou(valor: Any, reserva: int) -> int:
    """`int(valor)` tolerante — devolve `reserva` se o campo não converter."""
    try:
        return int(valor)
    except Exception:
        return reserva


def discover_gamepads(*, com_sysfs: bool = True) -> list[GamepadDescoberto]:
    """Descoberta ÚNICA: abre cada node de /dev/input UMA vez e classifica.

    LUGAR-À-MESA-01/E2. Até aqui havia DOIS laços — `discover_dualsense_evdevs`
    e `discover_external_gamepads` — que abriam **todos** os nodes, cada um com
    a sua regra de identidade e o seu filtro. Quem precisava dos dois lados
    pagava a enumeração duas vezes, e a identidade de um mesmo aparelho tinha
    dois donos. Agora as duas portas antigas são VISTAS desta função, com o
    contrato de retorno intacto.

    Regras preservadas, uma a uma:

    - virtuais fora (`_is_virtual_evdev`) — cobre o vpad uhid do daemon, os
      vpads do Steam Input e o teclado virtual;
    - só nodes com caps de gamepad (`BTN_GAMEPAD`/`BTN_SOUTH`): touchpad e
      motion sensors ficam de fora;
    - espécie `dualsense` para `DUALSENSE_VENDOR` + `DUALSENSE_PIDS`,
      `external` para todo o resto;
    - **identidade por espécie, e a diferença é medida**: o DualSense usa o MAC
      direto (`norm_mac(uniq)`, `path:` como último recurso) porque esta perna é
      fechada em vendor e o `hid_playstation` não fabrica endereço; o externo
      usa `_external_dedup_key`, que sabe descartar o endereço SINTÉTICO do
      `hid-nintendo` degradado — igual para dois clones idênticos;
    - 1º node vence por espécie+identidade (ordem estável por número de node).

    `com_sysfs=False` pula a subida no sysfs (driver/hidraw): é o que o caminho
    do co-op nunca leu e não vai começar a pagar.

    **O que ela NÃO faz: adotar ninguém.** Devolver um externo aqui é dizer que
    ele existe e qual a forma dos eixos dele — não é dar-lhe vpad nem lugar na
    partida. O veto de 19/07 (*"externo não ganha controle virtual"*) segue de
    pé; quem o derruba é a `E3`, e ela é dela.

    CUSTO (lição PERF-MULTI-CONTROLLER-01): abre TODOS os nodes de /dev/input
    (open + ioctls + close, ~10-40 ms) — PROIBIDO no event loop do daemon e em
    qualquer caminho quente (`state_full`/tick). **GRAU: SUSPEITA COM
    MECANISMO** sobre o delta: o caminho DualSense passa a chamar
    `capabilities()` também nos nodes de outro vendor (antes o filtro de vendor
    curto-circuitava antes) — alguns ioctls a mais por node, num caminho que já
    é gated pelo `InputDirWatch` e só roda em hotplug. Não foi medido com
    aparelho na mesa.
    """
    try:
        from evdev import InputDevice, ecodes, list_devices
    except ImportError:
        return []
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    encontrados: dict[tuple[str, str], GamepadDescoberto] = {}
    for path in sorted(list_devices(), key=lambda p: _event_num(Path(p))):
        if _is_virtual_evdev(path):
            continue
        try:
            dev = InputDevice(path)
            try:
                vendor = int(dev.info.vendor)
                product = int(dev.info.product)
                caps = dev.capabilities()
                buttons = caps.get(ecodes.EV_KEY, [])
                if not (
                    ecodes.BTN_GAMEPAD in buttons or ecodes.BTN_SOUTH in buttons
                ):
                    continue
                uniq_raw = str(getattr(dev, "uniq", "") or "").strip()
                if vendor == DUALSENSE_VENDOR and product in DUALSENSE_PIDS:
                    especie = ESPECIE_DUALSENSE
                    identidade = norm_mac(uniq_raw) or f"path:{path}"
                else:
                    especie = ESPECIE_EXTERNAL
                    identidade = _external_dedup_key(path, uniq_raw, vendor, product)
                driver, hidraw = (
                    _external_device_sysfs(path) if com_sysfs else (None, None)
                )
                # `name`/`bustype` são lidos com tolerância porque as duas
                # portas antigas divergiam: a do DualSense nunca os tocava, a
                # dos externos morria no `int(...)` e o node sumia do
                # inventário SEM UMA LINHA DE LOG. Unificar com a leitura
                # estrita reprovaria os nodes que a porta do DualSense sempre
                # aceitou; unificar com a tolerante só troca o sumiço silencioso
                # por uma entrada com o campo em branco. Kernel real sempre
                # publica os dois.
                encontrados.setdefault(
                    (especie, identidade),
                    GamepadDescoberto(
                        especie=especie,
                        identidade=identidade,
                        evdev_path=str(path),
                        name=str(getattr(dev, "name", "") or ""),
                        vid=f"{vendor:04x}",
                        pid=f"{product:04x}",
                        bus=_bus_name(_int_ou(getattr(dev.info, "bustype", 0), 0)),
                        uniq=uniq_raw or None,
                        driver=driver,
                        hidraw=hidraw,
                        eixos=faixas_de_eixo(caps, ecodes.EV_ABS),
                    ),
                )
            finally:
                dev.close()
        except Exception:
            continue
    return list(encontrados.values())


def localizar_node_por_identidade(identidade: str) -> Path | None:
    """Node evdev do controle de `identidade` — DualSense **ou** externo.

    É o REENCONTRO da `E2`: `EvdevReader._locate` só sabia procurar em
    `discover_dualsense_evdevs()`, então um controle externo que perdesse o
    node (replug, re-enumeração pós-storm, troca de barramento) nunca mais era
    achado — o `eventN` é volátil e a identidade é o que sobrevive.

    Não confere espécie de propósito: quem chama já escolheu O CONTROLE, e a
    identidade é única entre eles. Quem NÃO tem alvo continua caindo em
    `find_dualsense_evdev`, que segue fechado em Sony — sem alvo, adotar um
    externo seria adoção por acidente.
    """
    for gp in discover_gamepads(com_sysfs=False):
        if gp.identidade == identidade:
            return Path(gp.evdev_path)
    return None


def discover_external_gamepads() -> list[dict[str, Any]]:
    """Inventário READ-ONLY de gamepads físicos NÃO-DualSense (8BIT-01).

    Enumera os evdevs com caps de gamepad (BTN_GAMEPAD/BTN_SOUTH) SEM filtro
    de vendor — 8BitDo em modo Switch (057e:2009/hid-nintendo), X-input
    (045e:028e/xpad), qualquer marca. Exclusões, nesta ordem:

    1. Virtuais via `_is_virtual_evdev` (`/devices/virtual/`): cobre o vpad
       uhid do daemon (vive sob /devices/virtual/misc/uhid), os vpads do
       Steam Input e o teclado virtual do próprio daemon (uinput) — que, além
       de virtual, nem tem caps de gamepad.
    2. DualSense/Edge físicos (`DUALSENSE_VENDOR` + `DUALSENSE_PIDS`): são o
       domínio do caminho existente (`discover_dualsense_evdevs`); este
       inventário é SÓ dos externos — uma lista de controles com um dono só.

    Por device: name, vid/pid (hex 4 dígitos minúsculo, ex. "057e"), bus
    ("usb" | "bluetooth" | "0xNN"), uniq (MAC como o kernel reporta, ou
    None), driver do kernel (readlink no sysfs, tolerante a ausência),
    evdev_path e hidraw irmão (quando resolvível). Tudo JSON-serializável.

    Dedup pela IDENTIDADE DE APARELHO (`_external_dedup_key`): 1º node vence
    (ordem estável por número de node). A chave é o MAC quando ele identifica o
    aparelho e o dono no sysfs quando não identifica — `uniq` ausente, ou o
    endereço SINTÉTICO que o `hid-nintendo` degradado fabrica, igual para dois
    clones idênticos. Colapsar os vários nodes de um controle (gamepad, IMU,
    touchpad) numa entrada só continua sendo requisito: os dois lados têm teste.

    CUSTO (lição PERF-MULTI-CONTROLLER-01): abre TODOS os nodes de /dev/input
    (open + ioctls + close, ~10-40 ms) — PROIBIDO no event loop do daemon e
    em qualquer caminho quente (`state_full`/tick). Consumidor canônico: o
    handler `controller.list` sob opt-in, via thread.

    LUGAR-À-MESA-01/E2: virou uma VISTA da descoberta única
    (`discover_gamepads`). As oito chaves do dict e a regra de dedup são as
    mesmas; cada chamada devolve dicts NOVOS, porque os consumidores os mutam
    (o `controller.list` carimba `holders` e a identidade do aparelho).
    """
    return [
        gp.como_entrada_de_inventario()
        for gp in discover_gamepads()
        if gp.especie == ESPECIE_EXTERNAL
    ]


class _EvdevReconnectLoop:
    """Loop base de leitura evdev com auto-reconnect e backoff exponencial.

    Encapsula o padrão duplicado entre `EvdevReader` e `TouchpadReader`.
    Subclasses implementam hooks: `_find_device`, `_handle_event`,
    `_reset_on_disconnect`, `_log_prefix` (prefixo para log events).
    """

    _device_path: Path | None
    _stop_flag: threading.Event
    _thread: threading.Thread | None
    # HANG-01: self-pipe de wake + flag de reopen — ver `__init__` abaixo.
    _reopen_flag: threading.Event
    _wake_lock: threading.Lock
    _wake_r: int
    _wake_w: int
    # InputDevice atualmente aberto pelo loop (ou None). Permite grab/ungrab
    # em runtime de fora da thread (FEAT-DSX-GAMEPAD-FLAVOR-01).
    _active_dev: Any = None
    # Watch barato de /dev/input para o is_stale (lazy; PERF-MULTI-CONTROLLER-01).
    _stale_watch: Any = None
    _THREAD_NAME: ClassVar[str] = "hefesto-evdev-base"
    #: HANG-01: teto de latência do select por iteração do loop de leitura —
    #: sem isto, `_stop_flag`/`_reopen_flag` só seriam vistos quando o
    #: self-pipe acordasse; com o timeout, mesmo um wake perdido/atrasado é
    #: recuperado em ≤ este intervalo (mesma constante do PhysicalReportReader,
    #: `_SELECT_TIMEOUT_S`).
    _SELECT_TIMEOUT_S: ClassVar[float] = 0.5

    def __init__(self) -> None:
        """Self-pipe de wake (HANG-01, padrão GYRO-FD-01/PhysicalReportReader).

        Chamado pelas subclasses via `super().__init__()` antes dos campos
        próprios. `request_reopen()`/`stop()` NUNCA fecham o `InputDevice` de
        fora — fechar de outra thread enquanto a THREAD DONA está em
        select/read no mesmo fd libera o número com ela ainda presa nele; um
        open concorrente (retarget, novo device, watchdog) recicla o número e
        o loop passaria a ler um fd ALHEIO (o wedge de GIL do incidente de
        16:08 nasceu de um close cross-thread num cenário correlato). Aqui os
        dois só SINALIZAM (flag + 1 byte no self-pipe); quem fecha é sempre a
        própria thread, no `finally` do `_run`.
        """
        self._reopen_flag = threading.Event()
        self._wake_lock = threading.Lock()
        self._wake_r, self._wake_w = self._novo_wake_pipe()

    @staticmethod
    def _novo_wake_pipe() -> tuple[int, int]:
        r, w = os.pipe()
        os.set_blocking(r, False)
        os.set_blocking(w, False)
        return r, w

    def _wake(self) -> None:
        """1 byte no self-pipe: acorda o select da thread dona na hora."""
        with self._wake_lock:
            if self._wake_w >= 0:
                with contextlib.suppress(OSError):
                    os.write(self._wake_w, b"w")

    def _drain_wake(self) -> None:
        """Esvazia o self-pipe (não-bloqueante; bytes velhos não acumulam)."""
        with contextlib.suppress(OSError):
            while os.read(self._wake_r, 64):
                pass

    def _close_wake_pipe(self) -> None:
        with self._wake_lock:
            for attr in ("_wake_r", "_wake_w"):
                fd = getattr(self, attr, -1)
                if fd >= 0:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                    setattr(self, attr, -1)

    def _wait_ready(self, dev: Any) -> list[Any]:
        """Espera o fd do `dev` OU o self-pipe de wake ficarem prontos.

        Extraído em método próprio (em vez de `select.select` inline) para os
        testes conseguirem simular prontidão/timeout sem precisar de fds
        reais — só esta chamada toca o `select` de verdade.
        """
        ready, _, _ = select.select(
            [dev.fd, self._wake_r], [], [], self._SELECT_TIMEOUT_S
        )
        return list(ready)

    def _find_device(self) -> Path | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _handle_event(self, event: Any, ecodes: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    def _reset_on_disconnect(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _reapply_grab(self, dev: Any) -> None:
        """Hook de (re)aplicação de grab ao abrir o device. No-op na base."""

    def _on_device_opened(self, dev: Any) -> None:
        """Hook genérico "o device acabou de abrir". No-op na base.

        Existe separado do `_reapply_grab` porque nem toda subclasse quer
        grab, mas várias precisam ler METADADOS do node recém-aberto — o
        `MotionSensorReader` lê aqui a `resolution` do absinfo (é ela que
        converte o valor cru em graus/s, e ela muda quando o kernel recria
        o node). Ler isso de dentro de `_handle_event` custaria um ioctl
        por evento a 250-765 Hz; ler no open custa um por conexão.
        """

    def _log_prefix(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def is_available(self) -> bool:
        return self._device_path is not None

    def refresh_device(self) -> bool:
        """Re-procura o device de input quando ainda não há um path.

        Hotplug-safe: o `__init__` chama `_find_device()` uma única vez. Se o
        daemon subiu sem o controle (offline), o path nasce `None` e jamais
        seria reavaliado — o evdev criado pelo kernel hid_playstation ao plugar
        o controle nunca era localizado. `connect()` chama isto a cada
        (re)conexão para fechar essa janela (BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01).
        """
        if self._device_path is None:
            self._device_path = self._find_device()
        return self._device_path is not None

    def is_stale(self) -> bool:
        """True se o reader está preso num node de evdev OBSOLETO.

        Caso-alvo (FEAT-DSX-EVDEV-WATCHDOG-01): após uma re-enumeração do
        controle (storm -71, replug rápido) o kernel cria um novo
        /dev/input/eventN, mas o read_loop pode seguir bloqueado no fd antigo SEM
        receber ENODEV — leitura zumbi, controle "morto" sem erro. Detectamos
        comparando o path aberto com o canônico atual do finder: se ele aponta
        agora para um node DIFERENTE (e não-None), o nosso está obsoleto.

        IDLE-SAFE: ficar parado não muda o node canônico, então isto NUNCA dispara
        por ociosidade — só por troca real de node. (O daemon ainda cruza com o
        HID: só chama o watchdog quando o controller reporta conectado.)
        """
        held = self._device_path
        if held is None:
            return False  # sem device aberto: o loop de reconexão já cobre
        # PERF-MULTI-CONTROLLER-01: o node canônico só muda se /dev/input mudou
        # — checagem por listdir (~µs) evita a enumeração completa (~10-40ms)
        # a cada tick do watchdog. 1ª chamada estabelece baseline e verifica.
        watch = getattr(self, "_stale_watch", None)
        if watch is None:
            watch = InputDirWatch()
            self._stale_watch = watch
            watch.poll()
        elif not watch.poll():
            return False
        current = self._find_device()
        if current is None:
            return False  # finder transitório/sem node: conservador, não reabre
        return current != held

    def request_reopen(self, reason: str = "watchdog") -> None:
        """Pede à thread dona que largue o device atual e reabra o canônico.

        HANG-01: NÃO fecha mais o fd de fora (era o `dev.close()` cross-thread
        do HEAD) — zera o path em cache (próximo ciclo re-localiza o node
        certo) e só SINALIZA (`_reopen_flag` + wake do self-pipe); é a própria
        thread do `_run` que larga o device, no `finally` dela. Best-effort.
        """
        logger.info(f"{self._log_prefix()}_reopen_requested", reason=reason)
        self._device_path = None
        self._reopen_flag.set()
        self._wake()

    def start(self) -> bool:
        if not self.is_available():
            prefix = self._log_prefix()
            key = "evdev_reader_unavailable" if prefix == "evdev" else f"{prefix}_unavailable"
            logger.debug(key)
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_flag.clear()
        self._reopen_flag.clear()
        if self._wake_r < 0 or self._wake_w < 0:
            # Um stop() anterior fechou o self-pipe — recria para esta vida.
            self._wake_r, self._wake_w = self._novo_wake_pipe()
        self._thread = threading.Thread(target=self._run, name=self._THREAD_NAME, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Para a thread; idempotente.

        HANG-01: não fecha mais o fd ativo de fora (M4 fazia isto para
        desbloquear o `read_loop` de um controle OCIOSO — daí o teardown do
        co-op via IPC congelar o input do P1 por 2-6s). Agora só sinaliza
        (`_stop_flag` + wake do self-pipe), que acorda o select da PRÓPRIA
        thread na hora — o mesmo ganho de latência do M4, sem o risco do
        close cross-thread (padrão GYRO-FD-01). Quem fecha o `InputDevice`
        continua sendo só a thread dona, no `finally` do `_run`.
        """
        self._stop_flag.set()
        self._wake()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
            if not thread.is_alive():
                # Thread morta de verdade: o self-pipe pode ir sem risco de
                # reciclagem (start() recria se este reader voltar a subir).
                self._close_wake_pipe()
        else:
            self._close_wake_pipe()

    def _read_until_signaled(self, dev: Any, ecodes: Any) -> str:
        """Lê eventos do `dev` até stop/reopen pedido; devolve o motivo.

        HANG-01: substitui o `dev.read_loop()` da lib evdev (select interno
        SEM timeout nem self-pipe — só sai por leitura real ou por um close()
        de fora) por um select PRÓPRIO que vigia TAMBÉM o wake do self-pipe.
        `stop()`/`request_reopen()` acordam esta leitura na hora sem nunca
        tocar o fd (GYRO-FD-01/PhysicalReportReader) — quem fecha o device é
        sempre o `finally` de `_run`, na mesma thread deste método. Um ENODEV
        real (unplug) propaga a OSError normalmente; o chamador trata.
        """
        while True:
            if self._stop_flag.is_set():
                return "stop"
            if self._reopen_flag.is_set():
                self._reopen_flag.clear()
                return "reopen"
            ready = self._wait_ready(dev)
            if self._wake_r in ready:
                self._drain_wake()
                continue  # byte de wake atendido — reavalia as flags no topo
            if not ready:
                continue  # timeout do select — reavalia as flags no topo
            for event in dev.read():
                if self._stop_flag.is_set():
                    return "stop"
                self._handle_event(event, ecodes)

    def _run(self) -> None:
        """Loop com auto-reconnect; ENODEV/erro real dispara reset + reabrir."""
        try:
            from evdev import InputDevice, ecodes
        except ImportError:
            logger.warning("evdev_module_missing")
            return

        prefix = self._log_prefix()
        backoff = 0.5
        while not self._stop_flag.is_set():
            # HANG-01: um reopen pedido ANTES desta iteração já está atendido
            # por ela (o finder resolve o node canônico agora); um pedido que
            # chegar DEPOIS deste clear é novo e derruba o fd já na 1ª volta
            # do select em `_read_until_signaled` (mesmo padrão do
            # `PhysicalReportReader._run`).
            self._reopen_flag.clear()
            path = self._device_path or self._find_device()
            if path is None:
                if prefix == "evdev":
                    logger.debug("evdev_device_not_found_retry", backoff=backoff)
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue
            try:
                dev = InputDevice(str(path))
            except Exception as exc:
                logger.warning(f"{prefix}_open_failed", err=str(exc), path=str(path))
                self._device_path = None
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            logger.info(f"{prefix}_started", path=str(path), name=dev.name)
            backoff = 0.5
            self._device_path = path
            self._active_dev = dev
            # Reaplica o grab se foi pedido enquanto o device estava fechado
            # (ex.: gamepad já estava ligado antes desta (re)conexão). Falha
            # NÃO é silenciosa: `_reapply_grab` registra estado + warning
            # (BUG-COOP-GRAB-SILENT-FAIL-01).
            self._reapply_grab(dev)
            self._on_device_opened(dev)
            try:
                reason = self._read_until_signaled(dev, ecodes)
            except OSError as exc:
                logger.warning(f"{prefix}_read_lost", err=str(exc), path=str(path))
                self._reset_on_disconnect()
                self._device_path = None
            except Exception as exc:
                logger.warning(f"{prefix}_loop_error", err=str(exc))
                self._reset_on_disconnect()
            else:
                if reason == "stop":
                    # HANG-01: teardown INTENCIONAL (sem exceção nenhuma —
                    # antes era um EBADF do close cross-thread, MISC-08 item
                    # 4) — nunca alarma como perda de device.
                    logger.debug(f"{prefix}_read_stopped", path=str(path))
                else:  # "reopen"
                    logger.debug(f"{prefix}_reopen_applied", path=str(path))
                    self._reset_on_disconnect()
                    self._device_path = None
            finally:
                self._active_dev = None
                with contextlib.suppress(Exception):
                    dev.close()
            if not self._stop_flag.is_set():
                time.sleep(0.1)  # grace period antes de tentar reabrir


class EvdevReader(_EvdevReconnectLoop):
    """Lê input do DualSense via evdev em thread dedicada.

    `start()` abre o device e inicia o loop. `snapshot()` retorna o estado
    atual (thread-safe). `stop()` encerra limpo.
    """

    # Mapeamento de evdev keycode -> nome canônico no domínio Hefesto - Dualsense4Unix.
    #
    # Botões com keycode evdev estável no kernel hid_playstation:
    # cross, circle, triangle, square, l1, r1, l2_btn, r2_btn,
    # create, options, ps, l3, r3.
    #
    # Botões sem keycode evdev estável no device principal (injetados por outros caminhos):
    # - "mic_btn": vem por HID-raw via `ds.state.micBtn` (byte misc2, bit 0x04).
    #   Injetado em `PyDualSenseController.read_state()`. Ver INFRA-MIC-HID-01.
    # - dpad (up/down/left/right): vem via `_refresh_dpad_buttons` (ABS_HAT0X/Y).
    # - touchpad_*_press: device separado (name contém "Touchpad"); lido por
    #   `TouchpadReader` abaixo (INFRA-EVDEV-TOUCHPAD-01).
    BUTTON_MAP: ClassVar[dict[str, str]] = {
        "BTN_SOUTH": "cross",
        "BTN_EAST": "circle",
        "BTN_NORTH": "triangle",
        "BTN_WEST": "square",
        "BTN_TL": "l1",
        "BTN_TR": "r1",
        "BTN_TL2": "l2_btn",
        "BTN_TR2": "r2_btn",
        "BTN_SELECT": "create",
        "BTN_START": "options",
        "BTN_MODE": "ps",
        "BTN_THUMBL": "l3",
        "BTN_THUMBR": "r3",
    }

    _THREAD_NAME: ClassVar[str] = "hefesto-evdev"

    def __init__(self, device_path: Path | None = None, target_uniq: str | None = None) -> None:
        super().__init__()  # HANG-01: self-pipe de wake (request_reopen/stop)
        # FEAT-DSX-CONTROLLER-IDENTITY-01: quando `_target_uniq` está setado, o
        # finder resolve o node PELO MAC (identidade estável) em vez de "menor
        # node" — com 2+ controles, "menor node" e "primário do backend" podem
        # divergir após re-enumeração e o reader passaria a ler OUTRO controle.
        self._target_uniq = target_uniq
        self._device_path = device_path or self._locate()
        self._lock = threading.RLock()
        self._snapshot = EvdevSnapshot()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._dpad_x = 0
        self._dpad_y = 0
        self._pressed: set[str] = set()
        self._active_dev: Any = None
        # FEAT-DSX-GAMEPAD-FLAVOR-01: quando True, o loop faz EVIOCGRAB no
        # device — o daemon vira leitor exclusivo do controle real e os jogos
        # deixam de ver o controle cru (evitando input dobrado ao lado do
        # gamepad virtual). Aplicado/removido por `set_grab`.
        self._grab: bool = False
        # BUG-COOP-GRAB-SILENT-FAIL-01: estado observável do grab. "off" (não
        # pedido), "pending" (pedido, device ainda não aberto), "held" (ativo),
        # "failed" (EVIOCGRAB recusado — ex.: EBUSY, outro leitor já graba).
        # Falha de grab NÃO pode ser silenciosa: com gamepad virtual ligado,
        # físico sem grab = input DOBRADO no jogo.
        self._grab_state: str = "off"
        # LUGAR-À-MESA-01/E2 — a forma dos eixos DESTE aparelho, lida do
        # `absinfo` no open (`_on_device_opened`). Vazio = faixa desconhecida,
        # e aí o `_handle_abs` cai no `& 0xFF` histórico: o DualSense continua
        # bit a bit igual mesmo se a leitura do node falhar.
        self._eixos: dict[int, EixoAbsoluto] = {}
        # Gatilho ANALÓGICO ausente no aparelho (o Nintendo Pro não publica
        # `ABS_Z`/`ABS_RZ`, medido em 06/08/2026): sem síntese, o gatilho fica
        # 0 para sempre e o botão físico não chega ao jogo. Nunca liga num
        # DualSense — lá o eixo existe, e sobrescrevê-lo mataria o analógico.
        self._sintetizar_l2: bool = False
        self._sintetizar_r2: bool = False

    def retarget(self, uniq: str | None) -> None:
        """Re-aponta o reader para o controle de MAC `uniq` (normalizado).

        Se o node atualmente aberto não pertence ao novo alvo, força reabrir
        (fecha o fd; o loop re-localiza pelo finder, agora filtrado por MAC).
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        norm = norm_mac(uniq)
        if norm == self._target_uniq:
            return
        self._target_uniq = norm
        current = self._locate()
        if current is not None and current == self._device_path:
            return  # o node aberto já é o do alvo — nada a fazer
        self.request_reopen(reason="retarget")

    @property
    def grab_state(self) -> str:
        """Estado observável do EVIOCGRAB: off | pending | held | failed."""
        return self._grab_state

    def set_grab(self, grab: bool) -> bool:
        """Liga/desliga o EVIOCGRAB no controle físico (thread-safe-ish).

        Registra a intenção em `self._grab` (reaplicada a cada (re)conexão pelo
        loop) e tenta aplicar imediatamente no device aberto. Retorna True se o
        estado desejado foi APLICADO agora (ou é pending com device fechado —
        o loop aplica ao abrir); False se o EVIOCGRAB falhou (`grab_state` vira
        "failed" e o chamador NÃO deve assumir exclusividade do device).
        """
        self._grab = grab
        dev = self._active_dev
        if dev is None:
            self._grab_state = "pending" if grab else "off"
            return True
        # BUG-GRAB-DOUBLE-EBUSY-01: re-grabar um fd que ESTE reader já graba
        # levanta EBUSY (errno 16) no kernel — e o `except` abaixo marcava
        # `grab_state="failed"` MESMO com o device fisicamente exclusivo. Era o
        # card "grab falhou — input pode dobrar no jogo" mentindo depois de uma
        # troca de máscara/flavor (que re-chama `set_grab(True)` sem soltar antes,
        # `gamepad.py`: stop(release_grab=False) → re-grab) ou do upgrade
        # uinput→uhid. `grab_state == "held"` já significa "este fd é exclusivo":
        # nada a (re)fazer. Idempotente nos dois sentidos — ungrab de um device
        # que este reader NÃO graba ("off"/"pending"/"failed") também é no-op (o
        # `ungrab()` de um fd solto levantaria EINVAL espúrio). Um EBUSY EXTERNO
        # real (outro leitor exclusivo) nunca chega a "held" primeiro → continua
        # virando "failed" e o card segue honesto quando há duplicação de verdade.
        if grab and self._grab_state == "held":
            return True
        if not grab and self._grab_state != "held":
            self._grab_state = "off"
            return True
        try:
            if grab:
                dev.grab()
                self._grab_state = "held"
            else:
                dev.ungrab()
                self._grab_state = "off"
            return True
        except Exception as exc:
            if grab:
                self._grab_state = "failed"
                logger.warning(
                    "evdev_grab_failed",
                    path=str(self._device_path),
                    err=str(exc),
                    hint="outro leitor exclusivo? físico ficaria DOBRADO no jogo",
                )
                return False
            # ungrab falhou (device já fechado/sumiu): estado efetivo é solto.
            self._grab_state = "off"
            return True

    def snapshot(self) -> EvdevSnapshot:
        with self._lock:
            return EvdevSnapshot(
                l2_raw=self._snapshot.l2_raw,
                r2_raw=self._snapshot.r2_raw,
                lx=self._snapshot.lx,
                ly=self._snapshot.ly,
                rx=self._snapshot.rx,
                ry=self._snapshot.ry,
                buttons_pressed=self._snapshot.buttons_pressed,
            )

    # Hooks do loop base ------------------------------------------------

    def _locate(self) -> Path | None:
        """Resolve o node do controle-alvo (por identidade) ou o 1º DualSense.

        LUGAR-À-MESA-01/E2 (reencontro): com alvo, procura na descoberta ÚNICA
        — que enxerga DualSense **e** externo. Antes só olhava
        `discover_dualsense_evdevs()`, então um externo que trocasse de `eventN`
        (replug, re-enumeração) nunca mais era reencontrado. Sem alvo, nada
        muda: continua o primeiro DualSense físico, porque adotar um externo
        sem ninguém ter pedido seria adoção por acidente — e a adoção é a `E3`.
        """
        if self._target_uniq is not None:
            return localizar_node_por_identidade(self._target_uniq)
        return find_dualsense_evdev()

    def _find_device(self) -> Path | None:
        return self._locate()

    def _on_device_opened(self, dev: Any) -> None:
        """Monta o normalizador DESTE aparelho a partir do `absinfo` do node.

        Um ioctl por conexão, nunca por evento (mesmo motivo do
        `MotionSensorReader._on_device_opened`). Falha aqui não é fatal: o mapa
        fica vazio e o `_handle_abs` volta ao `& 0xFF` de sempre — degradar
        para o que já rodava é o único modo de falha aceitável aqui.
        """
        try:
            from evdev import ecodes
        except ImportError:  # pragma: no cover - sem evdev não há loop
            return
        caps: Any = {}
        with contextlib.suppress(Exception):
            caps = dev.capabilities()
        eixos = faixas_de_eixo(caps, getattr(ecodes, "EV_ABS", 3))
        z = getattr(ecodes, "ABS_Z", None)
        rz = getattr(ecodes, "ABS_RZ", None)
        with self._lock:
            self._eixos = eixos
            # Só sintetiza quando a leitura FOI POSSÍVEL e o eixo não estava
            # lá. Mapa vazio (node ilegível) é "não sei", não "não tem" — e
            # chutar "não tem" num DualSense mataria o gatilho analógico dele.
            self._sintetizar_l2 = bool(eixos) and z is not None and z not in eixos
            self._sintetizar_r2 = bool(eixos) and rz is not None and rz not in eixos

    def _reapply_grab(self, dev: Any) -> None:
        """Reaplica o grab pedido ao (re)abrir o device, com estado observável."""
        if not self._grab:
            return
        try:
            dev.grab()
            self._grab_state = "held"
        except Exception as exc:
            self._grab_state = "failed"
            logger.warning(
                "evdev_grab_failed",
                path=str(self._device_path),
                err=str(exc),
                hint="grab falhou ao reabrir o device; o controle pode dobrar input",
            )

    def _log_prefix(self) -> str:
        return "evdev"

    def _reset_on_disconnect(self) -> None:
        """Limpa botões 'travados' quando o device caiu."""
        with self._lock:
            self._pressed.clear()
            self._dpad_x = 0
            self._dpad_y = 0
            mudancas: dict[str, Any] = {"buttons_pressed": frozenset()}
            # E2: gatilho SINTETIZADO vem do botão, e o botão acabou de ser
            # solto à força — deixá-lo em 255 seria um gatilho travado no
            # fundo. O gatilho ANALÓGICO não é tocado: ali o valor congelado é
            # o comportamento de sempre, e mudá-lo não foi pedido.
            if self._sintetizar_l2:
                mudancas["l2_raw"] = 0
            if self._sintetizar_r2:
                mudancas["r2_raw"] = 0
            self._snapshot = self._with(**mudancas)
            # A forma dos eixos é do NODE, e o node morreu: o próximo open
            # relê. Enquanto isso, "não sei" — que é o `& 0xFF` histórico.
            self._eixos = {}
            self._sintetizar_l2 = False
            self._sintetizar_r2 = False
        # Grab pedido volta a "pending" — será reaplicado (com verificação)
        # quando o loop reabrir o device (BUG-COOP-GRAB-SILENT-FAIL-01).
        if self._grab:
            self._grab_state = "pending"

    # Alias retrocompatível para testes legados (HOTFIX-3).
    _reset_buttons_on_disconnect = _reset_on_disconnect

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS:
            self._handle_abs(event.code, event.value, ecodes)
        elif event.type == ecodes.EV_KEY:
            self._handle_key(event.code, event.value, ecodes)

    def _handle_abs(self, code: int, value: int, ecodes: Any) -> None:
        with self._lock:
            # E2: a faixa é DO APARELHO (`absinfo` lido no open). Sem faixa
            # conhecida, `normalizar_eixo` devolve o mesmo `value & 0xFF` que
            # esta função fazia seis vezes seguidas até 07/08/2026.
            if code == ecodes.ABS_X:
                self._snapshot = self._with(lx=self._normalizado(code, value))
            elif code == ecodes.ABS_Y:
                self._snapshot = self._with(ly=self._normalizado(code, value))
            elif code == ecodes.ABS_RX:
                self._snapshot = self._with(rx=self._normalizado(code, value))
            elif code == ecodes.ABS_RY:
                self._snapshot = self._with(ry=self._normalizado(code, value))
            elif code == ecodes.ABS_Z:
                self._snapshot = self._with(l2_raw=self._normalizado(code, value))
            elif code == ecodes.ABS_RZ:
                self._snapshot = self._with(r2_raw=self._normalizado(code, value))
            elif code == ecodes.ABS_HAT0X:
                self._dpad_x = int(value)
                self._refresh_dpad_buttons()
            elif code == ecodes.ABS_HAT0Y:
                self._dpad_y = int(value)
                self._refresh_dpad_buttons()

    def _normalizado(self, code: int, value: int) -> int:
        """Valor do eixo `code` na faixa canônica da casa (0..255)."""
        return normalizar_eixo(int(value), self._eixos.get(code))

    def _handle_key(self, code: int, value: int, ecodes: Any) -> None:
        # evdev retorna keycode numerico; converte pra nome canonico
        name = self._keycode_name(code, ecodes)
        if name is None:
            return
        with self._lock:
            if value == 1:
                self._pressed.add(name)
            elif value == 0:
                self._pressed.discard(name)
            self._sintetizar_gatilho(name, value)
            self._sync_buttons_to_snapshot()

    def _sintetizar_gatilho(self, name: str, value: int) -> None:
        """Gatilho DIGITAL: o botão vira 0/255 quando o eixo não existe.

        O Nintendo Pro não publica `ABS_Z`/`ABS_RZ` — o ZL/ZR dele é botão, não
        eixo (medido em 06/08/2026). Sem esta síntese o gatilho fica **0 para
        sempre** e o dedo da pessoa não chega ao jogo.

        Chamado sempre, mas só faz algo quando o open confirmou que o eixo
        FALTA neste aparelho. Num DualSense o eixo existe, a síntese fica
        desligada, e o `BTN_TL2` continua sendo só um botão — sobrescrever o
        analógico com 255 ao cruzar o limiar seria matar o gatilho adaptativo,
        que é metade do produto.
        """
        if value not in (0, 1):
            return  # autorepeat (value == 2) não muda estado de gatilho
        nivel = EIXO_MAX_HEFESTO if value == 1 else 0
        if name == "l2_btn" and self._sintetizar_l2:
            self._snapshot = self._with(l2_raw=nivel)
        elif name == "r2_btn" and self._sintetizar_r2:
            self._snapshot = self._with(r2_raw=nivel)

    def _keycode_name(self, code: int, ecodes: Any) -> str | None:
        for evdev_name, hefesto_name in self.BUTTON_MAP.items():
            ev_code = getattr(ecodes, evdev_name, None)
            if ev_code is not None and ev_code == code:
                return hefesto_name
        return None

    def _refresh_dpad_buttons(self) -> None:
        for d in ("dpad_up", "dpad_down", "dpad_left", "dpad_right"):
            self._pressed.discard(d)
        if self._dpad_y < 0:
            self._pressed.add("dpad_up")
        elif self._dpad_y > 0:
            self._pressed.add("dpad_down")
        if self._dpad_x < 0:
            self._pressed.add("dpad_left")
        elif self._dpad_x > 0:
            self._pressed.add("dpad_right")
        self._sync_buttons_to_snapshot()

    def _sync_buttons_to_snapshot(self) -> None:
        self._snapshot = self._with(buttons_pressed=frozenset(self._pressed))

    def _with(self, **changes: Any) -> EvdevSnapshot:
        current = self._snapshot
        fields = ("l2_raw", "r2_raw", "lx", "ly", "rx", "ry", "buttons_pressed")
        values = {f: changes.get(f, getattr(current, f)) for f in fields}
        return EvdevSnapshot(**values)


def _discover_dualsense_por_nome(marcador: str) -> dict[str, Path]:
    """MAC normalizado -> node evdev dos DualSense cujo nome contém `marcador`.

    Mesma mecânica de `discover_dualsense_evdevs` (que casa por CAPS de
    gamepad), mas para os nodes AUXILIARES que o `hid_playstation` cria com
    o mesmo vendor/product e um sufixo no nome: "… Touchpad" e "… Motion
    Sensors". Chave por MAC (`uniq`) porque `eventN` é volátil — o mesmo
    contrato de identidade do resto do projeto (FEAT-DSX-CONTROLLER-IDENTITY-01);
    node sem `uniq` legível cai em "path:<caminho>", que nunca colide com MAC.

    Devices virtuais ficam de fora (`_is_virtual_evdev`): os vpads uhid do
    daemon publicam nodes com ESTES MESMOS nomes ("Hefesto Virtual DualSense
    P1 Motion Sensors"), e adotar um deles seria o daemon lendo a própria
    saída.
    """
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        return {}
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    found: dict[str, Path] = {}
    for path in sorted(list_devices(), key=lambda p: _event_num(Path(p))):
        if _is_virtual_evdev(path):
            continue
        try:
            dev = InputDevice(path)
            try:
                if (
                    dev.info.vendor == DUALSENSE_VENDOR
                    and dev.info.product in DUALSENSE_PIDS
                    and marcador in dev.name
                ):
                    key = norm_mac(getattr(dev, "uniq", None)) or f"path:{path}"
                    found.setdefault(key, Path(path))
            finally:
                dev.close()
        except Exception:
            continue
    return found


def discover_dualsense_touchpad_evdevs() -> dict[str, Path]:
    """MAC normalizado -> node evdev do TOUCHPAD de cada DualSense físico."""
    return _discover_dualsense_por_nome("Touchpad")


def discover_dualsense_motion_evdevs() -> dict[str, Path]:
    """MAC normalizado -> node evdev dos SENSORES DE MOVIMENTO de cada DualSense.

    É o node que `assets/78-dualsense-motion-not-joystick.rules` nomeia para
    tirá-lo da lista de joysticks. Diferente do espelho de motion do vpad
    (`core/physical_report_reader.py`), ele entrega o gyro JÁ DECODIFICADO
    pelo kernel e existe em TODOS os modos — inclusive com a emulação
    desligada, quando não há vpad nenhum para o espelho alimentar.
    """
    return _discover_dualsense_por_nome("Motion Sensors")


def find_dualsense_touchpad_evdev(target_uniq: str | None = None) -> Path | None:
    """Retorna path do evdev do touchpad do DualSense; None se ausente.

    O touchpad é exposto pelo kernel `hid_playstation` como um event
    device separado do gamepad principal: mesmo vendor/product Sony
    DualSense, mas nome contendo "Touchpad" (ex: "Sony Interactive
    Entertainment DualSense Wireless Controller Touchpad").

    Com `target_uniq` (MAC normalizado) resolve o touchpad DAQUELE controle;
    sem ele, o primeiro por número de node — o comportamento histórico, que
    o caminho de cursor/teclado usa (lá só existe o primário).

    INFRA-EVDEV-TOUCHPAD-01 — validação empírica 2026-04-24.
    """
    mapa = discover_dualsense_touchpad_evdevs()
    if target_uniq is not None:
        return mapa.get(target_uniq)
    ordenados = sorted(mapa.values(), key=_event_num)
    return ordenados[0] if ordenados else None


@dataclass(frozen=True)
class TouchState:
    """Estado de toque do touchpad num instante (leitura NÃO-destrutiva).

    Coordenadas nas unidades absolutas do kernel (`largura`/`altura` viajam
    junto para quem desenha não precisar hardcodar 1920x1080). Sem dedo
    apoiado, `x`/`y` guardam a ÚLTIMA posição vista — quem renderiza só deve
    desenhar o ponto quando `touching` for True.
    """

    touching: bool = False
    x: int = 0
    y: int = 0
    largura: int = 1920
    altura: int = 1080


class TouchpadReader(_EvdevReconnectLoop):
    """Lê o touchpad do DualSense: click regionalizado + movimento do dedo.

    O touchpad emite `BTN_LEFT` (click firme mecânico, não toque leve) +
    `ABS_X` (0 a 1919) / `ABS_Y` (0 a 1079) + `BTN_TOUCH` (dedo presente) no
    device separado descoberto por `find_dualsense_touchpad_evdev`.

    Duas responsabilidades, ambas via o mesmo loop evdev:

    1. **Click regionalizado** (`regions_pressed()`): correlaciona o último
       `ABS_X` observado com o `BTN_LEFT` para discriminar três regiões —
       esquerda, meio, direita (limites 640 e 1280 sobre largura 1920). Vira
       teclas no `dispatch_keyboard`.

    2. **Movimento do cursor** (`consume_motion()`, FEAT-DSX-TOUCHPAD-CURSOR-B4):
       enquanto `BTN_TOUCH` está ativo, acumula o delta de `ABS_X`/`ABS_Y`
       entre frames. O poll loop drena esse delta a cada tick e o converte em
       REL_X/REL_Y via o mouse virtual — touchpad como fonte ÚNICA do cursor,
       sem briga = sem engasgo. `BTN_TOUCH` solto zera a posição de referência:
       levantar e reapoiar o dedo em outro ponto NÃO faz o cursor pular.

    TOUCHPAD-DO-SISTEMA-01 (2026-08-09) — QUEM É O DONO DO DEDO: as duas
    responsabilidades acima só valem quando o touchpad **não** é ponteiro do
    sistema. Desde 09/08 a `assets/76-dualsense-touchpad-libinput-ignore.rules`
    tira do libinput só o touchpad do VPAD; o FÍSICO volta a ser o touchpad do
    sistema em todos os modos, que foi o que ela pediu — *"a ideia do touchpad é
    ele voltar a funcionar assim, seja no modo nativo ou dualsense"*. Nesse
    estado o libinput já move o cursor e já entrega o clique, e o reader tem de
    ficar de fora: o mesmo dedo movendo o cursor por dois caminhos é o "engasgo"
    de 26/06, e o mesmo clique virando botão do mouse E `KEY_BACKSPACE` seria o
    mesmo defeito na tecla. Quem responde é `libinput_ignora_device`, lida UMA
    vez por (re)conexão no `_on_device_opened` — o estado real do nó, não um
    modo que o udev não conhece. `ponteiro_do_sistema` é observável de fora.

    O reader continua LENDO tudo em qualquer caso: o painel de Status desenha o
    dedo pelo `touch_state()`, e observar nunca duplicou nada.

    Threadsafe via RLock.
    """

    # Largura do touchpad em unidades absolutas do kernel hid_playstation
    # (empírico, DualSense USB 054c:0ce6 com kernel 6.x):
    _TOUCHPAD_WIDTH: ClassVar[int] = 1920
    _TOUCHPAD_HEIGHT: ClassVar[int] = 1080
    # Limites de região (terços): [0, 640) esquerda; [640, 1280) meio;
    # [1280, 1920) direita.
    _REGION_LEFT_LIMIT: ClassVar[int] = 640
    _REGION_RIGHT_LIMIT: ClassVar[int] = 1280
    _THREAD_NAME: ClassVar[str] = "hefesto-touchpad"

    def __init__(
        self,
        device_path: Path | None = None,
        target_uniq: str | None = None,
        *,
        acumular_movimento: bool = True,
    ) -> None:
        """Reader do touchpad de UM controle.

        `target_uniq` (MAC normalizado) fixa DE QUEM é este touchpad; sem
        ele vale o primeiro node por número (o caminho histórico de
        cursor/teclado, que só conhece o primário).

        `acumular_movimento=False` desliga o acúmulo de delta do
        `consume_motion`. É OBRIGATÓRIO para qualquer leitor que só OBSERVE
        o touchpad (o painel da aba Status): o mesmo node aceita vários fds
        e o kernel replica os eventos para todos, então um segundo reader
        acumulando delta que ninguém drena faria `_accum_dx/dy` crescer a
        sessão inteira — exatamente o salto de cursor que o poll loop já
        aprendeu a evitar drenando o reader do mouse a cada tick. Sem
        acúmulo, este reader é puro observador e não tem como roubar (nem
        inflar) o movimento do cursor.
        """
        super().__init__()  # HANG-01: self-pipe de wake (request_reopen/stop)
        self._target_uniq = target_uniq
        self._acumular_movimento = acumular_movimento
        self._device_path = device_path or find_dualsense_touchpad_evdev(target_uniq)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._last_abs_x: int = self._TOUCHPAD_WIDTH // 2  # centro por default
        self._last_abs_y: int = self._TOUCHPAD_HEIGHT // 2
        self._regions: frozenset[str] = frozenset()
        # Movimento do cursor (B4): dedo presente + posição de referência por
        # eixo (None = ainda sem âncora; o primeiro frame só seeda, não move) +
        # delta acumulado entre drenagens (`consume_motion`).
        self._touching: bool = False
        self._motion_last_x: int | None = None
        self._motion_last_y: int | None = None
        self._accum_dx: int = 0
        self._accum_dy: int = 0
        # TOUCHPAD-DO-SISTEMA-01: quem move o cursor com este nó. Nasce False
        # (o hefesto é o dono) e é decidido de verdade no `_on_device_opened`,
        # que o loop base SEMPRE chama antes do primeiro evento — nenhum evento
        # é consumido com o valor de nascença.
        self._ponteiro_do_sistema: bool = False

    @property
    def ponteiro_do_sistema(self) -> bool:
        """True se o libinput é quem move o cursor com ESTE nó de touchpad.

        Observável de fora porque o consumidor do CLIQUE também precisa dela:
        `daemon/subsystems/keyboard._combine_with_touchpad` não pode transformar
        a região em tecla enquanto o sistema já está transformando o mesmo
        clique em botão do mouse.
        """
        with self._lock:
            return self._ponteiro_do_sistema

    def regions_pressed(self) -> frozenset[str]:
        with self._lock:
            return self._regions

    def touch_state(self) -> TouchState:
        """Dedo presente + última posição, SEM consumir nada (STATUS-S2).

        Deliberadamente separado do `consume_motion()`: aquele DRENA o delta
        acumulado para o cursor do mouse, então chamá-lo aqui roubaria o
        movimento de quem é dono dele (o poll loop). Este devolve uma cópia
        imutável do estado sob lock — pode ser chamado a 10 Hz pelo painel da
        aba Status sem interferir em nada.
        """
        with self._lock:
            return TouchState(
                touching=self._touching,
                x=self._last_abs_x,
                y=self._last_abs_y,
                largura=self._TOUCHPAD_WIDTH,
                altura=self._TOUCHPAD_HEIGHT,
            )

    def consume_motion(self) -> tuple[int, int]:
        """Retorna e zera o delta acumulado do dedo (unidades do touchpad).

        Chamado pelo poll loop a cada tick. Drena-e-reseta para que o consumo
        seja sempre o movimento desde a última chamada — o escalonamento para
        pixels (com `mouse_speed` e carry sub-pixel) é responsabilidade do
        `UinputMouseDevice.emit_touchpad_move`.
        """
        with self._lock:
            dx, dy = self._accum_dx, self._accum_dy
            self._accum_dx = 0
            self._accum_dy = 0
            return dx, dy

    @classmethod
    def _region_from_x(cls, x: int) -> str:
        if x < cls._REGION_LEFT_LIMIT:
            return "touchpad_left_press"
        if x >= cls._REGION_RIGHT_LIMIT:
            return "touchpad_right_press"
        return "touchpad_middle_press"

    # Hooks do loop base ------------------------------------------------

    def _find_device(self) -> Path | None:
        return find_dualsense_touchpad_evdev(self._target_uniq)

    def _log_prefix(self) -> str:
        return "touchpad_reader"

    def _on_device_opened(self, dev: Any) -> None:
        """Decide de quem é o cursor deste nó (TOUCHPAD-DO-SISTEMA-01).

        Uma leitura por (re)conexão, no mesmo lugar em que o `MotionSensorReader`
        lê a `resolution` — e pelo mesmo motivo: a resposta muda quando o kernel
        recria o nó (replug, storm, troca USB↔BT), e perguntar por evento
        custaria um `open()` a cada frame do dedo.
        """
        caminho = getattr(dev, "path", None) or self._device_path
        do_sistema = libinput_ignora_device(caminho) is False
        with self._lock:
            mudou = do_sistema != self._ponteiro_do_sistema
            self._ponteiro_do_sistema = do_sistema
            if mudou:
                # Trocou de dono: o que estava acumulado é do dono ANTERIOR e
                # viraria um salto de cursor na primeira drenagem do novo.
                self._accum_dx = 0
                self._accum_dy = 0
        logger.info(
            "touchpad_reader_dono_do_cursor",
            ponteiro_do_sistema=do_sistema,
            path=str(caminho) if caminho else None,
        )

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_X:
                with self._lock:
                    # Snapshot de X para a região do próximo BTN_LEFT.
                    self._last_abs_x = int(event.value)
                    self._accumulate_axis_x(int(event.value))
            elif event.code == ecodes.ABS_Y:
                with self._lock:
                    self._last_abs_y = int(event.value)
                    self._accumulate_axis_y(int(event.value))
        elif event.type == ecodes.EV_KEY:
            if event.code == ecodes.BTN_LEFT:
                with self._lock:
                    if event.value == 1:
                        self._regions = frozenset(
                            {self._region_from_x(self._last_abs_x)}
                        )
                    elif event.value == 0:
                        self._regions = frozenset()
            elif event.code == ecodes.BTN_TOUCH:
                with self._lock:
                    # Dedo apoiado/levantado: zera a âncora dos dois eixos para
                    # que reapoiar em outro ponto não gere um salto do cursor.
                    self._touching = event.value == 1
                    self._motion_last_x = None
                    self._motion_last_y = None

    def _acumula_agora(self) -> bool:
        """Se este reader pode acumular movimento para o cursor do hefesto.

        Duas condições, e as duas negam por razões diferentes:
        `_acumular_movimento=False` é o OBSERVADOR (o painel de Status abre o
        mesmo nó e não pode roubar delta); `_ponteiro_do_sistema` é o dedo já
        estar movendo o cursor pelo libinput (TOUCHPAD-DO-SISTEMA-01).
        """
        return self._acumular_movimento and not self._ponteiro_do_sistema

    def _accumulate_axis_x(self, value: int) -> None:
        """Acumula delta de X se há dedo e âncora; senão só seeda a âncora."""
        if self._acumula_agora() and self._touching and self._motion_last_x is not None:
            self._accum_dx += value - self._motion_last_x
        self._motion_last_x = value

    def _accumulate_axis_y(self, value: int) -> None:
        if self._acumula_agora() and self._touching and self._motion_last_y is not None:
            self._accum_dy += value - self._motion_last_y
        self._motion_last_y = value

    def _reset_on_disconnect(self) -> None:
        with self._lock:
            self._regions = frozenset()
            self._touching = False
            self._motion_last_x = None
            self._motion_last_y = None
            self._accum_dx = 0
            self._accum_dy = 0


@dataclass(frozen=True)
class GyroSnapshot:
    """Velocidade angular dos três eixos do giroscópio, em GRAUS POR SEGUNDO."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


def graus_por_segundo(valor: int, resolucao: int) -> float:
    """Converte o valor CRU de um eixo de giroscópio evdev em graus/s.

    O `hid_playstation` publica a escala do sensor no próprio node, em
    `absinfo.resolution` — "unidades por grau/s" (`DS_GYRO_RES_PER_DEG_S`,
    1024 no kernel atual). Dividir pelo que o node declara é o único jeito
    que sobrevive a uma mudança de escala do kernel; hardcodar 1024 daria
    um número silenciosamente errado no dia em que ela mudasse.

    Resolução ausente/zero/negativa (node atípico, dublê de teste) cai no
    default do kernel — é melhor que devolver o valor cru, que a interface
    leria como dezenas de milhares de graus/s.
    """
    escala = resolucao if resolucao > 0 else DUALSENSE_GYRO_RES_PER_DEG_S
    return valor / escala


class MotionSensorReader(_EvdevReconnectLoop):
    """Lê o giroscópio de UM DualSense pelo node evdev "… Motion Sensors".

    Por que este caminho e não o `PhysicalReportReader` (GYRO-01): aquele
    fatia a janela de motion do report CRU e a repassa OPACA ao vpad — os
    bytes nunca viram número — e só existe enquanto há vpad ativo. Este lê o
    node que o kernel já decodifica, existe com a emulação desligada e
    entrega graus/s direto. São consumidores diferentes do mesmo sensor: um
    alimenta o jogo, o outro alimenta a interface.

    O eixo é mapeado por `ABS_RX/RY/RZ` (gyro) — `ABS_X/Y/Z` no mesmo node
    são o ACELERÔMETRO e não entram aqui. A escala vem do `absinfo` lido no
    open (ver `_on_device_opened`), não de constante.
    """

    _THREAD_NAME: ClassVar[str] = "hefesto-motion-sensors"

    def __init__(
        self, device_path: Path | None = None, target_uniq: str | None = None
    ) -> None:
        super().__init__()  # HANG-01: self-pipe de wake (request_reopen/stop)
        self._target_uniq = target_uniq
        self._device_path = device_path or self._locate()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._eixos: dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}
        #: Nome do eixo -> resolução declarada pelo node (preenchido no open).
        self._resolucoes: dict[str, int] = {}

    def snapshot(self) -> GyroSnapshot:
        """Última velocidade angular conhecida (cópia sob lock)."""
        with self._lock:
            return GyroSnapshot(
                x=self._eixos["x"], y=self._eixos["y"], z=self._eixos["z"]
            )

    # Hooks do loop base ------------------------------------------------

    def _locate(self) -> Path | None:
        mapa = discover_dualsense_motion_evdevs()
        if self._target_uniq is not None:
            return mapa.get(self._target_uniq)
        ordenados = sorted(mapa.values(), key=_event_num)
        return ordenados[0] if ordenados else None

    def _find_device(self) -> Path | None:
        return self._locate()

    def _log_prefix(self) -> str:
        return "motion_sensors"

    def _on_device_opened(self, dev: Any) -> None:
        """Lê a escala de cada eixo do `absinfo` do node recém-aberto.

        Falha aqui NÃO é fatal: sem resolução, `graus_por_segundo` cai no
        default do kernel e o painel segue mostrando um número plausível em
        vez de sumir (degradação silenciosa, como o tema sem CSS).
        """
        resolucoes: dict[str, int] = {}
        try:
            from evdev import ecodes
        except ImportError:  # pragma: no cover - sem evdev não há loop
            return
        for eixo, nome in (("x", "ABS_RX"), ("y", "ABS_RY"), ("z", "ABS_RZ")):
            code = getattr(ecodes, nome, None)
            if code is None:
                continue
            with contextlib.suppress(Exception):
                info = dev.absinfo(code)
                resolucoes[eixo] = int(getattr(info, "resolution", 0) or 0)
        with self._lock:
            self._resolucoes = resolucoes

    def _reset_on_disconnect(self) -> None:
        """Controle sumiu: zera os eixos — gyro congelado mentiria movimento."""
        with self._lock:
            self._eixos = {"x": 0.0, "y": 0.0, "z": 0.0}
            self._resolucoes = {}

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type != ecodes.EV_ABS:
            return
        for eixo, nome in (("x", "ABS_RX"), ("y", "ABS_RY"), ("z", "ABS_RZ")):
            code = getattr(ecodes, nome, None)
            if code is not None and code == event.code:
                with self._lock:
                    self._eixos[eixo] = graus_por_segundo(
                        int(event.value), self._resolucoes.get(eixo, 0)
                    )
                return


__all__ = [
    "DUALSENSE_GYRO_RES_PER_DEG_S",
    "DUALSENSE_PIDS",
    "DUALSENSE_VENDOR",
    "EIXO_MAX_HEFESTO",
    "ESPECIE_DUALSENSE",
    "ESPECIE_EXTERNAL",
    "EixoAbsoluto",
    "EvdevReader",
    "EvdevSnapshot",
    "GamepadDescoberto",
    "GyroSnapshot",
    "MotionSensorReader",
    "TouchState",
    "TouchpadReader",
    "discover_dualsense_motion_evdevs",
    "discover_dualsense_touchpad_evdevs",
    "discover_external_gamepads",
    "discover_gamepads",
    "faixas_de_eixo",
    "find_all_dualsense_evdevs",
    "find_dualsense_evdev",
    "find_dualsense_touchpad_evdev",
    "graus_por_segundo",
    "localizar_node_por_identidade",
    "normalizar_eixo",
]
