#!/usr/bin/env python3
"""A coluna SEM controle da aba Vibração não pode mostrar o desenho como dado."""
from __future__ import annotations

import argparse
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

ABA = "05-vibracao.html"

#: O TRAVESSÃO É DO PRODUTO, e não se digita aqui: ``app/telas/vibracao.NAO_SEI``
from hefesto_dualsense4unix.app.telas.vibracao import NAO_SEI

import monta

LUGARES = tuple(c["pref"] for c in monta.CONECTADOS)

PARES = (("mult", "forca-pct"), ("motor-e", "motor-e-pct"),
         ("motor-d", "motor-d-pct"))

LER = r"""
(function(){
  const fora = [];
  const largura = (el) => el.style.width || '';
  const pega = (i) => { while(fora.length <= i){ fora.push({campos:{}, larguras:{}, degraus:[]}); } return fora[i]; };
  const conta = {};
  for(const el of document.querySelectorAll('[data-campo]')){
    const campo = el.getAttribute('data-campo');
    if(campo === 'degrau'){
      // Os degraus vêm de quatro em quatro, um grupo por coluna ocupada.
      const i = Math.floor((conta['degrau'] = (conta['degrau'] || 0) + 1, conta['degrau'] - 1) / 4);
      if(el.classList.contains('on')){
        pega(i).degraus.push(el.getAttribute('data-hef-quando') || el.textContent.trim());
      }
      continue;
    }
    const i = (conta[campo] = (conta[campo] || 0) + 1) - 1;
    if(campo.endsWith('-pct')) pega(i).larguras[campo] = largura(el);
    else pega(i).campos[campo] = el.textContent.trim();
  }
  // A identidade viaja por `data-hef`, não por `data-campo` — é o rótulo da
  // coluna, e o pintor a alcança pelo mesmo fecho de endereços.
  let j = 0;
  for(const el of document.querySelectorAll('[data-hef="identidade"]')){
    pega(j++).campos['identidade'] = el.textContent.trim().replace(/\s+/g, ' ');
  }
  return JSON.stringify({lugares: fora, achei: document.querySelectorAll('[data-campo]').length,
                         url: location.pathname.split('/').pop()});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _largura_afirmada(w: str | None) -> bool:
    """`True` quando o trilho AFIRMA um comprimento — 0% e vazio não afirmam."""
    if not w:
        return False
    try:
        return float(w.rstrip("%")) > 0.0
    except ValueError:
        return False


def main() -> int:
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    medida: list[dict] = []

    def ir() -> bool:
        if not piloto.pronto:
            return True
        piloto._ir(ABA)
        GLib.timeout_add(2500, depois)
        return False

    def depois() -> bool:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            if erro or not texto:
                print(f"[dom] a ponte não respondeu: {erro}")
                Gtk.main_quit()
                return
            bruto = json.loads(texto)
            pagina.append(str(bruto["url"]))
            print(f"[dom] página {bruto['url']!r} · "
                  f"{bruto['achei']} elementos com data-campo")
            medida.extend(bruto["lugares"])
            Gtk.main_quit()

        piloto.ponte.perguntar(LER, respondeu)
        return False

    pagina: list[str] = []
    GLib.timeout_add(600, ir)
    GLib.timeout_add(40000, Gtk.main_quit)
    Gtk.main()

    if pagina and pagina[0] != ABA:
        print(f"REPROVA: li a página {pagina[0]!r}, e esta régua é da {ABA!r}.")
        return 1

    if not medida:
        print("REPROVA: não li o DOM — a janela não respondeu.")
        return 1

    print(f"{'lugar':6} {'identidade':26} "
          + " ".join(f"{n:>8}/{w:<11}" for n, w in PARES) + " degraus")
    print("-" * 112)
    culpados = []
    for i, lugar in enumerate(LUGARES):
        if i >= len(medida):
            print(f"{lugar:6} (a página não emitiu campo para este lugar)")
            continue
        d = medida[i]
        campos, larguras = d["campos"], d["larguras"]
        celas = " ".join(
            f"{campos.get(n)!s:>8}/{larguras.get(w)!s:<11}" for n, w in PARES)
        ident = f"{campos.get('identidade')}"[:26]
        print(f"{lugar:6} {ident:26} {celas} {d['degraus']}")
        for num, larg in PARES:
            if campos.get(num) == NAO_SEI and _largura_afirmada(larguras.get(larg)):
                culpados.append(
                    f"{lugar}: {num} diz {NAO_SEI!r} e o trilho {larg} afirma "
                    f"{larguras.get(larg)}")

    print()
    if culpados:
        print(f"REPROVA: {len(culpados)} trilho(s) afirmando largura sem número:")
        for c in culpados:
            print(f"  {c}")
        return 1
    print("OK: nenhum trilho desta aba afirma comprimento sem ter número.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
