#!/usr/bin/env python3
"""Os QUATRO lugares de cada aba carregam os MESMOS endereços.

ELA MEDIU O DEFEITO NA PRÓPRIA MESA, 07/09/2026, com os quatro DualSense
ligados e os quatro reconhecidos:

    "4 controles conectados mas as infos dos dos outros 2 ultimos não  (noqa-acento: citação literal dela)
    aparecem (…) isso em todas as abas."

A CAUSA NÃO ERA O DADO. Medido de ponta a ponta: o daemon publicava os quatro,
o piloto montava `colunas=['p1','p2','p3','p4']` e `vazios=[]`. O que faltava
era ONDE POUSAR — o ramo do lugar vazio de vários geradores emitia um cartão
sem um único `data-campo`, e o passo 2 do piloto procura o endereço DENTRO do
bloco `[data-controle="pN"]`. Sem endereço, o valor do P3 e do P4 caía no chão,
calado. A tela dizia dois porque a MESA do desenho tem dois; o aparelho dizia
quatro.

POR QUE UM PORTÃO, e não só a auto-checagem de cada gerador: o defeito é o
MESMO em dez arquivos, e sete deles o tinham. Uma régua por aba já existe (cada
`abaNN.py` ganhou a sua nesta leva) — esta aqui é a que atravessa as dez e vê
o que nenhuma delas pode ver: uma aba nova nascendo com o ramo separado.

O QUE NÃO PRECISA PRÉ-EXISTIR, e as duas razões são estruturais:

1. O que mora DENTRO de um campo de alvo `html`. O piloto troca o miolo do
   bloco e RECRIA os filhos — cravar um filho escondido no lugar vazio só para
   o conjunto fechar seria régua medindo a própria saída. É o `luz-incerta` da
   aba Iluminação, que nasce dentro do `luz`.
2. A caixa que é BLOCO (`data-ajuste`, na aba Gatilhos). Bloco pousa por
   seletor CSS, e `pacotes/a03_gatilhos.py` o emite para TODO lugar da página,
   cheio ou vazio. Exigi-lo igual obrigaria a inventar no P2 uma barra que o
   MODO dele não tem: as barras são do modo, nunca do lugar.

TRÊS ABAS NÃO TÊM CARTÃO POR CONTROLE, e isso é desenho, não falta: Lançadores
(os cartões são por lançador), Sistema (a página é a contagem da máquina) e
Perfis (os lugares são `<tr data-hef-uniq>`, outro vocabulário). Elas passam
declarando ausência, e o portão diz isso em vez de calar.

Uso:
    scripts/check_os_quatro_lugares.py              a bancada — o desenho de hoje
    scripts/check_os_quatro_lugares.py --publicado  o que o produto renderiza
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from hefesto_dualsense4unix.interface import onde  # noqa: E402

#: O bloco de um lugar, e o seletor é O MESMO que o piloto usa —
#: `document.querySelectorAll('[data-controle="' + pref + '"]')`. Uma régua que
#: não procura o que o produto procura reprova pelo motivo errado no dia em que
#: morder de verdade.
LUGAR = re.compile(r'data-controle="(p[1-4])"')
CAMPO = re.compile(r'data-campo="([^"]+)"')
ALVO_HTML = re.compile(r'data-campo="[^"]+"[^>]*data-hef-alvo="html"')
CAIXA_DE_BLOCO = re.compile(r'<div[^>]*data-ajuste="[^"]*"')

#: As páginas avulsas — a de calibração, os dois mapas, as folhas do Design.
#: Elas não são aba, e a de calibração desenha só quem está na mesa AGORA.
SO_AS_ABAS = re.compile(r"^\d\d-")


def _miolo(html: str, i_abre: int, tag: str) -> tuple[int, int]:
    """(início, fim) do miolo de uma tag aberta em `i_abre`, por contagem.

    POR CONTAGEM E NÃO ATÉ O VIZINHO: recortar cada lugar até o começo do
    seguinte faz o ÚLTIMO engolir o rodapé — foi assim que o P4 da aba Gatilhos
    apareceu com doze endereços onde tem dez.
    """
    fim_da_abertura = html.index(">", i_abre) + 1
    i, nivel = fim_da_abertura, 1
    passo = re.compile(r"</?%s\b" % tag)
    while nivel and i < len(html):
        n = passo.search(html, i)
        if not n:
            break
        nivel += -1 if n.group(0).startswith("</") else 1
        i = n.end()
    return fim_da_abertura, i


def _recorta(html: str, pref: str) -> str:
    """O miolo do bloco `data-controle="pN"`."""
    m = re.search(r'<(\w+)[^>]*data-controle="%s"[^>]*>' % pref, html)
    if not m:
        return ""
    a, b = _miolo(html, m.start(), m.group(1))
    return html[a:b]


def campos_que_pousam(miolo: str) -> set[str]:
    """Os `data-campo` que o piloto precisa achar JÁ NO DOCUMENTO."""
    recriados: set[str] = set()
    for m in ALVO_HTML.finditer(miolo):
        i = miolo.rfind("<", 0, m.start())
        tag = re.match(r"<(\w+)", miolo[i:])
        if not tag:
            continue
        a, b = _miolo(miolo, i, tag.group(1))
        recriados |= set(CAMPO.findall(miolo[a:b]))
    for m in CAIXA_DE_BLOCO.finditer(miolo):
        a, b = _miolo(miolo, m.start(), "div")
        recriados |= set(CAMPO.findall(miolo[a:b]))
    return set(CAMPO.findall(miolo)) - recriados


def medir(caminho: pathlib.Path) -> tuple[bool, str]:
    """(passou, o recado) de uma página."""
    html = caminho.read_text(encoding="utf-8")
    corpo = html[html.find("<body"):] if "<body" in html else html
    lugares = sorted(set(LUGAR.findall(corpo)))
    if not lugares:
        return True, f"{caminho.stem:16} sem cartão por controle — é o desenho"
    conjuntos = {p: campos_que_pousam(_recorta(corpo, p)) for p in lugares}
    uniao: set[str] = set().union(*conjuntos.values())
    faltas = {p: sorted(uniao - c) for p, c in conjuntos.items() if uniao - c}
    if len(lugares) != 4:
        return False, (f"{caminho.stem:16} tem {len(lugares)} lugares "
                       f"({', '.join(lugares)}) e a mesa tem quatro")
    if faltas:
        linhas = [f"{caminho.stem:16} os lugares não recebem o mesmo:"]
        linhas += [f"                   {p} não tem onde receber {f}"
                   for p, f in sorted(faltas.items())]
        return False, "\n".join(linhas)
    return True, (f"{caminho.stem:16} os quatro lugares recebem os mesmos "
                  f"{len(uniao)} endereços")


def main() -> int:
    publicado = "--publicado" in sys.argv
    paginas = [p for p in onde.paginas(publicado=publicado)
               if SO_AS_ABAS.match(p.name)]
    if not paginas:
        # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE.
        print("check_os_quatro_lugares: não achei nenhuma aba para medir.")
        return 1
    onde_estou = "o publicado" if publicado else "a bancada"
    print(f"os quatro lugares — {onde_estou}, {len(paginas)} abas")
    ruins = 0
    for p in paginas:
        passou, recado = medir(p)
        print(("  ok   " if passou else "  FALHA ") + recado)
        ruins += 0 if passou else 1
    if ruins:
        print(f"\n{ruins} aba(s) em que o dado dos quatro controles não tem "
              f"onde pousar. É o defeito que ela mediu em 07/09/2026: a tela "
              f"mostra dois porque o desenho tem dois.")
    return 1 if ruins else 0


if __name__ == "__main__":
    raise SystemExit(main())
