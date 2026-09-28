"""O segfault da suíte diz onde morreu (VERDE-NAO-E-PROVA-01, passo 4).

Em 26/09/2026 uma parte da suíte morreu com `rc=139` (o WebKit no lote) e
nenhum log tinha a pilha. A Python vem do `faulthandler` (o pytest o liga, e o
`tests/conftest.py` põe `PYTHONFAULTHANDLER=1` para os filhos); a nativa, de
`scripts/pilha_nativa.c`, que o `scripts/rodar-a-suite.sh` carrega em todo
pytest; e cada arquivo do WebKit roda em processo próprio. O processo que
morre de propósito se declara não despejável antes do sinal: o apport dorme.

AS MORDIDAS: tire o `PYTHONFAULTHANDLER` do conftest, e a régua do filho
reprova; troque a `saida` da `pilha_nativa.c` pelo `STDERR_FILENO`, e as duas
da pilha reprovam (a captura do pytest engole o texto); tire o `LD_PRELOAD` ou
o processo próprio do `rodar-a-suite.sh`, e a da suíte de brinquedo reprova;
tire o dígito da classe do nome ou o fecho dos imports, e a da árvore de
verdade reprova (o pacote é `hefesto_dualsense4unix`, e o brinquedo também
tem dígito); leia o sumário pela última linha do log, e o que morre ao sair
vira «SEM SUMÁRIO».
"""
from __future__ import annotations

import ast
import faulthandler
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "scripts" / "pilha_nativa.c"
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

#: O processo que morre de propósito: não despejável, sem apport.
_MORRE = (
    "import ctypes, os, signal\n"
    "ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)\n"
    "os.kill(os.getpid(), signal.SIGSEGV)\n"
)


def _ambiente(**mais: str) -> dict[str, str]:
    """O ambiente do filho, sem as opções e o `LD_PRELOAD` de quem chama."""
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", **mais})
    return env


