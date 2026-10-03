"""DADO e PROCESSO são coisas diferentes — a régua da decisão de 20/09/2026."""

from __future__ import annotations

import ast
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PASTA = RAIZ / "docs" / "method"
INDICE = PASTA / "LEIA-PRIMEIRO.md"

PROCESSO = "docs/process"

LEITORES_DE_PROCESSO: dict[str, str] = {
    "scripts/check_colisao_de_sprints.py":
        "o portão da colisão de posse ENTRE SPRINTS — o que ele cruza são as "
        "sprints, que são processo. Sem a pasta ele não tem o que cruzar",
    "tests/unit/test_o_dado_nao_mora_no_processo.py":
        "esta régua, que nomeia a pasta para proibi-la",
    "tests/unit/test_o_basico_o_contrato.py":
        "a régua 7 do básico, que nomeia a pasta para proibi-la: afirma que "
        "nenhum caminho do protocolo mora ali, e nunca lê o que há dentro",
    "tests/unit/test_toda_excecao_tem_sprint_que_a_tira.py":
        "a régua das listas de exceção: ela pergunta a cada sprint citada se "
        "ainda está aberta, e o estado de uma sprint é processo",
}

RAIZES_REAIS = frozenset({
    "RAIZ", "RAIZ_REAL", "REPO_ROOT", "RAIZ_DO_REPO", "ROOT", "RAIZ_REPO",
})

PASTAS_VARRIDAS = ("src", "scripts", "tests")


def _modulos() -> list[pathlib.Path]:
    """Os `.py` de `src/`, `scripts/` e `tests/` que VIAJAM no git."""
    nao_viajam = _ignorados_pelo_git()
    fora: list[pathlib.Path] = []
    for pasta in PASTAS_VARRIDAS:
        fora.extend(m for m in sorted((RAIZ / pasta).rglob("*.py")) if m not in nao_viajam)
    return fora


def _ignorados_pelo_git() -> set[pathlib.Path]:
    """Os arquivos das pastas varridas que o git ignora nesta árvore."""
    saida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "--others", "--ignored",
         "--exclude-standard", "-z", "--", *PASTAS_VARRIDAS],
        capture_output=True, text=True, check=False)
    if saida.returncode != 0:
        return set()
    return {RAIZ / relativo for relativo in saida.stdout.split("\0") if relativo}


def _rastreado(relativo: str) -> bool:
    saida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "--error-unmatch", relativo],
        capture_output=True, text=True, check=False)
    return saida.returncode == 0


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


def test_o_indice_nomeia_cada_arquivo_da_pasta() -> None:
    """Arquivo novo na pasta sem linha no índice reprova."""
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
    """As linhas em que o módulo monta um caminho para a `docs/process` REAL."""
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


def test_toda_isencao_traz_a_razao() -> None:
    """Isenção sem razão apodrece — e a razão viaja no git, então se cobra em toda árvore."""
    for relativo, razao in LEITORES_DE_PROCESSO.items():
        assert len(razao.strip()) >= 30, (
            f"a isenção de `{relativo}` não diz por quê: {razao!r}")


@pytest.mark.parametrize("relativo", [
    pytest.param(relativo, id=relativo, marks=pytest.mark.insumo_fora_do_git(relativo))
    for relativo in LEITORES_DE_PROCESSO
])
def test_todo_arquivo_isento_existe(relativo: str) -> None:
    """Isenção de arquivo morto engana."""
    assert (RAIZ / relativo).is_file(), (
        f"`{relativo}` está isento de ler `{PROCESSO}/` e não existe "
        "mais — a isenção virou letra morta e esconde o próximo caso")


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
