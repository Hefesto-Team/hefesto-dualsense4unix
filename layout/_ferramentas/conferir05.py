#!/usr/bin/env python3
"""05 · Vibração — a conferência da aba, medida no Chrome.

A versão anterior conferia UM controle: quatro botões abaixo do desenho, três
trilhos no mesmo x, a Força parando em 150%. Aquilo estava bem conferido, e
deixou de fazer sentido quando a mesa virou quatro — `.acoes-col .btn` passou a
casar oito botões, e "os 3 trilhos no mesmo x" virou doze trilhos em quatro
colunas, que NÃO devem começar no mesmo x.

O que ela conferia continua conferido, agora por coluna. E entram as perguntas que a
mesa de quatro criou, todas contra o MAPA — nunca contra um número digitado
aqui:

* a cor de cada moldura é a que `cor_da_zona()` lê do desenho (o hex digitado é
  exatamente o defeito que o `check_cores_do_dualsense.py` existe para matar);
* os ids dos motores são os do `docs/data/pecas-do-dualsense.csv`;
* o lado ACESO do desenho é o lado LIGADO no interruptor;
* as cinco lâmpadas acendem no padrão do produto (`core/led_control.py`).

Uso: python3 conferir05.py
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402
from monta import MESA, PADRAO_JOGADOR, cor_da_zona  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aba05 import DIR, ESQ, ESTADO, TETO  # noqa: E402

# MEDE A BANCADA (`mockup/`) — 31/08/2026. Este caminho era `parent.parent`,
# que resolvia para `layout/`; apontá-lo lá hoje mediria a página congelada.
D = onde.BANCADA


def rgb(h):
    h = h.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


SONDA = """() => {
  const R = n => Math.round(n*10)/10;
  const cx = e => { const b = e.getBoundingClientRect();
    return {t:(e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,30),
            x:R(b.x), y:R(b.y), w:R(b.width), h:R(b.height), r:R(b.right), b:R(b.bottom)}; };
  const fim = el => {           // onde o CONTEÚDO da coluna acaba
    let f = -Infinity;
    (function anda(n){ [...n.children].forEach(c=>{
      const r = c.getBoundingClientRect(); if (r.height < 1) return;
      const texto = [...c.childNodes].some(x=>x.nodeType===3 && x.textContent.trim().length);
      if (!c.children.length || texto || c.tagName==='BUTTON' || c.tagName==='svg') f = Math.max(f, r.bottom);
      else anda(c); }); })(el);
    return R(f); };
  const out = {colunas:[], rotulos:[], chips:[], titulos:[], miolo:{}};
  out.chips = [...document.querySelectorAll('.fita .chip.plastico')].map(e=>e.textContent.trim().replace(/\\s+/g,' '));
  out.titulos = [...document.querySelectorAll('.vib .rotulos .sec-rot')].map(e=>({
      t:e.textContent.trim().split('\\n')[0].slice(0,22),
      x:R(e.getBoundingClientRect().x + parseFloat(getComputedStyle(e).paddingLeft))}));
  out.rotulos = {fim: fim(document.querySelector('.vib .rotulos')),
                 x: R(document.querySelector('.vib .rotulos').getBoundingClientRect().x)};
  document.querySelectorAll('.vib .ctrl').forEach(col=>{
    const svg = col.querySelector('.ds-svg');
    const acesa = a => !!svg.querySelector('[id$="-feat-rumble-'+a+'"].acesa');
    const lados = [...col.querySelectorAll('.lado')];
    out.colunas.push({
      rot: col.querySelector('.rot-ctrl').textContent.trim().replace(/\\s+/g,' '),
      escolhido: col.classList.contains('escolhido'),
      borda: getComputedStyle(col.querySelector('.moldura')).borderTopColor,
      colorway: svg.getAttribute('data-colorway'),
      ids: [...svg.querySelectorAll('[id*="-feat-rumble-"]')].map(e=>e.id.replace(/^vb-p\\d-/,'')),
      acesa_esq: acesa('esquerdo'), acesa_dir: acesa('direito'),
      lado_on: lados.map(e=>e.classList.contains('on')),
      lado_glifo: lados.map(e=>e.querySelectorAll('svg').length),
      // AS LÂMPADAS SAÍRAM (28/08). Duas medidas, e as duas mordem: a âncora do
      // GRUPO tem de existir (é o que a regra do CSS esconde — se ela some, a
      // regra deixa de casar e as lâmpadas voltam sem aviso), e nenhuma das
      // cinco pode ter caixa na tela. `display:none` dá width/height ZERO, que é
      // o que se mede — a classe no HTML não prova nada sobre o que se vê.
      leds_grupo: svg.querySelectorAll('[id$="-led-jogador"]').length,
      leds_visiveis: [...svg.querySelectorAll('[id*="-led-jogador-"]')]
              .filter(e=>{const b=e.getBoundingClientRect(); return b.width>0 || b.height>0;})
              .map(e=>e.id.slice(-1)).sort().join(''),
      forca_on: [...col.querySelectorAll('.seg button.on')].map(e=>e.textContent.trim()),
      seg_w: [...new Set([...col.querySelectorAll('.seg button')].map(e=>R(e.getBoundingClientRect().width)))],
      barras: [...col.querySelectorAll('.motor')].map(m=>({
        x:R(m.querySelector('.trilho').getBoundingClientRect().x),
        r:R(m.querySelector('.trilho').getBoundingClientRect().right),
        num_r:R(m.querySelector('.num').getBoundingClientRect().right),
        teto_x:R(m.querySelector('.teto').getBoundingClientRect().x),
        cheio:m.querySelector('.cheio').style.width,
        num:m.querySelector('.num').textContent.trim(),
        teto:m.querySelector('.teto').textContent.trim()})),
      ordens: [...col.querySelectorAll('.acoes-col .btn')].map(cx),
      fim: fim(col), x: R(col.getBoundingClientRect().x), w: R(col.getBoundingClientRect().width),
    });
  });
  const f = document.querySelector('.fita');
  out.fita = {inerte: f.classList.contains('inerte'),
              opacidade: getComputedStyle(f).opacity,
              on: [...f.querySelectorAll('.chip.on')].map(e=>e.textContent.trim())};
  const m = document.querySelector('.miolo'), d = document.documentElement;
  out.miolo = {rola: m.scrollHeight > m.clientHeight + 1,
               lateral: d.scrollWidth > d.clientWidth,
               alvo_proprio: document.querySelectorAll('.miolo .chip').length};
  return out;
}"""

msgs = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: msgs.append(f"pageerror: {e}"))
    pg.goto(f"file://{D}/05-vibracao.html")
    pg.wait_for_load_state("networkidle")
    pg.add_style_tag(content=".nota{display:none}")
    pg.wait_for_timeout(400)
    r = pg.evaluate(SONDA)
    b.close()

falhas = 0


def p(ok, s):
    global falhas
    falhas += not ok
    print(("  OK   " if ok else "  FALHA") + " " + s)


print("=== 05 · VIBRAÇÃO — os quatro controles, contra o mapa ===")
c = r["colunas"]
p(len(c) == len(MESA), f'uma coluna por controle da MESA — {len(c)} de {len(MESA)}')
p([x["colorway"] for x in c] == [m["cor"] for m in MESA],
  f'na ORDEM da mesa (e da fita) — {[x["colorway"] for x in c]}')
p(all(f'P{m["jogador"]}' in x["rot"] and m["nome"] in x["rot"] and m["via"] in x["rot"]
      for x, m in zip(c, MESA)),
  f'o rótulo é marca • player • plástico • transporte — {[x["rot"] for x in c]}')
p([x["rot"].replace("• ", "").replace(" •", "") for x in c]
  == [y.replace("• ", "").replace(" •", "") for y in r["chips"]],
  "o rótulo da coluna diz o mesmo que o chip da fita")

print("--- o mapa: nada digitado ---")
p(all(x["borda"] == rgb(cor_da_zona(m["cor"])) for x, m in zip(c, MESA)),
  "a borda de cada desenho é a cor que cor_da_zona() lê do SVG — "
  + " · ".join(f'{m["cor"]}={x["borda"]}' for x, m in zip(c, MESA)))
p(all(sorted(x["ids"]) == sorted([ESQ["id"], DIR["id"]]) for x in c),
  f'os dois motores são os ids do CSV de peças — {c[0]["ids"]}')
p(all(x["lado_glifo"] == [1, 1] for x in c),
  "cada interruptor traz o glifo do mapa (assets/glyphs)")
p(all(x["leds_grupo"] == 1 for x in c),
  "o grupo das lâmpadas continua no desenho — é a âncora que o CSS esconde "
  f'({[x["leds_grupo"] for x in c]})')
p(all(x["leds_visiveis"] == "" for x in c),
  "e NENHUMA lâmpada tem caixa na tela (28/08: 2,79 × 0,93 px não se leem) — "
  + " · ".join(f'P{m["jogador"]}={x["leds_visiveis"] or "—"}' for x, m in zip(c, MESA)))
p(PADRAO_JOGADOR[3] == "135",
  f'o padrão do produto segue vindo de core/led_control.py (P3={PADRAO_JOGADOR[3]}) '
  "— esta aba não o desenha, a Iluminação desenha")

print("--- o desenho conta a verdade do controle ---")
for x, m in zip(c, MESA):
    e = ESTADO[m["pref"]]
    p(x["acesa_esq"] == e["esq"][0] and x["acesa_dir"] == e["dir"][0],
      f'P{m["jogador"]}: acende o lado LIGADO — esq {x["acesa_esq"]}/{e["esq"][0]}, '
      f'dir {x["acesa_dir"]}/{e["dir"][0]}')
p(all(x["lado_on"] == [ESTADO[m["pref"]]["esq"][0], ESTADO[m["pref"]]["dir"][0]]
      for x, m in zip(c, MESA)),
  "o interruptor de cada lado diz o mesmo que o desenho")
p(all(len(x["forca_on"]) == 1 for x in c),
  f'a Força é UMA escolha por controle — {[x["forca_on"] for x in c]}')
p(float(c[0]["barras"][0]["cheio"].rstrip("%")) == 100 and c[0]["barras"][0]["num"] == f"{TETO}%"
  and c[0]["barras"][0]["teto"] == "máx",
  f'a barra do P1 para em {TETO}% — {c[0]["barras"][0]}')
p(all(b["num"] == "0" and float(b["cheio"].rstrip("%")) == 0
      for x in c for b, lig in zip(x["barras"][1:], x["lado_on"]) if not lig),
  "lado desligado mostra 0, e o trilho vazio")

print("--- alinhamento (o que ela chamou de fundamental) ---")
for x, m in zip(c, MESA):
    b = x["barras"]
    p(len({y["x"] for y in b}) == 1 and len({y["r"] for y in b}) == 1,
      f'P{m["jogador"]}: os 3 trilhos começam e acabam no mesmo x — '
      f'{sorted({y["x"] for y in b})} → {sorted({y["r"] for y in b})}')
    p(len({y["num_r"] for y in b}) == 1 and len({y["teto_x"] for y in b}) == 1,
      f'P{m["jogador"]}: números à direita e sufixos alinhados')
p(all(len(x["seg_w"]) == 1 for x in c) and len({x["seg_w"][0] for x in c}) == 1,
  f'os 16 degraus de Força têm a mesma largura — {c[0]["seg_w"]}')
larg = {a["w"] for x in c for a in x["ordens"]}
p(len(larg) == 1 and all(len(x["ordens"]) == 2 for x in c),
  f'os 8 botões de ação têm a mesma largura — {larg}')
p(len({x["w"] for x in c}) == 1, f'as quatro colunas têm a mesma largura — {{x["w"] for x in c}}'
  .replace('{x["w"] for x in c}', str({x["w"] for x in c})))
fins = [r["rotulos"]["fim"]] + [x["fim"] for x in c]
p(max(fins) - min(fins) <= 8, f'as cinco colunas acabam no mesmo y — {fins}')
xs = sorted({t["x"] for t in r["titulos"]})
p(len(xs) == 1, f'os títulos da coluna de rótulos começam no mesmo x — {xs}')

print("--- a fita não manda nesta aba, e a tela cabe ---")
p(r["fita"]["inerte"] and float(r["fita"]["opacidade"]) < 1,
  f'a fita do topo nasce esmaecida (28/08) — inerte={r["fita"]["inerte"]}, '
  f'opacidade={r["fita"]["opacidade"]}')
p(r["fita"]["on"] == ["Todos"],
  f'e presa em "Todos", sem apontar controle nenhum — {r["fita"]["on"]}')
p(all(not x["escolhido"] for x in c),
  "nenhuma coluna vem destacada: com a fita inerte, o destaque afirmaria na "
  f'tela o que a fita já não faz — {[x["escolhido"] for x in c]}')
p(r["miolo"]["alvo_proprio"] == 0,
  f'a aba não tem seletor de alvo próprio — {r["miolo"]["alvo_proprio"]} chip(s) no miolo')
p(not r["miolo"]["rola"], "a aba cabe na janela sem rolar por dentro")
p(not r["miolo"]["lateral"], "e não rola de lado")
p(not msgs, f"console limpo — {msgs or 'nada'}")

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
