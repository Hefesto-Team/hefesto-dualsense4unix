"""Os testes do que saiu do produto saem junto.

OS-TESTES-DO-QUE-SAIU-DO-PRODUTO-SAEM-JUNTO-01 (04/11/2026). Medido no dia: os pulos da suíte por
alvo que saiu eram todos ramos que liam a página publicada da 02 (fora do produto desde f0fab2db6)
ou um arquivo de teste da janela GTK; cada um era um verde que não provava nada.

A régua lê cada arquivo de ``tests/unit/`` e acha o pulo guardado pela ausência de um caminho
(``if not X.exists(): pytest.skip(...)`` e ``skipif(not X.exists())``). Quando o caminho resolve
para dentro do repositório e não existe, o alvo saiu: o teste sai junto, ou passa a ler o que
ficou. Caminho de fora do repositório (o Chrome, o ``/usr``, o aparelho) é ambiente e fica.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde

RAIZ = pathlib.Path(__file__).resolve().parents[2]
METODOS_DE_PRESENCA = frozenset({"exists", "is_file", "is_dir"})
NAO_RESOLVE = object()


def _alvo_da_ausencia(no: ast.AST) -> ast.expr | None:
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
        dentro = no.operand
        if (isinstance(dentro, ast.Call) and isinstance(dentro.func, ast.Attribute)
                and dentro.func.attr in METODOS_DE_PRESENCA):
            return dentro.func.value
    if isinstance(no, ast.BoolOp):
        for valor in no.values:
            alvo = _alvo_da_ausencia(valor)
            if alvo is not None:
                return alvo
    return None


def _pula(no: ast.AST) -> bool:
    return (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
            and no.func.attr in ("skip", "skipif"))


class _Avaliador:
    def __init__(self, arquivo: pathlib.Path, nomes: dict[str, ast.expr],
                 funcoes: dict[str, ast.expr] | None = None) -> None:
        self.nomes = nomes
        self.funcoes = funcoes or {}
        self.valores: dict[str, Any] = {"__file__": str(arquivo), "onde": onde,
                                        "Path": pathlib.Path, "pathlib": pathlib}

    def nome(self, nome: str) -> Any:
        if nome not in self.valores:
            self.valores[nome] = NAO_RESOLVE
            if nome in self.nomes:
                self.valores[nome] = self.valor(self.nomes[nome])
        return self.valores[nome]

    def valor(self, no: ast.expr) -> Any:
        if isinstance(no, ast.Constant) and isinstance(no.value, (str, int)):
            return no.value
        if isinstance(no, ast.Name):
            return self.nome(no.id)
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
            esquerda, direita = self.valor(no.left), self.valor(no.right)
            if isinstance(esquerda, pathlib.Path) and isinstance(direita, (str, pathlib.Path)):
                return esquerda / direita
            return NAO_RESOLVE
        if isinstance(no, ast.Attribute):
            dono = self.valor(no.value)
            if dono is onde and (no.attr in ("RAIZ", "ENSAIO", "PUBLICADO")
                                 or getattr(onde, no.attr, None) is onde.pagina):
                return getattr(onde, no.attr)
            if dono is pathlib and no.attr == "Path":
                return pathlib.Path
            if isinstance(dono, pathlib.Path) and no.attr in ("parent", "parents", "resolve"):
                return getattr(dono, no.attr)
            return NAO_RESOLVE
        if isinstance(no, ast.List):
            return [self.valor(e) for e in no.elts]
        if isinstance(no, ast.Subscript):
            dono = self.valor(no.value)
            indices = ([no.slice.body, no.slice.orelse] if isinstance(no.slice, ast.IfExp)
                       else [no.slice])
            escolhas = [dono[i] for i in map(self.valor, indices) if isinstance(i, int) and (
                isinstance(dono, list) or type(dono).__name__.endswith("Parents"))]
            ausentes = [e for e in escolhas if isinstance(e, pathlib.Path) and not e.exists()]
            return (ausentes or escolhas or [NAO_RESOLVE])[0]
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in self.funcoes and not no.args):
            return self.valor(self.funcoes[no.func.id])
        if isinstance(no, ast.Call):
            funcao = self.valor(no.func)
            argumentos = [self.valor(a) for a in no.args]
            nomeados = {k.arg: self.valor(k.value) for k in no.keywords if k.arg}
            if NAO_RESOLVE in argumentos or NAO_RESOLVE in nomeados.values():
                return NAO_RESOLVE
            if funcao is pathlib.Path or funcao is onde.pagina:
                return funcao(*argumentos, **nomeados)
            if callable(funcao) and getattr(funcao, "__name__", "") == "resolve":
                return funcao()
        return NAO_RESOLVE


def _atribuicoes(corpo: list[ast.stmt]) -> dict[str, ast.expr]:
    fora: dict[str, ast.expr] = {}
    for no in corpo:
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(
                no.targets[0], ast.Name):
            fora[no.targets[0].id] = no.value
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name) and no.value:
            fora[no.target.id] = no.value
    return fora


def _funcoes_de_um_retorno(corpo: list[ast.stmt]) -> dict[str, ast.expr]:
    fora: dict[str, ast.expr] = {}
    for no in corpo:
        if isinstance(no, ast.FunctionDef) and not no.args.args:
            miolo = [s for s in no.body if not (isinstance(s, ast.Expr)
                                                and isinstance(s.value, ast.Constant))]
            if len(miolo) == 1 and isinstance(miolo[0], ast.Return) and miolo[0].value:
                fora[no.name] = miolo[0].value
    return fora


def pulos_por_alvo_que_saiu(arquivo: pathlib.Path, fonte: str,
                            raiz: pathlib.Path = RAIZ) -> list[str]:
    """Os pulos de ``fonte`` guardados por um caminho do repositório que não existe."""
    if "skip" not in fonte or not any(f".{m}()" in fonte for m in METODOS_DE_PRESENCA):
        return []
    arvore = ast.parse(fonte)
    do_modulo = _atribuicoes(arvore.body)
    funcoes = _funcoes_de_um_retorno(arvore.body)
    dono: dict[int, ast.AST] = {}
    for pai in ast.walk(arvore):
        for filho in ast.iter_child_nodes(pai):
            dono[id(filho)] = pai
    avaliadores: dict[int, _Avaliador] = {}
    achados: list[str] = []
    for no in ast.walk(arvore):
        alvo = None
        if isinstance(no, ast.If) and any(_pula(x) for s in no.body for x in ast.walk(s)):
            alvo = _alvo_da_ausencia(no.test)
        elif _pula(no) and getattr(no.func, "attr", "") == "skipif" and no.args:
            alvo = _alvo_da_ausencia(no.args[0])
        if alvo is None:
            continue
        funcao: ast.AST | None = dono.get(id(no))
        while funcao is not None and not isinstance(funcao, (ast.FunctionDef,
                                                              ast.AsyncFunctionDef)):
            funcao = dono.get(id(funcao))
        if id(funcao) not in avaliadores:
            nomes = {**do_modulo, **_atribuicoes(getattr(funcao, "body", []))}
            avaliadores[id(funcao)] = _Avaliador(arquivo, nomes, funcoes)
        caminho = avaliadores[id(funcao)].valor(alvo)
        if not isinstance(caminho, pathlib.Path):
            continue
        caminho = caminho.resolve()
        if not caminho.is_relative_to(raiz) or caminho.exists():
            continue
        relativo = caminho.relative_to(raiz)
        if any(parte.startswith(".") for parte in relativo.parts):
            continue
        achados.append(f"{arquivo.name}:{no.lineno}: {relativo}")
    return achados


def test_nenhum_teste_pula_por_um_alvo_que_saiu_do_produto() -> None:
    achados = [a for arquivo in sorted((RAIZ / "tests" / "unit").glob("test_*.py"))
               for a in pulos_por_alvo_que_saiu(arquivo, arquivo.read_text(encoding="utf-8"))]
    assert not achados, (
        "teste que pula porque o alvo saiu do produto: o teste sai junto, ou passa a medir o "
        "que ficou\n  " + "\n  ".join(achados))


ARQUIVO_DE_PROVA = RAIZ / "tests" / "unit" / "test_de_prova.py"


@pytest.mark.parametrize(("fonte", "acha"), [
    ('import pathlib\nimport pytest\nRAIZ = pathlib.Path(__file__).resolve().parents[2]\n'
     'PAGINA = RAIZ / "src/sumiu.html"\n'
     'def test_x():\n    if not PAGINA.exists():\n        pytest.skip("saiu")\n', True),
    ('import pytest\nfrom hefesto_dualsense4unix.interface import onde\n'
     'def test_x():\n    caminho = onde.pagina("99-sumiu.html", publicado=True)\n'
     '    if not caminho.exists():\n        pytest.skip("saiu")\n', True),
    ('import pathlib\nimport pytest\nRAIZ = pathlib.Path(__file__).resolve().parents[2]\n'
     '@pytest.mark.skipif(not (RAIZ / "scripts/sumiu.sh").exists(), reason="x")\n'
     'def test_x():\n    pass\n', True),
    ('import pathlib\nimport pytest\nRAIZ = pathlib.Path(__file__).resolve().parents[2]\n'
     'PAGINA = RAIZ / "pyproject.toml"\n'
     'def test_x():\n    if not PAGINA.exists():\n        pytest.skip("fica")\n', False),
    ('import pathlib\nimport pytest\nCHROME = pathlib.Path("/opt/sem/chrome")\n'
     '@pytest.mark.skipif(not CHROME.exists(), reason="ambiente")\n'
     'def test_x():\n    pass\n', False),
    ('import pathlib\nimport pytest\nRAIZ = pathlib.Path(__file__).resolve().parents[2]\n'
     'def test_x():\n    if not (RAIZ / ".venv/bin/python").exists():\n'
     '        pytest.skip("sem venv")\n', False),
    ('import pytest\nfrom hefesto_dualsense4unix.interface import onde\n'
     'def _paginas():\n    return [onde.pagina("01-jogar.html"),'
     ' onde.pagina("99-sumiu.html", publicado=True)]\n'
     '@pytest.fixture(params=["desenho", "publicado"])\ndef pagina(request):\n'
     '    caminho = _paginas()[0 if request.param == "desenho" else 1]\n'
     '    if not caminho.exists():\n        pytest.skip("saiu")\n', True),
], ids=["nome-do-modulo", "pagina-publicada", "skipif", "alvo-que-ficou", "ambiente",
        "a-venv-da-arvore", "o-ramo-publicado"])
def test_a_regua_acha_o_alvo_que_saiu_e_deixa_o_ambiente(fonte: str, acha: bool) -> None:
    assert bool(pulos_por_alvo_que_saiu(ARQUIVO_DE_PROVA, fonte)) is acha
