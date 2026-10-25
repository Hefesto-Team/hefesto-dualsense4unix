#!/usr/bin/env python3
"""USAR um símbolo é uma coisa; CITÁ-LO na prosa é outra. Aqui mora a diferença.

POR QUE ISTO EXISTE, E POR QUE É UM MÓDULO E NÃO UMA FUNÇÃO SOLTA
------------------------------------------------------------------
Em 06/09/2026 dois portões diferentes anunciaram, no mesmo dia, que uma dívida
tinha fechado — porque o nome de uma função da janela antiga *apareceu* na tela
nova. O que apareceu era **prosa**: uma docstring que EXPLICAVA o que a janela
antiga fazia::

    A LINHA **L315** DO CSV (…) A janela antiga tinha
    (`daemon_actions.on_daemon_migrate_to_systemd`).

Os dois portões:

* ``scripts/check_paridade_gtk_html.py`` — a regra ``divida-fechada``, com
  ``alvo in self.texto(p)``;
* ``scripts/check_donos_de_comportamento.py`` — a regra ``SO-GTK`` que já
  migrou, com ``simbolo in caminho.read_text()``.

E não era a primeira vez: em **03/09/2026** o mesmo símbolo, pelo mesmo caminho,
promoveu as linhas 315 e 343 do CSV da paridade a ``DIFERENTE``, e as duas
tiveram de ser devolvidas no mesmo dia. O ``porque`` de cada uma registra o
tombo.

**A regra desta casa é que a cura cobre TODOS os chamadores** — cobrir um deixa
a próxima pessoa remedindo o mesmo defeito, e foi o que aconteceu duas vezes
num dia em 05/09. Por isso a separação virou dono único, e os dois portões
perguntam a ele.

O QUE É PROSA, E O QUE NÃO É
-----------------------------
Prosa é **a docstring e o comentário**, e mais nada. Três tentativas erradas,
com o custo medido, para ninguém as repetir:

1. **apagar toda ``ast.Constant`` de texto** → 165 falsos. Cadeia usada como
   VALOR é código: ``"restaurar-de-fabrica"`` é o nome de um gesto e
   ``data-campo="fragil"`` é um endereço de tela;
2. **tirar comentário com ``(?m)#[^\\n]*``** → 93 falsos, porque o regex come o
   ``#`` de ``cor = "#A51C48"`` e o resto da linha junto;
3. **borda de palavra com ``(?<![\\w.])``** → 17 falsos: excluir o ponto faz
   ``mesa_viva.VIA_DO_TRANSPORTE`` deixar de casar, e acesso por atributo é uso.

Quem sabe separar isso é a gramática da linguagem, não um regex: o ``ast`` diz
qual cadeia é docstring, o ``tokenize`` diz qual ``#`` abre comentário.

FALHA PARA O LADO SEGURO
-------------------------
Arquivo que não parseia devolve o texto CRU. Uma régua que emudece por causa de
um ``.py`` a meio caminho de uma edição é pior que uma que exagera: ela dá verde
sobre o que não leu.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.S)

_CACHE: dict[Path, str] = {}


def _linhas(fonte: str) -> list[str]:
    """As linhas com a quebra, cortadas só no ``\n``, como o ``tokenize`` e o ``ast`` as contam.

    O ``splitlines`` corta também no ``\x0c`` e no ``\u2028``, e a linha N dele deixa de ser a do
    ``ast``.
    """
    return re.findall(r"[^\n]*\n|[^\n]+\Z", fonte)


def _inicio_das_linhas(fonte: str) -> list[int]:
    """O deslocamento em que cada linha começa."""
    inicio = [0]
    for linha in _linhas(fonte):
        inicio.append(inicio[-1] + len(linha))
    return inicio


def _docstrings(arvore: ast.AST) -> list[ast.Constant]:
    """As docstrings — e só elas, nunca toda cadeia de texto."""
    fora: list[ast.Constant] = []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.Module, ast.ClassDef,
                               ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = getattr(no, "body", None)
        if not corpo:
            continue
        primeira = corpo[0]
        if (isinstance(primeira, ast.Expr)
                and isinstance(primeira.value, ast.Constant)
                and isinstance(primeira.value.value, str)):
            fora.append(primeira.value)
    return fora


def _coluna(linhas: list[str], numero: int, deslocamento: int) -> int:
    """A coluna em LETRAS do ``col_offset`` do ``ast``, que conta BYTES do UTF-8.

    Sem a conversão, a docstring com acento ou travessão na última linha apagava o começo da linha de
    baixo, o ``tokenize`` caía na indentação torta e o comentário do arquivo inteiro voltava a contar
    como uso (60 dos 405 ``.py`` do ``src/``, 2.493 comentários, medido em 25/10/2026).
    """
    return len(linhas[numero - 1].encode("utf-8")[:deslocamento].decode("utf-8", errors="replace"))


def _apagar(letras: list[str], a: int, b: int) -> None:
    """Espaço no lugar do trecho, preservando as quebras de linha."""
    for i in range(a, min(b, len(letras))):
        if letras[i] != "\n":
            letras[i] = " "


def sem_prosa(fonte: str, sufixo: str = ".py") -> str:
    """O texto sem docstring e sem comentário. O resto fica intacto.

    Fora do ``.py`` a prosa é só o comentário, e quem o conhece é o :func:`sem_comentario`; o sufixo que
    ele não conhece (o ``.md``, o ``.glade``) perde só o ``<!-- -->``.
    """
    if sufixo in SUFIXOS_COM_COMENTARIO - {".py"}:
        return sem_comentario(fonte, sufixo)
    if sufixo != ".py":
        return _COMENTARIO_HTML.sub(lambda m: " " * len(m.group(0)), fonte)

    letras = list(fonte)
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return fonte
    inicio = _inicio_das_linhas(fonte)
    linhas = _linhas(fonte)
    for no in _docstrings(arvore):
        if no.end_lineno is None or no.end_col_offset is None:
            continue
        _apagar(letras,
                inicio[no.lineno - 1] + _coluna(linhas, no.lineno, no.col_offset),
                inicio[no.end_lineno - 1] + _coluna(linhas, no.end_lineno, no.end_col_offset))

    parcial = "".join(letras)
    limpo = _sem_comentario_py(parcial)
    return parcial if limpo is None else limpo


def _sem_comentario_py(fonte: str) -> str | None:
    """O ``.py`` com cada comentário (o ``#`` que o ``tokenize`` diz) em branco; ``None`` se não tokeniza."""
    inicio = _inicio_das_linhas(fonte)
    letras = list(fonte)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(fonte).readline):
            if tok.type != tokenize.COMMENT:
                continue
            _apagar(letras,
                    inicio[tok.start[0] - 1] + tok.start[1],
                    inicio[tok.end[0] - 1] + tok.end[1])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    return "".join(letras)


