#!/usr/bin/env python3
# ruff: noqa: E501
"""A régua dos ajustes da rodada 4: mede as quatro páginas tocadas em três tamanhos e a página de conferência, sem janela na tela.

Uso: regua.py [--mordida <nome|js>] ; sai 0 se tudo passa. As mordidas nomeadas estão em MORDIDAS; cada uma devolve
de propósito algo que ela mandou tirar, e a régua tem de reprovar. A página de conferência grava num servidor de
mentira (page.route): a régua nunca escreve no arquivo de respostas de verdade.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

R4 = Path(__file__).resolve().parent.parent
PAGINAS = {
    "01": "01-jogar.html",
    "02": "02-controles.html",
    "07": "07-lancadores.html?aba=t2#acessorios",
    "calibrar": "calibrar-sensores.html",
}
TAMANHOS = [(1212, 809), (1212, 740), (1918, 840)]
REGIAO = {
    "01": "[data-controle]",
    "02": ".ctl > .faixa, .ctl[data-conectado=nao]",
    "07": "#acessorios .ja-tela.t2",
    "calibrar": "body",
}


def _m(corpo):
    return "(function(){try{" + corpo + "}catch(e){}})()"


MORDIDAS = {
    "zona-01": _m("var c=document.querySelector('[data-controle=p1] [data-gesto=mascara]');var d=document.createElement('div');d.className='jv';"
                  "d.setAttribute('data-todo','12');d.setAttribute('data-dica','O que o jogo enxerga');d.textContent='O jogo vê: Sony DualSense';c.parentNode.appendChild(d);"),
    "botao-02": _m("var f=document.querySelector('.ctl[data-conectado=sim] > .faixa, .ctl:not([data-conectado=nao]) > .faixa');var b=document.createElement('button');"
                   "b.className='jv-btn';b.setAttribute('data-todo','17');b.textContent='O que chega';f.appendChild(b);"),
    "vaga-02": _m("var f=document.querySelector('.ctl[data-conectado=nao] > .faixa');var s=document.createElement('span');s.className='card-nome';"
                  "s.textContent=' Galactic Purple';f.querySelector('.card-nome').appendChild(s);"),
    "q4-player-02": _m("var p=document.querySelector('.ctl[data-conectado=nao] [data-campo=peca]');p.textContent='Player 3';"),
    "lista-07": _m("var l=document.querySelector('.ext-lista');var j=document.querySelector('[data-todo=\"34\"]');l.appendChild(j);"),
    "legenda-07": _m("var g=document.querySelector('.fz-grade');var s=document.createElement('span');s.className='fz-leg';s.textContent='dois motores';g.appendChild(s);"),
    "letra-07": _m("document.querySelectorAll('.ja-tela.t2 .pc-sub').forEach(function(x){x.style.fontSize='11px';});"),
    "largura-07": _m("document.querySelector('.ja-tela.t2 .t2-segue .ja-op').style.width='70%';"),
    "nome-calibrar": _m("var m=document.querySelector('.mira');var s=document.createElement('span');s.className='quem';s.textContent='Vitória';m.insertBefore(s,m.firstChild);"),
    "q4-player-calibrar": _m("var b=document.querySelector('.controles > .lugar b');b.textContent='Player 3';"),
    "q5-selo": _m("document.querySelectorAll('.mira').forEach(function(m){var d=document.createElement('div');d.className='mira-topo leitura';"
                  "d.innerHTML='<span class=selo-av><span class=p></span>Giroscópio como analógico: desligado</span>';m.insertBefore(d,m.firstChild);});"),
    "q6-rotulo": _m("document.querySelectorAll('.mira .desl[data-seis=q6] .r').forEach(function(r){r.textContent='Só enquanto eu segurar';});"),
    "q6-opcoes": _m("document.querySelectorAll('select[data-gesto=mira-segurar]').forEach(function(x){var o=document.createElement('option');o.text='Cruz';x.add(o);});"),
    "barra-calibrar": _m("document.querySelectorAll('.lin > .r').forEach(function(x){x.style.flex='0 0 82px';});"),
    "c3-textao": _m("document.querySelectorAll('.chip-virtual>.sw').forEach(function(b){b.lastChild.textContent='Usar giroscópio como analógico';});"),
    "c3-largura": _m("var b=document.querySelector('.chip-virtual>.sw');b.style.width='80%';"),
    "c3-pula": _m("var st=document.createElement('style');st.textContent='.chip-virtual.on>.sw{height:34px!important}';document.head.appendChild(st);"),
    "n4-sempre-mostra": _m("var st=document.createElement('style');st.textContent='.desl .mira-quando .mira-botao{display:block!important}';document.head.appendChild(st);"),
    "n4-outra-linha": _m("var st=document.createElement('style');st.textContent='.desl .mira-quando .mira-botao{grid-row:2!important;grid-column:1/-1!important}';document.head.appendChild(st);"),
    "n4-sem-botoes": _m("document.querySelectorAll('.mira-botao').forEach(function(x){x.remove(x.options.length-1);});"),
    "n4-nome-corta": _m("document.querySelectorAll('.mira-botao option').forEach(function(o){if(o.title)o.textContent=o.title;});"),
    "conta-calibrar": _m("var a=document.querySelector('.rodape .acoes');var s=document.createElement('span');s.className='quantos';s.textContent='2 controles conectados';a.parentNode.insertBefore(s,a);"),
}

JS_MEDIR = r"""
(function(reg){
  function vis(e){var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
    for(var p=e;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden'||+t.opacity===0)return false;}return true;}
  function nome(e){var c=(typeof e.className==='string'?e.className:'').trim().split(/\s+/).slice(0,2).join('.');
    return e.tagName.toLowerCase()+(c?'.'+c:'')+(e.id?'#'+e.id:'');}
  var out={rolagemV:[document.documentElement.scrollHeight,innerHeight],rolagemH:[document.documentElement.scrollWidth,innerWidth],
           cortes:[],pequenos:[],letrinhas:[],verdes:[]};
  var jan=document.querySelector('.janela');
  if(jan){out.janela=[Math.round(jan.getBoundingClientRect().bottom),innerHeight,jan.scrollHeight,jan.clientHeight];}
  var vistos=new Set();
  document.querySelectorAll(reg).forEach(function(raiz){[raiz].concat([...raiz.querySelectorAll('*')]).forEach(function(e){
    if(vistos.has(e)||!vis(e)||e.closest('svg,script,style'))return;vistos.add(e);
    var s=getComputedStyle(e);
    if((s.overflowY==='hidden'||s.overflowY==='auto'||s.overflowY==='scroll')&&e.scrollHeight>e.clientHeight+1&&!e.matches('textarea,select,body,html'))
      out.cortes.push([nome(e),e.scrollHeight,e.clientHeight]);
    if(e.matches('button,select,input:not([type=hidden]),a[href],.nj-tog,[role=button]')){
      // a caixa de marcar dentro de um rótulo conta pela linha inteira, que é onde se clica
      var alvo=e.matches('input[type=checkbox],input[type=radio]')&&e.closest('label')?e.closest('label'):e;
      var r=alvo.getBoundingClientRect();
      if(r.height<24||r.width<24)out.pequenos.push([nome(alvo),Math.round(r.width*10)/10,Math.round(r.height*10)/10,(alvo.textContent||'').trim().slice(0,18)]);}
    var tem=false;for(var n=e.firstChild;n;n=n.nextSibling)if(n.nodeType===3&&/[0-9A-Za-zÀ-ú]/.test(n.textContent))tem=true;
    if(tem&&parseFloat(s.fontSize)<12)out.letrinhas.push([nome(e),s.fontSize,(e.textContent||'').trim().slice(0,18)]);
    [s.color,s.backgroundColor,s.borderTopColor].forEach(function(c,i){var m=c.match(/rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)/);
      if(!m)return;var r=+m[1],g=+m[2],b=+m[3],a=m[4]===undefined?1:+m[4];
      if(a>0.05&&g>r+35&&g>b+35&&g>120&&!(i===2&&parseFloat(s.borderTopWidth)===0))out.verdes.push([nome(e),['cor','fundo','borda'][i],c,(e.textContent||'').trim().slice(0,18)]);});
  });});
  return out;})
"""

JS_IGUAIS = r"""
(function(grupos){
  return grupos.map(function(g){var ws=[];document.querySelectorAll(g[1]).forEach(function(e){var r=e.getBoundingClientRect();
    if(r.width>0&&r.height>0)ws.push(Math.round((g[2]==='altura'?r.height:r.width)*10)/10);});return [g[0],g[1],ws];});})
"""
IGUAIS = {
    "01": [],
    "02": [["os quatro cartões", ".ctl"], ["os botões «Mira virtual»", ".chip-virtual>.sw"]],
    "07": [["O que os acessórios seguem", ".ja-tela.t2 .t2-segue .ja-op"],
           ["Como os três tocam juntos", ".ja-tela.t2 .t2-juntos .ja-op"],
           ["as opções das duas molduras de cima", ".ja-tela.t2 .ja-op"],
           ["as quatro molduras", ".ja-tela.t2 > .moldura"],
           ["a altura das molduras de cima", ".ja-tela.t2 > .t2-segue, .ja-tela.t2 > .t2-juntos", "altura"],
           ["a altura das molduras de baixo", ".ja-tela.t2 > .t2-jogos, .ja-tela.t2 > .t2-forca", "altura"],
           ["os nove deslizantes", ".fz-c input[type=range]"],
           ["as linhas dos jogos", ".jg-l"]],
    "calibrar": [["os quatro lugares", ".controles > .ctr, .controles > .lugar, .grade > .lugar"]],
}

JS_PEDIDO = r"""
(function(aba){
  function vis(e){var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
    for(var p=e;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden'||+t.opacity===0)return false;}return true;}
  function txt(e){return (e.innerText||'').replace(/\s+/g,' ').trim();}
  function visivelCom(re){return [...document.querySelectorAll('body *')].filter(function(e){return vis(e)&&!e.closest('script,style')&&
    [...e.childNodes].some(function(n){return n.nodeType===3&&re.test(n.textContent);});}).map(function(e){return e.tagName.toLowerCase()+'.'+(e.className||'');});}
  var falta=[];
  if(aba==='01'){
    if(document.querySelector('.jv,[data-aba="o-jogo-ve-r4"],[data-todo-css="o-jogo-ve-r4"]'))falta.push('a zona «O jogo vê» existe');
    var v=visivelCom(/O jogo vê/);if(v.length)falta.push('o texto «O jogo vê» aparece em '+v.slice(0,2));
    if(document.querySelector('[data-todo="12"][data-dica]'))falta.push('a dica da zona voltou');
    if(document.querySelectorAll('[data-gesto=mascara]').length<2)falta.push('a seleção da forma sumiu dos cartões');}
  if(aba==='02'){
    if(document.querySelector('.jv-btn,#jv-pop,[data-todo="17"]'))falta.push('o bloco «O que chega» existe');
    var c=visivelCom(/O que chega/);if(c.length)falta.push('o texto «O que chega» aparece em '+c.slice(0,2));
    var des=[...document.querySelectorAll('.ctl[data-conectado=nao] > .faixa')];
    if(des.length!==2)falta.push('há '+des.length+' faixas de controle desconectado (têm de ser 2)');
    // as seis respostas, q4: a vaga sem controle diz só «P3 • Desconectado» (a letra e o número)
    des.forEach(function(f){var t=txt(f);if(!/^P\d • Desconectado$/.test(t))falta.push('a vaga sem controle não diz «P<n> • Desconectado»: «'+t.slice(0,60)+'»');});
    if(visivelCom(/Player/).length)falta.push('uma vaga diz «Player» em '+visivelCom(/Player/).slice(0,2));
    [...document.querySelectorAll('.ctl[data-conectado=nao]')].forEach(function(k){if(/Galactic Purple|White|Cosmic Red|Starlight Blue/.test(txt(k)))falta.push('o desconectado tem cor de plástico');
      if([...k.querySelectorAll('button,select,input,.mic,.bat,[data-campo=bateria]')].some(vis))falta.push('o desconectado tem controle ou dado visível');});
    // c3 (v3): os dois botões sob os analógicos dizem só «Mira virtual», com a mesma largura e a mesma altura, e nada pula
    var mv=[...document.querySelectorAll('.chip-virtual>.sw')].filter(vis);
    if(mv.length<2)falta.push('os botões da mira virtual sumiram');
    mv.forEach(function(b){var t=txt(b),r=b.getBoundingClientRect();if(t!=='Mira virtual')falta.push('um botão da mira diz «'+t.slice(0,40)+'»');
      if(r.height<24)falta.push('o botão da mira tem '+Math.round(r.height)+' px de altura');
      if(parseFloat(getComputedStyle(b).fontSize)<12)falta.push('o botão da mira tem letra de '+getComputedStyle(b).fontSize);
      if(!b.getAttribute('data-dica'))falta.push('o botão da mira perdeu a dica');});
    if(mv.length>=2){var hs=mv.map(function(b){return b.getBoundingClientRect().height;});if(Math.max.apply(null,hs)-Math.min.apply(null,hs)>0.5)falta.push('os botões da mira têm alturas diferentes '+hs);}
    if(visivelCom(/giroscópio como analógico/i).length)falta.push('o texto «Usar giroscópio como analógico» aparece');
    var cv=[...document.querySelectorAll('.chip-virtual')],mede=function(){return [...document.querySelectorAll('.ctl')].map(function(k){return Math.round(k.getBoundingClientRect().height*10);}).concat(mv.map(function(b){return Math.round(b.getBoundingClientRect().height*10);}));};
    var h0=mede();cv.forEach(function(c){c.classList.toggle('on');});var h1=mede();cv.forEach(function(c){c.classList.toggle('on');});
    if(h0.join()!==h1.join())falta.push('ligar ou desligar a mira virtual muda a altura do bloco');}
  if(aba==='07'){
    var ac=document.querySelector('#acessorios');
    [['34','os jogos'],['35','a força']].forEach(function(p){var e=document.querySelector('[data-todo="'+p[0]+'"]');
      if(!e)falta.push(p[1]+' sumiu');else{if(!ac||!ac.contains(e))falta.push(p[1]+' fora do diálogo da engrenagem');
        if(e.closest('.ext-lista'))falta.push(p[1]+' está na lista de extensões');}});
    var eg=document.querySelector('.ext-lista .ext-conf[href="#acessorios"]');if(!eg)falta.push('a engrenagem da lista não abre o diálogo');
    if(!document.querySelector('#t2:checked'))falta.push('a aba «O que seguem» não abriu');
    var t2=document.querySelector('.ja-tela.t2');
    if(t2){if(t2.querySelector('.jg-nota'))falta.push('a frase «Nenhum jogo marcado» voltou');
      if(/dois motores|um motor|\/20/.test(txt(t2.querySelector('.fz-grade')||t2)))falta.push('as legendas ou o «/20» voltaram na força');
      if([...t2.querySelectorAll('.ja-op')].some(function(o){return [...o.querySelectorAll('.ja-op-txt > :not(b)')].some(vis);}))falta.push('uma opção tem descrição visível além do nome');
      if(t2.querySelectorAll('.jg-l input[type=checkbox]').length!==5)falta.push('a lista não tem os cinco jogos');
      if(t2.querySelectorAll('.fz-c input[type=range]').length!==9)falta.push('a força não tem os nove deslizantes');
      if(t2.scrollHeight>t2.clientHeight+1)falta.push('a aba rola por dentro');}
    else falta.push('a aba «O que seguem» sumiu');}
  if(aba==='calibrar'){
    if(document.querySelector('.mira .quem,[data-campo=quem-joga].quem'))falta.push('o nome repetido em cima da mira voltou');
    if(document.querySelector('.quantos'))falta.push('a contagem do rodapé voltou');
    var q=visivelCom(/controles? conectados?/);if(q.length)falta.push('«controles conectados» aparece');
    var lg=[...document.querySelectorAll('.controles > .lugar, .grade > .lugar')];
    if(lg.length!==2)falta.push('há '+lg.length+' vagas sem controle (têm de ser 2)');
    // as seis respostas, q4: a vaga sem controle diz «P3 • Desconectado»; nenhuma vaga diz «Player»
    lg.forEach(function(l){var t=txt(l);if(!/^P\d • Desconectado$/.test(t))falta.push('a vaga diz «'+t.slice(0,40)+'»');});
    if(visivelCom(/Player/).length)falta.push('uma vaga diz «Player» em '+visivelCom(/Player/).slice(0,2));
    var ctr=document.querySelector('.ctr');if(ctr&&parseFloat(getComputedStyle(ctr).rowGap)<8)falta.push('o respiro apertado da rodada 4 voltou (gap '+getComputedStyle(ctr).rowGap+')');
    // q5: sai o selo «Giroscópio como analógico: desligado»; os números das barras ficam
    if(document.querySelector('.selo-av')||visivelCom(/como analógico/).length)falta.push('o selo do giroscópio como analógico voltou');
    if(document.querySelectorAll('.ctr .lin > .v').length<12||document.querySelectorAll('.mira .desl .n').length<4)falta.push('os números das barras sumiram');
    // q6: «Só enquanto eu segurar» vira «A mira se move», com «Sempre» (escolhido) e «Só segurando um botão»
    if(visivelCom(/Só enquanto eu segurar/).length||document.querySelector('[aria-label="Só enquanto eu segurar"]'))falta.push('o rótulo «Só enquanto eu segurar» voltou');
    var ss=[...document.querySelectorAll('select[data-gesto=mira-segurar]')];
    if(ss.length!==2)falta.push('há '+ss.length+' seletores de quando a mira se move (têm de ser 2)');
    ss.forEach(function(x){var op=[...x.options].map(function(o){return o.text;}).join('|');var r=x.closest('.desl').querySelector('.r');
      if(op!=='Sempre|Só segurando um botão')falta.push('o seletor da mira tem «'+op.slice(0,50)+'»');
      if(x.options[x.selectedIndex].text!=='Sempre')falta.push('o «Sempre» não segue escolhido');
      if(!r||r.textContent.trim()!=='A mira se move')falta.push('a linha não diz «A mira se move»');});
    // n4 (v3): o seletor do botão aparece ao lado, na mesma linha, só com «Só segurando um botão»; nada pula nem rola
    var BOT='cruz|circulo|quadrado|triangulo|l1|r1|l2|r2|l3|r3|cima|baixo|esquerda|direita|options|share';
    ss.forEach(function(x){var q=x.closest('.mira-quando'),b=q&&q.querySelector('select[data-gesto=mira-botao]'),dl=x.closest('.desl'),inv=dl&&dl.nextElementSibling;
      if(!b){falta.push('o seletor do botão que segura a mira não existe');return;}
      if([...b.options].map(function(o){return o.value;}).join('|')!==BOT)falta.push('o seletor do botão não tem os dezesseis botões: '+[...b.options].map(function(o){return o.value;}).join('|').slice(0,60));
      if(vis(b))falta.push('com «Sempre», o seletor do botão aparece');
      var y0=[inv.getBoundingClientRect().top,document.documentElement.scrollHeight];
      x.value='segurando';x.dispatchEvent(new Event('change',{bubbles:true}));
      var a=x.getBoundingClientRect(),c=b.getBoundingClientRect(),d=dl.getBoundingClientRect(),y1=[inv.getBoundingClientRect().top,document.documentElement.scrollHeight];
      if(!vis(b))falta.push('com «Só segurando um botão», o seletor do botão não aparece');
      else{if(Math.abs(a.top-c.top)>1||Math.abs(a.height-c.height)>0.5)falta.push('o seletor do botão não fica na mesma linha e na mesma altura');
        if(c.left<a.right)falta.push('o seletor do botão não fica ao lado do primeiro');
        if(c.right>d.right+0.5)falta.push('o seletor do botão passa da coluna');
        // o texto de cada escolha cabe no seletor (um clone com a largura natural da escolha)
        [[x,'Só segurando um botão']].concat([...b.options].map(function(o){return [b,o.text];})).forEach(function(p){var t=p[0].cloneNode(false);t.style.position='absolute';t.style.width='auto';t.add(new Option(p[1]));q.appendChild(t);
          var w=t.getBoundingClientRect().width;t.remove();if(w>p[0].getBoundingClientRect().width+0.5)falta.push('«'+p[1]+'» não cabe no seletor ('+Math.round(w)+' > '+Math.round(p[0].getBoundingClientRect().width)+')');});}
      if(Math.abs(y0[0]-y1[0])>0.5)falta.push('o seletor do botão faz a linha de baixo pular');
      if(y1[1]>innerHeight)falta.push('o seletor do botão faz a janela rolar');
      x.value='sempre';x.dispatchEvent(new Event('change',{bubbles:true}));
      if(vis(b))falta.push('de volta a «Sempre», o seletor do botão não some');});
    [...document.querySelectorAll('.ctr')].forEach(function(c){var xs=[...c.querySelectorAll('.lin > .g')].map(function(g){return Math.round(g.getBoundingClientRect().left);});
      if(xs.length&&Math.max.apply(null,xs)-Math.min.apply(null,xs)>1)falta.push('as barras da leitura não começam juntas '+[...new Set(xs)]);});}
  return falta;})
"""

VERDE_DE_TEMA = ("nj-tog", "pino", "span.txt", "btn.fazer", "btn.prim", "button.sw", "span.p")


def verde_de_aviso(item) -> bool:
    nome, _tipo, _cor, _texto = item
    return not any(t in nome for t in VERDE_DE_TEMA)


def medir_paginas(nav, mordida: str) -> int:
    falhas = 0
    for aba, arq in PAGINAS.items():
        for (w, h) in TAMANHOS:
            pg = nav.new_page(viewport={"width": w, "height": h})
            erros = []
            pg.on("pageerror", lambda e, erros=erros: erros.append(str(e)[:80]))
            pg.goto(f"file://{R4}/{arq}")
            pg.wait_for_timeout(600)
            if mordida:
                pg.evaluate(mordida)
                pg.wait_for_timeout(100)
            m = pg.evaluate(JS_MEDIR, REGIAO[aba])
            ruins = []
            if erros:
                ruins.append(f"erro de script {erros[:2]}")
            if "janela" in m and aba != "07":
                if m["janela"][0] > m["janela"][1] or m["janela"][2] > m["janela"][3] + 1:
                    ruins.append(f"a janela rola ou passa da tela {m['janela']}")
            elif m["rolagemV"][0] > m["rolagemV"][1]:
                ruins.append(f"rolagem vertical {m['rolagemV']}")
            if m["rolagemH"][0] > m["rolagemH"][1]:
                ruins.append(f"rolagem lateral {m['rolagemH']}")
            if aba == "07":
                d = pg.evaluate("(function(){var c=document.querySelector('#acessorios .tn-cx');if(!c)return null;var r=c.getBoundingClientRect();"
                                "return [Math.round(r.top),Math.round(r.bottom),Math.round(r.left),Math.round(r.right),c.scrollHeight,c.clientHeight];})()")
                if not d:
                    ruins.append("o diálogo da engrenagem não abriu")
                elif d[0] < 0 or d[1] > h or d[2] < 0 or d[3] > w or d[4] > d[5] + 1:
                    ruins.append(f"o diálogo passa da tela ou rola {d}")
            if m["cortes"]:
                ruins.append(f"corte por overflow {m['cortes'][:3]}")
            if m["pequenos"]:
                ruins.append(f"alvo < 24 px {m['pequenos'][:4]}")
            if m["letrinhas"]:
                ruins.append(f"letra < 12 px {m['letrinhas'][:4]}")
            vs = [v for v in m["verdes"] if verde_de_aviso(v)]
            if vs:
                ruins.append(f"verde de aviso {vs[:4]}")
            for ig in pg.evaluate(JS_IGUAIS, IGUAIS.get(aba, [])):
                if len(ig[2]) < 2:
                    ruins.append(f"o grupo «{ig[0]}» não foi achado ({ig[1]})")
                elif max(ig[2]) - min(ig[2]) > 0.5:
                    ruins.append(f"tamanhos diferentes em «{ig[0]}»: {sorted(set(ig[2]))}")
            ruins += [f"o pedido: {x}" for x in pg.evaluate(JS_PEDIDO, aba)]
            rot = f"{aba} {w}x{h}"
            if ruins:
                falhas += len(ruins)
                print(f"REPROVA {rot}: " + " | ".join(ruins))
            else:
                print(f"ok      {rot}: sem rolagem, alvos ≥24 px, letra ≥12 px, sem verde de aviso, grupos iguais, o pedido está ali")
            pg.close()
    return falhas


def medir_conferencia(nav) -> int:
    """A página de conferência: abre, cada cartão grava (local e no servidor de mentira) e volta depois de recarregar, e nenhuma foto quebra."""
    ruins = []
    servidor = {"dados": {}, "posts": 0}

    def rota(route, request):
        if request.method == "POST":
            servidor["dados"] = json.loads(request.post_data or "{}")
            servidor["posts"] += 1
            route.fulfill(status=200, body='{"ok":true}', headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
        else:
            route.fulfill(status=200, body=json.dumps(servidor["dados"]), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})

    ctx = nav.new_context(viewport={"width": 1212, "height": 809})
    ctx.route("**/respostas-ajustes-r4", rota)
    pg = ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)[:80]))
    url = f"file://{R4}/ajustes/index.html"
    pg.goto(url)
    pg.wait_for_timeout(500)
    ids = pg.evaluate("[...document.querySelectorAll('section[data-id]')].map(s=>s.dataset.id)")
    esperado = ["r4-01-12", "r4-02-17", "r4-02-18", "r4-07-34", "r4-07-35", "r4-calibrar-7"]
    if ids != esperado:
        ruins.append(f"os cartões são {ids}")
    for largura in (1212, 390):
        pg.set_viewport_size({"width": largura, "height": 809})
        pg.wait_for_timeout(200)
        sw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        if sw[0] > sw[1]:
            ruins.append(f"rolagem lateral em {largura} px {sw}")
    pg.set_viewport_size({"width": 1212, "height": 809})
    if "aprovadas" not in pg.evaluate("document.querySelector('.aprovadas') ? 'aprovadas' : ''"):
        ruins.append("a linha das aprovadas sumiu")
    else:
        ap = pg.evaluate("document.querySelector('.aprovadas').getBoundingClientRect().height")
        if ap > 60:
            ruins.append(f"a linha das aprovadas ocupa {ap} px (mais de duas linhas)")
    n_img = pg.evaluate("document.images.length")
    for i in range(n_img):
        pg.evaluate("i=>document.images[i].scrollIntoView()", i)
        pg.wait_for_timeout(120)
    pg.wait_for_timeout(600)
    quebradas = pg.evaluate("[...document.images].filter(i=>!(i.complete&&i.naturalWidth>0)).map(i=>i.getAttribute('src'))")
    if quebradas or n_img < 13:
        ruins.append(f"fotos quebradas {quebradas} de {n_img}")
    for k, sid in enumerate(esperado):
        voto = "aprova" if k % 2 == 0 else "ajustar"
        pg.click(f'section[data-id="{sid}"] .votos button[data-v="{voto}"]')
        pg.fill(f'section[data-id="{sid}"] textarea', f"teste {sid}")
    pg.wait_for_timeout(1200)
    if servidor["posts"] == 0:
        ruins.append("nenhum POST chegou ao servidor")
    for k, sid in enumerate(esperado):
        r = servidor["dados"].get(sid, {})
        if r.get("voto") != ("aprova" if k % 2 == 0 else "ajustar") or r.get("texto") != f"teste {sid}":
            ruins.append(f"o servidor não recebeu {sid}: {r}")
    estado = pg.evaluate("document.getElementById('estado').textContent")
    if not estado.startswith("Salvo às"):
        ruins.append(f"o estado diz «{estado}»")
    pg.reload()
    pg.wait_for_timeout(700)
    pg.evaluate("localStorage.clear()")
    pg.reload()
    pg.wait_for_timeout(900)
    for k, sid in enumerate(esperado):
        v = pg.evaluate(f"""(function(){{var s=document.querySelector('section[data-id="{sid}"]');
          var b=s.querySelector('.votos button[aria-pressed=true]');return [b?b.dataset.v:'',s.querySelector('textarea').value];}})()""")
        if v != ["aprova" if k % 2 == 0 else "ajustar", f"teste {sid}"]:
            ruins.append(f"{sid} não voltou depois de recarregar: {v}")
    conta = pg.evaluate("document.getElementById('conta').textContent")
    if conta != "6 de 6 respondidas":
        ruins.append(f"a conta diz «{conta}»")
    if erros:
        ruins.append(f"erro de script {erros[:2]}")
    ctx.close()
    if ruins:
        print("REPROVA conferência: " + " | ".join(ruins))
    else:
        print(f"ok      conferência: 6 cartões, {n_img} fotos carregadas, cada voto e texto gravou e voltou (navegador e servidor)")
    return len(ruins)


def main() -> int:
    mordida = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--mordida" else ""
    mordida = MORDIDAS.get(mordida, mordida)
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
        f = medir_paginas(nav, mordida)
        if not mordida:
            f += medir_conferencia(nav)
        nav.close()
    print(json.dumps({"falhas": f}))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
