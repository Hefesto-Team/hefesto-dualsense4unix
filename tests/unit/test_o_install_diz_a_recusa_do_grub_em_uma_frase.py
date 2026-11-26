"""O INSTALL DIZ A RECUSA DO GRUB EM UMA FRASE (O-INSTALL-DIZ-A-RECUSA-DO-GRUB-EM-UMA-FRASE-01).

O passo 3e lia o carregador sem capturar `GrubNaoEntendidoError`: a recusa (a linha do grub que o
passo não sabe reescrever) chegava à tela como `Traceback`, e o install só dizia «o plano do cmdline
não saiu». O bloco do `install.sh` roda aqui de verdade, com os três caminhos do carregador
trocados por arquivos do teste (a única diferença do bloco real), e exige uma frase com a linha
recusada, nenhum `Traceback` na tela e o install seguindo. O erro que ninguém previu também não
chega à tela: o `Traceback` vai para o registro do install, e a frase diz onde ele está.

MORDIDAS (25/11/2026): tirar o `try`/`except` do heredoc devolve o `Traceback` à tela e a frase
some; trocar o `2>"${_cmdline_log}"` por nada devolve o `Traceback` do erro imprevisto à tela.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FONTE = (RAIZ / "install.sh").read_text(encoding="utf-8")


def _o_passo(tmp_path: pathlib.Path) -> str:
    inicio = FONTE.index('if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v python3')
    fim = FONTE.index('step "3e-trava"', inicio)
    passo = FONTE[inicio:fim]
    for original, troca in (
        ('Path("/etc/kernelstub/configuration")', f'Path("{tmp_path}/kernelstub")'),
        ('Path("/etc/default/grub")', f'Path("{tmp_path}/grub")'),
        ('Path("/etc/kernel/cmdline")', f'Path("{tmp_path}/cmdline")'),
    ):
        assert original in passo
        passo = passo.replace(original, troca)
    return passo


def _rodar(tmp_path: pathlib.Path, grub: str, *, ensaio: bool = False,
           raiz: pathlib.Path = RAIZ) -> subprocess.CompletedProcess[str]:
    (tmp_path / "grub").write_text(grub, encoding="utf-8")
    roteiro = (
        "set -euo pipefail\n"
        f"ROOT_DIR={raiz}\n"
        "step() { :; }\n"
        "warn() { printf '      aviso: %s\\n' \"$*\"; }\n"
        "_desempenho_tem_bateria() { return 1; }\n"
        "_register_cmdline_owner() { :; }\n"
        "_faria_root() { echo \"FARIA_ROOT $*\"; }\n"
        "anotar_reinicio_pendente() { :; }\n"
        "CMDLINE_OWNERS_FILE=/dev/null\n_PENDENTE_DO_CMDLINE=x\n"
        f"DRY_RUN={1 if ensaio else 0}\nSKIP_UDEV=0\n"
        f"_ESTADO_DO_INSTALL={tmp_path / 'estado'}\n"
        f"{_o_passo(tmp_path)}\n"
        "echo SEGUIU\n")
    ambiente = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "casa"),
                "ROOT_DIR": str(raiz)}
    return subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True,
                          timeout=60, check=False)


@pytest.mark.parametrize("linha,trecho", [
    ('GRUB_CMDLINE_LINUX_DEFAULT="$(cat /etc/x) quiet"', "forma que eu não sei reescrever"),
    ('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash', "aspas sem par na linha do grub"),
])
def test_a_recusa_do_grub_sai_numa_frase_e_sem_traceback(
        tmp_path: pathlib.Path, linha: str, trecho: str) -> None:
    feito = _rodar(tmp_path, f"{linha}\n")
    tela = feito.stdout + feito.stderr
    assert feito.returncode == 0, tela
    assert "SEGUIU" in tela
    assert "Traceback" not in tela and "GrubNaoEntendidoError" not in tela, tela
    assert "cmdline: o grub não foi tocado" in tela, tela
    assert trecho in tela and linha.strip() in tela, tela
    assert "o plano do cmdline não saiu" not in tela


def test_o_grub_que_o_install_entende_segue_sem_recusa(tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n', ensaio=True)
    tela = feito.stdout + feito.stderr
    assert feito.returncode == 0, tela
    assert "o grub não foi tocado" not in tela
    assert "Traceback" not in tela


def _arvore_que_quebra(tmp_path: pathlib.Path) -> pathlib.Path:
    """Uma árvore cujo `kernel_cmdline` levanta um erro que ninguém previu ao ser importado."""
    modulo = tmp_path / "arvore" / "src" / "hefesto_dualsense4unix" / "integrations"
    modulo.mkdir(parents=True)
    (modulo.parent / "__init__.py").write_text("", encoding="utf-8")
    (modulo / "__init__.py").write_text("", encoding="utf-8")
    (modulo / "kernel_cmdline.py").write_text("raise RuntimeError('estouro de mentira')\n",
                                              encoding="utf-8")
    return tmp_path / "arvore"


def test_o_erro_que_ninguem_previu_vai_para_o_registro_e_nao_para_a_tela(
        tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n',
                   raiz=_arvore_que_quebra(tmp_path))
    tela = feito.stdout + feito.stderr
    registro = tmp_path / "estado" / "install-cmdline.log"
    assert feito.returncode == 0, tela
    assert "Traceback" not in tela, tela
    assert "o plano do cmdline não saiu" in tela and str(registro) in tela, tela
    assert "estouro de mentira" in registro.read_text(encoding="utf-8")


def test_o_ensaio_nao_escreve_o_registro(tmp_path: pathlib.Path) -> None:
    feito = _rodar(tmp_path, 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n',
                   raiz=_arvore_que_quebra(tmp_path), ensaio=True)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "Traceback" not in feito.stdout + feito.stderr
    assert "o plano do cmdline não saiu" in feito.stdout and "(nada registrado)" in feito.stdout
    assert "o motivo está em" not in feito.stdout
    assert not (tmp_path / "estado").exists()
