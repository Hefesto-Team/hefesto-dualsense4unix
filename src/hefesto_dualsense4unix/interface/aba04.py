import sys, pathlib, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
import monta as monta_
from itertools import cycle
from monta import (monta, svg, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, player_slot_color, tom_da_casa)
#: O PACOTE DESENHA A FILEIRA DE NÚMEROS, e o gerador a chama. Um dono, dois
#: chamadores — ver `botao_player` abaixo.
from pacotes import a04_iluminacao as _pacote04

# ---------------------------------------------------------------------------
# AS TRÊS MUDANÇAS DE 28/08/2026, e a que arrastou o resto.
#
# 1. Fora de `monta.ABAS_QUE_ESCOLHEM`. Decisão dela: em Gatilhos, Iluminação e Vibração os
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


# ---------------------------------------------------------------------------
# O DESENHO DO CONTROLE VESTE O APARELHO — 03/09/2026, e é a lei dela:
#
#     "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
#      players com cada controle — tudo isso muda de acordo com o controle
#      identificado no canto superior. é white no p1, mas a borda de tudo é
#      cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"
#
# ESTA ABA JÁ TINHA VESTIDO A MOLDURA (`data-campo="plastico"`, alvo `cor`) e a
# FILEIRA de números (o anel do dono, pelo alvo `html`). O que continuava do
# MOCKUP era o maior objeto da tela: o próprio DualSense desenhado, 146 px de
# altura por coluna. Fotografado nesta árvore, com a mesa dela:
#
#     rótulo da coluna (lido do aparelho)   P1 • White • USB
#     desenho dentro da moldura (do MOCKUP) cosmic-red
#     rótulo da coluna (lido do aparelho)   P2 • Galactic Purple • BT
#     desenho dentro da moldura (do MOCKUP) starlight-blue
#
# SÃO DUAS METADES, e uma sem a outra não pinta nada:
#
# 1. O ENDEREÇO. O que muda no desenho é o ATRIBUTO `data-colorway` — é ele que
#    escolhe, na folha de cores, qual dos modelos pinta as dez zonas. O alvo
#    `atributo` do pintor é quem escreve atributo, e o nome do atributo viaja
#    num `data-hef-atributo` SEPARADO (o par é a mesma gramática de
#    `data-hef-classe`/`data-hef-quando`).
#
# 2. A FOLHA. `monta._so_o_colorway` guarda dentro de CADA SVG só as regras do
#    modelo pedido — 3.127 bytes dos 45.497 dos vinte e oito. Escrever
#    `galactic-purple` num SVG cuja folha só conhece `starlight-blue` não pinta
#    roxo: cai nos `fill` crus do `ds_limpo.svg` e dá o mesmo cinza neutro de um
#    desenho sem identidade. Trocaria uma cor errada por um cinza.
#
#    A CURA É PUBLICAR A FOLHA INTEIRA UMA VEZ, na página, e tirar as quatro
#    cópias podadas de dentro dos SVGs. Ela é o mapa DELA — vinte e oito
#    modelos, do White ao Ghost of Yōtei —, e a partir daqui qualquer um deles
#    pinta qualquer uma das quatro colunas. A conta: a página perde 4 × 3.127 e
#    ganha 45.497 uma vez, e passa a saber pintar 28 modelos em vez de 4.
# ---------------------------------------------------------------------------

#: OS TRÊS ATRIBUTOS QUE LIGAM UM DESENHO, e eles andam juntos: sem o
#: `data-hef-alvo` o pintor cai no ramo padrão e escreve o nome do colorway como
#: TEXTO dentro do `<svg>` — o que apaga o desenho inteiro.
ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo" '
                       'data-hef-atributo="data-colorway"')

#: O BLOCO DAS CORES dentro do SVG — a folha E os fundos que ela usa.
#:
#: O `id` VEM PREFIXADO, e é por isso que a âncora não é o nome cru: `monta.svg`
#: renomeia TODO `id` do desenho para `{pref}-{id}`, senão os quatro SVGs da
#: mesma página compartilhariam filtro e degradê.
#:
#: E A FOLHA NÃO VIAJA SOZINHA — este defeito foi MEDIDO, não previsto. A
#: primeira volta desta entrega subiu só o `<style>`, e o Chrome mostrou três
#: modelos pintando com `url(#…)`: `hachura-sem-hex` (a trama de "zona sem hex
#: no catálogo", usada 64 vezes), `casca-god-of-war-20th` e `casca-spider-man-2`.
#: Os três são `<pattern>`/`<linearGradient>` que moram no MESMO
#: `<defs id="cores-do-dualsense">` — e, prefixados dentro de cada SVG, o
#: `url(#casca-spider-man-2)` da folha subida deixava de achar o alvo. Três dos
#: vinte e oito pintariam NADA. A folha e os fundos dela são UMA peça, e sobem
#: juntos, como o gerador de cores os emite.
_BLOCO_DAS_CORES = re.compile(
    r'[ \t]*<defs id="[^"]*cores-do-dualsense">.*?</defs>\n?', re.S)


def _cores_do_mapa(x, quem):
    """O `<defs>` das cores como o gerador o deixou — para a página emiti-lo uma vez.

    Sai de `monta.DS`, que é o `ds_limpo.svg` escrito por
    `scripts/gerar_cores_do_dualsense.py` — o mesmo lugar de onde
    `monta.cor_da_zona` lê o hexadecimal de cada zona. Digitar cor aqui seria a
    segunda verdade que o `docs/data/cores-do-dualsense.csv` existe para não ter.
    """
    m = _BLOCO_DAS_CORES.search(x)
    if m is None:
        raise SystemExit(f"ERRO em {quem}: o `<defs>` das cores sumiu do "
                         f"desenho — rode scripts/gerar_cores_do_dualsense.py")
    return m.group(0)


#: AS CORES DOS VINTE E OITO, uma vez por página, num SVG fora do fluxo. Os
#: quatro desenhos leem daqui — é isto que faz o alvo do `data-colorway` valer
#: para o mapa inteiro dela, e não só para os quatro modelos do desenho.
CORES_DO_MAPA = f'''    <svg class="cores-do-mapa" aria-hidden="true"
         style="position:absolute;width:0;height:0;overflow:hidden">
{_cores_do_mapa(monta_.DS, "04-iluminacao")}    </svg>
'''


def desenho(pref, colorway, conectado, **resto):
    """O DualSense de uma coluna: sem as cores dentro, e com o endereço SEMPRE.

    O QUE O `conectado` DECIDE AQUI É O VALOR, NÃO O ENDEREÇO — e essa distinção
    é a cura de 07/09/2026. O lugar vazio sai SEM `data-colorway` nenhum: não há
    aparelho ali, e um colorway cravado num lugar que diz "Desconectado" é
    identidade do mockup parada na tela. Mas o `data-campo="desenho"` e os dois
    atributos que o acompanham FICAM nos quatro lugares, porque é por eles que o
    pintor veste o desenho quando o controle chega.

    ERA `endereco=False` ATÉ 07/09, e o nome dizia o que o parâmetro fazia: ele
    tirava o endereço JUNTO com o valor. Medido na página publicada daquele dia,
    com os quatro DualSense dela na mesa: `[data-controle="p3"]` tinha ZERO
    `data-campo` por dentro, e o desenho do P3 era um dos dez que não tinham
    onde pousar. O desenho reaparece sozinho — a folha das dez (`topo.html`) tem
    `[data-conectado="nao"] .ds-svg{display:none}`, e o `data-conectado` é a
    marca que o piloto vira nos DOIS sentidos —, mas reaparecia VESTIDO DE
    NADA: sem colorway e sem endereço, ele ficaria no cinza padrão para sempre.
    """
    x, n = _BLOCO_DAS_CORES.subn("", svg(pref, colorway, **resto), count=1)
    if n != 1:
        raise SystemExit(f"ERRO em 04-iluminacao: o SVG de {pref!r} não trazia o "
                         f"`<defs>` das cores — a poda de `monta.svg` mudou de forma")
    marca = f'<svg data-colorway="{colorway}" class="ds-svg" '
    return monta_.troca(
        x, f"04-iluminacao/{pref}", marca,
        f"{marca}{ENDERECO_DO_DESENHO} " if conectado
        else f'<svg class="ds-svg" {ENDERECO_DO_DESENHO} ')


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

#: O EXEMPLO DA TROCA SAIU DAQUI — 03/09/2026. Ele era `TEM_O_1`/`QUER_O_1`,
#: derivado da `MESA` do desenho, e alimentava a dica do "Jogador" e a legenda do
#: rodapé. Derivar da mesa FIXA não é derivar da mesa DELA: os dois nomes que
#: saíam nas duas frases eram os do mockup, na tela do produto. Quem faz o
#: exemplo agora é `pacotes.a04_iluminacao.secao_da_troca`, que recebe a mesa —
#: a do desenho quando o gerador a chama, a VIVA a cada tique.

