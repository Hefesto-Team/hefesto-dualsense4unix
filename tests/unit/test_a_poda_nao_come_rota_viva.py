"""A régua da PODA — ``PODA-NAO-COME-ROTA-VIVA-01`` (26/08/2026)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"

_PODADOS: tuple[str, ...] = (
    "utils/session.py::save_mouse_emulation_enabled",
    "utils/session.py::load_mouse_emulation_enabled",
    "utils/session.py::load_keyboard_emulation_enabled",
    "utils/session.py::load_coop_enabled",
    "integrations/kernel_cmdline.py::ownership_record",
    "tui/app.py::main_async",
)

_ROTEIROS_DE_PRODUCAO = ("install.sh", "uninstall.sh")

_HEREDOC_PYTHON = re.compile(
    r"""\bpython3?\b[^\n<]*<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*$"""
)

_ARQUIVO_DESTA_REGUA = Path(__file__).resolve()


def _fontes_python() -> list[tuple[Path, str, bool]]:
    """``(caminho, código, e_producao)`` de tudo que pode conter chamador."""
    fontes: list[tuple[Path, str, bool]] = []
    for pasta, e_producao in (("src", True), ("scripts", True), ("tests", False)):
        raiz = _RAIZ / pasta
        if not raiz.is_dir():
            continue
        for arquivo in sorted(raiz.rglob("*.py")):
            if arquivo.resolve() == _ARQUIVO_DESTA_REGUA:
                continue
            try:
                fontes.append((arquivo, arquivo.read_text(encoding="utf-8"), e_producao))
            except OSError:  # pragma: no cover - disco quebrado
                continue
    for nome in _ROTEIROS_DE_PRODUCAO:
        roteiro = _RAIZ / nome
        if not roteiro.is_file():
            continue
        for trecho in _heredocs_python(roteiro.read_text(encoding="utf-8")):
            fontes.append((roteiro, trecho, True))
    return fontes


def _heredocs_python(roteiro: str) -> list[str]:
    """Os blocos Python embutidos no shell, um por heredoc."""
    linhas = roteiro.splitlines()
    blocos: list[str] = []
    i = 0
    while i < len(linhas):
        casou = _HEREDOC_PYTHON.search(linhas[i])
        if not casou:
            i += 1
            continue
        fim = casou.group(2)
        corpo: list[str] = []
        i += 1
        while i < len(linhas) and linhas[i].strip() != fim:
            corpo.append(linhas[i])
            i += 1
        i += 1
        blocos.append("\n".join(corpo))
    return blocos


def _citacoes(codigo: str, nome: str, *, com_literais: bool) -> list[int]:
    """Linhas em que ``nome`` é USADO — chamada, referência ou despacho."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError:
        return []
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name) and no.id == nome:
            if isinstance(no.ctx, ast.Load):
                linhas.append(no.lineno)
        elif isinstance(no, ast.Attribute) and no.attr == nome:
            linhas.append(no.lineno)
        elif isinstance(no, ast.alias) and (no.name == nome or no.asname == nome):
            linhas.append(getattr(no, "lineno", 0))
        elif (
            com_literais
            and isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and nome in re.split(r"[^A-Za-z0-9_]+", no.value)
        ):
            linhas.append(no.lineno)
    return sorted(set(linhas))


@pytest.mark.parametrize("alvo", _PODADOS, ids=lambda a: a.replace("/", "."))
def test_todo_simbolo_podado_tinha_zero_chamadores(alvo: str) -> None:
    """Nenhum dos podados era rota viva — e a prova é a varredura, não a palavra."""
    modulo, _, nome = alvo.partition("::")
    achados: list[str] = []
    for caminho, codigo, e_producao in _fontes_python():
        for linha in _citacoes(codigo, nome, com_literais=e_producao):
            rel = caminho.relative_to(_RAIZ)
            achados.append(f"{rel}:{linha}")
    assert not achados, (
        f"a poda de `{modulo}::{nome}` comeu rota viva — ela TEM chamador em: "
        + ", ".join(achados)
        + ". Devolva o símbolo (a lápide dele, no lugar onde morava, diz o que "
        "ele fazia) ou tire o chamador antes de podar."
    )


@pytest.mark.parametrize("alvo", _PODADOS, ids=lambda a: a.replace("/", "."))
def test_todo_simbolo_podado_sumiu_de_verdade(alvo: str) -> None:
    """Poda pela metade é pior que poda nenhuma: o nome some, o corpo fica."""
    modulo, _, nome = alvo.partition("::")
    arquivo = _SRC / modulo
    assert arquivo.is_file(), f"{modulo} não existe — a lápide de `{nome}` mudou de casa"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    definidos = {
        no.name
        for no in arvore.body
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert nome not in definidos, (
        f"`{nome}` continua definido em {modulo}: a poda ficou pela metade. "
        "Ou apague o corpo, ou tire a entrada de `_PODADOS` e devolva a "
        "classificação dele ao portão de lápides."
    )


def test_a_lista_de_podados_nao_e_vazia() -> None:
    """Régua que mede lista vazia passa sempre — e não é régua."""
    assert _PODADOS, "sem podados declarados, este arquivo não trava nada"


def test_a_varredura_enxerga_o_python_dentro_do_heredoc() -> None:
    """A régua tem de saber ACHAR chamador, senão o verde dela não vale nada."""
    achados = [
        f"{caminho.name}:{linha}"
        for caminho, codigo, e_producao in _fontes_python()
        if caminho.name in _ROTEIROS_DE_PRODUCAO
        for linha in _citacoes(codigo, "plan_tokens", com_literais=e_producao)
    ]
    assert achados, (
        "a varredura não achou `plan_tokens` em heredoc nenhum — e o install.sh "
        "o chama. Régua cega ao heredoc dá verde para poda que come produção."
    )
