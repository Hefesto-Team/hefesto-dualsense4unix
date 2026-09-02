"""Aba 05 · Vibração — a mesa de QUATRO controles.

Pedido dela, 27/08/2026: *"precisamos que cada aba dessa do nosso mockup seja
reescrita pra 4 controles conectados. (…) considerando o nosso mapa. e o sistema
de fitas. cada vez que o svg ou do controle ou de um glifo aparecerem tem que
considerar os do nosso mapa."*

Aqui isso quer dizer quatro coisas, e nenhuma é digitada:

* os quatro controles saem de `monta.MESA`, na mesma ordem dos chips da fita;
* a cor de cada plástico sai de `monta.cor_da_zona()`, que LÊ o `<style>` que o
  `gerar_cores_do_dualsense.py` escreveu no SVG;
* **os dois motores saem de `docs/data/pecas-do-dualsense.csv`** — o id no SVG
  (`no_svg`), o glifo (`glifo`), o nome e a nota de cada um. Digitar
  `feat-rumble-esquerdo` aqui seria a segunda verdade que o mapa existe para
  matar: quando a peça mudar de id, esta aba muda junto ou reprova alto.
* o número do jogador acende as cinco lâmpadas pelo padrão do produto
  (`monta.PADRAO_JOGADOR`, de `core/led_control.py`).
"""
import csv
import pathlib
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import onde  # noqa: E402
import monta as monta_  # noqa: E402
from monta import CONECTADOS, DADOS_DO_REPO  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import (  # noqa: E402
    MESA, cor_da_zona, glifo, monta, svg,
)

# O DONO ÚNICO DO DEGRAU DE FORÇA. O `monta` já põe `src/` no `sys.path` para
# ler o padrão das lâmpadas do produto; esta aba faz o mesmo com a tabela de
# multiplicadores, em vez de digitar `economia`/`balanceado`/`max` aqui e
# divergir no dia em que o produto renomear um.
from hefesto_dualsense4unix.daemon.subsystems.rumble import (  # noqa: E402
    RUMBLE_POLICY_MULT,
)

# ---------------------------------------------------------------------------
# OS DOIS MOTORES, LIDOS DO MAPA. A coluna `regiao` do CSV é quem diz quais
# peças são de vibração; o id no SVG é a coluna `no_svg`; o glifo é a coluna
# `glifo` — os mesmos 19 arquivos de `assets/glyphs/` que a aba Status usa.
# ---------------------------------------------------------------------------
_LINHAS = [
    l for l in csv.DictReader(
        x for x in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
         if not x.startswith("#"))
    if l["regiao"] == "vibracao"
]
if len(_LINHAS) != 2:
    raise SystemExit(f"ERRO: o mapa tem {len(_LINHAS)} peça(s) de vibração, e a aba "
                     f"desenha duas. Confira docs/data/pecas-do-dualsense.csv")

# "Motor de vibração esquerdo" -> "Motor esquerdo": o rótulo curto é DERIVADO do
# nome do mapa, e não uma segunda escrita dele.
MOTORES = [
    {
        "id": l["no_svg"],
        "glifo": l["glifo"],
        "rot": f'{l["nome"].split()[0]} {l["nome"].split()[-1]}',
        "nome": l["nome"],
        "nota": l["nota"],
        "apelido": l["apelidos"],
    }
    for l in sorted(_LINHAS, key=lambda l: float(l["x1"]))  # esquerdo antes do direito
]
ESQ, DIR = MOTORES

