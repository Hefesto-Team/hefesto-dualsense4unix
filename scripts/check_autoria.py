#!/usr/bin/env python3
"""Quem assina a história e o que o texto carrega: uma régua só, no gancho, nos portões e no CI.

Só assinam as pessoas do `.mailmap` (autor, committer e tagger, nome e endereço); linha
de atribuição só com o endereço delas; termos internos que não se publicam, de uma lista
fora do repositório. A saída nunca imprime o termo nem a linha que casou: o log do CI é público.

Modos:
  historia [REV...]       tudo o que as REVs alcançam (padrão: dev, main, HEAD e as tags)
  pre-push REMOTO URL     o que o push leva (lê o stdin do gancho)
  arvore [REV]            nome e conteúdo dos arquivos (padrão: a árvore de trabalho)
  diff BASE TOPO          as linhas acrescentadas e as mensagens do intervalo
  remoto REMOTO           as referências que o servidor guarda
  texto                   o que chega pelo stdin (título e corpo de PR, nota de release)

A lista: `AUTORIA_VEDADOS` (o conteúdo, no CI) ou o arquivo que `git config autoria.vedados`
aponta. Uma linha por termo: `1 <termo>`, `2 <Termo>` ou `1 re:<expressão>`. Sem lista,
a parte de vocabulário sai «NÃO MEDIDO» e o código de saída é 1.
"""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# O push e o pack não obedecem a `refs/replace/*`, e o `git log` obedece: a história
# medida é a que VIAJA.
os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"

ZERO = "0" * 40
PUBLICAVEIS_PADRAO = (
    "refs/heads/dev",
    "refs/heads/main",
    "refs/tags/v*",
    "refs/heads/fecho/*",
)
# De onde um push pode PARTIR: ramo, tag, HEAD ou um SHA cru. Qualquer outro espaço de
# nomes (substituições, instantâneos, esconderijos, salvaguardas) nunca sai da máquina:
# a lista é de quem PODE, para não ter de nomear quem não.
ORIGENS = ("refs/heads/", "refs/tags/")
# O que o servidor pode guardar: ramos, tags e as referências de PR que ele mesmo cria.
NO_SERVIDOR = ("refs/heads/", "refs/tags/", "refs/pull/")
ATRIBUICAO = re.compile(
    r"^[ \t]*[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-(?:by|with|session)[ \t]*:(.*)$",
    re.I | re.M,
)
GITHUB_NOME = "GitHub"
GITHUB_ENDERECO = "noreply@github.com"
ESPACO_DO_TOKEN = re.compile(r"[A-Za-z0-9]+")


def git(*args: str, entrada: str | None = None, ok: bool = False) -> str:
    r = subprocess.run(["git", *args], input=entrada, capture_output=True, text=True)
    if r.returncode != 0 and not ok:
        sys.exit(f"autoria: git {' '.join(args[:2])} falhou: {r.stderr.strip()[:200]}")
    return r.stdout


# ---------------------------------------------------------------------------
# A lista de termos: fora do repositório, e a régua nunca a imprime.
# ---------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    if texto.isascii():
        return texto
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c))


def _tokens(texto: str, caixa: bool) -> list[str]:
    t = _sem_acento(texto)
    return ESPACO_DO_TOKEN.findall(t if caixa else t.lower())


