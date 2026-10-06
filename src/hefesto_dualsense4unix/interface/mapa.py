#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O MAPA DO CONTROLE — a fonte da verdade das peças, funcional."""
import csv, json, math, pathlib, re, sys

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from onde import RAIZ as R  # noqa: E402

DADOS_DO_REPO = R / "docs/data"
CSV = DADOS_DO_REPO / "pecas-do-dualsense.csv"
CSV_CORES = DADOS_DO_REPO / "cores-do-dualsense.csv"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(R / "src"))
import onde  # noqa: E402
import caixa_da_janela  # noqa: E402
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402
    player_led_pattern,
)
GLIFOS = R / "assets/glyphs"
SVG = R / "src/hefesto_dualsense4unix/interface/ds_limpo.svg"
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
    x = re.sub(r'(stroke|fill)="#[0-9a-fA-F]{3,8}"', r'\1="currentColor"', x)
    x = re.sub(r'\s+width="32"\s+height="32"', "", x)
    return x.replace("<svg ", f'<svg width="{tam}" height="{tam}" ', 1).strip()


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

# O CHASSI NÃO É BOTÃO (ela, 03/10/2026: «removermos o chassi como botão»): sem
# alvo no desenho e sem linha na lista. A linha dele fica no CSV das peças, que
# é o dono delas; o que sai é só o que se podia apontar e clicar.
SEM_BOTAO = {"corpo"}

# A HÁPTICA TEM LUGAR NO DESENHO (ela: «falta colocarmos o háptico»), e o lugar é
# o do glifo dela: a área do touchpad, com ondas na borda de cima. O grupo nasce
# aqui, e não no `ds_limpo.svg`, porque o arquivo do desenho é dela e este
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


def controle(pecas, trocam=()):
    """O desenho — que É o arquivo dela — com os alvos do ponteiro por cima."""
    x = sobe_a_letra(SVG.read_text())
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

    marcas = []
    for pid in trocam:
        corpo = re.sub(r"<ellipse\b[^>]*/>", "", forma_cheia(x, pid))
        if corpo:
            marcas.append(f'  <g class="marca-troca m-{pid}">{corpo}</g>')
    return x.replace("</svg>", "\n".join(marcas + [t[2] for t in saida]) + "\n</svg>", 1)

def cores_do_csv():
    """Os 28 modelos do `cores-do-dualsense.csv`, agrupados por modelo."""
    linhas = [x for x in CSV_CORES.read_text().splitlines()
              if x and not x.startswith("#")]
    fora = {}
    for c in csv.DictReader(linhas):
        fora.setdefault(c["id"], []).append(c)
    return fora


ZONAS_NA_PROVA = ("casca_esq", "casca_dir", "painel", "touch", "botoes_face",
                  "simbolos", "dpad", "analogicos", "gatilhos")


