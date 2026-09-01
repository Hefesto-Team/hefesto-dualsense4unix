#!/usr/bin/env python3
"""O produto não anda na frente do desenho dela, e não fica atrás dele calado.

DECISÃO DELA, 31/08/2026, com o diagnóstico dela:

    "o problema original foi não ter separado a pasta do mockup e ter feito a
    interface usando o HTML do mockup. **Se alteramos no layout final a
    referência do mockup se perde.**"

E a reorientação do mesmo dia, que é o que inverteu este arquivo:

    "primeiro **nunca terminamos o mockup**, por isso não era pra ser feito no
    layout final. **Vamos concluir lá e depois seguimos pra interface.**"

O FLUXO, e a direção é `mockup/` → `layout/`:

    layout/_ferramentas/abaNN.py   ← os geradores ficam aqui
              │  python3 abaNN.py
    mockup/NN-*.html               ← a BANCADA. O desenho sendo concluído.
              │  --publicar NN, depois do OK dela na aba INTEIRA
    layout/NN-*.html               ← o PUBLICADO. É o que o produto renderiza.

ELE NASCEU INVERTIDO, e o ponto 0 do `mockup/TODO-DELA.md` era consertá-lo. Na
primeira versão o `--aprovar` copiava `layout/` → `mockup/`, o que faz o desenho
seguir o produto — o contrário do que ela decidiu. Enquanto isso valia, todo
desenho novo caía direto no produto que ela usa: `monta()` gravava em `layout/`,
e `layout/02-controles.html` é a página que o piloto `controles_vivos.py` abre
num `WebKit2.WebView`. Gerar uma aba **já trocava o produto**, sem passar pelo
olho dela.

QUANDO O PUBLICADO RECEBE, e é escolha dela em 31/08: **a cada aba fechada** —
quando todos os pontos daquela aba do `mockup/TODO-DELA.md` tiverem o OK dela.
Nem a cada ponto, nem só no fim da lista.

O QUE ELE MEDE: sha256, arquivo a arquivo. Reprova quando o produto está **atrás
do desenho** sem que a aba esteja declarada em trabalho em `mockup/DIVERGENCIAS.md`.

O QUE ELE NÃO FAZ, e é decisão: não compara byte a byte dentro do arquivo. Um
diff de HTML gerado seria ruído — a régua diz QUAL página se afastou, e o
`git diff` diz o quê. Uma linha por arquivo é acionável; mil linhas de diff são
desligadas na primeira semana.

    check_o_desenho_aprovado.py            confere (rc=1 se o produto estiver atrás)
    check_o_desenho_aprovado.py --publicar        ela aprovou tudo: publica as dez
    check_o_desenho_aprovado.py --publicar 02 09  ela aprovou essas abas
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
#: A bancada — o desenho de hoje. É onde os geradores escrevem e é o que ela olha.
BANCADA = RAIZ / "mockup"
#: O publicado — o que o produto renderiza. Só muda pelo `--publicar`.
PUBLICADO = RAIZ / "layout"
DECLARACOES = BANCADA / "DIVERGENCIAS.md"


def paginas() -> list[str]:
    """As páginas que a régua cobre, enumeradas a partir da BANCADA.

    A enumeração mudou de lado junto com o fluxo: página nova nasce no desenho,
    não no produto. `.dc.html` fica de FORA — são canvas do Claude Design
    (logo, paleta, telas), ferramenta de desenho, não página que ela abre.
    Cobri-los faria o portão cobrar publicação de rascunho.
    """
    return sorted(
        p.name
        for p in BANCADA.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


def soma(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def declaradas() -> set[str]:
    """As páginas declaradas EM TRABALHO, lidas dos títulos `## nome.html`.

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
    """Devolve (atrasadas, só-na-bancada, só-no-publicado)."""
    atrasadas, so_bancada, so_publicado = [], [], []
    for nome in paginas():
        no_produto = PUBLICADO / nome
        if not no_produto.exists():
            so_bancada.append(nome)
        elif soma(BANCADA / nome) != soma(no_produto):
            atrasadas.append(nome)
    for p in PUBLICADO.glob("*.html"):
        if p.name.endswith(".dc.html"):
            continue
        if not (BANCADA / p.name).exists():
            so_publicado.append(p.name)
    return atrasadas, so_bancada, sorted(so_publicado)


def _alvos(argv: list[str]) -> list[str]:
    """Traduz `--publicar 02 09` nos nomes de arquivo. Sem argumento: todas."""
    pedidos = [a for a in argv if not a.startswith("-")]
    if not pedidos:
        return paginas()
    escolhidas, desconhecidos = [], []
    for pedido in pedidos:
        casam = [n for n in paginas() if n == pedido or n.startswith(f"{pedido}-")]
        if casam:
            escolhidas.extend(casam)
        else:
            desconhecidos.append(pedido)
    if desconhecidos:
        # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE. Um `--publicar 11` calado
        # publicaria NADA e imprimiria sucesso — o silêncio que esta casa já
        # pagou quatro vezes em 31/08. Aqui ele é erro, com a lista ao lado.
        raise SystemExit(
            f"ERRO: não achei página para {', '.join(desconhecidos)}.\n"
            f"  As que existem na bancada: {', '.join(paginas())}"
        )
    return sorted(set(escolhidas))