#: OS TOKENS DA LUZ NO ESCOPO QUE O DESENHO ALCANÇA — e o dono deles é o PACOTE
#: (`a04_iluminacao.tokens_da_luz`), onde está a medição. São dois chamadores: o
#: gerador aqui, para a bancada se ver sozinha, e a folha VIVA, porque a página
#: publicada ainda não os tem. Digitá-los nos dois daria dois brancos na mesma
#: célula no primeiro ajuste.
CSS_DA_LUZ_NO_DESENHO = "  " + _pacote04.tokens_da_luz()

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

     AS ALTURAS SÃO TOKENS porque a soma é o orçamento: 146+16+44+26+52+56+72
     = 412, mais seis passos de 10 = 472, contra o teto de 476 que a caixa do
     miolo oferece. Mexer numa linha sem tirar de outra faz a aba rolar por
     dentro — e quadro que rola por dentro é conteúdo que ninguém sabe que
     existe. O teto sai da MEDIÇÃO, não de uma conta: o `.miolo` dá 564px de
     caixa, 34 vão nos paddings dele e 54 no cromo do quadro (as duas bordas,
     os 17px da faixa do título com o seu padding, e os 24 do corpo). */
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
    /* A LINHA DE RESSALVA CABE NA LINHA DOS LEDs — 04/09/2026, decisão dela
       (D-02, e a pergunta [01] desta aba): *"Uma linha só quando há
       ressalva."* Ela nasce DEBAIXO da tira, e por isso não é uma oitava
       faixa da grade: uma faixa a mais cobra o `--r-passo` inteiro (10px) em
       toda tela, inclusive nas que não têm nada a ressalvar — e a régua da
       D-02 mede exatamente esse pixel. Aqui ela mora DENTRO da faixa dos
       LEDs, na `.cel-leds`, e o `:empty`/`:has(.nada)` de `monta.CSS_FOLHA`
       a apaga por coluna.

       O QUE ELA CUSTA, e a conta está fechada porque o teto é medido: a
       ressalva pede 22px (5 de `margin-top` + 17,25 de linha, arredondado),
       e `--r-leds` vai de 34 para 56. Doze vêm dos 16px de folga que a
       coluna tinha, e DEZ vêm do `--r-player`, que os tinha sobrando: os
       botões de número medem 36px (`--h-escolha`) e a faixa dava 62 —
       medido no Chrome, o conteúdo ia de y=13 a y=49 dentro dela. Com 52 o
       respiro cai de 13 para 8px de cada lado, e nenhum botão encolhe.

       A COLUNA VAI DE 460 PARA 472, contra o teto de 476. O interruptor da
       D-13 não entra nesta conta porque não gasta linha nenhuma: ele mora na
       faixa do TÍTULO do quadro, que tem 17px de altura e 1000px vazios à
       direita — ver `.chave-auto`. */
    --r-player:52px;--r-leds:56px;--r-acoes:72px;
    /* O RESPIRO É O DONO, E O PASSO É O DOBRO DELE — 31/08/2026, pedido dela:
       *"aba iluminação tem a mesma questão do respiro vertical."* É a mesma
       construção da Vibração (30/08) e da Gatilhos (hoje), e o mesmo valor da
       Vibração: 5.
       MEDIDO ANTES: o passo era 8 e a divisória ficava em `top:0` — encostada no
       conteúdo de cima, com o vão INTEIRO embaixo. `a_divisoria_sobe: [0]`.
       O QUE ELE CUSTA: o passo vai de 8 para 10, e 2px em seis vãos são 12. A
       coluna foi de 448 para 460, contra o teto MEDIDO de 476.
       A parte que NÃO custa nada é a que arruma o feio: descer a linha meio
       passo só muda de que lado dela o vão está.
       A FOLGA DE HOJE É 4px, e não os 16 de então: a linha de ressalva de
       04/09 comeu doze — ver a nota do `--r-leds` acima. */
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
  /* A MARCA ENTROU EM 07/09/2026, e é ela que faz este bloco se DESFAZER.
     Tudo daqui para baixo é a cara do lugar sem controle — o cinza, o desenho
     apagado, o travessão preenchendo a célula. Estava preso a `.vazia`, e
     `.vazia` é fato de NASCIMENTO: o gerador a escreve e ninguém a tira nunca,
     nem o piloto. Enquanto o lugar vazio não tinha `data-campo` nenhum isso não
     aparecia — não havia dado a mostrar. Com os endereços no lugar, aparece:
     medido nesta bancada, simulando os passos `1c` e `2` do piloto sobre o P3,
     os dez campos POUSAM (identidade, cor, brilho, tira, ressalva, colorway) e
     o cartão inteiro continuava pintado de cinza, com o desenho em
     `var(--linha) !important` por cima do plástico que acabara de chegar.
     O dado certo, vestido de desconectado.

     `data-conectado` É A MARCA QUE VIRA NOS DOIS SENTIDOS — o gerador a
     escreve, o piloto a fecha no passo `1b` e a REABRE no `1c`. É a mesma
     escolha que a folha das dez faz para o desenho (`topo.html`:
     `[data-conectado="nao"] .ds-svg{display:none}`), e o comentário de lá
     explica por quê. Na página parada nada muda: todo `.vazia` nasce com
     `data-conectado="nao"`, e o retrato antes/depois desta cura tem ZERO pixel
     de diferença nas duas colunas conectadas. */
  .luz-grade .ctrl.vazia[data-conectado="nao"] .nada{display:flex;align-items:center;justify-content:center;height:100%;width:100%}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ctrl-rot,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .nada{color:var(--linha)}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .moldura{border-color:var(--border-forte)}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg .peca,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg .corpo,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg .miolo *{fill:var(--linha) !important}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg .corpo{stroke:var(--border-forte) !important}
  /* OS DETALHES CLAROS TAMBÉM CAEM, e eles só aparecem AQUI. Na aba Jogar o
     desenho tem 62px e estes elementos somem sozinhos; nesta aba ele tem 146 e
     eles ficam à mostra — medido no DOM do lugar vazio: 8 `line` em branco
     (#f8f8f2), 7 `text` em `--texto-suave` e 4 `path` em #d8d8d8, que são os
     glifos L/R/PS e os traços dos botões.
     Copiar a regra da Jogar não bastava: o que muda com o TAMANHO do desenho
     tem de ser medido no tamanho em que ele é desenhado. */
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg text{fill:var(--linha) !important}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg line{stroke:var(--linha) !important}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                            stroke:var(--linha) !important}
  /* O TOUCHPAD E OS BOTÕES SÃO `rect`, `circle` e `polygon`, e a ampliação foi
     quem os achou: com `path`, `line` e `text` já apagados, o touchpad continuou
     cinza-claro (#8a8a96) no meio de um controle inteiro em `--linha`.
     `fill` NÃO leva `none` como valor aqui, e é de propósito: pintar um contorno
     vazado apagaria a forma em vez de escurecê-la. Quem tem `fill:none` no
     arquivo continua sem, porque `var(--linha)` só substitui uma cor que existe. */
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg rect:not([fill="none"]),
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg circle:not([fill="none"]),
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg polygon:not([fill="none"]),
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg rect,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg circle,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg polygon,
  .luz-grade .ctrl.vazia[data-conectado="nao"] .ds-svg ellipse{stroke:var(--border-forte) !important}
  /* O TRAVESSÃO FICA ONDE O CONTEÚDO FICARIA — centrado na célula, para as sete
     linhas continuarem legíveis como linhas. */
  .luz-grade .ctrl.vazia[data-conectado="nao"] > *{display:flex;align-items:center;justify-content:center}
  .luz-grade .ctrl.vazia[data-conectado="nao"] .moldura{display:block}

  /* ---------- O LUGAR QUE ESVAZIA NA FRENTE DELA ---------- */
  /* `.vazia` é o lugar que NASCE sem controle; `.off` é o mesmo lugar depois que
     o controle SAIU — quem escreve a classe é `pacotes.apagar_os_lugares_sem_dono`.
     São o mesmo fato, e até 03/09/2026 tinham duas leituras: esta folha não
     tinha UMA regra `.off`, medido (zero ocorrências de `.off` em
     `04-iluminacao.html`, contra 11 na Jogar e 10 na Controles).

     O QUE ELA VIA, com UM controle no cabo e a régua do produto instalado: a
     coluna do P2 com a moldura ainda no plástico do MOCKUP (medido:
     `borderColor rgb(126,184,212)` = Starlight Blue, contra `rgb(68,71,90)` na
     coluna vazia), os oito tons na mesma saturação da coluna viva
     (`rgb(126,184,212)`, `cursor:pointer`), a barra de brilho CHEIA
     (`width:100%`) ao lado de um "—", e "Automático"/"Desligar" acesos. A régua
     do mockup chama os dois últimos pelo nome: `p2·plastico` e `p2·brilho-pct`,
     **ENDEREÇO MORTO** — o travessão que o molde escreve é recusado pelo CSSOM
     em `color:` e em `width:`, e o valor do desenho fica na tela para sempre.

     E OS BOTÕES ACEITAVAM O CLIQUE. Os dez endereços dessa coluna levantam
     `ValueError: … o clique não disse em qual controle`, e
     `hefesto_vivo._recusou_dizendo` só leva `RuntimeError` à tela: dez botões
     que engoliam o toque sem uma letra. Escondê-los é o que fecha isso — o que
     não existe não pode aceitar clique, e não precisa de frase nova.

     `!important` NÃO É ÊNFASE: a cor do plástico e a largura da barra são
     `style=` INLINE, escritos pelo gerador, e regra externa não os vence sem
     isto — a mesma razão pela qual o bloco `.vazia` acima já o usa no SVG. */
  .luz-grade .ctrl.off .moldura{color:var(--linha) !important;
                                border-color:var(--border-forte) !important}
  .luz-grade .ctrl.off .ctrl-rot{color:var(--linha)}
  .luz-grade .ctrl.off .ds-svg .peca,
  .luz-grade .ctrl.off .ds-svg .corpo,
  .luz-grade .ctrl.off .ds-svg .miolo *{fill:var(--linha) !important}
  .luz-grade .ctrl.off .ds-svg .corpo{stroke:var(--border-forte) !important}
  .luz-grade .ctrl.off .ds-svg text{fill:var(--linha) !important}
  .luz-grade .ctrl.off .ds-svg line{stroke:var(--linha) !important}
  .luz-grade .ctrl.off .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                           stroke:var(--linha) !important}
  .luz-grade .ctrl.off .ds-svg rect:not([fill="none"]),
  .luz-grade .ctrl.off .ds-svg circle:not([fill="none"]),
  .luz-grade .ctrl.off .ds-svg polygon:not([fill="none"]),
  .luz-grade .ctrl.off .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .luz-grade .ctrl.off .ds-svg rect,
  .luz-grade .ctrl.off .ds-svg circle,
  .luz-grade .ctrl.off .ds-svg polygon,
  .luz-grade .ctrl.off .ds-svg ellipse{stroke:var(--border-forte) !important}
  /* OS WIDGETS SAEM, E O TRAVESSÃO FICA. Seis das sete células já têm o "—"
     escrito pelo molde; o que sobrava ao lado dele era o widget da coluna VIVA.
     Sem a guia e sem o trilho, `.cel-cor` e `.cel-brilho` passam a ler o que a
     coluna vazia lê: um traço, e nada mais. */
  /* E A CHAVE DESTE BLOCO PASSOU DE `.off` PARA `[data-conectado="nao"]` —
     07/09/2026, e é o que sustenta a cura desta leva. `.off` só alcança o
     lugar que ESVAZIA na frente dela; o lugar que NASCE vazio carrega `.vazia`
     e nunca ganha `.off` (`hefesto_vivo`, passo `1b`). Enquanto os widgets de
     gesto não nasciam nas colunas sem dono isso bastava — agora eles nascem
     nas quatro, e quem cumpre a decisão dela (*um lugar sem aparelho não
     oferece gesto nenhum*, 31/08/2026) é ESTA regra.

     A MARCA É A CERTA porque é a que o piloto VIRA nos dois sentidos: o passo
     `1b` escreve `nao` e o `1c` escreve `sim`. O widget some quando o  (noqa-acento: valores de atributo)
     controle
     sai e aparece quando ele chega, no mesmo tique, sem que ninguém injete
     HTML — que é justamente o que o piloto não sabe fazer, e a razão de o P3
     e o P4 ficarem sem guia de cores desde que esta aba existe.

     `:not(.vazia)` NÃO ENTRA AQUI, e a diferença é a razão do `:not` lá
     embaixo: aquela regra apaga um `<span class="nada">` (o travessão que o
     lugar vazio já tinha, e que ele precisa manter); esta esconde `button` e
     `input`, que o lugar vazio nunca deve oferecer — nascido vazio ou
     esvaziado. É a mesma leitura que `monta.CSS_FOLHA` faz para as dez abas.

     O TRILHO ESTAVA NESTA LISTA E SAIU PARA A LINHA DE BAIXO em 07/09/2026,
     quando ele passou a nascer no lugar vazio para dar casa ao
     `data-campo="brilho-pct"`; agora as duas leituras voltam a ser uma só. */
  .luz-grade .ctrl[data-conectado="nao"] .guia,
  .luz-grade .ctrl[data-conectado="nao"] .trilho,
  .luz-grade .ctrl[data-conectado="nao"] .cel-acoes .btn{display:none}
  /* A SÉTIMA CÉLULA É A ÚNICA QUE PRECISA DO TRAVESSÃO DE VOLTA — ver o
     `<span class="nada">` que o gerador emite em `cel-acoes`. Ele nasce
     escondido na coluna viva, para não pôr um traço debaixo de dois botões.
     `:not(.vazia)` NÃO É ZELO: sem ele esta regra apaga o travessão que a
     coluna NASCIDA vazia já tinha, e o P3/P4 perdem a linha "Opções". Foi o
     que a primeira foto desta cura mostrou — a régua sou eu olhando, e ela
     pegou a regressão que eu mesmo tinha acabado de escrever.

     E O SELETOR VIROU `[data-conectado="sim"]` EM 07/09/2026, porque
     `:not(.vazia):not(.off)` media o NASCIMENTO e o que decide é o AGORA.  (noqa-acento: verbo medir, imperfeito)
     Medido: com os dois botões nascendo nos quatro lugares, o P3 que ganha um
     controle sai de `.vazia` + `conectado="sim"` — nenhum dos dois `:not`
     falha, o travessão continuava visível, e a célula Opções mostrava "—" ao
     lado de `Automático` e `Desligar`. A marca do piloto responde pelos dois
     estados; a classe de nascimento só responde por um. */
  .luz-grade .ctrl[data-conectado="sim"] .cel-acoes .nada{display:none}
  .luz-grade .ctrl.off .cel-acoes .nada{display:flex;align-items:center;
                                        justify-content:center;color:var(--linha)}
  .luz-grade .ctrl.off .cel-cor,
  .luz-grade .ctrl.off .cel-brilho,
  .luz-grade .ctrl.off .cel-acoes{justify-content:center;color:var(--linha)}
  /* O TRAVESSÃO DESTAS DUAS CÉLULAS NÃO É O `.nada` — é o `.hex` e o `.num`, os
     mesmos elementos que mostram `#0000FF` e `100%` na coluna viva, com o traço
     que o molde escreveu dentro. Eles trazem a fonte e a cor do DADO, e sem
     esta regra os três lugares vazios da mesa mostravam o mesmo caractere em
     duas tintas: medido, `rgb(248,248,242)` em JetBrains Mono na coluna que
     esvaziou contra `rgb(83,87,111)` em Space Grotesk nas que nasceram vazias.
     Branco é a cor do dado nesta aba — um traço branco lê-se como valor.
     O `flex`/`text-align` do `.num` também caem: com o trilho escondido, um
     traço encostado à direita de uma caixa de 38px não fica onde os outros
     dois ficam. */
  /* E OS DOIS LUGARES SEM DONO LEEM IGUAL desde 07/09/2026. A coluna que NASCE
     vazia escrevia o traço num `<span class="nada">` sem endereço; agora ela
     escreve nos MESMOS `.hex` e `.num` da coluna viva, que é o que dá ao
     produto onde pousar a cor e o brilho quando o controle chega. Sem esta
     linha os dois voltariam à fonte e à cor do DADO — que é o defeito que esta
     regra nasceu para matar, agora do outro lado. */
  .luz-grade .ctrl[data-conectado="nao"] .cel-cor .hex,
  .luz-grade .ctrl[data-conectado="nao"] .cel-brilho .num{
                                        font-family:inherit;color:var(--linha);
                                        font-size:inherit;
                                        flex:1;text-align:center;
                                        display:flex;align-items:center;
                                        justify-content:center}
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
     a coluna inteira: nesta aba ele é o instrumento, não a ilustração.

     A BORDA SAI DE `currentColor`, E NÃO DE `--plastico` — 03/09/2026, e é o
     que faz a cor do plástico ser LIDA DO APARELHO em vez de cravada aqui.
     Nenhum alvo do pintor escreve uma variável CSS (`hefesto_vivo.escrever`
     sabe `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e `cor`), e o
     alvo `cor` escreve `style.color`. Com a borda em `currentColor` o pacote
     passa a mandar a cor da casca a cada tique, pelo `data-campo="plastico"`.

     O PADRÃO É NEUTRO de propósito: sem leitura do broker — o primeiro tique de
     toda sessão, e o rádio enquanto a cor não chega — `style.color` volta a
     vazio e a borda cai em `var(--linha)`. Regra dela: campo sem informação não
     mostra nada. Uma borda colorida ali afirmaria um modelo que ninguém leu.

     E O DESENHO NÃO HERDA A COR DA MOLDURA. Medido em 03/09 no Chrome, dentro
     desta página: `#il-p1-glifo-ps` e `#il-p1-glifo-share` desenham com
     `stroke="currentColor"` e SEM classe, então herdavam `--fg` do documento.
     Sem a linha abaixo, a cor que vai à borda tingiria os glifos do PS, do
     share, do options, do mic e dos analógicos. Os quatro glifos de face
     (`.z-simbolos`) já têm cor própria com `!important`, e não estavam em
     risco — os outros cinco estavam. */
  .luz-grade .moldura{color:var(--linha);border:1px solid currentColor;
                      border-radius:8px;background:var(--app-bg);overflow:hidden}
  .luz-grade .moldura .ds-svg{color:var(--fg)}
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
  /* AS DUAS CORES DAS LÂMPADAS MORAM NO `CSS_LUZINHAS` — E NÃO CHEGAVAM AQUI.
     A linha que estava neste lugar dizia "moram no `CSS_LUZINHAS`, com elas" e
     parava aí. Elas moram em `.luzinhas`, que é o indicador PEQUENO da célula
     LEDs, e `.luzinhas` é uma FOLHA da árvore, não um ancestral do desenho: as
     duas regras abaixo pintam `<rect>` DENTRO DO SVG, e variável de CSS só
     herda para baixo. Medido no DOM vivo em 03/09/2026, na mesa dela — as cinco
     lâmpadas do desenho grande saíam todas com o mesmo cinza herdado do casco,
     nenhuma acesa, com o `title` da moldura prometendo que *"as cinco lâmpadas
     dizem qual é [o número]"*.

     O `--luz-apagada` NÃO TEM ESSA DOENÇA, e a primeira volta desta cura disse
     que tinha: `.luzes` é o QUADRO que envolve a `.luz-grade`, então ele já
     descia. A mordida desmentiu — arrancadas as declarações, a barra ficou no
     cinza certo e só as lâmpadas caíram.

     A declaração entra por `CSS_DA_LUZ_NO_DESENHO`, logo abaixo — o par é LIDO
     do dono (o PACOTE, que também o escreve na folha viva), nunca digitado. */
  .luzes,.troca{--luz-apagada:#3f4350}
""" + CSS_DA_LUZ_NO_DESENHO + """
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

  /* ---------- O INTERRUPTOR DO AUTOMÁTICO (D-13) ----------
     ELA ESCOLHEU O INTERRUPTOR DE VERDADE — 04/09/2026, e a recomendação
     escrita propunha o contrário (só MOSTRAR o estado no botão "Automático"):
     *"Um interruptor no topo da aba Iluminação."*

     O CUSTO DECLARADO ERA ~30px, E ELE SAIU DE GRAÇA. A faixa do título do
     quadro (`.quadro-topo`) é um flex de 17px de altura com dois filhos que
     somam 87px numa linha de 1140 — mil pixels vazios à direita. O
     `margin-left:auto` empurra o interruptor para lá, e a faixa não cresce um
     pixel: nada aqui passa dos 17px que o `.ajuda` já ocupa. Os 30px que ela
     aceitou pagar ficaram no bolso, e é o que deixou a linha de ressalva da
     D-02 caber na mesma leva.

     A ALTURA É 17px E NÃO 18: o trilho é 15 de caixa mais 1+1 de borda. Um
     pixel a mais faria a faixa do título crescer, e com ela a coluna inteira
     — que está a 4px do teto.

     O `<input>` É INVISÍVEL E CONTINUA SENDO O ESTADO. Quem pinta é o
     `:checked` do CSS; quem escreve é o alvo `marcado` do piloto, o décimo, e
     é o único que toca `el.checked`. Uma caixinha `class="ligado"` pintada à
     mão seria um estado que só o desenho sabe — e o desenho não sabe o perfil
     dela.

     A DICA ABRE PARA A ESQUERDA, e é medida: a `.dica` tem 330px e nasce em
     `left:22px`; num `?` encostado na direita do quadro ela sairia da janela
     de 1180. `right:22px` é a mesma peça, do outro lado. */
  .chave-auto{
    margin-left:auto;display:flex;align-items:center;gap:7px;cursor:pointer;
    font-size:11.5px;color:var(--texto-suave);height:17px;position:relative;
    -webkit-user-select:none;user-select:none;
  }
  .chave-auto:hover{color:var(--fg)}
  .chave-auto input{position:absolute;width:0;height:0;opacity:0;margin:0;padding:0}
  .chave-trilho{
    width:28px;height:15px;flex:0 0 28px;border-radius:8px;position:relative;
    background:var(--app-bg);border:1px solid var(--border-forte);
  }
  .chave-trilho::after{
    content:"";position:absolute;top:2px;left:2px;width:9px;height:9px;
    border-radius:50%;background:var(--texto-mudo);
  }
  .chave-auto input:checked + .chave-trilho{background:var(--sel-bg);border-color:var(--purple)}
  .chave-auto input:checked + .chave-trilho::after{left:15px;background:var(--purple)}
  .chave-auto:hover .chave-trilho{border-color:var(--comment)}
  .chave-auto input:checked:focus-visible + .chave-trilho,
  .chave-auto input:focus-visible + .chave-trilho{outline:1px solid var(--cyan);outline-offset:1px}
  .quadro-topo .ajuda.esq .dica{left:auto;right:22px}
  /* O ESCOPO GLOBAL DA ABA — LUZES-01, e ele mora na MESMA faixa do
     interruptor, pela mesma razão medida: a faixa do título tem 17px de altura
     e mais de mil de largura vaga, e a grade das colunas está a 6px do teto.
     E o lugar diz o alcance: um botão que mexe em TODOS os controles dentro de
     UMA coluna mentiria sobre quem ele atinge. */
  /* A ALTURA É A DA FAIXA, e ela foi MEDIDA: com `padding:5px` o botão tinha
     23px, a faixa do título ia de 17 para 34 e o quadro passava do teto do
     `.miolo` — a aba rolava por dentro, que é conteúdo que ninguém sabe que
     existe. Com 15px de caixa ele cabe ao lado do interruptor (cujo trilho tem
     15px) e a faixa não cresce um pixel. */
  .btn-todos{
    font-size:10px;line-height:13px;padding:0 8px;height:15px;border-radius:5px;
    border:1px solid var(--border-forte);background:var(--app-bg);
    color:var(--texto-mudo);cursor:pointer;white-space:nowrap;
  }
  .btn-todos:hover{border-color:var(--purple);color:var(--fg)}

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
  /* A CAIXA DO HEXADECIMAL VIRA O BOTÃO — 04/09/2026, decisão dela na pergunta
     [03] desta aba, contra as outras duas opções (deixar como está, ou um
     terceiro botão em Opções).

     O QUE ELA FECHA: a aba manda a cor no instante do clique, e um botão da
     guia SEMPRE dispara — clicar de novo no mesmo tom reenvia. O seletor livre
     não: ele só avisa quando o valor MUDA, então a cor que ela escolheu à mão
     era justamente a única sem porta de volta. A janela GTK tem um botão
     dedicado para isso; aqui o botão é o lugar onde a cor já está escrita.

     NENHUM ELEMENTO NOVO E NENHUMA LINHA, que é a razão da escolha — a fileira
     de Opções já estava apertada. O que muda é o SINAL de que se pode clicar:
     o cursor, e a borda no rato. Sem eles, uma caixa que se lê como texto
     aceitaria clique sem nunca dizer que aceita.

     A BORDA JÁ NASCE (transparente) para o hover não mexer no tamanho — a
     mesma lição que `.guia .tom.on` pagou nesta folha, quatro regras acima. */
  .hex.reenvia{cursor:pointer;border:1px solid transparent;border-radius:5px;
            padding:0 4px;align-self:center}
  .hex.reenvia:hover{border-color:var(--purple);color:var(--purple)}
  /* O LUGAR QUE ESVAZIA NÃO ACEITA O CLIQUE. Ali o `.hex` mostra o travessão
     que o molde escreve, e um clique nele levantaria `o clique não disse em
     qual controle` — que o cartão do piloto não leva à tela (só `RuntimeError`
     chega lá). É a MESMA cura que a folha do `.off` já faz com a guia, o
     trilho e os dois botões, três seções acima. */
  /* E VALE PARA O LUGAR QUE NASCE VAZIO DESDE 07/09/2026, pela chave
     `[data-conectado="nao"]`. A caixa passou a levar `data-gesto="reenviar"`
     nos quatro lugares — sem isso o P3 que chega fica com a única maneira de
     reenviar a cor congelada em nunca. Aqui ela não pode SUMIR como a guia
     some: este `<span>` É o travessão da célula, o mesmo elemento que mostra
     `#0000FF` na coluna viva. O que se apaga é o CLIQUE e a borda de botão,
     não o elemento. */
  .luz-grade .ctrl[data-conectado="nao"] .cel-cor .hex.reenvia{pointer-events:none;
                                                               border-color:transparent}

  /* ---------- BRILHO ---------- */
  .cel-brilho{display:flex;align-items:center;gap:9px}
  .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .num{flex:0 0 38px;text-align:right;font-family:'JetBrains Mono',monospace;
       font-size:11.5px;color:var(--fg)}
  /* O TRILHO PASSA A ACEITAR O ARRASTE — 03/09/2026, decisão dela: perguntada
     se mexer no brilho grava o perfil na hora ou espera o "Salvar Perfil", ela
     respondeu **"Grava na hora"**.

     O QUE HAVIA ATÉ HOJE: o desenho já era um slider — a regra `.cheio::after`
     punha um knob de 12px na ponta da barra roxa — e ele **não fazia nada**.
     Ela via 100%, arrastava, e nada acontecia: a célula inteira era só leitura,
     e o `docs/data/paridade-gtk-html.csv` a nomeia como *"a maior falta desta
     aba"*. Um desenho de slider que não desliza é a família de defeito que esta
     casa mais paga: a tela AFIRMANDO o que o produto não faz.

     O KNOB DEIXA DE SER DESENHO E VIRA O POLEGAR DE VERDADE, e é por isso que
     a regra `.cheio::after` SAIU em vez de ganhar um irmão: com as duas, ela
     veria DOIS knobs durante o arraste — o nativo, que a segue, e o pintado,
     que só alcança o valor no tique seguinte à soltura.

     A GEOMETRIA É A MESMA DO DESENHO APROVADO, e ela não é aproximada: é
     resolvida. O knob do mockup tinha o centro em `larg × b% − 1px` (uma caixa
     de 12px com `right:-5px` dentro de um `.cheio` de largura `b%`). O polegar
     nativo tem o centro em `L + 6px + b% × (W − 12px)`. Igualando para TODO
     `b`: `W = 100% + 12px` e `L = −7px` — que são exatamente os dois números
     abaixo. Com `left:0;width:100%` (o encaixe óbvio) o polegar erraria 7px nas
     pontas, e o desenho dela mudaria de lugar em 0% e em 100%.

     O FUNDO É TRANSPARENTE — a barra roxa continua sendo o `.cheio`, que é
     quem carrega o endereço `brilho-pct` e é pintado pelo PRODUTO. O trilho
     nativo por baixo desenharia uma segunda barra, cinza, por cima da dela.

     `appearance:none` NOS DOIS LADOS: sem ele o WebKit ignora `::-webkit-slider-thumb`
     e devolve o polegar do sistema — outro tamanho, outra cor, e a coluna deixa
     de ser a coluna que ela aprovou. */
  .puxador{position:absolute;left:-7px;top:50%;transform:translateY(-50%);
    width:calc(100% + 12px);height:12px;margin:0;padding:0;
    -webkit-appearance:none;appearance:none;background:transparent;cursor:pointer}
  .puxador::-webkit-slider-runnable-track{height:12px;background:transparent;border:0}
  .puxador::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:12px;height:12px;border-radius:50%;background:var(--purple);
    border:2px solid var(--panel);box-sizing:border-box;cursor:pointer}
  /* O FOCO SE VÊ, e ele importa mais aqui que em qualquer botão desta aba: o
     polegar anda pelas setas do teclado, e um foco invisível seria uma barra
     que muda sozinha sem ninguém saber qual está em foco. */
  .puxador:focus-visible{outline:2px solid var(--purple);outline-offset:4px}

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
  .players button:hover:not(.on):not(.fora){border-color:var(--comment);color:var(--texto-suave)}
  /* O NÚMERO QUE O PRODUTO RECUSARIA — 03/09/2026, medido com UM controle no
     cabo. Os botões 2, 3 e 4 eram pixel a pixel iguais ao 1 e a dica dizia
     "livre"; clicar devolvia *"Esse número é maior do que a quantidade de
     controles ligados"*. A conta e a frase moram em
     `a04_iluminacao.um_botao_de_player`; aqui fica só o que os olhos leem.
     AS CORES SÃO AS QUE A COLUNA VAZIA JÁ USA (`--linha`, `--border-forte`) —
     "não há controle para isto" já tem um cinza nesta aba, e um segundo cinza
     seria um segundo vocabulário para o mesmo fato.
     O CURSOR CAI PARA `default` porque `pointer` é uma promessa: ele diz "isto
     responde ao clique" antes de qualquer dica ser lida. O botão CONTINUA
     clicável de propósito — quem insistir ouve a recusa em vez de nada. */
  .players button.fora{border-color:var(--border-forte);color:var(--linha);
                       cursor:default}
  /* O ANEL É O DONO DO NÚMERO, na cor do plástico dele — e é ele que diz com
     QUEM a troca acontece. Ele é o mesmo em todas as colunas, porque o dono de
     um número é um só; o que muda de coluna para coluna é qual botão está `on`.
     ANEL E NÃO BOLINHA CHEIA, de propósito: nesta aba tudo o que é CHEIO de cor
     é LUZ (a barra, as lâmpadas, os tons da guia). Um disco vermelho ao lado do
     "1" seria lido como a luz do Player 1, que é azul. A BORDA é a cor do
     plástico — a mesma gramática do chip da fita. */
  .players .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                 background:none;border:2px solid var(--plastico)}
  /* O ANEL DO "NÃO SEI" — decisão 9 dela, aplicada ao vizinho de cima
     (`a04_iluminacao.ANEL_INCERTO`, onde está a prova). Um número TOMADO por um
     controle cuja cor ainda não chegou saía SEM anel, isto é, igualzinho a um
     número LIVRE; a ressalva viajava só no `title`. Tracejado, e nunca cor
     nova: quem manda de verdade é o estilo de linha que o pacote escreve, para
     a página publicada valer também. */
  .players .dono.incerta{border:2px dashed var(--comment)}

  /* ---------- DISPOSIÇÃO DE LEDS ---------- */
  /* A CAIXA DA DISPOSIÇÃO PERDEU A MOLDURA — 31/08/2026. Ela era uma borda
     dentro de outra: `.aceso` emoldurava, e o `.pad` lá dentro — 20px mais
     abaixo — emoldurava de novo. Duas linhas onde uma basta, e a de fora não
     separava nada: a faixa já está delimitada pela divisória de cima, pela de
     baixo e pela barra vertical da coluna. Quem tem de ter contorno é o
     touchpad, porque o contorno É o desenho dele. */
  /* A CÉLULA DOS LEDs VOLTOU A TER UM ANDAR SÓ — 07/09/2026. Ela teve DOIS
     entre 04/09 e hoje: a tira em cima e a RESSALVA embaixo (D-02, pergunta
     [01] desta aba). A linha de ressalva saiu por ordem dela — *"o que eu não
     quero é frase da steam ou outras"* —, e com ela saíram as duas regras que a
     vestiam (`.cel-leds .ressalva` e a que a escondia no lugar sem dono).

     A COLUNA DE FLEX FICA, e não é sobra: é ela que dá à célula o
     `justify-content:center` que mantém a tira no eixo do rótulo "LEDs" da
     primeira coluna e do travessão das colunas vazias. Com um filho só,
     centrar a coluna é o que põe a tira no meio dos 56px da faixa — era esse o
     comportamento de antes dos dois andares, e é o que a foto confirma.

     `flex:0 0 34px` NA TIRA, e não `height:100%`: o `100%` a esticaria pelos
     56px da faixa e levaria o halo das duas barras junto. Trinta e quatro é a
     altura que a tira sempre teve.

     `min-width:0` FICA pela razão de sempre num flex: sem ele um item não
     encolhe abaixo do conteúdo, e as cinco colunas dividem 1112px em partes
     iguais. */
  .cel-leds{display:flex;flex-direction:column;align-items:stretch;
            justify-content:center;min-width:0}
  /* E A TIRA DO LUGAR VAZIO MORA NA MESMA CÉLULA — 07/09/2026. Até aqui o
     `.aceso` do lugar sem dono era ele próprio o item da grade, e esta linha
     dizia `align-self:center;height:34px` para ele não esticar pelos 56px da
     faixa. Com a função única, os QUATRO lugares emitem a `.cel-leds`, e quem
     é item de grade é ela nos quatro — a tira volta a medir 34 sozinha, pelo
     `flex:0 0 34px` que já tinha.
     O QUE SOBRA É DEVOLVER O `align-items`: a regra genérica
     `.ctrl.vazia > *` (0,3,0) escreve `center` em todo filho direto, e num
     flex de coluna `center` faz a tira encolher para a largura do conteúdo —
     medido: 212px viravam a largura de um travessão. Esta linha vem DEPOIS
     dela, com a mesma especificidade, e é a que vale. */
  .luz-grade .ctrl.vazia .cel-leds{align-items:stretch}
  /* O VÃO VOLTOU A SER 16px E UM SÓ — 07/09/2026, com a botoeira fora. A
     LUZES-01 o partira em dois grupos (`space-between` + `gap:4px`) porque as
     seis teclas de desenho pediam 212 dos 220px da coluna e não sobrava vão;
     sem elas, a `.aceso` volta a ter três filhos — tira, indicador, tira — e o
     `center` com 16 de respiro é o desenho original, que é o que ela mandou
     manter: *"os leds. barra de luz ficam. é o desenho original."* */
  .aceso{border-radius:8px;background:var(--app-bg);
         display:flex;align-items:center;justify-content:center;gap:16px;
         flex:0 0 34px}
  /* `flex:0 0 6px` FICA, mesmo com o aperto embora — e não é sobra da botoeira.
     Sem ele a largura da tira é um PEDIDO, e o `flex-shrink` padrão (1) o
     atende encolhendo até zero: foi assim que as duas tiras sumiram quando o
     conteúdo apertou. Elas cabem hoje; a trava é o que garante que o próximo
     item posto nesta faixa não as apague de novo, calado. */
  .tira-luz{flex:0 0 6px;width:6px;height:20px;border-radius:3px}
  .tira-luz.esq{box-shadow:-3px 0 12px 1px currentColor}
  .tira-luz.dir{box-shadow:3px 0 12px 1px currentColor}
  /* A TIRA DO "NÃO SEI" — decisão 9 dela, 03/09/2026:
     *"tracejado para 'não sei'; lisa e vazia para 'apagada'"*.

     O DEFEITO QUE ELA VIU: as duas eram a MESMA tira, byte por byte
     (`background:var(--panel);color:transparent;opacity:1`), e a ressalva que
     as separa viajava só no `title` — quem não passa o mouse não vê. São três
     coisas que o motor já distinguia e a tela mostrava como duas:

       acesa     a cor conhecida, com halo        `background:{tinta}`
       apagada   fonte NOSSA, barra desligada     `TIRA_APAGADA` — lisa e vazia
       incerta   Nativo · Steam · cor ignorada    ESTA REGRA — tracejada

     CONTORNO, E NUNCA COR NOVA — ordem dela. Nesta aba tudo o que é CHEIO de
     cor é LUZ (as duas tiras, as cinco lâmpadas, os oito tons da guia): uma
     cor inventada para "não sei" seria lida como uma luz que ninguém mediu.

     ESTA REGRA É SÓ O CONTORNO, e ela ficou assim depois da mordida. Fundo,
     halo e opacidade já vêm do PISO: a tira do "não sei" sai com o mesmo
     `style=` de linha da apagada (`a04_iluminacao.TIRA_APAGADA`), que é o que
     protege a página cuja folha ainda não conhece esta regra — o publicado, até
     ela mandar publicar a 04. Sem estilo de linha a tira ficaria sem `color`,
     herdaria o `--fg` e o halo `box-shadow: … currentColor` a acenderia BRANCA,
     que é o defeito fotografado em 02/09.

     FATO ERRADO, DERRUBADO PELA PRÓPRIA MORDIDA (03/09/2026): esta regra dizia
     `background:transparent !important` e o comentário afirmava que sem o
     `!important` *"o contorno nunca aparece"*. Arranquei o `!important`,
     regerei e FOTOGRAFEI: o tracejado continua lá, idêntico. Ele nunca foi o
     que mostra o traço — quem mostra é a `border`, e o fundo que ele disputava
     é o `var(--panel)`, indistinguível do `--app-bg` atrás dele. As três
     declarações que sobravam saíram junto (`color`, `box-shadow`, `opacity`):
     o estilo de linha já as põe, e regra que não morde é regra que mente sobre
     quem manda. */
  .tira-luz.incerta{border:1px dashed var(--comment)}
  /* ---------- O INDICADOR VOLTOU A SER INDICADOR (07/09/2026) ----------
     A BOTOEIRA DA LUZES-01 SAIU INTEIRA, por ordem dela: *"só olhar a linha de
     cima da seleção de player e replicar o que tem lá."* Saíram com ela as
     cinco `.pad .lamp`, que eram botões de gesto, mais as seis `.desenhos .dz`
     e o `.pad.reenvia`.

     OS TRÊS NOMES DE GESTO NÃO ESTÃO ESCRITOS AQUI, e a omissão é cura de um
     defeito MEDIDO nesta mesma leva: a primeira redação deste comentário citava
     um deles por extenso, com o atributo e as aspas. O CSS do gerador entra
     INTEIRO na página, e o portão `paridade-gtk-html` procura o sinal de cada
     linha do CSV como TEXTO no HTML — então o comentário que EXPLICAVA a
     remoção virou a prova de que a peça continuava lá, e a linha 140 do CSV
     ficou verde sobre um botão que não existe mais. As outras duas, que ninguém
     tinha citado, reprovaram certo.

     É a armadilha que o `CLAUDE.md` desta casa nomeia três vezes em três dias:
     *um comentário que descreve o padrão proibido VIRA a primeira ocorrência
     dele*. Quem for escrever aqui o nome de um `data-gesto` que saiu, escreva-o
     sem o atributo — ou não escreva. Os nomes estão em
     `pacotes/a04_iluminacao.GESTO_DO_AUTOMATICO_DE_TODOS`, na nota datada. */
  /* (continua) O que sobra desta faixa: */

     O QUE SOBRA É A MOLDURA DE LEITURA, e ela é a de antes da LUZES-01, com as
     medidas de então: 56x20, que é o que as cinco lâmpadas de `monta.luzinhas`
     pedem — 5 de 6px, dois vãos de 4 e o `padding-bottom:3px` que centra o
     desenho na moldura do touchpad. As cinco lâmpadas em si são pintadas por
     `CSS_LUZINHAS`, logo abaixo, que é o dono das duas cores.

     E NÃO SOBRA CURSOR NENHUM: sem `cursor:pointer` e sem `:hover`, a célula
     LEDs não convida a um clique que não existe mais. Uma moldura que ainda
     acendesse a borda no rato prometeria um gesto que o pacote já não tem —
     que é a metade visual do órfão calado. */
  .pad{width:56px;height:20px;border-radius:5px;border:1px solid var(--linha);
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
  /* O mesmo "não sei" da fileira de players — ver `.players .dono.incerta`. */
  .troca-item .dono.incerta{border:2px dashed var(--comment)}
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


#: OS DONOS DOS NÚMEROS, como o desenho os conhece: só quem está na MESA.
#:
#: O DONO SÓ EXISTE SE ELE ESTIVER LÁ — 31/08/2026, e foi a régua desta aba que
#: achou. O `title` dizia *"Dar o Player 3 ao Cosmic Red: o Galactic Purple
#: (BT), que tem o 3 hoje, fica com o 1"* — e o Galactic Purple está
#: DESCONECTADO. Ele não tem o 3 hoje; ele não tem nada hoje. É a mesma família
#: do que ela mandou tirar do cabeçalho da coluna (*"colocar algo como
#: Desconectado e não os controles mockados"*).
DONOS_NA_MESA = {n: d for n, d in DONO.items() if d.get("conectado", True)}


#: O `botao_player` DESTE ARQUIVO MORREU EM 02/09/2026, e a razão é a regra da
#: casa: o produto passou a pintar esta fileira a cada tique (o `data-campo`
#: saiu dos quatro botões e foi para o `.players`, com alvo `html`), e enquanto
#: o botão fosse escrito em DOIS lugares o desenho e o produto podiam divergir
#: sem ninguém ver — foi assim que a `novo-layout/` divergiu 25 KB calada.
#: O dono único é `pacotes/a04_iluminacao.um_botao_de_player`, e este gerador é
#: um dos dois chamadores.


#: O marcador de campo vazio — o mesmo travessão da Jogar e da Controles.
#:
#: E ELE É O MESMO CARACTERE QUE O PRODUTO ESCREVE: `pacotes.TRAVESSAO` é o que
#: `apagar_os_lugares_sem_dono` põe em todo `data-campo` de um lugar sem dono, e
#: este literal é o que o gerador põe no mesmo lugar. Se os dois divergissem, o
#: lugar vazio trocaria de caractere no primeiro tique.
VAZIO = "—"

#: A FRASE DO LUGAR SEM DONO, e ela é a mesma que o produto escreve —
#: `pacotes.SEM_NINGUEM_AQUI`. O gerador a escreve com a marcação da tela
#: (`<span class="pt">`); o pacote a reescreve por `texto`, sem marcação, a cada
#: tique. As duas dizem a mesma palavra, que é o que a régua §3 cobra.
SEM_NINGUEM_AQUI = "Desconectado"


def coluna(c):
    """A coluna de UM lugar da mesa — com controle ou sem, e é a MESMA função.

    ERAM DUAS ATÉ 07/09/2026, e a segunda envelheceu sem a primeira. Este
    arquivo tinha uma `coluna_vazia()` que desenhava o lugar sem dono com sete
    células de travessão e **nenhum `data-campo` por dentro** — medido na página
    publicada naquele dia, com a régua `medir.py` deste trabalho:

        p1: 20 data-campo (10 distintos)     p3: 0 data-campo (0 distintos)
        p2: 20 data-campo (10 distintos)     p4: 0 data-campo (0 distintos)

    O QUE ISSO CUSTAVA, com os QUATRO DualSense dela na mesa: o daemon publicava
    quatro controles, a carga chegava com `colunas = ['p1','p2','p3','p4']` e os
    quatro em `ocupados` — e a tela mostrava DOIS. O piloto pinta por endereço
    (`hefesto_vivo`, passo 2: `for(const el of achar(raiz, k))`, e `achar`
    procura `data-campo` DENTRO do bloco daquele `data-controle`), então o dado
    do P3 chegava e **não tinha onde pousar**. Os outros dois lugares seguiam
    dizendo "P3 · Desconectado" com travessão em tudo.

    O ENDEREÇO DO BLOCO JÁ TINHA SIDO CURADO EM 03/09 — o `data-controle` no
    lugar vazio, decisão dela: *"tem que aparecer desligado enquanto não tem
    nenhum controle. A partir do momento que tiver, ele aparece o controle
    devidamente conectado. Se isso não ocorre com os 4 controles em cada aba,
    então temos que construir isso e garantir isso."* Faltava a outra metade:
    o endereço do bloco diz ONDE, e o `data-campo` diz O QUÊ. Sem os dois o
    piloto acha a coluna e não acha um só campo dentro dela.

    POR QUE UMA FUNÇÃO SÓ, e não duas curadas em paralelo: **duas funções que
    duplicam estrutura foi exatamente o que produziu este defeito.** Os campos
    entraram na coluna viva ao longo de agosto e setembro — `plastico`,
    `desenho`, `identidade`, `hex`, `brilho-pct`, `brilho`, `players`, `luz`,
    `luz-ressalva` — e a `coluna_vazia` não foi junto uma única vez. Escrever o
    endereço num literal só, compartilhado pelos dois estados, é o que impede
    que ele volte a envelhecer pela metade.

    O `conectado` DECIDE TRÊS COISAS, e a terceira é a única que não é texto:

    1. **a classe e o atributo** — `ctrl` / `ctrl vazia`, `data-conectado`
       `sim` / `nao`. Quem os tira quando o controle chega é o piloto, no passo  (noqa-acento: `nao` é o VALOR do atributo, não a palavra)
       `1c`; o `data-conectado` é a marca que ele vira nos DOIS sentidos, e é
       por ela que a folha das dez (`topo.html`) acende o desenho de novo.
    2. **o TEXTO inicial de cada campo** — o valor do desenho, ou o travessão.
       Nenhum valor cravado sobra num lugar sem dono: nem `data-colorway`, nem
       a cor do plástico no `style`, nem a largura da barra de brilho. Valor
       cravado num lugar vazio é identidade do mockup parada na tela.
    3. **os widgets que carregam GESTO** — a guia das oito cores, o seletor
       livre, o puxador do brilho e os dois botões de Opções. Estes são a
       exceção, e ela é decisão dela: *um lugar sem aparelho não oferece gesto
       nenhum* (a régua §4 abaixo, e a razão medida está no bloco `.ctrl.off`
       do CSS — os dez endereços dessa coluna levantam `o clique não disse em
       qual controle`, e a tela só recebe `RuntimeError`).

    O QUE ESTA CURA **NÃO** ALCANÇA, e fica escrito para quem vier: os widgets
    do item 3 continuam fora do lugar que NASCE vazio, e o piloto não injeta
    widget nenhum — ele só vira classe e escreve campo. Quando o P3 chega, a
    coluna passa a mostrar identidade, cor, brilho, a fileira de jogador e a
    tira de luz (as duas últimas voltam inteiras, porque são blocos de alvo
    `html` que o pacote reescreve), mas a guia de cores, o trilho e os dois
    botões só aparecem no recarregar. Fechar isso é decisão de tela — dela — e
    pede ou o piloto sabendo materializar widget, ou o lugar vazio nascendo com
    eles escondidos por CSS, que é o que o bloco `.ctrl.off` já faz para a
    coluna que ESVAZIA.

    E O `luz-incerta` NÃO É CAMPO DO CARTÃO: ele nasce nas duas `.tira-luz`,
    dentro do `.aceso`, que é um bloco de alvo `html` — o pacote troca aquele
    miolo inteiro a cada tique, e o que mora lá dentro é contrato DELE, não
    deste gerador. Cravar uma tira escondida no lugar vazio só para o conjunto
    fechar seria régua medindo a própria saída. A auto-checagem §14 desconta os
    blocos de alvo `html` dos dois lados, e é por isso.
    """
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
    ligado = c.get("conectado", True)
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
        # `data-gesto="cor"` É O ENDEREÇO DO CLIQUE, e `data-hex` é o que ele
        # leva. Sem os dois o botão era pintura pura: o piloto via um `<button>`
        # sem `data-*` e não tinha o que mandar ao daemon. Medido em 01/09/2026
        # — dos 202 botões das dez páginas, 178 estavam assim.
        #
        # O `data-hex` LEVA A COR DO PRODUTO, não o tom da casa, e a diferença
        # foi um defeito de verdade que a prova botão a botão pegou em
        # 01/09/2026, no pedido dela: *"no aparelho por favor valida botão a
        # botão"*. O `monta.TOM_DA_CASA` traduz `#0000FF → #7EB8D4` para o
        # DESENHO — a paleta Dracula não usa azul puro — e o botão levava esse
        # tom AO APARELHO. A tela pintava no plástico dela a cor de tela.
        #
        # Os dois lados ficam, e cada um no seu lugar: `style="background"` usa
        # o tom da casa (é o que ela vê) e `data-hex` usa `luz(i)` (é o que o
        # produto acende). É a mesma cura que a linha do `.tom.on` já fazia para
        # a comparação — faltava fazê-la para o VALOR.
        # O ANEL DA COR ESCOLHIDA DEIXOU DE SER PINTURA — 02/09/2026. O `on`
        # acima é o que o GERADOR soube: a cor cravada do mockup. Quem escolhe
        # uma cor fora da guia, ou muda a cor pelo aparelho, via o anel parado
        # no tom velho para sempre — a pintura da casa sabia texto, largura,
        # fundo, valor e HTML, e o estado desta guia é uma CLASSE.
        #
        # Agora sabe: `data-hef-alvo="classe"` com `data-hef-quando` acende no
        # botão cujo valor casa com o pintado, e apaga nos outros — sem lista de
        # irmãos, porque os oito dividem o MESMO `data-campo` e cada um decide
        # por si (`hefesto_vivo.escrever`, o ramo do alvo `classe`).
        #
        # O ENDEREÇO É `hex`, o MESMO da caixa `#RRGGBB` logo abaixo, e não um
        # segundo: é UM valor — a cor gravada — em duas renderizações. Um nome
        # novo faria o pacote emitir a mesma cor duas vezes, e as duas poderiam
        # divergir. O `data-hef-quando` leva `luz(i)`, o hex do PRODUTO, porque
        # é ele que o pacote emite; o `style` continua no tom da casa, que é o
        # que ela vê.
        # E O `on` PEDE `ligado` DESDE 07/09/2026, junto com a guia que passou a
        # nascer nos quatro lugares: `cor` é `luz(j)`, a cor AUTOMÁTICA do
        # número daquele lugar, e num lugar sem aparelho ela não é escolha de
        # ninguém — é o desenho. Marcar o anel ali seria afirmar uma cor
        # escolhida onde não há controle que a tenha escolhido.
        f'            <button class="tom{" on" if ligado and t == tom_da_casa(cor) else ""}" style="background:{t}"'
        f' data-campo="hex" data-hef-alvo="classe" data-hef-quando="{luz(i)}"'
        f' data-gesto="cor" data-hex="{luz(i)}"'
        # E O `title` NÃO NOMEIA CONTROLE — 03/09/2026. Ele dizia *"pinta a
        # barra do {nome}"*, com o nome do MOCKUP, e a régua da identidade não o
        # acusava: ela pula o `title` de quem já tem endereço, e este botão tem
        # (`data-campo="hex"`). Endereço não cura frase congelada — `title` é
        # ATRIBUTO, e o pintor não tem alvo para atributo, então o que estivesse
        # escrito aqui ficaria na tela dela para sempre. A frase que sobra é
        # verdadeira em qualquer mesa: quem é "este controle" a coluna já diz,
        # no rótulo vivo logo acima.
        f' title="Cor automática do Player {i} — usar aqui pinta a barra deste'
        f' controle, e não muda o número dele."></button>'
        for i, t in enumerate(TONS, 1))

    # ---- O QUE O `conectado` DECIDE, peça por peça ----
    # Cada nome abaixo é UM pedaço do molde único lá embaixo. O endereço
    # (`data-campo`, `data-hef-*`) NUNCA está aqui: ele mora no molde, escrito
    # uma vez só, e é isso que impede os dois estados de envelhecerem apartados.
    #
    # O `title` DO CARTÃO só existe no lugar vazio — é a frase que diz o que
    # aquele espaço é. `title` é ATRIBUTO, e o pintor não tem alvo para
    # atributo: uma frase escrita aqui fica congelada. A do lugar vazio é
    # verdadeira enquanto ele estiver vazio, e some no recarregar seguinte.
    titulo_do_lugar = "" if ligado else (
        '\n             title="Nenhum controle neste lugar."')
    # A COR DO PLÁSTICO É VALOR, e por isso não sobra no lugar sem dono: o
    # `style="color:"` do desenho é o plástico do MOCKUP. O endereço fica; o
    # valor de partida, não. Quem escreve a cor é o pintor, pelo alvo `cor`.
    plastico_de_partida = (f' style="color:{cor_da_zona(c["cor"])}"'
                           if ligado else "")
    dica_da_moldura = (
        ' title="A borda é a cor do plástico deste controle, quando o produto a'
        ' conhece. A barra acende a cor do número, e as cinco lâmpadas dizem'
        ' qual é."' if ligado else "")
    rotulo = (f'P{j} <span class="pt">•</span> {c["nome"]}'
              f' <span class="pt">•</span> {c["via"]}' if ligado else
              f'P{j} <span class="pt">•</span> {SEM_NINGUEM_AQUI}')
    # OS QUATRO WIDGETS DE GESTO NASCEM NOS QUATRO LUGARES — 07/09/2026, e é a
    # cura desta leva. Até hoje a `guia`, o `puxador`, o `reenvio` e as
    # `opcoes` eram `... if ligado else ""`, e o preço foi MEDIDO nas  (noqa-acento: nome de variável)
    # páginas
    # publicadas: `data-gesto` por lugar dava `p1=9 · p2=9 · p3=0 · p4=0`
    # nesta aba, contra `p1=p2=p3=p4` em todas as outras. Com os QUATRO
    # DualSense dela na mesa e o daemon de pé, a foto ao vivo mostrava o P3 e o
    # P4 com nome, cor (#00FF00, #FF0000), brilho 100% e o número de jogador
    # aceso — e SEM a fileira de amostras de cor, SEM o puxador do brilho e com
    # a célula Opções em travessão. **Ela não conseguia trocar a cor do P3 pela
    # tela**, e há dois testes da bancada que mandam fazer exatamente isso (a
    # Linha 8, "uma cor diferente em cada um", e a Linha 21, "uma cor no P4").
    #
    # A CAUSA É QUE O PILOTO NÃO MATERIALIZA WIDGET: ele vira a marca
    # `data-conectado` e escreve campo (`hefesto_vivo`, passos 1c e 2). O que
    # não nasceu no HTML não aparece quando o controle chega — só recarregar a
    # página desfazia, e a página é ela quem abre. Era a limitação que a
    # docstring desta função já dava por escrito ("o que esta cura NÃO
    # alcança"); esta leva a fecha.
    #
    # A DECISÃO DELA CONTINUA DE PÉ — *um lugar sem aparelho não oferece gesto
    # nenhum* (31/08/2026) — e quem a cumpre agora é o CSS, não a ausência: o
    # bloco `[data-conectado="nao"]` desta folha esconde a guia, o trilho e os
    # dois botões, e neutraliza o clique da caixa do hexadecimal. É a MESMA
    # marca que o piloto já virava nos dois sentidos, então o widget aparece no
    # instante do passo `1c` e some no `1b`, sem ninguém injetar HTML.
    #
    # E A ESTRUTURA VEM SEM O VALOR, que é a outra metade: um lugar sem dono
    # não carrega a cor nem o brilho do MOCKUP (a lei da `check_a_cor_vem_do_
    # aparelho.py`, e a razão do item 2 da docstring). O `value` do seletor
    # livre nasce preto e o do puxador nasce zero — nenhum dos dois é
    # identidade de aparelho nenhum —, e o `.cheio` continua sem `style=
    # "width"`. Quem escreve os valores é o pintor, pelo `data-campo`.
    cor_de_partida = cor.lower() if ligado else "#000000"
    guia = f'''<span class="guia">
{tons}
              <input type="color" class="livre" value="{cor_de_partida}" data-gesto="cor"
                     title="Livre — abre o seletor para uma cor que não está na guia.">
            </span>
            '''
    reenvio = ' data-gesto="reenviar"'
    dica_do_hex = ('\n                  title="Manda esta cor ao controle de novo'
                   ' — a mesma que já está escrita aqui."')
    largura_de_partida = f' style="width:{b}%"' if ligado else ""
    puxador = (f'<input class="puxador" type="range" min="0" max="100" step="1"'
               f' value="{b if ligado else 0}" data-gesto="brilho" data-campo="brilho-pct"'
               f' data-hef-alvo="valor"'
               f' aria-label="{_pacote04.ROTULO_DO_BRILHO}"'
               f' title="{_pacote04.DICA_DO_BRILHO}">')
    fileira = (_pacote04.fileira_de_players(
        c["nome"], c["jogador"], DONOS_NA_MESA, "            ",
        quantos=len(monta_.CONECTADOS)) if ligado else
        f'            <span class="nada">{VAZIO}</span>')
    # A DICA DA CÉLULA `LEDs` SAIU DA CÉLULA E ENTROU NO DESENHO — 02/09/2026,
    # decisões 7 e 8 dela. Ela dizia *"O Cosmic Red **aceso**: as duas tiras na
    # cor escolhida, e as cinco lâmpadas no padrão do Player 1"*: o nome do
    # MOCKUP, e uma palavra que ela já tinha mandado tirar (a GTK obedeceu em
    # 25/08 — ver `pacotes/a04_iluminacao.dica_da_luz`).
    #
    # POR QUE ELA NÃO PODIA FICAR NA CÉLULA: `title` é ATRIBUTO, e o piloto não
    # tem alvo de pintura para atributo. Toda dica escrita aqui fica CONGELADA
    # no que o gerador soube — e o gerador só sabe o mockup. Dentro do desenho
    # ela viaja pelo alvo `html` do `luz`, que se troca a cada tique.
    #
    # E ELA ENCOLHEU no mesmo dia: a frase *"Desenho que mandamos: desenho do
    # PN — automático…"* saiu, porque o pacote não vê a camada do merge que
    # decide qual desenho está em vigor. Aqui, sem mesa viva, o gerador não
    # passa nem o número: `dica_da_luz` não precisa mais dele.
    miolo_da_luz = (_pacote04.desenho_da_luz(
        tinta, b / 100, j, dica=_pacote04.dica_da_luz(c["nome"], c["via"], ""),
        recuo="              ") if ligado else
        f'              <span class="nada">{VAZIO}</span>')
    # O DESENHO DO LUGAR VAZIO NÃO ACENDE LÂMPADA NENHUMA — não há número de
    # jogador a mostrar. O do lugar cheio acende o padrão do número dele.
    resto_do_desenho = ({"jogador": j, "luz": tinta} if ligado
                        else {"lampadas": False})
    brilho_escrito = f"{b}%" if ligado else VAZIO
    opcoes = '''<button class="btn roxo" data-gesto="auto" title="Tira a cor escolhida à mão e devolve a automática — a do número deste controle.">Automático</button>
            <button class="btn vermelho" data-gesto="apagar" title="Apaga a barra de luz deste controle.">Desligar</button>
            '''

    # O VALOR DO ATRIBUTO SAI DA f-STRING, e não é asseio: a marca que isenta
    # `nao` da régua de acentuação é um `#`, e dentro de uma f-string de  (noqa-acento: o próprio valor que a nota explica)
    # HTML o
    # `#` não comenta nada — ele SAI NA PÁGINA. Aqui em cima ela comenta.
    conectado = "sim" if ligado else "nao"  # noqa-acento: valor de atributo
    return f'''        <div class="ctrl{"" if ligado else " vazia"}" data-controle="{c.get("uniq") or p}" data-conectado="{conectado}"{titulo_do_lugar}>
          <div class="moldura" data-campo="plastico" data-hef-alvo="cor"{plastico_de_partida}{dica_da_moldura}>
            {desenho(f"il-{p}", c["cor"], ligado, **resto_do_desenho)}
          </div>
          <div class="ctrl-rot" data-campo="identidade">{rotulo}</div>
          <div class="cel-cor">
            {guia}<!-- E ELA REENVIA — 04/09/2026, decisão [03] dela. O `data-gesto`
                 vai NESTA caixa e não num botão novo, e o valor que ele leva é
                 o TEXTO dela: `data-hex` seria a cor do gerador, congelada, e
                 mandaria ao aparelho a cor do mockup em vez da que está
                 gravada. O `texto` do clique é o que o piloto lê do
                 `textContent`, e o `textContent` é o que o pacote reescreve a
                 cada tique pelo `data-campo="hex"`. -->
            <span class="hex reenvia" data-campo="hex"{reenvio}{dica_do_hex}>{cor if ligado else VAZIO}</span>
          </div>
          <div class="cel-brilho">
            <span class="trilho"><span class="cheio" data-campo="brilho-pct" data-hef-alvo="largura"{largura_de_partida}></span>{puxador}</span>
            <span class="num" data-campo="brilho">{brilho_escrito}</span>
          </div>
          <div class="players" data-campo="players" data-hef-alvo="html">
{fileira}
          </div>
          <div class="cel-leds">
            <div class="aceso" data-campo="luz" data-hef-alvo="html">
{miolo_da_luz}
            </div>
            <!-- A LINHA DE RESSALVA SAIU DAQUI — 07/09/2026, ordem dela: *"o
                 que eu não quero é frase da steam ou outras e p1,P2…"*. Ela
                 nasceu em 04/09 (D-02) para responder QUAL das três causas
                 apagou a barra sem exigir o rato; o que ela mostrava era, entre
                 outras, a frase da Steam, e é exatamente essa que ela mandou
                 tirar.

                 O FATO NÃO SE PERDEU, e é o que faz esta remoção não ser perda:
                 a razão continua no `title` das DUAS tiras, escrita pela
                 `dica_da_luz` a cada tique — o mesmo motor
                 (`controller_card.rotulo_lightbar`), pelo alvo `html` do `luz`.
                 O que saiu foi a LINHA de texto, não o dado.

                 E O CAMPO SAIU DOS DOIS LADOS NO MESMO COMMIT: o pacote parou
                 de emitir o endereço desta linha junto com este widget. Um
                 campo que o pacote manda e a página não tem vira ÓRFÃO calado
                 no piloto, tique após tique — medido a zero nesta leva, com os
                 quatro DualSense na mesa.

                 O NOME DO CAMPO NÃO ESTÁ ESCRITO AQUI, e a omissão é cura de um
                 defeito medido nesta mesma leva, do outro lado do arquivo: um
                 comentário da folha citou um `data-gesto` removido com o
                 atributo e as aspas, o CSS entrou inteiro na página, e o portão
                 `paridade-gtk-html` — que procura o sinal como TEXTO no HTML —
                 deu VERDE sobre um botão que não existe mais. *Um comentário
                 que descreve o padrão proibido vira a primeira ocorrência
                 dele.* Quem precisar do nome: ele está no
                 `test_a_04_as_lampadas_espelham_o_numero`, que cobra a
                 ausência. -->
          </div>
          <div class="cel-acoes">
            {opcoes}<!-- O TRAVESSÃO DESTA CÉLULA NASCE AQUI, escondido na coluna viva, e
                 é o único das sete que precisava nascer: as outras seis têm
                 `data-campo`, e o molde do lugar sem dono já escreve o traço
                 nelas. Esta não tem — dois botões não são um valor —, então sem
                 este `<span>` a coluna que ESVAZIA na frente dela ficaria com a
                 linha "Opções" em branco, quando a coluna que nasce vazia
                 mostra "—". Um lugar sem controle tem uma leitura só. -->
            <span class="nada">{VAZIO}</span>
          </div>
        </div>'''