# ---------------------------------------------------------------------------
# O ESTADO DE CADA CONTROLE NA MESA. Um mockup mostra uma cena, e esta cena foi
# escolhida para ensinar: os quatro degraus de força aparecem uma vez cada, e os
# lados desligados são dois — um à esquerda (P4) e um à direita (P1) —, que é o
# que prova no desenho que o lado tem endereço.
#
# O P1 é o que ela aprovou em 27/08 ("ok, foda… Tá fechado essa"), com os mesmos
# números: Máximo, 150%, esquerdo desligado em 0, direito ligado em 60.
# ---------------------------------------------------------------------------
# OS QUATRO DEGRAUS: o RÓTULO é dela, a CHAVE é do produto.
#
# "Máximo" é texto de tela; `max` é contrato — está no perfil no disco
# (`profiles/schema.py`), no IPC (`rumble.policy_set`) e no `RUMBLE_POLICY_MULT`
# (`daemon/subsystems/rumble.py:82`). O `data-forca` do HTML carrega a CHAVE,
# nunca o rótulo: endereçar pelo rótulo quebra a pintura no dia em que ela
# renomear um degrau, e quebra calado.
#
# E A TABELA DO PRODUTO TEM TRÊS, NÃO QUATRO. Medido em 29/08/2026:
# `RUMBLE_POLICY_MULT` = {economia: 0.3, balanceado: 1.0, max: 1.5} — o **Auto**
# não está lá, e não é esquecimento: ele não tem multiplicador fixo, escala pela
# BATERIA em `core/rumble._effective_mult` (>50% → 1.0 · 20-50% → 0.7 · <20% →
# 0.3) e nunca amplifica. A `MIGRA-VIBRACAO-02` manda a régua exigir que os
# quatro sejam `set(RUMBLE_POLICY_MULT)`; são três mais um, e a régua desta aba
# mede assim.
FORCA = [("Economia", "economia"), ("Balanceado", "balanceado"),
         ("Máximo", "max"), ("Auto", "auto")]
#: O degrau sem multiplicador na tabela, e o motivo. Fica em dado, não em prosa.
FORCA_SEM_MULTIPLICADOR = "auto"

_COM_MULT = {chave for _, chave in FORCA} - {FORCA_SEM_MULTIPLICADOR}
if set(RUMBLE_POLICY_MULT) != _COM_MULT:
    raise SystemExit(
        f"ERRO: os degraus desta aba são {sorted(_COM_MULT)} e o produto tem "
        f"{sorted(RUMBLE_POLICY_MULT)} (daemon/subsystems/rumble.py). O "
        "`data-forca` é o endereço por onde a pintura acha o botão — divergir "
        "aqui faz a tela acender o degrau errado, em silêncio.")

TETO = 150  # a barra para no Máximo — "não passa dele", pedido dela

