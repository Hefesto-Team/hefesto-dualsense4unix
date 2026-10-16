"""O tempo da casa só desce: a memória do rápido não vê o bytecode, e a catraca do tempo morde."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


RECIBO = _carregar("scripts/recibo_da_medida.py", "_recibo_do_tempo")


# --- a memória do rápido: o bytecode que os portões escrevem não muda a chave ---------------------


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore git com `src/` e `scripts/` rastreados e o bytecode ignorado, como a da casa."""
    (tmp_path / "src/pacote").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src/pacote/a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "scripts/b.py").write_text("b = 2\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "__pycache__/\n*.pyc\nscripts/dispositivo.txt\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "x")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "base")
    return tmp_path


def _chave(raiz: Path, entradas: list[str]) -> str | None:
    ent = RECIBO.Entradas(raiz)
    return RECIBO.chave_do_portao(ent, "ambiente", "um-portao", "pytest", "", entradas)


def _escreve_bytecode(raiz: Path) -> None:
    for pasta in ("src/pacote", "scripts"):
        alvo = raiz / pasta / "__pycache__"
        alvo.mkdir(exist_ok=True)
        (alvo / "x.cpython-312.pyc").write_bytes(b"\x00bytecode novo")


@pytest.mark.parametrize(
    "entradas", ([], ["src/**", "scripts/**"], ["src/pacote/*.py", "scripts/*"]),
    ids=("sem-quinta-coluna", "globs-largos", "globs-do-py-e-do-resto"))
def test_o_bytecode_escrito_durante_a_corrida_nao_muda_a_chave(
        arvore: Path, entradas: list[str]) -> None:
    antes = _chave(arvore, entradas)
    assert antes, "o portão tem de poder ser lembrado"
    _escreve_bytecode(arvore)
    assert _chave(arvore, entradas) == antes, (
        "o `.pyc` que o próprio portão escreve mudou a chave: todo verde se descarta "
        "(«a árvore mudou durante a corrida») e a memória nunca lembra")


def test_o_fonte_ignorado_de_scripts_continua_na_chave(arvore: Path) -> None:
    """Só o bytecode sai: o resto do ignorado de `scripts/` segue entrando."""
    ausente = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("um\n", encoding="utf-8")
    um = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("dois\n", encoding="utf-8")
    assert len({ausente, um, _chave(arvore, [])}) == 3


def test_o_py_mudado_continua_mudando_a_chave(arvore: Path) -> None:
    antes = _chave(arvore, ["src/**"])
    (arvore / "src/pacote/a.py").write_text("a = 2\n", encoding="utf-8")
    assert _chave(arvore, ["src/**"]) != antes


def test_mordida_com_o_bytecode_devolvido_a_chave_a_chave_muda(
        arvore: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RECIBO, "_BYTECODE", re.compile(r"(?!x)x"))
    antes = _chave(arvore, ["src/**", "scripts/**"])
    _escreve_bytecode(arvore)
    assert _chave(arvore, ["src/**", "scripts/**"]) != antes, (
        "a mordida não mordeu: com o bytecode na chave, o `.pyc` novo tinha de mudá-la")


# --- o ci-local lê a tabela e os workflows UMA vez ------------------------------------------------

CI_LOCAL = RAIZ / "scripts" / "ci-local.sh"


def _awks_da_corrida(tmp_path: Path, *args: str, script: Path = CI_LOCAL) -> int:
    """Quantos `awk` o script cria numa corrida: um `awk` de mentira os conta e passa adiante."""
    import os
    import shutil

    awk_real = shutil.which("awk")
    assert awk_real
    pasta = tmp_path / "shim"
    pasta.mkdir()
    registro = tmp_path / "awk.log"
    registro.write_text("")
    contador = pasta / "awk"
    contador.write_text(f'#!/bin/bash\necho x >> "{registro}"\nexec {awk_real} "$@"\n')
    contador.chmod(0o755)
    env = {**os.environ, "PATH": f"{pasta}{os.pathsep}{os.environ['PATH']}"}
    feito = subprocess.run(["bash", str(script), *args], capture_output=True, text=True,
                           env=env, check=False, timeout=60)
    assert feito.returncode in (0, 1), feito.stderr
    return len(registro.read_text().splitlines())


# A tabela da casa tem dezenas de jobs. Lida uma vez, a conferência gasta ~23 `awk` e o preço não
# cresce com a tabela; relida a cada pergunta, eram 749 (0,8 s só para listar) e crescia com ela.
TETO_DE_AWK = 60


@pytest.mark.parametrize("args", (["--listar"], ["--rapido", "--conferir"]),
                         ids=("listar", "conferir-rapido"))
def test_o_ci_de_casa_le_a_tabela_e_os_workflows_uma_vez(tmp_path: Path, args: list[str]) -> None:
    quantos = _awks_da_corrida(tmp_path, *args)
    assert 0 < quantos <= TETO_DE_AWK, (
        f"o ci-local criou {quantos} `awk` (teto {TETO_DE_AWK}): a tabela ou os workflows "
        "voltaram a ser relidos a cada pergunta")


def test_mordida_o_ci_de_casa_que_rele_a_cada_pergunta_estoura_o_teto(tmp_path: Path) -> None:
    """A versão de antes da cura (cada pergunta relê os workflows) tem de passar do teto."""
    texto = CI_LOCAL.read_text(encoding="utf-8")
    trocas = (
        ('jobs_do_yaml() { [ -z "$_JOBS_YAML" ] || printf \'%s\\n\' "$_JOBS_YAML"; }',
         "jobs_do_yaml() { _jobs_do_yaml_lidos; }"),
        ('arquivo_do_job() { [ -z "${ARQUIVO_DO_JOB[$1]:-}" ] || printf \'%s\\n\' '
         '"${ARQUIVO_DO_JOB[$1]}"; }',
         "arquivo_do_job() { jobs_do_yaml | awk -v j=\"$1\" '$2==j {print $1; exit}'; }"),
        ('[ "$tipo" = EM-TAG ] || [ -n "${ARQUIVO_DO_JOB[$j]:-}" ]',
         '[ "$tipo" = EM-TAG ] || jobs_do_yaml | awk -v j="$j" \'$2==j {ok=1} END{exit !ok}\''),
    )
    torto = texto
    for antes, depois in trocas:
        assert antes in torto, antes
        torto = torto.replace(antes, depois)
    raiz = tmp_path / "raiz"  # o script acha a raiz pelo próprio caminho: uma raiz de mentira
    (raiz / "scripts").mkdir(parents=True)
    (raiz / ".github").symlink_to(RAIZ / ".github")
    (raiz / "scripts" / "ci-local").symlink_to(RAIZ / "scripts" / "ci-local")
    copia = raiz / "scripts" / "ci-local.sh"
    copia.write_text(torto, encoding="utf-8")
    quantos = _awks_da_corrida(tmp_path, "--listar", script=copia)
    assert quantos > TETO_DE_AWK, f"a mordida não mordeu: só {quantos} `awk` sem a cura"
