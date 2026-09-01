#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O MAPA DO CONTROLE — a fonte da verdade das peças, funcional.

Pedido dela, 27/08/2026:
  "vamos fazer um mapa svg totalmente funcional com cada botão desenhado no lado
   mas com os botões da tela acendendo quando passamos o mouse por cima. Vamos
   fazer isso separado. botões svg do lado direito e o controle fullscream no lado
   esquerdo com botões quadrado, bola...todos os botões no controle iguais os svgs
   glifos nosso."
e, logo depois:
  "isso sempre vai dar problema vamos criar uma fonte da verdade universal."

POR QUE ELE EXISTE. O SVG chamava de `l2` e `r2` duas peças que são o Share e o
Options — elas ficam ao lado do touchpad, e o gatilho não fica. Nenhuma régua
comparava o NOME da peça com o LUGAR dela, então o erro atravessou dois meses.
Aqui os dois aparecem juntos: passe o mouse num glifo e a peça acende no desenho;
passe na peça e o glifo acende. Nome e lugar ficam na mesma tela, e a divergência
salta aos olhos.

Sem uma linha de script: o cruzamento é `:has()`.

    python3 mapa.py      -> layout/mapa-do-controle.html
"""
import csv, json, pathlib, re, sys

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
R = pathlib.Path(__file__).resolve().parents[2]
CSV = R / "docs/data/pecas-do-dualsense.csv"
CSV_CORES = R / "docs/data/cores-do-dualsense.csv"

# O PADRÃO DAS CINCO LÂMPADAS E A COR DE CADA JOGADOR VÊM DO PRODUTO, e não de
# uma tabela digitada aqui. O `monta.py` tinha uma cópia, e nela o jogador 3
# estava escrito "234" quando o canônico é "135" — as duas pontas e o centro.
# Ninguém tinha visto porque os mockups só usam os jogadores 1 e 2. Banco de
# provas com tabela própria prova a tabela dele, não o produto.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(R / "src"))
import onde  # noqa: E402
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402
    player_led_pattern,
    player_slot_color,
)
GLIFOS = R / "assets/glyphs"
SVG = R / "layout/_ferramentas/ds_limpo.svg"
# A SAÍDA É A BANCADA — 31/08/2026. Este gerador tinha ficado de fora quando o
# escopo foi reduzido a "só o mockup"; ele voltou porque ela pediu mudança no
# mapa (a linha de instrução do hover). Escrever em `layout/` trocaria o
# produto que ela usa, sem ela ver.
SAIDA = onde.pagina("mapa-do-controle.html")

REGIOES = [("face", "Botões da face"), ("direcional", "Direcional"),
           ("ombros", "Ombros"), ("gatilhos", "Gatilhos"),
           ("analogicos", "Analógicos"), ("centro", "Centro"),
           ("sensores", "Sensores"), ("luzes", "Luzes"),
           ("audio", "Áudio"), ("energia", "Energia"), ("vibracao", "Vibração"),
           ("chassi", "Chassi")]


def le_csv():
    linhas = [l for l in CSV.read_text().splitlines() if l and not l.startswith("#")]
    return list(csv.DictReader(linhas))


def glifo(nome, tam=30, ativo=False):
    arq = GLIFOS / f"{nome}{'_active' if ativo else ''}.svg"
    if not arq.exists():
        return ""
    x = arq.read_text()
    x = re.sub(r"<\?xml[^>]*\?>\s*", "", x)
    x = re.sub(r"<!--.*?-->", "", x, flags=re.S)
    # TODA cor do glifo vira `currentColor`, e não só duas. A lista fixa de dois
    # hexadecimais deixava de fora os glifos escritos com outra cor — e ali o glifo
    # ficava CRAVADO em cinza claro: no hover a peça acendia em rosa e o símbolo
    # sumia por baixo contraste. Ela viu: "ao passar o mouse em cima de um botão o
    # glifo some". Medido no triângulo: stroke rgb(200,204,218) sobre rgb(255,121,198).
    x = re.sub(r'(stroke|fill)="#[0-9a-fA-F]{3,8}"', r'\1="currentColor"', x)
    x = re.sub(r'\s+width="32"\s+height="32"', "", x)
    return x.replace("<svg ", f'<svg width="{tam}" height="{tam}" ', 1).strip()


# O LIGHTBAR é a única peça cuja caixa não é a peça: são DUAS tiras, e o vão entre
# elas é o touchpad. As faixas abaixo saem da medição das tiras no navegador — cada
# uma segue a borda do touchpad, da esquerda 39,9–44,1 e da direita 83,9–88,3.
CAIXAS_PROPRIAS = {
    "lightbar": [(38.9, 30.0, 45.1, 52.0), (82.9, 30.0, 89.3, 52.0)],
}


# QUAL SUBPATH É O CONTORNO EXTERNO, medido no navegador por `medir-subpaths.py`.
# Em 8 das 23 peças de vários subpaths o externo NÃO é o primeiro — nos quatro
# botões da face e nos quatro braços do d-pad o `d` começa pelo FURO. Duas
# heurísticas minhas erraram nisso, e a segunda deixou as 27 peças sem responder ao
# ponteiro. Path com arco relativo não se mede por regex: mede-se renderizando.
EXTERNO = {}
_ext = pathlib.Path(__file__).with_name("subpath-externo.json")
if _ext.exists():
    EXTERNO = __import__("json").loads(_ext.read_text())


def subpath_externo(d, pid=None, k=0):
    """De um path de vários subpaths, o que CONTÉM os outros.

    Não é o primeiro: no triângulo o `d` começa pelo arco de r=2,5, que é o FURO, e
    o contorno de r=3,5 vem depois. Pegar o primeiro deu um alvo do tamanho do
    buraco, e nenhuma das 27 peças respondia ao ponteiro.

    A escolha é pela EXTENSÃO: o subpath cujos números cobrem a maior área é o de
    fora. Serve para faixa, anel e cápsula, que é tudo o que este desenho usa.
    """
    partes = [p for p in re.split(r"(?<=Z)\s*(?=M)|\s(?=M\s)", d.strip()) if p.strip()]
    if len(partes) < 2:
        return d
    q = EXTERNO.get(f"{pid}|{k}", 0)
    return partes[q] if q < len(partes) else partes[0]


def bloco_fim(s, i):
    """O índice logo depois do </g> que fecha o <g> que abre em `i`."""
    prof, j = 0, i
    while True:
        n = re.search(r"<g\b|</g>", s[j:])
        if not n:
            return len(s)
        j += n.end()
        prof += 1 if n.group(0) == "<g" else -1
        if prof == 0:
            return j


def forma_cheia(svg_txt, pid):
    """O desenho da peça, com cada path reduzido ao seu contorno EXTERNO.

    O ALVO É A PEÇA. Ela, 27/08: "as áreas que acendem não estão perfeitamente
    sobrepostas ... eu to falando das partes transparentes que servem pra acender".
    Estava certo — o alvo era um retângulo com 1 unidade de folga em volta da
    caixa, e para o d-pad, o triângulo ou o casco a caixa não é a peça.

    O motivo de ter sido retângulo: o segundo subpath de uma faixa ou de um anel é
    o FURO, e com ele o ponteiro passava pelo meio do botão. Guardando só o
    primeiro subpath, o furo some e a área fica exatamente a da peça.
    """
    marca = f'id="mp-{pid}"'
    if marca not in svg_txt:
        return ""
    i = svg_txt.index(marca)
    ini = svg_txt.rindex("<g ", 0, i)
    prof, j = 0, ini
    while True:
        n = re.search(r"<g\b|</g>", svg_txt[j:])
        if not n:
            break
        j += n.end()
        prof += 1 if n.group(0) == "<g" else -1
        if prof == 0:
            break
    bloco = svg_txt[ini:j]
    # TODOS os transforms da cadeia viajam junto, não só o do próprio grupo.
    # Ela fez o Options espelhando o Share com `matrix(-1,0,0,1,...)`, e o espelho
    # vive num ANCESTRAL: lendo só o transform do grupo da peça, o alvo do Options
    # nascia em x negativo, do outro lado da tela.
    cadeia = []
    k = ini
    while True:
        p = svg_txt.rfind("<g ", 0, k)
        if p < 0:
            break
        if bloco_fim(svg_txt, p) > j:          # é ancestral de verdade
            t = re.search(r'\stransform="([^"]*)"', svg_txt[p:svg_txt.index(">", p)])
            if t:
                cadeia.insert(0, t.group(1))
        k = p
    tg_self = re.search(r'<g\b[^>]*\stransform="([^"]*)"', bloco)
    if tg_self:
        cadeia.append(tg_self.group(1))
    tg = type("M", (), {"group": lambda s, i: " ".join(cadeia)})() if cadeia else None
    fora, k = [], -1
    # TAG COM FILHO TAMBÉM CONTA. O ciclo exportar->importar deu <title> a cada
    # sub-peça, e com isso `<circle .../>` virou `<circle ...><title/></circle>`.
    # O regex exigia `/>`: os 9 furos do alto-falante, as 5 lâmpadas, as 2 tiras do
    # lightbar e a bateria ficaram SEM ALVO NENHUM, e o portão as reprovou.
    for mm in re.finditer(r"<(rect|path|circle|ellipse|polygon)\b[^>]*?/?>", bloco):
        t = mm.group(0)
        if not t.endswith("/>"):
            t = t[:-1] + "/>"
        if mm.group(1) == "path":
            k += 1
        # a peça do PS é `sem-tinta` — o glifo é o botão —, mas o ALVO dela existe:
        # é por ele que se aponta o botão no desenho.
        d_ = re.search(r'\sd="([^"]*)"', t)
        if d_:
            t = t.replace(d_.group(0), f' d="{subpath_externo(d_.group(1), pid, k)}"')
        # O `style` sai — mas o que dele POSICIONA fica. Ela desenhou o Options
        # espelhando o Share, e o `transform-origin` da matriz vive no style: sem
        # ele a matriz aplica a partir de (0,0) e o alvo voa para x=166, fora do
        # desenho. Cor sai, geometria fica.
        st = re.search(r'\sstyle="([^"]*)"', t)
        posicao = ""
        if st:
            manter = [d_.strip() for d_ in st.group(1).split(";")
                      if d_.strip().startswith(("transform-origin", "transform-box", "transform"))]
            if manter:
                posicao = ' style="' + "; ".join(manter) + '"'
        t = re.sub(r'\s(class|id|fill|fill-rule|stroke|stroke-width|style|opacity)="[^"]*"', "", t)
        t = t[:-2] + posicao + "/>"
        fora.append(t)
    if not fora:
        return ""
    dentro = "".join(fora)
    return f'<g transform="{tg.group(1)}">{dentro}</g>' if tg else dentro


def caixas(pid, x1, y1, x2, y2):
    return CAIXAS_PROPRIAS.get(pid, [(x1, y1, x2, y2)])


# ---------------------------------------------------------------------------
# SOBRE O DESENHO, O GLIFO NÃO REPETE O QUE A PEÇA JÁ DIZ.
# Três defeitos, a mesma causa: o glifo foi feito para viver SOZINHO numa lista, e
# por isso carrega a moldura da peça junto. Por cima da peça, essa moldura vira uma
# segunda borda.
#   - o anel do stick_l/r sobre o analógico dava as "várias voltas" que ela reprovou;
#   - o retângulo do l1/r1/l2/r2 é um crachá boiando dentro do botão (0,0% de
#     interseção com a peça, medido);
#   - a seta do l2/r2 saía da peça, entrava 15,1px no L1 e pousava no crachá dele:
#     os dois lidos juntos viravam um fluxograma "L2 -> L1";
#   - o anel do `circle` era a TERCEIRA volta concêntrica do mesmo botão.
# Sobre o desenho fica só a LETRAGEM; a moldura continua na lista, onde faz falta.
# O CENTRO DA TINTA de cada glifo, medido uma vez no navegador com getBBox().
# O gerador centrava o ponto (16,16) da caixa; glifo com tinta fora do centro da
# própria caixa nascia deslocado (o pior, 2,25px).
# A POSIÇÃO QUE ELA DEU A CADA GLIFO, quando existe. Nasce do ciclo
# exportar -> ela arruma no editor -> importar. Quando o arquivo existe, ele MANDA:
# o cálculo é só o ponto de partida, e ela é quem decide onde o símbolo fica.
POS_GLIFO = {}
_pos = pathlib.Path(__file__).with_name("posicao-dos-glifos.json")
if _pos.exists():
    POS_GLIFO = __import__("json").loads(_pos.read_text())

TINTA = {}
_tinta = pathlib.Path(__file__).with_name("centro-da-tinta.json")
if _tinta.exists():
    TINTA = {k: tuple(v) for k, v in __import__("json").loads(_tinta.read_text()).items()}

# PEÇAS QUE NÃO GANHAM ALVO NO DESENHO, e por quê.
# O giroscópio e o acelerômetro medem o movimento do CONTROLE INTEIRO — a região
# deles É o corpo. Três alvos sobre a mesma área não se apontam: um cobre o outro,
# e o que a pessoa aponta passa a ser sorteio. Eles acendem a partir da LISTA, que
# é o sentido que importa; no desenho, quem responde ali é o corpo.
# A BATERIA entra junto: a peça dela É o lightbar (decisão dela, 27/08 — as
# duas tiras são o medidor). Dois alvos sobre a mesma forma viram sorteio.
SEM_ALVO = {"feat-giroscopio", "feat-acelerometro", "feat-bateria"}

# O PS ACENDE PELO GLIFO, e só. Ela, 27/08: "no PS. Remove o circulo e Deixa só o
# Glifo do PS pra ser o Botão." A peça dele já é `sem-tinta`, mas o ALVO — que
# existe para o mouse — recebia tinta no hover e o disco voltava por baixo do
# símbolo. Aqui ele fica transparente sempre; quem acende é o glifo.
SO_O_GLIFO_ACENDE = {"ps"}

# NO HOVER O GLIFO FICA CLARO, e não escuro. Escurecê-lo resolvia o símbolo que
# cai sobre a MASSA da peça acesa, e criava o inverso no que cai sobre o FURO:
# os botões da face são anéis, o símbolo mora no miolo, e o miolo é o fundo
# escuro — escuro sobre escuro some igual. Claro aparece nos dois: 15:1 contra o
# furo, 2,1:1 contra o rosa, e é no furo que o símbolo mora.
# O MICROFONE fica AO LADO da peça, não em cima. A peça dele é uma fresta de
# 7,0 x 1,0; qualquer glifo alto por cima dela é riscado no meio pelo próprio
# traço, e o composto lê MUDO — um estado que não está na tela.
# ONDE O GLIFO NÃO CABE DENTRO, ELE VAI PARA FORA. Ela, 27/08: "esses dois glifos
# ficam acima dos botões não dentro" (Share e Options) — as peças deles têm 3 x 6 e
# o glifo por dentro sai da cápsula por todos os lados.
AO_LADO = {"mic": (0, 3.4)}
# O y ABSOLUTO do glifo, quando ele mora fora da peça e precisa correr na mesma
# linha do irmão do outro lado. O botão do Share e o do Options ocupam y 32,96 a
# 38,98; o glifo fica logo acima, em 32,0.
MESMA_LINHA = {"share": 31.4, "options": 31.4}
# E CADA UM PARA O SEU LADO. Ela, 27/08: "options o glifo move pra direita, share
# glifo move pra esquerda, ambos pra alinharem com os botões que representam". As
# duas peças são cápsulas inclinadas 14°, e o centro da CAIXA delas não é o centro
# da cápsula — alinhar pela caixa deixava os dois puxados para o meio da tela.
DESLOCA_X = {"share": -1.4, "options": 1.4}

# O TAMANHO, quando a conta pela peça não serve. Ela pediu, uma a uma:
#   "aumentar glifo do ps, R, L"  ·  "diminuir os glifos do opções"
#   "glifo do microfone tá muito grande"
TAMANHO = {"ps": 8.6, "stick_l": 14.0, "stick_r": 14.0,
           "share": 3.4, "options": 3.4, "mic": 3.0,
           # os quatro da face são ANÉIS de r=2,5 a 3,5: o símbolo tem de caber no
           # FURO, que tem 5,0 de diâmetro. O piso de 5,2 os fazia transbordar o
           # anel e, no hover, o composto virava um borrão em vez de um triângulo.
           "triangle": 4.2, "circle": 4.2, "square": 4.2, "cross": 4.2,
           # o d-pad é uma pétala de 7 x 8,5 com miolo vazado de ~4,5
           "dpad_up": 4.4, "dpad_down": 4.4, "dpad_left": 4.4, "dpad_right": 4.4}
# A BOLA VOLTA. Eu a tinha tirado porque o glifo do ○ é um anel sobre um botão que
# já é um anel — mas ela reparou na ausência ("o glifo de bola tá apagado"), e a
# ausência confunde mais que a repetição: era o único botão da face sem símbolo.
SEM_GLIFO_NO_DESENHO = set()


# A LETRA DO OMBRO SOBE. Ela, 27/08/2026: "o l1 e o r1 precisam subir um pouco
# (as letras apenas) pois estão sendo cortadas também".
#
# A causa NÃO é a fonte, e a primeira hipótese errou por isso. Medido: o `<text>`
# está exatamente no centro do glifo (`getBBox` devolve 16,00 de 32 nas quatro
# peças). **O que não está no centro é a CAIXA.** As quatro cápsulas dos ombros
# são inclinadas, e a letra é horizontal: no x onde ela mora, o miolo da cápsula
# já subiu, e o centro do bounding box cai abaixo dele. É a mesma lição do
# `medir-subpaths.py` desta casa — path inclinado não se mede por caixa.
#
# Por isso o ajuste é POR PEÇA: os analógicos são círculos, o centro da caixa É o
# centro da peça, e o mesmo `dy` os desalinharia. `em` e não unidade do viewBox
# porque o glifo é escalado para caber na peça, e a correção tem de escalar junto.
SOBE_A_LETRA = {"l1": "-0.2em", "r1": "-0.2em", "l2": "-0.2em", "r2": "-0.2em"}


def sobe_a_letra(svg_txt):
    """Acrescenta o `dy` ao `<text>` dos glifos que pedem, e a nenhum outro.

    FATO SUBSTITUÍDO: aqui existia `so_a_letra(pid, g)`, que fazia isto e mais —
    arrancava a moldura do glifo e recentrava o texto. Ela **nunca era chamada**:
    virou código morto no dia em que `controle()` parou de redesenhar peça a peça
    e passou a usar o arquivo dela. Foi por isso que a primeira tentativa de subir
    a letra não mudou um pixel na tela.
    """
    for pid, dy in SOBE_A_LETRA.items():
        alvo = f'id="glifo-{pid}"'
        if alvo not in svg_txt:
            continue
        i = svg_txt.index(alvo)
        j = svg_txt.index("</g>", i)
        bloco = svg_txt[i:j]
        novo = re.sub(r"(<text\b(?![^>]*\bdy=)[^>]*?)(/?>)", rf'\1 dy="{dy}"\2',
                      bloco, count=1)
        svg_txt = svg_txt[:i] + novo + svg_txt[j:]
    return svg_txt


def controle(pecas):
    """O desenho — que É o arquivo dela — com os alvos do ponteiro por cima.

    Ela, 27/08/2026: "ué pq o svg que vc gerou do trabalho que eu fiz tá perfeito e
    o do site tá horrível? pq não estamos conseguindo trazer ele?"

    A resposta era boba: o mapa reconstruía peça a peça num arquivo próprio e, na
    cópia, cada grupo perdia a hierarquia e os transforms dos ancestrais — o
    espelho do L1, a inclinação do Options. Agora `ds_limpo.svg` É o arquivo dela,
    e esta função não redesenha nada. Ela faz duas coisas:

      1. marca cada `glifo-*` com a classe que o cruzamento com a lista usa;
      2. gera, para cada peça, um ALVO transparente com a forma dela.
    """
    x = sobe_a_letra(SVG.read_text())
    # ids únicos, para o desenho conviver com os glifos da lista à direita
    for i in sorted(set(re.findall(r'id="([^"]+)"', x)), key=len, reverse=True):
        x = (x.replace(f'id="{i}"', f'id="mp-{i}"')
              .replace(f"url(#{i})", f"url(#mp-{i})").replace(f"#{i} ", f"#mp-{i} ")
              # AS TRÊS FORMAS COM ASPAS, e é por elas que o touchpad sumia.
              # Medido em 30/08/2026: ela perguntou *"pq a área do touchpad
              # sumiu?"* e a resposta estava aqui. O editor dela escreve o
              # filtro de contorno como `style="filter: url(&quot;#outline-
              # filter-1&quot;)"` — com aspas ESCAPADAS dentro do atributo. O
              # `url(#id)` acima não casa essa forma, então o `id` ganhava o
              # prefixo `mp-` e a REFERÊNCIA não: ela ficava pendurada, o filtro
              # nunca se aplicava, e o `g#mp-touchpad` (410x231px, `fill:#000`,
              # `stroke:none`) caía no preenchimento preto cru sobre fundo
              # escuro. A peça estava lá o tempo todo — invisível.
              # Nas dez abas o defeito não aparece porque lá o id NÃO é
              # prefixado, e a referência crua resolve.
              .replace(f"url(&quot;#{i}&quot;)", f"url(&quot;#mp-{i}&quot;)")
              .replace(f'url("#{i}")', f'url("#mp-{i}")')
              .replace(f"url('#{i}')", f"url('#mp-{i}')"))
    # O `data-colorway` JÁ VEM do arquivo (scripts/gerar_cores_do_dualsense.py o
    # escreve, para o SVG abrir colorido sozinho). Escrever um segundo aqui daria
    # dois atributos iguais na mesma tag, e o navegador ignora o segundo em
    # silêncio — o dropdown mexeria num atributo que ninguém lê.
    x = x.replace("<svg ", '<svg class="ds" ', 1)
    if "data-colorway=" not in x[: x.index(">")]:
        x = x.replace("<svg ", '<svg data-colorway="cosmic-red" ', 1)

    # ---- OS GLIFOS SÃO OS DELA ----------------------------------------
    # FUNDE com a classe que já estiver na tag. Os quatro glifos da face carregam
    # `z-simbolos`, escrita pelo gerador de cores; acrescentar um SEGUNDO atributo
    # `class` faz o navegador ignorar o segundo, sem erro e sem aviso — e os
    # símbolos ficariam fora do cruzamento com a lista.
    for pid in re.findall(r'\bid="mp-glifo-([^"]+)"', x):
        alvo = f'id="mp-glifo-{pid}"'
        i = x.index(alvo)
        fim = x.index(">", i)
        tag = x[i:fim]
        ja = re.search(r'\sclass="([^"]*)"', tag)
        if ja:
            x = x[:i] + tag.replace(ja.group(0), f' class="{ja.group(1)} sobre s-{pid}"', 1) + x[fim:]
        else:
            x = x.replace(alvo, f'{alvo} class="sobre s-{pid}"', 1)
    # A COR DO GLIFO É DA FOLHA. Os dela vêm com `fill` e `stroke` dentro do
    # `style`, e style inline vence qualquer folha: no hover o símbolo continuava
    # cinza-claro sobre a peça acesa e sumia. Aqui só as declarações de COR saem
    # do style; transform, origin e o resto do desenho dela ficam intactos.
    def _sem_cor(mm):
        dentro = re.sub(r"(^|;)\s*(fill|stroke)\s*:[^;]*", r"\1", mm.group(1))
        dentro = re.sub(r";\s*;", ";", dentro).strip(" ;")
        return f' style="{dentro}"' if dentro else ""

    for mm in re.finditer(r'<g\b[^>]*\bclass="[^"]*\bsobre s-([^"]+?)"', x):
        pid = mm.group(1)
        i0 = mm.start()
        prof, j0 = 0, i0
        while True:
            n = re.search(r"<g\b|</g>", x[j0:])
            if not n:
                break
            j0 += n.end()
            prof += 1 if n.group(0) == "<g" else -1
            if prof == 0:
                break
        bloco = x[i0:j0]
        x = x[:i0] + re.sub(r'\sstyle="([^"]*)"', _sem_cor, bloco) + x[j0:]

    # ---- OS ALVOS: a forma da peça, transparente ----------------------
    alvos = []
    for p in pecas:
        pid = p["id"]
        if pid in SEM_ALVO or p["x1"] == "-":
            continue
        corpo = forma_cheia(x, pid)
        if not corpo:
            continue
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        alvos.append(((x2 - x1) * (y2 - y1), (x1, y1, x2, y2),
                      f'  <g class="alvo a-{pid}">{corpo}</g>'))

    # POR CONTENÇÃO, e só depois por área: quem cabe dentro de outro nasce por
    # cima dele. Ordenar só por área punha o L2, que apenas ENCOSTA no L1, na
    # frente do L1 inteiro.
    def dentro(a, b):
        return (a[1][0] >= b[1][0] and a[1][1] >= b[1][1]
                and a[1][2] <= b[1][2] and a[1][3] <= b[1][3])

    ordem, saida = sorted(alvos, key=lambda t: -t[0]), []
    for a in ordem:
        pos = len(saida)
        for k, b in enumerate(saida):
            if dentro(b, a):
                pos = k
                break
        saida.insert(pos, a)

    return x.replace("</svg>", "\n".join(t[2] for t in saida) + "\n</svg>", 1)

def cores_do_csv():
    """Os 28 modelos do `cores-do-dualsense.csv`, agrupados por modelo.

    O dropdown mostra os 28, e não os cinco que o desenho conhecia. Os que não
    cabem num hexadecimal — iridescente, camuflado, metálico, arte — vão MARCADOS
    na lista: eles pintam com hachura, e a lista tem de dizer por quê antes de
    ela clicar e achar que o desenho quebrou.
    """
    linhas = [x for x in CSV_CORES.read_text().splitlines()
              if x and not x.startswith("#")]
    fora = {}
    for c in csv.DictReader(linhas):
        fora.setdefault(c["id"], []).append(c)
    return fora


# As oito zonas de superfície, na ordem em que a prova as lista. `detalhe` não
# entra: é arte impressa, e o desenho não tem superfície para ela — está
# declarado em scripts/gerar_cores_do_dualsense.py, em ZONAS_SEM_ALVO.
ZONAS_NA_PROVA = ("casca_esq", "casca_dir", "painel", "touch", "botoes_face",
                  "simbolos", "dpad", "analogicos", "gatilhos")


def banco_de_provas():
    """A barra de provas: cor do plástico, jogador e barra de luz.

    Ela decide VENDO. Um CSV de 233 linhas não se confere lendo — se confere
    clicando no modelo e olhando o desenho. É por isso que esta barra existe, e é
    por isso que ela fica no topo do mapa e não numa página à parte.
    """
    modelos = cores_do_csv()
    ordem = sorted(modelos, key=lambda k: (modelos[k][0]["codigo_da_cor"], k))
    fabrica, especiais = [], []
    for mid in ordem:
        ls = modelos[mid]
        cod = ls[0]["codigo_da_cor"]
        zonas = {x["zona"] for x in ls}
        sem_hex = sorted({x["zona"] for x in ls if x["grau"] == "SEM-HEX"})
        faltam = [z for z in ZONAS_NA_PROVA if z not in zonas]
        marca = ""
        if faltam:
            marca = f" · sem amostragem em {len(faltam)}"
        elif sem_hex:
            marca = f" · {ls[0]['acabamento']} em {len(sem_hex)}"
        rot = f"{ls[0]['nome']} · {cod}{marca}"
        op = (f'<option value="{mid}"'
              + (' data-parcial="1"' if (faltam or sem_hex) else "")
              + (" selected" if mid == "cosmic-red" else "")
              + f">{rot}</option>")
        (especiais if cod[0] == "Z" else fabrica).append(op)

    # O padrão canônico e a cor de cada jogador saem do PRODUTO. `1 | vão | 3 |
    # vão | 1`: as cinco lâmpadas não são igualmente espaçadas, e o jogador 1 é a
    # CENTRAL. Medido nesta casa em 11/08.
    padroes = {n: [i + 1 for i, on in enumerate(player_led_pattern(n)) if on]
               for n in range(1, 5)}
    luzes = {n: "#%02x%02x%02x" % player_slot_color(n) for n in range(1, 5)}
    botoes_p = "".join(
        f'<button class="bt" data-jogador="{n}" title="padrão {"".join(map(str, padroes[n]))}">'
        f"{n}</button>" for n in range(1, 5))

    barra_html = f"""  <div class="provas">
    <div class="prova">
      <div class="prova-rot">Cor do plástico</div>
      <select id="cw" class="ct">
        <optgroup label="De fábrica">{"".join(fabrica)}</optgroup>
        <optgroup label="Edições especiais">{"".join(especiais)}</optgroup>
      </select>
    </div>
    <div class="prova">
      <div class="prova-rot">Jogador</div>
      <div class="linha">{botoes_p}<button class="bt" data-jogador="0">nenhum</button></div>
    </div>
    <div class="prova">
      <div class="prova-rot">Barra de luz</div>
      <div class="linha">
        <input type="color" id="luz" class="ct ct-cor" value="#0000ff">
        <button class="bt" id="luz-off">apagar</button>
      </div>
    </div>
    <div class="prova-nota" id="nota">&nbsp;</div>
  </div>
