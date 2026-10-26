#!/usr/bin/env python3
"""A linha fechada da Gestão de Controles, medida DENTRO do WebKit dela."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

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

from hefesto_dualsense4unix.interface import hefesto_vivo, onde

ABA = "08-conexoes.html"

POR_CONTROLE = ("nome", "est-mic")
DA_PAGINA = ("confissao-nada", "confissao-conta")

ROTEIRO = r"""
(function(por_controle, da_aba){
  function um(raiz, campo){
    const el = raiz.querySelector('[data-campo="' + campo + '"]');
    if(!el) return null;
    return {texto: (el.textContent || '').trim(),
            titulo: el.getAttribute('title'),
            classes: el.className,
            visto: el.dataset.hefVisto || null};
  }
  const saida = {controles: {}, aba: {}};
  for(const raiz of document.querySelectorAll('.gc-item[data-controle]')){
    const campos = {conectado: raiz.dataset.conectado || null};
    for(const c of por_controle) campos[c] = um(raiz, c);
    saida.controles[raiz.dataset.controle] = campos;
  }
  for(const c of da_aba){
    const el = document.querySelector('[data-campo="' + c + '"]');
    saida.aba[c] = el === null ? null
      : {texto: (el.textContent || '').trim(),
         sumido: el.classList.contains('sumido'),
         visto: el.dataset.hefVisto || null};
  }
  return JSON.stringify(saida);
})(%s, %s)
""" % (json.dumps(POR_CONTROLE), json.dumps(DA_PAGINA))

BANDEIRAS = dict(oculta=True, segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _do_arquivo() -> dict[str, list[str]]:
    """O ANTES — o que a bancada crava em cada endereço, lido do arquivo."""
    import re

    html = onde.pagina(ABA).read_text(encoding="utf-8")
    cravado: dict[str, list[str]] = {}
    for campo in (*POR_CONTROLE, *DA_PAGINA):
        achados = re.findall(
            rf'data-campo="{campo}"[^>]*>(.*?)<', html, flags=re.S)
        cravado[campo] = [a.strip() for a in achados]
    return cravado


def faltando(dom: dict[str, Any]) -> list[str]:
    """Os endereços esperados que o DOM não tem, com o dono de cada um."""
    fora = [c for c in DA_PAGINA if dom["aba"].get(c) is None]
    for pref, d in sorted(dom["controles"].items()):
        fora += [f"{pref}.{c}" for c in POR_CONTROLE if d.get(c) is None]
    return fora


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--foto", default="", help="grava um PNG da janela oculta")
    escolha = ap.parse_args()

    onde.PUBLICADO = onde.BANCADA

    antes = _do_arquivo()
    sem_endereco = [c for c, achados in antes.items() if not achados]
    if sem_endereco:
        print(f"REPROVA: a {ABA} não tem os endereços {sem_endereco}.")
        return 1
    args = argparse.Namespace(**BANDEIRAS, abre=ABA, foto=escolha.foto)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {"dom": None, "erro": ""}

    def perguntar() -> bool:
        if not piloto.pronto:
            return True

        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["dom"] = json.loads(texto) if texto and not erro else None
            saida["erro"] = str(erro) if erro else ""
            if escolha.foto:
                piloto.tela.fotografar(escolha.foto)
            Gtk.main_quit()

        piloto.ponte.perguntar(ROTEIRO, respondeu)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(4000, perguntar)
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    dom = saida.get("dom")
    if not isinstance(dom, dict) or not dom.get("controles"):
        print(f"REPROVA: não li o DOM da {ABA}. {saida.get('erro', '')}")
        return 1

    print(f"ANTES (o que a bancada crava): {antes}")
    print()
    for pref, d in sorted(dom["controles"].items()):
        print(f"  {pref}  conectado={d['conectado']!r}")
        for chave in POR_CONTROLE:
            v = d.get(chave)
            marca = "" if v is None else ("  [pintado]" if v.get("visto") else "  [NÃO visitado]")
            print(f"        {chave:12s} {v if v is None else v['texto']!r}{marca}")
    print(f"\n  página      {dom['aba']}")

    fora = faltando(dom)
    if fora:
        print(f"\nREPROVA: endereço esperado que a {ABA} não tem: {', '.join(fora)}.")
        return 1

    visitados = [f"{pref}.{chave}"
                 for pref, d in dom["controles"].items()
                 for chave in POR_CONTROLE
                 if d[chave].get("visto")]
    visitados += [c for c in DA_PAGINA if dom["aba"][c].get("visto")]
    if not visitados:
        print("\nREPROVA: nenhum campo da linha fechada foi visitado pelo piloto — "
              "o pacote parou de emitir.")
        return 1

    print(f"\nOK: {len(visitados)} campo(s) da linha fechada visitados pelo produto "
          f"— {', '.join(sorted(visitados))}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
