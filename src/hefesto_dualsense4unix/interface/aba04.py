import json, sys, pathlib, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
import monta as monta_
from itertools import cycle
from monta import (monta, trava_do_nativo, svg, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, player_slot_color, tom_da_casa)
from pacotes import a04_iluminacao as _pacote04
from pacotes.meus_efeitos import TETO_DO_NOME
from hefesto_dualsense4unix.profiles.schema import (
    RITMO_MAXIMO_DA_LUZ, RITMO_MINIMO_DA_LUZ, RITMO_PADRAO_DA_LUZ)

#


def luz(jogador):
    """A cor automática da barra do controle de número `jogador`, dita pelo produto."""
    return "#%02X%02X%02X" % player_slot_color(jogador)


# ESTA ABA JÁ TINHA VESTIDO A MOLDURA (`data-campo="plastico"`, alvo `cor`) e a
# MOCKUP era o maior objeto da tela: o próprio DualSense desenhado, 146 px de

ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo" '
                       'data-hef-atributo="data-colorway"')

#: modelos pintando com `url(#…)`: `hachura-sem-hex` (a trama de "zona sem hex
_BLOCO_DAS_CORES = re.compile(
    r'[ \t]*<defs id="[^"]*cores-do-dualsense">.*?</defs>\n?', re.S)


def _cores_do_mapa(x, quem):
    """O `<defs>` das cores como o gerador o deixou — para a página emiti-lo uma vez."""
    m = _BLOCO_DAS_CORES.search(x)
    if m is None:
        raise SystemExit(f"ERRO em {quem}: o `<defs>` das cores sumiu do "
                         f"desenho — rode scripts/gerar_cores_do_dualsense.py")
    return m.group(0)


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
    com os quatro DualSense do usuário na mesa: `[data-controle="p3"]` tinha ZERO
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


DONO = {c["jogador"]: c for c in MESA}

NUMEROS = sorted(c["jogador"] for c in MESA)

_b = cycle((82, 100, 70, 45))
BRILHO = {c["pref"]: next(_b) for c in MESA}

#: O QUE ELAS ERAM: as primárias cruas que `player_slot_color` devolve —
#: #0000FF, #FF0000, #00FF00, #FF0080, #FFFF00… Cor de monitor de teste, com
#: `core/led_control.player_slot_color` continua devolvendo as primárias, e
CRUS_DA_GUIA = ["#%02X%02X%02X" % rgb for rgb in _pacote04.tons_da_guia()]
TONS = [tom_da_casa(h) for h in CRUS_DA_GUIA]



CSS_DA_LUZ_NO_DESENHO = "  " + _pacote04.tokens_da_luz()

