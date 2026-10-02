#!/usr/bin/env python3
"""O produto não anda na frente do desenho dela, e não fica atrás dele calado."""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from hefesto_dualsense4unix.interface import onde

BANCADA = onde.BANCADA

PUBLICADO = onde.PUBLICADO
DECLARACOES = BANCADA / "DIVERGENCIAS.md"


def paginas() -> list[str]:
    """As páginas que a régua cobre, enumeradas a partir da BANCADA."""
    return sorted(
        p.name
        for p in BANCADA.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


INVISIVEIS = re.compile(
    r'\s(?:data-campo|data-papel|data-gesto|data-controle|data-uniq|data-id'
    r'|data-eixo|data-bloco|data-lado|data-sensor|data-mudo|data-rota'
    r'|data-mic-modo|data-forca|data-mascara|data-conectado|data-lista'
    r'|data-degrau|data-modo|data-gatilho|data-entrada|data-clique'
    r'|data-hef-gesto|data-hef|data-ajuste|data-player'
        r'|data-hex|data-v|data-hef-alvo|data-hef-rolar'
    # elemento: `data-campo` (o endereço), `data-hef-alvo="classe"` (o alvo) e
    r'|data-hef-quando|data-hef-classe'
    r'|data-linha|data-hef-forma|data-face'
    r')="[^"]*"'
)


def o_que_se_ve(caminho: Path) -> bytes:
    """O HTML sem os endereços de pintura — o que chega aos olhos."""
    return INVISIVEIS.sub("", caminho.read_text(encoding="utf-8")).encode("utf-8")


def soma(caminho: Path) -> str:
    return hashlib.sha256(o_que_se_ve(caminho)).hexdigest()


def declaradas() -> set[str]:
    """As páginas declaradas EM TRABALHO, lidas dos títulos `## nome.html`."""
    if not DECLARACOES.exists():
        return set()
    texto = DECLARACOES.read_text(encoding="utf-8")
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


DIZ_O_QUE_ESPERA = re.compile(
    r"enquanto|at[ée] (?:ela |voc[êe] )?publicar|hoje ela v[êe]|"
    r"o produto continua|na tela dela hoje|sem publicar|at[ée] l[áa]",
    re.I,
)


def declaracoes_sem_custo() -> list[str]:
    """As seções que não dizem o que o produto faz enquanto espera o OK dela."""
    if not DECLARACOES.exists():
        return []
    _, sep, corpo = DECLARACOES.read_text(encoding="utf-8").partition("\n---\n")
    if not sep:
        return []
    mudas, atual, texto = [], None, []
    for linha in corpo.splitlines():
        titulo = re.match(r"^##\s+(\S+\.html)\s*$", linha)
        if titulo:
            if atual and not DIZ_O_QUE_ESPERA.search("\n".join(texto)):
                mudas.append(atual)
            atual, texto = titulo.group(1), []
        elif atual:
            texto.append(linha)
    if atual and not DIZ_O_QUE_ESPERA.search("\n".join(texto)):
        mudas.append(atual)
    return mudas


def so_mudou_endereco(nome: str) -> bool:
    """A bancada e o produto MOSTRAM a mesma coisa, e só os endereços mudaram?"""
    no_produto = PUBLICADO / nome
    if not no_produto.exists():
        return False
    return o_que_se_ve(BANCADA / nome) == o_que_se_ve(no_produto)


def publicar_enderecos(argv: list[str]) -> int:
    """Leva ao produto SÓ o que não muda um pixel — e recusa o resto."""
    alvos = _alvos(argv)
    levadas, recusadas, ja_iguais = [], [], []
    for nome in alvos:
        if not (PUBLICADO / nome).exists():
            recusadas.append((nome, "a página não existe no produto — é desenho novo"))
        # Medido no `10-perfis.html` com o `data-hef-alvo="classe"` novo:
        elif (BANCADA / nome).read_bytes() == (PUBLICADO / nome).read_bytes():
            ja_iguais.append(nome)
        elif so_mudou_endereco(nome):
            shutil.copy2(BANCADA / nome, PUBLICADO / nome)
            levadas.append(nome)
        else:
            recusadas.append((nome, "o DESENHO mudou — isto é decisão dela"))

    print(f"endereços: {len(levadas)} levada(s) · {len(recusadas)} recusada(s) "
          f"· {len(ja_iguais)} já igual(is)")
    for nome in levadas:
        print(f"  levada   {nome}  (nenhum pixel mudou)")
    for nome, porque in recusadas:
        print(f"  RECUSADA {nome}  ({porque})")
    if recusadas:
        print("\n  As recusadas esperam o OK dela:")
        for nome, _ in recusadas:
            print(f"      scripts/check_o_desenho_aprovado.py --publicar {nome[:2]}")
    _tirar_declaracoes([n for n in levadas if soma(BANCADA / n) == soma(PUBLICADO / n)])
    return 0


def _tirar_declaracoes(alvos: list[str]) -> None:
    """Apaga do DIVERGENCIAS.md a seção das páginas publicadas."""
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
    if "--publicar-enderecos" in sys.argv:
        return publicar_enderecos(
            sys.argv[sys.argv.index("--publicar-enderecos") + 1:]
        )
    if "--publicar" in sys.argv:
        return publicar(sys.argv[sys.argv.index("--publicar") + 1:])
    if "--aprovar" in sys.argv:
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

    mudas = declaracoes_sem_custo()
    if mudas:
        print(f"\nFALHA: {len(mudas)} declaração(ões) não dizem o que o produto FAZ")
        print("       enquanto espera o OK dela:")
        for n in mudas:
            print(f"  - {n}")
        print("\n  Isto custou TRÊS frentes em 02/09/2026, e sempre do mesmo jeito: o")
        print("  pacote foi para o merge com o rótulo novo e a página publicada ficou")
        print("  com o antigo. O produto rodou com metade nova e metade velha —")
        print("  clique morto, tela afirmando o contrário, conteúdo vazando.")
        print("\n  Escreva na seção o que ela vê HOJE, com a página de agora. Por")
        print("  exemplo: `Até publicar, o pacote se limita às quatro casas que a")
        print("  página tem e diz quantos ajustes ficaram de fora.`")

    if (sem_declarar or so_publicado or orfas or mudas
            or [n for n in so_bancada if n not in decl]):
        return 1
    print("\nOK: o produto não está atrás do desenho dela sem dizer por quê.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
