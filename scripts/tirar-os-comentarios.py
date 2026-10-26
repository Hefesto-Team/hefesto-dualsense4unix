#!/usr/bin/env python3
"""tirar-os-comentarios.py — tira o comentário do código versionado, arquivo por arquivo, com a prova.

Quem diz o que é comentário e o que é diretiva é o portão, ``check_codigo_sem_comentario.py``; este script
só corta. A diretiva fica na forma nua; a linha que sobra só com espaço some; o bloco que sai não deixa
mais linhas em branco seguidas do que havia de cada lado dele.

A prova, por arquivo, antes de gravar (sem ela o arquivo fica como estava e sai na conta dos recusados):

* ``.py``: o ``ast.dump`` igual antes e depois;
* ``.sh``: o ``bash -n`` verde e o corpo que o próprio bash imprime (``declare -f`` de uma função que
  embrulha o arquivo, sem rodá-lo) igual antes e depois;
* ``.js`` e o ``<script>``: o programa que o TypeScript imprime sem comentário igual antes e depois, quando
  o TypeScript existe na máquina; senão, o fluxo de tokens sem comentário;
* ``.css`` e o ``<style>``: o fluxo de tokens sem comentário igual;
* ``.html``: os eventos do ``html.parser`` sem comentário iguais, com o espaço em branco do texto
  normalizado como o navegador o mostra, e o JS e o CSS de dentro pela prova deles.

    tirar-os-comentarios.py [ARQ...]            a conta, por tipo: comentários que saem e diretivas que ficam
    tirar-os-comentarios.py --aplicar [ARQ...]  grava o que provou
    tirar-os-comentarios.py --strings ARQ...    nas strings de página de um gerador (CSS, JS, HTML)
"""

from __future__ import annotations

import argparse
import ast
import collections
import dataclasses
import difflib
import html.parser
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
APAGADA = "\0apagada\0"
MARCA = "\x01"
TYPESCRIPT = (
    Path("/usr/share/code/resources/app/extensions/node_modules/typescript"),
    Path("/usr/lib/node_modules/typescript"),
)