_BLOCO_DE_SCRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.S | re.I)
_BLOCO_DE_ESTILO = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.S | re.I)


def _sem_comentario_de_chaves(fonte: str, aspas: str, de_linha: bool) -> str:
    """O ``/* */`` (e o ``//``, se ``de_linha``) em branco; o que está entre as ``aspas`` fica.

    É a gramática comum do JS, do CSS e do C: o CSS não tem ``//`` (ele mora dentro de ``url(http://…)``),
    e a crase só abre cadeia no JS.
    """
    letras = list(fonte)
    i, n = 0, len(fonte)
    while i < n:
        c = fonte[i]
        if c in aspas:
            i += 1
            while i < n and fonte[i] != c and (c == "`" or fonte[i] != "\n"):
                i += 2 if fonte[i] == "\\" else 1
            i += 1
        elif de_linha and fonte.startswith("//", i):
            fim = fonte.find("\n", i)
            fim = n if fim < 0 else fim
            _apagar(letras, i, fim)
            i = fim
        elif fonte.startswith("/*", i):
            fim = fonte.find("*/", i + 2)
            fim = n if fim < 0 else fim + 2
            _apagar(letras, i, fim)
            i = fim
        else:
            i += 1
    return "".join(letras)


def _sem_comentario_js(fonte: str) -> str:
    """O JS com ``//`` e ``/* */`` em branco; o que está entre aspas ou crases fica."""
    return _sem_comentario_de_chaves(fonte, "'\"`", de_linha=True)