"""

    # O SCRIPT VAI NO FIM DO BODY, e não junto da barra. Ele nasceu ao lado dos
    # controles e quebrou inteiro: `document.querySelector("svg.ds")` devolvia
    # null porque o desenho ainda não existia no DOM quando o script rodou. Foram
    # 14 exceções de `reading 'dataset'` no console, e a página parecia sã — o
    # dropdown estava lá, só não fazia nada. Régua que não lê o console não pega.
    script = f"""  <script>
  // O PADRÃO E A COR SÃO DO PRODUTO — `core/led_control.py`. Copiar a tabela
  // para cá seria criar a segunda verdade que este mapa existe para matar.
  const PADRAO = {json.dumps(padroes)};
  const LUZ_DO_JOGADOR = {json.dumps(luzes)};
  const PARCIAL = "hachurado = o acabamento não cabe num hexadecimal (iridescente, "
                + "metálico, camuflado, arte); cinza chapado = zona sem amostragem.";
  const ds = document.querySelector("svg.ds");
  const barra = document.querySelector("#mp-lightbar");
  const nota = document.querySelector("#nota");

  document.querySelector("#cw").addEventListener("change", e => {{
    const op = e.target.selectedOptions[0];
    ds.dataset.colorway = e.target.value;
    nota.textContent = op.dataset.parcial ? PARCIAL : "\u00a0";
  }});

  function acende(n) {{
    for (let i = 1; i <= 5; i++)
      document.querySelector("#mp-led-jogador-" + i)
              .classList.toggle("led-on", (PADRAO[n] || []).includes(i));
    if (n && LUZ_DO_JOGADOR[n]) {{
      barra.style.setProperty("--luz", LUZ_DO_JOGADOR[n]);
      document.querySelector("#luz").value = LUZ_DO_JOGADOR[n];
    }} else {{
      barra.style.removeProperty("--luz");
    }}
    document.querySelectorAll("[data-jogador]").forEach(b =>
      b.classList.toggle("on", +b.dataset.jogador === n));
  }}
  document.querySelectorAll("[data-jogador]").forEach(b =>
    b.addEventListener("click", () => acende(+b.dataset.jogador)));

  // A BARRA DE LUZ E O JOGADOR ANDAM JUNTOS, e é assim no aparelho: o PS5 acende
  // as duas coisas ao numerar um controle. Mexer na cor à mão desfaz o vínculo —
  // a barra passa a ser a escolhida, e as lâmpadas continuam onde estavam.
  document.querySelector("#luz").addEventListener("input", e => {{
    barra.style.setProperty("--luz", e.target.value);
  }});
  document.querySelector("#luz-off").addEventListener("click", () => {{
    barra.style.removeProperty("--luz");
  }});

  // O MAPA NASCE COM LUZ. Sem jogador escolhido, o lightbar e as cinco lâmpadas
  // ficam na cor de apagado — que é o estado honesto de um controle sem luz, e
  // some sobre o fundo escuro. Ela reparou na ausência antes, com estas mesmas
  // duas peças: "faltou só os dois lightbar e os led de player". O apagado
  // continua a um clique, no botão "nenhum".
  acende(1);
  </script>
