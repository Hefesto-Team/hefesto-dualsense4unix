"""O INSTALL DIZ O ERRO REAL DO PIP (O-INSTALL-DIZ-O-ERRO-REAL-DO-PIP-01).

O `pip install` do pacote mandava o stderr para `/dev/null` e toda falha virava «verifique a
conexão». O trecho do `install.sh` roda aqui de verdade, com um `pip` de mentira que falha de três
jeitos, e exige uma frase diferente para cada, o código de saída diferente de zero, o caminho do
registro na tela, as últimas linhas do pip e o registro inteiro em arquivo. A atualização do pip
e do `packaging` é melhor esforço: falhou, avisa e segue.

MORDIDAS (25/11/2026): devolver o `2>/dev/null` ao `pip install` do pacote reprova a falha de
compilação e a de conflito (a frase de rede serve às duas); tirar o `if !` da atualização do pip
reprova o caso em que a atualização falha e o install segue.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FONTE = (RAIZ / "install.sh").read_text(encoding="utf-8")

SAIDAS = {
    "rede": (
        "WARNING: Retrying (Retry(total=0)) after connection broken by "
        "'NewConnectionError: Failed to establish a new connection: "
        "[Errno -3] Temporary failure in name resolution'\n"
        "ERROR: Could not find a version that satisfies the requirement evdev\n"
        "ERROR: No matching distribution found for evdev\n"),
    "compilacao": (
        "    evdev/input.c:12:10: fatal error: Python.h: No such file or directory\n"
        "    error: command '/usr/bin/x86_64-linux-gnu-gcc' failed with exit code 1\n"
        "ERROR: Failed building wheel for evdev\n"),
    "conflito": (
        "ERROR: Cannot install hefesto and numpy==1.0 because these package versions have "
        "conflicting dependencies.\n"
        "ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/\n"),
}
FRASES = {
    "rede": "falta de rede",
    "compilacao": "ao compilar uma biblioteca",
    "conflito": "versões em conflito",
}


def _o_trecho() -> str:
    inicio = FONTE.index('_extras="emulation,cosmic"')
    fim = FONTE.index('step "3/11"', inicio)
    return FONTE[inicio:fim]


def _rodar(tmp_path: pathlib.Path, *, saida_do_pip: str = "", pip_falha: bool = False,
           atualizacao_falha: bool = False, dev: bool = False,
           ensaio: bool = False, so_a_primeira: bool = False) -> subprocess.CompletedProcess[str]:
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (tmp_path / "saida-do-pip").write_text(saida_do_pip, encoding="utf-8")
    pip = venv / "bin" / "pip"
    pip.write_text(
        "#!/bin/bash\n"
        f"touch {tmp_path / 'chamadas-do-pip'}\n"
        f"antes=$(wc -l < {tmp_path / 'chamadas-do-pip'})\n"
        f"echo \"$*\" >> {tmp_path / 'chamadas-do-pip'}\n"
        f"[ {1 if so_a_primeira else 0} -eq 0 ] || [ \"$antes\" -eq 0 ] || exit 0\n"
        f"cat {tmp_path / 'saida-do-pip'} >&2\n"
        f"exit {1 if pip_falha else 0}\n", encoding="utf-8")
    python = venv / "bin" / "python"
    python.write_text(
        "#!/bin/bash\n"
        "echo 'ERROR: o índice não respondeu' >&2\n"
        f"exit {1 if atualizacao_falha else 0}\n", encoding="utf-8")
    pip.chmod(0o755)
    python.chmod(0o755)
    roteiro = (
        "set -euo pipefail\n"
        "warn()  { printf '      aviso: %s\\n' \"$*\"; }\n"
        "die()   { printf '\\nERRO: %s\\n' \"$*\" >&2; exit 1; }\n"
        "ok()    { printf '      ok\\n'; }\n"
        f"DRY_RUN={1 if ensaio else 0}\nWITH_DEV={1 if dev else 0}\n"
        "_faria() { echo \"FARIA $*\"; }\n"
        f"{_o_trecho()}\n"
        "echo SEGUIU\n")
    ambiente = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "casa"),
                "XDG_STATE_HOME": str(tmp_path / "estado"),
                "XDG_CACHE_HOME": str(tmp_path / "cache"),
                "VENV_DIR": str(venv), "ROOT_DIR": str(tmp_path / "raiz")}
    return subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True,
                          timeout=30, check=False)


def _registro(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "estado" / "hefesto-dualsense4unix" / "install-pip.log"


@pytest.mark.parametrize("causa", sorted(SAIDAS))
@pytest.mark.parametrize("dev", [False, True])
def test_cada_falha_do_pip_diz_a_sua_causa(tmp_path: pathlib.Path, causa: str, dev: bool) -> None:
    feito = _rodar(tmp_path, saida_do_pip=SAIDAS[causa], pip_falha=True, dev=dev)
    tela = feito.stdout + feito.stderr
    assert feito.returncode != 0, tela
    assert "SEGUIU" not in tela
    assert FRASES[causa] in tela, tela
    for outra, frase in FRASES.items():
        if outra != causa:
            assert frase not in tela, f"a frase de {outra} apareceu na falha de {causa}:\n{tela}"
    assert str(_registro(tmp_path)) in tela, tela
    ultima = SAIDAS[causa].strip().splitlines()[-1]
    assert ultima in tela, "as últimas linhas do pip não chegaram à tela"
    assert _registro(tmp_path).read_text(encoding="utf-8") == SAIDAS[causa]


def test_a_falha_sem_causa_conhecida_diz_so_o_registro(tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, saida_do_pip="ERROR: algo que ninguem previu\n", pip_falha=True)
    tela = feito.stdout + feito.stderr
    assert feito.returncode != 0
    assert "pip install do pacote falhou;" in tela
    assert "falta de rede" not in tela and "verifique a conexão" not in tela
    assert str(_registro(tmp_path)) in tela


def test_sem_onde_gravar_o_registro_a_falha_ainda_diz_a_frase(tmp_path: pathlib.Path) -> None:
    (tmp_path / "estado").write_text("um arquivo no lugar da pasta\n", encoding="utf-8")
    feito = _rodar(tmp_path, saida_do_pip=SAIDAS["rede"], pip_falha=True)
    tela = feito.stdout + feito.stderr
    assert feito.returncode != 0, tela
    assert "SEGUIU" not in tela
    assert "pip install do pacote falhou" in tela, tela


def test_com_o_dev_falhando_e_o_essencial_passando_o_install_segue(
        tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, saida_do_pip=SAIDAS["conflito"], pip_falha=True, dev=True,
                   so_a_primeira=True)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "SEGUIU" in feito.stdout
    assert "pip install com [dev] falhou" in feito.stdout
    chamadas = (tmp_path / "chamadas-do-pip").read_text(encoding="utf-8").splitlines()
    assert len(chamadas) == 2


def test_a_atualizacao_do_pip_que_falha_avisa_e_o_install_segue(tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, atualizacao_falha=True)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "SEGUIU" in feito.stdout
    assert "não consegui atualizar o pip e o packaging" in feito.stdout
    registro = tmp_path / "estado" / "hefesto-dualsense4unix" / "install-pip-atualizacao.log"
    assert "o índice não respondeu" in registro.read_text(encoding="utf-8")
    assert str(registro) in feito.stdout


def test_o_ensaio_nao_roda_o_pip_nem_escreve_registro(tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, pip_falha=True, ensaio=True)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert not (tmp_path / "chamadas-do-pip").exists()
    assert not (tmp_path / "estado").exists()


def test_nenhum_pip_do_install_manda_o_erro_para_o_nada() -> None:
    soltas = [
        linha for linha in FONTE.splitlines()
        if ("pip install" in linha or "-m pip" in linha or "/bin/pip" in linha)
        and "/dev/null" in linha
    ]
    assert soltas == []
