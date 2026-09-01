# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import re  # noqa: E402
import onde  # noqa: E402
import monta as monta_  # noqa: E402  o MÓDULO, para ler CONECTADOS
from monta import CSS_GLIFO, MESA, R, cor_da_zona, glifo, monta  # noqa: E402

# OS PARÂMETROS DE CADA MODO SAEM DO PRODUTO, e não de uma tabela digitada aqui.
# `app/actions/trigger_specs.py` é quem sabe quantos ajustes cada um dos 19
# modos tem, como cada um se chama e em que faixa ele anda — a mesma metadata
# que a aba Gatilhos usa para montar os sliders. Digitar "Posição, 0 a 9" nesta
# página seria a segunda verdade que o mapa existe para matar: no dia em que o
# produto mudar a faixa, a porcentagem desenhada aqui muda junto ou REPROVA.
sys.path.insert(0, str(R / "src"))
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS  # noqa: E402
from hefesto_dualsense4unix.profiles.trigger_presets import (
    FEEDBACK_POSITION_LABELS,
)

SPEC = {p.label: {q.label: q for q in p.params} for p in PRESETS}

# O GLIFO DO GATILHO TEM UM TAMANHO MEDIDO, e não um escolhido no olho.
# Achado em 27/08 numa foto: a 22px o L2 e o R2 liam como quadradinhos azuis.
# A conta é do próprio arquivo — `assets/glyphs/l2.svg` desenha "L2" com
# `font-size="9"` num `viewBox` de 32, ou seja **28,1% da caixa**. A tela devolve
# `9 × tam / 32`:
#     tam 17 (o recibo) →  4,8px   ·  tam 22 (o título) →  6,2px
#     tam 30            →  8,4px   ·  tam 36            → 10,1px
# O menor tipo desta casa é 10px (`.degrau i` do topo.html) e o segundo menor é
# 10,5px (`.pa-rot`, `.selo`). Abaixo disso não é texto, é textura. Logo o piso é
#     9 × tam / 32 ≥ 10  →  tam ≥ 35,6px  →  **36px**,
# que é exatamente `--h-escolha`: o glifo vale uma linha da escala.
GL = monta_.GLIFO_DA_SECAO

