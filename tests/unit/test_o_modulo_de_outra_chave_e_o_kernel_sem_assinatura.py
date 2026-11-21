"""O módulo da casa assinado por OUTRA chave se refaz, e o kernel que não assina não faz laço.

Com o Secure Boot ligado e a chave do DKMS inscrita, a marca de assinatura no fim do módulo não
prova que a chave é a do DKMS de agora: depois de uma troca de chave o módulo instalado traz a marca
e o kernel o recusa. O número de série do certificado que assinou (``modinfo -F sig_key``, que o
kmod com libcrypto mostra para ``.ko``, ``.ko.xz`` e ``.ko.zst``, e o ``.ko.gz`` quando compilado
com zlib) se compara com o do certificado público do DKMS: só a diferença de certeza refaz, e
qualquer falha de leitura é «não sei», sem gesto.

Tudo de mentira: ``dkms``, ``mokutil``, ``modinfo``, ``sudo`` e ``uname`` no ``PATH`` do teste,
raízes de mentira, módulo de mentira e certificado montado byte a byte no próprio teste.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_dkms_lib import (
    KERNEL_DO_TESTE,
    TestModuloSemAssinaturaComAChaveInscrita,
    _estado_do_secure_boot,
    _roda,
)

SERIE_DA_CHAVE = bytes.fromhex("0a1b2c3d4e5f60718293a4b5c6d7e8f901234567")
SERIE_DE_OUTRA = bytes.fromhex("ffeeddccbbaa99887766554433221100aabbccdd")
FALHA_DE_REFAZER = ("dkms build", "dkms install")


def _tlv(tag: int, corpo: bytes) -> bytes:
    n = len(corpo)
    tamanho = bytes([n]) if n < 0x80 else b"\x82" + n.to_bytes(2, "big")
    return bytes([tag]) + tamanho + corpo


def _certificado(serie: bytes) -> bytes:
    """Um certificado X.509 mínimo em DER: só o que o leitor do número de série percorre."""
    inteiro = serie if serie[0] < 0x80 else b"\x00" + serie
    corpo = _tlv(0xA0, _tlv(0x02, b"\x02")) + _tlv(0x02, inteiro) + _tlv(0x30, b"")
    return _tlv(0x30, _tlv(0x30, corpo) + _tlv(0x30, b"") + _tlv(0x03, b"\x00"))


def _com_a_chave_de(raiz: Path, serie: bytes, *, inscrita: bool = True) -> dict[str, str]:
    estado = _estado_do_secure_boot(raiz, ligado=True, inscrita=inscrita)
    cert = _certificado(serie)
    (raiz / "mok.pub").write_bytes(cert)
    (raiz / "MokListRT").write_bytes(cert if inscrita else b"outra-chave")
    return estado


def _com_sig_key(valor: str, status: int = 0) -> dict[str, str]:
    return {"modinfo": f'case "$*" in *sig_key*) echo "{valor}"; exit {status};; esac\n'
                       'echo "$MODULO_DE_MENTIRA"'}


def _serie_do_modinfo(serie: bytes) -> str:
    return ":".join(f"{b:02X}" for b in serie)


class TestModuloAssinadoPorOutraChave:
    """O-O-MODULO-ASSINADO-POR-OUTRA-CHAVE-SE-REFAZ-SO-DE-CERTEZA-01.

    D-2111-O-MODULO-DE-OUTRA-CHAVE-SE-REFAZ-SO-DE-CERTEZA: com a chave inscrita e a privada
    presente, o módulo assinado por certificado diferente do do DKMS se refaz uma vez; qualquer
    falha de leitura do signatário deixa tudo como está.
    """

    def _instalar(
        self, tmp_path: Path, estado: dict[str, str], sig_key: str, *,
        arquivo: str = "hid-teste.ko", status: int = 0, chave_privada: bool = True,
    ) -> tuple[str, str]:
        ko = (tmp_path / "lib" / "modules" / KERNEL_DO_TESTE / "updates" / "dkms" / arquivo)
        feito = TestModuloSemAssinaturaComAChaveInscrita()
        dubles = _com_sig_key(sig_key, status)
        dubles["modinfo"] = dubles["modinfo"].replace("$MODULO_DE_MENTIRA", str(ko))
        lidas = feito._instalar(
            tmp_path, estado, arquivo=arquivo, assinado=True, dubles=dubles,
            chave_privada=chave_privada)
        return feito.dito, lidas

    def test_assinado_por_outra_chave_o_modulo_se_refaz(self, tmp_path: Path) -> None:
        """D-2111-O-MODULO-DE-OUTRA-CHAVE-SE-REFAZ-SO-DE-CERTEZA."""
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        dito, lidas = self._instalar(tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA))
        assert f"dkms build hefesto-teste/9.9.9 -k {KERNEL_DO_TESTE} --force" in lidas, lidas
        assert f"dkms install hefesto-teste/9.9.9 -k {KERNEL_DO_TESTE} --force" in lidas, lidas
        assert "assinado por outra chave" in dito, dito

    @pytest.mark.parametrize("arquivo", ["hid-teste.ko", "hid-teste.ko.xz", "hid-teste.ko.gz",
                                         "hid-teste.ko.zst"])
    def test_o_signatario_se_le_nos_quatro_formatos(self, tmp_path: Path, arquivo: str) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        _dito, lidas = self._instalar(
            tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA), arquivo=arquivo)
        assert "dkms build" in lidas, lidas

    @pytest.mark.parametrize(
        "sig_key",
        [_serie_do_modinfo(SERIE_DA_CHAVE), _serie_do_modinfo(SERIE_DA_CHAVE).lower(),
         "00:" + _serie_do_modinfo(SERIE_DA_CHAVE)],
        ids=["igual", "caixa-baixa", "zero-na-frente"],
    )
    def test_a_mesma_chave_nao_se_refaz(self, tmp_path: Path, sig_key: str) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        _dito, lidas = self._instalar(tmp_path, estado, sig_key)
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    def test_a_serie_com_o_bit_alto_confere_com_o_zero_do_der(self, tmp_path: Path) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DE_OUTRA)
        _dito, lidas = self._instalar(tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA))
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    @pytest.mark.parametrize(("sig_key", "status"), [("", 0), ("", 1), ("não é uma série", 0)],
                             ids=["vazio", "modinfo-falha", "lixo"])
    def test_o_signatario_que_nao_se_le_e_nao_sei(
        self, tmp_path: Path, sig_key: str, status: int
    ) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        _dito, lidas = self._instalar(tmp_path, estado, sig_key, status=status)
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    @pytest.mark.parametrize("corpo", [b"", b"nao-e-um-certificado", b"0\x82\xff\xff"],
                             ids=["vazio", "texto", "der-truncado"])
    def test_o_certificado_que_nao_se_le_e_nao_sei(self, tmp_path: Path, corpo: bytes) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        (tmp_path / "mok.pub").write_bytes(corpo)
        (tmp_path / "MokListRT").write_bytes(corpo + b"x")
        _dito, lidas = self._instalar(tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA))
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    def test_sem_a_chave_privada_nada_se_refaz(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=True, chave_privada=False)
        (tmp_path / "mok.pub").write_bytes(_certificado(SERIE_DA_CHAVE))
        (tmp_path / "MokListRT").write_bytes(_certificado(SERIE_DA_CHAVE))
        _dito, lidas = self._instalar(
            tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA), chave_privada=False)
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    def test_sem_secure_boot_o_modulo_de_outra_chave_fica(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=False, inscrita=True)
        (tmp_path / "mok.pub").write_bytes(_certificado(SERIE_DA_CHAVE))
        _dito, lidas = self._instalar(tmp_path, estado, _serie_do_modinfo(SERIE_DE_OUTRA))
        for verbo in FALHA_DE_REFAZER:
            assert verbo not in lidas, lidas

    def test_a_pergunta_serve_so_ao_modulo_da_casa(self, tmp_path: Path) -> None:
        estado = _com_a_chave_de(tmp_path, SERIE_DA_CHAVE)
        feito = _roda("dkms_modulo_da_casa_de_outra_chave hid-teste", "/usr/bin:/bin", estado)
        assert feito.returncode == 1, feito

    def test_o_leitor_do_der_confere_com_um_certificado_de_verdade(self, tmp_path: Path) -> None:
        openssl = shutil.which("openssl")
        if openssl is None:
            pytest.skip("sem openssl nesta máquina")
        chave = tmp_path / "teste.key"
        cert = tmp_path / "teste.der"
        subprocess.run(
            [openssl, "req", "-new", "-x509", "-nodes", "-days", "2", "-subj", "/CN=teste",
             "-newkey", "rsa:2048", "-keyout", str(chave), "-outform", "DER", "-out", str(cert)],
            check=True, capture_output=True, timeout=120)
        esperado = subprocess.run(
            [openssl, "x509", "-inform", "DER", "-in", str(cert), "-noout", "-serial"],
            check=True, capture_output=True, text=True, timeout=60).stdout.strip()
        esperado = esperado.removeprefix("serial=").lower().lstrip("0")
        lido = _roda("_dkms_serie_normalizada \"$(_dkms_serie_da_chave_publica)\"", "/usr/bin:/bin",
                     {"HEFESTO_DKMS_MOK_PUB": str(cert)})
        assert lido.stdout.lstrip("0") == esperado, (lido, esperado)
