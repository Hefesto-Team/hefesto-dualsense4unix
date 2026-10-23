#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O MAPA DO CONTROLE — a fonte da verdade das peças, funcional."""
import csv, math, pathlib, re, sys

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from onde import RAIZ as R

DADOS_DO_REPO = R / "docs/data"
CSV = DADOS_DO_REPO / "pecas-do-dualsense.csv"
CSV_CORES = DADOS_DO_REPO / "cores-do-dualsense.csv"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(R / "src"))
import onde  # noqa: E402
import caixa_da_janela  # noqa: E402
GLIFOS = R / "assets/glyphs"
SVG = R / "src/hefesto_dualsense4unix/interface/ds_limpo.svg"
SAIDA = onde.pagina("mapa-do-controle.html")

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
    x = re.sub(r'(stroke|fill)="#[0-9a-fA-F]{3,8}"', r'\1="currentColor"', x)
    x = re.sub(r'\s+width="32"\s+height="32"', "", x)
    return x.replace("<svg ", f'<svg width="{tam}" height="{tam}" ', 1).strip()


#: O que a silhueta deixa de fora: o que não se desenha (as features), as letras e as luzes.
_FORA_DA_SILHUETA = ("grupo-invisiveis", "grupo-glifos", "grupo-luzes", "glifo-stick_r")


def _sem_o_grupo(x, gid):
    """O desenho sem o `<g id=gid>` inteiro, com os `<g>` de dentro contados."""
    ini = x.find(f'<g id="{gid}"')
    if ini < 0:
        raise SystemExit(f"ERRO: o grupo {gid!r} sumiu do ds_limpo.svg")
    fundo = 0
    for m in re.finditer(r"<g\b|</g>", x[ini:]):
        fundo += 1 if m.group(0) == "<g" else -1
        if fundo == 0:
            return x[:ini] + x[ini + m.end():]
    raise SystemExit(f"ERRO: o grupo {gid!r} do ds_limpo.svg não fecha")


def silhueta_do_dualsense(tam=40, traco=0.9):
    """O DualSense do mapa (o MESMO `ds_limpo.svg`) como ícone de uma cor só, `currentColor`.

    Sem `id` nenhum, para não colidir com outro desenho na página, e sem as cores, as features,
    as letras e as luzes. O `traco` engrossa o contorno, que no tamanho de ícone some.
    """
    x = re.sub(r"<\?xml[^>]*\?>\s*", "", SVG.read_text())
    x = re.sub(r"<!--.*?-->", "", x, flags=re.S)
    x = re.sub(r"<defs\b.*?</defs>", "", x, flags=re.S)
    for gid in _FORA_DA_SILHUETA:
        x = _sem_o_grupo(x, gid)
    x = re.sub(r"<title>[^<]*</title>|<text\b.*?</text>", "", x, flags=re.S)
    x = re.sub(r'\s(?:id|class|filter|style|data-[a-z-]+|xmlns:bx|bx:[a-z]+)="[^"]*"', "", x)
    x = re.sub(r'(fill|stroke)="(?:#[0-9a-fA-F]{3,8}|rgb[^"]*|url\([^"]*\))"',
               r'\1="currentColor"', x)
    x = re.sub(r'\swidth="[^"]*"\s+height="[^"]*"', "", x, count=1)
    x = x.replace("<svg ", f'<svg width="{tam}" height="{tam}" aria-hidden="true" '
                  f'stroke="currentColor" stroke-width="{traco}" stroke-linejoin="round" ', 1)
    return re.sub(r">\s+<", "><", x).strip()


CAIXAS_PROPRIAS = {
    "lightbar": [(38.9, 30.0, 45.1, 52.0), (82.9, 30.0, 89.3, 52.0)],
}


EXTERNO = {}
_ext = pathlib.Path(__file__).with_name("subpath-externo.json")
if _ext.exists():
    EXTERNO = __import__("json").loads(_ext.read_text())


def subpath_externo(d, pid=None, k=0):
    """De um path de vários subpaths, o que CONTÉM os outros."""
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
    """O desenho da peça, com cada path reduzido ao seu contorno EXTERNO."""
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
    cadeia = []
    k = ini
    while True:
        p = svg_txt.rfind("<g ", 0, k)
        if p < 0:
            break
        if bloco_fim(svg_txt, p) > j:
            t = re.search(r'\stransform="([^"]*)"', svg_txt[p:svg_txt.index(">", p)])
            if t:
                cadeia.insert(0, t.group(1))
        k = p
    tg_self = re.search(r'<g\b[^>]*\stransform="([^"]*)"', bloco)
    if tg_self:
        cadeia.append(tg_self.group(1))
    tg = type("M", (), {"group": lambda s, i: " ".join(cadeia)})() if cadeia else None
    fora, k = [], -1
    for mm in re.finditer(r"<(rect|path|circle|ellipse|polygon)\b[^>]*?/?>", bloco):
        t = mm.group(0)
        if not t.endswith("/>"):
            t = t[:-1] + "/>"
        if mm.group(1) == "path":
            k += 1
        d_ = re.search(r'\sd="([^"]*)"', t)
        if d_:
            t = t.replace(d_.group(0), f' d="{subpath_externo(d_.group(1), pid, k)}"')
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


POS_GLIFO = {}
_pos = pathlib.Path(__file__).with_name("posicao-dos-glifos.json")
if _pos.exists():
    POS_GLIFO = __import__("json").loads(_pos.read_text())

TINTA = {}
_tinta = pathlib.Path(__file__).with_name("centro-da-tinta.json")
if _tinta.exists():
    TINTA = {k: tuple(v) for k, v in __import__("json").loads(_tinta.read_text()).items()}

SEM_ALVO = {"feat-giroscopio", "feat-acelerometro", "feat-bateria"}

# O CHASSI NÃO É BOTÃO (decisão de produto, 03/10/2026): sem
# alvo no desenho e sem linha na lista. A linha dele fica no CSV das peças, que
# é o dono delas; o que sai é só o que se podia apontar e clicar.
SEM_BOTAO = {"corpo"}

