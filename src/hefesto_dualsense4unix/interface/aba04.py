import sys, pathlib, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
import monta as monta_
from itertools import cycle
from monta import (monta, svg, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, player_slot_color, tom_da_casa)
from pacotes import a04_iluminacao as _pacote04
import marca_da_camada as _marca

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


DONO = {c["jogador"]: c for c in MESA}

NUMEROS = sorted(c["jogador"] for c in MESA)

_b = cycle((82, 100, 70, 45))
BRILHO = {c["pref"]: next(_b) for c in MESA}

#: O QUE ELAS ERAM: as primárias cruas que `player_slot_color` devolve —
#: #0000FF, #FF0000, #00FF00, #FF0080, #FFFF00… Cor de monitor de teste, com
#: `core/led_control.player_slot_color` continua devolvendo as primárias, e
CRUS_DA_GUIA = ["#%02X%02X%02X" % rgb for rgb in _pacote04.tons_da_guia()]
TONS = [tom_da_casa(h) for h in CRUS_DA_GUIA]


def TITULO_DA_CASA(i: int) -> str:  # noqa: N802 - constante de molde, não classe
    """A frase de cada casa da guia. As oito primeiras são cor de número."""
    quem = f"Cor do Player {i}. " if i <= 8 else ""
    return f"{quem}Pinta a barra, não muda o número."


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

     AS ALTURAS SÃO TOKENS porque a soma é o orçamento: 146+16+44+26+52+64+64
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
    /* AS TRÊS PÍLULAS DO BRILHO DAS LUZES MORAM NA LINHA DOS LEDs — 24/09/2026,
       decisão dela (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): *"Fraco,
       Médio e Forte na linha LEDs, nascendo no Fraco"*. Elas pedem 30px
       (24 de pílula e 6 de vão) debaixo da tira de 34: `--r-leds` vai de 56
       para 64 e `--r-acoes` de 72 para 64. OS OITO SAEM DA LINHA OPÇÕES porque
       ela sobrava: tem UM botão desde 07/09/2026, e ele mede 34px dentro dos
       72 — a coluna continua em 472 e o teto de 476 não é tocado. */
    --r-player:52px;--r-leds:64px;--r-acoes:64px;
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
  /* A linha da luz do jogo: uma frase curta embaixo das cores, sem botão. Texto de apoio
     (nunca vermelho), com o «Agora» em tinta cheia só quando o jogo está pintando. */
  .luz-do-jogo{margin:6px 0 0;font-size:12px;line-height:1.3;color:var(--texto-mudo)}
  .luz-do-jogo b{font-weight:600;color:var(--fg)}

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
     `hefesto_vivo._recusou_dizendo` só levava `RuntimeError` à tela: dez botões
     que engoliam o toque sem uma letra. Escondê-los é o que fecha isso — o que
     não existe não pode aceitar clique, e não precisa de frase nova. (Desde
     13/09/2026 nenhuma recusa chega à tela como frase: as duas exceções vão ao
     diário e o botão pisca — a docstring de `_recusou_dizendo` diz por quê.)

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
  /* O ESCOPO GLOBAL DESTA FAIXA SAIU — 07/09/2026, e a faixa voltou a ter um
     morador só: o interruptor. A ordem dela é de hoje, sobre os três cantos
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
  .guia{display:flex;gap:4px;align-items:center}
  /* os onze botões continuam itens do flex da `.guia` — ver o gerador */
  .guia .tons{display:contents}
  /* A MOLDURA DA AMOSTRA SAIU — 31/08/2026, e é a mais pura das "bordas
     sobrando": um retângulo de 1px em volta de um retângulo CHEIO da cor que
     ele mostra. São oito por controle, trinta e dois na tela, e nenhum deles
     separava coisa nenhuma — o `gap:4px` já separa, e o conteúdo é a própria
     cor. A borda continua em `transparent`: a casa não muda de tamanho quando
     muda de estado. */
  .guia .tom{flex:1;height:26px;border-radius:6px;border:1px solid transparent;
             cursor:pointer;padding:0;display:block;min-width:0;position:relative}
  /* A LINHA DO DONO — 29/09/2026, D-2909-A-LINHA-DA-COR-DO-DONO, pedido dela
     na bancada: *«talvez uma linha abaixo do quadradinho de cada cor contendo
     a cor do plástico daquele controle.»* <!-- noqa-acento: citação literal dela -->
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

     O LUGAR É O VÃO ENTRE A CASA E A CAIXA `#RRGGBB`: 2 px abaixo da casa e 2
     px de altura, sem crescer a linha Cor. O vão de cima é o que separa a
     linha da casa: colada, a do Starlight Blue embaixo da casa azul se leria
     como a casa mais alta. O `-1px` dos lados alcança a borda da casa, porque
     o `left` conta da caixa por dentro dela. */
  .guia .tom.com-dono::before{
    content:"";position:absolute;left:-1px;right:-1px;
    top:calc(100% + 3px);height:2px;border-radius:1px;background:var(--dono);
  }
  /* O X DA COR DO VIZINHO — COR-X-01, 09/09/2026, decisão dela: "um X na cor
     selecionada por mim de forma que me impeça de setar alguma cor de um
     coleguinha". <!-- noqa-acento: citação literal dela -->

     ELE É DESENHADO, e não um caractere: um `×` de texto herda a fonte, muda
     de tamanho com ela e o traço fino some sobre um tom claro. Dois gradientes
     cruzados desenham as duas hastes, e uma sombra os contorna.

     A COR DO X É PRETA COM BORDA BRANCA — decisão dela, 09/09/2026, com os
     quatro na mesa: *"deixa o nosso x preto com borda branca pra destacar.
     Falo isso pois ficou perfeito o nosso x, o complicado é que são tons
     pasteis e o controle branco por exemplo não ajuda nisso o x dele fica
     invisível."* <!-- noqa-acento: citação literal dela -->

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
         vista 1918x840 (a TV dela)           .tom 26,1 x 26  X 14,0 x 14

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
  /* A CASA HACHURADA DO FIM DA FILEIRA SAIU — 11/09/2026, ordem dela. A razão,
     as palavras dela e os três tons que saíram junto estão na nota datada de
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
     guia SEMPRE dispara — clicar de novo no mesmo tom reenvia. O campo de cor
     do fim da fileira não: ele só avisava quando o valor MUDAVA, então a cor
     que ela escolhia à mão era justamente a única sem porta de volta. Aquele
     campo saiu em 11/09/2026 e esta caixa FICA — o que ela reenvia agora é a
     cor que a fileira não tem (o global do perfil, ou um tom podado que um
     perfil antigo ainda guarda), e a confirmação de que a cor chegou depois de
     um controle cair e voltar.

     NENHUM ELEMENTO NOVO E NENHUMA LINHA, que é a razão da escolha — a fileira
     de Opções já estava apertada. O que muda é o SINAL de que se pode clicar:
     o cursor, e a borda no rato. Sem eles, uma caixa que se lê como texto
     aceitaria clique sem nunca dizer que aceita.

     A BORDA JÁ NASCE (transparente) para o hover não mexer no tamanho — a
     mesma lição que a `.guia .tom` pagou nesta folha, algumas regras acima. */
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
  .players button,.brilhos button{
    flex:1;border-radius:7px;gap:6px;min-width:0;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--texto-mudo);
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
            justify-content:center;min-width:0;gap:6px}
  /* AS TRÊS PÍLULAS DO BRILHO DAS LUZES — 24/09/2026, decisão dela
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
       incerta   Steam · cor ignorada             ESTA REGRA — tracejada

     O NATIVO SAIU DA LINHA DE BAIXO em 24/09/2026
     (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`): no Nativo a barra é do
     Hefesto, e a tira desenha a cor como em todo modo.

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

     É a armadilha que o `GUIA.md` desta casa nomeia três vezes em três dias:
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


DONOS_NA_MESA = {n: d for n, d in DONO.items() if d.get("conectado", True)}


#: O dono único é `pacotes/a04_iluminacao.um_botao_de_player`, e este gerador é


VAZIO = "—"

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
    3. **os widgets que carregam GESTO** — a guia de tons, o puxador do brilho
       e os dois botões de Opções (eram quatro até 11/09/2026: o campo de cor
       do fim da fileira saiu com a poda de `FORA_DA_GUIA`). Estes são a
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
        '\n             title="Nenhum controle neste lugar."')
    plastico_de_partida = (f' style="color:{cor_da_zona(c["cor"])}"'
                           if ligado else "")
    dica_da_moldura = (
        ' title="A borda é a cor do plástico deste controle, quando o produto a'
        ' conhece. A barra acende a cor do número, e as cinco lâmpadas dizem'
        ' qual é."' if ligado else "")
    rotulo = (f'P{j} <span class="pt">•</span> {c["nome"]}'
              f' <span class="pt">•</span> {c["via"]}' if ligado else
              f'P{j} <span class="pt">•</span> {SEM_NINGUEM_AQUI}')
    # `opcoes` eram `... if ligado else ""`, e o preço foi MEDIDO nas  (noqa-acento: nome de variável)
    # DualSense dela na mesa e o daemon de pé, a foto ao vivo mostrava o P3 e o
    # bloco `[data-conectado="nao"]` desta folha esconde a guia, o trilho e os
    # instante do passo `1c` e some no `1b`, sem ninguém injetar HTML.
    # DONO. Ela carregava o `data-campo="plastico"` (alvo `cor`) só para dar
    guia = f'''<span class="guia">
              <span class="tons" data-campo="tons" data-hef-alvo="html">
{tons}
              </span>
            </span>
            '''
    reenvio = ' data-gesto="reenviar"'
    dica_do_hex = '\n                  title="Manda esta cor ao controle de novo."'
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
    # (`lightbar.reset`) e pintava a cor do número por cima; este escreve preto
    opcoes = '''<button class="btn vermelho" data-gesto="apagar" title="Apaga a barra de luz deste controle.">Desligar</button>
            '''

    # `nao` da régua de acentuação é um `#`, e dentro de uma f-string de  (noqa-acento: o próprio valor que a nota explica)
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
            <div class="brilhos" data-campo="{_pacote04.ENDERECO_DO_BRILHO_DAS_LUZES}" data-hef-alvo="html">
{brilhos}
            </div>
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
          {_marca.bloco("luz")}
        </div>'''

# dela: *"ainda temos 3 cantos falando sobre o automatico"*.  # noqa-acento: citação literal dela
# `noqa-acento` num comentário HTML aninhado — e **comentário HTML NÃO
# A REGRA QUE SOBRA: `# noqa-…` só comenta em Python. Prosa de projeto que
# precise de um `noqa` sai do HTML e vem para cá.

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
          A <b>barra de luz</b> é a faixa acesa dos dois lados do touchpad: é como
          você sabe de quem é cada controle.<br><br>
          O plástico pode se repetir; a <b>luz</b> nunca.
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
             ato, para nenhuma se perder e nenhuma se repetir.

             E A REGRA DA COR AUTOMÁTICA É A DO PLÁSTICO desde 29/09/2026
             (D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO): a cor da casca, e a do
             número quando o plástico não tem tom ou se repete. -->
        <label class="chave-auto">
          <input type="checkbox" data-gesto="auto-cores" data-campo="auto-cores"
                 data-hef-alvo="marcado" checked>
          <span class="chave-trilho"></span>
          <span>Cores automáticas por controle</span>
        </label>
        <span class="ajuda esq">?<span class="dica">
          Ligado, cada controle recebe um número e acende a cor do seu
          <b>plástico</b>; sem cor de plástico, ou com dois iguais, a cor do
          <b>número</b> — inclusive os de outras marcas.<br><br>
          Ao <b>desligar</b>, a cor de agora fica <b>gravada no perfil</b>, para nenhuma
          se perder.<br><br>
          É do <b>perfil</b>: viaja quando você troca de perfil.
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
                  A barra acende na cor do <b>número</b>; a borda da moldura é a cor do
                  <b>plástico</b>, e as cinco luzinhas acima do touchpad dizem o número.<br><br>
                  Cada coluna é um controle: a fita do topo não escolhe nada aqui.
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
                  <!-- A DICA PAROU DE CONTAR CASAS — 11/09/2026. Ela dizia "os oito
                       quadradinhos" e "o nono é o livre", e as duas frases já estavam
                       velhas: a fileira tinha CATORZE desde 09/09, e hoje tem onze. Um
                       número digitado aqui envelhece calado a cada poda — "os oito
                       primeiros" é estrutura (`player_slot_color(1..8)`), "os demais"
                       nunca mente. -->
                  Sem escolha à mão, a barra fica na <b>cor do número</b> do controle.<br><br>
                  Os <b>oito primeiros</b> quadradinhos são as cores dos jogadores 1 a 8;
                  os demais são tons a mais.<br><br>
                  Escolher um tom pinta a barra e <b>não muda o número</b>. O código
                  embaixo é a cor que vai ao aparelho.
                </span></span>
              </div>
            </div>
            <div><div class="sec-rot">Brilho</div></div>
            <div>
              <div class="sec-rot">Jogador
                <span class="ajuda">?<span class="dica">
                  <b>Dá</b> o número do jogador a este controle — o das cinco luzinhas
                  acima do touchpad. O <b>anelzinho</b> de cada botão é a cor do plástico
                  de quem tem aquele número hoje.<br><br>
                  <!-- A FRASE PAROU DE NOMEAR CONTROLE — 03/09/2026, a lei dela.
                       Ela dizia *"pôr o Starlight Blue no 1 faz o Cosmic Red virar
                       2"*: os dois nomes do MOCKUP, numa coluna de RÓTULOS que é
                       uma só para as quatro colunas — não há "este controle" aqui
                       a que endereçar, e por isso a cura não é endereço, é dizer a
                       regra em vez do exemplo. Quem nomeia os dois de verdade é a
                       dica de cada botão da fileira (`um_botao_de_player`), que o
                       pacote reescreve a cada tique com a mesa viva. -->
                  Dar um número que já é de outro faz <b>os dois trocarem</b>: ninguém
                  repete e ninguém fica sem.<br><br>
                  <!-- O JOGO NÃO MANDA NO NÚMERO — 24/09/2026, A-MIRA-NA-NAVEGACAO-01.
                       Aqui estava *"Um jogo em co-op pode mandar o próprio
                       número por cima"*, e a STEAM-NO-FISICO-01 derrubou o fato:
                       o número que o jogo manda ao controle virtual é RECUSADO
                       sempre (`backend_pydualsense.numeracao_do_jogo`), e o que
                       chega por fora é reescrito pela vigia do sequestro
                       (`escritor_cru.VigiaDoSequestro`) em até um segundo. -->
                  O número é do Hefesto: se um jogo o trocar, ele <b>volta em até
                  um segundo</b>.
                </span></span>
              </div>
            </div>
            <div><div class="sec-rot">LEDs</div></div>
            <div><div class="sec-rot">Opções</div></div>
          </div>

{chr(10).join(coluna(c) for c in MESA)}

        </div>

        <!-- A LUZ DO JOGO — 04/10/2026, desenho aprovado em `docs/process/estudos/2026-10-04-o-jogo-
             decide/` (item 3): nenhum botão novo, só uma linha curta embaixo das cores. A regra é a
             da 1.5 (o jogo pinta por cima; sem jogo, a sua cor) e a luz nunca sai preta; com o jogo
             pintando agora, a linha ganha «Agora: a cor do jogo». O sinal vem do `state_full`
             (`luz_do_jogo`), e a frase, do pacote. -->
        <div class="luz-do-jogo" data-campo="luz-do-jogo" data-hef-alvo="html">{_pacote04.FRASE_DA_LUZ_DO_JOGO}</div>

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
    "btn": '.luz-grade .ctrl[data-conectado="nao"] .cel-acoes .btn',
    "hex": '.luz-grade .ctrl[data-conectado="nao"] .cel-cor .hex.reenvia{pointer-events:none',
}

_SEM_CLASSE = re.compile(r"()").match("")


def _cada_coluna(colunas):
    """As colunas da grade, separadas em (vazias, conectadas)."""
    vazias, cheias = [], []
    for atributos, miolo in _UMA_COLUNA.findall(colunas):
        (vazias if "vazia" in atributos else cheias).append(atributos + ">" + miolo)
    return vazias, cheias


def _conferir(doc):
    """As decisões dela nesta aba, conferidas NA SAÍDA."""
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
    exigir(corpo.count('class="ctrl vazia"') == len(vazios),
           f"as colunas vazias não são {len(vazios)}")
    exigir(corpo.count('class="ctrl"') == len(MESA) - len(vazios),
           "uma coluna conectada virou vazia, ou o contrário")

    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")

    #    as outras. Com os quatro DualSense dela na mesa, ela não conseguia
    grade = corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
    #    A linha da luz do jogo é da página, não de um lugar: a régua das colunas não a conta.
    grade = grade.split('<div class="luz-do-jogo"', 1)[0]
    #    `luzes`, `desenho-de` e `reenviar-desenho` —, e eles JÁ chegavam aos
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
    colunas = corpo.split('<div class="luz-grade">', 1)[-1]
    exigir(colunas.count("data-colorway=") == len(monta_.CONECTADOS),
           "há `data-colorway` fora das colunas conectadas — identidade do "
           "mockup parada num lugar sem aparelho")

    topo = corpo.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    exigir('class="chave-auto"' in topo,
           "o interruptor das cores automáticas saiu da faixa do título — a "
           "D-13 pede ele NO TOPO da aba, e qualquer outro lugar cobra uma "
           "linha da grade que já está a 4px do teto")
    #    `marcado`, e só acha o elemento pelo `data-campo`.
    for atributo in (f'data-gesto="{_pacote04.ENDERECO_DO_AUTOMATICO}"',
                     f'data-campo="{_pacote04.ENDERECO_DO_AUTOMATICO}"',
                     'data-hef-alvo="marcado"'):
        exigir(atributo in topo,
               f"o interruptor perdeu {atributo!r} — sem os três ele é uma "
               f"chave que não lê o perfil nem o muda")
    exigir(".quadro-topo .ajuda.esq .dica{left:auto;right:22px}" in doc,
           "a dica do interruptor voltou a abrir para a direita — ela tem "
           "330px e o `?` está encostado na borda do quadro")

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
    caixas = re.findall(r'<span class="hex reenvia"[^>]*>', colunas)
    exigir(len(caixas) == len(MESA),
           "a caixa do hexadecimal não virou botão em todas as colunas")
    for caixa in caixas:
        exigir('data-gesto="reenviar"' in caixa,
               "a caixa do hexadecimal perdeu o gesto de reenvio")
        exigir("data-hex=" not in caixa,
               "a caixa do hexadecimal ganhou `data-hex` — o gesto passaria a "
               "reenviar a cor CRAVADA no desenho, e não a que está na tela")

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
    exigir(corpo.count(">Desligar</button>") == len(MESA),
           f"a célula Opções não tem um `Desligar` por lugar "
           f"({corpo.count('>Desligar</button>')} para {len(MESA)}) — ela NÃO "
           f"citou este botão, e apagar a barra é o único ato que só ele "
           f"oferece nesta tela")

    #     `p3: 0 (0)`, `p4: 0 (0)`. Com os quatro DualSense dela na mesa, o
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

    # 15. A PODA DA FILEIRA — 11/09/2026, ordem dela: *"remover esse botão que  <!-- noqa-acento: citação literal dela -->
    #     o mouse tá (que abre outras cores.) remover um tom de azul. um tom de  <!-- noqa-acento: citação literal dela -->
    #     rosa e o tom de preto de todas as cores pros 4 controles."*           <!-- noqa-acento: citação literal dela -->
    os_tres_que_sairam = ("#0080FF", "#FF00FF", "#000000")
    exigir(tuple(_pacote04.FORA_DA_GUIA) == os_tres_que_sairam,
           f"a poda da guia mudou sem esta régua saber: o pacote tira "
           f"{tuple(_pacote04.FORA_DA_GUIA)} e a ordem dela de 11/09/2026 era "
           f"{os_tres_que_sairam} — um azul, um rosa e o preto")
    for h in os_tres_que_sairam:
        exigir(f'data-hex="{h}"' not in corpo,
               f"o tom {h} voltou à fileira — ela mandou os três saírem de "
               f"todos os quatro controles em 11/09/2026")
    exigir('<input type="color"' not in grade,
           "a casa hachurada do fim da fileira voltou — e o gesto dela morreu "
           "junto em 11/09/2026, então ela seria um clique sem resposta")
    exigir(grade.count('class="tom') == len(MESA) * len(CRUS_DA_GUIA),
           f"a fileira não tem {len(CRUS_DA_GUIA)} casas em cada um dos "
           f"{len(MESA)} lugares da grade")

    if falhas:
        raise SystemExit("ERRO em 04-iluminacao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


CSS += _marca.CSS + """
  .luz-grade .ctrl{position:relative}
  .luz-grade .ctrl > .camada{position:absolute;top:-8px;left:22px;z-index:1;
    padding:0 5px;background:var(--panel);max-width:calc(100% - 34px)}
  .luz-grade .ctrl > .camada::before{content:none}
"""


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
