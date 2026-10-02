"""A frase do `--dry-run` não é quem instala — a paridade não a aceita como dono."""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_o_que_era_do_zsh_mora_no_hefesto import _paridade_numa_arvore

_DONOS_COM_A_LIB = "    for _dono_cand in install.sh scripts/lib/camada_de_maquina.sh \\\n"
_DONOS_SEM_A_LIB = "    for _dono_cand in install.sh \\\n"


def test_com_a_lib_o_vigia_tem_dono(tmp_path: Path) -> None:
    saida = _paridade_numa_arvore(tmp_path)
    assert "[ OK ] artefatos de sistema:" in saida, saida


def test_sem_a_lib_a_frase_do_ensaio_nao_segura_o_vigia(tmp_path: Path) -> None:
    saida = _paridade_numa_arvore(
        tmp_path,
        {"scripts/check_packaging_parity.sh": (_DONOS_COM_A_LIB, _DONOS_SEM_A_LIB)},
    )
    assert (
        "[FAIL] assets/systemd/hefesto-wifi-usb-vigia.service: artefato de sistema que "
        "nenhum caminho de instalação alcança"
    ) in saida, (
        "sem a lib entre os donos, o vigia seguiu «com dono» — a frase do ensaio do "
        "install passou por instalação:\n" + saida
    )
