import sys, pathlib, csv, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde

# são digitados aqui. `core/acoes_de_botao` é o dono desde 01/09/2026, e ele
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
from hefesto_dualsense4unix.core.acoes_de_botao import (  # noqa: E402
    BOTOES as _BOTOES_DO_PRODUTO,
)
#: (`core/acoes_de_botao._dominio_do_teclado`). Digitar a lista aqui faria o
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
from monta import NADA_A_DIZER  # noqa: E402
from monta import TITULOS_DA_FITA  # noqa: E402
from monta import folha_das_cores  # noqa: E402

# `pacotes/a04_iluminacao.um_botao_de_player`: o dono mora no PACOTE, porque é
# escritas do mesmo rótulo é como o desenho e o produto divergem calados.
from pacotes.a06_navegacao import (  # noqa: E402
    ENDERECO_DA_RESSALVA,
    PAPEL_DO_CURSOR,
    PAPEL_QUE_NAVEGA,
    PAPEL_SO_A_JANELA,
    PREFIXO_DA_TROCA,
    ROTULOS_DA_TROCA,
    chips_da_fita,
    rotulo_de_quem_navega,
)
from pacotes.a06_navegacao import linha_do_cartao as _linha_do_cartao  # noqa: E402
from pacotes.a06_navegacao import SEM_TROCA as _SEM_TROCA_DO_PACOTE  # noqa: E402

from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    REMAPEAVEIS as _REMAPEAVEIS,
)
from pacotes.a06_navegacao import PREFIXO_DA_ACAO  # noqa: E402
from hefesto_dualsense4unix.core import acoes_do_gesto as _acoes_do_gesto  # noqa: E402
from pacotes.a06_navegacao import (  # noqa: E402
    ENDERECO_DA_DICA_DOS_GESTOS,
    PREFIXO_DO_GESTO,
    PREFIXO_DO_SCRIPT,
)
#: que é exatamente como o desenho e o produto divergem calados.
from pacotes import SEM_NINGUEM_AQUI  # noqa: E402
import marca_da_camada as _marca  # noqa: E402

MESA_DA_FITA = CONECTADOS

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
    """O nome curto da peça, LIDO do mapa."""
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
    """Como a peça aparece numa lista de destino de remapeamento."""
    n = nome_de(pid)
    if PECAS[pid]["tipo"] == "eixo":
        return [f"{n} (clique)", f"{n} (direção)"]
    if PECAS[pid]["tipo"] == "superficie":
        return [f"{n} (clique)"]
    return [n]


_m = re.search(r"Clique ([^.]+)\.", PECAS["touchpad"]["nota"])
if not _m:
    raise SystemExit("ERRO: a nota do touchpad não declara mais os cliques — "
                     "veja docs/data/pecas-do-dualsense.csv")
TOUCH_REGIOES = [f"clique {x.strip()}" for x in
                 _m.group(1).replace(" e ", ", ").split(",") if x.strip()]

NAVEGA = min(c["jogador"] for c in CONECTADOS)
QUEM_NAVEGA = next((c for c in CONECTADOS if c["jogador"] == NAVEGA), None)
if QUEM_NAVEGA is None:
    raise SystemExit(f"ERRO: o Player {NAVEGA} navega o PC e NÃO está na mesa. "
                     f"Quem navega sai de `CONECTADOS`, nunca de `MESA`.")