CSS = CSS_GLIFO + """
  /* ---------- Gatilhos · a mesa de quatro ----------
     UMA GRADE SÓ: uma coluna de rótulos e UMA COLUNA POR CONTROLE da `MESA`.
     Decisão dela, 28/08: "os quatro lado a lado, sempre visíveis", e a fita
     esmaecida — cada coluna é o seu próprio alvo, e um chip que não aponta para
     nada seria escolha falsa.

     O NOME DA CLASSE É A ÂNCORA DA RÉGUA, e por isso ele fica. `regua.py` mede
     `.duas-colunas` para "colunas irmãs acabam no mesmo y" e para "as colunas
     somam a largura da caixa"; trocá-lo por um nome mais bonito desligaria as
     duas medições EM SILÊNCIO, que é o defeito desta casa. Precedente:
     `aba08.py:701` já usa a mesma classe com TRÊS colunas.

     AS ALTURAS DE LINHA SÃO COMPARTILHADAS pelas cinco colunas — é isso que faz
     o rótulo "Ajustes" ficar na linha das quatro caixas de ajuste e as cinco
     acabarem no MESMO y. (A cura do vão é na ALTURA, nunca `space-between`.)
     Com a grade compartilhada a dispensa dela para esta aba — "modos diferentes
     têm números de barra diferentes" — deixa de ser necessária: quem iguala
     agora é a LINHA, não um preenchimento inventado dentro de cada coluna. */
  /* AS ALTURAS DE LINHA SAEM DO PYTHON, no fim deste arquivo, e não daqui: a
     legenda da aba cita a altura da coluna e a altura de uma barra, e um número
     digitado no CSS mais outro digitado no texto são duas verdades que acabam
     divergindo. Lá elas são UMA, e a conta da coluna é a soma delas. */
  /* COLUNA COLADA, RESPIRO NA CÉLULA — 30/08/2026, mesma cura da Iluminação e da
     Vibração. Com `column-gap:12px` a linha separadora quebrava quatro vezes e o
     olho lia tracinhos; com o vão em zero e o padding nas células ela atravessa a
     grade inteira, cortada só pela barra vertical de 1px entre blocos. */
  /* `--gl` é o tamanho do glifo que titula a seção, e ele é o MESMO número que
     o Python usa em `glifo(tam=GL)`. Escrito duas vezes, ele diverge no dia em
     que alguém mudar um dos dois — é a cicatriz das cores do plástico. */
  .duas-colunas{display:grid;grid-template-columns:var(--larg-rot) repeat(4,1fr);gap:0 var(--gap-col)}

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido dela, 30/08:
     *"as linhas divisórias em todas as páginas (…) a primeira coluna serve como
     nome da linha e a divisória entre eles tem que estar clara. pra todas as
     abas"*. Mesmo molde da Iluminação (`aba04.py`), com a razão escrita lá.
     A ÚLTIMA não leva: separador depois do último campo vira moldura, e a
     moldura do quadro já existe. */
  /* A LINHA É UM PSEUDO-ELEMENTO, e não a borda da célula — 30/08/2026.
     Como BORDA ela parava no padding da coluna e quebrava em cinco tracinhos;
     movendo o padding para as células a linha ficou inteira mas o desenho do
     controle perdeu 9px (a moldura tem `overflow:hidden` e o SVG cresce com a
     largura). O `::after` com margem negativa resolve os dois: ele sai do
     padding pelos dois lados e atravessa a coluna inteira, sem tocar em
     geometria nenhuma. As cinco colunas têm as mesmas alturas de linha, então
     os cinco segmentos nascem no mesmo y e leem como uma linha só. */
  .duas-colunas > div > *{position:relative}
  /* A LINHA É `::before` DA CÉLULA DE BAIXO, e não `::after` da de cima.
     Como `::after` ela era filha da moldura — e a moldura do DESENHO tem
     `overflow:hidden` para conter o SVG, então ela cortava a própria linha
     24px antes da divisa. A célula de baixo não recorta nada, e o traço
     cai no mesmo lugar: entre uma linha e a outra. */
  /* A LINHA DESCE MEIO PASSO E CAI NO MEIO DO VÃO — 31/08/2026, e é a cura que
     a Vibração já tinha e esta aba não. Pedido dela: *"lá precisa de respiro em
     tudo (…) as bordas das 3 páginas tão sobrando de um jeito feio e tão sem dar
     respiro."*

     MEDIDO ANTES DA CURA: o respiro das células desta aba era **0px/0px**, e a
     divisória ficava em `top:0` — encostada no conteúdo de cima, com o vão
     INTEIRO embaixo dela. O olho lê isso como linha grudada em cima e buraco
     embaixo, que é exatamente o "sobrando e sem respiro" que ela viu. A hipótese
     da lista dela estava certa: *"o problema não era só contraste — é respiro"*.

     CUSTO DE ALTURA: ZERO. `top:-var(--r-ar)` só muda DE QUE LADO da linha o vão
     está; a tabela mede o mesmo pixel. E `--r-ar` é o dono do passo (`--r-passo`
     é o dobro dele, por construção), então nenhuma das duas pode voltar a ficar
     torta sem que alguém mude as duas de uma vez — e elas são uma só. */
  .duas-colunas > div > *::before{content:'';position:absolute;
    top:calc(var(--r-ar) * -1);height:0;
    left:-13px;right:-12px;border-top:1px solid var(--rot-linha)}
  /* A CONTA DA MARGEM NEGATIVA: ela tem de cancelar o padding da coluna E o
     `gap` do grid, senão sobra um buraco do tamanho do vão. À direita são
     12 de padding + 12 de gap = 24; a ÚLTIMA coluna não tem vão depois
     dela, então volta a 12. A coluna de rótulos não tem padding: 0 e 12. */
  .duas-colunas > div:not(:last-child) > *::before{right:-24px}
  .duas-colunas > .rotulos > *::before{left:0;right:-12px}
  .duas-colunas > div > *:first-child::before,
  .duas-colunas > div > .vao-l2-r2::before{display:none}
  /* o `.sep-linha` (um elemento de 1px entre os blocos L2 e R2) SAIU: com a borda
     de célula acima ele desenhava a SEGUNDA linha, 10px abaixo da primeira. */

  .duas-colunas > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-nome) var(--r-modo) var(--r-pronto) var(--r-aj-e)
                       var(--r-sep) var(--r-modo) var(--r-pronto) var(--r-aj-d)
                       var(--r-acao);
  }
  /* a barra vertical entre blocos irmãos — pedido dela. Ela mora na COLUNA do
     controle, e não na de rótulos: é o rótulo que serve as quatro. */
  .duas-colunas .ctrl{border-left:1px solid var(--linha);padding:0 12px 0 13px}
  /* O RÓTULO OCUPA A ALTURA INTEIRA DA SUA LINHA, e o texto fica centrado
     dentro dele. Sem isto o rótulo da última linha acaba acima dos botões que
     ele nomeia, e a régua lê — com razão — um vão entre as colunas. */
  .duas-colunas .rotulos > *{display:flex;flex-direction:column;justify-content:center}
  /* O NOME DA LINHA ALINHA À DIREITA — 30/08/2026, pedido dela: *"no nome das
     linhas deixa alinhadas à direita. Todas"*. Encostado na divisa, o rótulo fica
     perto do que ele nomeia em vez de ficar perto da borda do quadro — é o que
     toda tabela de formulário faz, e é o que faz a coluna deixar de ler como
     lista solta e passar a ler como cabeçalho de linha. */
  /* ---------- A COLUNA DE RÓTULOS TEM DUAS TRILHAS ----------
     A da esquerda é do GLIFO que titula a seção; a da direita, dos rótulos de
     linha. Cada célula diz onde fica (`grid-area`), e nenhuma depende da ORDEM
     em que está no HTML — a ordem já quebrou esta grade uma vez, quando alguém
     tirou o `.vao-l2-r2` achando que era enfeite e "Gatilho direito" caiu na
     trilha de 1px. Com posição explícita, tirar um elemento deixa um buraco
     visível em vez de deslocar os oito seguintes em silêncio. */
  .duas-colunas .rotulos{grid-template-columns:var(--gl) 1fr;column-gap:var(--vao-gl)}
  /* TODOS QUALIFICADOS COM `.rotulos`, e a primeira volta não os qualificou:
     o `.vao-l2-r2` existe nas CINCO colunas (é ele que guarda a trilha de 1px
     entre o bloco do L2 e o do R2), e um `grid-area:5/1/6/3` solto o mandou
     ocupar três colunas dentro das colunas de CONTROLE — que têm uma só. A
     grade delas cresceu para três, o conteúdo saiu de registro e a aba nasceu
     com rolagem lateral. Pego na foto, na volta seguinte. */
  .duas-colunas .rotulos > .rot-linha-1{grid-area:1/2}
  .duas-colunas .rotulos > .g-l2{grid-area:2/1/5/2}
  .duas-colunas .rotulos > .rot-l2-1{grid-area:2/2}
  .duas-colunas .rotulos > .rot-l2-2{grid-area:3/2}
  .duas-colunas .rotulos > .rot-l2-3{grid-area:4/2}
  .duas-colunas .rotulos > .vao-l2-r2{grid-area:5/1/6/3}
  .duas-colunas .rotulos > .g-r2{grid-area:6/1/9/2}
  .duas-colunas .rotulos > .rot-r2-1{grid-area:6/2}
  .duas-colunas .rotulos > .rot-r2-2{grid-area:7/2}
  .duas-colunas .rotulos > .rot-r2-3{grid-area:8/2}
  /* O GLIFO FICA NO MEIO DA SEÇÃO — decisão dela, 31/08/2026: *"o l2 e o r2 tem
     que tá centralizado entre modo, efeito pronto e ajustes (verticalmente)."*

     EU TINHA ESCRITO O CONTRÁRIO AQUI, e o argumento era que cabeçalho encosta
     no que titula. Ela olhou a foto e decidiu o oposto — e a decisão é dela: um
     glifo que titula TRÊS linhas, preso na primeira, lê como se fosse só dela.
     No meio, ele pertence às três. */
  .duas-colunas .rotulos > .sec-glifo{display:flex;align-items:center;
             justify-content:center}
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
  .duas-colunas .rotulos > *{align-items:flex-start;text-align:left}
  .duas-colunas .rotulos .sec-rot{justify-content:flex-start}
  .duas-colunas .rotulos > * > *{flex:1;display:flex;align-items:center}
  /* OS DOIS GLIFOS NO MESMO x, E O ALINHAMENTO À DIREITA FICA — 31/08/2026.
     MEDIDO ANTES DA CURA, no Chrome e no WebKit2 (o motor que a janela usa),
     com os mesmos números: o L2 nascia em x=434,20 e o R2 em x=448,08 —
     **13,88px** de diferença, que é exatamente o quanto "esquerdo" (54,80px) é
     mais largo que "direito" (40,92px). Com o par glifo+palavra encostado na
     divisa direita, quem manda no x do glifo é a largura da PALAVRA, e as duas
     palavras não têm a mesma largura. Numa coluna de rótulos isso salta aos
     olhos, e ela viu na foto.
     A CURA NÃO DESFAZ O PEDIDO DELA: o par glifo+palavra deixa de ser uma caixa
     que ENCOLHE até o texto e passa a ocupar uma TRILHA da grade, larga o
     bastante para o maior dos dois. A coluna de rótulos ganha duas trilhas —
     [1fr elástico][o par] —, e a segunda é COMPARTILHADA pela linha do L2 e pela
     do R2: o navegador mede o par mais largo e dá a largura dele aos dois. É por
     isso que ninguém DIGITA "54,8px" aqui — um número desses ficaria errado
     calado no dia em que a palavra mudasse, e o desalinho voltaria sem aviso.
     Dentro da trilha, `space-between` prende o glifo na esquerda dela e a palavra
     na divisa direita: o glifo nasce em x=434,20 nas duas linhas e as duas
     palavras continuam acabando em x=532, com o resto da coluna igual.
     O QUE SOBRA VIRA VÃO ENTRE O GLIFO E A PALAVRA — 7px no L2 e 20,88 no R2 —,
     e isso é inevitável: palavras de larguras diferentes, encostadas à direita,
     com o glifo no mesmo x. O que se escolhe é onde a diferença aparece, e ela
     aparece no vão interno em vez de aparecer na coluna de glifos, que é o que
     ela viu.
     As linhas sem glifo atravessam as duas trilhas (`grid-column:1/-1`) e
     continuam encostadas na divisa — as divisórias medem os mesmos 404→532 de
     antes, conferido célula a célula.
     CUSTO DE ALTURA: ZERO, e é medido. As nove trilhas de linha são px FIXOS
     (`grid-template-rows`) e nada aqui as toca: o miolo continua com 544px de
     caixa para 544 de conteúdo, e a grade com os mesmos 444px.
     `display:contents` NO `.sec-rot` FOI TENTADO E DESCARTADO, e a razão é a
     régua: sem box, `getBoundingClientRect()` devolve 0 para as duas linhas de
     gatilho, e o "títulos de seção em x diferentes" do `regua.py` deixa de
     enxergá-las — passaria a dar verde sobre elas mesmo desalinhadas. A cura que
     desliga a régua em silêncio é o defeito desta casa, não a cura. Aqui o
     `.sec-rot` continua com box, e a régua lê nele o x REAL do glifo. */
  .duas-colunas .rotulos{grid-template-columns:1fr auto}
  .duas-colunas .rotulos > *{grid-column:1/-1}
  .duas-colunas .rotulos > *:has(.gl){display:grid;grid-template-columns:subgrid}
  .duas-colunas .rotulos > *:has(.gl) > .sec-rot{grid-column:2;
    justify-content:space-between}
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
           gap:7px}
  /* O RÓTULO DE UMA LISTA FICA NA LINHA DO PRIMEIRO ITEM, e não no meio da
     caixa. Centrado, o "Ajustes" caía entre a segunda e a terceira barra do P1 e
     ABAIXO da última barra do P3 — nomeava de baixo uma lista que começa em
     cima. Os 5px são o que põe a linha de 11px no centro da primeira barra
     (82px / 4 = 20,5px de altura por barra). */
  /* O `.no-topo` SAIU — 30/08/2026, pedido dela: *"centraliza os nomes dentro
     das distâncias verticais de cada linha"*. Ele prendia "Ajustes" no alto de
     uma célula de 92px, e o nome ficava a 40px do conteúdo que nomeia. Com o
     centro, ele cai na altura do bloco — e é a mesma regra que as outras seis
     linhas da coluna já seguiam. */
  /* "GATILHO / ESQUERDO" em duas linhas: com o glifo de 36px ao lado, a palavra
     inteira numa linha só pediria 154px de coluna de rótulo, e sobrariam 218px
     por controle — 2px a menos do que o efeito pronto mais longo precisa. */
  .sec-rot .duas{display:block;line-height:1.25}
  /* A LEGENDA NÃO É TÍTULO: sem isto ela herda o `text-transform:uppercase` do
     rótulo e sai em CAIXA ALTA. */
  /* `display:block` E NÃO A HERANÇA DO FLEX: a regra acima faz de todo filho de
     célula um contêiner flex, e num contêiner flex o `<b>` vira um ITEM ao lado
     do texto — a frase saía quebrada em duas colunas ("Guarda o par L2+R2 em" |
     "Meus efeitos"). Visto no navegador, 28/08. */
  .duas-colunas .rotulos .legenda{display:block;font-size:10.5px;line-height:1.4;
    color:var(--comment);text-transform:none;letter-spacing:0;padding-top:2px}

  /* O CHIP DO CONTROLE é o mesmo chip da fita, com a borda na cor do plástico —
     é como ela sabe de quem é a coluna (D-A-BORDA-E-A-IDENTIDADE-DA-PECA). Ele
     NÃO acende: aqui ele não é escolha, é cabeçalho. */
  /* O NOME DA COLUNA FICA CENTRADO — decisão dela, 31/08/2026: *"temos que
     centralizar o nome das colunas dos controles, ou então colocarmos os SVG de
     cada controle ao lado direito do nome."*

     ESCOLHI CENTRALIZAR, e a razão é orçamento: o chip mede 126px numa coluna de
     232, então centrá-lo custa ZERO. O SVG ao lado pediria altura que a linha do
     nome não tem — ela é `--r-nome`, 24px, e um desenho de 24px de altura é o
     mesmo caso das lâmpadas do jogador que ela mandou sair dos desenhos
     pequenos: não é desenho apagado, é desenho que não cabe. Para caber, a linha
     iria a 40px e comeria 16 dos 24px de folga que a grade tem.
     Se ela quiser o SVG, o preço está aqui e é dela a escolha. */
  /* `justify-items`, e não `align-items`: a célula é uma GRADE de uma coluna,
     e `align-items` mexe no eixo vertical — o chip continuou colado à
     esquerda e a foto mostrou. É o eixo errado, e a diferença só aparece
     olhando. */
  .duas-colunas .ctrl > *:first-child{justify-items:center;text-align:center}
  .duas-colunas .ctrl .chip{padding:0 8px;font-size:11px;height:22px;
    display:inline-flex;align-items:center;align-self:center;white-space:nowrap}
  /* O CHIP DO LUGAR VAZIO. A borda inteira se declara aqui, e não só a cor: o
     `.chip.plastico` usa `var(--plastico)`, e uma `var()` sem valor invalida a
     declaração TODA — a borda não fica cinza, ela deixa de existir. Medido na
     aba Controles no mesmo dia, com a foto mostrando dois lugares sem caixa. */
  .duas-colunas .ctrl .chip.vazio{border:1px solid var(--border-forte);
    color:var(--linha);background:transparent}

  /* O SELETOR DOS 19 MODOS. Era uma grade de 19 botões de 172px, e com quatro
     controles na tela ela não existe mais: a coluna de um controle mede 220px de
     conteúdo, e a grade pediria 19 fileiras — 566px numa coluna que tem 447px
     inteiros. Vira o mesmo `<select>` que a Navegação usa nos campos dela
     ("quando eu falei de drop in eu tava falando de todos os campos"), com as
     19 descrições no `title` de cada opção: nenhum modo e nenhuma frase saiu. */
  select.modo,select.pronto{
    width:100%;padding:0 9px;border-radius:6px;font-size:11.5px;
    font-family:inherit;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--texto-suave);cursor:pointer;
    height:var(--h-escolha);
  }
  select.modo{color:var(--fg);font-weight:600;border-color:var(--purple);
              background:var(--sel-bg)}
  select.modo:hover,select.pronto:hover{border-color:var(--comment)}

  /* AS BARRAS DE AJUSTE. Todas as linhas com a MESMA altura — o modo com duas
     barras ocupa as duas primeiras, e a primeira barra de toda coluna começa no
     mesmo y. O rótulo é o token `--rot` (92px), o mesmo de toda aba que tem
     campo; sobram 80px de trilho, que é o que a coluna de 220px permite. */
  .ajustes{display:grid}
  .barra{display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--texto-mudo)}
  .barra .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);
                 position:relative}
  .barra .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .barra .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--panel)}
  .barra .num{flex:0 0 32px;text-align:right;font-family:'JetBrains Mono',monospace;color:var(--fg)}
  .ajustes-vazio{grid-row:1 / span 2;font-size:11.5px;color:var(--comment);
                 font-style:italic;display:flex;align-items:center}
  /* O BOTÃO É UM POR CONTROLE, e da MESMA largura em todas as colunas. Era um
     só no pé do quadro, e com quatro controles um botão só não diz o que guarda:
     é a mesma ambiguidade que o recibo tinha antes de dizer em QUAL controle
     escreveu. Aqui ele fica na coluna de quem ele guarda. */
  .duas-colunas .ctrl .btn{width:100%;font-size:11.5px;padding:0 6px}
"""

