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
#: A LISTA DO PRODUTO, para a autoconferência de `_conferir` — a tela e o
#: produto têm de listar os MESMOS botões. Aqui moram a ordem e os glifos, que
#: são desenho; quais botões existem é fato, e fato tem um dono só.
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    BOTOES as _BOTOES_DO_PRODUTO,
)
#: OS BOTÕES SOBRE OS QUAIS `Profile.key_bindings` MANDA — o domínio da tela
#: "Teclas do teclado", DERIVADO pelo motor dos quatro mapas do produto
#: (`core/acoes_de_botao._dominio_do_teclado`). Digitar a lista aqui faria o
#: desenho oferecer campo de tecla em botão que o `resolver()` não lê — e a
#: escolha iria para o disco sem nunca chegar ao aparelho.
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    DOMINIO_DO_TECLADO as _DOMINIO_DO_TECLADO,
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
from monta import ressalva as _ressalva  # noqa: E402
from monta import TITULOS_DA_FITA  # noqa: E402

# O DESENHO E O PRODUTO ESCREVEM A IDENTIDADE PELA MESMA FUNÇÃO — 03/09/2026,
# IDENTIDADE-VEM-DE-CIMA. É o mesmo arranjo de `aba04.py` com
# `pacotes/a04_iluminacao.um_botao_de_player`: o dono mora no PACOTE, porque é
# ele que roda a cada tique, e o gerador o chama para desenhar a bancada. Duas
# escritas do mesmo rótulo é como o desenho e o produto divergem calados.
from pacotes.a06_navegacao import (  # noqa: E402
    ENDERECO_DA_RESSALVA,
    chips_da_fita,
    rotulo_de_quem_navega,
)

