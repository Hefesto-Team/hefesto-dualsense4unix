#!/usr/bin/env python3
"""neutralizar-o-texto.py — o «dela» que aponta para a pessoa sai de comentário e docstring.

O produto é para qualquer usuário, e um texto versionado não fala de quem o mantém
na terceira pessoa. A troca é por padrão, e só no que é PROSA:

- Python: comentário, docstring, e os comentários de marcação (``<!-- -->``,
  ``/* */`` e ``//``) que os geradores de tela guardam dentro de strings;
- HTML, shell, CSS e JS: os comentários; Markdown e CSV de documento: o texto todo.

Nenhuma string de código (mensagem de teste, texto de tela, valor de dado) é tocada:
a tela fica byte a byte igual. O que o padrão não reconhece fica como está e aparece
em ``--sobra`` para revisão à mão. A fala literal entre aspas também não é tocada: tirá-la
pede reescrever a oração em volta, e a troca por padrão deixava a frase pela metade
(«disse .», «palavra de produto: **.»).

    python3 scripts/neutralizar-o-texto.py --conferir   # rc=1 se mudaria algo
    python3 scripts/neutralizar-o-texto.py --aplicar    # idempotente
    python3 scripts/neutralizar-o-texto.py --sobra      # lista o «dela» que sobrou

Resumo numa linha; ``--detalhe ARQUIVO`` grava a lista de arquivos.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: A posse do texto: o que esta passada reescreve.
PREFIXOS = (
    "src/", "tests/unit/", "tests/fixtures/", "scripts/",
    "docs/protocol/", "docs/method/", "docs/adr/",
)
#: Dentro dela, o que é da costura (publicado, gerado ou dado).
FORA = (
    "src/hefesto_dualsense4unix/interface/paginas/",
    "tests/fixtures/",
    "scripts/neutralizar-o-texto.py",
    "scripts/neutralizar-os-nomes.py",
)
EXT_CODIGO = {".py": "py", ".sh": "sh", ".html": "html", ".css": "css", ".js": "js"}
EXT_PROSA = {".md", ".txt"}

# --------------------------------------------------------------------------
# As regras. O padrão é minúsculo e sem acento de caixa; a troca herda a caixa.
# --------------------------------------------------------------------------
_E = r"(?<![\w-])"          # borda esquerda de palavra (hífen e sublinhado são palavra)
_D = r"(?![\w-])"           # borda direita

_DATA = r"(?=,? (?:de |em |do dia )?\(?\d{1,2}/\d{1,2})"
_NOMES_DE_DECISAO = (
    "decisão|decisões|ordem|ordens|pedido|pedidos|palavra|palavras|regra|regras|queixa|queixas|"
    "resposta|respostas|escolha|escolhas|aceite|ressalva|ressalvas|delegação|frase|frases|pergunta|perguntas"
)
_DO_USUARIO = (
    "máquina|tela|tv|mão|mãos|biblioteca|voz|vista|orelha|steam|disco|daemon|journal|aparelho|aparelhos|"
    "microfone|dedo|dedos|clique|cliques|gesto|gestos|rato|perfil|perfis|controle|controles|jogo|jogos|"
    "home|casa|sessão|conta|pasta|teclado|mouse|rádio|bluetooth|adaptador|adaptadores|som|fone|headset|"
    "lançador|lançadores|instalação|jogador|dualsense|dualsenses|configuração|ambiente|sistema|"
    "monitor|monitores|desktop|área de trabalho|lista de jogos|escolha|escolhas|fala|falas|voz|palavra de ordem"
)

#: O espaço entre duas palavras pode ser uma quebra de linha de comentário (``# `` ou ``#: ``).
_SEP = r"(?:[ \t]+|[ \t]*\n[ \t]*(?:#:?[ \t]*|\*[ \t]*)?)"
_QUEBRA = re.compile(r"[ \t]*\n[ \t]*(?:#:?[ \t]*|\*[ \t]*)?")


def _c(padrao: str, flags: int = 0) -> re.Pattern[str]:
    """Compila trocando cada espaço literal do padrão por «espaço ou quebra de comentário»."""
    return re.compile(padrao.replace(" ", _SEP), flags)


REGRAS: list[tuple[re.Pattern[str], str]] = [
    # a data já diz de quando: «ordem dela de 19/09» -> «ordem de 19/09»
    (_c(_E + r"(" + _NOMES_DE_DECISAO + r") dela" + _DATA, re.I), r"\1"),
    # a bancada é a bancada
    (_c(_E + r"(?:mesa|bancada) dela" + _D, re.I), "bancada"),
    # a medição foi na bancada: a máquina, a TV e o diário em que se mediu são da bancada
    (_c(_E + r"(medid[oa]s?|conferid[oa]s?|rodad[oa]s?|testad[oa]s?|observad[oa]s?|vist[oa]s?) na máquina dela" + _D, re.I), r"\1 na bancada"),
    (_c(_E + r"na máquina dela(?=,? (?:em|às|de|no dia) \d)", re.I), "na bancada"),
    (_c(_E + r"máquina dela(?=,? (?:em|às) \d)", re.I), "máquina da bancada"),
    (_c(_E + r"(tv|journal) dela" + _D, re.I), r"\1 da bancada"),
    # quem recebe a pergunta é o usuário
    (_c(_E + r"(levad[oa]s?|mostrad[oa]s?|perguntad[oa]s?|explicad[oa]s?|apresentad[oa]s?|entregues?) a ela" + _D, re.I), r"\1 ao usuário"),
    (_c(_E + r"(nas|com as|pelas) palavras dela" + _D, re.I), r"\1 palavras do usuário"),
    # o olho de quem confere
    (_c(_E + r"olho dela" + _D, re.I), "olho de quem confere"),
    # citação e literal: o «dela» some e a palavra fica
    (_c(_E + r"(cita[çc][ãa]o|literal|literais) dela" + _D, re.I), r"\1"),
    (_c(_E + r"(cita[çc][õo]es) delas" + _D, re.I), r"\1"),
    # o que é decisão vira decisão de produto
    (_c(_E + r"(decis[ãa]o|ordem|palavra|regra|aceite|delega[çc][ãa]o|resposta|ressalva|frase|pergunta|padr[ãa]o|lei) dela" + _D, re.I), r"\1 de produto"),
    (_c(_E + r"(decis[õo]es|ordens|palavras|regras|respostas|ressalvas|frases|perguntas) delas?" + _D, re.I), r"\1 de produto"),
    (_c(_E + r"(escolha) dela" + _D, re.I), r"\1 do usuário"),
    (_c(_E + r"(pedido|pedidos) dela" + _D, re.I), r"\1"),
    (_c(_E + r"(queixa|queixas) dela" + _D, re.I), r"\1 de uso"),
    # «a decisão é dela» / «a palavra é dela»
    (_c(_E + r"(decis[ãa]o|palavra|ordem|regra|escolha|pedido) é dela" + _D, re.I), r"\1 é de produto"),
    # o que é do usuário
    (_c(_E + r"(" + _DO_USUARIO + r") dela" + _D, re.I), r"\1 do usuário"),
    (_c(_E + r"(na frente) dela" + _D, re.I), r"\1 do usuário"),
    # quem diz e quem faz
    (_c(_E + r"(a validar|validad[oa]s?|aprovad[oa]s?|decidid[oa]s?|escolhid[oa]s?|pedid[oa]s?|confirmad[oa]s?|ditad[oa]s?|corrigid[oa]s?|delegad[oa]s?) por ela" + _D, re.I), r"\1 pelo usuário"),
    # só os verbos que uma função, uma tela ou um arquivo não têm como fazer
    (_c(_E + r"ela (pediu|mandou|aprovou|decidiu|ordenou|definiu|determinou|autorizou|liberou|aceitou|validou|confirmou|corrigiu|escreveu|disse|nomeou|perguntou|queixou-se|reclamou|falou|contou|apertou|apontou|digitou|clicou|olhou|viu|mexeu|escolheu|colou)" + _D, re.I), r"o usuário \1"),
    # ênfase em maiúsculas: no corpus, «DELA» sozinho é sempre a pessoa
    (_c(r"(?<![\w-])ELA É DELA(?![\w-])"), "É DO USUÁRIO"),
    (_c(r"(?<![\w-])DELA(?![\w-])"), "DO USUÁRIO"),
    (_c(_E + r"ela é dela" + _D, re.I), "é do usuário"),
    # «é dela» no fim da oração, quando o sujeito não é um nome técnico feminino
    (_c(
        r"(?<![\w-])(?P<cab>(?:(?!\b(?:régua|função|classe|tabela|lista|chave|fila|linha|camada|rota|porta|variável|"
        r"constante|ponte|aba|pasta|biblioteca|thread|string|lápide|ferramenta|sprint|página|imagem|foto|marca|cor|"
        r"fonte|saída|entrada|janela|árvore|mesa|conta|unidade|medição|nota|doc|docstring|seção|fase|etapa|ordem de execução)\b)[^\n.;:]){0,60}?)"
        r"\b(é|era|foi|são|seja|fica|ficou) dela(?=\s*(?:[:.;,—)\]*»\"]|$|decidir|escolher|conferir|validar|dizer|medir|olhar|abrir|aprovar|fechar))",
        re.I), r"\g<cab>\2 do usuário"),
]

def _adaptar(achado: str, troca: str) -> str:
    letras = [c for c in achado if c.isalpha()]
    if len(letras) > 1 and all(c.isupper() for c in letras):
        return troca.upper()
    if achado[:1].isupper():
        return troca[:1].upper() + troca[1:]
    return troca



def reescrever_prosa(texto: str) -> str:
    """Aplica as regras a um pedaço de prosa."""
    if "ela" not in texto.lower():
        return texto
    for padrao, troca in REGRAS:
        def _sub(m: re.Match[str], troca: str = troca) -> str:
            novo = _adaptar(m.group(0), m.expand(troca))
            q = _QUEBRA.search(m.group(0))
            if q and "\n" in q.group(0):
                i = novo.rfind(" ") if troca.startswith("o usuário ") else novo.find(" ")
                if i > 0:
                    novo = novo[:i] + q.group(0) + novo[i + 1:]
            return novo
        texto = padrao.sub(_sub, texto)
    return texto


# --------------------------------------------------------------------------
# Onde está a prosa em cada tipo de arquivo.
# --------------------------------------------------------------------------
_MARCACAO = re.compile(r"<!--.*?-->|(?<![\w/*\"'])/\*(?!/).*?\*/", re.S)
_JS = re.compile(r"(?:(?<=\s)|^)//(?=\s)[^\n]*", re.M)
_SH = re.compile(r"(?:(?<=\s)|^)#(?!!)[^\n]*", re.M)


def _linhas_para_deslocamentos(texto: str) -> list[int]:
    ini = [0]
    for i, c in enumerate(texto):
        if c == "\n":
            ini.append(i + 1)
    return ini


def _spans_py(texto: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    linhas = _linhas_para_deslocamentos(texto)
    try:
        for t in tokenize.generate_tokens(io.StringIO(texto).readline):
            if t.type == tokenize.COMMENT:
                spans.append((linhas[t.start[0] - 1] + t.start[1], linhas[t.end[0] - 1] + t.end[1]))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        arvore = None
    if arvore is not None:
        for no in ast.walk(arvore):
            documentavel = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            if isinstance(no, documentavel) and no.body and isinstance(no.body[0], ast.Expr):
                v = no.body[0].value
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.end_lineno:
                    spans.append((linhas[v.lineno - 1] + v.col_offset, linhas[v.end_lineno - 1] + v.end_col_offset))
    # comentário de HTML, CSS e JS só conta quando mora DENTRO de uma string do gerador
    strings: list[tuple[int, int]] = []
    if arvore is not None:
        for no in ast.walk(arvore):
            # a f-string conta inteira: do 3.12 em diante cada pedaço tem a posição exata, e um comentário
            # com `{CAMPO}` no meio cruzava dois pedaços e escapava (no 3.10 e no 3.11, não)
            string = isinstance(no, ast.JoinedStr) or (isinstance(no, ast.Constant) and isinstance(no.value, str))
            if string and no.end_lineno:
                strings.append((linhas[no.lineno - 1] + no.col_offset, linhas[no.end_lineno - 1] + no.end_col_offset))
    strings.sort()
    for rx in (_MARCACAO, _JS):
        for m in rx.finditer(texto):
            if any(a <= m.start() and m.end() <= b for a, b in strings if a <= m.start() < b):
                spans.append((m.start(), m.end()))
    return spans


def _spans_de(texto: str, tipo: str) -> list[tuple[int, int]]:
    if tipo == "py":
        return _spans_py(texto)
    if tipo == "sh":
        return [(m.start(), m.end()) for m in _SH.finditer(texto)]
    if tipo in ("html", "css", "js"):
        spans = [(m.start(), m.end()) for m in _MARCACAO.finditer(texto)]
        if tipo in ("html", "js"):
            spans += [(m.start(), m.end()) for m in _JS.finditer(texto)]
        return spans
    return [(0, len(texto))]


def _fundir(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    saida: list[tuple[int, int]] = []
    for ini, fim in sorted(spans):
        if saida and ini <= saida[-1][1]:
            saida[-1] = (saida[-1][0], max(saida[-1][1], fim))
        else:
            saida.append((ini, fim))
    return saida


def _aparar(linha: str) -> str:
    """Linha reescrita: sem espaço no fim, e sem o travessão ou a vírgula que sobrou da fala tirada."""
    limpa = linha.rstrip()
    if limpa != linha:
        limpa = re.sub(r"[ \t]*[—–,:-]$", "", limpa)
    return limpa


def reescrever_arquivo(texto: str, tipo: str) -> str:
    """Reescreve; em Python, o resultado tem de continuar compilando, senão o arquivo fica como está."""
    novo = _reescrever_arquivo(texto, tipo)
    if tipo != "py" or novo == texto:
        return novo
    try:
        ast.parse(novo)
    except SyntaxError:
        return texto
    return novo


def _reescrever_arquivo(texto: str, tipo: str) -> str:
    partes: list[str] = []
    cursor = 0
    for ini, fim in _fundir(_spans_de(texto, tipo)):
        partes.append(texto[cursor:ini])
        partes.append(reescrever_prosa(texto[ini:fim]))
        cursor = fim
    partes.append(texto[cursor:])
    novo = "".join(partes)
    if novo == texto:
        return texto
    antigas = texto.split("\n")
    saida = novo.split("\n")
    if len(antigas) == len(saida):
        saida = [n if n == o else _aparar(n) for o, n in zip(antigas, saida, strict=True)]
        return "\n".join(saida)
    velhas = set(antigas)
    final: list[str] = []
    for n in saida:
        if n in velhas:
            final.append(n)
            continue
        n = _aparar(n)
        if n.strip() in ("#", "#:", "*", "<!--"[:0]):
            continue  # a linha era só a fala tirada
        if not n.strip() and final and not final[-1].strip():
            continue
        final.append(n)
    return "\n".join(final)


def alvos() -> list[tuple[str, str]]:
    ls = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split("\n")
    saida: list[tuple[str, str]] = []
    for rel in ls:
        if not rel or not rel.startswith(PREFIXOS) or rel.startswith(FORA):
            continue
        ext = Path(rel).suffix
        if ext in EXT_CODIGO:
            saida.append((rel, EXT_CODIGO[ext]))
        elif ext in EXT_PROSA and rel.startswith(("docs/protocol/", "docs/method/", "docs/adr/", "scripts/")):
            saida.append((rel, "prosa"))
    return saida


_SOBRA = re.compile(_E + r"d?ela" + _D, re.I)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--conferir", action="store_true")
    modo.add_argument("--aplicar", action="store_true")
    modo.add_argument("--sobra", action="store_true")
    ap.add_argument("--detalhe")
    args = ap.parse_args(argv)

    mudados: list[str] = []
    sobra = 0
    linhas_da_sobra: list[str] = []
    for rel, tipo in alvos():
        caminho = RAIZ / rel
        try:
            antigo = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        novo = reescrever_arquivo(antigo, tipo)
        if novo != antigo:
            mudados.append(rel)
            if args.aplicar:
                caminho.write_text(novo, encoding="utf-8")
        if args.sobra:
            for ini, fim in _fundir(_spans_de(novo, tipo)):
                trecho = novo[ini:fim]
                for k, linha in enumerate(trecho.split("\n")):
                    if _SOBRA.search(linha):
                        sobra += 1
                        n = novo.count("\n", 0, ini) + k + 1
                        linhas_da_sobra.append(f"{rel}:{n}: {linha.strip()[:160]}")
    if args.detalhe:
        corpo = mudados if not args.sobra else linhas_da_sobra
        Path(args.detalhe).write_text("\n".join(corpo) + "\n", encoding="utf-8")
    if args.sobra:
        print(f"neutralizar-o-texto: sobram {sobra} linhas com «dela» em prosa")
        return 0
    verbo = "feito" if args.aplicar else "faria"
    print(f"neutralizar-o-texto: {verbo} em {len(mudados)} arquivos")
    return 1 if (mudados and args.conferir) else 0


if __name__ == "__main__":
    sys.exit(main())