def publicar(argv: list[str]) -> int:
    """Leva o desenho ao produto. É o que roda depois do OK dela numa aba."""
    alvos = _alvos(argv)
    atrasadas, _, _ = medir()
    for nome in alvos:
        shutil.copy2(BANCADA / nome, PUBLICADO / nome)
    # A página que sumiu da bancada some do produto — mas SÓ numa publicação
    # geral. Publicar uma aba não pode apagar outra.
    if len(alvos) == len(paginas()):
        for p in PUBLICADO.glob("*.html"):
            if not p.name.endswith(".dc.html") and not (BANCADA / p.name).exists():
                p.unlink()
    _tirar_declaracoes(alvos)
    mudaram = [n for n in alvos if n in atrasadas]
    print(f"publicado: {len(alvos)} página(s) · {len(mudaram)} mudou/mudaram de fato")
    for nome in mudaram:
        print(f"  - {nome}")
    if not mudaram:
        print("  (o produto já estava igual ao desenho nessas páginas)")
    return 0


def _tirar_declaracoes(alvos: list[str]) -> None:
    """Apaga do DIVERGENCIAS.md a seção das páginas publicadas.

    A aba deixou de estar em trabalho: a declaração sai junto. Declaração que
    envelhece calada vira paisagem, e paisagem ninguém lê.
    """
    if not DECLARACOES.exists():
        return
    texto = DECLARACOES.read_text(encoding="utf-8")
    cabeca, sep, corpo = texto.partition("\n---\n")
    if not sep:
        return
    guardadas, pulando = [], False
    for linha in corpo.splitlines():
        titulo = re.match(r"^##\s+(\S+\.html)\s*$", linha)
        if titulo:
            pulando = titulo.group(1).strip() in alvos
        if not pulando:
            guardadas.append(linha)
    novo = "\n".join(guardadas).strip("\n")
    if not re.search(r"^##\s+\S+\.html\s*$", novo, re.M):
        novo = "<!-- Nenhuma aba em trabalho: o produto está igual ao desenho dela. -->"
    DECLARACOES.write_text(f"{cabeca}\n---\n\n{novo}\n", encoding="utf-8")


def main() -> int:
    if not BANCADA.exists():
        print("ERRO: não há `mockup/`. Ela é a bancada — sem ela não há desenho.")
        return 2
    if "--publicar" in sys.argv:
        return publicar(sys.argv[sys.argv.index("--publicar") + 1:])
    if "--aprovar" in sys.argv:
        # O NOME ANTIGO NÃO FICA CALADO. Ele copiava `layout/` → `mockup/`, que
        # é a direção errada; quem o digitar por hábito faria o desenho seguir o
        # produto e apagaria em silêncio o que ela aprovou.
        print("ERRO: `--aprovar` copiava o PRODUTO para o DESENHO — a direção errada.")
        print("  O fluxo é `mockup/` → `layout/`. O comando de hoje é:")
        print("      scripts/check_o_desenho_aprovado.py --publicar [NN ...]")
        return 2

    atrasadas, so_bancada, so_publicado = medir()
    decl = declaradas()
    sem_declarar = [n for n in atrasadas if n not in decl]
    orfas = sorted(decl - set(atrasadas) - set(so_bancada))

    print(f"desenho: {len(paginas())} página(s) na bancada `mockup/`")
    print(f"  o produto já tem ..... {len(paginas()) - len(atrasadas) - len(so_bancada)}")
    print(f"  o produto está atrás . {len(atrasadas)}  ({len(atrasadas) - len(sem_declarar)} em trabalho)")

    if so_publicado:
        print(f"\nFALHA: {len(so_publicado)} página(s) do produto sumiram do desenho:")
        for n in so_publicado:
            print(f"  - {n}")
        print("  O produto renderiza uma página sem referência — é o colapso que ela mandou desfazer.")
    if so_bancada and any(n not in decl for n in so_bancada):
        novas = [n for n in so_bancada if n not in decl]
        print(f"\nFALHA: {len(novas)} página(s) novas no desenho e ainda fora do produto:")
        for n in novas:
            print(f"  - {n}")
        print("  Declare a aba em trabalho, ou publique quando ela aprovar.")
    if sem_declarar:
        print(f"\nFALHA: o produto está ATRÁS do desenho em {len(sem_declarar)} página(s), sem declaração:")
        for n in sem_declarar:
            print(f"  - {n}")
        print(f"\n  Veja o que mudou:   diff <(git show HEAD:layout/{sem_declarar[0]}) mockup/{sem_declarar[0]}")
        print(f"  Se a aba ainda está em trabalho, declare em {DECLARACOES.relative_to(RAIZ)}:")
        print(f"      ## {sem_declarar[0]}")
        print("      - **31/08/2026** — o ponto da lista que está aberto nela.")
        print("  Se ela aprovou a aba INTEIRA:")
        print(f"      scripts/check_o_desenho_aprovado.py --publicar {sem_declarar[0][:2]}")
    if orfas:
        print(f"\nFALHA: {len(orfas)} declaração(ões) sem trabalho aberto — APAGUE de {DECLARACOES.name}:")
        for n in orfas:
            print(f"  - {n}")
        print("  Declaração que envelhece calada vira paisagem, e paisagem ninguém lê.")

    if sem_declarar or so_publicado or orfas or [n for n in so_bancada if n not in decl]:
        return 1
    print("\nOK: o produto não está atrás do desenho dela sem dizer por quê.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
