import sys, pathlib, csv, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde

# AS FAIXAS E OS PADRÕES SÃO DO PRODUTO, e a tela os LÊ. Digitá-los aqui foi
# como as duas dicas passaram a dizer 'De 1 a 10' — errado nas duas linhas.
# O QUE CADA BOTÃO FAZ, e a LISTA do que ele pode fazer, vêm do produto — não
# são digitados aqui. `core/acoes_de_botao` é o dono desde 01/09/2026, e ele
# deriva o padrão dos quatro mapas do daemon.
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    EIXO_DIREITO,
    EIXO_ESQUERDO,
    por_grupo,
)
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    rotulo as rotulo_da_acao,
)
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    padrao as _padrao_dos_botoes,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MAX,
    SCROLL_SPEED_MIN,
)
from monta import (monta, svg, glifo, CSS_GLIFO, CSS_POPUP, DADOS_DO_REPO, MESA, CONECTADOS,
                   cor_da_zona, player_slot_color, DS)

# ---------------------------------------------------------------------------
# O MAPA É O DONO. Pedido dela, 27/08/2026: "cada vez que o svg ou do controle
# ou de um glifo aparecerem tem que considerar os do nosso mapa".
#
# Desta aba saíram, por causa disso, TODOS os símbolos digitados: o dropdown de
# remapeamento dizia "Cross ✕", "Circle ○", "Square □", "Triangle △" e "D-pad ↑"
# com o caractere desenhado à mão, e a coluna de nome ao lado de cada glifo era
# um dicionário escrito aqui. Agora os dois saem de
# `docs/data/pecas-do-dualsense.csv` — o mesmo arquivo que nomeia os ids do SVG
# e que o portão `scripts/check_pecas_do_dualsense.py` mede.
# ---------------------------------------------------------------------------
PECAS = {p["id"]: p for p in csv.DictReader(
    [l for l in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
     if l and not l.startswith("#")])}


def gl_de(pid):
    """O arquivo de glifo daquela peça — coluna `glifo` do mapa, nunca o id."""
    g = PECAS[pid]["glifo"]
    if g == "-":
        raise SystemExit(f"ERRO: a peça '{pid}' não tem glifo em pecas-do-dualsense.csv")
    return g


def nome_de(pid):
    """O nome curto da peça, LIDO do mapa.

    `nome` quando ele já é curto (L1, Share, Options, PS, Touchpad, Cruz…) e o
    apelido curto quando não é — é de lá que saem o **L3** e o **R3**, que no
    mapa são apelido de "Analógico Esquerdo/Direito".

    O apelido tem de ser alfanumérico: os apelidos do Triângulo e do D-pad são
    os símbolos `△` e `↑`, que são exatamente o que esta rodada tirou da tela.
    """
    p = PECAS[pid]
    if len(p["nome"]) <= 8:
        return p["nome"]
    for a in p["apelidos"].split("|"):
        if a.isalnum() and len(a) <= 3:
            return a
    return p["nome"]


def dir_de(pid):
    """A direção do d-pad, do `nome` do mapa: "D-pad Cima" -> "cima"."""
    return PECAS[pid]["nome"].split()[-1].lower()


def _ids(regiao):
    """Os ids de uma região, NA ORDEM DO MAPA."""
    return [i for i, p in PECAS.items() if p["regiao"] == regiao]


def _alvo(pid):
    """Como a peça aparece numa lista de destino de remapeamento.

    O `tipo` do mapa é quem decide: `eixo` são DUAS entradas na mesma peça
    (a nota do CSV diz isso com todas as letras — "Clique e direção são duas
    entradas na mesma peça"), e `superficie` só pode receber o clique.
    """
    n = nome_de(pid)
    if PECAS[pid]["tipo"] == "eixo":
        return [f"{n} (clique)", f"{n} (direção)"]
    if PECAS[pid]["tipo"] == "superficie":
        return [f"{n} (clique)"]
    return [n]


# AS TRÊS REGIÕES DO TOUCHPAD saem da `nota` do mapa, e não de uma lista
# escrita aqui: é a única linha do projeto que as declara. Se a nota mudar de
# forma, esta linha PARA a geração em vez de deixar a tela mentir.
_m = re.search(r"Clique ([^.]+)\.", PECAS["touchpad"]["nota"])
if not _m:
    raise SystemExit("ERRO: a nota do touchpad não declara mais os cliques — "
                     "veja docs/data/pecas-do-dualsense.csv")
TOUCH_REGIOES = [f"clique {x.strip()}" for x in
                 _m.group(1).replace(" e ", ", ").split(",") if x.strip()]

# QUEM NAVEGA O PC, e não é escolha de desenho — é o que o produto faz.
# O poll loop lê o estado do controle PRIMÁRIO (`daemon/lifecycle.py:4541`), e
# é esse estado, e só ele, que vai para o mouse (`_dispatch_mouse_emulation`,
# :4744), para o teclado (:4754) e para o `hotkey_manager.observe` (:4757). Os
# secundários do co-op têm UM caminho só, o do gamepad virtual
# (`daemon/subsystems/coop.py:1871` — `forward_analog`/`forward_buttons`).
# Logo: com quatro na mesa, mouse, teclado e os cinco gestos saem de um
# controle só, o do jogador 1. A aba diz isso na cara em vez de esconder.
# QUEM NAVEGA SAI DOS CONECTADOS, não da MESA — 31/08/2026, quando a mesa passou
# a ter dois lugares vazios. Um controle desconectado não navega o PC, e o menor
# número da MESA podia ser justamente ele: a tela apontaria o cursor para um
# aparelho que não está aqui.
NAVEGA = min(c["jogador"] for c in CONECTADOS)
QUEM_NAVEGA = next((c for c in CONECTADOS if c["jogador"] == NAVEGA), None)
if QUEM_NAVEGA is None:
    # SEM ESTA LINHA o `next()` estourava com `StopIteration` cru, e quem lesse a
    # saída não tinha como saber o que aconteceu. Régua que quebra não diz o que
    # está errado — a lição do mesmo dia, na aba Controles.
    raise SystemExit(f"ERRO: o Player {NAVEGA} navega o PC e NÃO está na mesa. "
                     f"Quem navega sai de `CONECTADOS`, nunca de `MESA`.")


