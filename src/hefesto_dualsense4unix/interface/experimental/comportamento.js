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
    var m = e.target.closest('.ja-marcar');
    if (m){ var l = m.closest('.ja-roda-l'); l.classList.toggle('fora'); m.textContent = l.classList.contains('fora') ? '' : '✓'; }
    var tom = e.target.closest('.ja-tons .tom');
    if (tom){ tom.parentElement.querySelectorAll('.tom').forEach(function(x){ x.classList.toggle('on', x === tom); });
              if (tom.parentElement.dataset.luz && tom.dataset.cor) document.documentElement.style.setProperty('--cor-luz', tom.dataset.cor); }
    var g = e.target.closest('.ja-degraus i');
    if (g){ var n = Array.prototype.indexOf.call(g.parentElement.children, g) + 1; nivel(n); }
    var np = e.target.closest('.ja-passos .passo');
    if (np){ var atual = document.querySelectorAll('.ja-degraus i.on').length; nivel(atual + (np.textContent.trim() === '+' ? 1 : -1)); }
    if (e.target.closest('.ja-parar')) nivel(0);
  });
  function nivel(n){
    n = Math.max(0, Math.min(10, n));
    document.querySelectorAll('.ja-degraus i').forEach(function(x, i){ x.classList.toggle('on', i < n); });
    var b = document.querySelector('.ja-nivel b'); if (b) b.textContent = n;
    var lz = document.querySelector('.ja-barra-luz');
    if (lz) lz.style.setProperty('--periodo', n ? (4 - (n - 1) / 3) + 's' : '0s');
  }
})();
(function(){
  var c = document.querySelector('[data-lv-conta]'); if (!c) return;
  var chave = document.querySelector('.ext[data-modificacao=lovense] > .nj-tog');
  function por(t, on){ t.classList.toggle('ligado', on); t.querySelector('.txt').textContent = on ? 'Ligada' : 'Desligada'; }
  function contar(){ var t = document.querySelectorAll('#lovense .lv-linha .nj-tog');
    var n = document.querySelectorAll('#lovense .lv-linha .nj-tog.ligado').length;
    c.textContent = n + ' de ' + t.length + (n === 1 ? ' ligada' : ' ligadas'); return n; }
  document.addEventListener('click', function(e){
    var f = e.target.closest('#lovense .lv-linha .nj-tog');
    if (f){ por(f, !f.classList.contains('ligado')); por(chave, contar() > 0); return; }
    if (chave && e.target.closest('.ext[data-modificacao=lovense] > .nj-tog')){
      var ligar = !chave.classList.contains('ligado');
      if (ligar && contar() === 0){ location.hash = '#lovense'; return; }
      por(chave, ligar);
    }
    setTimeout(contar, 0);
  });
  contar();
})();
document.addEventListener('DOMContentLoaded', () => {
  const q = new URLSearchParams(location.search);
  if (q.get('aba')) { const r = document.getElementById(q.get('aba')); if (r) r.click(); }
  if (q.get('marcados')) document.querySelectorAll('.jg-l input').forEach((c, i) => { c.checked = i === 0 || i === 2; });
});