class Lista:
    """Os termos vedados, indexados pelo primeiro token de cada um."""

    def __init__(self, linhas: list[str]) -> None:
        self.nivel1: dict[str, list[tuple[str, ...]]] = {}
        self.nivel2: dict[str, list[tuple[str, ...]]] = {}
        self.expressoes: list[re.Pattern[str]] = []
        self.invalidas = 0
        for bruta in linhas:
            linha = bruta.strip()
            if not linha or linha.startswith("#"):
                continue
            nivel, _, termo = linha.partition(" ")
            termo = termo.strip()
            if nivel not in ("1", "2") or not termo:
                self.invalidas += 1
                continue
            if termo.startswith("re:"):
                try:
                    self.expressoes.append(re.compile(termo[3:]))
                except re.error:
                    self.invalidas += 1
                continue
            toks = tuple(_tokens(termo, caixa=nivel == "2"))
            if toks:
                alvo = self.nivel1 if nivel == "1" else self.nivel2
                alvo.setdefault(toks[0], []).append(toks)

    def vazia(self) -> bool:
        return not (self.nivel1 or self.nivel2 or self.expressoes)

    @staticmethod
    def _casa(tokens: list[str], indice: dict[str, list[tuple[str, ...]]]) -> bool:
        for i, t in enumerate(tokens):
            for termo in indice.get(t, ()):
                if tuple(tokens[i:i + len(termo)]) == termo:
                    return True
        return False

    def vedado(self, texto: str, nivel: int = 1) -> bool:
        """O texto tem um termo do nível pedido? (nível 1: sem caixa; nível 2: com caixa)"""
        if nivel == 1:
            if self._casa(_tokens(texto, caixa=False), self.nivel1):
                return True
            return any(e.search(texto) for e in self.expressoes)
        return self._casa(_tokens(texto, caixa=True), self.nivel2)

    def pode_ter_termo(self, texto: str) -> bool:
        """Peneira barata de um arquivo inteiro: false só quando NENHUM termo do nível 1 cabe."""
        if any(e.search(texto) for e in self.expressoes):
            return True
        return any(t in self.nivel1 for t in set(_tokens(texto, caixa=False)))


def _lista() -> Lista | None:
    """A lista do ambiente ou do arquivo do `autoria.vedados`; None quando ausente ou vazia."""
    texto = os.environ.get("AUTORIA_VEDADOS", "")
    if not texto.strip():
        caminho = git("config", "--get", "autoria.vedados", ok=True).strip()
        alvo = Path(caminho).expanduser() if caminho else None
        if alvo is None or not alvo.is_file():
            return None
        texto = alvo.read_text(encoding="utf-8")
    lista = Lista(texto.splitlines())
    return None if lista.vazia() else lista


# ---------------------------------------------------------------------------
# Quem pode: o `.mailmap`, com todos os `<…>` de cada linha.
# ---------------------------------------------------------------------------


def pessoas() -> tuple[frozenset[str], frozenset[str]]:
    raiz = git("rev-parse", "--show-toplevel", ok=True).strip() or "."
    alvo = Path(raiz) / ".mailmap"
    texto = alvo.read_text(encoding="utf-8") if alvo.is_file() else git("show", "HEAD:.mailmap", ok=True)
    nomes: set[str] = set()
    enderecos: set[str] = set()
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        for nome, endereco in re.findall(r"([^<>]*)<([^>]+)>", linha):
            if nome.strip():
                nomes.add(nome.strip())
            enderecos.add(endereco.strip().lower())
    if not enderecos:
        sys.exit("autoria: VERMELHO: o `.mailmap` não declara ninguém; não há contra o que medir.")
    return frozenset(nomes), frozenset(enderecos)


Casa = tuple[frozenset[str], frozenset[str]]


def _identidade(papel: str, nome: str, email: str, casa: Casa) -> list[str]:
    nomes, enderecos = casa
    ruins = []
    if email.strip("<>").lower() not in enderecos:
        ruins.append(f"{papel} com endereço fora do .mailmap")
    if nomes and nome not in nomes:
        ruins.append(f"{papel} com nome fora do .mailmap")
    return ruins


def _identidades_do_commit(an: str, ae: str, cn: str, ce: str, casa: Casa) -> list[str]:
    ruins = _identidade("autor", an, ae, casa)
    # A edição e o merge pelo botão do GitHub: o committer é o servidor, e só passa
    # quando o autor é da casa.
    if not ruins and cn == GITHUB_NOME and ce.strip("<>").lower() == GITHUB_ENDERECO:
        return ruins
    return ruins + _identidade("committer", cn, ce, casa)


def _mensagem(msg: str, casa: Casa, lista: Lista | None, nivel2: bool) -> list[str]:
    ruins = []
    for m in ATRIBUICAO.finditer(msg):
        if not any(e in m.group(1).lower() for e in casa[1]):
            ruins.append("linha de atribuição a quem não assina o projeto")
    if lista is not None:
        if lista.vedado(msg, 1):
            ruins.append("termo da lista na mensagem (nível 1)")
        if nivel2 and lista.vedado(msg, 2):
            ruins.append("termo da lista na mensagem (nível 2)")
    return ruins


