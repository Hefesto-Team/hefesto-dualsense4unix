#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as nove abas, tudo pintado pelo despachante."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

import argparse
import contextlib
import dataclasses
import json
import os
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _pede_a_tela_de_mentira(argv: list[str], ambiente: Any) -> bool:
    """O `--conta-tamanho` sem `--oculta` abre uma janela com barra: ela nasce num Xvfb próprio."""
    conta = any(a == "--conta-tamanho" or a.startswith("--conta-tamanho=") for a in argv)
    return conta and "--oculta" not in argv and ambiente.get("HEFESTO_NA_TELA") != "1"


if __name__ == "__main__" and _pede_a_tela_de_mentira(sys.argv[1:], os.environ):
    from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

    garantir_tela_de_mentira()

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.interface import (  # noqa: E402
    monta,
    navegacao_interna,
    onde,
    regua_do_mockup,
)

if __name__ != "__main__":
    from hefesto_dualsense4unix.interface import mesa_viva, pacotes
    from hefesto_dualsense4unix.interface.pacotes import ponte

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402
from hefesto_dualsense4unix.interface.janela import JanelaDaAba  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import gesto_de_agora  # noqa: E402

PRIMEIRA = "01-jogar.html"

TIQUE_MS = 100


MS_DA_PISCADA = 1500


CHAVE_DO_CLIQUE_QUE_SO_ARMOU = "armou"

TITULO_DE_QUALQUER_ABA = "Hefesto — aba "


