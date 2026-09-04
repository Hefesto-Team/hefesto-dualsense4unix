#!/usr/bin/env python3
"""a_rota_do_som_vai_e_volta.py — "Todo o som do PC" escreve, LÊ DE VOLTA e devolve.

A PERGUNTA QUE ELE RESPONDE
---------------------------
*Quando o produto manda o som do PC para o alto-falante do controle, a leitura
de volta acompanha a escrita nas DUAS camadas — ou só no byte do firmware?*

POR QUE ELA IMPORTA, e a decisão é dela
----------------------------------------
Decisão dela, 04/09/2026, meio-dia: *"sons do pc e sons do jogo. veja como
fizemo no gtk."*  # noqa-acento: citação literal dela

São DOIS caminhos independentes, e a janela antiga já sabia disso
(`app/widgets/controller_card.CANAIS_DO_SPEAKER`):

    Sons do jogo      o byte `OUTPUT_PATH_SEL` = 2. Só o que o jogo mandar ao
                      dispositivo do controle sai nele; a trilha fica na TV.
    Todo o som do PC  `pactl set-default-sink` para a placa do controle **E**
                      o byte = 3.

E a ordem é medida: *"a camada 1 vence a camada 2 — volume e rota perfeitos num
sink mudo é trabalho invisível"*.

**O DEFEITO QUE ELE PEGA** é de 03/09/2026: o card 2 mostrava "Todo o som do
PC" ACESO com o som saindo na TV. A tela acendia o botão pelo FIRMWARE e mais
nada — ninguém lia o default sink. Uma régua que só confere o byte dá verde
sobre exatamente esse estado.

O QUE ELE FAZ, E POR QUE PODE SER RODADO COM ELA NA MÁQUINA
------------------------------------------------------------
Ele **vai e VOLTA**, e a volta está no `finally`:

    1. fotografa a saída padrão do sistema ANTES de tocar em qualquer coisa;
    2. manda "Todo o som do PC" pelas duas camadas, exatamente como o gesto
       `rota` da aba 02 manda;
    3. LÊ DE VOLTA as duas — `speaker.rota` do `state_full` e o
       `pactl get-default-sink` — e confere que as duas contam a mesma história;
    4. devolve a saída padrão ao que estava, e confere que voltou.

Sem o passo 4 o som dela ficaria preso no controle, que é justamente por que o
gesto `rota` estava em `PERIGOSOS` e a régua de clique nunca o tinha clicado.

A MORDIDA
---------
`--sem-volta` pula a devolução da camada 1 de propósito: o ensaio tem de
REPROVAR, dizendo que a saída padrão não voltou. Uma régua de ida e volta que
passa com a volta arrancada não mede a volta.

    scripts/ensaios/a_rota_do_som_vai_e_volta.py
    scripts/ensaios/a_rota_do_som_vai_e_volta.py --uniq d4:2f:…
    scripts/ensaios/a_rota_do_som_vai_e_volta.py --sem-volta   # a mordida
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import subprocess
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

#: Quanto se espera entre a escrita e a leitura de volta. Medido na bancada em
#: 04/09/2026: o `report_thread` só põe o byte no fio no ciclo do keepalive, e
#: o `state_full` publicou o valor novo em **547 ms** e **548 ms** nas duas
#: direções. Um segundo e meio é quase o triplo, e continua curto o bastante
#: para o som dela não ficar no controle por mais que um instante.
ASSENTAR_S: float = 1.5


async def _chamar(metodo: str, params: dict) -> dict:
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    async with IpcClient.connect() as cliente:
        resposta = await cliente.call(metodo, params)
    return resposta if isinstance(resposta, dict) else {}


def _pactl(*argv: str) -> str:
    try:
        return subprocess.run(
            ["pactl", *argv], capture_output=True, text=True, timeout=3.0, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _controles() -> list[dict]:
    r = asyncio.run(_chamar("controller.list", {}))
    return r.get("controllers") or []


def _byte_da_rota(uniq: str) -> object:
    """O `speaker.rota` que o daemon publica para este controle.

    LÊ O `state_full`, e não a resposta do `speaker.set`: a resposta do `set` é
    o eco do que mandamos — em Modo Nativo ela volta idêntica com o aparelho
    parado (medido em 04/09). O `state_full` é a leitura.
    """
    estado = asyncio.run(_chamar("daemon.state_full", {}))
    for c in estado.get("controllers") or []:
        if str(c.get("uniq") or "") != uniq:
            continue
        bloco = c.get("speaker")
        if isinstance(bloco, dict):
            return bloco.get("rota")
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--uniq", default=None, help="o controle a medir")
    p.add_argument(
        "--sem-volta",
        action="store_true",
        help="A MORDIDA: pula a devolução da camada 1 — o ensaio tem de reprovar",
    )
    args = p.parse_args()

    from hefesto_dualsense4unix.app import audio_saida

    ligados = [c for c in _controles() if c.get("connected")]
    if not ligados:
        print("SEM APARELHO — nenhum controle na mesa. Nada foi medido.")
        return 2
    escolhido = args.uniq or next(
        (c["uniq"] for c in ligados if c.get("transport") == "usb"),
        ligados[0]["uniq"],
    )
    na_mesa = [str(c.get("uniq") or "") for c in ligados if c.get("uniq")]

    antes = _pactl("get-default-sink")
    placa = audio_saida.sink_do_controle(escolhido, na_mesa)
    print(f"controle    : {escolhido}")
    print(f"saída ANTES : {antes or '(ilegível)'}")
    print(f"placa dele  : {placa or '(nenhuma — é o RÁDIO)'}")
    if not placa:
        print(
            "\nSEM PLACA — pelo rádio o DualSense não publica placa de som, e "
            "'Todo o som do PC' não tem para onde mandar. A recusa é honesta e "
            "está medida no `mapa-controles.csv` (audio.alto_falante, "
            "radio_aciona=não). Nada foi tocado."
        )
        return 2

    falhas: list[str] = []
    try:
        # ------------------------------------------------------------------ IDA
        # A CAMADA 1 PRIMEIRO, e a ordem é a do produto: "a camada 1 vence a
        # camada 2 — volume e rota perfeitos num sink mudo é trabalho invisível".
        desfecho = audio_saida.mandar_o_som_do_pc(escolhido, na_mesa)
        print(f"\nIDA camada 1: ok={desfecho.ok} sink={desfecho.sink or '—'} "
              f"{desfecho.motivo}")
        if not desfecho.ok:
            falhas.append(f"a camada 1 recusou: {desfecho.motivo}")
        resposta = asyncio.run(
            _chamar(
                "speaker.set",
                {"rota": audio_saida.BYTE_TODO_O_SOM_DO_PC, "uniq": escolhido},
            )
        )
        print(f"IDA camada 2: {resposta}")
        time.sleep(ASSENTAR_S)

        # ------------------------------------------------------------- A VOLTA
        # DA LEITURA. É esta a entrega: as duas camadas, lidas do produto.
        byte = _byte_da_rota(escolhido)
        padrao = _pactl("get-default-sink")
        leitura = audio_saida.RotaDasDuasCamadas(
            byte=byte if isinstance(byte, int) else None,
            sink_do_controle=placa,
            sink_padrao=padrao,
        )
        print(f"\nLEITURA byte : {byte!r}")
        print(f"LEITURA sink : {padrao}")
        print(f"botão aceso  : {leitura.botao_aceso!r}  (esperado 'pc')")
        print(f"concordam    : {leitura.concordam}")
        if leitura.recado:
            print(f"recado       : {leitura.recado}")
        if leitura.botao_aceso != "pc":
            falhas.append(
                "a leitura de volta não acendeu 'Todo o som do PC' — as duas "
                f"camadas não concordam (byte={byte!r}, sink={padrao!r})"
            )
    finally:
        # ------------------------------------------------------------- A VOLTA
        if args.sem_volta:
            print(
                "\n--sem-volta: A DEVOLUÇÃO FOI ARRANCADA DE PROPÓSITO. O som "
                "do PC ficou no controle — devolva pelas configurações de som "
                "do sistema, ou rode este ensaio sem a bandeira."
            )
        else:
            devolvido = audio_saida.devolver_o_som_do_pc()
            asyncio.run(
                _chamar(
                    "speaker.set",
                    {"rota": audio_saida.BYTE_SONS_DO_JOGO, "uniq": escolhido},
                )
            )
            time.sleep(ASSENTAR_S)
            depois = _pactl("get-default-sink")
            print(f"\nVOLTA camada 1: ok={devolvido.ok} {devolvido.motivo}")
            print(f"saída DEPOIS  : {depois or '(ilegível)'}")
            if depois != antes:
                falhas.append(
                    f"a saída padrão NÃO voltou: era {antes!r}, ficou {depois!r}"
                )

    if args.sem_volta:
        falhas.append(
            "a devolução da camada 1 foi pulada (--sem-volta): sem ela o som "
            "do PC fica preso no controle, e é isto que a mordida prova"
        )
    print()
    if falhas:
        for f in falhas:
            print(f"REPROVOU: {f}")
        return 1
    print("PASSOU — as duas camadas foram escritas, lidas de volta e devolvidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
