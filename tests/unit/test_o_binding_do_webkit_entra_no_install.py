"""ROTA-WEBKIT — o binding do WebKit entra no `install.sh`, sem flag."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL_PATH = RAIZ / "install.sh"
INSTALL = INSTALL_PATH.read_text(encoding="utf-8")

CANONICO = "webkit2gtk"
NOMES_MEDIDOS = {
    "apt": "gir1.2-webkit2-4.1",
    "dnf": "webkit2gtk4.1",
    "pacman": "webkit2gtk-4.1",
}

FAMILIAS = tuple(NOMES_MEDIDOS)

VAZIOS_ACEITOS_NO_CENSO: set[tuple[str, str]] = set()


def _extrai_funcao(nome: str) -> str:
    """``nome() { ... }`` até a primeira ``}`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", INSTALL, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada em install.sh"
    fim = re.search(r"^\}\n", INSTALL[match.end():], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return INSTALL[match.start(): match.end() + fim.end()]


def _extrai_array(nome: str) -> str:
    """``nome=(`` até a primeira ``)`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}=\(\n", INSTALL, re.MULTILINE)
    assert match is not None, f"array {nome} não encontrado em install.sh"
    fim = re.search(r"^\)\n", INSTALL[match.end():], re.MULTILINE)
    assert fim is not None, f"fim de {nome} não encontrado"
    return INSTALL[match.start(): match.end() + fim.end()]


def _entradas_do_censo() -> list[str]:
    """As linhas ``canônico|criticidade|checagem|razão`` do censo."""
    return re.findall(r'"([^"]*\|[^"]*)"', _extrai_array("_DEPS_DE_SISTEMA"))


def _linha_do_censo(canonico: str) -> str | None:
    for linha in _entradas_do_censo():
        if linha.split("|")[0] == canonico:
            return linha
    return None


def _roda(corpo: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_FAMILIA_PACOTES", None)
    ambiente.pop("HEFESTO_OS_RELEASE", None)
    ambiente.update(env or {})
    preludo = "\n".join(
        [
            "set -euo pipefail",
            _extrai_funcao("_familia_pacotes"),
            _extrai_funcao("_pkg_nome"),
        ]
    )
    return subprocess.run(
        [BASH, "-c", preludo + "\n" + corpo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
    )


def _checagem(venv_dir: Path, checagem: str) -> int:
    """Roda ``_dep_presente <checagem>`` com o ``VENV_DIR`` que se pedir."""
    script = "\n".join(
        [
            "set -euo pipefail",
            f'VENV_DIR="{venv_dir}"',
            '_VENV_PYTHON="python3"',
            _extrai_funcao("_dep_presente"),
            f'_dep_presente "{checagem}"',
        ]
    )
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=120
    ).returncode


@pytest.mark.parametrize("familia", FAMILIAS)
def test_a_tabela_traduz_o_binding_em_cada_familia(familia: str) -> None:
    """A MORDIDA: arranque a linha ``webkit2gtk)`` de ``_pkg_nome`` e as três"""
    proc = _roda(f"_pkg_nome {CANONICO} {familia}")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == NOMES_MEDIDOS[familia], (
        f"o nome do binding em {familia} mudou. Os três foram MEDIDOS em "
        "29/08/2026 (apt nesta bancada; dnf e pacman na lista de arquivos do "
        "pacote, conferindo o `WebKit2-4.1.typelib` lá dentro). Nome de pacote "
        "inferido é o que esta casa reprova desde a queda da família zypper"
    )


def test_a_serie_e_a_4_1_que_e_a_de_gtk3() -> None:
    """4.1 é a série de GTK 3; a 6.0 é GTK 4."""
    for familia, nome in NOMES_MEDIDOS.items():
        assert "4.1" in nome or "4-1" in nome, (
            f"o nome em {familia} ({nome!r}) não é da série 4.1 — a 6.0 é GTK 4 "
            "e não entra no processo do produto, que é GTK 3.0"
        )


def test_o_censo_pede_o_binding() -> None:
    """A MORDIDA: tire a linha ``"webkit2gtk|...`` do ``_DEPS_DE_SISTEMA`` e"""
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, (
        "o binding do WebKit saiu do censo `_DEPS_DE_SISTEMA`: voltou a ser "
        "instalação à mão, contra a regra dela — toda cura entra no install, "
        "sem flag"
    )
    _, criticidade, checagem, razao = linha.split("|")
    assert checagem == "webkit", (
        f"a checagem do binding virou {checagem!r} — a régua tem de perguntar "
        "pelo EFEITO (o motor carrega?), como manda o desenho do `_dep_presente`"
    )
    assert razao.strip(), "a linha ficou sem o 'o que quebra sem ele'"
    assert criticidade == "importante", (
        "a criticidade do binding mudou. Ela é `importante` **de propósito**: a "
        "rota WebKit ainda não foi escolhida por ela, e enquanto não for, "
        "ninguém pode pagar ~93 MB em disco por uma decisão que não foi "
        "tomada. NO DIA EM QUE A ROTA FOR ADOTADA a linha vira `obrigatoria` — "
        "e este teste é o outro lugar que muda junto, de propósito: a troca "
        "tem de ser consciente"
    )


def test_a_troca_para_obrigatoria_esta_escrita_em_cima_da_linha() -> None:
    """A decisão adiada tem de estar ESCRITA onde ela será feita."""
    linhas = INSTALL.splitlines()
    alvo = next(
        (i for i, x in enumerate(linhas) if x.strip().startswith(f'"{CANONICO}|')),
        None,
    )
    assert alvo is not None, "a linha do binding sumiu do censo"
    inicio = alvo
    while inicio > 0 and linhas[inicio - 1].strip().startswith("#"):
        inicio -= 1
    acima = "\n".join(linhas[inicio:alvo])
    assert "obrigatoria" in acima.lower(), (
        "o comentário acima da linha do binding não diz que ela vira "
        "`obrigatoria` no dia em que a rota WebKit for adotada. A decisão é "
        "dela e ainda não foi tomada: sem essa nota, a próxima pessoa não tem "
        "como saber que a troca é de UMA palavra, nesta linha"
    )


def _venv_falso(tmp_path: Path, stub: str, repositorio_stub: str = "") -> Path:
    """Um ``VENV_DIR`` cujo python enxerga um ``gi`` de mentira."""
    pacote = tmp_path / "stub" / "gi"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text(stub, encoding="utf-8")
    repositorio = pacote / "repository"
    repositorio.mkdir()
    (repositorio / "__init__.py").write_text(
        repositorio_stub
        or (
            "def __getattr__(nome):\n"
            "    raise ImportError('sem %s: a biblioteca não carrega' % nome)\n"
        ),
        encoding="utf-8",
    )
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin" / "python"
    python.write_text(
        "#!/usr/bin/env bash\n"
        f'exec env PYTHONPATH="{tmp_path / "stub"}" '
        f'"{RAIZ / ".venv" / "bin" / "python"}" "$@"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    return venv


STUB_SEM_TYPELIB = (
    "def require_version(espaco, serie):\n"
    "    raise ValueError('Namespace %s not available for version %s'\n"
    "                     % (espaco, serie))\n"
)

STUB_TYPELIB_SEM_BIBLIOTECA = (
    "def require_version(espaco, serie):\n"
    "    return None\n"
)

STUB_REPOSITORIO_QUE_IMPORTA_E_NAO_CARREGA = (
    "class _MotorSemBiblioteca:\n"
    "    @staticmethod\n"
    "    def get_major_version():\n"
    "        raise RuntimeError(\n"
    "            'Could not locate webkit_get_major_version: '\n"
    "            'libNAOEXISTE-4.1.so.0: cannot open shared object file')\n"
    "\n"
    "WebKit2 = _MotorSemBiblioteca()\n"
)


def test_maquina_sem_o_binding_le_como_ausente(tmp_path: Path) -> None:
    """A metade que TODA máquina consegue medir."""
    rc = _checagem(_venv_falso(tmp_path, STUB_SEM_TYPELIB), "webkit")
    assert rc != 0, (
        "um `gi` que NÃO tem o WebKit2 4.1 foi lido como PRESENTE: a régua "
        "parou de reprovar e o install deixaria de instalar o binding"
    )


def test_typelib_sem_a_biblioteca_tambem_e_ausente(tmp_path: Path) -> None:
    """O motivo de a checagem IMPORTAR, e não só pedir a versão."""
    rc = _checagem(
        _venv_falso(
            tmp_path,
            STUB_TYPELIB_SEM_BIBLIOTECA,
            STUB_REPOSITORIO_QUE_IMPORTA_E_NAO_CARREGA,
        ),
        "webkit",
    )
    assert rc != 0, (
        "typelib presente e biblioteca que não carrega passou por PRESENTE — a "
        "checagem voltou a olhar só a versão, em vez de perguntar se o motor "
        "CARREGA"
    )


def test_binding_presente_le_como_presente() -> None:
    """A outra metade: a régua não pode virar um não para tudo."""
    venv = RAIZ / ".venv"
    if not (venv / "bin" / "python").exists():
        pytest.skip("sem venv nesta árvore")
    disponivel = subprocess.run(
        [
            str(venv / "bin" / "python"),
            "-c",
            "import gi;gi.require_version('WebKit2','4.1');"
            "from gi.repository import WebKit2",
        ],
        capture_output=True,
        timeout=120,
    ).returncode
    if disponivel != 0:
        pytest.skip(
            "esta máquina não tem o `gir1.2-webkit2-4.1` (ou o equivalente da "
            "família): a metade PRESENTE da régua não pode ser medida aqui"
        )
    assert _checagem(venv, "webkit") == 0, (
        "o binding está instalado nesta máquina e a checagem do install o leu "
        "como AUSENTE — o instalador pediria sudo para instalar o que já está lá"
    )


def test_todo_canonico_do_censo_tem_nome_nas_tres_familias() -> None:
    """O portão que faltava."""
    entradas = _entradas_do_censo()
    assert entradas, "o censo saiu vazio — a régua ficou cega"
    pedidos = [
        (linha.split("|")[0], familia)
        for linha in entradas
        for familia in FAMILIAS
        if (linha.split("|")[0], familia) not in VAZIOS_ACEITOS_NO_CENSO
    ]
    corpo = "\n".join(
        f'printf "%s|%s|%s\\n" "{c}" "{f}" "$(_pkg_nome {c} {f})"' for c, f in pedidos
    )
    proc = _roda(corpo)
    assert proc.returncode == 0, proc.stderr
    faltando = [
        linha for linha in proc.stdout.splitlines() if linha.strip().endswith("|")
    ]
    assert not faltando, (
        "canônico do censo sem nome de pacote: "
        + ", ".join(x.rstrip("|").replace("|", " em ") for x in faltando)
        + ". O install avisaria 'não tenho nome para isso' e a dependência "
        "nunca seria instalada"
    )