MODOS = [
 ("Desligado", "Sem resistência nenhuma — o gatilho fica solto, como num controle comum."),
 ("Rígido", "Trava dura do começo ao fim do curso. Serve para freio de carro e para arma travada."),
 ("Rígido simples", "A mesma trava dura, com um só ponto de ajuste em vez de dez."),
 ("Pulso", "Um solavanco num ponto do curso e depois solta — o coice de um tiro único."),
 ("Pulso (curva A)", "Pulso com a subida mais suave: a força cresce antes do estalo."),
 ("Pulso (curva B)", "Pulso com a descida mais suave: o estalo vem e a força cai devagar."),
 ("Resistência", "Peso constante do começo ao fim, sem trava — remada, alavanca, arco sendo puxado."),
 ("Arco de flecha", "Fica cada vez mais pesado até o fim do curso, e então solta de uma vez."),
 ("Galope", "Batidas ritmadas enquanto o gatilho está apertado — cavalo correndo, motor pegando."),
 ("Arma semi-automática", "Uma trava, um estalo, e o gatilho volta. Um tiro por aperto."),
 ("Arma automática", "Vibra continuamente enquanto está apertado — rajada."),
 ("Metralhadora", "Batidas rápidas e fortes enquanto apertado. É o padrão do Estilo FPS."),
 ("Ponto duro", "Solto até certo ponto do curso, e daí em diante duro. O ponto é ajustável."),
 ("Disparo", "Trava, solta no estalo e fica leve até o fim — espingarda."),
 ("Vibração", "Treme o gatilho na frequência escolhida, sem opor força."),
 ("Rampa de força", "A força sobe em linha reta do início ao fim do curso."),
 ("Curva de força", "Você desenha a força em dez posições do curso, uma por uma."),
 ("Vibração por posição", "Treme só na faixa do curso que você marcar."),
 ("Montar do zero", "As dez posições em branco, para desenhar a curva do jeito que a sua mão pedir."),
]