MIOLO = f'''
{CORES_DO_MAPA}
    <div class="quadro luzes">
      <div class="quadro-topo">
        <span class="quadro-titulo">Iluminação</span>
        <!-- DE 777 PARA ~230 CARACTERES — 30/08/2026, mesma regra da Vibração: o
             parágrafo que nomeia um campo vai para o `?` daquele campo. O da cor
             das barras foi para "Cor", o de gravar foi para o rodapé (que já tem
             `title` nos quatro botões desde hoje). -->
        <span class="ajuda">?<span class="dica">
          A <b>barra de luz</b> é a faixa que acende dos dois lados do touchpad, e é a
          identidade de cada controle: você olha e sabe de quem é.<br><br>
          O plástico é físico e pode se repetir; a <b>luz</b> é o que nunca se repete.
        </span></span>
        <!-- O INTERRUPTOR DO AUTOMÁTICO — D-13, decisão dela de 04/09/2026:
             *"Um interruptor no topo da aba Iluminação."*

             O QUE ELE GOVERNA não é o botão "Automático" da célula Opções: são
             coisas diferentes com a mesma palavra. Aquele é POR CONTROLE e é um
             toque só — larga o claim da barra para o jogo. Este é do PERFIL, e
             governa a paleta automática E a numeração (inclusive a dos
             externos). Pelo HTML ela não via o estado nem podia mudá-lo, e o
             perfil dela está com ele LIGADO.

             `checked` NO DESENHO porque é o estado do perfil dela hoje; no
             produto quem manda é o alvo `marcado`, que o piloto escreve a cada
             tique com o que está no disco. O `data-gesto` fica no `<input>` e
             não no `<label>`: um clique no rótulo já dispara o do `<input>` por
             ativação, e dois endereços para o mesmo ato mandariam dois pedidos.

             A DICA DIZ A CONSEQUÊNCIA, e ela é a que ela aceitou por escrito
             (*"ok aceito o caminho"*): desligar GRAVA a cor de cada controle no
             ato, para nenhuma se perder e nenhuma se repetir. -->
        <label class="chave-auto">
          <input type="checkbox" data-gesto="auto-cores" data-campo="auto-cores"
                 data-hef-alvo="marcado" checked>
          <span class="chave-trilho"></span>
          <span>Cores automáticas por controle</span>
        </label>
        <span class="ajuda esq">?<span class="dica">
          Ligado, cada controle acende a <b>cor do número dele</b> e recebe o número
          automaticamente — inclusive os controles de outras marcas.<br><br>
          Ao <b>desligar</b>, a cor que cada controle tem agora é <b>gravada no perfil</b>
          na hora. Assim nenhuma se perde e nenhuma se repete: sem isso, o próximo
          controle a chegar cairia na cor global e ficaria igual ao vizinho.<br><br>
          Isto é do <b>perfil</b>. O botão <b>Automático</b> de cada coluna é outra coisa:
          ele larga a barra <i>daquele</i> controle para o jogo escolher.
        </span></span>
        <!-- O ÚNICO DESFAZER DE UMA VEZ QUE ELA TEM — LUZES-01, 06/09/2026, e
             o gêmeo é `lightbar_actions.on_lightbar_auto_reset_all`. O CSV da
             paridade mediu o perfil dela e achou DOIS `uniq` com
             `leds.lightbar` gravado: sem este botão, cada cor própria teria de
             ser desfeita uma a uma, e a interface nova não tinha um só gesto de
             escopo global nesta aba.

             O RÓTULO NÃO É "Voltar ao automático": essa é a frase LONGA que ela
             mandou encurtar em 31/08, e o curto ("Automático") já é o botão POR
             CONTROLE de cada coluna. Duas coisas diferentes na mesma tela não
             podem ter o mesmo nome. -->
        <button class="btn-todos" data-gesto="{_pacote04.GESTO_DO_AUTOMATICO_DE_TODOS}"
                title="Tira a cor própria de TODOS os controles e religa as cores automáticas. O desenho das luzes de jogador e os gatilhos ficam como estão.">Todos no automático</button>
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
                  O player é quem este controle é: o número do cabeçalho, o dos cards
                  da aba <b>Controles</b>, e o das cinco luzinhas brancas acima do
                  touchpad.<br><br>
                  <b>Isto não escolhe o que você está vendo</b> — os {len(MESA)} estão na tela. Isto
                  <b>dá</b> um número ao controle da coluna. O <b>anelzinho</b> de cada botão é
                  a cor do plástico de quem tem aquele número hoje.<br><br>
                  <!-- A FRASE PAROU DE NOMEAR CONTROLE — 03/09/2026, a lei dela.
                       Ela dizia *"pôr o Starlight Blue no 1 faz o Cosmic Red virar
                       2"*: os dois nomes do MOCKUP, numa coluna de RÓTULOS que é
                       uma só para as quatro colunas — não há "este controle" aqui
                       a que endereçar, e por isso a cura não é endereço, é dizer a
                       regra em vez do exemplo. Quem nomeia os dois de verdade é a
                       dica de cada botão da fileira (`um_botao_de_player`), que o
                       pacote reescreve a cada tique com a mesa viva. -->
                  Dar a este controle um número que já é de outro faz <b>os dois trocarem de
                  lugar</b>: quem tem aquele número hoje fica com o deste. Nunca fica um
                  número repetido, nunca fica um controle sem número — por isso a fileira
                  oferece os números que já estão em uso, e não os oito.<br><br>
                  Um jogo em co-op pode mandar o seu próprio número por cima — e aí quem
                  manda nas luzinhas é o jogo, não esta escolha.
                </span></span>
              </div>
            </div>
            <div><div class="sec-rot">LEDs</div></div>
            <div><div class="sec-rot">Opções</div></div>
          </div>

{chr(10).join(coluna(c) for c in MESA)}

        </div>

        <!-- A FOLHA VIVA DO PLÁSTICO — 03/09/2026, e ela fecha a maior
               identidade congelada desta aba: o DESENHO GRANDE.

               O QUE ESTAVA NA TELA DELA, medido nos pixels da foto (com dois
               controles na mesa, `P1 · White · USB` e `P2 · Galactic Purple · BT`):

                                  moldura (viva)        corpo desenhado
                   P1 · White     rgb(228,224,216) ✓    rgb(174,51,90)  = Cosmic Red
                   P2 · G.Purple  rgb(116,88,142)  ✓    rgb(126,184,212)= Starlight Blue

               A cura de 03/09 alcançou a MOLDURA e parou nela: a borda ficou da
               cor certa em volta de um controle da cor errada, na MESMA célula,
               com o rótulo logo abaixo dizendo o nome certo. E a aba Navegação
               desenha os MESMOS dois controles nas cores certas, no mesmo
               instante — duas abas, duas cores para o mesmo aparelho.

               POR QUE UM `<style>` E NÃO UM CAMPO: o casco lê `var(--z-casca)`,
               escrita por `svg[data-colorway="…"]` DENTRO do SVG, e o pintor não
               tem alvo que escreva variável CSS. O dono é
               `a06_navegacao.folha_do_plastico`, que a aba 06 já usa; o
               parâmetro `caixa` é o que deixa as duas compartilharem uma escrita
               só. A especificidade de `.ctrl[data-controle="p1"] .ds-svg`
               (0,3,0) vence a de dentro do SVG (0,1,1).

               VAZIO É RESPOSTA: sem leitura de cor o casco vai para
               `var(--border-forte)` — neutro —, nunca para a cor do mockup.

               FORA DA GRADE, e não dentro: `.luz-grade` é um grid de cinco
               colunas. Um `<style>` é `display:none` pela folha do navegador e
               não vira item de grade, mas pôr um elemento que não é coluna
               DENTRO da grade é convidar a próxima regra `> *` a contá-lo. -->
        <style id="plastico-vivo"></style>

      </div>
    </div>
'''

