#!/usr/bin/env python3
"""Arrasta o trilho da Força na coluna do P1, DENTRO do WebKit dela, e mede.

Desde 20/10/2026 a «Força» é só o trilho de 0 a 200% (O-GESTO-FORCA-DOS-DEGRAUS-DA-VIBRACAO-SAI-01).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]

_LAR = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-ensaio-forca-"))
for _chave, _valor in (("HOME", _LAR),
                       ("XDG_CONFIG_HOME", _LAR / ".config"),
                       ("XDG_DATA_HOME", _LAR / ".local/share"),
                       ("XDG_STATE_HOME", _LAR / ".local/state"),
                       ("XDG_CACHE_HOME", _LAR / ".cache")):
    os.environ[_chave] = str(_valor)
    pathlib.Path(_valor).mkdir(parents=True, exist_ok=True)

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

LER = r"""
(function(){
  const fora = {colunas: {}, recados: []};
  for(const bloco of document.querySelectorAll('[data-controle]')){
    const pref = bloco.dataset.controle;
    const barra = bloco.querySelector('input[type=range][data-papel="intensidade"]');
    if(!barra){ continue; }
    fora.colunas[pref] = {valor: barra.value,
                          uniq: bloco.dataset.uniq || '',
                          vazio: bloco.classList.contains('vazia')};
  }
  for(const r of document.querySelectorAll('.hef-recado, [data-hef-recado]')){
    fora.recados.push((r.textContent || '').trim().slice(0, 160));
  }
  return JSON.stringify(fora);
})()
"""

ARRASTAR = r"""
(function(){
  const bloco = document.querySelector('[data-controle="__PREF__"]');
  if(!bloco){ return JSON.stringify({erro: 'coluna __PREF__ não está na página'}); }
  const barra = bloco.querySelector('input[type=range][data-papel="intensidade"]');
  if(!barra){ return JSON.stringify({erro: 'a barra arrastável não está na coluna'}); }
  const antes = barra.value;
  barra.value = '__PONTOS__';
  barra.dispatchEvent(new Event('change', {bubbles: true}));
  return JSON.stringify({antes: antes, depois: barra.value,
                         min: barra.min, max: barra.max, passo: barra.step});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--antes", default="")
    ap.add_argument("--depois", default="")
    ap.add_argument("--pref", default="p1")
    ap.add_argument("--perfis-de-origem", default="",
                    help="a pasta de perfis a COPIAR (só leitura)")
    ap.add_argument("--bancada", action="store_true",
                    help="abre o desenho de `mockup/` em vez da página "
                         "publicada — é onde a barra arrastável já existe")
    ap.add_argument("--arrasta", type=int, default=30,
                    help="arrasta a barra da coluna até N%%")
    args_meus = ap.parse_args()

    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    destino = profiles_dir()
    destino.mkdir(parents=True, exist_ok=True)
    origem = pathlib.Path(args_meus.perfis_de_origem) if args_meus.perfis_de_origem else None
    if origem and origem.is_dir():
        for arq in origem.glob("*.json"):
            shutil.copy2(arq, destino / arq.name)
    copiados = sorted(p.name for p in destino.glob("*.json"))
    print(f"lar de mentira: {_LAR}")
    print(f"perfis copiados ({len(copiados)}): {', '.join(copiados) or '(nenhum)'}")

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {}

    def _pergunta(js: str, chave: str, depois=None):
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida[chave] = json.loads(texto) if texto and not erro else None
            saida[f"{chave}_erro"] = str(erro) if erro else ""
            if depois is not None:
                depois()
        piloto.ponte.perguntar(js, respondeu)

    def antes() -> bool:
        if not piloto.pronto:
            return True
        if args_meus.antes:
            piloto.tela.fotografar(args_meus.antes)
        _pergunta(LER, "antes")
        return False

    def clicar() -> bool:
        _pergunta(ARRASTAR.replace("__PREF__", args_meus.pref)
                          .replace("__PONTOS__", str(args_meus.arrasta)),
                  "clique")
        return False

    def depois() -> bool:
        if args_meus.depois:
            piloto.tela.fotografar(args_meus.depois)
        _pergunta(LER, "depois", depois=Gtk.main_quit)
        return False

    def _abrir() -> bool:
        import onde as _onde

        piloto.view.load_uri(
            _onde.pagina(ABA, publicado=not args_meus.bancada).as_uri())
        return False

    GLib.timeout_add(400, _abrir)
    GLib.timeout_add(3500, antes)
    GLib.timeout_add(5000, clicar)
    GLib.timeout_add(9000, depois)
    GLib.timeout_add(40000, Gtk.main_quit)
    Gtk.main()

    a, d = saida.get("antes"), saida.get("depois")
    print(f"\nclique: {saida.get('clique')}")
    if not a or not d:
        print(f"REPROVA: não li o DOM. {saida.get('antes_erro', '')} "
              f"{saida.get('depois_erro', '')}")
        return 1
    print(f"{'coluna':8s} {'uniq':20s} {'antes':12s} {'depois':12s}")
    for pref in sorted(set(a["colunas"]) | set(d["colunas"])):
        ca, cd = a["colunas"].get(pref, {}), d["colunas"].get(pref, {})
        print(f"{pref:8s} {cd.get('uniq') or ca.get('uniq') or '—'!s:20s} "
              f"{ca.get('valor')!s:12s} {cd.get('valor')!s:12s}")
    print(f"recados na tela, depois: {d['recados']}")

    for arq in sorted(destino.glob("*.json")):
        j = json.loads(arq.read_text(encoding="utf-8"))
        por_controle = j.get("controllers") or {}
        print(f"\n{arq.name}: rumble global = {(j.get('rumble') or {}).get('policy')!r}")
        for chave, ov in por_controle.items():
            print(f"  {chave}: rumble = {(ov or {}).get('rumble')}")

    alvo = d["colunas"].get(args_meus.pref, {})
    if str(alvo.get("valor")) != str(args_meus.arrasta):
        print(f"\nREPROVA: depois do arraste a coluna {args_meus.pref} mostra "
              f"{alvo.get('valor')!r}, e o arraste foi até {args_meus.arrasta}.")
        return 1
    mexeu = {q: (a["colunas"].get(q, {}).get("valor"), c.get("valor"))
             for q, c in d["colunas"].items() if q != args_meus.pref
             and a["colunas"].get(q, {}).get("valor") != c.get("valor")}
    if mexeu:
        print(f"\nREPROVA: o arraste na coluna {args_meus.pref} mexeu em {mexeu}.")
        return 1
    print(f"\nOK: o arraste até {args_meus.arrasta}% ficou SÓ na coluna "
          f"{args_meus.pref}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