def _compilada(pasta: Path) -> Path:
    if shutil.which("cc") is None:
        pytest.skip("sem compilador C nesta máquina: a suíte sai só com a pilha Python")
    alvo = pasta / "pilha-nativa.so"
    feito = subprocess.run(
        ["cc", "-shared", "-fPIC", "-O1", "-o", str(alvo), str(FONTE), "-ldl"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert feito.returncode == 0, feito.stderr
    return alvo


def test_o_processo_da_suite_tem_o_faulthandler_ligado() -> None:
    assert faulthandler.is_enabled(), (
        "o pytest roda sem o faulthandler (alguém passou `-p no:faulthandler`?): "
        "um segfault na suíte volta a morrer sem pilha")


def test_o_python_filho_herda_o_faulthandler() -> None:
    filho = subprocess.run(
        [sys.executable, "-c", "import faulthandler; print(faulthandler.is_enabled())"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert filho.returncode == 0, filho.stderr
    assert filho.stdout.strip() == "True", (
        "o Python que a suíte dispara nasce sem o faulthandler: o conftest "
        "deixou de pôr `PYTHONFAULTHANDLER=1` no ambiente, e o próximo `rc=139` "
        "de um filho Python morre sem dizer onde")


def test_a_pilha_nativa_sai_mesmo_com_o_stderr_desviado(tmp_path: Path) -> None:
    """O pytest desvia o fd 2 durante o teste; a pilha sai no stderr de nascença."""
    biblioteca = _compilada(tmp_path)
    codigo = (
        "import os\n"
        "print('LD_PRELOAD=' + repr(os.environ.get('LD_PRELOAD')), flush=True)\n"
        "os.dup2(os.open(os.devnull, os.O_WRONLY), 2)\n" + _MORRE
    )
    filho = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
        check=False, env=_ambiente(LD_PRELOAD=str(biblioteca)),
    )
    assert filho.returncode == -11, filho.stdout + filho.stderr
    assert "LD_PRELOAD=None" in filho.stdout, (
        "a biblioteca ficou no ambiente do processo: os filhos dele herdariam o "
        "tratador\n" + filho.stdout)
    assert "pilha nativa: sinal 11" in filho.stderr, filho.stderr
    assert "pilha nativa: a linha que recebeu o sinal" in filho.stderr, filho.stderr
    assert "libc.so" in filho.stderr, "a pilha saiu sem nenhum quadro:\n" + filho.stderr


def test_o_arquivo_do_webkit_morre_sozinho_e_diz_onde(tmp_path: Path) -> None:
    """A suíte de brinquedo: um arquivo comum, dois do WebKit que morrem (um no
    meio, um ao sair), um que pula inteiro e dois que só importam o piloto, um
    direto e um pela ponte. O pacote tem dígito no nome, como o de verdade."""
    _compilada(tmp_path)
    raiz = tmp_path / "arvore"
    for pasta in ("scripts", "tests/unit", "src/pacote4unix"):
        (raiz / pasta).mkdir(parents=True)
    shutil.copy(SUITE, raiz / "scripts" / SUITE.name)
    shutil.copy(FONTE, raiz / "scripts" / FONTE.name)
    (raiz / "src" / "pacote4unix" / "piloto.py").write_text(
        'import gi\ngi.require_version("WebKit2", "4.1")\n', encoding="utf-8")
    (raiz / "src" / "pacote4unix" / "ponte.py").write_text(
        "from pacote4unix import piloto  # noqa: F401\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_a_comum.py").write_text(
        "def test_passa():\n    assert True\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_b_morre.py").write_text(
        "# a régua do WebKit2 de mentira\n\n\ndef test_morre():\n"
        + "".join(f"    {linha}\n" for linha in _MORRE.splitlines()), encoding="utf-8")
    (raiz / "tests" / "unit" / "test_d_pula.py").write_text(
        "import pytest\n\n# WebKit2 ausente nesta máquina\npytest.skip('sem o WebKit', "
        "allow_module_level=True)\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_c_piloto.py").write_text(
        "def test_so_cita():\n    if False:\n"
        "        from pacote4unix import piloto  # noqa: F401\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_e_ponte.py").write_text(
        "def test_so_cita_a_ponte():\n    if False:\n"
        "        from pacote4unix import ponte  # noqa: F401\n", encoding="utf-8")
    (raiz / "tests" / "unit" / "test_f_morre_ao_sair.py").write_text(
        "# o WebKit2 de mentira, que morre depois do sumário\nimport atexit\n\n\n"
        "def _morrer():\n" + "".join(f"    {linha}\n" for linha in _MORRE.splitlines())
        + "\n\ndef test_passa_e_morre_ao_sair():\n    atexit.register(_morrer)\n",
        encoding="utf-8")
    saida = tmp_path / "saida"

    feito = subprocess.run(
        ["bash", "scripts/rodar-a-suite.sh", "00"], cwd=raiz, capture_output=True, text=True,
        timeout=300, check=False,
        env=_ambiente(PY=sys.executable, PARTES="1", SAIDA=str(saida)),
    )
    texto = feito.stdout + feito.stderr

    assert feito.returncode == 1, texto
    linhas = {linha.strip().split(":", 1)[0]: linha for linha in feito.stdout.splitlines()}
    assert "1 passed" in linhas.get("parte-00 (6 arq)", ""), (
        "o arquivo comum não sobreviveu ao sinal do vizinho:\n" + texto)
    assert "MORREU PELO SINAL 11" in linhas.get("test_b_morre, em processo próprio", ""), texto
    assert "1 passed" in linhas.get("test_c_piloto, em processo próprio", ""), (
        "o arquivo que importa um módulo do WebKit não rodou sozinho:\n" + texto)
    assert "1 passed" in linhas.get("test_e_ponte, em processo próprio", ""), (
        "o arquivo que carrega o WebKit por um módulo do meio não rodou sozinho:\n" + texto)
    pulo = linhas.get("test_d_pula, em processo próprio", "")
    assert "1 skipped" in pulo and "SEM SUMÁRIO" not in pulo, (
        "o arquivo que pula inteiro (rc=5) foi lido como processo morto:\n" + texto)
    ao_sair = linhas.get("test_f_morre_ao_sair, em processo próprio", "")
    assert "1 passed" in ao_sair and "MORREU PELO SINAL 11" in ao_sair, (
        "o arquivo que morre depois do sumário perdeu o sumário ou o sinal:\n" + texto)
    log = (saida / "parte-00-test_b_morre.log").read_text(encoding="utf-8")
    assert "Fatal Python error: Segmentation fault" in log, log
    assert "pilha nativa: a linha que recebeu o sinal" in log, (
        "o log de quem morreu não tem a pilha nativa:\n" + log)


def _topo(arvore: ast.Module) -> list[ast.stmt]:
    """Os comandos que rodam ao importar: o corpo, descendo em `if` e `try`."""
    fila, topo = list(arvore.body), []
    while fila:
        no = fila.pop()
        topo.append(no)
        if isinstance(no, (ast.If, ast.Try)):
            fila += no.body + no.orelse
        if isinstance(no, ast.Try):
            fila += no.finalbody + [c for h in no.handlers for c in h.body]
    return topo


def _importados(nos: list[ast.stmt] | list[ast.AST], modulo: str = "") -> set[str]:
    nomes: set[str] = set()
    for no in nos:
        if isinstance(no, ast.Import):
            nomes |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            if no.level:
                pai = modulo.split(".")[: -no.level]
                base = ".".join(pai + ([base] if base else []))
            nomes |= {base} | {f"{base}.{a.name}" for a in no.names}
    return nomes


def _carregam_o_webkit() -> set[str]:
    """Os arquivos de teste que importam um módulo que carrega o WebKit ao ser
    importado, pelo AST: o método é outro que o do runner, de propósito."""
    modulos: dict[str, ast.Module] = {}
    for caminho in sorted((RAIZ / "src").rglob("*.py")) + sorted((RAIZ / "scripts").rglob("*.py")):
        partes = list(caminho.relative_to(RAIZ / "src").with_suffix("").parts
                      if caminho.is_relative_to(RAIZ / "src") else [caminho.stem])
        if partes[-1] == "__init__":
            partes.pop()
        try:
            modulos[".".join(partes)] = ast.parse(caminho.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
    fecho = {m for m, a in modulos.items() if any(
        isinstance(n, ast.ImportFrom) and n.module == "gi.repository"
        and any(x.name == "WebKit2" for x in n.names) for n in _topo(a))}
    importa = {m: _importados(_topo(a), m) for m, a in modulos.items()}

    def alcanca(nomes: set[str]) -> bool:
        prefixos = {".".join(n.split(".")[:k]) for n in nomes for k in range(1, n.count(".") + 2)}
        return bool(prefixos & fecho)

    while novos := {m for m in modulos if m not in fecho and alcanca(importa[m] | {m})}:
        fecho |= novos
    folhas = {m.rsplit(".", 1)[-1] for m in fecho}
    achados = set()
    for teste in (RAIZ / "tests" / "unit").glob("test_*.py"):
        nomes = _importados(list(ast.walk(ast.parse(teste.read_text(encoding="utf-8")))))
        if alcanca(nomes) or nomes & folhas:
            achados.add(teste.relative_to(RAIZ).as_posix())
    return achados


def test_todo_arquivo_que_carrega_o_webkit_roda_sozinho(tmp_path: Path) -> None:
    """A árvore de verdade: o runner diz quem roda em processo próprio, e o AST confere."""
    feito = subprocess.run(
        ["bash", str(SUITE)], cwd=RAIZ, capture_output=True, text=True, timeout=300,
        check=False, env=_ambiente(PY=sys.executable, SAIDA=str(tmp_path / "saida"),
                                   LISTAR_O_WEBKIT="1"),
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    sozinhos = set(feito.stdout.split())
    esperados = _carregam_o_webkit()
    assert len(esperados) >= 20, f"o AST achou só {len(esperados)}: a régua ficou cega"
    faltam = sorted(esperados - sozinhos)
    assert not faltam, (
        "carregam o WebKit e rodariam no processo da parte:\n  " + "\n  ".join(faltam))