PRONTOS = ["— Nenhum —", "Rampa crescente", "Rampa decrescente", "Plateau central",
           "Stop hard", "Stop macio"]
MEUS = ["Recuo do MK — pesado no fim", "Freio do carro — trava tardia"]

# ---------------------------------------------------------------------------
# A CENA. Um mockup mostra um estado, e este foi escolhido para ENSINAR: os
# quatro controles trazem 4, 3, 2 e nenhuma barra de ajuste, que é o que prova
# no desenho que a caixa de ajustes é do MODO e não do controle.
#
# O P1 é LITERAL — é a cena que ela aprovou em 27/08 ("aba gatilhos perfeita"),
# com os mesmos quatro números. Ela não sai do `trigger_specs.py` de propósito:
# o produto diz que Metralhadora tem SEIS parâmetros (Início, Fim, Amplitude A,
# Amplitude B, Frequência, Período) e o mockup aprovado desenha quatro com
# outros nomes. A divergência é REAL e está declarada na legenda; corrigi-la
# seria mudar o que ela aprovou, e isto não é o que a decisão de 28/08 pede.
#
# Os outros três saem do produto: o rótulo e a faixa vêm de `trigger_specs`, e a
# porcentagem do trilho é DERIVADA da faixa. Se o produto mudar um nome, esta
# aba reprova alto em vez de desenhar um trilho com a régua errada.
# ---------------------------------------------------------------------------
LITERAL_P1 = {
    "Metralhadora": [("Força", 78, "7"), ("Frequência", 44, "4"),
                     ("Início do curso", 25, "25"), ("Fim do curso", 90, "230")],
    "Arco de flecha": [("Força no fim", 66, "6"), ("Início do curso", 15, "15")],
}

CENA = {
    "p1": {"esq": ("Metralhadora", MEUS[0], None),
           "dir": ("Arco de flecha", MEUS[0], None)},
    "p2": {"esq": ("Arma semi-automática", "Stop hard", [("Início", 3), ("Fim", 6), ("Força", 5)]),
           "dir": ("Rígido", PRONTOS[0], [("Posição", 5), ("Força", 200)])},
    # O P3 E O P4 SÃO LUGAR VAZIO — decisão dela, 31/08/2026: *"os demais 3 e o 4
    # ficam lá com os espaços mas tudo com Desligado e Nenhum, fora a borda do P1
    # e P2."* A coluna continua na tela (é o "ficam lá com os espaços"); o que
    # sai é o ESTADO, porque não há controle para tê-lo.
    #
    # E ISSO DEVOLVE ALTURA, que é o que a aba mais precisa: a linha de ajustes
    # do R2 valia o MAIOR modo que estivesse nela, e o maior era a Vibração do
    # P3, com três barras. Sem ela, o R2 passa a valer duas — 23px de volta para
    # o respiro que ela pediu, sem tirar nada de quem está conectado.
    "p3": {"esq": ("Desligado", PRONTOS[0], []),
           "dir": ("Desligado", PRONTOS[0], [])},
    "p4": {"esq": ("Desligado", PRONTOS[0], []),
           "dir": ("Desligado", PRONTOS[0], [])},
}


def barras(modo, escolha):
    """As barras de um modo — do produto, com a porcentagem DERIVADA da faixa."""
    if escolha is None:                       # o P1, literal e aprovado por ela
        return LITERAL_P1[modo]
    fora = [n for n, _ in escolha if n not in SPEC.get(modo, {})]
    if fora:
        raise SystemExit(
            f"ERRO: o modo {modo!r} não tem o(s) parâmetro(s) {fora} em "
            f"app/actions/trigger_specs.py — a cena da aba 03 ficou velha.")
    saida = []
    for nome, valor in escolha:
        q = SPEC[modo][nome]
        pct = round((valor - q.min_value) / (q.max_value - q.min_value) * 100)
        # "Início" e "Fim" viram "Início do curso" e "Fim do curso": é o
        # vocabulário que ela já leu e aprovou nesta aba, e o rótulo cabe nos
        # 92px do `--rot` (medido: 82px e 68px).
        rot = {"Início": "Início do curso", "Fim": "Fim do curso"}.get(nome, nome)
        saida.append((rot, pct, str(valor)))
    return saida


# ---------------------------------------------------------------------------
# O `value` DE CADA OPÇÃO É O CONTRATO, e o texto é o RÓTULO. Os dois campos, os
# dois donos — a mesma separação que o `trigger_specs.py` faz entre `name` e
# `label`, escrita ali com todas as letras: o `name` está serializado no perfil
# em disco (`triggers.left.mode`), no IPC (`trigger.set`) e no DSX; o `label` é
# só texto de tela.
#
# ATÉ HOJE ESTA PÁGINA SÓ TINHA O RÓTULO, e por isso o clique não tinha o que
# mandar ao daemon: `trigger.set` quer `Rigid`, e a opção dizia `Rígido`.
#
# E O `value` NÃO SE DIGITA — ele sai do `PRESETS`, PELA ORDEM. As duas listas
# têm 19 entradas na mesma sequência (Desligado=Off … Montar do zero=Custom), e
# casá-las por RÓTULO seria casar por um campo que já divergiu: `MODOS` diz
# "Arco de flecha" e o produto diz "Arco de flecha (Bow)"; `MODOS` diz "Disparo"
# e o produto diz "Disparo (Weapon)" — as duas decisões dela de 07/08 que esta
# página não acompanhou. A ordem é o que as duas listas têm em comum, e a guarda
# abaixo reprova alto no dia em que uma delas mudar de tamanho.
if len(MODOS) != len(PRESETS):
    raise SystemExit(
        f"ERRO: a aba desenha {len(MODOS)} modos e o produto tem {len(PRESETS)} "
        f"(`app/actions/trigger_specs.PRESETS`). O casamento é PELA ORDEM — com "
        f"tamanhos diferentes, o `value` de cada opção sairia trocado, e o clique "
        f"mandaria ao daemon o modo errado sem nada na tela dizendo.")
CHAVE_DO_MODO = {rot: spec.name for (rot, _), spec in zip(MODOS, PRESETS, strict=True)}

# O "EFEITO PRONTO" TEM DONO NO PRODUTO, e o dono é `profiles/trigger_presets.py`:
# os cinco nomes desta lista são, letra por letra, cinco dos seis
# `FEEDBACK_POSITION_LABELS`. Eles não são enfeite de mockup — cada um resolve
# para dez intensidades de 0 a 8, que é o que o modo "Curva de força"
# (`MultiPositionFeedback`) manda ao controle.
#
# `— Nenhum —` VIRA `custom`, e não uma palavra inventada: `custom` é o token do
# próprio produto para "nenhuma curva pronta, os valores são os que estão aí"
# (`FEEDBACK_POSITION_LABELS["custom"]`, e o `_populate_preset_combo` da GUI
# estável abre nele). Um `""` aqui obrigaria a tela a ter um sexto token só dela.
_PRONTO_POR_ROTULO = {rot: chave for chave, rot in FEEDBACK_POSITION_LABELS.items()}
CHAVE_DO_PRONTO = {PRONTOS[0]: "custom"}
for _rot in PRONTOS[1:]:
    if _rot not in _PRONTO_POR_ROTULO:
        raise SystemExit(
            f"ERRO: o efeito pronto {_rot!r} não existe em "
            f"`profiles/trigger_presets.FEEDBACK_POSITION_LABELS`. Ou o produto "
            f"perdeu a curva, ou esta aba oferece uma que ninguém sabe aplicar — "
            f"e a segunda é um botão que responde calado.")
    CHAVE_DO_PRONTO[_rot] = _PRONTO_POR_ROTULO[_rot]
# OS "MEUS EFEITOS" NASCEM SEM CHAVE, e o vazio é a afirmação: não há, em todo o
# `src/`, onde guardar um efeito com nome. Eles ficam no desenho porque ela os
# aprovou; o `value=""` é o que faz o gesto RECUSAR DIZENDO em vez de aplicar
# outra coisa no lugar.
for _rot in MEUS:
    CHAVE_DO_PRONTO[_rot] = ""


