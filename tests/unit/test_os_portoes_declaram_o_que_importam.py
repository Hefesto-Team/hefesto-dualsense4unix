"""DIVIDA-DO-PLAYWRIGHT-01 — todo portão declara a biblioteca de que precisa."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"
PYPROJECT = RAIZ / "pyproject.toml"

STDLIB = set(sys.stdlib_module_names)

DA_CASA = {"hefesto_dualsense4unix", "tests"}

EXCECOES = {
    "gi": "vem do pacote do sistema (python3-gi); o install.sh o garante no censo",
}


PASTAS_DA_CASA = ("scripts", "src", "tests", "layout")


def _modulos_da_casa() -> set[str]:
    nomes: set[str] = set()
    for pasta in PASTAS_DA_CASA:
        raiz = RAIZ / pasta
        if not raiz.is_dir():
            continue
        for caminho in raiz.rglob("*.py"):
            if ".venv" in caminho.parts or "__pycache__" in caminho.parts:
                continue
            nomes.add(caminho.stem)
            if caminho.name == "__init__.py":
                nomes.add(caminho.parent.name)
    return nomes


MODULOS_DA_CASA = _modulos_da_casa()


def _e_modulo_vizinho(nome: str) -> bool:
    """Um `import comum` num roteiro é o arquivo do lado, não o PyPI."""
    return nome in MODULOS_DA_CASA


def _imports_de_terceiros(caminho: Path) -> set[str]:
    """Os módulos de terceiro que este arquivo importa DE VERDADE."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - outro portão cuida
        return set()

    dentro_de_try: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Try):
            for filho in ast.walk(no):
                dentro_de_try.add(id(filho))

    achados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes = [alias.name.split(".")[0] for alias in no.names]
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                continue
            nomes = [(no.module or "").split(".")[0]]
        else:
            continue
        if id(no) in dentro_de_try:
            continue
        for nome in nomes:
            if not nome or nome in STDLIB or nome in DA_CASA:
                continue
            if _e_modulo_vizinho(nome):
                continue
            achados.add(nome)
    return achados


def _declaradas_no_pyproject() -> set[str]:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    projeto = dados.get("project", {})
    linhas: list[str] = list(projeto.get("dependencies", []))
    for extra in (projeto.get("optional-dependencies") or {}).values():
        linhas.extend(extra)
    nomes = set()
    for linha in linhas:
        nome = linha.split(";")[0].strip()
        for separador in ("[", ">", "<", "=", "!", "~", " "):
            nome = nome.split(separador)[0]
        if nome:
            nomes.add(nome.lower())
            nomes.add(nome.lower().replace("-", "_"))
            nomes.add(nome.lower().removeprefix("python-").replace("-", "_"))
            nomes.add(nome.lower().removeprefix("py"))
    return nomes


def test_todo_portao_de_scripts_importa_so_o_que_esta_declarado() -> None:
    """A régua, sobre `scripts/` inteiro."""
    declaradas = _declaradas_no_pyproject()
    achados: list[str] = []
    for caminho in sorted(SCRIPTS.glob("*.py")):
        for nome in sorted(_imports_de_terceiros(caminho)):
            if nome in EXCECOES:
                continue
            if nome.lower() in declaradas or nome.lower().replace("_", "-") in declaradas:
                continue
            achados.append(f"{caminho.relative_to(RAIZ)}: {nome}")
    assert not achados, (
        "biblioteca de terceiro importada em `scripts/` e NÃO declarada no "
        "`pyproject.toml`:\n  "
        + "\n  ".join(achados)
        + "\n\nÉ a dívida do `playwright` outra vez: quem escreveu tem a "
        "biblioteca na bancada, e toda árvore nova nasce com o portão vermelho "
        "sem dizer por quê. Declare no extra `[dev]` (é ferramenta de portão, "
        "não do produto) ou acrescente uma exceção COM MOTIVO em `EXCECOES`."
    )


def test_o_playwright_esta_declarado() -> None:
    """O caso nomeado, cravado para não voltar."""
    assert "playwright" in _declaradas_no_pyproject(), (
        "o `playwright` saiu do `pyproject.toml`. Os portões "
        "`check_pecas_do_dualsense` e `check_cores_do_dualsense` o importam, e "
        "sem a declaração toda árvore de trabalho nova nasce com os dois "
        "vermelhos — o defeito que a casa já descrevia em 29/08/2026"
    )


def test_o_playwright_esta_no_dev_e_nao_no_runtime() -> None:
    """Onde ele mora importa: `[dev]` é gate, `dependencies` é produto."""
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    projeto = dados["project"]
    runtime = " ".join(projeto.get("dependencies", []))
    dev = " ".join((projeto.get("optional-dependencies") or {}).get("dev", []))
    assert "playwright" not in runtime, (
        "o `playwright` virou dependência de RUNTIME. Ele é ferramenta de "
        "portão: o produto não o importa, e quem só quer usar o DualSense "
        "passaria a baixá-lo"
    )
    assert "playwright" in dev, (
        "o `playwright` saiu do extra `[dev]` — que é o extra que o "
        "`install.sh` instala por padrão, e por isso o único lugar em que a "
        "declaração conserta a máquina de quem instala"
    )


def test_os_dois_portoes_que_o_usam_abrem_o_chrome_do_sistema() -> None:
    """Declarar o pacote pip NÃO basta se o portão precisar de um navegador"""
    for nome in ("check_pecas_do_dualsense.py", "check_cores_do_dualsense.py"):
        texto = (SCRIPTS / nome).read_text(encoding="utf-8")
        assert 'executable_path="/usr/bin/google-chrome"' in texto, (
            f"`scripts/{nome}` deixou de abrir o Chrome do SISTEMA. Se ele "
            "passar a usar o navegador do próprio playwright, `pip install "
            "playwright` não basta mais: seria preciso um `playwright install` "
            "de ~300 MB, e isso é decisão de quem mantém o projeto — não pode "
            "acontecer por acidente numa mudança de portão"
        )