def _portao() -> ModuleType:
    caminho = AQUI / "check_codigo_sem_comentario.py"
    spec = importlib.util.spec_from_file_location("check_codigo_sem_comentario", caminho)
    if spec is None or spec.loader is None:
        raise SystemExit(f"o portão não carrega: {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


G = _portao()


def _inicio_da_linha(texto: str, i: int) -> int:
    return texto.rfind("\n", 0, i) + 1


def _fim_da_linha(texto: str, i: int) -> int:
    f = texto.find("\n", i)
    return len(texto) if f == -1 else f


def limpar(texto: str, tipo: str, rel: str = "") -> tuple[str, int, int]:
    """``(texto sem comentário, comentários que saíram, diretivas que ficaram)``."""
    if MARCA in texto:
        raise ValueError("o texto já tem o caractere que marca o corte")
    trocas: list[tuple[int, int, str]] = []
    saiu = ficou = 0
    for c in G.comentarios(texto, tipo):
        forma = G.forma_da_diretiva(c, tipo, rel, texto)
        quebras = c.texto.count("\n")
        if forma is None:
            saiu += 1
            trocas.append((c.inicio, c.fim, "\n".join([MARCA] * (quebras + 1))))
        else:
            ficou += 1
            if forma != c.texto:
                trocas.append((c.inicio, c.fim, forma + ("\n" + MARCA) * quebras))
    if not trocas:
        novo, sobrou = _escapes_a_mais(texto, tipo, rel)
        return novo, saiu + sobrou, ficou - sobrou
    novo = texto
    for ini, fim, troca in sorted(trocas, reverse=True):
        novo = novo[:ini] + troca + novo[fim:]
    linhas = []
    for linha in novo.split("\n"):
        if MARCA not in linha:
            linhas.append(linha)
            continue
        if not linha.replace(MARCA, "").strip():
            linhas.append(APAGADA)
            continue
        linhas.append(_arrumar(linha))
    novo = _juntar_brancas("\n".join(linhas), texto.endswith("\n"))
    novo, sobrou = _escapes_a_mais(novo, tipo, rel)
    return novo, saiu + sobrou, ficou - sobrou


_VALIDADOR: list[ModuleType] = []


def _validador() -> ModuleType:
    if not _VALIDADOR:
        caminho = AQUI / "validar-acentuacao.py"
        spec = importlib.util.spec_from_file_location("validar_acentuacao_do_corte", caminho)
        if spec is None or spec.loader is None:
            raise SystemExit(f"o validador não carrega: {caminho}")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        _VALIDADOR.append(modulo)
    return _VALIDADOR[0]


_ESCAPE = re.compile(r"[ \t]*#[ \t]*\(?noqa-acento\)?")


def _escapes_a_mais(texto: str, tipo: str, rel: str) -> tuple[str, int]:
    """Tira o ``# noqa-acento`` que o validador não pede na linha dele: o que ele escapava saiu com o corte."""
    if tipo not in ("py", "sh"):
        return texto, 0
    marcas = [c for c in G.comentarios(texto, tipo) if "noqa-acento" in c.texto]
    if not marcas:
        return texto, 0
    val = _validador()
    precisa: set[int] = set()
    sufixo = Path(rel).suffix.lower()
    if not val.is_whitelisted(rel) and sufixo in val.EXTENSOES_ALVO:
        sem = texto
        for c in sorted(marcas, key=lambda c: c.inicio, reverse=True):
            sem = sem[:c.inicio] + _ESCAPE.sub("", c.texto) + sem[c.fim:]
        with tempfile.TemporaryDirectory() as pasta:
            alvo = Path(pasta) / f"x{sufixo}"
            alvo.write_text(sem, encoding="utf-8")
            precisa = {n for n, *_ in val.checar_arquivo(alvo, Path(pasta))}
    tirados = 0
    novo = texto
    for c in sorted(marcas, key=lambda c: c.inicio, reverse=True):
        if c.linha in precisa:
            continue
        resto = _ESCAPE.sub("", c.texto).strip()
        if resto:
            novo = novo[:c.inicio] + resto + novo[c.fim:]
        else:
            inicio = c.inicio
            while inicio > 0 and novo[inicio - 1] in " \t":
                inicio -= 1
            novo = novo[:inicio] + novo[c.fim:]
            tirados += 1
    return novo, tirados


def _arrumar(linha: str) -> str:
    """A linha que perdeu um comentário e guarda código: sem o espaço que ele deixa."""
    partes = linha.split(MARCA)
    texto = partes[0]
    for resto in partes[1:]:
        if not texto.strip():
            texto += resto.lstrip(" \t")
        elif not resto.strip():
            texto = texto.rstrip(" \t") + resto.strip(" \t")
        elif texto.endswith((" ", "\t")) and resto.startswith((" ", "\t")):
            texto += resto.lstrip(" \t")
        elif not texto.endswith((" ", "\t")) and not resto.startswith((" ", "\t")):
            texto += " " + resto
        else:
            texto += resto
    return texto.rstrip(" \t") if partes[-1].strip() == "" else texto


def _juntar_brancas(novo: str, termina_em_quebra: bool) -> str:
    """Cada bloco de linhas apagadas e brancas vira o maior trecho branco que havia nele."""
    linhas = novo.split("\n")
    saida: list[str] = []
    i = 0
    while i < len(linhas):
        if linhas[i] != APAGADA and not (linhas[i].strip() == "" and _toca_apagada(linhas, i)):
            saida.append(linhas[i])
            i += 1
            continue
        j = i
        maior = corrida = 0
        while j < len(linhas) and (linhas[j] == APAGADA or linhas[j].strip() == ""):
            if linhas[j] == APAGADA:
                corrida = 0
            else:
                corrida += 1
                maior = max(maior, corrida)
            j += 1
        if not any(linha == APAGADA for linha in linhas[i:j]):
            saida.extend(linhas[i:j])
        elif i == 0 or j == len(linhas):
            pass
        else:
            saida.extend([""] * maior)
        i = j
    texto = "\n".join(saida)
    if termina_em_quebra and texto and not texto.endswith("\n"):
        texto += "\n"
    return texto


def _toca_apagada(linhas: list[str], i: int) -> bool:
    j = i
    while j < len(linhas) and linhas[j].strip() == "" and linhas[j] != APAGADA:
        j += 1
    return j < len(linhas) and linhas[j] == APAGADA


class ProvaFalhou(Exception):
    """A prova do arquivo não fechou: ele não se grava."""


def _ast(texto: str) -> str:
    return ast.dump(ast.parse(texto))


def prova_py(antes: str, depois: str) -> None:
    if _ast(antes) != _ast(depois):
        raise ProvaFalhou("o ast.dump mudou")


def _bash_canonico(texto: str) -> str:
    embrulho = "__arquivo_inteiro__() {\n" + texto + ("" if texto.endswith("\n") else "\n") + "}\n"
    feito = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", 'eval "$(cat)" && declare -f __arquivo_inteiro__'],
        input=embrulho, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"},
        capture_output=True, text=True, check=False, timeout=60,
    )
    if feito.returncode != 0:
        raise ProvaFalhou(f"o bash não leu o arquivo embrulhado: {feito.stderr.strip()[:200]}")
    return feito.stdout