#: OS CONTROLES QUE A FITA MOSTRA. Só quem está na mesa — 31/08/2026, decisão
#: dela: um controle desconectado não se escolhe, e pôr o chip dele ali seria
#: oferecer um destino que não existe.
MESA_DA_FITA = CONECTADOS

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
     ela vem do desenho, não de uma classe por modelo.

     A BORDA É `currentColor`, E NÃO `var(--plastico)` — 03/09/2026,
     IDENTIDADE-VEM-DE-CIMA. A cor do plástico é IDENTIDADE DE APARELHO, e
     identidade vem da leitura, nunca do desenho. O piloto tem um alvo que
     escreve `style.color` (`data-hef-alvo="cor"`) e **nenhum** que escreva uma
     variável CSS: enquanto a borda lesse `--plastico`, o hex ficava cravado no
     HTML e o produto não tinha por onde trocá-lo. Com `currentColor` a borda
     passa a ser um campo que o pacote pinta a cada tique.

     O PADRÃO É O NEUTRO, e é a regra dela — *campo sem informação não mostra
     nada*: sem leitura, `color` fica em `var(--border-forte)` e a caixa é
     cinza. Nunca a cor do mockup.

     OS FILHOS NÃO HERDAM: `.nav-rot` e `.nav-est` declaram a própria cor logo
     abaixo, e é por isso que pintar o cartão não tinge o texto dele. */
  .nav-mesa{flex:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
  .nav-ctl{display:flex;flex-direction:column;justify-content:center;gap:4px;
           color:var(--border-forte);
           border:2px solid currentColor;border-radius:8px;
           background:var(--app-bg);padding:6px 5px}

  /* ---------- O LUGAR VAZIO ----------
     A mesma gramática das outras cinco abas: cor explícita e NADA de `opacity`
     (a lição medida da `.fita.inerte`). A borda se declara INTEIRA aqui, e não
     só a cor — a cicatriz é de 31/08, quando o `.nav-ctl` lia `var(--plastico)`
     e uma `var()` sem valor invalidava a declaração toda: a borda não ficava
     cinza, ela DEIXAVA DE EXISTIR. Medido na aba Controles no mesmo dia, com a
     foto mostrando dois lugares soltos, sem caixa nenhuma. Hoje o `.nav-ctl`
     lê `currentColor`, que nunca invalida — mas a declaração inteira FICA,
     porque é ela que impede o lugar vazio de receber a cor de um aparelho.
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

  /* AS DUAS VELOCIDADES ARRASTAM — decisão dela, 05/09/2026: *"velocidade do
     cursor e da rolagem coloca um slicer pra cada"*. O molde é o da aba
     Vibração (`aba05._trilho`), e a aparência é copiada dela de propósito:
     `appearance:none` desliga o controle nativo do WebKit — que traria a cor e
     a altura do tema do sistema para dentro de uma tela que ela aprovou — e as
     três regras abaixo reconstroem o mesmo trilho de 5px, raio 3, fundo
     `--border-forte`, com o polegar de 12px em `--purple` e borda `--panel`.

     O TRILHO É QUEM ESTICA (`flex:1 1 auto`) e o NÚMERO fica na direita, com a
     mesma trinca de 22px do `.bignum` que ele substitui: assim o campo continua
     começando e acabando no mesmo x das listas da coluna (324px), que é o
     alinhamento que ela cobrou nas outras abas. `min-width:0` é a mesma rede do
     `.par`: sem ele o mínimo automático do item de flex impediria o campo de
     encolher e ele pintaria fora da janela.

     O GRADIENTE DE PREENCHIMENTO NÃO EXISTE, e é a mesma medição da aba 05: o
     `accent-color` não pinta trilho customizado neste WebKit2, então quem
     informa a posição é o POLEGAR — que é o que ela arrasta. */
  .campo-num .trilho{appearance:none;-webkit-appearance:none;flex:1 1 auto;
    min-width:0;height:5px;padding:0;margin:0;border:0;border-radius:3px;
    background:var(--border-forte);cursor:grab}
  .campo-num .trilho:active{cursor:grabbing}
  .campo-num .trilho::-webkit-slider-runnable-track{
    height:5px;border-radius:3px;background:transparent}
  .campo-num .trilho::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;
    width:12px;height:12px;border-radius:50%;background:var(--purple);
    border:2px solid var(--panel);margin-top:-4px}
  .campo-num .trilho:focus-visible{outline:2px solid var(--purple);outline-offset:3px}
  /* O NÚMERO ao lado do trilho: mesma fonte e mesma largura do `.bignum b`, para
     as duas linhas terem a coluna do número no mesmo x uma da outra. */
  .campo-num .num{font-family:'JetBrains Mono',monospace;font-size:15px;
    color:var(--fg);font-weight:600;min-width:22px;text-align:right;flex:none;
    margin-left:11px}

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

  /* ---- O CAMPO DE TEXTO DA TELA "Teclas do teclado" ----
     Ele herda a forma do `.campo-linha` (a mesma altura, a mesma borda, o mesmo
     raio) porque é a mesma linha de tabela — o que muda é o CURSOR: `text`, e
     não `pointer`. Um campo que se pode digitar com o cursor de clique parece
     um botão, e ela clicaria esperando uma lista.
     A FONTE É A DA CASA e não a monoespaçada: o que se escreve aqui é
     `Alt + Tab`, não `KEY_LEFTALT+KEY_TAB` — o token cru é do produto, e quem
     traduz é `input_actions`. */
  .tecla{width:100%;height:var(--h-escolha);border-radius:6px;font-size:11.5px;
    font-family:inherit;padding:0 8px;border:1px solid var(--border-forte);
    background:var(--panel);color:var(--fg);cursor:text}
  .tecla:hover{border-color:var(--purple)}
  .tecla:focus{outline:none;border-color:var(--purple);background:var(--sel-bg)}
  .tecla::placeholder{color:var(--comment)}
  /* A TERCEIRA COLUNA É SÓ O ↺, e ela tem largura fixa para o campo de texto
     ficar com o resto. Sem isto o `table-layout:fixed` divide as três em três
     partes iguais e o ↺ ganha 200px de coluna vazia. */
  .tab-teclas td.re,.tab-teclas th:last-child{width:34px;padding-right:0}
  .re-tecla{display:inline-flex;align-items:center;justify-content:center;
    width:26px;height:26px;border-radius:6px;text-decoration:none;font-size:14px;
    color:var(--texto-suave);border:1px solid transparent}
  .re-tecla:hover{color:var(--fg);border-color:var(--purple);background:var(--sel-bg)}
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

  /* as linhas de estado ficam no MESMO y: altura fixa e fundo da coluna */
  .estado{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--texto-mudo)}
  .estado .verde{color:var(--green)} .estado .laranja{color:var(--orange)}
  .estado .valor{color:var(--fg);font-weight:600}

  /* AS TRÊS LINHAS DE ESTADO NASCEM VAZIAS, E É REGRA DELA — 30/08/2026:
     *"se não tá mostrando agora, não tem info pra mostrar no produto; mas
     quando tiver, aparece a info correta"*. Elas são o que a GTK mostra e esta
     aba calava — a dica do quadro Navegação já cita "a linha de estado abaixo"
     desde 27/08, e até hoje a linha que ela cita não existia.

     NA MESMA FILEIRA, e a razão é medida: a aba já ocupa quase toda a altura da
     janela (757px), e três linhas empilhadas empurraram a fileira dos botões
     para FORA da tela — visto na foto de 03/09, com o "Definições Controle e
     Mouse" cortado pelo rodapé. Em fileira com `wrap` elas custam uma linha
     quando cabem, e só quebram quando a frase é longa (a de "não há teclado na
     tela instalado", que é justamente a que precisa de espaço).

     O `.nada` É COMO UMA LINHA SOME, e não o `:empty`: o `escrever()` do piloto
     troca valor vazio por `—` (`hefesto_vivo.py:141`), então uma frase vazia
     viraria um travessão solto na tela dela — foi o que a primeira foto
     mostrou. O pacote manda o marcador, e o `:has()` apaga a linha inteira.
     Emitir a chave sempre (em vez de omiti-la quando não há o que dizer) é o
     que faz a linha SUMIR quando o bloqueio acaba; chave ausente deixaria a
     frase velha na tela para sempre. O `:has()` já é usado nesta folha
     (`.at-linha:has(.btn)`), então não é aposta nova sobre o WebKit dela. */
  .estados{display:flex;flex-wrap:wrap;align-items:center;gap:3px 22px;padding:2px 0 0}
  .estados:empty{display:none}
  .estado:empty{display:none}
  .estado:has(.nada){display:none}
  /* `<tt>` vem das frases do produto (`frase_do_teclado_na_tela` nomeia os dois
     pacotes de teclado na tela dentro de um). A fonte é a MESMA que o resto da
     página usa para código — não uma segunda escolha inventada aqui. */
  .estado tt{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px}

  /* ---- O STATUS DO MODO (27/08, ela: "Status do Modo: ao clicar no botão
          Ligado. Ao clicar nele de novo desligado.") — o dono do que os dois
          botões suspensos faziam embaixo.

          A COR SAI DE UMA CLASSE, e não mais do `:checked` de um input —
          03/09/2026. O desenho nascia `<input checked>`, a palavra saía de um
          `content:` de CSS, e o produto não tinha por onde escrever nenhum dos
          dois: a tela dizia **Ligado** com `mouse_emulation.enabled=false` no
          daemon dela. Pior, clicar no `<label>` virava a caixa no DOM mesmo
          quando o gesto RECUSAVA — a tela trocava de lado sozinha e nada a
          devolvia.

          O piloto ganhou o alvo `classe` em 02/09 (`hefesto_vivo.py:227`), e é
          ele quem acende agora; a palavra virou nó de texto, que o alvo padrão
          escreve. Nasce em `—` de propósito: antes do primeiro tique ninguém
          perguntou ao Hefesto, e "Desligado" seria uma afirmação. ---- */
  .tog{display:flex;align-items:center;gap:9px;width:100%;height:var(--h-escolha);border-radius:7px;
       font-size:12px;padding:0 12px;border:1px solid var(--border-forte);
       background:var(--app-bg);color:var(--texto-mudo);cursor:pointer;user-select:none}
  .tog:hover{border-color:var(--comment)}
  .tog .pino{width:9px;height:9px;border-radius:50%;background:var(--border-forte);flex:0 0 9px}
  .tog.ligado{border-color:var(--green);background:rgba(80,250,123,.1);
       color:var(--fg);font-weight:600}
  .tog.ligado .pino{background:var(--green);box-shadow:0 0 7px var(--green)}

  /* ---------- O PORTÃO DE MODO APAGA O INTERRUPTOR (D-03 + D-02) ----------
     Decisão do PO, 04/09/2026 (`2026-09-04-O-PO-DECIDE` §2 `06[01]`):
     *"Apaga o interruptor e escreve ao lado, na tira de estados."* A janela
     antiga já faz isso desde sempre (`mouse_actions._sync_mouse_mode_gate`,
     `blocked = mode != MODE_DESKTOP`); o que faltava aqui era o MOMENTO — a
     tela aceitava o clique e recusava depois, e ela gastava o clique para
     descobrir.

     UM CAMPO SÓ, E NENHUM SEGUNDO ENDEREÇO: a razão é escrita numa linha só
     (`data-campo="modo-portao"`, na tira de estados), e o cinza do interruptor
     SAI DELA por `:has()`. Com dois campos seria possível pintar um interruptor
     apagado sem razão, ou uma razão sem interruptor apagado — que é exatamente
     o que a peça `monta.botao_cinza` evita do outro lado, e pela mesma regra.
     Aqui não dá para usar aquela peça: ela emite um `.btn`, e o "Status do
     Modo" é o rótulo `.tog` que ela pediu em 27/08.

     E A MARCAÇÃO NÃO SE ESCREVE NUM COMENTÁRIO DE CSS: a primeira redação deste
     bloco citava a tag do rótulo por extenso, e a citação SAIU NA PÁGINA — o
     `<style>` vem antes do corpo, e `test_o_interruptor_tem_os_dois_enderecos`
     achou a citação em vez do elemento. É a irmã da armadilha do
     `# noqa-acento` (menção em prosa, não válvula: nada aqui pede escape) que
     virou título visível: o que se escreve num gerador chega ao arquivo.

     A GRAMÁTICA DO APAGADO É A DA CASA, letra por letra — `.btn.apagado` do
     `monta.CSS_FOLHA`: borda sutil, texto mudo, `cursor:not-allowed`. Inventar
     uma segunda cara de apagado seria a doença que esta casa persegue.

     APAGADO DIZ "NÃO DÁ PARA MEXER"; NUNCA DIZ "ESTÁ DESLIGADO" — 06/09/2026,
     esclarecimento dela na 06-Q1: *"o switch fica apagado (não clicável) MAS
     mostra o estado real: pode ficar apagado no estado off, e pode ficar
     apagado no estado on"*. Isto CORRIGE a construção de 04/09 em dois pontos,
     e os dois estavam medidos:

       · o portão pintava também o `.pino` — e a regra dele vale (0,6,0) contra
         os (0,3,0) do pino aceso, então **o pino ficava cinza com o mouse
         LIGADO**. O que sobrava dizendo o lado era o fundo esverdeado, que
         sobrevivia por acidente (a regra do portão não declara `background`).
         Um lado inteiro dito por uma declaração que ninguém escreveu de
         propósito. A regra do pino SAIU: o lado sai de onde sempre saiu, e
         passa a valer também sob o portão;
       · o interruptor CONTINUAVA respondendo ao clique — este mesmo comentário
         dizia, por escrito, que *"nada aqui é `disabled` nem
         `pointer-events:none`"*, e ela pediu **não clicável**. Agora é.

     E O `cursor:not-allowed` MUDOU DE ELEMENTO, porque tinha de mudar: um
     elemento que não é alvo de ponteiro **não decide o cursor** — quem decide
     passa a ser o pai. Aplicar só a primeira metade trocaria um defeito por
     outro (recusa em silêncio, com cara de clicável), então a recusa mora na
     linha que contém o interruptor, na mesma regra `:has()`.

     O GESTO `modo` NÃO PERDE A RECUSA, e é de propósito:
     `a06_navegacao` continua levantando a `RAZAO_DO_PORTAO`. A folha protege o
     ponteiro; a página pode estar pintada com o modo de um tique atrás, e
     tirar a guarda do Python deixaria o único caminho aberto sem ninguém.

     O `.laranja` É O GATILHO, e não uma classe nova: o pacote manda a razão
     dentro de um `<span class="laranja">`, como as outras linhas de estado
     fazem, e manda `<i class="nada"></i>` quando não há bloqueio — que é o
     mesmo marcador que apaga a linha. Sem bloqueio não há `.laranja` naquela
     linha, e o interruptor fica como sempre foi. ---------- */
  .quadro-corpo:has(.estado.portao .laranja) .at-linha:has(.tog[data-gesto="modo"]){
       cursor:not-allowed}
  .quadro-corpo:has(.estado.portao .laranja) .tog[data-gesto="modo"]{
       border-color:var(--border-sutil);color:var(--texto-mudo);pointer-events:none}
  .quadro-corpo:has(.estado.portao .laranja) .tog[data-gesto="modo"]:hover{
       border-color:var(--border-sutil)}

  /* ---------- A TIRA DE AVISO SOB A TABELA DE BOTÕES ----------
     Decisão do PO, 04/09/2026 (§2 `06[04]`): *"Uma tira de aviso sob a tabela.
     O que vai ser APAGADO não mora num hover."*

     Ela nasce VAZIA e não ocupa nada: `:empty` no desenho, `.nada` quando o
     pacote diz que não há o que dizer — as duas metades, como a tira de estados
     já faz, porque a linha some por dois caminhos diferentes (nunca pintada, e
     pintada com "nada"). ---------- */
  .aviso-tabela{margin-top:8px;display:flex;flex-direction:column;gap:4px;
       font-size:11.5px;line-height:1.45;color:var(--texto-mudo)}
  .aviso-tabela:empty{display:none}
  .aviso-tabela:has(.nada){display:none}
  .aviso-tabela b{color:var(--texto-suave);font-weight:600}

  /* ---------- A MARCA DE "NÃO DISPARA" NA COLUNA DO NOME ----------
     Decisão do PO, 04/09/2026 (§2 `06[02]`): as três regiões do touchpad
     **ficam** — é a D-15 dela, *"pedi pra tirar o texto não o touch mostrando
     os toques"* — **com a marca de que não disparam**. A marca nasce FIXA: a
     marca VIVA (que acende só quando o touchpad é o ponteiro do sistema)
     espera o daemon publicar esse dado, e isso é sprint própria.

     Ela cabe na coluna do nome e não custa linha nenhuma, que é o que a decisão
     pede. O texto inteiro está no `title` e no `?` da tela. ---------- */
  .marca-nao-dispara{margin-left:7px;padding:0 5px;border-radius:4px;
       border:1px solid var(--border-sutil);color:var(--texto-mudo);
       font-size:9.5px;line-height:14px;display:inline-block;white-space:nowrap;
       cursor:help}
  /* A COLUNA DO NOME CRESCE **SÓ DENTRO DAS POP-UPS**, e o número é medido, não
     escolhido: a decisão do PO diz que a marca *"cabe na coluna do nome"*, e ela
     NÃO cabia — `.tab td.b` tem `width:176px`, `white-space:nowrap` e
     `overflow:hidden`, e a linha mais longa das vinte e duas ("Touchpad · Clique
     esquerdo") já usa ~168px. Fotografado em 04/09/2026: a marca saía cortada,
     com dois caracteres à mostra por baixo do `<select>` vizinho.

     Quando o instrumento e o aparelho discordam, o aparelho ganha: a marca é a
     decisão, e o que cede é o número. 250px deixam ~350px para a segunda
     coluna, que é mais do que a maior opção da lista pede ("Abrir e fechar o
     teclado na tela", ~200px).

     `.tn-cx` ESCOPA A REGRA: as tabelas da ABA (os cinco combos) continuam com
     os 176px que ela aprovou — lá não há marca nenhuma a caber. */
  .tn-cx .tab th:first-child,.tn-cx .tab td.b{width:250px}

  /* A DENSIDADE DE 22px FICA SÓ DENTRO DAS TELAS DE CIMA, e o número diz por quê.
     Cada uma das duas telas de botões tem uma lista por linha, e a caixa mede
     657px com elas a 22px — REMEDIDO em 06/09/2026, com a 22ª linha (o botão
     PS): eram 634px com 21. No token de 36 as linhas sozinhas passariam de
     750px, e a janela do produto tem 757. A tela não caberia na tela.
     Na ABA, onde há cinco linhas e não vinte e duas, o token vale: veja
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

    O `gesto` NOMEIA o campo para o piloto (ver `simples`), e é o que faz o
    `change` chegar ao Python.

    FATO SUBSTITUÍDO (02/09/2026, segunda correção): aqui estava escrito que
    *"as listas das três telas de pop-up ficam SEM `data-gesto` de propósito —
    elas são os CAMPOS de um formulário cujo ponto de gravação é o Guardar"*. A
    primeira metade caducou com a decisão dela de 02/09 (*"as 21 listas param de
    ser repintadas enquanto ela está mexendo"*): sem nome, o `change` de uma
    linha **não chega ao Python** — o `closest` do ouvinte
    (`hefesto_vivo.py:367`) não conhece `data-campo` nem `data-linha` —, e sem
    ele o pacote não tem como saber que ela está mexendo. As 21 linhas de *o que
    cada botão faz* passaram a levar `gesto=LINHA_DE_BOTAO`. A segunda metade
    continua de pé: **o ponto de gravação é o "Guardar"**, e este gesto não
    grava nada.

    As duas outras telas continuam sem `gesto` **e** sem `campo`, e é a mesma
    razão de sempre: os "Guardar" delas não têm dono no produto.

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


def simples(ops, classe="escolha-at", gesto="", campo="", escolhido=""):
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

    O `escolhido` NASCEU EM 02/09/2026, e a razão é a decisão dela sobre a
    "Função do teclado": as três opções passaram a ser `Só dentro do jogo` ·
    `Só fora do jogo` · `Desativado`, e **o padrão é a do meio**. Sem este
    argumento a lista nasceria marcada na PRIMEIRA — que é justamente a única
    das três sem dono no produto. Uma tela que nasce mostrando a opção que o
    produto não sabe fazer promete o que não entrega nos 100 ms anteriores ao
    primeiro tique (`hefesto_vivo.TIQUE_MS`).
    """
    g = f' data-gesto="{gesto}"' if gesto else ""
    c = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    marcada = escolhido if escolhido else (ops[0] if ops else "")
    if escolhido and escolhido not in ops:
        raise SystemExit(f"ERRO: a opção padrão {escolhido!r} não está na lista {ops}")
    op = "".join(f'<option{" selected" if o == marcada else ""}>{o}</option>' for o in ops)
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


def trilho(valor, minimo, maximo, gesto, campo, titulo):
    """Uma velocidade como barra arrastável, com o número ao lado.

    DECISÃO DELA, 05/09/2026: *"velocidade do cursor e da rolagem coloca um
    slicer pra cada"*. Ela substitui o :func:`bignum` de `−`/`+` nas duas linhas
    das "opções de ativação" — e o par de botões saiu junto com os quatro gestos
    de passo que o atendiam, para não deixar endereço sem campo na página.

    OS TRÊS NÚMEROS SÃO LIDOS, NUNCA DIGITADOS. `min`/`max` vêm de
    `integrations/uinput_mouse.py` — o mesmo módulo de onde `set_speed` tira a
    faixa com que apara — e `step` é 1 porque as duas velocidades são INTEIRAS
    dos dois lados (o `GtkAdjustment` da janela estável usa `step-increment` 1,
    `main.glade:79` e `:87`). Digitar `1..12` aqui seria a segunda verdade que
    esta casa persegue.

    O ENDEREÇO É UM SÓ para o trilho e para o número, e é de propósito: os dois
    mostram o MESMO inteiro, na mesma unidade. O piloto escreve um valor escalar
    em TODOS os elementos de mesmo `data-campo` (`hefesto_vivo.pintar`), e cada
    um decide como o mostra pelo `data-hef-alvo` — o `<input>` no `value`, o
    `<b>` no texto. É o contrário do par `forca`/`forca-pct` da aba Vibração, que
    precisa de dois nomes porque ali a barra fala em porcentagem e o número não.

    O `data-gesto` VIVE NO `<input>`, e não na linha: um `<div>` de fora não tem
    `value`, e o ouvinte do piloto manda `valor: alvo.value ?? ''`. Foi este o
    defeito que a aba 05 nomeou em 03/09 antes de o trilho dela virar `<input>`.
    """
    return (f'<div class="campo-num">'
            f'<input class="trilho" type="range" min="{minimo}" max="{maximo}"'
            f' step="1" value="{valor}" data-gesto="{gesto}"'
            f' data-campo="{campo}" data-hef-alvo="valor" title="{titulo}">'
            f'<span class="num" data-campo="{campo}">{valor}</span></div>')


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


# ---------------------------------------------------------------------------
# A FOLHA DOS 28 MODELOS, PUBLICADA UMA VEZ — 03/09/2026, A-COR-VEM-DO-APARELHO
#
# A LEI É DELA: *"imagina que cada pessoa tenha um dualsense diferente. eu
# mapeei as cores, glifos, controles, id e tudo mais. É pro projeto usar esse
# meu trabalho (…) nada hardcoded."*  (noqa-acento: citação literal dela)
#
# O QUE ESTAVA ERRADO NESTA ABA: o `monta._so_o_colorway` PODA a folha embutida
# em cada SVG e guarda só as regras do modelo pedido — 3.082 bytes dos 45.452
# dos 28. Cada um dos quatro cartões carregava, portanto, UM modelo: o do
# desenho. Um SVG assim não tem como virar outro aparelho, e escrever nele o
# colorway lido do controle dela daria o cinza cru do `ds_limpo.svg`
# (`rgb(58, 63, 75)`), não a cor dela.
#
# A CURA É PUBLICAR A TABELA, e é o que o `mapa-do-controle.html` já faz: a
# folha inteira UMA vez na página, e os quatro SVGs escolhem por seletor. Aí o
# `data-colorway` de cada desenho pode ser QUALQUER um dos 28 — que é a lei.
#
# NÃO É TABELA NOVA: o texto sai do `<style id="cores-do-dualsense-folha">` que
# `scripts/gerar_cores_do_dualsense.py` escreveu dentro do `ds_limpo.svg`, a
# partir de `docs/data/cores-do-dualsense.csv`. Digitar um hex aqui seria a
# segunda verdade que o `check_cores_do_dualsense.py` existe para matar.
#
# O PREÇO, MEDIDO: a página troca 4 cópias podadas (12,3 KB) por uma folha
# completa (45,5 KB) — +33 KB numa página de 400 KB, e o CSS das cores passa a
# existir em UM lugar só em vez de quatro.
_FOLHA_NO_SVG = re.compile(
    r'<style id="[^"]*cores-do-dualsense-folha">.*?</style>', re.S)


def folha_das_cores():
    """As 28 cores do mapa, tiradas do SVG que o gerador de cores pinta."""
    m = _FOLHA_NO_SVG.search(DS)
    if not m:
        raise SystemExit(
            "ERRO em 06-navegacao: o `<style id=\"cores-do-dualsense-folha\">` "
            "sumiu do ds_limpo.svg — rode scripts/gerar_cores_do_dualsense.py")
    return m.group(0)


CSS += "\n  /* ---- as 28 cores do mapa, publicadas UMA vez ---- */\n"
CSS += re.sub(r"</?style[^>]*>", "", folha_das_cores())


