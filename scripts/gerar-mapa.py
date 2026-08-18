#!/usr/bin/env python3
"""gerar-mapa.py — constrói specs.html a partir de docs/data/mapa-controles.csv.

O artefato é AUTOCONTIDO de propósito: um arquivo, zero requisição de rede,
zero CDN, zero fonte web. Abre com duplo clique, funciona sem servidor, sem
venv e sem internet — inclusive no PC novo, que é para onde este mapa está
sendo feito. Por isso a tipografia usa a pilha do sistema em vez de baixar
JetBrains Mono: uma fonte que não carrega transforma um instrumento numa
página quebrada, e um instrumento que só funciona com rede não serve para
depurar rádio.

Os três SVG entram INLINE, não por <img>: só assim o hover de uma peça pode
acender a linha da tabela, que é o que faz o mapa ser mapa e não planilha.

O GRÃO É (chave, controle)
--------------------------
Desde a migração v2 (scripts/migrar-mapa-v2.py), uma feature de um controle é
UMA linha, com o cabo e o rádio lado a lado. Ordenado por `chave`, cada feature
é um bloco de três linhas adjacentes, uma por controle — e a tabela desenha esse
bloco, para a comparação entre os três aparelhos ser de olhar, não de procurar.

Duas coisas que este arquivo deixou de fazer, porque agora são DADO:
- a máscara que adivinhava a peça do desenho a partir do texto da feature virou
  a coluna `peca`, resolvida uma vez e conferida contra os ids que cada SVG
  realmente tem;
- o código evdev virou a coluna `evdev`, lida do `data-evdev` dos desenhos.

O `--check` PERGUNTA PELO CONTEÚDO, NÃO PELO RELÓGIO
----------------------------------------------------
Ele regenera a página em memória e compara com o `specs.html` em disco. A
versão anterior comparava MTIME, e mtime deu verde falso das duas maneiras
possíveis (medido em 12/08/2026):

- por OMISSÃO: a lista de fontes trazia o CSV, os três desenhos e este
  arquivo — e não trazia `docs/data/ensaios.csv`, que alimenta o HTML desde o
  caderno de eliminação. Editar o caderno nunca fazia o `--check` reclamar, e
  o `specs.html` publicado mostrava a lightbar como "os ensaios se
  contradizem" enquanto o caderno do mesmo commit já tinha o culpado isolado;
- por RELÓGIO: qualquer ferramenta que TOQUE o HTML depois da geração o deixa
  "mais novo" que as fontes (o `--fix` do `scripts/validar-acentuacao.py`
  reescreve arquivos), e no CI o `actions/checkout` escreve a árvore em ordem
  de caminho — `specs.html` (raiz) nasce depois de `docs/` e de `scripts/`, e
  o `--check` passava SEMPRE, qualquer que fosse o conteúdo.

Comparar conteúdo responde a pergunta certa — *a página publicada é a que
estas fontes produzem?* — e vale igual na máquina de quem edita e no runner.
Duas coisas são normalizadas antes da comparação, e só duas: o espaço no FIM
da linha (a saída do gerador tem ~20 linhas com espaço sobrando dentro dos
`<style>` herdados dos SVG, que alguma ferramenta apara depois) e a hora da
geração no selo do rodapé, que é a única parte da página que não vem do dado.

Uso:
    python3 scripts/gerar-mapa.py            # escreve specs.html na raiz
    python3 scripts/gerar-mapa.py --check    # o publicado bate com as fontes?
"""
from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eliminacao  # o caderno de eliminação de suspeitos

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "docs" / "data" / "mapa-controles.csv"
SAIDA = RAIZ / "specs.html"
SVGS = {
    "dualsense": RAIZ / "assets" / "control-svg" / "dualsense.svg",
    "pro": RAIZ / "assets" / "control-svg" / "nintendo-pro.svg",
    "sn30": RAIZ / "assets" / "control-svg" / "8bitdo-sn30-pro.svg",
}
ROTULO = {
    "dualsense": "DualSense",
    "pro": "Nintendo Pro",
    "sn30": "8BitDo SN30 Pro",
}
MODELO = {
    "dualsense": "Sony · 054c:0ce6",
    "pro": "Nintendo · 057e:2009",
    "sn30": "8BitDo · 057e:2009 (modo Switch)",
}
LADOS = (("cabo", "cabo_"), ("radio", "radio_"))

#: TUDO o que entra na página. O caderno de ensaios está aqui porque ELE ENTRA
#: (`le_csv` o lê via `eliminacao.carrega_por_lado`) — a lista anterior o
#: esquecia, e essa omissão é metade do verde falso que o `--check` dava. Hoje
#: a lista não decide nada sozinha (quem decide é a comparação de conteúdo):
#: ela é o que o erro mostra a quem precisa saber o que regerar.
FONTES = (CSV, eliminacao.ENSAIOS, *SVGS.values())


def svg_inline(caminho: Path, controle: str) -> str:
    """Injeta o SVG prefixando TODO id com o controle.

    Sem o prefixo a página quebra de um jeito silencioso e convincente: os três
    desenhos trazem os mesmos ids da norma (`corpo`, `stick_l`, `touchpad`...)
    para o espaço global do documento, e o `<tbody id="mp-corpo">` da tabela perde
    a disputa para o `<g id="mp-corpo">` do primeiro SVG — que aparece antes. O
    resultado medido: `document.getElementById('mp-corpo')` devolvia o CORPO DO
    DESENHO, as linhas eram escritas dentro dele, e a tabela ficava vazia
    sem um único erro de JavaScript. Prefixar resolve a colisão com a página e
    a colisão entre os três desenhos de uma vez.
    """
    bruto = caminho.read_text(encoding="utf-8")
    bruto = re.sub(r"<\?xml[^>]*\?>", "", bruto)
    bruto = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)   # os comentários da norma
    bruto = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{controle}__{m.group(1)}"', bruto)
    bruto = re.sub(r'\b(href|xlink:href)="#([^"]+)"',
                   lambda m: f'{m.group(1)}="#{controle}__{m.group(2)}"', bruto)
    bruto = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{controle}__{m.group(1)})", bruto)
    bruto = bruto.replace("<svg ", f'<svg data-ctrl="{controle}" ', 1)
    return bruto.strip()


def ids_do_svg(caminho: Path) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', caminho.read_text(encoding="utf-8")))


def caderno_de(ens: list[dict]) -> dict:
    """O veredicto de eliminação de UM lado (cabo ou rádio) de uma linha."""
    estado, agora = eliminacao.estado_da_linha(ens)
    return {
        "estado": estado,
        "agora": agora,
        "n": len(ens),
        "suspeitos": [
            {"suspeito": j.suspeito, "veredicto": j.veredicto, "n": j.ensaios,
             "com": j.com, "sem": j.sem, "falta": j.proximo_ensaio}
            for j in eliminacao.julga_linha(ens)
        ],
        "poda": [{"suspeito": pd.suspeito, "n": pd.ensaios, "resultado": pd.resultado}
                 for pd in eliminacao.podaveis(ens)],
        "ensaios": [
            {"quando": e["quando"][:16].replace("T", " "), "suspeito": e["suspeito"],
             "presente": e["presente"], "resultado": e["resultado"], "nota": e.get("nota", "")}
            for e in ens
        ],
    }


