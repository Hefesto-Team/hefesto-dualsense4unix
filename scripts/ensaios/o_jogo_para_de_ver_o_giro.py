#!/usr/bin/env python3
"""O JOGO para de ver o giro — medido pelo SDL que o jogo CARREGA, não pela interface.

SENSOR-DE-VERDADE-01 / ONDA1-D3. Decisão, 04/09/2026:

    *"ele tem que funcionar de verdade. ambos independente do modo e da
    mascara."* <!-- noqa-acento: citação literal -->

**A DIFERENÇA QUE ESTE ENSAIO EXISTE PARA NÃO CONFUNDIR** é a mesma que
derrubou quatro réguas em 04/09: *"a interface parou de mostrar"* e *"o jogo
parou de receber"* são coisas diferentes, e só a segunda é a entrega. Por isso
o instrumento aqui **não** é o `state_full` do daemon: é uma sonda **SDL
headless**, que abre o controle como um jogo abre e conta amostras de sensor.

**E A BIBLIOTECA É PARTE DA MEDIDA** (SENSORES-NO-JOGO-02, 13/09/2026). Até
esta data o ensaio carregava `libSDL2-2.0.so.0` pelo loader do sistema — a
2.30.0 da Ubuntu, que nenhum jogo da Steam carrega —, e o zero que ele mediu em
10/09 era dessa biblioteca, não do vpad. Agora cada biblioteca roda num
processo próprio: as de `--lib`, ou, sem a opção, as dos runtimes da Steam
achadas na instalação (`~/.steam/root` e as pastas do `libraryfolders.vdf`).
Cada veredito nomeia a biblioteca, a revisão lida por `SDL_GetRevision` e a
dica com que ela rodou.

Sem janela: o SDL sobe só o subsistema de controle, com `SDL_VIDEODRIVER` em
`dummy`, e o processo de cada biblioteca nasce sem `DISPLAY` e sem
`WAYLAND_DISPLAY`. **Nada nasce na tela do usuário.**

O QUE ELE MEDE, e em que ordem
-------------------------------
1. por biblioteca, o que o ``SDL_hid_enumerate(0, 0)`` devolve — a MESMA
   chamada que o subsistema de joystick faz —, pedido num processo à parte com
   o filtro de controles do SDL3 desligado e conferido contra um PISO lido de
   `/sys/class/hidraw` (:func:`piso_da_enumeracao_hid`). Lista que não alcança
   o piso quer dizer que a struct deste ensaio não casa com a biblioteca, e o
   ensaio diz isso em vez de concluir;
2. por onde o SDL abriu cada controle (`hidraw` = HIDAPI; `event` = evdev);
3. se a biblioteca **expõe** giroscópio e acelerômetro naquele controle
   (`HasSensor`), antes de contar amostra nenhuma;
4. quantas amostras DISTINTAS de giroscópio e de acelerômetro chegaram;
5. o mesmo, depois de `sensor.set` desligar o sensor pelo daemon;
6. e o nó evdev "Motion Sensors" de cada peça, lido direto — é o CONTROLE do
   número do SDL: se o nó entrega e a biblioteca não, a diferença é da
   biblioteca.

Uso:

    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --so-medir          # só lê
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --so-medir --lib <caminho>
    scripts/bancada.sh reservar "ensaio do sensor"                   # e só então:
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --segundos 3

``--jogador P1..P4`` (O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01, degraus 1 e 2) é a outra
sonda: SDL3 com o HIDAPI LIGADO, como o Vita3K o tem. Abre SÓ o vpad daquele jogador, escolhido
pelo serial (o `HID_UNIQ` do `hidraw` que o SDL dá) e conferido pelo par `(st_dev, st_ino)`,
porque nome e GUID são IGUAIS nos quatro. Duas fases (parado, com o dedo), os contadores de
cada vpad antes, durante e depois, e um laudo por item; rc 3 quando reprova. **Escreve no
aparelho** (o driver PS5 do HIDAPI escreve ao abrir): exige `scripts/bancada.sh exigir`,
`--lib` de uma libSDL3 e recusa `--so-medir`. `--hidapi 0` existe só para a mordida.

``--so-medir`` não chama o daemon, força ``SDL_JOYSTICK_HIDAPI=0`` e
``SDL_HIDAPI_LIBUSB=0`` — nenhuma biblioteca abre `hidraw`, e nada é escrito em
controle nenhum (o driver PS5 do HIDAPI escreve efeitos ao abrir) — e lê o nó
de movimento sem ``EVIOCGRAB``.

``--dica-do-acelerometro`` escolhe o ``SDL_ACCELEROMETER_AS_JOYSTICK`` de cada
processo: ``0`` (o padrão, e é o que o wrapper entrega ao jogo desde 13/09 —
`compose_env`, em `daemon/launch_env.py`), ``1``, ou ``ausente`` (sem a
variável, como um jogo aberto por fora do Hefesto).

O QUE AS BANCADAS MEDIRAM, e é o que este cabeçalho existe para não deixar remedir
---------------------------------------------------------------------------------
**10/09/2026** — dois DualSense na mesa, P1 no cabo e P2 no rádio, **só a
libSDL2 2.30.0 do sistema Ubuntu**, sem a dica:

=========================  =========================  =========================
o que a 2.30.0 respondeu   **Virtual** (máscara DS)   **Nativo**
=========================  =========================  =========================
por onde o SDL abriu       ``/dev/input/eventNN``     ``/dev/hidraw5``
                           (evdev)                    (HIDAPI)
``HasSensor(GYRO)``        **False**                  True
``HasSensor(ACCEL)``       **False**                  True
giro distintos em 3 s      **0**                      96
acelerômetro em 3 s        **0**                      586
`hidraw` do FÍSICO         ``0600`` — o daemon o      ``0660``
                           esconde do jogo
=========================  =========================  =========================

Na MESMA janela, o nó "Motion Sensors" de cada peça entregava dezenas de
valores DISTINTOS de giro, e o `hidraw` do vpad do cabo entregava **250
relatórios/s com 222 valores distintos de giro em 5 s**. O vpad estava íntegro.

**13/09/2026** — o vpad P1 vivo, só o rádio, sonda só-leitura com
``SDL_JOYSTICK_HIDAPI=0``, 2 s por biblioteca, no nó do vpad:

=========================================  ===========  ================
biblioteca                                 HasSensor    giros distintos
=========================================  ===========  ================
libSDL2 2.30.0, sistema Ubuntu, sem dica   False        0
libSDL2 2.30.0, sistema Ubuntu, dica em 0  True         109
libSDL2 2.32.10, runtime scout             True         141
SDL3 3.4.14, runtime sniper                True         137
sdl2-compat 2.32.70, runtime sniper        True         144
=========================================  ===========  ================

A CAUSA, medida e lida no fonte (13/09/2026)
--------------------------------------------
* **O HIDAPI da SDL2 clássica não lista o vpad.** O ``hid_enumerate`` de
  ``hidapi/linux/hid.c`` (release-2.30.0, idêntico na 2.32.10) descarta o
  `hidraw` de barramento USB sem pai ``usb_device``, e o vpad `uhid` mora em
  ``/devices/virtual/misc/uhid``. O SDL3 e o sdl2-compat o listam.
* **Sem HIDAPI, o movimento viaja pelo evdev.** O SDL recusa o nó "Motion
  Sensors" como controle, pelo nome, e o casa como SENSOR ao gamepad da MESMA
  peça pelo ``EVIOCGUNIQ``. Isso vale em toda biblioteca medida, menos na
  2.30.0 da Ubuntu: o patch LP #2085140 exige a classe udev ACCELEROMETER, que
  a 2.30 só atribui com ``SDL_ACCELEROMETER_AS_JOYSTICK=0``.
* **O próprio ensaio mentia sobre a enumeração.** A struct não tinha os três
  ints de interface, o ``next`` era lido no deslocamento errado e a lista
  parava no primeiro item — e daí saiu a conclusão, também falsa, de que a
  chamada pública não era a do subsistema de joystick.

O QUE ELE **NÃO** PROVA, e está escrito para ninguém concluir demais
---------------------------------------------------------------------
Um controle imóvel entrega o mesmo valor por vários quadros: "zero amostras
distintas" com o aparelho parado não é prova de nada. **Mexa no controle
durante a medição** — o nó de movimento ao lado diz se havia dado a receber.

Uma sonda no host não é o contêiner do Steam Linux Runtime: lá dentro o SDL
enumera por outro caminho, e quem mede lá é a MESA-DE-QUATRO-01. E ele não
prova NADA sobre `O JOGO REAGIU`: um jogo de verdade, mirando, é o degrau
seguinte, e esse só fecha com o olho de quem confere.

SAÍDA: o relatório em JSON, e o código de retorno ``3`` quando alguma
biblioteca não pôde ser medida ou a enumeração dela não alcançou o piso.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import ctypes
import itertools
import json
import os
import pathlib
import re
import subprocess
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_SENSOR_ACCEL = 1
SDL_SENSOR_GYRO = 2
_SENSORES = ((SDL_SENSOR_GYRO, "giro"), (SDL_SENSOR_ACCEL, "accel"))

BASAL_MINIMO = 5

EIXOS_DO_GIRO = ("ABS_RX", "ABS_RY", "ABS_RZ")

EIXOS_DO_ACELEROMETRO = ("ABS_X", "ABS_Y", "ABS_Z")

DICA_DO_ACELEROMETRO = "SDL_ACCELEROMETER_AS_JOYSTICK"
VALOR_QUE_O_JOGO_RECEBE = "0"

FILTRO_SO_CONTROLES = "SDL_HIDAPI_ENUMERATE_ONLY_CONTROLLERS"

_SEMPRE_NO_PROCESSO = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
_SO_LEITURA = {"SDL_JOYSTICK_HIDAPI": "0", "SDL_HIDAPI_LIBUSB": "0"}
_SEM_TELA = ("DISPLAY", "WAYLAND_DISPLAY")
_TETO_DE_ENTRADAS_HID = 512

_SCOUT = "ubuntu12_32/steam-runtime/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0*"
_NOS_RUNTIMES = (
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/libSDL3.so.0*",
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/libSDL2-2.0.so.0*",
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/sdl2-*/libSDL2-2.0.so.0*",
)


class _InfoHid(ctypes.Structure):
    """`SDL_hid_device_info` da API da SDL2 (``include/SDL_hidapi.h``), até ``next``."""


_CAMPOS_ATE_A_INTERFACE: list[tuple[str, Any]] = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_ushort),
    ("product_id", ctypes.c_ushort),
    ("serial_number", ctypes.c_void_p),
    ("release_number", ctypes.c_ushort),
    ("manufacturer_string", ctypes.c_void_p),
    ("product_string", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_ushort),
    ("usage", ctypes.c_ushort),
    ("interface_number", ctypes.c_int),
    ("interface_class", ctypes.c_int),
    ("interface_subclass", ctypes.c_int),
    ("interface_protocol", ctypes.c_int),
]

_InfoHid._fields_ = [*_CAMPOS_ATE_A_INTERFACE, ("next", ctypes.POINTER(_InfoHid))]


class _InfoHid3(ctypes.Structure):
    """O mesmo registro no SDL3 (``include/SDL3/SDL_hidapi.h``): ``bus_type`` antes de ``next``."""


_InfoHid3._fields_ = [
    *_CAMPOS_ATE_A_INTERFACE,
    ("bus_type", ctypes.c_int),
    ("next", ctypes.POINTER(_InfoHid3)),
]


class _Versao2(ctypes.Structure):
    _fields_ = [("major", ctypes.c_uint8), ("minor", ctypes.c_uint8), ("patch", ctypes.c_uint8)]


@dataclass(frozen=True)
class Biblioteca:
    """Uma libSDL a medir, classificada SEM carregar — pelo nome e pelos bytes."""

    caminho: pathlib.Path
    api: int
    compat: bool
    pre_carregar: pathlib.Path | None


def descrever_biblioteca(caminho: pathlib.Path) -> Biblioteca | str:
    """A biblioteca pronta para carregar, ou a razão de não carregá-la."""
    if not caminho.is_file():
        return f"{caminho}: não é um arquivo"
    nome = caminho.name
    if nome.startswith("libSDL3.so"):
        return Biblioteca(caminho, 3, False, None)
    if not nome.startswith("libSDL2-2.0.so"):
        return f"{caminho}: não é libSDL2 nem libSDL3"
    if b"libSDL3.so.0" not in caminho.read_bytes():
        return Biblioteca(caminho, 2, False, None)
    for pasta in (caminho.parent, caminho.parent.parent):
        irmas = sorted(pasta.glob("libSDL3.so.0*"))
        if irmas:
            return Biblioteca(caminho, 2, True, irmas[0])
    return f"{caminho}: sdl2-compat sem um libSDL3.so.0 ao lado — não carrego"


def pastas_de_biblioteca_da_steam(raiz: pathlib.Path) -> list[pathlib.Path]:
    """A instalação e as pastas de biblioteca que o `libraryfolders.vdf` declara."""
    pastas = [raiz]
    try:
        texto = (raiz / "steamapps" / "libraryfolders.vdf").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return pastas
    for achado in re.finditer(r'"path"\s+"([^"]+)"', texto):
        pasta = pathlib.Path(achado.group(1))
        if pasta not in pastas:
            pastas.append(pasta)
    return pastas


def bibliotecas_dos_runtimes(casa: pathlib.Path | None = None) -> list[pathlib.Path]:
    """As libSDL que os runtimes da Steam instalados trazem — achadas, não digitadas."""
    raiz = (casa or pathlib.Path.home()) / ".steam" / "root"
    if not raiz.exists():
        return []
    raiz = raiz.resolve()
    candidatas = list(raiz.glob(_SCOUT))
    for pasta in pastas_de_biblioteca_da_steam(raiz):
        comum = pasta / "steamapps" / "common"
        for molde in _NOS_RUNTIMES:
            candidatas.extend(comum.glob(molde))
    reais: dict[pathlib.Path, None] = {}
    for candidata in sorted(candidatas):
        with contextlib.suppress(OSError):
            real = candidata.resolve(strict=True)
            if real.is_file():
                reais.setdefault(real, None)
    return list(reais)


def _tem_pai_usb(dispositivo: pathlib.Path) -> bool:
    atual = dispositivo.resolve()
    while str(atual).startswith("/sys/devices/") and atual != atual.parent:
        with contextlib.suppress(OSError):
            if "DEVTYPE=usb_device" in (atual / "uevent").read_text(errors="replace"):
                return True
        atual = atual.parent
    return False


def piso_da_enumeracao_hid(
    classe: pathlib.Path = pathlib.Path("/sys/class/hidraw"),
    dev: pathlib.Path = pathlib.Path("/dev"),
) -> list[str]:
    """Os `hidraw` que TODA biblioteca medida lista — o chão da conferência."""
    nos: list[str] = []
    for entrada in sorted(classe.glob("hidraw*")):
        no = dev / entrada.name
        if not os.access(no, os.R_OK | os.W_OK):
            continue
        try:
            uevent = (entrada / "device" / "uevent").read_text(errors="replace")
        except OSError:
            continue
        achado = re.search(r"^HID_ID=([0-9A-Fa-f]+):", uevent, re.MULTILINE)
        barramento = int(achado.group(1), 16) if achado else None
        if barramento == 0x0005 or (
            barramento == 0x0003 and _tem_pai_usb(entrada / "device")
        ):
            nos.append(str(no))
    return nos


def _mascara(uniq: str | None) -> str | None:
    """A máscara da casa, pelo dono (`core/formas_do_endereco`): nenhuma conta à mão."""
    from hefesto_dualsense4unix.core.formas_do_endereco import mascarar as pelo_dono

    return pelo_dono(uniq) if uniq else uniq


def _uniq_do_no(caminho: str | None) -> str | None:
    """O `uniq` do nó evdev que o SDL abriu — a propriedade de POSSE."""
    if not caminho or not caminho.startswith("/dev/input/event"):
        return None
    alvo = (
        pathlib.Path("/sys/class/input") / pathlib.Path(caminho).name / "device" / "uniq"
    )
    try:
        return alvo.read_text().strip() or None
    except OSError:
        return None


def _carregar(bib: Biblioteca) -> Any:
    if bib.pre_carregar is not None:
        ctypes.CDLL(str(bib.pre_carregar), mode=ctypes.RTLD_GLOBAL)
    sdl = ctypes.CDLL(str(bib.caminho))
    sdl.SDL_GetError.restype = ctypes.c_char_p
    sdl.SDL_GetRevision.restype = ctypes.c_char_p
    return sdl


def _versao_e_revisao(sdl: Any, api: int) -> tuple[str, str]:
    revisao = (sdl.SDL_GetRevision() or b"").decode(errors="replace")
    if api == 3:
        sdl.SDL_GetVersion.restype = ctypes.c_int
        numero = int(sdl.SDL_GetVersion())
        return f"{numero // 1000000}.{numero // 1000 % 1000}.{numero % 1000}", revisao
    versao = _Versao2()
    sdl.SDL_GetVersion(ctypes.byref(versao))
    return f"{versao.major}.{versao.minor}.{versao.patch}", revisao


def o_hidapi_da_biblioteca_enumera(sdl: Any, api: int) -> list[dict[str, Any]]:
    """O que ``SDL_hid_enumerate(0, 0)`` devolve — a chamada do subsistema de joystick."""
    estrutura: Any = _InfoHid3 if api == 3 else _InfoHid
    sdl.SDL_hid_init.restype = ctypes.c_int
    sdl.SDL_hid_enumerate.restype = ctypes.POINTER(estrutura)
    sdl.SDL_hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
    sdl.SDL_hid_free_enumeration.argtypes = [ctypes.POINTER(estrutura)]
    sdl.SDL_hid_init()
    cabeca = sdl.SDL_hid_enumerate(0, 0)
    fora: list[dict[str, Any]] = []
    atual = cabeca
    while atual and len(fora) < _TETO_DE_ENTRADAS_HID:
        d = atual.contents
        item: dict[str, Any] = {
            "no": d.path.decode(errors="replace") if d.path else None,
            "vid_pid": f"{d.vendor_id:04x}:{d.product_id:04x}",
            "usage": f"{d.usage_page:#06x}/{d.usage:#06x}",
        }
        if api == 3:
            item["bus_type"] = d.bus_type
        fora.append(item)
        atual = d.next
    if cabeca:
        sdl.SDL_hid_free_enumeration(cabeca)
    return fora


class _ApiDois:
    """Os controles pela API da SDL2 (a clássica e o sdl2-compat)."""

    def __init__(self, sdl: Any) -> None:
        self.sdl = sdl
        p, i, f = ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_float)
        for nome, res, args in (
            ("SDL_Init", i, [ctypes.c_uint32]),
            ("SDL_NumJoysticks", i, []),
            ("SDL_IsGameController", i, [i]),
            ("SDL_GameControllerOpen", p, [i]),
            ("SDL_GameControllerName", ctypes.c_char_p, [p]),
            ("SDL_GameControllerGetJoystick", p, [p]),
            ("SDL_JoystickPath", ctypes.c_char_p, [p]),
            ("SDL_GameControllerHasSensor", i, [p, i]),
            ("SDL_GameControllerSetSensorEnabled", i, [p, i, i]),
            ("SDL_GameControllerGetSensorData", i, [p, i, f, i]),
            ("SDL_GameControllerClose", None, [p]),
        ):
            getattr(sdl, nome).restype = res
            getattr(sdl, nome).argtypes = args

    def subir(self) -> None:
        if self.sdl.SDL_Init(SDL_INIT_GAMECONTROLLER) != 0:
            raise SystemExit(f"SDL não subiu: {self.sdl.SDL_GetError().decode()}")

    def abrir_todos(self) -> list[int]:
        abertos = []
        for indice in range(self.sdl.SDL_NumJoysticks()):
            if self.sdl.SDL_IsGameController(indice):
                controle = self.sdl.SDL_GameControllerOpen(indice)
                if controle:
                    abertos.append(controle)
        return abertos

    def nome(self, c: int) -> str:
        return (self.sdl.SDL_GameControllerName(c) or b"").decode(errors="replace")

    def caminho(self, c: int) -> bytes | None:
        return self.sdl.SDL_JoystickPath(self.sdl.SDL_GameControllerGetJoystick(c))

    def tem(self, c: int, tipo: int) -> bool:
        return bool(self.sdl.SDL_GameControllerHasSensor(c, tipo))

    def ligar(self, c: int, tipo: int) -> bool:
        return self.sdl.SDL_GameControllerSetSensorEnabled(c, tipo, 1) == 0

    def ler(self, c: int, tipo: int, buf: Any) -> bool:
        return self.sdl.SDL_GameControllerGetSensorData(c, tipo, buf, 3) == 0

    def fechar(self, c: int) -> None:
        self.sdl.SDL_GameControllerClose(c)


class _ApiTres:
    """Os controles pela API do SDL3."""

    def __init__(self, sdl: Any) -> None:
        self.sdl = sdl
        p, b, u = ctypes.c_void_p, ctypes.c_bool, ctypes.c_uint32
        i, f = ctypes.c_int, ctypes.POINTER(ctypes.c_float)
        for nome, res, args in (
            ("SDL_Init", b, [u]),
            ("SDL_GetJoysticks", ctypes.POINTER(u), [ctypes.POINTER(i)]),
            ("SDL_IsGamepad", b, [u]),
            ("SDL_OpenGamepad", p, [u]),
            ("SDL_GetGamepadName", ctypes.c_char_p, [p]),
            ("SDL_GetGamepadPath", ctypes.c_char_p, [p]),
            ("SDL_GamepadHasSensor", b, [p, i]),
            ("SDL_SetGamepadSensorEnabled", b, [p, i, b]),
            ("SDL_GetGamepadSensorData", b, [p, i, f, i]),
            ("SDL_CloseGamepad", None, [p]),
            ("SDL_free", None, [p]),
        ):
            getattr(sdl, nome).restype = res
            getattr(sdl, nome).argtypes = args

    def subir(self) -> None:
        if not self.sdl.SDL_Init(SDL_INIT_GAMECONTROLLER):
            raise SystemExit(f"SDL não subiu: {self.sdl.SDL_GetError().decode()}")

    def abrir_todos(self) -> list[int]:
        quantos = ctypes.c_int(0)
        ids = self.sdl.SDL_GetJoysticks(ctypes.byref(quantos))
        abertos = []
        for k in range(quantos.value):
            if self.sdl.SDL_IsGamepad(ids[k]):
                controle = self.sdl.SDL_OpenGamepad(ids[k])
                if controle:
                    abertos.append(controle)
        if ids:
            self.sdl.SDL_free(ctypes.cast(ids, ctypes.c_void_p))
        return abertos

    def nome(self, c: int) -> str:
        return (self.sdl.SDL_GetGamepadName(c) or b"").decode(errors="replace")

    def caminho(self, c: int) -> bytes | None:
        return self.sdl.SDL_GetGamepadPath(c)

    def tem(self, c: int, tipo: int) -> bool:
        return bool(self.sdl.SDL_GamepadHasSensor(c, tipo))

    def ligar(self, c: int, tipo: int) -> bool:
        return bool(self.sdl.SDL_SetGamepadSensorEnabled(c, tipo, True))

    def ler(self, c: int, tipo: int, buf: Any) -> bool:
        return bool(self.sdl.SDL_GetGamepadSensorData(c, tipo, buf, 3))

    def fechar(self, c: int) -> None:
        self.sdl.SDL_CloseGamepad(c)


def olhar_com_o_sdl(sdl: Any, api: Any, segundos: float) -> list[dict[str, Any]]:
    """O que um jogo com ESTA biblioteca veria agora: caminho aberto e amostras."""
    sdl.SDL_PumpEvents()
    time.sleep(0.4)
    sdl.SDL_PumpEvents()
    buf = (ctypes.c_float * 3)()
    abertos = api.abrir_todos()
    expoe: dict[int, dict[str, Any]] = {}
    for c in abertos:
        expoe[c] = {}
        for tipo, chave in _SENSORES:
            tem = api.tem(c, tipo)
            expoe[c][f"o_sdl_expoe_{chave}"] = tem
            expoe[c][f"ligou_{chave}"] = api.ligar(c, tipo) if tem else None
    vistos: dict[int, dict[str, set[Any]]] = {
        c: {"giro": set(), "accel": set()} for c in abertos
    }
    fim = time.time() + segundos
    while time.time() < fim:
        sdl.SDL_PumpEvents()
        for c in abertos:
            for tipo, chave in _SENSORES:
                if api.ler(c, tipo, buf):
                    vistos[c][chave].add(
                        (round(buf[0], 4), round(buf[1], 4), round(buf[2], 4))
                    )
        time.sleep(0.005)
    fora: list[dict[str, Any]] = []
    for c in abertos:
        bruto = api.caminho(c)
        aberto = bruto.decode() if bruto else None
        uniq = _uniq_do_no(aberto)
        fora.append(
            {
                "nome": api.nome(c),
                "o_sdl_abriu": aberto,
                "por_hidapi": bool(bruto and b"hidraw" in bruto),
                "uniq": _mascara(uniq),
                "_uniq_inteiro": uniq,
                **expoe[c],
                "giro_distintos": len(vistos[c]["giro"]),
                "accel_distintos": len(vistos[c]["accel"]),
            }
        )
    for c in abertos:
        api.fechar(c)
    return fora


def olhar_o_no_de_movimento(
    segundos: float, *, sondar_grab: bool = True
) -> list[dict[str, Any]]:
    """O nó "Motion Sensors" de cada peça: dá para abrir? chega evento?"""
    from evdev import InputDevice, ecodes, list_devices

    cod_giro = [ecodes.ecodes[n] for n in EIXOS_DO_GIRO]
    cod_accel = [ecodes.ecodes[n] for n in EIXOS_DO_ACELEROMETRO]

    fora: list[dict[str, Any]] = []
    for caminho in sorted(list_devices()):
        try:
            dev = InputDevice(caminho)
        except OSError as exc:
            fora.append({"no": caminho, "abre": False, "erro": str(exc)})
            continue
        if "Motion Sensors" not in dev.name:
            dev.close()
            continue
        nome, uniq = dev.name, dev.uniq
        exclusivo: bool | None = None
        if sondar_grab:
            exclusivo = False
            try:
                dev.grab()
                dev.ungrab()
            except OSError:
                exclusivo = True
        os.set_blocking(dev.fd, False)
        eventos = 0
        atual: dict[int, int] = {}
        giros: set[Any] = set()
        accels: set[Any] = set()
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                for ev in dev.read():
                    eventos += 1
                    if ev.type == ecodes.EV_ABS:
                        atual[ev.code] = ev.value
                    elif ev.type == ecodes.EV_SYN:
                        giros.add(tuple(atual.get(c) for c in cod_giro))
                        accels.add(tuple(atual.get(c) for c in cod_accel))
            except BlockingIOError:
                time.sleep(0.01)
            except OSError:
                break
        dev.close()
        fora.append(
            {
                "no": caminho,
                "nome": nome,
                "uniq": _mascara(uniq),
                "_uniq_inteiro": uniq,
                "ja_esta_grabado_por_alguem": exclusivo,
                "eventos": eventos,
                "giro_distintos": len(giros),
                "accel_distintos": len(accels),
            }
        )
    return fora


def _ambiente_do_processo(*, so_medir: bool, dica: str, enumerar: bool) -> dict[str, str]:
    """O ambiente de UM processo de biblioteca — sem tela, e com as dicas declaradas."""
    env = {k: v for k, v in os.environ.items() if k not in _SEM_TELA}
    env.update(_SEMPRE_NO_PROCESSO)
    if so_medir:
        env.update(_SO_LEITURA)
    if dica == "ausente":
        env.pop(DICA_DO_ACELEROMETRO, None)
    else:
        env[DICA_DO_ACELEROMETRO] = dica
    if enumerar:
        env[FILTRO_SO_CONTROLES] = "0"
    return env


def _processo_de_uma_biblioteca(args: argparse.Namespace) -> int:
    """O lado de DENTRO: carrega uma biblioteca e imprime uma linha de JSON."""
    os.environ.clear()
    os.environ.update(
        _ambiente_do_processo(
            so_medir=args.so_medir,
            dica=args.dica_do_acelerometro,
            enumerar=args.processo == "enumerar",
        )
    )
    bib = descrever_biblioteca(pathlib.Path(args.lib[0]))
    if isinstance(bib, str):
        print(json.dumps({"erro": bib}, ensure_ascii=False))
        return 2
    sdl = _carregar(bib)
    versao, revisao = _versao_e_revisao(sdl, bib.api)
    fora: dict[str, Any] = {"versao": versao, "revisao": revisao}  # noqa-acento: chave de dado, não prosa
    if args.processo == "enumerar":
        fora["hid"] = o_hidapi_da_biblioteca_enumera(sdl, bib.api)
    else:
        api = _ApiTres(sdl) if bib.api == 3 else _ApiDois(sdl)
        api.subir()
        fora["controles"] = olhar_com_o_sdl(sdl, api, args.segundos)
        sdl.SDL_Quit()
    print(json.dumps(fora, ensure_ascii=False))
    return 0


def _rodar_processo(
    bib: Biblioteca, papel: str, *, segundos: float, so_medir: bool, dica: str
) -> dict[str, Any]:
    comando = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "--processo", papel,
        "--lib", str(bib.caminho),
        "--segundos", str(segundos),
        "--dica-do-acelerometro", dica,
    ]
    if so_medir:
        comando.append("--so-medir")
    env = _ambiente_do_processo(so_medir=so_medir, dica=dica, enumerar=papel == "enumerar")
    try:
        feito = subprocess.run(
            comando, env=env, capture_output=True, text=True,
            timeout=segundos + 60, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"erro": f"o processo «{papel}» passou do tempo"}
    linha = next(
        (x for x in reversed(feito.stdout.splitlines()) if x.startswith("{")), None
    )
    if linha is None or feito.returncode not in (0, 2):
        return {
            "erro": f"o processo «{papel}» saiu com rc={feito.returncode}",
            "stderr": feito.stderr.strip().splitlines()[-3:],
        }
    dados: dict[str, Any] = json.loads(linha)
    return dados


def medir_uma_biblioteca(
    caminho: pathlib.Path,
    piso: list[str],
    *,
    segundos: float,
    so_medir: bool,
    dica: str,
    enumerar: bool = True,
) -> dict[str, Any]:
    """A enumeração conferida e os controles de UMA biblioteca, cada um no seu processo."""
    medida: dict[str, Any] = {
        "biblioteca": str(caminho),
        "dicas": {
            DICA_DO_ACELEROMETRO: "padrão (1)" if dica == "ausente" else dica,
            "SDL_JOYSTICK_HIDAPI": "0" if so_medir else "padrão",
        },
    }
    bib = descrever_biblioteca(caminho)
    if isinstance(bib, str):
        medida["erro"] = bib
        return medida
    medida["api"] = bib.api
    medida["sdl2_compat"] = bib.compat
    opcoes = {"segundos": segundos, "so_medir": so_medir, "dica": dica}
    if enumerar:
        lista = _rodar_processo(bib, "enumerar", **opcoes)
        if "erro" in lista:
            medida["erro"] = lista["erro"]
            medida["stderr"] = lista.get("stderr")
            return medida
        nos = sorted({item["no"] for item in lista["hid"] if item.get("no")})
        medida["hid"] = {
            "com_o_filtro_de_controles": "0",
            "entradas": len(lista["hid"]),
            "nos": nos,
            "piso": len(piso),
            "faltam_do_piso": [no for no in piso if no not in nos],
            "dualsense": [i for i in lista["hid"] if i["vid_pid"].startswith("054c:")],
        }
    controles = _rodar_processo(bib, "controles", **opcoes)
    if "erro" in controles:
        medida["erro"] = controles["erro"]
        medida["stderr"] = controles.get("stderr")
        return medida
    medida["versao"] = controles["versao"]  # noqa-acento: chave de dado, não prosa
    medida["revisao"] = controles["revisao"]  # noqa-acento: chave de dado, não prosa
    medida["controles"] = controles["controles"]
    return medida


async def _chamar(metodo: str, params: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    async with IpcClient.connect() as cliente:
        return await cliente.call(metodo, params, timeout=15.0)


def _uniq_do_primeiro_fisico() -> str | None:
    from hefesto_dualsense4unix.core.evdev_reader import (
        discover_dualsense_motion_evdevs,
    )

    mapa = discover_dualsense_motion_evdevs()
    return next(iter(sorted(mapa)), None)


def _o_no_da_mesma_peca(
    controle: dict[str, Any], nos: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """O nó "Motion Sensors" da MESMA peça que o SDL abriu — casado por `uniq`."""
    alvo = controle.get("_uniq_inteiro")
    if not alvo:
        return None
    return next((n for n in nos if n.get("_uniq_inteiro") == alvo), None)


def _rotulo(medida: dict[str, Any]) -> str:
    """Quem respondeu: a biblioteca, a revisão e a dica — nunca só "o SDL"."""
    caminho = str(medida["biblioteca"]).replace(str(pathlib.Path.home()), "~", 1)
    compat = " sdl2-compat" if medida.get("sdl2_compat") else ""
    return (
        f"libSDL {medida.get('versao', '?')}{compat} «{medida.get('revisao', '?')}» "  # noqa-acento: chave de dado
        f"em {caminho}, {DICA_DO_ACELEROMETRO}={medida['dicas'][DICA_DO_ACELEROMETRO]}"
    )


def _chave_do_controle(controle: dict[str, Any]) -> Any:
    return controle.get("_uniq_inteiro") or controle.get("o_sdl_abriu") or controle["nome"]


def _veredito(
    antes: list[dict[str, Any]],
    depois: list[dict[str, Any]] | None,
    nos: list[dict[str, Any]] | None = None,
) -> list[str]:
    """As frases do fim — uma por controle POR BIBLIOTECA, e cada uma diz quem respondeu."""
    nos = nos or []
    depois_por_bib = {m["biblioteca"]: m for m in (depois or [])}
    linhas: list[str] = []
    for medida in antes:
        if "erro" in medida:
            linhas.append(f"[{medida['biblioteca']}] NÃO MEDIDA — {medida['erro']}")
            continue
        rotulo = _rotulo(medida)
        hid = medida.get("hid")
        if hid and hid["faltam_do_piso"]:
            linhas.append(
                f"[{rotulo}] A ENUMERAÇÃO HID NÃO ALCANÇA O PISO: {len(hid['nos'])} "
                f"nó(s) listado(s), e faltam {len(hid['faltam_do_piso'])} dos "
                f"{hid['piso']} que toda biblioteca medida lista. A struct deste "
                "ensaio não casa com esta biblioteca: não conclua nada da lista."
            )
        par = depois_por_bib.get(medida["biblioteca"]) if depois is not None else None
        por_chave = {_chave_do_controle(d): d for d in (par or {}).get("controles", [])}
        for c in medida["controles"]:
            via = "hidraw (HIDAPI)" if c["por_hidapi"] else "evdev"
            if c.get("o_sdl_expoe_giro") is False:
                no = _o_no_da_mesma_peca(c, nos)
                tinha = (
                    f" — e o nó de movimento desta MESMA peça entregou "
                    f"{no['giro_distintos']} amostras distintas de giro: o dado existe"
                    if no and no.get("giro_distintos")
                    else ""
                )
                linhas.append(
                    f"[{rotulo}] {c['nome']}: ESTA BIBLIOTECA NÃO EXPÕE GIROSCÓPIO "
                    f"neste controle (aberto por {via}; HasSensor=False){tinha}. É a "
                    "resposta da biblioteca com esta dica, não do vpad: um jogo que "
                    "carregue ESTA biblioteca pergunta e ouve NÃO."
                )
                continue
            if depois is None:
                linhas.append(
                    f"[{rotulo}] {c['nome']}: a biblioteca expõe giroscópio e "
                    f"recebeu {c['giro_distintos']} amostras distintas por {via}."
                )
                continue
            d = por_chave.get(_chave_do_controle(c))
            if d is None:
                linhas.append(f"[{rotulo}] {c['nome']}: sumiu entre as duas medições")
            elif c["giro_distintos"] < BASAL_MINIMO:
                linhas.append(
                    f"[{rotulo}] {c['nome']}: INCONCLUSIVO — o basal trouxe só "
                    f"{c['giro_distintos']} amostras de giro por {via}. Mexa no "
                    "controle durante a medição; parado, 'parou de chegar' é "
                    "indistinguível de 'nunca chegou'."
                )
            elif d["giro_distintos"] == 0:
                linhas.append(
                    f"[{rotulo}] {c['nome']}: O JOGO PAROU DE VER O GIRO "
                    f"({c['giro_distintos']} → 0 amostras, por {via})."
                )
            else:
                linhas.append(
                    f"[{rotulo}] {c['nome']}: O GIRO CONTINUA CHEGANDO "
                    f"({c['giro_distintos']} → {d['giro_distintos']}, por {via}). "
                    "Se o caminho é hidraw do FÍSICO, é o limite medido do Modo "
                    "Nativo — o daemon não escreve nesse report."
                )
    return linhas


def _algo_nao_confere(medidas: list[dict[str, Any]]) -> bool:
    return any(
        "erro" in m or bool((m.get("hid") or {}).get("faltam_do_piso")) for m in medidas
    )


def _sem_o_endereco(valor: Any) -> Any:
    """O relatório sem as chaves de junção — o que SAI não leva endereço real."""
    if isinstance(valor, dict):
        return {k: _sem_o_endereco(v) for k, v in valor.items() if not str(k).startswith("_")}
    if isinstance(valor, list):
        return [_sem_o_endereco(v) for v in valor]
    return valor


# ---------------------------------------------------------------------------
# O JOGADOR (O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01, degraus 1 e 2): o SDL3 com o HIDAPI
# LIGADO abre UM vpad, escolhido pelo serial, e conta o que um jogo contaria.
# ---------------------------------------------------------------------------
JOGADORES = ("P1", "P2", "P3", "P4")
NOME_DO_PS5 = "DualSense Edge Wireless Controller"

#: Os tipos de evento do SDL3, lidos nas libs reais com um joystick VIRTUAL (3.4.14 e 3.4.16).
EV_BOTAO_BAIXO = 0x651
EV_BOTAO_CIMA = 0x652
EV_TOQUE_BAIXO = 0x656
EV_TOQUE_MOVE = 0x657
EV_TOQUE_CIMA = 0x658
EV_SENSOR = 0x659
BOTAO_DO_TOUCHPAD = 20  # SDL_GAMEPAD_BUTTON_TOUCHPAD

GRAVIDADE = 9.8
GRAVIDADE_TOLERANCIA = 0.5
SALTO_MAXIMO_NS = 100_000_000  # 0,1 s entre dois `sensor_timestamp`
_ESCRITAS = ("output_count", "lightbar_replicas", "player_led_replicas")
_CONTADORES = (*_ESCRITAS, "visto_ha_s", "game_open")

_FORMATO_TOQUE = struct.Struct("<IIQIiifff")
_FORMATO_SENSOR = struct.Struct("<IIQIi3f4xQ")
_FORMATO_BOTAO = struct.Struct("<IIQIBB")


def ler_evento(bruto: bytes) -> dict[str, Any] | None:
    """Um `SDL_Event` do SDL3 (128 bytes, little-endian); `None` para o que não se conta."""
    if len(bruto) < 4:
        return None
    tipo = struct.unpack_from("<I", bruto)[0]
    if tipo in (EV_TOQUE_BAIXO, EV_TOQUE_MOVE, EV_TOQUE_CIMA):
        _t, _r, _ts, quem, pad, dedo, x, y, pressao = _FORMATO_TOQUE.unpack_from(bruto)
        return {"tipo": tipo, "which": quem, "touchpad": pad, "dedo": dedo,
                "x": x, "y": y, "pressao": pressao}
    if tipo == EV_SENSOR:
        _t, _r, _ts, quem, sensor, a, b, c, carimbo = _FORMATO_SENSOR.unpack_from(bruto)
        return {"tipo": tipo, "which": quem, "sensor": sensor, "dados": (a, b, c),
                "carimbo_ns": carimbo}
    if tipo in (EV_BOTAO_BAIXO, EV_BOTAO_CIMA):
        _t, _r, _ts, quem, botao, baixo = _FORMATO_BOTAO.unpack_from(bruto)
        return {"tipo": tipo, "which": quem, "botao": botao, "baixo": bool(baixo)}
    return None


def uniq_do_no_aberto(
    caminho: str | None,
    hidraw: pathlib.Path = pathlib.Path("/sys/class/hidraw"),
    entrada: pathlib.Path = pathlib.Path("/sys/class/input"),
) -> str | None:
    """O `uniq` (o serial do SDL3) do nó aberto: `hidraw` pelo `HID_UNIQ`, evdev pelo `uniq`."""
    if not caminho:
        return None
    nome = pathlib.Path(caminho).name
    if nome.startswith("hidraw"):
        try:
            texto = (hidraw / nome / "device" / "uevent").read_text(errors="replace")
        except OSError:
            return None
        achado = re.search(r"^HID_UNIQ=(.+)$", texto, re.MULTILINE)
        return achado.group(1).strip() if achado else None
    if nome.startswith("event"):
        try:
            return (entrada / nome / "device" / "uniq").read_text().strip() or None
        except OSError:
            return None
    return None


def _chave_do_no(caminho: str | None) -> tuple[int, int] | None:
    """`(st_dev, st_ino)` de um caminho — `os.stat` não abre nada."""
    if not caminho:
        return None
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


def vpad_do_jogador(estado: dict[str, Any], jogador: str) -> dict[str, Any] | None:
    """O vpad do jogador no `state_full`: `rumble_ff.per_vpad[]` casado pelo número (P1..P4)."""
    numero = JOGADORES.index(jogador) + 1
    lista = (estado.get("rumble_ff") or {}).get("per_vpad") or []
    return next((v for v in lista if isinstance(v, dict) and v.get("player") == numero), None)


def contadores_dos_vpads(estado: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Os contadores do degrau 2, por jogador (1..4)."""
    lista = (estado.get("rumble_ff") or {}).get("per_vpad") or []
    return {
        int(v["player"]): {c: v.get(c) for c in _CONTADORES}
        for v in lista if isinstance(v, dict) and isinstance(v.get("player"), int)
    }