ESTADO = {
    "p1": {"forca": "max",        "pct": 150, "esq": (False, 0),   "dir": (True, 60)},
    "p2": {"forca": "balanceado", "pct": 100, "esq": (True, 120),  "dir": (True, 120)},
    "p3": {"forca": "auto",       "pct": 70,  "esq": (True, 90),   "dir": (True, 90)},
    "p4": {"forca": "economia",   "pct": 30,  "esq": (True, 40),   "dir": (False, 0)},
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
    --r-des:124px;--r-nome:17px;--r-forca:79px;--r-barra:26px;--r-motor:36px;
    --r-acoes:74px;
    --r-ar:5px;--r-passo:calc(var(--r-ar) * 2);
  }
  .vib > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-forca) var(--r-barra)
                       var(--r-motor) var(--r-motor) var(--r-acoes);
  }
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
  .vib .ctrl.vazia{border-color:var(--border-forte)}
  /* O TRAVESSÃO PREENCHE A CÉLULA, e isto é a régua de alinhamento falando.
     A coluna vazia tem a MESMA altura da viva (452px) e as mesmas sete linhas —
     medido. O que acabava 26px antes era o CONTEÚDO da última célula: dois
     botões empilhados preenchem os 74px de `--r-acoes`; um travessão centrado
     para no meio. A régua leu isso como "o conteúdo das colunas acaba em y
     diferentes", e leu certo.
     `height:100%` no marcador resolve sem mexer em altura nenhuma: ele passa a
     ocupar a célula e o texto continua centrado dentro dele. */
  .vib .ctrl.vazia .nada{display:flex;align-items:center;justify-content:center;height:100%;width:100%}
  .vib .ctrl.vazia .rot-ctrl,
  .vib .ctrl.vazia .nada{color:var(--linha)}
  .vib .ctrl.vazia .moldura{border-color:var(--border-forte)}
  .vib .ctrl.vazia .ds-svg .peca,
  .vib .ctrl.vazia .ds-svg .corpo,
  .vib .ctrl.vazia .ds-svg .miolo *{fill:var(--linha) !important}
  .vib .ctrl.vazia .ds-svg .corpo{stroke:var(--border-forte) !important}
  .vib .ctrl.vazia .ds-svg text{fill:var(--linha) !important}
  .vib .ctrl.vazia .ds-svg line{stroke:var(--linha) !important}
  .vib .ctrl.vazia .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                       stroke:var(--linha) !important}
  .vib .ctrl.vazia .ds-svg rect:not([fill="none"]),
  .vib .ctrl.vazia .ds-svg circle:not([fill="none"]),
  .vib .ctrl.vazia .ds-svg polygon:not([fill="none"]),
  .vib .ctrl.vazia .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .vib .ctrl.vazia .ds-svg rect,
  .vib .ctrl.vazia .ds-svg circle,
  .vib .ctrl.vazia .ds-svg polygon,
  .vib .ctrl.vazia .ds-svg ellipse{stroke:var(--border-forte) !important}
  /* O travessão fica ONDE o conteúdo ficaria — centrado na célula, para as sete
     linhas continuarem legíveis como linhas. */
  .vib .ctrl.vazia .seg,
  .vib .ctrl.vazia .nada-lin,
  .vib .ctrl.vazia .acoes-col{display:flex;align-items:center;justify-content:center}
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
     lado, sempre visíveis, e a fita do topo fica ESMAECIDA (`fita_viva=False`).
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
    border:1px solid var(--plastico);border-radius:8px;background:var(--app-bg);
    display:flex;align-items:center;justify-content:center;padding:5px;
  }
  /* ALTURA e não largura: a linha tem altura fixa e o desenho tem de caber nela.
     Com `width:100%` o SVG estouraria a linha e empurraria tudo. */
  .vib .moldura .ds-svg{height:100%;width:auto;max-width:100%}
  .rot-ctrl{font-size:11px;color:var(--texto-mudo);text-align:center;
            display:flex;align-items:center;justify-content:center}

  /* os quatro degraus de força, 2x2 e todos da MESMA largura */
  .vib .seg{display:grid;grid-template-columns:1fr 1fr;gap:7px}
  .vib .seg button{min-width:0;padding:0 8px;font-size:12px}

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
  /* o lado desligado não finge que tem força: o trilho fica apagado */
  .motor.off .cheio{background:var(--border-forte)}
  .motor.off .num{color:var(--comment)}

  /* o interruptor de cada lado: o GLIFO do mapa, aceso quando o lado está ligado */
  .lado{
    height:var(--h-escolha);width:36px;border-radius:7px;font-family:inherit;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--texto-mudo);
    cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;
  }
  .lado.on{border-color:var(--orange);background:rgba(255,184,108,.1);color:var(--orange)}
  .lado:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}

  /* os dois botões de ação, um sobre o outro e da MESMA largura */
  .acoes-col{display:grid;grid-template-columns:1fr;gap:6px}
  .acoes-col .btn{width:100%;justify-content:center;padding:0 6px;font-size:11.5px}

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
                             filter:drop-shadow(0 0 1.8px var(--plastico))}
