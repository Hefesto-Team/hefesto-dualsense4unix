#!/usr/bin/env python3
"""nivel_do_led_do_mic.py — o LED do botão de mudo tem NÍVEL, ou é só 0 e 1?

A PERGUNTA QUE ELE RESPONDE
---------------------------
*O `common[8]` (`mute_button_led`, autorizado pelo bit 0x01 do flag1) obedece a
valores além de 0 e 1? Existe meio-brilho? Existe piscar?*

POR QUE ELA IMPORTA, e a pergunta é dela
-----------------------------------------
Em 02/09/2026 ela decidiu que a luz do microfone deve dizer DUAS coisas ao
mesmo tempo, com brilho diferente:

    aceso fraco  = o canal deste controle está vivo
    aceso forte  = este é o microfone padrão do sistema

A decisão nasce do modelo de QUATRO CANAIS, um por controle: vários podem estar
vivos ao mesmo tempo, mas o sistema tem UMA fonte padrão. Com um só nível de
luz, a mesa de quatro perde exatamente a informação que interessa — quem está
sendo ouvido.

**E A CAPACIDADE NUNCA FOI MEDIDA.** A referência canônica desta casa lista o
byte 8 na tabela do report de saída e deixa a coluna de valores em BRANCO
(`docs/protocol/dualsense-referencia-canonica.md:232`) — ninguém aqui jamais
escreveu nada além de 0 e 1. O driver escreve só `ds->mic_muted`, que é `bool`
(`assets/dkms/hid-playstation/hid-playstation.c:1540`). O campo é `u8`, então
CABE mais — mas caber não é obedecer, e afirmar sem medir é o defeito que esta
casa passou o dia inteiro derrubando.

O QUE ELE FAZ, e por que é seguro
----------------------------------
Manda `mic.led.set` ao daemon vivo com uma escada de valores, uma pausa entre
cada, e no fim DEVOLVE A POSSE. Só isso.

**O mudo do microfone mora em OUTRO byte** — o `common[9]`, com outro bit de
autorização — e este instrumento não o toca. Acender a luz não muta nada: é o
mesmo fato que sustenta a inversão que ela pediu, e as três recusas medidas
(BT-E-VPAD-01, MIC-BT-DONO-01, MIC-DOIS-DONOS-01) são todas sobre o byte 9.

A DEVOLUÇÃO É OBRIGATÓRIA e está no `finally`, inclusive para o Ctrl+C. Sem ela
o `common[8]` fica nosso e o botão físico dela para de mandar na luz até o
controle ser desligado — é a porta de emergência descrita em
`_handle_mic_led_set`.

POR QUE PELO DAEMON, E NÃO POR UM `open()` DO HIDRAW
-----------------------------------------------------
O daemon reafirma o report de saída continuamente. Uma escrita crua feita por
fora seria sobrescrita em milissegundos pelo report seguinte — a luz piscaria e
o instrumento imprimiria "aplicado" sem ter aplicado. É a armadilha nº 3 do
`CLAUDE.md`, e o caminho certo é o do produto: quem segura o valor entre um
report e o próximo é o `_mic_led_desejado`, dentro do daemon.

COMO SE LÊ O RESULTADO
----------------------
Quem lê é o olho dela: o registrador **não tem caminho de leitura** no
firmware. O instrumento imprime o que está MANDANDO e espera; ela diz o que a
luz fez. É por isso que a linha do mapa vai nascer `provado_por = olho-dela`, e
nunca `bancada`.

    scripts/ensaios/nivel_do_led_do_mic.py             # a escada padrão
    scripts/ensaios/nivel_do_led_do_mic.py --pausa 4   # mais tempo por degrau
    scripts/ensaios/nivel_do_led_do_mic.py --uniq AA:… # escolhe o controle
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

#: A ESCADA. Os quatro primeiros decidem a pergunta dela; o `255` é o teto do
#: `u8` e existe para separar "ignora o que não conhece" de "satura em aceso".
#:
#: O `2` está aqui por uma razão de fora desta casa: em vários aparelhos da
#: família o terceiro estado do LED de mudo é PISCAR. Se ele piscar, a decisão
#: dela ganha uma terceira palavra de graça.
ESCADA: tuple[tuple[int, str], ...] = (
    (0, "apagado — o piso, e a prova de que a escrita chega"),
    (1, "aceso — o único valor que o driver conhece"),
    (2, "o terceiro estado, se existir (em alguns aparelhos: PISCAR)"),
    (3, "logo acima — separa 'escada de brilho' de 'três estados'"),
    (64, "um quarto do teto — se houver NÍVEL, é aqui que ele aparece"),
    (255, "o teto do byte"),
)


def _controle_do_cabo(uniq_pedido: str | None) -> tuple[str | None, str]:
    """O `uniq` do DualSense a medir, e a frase que explica a escolha.

    O cabo é o preferido: a escrita por rádio ainda passa pelo CRC, e o alvo
    desta medição é a CAPACIDADE DO FIRMWARE, que não muda com o transporte.
    Medir no cabo responde a pergunta com um caminho a menos para dar errado.
    """
    if uniq_pedido:
        return uniq_pedido, "escolhido na linha de comando"

    # Quem responde é o DAEMON, e não o `comum`, por uma razão medida em
    # 02/09/2026: os dois falam vocabulários diferentes. O `comum` devolve o MAC
    # com dois-pontos e chama o transporte de `cabo`; o daemon devolve o `uniq`
    # SEM os dois-pontos e chama de `usb`. Pedir com o formato do `comum` não dá
    # erro — dá `sem_controle`, que se lê como "não há controle na mesa" quando
    # o que houve foi um endereço que não casa com handle nenhum.
    lista = asyncio.run(_listar())
    cabo = [x for x in lista if x.get("connected") and x.get("transport") == "usb"]
    if cabo:
        return cabo[0]["uniq"], "no CABO (o transporte com menos caminho para errar)"
    ligados = [x for x in lista if x.get("connected")]
    if ligados:
        return ligados[0]["uniq"], "por RÁDIO — não havia nenhum no cabo"
    return None, "nenhum DualSense conectado"


async def _listar() -> list[dict]:
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    async with IpcClient.connect() as cliente:
        r = await cliente.call("controller.list", {})
    return (r or {}).get("controllers") or []


async def _mandar(aceso: object, uniq: str | None) -> dict:
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    payload: dict[str, object] = {"aceso": aceso}
    if uniq:
        payload["uniq"] = uniq
    async with IpcClient.connect() as cliente:
        resposta = await cliente.call("mic.led.set", payload)
    return resposta if isinstance(resposta, dict) else {}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pausa", type=float, default=3.0,
                   help="segundos em cada degrau (padrão: 3)")
    p.add_argument("--uniq", default=None, help="endereço do controle a medir")
    p.add_argument("--valores", default="",
                   help="escada própria, separada por vírgula (ex.: 0,1,2)")
    args = p.parse_args()

    uniq, porque_este = _controle_do_cabo(args.uniq)
    if not uniq:
        print(f"{porque_este} — conecte um DualSense e repita.", file=sys.stderr)
        return 2

    if args.valores:
        escada = tuple((int(v.strip()), "") for v in args.valores.split(",") if v.strip())
    else:
        escada = ESCADA

    curto = uniq.replace(":", "").lower()[-4:]
    print(f"controle …{curto} — {porque_este}")
    print(f"{len(escada)} degraus, {args.pausa}s cada "
          f"(~{int(len(escada) * args.pausa)}s no total)")
    print()
    print("  OLHE A LUZ DO BOTÃO DO MICROFONE — o botãozinho abaixo do touchpad.")
    print("  Para CADA degrau, diga uma destas: apagada · acesa · piscando · fraca")
    print()

    devolveu = False
    try:
        for valor, porque in escada:
            try:
                r = asyncio.run(_mandar(valor, uniq))
            except Exception as exc:
                print(f"  common[8] = {valor:<3d}  FALHOU: {exc}")
                continue
            estado = r.get("status", "?")
            marca = "  " if estado == "ok" else " ! "
            print(f"{marca}common[8] = {valor:<3d}  {porque}"
                  f"{'' if estado == 'ok' else f'   [{estado}]'}", flush=True)
            # `time.sleep` e não `asyncio.sleep`: cada degrau é uma conexão IPC
            # própria e curta, de propósito — assim uma queda do daemon no meio
            # aparece como UM degrau falhando, e não como o ensaio inteiro morto.
            import time
            time.sleep(args.pausa)
    except KeyboardInterrupt:
        print("\n  interrompido.")
    finally:
        try:
            asyncio.run(_mandar(None, uniq))
            devolveu = True
        except Exception as exc:
            print(f"  a devolução falhou: {exc}", file=sys.stderr)

    print()
    if devolveu:
        print("posse devolvida ao kernel — o botão físico volta a mandar na luz.")
    else:
        print("ATENÇÃO: a posse NÃO foi devolvida. Rode:")
        print("  hefesto-dualsense4unix mic led-release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