def _hex(rgb):
    """A cor canônica de lightbar do jogador, do produto (`led_control`)."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _tem_tinta(pid):
    """A peça tem superfície própria, ou o desenho dela é o glifo?

    O PS é `peca sem-tinta`: o círculo existe só para receber o ponteiro, e
    ela mandou tirá-lo da tela em 27/08 ("tem um círculo no PS de cada imagem,
    tem que excluir eles e deixar só o glifo lá"). Acender esse círculo o
    traria de volta em rosa — por isso o realce do PS vai no GLIFO.
    """
    m = re.search(rf'<g id="{pid}"[^>]*>(.*?)</g>', DS, re.S)
    return bool(m) and "sem-tinta" not in m.group(1)


CSS = CSS_GLIFO + """
  /* ---------- Navegação ----------
     A RODADA DOS QUATRO CONTROLES (27/08/2026). Ela: "precisamos que cada aba
     dessa do nosso mockup seja reescrita pra 4 controles conectados (…)
     considerando o nosso mapa. e o sistema de fitas."

     O que mudou aqui, e por quê:

     [1] A coluna do desenho deixou de ter UM controle e passou a ter A MESA —
     os quatro da `MESA` do `monta.py`, cada um na cor do seu plástico, com as
     cinco lâmpadas no padrão do jogador dele e a barra de luz na cor
     automática daquele número. Nenhum hex digitado: a cor do plástico vem de
     `cor_da_zona()` e a da luz de `core/led_control.player_slot_color`.

     [2] O desenho que ACENDE é o do Player 1, e só ele. Não é economia de
     desenho: é o que o produto faz (veja o comentário de `NAVEGA` acima).

     [3] Os símbolos desenhados à mão saíram. `✕ ○ □ △ ↑ ↓ ← →` eram texto no
     dropdown de remapeamento; agora as listas saem de
     `docs/data/pecas-do-dualsense.csv`.

     As correções anteriores dela, que continuam valendo:

     [56] "ativar mouse e emulação somem. aquela parte de roda dos pontos some
     também. nesse espaço era pra termos as opções de ativação que conversamos."

     [57] "todos os campos (coluna da direita das três tabelas ali, pra cada
     valor de cada linha) e arrumar a largura e disposição dos elementos."

     [51] "no navegação faltou usar os svgs que já usamos em status."
     ------------------------------------------------------------------- */

  /* ---- O `1fr` NÃO DIVIDE IGUAL, e foi assim que a divisória vertical do bloco
     de baixo ficou 8,3px fora da de cima (ela viu na tela, 27/08: "olha o
     alinhamento das barras verticais do bloco superior e inferior").
     Medido: `.ativacao` resolvia em `534,688px 551,312px` — o mínimo automático de
     um item de grid é `min-content`, e o campo "DOIS DEDOS" com `nowrap` empurrava
     a coluna direita. `minmax(0,1fr)` tira esse piso e as duas voltam a ser metade
     exata. Vale para as QUATRO grades de duas colunas desta aba.
     ---- o quadro dos gestos: a MESA à esquerda, os combos à direita, nas MESMAS
          duas colunas do quadro de baixo, para as três tabelas nascerem iguais */
  /* SEM `margin-bottom`: ele existia com 8px e deixava a moldura torta — 6px
     acima da tabela e 14px abaixo. Medido em 28/08; a moldura tem `padding:5px`
     dos dois lados, e o vão extra era só dele. */
  .gestos{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0;
          align-items:stretch}
  .gestos > .previa{padding-right:21px;display:flex}
  .gestos > .combos{border-left:1px solid var(--border-sutil);padding-left:20px}

  /* ---- A MESA DE QUATRO, na coluna que era de um controle só ----
     `stretch` + `justify-content:center`: as duas colunas do bloco terminam no
     MESMO y sem `space-between`, que é o que ela reprovou com todas as letras.
     A borda é a cor do plástico (P2 do redesenho — a borda diz QUAL peça é), e
     ela vem do desenho, não de uma classe por modelo. */
  .nav-mesa{flex:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
  .nav-ctl{display:flex;flex-direction:column;justify-content:center;gap:4px;
           border:2px solid var(--plastico,var(--border-forte));border-radius:8px;
           background:var(--app-bg);padding:6px 5px}

  /* ---------- O LUGAR VAZIO ----------
     A mesma gramática das outras cinco abas: cor explícita e NADA de `opacity`
     (a lição medida da `.fita.inerte`). A borda se declara INTEIRA aqui, e não
     só a cor: o `.nav-ctl` usa `var(--plastico)`, e uma `var()` sem valor
     invalida a declaração toda — a borda não fica cinza, ela deixa de existir.
     Medido na aba Controles no mesmo dia, com a foto mostrando dois lugares
     soltos, sem caixa nenhuma.
     OS DETALHES CLAROS DO DESENHO CAEM JUNTO — `text`, `line` e os `path` sem
     classe são os glifos L/R/PS, e eles só aparecem em desenho GRANDE: aqui ele
     tem 111px, contra os 62 da aba Jogar. O que muda com o TAMANHO tem de ser
     medido no tamanho em que é desenhado. */
  .nav-ctl.vazia{border:1px solid var(--border-forte);background:transparent}
  .nav-ctl.vazia .nav-rot,
  .nav-ctl.vazia .nav-est{color:var(--linha)}
  .nav-ctl.vazia .ds-svg .peca,
  .nav-ctl.vazia .ds-svg .corpo,
  .nav-ctl.vazia .ds-svg .miolo *{fill:var(--linha) !important}
  .nav-ctl.vazia .ds-svg .corpo{stroke:var(--border-forte) !important}
  .nav-ctl.vazia .ds-svg text{fill:var(--linha) !important}
  .nav-ctl.vazia .ds-svg line{stroke:var(--linha) !important}
  .nav-ctl.vazia .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                     stroke:var(--linha) !important}
  .nav-ctl.vazia .ds-svg rect:not([fill="none"]),
  .nav-ctl.vazia .ds-svg circle:not([fill="none"]),
  .nav-ctl.vazia .ds-svg polygon:not([fill="none"]),
  .nav-ctl.vazia .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  .nav-ctl.vazia .ds-svg rect,
  .nav-ctl.vazia .ds-svg circle,
  .nav-ctl.vazia .ds-svg polygon,
  .nav-ctl.vazia .ds-svg ellipse{stroke:var(--border-forte) !important}
  .nav-ctl .ds-svg{width:100%}
  /* a barra de luz acesa na cor automática do jogador. Sem esta regra o `--luz`
     que o `monta.svg()` escreve não pinta NADA: as duas tiras são `.peca`, e a
     regra neutra do esqueleto as deixa cinza. Era o caso desta aba até hoje. */
  .nav-ctl [id$="-lightbar"] .peca{fill:var(--luz)}
  /* AS CINCO LÂMPADAS DO JOGADOR NÃO EXISTEM NESTES CARTÕES — decisão dela,
     28/08: elas saem dos desenhos pequenos e ficam só nos grandes, da
     Iluminação. Aqui o desenho tem 111px e cada lâmpada media 1,90 × 0,64 px:  (noqa-acento: verbo medir, imperfeito)
     dois terços de um pixel de altura. Não havia contraste que resolvesse.
     NÃO HÁ REGRA DE COR PORQUE NÃO HÁ O QUE PINTAR: o grupo inteiro sai do SVG,
     por `svg(lampadas=False)`. Havia DUAS metades aqui, e tirar uma só não
     apagava nada — a classe `led-on` que o `monta.svg` funde estava no DOM e
     INERTE, e quem pintava era uma lista de ids montada por esta aba
     (`#p1-led-jogador-3{fill:var(--fg)}`). As duas saíram juntas.
     Quem diz o número do jogador aqui é o rótulo do cartão. */
  .nav-rot{font-size:10px;color:var(--texto-suave);text-align:center;white-space:nowrap;
           overflow:hidden;text-overflow:ellipsis}
  .nav-est{font-size:10px;color:var(--texto-mudo);text-align:center;white-space:nowrap;
           display:flex;align-items:center;justify-content:center;gap:5px;height:13px}
  /* O VERDE, E NÃO O LILÁS: nesta casa o interior lilás quer dizer "esta é a
     peça que a fita escolheu" (D-A-BORDA-E-A-IDENTIDADE-DA-PECA), e a fita aqui
     está apagada. O que este cartão diz é outra coisa — "é este que navega" —,
     e o verde de ligado é o mesmo do interruptor logo abaixo. */
  .nav-ctl.navega{background:rgba(80,250,123,.07)}
  .nav-ctl.navega .nav-rot{color:var(--fg);font-weight:600}
  .nav-ctl.navega .nav-est{color:var(--green)}
  .nav-est .bolinha{width:6px;height:6px;border-radius:50%;background:var(--green);flex:0 0 6px}

  /* o número ficou SÓ na linha da tabela: sobre o desenho ele era uma segunda
     legenda para o que a peça já diz ao acender (ela, 27/08). */
  .mk-n{display:inline-flex;align-items:center;justify-content:center;flex:0 0 17px;
        width:17px;height:17px;border-radius:50%;margin-right:6px;
        font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;
        border:1.5px solid var(--purple);color:var(--purple)}

  /* ---- as duas colunas de baixo. O `gap` saiu: com gap + padding-left o lado
          direito ficava 21px mais estreito que o esquerdo, e ela reprova 2px. */
""" + CSS_POPUP + """
  /* `.tn-vel` fica AQUI, e não no `CSS_POPUP` do `monta.py`: as duas
     velocidades são da Point-and-click e de mais nenhuma tela. O resto do
     bloco das pop-ups mudou-se para o montador em 29/08, quando a Conexões
     ganhou as duas dela — ver o comentário do `CSS_POPUP`. */
  .tn-vel{margin-top:9px;display:flex;flex-direction:column;gap:3px}

  /* os dois títulos ficam CADA UM sobre a sua coluna, no mesmo x delas.
     21px e não 20: a coluna da direita tem borda de 1px MAIS 20 de padding, e o
     título tem de começar onde o conteúdo dela começa. */
  /* `.sec-rot.sec-dupla` e não `.sec-dupla`: as duas regras tinham a MESMA
     especificidade e a do `.sec-rot` (display:flex) vem depois — os dois títulos
     ficavam colados um no outro, no canto esquerdo, e o da direita não ficava
     sobre a coluna dele. Estava assim desde que a tela dos botões nasceu. */
  .sec-rot.sec-dupla{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0}
  .sec-dupla > span{display:flex;align-items:center;gap:8px;min-width:0}
  .sec-dupla > span:last-child{padding-left:21px}
  /* `.duas-colunas` e `.col-nav` SAÍRAM daqui em 28/08: elas existiam só para a
     tela única que punha as duas tabelas lado a lado, e essa tela virou duas
     (uma tabela em cada). Ficaram sem um só elemento no HTML gerado. */
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
           margin-bottom:5px;display:flex;align-items:center;gap:8px;height:17px}
  .sec-rot .ajuda{text-transform:none;letter-spacing:0}
  /* O RESPIRO DO TÍTULO: `sec-alta` estava escrita no HTML desde 27/08 e não
     tinha uma linha de CSS — o título nascia colado no pé do bloco de cima.
     Ela: "desce mais um pouco o título pra separar ele do bloco". */
  .sec-alta{margin-top:16px}
  /* o bloco dos três botões não tem título: o vão que o título ocuparia vira
     margem, senão ele encosta no bloco das opções. */
  .moldura-acoes{margin-top:12px;padding:12px}
  .moldura-acoes .acoes{margin-top:0}
  /* o estado de 'valendo agora' viaja na própria linha da seção: como faixa
     própria ele custava 36px, e ela mede a altura da aba. */
  .sec-est{margin-left:auto;text-transform:none;letter-spacing:0;font-size:11.5px}
  .moldura{border:1px solid var(--border-sutil);border-radius:7px;background:var(--app-bg);
           padding:5px 12px}

  /* ---- AS OPÇÕES DE ATIVAÇÃO (fala [11]) ---- */
  .ativacao{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0}
  /* `gap:0`, e não os 5px de antes: a tabela do bloco de cima já empilha as
     linhas sem vão nenhum — o que as separa é a altura da própria linha. Dois
     blocos de linhas no MESMO quadro com passos diferentes é a cicatriz das
     quatro alturas de botão outra vez, e o vão de 5px é o que pagava os 10px
     que faltavam para as linhas caberem no token (veja `.at-linha`). */
  .at-col{display:flex;flex-direction:column;gap:0}

  /* O SEGUNDO QUADRO PAGA O PRÓPRIO CABEÇALHO — 30/08/2026.
     "As opções de ativação" era um `.sec-rot` de 17px dentro do quadro da
     Navegação; virando quadro próprio (pedido dela) ela ganhou `.quadro-topo`
     (28px), duas bordas e o padding de corpo — 26px a mais do que o miolo tem.
     Medido: o miolo pedia 570 num espaço de 544.
     O respiro sai de onde ele é folga e não leitura: o topo do segundo quadro e
     as duas pontas do corpo dele. Nenhuma linha de escolha encolhe — elas
     continuam nos 36px de `--h-escolha`, que é o alvo de clique. */
  .miolo > .quadro + .quadro > .quadro-topo{padding:6px 14px 0}
  .miolo > .quadro + .quadro > .quadro-corpo{padding:4px 14px 6px}
  .miolo > .quadro:first-child > .quadro-corpo{padding-bottom:6px}

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido dela, 30/08:
     *"as linhas divisórias em todas as páginas (…) a primeira coluna serve como
     nome da linha e a divisória entre eles tem que estar clara. pra todas as
     abas"*. Mesmo molde da Iluminação (`aba04.py`), com a razão escrita lá.
     A ÚLTIMA não leva: separador depois do último campo vira moldura, e a
     moldura do quadro já existe. */
  .at-col > .at-linha{border-bottom:1px solid var(--rot-linha)}
  .at-col > .at-linha:last-child{border-bottom:0}
  /* a `.tab` do quadro de cima, na MESMA janela, já separa as linhas dela
     assim desde sempre — as duas listas passam a ter a mesma cadência. */

  .at-col:first-child{padding-right:21px}
  .at-col:last-child{border-left:1px solid var(--border-sutil);padding-left:20px}
  /* ---------------------------------------------------------------------
     AS ALTURAS DESTA ABA PASSARAM A SER O TOKEN, e é medida, não gosto.
     Censo das dez abas em 28/08: TODA aba que tem `<select>` o desenha com
     36px — a Gatilhos (`select.modo`, `select.pronto`), a Conexões e a
     Perfis. A Navegação era a ÚNICA fora, e com DOIS valores ao mesmo
     tempo: `select.campo-linha` a 23px na coluna "O QUE FAZ" e
     `select.escolha-at` a 32px em "Função do teclado", lado a lado na
     mesma tela. Três alturas de lista numa janela é a cicatriz das quatro
     alturas de botão, que é a razão de o token existir.
     `.at-linha`, `.tog` e `.campo-num` acompanham: uma lista de 36px numa
     linha de 32px transborda, e um campo de 32px ao lado de uma lista de 36
     recria a divergência do outro lado da mesma linha.
     --------------------------------------------------------------------- */
  /* o rótulo da opção é verde e alinha à direita, como nas outras nove */
  .at-linha > span:first-child{color:var(--rot-campo);font-weight:600;text-align:right}
  .at-linha{display:grid;grid-template-columns:190px minmax(0,1fr);align-items:center;gap:12px;height:var(--h-escolha)}
  /* AS DUAS COLUNAS DO BLOCO VIRAM PROPORÇÃO, E NÃO PIXEL — 31/08/2026.
     Mesma família da cura da Controles (`aba02.py`, 31/08): com a coluna do
     rótulo em PIXEL FIXO, todo o encolhimento da janela caía na única coluna
     flexível — a do campo.

     A conta que condena o `190px`: o maior rótulo desta lista ("Velocidade de
     cursor", "Navegação Interna") pede 84px de `min-content`; com o `?` e o vão
     dele são 107. Os outros 83px eram folga MORTA, e ela não encolhia nem
     quando a vizinha pintava fora da janela.

     Do outro lado, o campo `[Dois dedos − 4 +][Analógico − 1 +]` pedia 328,3px
     e recebia 320 na janela de 1180 — 8,3px pintados FORA da coluna, por cima
     do vão da moldura. Não era caso de canto: era a tela do produto. A régua
     que só olha a borda da `.janela` dava VERDE (o campo ainda estava dentro
     dela), mas o olho via o campo da "Velocidade da rolagem" mais comprido que
     o da "Velocidade de cursor" logo acima e o do "Modo Steam" logo abaixo.
     Abaixo de 1136px de janela os mesmos 8,3px viravam vazamento de verdade —
     67,3px fora da janela num navegador de 1000px.

     186/324 e não 190/320: os 4px que o rótulo devolve são o que faltava para o
     campo caber inteiro na coluna com folga, e as três alturas de campo desta
     coluna passam a terminar no MESMO x (1133). `minmax(0,…)` é obrigatório —
     `Nfr` sozinho tem mínimo automático `min-content`, que é exatamente o piso
     que fazia as faixas se recusarem a encolher.

     A LISTA DA POP-UP FICA NO PIXEL, de propósito: a `.tn-cx` é uma caixa de
     660px que não encolhe com a janela, e lá a coluna do campo já sobra (420
     para 316 de conteúdo). Proporção numa caixa fixa só engordaria o rótulo
     para 222px sem curar nada. */
  .at-col > .at-linha{grid-template-columns:minmax(0,186fr) minmax(0,324fr)}
  /* a linha que hospeda um botão de AÇÃO cresce para os 34px do token */
  .at-linha:has(.btn){height:var(--h-acao)}
  .at-rot{font-size:11.5px;color:var(--texto-suave);display:flex;align-items:center;gap:6px}
  .at-rot .ajuda{margin-left:auto}
  /* na coluna da direita a dica abre para a esquerda: 22px + 330px de largura
     a partir de x=1154 passava da borda da janela de 1180px */
  .at-col:last-child .dica{left:auto;right:22px}
  .escolha-at{width:100%;height:var(--h-escolha);border-radius:7px;font-size:12px;
    font-family:inherit;padding:0 10px;border:1px solid var(--border-forte);
    background:var(--app-bg);color:var(--fg);cursor:pointer}
  .escolha-at:hover{border-color:var(--purple)}
  .escolha-at.viva{border-color:var(--purple);background:var(--sel-bg);font-weight:600}

  /* os "seletores tipo bignumbers" que ela pediu para a velocidade de cursor */
  .campo-num{display:flex;align-items:center;height:var(--h-escolha);padding:0 11px;
             border:1px solid var(--border-forte);border-radius:7px;background:var(--app-bg)}
  /* cada par (rótulo + número) anda junto, e o ÚLTIMO número encosta na borda
     direita do campo — o rótulo dele fica onde está. Sem isso a "Velocidade da
     rolagem", que tem um par só, acabava 86px antes da vizinha de cima e a
     caixa parecia inacabada; empurrar o par INTEIRO só trocava o buraco de
     lado. */
  /* `min-width:0` no par, e é a REDE: sem ele o mínimo automático de um item de
     flex é o `min-content` dele, e o campo inteiro se recusava a encolher —
     era assim que ele saía pela borda da janela em vez de apertar o que dá para
     apertar. Abaixo de ~1090px de janela nenhuma proporção salva, e a escolha
     passa a ser entre um rótulo encurtado DENTRO da janela e um campo inteiro
     pintado FORA dela. Na janela do produto (1180) nada é cortado — medido. */
  .campo-num .par{display:flex;align-items:center;gap:9px;flex:0 1 auto;min-width:0}
  .campo-num .par:last-child{flex:1 1 auto}
  /* O `margin-left:auto` SÓ VALE QUANDO HÁ UM PAR ANTES — 01/09/2026. Ele
     existe para empurrar o SEGUNDO número até a borda direita do campo, e com
     dois pares fazia exatamente isso. Quando as duas linhas passaram a ter UM
     número só (decisão dela), o par único é `:last-child` **e** `:first-child`,
     e a mesma regra jogava o `− 6 +` para a direita deixando o campo vazio à
     esquerda — um campo que parece quebrado, ao lado de listas que começam
     coladas na borda. O `:not(:first-child)` é a diferença entre "empurra o
     segundo" e "empurra o único". */
  .campo-num .par:not(:first-child):last-child .bignum{margin-left:auto}
  /* O `letter-spacing` SAIU, e ele era órfão: existia para abrir a CAIXA ALTA,
     que saiu daqui em 31/08 (`f7c6c199`) junto com a das outras. O comentário
     daquela cura, quatro telas acima neste mesmo arquivo, já dizia "o
     `letter-spacing` sai junto" — só que a regra foi aplicada no `.sec-rot` e
     esquecida NESTE seletor. Meia cura deixa as duas versões vivas, que é o
     defeito que a regra da casa existe para matar. Custava 7,6px de largura no
     campo mais apertado da aba ("Dois dedos" + "Analógico" = 19 caracteres).
     O `overflow:hidden` faz dois trabalhos: corta com reticências quando não há
     mesmo espaço, e zera o mínimo automático deste item de flex — sem ele o
     `min-width:0` do par não bastaria. */
  .campo-num .sub{font-size:10.5px;color:var(--comment);white-space:nowrap;
                  overflow:hidden;text-overflow:ellipsis}
  .campo-num .risco{width:1px;height:18px;background:var(--border-forte);margin:0 4px 0 5px}
  /* `flex:none` na trinca: quando o campo aperta, quem cede é o RÓTULO, nunca o
     `− N +`. Sem isso os botões de 22px encolheriam até o tamanho do sinal
     dentro deles, e o alvo de clique é a única coisa desta caixa que não pode
     encolher. */
  .bignum{display:inline-flex;align-items:center;flex:none}
  /* 22px, o mesmo dos dois botões ao lado: a trinca `− N +` vira três células
     iguais. 26 era folga sobre folga — o valor vai de 1 a 10, e "10" mede
     18,02px nesta fonte (JetBrains Mono 15px/600), logo cabe nos 22 com 2px de
     cada lado. Os 4px por `.bignum` são 8px no campo, e são eles que deixam a
     "Velocidade da rolagem" caber na coluna em vez de pintar fora dela. */
  .bignum b{font-family:'JetBrains Mono',monospace;font-size:15px;color:var(--fg);
            font-weight:600;min-width:22px;text-align:center}
  .passo{width:22px;height:24px;border:1px solid var(--border-forte);border-radius:5px;
         background:transparent;color:var(--texto-mudo);font-size:14px;font-family:inherit;
         cursor:pointer;line-height:1;padding:0}
  .passo:hover{border-color:var(--purple);color:var(--purple)}

  /* ---- as TRÊS tabelas: mesma largura de bloco, mesma coluna de valor,
          cabeçalho em roxo (fala [90]) — inclusive a dos gestos ---- */
  .tab{width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed}
  /* O CABEÇALHO DA TABELA DE GESTOS É BRANCO E NEGRITO — decisão dela,
     31/08/2026: *"Combinação no controle / O que faz: tira do verde, deixa
     branco e negrito."*
     Ele era `--rot-campo` (o verde que nomeia CAMPO nesta janela), e não é isso
     que ele é: campo é o que se ajusta, e estas duas são as COLUNAS de uma
     tabela — cabeçalho, não rótulo de campo. Pintá-lo de verde dava a duas
     palavras que não se clicam a mesma cor das que se clicam. */
  .tab th{color:var(--fg);font-weight:700;text-align:left;font-size:10px;
          padding:0 8px 4px 0;
          border-bottom:1px solid var(--border-forte)}
  /* a linha da tabela é o token + o fio de 1px que separa duas linhas, e mais
     nada. O `padding:1px 0` que havia aqui somava 2px por linha em cima de uma
     altura já declarada — 10px nas cinco, que é metade do que faltou para o
     quadro fechar dentro do miolo. */
  .tab td{padding:0 8px 0 0;height:var(--h-escolha);color:var(--texto-suave);
          border-bottom:1px solid var(--border-sutil);vertical-align:middle}
  .tab tr:last-child td{border-bottom:none}
  .tab th:first-child,.tab td.b{width:176px}
  .tab td.b{white-space:nowrap;overflow:hidden}
  .tab tr.disputa td.b{color:var(--orange)}
  .tab tr.g:hover td{background:rgba(189,147,249,.07)}
  .campo-linha{width:100%;height:var(--h-escolha);border-radius:6px;font-size:11.5px;font-family:inherit;
    padding:0 8px;border:1px solid var(--border-forte);background:var(--panel);
    color:var(--fg);cursor:pointer}
  .campo-linha:hover{border-color:var(--purple)}
  .disputa .campo-linha{border-color:var(--orange);color:var(--orange)}
  .nm{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-suave);margin-left:3px}
  .rot-gl{font-size:10.5px;color:var(--comment);margin-left:3px}

  /* ---- os grupos de botão: mesma largura, ocupando o bloco inteiro ---- */
  .acoes{display:grid;gap:var(--gap);margin-top:9px}
  .acoes a.btn{text-decoration:none}
  .acoes.dois{grid-template-columns:1fr 1fr}
  .acoes.tres{grid-template-columns:1fr 1fr 1fr}
  /* quatro botões na fileira de 1086px dão 261,8px cada. Coube — mas só depois
     de "Configurar o estilo Point-and-click" virar "Estilo Point-and-click":
     com o rótulo longo o texto QUEBRAVA em duas linhas dentro de uma caixa de
     34px de altura fixa, medido em 28/08. */
  .acoes.quatro{grid-template-columns:repeat(4,1fr)}
  .grupo-padrao{position:relative}
  /* a confirmação do "Voltar ao padrão": aparece sob o grupo, sem faixa fixa
     na tela e sem empurrar o que está embaixo */
  /* ela abre PARA CIMA do grupo: com `top` ela furava a borda do quadro (base
     em y=1005 contra o quadro terminando em 978), caía sobre a barra do rodapé
     e tapava a linha de estado do teclado na tela. */
  .confirma{display:none;position:absolute;bottom:calc(100% + 8px);left:0;right:0;z-index:6;
    align-items:center;gap:8px;background:var(--elevated);border:1px solid var(--orange);
    border-radius:7px;padding:8px 10px;font-size:11.5px;color:var(--texto-suave)}
  .confirma span{flex:1}
  .btn-conf{height:var(--h-acao);padding:0 13px;border-radius:7px;font-size:12.5px;
    font-family:inherit;cursor:pointer;border:1px solid var(--comment);
    background:transparent;color:var(--texto-suave);
    display:inline-flex;align-items:center;justify-content:center}
  .btn-conf.vermelho{border-color:var(--red);color:var(--red)}
  /* O POP-UP ABRE NO CLIQUE E SÓ FECHA NA OPÇÃO OU FORA — decisão dela,
     31/08/2026: *"voltar ao padrão tem que ficar aquele pop up ativo e só
     desativar se eu clicar na opção ou fora dela."*

     ERA `:hover`, e o hover é o gatilho errado para uma pergunta que espera
     resposta: ela sumia assim que o ponteiro saía do caminho entre o botão e o
     "Confirmar", e ler a frase inteira já bastava para perdê-la. Uma confirmação
     que foge do ponteiro não é confirmação — é aviso.

     COMO FUNCIONA, sem uma linha de JavaScript:
     · o `<input type="checkbox">` escondido guarda o estado (aberto/fechado);
     · o `<label for>` que se veste de botão é quem o liga;
     · o **véu** (`.veu`) é um segundo `<label for>` do MESMO checkbox, que cobre
       a tela inteira ATRÁS do pop-up — clicar em qualquer lugar fora fecha,
       porque clicar nele desmarca a caixa;
     · "Confirmar" e "Cancelar" também são `<label for>` do mesmo checkbox,
       então a opção fecha junto.
     O véu só existe quando está aberto (`display:none` no fechado), então ele
     nunca engole clique de quem não abriu nada. */
  .abre-conf{position:absolute;width:0;height:0;opacity:0;pointer-events:none}
  .veu{display:none;position:fixed;inset:0;z-index:5;cursor:default}
  .abre-conf:checked ~ .veu{display:block}
  .abre-conf:checked ~ .confirma{display:flex}

  /* as duas linhas de estado ficam no MESMO y: altura fixa e fundo da coluna */
  .estado{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--texto-mudo)}
  .estado .verde{color:var(--green)} .estado .laranja{color:var(--orange)}
  .estado .valor{color:var(--fg);font-weight:600}

  /* ---- O STATUS DO MODO (27/08, ela: "Status do Modo: ao clicar no botão
          Ligado. Ao clicar nele de novo desligado.") — um interruptor de
          verdade, sem uma linha de script: o `:checked` do input faz o resto.
          Ele é o dono do que os dois botões suspensos faziam embaixo. ---- */
  .tog-in{display:none}
  .tog{display:flex;align-items:center;gap:9px;width:100%;height:var(--h-escolha);border-radius:7px;
       font-size:12px;padding:0 12px;border:1px solid var(--border-forte);
       background:var(--app-bg);color:var(--texto-mudo);cursor:pointer;user-select:none}
  .tog:hover{border-color:var(--comment)}
  .tog .pino{width:9px;height:9px;border-radius:50%;background:var(--border-forte);flex:0 0 9px}
  .tog .txt::after{content:'Desligado'}
  .tog-in:checked + .tog{border-color:var(--green);background:rgba(80,250,123,.1);
       color:var(--fg);font-weight:600}
  .tog-in:checked + .tog .pino{background:var(--green);box-shadow:0 0 7px var(--green)}
  .tog-in:checked + .tog .txt::after{content:'Ligado'}

  /* A DENSIDADE DE 22px FICA SÓ DENTRO DAS TELAS DE CIMA, e o número diz por quê.
     Cada uma das duas telas de botões tem 21 listas em 21 linhas, e mede 660px
     com elas a 22px. No token de 36 as linhas sozinhas passariam de 750px, e a
     janela do produto tem 757. A tela não caberia na tela.
     Na ABA, onde há cinco linhas e não vinte e uma, o token vale: veja
     `.at-linha`. Esta é a única exceção da aba, e ela está aqui declarada em vez
     de espalhada.
     `.tn-cx.larga` (1120px) SAIU em 28/08: existia para caber as duas tabelas
     lado a lado, e agora cada tabela tem a sua tela na largura padrão de 660px.
     As duas regras de altura, que eram `.tn-cx .duas-colunas ...`, valem hoje
     para toda tabela dentro de uma tela — inclusive a do Point-and-click, que
     já herdava a mesma densidade da regra irmã lá em cima. */
  .btn-padrao-tela{border-color:var(--comment);color:var(--texto-suave)}
