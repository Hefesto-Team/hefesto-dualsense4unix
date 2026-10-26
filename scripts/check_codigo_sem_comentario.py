#!/usr/bin/env python3
"""check_codigo_sem_comentario.py — o código versionado não tem comentário; só a diretiva fica.

A regra é a D-2610-O-CODIGO-NAO-TEM-COMENTARIO: nos cinco tipos (``.py``, ``.sh``, ``.html``, ``.js``,
``.css``, e o arquivo sem extensão que abre com ``#!`` de shell ou de Python), todo comentário reprova pelo
nome do arquivo e pela linha, menos a diretiva da lista ``DIRETIVAS``, na forma nua dela. O porquê que vale
guardar mora em ``docs/research/o-porque-dos-modulos.md``; a docstring fica, porque não é comentário.

Os comentários são lidos pelo analisador de cada linguagem, nunca por ``grep``: o ``tokenize`` no Python; no
shell, aspas, ``$#``, ``${#x}``, ``$(…)`` e heredoc respeitados; no JS, string, template e expressão
regular; no CSS, string; no HTML, o ``<!-- -->`` da marcação, o JS do ``<script>`` e o CSS do ``<style>``.

    scripts/check_codigo_sem_comentario.py              todo arquivo versionado no escopo (rc 1 se achou)
    scripts/check_codigo_sem_comentario.py ARQ...       só os arquivos dados
    scripts/check_codigo_sem_comentario.py --lista      um achado por linha, sem teto
    scripts/check_codigo_sem_comentario.py --diretivas  as diretivas da lista, com quem lê cada uma
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TIPOS = ("py", "sh", "html", "js", "css")
FORA = ("docs/",)
TETO_DA_SAIDA = 40


@dataclass(frozen=True)
class Diretiva:
    """Uma diretiva que fica, na forma nua, com os tipos onde vale e quem a lê.

    A ancorada abre o comentário (``# noqa: E501``, ``# type: ignore[x]``); a de linha (``noqa-acento``,
    ``serial-de-mentira``) vale em qualquer ponto dele, mas só colada em código na mesma linha, que é
    onde o leitor dela olha.
    """

    nome: str
    forma: re.Pattern[str]
    tipos: tuple[str, ...]
    leitor: str
    pastas: tuple[str, ...] = ()
    de_linha: bool = False
    nua: str = ""


def _d(nome: str, forma: str, tipos: tuple[str, ...], leitor: str, pastas: tuple[str, ...] = (),
       de_linha: bool = False, nua: str = "") -> Diretiva:
    return Diretiva(nome, re.compile(forma), tipos, leitor, pastas, de_linha, nua or nome)


_CODIGOS = r"[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*"
DIRETIVAS: tuple[Diretiva, ...] = (
    _d("type", r"type:\s*ignore(?:\[[\w\-, ]+\])?", ("py",), "mypy"),
    _d("noqa", rf"noqa(?::\s*{_CODIGOS})?(?![\w-])", ("py",), "ruff"),
    _d("pragma", r"pragma:\s*no\s+(?:cover|branch)", ("py",), "coverage"),
    _d("ruff", rf"ruff:\s*noqa(?::\s*{_CODIGOS})?", ("py",), "ruff"),
    _d("isort", r"isort:\s*(?:skip_file|skip|off|on)", ("py",), "isort"),
    _d("fmt", r"fmt:\s*(?:off|on|skip)", ("py",), "formatador"),
    _d("mypy", r"mypy:\s*[\w\-]+(?:\s*=\s*[\w\-,\"']+)?", ("py",), "mypy"),
    _d("shellcheck", r"shellcheck\s+(?:disable|enable|source|shell|external-sources)=\S+", ("sh",), "shellcheck"),
    _d("spdx", r"SPDX-[\w\-]+:\s*\S.*", TIPOS, "licença"),
    _d("eslint", r"eslint-(?:disable-next-line|disable-line|disable|enable)(?:\s+[\w/\-]+(?:,\s*[\w/\-]+)*)?",
       ("js", "html"), "eslint"),
    _d("ts", r"@ts-(?:check|nocheck|ignore|expect-error)", ("js", "html"), "tsc"),
    _d("sai-com", r"sai com:\s*[A-Z0-9][A-Z0-9\-]*[A-Z0-9]", ("py",),
       "tests/unit/test_toda_excecao_tem_sprint_que_a_tira.py", ("tests/", "scripts/")),
    _d("fica", r"fica:\s*\S.{19,}", ("py",),
       "tests/unit/test_toda_excecao_tem_sprint_que_a_tira.py", ("tests/", "scripts/")),
    _d("noqa-acento", r"noqa-acento|noqa: acentuacao", ("py", "sh"), "scripts/validar-acentuacao.py", de_linha=True,
       nua="(noqa-acento)"),
    _d("serial-de-mentira", r"serial-de-mentira", TIPOS, "scripts/check_numero_de_serie.py", de_linha=True),
)


LITERAIS: dict[str, str] = {
    "<!--LOGO-->": "src/hefesto_dualsense4unix/interface/monta.py",
}


@dataclass(frozen=True)
class Comentario:
    """Um comentário no texto: ``inicio`` e ``fim`` em índice de caractere, e o texto cru."""

    inicio: int
    fim: int
    texto: str
    linha: int
    abre: str


def _linha_de(texto: str, indice: int) -> int:
    return texto.count("\n", 0, indice) + 1


def _miolo(c: Comentario) -> str:
    t = c.texto
    if c.abre == "#":
        return t[1:].lstrip(":").strip()
    if c.abre == "//":
        return t[2:].strip()
    if c.abre == "/*":
        return t[2:-2].strip().strip("*").strip()
    return t[4:-3].strip()


def _colado_em_codigo(c: Comentario, texto: str) -> bool:
    if "\n" in c.texto:
        return False
    antes = texto.rfind("\n", 0, c.inicio) + 1
    depois = texto.find("\n", c.fim)
    depois = len(texto) if depois == -1 else depois
    return bool(texto[antes:c.inicio].strip() or texto[c.fim:depois].strip())


def _ancoradas(trecho: str, tipo: str, rel: str) -> list[str]:
    achadas = []
    pos = 0
    while pos < len(trecho):
        for d in DIRETIVAS:
            if d.de_linha or tipo not in d.tipos or (d.pastas and not rel.startswith(d.pastas)):
                continue
            m = d.forma.match(trecho, pos)
            if m:
                achadas.append(m.group(0).strip())
                pos = m.end()
                while pos < len(trecho) and trecho[pos] in " \t,;":
                    pos += 1
                break
        else:
            break
    return achadas


def _embrulhar(abre: str, partes: list[str]) -> str:
    if abre == "#":
        return "  ".join(f"# {p}" for p in partes)
    if abre == "//":
        return f"// {' '.join(partes)}"
    if abre == "/*":
        return f"/* {' '.join(partes)} */"
    return f"<!-- {' '.join(partes)} -->"


def forma_da_diretiva(c: Comentario, tipo: str, rel: str = "", texto: str | None = None) -> str | None:
    """A forma nua que o comentário guarda, se ele é diretiva; ``None`` se ele sai inteiro.

    Sem o ``texto`` em volta, a diretiva de linha conta como colada em código.
    """
    if c.abre == "#" and c.linha == 1 and c.texto.startswith("#!"):
        return c.texto
    if c.abre == "#" and c.linha <= 2 and re.match(r"#.*?coding[:=]\s*[-\w.]+", c.texto):
        return c.texto
    if c.texto in LITERAIS:
        return c.texto
    miolo = _miolo(c)
    trechos = [t.strip().lstrip(":").strip() for t in miolo.split("#")] if c.abre == "#" else [miolo]
    partes: list[str] = []
    for trecho in trechos:
        partes += _ancoradas(trecho, tipo, rel)
    if texto is None or _colado_em_codigo(c, texto):
        for d in DIRETIVAS:
            if d.de_linha and tipo in d.tipos and d.forma.search(miolo) and d.nua not in partes:
                partes.append(d.nua)
    if not partes:
        return None
    return _embrulhar(c.abre, partes)


def comentarios_py(texto: str) -> list[Comentario]:
    inicios = [0] + [m.end() for m in re.finditer("\n", texto)]
    achados = []
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        if tok.type == tokenize.COMMENT:
            (lin, col), (lin_fim, col_fim) = tok.start, tok.end
            ini = inicios[lin - 1] + col
            achados.append(Comentario(ini, inicios[lin_fim - 1] + col_fim, tok.string, lin, "#"))
    return achados


_PALAVRA_SH = set(" \t\n;&|()")


def _heredoc(texto: str, i: int) -> tuple[int, str, bool] | None:
    j = i + 2
    tira_tab = False
    if j < len(texto) and texto[j] == "-":
        tira_tab, j = True, j + 1
    while j < len(texto) and texto[j] in " \t":
        j += 1
    k = j
    delim = []
    while k < len(texto) and texto[k] not in " \t\n;&|()<>":
        ch = texto[k]
        if ch in "'\"":
            fecha = texto.index(ch, k + 1)
            delim.append(texto[k + 1:fecha])
            k = fecha + 1
            continue
        if ch == "\\":
            k += 1
            continue
        delim.append(ch)
        k += 1
    if not delim:
        return None
    return k, "".join(delim), tira_tab


def _fecha_parenteses(texto: str, i: int) -> int:
    profundidade = 0
    while i < len(texto):
        ch = texto[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            i = texto.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _fim_das_aspas(texto, i + 1)
            continue
        if ch == "(":
            profundidade += 1
        elif ch == ")":
            profundidade -= 1
            if profundidade == 0:
                return i + 1
        i += 1
    return i


def _fim_das_chaves(texto: str, i: int) -> int:
    profundidade = 1
    while i < len(texto):
        ch = texto[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'" and profundidade:
            i = texto.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _fim_das_aspas(texto, i + 1)
            continue
        if texto.startswith("${", i):
            i = _fim_das_chaves(texto, i + 2)
            continue
        if ch == "{":
            profundidade += 1
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                return i + 1
        i += 1
    return i


def _fim_das_aspas(texto: str, i: int) -> int:
    while i < len(texto):
        ch = texto[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return i + 1
        if texto.startswith("$((", i):
            i = _fecha_parenteses(texto, i + 1)
            continue
        if texto.startswith("$(", i):
            i = _fim_da_substituicao(texto, i + 2, [])
            continue
        if texto.startswith("${", i):
            i = _fim_das_chaves(texto, i + 2)
            continue
        if ch == "`":
            i = _fim_da_crase(texto, i + 1)
            continue
        i += 1
    return i


def _fim_da_crase(texto: str, i: int) -> int:
    while i < len(texto):
        if texto[i] == "\\":
            i += 2
            continue
        if texto[i] == "`":
            return i + 1
        i += 1
    return i


def _fim_da_substituicao(texto: str, i: int, achados: list[Comentario]) -> int:
    return _varrer_sh(texto, i, achados, dentro=True)


def _varrer_sh(texto: str, i: int, achados: list[Comentario], dentro: bool = False) -> int:
    pendentes: list[tuple[str, bool]] = []
    profundidade = 0
    casos = 0
    n = len(texto)
    while i < n:
        ch = texto[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "\n":
            i += 1
            for delim, tira_tab in pendentes:
                while i < n:
                    fim = texto.find("\n", i)
                    fim = n if fim == -1 else fim
                    linha = texto[i:fim]
                    i = fim + 1
                    if (linha.lstrip("\t") if tira_tab else linha) == delim:
                        break
            pendentes = []
            continue
        if ch == "#" and (i == 0 or texto[i - 1] in _PALAVRA_SH):
            fim = texto.find("\n", i)
            fim = n if fim == -1 else fim
            achados.append(Comentario(i, fim, texto[i:fim], _linha_de(texto, i), "#"))
            i = fim
            continue
        if ch == "'":
            i = texto.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _fim_das_aspas(texto, i + 1)
            continue
        if ch == "`":
            i = _fim_da_crase(texto, i + 1)
            continue
        if ch == "$":
            if texto.startswith("$'", i):
                i += 2
                while i < n and texto[i] != "'":
                    i += 2 if texto[i] == "\\" else 1
                i += 1
                continue
            if texto.startswith("$((", i):
                i = _fecha_parenteses(texto, i + 1)
                continue
            if texto.startswith("$(", i):
                i = _varrer_sh(texto, i + 2, achados, dentro=True)
                continue
            if texto.startswith("${", i):
                i = _fim_das_chaves(texto, i + 2)
                continue
            i += 2 if i + 1 < n and texto[i + 1] != "\n" else 1
            continue
        if texto.startswith("<<<", i):
            i += 3
            continue
        if texto.startswith("<<", i):
            lido = _heredoc(texto, i)
            if lido is not None:
                i, delim, tira_tab = lido
                pendentes.append((delim, tira_tab))
                continue
        if dentro:
            palavra = re.match(r"[A-Za-z_]+", texto[i:i + 5]) if (i == 0 or texto[i - 1] in _PALAVRA_SH) else None
            if palavra and palavra.group(0) == "case" and texto[i + 4:i + 5] in " \t\n":
                casos += 1
            elif palavra and palavra.group(0) == "esac" and texto[i + 4:i + 5] in " \t\n;)":
                casos -= 1
            if ch == "(":
                profundidade += 1
            elif ch == ")":
                if casos > 0 and profundidade == 0:
                    i += 1
                    continue
                if profundidade == 0:
                    return i + 1
                profundidade -= 1
        i += 1
    return i


def comentarios_sh(texto: str) -> list[Comentario]:
    achados: list[Comentario] = []
    _varrer_sh(texto, 0, achados)
    return achados


def comentarios_css(texto: str, base: int = 0, fim: int | None = None) -> list[Comentario]:
    achados = []
    i, n = base, len(texto) if fim is None else fim
    while i < n:
        ch = texto[i]
        if ch in "'\"":
            i += 1
            while i < n and texto[i] != ch and texto[i] != "\n":
                i += 2 if texto[i] == "\\" else 1
            i += 1
            continue
        if texto.startswith("/*", i):
            f = texto.find("*/", i + 2)
            f = n if f == -1 else f + 2
            achados.append(Comentario(i, f, texto[i:f], _linha_de(texto, i), "/*"))
            i = f
            continue
        i += 1
    return achados


_ANTES_DE_REGEX = set("(,=:[!&|?{};+-*%<>~^")
_PALAVRAS_DE_REGEX = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
                      "case", "do", "else", "yield", "await"}


def _regex_pode(texto: str, i: int, base: int) -> bool:
    j = i - 1
    while j >= base and texto[j] in " \t\r\n":
        j -= 1
    if j < base:
        return True
    ch = texto[j]
    if ch in _ANTES_DE_REGEX:
        return True
    if ch.isalnum() or ch in "_$":
        k = j
        while k >= base and (texto[k].isalnum() or texto[k] in "_$"):
            k -= 1
        return texto[k + 1:j + 1] in _PALAVRAS_DE_REGEX
    return False


def _varrer_js(texto: str, i: int, n: int, achados: list[Comentario], base: int, no_template: bool = False) -> int:
    chaves = 0
    while i < n:
        ch = texto[i]
        if no_template:
            if ch == "{":
                chaves += 1
            elif ch == "}":
                if chaves == 0:
                    return i + 1
                chaves -= 1
        if ch in "'\"":
            i += 1
            while i < n and texto[i] != ch and texto[i] != "\n":
                i += 2 if texto[i] == "\\" else 1
            i += 1
            continue
        if ch == "`":
            i += 1
            while i < n and texto[i] != "`":
                if texto[i] == "\\":
                    i += 2
                    continue
                if texto.startswith("${", i):
                    i = _varrer_js(texto, i + 2, n, achados, base, no_template=True)
                    continue
                i += 1
            i += 1
            continue
        if texto.startswith("//", i):
            f = texto.find("\n", i)
            f = n if f == -1 or f > n else f
            achados.append(Comentario(i, f, texto[i:f], _linha_de(texto, i), "//"))
            i = f
            continue
        if texto.startswith("/*", i):
            f = texto.find("*/", i + 2)
            f = n if f == -1 else f + 2
            achados.append(Comentario(i, f, texto[i:f], _linha_de(texto, i), "/*"))
            i = f
            continue
        if ch == "/" and _regex_pode(texto, i, base):
            i += 1
            classe = False
            while i < n and texto[i] != "\n":
                c = texto[i]
                if c == "\\":
                    i += 2
                    continue
                if c == "[":
                    classe = True
                elif c == "]":
                    classe = False
                elif c == "/" and not classe:
                    break
                i += 1
            i += 1
            continue
        i += 1
    return i


def comentarios_js(texto: str, base: int = 0, fim: int | None = None) -> list[Comentario]:
    achados: list[Comentario] = []
    n = len(texto) if fim is None else fim
    inicio = base
    if texto.startswith("#!", base):
        inicio = texto.find("\n", base)
        inicio = n if inicio == -1 else inicio
    _varrer_js(texto, inicio, n, achados, base)
    return achados


_BRUTOS = re.compile(r"<(script|style|textarea|title|xmp)\b([^>]*)>", re.I)
_TIPO_DO_SCRIPT = re.compile(r"""\btype\s*=\s*["']?([^"'\s>]+)""", re.I)
_SCRIPT_JS = {"", "text/javascript", "module", "application/javascript"}


def comentarios_html(texto: str) -> list[Comentario]:
    achados: list[Comentario] = []
    i, n = 0, len(texto)
    while i < n:
        if texto.startswith("<!--", i):
            f = texto.find("-->", i + 4)
            f = n if f == -1 else f + 3
            achados.append(Comentario(i, f, texto[i:f], _linha_de(texto, i), "<!--"))
            i = f
            continue
        m = _BRUTOS.match(texto, i) if texto[i] == "<" else None
        if m:
            nome = m.group(1).lower()
            fecho = re.compile(rf"</{nome}\s*>", re.I).search(texto, m.end())
            fim = n if fecho is None else fecho.start()
            if nome == "style":
                achados += comentarios_css(texto, m.end(), fim)
            elif nome == "script":
                tipo = _TIPO_DO_SCRIPT.search(m.group(2))
                if (tipo.group(1).lower() if tipo else "") in _SCRIPT_JS:
                    achados += comentarios_js(texto, m.end(), fim)
            i = n if fecho is None else fecho.end()
            continue
        if texto[i] == "<" and i + 1 < n and (texto[i + 1].isalpha() or texto[i + 1] == "/"):
            i = _fim_da_etiqueta(texto, i + 1, n)
            continue
        i += 1
    return achados


def _fim_da_etiqueta(texto: str, i: int, n: int) -> int:
    while i < n:
        ch = texto[i]
        if ch in "'\"":
            fecha = texto.find(ch, i + 1)
            i = n if fecha == -1 else fecha + 1
            continue
        if ch == ">":
            return i + 1
        i += 1
    return i


LEITORES = {
    "py": comentarios_py,
    "sh": comentarios_sh,
    "html": comentarios_html,
    "js": comentarios_js,
    "css": comentarios_css,
}


def comentarios(texto: str, tipo: str) -> list[Comentario]:
    """Os comentários de ``texto`` lidos pelo analisador de ``tipo``."""
    return LEITORES[tipo](texto)


def tipo_do_arquivo(rel: str, primeira_linha: str = "") -> str | None:
    """O tipo pelo sufixo; sem sufixo, pelo ``#!``. ``None``: fora do escopo."""
    if rel.startswith(FORA):
        return None
    nome = rel.rsplit("/", 1)[-1]
    if "." in nome:
        sufixo = nome.rsplit(".", 1)[1]
        return sufixo if sufixo in TIPOS else None
    if primeira_linha.startswith("#!"):
        if re.search(r"\b(bash|sh|dash|zsh)\b", primeira_linha):
            return "sh"
        if "python" in primeira_linha:
            return "py"
    return None


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, check=False)