# ---------------------------------------------------------------------------
# A história que viaja.
# ---------------------------------------------------------------------------


def commits(revs: list[str], nao: list[str] | None = None) -> list[tuple[str, ...]]:
    if not revs:
        return []
    bruto = git("log", "--no-color", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e",
                *revs, *(f"^{n}" for n in (nao or [])))
    return [tuple(r.strip("\n").split("\x1f", 5)) for r in bruto.split("\x1e") if r.strip("\n")]


def tags(nomes: list[str]) -> list[tuple[str, str, str]]:
    """(objeto da tag, tagger bruto, mensagem) de cada tag ANOTADA; o nome da tag não sai."""
    fora = []
    for t in nomes:
        if git("cat-file", "-t", t, ok=True).strip() != "tag":
            continue
        objeto = git("rev-parse", t, ok=True).strip()
        cab, _, msg = git("cat-file", "-p", t).partition("\n\n")
        tagger = next((ln[7:] for ln in cab.splitlines() if ln.startswith("tagger ")), "")
        fora.append((objeto, tagger, msg))
    return fora


def auditar(revs: list[str], novos_de: list[str] | None, casa: Casa, lista: Lista | None) -> list[str]:
    ruins = []
    for sha, an, ae, cn, ce, msg in commits(revs):
        probs = _identidades_do_commit(an, ae, cn, ce, casa) + _mensagem(msg, casa, lista, nivel2=False)
        ruins += [f"{sha[:9]}: {p}" for p in probs]
    # Nome de arquivo que um dia existiu: apagar do topo não tira da história.
    if lista is not None:
        primeiro: dict[str, str] = {}
        atual = ""
        saida = git("-c", "core.quotepath=off", "log", "--format=%x1e%H", "--name-only",
                    "--no-renames", *revs)
        for linha in saida.splitlines():
            if linha.startswith("\x1e"):
                atual = linha[1:]
            elif linha:
                primeiro.setdefault(linha, atual)
        for nome, sha in primeiro.items():
            if lista.vedado(nome, 1):
                ruins.append(f"{sha[:9]}: nome de arquivo da história com termo da lista (nível 1)")
        if novos_de is not None:
            for sha, *_x, msg in commits(revs, novos_de):
                if lista.vedado(msg, 2):
                    ruins.append(f"{sha[:9]}: termo da lista na mensagem (nível 2)")
    return ruins


def auditar_tags(nomes: list[str], casa: Casa, lista: Lista | None) -> list[str]:
    ruins = []
    for objeto, tagger, msg in tags(nomes):
        m = re.match(r"(.*?) <([^>]*)>", tagger)
        nome, email = (m.group(1), m.group(2)) if m else ("", "")
        for p in _identidade("tagger", nome, email, casa) + _mensagem(msg, casa, lista, False):
            ruins.append(f"tag {objeto[:9]}: {p}")
    return ruins


def _raso() -> bool:
    return git("rev-parse", "--is-shallow-repository", ok=True).strip() == "true"


def _revs_padrao() -> list[str]:
    revs = [r for r in ("refs/heads/dev", "refs/heads/main", "HEAD")
            if git("rev-parse", "--verify", "--quiet", r, ok=True).strip()]
    return revs + git("for-each-ref", "--format=%(refname)", "refs/tags").split()


def modo_historia(revs: list[str], lista: Lista | None) -> int:
    if _raso():
        return _veredito(["clone raso: a régua veria um commit só (use fetch-depth: 0)"], "historia", lista)
    revs = revs or _revs_padrao()
    if not revs:
        return _veredito(["nenhuma referência resolveu; nada foi medido"], "historia", lista)
    casa = pessoas()
    ruins = auditar(revs, None, casa, lista)
    ruins += auditar_tags([r for r in revs if r.startswith("refs/tags/")], casa, lista)
    return _veredito(ruins, f"{len(commits(revs))} commits", lista)


def _publicavel(ref: str) -> bool:
    padroes = git("config", "--get-all", "autoria.publicavel", ok=True).split() or list(PUBLICAVEIS_PADRAO)
    return any(fnmatch.fnmatchcase(ref, p) for p in padroes)