def _a_pagina_pedida(pedido: str) -> str:
    """Resolve o que veio no ``--abre`` para o nome de arquivo da página.

    Aceita ``"10"``, ``"10-perfis"`` e ``"10-perfis.html"``: a string crua já
    abriu a página de erro do WebKit com rc=0. A página que saiu do produto
    (`monta.PAGINAS_QUE_SAIRAM`) cai na aba que a absorveu. O que não casar
    volta intacto, e quem reprova é o `_ir`, que confere o arquivo.
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return pedido
    nomes = [caminho.name for caminho in onde.paginas(publicado=True)
             if caminho.name not in monta.PAGINAS_QUE_SAIRAM]
    nomes += list(monta.PAGINAS_QUE_SAIRAM)
    achado = next((nome for nome in nomes if pedido in (nome, nome.removesuffix(".html"))
                   or nome.split("-", 1)[0] == pedido), pedido)
    return monta.PAGINAS_QUE_SAIRAM.get(achado, achado)


SELETOR_DO_DONO: str

CHAVES_QUE_O_VIVO_RECUSA = ("blocos", "fita", "recado", "recados")

BOOTSTRAP = r"""
(function(){
  window.__hef = window.__hef || {};
  function ligado(t){
    const b = String(t).trim().toLowerCase();
    return !(b === '' || b === '—' || b === '0' || b === 'false'
             || b === 'nao' || b === 'não' || b === 'off'
             || b === 'none' || b === 'null');
  }
  const ATRIBUTO_DE_ENDERECO = ['data-campo', 'data-papel', 'data-controle',
                                'data-uniq', 'data-gesto'];
  const ATRIBUTO_A_MAIS = ['title'];
  function atributo_escrevivel(n){
    if(ATRIBUTO_A_MAIS.indexOf(n) >= 0) return true;
    return /^(data|aria)-[a-z0-9]+(-[a-z0-9]+)*$/.test(n)
           && n.indexOf('data-hef') !== 0
           && ATRIBUTO_DE_ENDERECO.indexOf(n) < 0;
  }
  window.__hef.atributoEscrevivel = atributo_escrevivel;
  function escrever(el, v){
    if(!el) return 0;
    const vazio = (v === null || v === undefined || v === '');
    const tipo = String(el.type || '').toLowerCase();
    const digitavel = !!(el.dataset && el.dataset.hefVivo !== undefined
                         && String(el.dataset.hefVivo).trim() !== '')
      || el.tagName === 'TEXTAREA'
      || (el.tagName === 'INPUT' && (tipo === 'text' || tipo === 'search'));
    const t = vazio ? (digitavel ? '' : '—') : String(v);
    const alvo = el.dataset.hefAlvo || 'texto';
    if(el.dataset.hefVisto !== '1'){ el.dataset.hefVisto = '1'; }
    if(alvo === 'largura'){
      const antes = el.style.width;
      el.style.width = t + '%';
      return el.style.width === antes ? 0 : 1;
    }
    function sob_o_dedo(el){
      try{
        if(el === document.activeElement) return true;
        return !!(el.matches && el.matches(':active'));
      }catch(e){ return false; }
    }
    if(alvo === 'altura'){
      const antes = el.style.height;
      el.style.height = t + '%';
      return el.style.height === antes ? 0 : 1;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){
      if(sob_o_dedo(el)) return 0;
      if(el.tagName === 'SELECT'){
        const op = Array.prototype.find.call(el.options,
                                             function(o){ return o.value === t; })
          || Array.prototype.find.call(el.options, function(o){ return o.text === t; });
        if(!op) return 0;
        if(el.selectedIndex !== op.index){ el.selectedIndex = op.index; return 1; }
        return 0;
      }
      if(el.tagName === 'INPUT' && String(el.type).toLowerCase() === 'range'
         && !isFinite(Number(t))) return 0;
      if(el.value !== t){ el.value = t; return 1; }
      return 0;
    }
    if(alvo === 'marcado'){
      const querido = (t === 'sim');
      if(sob_o_dedo(el)) return 0;
      if(el.checked === querido) return 0;
      el.checked = querido;
      return 1;
    }
    if(alvo === 'html'){
      const h = (v === null || v === undefined || v === '') ? '' : t;
      if(el.__hefHtml === h) return 0;
      if(el.innerHTML !== h){ el.innerHTML = h; el.__hefHtml = h; return 1; }
      el.__hefHtml = h;
      return 0;
    }
    if(alvo === 'classe'){
      const c = el.dataset.hefClasse || 'on';
      const quando = el.dataset.hefQuando;
      const aceso = (quando === undefined || quando === '') ? ligado(t) : (t === quando);
      let n = 0;
      const junto = (el.dataset.hefAtributo || '').trim().toLowerCase();
      if(junto && atributo_escrevivel(junto)){
        const querido = aceso ? 'true' : 'false';
        if(el.getAttribute(junto) !== querido){
          el.setAttribute(junto, querido);
          n += 1;
        }
      }
      if(el.hasAttribute('data-hef-razao')){
        const razao = aceso && !vazio ? t : '';
        if(razao){
          if(el.getAttribute('data-dica') !== razao){ el.setAttribute('data-dica', razao); n += 1; }
        } else if(el.hasAttribute('data-dica')){
          el.removeAttribute('data-dica'); n += 1;
        }
      }
      if(el.classList.contains(c) === aceso) return n;
      el.classList.toggle(c, aceso);
      return n + 1;
    }
    if(alvo === 'cor'){
      const antes = el.style.color;
      el.style.color = vazio ? '' : t;
      return el.style.color === antes ? 0 : 1;
    }
    if(alvo === 'plastico'){
      const antes = el.style.getPropertyValue('--plastico');
      if(vazio || t === '—'){ el.style.removeProperty('--plastico'); }
      else { el.style.setProperty('--plastico', t); }
      return el.style.getPropertyValue('--plastico') === antes ? 0 : 1;
    }
    if(alvo === 'posicao'){
      const ax = el.style.getPropertyValue('--hef-x').trim();
      const ay = el.style.getPropertyValue('--hef-y').trim();
      const xy = (vazio || t === '—') ? [] : t.split(',');
      if(xy.length !== 2){
        if(!ax && !ay) return 0;
        el.style.removeProperty('--hef-x');
        el.style.removeProperty('--hef-y');
        return 1;
      }
      const x = xy[0].trim() + '%';
      const y = xy[1].trim() + '%';
      let mudou = 0;
      if(ax !== x){ el.style.setProperty('--hef-x', x); mudou = 1; }
      if(ay !== y){ el.style.setProperty('--hef-y', y); mudou = 1; }
      return mudou;
    }
    if(alvo === 'atributo'){
      const nome = (el.dataset.hefAtributo || '').trim().toLowerCase();
      if(!atributo_escrevivel(nome)) return 0;
      if(nome === 'title' && el.hasAttribute('data-hef-dica')){
        const dica = (vazio || t === '—') ? '' : t;
        if(el.getAttribute('data-hef-dica') === dica) return 0;
        if(dica === ''){ el.removeAttribute('data-hef-dica'); }
        else { el.setAttribute('data-hef-dica', dica); }
        if(window.__hefDica) window.__hefDica.trocar(el, dica);
        return 1;
      }
      const antes = el.getAttribute(nome);
      if(vazio || t === '—'){
        if(antes === null) return 0;
        el.removeAttribute(nome);
        return 1;
      }
      if(antes === t) return 0;
      el.setAttribute(nome, t);
      return el.getAttribute(nome) === antes ? 0 : 1;
    }
    const so_o_ponto = !!el.firstElementChild
      && Array.prototype.every.call(el.children, function(f){
           return f.classList.contains('pt') && !f.firstElementChild; });
    if(el.textContent !== t || so_o_ponto){
      el.textContent = t;
      if(el.dataset.hefRolar === 'fim'){ el.scrollTop = el.scrollHeight; }
      return 1;
    }
    return 0;
  }
  function achar(raiz, chave){
    const esc = chave.replace(/"/g, '\\"');
    return raiz.querySelectorAll(
      '[data-campo="' + esc + '"],[data-papel="' + esc + '"],[data-hef="' + esc + '"]');
  }
  window.__hef.voo = 0;
  window.__hef.rotulos = {};
  function em_voo(el){
    const n = String(++window.__hef.voo);
    el.setAttribute('data-hef-voo', n);
    el.classList.add('hef-em-voo');
    const dito = el.dataset.hefEmVoo;
    if(dito){
      window.__hef.rotulos[n] = el.innerHTML;
      el.textContent = dito;
    }
    return n;
  }
  window.__hef.voltouDoVoo = function(n, certo){
    const chave = String(n);
    const acende = certo === true ? 'hef-deu-certo'
      : (certo === false ? 'hef-recusou' : '');
    const apaga = acende === 'hef-deu-certo' ? 'hef-recusou' : 'hef-deu-certo';
    let k = 0;
    const piscando = [];
    for(const el of document.querySelectorAll('[data-hef-voo="' + chave + '"]')){
      el.classList.remove('hef-em-voo');
      if(window.__hef.rotulos[chave] !== undefined){
        el.innerHTML = window.__hef.rotulos[chave];
      }
      el.removeAttribute('data-hef-voo');
      if(acende){ el.classList.remove(apaga); el.classList.add(acende); piscando.push(el); }
      k += 1;
    }
    delete window.__hef.rotulos[chave];
    if(piscando.length){
      setTimeout(function(){
        for(const el of piscando){ el.classList.remove(acende); }
      }, 1500);
    }
    return k;
  };
  window.__hef.abaQueVale = function(){
    if(!document.querySelector('.abas-ctl')) return 0;
    const aceso = function(pref){
      const card = pref && document.querySelector('.ctl[data-controle="' + pref + '"]');
      return !!(card && !card.classList.contains('off'));
    };
    const marcado = document.querySelector('.radio-mesa:checked');
    const agora = marcado ? marcado.id.replace(/^c-/, '') : '';
    const querido = window.__hef.alvoPadrao || '';
    if(aceso(agora) && (window.__hef.abaSincronizada || !aceso(querido) || agora === querido)){
      window.__hef.abaSincronizada = true;
      return 0;
    }
    let vez = aceso(querido) ? querido : '';
    if(!vez){
      const primeiro = document.querySelector('.ctl[data-controle]:not(.off)');
      vez = primeiro ? primeiro.dataset.controle : 'p1';
    }
    const radio = document.getElementById('c-' + vez);
    if(!radio || radio.checked) return 0;
    radio.checked = true;
    window.__hef.abaSincronizada = true;
    return 1;
  };
  window.__hef.pintar = function(p){
    let n = 0;
    if(window.__hefDica) window.__hefDica.varrer();
    if('alvo' in p){ window.__hef.alvoPadrao = p.alvo || ''; }
    if(p.fita){
      const f = document.querySelector('.fita');
      if(f){
        const desejado = String(p.fita).trim();
        const agora = f.outerHTML.split(' data-hef-visto="1"').join('');
        if(window.__hef.fitaEscrita === desejado){ }
        else if(agora === desejado){ window.__hef.fitaEscrita = desejado; }
        else if(f.querySelector('.hef-em-voo') || f.closest('.hef-em-voo')){
          window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
        } else {
          f.outerHTML = desejado; n += 1;
          window.__hef.fitaEscrita = desejado;
        }
        for(const c of document.querySelectorAll('.fita [data-campo]')){
          if(c.dataset.hefVisto !== '1'){ c.dataset.hefVisto = '1'; }
        }
      }
    }
    for(const [seletor, html] of Object.entries(p.blocos || {})){
      const alvo = document.querySelector(seletor);
      if(!alvo) continue;
      if(alvo.__hefBloco === html) continue;
      if(alvo.innerHTML === html){ alvo.__hefBloco = html; continue; }
      if(alvo.querySelector('.hef-em-voo') || alvo.closest('.hef-em-voo')){
        window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
        continue;
      }
      alvo.innerHTML = html;
      alvo.__hefBloco = html;
      n += 1;
    }
    for(const caixa of document.querySelectorAll('[data-hef-molde]')){
      const seletor = caixa.dataset.hefMolde;
      const chave = caixa.dataset.hefMoldeConta;
      const lista = (p.mesa || {})[chave];
      if(!seletor || !chave || !Array.isArray(lista)) continue;
      const todos = Array.from(caixa.querySelectorAll(seletor));
      const originais = todos.filter(function(el){ return !el.hasAttribute('data-hef-clone'); });
      if(!originais.length) continue;
      const clones = todos.filter(function(el){ return el.hasAttribute('data-hef-clone'); });
      const querido = lista.length;
      const molde = originais[originais.length - 1];
      while(originais.length + clones.length > Math.max(querido, originais.length)){
        const fora = clones.pop();
        if(fora && fora.parentNode) fora.parentNode.removeChild(fora);
        n += 1;
      }
      let cauda = clones.length ? clones[clones.length - 1] : molde;
      while(originais.length + clones.length < querido){
        const copia = molde.cloneNode(true);
        copia.setAttribute('data-hef-clone', '1');
        if(cauda.parentNode) cauda.parentNode.insertBefore(copia, cauda.nextSibling);
        clones.push(copia);
        cauda = copia;
        n += 1;
      }
      Array.from(caixa.querySelectorAll(seletor)).forEach(function(el, i){
        const sobra = i >= querido;
        if(el.classList.contains('hef-sem-item') !== sobra){
          el.classList.toggle('hef-sem-item', sobra);
          n += 1;
        }
      });
    }
    for(const [k, v] of Object.entries(p.mesa || {})){
      const alvos = achar(document, k);
      if(Array.isArray(v)){
        alvos.forEach(function(el, i){ n += escrever(el, i < v.length ? v[i] : ''); });
        continue;
      }
      if(v !== null && typeof v === 'object') continue;
      for(const el of alvos) n += escrever(el, v);
    }
    for(const pref of (p.vazios || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        if(el.dataset.conectado !== 'nao'){
          el.dataset.conectado = 'nao'; n += 1;
        }
        if(!el.classList.contains('off')){ el.classList.add('off'); }
        if(el.classList.contains('alvo')){ el.classList.remove('alvo'); }
      }
    }
    for(const pref of (p.ocupados || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        if(el.dataset.conectado !== 'sim'){
          el.dataset.conectado = 'sim'; n += 1;
        }
        if(el.classList.contains('off')){ el.classList.remove('off'); }
      }
    }
    for(const [classe, com] of Object.entries(p.marcas || {})){
      for(const pref of ['p1', 'p2', 'p3', 'p4']){
        const quer = (com || []).indexOf(pref) >= 0;
        for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
          if(el.classList.contains(classe) !== quer){
            el.classList.toggle(classe, quer); n += 1;
          }
        }
      }
    }
    for(const [pref, campos] of Object.entries(p.colunas || {})){
      for(const raiz of document.querySelectorAll('[data-controle="' + pref + '"]')){
        for(const [k, v] of Object.entries(campos)){
          if(v !== null && typeof v === 'object') continue;
          for(const el of achar(raiz, k)) n += escrever(el, v);
        }
      }
    }
    n += window.__hef.abaQueVale();
    if(document.documentElement.classList.contains('hef-esperando'))
      document.documentElement.classList.remove('hef-esperando');
    return n;
  };
  if(!window.__hef.ouvindo){
    window.__hef.ouvindo = true;
    document.addEventListener('change', function(ev){ manda_do_alvo(ev); }, true);
    document.addEventListener('click', function(ev){
      manda_do_alvo(ev);
    }, true);
    document.addEventListener('blur', function(ev){
      if(ev.target && ev.target.isContentEditable) manda_do_alvo(ev);
    }, true);
    document.addEventListener('input', function(ev){ manda_do_vivo(ev); }, true);
    window.addEventListener('pagehide', function(){ window.__hefSaindo = true; });
    window.addEventListener('pageshow', function(){
      window.__hefSaindo = false;
      dizer_a_vista();
    });
    document.addEventListener('visibilitychange', function(){
      if(!window.__hefSaindo) dizer_a_vista();
    });
  }
  function dizer_a_vista(){
    const canal = window.webkit && window.webkit.messageHandlers
                  && window.webkit.messageHandlers.hefesto;
    if(!canal) return;
    canal.postMessage(JSON.stringify({
      visibilidade: document.hidden ? 'escondida' : 'vista',
      pagina: location.pathname.split('/').pop()}));
  }
  window.__hef.vivoN = window.__hef.vivoN || 0;
  function manda_do_alvo(ev){
      const alvo = ev.target.closest(
        '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
        '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
        '.r-aplicar,.r-salvar,.r-importar,.r-exportar');
      if(!alvo) return;
      const d = alvo.dataset;
      const doRodape = ((alvo.getAttribute('class') || '').match(/\br-([a-z]+)\b/) || [])[1];
      manda(carga_do_alvo(
        alvo, ev, d.gesto || d.hefGesto || d.papel || doRodape || 'clique',
        em_voo(alvo)));
  }
  function manda_do_vivo(ev){
      const alvo = ev.target.closest('[data-hef-vivo]');
      if(!alvo) return;
      const g = String(alvo.dataset.hefVivo || '').trim();
      if(!g) return;
      const o = carga_do_alvo(alvo, ev, g, '');
      o.vivoChave = g + '|'
        + (alvo.dataset.campo || alvo.dataset.hef || alvo.dataset.papel || '')
        + '|' + String(o.controle || '');
      o.vivo = String(++window.__hef.vivoN);
      manda(o);
  }
  function carga_do_alvo(alvo, ev, gesto, voo){
      const d = alvo.dataset;
      const dono = alvo.closest(
        '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
      const tudo = Object.assign({}, d);
      return Object.assign(tudo, {
        voo: voo,
        gesto: gesto,
        vivo: '', vivoChave: '',
        modo: d.modo || '', forca: d.forca || '', player: d.player || '',
        lado: d.lado || '', campo: d.campo || '', hef: d.hef || '',
        hex: d.hex || '', sensor: d.sensor || '', rota: d.rota || '',
        mudo: d.mudo || '', micModo: d.micModo || '', v: d.v || '',
        controle: dono ? (dono.dataset.controle || dono.dataset.uniq || '')
                       : (window.__hef.alvoPadrao || ''),
        valor: (('value' in alvo) ? String(alvo.value ?? '') : ''),
        rotulo: (alvo.selectedOptions && alvo.selectedOptions[0]
                 ? alvo.selectedOptions[0].textContent.trim() : ''),
        tipo: (alvo.tagName || '').toLowerCase(),
        evento: ev.type,
        carimbo: (performance.timeOrigin || 0) + ev.timeStamp,
        forma: (function(){
          const pedido = alvo.dataset.hefForma;
          if(!pedido) return null;
          const cx = pedido === '@controle'
            ? alvo.closest(
                '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]')
            : document.getElementById(pedido);
          if(!cx) return null;
          const fora = {};
          for(const el of cx.querySelectorAll('[data-linha],[data-campo]')){
            if(el.type === 'radio' && !el.checked) continue;
            const chave = el.dataset.linha || el.dataset.campo;
            fora[chave] = ('value' in el)
              ? String(el.value ?? '') : (el.textContent || '').trim();
          }
          return fora;
        })(),
        texto: (alvo.textContent || '').trim().slice(0, 60),
      });
  }
  function manda(o){
    o.pagina = location.pathname.split('/').pop();
    window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o));
  }
  dizer_a_vista();
  return 'ok';
})();
"""


DICA_DA_CASA = r"""
(function(){
  if(window.__hefDica && window.__hefDica.instalada) return 'ja';
  if(!document.body) return 'sem body';
  var SVG = 'http://www.w3.org/2000/svg';
  var ATRASO = 500;
  var caixa = document.createElement('div');
  caixa.id = 'hef-dica';
  caixa.setAttribute('role', 'tooltip');
  caixa.style.cssText =
    'position:fixed;left:0;top:0;z-index:2147483000;display:none;'
    + 'max-width:340px;pointer-events:none;white-space:pre-line;'
    + 'background:var(--elevated,#2b2d3a);border:1px solid var(--linha,#44475a);'
    + 'border-radius:7px;padding:9px 11px;font-size:11.5px;line-height:1.5;'
    + 'color:var(--texto-suave,#d8dae6);text-align:left;font-weight:400;'
    + 'box-shadow:0 8px 24px rgba(0,0,0,.5);';
  document.body.appendChild(caixa);

  var E = {alvo: null, texto: '', tempo: 0, x: 0, y: 0, aberta: false, abriu: 0,
           peloFoco: false, descrito: null};

  var PAPEL_SEM_NOME = {presentation: 1, none: 1, generic: 1};
  var TAG_QUE_ACEITA_NOME = {a: 1, button: 1, input: 1, select: 1, textarea: 1,
    summary: 1, img: 1, area: 1, iframe: 1, meter: 1, progress: 1, output: 1,
    details: 1, dialog: 1, fieldset: 1, optgroup: 1, option: 1, audio: 1,
    video: 1, th: 1, table: 1, svg: 1};
  var TAG_NOME_DO_CONTEUDO = {a: 1, button: 1, summary: 1, th: 1, td: 1,
    option: 1, optgroup: 1, legend: 1};
  var PAPEL_NOME_DO_CONTEUDO = {button: 1, link: 1, tab: 1, menuitem: 1,
    menuitemcheckbox: 1, menuitemradio: 1, option: 1, checkbox: 1, radio: 1,
    switch: 1, heading: 1, treeitem: 1, gridcell: 1, cell: 1, columnheader: 1,
    rowheader: 1, tooltip: 1};
  var NOSSOS = (typeof WeakMap === 'function') ? new WeakMap() : null;

  function texto_que_nomeia(no, fundo){
    if(!no || fundo > 12) return '';
    if(no.nodeType === 3) return no.nodeValue || '';
    if(no.nodeType !== 1) return '';
    if(no.namespaceURI === SVG
       && (no.localName === 'title' || no.localName === 'desc')) return '';
    if(no.getAttribute && no.getAttribute('aria-hidden') === 'true') return '';
    var s = '', f = no.firstChild;
    while(f){ s += texto_que_nomeia(f, fundo + 1); f = f.nextSibling; }
    return s;
  }
  function rotulo_de_formulario(el){
    if(el.id){
      var id = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id;
      var l = document.querySelector('label[for="' + id + '"]');
      if(l && texto_que_nomeia(l, 0).trim()) return true;
    }
    var p = el.parentElement, n = 0;
    while(p && n < 8){
      if(p.localName === 'label' && texto_que_nomeia(p, 0).trim()) return true;
      p = p.parentElement; n += 1;
    }
    return false;
  }
  function tem_nome(el){
    if(String(el.getAttribute('aria-label') || '').trim()) return true;
    var lb = String(el.getAttribute('aria-labelledby') || '').trim();
    if(lb){
      var ids = lb.split(/\s+/);
      for(var i = 0; i < ids.length; i++){
        var o = document.getElementById(ids[i]);
        if(o && texto_que_nomeia(o, 0).trim()) return true;
      }
    }
    var tag = el.localName;
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(tag === 'img' || tag === 'area') return el.hasAttribute('alt');
    if(tag === 'input'){
      var t = String(el.getAttribute('type') || 'text').toLowerCase();
      if(t === 'button' || t === 'submit' || t === 'reset'){
        return !!String(el.getAttribute('value') || '').trim();
      }
      if(t === 'image') return !!String(el.getAttribute('alt') || '').trim();
      return rotulo_de_formulario(el);
    }
    if(tag === 'select' || tag === 'textarea' || tag === 'meter'
       || tag === 'progress') return rotulo_de_formulario(el);
    if(tag === 'option' && String(el.getAttribute('label') || '').trim()){
      return true;
    }
    if(papel ? PAPEL_NOME_DO_CONTEUDO[papel] : TAG_NOME_DO_CONTEUDO[tag]){
      return !!texto_que_nomeia(el, 0).trim();
    }
    return false;
  }
  function aceita_nome(el){
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(papel) return !PAPEL_SEM_NOME[papel];
    return !!TAG_QUE_ACEITA_NOME[el.localName];
  }
  function e_nosso(el){
    if(!NOSSOS || !NOSSOS.has(el)) return false;
    return el.getAttribute('aria-label') === NOSSOS.get(el);
  }
  function vestir_nome(el, t){
    if(!el || !t || !el.getAttribute) return;
    if(!aceita_nome(el) || tem_nome(el)) return;
    el.setAttribute('aria-label', t);
    if(NOSSOS) NOSSOS.set(el, t);
  }
  function trocar_nome(el, t){
    if(!el || !e_nosso(el)) return;
    if(t){ el.setAttribute('aria-label', t); NOSSOS.set(el, t); }
    else { el.removeAttribute('aria-label'); NOSSOS.delete(el); }
  }
  function eco_no_vizinho(svg, t){
    var pai = svg.parentElement;
    if(!pai) return false;
    var fora = texto_que_nomeia(pai, 0).trim().toLowerCase();
    if(!fora) return false;
    return fora.indexOf(String(t).trim().toLowerCase()) >= 0;
  }
  function vestir_nome_do_desenho(dono, t){
    if(!dono || !t || !dono.getAttribute) return;
    if(String(dono.getAttribute('aria-label') || '').trim()) return;
    if(String(dono.getAttribute('aria-labelledby') || '').trim()) return;
    if(dono.getAttribute('aria-hidden') === 'true') return;
    if(dono.localName === 'svg'){
      if(eco_no_vizinho(dono, t)){
        dono.setAttribute('aria-hidden', 'true');
        return;
      }
      if(!dono.getAttribute('role')
         && dono.querySelectorAll('title').length <= 1){
        dono.setAttribute('role', 'img');
      }
    }
    dono.setAttribute('aria-label', t);
    if(NOSSOS) NOSSOS.set(dono, t);
  }

  function colher(raiz){
    var n = 0;
    var lista = raiz.querySelectorAll('[title]');
    for(var i = 0; i < lista.length; i++){
      var el = lista[i];
      if(el === caixa) continue;
      var d = String(el.getAttribute('title') || '').trim();
      el.setAttribute('data-hef-dica', d);
      el.removeAttribute('title');
      vestir_nome(el, d);
      n += 1;
    }
    var tt = raiz.querySelectorAll('svg title:not([data-hef-dica])');
    for(var j = 0; j < tt.length; j++){
      var t = tt[j];
      if(t.namespaceURI !== SVG) continue;
      var st = String(t.textContent || '').trim();
      t.setAttribute('data-hef-dica', st);
      t.textContent = '';
      vestir_nome_do_desenho(t.parentElement, st);
      n += 1;
    }
    return n;
  }

  function textoDe(el){
    if(!el || !el.getAttribute) return null;
    if(el.hasAttribute('data-dica')){
      var dd = String(el.getAttribute('data-dica') || '').trim();
      if(dd) return dd;
    }
    if(el.hasAttribute('data-hef-dica')){
      var g = String(el.getAttribute('data-hef-dica') || '').trim();
      return g ? g : '';
    }
    if(el.hasAttribute('title')){
      var t = String(el.getAttribute('title') || '').trim();
      el.setAttribute('data-hef-dica', t);
      el.removeAttribute('title');
      vestir_nome(el, t);
      return t ? t : '';
    }
    return null;
  }
  function svgTituloDe(el){
    if(!el || el.namespaceURI !== SVG) return null;
    var f = el.firstChild;
    while(f){
      if(f.nodeType === 1 && f.localName === 'title' && f.namespaceURI === SVG){
        if(!f.hasAttribute('data-hef-dica')){
          var ft = String(f.textContent || '').trim();
          f.setAttribute('data-hef-dica', ft);
          f.textContent = '';
          vestir_nome_do_desenho(el, ft);
        }
        var s = String(f.getAttribute('data-hef-dica') || '').trim();
        if(s) return {no: f, texto: s};
        return null;
      }
      f = f.nextSibling;
    }
    return null;
  }
  function achar(no){
    var e = (no && no.nodeType === 1) ? no : (no ? no.parentElement : null);
    while(e){
      var s = svgTituloDe(e);
      if(s) return {el: e, texto: s.texto, svg: s.no};
      var t = textoDe(e);
      if(t) return {el: e, texto: t, svg: null};
      if(t === '') return null;
      e = e.parentElement;
    }
    return null;
  }
  function descrever(el, liga){
    if(!el || !el.getAttribute) return;
    var lista = String(el.getAttribute('aria-describedby') || '').split(/\s+/)
      .filter(function(t){ return t && t !== 'hef-dica'; });
    if(liga) lista.push('hef-dica');
    if(lista.length) el.setAttribute('aria-describedby', lista.join(' '));
    else el.removeAttribute('aria-describedby');
  }
  function esconder(){
    if(E.tempo){ clearTimeout(E.tempo); E.tempo = 0; }
    caixa.style.display = 'none';
    E.aberta = false;
    if(E.descrito){ descrever(E.descrito, false); E.descrito = null; }
  }
  function limpar(){
    esconder();
    E.alvo = null; E.texto = ''; E.peloFoco = false;
  }
  function mostrar(){
    E.tempo = 0;
    if(!E.alvo || !document.contains(E.alvo.el)){ limpar(); return; }
    caixa.textContent = E.texto;
    caixa.style.display = 'block';
    E.aberta = true;
    E.abriu += 1;
    if(E.descrito && E.descrito !== E.alvo.el) descrever(E.descrito, false);
    E.descrito = E.alvo.el;
    descrever(E.descrito, true);
    var r = caixa.getBoundingClientRect();
    var x = E.x + 14, y = E.y + 20;
    if(x + r.width + 6 > window.innerWidth){
      x = Math.max(6, window.innerWidth - r.width - 6);
    }
    if(y + r.height + 6 > window.innerHeight){
      y = Math.max(6, E.y - r.height - 12);
    }
    caixa.style.left = Math.round(x) + 'px';
    caixa.style.top = Math.round(y) + 'px';
  }
  document.addEventListener('mousemove', function(ev){
    E.x = ev.clientX; E.y = ev.clientY;
    var a = achar(ev.target);
    if(!a){ if(E.alvo) limpar(); return; }
    if(!E.alvo || a.el !== E.alvo.el || a.svg !== E.alvo.svg){
      limpar();
      E.alvo = a; E.texto = a.texto;
      E.tempo = setTimeout(mostrar, ATRASO);
      return;
    }
    if(!E.aberta && !E.tempo){ E.tempo = setTimeout(mostrar, ATRASO); }
  }, true);
  document.addEventListener('mouseout', function(ev){
    if(!ev.relatedTarget) limpar();
  }, true);
  document.addEventListener('focusin', function(ev){
    var el = ev.target, visivel = false;
    try { visivel = !!(el && el.matches && el.matches(':focus-visible')); } catch(_){ visivel = false; }
    if(!visivel) return;
    var a = achar(el);
    if(!a) return;
    var r = el.getBoundingClientRect();
    limpar();
    E.alvo = a; E.texto = a.texto; E.peloFoco = true;
    E.x = r.left - 14; E.y = r.bottom - 16;
    mostrar();
  }, true);
  document.addEventListener('focusout', function(){
    if(E.peloFoco){ E.peloFoco = false; limpar(); }
  }, true);
  document.addEventListener('mousedown', function(){ esconder(); }, true);
  document.addEventListener('wheel', function(){ esconder(); }, true);
  document.addEventListener('scroll', function(){ esconder(); }, true);
  document.addEventListener('keydown', function(){ esconder(); }, true);
  window.addEventListener('blur', function(){ limpar(); });

  var colhidas = colher(document);

  window.__hefDica = {
    instalada: true,
    colhidas: colhidas,
    aberta: function(){ return E.aberta; },
    texto: function(){ return E.aberta ? E.texto : ''; },
    quantas: function(){ return E.abriu; },
    varrer: function(){
      if(E.alvo && !document.contains(E.alvo.el)){
        esconder(); E.alvo = null; E.texto = '';
      }
      if(document.querySelector('[title]')
         || document.querySelector('svg title:not([data-hef-dica])')){
        window.__hefDica.colhidas += colher(document);
      }
    },
    trocar: function(el, t){
      trocar_nome(el, String(t || ''));
      if(E.alvo && E.alvo.el === el){
        E.texto = String(t);
        if(E.aberta) caixa.textContent = E.texto;
      }
    },
  };
  return 'ok';
})();
"""


def _com_dono(ctx: pacotes.Contexto) -> list[str]:
    """Os `pN` que têm controle DE VERDADE agora — QUEM-TEM-DONO-01, 03/09/2026.

    NASCEU DE UMA REGRESSÃO, no mesmo dia. O passo `1c` do piloto (o que
    REABRE o cartão de um controle que chega) lia `carga["ocupados"]`, e a
    primeira versão daquela conta era `set(colunas)` — as colunas que a aba
    emitiu. Medido no DOM vivo, com UM controle na bancada: a `03-gatilhos`
    manda coluna para os QUATRO lugares, porque as vazias levam travessão de
    propósito, e o piloto passou a escrever `data-conectado="sim"` em dois
    lugares onde não há aparelho nenhum.

    **TER COLUNA NÃO É TER DONO.** A aba manda coluna para desenhar; quem diz
    quem está aqui é a MESA. Esta função é essa pergunta, e ela tem um dono só.

    A DECISÃO QUE ELA SUSTENTA é de 03/09/2026: *"tem que aparecer desligado
    enquanto não tem nenhum controle. A partir do momento que tiver, ele aparece
    o controle devidamente conectado."*
    """
    prefs: list[str] = []
    por_uniq = {str(c.get("uniq") or ""): c.get("pref") for c in ctx.mesa}
    for c in ctx.conectados:
        pref = por_uniq.get(str(c.get("uniq") or ""))
        if pref:
            prefs.append(str(pref))
    return prefs


class _EscolhaDaFita:
    """O único estado que o chip muda. Nada de perfil, nada de daemon."""

    def __init__(self) -> None:
        self.uniq = ""


ESCOLHA_DA_FITA = _EscolhaDaFita()


def _devolver_o_alvo_a_todos(ctx: pacotes.Contexto, ipc: Any) -> None:
    """O «Todos» da fita desfaz o «só este»: `controller.target.set` com `index: null`, uma vez.

    O serviço guarda UM alvo de saída (`output_target_index`); com um `index`, luz, gatilhos,
    luzes do jogador, vibração e luz do microfone miram só aquele controle, posto pelo «só este»
    da 08. Sem esta chamada o chip só escolhia o lugar da fita (medido no piloto em 20/10/2026).
    Só quando o estado diz um número: `None` já é «todos», e a chave ausente é serviço mudo.
    Se o serviço recusa, o clique recusa dizendo e a fita não muda.
    """
    if ctx.state.get("output_target_index") is None:
        return
    if not ipc.chamar("controller.target.set", index=None):
        raise RuntimeError(
            "O serviço não devolveu as ações a todos os controles — o alvo "
            "segue em um só.")


def _escolher_na_fita(ctx: pacotes.Contexto, o: dict[str, Any],
                      ipc: Any) -> dict[str, Any]:
    """O clique no chip do `Selecionar:` — ele ESCOLHE, e só o «Todos» fala com o serviço.

    O QUE ELE NÃO FAZ: não troca de perfil e não grava no disco do usuário. Só o «Todos»
    fala com o serviço (`_devolver_o_alvo_a_todos`, escolha de 23/10/2026); os chips de um
    controle apontam a aba, e o alvo de saída do serviço é o «só este» da 08.

    O `("*", …)` É O MESMO CORINGA DO RODAPÉ: a fita mora no `topo.html`, o
    esqueleto das dez, e registrá-la por página seria a mesma linha dez vezes.

    ELE RECUSA DIZENDO quando o `pref` clicado não está na mesa — um chip de um
    controle que saiu entre o desenho e o clique. Escolher calado o primeiro que
    sobrou é como a tela passa a mostrar um aparelho e a mexer noutro.

    E ELE MANDA A PRÓPRIA FRASE, que desde 13/09/2026 vai ao diário da janela e
    não à tela (TELA-CALADA-01: a tarja de rodapé que a mostrava saiu por pedido, *"em todas as abas da interface"*). Na tela, o clique responde pela
    piscada (`MS_DA_PISCADA`). O cartão fica de fora de propósito: ver
    `_endereco_do_chip`.
    """
    pref = str(o.get("pref") or "").strip()
    if pref == "todos":
        if not monta.cabe_o_todos(ctx.mesa):
            raise ValueError(
                "o chip `Todos` não se escolhe com um controle só na mesa: "
                "ele É a escolha.")
        _devolver_o_alvo_a_todos(ctx, ipc)
        ESCOLHA_DA_FITA.uniq = "todos"
        return {"recado": f"Esta aba passa a mirar os {len(ctx.mesa)} controles."}
    for c in ctx.mesa:
        if str(c.get("pref") or "") == pref:
            ESCOLHA_DA_FITA.uniq = norm_mac(str(c.get("uniq") or "")) or ""
            return {"recado": f"Esta aba passa a mirar o {pref.upper()}."}
    raise ValueError(
        f"o chip {pref!r} não está na mesa de agora — o controle saiu entre o "
        f"desenho da fita e o clique.")


def _registrar_a_fita() -> None:
    """O gesto da fita no despachante, uma vez só, por qualquer dos dois nomes."""
    if ("*", monta.GESTO_DA_FITA) not in pacotes.GESTOS:
        pacotes.gesto("*", monta.GESTO_DA_FITA)(_escolher_na_fita)


_FECHAR_A_JANELA: list[Callable[[], None]] = []

ITENS_DO_MENU_NA_SISTEMA = {
    "menu-atualizar": "atualizar",
    "menu-desligar": "parar-ou-retomar",
    "menu-reiniciar": "reiniciar",
}

ITENS_DO_MENU_NA_JOGAR = {
    "menu-reconectar": "reconectar",
}

O_QUE_O_MENU_MEXE = {
    "menu-desligar": "para ou liga o serviço do Hefesto pela aba Sistema",
    "menu-reiniciar": "reinicia o serviço do Hefesto pela aba Sistema",
    "menu-fechar": "fecha a janela do Hefesto",
}


def _gesto_do_menu(nome_na_aba: str, aba: str = "09-sistema.html",
                   ) -> Callable[[Any, dict[str, Any], Any], Any]:
    """O gesto do menu que chama o de uma aba, procurado na hora (a tabela se enche ao importar)."""
    def agir(ctx: Any, o: dict[str, Any], ipc: Any) -> Any:
        return pacotes.GESTOS[(aba, nome_na_aba)](ctx, o, ipc)
    return agir


def _fechar_pelo_menu(ctx: Any, o: dict[str, Any], ipc: Any) -> None:
    """`Fechar` do menu do botão direito: fecha a janela, no fio do GTK."""
    if _FECHAR_A_JANELA:
        GLib.idle_add(_FECHAR_A_JANELA[0])


def _registrar_o_menu() -> None:
    """Os gestos do menu do botão direito no despachante, uma vez só e para toda página."""
    for gesto_do_menu, na_sistema in ITENS_DO_MENU_NA_SISTEMA.items():
        if ("*", gesto_do_menu) not in pacotes.GESTOS:
            pacotes.gesto("*", gesto_do_menu, grava=O_QUE_O_MENU_MEXE.get(gesto_do_menu, ""))(
                _gesto_do_menu(na_sistema))
    for gesto_do_menu, na_jogar in ITENS_DO_MENU_NA_JOGAR.items():
        if ("*", gesto_do_menu) not in pacotes.GESTOS:
            pacotes.gesto("*", gesto_do_menu)(_gesto_do_menu(na_jogar, "01-jogar.html"))
    if ("*", "menu-fechar") not in pacotes.GESTOS:
        pacotes.gesto("*", "menu-fechar", grava=O_QUE_O_MENU_MEXE["menu-fechar"])(
            _fechar_pelo_menu)


def _a_fita_desta_pagina_escolhe(pagina: str) -> bool:
    """`monta.a_fita_escolhe`, sem derrubar a janela numa página que não é aba."""
    try:
        return monta.a_fita_escolhe(pagina)
    except SystemExit:
        return False


def _pref_escolhido(mesa: list[dict[str, Any]]) -> str:
    """Que `pref` a fita acende AGORA, traduzido da escolha do usuário."""
    if not mesa:
        return "todos"
    se = ESCOLHA_DA_FITA.uniq
    if se == "todos":
        return "todos"
    if se:
        for c in mesa:
            if norm_mac(str(c.get("uniq") or "")) == se:
                return str(c["pref"])
    return str(mesa[0]["pref"])


def _fita(mesa: list[dict[str, Any]], pagina: str) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho."""
    try:
        return monta.fita(ativo=_pref_escolhido(mesa),
                          inerte=not _a_fita_desta_pagina_escolhe(pagina),
                          mesa=mesa)
    except (Exception, SystemExit):
        return ""