# ---------------------------------------------------------------------------
# A TINTA QUE A FOLHA REFERENCIA — e sem ela DOZE dos 28 modelos dela somem
#
# DEFEITO MEDIDO NA TELA em 03/09/2026, nesta aba e só nesta: publicar a folha
# na página curou 27 modelos e QUEBROU doze. Doze dos 28 não pintam com hex —
# pintam com servidor de pintura (`url(#…)`): a hachura dos modelos que ela não
# amostrou, e os dois gradientes de casca do God of War 20th e do Spider-Man 2.
#
#   007-first-light · 30th-anniversary · chroma-indigo · chroma-pearl ·
#   chroma-teal · fortnite · genshin-impact · ghost-of-yotei ·
#   god-of-war-20th · grey-camouflage · marathon · spider-man-2
#
# Esses três `id` moram no `<defs>` do desenho, e `monta.svg()` PREFIXA todo id
# por controle — na página saíram `p1-hachura-sem-hex` … `p4-hachura-sem-hex`.
# A folha da página continuou dizendo `url(#hachura-sem-hex)`, que já não existe
# em lugar nenhum: `document.getElementById('hachura-sem-hex')` devolvia **null**
# nos três, medido no WebKit desta máquina.
#
# E REFERÊNCIA MORTA NÃO CAI NO CINZA — ela APAGA A PEÇA. Medido com
# `chroma-teal` escrito no cartão do P2: sobraram os dois gatilhos e as bolas
# dos analógicos, e o corpo do controle SUMIU da tela. Não é a cor do aparelho
# nem o neutro do "não sei": é um terceiro estado que não quer dizer nada, e é
# pior do que o congelado que esta onda veio matar.
#
# A CURA É A DA `aba05`: o `<defs>` sai UMA vez na página, SEM prefixo, e os
# quatro desenhos o consultam pelo id. As outras abas que publicaram a folha
# (01, 04, 05, 08) já o traziam; a 06 era a única que publicava a folha sem a
# tinta — `grep 'id="hachura-sem-hex"' mockup/*.html` mostra o buraco.
_ABRE_A_TINTA = '<defs id="cores-do-dualsense">'
if _ABRE_A_TINTA not in DS or DS.index(_ABRE_A_TINTA) > DS.index(
        '<style id="cores-do-dualsense-folha">'):
    raise SystemExit(
        "ERRO em 06-navegacao: o `<defs id=\"cores-do-dualsense\">` sumiu do "
        "ds_limpo.svg (ou passou a vir DEPOIS da folha) — os doze modelos que "
        "pintam por `url(#…)` ficariam sem tinta, e o desenho deles some da "
        "tela. Rode scripts/gerar_cores_do_dualsense.py")

#: Só os servidores de pintura, sem a folha: ela já foi para o `<style>` da
#: página, e repeti-la aqui daria duas cópias dos 45 KB.
TINTA_DOS_28 = (DS[DS.index(_ABRE_A_TINTA):
                   DS.index('<style id="cores-do-dualsense-folha">')] + "</defs>")

#: O BLOCO DA TINTA, invisível e fora do fluxo. `position:absolute` com 0×0, e
#: NÃO `display:none`: um `<defs>` em ramo escondido é caminho que já falhou em
#: motor de SVG, e aqui não há o que ganhar arriscando — este `<svg>` não
#: desenha nada, só empresta os três `id`.
#:
#: ELE VAI NO FIM DO MIOLO, E O LUGAR CUSTOU 8 PIXELS. Fora do fluxo não quer
#: dizer fora da CONTAGEM: posto no COMEÇO, ele vira o primeiro filho de
#: `.miolo`, e a regra
#:
#:     .miolo > .quadro:first-child > .quadro-corpo{padding-bottom:6px}
#:
#: deixa de casar. Medido no WebKit desta máquina, com foto antes e depois: o
#: primeiro quadro engordou de 282 para 290 px (o `padding-bottom` voltou aos
#: 14px do padrão) e **a metade de baixo da aba desceu 8 px** — 97.857 pixels
#: diferentes entre as duas fotos, com a renderização provada determinística
#: (duas corridas da MESMA página dão zero).
#:
#: A REGRA QUE ISSO DEIXA, e ela vale para toda aba que publicar a tinta:
#: `position:absolute` tira do FLUXO, não da lista de irmãos — `:first-child`,
#: `:nth-child` e `+` continuam contando o elemento. No fim do `.miolo` não há
#: o que quebrar: a página não tem uma só regra `:last-child` sobre `.quadro`
#: (são treze regras estruturais, e só a de cima olha para os filhos do miolo).
BLOCO_DA_TINTA = (
    '\n        <!-- A TINTA DOS 28 — os servidores de pintura que a folha das\n'
    '             cores pede por `url(#…)`. Sem eles, doze modelos dela viram\n'
    '             endereço morto e o desenho SOME. Ver `TINTA_DOS_28`.\n'
    '             FICA NO FIM: no começo ele quebra o `.quadro:first-child`. -->\n'
    '        <svg class="cores-do-dualsense" aria-hidden="true" focusable="false"\n'
    '             width="0" height="0" style="position:absolute;overflow:hidden">'
    f'{TINTA_DOS_28}</svg>\n')


def tinta_referenciada():
    """Os `id` que a folha dos 28 pede por `url(#…)` — lidos, nunca digitados.

    É a lista contra a qual a página se confere no fim da geração. Digitá-la
    aqui faria a régua envelhecer sozinha no dia em que ela mandar amostrar mais
    um modelo e um gradiente novo nascer.
    """
    return sorted(set(re.findall(r"url\(#([^)]+)\)", folha_das_cores())))


def zonas_do_desenho():
    """As classes de zona, LIDAS da folha do mapa — nunca digitadas aqui."""
    zonas = sorted(set(re.findall(
        r'svg\[data-colorway="[^"]+"\] (\.z-[a-z0-9_]+)', DS)))
    if not zonas:
        raise SystemExit("ERRO em 06-navegacao: a folha do mapa não declara "
                         "mais zona nenhuma — veja ds_limpo.svg")
    return zonas


# ---------------------------------------------------------------------------
# SEM COLORWAY, SEM COR DE APARELHO — e sem esta regra a ausência de leitura
# mostrava VERMELHO. Medido em 03/09/2026 com `hefesto_vivo --sem-cor`:
# apagado o `data-colorway`, nenhuma regra da folha casa e o desenho cai nos
# `fill` crus do `ds_limpo.svg` — que incluem DOIS `#b11f54`, o Cosmic Red
# VELHO e errado (a amostragem de 27/08 devolveu `#A51C48`; ver a nota em
# `monta.monta` sobre as variáveis do esqueleto). O Share, o Options e as duas
# bolas dos analógicos ficavam carmim num controle que ninguém identificou —
# exatamente a queixa dela: *"os svgs não são os que o meu mapa cataloga"*.
#
# A REGRA É POR AUSÊNCIA DE ATRIBUTO, e não por classe do cartão: quem decide é
# o mesmo fato que decide a cor — o produto leu, ou não leu. `.nav-ctl.vazia`
# continua valendo para o lugar VAZIO na bancada, que nasce com o colorway do
# desenho e só o perde no primeiro tique.
#
# SÓ AS ZONAS, e elas vêm do mapa (`zonas_do_desenho`): zona é o que muda de um
# modelo para outro, logo é o que carrega identidade. O contorno, os glifos e a
# barra de luz do jogador ficam — apagá-los transformaria o desenho num vulto,
# e a luz do jogador nem é cor de plástico (a folha do mapa a exclui de
# propósito: *"a cor de plástico nunca pinta a LUZ"*).
CSS += "\n  /* ---- desenho sem identidade: as zonas ficam no neutro ---- */\n"
CSS += "".join(
    f'  .nav-ctl .ds-svg:not([data-colorway]) {z}'
    f' :is(path,rect,circle,ellipse,polygon):not([fill="none"])'
    f"{{fill:var(--border-forte) !important}}\n"
    for z in zonas_do_desenho())


#: OS TRÊS ATRIBUTOS QUE FAZEM O DESENHO SEGUIR O APARELHO — o contrato do alvo
#: `atributo` do piloto (`hefesto_vivo.escrever`, ramo `atributo`). O nome do
#: atributo vai em `data-hef-atributo`, SEPARADO do alvo: `regua_do_mockup`, o
#: `LER_CAMPOS` e cada `campo.alvo == "…"` comparam o alvo por IGUALDADE, e um
#: alvo composto (`atributo:data-colorway`) viraria uma palavra diferente por
#: atributo. É a mesma forma que o alvo `classe` já usa com `data-hef-classe`.
ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo"'
                       ' data-hef-atributo="data-colorway"')


