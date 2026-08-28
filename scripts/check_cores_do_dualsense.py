#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PORTÃO — o desenho pinta a cor que o CSV manda, zona por zona?

Irmão do `check_pecas_do_dualsense.py`: aquele confere que o NOME da peça bate
com o LUGAR dela; este confere que a COR bate com o dado.

O defeito que ele existe para pegar (27/08/2026): as cinco cores que o produto
conhecia eram CSS escrito à mão, numa zona só. **Nenhuma régua sabia dizer se o
hex ali estava certo, porque não havia com o que comparar** — o Cosmic Red do
desenho era `#b11f54` e a amostragem devolveu `#A51C48`, uma distância de 17 que
atravessou o projeto inteiro sem ninguém ter como ver.

DUAS RÉGUAS INDEPENDENTES, e é de propósito — é regra desta casa, e nasceu de
portão que mediu o lugar errado e deu verde:

  1. **A LEITURA**  — os CSV e o texto do SVG, sem navegador nenhum. Pega a peça
     sem zona, a zona sem peça, e o gerador que não rodou depois do `importar.py`.
  2. **A PINTURA**  — o Chrome, com o `getComputedStyle` de cada peça em cada
     colorway. Pega o que a leitura não pode pegar: seletor que não alcança,
     `!important` que perdeu a disputa, style inline que venceu a folha.

A segunda existe porque a primeira é cega para o que o NAVEGADOR faz. O
`share`, o `options` e o `mic` trazem a cor dentro do `style` inline, e style
inline vence qualquer folha: a leitura veria a regra escrita e diria "certo",
enquanto a tela mostrava carmim no White.

    scripts/check_cores_do_dualsense.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from gerar_cores_do_dualsense import (  # noqa: E402
    GLIFOS_DA_FACE,
    NAO_MEDIDA,
    ZONAS_DA_CASCA,
    ZONAS_DE_SUPERFICIE,
    ZONAS_SEM_ALVO,
    legivel,
)
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402
    player_led_pattern,
    player_slot_color,
)

SVG = RAIZ / "assets/control-svg/dualsense.svg"
MAPA = RAIZ / "novo-layout/mapa-do-controle.html"
CSV_CORES = RAIZ / "docs/data/cores-do-dualsense.csv"
CSV_PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"

#: Os colorways que a régua da PINTURA percorre. Não são os 28: cada um custa
#: uma repintura e uma varredura, e o que importa é cobrir cada FORMA de resposta
#: — hex sólido, dois pretos que quase colidem, casca partida em duas, hachura de
#: SEM-HEX, e zona sem amostragem. Os 28 estão cobertos pela régua da leitura,
#: que os percorre inteiros.
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


# ===========================================================================
# RÉGUA 1 — A LEITURA. Os CSV e o texto do SVG, sem navegador.
# ===========================================================================
print("=== régua 1 · a leitura — os CSV e o texto do SVG ===")

pecas = le(CSV_PECAS)
cores = le(CSV_CORES)
svg = SVG.read_text()

zonas_de_peca = {p["zona"] for p in pecas} - {"-", "luz", ""}
zonas_de_cor = {c["zona"] for c in cores}

# 1a. Toda zona do CSV de cores é pintável, ou está declarada sem alvo.
orfas = sorted(zonas_de_cor - zonas_de_peca - set(ZONAS_SEM_ALVO)
               - set(ZONAS_DA_CASCA) - {"simbolos"})
diz(not orfas, f"toda zona de cor tem peça, ou está declarada sem alvo — órfãs: {orfas}")

# 1b. E o contrário: nenhuma peça aponta para uma zona que o CSV de cores ignora.
inventadas = sorted(zonas_de_peca - zonas_de_cor - {"casca"})
diz(not inventadas, f"nenhuma peça aponta para zona que as cores não conhecem — {inventadas}")