def escolher_o_id(candidatos: list[dict[str, Any]], uniq_alvo: str) -> int | None:
    """O id do SDL cujo serial é o do vpad — NUNCA pelo nome nem pelo GUID, iguais nos quatro."""
    alvo = uniq_alvo.casefold()
    for c in candidatos:
        if (c.get("uniq") or "").casefold() == alvo:
            return int(c["id"])
    return None


def fds_abertos_dos_vpads(
    nos: dict[int, str], pasta: pathlib.Path = pathlib.Path("/proc/self/fd")
) -> dict[int, bool]:
    """Quais `hidraw` de vpad este processo tem aberto — o `fd` casado por `(st_dev, st_ino)`."""
    chaves = {j: _chave_do_no(no) for j, no in nos.items()}
    abertos: set[tuple[int, int]] = set()
    with contextlib.suppress(OSError):
        for entrada in pasta.iterdir():
            chave = _chave_do_no(str(entrada))
            if chave is not None:
                abertos.add(chave)
    return {j: chave is not None and chave in abertos for j, chave in chaves.items()}


@dataclass
class Fase:
    """O que UMA fase da medição contou (parado, ou com o dedo)."""

    nome: str
    toque_baixo: int = 0
    toque_move: int = 0
    toque_cima: int = 0
    cliques: int = 0
    carimbos_giro: list[int] = field(default_factory=list)
    carimbos_accel: list[int] = field(default_factory=list)
    modulos_accel: list[float] = field(default_factory=list)

    def contar(self, ev: dict[str, Any]) -> None:
        tipo = ev["tipo"]
        if tipo == EV_TOQUE_BAIXO:
            self.toque_baixo += 1
        elif tipo == EV_TOQUE_MOVE:
            self.toque_move += 1
        elif tipo == EV_TOQUE_CIMA:
            self.toque_cima += 1
        elif tipo == EV_BOTAO_BAIXO and ev["botao"] == BOTAO_DO_TOUCHPAD:
            self.cliques += 1
        elif tipo == EV_SENSOR:
            if ev["sensor"] == SDL_SENSOR_GYRO:
                self.carimbos_giro.append(ev["carimbo_ns"])
            elif ev["sensor"] == SDL_SENSOR_ACCEL:
                self.carimbos_accel.append(ev["carimbo_ns"])
                a, b, c = ev["dados"]
                self.modulos_accel.append((a * a + b * b + c * c) ** 0.5)

    def resumo(self) -> dict[str, Any]:
        def maior(carimbos: list[int]) -> int | None:
            if len(carimbos) < 2:
                return None
            return max(b - a for a, b in itertools.pairwise(carimbos))

        modulos = self.modulos_accel
        return {
            "fase": self.nome,
            "toque_baixo": self.toque_baixo,
            "toque_move": self.toque_move,
            "toque_cima": self.toque_cima,
            "cliques_do_touchpad": self.cliques,
            "giro_amostras": len(self.carimbos_giro),
            "accel_amostras": len(self.carimbos_accel),
            "maior_intervalo_giro_ns": maior(self.carimbos_giro),
            "maior_intervalo_accel_ns": maior(self.carimbos_accel),
            "modulo_medio_accel": (sum(modulos) / len(modulos)) if modulos else None,
        }


