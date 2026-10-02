#!/usr/bin/env python3
"""Move para `arquivados/` a sprint cujo frontmatter diz que ela fechou — e"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

ARQUIVADOS = "arquivados"

FECHADOS = ("feita", "absorvida", "caducou")

SUBPASTA_DAS_SPRINTS = Path("docs") / "process" / "sprints"

PASTAS_FORA = frozenset({
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "build", "dist", ".eggs", ".tox",
})

SUFIXOS_FORA = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".xz", ".bz2", ".tar", ".whl", ".so", ".o", ".a", ".bin", ".hid", ".pcap",
    ".btsnoop", ".mo", ".ttf", ".otf", ".woff", ".woff2", ".wav", ".ogg",
    ".mp3", ".mp4", ".pyc",
})

TETO_DE_LEITURA = 8 * 1024 * 1024


class SprintSumida(FileNotFoundError):
    """A pasta está no disco e o alvo não. Isto GRITA, nunca devolve vazio."""


_ESTADO = re.compile(r"^estado:\s*([A-Za-zÀ-ÿ]+)\s*$")


def estado_da_sprint(texto: str) -> str | None:
    """O `estado:` do bloco de frontmatter, ou ``None`` se não houver bloco."""
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != "---":
        return None
    for linha in linhas[1:]:
        if linha.strip() == "---":
            return "aberta"
        achado = _ESTADO.match(linha.strip())
        if achado:
            return achado.group(1).strip().lower()
    return None


def campo_de_lista(texto: str, campo: str) -> list[str]:
    """Os itens de um campo de lista do frontmatter (`cria:`, `nao_toca:`)."""
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != "---":
        return []
    itens: list[str] = []
    dentro = False
    for linha in linhas[1:]:
        if linha.strip() == "---":
            break
        if not linha.startswith((" ", "\t")) and linha.strip().endswith(":"):
            dentro = linha.strip()[:-1] == campo
            continue
        cabeca = f"{campo}:"
        if linha.startswith(cabeca):
            resto = linha[len(cabeca):].strip()
            if resto.startswith("["):
                miolo = resto[1:-1] if resto.endswith("]") else resto[1:]
                itens += [p.strip().strip("'\"") for p in miolo.split(",") if p.strip()]
                dentro = False
            else:
                dentro = True
            continue
        if dentro and linha.strip().startswith("- "):
            itens.append(linha.strip()[2:].strip().strip("'\""))
        elif dentro and linha.strip() and not linha.startswith((" ", "\t")):
            dentro = False
    return itens


@dataclass(frozen=True)
class Sprint:
    arquivo: Path
    relativo: str
    estado: str

    @property
    def destino(self) -> Path:
        """A gaveta é irmã do arquivo, não um caminho escrito à mão."""
        return self.arquivo.parent / ARQUIVADOS / self.arquivo.name


def sprints_da_pasta_viva(raiz: Path) -> list[Sprint]:
    """Toda sprint que está FORA da gaveta, com o estado que ela declara."""
    pasta = raiz / SUBPASTA_DAS_SPRINTS
    if not pasta.is_dir():
        return []
    achadas: list[Sprint] = []
    for arquivo in sorted(pasta.rglob("*.md")):
        if ARQUIVADOS in arquivo.relative_to(pasta).parts:
            continue
        estado = estado_da_sprint(_texto(arquivo))
        if estado is None:
            continue
        achadas.append(Sprint(arquivo, str(arquivo.relative_to(raiz)), estado))
    return achadas


def _texto(arquivo: Path) -> str:
    try:
        return arquivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


@dataclass(frozen=True)
class Citacao:
    citador: str
    linha: int
    classe: str
    trecho: str

    def __str__(self) -> str:
        return f"{self.citador}:{self.linha}  {self.trecho}"


def _arquivos_de_prosa(raiz: Path):
    """Todo arquivo da árvore que pode conter uma citação, e só esses."""
    pilha = [raiz]
    while pilha:
        pasta = pilha.pop()
        try:
            entradas = sorted(pasta.iterdir())
        except OSError:
            continue
        for entrada in entradas:
            if entrada.is_symlink():
                continue
            if entrada.is_dir():
                if entrada.name not in PASTAS_FORA:
                    pilha.append(entrada)
                continue
            if entrada.suffix.lower() in SUFIXOS_FORA:
                continue
            try:
                if entrada.stat().st_size > TETO_DE_LEITURA:
                    continue
            except OSError:
                continue
            yield entrada


def quem_cita(raiz: Path, nomes: list[str]) -> dict[str, list[Citacao]]:
    """Para cada nome de arquivo, quem o alcança e de que forma."""
    if not nomes:
        return {}
    achado: dict[str, list[Citacao]] = {nome: [] for nome in nomes}
    agulha = re.compile("|".join(re.escape(nome) for nome in nomes))
    for arquivo in _arquivos_de_prosa(raiz):
        texto = _texto(arquivo)
        if not texto or not any(nome in texto for nome in nomes):
            continue
        relativo = str(arquivo.relative_to(raiz))
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for casa in agulha.finditer(linha):
                nome = casa.group(0)
                if _e_a_propria_sprint(relativo, nome):
                    continue
                classe = _classe_da_citacao(linha, casa.start(), casa.end())
                if classe is None:
                    continue
                achado[nome].append(
                    Citacao(relativo, numero, classe, linha.strip()[:160]))
    return achado


def _e_a_propria_sprint(relativo: str, nome: str) -> bool:
    """O arquivo que se nomeia não é citação de ninguém."""
    return Path(relativo).name == nome


_ANTES_DE_PASTA = re.compile(r"([A-Za-z0-9_./~-]+)/$")


def _classe_da_citacao(linha: str, inicio: int, fim: int) -> str | None:
    """`caminho` trava; `nome` avisa; ``None`` não é citação."""
    antes = linha[:inicio]
    depois = linha[fim:]

    if depois[:1] and (depois[0].isalnum() or depois[0] in "_-"):
        return None

    pasta = _ANTES_DE_PASTA.search(antes)
    if pasta:
        if pasta.group(1).rstrip("/").endswith(ARQUIVADOS):
            return None
        return "caminho"

    if antes.endswith("]("):
        return "caminho"
    return "nome"


def mover(sprint: Sprint, raiz: Path) -> str:
    """Leva a sprint para a gaveta. Só é chamada depois da trava."""
    if not sprint.arquivo.exists():
        raise SprintSumida(
            f"a sprint sumiu entre a medição e a mudança: {sprint.relativo}")
    destino = sprint.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        raise FileExistsError(
            f"já existe na gaveta: {destino.relative_to(raiz)} — duas sprints "
            f"com o mesmo nome é achado, não rotina")
    if _versionada(sprint.arquivo, raiz):
        subprocess.run(
            ["git", "mv", "--", str(sprint.arquivo.relative_to(raiz)),
             str(destino.relative_to(raiz))],
            cwd=raiz, check=True, capture_output=True)
    else:
        sprint.arquivo.rename(destino)
    return str(destino.relative_to(raiz))


def _versionada(arquivo: Path, raiz: Path) -> bool:
    """`docs/process/` é `.gitignore`, mas o script não confia nisso."""
    try:
        pronto = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--",
             str(arquivo.relative_to(raiz))],
            cwd=raiz, capture_output=True)
    except (OSError, ValueError):
        return False
    return pronto.returncode == 0


_PREFIXOS_DA_ARVORE = (
    "src/", "scripts/", "tests/", "docs/", "layout/", "mockup/", "assets/",
    "html/", "packaging/", "po/", "locale/", "examples/", "flatpak/",
)
_SUFIXOS_DE_ARQUIVO = (
    ".py", ".sh", ".md", ".html", ".css", ".js", ".json", ".csv", ".toml",
    ".yml", ".yaml", ".glade", ".rules", ".svg", ".conf", ".desktop",
)
_PACOTE = "hefesto_dualsense4unix"


@dataclass
class TesteMedido:
    """Um teste e o que ele mede que não está mais lá."""

    arquivo: str
    simbolos: list[str] = field(default_factory=list)
    caminhos: list[str] = field(default_factory=list)

    @property
    def mortos(self) -> list[str]:
        return self.simbolos + self.caminhos


def _modulo_no_disco(raiz: Path, pontilhado: str) -> Path | None:
    partes = pontilhado.split(".")
    base = raiz / "src"
    caminho = base.joinpath(*partes)
    if (caminho / "__init__.py").is_file():
        return caminho / "__init__.py"
    arquivo = caminho.with_suffix(".py")
    return arquivo if arquivo.is_file() else None


_ABRIGOS = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor,
            ast.While)


def _nomes_do_topo(arquivo: Path) -> set[str] | None:
    """Todo nome que o módulo publica, inclusive o que nasce sob guarda."""
    try:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    nomes: set[str] = set()

    def desce(corpo: list[ast.stmt]) -> None:
        for no in corpo:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
                nomes.add(no.name)
            elif isinstance(no, ast.Assign):
                for alvo in no.targets:
                    for nome in _nomes_do_alvo(alvo):
                        nomes.add(nome)
                        if nome == "__all__":
                            nomes.update(_literais_de_lista(no.value))
            elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
                nomes.add(no.target.id)
            elif isinstance(no, (ast.Import, ast.ImportFrom)):
                for apelido in no.names:
                    nomes.add(apelido.asname or apelido.name.split(".")[0])
            elif isinstance(no, _ABRIGOS):
                desce(no.body)
                desce(getattr(no, "orelse", []))
                for tratador in getattr(no, "handlers", []):
                    desce(tratador.body)
                desce(getattr(no, "finalbody", []))

    desce(arvore.body)
    return nomes


def _nomes_do_alvo(alvo: ast.expr) -> set[str]:
    """Os nomes que UM alvo de atribuição publica — inclusive o desempacotado."""
    if isinstance(alvo, ast.Name):
        return {alvo.id}
    if isinstance(alvo, (ast.Tuple, ast.List)):
        achados: set[str] = set()
        for parte in alvo.elts:
            achados |= _nomes_do_alvo(parte)
        return achados
    if isinstance(alvo, ast.Starred):
        return _nomes_do_alvo(alvo.value)
    return set()


def _literais_de_lista(no: ast.expr) -> set[str]:
    if not isinstance(no, (ast.List, ast.Tuple, ast.Set)):
        return set()
    return {e.value for e in no.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)}


def _alvo_pontilhado_morto(raiz: Path, alvo: str) -> str | None:
    """Resolve `a.b.c` contra o disco. Devolve o motivo, ou ``None``."""
    partes = alvo.split(".")
    if not partes or partes[0] != _PACOTE or len(partes) < 2:
        return None
    if not all(p.isidentifier() for p in partes):
        return None
    for corte in range(len(partes), 0, -1):
        modulo = ".".join(partes[:corte])
        arquivo = _modulo_no_disco(raiz, modulo)
        if arquivo is None:
            continue
        if corte == len(partes):
            return None
        nomes = _nomes_do_topo(arquivo)
        if nomes is None:
            return None
        if partes[corte] in nomes:
            return None
        return f"{alvo} — `{partes[corte]}` não existe em {modulo}"
    return f"{alvo} — módulo inexistente"


def _caminho_morto(raiz: Path, bruto: str) -> str | None:
    if not bruto.startswith(_PREFIXOS_DA_ARVORE):
        return None
    if not bruto.endswith(_SUFIXOS_DE_ARQUIVO):
        return None
    if any(c in bruto for c in "*?{}<>%"):
        return None
    if (raiz / bruto).exists():
        return None
    p = Path(bruto)
    if (raiz / p.parent / ARQUIVADOS / p.name).exists():
        return None
    return f"{bruto} — não existe na árvore"


def mede_os_testes(raiz: Path) -> tuple[list[TesteMedido], dict[str, list[str]]]:
    """As duas leituras da ordem dela, medidas e devolvidas separadas."""
    pasta = raiz / "tests"
    leitura_a: list[TesteMedido] = []
    if pasta.is_dir():
        for arquivo in sorted(pasta.rglob("test_*.py")):
            medido = TesteMedido(str(arquivo.relative_to(raiz)))
            try:
                arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for no in ast.walk(arvore):
                if isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                    for apelido in no.names:
                        motivo = _alvo_pontilhado_morto(
                            raiz, f"{no.module}.{apelido.name}")
                        if motivo:
                            medido.simbolos.append(motivo)
                elif isinstance(no, ast.Import):
                    for apelido in no.names:
                        if (apelido.name.startswith(_PACOTE)
                                and _modulo_no_disco(raiz, apelido.name) is None):
                            medido.simbolos.append(
                                f"{apelido.name} — módulo inexistente")
                elif isinstance(no, ast.Constant) and isinstance(no.value, str):
                    motivo = _alvo_pontilhado_morto(raiz, no.value)
                    if motivo:
                        medido.simbolos.append(motivo)
                        continue
                    motivo = _caminho_morto(raiz, no.value)
                    if motivo:
                        medido.caminhos.append(motivo)
            if medido.simbolos or medido.caminhos:
                medido.simbolos = sorted(set(medido.simbolos))
                medido.caminhos = sorted(set(medido.caminhos))
                leitura_a.append(medido)

    leitura_b: dict[str, list[str]] = {}
    pasta_sprints = raiz / SUBPASTA_DAS_SPRINTS
    if pasta_sprints.is_dir():
        for sprint in sorted(pasta_sprints.rglob("*.md")):
            texto = _texto(sprint)
            if estado_da_sprint(texto) not in FECHADOS:
                continue
            for criado in campo_de_lista(texto, "cria"):
                alvo = criado.strip().strip("`")
                if not alvo.startswith("tests/") or not alvo.endswith(".py"):
                    continue
                if (raiz / alvo).is_file():
                    leitura_b.setdefault(alvo, []).append(
                        str(sprint.relative_to(raiz)))
    return leitura_a, leitura_b


def separa_presas_e_livres(
    fechadas: list[Sprint], citacoes: dict[str, list[Citacao]],
) -> tuple[list[Sprint], list[Sprint]]:
    """(as que a citação por caminho segura, as que podem descer agora)."""
    presas: list[Sprint] = []
    livres: list[Sprint] = []
    for sprint in fechadas:
        travam = [c for c in citacoes[sprint.arquivo.name] if c.classe == "caminho"]
        (presas if travam else livres).append(sprint)
    return presas, livres


def _relata(raiz: Path, mover_de_verdade: bool) -> int:
    pasta = raiz / SUBPASTA_DAS_SPRINTS
    if not pasta.is_dir():
        print(f"sem {SUBPASTA_DAS_SPRINTS}/ nesta árvore — nada a medir.")
        return 0

    todas = sprints_da_pasta_viva(raiz)
    fechadas = [s for s in todas if s.estado in FECHADOS]
    abertas = [s for s in todas if s.estado not in FECHADOS]

    print(f"na pasta viva: {len(todas)} com frontmatter "
          f"({len(abertas)} aberta(s), {len(fechadas)} fechada(s))")
    if not fechadas:
        print("nada a mover.")
        return 0

    citacoes = quem_cita(raiz, [s.arquivo.name for s in fechadas])
    presas, livres = separa_presas_e_livres(fechadas, citacoes)

    print()
    print(f"PRESAS pela citação: {len(presas)}")
    for sprint in presas:
        todas_delas = citacoes[sprint.arquivo.name]
        travam = [c for c in todas_delas if c.classe == "caminho"]
        print(f"  {sprint.relativo}  [{sprint.estado}]")
        for citacao in travam:
            print(f"      {citacao}")

    print()
    print(f"LIVRES para descer: {len(livres)}")
    for sprint in livres:
        soltas = [c for c in citacoes[sprint.arquivo.name] if c.classe == "nome"]
        aviso = f"  ({len(soltas)} citação(ões) só pelo nome, que sobrevivem)" if soltas else ""
        print(f"  {sprint.relativo}  [{sprint.estado}]{aviso}")

    if not mover_de_verdade:
        print()
        print("SECO: nada foi movido. Use --mover para descer as LIVRES.")
        return 0

    print()
    for sprint in livres:
        destino = mover(sprint, raiz)
        print(f"movida: {sprint.relativo}  ->  {destino}")
    print(f"{len(livres)} movida(s); {len(presas)} presa(s) pela citação.")
    return 0


def _relata_testes(raiz: Path) -> int:
    leitura_a, leitura_b = mede_os_testes(raiz)
    total = sum(1 for _ in (raiz / "tests").rglob("test_*.py")) if (raiz / "tests").is_dir() else 0

    com_simbolo = [m for m in leitura_a if m.simbolos]
    so_caminho = [m for m in leitura_a if not m.simbolos]

    print(f"EIXO 4 — {total} arquivos de teste na árvore.")
    print()
    print(f"LEITURA A (mede o que não existe mais): {len(leitura_a)}")
    print(f"  A1 — símbolo do pacote que não resolve: {len(com_simbolo)}"
          "   (o achado forte)")
    for medido in com_simbolo:
        print(f"    {medido.arquivo}")
        for morto in medido.simbolos:
            print(f"        {morto}")
    print(f"  A2 — só caminho da árvore que não existe: {len(so_caminho)}"
          "   (triagem: há fixture negativa de propósito)")
    for medido in so_caminho:
        print(f"    {medido.arquivo}")
        for morto in medido.caminhos:
            print(f"        {morto}")
    print()
    print(f"LEITURA B (nasceu de sprint já fechada): {len(leitura_b)}")
    for alvo in sorted(leitura_b):
        print(f"  {alvo}   <- {', '.join(Path(s).name for s in leitura_b[alvo])}")
    print()
    print("NADA FOI MOVIDO EM tests/, E NÃO É OMISSÃO.")
    print("  A leitura B é armadilha: um teste não morre porque a sprint dele")
    print("  fechou — ele passa a ser a única coisa que impede a regressão")
    print("  daquele trabalho. Arquivar teste vivo é arrancar a mordida de")
    print("  tudo o que já foi pago.")
    print("  A leitura A é legítima, e mesmo ela é triagem humana: o alvo pode")
    print("  ter mudado de nome em vez de morrer.")
    return 0


def _exige(raiz: Path) -> int:
    """rc=1 só quando há sprint fechada que PODE descer agora."""
    pasta = raiz / SUBPASTA_DAS_SPRINTS
    if not pasta.is_dir():
        print(f"NÃO MEDIDO: não há {SUBPASTA_DAS_SPRINTS}/ nesta árvore.")
        print("  A pasta é .gitignore:178 e não viaja pelo git, então um clone")
        print("  limpo não a tem. Isto NÃO é 'nenhuma sprint fechada' — é")
        print("  ausência de dado, e dizer 'OK' aqui seria verde sobre nada.")
        return 0

    fechadas = [s for s in sprints_da_pasta_viva(raiz) if s.estado in FECHADOS]
    if not fechadas:
        print("OK: nenhuma sprint fechada na pasta viva.")
        return 0

    citacoes = quem_cita(raiz, [s.arquivo.name for s in fechadas])
    presas, livres = separa_presas_e_livres(fechadas, citacoes)

    if presas:
        print(f"presas pela citação, e FICAM: {len(presas)}")
        for sprint in presas:
            print(f"  {sprint.relativo}  [{sprint.estado}]")
        print("  Elas não reprovam: o reaponte é ato humano, e")
        print("  scripts/validar-referencias-docs.py diz o endereço de cada uma.")
        print()

    if not livres:
        print(f"OK: {len(fechadas)} fechada(s) na pasta viva, todas presas "
              "por citação de caminho. Nada pode descer sem reaponte.")
        return 0

    print(f"{len(livres)} sprint(s) fechada(s) podem descer AGORA:")
    for sprint in livres:
        print(f"  {sprint.relativo}  [{sprint.estado}]")
    print("Rode scripts/mover-sprints-fechadas.py --mover para descê-las.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move para arquivados/ a sprint que o frontmatter diz "
                    "fechada — e recusa a que alguém ainda cita pelo caminho.")
    parser.add_argument("--seco", action="store_true",
                        help="só relata (é o padrão; existe para ser escrito)")
    parser.add_argument("--mover", action="store_true",
                        help="move de verdade o que passou na trava")
    parser.add_argument("--testes", action="store_true",
                        help="mede tests/ nas duas leituras. Nunca move.")
    parser.add_argument("--exigir", action="store_true",
                        help="rc=1 se alguma fechada PODE descer agora "
                             "(a presa por citação não reprova)")
    parser.add_argument("--raiz", type=Path, default=RAIZ_PADRAO,
                        help="outra árvore (bancada de teste)")
    args = parser.parse_args(argv)

    raiz = args.raiz.resolve()
    if args.testes:
        return _relata_testes(raiz)

    if args.exigir:
        return _exige(raiz)

    return _relata(raiz, mover_de_verdade=args.mover and not args.seco)


if __name__ == "__main__":
    sys.exit(main())
