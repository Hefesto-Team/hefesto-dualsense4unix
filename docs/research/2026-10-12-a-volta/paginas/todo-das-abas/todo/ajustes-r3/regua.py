#!/usr/bin/env python3
# ruff: noqa: E501
"""A régua dos ajustes da rodada 3: mede as sete páginas tocadas em três tamanhos, sem janela na tela.

Uso: regua.py [--mordida] ; sai 0 se tudo passa. Cada falha vem com o seletor e o número.
Chrome sem janela (headless); nenhum clique no mouse dela.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TODO = Path(__file__).resolve().parent.parent
PAGINAS = {"03": "03-gatilhos.html", "04": "04-iluminacao.html", "05": "05-vibracao.html", "06": "06-navegacao.html",
           "07": "07-lancadores.html", "08": "08-conexoes.html", "10": "10-perfis.html"}
TAMANHOS = [(1212, 809), (1212, 740), (1918, 840)]
JS_EXEMPLO = ("(function(){var l=document.querySelector('.ext-lista');var k=l.querySelector('[data-modificacao=kyty]');"
              "var c=k.cloneNode(true);c.removeAttribute('data-modificacao');"
              "c.querySelector('.ext-nome').textContent='Exemplo da comunidade 1';var o=c.querySelector('.lanc-selo');"
              "o.textContent='Comunidade';o.className='lanc-selo comunidade';"
              "c.querySelector('.ext-faz').textContent='Uma linha de exemplo, só para medir a lista';"
              "c.querySelector('.nj-tog').className='nj-tog';c.querySelector('.nj-tog .txt').textContent='Desligada';"
              "l.appendChild(c);})()")

# Mede o que está visível: o JS roda dentro da página.
JS_MEDIR = r"""
(function(){
  function vis(e){var r=e.getBoundingClientRect();var s=getComputedStyle(e);
    if(r.width<1||r.height<1||s.visibility==='hidden'||s.display==='none'||+s.opacity===0)return false;
    for(var p=e.parentElement;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden')return false;}
    return true;}
  function nome(e){var c=(e.className&&e.className.baseVal===undefined?e.className:'').toString().trim().split(/\s+/).slice(0,2).join('.');
    return e.tagName.toLowerCase()+(c?'.'+c:'')+(e.id?'#'+e.id:'');}
  var out={rolagemV:[document.documentElement.scrollHeight,innerHeight],rolagemH:[document.documentElement.scrollWidth,innerWidth],
           cortes:[],pequenos:[],letrinhas:[],verdes:[]};
  var jan=document.querySelector('.janela');
  if(jan){out.janela=[Math.round(jan.getBoundingClientRect().bottom),innerHeight,jan.scrollHeight,jan.clientHeight];}
  document.querySelectorAll('*').forEach(function(e){
    if(!vis(e))return;
    if(e.closest('.fita-linha,.nota,svg,script,style'))return;
    var s=getComputedStyle(e);
    if(e!==document.body&&e!==document.documentElement&&(s.overflowY==='hidden'||s.overflowY==='auto'||s.overflowY==='scroll')&&e.scrollHeight>e.clientHeight+1&&!e.matches('textarea,select,pre'))
      out.cortes.push([nome(e),e.scrollHeight,e.clientHeight]);
    // o conteúdo que passa da borda do quadro sem rolar (overflow visível): a linha sai pela moldura
    if(e.matches('.quadro')&&s.overflowY==='visible'&&e.scrollHeight>e.clientHeight+1)
      out.cortes.push([nome(e)+' (transborda)',e.scrollHeight,e.clientHeight]);
    if(e.matches('button,select,input:not([type=hidden]):not([type=range]),a[href],.nj-tog,[role=button]')){var r=e.getBoundingClientRect();
      if(r.height<24||r.width<24)out.pequenos.push([nome(e),Math.round(r.width*10)/10,Math.round(r.height*10)/10,(e.textContent||'').trim().slice(0,18)]);}
    var tem=false;for(var n=e.firstChild;n;n=n.nextSibling)if(n.nodeType===3&&n.textContent.trim())tem=true;
    if(tem&&parseFloat(s.fontSize)<12)out.letrinhas.push([nome(e),s.fontSize,(e.textContent||'').trim().slice(0,18)]);
    [s.color,s.backgroundColor,s.borderTopColor].forEach(function(c,i){var m=c.match(/rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)/);
      if(!m)return;var r=+m[1],g=+m[2],b=+m[3],a=m[4]===undefined?1:+m[4];
      if(a>0.05&&g>r+35&&g>b+35&&g>120&&!(i===2&&parseFloat(s.borderTopWidth)===0))out.verdes.push([nome(e),['cor','fundo','borda'][i],c,(e.textContent||'').trim().slice(0,18)]);});
  });
  return out;})()
