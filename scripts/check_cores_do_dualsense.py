#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PORTÃO — o desenho pinta a cor que o CSV manda, zona por zona?"""
from __future__ import annotations

import csv
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from gerar_cores_do_dualsense import (
    GLIFOS_DA_FACE,
    NAO_MEDIDA,
    ZONAS_DA_CASCA,
    ZONAS_DE_SUPERFICIE,
    ZONAS_SEM_ALVO,
    legivel,
)
from hefesto_dualsense4unix.core.led_control import (
    player_led_pattern,
    player_slot_color,
)

SVG = RAIZ / "assets/control-svg/dualsense.svg"
from hefesto_dualsense4unix.interface import onde

MAPA = onde.PUBLICADO / "mapa-do-controle.html"
CSV_CORES = RAIZ / "docs/data/cores-do-dualsense.csv"
CSV_PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"

AMOSTRA = [
    ("white", "hex sólido, o mais claro"),
    ("midnight-black", "os dois pretos: casca e painel a 10 valores"),
    ("cosmic-red", "casca colorida com painel preto — o caso que o SVG errava"),
    ("spider-man-2", "casca PARTIDA: metade preta, metade vermelha"),
    ("chroma-teal", "SEM-HEX: iridescente não cabe num fill"),
    ("marathon", "zonas sem amostragem"),
]

falhas: list[str] = []


def diz(ok: bool, texto: str) -> None:
    print(("  OK   " if ok else "  FALHA") + " " + texto)
    if not ok:
        falhas.append(texto)


def le(caminho: pathlib.Path) -> list[dict[str, str]]:
    linhas = [x for x in caminho.read_text().splitlines()
              if x and not x.startswith("#")]
    return list(csv.DictReader(linhas))


print("=== régua 1 · a leitura — os CSV e o texto do SVG ===")

pecas = le(CSV_PECAS)
cores = le(CSV_CORES)
svg = SVG.read_text()

zonas_de_peca = {p["zona"] for p in pecas} - {"-", "luz", ""}
zonas_de_cor = {c["zona"] for c in cores}

orfas = sorted(zonas_de_cor - zonas_de_peca - set(ZONAS_SEM_ALVO)
               - set(ZONAS_DA_CASCA) - {"simbolos"})
diz(not orfas, f"toda zona de cor tem peça, ou está declarada sem alvo — órfãs: {orfas}")

inventadas = sorted(zonas_de_peca - zonas_de_cor - {"casca"})
diz(not inventadas, f"nenhuma peça aponta para zona que as cores não conhecem — {inventadas}")

sem_classe = []
for p in pecas:
    if p["zona"] in ("-", "luz", "") or p["no_svg"] in ("falta", ""):
        continue
    m = re.search(rf'<g\b[^>]*\bid="{re.escape(p["no_svg"])}"[^>]*>', svg)
    if not m or f'z-{p["zona"]}' not in m.group(0):
        sem_classe.append(p["id"])
diz(not sem_classe, f"toda peça de plástico tem class=\"z-<zona>\" no SVG — sem: {sem_classe}")

glifos_sem = [g for g in GLIFOS_DA_FACE
              if not (m := re.search(rf'<g\b[^>]*\bid="{g}"[^>]*>', svg))
              or "z-simbolos" not in m.group(0)]
diz(not glifos_sem, f"os quatro glifos da face têm z-simbolos — sem: {glifos_sem}")

luz_pintada = []
for p in pecas:
    if p["zona"] != "luz":
        continue
    m = re.search(rf'<g\b[^>]*\bid="{re.escape(p["no_svg"])}"[^>]*>', svg)
    if m and "z-" in m.group(0):
        luz_pintada.append(p["id"])
diz(not luz_pintada, f"a luz não recebe zona de plástico — recebeu: {luz_pintada}")

DIGITADOS = ("#b11f54", "#B11F54", "#ec429d", "#EC429D", "#4c319d", "#4C319D")


def so_o_codigo(texto: str) -> str:
    """O texto sem o que EXPLICA — comentário e docstring não são uso."""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r'"""(?:.|\n)*?"""', "", texto)
    texto = re.sub(r"<!--(?:.|\n)*?-->", "", texto)
    return "\n".join(x for x in texto.splitlines() if not x.lstrip().startswith("#"))