# A SEÇÃO DA TROCA É UM BLOCO VIVO — 03/09/2026, a lei dela: *"cada aba vai
# usar os controles lá de cima. Não mistura com a info dos mockups."*
#
# Ela era o maior amontoado de identidade congelada desta aba: dezesseis valores
# em oito `.troca-item`, mais quatro frases que nomeavam dois controles do
# desenho. E o rodapé NÃO é papel de parede — ele viaja no mesmo arquivo que o
# produto renderiza.
#
# O `data-hef` do contêiner declara o dono (a gramática da `10-perfis`), e o
# `blocos:` do pacote o reescreve a cada tique com `ctx.mesa`. Um dono, dois
# chamadores: `secao_da_troca` desenha a bancada aqui e o produto lá.
LEGENDA = f'''<div class="nota">
  <div class="nota-troca" data-hef="troca">
{_pacote04.secao_da_troca(MESA, recuo="    ")}
  </div>

  <h2>O que mudou hoje</h2>
  <ul>
    <li><b>O "Cores automáticas por controle" ganhou interruptor, no alto desta aba.</b>
        Ele é do <b>perfil</b>, e governa a paleta e a numeração automática — o botão
        <span class="marca">Automático</span> de cada coluna continua sendo outra coisa:
        aquele larga a barra <i>daquele</i> controle para o jogo. <b>Desligar grava a cor
        de cada controle no ato</b>, para nenhuma se perder e nenhuma se repetir. Ele não
        custou linha nenhuma: mora na faixa do título, que estava vazia à direita.</li>
    <li><b>A célula LEDs voltou a ser só o desenho.</b> Saíram as teclas
        <span class="marca">P1 P2 P3 P4</span> e os dois atalhos, o clique nas cinco
        lâmpadas e a linha de texto que dizia por que a barra apagou — pedido seu:
        <i>"só olhar a linha de cima da seleção de player e replicar o que tem lá."</i>
        Ficaram as duas tiras da barra de luz, que são o desenho original, e as cinco
        lâmpadas, que agora <b>espelham o número</b> escolhido na linha
        <span class="marca">Jogador</span> logo acima — sem escolha própria. A razão de
        uma barra tracejada continua a um rato de distância, na dica das tiras.</li>
    <li><b>O hexadecimal virou botão.</b> Clicar em <span class="marca">#0000FF</span> manda
        aquela cor ao controle de novo. Antes, uma cor escolhida à mão era a única sem
        caminho de volta: os oito tons reenviam ao serem clicados, e o seletor livre só
        avisa quando o valor muda.</li>
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
        controle do outro. Agora ele lê <span class="marca">P1 • Modelo • USB</span>,
        que é exatamente o que os chips da fita dizem 100 px acima, na mesma tela.
        <b>Aviso:</b> Controles e Conexões ainda escrevem a forma longa
        (<i>Sony • Player 1 • Modelo • USB</i>), citando a sua ordem de 26/08 — a que
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
    <li><b>Um número que ninguém está usando.</b> A fileira oferece os
        {len(NUMEROS)} números ocupados, porque troca só existe entre dois. O produto cobre 1 a 8
        (<code>core/led_control.py</code>) — se um dia for preciso pôr um DualSense no 5 com
        quatro ligados, isso é <i>mover</i>, não trocar, e é outra decisão sua.</li>
    <li><b>O "Desligar" guarda a cor ou grava preto?</b> A dica de hoje promete uma coisa e o
        código faz a outra (<code>lightbar_actions.py:1023</code>).</li>
    <li><b>Ajustar os quatro de uma vez?</b> Não há mais alvo único nesta aba, então um
        "aplicar a todos" teria de ser um botão próprio — e ele não existe.</li>
  </ul>
</div>

</body>
</html>
'''

