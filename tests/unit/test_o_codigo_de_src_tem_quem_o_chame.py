"""Todo módulo de `src/` tem quem o chame no produto. O-CODIGO-QUE-SO-O-TESTE-CHAMA-01.

O caminho do produto parte do que se instala e se executa: os pontos de entrada do
`pyproject.toml`, os arquivos fora de `src/`, `tests/`, `scripts/`, da documentação e
da configuração do git (o `install.sh`, as units, os `.desktop`, o empacotamento) e os
scripts que eles nomeiam. Dali se segue o `import`, o nome pontuado ou o caminho numa
string de código e, dentro de `interface/`, o `import` do irmão por nome nu. O módulo que
fica de fora mora em `_FORA_DO_PRODUTO`, com a razão; o resto vai para `scripts/` ou sai.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = "hefesto_dualsense4unix"

_GERADOR = (
    "gerador do desenho: `interface/regerar.py` o roda em subprocesso, por caminho, e quem "
    "edita o desenho o roda à mão; o `mockup/` nasce dele e o `--publicar` leva ao produto. "
    "Mora ao lado do `monta.py`, que ele usa como biblioteca"
)

#: O que fica em `src/` sem caminho do produto, e por quê. Chave: o módulo sem o pacote.
_FORA_DO_PRODUTO: dict[str, str] = {
    "interface.aba01": _GERADOR,
    "interface.aba03": _GERADOR,
    "interface.aba04": _GERADOR,
    "interface.aba05": _GERADOR,
    "interface.aba06": _GERADOR,
    "interface.aba07": _GERADOR,
    "interface.aba08": _GERADOR,
    "interface.aba09": _GERADOR,
    "interface.aba10": _GERADOR,
    "interface.mapa": (
        "gerador da página avulsa «Mapa do controle» e dono das peças que os geradores e o "
        "portão `pecas-do-dualsense` leem; mora ao lado do `monta.py`, como os `abaNN.py`"
    ),
    "interface.olhar": (
        "o retratista das dez páginas (Chrome headless), a rotina de toda mudança de tela: a "
        "tabela de `docs/method/COMO-OLHAR-A-TELA.md` o chama por este endereço, e "
        "`tests/unit/test_a_tabela_dos_scripts_de_tela.py` o cobra ali"
    ),
    "interface.regerar": (
        "a volta dos dez geradores contra o mesmo `ds_limpo.svg`; é a porta de entrada da "
        "bancada do desenho, rodada por quem edita o `mockup/`"
    ),
    "interface.ver": (
        "o visor do desenho aprovado dentro do WebKit; a tabela de instrumentos de "
        "`docs/method/COMO-OLHAR-A-TELA.md` o cita neste endereço, e "
        "`tests/unit/test_a_tabela_dos_scripts_de_tela.py` cobra que ele exista"
    ),
    "app.fatos_do_mapa": (
        "GERADO por `scripts/gerar-fatos-de-tela.py` a partir do `mapa-controles.csv`, e "
        "conferido pelo portão `fatos-de-tela`; as réguas de tela o leem para cobrar que a "
        "tela não afirme mais que o mapa"
    ),
    "profiles.curva_propria": (
        "o formato da curva própria com proveniência (sala limpa, CR-02), citado pelo NOTICE; "
        "`scripts/gerar-tabela-de-curvas.py` o usa no portão `curvas`"
    ),
    "integrations.varredura_do_radio": (
        "instrumento de bancada (`scripts/ensaios/o_travamento_fator_a_fator.py` pergunta "
        "quem varre com ele) e dono das constantes medidas que "
        "`docs/data/orcamento-de-ar.csv` aponta por este caminho, e que "
        "`tests/unit/test_o_orcamento_conta_a_ponte.py` importa de lá"
    ),
}

_PONTUADO = re.compile(r"hefesto_dualsense4unix(?:\.[A-Za-z_]\w*)+")
_CAMINHO = re.compile(r"hefesto_dualsense4unix/[\w/]+\.py")
#: O `from pacote import módulo` do Python embutido num heredoc de shell.
_DE_IMPORT = re.compile(
    r"from\s+(hefesto_dualsense4unix[\w.]*)\s+import[ \t]+(?:\(([^)]*)\)|([\w \t,]+))")
_SCRIPT = re.compile(r"scripts/[\w./-]+\.(?:sh|py)")
_FORA = ("src/", "tests/", "scripts/", "docs/", "mockup/", ".github/", "LICENSES/", "po/",
         "examples/")
_DOC = (".md", ".csv", ".txt", ".html", ".png", ".svg", ".json")
#: Texto da casa que nada executa: a licença, o aviso, e a configuração do git e dos ganchos.
_NAO_EXECUTA = frozenset({"NOTICE", "LICENSE"})


def _arquivos(raiz: Path) -> list[str]:
    if (raiz / ".git").exists():
        # O arquivo novo ainda fora do índice também conta: a régua não fica cega a ele.
        saida = subprocess.run(["git", "-C", str(raiz), "ls-files", "-z", "--cached", "--others",
                                "--exclude-standard"],
                               capture_output=True, check=True).stdout.decode()
        return [f for f in saida.split("\0") if f and (raiz / f).is_file()]
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file())


def _nome(arquivo: str) -> str:
    partes = list(Path(arquivo).relative_to("src").with_suffix("").parts)
    return ".".join(partes[:-1] if partes[-1] == "__init__" else partes)


class _Grafo:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.arquivos = _arquivos(raiz)
        self.do_src = {_nome(f): f for f in self.arquivos
                        if f.startswith("src/") and f.endswith(".py")}

    def alvos(self, nomes: set[str]) -> set[str]:
        achados: set[str] = set()
        for nome in nomes:
            partes = nome.split(".")
            achados |= {c for i in range(1, len(partes) + 1)
                        if (c := ".".join(partes[:i])) in self.do_src}
        return achados

    def do_texto(self, texto: str) -> set[str]:
        caminhos = (c[:-3].replace("/", ".").removesuffix(".__init__")
                    for c in _CAMINHO.findall(texto))
        importados = {f"{base}.{nome.split()[0]}"
                      for base, entre, solto in _DE_IMPORT.findall(texto)
                      for nome in (entre or solto).split(",") if nome.strip()}
        return self.alvos(set(_PONTUADO.findall(texto)) | set(caminhos) | importados)

    def do_python(self, arquivo: str) -> tuple[set[str], set[str]]:
        """Os módulos que o arquivo importa ou nomeia em string de código, e os scripts."""
        try:
            arvore = ast.parse((self.raiz / arquivo).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            return set(), set()
        atual = _nome(arquivo) if arquivo.startswith("src/") else ""
        e_pacote = arquivo.endswith("__init__.py")
        docstrings = {id(n.value) for n in ast.walk(arvore)
                      if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
        nomes: set[str] = set()
        achados: set[str] = set()
        scripts: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes |= {a.name for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                if no.level and not atual:
                    continue
                base = no.module or ""
                if no.level:
                    partes = atual.split(".") if e_pacote else atual.split(".")[:-1]
                    partes = partes[: len(partes) - (no.level - 1)]
                    base = ".".join(partes + ([no.module] if no.module else []))
                nomes.add(base)
                nomes |= {f"{base}.{a.name}" for a in no.names}
            elif (isinstance(no, ast.Constant) and isinstance(no.value, str)
                  and id(no) not in docstrings):
                achados |= self.do_texto(no.value)
                scripts |= set(_SCRIPT.findall(no.value))
                if atual and " " not in no.value and f"{PACOTE}.{no.value}" in self.do_src:
                    achados.add(f"{PACOTE}.{no.value}")
        if f"{PACOTE}.interface" in atual or "/interface/" in arquivo:
            # A pasta da interface entra no `sys.path`: o irmão se importa por nome nu.
            nus = {n for n in nomes if not n.startswith(PACOTE)
                   and n.split(".")[0] not in sys.stdlib_module_names}
            nomes |= {f"{PACOTE}.interface.{n}" for n in nus}
        achados |= self.alvos(nomes)
        achados.discard(atual)
        return achados, scripts

    def de_fora(self, arquivo: str) -> tuple[set[str], set[str]]:
        try:
            texto = (self.raiz / arquivo).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return set(), set()
        if arquivo == "pyproject.toml":
            projeto = tomllib.loads(texto).get("project", {})
            texto = json.dumps([projeto.get(k, {})
                                for k in ("scripts", "gui-scripts", "entry-points")])
        texto = "\n".join(linha for linha in texto.splitlines()
                          if not linha.lstrip().startswith("#"))
        return self.do_texto(texto), set(_SCRIPT.findall(texto))

    def fora_do_produto(self) -> set[str]:
        """Os módulos de `src/` que nenhum caminho do produto alcança."""
        produto = [f for f in self.arquivos
                   if not f.startswith(_FORA) and not f.endswith(_DOC)
                   and not f.startswith(".") and f not in _NAO_EXECUTA]
        raizes: set[str] = {PACOTE, f"{PACOTE}.__main__"}
        vistos: set[str] = set()
        pendentes = list(produto)
        while pendentes:
            f = pendentes.pop()
            if f in vistos:
                continue
            vistos.add(f)
            do_src, scripts = (self.do_python(f) if f.endswith(".py") else self.de_fora(f))
            raizes |= do_src
            pendentes += [s for s in scripts if (self.raiz / s).is_file()]
        arestas = {m: self.do_python(f)[0] for m, f in self.do_src.items()}
        alcancados: set[str] = set()
        pilha = list(raizes)
        while pilha:
            m = pilha.pop()
            if m in alcancados:
                continue
            alcancados.add(m)
            partes = m.split(".")
            pilha += [p for i in range(1, len(partes))
                      if (p := ".".join(partes[:i])) in self.do_src]
            pilha += arestas.get(m, ())
        return set(self.do_src) - alcancados


def _sem_pacote(do_src: set[str]) -> set[str]:
    return {m.removeprefix(f"{PACOTE}.") for m in do_src}


_FORA_HOJE = _sem_pacote(_Grafo(RAIZ).fora_do_produto())


def test_todo_modulo_de_src_tem_caminho_do_produto_ou_razao_declarada() -> None:
    """O módulo novo que só o teste chama reprova aqui, com o nome dele."""
    sem_razao = sorted(_FORA_HOJE - set(_FORA_DO_PRODUTO))
    assert not sem_razao, (
        "estes módulos de `src/` não têm caminho do produto (nem entrada do pyproject, "
        "nem o install, nem import a partir deles):\n  " + "\n  ".join(sem_razao)
        + "\nDê UM destino a cada um: ligue-o ao produto; leve-o a `scripts/` se ele mede "
        "(o teste vai junto); apague-o com o teste se ninguém o usa; ou, se ele é porta de "
        "entrada que esta régua não vê, declare-o em `_FORA_DO_PRODUTO` com a razão."
    )


def test_a_excecao_declarada_ainda_esta_fora_do_produto() -> None:
    """Declaração que o produto passou a alcançar é razão velha: sai da lista."""
    velhas = sorted(set(_FORA_DO_PRODUTO) - _FORA_HOJE)
    assert not velhas, (
        "estas exceções de `_FORA_DO_PRODUTO` já têm caminho do produto, ou o módulo "
        f"saiu de `src/`: {velhas}. Tire a linha."
    )


def test_a_regua_acha_o_produto() -> None:
    """Régua que não alcança o daemon nem a interface passa sobre o vazio."""
    grafo = _Grafo(RAIZ)
    alcancados = set(grafo.do_src) - grafo.fora_do_produto()
    for essencial in ("daemon.main", "cli.app", "interface.abrir", "interface.hefesto_vivo",
                      "interface.pacotes.a10_perfis"):
        assert f"{PACOTE}.{essencial}" in alcancados, essencial
    assert len(alcancados) > 300, len(alcancados)


def _arvore_de_mentira(raiz: Path) -> None:
    pacote = raiz / "src" / PACOTE
    (pacote / "interface").mkdir(parents=True)
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "__main__.py").write_text(f"from {PACOTE} import ligado\n", encoding="utf-8")
    (pacote / "ligado.py").write_text("VALOR = 1\n", encoding="utf-8")
    (pacote / "so_do_teste.py").write_text("VALOR = 2\n", encoding="utf-8")
    (pacote / "interface" / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "interface" / "abrir.py").write_text("import vizinho\n", encoding="utf-8")
    (pacote / "interface" / "vizinho.py").write_text("X = 1\n", encoding="utf-8")
    (raiz / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.gui-scripts]\n'
        f'x-gui = "{PACOTE}.interface.abrir:entrada"\n', encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_x.py").write_text(f"from {PACOTE} import so_do_teste\n",
                                              encoding="utf-8")


def test_a_mordida_o_modulo_que_so_o_teste_importa_reprova(tmp_path: Path) -> None:
    """A mordida: um módulo novo em `src/` que só um teste importa fica de fora."""
    _arvore_de_mentira(tmp_path)
    fora = _sem_pacote(_Grafo(tmp_path).fora_do_produto())
    assert fora == {"so_do_teste"}, fora


def test_a_mordida_o_install_que_nomeia_o_modulo_o_liga(tmp_path: Path) -> None:
    """O heredoc do install conta como caminho: é como o `kernel_cmdline` é chamado."""
    _arvore_de_mentira(tmp_path)
    (tmp_path / "install.sh").write_text(
        f"python3 - <<'PY'\nfrom {PACOTE} import so_do_teste\nPY\n", encoding="utf-8")
    assert _Grafo(tmp_path).fora_do_produto() == set()