# A HÁPTICA TEM LUGAR NO DESENHO (decisão de produto), e o lugar é
# o do glifo dela: a área do touchpad, com ondas na borda de cima. O grupo nasce
# aqui, e não no `ds_limpo.svg`, porque o arquivo do desenho é o original e este
# gerador já o enriquece com os alvos e as marcas de troca.
HAPTICA = "feat-haptica"


def ondas_da_haptica():
    """O grupo `feat-haptica`: duas faixas onduladas logo acima do touchpad."""
    def faixa(base, x0=48.0, x1=80.0, onda=0.45, espessura=0.42, passos=32):
        xs = [x0 + (x1 - x0) * i / passos for i in range(passos + 1)]
        de_cima = [(x, base + onda * math.sin(2 * math.pi * (x - x0) / 16)) for x in xs]
        de_baixo = [(x, y + espessura) for x, y in reversed(de_cima)]
        pts = de_cima + de_baixo
        return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"
    return (f'  <g id="mp-{HAPTICA}" class="oculta" data-feature="haptica">'
            f'<path class="peca" d="{faixa(25.7)}"/>'
            f'<path class="peca" d="{faixa(24.2)}"/></g>')

SO_O_GLIFO_ACENDE = {"ps"}

AO_LADO = {"mic": (0, 3.4)}
MESMA_LINHA = {"share": 31.4, "options": 31.4}
DESLOCA_X = {"share": -1.4, "options": 1.4}

TAMANHO = {"ps": 8.6, "stick_l": 14.0, "stick_r": 14.0,
           "share": 3.4, "options": 3.4, "mic": 3.0,
           "triangle": 4.2, "circle": 4.2, "square": 4.2, "cross": 4.2,
           "dpad_up": 4.4, "dpad_down": 4.4, "dpad_left": 4.4, "dpad_right": 4.4}
SEM_GLIFO_NO_DESENHO = set()


SOBE_A_LETRA = {"l1": "-0.2em", "r1": "-0.2em", "l2": "-0.2em", "r2": "-0.2em"}


def sobe_a_letra(svg_txt):
    """Acrescenta o `dy` ao `<text>` dos glifos que pedem, e a nenhum outro."""
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
    """O desenho — que É o arquivo dela — com os alvos do ponteiro por cima."""
    x = sobe_a_letra(SVG.read_text())
    # O grupo do chassi chega vazio do desenho (o `corpo` é SEM_BOTAO); sobraria
    # só o título dele no mapa, que é o que o leitor de tela anuncia.
    x = re.sub(r'\s*<g id="grupo-chassi">\s*<title>[^<]*</title>\s*</g>', "", x)
    for i in sorted(set(re.findall(r'id="([^"]+)"', x)), key=len, reverse=True):
        x = (x.replace(f'id="{i}"', f'id="mp-{i}"')
              .replace(f"url(#{i})", f"url(#mp-{i})").replace(f"#{i} ", f"#mp-{i} ")
              .replace(f"url(&quot;#{i}&quot;)", f"url(&quot;#mp-{i}&quot;)")
              .replace(f'url("#{i}")', f'url("#mp-{i}")')
              .replace(f"url('#{i}')", f"url('#mp-{i}')"))
    x = x.replace("<svg ", '<svg class="ds" ', 1)
    x = x.replace('id="mp-lightbar"',
                  'id="mp-lightbar" data-campo="luz-cor" data-hef-alvo="cor"', 1)
    if "data-colorway=" not in x[: x.index(">")]:
        x = x.replace("<svg ", '<svg data-colorway="cosmic-red" ', 1)

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

    x = x.replace("</svg>", ondas_da_haptica() + "\n</svg>", 1)
    alvos = []
    for p in pecas:
        pid = p["id"]
        if pid in SEM_ALVO or pid in SEM_BOTAO or p["x1"] == "-":
            continue
        corpo = forma_cheia(x, pid)
        if not corpo:
            continue
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        alvos.append(((x2 - x1) * (y2 - y1), (x1, y1, x2, y2),
                      f'  <g class="alvo a-{pid}">{corpo}</g>'))

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
    """Os 28 modelos do `cores-do-dualsense.csv`, agrupados por modelo."""
    linhas = [x for x in CSV_CORES.read_text().splitlines()
              if x and not x.startswith("#")]
    fora = {}
    for c in csv.DictReader(linhas):
        fora.setdefault(c["id"], []).append(c)
    return fora


CSS_BASE = """
  :root{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --fundo-da-pagina:#11121a;  /* o fundo em volta da caixa, o do `topo.html` */
    --border-sutil:#343746; --border-forte:#44475a;
    --branco:#ffffff; --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#8b8fa8; --comment:#6272a4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555; --yellow:#f1fa8c;
    --luz-apagada:#3f4350; --led-apagado:#4a4f5c; --led-aceso:#e8ecf5;
    --sem-plastico:#3a3f4b;
    --f:ui-sans-serif,system-ui,"Cantarell","Segoe UI",Roboto,sans-serif;
    --m:ui-monospace,"JetBrains Mono","Fira Mono","DejaVu Sans Mono",monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--fundo-da-pagina);color:var(--fg);font-family:var(--f);
       display:flex;flex-direction:column;align-items:center;gap:16px}
  .cx{background:var(--app-bg);border-radius:11px;border:1px solid var(--border-sutil);
      overflow:hidden;display:flex;flex-direction:column}
  .ds{width:100%;height:auto}
  .ds .peca,.ds .corpo{stroke:none}
  .ds g[id^="mp-"]:not([id^="mp-glifo"]):not(.sobre):not(.alvo)
    > :is(rect,path,circle,ellipse,polygon){fill:var(--z-casca-solida, var(--sem-plastico))}
  .ds #mp-lightbar{color:var(--luz-apagada)}
  .ds #mp-lightbar *{fill:var(--luz, currentColor)}
  .ds #mp-led-jogador rect{fill:var(--led-apagado)}
  .ds #mp-led-jogador rect.led-on{fill:var(--led-aceso)}
  .ds .sem-tinta{fill:none !important;stroke:none !important}
  .ds #mp-corpo .peca,.ds #mp-corpo .corpo{stroke:var(--z-casca-solida, var(--sem-plastico));stroke-width:.42;
                      stroke-linejoin:round;stroke-linecap:round}
  .ds .oculta{opacity:0 !important}
  .sobre{color:var(--branco);opacity:1;pointer-events:none;--pena:.35}
  .sobre *:not([fill="none"]):not(title){fill:currentColor !important}
  .sobre [stroke]:not([stroke="none"]){stroke:currentColor !important}
  .sobre text,.sobre tspan{fill:currentColor !important}
  .sobre svg{overflow:visible}
  .sobre [stroke-width]{stroke-width:calc(var(--pena) * 32 / var(--lado))}
  .alvo,.alvo *{fill:transparent;stroke:transparent;stroke-width:1.8;
                stroke-linejoin:round;stroke-linecap:round;pointer-events:all;cursor:pointer}
"""