# Fora de `monta.ABAS_QUE_ESCOLHEM` — decisão dela, 28/08/2026: em Gatilhos, Iluminação e
# Vibração os quatro ficam lado a lado, sempre visíveis, e a fita fica
# esmaecida. Ela não é o alvo desta aba porque não há alvo: cada coluna se
# ajusta no seu lugar.
#: O RECORTE DE UMA COLUNA. `ctrl` seguido de `"` (a viva) ou de espaço
#: (`ctrl vazia`) — `ctrl-rot` tem um `-` na terceira posição e não casa, que é
#: a armadilha que o `COMO-OLHAR-A-TELA.md` nomeia e que já cegou a régua §4.
_UMA_COLUNA = re.compile(r'<div class="ctrl([" ][^>]*?)>(.*?)(?=<div class="ctrl[" ]|\Z)',
                         re.S)

#: O MIOLO DE UM BLOCO DE ALVO `html`, para descontá-lo do contrato do cartão —
#: ver a §14. Os dois desta aba (`players` e `aceso`) não têm `<div>` por
#: dentro; a §14 confere isso antes de confiar neste recorte.
_MIOLO_DO_ALVO_HTML = re.compile(
    r'(<div class="(?:players|aceso)"[^>]*data-hef-alvo="html"[^>]*>).*?</div>', re.S)


