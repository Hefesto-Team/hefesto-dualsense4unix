#!/usr/bin/env python3
"""Os quatro lugares de controle são alcançáveis, aba por aba, no DOM VIVO.

POR QUE ELE EXISTE, e é a regra desta casa: o teste de unidade
``test_os_quatro_lugares_tem_endereco_em_toda_aba`` lê o HTML no disco. O que
prova o PRODUTO é o ``WebKit2.WebView`` que ela usa — o piloto pode, em tese,
remover um endereço em tempo de execução, e o disco continuaria verde.

A DECISÃO É DELA, 03/09/2026: *"tem que aparecer desligado enquanto não tem
nenhum controle. A partir do momento que tiver, ele aparece o controle
devidamente conectado. Se isso não ocorre com os 4 controles em cada aba, então
temos que construir isso e garantir isso."*

Ele passeia pelas sete abas com lugar por controle e pergunta, em cada uma,
quantos elementos ``[data-controle="pN"]`` existem. Reprova se algum der zero.

Uso (a janela é OCULTA; ela tem UMA tela)::

    scripts/ensaios/os_quatro_lugares_no_dom.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Ela pediu duas vezes em 04/09/2026; o `park` do workspace chega tarde,
# porque move a janela DEPOIS de ela existir. Escape: HEFESTO_NA_TELA=1.
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

ABAS = ("01-jogar.html", "02-controles.html", "03-gatilhos.html",
        "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
        "08-conexoes.html")
CASAS = ("p1", "p2", "p3", "p4")

LER = r"""
(function(){
  const fora = {};
  for(const p of ['p1','p2','p3','p4']){
    const els = document.querySelectorAll('[data-controle="' + p + '"]');
    fora[p] = {quantos: els.length,
               conectado: els.length ? (els[0].dataset.conectado || null) : null};
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
    args = argparse.Namespace(**BANDEIRAS, abre=ABAS[0])
    piloto = hefesto_vivo.Piloto(args)
    medidas: dict[str, dict] = {}
    fila = list(ABAS)

    def proxima() -> bool:
        if not piloto.pronto:
            return True
        if not fila:
            Gtk.main_quit()
            return False
        aba = fila.pop(0)
        piloto._ir(aba)

        def depois() -> bool:
            def respondeu(texto: str | None, erro: Exception | None) -> None:
                medidas[aba] = json.loads(texto) if texto and not erro else {}
                GLib.timeout_add(200, proxima)

            piloto.ponte.perguntar(LER, respondeu)
            return False

        GLib.timeout_add(1400, depois)
        return False

    GLib.timeout_add(600, proxima)
    GLib.timeout_add(90000, Gtk.main_quit)
    Gtk.main()

    if not medidas:
        print("REPROVA: não li uma aba sequer.")
        return 1

    print(f"{'aba':22s} " + "  ".join(f"{c:>10s}" for c in CASAS))
    print("-" * 68)
    faltam = []
    for aba in ABAS:
        m = medidas.get(aba)
        if m is None:
            print(f"{aba:22s} (não visitada)")
            faltam.append(f"{aba}: não visitada")
            continue
        cels = []
        for c in CASAS:
            d = m.get(c) or {"quantos": 0, "conectado": None}
            if d["quantos"] == 0:
                cels.append(f"{'NINGUÉM':>10s}")
                faltam.append(f"{aba}: {c}")
            else:
                cels.append(f"{d['conectado'] or '?':>10s}")
        print(f"{aba:22s} " + "  ".join(cels))

    print()
    if faltam:
        print(f"REPROVA: {len(faltam)} lugar(es) sem endereço no DOM vivo:")
        for f in faltam:
            print(f"  {f}")
        return 1
    print("OK: os quatro lugares são alcançáveis nas sete abas. Quando o "
          "controle chegar, o produto tem onde escrever.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
