#!/usr/bin/env python3
"""O JOGO para de ver o giro — medido pelo SDL, não pela interface.

SENSOR-DE-VERDADE-01 / ONDA1-D3. Decisão dela, 04/09/2026:

    *"ele tem que funcionar de verdade. ambos independente do modo e da
    mascara."* <!-- noqa-acento: citação literal dela -->

**A DIFERENÇA QUE ESTE ENSAIO EXISTE PARA NÃO CONFUNDIR** é a mesma que
derrubou quatro réguas em 04/09: *"a interface parou de mostrar"* e *"o jogo
parou de receber"* são coisas diferentes, e só a segunda é a entrega. Por isso
o instrumento aqui **não** é o `state_full` do daemon: é uma sonda **SDL2
headless** (a mesma biblioteca que o jogo usa), que abre o controle como um
jogo abre e conta amostras de sensor.

Sem janela: `SDL_INIT_GAMECONTROLLER` não inicia vídeo, e o `SDL_VIDEODRIVER`
sai como `dummy` de qualquer forma. **Nada nasce na tela dela.**

O QUE ELE MEDE, e em que ordem
-------------------------------
1. por onde o SDL abriu cada controle (`hidraw` = HIDAPI; `event` = evdev), e,
   ao lado, o que o ``SDL_hid_enumerate`` público devolve — **informação solta,
   não a causa** de ele ter caído no evdev (ver o parágrafo da causa, abaixo);
2. se o SDL **expõe** giroscópio e acelerômetro naquele controle
   (`SDL_GameControllerHasSensor`), antes de contar amostra nenhuma;
3. quantas amostras DISTINTAS de giroscópio e de acelerômetro chegaram;
4. o mesmo, depois de `sensor.set` desligar o sensor pelo daemon;
5. e o nó evdev "Motion Sensors" do físico, em paralelo — porque o SDL **não**
   o lê, e quem o lê (`evtest`, emulador com backend evdev) é justamente quem
   o braço do `EVIOCGRAB` alcança. Dele saem **amostras distintas**, não só a
   contagem de eventos: é o controle que diz se havia dado a receber.

Uso (a bancada é dela — reserve antes):

    scripts/bancada.sh reservar "ensaio do sensor"
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --segundos 3
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --so-medir   # não mexe em nada

O QUE A BANCADA DE 10/09/2026 MEDIU, e é o que este cabeçalho existe para não
deixar remedir
------------------------------------------------------------------------------
Dois DualSense na mesa — P1 no cabo, P2 no rádio —, SDL 2.30.0. O MESMO
instrumento, o MESMO aparelho, com minutos de diferença, nos dois modos:

=========================  =========================  =========================
o que o jogo pergunta      **Virtual** (máscara DS)   **Nativo**
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

Em Virtual o zero valeu para os QUATRO nós: os dois vpads (cabo e rádio) e os
dois físicos. E, na MESMA janela, o nó "Motion Sensors" de cada peça entregava
milhares de eventos com dezenas de valores DISTINTOS de giro, e o `hidraw` do
vpad do cabo entregava **250 relatórios/s com 222 valores distintos de giro em
5 s**.

Ou seja: **o dado está lá; o caminho até o jogo é que não existe.** E o defeito
é pior que decimação — o SDL não recebe zero amostra, ele responde ao jogo que
aquele controle **não tem giroscópio**. Um jogo que pergunta antes de usar nem
chega a ler.

**A CAUSA DENTRO DO SDL NÃO ESTÁ MEDIDA, e esta linha existe para ninguém a
inventar.** A tentação é dizer "o hidapi do SDL não enumera o vpad", porque
``SDL_hid_enumerate`` devolve **um** dispositivo dos oito `hidraw` da máquina e
nenhum dos dois vpads. **Isso não sustenta a conclusão:** em Nativo essa mesma
chamada continuou devolvendo só aquele um — enquanto o SDL tinha
``/dev/hidraw5`` ABERTO por HIDAPI. O ``SDL_hid_enumerate`` público não é a
enumeração que o subsistema de joystick usa, e por isso ele entra no relatório
como informação solta, não como causa.

O que está medido é o COMPORTAMENTO: com o `hidraw` do físico escondido em
`0600`, o SDL cai no evdev — e no evdev o sensor viaja num nó SEPARADO
("Motion Sensors") que o SDL pula. Por que ele não pega o `hidraw` do VPAD, que
está `0660` e abre sem esforço, é a primeira pergunta de quem for curar isto.

O QUE ELE **NÃO** PROVA, e está escrito para ninguém concluir demais
---------------------------------------------------------------------
Um controle imóvel entrega o mesmo valor por vários quadros: "zero amostras
distintas" com o aparelho parado não é prova de nada. **Mexa no controle
durante a medição** — o ensaio avisa quando o basal veio pobre demais para
sustentar conclusão, e o nó de movimento ao lado diz se havia dado a receber.

E ele não prova NADA sobre `O JOGO REAGIU`: um jogo de verdade, mirando, é o
degrau seguinte, e esse só fecha com o olho dela.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import ctypes
import json
import os
import pathlib
import sys
import time
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_SENSOR_ACCEL = 1
SDL_SENSOR_GYRO = 2

#: Abaixo disto o basal não sustenta conclusão nenhuma — o aparelho estava
#: parado, e "parou de chegar" seria indistinguível de "nunca chegou".
BASAL_MINIMO = 5

#: Os três eixos do GIROSCÓPIO no nó evdev "… Motion Sensors", já decodificados
#: pelo kernel. São os mesmos que o `MotionSensorReader` do produto lê.
EIXOS_DO_GIRO = ("ABS_RX", "ABS_RY", "ABS_RZ")

#: Os três do ACELERÔMETRO, no mesmo nó.
EIXOS_DO_ACELEROMETRO = ("ABS_X", "ABS_Y", "ABS_Z")


class _InfoHid(ctypes.Structure):
    """`SDL_hid_device_info` — só os campos até `next`, na ordem do cabeçalho."""


_InfoHid._fields_ = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_ushort),
    ("product_id", ctypes.c_ushort),
    ("serial_number", ctypes.c_wchar_p),
    ("release_number", ctypes.c_ushort),
    ("manufacturer_string", ctypes.c_wchar_p),
    ("product_string", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_ushort),
    ("usage", ctypes.c_ushort),
    ("interface_number", ctypes.c_int),
    ("next", ctypes.POINTER(_InfoHid)),
]


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


def o_hidapi_publico_do_sdl_ve(sdl: Any) -> list[dict[str, Any]]:
    """O que ``SDL_hid_enumerate`` devolve — informação solta, **não** a causa.

    **E o nome desta função é longo de propósito.** Ela nasceu em 10/09/2026
    como "a causa de `por_hidapi: false`": se o vpad não aparece aqui, o SDL não
    teria como abri-lo por HIDAPI. O controle em Modo Nativo derrubou a ideia na
    mesma bancada — esta chamada continuou devolvendo UM dispositivo enquanto o
    SDL tinha `/dev/hidraw5` aberto por HIDAPI. **O `SDL_hid_enumerate` público
    não é a enumeração que o subsistema de joystick usa.**

    Fica no relatório porque é barato e diz algo real sobre a máquina; não fica
    como explicação de nada. Quem a ler como causa repete o erro que este
    parágrafo custou.
    """
    try:
        sdl.SDL_hid_init()
        cabeca = sdl.SDL_hid_enumerate(0, 0)
    except (AttributeError, OSError):  # SDL < 2.0.18 não tem o hidapi exposto
        return []
    fora: list[dict[str, Any]] = []
    cur = cabeca
    while cur:
        d = cur.contents
        fora.append(
            {
                "no": d.path.decode(errors="replace") if d.path else None,
                "vid_pid": f"{d.vendor_id:04x}:{d.product_id:04x}",
                "produto": d.product_string,
            }
        )
        cur = d.next
    with contextlib.suppress(Exception):
        sdl.SDL_hid_free_enumeration(cabeca)
    return fora


def _carregar_sdl() -> Any:
    """A libSDL2 do sistema — a MESMA que o jogo carrega."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    sdl = ctypes.CDLL("libSDL2-2.0.so.0")
    sdl.SDL_GetError.restype = ctypes.c_char_p
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    sdl.SDL_GameControllerOpen.argtypes = [ctypes.c_int]
    sdl.SDL_GameControllerName.restype = ctypes.c_char_p
    sdl.SDL_GameControllerName.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerGetJoystick.restype = ctypes.c_void_p
    sdl.SDL_GameControllerGetJoystick.argtypes = [ctypes.c_void_p]
    sdl.SDL_JoystickPath.restype = ctypes.c_char_p
    sdl.SDL_JoystickPath.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerHasSensor.restype = ctypes.c_int
    sdl.SDL_GameControllerHasSensor.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerSetSensorEnabled.restype = ctypes.c_int
    sdl.SDL_GameControllerSetSensorEnabled.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    sdl.SDL_GameControllerGetSensorData.restype = ctypes.c_int
    sdl.SDL_GameControllerGetSensorData.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_int,
    ]
    sdl.SDL_GameControllerIsSensorEnabled.restype = ctypes.c_int
    sdl.SDL_GameControllerIsSensorEnabled.argtypes = [ctypes.c_void_p, ctypes.c_int]
    with contextlib.suppress(AttributeError):
        sdl.SDL_hid_init.restype = ctypes.c_int
        sdl.SDL_hid_enumerate.restype = ctypes.POINTER(_InfoHid)
        sdl.SDL_hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
        sdl.SDL_hid_free_enumeration.argtypes = [ctypes.POINTER(_InfoHid)]
    if sdl.SDL_Init(SDL_INIT_GAMECONTROLLER) != 0:
        raise SystemExit(f"SDL não subiu: {sdl.SDL_GetError().decode()}")
    return sdl