def _tudo_igual(valores: list[str]) -> bool:
    return len(set(valores)) == 1


def laudo(medida: dict[str, Any]) -> list[dict[str, Any]]:
    """Os itens de aceite do degrau 1, puros: cada um diz `ok` e o número que o sustenta."""
    itens: list[dict[str, Any]] = []

    def item(nome: str, ok: bool, detalhe: str) -> None:
        itens.append({"item": nome, "ok": bool(ok), "detalhe": detalhe})

    vpads = medida.get("vpads") or []
    esc = medida.get("escolhido") or {}
    nome = esc.get("nome")
    item("driver_ps5_no_vpad_escolhido", nome == NOME_DO_PS5,
         f"nome SDL «{nome}», esperado «{NOME_DO_PS5}»")
    guids = [v.get("guid") or "" for v in vpads]
    seriais = [v.get("uniq") or "" for v in vpads]
    mais_de_um = len(vpads) >= 2
    item("guids_iguais_e_seriais_distintos",
         mais_de_um and _tudo_igual(guids) and len(set(seriais)) == len(seriais)
         and all(seriais),
         f"{len(vpads)} vpad(s) listado(s); {len(set(guids))} GUID(s) distinto(s), "
         f"{len(set(seriais))} serial(is) distinto(s)")
    abertos = medida.get("fds_dos_vpads") or {}
    item("hidraw_de_todo_vpad_aberto", bool(abertos) and all(abertos.values()),
         f"abertos por jogador: {dict(sorted(abertos.items()))}")
    por_vpad = medida.get("escritas_por_jogador") or {}
    escolhido = esc.get("jogador")
    fora = {j: n for j, n in por_vpad.items() if j != escolhido and n}
    item("escrita_so_no_escolhido", bool(por_vpad) and not fora,
         f"escritas observadas por jogador: {dict(sorted(por_vpad.items()))}")
    item("serial_e_no_conferem", bool(esc.get("serial_confere")) and bool(esc.get("no_confere")),
         f"serial confere {esc.get('serial_confere')}; nó confere {esc.get('no_confere')}")
    item("um_touchpad_de_dois_dedos",
         esc.get("touchpads") == 1 and esc.get("dedos") == 2,
         f"{esc.get('touchpads')} touchpad(s), {esc.get('dedos')} dedo(s)")
    item("giro_e_acelerometro", bool(esc.get("tem_giro")) and bool(esc.get("tem_accel")),
         f"giro {esc.get('tem_giro')}, acelerômetro {esc.get('tem_accel')}")
    fases = {f["fase"]: f for f in medida.get("fases") or []}
    parado = fases.get("parado") or {}
    modulo = parado.get("modulo_medio_accel")
    item("gravidade_parado",
         modulo is not None and abs(modulo - GRAVIDADE) <= GRAVIDADE_TOLERANCIA,
         f"|acel| parado = {modulo} (esperado {GRAVIDADE} ± {GRAVIDADE_TOLERANCIA})")
    intervalos = {
        f"{f['fase']}/{s}": f.get(f"maior_intervalo_{s}_ns")
        for f in fases.values() for s in ("giro", "accel")
    }
    item("carimbo_sem_salto",
         bool(intervalos) and all(v is not None and v <= SALTO_MAXIMO_NS
                                  for v in intervalos.values()),
         f"maior intervalo (ns) por fase e sensor: {intervalos}; teto {SALTO_MAXIMO_NS}")
    dedo = fases.get("dedo") or {}
    toques = (dedo.get("toque_baixo") or 0) + (dedo.get("toque_move") or 0)
    item("toque_e_clique_chegam",
         toques > 0 and (dedo.get("cliques_do_touchpad") or 0) > 0,
         f"toque {toques} evento(s), clique {dedo.get('cliques_do_touchpad')}")
    return itens


