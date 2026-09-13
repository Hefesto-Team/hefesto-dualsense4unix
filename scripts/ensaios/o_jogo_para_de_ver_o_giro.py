#!/usr/bin/env python3
"""O JOGO para de ver o giro — medido pelo SDL que o jogo CARREGA, não pela interface.

SENSOR-DE-VERDADE-01 / ONDA1-D3. Decisão dela, 04/09/2026:

    *"ele tem que funcionar de verdade. ambos independente do modo e da
    mascara."* <!-- noqa-acento: citação literal dela -->

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
`WAYLAND_DISPLAY`. **Nada nasce na tela dela.**

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
seguinte, e esse só fecha com o olho dela.

SAÍDA: o relatório em JSON, e o código de retorno ``3`` quando alguma
biblioteca não pôde ser medida ou a enumeração dela não alcançou o piso.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import ctypes
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

#: `SDL_INIT_GAMECONTROLLER` na SDL2, `SDL_INIT_GAMEPAD` no SDL3: o mesmo bit.
SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_SENSOR_ACCEL = 1
SDL_SENSOR_GYRO = 2
_SENSORES = ((SDL_SENSOR_GYRO, "giro"), (SDL_SENSOR_ACCEL, "accel"))

#: Abaixo disto o basal não sustenta conclusão nenhuma — o aparelho estava
#: parado, e "parou de chegar" seria indistinguível de "nunca chegou".
BASAL_MINIMO = 5

#: Os três eixos do GIROSCÓPIO no nó evdev "… Motion Sensors", já decodificados
#: pelo kernel. São os mesmos que o `MotionSensorReader` do produto lê.
EIXOS_DO_GIRO = ("ABS_RX", "ABS_RY", "ABS_RZ")

#: Os três do ACELERÔMETRO, no mesmo nó.
EIXOS_DO_ACELEROMETRO = ("ABS_X", "ABS_Y", "ABS_Z")

#: A dica que decide se a libSDL2 2.30.x casa o nó de movimento ao gamepad, e o
#: valor que o jogo recebe do wrapper em toda variante (`compose_env`, em
#: `daemon/launch_env.py`). A régua
#: `tests/unit/test_o_jogo_recebe_a_dica_do_acelerometro.py` confere que o
#: ensaio mede com o mesmo valor que o jogo recebe.
DICA_DO_ACELEROMETRO = "SDL_ACCELEROMETER_AS_JOYSTICK"
VALOR_QUE_O_JOGO_RECEBE = "0"

#: O filtro do SDL3 que faz o ``SDL_hid_enumerate`` listar só controles, ligado
#: por padrão. Medido em 13/09/2026 com o SDL3 3.4.14 do sniper: com o filtro,
#: 2 nós; sem ele, 17 entradas em 6 nós. A conferência da struct contra o piso
#: pede a lista inteira — por isso a enumeração roda num processo à parte, com
#: o filtro desligado, e o processo que abre os controles fica como o do jogo.
FILTRO_SO_CONTROLES = "SDL_HIDAPI_ENUMERATE_ONLY_CONTROLLERS"

_SEMPRE_NO_PROCESSO = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
_SO_LEITURA = {"SDL_JOYSTICK_HIDAPI": "0", "SDL_HIDAPI_LIBUSB": "0"}
_SEM_TELA = ("DISPLAY", "WAYLAND_DISPLAY")
_TETO_DE_ENTRADAS_HID = 512

#: Onde os runtimes da Steam guardam a libSDL, relativo à instalação e às pastas
#: de biblioteca. São convenções de pasta da própria Steam, não versões: a
#: versão é lida da biblioteca achada. Só 64 bits (este python é 64), e as
#: cópias de `var/tmp-*` que o pressure-vessel monta ficam de fora — são do
#: contêiner em uso, não do runtime.
_SCOUT = "ubuntu12_32/steam-runtime/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0*"
_NOS_RUNTIMES = (
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/libSDL3.so.0*",
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/libSDL2-2.0.so.0*",
    "SteamLinuxRuntime_*/*_platform_*/files/lib/x86_64-linux-gnu/sdl2-*/libSDL2-2.0.so.0*",
)


class _InfoHid(ctypes.Structure):
    """`SDL_hid_device_info` da API da SDL2 (``include/SDL_hidapi.h``), até ``next``.

    OS TRÊS INTS DE INTERFACE SÃO O QUE FALTAVA até 13/09/2026. Sem eles o
    ``next`` era lido no deslocamento 56 — em cima de dois ints zerados —,
    virava NULL e a lista parava no primeiro item. Com eles o ``next`` cai no
    72, que é onde a biblioteca o põe. O sdl2-compat devolve esta mesma forma.
    """


_CAMPOS_ATE_A_INTERFACE: list[tuple[str, Any]] = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_ushort),
    ("product_id", ctypes.c_ushort),
    # O serial identifica o aparelho: fica como ponteiro cru, nunca decodificado.
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
    api: int  # 2 ou 3: a API que ela exporta
    compat: bool  # sdl2-compat: a API 2 sobre um SDL3
    pre_carregar: pathlib.Path | None  # o SDL3 que o sdl2-compat abre por NOME


def descrever_biblioteca(caminho: pathlib.Path) -> Biblioteca | str:
    """A biblioteca pronta para carregar, ou a razão de não carregá-la.

    O sdl2-compat abre o SDL3 pelo nome ``libSDL3.so.0``, e esse nome está nos
    bytes dele; a SDL2 clássica não o traz. Carregar um sdl2-compat sem SDL3 por
    perto é pedir falha de carregamento, então ele vai com o SDL3 da mesma pasta
    (sniper, SLR 4) ou da pasta de cima (`sdl2-compat/`, no soldier) — ou não vai.
    """
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
    """Os `hidraw` que TODA biblioteca medida lista — o chão da conferência.

    São os que passam em ``access(R_OK|W_OK)`` (a SDL2 clássica testa isso antes
    de listar) e têm barramento de verdade: USB com pai ``usb_device`` (a SDL2
    clássica descarta o USB sem pai, que é o vpad `uhid`) ou Bluetooth. O SDL3 e
    o sdl2-compat, com o filtro de controles desligado, listam um superconjunto
    disto. Medido em 13/09/2026 nesta máquina: 4 nós no piso; a 2.30.0 lista os
    4, e o SDL3 3.4.14 lista 6.
    """
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
    """O endereço com os octetos 4 e 5 zerados — a máscara desta casa.

    Este ensaio existe para ter a saída COLADA num documento, e documento é
    arquivo versionado: `AA:BB:CC:DD:EE:FF` sai `AA:BB:CC:00:00:FF`. Quem
    junta nó com controle aqui dentro usa o endereço INTEIRO; o que SAI é o
    mascarado. Sem isso o próximo a colar a saída derruba o portão do
    anonimato — ou, pior, publica o rádio dela.
    """
    if not uniq:
        return uniq
    partes = uniq.split(":")
    if len(partes) != 6:
        return uniq
    return ":".join([*partes[:3], "00", "00", partes[5]])


def _uniq_do_no(caminho: str | None) -> str | None:
    """O `uniq` do nó evdev que o SDL abriu — a propriedade de POSSE.

    Casar nó com controle pelo NOME é cura errada, e é regra dela: nesta
    bancada os DOIS vpads chegam com o mesmo rótulo, "(Hefesto P1)", e o nome
    não separa um do outro. O `uniq` separa, e é ele que junta o que o SDL viu
    com o nó de movimento da MESMA peça.
    """
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
    # O QUE O SDL RESPONDE ANTES DE QUALQUER AMOSTRA, e é a pergunta que o jogo
    # faz primeiro. Sem isto, "0 amostras" tem duas causas indistinguíveis:
    # o sensor está calado, ou a biblioteca diz ao jogo que ele NÃO EXISTE.
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
                "_uniq_inteiro": uniq,  # só para juntar aqui dentro; não sai no JSON
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
    """O nó "Motion Sensors" de cada peça: dá para abrir? chega evento?

    Ele é o CONTROLE do número do SDL. A contagem de eventos sozinha não serve:
    um nó pode despejar milhares de eventos repetindo o mesmo valor. Por isso
    saem daqui **amostras DISTINTAS** de giro e de acelerômetro — se elas são
    muitas e a biblioteca viu zero, "o controle estava parado" morre como
    explicação, e o que sobra é a biblioteca.

    Com ``sondar_grab`` o ensaio tenta um ``EVIOCGRAB`` e o solta na hora, para
    dizer se alguém já segura o nó (o braço evdev do interruptor, ou um rival).
    O ``--so-medir`` não sonda: um grab, por breve que seja, tira eventos de
    quem estiver lendo.
    """
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
                exclusivo = True  # alguém já graba: é o nosso braço, ou um rival
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
    """O nó "Motion Sensors" da MESMA peça que o SDL abriu — casado por `uniq`.

    Por `uniq` e não pelo nome: nesta bancada os dois vpads chegam rotulados
    "(Hefesto P1)", e casar por rótulo poria o dado de uma peça ao lado do
    veredito da outra.
    """
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
    """As frases do fim — uma por controle POR BIBLIOTECA, e cada uma diz quem respondeu.

    A PRIMEIRA PERGUNTA NÃO É QUANTAS AMOSTRAS CHEGARAM: com a biblioteca
    respondendo que o controle **não tem** giroscópio, zero amostras é
    conclusivo — sobre ESTA biblioteca. Até 13/09/2026 a frase atribuía o NÃO
    ao caminho até o jogo, e quem a leu concluiu sobre o vpad o que era da
    libSDL2 2.30.0 do sistema.
    """
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
    """O relatório sem as chaves de junção — o que SAI não leva endereço real.

    As chaves `_uniq_inteiro` existem para casar nó com controle aqui dentro,
    em qualquer profundidade do relatório. Elas nunca saem: a saída deste ensaio
    é feita para ser colada em documento, e documento é arquivo versionado.
    """
    if isinstance(valor, dict):
        return {k: _sem_o_endereco(v) for k, v in valor.items() if not k.startswith("_")}
    if isinstance(valor, list):
        return [_sem_o_endereco(v) for v in valor]
    return valor


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
    ap.add_argument("--processo", choices=("enumerar", "controles"), help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.processo:
        return _processo_de_uma_biblioteca(args)

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
    time.sleep(1.5)  # o hub reconcilia a 1 Hz; medir antes disso é medir frio
    relatorio["depois"] = [
        medir_uma_biblioteca(c, piso, enumerar=False, **opcoes) for c in caminhos
    ]
    relatorio["depois_no_de_movimento"] = olhar_o_no_de_movimento(1.0)

    # SEMPRE RELIGA. A bancada é dela, e um ensaio que sai deixando o
    # giroscópio desligado é um defeito que alguém vai caçar amanhã no jogo.
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