def olhar_com_o_sdl(sdl: Any, segundos: float) -> list[dict[str, Any]]:
    """O que um jogo veria agora: caminho aberto e amostras de sensor."""
    sdl.SDL_PumpEvents()
    time.sleep(0.4)
    sdl.SDL_PumpEvents()
    buf = (ctypes.c_float * 3)()
    fora: list[dict[str, Any]] = []
    abertos = []
    for i in range(sdl.SDL_NumJoysticks()):
        if not sdl.SDL_IsGameController(i):
            continue
        gc = sdl.SDL_GameControllerOpen(i)
        if gc:
            abertos.append(gc)
    # O QUE O SDL RESPONDE ANTES DE QUALQUER AMOSTRA, e é a pergunta que o jogo
    # faz primeiro. Sem isto, "0 amostras" tem duas causas indistinguíveis:
    # o sensor está calado, ou o SDL diz ao jogo que ele NÃO EXISTE. Medido em
    # 10/09/2026: em Virtual as duas respostas são `False`, e um jogo que
    # pergunta antes de usar nem chega a ler.
    expoe: dict[Any, dict[str, Any]] = {}
    for gc in abertos:
        expoe[gc] = {}
        for tipo, chave in ((SDL_SENSOR_GYRO, "giro"), (SDL_SENSOR_ACCEL, "accel")):
            tem = bool(sdl.SDL_GameControllerHasSensor(gc, tipo))
            expoe[gc][f"o_sdl_expoe_{chave}"] = tem
            expoe[gc][f"ligou_{chave}"] = (
                sdl.SDL_GameControllerSetSensorEnabled(gc, tipo, 1) == 0 if tem else None
            )
    vistos: dict[Any, dict[str, set[Any]]] = {
        gc: {"giro": set(), "accel": set()} for gc in abertos
    }
    fim = time.time() + segundos
    while time.time() < fim:
        sdl.SDL_PumpEvents()
        for gc in abertos:
            for tipo, chave in ((SDL_SENSOR_GYRO, "giro"), (SDL_SENSOR_ACCEL, "accel")):
                if sdl.SDL_GameControllerGetSensorData(gc, tipo, buf, 3) == 0:
                    vistos[gc][chave].add(
                        (round(buf[0], 4), round(buf[1], 4), round(buf[2], 4))
                    )
        time.sleep(0.005)
    for gc in abertos:
        caminho = sdl.SDL_JoystickPath(sdl.SDL_GameControllerGetJoystick(gc))
        aberto = caminho.decode() if caminho else None
        uniq = _uniq_do_no(aberto)
        fora.append(
            {
                "nome": sdl.SDL_GameControllerName(gc).decode(errors="replace"),
                "o_sdl_abriu": aberto,
                "por_hidapi": bool(caminho and b"hidraw" in caminho),
                "uniq": _mascara(uniq),
                "_uniq_inteiro": uniq,  # só para juntar aqui dentro; não sai no JSON
                **expoe[gc],
                "giro_distintos": len(vistos[gc]["giro"]),
                "accel_distintos": len(vistos[gc]["accel"]),
            }
        )
    return fora


