#!/usr/bin/env python3
# ruff: noqa: E501
"""A régua final dos mockups aprovados: mede as catorze páginas finais de todo/ em três tamanhos, sem janela na tela.

Junta as checagens de ajustes-r3/regua.py e de rodada-4/ajustes/regua.py, apontadas para as páginas finais (a fusão
de 14/10), e acrescenta duas, em todas as páginas: nenhuma diz «Player N» nem «Vitória» (no texto e nos atributos que
se leem: title, aria-label, value, placeholder, alt, data-dica e data-titulo; comentário não conta), e nenhuma rola.

Uso: regua-final.py [--mordida <nome|js>] ; sai 0 se tudo passa. As mordidas nomeadas estão em MORDIDAS: cada uma
devolve de propósito algo que saiu, e a régua tem de reprovar. Chrome sem janela (headless); nenhum clique no mouse dela.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TODO = Path(__file__).resolve().parent
TAMANHOS = [(1212, 809), (1212, 740), (1918, 840)]
FINAIS = {"01": "01-jogar.html", "02": "02-controles.html", "03": "03-gatilhos.html", "04": "04-iluminacao.html",
          "05": "05-vibracao.html", "06": "06-navegacao.html", "07": "07-lancadores.html", "08": "08-conexoes.html",
          "09": "09-sistema.html", "10": "10-perfis.html", "calibrar": "calibrar-sensores.html",
          "mapa-das-portas": "mapa-das-portas.html", "mapa-do-controle": "mapa-do-controle.html", "mapa-do-radio": "mapa-do-radio.html"}
PAGINAS_R3 = {k: FINAIS[k] for k in ("03", "04", "05", "06", "07", "08", "10")}
PAGINAS_R4 = {"01": FINAIS["01"], "02": FINAIS["02"], "07": FINAIS["07"] + "?aba=t2#acessorios", "calibrar": FINAIS["calibrar"]}


def _m(corpo):
    return "(function(){try{" + corpo + "}catch(e){}})()"


MORDIDAS_R3 = {
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
    "q1-nome-longo": _m("var s=document.querySelector('.g2-canto .g2-estilo');s.style.flexWrap='nowrap';"),
    "q1-cor": _m("document.querySelector('.g2-canto .sec-rot').style.color='#f8f8f2';"),
    "q2-para": _m("var p=document.querySelector('.ext[data-modificacao=lovense] .ext-para');p.innerHTML='<span class=ext-rot>Para</span>Todos';"),
    "q2-conta": _m("document.querySelector('#lovense .lv-linha:last-child .nj-tog').classList.add('ligado');"),
    "c1-sem-ds": _m("document.querySelector('.g2-gl.g2-ds').remove();"),
    "c1-ds-solto": _m("var d=document.querySelector('.g2-gl.g2-ds svg');d.setAttribute('width','24');d.setAttribute('height','24');"),
    "c1-nome-branco": _m("document.querySelector('.g2-canto .g2-estilo-nome').style.color='#f8f8f2';"),
    "c1-duas-linhas": _m("document.querySelector('.g2-canto .g2-estilo').style.flexDirection='column';"),
    "n1-chips-apagam": _m("document.querySelector('.modo-auto').dataset.governa='.g2-grade > :not(.g2-canto)';"),
    "n2-linha-fica": _m("document.querySelector('.g2-canto .g2-estilo').style.display='flex';"),
    "n2-pula": _m("var st=document.createElement('style');st.textContent='.g2-canto:has(.g2-estilo-nome:empty) .g2-canto-rot{margin-top:30px}';document.head.appendChild(st);"),
    "n3-chave-fica": _m("var k=document.querySelector('.ext[data-modificacao=lovense] > .nj-tog');k.replaceWith(k.cloneNode(true));"),
    "dica-passo": _m("var t=document.querySelector('.vib .forca input[type=range]');t.setAttribute('data-dica','Ajuste fino dentro do passo');"),
}

JS_MEDIR_R3 = r"""
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

