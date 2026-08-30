import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from itertools import cycle
from monta import (monta, svg, glifo, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, luzinhas, player_slot_color)

# ---------------------------------------------------------------------------
# AS TRÊS MUDANÇAS DE 28/08/2026, e a que arrastou o resto.
#
# 1. `fita_viva=False`. Decisão dela: em Gatilhos, Iluminação e Vibração os
#    quatro ficam lado a lado, sempre visíveis, e a fita do topo fica ESMAECIDA.
#
#    ELA ARRASTOU A ABA INTEIRA, e é por isso que aqui há mais que um parâmetro
#    trocado. Esta aba tinha UM controle escolhido — o `.ctrl.on` de borda roxa —
#    e as quatro seções de baixo ajustavam ELE. Quem dizia qual era? A fita. Com
#    a fita inerte e presa em "Todos", o destaque passaria a afirmar na tela uma
#    coisa que a fita já não faz, e a tela se contradiria sozinha. É o mesmo
#    achado da Vibração, no mesmo dia, e a cura é a mesma: **não há escolhido**.
#    Cada controle se ajusta na coluna dele.
#
# 2. O "Selecione o player" FICA e passa a TROCAR o número. Ele deixa de
#    perguntar "qual estou vendo" — com os quatro na tela, essa pergunta não tem
#    mais objeto — e passa a dizer *"este controle é o player N"*. É o caso real
#    dela, de 26/08: "o meu controle azul é o player 2 e antes de irmos pro jogo
#    ele tem que ser o player 1". Trocar é TROCA, não fila: pôr o azul no 1 faz
#    quem era 1 virar 2. Ninguém repete número, ninguém fica sem.
#
# 3. As lâmpadas do jogador FICAM aqui, nos desenhos grandes. Elas saem só dos
#    pequenos das outras abas, que medem 1,0 × 0,33 px.
#
# CORREÇÃO DE FATO, medida hoje: "nos desenhos grandes o padrão se lê" NÃO era
# verdade. Medido no Chrome, com o desenho a 224 px de largura, cada lâmpada
# saía com **3,84 × 1,29 px** — um traço de um pixel e um terço de altura. A
# lâmpada tem 2,0 × 1,15 unidades e o grupo carrega um achatamento vertical de
# 0,6254 no `transform`, então a altura em tela é 1,15 × 0,6254 × (larg/116,684).
# Nenhuma largura que cabe em quatro colunas dá altura legível: mesmo ocupando a
# coluna inteira o ganho é de 0,1 px. A cura não é agrandar o desenho — é
# agrandar A LÂMPADA dentro dele, que é o que o CSS abaixo faz.
# ---------------------------------------------------------------------------


def luz(jogador):
    """A cor automática da barra do controle de número `jogador`, dita pelo produto."""
    return "#%02X%02X%02X" % player_slot_color(jogador)


#: Quem tem cada número HOJE. É o que faz cada botão de número dizer com quem a
#: troca acontece — o anelzinho dele é a cor do plástico do dono.
DONO = {c["jogador"]: c for c in MESA}

#: OS NÚMEROS QUE A FILEIRA OFERECE SÃO OS OCUPADOS, e isso é consequência da
#: decisão dela, não escolha de desenho: se trocar é TROCA, só se pode trocar com
#: quem existe. Um número livre não tem com quem trocar — dá-lo seria mover, e
#: mover deixa um número sem dono, que é justamente o que ela proibiu ("nunca
#: fica um número repetido nem um controle sem número").
NUMEROS = sorted(c["jogador"] for c in MESA)

#: O brilho de cada controle. Sai de um `cycle`, e não de um dicionário com
#: quatro chaves: a mesa é a MESA, e uma mesa de três ou de cinco não pode
#: quebrar o gerador nem cair num `KeyError`.
_b = cycle((82, 100, 70, 45))
BRILHO = {c["pref"]: next(_b) for c in MESA}

#: A GUIA DE TONS SÃO AS OITO CORES DO PRODUTO — as mesmas que ele acende
#: sozinho, uma por número (`player_slot_color`, 1..8). Nenhuma é digitada aqui.
TONS = [luz(n) for n in range(1, 9)]