#: O QUE ESCONDE CADA WIDGET DE GESTO ENQUANTO O LUGAR NÃO TEM DONO — a
#: segunda metade da §4, e ela existe porque a cura de 07/09/2026 trocou o
#: mecanismo da decisão dela. Até 06/09 *"um lugar sem aparelho não oferece
#: gesto nenhum"* era cumprido pela AUSÊNCIA do widget; a partir de hoje é
#: cumprido por ESTA folha, e o widget nasce nos quatro lugares para que o
#: controle que chega o encontre pronto.
#:
#: A CHAVE É A CLASSE DO PRÓPRIO ELEMENTO, e o valor é o pedaço de seletor que
#: tem de estar na folha. A régua lê as classes do HTML emitido e cobra que ao
#: menos uma esteja aqui: um widget novo, com classe que ninguém escondeu,
#: reprova sem que ninguém se lembre de acrescentá-lo a lista nenhuma.
#:
#: `hex` NÃO SOME, e é a única exceção: aquele `<span>` É o travessão da célula
#: `Cor` — o mesmo elemento que mostra `#0000FF` na coluna viva. O que se apaga
#: nele é o CLIQUE.
_COBERTURA_SEM_DONO = {
    "tom": '.luz-grade .ctrl[data-conectado="nao"] .guia',
    "livre": '.luz-grade .ctrl[data-conectado="nao"] .guia',
    "puxador": '.luz-grade .ctrl[data-conectado="nao"] .trilho',
    "btn": '.luz-grade .ctrl[data-conectado="nao"] .cel-acoes .btn',
    "hex": '.luz-grade .ctrl[data-conectado="nao"] .cel-cor .hex.reenvia{pointer-events:none',
}