def _caminho(nome: str, lista: Lista) -> str:
    """O caminho para o log: cada componente que carrega termo da lista sai mascarado."""
    partes = nome.split("/")
    mascaradas = ["<…>" if lista.vedado(p, 1) else p for p in partes]
    if mascaradas == partes and lista.vedado(nome, 1):  # o termo atravessa a barra
        mascaradas[-1] = "<…>"
    return "/".join(mascaradas)


def _rotulo(ref: str, lista: Lista | None) -> str:
    """O nome da referência para o log: sem ele quando o nome carrega termo da lista."""
    if lista is None or lista.vedado(ref, 1):
        return "<referência omitida>"
    return ref


def modo_pre_push(remoto: str, lista: Lista | None) -> int:
    casa = pessoas()
    ruins: list[str] = []
    revs: list[str] = []
    tags_: list[str] = []
    novos_de: list[str] = []
    for linha in sys.stdin.read().splitlines():
        partes = linha.split()
        if len(partes) != 4:
            continue
        lref, lsha, rref, rsha = partes
        if lsha == ZERO:  # apagar no remoto é permitido
            continue
        if not (lref.startswith(ORIGENS) or lref == "HEAD" or re.fullmatch(r"[0-9a-f]{40}", lref)):
            ruins.append(f"{_rotulo(lref, lista)} -> {_rotulo(rref, lista)}: esta referência nunca sai da máquina")
            continue
        if not _publicavel(rref):
            ruins.append(f"{_rotulo(rref, lista)}: fora da lista de publicáveis (git config autoria.publicavel)")
            continue
        if lista is not None and lista.vedado(rref, 1):
            ruins.append("destino com termo da lista no nome (nível 1)")
            continue
        revs.append(lsha)
        if rref.startswith("refs/tags/"):
            tags_.append(lsha)
        if rsha != ZERO and subprocess.run(["git", "cat-file", "-e", rsha],
                                           capture_output=True).returncode == 0:
            novos_de.append(rsha)
    # O nível 2 mede só o que o push ACRESCENTA: a base é o que o remoto já tinha (o
    # valor antigo de cada ref e os ramos de rastreio DESTE remoto). Ramo de rastreio
    # velho só afrouxa o nível 2; o nível 1 mede a história inteira.
    novos_de += git("for-each-ref", "--format=%(objectname)", f"refs/remotes/{remoto}/").split()
    if _raso():
        ruins.append("clone raso: a história do push não pode ser medida inteira")
    if revs:
        ruins += auditar(revs, novos_de, casa, lista)
        ruins += auditar_tags(tags_, casa, lista)
    return _veredito(ruins, f"push para {remoto}", lista)


# ---------------------------------------------------------------------------
# A árvore, o diff, o texto e o servidor.
# ---------------------------------------------------------------------------


def _arquivos(rev: str | None) -> list[tuple[str, bytes]]:
    if rev:  # uma leitura só: `cat-file --batch` em vez de um `git show` por arquivo
        lista = [ln.split("\t", 1) for ln in git("ls-tree", "-r", "-z", "--full-tree", rev).split("\0") if ln]
        blobs = [(meta.split()[2], nome) for meta, nome in lista if meta.split()[1] == "blob"]
        saida = subprocess.run(["git", "cat-file", "--batch"], capture_output=True,
                               input="".join(f"{b}\n" for b, _ in blobs).encode()).stdout
        fora, pos = [], 0
        for _, nome in blobs:
            fim = saida.index(b"\n", pos)
            tamanho = int(saida[pos:fim].split()[2])
            fora.append((nome, saida[fim + 1:fim + 1 + tamanho]))
            pos = fim + 1 + tamanho + 1
        return fora
    nomes = git("-c", "core.quotepath=off", "ls-files", "-z", "--cached", "--others",
                "--exclude-standard").split("\0")
    return [(n, Path(n).read_bytes()) for n in nomes
            if n and os.path.isfile(n) and not os.path.islink(n)]