def _hex(rgb):
    """A cor canônica de lightbar do jogador, do produto (`led_control`)."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _tem_tinta(pid):
    """A peça tem superfície própria, ou o desenho dela é o glifo?"""
    m = re.search(rf'<g id="{pid}"[^>]*>(.*?)</g>', DS, re.S)
    return bool(m) and "sem-tinta" not in m.group(1)


CSS = CSS_GLIFO + """
  /* ---------- Navegação ----------
     A RODADA DOS QUATRO CONTROLES (27/08/2026). Ela

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

     [56]

     [57]

     [51] "no navegação faltou usar os svgs que já usamos em status."
     ------------------------------------------------------------------- */

  /* ---- O `1fr` NÃO DIVIDE IGUAL, e foi assim que a divisória vertical do bloco
     de baixo ficou 8,3px fora da de cima (o usuário viu na tela, 27/08: "olha o
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

     O PADRÃO É O NEUTRO, e é a regra de produto — *campo sem informação não mostra
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
  /* AS DUAS PALAVRAS PARA O MESMO ESTADO FINALMENTE SE ENCONTRAM — 17/09/2026.

     Queixa de uso, com a foto da Navegação.

     A causa estava NOMEADA nesta casa desde 04/09, no `a06_navegacao.py`: o P3
     e o P4 nascem `class="nav-ctl vazia"` no esqueleto; o P2 nasce OCUPADO (é
     o mockup de dois controles) e é esvaziado em tempo de execução — e quem o
     esvazia escreve a classe **`off`** (`hefesto_vivo.py:1151`), *"que folha de
     estilo nenhuma menciona"*. A cura daquele dia alcançou a COR, por outro
     caminho (`folha_do_plastico`), e a MOLDURA ficou: `.vazia` põe borda e
     fundo transparente, `off` não põe nada. Por isso o P2 desligado tinha
     caixa diferente da do P3 e do P4.

     A cura é o seletor de classe `.esvaziado`, que as duas palavras produzem.
     Não renomeei o `off` do piloto: ele é escrito pelo passo `vazios` para as
     CINCO abas, e trocá-lo aqui mudaria o contrato de todas. Não renomeei o
     `vazia` do esqueleto: ele é o que o desenho aprovado carrega.

     A régua que cobra o encontro é
     `tests/unit/test_nav_vazio_01_os_lugares_desligados_sao_iguais.py` — e ela
     mede a FOLHA contra a palavra que o PILOTO escreve, lida do fonte dele.
     Uma régua que digitasse "off" repetiria o defeito que ela existe para
     matar: duas cópias da mesma palavra, livres para divergir. */
  :is(.nav-ctl.vazia, .nav-ctl.off){border:1px solid var(--border-forte);background:transparent}
  :is(.nav-ctl.vazia, .nav-ctl.off) .nav-rot,
  :is(.nav-ctl.vazia, .nav-ctl.off) .nav-est{color:var(--linha)}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg .peca,
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg .corpo,
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg .miolo *{fill:var(--linha) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg .corpo{stroke:var(--border-forte) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg text{fill:var(--linha) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg line{stroke:var(--linha) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg path:not(.peca):not(.corpo){fill:var(--linha) !important;
                                                     stroke:var(--linha) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg rect:not([fill="none"]),
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg circle:not([fill="none"]),
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg polygon:not([fill="none"]),
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg ellipse:not([fill="none"]){fill:var(--linha) !important}
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg rect,
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg circle,
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg polygon,
  :is(.nav-ctl.vazia, .nav-ctl.off) .ds-svg ellipse{stroke:var(--border-forte) !important}
  .nav-ctl .ds-svg{width:100%}
  /* a barra de luz acesa na cor automática do jogador. Sem esta regra o `--luz`
     que o `monta.svg()` escreve não pinta NADA: as duas tiras são `.peca`, e a
     regra neutra do esqueleto as deixa cinza. Era o caso desta aba até hoje. */
  .nav-ctl [id$="-lightbar"] .peca{fill:var(--luz)}
  /* AS CINCO LÂMPADAS DO JOGADOR NÃO EXISTEM NESTES CARTÕES — decisão,
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
     PRIMEIRA LETRA, e o usuário confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     o usuário apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           margin-bottom:5px;display:flex;align-items:center;gap:8px;height:17px}
  .sec-rot .ajuda{text-transform:none;letter-spacing:0}
  /* O RESPIRO DO TÍTULO: `sec-alta` estava escrita no HTML desde 27/08 e não
     tinha uma linha de CSS — o título nascia colado no pé do bloco de cima.
     Ela. */
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
     Navegação; virando quadro próprio (pedido) ela ganhou `.quadro-topo`
     (28px), duas bordas e o padding de corpo — 26px a mais do que o miolo tem.
     Medido: o miolo pedia 570 num espaço de 544.
     O respiro sai de onde ele é folga e não leitura: o topo do segundo quadro e
     as duas pontas do corpo dele. Nenhuma linha de escolha encolhe — elas
     continuam nos 36px de `--h-escolha`, que é o alvo de clique. */
  .miolo > .quadro + .quadro > .quadro-topo{padding:6px 14px 0}
  /* O PÉ DO SEGUNDO QUADRO FOI DE 6px A 2px EM 07/09/2026, e os 4px pagam a
     TIRA DE ESTADOS — a que ficou, não a que saiu.

     O QUE A CONFERÊNCIA MEDIU, e derruba a premissa da cura de hoje: a queixa
     de uso (*"essas 3 frases aqui na parte de baixo que quebram o layout"*) foi
     lida como sendo das TRÊS frases, e não era. A tira nunca coube — **UMA
     linha sozinha já transbordava**, e a linha que sobra é a mais comum da
     máquina do usuário. Medido em Chrome (1200x777), na página publicada e no `HEAD`,
     `scrollHeight - clientHeight` do `.miolo`:

         tira vazia .............. 0px    0px  (HEAD)
         só `rato-estado` ........ 4px    4px  (HEAD)   ← e ninguém a tirou
         + `modo-portao` ........ 44px   44px  (HEAD)

     Os números do `HEAD` são a prova de que isto é HERDADO e não desta leva: o
     transbordo é o MESMO com as cinco linhas de ontem e com as três de hoje.
     Tirar três frases reduziu a chance de acontecer e não curou o defeito —
     `rato-estado` (*"Pronto para usar como mouse"*) acende sozinha e a barra de
     rolagem nascia por dentro do miolo do mesmo jeito.

     4px É O NÚMERO EXATO, e não uma folga escolhida a esmo: é o que falta para
     a tira de UMA linha caber (25px de tira contra 21px de sobra). Medido
     depois: 0px de transbordo com a tira em uma linha, nas duas árvores.

     O QUE ELE NÃO COMPRA, e fica dito: com DUAS linhas o miolo volta a
     transbordar 40px, porque `modo-portao` sozinha ocupa duas. Ela é uma das
     que SAÍRAM do pé por ordem de produto — e esta medida é a segunda razão, medida,
     para que continue fora: aquele pé não cabe a frase, com trim nenhum.

     O RESPIRO SAI DE ONDE É FOLGA E NÃO LEITURA, que é a mesma regra da linha
     de cima: o pé do corpo, e não a altura das linhas de escolha, que continuam
     nos 36px de `--h-escolha` porque são o alvo de clique. */
  .miolo > .quadro + .quadro > .quadro-corpo{padding:4px 14px 2px}
  .miolo > .quadro:first-child > .quadro-corpo{padding-bottom:6px}

  /* A LINHA HORIZONTAL QUE SEPARA UM CAMPO DO OUTRO — pedido, 30/08. Mesmo molde da Iluminação (`aba04.py`), com a razão escrita lá.
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
  /* E AS DICAS DAS OPÇÕES DE ATIVAÇÃO ABREM PARA CIMA — 07/09/2026, e é a
     mesma medida daquela linha acima, no outro eixo.

     O painel é o ÚLTIMO quadro da aba: o `?` da "Função do teclado" fica a
     541,5px do topo da janela de 777px, e a `.dica` do desenho abre para BAIXO
     (`top:-4px`). Sobravam 235px. Com as frases do produto dentro — que é o que
     as três que o usuário mandou tirar do pé passaram a fazer — aquela dica vai a
     267px com o teclado na tela instalado e a **319px sem** (a frase longa é a
     que manda instalar `wvkbd-mobintl` ou `onboard` pelo nome), e o
     `overflow-y` do `.miolo` cortava o último parágrafo. A frase que mudou de
     lugar para não sumir sumia de novo, por outro caminho.

     ANCORADA EMBAIXO ela cresce para onde há espaço: são 545px do `?` até o
     topo do miolo, contra 235 para baixo. Nenhuma outra dica desta aba muda —
     a regra é do painel, e as duas velocidades da pop-up "Estilo
     Point-and-click" moram fora dele.

     A RÉGUA É `test_a_06_as_tres_frases_do_pe_couberam_no_ponto_de_interrogacao`,
     e ela mede as duas frases do teclado na tela, não só a curta. */
  .ativacao .dica{top:auto;bottom:-4px}
  .escolha-at{width:100%;height:var(--h-escolha);border-radius:7px;font-size:12px;
    font-family:inherit;padding:0 10px;border:1px solid var(--border-forte);
    background:var(--app-bg);color:var(--fg);cursor:pointer}
  .escolha-at:hover{border-color:var(--purple)}
  .escolha-at.viva{border-color:var(--purple);background:var(--sel-bg);font-weight:600}

  /* os "seletores tipo bignumbers" que o usuário pediu para a velocidade de cursor */
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
     número só (decisão de produto), o par único é `:last-child` **e** `:first-child`,
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

  /* AS DUAS VELOCIDADES ARRASTAM — decisão, 05/09/2026. O molde é o da aba
     Vibração (`aba05._trilho`), e a aparência é copiada dela de propósito:
     `appearance:none` desliga o controle nativo do WebKit — que traria a cor e
     a altura do tema do sistema para dentro de uma tela que o usuário aprovou — e as
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
  /* O CABEÇALHO DA TABELA DE GESTOS É BRANCO E NEGRITO — decisão,
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
  /* ---- AS SEIS LINHAS QUE A TROCA NÃO ALCANÇA — F1-REMAPEAR-02, 13/09/2026 ----
     A direção dos dois analógicos, o PS e as três regiões do touchpad: o motor
     as recusa, e a lista delas nasce apagada. A cara é a do apagado da casa
     (`.btn.apagado` e `.seg button:disabled` do `monta.CSS_FOLHA`): borda
     sutil, texto mudo, cursor de recusa. O `:hover` repete a borda porque a
     regra da linha acende o roxo, e um apagado que acende no ponteiro promete
     o clique que não existe. */
  .campo-linha:disabled{border-color:var(--border-sutil);color:var(--texto-mudo);
    cursor:not-allowed}
  .campo-linha:disabled:hover{border-color:var(--border-sutil)}

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
  /* quatro botões na fileira de 1086px dão 261,8px cada, e o rótulo mais longo
     cabe numa linha. O comentário daqui afirmava, desde 28/08, que "Configurar
     o estilo Point-and-click" JÁ tinha virado "Estilo Point-and-click" — e o
     gerador continuava escrevendo o rótulo longo: era comentário descrevendo
     cura que não existia. A troca aconteceu de fato em 11/09/2026, aprovada
     pelo usuário, e por outra razão: o botão e a tela que ele abre tinham nomes
     diferentes. A medida de 28/08 fica registrada na LEGENDA. */
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
  /* O POP-UP ABRE NO CLIQUE E SÓ FECHA NA OPÇÃO OU FORA — decisão,
     31/08/2026

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

  /* AS TRÊS LINHAS DE ESTADO NASCEM VAZIAS, E É REGRA DE PRODUTO — 30/08/2026. Elas são o que a GTK mostra e esta
     aba calava — a dica do quadro Navegação já cita "a linha de estado abaixo"
     desde 27/08, e até hoje a linha que ela cita não existia.

     NA MESMA FILEIRA, e a razão é medida: a aba já ocupa quase toda a altura da
     janela (757px), e três linhas empilhadas empurraram a fileira dos botões
     para FORA da tela — visto na foto de 03/09, com o "Definições Controle e
     Mouse" cortado pelo rodapé. Em fileira com `wrap` elas custam uma linha
     quando cabem, e só quebram quando a frase é longa (a de "não há teclado na
     tela instalado", que é justamente a que precisa de espaço).

     O `.nada` É COMO UMA LINHA SOME, e não o `:empty`: o `escrever()` do piloto
     troca valor vazio por `—` (`hefesto_vivo.py:65`), então uma frase vazia
     viraria um travessão solto na tela do usuário — foi o que a primeira foto
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

  /* ---------- A FRASE DO PRODUTO DENTRO DO `?` ----------
     07/09/2026,  As três desceram para o `?` do campo de que
     falam (`ajuda(..., vivas=…)`), e continuam sendo escritas pelo pacote a
     cada tique — o que muda é o LUGAR, nunca o dono.

     OS DOIS MARCADORES DE APAGAR SÃO OS MESMOS da tira, e pela mesma razão: o
     `:empty` cobre o bloco que nasce vazio e nunca é pintado, e o `.nada` cobre
     o que o piloto pinta a cada tique com "não há o que dizer" — sem ele o
     `escrever()` troca vazio por `—` e a dica ganha um travessão solto, com o
     traço de cima em volta de nada. Faltando um dos dois, o traço volta por um
     dos dois caminhos, calado.

     O TRAÇO SEPARA DUAS VOZES, e é por isso que ele existe: o que está acima é
     o texto FIXO do desenho, o que está abaixo é o que a máquina do usuário diz
     AGORA. Sem a separação, uma frase que muda com o estado se lê como parte da
     explicação que nunca muda. */
  .dica .viva{display:block;margin-top:10px;padding-top:9px;
       border-top:1px solid var(--border-sutil)}
  .dica .viva:empty{display:none}
  .dica .viva:has(.nada){display:none}

  /* ---------- O `?` QUE TEM ALGO A DIZER SE ACENDE — 07/09/2026 ----------
     A razão inteira está no comentário de `ajuda()`, e a curta é a palavra
     de 05/09: *"ninguém passa o rato onde não sabe que há algo"*.

     O SELETOR LÊ O CONTEÚDO VIVO, e é isso que o impede de mentir. Ele não
     acende porque o `?` foi MARCADO no desenho — acende porque existe, ali
     dentro, uma `.viva` que não está vazia e não traz o `<i class="nada">` com
     que o pacote diz *não há o que dizer*. São os MESMOS dois marcadores de
     apagar da regra logo acima, e de propósito: se um dia um terceiro jeito de
     "nada a dizer" aparecer, ele apaga a frase e apaga o ponto no mesmo tique,
     em vez de deixar um ponto aceso sobre um travessão.

     A MORDIDA: apague o `:has()` e o ponto acende em todo `?` marcado, com a
     máquina em silêncio — que é a promessa falsa que esta casa persegue. A
     régua está em `_conferir` (a 6c) e no
     `test_a_06_as_tres_frases_do_pe_couberam_no_ponto_de_interrogacao`.

     É UM PONTO, E NÃO UMA COR NOVA: o `--cyan` já é a cor com que o próprio `?`
     responde ao ponteiro nesta casa (`topo.html`), então o aceso e o hover
     falam a mesma língua. O ponto fica FORA do círculo, no canto de cima, para
     não disputar os 17px com o "?" desenhado dentro dele.

     ---- POR QUE `> :not(.nada)` E NÃO `:not(:has(.nada))` ----

     A PRIMEIRA VOLTA DESTA REGRA ESTAVA MORTA, e passou verde. Ela era
     `:has(.viva:not(:empty):not(:has(.nada)))` — um `:has()` DENTRO de um
     `:has()`, que a especificação proíbe. O navegador não avisa: descarta a
     regra inteira, calado. Medido com `el.matches()` em Chrome:

         .ajuda.tem-viva:has(.viva:not(:empty):not(:has(.nada)))  → SyntaxError
         .ajuda.tem-viva:has(.viva > :not(.nada))                 → funciona

     A RÉGUA DESSA REGRA DAVA VERDE, porque procurava o texto do seletor no
     documento — e o texto estava lá. *A régua respondia sobre o próprio texto
     do código, não sobre o produto*, que é a assinatura das seis de 05/09.
     Quem revelou foi ABRIR e olhar a cor.

     O QUE O SELETOR VÁLIDO EXIGE, e está declarado porque é um contrato: a
     frase viva tem de trazer ao menos UM elemento. As três trazem —
     `_a_razao_do_portao` embrulha em `<span class="laranja">`, e as outras duas
     começam em `<b>` (`frase_do_teclado_na_tela`, `RESSALVA_DOS_GLOBAIS`). Uma
     frase pelada acenderia a dica e não acenderia o ponto. Isso NÃO fica ao
     acaso: a régua 6d do `_conferir` chama as três funções e reprova a que
     voltar sem marcação. */
  .ajuda.tem-viva:has(.viva > :not(.nada)){
       border-color:var(--cyan);color:var(--cyan)}
  .ajuda.tem-viva:has(.viva > :not(.nada))::after{
       content:"";position:absolute;top:-2px;right:-2px;width:6px;height:6px;
       border-radius:50%;background:var(--cyan)}
  .dica .viva .verde{color:var(--green)} .dica .viva .laranja{color:var(--orange)}
  .dica .viva tt{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px}

  /* ---- O STATUS DO MODO (27/08, ela: "Status do Modo: ao clicar no botão
          Ligado. Ao clicar nele de novo desligado.") — o dono do que os dois
          botões suspensos faziam embaixo.

          A COR SAI DE UMA CLASSE, e não mais do `:checked` de um input —
          03/09/2026. O desenho nascia `<input checked>`, a palavra saía de um
          `content:` de CSS, e o produto não tinha por onde escrever nenhum dos
          dois: a tela dizia **Ligado** com `mouse_emulation.enabled=false` no
          daemon do usuário. Pior, clicar no `<label>` virava a caixa no DOM mesmo
          quando o gesto RECUSAVA — a tela trocava de lado sozinha e nada a
          devolvia.

          O piloto ganhou o alvo `classe` em 02/09 (`hefesto_vivo.py:458`), e é
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

     A TIRA DE ESTADOS SAIU DAQUI EM 07/09/2026, e a metade que ela pedia
     ficou: a frase *"escreve ao lado, na tira de estados"* caducou por ordem
     de produto (*"essas 3 frases … quebram o layout"*) — a razão foi para o `?` do
     "Status do Modo", que é a linha deste interruptor. O *"apaga o
     interruptor"* continua letra por letra, e é o que estas três regras fazem.

     UM CAMPO SÓ, E NENHUM SEGUNDO ENDEREÇO: a razão é escrita num endereço só
     (`data-campo="modo-portao"`), e o cinza do interruptor SAI DELE por
     `:has()`. Com dois campos seria possível pintar um interruptor
     apagado sem razão, ou uma razão sem interruptor apagado — que é exatamente
     o que a peça `monta.botao_cinza` evita do outro lado, e pela mesma regra.
     Aqui não dá para usar aquela peça: ela emite um `.btn`, e o "Status do
     Modo" é o rótulo `.tog` que o usuário pediu em 27/08.

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
         `pointer-events:none`"*, e o usuário pediu **não clicável**. Agora é.

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
     linha, e o interruptor fica como sempre foi.

     A REGRA PARTE DO ENDEREÇO, E NÃO MAIS DA CLASSE — 07/09/2026. Ela dizia
     `.quadro-corpo:has(.estado.portao .laranja)`, e as duas classes só existiam
     porque a razão morava na tira de `.estados`. A frase desceu para o `?` do
     "Status do Modo" por ordem de produto (*"essas 3 frases … quebram o layout"*), e
     uma regra ancorada em `.estado.portao` teria parado de apagar o interruptor
     **em silêncio**: a razão continuaria chegando, o interruptor voltaria a
     parecer clicável, e nada reprovaria. O `data-campo` é o que não muda de
     lugar — é o endereço pelo qual o pacote escreve.

     ISTO É O CINZA, E ELE FICA NA TELA SEM HOVER NENHUM. O que foi para o `?`
     é a RAZÃO, em palavras; o sinal de *não dá para mexer* continua sendo o
     próprio interruptor apagado, como a 06-Q1 pediu. ---------- */
  .quadro-corpo:has([data-campo="modo-portao"] .laranja)
       .at-linha:has(.tog[data-gesto="modo"]){cursor:not-allowed}
  .quadro-corpo:has([data-campo="modo-portao"] .laranja) .tog[data-gesto="modo"]{
       border-color:var(--border-sutil);color:var(--texto-mudo);pointer-events:none}
  .quadro-corpo:has([data-campo="modo-portao"] .laranja) .tog[data-gesto="modo"]:hover{
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
     **ficam** — é a D-15 dela, ** — **com a marca de que não disparam**. A marca nasce FIXA: a
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

     `.tn-cx` ESCOPA A REGRA: as tabelas da ABA (os seis combos) continuam com
     os 176px que o usuário aprovou — lá não há marca nenhuma a caber. */
  .tn-cx .tab th:first-child,.tn-cx .tab td.b{width:250px}

  /* A DENSIDADE DE 22px FICA SÓ DENTRO DAS TELAS DE CIMA, e o número diz por quê.
     Cada uma das duas telas de botões tem uma lista por linha, e a caixa mede
     657px com elas a 22px — REMEDIDO em 06/09/2026, com a 22ª linha (o botão
     PS): eram 634px com 21. No token de 36 as linhas sozinhas passariam de
     750px, e a janela do produto tem 757. A tela não caberia na tela.
     Na ABA, onde há seis linhas e não vinte e duas, o token vale: veja
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
    """O qualificador ao lado do glifo — SEMPRE com a primeira letra maiúscula."""
    return f'<span class="rot-gl">{txt[:1].upper()}{txt[1:]}</span>'


def _um(pid, rot=None, tam=18):
    """Um glifo do mapa, com o nome do mapa ao lado quando ele não se lê sozinho."""
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

# existia em `core/acoes_de_botao.ACOES`, do lado do produto, e as duas JÁ
ACOES_UNI = por_grupo()
ACOES_DO_PS = por_grupo("ps")

# do DualSense era texto solto.
REMAP = [
    ("Botões", [nome_de(i) for i in _ids("face")]),
    ("Ombros e gatilhos", [nome_de(i) for i in _ids("ombros") + _ids("gatilhos")]),
    ("Analógicos", [x for i in _ids("analogicos") for x in _alvo(i)]),
    ("Direcional", [nome_de(i) for i in _ids("direcional")]),
    ("Sistema", [x for i in _ids("centro") for x in _alvo(i)]),
    ("", ["— Sem troca —"]),
]
#: seguia fazendo o de fábrica. O dono do vocabulário é `core/acoes_do_gesto`,
ACOES_GESTO = _acoes_do_gesto.por_grupo()


def drop(grupos, escolhido, classe="campo-linha", gesto="", linha="", campo="",
         apagado=False):
    """Um <select> de verdade em TODA linha — nenhum travado (falas [55], [57], [91]).

    O `gesto` NOMEIA o campo para o piloto (ver `simples`), e é o que faz o
    `change` chegar ao Python.

    FATO SUBSTITUÍDO (02/09/2026, segunda correção): aqui estava escrito que
    *"as listas das três telas de pop-up ficam SEM `data-gesto` de propósito —
    elas são os CAMPOS de um formulário cujo ponto de gravação é o Guardar"*. A
    primeira metade caducou com a decisão de 02/09 (*"as 21 listas param de
    ser repintadas enquanto ela está mexendo"*): sem nome, o `change` de uma
    linha **não chega ao Python** — o `closest` do ouvinte
    (`hefesto_vivo.py:189`) não conhece `data-campo` nem `data-linha` —, e sem
    ele o pacote não tem como saber que ela está mexendo. As 21 linhas de *o que
    cada botão faz* passaram a levar `gesto=LINHA_DE_BOTAO`. A segunda metade
    continua de pé: **o ponto de gravação é o "Guardar"**, e este gesto não
    grava nada.

    FATO SUBSTITUÍDO (13/09/2026, F1-REMAPEAR): aqui estava escrito que *"as
    duas outras telas continuam sem `gesto` e sem `campo`"*, porque os
    "Guardar" delas não tinham dono. As duas ganharam dono — o do Estilo
    Point-and-click em 11/09 e o da troca de botões em 13/09 —, e as duas
    passaram a levar `gesto`, `linha` e `campo` pela mesma razão das 21 daqui.

    FATO SUBSTITUÍDO (02/09/2026): aqui estava escrito que as 49 listas ficam
    "sem nome" porque só o Guardar importa. **Sem nome elas nunca são pintadas**,
    e um formulário que não é pintado mostra o DESENHO, não o perfil do usuário —
    enquanto o Guardar lê essas mesmas linhas e as grava. Medido contra a página
    publicada: as 21 opções cravadas são exatamente `acoes_de_botao.padrao()`, e
    o Guardar gravava `button_actions = None`, apagando em silêncio o que ela
    tivesse escolhido. As 21 linhas de *o que cada botão faz* passaram a levar
    `campo`. As duas outras telas ficaram sem enquanto os gestos delas
    (`guardar-ponto`, `guardar-remapeamento`) não tinham dono — pintar um
    formulário que ninguém grava seria a metade errada da cura —, e passaram a
    ter quando o dono nasceu (11/09 e 13/09/2026).

    O `apagado` TRAVA A LISTA — 13/09/2026, F1-REMAPEAR-02 — e é a exceção, com
    dono, ao "nenhum travado" do título: as seis linhas que a troca de botões
    não alcança (`_lista_da_troca`). Elas continuam `<select>` na linha e
    mostram o estado real; a razão de travar está no docstring de lá.
    """
    partes = []
    for rot, ops in grupos:
        op = "".join(f'<option{" selected" if o == escolhido else ""}>{o}</option>' for o in ops)
        partes.append(f'<optgroup label="{rot}">{op}</optgroup>' if rot else op)
    g = f' data-gesto="{gesto}"' if gesto else ""
    ln = f' data-linha="{linha}"' if linha else ""
    # opções (ver `simples`). O ouvinte da forma prefere o `data-linha`
    c = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    ap = " disabled" if apagado else ""
    return f'<select class="{classe}"{g}{ln}{c}{ap}>{"".join(partes)}</select>'


def simples(ops, classe="escolha-at", gesto="", campo="", escolhido=""):
    """Um `<select>` das opções, com o ENDEREÇO do clique e o da PINTURA.

    O `data-gesto` liga o campo **desde 01/09/2026**, e a frase que estava aqui
    ("nenhum `<select>` desta casa liga") caducou no mesmo dia: o piloto passou a
    ouvir `change` além de `click` (`hefesto_vivo.py:75`) e a mandar o `valor` e
    o `rotulo` da opção escolhida. O motivo antigo era real — o clique num
    `<select>` chega quando a lista ABRE, com o valor ANTIGO —, e é exatamente o
    que o `change` resolve.

    O `campo` é o SEGUNDO endereço, e ele não é enfeite: sem ele a lista fica
    mostrando o que o usuário escolheu mesmo quando o gesto RECUSOU, porque a recusa
    de um gesto só imprime no terminal (`hefesto_vivo.py:341`) — na tela não
    aparece nada. Com ele, o tique seguinte reescreve o `value` com o que o
    DAEMON diz, e a opção sem dono volta sozinha para o lugar. É a única forma
    de uma recusa ser visível nesta aba.

    `data-hef-alvo="valor"` é obrigatório junto: sem ele a pintura escreveria o
    texto DENTRO do `<select>` (o alvo padrão do `escrever` é `textContent`) e
    comeria as opções.

    O `escolhido` NASCEU EM 02/09/2026, e a razão é a decisão de produto sobre a
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

    DECISÃO, 05/09/2026. Ela substitui o :func:`bignum` de `−`/`+` nas duas linhas
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


#: pacote, a cada tique.
def ajuda(txt, largura="", vivas=()):
    st = f' style="width:{largura}"' if largura else ""
    corpo = txt + "".join(
        f'<span class="viva" data-campo="{c}" data-hef-alvo="html">'
        f'{NADA_A_DIZER}</span>' for c in vivas)
    cls = "ajuda tem-viva" if vivas else "ajuda"
    return (f'<span class="{cls}" tabindex="0">?'
            f'<span class="dica"{st}>{corpo}</span></span>')

# aba navegAção."* <!-- noqa-acento: citação literal --> O PS + L3 anda
#: O de fábrica de cada linha sai do produto (`acoes_do_gesto.PADRAO`), e as
COMBOS = [(g.numero, g.pecas, _acoes_do_gesto.rotulo(_acoes_do_gesto.PADRAO[g.chave]))
          for g in _acoes_do_gesto.GESTOS.values()]
_GESTO_DA_LINHA = {g.numero: g.chave for g in _acoes_do_gesto.GESTOS.values()}

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


CSS += "\n  /* ---- o desenho acompanha o combo apontado, sem uma linha de script ---- */\n"
CSS += REALCE + "\n"


_FOLHA_NO_SVG = re.compile(
    r'<style id="[^"]*cores-do-dualsense-folha">.*?</style>', re.S)

CSS += _marca.CSS
CSS += "\n  /* ---- as 28 cores do mapa, publicadas UMA vez ---- */\n"
CSS += re.sub(r"</?style[^>]*>", "", folha_das_cores())


# por controle — na página saíram `p1-hachura-sem-hex` … `p4-hachura-sem-hex`.
# A folha da página continuou dizendo `url(#hachura-sem-hex)`, que já não existe
# em lugar nenhum: `document.getElementById('hachura-sem-hex')` devolvia **null**
# tinta — `grep 'id="hachura-sem-hex"' mockup/*.html` mostra o buraco.
_ABRE_A_TINTA = '<defs id="cores-do-dualsense">'
if _ABRE_A_TINTA not in DS or DS.index(_ABRE_A_TINTA) > DS.index(
        '<style id="cores-do-dualsense-folha">'):
    raise SystemExit(
        "ERRO em 06-navegacao: o `<defs id=\"cores-do-dualsense\">` sumiu do "
        "ds_limpo.svg (ou passou a vir DEPOIS da folha) — os doze modelos que "
        "pintam por `url(#…)` ficariam sem tinta, e o desenho deles some da "
        "tela. Rode scripts/gerar_cores_do_dualsense.py")

TINTA_DOS_28 = (DS[DS.index(_ABRE_A_TINTA):
                   DS.index('<style id="cores-do-dualsense-folha">')] + "</defs>")

#: `position:absolute` tira do FLUXO, não da lista de irmãos — `:first-child`,
BLOCO_DA_TINTA = (
    '\n        <!-- A TINTA DOS 28 — os servidores de pintura que a folha das\n'
    '             cores pede por `url(#…)`. Sem eles, doze modelos dela viram\n'
    '             endereço morto e o desenho SOME. Ver `TINTA_DOS_28`.\n'
    '             FICA NO FIM: no começo ele quebra o `.quadro:first-child`. -->\n'
    '        <svg class="cores-do-dualsense" aria-hidden="true" focusable="false"\n'
    '             width="0" height="0" style="position:absolute;overflow:hidden">'
    f'{TINTA_DOS_28}</svg>\n')


def tinta_referenciada():
    """Os `id` que a folha dos 28 pede por `url(#…)` — lidos, nunca digitados."""
    return sorted(set(re.findall(r"url\(#([^)]+)\)", folha_das_cores())))


def zonas_do_desenho():
    """As classes de zona, LIDAS da folha do mapa — nunca digitadas aqui."""
    zonas = sorted(set(re.findall(
        r'svg\[data-colorway="[^"]+"\] (\.z-[a-z0-9_]+)', DS)))
    if not zonas:
        raise SystemExit("ERRO em 06-navegacao: a folha do mapa não declara "
                         "mais zona nenhuma — veja ds_limpo.svg")
    return zonas


CSS += "\n  /* ---- desenho sem identidade: as zonas ficam no neutro ---- */\n"
CSS += "".join(
    f'  .nav-ctl .ds-svg:not([data-colorway]) {z}'
    f' :is(path,rect,circle,ellipse,polygon):not([fill="none"])'
    f"{{fill:var(--border-forte) !important}}\n"
    for z in zonas_do_desenho())


ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo"'
                       ' data-hef-atributo="data-colorway"')


def desenho(c, **kw):
    """O DualSense do cartão, ENDEREÇADO e sem a folha podada dentro.

    Duas coisas, e as duas são a mesma cura vista de lados opostos:

    * a folha embutida SAI. Ela traz um modelo só, e a página já publica os 28
      (ver `folha_das_cores`). Mantê-la seria a mesma tabela quatro vezes, e a
      podada é justamente a que impede o desenho de virar outro aparelho;
    * o `<svg>` ganha `ENDERECO_DO_DESENHO`. Sem ele o `data-colorway` fica
      sendo o do MOCKUP para sempre — era o defeito que o usuário nomeou.

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


VAZIO = "—"


def controle(c):
    """UM lugar da mesa — cheio ou vazio, pela MESMA função e com os MESMOS
    endereços. O `conectado` decide só duas coisas: (a) a classe e os atributos
    de estado da casca, e (b) o TEXTO INICIAL de cada campo.

    POR QUE ELA É UMA SÓ — 07/09/2026, O-LUGAR-VAZIO-TEM-ENDERECO. Até hoje
    havia `controle()` e `controle_vazio()`, duas funções que desenhavam a mesma
    caixa, e **uma envelheceu sem a outra**: a cheia ganhou
    `data-campo="identidade"` e `data-campo="navega"` em 03/09, a vazia não.

    O QUE ISSO CUSTOU, medido nesta aba com os QUATRO DualSense do usuário na mesa:
    o daemon publicava quatro controles, a carga chegava com
    `colunas = {p1, p2, p3, p4}` e `ocupados` com os quatro — e a tela mostrava
    DOIS. O passo 2 do piloto faz `achar(raiz, k)`, que procura `data-campo="k"`
    **dentro** do bloco `[data-controle]`; sem endereço, o dado dela chegava e
    não tinha onde pousar. O P3 e o P4 seguiam dizendo `P3 • Desconectado` com
    travessão em tudo, com o aparelho ligado na mão do usuário.

    ``p1: 3 campos · p2: 3 · p3: 1 · p4: 1`` era a medida da página publicada.

    O ESTADO INICIAL CONTINUA SENDO O DESENHO DO USUÁRIO: o lugar vazio nasce com
    `class="nav-ctl vazia"`, `data-conectado="nao"` e o travessão. **Quem os
    tira é o piloto**, no passo `1c`, quando o controle chega — e agora ele tem
    onde escrever o que o controle diz. A `monta.MESA` não muda: ela é o desenho
    aprovado (dois cheios, dois vazios); o que mudou é a ESTRUTURA que o gerador
    emite para o lugar vazio.

    ---- o que o estado decide, e é só isto ----

    (a) A CASCA. `class="nav-ctl vazia"` contra `nav-ctl [navega]`; o
        `style="color:…"` do plástico, que o lugar vazio não tem (a regra
        `.nav-ctl.vazia{border:1px solid var(--border-forte)}` é quem lhe dá
        caixa — uma `var(--plastico)` indefinida invalidaria a declaração
        inteira); o `data-conectado`; e o `title` que diz que ali não há
        ninguém.

    (b) O TEXTO INICIAL. O nome do plástico contra `Desconectado`, e a linha do
        transporte contra o travessão. Nada mais.

    ---- o que NÃO muda com o estado, e é o ponto desta função ----

    Os cinco endereços saem iguais nos quatro lugares:
    `data-campo="plastico" data-hef-alvo="cor"` na casca,
    `ENDERECO_DO_DESENHO` no `<svg>` (ver `desenho`),
    `data-campo="identidade"` no rótulo e `data-campo="navega"` na linha de
    estado. `_conferir` mede isso na SAÍDA, lugar a lugar.

    A IDENTIDADE DESTE CARTÃO VEM DE CIMA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA.
    Três coisas mudaram então, e as três eram o desenho mandando na tela:

    * a cor do plástico saiu do `style="--plastico:#hex"` e virou
      `style="color:#hex"` com `data-campo="plastico" data-hef-alvo="cor"`. É o
      ÚNICO canal de cor que o piloto tem (`hefesto_vivo.escrever`, ramo
      `cor`), e ele escreve `style.color` — que a borda passou a ler por
      `currentColor`. Sem leitura, a cor volta ao neutro do CSS;
    * o `title` que dizia `Player 1 • Cosmic Red • USB` SAIU. Ele repetia o que
      o cartão já mostra em texto, e um `title` não tem alvo de pintura: ficaria
      nomeando o controle do mockup para sempre, por cima do rótulo já vivo.
      (O `title` do lugar VAZIO fica: ele não nomeia aparelho nenhum, diz que
      não há aparelho.);
    * o nome do plástico virou `<span data-campo="identidade">`, que o pacote
      escreve com `pacotes.identidade_de` — o dono do nome desde a ROTA-A. O
      `P{n}` fica FORA do span de propósito: o número do jogador é ESTRUTURA
      (a posição na mesa), e a lei do dia diz para não tocá-lo.

    E O DESENHO SEGUIU — 03/09/2026, A-COR-VEM-DO-APARELHO. O `<svg>` ganhou o
    `ENDERECO_DO_DESENHO` e perdeu a folha podada de um modelo só (ver
    `desenho`). Era a última coisa deste cartão que ainda nomeava o controle do
    mockup: com o P1 dela em White, o `<svg>` dizia `cosmic-red`.

    O PIXEL JÁ ESTAVA CERTO, E O MECANISMO NÃO — medido no WebKit em 03/09, com
    os dois controles do usuário na mesa: o casco do P1 saía `rgb(228, 224, 216)`,
    que é o White do mapa, porque a `a06_navegacao.folha_do_plastico`
    sobrescrevia as variáveis. Só que as REGRAS que leem essas variáveis são
    `svg[data-colorway="cosmic-red"] …`: elas casavam **porque o atributo do
    mockup tinha ficado**. Ligar o atributo — que é o que a lei de produto pede —
    teria apagado a cor em vez de acertá-la, e é por isso que a página passou a
    publicar os 28 modelos no mesmo movimento.

    O DESENHO DO LUGAR VAZIO TAMBÉM É ENDEREÇADO, e não é enfeite: o piloto
    distribui uma LISTA pelos elementos de mesmo `data-campo`, NA ORDEM do HTML
    (`hefesto_vivo`, `alvos.forEach(…, i)`). Um lugar vazio sem endereço tiraria
    uma casa da fila e o P4 receberia a cor do P3. O valor que ele recebe é `""`,
    que APAGA o `data-colorway` — e o desenho cai no neutro que as regras
    `.nav-ctl.vazia .ds-svg` já pintam.

    O `data-controle` do lugar vazio é decisão, 03/09/2026, e ela a
    enunciou assim:  — o `data-controle` chegou naquele
    dia; os campos DE DENTRO chegam hoje, e sem eles a segunda metade da frase
    de produto não acontecia.
    """
    n = c["jogador"]
    conectado = bool(c.get("conectado", True))
    navega = conectado and n == NAVEGA
    classe = f'nav-ctl{" navega" if navega else ""}' if conectado else "nav-ctl vazia"
    tinta = f' style="color:{cor_da_zona(c["cor"])}"' if conectado else ""
    dica = "" if conectado else ' title="Nenhum controle neste lugar."'
    luz = {"luz": _hex(player_slot_color(n))} if conectado else {}
    identidade = c["nome"] if conectado else SEM_NINGUEM_AQUI
    estado = _linha_do_cartao(c["via"], navega) if conectado else VAZIO
    return (
        f'              <div class="{classe}"{tinta}'
        f' data-controle="{c.get("uniq") or c["pref"]}"'
        f' data-conectado="{"sim" if conectado else "nao"}"'  # (noqa-acento) valor do atributo
        f' data-campo="plastico" data-hef-alvo="cor"{dica}>\n'
        f'                {desenho(c, **luz)}\n'
        f'                <div class="nav-rot">P{n} <span class="pt">•</span> '
        f'<span data-campo="identidade">{identidade}</span></div>\n'
        f'                <div class="nav-est" data-campo="navega"'
        f' data-hef-alvo="html">{estado}</div>\n'
        f'              </div>')


def linha_combo(n, pecas, faz):
    nomes = [glifo(gl_de(p), tam=18) if p == "ps" else _um(p) for p in pecas]
    combo = ' <span class="mais">+</span> '.join(nomes)
    return (f'                <tr class="g g{n}"><td class="b">'
            f'<span class="gls"><span class="mk-n">{n}</span>{combo}</span></td>'
            f'<td>{drop_do_gesto(_GESTO_DA_LINHA[n], faz)}</td></tr>')


def drop_do_gesto(chave, faz):
    """A lista de UM gesto, com o endereço de leitura e o de pintura."""
    lista = drop(ACOES_GESTO, faz, gesto="acao-do-gesto", linha=chave,
                 campo=PREFIXO_DO_GESTO + chave)
    rotulo = _acoes_do_gesto.rotulo(_acoes_do_gesto.SCRIPT)
    return lista.replace(f"<option>{rotulo}</option>",
                         f'<option data-campo="{PREFIXO_DO_SCRIPT}{chave}">{rotulo}</option>')

#: O PADRÃO DE CADA LINHA VEM DO PRODUTO — `core/acoes_de_botao.padrao()`, que
_PADRAO_DOS_BOTOES = {b: rotulo_da_acao(a)
                      for b, a in _padrao_dos_botoes().items()}

MARCA_DO_TOUCHPAD = (
    '<span class="marca-nao-dispara" title="O touchpad é o ponteiro do '
    "computador nesta máquina; enquanto for assim, o clique dele não vira "
    'tecla. A escolha fica guardada.">'
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
    (gl("dpad_up",    rot=dir_de("dpad_up")),    "dpad_up"),
    (gl("dpad_down",  rot=dir_de("dpad_down")),  "dpad_down"),
    (gl("dpad_left",  rot=dir_de("dpad_left")),  "dpad_left"),
    (gl("dpad_right", rot=dir_de("dpad_right")), "dpad_right"),
    (gl("options"),                              "options"),
    (gl("share"),                                "create"),
    # MESMA de `core/acoes_de_botao.BOTOES`. As duas ordens não se comparam por
    # própria de resolução (`acoes_de_botao.acao_do_ps`) e tem atendente
    (gl("ps"),                                   "ps"),
    # máquina só esconde os touchpads VIRTUAIS — o físico do DualSense continua
    (gl("touchpad", rot=TOUCH_REGIOES[0]) + MARCA_DO_TOUCHPAD, "touchpad_left_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[1]) + MARCA_DO_TOUCHPAD, "touchpad_right_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[2]) + MARCA_DO_TOUCHPAD, "touchpad_middle_press"),
]
SEM_TROCA = REMAP[-1][1][0]

_ROTULOS_DO_DESENHO = {o for _g, ops in REMAP[:-1] for o in ops}
if set(ROTULOS_DA_TROCA) != _ROTULOS_DO_DESENHO or _SEM_TROCA_DO_PACOTE != SEM_TROCA:
    raise SystemExit(
        "ERRO: a lista de destinos da tela 'Trocar os botões' divergiu de "
        "`pacotes/a06_navegacao.ROTULOS_DA_TROCA` — a mais no desenho: "
        f"{sorted(_ROTULOS_DO_DESENHO - set(ROTULOS_DA_TROCA))}; a menos: "
        f"{sorted(set(ROTULOS_DA_TROCA) - _ROTULOS_DO_DESENHO)}; sem troca: "
        f"{SEM_TROCA!r} x {_SEM_TROCA_DO_PACOTE!r}")

D_QUANDO = ajuda(
    "Vale para <b>este perfil</b>. <b>Desligado</b>, o controle "
    "é só gamepad e nada desta aba chega ao PC, até você entrar na Navegação "
    "de novo.",
    vivas=("modo-portao",))
D_TECLADO = ajuda(
    "Liga o que o controle <b>digita</b>: os atalhos das telas de botões, o teclado "
    "na tela e as três regiões do touchpad. Vale para este perfil.",
    vivas=("teclado-osk", ENDERECO_DA_RESSALVA))
D_MOUSE = ajuda(
    "Os <b>mapeamentos pré-prontos</b> de mouse. Trocar aqui reescreve as linhas "
    "da tabela <b>O controle como mouse</b>; qualquer linha continua "
    "editável depois.")
D_VEL_TXT = (
    f"Vale para o <b>analógico esquerdo</b> e para o <b>touchpad</b>. "
    f"De {MOUSE_SPEED_MIN} a {MOUSE_SPEED_MAX}; o padrão é "
    f"{DEFAULT_MOUSE_SPEED}.")
D_ROL_TXT = (
    f"Vale para o <b>analógico direito</b>. "
    f"De {SCROLL_SPEED_MIN} a {SCROLL_SPEED_MAX}; o padrão é "
    f"{DEFAULT_SCROLL_SPEED}.")
D_VEL = ajuda(D_VEL_TXT, vivas=(ENDERECO_DA_RESSALVA,))
D_ROL = ajuda(D_ROL_TXT, vivas=(ENDERECO_DA_RESSALVA,))
D_VEL_ESTILO = ajuda(D_VEL_TXT)
D_ROL_ESTILO = ajuda(D_ROL_TXT)
D_INTERNA = ajuda(
    "Navegar o Hefesto com o controle — abas, botões e listas.<br><br>"
    "O cursor do PC é outra coisa: é <b>um só</b>, e sai do controle marcado "
    "«Navega o PC».")
D_STEAM = ajuda(
    "Serve para navegar a <b>Steam</b> sem mouse, com o d-pad e os botões.")

# AS DUAS SAEM COM A MESMA MUDANÇA: o `<input>` some, a cor passa a ser a classe
STATUS_MODO = ('<label class="tog" data-gesto="modo" data-campo="rato-ligado"'
               ' data-hef-alvo="classe" data-hef-classe="ligado"'
               ' data-hef-quando="Ligado">'
               '<span class="pino"></span>'
               '<span class="txt" data-campo="rato-ligado">—</span></label>')

#: o escreve com `pacotes.identidade_de` + `pacotes.jogador_de` do PRIMÁRIO —
VALEM_PARA = (
    'Valem para o controle que navega o PC: o <b data-campo="quem-navega">'
    + rotulo_de_quem_navega(NAVEGA, QUEM_NAVEGA["nome"], QUEM_NAVEGA["via"])
    + "</b>.")

#:   · **o botão PS, e o parágrafo VIROU O CONTRÁRIO em 06/09/2026.** Ele dizia
#:     (§2 `06[03]`), que **a palavra de produto reverteu** na 06-Q3: *"O PS ganha a
#:     a digitar SEM parar de abrir a Steam."*
D_DEFINICOES = ajuda(
    f"As <b>{len(BOTOES)} linhas</b> de cada botão: <b>o que ele faz</b> "
    "— mouse, tecla ou programa, na mesma lista.<br><br>"
    "O <b>PS</b> continua sendo a saída de emergência — os "
    f"{len(COMBOS)} gestos desta aba saem dele. O que o toque nele faz no "
    "computador é o <b>⑥</b> dos gestos; aqui ele só ganha uma tecla, que "
    "acontece <b>junto</b>, no toque curto e fora do jogo.<br><br>"
    "Enquanto o touchpad for o ponteiro do computador, o clique dele não vira "
    "tecla — as três regiões ficam marcadas e a escolha fica guardada.<br><br>"
    + VALEM_PARA)
D_REMAPEAMENTO = ajuda(
    f"As mesmas <b>{len(BOTOES)} linhas</b>, na mesma ordem, dizendo outra coisa: "
    "<b>para qual outro botão</b> cada um passa a valer. O que cada botão "
    "<b>faz</b> se escolhe na tela <b>Definições Controle e Mouse</b>.")

OPCOES_TECLADO = [
    "Só dentro do jogo",
    "Só fora do jogo",
    "Desativado",
]

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

ATIVACAO_DIR = [
    # (`vel-cursor-menos`/`-mais`, `rolagem-menos`/`-mais`): quem atende as
    ("Velocidade de cursor", D_VEL,
     trilho(DEFAULT_MOUSE_SPEED, MOUSE_SPEED_MIN, MOUSE_SPEED_MAX,
            "vel-cursor", "vel-cursor",
            "Vale na hora.")),
    ("Velocidade da rolagem", D_ROL,
     trilho(DEFAULT_SCROLL_SPEED, SCROLL_SPEED_MIN, SCROLL_SPEED_MAX,
            "vel-rolagem", "vel-rolagem",
            "Vale na hora.")),
    ("Modo Steam", D_STEAM, simples([
        "Desligado",
        "Ligado — o controle navega a Steam como num Steam Deck",
        "Ligado, e a Steam abre em Modo Jogo na próxima vez"], gesto="modo-steam")),
]

#:                        e `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`). É a linha que
#:                        `app/actions/emulation_actions.descrever_teclado_emulado`.
#:                        `app/actions/input_actions.frase_do_teclado_na_tela`.
#: `frase_do_teclado_na_tela`. O alvo padrão escreveria `<b>` como texto na tela
#:   · `modo-portao`   §2 `06[01]`: a razão de o interruptor do "Status do Modo"
#:                     frase desta linha e, pela regra `:has()` da folha desta
#:                     aba, o cinza do próprio interruptor. A frase é a MESMA
ESTADOS = '''
        <div class="estados">
          <div class="estado" data-campo="rato-estado" data-hef-alvo="html"></div>
          <div class="estado" data-campo="teclado-bloqueio" data-hef-alvo="html"></div>
          <div class="estado" data-campo="teclado-custo" data-hef-alvo="html"></div>
        </div>'''

FILEIRA = '''
            <div class="acoes quatro grupo-padrao">
              <a class="btn roxo" href="#definicoes-mouse">Definições Controle e Mouse</a>
              <a class="btn roxo" href="#remapeamento">Trocar os botões</a>
              <a class="btn roxo" href="#point-and-click">Estilo Point-and-click</a>
              <!-- O RÁDIO VEM ANTES de tudo o que reage a ele: o `~` do CSS só
                   enxerga irmão POSTERIOR. É a mesma armadilha que o interruptor
                   da aba Jogar documenta, e a mesma cura. -->
              <input type="checkbox" id="conf-padrao" class="abre-conf">
              <label for="conf-padrao" class="btn btn-padrao">Voltar ao padrão</label>
              <label for="conf-padrao" class="veu" title="Fecha sem mudar nada."></label>
              <div class="confirma">
                <span>Voltar ao padrão o mouse, as Definições e as teclas? No jogo
                  que os escolheu, volta o do computador; sem jogo, o computador
                  volta ao de fábrica, e os gestos também. A troca de botões fica.</span>
                <!-- O ENDEREÇO VAI NO "Confirmar", nunca no "Voltar ao padrão":
                     o de cima só ABRE a pergunta (é `<label for>` do mesmo
                     checkbox, e funciona), e marcá-lo faria o piloto acusar de
                     sem dono um botão que faz o que promete. -->
                <label for="conf-padrao" class="btn-conf vermelho" data-gesto="padrao-da-aba">Confirmar</label>
                <label for="conf-padrao" class="btn-conf">Cancelar</label>
              </div>
            </div>'''

#: `core/acoes_de_botao.BOTOES`, e é o que faz a linha SER GRAVADA: sem ela o
#: MESMO campo do perfil (`Profile.button_actions`), e um segundo endereço para
#: precisa virar dado com dono — e isso é decisão de produto.
PONTO_MAPA = [
    (gl("touchpad", rot="deslizar"), "Movimento do cursor", ""),
    (gl("touchpad", rot=TOUCH_REGIOES[0]) + MARCA_DO_TOUCHPAD,
     "Botão esquerdo", "touchpad_left_press"),
    (gl("touchpad", rot=TOUCH_REGIOES[1]) + MARCA_DO_TOUCHPAD,
     "Botão direito", "touchpad_right_press"),
    (gl("cross"),                    "Botão esquerdo", "cross"),
    (gl("circle"),                   "Botão direito", "circle"),
    (gl("stick_l", rot="direção"),   "Movimento do cursor", EIXO_ESQUERDO),
    (gl("stick_r", rot="direção"),   "Rolagem vertical e horizontal", EIXO_DIREITO),
]

def tela_de_botoes(ident, titulo, dica, coluna, linhas, confirma, guardar, padrao,
                   fechar="", aviso="", extra=""):
    """Uma das duas telas de botões."""
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
      <!-- TEXTO NA TELA É ZERO — regra, 30/08/2026: *"texto na interface é
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


LINHA_DE_BOTAO = "linha-de-botao"

#: (`a06_navegacao._aviso_da_tabela`). Decisão do PO, 04/09/2026, §2 `06[04]`:
#: cada linha faz de `core/acoes_de_botao`. O que este bloco faz é dar LUGAR.
AVISO_DA_TABELA = ('        <div class="aviso-tabela" data-campo="aviso-da-tabela"'
                   ' data-hef-alvo="html"></div>')

TELA_DEFINICOES = tela_de_botoes(
    "definicoes-mouse", "Definições Controle e Mouse", D_DEFINICOES,
    "O que ele faz",
    chr(10).join(
        f'          <tr><td class="b">{b}</td>'
        f'<td>{drop(ACOES_DO_PS if i == "ps" else ACOES_UNI, _PADRAO_DOS_BOTOES[i], gesto=LINHA_DE_BOTAO, linha=i, campo=f"{PREFIXO_DA_ACAO}{i}")}</td></tr>'
        for b, i in BOTOES),
    # do perfil (`key_bindings` e `button_actions`), direto no disco e sem
    f"Devolver ao de fábrica as {len(BOTOES)} linhas? "
    "Isto apaga também os <b>atalhos de teclado</b> deste perfil — "
    "inclusive os de antes, que esta lista não sabe "
    "mostrar. Para voltar <b>uma linha só</b>, use o ↺ dela em "
    "<b>Teclas do teclado</b>. A tela <b>Trocar os botões</b> não é tocada.",
    guardar="guardar-definicoes", padrao="padrao-definicoes",
    fechar="fechar-definicoes", aviso=AVISO_DA_TABELA,
    extra='      <a class="btn" href="#teclas-do-teclado">Teclas do teclado</a>')

LINHA_DE_TROCA = "linha-de-troca"
FECHAR_TROCA = "fechar-troca"


def _campo_da_troca(botao):
    """O endereço de pintura da linha — só para o que a troca alcança."""
    return f"{PREFIXO_DA_TROCA}{botao}" if botao in _REMAPEAVEIS else ""


def _lista_da_troca(botao):
    """A lista de UMA linha da troca: a que troca, ou a apagada."""
    if botao in _REMAPEAVEIS:
        return drop(REMAP, SEM_TROCA, gesto=LINHA_DE_TROCA, linha=botao,
                    campo=_campo_da_troca(botao))
    return drop([("", [SEM_TROCA])], SEM_TROCA, linha=botao, apagado=True)


TELA_REMAPEAMENTO = tela_de_botoes(
    "remapeamento", "Trocar os botões", D_REMAPEAMENTO,
    "Passa a ser",
    chr(10).join(
        f'          <tr><td class="b">{b.removesuffix(MARCA_DO_TOUCHPAD)}</td>'
        f'<td>{_lista_da_troca(i)}</td></tr>'
        for b, i in BOTOES),
    f"Devolver as {len(BOTOES)} linhas ao <b>{SEM_TROCA}</b>? "
    "As <b>Definições Controle e Mouse</b> não são tocadas.",
    guardar="guardar-remapeamento", padrao="padrao-remapeamento",
    fechar=FECHAR_TROCA)

# O QUE ELA FECHA: a linha `FALTA_NO_HTML` de *Editar QUAL TECLA cada botão
# campo de TEXTO, e quem traduz é o dono (`input_actions.dehumanize_binding`),
# `acoes_de_botao.DOMINIO_DO_TECLADO`. Oferecer campo nas outras catorze faria
# `button_actions` de uma vez.

#: POR QUE ISTO IMPORTA, medido em 06/09/2026: `dehumanize_binding` casa pelo
#: "Super" mandaria a pessoa na direção da recusa.
def _exemplo_de_tecla(token):
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:  # pragma: no cover — sem GTK no ambiente do gerador
        return token
    return str(humanize_binding(token))


D_TECLAS = ajuda(
    "Escreva a tecla que o botão deve digitar — vale <b>qualquer combinação</b>."
    "<br><br>"
    f"Exemplos: <b>{_exemplo_de_tecla('KEY_LEFTALT+KEY_TAB')}</b>, "
    f"<b>{_exemplo_de_tecla('KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_F')}</b>, "
    f"<b>{_exemplo_de_tecla('KEY_F5')}</b>. "
    "<b>Campo em branco</b>: o botão não digita nada.<br><br>"
    "O <b>↺</b> devolve a linha ao de fábrica.")

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
        "Serve para jogo de <b>apontar e clicar</b>, que espera mouse e não entende "
        "controle: <b>o touchpad vira o ponteiro</b>, e o toque vira o clique.")}
      <a class="tn-x" href="#" title="Fechar" data-gesto="fechar-ponto">×</a>
    </div>
    <div class="tn-corpo">
      <!-- TEXTO NA TELA É ZERO — regra, 30/08/2026: *"texto na interface é
           zero, só deixamos se for algo extremamente importante, e se for de
           média importância vira tooltip"*. Esta frase era prosa fixa a poucos
           pixels de um `?` que explicava o mesmo assunto. Ela não sumiu: subiu
           para a dica do cabeçalho, onde só aparece a quem pergunta. -->
      <div class="moldura">
        <table class="tab">
          <tr><th>Botão do controle</th><th>O que ele faz neste estilo</th></tr>
{chr(10).join(f'          <tr><td class="b">{b}</td><td>{drop(ACOES_UNI, _PADRAO_DOS_BOTOES[i], gesto=LINHA_DE_BOTAO, linha=i, campo=f"{PREFIXO_DA_ACAO}{i}") if i else drop(ACOES_UNI, f)}</td></tr>' for b, f, i in PONTO_MAPA)}
        </table>
      </div>
      <!-- AS DICAS AQUI SÃO AS `_ESTILO`, e a diferença é uma só: elas NÃO
           levam a ressalva da D3. Ela diz que o ajuste vale para todos os
           controles ligados, e é verdade sobre as barras do painel — não sobre
           estes dois números, que são a velocidade DO ESTILO e não escrevem em
           lugar nenhum (ver o comentário dos `bignum` logo abaixo). -->
      <div class="tn-vel">
        <div class="at-linha"><span class="at-rot">Velocidade do cursor{D_VEL_ESTILO}</span>
          {bignum(("", 8))}</div>
        <div class="at-linha"><span class="at-rot">Velocidade da rolagem{D_ROL_ESTILO}</span>
          {bignum(("", 4))}</div>
      </div>
    </div>
    <!-- OS DOIS `bignum` DESTA TELA FICAM SEM ENDEREÇO, e é decisão medida: eles
         são a velocidade DO ESTILO Point-and-click, que o perfil escolhe usar —
         não a velocidade viva do daemon. Ligá-los ao `mouse.emulation.set`
         mudaria o cursor AGORA enquanto ela pensa que edita um estilo guardado,
         que é a pior forma de um botão mentir. Quem carrega o que falta é o
         "Guardar" desta tela, que é o ponto de gravação de todos eles. -->
    <div class="tn-rod">
      <!-- O "Cancelar" E O "×" GANHARAM NOME EM 11/09/2026, pela mesma razão
           que os da tela de Definições ganharam em 02/09: FECHAR É O "SAIR" da
           decisão de produto (*"as listas param de ser repintadas enquanto ela está
           mexendo, até guardar ou sair"*). Eles já fechavam a pop-up sozinhos,
           pelo `:target` do CSS; o que faltava era o Python saber que ela
           desistiu — sem isso a trava ficaria presa depois do "Cancelar", e as
           sete linhas continuariam mostrando escolha que ninguém vai guardar.
           As duas telas dividem a MESMA trava porque dividem o mesmo campo. -->
      <a class="btn" href="#" data-gesto="fechar-ponto">Cancelar</a>
      <!-- O `data-hef-forma` É O QUE FAZ ESTE BOTÃO PODER GRAVAR — 11/09/2026.
           O ouvinte do piloto manda o valor do elemento CLICADO, e o Guardar é
           outro elemento: sem a forma ele não tem como saber o que está
           escolhido em cada linha. O `id` recorta a varredura nesta pop-up, e é
           por isso que as duas telas que escrevem o MESMO campo do perfil não
           disputam a forma uma da outra. -->
      <a class="btn roxo" href="#" data-gesto="guardar-ponto"
         data-hef-forma="point-and-click">Guardar</a>
    </div>
  </div>
</div>
'''


MARCAS_DA_ATIVACAO = "        " + _marca.rotuladas(
    (("mouse", "Mouse"), ("teclado", "Teclado")))


def at_linha(rot, dica, campo):
    return (f'              <div class="at-linha"><span class="at-rot">{rot}{dica}</span>'
            f'{campo}</div>')


D_MESA = ajuda(
    "Os controles ligados agora, cada um na cor do seu plástico.<br><br>"
    "<b>O cursor do PC é um só:</b> mouse e teclado saem do controle marcado "
    "«Navega o PC» aqui embaixo; os outros chegam ao jogo e não mexem no cursor. "
    f"Os {len(COMBOS)} gestos valem em qualquer controle.<br><br>"
    "O alvo de um ajuste se escolhe na <b>fita do topo</b>; estes cartões são "
    "leitura.")

D_GESTOS = ajuda(
    "Combinações que valem <b>sem largar o controle</b>, a qualquer momento — "
    "mesmo com o jogo aberto. O que cada uma faz vale para o computador, em "
    "todo perfil e nos quatro controles.<br><br>"
    "Segure os dois <b>juntos</b> por <b>0,15 s</b>. Um toque rápido demais não "
    "vira combo: vira o PS sozinho. Com um jogo aberto, o PS sozinho é do "
    "jogo.<br><br>"
    "Um script escolhido precisa ser seu, executável e começar com <b>#!</b>; "
    "ele roda por até 60 s. Para deixar um programa aberto, o script o entrega "
    "ao sistema (xdg-open).",
    vivas=(ENDERECO_DA_DICA_DOS_GESTOS,))

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Navegação</span>
        {ajuda(
          "Usa o controle como mouse e teclado do computador — e nos jogos que "
          "só entendem mouse e teclado."
          "<br><br><b>Combinações:</b> junte teclas com &quot;+&quot; (ex.: Alt + Tab). Nenhum "
          "atalho digita letra: para escrever texto, abra o teclado na tela "
          "com o <b>L3</b>.")}
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
{chr(10).join(controle(c) for c in MESA)}
            </div>
          </div>
          <div class="combos">
            <table class="tab">
              <tr><th>Combinação</th><th>O que faz</th></tr>
{chr(10).join(linha_combo(n, p, f) for n, p, f in COMBOS)}
            </table>
          </div>
        </div>
        </div>

      </div>
    </div>

    <!-- ---------- AS OPÇÕES DE ATIVAÇÃO VIRARAM QUADRO PRÓPRIO ----------
         Pedido, 30/08: *"a parte 'As opções de ativação' coloca na mesma cor
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
{MARCAS_DA_ATIVACAO}
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
          <!-- ---------- A RESSALVA DA D3 SAIU DA MOLDURA ----------
               07/09/2026,  — e ela era a primeira das
               três, 17,25px logo abaixo da grade das sete linhas.

               A DECISÃO D3 CONTINUA CUMPRIDA, e é o que importa: `mouse`,
               `key_bindings`, `button_actions`, `teclado_emulado` e
               `suppress_desktop_emulation` seguem GLOBAIS, e a tela continua
               dizendo isso — *"onde a aba oferece um destes cinco, a linha de
               ressalva diz que o ajuste vale para a mesa inteira, não só para o
               controle selecionado"*. O que mudou é ONDE: em vez de uma linha
               sob a grade inteira, a mesma frase VIVA está no `?` dos TRÊS
               campos que ela nomeia — "Velocidade de cursor", "Velocidade da
               rolagem" e "Função do teclado" (ver `ajuda(..., vivas=…)`).

               O QUE ISSO GANHA, além dos 17px: a ressalva deixa de ressalvar as
               SETE linhas em bloco e passa a estar no campo de que fala. Ela
               nunca valeu para as sete — "Navegação Interna" é por controle
               (cada jogador anda no seu card) e "Modo Steam" já diz na própria
               dica que vale para a máquina.

               E ELA CONTINUA NASCENDO VAZIA, pelo mesmo motivo de sempre: quem
               decide se há o que ressalvar é o pacote, ao vivo, contando os
               CONECTADOS. Com UM controle ligado não há promessa quebrada, e
               uma frase cravada no desenho a afirmaria assim mesmo — que é a
               ressalva mentindo pelo desenho, o defeito da aba 08. -->
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
  <h2>O que mudou em 25/09</h2>
  <ul>
    <li><b>O cartão de quem não navega diz <i>{PAPEL_DO_CURSOR}</i> quando a
    Mira Virtual dele está acesa na Navegação.</b> O giro daquele controle já
    movia o cursor do computador, e o cartão continuava dizendo <i>{PAPEL_SO_A_JANELA}</i>.
    Fica <i>{PAPEL_SO_A_JANELA}</i> sempre que o giro não chega ao cursor: com a
    Mira apagada, com o Giroscópio daquele controle desligado, com o mouse
    parado (o Status do Modo desligado, ou em pausa no modo jogo) e fora da
    Navegação: no Sony DualSense e no Xbox a Mira vai ao analógico direito do
    jogo, e no Nativo ela não anda. O desenho mostra a Mira apagada
    nos quatro, como a aba Controles; é o produto que troca a palavra, a cada
    tique, em todo controle que não navega, no USB e no BT.</li>
    <li><b>Com três ou quatro controles conectados, o P3 e o P4 deixaram de
    aparecer apagados</b>, com a cara de lugar vazio. Eles nascem vazios no
    desenho, e a tela só tirava essa cara do P2. Agora quem está conectado
    aparece como o P2, e quem saiu fica apagado, nos quatro lugares.</li>
  </ul>

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
    sido mudança que ninguém pediu, por um defeito que não existe.
    <br><br><b>CADUCOU EM 11/09/2026</b>, e não pela largura: a medida acima
    continua valendo — o rótulo longo cabia. O que a derrubou foi a língua. O
    botão dizia <i>"Configurar o estilo Point-and-click"</i> e a tela que ele
    abre dizia <i>"Estilo Point-and-click"</i>: dois nomes para a mesma tela.
    Ela aprovou o do destino para os dois.</li>
  </ul>

  <h2>A rodada dos quatro controles</h2>
  <ul>
    <li><b>A coluna do desenho passou a mostrar todos.</b> Onde havia <b>um</b> DualSense
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
    <b>forma</b> do cartão; o <b>aparelho</b> é sempre o que está ligado.</li>
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

  <h2>O que os quatro controles revelaram, e está na tela</h2>
  <ul>
    <li><b>Mouse, teclado e os seis gestos saem de UM controle só.</b> Com um
    controle ligado ninguém podia ver isso. O poll loop lê o estado do controle
    <b>primário</b> (<code>daemon/lifecycle.py:3942</code>) e é esse estado que vai
    para o mouse (<code>:6189</code>), para o teclado (<code>:6200</code>) e para o
    <code>hotkey_manager.observe</code> (<code>:6208</code>); os secundários do
    co-op têm um caminho só, o do gamepad virtual
    (<code>daemon/subsystems/coop.py:1552</code>). Por isso o cartão do
    <b>Player {NAVEGA}</b> diz <i>{PAPEL_QUE_NAVEGA}</i> e os outros dizem <i>{PAPEL_SO_A_JANELA}</i>,
    e por isso o desenho que acende no combo é o dele. A exceção é o giro: na
    Navegação, quem acende a Mira Virtual move o cursor com ele, e o cartão
    diz <i>{PAPEL_DO_CURSOR}</i>. A
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
    <li><b>"Quem navega" na coluna do desenho.</b> Pus os quatro no lugar do desenho
    único porque é lá que ela responde a pergunta da aba sem custar altura. Se você
    quiser os quatro <b>maiores</b>, eles cabem numa fileira própria — mas aí a aba
    passa da dobra, e as tabelas de baixo já estão em telas à parte por isso.</li>
    <li><b>O cartão diz "{PAPEL_SO_A_JANELA}"</b> para os outros três: os analógicos
    deles andam só na janela do Hefesto, com a Navegação Interna ligada. O giro
    de quem acende a Mira Virtual soma no mesmo cursor, e aí o cartão diz
    "{PAPEL_DO_CURSOR}". Se você preferir que os quatro disputem o cursor pelos
    analógicos também, isso é código novo no daemon, não desenho.</li>
  </ul>
</div>

</body>
</html>
'''


def _conferir(doc):
    """As decisões de produto nesta aba, conferidas NA SAÍDA."""
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
    exigir(corpo.count('class="nav-ctl vazia"') == len(vazios),
           f"os lugares vazios não são {len(vazios)}")
    exigir(corpo.count('class="nav-ctl') == len(MESA),
           f"a fileira não tem os {len(MESA)} lugares")
    #    `<span data-campo="identidade">`, que é o que faz o produto ter onde
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> '
               f'<span data-campo="identidade">{SEM_NINGUEM_AQUI}</span>' in corpo,
               f"o lugar do P{c['jogador']} não diz {SEM_NINGUEM_AQUI} no rótulo "
               f"endereçado — ou a palavra mudou, ou o endereço caiu e o produto "
               f"volta a não ter onde escrever quando o controle chegar")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a um lugar vazio")
    _fileira = corpo.split('<div class="nav-mesa">', 1)
    if len(_fileira) != 2 or '<div class="combos">' not in _fileira[1]:
        raise SystemExit(
            "ERRO em 06-navegacao: a régua não achou a fileira `.nav-mesa` "
            "entre o começo dela e o `.combos` — refaça o recorte antes de "
            "confiar na conferência dos endereços por lugar")
    _fileira = _fileira[1].split('<div class="combos">', 1)[0]
    for pedaco in _fileira.split('class="nav-ctl vazia"')[1:]:
        bloco = pedaco.split('class="nav-ctl', 1)[0]
        exigir(all(papel not in bloco for papel in
                   (PAPEL_SO_A_JANELA, PAPEL_QUE_NAVEGA, PAPEL_DO_CURSOR)),
               "um lugar vazio diz o que ele navega — e ele não navega nada")

    #    O DEFEITO QUE ELA MEDE, com os QUATRO DualSense do usuário na mesa: o daemon
    _lugares = _fileira.split('<div class="nav-ctl')[1:]
    exigir(len(_lugares) == len(MESA),
           f"a régua dos endereços achou {len(_lugares)} lugares na fileira, e "
           f"a mesa tem {len(MESA)}")
    _campos = {}
    for c, _bloco in zip(MESA, _lugares):
        _campos[c["pref"]] = set(_re.findall(r'data-campo="([^"]+)"', _bloco))
    if len(_campos) == len(MESA):
        _base = _campos[MESA[0]["pref"]]
        exigir(bool(_base), "o primeiro lugar da fileira não tem um "
                            "`data-campo` sequer — não há contra o que comparar")
        for c in MESA[1:]:
            _pref = c["pref"]
            exigir(_campos[_pref] == _base,
                   f"o lugar {_pref} não tem os mesmos endereços do "
                   f"{MESA[0]['pref']} — faltam {sorted(_base - _campos[_pref])}, "
                   f"sobram {sorted(_campos[_pref] - _base)}. O piloto escreve "
                   f"por `data-campo` DENTRO do bloco do controle: sem o "
                   f"endereço, o dado dela chega e não tem onde pousar, e o "
                   f"lugar fica dizendo 'Desconectado' com o aparelho ligado")

    #    `.nav-ctl` diz `border:1px solid var(--plastico)`, e o lugar vazio NÃO
    #    tem `--plastico`. Uma `var()` sem valor **invalida a declaração toda**:
    #    crescer, o que não pode é a borda voltar a depender de `--plastico`.
    borda_do_vazio = re.search(
        r"border\s*:\s*1px\s+solid\s+var\(--border-forte\)", doc)
    exigir(bool(borda_do_vazio),
           "a borda do lugar vazio voltou a ser só COR — com `var(--plastico)` "
           "indefinido, a declaração inteira cai e o lugar fica sem caixa")
    for palavra in ("vazia", "off"):
        exigir(f".nav-ctl.{palavra}" in doc,
               f"a folha parou de desenhar o lugar `{palavra}` — o P2 "
               f"(esvaziado em execução, classe `off`) e o P3/P4 (`vazia` no "
               f"esqueleto) têm de ficar IGUAIS, e é a queixa dela de 17/09")
    exigir(QUEM_NAVEGA.get("conectado", True),
           f"quem navega (P{NAVEGA}) não está conectado")
    exigir(f'>P{NAVEGA} <span class="pt">•</span> '
           f'<span data-campo="identidade">{QUEM_NAVEGA["nome"]}</span></div>' in corpo,
           "o card de quem navega não é o do controle certo")

    conectados = [c for c in MESA if c.get("conectado", True)]
    exigir(corpo.count('data-campo="identidade"') == len(MESA),
           f"os {len(MESA)} lugares da mesa não têm um "
           f'`data-campo="identidade"` cada — o nome do plástico volta a ser o '
           f"do mockup no lugar cheio, e no vazio o controle que chegar não tem "
           f"onde se nomear")
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
    exigir(doc.count('data-campo="quem-navega"') == 1,
           "a dica da tela de Definições perdeu o "
           '`data-campo="quem-navega"` — ela volta a nomear o controle do '
           "desenho no meio do texto (ou a frase voltou à dica da troca de "
           "botões, onde ela é falsa)")
    exigir('data-campo="fita-chips" data-hef-alvo="html"' in doc,
           "a fita perdeu o endereço — e `hefesto_vivo._fita` DESISTE quando um "
           "controle da mesa não tem cor lida, que é o caso do rádio hoje")
    for c in conectados:
        exigir(f'title="Player {c["jogador"]}' not in doc,
               f"o `title` do cartão do P{c['jogador']} voltou — ele nomeia o "
               f"controle e não tem alvo de pintura")

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
    _ids = set(_re.findall(r'\sid="([^"]+)"', doc))
    _mortas = [i for i in tinta_referenciada() if i not in _ids]
    exigir(not _mortas,
           f"a folha das cores pede {_mortas} e a página não publica esse "
           f"`id` — os doze modelos que pintam por `url(#…)` ficam com "
           f"referência morta, e o desenho deles SOME (não fica cinza). Falta o "
           f"`BLOCO_DA_TINTA` no miolo")

    #    `core.acoes_de_botao.BOTOES`), nunca o gerador — e o gerador é quem
    _do_produto = set(_BOTOES_DO_PRODUTO)
    _do_desenho = {i for _b, i in BOTOES}
    exigir(_do_desenho == _do_produto,
           f"a tela e o produto não listam os mesmos botões — a mais no "
           f"desenho: {sorted(_do_desenho - _do_produto)}; a menos: "
           f"{sorted(_do_produto - _do_desenho)}. Uma linha que só existe de um "
           f"lado é escolha que o Guardar descarta em silêncio, ou botão que o "
           f"produto atende e a tela não oferece")

    def _tela(ident: str) -> str:
        return corpo.split(f'id="{ident}"', 1)[-1].split('class="tela-nova"', 1)[0]

    _com_endereco = [i for _b, _f, i in PONTO_MAPA if i]
    for _ident, _quantas, _oque in (
            ("definicoes-mouse", len(BOTOES), "'o que cada botão faz'"),
            ("point-and-click", len(_com_endereco), "do Estilo Point-and-click")):
        exigir(_tela(_ident).count(f'data-gesto="{LINHA_DE_BOTAO}"') == _quantas,
               f"as {_quantas} linhas {_oque} perderam o "
               f"`data-gesto=\"{LINHA_DE_BOTAO}\"` — sem ele a pintura volta a "
               f"desfazer a escolha antes do clique em Guardar")
    for _ident, _nome_do_gesto in (("definicoes-mouse", "fechar-definicoes"),
                                   ("point-and-click", "fechar-ponto"),
                                   ("remapeamento", FECHAR_TROCA)):
        exigir(_tela(_ident).count(f'data-gesto="{_nome_do_gesto}"') == 2,
               f"o `×` e o `Cancelar` da tela {_ident} perderam o "
               f"`data-gesto=\"{_nome_do_gesto}\"` — a trava das linhas ficaria "
               "presa depois de ela desistir")
    _troca = _tela("remapeamento")
    _fora_da_troca = sorted(set(_BOTOES_DO_PRODUTO) - set(_REMAPEAVEIS))
    _com_gesto = _troca.count(f'data-gesto="{LINHA_DE_TROCA}"')
    exigir(_com_gesto == len(_REMAPEAVEIS),
           f"a troca de botões tem {_com_gesto} listas com "
           f"`data-gesto=\"{LINHA_DE_TROCA}\"`, e a troca alcança {len(_REMAPEAVEIS)}")
    exigir(sorted(_re.findall(r'data-gesto="' + LINHA_DE_TROCA + r'" data-linha="([^"]+)"',
                              _troca)) == sorted(_REMAPEAVEIS),
           "o `data-linha` das listas com gesto da troca não é o que o motor "
           "alcança — o Guardar descartaria a linha sem endereço em silêncio")
    _apagadas = _re.findall(
        r'<select class="campo-linha" data-linha="([^"]+)" disabled>(.*?)</select>',
        _troca)
    exigir(sorted(_linha for _linha, _ops in _apagadas) == _fora_da_troca,
           f"as listas apagadas da troca são {sorted(a for a, _o in _apagadas)}, e "
           f"as que o motor recusa são {_fora_da_troca} — uma lista clicável "
           "numa linha que a troca não alcança segura todo Guardar sem dizer qual")
    exigir(all(_re.findall(r"<option[^>]*>(.*?)</option>", _ops) == [SEM_TROCA]
               for _linha, _ops in _apagadas),
           f"uma lista apagada da troca oferece mais que {SEM_TROCA!r} — o estado "
           "real dessas linhas é sempre sem troca")
    exigir(_troca.count("<select") == len(_REMAPEAVEIS) + len(_fora_da_troca),
           "a troca de botões tem lista que não é nem das dezesseis nem das seis")
    _pintadas = _troca.count('data-campo="' + PREFIXO_DA_TROCA)
    exigir(_pintadas == len(_REMAPEAVEIS),
           f"a troca de botões pinta {_pintadas} linhas, e a troca alcança "
           f"{len(_REMAPEAVEIS)}")
    exigir("marca-nao-dispara" not in _troca,
           "a tela da troca voltou a marcar o touchpad com «não dispara», e a "
           "dica promete uma escolha guardada ao lado de uma lista apagada")
    exigir(_tela("definicoes-mouse").count('class="marca-nao-dispara"')
           == len(TOUCH_REGIOES),
           "as Definições perderam a marca «não dispara» de uma região do touchpad")
    exigir('data-gesto="guardar-ponto"\n         data-hef-forma="point-and-click"'
           in corpo,
           "o Guardar do Estilo Point-and-click perdeu o "
           "`data-hef-forma=\"point-and-click\"` — sem a forma ele não sabe o "
           "que está escolhido em cada linha e volta a só poder recusar")

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
    _tela_teclas = corpo.split('id="teclas-do-teclado"', 1)[-1].split(
        'class="tela-nova"', 1)[0]
    exigir("data-linha=" not in _tela_teclas,
           "voltou um `data-linha` à tela de teclas — a `forma` do piloto usa "
           "`data-linha || data-campo` como chave, e ele faria o campo de texto "
           "ocupar a chave da lista de 'o que cada botão faz'")
    exigir(_tela_teclas.count('data-campo="tecla-') == len(_dominio),
           "a tela de teclas tem `data-campo` fora dos campos de texto — o ↺ e "
           "os botões do rodapé não podem ter, senão entram na `forma`")
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
    exigir(f'<option selected>{TECLADO_PADRAO}</option>' in corpo,
           f"a 'Função do teclado' não nasce em {TECLADO_PADRAO!r}")
    for opcao in OPCOES_TECLADO:
        exigir(f">{opcao}</option>" in corpo,
               f"a opção {opcao!r} da 'Função do teclado' sumiu do desenho")

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

    for campo in ("rato-estado", "teclado-bloqueio", "teclado-osk"):
        exigir(f'data-campo="{campo}" data-hef-alvo="html"' in corpo,
               f"a linha de estado `{campo}` sumiu do desenho — a frase do "
               f"produto volta a ser emitida para o vazio")

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
    painel = corpo.split('As opções de ativação', 1)[-1].split('class="tela-nova"', 1)[0]
    exigir(len(painel) > 2000, "a régua não achou o painel das opções de ativação")
    exigir('class="passo"' not in painel,
           "voltou um `−`/`+` ao painel das opções de ativação — ela mandou "
           "barra, e um par de botões ao lado dela é a meia-cura")
    exigir('class="ressalva"' not in painel,
           "voltou uma linha de ressalva solta ao painel das opções de "
           "ativação — ela quebra o layout, e a frase da D3 mora no `?` dos "
           "três campos de que fala desde 07/09")
    for campo in ("modo-portao", "teclado-osk", ENDERECO_DA_RESSALVA):
        exigir(f'<div class="estado" data-campo="{campo}"' not in corpo,
               f"`{campo}` voltou para a tira de `.estados`. Medido em "
               f"07/09: com as três lá, o quadro das opções ia de 215px a "
               f"300,25px e a fileira dos quatro botões terminava 41,25px "
               f"FORA da janela")
    for campo, quantas in (("modo-portao", 1), ("teclado-osk", 1),
                           (ENDERECO_DA_RESSALVA, 3)):
        alvo = (f'<span class="viva" data-campo="{campo}"'
                f' data-hef-alvo="html"><i class="nada"></i></span>')
        exigir(painel.count(alvo) == quantas,
               f"`{campo}` devia aparecer em {quantas} `?` do painel, viva e "
               f"vazia, e aparece em {painel.count(alvo)} — a frase que saiu do "
               f"pé só não se perde se chegar ao campo de que fala")
        exigir(doc.count(alvo) == quantas,
               f"`{campo}` aparece {doc.count(alvo)} vezes na página e devia "
               f"aparecer {quantas} — a dica de uma velocidade é COMPARTILHADA "
               f"com a pop-up do Point-and-click, e a frase não vale lá")
    exigir('.quadro-corpo:has([data-campo="modo-portao"] .laranja)' in doc,
           "a regra que apaga o interruptor do modo deixou de partir do "
           "endereço `modo-portao` — sem ela a razão chega e o interruptor "
           "continua com cara de clicável")
    reais = re.findall(r'<span class="ajuda[^"]*"([^>]*)>\?<span class="dica', doc)
    sem_foco = [a for a in reais if 'tabindex="0"' not in a]
    exigir(not sem_foco,
           f"há `?` sem `tabindex` nesta aba ({len(sem_foco)} de "
           f"{len(reais)}) — sem ele o `el.click()` do controle não abre a "
           f"dica, e esta é a aba da navegação com o controle")
    _acende = '.ajuda.tem-viva:has(.viva > :not(.nada))'
    exigir(f'{_acende}{{' in doc,
           "sumiu a regra que dá COR ao `?` com frase viva dentro — sem ela a "
           "frase que ela mandou tirar do pé fica num hover que não se anuncia, "
           "e a decisão dela de 05/09 diz que ninguém passa o rato onde não "
           "sabe que há algo")
    exigir(f'{_acende}::after{{' in doc,
           "sumiu o PONTO que anuncia o `?` com frase viva — a cor sozinha "
           "muda um `?` cinza para ciano, que é a mesma coisa que o hover já "
           "faz; o ponto é o que se vê sem chegar perto")
    orfas = [a for a, corpo in
             re.findall(r'<span class="ajuda([^"]*)"[^>]*>\?<span class="dica'
                        r'(.*?)</span></span>', doc, re.S)
             if '<span class="viva"' in corpo and 'tem-viva' not in a]
    exigir(not orfas,
           f"há frase viva pendurada em `?` sem a marca `tem-viva`: {orfas} — "
           f"o ponto que a anuncia sai da marca, e sem ele a frase volta a "
           f"morar num hover que ninguém sabe que existe")
    _css_nu = re.sub(r'/\*.*?\*/', '', doc, flags=re.S)
    _aninhados = []
    for m in re.finditer(r':has\(', _css_nu):
        prof, i = 1, m.end()
        while prof and i < len(_css_nu):
            if _css_nu[i] == "(":
                prof += 1
            elif _css_nu[i] == ")":
                prof -= 1
            i += 1
        if ":has(" in _css_nu[m.end():i]:
            _aninhados.append(_css_nu[m.start():i][:120])
    exigir(not _aninhados,
           f"há `:has()` dentro de `:has()` — o navegador descarta a regra "
           f"inteira, calado, e a régua que a procurar por texto vai continuar "
           f"verde sobre nada: {_aninhados}")
    from hefesto_dualsense4unix.app.actions.input_actions import (
        frase_do_teclado_na_tela,
    )
    from hefesto_dualsense4unix.interface.pacotes.a06_navegacao import (
        RESSALVA_DOS_GLOBAIS,
        _a_razao_do_portao,
    )
    for nome, frase in (
            # razão tem o que dizer. A forma sai de `mode_of_state`, que lê
            ("modo-portao",
             _a_razao_do_portao({"gamepad_emulation": {"enabled": True}})),
            ("teclado-osk", frase_do_teclado_na_tela(True)),
            ("teclado-osk (sem teclado)", frase_do_teclado_na_tela(False)),
            (ENDERECO_DA_RESSALVA, RESSALVA_DOS_GLOBAIS)):
        exigir("<" in frase and NADA_A_DIZER not in frase,
               f"a frase viva de `{nome}` voltou sem marcação nenhuma "
               f"({frase[:60]!r}) — o `?` abriria a dica com ela dentro e o "
               f"ponto ficaria APAGADO, que é a tela tendo o que dizer e não "
               f"avisando")

    if falhas:
        raise SystemExit("ERRO em 06-navegacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


def _gerar() -> None:
    n = monta("06-navegacao", "Navegação", MIOLO, CSS)

    p = onde.pagina("06-navegacao.html")
    s = p.read_text()
    antes = 'title="Esta aba não usa o controle escolhido aqui — os cards são leitura."'
    depois = f'title="{TITULOS_DA_FITA["06-navegacao.html"]}"'
    if f"Player {NAVEGA}" not in depois:
        raise SystemExit(
            f"ERRO: a fita da 06 nomeia o Player 1 e o mockup elegeu o {NAVEGA} — "
            "reveja `monta.TITULOS_DA_FITA` antes de gerar")
    if antes not in s:
        raise SystemExit("ERRO: o title da fita mudou no topo.html — refaça a troca")
    s = s.replace(antes, depois)

    fita_re = re.compile(r'(<div class="fita inerte"[^>]*)(>)(.*?)(</div>)', re.S)
    if not fita_re.search(s):
        raise SystemExit("ERRO: a fita inerte mudou de forma — refaça o endereço")
    s = fita_re.sub(
        lambda m: (m.group(1) + ' data-campo="fita-chips" data-hef-alvo="html"'
                   + m.group(2) + chips_da_fita(MESA_DA_FITA) + m.group(4)),
        s, count=1)

    marca = "<!-- ===== fim da aba ===== -->"
    if marca not in s:
        raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
    telas = "\n".join(t.strip() for t in (TELA_DEFINICOES, TELA_TECLAS,
                                          TELA_REMAPEAMENTO, TELA_PONTO))
    s = s.replace(marca, telas + "\n\n" + marca, 1)
    onde.gravar("06-navegacao.html", s)

    _conferir(onde.pagina("06-navegacao.html").read_text())
    print(f"06-navegacao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · "
          f"quem navega: P{NAVEGA} · {len(BOTOES)} botões do mapa")


if __name__ == "__main__":
    import os
    import pathlib
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-06-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    _gerar()
    shutil.copyfile(_prova / "06-navegacao.html", _real / "06-navegacao.html")
    shutil.rmtree(_prova)
