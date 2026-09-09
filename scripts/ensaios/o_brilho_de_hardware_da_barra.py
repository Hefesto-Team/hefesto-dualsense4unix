#!/usr/bin/env python3
"""o_brilho_de_hardware_da_barra.py — o byte que nem o kernel escreve, no olho dela.

A PERGUNTA QUE ELE DECIDE (BRILHO-DE-HARDWARE-01, decisão dela de 09/09/2026: *"2b"*)
------------------------------------------------------------------------------------
A barra do DualSense tem DOIS brilhos, e a casa os confundia até 08/09:

* **o da tela** — `brilho`, `lightbar_brightness`: a cor multiplicada em
  Python antes de sair. Um vermelho a 30 % é um vermelho escuro. Funciona
  pelo caminho da cor (medido 12/08 nos dois transportes);
* **o de HARDWARE** — `luz.lightbar.brilho@dualsense`: `common[42]`
  (`led_brightness`, três níveis: 0 alto · 1 médio · 2 baixo), autorizado por
  `flag2` bit0 em `common[38]`. O produto manda o byte sempre em 0 e **o
  kernel desta máquina nem define o bit**. `nao-medido` nos dois transportes.

Ela decidiu medir. Este instrumento escreve o byte, com e sem o bit, e ela
olha a barra.

O DESENHO
---------
Cor fixa (branco por omissão, com o bit da barra ligado para ela acender) e o
`common[42]` variando::

    nível 0   alto    (o que o produto manda hoje — a linha de base)
    nível 2   baixo   se o firmware obedece, ESCURECE aqui
    nível 1   médio   entre os dois
    nível 0   alto    de volta — tem de voltar ao brilho da base

E a mesma escada **sem o bit** (`--sem-bit`): se escurecer sem o bit, o
firmware ignora a autorização — e o kernel estava certo em não a definir.

O MARTELO
---------
Quando o daemon é dono das luzes, cada report dele leva `flag2` com o bit e
`common[42] = 0`: uma escrita minha pode ser desfeita antes de ela olhar. Por
isso cada nível **martela** a 10 Hz durante a janela (`--uma-vez` desliga).
Se a barra "piscar" entre dois brilhos, é o daemon e eu disputando — e isso é
um SIM do firmware, não um não. No rádio o bloco cai sob `suppress_leds` e o
daemon não manda o bit: lá a escrita única já é limpa.

Porta: o broker (`comum.abrir_no_hidraw`), com o daemon VIVO. Escreve no
aparelho? SIM — cor, `common[42]` e `flag2` bit0.

USO
    o_brilho_de_hardware_da_barra.py --listar
    o_brilho_de_hardware_da_barra.py --alvo <MAC>                 # 0, 2, 1, 0 com o bit
    o_brilho_de_hardware_da_barra.py --alvo <MAC> --sem-bit       # a mesma escada sem o bit
    o_brilho_de_hardware_da_barra.py --alvo <MAC> --nivel 2 --segundos 15
"""

from __future__ import annotations

import argparse
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import CABO, cabecalho_do_instrumento, resumo
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    common_vazio,
    escolher_alvo,
    linha_do_caderno,
    listar,
    mascarar,
    perguntar,
)
from hefesto_dualsense4unix.core.ds_output_report import (
    COMMON_VALID_FLAG2,
    VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE,
    VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE,
)

LINHA_DO_MAPA = "luz.lightbar.brilho@dualsense"
COMMON_LED_BRIGHTNESS = 42  #: `led_brightness` no common — o mapa e o kernel dizem 42
OFF_R, OFF_G, OFF_B = 44, 45, 46
NOME_DO_NIVEL = {0: "ALTO (a base)", 1: "MÉDIO", 2: "BAIXO"}
ESCADA_PADRAO = (0, 2, 1, 0)


def common_do_nivel(nivel: int, *, com_bit: bool, cor: tuple[int, int, int]) -> bytearray:
    """A cor pedida com o bit da barra, e SÓ o `common[42]` (e seu bit) variando."""
    if nivel not in (0, 1, 2):
        raise ValueError(f"nível de brilho fora de 0..2: {nivel}")
    c = common_vazio()
    c[1] |= VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    c[OFF_R], c[OFF_G], c[OFF_B] = (x & 0xFF for x in cor)
    c[COMMON_LED_BRIGHTNESS] = nivel
    if com_bit:
        c[COMMON_VALID_FLAG2] |= VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
    return c