def modo_arvore(rev: str | None, lista: Lista | None) -> int:
    ruins: list[str] = []
    arquivos = _arquivos(rev)
    if lista is not None:
        for nome, dados in arquivos:
            if lista.vedado(nome, 1):
                ruins.append(f"{_caminho(nome, lista)}: termo da lista no nome do arquivo (nível 1)")
            if b"\0" in dados[:8192]:
                continue
            texto = dados.decode("utf-8", "replace")
            if not lista.pode_ter_termo(texto):
                continue
            for i, linha in enumerate(texto.splitlines(), 1):
                if lista.vedado(linha, 1):
                    ruins.append(f"{_caminho(nome, lista)}:{i}: termo da lista (nível 1)")
    return _veredito(ruins, f"{len(arquivos)} arquivos", lista)


def modo_diff(base: str, topo: str, lista: Lista | None) -> int:
    ruins: list[str] = []
    if lista is not None:
        atual = ""
        for linha in git("diff", "--no-ext-diff", "--no-color", "-U0", base, topo).splitlines():
            if linha.startswith("+++ "):
                atual = linha[6:] if linha.startswith("+++ b/") else linha[4:]
            elif linha.startswith("+") and lista.vedado(linha[1:], 1):
                ruins.append(f"{_caminho(atual, lista)}: linha acrescentada com termo da lista (nível 1)")
        # O nível 2 mede só a mensagem: no código ele barra o vocabulário legítimo do produto.
        for sha, *_x, msg in commits([topo], [base]):
            if lista.vedado(msg, 2):
                ruins.append(f"{sha[:9]}: termo da lista na mensagem (nível 2)")
    return _veredito(ruins, f"{base[:9]}..{topo[:9]}", lista)


def modo_remoto(remoto: str, lista: Lista | None) -> int:
    ruins: list[str] = []
    n = fora = 0
    for linha in git("ls-remote", remoto).splitlines():
        ref = linha.split("\t")[1]
        n += 1
        if ref == "HEAD":
            continue
        if not ref.startswith(NO_SERVIDOR):
            fora += 1
        elif lista is not None and lista.vedado(ref, 1):
            ruins.append("referência com termo da lista no nome (nível 1)")
    if fora:
        ruins.append(f"{fora} referência(s) fora de heads, tags e pull no servidor (nome omitido)")
    return _veredito(ruins, f"{n} referências em {remoto}", lista)


def modo_texto(lista: Lista | None) -> int:
    ruins: list[str] = []
    if lista is not None:
        for i, linha in enumerate(sys.stdin.read().splitlines(), 1):
            if lista.vedado(linha, 1):
                ruins.append(f"linha {i}: termo da lista (nível 1)")
            if lista.vedado(linha, 2):
                ruins.append(f"linha {i}: termo da lista (nível 2)")
    return _veredito(ruins, "texto", lista)


def _veredito(ruins: list[str], alcance: str, lista: Lista | None) -> int:
    unicos = sorted(set(ruins))
    if unicos:
        limite = int(os.environ.get("AUTORIA_LIMITE", "60"))
        print(f"autoria: VERMELHO: {len(unicos)} ocorrência(s) em {alcance}:")
        for r in unicos[:limite]:
            print(f"  {r}")
        if len(unicos) > limite:
            print(f"  … e mais {len(unicos) - limite}.")
    if lista is None:
        print("autoria: NÃO MEDIDO: a lista de termos não chegou (AUTORIA_VEDADOS ou "
              "`git config autoria.vedados`); a parte de vocabulário não foi medida.")
        return 1
    if unicos:
        return 1
    print(f"autoria: OK: {alcance}.")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    modo, resto = argv[0], argv[1:]
    if modo not in ("historia", "pre-push", "arvore", "diff", "remoto", "texto"):
        print(__doc__)
        return 2
    if modo == "diff" and len(resto) != 2:
        print(__doc__)
        return 2
    if modo == "remoto" and len(resto) != 1:
        print(__doc__)
        return 2
    lista = _lista()
    if modo == "historia":
        return modo_historia(resto, lista)
    if modo == "pre-push":
        return modo_pre_push(resto[0] if resto else "?", lista)
    if modo == "arvore":
        return modo_arvore(resto[0] if resto else None, lista)
    if modo == "diff":
        return modo_diff(resto[0], resto[1], lista)
    if modo == "remoto":
        return modo_remoto(resto[0], lista)
    return modo_texto(lista)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
