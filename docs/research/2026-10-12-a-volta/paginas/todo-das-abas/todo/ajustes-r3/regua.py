#!/usr/bin/env python3
# ruff: noqa: E501
"""A régua dos ajustes da rodada 3 (com a volta 2): mede as sete páginas tocadas em três tamanhos, e os diálogos abertos, sem janela na tela.

Uso: regua.py [--mordida <nome|js>] ; sai 0 se tudo passa. As mordidas nomeadas estão em MORDIDAS. Cada falha vem com o seletor e o número.
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
# As mordidas: cada uma devolve um ajuste de propósito, e a régua tem de reprovar (a tentativa roda em todas as páginas, protegida).
def _m(corpo):
    return "(function(){try{" + corpo + "}catch(e){}})()"


MORDIDAS = {
    "terceira-linha": _m("var l=document.querySelector('.ext-lista');var k=l.querySelector('.ext');var c=k.cloneNode(true);"
                         "c.removeAttribute('data-modificacao');c.querySelector('.ext-nome').textContent='Exemplo da comunidade';l.appendChild(c);"),
    "aviso-laranja": _m("var f=document.querySelector('[data-lancador=steam] .lf-botoes');var a=document.createElement('a');"
                        "a.className='lf-imped btn mini';a.href='#impedimentos';a.textContent='2 com impedimento';f.parentNode.insertBefore(a,f);"),
    "forca-03": _m("var c=document.querySelector('.g2-canto');var d=document.createElement('div');d.className='g2-rot g2-rot-forca';"
                   "d.innerHTML='<span class=\"sec-rot\">Força do gatilho</span><select class=\"g2-forca-sel\"><option>Média</option></select>';"
                   "c.parentNode.appendChild(d);"),
    "botoes-05": _m("var m=document.querySelector('.vib .forca');var d=document.createElement('div');d.className='seg passos';"
                    "d.innerHTML='<button>Forte</button><button>Média</button><button>Fraca</button><button>Desligada</button>';m.insertBefore(d,m.firstChild);"),
    "texto-06": _m("var t=document.querySelector('.nav-topo');var d=document.createElement('div');d.id='nav-expl';"
                   "d.textContent='Aqui o controle vira mouse e teclado do computador: cada botão faz o que está na lista.';t.appendChild(d);"),
    "dialogo-alto": _m("var l=document.querySelector('#lovense .lv-linha');if(l){for(var i=0;i<6;i++)l.parentNode.appendChild(l.cloneNode(true));}"),
    "dialogo-botao": _m("var t=document.querySelector('#lovense .nj-tog');if(t)t.style.width='140px';"),
    "conf-botoes": _m("document.querySelectorAll('#lanc-conf .lc-val .btn.mini').forEach(function(b){b.style.width='auto';});"),
    "q1-desenho": _m("var c=document.querySelector('.g2-canto');var d=document.createElement('div');d.className='g2-leitura';"
                     "d.innerHTML='<b>L2</b><span data-leitura=l2>Metralhadora</span><b>R2</b><span data-leitura=r2>Arco de flecha</span>';c.appendChild(d);"),
    "q1-desconectado": _m("var c=document.querySelector('.g2-cab[data-controle=p3]');c.classList.remove('vazio');"
                          "c.innerHTML='<div class=cabeca><span><span class=\"chip vazio\">Galactic Purple <span class=pt>•</span> Desconectado</span></span></div>';"),
    "q1-cor": _m("document.querySelector('.g2-canto .sec-rot').style.color='#f8f8f2';"),
    "q2-para": _m("var p=document.querySelector('.ext[data-modificacao=lovense] .ext-para');p.innerHTML='<span class=ext-rot>Para</span>Todos';"),
    "q2-conta": _m("document.querySelector('#lovense .lv-linha:last-child .nj-tog').classList.add('ligado');"),
    "dica-passo": _m("var t=document.querySelector('.vib .forca input[type=range]');t.setAttribute('data-dica','Ajuste fino dentro do passo');"),
}

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
    "03": [["selects de acionamento e imersão", ".g2-cel .g2-acion, .g2-cel .g2-imersao"]],
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
  if(aba==='03'){
    if(document.querySelectorAll('.g2-forca-sel,.g2-rot-forca,.g2-gl-forca').length)falta.push('a linha «Força do gatilho» existe');
    if(tem('.miolo *','Força do gatilho'))falta.push('o texto «Força do gatilho» aparece');
    // as seis respostas, q1: a célula à esquerda dos controles tem só «Controle» e «Estilo de jogo: …», e os desconectados não aparecem
    var cn=document.querySelector('.g2-canto');
    if(!cn||!vis(cn))falta.push('a célula à esquerda dos controles sumiu');
    else{var tx=[...cn.children].map(function(x){return x.textContent.trim();}).join(' ');
      if(cn.children.length!==2||!/^Controle Estilo de jogo: \S+$/.test(tx))falta.push('a célula da esquerda não diz só «Controle» e «Estilo de jogo: …»: «'+tx.slice(0,50)+'»');
      if(cn.querySelector('svg,[data-leitura],.g2-leitura')||/\b[LR]2\b/.test(tx))falta.push('o desenho ou a leitura do L2 e R2 voltou à célula da esquerda');
      if(cn.querySelector('button,select,input,a'))falta.push('a célula da esquerda virou controle (tem de ser só leitura)');
      var rc=cn.querySelector('.sec-rot'),es=cn.querySelector('.g2-estilo'),ro=document.querySelector('.g2-rot .sec-rot');
      if(!rc||!/^Controle$/.test(rc.textContent.trim()))falta.push('«Controle» não tem a letra dos rótulos de linha');
      else if(getComputedStyle(rc).color!==getComputedStyle(ro).color)falta.push('«Controle» não tem a cor verde dos rótulos de linha');
      if(es&&getComputedStyle(es).color!==getComputedStyle(document.querySelector('.g2-acion')).color)falta.push('«Estilo de jogo» não está em branco');
      [rc,es].forEach(function(x){if(x&&ro&&Math.abs(x.getBoundingClientRect().left-ro.getBoundingClientRect().left)>1.5)falta.push('a linha «'+x.textContent.trim().slice(0,14)+'» não começa na borda dos rótulos de baixo');
        if(x&&x.getBoundingClientRect().right>document.querySelector('.g2-cab').getBoundingClientRect().left-4)falta.push('a linha «'+x.textContent.trim().slice(0,14)+'» encosta no chip');});}
    var cabs=[...document.querySelectorAll('.g2-cab')].filter(vis);
    if(cabs.some(function(c){return /Desconectado/.test(c.textContent)||c.querySelector('.chip.vazio');}))falta.push('um controle desconectado aparece na linha do alto');
    if(cabs.filter(function(c){return c.querySelector('.chip');}).length!==2)falta.push('a linha do alto não tem os dois controles conectados');
    // as colunas seguem a grade: cada chip na borda da coluna dele embaixo
    ['p1','p2'].forEach(function(k){var ch=document.querySelector('.g2-cab[data-controle='+k+'] .chip'),ce=document.querySelector('.g2-cel[data-controle='+k+']');
      if(ch&&ce){var a=ch.getBoundingClientRect(),c=ce.getBoundingClientRect();if(Math.abs(a.left-c.left)>1||Math.abs(a.width-c.width)>1)falta.push('o chip '+k+' desalinhou da coluna de baixo');}});
    var ca=document.querySelector('.modo-auto');if(ca){ca.click();if(!vis(cn)||!/Estilo de jogo: \S/.test(cn.textContent))falta.push('com o Modo automático, a leitura do estilo some');ca.click();}}
  if(aba==='04'){if(tem('.miolo button, .miolo [role=button]','Desligar'))falta.push('o «Desligar» voltou aos efeitos');
    if(tem('.miolo .quadro-topo *, .miolo button, .miolo .nj-tog','Sem piscar'))falta.push('«Sem piscar» voltou como chave');
    [...document.querySelectorAll('.miolo select')].filter(vis).forEach(function(x){var o=[...x.options].map(function(y){return y.text;});
      if(o.indexOf('Sem efeito')<0||o.indexOf('Sem piscar')<0)falta.push('um seletor de efeito sem «Sem efeito» ou «Sem piscar»');});
    if(tem('.miolo *','Desconectado'))falta.push('a vaga sem controle mostra nome');}
  if(aba==='05'){if(tem('.miolo *','Criar efeitos novos'))falta.push('«Criar efeitos novos» voltou');
    if(tem('.miolo *','Desconectado'))falta.push('as vagas 3 e 4 mostram nome');
    if(document.querySelectorAll('.vib .seg').length)falta.push('há botões de passo na vibração (.seg)');
    if(['Forte','Média','Fraca','Desligada'].some(function(t){return textos('.vib button').some(function(x){return x===t;});}))falta.push('um dos quatro botões da força voltou');
    var gl=[...document.querySelectorAll('.glifo-forca')].filter(vis);
    if(gl.length<2)falta.push('o ícone da força sumiu');
    if(gl.some(function(g){return g.querySelector('path.casco,path.vibra,path.onda');}))falta.push('o ícone da força é o controle genérico de antes');
    if(gl.some(function(g){return !g.querySelector('svg rect');}))falta.push('o ícone da força não tem o touchpad do DualSense');
    if([...document.querySelectorAll('.vib .forca [data-dica]')].some(function(x){return /passo/i.test(x.getAttribute('data-dica'));}))falta.push('a dica da força ainda fala do passo que saiu');
    var ln=[...document.querySelectorAll('.vib .forca > .motor')].filter(vis);
    if(!ln.length||ln.some(function(m){return !m.querySelector('input[type=range]');}))falta.push('a força não é só o trilho');}
  if(aba==='06'){var tp=document.querySelector('.nav-topo');
    if(!tp||tp.textContent.replace(/\s+/g,' ').trim()!=='Navegação')falta.push('o título da Navegação tem texto além do nome: «'+(tp?tp.textContent.replace(/\s+/g,' ').trim().slice(0,40):'')+'»');
    if(document.getElementById('nav-expl'))falta.push('a faixa de explicação existe');
    var nt=tp&&tp.querySelector('.quadro-titulo');
    if(!nt||!nt.getAttribute('data-dica')||nt.getAttribute('tabindex')!=='0')falta.push('a dica sobre «Navegação» não existe (data-dica e foco)');
    if([...document.querySelectorAll('.miolo button, .miolo .ajuda, .miolo [aria-label=Explicar]')].filter(vis).some(function(x){return (x.textContent||'').trim()==='i';}))falta.push('o «i» voltou');}
  if(aba==='07'){var t=[...document.querySelectorAll('.quadro-titulo')].find(function(x){return x.textContent.trim()==='Lançadores';});
    var topo=t&&t.closest('.quadro-topo');if(!topo||topo.textContent.trim()!=='Lançadores')falta.push('o título dos Lançadores tem mais que o nome');
    if(tem('.miolo *','Detectar o jogo aberto')||tem('.miolo *','Procurar de novo'))falta.push('«Detectar» ou «Procurar de novo» voltou');
    var ls=[...document.querySelectorAll('.ext-lista > .ext')];
    if(ls.length!==2)falta.push('a lista tem '+ls.length+' linhas de extensão (têm de ser 2)');
    var nm=ls.map(function(x){return (x.querySelector('.ext-nome')||{}).textContent;});
    if(nm.join('|')!=='Kyty|Lovense')falta.push('as duas extensões não são Kyty e Lovense: '+nm.join('|'));
    if(textos('.ext-lista .ext-nome').some(function(x){return /Intiface|celular|brinquedo|Exemplo/.test(x);}))falta.push('uma forma da Lovense ou a linha de exemplo está na lista');
    if(ls.some(function(x){return ['.ext-nome','.lanc-selo','.ext-ver','.ext-faz','.ext-para','.nj-tog','.ext-conf'].some(function(q){return !x.querySelector(q);});}))falta.push('uma linha de extensão não segue o formato (nome, selo, versão, descrição, Para, chave, engrenagem)');
    if(document.querySelector('.lf-imped')||tem('.lanc-fila *','com impedimento'))falta.push('o aviso laranja de impedimento está na linha da Steam');
    var lv=document.querySelector('#lovense');
    if(!lv||lv.querySelectorAll('.lv-linha').length!==3)falta.push('o diálogo da Lovense não tem as três formas');
    else if([...lv.querySelectorAll('.lv-linha')].some(function(x){return !x.querySelector('.nj-tog')||!x.querySelector('.lv-para select');}))falta.push('uma forma da Lovense sem chave ou sem Para');
    else if([...lv.querySelectorAll('.lv-linha')].slice(0,2).some(function(x){return !x.querySelector('.lv-quando select');}))falta.push('Pelo Intiface e Pelo celular sem Quando');
    var eg=document.querySelector('.ext[data-modificacao=lovense] .ext-conf');if(!eg||eg.getAttribute('href')!=='#lovense')falta.push('a engrenagem da Lovense não abre o diálogo das três formas');
    // as seis respostas, q2: a linha da Lovense diz quantas formas estão ligadas, e não «Para»; o Kyty segue com «Para Todos»
    var pl=document.querySelector('.ext[data-modificacao=lovense] .ext-para'),pk=document.querySelector('.ext[data-modificacao=kyty] .ext-para');
    var nlv=document.querySelectorAll('#lovense .lv-linha .nj-tog.ligado').length,tlv=document.querySelectorAll('#lovense .lv-linha .nj-tog').length;
    if(!pl||pl.textContent.trim()!==nlv+' de '+tlv+' ligadas')falta.push('a linha da Lovense não diz «'+nlv+' de '+tlv+' ligadas»: «'+(pl?pl.textContent.trim():'')+'»');
    if(pl&&/Para/.test(pl.textContent))falta.push('a linha da Lovense ainda diz «Para»');
    if(!pk||pk.textContent.replace(/\s+/g,'')!=='ParaTodos')falta.push('o Kyty perdeu o «Para Todos»');
    if(pl&&pk){var a1=pl.getBoundingClientRect(),a2=pk.getBoundingClientRect(),f1=getComputedStyle(pl.lastElementChild||pl),f2=getComputedStyle(pk);
      if(Math.abs(a1.left-a2.left)>0.5)falta.push('«'+pl.textContent.trim()+'» não fica no lugar do «Para»');
      if(f1.fontSize!==f2.fontSize||f1.fontFamily!==f2.fontFamily||f1.color!==f2.color)falta.push('a contagem da Lovense não tem a letra do «Todos»');}
    var cf=document.querySelector('#lanc-conf a[href="#impedimentos"]');if(!cf)falta.push('o Configurar da Steam não leva aos impedimentos');}
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


# Os diálogos abertos (pelo #âncora): nada rola dentro, nada passa da tela, alvos de 24 px e letra de 12 px.
DIALOGOS = {"07": ["lovense", "impedimentos", "lanc-conf"]}
JS_DIALOGO = r"""
(function(id){
  var cx=document.querySelector('#'+id+' .tn-cx');if(!cx)return {erro:'sem diálogo'};
  var r=cx.getBoundingClientRect(),out={topo:Math.round(r.top),base:Math.round(r.bottom),esq:Math.round(r.left),dir:Math.round(r.right),
    iw:innerWidth,ih:innerHeight,rolagem:[],pequenos:[],letrinhas:[],verdes:[],igual:[]};
  function vis(e){var q=e.getBoundingClientRect();return q.width>=1&&q.height>=1;}
  cx.querySelectorAll('*').forEach(function(e){
    if(!vis(e)||e.closest('svg'))return;var s=getComputedStyle(e);
    if(e.scrollHeight>e.clientHeight+1&&(s.overflowY==='auto'||s.overflowY==='scroll'||s.overflowY==='hidden')&&!e.matches('select,textarea'))
      out.rolagem.push([e.tagName.toLowerCase()+'.'+(e.className||'').toString().split(' ')[0],e.scrollHeight,e.clientHeight]);
    if(e.matches('button,select,input:not([type=range]),a[href],.nj-tog')){var q=e.getBoundingClientRect();
      if(q.height<24||q.width<24)out.pequenos.push([e.className||e.tagName,Math.round(q.width),Math.round(q.height)]);}
    var tem=false;for(var n=e.firstChild;n;n=n.nextSibling)if(n.nodeType===3&&n.textContent.trim())tem=true;
    if(tem&&parseFloat(s.fontSize)<12)out.letrinhas.push([e.className||e.tagName,s.fontSize,(e.textContent||'').trim().slice(0,18)]);
    [s.color,s.backgroundColor].forEach(function(c,i){var m=c.match(/rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)/);if(!m)return;
      var R=+m[1],G=+m[2],B=+m[3],A=m[4]===undefined?1:+m[4];
      if(A>0.05&&G>R+35&&G>B+35&&G>120&&!e.closest('.nj-tog')&&!e.matches('.ext-rot,.ext-rot *'))out.verdes.push([e.className||e.tagName,i?'fundo':'cor',c]);});
  });
  var ws=[];cx.querySelectorAll('.nj-tog').forEach(function(e){ws.push(Math.round(e.getBoundingClientRect().width*10)/10);});out.igual=ws;
  var bs=[];cx.querySelectorAll('.lc-val .btn.mini').forEach(function(e){bs.push(Math.round(e.getBoundingClientRect().width*10)/10);});out.botoes=bs;
  var gs=[];cx.querySelectorAll('.lv-linha .ext-conf').forEach(function(e){gs.push(Math.round(e.getBoundingClientRect().width*10)/10);});out.engr=gs;
  return out;})
