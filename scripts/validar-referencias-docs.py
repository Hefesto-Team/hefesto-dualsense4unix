#!/usr/bin/env python3
"""Reprova documento que cita arquivo, variável de ambiente ou método IPC que
não existe.

Motivação (sprint PORTÃO-VIVO-01, bloco F): a documentação deste projeto
descreve garantias que ninguém verifica. O caso canônico está em
`docs/adr/011-glyphs-vs-emojis.md`, que afirma duas vezes que o hook
"guardian.py" cobre os proibidos -- e esse arquivo não existe nesta árvore.
Uma decisão arquitetural inteira se apoia num arquivo imaginário.

Filosofia deste portão: FALSO POSITIVO EM MASSA TORNA O GATE INÚTIL. Por isso
ele é deliberadamente conservador em todas as três regras.

REGRA 1 -- ARQUIVO (nasceu na PORTÃO-VIVO-01, vale para `docs/` inteiro)

  - o texto precisa estar dentro de crase (`assim`) ou ser o alvo de um link
    markdown no formato [texto](alvo);
  - precisa terminar numa extensão da casa (.py, .sh, .md, .yml, .yaml, .toml,
    .glade, .rules);
  - nome solto, sem barra, só é cobrado para .py e .sh -- código executável que
    ou está no repositório ou não está. Nome solto de configuração
    (`daemon.toml`, `controllers.json`) é artefato de tempo de execução que
    vive em ~/.config, e por isso fica de fora;
  - caminho absoluto (/etc/...), caminho de HOME (~/...), variável de shell
    ($VAR), URL, glob, placeholder entre sinais de menor e maior, e `..` são
    ignorados;
  - bloco de código cercado por três crases é ignorado inteiro: ali mora
    comando de terminal, não referência a arquivo do repositório.

  A verificação aceita SUFIXO: `gui/main.glade` casa com o caminho real
  `src/hefesto_dualsense4unix/gui/main.glade`, porque a casa cita caminho
  encurtado o tempo todo e cobrar o caminho completo seria ruído puro.

REGRA 2 -- VARIÁVEL DE AMBIENTE (sprint DOC-VERDADE-02, entrega E10)

  Token entre crases no formato `HEFESTO_[A-Z0-9_]+` conferido contra os
  literais que existem no CÓDIGO (`src/`, `scripts/`, `assets/`, instaladores,
  empacotamento). Foi por este buraco que o ADR-017 passou anos ensinando
  `HEFESTO_PLUGINS_ENABLED` -- variável que nunca existiu, enquanto a real é
  `HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED`. Variável de ambiente não é arquivo,
  e por isso a regra 1 era cega a ela.

REGRA 3 -- MÉTODO DE IPC (sprint DOC-VERDADE-02, entrega E10)

  Token entre crases no formato `a.b` ou `a.b.c`, todo em minúsculas, cujo
  PRIMEIRO segmento seja um espaço de nomes que existe de fato no dicionário
  `_handlers` de `daemon/ipc_server.py` (lido por AST, sem importar o pacote) e
  cujo token completo NÃO esteja registrado ali. Assim `ctx.controller` nunca é
  cobrado -- `ctx` não é espaço de nomes de IPC -- e `daemon.toml`/`daemon.pid`
  saem pelo filtro de extensão de arquivo (`SUFIXOS_DE_ARQUIVO`).

ESCOPO DAS REGRAS 2 E 3: só os documentos que ENSINAM (`PREFIXOS_QUE_ENSINAM`:
`docs/usage/`, `docs/adr/`, `docs/protocol/` e o `README.md`). `docs/process/`
fica de fora POR ESCRITO: sprint é registro de proposta, e propor um método que
ainda não existe (`controller.player.set` na PLAYER-01, `identity.alias.set` na
IDENT-01) é o trabalho dela, não defeito. A própria DOC-VERDADE-02 cita 16
vezes as três variáveis mortas que mandou matar -- cobrar dela seria cobrar o
diagnóstico de conter o diagnosticado.

Escapes, para o portão não virar impossível de satisfazer:
  - `EXTERNOS`, abaixo: nomes de arquivo que pertencem a projetos de fora;
  - marcador de linha `<!-- ref-externa -->` (ou `<!-- ref-externa: motivo -->`)
    no próprio documento, para a linha que fala de um ausente DE PROPÓSITO --
    por exemplo `docs/usage/metrics.md`, que existe justamente para dizer que
    `HEFESTO_DUALSENSE4UNIX_METRICS` não existe. Vale para as três regras;
  - NOTA DE VERIFICAÇÃO DATADA (só regras 2 e 3): se o token aparece em algum
    ponto do documento a partir de um cabeçalho "Nota de verificação", o
    documento inteiro fica isento daquele token. É o padrão desta casa para ADR
    -- não se reescreve a decisão original, acrescenta-se a nota datada que diz
    o que mudou (ver `docs/adr/003-udp-port-6969-compat.md`). Sem esta isenção
    o portão reprovaria exatamente quem fez a correção certa, e um gate que
    castiga a honestidade é pior que gate nenhum.

Uso:
    python3 scripts/validar-referencias-docs.py --all
    python3 scripts/validar-referencias-docs.py docs/adr/011-glyphs-vs-emojis.md
    python3 scripts/validar-referencias-docs.py --root /outro/repo --all
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

#: Extensões que contam como "arquivo desta casa" quando o texto tem barra.
EXTENSOES = frozenset(
    {".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".glade", ".rules"}
)

#: Extensões cobradas também quando o nome vem solto, sem nenhuma barra.
#: Restrito a código executável de propósito: é o que gera afirmação falsa do
#: tipo "o hook guardian.py cobre isso".
EXTENSOES_NOME_SOLTO = frozenset({".py", ".sh"})

#: Diretórios que não entram no índice de arquivos existentes.
DIRS_IGNORADOS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "flatpak-repo",
        "flatpak-build-dir",
        "dist",
        "build",
        ".eggs",
    }
)

#: Documentos que não são varridos. `history/` e `research/` são arquivo morto
#: por definição -- descrevem o repositório como ele era, e cobrar deles o
#: presente é cobrar o impossível. É a mesma exclusão que o gate de acentuação
#: já aplica no .pre-commit-config.yaml.
#:
#: `process/agentes/` entrou em 06/08/2026 pelo mesmo motivo, e por mais um: é
#: saída BRUTA de agente, e um relatório cita o caminho que existia no instante
#: da medição — às vezes em `/tmp`, às vezes num arquivo que a própria leva
#: depois renomeou. Corrigir esses caminhos falsificaria o registro; cobrá-los
#: seria cobrar do passado o presente. O que NÃO é isento ali é segurança:
#: `tests/unit/test_saida_de_agente_sanitizada.py` varre MAC e segredo.
PREFIXOS_IGNORADOS = ("docs/history/", "docs/research/", "docs/process/agentes/")

#: Arquivos que existem, mas em OUTRO projeto. Citar `pydualsense.py` é citar a
#: biblioteca de terceiros; citar `universal-sanitizer.py` é citar a ferramenta
#: do ambiente da máquina. Nenhum dos dois deveria estar versionado aqui.
EXTERNOS = frozenset(
    {
        "pydualsense.py",
        "universal-sanitizer.py",
        "setup.py",
        "conftest.py",
    }
)

#: Marcador que a autora do documento pode escrever para dizer "eu sei que este
#: arquivo não existe, e o assunto do parágrafo é exatamente esse".
MARCADOR_ISENCAO = "<!-- ref-externa"

#: Documentos que ENSINAM -- os únicos varridos pelas regras 2 (variável de
#: ambiente) e 3 (método de IPC). Quem lê estes arquivos os copia para um
#: terminal; quem lê `docs/process/` está lendo história e proposta.
PREFIXOS_QUE_ENSINAM = ("docs/usage/", "docs/adr/", "docs/protocol/", "README.md")

#: Onde o índice de variáveis de ambiente procura literais. Tudo o que EXECUTA:
#: código, script, unit, empacotamento. Documento fica de fora de propósito --
#: senão o documento validaria a si mesmo e a regra 2 nasceria morta.
EXTENSOES_DE_CODIGO = frozenset(
    {
        ".py",
        ".sh",
        ".bash",
        ".service",
        ".toml",
        ".yml",
        ".yaml",
        ".rules",
        ".desktop",
        ".cfg",
        ".ini",
        ".in",
        ".json",
        ".rs",
        ".nix",
        ".c",
        ".h",
    }
)

#: Arquivos sem extensão que ainda assim executam (o instalador, o desinstalador
#: e o lançador ficam na raiz com `.sh`, mas o wrapper POSIX e o PKGBUILD não).
NOMES_DE_CODIGO = frozenset({"PKGBUILD", "Makefile", "hefesto-launch"})

#: Arquivos que NÃO alimentam o índice de variáveis de ambiente, ainda que
#: sejam código. Mesmo princípio que o `.pre-commit-config.yaml` já aplica aos
#: gates de acentuação e de glifos: o próprio validador e o teste dele precisam
#: escrever os nomes mortos que detectam, e sem esta exclusão o portão
#: autorizaria justamente o que existe para reprovar. Medido: sem ela,
#: `HEFESTO_PLUGINS_ENABLED` e `HEFESTO_DUALSENSE4UNIX_METRICS` entravam no
#: índice pelo cabeçalho DESTE arquivo e a regra 2 ficava cega aos dois.
ARQUIVOS_FORA_DO_INDICE_DE_ENV = frozenset(
    {
        "scripts/validar-referencias-docs.py",
        "tests/unit/test_validar_referencias_docs.py",
        "tests/unit/test_doc_verdade_02_contagens_derivadas.py",
    }
)

#: Sufixos que descartam um token `a.b` como NOME DE ARQUIVO, não método IPC.
#: `daemon.toml` e `daemon.pid` são os dois casos reais medidos na árvore de
#: 31/07 -- o resto é margem barata contra o falso positivo que a regra 3 mais
#: teme.
SUFIXOS_DE_ARQUIVO = frozenset(
    {
        "py",
        "sh",
        "md",
        "yml",
        "yaml",
        "toml",
        "glade",
        "rules",
        "json",
        "txt",
        "service",
        "po",
        "pot",
        "c",
        "h",
        "bin",
        "log",
        "patch",
        "desktop",
        "cfg",
        "ini",
        "in",
        "vdf",
        "env",
        "pid",
        "sock",
        "lock",
        "flag",
        "conf",
        "rs",
        "so",
        "ko",
        "deb",
        "xml",
        "html",
        "css",
        "js",
        "png",
        "svg",
        "gz",
        "zip",
        "bak",
        "tmp",
        "d",
    }
)

#: O registro de métodos vive aqui e é um `dict` de literais -- lido por AST,
#: sem importar o pacote (importar exigiria as dependências instaladas, e o
#: portão precisa rodar num runner pelado).
FONTE_DOS_METODOS_IPC = "src/hefesto_dualsense4unix/daemon/ipc_server.py"

_CRASE = re.compile(r"`([^`\n]{1,120})`")
_LINK = re.compile(r"\]\(([^)\s]{1,200})\)")
_CERCA = re.compile(r"^\s*(```|~~~)")
_TOKEN_LIMPO = re.compile(r"[A-Za-z0-9._/+-]+")
_ENV = re.compile(r"\bHEFESTO_[A-Z0-9_]+")
_METODO = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,2}$")
_NOTA_DE_VERIFICACAO = re.compile(r"^#{1,6}\s*Nota de verifica", re.IGNORECASE)

#: Rótulo humano de cada regra, para o relatório dizer O QUE está morto.
REGRA_ARQUIVO = "arquivo"
REGRA_ENV = "variável de ambiente"
REGRA_IPC = "método de IPC"


class Achado(NamedTuple):
    """Uma referência morta: documento, linha, o texto citado e a regra."""

    documento: str
    linha: int
    alvo: str
    regra: str = REGRA_ARQUIVO

    def __str__(self) -> str:
        return f"  {self.documento}:{self.linha}: {self.alvo}  [{self.regra}]"


def indexar(raiz: Path) -> set[str]:
    """Devolve todo caminho do repositório mais todos os seus sufixos.

    Indexar sufixo é o que faz `gui/main.glade` casar com o caminho real
    `src/hefesto_dualsense4unix/gui/main.glade`. Diretório entra junto: a
    documentação cita `docs/process/sprints/` tanto quanto cita arquivo.

    Percorre o disco em vez de perguntar ao git de propósito: `git ls-files` é
    cego a arquivo novo ainda não adicionado ao índice, e o arquivo recém
    criado é justamente o que a documentação acabou de passar a citar.
    """
    sufixos: set[str] = set()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if d not in DIRS_IGNORADOS]
        base = Path(pasta)
        for nome in list(arquivos) + list(subpastas):
            try:
                relativo = (base / nome).relative_to(raiz).as_posix()
            except ValueError:  # pragma: no cover - defensivo
                continue
            partes = relativo.split("/")
            for corte in range(len(partes)):
                sufixos.add("/".join(partes[corte:]))
    return sufixos


def indexar_envs(raiz: Path) -> set[str]:
    """Todo literal `HEFESTO_*` que aparece em código, script ou empacotamento.

    Documento NÃO entra: se `docs/` alimentasse o índice, um documento que
    inventa uma variável passaria a se autoautorizar, e a regra 2 nasceria
    morta. O índice é o que EXECUTA.
    """
    encontrados: set[str] = set()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if d not in DIRS_IGNORADOS]
        base = Path(pasta)
        try:
            relativo_pasta = base.relative_to(raiz).as_posix()
        except ValueError:  # pragma: no cover - defensivo
            continue
        if relativo_pasta.startswith("docs"):
            continue
        for nome in arquivos:
            caminho = base / nome
            if caminho.suffix not in EXTENSOES_DE_CODIGO and nome not in NOMES_DE_CODIGO:
                continue
            relativo = f"{relativo_pasta}/{nome}" if relativo_pasta != "." else nome
            if relativo in ARQUIVOS_FORA_DO_INDICE_DE_ENV:
                continue
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            encontrados.update(_ENV.findall(texto))
    return encontrados


def indexar_metodos_ipc(raiz: Path) -> set[str]:
    """As chaves do dicionário `_handlers` de `daemon/ipc_server.py`, por AST.

    Ler por AST em vez de importar é deliberado: o portão roda em runner sem as
    dependências do projeto instaladas, e um `ImportError` viraria "zero
    métodos registrados" -- o que faria a regra 3 acusar TODO método citado. Um
    gate que reprova tudo quando tropeça é pior que gate nenhum, então a
    ausência do arquivo devolve conjunto vazio e a regra 3 se desliga sozinha
    (ver `varrer_documento`).
    """
    fonte = raiz / FONTE_DOS_METODOS_IPC
    try:
        arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()

    metodos: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            se_e_o_registro = isinstance(alvo, ast.Attribute) and alvo.attr == "_handlers"
            if not se_e_o_registro or not isinstance(no.value, ast.Dict):
                continue
            for chave in no.value.keys:
                if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
                    metodos.add(chave.value)
    return metodos


def tokens_isentos_por_nota(conteudo: str) -> set[str]:
    """Tokens citados a partir de um cabeçalho "Nota de verificação".

    Padrão da casa para ADR: a decisão original não se reescreve; acrescenta-se
    uma nota datada no fim dizendo o que caducou. Essa nota PRECISA nomear o
    valor errado -- é a informação inteira dela. Sem esta isenção o portão
    reprovaria justamente o documento que foi corrigido direito.
    """
    linhas = conteudo.splitlines()
    inicio: int | None = None
    for indice, linha in enumerate(linhas):
        if _NOTA_DE_VERIFICACAO.match(linha):
            inicio = indice
            break
    if inicio is None:
        return set()

    isentos: set[str] = set()
    for linha in linhas[inicio:]:
        for bruto in _CRASE.findall(linha):
            isentos.update(_ENV.findall(bruto))
            texto = bruto.strip()
            if _METODO.fullmatch(texto):
                isentos.add(texto)
    return isentos


def envs_da_linha(linha: str) -> list[str]:
    """Variáveis `HEFESTO_*` citadas entre crases nesta linha."""
    achados: list[str] = []
    for bruto in _CRASE.findall(linha):
        achados.extend(_ENV.findall(bruto))
    return achados


def metodos_da_linha(linha: str, espacos_de_nomes: frozenset[str]) -> list[str]:
    """Tokens `a.b`/`a.b.c` entre crases cujo primeiro segmento é do IPC."""
    achados: list[str] = []
    for bruto in _CRASE.findall(linha):
        texto = bruto.strip()
        if not _METODO.fullmatch(texto):
            continue
        segmentos = texto.split(".")
        if segmentos[0] not in espacos_de_nomes:
            continue
        if segmentos[-1] in SUFIXOS_DE_ARQUIVO:
            continue
        achados.append(texto)
    return achados


def candidatos_da_linha(linha: str) -> list[str]:
    """Extrai da linha os textos com cara de caminho de arquivo.

    A origem importa. Texto entre crases é ambíguo -- pode ser nome de módulo,
    de comando ou de conceito -- e por isso passa pelo filtro estreito de
    `EXTENSOES_NOME_SOLTO`. Já o alvo de um link markdown é inequívoco: quem
    escreve [texto](alvo) está afirmando que existe algo naquele caminho. Um
    índice de sprints apontando para arquivo que não existe é justamente um
    dos defeitos que a sprint mandou pegar, e ele aparece só nessa forma.
    """
    brutos = [(m.group(1), True) for m in _CRASE.finditer(linha)]
    brutos += [(m.group(1), False) for m in _LINK.finditer(linha)]

    limpos: list[str] = []
    for bruto, veio_de_crase in brutos:
        texto = bruto.strip()
        if not texto or " " in texto:
            continue
        if texto.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # `arquivo.py:551-567` e `doc.md#secao` citam trecho: fica só o caminho.
        texto = texto.split(":", 1)[0].split("#", 1)[0]
        if texto.startswith("./"):
            texto = texto[2:]
        if not texto:
            continue
        if texto[0] in "/~$":
            continue
        if any(ruim in texto for ruim in ("*", "?", "<", ">", "..", "{", "}")):
            continue
        if not _TOKEN_LIMPO.fullmatch(texto):
            continue
        extensao = Path(texto).suffix
        if extensao not in EXTENSOES:
            continue
        if veio_de_crase and "/" not in texto and extensao not in EXTENSOES_NOME_SOLTO:
            continue
        if Path(texto).name in EXTERNOS:
            continue
        limpos.append(texto)
    return limpos


def varrer_documento(
    caminho: Path,
    raiz: Path,
    sufixos: set[str],
    envs: set[str] | None = None,
    metodos_ipc: set[str] | None = None,
) -> list[Achado]:
    """Devolve as referências mortas de um documento -- as três regras.

    As regras 2 e 3 só valem para os documentos que ENSINAM
    (`PREFIXOS_QUE_ENSINAM`) e se desligam sozinhas quando o índice
    correspondente vem vazio: sem literal de env no código não há como
    distinguir variável morta de variável nova, e acusar tudo seria o oposto
    do que este portão existe para fazer.
    """
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    relativo_doc = caminho.resolve().relative_to(raiz).as_posix()
    ensina = relativo_doc.startswith(PREFIXOS_QUE_ENSINAM)
    cobra_env = ensina and bool(envs)
    cobra_ipc = ensina and bool(metodos_ipc)
    espacos_de_nomes = frozenset(
        m.split(".")[0] for m in (metodos_ipc or set()) if "." in m
    )
    isentos_por_nota = (
        tokens_isentos_por_nota(conteudo) if (cobra_env or cobra_ipc) else set()
    )

    achados: list[Achado] = []
    dentro_de_cerca = False

    for numero, linha in enumerate(conteudo.splitlines(), start=1):
        if _CERCA.match(linha):
            dentro_de_cerca = not dentro_de_cerca
            continue
        if dentro_de_cerca:
            continue
        if MARCADOR_ISENCAO in linha:
            continue

        for referencia in candidatos_da_linha(linha):
            if referencia in sufixos:
                continue
            # Última chance: link relativo ao diretório do próprio documento.
            vizinho = (caminho.parent / referencia).resolve()
            try:
                relativo = vizinho.relative_to(raiz).as_posix()
            except ValueError:
                relativo = None
            if relativo is not None and relativo in sufixos:
                continue
            achados.append(Achado(relativo_doc, numero, referencia, REGRA_ARQUIVO))

        if cobra_env:
            for variavel in envs_da_linha(linha):
                if variavel in envs or variavel in isentos_por_nota:
                    continue
                achados.append(Achado(relativo_doc, numero, variavel, REGRA_ENV))

        if cobra_ipc:
            for metodo in metodos_da_linha(linha, espacos_de_nomes):
                if metodo in metodos_ipc or metodo in isentos_por_nota:
                    continue
                achados.append(Achado(relativo_doc, numero, metodo, REGRA_IPC))

    return achados


def documentos_de(raiz: Path) -> list[Path]:
    """Todos os .md sob docs/ menos o arquivo morto, mais o `README.md`.

    O README entrou na varredura com a DOC-VERDADE-02: ele é a página que mais
    gente copia e cola, e ficava fora do portão só porque mora na raiz.
    """
    encontrados = []
    readme = raiz / "README.md"
    if readme.is_file():
        encontrados.append(readme)

    pasta = raiz / "docs"
    if not pasta.is_dir():
        return encontrados
    for md in sorted(pasta.rglob("*.md")):
        relativo = md.relative_to(raiz).as_posix()
        if relativo.startswith(PREFIXOS_IGNORADOS):
            continue
        encontrados.append(md)
    return encontrados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova documento que cita arquivo inexistente."
    )
    parser.add_argument("arquivos", nargs="*", type=Path, help="documentos a varrer")
    parser.add_argument("--all", action="store_true", help="varre docs/ inteiro")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}")
        return 2

    if args.all:
        alvos = documentos_de(raiz)
    else:
        alvos = [p for p in args.arquivos if p.suffix == ".md" and p.is_file()]
    if not alvos:
        print("Nenhum documento para varrer.")
        return 0

    sufixos = indexar(raiz)
    envs = indexar_envs(raiz)
    metodos_ipc = indexar_metodos_ipc(raiz)
    achados: list[Achado] = []
    for alvo in alvos:
        achados.extend(varrer_documento(alvo, raiz, sufixos, envs, metodos_ipc))

    if achados:
        print(f"{len(achados)} referência(s) morta(s) em {len(alvos)} documento(s):")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um arquivo, uma variável de ambiente ou um")
        print("método de IPC que NÃO existe nesta árvore. Corrija o nome, crie o")
        print("que falta, ou -- se a ausência for o assunto do parágrafo --")
        print("marque a linha com o comentário de isenção descrito no cabeçalho")
        print("deste script. Em ADR, a nota de verificação datada no fim do")
        print("arquivo já isenta o documento inteiro daquele nome.")
        return 1

    print(f"OK: {len(alvos)} documento(s) sem referência morta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