def desenho(c, **kw):
    """O DualSense do cartão, ENDEREÇADO e sem a folha podada dentro.

    Duas coisas, e as duas são a mesma cura vista de lados opostos:

    * a folha embutida SAI. Ela traz um modelo só, e a página já publica os 28
      (ver `folha_das_cores`). Mantê-la seria a mesma tabela quatro vezes, e a
      podada é justamente a que impede o desenho de virar outro aparelho;
    * o `<svg>` ganha `ENDERECO_DO_DESENHO`. Sem ele o `data-colorway` fica
      sendo o do MOCKUP para sempre — era o defeito que ela nomeou: *"é white
      no p1, mas (…) os svgs não são os que o meu mapa cataloga"*.

    AS DUAS ÂNCORAS PARAM A GERAÇÃO se sumirem. Uma `str.replace` que não casa
    devolve o texto intacto e não avisa — foi assim que a fita viva morreu em
    silêncio nesta casa, e é o que esta função recusa repetir.
    """
    x = svg(c["pref"], c["cor"], classes="ds-svg", lampadas=False, **kw)
    if not _FOLHA_NO_SVG.search(x):
        raise SystemExit(
            f"ERRO em 06-navegacao: o svg({c['pref']!r}) não traz mais a folha "
            f"podada — quem a tirou tem de conferir se a página ainda publica "
            f"os 28 modelos")
    x = _FOLHA_NO_SVG.sub("", x, count=1)
    if "<svg " not in x:
        raise SystemExit(f"ERRO em 06-navegacao: svg({c['pref']!r}) não abre "
                         f"com `<svg ` — o endereço não tem onde entrar")
    return x.replace("<svg ", f"<svg {ENDERECO_DO_DESENHO} ", 1)


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

    O DESENHO DAQUI TAMBÉM É ENDEREÇADO, e não é enfeite: o piloto distribui uma
    LISTA pelos elementos de mesmo `data-campo`, NA ORDEM do HTML
    (`hefesto_vivo`, `alvos.forEach(…, i)`). Um lugar vazio sem endereço tiraria
    uma casa da fila e o P4 receberia a cor do P3. O valor que ele recebe é `""`,
    que APAGA o `data-colorway` — e o desenho cai no neutro que as regras
    `.nav-ctl.vazia .ds-svg` já pintam.

    O `data-controle` FICA AQUI TAMBÉM — decisão dela, 03/09/2026, e ela a
    enunciou assim: *"tem que aparecer desligado enquanto não tem nenhum
    controle. A partir do momento que tiver, ele aparece o controle devidamente
    conectado. Se isso não ocorre com os 4 controles em cada aba, então temos
    que construir isso e garantir isso."*

    SEM O ENDEREÇO O LUGAR VAZIO É VAZIO SÓ PORQUE O DESENHO O DESENHOU VAZIO.
    Medido no DOM vivo desta aba em 03/09, antes desta linha:
    ``[data-controle="p3"]`` devolvia **zero elementos** — a coluna estava na
    tela, com o desenho e o rótulo "P3 · Desconectado", e o produto não tinha
    por onde escrever nela quando o terceiro controle chegasse.

    A ``05-vibracao`` já fazia certo, e o comentário dela dizia a mesma coisa.
    Esta linha é a cópia daquela decisão para as abas que ficaram para trás.
    """
    n = c["jogador"]
    return (
        f'              <div class="nav-ctl vazia" data-controle="{c["pref"]}"'
        f' data-conectado="nao"'
        f' data-campo="plastico" data-hef-alvo="cor"'
        f' title="Nenhum controle neste lugar.">\n'
        f'                {desenho(c)}\n'
        f'                <div class="nav-rot">P{n} <span class="pt">•</span> Desconectado</div>\n'
        f'                <div class="nav-est">{VAZIO}</div>\n'
        f'              </div>')


def controle(c):
    """Um dos quatro da mesa: o desenho na cor do plástico, o rótulo na ordem
    dela (player • plástico • transporte) e o que ele navega agora.

    A IDENTIDADE DESTE CARTÃO VEM DE CIMA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA.
    Três coisas mudaram aqui, e as três eram o desenho mandando na tela:

    * a cor do plástico saiu do `style="--plastico:#hex"` e virou
      `style="color:#hex"` com `data-campo="plastico" data-hef-alvo="cor"`. É o
      ÚNICO canal de cor que o piloto tem (`hefesto_vivo.escrever`, ramo
      `cor`), e ele escreve `style.color` — que a borda passou a ler por
      `currentColor`. Sem leitura, a cor volta ao neutro do CSS;
    * o `title` que dizia `Player 1 • Cosmic Red • USB` SAIU. Ele repetia o que
      o cartão já mostra em texto, e um `title` não tem alvo de pintura: ficaria
      nomeando o controle do mockup para sempre, por cima do rótulo já vivo;
    * o nome do plástico virou `<span data-campo="identidade">`, que o pacote
      escreve com `pacotes.identidade_de` — o dono do nome desde a ROTA-A. O
      `P{n}` fica FORA do span de propósito: o número do jogador é ESTRUTURA
      (a posição na mesa), e a lei do dia diz para não tocá-lo.

    E O DESENHO SEGUIU — 03/09/2026, A-COR-VEM-DO-APARELHO. O `<svg>` ganhou o
    `ENDERECO_DO_DESENHO` e perdeu a folha podada de um modelo só (ver
    `desenho`). Era a última coisa deste cartão que ainda nomeava o controle do
    mockup: com o P1 dela em White, o `<svg>` dizia `cosmic-red`.

    O PIXEL JÁ ESTAVA CERTO, E O MECANISMO NÃO — medido no WebKit em 03/09, com
    os dois controles dela na mesa: o casco do P1 saía `rgb(228, 224, 216)`,
    que é o White do mapa, porque a `a06_navegacao.folha_do_plastico`
    sobrescrevia as variáveis. Só que as REGRAS que leem essas variáveis são
    `svg[data-colorway="cosmic-red"] …`: elas casavam **porque o atributo do
    mockup tinha ficado**. Ligar o atributo — que é o que a lei dela pede —
    teria apagado a cor em vez de acertá-la, e é por isso que a página passou a
    publicar os 28 modelos no mesmo movimento.
    """
    n = c["jogador"]
    navega = n == NAVEGA
    ponto = '<span class="bolinha"></span>' if navega else ""
    return (
        f'              <div class="nav-ctl{" navega" if navega else ""}"'
        f' style="color:{cor_da_zona(c["cor"])}"'
        f' data-controle="{c.get("uniq") or c["pref"]}" data-conectado="sim"'
        f' data-campo="plastico" data-hef-alvo="cor">\n'
        f'                {desenho(c, luz=_hex(player_slot_color(n)))}\n'
        f'                <div class="nav-rot">P{n} <span class="pt">•</span> '
        f'<span data-campo="identidade">{c["nome"]}</span></div>\n'
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

#: A MARCA DAS TRÊS REGIÕES DO TOUCHPAD — decisão do PO, 04/09/2026, §2 `06[02]`:
#: *"Ficam, com a marca de que não disparam."*
#:
#: ELA NASCE FIXA, e isso é a decisão e não uma economia: a marca VIVA (que
#: acende só quando o touchpad é o ponteiro do sistema) depende de o daemon
#: publicar o `ponteiro_do_sistema` do leitor no estado — hoje ele só existe
#: dentro do daemon —, e isso é sprint própria. Está no relato desta frente.
#:
#: O TEXTO CURTO FICA NA COLUNA e o inteiro no `title`: a decisão diz, com todas
#: as letras, que a marca cabe na coluna do nome e não custa linha nova.
MARCA_DO_TOUCHPAD = (
    '<span class="marca-nao-dispara" title="O touchpad do controle continua '
    "sendo o mouse do computador nesta máquina, e enquanto for assim o Hefesto "
    "não transforma o clique dele em tecla. A escolha fica guardada no perfil e "
    'volta a valer no dia em que o touchpad deixar de ser o ponteiro.">'
    "não dispara</span>")

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
    # O BOTÃO PS — 06/09/2026, decisão dela na 06-Q3: *"O PS ganha a mesma lista
    # das outras 21 linhas; se você der uma tecla a ele, ele passa a digitar SEM
    # parar de abrir a Steam, e a tabela não avisa isso."*
    #
    # A POSIÇÃO É A DO APARELHO — depois do `create`, antes do touchpad —, e é a
    # MESMA de `core/acoes_de_botao.BOTOES`. As duas ordens não se comparam por
    # régua nenhuma hoje; o que se compara é o CONJUNTO. Manter as duas na mesma
    # ordem é o que faz a tabela e o produto se lerem em paralelo.
    #
    # ISTO REVERTE a decisão de 04/09 (*"o PS fica fora, e a razão vira dica"*),
    # e a reversão é dela. O motor chegou primeiro (ONDA5-06-01): o PS tem valor
    # de fábrica (`token_do_ps_da_maquina`), tem porta própria de resolução
    # (`acoes_de_botao.acao_do_ps`) e tem atendente (`build_ps_solo_callback`).
    # Sem aquele degrau, esta linha nasceria em `— Nada —` sobre o botão que
    # abre a Steam há meses.
    #
    # A ÚLTIMA ORAÇÃO DA FRASE DELA — *"e a tabela não avisa isso"* — é a TIRA,
    # não esta linha: quem a faz deixar de ser verdade é
    # `a06_navegacao._o_que_o_ps_faz`, pela regra da 06-Q4 (*o que se perde
    # ocupa linha; o que se explica mora no `?`*).
    #
    # ELE VEM COM O NOME AO LADO, como as outras dezessete linhas que não são
    # face nem direcional. `linha_combo` faz o CONTRÁRIO (só o glifo), e a razão
    # é dela, de 27/08: lá o PS aparece dentro de um combo — *"temos o icone do
    # PS e do lado direito PS escrito novamente, tira a parte escrita"*. Aqui
    # ele é uma LINHA, e a coluna se chama "Botão do controle": uma linha sem
    # palavra seria a única das vinte e duas que não se lê em texto.
    (gl("ps"),                                   "ps"),
    # as TRÊS regiões do touchpad ganharam linha — ela, 27/08: "o touchpad tem o
    # click pra esquerda, linha do clique direita linha do click centro".
    #
    # E ELAS GANHARAM A MARCA — 04/09/2026, decisão do PO (§2 `06[02]`) sobre a
    # D-15 dela. A escolha de OFERECÊ-LAS é dela e fica; o que a marca cura é a
    # tela PROMETER um clique que o produto não dispara. A medição:
    # `daemon/subsystems/keyboard._combine_with_touchpad:442` se cala quando o
    # touchpad é o ponteiro do sistema, e a regra de udev instalada nesta
    # máquina só esconde os touchpads VIRTUAIS — o físico do DualSense continua
    # sendo o mouse do computador.
    (gl("touchpad", rot=TOUCH_REGIOES[0]) + MARCA_DO_TOUCHPAD, "touchpad_left_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[1]) + MARCA_DO_TOUCHPAD, "touchpad_right_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[2]) + MARCA_DO_TOUCHPAD, "touchpad_middle_press"),
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
    f"Com os {len(MESA)} controles ligados, cada jogador anda no seu próprio card "
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
# A MAIOR MENTIRA DESTA ABA MORREU EM 03/09/2026, e ela era de DESENHO.
#
# O que havia aqui: `<input type="checkbox" id="st-modo" checked>` mais um
# `<label class="tog">` vazio, com a palavra saindo de
# `.tog-in:checked + .tog .txt::after{content:'Ligado'}`. Duas consequências
# medidas, as duas caladas:
#
#   1. o produto não tinha ONDE escrever. O `escrever()` do piloto cobre texto,
#      valor, largura, fundo, cor, `innerHTML` e classe — nunca o atributo
#      `checked`, e um `content:` de CSS não é nó de texto. `rato-ligado` era
#      emitido a cada tique e caía no vazio (estava em `SEM_ENDERECO`). Com
#      `mouse_emulation.enabled=false` no daemon dela, a tela dizia **Ligado**;
#   2. clicar no `<label>` virava a caixa NO DOM, porque é o que o navegador faz
#      com um rótulo ligado a um `<input>`. A tela trocava de lado mesmo quando
#      o gesto RECUSAVA — e nada a devolvia.
#
# AS DUAS SAEM COM A MESMA MUDANÇA: o `<input>` some, a cor passa a ser a classe
# `ligado` (alvo `classe` do piloto, `hefesto_vivo.py:227`, com
# `data-hef-quando` dizendo qual palavra a acende) e a palavra vira nó de texto
# no `.txt` (alvo padrão). Os dois elementos levam o MESMO `data-campo`: o
# `achar()` visita os dois com o mesmo valor e cada um decide por si — é a
# semântica que os quatro degraus da Vibração já usavam.
#
# NASCE EM `—`, e não em "Desligado": antes do primeiro tique ninguém perguntou
# ao Hefesto, e afirmar o lado desligado seria trocar uma mentira por outra. É a
# regra dela de 30/08 — *"se não tá mostrando agora, não tem info pra mostrar"*.
#
# O `data-gesto` FICA NO `<label>`: quem recebe o clique é ele, e é dele que o
# `closest()` do piloto parte. Sem `for=`, porque não há mais input a alcançar.
STATUS_MODO = ('<label class="tog" data-gesto="modo" data-campo="rato-ligado"'
               ' data-hef-alvo="classe" data-hef-classe="ligado"'
               ' data-hef-quando="Ligado">'
               '<span class="pino"></span>'
               '<span class="txt" data-campo="rato-ligado">—</span></label>')

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
#: QUEM NAVEGA, DITO NAS DUAS DICAS — e o rótulo é um CAMPO, não uma frase.
#:
#: Ele dizia `P1 Cosmic Red USB` cravado, nas duas telas. É identidade de
#: aparelho no meio de um texto de ajuda, e por isso continuava nomeando o
#: controle do desenho enquanto a fita do topo já lia o dela
#: (IDENTIDADE-VEM-DE-CIMA, 03/09/2026). O endereço é `quem-navega`, e o pacote
#: o escreve com `pacotes.identidade_de` + `pacotes.jogador_de` do PRIMÁRIO —
#: os dois donos que a ROTA-A deixou prontos.
#:
#: `data-campo` no `<b>`, e não na dica inteira: o piloto escreve
#: `textContent`, e o endereço na dica apagaria os quatro `<br>` e os `<b>` que
#: ela tem. O `<b>` é uma folha de texto puro — é o que o alvo padrão sabe
#: escrever sem destruir marcação.
VALEM_PARA = (
    'Valem para o controle que navega o PC: o <b data-campo="quem-navega">'
    + rotulo_de_quem_navega(NAVEGA, QUEM_NAVEGA["nome"], QUEM_NAVEGA["via"])
    + "</b>.")

#: AS DUAS RESPOSTAS QUE ESTA DICA DÁ:
#:
#:   · **o botão PS, e o parágrafo VIROU O CONTRÁRIO em 06/09/2026.** Ele dizia
#:     *"o botão PS não entra, e é de propósito"* — a decisão do PO de 04/09
#:     (§2 `06[03]`), que **a palavra dela reverteu** na 06-Q3: *"O PS ganha a
#:     mesma lista das outras 21 linhas; se você der uma tecla a ele, ele passa
#:     a digitar SEM parar de abrir a Steam."*
#:
#:     O QUE ELE PASSOU A DIZER é o que ela precisa saber para USAR a linha, e
#:     não por que ela falta: o PS continua sendo a saída de emergência (os
#:     cinco gestos desta aba saem dele, e segurá-lo alterna o modo jogo) **e**
#:     a tecla escolhida acontece junto. A precedência é do motor e está escrita
#:     em tabela em `daemon/subsystems/hotkey._a_metade_da_maquina`; aqui só se
#:     diz o que se vê acontecer.
#:
#:     O QUE **NÃO** ENTRA AQUI é o que se PERDE — isso ocupa linha, na tira sob
#:     a tabela (`a06_navegacao._o_que_o_ps_faz`), pela regra que a 06-Q4 fixou;
#:   · §2 `06[02]` — a frase que explica a marca das três regiões do touchpad.
#:     A marca diz *o quê*; a dica diz *por quê* e o que continua guardado.
#:
#: AS DUAS ENTRAM NO `?` E NÃO NA TELA, e é a regra dela de 30/08: *"texto na
#: interface é zero, só deixamos se for algo extremamente importante, e se for
#: de média importância vira tooltip"*. O que é importante o bastante para
#: ocupar linha é o que se PERDE, e isso mora na tira sob a tabela.
D_DEFINICOES = ajuda(
    f"As <b>{len(BOTOES)} linhas</b> de cada botão do controle: <b>o que ele faz</b> "
    "— mouse, tecla ou programa, tudo na mesma lista.<br><br>"
    "A lista de botões sai de <b>docs/data/pecas-do-dualsense.csv</b>, o mesmo mapa "
    "que nomeia as peças do desenho.<br><br>"
    "<b>O botão PS faz as duas coisas.</b> Ele continua sendo a saída de "
    f"emergência — os {len(COMBOS)} gestos desta aba saem dele, e segurá-lo "
    "alterna o modo jogo —, e a tecla que você escolher para ele acontece "
    "<b>junto</b>: no toque curto, sem combo e fora do jogo. Escolher "
    "<b>— Nada —</b> cala as duas.<br><br>"
    "<b>As três regiões do touchpad estão marcadas.</b> Enquanto o touchpad do "
    "controle for o mouse do computador, o Hefesto não transforma o clique dele "
    "em tecla — a escolha fica guardada no perfil e volta a valer no dia em que "
    "isso mudar.<br><br>"
    + VALEM_PARA)
D_REMAPEAMENTO = ajuda(
    f"As mesmas <b>{len(BOTOES)} linhas</b>, na mesma ordem, dizendo outra coisa: "
    "<b>para qual outro botão</b> cada um passa a valer.<br><br>"
    "É troca de botão por botão, e ela vale antes de o jogo ver. O que cada botão "
    "<b>faz</b> se escolhe na tela <b>Definições Controle e Mouse</b>, ao lado.<br><br>"
    + VALEM_PARA)

#: AS TRÊS PALAVRAS DA "Função do teclado", e elas são o CONTRATO do gesto.
#:
#: O `<option>` não leva `value` de propósito: `value` não está entre os
#: atributos que `scripts/check_o_desenho_aprovado.INVISIVEIS` ignora, então
#: pô-lo aqui faria toda marcação virar divergência de desenho. Sem ele, o
#: `select.value` que chega ao Python É o texto da opção — e é por isso que
#: `pacotes/a06_navegacao.py` casa por texto.
#:
#: **A MESMA LISTA ESTÁ LÁ, e a repetição é declarada**: o gesto casa pela
#: palavra que DISTINGUE (`dentro`, `fora`, `desativado`) e a pintura usa a
#: frase inteira. Quem reescrever uma opção aqui tem de abrir
#: `a06_navegacao.py` — o cabeçalho de `_ESCOLHA` diz o que muda de cada lado.
#:
#: AS TRÊS SÃO DECISÃO DELA, 02/09/2026: *"`Só dentro do jogo` · `Só fora do
#: jogo` · `Desativado`. O padrão de um perfil novo é `Só fora do jogo` — no
#: jogo o L3 é o clique do analógico e o teclado atrapalha; no desktop é onde
#: ele serve."*
#:
#: A PRIMEIRA OPÇÃO SAIU PORQUE O NOME ESTAVA ERRADO, e isto é medição e não
#: gosto: ela dizia **"Ligada — atalhos e teclado na tela"**, e "ligada"
#: afirmava um alcance que o produto NÃO tem. O daemon já cala a emulação de
#: desktop quando um jogo assume — `_jogo_no_controle_do_desktop`
#: (`daemon/lifecycle.py:2270`, a cura da queixa dela de 29/07 *"aperto r1 e ele
#: muda de app ao invés de funcionar no jogo"*) e o `gamepad_dispatched` do laço
#: (`:4780`). O que o teclado emulado faz hoje **é** "só fora do jogo": a
#: etiqueta é que mentia.
OPCOES_TECLADO = [
    "Só dentro do jogo",
    "Só fora do jogo",
    "Desativado",
]

#: A opção que a lista mostra ANTES do primeiro tique. É a que ela escolheu como
#: padrão, e é a única das três com dono no produto hoje — ver `OPCOES_TECLADO`.
TECLADO_PADRAO = OPCOES_TECLADO[1]

ATIVACAO_ESQ = [
    ("Status do Modo", D_QUANDO, STATUS_MODO),
    ("Função do teclado", D_TECLADO,
     simples(OPCOES_TECLADO, gesto="teclado", campo="teclado-estado",
             escolhido=TECLADO_PADRAO)),
    ("Navegação Interna", D_INTERNA, simples([
        "Ligada — cada controle navega o Hefesto",
        f"Só o Player {NAVEGA} navega",
        "Desligada"], gesto="navegacao-interna")),
]

# AS DUAS METADES DE CADA LINHA NÃO ERAM IRMÃS, e foi isto que a ligação mediu:
# só a da direita ("Analógico") tinha dono no produto.
#
#   · `mouse_emulation.speed`        é UM número (1..12), e o cursor do TOUCHPAD
#     sai dele: `emit_touchpad_move` escala por
#     `TOUCHPAD_SENSITIVITY * (mouse_speed / DEFAULT_MOUSE_SPEED)`
#     (`integrations/uinput_mouse.py:486`). Não há segunda velocidade a ajustar
#     — o "Touch" da tela era uma conta que ninguém faz do outro lado.
#   · `mouse_emulation.scroll_speed` é UM número (1..5) e vale só para o
#     analógico DIREITO: `_emit_scroll(rx, ry)` (`uinput_mouse.py:412`). Rolagem
#     por dois dedos no touchpad **não existe** no produto — nem uma linha.
#
# As duas metades sem dono SAÍRAM do desenho em 01/09/2026, com os rótulos e os
# quatro botões delas; sobrou um número por linha, com dono. A medição fica
# porque é ela que responde "por que uma velocidade só".
ATIVACAO_DIR = [
    # UM NÚMERO EM CADA LINHA — decisão dela, 01/09/2026: *"só ajustar o texto e
    # deixar rolagem, ajustar ali pra deixar um só se for o caso pra ambos"*.
    # O segundo número de cada par prometia um ajuste que o produto não tem, e a
    # medição está logo acima: `mouse_speed` move o touchpad E o analógico, e
    # rolagem por dois dedos não existe. Os quatro botões `−`/`+` que sobravam
    # saíram do desenho junto com os rótulos.
    #
    # E OS DOIS QUE FICARAM VIRARAM BARRA — decisão dela, 05/09/2026:
    # *"velocidade do cursor e da rolagem coloca um slicer pra cada"*. Com isso
    # os `−`/`+` sumiram das duas linhas, e com eles os quatro gestos de passo
    # (`vel-cursor-menos`/`-mais`, `rolagem-menos`/`-mais`): quem atende as
    # barras é um gesto por linha, que recebe o número inteiro em `o["valor"]`.
    # A faixa que cada barra oferece é a do DONO — ver :func:`trilho`.
    ("Velocidade de cursor", D_VEL,
     trilho(DEFAULT_MOUSE_SPEED, MOUSE_SPEED_MIN, MOUSE_SPEED_MAX,
            "vel-cursor", "vel-cursor",
            f"Arraste para escolher a velocidade do cursor — de "
            f"{MOUSE_SPEED_MIN} a {MOUSE_SPEED_MAX}. Vale na hora.")),
    ("Velocidade da rolagem", D_ROL,
     trilho(DEFAULT_SCROLL_SPEED, SCROLL_SPEED_MIN, SCROLL_SPEED_MAX,
            "vel-rolagem", "vel-rolagem",
            f"Arraste para escolher a velocidade da rolagem — de "
            f"{SCROLL_SPEED_MIN} a {SCROLL_SPEED_MAX}. Vale na hora.")),
    ("Modo Steam", D_STEAM, simples([
        "Desligado",
        "Ligado — o controle navega a Steam como num Steam Deck",
        "Ligado, e a Steam abre em Modo Jogo na próxima vez"], gesto="modo-steam")),
]

#: AS TRÊS LINHAS DE ESTADO QUE A GTK MOSTRA E ESTA ABA CALAVA — 03/09/2026.
#:
#: Nenhuma frase é escrita aqui: as três saem do PRODUTO, e é o pacote que as
#: chama (ver `a06_navegacao.LINHAS_DE_ESTADO`). O que este bloco faz é dar-lhes
#: LUGAR — que era exatamente o que faltava, e estava declarado em
#: `SEM_ENDERECO` com as três razões:
#:
#:   · `rato-estado`      "Pronto para usar como mouse" / o motivo do bloqueio,
#:                        de `app/actions/mouse_actions` (`_refresh_mouse_view`
#:                        e `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`). É a linha que
#:                        responde *por que o cursor não anda* com o
#:                        interruptor em pé — e a dica deste quadro já a citava
#:                        pelo nome ("se a linha de estado abaixo estiver
#:                        vermelha") desde 27/08, para uma linha inexistente;
#:   · `teclado-bloqueio` "Ligado, em pausa agora: …", de
#:                        `app/actions/emulation_actions.descrever_teclado_emulado`.
#:                        Separa *desligado por você* de *ligado e calado porque
#:                        um jogo assumiu* — a lista "Função do teclado" sozinha
#:                        fala da CONFIGURAÇÃO, nunca do que está acontecendo;
#:   · `teclado-osk`      "Neste computador: o teclado na tela está instalado —
#:                        o L3 abre", de
#:                        `app/actions/input_actions.frase_do_teclado_na_tela`.
#:                        Como nenhum atalho de fábrica digita letra, é a frase
#:                        que decide se existe ALGUM caminho para escrever texto
#:                        com o controle. A dica desta aba manda abrir o teclado
#:                        na tela com o L3 sem nunca dizer se há um instalado.
#:
#: O ALVO É `html` PORQUE AS FRASES DO PRODUTO TÊM MARCAÇÃO — `<b>` e `<tt>` em
#: `frase_do_teclado_na_tela`. O alvo padrão escreveria `<b>` como texto na tela
#: dela.
#:
#: VAZIAS ATÉ O HEFESTO FALAR: o `:empty` do CSS as apaga, e a fileira dos
#: botões sobe. Nenhuma das três afirma coisa alguma sobre uma máquina que
#: ninguém olhou — as próprias funções do produto devolvem `""` nesse caso.
#: E DUAS ENTRARAM NA ONDA 2 — 04/09/2026, as duas por decisão do PO e as duas
#: na MESMA tira, que é o que a decisão pede em vez de um lugar novo:
#:
#:   · `modo-portao`   §2 `06[01]`: a razão de o interruptor do "Status do Modo"
#:                     estar apagado. Ela é DUAS coisas com um endereço só — a
#:                     frase desta linha e, pela regra `:has()` da folha desta
#:                     aba, o cinza do próprio interruptor. A frase é a MESMA
#:                     que o gesto levanta ao recusar
#:                     (`a06_navegacao.RAZAO_DO_PORTAO`);
#:   · `teclado-custo` §2 `06[05]`: o que sai junto enquanto a "Função do
#:                     teclado" estiver em "Desativado". A dica `?` já dizia o
#:                     custo ANTES do ato e some com o ponteiro; a pergunta
#:                     *"por que o L3 parou de abrir o teclado?"* chega dias
#:                     depois, e nesse dia esta linha ainda está aqui.
#:
#: A ORDEM É A DA LEITURA: primeiro o que impede (o portão), depois o mouse,
#: depois o teclado. As cinco continuam se apagando sozinhas.
ESTADOS = '''
        <div class="estados">
          <div class="estado portao" data-campo="modo-portao" data-hef-alvo="html"></div>
          <div class="estado" data-campo="rato-estado" data-hef-alvo="html"></div>
          <div class="estado" data-campo="teclado-bloqueio" data-hef-alvo="html"></div>
          <div class="estado" data-campo="teclado-custo" data-hef-alvo="html"></div>
          <div class="estado" data-campo="teclado-osk" data-hef-alvo="html"></div>
        </div>'''

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
def tela_de_botoes(ident, titulo, dica, coluna, linhas, confirma, guardar, padrao,
                   fechar="", aviso="", extra=""):
    """Uma das duas telas de botões.

    Os NOMES dos gestos vêm por argumento, e desde 02/09/2026 são TRÊS: o de
    guardar, o de voltar ao de fábrica e o de FECHAR.

    FATO SUBSTITUÍDO (02/09/2026): aqui estava escrito que *"o 'Cancelar' e o
    '×' não levam nome porque funcionam: fecham a pop-up pelo `:target` do CSS.
    Marcar um botão que faz o que promete o faria aparecer no relato como 'sem
    dono'"*. Continua verdade que eles fecham sozinhos — e **deixou de ser
    verdade que fechar é tudo o que eles têm a fazer**. Com a decisão dela de
    02/09 (*"as 21 listas param de ser repintadas enquanto ela está mexendo,
    até guardar ou sair"*), FECHAR É O "SAIR": é o instante em que as escolhas
    pendentes têm de ser largadas e a tabela voltar ao que o perfil guarda.
    Sem nome, esse instante não chega ao Python e a trava ficaria presa depois
    de ela desistir. Eles não aparecem como "sem dono" porque agora TÊM dono —
    `a06_navegacao.fechar_definicoes`.

    A tela que passa `fechar=""` continua sem os nomes, e é o caso da de
    remapeamento: lá não há trava a soltar, porque o `Guardar` dela não tem
    dono no produto (ver `SEM_GESTO`).

    O `aviso` É A TIRA SOB A TABELA — 04/09/2026, decisão do PO (§2 `06[04]`).
    Só a tela de Definições a recebe, e a razão é a mesma que dá o `data-campo`
    às 21 listas de lá e não às da outra: o que a tira nomeia é o que o
    "Guardar" DESTA tela substitui, e o "Guardar" da outra não tem dono no
    produto. Uma tira que avisasse sobre um botão que não grava nada seria a
    tela inventando um risco.

    O `extra` É UM BOTÃO A MAIS NO RODAPÉ — 06/09/2026, NAVEGACAO-TECLAS-01. Só
    a tela de Definições o recebe, e ele leva à tela "Teclas do teclado". Ele
    NÃO foi para a `FILEIRA` da aba, e a razão é medida: aquela fileira já tem
    quatro botões e a classe `quatro` divide a largura por eles (261,8px cada,
    medido em 28/08) — um quinto quebraria o rótulo de todos em duas linhas
    dentro de uma caixa de 34px de altura fixa. E o lugar é este mesmo: quem
    quer trocar a TECLA de um botão está olhando a tabela de o que cada botão
    faz.
    """
    x = f' data-gesto="{fechar}"' if fechar else ""
    return f'''
<div class="tela-nova" id="{ident}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{titulo}</span>
      {dica}
      <a class="tn-x" href="#" title="Fechar"{x}>×</a>
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
{aviso}
    </div>
    <div class="tn-rod grupo-padrao">
      <a class="btn" href="#"{x}>Cancelar</a>
{extra}
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


#: O NOME DO GESTO DAS 21 LINHAS. Ele não grava nada — quem grava é o
#: "Guardar". O que ele faz é DIZER ao Python que ela está mexendo, e é o que
#: destrava a decisão dela de 02/09: *"as 21 listas param de ser repintadas
#: enquanto ela está mexendo, até guardar ou sair"*.
#:
#: SEM ELE A ESCOLHA NUNCA CHEGAVA AO PYTHON, e isto foi medido: o ouvinte do
#: piloto só reconhece um alvo que case com o `closest` de `manda_do_alvo`
#: (`hefesto_vivo.py:367` — `[data-gesto]`, `[data-modo]`, `[data-papel]`…), e
#: os 21 `<select>` tinham só `data-campo`, `data-linha` e `data-hef-alvo`.
#: O `change` morria no navegador; o tique da pintura reescrevia a escolha por
#: cima; e o "Guardar" ao lado nunca via uma forma diferente do perfil.
LINHA_DE_BOTAO = "linha-de-botao"

#: A TIRA DE AVISO SOB A TABELA — nasce VAZIA e o pacote a escreve a cada tique
#: (`a06_navegacao._aviso_da_tabela`). Decisão do PO, 04/09/2026, §2 `06[04]`:
#: *"Uma tira de aviso sob a tabela. O que vai ser APAGADO não mora num hover."*
#:
#: NENHUMA FRASE É ESCRITA AQUI, e é a mesma disciplina da tira de estados: o
#: que ela diz sai do PRODUTO — os nomes dos botões de
#: `input_actions.humanize_button`, as teclas de `humanize_binding`, e o que
#: cada linha faz de `core/acoes_de_botao`. O que este bloco faz é dar LUGAR.
#:
#: O ALVO É `html` porque as três frases levam `<b>` e vêm em `<div>` cada uma.
AVISO_DA_TABELA = ('        <div class="aviso-tabela" data-campo="aviso-da-tabela"'
                   ' data-hef-alvo="html"></div>')

TELA_DEFINICOES = tela_de_botoes(
    "definicoes-mouse", "Definições Controle e Mouse", D_DEFINICOES,
    "O que ele faz",
    chr(10).join(
        f'          <tr><td class="b">{b}</td>'
        f'<td>{drop(ACOES_UNI, _PADRAO_DOS_BOTOES[i], gesto=LINHA_DE_BOTAO, linha=i, campo=f"acao-{i}")}</td></tr>'
        for b, i in BOTOES),
    # A CONFIRMAÇÃO GANHOU A METADE QUE FALTAVA — 04/09/2026, e é o defeito §3-2
    # dito na tela. Ela dizia só *"as 21 linhas de o que cada botão faz"* e
    # **nunca usava a palavra atalhos**, sendo que o gesto zera os DOIS campos
    # do perfil (`key_bindings` e `button_actions`), direto no disco e sem
    # desfazer. Quem tivesse escrito "Ctrl + W" na janela antiga perdia isso
    # neste clique, com a pergunta falando de outra coisa.
    #
    # ZERAR OS DOIS CONTINUA SENDO O CERTO — zerar só um deixaria a tabela
    # metade de fábrica, com o botão dizendo o contrário. O que estava errado
    # era a pergunta, não o ato.
    #
    # E ELA APONTA A SAÍDA MENOR — 06/09/2026, NAVEGACAO-TECLAS-01. Este botão
    # continua sendo o "tudo ao de fábrica", e agora existe o de UMA linha
    # (o ↺ de cada linha de "Teclas do teclado"). Uma pergunta que apaga tudo
    # sem dizer que há um caminho de uma linha é a tela escondendo a opção
    # barata.
    f"Devolver ao de fábrica as {len(BOTOES)} linhas de <b>o que cada botão faz</b>? "
    "Isto apaga também os <b>atalhos de teclado</b> que este perfil guarda — "
    "inclusive os que você escreveu na janela antiga e esta lista não sabe "
    "mostrar. Para voltar <b>uma linha só</b>, use o ↺ dela em "
    "<b>Teclas do teclado</b>. O <b>Remapeamento dos botões</b> não é tocado.",
    guardar="guardar-definicoes", padrao="padrao-definicoes",
    fechar="fechar-definicoes", aviso=AVISO_DA_TABELA,
    extra='      <a class="btn" href="#teclas-do-teclado">Teclas do teclado</a>')

TELA_REMAPEAMENTO = tela_de_botoes(
    "remapeamento", "Remapeamento dos botões", D_REMAPEAMENTO,
    "Passa a valer como",
    chr(10).join(f'          <tr><td class="b">{b}</td><td>{drop(REMAP, SEM_TROCA)}</td></tr>'
                 for b, _ in BOTOES),
    f"Devolver as {len(BOTOES)} linhas ao <b>{SEM_TROCA}</b>? "
    "As <b>Definições Controle e Mouse</b> não são tocadas.",
    guardar="guardar-remapeamento", padrao="padrao-remapeamento")

# ---------------------------------------------------------------------------
# A TELA "Teclas do teclado" — 06/09/2026, NAVEGACAO-TECLAS-01.
#
# O QUE ELA FECHA: a linha `FALTA_NO_HTML` de *Editar QUAL TECLA cada botão
# digita* (`docs/data/paridade-gtk-html.csv:208`). A janela antiga tem coluna
# EDITÁVEL EM TEXTO; a tela nova só tinha a lista fechada de 26 ações, e tudo o
# que estivesse fora dela a GTK escrevia e o HTML não tinha como escrever.
#
# **NÃO É UMA VIGÉSIMA SÉTIMA OPÇÃO NA LISTA**, e é a exigência da sprint: uma
# opção por combinação que ela invente faria a lista crescer para sempre. É um
# campo de TEXTO, e quem traduz é o dono (`input_actions.dehumanize_binding`),
# o mesmo da janela antiga.
#
# AS OITO LINHAS SÃO O DOMÍNIO DO PRODUTO, perguntado e não digitado:
# `acoes_de_botao.DOMINIO_DO_TECLADO`. Oferecer campo nas outras catorze faria
# a tela aceitar uma escolha que o `resolver()` não lê — gravada no disco,
# visível na tela e sem nunca chegar ao aparelho.
#
# O ↺ DE CADA LINHA é o Passo 2 da sprint, e é o único caminho não destrutivo
# que existia: até hoje voltar UMA linha ao de fábrica custava o
# "Voltar ao padrão" da tela inteira, que zera `key_bindings` e
# `button_actions` de uma vez.
#
# NÃO HÁ "Voltar ao padrão" DE TELA AQUI, e a ausência é decisão: o desta tela
# seria um terceiro botão a zerar `key_bindings` inteiro, ao lado dos dois que
# já fazem isso (o da tela de Definições e o da aba). O que faltava era o de UMA
# linha, e ele está em cada linha.
# ---------------------------------------------------------------------------

#: OS EXEMPLOS DA DICA SAEM DO DONO, e não de uma digitação. `humanize_binding`
#: é a mesma função que escreve o valor dos campos, então o que a dica ensina a
#: escrever é, por construção, o que a tela devolve — e o dia em que um rótulo
#: mudar lá, ele muda aqui junto.
#:
#: POR QUE ISTO IMPORTA, medido em 06/09/2026: `dehumanize_binding` casa pelo
#: rótulo INTEIRO (`_REV_KEY` é `{rótulo.lower(): token}`), então escrever
#: `Super` é RECUSADO e `Super (tecla Windows)` é aceito. A dica que ensinasse
#: "Super" mandaria a pessoa na direção da recusa.
def _exemplo_de_tecla(token):
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:  # pragma: no cover — sem GTK no ambiente do gerador
        return token
    return str(humanize_binding(token))


D_TECLAS = ajuda(
    "Escreva a tecla que o botão deve digitar. Vale <b>qualquer combinação</b> "
    "— não só as da lista de <b>Definições Controle e Mouse</b>.<br><br>"
    f"Exemplos: <b>{_exemplo_de_tecla('KEY_LEFTALT+KEY_TAB')}</b>, "
    f"<b>{_exemplo_de_tecla('KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_F')}</b>, "
    f"<b>{_exemplo_de_tecla('KEY_LEFTMETA')}</b>, "
    f"<b>{_exemplo_de_tecla('KEY_F5')}</b>.<br><br>"
    "<b>Campo em branco</b> quer dizer que o botão não digita nada.<br><br>"
    f"Só estes {len(_DOMINIO_DO_TECLADO)} botões aparecem aqui porque são os "
    "únicos em que o Hefesto guarda uma tecla escrita; nos outros o que vale é "
    "o que a lista de <b>Definições Controle e Mouse</b> escolhe.<br><br>"
    "O <b>↺</b> devolve <b>só aquela linha</b> ao de fábrica.")

#: A LINHA DA TELA DE TECLAS. O `data-campo` é `tecla-<botão>` e **não há
#: `data-linha`**: a `forma` que o piloto recolhe usa `data-linha || data-campo`
#: como chave, e as vinte e duas listas da outra tela já ocupam a chave
#: `<botão>` — um campo com `data-linha` apagaria a escolha delas dentro da
#: mesma forma.
#:
#: O `data-gesto` VIVE NO `<input>` pelo mesmo motivo do trilho: o ouvinte do
#: piloto sobe pelo `closest`, e sem ele o clique dentro do campo não chega ao
#: Python — a trava não abre e o tique de 100 ms apaga o que ela está digitando.
#:
#: O ↺ NÃO LEVA `data-campo` NEM `data-linha`, e é a mesma armadilha vista do
#: outro lado: ele não tem `value`, então a `forma` gravaria o `textContent`
#: dele ("↺") na chave do botão, e o "Guardar" leria isso como um rótulo de
#: ação. Ele diz quem é por `data-tecla`, que o ouvinte carrega inteiro
#: (`Object.assign({}, d)`).
def linha_de_tecla(rotulo, botao):
    return (f'          <tr><td class="b">{rotulo}</td>'
            f'<td><input type="text" class="tecla" data-campo="tecla-{botao}"'
            f' data-hef-alvo="valor" data-gesto="tecla-escrita"'
            f' placeholder="não digita nada"'
            f' title="Escreva a tecla que este botão digita."></td>'
            f'<td class="re"><a href="#" class="re-tecla" data-gesto="padrao-da-tecla"'
            f' data-tecla="{botao}"'
            f' title="Voltar só esta linha ao de fábrica.">↺</a></td></tr>')


TELA_TECLAS = f'''
<div class="tela-nova" id="teclas-do-teclado">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">Teclas do teclado</span>
      {D_TECLAS}
      <a class="tn-x" href="#" title="Fechar" data-gesto="fechar-teclas">×</a>
    </div>
    <div class="tn-corpo">
      <div class="moldura">
        <table class="tab tab-teclas">
          <tr><th>Botão do controle</th><th>Tecla que ele digita</th><th></th></tr>
{chr(10).join(linha_de_tecla(b, i) for b, i in BOTOES if i in _DOMINIO_DO_TECLADO)}
        </table>
      </div>
    </div>
    <div class="tn-rod grupo-padrao">
      <a class="btn" href="#" data-gesto="fechar-teclas">Cancelar</a>
      <!-- O CAMINHO DE VOLTA À OUTRA TELA MORA NO `?`, e não num terceiro
           botão: medido no WebKit em 06/09/2026, com os três no rodapé o rótulo
           "Definições Controle e Mouse" QUEBRA EM DUAS LINHAS dentro de uma
           caixa de altura fixa — o mesmo defeito que encurtou o terceiro botão
           da fileira da aba em 28/08. Cancelar fecha, e a fileira da aba está a
           um clique. -->
      <a class="btn roxo" href="#" data-gesto="guardar-teclas"
         data-hef-forma="teclas-do-teclado">Guardar</a>
    </div>
  </div>
</div>
'''

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
    f"Os {len(MESA)} controles ligados, cada um na cor do seu plástico, com as "
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
            <!-- A FOLHA VIVA DO PLÁSTICO — nasce VAZIA, e é o pacote que a
                 escreve (`a06_navegacao.folha_do_plastico`, pelo `blocos`).
                 Ela existe porque o CASCO do desenho não é `style` de
                 elemento: as peças do SVG leem `var(--z-…)`, escritas por uma
                 regra `svg[data-colorway="…"]` que o `monta.svg()` embute. O
                 piloto não escreve atributo nem variável — só texto, valor,
                 classe, cor, largura, fundo e `innerHTML`. O `innerHTML` de um
                 `<style>` É texto, e não sofre a normalização que o navegador
                 faz em marcação: é o único canal que troca o casco sem
                 reescrever 370 linhas de SVG a cada meio segundo.
                 VAZIA na bancada de propósito: o desenho continua sendo o
                 desenho, e quem manda na tela é a leitura. -->
            <style id="plastico-vivo"></style>
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
          <!-- ---------- A RESSALVA DA D3: o ajuste é de todos ----------
               05/09/2026, decisão D3 de `2026-09-05-AS-TRES-DECISOES-DO-PERFIL`:
               `mouse`, `key_bindings`, `button_actions`, `teclado_emulado` e
               `suppress_desktop_emulation` ficam GLOBAIS enquanto o caminho de
               ENTRADA por unidade não existir — o `Daemon` tem UM
               `_mouse_device` e UM `_keyboard_device`, e o input vem sempre do
               primário. A decisão pede a tela junto: *"onde a aba oferece um
               destes cinco, a linha de ressalva diz que o ajuste vale para a
               mesa inteira, não só para o controle selecionado."*

               A PEÇA É A DAS DEZ (`monta.ressalva`, D-02), e ela NASCE VAZIA:
               quem decide se há o que ressalvar é o pacote, ao vivo, contando
               os CONECTADOS — com um controle ligado não há promessa quebrada.
               Uma frase cravada aqui a afirmaria também na tela de quem tem um
               controle só, que é a ressalva mentindo pelo desenho.

               DENTRO DA `.moldura` E DEPOIS DA GRADE, e não na tira de
               `.estados` logo abaixo: aquelas cinco linhas falam do que está
               ACONTECENDO agora (o portão, o bloqueio, o custo); esta fala do
               ALCANCE das sete linhas acima dela, e é delas que ela precisa
               estar perto. -->
          {_ressalva(ENDERECO_DA_RESSALVA)}
        </div>
{ESTADOS}

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
{BLOCO_DA_TINTA}'''

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
    e ainda {len(BOTOES)}. As duas medem <b>657px</b> de altura contra os
    <b>757px</b> da janela do produto: sobram 100px, e o rodapé com o
    <i>Guardar</i> fecha dentro dela.
    <br><br>NÚMEROS REMEDIDOS em 06/09/2026, com a 22ª linha: eram 634px com 21,
    e o que estava escrito aqui (660,3px · 96,7px de sobra · y=707,7) já não
    batia antes dela. A caixa tem teto e rola por dentro quando a tira sob a
    tabela cresce — medido no WebKit com duas frases na tira.</li>
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
    há agora os <b>{len(MESA)}</b> da <code>MESA</code> do
    <code>monta.py</code>, cada um com a
    borda e o casco na cor do seu plástico e a barra de luz na cor automática do
    número dele. Nada disso é digitado: o plástico vem de
    <code>cor_da_zona()</code> (que lê o que
    <code>gerar_cores_do_dualsense.py</code> escreveu no SVG) e a cor da luz de
    <code>player_slot_color</code>. <b>As cinco lâmpadas do jogador não estão
    aqui</b> — decisão dela, 28/08: elas saem dos desenhos pequenos e ficam só
    nos grandes, da Iluminação. Neste cartão mediam 1,90 × 0,64 px.</li>
    <li><b>A identidade vem de cima, e o desenho parou de nomeá-la.</b> Os
    nomes de plástico que estavam escritos nesta legenda e no cartão saíram —
    <code>03/09/2026</code>, IDENTIDADE-VEM-DE-CIMA. Quem diz o nome é
    <code>pacotes.identidade_de</code>, quem diz o número é
    <code>pacotes.jogador_de</code>, e a cor da borda é
    <code>style.color</code> escrito pelo pacote. O que sobra aqui é a
    <b>forma</b> do cartão; o <b>aparelho</b> é sempre o que está na mesa.</li>
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

n = monta("06-navegacao", "Navegação", MIOLO, CSS, legenda=LEGENDA)

# A FITA fica apagada nesta aba, mas o motivo herdado da Jogar é falso aqui: não há
# card nenhum, há 28 campos editáveis. Trocado na saída, porque o texto mora no
# esqueleto (topo.html) e esta aba só pode mexer no arquivo dela.
p = onde.pagina("06-navegacao.html")
s = p.read_text()
ANTES = 'title="Esta aba não usa o controle escolhido aqui — os cards são leitura."'
# O TÍTULO SAI DE `monta.TITULOS_DA_FITA` — 05/09/2026. Ele era digitado aqui,
# e o PILOTO não o conhecia: como ele troca o bloco inteiro da fita a cada
# tique, esta frase durava um tique e dava lugar ao genérico de leitura. Agora
# há um dono, consultado pelo gerador do arquivo E pela tela viva.
DEPOIS = f'title="{TITULOS_DA_FITA["06-navegacao.html"]}"'
if f"Player {NAVEGA}" not in DEPOIS:
    raise SystemExit(
        f"ERRO: a fita da 06 nomeia o Player 1 e o mockup elegeu o {NAVEGA} — "
        "reveja `monta.TITULOS_DA_FITA` antes de gerar")
if ANTES not in s:
    raise SystemExit("ERRO: o title da fita mudou no topo.html — refaça a troca")
s = s.replace(ANTES, DEPOIS)

# A FITA DESTA ABA GANHA ENDEREÇO — 03/09/2026, IDENTIDADE-VEM-DE-CIMA.
#
# Os dois chips nomeavam o controle do MOCKUP (`P1 · Cosmic Red · USB`,
# `P2 · Starlight Blue · BT`) e o `title` de cada um repetia o nome. Seis dos
# dezesseis valores congelados desta aba estavam aqui.
#
# O DONO DA FITA É COMPARTILHADO (`monta.fita` desenha, `hefesto_vivo._fita`
# repinta), e por isso a troca é feita AQUI, na saída — a mesma razão pela qual
# o `title` acima é trocado neste arquivo: o bloco mora no esqueleto e esta aba
# só pode mexer no arquivo dela.
#
# E ELA PRECISOU EXISTIR, medido em 03/09/2026 com os dois controles dela na
# mesa: `_fita` **desiste** quando um controle não tem cor lida (`any(not
# c.get("cor") …) -> return ""`), e pelo rádio a cor não se lê. Treze tiques
# depois, a fita da `06` ainda dizia Cosmic Red e Starlight Blue ao lado de um
# cabeçalho que já contava certo. Com o endereço, quem escreve é o pacote.
FITA = re.compile(r'(<div class="fita inerte"[^>]*)(>)(.*?)(</div>)', re.S)
if not FITA.search(s):
    raise SystemExit("ERRO: a fita inerte mudou de forma — refaça o endereço")
s = FITA.sub(
    lambda m: (m.group(1) + ' data-campo="fita-chips" data-hef-alvo="html"'
               + m.group(2) + chips_da_fita(MESA_DA_FITA) + m.group(4)),
    s, count=1)

# a tela nova entra IRMÃ da janela, fora do miolo (ver o comentário no MIOLO)
MARCA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"
if MARCA not in s:
    raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
TELAS = "\n".join(t.strip() for t in (TELA_DEFINICOES, TELA_TECLAS,
                                      TELA_REMAPEAMENTO, TELA_PONTO))
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
    exigir(f'>P{NAVEGA} <span class="pt">•</span> '
           f'<span data-campo="identidade">{QUEM_NAVEGA["nome"]}</span></div>' in corpo,
           "o card de quem navega não é o do controle certo")

    # 3-bis. A IDENTIDADE TEM ENDEREÇO EM TODA PARTE ONDE ELA É DITA —
    #    03/09/2026, IDENTIDADE-VEM-DE-CIMA. Cada `exigir` daqui vale UM dos
    #    dezesseis valores que a régua `check_identidade_vem_de_cima.py`
    #    contava nesta aba. Tirar um endereço volta a congelar o controle do
    #    desenho na tela dela, e a régua da onda o acusa de novo — mas ela roda
    #    sobre a bancada INTEIRA, e esta roda sobre a saída deste gerador.
    conectados = [c for c in MESA if c.get("conectado", True)]
    exigir(corpo.count('data-campo="identidade"') == len(conectados),
           f"os {len(conectados)} cartões conectados perderam o "
           f'`data-campo="identidade"` — o nome do plástico volta a ser o do '
           f"mockup, e nada o reescreve")
    exigir(corpo.count('data-campo="plastico" data-hef-alvo="cor"') == len(MESA),
           f"os {len(MESA)} lugares perderam o `data-campo=\"plastico\"` — a "
           f"borda volta a ser a cor cravada do desenho")
    exigir("--plastico" not in corpo,
           "voltou um `--plastico` cravado ao miolo: ele não tem alvo de "
           "pintura, e o piloto não escreve variável CSS — a cor ficaria a do "
           "mockup para sempre")
    exigir('<style id="plastico-vivo"></style>' in doc,
           "a folha viva do plástico sumiu — sem ela o casco do desenho fica "
           "no colorway do mockup, que nenhum campo alcança")
    exigir(doc.count('data-campo="quem-navega"') == 2,
           "as duas dicas das telas de botões perderam o "
           '`data-campo="quem-navega"` — elas voltam a nomear o controle do '
           "desenho no meio do texto")
    exigir('data-campo="fita-chips" data-hef-alvo="html"' in doc,
           "a fita perdeu o endereço — e `hefesto_vivo._fita` DESISTE quando um "
           "controle da mesa não tem cor lida, que é o caso do rádio hoje")
    for c in conectados:
        exigir(f'title="Player {c["jogador"]}' not in doc,
               f"o `title` do cartão do P{c['jogador']} voltou — ele nomeia o "
               f"controle e não tem alvo de pintura")

    # 3-ter. O DESENHO SEGUE O APARELHO — 03/09/2026, A-COR-VEM-DO-APARELHO.
    #    As três linhas abaixo são a MESMA cura vista de três lados, e cada uma
    #    sozinha a desfaz:
    #      · sem o endereço, o `data-colorway` fica o do mockup para sempre;
    #      · com a folha PODADA de volta dentro do SVG, escrever um colorway que
    #        ela não traz dá o cinza cru do desenho (`rgb(58, 63, 75)`) — a
    #        armadilha que o alvo de atributo documenta com todas as letras;
    #      · sem a folha dos 28 na página, idem para 27 dos 28 modelos dela.
    exigir(corpo.count(ENDERECO_DO_DESENHO) == len(MESA),
           f"os {len(MESA)} desenhos perderam o `{ENDERECO_DO_DESENHO}` — o "
           f"`data-colorway` volta a ser o do mockup, e nada o reescreve")
    exigir(corpo.count("data-colorway=") == len(MESA),
           f"há `data-colorway` no miolo fora dos {len(MESA)} desenhos "
           f"endereçados — cor de aparelho cravada onde o produto não alcança")
    exigir("cores-do-dualsense-folha" not in corpo,
           "a folha podada voltou para dentro de um SVG do miolo: ela traz UM "
           "modelo, e um SVG assim não tem como virar outro aparelho")
    _no_mapa = set(_re.findall(r'svg\[data-colorway="([^"]+)"\]', DS))
    _na_pagina = set(_re.findall(r'svg\[data-colorway="([^"]+)"\]', doc))
    exigir(_no_mapa and _no_mapa <= _na_pagina,
           f"a página publica {len(_na_pagina)} dos {len(_no_mapa)} modelos do "
           f"mapa — faltam {sorted(_no_mapa - _na_pagina)}; quem tiver um "
           f"desses vê o desenho no cinza cru")
    #    E A TINTA JUNTO. Doze dos 28 pintam por `url(#…)`, e `monta.svg()`
    #    prefixa todo id do desenho: sem o `BLOCO_DA_TINTA` a referência morre e
    #    a peça SOME da tela — medido no WebKit com `chroma-teal`, e é o pior
    #    dos três estados possíveis, porque não parece defeito, parece desenho.
    _ids = set(_re.findall(r'\sid="([^"]+)"', doc))
    _mortas = [i for i in tinta_referenciada() if i not in _ids]
    exigir(not _mortas,
           f"a folha das cores pede {_mortas} e a página não publica esse "
           f"`id` — os doze modelos que pintam por `url(#…)` ficam com "
           f"referência morta, e o desenho deles SOME (não fica cinza). Falta o "
           f"`BLOCO_DA_TINTA` no miolo")

    # 3-bis. A LISTA DA TELA É A DO PRODUTO — e esta conferência FALTAVA.
    #
    #    ACHADO EM 06/09/2026, mordendo a §4-P3 da ONDA5-06-02: a sprint dizia
    #    que tirar uma entrada de `BOTOES` faria a conferência abaixo reprovar
    #    *"nomeando quantas linhas achou contra quantas o produto declara"*.
    #    **Não fazia.** A conferência de baixo conta `data-gesto` contra
    #    `len(BOTOES)` — as duas pontas saem da MESMA lista deste arquivo —,
    #    então tirar uma entrada diminui os dois lados e o gerador sai `OK`,
    #    com a tela mostrando uma linha a menos que o produto atende.
    #
    #    Medido: sem a entrada do PS o gerador imprimia `21 botões do mapa` e
    #    rc=0. Quem pegava era a suíte (as réguas que comparam a página com
    #    `core.acoes_de_botao.BOTOES`), nunca o gerador — e o gerador é quem
    #    roda ANTES, na mão de quem mexe no desenho.
    #
    #    O DONO DA LISTA É O PRODUTO. Aqui moram a ORDEM e os GLIFOS, que são
    #    desenho; QUAIS botões existem é fato, e fato tem um dono só.
    _do_produto = set(_BOTOES_DO_PRODUTO)
    _do_desenho = {i for _b, i in BOTOES}
    exigir(_do_desenho == _do_produto,
           f"a tela e o produto não listam os mesmos botões — a mais no "
           f"desenho: {sorted(_do_desenho - _do_produto)}; a menos: "
           f"{sorted(_do_produto - _do_desenho)}. Uma linha que só existe de um "
           f"lado é escolha que o Guardar descarta em silêncio, ou botão que o "
           f"produto atende e a tela não oferece")

    # 4. AS LINHAS DIZEM AO PYTHON QUE ELA ESTÁ MEXENDO — decisão
    #    dela, 02/09/2026. O `data-gesto` é o ÚNICO atributo destes `<select>`
    #    que o ouvinte do piloto reconhece (`hefesto_vivo.py:367`); sem ele o
    #    `change` morre no navegador, o tique reescreve a escolha por cima em
    #    ≤1,5 s e o "Guardar" ao lado nunca vê forma diferente do perfil.
    #    Tirá-lo desfaz a decisão CALADO, e é por isso que ele é conferido aqui.
    exigir(corpo.count(f'data-gesto="{LINHA_DE_BOTAO}"') == len(BOTOES),
           f"as {len(BOTOES)} linhas de 'o que cada botão faz' perderam o "
           f"`data-gesto=\"{LINHA_DE_BOTAO}\"` — sem ele a pintura volta a "
           f"desfazer a escolha antes do clique em Guardar")
    # 4-bis. E O "SAIR" TEM NOME. O `×` e o `Cancelar` da tela de definições
    #    fecham a pop-up pelo `:target` sozinhos; o que eles NÃO faziam era
    #    avisar o Python, e é nesse instante que as escolhas pendentes têm de
    #    ser largadas. São DOIS na tela de definições, e ZERO na de
    #    remapeamento, que não tem trava a soltar.
    exigir(corpo.count('data-gesto="fechar-definicoes"') == 2,
           "o `×` e o `Cancelar` da tela de definições perderam o "
           "`data-gesto=\"fechar-definicoes\"` — a trava das 21 linhas ficaria "
           "presa depois de ela desistir")

    # 4-ter. A TELA "Teclas do teclado" — 06/09/2026, NAVEGACAO-TECLAS-01.
    #    As cinco conferências são a mesma cura vista de cinco lados, e cada uma
    #    sozinha a desfaz.
    _dominio = sorted(_DOMINIO_DO_TECLADO)
    exigir(corpo.count('data-campo="tecla-') == len(_dominio),
           f"a tela de teclas não tem os {len(_dominio)} campos de texto — o "
           f"domínio de `key_bindings` é do produto "
           f"(`acoes_de_botao.DOMINIO_DO_TECLADO`) e a tela tem de oferecer "
           f"exatamente ele")
    for _b in _dominio:
        exigir(f'data-campo="tecla-{_b}"' in corpo,
               f"o campo de tecla do {_b} sumiu — o produto guarda "
               f"`key_bindings[{_b!r}]` e a tela deixou de oferecer onde escrever")
        exigir(f'data-tecla="{_b}"' in corpo,
               f"o ↺ do {_b} sumiu — voltar UMA linha ao de fábrica volta a "
               f"custar o 'Voltar ao padrão' da tela inteira")
    #    O CAMPO DE TEXTO NÃO PODE LEVAR `data-linha`: a `forma` que o piloto
    #    recolhe usa `data-linha || data-campo` como chave, e as 22 listas da
    #    outra tela já ocupam a chave `<botão>` pelo `data-linha`. Um campo com
    #    ele apagaria a escolha da lista DENTRO da mesma forma.
    _tela_teclas = corpo.split('id="teclas-do-teclado"', 1)[-1].split(
        'class="tela-nova"', 1)[0]
    exigir("data-linha=" not in _tela_teclas,
           "voltou um `data-linha` à tela de teclas — a `forma` do piloto usa "
           "`data-linha || data-campo` como chave, e ele faria o campo de texto "
           "ocupar a chave da lista de 'o que cada botão faz'")
    #    E O ↺ NÃO PODE LEVAR `data-campo` NEM `data-linha` pelo mesmo motivo,
    #    visto do outro lado: sem `value`, a `forma` gravaria o `textContent`
    #    dele ("↺") e o Guardar leria isso como rótulo de ação.
    exigir(_tela_teclas.count('data-campo="tecla-') == len(_dominio),
           "a tela de teclas tem `data-campo` fora dos campos de texto — o ↺ e "
           "os botões do rodapé não podem ter, senão entram na `forma`")
    #    O `change` de um `<input>` só chega no BLUR. Sem o `data-gesto` no
    #    próprio campo, o clique dentro dele não chega ao Python, a trava não
    #    abre e o tique de 100 ms apaga o que ela está digitando.
    exigir(_tela_teclas.count('data-gesto="tecla-escrita"') == len(_dominio),
           "os campos de tecla perderam o `data-gesto=\"tecla-escrita\"` — sem "
           "ele a trava não abre e a pintura apaga a digitação dela na primeira "
           "letra")
    exigir(_tela_teclas.count('data-gesto="fechar-teclas"') == 2,
           "o `×` e o `Cancelar` da tela de teclas perderam o "
           "`data-gesto=\"fechar-teclas\"` — a trava ficaria presa depois de "
           "ela desistir")
    exigir('href="#teclas-do-teclado"' in corpo,
           "não há como CHEGAR à tela de teclas — ela é `:target`, e sem um "
           "link para o `id` dela a tela existe no HTML e não abre nunca")
    # 5. A LISTA DO TECLADO NASCE NA OPÇÃO QUE ELA ESCOLHEU COMO PADRÃO, e ela
    #    é a única das três com dono no produto. Nascer marcada na primeira
    #    ("Só dentro do jogo") faria a tela prometer, nos 100 ms anteriores ao
    #    primeiro tique, o que o Hefesto ainda não sabe fazer.
    exigir(f'<option selected>{TECLADO_PADRAO}</option>' in corpo,
           f"a 'Função do teclado' não nasce em {TECLADO_PADRAO!r}")
    for opcao in OPCOES_TECLADO:
        exigir(f">{opcao}</option>" in corpo,
               f"a opção {opcao!r} da 'Função do teclado' sumiu do desenho")

    # 6. O "STATUS DO MODO" NÃO VOLTA A AFIRMAR SOZINHO — 03/09/2026. As três
    #    coisas abaixo são a mesma cura vista de três lados, e cada uma sozinha
    #    a desfaz: sem o `data-campo` o produto não tem onde escrever; com o
    #    `<input checked>` de volta a tela troca de lado no clique recusado; com
    #    o `content:'Ligado'` de volta a palavra volta a ser do CSS e o nó de
    #    texto vira enfeite.
    exigir(corpo.count('data-campo="rato-ligado"') == 2,
           "o 'Status do Modo' perdeu um dos dois `data-campo=\"rato-ligado\"` "
           "(a classe no rótulo e a palavra no `.txt`) — a tela volta a dizer "
           "'Ligado' com a emulação desligada")
    exigir('class="tog-in"' not in doc and 'id="st-modo"' not in doc,
           "voltou o `<input type=\"checkbox\">` do 'Status do Modo': clicar no "
           "rótulo vira a caixa no DOM mesmo quando o gesto RECUSA, e nada a "
           "devolve")
    exigir("content:'Ligado'" not in doc and "content:'Desligado'" not in doc,
           "a palavra do 'Status do Modo' voltou a sair de um `content:` de "
           "CSS — o piloto não escreve pseudoelemento, e a palavra fica a do "
           "desenho para sempre")
    exigir('<span class="txt" data-campo="rato-ligado">—</span>' in corpo,
           "o 'Status do Modo' não nasce mais em '—': antes do primeiro tique "
           "ninguém perguntou ao Hefesto, e qualquer das duas palavras é uma "
           "afirmação")

    # 7. AS TRÊS LINHAS DE ESTADO TÊM LUGAR. Elas são a única coisa desta aba
    #    que responde "por que o cursor não anda" e "há teclado na tela nesta
    #    máquina" — as duas perguntas que a GTK responde e a tela nova calava.
    for campo in ("rato-estado", "teclado-bloqueio", "teclado-osk"):
        exigir(f'data-campo="{campo}" data-hef-alvo="html"' in corpo,
               f"a linha de estado `{campo}` sumiu do desenho — a frase do "
               f"produto volta a ser emitida para o vazio")

    # 8. AS DUAS VELOCIDADES ARRASTAM, E A FAIXA DELAS É A DO PRODUTO —
    #    05/09/2026, decisão dela: *"velocidade do cursor e da rolagem coloca
    #    um slicer pra cada"*.
    #
    #    A FAIXA VAI CONFERIDA CONTRA A CONSTANTE, e não contra um literal: se
    #    alguém digitar `max="100"` no gerador, esta régua reprova. É a mesma
    #    razão de as dicas lerem `MOUSE_SPEED_MAX` em vez de dizerem "de 1 a
    #    10", que era o erro que elas carregavam até 01/09.
    #
    #    E O NÚMERO AO LADO TEM O MESMO ENDEREÇO DO TRILHO: os dois mostram o
    #    mesmo inteiro, e o piloto escreve um escalar em TODOS os elementos de
    #    mesmo `data-campo`. Sem o segundo, a barra andaria e o número ficaria
    #    parado no que o desenho cravou.
    for campo, minimo, maximo in (("vel-cursor", MOUSE_SPEED_MIN, MOUSE_SPEED_MAX),
                                  ("vel-rolagem", SCROLL_SPEED_MIN, SCROLL_SPEED_MAX)):
        exigir(f'<input class="trilho" type="range" min="{minimo}"'
               f' max="{maximo}" step="1" ' in corpo
               and f'data-gesto="{campo}" data-campo="{campo}"'
                   ' data-hef-alvo="valor"' in corpo,
               f"a barra de `{campo}` sumiu, ou a faixa dela deixou de ser a do "
               f"produto ({minimo} a {maximo}, de `integrations/uinput_mouse.py`)")
        exigir(f'<span class="num" data-campo="{campo}">' in corpo,
               f"o número ao lado da barra de `{campo}` perdeu o endereço — a "
               f"barra andaria e o número ficaria no que o desenho cravou")
    #    E OS `−`/`+` NÃO VOLTAM AO PAINEL. Os do "Estilo Point-and-click" ficam
    #    (nunca tiveram endereço, e a razão está no comentário daquela pop-up):
    #    por isso a conta é do PAINEL, recortado, e não da página.
    painel = corpo.split('As opções de ativação', 1)[-1].split('class="tela-nova"', 1)[0]
    exigir(len(painel) > 2000, "a régua não achou o painel das opções de ativação")
    exigir('class="passo"' not in painel,
           "voltou um `−`/`+` ao painel das opções de ativação — ela mandou "
           "barra, e um par de botões ao lado dela é a meia-cura")
    # 6. A RESSALVA DA D3 — 05/09/2026. Ela tem de estar NO PAINEL (é o alcance
    #    das sete linhas dele que ela ressalva) e tem de nascer VAZIA: a frase
    #    quem escreve é o pacote, contando os controles ligados. Uma ressalva
    #    cravada no desenho é a que já mentiu na aba 08.
    exigir(f'class="ressalva" data-campo="{ENDERECO_DA_RESSALVA}"' in painel,
           "a linha de ressalva da D3 saiu do painel das opções de ativação — "
           "sem ela a aba promete por-controle e entrega global, que é o mesmo "
           "defeito por outro caminho")
    exigir(f'data-campo="{ENDERECO_DA_RESSALVA}" data-hef-alvo="html">'
           '<i class="nada"></i></div>' in painel,
           "a ressalva da D3 nasceu com frase no desenho — quem decide se há o "
           "que ressalvar é o pacote, ao vivo, e com UM controle ligado não há")

    if falhas:
        raise SystemExit("ERRO em 06-navegacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


_conferir(onde.pagina("06-navegacao.html").read_text())
print(f"06-navegacao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
      f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · "
      f"quem navega: P{NAVEGA} · {len(BOTOES)} botões do mapa")