sujos = []
for arq in (RAIZ / "src/hefesto_dualsense4unix/interface/mapa.py",
            RAIZ / "src/hefesto_dualsense4unix/interface/monta.py",
            RAIZ / "src/hefesto_dualsense4unix/interface/exportar.py",
            RAIZ / "src/hefesto_dualsense4unix/interface/topo.html"):
    txt = so_o_codigo(arq.read_text())
    for h in DIGITADOS:
        if h in txt:
            sujos.append(f"{arq.name}:{h}")
diz(not sujos, f"nenhum hex de plástico digitado nos geradores do mockup — {sujos}")

sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
import monta

velhas = []
for arq in (RAIZ / "src/hefesto_dualsense4unix/interface/topo.html",
            RAIZ / "src/hefesto_dualsense4unix/interface/paginas/01-jogar.html"):
    txt = arq.read_text()
    for nome, colorway in monta.PLASTICOS_DO_ESQUELETO.items():
        m = re.search(rf"--{nome}:(#[0-9a-fA-F]{{6}})", txt)
        certo = monta.cor_da_zona(colorway)
        if m and m.group(1).lower() != certo.lower():
            velhas.append(f"{arq.name}:--{nome}={m.group(1)} (é {certo})")
diz(not velhas, f"as cores do esqueleto batem com o desenho — velhas: {velhas}")

# 1f-ter. TODO `--plastico` DIGITADO NA `01-jogar.html` É UMA COR DA MESA.
da_mesa = {monta.cor_da_zona(c["cor"]).lower() for c in monta.MESA}
jogar = (RAIZ / "src/hefesto_dualsense4unix/interface/paginas/01-jogar.html").read_text()
forasteiras = sorted({h.lower() for h in re.findall(r"--plastico:\s*(#[0-9a-fA-F]{6})", jogar)}
                     - da_mesa)
diz(not forasteiras,
    f"todo --plastico da 01-jogar é uma cor da MESA — fora: {forasteiras}")

r = subprocess.run([sys.executable, str(RAIZ / "scripts/gerar_cores_do_dualsense.py"),
                    "--check"], capture_output=True, text=True)
diz(r.returncode == 0, "o SVG no disco é o que os CSV geram (gerador --check)")
if r.returncode != 0:
    print("    " + r.stdout.strip().replace("\n", "\n    "))

mal = [f'{c["id"]}/{c["zona"]}' for c in cores
       if (c["grau"] == "SEM-HEX") != (not c["hex"].strip())]
diz(not mal, f"SEM-HEX é sem hex, e hex declarado tem cor — fora: {mal}")
torto = [f'{c["id"]}/{c["zona"]}' for c in cores
         if c["hex"].strip() and not re.fullmatch(r"#[0-9A-Fa-f]{6}", c["hex"].strip())]
diz(not torto, f"todo hex tem seis dígitos — fora: {torto}")

por_modelo_sem_hex: dict[str, list[str]] = {}
for c in cores:
    if c["grau"] == "SEM-HEX":
        por_modelo_sem_hex.setdefault(c["id"], []).append(c["nota"].strip())
mudos = sorted(k for k, v in por_modelo_sem_hex.items() if not any(v))
diz(not mudos, f"todo modelo SEM-HEX traz a receita em alguma linha — mudos: {mudos}")


print("\n=== régua 2 · a pintura — o computado no navegador ===")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("  FALHA playwright ausente — a régua da pintura não pode rodar")
    sys.exit(1)

por_modelo: dict[str, dict[str, dict[str, str]]] = {}
for c in cores:
    por_modelo.setdefault(c["id"], {})[c["zona"]] = c

AMOSTRA_DE_PECA = {
    "casca": "#mp-corpo", "painel": "#mp-alto-falante", "touch": "#mp-touchpad",
    "gatilhos": "#mp-l1", "dpad": "#mp-dpad_up", "analogicos": "#mp-stick_l",
    "botoes_face": "#mp-triangle",
}