def _cor(texto: str) -> tuple[int, int, int]:
    partes = [int(p, 0) for p in texto.split(",")]
    if len(partes) != 3:
        raise argparse.ArgumentTypeError("cor é r,g,b")
    return partes[0], partes[1], partes[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC (inteira ou mascarada) ou nome do hidraw")
    ap.add_argument("--nivel", type=int, action="append", choices=(0, 1, 2),
                    help="a escada (padrão: 0, 2, 1, 0)")
    ap.add_argument("--sem-bit", action="store_true", help="a mesma escada SEM o flag2 bit0")
    ap.add_argument("--cor", type=_cor, default=(255, 255, 255), help="r,g,b (padrão branco)")
    ap.add_argument("--segundos", type=float, default=8.0, help="a janela de cada nível")
    ap.add_argument("--uma-vez", action="store_true", help="escreve uma vez por nível, sem martelar")
    ap.add_argument("--hz", type=float, default=10.0, help="o ritmo do martelo")
    args = ap.parse_args()

    aparelhos = alvos_da_mesa()
    pergunta = "o common[42] escurece a barra, com e sem o bit que o kernel não define?"
    if args.listar or not args.alvo:
        print(cabecalho_do_instrumento(
            "o_brilho_de_hardware_da_barra", pergunta,
            bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
            escreve_no_aparelho=True))
        print("\ncontroles físicos na mesa:")
        print(listar(aparelhos))
        return 0

    alvo = escolher_alvo(aparelhos, args.alvo)
    if alvo is None:
        print(f"alvo {args.alvo!r} não está na mesa. Conhecidos: {[mascarar(a.mac) for a in aparelhos]}")
        return 1
    escada = tuple(args.nivel) if args.nivel else ESCADA_PADRAO
    com_bit = not args.sem_bit

    print(cabecalho_do_instrumento(
        "o_brilho_de_hardware_da_barra", pergunta,
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
        escreve_no_aparelho=True))
    print(f"\nalvo ....... {mascarar(alvo.mac)}  {alvo.transporte}  ({alvo.caminho_hidraw})")
    print(f"cor ........ {args.cor}   bit ....... {'LIGADO' if com_bit else 'APAGADO (o negativo)'}")
    print(f"martelo .... {'desligado' if args.uma_vez else f'{args.hz:g} Hz'}"
          f"{'  (no cabo o daemon reescreve 42=0 com o bit a cada report dele)' if alvo.transporte == CABO else ''}")

    escritor = Escritor(alvo)
    try:
        print(f"porta ...... {escritor.abrir()}")
    except Exception as erro:
        print(f"sem porta para {mascarar(alvo.mac)}: {erro}")
        return 1

    respostas: list[tuple[int, str]] = []
    print("\nO RETORNO DO os.write NÃO É A MEDIÇÃO — quem mede é o olho dela, na barra.\n")
    try:
        for nivel in escada:
            common = common_do_nivel(nivel, com_bit=com_bit, cor=args.cor)
            print(f"NÍVEL {nivel} — {NOME_DO_NIVEL[nivel]}")
            if nivel == 0:
                print("  ^ é a linha de base: o brilho de sempre. Se ela mudar aqui, PARE.")
            if args.uma_vez:
                escritor.escrever(common)
                time.sleep(args.segundos)
                feitas = 1
            else:
                feitas = escritor.martelar(common, args.segundos, hz=args.hz)
            print(f"  {feitas} escrita(s)")
            respostas.append((nivel, perguntar("  -> a barra escureceu, clareou ou ficou igual? (verbatim)  ")))
    finally:
        escritor.escrever(common_do_nivel(0, com_bit=True, cor=args.cor))
        escritor.fechar()
        print("\nnível 0 devolvido com o bit, porta fechada — o daemon reassume a cor na próxima escrita dele.")

    print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv — quem coordena escreve):")
    for nivel, resposta in respostas:
        print(linha_do_caderno(
            id=f"brilho-de-hardware-nivel{nivel}-{'com' if com_bit else 'sem'}-bit-{time.strftime('%d%m')}",
            linha_id=LINHA_DO_MAPA,
            transporte="cabo" if alvo.transporte == CABO else "radio",
            suspeito="o firmware obedece ao common[42] (3 níveis) — e exige o flag2 bit0 que o kernel não define",
            presente="sim" if com_bit else "não",
            resultado="",
            observado_por="olho-dela",
            fonte="scripts/ensaios/o_brilho_de_hardware_da_barra.py",
            nota=f"nível {nivel} ({NOME_DO_NIVEL[nivel]}), bit {'ligado' if com_bit else 'apagado'}, "
                 f"cor {args.cor}, martelo {'não' if args.uma_vez else f'{args.hz:g} Hz'}; ela: {resposta or '(sem resposta)'}",
        ))
    print(resumo("o resultado é o olho dela: `obedece` se o nível 2 escureceu e o 0 voltou; senão `não obedece`."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