class _Guid(ctypes.Structure):
    _fields_ = [("data", ctypes.c_uint8 * 16)]


class _JogoSdl3:
    """O SDL3 como um jogo o usa: enumera os gamepads, abre UM, drena os eventos."""

    def __init__(self, sdl: Any) -> None:
        self.sdl = sdl
        p, b, u, i = ctypes.c_void_p, ctypes.c_bool, ctypes.c_uint32, ctypes.c_int
        for nome, res, args in (
            ("SDL_Init", b, [u]),
            ("SDL_PumpEvents", None, []),
            ("SDL_GetGamepads", ctypes.POINTER(u), [ctypes.POINTER(i)]),
            ("SDL_GetGamepadNameForID", ctypes.c_char_p, [u]),
            ("SDL_GetGamepadPathForID", ctypes.c_char_p, [u]),
            ("SDL_GetGamepadGUIDForID", _Guid, [u]),
            ("SDL_GUIDToString", None, [_Guid, ctypes.c_char_p, i]),
            ("SDL_OpenGamepad", p, [u]),
            ("SDL_GetGamepadSerial", ctypes.c_char_p, [p]),
            ("SDL_GetGamepadPath", ctypes.c_char_p, [p]),
            ("SDL_GetGamepadName", ctypes.c_char_p, [p]),
            ("SDL_GetNumGamepadTouchpads", i, [p]),
            ("SDL_GetNumGamepadTouchpadFingers", i, [p, i]),
            ("SDL_GamepadHasSensor", b, [p, i]),
            ("SDL_SetGamepadSensorEnabled", b, [p, i, b]),
            ("SDL_PollEvent", b, [p]),
            ("SDL_CloseGamepad", None, [p]),
            ("SDL_free", None, [p]),
            ("SDL_Quit", None, []),
        ):
            getattr(sdl, nome).restype = res
            getattr(sdl, nome).argtypes = args

    def subir(self) -> None:
        if not self.sdl.SDL_Init(SDL_INIT_GAMECONTROLLER):
            raise SystemExit(f"SDL não subiu: {self.sdl.SDL_GetError().decode()}")
        self.sdl.SDL_PumpEvents()
        time.sleep(0.4)
        self.sdl.SDL_PumpEvents()

    def enumerar(self) -> list[dict[str, Any]]:
        quantos = ctypes.c_int(0)
        ids = self.sdl.SDL_GetGamepads(ctypes.byref(quantos))
        fora: list[dict[str, Any]] = []
        for k in range(quantos.value):
            identidade = ids[k]
            texto = ctypes.create_string_buffer(64)
            self.sdl.SDL_GUIDToString(
                self.sdl.SDL_GetGamepadGUIDForID(identidade), texto, 64)
            caminho = self.sdl.SDL_GetGamepadPathForID(identidade)
            fora.append({
                "id": int(identidade),
                "nome": (self.sdl.SDL_GetGamepadNameForID(identidade) or b"").decode(
                    errors="replace"),
                "guid": texto.value.decode(),
                "caminho": caminho.decode() if caminho else None,
            })
        if ids:
            self.sdl.SDL_free(ctypes.cast(ids, ctypes.c_void_p))
        return fora

    def abrir(self, identidade: int) -> Any:
        return self.sdl.SDL_OpenGamepad(identidade) or None

    def descrever(self, h: Any) -> dict[str, Any]:
        serial = self.sdl.SDL_GetGamepadSerial(h)
        caminho = self.sdl.SDL_GetGamepadPath(h)
        pads = int(self.sdl.SDL_GetNumGamepadTouchpads(h))
        return {
            "nome": (self.sdl.SDL_GetGamepadName(h) or b"").decode(errors="replace"),
            "serial": serial.decode() if serial else None,
            "caminho": caminho.decode() if caminho else None,
            "touchpads": pads,
            "dedos": int(self.sdl.SDL_GetNumGamepadTouchpadFingers(h, 0)) if pads else 0,
            "tem_giro": bool(self.sdl.SDL_GamepadHasSensor(h, SDL_SENSOR_GYRO)),
            "tem_accel": bool(self.sdl.SDL_GamepadHasSensor(h, SDL_SENSOR_ACCEL)),
        }

    def ligar_sensores(self, h: Any) -> None:
        for tipo, _chave in _SENSORES:
            self.sdl.SDL_SetGamepadSensorEnabled(h, tipo, True)

    def eventos(self) -> list[dict[str, Any]]:
        buf = (ctypes.c_ubyte * 128)()
        fora: list[dict[str, Any]] = []
        while self.sdl.SDL_PollEvent(buf):
            ev = ler_evento(bytes(buf))
            if ev is not None:
                fora.append(ev)
        return fora

    def fechar(self, h: Any) -> None:
        self.sdl.SDL_CloseGamepad(h)

    def encerrar(self) -> None:
        self.sdl.SDL_Quit()