#: O EXEMPLO DA TROCA, derivado da mesa. É o caso dela, de 26/08: quem tem o 1
#: hoje, e o primeiro da mesa que NÃO o tem — na mesa de hoje, o Cosmic Red e o
#: Starlight Blue, que é o "meu controle azul" da frase dela. Se a mesa mudar,
#: os dois mudam junto: nada aqui está escrito com o nome de um controle.
TEM_O_1 = DONO[NUMEROS[0]]
QUER_O_1 = next(c for c in MESA if c is not TEM_O_1)

CSS = """
  /* ---------- Iluminação ---------- */
  /* UMA GRADE SÓ: uma coluna de rótulos e uma coluna por controle da MESA.
     É a mesma gramática da Vibração, que ela aprovou em 27/08 ("viu esses
     detalhes que eu pedi? eu quero esse refinamento em todas as demais").
     As sete linhas são compartilhadas pelas cinco colunas, e é isso que faz o
     rótulo "Brilho" ficar na mesma linha dos quatro trilhos e as cinco colunas
     acabarem no MESMO y — a cura do vão é na ALTURA, nunca `space-between`.

     ANTES ELA ERA OUTRA COISA: uma fileira de quatro desenhos em cima e um
     grid 2x2 de seções embaixo, que ajustavam UM controle — o que a fita
     apontava. Com a fita esmaecida (decisão dela, 28/08) esse alvo deixou de
     existir, e as seções desceram para dentro das colunas.

     AS ALTURAS SÃO TOKENS porque a soma é o orçamento: 146+16+44+26+62+34+72
     = 400, mais seis passos de 8 = 448, e o miolo dá 452. Mexer numa linha sem
     tirar de outra faz a aba rolar por dentro — e quadro que rola por dentro é
     conteúdo que ninguém sabe que existe. */
  .luz-grade{
    display:grid;grid-template-columns:132px repeat(4,1fr);gap:16px;
    --r-des:146px;--r-nome:16px;--r-cor:44px;--r-brilho:26px;
    --r-player:62px;--r-leds:34px;--r-acoes:72px;--r-passo:8px;
  }
  .luz-grade > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-cor) var(--r-brilho)
                       var(--r-player) var(--r-leds) var(--r-acoes);
  }
  /* a barra vertical entre blocos irmãos — pedido dela */
  .luz-grade .ctrl{border-left:1px solid var(--border-sutil);padding:0 8px 0 12px}

  /* a coluna dos rótulos: todo título começa no mesmo x, e cada um ocupa a
     ALTURA INTEIRA da sua linha — é assim que a coluna acaba junto das outras */
  .luz-grade .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
  .luz-grade .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  .luz-grade .rotulos .cel-des{justify-content:flex-start;gap:8px}
  .sec-rot{font-size:11px;color:var(--comment);text-transform:uppercase;
           letter-spacing:.5px;display:flex;align-items:center;gap:6px}
  /* A LEGENDA NÃO É TÍTULO. Sem isto ela herda o `text-transform:uppercase` do
     rótulo e sai um parágrafo inteiro em caixa alta, que é o mais difícil de
     ler que existe. Medido no navegador em 27/08, na Vibração. */
  .luz-grade .rotulos .legenda{font-size:10.5px;line-height:1.45;color:var(--comment);
                               text-transform:none;letter-spacing:0}
  /* e a dica abre PARA CIMA: nas linhas de baixo, aberta para baixo, a janela
     (que tem `overflow:hidden`) cortava o fim do texto. */
  .luz-grade .rotulos .dica{text-transform:none;letter-spacing:0;top:auto;bottom:-4px}

  /* O DESENHO: a borda tem a cor do plástico, sempre — é como ela sabe de quem
     é a luz que está vendo (D-A-BORDA-E-A-IDENTIDADE-DA-PECA). O desenho ocupa
     a coluna inteira: nesta aba ele é o instrumento, não a ilustração. */
  .luz-grade .moldura{border:1px solid var(--plastico);border-radius:8px;
                      background:var(--app-bg);overflow:hidden}
  .ctrl-rot{font-size:11px;color:var(--texto-mudo);text-align:center;white-space:nowrap;
            display:flex;align-items:center;justify-content:center}

  /* A LUZ É LUZ, E NÃO PLÁSTICO. Os tokens são os do mapa do controle
     (`mapa.py`), que é onde eles nasceram: a barra e as cinco lâmpadas ficam de
     fora da folha de cores de propósito — na cor do casco elas sumiriam sobre a
     borda do touchpad.

     E A `.troca` DA LEGENDA ENTRA AQUI JUNTO, medido: os tokens moravam só no
     `.luzes` (o quadro), e o antes/depois desenhado na nota fica FORA dele — as
     cinco lâmpadas de cada item saíam todas transparentes, e o que se via era o
     halo do `box-shadow` das acesas. Cinco pontos viraram um, dois, três e
     quatro anéis, e o padrão — que é o que aquele desenho existe para mostrar —
     não estava lá. */
  /* as duas cores das lâmpadas moram no `CSS_LUZINHAS`, com elas */
  .luzes,.troca{--luz-apagada:#3f4350}
  .luz-grade [id$="-lightbar"] .peca{fill:var(--luz,var(--luz-apagada))}
  .luz-grade [id$="-lightbar"]{filter:drop-shadow(0 0 1.1px var(--luz))}

  /* AS CINCO LÂMPADAS TÊM DE SE LER, e medido elas não se liam: 3,84 × 1,29 px
     no desenho de 224 px desta aba. A decisão dela de 28/08 é que o padrão se
     lê AQUI — então a lâmpada cresce dentro do desenho, que é a única alavanca
     que resta (agrandar o desenho até a coluna inteira ganha 0,1 px de altura).

     `scale(1.15, 2.9)` e não um número redondo, e os dois vêm da geometria do
     arquivo: as lâmpadas estão em x = 56,3 / 60,6 / 63,0 / 65,4 / 69,7 com 2,0
     de largura, então entre a 2ª e a 3ª sobram 0,4 unidades — 1,15 é o máximo
     que alarga sem elas se encostarem. Na vertical não há esse teto, e 2,9
     desfaz o achatamento de 0,6254 do grupo: 1,15 × 2,9 × 0,6254 = 2,09
     unidades, que dão ~4 px em tela. Cinco pontos de 4×4 px se contam a olho;
     um traço de 1,29 px, não.

     `transform-box:fill-box` porque sem ele a origem é a caixa do SVG inteiro e
     a lâmpada sai voando para fora do desenho. */
  .luz-grade [id*="-led-jogador-"]{
    fill:var(--led-apagado);
    transform-box:fill-box;transform-origin:center;transform:scale(1.15,2.9);
  }
  /* `!important` no filtro, e é a única forma: o `filter: url(#outline-filter-2)`
     mora no atributo `style` de cada `<rect>` do desenho, e atributo vence folha.
     O que se perde é um contorno de 0,1 unidade em #cdc5da11 — invisível — e o
     que se ganha é o brilho que faz a lâmpada acesa parecer acesa. */
  .luz-grade .led-on{fill:var(--led-aceso);
                     filter:drop-shadow(0 0 .5px var(--led-aceso)) !important}

  /* ---------- COR: a guia dos oito tons do produto, por controle ---------- */
  .guia{display:flex;gap:4px;align-items:center}
  .guia .tom{flex:1;height:26px;border-radius:6px;border:1px solid var(--border-forte);
             cursor:pointer;padding:0;display:block;min-width:0}
  /* o tom escolhido engrossa POR DENTRO, com sombra, e não com `border-width:2`:
     os nove são `flex:1` e a borda de 2px conta no piso do item — o escolhido
     ficava 2px mais largo que os outros oito, na fileira que ela mede a olho. */
  .guia .tom.on{border-color:var(--fg);box-shadow:inset 0 0 0 1px var(--fg)}
  .guia .livre{
    flex:1;height:26px;border-radius:6px;padding:2px;cursor:pointer;min-width:0;
    border:1px dashed var(--comment);background:
      linear-gradient(45deg,transparent 44%,var(--comment) 44%,var(--comment) 56%,transparent 56%);
  }
  .guia .livre:hover{border-color:var(--purple)}
  .guia .livre::-webkit-color-swatch-wrapper{padding:0}
  .guia .livre::-webkit-color-swatch{border:none;border-radius:4px;opacity:0}
  /* O HEXADECIMAL FICA NA TELA — decisão dela, 28/08, para as duas abas que o
     têm (Controles e Iluminação). Ele é o valor do campo Cor, e por isso mora
     debaixo da guia, na coluna do controle a que pertence. */
  .cel-cor{display:flex;flex-direction:column;gap:4px;justify-content:center}
  .hex{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--fg);
       text-align:center;line-height:14px}

  /* ---------- BRILHO ---------- */
  .cel-brilho{display:flex;align-items:center;gap:9px}
  .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--panel)}
  .num{flex:0 0 38px;text-align:right;font-family:'JetBrains Mono',monospace;
       font-size:11.5px;color:var(--fg)}

  /* ---------- SELECIONE O PLAYER: a troca ---------- */
  .players{display:flex;gap:5px;align-items:center;height:100%}
  /* O BOTÃO CONTINUA COM OS 36px DA ESCALA — quem os fixa é o esqueleto
     (`.players button{height:var(--h-escolha)}`). */
  .players button{
    flex:1;border-radius:7px;gap:6px;min-width:0;
    border:1px solid var(--border-forte);background:var(--app-bg);color:var(--texto-mudo);
    cursor:pointer;font-size:13px;font-weight:600;font-family:'JetBrains Mono',monospace;
  }
  .players button.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg)}
  .players button:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}
  /* O ANEL É O DONO DO NÚMERO, na cor do plástico dele — e é ele que diz com
     QUEM a troca acontece. Ele é o mesmo em todas as colunas, porque o dono de
     um número é um só; o que muda de coluna para coluna é qual botão está `on`.
     ANEL E NÃO BOLINHA CHEIA, de propósito: nesta aba tudo o que é CHEIO de cor
     é LUZ (a barra, as lâmpadas, os tons da guia). Um disco vermelho ao lado do
     "1" seria lido como a luz do Player 1, que é azul. A BORDA é a cor do
     plástico — a mesma gramática do chip da fita. */
  .players .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                 background:none;border:2px solid var(--plastico)}

  /* ---------- DISPOSIÇÃO DE LEDS ---------- */
  .aceso{border:1px solid var(--border-sutil);border-radius:8px;background:var(--app-bg);
         display:flex;align-items:center;justify-content:center;gap:16px;height:100%}
  .tira-luz{width:6px;height:20px;border-radius:3px}
  .tira-luz.esq{box-shadow:-3px 0 12px 1px currentColor}
  .tira-luz.dir{box-shadow:3px 0 12px 1px currentColor}
  .pad{width:56px;height:20px;border-radius:5px;border:1px solid var(--border-forte);
       background:var(--panel);display:flex;align-items:flex-end;justify-content:center;
       padding-bottom:3px}
""" + CSS_LUZINHAS.lstrip("\n") + """
  /* ---------- OPÇÕES ---------- */
  .cel-acoes{display:flex;flex-direction:column;align-items:stretch;gap:4px;
             justify-content:center;margin-top:0}
  .cel-acoes .btn{width:100%}

  /* ---------- o antes e o depois da troca, na legenda ---------- */
  .troca{margin:8px 0 12px;font-size:11.5px}
  .troca-linha{display:flex;align-items:center;gap:10px;margin:5px 0;flex-wrap:wrap}
  .troca-rot{flex:0 0 52px;font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;
             color:var(--comment)}
  .troca-item{display:flex;align-items:center;gap:7px;padding:4px 9px;border-radius:7px;
              border:1px solid var(--border-sutil);background:var(--app-bg)}
  .troca-item.mexeu{border-color:var(--purple);background:var(--sel-bg)}
  .troca-item .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                    background:none;border:2px solid var(--plastico)}
  .troca-item .np{font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--fg)}
  .troca-gesto{margin:6px 0 6px 62px;color:var(--texto-mudo)}
""" + CSS_GLIFO + """
  /* OS GLIFOS DOS TÍTULOS são as peças de `assets/glyphs/` — as mesmas 19 da aba
     Status. Só entram nos dois títulos que NOMEIAM uma peça: a barra de luz e o
     indicador de jogador. "Brilho", "Opções" e "Selecione o player" não são peça
     de controle — pôr o glifo do botão Options ao lado de "Opções" seria um
     trocadilho com outra coisa. */
  .sec-rot .gl{opacity:.9;flex:0 0 auto}
"""