"""

# ---------------------------------------------------------------------------
# AS CINCO LÂMPADAS DO JOGADOR SAEM DESTE DESENHO — decisão dela, 28/08/2026:
# elas somem dos desenhos pequenos e ficam nos grandes, da Iluminação.
#
# E o número que a sustenta foi medido AQUI, no Chrome, nesta aba: cada lâmpada
# tem **2,79 × 0,93 px**. Não é pouco contraste — é pouco PIXEL: um retângulo de
# menos de um pixel de altura não tem como dizer coisa nenhuma, aceso ou
# apagado. Quem diz o jogador nesta aba é o rótulo escrito embaixo da coluna
# (`P1 • Cosmic Red • USB`), que se lê.
#
# ELAS SAEM DO DESENHO, e não do CSS: `svg(..., lampadas=False)` arranca o
# `<g id="…-led-jogador">` inteiro. **Apagar não é tirar** — a regra
# `display:none` que morava aqui deixava as vinte lâmpadas no DOM, e quem herda
# um desenho com o grupo lá dentro volta a acendê-lo no dia em que precisar do
# número do jogador. Medido em 28/08: com a regra, 24 elementos de lâmpada nesta
# aba; sem o grupo, zero.
#
# A GUARDA DA ÂNCORA veio junto e ficou em UM lugar: `_tira_grupo()` reprova a
# geração quando o `<g>` some do desenho. Era uma checagem à mão em `_coluna()`,
# que é a mesma régua escrita duas vezes.
#
# O QUE NÃO SE PERDEU: o padrão que acende as lâmpadas continua sendo o do
# produto (`core/led_control.py::player_led_pattern` — P3 é `135`, e não o `234`
# que já esteve digitado no mockup). Ele não é desenhado aqui; segue desenhado
# na Iluminação, onde o controle é grande.
# ---------------------------------------------------------------------------

def _barra(valor, teto, sufixo, ligado=True, botao="", papel="forca", lado="",
           campo_num=""):
    """Uma linha de barra: interruptor · trilho · número · sufixo.

    `papel`/`lado` são o ENDEREÇO DO CLIQUE, e sem eles a pintura só alcança as
    três barras de uma coluna por POSIÇÃO — que é o casamento que quebra em
    silêncio no dia em que alguém trocar duas linhas aqui.

    `campo_num` é o ENDEREÇO DO NÚMERO quando ele NÃO PODE ser o nome do papel,
    e entrou em 02/09/2026. O pintor procura um valor por
    `[data-campo=X],[data-papel=X],[data-hef=X]` (`hefesto_vivo.py:183`): um
    nome que seja `data-papel` de um botão e `data-campo` de um número faz a
    pintura escrever o valor DENTRO do botão. Era o caso do `forca` — a linha
    do "Personalizado" tinha `data-papel="forca"` e `data-campo="forca"`, e os
    quatro degraus da coluna também são `data-papel="forca"`. Um tique escrevia
    `"balanceado"` em dez elementos e apagava a linha inteira.

    SÓ O NÚMERO TROCA DE NOME, e o trilho continua `forca-pct`. Não é descuido:
    o trilho nunca esteve em colisão — ele é um `<span>` filho, e o que o apagava
    era a pintura do PAI. Renomeá-lo junto seria mais bonito e custaria caro
    agora: o `casamento.py:66` mede contra a página PUBLICADA, e a publicação é
    ato DELA — um nome novo lá vira órfão até ela publicar. Quando a
    `05-vibracao` sair da `mockup/DIVERGENCIAS.md`, unificar o par em
    `mult`/`mult-pct` é uma linha aqui e uma no pacote.

    Quando não se diz nada, o número herda o nome do papel — que é o que as
    barras dos motores querem (`motor-e`, `motor-d`), porque ali o papel é
    `motor` e o campo leva o lado junto.
    """
    pct = round(100 * valor / teto, 1)
    endereco = f' data-papel="{papel}"' + (f' data-lado="{lado}"' if lado else "")

    #: O SEGUNDO ENDEREÇO, e ele não substitui o primeiro. Esta aba nasceu com
    #: `data-papel` + `data-lado`, que é um PAR — e o piloto `vibracao_viva.py`
    #: o usa. O piloto ÚNICO das dez endereça por `data-campo`, uma chave só,
    #: porque é o que as outras nove páginas trazem.
    #:
    #: Medido em 01/09/2026: a aba Vibração tinha 28 `data-papel` e TRÊS
    #: `data-campo` (os do cabeçalho, que são de todas). O pacote dela emitia
    #: dezesseis valores e nenhum tinha onde cair — zero casamentos, sem uma
    #: linha de erro. Os dois vocabulários convivem: um par para quem já o
    #: usava, uma chave para quem chegou depois.
    campo = f"{papel}-{lado}" if lado else papel
    return (f'<div class="motor{"" if ligado else " off"}"{endereco}>'
            f'{botao or "<span></span>"}'
            f'<span class="trilho"><span class="cheio" data-campo="{campo}-pct"'
            f' data-hef-alvo="largura" style="width:{pct}%"></span></span>'
            f'<span class="num" data-campo="{campo_num or campo}">'
            f'{valor}{"%" if teto == TETO else ""}</span>'
            f'<span class="teto">{sufixo}</span></div>')


#: A tradução `lado da tela` → `lado do desenho`, num lugar só. `e`/`d` é a
#: língua dela (esquerdo/direito); `weak`/`strong` é contrato de código e mora
#: do lado do Python (`app/telas/vibracao.LADO_PARA_MOTOR`). Escrever
#: `weak`/`strong` no HTML seria a segunda verdade — e é a inversão que este
#: assunto convida, porque `weak` é o motor DIREITO.
LADOS = (("e", ESQ, "esq"), ("d", DIR, "dir"))


#: O marcador de campo vazio — o mesmo travessão da Jogar, da Controles, da
#: Gatilhos e da Iluminação.
VAZIO = "—"


def _coluna_vazia(c):
    """O LUGAR de um controle que não está na mesa — ordem dela, 31/08/2026:

        "Todas as abas tem que ter só dois controles conectados no momento, o
         resto fica off." · "Deixa os outros espaços dos 4 controles a mostra
         ainda mas cinza igual vc fez na aba jogar."

    A COLUNA CONTINUA NA TELA, com as sete linhas na mesma altura — é isso que
    mantém as divisórias atravessando as cinco colunas no mesmo y. O que sai é o
    ESTADO: a força, os dois motores e as ações, porque nenhum deles tem controle
    para valer. Testar a vibração de um lugar vazio não é um botão fraco: é um
    botão que mente.

    O NOME DIZ A POSIÇÃO E O ESTADO, nunca o do plástico — a mesma decisão que
    ela tomou na Gatilhos e na Iluminação no mesmo dia.
    """
    j = c["jogador"]
    # O `data-controle` TAMBÉM AQUI, e pela mesma razão que na coluna viva: é
    # por ele que `hefesto_vivo.py:229` acha o lugar e o marca `conectado="nao"`.
    # Sem ele, o lugar vazio só é vazio porque o DESENHO o desenhou vazio.
    return f'''
          <div class="ctrl vazia" data-controle="{c["pref"]}" data-conectado="nao"
               title="Nenhum controle neste lugar.">
            <div class="moldura" data-papel="desenho">{svg(f'vb-{c["pref"]}', c["cor"], lampadas=False)}</div>
            <div class="rot-ctrl">P{j} <span class="pt">•</span> Desconectado</div>
            <div class="seg"><span class="nada">{VAZIO}</span></div>
            <div class="nada-lin"><span class="nada">{VAZIO}</span></div>
            <div class="nada-lin"><span class="nada">{VAZIO}</span></div>
            <div class="nada-lin"><span class="nada">{VAZIO}</span></div>
            <div class="acoes-col"><span class="nada">{VAZIO}</span></div>
          </div>'''


def _coluna(c, e=None):
    """Uma coluna da mesa: o desenho, o nome, a força, os dois motores, as ações.

    `e` é o estado daquela coluna. Sem ele vale a CENA do mockup
    (:data:`ESTADO`, chaveada pelo `pref`); com ele a coluna é montada com o que
    o daemon respondeu — que é como o piloto `vibracao_viva.py` a usa. O
    parâmetro existe para que a tela viva saia do MESMO gerador que a tela
    aprovada: um segundo emissor de HTML seria o segundo dono do desenho.
    """
    e = e or ESTADO[c["pref"]]
    plastico = cor_da_zona(c["cor"])
    acesos = tuple(m["id"] for m, k in ((ESQ, "esq"), (DIR, "dir")) if e[k][0])
    # `lampadas=False`: o grupo das cinco sai do desenho (ver o bloco das
    # lâmpadas, acima). Quem reprova quando a âncora some é o `_tira_grupo()`,
    # dentro do `svg()` — uma régua só, no lugar onde o corte acontece.
    desenho = svg(f'vb-{c["pref"]}', c["cor"], acesos=acesos, lampadas=False)

    degraus = "".join(
        f'<button class="{"on" if chave == e["forca"] else ""}" '
        f'data-papel="forca" data-forca="{chave}">{rot}</button>'
        for rot, chave in FORCA)

    linhas = []
    for sigla, m, k in LADOS:
        ligado, valor = e[k]
        botao = (f'<button class="lado{" on" if ligado else ""}" '
                 f'data-papel="lado" data-lado="{sigla}" '
                 f'title="{m["nome"]} — {m["nota"]}">'
                 f'{glifo(m["glifo"], ativo=ligado, tam=18)}</button>')
        linhas.append(_barra(valor, 255, "/255", ligado=ligado, botao=botao,
                             papel="motor", lado=sigla))

    # `data-uniq` VAZIO NA CENA ESTÁTICA, e não é descuido: o mockup não tem MAC
    # de verdade e não pode ter — `AA:BB:CC:DD:EE:FF` num arquivo é o que os dois
    # portões de anonimato existem para reprovar. Quem o preenche é a mesa viva.
    #
    # O `data-controle` ENTROU EM 02/09/2026, e é o que faltava para esta aba
    # existir como produto. Ele NÃO substitui o `data-uniq`: o `uniq` é o
    # endereço do APARELHO e nasce vazio aqui; o `pref` é o endereço da COLUNA e
    # é o que o pintor e o ouvinte de clique procuram. As três frentes que ele
    # destrava, medidas em 02/09 contra o daemon dela:
    #
    # 1. A PINTURA POR CONTROLE. `hefesto_vivo.py:240` faz
    #    `querySelectorAll('[data-controle="p1"]')` e pinta DENTRO. Sem o
    #    atributo, os doze valores por coluna — identidade, o multiplicador e os
    #    dois motores, nos dois controles — não tinham onde cair: a aba pintava
    #    13 valores, e os 13 eram do cabeçalho e da destruição dos degraus. A
    #    tela continuava mostrando `0 /255` e `60 /255` do desenho com o daemon
    #    dizendo `—`.
    # 2. O DONO DO CLIQUE. O ouvinte sobe com
    #    `closest('[data-controle],[data-uniq]')` (`hefesto_vivo.py:286`) e lê
    #    `dataset.controle || dataset.uniq`. Achava este `<div>` e lia `""`, de
    #    modo que "Testar" e "Parar" chegavam ao pacote sem controle nenhum e
    #    RECUSAVAM SEMPRE — para ela, com o rato de verdade. A régua unitária
    #    passava porque injeta o `uniq` à mão: verde sobre dois botões mortos.
    # 3. O LUGAR QUE ESVAZIA. `hefesto_vivo.py:229` marca os lugares sem
    #    controle por `[data-controle="pN"]`. Sem o atributo, um controle só na
    #    mesa deixava a coluna do P2 com os números do desenho — a sétima
    #    aparição do defeito que o pintor já sabia curar.
    return f'''
          <div class="ctrl" data-controle="{c["pref"]}" data-uniq="{c.get("uniq", "")}"
               style="--plastico:{plastico}">
            <div class="moldura" data-papel="desenho">{desenho}</div>
            <div class="rot-ctrl" data-papel="identidade">P{c["jogador"]} <span class="pt">•</span> {c["nome"]}
              <span class="pt">•</span> {c["via"]}</div>
            <div class="seg">{degraus}</div>
            {_barra(e["pct"], TETO, "Máx" if e["pct"] == TETO else "", papel="forca",
                    campo_num="mult")}
            {linhas[0]}
            {linhas[1]}
            <div class="acoes-col">
              <!-- "Testar", não "Testar por 500 ms" — decisão dela, 30/08:
                   *"ali vai ser só Testar; se o user quiser parar vai clicar em Parar"*.
                   O par Testar/Parar já diz a duração pelo próprio par: quem começa
                   escolhe quando termina. O meio segundo continua sendo o que o
                   gesto manda ao daemon; o que sai é a PROMESSA na tela. -->
              <button class="btn" data-papel="testar">Testar</button>
              <button class="btn vermelho" data-papel="parar">Parar</button>
            </div>
          </div>'''


MIOLO = f'''
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
          <b>O endereço do ajuste é a coluna, não a fita</b> — os quatro estão sempre à vista,
          então a fita do topo fica esmaecida de propósito.
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
                <b>Máximo</b> 150%, mais forte do que ele pediu · <b>Auto</b>, o Hefesto
                escolhe pela bateria (100/70/30%) e nunca amplifica.
              </span></span></span></div>
            <div><span class="sec-rot">Personalizado</span></div>
            <div><span class="sec-rot">{ESQ["rot"]}
              <span class="ajuda">?<span class="dica">
                <b>{ESQ["nome"]}</b> ({ESQ["apelido"]}). {ESQ["nota"]}<br><br>Cada punho tem UM motor e cada um recebe UM valor — não existe "leve" e "forte" para cada. O da esquerda tem <b>contrapeso maior</b> e soa grosso; o da direita, contrapeso menor, soa fino.<br><br>
                Desligue um lado e o jogo deixa de fazer aquele punho tremer — o outro
                continua. Serve para quem sente enjoo com o motor pesado, e para bancada.<br><br>
                A barra ao lado diz com que força esse motor entra no
                <b>Testar</b>, de 0 a 255.
              </span></span></span></div>
            <div><span class="sec-rot">{DIR["rot"]}
              <span class="ajuda">?<span class="dica">
                <b>{DIR["nome"]}</b> ({DIR["apelido"]}). {DIR["nota"]}
              </span></span></span></div>
            <div><span class="sec-rot">Testar agora
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica" style="left:auto;right:22px">
                <b>Testar</b> faz aquele controle tremer meio segundo com os valores das
                barras daquela coluna; <b>Parar</b> corta a vibração dele agora e devolve
                a mão ao jogo.
              </span></span></span></div>
          </div>
{"".join(_coluna(c) if c.get("conectado", True) else _coluna_vazia(c) for c in MESA)}

        </div>
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>O que você pediu, e está aqui</h2>
  <ul>
    <li><b>Os quatro controles da mesa, um por coluna, sempre à vista</b> — na mesma ordem da fita do topo, cada um com a sua cor de plástico na borda do desenho.</li>
    <li><b>A força tem endereço, e o endereço é a coluna</b> — cada uma tem os seus quatro degraus e a sua barra. Como os quatro estão à vista, <b>a fita do topo não escolhe nada aqui</b> e nasce esmaecida (28/08). Também saiu o destaque que a coluna do P1 tinha: com a fita inerte, ele afirmaria na tela uma coisa que a fita já não faz.</li>
    <li><b>As cinco lâmpadas do jogador saíram do desenho</b> (28/08). Medidas neste navegador, nesta aba: <b>2,79 × 0,93 px</b> cada uma. Não é pouco contraste, é pouco pixel — menos de um pixel de altura não diz nada, aceso ou apagado. Quem diz o jogador aqui é o rótulo embaixo da coluna, que se lê. Elas continuam desenhadas na <b>Iluminação</b>, onde o controle é grande.</li>
    <li><b>Um bloco só</b> — as duas áreas viraram uma tabela do mesmo quadro.</li>
    <li><b>Motor esquerdo e direito são o que ATIVA o lado durante o jogo</b> — o interruptor de cada lado, e o desenho mostra qual punho treme.</li>
    <li><b>A barra de Força para em {TETO}%</b>, que é o Máximo — não passa dele.</li>
  </ul>

  <h2>O que passou a vir do mapa, e deixou de ser digitado</h2>
  <ul>
    <li><b>Os quatro controles</b> saem de <code>monta.MESA</code> — nome, jogador, plástico e transporte. A aba não sabe contar até quatro: ela percorre a mesa.</li>
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

# `fita_viva=False` — decisão dela, 28/08/2026: em Gatilhos, Iluminação e
# Vibração os quatro ficam lado a lado, sempre visíveis, e a fita fica
# esmaecida. Ela não é o alvo destas três abas porque não há alvo: cada coluna
# se ajusta no seu lugar.
#: AS DUAS MEDIDAS DA PRIMEIRA COLUNA, injetadas do dono (`medidas.py`). Elas não
#: podem ser digitadas no bloco `CSS` acima porque ele é uma string crua — e um
#: número digitado ali seria a terceira cópia do mesmo valor, que é o defeito que
#: `medidas.py` nasceu para matar.
CSS_DAS_MEDIDAS = f"""
  .vib{{
    --larg-rot:{monta_.larg_rotulos('05-vibracao')}px;
    --gap-col:{monta_.GAP_DAS_COLUNAS}px;
  }}