def _primeira_linha(caminho: Path) -> str:
    try:
        with caminho.open("rb") as f:
            return f.readline(200).decode("utf-8", "replace")
    except OSError:
        return ""


def alvos(raiz: Path = RAIZ, arquivos: list[str] | None = None) -> list[tuple[str, str]]:
    """``(arquivo, tipo)`` de cada arquivo no escopo: os versionados, ou os dados."""
    if arquivos is None:
        feito = _git(raiz, "ls-files", "-z")
        if feito.returncode != 0:
            raise RuntimeError(f"git ls-files falhou: {feito.stderr.strip()}")
        arquivos = [a for a in feito.stdout.split("\0") if a]
    saida = []
    for rel in sorted(set(arquivos)):
        caminho = raiz / rel
        if not caminho.is_file() or caminho.is_symlink():
            continue
        tipo = tipo_do_arquivo(rel, _primeira_linha(caminho))
        if tipo is not None:
            saida.append((rel, tipo))
    return saida


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    texto: str

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha}: {self.texto[:100]}"


def achados_do_texto(texto: str, tipo: str, rel: str = "") -> list[Achado]:
    """Cada comentário de ``texto`` que não é diretiva nua."""
    try:
        lidos = comentarios(texto, tipo)
    except (tokenize.TokenError, SyntaxError, ValueError) as erro:
        return [Achado(rel, 0, f"o analisador de {tipo} não leu o arquivo: {type(erro).__name__}")]
    return [Achado(rel, c.linha, c.texto) for c in lidos if forma_da_diretiva(c, tipo, rel, texto) != c.texto]