# 1c. Toda peça de plástico carrega a classe da zona dela NO DESENHO. É esta
#     asserção que pega o caso real: ela reimporta o desenho do editor, o
#     `importar.py` substitui o bloco `<g>` inteiro, e a classe some junto.
sem_classe = []
for p in pecas:
    if p["zona"] in ("-", "luz", "") or p["no_svg"] in ("falta", ""):
        continue
    m = re.search(rf'<g\b[^>]*\bid="{re.escape(p["no_svg"])}"[^>]*>', svg)
    if not m or f'z-{p["zona"]}' not in m.group(0):
        sem_classe.append(p["id"])
diz(not sem_classe, f"toda peça de plástico tem class=\"z-<zona>\" no SVG — sem: {sem_classe}")

# 1d. Os quatro glifos da face carregam `z-simbolos`. Eles não são peça, e por
#     isso não entram no laço acima — mas a impressão dos botões é uma zona, e
#     no 30th Anniversary ela é a única coisa que separa o modelo do White.
glifos_sem = [g for g in GLIFOS_DA_FACE
              if not (m := re.search(rf'<g\b[^>]*\bid="{g}"[^>]*>', svg))
              or "z-simbolos" not in m.group(0)]
diz(not glifos_sem, f"os quatro glifos da face têm z-simbolos — sem: {glifos_sem}")

# 1e. A LUZ NÃO É PLÁSTICO. O lightbar e as cinco lâmpadas não podem carregar
#     zona de cor: pintados na cor do casco eles caem sobre a borda do touchpad
#     e somem — está medido, e é por isso que a coluna `zona` os marca como `luz`.
luz_pintada = []
for p in pecas:
    if p["zona"] != "luz":
        continue
    m = re.search(rf'<g\b[^>]*\bid="{re.escape(p["no_svg"])}"[^>]*>', svg)
    if m and "z-" in m.group(0):
        luz_pintada.append(p["id"])
diz(not luz_pintada, f"a luz não recebe zona de plástico — recebeu: {luz_pintada}")

# 1f. Nenhum hexadecimal de plástico continua digitado nas ferramentas. É a
#     duplicata que o gerador existe para matar: enquanto ela viver, o hex do
#     desenho e o do CSV podem divergir de novo sem ninguém ver.
#     COMENTÁRIO NÃO É USO, e a distinção é a diferença entre régua e ruído: a
#     primeira versão desta linha reprovou o próprio comentário que EXPLICA por
#     que o `#b11f54` saiu dali. Régua que reprova a explicação da cura ensina a
#     apagar a explicação — que é o oposto do que esta casa quer.
DIGITADOS = ("#b11f54", "#B11F54", "#ec429d", "#EC429D", "#4c319d", "#4C319D")


def so_o_codigo(texto: str) -> str:
    """O texto sem o que EXPLICA — comentário e docstring não são uso.

    A distinção é a diferença entre régua e ruído: a primeira versão desta linha
    reprovou o próprio comentário que explica por que o `#b11f54` saiu dali.
    Régua que reprova a explicação da cura ensina a apagar a explicação.
    """
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)          # comentário CSS
    texto = re.sub(r'"""(?:.|\n)*?"""', "", texto)               # docstring Python
    texto = re.sub(r"<!--(?:.|\n)*?-->", "", texto)              # comentário HTML
    return "\n".join(x for x in texto.splitlines() if not x.lstrip().startswith("#"))


sujos = []
for arq in (RAIZ / "novo-layout/_ferramentas/mapa.py",
            RAIZ / "novo-layout/_ferramentas/monta.py",
            RAIZ / "novo-layout/_ferramentas/exportar.py",
            RAIZ / "novo-layout/_ferramentas/topo.html"):
    txt = so_o_codigo(arq.read_text())
    for h in DIGITADOS:
        if h in txt:
            sujos.append(f"{arq.name}:{h}")
diz(not sujos, f"nenhum hex de plástico digitado nos geradores do mockup — {sujos}")

# 1f-bis. AS VARIÁVEIS DE PLÁSTICO DO ESQUELETO BATEM COM O DESENHO. Elas são
#     geradas por `monta.py` a cada `abaNN.py`, mas a `01-jogar.html` é escrita à
#     mão e NÃO passa por ele — sem esta régua, ela mostra a cor velha para
#     sempre, e a 01 é o esqueleto do qual as outras nove nascem.
sys.path.insert(0, str(RAIZ / "novo-layout/_ferramentas"))
import monta  # noqa: E402

