#!/usr/bin/env python3
"""Régua de alinhamento — mede as caixas REAIS no Chrome contra a JOGAR aprovada.

A primeira versão desta régua comparava cada aba CONSIGO MESMA, e por isso era
cega numa aba de um quadro só: não havia com o que comparar. Medido em 26/08 com
uma mordida que ela deixou passar inteira. Agora o padrão vem de fora — da Jogar,
que é a única aba que ela aprovou — e cada número tem de bater com o dela.
"""
import subprocess, sys, json, re, pathlib

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
D = pathlib.Path(__file__).resolve().parents[1]
REF = "01-jogar.html"
ROT = 92   # o token --rot, em px — a coluna de rótulo de toda aba

# ---------------------------------------------------------------------------
# AS EXCEÇÕES, POR ABA E COM MOTIVO. Palavra dela em 27/08: "Talvez a régua tenha
# que ser ajustada por aba." Uma regra que vale em toda tela vira ruído na tela
# onde ela não faz sentido — e régua que grita onde não deve é régua que se
# aprende a ignorar, que é o começo de portão cego.
#
# Só entra aqui o que ELA dispensou, com a frase dela. Nada de exceção por
# conveniência de quem desenha.
# ---------------------------------------------------------------------------
DISPENSAS = {
    "03-gatilhos.html": [
        ("conteúdo das colunas",
         "27/08, ela: 'Nenhuma. Talvez a régua tenha que ser ajustada por aba.' "
         "L2 e R2 mostram as barras do MODO escolhido, e modos diferentes têm "
         "números de barra diferentes. Igualar a altura seria inventar espaço."),
    ],
    "04-iluminacao.html": [
        ("conteúdo das colunas",
         "27/08, ela: 'Nenhuma.' O desenho do controle ocupa as DUAS linhas do "
         "grid — a régua o compara com a fileira de cima e acusa um vão que é "
         "só a segunda linha. Falso positivo estrutural.\n"
         "         MAS a dispensa cobria também um vão REAL de 34px no pé da "
         "fileira de baixo, e a frase 'ela aprovou vendo' que estava aqui era "
         "FALSA: ela voltou no mesmo dia — 'os elementos estão muito mal "
         "distribuídos'. O vão foi curado na ALTURA (a fileira de números "
         "passou a valer os 70px da caixa de LEDs); sobram 17px, que são a "
         "distância entre o pé de um botão flutuante e a borda de uma caixa."),
    ],
}