def olhar_o_no_de_movimento(segundos: float) -> list[dict[str, Any]]:
    """O nó "Motion Sensors" de cada peça: dá para abrir? chega evento?

    O SDL **não** lê este nó — medido em 04/09/2026 —, mas `evtest` e vários
    emuladores leem. É o consumidor que o `EVIOCGRAB` alcança, e por isso ele
    é medido aqui ao lado do outro.

    **E ele é o CONTROLE do outro número.** A contagem de eventos sozinha não
    serve: um nó pode despejar milhares de eventos repetindo o mesmo valor.
    Por isso saem daqui **amostras DISTINTAS** de giro e de acelerômetro — se
    elas são muitas e o SDL viu zero, "o controle estava parado" morre como
    explicação, e o que sobra é que o caminho até o jogo não existe.
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


def _veredito(
    antes: list[dict[str, Any]],
    depois: list[dict[str, Any]] | None,
    nos: list[dict[str, Any]] | None = None,
) -> list[str]:
    """As frases do fim — uma por controle, e cada uma diz o CAMINHO.

    A PRIMEIRA PERGUNTA NÃO É QUANTAS AMOSTRAS CHEGARAM, e foi por não a fazer
    que este ensaio deu a resposta errada até 10/09/2026: com o SDL respondendo
    ao jogo que o controle **não tem** giroscópio, ele dizia "INCONCLUSIVO —
    mexa no controle", mandando quem estava medindo sacudir um aparelho que
    nunca teve por onde entregar. Zero com o sensor NÃO EXPOSTO é conclusivo,
    e é ruim.
    """
    por_nome = {c["nome"]: c for c in depois} if depois is not None else {}
    nos = nos or []
    linhas: list[str] = []
    for c in antes:
        via = "hidraw (HIDAPI)" if c["por_hidapi"] else "evdev"

        # 1. O SDL EXPÕE O SENSOR? Antes de contar amostra. Um jogo pergunta
        #    isto primeiro, e com `False` ele nem chega a ler.
        if c.get("o_sdl_expoe_giro") is False:
            no = _o_no_da_mesma_peca(c, nos)
            tinha = (
                f" — e o nó de movimento desta MESMA peça entregou "
                f"{no['giro_distintos']} amostras distintas de giro na mesma "
                "janela: o dado existe, o caminho até o jogo é que não"
                if no and no.get("giro_distintos")
                else ""
            )
            linhas.append(
                f"{c['nome']}: O SDL NÃO EXPÕE GIROSCÓPIO neste controle "
                f"(aberto por {via}; HasSensor=False){tinha}. Não há amostra a "
                "decimar nem a desligar: o jogo pergunta e ouve NÃO."
            )
            continue

        if depois is None:
            linhas.append(
                f"{c['nome']}: o SDL expõe giroscópio e recebeu "
                f"{c['giro_distintos']} amostras distintas por {via}."
            )
            continue

        d = por_nome.get(c["nome"])
        if d is None:
            linhas.append(f"{c['nome']}: sumiu do SDL entre as duas medições")
            continue
        if c["giro_distintos"] < BASAL_MINIMO:
            linhas.append(
                f"{c['nome']}: INCONCLUSIVO — o basal trouxe só "
                f"{c['giro_distintos']} amostras de giro por {via}. Mexa no "
                "controle durante a medição; parado, 'parou de chegar' é "
                "indistinguível de 'nunca chegou'."
            )
        elif d["giro_distintos"] == 0:
            linhas.append(
                f"{c['nome']}: O JOGO PAROU DE VER O GIRO "
                f"({c['giro_distintos']} → 0 amostras, por {via})."
            )
        else:
            linhas.append(
                f"{c['nome']}: O GIRO CONTINUA CHEGANDO "
                f"({c['giro_distintos']} → {d['giro_distintos']}, por {via}). "
                "Se o caminho é hidraw do FÍSICO, é o limite medido do Modo "
                "Nativo — o daemon não escreve nesse report."
            )
    return linhas


def _sem_o_endereco(relatorio: dict[str, Any]) -> dict[str, Any]:
    """O relatório sem as chaves de junção — o que SAI não leva endereço real.

    As chaves `_uniq_inteiro` existem para casar nó com controle aqui dentro.
    Elas nunca saem: a saída deste ensaio é feita para ser colada em documento,
    e documento é arquivo versionado.
    """
    limpo: dict[str, Any] = {}
    for chave, valor in relatorio.items():
        if isinstance(valor, list):
            limpo[chave] = [
                {k: v for k, v in item.items() if not k.startswith("_")}
                if isinstance(item, dict)
                else item
                for item in valor
            ]
        else:
            limpo[chave] = valor
    return limpo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=float, default=3.0, help="janela de medição")
    ap.add_argument("--uniq", default=None, help="a peça (padrão: a primeira achada)")
    ap.add_argument(
        "--so-medir",
        action="store_true",
        help="só mede o estado de agora; não chama sensor.set",
    )
    ap.add_argument(
        "--acelerometro",
        action="store_true",
        help="desliga o acelerômetro em vez do giroscópio",
    )
    args = ap.parse_args()

    sdl = _carregar_sdl()
    relatorio: dict[str, Any] = {"segundos": args.segundos}

    # Informação solta, e o nome da chave diz isso: NÃO é a enumeração que o
    # subsistema de joystick do SDL usa. Ver a docstring da função.
    relatorio["o_hidapi_publico_do_sdl_ve"] = o_hidapi_publico_do_sdl_ve(sdl)
    relatorio["antes_sdl"] = olhar_com_o_sdl(sdl, args.segundos)
    relatorio["antes_no_de_movimento"] = olhar_o_no_de_movimento(1.0)

    if args.so_medir:
        relatorio["veredito"] = _veredito(
            relatorio["antes_sdl"], None, relatorio["antes_no_de_movimento"]
        )
        print(json.dumps(_sem_o_endereco(relatorio), ensure_ascii=False, indent=2))
        return 0

    uniq = args.uniq or _uniq_do_primeiro_fisico()
    if not uniq:
        print("nenhum DualSense com nó de movimento na mesa — nada a medir")
        return 1
    sensor = "acelerometro" if args.acelerometro else "giroscopio"
    relatorio["peca"] = uniq
    relatorio["sensor"] = sensor

    relatorio["resposta_do_desligar"] = asyncio.run(
        _chamar("sensor.set", {"uniq": uniq, sensor: False})
    )
    time.sleep(1.5)  # o hub reconcilia a 1 Hz; medir antes disso é medir frio
    relatorio["depois_sdl"] = olhar_com_o_sdl(sdl, args.segundos)
    relatorio["depois_no_de_movimento"] = olhar_o_no_de_movimento(1.0)

    # SEMPRE RELIGA. A bancada é dela, e um ensaio que sai deixando o
    # giroscópio desligado é um defeito que alguém vai caçar amanhã no jogo.
    with contextlib.suppress(Exception):
        relatorio["resposta_do_religar"] = asyncio.run(
            _chamar("sensor.set", {"uniq": uniq, sensor: True})
        )

    relatorio["veredito"] = _veredito(
        relatorio["antes_sdl"],
        relatorio["depois_sdl"],
        relatorio["antes_no_de_movimento"],
    )
    print(json.dumps(_sem_o_endereco(relatorio), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