SELETOR = ("(function(p){const t=window.__hefTocar;const el=t.achar(document,p);"
           "if(el)t.tocar(el,p);})(%s)")

CLIQUE_COM_ALVO = r"""
(function(g, prefs){
  const t = window.__hefTocar;
  if(!t) return 'SEM O TOCAR';
  for(const p of prefs){
    for(const bloco of document.querySelectorAll('[data-controle="' + p + '"]')){
      const dentro = t.achar(bloco, g);
      if(dentro){ window.__hef.alvoPadrao = p; t.tocar(dentro, g); return 'no bloco de ' + p; }
    }
  }
  const el = t.achar(document, g);
  if(!el) return 'NAO ACHEI NA PAGINA';
  const dono = el.closest(
    '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
  if(dono){
    const q = dono.dataset.controle || dono.dataset.uniq || '';
    window.__hef.alvoPadrao = q;
    t.tocar(el, g);
    return 'no bloco de ' + q;
  }
  window.__hef.alvoPadrao = prefs[0] || '';
  t.tocar(el, g);
  return 'ALVO FORCADO ' + (prefs[0] || '(mesa vazia)');
})(%s, %s)
"""

GESTO_DO_START = "salvar-e-aplicar"

NAV_INSTALAR = r"""
(function(){
  if(window.__hefNav) return;
  const SEL = '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
    '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
    '.r-aplicar,.r-salvar,.r-importar,.r-exportar,a[href],button';
  function aberta(){
    for(const d of document.querySelectorAll('[role="dialog"],.tela-nova')){
      if(d.getAttribute('aria-hidden') !== 'true' && !d.hasAttribute('inert') && presente(d)) return d;
    }
    return null;
  }
  function presente(el){
    return el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  }
  function visivel(el){
    if(el.closest('[aria-hidden="true"],[inert],[hidden]')) return false;
    if(el.disabled) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  }
  function dono(el){
    let b = el.closest('[data-controle]');
    while(b && !/^p[1-4]$/.test(b.dataset.controle || '')){
      b = b.parentElement ? b.parentElement.closest('[data-controle]') : null;
    }
    return b ? b.dataset.controle : '';
  }
  function nome(el){
    const d = el.dataset;
    const r = Array.from(el.classList).find(function(k){ return k.indexOf('r-') === 0; }) || '';
    const sem = el.getAttribute('href') || el.id || (el.textContent || '').trim().slice(0, 24);
    return [dono(el), d.gesto || d.hefGesto || d.papel || d.modo || d.forca || d.player ||
            d.sensor || d.rota || d.mudo || d.micModo || r || sem, d.campo || '', d.v || ''].join('|');
  }
  function lista(){
    const raiz = aberta() || document;
    const vistos = {};
    const fora = [];
    for(const el of raiz.querySelectorAll(SEL)){
      if(el.dataset.campo === 'fita-chip' || el.closest('.fita') || !visivel(el)) continue;
      const base = nome(el);
      vistos[base] = (vistos[base] || 0) + 1;
      fora.push({el: el, endereco: base + '#' + vistos[base]});
    }
    return fora;
  }
  function achar(endereco){
    for(const c of lista()) if(c.endereco === endereco) return c.el;
    return null;
  }
  window.__hefNav = {
    ler: function(){
      return JSON.stringify({
        popup: !!aberta(), largura: innerWidth, altura: innerHeight,
        caixas: lista().map(function(c){
          const r = c.el.getBoundingClientRect();
          const tag = c.el.tagName.toLowerCase();
          const tipo = tag === 'select' ? 'lista'
            : (tag === 'input' && c.el.type === 'range') ? 'trilho' : '';
          return {endereco: c.endereco, x: r.left, y: r.top, w: r.width, h: r.height,
                  tipo: tipo, dono: dono(c.el)};
        })
      });
    },
    aplicar: function(ops, molduras){
      for(const op of ops){
        if(op.op === 'fechar'){
          const d = aberta();
          const f = d && d.querySelector('.fechar');
          if(f) f.click();
          else document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
        } else {
          const el = achar(op.endereco);
          if(!el) continue;
          if(op.op === 'clicar'){
            if(window.__hef && op.pref) window.__hef.alvoPadrao = op.pref;
            el.click();
          } else if(op.op === 'escolha'){
            const n = el.options.length;
            const escolhivel = function(o){
              return !o.disabled && !o.hidden &&
                !(o.parentElement && o.parentElement.tagName === 'OPTGROUP' && o.parentElement.disabled);
            };
            let i = el.selectedIndex;
            for(let k = 0; k < n; k++){
              i = ((i + op.passo) % n + n) % n;
              if(escolhivel(el.options[i])) break;
            }
            if(n && !escolhivel(el.options[i])) i = el.selectedIndex;
            if(i !== el.selectedIndex){
              el.selectedIndex = i;
              el.dispatchEvent(new Event('change', {bubbles: true}));
            }
          } else if(op.op === 'trilho'){
            if(op.passo > 0) el.stepUp(); else el.stepDown();
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
          }
        }
      }
      this.molduras(molduras || []);
      return ops.length;
    },
    molduras: function(molduras){
      const oposta = function(cor){
        const k = document.createElement('i');
        k.style.color = cor || ''; document.body.appendChild(k);
        const v = (getComputedStyle(k).color.match(/\d+(\.\d+)?/g) || []).map(Number);
        k.remove();
        if(!cor || v.length < 3) return '#fff';
        return 'rgb(' + (255 - v[0]) + ',' + (255 - v[1]) + ',' + (255 - v[2]) + ')';
      };
      for(const m of document.querySelectorAll('.hef-nav-moldura')) m.remove();
      const por = {};
      for(const m of molduras){
        const el = achar(m.endereco);
        if(!el) continue;
        const n = por[m.endereco] = (por[m.endereco] || 0) + 1;
        const r = el.getBoundingClientRect();
        const folga = 2 + (n - 1) * 4;
        const q = document.createElement('div');
        q.className = 'hef-nav-moldura';
        q.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483000;' +
          'border-radius:8px;box-sizing:border-box;' +
          'left:' + (r.left - folga) + 'px;top:' + (r.top - folga) + 'px;' +
          'width:' + (r.width + 2 * folga) + 'px;height:' + (r.height + 2 * folga) + 'px;' +
          'border:' + (m.dentro ? 3 : 2) + 'px solid ' + (m.cor || 'var(--acento, #6aa0ff)') +
          (m.dentro ? ';box-shadow:0 0 0 3px ' + oposta(m.cor) : '');
        const p = document.createElement('span');
        p.textContent = (m.pref || '').toUpperCase();
        p.style.cssText = 'position:absolute;top:-10px;right:-6px;font:600 10px/14px sans-serif;' +
          'padding:0 4px;border-radius:6px;color:#fff;background:' + (m.cor || 'var(--acento, #6aa0ff)');
        q.appendChild(p);
        document.body.appendChild(q);
      }
    }
  };
})();
"""

NAV_LER = "window.__hefNav.ler()"

PEDIR_A_PINTURA = r"""
(window.__hef && window.__hef.pintar) ? window.__hef.pintar(CARGA) : -1
"""

LER_CAMPOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('[data-campo],[data-papel],[data-hef]')){
    const chave = el.dataset.campo || el.dataset.papel || el.dataset.hef || '';
    const bloco = el.closest(
      '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
    const dono = bloco ? (bloco.dataset.controle || bloco.dataset.uniq || '') : '';
    const alvo = el.dataset.hefAlvo || 'texto';
    let v;
    if(alvo === 'largura'){ v = el.style.width; }
    else if(alvo === 'altura'){ v = el.style.height; }
    else if(alvo === 'valor'){ v = ('value' in el) ? String(el.value ?? '') : ''; }
    else if(alvo === 'posicao'){
      const px = el.style.getPropertyValue('--hef-x').trim().replace(/%$/, '');
      const py = el.style.getPropertyValue('--hef-y').trim().replace(/%$/, '');
      v = (px || py) ? (px + ',' + py) : '';
    }
    else if(alvo === 'cor'){ v = el.style.color; }
    else if(alvo === 'atributo'){
      const qual = (el.dataset.hefAtributo || '').trim().toLowerCase();
      v = el.getAttribute(qual) || '';
      if(!v && qual === 'title') v = el.getAttribute('data-hef-dica') || '';
    }
    else if(alvo === 'marcado'){
      v = el.checked ? 'sim' : '';
    }
    else if(alvo === 'classe'){
      const c = el.dataset.hefClasse || 'on';
      v = el.classList.contains(c) ? (el.dataset.hefQuando || 'sim') : '';
    }
    else { v = (el.textContent || '').replace(/\s+/g, ' ').trim(); }
    fora.push([chave, dono, alvo, v, el.dataset.hefVisto === '1']);
  }
  return JSON.stringify(fora);
})()
"""

VOLTAS_ATE_ASSENTAR = 20

RAJADA_DE_ESTADOS = 20

OBSERVAR_MUTACOES = r"""
(function(){
  window.__hef = window.__hef || {};
  if(window.__hef.observador){ window.__hef.observador.disconnect(); }
  const linhas = {};
  window.__hef.mutacoes = linhas;
  window.__hef.mutacoesTotal = 0;
  function endereco(no){
    let el = (no && no.nodeType === 1) ? no : (no ? no.parentElement : null);
    while(el && el.getAttribute){
      const c = el.getAttribute('data-campo') || el.getAttribute('data-papel')
                || el.getAttribute('data-hef');
      if(c) return c;
      if(el.classList && el.classList.contains('fita')) return '(a fita)';
      el = el.parentElement;
    }
    return '(sem endereco)';
  }
  function somar(campo, tipo, detalhe, nos){
    const k = campo + '|' + tipo + '|' + detalhe;
    let l = linhas[k];
    if(!l){ l = linhas[k] = {campo: campo, tipo: tipo, detalhe: detalhe,
                             n: 0, nos: 0}; }
    l.n += 1;
    l.nos += (nos || 0);
    window.__hef.mutacoesTotal += 1;
  }
  const obs = new MutationObserver(function(regs){
    for(const r of regs){
      const onde = endereco(r.target);
      if(r.type === 'attributes'){
        somar(onde, 'attributes', r.attributeName || '?', 0);
      } else if(r.type === 'childList'){
        somar(onde, 'childList', '(filhos)',
              r.addedNodes.length + r.removedNodes.length);
      } else {
        somar(onde, 'characterData', '(texto)', 0);
      }
    }
  });
  obs.observe(document.documentElement, {
    attributes: true, childList: true, characterData: true, subtree: true});
  window.__hef.observador = obs;
  window.__hef.mutacoesDesde = Date.now();
  return 'observando';
})()
"""

LER_MUTACOES = r"""
(function(){
  const h = window.__hef || {};
  const linhas = [];
  for(const k of Object.keys(h.mutacoes || {})) linhas.push(h.mutacoes[k]);
  linhas.sort(function(a, b){ return b.n - a.n; });
  return JSON.stringify({
    total: h.mutacoesTotal || 0,
    ms: Date.now() - (h.mutacoesDesde || Date.now()),
    blocos_adiados: h.blocosAdiados || 0,
    linhas: linhas
  });
})()
"""

ALVOS_DO_TAMANHO = (".janela", ".miolo", ".registro")

OBSERVAR_TAMANHO = r"""
(function(){
  window.__hef = window.__hef || {};
  if(window.__hef.observadorDeTamanho){ window.__hef.observadorDeTamanho.disconnect(); }
  const tabela = {};
  window.__hef.tamanhos = tabela;
  window.__hef.tamanhoDesde = Date.now();
  const ausentes = [];
  function ficha(nome){
    if(!tabela[nome]){
      tabela[nome] = {alvo: nome, n: 0, alturas: {}, larguras: {}, partiu: '', anterior: ''};
    }
    return tabela[nome];
  }
  function ver(nome, w, h, primeira){
    const f = ficha(nome);
    const caixa = w.toFixed(1) + 'x' + h.toFixed(1);
    if(primeira){ f.partiu = caixa; f.anterior = caixa;
      f.alturas[h.toFixed(1)] = 1; f.larguras[w.toFixed(1)] = 1; return; }
    if(caixa === f.anterior){ return; }
    f.anterior = caixa;
    f.n += 1;
    f.alturas[h.toFixed(1)] = (f.alturas[h.toFixed(1)] || 0) + 1;
    f.larguras[w.toFixed(1)] = (f.larguras[w.toFixed(1)] || 0) + 1;
  }
  const vistos = new Set();
  const obs = new ResizeObserver(function(regs){
    for(const r of regs){
      const nome = r.target.__hefNome;
      const primeira = !vistos.has(nome);
      vistos.add(nome);
      ver(nome, r.contentRect.width, r.contentRect.height, primeira);
    }
  });
  for(const sel of ALVOS){
    const el = document.querySelector(sel);
    if(!el){ ausentes.push(sel); continue; }
    el.__hefNome = sel;
    obs.observe(el);
  }
  ficha('(vista)');
  let primeiraVista = true;
  const aoVista = function(){
    ver('(vista)', window.innerWidth, window.innerHeight, primeiraVista);
    primeiraVista = false;
  };
  window.__hef.aoVista = aoVista;
  window.addEventListener('resize', aoVista);
  aoVista();
  window.__hef.observadorDeTamanho = obs;
  window.__hef.tamanhoAusentes = ausentes;
  return 'observando';
})()
""".replace("ALVOS", str(list(ALVOS_DO_TAMANHO)))

LER_TAMANHO = r"""
(function(){
  const h = window.__hef || {};
  const fichas = [];
  for(const k of Object.keys(h.tamanhos || {})) fichas.push(h.tamanhos[k]);
  return JSON.stringify({
    ms: Date.now() - (h.tamanhoDesde || Date.now()),
    ausentes: h.tamanhoAusentes || [],
    fichas: fichas
  });
})()
"""

_METODO_DO_GESTO = {
    "atualizar": "daemon.reload", "modo-dualsense": "gamepad.emulation.set",
    "modo-xbox": "gamepad.emulation.set", "modo-navegacao": "mouse.emulation.set",
    "hefesto": "native.mode.set", "ativar": "profile.switch",
    "aplicar": "profile.reaplicar", "reconectar": "coop.sync",
}

PERIGOSOS: set[tuple[str, str]]


def _achatar(o: Any, prefixo: str = "") -> dict[str, Any]:
    """O estado do daemon como `{caminho: valor}` — para comparar antes/depois."""
    fora = {}
    if isinstance(o, dict):
        for k, v in o.items():
            fora.update(_achatar(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            fora.update(_achatar(v, f"{prefixo}.{i}"))
    else:
        fora[prefixo] = o
    return fora


RUIDO = ("visto_ha_s", "ha_s", "_count", "nascimento", "age_sec", "uptime",
         "inputs.", "motion_", "forwards", "counters.", "_ultimos_",
         "lx", "ly", "rx", "ry", "l2_raw", "r2_raw", "buttons",
         "battery_pct", "bt_mic")


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`."""
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


def _anotar_a_aba(pagina: str) -> None:
    """A aba à vista vai para o runtime, para o install reabrir a janela nela."""
    from hefesto_dualsense4unix.app.actions.recarga_do_install import arquivo_da_aba

    with contextlib.suppress(OSError):
        alvo = arquivo_da_aba(os.getpid())
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(pagina + "\n", encoding="utf-8")


MUDOS_SEGUIDOS_QUE_VOLTARAM = 3


def _o_servico_so_demorou(erro: BaseException) -> bool:
    """O tique mudo foi DEMORA (o prazo vencido), e não serviço fora do ar?"""
    from hefesto_dualsense4unix.app.ipc_bridge import PRAZO_VENCIDO

    return (isinstance(erro, PRAZO_VENCIDO)
            or isinstance(erro.__cause__, PRAZO_VENCIDO))