CSS_TELA = """
  .mc{--tipo:var(--purple)}
  .mc[data-tipo="pac"]{--tipo:var(--cyan)}
  .mc[data-tipo="troca"]{--tipo:var(--orange)}
  .mc-topo{display:flex;align-items:center;gap:16px;padding:12px 20px;border-bottom:1px solid var(--border-sutil);flex:none}
  .mc-topo h1{font-size:17px;font-weight:700;color:var(--pink)}
  .voltar2{display:inline-flex;align-items:center;height:30px;padding:0 12px;border-radius:7px;text-decoration:none;
    border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-suave);font-size:12px}
  .voltar2:hover{border-color:var(--purple);color:var(--fg)}
  .mc-topo > .mc-rot{margin-left:auto}
  /* O nome do controle corta com reticências, com o nome inteiro na dica (`base-comum.js`), quando a barra dos
     chips não cabe. */
  .mc-chips{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px}
  .chip{height:30px;padding:0 12px;border-radius:7px;border:2px solid var(--plastico,var(--border-forte));
    background:var(--app-bg);color:var(--texto-suave);font:12px var(--f);cursor:pointer;white-space:nowrap;text-align:center;
    overflow:hidden;text-overflow:ellipsis}
  .chip.on{background:rgba(189,147,249,.16);color:var(--fg);font-weight:600}
  .chip .pt{color:var(--fg);margin:0 2px}
  /* Abaixo de 1000 px o título fica em duas linhas, de largura fixa, e os chips tomam o resto da barra: cada
     coluna segue o texto do seu chip (`auto`) e cresce com a folga. Sem a folga, o texto cabia no chip por
     centésimos de pixel, e a reticência cortava o nome de exemplo à toa; com ela, só o nome comprido corta. */
  @media (max-width:1000px){.mc-chips{flex:1 1 auto;gap:5px;grid-auto-columns:auto}.chip{padding:0 7px}
    .mc-topo h1{flex:none;width:6em}}
  .mc-perfil{display:grid;grid-template-columns:292px minmax(0,1fr) 292px;gap:20px;align-items:center;
    padding:12px 20px;border-bottom:1px solid var(--border-sutil);flex:none}
  .mc-perfil .cel{display:flex;align-items:center;gap:12px;min-width:0}
  .mc-rot{font-size:12px;color:var(--texto-suave);white-space:nowrap}
  .mc-rot[data-dica]{cursor:help}
  .campo2{height:32px;border-radius:7px;border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg);
    font:12.5px var(--f);padding:0 10px}
  #perfil,.nome2{width:auto;flex:1 1 0;min-width:0}
  .mc-perfil[data-fixo="sim"] .nome2{color:var(--fg)}
  .etiqueta{height:24px;display:inline-flex;align-items:center;padding:0 10px;border-radius:12px;font-size:11.5px;
    font-weight:600;color:var(--app-bg);background:var(--tipo)}
  .usar-em{display:flex;gap:6px;align-items:center;margin-left:auto}
  .usar-em .jogo{height:26px;display:inline-flex;align-items:center;padding:0 10px;border-radius:13px;font-size:11.5px;
    border:1px solid var(--tipo);color:var(--fg);background:transparent;font-family:var(--f)}
  .usar-em .mais{border-style:dashed;color:var(--fg);border-color:var(--border-forte);cursor:pointer}
  .cx > .corpo{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column}
  .mapa.mc-mapa{flex:1 0 auto;display:grid;grid-template-columns:292px minmax(0,1fr) 292px;gap:20px;
    padding:14px 20px;align-items:stretch;align-content:center}
  /* Abaixo de 1000 px as duas colunas laterais (292) deixariam ao centro 162 px na vista de 860: o Toque, o Meio
     e o PS cruzavam a coluna da direita. A 252 px a ação mais longa do exemplo («Movimento do cursor») ainda cabe
     na linha do lado, e o centro fica com 260 px, com as linhas dele uma embaixo da outra (regra mais abaixo). */
  @media (max-width:1000px){.mc-perfil,.mapa.mc-mapa{grid-template-columns:252px minmax(0,1fr) 252px;gap:12px}}
  .mc-lado{display:flex;flex-direction:column;gap:7px;justify-content:space-between}
  .b2{display:grid;grid-template-columns:24px 74px minmax(0,1fr);align-items:center;gap:8px;height:37px;padding:0 10px;
    border-radius:8px;border:1px solid var(--border-sutil);background:var(--panel);color:var(--fg);font:12px var(--f);
    cursor:pointer;text-align:left}
  .b2:hover{border-color:var(--comment)}
  .b2-gl{display:flex;align-items:center;justify-content:center;color:var(--texto-suave)}
  .b2-gl svg{width:18px;height:18px}
  .b2-nm{font-size:11.5px;color:var(--texto-suave);white-space:nowrap}
  .b2-val{height:25px;line-height:25px;padding:0 9px;border-radius:6px;background:var(--app-bg);
    color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11.5px}
  .b2[data-estado~="muda"]{border-left:1px solid var(--tipo);box-shadow:inset 2px 0 0 var(--tipo)}
  .b2[data-estado~="muda"] .b2-val{color:var(--fg);box-shadow:inset 0 0 0 1px var(--tipo)}
  .b2[data-estado~="pisca"]{border-color:var(--pink)}
  .b2[data-estado~="on"]{border-color:var(--pink);background:rgba(255,121,198,.10)}
  .b2[data-estado~="on"] .b2-gl,.b2[data-estado~="pisca"] .b2-gl{color:var(--pink)}
  .mc-centro{position:relative;display:flex;flex-direction:column;gap:12px;min-width:0;justify-content:flex-start}
  .mc-desenho{display:flex;justify-content:center;min-height:0}
  .mc-desenho .ds{width:100%;height:auto;max-height:380px}
  .mc-baixo{display:grid;grid-template-columns:1fr 1fr;gap:7px 12px}
  .mc-baixo .b2{grid-template-columns:24px 58px minmax(0,1fr);gap:8px}
  .mc-baixo .b2:last-child{grid-column:1 / -1;justify-self:center;width:calc(50% - 6px)}
  /* Abaixo de 1000 px a linha aperta o nome (60 px cabem «R3 direção») e o centro empilha as cinco linhas: em
     duas colunas de 124 px a ação não cabia. */
  @media (max-width:1000px){.b2,.mc-baixo .b2{grid-template-columns:24px 60px minmax(0,1fr);gap:6px;padding:0 8px}
    .mc-baixo{grid-template-columns:minmax(0,1fr)}
    .mc-baixo .b2:last-child{grid-column:auto;justify-self:stretch;width:auto}}
  .sel2{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);z-index:5;background:var(--panel);
    border:1px solid var(--pink);border-radius:11px;box-shadow:0 18px 50px rgba(0,0,0,.55);
    display:flex;flex-direction:column;padding:14px 16px;gap:12px}
  .sel2[hidden]{display:none}
  .sel2-topo{display:flex;align-items:center;gap:14px}
  .sel2-tit{font-size:13.5px;font-weight:600;color:var(--fg)}
  .sel2-b{color:var(--pink)}
  .seg2{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:6px;margin-left:auto}
  .seg2 button{height:30px;padding:0 14px;border-radius:7px;border:1px solid var(--border-forte);background:var(--app-bg);
    color:var(--texto-suave);font:12px var(--f);cursor:pointer}
  .seg2 button[hidden]{display:none}
  .seg2 button.on{border-color:var(--purple);background:rgba(189,147,249,.16);color:var(--fg);font-weight:600}
  .sel2-x{width:30px;height:30px;border-radius:7px;border:1px solid var(--border-forte);background:transparent;
    color:var(--fg);font-size:15px;cursor:pointer}
  .sel2-grade{flex:none;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:42px;gap:9px;align-content:start}
  .sel2-grade[hidden]{display:none}
  .op3{display:flex;align-items:center;gap:9px;padding:0 12px;border-radius:8px;border:1px solid var(--border-sutil);
    background:var(--app-bg);color:var(--fg);font:12px var(--f);cursor:pointer;text-align:left;min-width:0}
  .op3:hover{border-color:var(--purple)}
  .op3 svg{width:18px;height:18px;flex:none;color:var(--texto-suave)}
  .op3.on{border-color:var(--tipo);box-shadow:inset 0 0 0 1px var(--tipo);background:rgba(255,184,108,.08)}
  .op3.gravar{grid-column:1 / -1;justify-content:center;border-color:var(--red);color:var(--red);font-weight:600}
  .op3.gravar .ponto{width:9px;height:9px;border-radius:50%;background:var(--red)}
  .op3.gravar.ouvindo{background:rgba(255,85,85,.12)}
  .op3.gravar[data-gravando="sim"]{background:rgba(255,85,85,.12)}
  .seq-grade{grid-template-columns:repeat(2,1fr)}
  .seq-passos{grid-column:1 / -1;display:flex;flex-wrap:wrap;align-items:center;gap:6px;min-height:42px;padding:6px 10px;border-radius:8px;
    border:1px dashed var(--border-forte);background:var(--app-bg)}
  .seq-p{padding:4px 10px;border-radius:6px;border:1px solid var(--purple);color:var(--fg);font-size:12px}
  .seq-t{font-size:11px;color:var(--texto-mudo);font-family:'JetBrains Mono',monospace}
  .seq-campo{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--texto-suave)}
  .seq-campo select{flex:1;min-width:0;height:34px;border-radius:7px;border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg);font:12px var(--f)}
  .seq-tocar{grid-column:1 / -1;justify-content:center}
  .sel2-rod{display:flex;justify-content:flex-end}
  .sel2-rod .op3{height:32px}
  .mc-cursor{display:flex;align-items:center;gap:12px;padding:10px 20px;border-top:1px solid var(--border-sutil);flex:none}
  .mc-cursor .campo2{height:30px}
  .mc-cursor .par2{display:flex;align-items:center;gap:12px}
  .mc:not([data-tipo="pac"]) .mc-cursor{display:none}
  .mc-rod{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:12px 20px;border-top:1px solid var(--border-sutil);flex:none}
  .btn2{height:36px;display:flex;align-items:center;justify-content:center;border-radius:7px;border:1px solid var(--border-forte);
    background:transparent;color:var(--texto-suave);font:12.5px var(--f);cursor:pointer;text-decoration:none}
  .btn2.amarelo{border-color:#f1fa8c;color:#f1fa8c}
  .btn2.roxo{border-color:var(--purple);color:var(--purple)}
"""