_ABRE_HEREDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_ANTES_DO_CERQUILHA = frozenset(" \t\n;&|()<>")


def _sem_comentario_sh(fonte: str) -> str:
    """O ``.sh`` com o ``#`` que abre comentário em branco, e o resto como veio.

    O ``#`` só abre comentário no começo de palavra: ``$#``, ``${#lista[@]}`` e ``a#b`` são código. A
    cadeia (``'…'``, ``"…"``) e o corpo do heredoc são dado, e o ``#!`` da primeira linha fica.
    """
    letras = list(fonte)
    i, n = 0, len(fonte)
    heredocs: list[tuple[bool, str]] = []
    if fonte.startswith("#!"):
        i = fonte.find("\n")
        i = n if i < 0 else i
    while i < n:
        c = fonte[i]
        if c == "\\":
            i += 2
        elif c == "'":
            fim = fonte.find("'", i + 1)
            i = n if fim < 0 else fim + 1
        elif c == '"':
            i += 1
            while i < n and fonte[i] != '"':
                i += 2 if fonte[i] == "\\" else 1
            i += 1
        elif c == "#" and (i == 0 or fonte[i - 1] in _ANTES_DO_CERQUILHA):
            fim = fonte.find("\n", i)
            fim = n if fim < 0 else fim
            _apagar(letras, i, fim)
            i = fim
        elif c == "<" and fonte.startswith("<<", i) and not fonte.startswith("<<<", i):
            achado = _ABRE_HEREDOC.match(fonte, i)
            if achado is None:
                i += 2
            else:
                heredocs.append((achado.group(1) == "-", achado.group(3)))
                i = achado.end()
        elif c == "\n" and heredocs:
            i += 1
            for tira_tab, palavra in heredocs:
                while i < n:
                    fim = fonte.find("\n", i)
                    fim = n if fim < 0 else fim
                    linha = fonte[i:fim]
                    i = fim + 1
                    if (linha.lstrip("\t") if tira_tab else linha) == palavra:
                        break
            heredocs.clear()
        else:
            i += 1
    return "".join(letras)


def sem_comentario(fonte: str, sufixo: str) -> str:
    """O texto sem comentário, com a docstring e a cadeia intactas, e as quebras de linha no lugar.

    Comentário é o ``#`` do ``.py`` (pelo ``tokenize``) e o do ``.sh`` (no começo de palavra, fora de
    cadeia e de heredoc, o ``#!`` preservado), o ``<!-- -->`` do HTML, o ``//`` e o ``/* */`` do JS e do
    C (``.c``, ``.h``), e o ``/* */`` do CSS, inclusive o do ``<script>`` e o do ``<style>`` dentro do
    HTML. Outro sufixo volta como veio, e o ``.py`` que não tokeniza também (o lado seguro de cima).
    """
    if sufixo == ".py":
        limpo = _sem_comentario_py(fonte)
        return fonte if limpo is None else limpo
    if sufixo in (".js", ".mjs"):
        return _sem_comentario_js(fonte)
    if sufixo == ".css":
        return _sem_comentario_de_chaves(fonte, "'\"", de_linha=False)
    if sufixo in (".c", ".h"):
        return _sem_comentario_de_chaves(fonte, "'\"", de_linha=True)
    if sufixo == ".sh":
        return _sem_comentario_sh(fonte)
    if sufixo in (".html", ".htm"):
        sem_html = _COMENTARIO_HTML.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), fonte)
        sem_js = _BLOCO_DE_SCRIPT.sub(
            lambda m: m.group(1) + _sem_comentario_js(m.group(2)) + m.group(3), sem_html)
        return _BLOCO_DE_ESTILO.sub(
            lambda m: m.group(1) + _sem_comentario_de_chaves(m.group(2), "'\"", de_linha=False)
            + m.group(3), sem_js)
    return fonte


