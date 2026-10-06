#!/usr/bin/env python3
"""gerar.py — a Wiki nasce do que o repositório já sabe: gerada a cada push, nunca escrita à mão.

Lê os documentos de origem NA HORA (nada é copiado para o repositório) e monta as páginas num
diretório: o início (do `README.md`), o guia de uso (`docs/usage`), o mapa dos controles (do
`docs/data/mapa-controles.csv`, uma página por família de recurso, com a tabela cabo × Bluetooth e
até onde cada linha foi provada) e o protocolo (`docs/protocol`), mais a barra lateral e o rodapé.
Cada página carrega, no alto, o cabeçalho da fonte, e no fim a linha «corrija lá».

  gerar.py --saida DIR              escreve as páginas (o mesmo commit gera os mesmos bytes)
  gerar.py --saida DIR --conferir   diz o que mudaria e sai 1 se mudaria alguma coisa

Os filtros de publicação rodam sobre o texto GERADO (`filtros_de_publicacao.py`): a página que
reprova não sobe (os links dos outros para ela voltam ao arquivo no repositório), e a fonte é
corrigida. Saídas: 0 limpo; 1 houve página segurada, ou `--conferir` achou diferença; 2 a saída é
recusada (a árvore de origem, ou uma pasta com arquivos que não é Wiki); 3 um filtro não pôde medir
(nada é escrito: o que não dá para medir reprova).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
RAIZ = SCRIPTS.parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import filtros_de_publicacao as filtros

REPO = os.environ.get("WIKI_REPO", "https://github.com/Hefesto-Team/hefesto-dualsense4unix")
# A Wiki sai do `dev`: os links para arquivo apontam para o ramo de onde ela foi gerada.
REF = "dev"

LEIAME = "README.md"
USO = "docs/usage"
PROTOCOLO = "docs/protocol"
MAPA = "docs/data/mapa-controles.csv"
IMAGENS_DO_USO = "docs/usage/assets"

# O que NÃO vai para a Wiki, com o motivo. Tudo o mais de `docs/usage` e `docs/protocol` vai, e passa
# pelos filtros. O que é do trabalho interno (`docs/process`, `docs/method`, `docs/research`, estudos
# e relatos) nunca entra: a Wiki é uso, mapa e protocolo.
FORA: dict[str, str] = {
    "docs/protocol/proton-o-pino-desta-casa-e-a-subida-para-o-11-7.md":
        "decisão interna de versão do Proton, do trabalho da casa e não do que o aparelho faz",
}

# Links para arquivo que existe e vira link no repositório; o resto vira só o texto do link.
LINKAVEIS = ("src/", "assets/", "examples/", ".github/", "flatpak/", "docs/data/", "docs/usage/",
             "docs/protocol/")
LINKAVEIS_NA_RAIZ = ("README.md", "LICENSE", "NOTICE", "CHANGELOG.md")
SUFIXOS_DE_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# O vocabulário do mapa (rótulos de tabela, não frases): a mesma ordem e os mesmos nomes do `specs.html`.
CONTROLES = (("dualsense", "DualSense"), ("pro", "Nintendo Pro"), ("sn30", "8BitDo SN30 Pro"))
FAMILIAS = {
    "gatilho": "Gatilhos", "luz": "Luz", "audio": "Som", "vibracao": "Vibração", "movimento": "Movimento",
    "toque": "Toque", "entrada": "Entrada", "energia": "Energia", "identidade": "Identidade",
    "plataforma": "Plataforma", "combinacao": "Vários controles",
}
EXISTE = {"tem": "tem", "nao-tem": "não tem", "parcial": "parcial", "desconhecido": "desconhecido"}
ORIGEM = {"medido": "medido", "inferido-do-codigo": "lido no código", "afirmado-no-doc": "afirmado em documento",
          "incerto": "incerto"}


# ---------------------------------------------------------------------------
# O modelo
# ---------------------------------------------------------------------------


@dataclass
class Pagina:
    nome: str          # o nome do arquivo na Wiki, sem `.md`
    titulo: str        # o que a barra lateral mostra
    fonte: str         # o arquivo do repositório de onde a página nasce
    grupo: str         # onde ela aparece na navegação
    corpo: str = ""
    posicao: int = 0   # a ordem dentro do grupo (as famílias do mapa seguem `FAMILIAS`); empate, pelo nome


@dataclass
class Wiki:
    paginas: dict[str, Pagina] = field(default_factory=dict)
    imagens: dict[str, str] = field(default_factory=dict)   # destino na Wiki → arquivo de origem
    avisos: list[str] = field(default_factory=list)

    def arquivos(self) -> dict[str, str]:
        """O texto de cada arquivo `.md` da Wiki (páginas, barra lateral e rodapé)."""
        return {f"{n}.md": p.corpo for n, p in sorted(self.paginas.items())}


def ascii_minusculo(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def titulo_do(markdown: str, padrao: str) -> str:
    """O primeiro título `# ` fora dos blocos de código."""
    em_codigo = False
    for linha in markdown.splitlines():
        if linha.lstrip().startswith(("```", "~~~")):
            em_codigo = not em_codigo
        elif not em_codigo and linha.startswith("# "):
            return re.sub(r"[*_`]", "", linha[2:]).strip() or padrao
    return padrao


def url_do(caminho: str, *, pasta: bool = False) -> str:
    return f"{REPO}/{'tree' if pasta else 'blob'}/{REF}/{caminho}"


# ---------------------------------------------------------------------------
# Os links: a Wiki é plana, e cada alvo é uma página, uma imagem, um arquivo do repositório ou só texto
# ---------------------------------------------------------------------------

_ESQUEMA = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)
_LINK = re.compile(
    r'(?P<img>!?)\[(?P<txt>[^\[\]]*)\]\((?P<t>[^)\s]+)(?P<ti>\s+"[^"]*")?\)'
    r'|\]\((?P<t2>[^)\s]+)(?P<ti2>\s+"[^"]*")?\)'
)
_ATRIBUTO = re.compile(r'\b(?P<a>src|href)="(?P<t>[^"]*)"')
_DEFINICAO = re.compile(r"^(?P<ini>\s{0,3}\[[^\]]+\]:\s*)(?P<t>\S+)")


@dataclass
class Contexto:
    raiz: Path
    publicados: dict[str, str]          # fonte → nome da página
    imagens: dict[str, str]             # destino → origem
    avisos: list[str]
    titulos: dict[str, str] = field(default_factory=dict)   # nome da página → título
    origem: str = ""

    def destino(self, alvo: str) -> str | None:
        """O novo endereço do alvo, ou None quando o link não pode continuar (só o texto fica)."""
        if not alvo or alvo.startswith("#") or _ESQUEMA.match(alvo):
            return alvo
        caminho, _, ancora = alvo.partition("#")
        relativo = os.path.normpath(os.path.join(os.path.dirname(self.origem), unquote(caminho)))
        relativo = relativo.replace(os.sep, "/")
        sufixo = f"#{ancora}" if ancora else ""
        if relativo in self.publicados:
            return self.publicados[relativo] + sufixo
        existe = (self.raiz / relativo).exists() and not relativo.startswith("..")
        if existe and relativo.lower().endswith(SUFIXOS_DE_IMAGEM):
            nome = f"images/{Path(relativo).name}"
            if self.imagens.setdefault(nome, relativo) != relativo:
                raise ValueError(f"duas imagens com o mesmo nome na Wiki: {nome}")
            return nome
        if existe and (relativo in LINKAVEIS_NA_RAIZ or relativo.startswith(LINKAVEIS)):
            return url_do(relativo, pasta=(self.raiz / relativo).is_dir()) + sufixo
        if not existe:
            self.avisos.append(f"{self.origem}: link para arquivo que não existe: {relativo}")
        return None


def _sem_link(trecho: str, ctx: Contexto) -> str:
    def troca(m: re.Match[str]) -> str:
        if m.group("t2") is not None:
            novo = ctx.destino(m.group("t2"))
            return f"]({novo if novo is not None else REPO}{m.group('ti2') or ''})"
        novo = ctx.destino(m.group("t"))
        if novo is None:
            return m.group("txt")           # a imagem ou o link sem destino: só o texto
        texto = m.group("txt")
        pagina = novo.partition("#")[0]
        if not m.group("img") and pagina in ctx.titulos and re.search(r"\.md\b|/", texto):
            texto = ctx.titulos[pagina]     # o texto era o caminho do arquivo: na Wiki vira o título
        return f"{m.group('img')}[{texto}]({novo}{m.group('ti') or ''})"

    trecho = _LINK.sub(troca, trecho)

    def atributo(m: re.Match[str]) -> str:
        novo = ctx.destino(m.group("t"))
        return f'{m.group("a")}="{novo}"' if novo is not None else ""

    return _ATRIBUTO.sub(atributo, trecho)


def reescrever(texto: str, origem: str, ctx: Contexto) -> str:
    """Os links da fonte, trocados pelos da Wiki; o que está em bloco ou trecho de código não muda."""
    ctx.origem = origem
    saida: list[str] = []
    em_codigo = False
    for linha in texto.split("\n"):
        if linha.lstrip().startswith(("```", "~~~")):
            em_codigo = not em_codigo
            saida.append(linha)
            continue
        if em_codigo:
            saida.append(linha)
            continue
        definicao = _DEFINICAO.match(linha)
        if definicao:
            novo = ctx.destino(definicao.group("t"))
            if novo is not None:
                linha = definicao.group("ini") + novo + linha[definicao.end():]
            else:
                linha = ""
        partes = re.split(r"(`+[^`]*`+)", linha)
        saida.append("".join(p if i % 2 else _sem_link(p, ctx) for i, p in enumerate(partes)))
    return "\n".join(saida)


# ---------------------------------------------------------------------------
# As páginas
# ---------------------------------------------------------------------------


def _cabeca(fonte: str) -> str:
    return f"<!-- gerado por scripts/wiki/gerar.py a partir de {fonte}; não edite aqui -->\n"


def _pe(fonte: str) -> str:
    return f"\n\n---\nEsta página é gerada de [`{fonte}`]({url_do(fonte)}); corrija lá.\n"


def _fontes_md(raiz: Path, pasta: str) -> list[str]:
    base = raiz / pasta
    if not base.is_dir():
        return []
    return sorted(f"{pasta}/{p.name}" for p in base.glob("*.md"))


def fontes_publicadas(raiz: Path, fora: dict[str, str]) -> dict[str, tuple[str, str]]:
    """fonte → (prefixo da página, grupo): o que `docs/usage` e `docs/protocol` mandam para a Wiki."""
    achados: dict[str, tuple[str, str]] = {}
    for pasta, prefixo, grupo in ((USO, "Usar", "Usar"), (PROTOCOLO, "Protocolo", "O protocolo")):
        for fonte in _fontes_md(raiz, pasta):
            if fonte not in fora:
                achados[fonte] = (prefixo, grupo)
    return achados


def _celula(texto: str) -> str:
    return " ".join(texto.replace("|", "\\|").split())


def _lado(linha: dict[str, str], p: str) -> str:
    aceita, aciona = linha.get(p + "aceita", "").strip(), linha.get(p + "aciona", "").strip()
    if not aceita:
        return "sem resposta"
    if aciona == "sim":
        return "funciona"
    if aceita in ("sim", "parcial"):
        return "aceita, o efeito não foi visto"
    return "não"


def _prova(linha: dict[str, str], p: str, escada: dict[str, str]) -> str:
    if not linha.get(p + "aceita", "").strip():
        return "—"
    origem = ORIGEM.get(linha.get(p + "de_onde_sei", "").strip(), linha.get(p + "de_onde_sei", "").strip())
    ate = escada.get(linha.get(p + "ate_onde_foi", "").strip(), "")
    return "; ".join(x for x in (origem, ate) if x) or "—"


def _escada() -> dict[str, str]:
    """valor do degrau → o resumo dele, lidos do portão do mapa (uma fonte só)."""
    portao = filtros.carregar("check_paridade_transporte")
    return {d.valor: d.resumo for d in portao.ESCADA}


def ler_mapa(raiz: Path) -> list[dict[str, str]]:
    with open(raiz / MAPA, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _paginas_do_mapa(raiz: Path, wiki: Wiki, seguradas: set[str]) -> None:
    linhas = ler_mapa(raiz)
    escada = _escada()
    ordem = {c: i for i, (c, _) in enumerate(CONTROLES)}
    rotulo = dict(CONTROLES)
    # A ordem de `FAMILIAS` (a de quem lê: gatilhos, luz, som…), e a família que ela não conhece vai ao fim.
    posicao = {f: i for i, f in enumerate(FAMILIAS)}
    familias = sorted({ln["familia"] for ln in linhas}, key=lambda f: (posicao.get(f, len(posicao)), f))
    nomes = {f: f"Mapa-{ascii_minusculo(FAMILIAS.get(f, f))}" for f in familias}
    indice = ["# O mapa dos controles", "",
              "Cada recurso do controle, no cabo e no Bluetooth, com até onde foi provado:", ""]
    for degrau, resumo in escada.items():
        indice.append(f"- **{degrau.lower()}**: {resumo}")
    indice += ["", "| Família | Recursos |", "| --- | ---: |"]
    for fam in familias:
        chaves = {ln["chave"] for ln in linhas if ln["familia"] == fam}
        if nomes[fam] in seguradas:
            indice.append(f"| {FAMILIAS.get(fam, fam)} | {len(chaves)} |")
        else:
            indice.append(f"| [{FAMILIAS.get(fam, fam)}]({nomes[fam]}) | {len(chaves)} |")
    indice_no_ar = "Mapa-dos-controles" not in seguradas
    if indice_no_ar:
        wiki.paginas["Mapa-dos-controles"] = Pagina(
            "Mapa-dos-controles", "O mapa dos controles", MAPA, "O mapa dos controles",
            _cabeca(MAPA) + "\n".join(indice) + _pe(MAPA))
    for fam in familias:
        if nomes[fam] in seguradas:
            continue
        titulo = FAMILIAS.get(fam, fam)
        wiki.paginas[nomes[fam]] = Pagina(nomes[fam], titulo, MAPA, "O mapa dos controles",
                                          posicao=1 + familias.index(fam))
        deles = sorted((ln for ln in linhas if ln["familia"] == fam),
                       key=lambda ln: (ln["chave"], ordem.get(ln["controle"], 99)))
        texto = [f"# O mapa dos controles: {titulo}", "",
                 "| Recurso | Controle | Existe | Cabo | Bluetooth | Prova no cabo | Prova no Bluetooth |",
                 "| --- | --- | --- | --- | --- | --- | --- |"]
        for ln in deles:
            texto.append("| " + " | ".join(_celula(c) for c in (
                ln["rotulo"], rotulo.get(ln["controle"], ln["controle"]),
                EXISTE.get(ln["existe"], ln["existe"]), _lado(ln, "cabo_"), _lado(ln, "radio_"),
                _prova(ln, "cabo_", escada), _prova(ln, "radio_", escada))) + " |")
        volta = "[Voltar ao mapa dos controles](Mapa-dos-controles)\n\n" if indice_no_ar else ""
        wiki.paginas[nomes[fam]].corpo = _cabeca(MAPA) + volta + "\n".join(texto) + _pe(MAPA)


def montar(raiz: Path, *, fora: dict[str, str] | None = None, seguradas: set[str] | None = None) -> Wiki:
    """A Wiki inteira, lida da árvore `raiz`. `seguradas` são páginas que os filtros barraram."""
    fora = FORA if fora is None else fora
    seguradas = seguradas or set()
    wiki = Wiki()
    fontes = fontes_publicadas(raiz, fora)
    publicados: dict[str, str] = {}
    for fonte, (prefixo, _) in fontes.items():
        nome = f"{prefixo}-{ascii_minusculo(Path(fonte).stem)}"
        if nome in publicados.values():
            raise ValueError(f"duas fontes com o mesmo nome de página: {nome}")
        if nome not in seguradas:
            publicados[fonte] = nome
    if (raiz / LEIAME).is_file() and "Home" not in seguradas:
        publicados[LEIAME] = "Home"
    titulos = {nome: titulo_do((raiz / f).read_text(encoding="utf-8"), Path(f).stem)
               for f, nome in publicados.items() if f != LEIAME}
    ctx = Contexto(raiz, publicados, wiki.imagens, wiki.avisos, titulos)
    for fonte, (prefixo, grupo) in fontes.items():
        nome = f"{prefixo}-{ascii_minusculo(Path(fonte).stem)}"
        if nome in seguradas:
            continue
        texto = (raiz / fonte).read_text(encoding="utf-8")
        wiki.paginas[nome] = Pagina(
            nome, titulo_do(texto, Path(fonte).stem), fonte, grupo,
            _cabeca(fonte) + reescrever(texto.rstrip("\n"), fonte, ctx) + _pe(fonte))
    if (raiz / MAPA).is_file():
        _paginas_do_mapa(raiz, wiki, seguradas)
    if (raiz / LEIAME).is_file() and "Home" not in seguradas:
        texto = (raiz / LEIAME).read_text(encoding="utf-8")
        wiki.paginas["Home"] = Pagina("Home", "Início", LEIAME, "Início",
                                      _cabeca(LEIAME) + reescrever(texto.rstrip("\n"), LEIAME, ctx))
    _navegacao(wiki)
    return wiki


def _navegacao(wiki: Wiki) -> None:
    """A barra lateral, o rodapé e o «Nesta Wiki» do início, tudo da lista de páginas."""
    grupos: dict[str, list[Pagina]] = {}
    for p in sorted(wiki.paginas.values(), key=lambda q: (q.posicao, q.nome)):
        if p.nome != "Home":
            grupos.setdefault(p.grupo, []).append(p)
    ordem = ["Usar", "O mapa dos controles", "O protocolo"]
    nomes = [g for g in ordem if g in grupos] + sorted(g for g in grupos if g not in ordem)

    def lista(prefixo_titulo: str) -> list[str]:
        saida: list[str] = []
        for g in nomes:
            saida += ["", f"{prefixo_titulo} {g}", ""]
            saida += [f"- [{p.titulo}]({p.nome})" for p in grupos[g]]
        return saida

    if "Home" in wiki.paginas:
        wiki.paginas["Home"].corpo += "\n\n## Nesta Wiki\n" + "\n".join(lista("###")) + _pe(LEIAME)
    barra = ["**[Início](Home)**", *lista("###")]
    wiki.paginas["_Sidebar"] = Pagina("_Sidebar", "", "", "", _cabeca("docs/") + "\n".join(barra) + "\n")
    wiki.paginas["_Footer"] = Pagina(
        "_Footer", "", "", "",
        _cabeca("docs/") + f"Esta Wiki é gerada do [repositório]({REPO}): cada página diz de qual arquivo "
        "nasce, e a correção se faz lá, não aqui.\n")


# ---------------------------------------------------------------------------
# A régua: toda página tem a fonte no alto, todo link interno resolve
# ---------------------------------------------------------------------------


def links_internos(texto: str) -> list[str]:
    """Os alvos relativos de uma página (os de rede, as âncoras e o que está em código ficam de fora)."""
    achados: list[str] = []
    em_codigo = False
    for linha in texto.split("\n"):
        if linha.lstrip().startswith(("```", "~~~")):
            em_codigo = not em_codigo
            continue
        if em_codigo:
            continue
        for i, parte in enumerate(re.split(r"(`+[^`]*`+)", linha)):
            if i % 2:
                continue
            for m in _LINK.finditer(parte):
                achados.append(m.group("t") or m.group("t2"))
            achados += [m.group("t") for m in _ATRIBUTO.finditer(parte)]
    return [a for a in achados if a and not a.startswith("#") and not _ESQUEMA.match(a)]


def links_quebrados(arquivos: dict[str, str], imagens: set[str]) -> list[str]:
    """Os links relativos que não dão em página, nem em imagem da Wiki."""
    paginas = {n.removesuffix(".md") for n in arquivos}
    ruins: list[str] = []
    for nome, texto in sorted(arquivos.items()):
        for alvo in links_internos(texto):
            caminho = unquote(alvo.partition("#")[0])
            if caminho in paginas or caminho in imagens:
                continue
            ruins.append(f"{nome}: {alvo}")
    return ruins


def paginas_sem_fonte(arquivos: dict[str, str]) -> list[str]:
    """As páginas que não abrem com o cabeçalho da fonte (texto escrito à mão não tem)."""
    return [n for n, t in sorted(arquivos.items()) if not t.startswith("<!-- gerado por scripts/wiki/gerar.py")]


# ---------------------------------------------------------------------------
# Gerar, conferir, escrever
# ---------------------------------------------------------------------------


@dataclass
class Resultado:
    wiki: Wiki
    seguradas: dict[str, list[str]]
    nao_medido: list[str]


def gerar(raiz: Path, *, fora: dict[str, str] | None = None, lar: Path | None = None,
          filtrar: bool = True) -> Resultado:
    """Monta, filtra, e refaz sem as páginas barradas até estabilizar (os links delas voltam ao repositório)."""
    seguradas: dict[str, list[str]] = {}
    for _ in range(4):
        wiki = montar(raiz, fora=fora, seguradas=set(seguradas))
        if not filtrar:
            return Resultado(wiki, {}, [])
        veredito = filtros.medir({n: p.corpo for n, p in wiki.paginas.items()}, lar=lar)
        if veredito.nao_medido:
            return Resultado(wiki, {}, veredito.nao_medido)
        novas = {n: m for n, m in veredito.seguradas.items() if n not in seguradas}
        if not novas:
            return Resultado(wiki, seguradas, [])
        seguradas.update(novas)
    raise RuntimeError("os filtros não estabilizaram em quatro voltas")


def conteudo_da_saida(wiki: Wiki, raiz: Path) -> dict[str, bytes]:
    """caminho relativo → bytes de tudo o que a Wiki leva (páginas e imagens)."""
    saida = {f"{n}.md": p.corpo.encode("utf-8") for n, p in wiki.paginas.items()}
    for destino, origem in wiki.imagens.items():
        saida[destino] = (raiz / origem).read_bytes()
    return saida


def _do_disco(pasta: Path) -> dict[str, bytes]:
    achados: dict[str, bytes] = {}
    if pasta.is_dir():
        for p in sorted(pasta.rglob("*")):
            relativo = p.relative_to(pasta).as_posix()
            if p.is_file() and relativo != ".git" and not relativo.startswith(".git/"):
                achados[relativo] = p.read_bytes()
    return achados


def diferenca(esperado: dict[str, bytes], no_disco: dict[str, bytes]) -> list[str]:
    return sorted(
        [f"falta {n}" for n in esperado if n not in no_disco]
        + [f"a mais {n}" for n in no_disco if n not in esperado]
        + [f"muda {n}" for n in esperado if n in no_disco and esperado[n] != no_disco[n]])


def recusa_da_saida(pasta: Path, raiz: Path) -> str | None:
    """Por que `pasta` não pode receber a Wiki, ou None. A escrita apaga o que a Wiki não leva.

    A saída nunca é a árvore de onde a Wiki nasce (nem uma pasta acima dela), e uma pasta que já
    tem arquivos só é Wiki se tem a página de início ou a barra lateral: um `--saida` trocado não
    apaga o repositório de ninguém.
    """
    alvo, origem = pasta.resolve(), raiz.resolve()
    if alvo == origem or alvo in origem.parents:
        return f"{pasta} contém a árvore de origem"
    no_disco = _do_disco(pasta)
    if no_disco and not {"Home.md", "_Sidebar.md"} & set(no_disco):
        return f"{pasta} tem arquivos e não é uma Wiki (sem Home.md nem _Sidebar.md)"
    return None


def escrever(esperado: dict[str, bytes], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for n in set(_do_disco(pasta)) - set(esperado):
        (pasta / n).unlink()
    for n, dados in esperado.items():
        alvo = pasta / n
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not alvo.is_file() or alvo.read_bytes() != dados:
            alvo.write_bytes(dados)


def impressao_das_fontes(raiz: Path, wiki: Wiki) -> str:
    """O recibo: um hash do que a Wiki leva e dos arquivos que a geraram."""
    h = hashlib.sha256()
    for n, dados in sorted(conteudo_da_saida(wiki, raiz).items()):
        h.update(n.encode() + b"\0" + dados + b"\0")
    return h.hexdigest()[:16]


def principal(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    ap.add_argument("--conferir", action="store_true")
    ap.add_argument("--sem-filtros", action="store_true",
                    help="só gera, sem os filtros (nunca para publicar)")
    ap.add_argument("--lar", type=Path, default=None,
                    help="um lar de mentira para a pergunta dos endereços da máquina")
    ap.add_argument("--detalhe", type=Path, default=None, help="onde escrever o detalhe (páginas, avisos, achados)")
    ap.add_argument("--recibo", type=Path, default=None, help="pasta do recibo (um arquivo por conteúdo gerado)")
    a = ap.parse_args(argv)
    raiz = a.raiz.resolve()
    r = gerar(raiz, lar=a.lar, filtrar=not a.sem_filtros)
    detalhe = [f"página {n}: {p.fonte or '(navegação)'}" for n, p in sorted(r.wiki.paginas.items())]
    detalhe += [f"imagem {d}: {o}" for d, o in sorted(r.wiki.imagens.items())]
    detalhe += [f"aviso: {x}" for x in r.wiki.avisos]
    detalhe += [f"segurada: {m}" for ms in r.seguradas.values() for m in ms]
    detalhe += [f"NÃO MEDIDO: {m}" for m in r.nao_medido]
    if a.detalhe:
        a.detalhe.write_text("\n".join(detalhe) + "\n", encoding="utf-8")
    if r.nao_medido:
        print(f"wiki: NÃO MEDIDO, nada escrito ({'; '.join(r.nao_medido)})", file=sys.stderr)
        return 3
    esperado = conteudo_da_saida(r.wiki, raiz)
    marcas = f"{len(r.wiki.paginas)} páginas, {len(r.wiki.imagens)} imagens, {len(r.seguradas)} seguradas"
    if a.conferir:
        dif = diferenca(esperado, _do_disco(a.saida))
        print(f"wiki: {marcas}; conferir: {'igual' if not dif else str(len(dif)) + ' diferença(s)'}")
        if a.detalhe:
            with a.detalhe.open("a", encoding="utf-8") as fh:
                fh.write("".join(f"conferir: {d}\n" for d in dif))
        else:
            for d in dif[:40]:
                print(f"  {d}")
        return 1 if dif or r.seguradas else 0
    recusa = recusa_da_saida(a.saida, raiz)
    if recusa:
        print(f"wiki: RECUSADO, nada escrito ({recusa})", file=sys.stderr)
        return 2
    escrever(esperado, a.saida)
    if a.recibo:
        a.recibo.mkdir(parents=True, exist_ok=True)
        (a.recibo / f"wiki.{impressao_das_fontes(raiz, r.wiki)}").write_text(marcas + "\n", encoding="utf-8")
    print(f"wiki: {marcas}; escrito em {a.saida}")
    if not a.detalhe:   # com `--detalhe`, a lista mora no arquivo e o terminal fica no resumo
        for m in (m for ms in r.seguradas.values() for m in ms):
            print(f"  segurada: {m}", file=sys.stderr)
    return 1 if r.seguradas else 0


if __name__ == "__main__":
    sys.exit(principal())