#: a regra da peça acesa: a cor do tipo quando o botão muda, rosa quando é o escolhido, quando pisca
#: no controle ou quando o ponteiro passa. O atributo `data-estado` é escrito pelo piloto.
_PINTA = ":is(.peca, rect, circle, path, ellipse){fill:var(--%s) !important;stroke:var(--%s) !important}"


def css_das_pecas(pecas):
    regras = []
    for i in pecas:
        alvo = f"#mp-{i} {_PINTA % ('tipo', 'tipo')}"
        rosa = f"#mp-{i} {_PINTA % ('pink', 'pink')}"
        regras.append(f'.mc .mapa:has(.item-{i}[data-estado~="muda"]) {alvo}')
        for gatilho in ('[data-estado~="on"]', '[data-estado~="pisca"]', ":hover"):
            regras.append(f".mc .mapa:has(.item-{i}{gatilho}) {rosa}")
        # o ponteiro na peça acende a linha dela, e o glifo fica claro nos dois sentidos
        regras.append(f".mc .mapa:has(.a-{i}:hover) {rosa}")
        regras.append(f".mc .mapa:has(.a-{i}:hover) .item-{i}"
                      "{border-color:var(--pink);background:rgba(255,121,198,.12);color:var(--fg)}")
        regras.append(f".mc .mapa:has(.item-{i}:hover) .s-{i}, .mc .mapa:has(.a-{i}:hover) .s-{i}"
                      "{color:var(--fg) !important;opacity:1}")
    return "\n".join("  " + r for r in regras)