CSS = """
  /* ---------- Iluminação ---------- */
  /* UMA GRADE SÓ: uma coluna de rótulos e uma coluna por controle da MESA.
     É a mesma gramática da Vibração, que o usuário aprovou em 27/08 ("viu esses
     detalhes que eu pedi? eu quero esse refinamento em todas as demais").
     As sete linhas são compartilhadas pelas cinco colunas, e é isso que faz o
     rótulo "Brilho" ficar na mesma linha dos quatro trilhos e as cinco colunas
     acabarem no MESMO y — a cura do vão é na ALTURA, nunca `space-between`.

     ANTES ELA ERA OUTRA COISA: uma fileira de quatro desenhos em cima e um
     grid 2x2 de seções embaixo, que ajustavam UM controle — o que a fita
     apontava. Com a fita esmaecida (decisão, 28/08) esse alvo deixou de
     existir, e as seções desceram para dentro das colunas.

     AS ALTURAS SÃO TOKENS porque a soma é o orçamento: 146+16+46+26+52+64+64
     = 414, mais seis passos de 10 = 474, contra o teto de 476 que a caixa do
     miolo oferece. Mexer numa linha sem tirar de outra faz a aba rolar por
     dentro — e quadro que rola por dentro é conteúdo que ninguém sabe que
     existe. O teto sai da MEDIÇÃO, não de uma conta: o `.miolo` dá 564px de
     caixa, 34 vão nos paddings dele e 54 no cromo do quadro (as duas bordas,
     os 17px da faixa do título com o seu padding, e os 24 do corpo). */
  /* A LINHA NÃO PODE QUEBRAR NOS VÃOS — 30/08/2026, pedido: *"as linhas
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
       acabava em x=536 numa e x=542 na outra. O usuário viu: *"tem algo que
       deixa estranho essa área da primeira coluna."* */
    /* AS QUATRO COLUNAS TÊM A MESMA LARGURA E O RESPIRO É SIMÉTRICO (desenho do todo, 14/10/2026):
       a divisória é a borda da fatia, o vão entre colunas virou padding dos dois lados dela, a
       coluna dos nomes leva o vão consigo e a última fatia vai até a borda do quadro. */
    grid-template-columns:calc(var(--larg-rot) + var(--gap-col)) repeat(4,minmax(0,1fr));
    column-gap:0;margin-right:-14px;
    --r-des:92px;--r-nome:30px;--r-cor:66px;--r-brilho:26px;
    /* A LINHA DE RESSALVA CABE NA LINHA DOS LEDs — 04/09/2026, decisão de produto
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

       A COLUNA VAI DE 460 PARA 472, contra o teto de 476. O par dos modos
       mora na faixa do TÍTULO do quadro (06/10/2026). */
    /* AS TRÊS PÍLULAS DO BRILHO DAS LUZES MORAM NA LINHA DOS LEDs — 24/09/2026,
       decisão de produto (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): *"Fraco,
       Médio e Forte na linha LEDs, nascendo no Fraco"*. Elas pedem 30px
       (24 de pílula e 6 de vão) debaixo da tira de 34: `--r-leds` vai de 56
       para 64 e `--r-acoes` de 72 para 64. OS OITO SAEM DA LINHA OPÇÕES porque
       ela sobrava: tem UM botão desde 07/09/2026, e ele mede 34px dentro dos
       72 — a coluna continua em 472 e o teto de 476 não é tocado. */
    --r-player:52px;--r-leds:64px;--r-acoes:48px;
    /* O RESPIRO É O DONO, E O PASSO É O DOBRO DELE — 31/08/2026, pedido:
       *"aba iluminação tem a mesma questão do respiro vertical."* É a mesma
       construção da Vibração (30/08) e da Gatilhos (hoje), e o mesmo valor da
       Vibração: 5.
       MEDIDO ANTES: o passo era 8 e a divisória ficava em `top:0` — encostada no
       conteúdo de cima, com o vão INTEIRO embaixo. `a_divisoria_sobe: [0]`.
       O QUE ELE CUSTA: o passo vai de 8 para 10, e 2px em seis vãos são 12. A
       coluna foi de 448 para 460, contra o teto MEDIDO de 476.
       A parte que NÃO custa nada é a que arruma o feio: descer a linha meio
       passo só muda de que lado dela o vão está.
       A FOLGA DE HOJE É 2px, e não os 16 de então: a linha de ressalva de
       04/09 comeu doze — ver a nota do `--r-leds` acima —, e a linha da cor
       do dono, a 6 px em 08/10/2026, comeu dois no `--r-cor`. */
    --r-ar:6px;--r-passo:calc(var(--r-ar) * 2);
  }
  /* Em janela baixa o desenho encolhe, a linha do Jogador aperta e o passo entre as linhas cai. */
  @media (max-height:780px){.luz-grade{--r-des:54px;--r-player:40px;--r-cor:60px;--r-ar:5px}}
  .luz-grade > .rotulos{padding-right:var(--gap-col)}
  .luz-grade > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-cor) var(--r-brilho)
                       var(--r-player) var(--r-leds) var(--r-acoes);
  }
  /* a barra vertical entre blocos irmãos — pedido */
  /* O PADDING SAIU DA COLUNA E FOI PARA AS CÉLULAS — 30/08/2026.
     A borda separadora mora na CÉLULA (`> div > *`), e padding na coluna
     recua a célula junto: a linha parava 21px antes da divisa e voltava a
     ler como tracinho. Com o padding na célula, ela vai de ponta a ponta da
     coluna e encosta na vizinha — o respiro do conteúdo é o mesmo. */
  .luz-grade .ctrl{border-left:1px solid var(--linha);padding:0 14px 0 13px}
  /* A linha da luz do jogo: uma frase curta embaixo das cores, sem botão. Texto de apoio
     (nunca vermelho), com o «Agora» em tinta cheia só quando o jogo está pintando. */

  /* ---------- O LUGAR SEM CONTROLE ----------
     UMA marca só, `[data-conectado="nao"]`: o gerador a escreve e o piloto a vira nos dois
     sentidos (passos `1b` e `1c`). As quatro colunas nascem do MESMO molde, e o lugar que nasce
     vazio e o que esvazia na frente do usuário têm a mesma cara. Até 16/10/2026 havia duas
     (`.vazia`, de nascimento, e `.off`, do piloto), e o P3 e o P4 saíam com o nome em caixa
     tracejada e letra própria, diferentes do P2 (fotos 7 e 8 do pedido de 16/10).
     Cor explícita e nada de `opacity`; o desenho apagado leva `!important` porque a cor da peça
     é `style=` inline no SVG. O nome fica BRANCO: o lugar vazio se distingue pela palavra
     «Desconectado», pela borda e pelo travessão, não por letra cinza (decisão de 16/10). */
  .luz-grade .ctrl[data-conectado="nao"] > *{display:flex;align-items:center;justify-content:center}
  .luz-grade .ctrl[data-conectado="nao"] .moldura{display:block;color:var(--linha) !important;
                                                  border-color:var(--border-forte) !important}
  .luz-grade .ctrl[data-conectado="nao"] .ctrl-rot{color:var(--fg);border-color:var(--border-forte)}
  .luz-grade .ctrl[data-conectado="nao"] .nada{display:flex;align-items:center;justify-content:center;
                                               height:100%;width:100%;color:var(--linha)}
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg .peca,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg .corpo,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg .miolo *,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg text,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg rect:not([fill="none"]),
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg circle:not([fill="none"]),
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg polygon:not([fill="none"]),
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                                              stroke:var(--linha) !important}
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg line{stroke:var(--linha) !important}
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg .corpo,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg rect,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg circle,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg polygon,
  .luz-grade .ctrl[data-conectado="nao"] .ds-svg ellipse{stroke:var(--border-forte) !important}
  /* Os widgets saem e o travessão fica: um lugar sem aparelho não oferece gesto (31/08/2026). */
  .luz-grade .ctrl[data-conectado="nao"] .guia,
  .luz-grade .ctrl[data-conectado="nao"] .trilho,
  .luz-grade .ctrl[data-conectado="nao"] .g4-efeito{display:none}
  /* O travessão da Cor e da Efeito nasce nas quatro colunas e só aparece no lugar vazio. */
  .luz-grade .ctrl[data-conectado="sim"] .cel-cor .nada,
  .luz-grade .ctrl[data-conectado="sim"] .cel-acoes .nada{display:none}
  /* O `.num` do brilho É o travessão da célula no lugar vazio: lê como os outros traços. */
  .luz-grade .ctrl[data-conectado="nao"] .cel-brilho .num{font-family:inherit;color:var(--linha);
                                                          font-size:inherit;flex:1;text-align:center;
                                                          display:flex;align-items:center;
                                                          justify-content:center}
  /* o respiro entre colunas é do CONTEÚDO, não da célula: padding na coluna
     recua os filhos e a borda deles para 16px antes da divisa, e a linha
     volta a quebrar. Aqui a célula vai até o fim e quem se afasta é o texto. */

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido:
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
    left:-13px;right:-14px;border-top:1px solid var(--rot-linha)}
  /* A CONTA DA MARGEM NEGATIVA: ela tem de cancelar o padding da coluna E o
     `gap` do grid, senão sobra um buraco do tamanho do vão. À direita são
     8 de padding + 16 de gap = 24; a ÚLTIMA coluna não tem vão depois
     dela, então volta a 8. A coluna de rótulos não tem padding: 0 e 16. */
  .luz-grade > div:not(:last-child) > *::before{right:-14px}
  .luz-grade > div:last-child > *::before{right:0}
  .luz-grade > .rotulos > *::before{left:0;right:calc(var(--gap-col) * -1)}
  .luz-grade > div > *:first-child::before{display:none}

  /* a coluna dos rótulos: todo título começa no mesmo x, e cada um ocupa a
     ALTURA INTEIRA da sua linha — é assim que a coluna acaba junto das outras */
  .luz-grade .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
  /* O NOME DA LINHA ALINHA À DIREITA — 30/08/2026, pedido: *"no nome das
     linhas deixa alinhadas à direita. Todas"*. Encostado na divisa, o rótulo fica
     perto do que ele nomeia em vez de ficar perto da borda do quadro — é o que
     toda tabela de formulário faz, e é o que faz a coluna deixar de ler como
     lista solta e passar a ler como cabeçalho de linha. */
  /* O RÓTULO ALINHA À ESQUERDA — decisão, 31/08/2026: *"alinha a esquerda a
     primeira coluna."*

     E ELA REVOGA A DECISÃO DE PRODUTO MESMA de 30/08 (*"no nome das linhas deixa
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
     do desenho que nomeia — a cura do vão é na ALTURA, regra de produto. */
  .luz-grade .rotulos .cel-des{gap:8px}
  /* A CAIXA ALTA SAIU — 30/08/2026. A regra desta casa sobre maiúscula é a
     PRIMEIRA LETRA, e o usuário confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     o usuário apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           display:flex;align-items:center;gap:6px}
  /* A LEGENDA NÃO É TÍTULO. Sem isto ela herda o `text-transform:uppercase` do
     rótulo e sai um parágrafo inteiro em caixa alta, que é o mais difícil de
     ler que existe. Medido no navegador em 27/08, na Vibração. */
  .luz-grade .rotulos .legenda{font-size:10.5px;line-height:1.45;color:var(--fg);
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
     vazio e a borda cai em `var(--linha)`. Regra de produto: campo sem informação não
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
  .luz-grade .moldura{height:100%;box-sizing:border-box;display:flex;align-items:center;
                      justify-content:center}
  .luz-grade .moldura .ds-svg{height:100%;width:auto;max-width:100%}
  /* A linha «Modelo» leva o nome do jogador (item 9, 06/10): um nome comprido NÃO alarga a coluna do
     controle, quebra em duas linhas como a Vibração faz, e a tela continua sem rolagem. */
  /* O NOME DO CONTROLE É UMA CAIXA, com a largura da coluna e centrado (desenho do todo). */
  .ctrl-rot{height:30px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;
            border:1px solid var(--linha);border-radius:7px;font:600 12.5px 'Space Grotesk',system-ui,sans-serif;
            color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;align-self:center;
            width:100%;min-width:0}
  .ctrl-rot .pt{margin:0 6px}

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
     herda para baixo. Medido no DOM vivo em 03/09/2026, na bancada — as cinco
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
     no desenho de 224 px desta aba. A decisão de 28/08 é que o padrão se
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

  /* O MODO AUTOMÁTICO DEIXA AS COLUNAS PARADAS — pedido de 06/10/2026: o
     desenho e o modelo continuam dizendo de quem é a coluna; a cor, o brilho, o
     número, as luzes e o «Desligar» esmaecem e não recebem clique. */
  /* O ESCOPO GLOBAL DESTA FAIXA SAIU — 07/09/2026, e a faixa voltou a ter um
     morador só: o interruptor. A ordem de produto é de hoje, sobre os três cantos
     que falavam de automático — *"Olha na real sai todos. Deixa só lá o de
     cima mesmo o tongle."*

     O CSS SAI COM O BOTÃO, e não fica "por via das dúvidas": esta folha entra
     INTEIRA na página, e uma classe órfã aqui é a próxima pessoa repondo o
     widget porque o estilo já estava pronto. A medição que ela carregava (a
     faixa tem 17px de altura, o botão precisava caber em 15) morreu com ela.

     E NENHUM `data-gesto` ESTÁ ESCRITO NESTE COMENTÁRIO, de propósito — ver a
     nota longa da faixa das lâmpadas, algumas telas acima: o portão
     `paridade-gtk-html` procura o sinal como TEXTO no HTML, e o comentário que
     EXPLICA a remoção já virou, nesta mesma aba, a prova de que a peça
     continuava lá. Os nomes estão no pacote, na nota datada. */

  /* ---------- COR: a guia dos oito tons do produto, por controle ---------- */
  .guia{display:flex;flex-wrap:nowrap;justify-content:space-between;align-items:center}
  /* os onze botões continuam itens do flex da `.guia` — ver o gerador */
  .guia .tons{display:contents}
  /* A MOLDURA DA AMOSTRA SAIU — 31/08/2026, e é a mais pura das "bordas
     sobrando": um retângulo de 1px em volta de um retângulo CHEIO da cor que
     ele mostra. São oito por controle, trinta e dois na tela, e nenhum deles
     separava coisa nenhuma — o `gap:4px` já separa, e o conteúdo é a própria
     cor. A borda continua em `transparent`: a casa não muda de tamanho quando
     muda de estado. */
  .guia .tom{flex:0 0 24px;width:24px;height:24px;border-radius:6px;border:1px solid transparent;
             cursor:pointer;padding:0;display:block;min-width:0;position:relative}
  /* A LINHA DO DONO — 29/09/2026, D-2909-A-LINHA-DA-COR-DO-DONO, pedido
     na bancada: *«talvez uma linha abaixo do quadradinho de cada cor contendo
     a cor do plástico daquele controle.»* <!-- noqa-acento: citação literal -->
     Toda casa com dono ganha a linha, nas quatro colunas: a linha diz de quem
     é, e o X diz que não é sua. A casa deste controle é a que tem a linha da
     cor da moldura e não tem X.

     A TINTA É `--dono`, que o pacote escreve na própria casa: a cor do
     plástico, partes iguais por dono na ordem do número quando a casa é de
     vários, ou tracejada em `--comment` quando o plástico não chegou (a
     gramática do anel incerto da linha Jogador). NUNCA `currentColor`: a casa
     é um `<button>`, e o `<button>` não herda `color`.

     A BORDA DA ESCOLHIDA SAIU com esta linha. Ela pedia `currentColor` à
     `.guia`, e saía na cor de texto de botão do motor, quase preta nas quatro
     colunas desde 09/09. Na cor certa ainda sumiria onde o plástico e a casa
     são o mesmo tom (o Starlight Blue na casa azul, o White na branca); a
     linha fica no painel escuro, onde o White aparece.

     O LUGAR É O VÃO ENTRE A CASA E A CAIXA `#RRGGBB`: 2 px abaixo da casa e 6
     px de altura, com o vão da `.cel-cor` em 8 px e a linha Cor em 46 px
     (`--r-cor`). Era 2 px, e o roxo do Galactic Purple (`#74588e`, 2,39:1
     contra o painel) se lia como traço cinza: *«o do p2 não tem a cor dele
     roxo.»* (29/09, ~18h50) <!-- noqa-acento: citação literal -->
     O piso de 2,2:1 do `tom_para_a_borda` foi pensado para a borda de um
     cartão, onde o comprimento carrega o tom; numa marca curta quem o carrega
     é a área. A altura é a (b) das ESCOLHAS de 08/10/2026. O vão de cima é o
     que separa a linha da casa: colada, a do Starlight Blue embaixo da casa
     azul se leria como a casa mais alta. O `-1px` dos lados alcança a borda
     da casa, porque o `left` conta da caixa por dentro dela. */
  .guia .tom.com-dono::before{
    content:"";position:absolute;left:-1px;right:-1px;
    top:calc(100% + 3px);height:6px;border-radius:2px;background:var(--dono);
  }
  /* O X DA COR DO VIZINHO — COR-X-01, 09/09/2026, decisão de produto: "um X na cor
     selecionada por mim de forma que me impeça de setar alguma cor de um
     coleguinha". <!-- noqa-acento: citação literal -->

     ELE É DESENHADO, e não um caractere: um `×` de texto herda a fonte, muda
     de tamanho com ela e o traço fino some sobre um tom claro. Dois gradientes
     cruzados desenham as duas hastes, e uma sombra os contorna.

     A COR DO X É PRETA COM BORDA BRANCA — decisão, 09/09/2026, com os
     quatro na mesa: *"deixa o nosso x preto com borda branca pra destacar.
     Falo isso pois ficou perfeito o nosso x, o complicado é que são tons
     pasteis e o controle branco por exemplo não ajuda nisso o x dele fica
     invisível."* <!-- noqa-acento: citação literal -->

     ELE ERA `var(--dono)` — a cor do PLÁSTICO de quem tem o tom —, e a ideia
     vinha da mesma regra que pinta a borda da coluna
     (`D-A-BORDA-E-A-IDENTIDADE-DA-PECA`): o X diria de quem é a cor sem
     palavra nenhuma. **A bancada derrubou a ideia**, e o caso que a derruba é o
     controle BRANCO dela: branco sobre um tom pastel não tem contraste
     nenhum, e o X dele fica invisível — exatamente na casa em que ela precisa
     ver que não pode clicar. Um X que só aparece em três dos quatro controles
     é pior do que um X neutro que aparece nos quatro.

     QUEM DIZ DE QUEM É A COR PASSA A SER O `title`, e ele já dizia: o pacote
     escreve *"P3 (Starlight Blue) já está neste tom"* em cada botão tomado. A
     identidade não se perdeu — mudou de canal, do desenho para a palavra, e a
     palavra não depende de contraste.

     O `--dono` SAIU DO X e virou a tinta da linha embaixo da casa (29/09/2026,
     a regra de cima).

     A CASA DIVIDIDA TAMBÉM NÃO OFERECE O CLIQUE (29/09/2026): ela fica `on`,
     sem X e sem gesto, com o `aria-disabled`; com a mão de clique por cima ela
     prometeria o gesto que não tem. */
  .guia .tom.tomado,.guia .tom[aria-disabled="true"]{cursor:not-allowed}
  /* O CONTORNO BRANCO É `filter:drop-shadow`, e não um segundo X por baixo:
     o `drop-shadow` segue a FORMA alfa do gradiente, então ele contorna as
     duas hastes de verdade. Quatro sombras de 1px (uma por diagonal) fecham
     o contorno inteiro; com uma só, o X ganha borda de um lado e fica torto.
     Um `::before` com o mesmo X mais grosso por baixo também funcionaria e
     custaria um pseudo-elemento a mais em 14 botões por coluna, vezes quatro
     colunas — 56 nós contra zero. */
  /* O X É UM QUADRADO CENTRADO, E NÃO UMA MOLDURA RECUADA — DICA-DA-COR-01,
     13/09/2026. A `COR-X-01` mediu a COR do X e deu verde; a LARGURA ninguém
     mediu. O recuo de 5 px dos quatro lados amarrava o X à largura da pílula,
     que é a coisa mais estreita desta tela, e ele saía uma TIRA. Medido no
     `WebKit2.WebView`, na página publicada, com dois controles pintados:

         vista 1212x809 (como a janela abre)  .tom 16,5 x 26  X  4,5 x 14
         vista 1918x840 (a TV da bancada)           .tom 26,1 x 26  X 14,0 x 14

     A LARGURA TEM TETO DE 12 PX, e o `100% - 2px` impede o X e o contorno
     branco de vazarem da pílula se ela encolher. A ALTURA VEM DE
     `aspect-ratio`, e não do mesmo `min()`: os dois `100%` respondem a caixas
     diferentes (a largura e a altura por dentro da pílula), e com `min()` nos
     dois eixos o X saía 8,94 x 12 na pílula de 10,94 px que a janela tinha a
     1222 px — medido na entrega de 10/09 (`65838cf4`). A pílula de hoje é mais
     larga (14,5 px por dentro a 1212 px), e o `aspect-ratio` é o que segura o
     quadrado se ela voltar a ficar mais estreita que o teto.

     Quem morde: `tests/unit/test_o_x_do_vizinho_e_quadrado.py`. */
  .guia .tom.tomado::after{
    content:"";position:absolute;
    left:50%;top:50%;transform:translate(-50%,-50%);
    width:min(12px,calc(100% - 2px));height:auto;aspect-ratio:1;
    background:
      linear-gradient(to top left,transparent 45%,#000 45%,#000 55%,transparent 55%),
      linear-gradient(to top right,transparent 45%,#000 45%,#000 55%,transparent 55%);
    filter:drop-shadow(1px 0 0 #fff) drop-shadow(-1px 0 0 #fff)
           drop-shadow(0 1px 0 #fff) drop-shadow(0 -1px 0 #fff);
  }
  /* A CASA HACHURADA DO FIM DA FILEIRA SAIU — 11/09/2026, ordem de produto. A razão,
     as palavras de produto e os três tons que saíram junto estão na nota datada de
     `FORA_DA_GUIA`, no pacote desta aba.

     Eram quatro regras: o losango tracejado, o realce ao passar por cima, e os
     dois pseudo-elementos com que o WebKit desenha a amostra por dentro do
     campo. As quatro saem com a peça, e não ficam "por via das dúvidas" —
     classe órfã nesta folha é a próxima pessoa repondo o widget porque o estilo
     já estava pronto. É a mesma lição que o botão da faixa das lâmpadas pagou,
     algumas telas acima.

     E O NOME DO SINAL NÃO ESTÁ ESCRITO AQUI, de propósito: o portão
     `paridade-gtk-html` procura o sinal como TEXTO no HTML, e nesta MESMA aba
     um comentário que explicava uma remoção já virou a prova de que a peça
     continuava lá. */
  /* O HEXADECIMAL SAIU DA TELA — 16/10/2026, por pedido de produto: ele vira a dica da célula Cor
     (`data-dica`, pintada pelo campo `hex`). A caixa era o botão de reenvio (04/09); a cor
     reenvia agora no clique da amostra já acesa, que é o mesmo gesto `cor` de escolher. */
  .cel-cor{display:flex;flex-direction:column;gap:8px;justify-content:center}

  /* ---------- BRILHO ---------- */
  .cel-brilho{display:flex;align-items:center;gap:9px}
  .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .num{flex:0 0 38px;text-align:right;font-family:'JetBrains Mono',monospace;
       font-size:12px;color:var(--fg)}
  /* O TRILHO PASSA A ACEITAR O ARRASTE — 03/09/2026, decisão de produto: perguntada
     se mexer no brilho grava o perfil na hora ou espera o "Salvar perfil", ela
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
     de ser a coluna que o usuário aprovou. */
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
  .players button,.brilhos button{
    flex:1;border-radius:7px;gap:6px;min-width:0;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    cursor:pointer;font-size:13px;font-weight:600;font-family:'JetBrains Mono',monospace;
  }
  .players button.on,.brilhos button.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg)}
  .players button:hover:not(.on):not(.fora),
  .brilhos button:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}
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
     clicável de propósito — quem insistir vê o botão piscar a recusa em vez de
     nada; a frase do daemon vai ao diário, e não à tela (13/09/2026, a
     docstring de `hefesto_vivo._recusou_dizendo`). */
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
     [01] desta aba). A linha de ressalva saiu por ordem de produto — *"o que eu não
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
            justify-content:center;min-width:0;gap:6px}
  /* AS TRÊS PÍLULAS DO BRILHO DAS LUZES — 24/09/2026, decisão de produto
     (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`). No molde da linha
     `Jogador`: a regra de botão é a MESMA (`.players button`, logo acima, e
     ela ganhou o seletor destas), e só a altura muda — 24 em vez dos 36 da
     escala, porque elas dividem a faixa com a tira. `flex:0 0 24px` pela
     razão da tira: sem a trava, o `flex-shrink` padrão as apertaria.

     O LUGAR SEM DONO FICA SEM PÍLULA, e a caixa fica: o pacote escreve a
     fileira vazia quando o controle sai, e a caixa de 24px mantém a tira no
     MESMO y das colunas vivas. */
  .brilhos{display:flex;gap:5px;align-items:stretch;flex:0 0 24px;min-width:0}
  .brilhos button{height:24px;font-size:12px}
  .luz-grade .ctrl[data-conectado="nao"] .brilhos button{display:none}
  /* E A TIRA DO LUGAR VAZIO MORA NA MESMA CÉLULA — 07/09/2026. Até aqui o
     `.aceso` do lugar sem dono era ele próprio o item da grade, e esta linha
     dizia `align-self:center;height:34px` para ele não esticar pelos 56px da
     faixa. Com a função única, os QUATRO lugares emitem a `.cel-leds`, e quem
     é item de grade é ela nos quatro — a tira volta a medir 34 sozinha, pelo
     `flex:0 0 34px` que já tinha.
     O QUE SOBRA É DEVOLVER O `align-items`: a regra genérica
     `.ctrl[data-conectado="nao"] > *` (0,3,0) escreve `center` em todo filho direto, e num
     flex de coluna `center` faz a tira encolher para a largura do conteúdo —
     medido: 212px viravam a largura de um travessão. Esta linha vem DEPOIS
     dela, com a mesma especificidade, e é a que vale. */
  .luz-grade .ctrl[data-conectado="nao"] .cel-leds{align-items:stretch}
  /* O VÃO VOLTOU A SER 16px E UM SÓ — 07/09/2026, com a botoeira fora. A
     LUZES-01 o partira em dois grupos (`space-between` + `gap:4px`) porque as
     seis teclas de desenho pediam 212 dos 220px da coluna e não sobrava vão;
     sem elas, a `.aceso` volta a ter três filhos — tira, indicador, tira — e o
     `center` com 16 de respiro é o desenho original, que é o que o usuário mandou
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

     O DEFEITO QUE O USUÁRIO VIU: as duas eram a MESMA tira, byte por byte
     (`background:var(--panel);color:transparent;opacity:1`), e a ressalva que
     as separa viajava só no `title` — quem não passa o mouse não vê. São três
     coisas que o motor já distinguia e a tela mostrava como duas:

       acesa     a cor conhecida, com halo        `background:{tinta}`
       apagada   fonte NOSSA, barra desligada     `TIRA_APAGADA` — lisa e vazia
       incerta   Steam · cor ignorada             ESTA REGRA — tracejada

     O NATIVO SAIU DA LINHA DE BAIXO em 24/09/2026
     (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`): no Nativo a barra é do
     Hefesto, e a tira desenha a cor como em todo modo.

     CONTORNO, E NUNCA COR NOVA — ordem de produto. Nesta aba tudo o que é CHEIO de
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
     A BOTOEIRA DA LUZES-01 SAIU INTEIRA, por ordem de produto: *"só olhar a linha de
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

     É a armadilha que o contrato desta casa nomeia três vezes em três dias:
     *um comentário que descreve o padrão proibido VIRA a primeira ocorrência
     dele*. Quem for escrever aqui o nome de um `data-gesto` que saiu, escreva-o
     sem o atributo — ou não escreva. Os nomes estão no pacote desta aba, na
     nota datada do piso — e o ponteiro que estava aqui apontava para uma
     constante que morreu com a faixa em 07/09/2026. */
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
  .cel-acoes{display:flex;flex-direction:column;align-items:stretch;gap:2px;justify-content:center;
             margin-top:0;min-width:0}
  /* A LISTA DE EFEITOS ocupa a célula inteira, em vez de impor a largura do nome mais longo, e a
     frase de UMA linha embaixo dela diz o que a opção escolhida faz (desenho A de 15/10/2026).
     A frase não quebra e cabe inteira (até ~36 letras na coluna de 232px; as de 40 a 60 letras do
     desenho saíam cortadas, medido na tela em 15/10): a faixa tem 48px (32 da lista, 2 de vão e
     14 da frase), e com 62px o miolo passa de 618 e a aba rola. */
  .g4-efeito{flex:0 0 32px;width:100%;min-width:0;height:32px;padding:0 9px;border-radius:7px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif;cursor:pointer}
  .g4-efeito:hover{border-color:var(--comment)}
  /* A FRASE DO EFEITO É DICA (16/10/2026): mora na `data-dica` da caixa da lista, pintada pelo
     campo `efeito-dica`. A caixa não ocupa lugar (`display:contents`); a dica sobe a árvore. */
  .g4-efeito-dica{display:contents}
  .quadro-topo .modo-auto{margin-left:auto}
  /* ---------- CRIAR EFEITOS NOVOS ---------- */
  .criar{flex:0 0 auto}
  .criar .criar-linha{display:flex;align-items:center;gap:12px;padding:7px 16px;flex-wrap:nowrap;min-width:0}
  .criar .quadro-titulo{flex:0 0 auto;margin-right:4px}
  .criar .seg-criar{display:inline-flex;gap:4px;flex:0 0 auto}
  .criar .seg-criar label,.criar .meu{height:30px;padding:0 12px;border-radius:999px;
    font:500 12.5px/1 'Space Grotesk',system-ui,sans-serif;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--fg);cursor:pointer;white-space:nowrap;
    display:inline-flex;align-items:center;gap:7px;box-sizing:border-box}
  .criar .seg-criar input{position:absolute;opacity:0;pointer-events:none;width:1px;height:1px}
  .criar .seg-criar label:has(input:checked){border-color:var(--purple);background:var(--sel-bg);
    color:var(--fg);font-weight:600}
  .criar .seg-criar label:hover:not(:has(input:checked)),.criar .meu:hover{border-color:var(--comment);
    color:var(--texto-suave)}
  .criar .seg-criar label:has(input:focus-visible){outline:2px solid var(--cyan,#8be9fd);outline-offset:2px}
  .criar .nome-criar{height:30px;width:136px;flex:0 0 auto;padding:0 11px;border-radius:7px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif}
  .criar .nome-criar::placeholder{color:var(--fg)}
  .criar .btn-criar{height:30px;padding:0 14px;border-radius:7px;border:1px solid var(--purple);
    background:rgba(189,147,249,.12);color:var(--purple);font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;
    cursor:pointer;flex:0 0 auto}
  .criar .btn-criar:hover{background:rgba(189,147,249,.22)}
  .criar .meus{display:flex;gap:6px;margin-left:auto;align-items:center;min-width:0;overflow:hidden}
  .criar .meu{color:var(--texto-suave);cursor:default}
  .criar .meu i{width:7px;height:7px;border-radius:50%;background:var(--cor,var(--purple));flex:0 0 auto}
  .g4-cores{display:inline-flex;gap:6px;align-items:center;flex:0 0 auto}
  .g4-cor{width:24px;height:24px;border-radius:6px;display:block;border:0;padding:0;cursor:pointer}
  .g4-cor:hover{outline:2px solid var(--comment)}
  .g4-mais{width:24px;height:24px;border-radius:6px;border:1px dashed var(--linha);background:transparent;
    color:var(--fg);font:600 14px/1 'Space Grotesk',system-ui,sans-serif;cursor:pointer;padding:0}
  .g4-mais[hidden]{display:none}
  .g4-vel{display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;font-size:12px;font-weight:600;
    color:var(--rot-campo)}
  .g4-vel input{width:90px;accent-color:var(--purple);height:24px}
  .criar:has(input[value="arco-iris"]:checked) .g4-cores{display:none}

  /* ---------- o antes e o depois da troca, na legenda ---------- */
  .troca{margin:8px 0 12px;font-size:11.5px}
  .troca-linha{display:flex;align-items:center;gap:10px;margin:5px 0;flex-wrap:wrap}
  .troca-rot{flex:0 0 52px;font-size:10.5px;
             color:var(--fg)}
  .troca-item{display:flex;align-items:center;gap:7px;padding:4px 9px;border-radius:7px;
              border:1px solid var(--linha);background:var(--app-bg)}
  .troca-item.mexeu{border-color:var(--purple);background:var(--sel-bg)}
  .troca-item .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                    background:none;border:2px solid var(--plastico)}
  /* O mesmo "não sei" da fileira de players — ver `.players .dono.incerta`. */
  .troca-item .dono.incerta{border:2px dashed var(--comment)}
  .troca-item .np{font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--fg)}
  .troca-gesto{margin:6px 0 6px 62px;color:var(--fg)}
""" + CSS_GLIFO + """
  /* OS GLIFOS DOS TÍTULOS são as peças de `assets/glyphs/` — as mesmas 19 da aba
     Status. Só entram nos dois títulos que NOMEIAM uma peça: a barra de luz e o
     indicador de jogador. "Brilho", "Opções" e "Selecione o player" não são peça
     de controle — pôr o glifo do botão Options ao lado de "Opções" seria um
     trocadilho com outra coisa. */
  .sec-rot .gl{opacity:.9;flex:0 0 auto}
"""