"""


def medir_dialogos(nav, mordida: str) -> int:
    falhas = 0
    for aba, ids in DIALOGOS.items():
        for did in ids:
            for (w, h) in TAMANHOS:
                pg = nav.new_page(viewport={"width": w, "height": h})
                pg.goto(f"file://{TODO / PAGINAS[aba]}#{did}")
                pg.wait_for_timeout(400)
                if mordida:
                    pg.evaluate(mordida)
                d = pg.evaluate(JS_DIALOGO, did)
                ruins = []
                if "erro" in d:
                    ruins.append(d["erro"])
                else:
                    if d["rolagem"]:
                        ruins.append(f"o diálogo rola ou corta por dentro {d['rolagem'][:3]}")
                    if d["topo"] < 0 or d["base"] > d["ih"] or d["esq"] < 0 or d["dir"] > d["iw"]:
                        ruins.append(f"o diálogo passa da tela {[d['topo'], d['base'], d['esq'], d['dir']]} em {d['iw']}x{d['ih']}")
                    if d["pequenos"]:
                        ruins.append(f"alvo < 24 px {d['pequenos'][:3]}")
                    if d["letrinhas"]:
                        ruins.append(f"letra < 12 px {d['letrinhas'][:3]}")
                    if d["verdes"]:
                        ruins.append(f"verde de aviso {d['verdes'][:3]}")
                    if len(d["igual"]) >= 2 and max(d["igual"]) - min(d["igual"]) > 0.5:
                        ruins.append(f"as chaves do diálogo têm larguras diferentes {sorted(set(d['igual']))}")
                    if did == "lanc-conf" and len(d.get("botoes", [])) >= 2 and max(d["botoes"]) - min(d["botoes"]) > 0.5:
                        ruins.append(f"os botões da coluna da direita têm larguras diferentes {sorted(set(d['botoes']))}")
                    if len(d.get("engr", [])) >= 2 and max(d["engr"]) - min(d["engr"]) > 0.5:
                        ruins.append(f"as engrenagens do diálogo têm larguras diferentes {sorted(set(d['engr']))}")
                rot = f"{aba} #{did} {w}x{h}"
                if ruins:
                    falhas += len(ruins)
                    print(f"REPROVA {rot}: " + " | ".join(ruins))
                else:
                    print(f"ok      {rot}: sem rolagem, dentro da tela, alvos e letra conferidos")
                pg.close()
    return falhas


def medir_dica_da_navegacao(nav, mordida: str) -> int:
    """A dica da Navegação: aparece com o mouse sobre o nome e com o foco, e some ao sair."""
    falhas = 0
    pg = nav.new_page(viewport={"width": 1212, "height": 809})
    pg.goto(f"file://{TODO / PAGINAS['06']}")
    pg.wait_for_timeout(400)
    if mordida:
        pg.evaluate(mordida)
    ruins = []
    try:
        pg.hover(".nav-topo .quadro-titulo", timeout=3000)
        pg.wait_for_timeout(300)
        if not pg.evaluate("document.getElementById('hef-dica').classList.contains('visivel')"):
            ruins.append("a dica não aparece com o mouse sobre «Navegação»")
        elif "Quem navega" not in pg.evaluate("document.getElementById('hef-dica').textContent"):
            ruins.append("a dica não traz a explicação")
        pg.mouse.move(600, 790)
        pg.wait_for_timeout(300)
        if pg.evaluate("document.getElementById('hef-dica').classList.contains('visivel')"):
            ruins.append("a dica não some ao sair")
        pg.focus(".nav-topo .quadro-titulo")
        pg.wait_for_timeout(300)
        if not pg.evaluate("document.getElementById('hef-dica').classList.contains('visivel')"):
            ruins.append("a dica não aparece com o foco do teclado")
    except Exception as e:
        ruins.append(f"não consegui passar o mouse no nome: {str(e)[:60]}")
    if ruins:
        falhas += len(ruins)
        print("REPROVA 06 dica: " + " | ".join(ruins))
    else:
        print("ok      06 dica: aparece no mouse e no foco, some ao sair")
    pg.close()
    return falhas


def medir(pw, mordida: str = "") -> int:
    falhas = 0
    nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for aba, arq in PAGINAS.items():
        for (w, h) in TAMANHOS:
            for exemplo in [False]:
                pg = nav.new_page(viewport={"width": w, "height": h})
                pg.goto(f"file://{TODO / arq}")
                pg.wait_for_timeout(500)
                if mordida:
                    pg.evaluate(mordida)
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
    falhas += medir_dialogos(nav, mordida)
    falhas += medir_dica_da_navegacao(nav, mordida)
    nav.close()
    return falhas


if __name__ == "__main__":
    with sync_playwright() as pw:
        mordida = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--mordida" else ""
        mordida = MORDIDAS.get(mordida, mordida)
        f = medir(pw, mordida)
    print(json.dumps({"falhas": f}))
    sys.exit(1 if f else 0)
