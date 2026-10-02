#!/usr/bin/env python3
"""Guarda a casa inteira do Hefesto, confere a máquina limpa e devolve tudo."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[1]
DONO = RAIZ / "src" / "hefesto_dualsense4unix" / "utils" / "memoria_dos_controles.py"


def carregar_o_dono() -> ModuleType:
    """O inventário, pelo caminho — sem o pacote instalado."""
    spec = importlib.util.spec_from_file_location("_hefesto_memoria", DONO)
    if spec is None or spec.loader is None:
        raise SystemExit(f"não achei o dono do inventário em {DONO}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_hefesto_memoria"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="guardar-e-devolver-a-casa.py",
        description="Guarda a casa inteira do Hefesto, confere a máquina limpa "
                    "depois do uninstall, e devolve tudo por cima do install novo.",
    )
    sub = p.add_subparsers(dest="verbo", required=True)
    g = sub.add_parser("guardar", help="copia a casa e esquece os controles (Steam fechada)")
    g.add_argument("--seco", action="store_true", help="só diz o que faria")
    sub.add_parser("limpa", help="depois do uninstall: sobrou algo do Hefesto? "
                   "(sai 0 limpa, 1 sobrou, 3 não sei: falta privilégio)")
    d = sub.add_parser("devolver", help="devolve a pasta (a mais nova ainda não "
                       "devolvida da casa inteira, se não disser qual)")
    d.add_argument("pasta", nargs="?", default=None)
    d.add_argument("--seco", action="store_true", help="só diz o que faria")
    sub.add_parser("pastas", help="lista as pastas guardadas")
    a = p.parse_args(argv)

    m = carregar_o_dono()
    raizes = m.Raizes.do_ambiente()
    sistema = m.Sistema()
    try:
        m.conferir_o_ensaio(raizes)
        if a.verbo == "guardar":
            relato = m.guardar(raizes, m.CASA, sistema, seco=a.seco)
        elif a.verbo == "devolver":
            relato = m.devolver(raizes, sistema, a.pasta, seco=a.seco, alcance=m.CASA)
        elif a.verbo == "pastas":
            for pasta in m.pastas_guardadas(raizes):
                print(pasta)
            return 0
        else:
            rastros = m.conferir_a_casa(raizes, sistema)
            defeitos = [r for r in rastros if not r.de_proposito and not r.nao_sei]
            incertos = [r for r in rastros if r.nao_sei]
            for r in rastros:
                marca = ("NÃO SEI" if r.nao_sei
                         else "de propósito" if r.de_proposito else "SOBROU")
                print(f"{marca:<13} {r.onde} — {r.o_que}")
            if defeitos:
                return 1
            if incertos:
                print("não sei se está limpa: há lugar que só o root lê (acima)")
                return 3
            if not rastros:
                print("limpa: nenhum rastro do Hefesto nos lugares do inventário")
            else:
                print("limpa: só o que o uninstall deixa de propósito")
            return 0
    except m.RecusaError as erro:
        print(f"recusado: {erro}", file=sys.stderr)
        return 2
    for linha in relato.linhas:
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
