"""A lista do WebKit da suíte tem teto, e a lógica não importa a moldura (23/10/2026).

A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01. O `scripts/rodar-a-suite.sh` manda para
processo próprio todo arquivo de teste que carrega o WebKit. O fecho dele era textual: casava o
nome nu de módulo e contava o import de dentro de função como de topo. Uma corrente de imports
tardios (`a09_sistema` → `interface.janela`, `abrir` → `a09_sistema`, `app/tray` → `abrir`)
levou o fecho de 38 a 421 módulos, e o nome `app` de `cli/app.py` casou todo
`import hefesto_dualsense4unix.app.…`: 1582 de 2053 arquivos em processo próprio (127 em
17/10), e 75 s só para listar.

A RÉGUA DO TETO conta, por conta própria e pelo `ast`, os arquivos de teste que chegam ao
WebKit2 pelo import de TOPO dos módulos (o import do próprio teste e dos ajudantes de
`tests/unit/` conta em qualquer profundidade, que é onde ele roda) e cobra que a lista do
script não passe de 1,5 vez isso. A folga é o erro para mais que o script admite de propósito
(o import que só aparece numa string, o `__import__` de nome literal).

AS MORDIDAS (executadas em 23/10/2026; as duas primeiras rodam aqui, numa árvore de mentira):

1. o import tardio de `src/` volta a propagar (`do_topo` trocado por `do_texto`):
   `test_o_teto_morde_o_import_tardio_que_propaga` reprova o teto;
2. o fecho volta a casar o nome nu (`importa & nomes_do_webkit` pelo último pedaço do nome):
   `test_o_teto_morde_o_nome_nu` reprova o teto;
3. recoloque `from hefesto_dualsense4unix.interface.abrir import lembrar_o_parar` em
   `app/tray.py`, ou o `from hefesto_dualsense4unix.interface.janela import …` no «Copiar» de
   `a09_sistema`: `test_a_logica_nao_importa_a_moldura` reprova nomeando o módulo.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"
TETO = 1.5


def _nomes(rel: str) -> tuple[set[str], str]:
    """O caminho pontuado, cada sufixo dele (a casa põe pastas no `sys.path`) e o pacote."""
    partes = rel[:-3].split("/")
    init = partes[-1] == "__init__"
    if init:
        partes.pop()
    if partes[0] == "src":
        partes = partes[1:]
    return {".".join(partes[i:]) for i in range(len(partes))}, ".".join(
        partes if init else partes[:-1])


def _pede_o_webkit(no: ast.AST) -> bool:
    if isinstance(no, ast.Expr):
        no = no.value
    if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
        return (no.func.attr == "require_version" and bool(no.args)
                and isinstance(no.args[0], ast.Constant) and no.args[0].value == "WebKit2")
    return (isinstance(no, ast.ImportFrom) and no.module == "gi.repository"
            and any(a.name == "WebKit2" for a in no.names))


def _do_topo(arvore: ast.Module) -> list[ast.AST]:
    """Os nós que rodam ao importar o módulo: tudo fora de função."""
    vistos: list[ast.AST] = []
    pilha: list[ast.AST] = list(arvore.body)
    while pilha:
        no = pilha.pop()
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        vistos.append(no)
        for campo in ("body", "orelse", "finalbody", "handlers"):
            pilha.extend(getattr(no, campo, None) or [])
    return vistos


def _importados(nos: list[ast.AST], pacote: str) -> set[str]:
    saida: set[str] = set()
    for no in nos:
        if isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            if no.level:
                pai = pacote.split(".")[: max(0, len(pacote.split(".")) - (no.level - 1))]
                base = ".".join(pai + ([base] if base else []))
            nomes = [base, *(f"{base}.{a.name}" for a in no.names)]
        else:
            continue
        for nome in nomes:
            partes = nome.split(".")
            saida |= {".".join(partes[: k + 1]) for k in range(len(partes))}
    return saida


def _modulos(raiz: Path) -> dict[str, tuple[set[str], set[str], bool]]:
    """`rel → (nomes, importados, pede o WebKit)`: `src/` e `scripts/` só pelo topo."""
    modulos = {}
    caminhos = [*sorted((raiz / "src").rglob("*.py")),
                *sorted((raiz / "scripts").rglob("*.py")),
                *sorted((raiz / "tests" / "unit").glob("*.py"))]
    for caminho in caminhos:
        rel = caminho.relative_to(raiz).as_posix()
        if caminho.name == "conftest.py":
            continue
        nomes, pacote = _nomes(rel)
        texto = caminho.read_text(encoding="utf-8")
        try:
            arvore = ast.parse(texto)
        except SyntaxError:
            continue
        if rel.startswith("tests/"):
            nos = list(ast.walk(arvore))
            modulos[rel] = (nomes, _importados(nos, pacote), "WebKit2" in texto)
        else:
            nos = _do_topo(arvore)
            modulos[rel] = (nomes, _importados(nos, pacote), any(map(_pede_o_webkit, nos)))
    return modulos


def _fecho(modulos: dict[str, tuple[set[str], set[str], bool]]) -> tuple[set[str], set[str]]:
    dentro: set[str] = set()
    nomes_dentro: set[str] = set()
    while novos := {rel for rel, (_n, importa, pede) in modulos.items()
                    if rel not in dentro and (pede or importa & nomes_dentro)}:
        dentro |= novos
        for rel in novos:
            nomes_dentro |= modulos[rel][0]
    return dentro, nomes_dentro


def _chegam_ao_webkit(raiz: Path) -> set[str]:
    """Os arquivos de teste que chegam ao WebKit2 pelo import de topo dos módulos."""
    dentro, _ = _fecho(_modulos(raiz))
    return {rel for rel in dentro if rel.startswith("tests/unit/test_")}


def _listar(raiz: Path, suite: Path, saida: Path) -> list[str]:
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD", "PARTES", "SAIDA", "PARTIDO",
            "LOTE"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", "PY": sys.executable, "LISTAR_O_WEBKIT": "1",
                "SAIDA": str(saida)})
    feito = subprocess.run(["bash", str(suite)], cwd=raiz, capture_output=True, text=True,
                           timeout=300, check=False, env=env)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    return feito.stdout.split()


def _cabe_no_teto(lista: list[str], chegam: set[str]) -> None:
    assert len(lista) <= TETO * len(chegam), (
        f"a lista do WebKit tem {len(lista)} arquivos, e só {len(chegam)} chegam ao WebKit2 "
        f"pelo import de topo (o teto é {TETO} vez isso): o fecho do rodar-a-suite.sh inchou")


def test_a_lista_do_webkit_da_arvore_cabe_no_teto(tmp_path: Path) -> None:
    lista = _listar(RAIZ, SUITE, tmp_path / "saida")
    chegam = _chegam_ao_webkit(RAIZ)
    assert len(chegam) >= 20, f"o AST achou só {len(chegam)}: a régua ficou cega"
    _cabe_no_teto(lista, chegam)


# A árvore de mentira das mordidas: uma moldura com WebKit, uma lógica que a importa dentro de
# função, um `cli/app.py` que a importa no topo (legítimo) e um pacote `app` que não tem nada.
_ARVORE = {
    "src/casa/__init__.py": "",
    "src/casa/moldura.py": 'import gi\ngi.require_version("WebKit2", "4.1")\n'
                           "from gi.repository import WebKit2\n",
    "src/casa/regra.py": "def copiar():\n    from casa.moldura import WebKit2\n"
                          "    return WebKit2\n",
    "src/casa/cli/__init__.py": "",
    "src/casa/cli/app.py": "from casa import moldura\n",
    "src/casa/app/__init__.py": "",
    "src/casa/app/coisa.py": "X = 1\n",
    "tests/__init__.py": "",
    "tests/unit/__init__.py": "",
    "tests/unit/test_a_moldura.py": "from casa import moldura\n",
    "tests/unit/test_o_cli.py": "from casa.cli import app\n",
    **{f"tests/unit/test_a_regra_{n}.py": "from casa import regra\n" for n in range(4)},
    **{f"tests/unit/test_a_coisa_{n}.py": "from casa.app import coisa\n" for n in range(4)},
}


def _arvore_de_mentira(tmp_path: Path, troca: tuple[str, str] | None) -> tuple[list[str], set[str]]:
    raiz = tmp_path / "arvore"
    for rel, texto in _ARVORE.items():
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(texto, encoding="utf-8")
    texto = SUITE.read_text(encoding="utf-8")
    if troca is not None:
        assert troca[0] in texto, f"a cura «{troca[0]}» deixou de estar no script"
        texto = texto.replace(troca[0], troca[1])
    (raiz / "scripts").mkdir()
    (raiz / "scripts" / "rodar-a-suite.sh").write_text(texto, encoding="utf-8")
    lista = _listar(raiz, raiz / "scripts" / "rodar-a-suite.sh", tmp_path / "saida")
    return lista, _chegam_ao_webkit(raiz)


def test_na_arvore_de_mentira_so_vai_quem_chega_ao_webkit(tmp_path: Path) -> None:
    lista, chegam = _arvore_de_mentira(tmp_path, None)
    assert chegam == {"tests/unit/test_a_moldura.py", "tests/unit/test_o_cli.py"}
    assert sorted(lista) == sorted(chegam)


def test_o_teto_morde_o_import_tardio_que_propaga(tmp_path: Path) -> None:
    lista, chegam = _arvore_de_mentira(tmp_path, (
        "return (nomes, *do_topo(ast.parse(texto, rel), pacote))",
        'return nomes, do_texto(texto, pacote), "WebKit2" in texto'))
    assert "tests/unit/test_a_regra_0.py" in lista
    try:
        _cabe_no_teto(lista, chegam)
    except AssertionError:
        return
    raise AssertionError("o teto não mordeu o import tardio que propaga o fecho")


def test_o_teto_morde_o_nome_nu(tmp_path: Path) -> None:
    lista, chegam = _arvore_de_mentira(tmp_path, (
        "importa & nomes_do_webkit",
        '{p for n in importa for p in n.split(".")}'
        ' & {n.rsplit(".", 1)[-1] for n in nomes_do_webkit}'))
    assert "tests/unit/test_a_coisa_0.py" in lista
    try:
        _cabe_no_teto(lista, chegam)
    except AssertionError:
        return
    raise AssertionError("o teto não mordeu o fecho por nome nu")


def test_a_logica_nao_importa_a_moldura() -> None:
    """Fora da moldura (os módulos que carregam o WebKit no topo) e da entrada que a abre
    (`interface/abrir.py`), nenhum módulo de `src/` importa um deles, nem dentro de função.

    A lógica que importa a moldura só para uma função (a marca do Parar, a área de
    transferência) arrasta o WebKit para quem a chama; o dono neutro mora em `utils/`
    (`marca_do_parar`, `area_de_transferencia`), e a moldura entrega o que é do usuário."""
    modulos = {rel: m for rel, m in _modulos(RAIZ).items() if rel.startswith("src/")}
    moldura, nomes_da_moldura = _fecho(modulos)
    abrir = "src/hefesto_dualsense4unix/interface/abrir.py"
    moldura.add(abrir)
    nomes_da_moldura |= modulos[abrir][0]
    assert "src/hefesto_dualsense4unix/interface/janela.py" in moldura, "a régua ficou cega"
    ruins = []
    for rel in sorted(set(modulos) - moldura):
        arvore = ast.parse((RAIZ / rel).read_text(encoding="utf-8"))
        pacote = _nomes(rel)[1]
        chama = _importados(list(ast.walk(arvore)), pacote) & nomes_da_moldura
        if chama:
            ruins.append(f"{rel} importa {sorted(chama)[-1]}")
    assert not ruins, "a lógica importa a moldura:\n  " + "\n  ".join(ruins)
