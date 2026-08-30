# -*- coding: utf-8 -*-
"""Exporta o controle como SVG ORGANIZADO, para ela arrumar no editor.

Pedido dela, 27/08/2026:
  "ou converter o controle inteiro pra svg que arrumo agora"
  "com os nomes de cada elemento descritos nas layers e objetos. os agrupamentos
   também."

O que muda em relação ao ds_limpo.svg: as 29 peças passam a viver dentro de NOVE
grupos nomeados, e todo grupo e toda peça carrega um <title> em português — que é
o que o editor mostra na árvore de camadas. O estilo vem embutido, para o arquivo
abrir com a mesma cara do mapa, sem depender de folha externa.

O caminho de volta é o `importar.py`, irmão deste: ele lê o arquivo que ela salvar,
extrai a caixa de cada peça e reescreve o CSV e o ds_limpo.
"""
import pathlib, re, csv, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import mapa

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
R = pathlib.Path(__file__).resolve().parents[2]
FONTE = R / "layout/_ferramentas/ds_limpo.svg"
SAIDA = pathlib.Path("/home/vitoriamaria/Imagens/dualsense-para-editar.svg")

linhas = [l for l in (R / "docs/data/pecas-do-dualsense.csv").read_text().splitlines()
          if l and not l.startswith("#")]
NOME = {p["id"]: p["nome"] for p in csv.DictReader(linhas)}

GRUPOS = [
    ("chassi",     "CHASSI",              ["corpo", "aresta-topo"]),
    ("face",       "BOTÕES DA FACE",      ["triangle", "circle", "square", "cross"]),
    ("direcional", "DIRECIONAL",          ["dpad_up", "dpad_right", "dpad_down", "dpad_left"]),
    ("ombros",     "OMBROS E GATILHOS",   ["l1", "l2", "r1", "r2"]),
    ("analogicos", "ANALÓGICOS",          ["stick_l", "stick_r"]),
    ("centro",     "CENTRO",              ["touchpad", "share", "options", "ps", "mic"]),
    ("luzes",      "LUZES",               ["lightbar", "led-jogador"]),
    ("audio",      "ÁUDIO",               ["alto-falante"]),
    ("invisiveis", "SENSORES E MOTORES (não aparecem no mapa)",
                   ["feat-giroscopio", "feat-acelerometro", "feat-bateria",
                    "feat-rumble-esquerdo", "feat-rumble-direito"]),
]

s = FONTE.read_text()
vb = re.search(r'viewBox="([^"]+)"', s).group(1)

def pega(pid):
    i = s.index(f'id="{pid}"'); ini = s.rindex("<g ", 0, i); fim = s.index("</g>", i) + 4
    return s[ini:fim]

# Os filhos de cada peça ganham <title> PRÓPRIO — e com nome de verdade, não
# "peça 1". Na árvore do editor é por esse nome que ela acha o que quer mover.
SUB = {
  "lightbar":    ["tira esquerda", "tira direita"],
  "led-jogador": ["lâmpada 1 (sozinha, à esquerda)", "lâmpada 2", "lâmpada 3 (a do meio)",
                  "lâmpada 4", "lâmpada 5 (sozinha, à direita)"],
  "alto-falante": [f"furo {i} da linha de cima" for i in range(1, 6)]
                  + [f"furo {i} da linha de baixo" for i in range(1, 5)],
  "corpo":       ["casco"],
  "feat-rumble-esquerdo": ["empunhadura esquerda"],
  "feat-rumble-direito":  ["empunhadura direita"],
}

def nomeia_filhos(bloco, base, pid=None):
    partes = [m.group(0) for m in
              re.finditer(r"<(?:rect|path|circle|ellipse|polygon)\b[^>]*/>", bloco)]
    if len(partes) < 2:
        return bloco
    for n, tag in enumerate(partes, 1):
        nome_tag = re.match(r"<(\w+)", tag).group(1)
        rot = (SUB.get(pid, [])[n-1] if pid in SUB and n <= len(SUB[pid])
               else f"peça {n}")
        novo = tag[:-2] + f"><title>{base} — {rot}</title></{nome_tag}>"
        bloco = bloco.replace(tag, novo, 1)
    return bloco

# ---- OS GLIFOS VÃO JUNTO -------------------------------------------------
# Ela: "sumiu os glifos preciso deles lá". Eles moravam só no gerador do mapa —
# no SVG não existiam, e por isso não dava para arrumá-los no editor. Agora cada
# um vai como um grupo próprio, `glifo-<peça>`, com a posição e o tamanho que o
# mapa lhe dá hoje. Mexer neles no editor passa a ser o jeito de ajustá-los: o
# importar.py lê a caixa de cada um e o mapa passa a obedecer.
def grupo_glifos(pecas):
    fora = []
    for p in pecas:
        if p["glifo"] == "-" or p["x1"] == "-":
            continue
        if p["tipo"] not in ("botao", "gatilho", "eixo", "entrada"):
            continue
        if p["id"] in mapa.SEM_GLIFO_NO_DESENHO:
            continue
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        base = float(p["face"]) if p.get("face", "-") not in ("-", "") \
               else min(x2 - x1, y2 - y1)
        lado = mapa.TAMANHO.get(p["id"], min(max(base * 0.92, 5.2), 8.0))
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if p["id"] in mapa.AO_LADO:
            dx, dy = mapa.AO_LADO[p["id"]]; cx, cy = cx + dx, cy + dy
        if p["id"] in mapa.MESMA_LINHA:
            cy = mapa.MESMA_LINHA[p["id"]]
        cx += mapa.DESLOCA_X.get(p["id"], 0.0)
        g = mapa.so_a_letra(p["id"], mapa.glifo(p["glifo"], tam=32))
        # DESEMBRULHA o <svg> do glifo. Duas razões, e as duas apareceram na tela
        # dela: (1) sem `width`/`height` um <svg> aninhado ocupa 100% do viewport, e
        # os 18 glifos saíram do tamanho de um controle cada um; (2) mesmo com as
        # medidas certas, um <svg> dentro de outro é uma caixa-preta no editor —
        # desembrulhado, ela pega o path do triângulo e mexe nele.
        g = re.sub(r"^<svg[^>]*>|</svg>$", "", g.strip())
        ang = float(p.get("angulo") or 0)
        rot = f" rotate({ang:.2f})" if ang else ""
        tx, ty = ((16.0, 16.0) if p["id"] in mapa.SO_LETRA
                  else mapa.TINTA.get(p["glifo"], (16.0, 16.0)))
        s_ = lado / 32
        fora.append(
            f'    <g id="glifo-{p["id"]}" style="--lado:{lado:.3f}" '
            f'transform="translate({cx:.3f} {cy:.3f}){rot} scale({s_:.5f}) '
            f'translate({-tx:.3f} {-ty:.3f})">'
            f'<title>Glifo — {NOME.get(p["id"], p["id"])}</title>{g}</g>')
    return fora