JS = r"""
(() => {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const mc = $('.mc'), pop = $('.sel2'), ds = $('svg.ds'), nome = $('#nome');
  const captura = $('#mapa-captura'), gravar = $('.op3.gravar:not(.seq-grava)', pop), grava_seq = $('.seq-grava', pop);
  const PADRAO = {"1": [3], "2": [2, 4], "3": [1, 3, 5], "4": [1, 2, 4, 5]};
  const ROTULO = gravar.querySelector('span:last-child').textContent;
  let linha = null, ouvindo = false, soModificador = null;

  const mostra = aba => {
    $$('.seg2 button', pop).forEach(x => x.classList.toggle('on', x.dataset.aba === aba));
    $$('.sel2-grade', pop).forEach(g => g.hidden = g.dataset.aba !== aba);
    escuta(false);
  };
  const abre = b => {
    if (b.dataset.fixo === 'sim') return;
    linha = b;
    $('.sel2-b', pop).textContent = $('.b2-nm', b).textContent;
    const atual = ($('.b2-atual', b) || {}).textContent || '';
    $$('.op3', pop).forEach(o => o.classList.toggle('on', !!atual && o.dataset.v === atual));
    const troca = b.dataset.troca === 'sim';
    $('.seg2 [data-aba="controle"]', pop).hidden = !troca;
    $('.seg2 [data-aba="sequencia"]', pop).hidden = !troca;
    const em = aba => !!$(`.sel2-grade[data-aba="${aba}"] .op3[data-v="${atual}"]`, pop);
    mostra(atual.startsWith('sequencia:') && troca ? 'sequencia' : atual.startsWith('troca:') && troca ? 'controle' : em('mouse') ? 'mouse' : atual && !em('controle') ? 'teclado' : troca ? 'controle' : 'mouse');
    pop.hidden = false;
  };
  /* A linha escolhida só fica acesa enquanto o seletor dela está aberto: fechar manda `mapa-botao` sem
     botão, e o pacote apaga o `on`. O `setTimeout` deixa passar antes o clique da opção que fechou. */
  const solta = () => setTimeout(() => $('#mapa-solta').click(), 0);
  const fecha = () => { escuta(false); pop.hidden = true; solta(); };

  /* a captura: a tecla, o botão do mouse ou o botão do controle que a pessoa aperta */
  const MODIFICADOR = {ControlLeft: 'LEFTCTRL', ControlRight: 'RIGHTCTRL', ShiftLeft: 'LEFTSHIFT', ShiftRight: 'RIGHTSHIFT',
    AltLeft: 'LEFTALT', AltRight: 'RIGHTALT', MetaLeft: 'LEFTMETA', MetaRight: 'RIGHTMETA'};
  const NOMEADA = {ArrowUp: 'UP', ArrowDown: 'DOWN', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', Space: 'SPACE', Enter: 'ENTER',
    NumpadEnter: 'ENTER', Tab: 'TAB', Backspace: 'BACKSPACE', Delete: 'DELETE', Home: 'HOME', End: 'END', PageUp: 'PAGEUP',
    PageDown: 'PAGEDOWN', Insert: 'INSERT', Comma: 'COMMA', Period: 'DOT', PrintScreen: 'SYSRQ'};
  const tecla = e => {
    const c = e.code;
    if (/^Key[A-Z]$/.test(c)) return 'KEY_' + c.slice(3);
    if (/^Digit[0-9]$/.test(c)) return 'KEY_' + c.slice(5);
    if (/^F([1-9]|1[0-2])$/.test(c)) return 'KEY_' + c;
    return NOMEADA[c] ? 'KEY_' + NOMEADA[c] : '';
  };
  const modificadores = e => [e.ctrlKey && 'KEY_LEFTCTRL', e.altKey && 'KEY_LEFTALT', e.shiftKey && 'KEY_LEFTSHIFT',
    e.metaKey && 'KEY_LEFTMETA'].filter(Boolean);
  const escuta = on => {
    ouvindo = on; soModificador = null;
    gravar.classList.toggle('ouvindo', on);
    gravar.querySelector('span:last-child').textContent = on ? 'Aperte uma tecla ou um botão' : ROTULO;
  };
  const manda = (campo, valor) => {
    delete captura.dataset.tecla; delete captura.dataset.troca;
    captura.dataset[campo] = valor;
    escuta(false); pop.hidden = true;
    captura.click();
    solta();
  };
  document.addEventListener('keydown', e => {
    if (!ouvindo) return;
    e.preventDefault(); e.stopPropagation();
    if (e.code === 'Escape' && !modificadores(e).length) { escuta(false); return; }
    if (MODIFICADOR[e.code]) { soModificador = 'KEY_' + MODIFICADOR[e.code]; return; }
    const k = tecla(e);
    if (k) { soModificador = null; manda('tecla', [...modificadores(e), k].join('+')); }
  }, true);
  document.addEventListener('keyup', e => {
    if (!ouvindo || !soModificador || !MODIFICADOR[e.code]) return;
    e.preventDefault(); manda('tecla', soModificador);
  }, true);
  const BOTAO_DO_MOUSE = ['BTN_LEFT', 'BTN_MIDDLE', 'BTN_RIGHT'];
  document.addEventListener('mousedown', e => {
    if (!ouvindo) return;
    if (e.target.closest('.op3.gravar')) return;
    if (e.target.closest('.sel2')) { escuta(false); return; }
    if (BOTAO_DO_MOUSE[e.button]) { e.preventDefault(); e.stopPropagation(); manda('tecla', BOTAO_DO_MOUSE[e.button]); }
  }, true);
  document.addEventListener('contextmenu', e => { if (ouvindo) { e.preventDefault(); e.stopImmediatePropagation(); } }, true);
  /* o botão do controle: a linha que ganha `pisca` enquanto a captura escuta vira a troca */
  const olho = new MutationObserver(lista => {
    if (!ouvindo) return;
    for (const m of lista) {
      const antes = (m.oldValue || '').split(' '), agora = (m.target.dataset.estado || '').split(' ');
      if (agora.includes('pisca') && !antes.includes('pisca') && m.target.dataset.destino)
        { manda('troca', m.target.dataset.destino); return; }
    }
  });
  $$('.b2[data-destino]').forEach(b => olho.observe(b, {attributes: true, attributeFilter: ['data-estado'], attributeOldValue: true}));

  $$('.b2').forEach(b => b.addEventListener('click', () => abre(b)));
  $$('.alvo').forEach(a => a.addEventListener('click', () => {
    const peca = [...a.classList].find(c => c.startsWith('a-'));
    const b = peca && $(`.b2.item-${peca.slice(2)}`);
    if (b) b.click();
  }));
  $('.seg2', pop).addEventListener('click', e => { const t = e.target.closest('button'); if (t) mostra(t.dataset.aba); });
  $('.sel2-x', pop).addEventListener('click', fecha);
  gravar.addEventListener('click', () => escuta(!ouvindo));
  /* a gravação da sequência é do controle: o botão só vira «Parar» até a página repintar */
  const ROTULO_SEQ = grava_seq.querySelector('span:last-child').textContent;
  grava_seq.addEventListener('click', () => {
    const on = grava_seq.dataset.gravando !== 'sim';
    grava_seq.dataset.gravando = on ? 'sim' : '';
    grava_seq.querySelector('span:last-child').textContent = on ? 'Parar de gravar' : ROTULO_SEQ;
  });
  pop.addEventListener('click', e => {
    const o = e.target.closest('.op3');
    if (o && o !== gravar && !o.closest('.seq-grade')) fecha();
  });

  /* o controle escolhido pinta o casco, os cinco pontos do jogador e a barra de luz do desenho */
  const acende = c => {
    if (!c) return;
    ds.dataset.colorway = c.dataset.colorway || '';
    for (let i = 1; i <= 5; i++) {
      const led = document.getElementById('mp-led-jogador-' + i);
      if (led) led.classList.toggle('led-on', (PADRAO[c.dataset.jogador] || []).includes(i));
    }
    if (c.dataset.luz) document.getElementById('mp-lightbar').style.setProperty('--luz', c.dataset.luz);
  };
  const chips = $('.mc-chips');
  new MutationObserver(() => acende($('.chip.on', chips))).observe(chips, {childList: true, subtree: true, attributes: true});
  chips.addEventListener('click', e => {
    const c = e.target.closest('.chip');
    if (c) { $$('.chip', chips).forEach(x => x.classList.toggle('on', x === c)); acende(c); }
  });
  acende($('.chip.on', chips));
  const bloqueia = () => { nome.readOnly = $('.mc-perfil').dataset.fixo === 'sim'; };
  new MutationObserver(bloqueia).observe($('.mc-perfil'), {attributes: true, attributeFilter: ['data-fixo']});
  bloqueia();
  /* A ÂNCORA DO ENDEREÇO escolhe o perfil de abertura (O-MAPA-DO-CONTROLE-ABRE-NO-PERFIL-QUE-A-ANCORA-PEDE-E-LE-A-ESCOLHA-DO-POINT-AND-CLICK-01).
     `#point-and-click` e `#trocar` vêm da aba Navegação; o produto pinta, no `data-chave` de dois marcadores
     que não aparecem, a chave que cada uma pede. Sem âncora, ou com outra, nada muda: abre em Navegar. */
  const MARCADOR = {'#point-and-click': 'ancora-pac', '#trocar': 'ancora-trocar'};
  const lista = $('#perfil');
  /* A âncora se segue UMA vez por chegada (a carga ou o `hashchange`), quando a chave pintada já tem
     lugar no seletor. Depois o seletor é de quem usa: o perfil ativo que troca no meio da edição
     não muda a escolha feita nem larga o que não se salvou. */
  let seguida = null;
  const seguirAncora = () => {
    if (seguida === location.hash) return;
    const campo = MARCADOR[location.hash];
    const marca = campo && $('[data-campo="' + campo + '"]');
    const chave = marca ? marca.dataset.chave : '';
    if (campo && !(chave && [...lista.options].some(o => o.value === chave))) return;
    seguida = location.hash;
    if (!chave || lista.value === chave) return;
    lista.value = chave;
    lista.dispatchEvent(new Event('change', {bubbles: true}));
  };
  /* O TÍTULO DIZ QUAL DAS DUAS TELAS É: a Navegação abre o mesmo mapa por «Trocar os botões» e por
     «Point and click», e o `<h1>`, o `aria-label` e o `<title>` seguem a âncora. */
  const TITULO = {'#trocar': 'Trocar os botões', '#point-and-click': 'Point and click'};
  const titula = () => {
    const t = TITULO[location.hash] || 'Mapa do controle';
    $('#mc-titulo').textContent = t;
    mc.setAttribute('aria-label', t);
    document.title = 'Hefesto — ' + t;
  };
  titula();
  addEventListener('hashchange', titula);
  addEventListener('hashchange', () => { seguida = null; seguirAncora(); });
  new MutationObserver(seguirAncora).observe($('.mc-perfil'), {subtree: true, childList: true, attributes: true});
  seguirAncora();
})();
"""