def prova_sh(antes: str, depois: str) -> None:
    feito = subprocess.run(["bash", "-n"], input=depois, capture_output=True, text=True, check=False, timeout=60)
    if feito.returncode != 0:
        raise ProvaFalhou(f"bash -n: {feito.stderr.strip()[:200]}")
    if _bash_canonico(antes) != _bash_canonico(depois):
        raise ProvaFalhou("o corpo que o bash imprime mudou")


def _typescript() -> Path | None:
    for pasta in TYPESCRIPT:
        if (pasta / "lib" / "typescript.js").is_file():
            return pasta
    return None


_IMPRESSOR_TS = r"""
const ts = require(process.argv[1]);
const entrada = JSON.parse(require("fs").readFileSync(0, "utf8"));
const impressor = ts.createPrinter({removeComments: true});
const saida = entrada.map((programa) => {
  const fonte = ts.createSourceFile("x.js", programa, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  if (fonte.parseDiagnostics && fonte.parseDiagnostics.length) {
    return "ERRO: " + ts.flattenDiagnosticMessageText(fonte.parseDiagnostics[0].messageText, "\n");
  }
  return impressor.printFile(fonte);
});
process.stdout.write(JSON.stringify(saida));
"""


def js_canonico(codigos: list[str]) -> list[str]:
    """O programa de cada código, impresso pelo TypeScript sem comentário (ou os tokens, sem ele)."""
    ts = _typescript()
    node = shutil.which("node")
    if ts is None or node is None:
        return [_tokens_js(c) for c in codigos]
    feito = subprocess.run([node, "-e", _IMPRESSOR_TS, str(ts / "lib" / "typescript.js")],
                           input=json.dumps(codigos), capture_output=True, text=True, check=False, timeout=300)
    if feito.returncode != 0:
        raise ProvaFalhou(f"o impressor do TypeScript falhou: {feito.stderr.strip()[:300]}")
    return list(json.loads(feito.stdout))


def _sem_trechos(texto: str, trechos: list[tuple[int, int]]) -> str:
    partes, pos = [], 0
    for ini, fim in sorted(trechos):
        partes.append(texto[pos:ini])
        partes.append(" ")
        pos = fim
    partes.append(texto[pos:])
    return "".join(partes)


def _tokens_js(codigo: str) -> str:
    sem = _sem_trechos(codigo, [(c.inicio, c.fim) for c in G.comentarios_js(codigo)])
    return " ".join(re.findall(r"\S+", sem))


def tokens_css(codigo: str) -> str:
    sem = _sem_trechos(codigo, [(c.inicio, c.fim) for c in G.comentarios_css(codigo)])
    return " ".join(re.findall(r"""[\w\-#.%]+|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s\w]""", sem))


def prova_js(antes: str, depois: str) -> None:
    a, b = js_canonico([antes, depois])
    if a.startswith("ERRO") or a != b:
        raise ProvaFalhou("o programa JS mudou" if not a.startswith("ERRO") else a)


def prova_css(antes: str, depois: str) -> None:
    if tokens_css(antes) != tokens_css(depois):
        raise ProvaFalhou("os tokens do CSS mudaram")