class FolgaDoServicoMudo:
    """O estado que o tique pinta quando o serviço não respondeu — RECONECTAR-SAMBA-02.

    Cada TRANSIÇÃO do que a tela mostra deixa uma linha no diário, para a foto dela se cruzar
    com a hora: `[tela] estado velho desde <hora>` (pintando o último estado bom), `[tela] vazio`
    (a verdade, `{}`) e `[tela] novo` (voltou a resposta). Uma linha por transição, nunca por
    tique; o que a tela mostra não muda.
    """

    def __init__(
        self,
        folga: int = MUDOS_SEGUIDOS_QUE_VOLTARAM,
        anotar: Callable[[str], None] | None = None,
    ) -> None:
        self.folga = folga
        self.seguidos = 0
        self._ultimo_bom: dict[str, Any] | None = None
        self._anotar = anotar or self._ao_diario
        self._mostrando: str | None = None

    @staticmethod
    def _ao_diario(linha: str) -> None:
        print(linha, file=sys.stderr)

    def _passar_a(self, estado: str, linha: str) -> None:
        if self._mostrando != estado:
            if estado != "novo" or self._mostrando is not None:
                self._anotar(linha)
            self._mostrando = estado

    def respondeu(self, estado: dict[str, Any]) -> None:
        """O serviço respondeu: zera a conta e guarda o estado para a folga."""
        self.seguidos = 0
        self._ultimo_bom = estado
        self._passar_a("novo", "[tela] novo")

    def mudo(self, erro: BaseException) -> dict[str, Any]:
        """O estado a pintar neste tique mudo: o último bom, ou a verdade (`{}`)."""
        self.seguidos += 1
        if (self._ultimo_bom is not None and self.seguidos <= self.folga
                and _o_servico_so_demorou(erro)):
            self._passar_a("velho", f"[tela] estado velho desde {time.strftime('%H:%M:%S')}")
            return self._ultimo_bom
        self._ultimo_bom = None
        self._passar_a("vazio", "[tela] vazio")
        return {}


def _declarar_o_foco(ativa: bool) -> Any:
    """O `navegacao.foco` do daemon: o pulso e a renovação do prazo."""
    return ponte.navegacao_foco(ativa)


class LeitorDoEstado:
    """O `state_full` lido FORA do laço do GTK — A-TELA-QUE-TRAVA-01, 15/09/2026.

    A QUEIXA DE USO, com os dois controles na mesa: *"tem algo muito estranho
    travando a interface do app. como um todo."*  (noqa-acento: citação)

    A CAUSA JÁ ESTAVA ESCRITA DENTRO DO PRÓPRIO TIQUE, na A-TELA-SAMBA-01 de
    03/09: *"as DUAS VIAGENS de IPC do começo deste método são SÍNCRONAS — elas
    seguram o laço do GTK inteiro"*. O que aquela leva fez foi PULAR o tique
    seguinte, que encurta a fila e não desbloqueia nada: enquanto o
    `estado_do_daemon()` não volta, o laço do GTK não roda, e a janela inteira
    — rolagem, clique, `:hover`, o cursor de texto — fica parada.

    O NÚMERO, medido no diário dela (`interface.log`, a sessão de 14/09):

    ========  ======  ==========  ===========
    aba       lentos  IPC médio   IPC pior
    ========  ======  ==========  ===========
    01-jogar     244      568 ms     6.016 ms
    02-controles  55      929 ms     2.665 ms
    09-sistema     7      678 ms     2.002 ms
    ========  ======  ==========  ===========

    612 tiques lentos numa sessão, e em 457 deles o IPC é **80% ou mais** do
    custo. Seis segundos de janela morta é o que ela chama de travar.

    A CURA É DE FORMA, e não de velocidade: a leitura passa a um fio próprio,
    que lê na mesma cadência de antes (uma por tique) e deixa a resposta num
    escaninho. O tique pega o que está lá e segue — **nunca espera**. Um daemon
    que demore seis segundos deixa a tela com dado de seis segundos atrás, que é
    exatamente o que ela já mostrava enquanto congelava; o que muda é que a
    janela continua andando.

    A FOLGA CONTINUA CONTANDO RESPOSTAS, E NÃO TIQUES, e é por isso que existe a
    `self._geracao`: sem ela, uma leitura que falhasse seria entregue a dez
    tiques por segundo, e os `MUDOS_SEGUIDOS_QUE_VOLTARAM` da
    `FolgaDoServicoMudo` — três respostas mudas — queimariam em 300 ms. O
    tique só mexe na folga quando a geração ANDA; entre duas respostas ele
    repinta o que já tinha.

    O QUE ESTA CLASSE NÃO FAZ: pedir mais depressa. O `intervalo` é o mesmo
    `TIQUE_MS`, então o daemon recebe o mesmo número de perguntas por segundo
    que recebia — a mudança é quem espera pela resposta, não quantas são.
    """

    SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA = 1.0

    def __init__(
        self,
        ler: Callable[[], dict[str, Any]] | None = None,
        *,
        intervalo: float = TIQUE_MS / 1000.0,
        declarar_foco: Callable[[bool], Any] | None = None,
        avisar: Callable[[], Any] | None = None,
    ) -> None:
        self._ler = ler if ler is not None else mesa_viva.estado_do_daemon
        self._avisar = avisar
        self._declarar_foco = (declarar_foco if declarar_foco is not None
                               else _declarar_o_foco)
        self._ativa = False
        self._toques: dict[str, dict[str, int]] = {}
        self._pulso = threading.Event()
        self._intervalo = intervalo
        self._trava = threading.Lock()
        self._estado: dict[str, Any] | None = None
        self._erro: BaseException | None = None
        self._geracao = 0
        self._ultima_viagem_ms = 0.0
        self._parar = threading.Event()
        self._a_vista = threading.Event()
        self._a_vista.set()
        self._acordar = threading.Event()
        self._fio: threading.Thread | None = None

    def ultimo(self) -> tuple[dict[str, Any] | None, BaseException | None, int]:
        """O estado, o erro e a geração de agora. Não espera por ninguém."""
        with self._trava:
            return self._estado, self._erro, self._geracao

    def ultima_viagem_ms(self) -> float:
        """Quanto a última leitura do serviço custou, em ms."""
        with self._trava:
            return self._ultima_viagem_ms

    def definir_ativa(self, ativa: bool) -> None:
        """A janela ganhou ou perdeu o foco: o fio lê já, e a leitura é o pulso."""
        with self._trava:
            mudou, self._ativa = self._ativa != bool(ativa), bool(ativa)
        if mudou:
            self._pulso.set()

    def ativa(self) -> bool:
        """A janela está na frente, pelo último `notify::is-active`."""
        with self._trava:
            return self._ativa

    def toques(self) -> dict[str, dict[str, int]]:
        """Os contadores do último `navegacao.foco`, que só sobem."""
        with self._trava:
            return {u: dict(t) for u, t in self._toques.items()}

    def comecar(self) -> None:
        """Sobe o fio, que lê JÁ e chama o `avisar`. Chamar duas vezes não sobe dois.

        Nota de 21/10/2026 (O-FIO-DA-JANELA-NUNCA-ESPERA-01): a primeira leitura era
        semeada aqui, no fio de quem chama, que é o do GTK — um IPC no `_instalado`. Ela
        passou ao fio; o tique sem resposta não pinta, e o aviso traz a primeira pintura.
        """
        if self._fio is not None:
            return
        self._fio = pacotes.fios.soltar("hefesto-estado", self._laco)

    def parar(self) -> None:
        """Pede o fim do fio. Ele é `daemon`, então o processo não o espera."""
        self._parar.set()
        self._acordar.set()
        self._pulso.set()

    def pausar(self) -> None:
        """A janela foi escondida: o fio passa a ler de segundo em segundo."""
        self._a_vista.clear()
        self._acordar.clear()

    def retomar(self) -> None:
        """A janela voltou: o fio acorda, lê já e volta à cadência do tique."""
        self._a_vista.set()
        self._acordar.set()

    def _uma_leitura(self) -> None:
        t0 = time.perf_counter()
        try:
            st = self._ler()
        except Exception as erro:
            with self._trava:
                self._estado, self._erro = None, erro
                self._geracao += 1
                self._ultima_viagem_ms = (time.perf_counter() - t0) * 1000
        else:
            self._declarar(st)
            with self._trava:
                self._estado, self._erro = st, None
                self._geracao += 1
                self._ultima_viagem_ms = (time.perf_counter() - t0) * 1000

    def _declarar(self, st: Any) -> None:
        """Com a Interna ligada, o foco vai ao daemon e os toques voltam.

        Desligada, nada vai: o foco que a janela declarou antes cai sozinho no
        prazo do daemon (`PRAZO_DO_FOCO_S`). Uma recusa não derruba a leitura.
        """
        nav = st.get("navegacao") if isinstance(st, dict) else None
        if not isinstance(nav, dict) or not nav.get("interna_ligada"):
            return
        with self._trava:
            ativa = self._ativa
        resposta = self._declarar_foco(ativa)
        toques = resposta.get("toques") if isinstance(resposta, dict) else None
        if isinstance(toques, dict):
            with self._trava:
                self._toques = {str(u): {str(k): int(v or 0) for k, v in t.items()}
                                for u, t in toques.items() if isinstance(t, dict)}

    def _laco(self) -> None:
        self._uma_leitura()
        if self._avisar is not None:
            try:
                self._avisar()
            except Exception as erro:
                print(f"[estado] o aviso da primeira leitura falhou: {erro}", file=sys.stderr)
        while not self._parar.is_set():
            if self._a_vista.is_set():
                self._pulso.wait(self._intervalo)
                self._pulso.clear()
            else:
                self._acordar.wait(max(self._intervalo,
                                       self.SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA))
                self._acordar.clear()
            if self._parar.is_set():
                return
            self._uma_leitura()