velhas = []
for arq in (RAIZ / "novo-layout/_ferramentas/topo.html",
            RAIZ / "novo-layout/01-jogar.html"):
    txt = arq.read_text()
    for nome, colorway in monta.PLASTICOS_DO_ESQUELETO.items():
        m = re.search(rf"--{nome}:(#[0-9a-fA-F]{{6}})", txt)
        certo = monta.cor_da_zona(colorway)
        if m and m.group(1).lower() != certo.lower():
            velhas.append(f"{arq.name}:--{nome}={m.group(1)} (é {certo})")
diz(not velhas, f"as cores do esqueleto batem com o desenho — velhas: {velhas}")

# 1f-ter. TODO `--plastico` DIGITADO NA `01-jogar.html` É UMA COR DA MESA.
#     A 01 é o único mockup mantido à mão — as outras nove saem do `abaNN.py`, e
#     nelas a cor vem de `monta.cor_da_zona()`. Na 01 ela é digitada, oito vezes
#     (o chip da fita e o cartão de cada um dos quatro), e **nenhum portão olhava
#     para lá**: a régua de hex digitado lê `mapa.py`, `monta.py`, `exportar.py` e
#     `topo.html`. É o mesmo caminho por onde o Cosmic Red virou `#b11f54` e
#     ninguém tinha como ver. Achado pela conferência das dez abas, 27/08.
da_mesa = {monta.cor_da_zona(c["cor"]).lower() for c in monta.MESA}
jogar = (RAIZ / "novo-layout/01-jogar.html").read_text()
forasteiras = sorted({h.lower() for h in re.findall(r"--plastico:\s*(#[0-9a-fA-F]{6})", jogar)}
                     - da_mesa)
diz(not forasteiras,
    f"todo --plastico da 01-jogar é uma cor da MESA — fora: {forasteiras}")

# 1g. O gerado bate com o disco. Sem isto, editar o CSV e esquecer de gerar passa.
r = subprocess.run([sys.executable, str(RAIZ / "scripts/gerar_cores_do_dualsense.py"),
                    "--check"], capture_output=True, text=True)
diz(r.returncode == 0, "o SVG no disco é o que os CSV geram (gerador --check)")
if r.returncode != 0:
    print("    " + r.stdout.strip().replace("\n", "\n    "))

# 1h. SEM-HEX não tem hexadecimal, e o contrário também: hex declarado tem forma
#     de hex. Uma linha `SEM-HEX` com cor dentro seria a cor inventada que o
#     cabeçalho do CSV proíbe com todas as letras.
mal = [f'{c["id"]}/{c["zona"]}' for c in cores
       if (c["grau"] == "SEM-HEX") != (not c["hex"].strip())]
diz(not mal, f"SEM-HEX é sem hex, e hex declarado tem cor — fora: {mal}")
torto = [f'{c["id"]}/{c["zona"]}' for c in cores
         if c["hex"].strip() and not re.fullmatch(r"#[0-9A-Fa-f]{6}", c["hex"].strip())]
diz(not torto, f"todo hex tem seis dígitos — fora: {torto}")

# 1i. Todo MODELO com zona SEM-HEX diz POR QUÊ, em pelo menos uma das linhas
#     dela. Sem a receita, quem for medir não sabe se é iridescente, camuflado ou
#     arte — e a receita é o que impede a invenção do hex.
#
#     RÉGUA CORRIGIDA. A primeira versão exigia a nota em TODA linha SEM-HEX, e
#     reprovou 17 linhas sãs: o CSV escreve a receita UMA vez, na primeira zona
#     do modelo, e deixa as irmãs vazias — a mesma convenção que o White usa para
#     o `casca_dir`. A receita é do ACABAMENTO, não da zona. Régua que nasce
#     falsa é a cicatriz mais cara desta casa; esta mordeu o dado certo antes de
#     alguém acreditar nela.
por_modelo_sem_hex: dict[str, list[str]] = {}
for c in cores:
    if c["grau"] == "SEM-HEX":
        por_modelo_sem_hex.setdefault(c["id"], []).append(c["nota"].strip())
