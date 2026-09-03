"""DIVIDA-DO-PLAYWRIGHT-01 — todo portão declara a biblioteca de que precisa.

O DEFEITO, com nome e data. Dois portões desta casa importam `playwright`:

    scripts/check_pecas_do_dualsense.py
    scripts/check_cores_do_dualsense.py

e o `pyproject.toml` não o declarava em extra nenhum. Ele vivia na bancada de
quem escreveu os portões, por instalação à mão. O efeito é o mesmo toda vez, e
o `CLAUDE.md` da casa já o descrevia em 29/08/2026: uma árvore criada com
`pip install -e ".[dev,emulation,cosmic]"` NASCE com dois portões vermelhos, e
quem chega gasta a manhã concluindo que quebrou alguma coisa.

Não é um caso isolado — é uma FORMA, e a mesma forma já mordeu esta casa em
outro lugar: `tests/unit/test_o_install_entrega_a_luz_do_mic.py` guarda `src/`
contra biblioteca de áudio não declarada, com o `playwright` citado no
cabeçalho como o precedente a não repetir. O que faltava era a régua do outro
lado da cerca: `scripts/`, onde moram os portões.

ESTE ARQUIVO É ESSA RÉGUA. Ele lê os imports de verdade (AST, nunca `grep`) e
exige que toda biblioteca de terceiro esteja declarada — ou esteja numa lista
de exceções com o motivo escrito.

A MORDIDA (feita em 03/09/2026): tirada a linha `playwright>=1.62` do
`[project.optional-dependencies].dev`, o teste reprovou nomeando os dois
portões e a biblioteca. Devolvida, voltou verde.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"
PYPROJECT = RAIZ / "pyproject.toml"

# `sys.stdlib_module_names` é a lista do PRÓPRIO interpretador que roda o teste
# — nada digitado à mão, que é como uma régua desta casa envelhece.
STDLIB = set(sys.stdlib_module_names)

DA_CASA = {"hefesto_dualsense4unix", "tests"}

# O que NÃO precisa estar no `pyproject.toml`, com o motivo. Uma exceção sem
# motivo é uma dívida escondida atrás de uma lista.
EXCECOES = {
    # O PyGObject vem do SISTEMA (`python3-gi`), não do pip: a wheel do pip não
    # traz o typelib nem os bindings do GTK. Quem garante é o censo
    # `_DEPS_DE_SISTEMA` do `install.sh`, que o pede como `python-gi` e o
    # confere pelo EFEITO — e é por isso que o venv desta casa nasce com
    # `--system-site-packages`.
    "gi": "vem do pacote do sistema (python3-gi); o install.sh o garante no censo",
}


# As pastas que os roteiros desta casa põem no `sys.path` à mão antes de
# importar um módulo daqui — `scripts/check_cores_do_dualsense.py:188` faz
# exatamente isso para alcançar o `monta.py` da interface, e o
# `capture_blueprint.py` para alcançar o `comum.py` dos ensaios.
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
    """Um `import comum` num roteiro é o arquivo do lado, não o PyPI.

    A busca é por TODA pasta da casa, e não só por `scripts/`: os roteiros
    fazem `sys.path.insert` para alcançar módulos de `src/` e de
    `scripts/ensaios/`, e uma régua que só olhasse o diretório do arquivo
    chamaria de "dependência não declarada" um arquivo do próprio repositório.
    """
    return nome in MODULOS_DA_CASA


def _imports_de_terceiros(caminho: Path) -> set[str]:
    """Os módulos de terceiro que este arquivo importa DE VERDADE.

    Import dentro de `try:` fica de fora: é o padrão do fallback opcional (o
    `check_version_consistency.py` faz `try: import tomllib / except: import
    tomli`), e cobrá-lo obrigaria a declarar uma dependência que o arquivo já
    sabe viver sem.
    """
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
            if no.level:  # import relativo: é da própria pasta
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
        # `pydualsense>=0.7.5` -> `pydualsense`; `ruff==0.15.20` -> `ruff`.
        nome = linha.split(";")[0].strip()
        for separador in ("[", ">", "<", "=", "!", "~", " "):
            nome = nome.split(separador)[0]
        if nome:
            # O nome do PROJETO e o nome do MÓDULO divergem em alguns casos
            # (`python-uinput` importa `uinput`, `PyYAML` importa `yaml`), então
            # guardamos as duas grafias normalizadas.
            nomes.add(nome.lower())
            nomes.add(nome.lower().replace("-", "_"))
            nomes.add(nome.lower().removeprefix("python-").replace("-", "_"))
            nomes.add(nome.lower().removeprefix("py"))
    return nomes


def test_todo_portao_de_scripts_importa_so_o_que_esta_declarado() -> None:
    """A régua, sobre `scripts/` inteiro.

    A MORDIDA: acrescente `import requests` a qualquer `scripts/*.py` e isto
    reprova nomeando o arquivo — que é exatamente o que NÃO aconteceu com o
    `playwright` durante semanas.
    """
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
    """O caso nomeado, cravado para não voltar.

    A MORDIDA: tire `playwright>=1.62` do `[dev]` e isto reprova.
    """
    assert "playwright" in _declaradas_no_pyproject(), (
        "o `playwright` saiu do `pyproject.toml`. Os portões "
        "`check_pecas_do_dualsense` e `check_cores_do_dualsense` o importam, e "
        "sem a declaração toda árvore de trabalho nova nasce com os dois "
        "vermelhos — o defeito que o `CLAUDE.md` já descrevia em 29/08/2026"
    )


def test_o_playwright_esta_no_dev_e_nao_no_runtime() -> None:
    """Onde ele mora importa: `[dev]` é gate, `dependencies` é produto.

    A MORDIDA: mova a linha para `dependencies` e isto reprova. O produto NÃO
    importa playwright em lugar nenhum — pô-lo no runtime cobraria de quem só
    quer usar o controle o download de uma ferramenta de teste.
    """
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
    """Declarar o pacote pip NÃO basta se o portão precisar de um navegador
    baixado — e é aqui que se vê que não precisa.

    Os dois portões passam `executable_path="/usr/bin/google-chrome"`, então
    nenhum `playwright install` (≈300 MB de navegadores) entra neste projeto.

    A MORDIDA: tire o `executable_path` de qualquer um dos dois e isto reprova
    — porque aí a declaração do `pyproject.toml` deixaria de ser suficiente e
    alguém teria de decidir, conscientemente, baixar os navegadores.
    """
    for nome in ("check_pecas_do_dualsense.py", "check_cores_do_dualsense.py"):
        texto = (SCRIPTS / nome).read_text(encoding="utf-8")
        assert 'executable_path="/usr/bin/google-chrome"' in texto, (
            f"`scripts/{nome}` deixou de abrir o Chrome do SISTEMA. Se ele "
            "passar a usar o navegador do próprio playwright, `pip install "
            "playwright` não basta mais: seria preciso um `playwright install` "
            "de ~300 MB, e isso é decisão de quem mantém o projeto — não pode "
            "acontecer por acidente numa mudança de portão"
        )