def _chips_de_exemplo():
    """Os quatro controles do desenho, um por cor do plástico (o produto troca por `blocos`)."""
    exemplo = (("Cosmic Red", "cosmic-red", "USB", 1, "#0000ff", True),
               ("Starlight Blue", "starlight-blue", "BT", 2, "#ff0000", False),
               ("Galactic Purple", "galactic-purple", "BT", 3, "#00ff00", False),
               ("White", "white", "USB", 4, "#ff0080", False))
    import monta
    return "".join(
        f'<button class="chip plastico{" on" if ligado else ""}" '
        f'style="--plastico:{monta.cor_da_zona(slug)}" data-colorway="{slug}" '
        f'data-jogador="{n}" data-luz="{luz}">{nome} <span class="pt">•</span> {via}</button>'
        for nome, slug, via, n, luz, ligado in exemplo)


def _linha_da_tela(x, pecas, valores, escolhida):
    """Uma linha da lista: o glifo, o nome e o valor. O piloto escreve `data-estado` e o valor."""
    from pacotes import a13_mapa_do_controle as a13

    g = glifo(pecas[x.peca]["glifo"], tam=18) if pecas[x.peca]["glifo"] != "-" else ""
    par = valores.get(x.b)
    palavras = (["muda"] if par else []) + (["on"] if x.b == escolhida else [])
    fisico = x.b in a13.PODE_TROCAR
    fixo = ' data-fixo="sim"' if x.fixo else ""
    destino = f' data-destino="{x.motor}"' if fisico else ""
    dica = {"ps": "Os gestos do PS ficam na aba Navegação",
            "tp_toque": "O toque no touchpad move o cursor; não se troca aqui"}.get(x.b)
    dica = f' data-dica="{dica}"' if dica else ""
    return (
        f'<button class="b2 item-{x.peca}" data-b="{x.b}" data-gesto="mapa-botao"'
        f'{fixo}{destino}{dica} data-troca="{"sim" if fisico else "não"}"'
        f' data-campo="estado-{x.b}" data-hef-alvo="atributo" data-hef-atributo="data-estado"'
        f' data-estado="{" ".join(palavras)}">'
        f'<span class="b2-gl">{g}</span><span class="b2-nm">{x.nome}</span>'
        f'<span class="b2-val" data-campo="val-{x.b}" data-hef-alvo="texto">'
        f'{a13._texto_do_valor(par, x.b)}</span>'
        f'<span class="b2-atual" hidden data-campo="atual-{x.b}" data-hef-alvo="texto">'
        f'{"" if x.fixo or not par else par[0] + ":" + par[1]}</span></button>')