#: O `class=` QUE NÃO EXISTE, para a §4 não precisar de um `if` no meio do laço.
_SEM_CLASSE = re.compile(r"()").match("")


def _cada_coluna(colunas):
    """As colunas da grade, separadas em (vazias, conectadas).

    UM RECORTE SÓ PARA AS TRÊS RÉGUAS QUE O USAM — §4, §12 e §14. Ele vivia
    escrito duas vezes, com duas expressões diferentes, e a de baixo dependia
    de o lugar vazio NÃO ter uma `.cel-leds`: quando ele passou a ter (a função
    única, 07/09/2026), a régua das doze teclas cobrou de quatro colunas o que
    só duas podem ter. Recorte duplicado envelhece pela metade, que é o mesmo
    defeito que a `coluna_vazia` era.
    """
    vazias, cheias = [], []
    for atributos, miolo in _UMA_COLUNA.findall(colunas):
        (vazias if "vazia" in atributos else cheias).append(atributos + ">" + miolo)
    return vazias, cheias


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

    # 4. OS GESTOS NASCEM NOS QUATRO LUGARES, E O LUGAR SEM DONO NÃO OFERECE
    #    NENHUM — 07/09/2026, e esta régua foi REESCRITA neste dia.
    #
    #    O QUE ELA MEDIA ATÉ ONTEM: que a coluna vazia não tinha `data-gesto`,
    #    nem `<input`, nem `<button`. Estava certa sobre a DECISÃO dela (*um
    #    lugar sem aparelho não oferece gesto nenhum*, 31/08/2026) e errada
    #    sobre o MUNDO: ela cobrava a ausência do widget, quando o que a decisão
    #    pede é a ausência do GESTO. Enquanto o widget não nascia, o P3 que
    #    ganhava um controle ficava sem guia de cores, sem puxador de brilho e
    #    sem os dois botões de Opções — o piloto vira marca e escreve campo, não
    #    materializa HTML —, e só recarregar a página desfazia. Medido nas
    #    páginas publicadas em 07/09/2026: `data-gesto` por lugar dava
    #    `p1=9 · p2=9 · p3=0 · p4=0` nesta aba, contra os quatro iguais em todas
    #    as outras. Com os quatro DualSense dela na mesa, ela não conseguia
    #    trocar a cor do P3 pela tela.
    #
    #    O QUE ELA COBRA AGORA, e são três metades. Afrouxá-la seria apagar as
    #    três — uma régua que só some não mede nada.
    #
    #    A PRIMEIRA: o conjunto de `data-gesto` é o MESMO nos quatro lugares.
    #    É o irmão da §14 (que faz isso com `data-campo`) e é a linha que morde
    #    a cura: devolver um `if ligado else ""` a qualquer dos widgets faz esta
    #    régua nomear o lugar e o gesto que sumiram.
    #
    #    E O RECORTE É DENTRO DA GRADE, e não do miolo inteiro: a ÚLTIMA coluna
    #    termina onde a grade termina, e um `\Z` a fazia engolir o RODAPÉ — os
    #    quatro botões `Aplicar`/`Salvar`/`Exportar`/`Importar`, que são do
    #    esqueleto das dez páginas e não pertencem a coluna nenhuma. Medido em
    #    03/09/2026: com o `\Z`, o segundo bloco tinha 48.131 caracteres e a
    #    régua acusava `<button` num lugar vazio que não tem botão nenhum.
    grade = corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
    #
    #    E ELA DESCONTA OS BLOCOS DE ALVO `html` DOS DOIS LADOS, pela mesma
    #    razão da §14 e com o mesmo recorte: `players` e `aceso` são buracos que
    #    o pacote preenche com HTML inteiro a cada tique, e o que mora lá dentro
    #    é contrato DELE. Quatro dos nove gestos desta aba são de lá — `player`,
    #    `luzes`, `desenho-de` e `reenviar-desenho` —, e eles JÁ chegavam aos
    #    quatro lugares antes desta cura, porque nascem com o bloco que os
    #    carrega. Cravá-los no lugar vazio só para o conjunto fechar seria régua
    #    medindo a própria saída, que é a armadilha nomeada no `ONDE PARAMOS` de
    #    07/09/2026. Os CINCO que faltavam de verdade — `cor`, `brilho`, `auto`,
    #    `apagar` e `reenviar` — são os do cartão, e são estes que a régua conta.
    gestos_por_lugar = {}
    vazias, cheias = _cada_coluna(grade)
    for coluna_html in vazias + cheias:
        pref = re.search(r'data-controle="([^"]+)"', coluna_html)
        if pref:
            gestos_por_lugar[pref.group(1)] = sorted(set(re.findall(
                r'data-gesto="([^"]+)"',
                _MIOLO_DO_ALVO_HTML.sub(r"\1</div>", coluna_html))))
    exigir(len(gestos_por_lugar) == len(MESA),
           f"a grade tem {len(gestos_por_lugar)} lugares e a mesa tem {len(MESA)}")
    de_referencia = gestos_por_lugar.get(MESA[0]["pref"], [])
    for pref, gestos in sorted(gestos_por_lugar.items()):
        faltam = sorted(set(de_referencia) - set(gestos))
        sobram = sorted(set(gestos) - set(de_referencia))
        exigir(not faltam,
               f"o lugar {pref} não oferece {faltam} — o controle que chegar "
               f"ali não terá esse gesto na tela, porque o piloto vira marca e "
               f"escreve campo, e não materializa widget: só recarregar a "
               f"página desfaz")
        exigir(not sobram,
               f"o lugar {pref} oferece {sobram}, que o lugar cheio não tem — "
               f"o conjunto tem de ser IGUAL, não maior")

    #    A SEGUNDA: cada widget de gesto que o lugar vazio carrega está COBERTO
    #    por uma regra desta folha que o esconde enquanto `data-conectado="nao"`
    #    — a marca que o piloto vira nos dois sentidos (`hefesto_vivo`, passos
    #    `1b` e `1c`), e não a classe de NASCIMENTO `.vazia`, que só responde
    #    por um dos dois estados.
    #
    #    A COBERTURA É LIDA DO HTML, e não digitada: a régua acha as tags com
    #    `data-gesto` dentro da coluna vazia, tira as classes DELAS, e cobra que
    #    alguma esteja no mapa `_COBERTURA_SEM_DONO`. Um widget novo, com classe
    #    que ninguém escondeu, reprova sozinho — que é o contrário da lista
    #    escrita à mão, cuja falha é silenciosa (o esquecimento não avisa).
    for coluna_html in _cada_coluna(grade)[0]:
        exigir("cel-brilho" in coluna_html,
               "a régua do lugar vazio não alcança as células da coluna — ela "
               "voltou a dar verde sobre o desenho, que é onde nunca houve "
               "ajuste nenhum")
        for tag in re.findall(r"<[a-z]+[^>]*data-gesto=[^>]*>", coluna_html):
            classes = set(re.findall(
                r"[\w-]+", (re.search(r'class="([^"]*)"', tag) or _SEM_CLASSE).group(1)))
            cobre = sorted(classes & set(_COBERTURA_SEM_DONO))
            exigir(cobre,
                   f"um lugar vazio ganhou um gesto que nenhuma regra esconde: "
                   f"{tag[:90]!r} — sem cobertura ele aceita o clique, e os "
                   f"endereços dessa coluna levantam `o clique não disse em "
                   f"qual controle`, que o cartão do piloto não leva à tela "
                   f"(só `RuntimeError` chega lá): botão que engole o toque")
            for classe in cobre:
                exigir(_COBERTURA_SEM_DONO[classe] in doc,
                       f"a regra que esconde `.{classe}` no lugar sem dono "
                       f"sumiu da folha: {_COBERTURA_SEM_DONO[classe]!r}")

    #    A TERCEIRA: a ESTRUTURA vem, o VALOR não. Um lugar sem dono não carrega
    #    a cor nem o brilho do MOCKUP — é a lei da
    #    `scripts/check_a_cor_vem_do_aparelho.py` e o item 2 da docstring de
    #    `coluna()`. Os quatro valores cravados desta coluna, um a um.
    for coluna_html in _cada_coluna(grade)[0]:
        exigir("class=\"tom on\"" not in coluna_html,
               "um lugar vazio marca uma cor escolhida — `luz(j)` é a cor "
               "AUTOMÁTICA daquele número, e ali não há controle que a tenha "
               "escolhido")
        exigir('value="#000000"' in coluna_html,
               "o seletor livre do lugar vazio deixou de nascer neutro — o "
               "`value` passa a ser a cor que o DESENHO deu àquele número")
        exigir('class="puxador"' in coluna_html and 'value="0"' in coluna_html,
               "o puxador do lugar vazio não nasce em zero — brilho cravado "
               "num lugar sem dono é o brilho do MOCKUP na tela dela")
        exigir("style=\"width:" not in coluna_html,
               "a barra de brilho do lugar vazio nasceu com largura")
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
           "a cor escolhida não está marcada em todos os controles ligados")

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

    # 8. O DESENHO VESTE O APARELHO, e as quatro metades vão conferidas na SAÍDA.
    #    Esta régua olha o `doc` inteiro para o que é da PÁGINA e o `corpo` para
    #    o que é das COLUNAS — as cores do mapa são uma peça só da página.
    exigir(doc.count('id="cores-do-dualsense"') == 1,
           "as cores do mapa não estão UMA vez na página — ou voltaram para "
           "dentro dos SVGs (cada desenho sabendo pintar um modelo só), ou "
           "saíram de vez")
    modelos = len(set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]', doc)))
    do_mapa = len(set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]',
                                 monta_.DS)))
    exigir(modelos == do_mapa,
           f"a página conhece {modelos} modelos e o mapa dela tem {do_mapa}")
    #    OS FUNDOS TÊM DE SER ALCANÇÁVEIS. Três modelos pintam com `url(#…)` —
    #    prefixados dentro de um SVG, o `url()` da folha subida não os acha, e
    #    eles pintam NADA. Foi medido no Chrome antes de virar régua.
    for alvo in sorted(set(re.findall(r"url\(#([a-zA-Z0-9_-]+)\)", doc))):
        exigir(f'id="{alvo}"' in doc,
               f"a folha aponta para `url(#{alvo})` e a página não tem esse id "
               f"— o modelo que usa esse fundo pinta nada")
    #    E SÃO OS QUATRO, não os dois — reescrita em 07/09/2026. Esta linha
    #    cobrava o endereço só nas colunas CONECTADAS, e com isso media o  # noqa-acento: verbo medir, imperfeito
    #    defeito em vez de medi-lo: o desenho do lugar vazio saía sem
    #    `data-campo="desenho"`, e o produto não tinha por onde vesti-lo quando
    #    o controle chegasse. O desenho reaparece sozinho (a folha das dez tem
    #    `[data-conectado="nao"] .ds-svg{display:none}`, e o piloto vira essa
    #    marca nos dois sentidos) — reaparecia sem colorway nenhum, no cinza
    #    padrão, para sempre. O VALOR continua só nos conectados; é o que a
    #    linha do `data-colorway` logo abaixo cobra.
    exigir(corpo.count(ENDERECO_DO_DESENHO) == len(MESA),
           "algum desenho da grade não pede o alvo do atributo — sem ele o "
           "pintor escreve o colorway como TEXTO e apaga o desenho, e o lugar "
           "que ganha controle fica com um desenho vestido de nada")
    #    E O LUGAR VAZIO NÃO CARREGA COLORWAY NENHUM: o único `data-colorway`
    #    que sobra nas colunas é o das conectadas, e ele é o valor de PARTIDA
    #    que o primeiro tique substitui.
    colunas = corpo.split('<div class="luz-grade">', 1)[-1]
    exigir(colunas.count("data-colorway=") == len(monta_.CONECTADOS),
           "há `data-colorway` fora das colunas conectadas — identidade do "
           "mockup parada num lugar sem aparelho")

    # 9. O INTERRUPTOR DO AUTOMÁTICO — D-13, e as TRÊS metades dele.
    #
    #    A PRIMEIRA é o lugar: ele é o interruptor "no topo da aba", e o topo
    #    desta aba é a faixa do título do quadro. Fora dela ele custaria uma
    #    linha da grade, que é o custo de 30px que ela aceitou pagar e que esta
    #    conta não precisou cobrar.
    topo = corpo.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    exigir('class="chave-auto"' in topo,
           "o interruptor das cores automáticas saiu da faixa do título — a "
           "D-13 pede ele NO TOPO da aba, e qualquer outro lugar cobra uma "
           "linha da grade que já está a 4px do teto")
    #    A SEGUNDA é o ENDEREÇO, e sem ele o interruptor é desenho: um
    #    `<input type="checkbox">` sem `data-hef-alvo="marcado"` fica congelado
    #    no `checked` que este gerador escreveu, e passa a afirmar o estado do
    #    MOCKUP sobre o perfil dela. Os três atributos vão juntos porque é
    #    assim que o piloto lê — `escrever()` só toca `el.checked` no alvo
    #    `marcado`, e só acha o elemento pelo `data-campo`.
    for atributo in (f'data-gesto="{_pacote04.ENDERECO_DO_AUTOMATICO}"',
                     f'data-campo="{_pacote04.ENDERECO_DO_AUTOMATICO}"',
                     'data-hef-alvo="marcado"'):
        exigir(atributo in topo,
               f"o interruptor perdeu {atributo!r} — sem os três ele é uma "
               f"chave que não lê o perfil nem o muda")
    #    A TERCEIRA é a DICA ABRINDO PARA A ESQUERDA. Medido: a `.dica` tem
    #    330px e nasce em `left:22px`; num `?` encostado na direita de um quadro
    #    de 1142 ela sairia da janela de 1180. A regra é a peça, e sem ela a
    #    explicação do martelo mais pesado da aba fica meio fora da tela.
    exigir(".quadro-topo .ajuda.esq .dica{left:auto;right:22px}" in doc,
           "a dica do interruptor voltou a abrir para a direita — ela tem "
           "330px e o `?` está encostado na borda do quadro")

    # 10. A CÉLULA `LEDs` É SÓ O DESENHO — 07/09/2026, ordem dela: *"só olhar a
    #     linha de cima da seleção de player e replicar o que tem lá."*
    #
    #     ESTA RÉGUA MEDE UMA AUSÊNCIA, e por isso ela tem de nomear o que não
    #     pode voltar. Entre 04/09 e hoje esta faixa teve uma linha de ressalva
    #     (D-02) e, desde 06/09, doze teclas de desenho; as duas saíram por
    #     ordem dela, e as duas voltariam calado — a de ressalva por um `luz-
    #     ressalva` reposto no pacote, as teclas por um `bits=` devolvido à
    #     `desenho_da_luz`. Um endereço que o pacote emite e a página não tem é
    #     ÓRFÃO no piloto: escreve-se em nada, tique após tique, sem erro.
    exigir('data-campo="luz-ressalva"' not in colunas,
           "a linha de ressalva voltou à célula dos LEDs — ela saiu por ordem "
           "dela em 07/09/2026 (*'o que eu não quero é frase da steam ou "
           "outras'*), e a razão da barra apagada continua no `title` das duas "
           "tiras, escrita pela `dica_da_luz` a cada tique")
    #     E NENHUM GESTO MORA AQUI. As cinco lâmpadas são ESPELHO do número —
    #     quem escolhe o número é a linha `Jogador`, uma célula acima. Um
    #     `data-gesto` nesta faixa é o desenho voltando a oferecer uma segunda
    #     maneira de mexer nas mesmas luzes, que é exatamente o que ela mandou
    #     tirar: *"pq tá surgindo os leds no lado da iluminação se acima já tem
    #     o canto dos players?"*
    for bloco in re.findall(
            r'<div class="cel-leds">(.*?)</div>\s*</div>',
            "\n".join(_cada_coluna(grade)[1]), re.S):
        exigir("data-gesto=" not in bloco,
               "um gesto voltou à célula dos LEDs — ela é desenho de leitura "
               "desde 07/09/2026, e as cinco lâmpadas espelham o número sem "
               "escolha própria")
        exigir('class="luzinhas"' in bloco,
               "as cinco lâmpadas do indicador sumiram da célula dos LEDs — "
               "sem elas a coluna deixa de replicar a linha `Jogador`")
        exigir(bloco.count('class="tira-luz') == 2,
               "a barra de luz deixou de ter as DUAS tiras — elas são o "
               "desenho original, e ela mandou que ficassem")

    # 11. A CAIXA DO HEXADECIMAL É O BOTÃO — decisão [03] dela.
    #
    #     E ELA NÃO LEVA `data-hex`: esse atributo é escrito pelo gerador e fica
    #     congelado no que o mockup sabia. Um reenvio por ele mandaria ao
    #     plástico dela a cor do DESENHO; o gesto lê o `textContent`, que o
    #     produto reescreve a cada tique. As duas metades vão juntas porque a
    #     segunda é a que morde: só a primeira daria verde sobre um botão que
    #     reenvia a cor errada.
    #
    #     E SÃO OS QUATRO desde 07/09/2026, pela mesma razão do endereço do
    #     desenho e da linha de ressalva: cobrar a caixa só nas conectadas
    #     deixava o P3 que GANHA um controle com a única maneira de reenviar a
    #     cor congelada em nunca — o piloto não materializa widget. No repouso
    #     ela não aceita o clique: a folha desta aba apaga o `pointer-events` e
    #     a borda de botão enquanto `data-conectado="nao"`, e é a §4 que cobra
    #     essa cobertura.
    caixas = re.findall(r'<span class="hex reenvia"[^>]*>', colunas)
    exigir(len(caixas) == len(MESA),
           "a caixa do hexadecimal não virou botão em todas as colunas")
    for caixa in caixas:
        exigir('data-gesto="reenviar"' in caixa,
               "a caixa do hexadecimal perdeu o gesto de reenvio")
        exigir("data-hex=" not in caixa,
               "a caixa do hexadecimal ganhou `data-hex` — o gesto passaria a "
               "reenviar a cor CRAVADA no desenho, e não a que está na tela")

    # 12. AS CINCO LÂMPADAS ESPELHAM O NÚMERO — 07/09/2026, e é a linha que
    #     esta leva fecha. Ela SUBSTITUI a régua da LUZES-01, que cobrava aqui
    #     as doze teclas da botoeira (cinco lâmpadas clicáveis, seis desenhos e
    #     a moldura do reenvio). A ordem dela desfez a botoeira inteira, e uma
    #     régua que continuasse a cobrá-la reprovaria a decisão em vez do
    #     defeito — que é o erro que esta casa já pagou onze vezes num dia.
    #
    #     O QUE ELA MEDE AGORA: o padrão aceso na célula `LEDs` é o do número
    #     daquela coluna, e não de outro. É a réplica que ela pediu — *"só
    #     olhar a linha de cima da seleção de player e replicar o que tem lá."*
    #
    #     O PADRÃO NÃO SE DIGITA: ele é perguntado a `monta.luzinhas`, que sai
    #     de `core/led_control.player_led_pattern` — o MESMO que o daemon
    #     acende. Escrever aqui `<i class="on">` na posição que eu achasse certa
    #     seria a régua medindo a minha memória, e não o produto.
    for coluna_html in _cada_coluna(grade)[1]:
        jogador = re.search(r'data-campo="identidade">P(\d)', coluna_html)
        exigir(bool(jogador), "uma coluna conectada perdeu o número no rótulo")
        if not jogador:
            continue
        n = int(jogador.group(1))
        leds = re.search(r'<div class="cel-leds">(.*?)</div>\s*</div>',
                         coluna_html, re.S)
        exigir(bool(leds), f"o P{n} perdeu a célula dos LEDs")
        if not leds:
            continue
        esperado = monta_.luzinhas(n)
        exigir(esperado in leds.group(1),
               f"as cinco lâmpadas do P{n} não desenham o padrão do número {n} "
               f"— a célula LEDs deixou de replicar a linha `Jogador`, que é o "
               f"que ela mandou em 07/09/2026")

    # 13. O ESCOPO GLOBAL — "Todos no automático", e ele mora na MESMA faixa do
    #     interruptor, pela mesma razão medida da §9: a grade das colunas está
    #     no teto do `.miolo` (medido no Chrome: 526px de quadro para 564 de
    #     caixa, e os 38 restantes são o rodapé). Fora da faixa ele custaria
    #     linha, e dentro de uma coluna mentiria sobre o alcance.
    exigir(f'data-gesto="{_pacote04.GESTO_DO_AUTOMATICO_DE_TODOS}"' in topo,
           "o `Todos no automático` saiu da faixa do título — é o único "
           "desfazer de uma vez que ela tem, e dentro de uma coluna ele "
           "afirmaria mexer só naquele controle")
    #     E O NOME NÃO COLIDE: `Automático` é o botão POR CONTROLE de cada
    #     coluna desde 31/08 (ordem dela, encurtando "Voltar ao automático").
    #     Duas coisas diferentes na mesma tela não podem ter o mesmo nome.
    exigir(">Todos no automático</button>" in topo,
           "o botão de escopo global perdeu o rótulo que o separa do "
           "`Automático` de cada coluna")

    # 14. OS QUATRO LUGARES TÊM OS MESMOS ENDEREÇOS — 07/09/2026, e é a régua
    #     que impede este defeito de voltar.
    #
    #     O QUE ELA MEDE: o conjunto de `data-campo` que o CARTÃO emite tem de
    #     ser o mesmo nos quatro lugares — igual, não maior. É por `data-campo`
    #     que o piloto acha onde escrever (`hefesto_vivo`, passo 2:
    #     `for(const el of achar(raiz, k))`, e `achar` procura dentro do bloco
    #     daquele `data-controle`). Um lugar sem o endereço é um lugar onde o
    #     dado dela chega e não tem onde pousar.
    #
    #     O QUE ELA TERIA PEGO: medido na página publicada em 07/09/2026, antes
    #     desta cura — `p1: 20 data-campo (10 distintos)`, `p2: 20 (10)`,
    #     `p3: 0 (0)`, `p4: 0 (0)`. Com os quatro DualSense dela na mesa, o
    #     daemon publicava quatro controles e a tela mostrava DOIS.
    #
    #     E ELA DESCONTA OS BLOCOS DE ALVO `html` DOS DOIS LADOS. O `players` e
    #     o `aceso` são buracos que o pacote preenche com HTML inteiro a cada
    #     tique: o que mora lá dentro é contrato DELE, não deste gerador.
    #
    #     O CASO É O `luz-incerta`, e o pacote diz isso com todas as letras
    #     (`pacotes/a04_iluminacao.py`, na chave `ENDERECO_DA_INCERTA`): *"ele
    #     vem DEPOIS do `luz` de propósito. O `luz` troca o miolo do `.aceso`
    #     inteiro (alvo `html`) e RECRIA as duas tiras"*. O endereço dele nasce
    #     com o bloco que o carrega, no mesmo tique, nos quatro lugares —
    #     cravar uma tira escondida no lugar vazio só para o conjunto fechar
    #     seria régua medindo a própria saída, que é a armadilha nomeada no
    #     `ONDE PARAMOS` de 07/09/2026.
    campos_por_lugar = {}
    vazias, cheias = _cada_coluna(grade)
    for coluna_html in vazias + cheias:
        pref = re.search(r'data-controle="([^"]+)"', coluna_html)
        if not pref:
            continue
        #     A PREMISSA DO DESCONTO VAI CONFERIDA, e não suposta: o recorte do
        #     miolo por `</div>` só é exato porque nem o `players` nem o
        #     `aceso` têm `<div>` por dentro. No dia em que tiverem, esta linha
        #     reprova em vez de a §14 passar a descontar demais.
        for buraco in _MIOLO_DO_ALVO_HTML.finditer(coluna_html):
            exigir("<div" not in buraco.group(0)[len(buraco.group(1)):],
                   "um bloco de alvo `html` ganhou um `<div>` por dentro — o "
                   "desconto da §14 recorta pelo primeiro `</div>` e passaria a "
                   "engolir metade da coluna")
        so_do_cartao = _MIOLO_DO_ALVO_HTML.sub(r"\1</div>", coluna_html)
        campos_por_lugar[pref.group(1)] = set(
            re.findall(r'data-campo="([^"]+)"', so_do_cartao))
    exigir(len(campos_por_lugar) == len(MESA),
           f"a grade tem {len(campos_por_lugar)} lugares endereçados e a mesa "
           f"tem {len(MESA)}")
    referencia = campos_por_lugar.get(MESA[0]["pref"], set())
    for pref, campos in sorted(campos_por_lugar.items()):
        faltam = sorted(referencia - campos)
        sobram = sorted(campos - referencia)
        exigir(not faltam,
               f"o lugar {pref} não tem onde pousar {faltam} — o dado dela "
               f"chega e o piloto não acha o campo dentro do bloco")
        exigir(not sobram,
               f"o lugar {pref} tem endereço que o lugar cheio não tem "
               f"({sobram}) — o conjunto tem de ser IGUAL, não maior")

    if falhas:
        raise SystemExit("ERRO em 04-iluminacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


#: AS DUAS MEDIDAS DA PRIMEIRA COLUNA, injetadas do dono (`medidas.py`). Elas não
#: podem ser digitadas no bloco `CSS` acima porque ele é uma string crua — e um
#: número digitado ali seria a terceira cópia do mesmo valor, que é o defeito que
#: `medidas.py` nasceu para matar.
CSS_DAS_MEDIDAS = f"""
  .luz-grade{{
    --larg-rot:{monta_.larg_rotulos('04-iluminacao')}px;
    --gap-col:{monta_.GAP_DAS_COLUNAS}px;
  }}
"""


# A ESCRITA MORA DEBAIXO DO `__main__`, e isto é cura de defeito MEDIDO em
# 06/09/2026: `import aba04` REESCREVIA a bancada dela como efeito de um
# import. Bastava o pytest COLETAR
# `tests/unit/test_a_vibracao_diz_qual_degrau_esta_aceso.py` — que importa
# `aba05` no topo — para `mockup/05-vibracao.html` mudar no disco, com a
# contagem VIVA de controles dentro: `1 USB · 1 BT` virou `0 USB · 0 BT`
# porque os controles não estavam ligados naquele instante. A régua do desenho
# aprovado passava a reprovar por causa do que estava na tomada.
#
# A ironia estava escrita: o próprio teste avisa, na docstring, que *"importar
# `aba05` REESCREVE a bancada dela como efeito de um `import`, e uma régua não
# mexe no que mede"* — e importava assim mesmo. A `aba01` e a `aba02` já tinham
# esta guarda desde que `jogar_vivo.py` e `controles_vivos.py` passaram a
# importá-las; as outras oito não.
if __name__ == "__main__":
    n = monta("04-iluminacao", "Iluminação", MIOLO, CSS + CSS_DAS_MEDIDAS,
              legenda=LEGENDA)
    _conferir(onde.pagina("04-iluminacao.html").read_text())
    print(f"04-iluminacao: OK, {n} divs · {len(monta_.CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s) · "
          f"números {NUMEROS} · respiro 5px, a divisória no meio do vão")
