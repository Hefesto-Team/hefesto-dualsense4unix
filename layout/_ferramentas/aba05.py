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

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import (  # noqa: E402
    MESA, R, cor_da_zona, glifo, monta, svg,
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
        (x for x in (R / "docs/data/pecas-do-dualsense.csv").read_text().splitlines()
         if not x.startswith("#")))
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
if _COM_MULT != set(RUMBLE_POLICY_MULT):
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
  .vib{
    display:grid;grid-template-columns:132px repeat(4,1fr);gap:16px;
    --r-des:124px;--r-nome:17px;--r-forca:79px;--r-barra:26px;--r-motor:36px;
    --r-acoes:74px;--r-passo:10px;
  }
  .vib > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-forca) var(--r-barra)
                       var(--r-motor) var(--r-motor) var(--r-acoes);
  }
  /* a barra vertical entre blocos irmãos — pedido dela */
  .vib .ctrl{border-left:1px solid var(--border-sutil);padding:0 10px 0 14px}
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
  /* O RÓTULO OCUPA A ALTURA INTEIRA DA LINHA, e o texto fica centrado dentro
     dele. Não é enfeite: sem isto o rótulo da última linha acaba 29px acima dos
     botões que ele nomeia, e a régua lê — com razão — um vão entre as colunas.
     A cura é na ALTURA, que é a regra dela. */
  .vib .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  .sec-rot{font-size:11px;color:var(--comment);text-transform:uppercase;
           letter-spacing:.5px;display:flex;align-items:center;gap:6px}
  .vib .rotulos .legenda{font-size:10.5px;line-height:1.45;color:var(--comment);
                         text-transform:none;letter-spacing:0}
  /* A DICA NÃO É TÍTULO: sem isto ela herda o `text-transform:uppercase` do
     rótulo e o parágrafo inteiro sai em CAIXA ALTA — visto no navegador. E ela
     abre PARA CIMA: nas linhas de baixo da tabela, aberta para baixo, a janela
     (que tem `overflow:hidden`) cortava o fim do texto. */
  .vib .rotulos .dica{text-transform:none;letter-spacing:0;top:auto;bottom:-4px}
  .vib .rotulos .cel-des{justify-content:flex-start;gap:8px}

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
    border:1px solid var(--border-forte);background:var(--app-bg);color:var(--texto-mudo);
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

def _barra(valor, teto, sufixo, ligado=True, botao="", papel="forca", lado=""):
    """Uma linha de barra: interruptor · trilho · número · sufixo.

    `papel`/`lado` são o ENDEREÇO da linha, e sem eles a pintura só alcança as
    três barras de uma coluna por POSIÇÃO — que é o casamento que quebra em
    silêncio no dia em que alguém trocar duas linhas aqui.
    """
    pct = round(100 * valor / teto, 1)
    endereco = f' data-papel="{papel}"' + (f' data-lado="{lado}"' if lado else "")
    return (f'<div class="motor{"" if ligado else " off"}"{endereco}>'
            f'{botao or "<span></span>"}'
            f'<span class="trilho"><span class="cheio" style="width:{pct}%"></span></span>'
            f'<span class="num">{valor}{"%" if teto == TETO else ""}</span>'
            f'<span class="teto">{sufixo}</span></div>')


#: A tradução `lado da tela` → `lado do desenho`, num lugar só. `e`/`d` é a
#: língua dela (esquerdo/direito); `weak`/`strong` é contrato de código e mora
#: do lado do Python (`app/telas/vibracao.LADO_PARA_MOTOR`). Escrever
#: `weak`/`strong` no HTML seria a segunda verdade — e é a inversão que este
#: assunto convida, porque `weak` é o motor DIREITO.
LADOS = (("e", ESQ, "esq"), ("d", DIR, "dir"))


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
    return f'''
          <div class="ctrl" data-uniq="{c.get("uniq", "")}" style="--plastico:{plastico}">
            <div class="moldura" data-papel="desenho">{desenho}</div>
            <div class="rot-ctrl" data-papel="identidade">P{c["jogador"]} <span class="pt">•</span> {c["nome"]}
              <span class="pt">•</span> {c["via"]}</div>
            <div class="seg">{degraus}</div>
            {_barra(e["pct"], TETO, "Máx" if e["pct"] == TETO else "", papel="forca")}
            {linhas[0]}
            {linhas[1]}
            <div class="acoes-col">
              <button class="btn" data-papel="testar">Testar por 500 ms</button>
              <button class="btn vermelho" data-papel="parar">Parar</button>
            </div>
          </div>'''


MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Vibração</span>
        <span class="ajuda">?<span class="dica">
          O jogo pede uma vibração; a <b>Força</b> diz quanto dela chega ao controle.
          <b>Economia</b> 30% · <b>Balanceado</b> 100%, como o jogo pediu · <b>Máximo</b> 150%,
          mais forte do que ele pediu · <b>Auto</b>, o Hefesto escolhe pela bateria (100/70/30%)
          e nunca amplifica.<br><br>
          <b>Cada controle tem a sua força e os seus dois motores</b> — a coluna é a peça, e o
          que você mexe numa coluna vale só para aquele controle. Os quatro estão sempre à
          vista, lado a lado, então a fita do topo <b>não escolhe nada aqui</b>: ela fica
          esmaecida de propósito. O endereço do ajuste é a coluna, não a fita.<br><br>
          <b>Dentro do controle há dois motores, um em cada punho, e cada um recebe UM valor.</b>
          Não existe "leve" e "forte" para cada um: o da esquerda tem <b>contrapeso maior</b> e
          por isso soa grosso, o da direita tem contrapeso menor e soa fino. Medido nesta casa —
          <b>common[3]</b> é o esquerdo e <b>common[2]</b> o direito, dois bytes independentes.<br><br>
          <b>Testar por 500 ms</b> faz aquele controle tremer meio segundo com os valores das
          barras daquela coluna; <b>Parar</b> corta a vibração dele agora e devolve a mão ao jogo.
        </span></span>
      </div>
      <div class="quadro-corpo">
        <div class="vib">

          <div class="rotulos">
            <div class="cel-des">
              <span class="sec-rot">Controle</span>
              <span class="legenda">O lado que treme acende em laranja; o contorno na cor
                do plástico diz de quem é o controle. Apagado é lado desligado.</span>
            </div>
            <div></div>
            <div><span class="sec-rot">Força da vibração</span></div>
            <div><span class="sec-rot">Personalizado</span></div>
            <div><span class="sec-rot">{ESQ["rot"]}
              <span class="ajuda">?<span class="dica">
                <b>{ESQ["nome"]}</b> ({ESQ["apelido"]}). {ESQ["nota"]}<br><br>
                Desligue um lado e o jogo deixa de fazer aquele punho tremer — o outro
                continua. Serve para quem sente enjoo com o motor pesado, e para bancada.<br><br>
                A barra ao lado diz com que força esse motor entra no
                <b>Testar por 500 ms</b>, de 0 a 255.
              </span></span></span></div>
            <div><span class="sec-rot">{DIR["rot"]}
              <span class="ajuda">?<span class="dica">
                <b>{DIR["nome"]}</b> ({DIR["apelido"]}). {DIR["nota"]}
              </span></span></span></div>
            <div><span class="sec-rot">Testar agora</span></div>
          </div>
{"".join(_coluna(c) for c in MESA)}

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
n = monta("05-vibracao", "Vibração", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"05-vibracao: OK, {n} divs · {len(MESA)} controles · motores do mapa: "
      f'{ESQ["id"]} / {DIR["id"]}')
