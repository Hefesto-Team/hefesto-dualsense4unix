"""Aba 05 · Vibração — a mesa de QUATRO controles."""
import csv
import math
import pathlib
import re
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import onde  # noqa: E402
import monta as monta_  # noqa: E402
from monta import CONECTADOS, DADOS_DO_REPO  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import (  # noqa: E402
    MESA, cor_da_zona, glifo, monta, svg,
)
import marca_da_camada as _marca  # noqa: E402

from hefesto_dualsense4unix.daemon.subsystems.rumble import (  # noqa: E402
    RUMBLE_POLICY_MULT,
)

from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    HAPTICA_PCT_MAX,
    HAPTICA_PCT_PADRAO,
    MOTOR_PCT_MAX,
    MOTOR_PCT_PADRAO,
    RUMBLE_CUSTOM_MULT_MAX,
)

# pinta a linha dela pelo seu próprio método (`app/actions/rumble_actions.py`,
# Quem mediu isso não fui eu — foi o `portao_a_casa_sabe_e_o_produto_nao_faz`,
from hefesto_dualsense4unix.app.telas.vibracao import (  # noqa: E402
    DICA_DO_TETO_DA_MESA,
    DICA_DOS_VALORES_QUE_PASSAM,
    degraus_da_forca,
    html_do_estado,
    textos_do_estado,
)

