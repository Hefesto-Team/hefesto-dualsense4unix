"""O DKMS não gera par novo quando falta só o certificado (25/11/2026).

O-DKMS-NAO-GERA-PAR-NOVO-QUANDO-FALTA-SO-O-CERTIFICADO-01. Com o Secure Boot ligado, o DKMS 3.0.4
a 3.1.6 gera um par de chaves no ``autoinstall`` quando falta qualquer uma das duas peças, a
privada ou o certificado, e o par novo cobre a privada inscrita. A guarda do ``AUTOINSTALL``
(``preparar-o-fonte.py --sem-a-chave-privada``, o mesmo nos cinco pacotes) olhava só a privada.

Tudo de mentira: efivars, chaves e framework num lar de teste; a privada de teste é gerada aqui e
nenhum processo toca ``/var/lib/dkms``. Os pacotes servem todo modo e transporte (DualSense,
Nintendo, Wi-Fi USB, gadget): a guarda é a de cada um deles.

MORDIDA: com a guarda de volta a olhar só a privada, os casos sem o certificado reprovam.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_a_chave_privada_do_dkms import (
    KERNEL,
    _framework,
    _sem_kernel_da_maquina,
)
from tests.unit.test_dkms_lib import (
    CINCO_PREPARADORES,
    _estado_do_secure_boot,
    _sem_mokutil,
)

PRIVADA = b"CHAVE-PRIVADA-DE-MENTIRA"


def _pergunta(
        preparador: Path, raiz: Path, estado: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(preparador), "--sem-a-chave-privada", KERNEL],
        env={**os.environ, **estado, **_sem_kernel_da_maquina(raiz),
             "PATH": _sem_mokutil(estado, os.environ["PATH"])},
        capture_output=True, text=True, check=False, timeout=60)


def _lar(raiz: Path, *, privada: bool, certificado: bool, ligado: bool = True
         ) -> dict[str, str]:
    estado = _estado_do_secure_boot(raiz, ligado=ligado, inscrita=True, chave_privada=privada)
    if not certificado:
        (raiz / "mok.pub").unlink()
    return estado


@pytest.mark.parametrize("preparador", CINCO_PREPARADORES, ids=lambda p: p.parent.name)
def test_so_a_privada_a_guarda_responde_e_a_privada_fica_igual(
        tmp_path: Path, preparador: Path) -> None:
    estado = _lar(tmp_path, privada=True, certificado=False)
    antes = (tmp_path / "mok.key").read_bytes()
    feito = _pergunta(preparador, tmp_path, estado)
    assert feito.returncode == 0, feito
    assert "o certificado" in feito.stderr and "privada" not in feito.stderr, feito.stderr
    assert (tmp_path / "mok.key").read_bytes() == antes == PRIVADA


@pytest.mark.parametrize("preparador", CINCO_PREPARADORES, ids=lambda p: p.parent.name)
def test_so_o_certificado_a_guarda_responde_e_diz_a_privada(
        tmp_path: Path, preparador: Path) -> None:
    estado = _lar(tmp_path, privada=False, certificado=True)
    antes = (tmp_path / "mok.pub").read_bytes()
    feito = _pergunta(preparador, tmp_path, estado)
    assert feito.returncode == 0, feito
    assert "a chave privada" in feito.stderr and "certificado" not in feito.stderr, feito.stderr
    assert (tmp_path / "mok.pub").read_bytes() == antes


@pytest.mark.parametrize("preparador", CINCO_PREPARADORES, ids=lambda p: p.parent.name)
def test_sem_as_duas_a_saida_diz_as_duas(tmp_path: Path, preparador: Path) -> None:
    estado = _lar(tmp_path, privada=False, certificado=False)
    feito = _pergunta(preparador, tmp_path, estado)
    assert feito.returncode == 0, feito
    assert "a chave privada e o certificado" in feito.stderr, feito.stderr


def test_o_certificado_vazio_vale_como_ausente(tmp_path: Path) -> None:
    estado = _lar(tmp_path, privada=True, certificado=False)
    (tmp_path / "mok.pub").write_bytes(b"")
    feito = _pergunta(CINCO_PREPARADORES[0], tmp_path, estado)
    assert feito.returncode == 0 and "o certificado" in feito.stderr, feito


@pytest.mark.parametrize("preparador", CINCO_PREPARADORES, ids=lambda p: p.parent.name)
def test_o_par_inteiro_deixa_o_autoinstall_em_paz(tmp_path: Path, preparador: Path) -> None:
    estado = _lar(tmp_path, privada=True, certificado=True)
    feito = _pergunta(preparador, tmp_path, estado)
    assert feito.returncode == 1 and feito.stderr == "", feito


def test_sem_secure_boot_ou_com_a_privada_em_token_a_guarda_cala(tmp_path: Path) -> None:
    desligado = tmp_path / "desligado"
    desligado.mkdir()
    estado = _lar(desligado, privada=False, certificado=False, ligado=False)
    assert _pergunta(CINCO_PREPARADORES[0], desligado, estado).returncode == 1
    token = tmp_path / "token"
    token.mkdir()
    estado = _lar(token, privada=True, certificado=False)
    estado["HEFESTO_DKMS_FRAMEWORK_CONFS"] = _framework(token, "pkcs11:token=dkms")
    assert _pergunta(CINCO_PREPARADORES[0], token, estado).returncode == 1
