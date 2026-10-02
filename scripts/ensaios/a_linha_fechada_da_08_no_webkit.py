#!/usr/bin/env python3
"""A linha fechada da Gestão de Controles, medida DENTRO do WebKit dela."""
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

from hefesto_dualsense4unix.interface import hefesto_vivo, onde

ABA = "08-conexoes.html"

ROTEIRO = r"""
(function(){
  function um(raiz, campo){
    const el = raiz.querySelector('[data-campo="' + campo + '"]');
    if(!el) return null;
    return {texto: (el.textContent || '').trim(),
            titulo: el.getAttribute('title'),
            classes: el.className,
            visto: el.dataset.hefVisto || null};
  }
  const saida = {controles: {}, confissao: null};
  for(const raiz of document.querySelectorAll('[data-controle]')){
    const pref = raiz.dataset.controle;
    const botao = raiz.querySelector('[data-campo="luz-trava"]');
    saida.controles[pref] = {
      conectado: raiz.dataset.conectado || null,
      nome: um(raiz, 'nome'),
      mic_existe: um(raiz, 'mic-existe'),
      mic_caminho: um(raiz, 'mic-caminho'),
      luz: botao === null ? null : {apagado: botao.classList.contains('apagado'),
                                   visto: botao.dataset.hefVisto || null}
    };
  }
  const linha = document.querySelector('[data-campo="confissao-nada"]');
  if(linha){
    saida.confissao = {
      sumido: linha.classList.contains('sumido'),
      conta: um(linha, 'confissao-conta'),
      dica: um(linha, 'confissao-dica')
    };
  }
  return JSON.stringify(saida);
})()
"""

BANDEIRAS = dict(oculta=True, segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _do_arquivo() -> dict[str, str]:
    """O ANTES — o que a bancada crava, lido do arquivo e não do DOM."""
    import re

    html = onde.pagina(ABA).read_text(encoding="utf-8")
    cravado: dict[str, str] = {}
    for campo in ("mic-existe", "mic-caminho", "confissao-conta"):
        achados = re.findall(
            rf'data-campo="{campo}"[^>]*>(.*?)<', html, flags=re.S)
        cravado[campo] = " · ".join(a.strip() for a in achados)
    return cravado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--foto", default="", help="grava um PNG da janela oculta")
    escolha = ap.parse_args()

    onde.PUBLICADO = onde.BANCADA

    antes = _do_arquivo()
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
    if not dom:
        print(f"REPROVA: não li o DOM da {ABA}. {saida.get('erro', '')}")
        return 1

    print(f"ANTES (o que a bancada crava): {antes}")
    print()
    for pref, d in sorted(dom["controles"].items()):
        print(f"  {pref}  conectado={d['conectado']!r}")
        for chave in ("nome", "mic_existe", "mic_caminho"):
            v = d[chave]
            marca = "" if v is None else ("  [pintado]" if v.get("visto") else "  [NÃO visitado]")
            print(f"        {chave:12s} {v if v is None else v['texto']!r}{marca}")
        print(f"        luz          {d['luz']}")
    print(f"\n  confissão   {dom['confissao']}")

    visitados = [f"{pref}.{chave}"
                 for pref, d in dom["controles"].items()
                 for chave in ("mic_existe", "mic_caminho")
                 if d[chave] and d[chave].get("visto")]
    if dom["confissao"] and (dom["confissao"]["conta"] or {}).get("visto"):
        visitados.append("confissao-conta")
    if not visitados:
        print("\nREPROVA: nenhum campo desta leva foi visitado pelo piloto — "
              "ou os endereços sumiram da bancada, ou o pacote parou de emitir.")
        return 1

    print(f"\nOK: {len(visitados)} campo(s) desta leva visitados pelo produto "
          f"— {', '.join(sorted(visitados))}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