SONDA = r"""
<script>
(function(){
  const R = o => Math.round(o*10)/10;
  const j   = document.querySelector('.janela').getBoundingClientRect();
  const mio = document.querySelector('.miolo');
  const cs  = getComputedStyle(mio);
  const _b  = mio.getBoundingClientRect();
  // a CONTENT BOX do miolo — comparar com a border box acusava o próprio padding.
  // `clientWidth` e não `getBoundingClientRect().width`: a border box INCLUI a
  // barra de rolagem (e o gutter que o `scrollbar-gutter:stable` reserva), e a
  // largura tirada dela dava 15px a mais do que o filho pode ocupar. Em 27/08,
  // com o gutter ligado, isso reprovou as DEZ abas de uma vez — o defeito era da
  // regua, não do desenho.
  const mr  = {x:_b.x+parseFloat(cs.paddingLeft), width:mio.clientWidth
               -parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight)};
  const o = {erros:[], m:{}};

  o.m.janela_larg = R(j.width);
  // A ALTURA entra na régua em 27/08: ela media de 530 a 1032 nas dez abas e o  (noqa-acento: "media" aqui é o imperfeito de MEDIR, não "média" de cálculo)
  // rodapé pulava meia tela a cada clique na tira. "Sair clicando entre as abas
  // causa muito desconforto, pq muda tudo."
  o.m.janela_alt  = R(j.height);
  o.m.rodape_y    = R(document.querySelector('.rodape').getBoundingClientRect().y);
  o.m.miolo_pad   = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(' ');
  o.m.miolo_gap   = cs.rowGap;
  o.m.miolo_x     = R(mr.x - j.x);
  o.m.miolo_larg  = R(mr.width);

  // O QUE ROLA POR DENTRO, E QUANTO DELE NINGUÉM VÊ.
  //
  // RÉGUA NOVA em 27/08/2026 (à noite), e ela nasceu de um buraco medido: as dez
  // abas davam `passa_da_dobra = 0` e três escondiam conteúdo. O motivo é que
  // "passa da dobra" mede a JANELA — e a janela tem 757px em todas as dez. A
  // rolagem estava POR DENTRO do miolo e das caixas: na Conexões, DOIS quadros
  // inteiros ("Conexões" e "Desempenho") com ZERO pixel à mostra; na Gatilhos, o
  // recibo e o único botão da aba; na Controles, a aba que É sobre os controles
  // mostrava um e meio dos quatro.
  //
  // Régua nenhuma das dez olhava para isso, e o portão de cores também não —
  // ele mede o mapa, que não tem miolo. Aqui a conta é a do que a pessoa vê:
  // para cada caixa que rola, quanto do conteúdo fica FORA, e quanto de cada
  // quadro sobra à mostra. Quadro com 0px visível é o defeito; ele existe no
  // DOM, passa em toda régua de alinhamento, e não está na tela.
  o.m.rolagem_interna = [];
  document.querySelectorAll('.miolo, .miolo *').forEach(e=>{
    const esconde = e.scrollHeight - e.clientHeight;
    if (esconde <= 2 || e.clientHeight === 0) return;
    const cx = e.getBoundingClientRect();
    const quadros = [...e.querySelectorAll('.quadro')].map(q=>{
      const b = q.getBoundingClientRect();
      const visivel = Math.max(0, Math.min(b.bottom, cx.bottom) - Math.max(b.top, cx.top));
      const tit = q.querySelector('.quadro-titulo, .quadro-tit, .q-tit, h2, h3');
      return {tit: (tit ? tit.textContent : '?').trim().slice(0,32),
              fora: R(b.height - visivel), visivel: R(visivel)};
    }).filter(q => q.fora > 2);
    o.m.rolagem_interna.push({
      onde: e.className ? '.' + String(e.className).split(' ')[0] : e.tagName.toLowerCase(),
      esconde: R(esconde), quadros: quadros});
  });

  // TRANSBORDO
  document.querySelectorAll('.miolo *').forEach(e=>{
    const r = e.getBoundingClientRect();
    if (r.width && (r.right > j.right + .5 || r.left < j.left - .5))
      o.erros.push('transborda ' + R(r.right - j.right) + 'px: ' + (e.className||e.tagName));
  });

  // TODO FILHO DIRETO DO MIOLO ocupa a largura inteira, e comeca no mesmo x
  [...mio.children].forEach(e=>{
    const r = e.getBoundingClientRect();
    if (Math.abs(r.x - mr.x) > .6)
      o.erros.push('filho do miolo fora do x: ' + (e.className||e.tagName) + ' dx=' + R(r.x-mr.x));
    if (Math.abs(r.width - mr.width) > .6)
      o.erros.push('filho do miolo com largura própria: ' + (e.className||e.tagName) + ' dw=' + R(r.width-mr.width));
  });

  // CADA QUADRO: titulo alinhado com o corpo, e o corpo com padding igual
  o.m.quadros = [];
  document.querySelectorAll('.quadro').forEach(q=>{
    const t = q.querySelector('.quadro-titulo'), c = q.querySelector('.quadro-corpo');
    if(!t||!c) return;
    const qr = q.getBoundingClientRect();
    const dt = R(t.getBoundingClientRect().x - qr.x);
    const cc = getComputedStyle(c);
    const dc = R(c.getBoundingClientRect().x - qr.x + parseFloat(cc.paddingLeft));
    o.m.quadros.push({tit:t.textContent.trim().slice(0,26), dx_tit:dt, dx_corpo:dc,
                      pad:[cc.paddingTop,cc.paddingRight,cc.paddingBottom,cc.paddingLeft].join(' ')});
    if (Math.abs(dt-dc) > .6)
      o.erros.push('titulo x='+dt+' != corpo x='+dc+' em "'+t.textContent.trim()+'"');
  });

  // RITMO VERTICAL entre os filhos do miolo
  const gaps=[]; [...mio.children].forEach((e,i,a)=>{ if(i) gaps.push(
    R(e.getBoundingClientRect().top - a[i-1].getBoundingClientRect().bottom)); });
  o.m.gaps = [...new Set(gaps)];

  // ALTURA de cada familia de controle
  const alt={};
  document.querySelectorAll('.miolo button, .miolo select, .miolo input[type=text]').forEach(e=>{
    const k = e.tagName.toLowerCase()+'.'+((e.className||'').split(' ').filter(c=>c!=='on')[0]||'-');
    (alt[k]=alt[k]||new Set()).add(R(e.getBoundingClientRect().height));
  });
  o.m.alturas={};
  Object.entries(alt).forEach(([k,v])=>{ o.m.alturas[k]=[...v].sort((a,b)=>a-b);
    if(v.size>1) o.erros.push('altura divergente em '+k+': '+[...v].join(' / ')); });

  // LARGURA — a Jogar e o padrão: fileira de escolha DIVIDE IGUAL, e toda
  // coluna de rotulo tem a mesma largura na janela inteira.
  o.m.larguras = {};
  document.querySelectorAll('.seg, .escada, .acoes, .lados, .rota, .modos, .players').forEach(f=>{
    const fs = [...f.children].filter(e=>e.tagName==='BUTTON'||e.classList.contains('degrau'));
    if (fs.length < 2) return;
    const ws = fs.map(e=>R(e.getBoundingClientRect().width));
    const cls = f.className.split(' ')[0];
    (o.m.larguras[cls] = o.m.larguras[cls] || []).push(ws);
    // .acoes e .modos não dividem igual por desenho; as outras sim
    if (['seg','escada','lados','rota'].includes(cls) && new Set(ws).size > 1)
      o.erros.push('fileira ".'+cls+'" não divide igual: '+[...new Set(ws)].join(' / '));
  });
  const rots = [...document.querySelectorAll('.campo .nome, .barra .nome, .viva .nome')]
               .map(e=>R(e.getBoundingClientRect().width));
  o.m.rotulos = [...new Set(rots)];
  if (o.m.rotulos.length > 1)
    o.erros.push('colunas de rotulo com larguras diferentes: '+o.m.rotulos.join(' / '));

  // toda COLUNA de um grid do miolo soma a largura do corpo
  document.querySelectorAll('.card-corpo, .duas-colunas, .luz-linha, .motores, .gestos, .dupla').forEach(g=>{
    const gr = g.getBoundingClientRect();
    const cs = getComputedStyle(g);
    const soma = [...g.children].reduce((a,e)=>a+e.getBoundingClientRect().width,0)
                 + parseFloat(cs.columnGap||0)*(g.children.length-1)
                 + parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight);
    if (Math.abs(soma - gr.width) > 1.5)
      o.erros.push('grid ".'+g.className.split(' ')[0]+'": colunas somam '+R(soma)+' e a caixa tem '+R(gr.width));
  });

  // NADA VAZA DA SUA MOLDURA. Medido em 27/08: o círculo do analógico direito
  // passava 24px para fora da caixa escura que o contém — a caixa recorta nada,
  // então o desenho simplesmente saía por cima do vizinho.
  document.querySelectorAll('.moldura, .cx, .quadro-corpo > .card').forEach(m=>{
    const b = m.getBoundingClientRect();
    m.querySelectorAll('*').forEach(e=>{
      const r = e.getBoundingClientRect();
      if (!r.width || getComputedStyle(e).position === 'absolute') return;
      if (r.right > b.right + .5 || r.left < b.left - .5)
        o.erros.push('vaza da moldura: ' + (e.className||e.tagName).toString().slice(0,20)
          + ' passa ' + R(Math.max(r.right-b.right, b.left-r.left)) + 'px');
    });
  });

  // ---- O REFINAMENTO QUE ELA APROVOU NA VIBRACAO (27/08) ----
  // 1) todo titulo de secao de um mesmo quadro comeca no MESMO x
  document.querySelectorAll('.quadro-corpo').forEach(c=>{
    const ts=[...c.querySelectorAll('.sec-rot, .col-rot')];
    if(ts.length<2) return;
    const porCol={};
    // ONDE O TEXTO COMECA, não onde a caixa comeca: `padding-left` empurra o
    // conteúdo sem mover a caixa, e foi assim que uma mordida de 11px passou
    // inteira por esta regua. Ela ve o TEXTO; a regua tem de ver o mesmo.
    ts.forEach(e=>{ const x=R(e.getBoundingClientRect().x
                              + parseFloat(getComputedStyle(e).paddingLeft));
      // agrupa por coluna: titulos a menos de 40px um do outro sao da mesma coluna
      const k=Object.keys(porCol).find(k=>Math.abs(k-x)<40) ?? x;
      (porCol[k]=porCol[k]||[]).push({t:e.textContent.trim().split('\n')[0].slice(0,22), x}); });
    Object.values(porCol).forEach(g=>{
      const xs=[...new Set(g.map(o=>o.x))];
      if(xs.length>1) o.erros.push('titulos de secao em x diferentes: '
        + g.map(o=>o.t+'@'+o.x).join(' / ')); });
  });
  // 2) colunas irmas terminam no MESMO y — e o que conta e onde o CONTEUDO acaba,
  //    não a caixa: com `align-items:stretch` as caixas tem sempre a mesma altura,
  //    e uma mordida de 60px de vao passou inteira por esta regua por causa disso.
  const fimDoConteudo = el => {
    let f = -Infinity;
    (function anda(n){
      [...n.children].forEach(c=>{
        const r = c.getBoundingClientRect();
        if (r.height < 1) return;
        // conta o elemento quando ele TEM texto próprio, quando não tem filhos, ou
        // quando desenha borda. A versão anterior descia em qualquer um com filhos —
        // e um `<br>` dentro do X/Y bastava para ele sumir da conta, gerando 18px de
        // vão que não existiam na tela. Régua com falso positivo faz consertar o que
        // não está quebrado, que é pior do que régua muda.
        const temTextoProprio = [...c.childNodes].some(
          n => n.nodeType === 3 && n.textContent.trim().length);
        // um <svg> é folha: descer nos seus <path> devolve a caixa de tinta, não a
        // do elemento, e produzia 9px de vão que o olho não vê.
        if (!c.children.length || temTextoProprio || c.tagName === 'BUTTON'
            || c.tagName === 'svg' || c.tagName === 'SVG'
            || getComputedStyle(c).borderBottomWidth !== '0px') f = Math.max(f, r.bottom);
        else anda(c);
      });
    })(el);
    return f === -Infinity ? R(el.getBoundingClientRect().bottom) : R(f);
  };
  document.querySelectorAll('.dupla.igual, .vib, .luz-grade, .duas-colunas, .card-corpo').forEach(g=>{
    const cols=[...g.children].filter(e=>e.getBoundingClientRect().height>1);
    if(cols.length<2) return;
    // SO COMPARA QUEM ESTA NA MESMA FILEIRA. Num grid de duas linhas (a Iluminacao),
    // comparar todos os filhos acusava um vao de 148px que não existe: eram
    // simplesmente a linha de cima e a de baixo.
    const fileiras={};
    cols.forEach(e=>{ const y=R(e.getBoundingClientRect().top);
      const k=Object.keys(fileiras).find(k=>Math.abs(k-y)<6) ?? y;
      (fileiras[k]=fileiras[k]||[]).push(e); });
    Object.values(fileiras).forEach(fil=>{
      if(fil.length<2) return;
      const fs=fil.map(fimDoConteudo);
      const d=Math.max(...fs)-Math.min(...fs);
      if(d>8) o.erros.push('o conteúdo das colunas de ".'+g.className.split(' ')[0]
        +'" acaba em y diferentes: '+fs.join(' / ')+' (vao de '+R(d)+'px)');
    });
  });

  // COLUNAS IRMAS de um grid comecam na mesma linha
  document.querySelectorAll('.dupla, .duas-colunas, .luz-linha, .miolo [style*="grid-template-columns"]').forEach(g=>{
    const f=[...g.children].map(e=>R(e.getBoundingClientRect().top));
    if(new Set(f).size>1) o.erros.push('colunas irmas em y diferentes: '+[...new Set(f)].join(', '));
  });

  document.title='REGUA'+JSON.stringify(o);
})();
</script>
"""

