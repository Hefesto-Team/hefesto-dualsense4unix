# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import CSS_GLIFO, MESA, R, cor_da_zona, glifo, monta  # noqa: E402

# OS PARÂMETROS DE CADA MODO SAEM DO PRODUTO, e não de uma tabela digitada aqui.
# `app/actions/trigger_specs.py` é quem sabe quantos ajustes cada um dos 19
# modos tem, como cada um se chama e em que faixa ele anda — a mesma metadata
# que a aba Gatilhos usa para montar os sliders. Digitar "Posição, 0 a 9" nesta
# página seria a segunda verdade que o mapa existe para matar: no dia em que o
# produto mudar a faixa, a porcentagem desenhada aqui muda junto ou REPROVA.
sys.path.insert(0, str(R / "src"))
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS  # noqa: E402

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
GL = 36

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
  .duas-colunas{display:grid;grid-template-columns:128px repeat(4,1fr);gap:0 12px}

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
  .duas-colunas > div > *::before{content:'';position:absolute;top:0;height:0;
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
  .duas-colunas .rotulos > *{align-items:flex-end;text-align:right}
  .duas-colunas .rotulos .sec-rot{justify-content:flex-end}
  .duas-colunas .rotulos > * > *{flex:1;display:flex;align-items:center}
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
  .duas-colunas .ctrl .chip{padding:0 8px;font-size:11px;height:22px;
    display:inline-flex;align-items:center;align-self:center;white-space:nowrap}

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
    "p3": {"esq": ("Resistência", "Rampa crescente", [("Início", 3), ("Força", 5)]),
           "dir": ("Vibração", PRONTOS[0], [("Posição", 3), ("Amplitude", 4), ("Frequência", 40)])},
    "p4": {"esq": ("Desligado", PRONTOS[0], []),
           "dir": ("Ponto duro", "Plateau central", [("Posição", 5), ("Intensidade", 4)])},
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


def opcoes_modo(escolhido):
    return "\n".join(
        f'                <option{" selected" if n == escolhido else ""} title="{d}">{n}</option>'
        for n, d in MODOS)


def opcoes_pronto(escolhido):
    fora = [f'                <option{" selected" if n == escolhido else ""}>{n}</option>'
            for n in PRONTOS]
    dentro = [f'                <option{" selected" if n == escolhido else ""}>{n}</option>'
              for n in MEUS]
    return ("\n".join(fora) + '\n                <option disabled>──── Meus efeitos ────</option>\n'
            + "\n".join(dentro))


def bloco(lado, sigla, modo, pronto, ajustes):
    """`sigla` é "e" ou "d": a linha de ajustes do L2 e a do R2 têm
    alturas diferentes, porque cada uma vale o maior modo que está NELA."""
    if ajustes:
        aj = "\n".join(
            f'''            <div class="barra">
              <span class="nome">{n}</span>
              <span class="trilho"><span class="cheio" style="width:{p}%"></span></span>
              <span class="num">{v}</span>
            </div>''' for n, p, v in ajustes)
    else:
        aj = '            <div class="ajustes-vazio">Este modo não tem o que ajustar.</div>'
    return f'''          <div>
            <select class="modo" title="Gatilho {lado} — os 19 modos, com a descrição de cada um">
{opcoes_modo(modo)}
            </select>
          </div>
          <div>
            <select class="pronto" title="Efeito pronto do gatilho {lado}">
{opcoes_pronto(pronto)}
            </select>
          </div>
          <div class="ajustes {sigla}">
{aj}
          </div>'''


def coluna(c):
    """Uma coluna = UM controle da `MESA`. A aba não sabe contar até quatro."""
    cena = CENA[c["pref"]]
    esq = bloco("esquerdo", "e", *cena["esq"][:2], barras(*cena["esq"][::2]))
    dire = bloco("direito", "d", *cena["dir"][:2], barras(*cena["dir"][::2]))
    rot = (f'P{c["jogador"]} <span class="pt">•</span> {c["nome"]}'
           f' <span class="pt">•</span> {c["via"]}')
    return f'''        <div class="ctrl">
          <div><span class="chip plastico" style="--plastico:{cor_da_zona(c['cor'])}"
                     title="{c["nome"]} — a borda é a cor do plástico">{rot}</span></div>
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
          <div><button class="btn roxo">Guardar esse efeito</button></div>
        </div>'''


# ---------------------------------------------------------------------------
# AS NOVE LINHAS DA GRADE, e a altura da coluna é a SOMA delas.
#
# A LINHA DE AJUSTES SAI DA CENA, e não de um número escolhido no olho: ela vale
# o MAIOR modo que está NELA — 4 barras no L2 (a Metralhadora do P1) e 3 no R2
# (a Vibração do P3). Com um número só para as duas, a linha do R2 herdava a
# altura do L2 e as três colunas de dois ajustes ficavam com uma barra de vão em
# cima do botão. É a regra dela: a cura do vão é na ALTURA.
#
# O TETO É MEDIDO: o miolo tem 508px úteis (542 de caixa menos os 16+18 de
# padding), e o quadro gasta 28 de cabeçalho, 24 de padding e 2 de borda — sobram
# 454px para a grade. O que passar disso rola por dentro, e quadro que rola é
# conteúdo que ninguém sabe que existe.
# ---------------------------------------------------------------------------
ALT_BARRA = 23   # uma barra: 11,5px de rótulo e 5 de trilho
R_NOME, R_MODO, R_PRONTO, R_SEP, R_ACAO, R_PASSO = 24, 36, 36, 1, 34, 10
N_ESQ = max(len(barras(*CENA[c["pref"]]["esq"][::2])) for c in MESA)
N_DIR = max(len(barras(*CENA[c["pref"]]["dir"][::2])) for c in MESA)
R_AJ_E, R_AJ_D = N_ESQ * ALT_BARRA, N_DIR * ALT_BARRA
LINHAS = [R_NOME, R_MODO, R_PRONTO, R_AJ_E, R_SEP, R_MODO, R_PRONTO, R_AJ_D, R_ACAO]
ALT_COLUNA = sum(LINHAS) + (len(LINHAS) - 1) * R_PASSO
TETO_DA_GRADE = 454
if ALT_COLUNA > TETO_DA_GRADE:
    raise SystemExit(f"ERRO: a coluna pede {ALT_COLUNA}px e a grade tem "
                     f"{TETO_DA_GRADE}px — o quadro passaria a rolar por dentro.")

CSS_DA_CENA = f"""
  .duas-colunas{{
    --r-nome:{R_NOME}px;--r-modo:{R_MODO}px;--r-pronto:{R_PRONTO}px;
    --r-aj-e:{R_AJ_E}px;--r-sep:{R_SEP}px;--r-aj-d:{R_AJ_D}px;
    --r-acao:{R_ACAO}px;--r-passo:{R_PASSO}px;
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
          <div><span class="sec-rot">Controle</span></div>
          <div><span class="sec-rot">{glifo("l2", tam=GL)}<span class="duas">Gatilho<br>esquerdo</span></span></div>
          <div><span class="sec-rot">Efeito pronto</span></div>
          <div class="no-topo"><span class="sec-rot">Ajustes</span></div>
<!-- ESTE ELEMENTO É CÉLULA DA GRADE, não enfeite. Ele ocupa a trilha de
               1px que separa o bloco do L2 do bloco do R2 (`grid-template-rows`
               em `.duas-colunas > div`). Tirei-o em 30/08 pensando que era só um
               traço, e "Gatilho direito" caiu nessa trilha e nasceu com **1px de
               altura** — as cinco colunas saíram de registro e as divisórias
               passaram a cortar o conteúdo de P3 e P4 no meio. O traço VISÍVEL
               agora vem da borda de célula (`--rot-linha`); esta célula só guarda
               o lugar, e por isso não leva borda. -->
          <div class="vao-l2-r2"></div>
          <div><span class="sec-rot">{glifo("r2", tam=GL)}<span class="duas">Gatilho<br>direito</span></span></div>
          <div><span class="sec-rot">Efeito pronto</span></div>
          <div class="no-topo"><span class="sec-rot">Ajustes</span></div>
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
    <li><b>A caixa de ajustes vale o maior modo que está na LINHA</b> — {N_ESQ} barras no L2 (a
        Metralhadora do P1) e {N_DIR} no R2 (a Vibração do P3). O modo com duas barras ocupa as duas
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

n = monta("03-gatilhos", "Gatilhos", MIOLO, CSS + CSS_DA_CENA,
          fita_viva=False, legenda=LEGENDA)
print(f"03-gatilhos: OK, {n} divs · {len(MESA)} controles lado a lado · "
      f"{len(MODOS)} modos por gatilho · fita esmaecida")