"""

# Grupos que têm de ter a mesma largura (diferença 0 px): [página, descrição, seletor, ... ]
JS_IGUAIS = r"""
(function(grupos){
  var out=[];grupos.forEach(function(g){
    var ws=[];document.querySelectorAll(g[1]).forEach(function(e){var r=e.getBoundingClientRect();if(r.width>0&&r.height>0)ws.push(Math.round(r.width*10)/10);});
    out.push([g[0],g[1],ws]);});return out;})
"""
IGUAIS = {
    "03": [["selects da força e os de cima, por controle", ".g2-forca-sel, .g2-cel .g2-acion, .g2-cel .g2-imersao"]],
    "05": [["os quatro passos", ".seg.passos > *"]],
    "07": [["Ligada e Desligada", ".ext-lista .nj-tog"],
           ["Identificar / Criar perfis / Configurar", ".lanc-fila .btn.mini:not(.lf-imped)"],
           ["botões do conserto no diálogo", "#impedimentos .imp-conserta, #impedimentos .imp-item .btn"]],
    "08": [["Usar como botões / Trazer de volta", "[data-r3='13'] .features .btn, [data-r3='14'] .features .btn"]],
}

# O que ela pediu, conferido no DOM: cada página devolve a lista do que falta (vazia = o pedido está ali).
JS_PEDIDO_BASE = r"""
(function(aba){
  function vis(e){var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
    for(var p=e;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden'||+t.opacity===0)return false;}return true;}
  function textos(sel){return [...document.querySelectorAll(sel)].filter(vis).map(function(e){return (e.textContent||'').trim();});}
  function tem(sel,txt){return textos(sel).some(function(t){return t.indexOf(txt)>=0;});}
  var falta=[];
  var jan=document.querySelector('.janela .miolo')||document.body;
  if(aba==='03'){var f=[...document.querySelectorAll('.g2-forca-sel')].filter(vis);
    if(f.length<2)falta.push('a força por controle sumiu');
    if(f.some(function(x){return x.options[0].text!=='Pelo estilo do jogo';}))falta.push('«Pelo estilo do jogo» não é a primeira escolha da força');}
  if(aba==='04'){if(tem('.miolo button, .miolo [role=button]','Desligar'))falta.push('o «Desligar» voltou aos efeitos');
    if(tem('.miolo .quadro-topo *, .miolo button, .miolo .nj-tog','Sem piscar'))falta.push('«Sem piscar» voltou como chave');
    [...document.querySelectorAll('.miolo select')].filter(vis).forEach(function(x){var o=[...x.options].map(function(y){return y.text;});
      if(o.indexOf('Sem efeito')<0||o.indexOf('Sem piscar')<0)falta.push('um seletor de efeito sem «Sem efeito» ou «Sem piscar»');});
    if(tem('.miolo *','Desconectado'))falta.push('a vaga sem controle mostra nome');}
  if(aba==='05'){if(tem('.miolo *','Criar efeitos novos'))falta.push('«Criar efeitos novos» voltou');
    if(tem('.miolo *','Desconectado'))falta.push('as vagas 3 e 4 mostram nome');}
  if(aba==='06'){var e=document.getElementById('nav-expl');if(!e||getComputedStyle(e).opacity!=='0')falta.push('a explicação aparece sem o mouse');
    if([...document.querySelectorAll('.miolo button, .miolo .ajuda, .miolo [aria-label=Explicar]')].filter(vis).some(function(x){return (x.textContent||'').trim()==='i';}))falta.push('o «i» voltou');}
  if(aba==='07'){var t=[...document.querySelectorAll('.quadro-titulo')].find(function(x){return x.textContent.trim()==='Lançadores';});
    var topo=t&&t.closest('.quadro-topo');if(!topo||topo.textContent.trim()!=='Lançadores')falta.push('o título dos Lançadores tem mais que o nome');
    if(tem('.miolo *','Detectar o jogo aberto')||tem('.miolo *','Procurar de novo'))falta.push('«Detectar» ou «Procurar de novo» voltou');
    var nomes=textos('.ext-lista .ext-nome').filter(function(x){return /Lovense/.test(x);});
    if(nomes.length!==1)falta.push('a Lovense não é uma extensão só ('+nomes.length+')');
    if([...document.querySelectorAll('.ext-lista [data-modificacao=intiface],.ext-lista [data-modificacao=lovense-celular],.ext-lista [data-modificacao=buttplug]')].filter(vis).length!==3)falta.push('faltam as três formas da Lovense');}
  if(aba==='10'){if([...document.querySelectorAll('[data-r3="19"]')].some(vis))falta.push('o campo do segundo controle voltou');}
  return falta;})
"""


def verde_permitido(pagina: str, item) -> bool:
    """Aviso verde é fundo verde ou texto verde com ✓/●/«ok». Fica de fora o que é controle ou tema:
    o toggle «Ligada», o botão Aplicar, as amostras de cor e os rótulos de campo."""
    nome, tipo, _cor, texto = item
    if pagina in ("03", "06", "08", "10"):
        return True
    if any(t in nome for t in ("nj-tog", "pino", "r-aplicar", "button.tom")) or nome == "span.txt":
        return True
    return tipo == "cor" and not any(g in texto.lower() for g in ("✓", "✔", "●", "ok"))


def medir(pw, mordida: str = "") -> int:
    falhas = 0
    nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for aba, arq in PAGINAS.items():
        for (w, h) in TAMANHOS:
            for exemplo in ([False, True] if aba == "07" else [False]):
                pg = nav.new_page(viewport={"width": w, "height": h})
                pg.goto(f"file://{TODO / arq}")
                pg.wait_for_timeout(500)
                if mordida:
                    pg.evaluate(mordida)
                if exemplo:
                    pg.evaluate(JS_EXEMPLO)
                m = pg.evaluate(JS_MEDIR)
                ruins = []
                if "janela" in m:
                    if m["janela"][0] > m["janela"][1] or m["janela"][2] > m["janela"][3] + 1:
                        ruins.append(f"a janela rola ou passa da tela {m['janela']}")
                elif m["rolagemV"][0] > m["rolagemV"][1]:
                    ruins.append(f"rolagem vertical {m['rolagemV']}")
                if m["rolagemH"][0] > m["rolagemH"][1]:
                    ruins.append(f"rolagem lateral {m['rolagemH']}")
                if aba in ("03", "04", "05", "07") and m["cortes"]:
                    ruins.append(f"corte por overflow {m['cortes'][:3]}")
                if aba in ("04", "05", "07"):
                    vs = [v for v in m["verdes"] if not verde_permitido(aba, v)]
                    if vs:
                        ruins.append(f"verde de aviso {vs[:4]}")
                for ig in pg.evaluate(JS_IGUAIS, IGUAIS.get(aba, [])):
                    if len(ig[2]) >= 2 and max(ig[2]) - min(ig[2]) > 0.5:
                        ruins.append(f"larguras diferentes em «{ig[0]}»: {sorted(set(ig[2]))}")
                if aba in ("04", "05", "07"):
                    if m["pequenos"]:
                        ruins.append(f"alvo < 24 px {m['pequenos'][:4]}")
                    m["letrinhas"] = [x for x in m["letrinhas"] if any(c.isalnum() for c in x[2])]
                    if m["letrinhas"]:
                        ruins.append(f"letra < 12 px {m['letrinhas'][:4]}")
                ruins += [f"o pedido: {x}" for x in pg.evaluate(JS_PEDIDO_BASE, aba)]
                rot = f"{aba} {w}x{h}" + (" +exemplo" if exemplo else "")
                if ruins:
                    falhas += len(ruins)
                    print(f"REPROVA {rot}: " + " | ".join(ruins))
                else:
                    print(f"ok      {rot}: rolagem {m.get('janela', m['rolagemV'])}, igualdade e verde conferidos")
                pg.close()
    nav.close()
    return falhas


if __name__ == "__main__":
    with sync_playwright() as pw:
        mordida = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--mordida" else ""
        f = medir(pw, mordida)
    print(json.dumps({"falhas": f}))
    sys.exit(1 if f else 0)
