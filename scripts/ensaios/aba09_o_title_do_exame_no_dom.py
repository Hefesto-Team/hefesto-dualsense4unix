#!/usr/bin/env python3
"""Lê no DOM VIVO o `title` de cada linha do exame da aba Sistema."""
from __future__ import annotations

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo

LER = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('.saude .txt')){
    fora.push([(el.textContent||'').trim(), el.getAttribute('title') || '']);
  }
  return JSON.stringify(fora);
})()
"""


BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def main() -> int:
    import argparse

    args = argparse.Namespace(**BANDEIRAS, abre="09-sistema.html")
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {"linhas": None}

    def perguntar() -> bool:
        if not piloto.pronto:
            return True

        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["linhas"] = json.loads(texto) if texto and not erro else []
            Gtk.main_quit()

        piloto.ponte.perguntar(LER, respondeu)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2500, perguntar)
    GLib.timeout_add(25000, Gtk.main_quit)
    Gtk.main()

    linhas = saida["linhas"]
    if not linhas:
        print("REPROVA: não li uma linha de exame sequer no DOM.")
        return 1

    faltam = 0
    for visivel, titulo in linhas:
        bate = "ok" if titulo else "SEM TITLE"
        if not titulo:
            faltam += 1
        print(f"  [{bate:9s}] tela {len(visivel):3d} car · title {len(titulo):3d} car "
              f"· {titulo[:70] or visivel[:70]}")
    print(f"\n{len(linhas)} linha(s) · {faltam} sem `title`")
    return 1 if faltam else 0


if __name__ == "__main__":
    raise SystemExit(main())