def sondar_o_jogador(
    jogo: Any,
    vpad: dict[str, Any],
    todos: dict[int, dict[str, Any]],
    *,
    fotografar: Any,
    fase_segundos: float,
    dormir: Any = time.sleep,
    agora: Any = time.monotonic,
    pasta_fd: pathlib.Path = pathlib.Path("/proc/self/fd"),
) -> dict[str, Any]:
    """Enumera, abre SÓ o vpad pedido (pelo serial), e conta as duas fases.

    ``todos`` é o `per_vpad` por jogador; ``fotografar()`` devolve os contadores dos vpads
    naquele instante (o degrau 2), e é chamado antes de abrir, no fim de cada fase e depois de
    fechar.
    """
    medida: dict[str, Any] = {"contadores": {"antes": fotografar()}}
    candidatos = jogo.enumerar()
    for c in candidatos:
        c["uniq"] = uniq_do_no_aberto(c.get("caminho"))
    medida["vpads"] = [
        {"nome": c["nome"], "guid": c["guid"], "uniq": c["uniq"],
         "_uniq_inteiro": c["uniq"], "caminho": c["caminho"]}
        for c in candidatos if c["uniq"] and c["uniq"].casefold() in {
            (v.get("vpad_uniq") or "").casefold() for v in todos.values()}
    ]
    identidade = escolher_o_id(candidatos, vpad["vpad_uniq"])
    if identidade is None:
        medida["erro"] = "o SDL não lista nenhum gamepad com o serial deste vpad"
        medida["fds_dos_vpads"] = {}
        medida["escolhido"] = {}
        medida["fases"] = []
        return medida
    alvo = next(c for c in candidatos if c["id"] == identidade)
    h = jogo.abrir(identidade)
    if h is None:
        medida["erro"] = "o SDL não abriu o vpad escolhido"
        medida["fds_dos_vpads"] = {}
        medida["escolhido"] = {}
        medida["fases"] = []
        return medida
    abriu = jogo.descrever(h)
    esperado = vpad.get("hidraw") if pathlib.Path(str(alvo["caminho"])).name.startswith(
        "hidraw") else vpad.get("evdev")
    chave_esperada = _chave_do_no(esperado)
    medida["escolhido"] = {
        **abriu,
        "jogador": vpad["player"],
        "guid": alvo["guid"],
        "serial_confere": (abriu["serial"] or "").casefold() == vpad["vpad_uniq"].casefold(),
        "no_confere": chave_esperada is not None
        and _chave_do_no(abriu["caminho"]) == chave_esperada,
        "_serial_inteiro": abriu["serial"],
    }
    jogo.ligar_sensores(h)
    fases: list[Fase] = []
    medida["contadores"]["durante"] = {}
    for nome in ("parado", "dedo"):
        fase = Fase(nome)
        fim = agora() + fase_segundos
        while agora() < fim:
            for ev in jogo.eventos():
                if ev["which"] == identidade:
                    fase.contar(ev)
            dormir(0.002)
        fases.append(fase)
        medida["contadores"]["durante"][nome] = fotografar()
    medida["fases"] = [f.resumo() for f in fases]
    medida["fds_dos_vpads"] = fds_abertos_dos_vpads(
        {j: v["hidraw"] for j, v in todos.items() if v.get("hidraw")}, pasta_fd)
    jogo.fechar(h)
    dormir(0.5)
    medida["contadores"]["depois"] = fotografar()
    medida["escritas_por_jogador"] = _escritas_por_jogador(medida["contadores"])
    return medida