mudos = sorted(k for k, v in por_modelo_sem_hex.items() if not any(v))
diz(not mudos, f"todo modelo SEM-HEX traz a receita em alguma linha — mudos: {mudos}")


# ===========================================================================
# RÉGUA 2 — A PINTURA. O Chrome, que é onde a cor de verdade acontece.
# ===========================================================================
print("\n=== régua 2 · a pintura — o computado no navegador ===")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("  FALHA playwright ausente — a régua da pintura não pode rodar")
    sys.exit(1)

por_modelo: dict[str, dict[str, dict[str, str]]] = {}
for c in cores:
    por_modelo.setdefault(c["id"], {})[c["zona"]] = c

#: uma peça representante por zona, para não varrer 28 × 233
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

    # 2a. O CONSOLE LIMPO. Cicatriz de 27/08: o script do banco de provas nasceu
    #     ao lado dos controles, ANTES do desenho existir no DOM, e quebrou
    #     inteiro — 14 exceções de `reading 'dataset'`. A página parecia sã: o
    #     dropdown estava lá, só não fazia nada. Régua que não lê o console não
    #     pega isso, e foi por isso que ela entrou aqui.
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
                # A COR ESPERADA É A LEGÍVEL, não a crua — e a régua chama a
                # MESMA função que o gerador. Digitar o valor ajustado aqui seria
                # a segunda verdade: no dia em que o piso de contraste mudasse, a
                # régua continuaria exigindo o número velho e reprovaria a cura.
                esperado = para_rgb(legivel(linha["hex"]))
                bate = visto == esperado
            if not bate:
                erradas.append(f"{zona}: esperava {esperado}, veio {visto}")
        diz(not erradas, f"{mid:16} pinta o que o CSV manda ({porque})")
        for e in erradas:
            print(f"         {e}")

    # 2b. A LUZ NÃO MUDA COM O PLÁSTICO. Se o lightbar acompanhasse o casco, um
    #     controle White teria a barra branca — e a barra é o que diz o jogador.
    pg.click('[data-jogador="2"]')
    pg.wait_for_timeout(150)
    antes = pg.evaluate("()=>getComputedStyle(document.querySelector('#mp-lightbar *')).fill")
    pg.select_option("#cw", "white")
    pg.wait_for_timeout(150)
    depois = pg.evaluate("()=>getComputedStyle(document.querySelector('#mp-lightbar *')).fill")
    diz(antes == depois == para_rgb("#%02x%02x%02x" % player_slot_color(2)),
        f"a barra de luz não muda com o plástico — {antes} -> {depois}")

    # 2c. O PADRÃO DAS LÂMPADAS É O DO PRODUTO, e não uma tabela digitada no
    #     mockup. O `monta.py` tinha uma cópia com o jogador 3 escrito "234"
    #     quando o canônico é "135" — as duas pontas e o centro. `1 | vão | 3 |
    #     vão | 1`: as cinco NÃO são igualmente espaçadas, e o jogador 1 é a
    #     lâmpada CENTRAL.
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

    # 2d. E o apagado apaga. Estado que não volta ensina que a tela travou.
    pg.click('[data-jogador="0"]')
    pg.wait_for_timeout(120)
    apagou = pg.evaluate(
        "()=>[1,2,3,4,5].every(i=>!document.querySelector('#mp-led-jogador-'+i)"
        ".classList.contains('led-on'))")
    diz(apagou, "o 'nenhum' apaga as cinco lâmpadas")

    # 2e. O DROPDOWN TEM OS 28. Cinco eram o que o desenho conhecia; o CSV tem 28,
    #     e um dropdown com menos é a lista velha com cara de nova.
    n_op = pg.evaluate("()=>document.querySelectorAll('#cw option').length")
    diz(n_op == len(por_modelo), f"o dropdown lista os {len(por_modelo)} modelos — tem {n_op}")

    # 2f. E MARCA os que não pintam por hexadecimal. Sem a marca, ela clica no
    #     Chroma Teal, vê hachura, e conclui que o desenho quebrou.
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