class Piloto:
    SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS = 4.0
    SEGUNDOS_DE_ESPERA_DOS_EXTERNOS = 3.0

    TIQUES_ENTRE_CARGAS_INTEIRAS = 10
    CUSTOS_GUARDADOS = 6000

    def __init__(self, args: argparse.Namespace) -> None:
        from collections import deque

        self._abertura: dict[str, float] = {"piloto": time.monotonic()}
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        self.pinturas: dict[str, list[int]] = {}
        self.tiques: dict[str, int] = {}
        self.trocas: dict[str, int] = {}
        self.visitadas: list[str] = []
        self.custos: deque[float] = deque(maxlen=self.CUSTOS_GUARDADOS)
        self.gestos: list[dict[str, Any]] = []
        self.aplicados: list[str] = []
        self.recusados: list[str] = []
        self.provas: list[dict[str, Any]] = []
        self.desfechos: dict[str, tuple[str, str]] = {}
        self._onde_clicou: dict[str, str] = {}
        self._vivos: dict[str, str] = {}
        self.vivos_atendidos: list[str] = []
        self.vivos_recusados: list[str] = []
        self.vivos_descartados = 0
        self._fila: list[str] = []
        self.cravados: dict[str, list[regua_do_mockup._Campo]] = {}
        self.pristino: dict[str, list[list[str]]] = {}
        self.vereditos: dict[str, list[regua_do_mockup._Veredito]] = {}
        self.cegueiras: list[str] = []
        self._fila_de_abas: list[str] = []
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora: dict[str, Any] = {}
        self._mesa_de_agora: list[dict[str, Any]] = []
        self._voltas_do_contador = 0
        self._mutacoes_lidas = False
        self.mutacoes: dict[str, Any] = {}
        self._voltas_do_tamanho = 0
        self._tamanho_lido = False
        self.tamanhos: dict[str, Any] = {}
        self._tamanho_da_janela_ao_partir = 0
        self._mudo_de_proposito = False
        self.estados_simulados = 0
        self._pulados_por_voo = 0
        self._pulados_por_custo = 0
        self._pintura_no_ar = False
        self._pular = 0
        self._folga = FolgaDoServicoMudo()
        self._geracao_vista = 0
        self._st_de_agora: dict[str, Any] = {}
        self.custo_do_ipc: deque[float] = deque(maxlen=self.CUSTOS_GUARDADOS)
        self._escondida = False
        self._escondida_desde = 0.0
        self._geracao_na_volta: int | None = 0
        self._pintada: dict[tuple[str, ...], tuple[Any, Any]] | None = None
        self._ate_a_inteira = 0
        self._moldes: dict[str, frozenset[str]] = {}
        self._externos: list[dict[str, Any]] = []
        self._externos_lidos_em = 0.0
        self._externos_no_ar = False

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._navegou,
            ao_morrer_a_pagina=self._a_pagina_morreu,
            oculta=args.oculta,
            esperar_a_pintura=True,
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        _FECHAR_A_JANELA[:] = [self.tela.fechar]
        self.view.connect("load-changed", self._carregou)
        self._abertura["janela"] = time.monotonic()
        _importar_as_abas(self.tela)
        self._ctx_de_agora = pacotes.Contexto(state={})
        self._estado_vivo = LeitorDoEstado(avisar=self._a_primeira_resposta_chegou)
        if getattr(args, "cenario", "parado") == "mudo":
            self._tornar_o_servico_mudavel()
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)
        self._navegador = navegacao_interna.Navegador()
        self._selecoes = navegacao_interna.Selecoes()
        self._leiaute_no_ar = False
        self._atos_pendentes: list[navegacao_interna.Ato] = []
        self._com_molduras = False
        janela = getattr(self.tela, "janela", None)
        if getattr(args, "na_frente", False):
            self._estado_vivo.definir_ativa(True)
        elif janela is not None and hasattr(janela, "is_active"):
            janela.connect("notify::is-active",
                           lambda w, _p: self._estado_vivo.definir_ativa(w.is_active()))
            self._estado_vivo.definir_ativa(bool(janela.is_active()))

        ponte.escolher_arquivo = self._escolher_arquivo
        ponte.salvar_arquivo = self._salvar_arquivo

    def _dialogo(self, titulo: str, acao: Any, rotulo: str, *,
                 sugestao: str = "", padrao: str = "*") -> str | None:
        """Um `FileChooserDialog` modal, e ele RODA NO LAÇO DO GTK.

        POR QUE `Gtk.Dialog.run()` E NÃO UM CALLBACK: o gesto está numa thread
        (os gestos correm fora do laço, porque `daemon.reload` leva 9,5 s), e
        precisa do caminho para seguir. `run()` bombeia o laço do GTK por
        dentro, então a janela continua viva enquanto ela escolhe.

        COM A JANELA OCULTA NÃO HÁ DIÁLOGO: uma `Gtk.OffscreenWindow` não tem
        onde pôr um modal, e abrir um sem pai o jogaria NA TELA DO USUÁRIO — que é
        exatamente o que `--oculta` existe para impedir. Nesse caso devolve
        `None`, e o gesto o lê como "cancelou".
        """
        if self.args.oculta:
            print(f"[seletor] {titulo}: a janela está oculta, não abro diálogo",
                  file=sys.stderr)
            return None
        dlg = Gtk.FileChooserDialog(title=titulo, transient_for=self.tela.janela,
                                    action=acao)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        rotulo, Gtk.ResponseType.ACCEPT)
        if sugestao:
            dlg.set_current_name(pathlib.Path(sugestao).name)
            with contextlib.suppress(Exception):
                dlg.set_current_folder(str(pathlib.Path(sugestao).parent))
        if padrao != "*":
            f = Gtk.FileFilter()
            f.set_name(padrao)
            f.add_pattern(padrao)
            dlg.add_filter(f)
        try:
            escolhido = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        finally:
            dlg.destroy()
        return escolhido

    def _escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.OPEN, "Abrir", padrao=padrao)

    def _salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.SAVE, "Guardar",
                             sugestao=sugestao)

    def _com_uniq(self, o: dict[str, Any]) -> dict[str, Any]:
        """O clique com o `uniq` do controle resolvido contra a mesa de agora."""
        pref = str(o.get("controle") or "")
        for c in self._mesa_de_agora:
            if c.get("pref") == pref or str(c.get("uniq") or "") == pref:
                return {**o, "uniq": str(c.get("uniq") or "")}
        return o

    def _gesto_vivo(self, o: dict[str, Any], pagina: str, nome: str) -> None:
        """A quarta porta — o gesto que LÊ enquanto ela digita, e não grava."""
        serial = str(o.get("vivo") or "")
        chave = str(o.get("vivoChave") or f"{pagina}:{nome}")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.vivos_recusados.append(f"{pagina}:{nome} (sem dono)")
            print(f"[vivo sem dono] {pagina} · {nome} — o `data-hef-vivo` "
                  f"aponta para um gesto que ninguém registrou", file=sys.stderr)
            return
        grava = (pacotes.GESTOS_QUE_MEXEM.get((pagina, nome))
                 or pacotes.GESTOS_QUE_MEXEM.get(("*", nome)) or "")
        if grava:
            self.vivos_recusados.append(f"{pagina}:{nome} (grava: {grava})")
            print(f"[vivo recusado] {pagina} · {nome} declara gravação "
                  f"({grava}) — a quarta porta é de LEITURA, e ela dispara a "
                  f"cada tecla", file=sys.stderr)
            return
        self._vivos[chave] = serial
        o = self._com_uniq(o)

        def trabalhar() -> None:
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                self.vivos_recusados.append(
                    f"{pagina}:{nome} ({type(erro).__name__}: {erro})")
                print(f"[vivo falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
            else:
                GLib.idle_add(
                    lambda r=resposta: self._vivo_voltou(pagina, nome, chave,
                                                         serial, r))

        pacotes.fios.soltar(f"hefesto-vivo-{nome}", trabalhar)

    def _vivo_voltou(self, pagina: str, nome: str, chave: str, serial: str,
                     resposta: object) -> bool:
        """A leitura chegou. Se ainda é a mais nova, ela pinta."""
        if self._vivos.get(chave) != serial:
            self.vivos_descartados += 1
            return False
        if not isinstance(resposta, dict) or not resposta:
            self.vivos_atendidos.append(f"{pagina}:{nome}")
            return False
        proibidas = [k for k in CHAVES_QUE_O_VIVO_RECUSA if k in resposta]
        if proibidas:
            self.vivos_recusados.append(
                f"{pagina}:{nome} (devolveu {', '.join(proibidas)})")
            print(f"[vivo recusado] {pagina} · {nome} devolveu "
                  f"{', '.join(proibidas)} — a quarta porta dispara a cada "
                  f"tecla, e essas chaves trocam HTML inteiro ou mandam "
                  f"frase", file=sys.stderr)
            return False
        self.vivos_atendidos.append(f"{pagina}:{nome}")
        _esquecer_a_pintura(self)
        self._js(f"window.__hef && window.__hef.pintar({_json(resposta, pagina=pagina)})")
        return False

    def _gesto(self, o: dict[str, Any]) -> None:
        """tela → Python, já em JSON. Quem recusa o que não é objeto é a ponte."""
        if "gesto" not in o and o.get("visibilidade") in ("escondida", "vista"):
            self._a_janela_mudou(o.get("visibilidade") == "escondida")
            return
        _esquecer_a_pintura(self)
        self.gestos.append(o)
        nome = str(o.get("gesto") or "")
        pagina = str(o.get("pagina") or self.pagina)  # (noqa-acento)
        if str(o.get("vivo") or ""):
            self._gesto_vivo(o, pagina, nome)
            return
        voo = str(o.get("voo") or "")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.recusados.append(f"{pagina}:{nome}")
            self.desfechos[f"{pagina}:{nome}"] = ("sem dono", "")
            print(f"[gesto sem dono] {pagina} · {nome} · {o.get('texto', '')!r}")
            self._pousou(voo, False)
            return
        o = self._com_uniq(o)
        alvo = norm_mac(str(o.get("uniq") or "")) or ""

        def trabalhar() -> None:
            desta_vez: tuple[str, str] = ("", "")
            so_armou = False
            marca_do_gesto = gesto_de_agora.set(f"{pagina} · {nome}")
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                desta_vez = ("recusou dizendo", f"{type(erro).__name__}: {erro}")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                GLib.idle_add(
                    lambda x=erro: self._recusou_dizendo(pagina, nome, alvo, x))
            else:
                desta_vez = ("aplicou", "")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                so_armou = (isinstance(resposta, dict)
                            and bool(resposta.get(CHAVE_DO_CLIQUE_QUE_SO_ARMOU)))
                GLib.idle_add(lambda r=resposta: self._deu_certo_dizendo(
                    pagina, nome, alvo, self._o_arranjo_relido(pagina, r)))
            finally:
                gesto_de_agora.reset(marca_do_gesto)
                certo: bool | None = (None if so_armou
                                      else desta_vez[0] == "aplicou")
                GLib.idle_add(lambda v=voo, c=certo: self._pousou(v, c))

        pacotes.despachar(pagina, nome, o, trabalhar)

    def _a_janela_mudou(self, escondida: bool) -> None:
        """A página disse se alguém pode vê-la. Escondida, a janela não trabalha."""
        if escondida == self._escondida:
            return
        self._escondida = escondida
        _esquecer_a_pintura(self)
        if escondida:
            self._geracao_na_volta = None
            self._escondida_desde = time.monotonic()
            self._estado_vivo.pausar()
            _soltar_as_ondas()
            print("[janela] escondida: o tique parou", file=sys.stderr)
            return
        self._geracao_na_volta = self._estado_vivo.ultimo()[2]
        self._estado_vivo.retomar()
        desde = getattr(self, "_escondida_desde", 0.0)
        ficou = time.monotonic() - desde if desde else 0.0
        self._escondida_desde = 0.0
        print(f"[janela] à vista: o tique voltou · escondida por {ficou:.0f} s", file=sys.stderr)

    def _moldes_da_pagina(self) -> frozenset[str]:
        """As chaves de lista que um `data-hef-molde` conta nesta página."""
        import re

        if self.pagina not in self._moldes:
            try:
                texto = onde.pagina(self.pagina, publicado=True).read_text(encoding="utf-8")
            except OSError:
                texto = ""
            self._moldes[self.pagina] = frozenset(
                re.findall(r'data-hef-molde-conta="([^"]+)"', texto))
        return self._moldes[self.pagina]

    def _pousou(self, voo: str, certo: bool | None = None) -> bool:
        """O botão volta do voo — a classe sai e o rótulo original é devolvido."""
        if not voo:
            return False
        _esquecer_a_pintura(self)
        self._js(
            f"window.__hef && window.__hef.voltouDoVoo("
            f"{_json(voo, pagina=self.pagina)}, {_json(certo, pagina=self.pagina)})"
        )
        return False

    def _deu_certo(self, pagina: str, nome: str, resposta: object = None) -> bool:
        """O gesto voltou. Se ele TROUXE ALGO, o que trouxe vai para a tela.

        O CAMINHO DE VOLTA, e por que ele precisou existir (01/09/2026): o gesto
        devolvia `None` e não havia por onde escrever um resultado na página.
        Isso deixou sem dono os botões cuja promessa é MOSTRAR — "Ver os
        plugins carregados" e "Ver detalhes" da aba Sistema. O daemon atende
        `plugin.list` desde sempre; o que faltava era o retorno. Um gesto que
        chamasse `plugin.list` e jogasse a lista fora seria o botão que responde
        calado — o defeito que esta casa tem nome para.

        A CARGA É A MESMA DA PINTURA, de propósito: `{"mesa": {...}}`,
        `{"colunas": {...}}`. Nenhum segundo vocabulário nasce aqui, e um gesto
        que devolve endereço escreve no mesmo lugar em que a pintura escreveria
        — logo o tique seguinte não briga com ele, sobrescreve com o valor vivo.
        """
        self.aplicados.append(f"{pagina}:{nome}")
        if isinstance(resposta, dict) and resposta:
            _esquecer_a_pintura(self)
            self._js(f"window.__hef && window.__hef.pintar({_json(resposta, pagina=pagina)})")
            print(f"[gesto] {pagina} · {nome} → aplicado, e a resposta foi para a tela")
            return False
        print(f"[gesto] {pagina} · {nome} → aplicado")
        return False

    def _recusou_dizendo(self, pagina: str, nome: str, uniq: str,
                         erro: BaseException) -> bool:
        """A recusa do produto chegando ao DIÁRIO — e ao botão, pela piscada."""
        print(f"[gesto falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
        return False

    def _deu_certo_dizendo(self, pagina: str, nome: str, uniq: str,
                           resposta: object = None) -> bool:
        """O gesto voltou SEM levantar — e agora a tela do usuário sabe disso.

        **O DEFEITO, e a decisão que o fecha.** Até 04/09/2026 a interface nova
        só falava quando RECUSAVA: um gesto que dava certo imprimia
        `[gesto] … → aplicado` no terminal de quem lançou a janela, e quem clica
        não lê terminal. **Cinco linhas do CSV paravam neste mesmo buraco**, em
        cinco abas (02, 03, 05, 06 e 09). A decisão de produto, no mesmo dia:

            *"No próprio cartão, como a recusa."*   — D-01

        DUAS RECOMENDAÇÕES PROPUNHAM OUTRO CANAL e as duas foram recusadas por
        UM FATO, UM SINAL — e é o que faz esta peça fechar as cinco abas de uma
        vez em vez de virar cinco peças que divergem. Esta metade continua
        valendo inteira.

        A OUTRA METADE CADUCOU EM 05/09/2026, e a data importa. Este parágrafo
        dizia que ELA recusara *o campo que pisca* (aba 03) e *a faixa embaixo
        da grade* (aba 05), e mandava: **"não construa nenhum dos dois"**. Quem
        recusou foi o PO, lendo a D-01 (*"no próprio cartão, como a recusa"*)
        como se ela fechasse a FORMA — os conflitos C-3 e C-6 de
        `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` são dele, não
        dela. Em 05/09 ela respondeu a `03-Q4` vendo as quatro formas lado a
        lado e escolheu o campo que pisca. **A palavra de produto vence a leitura que
        o PO fez da palavra de produto.**

        E a piscada não é um segundo canal para o mesmo fato: é o mesmo fato num
        sinal mais barato. O cartão passa a dizer só o que tem notícia, e as
        duas peças deixam de disputar.

        A FRASE É DO DONO DO ASSUNTO, e não deste arquivo: um gesto que devolva
        `{"recado": "…"}` manda a própria, e o piloto a leva. O `recado`
        SAI da carga antes de a resposta ir para a pintura: ele não é endereço de
        página nenhuma, e deixá-lo entrar faria o `escrever()` procurar um
        `data-campo="recado"` que não existe.

        E QUANDO NÃO HÁ FRASE, A TELA NÃO FALA — 05/09/2026, decisão de produto na
        `03-Q4`. Até aqui valia uma frase do piloto (*"Pronto."*), e ela tirou
        a palavra nova da tela:

            *"nada muda de lugar e nenhuma palavra nova entra na tela"*

        A regra que isso escrevia — *"quando ele tem NOTÍCIA, a tela fala"* —
        caducou em 13/09/2026 (nota abaixo). Quem pisca continua sendo o
        `voltouDoVoo`, no pouso, e agora a piscada é a resposta inteira do
        sucesso na tela.

        ELE NÃO SUBSTITUI O `_deu_certo`, ele o EMBRULHA — e isso é de propósito:
        `_deu_certo` é o caminho da carga de volta (`plugin.list`, "Ver
        detalhes"), tem régua própria e não precisa saber que existe recado.

        **A METADE DO SUCESSO DA D-01 CADUCOU EM 13/09/2026** — TELA-CALADA-01,
        pela palavra de produto, com a foto do rodapé: *"essas frases de status que
        aparecem no rodapé isso não deveria estar aparecendo"*, *"em todas as
        abas da interface"*. O recado de sucesso chegava por três portas — o
        cartão, as faixas `data-hef-recados` da 01 e da 05, e a aba seguinte —,
        e as três passavam por um depósito de tom `sucesso` feito aqui. **A frase
        continua vindo do dono e continua saindo da carga**; o que mudou é o
        destino: o diário da janela, como `[relato] <página> · <gesto>: <frase>`
        (o desenho que a aba 10 ganhou no mesmo dia, `a10_perfis._anotar`).
        **A metade da recusa caducou no mesmo dia** (FRASES-E-DICAS-01): ver
        `_recusou_dizendo`.

        E A CHAVE `armou` SAI JUNTO COM O `recado` — 13/09/2026. Ela é sinal
        para o POUSO (`CHAVE_DO_CLIQUE_QUE_SO_ARMOU`, lida em `_gesto`), e não
        endereço de página.
        """
        frase = ""
        if isinstance(resposta, dict):
            bruto = resposta.get("recado")
            if isinstance(bruto, str) and bruto.strip():
                frase = bruto.strip()
            fora_da_pintura = ("recado", CHAVE_DO_CLIQUE_QUE_SO_ARMOU)
            if any(k in resposta for k in fora_da_pintura):
                resposta = {k: v for k, v in resposta.items()
                            if k not in fora_da_pintura}
        if frase:
            print(f"[relato] {pagina} · {nome}: {frase}", file=sys.stderr)
        return self._deu_certo(pagina, nome, resposta)

    def _a_pagina_morreu(self, motivo: str) -> None:
        """O processo web do WebKit caiu. A janela já está recarregando; aqui se DIZ."""
        print(f"[página morreu] {motivo} — a pintura pausou até a página voltar",
              file=sys.stderr)
        self.pronto = False


    def _navegou(self, titulo: str) -> None:
        """O usuário clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view: Any, evento: Any) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            self._a_mesma_recarregou(nova)
            return
        if nova != self.pagina:
            pacotes.largar_o_que_as_abas_seguram(ponte, mesa=self._mesa_de_agora)
        self.pagina = nova
        if not self.args.oculta:
            _anotar_a_aba(nova)
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        self.pronto = False
        self._antes_de_instalar()

    def _a_mesma_recarregou(self, nova: str) -> None:
        """O MAPA RECARREGADO VOLTA COM O ARRANJO — O-MAPA-QUE-ELA-CORRIGE-01."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if nova != arranjo_desta_maquina.PAGINA or nova != self.pagina or not self.pronto:
            return

        def respondeu(valor: Any, erro: Any) -> None:
            if erro is None and str(valor) == "false" and self.pagina == nova:
                self.pronto = False
                self._antes_de_instalar()

        self.ponte.perguntar("String(!!window.__hef)", respondeu)

    def _instalar(self) -> None:
        self._antes_de_instalar()

    def _antes_de_instalar(self) -> None:
        """O DOM VIRGEM é lido AQUI, e é o único instante em que ele existe."""
        self._voltas_do_contador = 0
        if self.args.prova_de_mockup and self.pagina not in self.pristino:
            pagina = self.pagina

            def retratou(valor: Any, erro: Any) -> None:
                self._leu_virgem(pagina, valor, erro)

            self.ponte.perguntar(LER_CAMPOS, retratou)
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _dica_instalada(self, valor: Any, erro: Any) -> None:
        """A camada da dica respondeu — ou a página ficou com a dica do sistema."""
        if erro is not None:
            self.cegueiras.append(f"{self.pagina}: a camada da dica não instalou — {erro}")
            print(f"ERRO: a camada da dica não instalou em {self.pagina}: {erro}",
                  file=sys.stderr)
            return
        resposta = str(valor)
        if resposta not in ("ok", "ja"):
            self.cegueiras.append(
                f"{self.pagina}: a camada da dica respondeu {resposta!r}")

    def _entregar_o_arranjo(self) -> None:
        """Entrega ao `mapa-das-portas` o gabinete de quem abriu a janela."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        pagina = self.pagina

        def ler() -> None:
            dado = arranjo_desta_maquina.para_a_pagina(faixas=self._as_faixas_do_mapa)
            porque = "" if dado is not None else arranjo_desta_maquina.porque_sem_leitura()
            GLib.idle_add(lambda: self._entregar(pagina, dado, porque=porque))

        pacotes.fios.soltar("arranjo-desta-maquina", ler)

    def _as_faixas_do_mapa(self) -> dict[str, Any]:
        """A faixa de cada rádio, pela MESMA conta da aba Conexões, com o estado do último tique."""
        ctx = getattr(self, "_ctx_de_agora", None)
        if ctx is None:
            return {}
        from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

        return a08_conexoes.faixas_para_o_mapa(ctx)

    def _entregar(self, pagina: str, dado: Any, *, reexame: bool = False,
                  como: str = "", porque: str = "") -> bool:
        """O arranjo lido (ou o porquê de não haver) vai à página, no laço do GTK e se ela é a dele."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if self.pagina != pagina:
            return False
        js = arranjo_desta_maquina.js_da_entrega(dado, reexame=reexame, como=como, porque=porque)
        self.ponte.perguntar(js, self._arranjo_entregue)
        return False

    def _o_arranjo_relido(self, pagina: str, resposta: object) -> object:
        """A resposta do «Examinar» traz um arranjo: ele sai da carga e vai à página."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina as arranjo

        if pagina != arranjo.PAGINA or not isinstance(resposta, dict):
            return resposta
        modos = ((arranjo.CHAVE_DA_ENTREGA, arranjo.COMO_REEXAME),
                 (arranjo.CHAVE_DEPOIS_DE_GRAVAR, arranjo.COMO_GRAVOU))
        achadas = [(chave, como) for chave, como in modos if chave in resposta]
        if not achadas:
            return resposta
        for chave, como in achadas:
            self._entregar(pagina, resposta[chave], como=como)
        return {k: v for k, v in resposta.items() if k not in dict(achadas)}

    def _arranjo_entregue(self, valor: Any, erro: Any) -> None:
        if erro is not None:
            self.cegueiras.append(f"{self.pagina}: o arranjo desta máquina não "
                                  f"chegou à página — {erro}")
            return
        if str(valor) != "ok":
            self.cegueiras.append(f"{self.pagina}: a página recusou o arranjo "
                                  f"desta máquina — respondeu {valor!r}")

    def _leu_virgem(self, pagina: str, valor: Any, erro: Any) -> None:
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li o DOM virgem — {erro}")
            self.pristino[pagina] = []
            return
        try:
            self.pristino[pagina] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: o DOM virgem não veio em JSON — {e}")
            self.pristino[pagina] = []

    def _instalado(self, _valor: Any, erro: Any) -> None:
        if erro is not None:
            print(f"ERRO: o bootstrap não instalou em {self.pagina}: {erro}", file=sys.stderr)
            return
        self.pronto = True
        self.ponte.perguntar(DICA_DA_CASA, self._dica_instalada)
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if self.pagina == arranjo_desta_maquina.PAGINA:
            self._entregar_o_arranjo()
        self._estado_vivo.comecar()
        _esquecer_a_pintura(self)
        _soltar_as_ondas()
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    def _contexto(self, st: dict[str, Any], *,
                  perguntar: bool = True) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        self.leitor.esquecer_ausentes(
            {str(c.get("uniq") or "") for c in ctx_conectados})
        if perguntar:
            self.leitor.disparar(ctx_conectados)
        conectados = ctx_conectados
        if perguntar:
            self._talvez_ler_os_externos()
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={},
                               externos=list(self._externos), escolhido=_pref_escolhido(mesa))
        return ctx, para_pref

    def _talvez_ler_os_externos(self) -> None:
        """Pede `controller.list {external: true}` no tique LENTO, em thread."""
        agora = time.monotonic()
        if self._externos_no_ar:
            return
        if (agora - self._externos_lidos_em
                < self.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS):
            return
        self._externos_lidos_em = agora
        self._externos_no_ar = True

        def perguntar() -> None:
            try:
                r = ponte.resultado(
                    "controller.list",
                    timeout=self.SEGUNDOS_DE_ESPERA_DOS_EXTERNOS,
                    external=True,
                )
            except Exception as e:
                print(f"[externos] não li o inventário: {e}", file=sys.stderr)
                return
            finally:
                self._externos_no_ar = False
            from hefesto_dualsense4unix.app.actions.home_actions import externos_na_mesa

            bruto = r.get("external") if isinstance(r, dict) else None
            self._externos = externos_na_mesa(
                None, bruto if isinstance(bruto, list) else ())

        pacotes.fios.soltar("hefesto-externos", perguntar)

    def _da_resposta(
        self, st: dict[str, Any] | None, erro: BaseException | None
    ) -> dict[str, Any]:
        """O estado a pintar a partir de UMA resposta do leitor — boa ou muda."""
        if erro is not None:
            print(f"[daemon mudo] {erro}", file=sys.stderr)
            return self._folga.mudo(erro)
        bom = st if isinstance(st, dict) else {}
        self._folga.respondeu(bom)
        return bom

    def _a_primeira_resposta_chegou(self) -> None:
        """No fio do leitor: a primeira pintura vai ao laço do GTK, sem esperar o tique."""
        GLib.idle_add(lambda: self._tique() and False)

    def _estado_do_tique(self) -> dict[str, Any]:
        """O estado que ESTE tique pinta — e ele não espera por ninguém."""
        st_lido, erro_lido, geracao = self._estado_vivo.ultimo()
        if geracao != self._geracao_vista:
            self._geracao_vista = geracao
            self._st_de_agora = self._da_resposta(st_lido, erro_lido)
        return self._st_de_agora

    def _o_contexto_anda_escondido(self) -> None:
        """Com a janela escondida, o CONTEXTO anda com o leitor; a pintura não."""
        if self._estado_vivo.ultimo()[2] == self._geracao_vista:
            return
        st = self._estado_do_tique()
        try:
            ctx, _ = self._contexto(st, perguntar=False)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx

    def _esperando_o_estado_novo(self) -> bool:
        """A janela voltou e o leitor ainda não trouxe resposta depois disso?"""
        if self._geracao_na_volta is None:
            return False
        if self._estado_vivo.ultimo()[2] == self._geracao_na_volta:
            return True
        self._geracao_na_volta = None
        return False

    def _o_que_mandar(self, carga: dict[str, Any]) -> dict[str, Any]:
        """A carga que ESTE tique manda à página: inteira, só a diferença, ou nada."""
        agora = _achatar_a_carga(carga)
        antes, self._pintada = self._pintada, agora
        self._ate_a_inteira -= 1
        if antes is None or self._ate_a_inteira <= 0:
            self._ate_a_inteira = self.TIQUES_ENTRE_CARGAS_INTEIRAS
            return carga
        dif = _o_que_mudou(antes, agora)
        if _a_diferenca_muda_a_forma(dif, self._moldes_da_pagina()):
            self._ate_a_inteira = self.TIQUES_ENTRE_CARGAS_INTEIRAS
            return carga
        return dif

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        if self._escondida or self._esperando_o_estado_novo():
            self._o_contexto_anda_escondido()
            pacotes.bater_os_coracoes(self._ctx_de_agora, ponte)
            return True
        if self._pintura_no_ar:
            self._pulados_por_voo += 1
            return True
        if self._pular > 0:
            self._pular -= 1
            self._pulados_por_custo += 1
            return True
        if self.args.prova_de_mockup:
            if self.pagina not in self.pristino:
                return True
            self._voltas_da_aba += 1
            if self._voltas_da_aba >= self.args.voltas_por_aba and not self._medindo:
                self._medindo = True
                pagina = self.pagina

                def mediu(valor: Any, erro: Any, p: str = pagina) -> None:
                    self._fechou_a_aba(p, valor, erro)

                self.ponte.perguntar(LER_CAMPOS, mediu)
        t0 = time.perf_counter()
        st = self._estado_do_tique()

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        t_ipc = (time.perf_counter() - t0) * 1000
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx
        pacotes.bater_os_coracoes(ctx, ponte)
        self._navegar(st, ctx)
        t_pacote0 = time.perf_counter()
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except pacotes.fios.AindaNaoChegou:
            return True
        except Exception as e:
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            pacote = {}
        t_pacote = (time.perf_counter() - t_pacote0) * 1000

        carga = pacotes.normalizar(pacote, para_pref)
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        carga["fita"] = ("" if self.pagina.removesuffix(".html") in monta.ABAS_SEM_A_FITA
                         else _fita(ctx.mesa, self.pagina))

        alvo = (_pref_escolhido(ctx.mesa)
                if _a_fita_desta_pagina_escolhe(self.pagina) else "")
        carga["alvo"] = "" if alvo == "todos" else alvo

        pacotes.apagar_os_lugares_sem_dono(carga, _com_dono(ctx), pagina=self.pagina)


        def contou(valor: Any, erro: Any) -> None:
            self._pintura_no_ar = False
            if erro is not None:
                _esquecer_a_pintura(self)
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            if n < 0:
                _esquecer_a_pintura(self)
                self.trocas[self.pagina] = self.trocas.get(self.pagina, 0) + 1
                return
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
            if n > 0:
                self.pinturas.setdefault(self.pagina, []).append(n)
                abertura = getattr(self, "_abertura", None)
                if abertura is not None and "pintura" not in abertura:
                    Piloto._contar_a_abertura(self)

        enviar = self._o_que_mandar(carga)
        if enviar:
            pedido = PEDIR_A_PINTURA.replace("CARGA", _json(enviar, pagina=self.pagina))
            self._pintura_no_ar = True
            self.ponte.perguntar(pedido, contou)
        else:
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
        self._carga_de_agora = carga
        self.voltas += 1
        custo = (time.perf_counter() - t0) * 1000
        self.custos.append(custo)
        self.custo_do_ipc.append(t_ipc)
        if custo > TIQUE_MS:
            self._pular += 1
            viagem = getattr(getattr(self, "_estado_vivo", None), "ultima_viagem_ms", None)
            daemon_ms = viagem() if callable(viagem) else 0.0
            print(f"[tique lento] {self.pagina}: {custo:.0f} ms "
                  f"(pacote {t_pacote:.0f} · contexto {t_ipc:.0f} · daemon "
                  f"{daemon_ms:.0f}) — teto {TIQUE_MS} ms, pulando o próximo · janela: "
                  f"{getattr(getattr(self, 'tela', None), 'mudancas_de_tamanho', 0)} "
                  f"mudança(s) de tamanho",
                  file=sys.stderr)
        self._contar_mutacoes()
        contar_o_tamanho = getattr(self, "_contar_tamanho", None)
        if contar_o_tamanho is not None:
            contar_o_tamanho()
        return True

    def _contar_a_abertura(self) -> None:
        """A linha `[abertura]`, uma vez — O-APP-RESPONDE-NA-HORA-01, cura 3."""
        agora = time.monotonic()
        self._abertura["pintura"] = agora
        vida = _segundos_de_vida()
        piloto = self._abertura["piloto"]
        janela = self._abertura.get("janela", piloto)
        total = vida if vida is not None else agora - piloto
        importar = max(0.0, total - (agora - piloto))
        print(f"[abertura] primeira pintura em {total * 1000:.0f} ms "
              f"(importar {importar * 1000:.0f} · janela {(janela - piloto) * 1000:.0f} "
              f"· página {(agora - janela) * 1000:.0f})", file=sys.stderr)

    def _contar_mutacoes(self) -> None:
        """Um passo do `--conta-mutacoes`, por tique. Fora dele, é um `if` falso."""
        quantos = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        if quantos <= 0 or self._mutacoes_lidas:
            return
        self._voltas_do_contador += 1
        if self._voltas_do_contador == VOLTAS_ATE_ASSENTAR:
            self.ponte.rodar(OBSERVAR_MUTACOES)
            print(f"[mutações] observando {self.pagina} por {quantos} tiques "
                  f"(~{quantos * TIQUE_MS / 1000:.0f} s), com a mesa parada")
        if self._voltas_do_contador >= VOLTAS_ATE_ASSENTAR + quantos:
            self._mutacoes_lidas = True
            self.ponte.perguntar(LER_MUTACOES, self._leu_mutacoes)

    def _tornar_o_servico_mudavel(self) -> None:
        """Cenário `mudo`: a leitura do estado passa a poder vencer o prazo, de propósito.

        O erro é o mesmo que o IPC real dá quando o serviço demora (`TimeoutError`), então o
        tique percorre o caminho inteiro: estado velho, depois vazio, depois novo.
        """
        lida = self._estado_vivo._ler

        def ler() -> dict[str, Any]:
            if self._mudo_de_proposito:
                raise TimeoutError("cenário: o serviço mudo de propósito")
            return lida()

        self._estado_vivo._ler = ler

    def _simular_um_estado_da_janela(self, n: int) -> bool:
        """Cenário `rajada`: um `window-state-event` de maximizar/restaurar, SEM mudar o tamanho.

        Entra pelos mesmos dois ouvintes que o GTK chama (`_a_barra_se_refaz`, que repinta a
        decoração, e `_o_tamanho_mudou`). Num X sem gerenciador de janelas ninguém maximiza de
        verdade, então o evento é montado; o que se mede é o que a PÁGINA faz com ele.
        """
        import types

        from gi.repository import Gdk

        maximizada = int(Gdk.WindowState.MAXIMIZED) if n % 2 == 0 else 0
        evento = types.SimpleNamespace(
            changed_mask=int(Gdk.WindowState.MAXIMIZED), new_window_state=maximizada)
        janela = self.tela.janela
        self.tela._a_barra_se_refaz(janela, evento)
        self.tela._o_tamanho_mudou(janela, evento)
        self.estados_simulados += 1
        return False

    def _andar_o_cenario(self, volta: int, tiques: int) -> None:
        """Um passo do cenário do `--conta-tamanho` (`parado` não faz nada)."""
        cenario = getattr(self.args, "cenario", "parado")
        if cenario == "mudo":
            self._mudo_de_proposito = tiques // 3 <= volta < 2 * tiques // 3
        elif cenario == "rajada" and volta == tiques // 4:
            for n in range(RAJADA_DE_ESTADOS):
                GLib.timeout_add(1 + n * TIQUE_MS, self._simular_um_estado_da_janela, n)

    def _contar_tamanho(self) -> None:
        """Um passo do `--conta-tamanho`, por tique. Fora dele, é um `if` falso."""
        quantos = int(getattr(self.args, "conta_tamanho", 0) or 0)
        if quantos <= 0 or self._tamanho_lido:
            return
        self._voltas_do_tamanho += 1
        volta = self._voltas_do_tamanho - VOLTAS_ATE_ASSENTAR
        if volta == 0:
            self._tamanho_da_janela_ao_partir = int(
                getattr(self.tela, "mudancas_de_tamanho", 0))
            self.ponte.rodar(OBSERVAR_TAMANHO)
            print(f"[tamanho] observando {self.pagina} por {quantos} tiques "
                  f"(~{quantos * TIQUE_MS / 1000:.0f} s), cenário "
                  f"{getattr(self.args, 'cenario', 'parado')}")
        if volta >= 0:
            self._andar_o_cenario(volta, quantos)
        if volta >= quantos:
            self._tamanho_lido = True
            self._mudo_de_proposito = False
            self.ponte.perguntar(LER_TAMANHO, self._leu_tamanho)

    def _leu_tamanho(self, valor: Any, erro: Any) -> None:
        """Imprime a tabela do `--conta-tamanho` e SAI: a medição acabou."""
        import json

        if erro is not None:
            print(f"REPROVA: o observador de tamanho não respondeu — {erro}", file=sys.stderr)
            self._sair("a contagem de tamanho falhou")
            return
        try:
            fora = json.loads(str(valor))
        except ValueError as e:
            print(f"REPROVA: a tabela de tamanho não veio em JSON — {e}", file=sys.stderr)
            self._sair("a contagem de tamanho falhou")
            return
        fora["janela_gtk"] = int(getattr(self.tela, "mudancas_de_tamanho", 0)) \
            - self._tamanho_da_janela_ao_partir
        fora["estados_simulados"] = self.estados_simulados
        fora["cenario"] = getattr(self.args, "cenario", "parado")
        self.tamanhos = fora
        minutos = max(fora.get("ms", 0) / 60000.0, 1e-9)
        print(f"\nTAMANHO em {fora.get('ms', 0) / 1000:.1f} s na {self.pagina}, "
              f"cenário {fora['cenario']}")
        print(f"{'alvo':14s} {'mudanças':>9s} {'por minuto':>11s}  alturas (valor x vezes)")
        for ficha in fora.get("fichas", []):
            alturas = ", ".join(f"{h}x{n}" for h, n in ficha["alturas"].items())
            print(f"{ficha['alvo']:14s} {ficha['n']:9d} {ficha['n'] / minutos:11.1f}  {alturas}")
        for ausente in fora.get("ausentes", []):
            print(f"{ausente:14s}  (não existe nesta página)")
        print(f"JANELA GTK: {fora['janela_gtk']} mudança(s) de tamanho · "
              f"{fora['estados_simulados']} estado(s) simulado(s)")
        with contextlib.suppress(SystemExit):
            self._relatar()
        self._sair("a contagem de tamanho acabou")

    def _sair(self, motivo: str) -> None:
        """Encerra o laço dizendo o porquê, pelo `fechar`, que destrói a janela dentro do laço."""
        self.tela.fechar(motivo)

    def _leu_mutacoes(self, valor: Any, erro: Any) -> None:
        """Imprime a tabela do observador — e SAI, porque a medição acabou."""
        import json

        if erro is not None:
            print(f"REPROVA: o observador não respondeu — {erro}",
                  file=sys.stderr)
            self._sair("a contagem de mutações falhou")
            return
        try:
            fora = json.loads(str(valor))
        except ValueError as e:
            print(f"REPROVA: a tabela não veio em JSON — {e}", file=sys.stderr)
            self._sair("a contagem de mutações falhou")
            return
        self.mutacoes = fora
        tiques = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        print(f"\nMUTAÇÕES DE DOM em {tiques} tiques "
              f"({fora.get('ms', 0) / 1000:.1f} s) na {self.pagina}, "
              f"com a mesa parada")
        print(f"{'endereço':34s} {'tipo':14s} {'o quê':22s} {'n':>6s} {'nós':>6s}")
        for linha in fora.get("linhas", []):
            print(f"{str(linha['campo'])[:34]:34s} {linha['tipo']:14s} "
                  f"{str(linha['detalhe'])[:22]:22s} {linha['n']:6d} "
                  f"{linha['nos']:6d}")
        total = int(fora.get("total", 0))
        print(f"TOTAL: {total} mutações · {total / max(tiques, 1):.1f} por tique")
        if fora.get("blocos_adiados"):
            print(f"blocos ADIADOS por haver um `hef-em-voo` dentro: "
                  f"{fora['blocos_adiados']}")
        with contextlib.suppress(SystemExit):
            self._relatar()
        self._sair("a contagem de mutações acabou")

    def _agendar(self) -> None:
        if self.args.passear:
            roteiro = [p for p in sorted(pacotes.PACOTES) if p not in monta.PAGINAS_QUE_SAIRAM]
            for i, alvo in enumerate(roteiro):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: self._ir(a),
                )
            total = 1600 + len(roteiro) * self.args.parada
        elif self.args.segundos:
            total = int(self.args.segundos * 1000)
        else:
            return
        def fechar() -> bool:
            self._relatar()
            self._sair("o tempo da medição (--segundos ou --passear) acabou")
            return False

        GLib.timeout_add(total, fechar)

    def _provar_mockup(self) -> bool:
        """Passa pelas abas de `monta.ABAS` e mede, em cada uma, o que é dado e o que é desenho."""
        self._fila_de_abas = monta.as_abas_do_produto()
        self.lugar_vazio_com_desenho: dict[str, list[str]] = {}
        print(f"[prova-de-mockup] {len(self._fila_de_abas)} abas · "
              f"{self.args.voltas_por_aba} voltas de {TIQUE_MS} ms em cada uma")
        return self._proxima_aba()

    def _proxima_aba(self) -> bool:
        if not self._fila_de_abas:
            self._relatar_mockup()
            self._sair("a prova de mockup passou pelas abas")
            return False
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora = {}
        self.pronto = False
        self._ir(self._fila_de_abas.pop(0))
        return False

    def _fechou_a_aba(self, pagina: str, valor: Any, erro: Any) -> None:
        """A aba rodou o bastante. Classifica cada campo e segue para a próxima."""
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li a tela ao fim — {erro}")
            self._proxima_aba()
            return
        try:
            vivos: list[list[Any]] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: a leitura final não veio em JSON — {e}")
            self._proxima_aba()
            return

        arquivo = onde.pagina(pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        cravados = regua_do_mockup._campos_cravados(texto)
        self.cravados[pagina] = cravados

        virgem = self.pristino.get(pagina) or []
        if len(virgem) != len(cravados):
            self.cegueiras.append(
                f"{pagina}: o DOM virgem trouxe {len(virgem)} endereços e o "
                f"arquivo {len(cravados)}")
        else:
            for c, linha in zip(cravados, virgem, strict=True):
                k, d, _alvo, v = linha[:4]
                if (str(k), str(d)) != (c.chave, c.dono):
                    self.cegueiras.append(
                        f"{pagina}: o arquivo põe {c.endereco} onde a página "
                        f"virgem põe {d}·{k} — as duas leituras estão fora de ordem")
                elif str(v) != c.valor:
                    self.cegueiras.append(
                        f"{pagina}: a régua lê {c.endereco} como {c.valor!r} no "
                        f"arquivo e a página virgem mostra {v!r} — o parser e o "
                        f"leitor de tela discordam neste alvo ({c.alvo})")

        alinhados, nasceram = regua_do_mockup._alinhar(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3])) for x in vivos])
        selos = regua_do_mockup._selos_alinhados(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3]),
                        bool(x[4]) if len(x) > 4 else False) for x in vivos])
        if nasceram:
            print(f"[prova-de-mockup] {pagina}: {len(nasceram)} endereço(s) "
                  f"NASCERAM na tela (o produto trocou um bloco): "
                  f"{', '.join(f'{d}·{k}' if d else k for k, d in nasceram[:8])}")

        vazaram = _o_desenho_cheio_no_lugar_vazio(
            cravados, alinhados,
            [str(p) for p in (self._carga_de_agora.get("vazios") or [])], texto)
        if vazaram:
            self.lugar_vazio_com_desenho[pagina] = vazaram
            print(f"[prova-de-mockup] {pagina}: {len(vazaram)} campo(s) de lugar "
                  f"SEM controle mostram o desenho de um lugar CHEIO")

        if self.args.sem_cravado:
            cravados = [dataclasses.replace(c, valor="\x00cura arrancada")
                        for c in cravados]
        declarados = regua_do_mockup._declarados_do_pacote(self._carga_de_agora)
        if self.args.sem_selo:
            selos = [False] * len(cravados)
        self.vereditos[pagina] = regua_do_mockup._classificar(
            cravados, alinhados, declarados, selos)
        contas = regua_do_mockup._contar(self.vereditos[pagina])
        print(f"[prova-de-mockup] {pagina:22s} "
              f"produto {contas[regua_do_mockup.PRODUTO]:3d} · "
              f"mockup {contas[regua_do_mockup.MOCKUP]:3d} · "
              f"indecidível {contas[regua_do_mockup.INDECIDIVEL]:3d}")
        self._proxima_aba()

    def _relatar_mockup(self) -> None:
        """A tabela das três contagens, e a lista NOMINAL do que ainda é desenho."""
        r = regua_do_mockup
        print("\n" + "=" * 74)
        print("A RÉGUA DO MOCKUP — o que a tela mostra é dado, ou é o desenho?")
        print("=" * 74)
        print(f"{'aba':22s} {'campos':>7s} {'PRODUTO':>8s} {'RÓTULO':>7s} "
              f"{'MOCKUP':>7s} {'INDECID':>8s} {'pronto':>7s}")
        soma = {r.PRODUTO: 0, r.ROTULO: 0, r.MOCKUP: 0, r.INDECIDIVEL: 0}
        for pagina in sorted(self.vereditos):
            contas = r._contar(self.vereditos[pagina])
            for classe, quantos in contas.items():
                soma[classe] = soma.get(classe, 0) + quantos
            n = sum(contas.values())
            pronto = contas[r.PRODUTO] + contas.get(r.ROTULO, 0)
            print(f"{pagina:22s} {n:7d} {contas[r.PRODUTO]:8d} "
                  f"{contas.get(r.ROTULO, 0):7d} {contas[r.MOCKUP]:7d} "
                  f"{contas[r.INDECIDIVEL]:8d} {(100 * pronto // n) if n else 100:6d}%")
        total = sum(soma.values())
        pronto = soma[r.PRODUTO] + soma[r.ROTULO]
        print(f"{'TODAS':22s} {total:7d} {soma[r.PRODUTO]:8d} "
              f"{soma[r.ROTULO]:7d} {soma[r.MOCKUP]:7d} "
              f"{soma[r.INDECIDIVEL]:8d} {(100 * pronto // total) if total else 100:6d}%")

        print("\nOS CAMPOS QUE AINDA MOSTRAM O DESENHO — é este número que tem de cair:")
        for pagina in sorted(self.vereditos):
            presos = [v for v in self.vereditos[pagina] if v.classe == r.MOCKUP]
            if not presos:
                print(f"  {pagina}: nenhum")
                continue
            print(f"  {pagina} ({len(presos)}):")
            for preso in presos:
                marca = " ← ENDEREÇO MORTO" if preso.declarado is not None else ""
                print(f"      {preso.campo.endereco:28s} = {preso.vivo!r}{marca}")

        coincidem = sum(
            1 for vs in self.vereditos.values() for v in vs
            if v.classe == r.PRODUTO and v.vivo == v.campo.valor
            and v.declarado is not None and v.declarado == v.vivo)
        if coincidem:
            print(f"\nDESTES, {coincidem} SÃO PRODUTO PELO SELO DA VISITA: o valor que o "
                  "piloto\nescreveu COINCIDE com o que o desenho cravou, e antes do selo "
                  "isso\nera INDECIDÍVEL. O selo não é a tela — é o `escrever()` "
                  "registrando\nque esteve naquele elemento com aquele valor. Para "
                  "conferir que ele\ndecide alguma coisa: `--sem-selo` tem de devolvê-los "
                  "aos indecidíveis.")
        if soma[r.INDECIDIVEL]:
            print(f"\nOS {soma[r.INDECIDIVEL]} INDECIDÍVEIS que SOBRAM são campos em que o "
                  "valor coincide\ncom o desenho e o piloto NÃO passou pelo elemento — "
                  "quase sempre\num bloco que a pintura trocou inteiro. Ler a tela não "
                  "separa\n'pintou igual' de 'não pintou', e a régua prefere dizer "
                  "quantos são\na inventar certeza.")

        if self.lugar_vazio_com_desenho:
            print("\nREPROVA: lugar SEM controle mostrando o desenho de um lugar "
                  "COM controle:")
            for pagina in sorted(self.lugar_vazio_com_desenho):
                for linha in self.lugar_vazio_com_desenho[pagina]:
                    print(f"   · {pagina}: {linha}")
        else:
            print("\nNenhum lugar sem controle mostra o desenho de um lugar com "
                  "controle.")
        if self.cegueiras:
            print(f"\nA RÉGUA NÃO ENXERGOU {len(self.cegueiras)} coisa(s) — e isso reprova, "
                  "porque\numa régua que não sabe o que está lendo mede o que quiser:")
            for cegueira in self.cegueiras:
                print(f"   · {cegueira}")
            raise SystemExit(1)
        if self.lugar_vazio_com_desenho:
            raise SystemExit(1)
        if 0 <= self.args.teto_de_mockup < soma[r.MOCKUP]:
            print(f"\nREPROVA: {soma[r.MOCKUP]} campos no desenho, e o teto pedido "
                  f"era {self.args.teto_de_mockup}.")
            raise SystemExit(1)

    def _provar_cliques(self) -> bool:
        """Cliques SINTÉTICOS nos gestos INÓCUOS, para provar o caminho.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato — o
        ouvinte delegado do bootstrap é o que responde. Clicar por coordenada é
        a armadilha que esta casa já pagou duas vezes, e a janela é Offscreen.

        SÓ OS INÓCUOS, e a lista é curta de propósito: `atualizar` é
        `daemon.reload` e `retomar` é `daemon.resume` num daemon que não está
        pausado. `desligar`, `restaurar-de-fabrica` e `refazer-proton` NÃO
        entram — uma régua não mexe na máquina do usuário para provar que sabe clicar.

        **E ATÉ 06/09/2026 ESSA FRASE ERA SÓ UMA FRASE.** Este caminho clicava o
        que a bandeira nomeasse, sem consultar `PERIGOSOS` uma única vez — só o
        `--prova-no-aparelho` a consultava. Achado pela `ONDA5-03-02`, que
        mediu o próprio estrago: o clique do usuário **gravou no perfil real** da dona
        (a gravação foi no-op — o valor já era o mesmo desde as 02:46, e nenhum
        arquivo nasceu no `.historico/` — mas a porta estava aberta e ninguém
        sabia). É a terceira vez em quatro dias que o comentário que
        AVISA do risco fica ao lado do código que o comete.

        A recusa é BARULHENTA e não um pulo em silêncio: uma régua que pula
        calado ensina quem a roda que ela cobriu o botão. `--incluir-perigosos`
        continua sendo a porta, e aí é escolha de quem roda.
        """
        proibidos = sorted(
            g for g in dict.fromkeys(x.strip().split("@")[0] for x in self.args.prova_clique.split(","))
            if (self.pagina, g) in PERIGOSOS or ("*", g) in PERIGOSOS)
        if proibidos and not self.args.incluir_perigosos:
            print(f"[prova] RECUSA: {', '.join(proibidos)} mexe(m) na máquina "
                  f"dela em {self.pagina}. Use --incluir-perigosos se for "
                  "mesmo isso que você quer.", file=sys.stderr)
            raise SystemExit(1)
        def clicar(g: str) -> bool:
            if not self.pronto:
                return True
            self._js(TOCAR + SELETOR % _json(g.strip(), pagina=self.pagina))
            return False

        for i, gesto in enumerate(self.args.prova_clique.split(",")):
            GLib.timeout_add(600 + i * 900, lambda g=gesto: clicar(g))
        return False

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _provar_no_aparelho(self) -> bool:
        """A PROVA BOTÃO A BOTÃO, no aparelho do usuário — pedido, 01/09/2026."""
        arquivo = onde.pagina(self.pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        da_pagina = regua_do_mockup._gestos_cravados(texto)
        registrados = {n for (p, n) in pacotes.GESTOS if p in (self.pagina, "*")}
        perigosos = set() if self.args.incluir_perigosos else PERIGOSOS
        alvos, pulados = regua_do_mockup._alvos_a_clicar(
            da_pagina, registrados, self.pagina, perigosos)
        faltou = regua_do_mockup._cobertura_dos_gestos(
            da_pagina, registrados, alvos, pulados)
        if faltou:
            print(f"[prova] REPROVA: {len(faltou)} endereço(s) clicável(is) de "
                  f"{self.pagina} ficaram de fora: {', '.join(faltou)}", file=sys.stderr)
            raise SystemExit(1)
        so_na_pagina = sorted({g.nome for g in da_pagina} - registrados)
        so_no_codigo = sorted(registrados - {g.nome for g in da_pagina})
        papeis = sorted({g.nome for g in regua_do_mockup._papeis_cravados(texto)}
                        - registrados)
        print(f"[prova] {self.pagina}: {len(da_pagina)} endereços na página · "
              f"{len(registrados)} registrados no código")
        if so_na_pagina:
            print(f"[prova] SÓ NA PÁGINA (ninguém os ligou): {', '.join(so_na_pagina)}")
        if so_no_codigo:
            print(f"[prova] SÓ NO CÓDIGO (a página não tem `data-gesto`): "
                  f"{', '.join(so_no_codigo)}")
        if papeis:
            print(f"[prova] `data-papel` que o ouvinte aceita como gesto e nenhum "
                  f"pacote registra: {', '.join(papeis)}")
        if pulados:
            print(f"[prova] pulados por mexerem na máquina dela: {', '.join(pulados)}")
        if not alvos:
            print(f"[prova] {self.pagina} não tem gesto seguro a clicar")
            return False
        print(f"[prova] {len(alvos)} gesto(s) em {self.pagina}: {', '.join(alvos)}")
        self._fila = list(alvos)
        GLib.timeout_add(400, self._proximo_da_fila)
        return False

    def _proximo_da_fila(self) -> bool:
        """O próximo gesto da prova no aparelho."""
        if self._fila:
            self._um_botao(self._fila.pop(0))
        return False

    def _um_botao(self, nome: str) -> None:
        """Um gesto: fotografa o daemon, clica NO ALVO CERTO, e mede o que mudou."""
        try:
            antes = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon antes ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return
        self._antes_do_gesto = (nome, antes)
        self.desfechos.pop(f"{self.pagina}:{nome}", None)
        prefs = [c["pref"] for c in self._mesa_de_agora if c.get("pref")]

        def anotou(valor: Any, erro: Any) -> None:
            self._onde_clicou[nome] = (
                f"o clique falhou: {erro}" if erro is not None else str(valor))

        self.ponte.perguntar(TOCAR + CLIQUE_COM_ALVO % (_json(nome, pagina=self.pagina),
                                                _json(prefs, pagina=self.pagina)), anotou)
        from pacotes import ponte as _p

        espera = max(self.args.espera, int(_p.teto(_METODO_DO_GESTO.get(nome, "")) * 1000) + 800)
        GLib.timeout_add(espera, self._depois_do_gesto)

    def _depois_do_gesto(self) -> bool:
        nome, antes = getattr(self, "_antes_do_gesto", (None, {}))
        antes_do_daemon: dict[str, Any] = dict(antes)
        if nome is None:
            return False
        try:
            depois = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon depois ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return False
        mudou = {k: (antes_do_daemon.get(k), v) for k, v in depois.items()
                 if antes_do_daemon.get(k) != v
                 and not any(r in k for r in RUIDO)}
        sem_eco = nome in self._sem_eco_da_pagina()
        desfecho, frase = self.desfechos.get(f"{self.pagina}:{nome}", ("aplicou", ""))
        onde_ = self._onde_clicou.get(nome, "")
        self.provas.append({"gesto": nome, "mudou": mudou, "sem_eco": sem_eco,
                            "desfecho": desfecho, "frase": frase, "onde": onde_})
        cabeca = f"[PROVA] {self.pagina} · {nome}"
        if onde_:
            cabeca += f" ({onde_})"
        if desfecho == "sem dono":
            print(f"{cabeca} → SEM DONO: nenhum pacote registra este gesto")
        elif desfecho == "recusou dizendo":
            print(f"{cabeca} → RECUSOU DIZENDO: {frase}")
        elif mudou:
            print(f"{cabeca} → MUDOU {len(mudou)} campo(s):")
            for k, (a, d) in sorted(mudou.items())[:6]:
                print(f"          {k}: {a!r} → {d!r}")
        elif sem_eco:
            print(f"{cabeca} → ACEITO, sem eco no state "
                  f"(o daemon não publica este assunto)")
        else:
            print(f"{cabeca} → DISSE APLICADO E NADA MUDOU no estado do daemon")
        return self._proximo_da_fila()

    def _sem_eco_da_pagina(self) -> set[str]:
        """Os gestos daquela aba cujo efeito o daemon não publica."""
        import importlib

        sem_eco = {monta.GESTO_DA_FITA}
        for arq in sorted((AQUI / "pacotes").glob("a[0-9][0-9]_*.py")):
            mod = importlib.import_module(f"pacotes.{arq.stem}")
            if getattr(mod, "PAGINA", "") == self.pagina:
                return sem_eco | set(getattr(mod, "SEM_ECO", ()))
        return sem_eco

    def _navegar(self, st: dict[str, Any], ctx: pacotes.Contexto) -> None:
        """A Navegação Interna, um passo por tique (A-NAVEGACAO-INTERNA-…-01).

        Os toques do daemon viram atos; com atos ou molduras a desenhar, a
        página mede o leiaute (`NAV_LER`) e a resposta vira as operações que o
        `__hef.nav` executa. A janela fora da frente só ressincroniza a base:
        o R1 dentro do jogo nunca anda uma aba escondida.
        """
        nav = st.get("navegacao") if isinstance(st, dict) else None
        if not isinstance(nav, dict) or not nav.get("interna_ligada"):
            if self._com_molduras:
                self._com_molduras = False
                self._js(NAV_INSTALAR + "window.__hefNav.molduras([])")
            return
        from hefesto_dualsense4unix.interface.pacotes import a06_navegacao

        controles = [c for c in st.get("controllers") or [] if isinstance(c, dict)]
        inputs = {str(c.get("uniq") or ""): c.get("inputs") or {} for c in controles
                  if c.get("uniq")}
        sem = {str(c.get("uniq") or "") for c in controles
               if c.get("is_primary") and a06_navegacao.o_mouse_navega(st)}
        dez = monta.as_abas_do_produto()
        ativa = self._estado_vivo.ativa()
        atos = self._navegador.atos(
            pagina=self.pagina, dez=dez, toques=self._estado_vivo.toques(),
            ativa=ativa, inputs=inputs, sem_selecao=sem)
        if not ativa:
            return
        self._selecoes.esquecer_quem_saiu(set(inputs) - sem)
        self._atos_pendentes.extend(atos)
        if self._leiaute_no_ar or not (self._atos_pendentes or self._selecoes.alguma()):
            return
        pref_de = {str(c.get("uniq") or ""): str(c.get("pref") or "") for c in ctx.mesa}
        cor_de = {str(c.get("uniq") or ""): monta.cor_da_zona(str(c.get("cor")))
                  for c in ctx.mesa if c.get("cor")}
        pendentes, self._atos_pendentes = self._atos_pendentes, []
        pagina = self.pagina
        self._leiaute_no_ar = True

        def mediu(valor: Any, erro: Any) -> None:
            self._leiaute_no_ar = False
            if erro is not None or pagina != self.pagina:
                return
            try:
                leiaute = json.loads(str(valor))
            except ValueError as e:
                self.cegueiras.append(f"{pagina}: o leiaute da navegação não veio em JSON — {e}")
                return
            if not isinstance(leiaute, dict):
                return
            self._agir(pendentes, leiaute, ctx, pref_de, cor_de)

        self.ponte.perguntar(NAV_INSTALAR + NAV_LER, mediu)

    def _agir(self, atos: list[navegacao_interna.Ato], leiaute: dict[str, Any],
              ctx: pacotes.Contexto, pref_de: dict[str, str],
              cor_de: dict[str, str]) -> None:
        """Os atos sobre o leiaute medido: a aba, o Start, a seleção e o X."""
        popup = bool(leiaute.get("popup"))
        ops = self._selecoes.aplicar(
            navegacao_interna.no_espaco_da_pagina(atos, leiaute),
            lambda uniq: navegacao_interna.caixas_do_leiaute(leiaute, pref_de.get(uniq, "")),
            pref_de=pref_de, popup=popup)
        if any(a.tipo == "salvar" for a in atos):
            self._gesto({"gesto": GESTO_DO_START, "pagina": self.pagina, "texto": "Start"})  # (noqa-acento)
        for op in ops:
            if op.get("op") == "clicar" and op.get("pref") and \
                    _a_fita_desta_pagina_escolhe(self.pagina):
                with contextlib.suppress(Exception):
                    _escolher_na_fita(ctx, {"pref": op["pref"]}, ponte)
        molduras = self._selecoes.molduras(pref_de, cor_de)
        self._com_molduras = bool(molduras)
        self._js(NAV_INSTALAR + "window.__hefNav.aplicar("
                 + json.dumps(ops) + "," + json.dumps(molduras) + ")")
        ir = next((a.pagina for a in reversed(atos) if a.tipo == "ir"), "")
        if ir and not popup:
            GLib.idle_add(self._ir, ir)

    def _ir(self, pagina: str) -> bool:
        """Abre uma aba. `False` para o GLib — ver `_proximo_da_fila`."""
        alvo = onde.pagina(_a_pagina_pedida(pagina), publicado=True)
        if not alvo.exists():
            self.tela._morrer(f"não existe a página pedida: {alvo.name}")
            return False
        pacotes.largar_o_que_as_abas_seguram(ponte, mesa=self._mesa_de_agora)
        _soltar_as_ondas()
        self.view.load_uri(alvo.as_uri())
        return False

    def _relatar(self) -> bool:
        if self.relatou:
            return False
        self.relatou = True
        self._estado_vivo.parar()
        pacotes.largar_o_que_as_abas_seguram(ponte)
        if self.args.foto:
            self.tela.fotografar(self.args.foto)
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'tiques':>7s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            tiques = self.tiques.get(pagina, 0)
            print(f"{pagina:22s} {tiques:7d} {len(conta):8d} {pico:8d}")
            if tiques and not conta:
                mudas.append(pagina)
        if self.trocas:
            print("página trocada no meio do tique: " + " · ".join(
                f"{p} {n}" for p, n in sorted(self.trocas.items())))
        if self.provas:
            def classe(p: dict[str, Any]) -> str:
                if p.get("desfecho") == "sem dono":
                    return "sem dono"
                if p.get("desfecho") == "recusou dizendo":
                    return "recusou dizendo"
                if p["mudou"]:
                    return "mudou o daemon"
                if p["sem_eco"]:
                    return "aceito sem eco"
                return "disse aplicado e nada mudou"

            marcas = {"mudou o daemon": "✓", "aceito sem eco": "·",
                      "recusou dizendo": "!", "sem dono": "?",
                      "disse aplicado e nada mudou": "—"}
            contas: dict[str, int] = {}
            for p in self.provas:
                contas[classe(p)] = contas.get(classe(p), 0) + 1
            print("\nPROVA NO APARELHO: " + " · ".join(
                f"{n} {k}" for k, n in sorted(contas.items())))
            for p in self.provas:
                k = classe(p)
                extra = f" — {p['frase']}" if p.get("frase") else ""
                onde_ = f" ({p['onde']})" if p.get("onde") else ""
                print(f"   {marcas[k]} {p['gesto']}{onde_}{extra}")
            mudos = [p["gesto"] for p in self.provas
                     if classe(p) == "disse aplicado e nada mudou"]
            if mudos:
                print(f"   sem efeito e sem `SEM_ECO`: {', '.join(mudos)}")
            forcados = [p["gesto"] for p in self.provas
                        if str(p.get("onde", "")).startswith("ALVO FORCADO")]
            if forcados:
                print(f"   alvo FORÇADO pela régua (a página não diz em quem "
                      f"agir): {', '.join(forcados)}")
        if self.gestos:
            print(f"gestos: {len(self.gestos)} · aplicados: {len(self.aplicados)} · "
                  f"sem dono: {len(set(self.recusados))}")
            for r in sorted(set(self.recusados)):
                print(f"   sem dono: {r}")
        if self.custos:
            ordenado = sorted(self.custos)
            print(f"custo do tique: mediana {ordenado[len(ordenado)//2]:.2f} ms · "
                  f"max {ordenado[-1]:.2f} ms · teto {TIQUE_MS} ms")
        if self.custo_do_ipc:
            ipc = sorted(self.custo_do_ipc)
            print(f"custo do IPC:   mediana {ipc[len(ipc)//2]:.2f} ms · "
                  f"max {ipc[-1]:.2f} ms")
        if self._pulados_por_voo or self._pulados_por_custo:
            print(f"tiques pulados: {self._pulados_por_voo} com pintura no ar · "
                  f"{self._pulados_por_custo} pelo custo do anterior")
        if mudas:
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)
        return False


_ALVOS_QUE_O_LUGAR_VAZIO_COBRA = frozenset(
    {"texto", "html", "cor", "atributo", "plastico"})

_TAG_DO_LUGAR = r'<[a-zA-Z][^>]*\bdata-controle="(p\d+)"[^>]*>'
_ENDERECO_NA_TAG = r'\bdata-(?:campo|papel|hef)="([^"]+)"'


def _o_lugar_no_arquivo(texto: str) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Os lugares que o arquivo publica VAZIOS, e os endereços que SÃO o lugar."""
    import re

    vazios: set[str] = set()
    proprios: set[tuple[str, str]] = set()
    for m in re.finditer(_TAG_DO_LUGAR, texto):
        tag, pref = m.group(0), m.group(1)
        if 'data-conectado="nao"' in tag:
            vazios.add(pref)
        proprios |= {(pref, chave) for chave in re.findall(_ENDERECO_NA_TAG, tag)}
    return frozenset(vazios), frozenset(proprios)


def _o_desenho_cheio_no_lugar_vazio(
        cravados: list[regua_do_mockup._Campo],
        vivos: list[str],
        vazios_agora: Iterable[str],
        texto: str) -> list[str]:
    """Os campos de um lugar SEM controle que mostram o desenho de um lugar CHEIO.

    O que o desenho diz do lugar vazio DAQUELE número não é vazamento: o número do jogador
    (`jogador`, o «P1» de quem joga) é o mesmo cheio ou vazio, e o lugar vazio do desenho o
    diz pela mesma troca de número que o molde usa (`pacotes._a_palavra_do_desenho`).
    """
    do_desenho, proprios = _o_lugar_no_arquivo(texto)
    cheio: dict[tuple[str, str], set[str]] = {}
    vazio: dict[tuple[str, str], set[str]] = {}
    vazio_por_numero: dict[tuple[str, str], dict[int, list[str]]] = {}
    for c in cravados:
        if c.dono not in pacotes.TODOS_OS_LUGARES:
            continue
        (vazio if c.dono in do_desenho else cheio).setdefault(
            (c.chave, c.alvo), set()).add(c.valor)
        if c.dono in do_desenho:
            vazio_por_numero.setdefault((c.chave, c.alvo), {}).setdefault(
                int(c.dono[1:]), []).append(c.valor)
    agora = set(vazios_agora)
    fora: list[str] = []
    for c, vivo in zip(cravados, vivos, strict=True):
        if (c.dono not in agora or c.rotulo
                or c.alvo not in _ALVOS_QUE_O_LUGAR_VAZIO_COBRA
                or (c.dono, c.chave) in proprios
                or vivo in ("", pacotes.TRAVESSAO, regua_do_mockup.SUMIU)):
            continue
        k = (c.chave, c.alvo)
        if k in vazio_por_numero and vivo == pacotes._a_palavra_do_desenho(
                c.alvo, vazio_por_numero[k])(int(c.dono[1:])):
            continue
        if vivo in cheio.get(k, ()) and vivo not in vazio.get(k, ()):
            fora.append(f"{c.endereco} [{c.alvo}] = {vivo[:70]!r}")
    return fora


_SECOES_POR_CHAVE: dict[str, int] = {"mesa": 1, "colunas": 2, "blocos": 1, "marcas": 1}


def _achatar_a_carga(carga: dict[str, Any]) -> dict[tuple[str, ...], tuple[Any, Any]]:
    """`{caminho: (retrato, valor)}` de cada valor que o `pintar` lê sozinho."""
    import json

    fora: dict[tuple[str, ...], tuple[Any, Any]] = {}

    def descer(caminho: tuple[str, ...], valor: Any, niveis: int) -> None:
        if niveis and isinstance(valor, dict):
            for k, v in valor.items():
                descer((*caminho, str(k)), v, niveis - 1)
            return
        retrato = (("t", valor) if isinstance(valor, str)
                   else ("j", json.dumps(valor, sort_keys=True, ensure_ascii=False,
                                         default=str)))
        fora[caminho] = (retrato, valor)

    for secao, valor in carga.items():
        descer((str(secao),), valor, _SECOES_POR_CHAVE.get(str(secao), 0))
    return fora


def _o_que_mudou(antes: dict[tuple[str, ...], tuple[Any, Any]],
                 agora: dict[tuple[str, ...], tuple[Any, Any]]) -> dict[str, Any]:
    """A carga com só o que mudou entre as duas, na forma que o `pintar` lê."""
    dif: dict[str, Any] = {}
    for caminho, (retrato, valor) in agora.items():
        velho = antes.get(caminho)
        if velho is not None and velho[0] == retrato:
            continue
        no = dif
        for k in caminho[:-1]:
            no = no.setdefault(k, {})
        no[caminho[-1]] = valor
    return dif


def _a_diferenca_muda_a_forma(dif: dict[str, Any], moldes: frozenset[str]) -> bool:
    """A diferença troca ou clona nós? A fita, os lugares, um bloco ou a lista de um molde."""
    return ("fita" in dif or "ocupados" in dif or "vazios" in dif or "blocos" in dif
            or any(k in moldes for k in (dif.get("mesa") or {})))


def _esquecer_a_pintura(piloto: Any) -> None:
    """O próximo tique do `piloto` manda a carga INTEIRA, e não só o que mudou."""
    piloto._pintada = None


def _soltar_as_ondas() -> None:
    """As ondas sonoras soltam todo nó. Nunca levanta."""
    from hefesto_dualsense4unix.integrations import ondas_de_som

    with contextlib.suppress(Exception):
        ondas_de_som.o_de_sempre().seguir({})


def _json(obj: Any, pagina: str = "") -> str:
    """Serializa para o WebView — e DENUNCIA o que o usuário mandou tirar da tela."""
    import json

    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        FRASES_BANIDAS,
        PALAVRAS_BANIDAS,
        primeiro_trecho_banido,
        sem_o_citado,
        sem_o_trecho,
    )

    saida = json.dumps(obj, ensure_ascii=False, default=str)
    teto = len(FRASES_BANIDAS) + len(PALAVRAS_BANIDAS) + 1
    for campo, folha in _folhas_da_carga(obj):
        if isinstance(folha, str) and folha in _TEXTOS_LIDOS_PELO_FUNIL:
            banidas = _TEXTOS_LIDOS_PELO_FUNIL[folha]
        else:
            lido = sem_o_citado(folha) if isinstance(folha, str) else folha
            resto = json.dumps(lido, ensure_ascii=False, default=str)
            achadas: list[str] = []
            for _ in range(teto):
                banida = primeiro_trecho_banido(resto)
                if banida is None:
                    break
                achadas.append(banida)
                resto = sem_o_trecho(resto, banida)
            banidas = tuple(achadas)
            if isinstance(folha, str):
                if len(_TEXTOS_LIDOS_PELO_FUNIL) >= TEXTOS_QUE_O_FUNIL_LEMBRA:
                    _TEXTOS_LIDOS_PELO_FUNIL.pop(next(iter(_TEXTOS_LIDOS_PELO_FUNIL)))
                _TEXTOS_LIDOS_PELO_FUNIL[folha] = banidas
        for banida in banidas:
            dono = (banida, pagina, campo)
            if dono in _BANIDAS_JA_DENUNCIADAS:
                continue
            _BANIDAS_JA_DENUNCIADAS.add(dono)
            print(f"[texto banido] {banida!r} em {_onde_foi(pagina, campo)}. A frase "
                  "é defeito do dono dela — ver `interface/frases_que_ela_baniu.py`.",
                  file=sys.stderr)
    return saida


def _onde_foi(pagina: str, campo: str) -> str:
    """`09-sistema.html · registro-texto` — a página e o campo da denúncia."""
    return f"{pagina or 'página sem nome'} · {campo or 'campo sem nome'}"


def _folhas_da_carga(obj: Any, campo: str = "") -> Iterable[tuple[str, Any]]:
    """`(campo, valor)` de cada valor que pode ter letra — o campo é a chave."""
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            yield from _folhas_da_carga(valor, str(chave))
    elif isinstance(obj, (list, tuple)):
        for valor in obj:
            yield from _folhas_da_carga(valor, campo)
    elif obj is None or isinstance(obj, (bool, int, float)):
        return
    else:
        yield campo, obj


_BANIDAS_JA_DENUNCIADAS: set[tuple[str, str, str]] = set()

TEXTOS_QUE_O_FUNIL_LEMBRA = 4096
_TEXTOS_LIDOS_PELO_FUNIL: dict[str, tuple[str, ...]] = {}


SEGUNDOS_DA_LARGADA_NA_SAIDA = 2.0


@contextlib.contextmanager
def _o_processo_da_janela() -> Iterator[None]:
    """O que o processo da janela liga ao subir e desliga ao sair.

    A LARGADA MORA AQUI porque todo fim da janela passa por este `finally`: o X
    (`destroy` → `Gtk.main_quit`), o `agendar_saida` e o `_morrer`. O teste da
    vibração e o da háptica de cada controle voltam ao jogo na saída, e o teto
    do serviço fica como rede só para a janela que morre sem `finally`.

    A saída ESPERA a largada na fila dos controles: um «Testar» ou um «Parar»
    ainda no ar termina antes dela, e as filas são de fios que morrem com o
    processo. O prazo fica abaixo do teto do serviço, que é a rede de depois.
    """
    from hefesto_dualsense4unix.profiles import loader

    loader.ligar_a_leitura_pela_assinatura()
    pacotes.fios.ligar_a_janela()
    try:
        yield
    finally:
        pacotes.fios.ligar_a_janela(False)
        from hefesto_dualsense4unix.app.actions.recarga_do_install import arquivo_da_aba

        arquivo_da_aba(os.getpid()).unlink(missing_ok=True)
        try:
            if _AS_ABAS_CHEGARAM:
                pacotes.largar_o_que_as_abas_seguram(
                    ponte, esperar_s=SEGUNDOS_DA_LARGADA_NA_SAIDA)
        finally:
            loader.desligar_a_leitura_pela_assinatura()


def _recusar_a_tela_que_nao_foi_desviada(desviada: str | None) -> None:
    """Sai se a tela que o GTK abriu não é o Xvfb do desvio.

    O GTK abriu a tela ao ser importado: quem importou o piloto antes do desvio (ou o chamou
    com `--conta-tamanho` abreviado) já está falando com a sessão de quem chamou, e o desvio
    de agora só muda o ambiente."""
    from gi.repository import Gdk

    aberta = Gdk.Display.get_default()
    nome = aberta.get_name() if aberta is not None else "(nenhuma)"
    if desviada is None or nome != desviada:
        raise SystemExit(
            f"REPROVA: a janela do `--conta-tamanho` abriria na tela {nome}, que não é o X de "
            "mentira. Rode `hefesto_vivo.py --conta-tamanho N` direto (o desvio vem antes do "
            "GTK), no lar de mentira, ou com `--oculta`."
        )
    print(f"[conta-tamanho] a janela com barra nasce no Xvfb {nome}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true",
                   help="Gtk.OffscreenWindow — nada aparece na tela dela. "
                        "Ela tem UMA tela; é o padrão de toda régua desta casa.")
    p.add_argument("--segundos", type=float, default=0.0,
                   help="fecha a janela depois de N segundos e relata. ZERO (o "
                        "padrão) mantém a janela aberta até ela fechar — que é "
                        "o comportamento do PRODUTO. Só a bancada põe prazo.")
    p.add_argument("--passear", action="store_true",
                   help="visita as nove abas e mede a pintura de cada uma")
    p.add_argument("--parada", type=int, default=900,
                   help="ms em cada aba durante o passeio")
    p.add_argument("--foto", default="")
    p.add_argument("--abre", default="",
                   help="abrir direto numa aba: o número (`10`), o nome sem "
                        "extensão (`10-perfis`) ou o arquivo "
                        "(`10-perfis.html`). Página que não existe REPROVA")
    p.add_argument("--prova-no-aparelho", action="store_true",
                   help="clica CADA gesto da aba, um por vez, e mede o que mudou "
                        "no estado do daemon — a prova que ela pediu")
    p.add_argument("--entre", type=int, default=2500,
                   help="ms entre um gesto e o próximo")
    p.add_argument("--espera", type=int, default=1200,
                   help="ms entre o clique e a leitura do daemon")
    p.add_argument("--incluir-perigosos", action="store_true",
                   help="inclui os gestos que mexem na máquina dela (desligar, "
                        "reiniciar, restaurar) — escolha de quem roda")
    p.add_argument("--prova-clique", default="",
                   help="gestos a tocar, por vírgula, até o daemon; `gesto@linha` escolhe o "
                        "`data-linha` e `gesto@linha=valor` a opção da lista; a barra é arrastada e solta, e a lista passa à seguinte")
    p.add_argument("--sem-cor", action="store_true",
                   help="MORDIDA: sem o leitor de cor do plástico")
    p.add_argument("--sem-ondas", action="store_true",
                   help="MORDIDA: arranca o medidor de áudio das ondas sonoras "
                        "da aba 02. As catorze barrinhas de cada medidor têm de "
                        "ACHATAR e ficar cinza — se continuarem desenhando a "
                        "onda do arquivo, elas nunca foram dado")
    p.add_argument("--prova-de-mockup", action="store_true",
                   help="passa pelas abas e diz, campo a campo, o que é DADO "
                        "e o que ainda é o DESENHO cravado no arquivo")
    p.add_argument("--voltas-por-aba", type=int, default=8,
                   help="quantos tiques a pintura corre em cada aba antes da "
                        "medição. Uma volta só mede um INSTANTE, não um "
                        "comportamento — o padrão dá 4 s por aba")
    p.add_argument("--teto-de-mockup", type=int, default=-1,
                   help="reprova se mais de N campos ainda mostrarem o desenho. "
                        "NEGATIVO (o padrão) só mede e relata — é assim que ele "
                        "vira catraca quando o número começar a cair")
    p.add_argument("--sem-cravado", action="store_true",
                   help="MORDIDA: arranca a comparação com o arquivo publicado e "
                        "compara a tela com ela mesma. A régua tem de parar de "
                        "acusar — se continuar acusando, ela não mede o que diz")
    p.add_argument("--na-frente", action="store_true",
                   help="PROVA: a janela (mesmo oculta) se declara na frente à "
                        "Navegação Interna, para a bancada no lar de mentira "
                        "provar o R1, o L1 e a seleção sem janela visível")
    p.add_argument("--sem-selo", action="store_true",
                   help="MORDIDA: arranca o selo da visita. Os campos que "
                        "coincidem com o desenho voltam a ser INDECIDÍVEIS — e "
                        "se o número não voltar, o selo não estava decidindo nada")
    p.add_argument("--conta-mutacoes", type=int, default=0, metavar="N",
                   help="conta as mutações de DOM em N tiques COM A MESA "
                        "PARADA, por endereço e por tipo, e sai. O número certo "
                        "é ZERO para tudo o que não mudou de valor — o que "
                        "sobrar é a tela sambando")
    p.add_argument("--conta-tamanho", type=int, default=0, metavar="N",
                   help="conta, em N tiques, quantas vezes mudou a caixa de `.janela`, "
                        "`.miolo`, `.registro` e a vista (o que `100dvh` lê), e sai. O "
                        "número certo, sem a janela mudar de tamanho de verdade, é ZERO. "
                        "Abre uma janela com barra: só roda no X de mentira")
    p.add_argument("--cenario", choices=("parado", "mudo", "rajada"), default="parado",
                   help="o que acontece durante o `--conta-tamanho`: `parado` (nada), "
                        "`mudo` (o serviço vence o prazo no terço do meio) ou `rajada` "
                        "(%d estados de maximizar/restaurar, sem mudar o tamanho)"
                   % RAJADA_DE_ESTADOS)
    args = p.parse_args()

    if args.conta_tamanho and os.environ.get("HEFESTO_NA_TELA") == "1" and not args.oculta:
        print("[conta-tamanho] ligando `--oculta`: a tela é UMA e não é do instrumento.")
        args.oculta = True
    if args.conta_tamanho and not args.oculta:
        from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

        _recusar_a_tela_que_nao_foi_desviada(garantir_tela_de_mentira(anunciar=False))

    if args.conta_mutacoes and not args.oculta:
        print("[conta-mutações] ligando `--oculta`: ela tem UMA tela.")
        args.oculta = True

    if args.prova_de_mockup and not args.oculta:
        print("[prova-de-mockup] ligando `--oculta`: esta régua abre as nove abas e "
              "ela tem UMA tela.")
        args.oculta = True

    from hefesto_dualsense4unix.integrations import ondas_de_som

    ondas_de_som.ligar(not args.sem_ondas)

    piloto = Piloto(args)

    def _quando_a_pagina_estiver_de_pe(tarefa: Callable[[], Any]) -> None:
        """Agenda ``tarefa`` para o instante em que a PÁGINA confirmar — não o relógio."""

        def _tique() -> bool:
            if piloto.tela.morreu is not None:
                return False
            if not piloto.tela.na_aba:
                return True
            tarefa()
            return False

        GLib.timeout_add(120, _tique)

    if args.prova_de_mockup:
        _quando_a_pagina_estiver_de_pe(piloto._provar_mockup)
    if args.prova_no_aparelho:
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2500, piloto._provar_no_aparelho))
    if args.prova_clique:
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2000, piloto._provar_cliques))
    if args.abre:
        _quando_a_pagina_estiver_de_pe(lambda: piloto._ir(args.abre))
    with _o_processo_da_janela():
        piloto.tela.fechar_por_sinal()
        Gtk.main()
        piloto.tela.anotar_o_fim("o laço do GTK terminou sem motivo registrado")

    if piloto.tela.morreu is not None:
        print(f"\nREPROVA: a página morreu e nada foi medido — {piloto.tela.morreu}",
              file=sys.stderr)
        raise SystemExit(1)
    if args.prova_de_mockup and not piloto.visitadas:
        print("\nREPROVA: `--prova-de-mockup` não visitou aba nenhuma.",
              file=sys.stderr)
        raise SystemExit(1)