"""


def _rot(txt):
    """O qualificador ao lado do glifo — SEMPRE com a primeira letra maiúscula.

    A REGRA, e ela vale para as próximas abas: **o qualificador ao lado do glifo
    é capitalizado, como o nome da peça no `pecas-do-dualsense.csv`** — "Direção",
    "Clique esquerdo", "Cima". Ele é rótulo de linha, não complemento no meio de
    uma frase: na mesma coluna, ao lado de "Touchpad" e "Options", a minúscula
    fazia a tabela misturar duas grafias.

    Decisão dela, 29/08/2026. Quem coordena recomendou o contrário — são gestos,
    e em português o complemento é minúsculo. Ela decidiu capitalizar.

    POR QUE AQUI, e não em cada `rot=`: a mesma palavra é escrita em SETE lugares
    ("direção" em quatro, "clique" em dois, "deslizar" em um) e ainda vem de duas
    fontes que não são texto solto — `dir_de` lê o `nome` do d-pad no mapa e
    `TOUCH_REGIOES` lê a `nota` do touchpad. Capitalizar em cada uso deixaria
    nove grafias para divergirem na primeira correção; capitalizar no ÚNICO lugar
    que escreve o `<span class="rot-gl">` alcança também todo `rot=` que nascer
    depois. As fontes continuam minúsculas: quem capitaliza é a TELA, e o mapa
    segue dono da palavra.

    `.capitalize()` não serve — ele rebaixa o resto, e um dia isso comeria a
    maiúscula de um qualificador com nome de peça dentro ("Clique do L3").
    """
    return f'<span class="rot-gl">{txt[:1].upper()}{txt[1:]}</span>'


def _um(pid, rot=None, tam=18):
    """Um glifo do mapa, com o nome do mapa ao lado quando ele não se lê sozinho.

    Os quatro botões da face e as quatro direções do d-pad ficam SEM nome: o
    desenho deles já é o nome. Os outros levam o `nome` (ou o apelido curto) da
    peça — antes isso era um dicionário escrito aqui.
    """
    g = glifo(gl_de(pid), tam=tam)
    if PECAS[pid]["regiao"] not in ("face", "direcional"):
        g += f'<span class="nm">{nome_de(pid)}</span>'
    if rot:
        g += _rot(rot)
    return g


def gl(*pids, sep="/", rot=None, tam=18):
    corpo = f' <span class="mais">{sep}</span> '.join(_um(p, tam=tam) for p in pids)
    if rot:
        corpo += _rot(rot)
    return f'<span class="gls">{corpo}</span>'

# ---------------------------------------------------------------------------
# AS LISTAS DE VALOR. Os grupos são as palavras DELA na fala [11] — "no lado
# direito teríamos Função do teclado, Executar Comando, Mouse" —, e é por isso
# que elas aparecem dentro de cada dropdown, e não só no bloco de ativação.
# ---------------------------------------------------------------------------
# UMA lista só, com as opções dos DOIS lados — ela, 27/08: "as opções que temos
# em ambos os lados no dropin". Antes eram duas listas, e um botão que estivesse
# nas duas tabelas fazia as duas coisas em silêncio.
#
# ELA DEIXOU DE SER DIGITADA em 01/09/2026, e a razão é medida: a mesma lista
# existia em `core/acoes_de_botao.ACOES`, do lado do produto, e as duas JÁ
# DIVERGIAM — faltavam aqui o `Backspace` e o `Delete`, que o produto emite nas
# regiões esquerda e direita do touchpad. Com a lista digitada, a tela não
# conseguia sequer MOSTRAR o que três das suas vinte e uma linhas fazem.
ACOES_UNI = por_grupo()

# O REMAPEAMENTO: para qual botão do controle este botão passa a valer.
#
# ELE ERA DIGITADO, COM OS SÍMBOLOS DESENHADOS À MÃO: "Cross ✕", "Circle ○",
# "Square □", "Triangle △", "D-pad ↑". Agora as cinco famílias saem da coluna
# `regiao` do mapa, na ordem do mapa, e o nome de cada peça vem do mapa também
# — que é o pedido dela de 27/08 aplicado ao último canto da aba onde uma peça
# do DualSense era texto solto.
REMAP = [
    ("Botões", [nome_de(i) for i in _ids("face")]),
    ("Ombros e gatilhos", [nome_de(i) for i in _ids("ombros") + _ids("gatilhos")]),
    ("Analógicos", [x for i in _ids("analogicos") for x in _alvo(i)]),
    ("Direcional", [nome_de(i) for i in _ids("direcional")]),
    ("Sistema", [x for i in _ids("centro") for x in _alvo(i)]),
    ("", ["— Sem troca —"]),
]
ACOES_GESTO = [
    ("Navegação Interna", ["Suspender mouse e teclado", "Próximo perfil", "Perfil anterior",
                           "Sair do modo jogo"]),
    ("Modo de conexão", ["Sobe um degrau no Modo de conexão"]),
    ("Modo Steam", ["Abre e foca a Steam"]),
    ("Executar Comando", ["Religar o controle"]),
    ("", ["— Nada —"]),
]


def drop(grupos, escolhido, classe="campo-linha", gesto="", linha="", campo=""):
    """Um <select> de verdade em TODA linha — nenhum travado (falas [55], [57], [91]).

    O `gesto` só NOMEIA o campo para o piloto (ver `simples`): `<select>` nenhum
    liga por clique. As listas das três telas de pop-up ficam SEM `data-gesto` de
    propósito — elas são os CAMPOS de um formulário cujo ponto de gravação é o
    "Guardar".

    FATO SUBSTITUÍDO (02/09/2026): aqui estava escrito que as 49 listas ficam
    "sem nome" porque só o Guardar importa. **Sem nome elas nunca são pintadas**,
    e um formulário que não é pintado mostra o DESENHO, não o perfil dela —
    enquanto o Guardar lê essas mesmas linhas e as grava. Medido contra a página
    publicada: as 21 opções cravadas são exatamente `acoes_de_botao.padrao()`, e
    o Guardar gravava `button_actions = None`, apagando em silêncio o que ela
    tivesse escolhido. As 21 linhas de *o que cada botão faz* passaram a levar
    `campo`; as duas outras telas continuam sem, porque os gestos delas
    (`guardar-remapeamento`, `guardar-ponto`) não têm dono no produto — pintar
    um formulário que ninguém grava seria a metade errada da cura.
    """
    partes = []
    for rot, ops in grupos:
        op = "".join(f'<option{" selected" if o == escolhido else ""}>{o}</option>' for o in ops)
        partes.append(f'<optgroup label="{rot}">{op}</optgroup>' if rot else op)
    g = f' data-gesto="{gesto}"' if gesto else ""
    # O ENDEREÇO DA LINHA — 01/09/2026. Sem ele o "Guardar" da tela não tem como
    # saber QUAL botão cada `<select>` representa: o ouvinte do piloto manda o
    # valor do elemento CLICADO, e o Guardar é outro elemento, a três telas de
    # distância. É o que faz o botão poder GRAVAR em vez de só recusar.
    ln = f' data-linha="{linha}"' if linha else ""
    # O ENDEREÇO DA PINTURA — 02/09/2026, e ele é o par do de cima: aquele deixa
    # LER, este deixa ESCREVER. `data-hef-alvo="valor"` é obrigatório junto —
    # sem ele o piloto escreveria o texto DENTRO do `<select>` e comeria as
    # opções (ver `simples`). O ouvinte da forma prefere o `data-linha`
    # (`hefesto_vivo.py`: `el.dataset.linha || el.dataset.campo`), então os dois
    # convivem sem disputa.
    c = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    return f'<select class="{classe}"{g}{ln}{c}>{"".join(partes)}</select>'


def simples(ops, classe="escolha-at", gesto="", campo=""):
    """Um `<select>` das opções, com o ENDEREÇO do clique e o da PINTURA.

    O `data-gesto` liga o campo **desde 01/09/2026**, e a frase que estava aqui
    ("nenhum `<select>` desta casa liga") caducou no mesmo dia: o piloto passou a
    ouvir `change` além de `click` (`hefesto_vivo.py:196`) e a mandar o `valor` e
    o `rotulo` da opção escolhida. O motivo antigo era real — o clique num
    `<select>` chega quando a lista ABRE, com o valor ANTIGO —, e é exatamente o
    que o `change` resolve.

    O `campo` é o SEGUNDO endereço, e ele não é enfeite: sem ele a lista fica
    mostrando o que ela escolheu mesmo quando o gesto RECUSOU, porque a recusa
    de um gesto só imprime no terminal (`hefesto_vivo.py:519`) — na tela não
    aparece nada. Com ele, o tique seguinte reescreve o `value` com o que o
    DAEMON diz, e a opção sem dono volta sozinha para o lugar. É a única forma
    de uma recusa ser visível nesta aba.

    `data-hef-alvo="valor"` é obrigatório junto: sem ele a pintura escreveria o
    texto DENTRO do `<select>` (o alvo padrão do `escrever` é `textContent`) e
    comeria as opções.
    """
    g = f' data-gesto="{gesto}"' if gesto else ""
    c = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    op = "".join(f'<option{" selected" if i == 0 else ""}>{o}</option>' for i, o in enumerate(ops))
    return f'<select class="{classe}"{g}{c}>{op}</select>'


def bignum(*pares):
    """Os "seletores tipo bignumbers" da fala [11], num campo do tamanho dos outros.

    Cada par vai num `.par`, e o risco separador viaja DENTRO do par seguinte:
    é isso que deixa o último par encostar na borda direita do campo sem largar
    o separador para trás.

    O par é `(rótulo, valor)` e pode levar mais dois, que são o que LIGA o campo:

        (rótulo, valor, gesto)          os dois `<button>` viram
                                        `<gesto>-menos` e `<gesto>-mais`
        (rótulo, valor, gesto, campo)   e o número ganha endereço de pintura

    SEM O QUARTO, O BOTÃO RESPONDE CALADO: o `−`/`+` muda o daemon e o número na
    tela fica onde estava até alguém recarregar. O `data-campo` é o que o piloto
    reescreve a cada tique (`hefesto_vivo.py`, `window.__hef.pintar`), e é por
    isso que ele anda junto com o gesto, e não depois.
    """
    partes = []
    for i, par in enumerate(pares):
        rot, v = par[0], par[1]
        g = par[2] if len(par) > 2 else ""
        campo = par[3] if len(par) > 3 else ""
        menos = f' data-gesto="{g}-menos"' if g else ""
        mais = f' data-gesto="{g}-mais"' if g else ""
        end = f' data-campo="{campo}"' if campo else ""
        risco = "" if i == 0 else "<span class='risco'></span>"
        # SEM RÓTULO, quando não há com quem comparar. Com DOIS números o `.sub`
        # dizia qual era qual ("Touch"/"Analógico"); com UM, ele repetiria o
        # rótulo da linha. Um `<span>` vazio não é neutro: ele continua ocupando
        # a coluna e abre um vão que a régua de alinhamento acusaria.
        sub = f'<span class="sub">{rot}</span>' if rot else ""
        partes.append(
            f'<span class="par">{risco}'
            f'{sub}<span class="bignum">'
            f'<button class="passo"{menos}>−</button><b{end}>{v}</b>'
            f'<button class="passo"{mais}>+</button>'
            f'</span></span>')
    return f'<div class="campo-num">{"".join(partes)}</div>'


def ajuda(txt, largura=""):
    st = f' style="width:{largura}"' if largura else ""
    return f'<span class="ajuda">?<span class="dica"{st}>{txt}</span></span>'

# ---------------------------------------------------------------------------
# OS CINCO COMBOS: a linha da tabela e o desenho do Player 1 usam o MESMO
# número, e o ponteiro numa linha acende as peças dela no desenho.
# ---------------------------------------------------------------------------
COMBOS = [
    (1, ("ps", "options"), "Suspender mouse e teclado"),
    (2, ("ps", "dpad_up"), "Próximo perfil"),
    (3, ("ps", "dpad_down"), "Perfil anterior"),
    (4, ("ps", "stick_r"), "Sobe um degrau no Modo de conexão"),
    (5, ("ps",), "Abre e foca a Steam"),
]

# ---------------------------------------------------------------------------
# O REALCE DO COMBO — e ele estava MORTO em três das cinco linhas.
#
# A regra antiga pintava `#nv-<peça> > .peca`, e isso não alcançava nada em dois
# casos que só apareceram quando o desenho passou a ser gerado:
#   · o PS é `peca sem-tinta` (`fill:none !important`) desde que ela mandou tirar
#     o círculo de trás do logo — a regra perdia para o `!important`;
#   · o Options traz a cor no `style` INLINE (é o que o portão das cores já
#     dizia: "style inline vence qualquer folha") — a regra perdia de novo.
# Resultado medido: das cinco linhas, a 1 (PS+Options) e a 5 (PS) não acendiam
# NADA, e o PS não acendia em nenhuma. A legenda da aba afirmava o contrário.
#
# A cura tem três partes: `!important` na peça, o GLIFO junto (é ele o desenho
# do PS), e nunca tocar a peça `sem-tinta` — acendê-la traria de volta o círculo
# que ela mandou tirar.
def _realce(pref, pid):
    sel = [f'#{pref}-glifo-{pid}', f'#{pref}-glifo-{pid} *']
    if _tem_tinta(pid):
        sel.insert(0, f'#{pref}-{pid} > .peca')
    return sel


REALCE = "\n".join(
    f'  .gestos:has(.g{n}:hover) :is('
    + ",".join(s for p in pecas for s in _realce(QUEM_NAVEGA["pref"], p))
    + "){fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink)}"
    for n, pecas, _ in COMBOS)

# AS CINCO LÂMPADAS SAÍRAM, e com elas a lista de ids que as acendia.
#
# Havia aqui um `LAMPADAS` com dez regras `#{pref}-led-jogador-{n}{fill:var(--fg)}`,
# geradas do `PADRAO_JOGADOR`. Ela era a metade VIVA do desenho: a classe
# `led-on` que o `monta.svg(jogador=…)` funde nas mesmas peças estava no DOM e
# inerte, então tirar a classe não apagava nada e tirar só a lista deixaria a
# classe herdada para a próxima folha reacender.
#
# Decisão dela, 28/08: as lâmpadas do jogador saem dos desenhos pequenos. Neste
# cartão elas mediam 1,90 × 0,64 px. Agora o grupo inteiro sai do SVG, em
# `controle()`, por `svg(lampadas=False)` — o mesmo botão que os cartões da
# Jogar usam.

CSS += "\n  /* ---- o desenho acompanha o combo apontado, sem uma linha de script ---- */\n"
CSS += REALCE + "\n"

# ---------------------------------------------------------------------------
# A PORTA PARA O BANCO DE PROVAS — `.porta`, 29/08/2026.
#
# DEFEITO MEDIDO: `mapa-do-controle.html` tem 1309 linhas, gerador próprio
# (`_ferramentas/mapa.py`) e DOIS portões que o medem
# (`scripts/check_pecas_do_dualsense.py`, `scripts/check_cores_do_dualsense.py`)
# — e `grep -c 'mapa-do-controle' layout/??-*.html` devolve **0 nas dez
# abas**. Só se chega nele digitando o caminho. É a fonte da verdade das 28
# peças, e as 21 linhas das duas telas de botões desta aba saem do MESMO
# `docs/data/pecas-do-dualsense.csv` que ele publica.
#
# A porta é `margin-left:auto` no `.quadro-topo`, que é o mesmo lugar e o mesmo
# empurrão do `.sensores` da aba Controles — não é padrão novo.
#
# A ALTURA É TRAVADA EM 17px, e o número é medido: o `.quadro-topo` é
# `align-items:center`, então a altura dele é a do filho mais alto, e o
# `.quadro-titulo` mede **17px**. A primeira volta desta porta era uma pastilha
# com borda, `height:19px` — dois pixels a mais que o título —, e o quadro
# inteiro desceu: 663 das 733 caixas da aba mudaram de lugar, todas por 2px.
# Sem borda e sem preenchimento, a porta é um link de texto com o mesmo
# line-height do título, e a medição de antes e depois volta a bater caixa a
# caixa. Um `.btn` da casa (34px) empurraria 17.
CSS += """
  .porta{margin-left:auto;font-size:11px;line-height:17px;height:17px;
    color:var(--texto-mudo);text-decoration:none;white-space:nowrap}
  .porta:hover{color:var(--cyan);text-decoration:underline}