def _escritas_por_jogador(contadores: dict[str, Any]) -> dict[int, int]:
    """Quanto cada vpad foi escrito entre o antes e o fim da última fase."""
    antes = contadores.get("antes") or {}
    fim = (contadores.get("durante") or {}).get("dedo") or {}
    fora: dict[int, int] = {}
    for jogador, depois in fim.items():
        base = antes.get(jogador) or {}
        fora[jogador] = sum(
            max(0, int(depois.get(c) or 0) - int(base.get(c) or 0)) for c in _ESCRITAS
        )
    return fora


def _ambiente_do_vpad(*, hidapi: str, dica: str) -> dict[str, str]:
    """O ambiente da sonda do jogador: sem tela, e com o HIDAPI como um jogo o tem (ligado)."""
    env = {k: v for k, v in os.environ.items() if k not in _SEM_TELA}
    env.update(_SEMPRE_NO_PROCESSO)
    env["SDL_JOYSTICK_HIDAPI"] = hidapi
    env["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
    env.pop("SDL_HIDAPI_LIBUSB", None)
    if dica == "ausente":
        env.pop(DICA_DO_ACELEROMETRO, None)
    else:
        env[DICA_DO_ACELEROMETRO] = dica
    return env


def _para_a_saida(medida: dict[str, Any]) -> dict[str, Any]:
    """A medida que SAI: o serial dos vpads com a máscara da casa, sem chaves de junção."""
    fora: dict[str, Any] = json.loads(json.dumps(medida, default=str))
    for v in fora.get("vpads") or []:
        v["uniq"] = _mascara(v.get("uniq"))
    esc = fora.get("escolhido") or {}
    if esc.get("serial"):
        esc["serial"] = _mascara(esc["serial"])
    result: dict[str, Any] = _sem_o_endereco(fora)
    return result


def _estado_do_daemon() -> dict[str, Any]:
    resposta = asyncio.run(_chamar("daemon.state_full", {}))
    return resposta if isinstance(resposta, dict) else {}


def _processo_do_vpad(args: argparse.Namespace) -> int:
    """O lado de DENTRO da sonda do jogador: uma biblioteca SDL3, um vpad, uma linha de JSON."""
    os.environ.clear()
    os.environ.update(_ambiente_do_vpad(hidapi=args.hidapi, dica=args.dica_do_acelerometro))
    bib = descrever_biblioteca(pathlib.Path(args.lib[0]))
    if isinstance(bib, str) or bib.api != 3 or bib.compat:
        print(json.dumps({"erro": "a sonda do jogador mede o SDL3, nunca o sdl2-compat"},
                         ensure_ascii=False))
        return 2
    sdl = _carregar(bib)
    versao, revisao = _versao_e_revisao(sdl, bib.api)
    estado = _estado_do_daemon()
    vpad = vpad_do_jogador(estado, args.jogador)
    if vpad is None or not vpad.get("vpad_uniq"):
        print(json.dumps({"erro": f"o daemon não tem vpad do jogador {args.jogador}"},
                         ensure_ascii=False))
        return 2
    todos = {int(v["player"]): v for v in (estado.get("rumble_ff") or {}).get("per_vpad") or []
             if isinstance(v, dict) and isinstance(v.get("player"), int)}
    jogo = _JogoSdl3(sdl)
    jogo.subir()
    medida = sondar_o_jogador(
        jogo, vpad, todos,
        fotografar=lambda: contadores_dos_vpads(_estado_do_daemon()),
        fase_segundos=args.fase_segundos)
    jogo.encerrar()
    medida.update({"versao": versao, "revisao": revisao, "hidapi": args.hidapi,  # noqa-acento: chave de dado, não prosa
                   "jogador": args.jogador})
    medida["laudo"] = laudo(medida)
    print(json.dumps(_para_a_saida(medida), ensure_ascii=False, default=str))
    return 0


def _o_jogador(args: argparse.Namespace) -> int:
    """O lado de FORA: recusa o que não vale, toma a bancada, roda o processo e dá o laudo."""
    if args.so_medir:
        print("RECUSO: --jogador abre o vpad com o HIDAPI ligado e escreve no aparelho; "
              "isto não combina com --so-medir")
        return 2
    if not args.lib or len(args.lib) != 1:
        print("RECUSO: --jogador mede UMA biblioteca SDL3; passe --lib <libSDL3.so.0>")
        return 2
    bib = descrever_biblioteca(pathlib.Path(args.lib[0]))
    if isinstance(bib, str) or bib.api != 3 or bib.compat:
        print("RECUSO: --jogador mede o SDL3; a biblioteca dada não é uma libSDL3")
        return 2
    exigir = subprocess.run(["bash", str(RAIZ / "scripts" / "bancada.sh"), "exigir"],
                            capture_output=True, text=True, check=False)
    if exigir.returncode != 0:
        print("RECUSO: a bancada está tomada por outra reserva; esperar é a resposta")
        return 2
    comando = [sys.executable, str(pathlib.Path(__file__).resolve()), "--processo", "vpad",
               "--lib", args.lib[0], "--jogador", args.jogador, "--hidapi", args.hidapi,
               "--fase-segundos", str(args.fase_segundos),
               "--dica-do-acelerometro", args.dica_do_acelerometro]
    feito = subprocess.run(comando, env=_ambiente_do_vpad(hidapi=args.hidapi,
                           dica=args.dica_do_acelerometro), capture_output=True, text=True,
                           timeout=args.fase_segundos * 2 + 90, check=False)
    linha = next((x for x in reversed(feito.stdout.splitlines()) if x.startswith("{")), None)
    if linha is None or feito.returncode not in (0, 2):
        print(json.dumps({"erro": f"o processo do vpad saiu com rc={feito.returncode}",
                          "stderr": feito.stderr.strip().splitlines()[-3:]},
                         ensure_ascii=False, indent=2))
        return 3
    medida: dict[str, Any] = json.loads(linha)
    medida.setdefault("laudo", [])
    medida["anotar"] = ("olho no plástico: a cor e o número ANTES, DURANTE e DEPOIS; pelo fonte "
                        "eles NÃO voltam ao fechar a sonda — anote também o que os devolve")
    print(json.dumps(medida, ensure_ascii=False, indent=2))
    reprovou = "erro" in medida or not medida["laudo"] or not all(
        i["ok"] for i in medida["laudo"])
    return 3 if reprovou else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--segundos", type=float, default=3.0, help="janela de medição")
    ap.add_argument("--uniq", default=None, help="a peça (padrão: a primeira achada)")
    ap.add_argument(
        "--so-medir",
        action="store_true",
        help="só lê: não chama sensor.set, sem HIDAPI e sem EVIOCGRAB",
    )
    ap.add_argument(
        "--acelerometro",
        action="store_true",
        help="desliga o acelerômetro em vez do giroscópio",
    )
    ap.add_argument(
        "--lib",
        action="append",
        default=None,
        help="caminho de uma libSDL2 ou libSDL3 a medir; repita para várias "
        "(padrão: as dos runtimes da Steam instalados)",
    )
    ap.add_argument(
        "--dica-do-acelerometro",
        choices=("0", "1", "ausente"),
        default=VALOR_QUE_O_JOGO_RECEBE,
        help=f"o {DICA_DO_ACELEROMETRO} de cada biblioteca (padrão: o que o jogo recebe)",
    )
    ap.add_argument(
        "--jogador",
        choices=JOGADORES,
        help="abre SÓ o vpad deste jogador no SDL3, com o HIDAPI ligado (exige --lib de "
        "uma libSDL3; recusa --so-medir)",
    )
    ap.add_argument(
        "--fase-segundos",
        type=float,
        default=5.0,
        help="--jogador: cada fase (parado, com o dedo) dura isto",
    )
    ap.add_argument(
        "--hidapi",
        choices=("1", "0"),
        default="1",
        help="--jogador: o SDL_JOYSTICK_HIDAPI da sonda; 0 só para a mordida (mede o evdev)",
    )
    ap.add_argument(
        "--processo", choices=("enumerar", "controles", "vpad"), help=argparse.SUPPRESS
    )
    args = ap.parse_args()

    if args.processo == "vpad":
        return _processo_do_vpad(args)
    if args.processo:
        return _processo_de_uma_biblioteca(args)
    if args.jogador:
        return _o_jogador(args)

    caminhos = (
        [pathlib.Path(p) for p in args.lib] if args.lib else bibliotecas_dos_runtimes()
    )
    if not caminhos:
        print("nenhuma libSDL de runtime da Steam achada em ~/.steam — passe --lib <caminho>")
        return 1

    piso = piso_da_enumeracao_hid()
    opcoes = {
        "segundos": args.segundos,
        "so_medir": args.so_medir,
        "dica": args.dica_do_acelerometro,
    }
    relatorio: dict[str, Any] = {
        "segundos": args.segundos,
        "piso_hid": piso,
        "antes": [medir_uma_biblioteca(c, piso, **opcoes) for c in caminhos],
        "antes_no_de_movimento": olhar_o_no_de_movimento(
            1.0, sondar_grab=not args.so_medir
        ),
    }

    if args.so_medir:
        relatorio["veredito"] = _veredito(
            relatorio["antes"], None, relatorio["antes_no_de_movimento"]
        )
        print(json.dumps(_sem_o_endereco(relatorio), ensure_ascii=False, indent=2))
        return 3 if _algo_nao_confere(relatorio["antes"]) else 0

    uniq = args.uniq or _uniq_do_primeiro_fisico()
    if not uniq:
        print("nenhum DualSense com nó de movimento na mesa — nada a medir")
        return 1
    sensor = "acelerometro" if args.acelerometro else "giroscopio"
    relatorio["peca"] = _mascara(uniq)
    relatorio["sensor"] = sensor

    relatorio["resposta_do_desligar"] = asyncio.run(
        _chamar("sensor.set", {"uniq": uniq, sensor: False})
    )
    time.sleep(1.5)
    relatorio["depois"] = [
        medir_uma_biblioteca(c, piso, enumerar=False, **opcoes) for c in caminhos
    ]
    relatorio["depois_no_de_movimento"] = olhar_o_no_de_movimento(1.0)

    with contextlib.suppress(Exception):
        relatorio["resposta_do_religar"] = asyncio.run(
            _chamar("sensor.set", {"uniq": uniq, sensor: True})
        )

    relatorio["veredito"] = _veredito(
        relatorio["antes"],
        relatorio["depois"],
        relatorio["antes_no_de_movimento"],
    )
    print(json.dumps(_sem_o_endereco(relatorio), ensure_ascii=False, indent=2))
    return 3 if _algo_nao_confere(relatorio["antes"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
