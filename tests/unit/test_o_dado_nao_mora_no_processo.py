"""DADO e PROCESSO são coisas diferentes — a régua da decisão de 20/09/2026.

A ORDEM DELA, escolhida entre três opções: *"Mover o que as réguas precisam"*.
Ela recusou versionar `docs/process/` inteira (1.607 arquivos, 77 MB de prosa)
e recusou fazer as réguas pularem sem a pasta (*régua que pula é régua que não
mede*).

O QUE ISSO DEIXA DE CONTRATO, e é o que este arquivo cobra:

1. o que uma régua LÊ mora em `docs/method/` e **viaja no git**;
2. `docs/method/LEIA-PRIMEIRO.md` diz de cada um de onde veio e quem o lê;
3. **nada em `src/`, `scripts/` ou `tests/` volta a ler a árvore real
   `docs/process/`** — salvo as ferramentas de PROCESSO, declaradas aqui com
   a razão de cada uma.

O PREÇO QUE PAGOU POR ESTA RÉGUA, e ele é de 20/09/2026: os dois donos do
gesto das 199 células da mesa de medição foram arquivados junto com 732
sprints fechadas. `_gesto_do_arquivo` digitava o caminho, não achava e
devolvia `{}` — **calado**. As 199 células caíram no fallback da procedência
(canal, report, offset), que é literalmente o defeito que ela apontou em 07/09
olhando a linha 10: *"sinceramente não entendi o que diabos é pra fazer
aqui"*. Voltou inteiro seis dias depois, e sete réguas ficaram vermelhas sem
que nenhuma soubesse dizer por quê.

A REGRA 3 É A QUE MORDE DE VERDADE. As duas primeiras conferem o estado de
hoje; a terceira impede o estado de amanhã — o dia em que alguém escrever
`RAIZ / "docs" / "process" / "algo.md"` num teste novo e recriar o defeito
inteiro, com a árvore dela verde, porque na árvore dela o arquivo está lá.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PASTA = RAIZ / "docs" / "method"
INDICE = PASTA / "LEIA-PRIMEIRO.md"

#: A PASTA QUE NÃO VIAJA. `docs/process/` é `.gitignore:178` por ordem dela de
#: 15/09/2026 — *"não quero que as pessoas tenham acesso a isso"*.
PROCESSO = "docs/process"

#: AS FERRAMENTAS DE PROCESSO, que leem `docs/process/` porque o PROCESSO é o
#: assunto delas. Cada uma sabe viver sem a pasta: nenhuma é portão do CI.
#: Quem entrar nesta lista entra com a razão escrita, e a razão é conferida
#: pela régua (linha vazia reprova).
LEITORES_DE_PROCESSO: dict[str, str] = {
    "scripts/gerar-painel.py":
        "o painel das sprints — ele É a leitura da pasta de processo, e sai "
        "vazio sem ela",
    "scripts/mover-sprints-fechadas.py":
        "o movedor de sprints fechadas: o que ele move são as sprints, que "
        "são processo",
    "tests/unit/test_portao_a_colisao_de_sprints_morde.py":
        "a régua da colisão entre sprints abertas; ela mede posse de arquivo "
        "ENTRE SPRINTS, e sprint é processo. Os dois alvos dela são "
        "ignorados, e ela já se desliga com a razão escrita quando faltam",
    "scripts/check_colisao_de_sprints.py":
        "o portão da colisão de posse ENTRE SPRINTS — o que ele cruza são as "
        "sprints, que são processo. Sem a pasta ele não tem o que cruzar",
    "scripts/apontar-o-dado-que-saiu-do-processo.py":
        "o ponteiro que fica no lugar antigo; ele existe justamente porque a "
        "pasta não viaja",
    "tests/unit/test_o_dado_nao_mora_no_processo.py":
        "esta régua, que nomeia a pasta para proibi-la",
}

#: OS NOMES DE RAIZ. Uma expressão só é leitura da ÁRVORE REAL quando a
#: corrente começa num destes; `tmp_path / "docs" / "process"` é árvore de
#: brinquedo, e árvore de brinquedo é o jeito certo de testar um varredor.
RAIZES_REAIS = frozenset({
    "RAIZ", "RAIZ_REAL", "REPO_ROOT", "RAIZ_DO_REPO", "ROOT", "RAIZ_REPO",
})

PASTAS_VARRIDAS = ("src", "scripts", "tests")


def _modulos() -> list[pathlib.Path]:
    fora: list[pathlib.Path] = []
    for pasta in PASTAS_VARRIDAS:
        fora.extend(sorted((RAIZ / pasta).rglob("*.py")))
    return fora


def _rastreado(relativo: str) -> bool:
    saida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "--error-unmatch", relativo],
        capture_output=True, text=True, check=False)
    return saida.returncode == 0


# ---------------------------------------------------------------------------
# 1 · O QUE A RÉGUA LÊ VIAJA NO GIT
# ---------------------------------------------------------------------------
def test_a_pasta_do_metodo_existe_e_e_rastreada() -> None:
    """Cada arquivo de `docs/method/` é rastreado — o oráculo é o git."""
    assert PASTA.is_dir(), (
        "`docs/method/` sumiu — é a pasta do que as réguas leem, e sem ela "
        "28 testes voltam a reprovar em todo clone limpo")
    arquivos = sorted(p for p in PASTA.iterdir() if p.is_file())
    assert len(arquivos) >= 8, (
        f"`docs/method/` tem {len(arquivos)} arquivo(s); eram os sete "
        "medidos mais o índice")
    for arquivo in arquivos:
        relativo = arquivo.relative_to(RAIZ).as_posix()
        assert _rastreado(relativo), (
            f"`{relativo}` está na pasta do dado e NÃO é rastreado pelo git. "
            "Ou ele entra no commit, ou ele some no próximo clone — e sumir "
            "calado é o defeito inteiro que esta pasta existe para matar.")


# ---------------------------------------------------------------------------
# 2 · O ÍNDICE DIZ DE ONDE VEIO E QUEM LÊ
# ---------------------------------------------------------------------------
def test_o_indice_nomeia_cada_arquivo_da_pasta() -> None:
    """Arquivo novo na pasta sem linha no índice reprova.

    Sem isto, a pasta vira depósito: daqui a um mês ninguém sabe se um
    arquivo ali ainda é lido por alguma coisa, e o critério de entrada — *ser
    LIDO* — deixa de ser conferível.
    """
    assert INDICE.is_file(), f"o índice sumiu: {INDICE.relative_to(RAIZ)}"
    texto = INDICE.read_text(encoding="utf-8")
    sem_linha = [
        p.name for p in sorted(PASTA.iterdir())
        if p.is_file() and p != INDICE and p.name not in texto
    ]
    assert not sem_linha, (
        f"{len(sem_linha)} arquivo(s) em `docs/method/` sem linha no "
        f"`LEIA-PRIMEIRO.md`: {sem_linha}. A pasta é do que as réguas LEEM; "
        "quem entra diz quem o lê.")


def test_o_indice_registra_o_endereco_velho() -> None:
    """De onde cada um veio — senão a próxima pessoa procura onde ele estava."""
    texto = INDICE.read_text(encoding="utf-8")
    assert texto.count(PROCESSO) >= 7, (
        "o índice parou de dizer de onde os arquivos vieram; sem o endereço "
        "velho, quem procurar pelo caminho de ontem não acha o de hoje")


# ---------------------------------------------------------------------------
# 3 · NINGUÉM VOLTA A LER A ÁRVORE REAL `docs/process/`
# ---------------------------------------------------------------------------
def _raiz_da_corrente(no: ast.AST) -> str | None:
    """O nome que está na ponta esquerda de `A / "b" / "c"`, se houver um."""
    while isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
        no = no.left
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return no.attr
    return None


def _le_o_processo_real(arvore: ast.AST) -> list[int]:
    """As linhas em que o módulo monta um caminho para a `docs/process` REAL.

    Duas formas, e só elas, porque só elas leem a árvore de verdade:

    * `RAIZ / "docs" / "process" / …` — a corrente de `pathlib` ancorada num
      nome de raiz;
    * a string `"docs/process/…"` passada a `Path(...)`/`open(...)`, ou
      dividida por `/` a partir de uma raiz.

    O que NÃO conta, de propósito: prosa, docstring, comentário, e
    `tmp_path / "docs" / "process"`. Uma régua que confundisse a árvore de
    brinquedo com a real proibiria justamente o jeito CERTO de testar um
    varredor de sprints — e régua que proíbe o certo é desligada na semana
    seguinte.
    """
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
            direita = no.right
            if (isinstance(direita, ast.Constant)
                    and isinstance(direita.value, str)
                    and direita.value.strip("/") in {"process", PROCESSO}
                    and _raiz_da_corrente(no.left) in RAIZES_REAIS):
                linhas.append(no.lineno)
            if (isinstance(direita, ast.Constant)
                    and isinstance(direita.value, str)
                    and PROCESSO in direita.value
                    and _raiz_da_corrente(no.left) in RAIZES_REAIS):
                linhas.append(no.lineno)
        if isinstance(no, ast.Call):
            chamado = no.func
            nome = (chamado.attr if isinstance(chamado, ast.Attribute)
                    else getattr(chamado, "id", ""))
            if nome not in {"Path", "open", "read_text", "glob", "rglob"}:
                continue
            for argumento in no.args:
                if (isinstance(argumento, ast.Constant)
                        and isinstance(argumento.value, str)
                        and argumento.value.lstrip("./").startswith(PROCESSO)):
                    linhas.append(no.lineno)
    return sorted(set(linhas))


def test_nenhum_modulo_le_a_arvore_real_do_processo() -> None:
    """O portão de amanhã: dado novo não nasce numa pasta que não viaja."""
    culpados: list[str] = []
    for modulo in _modulos():
        relativo = modulo.relative_to(RAIZ).as_posix()
        if relativo in LEITORES_DE_PROCESSO:
            continue
        try:
            arvore = ast.parse(modulo.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        for linha in _le_o_processo_real(arvore):
            culpados.append(f"{relativo}:{linha}")
    assert not culpados, (
        f"{len(culpados)} leitura(s) da árvore real `{PROCESSO}/`:\n  "
        + "\n  ".join(culpados)
        + "\n\nEssa pasta é `.gitignore:178` — ela não viaja no clone nem na "
        "worktree de agente. O que uma régua lê mora em `docs/method/`. Se o "
        "que você está lendo é PROCESSO mesmo (sprint, painel, colisão), "
        "declare o módulo em `LEITORES_DE_PROCESSO` com a razão.")


def test_toda_isencao_traz_a_razao_e_o_arquivo_existe() -> None:
    """Isenção sem razão apodrece; isenção de arquivo morto engana."""
    for relativo, razao in LEITORES_DE_PROCESSO.items():
        assert (RAIZ / relativo).is_file(), (
            f"`{relativo}` está isento de ler `{PROCESSO}/` e não existe "
            "mais — a isenção virou letra morta e esconde o próximo caso")
        assert len(razao.strip()) >= 30, (
            f"a isenção de `{relativo}` não diz por quê: {razao!r}")


# ---------------------------------------------------------------------------
# A MORDIDA DA REGRA 3 — a régua tem de ACUSAR o caso que ela existe para pegar
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fonte", [
    'ALVO = RAIZ / "docs" / "process" / "UM-GESTO.md"',
    'ALVO = REPO_ROOT / "docs/process/sprints/UM-GESTO.md"',
    'texto = Path("docs/process/UM-GESTO.md").read_text()',
    'texto = open("./docs/process/UM-GESTO.md").read()',
])
def test_a_regua_acusa_a_leitura_da_arvore_real(fonte: str) -> None:
    """As quatro formas com que o defeito volta."""
    assert _le_o_processo_real(ast.parse(fonte)), (
        f"a régua ficou cega para: {fonte}")


@pytest.mark.parametrize("fonte", [
    'alvo = tmp_path / "docs" / "process" / "UMA-SPRINT.md"',
    'raiz = repo_falso / "docs" / "process"',
    '"o gesto morava em docs/process/sprints/ e saiu em 20/09"',
])
def test_a_regua_deixa_passar_a_arvore_de_brinquedo(fonte: str) -> None:
    """E o que ela NÃO pode acusar, que é metade de uma régua boa."""
    assert not _le_o_processo_real(ast.parse(fonte)), (
        f"a régua acusou o que é legítimo: {fonte}")