"""


#: O marcador de campo vazio — o mesmo travessão das outras cinco abas.
VAZIO = "—"


def controle_vazio(c):
    """O LUGAR de um controle que não está na mesa — ordem dela, 31/08/2026:
    *"todas as abas tem que ter só dois controles conectados no momento, o resto
    fica off"* e *"colocar algo como Desconectado e não os controles mockados"*.

    O CARD CONTINUA NA FILEIRA, e é o ponto: quem olha precisa saber que a mesa
    tem quatro lugares e dois vazios, não que ela tem dois. O que sai é o estado
    — a cor do plástico, o transporte e o "Só a janela", porque nenhum deles tem
    aparelho para valer.
    """
    n = c["jogador"]
    return (
        f'              <div class="nav-ctl vazia" data-conectado="nao"'
        f' title="Nenhum controle neste lugar.">\n'
        f'                {svg(c["pref"], c["cor"], classes="ds-svg", lampadas=False)}\n'
        f'                <div class="nav-rot">P{n} <span class="pt">•</span> Desconectado</div>\n'
        f'                <div class="nav-est">{VAZIO}</div>\n'
        f'              </div>')


def controle(c):
    """Um dos quatro da mesa: o desenho na cor do plástico, o rótulo na ordem
    dela (player • plástico • transporte) e o que ele navega agora."""
    n = c["jogador"]
    navega = n == NAVEGA
    ponto = '<span class="bolinha"></span>' if navega else ""
    return (
        f'              <div class="nav-ctl{" navega" if navega else ""}"'
        f' style="--plastico:{cor_da_zona(c["cor"])}"'
        f' data-controle="{c.get("uniq") or c["pref"]}" data-conectado="sim"'
        f' title="Player {n} • {c["nome"]} • {c["via"]}">\n'
        f'                {svg(c["pref"], c["cor"], classes="ds-svg", lampadas=False, luz=_hex(player_slot_color(n)))}\n'
        f'                <div class="nav-rot">P{n} <span class="pt">•</span> {c["nome"]}</div>\n'
        f'                <div class="nav-est" data-campo="navega">{ponto}{c["via"]} <span class="pt">•</span> '
        f'{"Navega o PC" if navega else "Só a janela"}</div>\n'
        f'              </div>')


def linha_combo(n, pecas, faz):
    # O PS entra SÓ com o glifo: ela, 27/08 — "temos o icone do PS e do lado
    # direito PS escrito novamente, tira a parte escrita". O ícone já diz o nome.
    nomes = [glifo(gl_de(p), tam=18) if p == "ps" else _um(p) for p in pecas]
    combo = ' <span class="mais">+</span> '.join(nomes)
    return (f'                <tr class="g g{n}"><td class="b">'
            f'<span class="gls"><span class="mk-n">{n}</span>{combo}</span></td>'
            f'<td>{drop(ACOES_GESTO, faz, gesto="acao-do-gesto")}</td></tr>')

# A LISTA ÚNICA DE BOTÕES — a MESMA primeira coluna nas duas telas de botões.
# Ela, 27/08: "Em que cada linha seria um dos botões do controle" e, da tabela da
# direita, "Repetindo a mesma tabela da Esquerda".
# (peça do mapa, qualificador, o que ele faz)
#: O PADRÃO DE CADA LINHA VEM DO PRODUTO — `core/acoes_de_botao.padrao()`, que
#: por sua vez o deriva dos quatro mapas. Antes ele era DIGITADO aqui, ao lado
#: de cada glifo, e três das vinte e uma linhas estavam erradas desde que foram
#: escritas: o touchpad dizia "Botão esquerdo · Botão direito · F11" e o produto
#: faz "Backspace · Enter · Delete". Nada as comparava.
#:
#: A ORDEM E OS GLIFOS CONTINUAM AQUI, porque são desenho; o que saiu foi o
#: FATO. `_PADRAO_DOS_BOTOES` casa a linha da tela com o endereço do produto.
#: botão -> RÓTULO, que é o que o `<select>` mostra como escolhido.
_PADRAO_DOS_BOTOES = {b: rotulo_da_acao(a)
                      for b, a in _padrao_dos_botoes().items()}

BOTOES = [
    (gl("cross"),                                "cross"),
    (gl("circle"),                               "circle"),
    (gl("square"),                               "square"),
    (gl("triangle"),                             "triangle"),
    (gl("l1"),                                   "l1"),
    (gl("r1"),                                   "r1"),
    (gl("l2"),                                   "l2"),
    (gl("r2"),                                   "r2"),
    (gl("stick_l", rot="clique"),                "l3"),
    (gl("stick_l", rot="direção"),               EIXO_ESQUERDO),
    (gl("stick_r", rot="clique"),                "r3"),
    (gl("stick_r", rot="direção"),               EIXO_DIREITO),
    # cada direcional é uma LINHA — ela, 27/08. Numa linha só, as quatro setas
    # dividiam um valor e não havia como dar destino diferente a cada direção.
    (gl("dpad_up",    rot=dir_de("dpad_up")),    "dpad_up"),
    (gl("dpad_down",  rot=dir_de("dpad_down")),  "dpad_down"),
    (gl("dpad_left",  rot=dir_de("dpad_left")),  "dpad_left"),
    (gl("dpad_right", rot=dir_de("dpad_right")), "dpad_right"),
    (gl("options"),                              "options"),
    (gl("share"),                                "create"),
    # as TRÊS regiões do touchpad ganharam linha — ela, 27/08: "o touchpad tem o
    # click pra esquerda, linha do clique direita linha do click centro".
    (gl("touchpad", rot=TOUCH_REGIOES[0]),       "touchpad_left_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[1]),       "touchpad_right_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[2]),       "touchpad_middle_press"),
]
SEM_TROCA = REMAP[-1][1][0]

# ---------------------------------------------------------------------------
# AS OPÇÕES DE ATIVAÇÃO — cada rótulo é a palavra dela na fala [11].
# ---------------------------------------------------------------------------
D_QUANDO = ajuda(
    "Vale para <b>este perfil</b>. Enquanto estiver em <b>Nunca</b>, o controle "
    "é só gamepad e nada desta aba chega ao PC.")
D_TECLADO = ajuda(
    "Liga o que o controle <b>digita</b>: os atalhos da tabela à direita, o teclado "
    "na tela e as três regiões do touchpad.<br><br>"
    "Passou a viajar no <b>perfil</b>, como o mouse vizinho já viajava.")
D_MOUSE = ajuda(
    "Os <b>mapeamentos pré-prontos</b> de mouse. Trocar aqui reescreve as linhas "
    "da tabela <b>O controle como mouse</b>; qualquer linha continua "
    "editável depois.")
#: AS DUAS DICAS SÃO LIDAS DO PRODUTO, e antes eram digitadas — as duas diziam
#: *"De 1 a 10"*, e as duas estavam erradas: o cursor vai a 12 e a rolagem a 5
#: (`integrations/uinput_mouse.py`, que desde 01/09/2026 é o dono da faixa).
D_VEL = ajuda(
    f"Uma velocidade só, porque é um número só no Hefesto: o <b>analógico "
    f"esquerdo</b> e o <b>touch</b> do touchpad andam pelo mesmo ajuste.<br><br>"
    f"De {MOUSE_SPEED_MIN} a {MOUSE_SPEED_MAX}. O padrão do Hefesto é "
    f"{DEFAULT_MOUSE_SPEED}.")
D_ROL = ajuda(
    f"Rola com o <b>analógico direito</b>. Rolar com dois dedos no touchpad é "
    f"outra coisa, e o Hefesto ainda não faz.<br><br>"
    f"De {SCROLL_SPEED_MIN} a {SCROLL_SPEED_MAX}. O padrão do Hefesto é "
    f"{DEFAULT_SCROLL_SPEED}.")
D_INTERNA = ajuda(
    "Navegar <b>a janela do Hefesto</b> com o controle — abas, botões e listas.<br><br>"
    f"Com os {len(MESA)} controles na mesa, cada jogador anda no seu próprio card "
    "e o <b>X de cada um grava no controle dele</b> — sem disputar o card do "
    "vizinho.<br><br>"
    "É outra coisa que o cursor do PC: esse é <b>um só</b>, e sai do controle do "
    f"Player {NAVEGA}.")
# UMA linha só: ela, 27/08 — "o seletor de modo steam tá trocado com ativar modo
# steam Deck. Esses dois botões tem que ser Unificados. Deixa Só Modo Steam."
D_STEAM = ajuda(
    "O controle passa a navegar a <b>Steam</b> do jeito que navega num Steam Deck: "
    "o Modo Jogo responde ao d-pad e aos botões, sem mouse.<br><br>"
    "O terceiro degrau grava a escolha para a <b>próxima vez</b> — a Steam abre "
    "direto em Modo Jogo, sem ninguém clicar. Esse degrau vale para a máquina, "
    "não só para este perfil.")

# O interruptor que substituiu "Quando vira mouse e teclado" — e, com ele, os dois
# botões que ficavam sob a tabela do mouse. Ela, 27/08: "Status do Modo: ao clicar
# no botão Ligado. Ao clicar nele de novo desligado." e "Suspender Mouse e Teclado,
# Sair do Modo Jogo, deixam de existir devido ao botão status na parte superior."
#
# O `data-gesto` VAI NO `<label>`, e não no `<input>`: o `.tog-in` é
# `display:none`, então clique nenhum o alcança direto — quem recebe o clique é
# o rótulo, e é dele que o `closest()` do piloto parte.
#
# O QUE ESTE ENDEREÇO **NÃO** RESOLVE, e é dívida declarada: a marca de qual
# lado o interruptor está mora no `:checked` do CSS, e o piloto não sabe
# escrever `checked` — o `escrever()` dele cobre texto, largura, fundo e
# `value`, mais nada. Então o desenho nasce `checked` e o daemon dela nasce com
# `mouse_emulation.enabled=false`: os dois podem discordar até alguém dar ao
# piloto um alvo de `checked`. O gesto trata isso do único jeito honesto que lhe
# resta — decide pelo DAEMON, nunca pelo que a caixinha mostra.
STATUS_MODO = ('<input type="checkbox" id="st-modo" class="tog-in" checked>'
               '<label class="tog" for="st-modo" data-gesto="modo">'
               '<span class="pino"></span>'
               '<span class="txt"></span></label>')

# ---------------------------------------------------------------------------
# UM BOTÃO VIROU DOIS, E UMA POP-UP VIROU DUAS. Ela, 28/08/2026: "aba navegação
# no botão Definições e Remapeamento / Abrimos uma tela pra remapeamento e
# Definições Controle e Mouse, vamos dividir isso em dois botões no mesmo lugar
# e dividir em dois pop up um pra cada. Tem muita info ali."
#
# O "muita info" era medida: uma tela só, de 1120x682px, com 42 listas e 42
# linhas de tabela. Cada metade fica com 21 linhas — a divisão resolve a
# LARGURA (1120px -> 660px, a padrão), não a densidade. O que resolve a
# densidade é o teto de altura com rolagem interna, em `.tn-cx`.
#
# Havia aqui um `D_BOTOES` e um `D_PADRAO` que descreviam "as duas tabelas" da
# tela única. Nenhum dos dois era usado em lugar nenhum do HTML — e depois da
# divisão os dois passariam a descrever uma tela que não existe. O `D_BOTOES`
# virou os dois abaixo, e estes SÃO usados, um no título de cada tela; o que o
# `D_PADRAO` dizia ("o que este botão apaga") passou a viver onde ele morde, na
# frase de confirmação de cada "Voltar ao padrão".
# ---------------------------------------------------------------------------
D_DEFINICOES = ajuda(
    f"As <b>{len(BOTOES)} linhas</b> de cada botão do controle: <b>o que ele faz</b> "
    "— mouse, tecla ou programa, tudo na mesma lista.<br><br>"
    "A lista de botões sai de <b>docs/data/pecas-do-dualsense.csv</b>, o mesmo mapa "
    "que nomeia as peças do desenho.<br><br>"
    f"Valem para o controle que navega o PC: o <b>P{NAVEGA} "
    f"{QUEM_NAVEGA['nome']} {QUEM_NAVEGA['via']}</b>.")
D_REMAPEAMENTO = ajuda(
    f"As mesmas <b>{len(BOTOES)} linhas</b>, na mesma ordem, dizendo outra coisa: "
    "<b>para qual outro botão</b> cada um passa a valer.<br><br>"
    "É troca de botão por botão, e ela vale antes de o jogo ver. O que cada botão "
    "<b>faz</b> se escolhe na tela <b>Definições Controle e Mouse</b>, ao lado.<br><br>"
    f"Valem para o controle que navega o PC: o <b>P{NAVEGA} "
    f"{QUEM_NAVEGA['nome']} {QUEM_NAVEGA['via']}</b>.")

#: AS TRÊS PALAVRAS DA "Função do teclado", e elas são o CONTRATO do gesto.
#:
#: O `<option>` não leva `value` de propósito: `value` não está entre os
#: atributos que `scripts/check_o_desenho_aprovado.INVISIVEIS` ignora, então
#: pô-lo aqui faria toda marcação virar divergência de desenho. Sem ele, o
#: `select.value` que chega ao Python É o texto da opção — e é por isso que
#: `pacotes/a06_navegacao.py` casa por texto.
#:
#: **A MESMA LISTA ESTÁ LÁ, e a repetição é declarada**: o gesto casa pela
#: PRIMEIRA palavra (tolerante ao que vier depois do travessão) e a pintura usa
#: as duas frases inteiras. Quem reescrever uma opção aqui tem de abrir
#: `a06_navegacao.py` — o cabeçalho de `_TECLADO` diz o que muda de cada lado.
OPCOES_TECLADO = [
    "Ligada — atalhos e teclado na tela",
    "Só fora do jogo",
    "Desligada",
]

ATIVACAO_ESQ = [
    ("Status do Modo", D_QUANDO, STATUS_MODO),
    ("Função do teclado", D_TECLADO,
     simples(OPCOES_TECLADO, gesto="teclado", campo="teclado-estado")),
    ("Navegação Interna", D_INTERNA, simples([
        "Ligada — cada controle navega o Hefesto",
        f"Só o Player {NAVEGA} navega",
        "Desligada"], gesto="navegacao-interna")),
]

# AS DUAS METADES DE CADA LINHA NÃO SÃO IRMÃS, e foi isto que a ligação mediu:
# só a da direita ("Analógico") tem dono no produto.
#
#   · `mouse_emulation.speed`        é UM número (1..12), e o cursor do TOUCHPAD
#     sai dele: `emit_touchpad_move` escala por
#     `TOUCHPAD_SENSITIVITY * (mouse_speed / DEFAULT_MOUSE_SPEED)`
#     (`integrations/uinput_mouse.py:486`). Não há segunda velocidade a ajustar
#     — o "Touch" da tela é uma conta que ninguém faz do outro lado.
#   · `mouse_emulation.scroll_speed` é UM número (1..5) e vale só para o
#     analógico DIREITO: `_emit_scroll(rx, ry)` (`uinput_mouse.py:412`). Rolagem
#     por dois dedos no touchpad **não existe** no produto — nem uma linha.
#
# Os dois campos sem dono ficam com NOME e sem gesto, que é o que faz o piloto
# recusar dizendo qual é, em vez de o clique sumir.
ATIVACAO_DIR = [
    # UM NÚMERO EM CADA LINHA — decisão dela, 01/09/2026: *"só ajustar o texto e
    # deixar rolagem, ajustar ali pra deixar um só se for o caso pra ambos"*.
    # O segundo número de cada par prometia um ajuste que o produto não tem, e a
    # medição está logo acima: `mouse_speed` move o touchpad E o analógico, e
    # rolagem por dois dedos não existe. Os quatro botões `−`/`+` que sobravam
    # saíram do desenho junto com os rótulos.
    ("Velocidade de cursor", D_VEL,
     bignum(("", DEFAULT_MOUSE_SPEED, "vel-cursor", "vel-cursor"))),
    ("Velocidade da rolagem", D_ROL,
     bignum(("", DEFAULT_SCROLL_SPEED, "rolagem", "vel-rolagem"))),
    ("Modo Steam", D_STEAM, simples([
        "Desligado",
        "Ligado — o controle navega a Steam como num Steam Deck",
        "Ligado, e a Steam abre em Modo Jogo na próxima vez"], gesto="modo-steam")),
]

# A FILEIRA AO PÉ DO BLOCO: os QUATRO botões com a mesma largura, ocupando-o inteiro.
#
# "Definições e remapeamento" virou dois, na ordem em que ela os nomeou, e no
# mesmo lugar do que havia. Medido em 28/08: a fileira tem 1086px; com três,
# cada botão ficava com 352,7px, e com quatro fica com 261,8px.
#
# O TERCEIRO BOTÃO TEVE DE ENCURTAR, e é medida: "Configurar o estilo
# Point-and-click" ocupava 246,7px do texto — cabia nos 352,7 e NÃO cabe nos
# 261,8 menos os 26 de padding. O `.btn` não corta texto, ele QUEBRA: o rótulo
# ia para duas linhas dentro de uma caixa de 34px de altura fixa. O nome curto
# não foi inventado aqui — é como a própria pop-up dele já se chama no título.
#
# O "VOLTAR AO PADRÃO" DA FILEIRA VOLTOU A FAZER O QUE O NOME DIZ. A frase dele
# era "Apagar as 21 linhas das duas tabelas e voltar ao de fábrica?", e com as
# tabelas em duas telas separadas "as duas tabelas" deixou de ser o que este
# botão alcança. Cada tela ganhou o seu "Voltar ao padrão", que zera só a tabela
# dela; o daqui devolve a ABA INTEIRA, e a frase agora lista o que ele apaga.
FILEIRA = f'''
            <div class="acoes quatro grupo-padrao">
              <a class="btn roxo" href="#definicoes-mouse">Definições Controle e Mouse</a>
              <a class="btn roxo" href="#remapeamento">Remapeamento dos botões</a>
              <a class="btn roxo" href="#point-and-click">Configurar o estilo Point-and-click</a>
              <!-- O RÁDIO VEM ANTES de tudo o que reage a ele: o `~` do CSS só
                   enxerga irmão POSTERIOR. É a mesma armadilha que o interruptor
                   da aba Jogar documenta, e a mesma cura. -->
              <input type="checkbox" id="conf-padrao" class="abre-conf">
              <label for="conf-padrao" class="btn btn-padrao">Voltar ao padrão</label>
              <label for="conf-padrao" class="veu" title="Fecha sem mudar nada."></label>
              <div class="confirma">
                <span>Devolver a aba <b>Navegação</b> inteira ao de fábrica — as opções
                  de ativação, os {len(COMBOS)} gestos e as {len(BOTOES)} linhas das duas
                  telas de botões?</span>
                <!-- O ENDEREÇO VAI NO "Confirmar", nunca no "Voltar ao padrão":
                     o de cima só ABRE a pergunta (é `<label for>` do mesmo
                     checkbox, e funciona), e marcá-lo faria o piloto acusar de
                     sem dono um botão que faz o que promete. -->
                <label for="conf-padrao" class="btn-conf vermelho" data-gesto="padrao-da-aba">Confirmar</label>
                <label for="conf-padrao" class="btn-conf">Cancelar</label>
              </div>
            </div>'''

PONTO_MAPA = [
    (gl("touchpad", rot="deslizar"), "Movimento do cursor"),
    (gl("touchpad", rot=TOUCH_REGIOES[0]), "Botão esquerdo"),
    (gl("touchpad", rot=TOUCH_REGIOES[1]), "Botão direito"),
    (gl("cross"),                    "Botão esquerdo"),
    (gl("circle"),                   "Botão direito"),
    (gl("stick_l", rot="direção"),   "Movimento do cursor"),
    (gl("stick_r", rot="direção"),   "Rolagem vertical e horizontal"),
]

# ---------------------------------------------------------------------------
# AS DUAS TELAS DE BOTÕES — uma por botão da fileira, uma tabela em cada.
#
# Elas nascem da MESMA lista `BOTOES`, na mesma ordem: é a segunda metade do
# pedido dela ("dividir em dois pop up um pra cada"), e o que muda de uma para a
# outra é a segunda coluna, não a primeira. Por isso a função abaixo, e não duas
# telas escritas por extenso: duas cópias divergiriam na primeira correção.
#
# Cada uma leva o SEU rodapé, com o seu "Voltar ao padrão" e a frase que diz o
# que aquele botão apaga — e o que ele NÃO apaga, que é o que a frase antiga,
# única e comum às duas tabelas, não podia dizer.
# ---------------------------------------------------------------------------
def tela_de_botoes(ident, titulo, dica, coluna, linhas, confirma, guardar, padrao):
    """Uma das duas telas de botões.

    Os dois últimos argumentos são os NOMES dos gestos que a tela tem — o
    "Cancelar" e o "×" não levam nome porque **funcionam**: fecham a pop-up pelo
    `:target` do CSS, sem uma linha de script. Marcar um botão que faz o que
    promete o faria aparecer no relato como "sem dono", que é o inverso da
    verdade.
    """
    return f'''
<div class="tela-nova" id="{ident}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{titulo}</span>
      {dica}
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      <!-- TEXTO NA TELA É ZERO — regra dela, 30/08/2026: *"texto na interface é
           zero, só deixamos se for algo extremamente importante, e se for de
           média importância vira tooltip"*. Esta frase era prosa fixa a poucos
           pixels de um `?` que explicava o mesmo assunto. Ela não sumiu: subiu
           para a dica do cabeçalho, onde só aparece a quem pergunta. -->
      <div class="moldura">
        <table class="tab">
          <tr><th>Botão do controle</th><th>{coluna}</th></tr>
{linhas}
        </table>
      </div>
    </div>
    <div class="tn-rod grupo-padrao">
      <a class="btn" href="#">Cancelar</a>
      <a class="btn btn-padrao btn-padrao-tela" href="#">Voltar ao padrão</a>
      <a class="btn roxo" href="#" data-gesto="{guardar}" data-hef-forma="{ident}">Guardar</a>
      <div class="confirma">
        <span>{confirma}</span>
        <button class="btn-conf vermelho" data-gesto="{padrao}">Confirmar</button>
        <button class="btn-conf">Cancelar</button>
      </div>
    </div>
  </div>
</div>
'''


TELA_DEFINICOES = tela_de_botoes(
    "definicoes-mouse", "Definições Controle e Mouse", D_DEFINICOES,
    "O que ele faz",
    chr(10).join(
        f'          <tr><td class="b">{b}</td>'
        f'<td>{drop(ACOES_UNI, _PADRAO_DOS_BOTOES[i], linha=i, campo=f"acao-{i}")}</td></tr>'
        for b, i in BOTOES),
    f"Devolver ao de fábrica as {len(BOTOES)} linhas de <b>o que cada botão faz</b>? "
    "O <b>Remapeamento dos botões</b> não é tocado.",
    guardar="guardar-definicoes", padrao="padrao-definicoes")

TELA_REMAPEAMENTO = tela_de_botoes(
    "remapeamento", "Remapeamento dos botões", D_REMAPEAMENTO,
    "Passa a valer como",
    chr(10).join(f'          <tr><td class="b">{b}</td><td>{drop(REMAP, SEM_TROCA)}</td></tr>'
                 for b, _ in BOTOES),
    f"Devolver as {len(BOTOES)} linhas ao <b>{SEM_TROCA}</b>? "
    "As <b>Definições Controle e Mouse</b> não são tocadas.",
    guardar="guardar-remapeamento", padrao="padrao-remapeamento")

TELA_PONTO = f'''
<div class="tela-nova" id="point-and-click">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">Estilo Point-and-click</span>
      {ajuda(
        "Um <b>Estilo de Jogo</b>, como o FPS e o Corrida. O perfil escolhe usá-lo; "
        "o que ele faz é escrito <b>aqui</b>.<br><br>"
        "Enquanto ele estiver valendo, estas linhas mandam — as da aba voltam "
        "quando o estilo sai.<br><br>"
        "Serve para jogo de <b>apontar e clicar</b>, que espera mouse e não entende "
        "controle: <b>o touchpad vira o ponteiro</b>, e o toque vira o clique.")}
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      <!-- TEXTO NA TELA É ZERO — regra dela, 30/08/2026: *"texto na interface é
           zero, só deixamos se for algo extremamente importante, e se for de
           média importância vira tooltip"*. Esta frase era prosa fixa a poucos
           pixels de um `?` que explicava o mesmo assunto. Ela não sumiu: subiu
           para a dica do cabeçalho, onde só aparece a quem pergunta. -->
      <div class="moldura">
        <table class="tab">
          <tr><th>Botão do controle</th><th>O que ele faz neste estilo</th></tr>
{chr(10).join(f'          <tr><td class="b">{b}</td><td>{drop(ACOES_UNI, f)}</td></tr>' for b, f in PONTO_MAPA)}
        </table>
      </div>
      <div class="tn-vel">
        <div class="at-linha"><span class="at-rot">Velocidade de cursor{D_VEL}</span>
          {bignum(("", 8))}</div>
        <div class="at-linha"><span class="at-rot">Velocidade da rolagem{D_ROL}</span>
          {bignum(("", 4))}</div>
      </div>
    </div>
    <!-- OS DOIS `bignum` DESTA TELA FICAM SEM ENDEREÇO, e é decisão medida: eles
         são a velocidade DO ESTILO Point-and-click, que o perfil escolhe usar —
         não a velocidade viva do daemon. Ligá-los ao `mouse.emulation.set`
         mudaria o cursor AGORA enquanto ela pensa que edita um estilo guardado,
         que é a pior forma de um botão mentir. Quem carrega o que falta é o
         "Guardar no estilo", que é o ponto de gravação de todos eles. -->
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="guardar-ponto">Guardar no estilo</a>
    </div>
  </div>
</div>
'''


def at_linha(rot, dica, campo):
    return (f'              <div class="at-linha"><span class="at-rot">{rot}{dica}</span>'
            f'{campo}</div>')


D_MESA = ajuda(
    f"Os {len(MESA)} controles da mesa, cada um na cor do seu plástico, com as "
    "cinco lâmpadas no padrão do número dele e a barra de luz na cor automática "
    "daquele número.<br><br>"
    f"<b>O cursor do PC é um só.</b> Mouse, teclado e os {len(COMBOS)} gestos saem "
    f"do controle do <b>Player {NAVEGA}</b> — é o controle que o Hefesto lê por "
    "inteiro; os outros chegam ao jogo pelo gamepad virtual e não mexem no "
    "cursor.<br><br>"
    "Quem escolhe o alvo de um ajuste é a <b>fita do topo</b>, e só ela — estes "
    "cartões são leitura.")

D_GESTOS = ajuda(
    "São combinações que valem <b>sem largar o controle</b>, a qualquer momento, "
    "mesmo com o jogo aberto.<br><br>"
    "Apertar os dois botões em até <b>0,15 s</b> conta como combo — mais devagar, "
    "o Hefesto entende como dois toques separados.<br><br>"
    f"O número de cada linha marca a peça no desenho do <b>Player {NAVEGA}</b>; "
    "passe o ponteiro por uma linha e ela acende. Acende só ali porque é só ali "
    "que o gesto existe.<br><br>"
    "<b>Ressalva:</b> o <b>PS + R3</b> e o <b>PS + Options</b> são as duas saídas "
    "de emergência quando o jogo não responde — trocar o que eles fazem tira "
    "essa saída. Os cinco degraus do <b>Modo de conexão</b> se escolhem na aba "
    "<b>Jogar</b>, e aqui não se repetem.")

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Navegação</span>
        {ajuda(
          "Serve para navegar o computador sem largar o controle — e para os jogos que "
          "só entendem mouse e teclado.<br><br>"
          "Precisa de <b>uinput</b> e de uma regra <b>udev</b>; o instalador já deixa os "
          "dois prontos. Se a linha de estado abaixo estiver vermelha, é isso que falta."
          "<br><br><b>Combinações:</b> junte teclas com &quot;+&quot; (ex.: Alt + Tab). Nenhum "
          "atalho de fábrica digita letra — para escrever texto, abra o teclado na tela "
          "com o <b>L3</b>.")}
        <a class="porta" href="mapa-do-controle.html" title="Abre o mapa do controle — as {len(PECAS)} peças do aparelho com nome, apelido e glifo, e as cores de fábrica para ver clicando. É de lá que saem as {len(BOTOES)} linhas das duas telas de botões desta aba: o mesmo docs/data/pecas-do-dualsense.csv.">Banco de provas: o mapa do controle&nbsp;↗</a>
      </div>
      <div class="quadro-corpo">

        <!-- ---------- A MESA + OS GESTOS, nas duas mesmas colunas ---------- -->
        <div class="sec-rot sec-dupla">
          <span>Quem navega, e com qual controle{D_MESA}</span>
          <span>Os gestos do controle{D_GESTOS}</span>
        </div>
        <div class="moldura">
        <div class="gestos">
          <div class="previa">
            <div class="nav-mesa">
{chr(10).join(controle(c) if c.get('conectado', True) else controle_vazio(c) for c in MESA)}
            </div>
          </div>
          <div class="combos">
            <table class="tab">
              <tr><th>Combinação no controle</th><th>O que faz</th></tr>
{chr(10).join(linha_combo(n, p, f) for n, p, f in COMBOS)}
            </table>
          </div>
        </div>
        </div>

      </div>
    </div>

    <!-- ---------- AS OPÇÕES DE ATIVAÇÃO VIRARAM QUADRO PRÓPRIO ----------
         Pedido dela, 30/08: *"a parte 'As opções de ativação' coloca na mesma cor
         que o Navegação e divide em dois blocos, o superior e as opções de
         ativação"*.

         Ela era um `.sec-rot` — rótulo de CAMPO, verde, do mesmo peso que
         "Controle" ou "Brilho" — dentro do quadro da Navegação. Mas ela não nomeia
         um campo: nomeia um ASSUNTO, com sete linhas de escolha embaixo. Virando
         `.quadro-titulo` ela ganha o roxo e o tamanho que a Navegação tem, e a
         divisão em dois quadros diz na estrutura o que a leitura já dizia: em cima
         quem navega e com quê, embaixo como ligar e com que velocidade. -->
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">As opções de ativação</span>
      </div>
      <div class="quadro-corpo">
        <div class="moldura">
          <div class="ativacao">
            <div class="at-col">
{chr(10).join(at_linha(*x) for x in ATIVACAO_ESQ)}
            </div>
            <div class="at-col">
{chr(10).join(at_linha(*x) for x in ATIVACAO_DIR)}
            </div>
          </div>
        </div>

        <!-- ---------- O TERCEIRO BLOCO: os três botões, sozinhos ----------
             Ela, 27/08: "separa os três botões do bloco dois ... e os coloca
             abaixo em um bloco individual, um terceiro". Dentro do bloco dois
             eles liam como a última linha das opções de ativação, e não são:
             duas abrem outra tela e a terceira apaga as linhas das tabelas. -->
        <div class="moldura moldura-acoes">
{FILEIRA}
        </div>

      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>Um botão virou dois, e uma pop-up virou duas</h2>
  <ul>
    <li><b>O que ela pediu, e por quê.</b> <i>"aba navegação no botão Definições e
    Remapeamento / Abrimos uma tela pra remapeamento e Definições Controle e Mouse,
    vamos dividir isso em dois botões no mesmo lugar e dividir em dois pop up um pra
    cada. <b>Tem muita info ali</b>."</i> O "muita info" era medida: uma tela só, de
    <b>1120×682px</b>, com <b>42 listas</b> e <b>42 linhas</b> de tabela.</li>
    <li><b>A divisão resolve a largura; ela NÃO resolve a densidade.</b> Cada tela
    caiu de <b>1120px</b> para a largura padrão de <b>660px</b>, e cada uma ficou
    com <b>{len(BOTOES)} linhas</b> e <b>{len(BOTOES)} listas</b> — metade do total,
    e ainda vinte e uma. As duas medem <b>660,3px</b> de altura contra os
    <b>757px</b> da janela do produto: sobram 96,7px, e o rodapé com o
    <i>Guardar</i> fecha em y=707,7 dentro dela.</li>
    <li><b>O teto de altura, que não existia.</b> A <code>.tn-cx</code> não tinha
    <code>max-height</code> nem <code>overflow</code>: se o conteúdo crescesse, ele
    sairia da tela <b>sem barra de rolagem e sem aviso</b>. Agora o teto é
    <code>min(717px, 100vh − 40px)</code> — os 757px da janela menos 20px de respiro
    de cada lado — e <b>quem rola é o corpo</b>, não a caixa, para o título e o
    <i>Guardar</i> nunca saírem de vista. <b>Mordida:</b> com o teto forçado a 400px
    o corpo passa a rolar (568px de conteúdo em 308px de vão) e o rodapé continua
    visível; com a cura arrancada, nada rola.</li>
    <li><b>O "Voltar ao padrão" da fileira voltou a fazer o que o nome diz.</b> A
    frase dele era <i>"Apagar as {len(BOTOES)} linhas das duas tabelas…"</i>, e com
    as tabelas em telas separadas <b>"as duas tabelas" deixou de ser o que este
    botão alcança</b>. Cada tela ganhou o seu <i>Voltar ao padrão</i>, que zera só a
    tabela dela e diz o que <b>não</b> toca; o da fileira devolve a <b>aba
    inteira</b> — ativação, os {len(COMBOS)} gestos e as duas telas.</li>
    <li><b>A régua desta casa não mede pop-up — e a primeira que eu escrevi também
    não mediu.</b> A <code>regua.py</code> carrega o arquivo <b>sem fragmento</b> e a
    <code>regua_estados.py</code> varre só <code>.miolo, .miolo *</code>; a
    <code>.tela-nova</code> é <code>position:fixed</code>, fora do miolo. As duas
    pop-ups que já existiam <b>nunca tinham sido medidas</b>. E a minha primeira
    régua de botão usava <code>scrollWidth &gt; clientWidth</code>: ela deu
    <b>verde</b> na mordida, porque o <code>.btn</code> é <code>inline-flex</code>
    sem <code>nowrap</code> — o texto que não cabe <b>quebra em duas linhas</b>
    dentro de uma caixa de 34px, e o <code>scrollWidth</code> nem se mexe. Quem
    morde é o <b>número de linhas</b>, por <code>Range.getClientRects()</code>.</li>
    <li><b>Uma afirmação do enunciado caiu.</b> Estava escrito que
    <i>"Configurar o estilo Point-and-click" vai estourar</i> nos 261,8px de quatro
    botões. <b>Não estoura.</b> Medido nas três fontes que a página pode acabar
    usando: o texto pede <b>207,6px</b> com a Space Grotesk, <b>198,3px</b> com o
    <code>system-ui</code> e <b>210,8px</b> com a DejaVu Sans, contra os
    <b>233px</b> que a caixa oferece — uma linha só nos três casos, com 22px de
    folga no pior deles. O rótulo <b>ficou como ela o aprovou</b>; encurtá-lo teria
    sido mudança que ninguém pediu, por um defeito que não existe.</li>
  </ul>

  <h2>A rodada dos quatro controles</h2>
  <ul>
    <li><b>A coluna do desenho virou a mesa.</b> Onde havia <b>um</b> DualSense
    Cosmic Red há agora os <b>{len(MESA)}</b> da <code>MESA</code> do
    <code>monta.py</code> — {", ".join(c["nome"] for c in MESA)} —, cada um com a
    borda e o casco na cor do seu plástico e a barra de luz na cor automática do
    número dele. Nada disso é digitado: o plástico vem de
    <code>cor_da_zona()</code> (que lê o que
    <code>gerar_cores_do_dualsense.py</code> escreveu no SVG) e a cor da luz de
    <code>player_slot_color</code>. <b>As cinco lâmpadas do jogador não estão
    aqui</b> — decisão dela, 28/08: elas saem dos desenhos pequenos e ficam só
    nos grandes, da Iluminação. Neste cartão mediam 1,90 × 0,64 px.</li>
    <li><b>O <code>#ff2d6f</code> saiu — e ele nunca tinha pintado nada.</b> O
    <code>luz=</code> desta aba escrevia uma variável CSS que <b>nenhuma regra
    lia</b>: a barra de luz ficava cinza nas dez abas. Agora a regra existe
    (<code>.nav-ctl [id$="-lightbar"] .peca</code>) e a cor vem do produto.</li>
    <li><b>Os símbolos desenhados à mão acabaram.</b> O dropdown de remapeamento
    dizia <i>Cross ✕</i>, <i>Circle ○</i>, <i>Square □</i>, <i>Triangle △</i> e
    <i>D-pad ↑</i> com o caractere solto. As cinco famílias saem agora da coluna
    <code>regiao</code> de <code>docs/data/pecas-do-dualsense.csv</code>, com o
    nome de cada peça vindo do mapa: <b>Triângulo, Círculo, Quadrado, Cruz</b>,
    <b>D-pad Cima/Direita/Baixo/Esquerda</b>, e o <b>L3</b> e o <b>R3</b> pelo
    apelido. A coluna de nome ao lado de cada glifo era um dicionário escrito na
    aba; virou consulta ao mapa. As três regiões do touchpad saem da
    <code>nota</code> da peça, que é a única linha do projeto que as declara.</li>
    <li><b>As listas desta aba estavam em duas alturas, e nenhuma era a da casa.</b>
    A coluna <i>O QUE FAZ</i> tinha <b>23px</b> e a de <i>Função do teclado</i>
    <b>32px</b>, na mesma tela, contra o token <code>--h-escolha</code> de
    <b>36px</b>. O censo das dez abas mostrou que toda outra aba com lista usa 36
    — Gatilhos, Conexões e Perfis — e que a Navegação era a única fora. As duas
    foram para 36, e o interruptor e os campos de número foram junto, senão a
    divergência apenas trocaria de lado dentro da mesma linha.</li>
    <li><b>A faixa morta de 69px no pé da aba fechou junto, e não por esticar
    nada.</b> Era a maior das dez (as outras nove ficam entre 18 e 36px), e o
    espaço estava sobrando porque os controles estavam pequenos: subir as listas
    ao token consumiu 51px dos 69. O resto veio de dois vãos que não eram
    ritmo — o <code>padding</code> vertical de cada linha de tabela, sobre uma
    altura já declarada, e o <code>margin-bottom</code> que deixava a moldura dos
    gestos com 6px em cima e 14px embaixo. Sobram 20px, dentro da faixa das
    outras nove. <b>O quadro não foi esticado</b>: ele cresceu porque tem mais
    dentro, que é o contrário do que ela reprovou em 27/08.</li>
    <li><b>O que foi medido e NÃO era defeito:</b> os botões <i>Confirmar</i> e
    <i>Cancelar</i> aparecem com <b>0px de altura</b> em qualquer sonda que leia
    a página parada — e devem mesmo. Eles moram no <code>.confirma</code>, que é
    <code>display:none</code> até o ponteiro entrar em <i>Voltar ao padrão</i>
    (<code>:has(.btn-padrao:hover)</code>, sem uma linha de script). Com o
    ponteiro lá, medem <b>34px</b> — o <code>--h-acao</code> — e cabem inteiros
    na tela. Régua que mede só o estado parado chama de buraco o que é a
    confirmação funcionando.</li>
  </ul>

  <h2>O que a mesa de quatro revelou, e está na tela</h2>
  <ul>
    <li><b>Mouse, teclado e os cinco gestos saem de UM controle só.</b> Com um
    controle na mesa ninguém podia ver isso. O poll loop lê o estado do controle
    <b>primário</b> (<code>daemon/lifecycle.py:4541</code>) e é esse estado que vai
    para o mouse (<code>:4744</code>), para o teclado (<code>:4754</code>) e para o
    <code>hotkey_manager.observe</code> (<code>:4757</code>); os secundários do
    co-op têm um caminho só, o do gamepad virtual
    (<code>daemon/subsystems/coop.py:1871</code>). Por isso o cartão do
    <b>Player {NAVEGA}</b> diz <i>Navega o PC</i> e os outros dizem <i>Só a
    janela</i>, e por isso o desenho que acende no combo é o dele. A
    <b>Navegação Interna</b> é a outra metade: com ela ligada, cada jogador anda
    na janela do Hefesto no seu próprio card.</li>
    <li><b>O realce do combo estava morto em três das cinco linhas.</b> A regra
    pintava <code>#nv-&lt;peça&gt; &gt; .peca</code>, e isso não alcança o
    <b>PS</b> (é <code>peca sem-tinta</code>, com <code>fill:none !important</code>,
    desde que ela mandou tirar o círculo de trás do logo) nem o <b>Options</b> (traz
    a cor no <code>style</code> inline, e style inline vence qualquer folha). Como
    o PS está nas cinco linhas, as linhas <b>1</b> (PS+Options) e <b>5</b> (PS) não
    acendiam <b>nada</b> — e a legenda desta aba afirmava o contrário. Agora o
    realce vai no <b>glifo</b> e leva <code>!important</code>; a peça
    <code>sem-tinta</code> continua sem tinta, que é o que ela pediu.</li>
    <li><b>As lâmpadas do jogador tinham DUAS metades, e uma delas era inerte.</b>
    O <code>monta.svg(jogador=…)</code> funde <code>class="led-on"</code> nas
    peças do padrão, mas quem pintava nesta aba era uma <b>lista de ids</b> que
    ela mesma montava (<code>#p1-led-jogador-3{{fill:var(--fg)}}</code>) — a classe
    estava no DOM sem uma regra que a lesse. Quem tirasse só a classe não teria
    apagado nada. Com a decisão dela de 28/08 — <b>as lâmpadas saem dos desenhos
    pequenos</b> —, saíram as duas juntas, e o grupo inteiro sai do SVG por
    <code>svg(lampadas=False)</code>, que é uma regra só para a Jogar e para
    esta.</li>
  </ul>

  <h2>A palavra dela que esta aba já cumpria, e continua cumprindo</h2>
  <ul>
    <li><b>Os {len(BOTOES)} valores das tabelas são dropdown, e nenhum está travado</b>
    — [57] <i>"todos os campos (coluna da direita das três tabelas ali, pra cada
    valor de cada linha)"</i>.</li>
    <li><b>Os grupos "Função do teclado", "Executar Comando" e "Mouse" também são
    os grupos de dentro de cada dropdown</b> — [11].</li>
    <li><b>Os cinco combos usam os SVGs da Status</b> — [51] <i>"faltou usar os
    svgs que já usamos em status"</i> — e agora acendem de verdade.</li>
    <li><b>Cabeçalho roxo nas três tabelas</b> — [90]. <b>Largura e disposição</b>
    — [57]: as tabelas têm a mesma largura, a coluna de valor começa no mesmo
    ponto, e as barras verticais dos dois blocos ficam no mesmo x.</li>
    <li><b>A fita fica apagada</b>, com o motivo certo: mouse, teclado e gestos
    saem de um controle só e o que eles fazem é do perfil (D-A-FITA-E-O-UNICO-ALVO).</li>
  </ul>

  <h2>Onde eu li a sua fala de um jeito, e pode ser o outro</h2>
  <ul>
    <li><b>"Quem navega" na coluna do desenho.</b> Pus a mesa no lugar do desenho
    único porque é lá que ela responde a pergunta da aba sem custar altura. Se você
    quiser os quatro <b>maiores</b>, eles cabem numa fileira própria — mas aí a aba
    passa da dobra, e as tabelas de baixo já estão em telas à parte por isso.</li>
    <li><b>O cartão diz "Só a janela"</b> para os outros três. É o que o produto
    faz hoje com a Navegação Interna ligada. Se você preferir que os quatro
    disputem o cursor do PC, isso é código novo no daemon, não desenho.</li>
  </ul>
</div>

</body>
</html>
'''

n = monta("06-navegacao", "Navegação", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)

# A FITA fica apagada nesta aba, mas o motivo herdado da Jogar é falso aqui: não há
# card nenhum, há 28 campos editáveis. Trocado na saída, porque o texto mora no
# esqueleto (topo.html) e esta aba só pode mexer no arquivo dela.
p = onde.pagina("06-navegacao.html")
s = p.read_text()
ANTES = 'title="Esta aba não usa o controle escolhido aqui — os cards são leitura."'
DEPOIS = ('title="Não se aplica: mouse, teclado e gestos saem de um controle só — '
          f'o do Player {NAVEGA} — e o que eles fazem é do perfil."')
if ANTES not in s:
    raise SystemExit("ERRO: o title da fita mudou no topo.html — refaça a troca")
s = s.replace(ANTES, DEPOIS)

# a tela nova entra IRMÃ da janela, fora do miolo (ver o comentário no MIOLO)
MARCA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"
if MARCA not in s:
    raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
TELAS = "\n".join(t.strip() for t in (TELA_DEFINICOES, TELA_REMAPEAMENTO, TELA_PONTO))
s = s.replace(MARCA, TELAS + "\n\n" + MARCA, 1)
onde.gravar("06-navegacao.html", s)


def _conferir(doc):
    """As decisões dela nesta aba, conferidas NA SAÍDA.

    Só o miolo, sem comentário HTML e sem o `<style>` — as três armadilhas que
    fizeram as réguas das abas irmãs reprovarem o que estava certo.
    """
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
    # 1. A MESA — dois conectados, dois lugares vazios, e os quatro cards na tela.
    exigir(corpo.count('class="nav-ctl vazia"') == len(vazios),
           f"os lugares vazios não são {len(vazios)}")
    exigir(corpo.count('class="nav-ctl') == len(MESA),
           f"a fileira não tem os {len(MESA)} lugares")
    # 2. O LUGAR VAZIO DIZ A POSIÇÃO E O ESTADO, nunca o nome do plástico.
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"o lugar do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a um lugar vazio")
    # A ORDEM SE MEDE COM `find`, E O RECORTE COM `[1:]` — nunca com `[1]`.
    # A primeira versão desta régua fazia `split(...)[1]` e ESTOUROU com
    # `IndexError` na mordida que tirava os lugares vazios: o gerador morreu e a
    # mensagem que ele devia imprimir nunca saiu. Na mordida isso é
    # indistinguível de uma régua que não pegou nada. Já tinha acontecido na aba
    # Controles hoje, com `index` em vez de `find` — mesma família, mesma cura.
    for pedaco in corpo.split('class="nav-ctl vazia"')[1:]:
        bloco = pedaco.split('class="nav-ctl', 1)[0]
        exigir("Só a janela" not in bloco and "Navega o PC" not in bloco,
               "um lugar vazio diz o que ele navega — e ele não navega nada")

    # 2-bis. A BORDA DO LUGAR VAZIO SE DECLARA INTEIRA, e não só a cor.
    #    `.nav-ctl` diz `border:1px solid var(--plastico)`, e o lugar vazio NÃO
    #    tem `--plastico`. Uma `var()` sem valor **invalida a declaração toda**:
    #    a borda não fica cinza, ela DEIXA DE EXISTIR — em silêncio, com o
    #    `border-color` que alguém escreveu ali intacto e inútil.
    #    Isto já me pegou duas vezes hoje (Controles e Gatilhos), e a mordida
    #    mostrou que nenhuma régua via. Agora vê.
    exigir(".nav-ctl.vazia{border:1px solid var(--border-forte)" in doc,
           "a borda do lugar vazio voltou a ser só COR — com `var(--plastico)` "
           "indefinido, a declaração inteira cai e o lugar fica sem caixa")
    # 3. QUEM NAVEGA ESTÁ NA MESA. Apontar o cursor para um aparelho que não está
    #    aqui é a mesma mentira que o nome do plástico num lugar vazio.
    exigir(QUEM_NAVEGA.get("conectado", True),
           f"quem navega (P{NAVEGA}) não está conectado")
    exigir(f'>P{NAVEGA} <span class="pt">•</span> {QUEM_NAVEGA["nome"]}</div>' in corpo,
           "o card de quem navega não é o do controle certo")

    if falhas:
        raise SystemExit("ERRO em 06-navegacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


_conferir(onde.pagina("06-navegacao.html").read_text())
print(f"06-navegacao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
      f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · "
      f"quem navega: P{NAVEGA} · {len(BOTOES)} botões do mapa")