pecas_csv = list(csv.DictReader(linhas))
glifos = grupo_glifos(pecas_csv)

corpo = []
for gid, titulo, pids in GRUPOS:
    dentro = []
    for pid in pids:
        try:
            b = pega(pid)
        except ValueError:
            continue
        # (a opacidade das features é VISUALIZAÇÃO e vive na folha embutida —
        #  injetá-la como atributo fazia o importador trazê-la de volta como se
        #  fosse geometria, e na segunda volta ela duplicava e quebrava o XML)
        b = nomeia_filhos(b, NOME.get(pid, pid), pid)
        dentro.append("    " + b.replace("\n  ", "\n    "))
    if dentro:
        corpo.append(f'  <g id="grupo-{gid}"><title>{titulo}</title>\n'
                     + "\n".join(dentro) + "\n  </g>")

if glifos:
    corpo.append('  <g id="grupo-glifos"><title>GLIFOS (o símbolo de cada peça)</title>\n'
                 + "\n".join(glifos) + "\n  </g>")

# A COR DO ARQUIVO DE EDIÇÃO SAI DO MESMO LUGAR QUE A DO DESENHO.
# Ela era `#b11f54` digitada aqui — o Cosmic Red que a amostragem de 27/08
# derrubou (`#A51C48`, distância 17). Um arquivo de edição pintado com o hex
# velho ensina o hex velho a quem edita, e é a terceira cópia da mesma cor.
# Aqui ela vem do `<style>` que `scripts/gerar_cores_do_dualsense.py` escreveu
# dentro do SVG, pela mesma função que o `monta.py` usa.
import sys as _sys
_sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from monta import cor_da_zona as _cor  # noqa: E402

_CASCA = _cor("cosmic-red")

ESTILO = f"""  <style>
    /* Tudo PREENCHIDO — foi a decisão dela em 27/08. Os paths são faixas e anéis:
       traçá-los faz cada aresta virar dois fios.
       A COR É A DO COSMIC RED, lida do desenho — não digitada. Ela é só para
       você enxergar enquanto edita; quem manda na cor final é
       `docs/data/cores-do-dualsense.csv`. */
    .peca      {{ fill: {_CASCA}; stroke: none; }}
    #grupo-chassi .peca {{ stroke: {_CASCA}; stroke-width: .42;
                          stroke-linejoin: round; stroke-linecap: round; }}
    .sem-tinta {{ fill: none !important; stroke: none !important; }}
    .oculta    {{ opacity: .35; }}
    /* os glifos: cinza claro, como no mapa */
    #grupo-glifos {{ color: #c8ccda; }}
    #grupo-glifos [stroke] {{ stroke: currentColor; }}
    #grupo-glifos [fill]:not([fill="none"]) {{ fill: currentColor; }}
    #grupo-glifos [stroke-width] {{ stroke-width: calc(.35 * 32 / var(--lado)); }}
  </style>"""

SAIDA.write_text(
f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- ===========================================================================
     DualSense — o controle para EDITAR.
     Gerado em 27/08/2026 a pedido dela: "converter o controle inteiro pra svg que
     arrumo agora", "com os nomes de cada elemento descritos nas layers e objetos".

     COMO USAR
       1. Abra este arquivo no seu editor (Boxy SVG, Figma, Inkscape).
       2. A árvore de camadas traz NOVE grupos, e cada peça com o nome em português.
       3. Mova, gire e redimensione o que quiser. NÃO RENOMEIE os ids: é por eles
          que o caminho de volta reconhece cada peça.
       4. Salve por cima deste mesmo arquivo.
       5. Me avise. O `importar.py` lê a caixa de cada peça daqui e reescreve
          docs/data/pecas-do-dualsense.csv e o desenho do mapa.

     O que NÃO mexer: os atributos id. Todo o resto é seu.
     ======================================================================== -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="1160" height="800"
     data-controle="dualsense" data-modelo="Sony DualSense">
  <title>DualSense — mapa de peças, para editar</title>
{ESTILO}
  <rect id="fundo" x="-100" y="-100" width="400" height="400" fill="#21222c"/>
{chr(10).join(corpo)}
</svg>
''')
n_g = len(corpo)
n_p = sum(len(p) for _, _, p in GRUPOS)
print(f"  ok  {SAIDA}")
print(f"      {n_g} grupos nomeados · {n_p} peças, cada uma com <title> em português")