CENA_DO_ESTADO = {"rumble_policy": "economia",
                  "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}}

_LINHAS = [
    l for l in csv.DictReader(
        x for x in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
         if not x.startswith("#"))
    if l["regiao"] == "vibracao"
]
if len(_LINHAS) != 2:
    raise SystemExit(f"ERRO: o mapa tem {len(_LINHAS)} peça(s) de vibração, e a aba "
                     f"desenha duas. Confira docs/data/pecas-do-dualsense.csv")

MOTORES = [
    {
        "id": l["no_svg"],
        "glifo": l["glifo"],
        "rot": f'{l["nome"].split()[0]} {l["nome"].split()[-1]}',
        "nome": l["nome"],
        "nota": l["nota"],
        "apelido": l["apelidos"],
    }
    for l in sorted(_LINHAS, key=lambda l: float(l["x1"]))
]
ESQ, DIR = MOTORES

#      entao a vibração dos 2 será 150%, mas se so a do motor fraco tiver 100 e  # noqa-acento: citação literal dela
# (`daemon/subsystems/rumble.py:20`). O `data-forca` do HTML carrega a CHAVE,
# (`a05_vibracao._aplicar_a_forca`, desfecho 3, medido em 04/09). Um botão a
# bem. `a05_vibracao._pct_da_coluna` chama `_pedido_da_politica`, que faz
# (`rumble_actions:414`, silêncio 3), e é mais honesto que acender um botão que
FORCA = [("Economia", "economia"), ("Balanceado", "balanceado"),
         ("Máximo", "max")]

if tuple(chave for _, chave in FORCA) != degraus_da_forca():
    raise SystemExit(
        f"ERRO: os degraus desta aba são {[c for _, c in FORCA]} e o "
        f"produto tem {list(degraus_da_forca())} (app/telas/vibracao."
        "degraus_da_forca). O `data-forca` é o endereço por onde a pintura acha "
        "o botão — divergir aqui faz a tela acender o degrau errado, em silêncio.")

#: passa a ser o do multiplicador personalizado — `RUMBLE_CUSTOM_MULT_MAX`, que
TETO = round(RUMBLE_CUSTOM_MULT_MAX * 100)

PASSO = math.gcd(*(round(m * 100) for m in RUMBLE_POLICY_MULT.values()), TETO)

TETO_DO_MOTOR = MOTOR_PCT_MAX

TETO_DA_HAPTICA = HAPTICA_PCT_MAX

#: regra é que a barra tenha uma parada em cima de **todo valor que a borda
#: aceita**. O esquema aceita `int` de 0 a 100 (`motor_forte_pct`), logo o passo
PASSO_DO_MOTOR = 1

#: que a peça sem opinião vale no motor, e o `state_full` o publica ao lado do
BARRA_DO_MOTOR_PADRAO = MOTOR_PCT_PADRAO

# Dois textos de tela existiam no `gui/main.glade` há semanas e não
# (`rumble_actions.BTN_GIVE_BACK_TO_GAME`, RUM-01).

#: `rumble_passthrough(True)` — `a05_vibracao.testar` (passos 3 e 4) e
SEM_A_FAIXA_DE_ESTADO = True

#: A CHAVE `propria` DIZ SE AQUELA COLUNA TEM AJUSTE PRÓPRIO — e ela é chave de  # (noqa-acento) chave da cena
ESTADO = {
    "p1": {"forca": "max",        "pct": 150, "propria": True,  # (noqa-acento) chave
           "esq": (True, 50),   "dir": (True, 100),
           "hap": (True, HAPTICA_PCT_PADRAO)},
    "p2": {"forca": "balanceado", "pct": 100, "propria": False,  # (noqa-acento) chave
           "esq": (False, 0),   "dir": (True, 100),
           "hap": (True, 180)},
    "p3": {"forca": "economia",   "pct": 30,  "propria": True,  # (noqa-acento) chave
           "esq": (True, 100),  "dir": (True, 100),
           "hap": (True, HAPTICA_PCT_PADRAO)},
    "p4": {"forca": "balanceado", "pct": 100, "propria": True,  # (noqa-acento) chave
           "esq": (True, 100),  "dir": (False, 0),
           "hap": (False, 0)},
}

CSS = """
  /* ---------- Vibração · a mesa de quatro ---------- */
  /* UMA GRADE SÓ, com uma coluna de rótulos e uma coluna por controle da MESA.
     As alturas de linha são variáveis porque as CINCO colunas as compartilham:
     é isso que faz o rótulo "Motor esquerdo" ficar na mesma linha dos quatro
     interruptores, e as cinco colunas acabarem no MESMO y — que é a régua dela.
     (A cura do vão é na ALTURA, nunca `space-between`.) */
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
  /* O RESPIRO VERTICAL É UMA ESCALA, E A DIVISÓRIA MORA NO MEIO DELE —
     31/08/2026, pedido dela: *"em vibração tem que ver a distribuição vertical
     dos elementos da tabela. tão todos colados nas linhas"*.

     O CENSO QUE MEDIU O DEFEITO (DOM, coluna do P1, antes da cura). A folga é da
     divisória até o conteúdo, acima e abaixo:

       faixa           altura  conteúdo   ↑acima  ↓abaixo
       Controle           124       112        —       16
       Modelo              17        13        2       12
       Força da vibração   79        79        0       10
       Personalizado       26        16        5       15
       Motor esquerdo      36        36        0       10
       Motor direito       36        36        0       10
       Testar agora        74        74        0        —

     QUATRO DAS SETE FAIXAS COM ZERO ACIMA — o conteúdo encostado na linha —
     e dez abaixo. Não é padding esquecido: é a soma de duas decisões que,
     sozinhas, estavam certas.

     1. As alturas de faixa foram calculadas para serem EXATAMENTE a altura do
        conteúdo: `--r-forca` 79 = 36 (`--h-escolha`) + 7 (vão do `.seg`) + 36;
        `--r-motor` 36 = o `.lado`, que é `--h-escolha`; `--r-acoes` 74 = 34
        (`--h-acao`) + 6 + 34. Sem uma sobra, o filho preenche a célula e o topo
        dele cai em cima da borda.
     2. A divisória era `::before` com `top:0` da própria célula — ou seja, na
        BORDA DE BAIXO do vão, e não no meio dele. Todo o respiro que existe
        (`--r-passo`) ficava de um lado só.

     A CURA É A ESCALA, e ela inverte quem deriva de quem: o dono passa a ser o
     RESPIRO (`--r-ar`), e o passo entre faixas é o dobro dele, por construção.
     A linha desce meio passo (`top:-var(--r-ar)`) e cai no MEIO do vão. Efeito:
     todo conteúdo centrado na sua célula fica centrado na sua FAIXA — porque a
     faixa passa a ser [meio-vão de cima, meio-vão de baixo], que tem o mesmo
     centro da célula. Nenhuma faixa pode voltar a ficar torta sem que alguém
     mude as duas coisas de uma vez, e agora elas são uma só.

     POR QUE 5px, E NÃO MAIS — o orçamento de altura, medido no mesmo dia:
     o miolo desta aba tem 544px visíveis e o quadro ocupa 540 (16+506+18).
     **Sobram 4px.** Cada pixel a mais de `--r-ar` custa 12 (6 divisórias × 2
     lados), então `--r-ar:6px` custaria 12 e a aba passaria a rolar — que é o
     que ela não pode fazer. Com 5, o passo continua 10 e a altura da tabela não
     muda um pixel: o que muda é de que lado da linha o vão está.
     Se um dia ela quiser mais ar, o preço sai de `--r-des` (o desenho é a única
     faixa com conteúdo elástico): −12px ali pagam `--r-ar:6px`, e o controle
     encolhe 11%. */
  .vib{
    display:grid;
    /* A LARGURA DA COLUNA DE RÓTULOS E O VÃO ATÉ A PRIMEIRA COLUNA DE
       CONTROLE VÊM DE `medidas.py` — o dono deles nas TRÊS abas que têm
       essa coluna. Eram 132px e 16 aqui, 138 e 12 na Gatilhos, e o texto
       acabava em x=536 numa e x=542 na outra. Ela viu: *"tem algo que
       deixa estranho essa área da primeira coluna."* */
    grid-template-columns:var(--larg-rot) repeat(4,1fr);
    gap:var(--gap-col);
    --r-des:124px;--r-nome:17px;--r-forca:112px;--r-barra:26px;--r-motor:36px;
    --r-acoes:34px;
    --r-ar:5px;--r-passo:calc(var(--r-ar) * 2);
  }
  /* SETE FAIXAS, E NÃO OITO — a oitava saiu em 05/09/2026 com a linha "Estado"
     (ver `SEM_A_FAIXA_DE_ESTADO`). Ela era um `minmax` de piso 20px e a única
     elástica da grade; com ela foram embora a variável do piso e um `--r-passo`
     de vão. MEDIDO na janela do produto (`ponte_da_tela.TAMANHO_OCULTA`, WebKit
     offscreen, 05/09/2026): o miolo rolava 74px e passou a rolar 43, e a grade
     caiu de 483px para 452 — 31px devolvidos.
     NÃO FECHA A `VIBRAÇÃO-CABE-01`, e o número fica dito: o alerta do gamepad
     virtual terminava 41px abaixo do fundo do miolo e agora termina 10px
     abaixo. A primeira das duas frases passou a caber; a segunda ainda não.
     A VARIÁVEL DO PISO NÃO É CITADA POR NOME AQUI DE PROPÓSITO: a régua 14 do
     `_conferir` pergunta o nome dela ao documento inteiro, e um comentário que
     o escrevesse reprovaria o próprio gerador.
     O `--r-acoes` PASSA A SER A ÚLTIMA FAIXA, e nada nas divisórias muda: a
     divisória de uma faixa é o `::before` da célula de BAIXO, e a que sumiu era
     a última — nenhuma linha horizontal dependia da altura dela. */
  .vib > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-forca)
                       var(--r-motor) var(--r-motor) var(--r-motor) var(--r-acoes);
  }
  /* O DESENHO NOVO DELA — 02/10/2026 (A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-
     DOIS-TESTES-01, a resposta [26] de 29/09). O trilho do Personalizado sobe
     para dentro da Força (`--r-forca` 112 = 79 dos degraus + 7 de vão + 26 do
     trilho, `--r-barra`), e a faixa que era dele vira a «Sensor Háptico», a
     linha da háptica por áudio (36, com o interruptor). A linha de baixo dos
     motores, que a háptica ocupava desde 29/09 com o desenho pagando 46 px,
     sai. E o «Testar agora» vira UMA linha («Vibração», «Háptica» e «Parar»,
     `--r-acoes` 34 = `--h-acao`): medido no WebKit da janela, os três pedem
     175 px e a coluna tem 206. Saldo: o desenho volta aos 124 px de antes de
     29/09 (o desenho dela não encolhe), e a grade cresce 3 px, de 452 a 455.
     Cabe com folga: medido no WebKit da janela do produto, sobram 108 px
     embaixo da grade, e a linha de estado com o aviso aceso cabe neles.
     O risco no meio do trilho da háptica marca 100%, o jogo como ele mandou.
     Onde o Hefesto não está no caminho do controle, a linha fica cinza e
     inerte; a bolinha verde depois do `%` é a luz «no ar»: há háptica
     chegando a este controle agora. */
  .vib .forca{display:flex;flex-direction:column;justify-content:center;gap:7px}
  .vib .forca > .motor{height:var(--r-barra);flex:none}
  .vib .ctrl[data-conectado="nao"] .forca > .motor{display:none}
  .motor.haptica .teto.no-ar.on::after{content:'';display:inline-block;width:6px;
    height:6px;border-radius:50%;background:var(--green);margin-left:3px;
    vertical-align:1px}
  .motor.haptica .trilho.arrasta{
    background:linear-gradient(to right,transparent calc(50% - 1px),
      var(--comment) calc(50% - 1px),var(--comment) calc(50% + 1px),
      transparent calc(50% + 1px)),var(--border-forte)}
  .motor.haptica.fora{opacity:.45}
  .motor.haptica.fora .trilho.arrasta,.motor.haptica.fora .lado{pointer-events:none}
  /* a barra vertical entre blocos irmãos — pedido dela */
  /* O PADDING SAIU DA COLUNA E FOI PARA AS CÉLULAS — 30/08/2026.
     A borda separadora mora na CÉLULA (`> div > *`), e padding na coluna
     recua a célula junto: a linha parava 21px antes da divisa e voltava a
     ler como tracinho. Com o padding na célula, ela vai de ponta a ponta da
     coluna e encosta na vizinha — o respiro do conteúdo é o mesmo. */
  .vib .ctrl{border-left:1px solid var(--linha);padding:0 10px 0 14px}

  /* ---------- O LUGAR VAZIO ----------
     A mesma gramática das outras quatro abas: cor explícita e NADA de `opacity`
     (a lição medida da `.fita.inerte`). O DESENHO fica cinza por `!important`
     porque a cor da peça é `style=` INLINE dentro do SVG, e regra externa não
     vence atributo inline sem isto.
     OS DETALHES CLAROS TAMBÉM CAEM — `text`, `line` e os `path` sem classe são
     os glifos L/R/PS e os traços dos botões, e só aparecem em desenho GRANDE.
     Medido na Iluminação no mesmo dia: copiar a regra da aba Jogar não bastava,
     porque lá o desenho tem 62px e aqui tem 124. */
  /* ---------- O LUGAR SEM CONTROLE, E SÃO OS QUATRO PELA MESMA REGRA ----------
     QUEIXA DELA, 05/09/2026: *"temos que entender se só tem um controle
     conectado só aparece config daquele. aba cinco tá errada."*

     E ESTAVA. Medido na tela viva com UM controle ligado: a segunda coluna
     mostrava `—` no Modelo e, logo abaixo, os TRÊS degraus, os três trilhos e
     os dois interruptores de motor — um deles ACESO em laranja. Controles
     vivos, clicáveis, para um aparelho que não está aqui. *Testar a vibração de
     um lugar vazio não é um botão fraco: é um botão que mente.*

     O MECANISMO JÁ EXISTIA E NINGUÉM O HONRAVA. O pacote calcula `vazios`
     (`pacotes/__init__.py`: os lugares para os quais a aba não emitiu coluna) e
     o piloto marca cada um com `data-conectado="nao"` e a classe `off` (passo
     1b do `_pintar`). O travessão dos CAMPOS já chegava — `dict.fromkeys(chaves,
     TRAVESSAO)`. O que não chegava era o sumiço dos WIDGETS, porque um botão
     não é campo de texto e nenhum `—` o apaga.

     A CURA É CSS, e por isso vale para a coluna que esvazia DEPOIS de a aba
     estar aberta — sem regerar nada, no tique seguinte. Os filhos saem e o
     `::after` põe o travessão no lugar deles.

     O `:not(.vazia)` MORREU EM 07/09/2026, e com ele a classe. Ele existia
     porque as duas colunas que NASCEM vazias eram outro HTML — um cartão sem um
     único `data-campo`, com `<span class="nada">—</span>` no lugar dos widgets
     — e o `> *` teria escondido o próprio travessão delas. Esse cartão era o
     defeito: o daemon publicava quatro controles, o pacote mandava as quatro
     colunas e **o dado do P3 e do P4 não tinha onde pousar** (ver `_coluna`).
     Fundidos os dois ramos, o lugar que nasce vazio é byte a byte o que o
     piloto produz quando um lugar esvazia — mesma marca, mesma folha, mesmo
     travessão —, e a exclusão passou a ser a única coisa capaz de separá-los.

     E A CLASSE TINHA DE MORRER, não só a exclusão: **o piloto tira a `off` e o
     `data-conectado`, e não conhece a `vazia`** (`_pintar`, passo 1c). Um
     cartão que nascesse com ela ficaria cinza para sempre — agora com o dado
     dela chegando por baixo, invisível. */
  .vib .ctrl[data-conectado="nao"]{border-color:var(--border-forte)}
  .vib .ctrl[data-conectado="nao"] .seg > *,
  .vib .ctrl[data-conectado="nao"] .motor > *,
  .vib .ctrl[data-conectado="nao"] .acoes-col > *{display:none}
  .vib .ctrl[data-conectado="nao"] .seg::after,
  .vib .ctrl[data-conectado="nao"] .motor::after,
  .vib .ctrl[data-conectado="nao"] .acoes-col::after{
    /* O TRAVESSÃO É O CARACTERE, NÃO O ESCAPE — medido em 05/09/2026.
       Escrito `content:"\\2014"`, o CSS lê `\201` como o escape (que são
       até seis dígitos hex) e sobra o `4` como texto: a tela mostrava um
       quadradinho seguido de "4". O escape só funciona com um espaço a
       separá-lo do que vem depois, e um espaço num `content` é um espaço
       na tela. O caractere literal não tem essa armadilha, é o MESMO que
       `VAZIO` usa nas colunas que nascem vazias, e o arquivo é UTF-8. */
    /* `grid-column:1/-1` NÃO É ENFEITE — medido em 05/09/2026. O `.seg` é
       grade de duas colunas e o `.motor` de quatro (36px · 1fr · 36px ·
       26px); sem atravessar, o `::after` vira item da PRIMEIRA célula e o
       travessão nasce encostado à esquerda, a 36px da borda, enquanto o
       das colunas que já nascem vazias fica no meio. Duas caras para o
       mesmo estado na mesma tela é o que esta regra existe para evitar. */
    /* `height:100%` NÃO É ENFEITE — é a régua de alinhamento falando. A coluna
       vazia tem a MESMA altura da viva (452px) e as mesmas sete linhas; o que
       acabava 26px antes era o CONTEÚDO da última célula: os botões
       preenchem a faixa `--r-acoes`, e um travessão centrado para no meio. A régua leu isso como "o conteúdo das colunas acaba em y
       diferentes", e leu certo. */
    content:"—";color:var(--linha);display:flex;align-items:center;
    justify-content:center;grid-column:1/-1;width:100%;height:100%}
  /* A MOLDURA E O NOME acompanham — senão o desenho do controle fica colorido
     em cima de uma coluna apagada. */
  .vib .ctrl[data-conectado="nao"] .moldura{border-color:var(--border-forte)}
  .vib .ctrl[data-conectado="nao"] .rot-ctrl{color:var(--linha)}
  /* O DESENHO DO LUGAR VAZIO NÃO SE PINTA AQUI — 07/09/2026, e a razão é que
     ele tem DONO. Havia catorze linhas nesta folha pintando o `<svg>` de
     `var(--linha)` (`.ctrl.vazia .ds-svg rect`, `circle`, `polygon`, `ellipse`,
     `text`, `line`, `path`…), e elas existiam porque o `.vazia` ficava DE FORA
     da regra compartilhada. Com a classe morta, quem responde é
     `monta.py` — `[data-controle][data-conectado="nao"]:not(.vazia) .ds-svg
     {visibility:hidden}`, a S-04 de 05/09/2026, palavra dela: *"os svgs não
     deveriam aparecer prós demais controles desconectados"*.

     MANTÊ-LAS SERIA O SEGUNDO DONO do mesmo fato, e o pior tipo: um desenho
     cinza por baixo de um `visibility:hidden !important` é código que ninguém
     vê falhar. Se ela quiser o desenho cinza DE VOLTA no lugar vazio, o lugar
     de dizer isso é a folha compartilhada — e vale para as quatro abas de uma
     vez, que é a razão de aquela regra morar lá. */
  /* o respiro entre colunas é do CONTEÚDO, não da célula: padding na coluna
     recua os filhos e a borda deles para 16px antes da divisa, e a linha
     volta a quebrar. Aqui a célula vai até o fim e quem se afasta é o texto. */

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido dela, 30/08:
     *"as linhas horizontais deveriam separar os campos em linhas"*. É a mesma
     cura da Iluminação, e o motivo de estar na CÉLULA (e não na grade) é o
     mesmo: as sete linhas não são de `.vib`, são de cada coluna, com as mesmas
     alturas nas cinco — as bordas nascem no mesmo y e leem como uma linha só.
     A última não leva: separador depois do último campo vira moldura. */
  /* A LINHA É UM PSEUDO-ELEMENTO, e não a borda da célula — 30/08/2026.
     Como BORDA ela parava no padding da coluna e quebrava em cinco tracinhos;
     movendo o padding para as células a linha ficou inteira mas o desenho do
     controle perdeu 9px (a moldura tem `overflow:hidden` e o SVG cresce com a
     largura). O `::after` com margem negativa resolve os dois: ele sai do
     padding pelos dois lados e atravessa a coluna inteira, sem tocar em
     geometria nenhuma. As cinco colunas têm as mesmas alturas de linha, então
     os cinco segmentos nascem no mesmo y e leem como uma linha só. */
  .vib > div > *{position:relative}
  /* A LINHA É `::before` DA CÉLULA DE BAIXO, e não `::after` da de cima.
     Como `::after` ela era filha da moldura — e a moldura do DESENHO tem
     `overflow:hidden` para conter o SVG, então ela cortava a própria linha
     26px antes da divisa. A célula de baixo não recorta nada, e o traço
     cai no mesmo lugar: entre uma linha e a outra. */
  /* `top` NEGATIVO DE MEIO PASSO — é o que põe a linha no MEIO do vão em vez de
     na borda de baixo dele (ver a escala `--r-ar`, no `.vib`). Nenhuma célula
     recorta: a única com `overflow` era a moldura do desenho, e a primeira
     célula não desenha divisória nenhuma. */
  .vib > div > *::before{content:'';position:absolute;top:calc(var(--r-ar) * -1);height:0;
    left:-14px;right:-10px;border-top:1px solid var(--rot-linha)}
  /* A CONTA DA MARGEM NEGATIVA: ela tem de cancelar o padding da coluna E o
     `gap` do grid, senão sobra um buraco do tamanho do vão. À direita são
     10 de padding + 16 de gap = 26; a ÚLTIMA coluna não tem vão depois
     dela, então volta a 10. A coluna de rótulos não tem padding: 0 e 16. */
  .vib > div:not(:last-child) > *::before{right:-26px}
  .vib > .rotulos > *::before{left:0;right:-16px}
  .vib > div > *:first-child::before{display:none}
  /* NÃO HÁ COLUNA DESTACADA, e é decisão dela de 28/08: os quatro ficam lado a
     lado, sempre visíveis, e a fita do topo fica ESMAECIDA (fora de `monta.ABAS_QUE_ESCOLHEM`).
     Aqui havia um `.ctrl.escolhido` — fundo `--sel-bg` e rótulo em negrito na
     coluna do P1 — com o `title` "A fita do topo aponta para este controle".
     Com a fita inerte e presa em "Todos", esse destaque passou a AFIRMAR NA
     TELA uma coisa que a fita já não faz: a tela se contradiria sozinha, que é
     o defeito que esta casa mais paga. Saiu o destaque, não a barra. */

  /* a coluna dos rótulos: todo título começa no mesmo x, e cada um ocupa a
     ALTURA INTEIRA da sua linha — é assim que a coluna acaba junto das outras */
  .vib .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
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
  .vib .rotulos > *{align-items:flex-start;text-align:left}
  .vib .rotulos .sec-rot{justify-content:flex-start}
  /* O RÓTULO OCUPA A ALTURA INTEIRA DA LINHA, e o texto fica centrado dentro
     dele. Não é enfeite: sem isto o rótulo da última linha acaba 29px acima dos
     botões que ele nomeia, e a régua lê — com razão — um vão entre as colunas.
     A cura é na ALTURA, que é a regra dela. */
  .vib .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  /* O VERDE DESTA ABA VIROU O PADRÃO DAS DEZ em 30/08 (`--rot-campo`, em
     `topo.html`), e a exceção escopada em `.vib` que vivia aqui virou redundância. */
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
  /* a regra `.legenda` saiu: depois que a prosa virou dica, zero elementos a usavam. */
  /* A DICA NÃO É TÍTULO: sem isto ela herda o `text-transform:uppercase` do
     rótulo e o parágrafo inteiro sai em CAIXA ALTA — visto no navegador. E ela
     abre PARA CIMA: nas linhas de baixo da tabela, aberta para baixo, a janela
     (que tem `overflow:hidden`) cortava o fim do texto. */
  .vib .rotulos .dica{text-transform:none;letter-spacing:0;top:auto;bottom:-4px}
  /* O RÓTULO DA PRIMEIRA LINHA VOLTOU A CENTRAR — 30/08/2026.
     Ele estava preso no topo (`flex-start`) porque a legenda de sete linhas vinha
     logo abaixo dele e as duas juntas enchiam a célula. A legenda virou dica no
     mesmo dia, e o `flex-start` sobrou: o rótulo ficava sozinho no alto de uma
     célula de 124 px, com o vazio inteiro embaixo. Centrado, ele fica na altura
     do desenho que nomeia — a cura do vão é na ALTURA, regra dela. */
  .vib .rotulos .cel-des{gap:8px}

  /* O DESENHO: a borda tem a cor do plástico, sempre — é como ela sabe de quem é
     a vibração que está vendo (D-A-BORDA-E-A-IDENTIDADE-DA-PECA). A borda mora
     na CAIXA, não na coluna: `border-top` na coluna empurraria as sete linhas
     2px para baixo e o rótulo deixaria de casar com o das vizinhas. */
  .vib .moldura{
    border:1px solid var(--plastico, var(--border-forte));border-radius:8px;
    background:var(--app-bg);
    display:flex;align-items:center;justify-content:center;padding:5px;
  }
  /* ALTURA e não largura: a linha tem altura fixa e o desenho tem de caber nela.
     Com `width:100%` o SVG estouraria a linha e empurraria tudo. */
  .vib .moldura .ds-svg{height:100%;width:auto;max-width:100%}
  .rot-ctrl{font-size:11px;color:var(--texto-mudo);text-align:center;
            display:flex;align-items:center;justify-content:center}

  /* OS TRÊS DEGRAUS DE FORÇA — 2 em cima, o terceiro OCUPANDO A LARGURA.
     Eram quatro em 2x2 até o `Auto` sair em 05/09/2026 (ver :data:`FORCA`), e
     com três o 2x2 puro deixava o "Máximo" sozinho e curto na segunda linha —
     o desenho anunciando um quarto botão que não existe.

     OS TRÊS NUMA LINHA SÓ NÃO CABEM, e isto foi MEDIDO em vez de estimado: a
     coluna tem 227,5px, o `.ctrl` recolhe 24 e sobram 203 para três botões mais
     dois vãos. "Balanceado" mede 68px a 12px de fonte, e o botão fica com 63.
     Varridas 27 combinações de vão (7/5/4), fonte (12/11,5/11) e recuo (8/4/2),
     a MELHOR ainda estoura em 2px — e mesmo com o recuo do pai a zero o texto
     ocupa 68 de 72, sem respiro. Encolher a fonte até caber daria um degrau com
     letra menor que o resto da tela para esconder um problema de largura.

     O `span 2` do terceiro é o que faz a falta do quarto parecer o que é: uma
     escolha. E ele não custa altura nenhuma — `--r-forca` continua nos 79 que
     as duas faixas sempre custaram.

     QUANDO A COLUNA CRESCER, os três cabem lado a lado e este bloco volta a ser
     `repeat(3, 1fr)` com `--r-forca:36px` — são 43px devolvidos à aba que mais
     rola. A medição acima é o que diz a partir de que largura isso vale. */
  .vib .seg{display:grid;grid-template-columns:1fr 1fr;gap:7px}
  .vib .seg button:last-child{grid-column:1 / -1}
  .vib .seg button{min-width:0;padding:0 8px;font-size:12px}

  /* O DEGRAU HERDADO TEM CARA PRÓPRIA — VIBRA-ACESA-01, 17/09/2026.

     A coluna que NÃO tem ajuste próprio herda a força geral, e até hoje isso
     aparecia como NADA: o pacote emitia `degrau=""`, o alvo `classe` apagava os
     três, e ela leu o resultado como defeito — *"o botão não tá ativo"*, com a
     coluna ao lado marcando 150%.

     A decisão [05] dela (04/09) mandava o herdado acender na LINHA DE MESA, e a
     linha de mesa foi apagada em 05/09 pela decisão dela de não ter mesa em
     nada da interface. O herdado ficou sem lugar. Aqui ele ganha o lugar que
     sobrou, que é o botão: ACESO, porque é a força que a mão dela sente, e
     DIFERENTE do escolhido, porque procedência é informação — foi exatamente
     isso que a decisão [05] pediu, e só o endereço dela é que mudou.

     A MARCA É O TRAÇO, NÃO A COR: o preenchimento de `.seg button.on` continua
     dizendo "ligado" e a borda tracejada diz "veio de fora". Trocar a cor faria
     o olho ler outro ESTADO; trocar o traço faz ele ler a mesma força com outra
     origem. E o peso volta ao normal — negrito é o que ela escolheu para esta
     coluna. */
  .vib .seg.herdado button.on{background:transparent;border-style:dashed;
                              font-weight:500}

  /* AS TRÊS BARRAS DE UM CONTROLE NA MESMA GRADE — a Força e os dois motores.
     Quatro colunas fixas: interruptor · trilho · número · sufixo. A da Força não
     tem interruptor, e a célula fica vazia de propósito: é o que faz os três
     trilhos começarem e acabarem no mesmo x, que é o refinamento que ela cobrou. */
  .motor{display:grid;grid-template-columns:36px 1fr 36px 26px;align-items:center;
         gap:8px;height:100%}
  .motor .trilho{height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .motor .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .motor .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--panel)}
  .motor .num{text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg)}
  /* `.teto` AQUI É O SUFIXO DA ESCALA — o "/255" e o "Máx" que dizem em que
     unidade o número ao lado está. **Não é o "Teto da vibração"**, que é outra
     coisa e mora na aba Conexões (global + por controle, decisão dela de
     28/08 — hoje "sem teto agora"). Esta aba não escreve teto nenhum.

     "máx" VIROU "Máx" — 28/08/2026. Ela apontou o padrão na Conexões ("• o rádio
     de cada adaptador, em fatias") e mandou caçar rótulo visível começando em
     minúscula em TODAS as abas. Este é o único caso desta aba, e foi a única
     coisa tocada aqui: a Vibração está FECHADA por elogio literal dela
     (`CORRECOES-DELA.md:39`). O irmão "/255" fica como está — barra e dígito não
     têm caixa. */
  .motor .teto{font-size:10.5px;color:var(--comment);font-family:'JetBrains Mono',monospace}
  /* O `Máx` SOME RESERVANDO O ESPAÇO — decisão 11 dela, 03/09/2026.
     `visibility:hidden`, nunca `display:none`: nada se mexe quando ele acende ou
     apaga, e esta aba é para olhar enquanto o jogo treme. A palavra fica SEMPRE
     no HTML e quem a acende é a classe `on`, que o produto escreve pelo alvo
     `classe` (`data-campo="mult-teto"`). */
  .motor .teto.mx{visibility:hidden}
  .motor .teto.mx.on{visibility:visible}
  /* o lado desligado não finge que tem força: o trilho fica apagado */
  .motor.off .cheio{background:var(--border-forte)}
  .motor.off .num{color:var(--comment)}
  /* O TRILHO ARRASTÁVEL — 03/09/2026, decisão dela: *"0 a 200%, e grava na
     hora."* Ele é um `<input type=range>` de verdade, e não um trilho pintado:
     é o `value` dele que o piloto lê no `change`.

     A APARÊNCIA NÃO MUDA UM PIXEL DE PROPÓSITO. A Vibração está FECHADA por
     elogio literal dela (`CORRECOES-DELA.md:39`), e um controle nativo do
     WebKit ali dentro traria a cor e a altura do tema do sistema no meio de uma
     tela que ela aprovou. `appearance:none` desliga o desenho nativo e as duas
     regras abaixo reconstroem EXATAMENTE o que o `.trilho` + `.cheio` já eram:
     5px de altura, raio 3, o fundo `--border-forte` e o polegar de 12px em
     `--purple` com a borda `--panel`.

     O CHEIO É UM GRADIENTE, e não um filho: um `<input>` não tem onde pendurar
     o `<span class="cheio">`, então a parte preenchida vem de
     `background-size` — o piloto escreve o `value`, o navegador move o polegar,
     e o `--pct` do gradiente acompanha por `accent-color`... que o WebKit2 desta
     versão não pinta em trilho customizado. Por isso o preenchimento fica no
     próprio `--purple` do polegar e o trilho inteiro no tom apagado: o que
     informa a posição é o POLEGAR, que é o que ela arrasta.

     `cursor:grab` diz que a coisa se pega — a única affordance que o desenho
     ganhou, e ela não desloca nada. */
  .motor .trilho.arrasta{appearance:none;-webkit-appearance:none;
    width:100%;padding:0;margin:0;border:0;background:var(--border-forte);
    cursor:grab}
  .motor .trilho.arrasta:active{cursor:grabbing}
  .motor .trilho.arrasta::-webkit-slider-runnable-track{
    height:5px;border-radius:3px;background:transparent}
  .motor .trilho.arrasta::-webkit-slider-thumb{appearance:none;
    -webkit-appearance:none;width:12px;height:12px;border-radius:50%;
    background:var(--purple);border:2px solid var(--panel);margin-top:-4px}
  .motor .trilho.arrasta:focus-visible{outline:2px solid var(--purple);
    outline-offset:3px}

  /* o interruptor de cada lado: o GLIFO do mapa, aceso quando o lado está ligado */
  .lado{
    height:var(--h-escolha);width:36px;border-radius:7px;font-family:inherit;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--texto-mudo);
    cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;
  }
  .lado.on{border-color:var(--orange);background:rgba(255,184,108,.1);color:var(--orange)}
  .lado:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}

  /* os dois testes lado a lado («Vibração» e «Háptica», a resposta [24] dela)
     e o «Parar» na mesma linha, no tamanho do texto dele: os dois testes
     dividem o resto (75 px cada, para os 62 que «Vibração» pede) */
  .acoes-col{display:grid;grid-template-columns:1fr 1fr auto;gap:6px}
  .acoes-col .btn{width:100%;justify-content:center;padding:0 6px;font-size:11.5px}
  /* o Testar aceso é o teste ligado naquela coluna: a mesma cor do lado que treme */
  .acoes-col .btn.on{border-color:var(--orange);background:rgba(255,184,108,.1);color:var(--orange)}

  /* O LADO QUE TREME — e onde entra a cor do plástico (D-O-SVG-VIBRA-POR-LADO,
     palavra dela: "Parte esquerda vibra mostrando a cor do motor esquerdo").
     O traço é LARANJA porque o contorno do desenho já é a cor do plástico:
     pintar o traço de plástico apagaria o lado em vez de mostrá-lo. Quem diz de
     quem é o tremor é o CONTORNO (e a borda da moldura), que são o plástico; o
     halo em `--plastico` só reforça. É isso, e não outra coisa, que o rótulo da
     coluna promete — a frase dizia "acende na cor do plástico" e contradizia
     este laranja na mesma tela (visto na foto, 27/08).
     E o `stroke-width` é obrigatório: o traço de fábrica tem 0,35 unidade, que
     neste tamanho vira meio pixel e some no antialiasing — o lado aceso ficava
     bege, não laranja. Medido no Chrome em 27/08.
     O PREENCHIMENTO não serve aqui: medido com `fill-opacity:1`, o caminho do
     motor é um anel fino, e pintá-lo não acrescenta um pixel ao que o traço já
     cobre. */
  .vib .ds-svg [id$="-feat-rumble-esquerdo"] .peca,
  .vib .ds-svg [id$="-feat-rumble-direito"] .peca{stroke:var(--orange);stroke-width:1}
  /* DEFEITO DO DESENHO COMPARTILHADO, contornado aqui: o grupo do motor direito
     carrega `style="opacity:.55"` de fábrica, e estilo em linha vence a regra
     `.oculta{opacity:0}` do esqueleto — o motor direito aparecia meio aceso em
     TODA aba que desenha o controle, mesmo apagado. O conserto de verdade é no
     `ds_limpo.svg`/`importar.py`, que não são desta aba. */
  .vib .ds-svg .oculta{opacity:0 !important}
  .vib .ds-svg .oculta.acesa{opacity:.95 !important;
                             filter:drop-shadow(0 0 1.8px var(--plastico, var(--border-forte)))}

  /* ---------- A LINHA DO ESTADO — 02/09/2026 ----------
     A janela estável tem QUATRO avisos nesta aba e a interface nova não tinha
     nenhum. Eles não são decoração: um deles é o "a intensidade que você
     escolheu não chega a jogo nenhum", que ficou onze dias sem tela.

     TRÊS TONS, e o nome do tom vem do produto (`app/telas/vibracao.DIZ`,
     `.ALERTA` e `.INFO`), nunca um hex emitido pelo Python: `diz` conta o que
     está acontecendo, `alerta` avisa que o que ela escolheu não chega, `info`
     explica sem alarmar. O laranja é o `--orange` do tema, o MESMO `#ffb86c`
     que a janela estável usa nestas linhas — um token, não uma segunda cópia
     da cor.

     `:empty{display:none}` é o que deixa a linha SUMIR quando não há o que
     dizer. É a metade que o pintor não sabe fazer: `escrever()` troca vazio por
     travessão, e um `—` numa linha de alerta afirmaria "não sei" onde a
     resposta certa é "não há nada a avisar". Por isso o bloco inteiro é
     trocado (`p.blocos`) em vez de pintado campo a campo. */
  /* A CONTA DA MARGEM, e ela é apertada por CONSTRUÇÃO. `4px 4px 0` em vez do
     `12px 4px 2px` que a linha nasceu tendo — os 10 px que sobram são o que
     mantém o estado NORMAL sem barra de rolagem.

     FATO SUBSTITUÍDO — 02/09/2026, e o número anterior foi medido na cena
     errada. Este comentário dizia "o quadro tinha 476: sobravam 24 px" e
     "com aviso a aba rola, e isso é de propósito: os dois alertas só aparecem
     em ESTADO EXCEPCIONAL". As duas metades caíram na mesma medição.

     MEDIDO no WebKit da janela do produto (1180x757 — o `TAMANHO_NA_TELA`, e
     não o `TAMANHO_OCULTA`, que é 143 px mais alto e responderia "não rola"
     sempre), com a MESA DELA — dois controles, um `usb` e um `bt`, `vpads == 0`
     —, injetando o BOOTSTRAP do piloto e pintando a carga do
     `a05_vibracao.pacote()`. A régua está versionada:
     `tests/unit/test_o_aviso_da_vibracao_cabe_na_aba.py`.

       .miolo: client 564 · fundo em 733 px
       a cena CRAVADA (1 linha) ................ estado 18 px · rola 0
       a mesa dela, com a frase de 211 chars ... estado 60 px · rola 40 · CORTADA
       a mesa dela, com a frase de hoje ........ estado 42 px · rola 22 · inteira

     A FRASE ENCURTOU — decisão dela, 02/09, ciente do custo. A de 211
     caracteres ocupava 1072 px de 1072: quebrava em duas sublinhas e a segunda
     — "que você fixar aqui embaixo." — terminava em 740 px, SETE px abaixo do
     fundo do miolo. Fotografado. A de hoje tem 162 caracteres, ocupa 942 px e
     cabe numa sublinha; o aviso se lê inteiro sem arrastar.

     A frase é a MESMA da janela GTK e tem um dono só
     (`rumble_actions.texto_do_alcance_da_intensidade`) — encurtar ali encurtou
     as duas telas, de propósito.

     SOBRAM 22 px DE ROLAGEM, e eles não são texto: são DUAS mensagens acesas ao
     mesmo tempo (a dos pedidos e a do alcance) onde o desenho reservou UMA — 42
     px contra 20 de folga. `vpads == 0` não é excepcional, é o estado corrente
     da mesa dela. Caber os 22 exige encolher a tabela que ela aprovou, e o
     `.miolo` (16px 3px 18px 18px) é do `topo.html`, comum às dez abas: é
     DECISÃO DELA, não pixel. As saídas estão em `mockup/DIVERGENCIAS.md`. */
  /* OS DEZ PIXELS QUE FALTAVAM — VIBRAÇÃO-CABE-01 FECHA EM 05/09/2026.
     A régua acusava o alerta terminando 41 px abaixo do fundo do miolo; a saída
     da faixa "Estado" devolveu 31, e estes dez são os últimos. Eles saem do
     ESPAÇAMENTO DESTE RODAPÉ, e de mais lugar nenhum:

       margin-top   4 -> 0    o rodapé já vem depois da grade, com a folga dela
       gap          6 -> 2    entre a ressalva e o alerta
       line-height  1,5 -> 1,4 nas duas linhas do `.est`

     O QUE **NÃO** PAGOU A CONTA, e as duas exclusões são regra desta casa: a
     FRASE (texto de tela é decisão dela — o dono é
     `rumble_actions.texto_do_alcance_da_intensidade`, e encurtá-la por pixel
     seria eu decidindo o que ela lê) e a TABELA que ela aprovou, junto com o
     `.miolo` do `topo.html`, que é comum às dez abas.

     Medido depois: o alerta termina em 733 px e o fundo do miolo é 733. */
  .vib-estado{margin:0 4px 0;display:flex;flex-direction:column;gap:2px}
  .vib-estado:empty{display:none}
  .vib-estado .est{display:flex;gap:8px;align-items:flex-start;
                   font-size:12px;line-height:1.4}
  .vib-estado .est .sinal{flex:0 0 auto;font-size:9px;line-height:1.9}
  /* O TOM `diz` SAIU — 07/09/2026, com a única frase que o vestia. Ordem dela,
     olhando o pé do quadro com os quatro na mesa: *"Vibração remove essa última
     frase também."* Ver `app/telas/vibracao.SEM_A_CONTAGEM_DE_PEDIDOS`.

     A REGRA SAI JUNTO E NÃO É ZELO: `.est.diz` era o cinza da contagem de
     pedidos, e nenhuma outra linha desta faixa usa esse tom. Cor que nada veste
     é a metade órfã de uma promessa — o mesmo par que o
     `portao_a_casa_sabe_e_o_produto_nao_faz` cobrou em 05/09, quando a faixa de
     estado saiu e as cinco peças da trava ficaram sem chamador.

     O QUE ESTA REGRA JÁ TINHA CUSTADO, e fica registrado porque foi medido: em
     03/09 o marcador dela era VERDE, e a foto da tela dela mostrava
     `● (verde) não há gamepad virtual` colado a `▲ (laranja) A intensidade não
     está chegando a jogo nenhum` — o MESMO fato com marcadores de sentido
     oposto. A cura foi o marcador herdar a cor do texto, que é o que os dois
     tons restantes fazem (`alerta` laranja/laranja, `info` ciano/ciano). */
  .vib-estado .est.alerta{color:var(--orange)}
  .vib-estado .est.alerta .sinal{color:var(--orange)}
  /* O TERCEIRO TOM, e ele é o da janela estável: `#8be9fd` é o token de INFO da
     casa, o que ela usa na frase "grava aqui, manda ali"
     (`rumble_actions.py`, com o comentário "a frase explica, não alarma").
     Ela saía como `diz` — o cinza — e o erro só apareceria na tela no dia em
     que a MIGRA-VIBRACAO-04 ligasse o alvo por controle. `--cyan` é o mesmo
     hexadecimal, já declarado no `topo.html`. */
  .vib-estado .est.info{color:var(--cyan)}
  .vib-estado .est.info .sinal{color:var(--cyan)}
  /* O QUARTO TOM — o RECIBO, e ele nasce com a 05-Q4 dela (06/09/2026):
     *"Linha embaixo da grade (…) nomeando a coluna (`P2 · voltou ao ajuste
     geral`) e some logo depois; nada se mexe dentro das colunas"*.

     VERDE É A COR QUE ESTA CASA JÁ USA PARA O QUE DEU CERTO, e não uma quinta
     invenção: o `--green` já está declarado no `topo.html`. E não pode ser o
     `alerta`: laranja sobre um clique que GRAVOU ensina que o botão falha, que
     é o defeito que a D-01 fechou em 04/09.

     ESTA REGRA NÃO TEM MAIS NÓ A VESTIR — 13/09/2026, FRASES-E-DICAS-01. Ela
     vestia o recado que o piloto pousava nesta faixa pelo endereço que o
     `#vib-estado` declarava, e o piloto deixou de pôr frase na tela: o sucesso
     na TELA-CALADA-01 (*"em todas as abas da interface"*), a recusa nesta. O
     endereço saiu do miolo; a regra fica porque o tom `recibo` ainda é nome do
     pacote (`a05_vibracao.TOM_DO_RECIBO`), que não é desta posse. Ela não
     pinta pixel nenhum. */
  .vib-estado .est.recibo{color:var(--green)}
  .vib-estado .est.recibo .sinal{color:var(--green)}

  /* AS QUATRO REGRAS DA `.vib .ressalva` SAÍRAM em 05/09/2026, com a faixa que
     era a única a usá-las. Elas vestiam a `monta.ressalva` que ficava dentro da
     grade; sem a faixa não há uma `.ressalva` dentro da `.vib`, e CSS para
     elemento que a página não tem é a segunda cara de um dado morto. A peça
     comum segue na folha das dez (`monta.CSS_FOLHA`), intacta para as outras
     abas. */

  /* ---------- A `.vib-nota` SAIU — 05-Q2 dela, 05/09/2026 ----------
     *"As duas na dica."*

     A REGRA DA NOTA MORREU JUNTO COM A LINHA QUE ELA VESTIA. O que ela
     pintava — a frase :data:`DICA_DOS_VALORES_QUE_PASSAM` como linha
     permanente embaixo da grade — voltou para o `?` do "Testar agora".

     AS DUAS METADES DA RAZÃO DE 04/09, e só uma caducou:

     · **"a frase é LIDA do glade e nunca redigitada"** — VALE, e vale para
       sempre. É ela que evitou a segunda cópia de um texto de tela, e o
       endereço da leitura continua em :data:`DICA_DOS_VALORES_QUE_PASSAM`.
     · **"ela sobe para a tela"** — CADUCOU em 05/09/2026, decisão dela na
       05-Q2. A atribuição *"decisão [02] dela, 04/09/2026"* que esta aba
       carregava em quatro lugares era do PO, não dela: a fonte real é a
       `ONDA2-05-VIBRACAO-01`, que decidiu no lugar dela a partir do
       `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`. Hoje ela
       respondeu a pergunta, e **a palavra dela vence a atribuição**.

     O CUSTO QUE ELA ACEITOU, e estava escrito na opção que ela escolheu: quem
     testar em Economia com as barras em 220 não descobre NA TELA por que o
     tremor saiu fraco — descobre passando o rato no `?`. Ela leu isso e
     escolheu assim mesmo.

     NÃO SOBRA CSS: a regra `.vib-nota` era a única a usar esta classe, e folha
     para elemento que a página não tem é a segunda cara de um dado morto — a
     mesma lição das quatro regras da `.vib .ressalva`, logo acima. */
"""

# que já esteve digitado no mockup). Ele não é desenhado aqui; segue desenhado

PAPEIS_QUE_SAO_GESTO = ("forca", "testar", "parar",
                        "intensidade", "motor", "haptica", "testar-haptica")


def _endereco_de_pintura(nome, extra=""):
    """`data-papel` quando o nome é gesto desta aba; `data-hef` quando não é."""
    atributo = "data-papel" if nome in PAPEIS_QUE_SAO_GESTO else "data-hef"
    return f' {atributo}="{nome}"' + extra


def _trilho_arrastavel(valor, teto, campo):
    """O trilho da "Personalizado" como `<input type=range>` — 03/09/2026.

    DECISÃO DELA: *"0 a 200%, e grava na hora."* Até hoje esta linha era
    LEITURA — um `<div>` sem `value` — e o gesto `forca` recusava o clique nela
    com um `ValueError` que **não chega à tela**: o contrato do piloto manda
    `RuntimeError` ao cartão e deixa o `ValueError` no `stderr` de quem lançou a
    janela (`hefesto_vivo._recusou_dizendo`). Para ela, clicar na barra não
    fazia nada, sem uma letra de explicação.

    E O `<div>` ERA A CAUSA, por escrito: `a05_vibracao.SEM_DONO["barra:motor"]`
    já nomeava o mesmo defeito na linha vizinha — *"o ouvinte manda
    `valor: alvo.value ?? ''` e um `<div>` não tem `value`"*. Um
    `<input type=range>` tem, e o ouvinte de `change` do piloto já o escuta
    desde 01/09.

    OS TRÊS NÚMEROS SÃO DERIVADOS: `max` é :data:`TETO` (do
    `RUMBLE_CUSTOM_MULT_MAX` do esquema), `step` é :data:`PASSO` (o MDC dos
    degraus com o teto) e `min` é zero — que é o único que se escreve, porque
    "nada de vibração" não é um número que alguém decidiu, é o fundo da escala.

    O ALVO DE PINTURA É `valor`, e não `largura`: quem move o cursor agora é o
    `value` do próprio elemento (`hefesto_vivo.escrever`, ramo `alvo ===
    'valor'`). Pintar `style.width` num `<input>` esticaria o controle em vez de
    mover o polegar dele.
    """
    return _trilho(valor, teto, PASSO, campo, "intensidade",
                   f'Quanto da vibração chega a este controle — 0 a {teto}%.'
                   f' Grava na hora, só para ele.')


def _trilho(valor, teto, passo, campo, papel, titulo, extra=""):
    """O `<input type=range>` das TRÊS barras que se arrastam nesta coluna."""
    return (f'<input class="trilho arrasta" type="range" min="0"'
            f' max="{teto}" step="{passo}" value="{valor}"'
            f' data-papel="{papel}" data-campo="{campo}"'
            f' data-hef-alvo="valor"{extra}'
            f' title="{titulo}">')


def _barra(valor, teto, sufixo, ligado=True, botao="", papel="forca", lado="",
           campo_num="", sufixo_html="", arrasta=False, campo_trilho="",
           vazio=False):
    """Uma linha de barra: interruptor · trilho · número · sufixo.

    `vazio` TROCA SÓ O TEXTO DO NÚMERO pelo travessão — 07/09/2026, com a fusão
    dos dois ramos de coluna (ver :func:`_coluna`). A ESTRUTURA e os ENDEREÇOS
    são os mesmos nos quatro lugares; o que um lugar sem controle não pode ter é
    um número afirmado. `0` ali seria a tela dizendo *"este motor está em zero"*
    sobre um aparelho que não está na mesa — e o travessão é a palavra que esta
    casa usa para *"isto eu não sei"*.

    `arrasta` troca o trilho de LEITURA pelo `<input type=range>` da decisão
    dela de 03/09 — ver :func:`_trilho_arrastavel`. Aqui só a linha do
    "Personalizado" o pede; as duas de motor têm builder próprio
    (:func:`_barra_de_motor`) desde 04/09.

    **FATO SUBSTITUÍDO, e quem o derrubou foi ELA.** Esta linha dizia *"as duas
    de motor continuam leitura, porque o par `weak`/`strong` viaja JUNTO ao
    daemon e um arraste por lado mandaria meio par"*. Era verdade enquanto a
    barra do motor fosse um comando (`rumble.set`). Ela decidiu em 04/09/2026 —
    fora das opções que eu ofereci — que a barra **não manda o par: ela é
    POLÍTICA que MULTIPLICA o degrau**, e as duas são independentes de propósito
    (*"se so a do motor fraco tiver 100 e a outrqa 50% então será 150 em um e  # noqa-acento: citação literal dela
    75% no outro"*). O método que grava uma barra sem a outra existe desde o
    mesmo dia (`rumble.motores.set`, campo omitido não mexe naquela barra).

    `papel`/`lado` são o ENDEREÇO DO CLIQUE, e sem eles a pintura só alcança as
    três barras de uma coluna por POSIÇÃO — que é o casamento que quebra em
    silêncio no dia em que alguém trocar duas linhas aqui.

    `campo_num` é o ENDEREÇO DO NÚMERO quando ele NÃO PODE ser o nome do papel,
    e entrou em 02/09/2026. O pintor procura um valor por
    `[data-campo=X],[data-papel=X],[data-hef=X]` (`hefesto_vivo.py:74`): um
    nome que seja `data-papel` de um botão e `data-campo` de um número faz a
    pintura escrever o valor DENTRO do botão. Era o caso do `forca` — a linha
    do "Personalizado" tinha `data-papel="forca"` e `data-campo="forca"`, e os
    quatro degraus da coluna também são `data-papel="forca"`. Um tique escrevia
    `"balanceado"` em dez elementos e apagava a linha inteira.

    SÓ O NÚMERO TROCA DE NOME, e o trilho continua `forca-pct`. Não é descuido:
    o trilho nunca esteve em colisão — ele é um `<span>` filho, e o que o apagava
    era a pintura do PAI. Renomeá-lo junto seria mais bonito e custaria caro
    agora: o `casamento.py:54` mede contra a página PUBLICADA, e a publicação é
    ato DELA — um nome novo lá vira órfão até ela publicar. Quando a
    `05-vibracao` sair da `mockup/DIVERGENCIAS.md`, unificar o par em
    `mult`/`mult-pct` é uma linha aqui e uma no pacote.

    Quando não se diz nada, o número herda o nome do papel — que é o que as
    barras dos motores querem (`motor-e`, `motor-d`), porque ali o papel é
    `motor` e o campo leva o lado junto.

    `sufixo_html` TROCA A ÚLTIMA CÉLULA INTEIRA, e existe para um caso só: o
    `Máx` do multiplicador, que deixou de ser texto e virou ESTADO (decisão 11
    dela, 03/09/2026 — ver :func:`_teto_do_multiplicador`). O `sufixo` de texto
    continua sendo o que as duas barras de motor querem, e ali `/255` é uma
    unidade, não um estado.
    """
    pct = round(100 * valor / teto, 1)
    endereco = (_endereco_de_pintura(papel, f' data-lado="{lado}"' if lado else "")
                if papel else "")

    campo = f"{papel}-{lado}" if lado else papel
    cauda = sufixo_html or f'<span class="teto">{sufixo}</span>'
    trilho = (_trilho_arrastavel(valor, teto, campo_trilho or f"{campo}-pct")
              if arrasta else
              f'<span class="trilho"><span class="cheio"'
              f' data-campo="{campo_trilho or f"{campo}-pct"}"'
              f' data-hef-alvo="largura" style="width:{pct}%"></span></span>')
    texto_do_num = VAZIO if vazio else f'{valor}{"%" if teto == TETO else ""}'
    return (f'<div class="motor{" mult" if arrasta else ""}'
            f'{"" if ligado else " off"}"{endereco}>'
            f'{botao or "<span></span>"}'
            f'{trilho}'
            f'<span class="num" data-campo="{campo_num or campo}">'
            f'{texto_do_num}</span>'
            f'{cauda}</div>')


def _barra_de_motor(valor, sigla, m, ligado, botao, vazio=False):
    """A linha de UM motor: interruptor · barra que arrasta · número · `%`.

    `vazio` é o lugar SEM CONTROLE, e ele troca só o TEXTO do número pelo
    travessão — a mesma regra do irmão :func:`_barra`, e a razão inteira está
    lá. O `<input>` continua com `value="0"` porque um `type=range` não guarda
    travessão; ele é `display:none` num lugar vazio, e o que a tela mostra é o
    `—` que a folha põe por cima (`.ctrl[data-conectado="nao"] .motor::after`).

    **É A METADE DE DESENHO QUE A ONDA1-D2 DEIXOU COM ENDEREÇO**, e a decisão é
    dela, de 04/09/2026, dita fora das três opções que eu ofereci:

        "os slcers do botão esquerdo e direito (forte e  # noqa-acento: citação dela
         fraco) se multiplicam (interagem com os botões economia, moderado,
         máximo, se eu tiver 150% do perfil de vibração e as duas linhas
         estiverem 100 entao a vibração dos 2 será 150%, mas se so a do motor
         fraco tiver 100 e a outrqa 50% então será 150 em um e 75% no outro
         entende?"

    `efetivo(motor) = degrau(coluna) x barra(motor)`, e a conta mora num lugar
    só, do lado do daemon (`gamepad._mults_por_motor`). Esta linha é o primeiro
    fator visível ao lado do segundo: os quatro degraus logo acima, a barra
    aqui.

    **O QUE A LINHA DEIXOU DE MOSTRAR, e onde ele foi parar.** Até 04/09 o
    número desta linha era o par `weak`/`strong` que o JOGO pediu, de 0 a 255 —
    LEITURA. Ele não cabe mais no mesmo pixel que o ajuste (duas escalas na
    mesma barra é a contradição que esta aba mais persegue), e não se perdeu:

    * o **punho que treme** no desenho já sai do mesmo dado (`treme-e`/`treme-d`,
      `_endereca_o_tremor`), e é ele que responde *"chegou força agora?"*;
    * o número exato vira o `title` DESTA linha, pintado pelo alvo `atributo`
      (`motor-{sigla}-pedido`) — e quando não há o que dizer o pintor **APAGA o
      atributo** (`hefesto_vivo.escrever`, ramo `atributo`), de modo que não
      sobra dica afirmando um pedido que ninguém mediu.

    **O `data-papel` VAI NO `<input>`, NUNCA NO `<div>` DE FORA** — a lição já
    paga pela linha "Personalizado": o ouvinte manda `valor: alvo.value ?? ''`,
    e um `<div>` não tem `value`, então o clique chegaria ao pacote sem
    quantidade nenhuma. O `data-lado` viaja junto no MESMO elemento, porque é
    ele que diz ao gesto qual das duas barras foi arrastada
    (`hefesto_vivo.manda_do_alvo`: `lado: d.lado || ''`).

    **O ENDEREÇO DE PINTURA É NOVO DE PROPÓSITO** (`barra-e`/`barra-e-pct`), e
    os velhos (`motor-e`, `motor-e-pct`) continuam sendo emitidos pelo pacote.
    É a PONTE DE PUBLICAÇÃO, e a razão é a mesma do `forca-pct`: a página que
    ela ABRE hoje ainda tem a linha de leitura, e publicar é ato dela. Reusar o
    nome velho para o significado novo faria o produto pintar um multiplicador
    dentro de uma barra de 0 a 255 — a mentira que esta aba mais persegue.

    `off` SEGUE A BARRA, e não o interruptor: com a barra em 0 aquele motor não
    treme neste perfil, e é o que o trilho apagado diz. O interruptor de punho
    continua sem fonte no produto (`app/telas/vibracao.SEM_FONTE['lado:ligado']`)
    e continua sendo desenho — mas agora o desenho não se contradiz, porque a
    cena põe os dois de acordo.
    """
    campo = f"barra-{sigla}"
    titulo = (f'Quanto da vibração chega a este punho — 0 a {TETO_DO_MOTOR}% do'
              f' degrau da coluna. Em 0, este motor fica mudo. Grava na hora, só'
              f' para este controle.')
    trilho = _trilho(valor, TETO_DO_MOTOR, PASSO_DO_MOTOR, campo, "motor",
                     titulo, extra=f' data-lado="{sigla}"')
    return (f'<div class="motor mult{"" if ligado else " off"}"'
            f' data-campo="motor-{sigla}-pedido" data-hef-alvo="atributo"'
            f' data-hef-atributo="title">'
            f'{botao}{trilho}'
            f'<span class="num" data-campo="{campo}-pct">'
            f'{VAZIO if vazio else valor}</span>'
            f'<span class="teto">%</span></div>')


def _linha_da_haptica(valor, ligado, vazio=False):
    """A linha «Sensor Háptico»: interruptor · trilho de 0 a 200 · número · `%` e a luz.

    Desde 02/10/2026 ela mora na faixa que era do Personalizado, logo abaixo da
    Força (A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01); o nome é o
    dela, «Sensor Háptico». A luz «no ar» é a bolinha depois do `%`, acesa pelo
    `haptica_no_ar` do `state_full`.

    O mesmo desenho das linhas dos motores, com gesto próprio (`haptica`,
    porque o teto é outro), e o mesmo par: o
    interruptor é a barra acima de zero (desligar grava 0, ligar devolve o
    padrão do dono), sem campo booleano à parte. O teto é lido do esquema
    (:data:`TETO_DA_HAPTICA`). Onde o Hefesto não está no caminho do controle
    (o Nativo pelo rádio sem a ponte), o pacote acende `fora` e a linha fica
    cinza — e o porquê fica no `?` do rótulo, e não na tela aberta.
    """
    botao = (f'<button class="haptica-lado lado{" on" if ligado else ""}" '
             f'data-gesto="haptica" '
             f'data-campo="lado-h" data-hef-alvo="classe" '
             f'data-hef-quando="1" '
             f'title="Háptica por áudio — a vibração fina que o jogo manda como som.">'
             f'{glifo(ESQ["glifo"], ativo=ligado, tam=18)}</button>')
    titulo = (f'A força da háptica por áudio neste controle — 0 a {TETO_DA_HAPTICA}%.'
              f' 100% é o jogo como ele mandou. Grava na hora, só para ele.')
    trilho = _trilho(valor, TETO_DA_HAPTICA, PASSO_DO_MOTOR, "barra-h", "haptica",
                     titulo)
    return (f'<div class="motor mult haptica"'
            f' data-campo="haptica-fora" data-hef-alvo="classe"'
            f' data-hef-classe="fora">'
            f'{botao}{trilho}'
            f'<span class="num" data-campo="barra-h-pct">'
            f'{VAZIO if vazio else valor}</span>'
            f'<span class="teto no-ar" data-campo="haptica-no-ar"'
            f' data-hef-alvo="classe"'
            f' title="Aceso: há háptica chegando a este controle agora.">%</span></div>')


def _teto_do_multiplicador(no_teto):
    """A célula do `Máx` — a palavra SEMPRE no HTML, acesa por classe."""
    return (f'<span class="teto mx{" on" if no_teto else ""}"'
            f' data-campo="mult-teto" data-hef-alvo="classe">Máx</span>')


LADOS = (("e", ESQ, "esq"), ("d", DIR, "dir"))


VAZIO = "—"


def _endereca_o_tremor(desenho, pref):
    """Dá endereço de pintura aos dois grupos de motor do SVG — 03/09/2026."""
    for sigla, m, _k in LADOS:
        ancora = f'id="{pref}-{m["id"]}"'
        if ancora not in desenho:
            raise SystemExit(
                f"ERRO em _endereca_o_tremor({pref!r}): o desenho não tem "
                f"{ancora} — o motor {sigla!r} sai do mapa "
                f"(docs/data/pecas-do-dualsense.csv, coluna `no_svg`), e sem a "
                f"âncora o punho que treme volta a ser o da cena, calado.")
        desenho = desenho.replace(
            ancora,
            f'{ancora} data-campo="treme-{sigla}"'
            f' data-hef-alvo="classe" data-hef-classe="acesa"', 1)
    return desenho


#     "eu mapeei as cores, glifos, controles, id e tudo mais. é pro projeto usar  # noqa-acento: citação literal dela
#      canto superior. é white no p1, mas a borda de tudo é cosmic red e os svgs  # noqa-acento: citação literal dela

FOLHA_DOS_28 = re.sub(r"</?style[^>]*>", "", monta_.folha_das_cores())

#: `monta.svg()` PREFIXA todo id por controle (`vb-p1-hachura-sem-hex`): uma
#: folha de página que diga `url(#hachura-sem-hex)` não acharia nada, e os doze
_ABRE_A_TINTA = '<defs id="cores-do-dualsense">'
if _ABRE_A_TINTA not in monta_.DS:
    raise SystemExit(
        "ERRO em aba05: o desenho não tem mais o `<defs id=\"cores-do-"
        "dualsense\">` — os doze modelos que pintam por `url(#…)` ficariam sem "
        "tinta na página.")
TINTA_DOS_28 = (
    monta_.DS[monta_.DS.index(_ABRE_A_TINTA):
              monta_.DS.index('<style id="cores-do-dualsense-folha">')]
    + "</defs>")

BLOCO_DA_TINTA = (
    f'          <svg width="0" height="0" aria-hidden="true"\n'
    f'               style="position:absolute;overflow:hidden">'
    f'{TINTA_DOS_28}</svg>\n')

ENDERECO_DA_COR = ('data-campo="colorway" data-hef-alvo="atributo"'
                   ' data-hef-atributo="data-colorway"')

_FOLHA_PODADA = re.compile(
    r'\s*<style id="[^"]*cores-do-dualsense-folha">.*?</style>', re.S)


def _endereca_a_cor(desenho, pref, cor, com_dono=True):
    """Dá ao `<svg>` o endereço da COR e tira dele a folha de um modelo só.

    `com_dono=False` é o LUGAR VAZIO da mesa, e ele sai daqui **sem**
    `data-colorway`. Não é economia: é a regra dela — campo sem informação não
    mostra nada. Um lugar sem controle não tem modelo, e afirmar "Galactic
    Purple" ali seria o desenho falando por um aparelho que não existe. Sem o
    atributo, nenhuma regra da folha casa e o desenho cai no cinza neutro, que é
    o que o `.ctrl[data-conectado="nao"]` já pinta por cima com `var(--linha)` — a tela não muda
    um pixel, e o arquivo deixa de afirmar o que não sabe.

    O ENDEREÇO FICA NOS QUATRO, inclusive nos vazios: no dia em que um terceiro
    controle entrar na mesa, o pintor tem onde escrever o modelo dele.

    RECUSA QUANDO A ÂNCORA SOME, pelas duas vias — `monta.troca` para o `<svg>`
    e a contagem para a folha. É a lição do `str.replace` que não casava: um
    endereço que não entra no HTML é uma pintura que não acontece, e ela é
    silenciosa dos dois lados.
    """
    quem = f"aba05 · _endereca_a_cor({pref!r})"
    desenho = monta_.troca(
        desenho, quem, f'<svg data-colorway="{cor}" ',
        f'<svg {ENDERECO_DA_COR} data-colorway="{cor}" ' if com_dono
        else f'<svg {ENDERECO_DA_COR} ')
    achadas = _FOLHA_PODADA.findall(desenho)
    if len(achadas) != 1:
        raise SystemExit(
            f"ERRO em {quem}: esperava UMA folha podada dentro do desenho e "
            f"achei {len(achadas)}. A página publica as 28 de uma vez; deixar "
            f"a podada aqui dentro devolveria a este controle uma cor só.")
    return _FOLHA_PODADA.sub("", desenho, count=1)


#: travessão, posto pela folha (`.ctrl[data-conectado="nao"] … ::after`).
#: botão acende de qualquer jeito, e uma chave real aqui seria o desenho
ESTADO_DO_LUGAR_VAZIO = {"forca": "", "pct": 0, "propria": False,  # (noqa-acento) chave
                         "esq": (False, 0), "dir": (False, 0), "hap": (False, 0)}


def _coluna(c, e=None, conectado=None):
    """Uma coluna da mesa: o desenho, o nome, a força, os dois motores, as ações.

    `e` é o estado daquela coluna. Sem ele vale a CENA do mockup
    (:data:`ESTADO`, chaveada pelo `pref`) para quem está na mesa, e o
    :data:`ESTADO_DO_LUGAR_VAZIO` para quem não está; com ele a coluna é montada
    com o que o daemon respondeu. O parâmetro existe para que a tela viva saia do
    MESMO gerador que a tela aprovada: um segundo emissor de HTML seria o segundo
    dono do desenho.

    **UMA FUNÇÃO SÓ PARA OS QUATRO LUGARES — 07/09/2026, e é cura de defeito
    MEDIDO com os quatro DualSense dela na mesa.** Havia um `_coluna_vazia()` à
    parte que devolvia um cartão **sem um único `data-campo` por dentro**:

        <div class="ctrl vazia" …><div class="seg"><span class="nada">—</span></div>…

    O daemon publicava os quatro controles, o pacote mandava as quatro colunas
    (`a05_vibracao` emite para os QUATRO lugares de propósito) e o piloto fazia
    `raiz.querySelectorAll('[data-campo="…"]')` dentro do bloco daquele
    `data-controle` (`hefesto_vivo._pintar`, passo 2). **Sem endereço, o dado
    dela chegava e não tinha onde pousar**: o P3 e o P4 continuavam dizendo
    `P3 • Desconectado` com travessão em tudo, com os aparelhos ligados.

    Medido na página publicada de 06/09, contando `data-campo` por
    `[data-controle="pN"]`: **P1 e P2 com 14 endereços distintos, P3 e P4 com
    UM** (o `colorway` do `<svg>`, que só existia por acidente do
    `_endereca_a_cor`).

    **A CAUSA DE FUNDO ERAM OS DOIS RAMOS**, e é por isso que a cura é fundi-los:
    o lugar cheio ganhou o degrau endereçado (03/09), o punho que treme (03/09),
    a cor do plástico (03/09) e as duas barras de motor (04/09) — e nenhuma
    dessas quatro passou pelo lugar vazio, porque ele era outro texto. **Um dos
    dois ramos envelheceu sem o outro**, quatro vezes em dois dias, sem uma
    linha de erro.

    `conectado` DECIDE DUAS COISAS, e só elas:

    a) **a marca do cartão** — `class="ctrl off"`, `data-conectado="nao"` e o
       `title`. São as MESMAS marcas que o piloto põe num lugar que esvazia ao
       vivo (`_pintar`, passo 1b) e TIRA quando o controle chega (passo 1c). É o
       que faz o lugar reabrir sozinho, sem regerar nada. A classe `vazia`
       morreu com esta fusão justamente por isso: **o piloto não a conhece**, e
       um cartão que nascesse com ela ficaria cinza para sempre, agora com o
       dado dela chegando por baixo.
    b) **o valor INICIAL de cada campo** — o travessão nos números, nenhum
       degrau aceso, nenhum punho tremendo e nenhum `data-colorway`. Quem some
       da tela são os WIDGETS, e quem os some é a folha
       (`.ctrl[data-conectado="nao"] .seg > *{{display:none}}` e os irmãos), que
       é a mesma cura de 05/09 para a coluna que perde o dono ao vivo. Nada de
       clicável sobrevive num lugar vazio: `display:none` não recebe clique.

    A ordem dela de 31/08/2026 continua inteira — *"Deixa os outros espaços dos
    4 controles a mostra ainda mas cinza igual vc fez na aba jogar."* A coluna
    continua na tela, com as sete linhas na mesma altura, o nome dizendo a
    POSIÇÃO e o ESTADO (nunca o do plástico) e o travessão no lugar do ajuste.
    O que mudou é que agora ela tem ONDE receber o controle que chega.
    """
    if conectado is None:
        conectado = c.get("conectado", True)
    e = e or (ESTADO[c["pref"]] if conectado else ESTADO_DO_LUGAR_VAZIO)
    plastico = cor_da_zona(c["cor"])
    acesos = tuple(m["id"] for m, k in ((ESQ, "esq"), (DIR, "dir")) if e[k][0])
    desenho = _endereca_a_cor(
        _endereca_o_tremor(
            svg(f'vb-{c["pref"]}', c["cor"], acesos=acesos, lampadas=False),
            f'vb-{c["pref"]}'),
        f'vb-{c["pref"]}', c["cor"], com_dono=conectado)

    # nome: `data-campo="degrau" data-hef-alvo="classe" data-hef-quando=<chave>`.
    # `data-hef-rotulo` esconderia justamente o dado que ele passou a mostrar.
    degraus = "".join(
        f'<button class="{"on" if e["propria"] and chave == e["forca"] else ""}" '  # noqa-acento: chave
        f'data-campo="degrau" data-hef-alvo="classe" data-hef-quando="{chave}" '
        f'data-papel="forca" data-forca="{chave}">{rot}</button>'
        for rot, chave in FORCA)

    linhas = []
    for sigla, m, k in LADOS:
        ligado, valor = e[k]
        # 03/09/2026. O que a régua lê aqui é o `<title>` do glifo, que é o NOME
        # troca: `data-hef="lado"` mais a classe `on` CRAVADA pelo desenho. As
        botao = (f'<button class="lado{" on" if ligado else ""}" '
                 f'data-gesto="lado" data-lado="{sigla}" '
                 f'data-campo="lado-{sigla}" data-hef-alvo="classe" '
                 f'data-hef-quando="1" '
                 f'title="{m["nome"]} — {m["nota"]}">'
                 f'{glifo(m["glifo"], ativo=ligado, tam=18)}</button>')
        linhas.append(_barra_de_motor(valor, sigla, m, ligado, botao,
                                      vazio=not conectado))

    # a cor do card em volta tem que ser branco"*. Ela era `style="--plastico:…"`
    # `var(--plastico)` nesta aba moram nela ou dentro dela — a borda da própria
    # O `style="--plastico:…"` SÓ VAI EM QUEM TEM APARELHO, e o par de
    # folha cai no `var(--plastico, …)` de sempre — e o alvo `plastico` do
    classe = "ctrl" if conectado else "ctrl off"
    marca = ("" if conectado else
             ' data-conectado="nao" title="Nenhum controle neste lugar."')
    tinta = f' style="--plastico:{plastico}"' if conectado else ""
    if conectado:
        rotulo = (f'P{c["jogador"]} <span class="pt">•</span> {c["nome"]}\n'
                  f'              <span class="pt">•</span> {c["via"]}</div>')
    else:
        rotulo = f'P{c["jogador"]} <span class="pt">•</span> Desconectado</div>'
    return f'''
          <div class="{classe}" data-controle="{c["pref"]}" data-uniq="{c.get("uniq", "")}"{marca}>
            <div class="moldura" data-hef="desenho" data-campo="plastico"
                 data-hef-alvo="plastico"{tinta}>{desenho}</div>
            <div class="rot-ctrl" data-hef="identidade">{rotulo}
            <div class="forca">
              <div class="seg" data-campo="degrau-herdado" data-hef-alvo="classe"
                   data-hef-classe="herdado">{degraus}</div>
              {_barra(e["pct"], TETO, "", papel="", campo_num="mult",
                      arrasta=True, campo_trilho="mult-pos",
                      sufixo_html=_teto_do_multiplicador(e["pct"] == TETO),
                      vazio=not conectado)}
            </div>
            {_linha_da_haptica(e["hap"][1], e["hap"][0], vazio=not conectado)}
            {linhas[0]}
            {linhas[1]}
            <div class="acoes-col">
              <!-- "Testar", não "Testar por 500 ms" — decisão dela, 30/08:
                   *"ali vai ser só Testar; se o user quiser parar vai clicar em Parar"*.
                   O par Testar/Parar já diz a duração pelo próprio par: quem começa
                   escolhe quando termina. E desde 07/09/2026 o gesto também não
                   tem duração: o Testar fica ligado até o Parar
                   (`a05_vibracao._EM_TESTE`). -->
              <!-- O texto dos dois é RÓTULO (categoria dela, 03/09/2026), e
                   este par foi decidido por ela justamente para NÃO mudar —
                   quem começa escolhe quando termina. O que estes botões fazem
                   é gesto, e o gesto tem dono no pacote da aba
                   (`interface/pacotes/a05_vibracao`, `testar` e `parar`).
                   O TESTAR ACENDE ENQUANTO O TESTE DAQUELA COLUNA ESTÁ LIGADO —
                   28/09/2026: o estado é `a05_vibracao.em_teste()`, pintado pelo
                   alvo `classe` (`em-teste`), com o `aria-pressed` junto para
                   quem não vê a cor. Como os degraus, ele não leva a marca de
                   rótulo: o que a régua mede aqui é o ESTADO. -->
              <!-- OS DOIS TESTES LADO A LADO — 02/10/2026, a resposta [24] dela:
                   *«ficam dois botões lado a Lado Vibração e Háptica»*. O
                   «Vibração» é o Testar de sempre; o «Háptica» toca a vibração
                   fina pelo som. Ligar um desliga o outro, e o «Parar» corta
                   os dois. -->
              <button class="btn" data-papel="testar" data-campo="em-teste"
                      data-hef-alvo="classe" data-hef-atributo="aria-pressed"
                      aria-pressed="false">Vibração</button>
              <button class="btn" data-papel="testar-haptica" data-campo="em-teste-h"
                      data-hef-alvo="classe" data-hef-atributo="aria-pressed"
                      aria-pressed="false">Háptica</button>
              <button class="btn vermelho" data-papel="parar"
                      data-hef-rotulo="o texto do botão">Parar</button>
            </div>
            {_marca.bloco("vibracao")}
          </div>'''


MIOLO = f'''
{BLOCO_DA_TINTA}
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Vibração</span>
        <!-- A DICA DO QUADRO ENCOLHEU DE 1000 PARA ~200 CARACTERES — 30/08/2026,
             regra dela: *"ao invés de estar tudo em [um só] deveria estar em cada
             seção"*, e vale *"em todas as abas"*.
             Ela tinha QUATRO parágrafos, e três deles nomeavam um campo que está
             na tela, a poucos pixels: a Força, os dois motores e o Testar. Cada um
             foi para o `?` do seu próprio rótulo. Aqui fica só o que nenhum campo
             diz — o que a aba É, e por que a fita do topo não vale nela. -->
        <span class="ajuda">?<span class="dica">
          O jogo pede uma vibração, e esta aba decide quanto dela chega a cada controle.<br><br>
          <b>Ajuste na coluna do controle</b>: a fita do topo não escolhe nada aqui.
        </span></span>
      </div>
      <div class="quadro-corpo">
        <div class="vib">

          <div class="rotulos">
            <!-- A LEGENDA VIROU DICA — 30/08/2026, pedido dela: *"'O lado que treme
                 acende em laranja; …' isso é tool tip"*. Mesma cura da Iluminação,
                 no mesmo dia, e pelo mesmo motivo: prosa cinza na coluna de rótulos
                 compete com os rótulos. O texto não muda uma palavra — ele explica
                 uma decisão medida (`D-O-SVG-VIBRA-POR-LADO`) e some seria perder. -->
            <div class="cel-des">
              <span class="sec-rot">Controle
                <span class="ajuda">?<span class="dica">
                  O lado que treme acende em <b>laranja</b>; o contorno na cor do
                  <b>plástico</b> diz de quem é o controle. Apagado é lado desligado.
                </span></span></span>
            </div>
            <!-- A LINHA DO MODELO GANHOU NOME — 30/08/2026, pedido dela:
                 *"a parte do Modelo tá faltando, tá o espaço vazio ali. a primeira
                 coluna serve como nome da linha"*. Esta célula existia vazia só para
                 ocupar a linha `--r-nome` da grade, e uma coluna cujo trabalho é
                 nomear linhas tinha uma linha sem nome. -->
            <div><span class="sec-rot">Modelo</span></div>
            <div><span class="sec-rot">Força da vibração
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica">
                Quanto da vibração que o jogo pede chega ao controle.<br><br>
                <b>Economia</b> 30% · <b>Balanceado</b> 100%, como o jogo pediu ·
                <b>Máximo</b> 150%, mais forte.<br><br>
                O trilho embaixo vai de 0 a {TETO}%, e o valor que vale é o dele:
                acende o maior degrau que ele alcança.<br><br>
                {DICA_DO_TETO_DA_MESA}<br><br>
                <!-- O MECANISMO DO AUTO MUDOU DE CASA — 05-Q4 dela, 06/09/2026.
                     Ele era a segunda metade de `a05_vibracao.FRASE_DA_MESA_EM_AUTO`,
                     de 331 caracteres, escrita para o CARTÃO — uma caixa que
                     CRESCE. A faixa embaixo da grade reserva UMA linha e corta o
                     resto (medido: 189 caracteres é o último que cabe), então a
                     frase ficou com o FATO e o CONSERTO e o porquê veio para cá,
                     que é onde há espaço para ele.

                     E O PORQUÊ SAIU DAQUI EM 11/09/2026 (A4-058, aprovado por
                     ela): ele JUSTIFICAVA a regra contra uma alternativa que
                     ninguém propôs. O fato — a escolha fica guardada e não
                     chega ao motor — é o que ela precisa, e é o que fica. -->
                Com a <b>força geral</b> em Auto, a escolha de cada coluna fica
                guardada e não chega ao motor.
              </span></span></span></div>
            <div><span class="sec-rot">Sensor Háptico
              <span class="ajuda">?<span class="dica">
                <b>A vibração fina</b> que o jogo manda como som, no cabo e no BT.<br><br>
                O risco no meio é 100%: o jogo como ele mandou. Acima disso ela
                fica mais forte; em 0, ela para. A bolinha verde acende quando
                ela está chegando ao controle.<br><br>
                Cinza quando o jogo fala direto com o controle, sem passar pelo
                Hefesto.
              </span></span></span></div>
            <div><span class="sec-rot">{ESQ["rot"]}
              <span class="ajuda">?<span class="dica">
                <!-- O PUNHO NO LUGAR DO NOME DA PEÇA — 11/09/2026, aprovado por ela.
                      O `nome`/`apelido`/`nota` do CSV continuam donos do `title`
                      do interruptor (`_coluna`) e do `mapa-do-controle`; aqui a
                      frase é a que ela leu e aprovou, e ela fala do PUNHO, que é
                      o que a mão procura. O registro do "não existe leve e forte
                      para cada" mora na `.nota` desta página, que é onde ele
                      deve morar. -->
                <b>Motor do punho esquerdo</b>: contrapeso maior, som grosso.<br><br>
                Desligue um lado e aquele punho para de tremer; o outro continua.<br><br>
                A barra ao lado é a força desse motor no teste <b>Vibração</b>.
              </span></span></span></div>
            <div><span class="sec-rot">{DIR["rot"]}
              <span class="ajuda">?<span class="dica">
                <b>Motor do punho direito</b>: contrapeso menor, som fino.
              </span></span></span></div>
            <!-- A DICA DESTE `?` ABRE PARA A DIREITA, e o número é medido — 06/09/2026.
                 Ela carregava `style="left:auto;right:22px"`, que é o arranjo das
                 dicas que moram do lado DIREITO da página (`.at-col:last-child` na
                 06, `.col-acao` na 09). Este `?` mora na PRIMEIRA coluna da grade,
                 a dos rótulos: com `right:22px` a caixa de 330 px nascia em x=146
                 numa janela que começa em x=370 — **224 px, dois terços dela,
                 fora da janela**, medidos no Chrome a 1920x1080.
                 Estava assim antes desta sprint e a página publicada ainda está:
                 com as duas orações do par a caixa tinha 72 px de altura e o corte
                 já comia o texto. A 05-Q2 dela põe a terceira frase aqui dentro,
                 e uma dica que não se lê não cumpre *"as duas na dica"*.
                 O padrão da casa (`.dica`, com `left:22px` no `topo.html`) abre para a
                 direita e cabe: x=505, fim em 835, dentro de 370..1550. -->
            <div><span class="sec-rot">Testar agora
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica">
                <!-- O MEIO SEGUNDO SAIU DA DICA EM 24/09/2026
                     (AS-FRASES-QUE-A-BANCADA-ACHOU-01). Ela prometia um pulso,
                     e o gesto deixou de ser pulso em 07/09, a pedido dela: o
                     `a05_vibracao.testar` fica ligado até o Parar, segue as
                     barras ao vivo, e o Testar de outra coluna encerra o
                     anterior (`_EM_TESTE`, um teste só). Medido no daemon de
                     mentira: nenhum `rumble.stop` sai sem o Parar. -->
                <b>Vibração</b> treme os motores deste controle até o <b>Parar</b>,
                seguindo ao vivo as barras da coluna. <b>Háptica</b> toca a vibração
                fina pelo som, com a força do <b>Sensor Háptico</b>. Ligar um desliga
                o outro, e testar outro controle encerra este. <b>Parar</b> corta os
                dois e devolve a vibração ao jogo.<br><br>
                <!-- A NOTA DOS VALORES QUE PASSAM VOLTOU PARA CÁ — 05-Q2 dela,
                     05/09/2026: *"As duas na dica."* Ela é a única frase desta
                     aba que explica um resultado que a PRÓPRIA TELA produz (por
                     que um "Testar" com 220 sai fraco quando o degrau está em
                     Economia), e por isso mora no `?` do "Testar agora", ao
                     lado das duas orações do par.

                     E ELA CONTINUA LIDA DO `gui/main.glade`, nunca redigitada
                     (`DICA_DOS_VALORES_QUE_PASSAM`) — essa metade da razão de
                     04/09 não caducou. Uma vez só na página: a régua 16 do
                     gerador conta. -->
                {DICA_DOS_VALORES_QUE_PASSAM}
              </span></span></span></div>
            <!-- O RÓTULO "Estado" SAIU EM 05/09/2026, com a faixa inteira —
                 ver `SEM_A_FAIXA_DE_ESTADO`. O `?` dele terminava confessando
                 *"Esta aba não trava — quem trava é a janela do Hefesto ou a
                 linha de comando"*, e era a medição inteira em uma frase. -->
          </div>
{"".join(_coluna(c) for c in MESA)}

        </div>
        <!-- A NOTA DO TESTAR SAIU DA TELA e voltou para o `?` do "Testar agora"
             — 05-Q2 dela, 05/09/2026: *"As duas na dica."* A linha permanente
             que morava aqui era decisão do PO atribuída a ela em 04/09; hoje
             ela respondeu a pergunta. A frase continua LIDA do
             `gui/main.glade`, que é a metade da razão que não caducou. A regra
             `.vib-nota` morreu junto, no `<style>` desta aba. -->
        <!-- A LINHA DO ESTADO — 02/09/2026. Ela existe na janela estável desde
             sempre e NÃO existia aqui: a tela nova tinha os dois motores, os
             quatro degraus e o "Testar", e nenhuma palavra sobre o que acontece
             com eles. As quatro frases já estavam escritas e ninguém as chamava
             (`app/actions/rumble_actions.py:127,291,370,459`).

             DEPOIS DA GRADE, e não dentro: as cinco colunas compartilham as
             alturas de linha, e uma linha a mais lá dentro empurraria o "Testar"
             de todas as colunas para fora do y das divisórias — que é a régua
             dela desde 30/08.

             O `id` É O ENDEREÇO DO BLOCO: o pintor troca o miolo inteiro por
             `p.blocos` (`hefesto_vivo.py:78`), porque o NÚMERO de linhas muda
             com o estado e não há endereço para uma linha que ainda não existe.
             Campo a campo, a linha que não se aplica viraria `—`. -->
        <!-- A FAIXA DEIXOU DE SER LUGAR DE RECADO — 13/09/2026,
             FRASES-E-DICAS-01. Ela declarava, por dois atributos, que o recado
             de SUCESSO desta página pousava aqui e com que classes (a 05-Q4
             dela, 06/09/2026). O piloto parou de pôr frase na tela: o sucesso
             na TELA-CALADA-01 (*"em todas as abas da interface"*), e a recusa
             nesta, pela caixa laranja da foto que está no índice da leva
             (`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`).
             Um endereço que ninguém lê é dado morto, e os dois saíram. A faixa
             continua sendo o lugar do ESTADO, e o que ela diz vem do bloco
             logo acima. -->
        <div class="vib-estado" id="vib-estado">{html_do_estado(textos_do_estado(CENA_DO_ESTADO))}</div>
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>O que você pediu, e está aqui</h2>
  <ul>
    <li><b>O trilho do Personalizado mora dentro da Força</b> (02/10), logo abaixo dos três degraus: o valor que vale é o do trilho, e acende o maior degrau que ele alcança (de 150% para cima, o Máximo). A faixa que era dele virou a <b>Sensor Háptico</b>, com a bolinha verde acesa quando a háptica está chegando ao controle; o <b>Testar agora</b> tem <b>Vibração</b>, <b>Háptica</b> e <b>Parar</b> numa linha só; e o desenho do controle voltou aos 124 px. A faixa entre os degraus (o Balanceado de 100 a 149, o Economia de 30 a 99) foi escolhida por delegação, e é sua para validar.</li>
    <li><b>Os quatro controles, um por coluna, sempre à vista</b> — na mesma ordem da fita do topo, cada um com a sua cor de plástico na borda do desenho.</li>
    <li><b>A força tem endereço, e o endereço é a coluna</b> — cada uma tem os seus quatro degraus e a sua barra. Como os quatro estão à vista, <b>a fita do topo não escolhe nada aqui</b> e nasce esmaecida (28/08). Também saiu o destaque que a coluna do P1 tinha: com a fita inerte, ele afirmaria na tela uma coisa que a fita já não faz.</li>
    <li><b>As cinco lâmpadas do jogador saíram do desenho</b> (28/08). Medidas neste navegador, nesta aba: <b>2,79 × 0,93 px</b> cada uma. Não é pouco contraste, é pouco pixel — menos de um pixel de altura não diz nada, aceso ou apagado. Quem diz o jogador aqui é o rótulo embaixo da coluna, que se lê. Elas continuam desenhadas na <b>Iluminação</b>, onde o controle é grande.</li>
    <li><b>Um bloco só</b> — as duas áreas viraram uma tabela do mesmo quadro.</li>
    <li><b>Motor esquerdo e direito são o que ATIVA o lado durante o jogo</b> — o interruptor de cada lado, e o desenho mostra qual punho treme.</li>
    <li><b>A barra de Força para em {TETO}%</b>, que é o Máximo — não passa dele.</li>
  </ul>

  <h2>O que passou a vir do mapa, e deixou de ser digitado</h2>
  <ul>
    <li><b>Os quatro controles</b> saem de <code>monta.MESA</code> — nome, jogador, plástico e transporte. A aba não sabe contar até quatro: ela percorre a lista.</li>
    <li><b>As cores</b> saem de <code>cor_da_zona()</code>, que lê o <code>&lt;style&gt;</code> gerado por <code>gerar_cores_do_dualsense.py</code> a partir de <code>docs/data/cores-do-dualsense.csv</code>. Não há um hexadecimal de plástico escrito nesta aba.</li>
    <li><b>Os dois motores</b> saem de <code>docs/data/pecas-do-dualsense.csv</code>: o id no desenho (<code>{ESQ["id"]}</code> e <code>{DIR["id"]}</code>), o glifo de cada um, o nome e a nota que vira dica.</li>
    <li><b>O padrão das lâmpadas</b> continua vindo do produto (<code>core/led_control.py</code>): P1 é a do meio e o P3 é <code>135</code> — não <code>234</code>, que era o que estava digitado no mockup. Ele não é desenhado nesta aba (elas saíram, por tamanho), e segue desenhado na Iluminação.</li>
  </ul>

  <h2>A sua dúvida sobre os motores, respondida</h2>
  <p style="margin:5px 0 10px">Você desconfiou certo do nome. <b>Não existe "leve" e "forte" para cada motor</b> — existem <b>dois motores</b>, um em cada punho, e cada um recebe <b>um</b> valor de 0 a 255. O da esquerda tem <b>contrapeso maior</b>, por isso soa grosso; o da direita, menor, soa fino. "Leve" e "forte" são apelidos dos <b>lados</b>.</p>
  <p style="margin:0 0 10px">Medido nesta casa, e está na canônica (<code>dualsense-referencia-canonica.md:303</code>): com o daemon parado, um <code>EV_FF</code> ligou o esquerdo e o report seguinte pediu <code>common[2]=200</code> (direito) e <code>common[3]=0</code> (esquerdo) — <b>o tremor trocou de lado</b>. Palavra sua, na medição: <i>"esquerda e senti que foi pra direita e lá morreu"</i>. São dois bytes independentes. No código do produto o par é <code>weak</code>/<code>strong</code> = direito/esquerdo.</p>

  <h2>Ainda aberto — precisa da sua palavra</h2>
  <ul>
    <li><b>A cor do lado que treme — e o rótulo que a contradizia.</b> Você decidiu "cor do plástico" (D-O-SVG-VIBRA-POR-LADO), e o rótulo da coluna prometia isso com estas palavras: <i>"acende na cor do plástico daquele controle"</i>. O que está desenhado é <b>laranja</b>, e a tela se contradizia sozinha. A frase passou a descrever o desenho, porque o laranja tem motivo medido: o contorno do controle <i>já é</i> a cor do plástico, então um traço de plástico sobre ele <b>apagaria</b> o lado em vez de mostrá-lo, e o laranja é o que diz o LADO de longe — a cor do plástico não distingue os dois punhos do mesmo controle. Quem diz de quem é o tremor é o contorno e a borda da moldura, que são o plástico.<br>
        <b>Se você quiser o contrário, é uma linha:</b> o traço vira <code>var(--plastico)</code> e a frase volta ao que era — mas então os dois lados acesos de um controle ficam da mesma cor do corpo dele, e o "qual punho treme" passa a depender só da espessura do traço.</li>
    <li><b>Respondida em 28/08, e por isso saiu daqui:</b> "com a fita em Todos, as quatro colunas mexem juntas?". Não há mais o que a fita mexa nesta aba — os quatro ficam lado a lado e cada coluna se ajusta sozinha. A fita esmaecida é a tela dizendo isso.</li>
    <li><b>O "Auto" mostra 70% no P3</b> porque a bateria dele está no meio. Esse número muda sozinho na tela enquanto joga, ou só quando você entra na aba?</li>
  </ul>
</div>

</body>
</html>
'''

CSS += _marca.CSS + """
  .vib .ctrl{position:relative}
  .vib .ctrl > .camada{position:absolute;top:-8px;left:18px;z-index:1;
    padding:0 5px;background:var(--panel);max-width:calc(100% - 30px)}
  .vib .ctrl > .camada::before{content:none}
"""


CSS_DAS_MEDIDAS = f"""
  .vib{{
    --larg-rot:{monta_.larg_rotulos('05-vibracao')}px;
    --gap-col:{monta_.GAP_DAS_COLUNAS}px;
  }}
"""

def _colunas_do_corpo(corpo):
    """O HTML de cada `[data-controle="pN"]`, na língua em que o PILOTO o lê."""
    import re as _re
    ate_a_faixa = corpo.split('class="vib-estado"', 1)[0]
    achados = {}
    for pedaco in ate_a_faixa.split('<div class="ctrl')[1:]:
        abre = pedaco.split(">", 1)[0]
        quem = _re.search(r'data-controle="(p\d+)"', abre)
        if quem:
            achados[quem.group(1)] = pedaco
    return achados


def _conferir(doc):
    """As decisões dela nesta aba, conferidas NA SAÍDA. Só o miolo, sem"""
    import re as _re
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = _re.sub(r"<!--.*?-->", "", corpo, flags=_re.S)
    corpo = _re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=_re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    vazios = [c for c in MESA if not c.get("conectado", True)]
    blocos = _colunas_do_corpo(corpo)
    #    `data-conectado="nao"`). A classe `vazia` morreu em 07/09/2026: o
    exigir(corpo.count('class="ctrl off"') == len(vazios),
           f"os lugares vazios marcados `ctrl off` não são {len(vazios)}")
    exigir(corpo.count('data-conectado="nao"') == len(vazios),
           f"os lugares vazios marcados `data-conectado=\"nao\"` não são "  # (noqa-acento) valor do atributo
           f"{len(vazios)}")
    exigir("ctrl vazia" not in corpo,
           "a classe `vazia` voltou ao cartão — o piloto tira a `off` e o "
           "`data-conectado`, e não conhece a `vazia`: o lugar ficaria cinza "
           "para sempre com o dado dela chegando por baixo")
    exigir(len(blocos) == len(MESA),
           f"a régua não achou as {len(MESA)} colunas: {sorted(blocos)}")
    #    O `data-colorway` E O `--plastico` ENTRARAM NESTA RÉGUA EM 07/09/2026,
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")
        bloco = blocos.get(c["pref"], "")
        exigir("data-colorway=" not in bloco,
               f"o lugar vazio {c['pref']} afirma um modelo de controle — o "
               f"ENDEREÇO da cor vai nos quatro, o VALOR só em quem tem "
               f"aparelho")
        exigir("--plastico:" not in bloco,
               f"o lugar vazio {c['pref']} afirma uma cor de plástico — mesma "
               f"regra do `data-colorway` logo acima")
    #    medido com os quatro DualSense dela na mesa. Até aqui ela proibia os
    for alvo in (".seg > *", ".motor > *", ".acoes-col > *"):
        exigir(f'.vib .ctrl[data-conectado="nao"] {alvo}' in doc,
               f"a folha deixou de esconder `{alvo}` num lugar sem controle — "
               f"os degraus, os trilhos e o `Testar` voltam a ficar clicáveis "
               f"para um aparelho que não está na mesa")
    exigir('.vib .ctrl[data-conectado="nao"]:not(' not in doc,
           "voltou uma exceção ao `[data-conectado=\"nao\"]` na folha desta "  # (noqa-acento) valor do atributo
           "aba — ela separa o lugar que NASCE vazio do que esvazia ao vivo, e "
           "duas caras para o mesmo estado na mesma tela é o que esta aba mais "
           "persegue")
    exigir(corpo.count('class="trilho arrasta"') == len(MESA) * (1 + len(LADOS) + 1),
           "os trilhos arrastáveis não são os mesmos nos quatro lugares")
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc, "o passo deixou de ser o dobro do ar")
    exigir("top:calc(var(--r-ar) * -1)" in doc or "top:-var(--r-ar)" in doc
           or "top: calc(var(--r-ar) * -1)" in doc,
           "a divisória saiu do meio do vão")
    exigir(".rotulos > *{align-items:flex-start;text-align:left}" in doc,
           "os rótulos voltaram a alinhar à direita")
    campos = set(_re.findall(r'data-campo="([^"]+)"', corpo))
    papeis = set(_re.findall(r'data-papel="([^"]+)"', corpo))
    exigir(not (campos & papeis),
           f"nome que é valor E clique ao mesmo tempo: {sorted(campos & papeis)} — "
           f"a pintura escreve o valor dentro do botão")
    for c in MESA:
        exigir(f'data-controle="{c["pref"]}"' in corpo,
               f'a coluna do {c["pref"]} não tem data-controle')
    exigir(corpo.count('data-controle="p') == len(MESA),
           f'as colunas endereçadas não são {len(MESA)}')
    exigir('id="vib-estado"' in corpo, "a faixa de estado sumiu da aba")
    cena = textos_do_estado(CENA_DO_ESTADO)
    exigir(cena == [],
           f"a cena do estado voltou a acender linha permanente: {cena} — a "
           f"decisão dela de 07/09/2026 é que, com a mesa quieta, não há texto "
           f"nenhum sob a grade")
    exigir('id="vib-estado"></div>' in corpo,
           "a faixa de estado não nasce vazia no desenho — com a mesa quieta "
           "ela não tem o que dizer, e o que estiver ali é prosa cravada")
    exigir(".vib-estado:empty{display:none}" in doc,
           "sumiu a regra que esconde a faixa vazia: sem ela a faixa vira uma "
           "tira de nada debaixo da grade")
    _com_pedidos = {"rumble_policy": "economia",
                    "rumble_ff": {"plays": 12, "nao_nulos": 12, "vpads": 1}}
    exigir(textos_do_estado(_com_pedidos) == [],
           f"a faixa voltou a falar sobre o que o JOGO pediu: "
           f"{textos_do_estado(_com_pedidos)} — ela saiu por ordem dela em "
           f"07/09/2026")
    for sigla, _m, _k in LADOS:
        exigir(corpo.count(f'data-campo="treme-{sigla}"') == len(MESA),
               f"o motor {sigla!r} não tem endereço em cada uma das "
               f"{len(MESA)} colunas — sem ele o tremor do controle que chegar "
               f"naquele lugar não tem onde pousar")
    exigir(corpo.count('data-hef-classe="acesa"') == len(LADOS) * len(MESA),
           "a classe do tremor não é a `acesa` do desenho compartilhado")
    for c in vazios:
        exigir(' acesa' not in blocos.get(c["pref"], ""),
               f"o lugar vazio {c['pref']} nasceu com um punho ACESO — o "
               f"endereço vai nos quatro, a classe só em quem tremeu de verdade")
    for frase, nome in ((DICA_DO_TETO_DA_MESA, "o teto da mesa"),
                        (DICA_DOS_VALORES_QUE_PASSAM, "os valores que passam pela intensidade")):
        exigir(frase in corpo, f"a dica perdeu a frase da janela estável: {nome}")
    sobrando = papeis - set(PAPEIS_QUE_SAO_GESTO)
    exigir(not sobrando,
           f"`data-papel` sem gesto que atenda: {sorted(sobrando)} — o ouvinte "
           f"do piloto lê todo `data-papel` como nome de gesto, e um nome que "
           f"nenhum pacote registra vira clique que não responde. Use "
           f"`data-hef` para endereço que é só pintura")

    #        `RUMBLE_CUSTOM_MULT_MAX` do esquema. Um `max` menor esconderia
    arrastaveis = _re.findall(r'<input class="trilho arrasta"[^>]*>', corpo)
    por_papel = {}
    for tag in arrastaveis:
        achado = _re.search(r'data-papel="([^"]+)"', tag)
        por_papel.setdefault(achado.group(1) if achado else "", []).append(tag)
    exigir(len(por_papel.get("intensidade", [])) == len(MESA),
           f"as barras 'Personalizado' arrastáveis não são {len(MESA)} "
           f"(achei {len(por_papel.get('intensidade', []))}) — a de cada lugar "
           f"tem de ser um `<input type=range>`, senão o clique dela chega "
           f"ao pacote sem número")
    for tag in por_papel.get("intensidade", []):
        exigir(f'max="{TETO}"' in tag,
               f"a barra arrastável não vai até {TETO}% — o teto é o "
               f"`RUMBLE_CUSTOM_MULT_MAX` do esquema, e é ele que recusa o que "
               f"passa dele")
        exigir(f'step="{PASSO}"' in tag,
               f"o passo do arraste não é {PASSO} — ele é o MDC dos degraus com "
               f"o teto, e é o que faz cada degrau ter uma parada em cima dele")
    da_haptica = por_papel.get("haptica", [])
    de_motor = por_papel.get("motor", [])
    exigir(len(da_haptica) == len(MESA),
           f"a barra da háptica por áudio não está nos {len(MESA)} lugares "
           f"(achei {len(da_haptica)})")
    for tag in da_haptica:
        exigir(f'max="{TETO_DA_HAPTICA}"' in tag and 'data-campo="barra-h"' in tag,
               f"a barra da háptica não para em {TETO_DA_HAPTICA}% ou perdeu o "
               f"endereço `barra-h` — o teto é o `HAPTICA_PCT_MAX` do esquema")
    exigir(len(de_motor) == len(LADOS) * len(MESA),
           f"as barras de motor arrastáveis não são {len(LADOS) * len(MESA)} "
           f"(achei {len(de_motor)}) — cada LUGAR tem UMA por punho, e é "
           f"o que fecha a `SEM_DONO['barra:motor']`")
    for sigla, _m, _k in LADOS:
        do_lado = [t for t in de_motor if f'data-lado="{sigla}"' in t]
        exigir(len(do_lado) == len(MESA),
               f"a barra do motor {sigla!r} não tem `data-lado` em cada um dos "
               f"{len(MESA)} lugares — sem ele o gesto não sabe qual das duas "
               f"foi arrastada")
        for tag in do_lado:
            exigir(f'data-campo="barra-{sigla}"' in tag,
                   f"a barra do motor {sigla!r} não usa o endereço novo "
                   f"`barra-{sigla}` — `motor-{sigla}-pct` é a LEITURA de 0 a "
                   f"255 da página publicada, e escrever nela um multiplicador "
                   f"põe o cursor no lugar errado")
    for tag in de_motor:
        exigir(f'max="{TETO_DO_MOTOR}"' in tag,
               f"a barra de motor não para em {TETO_DO_MOTOR}% — o teto é o "
               f"`MOTOR_PCT_MAX` do esquema, e passar dele daria à mesma peça "
               f"duas portas para o mesmo estouro")
        exigir(f'step="{PASSO_DO_MOTOR}"' in tag,
               f"o passo da barra de motor não é {PASSO_DO_MOTOR} — a borda "
               f"aceita todo inteiro de 0 a {TETO_DO_MOTOR}, e um passo maior "
               f"esconderia valores que o produto grava sem reclamar")
    for morto in ('data-campo="trava"', '<span class="sec-rot">Estado'):
        exigir(morto not in corpo,
               f"{morto!r} voltou à aba 05 — a faixa de estado saiu em "
               f"05/09/2026 por decisão dela: *'remove ela não faz sentido'*")
    exigir("--r-estado" not in doc,
           "`--r-estado` voltou à folha da aba 05 — a faixa cuja altura ele "
           "reservava saiu em 05/09/2026, e altura guardada para linha que não "
           "existe é rolagem paga por nada")
    exigir(doc.count("var(--r-motor) var(--r-motor) var(--r-motor) var(--r-acoes);") == 1,
           "a grade da aba 05 deixou de terminar no `--r-acoes` — a oitava "
           "faixa saiu em 05/09/2026 e a `grid-template-rows` foi junto")
    _apos_o_rotulo = corpo.split('<span class="sec-rot">Testar agora', 1)
    exigir(len(_apos_o_rotulo) == 2,
           'o rótulo "Testar agora" saiu da coluna de rótulos — sem ele não há '
           "onde a dica morar")
    _celula = _apos_o_rotulo[-1].split("</div>", 1)[0]
    _dica_do_testar = _celula.split('<span class="dica"', 1)[-1] if '<span class="dica"' in _celula else ""
    exigir(DICA_DOS_VALORES_QUE_PASSAM in _dica_do_testar,
           'a nota do Testar não está no `?` do "Testar agora" — a 05-Q2 dela é '
           '*"As duas na dica"*')
    exigir("left:auto" not in _celula,
           'a dica do "Testar agora" voltou a abrir para a ESQUERDA — na '
           "primeira coluna da grade isso joga 224 px dela para fora da janela")
    exigir(corpo.count(DICA_DOS_VALORES_QUE_PASSAM) == 1,
           "a nota do Testar aparece mais de uma vez na mesma tela")
    for _rot, chave in FORCA:
        degrau = round(RUMBLE_POLICY_MULT[chave] * 100)
        exigir(degrau % PASSO == 0 and degrau <= TETO,
               f"o degrau {chave!r} vale {degrau}% e a barra não para nele "
               f"(passo {PASSO}, teto {TETO}) — clicar o botão e arrastar a "
               f"barra deixariam de poder dizer o mesmo número")

    _faixa = corpo.split('class="vib-estado"', 1)[-1].split(">", 1)[0]
    exigir("data-hef-recado" not in _faixa,
           "a faixa voltou a declarar lugar de recado — o piloto não põe mais "
           "frase na tela, e um endereço que ninguém lê é dado morto")
    exigir(".vib-estado .est.recibo{color:var(--green)}" in doc
           and ".vib-estado .est.recibo .sinal{color:var(--green)}" in doc,
           "o tom `recibo` da faixa não é verde — e verde é a cor que esta "
           "casa usa para o que deu certo em todas as dez abas")
    exigir("--orange" not in doc.split(".vib-estado .est.recibo", 1)[-1]
           .split("}", 2)[0],
           "o recibo da faixa ficou laranja — laranja é o `alerta`, e alerta "
           "sobre um clique que gravou ensina que o botão falha")

    #     MEDIDO com os quatro DualSense dela na mesa: o daemon publicava os
    _marcas = _re.compile(
        r'data-campo="([^"]+)"'
        r'|data-hef-alvo="([^"]+)"'
        r'|data-hef-classe="([^"]+)"'
        r'|data-hef-quando="([^"]+)"'
        r'|data-hef-atributo="([^"]+)"')

    def _enderecos(html):
        achados = set()
        for grupo in _marcas.findall(html):
            achados.add(next(x for x in grupo if x))
        return achados

    if len(blocos) == len(MESA):
        _por_lugar = {pref: _enderecos(html) for pref, html in blocos.items()}
        _padrao = _por_lugar[MESA[0]["pref"]]
        for c in MESA[1:]:
            _dele = _por_lugar[c["pref"]]
            exigir(_dele == _padrao,
                   f"o lugar {c['pref']} não tem os mesmos endereços do "
                   f"{MESA[0]['pref']} — faltam {sorted(_padrao - _dele)} e "
                   f"sobram {sorted(_dele - _padrao)}. O piloto pinta dentro do "
                   f"bloco daquele `data-controle`: um endereço a menos é dado "
                   f"dela chegando sem ter onde pousar; um a mais é pintura que "
                   f"nunca acontece")
        exigir(len(_padrao) >= 14,
               f"a régua dos quatro lugares mede {len(_padrao)} endereços e "
               f"eram 14 em 06/09 — ela ficou verde por VACUIDADE, que é o "
               f"jeito de esta guarda deixar de guardar")

    if falhas:
        raise SystemExit("ERRO em 05-vibracao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


# .ctrl[data-conectado="nao"] .ds-svg rect:not([fill="none"])` (0,5,1) ganha de
# `.vazia` que saiu valia uma classe e o `[data-conectado="nao"]` que entrou

if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-05-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("05-vibracao", "Vibração", MIOLO,
              CSS + CSS_DAS_MEDIDAS + FOLHA_DOS_28,
              legenda=LEGENDA)
    _conferir(onde.pagina("05-vibracao.html").read_text())
    shutil.copyfile(_prova / "05-vibracao.html", _real / "05-vibracao.html")
    shutil.rmtree(_prova)
    print(f"05-vibracao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · motores do mapa: "
          f'{ESQ["id"]} / {DIR["id"]}')
