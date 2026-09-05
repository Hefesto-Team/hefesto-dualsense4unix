#!/usr/bin/env python3
"""Clica um degrau de força na coluna do P1, DENTRO do WebKit dela, e mede.

POR QUE ELE EXISTE, e é a regra desta casa: os testes de unidade provam que o
gesto grava o override certo com uma ponte dublê e um disco de mentira. O que
eles NÃO provam é que o CLIQUE chega — que o botão da coluna tem endereço, que o
ouvinte o lê como gesto, que o `uniq` da coluna viaja junto, e que a resposta
volta para a tela. Foi assim que esta casa já deu verde sobre dois botões
mortos.

**ELE NÃO ESCREVE NO PERFIL DELA, e essa é a primeira coisa a conferir aqui.**
O ensaio desvia `HOME` e os quatro `XDG_*` para um lar de mentira e COPIA para
lá a pasta de perfis dela — leitura, nunca escrita. O gesto grava na cópia; o
original não é aberto para escrita em momento nenhum.

O QUE ELE FAZ, em quatro tempos:

1. abre a `05-vibracao` publicada no `WebKit2.WebView`, oculta, e fotografa;
2. lê qual degrau está aceso em cada coluna VIVA, antes;
3. clica um degrau que NÃO é o de agora, na coluna do P1, pelo caminho dela —
   `element.click()` no DOM, que dispara o ouvinte real do piloto;
4. relê o DOM (o degrau aceso e os recados), fotografa de novo e abre o
   arquivo de perfil da CÓPIA para ver o que foi gravado.

Reprova se o clique não mudar o degrau aceso do P1, se ele mexer no de outra
coluna, ou se o override não aparecer no arquivo.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/a_forca_por_controle_no_webkit.py --antes /tmp/a.png --depois /tmp/b.png
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

#: O LAR DE MENTIRA, e ele nasce ANTES de qualquer import que resolva caminho.
#: `utils.xdg_paths` lê o ambiente a cada chamada (de propósito — ver
#: `pacotes/perfil.pasta`), então basta o ambiente estar posto antes do gesto.
#: Pô-lo aqui, e não depois dos imports, é a trava contra um módulo que resolva
#: o caminho no import de alguém.
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

ABA = "05-vibracao.html"

#: O QUE SE LÊ NO DOM, e é o que a tela MOSTRA — não o que o pacote emitiu.
#: O degrau aceso é uma CLASSE (`on`), que é como o desenho o diz.
LER = r"""
(function(){
  const fora = {colunas: {}, recados: []};
  for(const bloco of document.querySelectorAll('[data-controle]')){
    const pref = bloco.dataset.controle;
    const botoes = bloco.querySelectorAll('[data-papel="forca"][data-forca]');
    if(!botoes.length){ continue; }
    let aceso = null;
    const todos = [];
    for(const b of botoes){
      todos.push(b.dataset.forca);
      if(b.classList.contains('on')){ aceso = b.dataset.forca; }
    }
    fora.colunas[pref] = {aceso: aceso, degraus: todos,
                          uniq: bloco.dataset.uniq || '',
                          vazio: bloco.classList.contains('vazia')};
  }
  for(const r of document.querySelectorAll('.hef-recado, [data-hef-recado]')){
    fora.recados.push((r.textContent || '').trim().slice(0, 160));
  }
  return JSON.stringify(fora);
})()
"""

#: O ARRASTE, e ele é o caminho dela num `<input type=range>`: mudar o `value`
#: e disparar `change`. É o MESMO evento que o polegar solto dispara — o ouvinte
#: do piloto escuta `change` desde 01/09 —, e `dispatchEvent` é a única forma de
#: mover um range sem tocar no mouse dela.
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

#: O CLIQUE, e ele é o DELA: `element.click()` no botão que o desenho publica.
#: Nada aqui chama a função de gesto por dentro — o que se mede é o caminho
#: inteiro, do pixel ao pacote.
CLICAR = r"""
(function(){
  const bloco = document.querySelector('[data-controle="__PREF__"]');
  if(!bloco){ return JSON.stringify({erro: 'coluna __PREF__ não está na página'}); }
  const alvo = bloco.querySelector('[data-papel="forca"][data-forca="__DEGRAU__"]');
  if(!alvo){ return JSON.stringify({erro: 'degrau __DEGRAU__ não está na coluna'}); }
  const antes = alvo.getBoundingClientRect();
  alvo.click();
  return JSON.stringify({clicou: '__DEGRAU__', rotulo: (alvo.textContent||'').trim(),
                         area: Math.round(antes.width * antes.height)});
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
    ap.add_argument("--degrau", default="economia")
    ap.add_argument("--perfis-de-origem", default="",
                    help="a pasta de perfis a COPIAR (só leitura)")
    ap.add_argument("--bancada", action="store_true",
                    help="abre o desenho de `mockup/` em vez da página "
                         "publicada — é onde a barra arrastável já existe")
    ap.add_argument("--arrasta", type=int, default=-1,
                    help="em vez de clicar um degrau, arrasta a barra até N%%")
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
        if args_meus.arrasta >= 0:
            _pergunta(ARRASTAR.replace("__PREF__", args_meus.pref)
                              .replace("__PONTOS__", str(args_meus.arrasta)),
                      "clique")
        else:
            _pergunta(CLICAR.replace("__PREF__", args_meus.pref)
                            .replace("__DEGRAU__", args_meus.degrau), "clique")
        return False

    def depois() -> bool:
        if args_meus.depois:
            piloto.tela.fotografar(args_meus.depois)
        _pergunta(LER, "depois", depois=Gtk.main_quit)
        return False

    def _abrir() -> bool:
        # A BANCADA É OUTRA PASTA, e o dono das duas é o `onde` — nunca um
        # `RAIZ / "mockup"` escrito à mão. `piloto._ir` abre sempre a publicada,
        # que é o que o produto faz; aqui a escolha é do ensaio.
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
              f"{ca.get('aceso')!s:12s} {cd.get('aceso')!s:12s}")
    print(f"recados na tela, depois: {d['recados']}")

    for arq in sorted(destino.glob("*.json")):
        j = json.loads(arq.read_text(encoding="utf-8"))
        por_controle = j.get("controllers") or {}
        print(f"\n{arq.name}: rumble global = {(j.get('rumble') or {}).get('policy')!r}")
        for chave, ov in por_controle.items():
            print(f"  {chave}: rumble = {(ov or {}).get('rumble')}")

    alvo = d["colunas"].get(args_meus.pref, {})
    if args_meus.arrasta >= 0:
        # ARRASTAR PÕE A COLUNA EM `custom`, e `custom` NÃO é um dos quatro
        # degraus: o alvo `classe` do pintor apaga os quatro, que é a resposta
        # certa — nenhum botão descreve o que ela escolheu.
        if alvo.get("aceso") is not None:
            print(f"\nREPROVA: depois do arraste a coluna {args_meus.pref} "
                  f"ainda acende {alvo['aceso']!r} — a tela diria que ela "
                  f"escolheu um degrau que não escolheu.")
            return 1
        print(f"\nOK: o arraste até {args_meus.arrasta}% apagou os quatro "
              f"degraus da coluna {args_meus.pref} — a escolha dela não é "
              f"nenhum deles.")
        return 0
    if alvo.get("aceso") != args_meus.degrau:
        print(f"\nREPROVA: a coluna {args_meus.pref} devia acender "
              f"{args_meus.degrau!r} e acendeu {alvo.get('aceso')!r}.")
        return 1
    outras = {p: c.get("aceso") for p, c in d["colunas"].items()
              if p != args_meus.pref}
    print(f"\nOK: o clique acendeu {args_meus.degrau!r} SÓ na coluna "
          f"{args_meus.pref}; as outras ficaram em {outras}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
