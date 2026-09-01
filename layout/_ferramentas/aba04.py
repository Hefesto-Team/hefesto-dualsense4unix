import sys, pathlib, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
import medidas
import monta as monta_
from itertools import cycle
from monta import (monta, svg, glifo, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, luzinhas, player_slot_color, tom_da_casa)

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

#: AS OITO CORES, NO TOM DA CASA — 30/08/2026.
#:
#: Ela, olhando a fileira: *"essas cores de seleção do lightbar seguem me
#: incomodando profundamente, pq destoam demais do resto do layout. (…) pode ser
#: as mesmas cores mas num tom que fiquem em harmonia com o resto do layout"*.
#:
#: O QUE ELAS ERAM: as primárias cruas que `player_slot_color` devolve —
#: #0000FF, #FF0000, #00FF00, #FF0080, #FFFF00… Cor de monitor de teste, com
#: saturação total, ao lado de uma interface inteira construída na paleta
#: Dracula. Não é gosto: uma primária pura sobre o painel #282a36 grita mais que
#: qualquer coisa da tela, e a fileira roubava a atenção do desenho do controle.
#:
#: O QUE ELAS SÃO AGORA: as MESMAS OITO MATIZES, no tom que a casa já usa em
#: todo o resto. Azul e roxo compartilham a família do `--purple` porque a
#: paleta não tem um azul próprio — e o azul do player 1 é a cor que mais
#: aparece, então ela vai para o `--cyan`, que é o azul desta casa.
#:
#: ISTO É PROPOSTA DE PRODUTO, e está aqui porque mockup é especificação: o
#: `core/led_control.player_slot_color` continua devolvendo as primárias, e
#: enquanto ele não adotar estes tons o controle acende a cor de cima e a tela
#: mostra a de baixo. A troca no produto foi aprovada por ela; falta executar.
# (o mapa mora em `monta.py` — dois donos: esta guia e a barra de luz da 02)
TONS = [tom_da_casa(luz(n)) for n in range(1, 9)]

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
  /* A LINHA NÃO PODE QUEBRAR NOS VÃOS — 30/08/2026, pedido dela: *"as linhas
     horizontais (…) precisam melhorar ali"*.

     Elas já atravessavam as cinco colunas, no mesmo y — mas o `gap:16px` do grid
     abria um buraco entre cada duas, e o olho lia CINCO TRACINHOS em vez de uma
     linha. Ampliado a 2x fica evidente.

     A cura é trocar o vão HORIZONTAL por respiro DENTRO da célula: `column-gap:0`
     e o padding que já existia no `.ctrl` cresce para os dois lados. A distância
     entre o conteúdo de duas colunas continua a mesma; o que muda é que agora ela
     é padding — e padding não interrompe borda. O vão VERTICAL (`row-gap`) fica:
     é ele que separa uma linha da outra. */
  .luz-grade{
    display:grid;
    /* A LARGURA DA COLUNA DE RÓTULOS E O VÃO ATÉ A PRIMEIRA COLUNA DE
       CONTROLE VÊM DE `medidas.py` — o dono deles nas TRÊS abas que têm
       essa coluna. Eram 132px e 16 aqui, 138 e 12 na Gatilhos, e o texto
       acabava em x=536 numa e x=542 na outra. Ela viu: *"tem algo que
       deixa estranho essa área da primeira coluna."* */
    grid-template-columns:var(--larg-rot) repeat(4,1fr);
    gap:var(--gap-col);
    --r-des:146px;--r-nome:16px;--r-cor:44px;--r-brilho:26px;
    --r-player:62px;--r-leds:34px;--r-acoes:72px;
    /* O RESPIRO É O DONO, E O PASSO É O DOBRO DELE — 31/08/2026, pedido dela:
       *"aba iluminação tem a mesma questão do respiro vertical."* É a mesma
       construção da Vibração (30/08) e da Gatilhos (hoje), e o mesmo valor da
       Vibração: 5.
       MEDIDO ANTES: o passo era 8 e a divisória ficava em `top:0` — encostada no
       conteúdo de cima, com o vão INTEIRO embaixo. `a_divisoria_sobe: [0]`.
       O QUE ELE CUSTA: o passo vai de 8 para 10, e 2px em seis vãos são 12. A
       coluna vai de 448 para 460, contra o teto MEDIDO de 476 — 16px de folga.
       A parte que NÃO custa nada é a que arruma o feio: descer a linha meio
       passo só muda de que lado dela o vão está. */
    --r-ar:5px;--r-passo:calc(var(--r-ar) * 2);
  }
  .luz-grade > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-cor) var(--r-brilho)
                       var(--r-player) var(--r-leds) var(--r-acoes);
  }
  /* a barra vertical entre blocos irmãos — pedido dela */
  /* O PADDING SAIU DA COLUNA E FOI PARA AS CÉLULAS — 30/08/2026.
     A borda separadora mora na CÉLULA (`> div > *`), e padding na coluna
     recua a célula junto: a linha parava 21px antes da divisa e voltava a
     ler como tracinho. Com o padding na célula, ela vai de ponta a ponta da
     coluna e encosta na vizinha — o respiro do conteúdo é o mesmo. */
  .luz-grade .ctrl{border-left:1px solid var(--linha);padding:0 8px 0 12px}

  /* ---------- O LUGAR VAZIO ----------
     A mesma gramática da Jogar, da Controles e da Gatilhos: cor explícita e
     NADA de `opacity` — a lição medida da `.fita.inerte`, que a opacidade tira
     contraste e peso do traço ao mesmo tempo.

     O DESENHO FICA CINZA POR `!important` porque a cor da peça é `style=` INLINE
     dentro do SVG: o gerador de cores a escreve lá para o arquivo abrir colorido
     sozinho, e regra externa não vence atributo inline sem isto. `.corpo` entra
     junto com `.peca` — foi a ampliação da foto na aba Jogar que o achou, com o
     P3 continuando roxo e o P4 branco depois da primeira volta. */
  /* O TRAVESSÃO PREENCHE A CÉLULA, e isto é a régua de alinhamento falando.
     A coluna vazia tem a MESMA altura da viva (452px) e as mesmas sete linhas —
     medido. O que acabava 26px antes era o CONTEÚDO da última célula: dois
     botões empilhados preenchem os 74px de `--r-acoes`; um travessão centrado
     para no meio. A régua leu isso como "o conteúdo das colunas acaba em y
     diferentes", e leu certo.
     `height:100%` no marcador resolve sem mexer em altura nenhuma: ele passa a
     ocupar a célula e o texto continua centrado dentro dele. */
  .luz-grade .ctrl.vazia .nada{display:flex;align-items:center;justify-content:center;height:100%;width:100%}
  .luz-grade .ctrl.vazia .ctrl-rot,
  .luz-grade .ctrl.vazia .nada{color:var(--linha)}
  .luz-grade .ctrl.vazia .moldura{border-color:var(--border-forte)}
  .luz-grade .ctrl.vazia .ds-svg .peca,
  .luz-grade .ctrl.vazia .ds-svg .corpo,
  .luz-grade .ctrl.vazia .ds-svg .miolo *{fill:var(--linha) !important}
  .luz-grade .ctrl.vazia .ds-svg .corpo{stroke:var(--border-forte) !important}
  /* OS DETALHES CLAROS TAMBÉM CAEM, e eles só aparecem AQUI. Na aba Jogar o
     desenho tem 62px e estes elementos somem sozinhos; nesta aba ele tem 146 e
     eles ficam à mostra — medido no DOM do lugar vazio: 8 `line` em branco
     (#f8f8f2), 7 `text` em `--texto-suave` e 4 `path` em #d8d8d8, que são os
     glifos L/R/PS e os traços dos botões.
     Copiar a regra da Jogar não bastava: o que muda com o TAMANHO do desenho
     tem de ser medido no tamanho em que ele é desenhado. */
  .luz-grade .ctrl.vazia .ds-svg text{fill:var(--linha) !important}
  .luz-grade .ctrl.vazia .ds-svg line{stroke:var(--linha) !important}
  .luz-grade .ctrl.vazia .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                            stroke:var(--linha) !important}
  /* O TOUCHPAD E OS BOTÕES SÃO `rect`, `circle` e `polygon`, e a ampliação foi
     quem os achou: com `path`, `line` e `text` já apagados, o touchpad continuou
     cinza-claro (#8a8a96) no meio de um controle inteiro em `--linha`.
     `fill` NÃO leva `none` como valor aqui, e é de propósito: pintar um contorno
     vazado apagaria a forma em vez de escurecê-la. Quem tem `fill:none` no
     arquivo continua sem, porque `var(--linha)` só substitui uma cor que existe. */
  .luz-grade .ctrl.vazia .ds-svg rect:not([fill="none"]),
  .luz-grade .ctrl.vazia .ds-svg circle:not([fill="none"]),
  .luz-grade .ctrl.vazia .ds-svg polygon:not([fill="none"]),
  .luz-grade .ctrl.vazia .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .luz-grade .ctrl.vazia .ds-svg rect,
  .luz-grade .ctrl.vazia .ds-svg circle,
  .luz-grade .ctrl.vazia .ds-svg polygon,
  .luz-grade .ctrl.vazia .ds-svg ellipse{stroke:var(--border-forte) !important}
  /* O TRAVESSÃO FICA ONDE O CONTEÚDO FICARIA — centrado na célula, para as sete
     linhas continuarem legíveis como linhas. */
  .luz-grade .ctrl.vazia > *{display:flex;align-items:center;justify-content:center}
  .luz-grade .ctrl.vazia .moldura{display:block}
  /* o respiro entre colunas é do CONTEÚDO, não da célula: padding na coluna
     recua os filhos e a borda deles para 16px antes da divisa, e a linha
     volta a quebrar. Aqui a célula vai até o fim e quem se afasta é o texto. */

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido dela:
     *"com linha abaixo de cada campo"*.
     POR QUE NA CÉLULA E NÃO NA GRADE: `.luz-grade` é um grid de 5 colunas, mas
     as LINHAS não são dele — cada coluna é um grid próprio com as mesmas sete
     alturas (`--r-des` … `--r-acoes`). Não existe "linha da grade" onde pendurar
     uma borda; o que existe é a célula. Como as sete alturas são idênticas nas
     cinco colunas, as bordas nascem no mesmo y e leem como uma linha só.
     A borda cai no fim da célula, e o `row-gap` de 8px a separa do campo de
     baixo — o respiro fica em cima da linha seguinte, não colado nela.
     A ÚLTIMA não leva linha: separador depois do último campo não separa nada,
     vira moldura, e a moldura do quadro já existe. */
  /* A LINHA É UM PSEUDO-ELEMENTO, e não a borda da célula — 30/08/2026.
     Como BORDA ela parava no padding da coluna e quebrava em cinco tracinhos;
     movendo o padding para as células a linha ficou inteira mas o desenho do
     controle perdeu 9px (a moldura tem `overflow:hidden` e o SVG cresce com a
     largura). O `::after` com margem negativa resolve os dois: ele sai do
     padding pelos dois lados e atravessa a coluna inteira, sem tocar em
     geometria nenhuma. As cinco colunas têm as mesmas alturas de linha, então
     os cinco segmentos nascem no mesmo y e leem como uma linha só. */
  .luz-grade > div > *{position:relative}
  /* A LINHA É `::before` DA CÉLULA DE BAIXO, e não `::after` da de cima.
     Como `::after` ela era filha da moldura — e a moldura do DESENHO tem
     `overflow:hidden` para conter o SVG, então ela cortava a própria linha
     24px antes da divisa. A célula de baixo não recorta nada, e o traço
     cai no mesmo lugar: entre uma linha e a outra. */
  /* A LINHA DESCE MEIO PASSO E CAI NO MEIO DO VÃO — 31/08/2026. O comentário
     acima dizia que *"o `row-gap` de 8px a separa do campo de baixo — o respiro
     fica em cima da linha seguinte, não colado nela"*, e isso descrevia metade
     do que acontecia: o vão ficava TODO de um lado. O olho lê linha grudada em
     cima e buraco embaixo — que é o *"sobrando e sem respiro"* dela.
     Com `top:-var(--r-ar)` cada campo fica com o mesmo ar acima e abaixo da sua
     divisória, e a tabela mede o mesmo pixel. */
  .luz-grade > div > *::before{content:'';position:absolute;
    top:calc(var(--r-ar) * -1);height:0;
    left:-12px;right:-8px;border-top:1px solid var(--rot-linha)}
  /* A CONTA DA MARGEM NEGATIVA: ela tem de cancelar o padding da coluna E o
     `gap` do grid, senão sobra um buraco do tamanho do vão. À direita são
     8 de padding + 16 de gap = 24; a ÚLTIMA coluna não tem vão depois
     dela, então volta a 8. A coluna de rótulos não tem padding: 0 e 16. */
  .luz-grade > div:not(:last-child) > *::before{right:-24px}
  .luz-grade > .rotulos > *::before{left:0;right:-16px}
  .luz-grade > div > *:first-child::before{display:none}

  /* a coluna dos rótulos: todo título começa no mesmo x, e cada um ocupa a
     ALTURA INTEIRA da sua linha — é assim que a coluna acaba junto das outras */
  .luz-grade .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
  /* O NOME DA LINHA ALINHA À DIREITA — 30/08/2026, pedido dela: *"no nome das
     linhas deixa alinhadas à direita. Todas"*. Encostado na divisa, o rótulo fica
     perto do que ele nomeia em vez de ficar perto da borda do quadro — é o que
     toda tabela de formulário faz, e é o que faz a coluna deixar de ler como
     lista solta e passar a ler como cabeçalho de linha. */
  /* O RÓTULO ALINHA À ESQUERDA — decisão dela, 31/08/2026: *"alinha a esquerda a
     primeira coluna."*

     E ELA REVOGA A DECISÃO DELA MESMA de 30/08 (*"no nome das linhas deixa
     alinhadas à direita. Todas"*). Não é contradição a resolver: é o projeto
     vivo, e o que mudou no meio foi a própria coluna — ela encolheu de 138 para
     o tamanho do conteúdo de cada aba, e à direita, numa coluna justa, o texto
     passou a encostar na divisa em vez de se aproximar do que nomeia.

     DE QUEBRA ISSO CURA UM DESALINHAMENTO QUE A RÉGUA ACUSAVA e que era
     consequência aritmética do alinhamento à direita: rótulos de larguras
     diferentes COMEÇAM em x diferentes. À esquerda, todos começam no mesmo. */
  .luz-grade .rotulos > *{align-items:flex-start;text-align:left}
  .luz-grade .rotulos .sec-rot{justify-content:flex-start}
  .luz-grade .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  /* O RÓTULO DA PRIMEIRA LINHA VOLTOU A CENTRAR — 30/08/2026.
     Ele estava preso no topo (`flex-start`) porque a legenda de sete linhas vinha
     logo abaixo dele e as duas juntas enchiam a célula. A legenda virou dica no
     mesmo dia, e o `flex-start` sobrou: o rótulo ficava sozinho no alto de uma
     célula de 146 px, com o vazio inteiro embaixo. Centrado, ele fica na altura
     do desenho que nomeia — a cura do vão é na ALTURA, regra dela. */
  .luz-grade .rotulos .cel-des{gap:8px}
  /* A CAIXA ALTA SAIU — 30/08/2026. A regra desta casa sobre maiúscula é a
     PRIMEIRA LETRA, e ela confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     ela apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           display:flex;align-items:center;gap:6px}
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
  /* A MOLDURA DA AMOSTRA SAIU — 31/08/2026, e é a mais pura das "bordas
     sobrando": um retângulo de 1px em volta de um retângulo CHEIO da cor que
     ele mostra. São oito por controle, trinta e dois na tela, e nenhum deles
     separava coisa nenhuma — o `gap:4px` já separa, e o conteúdo é a própria
     cor. A borda continua existindo em `transparent`: é ela que o `.on` pinta,
     e sem ela o tom escolhido mudaria de tamanho ao ser escolhido. */
  .guia .tom{flex:1;height:26px;border-radius:6px;border:1px solid transparent;
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
    border:1px solid var(--linha);background:var(--app-bg);color:var(--texto-mudo);
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
  /* A CAIXA DA DISPOSIÇÃO PERDEU A MOLDURA — 31/08/2026. Ela era uma borda
     dentro de outra: `.aceso` emoldurava, e o `.pad` lá dentro — 20px mais
     abaixo — emoldurava de novo. Duas linhas onde uma basta, e a de fora não
     separava nada: a faixa já está delimitada pela divisória de cima, pela de
     baixo e pela barra vertical da coluna. Quem tem de ter contorno é o
     touchpad, porque o contorno É o desenho dele. */
  .aceso{border-radius:8px;background:var(--app-bg);
         display:flex;align-items:center;justify-content:center;gap:16px;height:100%}
  .tira-luz{width:6px;height:20px;border-radius:3px}
  .tira-luz.esq{box-shadow:-3px 0 12px 1px currentColor}
  .tira-luz.dir{box-shadow:3px 0 12px 1px currentColor}
  .pad{width:56px;height:20px;border-radius:5px;border:1px solid var(--linha);
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
  .troca-rot{flex:0 0 52px;font-size:10.5px;
             color:var(--comment)}
  .troca-item{display:flex;align-items:center;gap:7px;padding:4px 9px;border-radius:7px;
              border:1px solid var(--linha);background:var(--app-bg)}
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
    """Um número, na coluna de UM controle: dá-lo a `c` troca `c` com o dono.

    O DONO SÓ EXISTE SE ELE ESTIVER NA MESA — 31/08/2026, e foi a régua desta
    aba que achou. O `title` dizia *"Dar o Player 3 ao Cosmic Red: o Galactic
    Purple (BT), que tem o 3 hoje, fica com o 1"* — e o Galactic Purple está
    DESCONECTADO. Ele não tem o 3 hoje; ele não tem nada hoje.

    É a mesma família do que ela mandou tirar do cabeçalho da coluna (*"colocar
    algo como Desconectado e não os controles mockados"*): a `MESA` sabe que o
    P3 é um Galactic Purple, e a TELA não deve saber enquanto ele não estiver
    lá. Um número sem dono na mesa é um número **livre**, e é isso que a dica
    passa a dizer.
    """
    d = DONO.get(n)
    if d is not None and not d.get("conectado", True):
        d = None
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


def coluna_vazia(c):
    """O LUGAR de um controle que não está na mesa — ordem dela, 31/08/2026:

        "Todas as abas tem que ter só dois controles conectados no momento, o
         resto fica off." · "Deixa os outros espaços dos 4 controles a mostra
         ainda mas cinza igual vc fez na aba jogar."

    A COLUNA CONTINUA NA TELA, com as sete linhas na mesma altura — é isso que
    mantém as divisórias atravessando as cinco colunas no mesmo y, que é o que
    ela mandou arrumar em 30/08. O que sai é o ESTADO: a cor, o brilho, o número
    do player e os botões, porque nenhum deles tem controle para valer.

    O NOME DIZ A POSIÇÃO E O ESTADO, nunca o do plástico — a mesma decisão que
    ela tomou na Gatilhos no mesmo dia: *"colocar algo como Desconectado e não
    os controles mockados."*

    O DESENHO FICA, apagado. Um lugar sem desenho nenhum não diz que ali cabe um
    controle; um desenho cinza diz.
    """
    j = c["jogador"]
    return f'''        <div class="ctrl vazia" data-conectado="nao"
             title="Nenhum controle neste lugar.">
          <div class="moldura">
            {svg(f"il-{c['pref']}", c["cor"], lampadas=False)}
          </div>
          <div class="ctrl-rot">P{j} <span class="pt">•</span> Desconectado</div>
          <div class="cel-cor"><span class="nada">{VAZIO}</span></div>
          <div class="cel-brilho"><span class="nada">{VAZIO}</span></div>
          <div class="players"><span class="nada">{VAZIO}</span></div>
          <div class="aceso"><span class="nada">{VAZIO}</span></div>
          <div class="cel-acoes"><span class="nada">{VAZIO}</span></div>
        </div>'''


#: O marcador de campo vazio — o mesmo travessão da Jogar e da Controles.
VAZIO = "—"


def coluna(c):
    """A coluna de UM controle: o desenho dele e tudo o que se ajusta nele."""
    # DUAS ESCALAS DA MESMA COR, e ela viu: *"a cor selecionada (…) precisa
    # refletir no lightbar."* `luz()` devolve o hex CRU que o produto manda ao
    # controle (#0000FF); `tom_da_casa()` traduz para o tom desta janela, que é
    # o que a guia de oito cores pinta. Até 31/08 a guia usava um e o lightbar,
    # as luzinhas e o desenho usavam o outro — a mesma cor em dois azuis
    # diferentes na mesma coluna.
    #
    # QUEM MANDA NA TELA É O TOM DA CASA, porque é ele que ela clica. O hex cru
    # continua ESCRITO embaixo da guia, e é o certo: aquele campo diz o valor que
    # o produto grava, não a tinta que a janela usa para desenhá-lo.
    p, j = c["pref"], c["jogador"]
    cor = luz(j)                 # o hex cru do produto — o que o `.hex` mostra
    tinta = tom_da_casa(cor)     # o tom desta janela — o que a tela ACENDE
    b = BRILHO[c["pref"]]
    # O TOM ESCOLHIDO NUNCA ACENDIA, e ela viu sem medir: *"a cor selecionada
    # precisa ter uma borda."* Medido no DOM: `.tom.on` casava ZERO botões nos
    # dois controles conectados — a guia de oito cores mostrava a escolha em
    # nenhuma delas.
    #
    # A CAUSA são duas escalas comparadas como se fossem uma. `TONS` passa por
    # `tom_da_casa()`, que traduz o hex CRU do produto para o tom desta janela; a
    # comparação era contra `cor`, que é o hex cru. `#0000FF` nunca é igual ao
    # azul da casa, então nada casava — e um `if` que nunca é verdadeiro não dá
    # erro, dá SILÊNCIO. É a régua que "acha zero" em forma de CSS.
    #
    # A CURA TRADUZ OS DOIS LADOS, não escolhe um: o botão continua pintado com o
    # tom da casa (é o que ela vê) e a comparação passa a ser entre tons.
    tons = "\n".join(
        f'            <button class="tom{" on" if t == tom_da_casa(cor) else ""}" style="background:{t}"'
        f' title="Cor automática do Player {i} — usar aqui pinta a barra do'
        f' {c["nome"]}, e não muda o número dele."></button>'
        for i, t in enumerate(TONS, 1))
    return f'''        <div class="ctrl">
          <div class="moldura" style="--plastico:{cor_da_zona(c["cor"])}" title="O {c["nome"]} agora: a barra na cor do Player {j}, e as cinco lâmpadas no padrão dele.">
            {svg(f"il-{p}", c["cor"], jogador=j, luz=tinta)}
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
            <span class="tira-luz esq" style="background:{tinta};color:{tinta};opacity:{b / 100}"></span>
            <span class="pad">{luzinhas(j)}</span>
            <span class="tira-luz dir" style="background:{tinta};color:{tinta};opacity:{b / 100}"></span>
          </div>
          <div class="cel-acoes">
            <button class="btn roxo" title="Tira a cor escolhida à mão e devolve a automática — a do número deste controle.">Automático</button>
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
        <!-- DE 777 PARA ~230 CARACTERES — 30/08/2026, mesma regra da Vibração: o
             parágrafo que nomeia um campo vai para o `?` daquele campo. O da cor
             das barras foi para "Cor", o de gravar foi para o rodapé (que já tem
             `title` nos quatro botões desde hoje). -->
        <span class="ajuda">?<span class="dica">
          A <b>barra de luz</b> é a faixa que acende dos dois lados do touchpad, e é a
          identidade do controle na mesa: você olha e sabe de quem é.<br><br>
          O plástico é físico e pode se repetir; a <b>luz</b> é o que nunca se repete.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <div class="luz-grade">

          <div class="rotulos">
            <!-- A LEGENDA VIROU DICA — 30/08/2026, pedido dela sobre este texto
                 exato: *"esse texto selecionado não existia no original"*.
                 Ela não some: passa para o `?`, que é onde esta aba já põe toda
                 explicação (o rótulo "Cor", logo abaixo, faz igual desde 28/08).
                 Sete linhas de prosa cinza na coluna de rótulos competiam com os
                 rótulos e ainda empurravam "COR" para longe da linha dele. -->
            <div class="cel-des">
              <div class="sec-rot">Controle
                <span class="ajuda">?<span class="dica">
                  A barra acende na cor do <b>número</b>. A borda da moldura é a cor do
                  <b>plástico</b>, e as cinco luzinhas acima do touchpad dizem o número.<br><br>
                  Cada coluna é um controle e se ajusta sozinha — por isso a fita do topo
                  fica esmaecida aqui: não há um escolhido, estão os quatro.
                </span></span></div>
            </div>
            <!-- A LINHA DO MODELO GANHOU NOME — 30/08/2026, pedido dela:
                 *"a parte do Modelo tá faltando, tá o espaço vazio ali. a primeira
                 coluna serve como nome da linha"*. Esta célula existia vazia só para
                 ocupar a linha `--r-nome` da grade, e uma coluna cujo trabalho é
                 nomear linhas tinha uma linha sem nome. -->
            <div><span class="sec-rot">Modelo</span></div>
            <div>
              <!-- O GLIFO SAIU DO RÓTULO — 30/08/2026, pedido dela: *"os svg do lado
                   esquerdo dos nomes pode remover, eles tão diferentes demais"*. Eram
                   três desenhos de origens diferentes (`lightbar`, `led-jogador`, `l2`/`r2`)
                   ao lado de rótulos que os outros cinco não tinham — a coluna lia como
                   duas gramáticas. O glifo continua no DESENHO do controle, que é onde
                   ele diz de qual peça se fala. -->
              <div class="sec-rot">Cor
                <span class="ajuda">?<span class="dica">
                  Sem escolha à mão, cada barra fica na <b>cor do número</b> do controle.
                  O último quadradinho é o <b>livre</b>, para uma cor fora das oito.<br><br>
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
              <div class="sec-rot">Jogador
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
            </div>
            <div><div class="sec-rot">LEDs</div></div>
            <div><div class="sec-rot">Opções</div></div>
          </div>

{chr(10).join(coluna(c) if c.get('conectado', True) else coluna_vazia(c) for c in MESA)}

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
        Jogador · LEDs · Opções</span>.</li>
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
def _conferir(doc):
    """As decisões dela nesta aba, conferidas NA SAÍDA.

    Só o miolo e sem comentário HTML — a régua da Jogar nasceu errada duas vezes
    por casar token na legenda e no próprio comentário que a explicava.
    """
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    # E O `<style>` SAI JUNTO: os SVGs carregam a folha das cores do plástico
    # dentro deles, com um comentário por modelo (`/* Galactic Purple · código
    # 04 */`). Isso é DADO do CSV, não tela — e contá-lo fez a régua reprovar
    # um nome que ela mesma não põe em lugar nenhum visível.
    corpo = re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    # 1. O RESPIRO — *"aba iluminação tem a mesma questão do respiro vertical."*
    #    A divisória cai no MEIO do vão, e o passo é o DOBRO do ar. As duas
    #    metades, porque uma sem a outra deixa o vão todo de um lado.
    exigir("top:calc(var(--r-ar) * -1)" in doc,
           "a divisória voltou para o topo da célula — vão todo de um lado só")
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc,
           "o passo deixou de ser o dobro do ar")

    # 2. A MESA — dois conectados, dois lugares vazios. *"Todas as abas tem que
    #    ter só dois controles conectados no momento, o resto fica off."*
    vazios = [c for c in MESA if not c.get("conectado", True)]
    exigir(corpo.count('class="ctrl vazia"') == len(vazios),
           f"as colunas vazias não são {len(vazios)}")
    exigir(corpo.count('class="ctrl"') == len(MESA) - len(vazios),
           "uma coluna conectada virou vazia, ou o contrário")

    # 3. O LUGAR VAZIO DIZ A POSIÇÃO E O ESTADO — a mesma decisão da Gatilhos:
    #    *"colocar algo como Desconectado e não os controles mockados."*
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")

    # 4. NENHUM AJUSTE VIVO NUM LUGAR VAZIO. Sem controle não há cor, brilho nem
    #    número de player — desenhar um é oferecer um ajuste que não existe.
    for pedaco in corpo.split('class="ctrl vazia"')[1:]:
        bloco = pedaco.split('<div class="ctrl', 1)[0]
        for proibido in ('class="tom', 'type="color"', 'class="cheio"', 'class="pl'):
            exigir(proibido not in bloco,
                   f"um lugar vazio tem ajuste vivo: {proibido!r}")

    # 5. OS TRÊS RÓTULOS QUE ELA ENCURTOU — 31/08/2026: *"aonde tem Voltar ao
    #    automático deixa só Automático; onde tem Disposição dos LEDs coloca só
    #    LEDs; Selecione o player coloca só Jogador — vai ficar subentendido."*
    #    As duas metades: o curto tem de estar lá, e o longo NÃO.
    for curto, longo in ((">Automático</button>", "Voltar ao automático"),
                         (">LEDs</div>", "Disposição de LEDs"),
                         (">Jogador", "Selecione o player")):
        exigir(curto in corpo, f"o rótulo curto sumiu: {curto!r}")
        exigir(longo not in corpo, f"o rótulo longo voltou: {longo!r}")

    # 6. A COR ESCOLHIDA APARECE MARCADA, e a marca é o `.on` — *"a cor
    #    selecionada precisa ter uma borda."* Ele já existia no CSS e casava
    #    ZERO botões, porque a comparação era entre duas escalas.
    exigir(corpo.count('class="tom on"') == len(monta_.CONECTADOS),
           "a cor escolhida não está marcada em todos os controles da mesa")

    # 7. A GUIA E O LIGHTBAR ACENDEM A MESMA TINTA — *"e precisa refletir no
    #    lightbar."* A régua compara o que o gerador escreveu nos dois lugares,
    #    porque foi justamente aí que eles divergiram.
    # A RÉGUA OLHA A TIRA, e a primeira versão dela NÃO OLHAVA: ela procurava a
    # tinta em qualquer lugar do miolo, e a tinta também está no SVG e nas
    # luzinhas — então ela passava com a tira pintada de cor crua. Descoberto na
    # mordida: eu devolvi o `background:{cor}` à tira e a régua ficou VERDE.
    # É a armadilha do `COMO-OLHAR-A-TELA.md` outra vez: casar um token em
    # qualquer lugar do texto, em vez do campo que o significa.
    for c in monta_.CONECTADOS:
        tinta = tom_da_casa(luz(c["jogador"]))
        for lado in ("esq", "dir"):
            exigir(f'class="tira-luz {lado}" style="background:{tinta};color:{tinta}' in corpo,
                   f"a tira {lado} do P{c['jogador']} não acende a tinta da guia ({tinta})")

    if falhas:
        raise SystemExit("ERRO em 04-iluminacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


#: AS DUAS MEDIDAS DA PRIMEIRA COLUNA, injetadas do dono (`medidas.py`). Elas não
#: podem ser digitadas no bloco `CSS` acima porque ele é uma string crua — e um
#: número digitado ali seria a terceira cópia do mesmo valor, que é o defeito que
#: `medidas.py` nasceu para matar.
CSS_DAS_MEDIDAS = f"""
  .luz-grade{{
    --larg-rot:{medidas.larg_rotulos('04-iluminacao')}px;
    --gap-col:{medidas.GAP_DAS_COLUNAS}px;
  }}
"""

n = monta("04-iluminacao", "Iluminação", MIOLO, CSS + CSS_DAS_MEDIDAS, fita_viva=False, legenda=LEGENDA)
_conferir(onde.pagina("04-iluminacao.html").read_text())
print(f"04-iluminacao: OK, {n} divs · {len(monta_.CONECTADOS)} conectado(s) "
      f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s) · "
      f"números {NUMEROS} · respiro 5px, a divisória no meio do vão")
