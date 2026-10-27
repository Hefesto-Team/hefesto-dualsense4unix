import sys, pathlib, re; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
import monta as monta_
from itertools import cycle
from monta import (monta, trava_do_nativo, svg, CSS_GLIFO, CSS_LUZINHAS, MESA,
                   cor_da_zona, player_slot_color, tom_da_casa)
from pacotes import a04_iluminacao as _pacote04


def luz(jogador):
    """A cor automática da barra do controle de número `jogador`, dita pelo produto."""
    return "#%02X%02X%02X" % player_slot_color(jogador)


ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo" '
                       'data-hef-atributo="data-colorway"')

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

CRUS_DA_GUIA = ["#%02X%02X%02X" % rgb for rgb in _pacote04.tons_da_guia()]
TONS = [tom_da_casa(h) for h in CRUS_DA_GUIA]



CSS_DA_LUZ_NO_DESENHO = "  " + _pacote04.tokens_da_luz()

CSS = """  .luz-grade{
    display:grid;
    grid-template-columns:calc(var(--larg-rot) + var(--gap-col)) repeat(4,minmax(0,1fr));
    column-gap:0;margin-right:-14px;
    --r-des:92px;--r-nome:30px;--r-cor:66px;--r-brilho:26px;
    --r-player:52px;--r-leds:64px;--r-acoes:48px;
    --r-ar:6px;--r-passo:calc(var(--r-ar) * 2);
  }
  @media (max-height:780px){.luz-grade{--r-des:54px;--r-player:40px;--r-cor:60px;--r-ar:5px}}
  .luz-grade > .rotulos{padding-right:var(--gap-col)}
  .luz-grade > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:var(--r-des) var(--r-nome) var(--r-cor) var(--r-brilho)
                       var(--r-player) var(--r-leds) var(--r-acoes);
  }
  .luz-grade .ctrl{border-left:1px solid var(--linha);padding:0 14px 0 13px}

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
  .luz-grade .ctrl[data-conectado="nao"] .guia,
  .luz-grade .ctrl[data-conectado="nao"] .trilho,
  .luz-grade .ctrl[data-conectado="nao"] .g4-efeito{display:none}
  .luz-grade .ctrl[data-conectado="sim"] .cel-cor .nada,
  .luz-grade .ctrl[data-conectado="sim"] .cel-acoes .nada{display:none}
  .luz-grade .ctrl[data-conectado="nao"] .cel-brilho .num{font-family:inherit;color:var(--linha);
                                                          font-size:inherit;flex:1;text-align:center;
                                                          display:flex;align-items:center;
                                                          justify-content:center}

  .luz-grade > div > *{position:relative}
  .luz-grade > div > *::before{content:'';position:absolute;
    top:calc(var(--r-ar) * -1);height:0;
    left:-13px;right:-14px;border-top:1px solid var(--rot-linha)}
  .luz-grade > div:not(:last-child) > *::before{right:-14px}
  .luz-grade > div:last-child > *::before{right:0}
  .luz-grade > .rotulos > *::before{left:0;right:calc(var(--gap-col) * -1)}
  .luz-grade > div > *:first-child::before{display:none}
  .luz-grade > div > *:nth-child(3)::before{display:none}
  .luz-grade > .rotulos > *:nth-child(3)::before{display:block}

  .luz-grade .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
  .luz-grade .rotulos > *{align-items:flex-start;text-align:left}
  .luz-grade .rotulos .sec-rot{justify-content:flex-start}
  .luz-grade .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  .luz-grade .rotulos .cel-des{gap:8px}
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           display:flex;align-items:center;gap:6px}
  .luz-grade .rotulos .legenda{font-size:10.5px;line-height:1.45;color:var(--fg);
                               text-transform:none;letter-spacing:0}
  .luz-grade .rotulos .dica{text-transform:none;letter-spacing:0;top:auto;bottom:-4px}

  .luz-grade .moldura{color:var(--linha);border:1px solid currentColor;
                      border-radius:8px;background:var(--app-bg);overflow:hidden}
  .luz-grade .moldura .ds-svg{color:var(--fg)}
  .luz-grade .moldura{height:100%;box-sizing:border-box;display:flex;align-items:center;
                      justify-content:center}
  .luz-grade .moldura .ds-svg{height:100%;width:auto;max-width:100%}
  .ctrl-rot{height:30px;box-sizing:border-box;display:block;text-align:center;
            padding:0 4px;border:1px solid var(--linha);border-radius:7px;
            font:600 12.5px/28px 'Space Grotesk',system-ui,sans-serif;
            color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;align-self:center;
            width:100%;min-width:0}
  .ctrl-rot .pt{margin:0 6px}

  .luzes,.troca{--luz-apagada:#3f4350}
""" + CSS_DA_LUZ_NO_DESENHO + """
  .luz-grade [id$="-lightbar"] .peca{fill:var(--luz,var(--luz-apagada))}
  .luz-grade [id$="-lightbar"]{filter:drop-shadow(0 0 1.1px var(--luz))}

  .luz-grade [id*="-led-jogador-"]{
    fill:var(--led-apagado);
    transform-box:fill-box;transform-origin:center;transform:scale(1.15,2.9);
  }
  .luz-grade .led-on{fill:var(--led-aceso);
                     filter:drop-shadow(0 0 .5px var(--led-aceso)) !important}

  .guia{display:flex;flex-wrap:nowrap;justify-content:space-between;align-items:center}
  .guia .tons{display:contents}
  .guia .tom{flex:0 0 24px;width:24px;height:24px;border-radius:6px;border:1px solid transparent;
             cursor:pointer;padding:0;display:block;min-width:0;position:relative}
  .guia .tom.com-dono::before{
    content:"";position:absolute;left:-1px;right:-1px;
    top:calc(100% + 3px);height:6px;border-radius:2px;background:var(--dono);
  }
  .guia .tom.tomado,.guia .tom[aria-disabled="true"]{cursor:not-allowed}
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
  .cel-cor{display:flex;flex-direction:column;gap:8px;justify-content:center}

  .cel-brilho{display:flex;align-items:center;gap:9px}
  .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .num{flex:0 0 38px;text-align:right;font-family:'JetBrains Mono',monospace;
       font-size:12px;color:var(--fg)}
  .puxador{position:absolute;left:-7px;top:50%;transform:translateY(-50%);
    width:calc(100% + 12px);height:12px;margin:0;padding:0;
    -webkit-appearance:none;appearance:none;background:transparent;cursor:pointer}
  .puxador::-webkit-slider-runnable-track{height:12px;background:transparent;border:0}
  .puxador::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:12px;height:12px;border-radius:50%;background:var(--purple);
    border:2px solid var(--panel);box-sizing:border-box;cursor:pointer}
  .puxador:focus-visible{outline:2px solid var(--purple);outline-offset:4px}

  .players{display:flex;gap:5px;align-items:center;height:100%}
  .players button,.brilhos button{
    flex:1;border-radius:7px;gap:6px;min-width:0;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    cursor:pointer;font-size:13px;font-weight:600;font-family:'JetBrains Mono',monospace;
  }
  .players button.on,.brilhos button.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg)}
  .players button:hover:not(.on):not(.fora),
  .brilhos button:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}
  .players button.fora{border-color:var(--border-forte);border-style:dashed;color:var(--fg);
                       font-weight:400;cursor:default}
  .players .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                 background:none;border:2px solid var(--plastico)}
  .players .dono.incerta{border:2px dashed var(--comment)}

  .cel-leds{display:flex;flex-direction:column;align-items:stretch;
            justify-content:center;min-width:0;gap:6px}
  .brilhos{display:flex;gap:5px;align-items:stretch;flex:0 0 24px;min-width:0}
  .brilhos button{height:24px;font-size:12px}
  .luz-grade .ctrl[data-conectado="nao"] .brilhos button{display:none}
  .luz-grade .ctrl[data-conectado="nao"] .cel-leds{align-items:stretch}
  .aceso{border-radius:8px;background:var(--app-bg);
         display:flex;align-items:center;justify-content:center;gap:16px;
         flex:0 0 34px}
  .tira-luz{flex:0 0 6px;width:6px;height:20px;border-radius:3px}
  .tira-luz.esq{box-shadow:-3px 0 12px 1px currentColor}
  .tira-luz.dir{box-shadow:3px 0 12px 1px currentColor}
  .tira-luz.incerta{border:1px dashed var(--comment)}

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
""" + CSS_LUZINHAS.lstrip("\n") + """  .cel-acoes{display:flex;flex-direction:column;align-items:stretch;gap:2px;justify-content:center;
             margin-top:0;min-width:0}
  .g4-efeito{flex:0 0 32px;width:100%;min-width:0;height:32px;padding:0 9px;border-radius:7px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif;cursor:pointer}
  .g4-efeito:hover{border-color:var(--comment)}
  .g4-efeito-dica{display:contents}
  .quadro-topo .modo-auto{margin-left:auto}

  .troca{margin:8px 0 12px;font-size:11.5px}
  .troca-linha{display:flex;align-items:center;gap:10px;margin:5px 0;flex-wrap:wrap}
  .troca-rot{flex:0 0 52px;font-size:10.5px;
             color:var(--fg)}
  .troca-item{display:flex;align-items:center;gap:7px;padding:4px 9px;border-radius:7px;
              border:1px solid var(--linha);background:var(--app-bg)}
  .troca-item.mexeu{border-color:var(--purple);background:var(--sel-bg)}
  .troca-item .dono{width:9px;height:9px;border-radius:50%;display:block;flex:0 0 9px;
                    background:none;border:2px solid var(--plastico)}
  .troca-item .dono.incerta{border:2px dashed var(--comment)}
  .troca-item .np{font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--fg)}
  .troca-gesto{margin:6px 0 6px 62px;color:var(--fg)}
""" + CSS_GLIFO + """  .sec-rot .gl{opacity:.9;flex:0 0 auto}
"""