SUFIXOS_COM_COMENTARIO = frozenset({".py", ".js", ".mjs", ".css", ".c", ".h", ".sh", ".html", ".htm"})
"""Os sufixos cuja gramática de comentário o :func:`sem_comentario` conhece."""


def codigo_de(caminho: Path) -> str:
    """O arquivo sem a prosa, lido uma vez por processo."""
    if caminho in _CACHE:
        return _CACHE[caminho]
    try:
        cru = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        cru = ""
    _CACHE[caminho] = sem_prosa(cru, caminho.suffix)
    return _CACHE[caminho]


def agulha(simbolo: str) -> re.Pattern[str]:
    """O símbolo com borda de palavra dos DOIS lados, e o ponto de fora.

    Sem a borda, ``player_slot`` casa dentro de ``player_slot_color`` — foi
    assim que uma linha do CSV da paridade passou a vida inteira sem morder. E
    o ponto NÃO entra na borda da esquerda: excluí-lo faria
    ``mesa_viva.VIA_DO_TRANSPORTE`` deixar de casar, e acesso por atributo é
    uso do símbolo.
    """
    return re.compile(rf"(?<!\w){re.escape(simbolo)}(?![\w])")


def ocorre_no_texto(texto: str, simbolo: str) -> bool:
    """O símbolo aparece no texto com borda de palavra.

    O literal ausente responde «não» sem regex: a agulha com olhar-para-trás varre o texto inteiro, e a
    paridade a chamava 3.605 vezes, quase sempre por um símbolo que nem estava no arquivo (12,8 de 15,3 s
    da corrida, medido em 09/10/2026). Presente, a borda decide como sempre decidiu.
    """
    return simbolo in texto and agulha(simbolo).search(texto) is not None


def usa(caminho: Path, simbolo: str) -> bool:
    """O arquivo USA o símbolo — citá-lo num comentário não conta."""
    return ocorre_no_texto(codigo_de(caminho), simbolo)


def cita(caminho: Path, simbolo: str) -> bool:
    """O símbolo APARECE no arquivo, prosa incluída."""
    try:
        return ocorre_no_texto(caminho.read_text(encoding="utf-8", errors="replace"), simbolo)
    except OSError:
        return False


_CITACAO_POR_DESENHO = re.compile(
    r"(?:[\w.-]+/)+[\w.-]+(?::\d+)?"
    r"|[\w-]+\.(?:py|html?|js|mjs|css|c|h|sh|md|txt|csv|json|toml|ya?ml|service|rules|conf|desktop)"
    r"(?::\d+)?"
    r"|D(?:-[A-Z0-9]+)+")
"""As três formas de sinal que só vivem na prosa: o caminho (``core/ds_output_report.py:106``,
``app/actions/mode_transition.plan_mode_transition``), o nome de arquivo (``test_os_donos_de_fato.py``)
e o ID de decisão (``D-A-CONTAGEM-DO-EXAME-SAIU``)."""


def e_citacao(sinal: str) -> bool:
    """O sinal é citação por desenho (caminho, nome de arquivo, ID de decisão), e não símbolo de código.

    A FORMA DO SINAL DECIDE A PERGUNTA (O-SINAL-PRESENTE-DA-PARIDADE-E-CODIGO-E-NAO-COMENTARIO-01,
    25/10/2026). A citação só pode viver num comentário, e se confere por :func:`cita`; o símbolo
    (identificador, classe CSS, ``data-campo``, chave, frase da tela) se confere por :func:`usa`. Até
    ali a paridade conferia os dois por presença, e a linha que vigiava ``.selo.grave`` passou verde
    com a classe sobrando só em dois comentários.
    """
    return _CITACAO_POR_DESENHO.fullmatch(sinal) is not None


def presente(caminho: Path, sinal: str) -> bool:
    """O arquivo tem o sinal do jeito que a forma dele pede: citado, se é citação; usado, se é símbolo."""
    return cita(caminho, sinal) if e_citacao(sinal) else usa(caminho, sinal)
