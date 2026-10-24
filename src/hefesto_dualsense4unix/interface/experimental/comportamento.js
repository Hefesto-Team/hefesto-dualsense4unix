(function(){
  var alvo = document.body.dataset.abre;
  if (alvo && location.href.indexOf('#') < 0) location.replace('#' + alvo);
  function fmt(v, casas){ return casas ? v.toFixed(casas).replace('.', ',') : String(Math.round(v)); }
  document.addEventListener('click', function(e){
    var b = e.target.closest('.seg button');
    if (b){ b.parentElement.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on', x === b); });
            b.dispatchEvent(new CustomEvent('escolha', {bubbles:true})); }
    var t = e.target.closest('.nj-tog[data-on]');
    if (t){ t.classList.toggle('ligado'); t.querySelector('.txt').textContent = t.classList.contains('ligado') ? t.dataset.on : t.dataset.off; }
    var p = e.target.closest('.bignum .passo');
    if (p){ var bn = p.closest('.bignum'), el = bn.querySelector('b'); var txt = el.textContent.trim();
            var casas = (txt.split(',')[1] || '').length; var v = parseFloat(txt.replace(',', '.'));
            var d = parseFloat(bn.dataset.passo || '1') * (p.textContent.trim() === '+' ? 1 : -1);
            v = Math.min(parseFloat(bn.dataset.max || '100'), Math.max(parseFloat(bn.dataset.min || '0'), v + d));
            el.textContent = fmt(v, casas); }
    var o = e.target.closest('.ja-op');
    if (o){ o.parentElement.querySelectorAll('.ja-op').forEach(function(x){ x.classList.toggle('on', x === o); }); }
    var c = e.target.closest('.ja-chips .chip, .ac-chips .chip');
    if (c){ c.classList.toggle('on'); }
  });
  // O ⋮ ABERTO FICA À VISTA DENTRO DA LISTA QUE ROLA — 21/10/2026. O produto troca a lista inteira a
  // cada clique, e a lista rola só o que falta para o cartão do menu aparecer.
  // 24/10/2026 (O-CARTAO-DA-EXTENSAO-NAO-ABRE-PAINEL-01): o menu com as permissões flutua fora da lista
  // (`position:fixed`, sem esticar o cartão nem o vizinho); aqui ele ganha o lugar junto do ⋮: a borda
  // direita na do ⋮, logo abaixo do cartão ou, sem espaço na janela, logo acima.
  function oMenuAVista(lista){
    var m = lista.querySelector('.ext-pop.aberto');
    if (!m) return;
    var c = m.closest('.ext') || m.parentElement;
    var a = c.getBoundingClientRect(), b = lista.getBoundingClientRect();
    if (a.bottom > b.bottom) lista.scrollTop += Math.ceil(a.bottom - b.bottom);
    else if (a.top < b.top) lista.scrollTop -= Math.ceil(b.top - a.top);
    oMenuNoLugar(m);
  }
  function oMenuNoLugar(m){
    if (getComputedStyle(m).position !== 'fixed') return;
    var c = (m.closest('.ext') || m.parentElement).getBoundingClientRect();
    var mais = m.parentElement.querySelector('.ext-mais');
    var direita = mais ? mais.getBoundingClientRect().right : c.right;
    var w = m.offsetWidth, h = m.offsetHeight;
    var x = Math.max(8, Math.min(direita - w, innerWidth - w - 8));
    var y = c.bottom + 4;
    if (y + h > innerHeight - 8) y = Math.max(8, c.top - 4 - h);
    m.style.left = Math.round(x) + 'px';
    m.style.top = Math.round(y) + 'px';
  }
  document.querySelectorAll('.ext-lista').forEach(function(lista){
    new MutationObserver(function(){ oMenuAVista(lista); }).observe(lista,
      {childList:true, subtree:true, attributes:true, attributeFilter:['class']});
  });
  function osMenusNoLugar(){
    document.querySelectorAll('.ext-lista .ext-pop.aberto').forEach(oMenuNoLugar);
  }
  document.addEventListener('scroll', osMenusNoLugar, true);
  addEventListener('resize', osMenusNoLugar);
})();