def opcoes_modo(escolhido):
    return "\n".join(
        f'                <option value="{CHAVE_DO_MODO[n]}"'
        f'{" selected" if n == escolhido else ""} title="{d}">{n}</option>'
        for n, d in MODOS)


def _op_pronto(n, escolhido):
    return (f'                <option value="{CHAVE_DO_PRONTO[n]}"'
            f'{" selected" if n == escolhido else ""}>{n}</option>')


def opcoes_pronto(escolhido):
    fora = [_op_pronto(n, escolhido) for n in PRONTOS]
    dentro = [_op_pronto(n, escolhido) for n in MEUS]
    return ("\n".join(fora) + '\n                <option disabled>──── Meus efeitos ────</option>\n'
            + "\n".join(dentro))


def bloco(lado, sigla, modo, pronto, ajustes):
    """`sigla` é "e" ou "d": a linha de ajustes do L2 e a do R2 têm
    alturas diferentes, porque cada uma vale o maior modo que está NELA."""
    if ajustes:
        aj = "\n".join(
            f'''            <div class="barra" data-ajuste="{sigla}-{i}">
              <span class="nome" data-campo="aj-nome-{sigla}-{i}">{n}</span>
              <span class="trilho"><span class="cheio" data-campo="aj-pct-{sigla}-{i}" style="width:{p}%"></span></span>
              <span class="num" data-campo="aj-val-{sigla}-{i}">{v}</span>
            </div>''' for i, (n, p, v) in enumerate(ajustes))
    else:
        aj = '            <div class="ajustes-vazio">Este modo não tem o que ajustar.</div>'
    # O ENDEREÇO DE PINTURA DO MODO É A **CHAVE**, e não o rótulo — e junto vem o
    # `data-hef-alvo="valor"`. Os dois consertam o mesmo defeito, medido em
    # 01/09/2026 lendo o `escrever()` do piloto (`hefesto_vivo.py:100-115`): sem
    # `data-hef-alvo`, o alvo padrão é `texto`, e `select.textContent = "Rígido"`
    # **apaga as 19 opções** e põe um nó de texto no lugar. A primeira pintura
    # destruiria o campo de escolha desta aba, nas cinco colunas.
    # Com `valor`, o piloto faz `select.value = t` — e é por isso que o endereço
    # tem de ser `modo-chave-*` (`Rigid`), que é o que o `value` das opções
    # carrega. O `modo-*` (o rótulo "Rígido") continua saindo do pacote porque
    # `tests/unit/test_o_perfil_chega_na_tela.py:125` o cobra, mas nenhum
    # elemento o lê: o que casa com a opção é a chave.
    return f'''          <div>
            <select class="modo" data-gesto="modo" data-campo="modo-chave-{sigla}"
                    data-hef-alvo="valor" data-lado="{sigla}"
                    title="Gatilho {lado} — os 19 modos, com a descrição de cada um">
{opcoes_modo(modo)}
            </select>
          </div>
          <div>
            <select class="pronto" data-gesto="pronto" data-campo="pronto-{sigla}"
                    data-hef-alvo="valor" data-lado="{sigla}"
                    title="Efeito pronto do gatilho {lado}">
{opcoes_pronto(pronto)}
            </select>
          </div>
          <div class="ajustes {sigla}">
{aj}
          </div>'''


def _chip(c, rot):
    """O cabeçalho da coluna. A BORDA DE COR SÓ SAI PARA QUEM ESTÁ NA MESA.

    Decisão dela, 31/08/2026: *"os demais 3 e o 4 ficam lá com os espaços mas
    tudo com Desligado e Nenhum, **fora a borda do P1 e P2**."*

    A borda desta aba é o `D-A-BORDA-E-A-IDENTIDADE-DA-PECA`: ela é como se sabe
    de quem é a coluna. Num lugar vazio não há de quem — e pintar a cor de um
    plástico que não está na mesa é dizer que ele está.
    """
    if not c.get("conectado", True):
        # O NOME DO PLÁSTICO NÃO VAI PARA A TELA — decisão dela, 31/08/2026: *"na
        # parte do nome do P3 e do P4 colocar algo como Desconectado e não os
        # controles mockados."*
        #
        # A `MESA` sabe que o P3 é um Galactic Purple, e ELA não deve saber: o
        # lugar está vazio, e escrever ali o nome de um controle que não está na
        # mesa é a mesma mentira que a borda de cor era. O que a tela precisa
        # dizer é a POSIÇÃO (P3, P4) e o ESTADO — e é só isso que sobra.
        return (f'<span class="chip vazio" title="Nenhum controle neste lugar.">'
                f'P{c["jogador"]} <span class="pt">•</span> Desconectado</span>')
    return (f'<span class="chip plastico" style="--plastico:{cor_da_zona(c["cor"])}"'
            f' title="{c["nome"]} — a borda é a cor do plástico">{rot}</span>')


def coluna(c):
    """Uma coluna = UM controle da `MESA`. A aba não sabe contar até quatro."""
    cena = CENA[c["pref"]]
    esq = bloco("esquerdo", "e", *cena["esq"][:2], barras(*cena["esq"][::2]))
    dire = bloco("direito", "d", *cena["dir"][:2], barras(*cena["dir"][::2]))
    rot = (f'P{c["jogador"]} <span class="pt">•</span> {c["nome"]}'
           f' <span class="pt">•</span> {c["via"]}')
    # O VALOR SAI DA F-STRING, e a razão é que ele VAZAVA PARA A TELA. A palavra
    # do atributo faz o portão de acentuação reprovar, e o marcador que a isenta
    # tem de ficar na MESMA linha física — que, aqui, era DENTRO da f-string.
    # Resultado: as quatro colunas da aba Gatilhos nasciam com `  # noqa-acento`
    # como TEXTO, logo depois da `<div class="ctrl">`, visível para quem abrisse
    # a aba. Medido em 01/09/2026, no dia em que os dez geradores voltaram a
    # rodar; ninguém tinha visto porque ninguém os rodava.
    conectado = "sim" if c.get("conectado", True) else "nao"  # (noqa-acento) valor
    return f'''        <div class="ctrl" data-controle="{c.get("uniq") or c["pref"]}"
             data-conectado="{conectado}">
          <div>{_chip(c, rot)}</div>
{esq}
<!-- ESTE ELEMENTO É CÉLULA DA GRADE, não enfeite. Ele ocupa a trilha de
               1px que separa o bloco do L2 do bloco do R2 (`grid-template-rows`
               em `.duas-colunas > div`). Tirei-o em 30/08 pensando que era só um
               traço, e "Gatilho direito" caiu nessa trilha e nasceu com **1px de
               altura** — as cinco colunas saíram de registro e as divisórias
               passaram a cortar o conteúdo de P3 e P4 no meio. O traço VISÍVEL
               agora vem da borda de célula (`--rot-linha`); esta célula só guarda
               o lugar, e por isso não leva borda. -->
          <div class="vao-l2-r2"></div>
{dire}
          <div><button class="btn roxo" data-gesto="guardar" data-hef-forma="@controle">Guardar esse efeito</button></div>
        </div>'''


