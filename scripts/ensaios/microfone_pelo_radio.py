#!/usr/bin/env python3
"""microfone_pelo_radio.py — a voz sai do DualSense pelo rádio, ou não sai?

A PERGUNTA QUE ELE RESPONDE
----------------------------
O mapa dizia, com todas as letras, o que faltava para esta célula sair de
`parcial`: *"ele só sai daí quando alguém escrever o `0x32` num DualSense de
verdade pelo rádio e OUVIR o áudio"* (`docs/data/mapa-controles.csv`,
`audio.microfone@dualsense`, `radio_evidencia`). Este instrumento faz
exatamente isso e devolve o número.

Ele sobe a ponte de Opus tunelado em HID num controle, abre um ouvinte no canal
que ela publica e mede **o que o aplicativo recebeu**: quantas amostras, quantos
por cento de zeros, pico, RMS e dBFS. É a ponta do outro lado — não o que a
ponte julga ter mandado.

O QUE ELE NUNCA FAZ
--------------------
**Não grava áudio em disco.** O PCM do ouvinte é lido em memória, vira
estatística e morre com o processo. É o microfone da casa dela.

**Não abre janela nenhuma** (TELA-DELA-02): é CLI, e o ouvinte é um `parec` sem
interface.

**Não reinicia o daemon.** Ele pede o hidraw pelo broker, como a ponte de
verdade faz, e recusa o controle cuja ponte o daemon já segura — dois donos do
contador de sequência do `0x32` foi o que travou um DualSense em 16/08/2026.

**Devolve o microfone desligado.** O `0x32` de DESLIGAR sai no `finally`, mesmo
se o ensaio explodir no meio.

AS DUAS FORMAS DE ZERO, E ELE SEPARA AS DUAS
----------------------------------------------
Um ensaio que só diz *"deu 100% de zeros"* manda a próxima pessoa remedir tudo.
Silêncio digital tem duas causas completamente diferentes, e as colunas
`escritas_ok` / `descartes` as separam sozinhas:

* **`escritas_ok` alto e `descartes` zero, e ainda assim zeros** — o quadro
  Opus chegou, decodificou e entrou no canal. O microfone está **calado no
  firmware** (o botão do plástico), e o silêncio é a resposta CERTA.
* **`escritas_ok` travado em 8 e `descartes` subindo** — o fifo encheu e ninguém
  o esvazia. É o módulo ÓRFÃO com o mesmo `source_name`: quem é dono do nome no
  grafo é o nó morto, e o app grava dele. Medido em 07/09/2026;
  `SourceVirtualPipeWire.iniciar` passou a derrubar o órfão antes de publicar.

USO
    microfone_pelo_radio.py --no /dev/hidraw8 --segundos 10
    microfone_pelo_radio.py --listar
"""

from __future__ import annotations

import argparse
import fcntl
import math
import os
import select
import struct
import subprocess
import sys
import time

#: Quanto o ouvinte espera antes de a medição começar. O `0x32` de LIGAR só sai
#: quando a source vira `RUNNING`, e o `_talvez_seguir_a_source` olha uma vez
#: por segundo — medir antes disso mediria a espera, não o microfone.
_ESPERA_DO_OUVINTE_S = 2.0

#: 10 ms a 48 kHz mono — o quadro que o firmware manda. Contar zeros por bloco
#: deste tamanho é o que separa "silêncio contínuo" de "sinal com buraco".
_BLOCO = 480


def _stats(pcm: bytes) -> dict[str, float | int]:
    n = len(pcm) // 2
    if not n:
        return {"amostras": 0}
    amostras = struct.unpack(f"<{n}h", pcm[: n * 2])
    zeros = sum(1 for a in amostras if a == 0)
    pico = max(abs(a) for a in amostras)
    rms = math.sqrt(sum(a * a for a in amostras) / n)
    blocos = [amostras[i : i + _BLOCO] for i in range(0, n - _BLOCO, _BLOCO)]
    mudos = sum(1 for b in blocos if not any(b))
    return {
        "amostras": n,
        "segundos": round(n / 48000, 2),
        "zeros_pct": round(100.0 * zeros / n, 2),
        "pico": pico,
        "rms": round(rms, 1),
        "dbfs": round(20 * math.log10(rms / 32768.0), 1) if rms > 0 else float("-inf"),
        "blocos_de_10ms": len(blocos),
        "blocos_mudos": mudos,
    }