def _ligar_as_abas() -> None:
    """O que depende das nove abas: o gesto da fita e a lista dos perigosos."""
    global PERIGOSOS, SELETOR_DO_DONO
    _registrar_a_fita()
    _registrar_o_menu()
    PERIGOSOS = pacotes.perigosos()
    SELETOR_DO_DONO = '[data-uniq],[data-controle=""],' + ",".join(
        f'[data-controle="{lugar}"]' for lugar in sorted(pacotes.TODOS_OS_LUGARES))


def _segundos_de_vida() -> float | None:
    """Há quanto tempo este processo nasceu, pelo `/proc` (None fora do Linux)."""
    try:
        with open("/proc/self/stat", encoding="ascii") as arq:
            campos = arq.read().rsplit(")", 1)[1].split()
        nasceu = int(campos[19]) / os.sysconf("SC_CLK_TCK")
        return time.clock_gettime(time.CLOCK_BOOTTIME) - nasceu
    except (OSError, ValueError, IndexError, AttributeError):
        return None


_AS_ABAS_CHEGARAM = __name__ != "__main__"

TETO_DA_ESPERA_DO_WEBKIT_S = 3.0


def _esperar_o_webkit_comecar(tela: Any, teto_s: float = TETO_DA_ESPERA_DO_WEBKIT_S) -> None:
    """Roda o laço do GTK até o WebKit começar a carregar a página (`committed`)."""
    from gi.repository import WebKit2

    fim: list[str] = []
    vigia_no_ar = [True]

    def acabou(motivo: str) -> None:
        if not fim:
            fim.append(motivo)
            Gtk.main_quit()

    def viu(_view: Any, evento: Any) -> None:
        if evento in (WebKit2.LoadEvent.COMMITTED, WebKit2.LoadEvent.FINISHED):
            acabou("carregando")

    def olhar() -> bool:
        if tela.morreu is not None:
            acabou("morreu")
        elif time.monotonic() >= prazo:
            acabou("teto")
        vigia_no_ar[0] = not fim
        return vigia_no_ar[0]

    def sair_do_laco_que_vem() -> bool:
        Gtk.main_quit()
        return False

    ligacao = tela.view.connect("load-changed", viu)
    prazo = time.monotonic() + teto_s
    vigia = GLib.timeout_add(20, olhar)
    try:
        Gtk.main()
    finally:
        if vigia_no_ar[0]:
            GLib.source_remove(vigia)
        tela.view.disconnect(ligacao)
    if not fim:
        GLib.idle_add(sair_do_laco_que_vem)