def pecas_orfas(linhas: list[dict]) -> list[tuple[str, str, list[str]]]:
    """As peças que o CSV cita e o desenho não tem mais. UMA régua, dois donos.

    Devolve `(controle, chave, ids que sumiram)`. Quem chama são `le_csv` (para
    dizer em stderr) e `main` (para REPROVAR) — de propósito a mesma função, e
    não duas contagens parecidas: nesta casa duas réguas para o mesmo dado é a
    forma como uma delas envelhece calada.

    O que uma órfã significa: a peça é o alvo que o `specs.html` acende no
    desenho quando a pessoa clica na linha. Um id que sumiu do SVG não acende
    nada, e não acende EM SILÊNCIO — foi assim que 67 alvos apontaram para ids
    inexistentes na versão anterior do mapa sem um único erro visível.
    """
    presentes = {c: ids_do_svg(p) for c, p in SVGS.items()}
    orfas = []
    for lin in linhas:
        tem = presentes.get(lin["controle"], set())
        faltando = [i for i in lin["peca"].split() if i not in tem]
        if faltando:
            orfas.append((lin["controle"], lin["chave"], faltando))
    return orfas


def reclama_das_orfas(orfas: list[tuple[str, str, list[str]]]) -> None:
    """Diz, uma por linha, qual peça sumiu de qual desenho."""
    print(f"  {len(orfas)} linha(s) com peça que sumiu do desenho:", file=sys.stderr)
    for c, ch, faltando in orfas:
        print(f"    {c}: {ch} pede {' '.join(faltando)}", file=sys.stderr)


def reprova_por_orfas(orfas: list[tuple[str, str, list[str]]]) -> bool:
    """PECA-ORFA-01 (13/08/2026) — a órfã deixa de ser aviso e vira reprovação.

    Até 13/08 as órfãs eram acumuladas, impressas em stderr como "aviso", e o
    processo devolvia 0 — inclusive no `--check`, que é o passo do pre-commit e
    do CI. Ou seja: a única régua que confere o CSV contra os desenhos não
    reprovava nada, e um id que sumisse do SVG passaria por ela em silêncio.

    Medido na árvore em 13/08/2026: ZERO linhas órfãs nas 293 do mapa. Ligar a
    reprovação custou zero reprovações — o dia mais barato que existe para ligar.

    Devolve True quando há órfã (e então já disse por quê em stderr).
    """
    if not orfas:
        return False
    print("specs.html: PEÇA ÓRFÃ — o CSV cita id de desenho que sumiu do SVG",
          file=sys.stderr)
    reclama_das_orfas(orfas)
    print("conserte a coluna `peca` em docs/data/mapa-controles.csv, ou devolva "
          "o id ao desenho em " + ", ".join(sorted(str(p.relative_to(RAIZ))
                                                   for p in SVGS.values())),
          file=sys.stderr)
    return True