# ---------------------------------------------------------------------------
# AS NOVE LINHAS DA GRADE, e a altura da coluna é a SOMA delas.
#
# A LINHA DE AJUSTES SAI DA CENA, e não de um número escolhido no olho: ela vale
# o MAIOR modo que está NELA. Quem é esse modo MUDA com a cena — em 31/08 o P3
# virou lugar vazio e o R2 deixou de valer a Vibração dele —, e por isso nem o
# número nem o NOME se digitam: os dois saem de `_dono_da_linha()`, logo abaixo.
# Com um número só para as duas, a linha do R2 herdava a
# altura do L2 e as três colunas de dois ajustes ficavam com uma barra de vão em
# cima do botão. É a regra dela: a cura do vão é na ALTURA.
#
# O TETO É MEDIDO: o miolo tem 508px úteis (542 de caixa menos os 16+18 de
# padding), e o quadro gasta 28 de cabeçalho, 24 de padding e 2 de borda — sobram
# 454px para a grade. O que passar disso rola por dentro, e quadro que rola é
# conteúdo que ninguém sabe que existe.
# ---------------------------------------------------------------------------
ALT_BARRA = 23   # uma barra: 11,5px de rótulo e 5 de trilho
#: O PASSO ENTRE LINHAS — 10 até 31/08, 14 desde então. Pedido dela:
#: *"lá precisa de respiro em tudo (…) fora o respiro entre as linhas na questão
#: do espaço vertical."*
#:
#: E ELE FOI PAGO, não raspado: os 4px a mais em oito vãos custam 32px, e os 32
#: vieram de duas coisas que ela mesma decidiu no mesmo turno — o P3 e o P4
#: desligados devolveram 23 (a linha de ajustes do R2 valia a Vibração do P3, com
#: três barras, e passou a valer duas), e a janela de 777px devolveu os outros.
#: É a regra desta casa: a cura do vão é na ALTURA, e a altura tem dono.
R_NOME, R_MODO, R_PRONTO, R_SEP, R_ACAO = 24, 36, 36, 1, 34
#: O RESPIRO É O DONO, e o passo é o DOBRO dele — a mesma construção da Vibração
#: (`aba05.py`, 30/08). Assim a divisória cai no MEIO do vão e todo conteúdo
#: centrado na célula fica centrado na FAIXA. Escrever os dois à mão é como a
#: Vibração ficou torta antes de 30/08.
R_AR = 7
R_PASSO = R_AR * 2
N_ESQ = max(len(barras(*CENA[c["pref"]]["esq"][::2])) for c in MESA)
N_DIR = max(len(barras(*CENA[c["pref"]]["dir"][::2])) for c in MESA)
R_AJ_E, R_AJ_D = N_ESQ * ALT_BARRA, N_DIR * ALT_BARRA


def _dono_da_linha(lado, n):
    """Quem manda na altura da linha de ajustes — LIDO da cena, nunca digitado.

    A legenda dizia *"3 no R2 (a Vibração do P3)"*, e em 31/08 o P3 virou lugar
    vazio por decisão dela: o número caiu para 2 (o gerador o calcula) e o NOME
    continuou apontando um modo que saiu da tela. Metade certa, metade mentindo
    — que é o pior estado de uma legenda, porque a metade certa a faz parecer
    conferida. Agora as duas metades saem do mesmo lugar.
    """
    donos = [(c, CENA[c["pref"]][lado][0]) for c in MESA
             if len(barras(*CENA[c["pref"]][lado][::2])) == n]
    if not donos:
        raise SystemExit(f"ERRO: nenhum modo do {lado} tem {n} barra(s) — a "
                         f"legenda ficaria sem dono para citar.")
    c, modo = donos[0]
    # SEM ARTIGO, e não é estilo: o artigo obriga a saber o GÊNERO de 19 nomes de
    # modo, e a primeira versão escreveu *"a Arco de flecha do P1"*. Um gerador
    # que precisa concordar em gênero com dado que ele lê ou carrega uma tabela
    # de gêneros — outra coisa para envelhecer calada — ou erra o português na
    # primeira troca de cena. A vírgula resolve as duas.
    return f'{modo}, do P{c["jogador"]}'


DONO_ESQ, DONO_DIR = _dono_da_linha("esq", N_ESQ), _dono_da_linha("dir", N_DIR)
LINHAS = [R_NOME, R_MODO, R_PRONTO, R_AJ_E, R_SEP, R_MODO, R_PRONTO, R_AJ_D, R_ACAO]
ALT_COLUNA = sum(LINHAS) + (len(LINHAS) - 1) * R_PASSO

#: A largura da coluna de rótulos VEM DE `medidas.py`, que é o dono dela nas
#: TRÊS abas que têm essa coluna. Ela era 128 (o par glifo+palavra espremido numa
#: trilha só) e virou 138 quando o glifo ganhou trilha própria — e 138 não batia
#: com os 132 da Iluminação e da Vibração. Ela viu: *"tem algo que deixa estranho
#: essa área da primeira coluna."*
LARG_ROT = monta_.larg_rotulos("03-gatilhos", com_glifo=True)
#: O TETO DA GRADE, MEDIDO NO CHROME — 477px com a janela de 777.
#:
#: ELE ERA 454, e 454 era o número da janela de 757px. Com os 777 que ela pediu
#: em 31/08 ele ficou pequeno demais: teria reprovado um desenho que cabe.
#:
#: E EU TENTEI DERIVÁ-LO DA SOMA DAS PARTES ANTES DE MEDIR — cabeçalho + tira +
#: rodapé + paddings + cromo do quadro — e deu **528**, 51px a mais do que a
#: tela aguenta. Uma conta de layout que não passa pelo navegador erra por
#: margens que ninguém lembra de somar, e um teto folgado demais é pior que
#: nenhum: ele deixa passar a aba que rola.
#:
#: O COMANDO QUE O MEDE, e ele é reproduzível — empurra a coluna 2px por vez e
#: acha onde o `.miolo` começa a rolar:
#:
#:     pg.add_style_tag(content=f".duas-colunas > div{{padding-bottom:{n}px}}")
#:     m.scrollHeight > m.clientHeight + 1
#:
#: Última coluna que coube: 477px. A primeira que rolou: 479px.
TETO_DA_GRADE = 477
if ALT_COLUNA > TETO_DA_GRADE:
    raise SystemExit(f"ERRO: a coluna pede {ALT_COLUNA}px e a grade tem "
                     f"{TETO_DA_GRADE}px — o quadro passaria a rolar por dentro.")

CSS_DA_CENA = f"""
  .duas-colunas{{
    --r-nome:{R_NOME}px;--r-modo:{R_MODO}px;--r-pronto:{R_PRONTO}px;
    --r-aj-e:{R_AJ_E}px;--r-sep:{R_SEP}px;--r-aj-d:{R_AJ_D}px;
    --r-acao:{R_ACAO}px;--r-ar:{R_AR}px;--r-passo:calc(var(--r-ar) * 2);
    /* O TAMANHO DO GLIFO E A LARGURA DA COLUNA DE RÓTULOS saem do Python, do
       mesmo lugar que o `glifo(tam=GL)` lê. Digitados no CSS, os dois divergem
       no dia em que alguém mudar um só — é a cicatriz das cores do plástico e a
       do padrão das lâmpadas. */
    --gl:{GL}px; --larg-rot:{LARG_ROT}px; --gap-col:{monta_.GAP_DAS_COLUNAS}px; --vao-gl:{monta_.VAO_DO_GLIFO}px;
  }}
  .ajustes.e{{grid-template-rows:repeat({N_ESQ},1fr)}}
  .ajustes.d{{grid-template-rows:repeat({N_DIR},1fr)}}
"""