def banco_de_provas():
    """A barra de provas: cor do plástico, o controle e a barra de luz."""
    import monta
    from pacotes import a13_mapa_do_controle as a13

    primeiro = monta.MESA[0]
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
              + (" selected" if mid == primeiro["cor"] else "")
              + f">{rot}</option>")
        (especiais if cod[0] == "Z" else fabrica).append(op)

    padroes = {n: [i + 1 for i, on in enumerate(player_led_pattern(n)) if on]
               for n in range(1, 5)}
    chips = a13.chips_do_controle(monta.MESA, str(primeiro["pref"]), vivo=False)

    barra_html = f"""  <div class="provas">
    <div class="prova">
      <div class="prova-rot">Cor do plástico</div>
      <select id="cw" class="ct">
        <optgroup label="De fábrica">{"".join(fabrica)}</optgroup>
        <optgroup label="Edições especiais">{"".join(especiais)}</optgroup>
      </select>
    </div>
    <div class="prova">
      <div class="prova-rot">Controle<span class="papel" data-campo="{a13.PAPEL}" data-hef-alvo="html"></span></div>
      <div class="linha" data-bloco="controles-do-mapa">{chips}</div>
    </div>
    <div class="prova-nota" id="nota">&nbsp;</div>
  </div>
"""

    script = f"""  <script>
  // O PADRÃO DAS LÂMPADAS É DO PRODUTO — `core/led_control.py`. Copiar a tabela
  // para cá seria criar a segunda verdade que este mapa existe para matar.
  const PADRAO = {json.dumps(padroes)};
  const PARCIAL = "hachurado = o acabamento não cabe num hexadecimal (iridescente, "
                + "metálico, camuflado, arte); cinza chapado = zona sem amostragem.";
  const ds = document.querySelector("svg.ds");
  const barra = document.querySelector("#mp-lightbar");
  const nota = document.querySelector("#nota");
  const cw = document.querySelector("#cw");
  const cx = document.querySelector(".cx");
  const chips = document.querySelector('[data-bloco="controles-do-mapa"]');

  function plastico(modelo) {{
    if (modelo) {{ ds.dataset.colorway = modelo; cw.value = modelo; }}
    else {{ delete ds.dataset.colorway; cw.value = ""; }}
    const op = cw.selectedOptions[0];
    nota.textContent = op && op.dataset.parcial ? PARCIAL : "\u00a0";
  }}
  cw.addEventListener("change", e => plastico(e.target.value));

  // A BARRA DE LUZ E O JOGADOR ANDAM JUNTOS no banco de provas (o chip do
  // desenho leva a cor do jogador em `data-luz`), e é assim no aparelho: o PS5
  // acende as duas coisas ao numerar um controle. No produto o chip não leva
  // cor, e a barra fica com a do aparelho, que o tique pinta (`luz-cor`).
  function acende(n, luz) {{
    for (let i = 1; i <= 5; i++)
      document.querySelector("#mp-led-jogador-" + i)
              .classList.toggle("led-on", (PADRAO[n] || []).includes(i));
    if (luz) {{
      barra.style.setProperty("--luz", luz);
    }} else if (n) {{
      barra.style.removeProperty("--luz");
    }} else {{
      barra.style.setProperty("--luz", "var(--luz-apagada)");
    }}
  }}

  // O DESENHO SEGUE O CHIP: as lâmpadas pelo número do jogador, o plástico
  // pelo modelo. O «Nenhum» é o desenho sem controle, e com ele o pisca não
  // acende (`.sem-controle`). O «Cor do plástico» continua livre: escolher
  // um modelo depois de um chip vale até o próximo chip.
  // O «Todos» não é UM controle: o desenho dele é o do primeiro da mesa, o
  // mesmo de quem o produto pinta a barra (`luz-cor`). Sem isso, as lâmpadas e
  // o plástico ficavam os do chip anterior.
  function primeiro() {{
    return chips.querySelector('.bt[data-jogador]:not([data-jogador="0"])');
  }}
  function desenha(b) {{
    const d = b.hasAttribute("data-jogador") ? b : (primeiro() || b);
    if (d.hasAttribute("data-jogador")) acende(+d.dataset.jogador, d.dataset.luz);
    if (d.hasAttribute("data-colorway")) plastico(d.dataset.colorway);
    cx.classList.toggle("sem-controle", d.dataset.jogador === "0");
  }}
  // POR DELEGAÇÃO, porque o produto troca os chips a cada mudança da mesa: um
  // ouvinte posto em cada botão ao carregar morreria com o bloco.
  document.addEventListener("click", e => {{
    const b = e.target.closest('[data-bloco="controles-do-mapa"] .bt');
    if (!b) return;
    chips.querySelectorAll(".bt").forEach(x => x.classList.toggle("on", x === b));
    desenha(b);
  }});
  // A MESA SEM CONTROLE é o «Nenhum»: o bloco do produto chega só com ele, e
  // o desenho não pode ficar com as lâmpadas e a barra do chip da bancada.
  function segue() {{
    let b = chips.querySelector(".bt.on[data-jogador]") || primeiro();
    if (!b) {{
      b = chips.querySelector('.bt[data-jogador="0"]');
      if (b && !chips.querySelector(".bt.on")) b.classList.add("on");
    }}
    if (b) desenha(b);
  }}
  new MutationObserver(segue).observe(chips, {{childList: true}});

  // O MAPA NASCE COM LUZ: o desenho do chip aceso. Sem jogador, o lightbar e as
  // cinco lâmpadas ficam na cor de apagado — e ela reparou na ausência antes:
  // "faltou só os dois lightbar e os led de player". O apagado continua a um
  // clique, no botão "Nenhum".
  segue();
  </script>
"""
    return barra_html, script