JS_IGUAIS_R3 = r"""
(function(grupos){
  var out=[];grupos.forEach(function(g){
    var ws=[];document.querySelectorAll(g[1]).forEach(function(e){var r=e.getBoundingClientRect();if(r.width>0&&r.height>0)ws.push(Math.round(r.width*10)/10);});
    out.push([g[0],g[1],ws]);});return out;})
"""
IGUAIS_R3 = {
    "03": [["selects de acionamento e imersão", ".g2-cel .g2-acion, .g2-cel .g2-imersao"]],
    "07": [["Ligada e Desligada", ".ext-lista .nj-tog"],
           ["Identificar / Criar perfis / Configurar", ".lanc-fila .btn.mini:not(.lf-imped)"],
           ["botões do conserto no diálogo", "#impedimentos .imp-conserta, #impedimentos .imp-item .btn"]],
    "08": [["Usar como botões / Trazer de volta", "[data-r3='13'] .features .btn, [data-r3='14'] .features .btn"]],
}

JS_PEDIDO_R3 = r"""
(function(aba){
  function vis(e){var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
    for(var p=e;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden'||+t.opacity===0)return false;}return true;}
  function textos(sel){return [...document.querySelectorAll(sel)].filter(vis).map(function(e){return (e.textContent||'').trim();});}
  function tem(sel,txt){return textos(sel).some(function(t){return t.indexOf(txt)>=0;});}
  var falta=[];
  var jan=document.querySelector('.janela .miolo')||document.body;
  function vagas(sel){var v=[...document.querySelectorAll('.miolo '+sel)].filter(function(e){return vis(e)&&/Desconectado/.test(e.textContent);});
    if(v.length!==2)falta.push('há '+v.length+' vagas sem controle (têm de ser 2)');
    v.forEach(function(e){var t=e.textContent.replace(/\s+/g,' ').trim();if(!/^P[34] • Desconectado$/.test(t))falta.push('a vaga sem controle diz «'+t.slice(0,40)+'»');});}
  if(aba==='03'){
    if(document.querySelectorAll('.g2-forca-sel,.g2-rot-forca,.g2-gl-forca').length)falta.push('a linha «Força do gatilho» existe');
    if(tem('.miolo *','Força do gatilho'))falta.push('o texto «Força do gatilho» aparece');
    // as seis respostas, q1: a célula à esquerda dos controles tem só «Controle» e «Estilo de jogo: …», e os desconectados não aparecem
    var cn=document.querySelector('.g2-canto');
    if(!cn||!vis(cn))falta.push('a célula à esquerda dos controles sumiu');
    else{var tx=[...cn.children].map(function(x){return x.textContent.trim();}).join(' ');
      if(cn.children.length!==2||!/^Controle Estilo de jogo\S+$/.test(tx))falta.push('a célula da esquerda não diz só «Controle» e «Estilo de jogo» com o nome: «'+tx.slice(0,50)+'»');
      if(cn.querySelector('svg,[data-leitura],.g2-leitura')||/\b[LR]2\b/.test(tx))falta.push('o desenho ou a leitura do L2 e R2 voltou à célula da esquerda');
      if(cn.querySelector('button,select,input,a'))falta.push('a célula da esquerda virou controle (tem de ser só leitura)');
      var rc=cn.querySelector('.sec-rot'),es=cn.querySelector('.g2-estilo'),ro=document.querySelector('.g2-rot .sec-rot');
      if(!rc||!/^Controle$/.test(rc.textContent.trim()))falta.push('«Controle» não tem a letra dos rótulos de linha');
      else if(getComputedStyle(rc).color!==getComputedStyle(ro).color)falta.push('«Controle» não tem a cor verde dos rótulos de linha');
      var er=cn.querySelector('.g2-estilo-rot'),en=cn.querySelector('.g2-estilo-nome');
      if(!er||er.textContent.trim()!=='Estilo de jogo'||getComputedStyle(er).color!==getComputedStyle(document.querySelector('.g2-acion')).color)falta.push('«Estilo de jogo» não está em branco');
      // c1 (v3): o nome do estilo em roxo, à direita, na mesma linha de «Estilo de jogo», abaixo de «Controle»
      if(!en||getComputedStyle(en).color!==getComputedStyle(document.querySelector('.g2-acion')).borderTopColor)falta.push('o nome do estilo não está em roxo');
      if(er&&en&&rc){var a=er.getBoundingClientRect(),b=en.getBoundingClientRect(),c=rc.getBoundingClientRect();
        if(Math.abs(a.top-b.top)>1)falta.push('«Estilo de jogo» e o nome do estilo não estão na mesma linha');
        if(b.left<a.right)falta.push('o nome do estilo não fica à direita de «Estilo de jogo»');
        if(Math.abs(b.right-es.getBoundingClientRect().right)>1)falta.push('o nome do estilo não encosta à direita da coluna dos rótulos');
        if(a.top<c.bottom-1)falta.push('a linha do estilo não fica abaixo de «Controle»');}
      // c1 (v3): o DualSense na coluna dos ícones, do tamanho do L2 e do R2, na linha dos controles
      var ds=document.querySelector('.g2-gl.g2-ds'),l2=document.querySelector('.g2-gl.g2-l2');
      if(!ds||!vis(ds)||!ds.querySelector('svg title')||ds.querySelector('svg title').textContent!=='DualSense')falta.push('o ícone do DualSense não está na coluna dos ícones');
      else if(l2){var d=ds.querySelector('svg').getBoundingClientRect(),g=l2.querySelector('svg').getBoundingClientRect(),
          cc=document.querySelector('.g2-cab .chip').getBoundingClientRect();
        if(Math.abs((d.left+d.right)/2-(g.left+g.right)/2)>1)falta.push('o DualSense não fica na coluna do L2 e do R2');
        if(Math.abs(d.width-g.width)>0.5||Math.abs(d.height-g.height)>0.5)falta.push('o DualSense não tem o tamanho do L2 e do R2: '+Math.round(d.width)+' e '+Math.round(g.width));
        if(Math.abs((d.top+d.bottom)/2-(cc.top+cc.bottom)/2)>2)falta.push('o DualSense não fica na linha dos controles');
        if(getComputedStyle(ds).borderRightStyle!==getComputedStyle(l2).borderRightStyle)falta.push('o DualSense sem a divisória dos ícones');}
      [rc,es].forEach(function(x){if(x&&ro&&Math.abs(x.getBoundingClientRect().left-ro.getBoundingClientRect().left)>1.5)falta.push('a linha «'+x.textContent.trim().slice(0,14)+'» não começa na borda dos rótulos de baixo');
        if(x&&x.getBoundingClientRect().right>document.querySelector('.g2-cab').getBoundingClientRect().left-4)falta.push('a linha «'+x.textContent.trim().slice(0,14)+'» encosta no chip');});
      // o estilo mais longo de Perfis (Point and click) também não pode invadir a coluna do primeiro controle
      var nm=cn.querySelector('[data-estilo]');if(nm&&es){var ant=nm.textContent;nm.textContent='Point and click';
        if(Math.max(es.getBoundingClientRect().right,nm.getBoundingClientRect().right)>document.querySelector('.g2-cab').getBoundingClientRect().left-4)falta.push('o estilo «Point and click» invade a coluna do primeiro controle');
        if(document.documentElement.scrollHeight>innerHeight)falta.push('o estilo «Point and click» faz a página rolar');nm.textContent=ant;}}
    var cabs=[...document.querySelectorAll('.g2-cab')].filter(vis);
    if(cabs.some(function(c){return /Desconectado/.test(c.textContent)||c.querySelector('.chip.vazio');}))falta.push('um controle desconectado aparece na linha do alto');
    if(cabs.filter(function(c){return c.querySelector('.chip');}).length!==2)falta.push('a linha do alto não tem os dois controles conectados');
    // as colunas seguem a grade: cada chip na borda da coluna dele embaixo
    ['p1','p2'].forEach(function(k){var ch=document.querySelector('.g2-cab[data-controle='+k+'] .chip'),ce=document.querySelector('.g2-cel[data-controle='+k+']');
      if(ch&&ce){var a=ch.getBoundingClientRect(),c=ce.getBoundingClientRect();if(Math.abs(a.left-c.left)>1||Math.abs(a.width-c.width)>1)falta.push('o chip '+k+' desalinhou da coluna de baixo');}});
    var ca=document.querySelector('.modo-auto');if(ca){ca.click();if(!vis(cn)||!/Estilo de jogo\S/.test(cn.textContent))falta.push('com o Modo automático, a leitura do estilo some');
      // n1 (v3): com o automático ligado, os chips, o DualSense e a célula ficam acesos; só a grade dos efeitos apaga
      function op(e){var o=1;for(var p=e;p&&p.nodeType===1;p=p.parentElement){var t=getComputedStyle(p);o*=+t.opacity;if(t.filter!=='none')o*=0.99;}return o;}
      [...document.querySelectorAll('.g2-cab .chip, .g2-canto, .g2-gl.g2-ds')].filter(vis).forEach(function(e){if(op(e)<0.999)falta.push('com o Modo automático, «'+(e.textContent.trim().slice(0,16)||'o DualSense')+'» fica apagado');});
      if([...document.querySelectorAll('.g2-cel select, .g2-rot .sec-rot, .g2-gl:not(.g2-ds)')].filter(vis).some(function(e){return op(e)>0.9;}))falta.push('com o Modo automático, a grade dos efeitos não apaga');
      ca.click();}
    // n2 (v3): sem estilo no perfil, a linha do estilo some, fica só «Controle», e a grade não pula
    var nn=cn&&cn.querySelector('[data-estilo]');if(nn){var an=nn.textContent,sp=document.querySelector('.g2-sep-cab'),c1=document.querySelector('.g2-cel');
      var y0=[sp.getBoundingClientRect().top,c1.getBoundingClientRect().top];nn.textContent='';
      var y1=[sp.getBoundingClientRect().top,c1.getBoundingClientRect().top];
      if(vis(cn.querySelector('.g2-estilo')))falta.push('sem estilo no perfil, a linha «Estilo de jogo» não some');
      if(!vis(cn.querySelector('.g2-canto-rot')))falta.push('sem estilo no perfil, «Controle» some junto');
      if(Math.abs(y0[0]-y1[0])>0.5||Math.abs(y0[1]-y1[1])>0.5)falta.push('sem estilo no perfil, a grade pula: '+y0.map(Math.round)+' → '+y1.map(Math.round));
      var cr=cn.querySelector('.g2-canto-rot').getBoundingClientRect(),ch=document.querySelector('.g2-cab .chip').getBoundingClientRect();
      if(Math.abs((cr.top+cr.bottom)/2-(ch.top+ch.bottom)/2)>2)falta.push('sem estilo no perfil, «Controle» não fica no meio da linha dos controles');
      nn.textContent=an;}}
  if(aba==='04'){if(tem('.miolo button, .miolo [role=button]','Desligar'))falta.push('o «Desligar» voltou aos efeitos');
    if(tem('.miolo .quadro-topo *, .miolo button, .miolo .nj-tog','Sem piscar'))falta.push('«Sem piscar» voltou como chave');
    [...document.querySelectorAll('.miolo select')].filter(vis).forEach(function(x){var o=[...x.options].map(function(y){return y.text;});
      if(o.indexOf('Sem efeito')<0||o.indexOf('Sem piscar')<0)falta.push('um seletor de efeito sem «Sem efeito» ou «Sem piscar»');});
    // fusão (14/10): a q4B (as seis respostas) vence a r3-04-11: a vaga sem controle diz só «P3 • Desconectado», sem cor de plástico
    vagas('[data-campo=identidade]');}
  if(aba==='05'){if(tem('.miolo *','Criar efeitos novos'))falta.push('«Criar efeitos novos» voltou');
    // fusão (14/10): a q4B (as seis respostas) vence a r3-05-12: as vagas 3 e 4 dizem só «P3 • Desconectado», sem cor de plástico
    vagas('[data-hef=identidade]');
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
    // n3 (v3): as três formas desligadas deixam a chave da Lovense «Desligada» e «0 de 3 ligadas»; ligar a chave assim abre
    // a engrenagem; ligar uma forma devolve a chave a «Ligada». No fim, o estado de antes volta.
    var fs=[...document.querySelectorAll('#lovense .lv-linha .nj-tog')],kc=document.querySelector('.ext[data-modificacao=lovense] > .nj-tog'),lc=document.querySelector('[data-lv-conta]');
    if(kc&&lc&&fs.length===3){var antes=fs.map(function(f){return f.classList.contains('ligado');}),h0=location.hash;
      var clk=function(x){x.dispatchEvent(new MouseEvent('click',{bubbles:true}));};
      fs.filter(function(f){return f.classList.contains('ligado');}).forEach(clk);
      if(kc.classList.contains('ligado')||kc.textContent.trim()!=='Desligada')falta.push('com as três formas desligadas, a chave da Lovense não diz «Desligada»: «'+kc.textContent.trim()+'»');
      if(lc.textContent.trim()!=='0 de 3 ligadas')falta.push('com as três formas desligadas, a linha não diz «0 de 3 ligadas»: «'+lc.textContent.trim()+'»');
      clk(kc);
      if(location.hash!=='#lovense')falta.push('ligar a chave com as três formas desligadas não abre a engrenagem');
      if(kc.classList.contains('ligado'))falta.push('a chave da Lovense liga com as três formas desligadas');
      clk(fs[0]);
      if(!kc.classList.contains('ligado')||kc.textContent.trim()!=='Ligada')falta.push('ligar uma forma não devolve a chave da Lovense a «Ligada»');
      fs.forEach(function(f,i){if(f.classList.contains('ligado')!==antes[i])clk(f);});
      history.replaceState(null,'',location.pathname+location.search+h0);}
    else falta.push('a chave da Lovense, a conta ou as três formas sumiram');
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
                pg.goto(f"file://{TODO / PAGINAS_R3[aba]}#{did}")
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
    pg.goto(f"file://{TODO / PAGINAS_R3['06']}")
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


def medir_r3(nav, mordida: str) -> int:
    """As checagens de ajustes-r3/regua.py, apontadas para as páginas finais."""
    falhas = 0
    for aba, arq in PAGINAS_R3.items():
        for (w, h) in TAMANHOS:
            for exemplo in [False]:
                pg = nav.new_page(viewport={"width": w, "height": h})
                pg.goto(f"file://{TODO / arq}")
                pg.wait_for_timeout(500)
                if mordida:
                    pg.evaluate(mordida)
                m = pg.evaluate(JS_MEDIR_R3)
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
                for ig in pg.evaluate(JS_IGUAIS_R3, IGUAIS_R3.get(aba, [])):
                    if len(ig[2]) >= 2 and max(ig[2]) - min(ig[2]) > 0.5:
                        ruins.append(f"larguras diferentes em «{ig[0]}»: {sorted(set(ig[2]))}")
                if aba in ("04", "05", "07"):
                    if m["pequenos"]:
                        ruins.append(f"alvo < 24 px {m['pequenos'][:4]}")
                    m["letrinhas"] = [x for x in m["letrinhas"] if any(c.isalnum() for c in x[2])]
                    if m["letrinhas"]:
                        ruins.append(f"letra < 12 px {m['letrinhas'][:4]}")
                ruins += [f"o pedido: {x}" for x in pg.evaluate(JS_PEDIDO_R3, aba)]
                rot = f"r3 {aba} {w}x{h}" + (" +exemplo" if exemplo else "")
                if ruins:
                    falhas += len(ruins)
                    print(f"REPROVA {rot}: " + " | ".join(ruins))
                else:
                    print(f"ok      {rot}: rolagem {m.get('janela', m['rolagemV'])}, igualdade e verde conferidos")
                pg.close()
    falhas += medir_dialogos(nav, mordida)
    falhas += medir_dica_da_navegacao(nav, mordida)
    return falhas



REGIAO = {
    "01": "[data-controle]",
    "02": ".ctl > .faixa, .ctl[data-conectado=nao]",
    "07": "#acessorios .ja-tela.t2",
    "calibrar": "body",
}


MORDIDAS_R4 = {
    "zona-01": _m("var c=document.querySelector('[data-controle=p1] [data-gesto=mascara]');var d=document.createElement('div');d.className='jv';"
                  "d.setAttribute('data-todo','12');d.setAttribute('data-dica','O que o jogo enxerga');d.textContent='O jogo vê: Sony DualSense';c.parentNode.appendChild(d);"),
    "botao-02": _m("var f=document.querySelector('.ctl[data-conectado=sim] > .faixa, .ctl:not([data-conectado=nao]) > .faixa');var b=document.createElement('button');"
                   "b.className='jv-btn';b.setAttribute('data-todo','17');b.textContent='O que chega';f.appendChild(b);"),
    "vaga-02": _m("var f=document.querySelector('.ctl[data-conectado=nao] > .faixa');var s=document.createElement('span');s.className='card-nome';"
                  "s.textContent=' Galactic Purple';f.querySelector('.card-nome').appendChild(s);"),
    "q4-player-02": _m("var p=document.querySelector('.ctl[data-conectado=nao] [data-campo=peca]');p.textContent='Player 3';"),
    "lista-07": _m("var l=document.querySelector('.ext-lista');var j=document.querySelector('[data-todo=\"38\"]');l.appendChild(j);"),
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

JS_MEDIR_R4 = r"""
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