# O GLIFO ANTES DA PALAVRA, e é a gramática das vizinhas: a `aba08` escreve
# `{glifo("mic", tam=16)} Microfone e botões`, a `aba06` monta `glifo + nome` no
# `_um()`, e a `aba02` põe o glifo sozinho no botão. Aqui é o mesmo molde, com o
# `<title>` do SVG dizendo o nome da peça (L2 / R2) — nunca um `title=` no
# `<svg>`, que o navegador ignora (`monta.glifo`, docstring).
#
# ELES JÁ TINHAM SIDO ESCRITOS, E CAÍRAM CALADOS. Estavam nestas duas linhas até
# 48b4e1a2; a leva das divisórias de 30/08 reescreveu o bloco `ROTULOS` inteiro e
# levou os dois `glifo()` junto — sem nota, sem pedido, e com a legenda da aba
# continuando a prometê-los ("Os glifos são os do mapa"). Sobreviveram o `GL = 36`
# com a conta paga e o `import glifo` na linha 9, os dois sem um único chamador:
# é a assinatura do `a-casa-sabe-e-o-produto-nao-faz`. Devolvidos em 31/08/2026,
# a pedido dela: *"abas como gatilhos tinhamos os svgs do r2 e l2, isso tem que
# voltar."*
#
# CUSTO DE ALTURA: ZERO, e é medido. As nove trilhas de `.duas-colunas > div`
# são px FIXOS (`grid-template-rows`), então o glifo de 36px entra na trilha
# `--r-modo`, que também é 36px — a coluna continua em ALT_COLUNA px e o miolo
# não rola. Quem cresce é a LARGURA da coluna de rótulos, e ela já foi paga: os
# 128px do `grid-template-columns` e o "Gatilho / esquerdo" em duas linhas
# existem por causa deste glifo — está escrito no comentário do `.sec-rot .duas`.
ROTULOS = f'''        <div class="rotulos">
          <div class="rot-linha-1"><span class="sec-rot">Controle</span></div>

          <!-- O L2 E O R2 TITULAM A SEÇÃO — decisão dela, 31/08/2026: *"o L2 e o
               R2 deveriam controlar a seção e não ficar do lado esquerdo de
               gatilho esquerdo ou direito."*

               ATÉ HOJE o glifo era um adorno colado no rótulo da PRIMEIRA linha
               da seção (`[L2] Gatilho esquerdo`), e as outras duas linhas dela —
               Efeito pronto e Ajustes — não tinham dono visível. Ele agora ocupa
               uma trilha própria e ATRAVESSA as três (`grid-row: span 3`): é o
               cabeçalho da seção, e as três linhas ficam claramente debaixo dele.

               "GATILHO ESQUERDO" SAIU, e não é perda: o glifo L2 já diz qual
               gatilho é — a palavra repetia o desenho. O que sobra em cada linha
               é o que ela nomeia: Modo, Efeito pronto, Ajustes.

               CUSTO DE ALTURA: ZERO. A célula ocupa trilhas que já existiam. -->
          <div class="sec-glifo g-l2">{glifo("l2", tam=GL)}</div>
          <div class="rot-l2-1"><span class="sec-rot">Modo</span></div>
          <div class="rot-l2-2"><span class="sec-rot">Efeito pronto</span></div>
          <div class="rot-l2-3 no-topo"><span class="sec-rot">Ajustes</span></div>

<!-- ESTE ELEMENTO É CÉLULA DA GRADE, não enfeite. Ele ocupa a trilha de
               1px que separa o bloco do L2 do bloco do R2 (`grid-template-rows`
               em `.duas-colunas > div`). Tirei-o em 30/08 pensando que era só um
               traço, e "Gatilho direito" caiu nessa trilha e nasceu com **1px de
               altura** — as cinco colunas saíram de registro e as divisórias
               passaram a cortar o conteúdo de P3 e P4 no meio. O traço VISÍVEL
               agora vem da borda de célula (`--rot-linha`); esta célula só guarda
               o lugar, e por isso não leva borda. -->
          <div class="vao-l2-r2"></div>

          <div class="sec-glifo g-r2">{glifo("r2", tam=GL)}</div>
          <div class="rot-r2-1"><span class="sec-rot">Modo</span></div>
          <div class="rot-r2-2"><span class="sec-rot">Efeito pronto</span></div>
          <div class="rot-r2-3 no-topo"><span class="sec-rot">Ajustes</span></div>
        </div>'''

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Seleção de Gatilho</span>
        <span class="ajuda">?<span class="dica">
          O L2 e o R2 do DualSense têm um motorzinho dentro que <b>opõe força à sua mão</b>.
          É o que faz um gatilho parecer o freio de um carro e outro parecer uma metralhadora.<br><br>
          <b>Uma coluna por controle, e os {len(MESA)} ao mesmo tempo.</b> Cada coluna escreve no
          controle do chip que a encabeça — não há o que escolher lá em cima, e é por isso que a
          fita está esmaecida. Escolher um modo já manda o efeito para <b>aquele</b> controle, e
          quem está com ele na mão sente na hora.<br><br>
          <b>A descrição de cada modo está na lista</b> — passe o mouse por ela antes de soltar
          o botão, porque soltar já manda.<br><br>
          <b>Esta tela mostra o que o Hefesto escreveu no gatilho.</b> A confirmação é o que
          você sente na mão — é assim que se prova um efeito adaptativo.
        </span></span>
      </div>
      <div class="quadro-corpo">
        <div class="duas-colunas">
{ROTULOS}
{chr(10).join(coluna(c) for c in MESA)}
        </div>
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>O que a decisão de 28/08 mudou aqui</h2>
  <ul>
    <li><b>Os {len(MESA)} controles lado a lado, sempre visíveis</b> — uma coluna por controle da
        <code>monta.MESA</code>, na mesma ordem dos chips da fita. A palavra "quatro" não está
        escrita em laço nenhum: no dia em que a mesa tiver três ou cinco, esta aba acompanha
        sozinha.</li>
    <li><b>A fita ficou esmaecida</b> — cada coluna é o seu próprio alvo, e um chip que não
        aponta para nada seria escolha falsa. Quem diz de quem é a coluna é o <b>chip com a borda
        na cor do plástico</b>, no alto dela.</li>
    <li><b>O recibo saiu do pé do quadro e virou a própria coluna.</b> Ele existia para dizer
        <span class="marca">em QUAL controle escreveu</span>; com uma coluna por controle, a
        pergunta já não se faz.</li>
    <li><b>"Guardar esse efeito" é um por controle</b>, e não um só no pé do quadro — um botão
        único não diria qual dos {len(MESA)} pares ele guarda, que é exatamente a ambiguidade que
        o recibo foi criado para matar. Continua sendo o <b>único</b> botão da aba.</li>
  </ul>

  <h2>O que teve de mudar de forma para caber</h2>
  <ul>
    <li><b>A grade dos 19 modos virou um campo de escolha.</b> Medido: com {len(MESA)} colunas,
        cada controle tem <b>220px</b> de conteúdo e <b>{ALT_COLUNA}px</b> de altura inteira. Em
        220px a grade não cabe em duas colunas — <span class="marca">Arma semi-automática</span>
        mede 132px em negrito e o botão teria 108 —, então seria UMA: 19 fileiras de 36px com 4 de
        vão, <b>{19 * 36 + 18 * 4}px</b>, só para um dos dois gatilhos. Os 19 modos e as 19
        descrições continuam todos aqui: cada opção carrega a sua no <code>title</code>. É o mesmo
        campo que a Navegação usa, e por pedido seu — <span class="marca">"quando eu falei de drop
        in eu tava falando de todos os campos"</span>.</li>
    <li><b>"Efeito pronto" e "Ajustes" viraram rótulo de LINHA</b>, na coluna da esquerda. Repetidos
        dentro de cada controle seriam oito rótulos dizendo a mesma coisa, e o mais longo deles
        não caberia ao lado do campo.</li>
    <li><b>A caixa de ajustes vale o maior modo que está na LINHA</b> — {N_ESQ} barras no L2 ({DONO_ESQ}) e
        {N_DIR} no R2 ({DONO_DIR}). O modo com duas barras ocupa as duas
        primeiras, e a primeira barra de todas as colunas começa no mesmo y. A altura é da linha, e
        as cinco colunas a dividem: é o que as faz acabarem no mesmo y sem
        <code>space-between</code>. Uma altura só para as duas linhas daria ao R2 a altura do L2, e
        as três colunas de dois ajustes ganhariam uma barra de vão em cima do botão.</li>
  </ul>

  <h2>O que ficou apertado, e está dito</h2>
  <ul>
    <li><b>A caixa de ajustes cabe {N_ESQ} barras.</b> O produto
        (<code>app/actions/trigger_specs.py</code>) diz que cinco dos 19 modos pedem mais:
        <span class="marca">Galope</span> 5, <span class="marca">Metralhadora</span> 6,
        <span class="marca">Montar do zero</span> 8, <span class="marca">Curva de força</span> 10 e
        <span class="marca">Vibração por posição</span> 10. Dez barras pedem {10 * ALT_BARRA}px
        numa linha, e as duas somariam <b>{20 * ALT_BARRA}px</b> — mais do que a coluna inteira tem
        ({ALT_COLUNA}px, com o chip, os campos e o botão dentro). <b>Não cortei nada</b>: os cinco modos
        continuam na lista. O que falta decidir é onde as dez posições se desenham —
        provavelmente uma janela própria, que é o que o nome <span class="marca">Montar do zero</span>
        já promete.</li>
    <li><b>Divergência real, e ela é mais velha que esta aba:</b> o P1 mostra
        <span class="marca">Metralhadora</span> com quatro barras (Força, Frequência, Início do
        curso, Fim do curso) e o produto lista <b>seis</b> com outros nomes (Início, Fim, Amplitude
        A, Amplitude B, Frequência, Período). O P1 é a cena que você aprovou em 27/08 e ficou
        literal; os outros três saem do <code>trigger_specs.py</code>, com a porcentagem do trilho
        DERIVADA da faixa de cada parâmetro. <b>Uma das duas está errada</b> — e a escolha é
        sua.</li>
    <li><b>O trilho das barras mede 80px</b>, contra 109 na tela de dois. É o que sobra de 220px
        depois dos 92px do rótulo (o token <code>--rot</code>, igual em toda aba) e dos 32 do
        número.</li>
  </ul>

  <h2>O que NÃO mudou</h2>
  <ul>
    <li>Os <b>19 modos</b> e seus textos, o <b>efeito pronto</b> com "Meus efeitos" na mesma lista,
        as <b>barras de ajuste</b>, o <b>título "Seleção de Gatilho"</b> e o botão único.</li>
    <li><b>Os glifos são os do mapa</b> — <code>assets/glyphs/l2.svg</code> e <code>r2.svg</code>,
        a 36px, que é o piso medido para a palavra dentro deles chegar aos 10px de tipo desta casa.</li>
    <li><b>A dispensa da régua deixou de ser necessária.</b> Ela existia porque "modos diferentes têm
        números de barra diferentes" e igualar a altura seria inventar espaço. Agora quem iguala é a
        LINHA, compartilhada pelas cinco colunas — não há preenchimento inventado dentro de coluna
        nenhuma, e a régua fecha sem dispensa.</li>
  </ul>