def gestos_do_ps():
    """Os seis gestos do PS, com o número da linha da tabela da Navegação."""
    import aba06

    linhas = []
    for n, pecas_do_gesto, faz in aba06.COMBOS:
        botoes = " + ".join(aba06.nome_de(x) for x in pecas_do_gesto)
        linhas.append(f'<li><span class="n">{n}</span>{botoes} · {faz}</li>')
    return f'<ol class="gestos">{"".join(linhas)}</ol>'


def main():
    from pacotes import a13_mapa_do_controle as a13

    pecas = le_csv()
    ds = controle(pecas, trocam=a13.TROCAM)
    provas, script_provas = banco_de_provas()
    na_navegacao = a13._acoes({})

    regras = []
    for p in pecas:
        i = p["id"]
        if i in SEM_BOTAO:
            continue
        alvo_css = f'#mp-{i} :is(.peca, rect, circle, path, ellipse)'
        # própria) não acendia — o portão dava verde porque media o CSS computado  # (noqa-acento: verbo medir, imperfeito)
        if i not in SO_O_GLIFO_ACENDE:
            regras.append(f'.mapa:has(.item-{i}:hover) {alvo_css}'
                          f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')
        regras.append(f'.mapa:has(.item-{i}:hover) .s-{i}{{color:var(--fg) !important;opacity:1}}')
        regras.append(f'.mapa:has(.a-{i}:hover) .item-{i}'
                      f'{{border-color:var(--pink);background:rgba(255,121,198,.12);color:var(--fg)}}')
        regras.append(f'.mapa:has(.a-{i}:hover) .s-{i}{{color:var(--fg) !important;opacity:1}}')
        if i not in SO_O_GLIFO_ACENDE:
            regras.append(f'.mapa:has(.a-{i}:hover) {alvo_css}'
                          f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')
        if i in a13.PISCAM:
            if i not in SO_O_GLIFO_ACENDE:
                regras.append(f'.cx:not(.sem-controle) .mapa:has(.item-{i}.on) {alvo_css}'
                              f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')
            regras.append(f'.cx:not(.sem-controle) .mapa:has(.item-{i}.on) .s-{i}'
                          f'{{color:var(--fg) !important;opacity:1}}')
        if i in a13.TROCAM:
            regras.append(f'.mapa:has(.item-{i} .troca.tem) .m-{i}{{display:inline}}')
        if i in a13.SENSORES:
            # O SENSOR ACENDE NO DESENHO, na cor do ponteiro, no hover da linha e
            # quando o serviço diz que ele está em uso (`.item.on`). Os `feat-*`
            # nascem `.oculta` (opacity 0 !important), e é por isso que a regra
            # que os mostra repete o `!important`.
            for gatilho in (f'.mapa:has(.item-{i}:hover)', f'.mapa:has(.a-{i}:hover)',
                            f'.cx:not(.sem-controle) .mapa:has(.item-{i}.on)'):
                regras.append(f'{gatilho} #mp-{i}{{opacity:1 !important}}')
                regras.append(f'{gatilho} #mp-{i} .peca'
                              f'{{fill:var(--pink) !important;stroke:var(--pink) !important}}')

    blocos = []
    for chave, titulo in REGIOES:
        na_regiao = [p for p in pecas if p["regiao"] == chave and p["id"] not in SEM_BOTAO]
        if not na_regiao:
            continue
        itens = []
        for p in na_regiao:
            g = glifo(p["glifo"], tam=26) if p["glifo"] != "-" else '<span class="sem">—</span>'
            apel = f'<span class="ap">{p["apelidos"]}</span>' if p["apelidos"] not in ("-", "") else ""
            prop = ' <span class="prop">proposto</span>' if p["grau"] == "PROPOSTO" else ""
            nota = f'<span class="nota-peca" title="{p["nota"]}">i</span>' if p["nota"] else ""
            pid = p["id"]
            aceso = (f' data-campo="{a13.ACESO}{pid}" data-hef-alvo="classe"'
                     if pid in a13.PISCAM or pid in a13.SENSORES else "")
            acao = (f' data-campo="{a13.ACAO}{pid}" data-hef-alvo="atributo"'
                    f' data-hef-atributo="title" title="{na_navegacao[a13.ACAO + pid]}"'
                    if pid in a13.NA_NAVEGACAO else "")
            troca = (f'<span class="troca" data-campo="{a13.TROCADA}{pid}" data-hef-alvo="classe"'
                     f' data-hef-classe="tem">No jogo: <b data-campo="{a13.TROCA}{pid}"'
                     f' data-hef-alvo="html"></b></span>' if pid in a13.TROCAM else "")
            gestos = gestos_do_ps() if pid == "ps" else ""
            itens.append(
                f'      <div class="item item-{pid}"{aceso}>'
                f'<span class="gl">{g}</span>'
                f'<span class="txt"{acao}><b>{p["nome"]}</b>{apel}{prop}{troca}'
                f'<span class="id mono">{pid}</span></span>{nota}{gestos}</div>')
        blocos.append(f'    <div class="grupo">\n      <div class="grupo-rot">{titulo}</div>\n'
                      + "\n".join(itens) + "\n    </div>")

    faltam = [p for p in pecas if p["no_svg"] == "falta" and p["id"] != HAPTICA]

    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — o mapa do controle</title>
<style>
  :root{{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --border-sutil:#343746; --border-forte:#44475a;
    --branco:#ffffff; --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#8b8fa8; --comment:#6272a4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555; --yellow:#f1fa8c;
    /* A COR DO PLÁSTICO NÃO MORA MAIS AQUI. Ela vem do <style> gerado dentro do
       próprio SVG (scripts/gerar_cores_do_dualsense.py), zona por zona, dos 28
       modelos do docs/data/cores-do-dualsense.csv. O `--cosmic-red:#b11f54` que
       ficava nesta linha era um hex digitado à mão que a amostragem de 27/08
       derrubou — o Cosmic Red é #A51C48, distância 17. Fato errado, substituído.
       Quem precisa de UMA cor do casco lê `var(--z-casca-solida)`. */
    --luz-apagada:#3f4350; --led-apagado:#4a4f5c; --led-aceso:#e8ecf5;
    /* O CONTROLE SEM PLÁSTICO LIDO (pelo rádio a cor não se lê): o chip dele
       apaga o `data-colorway`, e o casco cai neste cinza, o mesmo cru do
       `ds_limpo.svg`, em vez do preto de uma variável sem valor. */
    --sem-plastico:#3a3f4b;
    /* Pilha do sistema: nada de fonte web, para o arquivo abrir sem rede.
       É a regra de scripts/paleta_da_casa.py, e vale aqui igual. */
    --f:ui-sans-serif,system-ui,"Cantarell","Segoe UI",Roboto,sans-serif;
    --m:ui-monospace,"JetBrains Mono","Fira Mono","DejaVu Sans Mono",monospace;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  /* O RECUO DO `body` E O TAMANHO DA `.cx` VÊM DA JANELA DAS ABAS — 24/09/2026,
     decisão de produto: o mapa segue a caixa da janela, como a Calibrar. */
  body{{background:#11121a;color:var(--fg);font-family:var(--f);
        display:flex;flex-direction:column;align-items:center;gap:16px}}
  .mono{{font-family:var(--m)}}
  /* COLUNA COMO A `.janela`: o cabeçalho fica e o `.corpo` rola por dentro
     quando a vista encolhe. `.cx > .corpo`, e não `.corpo` solto: o desenho
     do controle tem peças com essa classe. */
  .cx{{background:var(--app-bg);border-radius:11px;
       border:1px solid var(--border-sutil);overflow:hidden;
       display:flex;flex-direction:column}}
  .cx > .topo{{flex:0 0 auto}}
  .cx > .corpo{{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column}}
  .cx > .corpo > .mapa{{flex:1 0 auto}}
{caixa_da_janela.moldura()}  .topo{{padding:15px 20px;border-bottom:1px solid var(--border-sutil)}}
  h1{{font-size:18px;font-weight:700}}
  h1 .p{{color:var(--pink)}}
  .sub{{font-family:var(--m);font-size:11.5px;color:var(--comment);margin-top:3px}}

  /* A LISTA GANHOU 140px E UMA TERCEIRA COLUNA — 01/09/2026

     MEDIDO ANTES: a página pedia 1042px numa janela de 800 — 242px de rolagem
     vertical. O culpado era a LISTA, com 832px fixos, enquanto o desenho ao lado
     encolhia com a janela (710px em 1080, 387px em 800). Duas colunas de 28
     peças em 12 grupos não cabem em tela nenhuma abaixo de 1080.

     COM TRÊS COLUNAS ELA CAI PARA 573px, e a página passa a caber inteira:
     **zero rolagem vertical e zero lateral** em 1920x1080, 1600x900, 1440x900 e
     1390x800 — as quatro medidas.

     E OS 920px SÃO HARMONIA MEDIDA, que foi a outra metade do pedido. Com
     os 860 que a conta da rolagem pedia, **8 dos 28 itens quebravam em duas
     linhas** (`feat-rumble-esquerdo`, `feat-giroscopio`, `led-jogador`), e dois
     chegavam a 61px de altura numa lista onde o padrão é 36. Com 920 são 4, e o
     mais alto cai para 44. Testei até 1100: de 920 em diante o ganho estagna
     (24, 24, 25, 25 itens inteiros) e o desenho é que encolhe — 920 é onde a
     curva vira. */
  .mapa{{display:grid;grid-template-columns:minmax(0,1fr) 920px;gap:0;align-items:stretch}}
  .lado-ds{{padding:20px 24px;display:flex;align-items:center;justify-content:center}}
  /* A LISTA NÃO ROLA DE LADO — 31/08/2026

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
  /* TUDO PREENCHIDO — decisão, 27/08: os paths deste SVG são FAIXAS e
     ANÉIS. Traçá-los fazia cada aresta virar dois fios a 0,99 de distância:
     era a linha dupla do casco, as várias voltas dos botões, os furos do
     alto-falante em rosquinha e as lâmpadas ocas — tudo a mesma causa. */
  .ds .peca,.ds .corpo{{stroke:none}}
  /* TODA PEÇA PINTA COMO PEÇA, mesmo sem a classe. O desenho dela nem sempre
     carrega `class="peca"` — o Options, por exemplo, ficou sem `fill` nenhum e
     herdou o preto padrão do SVG. Aqui a folha alcança qualquer forma que viva
     dentro de um grupo de peça e não seja glifo. */
  .ds g[id^="mp-"]:not([id^="mp-glifo"]):not(.sobre):not(.alvo)
    > :is(rect,path,circle,ellipse,polygon){{fill:var(--z-casca-solida, var(--sem-plastico))}}
  /* O LIGHTBAR E O INDICADOR DE JOGADOR SÃO LUZ, e não plástico. Na cor do casco
     eles caíam sobre a borda do touchpad e sumiam — ela: "faltou só os dois
     lighbar e os led de player". Cor de luz, e aparecem. */
  .ds #mp-lightbar{{color:var(--luz-apagada)}}
  .ds #mp-lightbar *{{fill:var(--luz, currentColor)}}
  .ds #mp-led-jogador rect{{fill:var(--led-apagado)}}
  .ds #mp-led-jogador rect.led-on{{fill:var(--led-aceso)}}
  /* o PS não tem anel: a peça existe só para dar caixa e alvo, e quem se vê — e
     quem acende — é o glifo. Decisão, 27/08: "Remove o circulo e Deixa só o
     Glifo do PS pra ser o Botão". */
  .ds .sem-tinta{{fill:none !important;stroke:none !important}}
  /* A PONTA DO PUNHO fechava em BICO: a borda externa e a interna do punho
     convergem num vértice agudo, e preenchidas isso vira uma farpa. O traço
     da mesma cor com junta redonda arredonda o vértice sem mudar o path. */
  .ds #mp-corpo .peca,.ds #mp-corpo .corpo{{stroke:var(--z-casca-solida, var(--sem-plastico));stroke-width:.42;
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
     mesmo tempo, que foi o "não tá funcionando" que o usuário viu. */
  .mapa:has(.item-feat-giroscopio:hover) #mp-feat-giroscopio .peca,
  .mapa:has(.item-feat-acelerometro:hover) #mp-feat-acelerometro .peca,
  .mapa:has(.item-feat-bateria:hover) #mp-feat-bateria .peca,
  .mapa:has(.item-feat-rumble-esquerdo:hover) #mp-feat-rumble-esquerdo .peca,
  .mapa:has(.item-feat-rumble-direito:hover) #mp-feat-rumble-direito .peca
    {{fill:var(--pink) !important;stroke:var(--pink) !important}}
  /* A BATERIA É O LIGHTBAR. Decisão, 27/08: "bateria pode ser usando as
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
  .ds #mp-corpo .peca{{stroke:var(--z-casca-solida, var(--sem-plastico))}}
  /* os glifos POR CIMA do desenho — a mesma peça, vista de dois jeitos */
  .sobre{{color:var(--branco);opacity:1;pointer-events:none}}
  /* OS GLIFOS DO USUÁRIO TRAZEM COR NO `style` INLINE, e style inline vence folha: no
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
     A cura é na ALTURA, encolhendo o mais alto — regra, 27/08 —, e não em
     `space-between`: o item passa de 38 para 36 px, que é o `--h-escolha` da
     escala desta casa, e o vão entre grupos de 13/11 para 11/9. Com isso o
     conteúdo cai de 864 para 832 px, cabe nas duas colunas, e a página fecha
     com ZERO de rolagem (era 12 px). */
  .grupo + .grupo{{margin-top:11px;padding-top:9px;border-top:1px solid var(--border-sutil)}}
  /* O TEXTO DA LISTA E OS RÓTULOS SÃO BRANCOS (ela, 03/10/2026) (noqa-acento: citação). A cor fica no desenho;
     o texto lê-se. */
  .grupo-rot{{font-size:10.5px;color:var(--branco);
              letter-spacing:.6px;margin-bottom:6px}}
  .item{{display:flex;align-items:center;gap:11px;padding:4px 9px;border-radius:7px;
         border:1px solid transparent;color:var(--branco);cursor:default}}
  .item:hover{{border-color:var(--border-forte);background:rgba(255,121,198,.06);cursor:pointer}}
  .item .gl{{flex:0 0 26px;height:26px;display:flex;align-items:center;justify-content:center}}
  .item .sem{{color:var(--border-forte);font-size:15px}}
  .item .txt{{display:flex;align-items:baseline;gap:8px;flex:1;min-width:0}}
  .item .txt b{{font-size:12px;font-weight:600}}
  .item .ap{{font-size:11px;color:var(--branco)}}
  .item .id{{margin-left:auto;font-size:10.5px;color:var(--branco)}}
  .item .prop{{font-size:9.5px;color:var(--orange);border:1px solid var(--orange);
               border-radius:4px;padding:0 4px;}}
  .nota-peca{{flex:0 0 15px;width:15px;height:15px;border-radius:50%;font-size:10px;
              line-height:13px;text-align:center;border:1px solid var(--border-forte);
              color:var(--texto-mudo);cursor:help;font-family:var(--m)}}
  .nota-peca:hover{{border-color:var(--cyan);color:var(--cyan)}}
  /* O PISCA, A TROCA E OS GESTOS — 01/10/2026, O-MAPA-DO-CONTROLE-PISCA-E-SEGUE-
     O-REMAPEAMENTO-01. A linha acesa pelo botão apertado tem a cor do ponteiro.
     O «No jogo» só aparece quando a troca de botões alcança a peça, e entra no
     lugar do apelido, na MESMA linha: medido no piloto em 01/10/2026, uma linha
     a mais embaixo do nome fazia a página rolar 18 px na janela ladrilhada
     (1212 x 809), e o usuário pediu o mapa sem rolagem em 01/09. A marca tracejada no
     desenho é a mesma notícia.
     É uma CLASSE (`tem`), e não `:has(b:empty)`: medido no WebKitGTK em
     01/10/2026, a regra com `:empty` dentro do `:has()` não se recalcula quando
     o produto escreve o texto, e a linha ficava escondida com «Cruz» dentro. */
  .item{{flex-wrap:wrap;row-gap:2px}}
  .cx:not(.sem-controle) .item.on{{border-color:var(--pink);background:rgba(255,121,198,.12);color:var(--fg)}}
  .item .troca{{font-size:11px;color:var(--orange);white-space:nowrap}}
  .item:has(.troca.tem) .ap{{display:none}}
  .item .troca:not(.tem){{display:none}}
  .item .troca b{{font-weight:600}}
  .item .gestos{{flex:0 0 100%;list-style:none;padding-left:37px;font-size:10.5px;
                 line-height:1.4;color:var(--branco)}}
  .item .gestos .n{{font-family:var(--m);color:var(--comment);margin-right:6px}}
  .marca-troca{{display:none}}
  .marca-troca *{{fill:none !important;stroke:var(--pink);stroke-width:.45;
                 stroke-dasharray:1.1 .7;pointer-events:none}}
  .papel .bolinha{{display:inline-block;width:6px;height:6px;border-radius:50%;
                   background:var(--green);margin-right:4px;vertical-align:1px}}
  .bt .pt,.papel .pt{{color:var(--comment);margin:0 1px;font-size:10px;vertical-align:1px}}

  /* A BARRA DE PROVAS. A gramática é a da lista da direita — mesmo rótulo em
     versalete, mesma família de caixa —, para a barra não parecer colada de
     outra tela. Três blocos, e a BARRA VERTICAL entre eles: é o separador que
     o usuário pediu em 27/08 ("uma barra vertical entre os blocos"). */
  .provas{{display:flex;align-items:stretch;border-bottom:1px solid var(--border-sutil)}}
  .prova{{padding:11px 18px;display:flex;flex-direction:column;gap:7px;justify-content:space-between}}
  .prova + .prova{{border-left:1px solid var(--border-sutil)}}
  /* O RÓTULO DOS TRÊS BLOCOS COMEÇA NO MESMO x, e os três terminam no mesmo y.
     O vão se cura na ALTURA — os controles têm todos 28px —, nunca com
     `space-between` entre eles: ela reprovou isso com todas as letras. */
  .prova-rot{{font-size:10.5px;color:var(--branco);
              letter-spacing:.6px;line-height:1}}
  .prova .linha{{display:flex;gap:6px;align-items:center}}
  /* Os chips levam o nome do controle: na janela estreita eles descem de linha. */
  .prova [data-bloco="controles-do-mapa"]{{flex-wrap:wrap}}
  .ct{{height:28px;background:var(--elevated);color:var(--fg);
       border:1px solid var(--border-forte);border-radius:6px;
       padding:0 8px;font-family:var(--f);font-size:12px}}
  /* OS QUATRO NÚMEROS SÃO UMA FAMÍLIA, e família tem a mesma largura. O
     "Nenhum" e o "Apagar" são outro papel — palavra, não número — e por isso
     medem o que a palavra pede. */
  .bt{{height:28px;min-width:30px;padding:0 9px;background:var(--elevated);
       color:var(--texto-suave);border:1px solid var(--border-forte);
       border-radius:6px;font-family:var(--f);font-size:12px;cursor:pointer;white-space:nowrap}}
  .bt:hover{{border-color:var(--pink);color:var(--fg)}}
  .bt.on{{border-color:var(--pink);background:rgba(255,121,198,.14);color:var(--fg)}}
  .prova-nota{{margin-left:auto;align-self:center;padding:0 18px;max-width:460px;
               font-size:11px;line-height:1.45;color:var(--branco)}}

  /* O BOTÃO DE VOLTAR — 30/08/2026, pergunta de produto. Não havia: `grep href` no mapa gerado
     devolvia ZERO. Quem entrava aqui só saía pelo botão do navegador — e o
     mockup abre como ARQUIVO, onde nem sempre há um.
     O destino é a aba de onde ela veio (o dono é o `caixa_da_janela.voltar`). */
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
    <!-- O VOLTAR VOLTA PARA DE ONDE VEIO. Desde 29/09/2026 só a Conexões abre
         este mapa (a Controles e a Navegação o perderam, por ordem de produto), e por
         isso ela é a reserva de quem abre o arquivo direto. O dono é o
         `caixa_da_janela.voltar`, que pergunta à lista de volta do WebView. -->
    {caixa_da_janela.voltar("08-conexoes.html")}
    <h1><span class="p">O mapa do controle</span></h1>
    <!-- A LINHA DE INSTRUÇÃO SAIU — decisão, 31/08/2026: *"passe o mouse
         num glifo e a peça acende no desenho · passe na peça e o glifo acende
         só remove isso."* O comportamento FICA: o que sai é a legenda que o
         narrava. Quem passa o mouse descobre em meio segundo; quem não passa
         não precisava da frase. -->
  </div>

  <div class="corpo">
{provas}
  <div class="mapa">
    <div class="lado-ds">
{ds}
    </div>
    <div class="lado-lista">
{chr(10).join(blocos)}
    </div>
  </div>

  </div>
</div>

{script_provas}
</body>
</html>
'''
    onde.gravar(SAIDA.name, html)
    print(f"mapa-do-controle.html: {len(pecas)} peças, {len(regras)} regras de cruzamento")
    if faltam:
        print("  sem desenho no SVG: " + ", ".join(p["id"] for p in faltam))


if __name__ == "__main__":
    main()