"""
    return barra_html, script


def main():
    pecas = le_csv()
    ds = controle(pecas)
    provas, script_provas = banco_de_provas()

    # ---- as regras de cruzamento, geradas peça a peça ----
    regras = []
    for p in pecas:
        i = p["id"]
        # o glifo da direita aponta -> a peça acende no desenho
        # `:is(.peca, rect, circle, path)` porque o indicador de jogador é feito de
        # cinco <rect> com fill próprio, e não de `.peca` como as outras peças.
        alvo_css = f'#mp-{i} :is(.peca, rect, circle, path, ellipse)'
        # !important: o desenho dela traz cor no `style` inline em várias peças, e
        # style inline vence folha. Sem isto o microfone (e quem mais tivesse cor
        # própria) não acendia — o portão dava verde porque media o CSS computado  # (noqa-acento: verbo medir, imperfeito)
        # da peça, que de fato não mudava, mas ninguém tinha reparado no ']'.
        if i not in SO_O_GLIFO_ACENDE:
            regras.append(f'.mapa:has(.item-{i}:hover) {alvo_css}'
                          f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')
        regras.append(f'.mapa:has(.item-{i}:hover) .s-{i}{{color:var(--fg) !important;opacity:1}}')
        # a peça do desenho aponta -> o glifo da direita acende
        regras.append(f'.mapa:has(.a-{i}:hover) .item-{i}'
                      f'{{border-color:var(--pink);background:rgba(255,121,198,.12);color:var(--fg)}}')
        regras.append(f'.mapa:has(.a-{i}:hover) .s-{i}{{color:var(--fg) !important;opacity:1}}')
        if i not in SO_O_GLIFO_ACENDE:
            regras.append(f'.mapa:has(.a-{i}:hover) {alvo_css}'
                          f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')

    # ---- a lista da direita, por região ----
    blocos = []
    for chave, titulo in REGIOES:
        na_regiao = [p for p in pecas if p["regiao"] == chave]
        if not na_regiao:
            continue
        itens = []
        for p in na_regiao:
            g = glifo(p["glifo"], tam=26) if p["glifo"] != "-" else '<span class="sem">—</span>'
            apel = f'<span class="ap">{p["apelidos"]}</span>' if p["apelidos"] not in ("-", "") else ""
            prop = ' <span class="prop">proposto</span>' if p["grau"] == "PROPOSTO" else ""
            nota = f'<span class="nota-peca" title="{p["nota"]}">i</span>' if p["nota"] else ""
            itens.append(
                f'      <div class="item item-{p["id"]}">'
                f'<span class="gl">{g}</span>'
                f'<span class="txt"><b>{p["nome"]}</b>{apel}{prop}'
                f'<span class="id mono">{p["id"]}</span></span>{nota}</div>')
        blocos.append(f'    <div class="grupo">\n      <div class="grupo-rot">{titulo}</div>\n'
                      + "\n".join(itens) + "\n    </div>")

    faltam = [p for p in pecas if p["no_svg"] == "falta"]
    sem_glifo = [p for p in pecas if p["glifo"] == "-"]

    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — o mapa do controle</title>
<style>
  :root{{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --border-sutil:#343746; --border-forte:#44475a;
    --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#8b8fa8; --comment:#6272a4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555; --yellow:#f1fa8c;
    /* A COR DO PLÁSTICO NÃO MORA MAIS AQUI. Ela vem do <style> gerado dentro do
       próprio SVG (scripts/gerar_cores_do_dualsense.py), zona por zona, dos 28
       modelos do docs/data/cores-do-dualsense.csv. O `--cosmic-red:#b11f54` que
       ficava nesta linha era um hex digitado à mão que a amostragem de 27/08
       derrubou — o Cosmic Red é #A51C48, distância 17. Fato errado, substituído.
       Quem precisa de UMA cor do casco lê `var(--z-casca-solida)`. */
    --luz-apagada:#3f4350; --led-apagado:#4a4f5c; --led-aceso:#e8ecf5;
    /* Pilha do sistema: nada de fonte web, para o arquivo abrir sem rede.
       É a regra de scripts/paleta_da_casa.py, e vale aqui igual. */
    --f:ui-sans-serif,system-ui,"Cantarell","Segoe UI",Roboto,sans-serif;
    --m:ui-monospace,"JetBrains Mono","Fira Mono","DejaVu Sans Mono",monospace;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#11121a;color:var(--fg);font-family:var(--f);padding:22px;
        display:flex;flex-direction:column;align-items:center;gap:16px}}
  .mono{{font-family:var(--m)}}
  .cx{{width:1800px;max-width:100%;background:var(--app-bg);border-radius:11px;
       border:1px solid var(--border-sutil);overflow:hidden}}
  .topo{{padding:15px 20px;border-bottom:1px solid var(--border-sutil)}}
  h1{{font-size:18px;font-weight:700}}
  h1 .p{{color:var(--pink)}}
  .sub{{font-family:var(--m);font-size:11.5px;color:var(--comment);margin-top:3px}}

  /* A LISTA GANHOU 140px E UMA TERCEIRA COLUNA — 01/09/2026, pedido dela:
     *"o que eu não quero na mapa é barra de rolagem nem pra esquerda nem
     vertical; pode ir realocando os elementos pra terem mais harmonia."*

     MEDIDO ANTES: a página pedia 1042px numa janela de 800 — 242px de rolagem
     vertical. O culpado era a LISTA, com 832px fixos, enquanto o desenho ao lado
     encolhia com a janela (710px em 1080, 387px em 800). Duas colunas de 28
     peças em 12 grupos não cabem em tela nenhuma abaixo de 1080.

     COM TRÊS COLUNAS ELA CAI PARA 573px, e a página passa a caber inteira:
     **zero rolagem vertical e zero lateral** em 1920x1080, 1600x900, 1440x900 e
     1390x800 — as quatro medidas.

     E OS 920px SÃO HARMONIA MEDIDA, que foi a outra metade do pedido dela. Com
     os 860 que a conta da rolagem pedia, **8 dos 28 itens quebravam em duas
     linhas** (`feat-rumble-esquerdo`, `feat-giroscopio`, `led-jogador`), e dois
     chegavam a 61px de altura numa lista onde o padrão é 36. Com 920 são 4, e o
     mais alto cai para 44. Testei até 1100: de 920 em diante o ganho estagna
     (24, 24, 25, 25 itens inteiros) e o desenho é que encolhe — 920 é onde a
     curva vira. */
  .mapa{{display:grid;grid-template-columns:minmax(0,1fr) 920px;gap:0;align-items:stretch}}
  .lado-ds{{padding:20px 24px;display:flex;align-items:center;justify-content:center}}
  /* A LISTA NÃO ROLA DE LADO — 31/08/2026, pedido dela: *"a página de mapa do
     dualsense tem uma barra horizontal desnecessária."*

     A CAUSA eram três regras que se contradiziam: `column-width` deixa o
     navegador criar QUANTAS colunas couberem na largura, `max-height` limita a
     altura, e `column-fill:balance` manda encher todas por igual. Quando o
     conteúdo não cabe na altura, ele não rola — ele CRIA colunas novas, e as
     que não cabem na largura vão para fora. Medido: a lista recebia 719px e
     pedia **1071** — 352px de excesso, três colunas onde cabiam duas.

     A CURA É TIRAR O TETO DE ALTURA. Sem ele, o balanceamento acontece na
     altura que a lista pede, e nenhuma coluna nasce fora. A página cresce 32px
     e rola na vertical, que é o que uma lista faz.
     `columns:330px 2` guarda as duas coisas: 330 é a largura ideal de cada
     coluna e 2 é o TETO — numa tela estreita ele cai para uma sozinho, em vez
     de espremer duas. */
  .lado-lista{{border-left:1px solid var(--border-sutil);padding:14px 18px;
               columns:260px 3;column-gap:20px;column-fill:balance}}
  .grupo{{break-inside:avoid;-webkit-column-break-inside:avoid}}
  .ds{{width:100%;height:auto;max-height:74vh}}
  /* TUDO PREENCHIDO — decisão dela, 27/08: os paths deste SVG são FAIXAS e
     ANÉIS. Traçá-los fazia cada aresta virar dois fios a 0,99 de distância:
     era a linha dupla do casco, as várias voltas dos botões, os furos do
     alto-falante em rosquinha e as lâmpadas ocas — tudo a mesma causa. */
  .ds .peca,.ds .corpo{{stroke:none}}
  /* TODA PEÇA PINTA COMO PEÇA, mesmo sem a classe. O desenho dela nem sempre
     carrega `class="peca"` — o Options, por exemplo, ficou sem `fill` nenhum e
     herdou o preto padrão do SVG. Aqui a folha alcança qualquer forma que viva
     dentro de um grupo de peça e não seja glifo. */
  .ds g[id^="mp-"]:not([id^="mp-glifo"]):not(.sobre):not(.alvo)
    > :is(rect,path,circle,ellipse,polygon){{fill:var(--z-casca-solida)}}
  /* O LIGHTBAR E O INDICADOR DE JOGADOR SÃO LUZ, e não plástico. Na cor do casco
     eles caíam sobre a borda do touchpad e sumiam — ela: "faltou só os dois
     lighbar e os led de player". Cor de luz, e aparecem. */
  .ds #mp-lightbar *{{fill:var(--luz, var(--luz-apagada))}}
  .ds #mp-led-jogador rect{{fill:var(--led-apagado)}}
  .ds #mp-led-jogador rect.led-on{{fill:var(--led-aceso)}}
  /* o PS não tem anel: a peça existe só para dar caixa e alvo, e quem se vê — e
     quem acende — é o glifo. Decisão dela, 27/08: "Remove o circulo e Deixa só o
     Glifo do PS pra ser o Botão". */
  .ds .sem-tinta{{fill:none !important;stroke:none !important}}
  /* A PONTA DO PUNHO fechava em BICO: a borda externa e a interna do punho
     convergem num vértice agudo, e preenchidas isso vira uma farpa. O traço
     da mesma cor com junta redonda arredonda o vértice sem mudar o path. */
  .ds #mp-corpo .peca,.ds #mp-corpo .corpo{{stroke:var(--z-casca-solida);stroke-width:.42;
                      stroke-linejoin:round;stroke-linecap:round}}
  /* no MAPA as features aparecem — é o mapa das peças todas, não de uma aba */
  /* AS FEATURES SÓ APARECEM NO HOVER. Em repouso, as caixas tracejadas do
     giroscópio, do acelerômetro e da bateria empilhavam-se no meio do corpo e
     escondiam o alto-falante, o indicador de jogador e o microfone. */
  .ds .oculta{{opacity:0 !important}}
  /* e ACENDEM no hover — a regra de acender tem de vencer o !important que as
     esconde, senão o sensor e os motores não respondem a nada. */
  .mapa:has(.item-feat-giroscopio:hover) #mp-feat-giroscopio,
  .mapa:has(.a-feat-giroscopio:hover) #mp-feat-giroscopio,
  .mapa:has(.item-feat-acelerometro:hover) #mp-feat-acelerometro,
  .mapa:has(.a-feat-acelerometro:hover) #mp-feat-acelerometro,
  .mapa:has(.item-feat-bateria:hover) #mp-feat-bateria,
  .mapa:has(.a-feat-bateria:hover) #mp-feat-bateria,
  .mapa:has(.item-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo,
  .mapa:has(.a-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo,
  .mapa:has(.item-feat-rumble-direito:hover) #mp-feat-rumble-direito,
  .mapa:has(.a-feat-rumble-direito:hover) #mp-feat-rumble-direito{{opacity:1 !important}}

  /* O CORPO INTEGRA O TOUCHPAD. Ela, 27/08: "delimitação do corpo precisa ser
     corrigida integra o touchpad também" — o touchpad é parte do corpo, e acender
     um sem o outro desenha um buraco no meio da peça. */
  .mapa:has(.item-corpo:hover) #mp-touchpad :is(.peca,rect,circle,path,ellipse),
  .mapa:has(.a-corpo:hover) #mp-touchpad :is(.peca,rect,circle,path,ellipse)
    {{fill:var(--pink) !important;stroke:var(--pink) !important}}
  /* O MARCADOR DE SENSOR É PREENCHIDO, como todo o resto do desenho.
     FATO SUBSTITUÍDO: aqui ele era vazado e tracejado, "senão vira uma laje opaca
     que apaga o PS, o microfone e a grade do alto-falante" — e era verdade
     enquanto o giroscópio e o acelerômetro USAVAM O PATH DO CORPO INTEIRO. Agora
     que cada um tem a forma da própria região, não há laje: os dois são anéis, e
     anel é vazado por construção. O tracejado, esse, serrilhava a borda de tudo —
     era o que ela via nos sensores e nos dois motores. */
  .ds .oculta .peca{{stroke-width:.32;stroke-linejoin:round}}
  /* E ACENDEM NA COR DA CASA. A `feat-bateria` veio do editor com `fill="#3a3f4b"`
     como ATRIBUTO — cinza sobre fundo escuro: ela ficava visível e invisível ao
     mesmo tempo, que foi o "não tá funcionando" que ela viu. */
  .mapa:has(.item-feat-giroscopio:hover) #mp-feat-giroscopio .peca,
  .mapa:has(.item-feat-acelerometro:hover) #mp-feat-acelerometro .peca,
  .mapa:has(.item-feat-bateria:hover) #mp-feat-bateria .peca,
  .mapa:has(.item-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo .peca,
  .mapa:has(.item-feat-rumble-direito:hover) #mp-feat-rumble-direito .peca
    {{fill:var(--pink) !important;stroke:var(--pink) !important}}
  /* A BATERIA É O LIGHTBAR. Decisão dela, 27/08: "bateria pode ser usando as
     barras da lightbar com 100% e a barra cheia e 0% ela apagada". Apontá-la sem
     acender as duas tiras é apontar um medidor que não está ali. */
  .mapa:has(.item-feat-bateria:hover) #mp-lightbar :is(.peca,rect,path,circle,ellipse)
    {{fill:var(--pink) !important;stroke:var(--pink) !important}}
  .mapa:has(.item-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo,
  .mapa:has(.a-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo,
  .mapa:has(.item-feat-rumble-direito:hover) #mp-feat-rumble-direito,
  .mapa:has(.a-feat-rumble-direito:hover) #mp-feat-rumble-direito,
  .mapa:has(.item-feat-giroscopio:hover) #mp-feat-giroscopio,
  .mapa:has(.a-feat-giroscopio:hover) #mp-feat-giroscopio,
  .mapa:has(.item-feat-acelerometro:hover) #mp-feat-acelerometro,
  .mapa:has(.a-feat-acelerometro:hover) #mp-feat-acelerometro,
  .mapa:has(.item-feat-bateria:hover) #mp-feat-bateria,
  .mapa:has(.a-feat-bateria:hover) #mp-feat-bateria{{opacity:1}}
  .ds #mp-corpo .peca{{stroke:var(--z-casca-solida)}}
  /* os glifos POR CIMA do desenho — a mesma peça, vista de dois jeitos */
  .sobre{{color:var(--texto-suave);opacity:.8;pointer-events:none}}
  /* OS GLIFOS DELA TRAZEM COR NO `style` INLINE, e style inline vence folha: no
     hover eles continuavam cinza-claro sobre a peça acesa e sumiam. `currentColor`
     com !important devolve a palavra à folha, sem tocar no desenho dela. */
  /* TODO descendente que não peça `none` pinta com a cor do grupo — inclusive o
     que não declara `fill` nenhum. As setas do d-pad dela são exatamente assim:
     sem atributo e sem style de cor, herdavam o preto padrão do SVG, e no hover
     não tinham como acender. Selecionar por atributo não as alcançava. */
  .sobre *:not([fill="none"]):not(title){{fill:currentColor !important}}
  .sobre [stroke]:not([stroke="none"]){{stroke:currentColor !important}}
  .sobre text,.sobre tspan{{fill:currentColor !important}}
  /* O ALVO É A PEÇA: transparente, sem traço, e com a FORMA dela. */
  /* O ALVO É A PEÇA — transparente, com a FORMA dela, e engordado pelo TRAÇO.
     A forma exata sozinha deixava as peças finas (o lightbar, os furos do
     alto-falante, as lâmpadas do indicador, a cápsula do Share) pequenas demais
     para apontar: 6 das 29 não respondiam. O traço transparente de 1,8 acrescenta
     0,9 de cada lado sem deslocar nem deformar nada. */
  .alvo,.alvo *{{fill:transparent;stroke:transparent;stroke-width:1.8;
                stroke-linejoin:round;stroke-linecap:round;
                pointer-events:all;cursor:pointer}}
                pointer-events:all;cursor:pointer}}
  .sobre svg{{overflow:visible}}
  /* a pena do glifo, em unidades da PEÇA e não do glifo: sem isto ela variava
     com o tamanho e saía até 38% mais grossa que o traço do desenho. */
  .sobre{{--pena:.35}}
  .sobre [stroke-width]{{stroke-width:calc(var(--pena) * 32 / var(--lado))}}

  /* A LISTA CABE EM DUAS COLUNAS, E A PÁGINA NÃO ROLA. Medido em 27/08/2026,
     depois de a barra de provas nascer: a lista transbordava para uma TERCEIRA
     coluna, e a linha "Corpo" — a última — caía fora da caixa, invisível e
     inalcançável. É a mesma cicatriz que o portão das peças já nomeia, e ela
     voltou porque a barra roubou altura.
     A cura é na ALTURA, encolhendo o mais alto — regra dela, 27/08 —, e não em
     `space-between`: o item passa de 38 para 36 px, que é o `--h-escolha` da
     escala desta casa, e o vão entre grupos de 13/11 para 11/9. Com isso o
     conteúdo cai de 864 para 832 px, cabe nas duas colunas, e a página fecha
     com ZERO de rolagem (era 12 px). */
  .grupo + .grupo{{margin-top:11px;padding-top:9px;border-top:1px solid var(--border-sutil)}}
  .grupo-rot{{font-size:10.5px;color:var(--comment);
              letter-spacing:.6px;margin-bottom:6px}}
  .item{{display:flex;align-items:center;gap:11px;padding:4px 9px;border-radius:7px;
         border:1px solid transparent;color:var(--texto-suave);cursor:default}}
  .item:hover{{border-color:var(--border-forte);background:rgba(255,121,198,.06);cursor:pointer}}
  .item .gl{{flex:0 0 26px;height:26px;display:flex;align-items:center;justify-content:center}}
  .item .sem{{color:var(--border-forte);font-size:15px}}
  .item .txt{{display:flex;align-items:baseline;gap:8px;flex:1;min-width:0}}
  .item .txt b{{font-size:12px;font-weight:600}}
  .item .ap{{font-size:11px;color:var(--texto-mudo)}}
  .item .id{{margin-left:auto;font-size:10.5px;color:var(--texto-mudo)}}
  .item .prop{{font-size:9.5px;color:var(--orange);border:1px solid var(--orange);
               border-radius:4px;padding:0 4px;}}
  .nota-peca{{flex:0 0 15px;width:15px;height:15px;border-radius:50%;font-size:10px;
              line-height:13px;text-align:center;border:1px solid var(--border-forte);
              color:var(--texto-mudo);cursor:help;font-family:var(--m)}}
  .nota-peca:hover{{border-color:var(--cyan);color:var(--cyan)}}

  /* A BARRA DE PROVAS. A gramática é a da lista da direita — mesmo rótulo em
     versalete, mesma família de caixa —, para a barra não parecer colada de
     outra tela. Três blocos, e a BARRA VERTICAL entre eles: é o separador que
     ela pediu em 27/08 ("uma barra vertical entre os blocos"). */
  .provas{{display:flex;align-items:stretch;border-bottom:1px solid var(--border-sutil)}}
  .prova{{padding:11px 18px;display:flex;flex-direction:column;gap:7px;justify-content:space-between}}
  .prova + .prova{{border-left:1px solid var(--border-sutil)}}
  /* O RÓTULO DOS TRÊS BLOCOS COMEÇA NO MESMO x, e os três terminam no mesmo y.
     O vão se cura na ALTURA — os controles têm todos 28px —, nunca com
     `space-between` entre eles: ela reprovou isso com todas as letras. */
  .prova-rot{{font-size:10.5px;color:var(--comment);
              letter-spacing:.6px;line-height:1}}
  .prova .linha{{display:flex;gap:6px;align-items:center}}
  .ct{{height:28px;background:var(--elevated);color:var(--fg);
       border:1px solid var(--border-forte);border-radius:6px;
       padding:0 8px;font-family:var(--f);font-size:12px}}
  .ct-cor{{width:44px;padding:2px;cursor:pointer}}
  /* OS QUATRO NÚMEROS SÃO UMA FAMÍLIA, e família tem a mesma largura. O
     "nenhum" e o "apagar" são outro papel — palavra, não número — e por isso
     medem o que a palavra pede. */
  .bt{{height:28px;min-width:30px;padding:0 9px;background:var(--elevated);
       color:var(--texto-suave);border:1px solid var(--border-forte);
       border-radius:6px;font-family:var(--f);font-size:12px;cursor:pointer}}
  .bt:hover{{border-color:var(--pink);color:var(--fg)}}
  .bt.on{{border-color:var(--pink);background:rgba(255,121,198,.14);color:var(--fg)}}
  .prova-nota{{margin-left:auto;align-self:center;padding:0 18px;max-width:460px;
               font-size:11px;line-height:1.45;color:var(--texto-mudo)}}

  .rodape{{padding:12px 20px;border-top:1px solid var(--border-sutil);
           font-size:11.5px;color:var(--texto-mudo);display:flex;gap:22px;flex-wrap:wrap}}
  .rodape b{{color:var(--texto-suave)}}
  /* O BOTÃO DE VOLTAR — 30/08/2026, pergunta dela: *"ok temos um botão pra vir
     pra cá. Mas e o botão pra voltar?"*. Não havia: `grep href` no mapa gerado
     devolvia ZERO. Quem entrava aqui só saía pelo botão do navegador — e o
     mockup abre como ARQUIVO, onde nem sempre há um.
     O destino não é chute: `grep -l mapa-do-controle.html layout/*.html`
     devolve UMA aba, a Navegação. Cada mapa tem uma origem só. */
  .voltar{{position:absolute;left:0;top:2px;display:inline-flex;align-items:center;gap:6px;
           padding:5px 11px;border-radius:7px;text-decoration:none;
           border:1px solid var(--border-forte);background:var(--panel);
           color:var(--texto-suave);font-size:12px}}
  .voltar:hover{{border-color:var(--purple);color:var(--fg)}}
  .topo{{position:relative;padding-left:132px}}


{chr(10).join("  " + r for r in regras)}
</style>
</head>
<body>

<div class="cx">
  <div class="topo">
    <!-- O VOLTAR VOLTA PARA DE ONDE VEIO. Medido em 31/08/2026: DUAS abas
         abrem este mapa — a Controles (o botão novo, pedido dela) e a
         Navegação (`a.porta`). Um destino fixo estaria errado para metade de
         quem chega. O `href` é o fallback de quem abre o arquivo direto, com
         duplo clique, que é como ela abre. -->
    <a class="voltar" href="02-controles.html"
       onclick="if (document.referrer) {{ history.back(); return false }}"
       title="Volta para a aba de onde você veio.">← Voltar</a>
    <h1><span class="p">O mapa do controle</span> — a fonte da verdade das peças</h1>
    <!-- A LINHA DE INSTRUÇÃO SAIU — decisão dela, 31/08/2026: *"passe o mouse
         num glifo e a peça acende no desenho · passe na peça e o glifo acende
         só remove isso."* O comportamento FICA: o que sai é a legenda que o
         narrava. Quem passa o mouse descobre em meio segundo; quem não passa
         não precisava da frase. -->
  </div>

{provas}
  <div class="mapa">
    <div class="lado-ds">
{ds}
    </div>
    <div class="lado-lista">
{chr(10).join(blocos)}
    </div>
  </div>

  <div class="rodape">
    <span><b>{len(pecas)}</b> peças</span>
    <span><b>{len([p for p in pecas if p["glifo"] != "-"])}</b> com glifo · <b>{len(sem_glifo)}</b> sem</span>
    <span><b>{len([p for p in pecas if p["grau"] == "PROPOSTO"])}</b> propostas, a conferir</span>
    <span><b>{len(cores_do_csv())}</b> modelos de cor · <b>{len(ZONAS_NA_PROVA)}</b> zonas</span>
    <span>fontes: <b class="mono">docs/data/pecas-do-dualsense.csv</b>
      · <b class="mono">docs/data/cores-do-dualsense.csv</b></span>
  </div>
</div>

{script_provas}
</body>
</html>
'''
    SAIDA.write_text(html)
    print(f"mapa-do-controle.html: {len(pecas)} peças, {len(regras)} regras de cruzamento")
    if faltam:
        print("  sem desenho no SVG: " + ", ".join(p["id"] for p in faltam))


if __name__ == "__main__":
    main()