def botao_player(c, n):
    """Um número, na coluna de UM controle: dá-lo a `c` troca `c` com o dono."""
    d = DONO.get(n)
    eu = d is c
    anel = (f'<i class="dono" style="--plastico:{cor_da_zona(d["cor"])}"></i>'
            if d is not None else "")
    if eu:
        dica = f"O {c['nome']} É o Player {n} — é o número dele hoje."
    elif d is None:
        dica = f"Player {n} — livre."
    else:
        dica = (f"Dar o Player {n} ao {c['nome']}: o {d['nome']} ({d['via']}), "
                f"que tem o {n} hoje, fica com o {c['jogador']}. Os dois trocam de "
                f"lugar — ninguém repete número e ninguém fica sem.")
    return f'<button class="{"on" if eu else ""}" title="{dica}">{anel}{n}</button>'


def coluna(c):
    """A coluna de UM controle: o desenho dele e tudo o que se ajusta nele."""
    p, cor, j = c["pref"], luz(c["jogador"]), c["jogador"]
    b = BRILHO[c["pref"]]
    tons = "\n".join(
        f'            <button class="tom{" on" if t == cor else ""}" style="background:{t}"'
        f' title="Cor automática do Player {i} — usar aqui pinta a barra do'
        f' {c["nome"]}, e não muda o número dele."></button>'
        for i, t in enumerate(TONS, 1))
    return f'''        <div class="ctrl">
          <div class="moldura" style="--plastico:{cor_da_zona(c["cor"])}" title="O {c["nome"]} agora: a barra na cor do Player {j}, e as cinco lâmpadas no padrão dele.">
            {svg(f"il-{p}", c["cor"], jogador=j, luz=cor)}
          </div>
          <div class="ctrl-rot">P{j} <span class="pt">•</span> {c["nome"]} <span class="pt">•</span> {c["via"]}</div>
          <div class="cel-cor">
            <span class="guia">
{tons}
              <input type="color" class="livre" value="{cor.lower()}"
                     title="Livre — abre o seletor para uma cor que não está na guia.">
            </span>
            <span class="hex">{cor}</span>
          </div>
          <div class="cel-brilho">
            <span class="trilho"><span class="cheio" style="width:{b}%"></span></span>
            <span class="num">{b}%</span>
          </div>
          <div class="players">
{chr(10).join("            " + botao_player(c, n) for n in NUMEROS)}
          </div>
          <div class="aceso" title="O {c["nome"]} aceso: as duas tiras na cor escolhida, e as cinco lâmpadas no padrão do Player {j}.">
            <span class="tira-luz esq" style="background:{cor};color:{cor};opacity:{b / 100}"></span>
            <span class="pad">{luzinhas(j)}</span>
            <span class="tira-luz dir" style="background:{cor};color:{cor};opacity:{b / 100}"></span>
          </div>
          <div class="cel-acoes">
            <button class="btn roxo" title="Tira a cor escolhida à mão e devolve a automática — a do número deste controle.">Voltar ao automático</button>
            <button class="btn vermelho" title="Apaga a barra de luz do {c["nome"]}.">Desligar</button>
          </div>
        </div>'''


