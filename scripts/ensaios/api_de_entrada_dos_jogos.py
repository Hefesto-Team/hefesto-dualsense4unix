#!/usr/bin/env python3
"""api_de_entrada_dos_jogos.py — que API de entrada cada jogo instalado fala.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Dá para saber, LENDO O DISCO e sem rodar o jogo, se um jogo entende a máscara
DualSense do Hefesto?*

A resposta medida em 16/08/2026, nos 24 jogos instalados dela, é **NÃO** — e
este instrumento existe para que qualquer pessoa reproduza essa resposta em
dez segundos, em vez de reabrir a discussão de memória.

O QUE ELE MOSTRA
-----------------
Uma linha por jogo, com os fatos e depois o veredito:

- **imports** — as DLLs de entrada na tabela de importação do PE;
- **agulhas** — as famílias achadas varrendo o binário inteiro (pega o que é
  carregado por `LoadLibrary` e não aparece em import nenhum);
- **din** — marca quando o XInput só existe por `LoadLibrary`;
- **veredito** — `entende_dualsense`, `indeciso` ou `sem_evidencia`.

O ACHADO QUE IMPORTA, E ONDE OLHAR NA SAÍDA
---------------------------------------------
Compare as linhas do **Duskfade** e do **DON'T SCREAM**. São idênticas em tudo
que o disco mostra. O primeiro não funciona com a máscara DualSense; o segundo
funciona. É por isso que o veredito máximo dessa família é `indeciso`, e é por
isso que o produto NÃO troca a máscara sozinho: a troca marcaria Sackboy,
Stray e DON'T SCREAM como Xbox e tiraria de cada um o giroscópio, o touchpad,
a lightbar, os gatilhos adaptativos e a bateria.

LEITURA PURA
-------------
Nada é escrito, nenhum jogo é iniciado, a Steam não é aberta e nenhum controle
é tocado. São `stat`, `mmap` e leitura de `appmanifest_*.acf`.

USO
----
    python3 scripts/ensaios/api_de_entrada_dos_jogos.py
    python3 scripts/ensaios/api_de_entrada_dos_jogos.py --pasta /caminho/comum
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations.api_de_entrada import (  # noqa: E402
    examinar_pasta,
)

#: Pastas de `steamapps/common` que são infraestrutura da Steam, não jogos.
#: São prefixos de NOME DE FERRAMENTA (Proton, os runtimes, os redistribuíveis),
#: e nenhum deles é um título — um jogo lançado amanhã não precisa entrar aqui.
INFRAESTRUTURA = (
    "Proton",
    "SteamLinuxRuntime",
    "Steamworks",
    "Steam Controller",
    "Steam.dll",
)


def pastas_comuns() -> list[Path]:
    """Os `steamapps/common` desta máquina, sem depender de nada instalado."""
    candidatas = [
        Path.home() / ".steam/debian-installation/steamapps/common",
        Path.home() / ".steam/steam/steamapps/common",
        Path.home() / ".local/share/Steam/steamapps/common",
    ]
    vistas: list[Path] = []
    for c in candidatas:
        try:
            if c.is_dir() and c.resolve() not in {v.resolve() for v in vistas}:
                vistas.append(c)
        except OSError:
            continue
    return vistas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pasta", type=Path, default=None, help="um steamapps/common")
    args = ap.parse_args()

    raizes = [args.pasta] if args.pasta else pastas_comuns()
    if not raizes:
        print("nenhum steamapps/common encontrado nesta máquina.")
        return 1

    print(
        f"{'jogo':32} | {'imports':24} | {'agulhas':30} | din | "
        f"{'veredito':18} | custo"
    )
    print("-" * 130)
    total = 0
    por_veredito: dict[str, int] = {}
    t_total = 0.0

    for raiz in raizes:
        try:
            jogos = sorted(p for p in raiz.iterdir() if p.is_dir())
        except OSError as erro:
            print(f"  (ilegível: {raiz} — {erro})")
            continue
        for jogo in jogos:
            if any(jogo.name.startswith(x) for x in INFRAESTRUTURA):
                continue
            t0 = time.monotonic()
            ev = examinar_pasta(jogo)
            dt = time.monotonic() - t0
            t_total += dt
            total += 1
            v = ev.veredito.value
            por_veredito[v] = por_veredito.get(v, 0) + 1
            imports = ",".join(
                sorted(
                    d
                    for d in ev.imports
                    if any(m in d for m in ("xinput", "dinput", "sdl"))
                )
            )
            agulhas = ",".join(sorted(f.value for f in ev.familias))
            din = "sim" if ev.carrega_xinput_dinamicamente else " - "
            print(
                f"{jogo.name[:32]:32} | {imports or '-':24} | {agulhas or '-':30} | "
                f"{din} | {v:18} | {dt:5.2f}s"
            )

    print("-" * 130)
    print(f"{total} jogos, {t_total:.1f}s no total")
    for v, n in sorted(por_veredito.items(), key=lambda kv: -kv[1]):
        print(f"  {v:20} {n}")
    indecisos = por_veredito.get("indeciso", 0)
    if indecisos:
        print(
            f"\nOs {indecisos} 'indeciso' são a razão de o produto não escolher a "
            "máscara sozinho:\nnesse balde convivem jogos que funcionam e jogos "
            "que não funcionam, com a MESMA assinatura."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
