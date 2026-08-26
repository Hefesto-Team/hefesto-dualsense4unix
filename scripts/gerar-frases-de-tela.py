#!/usr/bin/env python3
"""gerar-frases-de-tela.py — constrói `frases-de-tela.html`: o que espera o olho dela.

O TERCEIRO IRMÃO
----------------
O ``specs.html`` responde *"o que o aparelho entende, por qual canal"*. O
``painel.html`` responde *"onde o projeto está"*. Este responde
*"que frases de tela mudaram e ainda não passaram por ela"*.

Os três dividem a paleta (``scripts/paleta_da_casa.py``) e a regra que a
originou, que não se negocia: **autocontido, zero rede, zero CDN, zero fonte
web.** Abre com duplo clique, sem servidor, sem venv e sem internet.

    scripts/gerar-frases-de-tela.py            # reescreve html/frases-de-tela.html
    scripts/gerar-frases-de-tela.py --check    # rc=1 se o publicado divergir

POR QUE ELE EXISTE, E NÃO UM ARTEFATO NA NUVEM
-----------------------------------------------
Regra dela, 25/08/2026: *"sem artifact no projeto, apenas html standalone"*.
O motivo é o mesmo que o ``gerar-mapa.py`` já registrava para a fonte web —
*"um instrumento que só funciona com rede não serve para depurar rádio"* — e
vale igual aqui: a decisão sobre a tela é dela, na máquina dela, com o produto
aberto ao lado. Um instrumento que depende de outra aba do navegador e de uma
conta de terceiro não é parte deste produto.

O DADO É VERSIONADO, E ISSO É O PONTO
--------------------------------------
A página não recalcula nada: ela RENDERIZA
``docs/process/dados/frases-de-tela-25-08.json``, que é a enumeração feita em
25/08 sobre os 27 relatórios da madrugada. Separar os dois é o que permite que a
lista seja auditável (o JSON entra no diff) e que a página seja descartável.

**A enumeração corrigiu um fato publicado:** os documentos diziam *"quarenta e
três mudanças, em dez das onze abas"* e mandavam buscar a lista no *"relatório
do conferente da leva"* — **que nunca existiu**. São SESSENTA, em onze abas,
mais o rodapé e a saída de terminal. E o piso é maior: cinco linhas são pacotes
(as oito frases do ``./install.sh``, as 38 dicas dos 19 modos de gatilho, e mais
três). Frase por frase, passa de cem.

O QUE ELA MARCA FICA NO NAVEGADOR DELA
---------------------------------------
Os botões *boa* / *mexer* gravam em ``localStorage``, que é por navegador e por
máquina. Não é sincronização e não pretende ser: é para ela poder fechar a
página no meio das sessenta e voltar depois. O que vale como decisão é o que ela
diz — isto aqui é a folha de rascunho, e o ``PROVA-DE-TELA-01`` continua sendo o
protocolo.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from carimbo_da_casa import CSS as CARIMBO_CSS
from carimbo_da_casa import PASTA as PASTA_HTML
from carimbo_da_casa import carimbo, sem_carimbo
from paleta_da_casa import TOKENS

RAIZ = Path(__file__).resolve().parents[1]
DADO = RAIZ / "docs" / "process" / "dados" / "frases-de-tela-25-08.json"
SAIDA = RAIZ / PASTA_HTML / "frases-de-tela.html"

#: A ordem da TIRA — como ela vê as abas na janela, e não a alfabética.
#:
#: É informação, não enfeite: a ordem em que ela percorre a janela é a ordem em
#: que faz sentido revisar. Medida do `<child type="tab">` do `main.glade`.
TIRA = (
    "Início", "Status", "No jogo", "Gatilhos", "Lightbar", "Rumble",
    "Perfis", "Sistema", "Emulação", "Navegação", "Configurações",
)


def _ordem(nome: str) -> int:
    for i, aba in enumerate(TIRA):
        if nome.startswith(aba):
            return i
    return 99  # rodapé e terminal vão para o fim, e é onde eles pertencem


def _marca(texto: object) -> str:
    """Escapa, e realça o que está entre aspas — ali é texto de tela.

    A frase citada é DADO, não prosa: é o literal que o produto mostra. Dar-lhe
    marca própria é o que deixa a página escaneável sem uma legenda.
    """
    s = html.escape(str(texto))
    return re.sub(r"&quot;([^&]*?)&quot;", r"<em>\1</em>", s)


ESTILO = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--color-paper);color:var(--color-ink);
  font-family:var(--font-corpo);font-size:var(--text-base);line-height:1.6;
  -webkit-font-smoothing:antialiased}
.env{max-width:70rem;margin:0 auto;padding:var(--space-md) var(--space-sm) var(--space-2xl)}
header{padding:var(--space-lg) 0 var(--space-md);border-bottom:2px solid var(--color-accent)}
h1{font-size:var(--text-display);line-height:1.05;margin:0 0 var(--space-xs);
  font-weight:700;letter-spacing:-.02em;text-wrap:balance}
.sub{color:var(--color-ink-quiet);max-width:62ch;margin:0}
.conta{display:flex;flex-wrap:wrap;gap:var(--space-md);margin-top:var(--space-md);
  font-family:var(--font-dado);font-size:var(--text-sm)}
.conta div{display:flex;flex-direction:column;gap:2px}
.conta b{font-size:var(--text-xl);font-variant-numeric:tabular-nums;line-height:1}
.conta span{color:var(--color-ink-faint);font-size:var(--text-xs);
  text-transform:uppercase;letter-spacing:.08em}
.riscado{text-decoration:line-through;color:var(--color-ink-faint)}
.nota{margin:var(--space-md) 0 0;padding:var(--space-sm);
  border-left:3px solid var(--color-lacuna);background:var(--color-paper-2);
  color:var(--color-ink-quiet);font-size:var(--text-sm);max-width:70ch}
.nota strong{color:var(--color-lacuna)}
.barra{position:sticky;top:0;z-index:5;background:var(--color-paper);
  padding:var(--space-sm) 0;border-bottom:var(--rule-hair) solid var(--color-rule);
  display:flex;flex-wrap:wrap;gap:var(--space-3xs);align-items:center}
.barra button{font:inherit;font-size:var(--text-xs);font-family:var(--font-dado);
  background:var(--color-paper-3);color:var(--color-ink-quiet);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  padding:.3rem .55rem;cursor:pointer;
  transition:color var(--dur-fast) var(--ease-out),border-color var(--dur-fast) var(--ease-out)}
.barra button:hover{color:var(--color-ink);border-color:var(--color-ink-faint)}
.barra button[aria-pressed="true"]{background:var(--color-accent);
  color:var(--color-paper);border-color:var(--color-accent);font-weight:600}
.barra .placar{margin-left:auto;font-family:var(--font-dado);font-size:var(--text-xs);
  color:var(--color-ink-faint);font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--color-frio);outline-offset:2px}
h2{font-size:var(--text-xl);margin:var(--space-lg) 0 var(--space-2xs);font-weight:700;
  display:flex;align-items:baseline;gap:var(--space-2xs);text-wrap:balance}
h2 .n{font-family:var(--font-dado);font-size:var(--text-sm);
  color:var(--color-ink-faint);font-weight:400;font-variant-numeric:tabular-nums}
.secao-nota{color:var(--color-ink-faint);font-size:var(--text-sm);
  margin:0 0 var(--space-sm);max-width:62ch}
.item{border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-md);
  background:var(--color-paper-2);margin-bottom:var(--space-2xs);overflow:hidden;
  transition:border-color var(--dur-base) var(--ease-out),opacity var(--dur-base) var(--ease-out)}
.item[data-voto="sim"]{border-color:var(--color-ok)}
.item[data-voto="nao"]{border-color:var(--color-alerta)}
.item[data-voto="nao"] .par{opacity:.5}
.item .onde{font-family:var(--font-dado);font-size:var(--text-xs);
  color:var(--color-ink-faint);padding:var(--space-2xs) var(--space-xs);
  border-bottom:var(--rule-hair) solid var(--color-rule);
  display:flex;gap:var(--space-2xs);align-items:center;flex-wrap:wrap}
.conferir{color:var(--color-lacuna);border:var(--rule-hair) solid var(--color-lacuna);
  border-radius:var(--radius-sm);padding:0 .35rem;font-size:10px;letter-spacing:.06em;
  text-transform:uppercase;white-space:nowrap}
.par{display:grid;grid-template-columns:1fr 1fr;gap:var(--rule-hair);
  background:var(--color-rule)}
@media (max-width:46rem){.par{grid-template-columns:1fr}}
.lado{background:var(--color-paper-2);padding:var(--space-xs)}
.lado .rot{font-family:var(--font-dado);font-size:10px;text-transform:uppercase;
  letter-spacing:.1em;margin-bottom:var(--space-3xs)}
.saiu .rot{color:var(--color-alerta)}
.entrou .rot{color:var(--color-ok)}
.frase{font-family:var(--font-dado);font-size:var(--text-sm);line-height:1.5;
  white-space:pre-wrap;overflow-wrap:anywhere;margin:0}
.saiu .frase{color:var(--color-ink-quiet)}
.entrou .frase{color:var(--color-ink)}
.frase em{font-style:normal;color:var(--color-frio)}
.porque{padding:var(--space-2xs) var(--space-xs);font-size:var(--text-sm);
  color:var(--color-ink-quiet);border-top:var(--rule-hair) solid var(--color-rule);
  display:flex;gap:var(--space-xs);align-items:flex-start;justify-content:space-between}
.porque p{margin:0;max-width:70ch}
.votos{display:flex;gap:var(--space-3xs);flex-shrink:0}
.votos button{font:inherit;font-family:var(--font-dado);font-size:var(--text-xs);
  background:transparent;color:var(--color-ink-faint);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  padding:.15rem .5rem;cursor:pointer;white-space:nowrap;
  transition:all var(--dur-fast) var(--ease-out)}
.votos button:hover{color:var(--color-ink);border-color:var(--color-ink-faint)}
.votos button[aria-pressed="true"][data-v="sim"]{background:var(--color-ok);
  color:var(--color-paper);border-color:var(--color-ok)}
.votos button[aria-pressed="true"][data-v="nao"]{background:var(--color-alerta);
  color:var(--color-ink);border-color:var(--color-alerta)}
.oito{list-style:none;padding:0;margin:0;counter-reset:oito}
.oito li{counter-increment:oito;position:relative;padding-left:2.2rem;
  margin-bottom:var(--space-2xs);color:var(--color-ink-quiet);max-width:74ch}
.oito li::before{content:counter(oito,decimal-leading-zero);position:absolute;
  left:0;top:.1rem;font-family:var(--font-dado);font-size:var(--text-sm);
  color:var(--color-accent);font-weight:700}
.oito li strong{color:var(--color-ink)}
footer{margin-top:var(--space-xl);padding-top:var(--space-md);
  border-top:var(--rule-hair) solid var(--color-rule);
  color:var(--color-ink-faint);font-size:var(--text-sm)}
footer code{color:var(--color-ink-quiet)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

SCRIPT = """
(function(){
  var CHAVE="hefesto.frases.25-08";
  var votos={};
  try{votos=JSON.parse(localStorage.getItem(CHAVE)||"{}")}catch(e){votos={}}
  function guarda(){try{localStorage.setItem(CHAVE,JSON.stringify(votos))}catch(e){}}
  function placar(){
    var itens=document.querySelectorAll(".item"),s=0,n=0;
    itens.forEach(function(it){var v=it.dataset.voto;if(v==="sim")s++;else if(v==="nao")n++});
    document.getElementById("placar").textContent=
      s+" boa \\u00b7 "+n+" mexer \\u00b7 "+(itens.length-s-n)+" sem olhar";
  }
  document.querySelectorAll(".item").forEach(function(it){
    var id=it.dataset.id,v=votos[id]||"";
    it.dataset.voto=v;
    it.querySelectorAll(".votos button").forEach(function(b){
      b.setAttribute("aria-pressed",String(b.dataset.v===v));
      b.addEventListener("click",function(){
        var novo=(it.dataset.voto===b.dataset.v)?"":b.dataset.v;
        it.dataset.voto=novo;votos[id]=novo;guarda();
        it.querySelectorAll(".votos button").forEach(function(o){
          o.setAttribute("aria-pressed",String(o.dataset.v===novo))});
        placar();
      });
    });
  });
  document.querySelectorAll(".barra button").forEach(function(b){
    b.addEventListener("click",function(){
      var f=b.dataset.f;
      document.querySelectorAll(".barra button").forEach(function(o){
        o.setAttribute("aria-pressed",String(o===b))});
      document.querySelectorAll("section[data-aba]").forEach(function(s){
        s.hidden=!(f==="todas"||s.dataset.aba===f)});
    });
  });
  placar();
})();
"""


def construir() -> str:
    t = json.loads(DADO.read_text(encoding="utf-8"))
    abas = sorted(t["por_aba"], key=lambda a: _ordem(a["aba"]))
    total = sum(a["quantas"] for a in abas)
    conferir = sum(1 for a in abas for m in a["mudancas"] if not m["literal"])
    de_aba = len([a for a in abas if _ordem(a["aba"]) < 99])
    e = html.escape

    P: list[str] = []
    P.append("<!doctype html>")
    P.append('<html lang="pt-BR"><head><meta charset="utf-8">')
    P.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    P.append("<title>As frases que esperam você — Hefesto</title>")
    P.append(f"<style>{TOKENS}{ESTILO}{CARIMBO_CSS}</style></head><body>")
    P.append('<div class="env">')

    P.append("<header><h1>As frases que esperam você</h1>")
    P.append(
        '<p class="sub">As mudanças de texto de tela da madrugada de 25/08, aba por '
        "aba, na ordem em que elas aparecem na sua janela. Nenhuma foi aprovada — "
        "a palavra final é sua.</p>"
    )
    P.append('<div class="conta">')
    P.append(f'<div><b>{total}</b><span>frases</span></div>')
    P.append(f'<div><b>{de_aba}</b><span>abas</span></div>')
    P.append('<div><b class="riscado">43</b><span>o número publicado</span></div>')
    P.append(
        f'<div><b style="color:var(--color-lacuna)">{conferir}</b>'
        "<span>a conferir no código</span></div>"
    )
    P.append("</div>")
    P.append(
        '<p class="nota"><strong>O número publicado era 43, e a lista não existia.</strong> '
        "O <code>ONDE-PARAMOS</code> mandava buscar a lista completa no “relatório do "
        "conferente da leva”. Esse relatório nunca existiu — os 27 arquivos estão no "
        "disco e nenhum é do conferente. Esta é a primeira enumeração. E o piso é "
        "maior: cinco linhas aqui são <em>pacotes</em> (as oito frases do "
        "<code>./install.sh</code>, as 38 dicas dos 19 modos de gatilho, e mais três). "
        "Frase por frase, passa de cem.</p>"
    )
    P.append("</header>")

    P.append("<h2>As oito que mais mudam o que você vê</h2>")
    P.append(
        '<p class="secao-nota">Ranqueadas por uma régua só: a frase antiga levaria '
        "você a uma decisão errada, ou afirmava sobre o seu aparelho algo que o "
        "produto não tinha como saber.</p>"
    )
    P.append('<ol class="oito">')
    for x in t["as_oito_que_mais_mudam"]:
        P.append(f"<li>{_marca(x)}</li>")
    P.append("</ol>")

    P.append('<div class="barra" role="group" aria-label="Filtrar por aba">')
    P.append('<button data-f="todas" aria-pressed="true">todas</button>')
    for a in abas:
        curto = a["aba"].split(" —")[0].split(" (")[0]
        P.append(
            f'<button data-f="{e(a["aba"])}" aria-pressed="false">{e(curto)} '
            f'<span style="opacity:.6">{a["quantas"]}</span></button>'
        )
    P.append('<span class="placar" id="placar"></span>')
    P.append("</div>")

    i = 0
    for a in abas:
        P.append(f'<section data-aba="{e(a["aba"])}">')
        P.append(f'<h2>{e(a["aba"])} <span class="n">{a["quantas"]}</span></h2>')
        for m in a["mudancas"]:
            i += 1
            selo = "" if m["literal"] else '<span class="conferir">conferir no código</span>'
            P.append(f'<article class="item" data-id="f{i}" data-voto="">')
            P.append(f'<div class="onde"><span>{_marca(m["onde"])}</span>{selo}</div>')
            P.append('<div class="par">')
            P.append(
                f'<div class="lado saiu"><div class="rot">saiu</div>'
                f'<p class="frase">{_marca(m["saiu"])}</p></div>'
            )
            P.append(
                f'<div class="lado entrou"><div class="rot">entrou</div>'
                f'<p class="frase">{_marca(m["entrou"])}</p></div>'
            )
            P.append("</div>")
            P.append(
                f'<div class="porque"><p>{_marca(m["porque"])}</p>'
                '<span class="votos">'
                '<button data-v="sim" aria-pressed="false">boa</button>'
                '<button data-v="nao" aria-pressed="false">mexer</button></span></div>'
            )
            P.append("</article>")
        P.append("</section>")

    P.append(
        "<footer><p>Gerado por <code>scripts/gerar-frases-de-tela.py</code> a partir de "
        "<code>docs/process/dados/frases-de-tela-25-08.json</code>. Autocontido: abre "
        "com duplo clique, sem servidor e sem rede. O que você marcar fica guardado "
        "neste navegador — pode fechar e voltar.</p></footer>"
    )
    P.append(carimbo("scripts/gerar-frases-de-tela.py"))
    P.append("</div>")
    P.append(f"<script>{SCRIPT}</script></body></html>")
    return "\n".join(P) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="não escreve; rc=1 se o publicado divergir do que este script produz",
    )
    args = ap.parse_args()

    if not DADO.is_file():
        print(f"ERRO: o dado não está no disco: {DADO.relative_to(RAIZ)}", file=sys.stderr)
        return 1

    novo = construir()
    if args.check:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.is_file() else ""
        # O carimbo da casa sai dos dois lados: ele traz commit e hora, e um
        # `--check` que os enxergasse ficaria vermelho a cada commit.
        if sem_carimbo(atual) == sem_carimbo(novo):
            print(f"OK: {SAIDA.relative_to(RAIZ)} está em dia com o dado versionado.")
            return 0
        print(
            f"DIVERGE: {SAIDA.relative_to(RAIZ)} não é o que este script produz hoje.\n"
            "  Cure rodando: scripts/gerar-frases-de-tela.py",
            file=sys.stderr,
        )
        return 1

    # A PASTA DE SAÍDA É DO GERADOR, não de quem o chama — 25/08/2026.
    # As páginas mudaram para `html/`, e as árvores de brinquedo dos testes
    # copiam o gerador para um `tmp_path` onde essa pasta não existe. O erro
    # que sai daí é um `FileNotFoundError` de DIRETÓRIO, que não diz nada
    # sobre o que se testa. Quem sabe onde escreve sabe criar o lugar.
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(novo, encoding="utf-8")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(novo) // 1024} KB, sem rede e sem CDN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
