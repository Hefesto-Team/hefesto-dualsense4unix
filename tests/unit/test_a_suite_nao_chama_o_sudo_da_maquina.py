"""A-SUITE-NAO-CHAMA-O-SUDO-DA-MAQUINA-01 — o `sudo` de todo teste é o de mentira."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from tests import conftest

RAIZ = Path(__file__).resolve().parents[2]
SIGLA = "A-SUITE-NAO-CHAMA-O-SUDO-DA-MAQUINA-01"

_SEM_DUBLE = '''
import subprocess

PATH_DE_FORA = {path!r}


def test_chama_o_sudo():
    subprocess.run(["sudo", "-n", "true"], check=False)


def test_chama_o_sudo_sem_o_ambiente():
    subprocess.run(["sudo", "-n", "-l"], env={{"PATH": PATH_DE_FORA}}, check=False)
'''

_COM_DUBLE = '''
import os
import subprocess


def test_o_duble_do_proprio_teste_vence(tmp_path, monkeypatch):
    sudo = tmp_path / "sudo"
    sudo.write_text("#!/bin/sh\\nexit 0\\n", encoding="utf-8")
    sudo.chmod(0o755)
    monkeypatch.setenv("PATH", f"{{tmp_path}}:{{os.environ['PATH']}}")
    assert subprocess.run(["sudo", "-n", "true"], check=False).returncode == 0


def test_o_ato_declarado_de_proposito_passa(ato_de_proposito):
    with ato_de_proposito("sudo -n true"):
        assert subprocess.run(["sudo", "-n", "true"], check=False).returncode == 1
'''


def _rodar_o_ninho(
    tmp_path: Path, nome: str, corpo: str, **ambiente_extra: str
) -> subprocess.CompletedProcess[str]:
    """Um pytest em subprocesso com a guarda desta árvore."""
    quintal = tmp_path / nome
    quintal.mkdir()
    (quintal / "conftest.py").symlink_to(RAIZ / "tests" / "conftest.py")
    (quintal / f"test_{nome}.py").write_text(
        textwrap.dedent(corpo).format(path=os.environ["PATH"]), encoding="utf-8"
    )
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    ambiente["PYTEST_ADDOPTS"] = ""
    ambiente["HEFESTO_SEM_CANARIO_FS"] = "1"
    ambiente.pop(conftest._SUDO_REGISTRO_ENV, None)
    ambiente.update(ambiente_extra)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"],
        cwd=str(quintal), env=ambiente, capture_output=True, text=True, timeout=300,
    )


def test_o_sudo_de_mentira_esta_na_frente_do_path_da_suite() -> None:
    """O primeiro `sudo` que o PATH acha é o dublê, e ele recusa sem tocar a máquina."""
    duble = conftest.lancador_de_mentira()
    assert duble is not None, "a sessão não armou os dublês: o `sudo` da máquina está à mostra"
    assert "sudo" in conftest.BINARIOS_DE_LANCADOR
    achado = subprocess.run(
        ["/bin/sh", "-c", "command -v sudo"], capture_output=True, text=True, check=False
    ).stdout.strip()
    assert achado == str(duble / "sudo"), f"o `sudo` que o PATH acha é {achado}"


def test_o_teste_que_chama_o_sudo_sem_duble_reprova_com_a_frase(tmp_path: Path) -> None:
    """Os dois testes de dentro terminam FAILED, com a sigla, o nodeid e o argv."""
    saida = _rodar_o_ninho(tmp_path, "sem_duble", _SEM_DUBLE)
    texto = saida.stdout + saida.stderr
    assert saida.returncode == 1, f"rc={saida.returncode}\n{texto[-3000:]}"
    for teste, argv in (
        ("test_chama_o_sudo", "sudo -n true"),
        ("test_chama_o_sudo_sem_o_ambiente", "sudo -n -l"),
    ):
        nodeid = f"test_sem_duble.py::{teste}"
        assert re.search(rf"^FAILED {re.escape(nodeid)}\b", texto, re.M), (
            f"{nodeid} não reprovou:\n{texto[-3000:]}"
        )
        assert f"{SIGLA}: este teste ({nodeid}, fase call)" in texto, texto[-3000:]
        assert f"`{argv}`" in texto, texto[-3000:]
    assert "FORA de qualquer teste" not in texto, texto[-3000:]


def test_o_duble_do_proprio_teste_e_o_ato_declarado_passam(tmp_path: Path) -> None:
    saida = _rodar_o_ninho(tmp_path, "com_duble", _COM_DUBLE)
    texto = saida.stdout + saida.stderr
    assert saida.returncode == 0 and "2 passed" in texto, texto[-3000:]


def test_o_modo_de_registro_anota_o_teste_e_o_argv_sem_reprovar(tmp_path: Path) -> None:
    registro = tmp_path / "registro.tsv"
    registro.touch()
    saida = _rodar_o_ninho(
        tmp_path, "registrado", _SEM_DUBLE, **{conftest._SUDO_REGISTRO_ENV: str(registro)}
    )
    texto = saida.stdout + saida.stderr
    assert saida.returncode == 0 and "2 passed" in texto, texto[-3000:]
    assert sorted(registro.read_text(encoding="utf-8").splitlines()) == [
        "test_registrado.py::test_chama_o_sudo\tsudo -n true",
        "test_registrado.py::test_chama_o_sudo_sem_o_ambiente\tsudo -n -l",
    ]


def _o_que_a_suite_executa() -> list[Path]:
    """Todo arquivo que um teste pode executar: o pacote, os scripts, os testes, os assets,
    o empacotamento e os instaladores da raiz."""
    arquivos = [RAIZ / nome for nome in ("install.sh", "uninstall.sh", "run.sh")]
    for pasta in ("src", "scripts", "tests", "assets", "packaging", "flatpak"):
        arquivos.extend(a for a in (RAIZ / pasta).rglob("*") if a.is_file())
    return [a for a in arquivos if a.is_file() and "__pycache__" not in a.parts]


def test_ninguem_chama_o_sudo_por_caminho_absoluto() -> None:
    """O limite do dublê: o `Popen` da sessão troca até `/usr/bin/sudo`, mas o shell, o neto
    e o `exec` que levam o caminho absoluto escapam dele. Hoje nenhum arquivo o leva. O outro
    limite, que esta régua não vê: o neto de um `env` sem `PATH` acha o `sudo` pelo `PATH`
    padrão do shell dele."""
    este = Path(__file__).resolve()
    achados = []
    for arquivo in _o_que_a_suite_executa():
        if arquivo.resolve() == este:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if re.search(r"/(?:usr/)?(?:local/)?s?bin/sudo\b", texto):
            achados.append(str(arquivo.relative_to(RAIZ)))
    assert not achados, (
        f"{SIGLA}: estes arquivos chamam o `sudo` por caminho absoluto, e o dublê da "
        f"suíte não os alcança: {sorted(achados)}"
    )