def _pontes_do_daemon() -> frozenset[str]:
    """Os `uniq` cuja ponte o daemon vivo já segura. Vazio = não sei / nenhuma."""
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _chamar() -> dict[str, object]:
        try:
            async with IpcClient.connect() as cliente:
                resposta = await cliente.call("daemon.state_full")
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return {}
        return resposta if isinstance(resposta, dict) else {}

    estado = asyncio.run(_chamar())
    bloco = estado.get("bt_mic")
    if not isinstance(bloco, dict):
        return frozenset()
    uniqs = bloco.get("uniqs")
    return frozenset(str(u) for u in uniqs) if isinstance(uniqs, list) else frozenset()


def _medir(caminho: str, segundos: float) -> int:
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        PonteMicBluetooth,
        nos_dualsense_bluetooth,
    )

    achados = [no for no in nos_dualsense_bluetooth() if no.caminho == caminho]
    if not achados:
        print(f"{caminho} não é um DualSense em Bluetooth.", file=sys.stderr)
        return 1
    no = achados[0]
    chave = norm_mac(str(no.uniq)) or ""
    if chave in _pontes_do_daemon():
        print(
            f"não meço {no.uniq}: o daemon já segura a ponte dele.\n"
            "  Por quê: dois donos do contador de sequência do 0x32 travaram um "
            "DualSense em 16/08/2026.\n"
            "  O que fazer: desligue o microfone deste controle na tela e rode "
            "de novo, ou meça o outro.",
            file=sys.stderr,
        )
        return 1

    ponte = PonteMicBluetooth(no)
    if not ponte.iniciar():
        print("a ponte não subiu (libopus, hidraw ou pactl) — nada ficou de pé.")
        return 1
    source = ponte._source  # o ensaio mede a peça por dentro, de propósito
    contas = {"ok": 0, "descarte": 0}
    escrever_de_verdade = source.escrever

    def _espiao(pcm: bytes) -> bool:
        aceito = escrever_de_verdade(pcm)
        contas["ok" if aceito else "descarte"] += 1
        return aceito

    source.escrever = _espiao  # type: ignore[method-assign]
    ouvinte = None
    try:
        ouvinte = subprocess.Popen(
            [
                "parec", "--raw", f"--device={ponte.nome_source}",
                "--format=s16le", "--rate=48000", "--channels=1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert ouvinte.stdout is not None
        flags = fcntl.fcntl(ouvinte.stdout, fcntl.F_GETFL)
        fcntl.fcntl(ouvinte.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        time.sleep(_ESPERA_DO_OUVINTE_S)
        print(f"source ....... {ponte.nome_source}  estado {source.estado()}")
        colhido = bytearray()
        fim = time.time() + segundos
        while time.time() < fim:
            prontos, _, _ = select.select([ouvinte.stdout], [], [], 0.1)
            if prontos:
                pedaco = ouvinte.stdout.read(1 << 16)
                if pedaco:
                    colhido += pedaco
        estatistica = ponte.estatistica()
        print(f"quadros Opus . {estatistica.quadros_audio}")
        print(f"escritas ok .. {contas['ok']}   descartes {contas['descarte']}")
        print(f"mudo no firmware ... {estatistica.mudo}")
        for chave_stat, valor in _stats(bytes(colhido)).items():
            print(f"  {chave_stat} = {valor}")
    finally:
        if ouvinte is not None:
            ouvinte.terminate()
            with_timeout = 3
            try:
                ouvinte.wait(timeout=with_timeout)
            except subprocess.TimeoutExpired:
                ouvinte.kill()
        ponte.parar()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no", dest="caminho", help="o /dev/hidrawN do controle")
    parser.add_argument("--segundos", type=float, default=10.0)
    parser.add_argument(
        "--listar", action="store_true", help="só lista os DualSense em rádio"
    )
    args = parser.parse_args(argv)

    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        nos_dualsense_bluetooth,
    )

    if args.listar or not args.caminho:
        nos = nos_dualsense_bluetooth()
        if not nos:
            print("nenhum DualSense em rádio.")
            return 0
        for no in nos:
            print(f"{no.caminho}  {no.uniq}")
        return 0 if args.listar else 1
    return _medir(args.caminho, args.segundos)


if __name__ == "__main__":
    raise SystemExit(main())