DONOS_NA_MESA = {n: d for n, d in DONO.items() if d.get("conectado", True)}


#: O dono único é `pacotes/a04_iluminacao.um_botao_de_player`, e este gerador é


VAZIO = "—"

#: Os dois efeitos do desenho (a biblioteca de mentira do mockup): a página viva troca a lista pela
#: dos efeitos que a pessoa criou.
CENA_DOS_EFEITOS = {
    "Alerta vermelho": {"nome": "Alerta vermelho", "base": "piscar",
                        "parametros": {"cores": "#FF0000", "ritmo": 6}},
    "Respiro calmo": {"nome": "Respiro calmo", "base": "respirar",
                      "parametros": {"cores": "#00FFFF", "ritmo": 2}},
}

SEM_NINGUEM_AQUI = "Desconectado"


def coluna(c):
    """A coluna de UM lugar da mesa — com controle ou sem, e é a MESMA função.

    ERAM DUAS ATÉ 07/09/2026, e a segunda envelheceu sem a primeira. Este
    arquivo tinha uma `coluna_vazia()` que desenhava o lugar sem dono com sete
    células de travessão e **nenhum `data-campo` por dentro** — medido na página
    publicada naquele dia, com a régua `medir.py` deste trabalho:

        p1: 20 data-campo (10 distintos)     p3: 0 data-campo (0 distintos)
        p2: 20 data-campo (10 distintos)     p4: 0 data-campo (0 distintos)

    O QUE ISSO CUSTAVA, com os QUATRO DualSense do usuário na mesa: o daemon publicava
    quatro controles, a carga chegava com `colunas = ['p1','p2','p3','p4']` e os
    quatro em `ocupados` — e a tela mostrava DOIS. O piloto pinta por endereço
    (`hefesto_vivo`, passo 2: `for(const el of achar(raiz, k))`, e `achar`
    procura `data-campo` DENTRO do bloco daquele `data-controle`), então o dado
    do P3 chegava e **não tinha onde pousar**. Os outros dois lugares seguiam
    dizendo "P3 · Desconectado" com travessão em tudo.

    O ENDEREÇO DO BLOCO JÁ TINHA SIDO CURADO EM 03/09 — o `data-controle` no
    lugar vazio, decisão de produto: *"tem que aparecer desligado enquanto não tem
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
    3. **os widgets que carregam GESTO** — a guia de tons, o puxador do brilho
       e os dois botões de Opções (eram quatro até 11/09/2026: o campo de cor
       do fim da fileira saiu com a poda de `FORA_DA_GUIA`). Estes são a
       exceção, e ela é decisão de produto: *um lugar sem aparelho não oferece gesto
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
    # controle (#0000FF); `tom_da_casa()` traduz para o tom desta janela, que é
    p, j = c["pref"], c["jogador"]
    ligado = c.get("conectado", True)
    cor = luz(j)
    tinta = tom_da_casa(cor)
    b = BRILHO[c["pref"]]
    # comparação era contra `cor`, que é o hex cru. `#0000FF` nunca é igual ao
    casas = _pacote04.as_casas_da_mesa(
        {"quem": d["pref"], "cor": player_slot_color(d["jogador"]),
         "nome": f'P{d["jogador"]}', "numero": d["jogador"],
         "plastico": _pacote04.plastico_da_linha(d["cor"])}
        for d in DONOS_NA_MESA.values())
    tons = _pacote04.fileira_de_tons(p, casas, "            ", ligado=ligado)

    titulo_do_lugar = "" if ligado else (
        '\n             data-dica="Nenhum controle aqui"')
    plastico_de_partida = (f' style="color:{cor_da_zona(c["cor"])}"'
                           if ligado else "")
    dica_da_moldura = (
        ' data-dica="A borda é o plástico; a barra, a cor do número"'
        if ligado else "")
    rotulo = (monta_.rotulo(c, "modelo") if ligado else
              f'P{j} <span class="pt">•</span> {SEM_NINGUEM_AQUI}')
    # `opcoes` eram `... if ligado else ""`, e o preço foi MEDIDO nas  (noqa-acento: nome de variável)
    # DualSense do usuário na mesa e o daemon de pé, a foto ao vivo mostrava o P3 e o
    # bloco `[data-conectado="nao"]` desta folha esconde a guia, o trilho e os
    # instante do passo `1c` e some no `1b`, sem ninguém injetar HTML.
    # DONO. Ela carregava o `data-campo="plastico"` (alvo `cor`) só para dar
    guia = f'''<span class="guia">
              <span class="tons" data-campo="tons" data-hef-alvo="html">
{tons}
              </span>
            </span>
            '''
    dica_do_hex = f' data-dica="{cor}"' if ligado else ""
    largura_de_partida = f' style="width:{b}%"' if ligado else ""
    puxador = (f'<input class="puxador" type="range" min="0" max="100" step="1"'
               f' value="{b if ligado else 0}" data-gesto="brilho" data-campo="brilho-pct"'
               f' data-hef-alvo="valor"'
               f' aria-label="{_pacote04.ROTULO_DO_BRILHO}"'
               f' data-dica="{_pacote04.DICA_DO_BRILHO}">')
    fileira = (_pacote04.fileira_de_players(
        c["nome"], c["jogador"], DONOS_NA_MESA, "            ",
        quantos=len(monta_.CONECTADOS)) if ligado else
        f'            <span class="nada">{VAZIO}</span>')
    miolo_da_luz = (_pacote04.desenho_da_luz(
        tinta, b / 100, j, dica=_pacote04.dica_da_luz(c["nome"], c["via"], ""),
        recuo="              ") if ligado else
        f'              <span class="nada">{VAZIO}</span>')
    resto_do_desenho = ({"jogador": j, "luz": tinta} if ligado
                        else {"lampadas": False})
    brilho_escrito = f"{b}%" if ligado else VAZIO
    from hefesto_dualsense4unix.core.led_control import BRILHO_DAS_LUZES_PADRAO
    brilhos = (_pacote04.fileira_de_brilhos_das_luzes(
        BRILHO_DAS_LUZES_PADRAO, "              ") if ligado else "")
    #: a lista nasce igual nos quatro lugares (a do vazio some pela folha): o pacote reescreve as
    #: opções da coluna viva, e o valor escolhido volta pelo `data-campo`.
    opcoes = (f'<span class="g4-efeito-dica" data-campo="{_pacote04.CAMPO_DA_DICA_DO_EFEITO}" '
              f'data-hef-alvo="atributo" data-hef-atributo="data-dica" '
              f'data-dica="{_pacote04.DICA_LUZ_FIXA}">'
              f'<select class="g4-efeito" data-gesto="{_pacote04.GESTO_DO_EFEITO}" '
              f'aria-label="Efeito da barra" data-campo="{_pacote04.CAMPO_DO_EFEITO}" '
              f'data-hef-alvo="valor">'
              + _pacote04.opcoes_do_efeito(CENA_DOS_EFEITOS).replace(
                  f'<option value="{_pacote04.LUZ_FIXA}">',
                  f'<option value="{_pacote04.LUZ_FIXA}" selected>', 1)
              + '</select></span>\n            ')

    # `nao` da régua de acentuação é um `#`, e dentro de uma f-string de  (noqa-acento: o próprio valor que a nota explica)
    conectado = "sim" if ligado else "nao"  # noqa-acento: valor de atributo
    return f'''        <div class="ctrl" data-controle="{c.get("uniq") or p}" data-conectado="{conectado}"{titulo_do_lugar}>
          <div class="moldura" data-campo="plastico" data-hef-alvo="cor"{plastico_de_partida}{dica_da_moldura}>
            {desenho(f"il-{p}", c["cor"], ligado, **resto_do_desenho)}
          </div>
          <div class="ctrl-rot" data-campo="identidade">{rotulo}</div>
          <div class="cel-cor" data-campo="hex" data-hef-alvo="atributo" data-hef-atributo="data-dica"{dica_do_hex}>
            {guia}<span class="nada">{VAZIO}</span>
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
            <!-- A LINHA DE RESSALVA SAIU DAQUI — 07/09/2026, ordem de produto: *"o
                 que eu não quero é frase da steam ou outras e p1,P2…"*. Ela
                 nasceu em 04/09 (D-02) para responder QUAL das três causas
                 apagou a barra sem exigir o rato; o que ela mostrava era, entre
                 outras, a frase da Steam, e é exatamente essa que o usuário mandou
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
            <div class="brilhos" data-campo="{_pacote04.ENDERECO_DO_BRILHO_DAS_LUZES}" data-hef-alvo="html">
{brilhos}
            </div>
          </div>
          <div class="cel-acoes">
            {opcoes}<!-- O TRAVESSÃO DESTA CÉLULA NASCE AQUI, escondido na coluna viva: a lista de efeitos
                 não é um valor que o molde do lugar sem dono escreva como travessão. -->
            <span class="nada">{VAZIO}</span>
          </div>
        </div>'''

# `noqa-acento` num comentário HTML aninhado — e **comentário HTML NÃO
# A REGRA QUE SOBRA: `# noqa-…` só comenta em Python. Prosa de projeto que
# precise de um `noqa` sai do HTML e vem para cá.

#: o gesto do par dos modos; o pintor (`data-modo-da-aba` do quadro) é do pacote
GESTO_DO_MODO = "modo-da-luz"

def _radios(grupo, opcoes):
    """Os rádios em pílula da área de criar: o primeiro vem marcado."""
    return "".join(
        f'<label><input type="radio" name="{grupo}-criar" value="{valor}" data-linha="{grupo}"'
        f'{" checked" if i == 0 else ""}><span>{rotulo}</span></label>'
        for i, (valor, rotulo) in enumerate(opcoes))


#: As cores com que a área de criar nasce: a do jogador 2 e a do 7, as que o desenho mostra.
CORES_DE_PARTIDA = (CRUS_DA_GUIA[1], CRUS_DA_GUIA[6])


def _cor_do_efeito(cru):
    """Uma cor do efeito: a CRUA vai no `data-cor` (é a que o aparelho recebe), o tom da casa pinta."""
    return (f'<button type="button" class="g4-cor" data-cor="{cru}" '
            f'style="background:{tom_da_casa(cru)}" data-dica="Tirar esta cor"></button>')


#: Mantém as cores do efeito: «+» põe a próxima da guia que ainda não está, a cor tirada sai (fica
#: uma, no mínimo), e o campo escondido leva as cruas ao gesto.
SCRIPT_DO_CRIAR = f'''<script data-aba="criar">
(function(){{
  var raiz = document.getElementById('criar-luz'); if(!raiz) return;
  var CRUAS = {json.dumps(CRUS_DA_GUIA)}, TONS = {json.dumps(TONS)};
  var caixa = raiz.querySelector('.g4-cores'), mais = caixa.querySelector('.g4-mais');
  var oculto = raiz.querySelector('input[data-linha="cores"]');
  function atuais(){{ return [].map.call(caixa.querySelectorAll('.g4-cor'), function(b){{ return b.dataset.cor; }}); }}
  function sincroniza(){{ var n = atuais(); oculto.value = n.join(','); mais.hidden = n.length >= CRUAS.length; }}
  caixa.addEventListener('click', function(ev){{
    var b = ev.target.closest('button'); if(!b) return;
    if(b === mais){{
      var tem = atuais(), i = CRUAS.findIndex(function(c){{ return tem.indexOf(c) < 0; }});
      if(i < 0) return;
      var novo = document.createElement('button');
      novo.type = 'button'; novo.className = 'g4-cor'; novo.dataset.cor = CRUAS[i];
      novo.style.background = TONS[i]; novo.setAttribute('data-dica', 'Tirar esta cor');
      caixa.insertBefore(novo, mais);
    }} else if(b.classList.contains('g4-cor') && atuais().length > 1){{
      b.remove();
    }}
    sincroniza();
  }});
  sincroniza();
}})();
</script>
'''


MIOLO = f'''
{CORES_DO_MAPA}
    <div class="quadro luzes" data-modo-da-aba="{monta_.MODO_PERSONALIZADO}" data-campo="{GESTO_DO_MODO}"
         data-hef-alvo="atributo" data-hef-atributo="data-modo-da-aba">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="A luz diz de quem é cada controle">Iluminação</span>
        {trava_do_nativo("na luz").replace("title=", "data-dica=", 1)}
        {monta_.modo_auto(GESTO_DO_MODO, governa=".luz-grade .ctrl", dica="O jogo pinta a barra; o estilo do perfil ajusta")}
      </div>
      <div class="quadro-corpo">

        <div class="luz-grade">

          <div class="rotulos">
            <!-- AS FRASES DOS RÓTULOS SÃO `data-dica`, texto puro: a dica aparece ao passar o mouse
                 (base comum das abas). Nenhum «?» na tela. -->
            <div class="cel-des">
              <div class="sec-rot" data-dica="A barra acende na cor do número; a borda é a cor do plástico; as cinco luzinhas dizem o número">Controle</div>
            </div>
            <div><span class="sec-rot">Modelo</span></div>
            <div>
              <div class="sec-rot" data-dica="Sem escolha à mão, a barra fica na cor do número do controle. Escolher um tom pinta a barra e não muda o número">Cor</div>
            </div>
            <div><div class="sec-rot">Brilho</div></div>
            <div>
              <div class="sec-rot" data-dica="Dá o número do jogador a este controle, o das cinco luzinhas. Dar um número que já é de outro faz os dois trocarem. O número é do Hefesto: se um jogo o trocar, ele volta em até um segundo">Jogador</div>
            </div>
            <div><div class="sec-rot">LEDs</div></div>
            <div><div class="sec-rot">Efeito</div></div>
          </div>

{chr(10).join(coluna(c) for c in MESA)}

        </div>


        <!-- A FOLHA VIVA DO PLÁSTICO — 03/09/2026, e ela fecha a maior
               identidade congelada desta aba: o DESENHO GRANDE.

               O QUE ESTAVA NA TELA DO USUÁRIO, medido nos pixels da foto (com dois
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
    <div class="quadro criar" id="criar-luz">
      <div class="criar-linha">
        <span class="quadro-titulo" data-dica="O que você criar entra na lista Efeito">Criar efeitos novos</span>
        <span class="seg-criar" role="group" aria-label="Jeito">{_radios("base", [("respirar", "Respirar"), ("piscar", "Piscar"), ("arco-iris", "Arco-íris")])}</span>
        <span class="g4-cores" aria-label="Cores">{"".join(_cor_do_efeito(h) for h in CORES_DE_PARTIDA)}<button type="button" class="g4-mais" aria-label="Mais uma cor" data-dica="Mais uma cor">+</button></span>
        <input type="hidden" data-linha="cores" value="{",".join(CORES_DE_PARTIDA)}">
        <label class="g4-vel" data-dica="Velocidade do efeito"><span>Ritmo</span><input type="range" min="{RITMO_MINIMO_DA_LUZ}" max="{RITMO_MAXIMO_DA_LUZ}" value="{RITMO_PADRAO_DA_LUZ}" data-linha="ritmo" aria-label="Ritmo do efeito"></label>
        <input class="nome-criar" type="text" data-linha="nome" maxlength="{TETO_DO_NOME}" placeholder="Nome do efeito" aria-label="Nome do efeito">
        <button class="btn-criar" type="button" data-gesto="{_pacote04.GESTO_DE_CRIAR_EFEITO}" data-hef-forma="criar-luz" data-dica="Guarda e põe na lista Efeito">Criar</button>
        <span class="meus" id="seus-efeitos" aria-label="Seus efeitos">{_pacote04.html_dos_efeitos(CENA_DOS_EFEITOS)}</span>
      </div>
    </div>
{SCRIPT_DO_CRIAR}'''

LEGENDA = f'''<div class="nota">
  <div class="nota-troca" data-hef="troca">
{_pacote04.secao_da_troca(MESA, recuo="    ")}
  </div>

</div>
'''

_UMA_COLUNA = re.compile(r'<div class="ctrl([" ][^>]*?)>(.*?)(?=<div class="ctrl[" ]|\Z)',
                         re.S)

_MIOLO_DO_ALVO_HTML = re.compile(
    r'(<div class="(?:players|aceso|brilhos)"[^>]*data-hef-alvo="html"[^>]*>).*?</div>',
    re.S)


#: `Cor` — o mesmo elemento que mostra `#0000FF` na coluna viva. O que se apaga
_COBERTURA_SEM_DONO = {
    "tom": '.luz-grade .ctrl[data-conectado="nao"] .guia',
    "puxador": '.luz-grade .ctrl[data-conectado="nao"] .trilho',
    "g4-efeito": '.luz-grade .ctrl[data-conectado="nao"] .g4-efeito',
}

_SEM_CLASSE = re.compile(r"()").match("")


def _cada_coluna(colunas):
    """As colunas da grade, separadas em (vazias, conectadas)."""
    vazias, cheias = [], []
    for atributos, miolo in _UMA_COLUNA.findall(colunas):
        (vazias if 'data-conectado="nao"' in atributos else cheias).append(  # noqa-acento
            atributos + ">" + miolo)
    return vazias, cheias


def _conferir(doc):
    """As decisões de produto nesta aba, conferidas NA SAÍDA."""
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    corpo = re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    exigir("top:calc(var(--r-ar) * -1)" in doc,
           "a divisória voltou para o topo da célula — vão todo de um lado só")
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc,
           "o passo deixou de ser o dobro do ar")

    vazios = [c for c in MESA if not c.get("conectado", True)]
    exigir(corpo.count('class="ctrl" data-controle=') == len(MESA),
           "as quatro colunas não nascem do mesmo molde (a classe de nascimento voltou)")
    exigir(corpo.count('data-conectado="nao"') == len(vazios),  # noqa-acento
           f"as colunas vazias não são {len(vazios)}")

    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")

    #    as outras. Com os quatro DualSense do usuário na mesa, ela não conseguia
    grade = (corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
             .split('<div class="quadro criar"', 1)[0])
    #    `luzes`, `desenho-de` e `reenviar-desenho` —, e eles JÁ chegavam aos
    #    `apagar` — são os do cartão, e são estes que a régua conta.
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

    #    por uma regra desta folha que o esconde enquanto `data-conectado="nao"`
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

    for coluna_html in _cada_coluna(grade)[0]:
        exigir("class=\"tom on\"" not in coluna_html,
               "um lugar vazio marca uma cor escolhida — `luz(j)` é a cor "
               "AUTOMÁTICA daquele número, e ali não há controle que a tenha "
               "escolhido")
        exigir('class="puxador"' in coluna_html and 'value="0"' in coluna_html,
               "o puxador do lugar vazio não nasce em zero — brilho cravado "
               "num lugar sem dono é o brilho do MOCKUP na tela dela")
        exigir("style=\"width:" not in coluna_html,
               "a barra de brilho do lugar vazio nasceu com largura")
    for curto, longo in ((">LEDs</div>", "Disposição de LEDs"),
                         (">Jogador", "Selecione o player")):
        exigir(curto in corpo, f"o rótulo curto sumiu: {curto!r}")
        exigir(longo not in corpo, f"o rótulo longo voltou: {longo!r}")
    exigir("Voltar ao automático" not in corpo,
           "o rótulo longo que ela mandou encurtar em 31/08 voltou à tela")

    exigir(len(re.findall(r'class="tom on com-dono"', corpo))
           == len(monta_.CONECTADOS),
           "a cor escolhida não está marcada em todos os controles ligados")

    for c in monta_.CONECTADOS:
        tinta = tom_da_casa(luz(c["jogador"]))
        for lado in ("esq", "dir"):
            exigir(f'class="tira-luz {lado}" style="background:{tinta};color:{tinta}' in corpo,
                   f"a tira {lado} do P{c['jogador']} não acende a tinta da guia ({tinta})")

    exigir(doc.count('id="cores-do-dualsense"') == 1,
           "as cores do mapa não estão UMA vez na página — ou voltaram para "
           "dentro dos SVGs (cada desenho sabendo pintar um modelo só), ou "
           "saíram de vez")
    modelos = len(set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]', doc)))
    do_mapa = len(set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]',
                                 monta_.DS)))
    exigir(modelos == do_mapa,
           f"a página conhece {modelos} modelos e o mapa dela tem {do_mapa}")
    for alvo in sorted(set(re.findall(r"url\(#([a-zA-Z0-9_-]+)\)", doc))):
        exigir(f'id="{alvo}"' in doc,
               f"a folha aponta para `url(#{alvo})` e a página não tem esse id "
               f"— o modelo que usa esse fundo pinta nada")
    #    cobrava o endereço só nas colunas CONECTADAS, e com isso media o  # noqa-acento: verbo medir, imperfeito
    #    `[data-conectado="nao"] .ds-svg{display:none}`, e o piloto vira essa
    exigir(corpo.count(ENDERECO_DO_DESENHO) == len(MESA),
           "algum desenho da grade não pede o alvo do atributo — sem ele o "
           "pintor escreve o colorway como TEXTO e apaga o desenho, e o lugar "
           "que ganha controle fica com um desenho vestido de nada")
    colunas = corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="quadro criar"', 1)[0]
    exigir(colunas.count("data-colorway=") == len(monta_.CONECTADOS),
           "há `data-colorway` fora das colunas conectadas — identidade do "
           "mockup parada num lugar sem aparelho")

    topo = corpo.split('<div class="quadro-topo">', 1)[-1].split('<div class="quadro-corpo">', 1)[0]
    exigir(topo.count(f'data-gesto="{GESTO_DO_MODO}"') == 1 and 'class="modo-auto"' in topo
           and 'data-governa=".luz-grade .ctrl"' in topo,
           "o modo automático saiu da faixa do título, ou voltou o par de botões — ele é UM botão "
           "com `data-governa` na grade (base comum das abas, 13/10/2026)")
    exigir('class="luz-do-jogo"' not in corpo,
           "a frase da luz do jogo voltou embaixo das colunas — o botão do modo a "
           "substituiu (pedido dela de 06/10/2026)")
    exigir('class="' + "ajuda" not in corpo and ">?<" not in corpo,
           "o «?» voltou à tela — as frases moram no `data-dica` (ordem dela de 14/10/2026)")

    exigir('data-campo="luz-ressalva"' not in colunas,
           "a linha de ressalva voltou à célula dos LEDs — ela saiu por ordem "
           "dela em 07/09/2026 (*'o que eu não quero é frase da steam ou "
           "outras'*), e a razão da barra apagada continua no `title` das duas "
           "tiras, escrita pela `dica_da_luz` a cada tique")
    from hefesto_dualsense4unix.core.led_control import (
        BRILHO_DAS_LUZES_PADRAO,
        BRILHOS_DAS_LUZES,
    )
    for bloco in re.findall(
            r'<div class="cel-leds">(.*?)<div class="brilhos"',
            "\n".join(_cada_coluna(grade)[1]), re.S):
        exigir("data-gesto=" not in bloco,
               "um gesto voltou ao DESENHO da célula dos LEDs — ele é de leitura "
               "desde 07/09/2026, e as cinco lâmpadas espelham o número sem "
               "escolha própria; o único gesto da faixa é o do brilho")
    for coluna_html in _cada_coluna(grade)[1]:
        pilulas = re.search(r'<div class="brilhos"[^>]*>(.*?)</div>', coluna_html, re.S)
        exigir(bool(pilulas), "uma coluna conectada perdeu as pílulas do brilho "
               "das luzes — a decisão dela de 24/09/2026 as põe na linha LEDs")
        if not pilulas:
            continue
        gestos = re.findall(r'data-gesto="([^"]+)"', pilulas.group(1))
        exigir(set(gestos) == {_pacote04.GESTO_DO_BRILHO_DAS_LUZES},
               f"as pílulas do brilho oferecem {sorted(set(gestos))} — o único "
               f"gesto delas é {_pacote04.GESTO_DO_BRILHO_DAS_LUZES!r}")
        palavras = re.findall(r'data-luzes="([^"]+)"', pilulas.group(1))
        exigir(palavras == list(BRILHOS_DAS_LUZES),
               f"as pílulas do brilho dizem {palavras} — são as três da decisão "
               f"dela, na ordem da tela: {list(BRILHOS_DAS_LUZES)}")
        acesa = re.findall(r'<button class="on"[^>]*data-luzes="([^"]+)"',
                           pilulas.group(1))
        exigir(acesa == [BRILHO_DAS_LUZES_PADRAO],
               f"a pílula acesa do desenho é {acesa} — todo controle nasce no "
               f"{BRILHO_DAS_LUZES_PADRAO!r}, e é isso que a bancada mostra")
    for bloco in re.findall(
            r'<div class="cel-leds">(.*?)<div class="brilhos"',
            "\n".join(_cada_coluna(grade)[1]), re.S):
        exigir('class="luzinhas"' in bloco,
               "as cinco lâmpadas do indicador sumiram da célula dos LEDs — "
               "sem elas a coluna deixa de replicar a linha `Jogador`")
        exigir(bloco.count('class="tira-luz') == 2,
               "a barra de luz deixou de ter as DUAS tiras — elas são o "
               "desenho original, e ela mandou que ficassem")

    #     deixava o P3 que GANHA um controle com a única maneira de reenviar a
    #     a borda de botão enquanto `data-conectado="nao"`, e é a §4 que cobra
    exigir('class="hex' not in colunas and 'data-gesto="reenviar"' not in colunas,
           "o hexadecimal voltou à tela: ele é a dica da célula Cor (16/10)")
    exigir(len(re.findall(r'<div class="cel-cor" data-campo="hex" data-hef-alvo="atributo" '
                          r'data-hef-atributo="data-dica"', colunas)) == len(MESA),
           "a célula Cor não leva o hexadecimal na dica em todas as colunas")

    #     de `core/led_control.player_led_pattern` — o MESMO que o daemon
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

    exigir("Todos no automático" not in topo,
           "o botão de escopo global voltou à faixa do título — ela mandou "
           "tirar os três cantos que falavam de automático em 07/09/2026, e "
           "deixar só o interruptor")
    exigir(">Automático</button>" not in corpo,
           "o botão `Automático` voltou à célula Opções — ele saiu com a "
           "ordem dela de 07/09/2026, e o gesto saiu no mesmo commit")
    exigir(">Desligar</button>" not in corpo,
           "o botão «Desligar» voltou — a lista Efeito tem «Sem efeito» no lugar (14/10/2026)")
    exigir(corpo.count('class="g4-efeito"') == len(MESA)
           and corpo.count(f'data-gesto="{_pacote04.GESTO_DO_EFEITO}"') == len(MESA),
           "a célula Efeito não tem uma lista por lugar")
    exigir(len(re.findall(r'<option value="sem-efeito"', corpo)) == len(MESA)
           and len(re.findall(r'<option value="luz-fixa" selected', corpo)) == len(MESA),
           "a lista Efeito não abre em «Luz fixa» com «Sem efeito» ao lado")
    exigir(len(re.findall(r'<optgroup label="(?:Parado|Que respira|Que se move)"', corpo))
           == 3 * len(MESA),
           "a lista Efeito perdeu os grupos do desenho A (Parado, Que respira, Que se move)")
    exigir(corpo.count(f'class="g4-efeito-dica" data-campo="{_pacote04.CAMPO_DA_DICA_DO_EFEITO}" '
                       'data-hef-alvo="atributo" data-hef-atributo="data-dica"') == len(MESA)
           and "g4-dica-do-efeito" not in doc,
           "a frase do efeito voltou para a tela: ela é a dica da lista (16/10), uma por lugar")
    exigir("sem-piscar" not in doc and "Sem piscar" not in doc,
           "o «Sem piscar» voltou à aba: ele saiu em 16/10, a «Luz fixa» já é a luz parada")
    criar = corpo.split('<div class="quadro criar"', 1)[-1]
    exigir(f'data-gesto="{_pacote04.GESTO_DE_CRIAR_EFEITO}"' in criar and "Criar efeitos novos" in criar
           and 'id="seus-efeitos"' in criar,
           "a linha «Criar efeitos novos» não está inteira (título, botão e a lista dos criados)")

    #     `p3: 0 (0)`, `p4: 0 (0)`. Com os quatro DualSense do usuário na mesa, o
    campos_por_lugar = {}
    vazias, cheias = _cada_coluna(grade)
    for coluna_html in vazias + cheias:
        pref = re.search(r'data-controle="([^"]+)"', coluna_html)
        if not pref:
            continue
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

    # 15. A PODA DA FILEIRA — 11/09/2026, ordem de produto: sai o botão que abre outras cores, e saem
    #     um tom de azul, um de rosa e o preto das cores dos 4 controles.
    fora = ("#0080FF", "#FF00FF", "#000000", "#80FF00", "#00FF80", "#FFFFFF")
    exigir(tuple(_pacote04.FORA_DA_GUIA) == fora,
           f"a poda da guia mudou sem esta régua saber: o pacote tira "
           f"{tuple(_pacote04.FORA_DA_GUIA)} e o desenho dela de 14/10/2026 tira {fora} — a guia "
           f"é UMA fileira com as oito cores de jogador")
    exigir(len(CRUS_DA_GUIA) == 8, f"a guia tem {len(CRUS_DA_GUIA)} cores, e o desenho tem oito")
    for h in fora:
        exigir(f'data-hex="{h}"' not in corpo,
               f"o tom {h} voltou à fileira — a guia é só das oito cores de jogador")
    exigir('<input type="color"' not in grade,
           "a casa hachurada do fim da fileira voltou — e o gesto dela morreu "
           "junto em 11/09/2026, então ela seria um clique sem resposta")
    exigir(grade.count('class="tom') == len(MESA) * len(CRUS_DA_GUIA),
           f"a fileira não tem {len(CRUS_DA_GUIA)} casas em cada um dos "
           f"{len(MESA)} lugares da grade")

    if falhas:
        raise SystemExit("ERRO em 04-iluminacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


CSS_DAS_MEDIDAS = f"""
  .luz-grade{{
    --larg-rot:{monta_.larg_rotulos('04-iluminacao')}px;
    --gap-col:{monta_.GAP_DAS_COLUNAS}px;
  }}
"""


if __name__ == "__main__":
    import os
    import pathlib
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-04-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("04-iluminacao", "Iluminação", MIOLO, CSS + CSS_DAS_MEDIDAS,
              legenda=LEGENDA)
    _conferir(onde.pagina("04-iluminacao.html").read_text())
    shutil.copyfile(_prova / "04-iluminacao.html", _real / "04-iluminacao.html")
    shutil.rmtree(_prova)
    print(f"04-iluminacao: OK, {n} divs · {len(monta_.CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s) · "
          f"números {NUMEROS} · respiro 5px, a divisória no meio do vão")
