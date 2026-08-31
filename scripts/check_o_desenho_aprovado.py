#!/usr/bin/env python3
"""O produto não se afasta do desenho dela sem alguém dizer por quê.

DECISÃO DELA, 31/08/2026, com o diagnóstico dela:

    "o problema original foi não ter separado a pasta do mockup e ter feito a
    interface usando o HTML do mockup. **Se alteramos no layout final a
    referência do mockup se perde.**"

`mockup/` guarda o desenho que ela aprovou; `layout/` é o que o produto
renderiza. Este portão compara os dois por sha256 e reprova toda divergência
**não declarada** em `mockup/DIVERGENCIAS.md`.

POR QUE ELE EXISTE, e o preço está medido: em 31/08/2026 esta casa tinha duas
pastas com o mesmo conteúdo e nenhuma régua entre elas. `layout/` e
`novo-layout/` divergiram **25 KB** (81.755 contra 56.416 bytes no piloto) sem
ninguém ver; o lançador `interface` passou a procurar a errada primeiro; e os
glifos L2 e R2 sumiram da aba Gatilhos numa leva não commitada, ficando dois
dias fora sem que nenhum portão acusasse.

Duas cópias sem régua divergem. Este arquivo é a régua.

O QUE ELE NÃO FAZ, e é decisão: ele não compara byte a byte dentro do arquivo.
Um diff de HTML gerado seria ruído — a régua diz QUAL arquivo se afastou, e o
`git diff` diz o quê. Uma linha por arquivo é acionável; mil linhas de diff são
desligadas na primeira semana.

    scripts/check_o_desenho_aprovado.py              confere (rc=1 se divergir)
    scripts/check_o_desenho_aprovado.py --aprovar    ela aprovou: refaz a foto
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MOCKUP = RAIZ / "mockup"
LAYOUT = RAIZ / "layout"
DECLARACOES = MOCKUP / "DIVERGENCIAS.md"

#: Os arquivos que a fotografia cobre. As dez abas mais os dois mapas — o que
#: ela abre com duplo clique. Os geradores NÃO entram: eles são do produto, e
#: fotografar gerador seria congelar o meio, não o fim.
#: `.dc.html` fica de FORA: são canvas do Claude Design (logo, paleta, telas),
#: ferramenta de desenho, não página que ela abre no produto. Fotografá-los faria
#: o portão cobrar aprovação de rascunho.
def paginas() -> list[str]:
    return sorted(
        p.name
        for p in LAYOUT.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


def soma(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def declaradas() -> set[str]:
    """Os arquivos com divergência declarada, lidos dos títulos `## nome.html`.

    A razão fica no corpo da seção e é para gente ler; o portão só cobra que a
    seção EXISTA. Cobrar o formato da razão faria a régua brigar com quem
    escreve bem — é a lição do `SERVE_UM_LADO_SO`.
    """
    if not DECLARACOES.exists():
        return set()
    texto = DECLARACOES.read_text(encoding="utf-8")
    # SÓ DEPOIS DO `---`: o cabeçalho do arquivo mostra o FORMATO com um exemplo
    # (`## 01-jogar.html`), e ler o exemplo como declaração faria o portão
    # absolver de graça a primeira aba da lista. Pego na primeira execução.
    corpo = texto.split("\n---\n", 1)[-1]
    return {m.group(1).strip() for m in re.finditer(r"^##\s+(\S+\.html)\s*$", corpo, re.M)}


def medir() -> tuple[list[str], list[str], list[str]]:
    """Devolve (mudaram, só-no-layout, só-no-mockup)."""
    mudaram, so_layout, so_mockup = [], [], []
    for nome in paginas():
        no_mockup = MOCKUP / nome
        if not no_mockup.exists():
            so_layout.append(nome)
        elif soma(no_mockup) != soma(LAYOUT / nome):
            mudaram.append(nome)
    for p in MOCKUP.glob("*.html"):
        if not (LAYOUT / p.name).exists():
            so_mockup.append(p.name)
    return mudaram, so_layout, sorted(so_mockup)


def aprovar() -> int:
    for nome in paginas():
        shutil.copy2(LAYOUT / nome, MOCKUP / nome)
    for p in MOCKUP.glob("*.html"):
        if not (LAYOUT / p.name).exists():
            p.unlink()
    DECLARACOES.write_text(
        DECLARACOES.read_text(encoding="utf-8").split("---\n")[0]
        + "---\n\n<!-- Nenhuma divergência declarada: ela aprovou o desenho de agora. -->\n",
        encoding="utf-8",
    )
    print(f"fotografia refeita: {len(paginas())} página(s). As declarações antigas saíram.")
    return 0


def main() -> int:
    if not MOCKUP.exists():
        print("ERRO: não há `mockup/`. Ela é o desenho aprovado — sem ela não há régua.")
        return 2
    if "--aprovar" in sys.argv:
        return aprovar()

    mudaram, so_layout, so_mockup = medir()
    decl = declaradas()
    sem_declarar = [n for n in mudaram if n not in decl]
    orfas = sorted(decl - set(mudaram))

    print(f"desenho aprovado: {len(list(MOCKUP.glob('*.html')))} página(s) em `mockup/`")
    print(f"  iguais ao produto ..... {len(paginas()) - len(mudaram) - len(so_layout)}")
    print(f"  divergem .............. {len(mudaram)}  ({len(mudaram) - len(sem_declarar)} declarada(s))")

    if so_layout:
        print(f"\nFALHA: {len(so_layout)} página(s) do produto NÃO estão no desenho aprovado:")
        for n in so_layout:
            print(f"  - {n}")
        print("  Página nova é desenho novo: ela precisa olhar antes de virar produto.")
    if so_mockup:
        print(f"\nFALHA: {len(so_mockup)} página(s) do desenho sumiram do produto:")
        for n in so_mockup:
            print(f"  - {n}")
    if sem_declarar:
        print(f"\nFALHA: {len(sem_declarar)} página(s) se afastaram do desenho SEM declaração:")
        for n in sem_declarar:
            print(f"  - {n}")
        print(f"\n  Veja o que mudou:   git diff -- layout/{sem_declarar[0]}")
        print(f"  Se a mudança é legítima, declare em {DECLARACOES.relative_to(RAIZ)}:")
        print(f"      ## {sem_declarar[0]}")
        print("      - **31/08/2026** — o que mudou, e por quê.")
        print("  Se ela aprovou o desenho novo:")
        print("      scripts/check_o_desenho_aprovado.py --aprovar")
    if orfas:
        print(f"\nFALHA: {len(orfas)} declaração(ões) sem divergência — APAGUE de {DECLARACOES.name}:")
        for n in orfas:
            print(f"  - {n}")
        print("  Declaração que envelhece calada vira paisagem, e paisagem ninguém lê.")

    if sem_declarar or so_layout or so_mockup or orfas:
        return 1
    print("\nOK: o produto não se afastou do desenho dela sem dizer por quê.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