def le_csv(reclamar: bool = False) -> list[dict]:
    """Lê o CSV do v2 e confere a coluna `peca` contra os ids reais do desenho.

    Casar por texto e torcer produziria um mapa que parece funcionar e não
    acende nada — na versão anterior 67 alvos apontavam para ids inexistentes
    (`microfone` quando o desenho chama `mic`) sem um único erro visível. Agora
    a peça é dado, resolvido na migração; aqui ela é RECONFERIDA, porque um
    desenho pode ser reeditado depois e levar o id embora sem avisar ninguém.
    """
    presentes = {c: ids_do_svg(p) for c, p in SVGS.items()}
    cadernos = eliminacao.carrega_por_lado()
    with open(CSV, encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    for lin in linhas:
        tem = presentes.get(lin["controle"], set())
        lin["alvo"] = " ".join(i for i in lin["peca"].split() if i in tem)
        for lado, _ in LADOS:
            lin[f"elim_{lado}"] = caderno_de(cadernos.get((lin["id"], lado), []))
    if reclamar:
        orfas = pecas_orfas(linhas)
        if orfas:
            reclama_das_orfas(orfas)
    return linhas


def tem_lado(lin: dict, pref: str) -> bool:
    """Aquele transporte foi respondido para esta linha?"""
    return bool(lin[pref + "aceita"].strip())


def placar(linhas: list[dict], controle: str) -> dict:
    ls = [lin for lin in linhas if lin["controle"] == controle]

    def qualquer(lin, sufixo, *valores):
        return any(lin[p + sufixo] in valores for _, p in LADOS)

    return {
        "linhas": len(ls),
        "existe": sum(1 for lin in ls if lin["existe"] == "tem"),
        "medidas": sum(1 for lin in ls if qualquer(lin, "de_onde_sei", "medido")),
        "aciona": sum(1 for lin in ls if qualquer(lin, "aciona", "sim")),
        "lacuna": sum(1 for lin in ls if lin["existe"] == "tem"
                      and not qualquer(lin, "aciona", "sim")),
        "sem_linha": sum(1 for lin in ls if lin["transporte"] == "sem linha no v1"),
    }


def assimetrias(linhas: list[dict]) -> int:
    """Linhas cujo veredicto MUDA entre cabo e rádio.

    No v1 isto era uma junção por texto de feature, e 34 linhas não pareavam —
    entre elas assimetrias reais, que o contador da tela não estava vendo. Com o
    grão em (chave, controle) a conta é do próprio registro: os dois lados estão
    na mesma linha.
    """
    n = 0
    for lin in linhas:
        if not (tem_lado(lin, "cabo_") and tem_lado(lin, "radio_")):
            continue
        if (lin["cabo_aceita"], lin["cabo_aciona"]) != (lin["radio_aceita"], lin["radio_aciona"]):
            n += 1
    return n


TOKENS = """
:root {
  /* Paleta Drácula — a mesma que o produto usa em 82 lugares no código.
     O mapa tem de parecer parte do Hefesto, não um site sobre ele. */
  --color-paper:      #282a36;
  --color-paper-2:    #21222c;
  --color-paper-3:    #343746;
  --color-rule:       #44475a;
  --color-ink:        #f8f8f2;
  --color-ink-quiet:  #a8b0c8;
  --color-ink-faint:  #6272a4;
  --color-accent:     #bd93f9;   /* o literal que set_accent() já substitui */
  --color-ok:         #50fa7b;
  --color-lacuna:     #ffb86c;   /* a casa sabe e o produto não faz */
  --color-nulo:       #6272a4;
  --color-alerta:     #ff5555;
  --color-frio:       #8be9fd;

  /* Pilha do sistema: nada de fonte web, para o arquivo abrir sem rede. */
  --font-corpo: ui-sans-serif, system-ui, "Cantarell", "Segoe UI", Roboto, sans-serif;
  --font-dado:  ui-monospace, "JetBrains Mono", "Fira Mono", "DejaVu Sans Mono", monospace;

  --space-3xs: .25rem; --space-2xs: .5rem;  --space-xs: .75rem;
  --space-sm:  1rem;   --space-md:  1.5rem; --space-lg: 2.5rem;
  --space-xl:  4rem;   --space-2xl: 6rem;

  --text-xs: .75rem;  --text-sm: .8125rem; --text-base: .9375rem;
  --text-lg: 1.125rem; --text-xl: 1.5rem;  --text-2xl: 2rem;
  --text-display: clamp(2rem, 5vw, 3.25rem);

  --rule-hair: 1px;
  --radius-sm: 3px; --radius-md: 6px;
  --ease-out: cubic-bezier(.22,.61,.36,1);
  --dur-fast: 120ms; --dur-base: 200ms;
}
"""

ESTILO = """
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--color-paper); color: var(--color-ink);
  font-family: var(--font-corpo); font-size: var(--text-base); line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3 { font-style: normal; font-weight: 600; line-height: 1.15;
             overflow-wrap: anywhere; min-width: 0; margin: 0; }
a { color: var(--color-accent); }
:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.envelope { max-width: 1440px; margin: 0 auto; padding: 0 var(--space-md); }

/* ── N9 · nav alinhada às bordas ─────────────────────────────── */
.topo {
  display: flex; flex-wrap: wrap; gap: var(--space-sm);
  align-items: baseline; justify-content: space-between;
  padding: var(--space-md) 0; border-bottom: var(--rule-hair) solid var(--color-rule);
}
.topo h1 { font-size: var(--text-lg); letter-spacing: -.01em; }
.topo h1 b { color: var(--color-accent); font-weight: 600; }
.canal { display: flex; gap: var(--space-3xs); }
.canal button {
  font: inherit; font-size: var(--text-sm); color: var(--color-ink-quiet);
  background: none; border: var(--rule-hair) solid var(--color-rule);
  padding: var(--space-3xs) var(--space-xs); border-radius: var(--radius-sm);
  cursor: pointer; white-space: nowrap;
  transition: color var(--dur-fast) var(--ease-out),
              border-color var(--dur-fast) var(--ease-out);
}
.canal button:hover { color: var(--color-ink); border-color: var(--color-ink-faint); }
.canal button[aria-pressed="true"] {
  color: var(--color-paper); background: var(--color-accent);
  border-color: var(--color-accent); font-weight: 600;
}

/* ── orientação ──────────────────────────────────────────────── */
.orienta { padding: var(--space-lg) 0 var(--space-md); max-width: 62ch; }
.orienta p:first-child {
  font-size: var(--text-display); font-weight: 600; line-height: 1.05;
  letter-spacing: -.025em; margin: 0 0 var(--space-sm);
}
.orienta p:last-child { margin: 0; color: var(--color-ink-quiet); }

/* ── o mapa: três controles ──────────────────────────────────── */
.mapa {
  display: grid; gap: var(--space-md);
  grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
  padding-bottom: var(--space-lg);
}
.ctrl {
  display: flex; flex-direction: column; gap: var(--space-2xs);
  background: var(--color-paper-2); border: var(--rule-hair) solid var(--color-rule);
  border-radius: var(--radius-md); padding: var(--space-sm); cursor: pointer;
  text-align: left; font: inherit; color: inherit;
  transition: border-color var(--dur-base) var(--ease-out);
}
.ctrl:hover { border-color: var(--color-ink-faint); }
.ctrl[aria-pressed="true"] { border-color: var(--color-accent); }
/* Quadro de altura fixa: sem ele os três SVG têm proporções diferentes
   (2,09 / 1,39 / 1,49) e os rótulos desalinham em zigue-zague. */
.quadro { height: 150px; display: grid; place-items: center; }
.quadro svg { max-width: 100%; max-height: 100%; width: auto; height: auto; display: block; }

/* Os desenhos nasceram para fundo CLARO (o traço é #2f333c) e esta página é
   escura — sem esta inversão eles somem. Os seletores respeitam quem é
   preenchido e quem é traço: sobrescrever `fill` num path com fill="none"
   encheria a silhueta de tinta sólida. */
/* O seletor tem de exigir que o atributo EXISTA: `:not([fill="none"])` sozinho
   é VERDADEIRO para quem não declara fill nenhum — e os paths do 8BitDo
   herdam fill="none" do grupo, sem atributo próprio. A versão anterior
   preenchia de tinta sólida o que era contorno, e o desenho virava um borrão
   facetado. `[fill]:not([fill="none"])` só pega quem declara e declara cor. */
.ctrl svg .corpo[fill]:not([fill="none"]) { fill: var(--color-ink-quiet); }
.ctrl svg .corpo[stroke]:not([stroke="none"]) { stroke: var(--color-ink-quiet); }
.ctrl svg .peca[fill]:not([fill="none"])  { fill: var(--color-ink-faint); }
.ctrl svg .peca[stroke]:not([stroke="none"]) { stroke: var(--color-ink-faint); }
.ctrl svg > g[stroke] { stroke: var(--color-ink-quiet); }   /* 8BitDo: traço no grupo */
.ctrl:hover svg .corpo[fill]:not([fill="none"]) { fill: var(--color-ink); }
.ctrl:hover svg .corpo[stroke]:not([stroke="none"]) { stroke: var(--color-ink); }
.ctrl .nome { font-weight: 600; }
.ctrl .modelo { font-family: var(--font-dado); font-size: var(--text-xs);
                color: var(--color-ink-faint); }
.barra { display: flex; height: 5px; border-radius: 99px; overflow: hidden;
         background: var(--color-paper-3); margin-top: var(--space-3xs); }
.barra i { display: block; }
.barra .b-ok { background: var(--color-ok); }
.barra .b-lac { background: var(--color-lacuna); }
.placar { font-family: var(--font-dado); font-size: var(--text-xs);
          color: var(--color-ink-quiet); }
.placar b { color: var(--color-ink); font-weight: 600; }

/* peça acesa quando a linha correspondente é apontada */
svg .peca, svg .corpo, svg .luz { transition: fill var(--dur-fast) var(--ease-out),
                                              stroke var(--dur-fast) var(--ease-out); }
svg g.marcada > .peca { fill: var(--color-accent); }
svg g.marcada > path[stroke] { stroke: var(--color-accent); }
svg g.oculta.acesa { opacity: .95; }

/* ── legenda ─────────────────────────────────────────────────── */
.legenda { display: flex; flex-wrap: wrap; gap: var(--space-md);
           padding: var(--space-sm) 0; border-top: var(--rule-hair) solid var(--color-rule);
           font-size: var(--text-sm); color: var(--color-ink-quiet); }
.legenda span { display: flex; align-items: center; gap: var(--space-2xs); }
.sim { font-family: var(--font-dado); font-size: var(--text-lg); line-height: 1; }
.s-ok { color: var(--color-ok); } .s-lac { color: var(--color-lacuna); }
.s-nulo { color: var(--color-nulo); } .s-mudo { color: var(--color-rule); }

/* ── as duas perguntas (D-13, 15/08/2026) ────────────────────── */
.duas { padding: var(--space-sm) 0 0; font-size: var(--text-sm);
        color: var(--color-ink-quiet); max-width: 84ch; }
.duas p { margin: 0 0 var(--space-3xs); }
.duas code { font-family: var(--font-dado); color: var(--color-ink); }

/* ── filtros ─────────────────────────────────────────────────── */
.filtros { display: flex; flex-wrap: wrap; gap: var(--space-2xs);
           align-items: center; padding: var(--space-md) 0 var(--space-sm); }
.filtros input, .filtros select {
  font: inherit; font-size: var(--text-sm); color: var(--color-ink);
  background: var(--color-paper-2); border: var(--rule-hair) solid var(--color-rule);
  border-radius: var(--radius-sm); padding: var(--space-3xs) var(--space-2xs);
}
.filtros input { min-width: 0; flex: 1 1 14rem; }
.filtros input::placeholder { color: var(--color-ink-faint); }
.conta { font-family: var(--font-dado); font-size: var(--text-xs);
         color: var(--color-ink-faint); margin-left: auto; white-space: nowrap; }

/* ── tabela ──────────────────────────────────────────────────── */
.rolo { overflow-x: auto; border: var(--rule-hair) solid var(--color-rule);
        border-radius: var(--radius-md); }
table { border-collapse: collapse; width: 100%; min-width: 60rem; }
th, td { text-align: left; padding: var(--space-2xs) var(--space-xs);
         border-bottom: var(--rule-hair) solid var(--color-rule);
         vertical-align: top; }
thead th { position: sticky; top: 0; z-index: 2; background: var(--color-paper-3);
           font-size: var(--text-xs); text-transform: uppercase;
           letter-spacing: .07em; color: var(--color-ink-quiet); font-weight: 600;
           white-space: nowrap; cursor: pointer; }
thead th.grupo-cabo { color: var(--color-frio); }
thead th.grupo-radio { color: var(--color-accent); }
thead th:hover { color: var(--color-ink); }
tbody tr { cursor: pointer; }
tbody tr:hover { background: var(--color-paper-2); }
tbody tr.aberta { background: var(--color-paper-2); }

/* O BLOCO DE TRÊS: a mesma chave nos três controles, uma embaixo da outra.
   A regra grossa em cima da primeira linha é o que faz o bloco existir aos
   olhos — sem ela a tabela volta a ser uma lista, e comparar os três aparelhos
   vira procurar. */
tbody tr.bloco > td { border-top: 2px solid var(--color-rule); }
td.f-feature { font-weight: 500; min-width: 18rem; }
td.f-feature .rot { display: block; }
td.f-feature .cont { color: var(--color-ink-quiet); font-weight: 400;
                     font-size: var(--text-sm); }
td.f-dado { font-family: var(--font-dado); font-size: var(--text-sm);
            color: var(--color-ink-quiet); }
td.f-cabo  { background: color-mix(in oklab, var(--color-frio) 5%, transparent); }
td.f-radio { background: color-mix(in oklab, var(--color-accent) 5%, transparent); }
.tag { font-family: var(--font-dado); font-size: var(--text-xs);
       color: var(--color-ink-faint); text-transform: uppercase; letter-spacing: .05em; }
/* A peça e o evdev sao IDENTIFICADORES — o id do grupo no SVG e a constante do
   kernel. Passar caixa alta neles faria a tela mostrar `ALTO-FALANTE` onde o
   desenho diz `alto-falante`, e quem copiasse da tela copiaria errado. */
.tag .lit { text-transform: none; letter-spacing: 0; color: var(--color-ink-quiet); }
.chv { font-family: var(--font-dado); font-size: var(--text-xs);
       color: var(--color-accent); }
.pill { font-family: var(--font-dado); font-size: var(--text-xs);
        border: var(--rule-hair) solid var(--color-rule); border-radius: 99px;
        padding: 1px var(--space-2xs); white-space: nowrap; }
.e-tem  { color: var(--color-ok); border-color: color-mix(in oklab, var(--color-ok) 40%, transparent); }
.e-nao  { color: var(--color-ink-faint); }
.e-par  { color: var(--color-lacuna); border-color: color-mix(in oklab, var(--color-lacuna) 40%, transparent); }
.e-desc { color: var(--color-frio); border-style: dashed; }
.assim { color: var(--color-lacuna); font-family: var(--font-dado);
         font-size: var(--text-xs); }
.mudo { color: var(--color-rule); font-family: var(--font-dado); font-size: var(--text-xs); }

/* gaveta de detalhe */
tr.detalhe > td { background: var(--color-paper-2); padding: var(--space-sm) var(--space-md); }
.lados { display: grid; gap: var(--space-md);
         grid-template-columns: repeat(auto-fit, minmax(min(22rem, 100%), 1fr)); }
.lado h3 { font-size: var(--text-sm); text-transform: uppercase; letter-spacing: .08em;
           margin-bottom: var(--space-2xs); }
.lado.l-cabo h3 { color: var(--color-frio); }
.lado.l-radio h3 { color: var(--color-accent); }
.det dt { font-size: var(--text-xs); text-transform: uppercase; letter-spacing: .06em;
          color: var(--color-ink-faint); margin-bottom: 2px; }
.det dd { margin: 0 0 var(--space-xs); font-family: var(--font-dado);
          font-size: var(--text-sm); overflow-wrap: anywhere; }
.det dd.vazio { color: var(--color-lacuna); font-style: normal; }
.cabecalho-linha { margin-bottom: var(--space-sm); }
.cabecalho-linha .nota { color: var(--color-lacuna); font-size: var(--text-sm);
                         max-width: 90ch; }

/* ── caderno de eliminação ───────────────────────────────────── */
.caderno { margin-bottom: var(--space-md); }
.cab-caderno { display: flex; flex-wrap: wrap; gap: var(--space-2xs);
               align-items: baseline; margin-bottom: var(--space-2xs); }
.ver { font-family: var(--font-dado); font-size: var(--text-xs);
       text-transform: uppercase; letter-spacing: .05em; padding: 1px var(--space-2xs);
       border-radius: var(--radius-sm); white-space: nowrap; }
.v-culp  { background: var(--color-alerta); color: var(--color-paper); font-weight: 600; }
.v-inoc  { background: var(--color-ok);     color: var(--color-paper); }
.v-inc   { background: var(--color-lacuna); color: var(--color-paper); }
.v-conf  { background: var(--color-frio);   color: var(--color-paper); }
.v-nunca { border: var(--rule-hair) solid var(--color-rule); color: var(--color-ink-faint); }
.agora { color: var(--color-ink-quiet); font-size: var(--text-sm); }
.susp { list-style: none; margin: 0 0 var(--space-sm); padding: 0;
        display: grid; gap: var(--space-2xs); }
.susp li { border-left: 2px solid var(--color-rule); padding-left: var(--space-2xs);
           font-size: var(--text-sm); }
.mini { font-family: var(--font-dado); font-size: var(--text-xs);
        color: var(--color-ink-faint); }
.falta { font-family: var(--font-dado); font-size: var(--text-xs);
         color: var(--color-lacuna); }
.poda { border: var(--rule-hair) solid var(--color-ok); border-radius: var(--radius-sm);
        padding: var(--space-2xs) var(--space-xs); margin-bottom: var(--space-sm); }
.poda b { color: var(--color-ok); font-size: var(--text-sm); }
.poda ul { margin: var(--space-2xs) 0 0; padding-left: var(--space-md);
           font-size: var(--text-sm); }
table.ens { min-width: 32rem; }
table.ens th { position: static; background: var(--color-paper-3); cursor: default; }

/* ── Ft5 · rodapé declaração ─────────────────────────────────── */
footer { border-top: var(--rule-hair) solid var(--color-rule);
         margin-top: var(--space-xl); padding: var(--space-lg) 0 var(--space-2xl); }
footer p { max-width: 68ch; margin: 0 0 var(--space-sm); color: var(--color-ink-quiet); }
footer strong { color: var(--color-ink); font-weight: 600; }
footer .selo { font-family: var(--font-dado); font-size: var(--text-xs);
               color: var(--color-ink-faint); }

@media (max-width: 640px) {   /* noqa-acento */
  .topo { flex-direction: column; align-items: flex-start; }
  .conta { margin-left: 0; width: 100%; }
}
@media (prefers-reduced-motion: reduce) {   /* noqa-acento */
  *, *::before, *::after { transition-duration: .01ms !important;
                           animation-duration: .01ms !important; }
}
"""

SCRIPT = """
(() => {
  const D = window.__MAPA__;
  const corpo = document.getElementById('mp-corpo');
  const conta = document.getElementById('mp-conta');
  const busca = document.getElementById('mp-busca');
  const familia = document.getElementById('mp-familia');
  const so = document.getElementById('mp-so');
  let canal = 'ambos', ctrl = null, ordem = 'chave', desc = true, aberta = null;

  const SIM = { ok: ['\\u25CF','s-ok'], lac: ['\\u25D0','s-lac'],
                nulo: ['\\u25CB','s-nulo'], mudo: ['\\u25CC','s-mudo'] };
  const esc = s => (s || '').replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // O simbolo de UM lado. O quarto estado NAO e enfeite: circulo pontilhado
  // significa "ninguem respondeu por este transporte", que e diferente de
  // "o aparelho recusa". Confundir os dois foi o que produziu as regressoes.
  const simboloLado = (l, p) => {
    if (!l[p + 'aceita']) return SIM.mudo;
    if (l[p + 'aciona'] === 'sim') return SIM.ok;
    if (l[p + 'aceita'] === 'sim' || l[p + 'aceita'] === 'parcial') return SIM.lac;
    return SIM.nulo;
  };
  const simbolo = l => {
    const [c, r] = [simboloLado(l, 'cabo_'), simboloLado(l, 'radio_')];
    for (const s of [SIM.ok, SIM.lac, SIM.nulo, SIM.mudo])
      if (c === s || r === s) return s;
    return SIM.mudo;
  };

  // Assimetria: a MESMA feature, no MESMO controle, com veredicto diferente
  // entre cabo e radio. E o produto do mapa — a lacuna que causou as regressoes.
  // Com o grao em (chave, controle) a conta sai da linha, sem juncao por texto.
  D.linhas.forEach(l => {
    l._assim = !!(l.cabo_aceita && l.radio_aceita &&
      (l.cabo_aceita !== l.radio_aceita || l.cabo_aciona !== l.radio_aciona));
  });

  const CLS_EXISTE = { 'tem': 'e-tem', 'nao-tem': 'e-nao', 'parcial': 'e-par',
                       'desconhecido': 'e-desc' };

  function visiveis() {
    const q = busca.value.trim().toLowerCase();
    const fam = familia.value;
    return D.linhas.filter(l => {
      if (ctrl && l.controle !== ctrl) return false;
      if (canal === 'usb' && !l.cabo_aceita) return false;
      if (canal === 'bluetooth' && !l.radio_aceita) return false;
      if (fam && l.familia !== fam) return false;
      if (so.value === 'assim' && !l._assim) return false;
      if (so.value === 'lacuna' && !(l.existe === 'tem' &&
          l.cabo_aciona !== 'sim' && l.radio_aciona !== 'sim')) return false;
      if (so.value === 'buraco' && l.transporte !== 'sem linha no v1') return false;
      if (so.value === 'semteste' && l.teste_que_morde) return false;
      if (so.value === 'porensaiar' &&
          !(l.elim_cabo.estado === 'nunca-investigado' &&
            l.elim_radio.estado === 'nunca-investigado')) return false;
      if (so.value === 'ensaiado' &&
          l.elim_cabo.estado === 'nunca-investigado' &&
          l.elim_radio.estado === 'nunca-investigado') return false;
      if (q) {
        const alvo = (l.chave + ' ' + l.rotulo + ' ' + l.peca + ' ' + l.evdev + ' ' +
                      l.cabo_comando + ' ' + l.radio_comando + ' ' +
                      l.cabo_report_id + ' ' + l.radio_report_id + ' ' +
                      l.cabo_codigo_ref + ' ' + l.radio_codigo_ref + ' ' +
                      l.cabo_canal + ' ' + l.radio_canal + ' ' +
                      l.cabo_feature_v1 + ' ' + l.radio_feature_v1).toLowerCase();
        if (!alvo.includes(q)) return false;
      }
      return true;
    });
  }

  const PESO = { chave: l => l.chave, assim: l => (l._assim ? 0 : 1),
                 existe: l => l.existe, controle: l => l.controle,
                 familia: l => l.familia, transporte: l => l.transporte };

  const par = (l, a, b) => {
    const x = esc(l[a] || ''), y = esc(l[b] || '');
    if (!x && !y) return '<span class="mudo">\\u2014</span>';
    if (x === y) return x;
    return (x || '<span class="mudo">\\u2014</span>') + ' / ' +
           (y || '<span class="mudo">\\u2014</span>');
  };

  function pinta() {
    const ls = visiveis().slice().sort((a, b) => {
      const f = PESO[ordem] || PESO.chave;
      const x = f(a), y = f(b);
      if (x < y) return desc ? -1 : 1;
      if (x > y) return desc ? 1 : -1;
      // Dentro do bloco a ordem dos controles e sempre a mesma, para cada um
      // deles cair na mesma posicao em todo bloco da pagina.
      return D.ordem_ctrl.indexOf(a.controle) - D.ordem_ctrl.indexOf(b.controle);
    });
    conta.textContent = ls.length + ' de ' + D.linhas.length + ' linhas';
    let anterior = null;
    corpo.innerHTML = ls.map(l => {
      const [g, cls] = simbolo(l);
      const [gc, cc] = simboloLado(l, 'cabo_');
      const [gr, cr] = simboloLado(l, 'radio_');
      const novo = l.chave !== anterior;
      anterior = l.chave;
      const cabeca = novo
        ? `<span class="rot">${esc(l.rotulo)}${l._assim ? ' <span class="assim">\\u2260</span>' : ''}</span>
           <span class="chv">${esc(l.chave)}</span><br>
           <span class="cont">${esc(D.rotulo[l.controle])}</span>`
        : `<span class="cont">${esc(D.rotulo[l.controle])}</span>${l._assim ? ' <span class="assim">\\u2260</span>' : ''}`;
      const lado = (p, klass, gl, cl) =>
        `<td class="f-dado ${klass}"><span class="sim ${cl}">${gl}</span>
           ${esc(l[p + 'aceita'] || '\\u2014')}${l[p + 'aciona']
             ? ' \\u2192 ' + esc(l[p + 'aciona']) : ''}</td>`;
      return `<tr class="${novo ? 'bloco' : ''}" data-i="${l._i}"
                  data-alvo="${esc(l.alvo)}" data-ctrl="${l.controle}">
        <td class="f-dado"><span class="sim ${cls}">${g}</span></td>
        <td class="f-feature">${cabeca}
            <div class="tag">${esc(l.familia)}${l.peca
              ? ' \\u00b7 <span class="lit">' + esc(l.peca) + '</span>' : ''}${l.evdev
              ? ' \\u00b7 <span class="lit">' + esc(l.evdev) + '</span>' : ''}</div></td>
        <td><span class="pill ${CLS_EXISTE[l.existe] || 'e-desc'}">${esc(l.existe)}</span></td>
        ${lado('cabo_', 'f-cabo', gc, cc)}
        ${lado('radio_', 'f-radio', gr, cr)}
        <td class="f-dado">${par(l, 'cabo_canal', 'radio_canal')}</td>
        <td class="f-dado">${par(l, 'cabo_report_id', 'radio_report_id')}</td>
      </tr>`;
    }).join('');
  }

  const VER = { 'e-a-causa': ['é a causa','v-culp'], 'nao-e-a-causa': ['não é a causa','v-inoc'],
                inconclusivo: ['inconclusivo','v-inc'], confuso: ['ensaios se contradizem','v-conf'],
                'nunca-investigado': ['nunca investigado','v-nunca'] };

  function caderno(c, titulo) {
    const [vrot, vcls] = VER[c.estado] || VER['nunca-investigado'];
    const susp = (c.suspeitos || []).map(sp => {
      const [r, k] = VER[sp.veredicto] || VER['nunca-investigado'];
      return `<li><span class="ver ${k}">${r}</span> ${esc(sp.suspeito)}
        <div class="mini">${sp.n} ensaio(s) · com: ${esc((sp.com||[]).join(', ')||'—')}
        · sem: ${esc((sp.sem||[]).join(', ')||'—')}</div>
        ${sp.falta ? `<div class="falta">falta ${esc(sp.falta)}</div>` : ''}</li>`;
    }).join('');
    const ensaios = (c.ensaios || []).map(e => `<tr>
        <td class="f-dado">${esc(e.quando)}</td>
        <td class="f-dado">${e.presente === 'sim' ? 'COM' : 'SEM'}</td>
        <td class="f-dado">${esc(e.resultado)}</td>
        <td>${esc(e.nota)}</td></tr>`).join('');
    const poda = (c.poda || []).map(pd => `<li>${esc(pd.suspeito)}
        <div class="mini">${pd.n} ensaio(s) · o resultado não muda: ${esc(pd.resultado)}</div></li>`).join('');
    return `<div class="caderno">
      <div class="cab-caderno"><span class="tag">${titulo}</span>
        <span class="ver ${vcls}">${vrot}</span>
        <span class="agora">${esc(c.agora)}</span></div>
      ${susp ? `<ul class="susp">${susp}</ul>` : ''}
      ${poda ? `<div class="poda"><b>Pode parar de acionar</b>
        <div class="mini">provado que mexer neles não muda o resultado — é aqui que
        o produto encolhe</div><ul>${poda}</ul></div>` : ''}
      ${ensaios ? `<div class="rolo"><table class="ens"><thead><tr>
        <th>quando</th><th>com/sem</th><th>resultado</th><th>nota</th>
      </tr></thead><tbody>${ensaios}</tbody></table></div>` : ''}
    </div>`;
  }

  function gaveta(tr) {
    const l = D.linhas[+tr.dataset.i];
    const campo = (rot, v, dica) =>
      `<div><dt>${rot}</dt><dd class="${v ? '' : 'vazio'}">${v ? esc(v) : dica}</dd></div>`;
    const bloco = (p, klass, titulo) => `<div class="lado ${klass}">
      <h3>${titulo}</h3>
      ${!l[p + 'aceita'] ? `<p class="mini">nenhuma linha do v1 respondeu por este
        transporte — vazio aqui é PERGUNTA ABERTA, não é "não"</p>` : ''}
      <dl class="det">
        ${campo('O aparelho aceita', l[p + 'aceita'], '\\u2014')}
        ${campo('O Hefesto aciona', l[p + 'aciona'], '\\u2014')}
        ${campo('Caminho', l[p + 'canal'], '\\u2014')}
        ${campo('Report', l[p + 'report_id'], '\\u2014')}
        ${campo('Offset / bit', l[p + 'offset'], '\\u2014')}
        ${campo('Comando', l[p + 'comando'], '\\u2014')}
        ${campo('De onde sei', l[p + 'de_onde_sei'], '\\u2014')}
        ${campo('At\\u00e9 onde foi', l[p + 'ate_onde_foi'], '\\u2014')}
        ${campo('Evid\\u00eancia do aparelho', l[p + 'evidencia'], 'sem evid\\u00eancia registrada')}
        ${campo('Refer\\u00eancia no c\\u00f3digo', l[p + 'codigo_ref'], 'n\\u00e3o localizada')}
        ${campo('Detalhe', l[p + 'detalhe'], '\\u2014')}
        ${campo('Ressalva', l[p + 'ressalva'], '\\u2014')}
        ${campo('Como o v1 chamava', l[p + 'feature_v1'], '\\u2014')}
      </dl>
      ${caderno(p === 'cabo_' ? l.elim_cabo : l.elim_radio,
                'caderno \\u00b7 ' + titulo)}</div>`;
    const tr2 = document.createElement('tr');
    tr2.className = 'detalhe';
    tr2.innerHTML = `<td colspan="7">
      <div class="cabecalho-linha">
        <div class="chv">${esc(l.chave)} \\u00b7 ${esc(D.rotulo[l.controle])}</div>
        <div class="mini">peça no desenho: ${esc(l.peca || '\\u2014')} ·
          evdev: ${esc(l.evdev || 'não declarado no desenho')} ·
          existe: ${esc(l.existe)} · transporte no v1: ${esc(l.transporte)} ·
          id v1: ${esc(l.id_v1 || '\\u2014')}</div>
        ${l.nota ? `<p class="nota">${esc(l.nota)}</p>` : ''}
      </div>
      <div class="lados">${bloco('cabo_', 'l-cabo', 'cabo')}${bloco('radio_', 'l-radio', 'rádio')}</div>
      <dl class="det">
        ${campo('Teste que morde', l.teste_que_morde,
                'NENHUM \\u2014 esta linha n\\u00e3o \\u00e9 defendida por teste')}
        ${campo('Mordida provada em', l.mordida_provada_em,
                'nunca arrancaram a cura para ver reprovar')}
        ${campo('Assimetria declarada', l.assimetria_declarada, '\\u2014')}
        ${campo('Estado hoje', l.estado_hoje, '\\u2014')}
      </dl></td>`;
    return tr2;
  }

  function acende(tr, on) {
    const ids = (tr.dataset.alvo || '').split(' ').filter(Boolean);
    const svg = document.querySelector(`svg[data-ctrl="${tr.dataset.ctrl}"]`);
    if (!svg) return;
    ids.forEach(id => {
      const g = document.getElementById(tr.dataset.ctrl + '__' + id);
      if (!g) return;
      g.classList.toggle('marcada', on);
      if (g.classList.contains('oculta')) g.classList.toggle('acesa', on);
    });
  }

  corpo.addEventListener('mouseover', e => { const t = e.target.closest('tr[data-i]'); if (t) acende(t, true); });
  corpo.addEventListener('mouseout',  e => { const t = e.target.closest('tr[data-i]'); if (t) acende(t, false); });
  corpo.addEventListener('click', e => {
    const t = e.target.closest('tr[data-i]'); if (!t) return;
    if (aberta) { aberta.remove(); aberta = null; }
    const jaera = t.classList.contains('aberta');
    corpo.querySelectorAll('tr.aberta').forEach(x => x.classList.remove('aberta'));
    if (jaera) return;
    t.classList.add('aberta');
    aberta = gaveta(t);
    t.after(aberta);
  });

  document.querySelectorAll('.canal button').forEach(b => b.addEventListener('click', () => {
    canal = b.dataset.canal;
    document.querySelectorAll('.canal button').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
    pinta();
  }));
  document.querySelectorAll('.ctrl').forEach(b => b.addEventListener('click', () => {
    ctrl = (ctrl === b.dataset.ctrl) ? null : b.dataset.ctrl;
    document.querySelectorAll('.ctrl').forEach(x =>
      x.setAttribute('aria-pressed', String(x.dataset.ctrl === ctrl)));
    pinta();
  }));
  document.querySelectorAll('thead th[data-ord]').forEach(th => th.addEventListener('click', () => {
    const o = th.dataset.ord;
    desc = (ordem === o) ? !desc : true;
    ordem = o; pinta();
  }));
  [busca, familia, so].forEach(el => el.addEventListener('input', pinta));

  D.linhas.forEach((l, i) => { l._i = i; });
  pinta();
})();
"""


def monta() -> str:
    linhas = le_csv(reclamar=True)
    fams = sorted({lin["familia"] for lin in linhas})
    assim = assimetrias(linhas)
    chaves = len({lin["chave"] for lin in linhas})
    sem_teste = sum(1 for lin in linhas if not lin["teste_que_morde"].strip())
    buracos = sum(1 for lin in linhas if lin["transporte"] == "sem linha no v1")
    mudos = sum(1 for lado, p in LADOS for lin in linhas if not tem_lado(lin, p))
    nunca = sum(1 for lin in linhas
                if lin["elim_cabo"]["estado"] == "nunca-investigado"
                and lin["elim_radio"]["estado"] == "nunca-investigado")
    culpados = sum(1 for lin in linhas for lado, _ in LADOS
                   if lin[f"elim_{lado}"]["estado"] == "e-a-causa")
    abertas = sum(1 for lin in linhas for lado, _ in LADOS
                  if lin[f"elim_{lado}"]["estado"] == "inconclusivo")
    poda_total = sum(len(lin[f"elim_{lado}"]["poda"]) for lin in linhas for lado, _ in LADOS)
    agora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    cartoes = []
    for c in ("dualsense", "pro", "sn30"):
        p = placar(linhas, c)
        ok = round(100 * p["aciona"] / max(p["linhas"], 1))
        lac = round(100 * p["lacuna"] / max(p["linhas"], 1))
        cartoes.append(f"""
      <button class="ctrl" data-ctrl="{c}" aria-pressed="false"
              aria-label="Filtrar por {html.escape(ROTULO[c])}">
        <span class="quadro">{svg_inline(SVGS[c], c)}</span>
        <span class="nome">{html.escape(ROTULO[c])}</span>
        <span class="modelo">{html.escape(MODELO[c])}</span>
        <span class="barra" role="presentation">
          <i class="b-ok" style="width:{ok}%"></i><i class="b-lac" style="width:{lac}%"></i>
        </span>
        <span class="placar"><b>{p['aciona']}</b> de {p['existe']} features que ele TEM
          o produto aciona &middot; <b>{p['medidas']}</b> medidas &middot;
          <b>{p['sem_linha']}</b> sem resposta</span>
      </button>""")

    dados = json.dumps({
        "linhas": linhas,
        "rotulo": ROTULO,
        "ordem_ctrl": ["dualsense", "pro", "sn30"],
    }, ensure_ascii=False, separators=(",", ":"))

    opt_fam = "".join(f'<option value="{html.escape(f)}">{html.escape(f)}</option>' for f in fams)

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hefesto · mapa de canais</title>
<style>
/* Hallmark · macrostructure: Map / Diagram · nav: N9 edge-aligned · footer: Ft5 statement
 * genre: modern-minimal · theme: custom (paleta Drácula da casa, preservada do pré-voo)
 * paper oklch(~26% .02 280) dark · accent oklch(~72% .16 300) roxo · display: system-sans
 * tone: técnico/utilitário · enrichment: none (os SVG são o conteúdo)
 * pre-emit critique: P5 H4 E4 S5 R5 V4
 * ARQUIVO GERADO por scripts/gerar-mapa.py — não edite à mão.
 */
{TOKENS}{ESTILO}
</style>
</head>
<body>
<div class="envelope">

  <header class="topo">
    <h1><b>Hefesto</b> · mapa de canais</h1>
    <nav class="canal" aria-label="Canal">
      <button data-canal="usb" aria-pressed="false">tem resposta por cabo</button>
      <button data-canal="bluetooth" aria-pressed="false">tem resposta por rádio</button>
      <button data-canal="ambos" aria-pressed="true">tudo</button>
    </nav>
  </header>

  <section class="orienta">
    <p>Do plástico ao byte. Por qual canal cada feature acende.</p>
    <p>Cada feature é um <strong>bloco de três linhas</strong> — uma por controle,
       com o cabo e o rádio na MESMA linha. Passe o mouse e a peça acende no
       desenho; clique num controle para filtrar.
       <strong>{assim}</strong> linhas têm veredicto diferente entre cabo e rádio —
       essa lacuna é a que produziu as regressões.</p>
  </section>

  <section class="mapa" aria-label="Os três controles">{''.join(cartoes)}
  </section>

  <div class="legenda">
    <span><i class="sim s-ok">●</i> o Hefesto aciona</span>
    <span><i class="sim s-lac">◐</i> o aparelho aceita, o produto não faz</span>
    <span><i class="sim s-nulo">○</i> o aparelho não aceita por aquele transporte</span>
    <span><i class="sim s-mudo">◌</i> ninguém respondeu por aquele transporte</span>
    <span><i class="assim">≠</i> cabo e rádio divergem</span>
  </div>

  <div class="duas">
    <p><code>de_onde_sei</code> — <strong>de onde vem a informação</strong>:
       <em>medido</em> no aparelho · <em>inferido-do-codigo</em> (alguém leu a
       fonte) · <em>afirmado-no-doc</em> · <em>incerto</em>.</p>
    <p><code>ate_onde_foi</code> — <strong>até onde a prova chegou</strong>:
       <em>MONTOU</em> (o produto montou o report) · <em>SAIU NO FIO</em> (o byte
       saiu e algo voltou) · <em>O APARELHO OBEDECEU</em> (acendeu, girou, saiu
       som).</p>
    <p>Duas perguntas diferentes, e por isso duas colunas. Até 15/08/2026 elas se
       chamavam <em>confianca</em> e <em>grau</em> — nomes que não diziam o que
       mediam, e que por isso se confundiam. Os domínios não mudaram.</p>
  </div>

  <div class="filtros">
    <input id="mp-busca" type="search" placeholder="buscar chave, peça, evdev, comando, report, arquivo…"
           aria-label="Buscar">
    <select id="mp-familia" aria-label="Família"><option value="">todas as famílias</option>{opt_fam}</select>
    <select id="mp-so" aria-label="Recorte">
      <option value="">tudo</option>
      <option value="assim">só as assimetrias</option>
      <option value="lacuna">só as lacunas</option>
      <option value="buraco">só o que ninguém respondeu</option>
      <option value="semteste">só o que nenhum teste defende</option>
      <option value="porensaiar">só o que falta ensaiar</option>
      <option value="ensaiado">só o que já tem ensaio</option>
    </select>
    <span class="conta" id="mp-conta"></span>
  </div>

  <div class="rolo">
    <table>
      <thead><tr>
        <th scope="col" data-ord="assim" title="Ordenar">·</th>
        <th scope="col" data-ord="chave">Feature &middot; chave &middot; controle</th>
        <th scope="col" data-ord="existe">Existe</th>
        <th scope="col" class="grupo-cabo" data-ord="controle">Cabo</th>
        <th scope="col" class="grupo-radio" data-ord="controle">Rádio</th>
        <th scope="col">Caminho <span class="mini">cabo / rádio</span></th>
        <th scope="col">Report <span class="mini">cabo / rádio</span></th>
      </tr></thead>
      <tbody id="mp-corpo"></tbody>
    </table>
  </div>

  <footer>
    <p>Este mapa não é documentação — é <strong>rede contra regressão</strong>.
       Ele existe porque features consolidadas no cabo quebravam no rádio sem ninguém
       perceber.</p>
    <p>São <strong>{chaves}</strong> chaves nos três controles, <strong>{len(linhas)}</strong>
       linhas. A chave é o que ela pediu: <em>"se eu mapear no 8BitDo o funcionamento de
       um pro outro será coisa de eu mover o nome de uma variável"</em>. Em
       <strong>{buracos}</strong> dessas linhas o mapa nunca teve resposta para aquele
       controle, e em <strong>{mudos}</strong> células de transporte ninguém respondeu:
       vazio aqui é <em>pergunta aberta</em>, nunca <em>não</em>.</p>
    <p>Das <strong>{len(linhas)}</strong> linhas, <strong>{sem_teste}</strong> não têm
       teste que morda: se aquela feature quebrar naquele transporte, a suíte inteira
       continua verde. Enquanto essa coluna estiver vazia, o mapa mede o que a casa
       <em>acredita</em>, não o que ela <em>garante</em>.</p>
    <p>No caderno de eliminação: <strong>{culpados}</strong> lado(s) com culpado
       isolado, <strong>{abertas}</strong> com investigação aberta, e
       <strong>{nunca}</strong> linha(s) onde ninguém ensaiou nada dos dois lados. O
       caderno julga o cabo e o rádio SEPARADAMENTE, e isso não é capricho: os sete
       ensaios da lightbar por rádio e o do cabo levantam o mesmo suspeito com
       resultados opostos — num balde só, o veredicto viraria "os ensaios se
       contradizem" e dezesseis dias de isolamento iriam para o lixo.</p>
    <p>E a metade que dá mais lucro: <strong>{poda_total}</strong> suspeito(s) já
       inocentado(s) — coisas que o produto aciona e que, medido, não mudam nada.
       No estudo da lightbar eram quatro dos cinco canais; parar de acioná-los foi
       o que deixou o produto menor. Um culpado isolado diz por onde acionar; os
       inocentados dizem <em>o que dá para parar de fazer</em>.</p>
    <p class="selo">gerado em {agora} a partir de docs/data/mapa-controles.csv ·
       {len(linhas)} linhas · o v1 por transporte está guardado em
       docs/data/mapa-controles-v1.csv · os três desenhos são assets/control-svg/</p>
  </footer>

</div>
<script>window.__MAPA__ = {dados};</script>
<script>{SCRIPT}</script>
</body>
</html>
"""


#: O selo do rodapé, a ÚNICA parte da página que não sai das fontes. Ignorá-lo
#: é o que torna a comparação possível: com ele, todo `--check` reprovaria pelo
#: relógio, que é exatamente o defeito de onde estamos saindo.
SELO = re.compile(r"gerado em \d{2}/\d{2}/\d{4} \d{2}:\d{2} a partir de")

#: Quantas linhas de divergência o erro imprime. O corte não é frescura: uma
#: das linhas da página é o JSON inteiro do mapa, com quase um megabyte.
LIMITE_DIFF = 24
LARGURA_DIFF = 200


def normaliza(pagina: str) -> list[str]:
    """A página em linhas, sem o que não é dado.

    Duas normalizações, cada uma com um defeito medido atrás:

    - `rstrip()`: a saída do gerador tem ~20 linhas com espaço sobrando dentro
      dos `<style>` herdados dos SVG, e o arquivo commitado não tem — alguma
      ferramenta da casa as apara depois. Um comparador byte a byte reprovaria
      sempre, e um portão que reprova sempre é desligado na semana seguinte.
    - o selo: a hora da geração muda a cada execução. Comparar relógio já é o
      erro do qual este `--check` está saindo.
    """
    return [SELO.sub("gerado em <momento> a partir de", linha).rstrip()
            for linha in pagina.splitlines()]


def recorta(linha: str) -> str:
    """Uma linha do relatório, cortada — e DIZENDO que cortou.

    Sem o aviso, as duas metades do JSON do mapa aparecem idênticas nos
    primeiros 200 caracteres e o relatório parece acusar linha igual.
    """
    if len(linha) <= LARGURA_DIFF:
        return linha
    return f"{linha[:LARGURA_DIFF]}… (+{len(linha) - LARGURA_DIFF} caracteres)"


def divergencias(publicado: str, regerado: str) -> list[str]:
    """As linhas em que a página publicada difere da que as fontes produzem."""
    return list(difflib.unified_diff(
        normaliza(publicado), normaliza(regerado),
        fromfile="specs.html publicado", tofile="o que as fontes produzem hoje",
        lineterm="", n=0,
    ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="reprova se specs.html não for a página que as fontes produzem")
    args = ap.parse_args()

    if args.check:
        # PECA-ORFA-01 (13/08/2026), e vem ANTES da comparação de conteúdo de
        # propósito: órfã é defeito de DADO, e regerar não conserta. Dizer
        # "DESATUALIZADO" mandaria a pessoa rodar o gerador, que devolveria a
        # mesma órfã — e o erro apontaria para o remédio errado.
        if reprova_por_orfas(pecas_orfas(le_csv())):
            return 1
        if not SAIDA.exists():
            print("specs.html: NAO EXISTE — rode scripts/gerar-mapa.py", file=sys.stderr)
            return 1
        difs = divergencias(SAIDA.read_text(encoding="utf-8"), monta())
        if difs:
            print("specs.html: DESATUALIZADO — a página publicada não é a que estas "
                  "fontes produzem", file=sys.stderr)
            for linha in difs[:LIMITE_DIFF]:
                print(f"  {recorta(linha)}", file=sys.stderr)
            if len(difs) > LIMITE_DIFF:
                print(f"  … e mais {len(difs) - LIMITE_DIFF} linha(s) de divergência",
                      file=sys.stderr)
            print("as fontes são: " + ", ".join(str(f.relative_to(RAIZ)) for f in FONTES),
                  file=sys.stderr)
            print("rode: python3 scripts/gerar-mapa.py", file=sys.stderr)
            return 1
        print("specs.html: atualizado (confere com o CSV, com o caderno de ensaios "
              "e com os três desenhos)")
        return 0

    SAIDA.write_text(monta(), encoding="utf-8")
    kb = SAIDA.stat().st_size / 1024
    linhas = le_csv()
    print(f"{SAIDA.relative_to(RAIZ)}: {kb:.0f} KB, {len(linhas)} linhas")
    # A página é ESCRITA antes de reprovar, e essa ordem é decisão: quem acabou
    # de mexer no CSV quer ver o estado quebrado no desenho para consertá-lo. O
    # que não pode é sair 0 — foi assim que 67 alvos apontaram para ids
    # inexistentes na versão anterior do mapa sem um único erro visível.
    return 1 if reprova_por_orfas(pecas_orfas(linhas)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