"""

def _conferir(doc):
    """As decisões dela nesta aba, conferidas NA SAÍDA. Só o miolo, sem
    comentário HTML e sem o `<style>` — as três armadilhas que fizeram as réguas
    das outras abas reprovarem o que estava certo."""
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
    # 1. A MESA — dois conectados, dois lugares vazios.
    exigir(corpo.count('class="ctrl vazia"') == len(vazios),
           f"as colunas vazias não são {len(vazios)}")
    # 2. O LUGAR VAZIO DIZ A POSIÇÃO E O ESTADO, nunca o nome do plástico.
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")
    # 3. NENHUM AJUSTE VIVO NUM LUGAR VAZIO. Testar a vibração de um lugar vazio
    #    não é botão fraco: é botão que mente.
    for pedaco in corpo.split('class="ctrl vazia"')[1:]:
        bloco = pedaco.split('<div class="ctrl', 1)[0]
        for proibido in ('data-papel="forca"', 'data-papel="lado"',
                         'data-papel="testar"', 'data-papel="motor"'):
            exigir(proibido not in bloco, f"um lugar vazio tem ajuste vivo: {proibido!r}")
    # 4. O RESPIRO — a divisória no meio do vão, e o passo como o dobro do ar.
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc, "o passo deixou de ser o dobro do ar")
    exigir("top:calc(var(--r-ar) * -1)" in doc or "top:-var(--r-ar)" in doc
           or "top: calc(var(--r-ar) * -1)" in doc,
           "a divisória saiu do meio do vão")
    # 5. OS RÓTULOS ALINHAM À ESQUERDA — decisão dela de 31/08.
    exigir(".rotulos > *{align-items:flex-start;text-align:left}" in doc,
           "os rótulos voltaram a alinhar à direita")
    # 6. NENHUM NOME É VALOR E CLIQUE AO MESMO TEMPO — 02/09/2026.
    #    O pintor procura um valor por `[data-campo=X],[data-papel=X],
    #    [data-hef=X]` (`hefesto_vivo.py:183`) e o ouvinte de clique lê
    #    `data-papel` como o nome do gesto (`hefesto_vivo.py:288`). Um nome nos
    #    dois papéis faz a pintura escrever o valor DENTRO do botão. Aconteceu
    #    com `forca`, e a foto de 02/09 mostra os quatro degraus lendo
    #    "balanceado" e a linha do "Personalizado" apagada.
    campos = set(_re.findall(r'data-campo="([^"]+)"', corpo))
    papeis = set(_re.findall(r'data-papel="([^"]+)"', corpo))
    exigir(not (campos & papeis),
           f"nome que é valor E clique ao mesmo tempo: {sorted(campos & papeis)} — "
           f"a pintura escreve o valor dentro do botão")
    # 7. TODA COLUNA TEM ENDEREÇO DE COLUNA — 02/09/2026.
    #    Sem `data-controle`, o pintor não acha onde pôr os valores daquele
    #    controle e o ouvinte não sabe de quem foi o clique: "Testar" e "Parar"
    #    recusavam sempre.
    for c in MESA:
        exigir(f'data-controle="{c["pref"]}"' in corpo,
               f'a coluna do {c["pref"]} não tem data-controle')
    exigir(corpo.count('data-controle="p') == len(MESA),
           f'as colunas endereçadas não são {len(MESA)}')

    if falhas:
        raise SystemExit("ERRO em 05-vibracao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


n = monta("05-vibracao", "Vibração", MIOLO, CSS + CSS_DAS_MEDIDAS, fita_viva=False, legenda=LEGENDA)
_conferir(onde.pagina("05-vibracao.html").read_text())
print(f"05-vibracao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
      f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · motores do mapa: "
      f'{ESQ["id"]} / {DIR["id"]}')
