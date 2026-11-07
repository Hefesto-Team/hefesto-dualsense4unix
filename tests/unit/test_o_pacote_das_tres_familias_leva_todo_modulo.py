"""Os três empacotadores leem a mesma lista de módulos DKMS, e a remoção desfaz cada um.

A lista tem um dono, `assets/dkms/*/dkms.conf`. A régua roda o laço de verdade de cada empacotador
e confere o resultado contra o que o install compila, uma lista que nasce em outro arquivo: uma
pasta tirada do dono reprova os três.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DKMS = RAIZ / "assets" / "dkms"
BUILD_DEB = RAIZ / "scripts" / "build_deb.sh"
PKGBUILD = RAIZ / "packaging" / "arch" / "PKGBUILD"
INSTALL_ARCH = RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install"
SPEC = RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
PRERM = RAIZ / "packaging" / "debian" / "prerm"
POSTINST = RAIZ / "packaging" / "debian" / "postinst"
O_QUE_O_INSTALL_COMPILA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
AJUDANTE = "scripts/dkms_do_pacote.sh"
PACOTES = (BUILD_DEB, PKGBUILD, SPEC)


def _ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _compilados_pelo_install() -> set[str]:
    texto = _ler(O_QUE_O_INSTALL_COMPILA)
    achados = re.findall(r"dkms_install_patched_module (hefesto-[\w-]+)", texto)
    assert len(achados) >= 5
    return set(achados)


def _laco(texto: str) -> str:
    achado = re.search(r"^ *for _conf in .*?^ *done$", texto, re.M | re.S)
    assert achado, "o empacotador não copia as fontes DKMS por laço"
    return achado.group(0)


def _levados(empacotador: Path, destino: Path) -> set[str]:
    corpo = (
        _laco(_ler(empacotador))
        .replace("%{buildroot}", str(destino))
        .replace("%{_datadir}", "/usr/share")
        .replace("%{app_id}", "hefesto-dualsense4unix")
    )
    subprocess.run(
        ["bash", "-euc", corpo], cwd=RAIZ, check=True,
        env={**os.environ, "STAGING": str(destino), "pkgdir": str(destino)},
    )
    nomes = set()
    for conf in destino.glob("usr/share/hefesto-dualsense4unix/dkms/*/dkms.conf"):
        achado = re.search(r'^PACKAGE_NAME="(.*)"$', _ler(conf), re.M)
        assert achado, conf
        nomes.add(achado.group(1))
    return nomes


@pytest.mark.parametrize("empacotador", PACOTES, ids=lambda p: p.name)
def test_cada_pacote_leva_o_que_o_install_compila(empacotador: Path, tmp_path: Path) -> None:
    levados = _levados(empacotador, tmp_path)
    assert levados == _compilados_pelo_install(), empacotador.name


@pytest.mark.parametrize("empacotador", PACOTES, ids=lambda p: p.name)
def test_nenhum_empacotador_nomeia_modulo_a_mao(empacotador: Path) -> None:
    pastas = sorted(conf.parent.name for conf in DKMS.glob("*/dkms.conf"))
    citadas = [p for p in pastas if f"assets/dkms/{p}/." in _ler(empacotador)]
    assert not citadas, f"{empacotador.name} ainda copia à mão: {citadas}"


@pytest.mark.parametrize("empacotador", PACOTES, ids=lambda p: p.name)
def test_cada_pacote_leva_o_ajudante(empacotador: Path) -> None:
    assert AJUDANTE in _ler(empacotador)


@pytest.mark.parametrize("pos", [POSTINST, INSTALL_ARCH, SPEC], ids=lambda p: p.name)
def test_a_instalacao_das_tres_familias_compila_e_confere(pos: Path) -> None:
    """Só o `.deb` rodava o ajudante; no Arch e no Fedora o `uhid` viajava sem nunca compilar."""
    assert re.search(r"scripts/dkms_do_pacote\.sh \|\| (true|:)$", _ler(pos), re.M), pos.name


@pytest.mark.parametrize("gancho", [PRERM, INSTALL_ARCH, SPEC], ids=lambda p: p.name)
def test_a_remocao_das_tres_familias_desfaz_cada_modulo(gancho: Path) -> None:
    for pacote in sorted(_compilados_pelo_install()):
        assert f'dkms remove "{pacote}/' in _ler(gancho), f"{gancho.name}: {pacote} fica registrado"


def test_o_rpm_empacota_a_pasta_inteira_dos_modulos() -> None:
    """O `%files` por módulo aborta o `rpmbuild` em toda pasta nova, e na `LICENSES` já abortava."""
    _, _, arquivos = _ler(SPEC).partition("\n%files")
    assert "%{_datadir}/%{app_id}/dkms/\n" in arquivos
    assert f"%{{_datadir}}/%{{app_id}}/{AJUDANTE}\n" in arquivos
