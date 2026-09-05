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
1. por onde o SDL abriu cada controle (`hidraw` = HIDAPI; `event` = evdev);
2. quantas amostras DISTINTAS de giroscópio e de acelerômetro chegaram;
3. o mesmo, depois de `sensor.set` desligar o sensor pelo daemon;
4. e o nó evdev "Motion Sensors" do físico, em paralelo — porque o SDL **não**
   o lê, e quem o lê (`evtest`, emulador com backend evdev) é justamente quem
   o braço do `EVIOCGRAB` alcança.

Uso (a bancada é dela — reserve antes):

    scripts/bancada.sh reservar "ensaio do sensor"
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --segundos 3
    scripts/ensaios/o_jogo_para_de_ver_o_giro.py --so-medir   # não mexe em nada

O QUE ELE **NÃO** PROVA, e está escrito para ninguém concluir demais
---------------------------------------------------------------------
Um controle imóvel entrega o mesmo valor por vários quadros: "zero amostras
distintas" com o aparelho parado não é prova de nada. **Mexa no controle
durante a medição** — o ensaio avisa quando o basal veio pobre demais para
sustentar conclusão.
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
    for gc in abertos:
        for tipo in (SDL_SENSOR_GYRO, SDL_SENSOR_ACCEL):
            if sdl.SDL_GameControllerHasSensor(gc, tipo):
                sdl.SDL_GameControllerSetSensorEnabled(gc, tipo, 1)
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
        fora.append(
            {
                "nome": sdl.SDL_GameControllerName(gc).decode(errors="replace"),
                "o_sdl_abriu": caminho.decode() if caminho else None,
                "por_hidapi": bool(caminho and b"hidraw" in caminho),
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
    """
    from evdev import InputDevice, list_devices

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
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                for _ in dev.read():
                    eventos += 1
            except BlockingIOError:
                time.sleep(0.01)
            except OSError:
                break
        dev.close()
        fora.append(
            {
                "no": caminho,
                "nome": nome,
                "uniq": uniq,
                "ja_esta_grabado_por_alguem": exclusivo,
                "eventos": eventos,
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


def _veredito(antes: list[dict[str, Any]], depois: list[dict[str, Any]]) -> list[str]:
    """As frases do fim — uma por controle, e cada uma diz o CAMINHO."""
    por_nome = {c["nome"]: c for c in depois}
    linhas: list[str] = []
    for c in antes:
        d = por_nome.get(c["nome"])
        if d is None:
            linhas.append(f"{c['nome']}: sumiu do SDL entre as duas medições")
            continue
        via = "hidraw (HIDAPI)" if c["por_hidapi"] else "evdev"
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

    relatorio["antes_sdl"] = olhar_com_o_sdl(sdl, args.segundos)
    relatorio["antes_no_de_movimento"] = olhar_o_no_de_movimento(1.0)

    if args.so_medir:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
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
        relatorio["antes_sdl"], relatorio["depois_sdl"]
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
