#!/usr/bin/env python3
"""o_tato_vivo_x_ou_y.py — o interruptor da bancada do tato vivo, um campo por vez.

O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01 (09/10/2026). O motor do tato
(`daemon/subsystems/tato_vivo.py`) lê a receita do estilo que o perfil guarda
(`Profile.estilo`) e, por cima dela, o desvio da bancada (`Profile.receita_do_tato`),
campo a campo. Este ensaio troca X por Y nesse desvio sem editar código: liga
ou desliga o toque por tiro, o lado do som, a luz e o gatilho no ritmo, um por
vez, para quem sente na mão não saber o esperado.

    --mostrar [--perfil NOME]                 uma linha por variável da receita em vigor
    --perfil NOME --campo C --valor V --medir  escreve o desvio C=V no perfil
    --perfil NOME --campo C --tirar --medir    tira C do desvio (volta ao estilo)

POR ONDE ESCREVE: pelo dono do perfil no disco, `profiles.loader.save_profile`
(o schema valida, a trava e o histórico guardam a versão de antes), nunca por
JSON à mão. Nenhum método do IPC grava perfil; o motor relê o perfil ativo a cada
`tato_vivo.RELEITURA_DA_RECEITA_S`, e o desvio vale no segundo seguinte, sem
reaplicar o perfil (reaplicar reescreveria gatilho e luz no aparelho).

O QUE ELE RECUSA: sem ``--medir`` não grava nada (rc=2, mostra o que faria);
campo que não é variável do motor; perfil que não existe. O ``--mostrar`` só lê.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_SRC = _AQUI.parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

RC_OK = 0
RC_RECUSA = 2
ORIGEM_DA_GRAVACAO = "ensaio:o_tato_vivo_x_ou_y"


def _valor(cru: str) -> Any:
    """`true`, `0.8`, `[255, 0, 0]` viram JSON; o resto (`pulsa`) fica texto."""
    try:
        return json.loads(cru)
    except ValueError:
        return cru


def _perfil_ativo() -> str | None:
    from hefesto_dualsense4unix.app import ipc_bridge

    estado = ipc_bridge.daemon_state_full() or {}
    nome = estado.get("active_profile")
    return nome if isinstance(nome, str) and nome else None


def linhas_da_receita(perfil: Any) -> list[str]:
    """Uma linha por variável da receita em vigor, com a origem do valor."""
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    receita = tv.receita_do_perfil(perfil)
    desvio = getattr(perfil, tv.CAMPO_DA_RECEITA, None) or {}
    estilo = getattr(perfil, "estilo", None)
    linhas = [f"perfil = {perfil.name}", f"estilo = {estilo or '—'}",
              f"ligada = {receita.ligada}"]
    for campo, valor in asdict(receita).items():
        origem = "desvio" if campo in desvio else ("estilo" if estilo else "padrão")
        linhas.append(f"{campo} = {valor}  ({origem})")
    return linhas


def main(argv: Sequence[str] | None = None) -> int:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
    from hefesto_dualsense4unix.profiles import loader

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--perfil")
    parser.add_argument("--campo", choices=tv.CAMPOS_DA_RECEITA)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--valor")
    grupo.add_argument("--tirar", action="store_true")
    parser.add_argument("--mostrar", action="store_true")
    parser.add_argument("--medir", action="store_true")
    args = parser.parse_args(argv)

    nome = args.perfil
    if nome is None and args.mostrar and args.campo is None:
        nome = _perfil_ativo()
    if not nome:
        print("recusa: diga o perfil (--perfil NOME); o daemon não disse o ativo.")
        return RC_RECUSA
    perfil = loader.perfil_em_disco(nome)
    if perfil is None:
        print(f"recusa: o perfil {nome!r} não existe.")
        return RC_RECUSA

    if args.campo is not None:
        if args.valor is None and not args.tirar:
            print("recusa: --campo pede --valor V ou --tirar.")
            return RC_RECUSA
        desvio = dict(getattr(perfil, tv.CAMPO_DA_RECEITA, None) or {})
        if args.tirar:
            desvio.pop(args.campo, None)
            acao = f"tirar {args.campo} do desvio"
        else:
            desvio[args.campo] = _valor(args.valor)
            acao = f"{args.campo} = {desvio[args.campo]!r}"
        if not args.medir:
            print(f"sem --medir nada se grava. Com ele: {acao} em {perfil.name!r}.")
            return RC_RECUSA
        perfil = perfil.model_copy(
            update={tv.CAMPO_DA_RECEITA: desvio or None})
        perfil = type(perfil).model_validate(perfil.model_dump())
        loader.save_profile(perfil, origem=ORIGEM_DA_GRAVACAO)
        print(f"gravado: {acao} em {perfil.name!r}.")
    elif not args.mostrar:
        parser.print_usage()
        return RC_RECUSA

    for linha in linhas_da_receita(perfil):
        print(linha)
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