def para_rgb(hexa: str) -> str:
    h = hexa.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    erros: list[str] = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.goto(f"file://{MAPA}")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(400)

    diz(not erros, f"o mapa abre sem exceção de JavaScript — {erros[:3]}")

    for mid, porque in AMOSTRA:
        pg.select_option("#cw", mid)
        pg.wait_for_timeout(150)
        zonas = por_modelo[mid]
        erradas = []
        for zona, sel in AMOSTRA_DE_PECA.items():
            chave = "casca_esq" if zona == "casca" else zona
            linha = zonas.get(chave)
            visto = pg.evaluate(
                f"()=>{{const e=document.querySelector({sel!r}+' :is(path,rect,circle,ellipse)');"
                "return e?getComputedStyle(e).fill:null}")
            if linha is None:
                esperado = para_rgb(legivel(NAO_MEDIDA))
                bate = visto == esperado
            elif linha["grau"] == "SEM-HEX":
                esperado = "a hachura"
                bate = bool(visto and "hachura-sem-hex" in visto)
            elif zona == "casca" and zonas.get("casca_dir") is not None and \
                    zonas["casca_dir"]["hex"] != linha["hex"]:
                esperado = "o gradiente da casca partida"
                bate = bool(visto and f"casca-{mid}" in visto)
            else:
                esperado = para_rgb(legivel(linha["hex"]))
                bate = visto == esperado
            if not bate:
                erradas.append(f"{zona}: esperava {esperado}, veio {visto}")
        diz(not erradas, f"{mid:16} pinta o que o CSV manda ({porque})")
        for e in erradas:
            print(f"         {e}")

    pg.click('[data-jogador="2"]')
    pg.wait_for_timeout(150)
    antes = pg.evaluate("()=>getComputedStyle(document.querySelector('#mp-lightbar *')).fill")
    pg.select_option("#cw", "white")
    pg.wait_for_timeout(150)
    depois = pg.evaluate("()=>getComputedStyle(document.querySelector('#mp-lightbar *')).fill")
    diz(antes == depois == para_rgb("#%02x%02x%02x" % player_slot_color(2)),
        f"a barra de luz não muda com o plástico — {antes} -> {depois}")

    for n in (1, 2, 3, 4):
        pg.click(f'[data-jogador="{n}"]')
        pg.wait_for_timeout(120)
        acesos = pg.evaluate(
            "()=>[1,2,3,4,5].filter(i=>document.querySelector('#mp-led-jogador-'+i)"
            ".classList.contains('led-on'))")
        canonico = [i + 1 for i, on in enumerate(player_led_pattern(n)) if on]
        luz = pg.evaluate("()=>getComputedStyle(document.querySelector('#mp-lightbar *')).fill")
        diz(acesos == canonico and luz == para_rgb("#%02x%02x%02x" % player_slot_color(n)),
            f"jogador {n}: lâmpadas {acesos} (canônico {canonico}) e barra {luz}")

    pg.click('[data-jogador="0"]')
    pg.wait_for_timeout(120)
    apagou = pg.evaluate(
        "()=>[1,2,3,4,5].every(i=>!document.querySelector('#mp-led-jogador-'+i)"
        ".classList.contains('led-on'))")
    diz(apagou, "o 'nenhum' apaga as cinco lâmpadas")

    n_op = pg.evaluate("()=>document.querySelectorAll('#cw option').length")
    diz(n_op == len(por_modelo), f"o dropdown lista os {len(por_modelo)} modelos — tem {n_op}")

    marcados = set(pg.evaluate(
        "()=>[...document.querySelectorAll('#cw option[data-parcial]')].map(o=>o.value)"))
    devem = {mid for mid, z in por_modelo.items()
             if any(x["grau"] == "SEM-HEX" for x in z.values())
             or any(k not in z for k in
                    [x for x in ZONAS_DE_SUPERFICIE if x != "casca"] + list(ZONAS_DA_CASCA))}
    diz(marcados == devem,
        f"os {len(devem)} modelos sem hex puro estão marcados na lista — "
        f"faltam {sorted(devem - marcados)}, sobram {sorted(marcados - devem)}")

    b.close()

print()
sys.exit(1 if falhas else 0)
