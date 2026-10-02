#!/usr/bin/env python3
"""Regera as DEZ abas de uma vez, contra o MESMO desenho."""
import pathlib, subprocess, sys
import monta

F = pathlib.Path(__file__).resolve().parent
D = F.parent

if __name__ == "__main__":
    quais = sys.argv[1:] or [f"{n:02d}" for n in range(1, 11)]
    for n in quais:
        subprocess.run([sys.executable, str(F / f"aba{n}.py")], check=True, cwd=F)

    agora = (F / "ds_limpo.svg").read_text()
    if agora != monta.DS:
        sys.exit("\nATENÇÃO: o ds_limpo.svg mudou durante esta volta.\n"
                 "As abas ficaram com desenhos diferentes de novo — rode outra vez.")
    print(f"\nas {len(quais)} abas contra o MESMO desenho ({len(monta.DS)} bytes)")