def _aba_da_sequencia():
    """A aba Sequência do «vira», copiada do desenho final: gravar, os passos, o jeito e o ritmo."""
    from pacotes import a13_mapa_do_controle as a13

    exemplo = a13.passos_em_html([("cross", 80), ("circle", 120), ("r1", 60), ("dpad_up", 0)])
    ao_apertar = "".join(
        f'<option value="{v}"{" selected" if v == "uma_vez" else ""}>{r}</option>'
        for v, r in a13.JEITOS_DA_SEQUENCIA)
    ritmo = "".join(
        f'<option value="{v}"{" selected" if v == "gravado" else ""}>{r}</option>'
        for v, r in a13.RITMOS_DA_SEQUENCIA)
    return (
        '<div class="sel2-grade seq-grade" data-aba="sequencia" hidden>\n'
        '          <button class="op3 gravar seq-grava" data-gesto="mapa-sequencia-gravar" data-gravando=""'
        ' data-campo="seq-gravando" data-hef-alvo="atributo" data-hef-atributo="data-gravando">'
        '<span class="ponto"></span><span data-campo="seq-rotulo" data-hef-alvo="texto">'
        'Gravar a sequência</span></button>\n'
        '          <div class="seq-passos" aria-label="A sequência gravada" data-campo="seq-passos"'
        f' data-hef-alvo="html">{exemplo}</div>\n'
        '          <label class="seq-campo">Ao apertar<select data-gesto="mapa-sequencia-jeito"'
        f' data-campo="seq-jeito" data-hef-alvo="valor">{ao_apertar}</select></label>\n'
        '          <label class="seq-campo">Ritmo<select data-gesto="mapa-sequencia-ritmo"'
        f' data-campo="seq-ritmo" data-hef-alvo="valor">{ritmo}</select></label>\n'
        '          <button class="op3 txt seq-tocar" data-gesto="mapa-sequencia-tocar">'
        '<span>Tocar para ouvir</span></button>\n'
        '        </div>')


def _grade_do_seletor(pecas):
    from pacotes import a13_mapa_do_controle as a13

    controle_ = "".join(
        f'<button class="op3" data-v="troca:{d}" data-gesto="mapa-escolher">'
        f'{glifo(pecas[peca]["glifo"], tam=18)}<span>{rotulo}</span></button>'
        for d, rotulo, peca in a13.OPCOES_DE_CONTROLE)
    mouse = "".join(
        f'<button class="op3 txt" data-v="acao:{t}" data-gesto="mapa-escolher"><span>{r}</span></button>'
        for t, r in a13.OPCOES_DE_MOUSE)
    teclado = "".join(
        f'<button class="op3 txt" data-v="acao:{t}" data-gesto="mapa-escolher"><span>{r}</span></button>'
        for t, r in a13.OPCOES_DE_TECLADO)
    return (
        '<div class="sel2" hidden role="dialog" aria-label="O que o botão faz">\n'
        '        <div class="sel2-topo"><span class="sel2-tit"><span class="sel2-b">Cruz</span> vira</span>\n'
        '          <div class="seg2" role="tablist"><button class="on" data-aba="controle">Controle</button>'
        '<button data-aba="mouse">Mouse</button><button data-aba="teclado">Teclado</button>'
        '<button data-aba="sequencia">Sequência</button></div>\n'
        '          <button class="sel2-x" aria-label="Fechar">×</button></div>\n'
        f'        <div class="sel2-grade" data-aba="controle">{controle_}</div>\n'
        f'        <div class="sel2-grade" data-aba="mouse" hidden>{mouse}</div>\n'
        '        <div class="sel2-grade" data-aba="teclado" hidden>'
        '<button class="op3 gravar"><span class="ponto"></span><span>Gravar tecla</span></button>'
        f'{teclado}</div>\n'
        f'        {_aba_da_sequencia()}\n'
        '        <div class="sel2-rod"><button class="op3 txt limpar" data-v="sem" data-gesto="mapa-escolher">'
        '<span>Sem mudança</span></button></div>\n'
        '      </div>')