def varrer(raiz: Path = RAIZ, arquivos: list[str] | None = None) -> list[Achado]:
    achados: list[Achado] = []
    for rel, tipo in alvos(raiz, arquivos):
        try:
            texto = (raiz / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            achados.append(Achado(rel, 0, "não é UTF-8"))
            continue
        achados += achados_do_texto(texto, tipo, rel)
    return achados


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument("arquivos", nargs="*")
    p.add_argument("--lista", action="store_true", help="todos os achados, sem teto")
    p.add_argument("--diretivas", action="store_true", help="a lista das diretivas e quem lê cada uma")
    p.add_argument("--raiz", default=None)
    a = p.parse_args(argv)
    raiz = Path(a.raiz).resolve() if a.raiz else RAIZ
    if a.diretivas:
        print("#!  na linha 1, e o coding nas linhas 1 e 2: o interpretador")
        for d in DIRETIVAS:
            pastas = f" (só em {', '.join(d.pastas)})" if d.pastas else ""
            print(f"{d.nome}: {d.forma.pattern}  [{', '.join(d.tipos)}]{pastas}  lida por {d.leitor}")
        for literal, leitor in LITERAIS.items():
            print(f"{literal}: inteiro, como está  [html]  lido por {leitor}")
        return 0
    pedidos = None
    if a.arquivos:
        pedidos = []
        for bruto in a.arquivos:
            caminho = Path(bruto)
            caminho = (caminho if caminho.is_absolute() else Path.cwd() / caminho).resolve()
            try:
                pedidos.append(caminho.relative_to(raiz).as_posix())
            except ValueError:
                continue
    achados = varrer(raiz, pedidos)
    if not achados:
        return 0
    print(f"check_codigo_sem_comentario: {len(achados)} comentário(s) em "
          f"{len({x.arquivo for x in achados})} arquivo(s). O código não tem comentário "
          "(D-2610-O-CODIGO-NAO-TEM-COMENTARIO): o porquê vai à docstring ou a "
          "docs/research/o-porque-dos-modulos.md; a diretiva fica nua (`--diretivas`).")
    mostrar = achados if a.lista else achados[:TETO_DA_SAIDA]
    for x in mostrar:
        print(x)
    if len(achados) > len(mostrar):
        print(f"(e mais {len(achados) - len(mostrar)}; `--lista` mostra todos)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