DONOS_NA_MESA = {n: d for n, d in DONO.items() if d.get("conectado", True)}


VAZIO = "—"

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
       nenhum* (a régua §4 abaixo, e a razão medida está no bloco `.ctrl[data-conectado="nao"]`
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
    eles escondidos por CSS, que é o que o bloco `.ctrl[data-conectado="nao"]` já faz para a
    coluna que ESVAZIA.

    E O `luz-incerta` NÃO É CAMPO DO CARTÃO: ele nasce nas duas `.tira-luz`,
    dentro do `.aceso`, que é um bloco de alvo `html` — o pacote troca aquele
    miolo inteiro a cada tique, e o que mora lá dentro é contrato DELE, não
    deste gerador. Cravar uma tira escondida no lugar vazio só para o conjunto
    fechar seria régua medindo a própria saída. A auto-checagem §14 desconta os
    blocos de alvo `html` dos dois lados, e é por isso.
    """
    p, j = c["pref"], c["jogador"]
    ligado = c.get("conectado", True)
    cor = luz(j)
    tinta = tom_da_casa(cor)
    b = BRILHO[c["pref"]]
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
    dica_do_nome = f' data-dica="{re.sub(r"<[^>]+>", "", rotulo)}"' if ligado else ""
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

    conectado = "sim" if ligado else "nao"  # (noqa-acento)
    classe = "ctrl" if ligado else "ctrl off"
    return f'''        <div class="{classe}" data-controle="{c.get("uniq") or p}" data-conectado="{conectado}"{titulo_do_lugar}>
          <div class="moldura" data-campo="plastico" data-hef-alvo="cor"{plastico_de_partida}{dica_da_moldura}>
            {desenho(f"il-{p}", c["cor"], ligado, **resto_do_desenho)}
          </div>
          <div class="ctrl-rot" data-campo="{_pacote04.CAMPO_DA_DICA_DA_IDENTIDADE}" data-hef-alvo="atributo" data-hef-atributo="data-dica"{dica_do_nome}><span data-campo="identidade">{rotulo}</span></div>
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
            <div class="brilhos" data-campo="{_pacote04.ENDERECO_DO_BRILHO_DAS_LUZES}" data-hef-alvo="html">
{brilhos}
            </div>
          </div>
          <div class="cel-acoes">
            {opcoes}
            <span class="nada">{VAZIO}</span>
          </div>
        </div>'''

GESTO_DO_MODO = "modo-da-luz"

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


        <style id="plastico-vivo"></style>

      </div>
    </div>'''

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
        (vazias if 'data-conectado="nao"' in atributos else cheias).append(
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
    exigir(corpo.count('class="ctrl" data-controle=') == len(MESA) - len(vazios)
           and corpo.count('class="ctrl off" data-controle=') == len(vazios),
           "a classe do lugar vazio não é a que o piloto escreve (`ctrl off`)")
    exigir(not re.search(r"\.ctrl\.(?:off|vazia)\b", doc),
           "a folha voltou a ler uma segunda marca do lugar vazio")
    exigir(corpo.count('data-conectado="nao"') == len(vazios),
           f"as colunas vazias não são {len(vazios)}")

    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")

    grade = (corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
             .split('<div class="quadro criar"', 1)[0])
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

    exigir('class="hex' not in colunas and 'data-gesto="reenviar"' not in colunas,
           "o hexadecimal voltou à tela: ele é a dica da célula Cor (16/10)")
    exigir(len(re.findall(r'<div class="cel-cor" data-campo="hex" data-hef-alvo="atributo" '
                          r'data-hef-atributo="data-dica"', colunas)) == len(MESA),
           "a célula Cor não leva o hexadecimal na dica em todas as colunas")

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
    grupos = [rotulo for rotulo, _ in _pacote04.GRUPOS_DA_LISTA]
    exigir(len(re.findall(
        '<optgroup label="(?:' + "|".join(map(re.escape, grupos)) + ')"', corpo))
           == len(grupos) * len(MESA),
           f"a lista Efeito perdeu os grupos do desenho A ({', '.join(grupos)})")
    exigir(corpo.count(f'class="g4-efeito-dica" data-campo="{_pacote04.CAMPO_DA_DICA_DO_EFEITO}" '
                       'data-hef-alvo="atributo" data-hef-atributo="data-dica"') == len(MESA)
           and "g4-dica-do-efeito" not in doc,
           "a frase do efeito voltou para a tela: ela é a dica da lista (16/10), uma por lugar")
    exigir("sem-piscar" not in doc and "Sem piscar" not in doc,
           "o «Sem piscar» voltou à aba: ele saiu em 16/10, a «Luz fixa» já é a luz parada")
    exigir('class="quadro criar"' not in corpo and "Criar efeitos novos" not in corpo
           and f'data-gesto="{_pacote04.GESTO_DE_CRIAR_EFEITO}"' not in corpo,
           "o «Criar efeitos novos» voltou à Iluminação: ele não criava nada que se usasse")
    exigir(".luz-grade > .rotulos > *:nth-child(3)::before{display:block}" in doc,
           "a linha entre «Modelo» e «Cor» saiu da coluna dos rótulos")

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

    fora = ("#0080FF", "#FF00FF", "#000000", "#80FF00", "#00FF80", "#00FFFF")
    exigir((*_pacote04.FORA_DA_GUIA, "#00FFFF") == fora,
           f"a poda da guia mudou sem esta régua saber: o pacote tira "
           f"{tuple(_pacote04.FORA_DA_GUIA)} e o desenho dela de 14/10/2026 tira {fora} — a guia "
           f"é UMA fileira com as oito cores de jogador")
    exigir(len(CRUS_DA_GUIA) == 8, f"a guia tem {len(CRUS_DA_GUIA)} cores, e o desenho tem oito")
    exigir(CRUS_DA_GUIA[0] == "#FFFFFF", f"a primeira casa é {CRUS_DA_GUIA[0]}, e o desenho pede o branco")
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