def _importar_as_abas(tela: Any = None) -> None:
    """As nove abas e a `mesa_viva`, depois de a janela pedir a página."""
    global _AS_ABAS_CHEGARAM, mesa_viva, pacotes, ponte
    if _AS_ABAS_CHEGARAM:
        return
    if tela is not None:
        _esperar_o_webkit_comecar(tela)
    from hefesto_dualsense4unix.interface import mesa_viva, pacotes
    from hefesto_dualsense4unix.interface.pacotes import ponte

    _AS_ABAS_CHEGARAM = True
    _ligar_as_abas()


TOCAR = r"""
window.__hefTocar = window.__hefTocar || {
  seletor: function(pedido){
    const g = String(pedido).split('@')[0];
    return '[data-gesto="' + g + '"],[data-hef-gesto="' + g + '"],'
         + '[data-papel="' + g + '"],.r-' + g;
  },
  achar: function(raiz, pedido){
    const linha = (String(pedido).split('@')[1] || '').split('=')[0];
    const todos = Array.from(raiz.querySelectorAll(this.seletor(pedido)));
    const casa = function(el){
      return linha ? el.dataset.linha === linha || el.dataset.campo === linha
                   : !el.dataset.linha && !el.dataset.campo;
    };
    return todos.find(casa) || (linha ? null : todos[0] || null);
  },
  tocar: function(el, pedido){
    const tag = (el.tagName || '').toLowerCase();
    const valor = String(pedido || '').split('=')[1];
    if(tag === 'select' && valor !== undefined){
      el.value = valor;
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return;
    }
    if(tag === 'input' && String(el.type).toLowerCase() === 'range'){
      const antes = el.value;
      el.stepUp();
      if(el.value === antes) el.stepDown();
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return;
    }
    if(tag === 'select'){
      const n = el.options.length;
      for(let k = 1; k < n; k++){
        const i = (el.selectedIndex + k) % n;
        const o = el.options[i];
        if(o.disabled || o.hidden || (o.parentElement && o.parentElement.disabled)) continue;
        el.selectedIndex = i;
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return;
      }
      return;
    }
    el.click();
  },
};
"""


if __name__ != "__main__":
    _ligar_as_abas()

if __name__ == "__main__":
    main()
