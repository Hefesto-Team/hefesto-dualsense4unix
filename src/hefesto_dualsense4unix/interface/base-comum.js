(() => {
  let dica = null, alvo = null;
  const descrever = (el, liga) => {
    const lista = (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(t => t && t !== 'hef-dica');
    if (liga) lista.push('hef-dica');
    if (lista.length) el.setAttribute('aria-describedby', lista.join(' ')); else el.removeAttribute('aria-describedby');
  };
  const mostrar = el => {
    if (alvo && alvo !== el) descrever(alvo, false);
    if (!dica) { dica = document.createElement('div'); dica.id = 'hef-dica'; dica.className = 'da-base'; dica.setAttribute('role', 'tooltip'); }
    alvo = el; dica.textContent = el.dataset.dica;
    descrever(el, true);
    if (!dica.isConnected) document.body.append(dica);
    const r = el.getBoundingClientRect(), d = dica.getBoundingClientRect();
    let x = r.left + r.width / 2 - d.width / 2, y = r.bottom + 8;
    if (y + d.height > innerHeight - 6) y = r.top - d.height - 8;
    dica.style.left = Math.max(6, Math.min(x, innerWidth - d.width - 6)) + 'px'; dica.style.top = y + 'px';
    dica.classList.add('visivel');
  };
  const esconder = () => { if (alvo) descrever(alvo, false); alvo = null; if (dica) dica.classList.remove('visivel'); };
  document.addEventListener('mousemove', e => {
    let el = e.target && e.target.nodeType === 1 ? e.target : null;
    for (let n = 0; el && n < 4; el = el.parentElement, n++) {
      if (getComputedStyle(el).textOverflow !== 'ellipsis') continue;
      const daRegra = el.hasAttribute('data-dica-do-corte');
      if (el.hasAttribute('data-dica') && !daRegra) return;
      const texto = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (texto && el.scrollWidth > el.clientWidth + 1) {
        el.setAttribute('data-dica', texto); el.setAttribute('data-dica-do-corte', '');
      } else if (daRegra) {
        el.removeAttribute('data-dica'); el.removeAttribute('data-dica-do-corte');
      }
      return;
    }
  }, true);
  for (const [ev, f] of [['mouseover', 'in'], ['focusin', 'in'], ['mouseout', 'out'], ['focusout', 'out']])
    document.addEventListener(ev, e => {
      if (window.__hefDica) return;
      const el = e.target.closest && e.target.closest('[data-dica]');
      if (f === 'in' && el && el.dataset.dica && el !== alvo) mostrar(el);
      if (f === 'out' && el && !el.contains(e.relatedTarget)) esconder();
    });
  const sincronizar = b => {
    const on = b.getAttribute('aria-pressed') === 'true';
    const pedido = on ? 'personalizado' : 'automatico';
    if (b.dataset.modo !== pedido) b.dataset.modo = pedido;
    if (b.dataset.governa)
      document.querySelectorAll(b.dataset.governa).forEach(el => el.classList.toggle('governado-pelo-jogo', on));
  };
  const sincronizarTodos = () => document.querySelectorAll('.modo-auto').forEach(sincronizar);
  sincronizarTodos();
  new MutationObserver(ms => {
    if (ms.some(m => m.type === 'childList' || (m.target.matches && m.target.matches('.modo-auto')))) sincronizarTodos();
  }).observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['aria-pressed']});
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.modo-auto');
    if (b) setTimeout(() => b.setAttribute('aria-pressed', b.getAttribute('aria-pressed') === 'true' ? 'false' : 'true'), 0);
  });
  const fechar = () => document.querySelectorAll('.menu-hefesto.vivo').forEach(m => m.remove());
  document.addEventListener('contextmenu', e => {
    e.preventDefault(); fechar();
    const m = document.createElement('div'); m.className = 'menu-hefesto vivo'; m.setAttribute('role', 'menu');
    const sel = String(getSelection()).trim() !== '';
    const servico = (document.querySelector('[data-campo="servico"]') || {dataset: {}}).dataset.servico;
    const ligar = servico === 'parado' || servico === 'pausado';
    const item = ligar
      ? '<button type="button" role="menuitem" data-gesto="menu-desligar" data-dica="O Hefesto volta a cuidar dos controles">Ligar</button>'
      : '<button type="button" role="menuitem" data-gesto="menu-desligar" data-menu="desligar" data-dica="O Hefesto sai da frente e o jogo lê o controle direto">Desligar</button>';
    m.innerHTML = `<button type="button" role="menuitem" data-menu="copiar" ${sel ? '' : 'disabled'}>Copiar</button><hr>
      <button type="button" role="menuitem" data-gesto="menu-atualizar">Atualizar</button>
      ${item}
      <button type="button" role="menuitem" data-gesto="menu-reiniciar">Reiniciar</button>
      <button type="button" role="menuitem" data-gesto="menu-reconectar" data-dica="Desliga e liga de novo todos os controles">Reconectar controles</button><hr>
      <button type="button" role="menuitem" data-gesto="menu-fechar">Fechar</button>`;
    document.body.append(m);
    const r = m.getBoundingClientRect();
    m.style.left = Math.min(e.clientX, innerWidth - r.width - 6) + 'px';
    m.style.top = Math.min(e.clientY, innerHeight - r.height - 6) + 'px';
  });
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.menu-hefesto button');
    if (!b) { fechar(); return; }
    if (b.disabled) return;
    if (b.dataset.menu === 'copiar') document.execCommand('copy');
    if (b.dataset.menu === 'desligar') {
      if (b.textContent.trim() !== 'Confirma?') { setTimeout(() => { b.textContent = 'Confirma?'; }, 0); return; }
    }
    setTimeout(fechar, 0);
  });
})();
(() => {
  const NATIVO = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[contenteditable=""],[contenteditable="true"]';
  const GESTO = '[data-gesto],[data-hef-gesto]';
  const SEM_PARADA = 'option,optgroup,html,body';
  const aparece = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const jaTemParada = el => el.hasAttribute('tabindex') || el.matches(NATIVO)
    || Array.from(el.querySelectorAll(NATIVO)).some(d => !d.disabled && aparece(d));
  const PEDE_PARADA = GESTO + ',[data-dica]';
  const marcar = raiz => {
    const todos = raiz.matches && raiz.matches(PEDE_PARADA) ? [raiz] : [];
    raiz.querySelectorAll && todos.push(...raiz.querySelectorAll(PEDE_PARADA));
    for (const el of todos) if (!el.matches(SEM_PARADA) && !jaTemParada(el)) el.setAttribute('tabindex', '0');
  };
  marcar(document.body);
  new MutationObserver(ms => {
    for (const m of ms) {
      if (m.type === 'attributes') marcar(m.target);
      else for (const n of m.addedNodes) if (n.nodeType === 1) marcar(n);
    }
  }).observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['data-dica']});
  document.addEventListener('keydown', e => {
    if ((e.key !== 'Enter' && e.key !== ' ') || e.defaultPrevented || e.repeat) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const el = e.target;
    if (!el || !el.matches || !el.matches(GESTO) || el.matches(NATIVO)) return;
    e.preventDefault();
    el.click();
  });
  const caixaDe = tela => tela.querySelector('.tn-cx') || tela.firstElementChild;
  const prepararTelas = () => document.querySelectorAll('.tela-nova').forEach(tela => {
    const caixa = caixaDe(tela);
    if (!caixa) return;
    if (!caixa.hasAttribute('role')) caixa.setAttribute('role', 'dialog');
    if (!caixa.hasAttribute('aria-modal')) caixa.setAttribute('aria-modal', 'true');
    const tit = tela.querySelector('.tn-tit');
    if (tit && !caixa.hasAttribute('aria-label') && !caixa.hasAttribute('aria-labelledby'))
      caixa.setAttribute('aria-label', tit.textContent.replace(/\s+/g, ' ').trim());
  });
  prepararTelas();
  const PARADAS = 'a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  const paradasDe = caixa => Array.from(caixa.querySelectorAll(PARADAS)).filter(aparece);
  const aberta = () => document.querySelector('.tela-nova:target');
  let quemAbriu = null, ultimo = null, estavaAberta = false;
  document.addEventListener('focusin', e => { if (!e.target.closest || !e.target.closest('.tela-nova')) ultimo = e.target; });
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    if (a && !a.closest('.tela-nova')) ultimo = a;
  }, true);
  const aoMudar = () => {
    const tela = aberta();
    if (tela && !estavaAberta) {
      quemAbriu = ultimo;
      const caixa = caixaDe(tela);
      const alvo = caixa && (caixa.querySelector('[autofocus]') || paradasDe(caixa)[0]);
      if (alvo) alvo.focus();
      else if (caixa) { caixa.setAttribute('tabindex', '-1'); caixa.focus(); }
    } else if (!tela && estavaAberta && quemAbriu && quemAbriu.isConnected) {
      quemAbriu.focus(); quemAbriu = null;
    }
    estavaAberta = !!tela;
  };
  addEventListener('hashchange', aoMudar);
  addEventListener('DOMContentLoaded', aoMudar);
  addEventListener('load', aoMudar);
  aoMudar();
  document.addEventListener('keydown', e => {
    const tela = aberta();
    if (!tela || e.defaultPrevented) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      const x = tela.querySelector('a.tn-x,.fechar,[data-fechar]');
      if (x) x.click(); else location.hash = '';
    } else if (e.key === 'Tab') {
      const caixa = caixaDe(tela), lista = caixa ? paradasDe(caixa) : [];
      if (!lista.length) { e.preventDefault(); return; }
      const dentro = caixa.contains(document.activeElement);
      const fim = e.shiftKey ? lista[0] : lista[lista.length - 1];
      if (!dentro || document.activeElement === fim) { e.preventDefault(); (e.shiftKey ? lista[lista.length - 1] : lista[0]).focus(); }
    }
  });
})();
