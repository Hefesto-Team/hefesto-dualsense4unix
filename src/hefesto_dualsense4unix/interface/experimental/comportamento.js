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
})();
