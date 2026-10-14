/* Base comum das abas: a dica no hover e o menu do botão direito. Uma vez por página, igual em todas. */
(() => {
  /* A dica: só nasce aqui quando NÃO há a camada da janela (`__hefDica`, do piloto), que é a dona
     do `#hef-dica` no produto. Os dois nunca rodam juntos: o teste vem a cada evento, porque a
     camada da janela chega depois da carga da página. */
  let dica = null, alvo = null;
  const mostrar = el => {
    if (!dica) { dica = document.createElement('div'); dica.id = 'hef-dica'; dica.className = 'da-base'; dica.setAttribute('role', 'tooltip'); }
    alvo = el; dica.textContent = el.dataset.dica;
    if (!dica.isConnected) document.body.append(dica);
    const r = el.getBoundingClientRect(), d = dica.getBoundingClientRect();
    let x = r.left + r.width / 2 - d.width / 2, y = r.bottom + 8;
    if (y + d.height > innerHeight - 6) y = r.top - d.height - 8;
    dica.style.left = Math.max(6, Math.min(x, innerWidth - d.width - 6)) + 'px'; dica.style.top = y + 'px';
    dica.classList.add('visivel');
  };
  const esconder = () => { alvo = null; if (dica) dica.classList.remove('visivel'); };
  for (const [ev, f] of [['mouseover', 'in'], ['focusin', 'in'], ['mouseout', 'out'], ['focusout', 'out']])
    document.addEventListener(ev, e => {
      if (window.__hefDica) return;
      const el = e.target.closest && e.target.closest('[data-dica]');
      if (f === 'in' && el && el.dataset.dica && el !== alvo) mostrar(el);
      if (f === 'out' && el && !el.contains(e.relatedTarget)) esconder();
    });
  /* O Modo automático: a área que o botão governa esmaece enquanto ele está ligado, e o `data-modo`
     leva o que o PRÓXIMO clique pede. Tudo parte do `aria-pressed`, que o piloto também pinta;
     o clique só vira o `aria-pressed` na hora (depois de o piloto ter lido o `data-modo`). */
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
  /* O menu do botão direito: Copiar (cinza sem seleção), Atualizar, Desligar ou Ligar, Reiniciar, Fechar.
     Cada item é um `data-gesto` comum: no produto a janela o despacha como qualquer botão. O serviço
     parado ou pausado vira «Ligar», de um clique só; o estado vem do `data-servico` do cabeçalho. */
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
      <button type="button" role="menuitem" data-gesto="menu-reiniciar">Reiniciar</button><hr>
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
    /* Desligar pede dois cliques, como o «Parar» da aba Sistema: o primeiro troca a palavra, o segundo age. */
    if (b.dataset.menu === 'desligar') {
      if (b.textContent.trim() !== 'Confirma?') { setTimeout(() => { b.textContent = 'Confirma?'; }, 0); return; }
    }
    setTimeout(fechar, 0);
  });
})();