</div>

</body>
</html>
'''

def _conferir(doc):
    """As decisões dela de 31/08 nesta aba, conferidas NA SAÍDA.

    Só o miolo e sem comentário HTML — a régua da aba Jogar nasceu errada duas
    vezes por casar token na legenda e no próprio comentário que a explicava.
    """
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    # 1. O L2 E O R2 TITULAM A SEÇÃO — *"deveriam controlar a seção e não ficar
    #    do lado esquerdo de gatilho esquerdo ou direito."*
    for g in ("g-l2", "g-r2"):
        exigir(f'class="sec-glifo {g}"' in corpo, f"o glifo {g[-2:].upper()} não titula a seção")
    exigir("Gatilho<br>esquerdo" not in corpo and "Gatilho<br>direito" not in corpo,
           "o rótulo 'Gatilho esquerdo/direito' voltou para o lado do glifo")
    exigir(corpo.count(">Modo</span>") == 2, "as duas seções não se chamam 'Modo'")

    # 2. O P3 E O P4 SÃO LUGAR VAZIO — *"tudo com Desligado e Nenhum, fora a
    #    borda do P1 e P2."* A régua olha as DUAS metades: o estado e a borda.
    vazios = [c for c in MESA if not c.get("conectado", True)]
    exigir(corpo.count('class="chip vazio"') == len(vazios),
           f"os chips sem cor do plástico não são {len(vazios)}")
    exigir(corpo.count('class="chip plastico"') == len(MESA) - len(vazios),
           "a borda de cor saiu de quem ESTÁ na mesa, ou ficou em quem não está")
    for c in vazios:
        exigir(CENA[c["pref"]]["esq"][0] == "Desligado"
               and CENA[c["pref"]]["dir"][0] == "Desligado",
               f"o {c['pref'].upper()} tem modo de gatilho e é lugar vazio")

    # 2-bis. O LUGAR VAZIO DIZ A POSIÇÃO E O ESTADO, nunca o nome de um plástico
    #    que não está na mesa — *"na parte do nome do P3 e do P4 colocar algo como
    #    Desconectado e não os controles mockados."* A régua olha as DUAS metades:
    #    a palavra tem de estar lá, e o nome do plástico NÃO.
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"o lugar do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a um lugar vazio")

    # 2-ter. O GLIFO CENTRA VERTICALMENTE NA SEÇÃO — *"o l2 e o r2 tem que tá
    #    centralizado entre modo, efeito pronto e ajustes (verticalmente)."*
    #    Ela decidiu o CONTRÁRIO do que eu tinha escrito no CSS um turno antes, e
    #    é por isso que a régua nomeia o valor errado: quem herdar o comentário
    #    velho e "consertar" para `flex-start` esbarra aqui.
    exigir("align-items:flex-start" not in doc.split(".sec-glifo", 1)[-1][:200],
           "o glifo voltou a ficar preso no alto da seção")
    exigir(".rotulos > .sec-glifo{display:flex;align-items:center" in doc,
           "o glifo deixou de centrar verticalmente na seção")

    # 3. O RESPIRO — a divisória cai no MEIO do vão, e o passo é o DOBRO do ar.
    #    *"lá precisa de respiro em tudo (…) o respiro entre as linhas."*
    exigir("top:calc(var(--r-ar) * -1)" in doc,
           "a divisória voltou para o topo da célula — vão todo de um lado só")
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc,
           "o passo deixou de ser o dobro do ar — os dois podem divergir de novo")
    exigir(R_PASSO == R_AR * 2, "R_PASSO e R_AR divergiram no Python")

    # 4. A ALTURA CABE, com folga. Zero de folga já mordeu duas vezes hoje.
    exigir(TETO_DA_GRADE - ALT_COLUNA >= 10,
           f"a grade tem só {TETO_DA_GRADE - ALT_COLUNA}px de folga — um pixel não é folga")

    # 5. OS BOTÕES TÊM ENDEREÇO — 01/09/2026. Sem `data-gesto` o clique não
    #    atravessa a ponte, e o piloto nem consegue RECUSAR dizendo o nome: o
    #    ouvinte dele (`hefesto_vivo.py:190`) só enxerga quem está marcado.
    for _g in ("modo", "pronto", "guardar"):
        exigir(f'data-gesto="{_g}"' in corpo,
               f"o endereço do gesto {_g!r} sumiu do desenho — o clique some calado")

    # 6. TODO MODO CARREGA O CONTRATO DE DISCO NO `value`. `trigger.set` quer
    #    `Rigid`; a opção que só tivesse "Rígido" mandaria um modo que o
    #    `build_from_name` não conhece, e a recusa viria do daemon, não da tela.
    for _spec in PRESETS:
        exigir(f'<option value="{_spec.name}"' in corpo,
               f"o modo {_spec.name} perdeu o `value` — o clique iria sem contrato")

    # 7. TODO CAMPO DE ESCOLHA PINTA POR `valor`, nunca por texto. Com o alvo
    #    padrão (`texto`), a primeira pintura faria `select.textContent = …` e
    #    APAGARIA as opções — as 19 do modo e as 8 do efeito pronto, nas quatro
    #    colunas. Medido no `escrever()` do piloto, `hefesto_vivo.py:100-115`.
    _campos = corpo.count("<select")
    _por_valor = corpo.count('data-hef-alvo="valor"')
    exigir(_por_valor == _campos,
           f"{_campos} campos de escolha e {_por_valor} pintando por valor — "
           f"o que sobra pinta por texto e perde as opções na primeira pintura")

    if falhas:
        raise SystemExit("ERRO em 03-gatilhos — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


n = monta("03-gatilhos", "Gatilhos", MIOLO, CSS + CSS_DA_CENA,
          fita_viva=False, legenda=LEGENDA)
_conferir(onde.pagina("03-gatilhos.html").read_text())
print(f"03-gatilhos: OK, {n} divs · {len(monta_.CONECTADOS)} conectado(s) "
      f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s) · "
      f"{len(MODOS)} modos · coluna {ALT_COLUNA}px de {TETO_DA_GRADE} "
      f"({TETO_DA_GRADE - ALT_COLUNA}px de folga) · respiro {R_AR}px")