JS_IGUAIS_R4 = r"""
(function(grupos){
  return grupos.map(function(g){var ws=[];document.querySelectorAll(g[1]).forEach(function(e){var r=e.getBoundingClientRect();
    if(r.width>0&&r.height>0)ws.push(Math.round((g[2]==='altura'?r.height:r.width)*10)/10);});return [g[0],g[1],ws];});})
"""
IGUAIS_R4 = {
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

JS_PEDIDO_R4 = r"""
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
    // fusão (14/10): a 07-34 e a 07-35 da rodada 4 são a 38 e a 39 na página final
    [['38','os jogos'],['39','a força']].forEach(function(p){var e=document.querySelector('[data-todo="'+p[0]+'"]');
      if(!e)falta.push(p[1]+' sumiu');else{if(!ac||!ac.contains(e))falta.push(p[1]+' fora do diálogo da engrenagem');
        if(e.closest('.ext-lista'))falta.push(p[1]+' está na lista de extensões');}});
    // fusão (14/10): na página final a Lovense é uma extensão só (r3-07-29); a engrenagem das formas dela abre os acessórios
    var eg=document.querySelector('#lovense .lv-linha .ext-conf[href="#acessorios"]');if(!eg)falta.push('a engrenagem das formas da Lovense não abre o diálogo dos acessórios');
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


def medir_r4(nav, mordida: str) -> int:
    """As checagens de rodada-4/ajustes/regua.py, apontadas para as páginas finais."""
    falhas = 0
    for aba, arq in PAGINAS_R4.items():
        for (w, h) in TAMANHOS:
            pg = nav.new_page(viewport={"width": w, "height": h})
            erros = []
            pg.on("pageerror", lambda e, erros=erros: erros.append(str(e)[:80]))
            pg.goto(f"file://{TODO}/{arq}")
            pg.wait_for_timeout(600)
            if mordida:
                pg.evaluate(mordida)
                pg.wait_for_timeout(100)
            m = pg.evaluate(JS_MEDIR_R4, REGIAO[aba])
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
            for ig in pg.evaluate(JS_IGUAIS_R4, IGUAIS_R4.get(aba, [])):
                if len(ig[2]) < 2:
                    ruins.append(f"o grupo «{ig[0]}» não foi achado ({ig[1]})")
                elif max(ig[2]) - min(ig[2]) > 0.5:
                    ruins.append(f"tamanhos diferentes em «{ig[0]}»: {sorted(set(ig[2]))}")
            ruins += [f"o pedido: {x}" for x in pg.evaluate(JS_PEDIDO_R4, aba)]
            rot = f"r4 {aba} {w}x{h}"
            if ruins:
                falhas += len(ruins)
                print(f"REPROVA {rot}: " + " | ".join(ruins))
            else:
                print(f"ok      {rot}: sem rolagem, alvos ≥24 px, letra ≥12 px, sem verde de aviso, grupos iguais, o pedido está ali")
            pg.close()
    return falhas




VAGAS = {"01": 2, "02": 2, "03": 0, "04": 2, "05": 2, "06": 0, "08": 2, "calibrar": 2}
JS_GERAL = r"""
(function(){
  // a letra conta: a citação dela na nota da 04 («o meu controle azul é o player 2») fica, como toda citação dela
  var re=/Player\s*[0-9]|Vitória/,ATR=['title','aria-label','value','placeholder','alt','data-dica','data-titulo'],ditos=[];
  function nome(e){var c=(typeof e.className==='string'?e.className:'').trim().split(/\s+/).slice(0,2).join('.');return e.tagName.toLowerCase()+(c?'.'+c:'')+(e.id?'#'+e.id:'');}
  if(re.test(document.title))ditos.push(['title',document.title]);
  var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
  while((n=w.nextNode())){var p=n.parentElement;if(!p||p.closest('script,style,noscript'))continue;if(re.test(n.textContent))ditos.push([nome(p),n.textContent.trim().slice(0,50)]);}
  document.querySelectorAll('body *').forEach(function(e){ATR.forEach(function(a){var v=e.getAttribute(a);if(v&&re.test(v))ditos.push([nome(e)+'['+a+']',v.slice(0,50)]);});
    if(e.matches('input,textarea')&&re.test(e.value||''))ditos.push([nome(e)+'.value',e.value.slice(0,50)]);});
  function vis(e){var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;
    for(var p=e;p;p=p.parentElement){var t=getComputedStyle(p);if(t.display==='none'||t.visibility==='hidden'||+t.opacity===0)return false;}return true;}
  var vagas=[];
  document.querySelectorAll('body *').forEach(function(e){if(e.closest('script,style')||!vis(e))return;
    if(![...e.childNodes].some(function(x){return x.nodeType===3&&/Desconectado/.test(x.textContent);}))return;
    var r=e;for(var i=0;i<3&&r.parentElement&&!/P\d/.test(r.innerText);i++)r=r.parentElement;
    vagas.push(r.innerText.replace(/\s+/g,'').trim());});
  // nenhum aviso verde (r3-07-29): o ✓ de um estado que está bem não é verde, nem no texto nem no fundo da pílula
  function verde(c){var m=c.match(/[\d.]+/g);if(!m)return false;var R=+m[0],G=+m[1],B=+m[2],A=m.length>3?+m[3]:1;return A>0.05&&G>R+35&&G>B+35&&G>120;}
  var certos=[];w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while((n=w.nextNode())){var ce=n.parentElement;if(!/✓/.test(n.textContent)||!ce||ce.closest('script,style')||!vis(ce))continue;
    var onde=verde(getComputedStyle(ce).color)?'cor':'';for(var q=ce,k=0;!onde&&q&&k<3;q=q.parentElement,k++)if(verde(getComputedStyle(q).backgroundColor))onde='fundo';
    if(onde)certos.push([nome(ce),onde,(ce.parentElement.textContent||'').trim().slice(0,20)]);}
  var jan=document.querySelector('.janela');
  return {ditos:ditos,vagas:vagas,certos:certos,rolagemV:[document.documentElement.scrollHeight,innerHeight],rolagemH:[document.documentElement.scrollWidth,innerWidth],
    janela:jan?[Math.round(jan.getBoundingClientRect().bottom),innerHeight,jan.scrollHeight,jan.clientHeight]:null};})()
"""

MORDIDAS_GERAL = {
    "player-3": _m("var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;while((n=w.nextNode())){if(/^P[34]$/.test(n.textContent.trim())){n.textContent='Player 3';break;}}"),
    "vitoria": _m("var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;while((n=w.nextNode())){if(/Cosmic Red/.test(n.textContent)&&!n.parentElement.closest('script,style')){n.textContent=n.textContent.replace('Cosmic Red','Vitória');break;}}"),
    "vitoria-na-dica": _m("var e=document.querySelector('[data-dica]');e.setAttribute('data-dica','Controle da Vitória');"),
    "tira-a-38": _m("var j=document.querySelector('[data-todo=\"38\"]');document.querySelector('.miolo, body').appendChild(j);"),
    "certo-verde": _m("document.querySelectorAll('.saude .selo.ok, .gc-est .certo').forEach(function(e){e.style.background='rgb(80,250,123)';e.style.color='rgb(80,250,123)';});"),
    "rola": _m("var d=document.createElement('div');d.style.height='2000px';(document.querySelector('.janela .miolo')||document.body).appendChild(d);"),
}
MORDIDAS = {**MORDIDAS_R3, **MORDIDAS_R4, **MORDIDAS_GERAL}
assert len(MORDIDAS) == len(MORDIDAS_R3) + len(MORDIDAS_R4) + len(MORDIDAS_GERAL), "mordida com nome repetido"


def medir_geral(nav, mordida: str) -> int:
    """Nas catorze páginas finais: sem «Player N», sem «Vitória», sem ✓ verde, as vagas como a q4B, sem rolar, sem erro de script."""
    falhas = 0
    for aba, arq in FINAIS.items():
        for (w, h) in TAMANHOS:
            pg = nav.new_page(viewport={"width": w, "height": h})
            erros = []
            pg.on("pageerror", lambda e, erros=erros: erros.append(str(e)[:80]))
            pg.goto(f"file://{TODO / arq}")
            pg.wait_for_timeout(500)
            if mordida:
                pg.evaluate(mordida)
                pg.wait_for_timeout(100)
            g = pg.evaluate(JS_GERAL)
            ruins = []
            if erros:
                ruins.append(f"erro de script {erros[:2]}")
            if g["ditos"]:
                ruins.append(f"diz «Player N» ou «Vitória» {g['ditos'][:3]}")
            if g["certos"]:
                ruins.append(f"um ✓ verde de aviso {g['certos'][:3]}")
            if aba in VAGAS and len(g["vagas"]) != VAGAS[aba]:
                ruins.append(f"há {len(g['vagas'])} vagas sem controle (têm de ser {VAGAS[aba]}): {g['vagas'][:4]}")
            ruins += [f"a vaga sem controle diz «{v[:40]}» (q4B: «P3 • Desconectado»)" for v in g["vagas"] if v not in ("P3•Desconectado", "P4•Desconectado")]
            if g["rolagemV"][0] > g["rolagemV"][1]:
                ruins.append(f"rolagem vertical {g['rolagemV']}")
            if g["janela"] and (g["janela"][0] > g["janela"][1] or g["janela"][2] > g["janela"][3] + 1):
                ruins.append(f"a janela rola ou passa da tela {g['janela']}")
            if g["rolagemH"][0] > g["rolagemH"][1]:
                ruins.append(f"rolagem lateral {g['rolagemH']}")
            rot = f"final {aba} {w}x{h}"
            if ruins:
                falhas += len(ruins)
                print(f"REPROVA {rot}: " + " | ".join(ruins))
            else:
                print(f"ok      {rot}: sem «Player N» nem «Vitória», vagas {len(g['vagas'])}, sem rolagem")
            pg.close()
    return falhas


def main() -> int:
    mordida = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--mordida" else ""
    mordida = MORDIDAS.get(mordida, mordida)
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
        f = medir_geral(nav, mordida) + medir_r3(nav, mordida) + medir_r4(nav, mordida)
        nav.close()
    print(json.dumps({"falhas": f}))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