def item_troca(c, n, mexeu=False):
    """Um controle com um número, para o antes/depois da legenda."""
    return (f'<span class="troca-item{" mexeu" if mexeu else ""}"'
            f' style="--plastico:{cor_da_zona(c["cor"])}">'
            f'<i class="dono"></i><span class="np">P{n}</span>'
            f'<span>{c["nome"]}</span>{luzinhas(n)}</span>')


#: O DEPOIS da troca: os dois trocam, os outros ficam. É uma permutação, e é o
#: que a frase dela exige — "nunca fica um número repetido nem um controle sem
#: número". Calculado, não escrito: se a mesa mudar, o desenho da legenda muda.
DEPOIS = {c["pref"]: c["jogador"] for c in MESA}
DEPOIS[QUER_O_1["pref"]], DEPOIS[TEM_O_1["pref"]] = TEM_O_1["jogador"], QUER_O_1["jogador"]

MIOLO = f'''
    <div class="quadro luzes">
      <div class="quadro-topo">
        <span class="quadro-titulo">Iluminação</span>
        <span class="ajuda">?<span class="dica">
          A <b>barra de luz</b> é a faixa que acende dos dois lados do touchpad. Ela é a
          identidade do controle na mesa: você olha e sabe de quem é.<br><br>
          As colunas são os <b>{len(MESA)} controles ligados agora</b>, cada uma com o desenho no
          plástico dele. O plástico é físico e pode se repetir; a <b>luz</b> é o que nunca
          se repete — é ela que separa dois controles do mesmo modelo.<br><br>
          Cada coluna se ajusta sozinha, no lugar dela — <b>a fita lá em cima está esmaecida
          porque não há um controle escolhido nesta aba</b>: estão os quatro.<br><br>
          Sem escolha à mão, cada barra fica na <b>cor do número</b> do controle:
          1 azul, 2 vermelho, 3 verde, 4 rosa. Os oito quadradinhos da guia são essas
          mesmas oito cores; o último é o <b>livre</b>, para uma cor fora delas.<br><br>
          O que você mudar vale <b>agora</b>; para que volte amanhã, é o <b>Salvar Perfil</b>
          do rodapé que grava.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <div class="luz-grade">

          <div class="rotulos">
            <div class="cel-des">
              <div class="sec-rot">Controle</div>
              <div class="legenda">A barra acende na cor do número. A borda da moldura é a
                cor do plástico, e as cinco luzinhas acima do touchpad dizem o número.</div>
            </div>
            <div></div>
            <div>
              <div class="sec-rot">{glifo("lightbar", tam=14)} Cor
                <span class="ajuda">?<span class="dica">
                  Os oito quadradinhos são as <b>oito cores do produto</b> — uma por número
                  de jogador (1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano,
                  7 laranja, 8 roxo). O nono é o <b>livre</b>, para uma cor que não está
                  nelas.<br><br>
                  Escolher um tom aqui pinta a barra <b>daquele controle</b> e <b>não muda o
                  número dele</b>. O código embaixo é a cor exata que vai para o aparelho.
                </span></span>
              </div>
            </div>
            <div><div class="sec-rot">Brilho</div></div>
            <div>
              <div class="sec-rot">Selecione o player
                <span class="ajuda">?<span class="dica">
                  O player é quem este controle é na mesa: o número do cabeçalho, o dos cards
                  da aba <b>Controles</b>, e o das cinco luzinhas brancas acima do
                  touchpad.<br><br>
                  <b>Isto não escolhe o que você está vendo</b> — os {len(MESA)} estão na tela. Isto
                  <b>dá</b> um número ao controle da coluna. O <b>anelzinho</b> de cada botão é
                  a cor do plástico de quem tem aquele número hoje.<br><br>
                  Dar a este controle um número que já é de outro faz <b>os dois trocarem de
                  lugar</b>: pôr o {QUER_O_1["nome"]} no {TEM_O_1["jogador"]} faz o
                  {TEM_O_1["nome"]} virar {QUER_O_1["jogador"]}. Nunca fica um número
                  repetido, nunca fica um controle sem número — por isso a fileira oferece
                  os números que existem na mesa, e não os oito.<br><br>
                  Um jogo em co-op pode mandar o seu próprio número por cima — e aí quem
                  manda nas luzinhas é o jogo, não esta escolha.
                </span></span>
              </div>
              <div class="legenda">Trocar troca os dois de lugar.</div>
            </div>
            <div><div class="sec-rot">{glifo("led-jogador", tam=14)} Disposição de LEDs</div></div>
            <div><div class="sec-rot">Opções</div></div>
          </div>

{chr(10).join(coluna(c) for c in MESA)}

        </div>

      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>Trocar o número: o antes e o depois</h2>
  <p>O caso é o seu, de 26/08 — <i>"o meu controle azul é o player 2 e antes de irmos pro
  jogo ele tem que ser o player 1"</i>. Na coluna do <b>{QUER_O_1["nome"]}</b>, clique no
  <b>{TEM_O_1["jogador"]}</b>:</p>

  <div class="troca">
    <div class="troca-linha"><span class="troca-rot">Antes</span>
{chr(10).join("      " + item_troca(c, c["jogador"], c is QUER_O_1) for c in MESA)}
    </div>
    <div class="troca-gesto">↓ clique no <b>{TEM_O_1["jogador"]}</b> na coluna do
      <b>{QUER_O_1["nome"]}</b></div>
    <div class="troca-linha"><span class="troca-rot">Depois</span>
{chr(10).join("      " + item_troca(c, DEPOIS[c["pref"]], DEPOIS[c["pref"]] != c["jogador"]) for c in MESA)}
    </div>
  </div>

  <ul>
    <li><b>Os dois trocam, os outros não se mexem.</b> É uma permutação: ninguém repete
        número e ninguém fica sem. Por isso a fileira oferece
        <span class="marca">{" · ".join(str(n) for n in NUMEROS)}</span> — os números que
        existem na mesa. Um número livre não teria com quem trocar, e dá-lo deixaria um
        controle sem número.</li>
    <li><b>As luzinhas seguem o número</b>, no padrão do produto: 1 é a do <b>meio</b>,
        2 são as duas de dentro, 3 são as pontas e o meio, 4 são quatro sem a do meio
        (<code>core/led_control.py::player_led_pattern</code>).</li>
    <li><b>E a cor da barra segue junto</b>, porque sem escolha à mão ela é a cor do
        <i>número</i>: depois da troca o {QUER_O_1["nome"]} acende
        <span class="marca">{luz(TEM_O_1["jogador"])}</span> e o {TEM_O_1["nome"]} acende
        <span class="marca">{luz(QUER_O_1["jogador"])}</span>
        (<code>core/led_control.py::player_slot_color</code>).</li>
  </ul>

  <h2>O que mudou hoje</h2>
  <ul>
    <li><b>A fita está esmaecida, e a aba parou de ter um "escolhido".</b> Antes as seções de
        baixo ajustavam UM controle — o que a fita apontava, de borda roxa. Com a fita
        inerte e presa em <span class="marca">Todos</span>, esse destaque passaria a afirmar
        na tela uma coisa que a fita já não faz. Saiu o escolhido, não o ajuste: cada coluna
        se ajusta sozinha, e agora dá para mudar a cor dos quatro sem sair da tela.</li>
    <li><b>"Selecione o player" deixou de perguntar o que já está respondido.</b> Com os
        {len(MESA)} na tela, "qual estou vendo" não tem mais objeto. Ele agora <b>dá</b> o número —
        e dar um número ocupado é uma troca, não uma fila. O texto antigo dizia que o outro
        "desliza para abrir lugar", o que é um rodízio; a sua palavra de 28/08 é
        <b>troca</b>, e as duas dão resultados diferentes com três ou mais controles.</li>
    <li><b>As lâmpadas do jogador ficam aqui — e agora se leem.</b> Medido no Chrome, no
        desenho de 224 px elas saíam com <b>3,84 × 1,29 px</b>: um traço, não cinco pontos.
        Agrandar o desenho não resolvia (ocupar a coluna inteira ganharia 0,1 px de altura),
        então quem cresceu foi a lâmpada, dentro do desenho, até ~4 × 4 px. Elas saem só dos
        desenhos pequenos das outras abas.</li>
    <li><b>Saiu o "Sony" do rótulo</b>, que ainda estava aqui. Decisão sua de 27/08 — "tira o
        Sony das outras abas também", porque a marca se repetia em cada card sem separar um
        controle do outro. Agora ele lê <span class="marca">P1 • Cosmic Red • USB</span>,
        que é exatamente o que os chips da fita dizem 100 px acima, na mesma tela.
        <b>Aviso:</b> Controles e Conexões ainda escrevem a forma longa
        (<i>Sony • Player 1 • Cosmic Red • USB</i>), citando a sua ordem de 26/08 — a que
        você trocou no dia seguinte. Não é falta de espaço: medida aqui, a forma longa dá
        196 px numa coluna de 208. É uma escolha, e ela precisa valer para as três.</li>
    <li><b>O hexadecimal fica</b>, por decisão sua de 28/08 — e agora há um por controle,
        debaixo da guia da coluna dele.</li>
    <li><b>O que NÃO coube, dito:</b> as cinco luzinhas em miniatura que ficavam dentro de
        cada botão de número. A coluna de um controle tem 208 px e os
        {len(NUMEROS)} botões ficam com 48 px cada; as luzinhas pedem 56 px só elas. O padrão de
        cada número não se perdeu — ele está nos {len(MESA)} desenhos, lado a lado: o P1 acende uma,
        o P2 duas, o P3 três, o P4 quatro. A tela mostra os
        {len(NUMEROS)} padrões ao mesmo tempo, que é mais do que o botão mostrava.</li>
    <li><b>E o arranjo que você pediu virou coluna, com um motivo:</b> "O Opções fica ao lado
        direito de Cor e brilho e abaixo fica os outros dois. <i>Isso por controle</i>" era
        para a aba que mostrava UM controle na largura inteira. Com
        {len(MESA)} colunas de 208 px não cabem dois tópicos lado a lado — quem ficou lado a lado
        foram os controles. Os cinco tópicos empilham na coluna, e a FILEIRA é o que os
        alinha entre os {len(MESA)}.</li>
  </ul>

  <h2>O que você pediu, e continua aqui</h2>
  <ul>
    <li><b>Cor e Brilho na mesma largura</b> — os dois são a coluna inteira do controle.</li>
    <li><b>Os títulos têm todos o mesmo estilo</b>, e agora começam todos no mesmo x, porque
        moram na mesma coluna: <span class="marca">Controle · Cor · Brilho · Selecione o
        player · Disposição de LEDs · Opções</span>.</li>
    <li><b>Os dois botões de Opções</b> continuam <span class="marca">roxo</span> e
        <span class="marca">vermelho</span>, como o <b>Parar</b> da Vibração.</li>
    <li><b>As cinco colunas acabam no mesmo y</b> — as sete linhas são compartilhadas, e a
        cura do vão é na altura, nunca <code>space-between</code>.</li>
    <li><b>Barra vertical entre blocos irmãos</b>, como na Vibração.</li>
  </ul>

  <h2>Ainda aberto</h2>
  <ul>
    <li><b>Um número fora da mesa.</b> A fileira oferece os
        {len(NUMEROS)} números ocupados, porque troca só existe entre dois. O produto cobre 1 a 8
        (<code>core/led_control.py</code>) — se um dia for preciso pôr um DualSense no 5 com
        a mesa em 4, isso é <i>mover</i>, não trocar, e é outra decisão sua.</li>
    <li><b>O "Desligar" guarda a cor ou grava preto?</b> A dica de hoje promete uma coisa e o
        código faz a outra (<code>lightbar_actions.py:1023</code>).</li>
    <li><b>Ajustar os quatro de uma vez?</b> Não há mais alvo único nesta aba, então um
        "aplicar a todos" teria de ser um botão próprio — e ele não existe.</li>
  </ul>
</div>

</body>
</html>
'''

# `fita_viva=False` — decisão dela, 28/08/2026: em Gatilhos, Iluminação e
# Vibração os quatro ficam lado a lado, sempre visíveis, e a fita fica
# esmaecida. Ela não é o alvo desta aba porque não há alvo: cada coluna se
# ajusta no seu lugar.
n = monta("04-iluminacao", "Iluminação", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"04-iluminacao: OK, {n} divs · {len(MESA)} controles · números {NUMEROS}")