def medir(arq):
    tmp = D / ("_regua_" + arq)
    tmp.write_text((D / arq).read_text().replace("</body>", SONDA + "\n</body>"))
    try:
        p = subprocess.run(["google-chrome","--headless","--disable-gpu","--no-sandbox",
                            "--virtual-time-budget=3000","--window-size=1260,2600","--dump-dom",
                            f"file://{tmp}"], capture_output=True, text=True, timeout=90)
        m = re.search(r"<title>REGUA(.*?)</title>", p.stdout, re.S)
        if not m: return {"erros":["a sonda não rodou"],"m":{}}
        s = m.group(1)
        for a,b in [("&quot;",'"'),("&amp;","&"),("&lt;","<"),("&gt;",">"),("&#39;","'")]:
            s = s.replace(a,b)
        return json.loads(s)
    finally:
        tmp.unlink(missing_ok=True)

if __name__ == "__main__":
    ref = medir(REF)["m"]
    print(f"PADRÃO (da {REF}): janela {ref['janela_larg']}×{ref['janela_alt']}px "
          f"· rodapé em y={ref['rodape_y']} · miolo pad {ref['miolo_pad']} "
          f"gap {ref['miolo_gap']} larg {ref['miolo_larg']}")
    print(f"  quadro: título e corpo em dx={ref['quadros'][0]['dx_tit']} · pad {ref['quadros'][0]['pad']}")
    print(f"  alturas: " + " · ".join(f"{k}={v[0]}" for k,v in ref["alturas"].items()))
    print(f"  rótulo: {ref.get('rotulos')} · fileiras: "
          + " · ".join(f"{k}={v[0]}" for k,v in list(ref.get("larguras",{}).items())[:4]))
    falhou = 0
    for arq in sys.argv[1:]:
        r = medir(arq); m = r["m"]; e = list(r["erros"])
        # O AVISO DE ROLAGEM ESPERA O CABEÇALHO. Ele era impresso durante a
        # medição, ANTES do `=== {arq} ===`, e por isso aparecia debaixo do nome
        # da aba ANTERIOR: em 28/08 a linha da Conexões saiu sob a Lançadores, e
        # quem lesse iria consertar a aba errada.
        avisos = []
        # ---- confronto com o PADRÃO, que é o que a versão cega não fazia ----
        for chave, rot in [("janela_larg","largura da janela"),("janela_alt","altura da janela"),
                           ("rodape_y","y do rodapé"),("miolo_pad","padding do miolo"),
                           ("miolo_gap","gap do miolo"),("miolo_larg","largura do miolo")]:
            if m.get(chave) != ref.get(chave):
                e.append(f"{rot}: {m.get(chave)} != {ref.get(chave)} da referência")
        for q in m.get("quadros", []):
            if q["dx_tit"] != ref["quadros"][0]["dx_tit"]:
                e.append(f'quadro "{q["tit"]}": título em dx={q["dx_tit"]}, a referência usa {ref["quadros"][0]["dx_tit"]}')
            if q["pad"] != ref["quadros"][0]["pad"]:
                e.append(f'quadro "{q["tit"]}": padding {q["pad"]} != {ref["quadros"][0]["pad"]}')
        # o rótulo tem valor CANÔNICO (o token --rot), não herdado da Jogar: a Jogar não
        # tem campo com rótulo, e comparar com a lista vazia dela deixava a mordida passar.
        for w in m.get("rotulos", []):
            if w != ROT:
                e.append(f"coluna de rótulo: {w}px, o token --rot é {ROT}px")
        for k, v in m.get("alturas", {}).items():
            if k in ref["alturas"] and v[0] != ref["alturas"][k][0]:
                e.append(f"altura de {k}: {v[0]} != {ref['alturas'][k][0]} da referência")
        # O QUE ROLA POR DENTRO. Um quadro com ZERO pixel à mostra não é uma
        # escolha de layout: é conteúdo que a pessoa não sabe que existe. Quadro
        # PARCIALMENTE fora é aviso — ela rola e acha; quadro INTEIRO fora é erro,
        # porque nada na tela diz que há mais.
        for caixa in m.get("rolagem_interna", []):
            # QUANTO PRECISA ESTAR À MOSTRA PARA VALER COMO "aparece".
            #
            # A RÉGUA NOMEAVA E DEIXAVA PASSAR, medido em 28/08: ela imprimia
            # `rola por dentro em .miolo: "Rádio e adaptadores" (323px fora)` e
            # devolvia **rc=0**, porque só reprovava quadro com ZERO pixel. Um
            # quadro de 343px mostrando 29 é a barra do título e mais nada — e
            # passava. O piso é 25% do quadro, OU 64px (a altura de um título com
            # a primeira linha do corpo), o que for menor: abaixo disso a pessoa
            # não tem como saber que há conteúdo ali.
            # O piso é 64px — a altura de um título de quadro com a PRIMEIRA
            # LINHA do corpo. Abaixo disso a pessoa vê uma barra de título e não
            # tem como saber que há conteúdo. Quadro menor que 64px tem de
            # aparecer inteiro.
            def _piso(q):
                return min(64, q["visivel"] + q["fora"])
            invisiveis = [q for q in caixa["quadros"] if q["visivel"] < _piso(q)]
            for q in invisiveis:
                quanto = ("ZERO pixel" if q["visivel"] < 1
                          else f'só {q["visivel"]}px de {q["visivel"] + q["fora"]}')
                e.append(f'quadro "{q["tit"]}" tem {quanto} à mostra em '
                         f'{caixa["onde"]} (rola {caixa["esconde"]}px por dentro)')
            parciais = [q for q in caixa["quadros"] if q["visivel"] >= 1]
            if parciais:
                lista = ", ".join(f'"{q["tit"]}" ({q["fora"]}px fora)' for q in parciais[:3])
                avisos.append(f"   – rola por dentro em {caixa['onde']}: {lista}")

        # as dispensas dela saem da conta, e ficam VISÍVEIS: exceção escondida é
        # exceção que ninguém revisita.
        dispensados = []
        for chave, motivo in DISPENSAS.get(arq, []):
            fica = [x for x in e if chave not in x]
            dispensados += [(x, motivo) for x in e if chave in x]
            e = fica
        print(f"\n=== {arq} === {len(e)} desalinhamento(s)")
        for x in avisos:
            print(x)
        for x, motivo in dispensados:
            print(f"   – dispensado por ela: {x}")
        for x in e[:16]: print("   ✗", x)
        if not e: print("   ✓ bate com a referência")
        falhou += bool(e)
    sys.exit(1 if falhou else 0)