def main():
    from pacotes import a13_mapa_do_controle as a13
    import monta
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.profiles import loader

    pecas = {p["id"]: p for p in le_csv()}
    ds = controle(list(pecas.values()))
    valores = a13._por_botao({m: (a13.ACAO, t) for m, t in acoes.tabela_efetiva(None, None).items() if t})
    escolhida = None  # a edição nasce sem linha escolhida: nada aceso sem clique

    def coluna(lado):
        return "\n".join(_linha_da_tela(x, pecas, valores, escolhida)
                         for x in a13.BOTOES_DA_PAGINA if x.lado == lado)

    moldes = "".join(f'<option value="molde:{m.chave}">{m.nome}</option>' for m in loader.MOLDES_DE_PERFIL)
    perfis = ('<optgroup label="Navegação"><option value="nav">Navegar no computador</option></optgroup>'
              f'<optgroup label="Moldes">{moldes}</optgroup><option value="novo">+ Novo perfil…</option>')
    doc = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — o mapa do controle</title>
<style>{CSS_BASE}{caixa_da_janela.moldura()}{CSS_TELA}
{css_das_pecas(sorted({x.peca for x in a13.BOTOES_DA_PAGINA}))}
</style>
</head>
<body>
<div class="cx mc" role="dialog" aria-modal="true" aria-label="Mapa do controle" data-tipo="nav"
     data-campo="mc-tipo" data-hef-alvo="atributo" data-hef-atributo="data-tipo">
  <div class="mc-topo">
    <a class="voltar2 voltar" href="06-navegacao.html" onclick="if (history.length > 1) {{ history.back(); return false }}" title="Volta para a Navegação">← Voltar</a>
    <h1 id="mc-titulo">Mapa do controle</h1>
    <span class="mc-rot" data-dica="O mapa vale só para o controle escolhido; cada controle guarda o seu">Vale para</span><div class="mc-chips" data-bloco="controles-do-mapa">{_chips_de_exemplo()}</div>
  </div>
  <div class="corpo">
  <div class="mc-perfil" data-fixo="sim" data-campo="mc-fixo" data-hef-alvo="atributo" data-hef-atributo="data-fixo">
    <span class="cel">
    <label class="mc-rot" for="perfil">Perfil</label>
    <select id="perfil" class="campo2" data-gesto="mapa-perfil" data-campo="perfil" data-hef-alvo="valor" data-dica="Navegação, point and click e trocas de botão">{perfis}</select>
    <i hidden data-campo="ancora-pac" data-hef-alvo="atributo" data-hef-atributo="data-chave" data-chave=""></i>
    <i hidden data-campo="ancora-trocar" data-hef-alvo="atributo" data-hef-atributo="data-chave" data-chave=""></i>
    </span>
    <span class="cel">
    <span class="etiqueta" data-campo="etiqueta" data-hef-alvo="texto" data-dica="A cor do tipo marca os botões mudados">Navegação</span>
    <label class="mc-rot" for="nome">Nome</label>
    <input id="nome" class="campo2 nome2" data-gesto="mapa-nome" data-campo="nome" data-hef-alvo="valor" value="Navegar no computador">
    </span>
    <span class="cel">
    <span class="mc-rot">Usar em</span>
    <span class="usar-em" data-campo="usar-em" data-hef-alvo="html"><span class="jogo">Fora do jogo</span></span>
    </span>
  </div>
  <div class="mapa mc-mapa">
    <div class="mc-lado">
{coluna("esq")}
    </div>
    <div class="mc-centro">
      <div class="mc-desenho">
{ds}
      </div>
      <div class="mc-baixo">
{coluna("baixo")}
      </div>
      {_grade_do_seletor(pecas)}
    </div>
    <div class="mc-lado">
{coluna("dir")}
    </div>
  </div>
  <div class="mc-cursor">
    <span class="par2"><span class="mc-rot">Mover com</span><select class="campo2" data-gesto="mapa-mover-com" data-campo="cursor-mover" data-hef-alvo="valor"><option value="esq" selected>Analógico esquerdo</option><option value="dir">Analógico direito</option></select></span>
  </div>
  </div>
  <div class="mc-rod">
    <a class="btn2" href="06-navegacao.html" data-gesto="mapa-cancelar">Cancelar</a>
    <button class="btn2 amarelo" data-gesto="mapa-padrao">Voltar ao padrão</button>
    <button class="btn2 roxo" data-gesto="mapa-guardar">Guardar</button>
  </div>
  <button id="mapa-captura" hidden tabindex="-1" aria-hidden="true" data-gesto="mapa-gravar-tecla"></button>
  <button id="mapa-solta" hidden tabindex="-1" aria-hidden="true" data-gesto="mapa-botao" data-b=""></button>
</div>
<script>{JS}</script>
</body>
</html>
'''
    onde.gravar(SAIDA.name, monta.com_a_base(doc))
    print(f"mapa-do-controle.html: {len(a13.BOTOES_DA_PAGINA)} botões, {len(pecas)} peças")


if __name__ == "__main__":
    main()
