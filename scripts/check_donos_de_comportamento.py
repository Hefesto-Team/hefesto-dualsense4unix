#!/usr/bin/env python3
"""Portão: cada comportamento tem UM dono, e a tela nova o CHAMA.

Nasceu da queixa dela, 05/09/2026:

    *"a parte de recriarmos cada script ao invés de adaptar o que já temos
    pronto do gtk, isso eu havia pedido e sempre repetia, mas tá sendo
    recriado tudo sempre (…) estamos recriando um produto que estava
    praticamente pronto pro gtk."*

Cinco agentes mediram 410 comportamentos das dez abas contra a janela GTK. O
resultado virou :file:`docs/data/donos-de-comportamento.csv`, e este portão é o
que **impede o mapa de envelhecer** — que é como todo mapa desta casa morre.

O que ele reprova, e por quê:

1. **Endereço morto.** Todo ``dono`` e todo ``onde_html`` é ``arquivo.py:símbolo``
   e tem de resolver — arquivo que existe, símbolo definido lá dentro. Por
   SÍMBOLO e não por linha, de propósito: número de linha caduca a cada edição
   acima dele, e um portão que fica vermelho por nada é um portão que se
   aprende a ignorar. Medido em 05/09: dez dos endereços vindos dos laudos já
   apontavam para outra função, horas depois.

2. **Cura descosturada.** Linha ``CURADO`` cujo arquivo de tela deixou de citar
   o símbolo do dono. É a regressão exata que os seis defeitos vivos de hoje
   tinham: a tela recalculava porque a ponte para o dono não passava tráfego.

3. **SO-GTK que já migrou.** Linha ``SO-GTK`` diz "isto existe pronto na janela
   e a tela nova não tem". No dia em que alguém ligar, o mapa passa a mentir —
   e mentir para menos, dizendo que falta trabalho já feito. O portão vê o
   símbolo aparecer em ``interface/`` e manda reclassificar.

4. **A dívida só desce.** ``TETO_DE_LINHAS_DUPLICADAS`` é o quanto de código
   recriado ainda está declarado. Declarar duplicata nova é o certo a fazer —
   e é o que estoura o teto, obrigando a decisão a ser tomada por gente, com
   data, em vez de a dívida crescer calada.

5. **Linha incompleta.** Sem ``razao`` não se decide nada meses depois; sem
   ``economia_linhas`` uma duplicata não entra na conta do item 4.

O portão NÃO tenta adivinhar se um código "calcula em vez de chamar" — isso é
julgamento, e julgamento vira laudo, não régua. O que ele garante é que o laudo
continue verdadeiro.
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MAPA = RAIZ / "docs" / "data" / "donos-de-comportamento.csv"

#: A dívida declarada de código recriado, em linhas. **Só desce.**
#:
#: 05/09/2026 — 2.397, a soma de ``economia_linhas`` das treze duplicatas que os
#: cinco laudos mediram. Quem declarar uma duplicata nova estoura o teto de
#: propósito: a alternativa é ela entrar calada, e foi assim que 27.689 linhas
#: de ``interface/pacotes/`` nasceram sem ninguém somar o custo.
TETO_DE_LINHAS_DUPLICADAS = 2397

#: Onde a tela nova mora. Um símbolo SO-GTK que apareça aqui deixou de ser
#: SO-GTK — é o item 3 do cabeçalho.
TELA_NOVA = ("interface", "app/actions/perfis_web.py", "app/actions/jogar")

VEREDITOS_DE_DUPLICATA = ("DUPLICATA", "DUPLICATA-QUE-PIOROU")


def _simbolos(caminho: Path) -> set[str]:
    """Todo nome que este arquivo DEFINE — def, class e atribuição de topo.

    Inclui método de classe: o dono de um comportamento pode ser um método
    (``DaemonActionsMixin._ESTADOS_COM_DAEMON_DE_PE`` é um deles), e exigir
    função solta empurraria o mapa a mentir sobre onde a regra mora.
    """
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.add(no.name)
        elif isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    nomes.add(alvo.id)
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nomes.add(no.target.id)
    return nomes


def _parte(endereco: str) -> tuple[str, str]:
    arquivo, _, simbolo = endereco.rpartition(":")
    return arquivo, simbolo


def _cita(caminho: Path, simbolo: str) -> bool:
    try:
        return simbolo in caminho.read_text(encoding="utf-8")
    except OSError:
        return False


def _quem_cita(simbolo: str) -> list[str]:
    """Arquivos da TELA NOVA que citam este símbolo."""
    achados: list[str] = []
    for pasta in TELA_NOVA:
        alvo = SRC / pasta
        arquivos = alvo.rglob("*.py") if alvo.is_dir() else ([alvo] if alvo.exists() else [])
        for py in arquivos:
            if _cita(py, simbolo):
                achados.append(str(py.relative_to(SRC)))
    return achados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--censo", action="store_true", help="imprime o mapa por veredito")
    args = parser.parse_args(argv)

    if not MAPA.exists():
        print(f"VERMELHO: o mapa não existe: {MAPA.relative_to(RAIZ)}")
        return 1

    with MAPA.open(encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))

    queixas: list[str] = []
    duplicadas = 0
    censo: dict[str, int] = {}

    for i, linha in enumerate(linhas, start=2):
        nome = linha["comportamento"]
        veredito = linha["veredito"]
        censo[veredito] = censo.get(veredito, 0) + 1

        if not linha["razao"].strip():
            queixas.append(f"{MAPA.name}:{i} {nome}: sem `razao` — ninguém decide nada com isto")

        enderecos = [("dono", linha["dono"])]
        if linha["onde_html"].strip():
            enderecos.append(("onde_html", linha["onde_html"]))

        for coluna, endereco in enderecos:
            arquivo, simbolo = _parte(endereco)
            if not arquivo or not simbolo:
                queixas.append(
                    f"{MAPA.name}:{i} {nome}: `{coluna}` não é `arquivo.py:símbolo`: {endereco!r}"
                )
                continue
            caminho = SRC / arquivo
            if not caminho.exists():
                queixas.append(f"{MAPA.name}:{i} {nome}: `{coluna}` cita arquivo que sumiu: {arquivo}")
            elif simbolo not in _simbolos(caminho):
                queixas.append(
                    f"{MAPA.name}:{i} {nome}: `{coluna}` cita `{simbolo}`, que {arquivo} não define"
                )

        if veredito == "CURADO" and linha["onde_html"].strip():
            _, simbolo_do_dono = _parte(linha["dono"])
            arquivo_html, _ = _parte(linha["onde_html"])
            tela = SRC / arquivo_html
            if tela.exists() and not _cita(tela, simbolo_do_dono):
                queixas.append(
                    f"{MAPA.name}:{i} {nome}: CURADO, mas {arquivo_html} não cita mais "
                    f"`{simbolo_do_dono}` — a ponte para o dono caiu de novo"
                )

        if veredito == "SO-GTK":
            _, simbolo_do_dono = _parte(linha["dono"])
            cita = _quem_cita(simbolo_do_dono)
            if cita:
                queixas.append(
                    f"{MAPA.name}:{i} {nome}: marcado SO-GTK, mas a tela nova já chama "
                    f"`{simbolo_do_dono}` em {', '.join(cita)} — reclassifique"
                )

        if veredito in VEREDITOS_DE_DUPLICATA:
            bruto = linha["economia_linhas"].strip()
            if not bruto.isdigit():
                queixas.append(
                    f"{MAPA.name}:{i} {nome}: duplicata sem `economia_linhas` — fica fora da conta"
                )
            else:
                duplicadas += int(bruto)

    if duplicadas > TETO_DE_LINHAS_DUPLICADAS:
        queixas.append(
            f"a dívida declarada subiu para {duplicadas} linhas, e o teto é "
            f"{TETO_DE_LINHAS_DUPLICADAS}. O teto SÓ DESCE: cure uma duplicata, ou "
            f"suba o teto neste arquivo com a data e a razão."
        )

    if args.censo or queixas:
        print(f"{len(linhas)} comportamentos, {duplicadas} linhas de dívida declarada")
        for veredito, quantos in sorted(censo.items(), key=lambda p: -p[1]):
            print(f"  {quantos:>3}  {veredito}")

    if queixas:
        print()
        for q in queixas:
            print(f"VERMELHO: {q}")
        return 1

    print(f"VERDE: {len(linhas)} comportamentos com dono vivo, dívida em {duplicadas} linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