class _Eventos(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.eventos: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.estilos: list[str] = []
        self._bruto: str | None = None
        self._pre = 0

    def _texto(self, dado: str) -> None:
        if self.eventos and self.eventos[-1][0] == "texto":
            self.eventos[-1] = ("texto", self.eventos[-1][1] + dado)
        else:
            self.eventos.append(("texto", dado))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.eventos.append(("abre", f"{tag} {attrs!r}"))
        if tag in ("script", "style"):
            self._bruto = tag
        if tag in ("pre", "textarea"):
            self._pre += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.eventos.append(("abre-fecha", f"{tag} {attrs!r}"))

    def handle_endtag(self, tag: str) -> None:
        self.eventos.append(("fecha", tag))
        self._bruto = None
        if tag in ("pre", "textarea"):
            self._pre -= 1

    def handle_data(self, data: str) -> None:
        if self._bruto == "script":
            self.scripts.append(data)
            self.eventos.append(("script", ""))
        elif self._bruto == "style":
            self.estilos.append(data)
            self.eventos.append(("style", ""))
        elif self._pre:
            self._texto(data)
        else:
            self._texto(" " if not data.strip() else re.sub(r"\s+", " ", data))

    def handle_entityref(self, name: str) -> None:
        self._texto(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._texto(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self.eventos.append(("decl", decl))

    def handle_pi(self, data: str) -> None:
        self.eventos.append(("pi", data))


def _eventos(texto: str) -> _Eventos:
    p = _Eventos()
    p.feed(texto)
    p.close()
    p.eventos = [(t, re.sub(r"\s+", " ", d) if t == "texto" else d) for t, d in p.eventos]
    return p


def _js_dos_scripts(texto: str) -> list[str]:
    saida = []
    for m in G._BRUTOS.finditer(texto):
        if m.group(1).lower() != "script":
            continue
        tipo = G._TIPO_DO_SCRIPT.search(m.group(2))
        if (tipo.group(1).lower() if tipo else "") not in G._SCRIPT_JS:
            continue
        fecho = re.compile(r"</script\s*>", re.I).search(texto, m.end())
        saida.append(texto[m.end():fecho.start() if fecho else len(texto)])
    return saida


def prova_html(antes: str, depois: str) -> None:
    a, b = _eventos(antes), _eventos(depois)
    if a.eventos != b.eventos:
        for i, (x, y) in enumerate(zip(a.eventos, b.eventos, strict=False)):
            if x != y:
                raise ProvaFalhou(f"o evento {i} do HTML mudou: {x!r:.80} -> {y!r:.80}")
        raise ProvaFalhou("o número de eventos do HTML mudou")
    if [tokens_css(s) for s in a.estilos] != [tokens_css(s) for s in b.estilos]:
        raise ProvaFalhou("o CSS de um <style> mudou")
    ja, jb = _js_dos_scripts(antes), _js_dos_scripts(depois)
    if len(ja) != len(jb):
        raise ProvaFalhou("o número de <script> mudou")
    canon = js_canonico(ja + jb)
    for js_a, js_b in zip(canon[:len(ja)], canon[len(ja):], strict=True):
        if js_a.startswith("ERRO") or js_a != js_b:
            raise ProvaFalhou("o JS de um <script> mudou" if not js_a.startswith("ERRO") else js_a)


PROVAS: dict[str, Callable[[str, str], None]] = {
    "py": prova_py,
    "sh": prova_sh,
    "js": prova_js,
    "css": prova_css,
    "html": prova_html,
}


_ABRE_PAGINA = re.compile(r"/\*|<!--|//")


def _js_em_string(conteudo: str) -> bool:
    return bool(re.search(r"\b(?:function|const|let|var|return|document|window)\b|=>", conteudo))


def limpar_string_de_pagina(conteudo: str) -> str:
    """O miolo de uma string de gerador sem o comentário de CSS, de HTML e, se ela é JS, o de JS.

    O que a string não fecha (um ``/*`` sem ``*/`` dentro dela) fica como está.
    """
    if not _ABRE_PAGINA.search(conteudo):
        return conteudo
    if "\n" not in conteudo and "\\n" in conteudo and "\\\\" not in conteudo:
        return limpar_string_de_pagina(conteudo.replace("\\n", "\n")).replace("\n", "\\n")
    comeco = re.sub(r"^(?:\s+|/\*.*?\*/|//[^\n]*|<!--.*?-->)*", "", conteudo, flags=re.S)
    if not comeco.startswith("<") and _js_em_string(conteudo):
        return limpar(conteudo, "js")[0] if _fechados(conteudo, "js") else conteudo
    sem_css = _sem_trechos(conteudo, [(c.inicio, c.fim) for c in G.comentarios_css(conteudo)])
    if "<" in sem_css and re.search(r"</?[a-zA-Z][\w-]*[\s>/]|<!--", sem_css):
        return limpar(conteudo, "html")[0] if _fechados(conteudo, "html") else conteudo
    if _js_em_string(conteudo):
        return limpar(conteudo, "js")[0] if _fechados(conteudo, "js") else conteudo
    return limpar(conteudo, "css")[0] if _fechados(conteudo, "css") else conteudo


def _fechados(conteudo: str, tipo: str) -> bool:
    for c in G.comentarios(conteudo, tipo):
        if c.abre == "/*" and not c.texto.endswith("*/"):
            return False
        if c.abre == "<!--" and not c.texto.endswith("-->"):
            return False
    return True


def contar(arquivos: list[tuple[str, str]], raiz: Path) -> dict[str, collections.Counter[str]]:
    conta: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for rel, tipo in arquivos:
        _, sai, fica = limpar((raiz / rel).read_text(encoding="utf-8"), tipo, rel)
        conta[tipo]["sai"] += sai
        conta[tipo]["fica"] += fica
        conta[tipo]["arquivos"] += 1
    return conta


def aplicar(arquivos: list[tuple[str, str]], raiz: Path, gravar: bool) -> int:
    recusados = []
    gravados = 0
    for rel, tipo in arquivos:
        caminho = raiz / rel
        texto = caminho.read_text(encoding="utf-8")
        try:
            novo, _, _ = limpar(texto, tipo, rel)
            if novo == texto:
                continue
            PROVAS[tipo](texto, novo)
            resto = G.achados_do_texto(novo, tipo, rel)
            if resto:
                raise ProvaFalhou(f"sobrou comentário na linha {resto[0].linha}")
        except (ProvaFalhou, SyntaxError, ValueError, tokenize.TokenError) as erro:
            recusados.append(f"{rel}: {erro}")
            continue
        if gravar:
            caminho.write_text(novo, encoding="utf-8")
        gravados += 1
    print(f"{'gravados' if gravar else 'provados'}: {gravados}; recusados: {len(recusados)}")
    for r in recusados:
        print(f"  RECUSADO {r}")
    return 1 if recusados else 0


@dataclasses.dataclass
class _FAberta:
    tok: int
    miolo: int
    fundura: int = 0
    campo: int = 0
    campos: list[tuple[int, int]] = dataclasses.field(default_factory=list)


def _strings_do_gerador(texto: str) -> list[tuple[int, int, str, int, int, tuple[tuple[int, int], ...]]]:
    """Cada string não crua e não docstring de ``texto``.

    ``(início do miolo, fim do miolo, tipo, início do token, fim do token, campos)``; ``tipo`` é ``s`` ou ``f``,
    e ``campos`` são os ``{…}`` de primeiro nível da f-string, que a limpeza não toca.
    """
    inicios = [0] + [m.end() for m in re.finditer("\n", texto)]
    docstrings = set()
    for no in ast.walk(ast.parse(texto)):
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and no.body:
            primeiro = no.body[0]
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant) \
                    and isinstance(primeiro.value.value, str):
                docstrings.add((primeiro.value.lineno, primeiro.value.col_offset))
    saida: list[tuple[int, int, str, int, int, tuple[tuple[int, int], ...]]] = []
    abertas: list[_FAberta] = []
    inicio_f = getattr(tokenize, "FSTRING_START", None)
    fim_f = getattr(tokenize, "FSTRING_END", None)
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        (la, ca), (lb, cb) = tok.start, tok.end
        ini, fim = inicios[la - 1] + ca, inicios[lb - 1] + cb
        if inicio_f is not None and tok.type == inicio_f:
            abertas.append(_FAberta(ini, fim))
            continue
        if abertas:
            topo = abertas[-1]
            if tok.type == fim_f:
                abertas.pop()
                if not abertas:
                    saida.append((topo.miolo, ini, "f", topo.tok, fim, tuple(topo.campos)))
                continue
            if tok.type == tokenize.OP and tok.string == "{":
                if topo.fundura == 0:
                    topo.campo = ini
                topo.fundura += 1
            elif tok.type == tokenize.OP and tok.string == "}":
                topo.fundura -= 1
                if topo.fundura == 0:
                    topo.campos.append((topo.campo, fim))
            continue
        if tok.type == tokenize.STRING:
            if (la, ca) in docstrings:
                continue
            m = re.match(r"(?i)([bur]?)('''|\"\"\"|'|\")", tok.string)
            if m is None:
                continue
            abre = len(m.group(0))
            saida.append((ini + abre, fim - len(m.group(2)), "s", ini, fim, ()))
    return saida


_LUGAR = "\x02{}\x03"


def limpar_fstring(texto: str, ini: int, fim: int, campos: tuple[tuple[int, int], ...]) -> str:
    """O miolo de uma f-string limpo inteiro, com cada ``{…}`` guardado num lugar que não é espaço nem comentário."""
    partes = []
    pos = ini
    for k, (a, b) in enumerate(campos):
        partes.append(texto[pos:a])
        partes.append(_LUGAR.format(k))
        pos = b
    partes.append(texto[pos:fim])
    molde = "".join(partes)
    limpo = limpar_string_de_pagina(molde)
    if limpo == molde:
        return texto[ini:fim]
    for k, (a, b) in enumerate(campos):
        lugar = _LUGAR.format(k)
        if limpo.count(lugar) > 1:
            raise ValueError(f"o campo {texto[a:b]!r} da f-string apareceu duas vezes")
        limpo = limpo.replace(lugar, texto[a:b])
    if "\x02" in limpo or "\x03" in limpo:
        raise ValueError("sobrou um lugar de campo na f-string")
    return limpo


@dataclasses.dataclass
class _Pedaco:
    ini: int
    fim: int
    miolo_ini: int
    miolo_fim: int
    cru: bool = False


_ESCAPE_DE_STRING = re.compile(r"\\(?:\n|[\\'\"abfnrtv]|[0-7]{1,3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|N\{[^}]*\})")


def _grupos_de_strings(texto: str) -> list[list[_Pedaco]]:
    """As concatenações implícitas (``"a" "b"``) de duas ou mais strings comuns, sem prefixo."""
    inicios = [0] + [m.end() for m in re.finditer("\n", texto)]
    grupos: list[list[_Pedaco]] = []
    atual: list[_Pedaco] = []
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        if tok.type == tokenize.STRING and tok.string.lstrip("rR")[:1] in ("'", '"'):
            (la, ca), (lb, cb) = tok.start, tok.end
            ini, fim = inicios[la - 1] + ca, inicios[lb - 1] + cb
            cru = tok.string[0] in "rR"
            aspas = 3 if tok.string[cru:cru + 3] in ('"""', "'''") else 1
            atual.append(_Pedaco(ini, fim, ini + cru + aspas, fim - aspas, cru))
            continue
        if tok.type in (tokenize.NL, tokenize.COMMENT) and atual:
            continue
        if len(atual) >= 2:
            grupos.append(atual)
        atual = []
    return grupos


def _unidades(cru: str, sem_escape: bool = False) -> list[tuple[str, str]]:
    """O miolo cru de uma string comum em ``(cru, valor)``: um caractere ou uma sequência de escape."""
    if sem_escape:
        return [(c, c) for c in cru]
    saida, i = [], 0
    while i < len(cru):
        m = _ESCAPE_DE_STRING.match(cru, i) if cru[i] == "\\" else None
        pedaco = m.group(0) if m else (cru[i:i + 2] if cru[i] == "\\" else cru[i])
        saida.append((pedaco, ast.literal_eval(f'"""{pedaco} """')[:-1]))
        i += len(pedaco)
    return saida


_FUNCOES_DE_REGEX = {"compile", "sub", "subn", "search", "match", "fullmatch", "findall", "finditer", "split"}


def _padroes_de_regex(texto: str) -> set[int]:
    """O início de cada string que é o padrão de uma chamada do ``re``: ela é regex, nunca página."""
    inicios = [0] + [m.end() for m in re.finditer("\n", texto)]
    linhas = texto.split("\n")
    saida = set()
    for no in ast.walk(ast.parse(texto)):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.args \
                and isinstance(no.func.value, ast.Name) and no.func.value.id == "re" \
                and no.func.attr in _FUNCOES_DE_REGEX:
            alvo = no.args[0]
            coluna = len(linhas[alvo.lineno - 1].encode()[:alvo.col_offset].decode())
            saida.add(inicios[alvo.lineno - 1] + coluna)
    return saida


def _limpar_grupos(texto: str) -> tuple[str, int]:
    """O texto com cada concatenação implícita limpa como UMA string: o comentário que atravessa os pedaços sai.

    A limpeza só apaga, e a apagada volta a cada pedaço pelo alinhamento das duas sequências; o pedaço que
    esvazia sai com a linha dele. A prova é o valor: a concatenação nova é igual à limpeza da velha.
    """
    trocas = 0
    padroes = _padroes_de_regex(texto)
    for grupo in reversed(_grupos_de_strings(texto)):
        if grupo[0].ini in padroes:
            continue
        unidades = [_unidades(texto[p.miolo_ini:p.miolo_fim], p.cru) for p in grupo]
        dono = [(k, u) for k, us in enumerate(unidades) for u, (_, v) in enumerate(us) for _ in v]
        junto = "".join(v for us in unidades for _, v in us)
        if junto != "".join(ast.literal_eval(texto[p.ini:p.fim]) for p in grupo):
            raise ValueError(f"o escape de uma string não se leu na linha {texto.count(chr(10), 0, grupo[0].ini) + 1}")
        if _COMENTARIO_INTEIRO.fullmatch(junto):
            continue
        limpo = limpar_string_de_pagina(junto)
        if limpo == junto:
            continue
        apagado = [False] * len(junto)
        for op, a1, a2, _, _ in difflib.SequenceMatcher(None, junto, limpo, autojunk=False).get_opcodes():
            if op not in ("equal", "delete"):
                raise ValueError("a limpeza de uma concatenação fez mais que apagar")
            if op == "delete":
                apagado[a1:a2] = [True] * (a2 - a1)
        sai: set[tuple[int, int]] = set()
        fica: set[tuple[int, int]] = set()
        for pos, chave in enumerate(dono):
            (sai if apagado[pos] else fica).add(chave)
        if sai & fica:
            raise ValueError("a limpeza cortou uma sequência de escape ao meio")
        novos = ["".join(c for u, (c, v) in enumerate(us) if not v or (k, u) not in sai)
                 for k, us in enumerate(unidades)]
        if "".join(v for k, us in enumerate(unidades) for u, (_, v) in enumerate(us) if (k, u) not in sai) != limpo:
            raise ValueError("a concatenação limpa não vale o que a limpeza pediu")
        vazios = [k for k, n in enumerate(novos) if not n]
        if len(vazios) == len(grupo):
            vazios = vazios[1:]
        for k in reversed(range(len(grupo))):
            p = grupo[k]
            if k in vazios:
                texto = _sem_o_pedaco(texto, p)
            else:
                texto = texto[:p.miolo_ini] + novos[k] + texto[p.miolo_fim:]
        trocas += 1
    return texto, trocas


def _sem_o_pedaco(texto: str, p: _Pedaco) -> str:
    """O texto sem um pedaço de concatenação: a linha inteira, se ele a ocupa sozinho; senão, ele e o espaço."""
    linha_ini = texto.rfind("\n", 0, p.ini) + 1
    linha_fim = texto.find("\n", p.fim)
    linha_fim = len(texto) if linha_fim == -1 else linha_fim
    if not texto[linha_ini:p.ini].strip() and not texto[p.fim:linha_fim].strip():
        return texto[:linha_ini] + texto[linha_fim + 1:]
    fim = p.fim
    while fim < len(texto) and texto[fim] in " \t":
        fim += 1
    return texto[:p.ini] + texto[fim:]


_COMENTARIO_INTEIRO = re.compile(r"<!--(?:(?!-->).)*-->", re.S)


def aplicar_strings(arquivos: list[str], raiz: Path, gravar: bool) -> int:
    """Tira o comentário de página das strings dos geradores; a prova é a página regerada (fora daqui).

    A string que é um comentário HTML inteiro e nada mais é um valor, não um comentário de página: o
    produto a escreve num campo vivo como o vazio que não desenha nada (o ``:empty`` o ignora e o
    ``escrever()`` não o troca por travessão), ou a compara como âncora. Ela fica.
    """
    for rel in arquivos:
        caminho = raiz / rel
        original = caminho.read_text(encoding="utf-8")
        texto, trocas = _limpar_grupos(original)
        novo = texto
        padroes = _padroes_de_regex(texto)
        juntas = {t.ini for g in _grupos_de_strings(texto) for t in g}
        for ini, fim, tipo, tok_ini, tok_fim, campos in sorted(_strings_do_gerador(texto), reverse=True):
            if tok_ini in juntas or tok_ini in padroes:
                continue
            miolo = texto[ini:fim]
            if tipo == "s" and _COMENTARIO_INTEIRO.fullmatch(miolo):
                continue
            limpo = limpar_fstring(texto, ini, fim, campos) if tipo == "f" else limpar_string_de_pagina(miolo)
            if limpo == miolo:
                continue
            trocas += 1
            if limpo == "":
                novo = _sem_a_string_vazia(novo, tok_ini, tok_fim, ini, fim)
            else:
                novo = novo[:ini] + limpo + novo[fim:]
        if novo != original:
            ast.parse(novo)
            if gravar:
                caminho.write_text(novo, encoding="utf-8")
        print(f"{rel}: {trocas} string(s) limpa(s)")
    return 0


def _sem_a_string_vazia(texto: str, ini: int, fim: int, miolo_ini: int, miolo_fim: int) -> str:
    """O texto sem a string que ficou vazia: a linha dela, ou ela e o ``+`` vizinho; senão, só o miolo."""
    linha_ini = texto.rfind("\n", 0, ini) + 1
    linha_fim = texto.find("\n", fim)
    linha_fim = len(texto) if linha_fim == -1 else linha_fim
    antes, depois = texto[linha_ini:ini], texto[fim:linha_fim]
    if not antes.strip() and re.fullmatch(r"\s*(?:\+\s*)?", depois):
        resto = texto[linha_fim + 1:]
        if "+" not in depois:
            mais = re.match(r"([ \t]*)\+[ \t]*", resto)
            if mais:
                return texto[:linha_ini] + mais.group(1) + resto[mais.end():]
            fim_anterior = re.search(r"[ \t]*\+[ \t]*\n$", texto[:linha_ini])
            if fim_anterior and not re.match(r"\s*[\"'(\w]", resto):
                return texto[:fim_anterior.start()] + "\n" + resto
        return texto[:linha_ini] + resto
    mais = re.match(r"[ \t]*\+[ \t]*", depois)
    if mais:
        return texto[:ini] + texto[fim + mais.end():]
    mais = re.search(r"[ \t]*\+[ \t]*$", antes)
    if mais:
        return texto[:linha_ini + mais.start()] + texto[fim:]
    return texto[:miolo_ini] + texto[miolo_fim:]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument("arquivos", nargs="*")
    p.add_argument("--aplicar", action="store_true", help="grava o que provou")
    p.add_argument("--provar", action="store_true", help="prova sem gravar")
    p.add_argument("--strings", action="store_true", help="as strings de página dos geradores dados")
    p.add_argument("--raiz", default=None)
    a = p.parse_args(argv)
    raiz = Path(a.raiz).resolve() if a.raiz else RAIZ
    pedidos = None
    if a.arquivos:
        pedidos = []
        for bruto in a.arquivos:
            caminho = Path(bruto)
            caminho = (caminho if caminho.is_absolute() else Path.cwd() / caminho).resolve()
            pedidos.append(caminho.relative_to(raiz).as_posix())
    if a.strings:
        return aplicar_strings(pedidos or [], raiz, a.aplicar)
    arquivos = G.alvos(raiz, pedidos)
    if a.aplicar or a.provar:
        return aplicar(arquivos, raiz, a.aplicar)
    for tipo, conta in sorted(contar(arquivos, raiz).items()):
        print(f"{tipo}: {conta['arquivos']} arquivo(s), {conta['sai']} comentário(s) que saem, "
              f"{conta['fica']} diretiva(s) que ficam")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
