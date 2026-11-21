"""O ``/sys/module`` dos testes tem um botão só: ``HEFESTO_SYS_MODULE``.

O-SYS-MODULE-DOS-TESTES-TEM-UM-BOTAO-SO-01. A biblioteca do DKMS, o doctor e a camada de máquina do
install liam o mesmo ``/sys/module`` por três variáveis; um teste que mexia numa e esquecia a outra
lia o módulo carregado da máquina de verdade. O preparador, que roda como root dentro do DKMS, só
atende o botão quando o processo não é root: o root nunca herda do ambiente de quem chama o
caminho dos módulos carregados.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PREPARADOR = RAIZ / "assets" / "dkms" / "hid-playstation" / "preparar-o-fonte.py"
ANTIGOS = ("HEFESTO_DKMS_" + "SYS_MODULE", "HEFESTO_DOCTOR_" + "SYS_MODULE")
BOTAO = "HEFESTO_SYS_MODULE"


def _fontes() -> list[Path]:
    achados: list[Path] = []
    for pasta, padrao in (
        ("scripts", "**/*.sh"), ("assets/dkms", "*/preparar-o-fonte.py"),
        ("tests", "**/*.py"), ("src", "**/*.py"),
    ):
        achados.extend((RAIZ / pasta).glob(padrao))
    achados.extend(RAIZ / nome for nome in ("install.sh", "uninstall.sh"))
    return [a for a in achados if a.is_file() and a != Path(__file__).resolve()]


def test_nenhum_arquivo_traz_os_botoes_antigos_do_sys_module() -> None:
    """O-SYS-MODULE-DOS-TESTES-TEM-UM-BOTAO-SO-01: os dois nomes velhos não voltam."""
    com_o_velho = sorted(
        f"{f.relative_to(RAIZ)}: {nome}"
        for f in _fontes() for nome in ANTIGOS
        if nome in f.read_text(encoding="utf-8", errors="replace")
    )
    assert not com_o_velho, f"o botão do /sys/module é {BOTAO}, os outros saíram: {com_o_velho}"


def _preparador():
    spec = importlib.util.spec_from_file_location("preparador_do_sys_module", PREPARADOR)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize(("euid", "esperado"), [(1000, "/de/mentira"), (0, "/sys/module")])
def test_o_preparador_como_root_nao_herda_o_caminho_do_ambiente(
    monkeypatch: pytest.MonkeyPatch, euid: int, esperado: str
) -> None:
    """O-SYS-MODULE-DOS-TESTES-TEM-UM-BOTAO-SO-01: só fora do root o botão vale."""
    modulo = _preparador()
    monkeypatch.setenv(BOTAO, "/de/mentira")
    monkeypatch.setattr(os, "geteuid", lambda: euid)
    assert str(modulo._raiz_dos_modulos_carregados()) == esperado
