#!/usr/bin/env python3
"""Move para `arquivados/` a sprint cujo frontmatter diz que ela fechou — e
RECUSA mover a que alguém ainda alcança pelo caminho.

A ORDEM DELA, repetida duas vezes
---------------------------------
17/09/2026: *"Temos que ter um hook pra isso não? Corrigir, sobrescrever e
encurtar info datada."*

20/09/2026: *"temos que ter um hook pra pegar o frontmatter tudo que tiver
concluido e mover pro arquivo automaticamente não?"* e *"temos que mover os
testes tambem inclusive."*  <!-- noqa-acento: citação literal dela -->

O PREÇO JÁ PAGO, e é a razão de a trava existir
-----------------------------------------------
Mover sprint fechada JÁ APAGOU o gesto de 199 testes, calado. A leva que tirou
as 732 fechadas da pasta viva levou junto os dois donos do gesto da mesa de
medição; `scripts/mesa_de_medicao.py` digitava o caminho, não achou e devolveu
`{}` sem uma linha de aviso. As células caíram no fallback da procedência e
sete réguas ficaram vermelhas sem que nenhuma soubesse dizer por quê. A raiz
está curada em `06396e232` — `_o_dono_do_gesto` procura nos dois lugares e
LEVANTA quando o dono some de verdade.

A lição manda no desenho deste script: *mover um arquivo quebra todo caminho
que o cita, e o silêncio é o que custa.* Por isso a varredura de citação não é
um extra — é metade da ferramenta, e ela roda ANTES de qualquer renomeação.

AS DUAS CLASSES DE CITAÇÃO, e só uma trava
------------------------------------------
Depois da mudança o arquivo existe em `<pasta>/arquivados/<nome>.md`, e o que
some é o caminho antigo. Então:

``caminho``  a citação fixa uma PASTA antes do nome (`…/sprints/X.md`), ou é
             alvo de link markdown (`](X.md)`). As duas quebram no ato.
             **TRAVA: não move, e nomeia quem cita, com `arquivo:linha`.**

``nome``     o nome aparece solto, sem pasta. Sobrevive: `referencias-docs`
             confere por SUFIXO, e `arquivados/X.md` termina em `X.md`.
             **Não trava — mas sai no relatório**, porque quem lê a lista
             decide melhor que quem a esconde.

Uma citação que já aponta para `arquivados/` é o destino, não o passado: ela
não trava.

O QUE ESTE SCRIPT NÃO FAZ
-------------------------
**Não move nada em `tests/`.** `--testes` MEDE as duas leituras da ordem dela e
recusa mover as duas, pelo motivo impresso na saída: um teste não morre porque
a sprint dele fechou — ele passa a ser a única coisa que impede a regressão
daquele trabalho, e *teste tem de MORDER* é regra desta casa.

**Não roda em timer.** Mover arquivo por trás de quem está trabalhando é a
família de defeito que esta casa persegue. Lugar dele é o gancho de commit ou
o `portoes.sh`, onde há alguém olhando.

**Não julga conteúdo.** A fronteira é o `estado:` do frontmatter e nada mais —
`feita`, `absorvida` e `caducou` descem; `aberta` e sprint SEM frontmatter
ficam onde estão.

Uso::

    scripts/mover-sprints-fechadas.py            # relata, não move (o padrão)
    scripts/mover-sprints-fechadas.py --mover    # move o que passou na trava
    scripts/mover-sprints-fechadas.py --testes   # mede `tests/`, nunca move
    scripts/mover-sprints-fechadas.py --raiz DIR # outra árvore (bancada)
    scripts/mover-sprints-fechadas.py --exigir   # a forma de PORTÃO

`--exigir` é o que o `portoes.sh` roda, e ele reprova **só o que tem
conserto**: a fechada LIVRE, que um `--mover` derruba. A presa por citação sai
nomeada e não reprova — segurá-la é o trabalho da trava, e puni-la seria um
vermelho sem conserto. Sem a pasta no disco ele diz NÃO MEDIDO, nunca «OK».

`--seco` existe e é o padrão: escrever o nome dele não muda nada, e é assim
que se pede o relatório sem medo em qualquer dúvida.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

#: A gaveta. O nome é o mesmo que `scripts/mesa_de_medicao.py` procura quando o
#: dono do gesto sai da pasta viva — os dois têm de concordar, senão arquivar
#: volta a apagar o gesto em silêncio.
ARQUIVADOS = "arquivados"

#: A fronteira, e ela é só esta. `aberta` é o padrão de quem não escreveu nada.
FECHADOS = ("feita", "absorvida", "caducou")

#: Onde as sprints moram, relativo à raiz.
SUBPASTA_DAS_SPRINTS = Path("docs") / "process" / "sprints"

#: Pastas que a varredura de citação não abre. `.git` guarda a história em
#: binário; as outras são artefato que ninguém cita de volta.
PASTAS_FORA = frozenset({
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "build", "dist", ".eggs", ".tox",
})

#: Extensões que não guardam prosa. Ler 1,8 MB de PNG atrás de um nome de
#: arquivo é gastar relógio para não achar nada.
SUFIXOS_FORA = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".xz", ".bz2", ".tar", ".whl", ".so", ".o", ".a", ".bin", ".hid", ".pcap",
    ".btsnoop", ".mo", ".ttf", ".otf", ".woff", ".woff2", ".wav", ".ogg",
    ".mp3", ".mp4", ".pyc",
})

#: Teto por arquivo. O `specs.html` tem 1,3 MB e é prosa legítima; acima disso
#: é dado gerado, e dado gerado que cita sprint é defeito de outro portão.
TETO_DE_LEITURA = 8 * 1024 * 1024


class SprintSumida(FileNotFoundError):
    """A pasta está no disco e o alvo não. Isto GRITA, nunca devolve vazio."""


# ---------------------------------------------------------------------------
# O frontmatter — o mesmo formato que `check_colisao_de_sprints.py` lê
# ---------------------------------------------------------------------------

_ESTADO = re.compile(r"^estado:\s*([A-Za-zÀ-ÿ]+)\s*$")


def estado_da_sprint(texto: str) -> str | None:
    """O `estado:` do bloco de frontmatter, ou ``None`` se não houver bloco.

    Devolver ``None`` NÃO é o mesmo que devolver `aberta`: sprint sem
    frontmatter nunca é candidata, porque quem não declarou não pediu para
    descer. Os dois casos saem separados no relatório.
    """
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
    """Os itens de um campo de lista do frontmatter (`cria:`, `nao_toca:`).

    Analisador pequeno de propósito, igual ao da casa: lê o bloco entre os dois
    ``---`` e só as duas formas que as sprints usam — a lista em linhas com
    ``-`` e a lista em colchetes na mesma linha.
    """
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


# ---------------------------------------------------------------------------
# As candidatas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sprint:
    arquivo: Path
    relativo: str
    estado: str

    @property
    def destino(self) -> Path:
        """A gaveta é irmã do arquivo, não um caminho escrito à mão.

        Assim uma sprint que more numa subpasta (`ABA-CONFIGURACOES/`) desce
        para a gaveta DELA, e `mesa_de_medicao._o_dono_do_gesto`, que procura
        em `<pasta do citado>/arquivados/`, continua achando.
        """
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


# ---------------------------------------------------------------------------
# A TRAVA — quem ainda alcança o arquivo pelo caminho
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Citacao:
    citador: str
    linha: int
    classe: str          # "caminho" (trava) | "nome" (avisa)
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
    """Para cada nome de arquivo, quem o alcança e de que forma.

    Uma passada só pela árvore, por mais candidatas que haja: a alternância dos
    nomes vira UMA expressão, e o pré-filtro literal descarta de saída o
    arquivo que não menciona nenhum deles.
    """
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
    """`caminho` trava; `nome` avisa; ``None`` não é citação.

    O que separa as duas é uma pergunta só: *depois da mudança, este texto
    ainda alcança o arquivo?* Pasta escrita antes do nome não alcança mais.
    Nome solto alcança, porque a conferência da casa é por sufixo.
    """
    antes = linha[:inicio]
    depois = linha[fim:]

    # Continuação de nome (`X.md.bak`, `X.mdx`) não é citação do arquivo.
    if depois[:1] and (depois[0].isalnum() or depois[0] in "_-"):
        return None

    pasta = _ANTES_DE_PASTA.search(antes)
    if pasta:
        # Já aponta para a gaveta: é o destino, não o passado.
        if pasta.group(1).rstrip("/").endswith(ARQUIVADOS):
            return None
        return "caminho"

    # Alvo de link markdown sem pasta: posicional, quebra na mudança.
    if antes.endswith("]("):
        return "caminho"
    return "nome"


# ---------------------------------------------------------------------------
# A mudança
# ---------------------------------------------------------------------------

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
    """`docs/process/` é `.gitignore`, mas o script não confia nisso.

    Numa bancada de teste não há repositório nenhum, e numa árvore onde a pasta
    passe a viajar o `git mv` é o certo. Perguntar custa um processo por
    arquivo movido, e movem-se poucos.
    """
    try:
        pronto = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--",
             str(arquivo.relative_to(raiz))],
            cwd=raiz, capture_output=True)
    except (OSError, ValueError):
        return False
    return pronto.returncode == 0


# ---------------------------------------------------------------------------
# EIXO 4 — `tests/`, medido nas duas leituras e movido em nenhuma
# ---------------------------------------------------------------------------

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
    """Um teste e o que ele mede que não está mais lá.

    As duas listas ficam separadas porque valem coisas diferentes, e somá-las
    esconderia o mais fraco dentro do mais forte:

    ``simbolos``  o endereço de um símbolo do pacote que não resolve. É o
                  achado forte — o alvo mudou de lugar ou de nome, e a régua
                  ficou medindo o mundo de ontem.
    ``caminhos``  um caminho da árvore que não existe. É o achado FRACO: boa
                  parte dos testes desta casa nomeia arquivo inexistente DE
                  PROPÓSITO, para provar que a régua recusa o que não está lá.
                  Sai no relatório como triagem, nunca como veredito.
    """

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
    """Todo nome que o módulo publica, inclusive o que nasce sob guarda.

    PRIMEIRA MEDIÇÃO, ARRANCADA E REFEITA: só os filhos diretos de `Module`
    acusavam 65 testes, e a amostra era falsa — `ExternalCard` nasce dentro de
    `if _GTK_DISPONIVEL:`, `StickPreviewGtk` idem. Toda a camada de tela desta
    casa se define sob guarda de importação, e uma régua que não entra nos
    abrigos mede um módulo que não existe. Por isso a descida entra em `if`,
    `try` e `with`, e para nos corpos de função e classe — ali o nome é local,
    e contá-lo abriria o buraco do outro lado.
    """
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
                    # `MOUSE_SPEED_MIN, MOUSE_SPEED_MAX = 1, 12` publica DOIS
                    # nomes, e ler só `ast.Name` acusava os dois como mortos.
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
    """Resolve `a.b.c` contra o disco. Devolve o motivo, ou ``None``.

    É o que pega a família que esta casa mais caçou: a régua que digita o
    endereço de um símbolo que mudou de lugar. Conservador de propósito — só
    responde sobre o pacote da casa, e só quando o módulo pai existe.
    """
    partes = alvo.split(".")
    if not partes or partes[0] != _PACOTE or len(partes) < 2:
        return None
    # `core.rumble:_effective_mult` é citação `arquivo:símbolo`, que tem dono
    # próprio (`scripts/validar-citacoes-de-linha.py`). Aqui ela só produziria
    # um falso positivo com cara de achado.
    if not all(p.isidentifier() for p in partes):
        return None
    # O corte desce até 1 porque `hefesto_dualsense4unix.__version__` é
    # atributo do PACOTE, e parar em 2 o acusava de módulo inexistente.
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
    # A gaveta salva a citação de sprint, igual à leniência da mesa de medição.
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


# ---------------------------------------------------------------------------
# A SEPARAÇÃO — um dono só, porque dois chamadores a fazem
# ---------------------------------------------------------------------------

def separa_presas_e_livres(
    fechadas: list[Sprint], citacoes: dict[str, list[Citacao]],
) -> tuple[list[Sprint], list[Sprint]]:
    """(as que a citação por caminho segura, as que podem descer agora).

    Ela vive fora dos dois chamadores de propósito. `--seco` e `--exigir`
    precisam da MESMA fronteira, e duas cópias dela é a forma de defeito que
    esta casa nomeia desde o `validar-caducos.py`: duas listas para a mesma
    coisa divergem, e a que reprova diverge calada.
    """
    presas: list[Sprint] = []
    livres: list[Sprint] = []
    for sprint in fechadas:
        travam = [c for c in citacoes[sprint.arquivo.name] if c.classe == "caminho"]
        (presas if travam else livres).append(sprint)
    return presas, livres


# ---------------------------------------------------------------------------
# A fala
# ---------------------------------------------------------------------------

def _relata(raiz: Path, mover_de_verdade: bool) -> int:
    pasta = raiz / SUBPASTA_DAS_SPRINTS
    if not pasta.is_dir():
        # SEM A PASTA NÃO É DEFEITO: `docs/process/` é `.gitignore`, e um clone
        # limpo não a tem. É o que mantém a esteira de pé onde o `release.yml`
        # já caiu uma vez. O que É defeito — a pasta no disco e o alvo fora
        # dela — grita em `mover()`.
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


# ---------------------------------------------------------------------------
# `--exigir` — a forma de PORTÃO, e ela só reprova o que tem conserto
# ---------------------------------------------------------------------------

def _exige(raiz: Path) -> int:
    """rc=1 só quando há sprint fechada que PODE descer agora.

    OS DOIS DEFEITOS QUE ESTA FUNÇÃO SUBSTITUI, medidos em 20/09/2026 na
    árvore viva, contra a versão que ela troca:

    1. **Verde sobre nada.** Sem `docs/process/` no disco — e um clone limpo
       nunca a tem, porque ela é `.gitignore:178` — a versão anterior imprimia
       *"OK: nenhuma sprint fechada na pasta viva"* e devolvia 0. Afirmava
       sobre 46 sprints que não tinha lido. *Ausência de pasta é ausência de
       medição*, e um portão que confunde as duas é a família que esta casa
       mais caçou em 2026: o instrumento respondendo sobre outra coisa.

    2. **Vermelho eterno sobre quem está certo.** Ela reprovava as 21 fechadas
       da pasta viva; **13 delas estão presas por citação de caminho**, e a
       trava as segura DE PROPÓSITO — soltá-las quebraria o `SPRINT_ORDER.md`
       e o comentário de `luz_do_mic.py`. Um portão que reprova o estado certo
       não tem conserto, e portão sem conserto é portão que se desliga.

    O que sobra é o que tem dono: as LIVRES. Quem vê este vermelho roda
    `--mover` e ele apaga. As presas saem nomeadas e não reprovam — o reaponte
    delas é ato humano, e `referencias-docs` já diz o endereço.
    """
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
