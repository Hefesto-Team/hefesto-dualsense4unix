"""O doctor avisa quando o módulo de fábrica assume e o microfone pelo rádio cai.

O-MODULO-DO-CONTROLE-SEGUE-O-KERNEL-NOVO-E-O-DOCTOR-AVISA-QUANDO-ELE-CAI-01. O pino do
`dkms.conf` PULA todo kernel que não conferiu, e nesse kernel o `hid_playstation` de
fábrica não tem a guarda do áudio (patch 0003): o microfone pelo Bluetooth cai. Esta régua
cobra a pergunta do `check_hefesto_hid_playstation_dkms` com os kernels que chegam depois dos
conferidos (o próximo build do Pop, o estável 7.2.10 e o 7.3), com um
`/sys/module` de mentira: com o módulo de fábrica o aviso sai, com a cópia do Hefesto não.

A MORDIDA: trocar o `warn` do kernel fora da lista por `info` (ou tirar a frase) reprova
`test_o_de_fabrica_em_kernel_novo_avisa` e `test_o_aviso_diz_como_voltar`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit.test_o_microfone_do_radio_pergunta_ao_driver import (
    _doctor_hidp,
    _sys_do_modulo,
)

RAIZ = Path(__file__).resolve().parents[2]
BASELINE = RAIZ / "assets" / "dkms" / "hid-playstation" / "patch" / "BASELINE"
DE_FABRICA = "A74F93FE20FF36683AF7614"

KERNELS_NOVOS = [
    "7.2.7-76070207-generic",
    "7.2.10-76070210-generic",
    "7.3.0-76070300-generic",
]


def _validados() -> list[str]:
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha.startswith("KERNELS_VALIDADOS="):
            return linha.split("=", 1)[1].replace(",", " ").split()
    raise AssertionError("o BASELINE perdeu o KERNELS_VALIDADOS")


@pytest.mark.parametrize("kernel", KERNELS_NOVOS)
def test_o_de_fabrica_em_kernel_novo_avisa(tmp_path: Path, kernel: str) -> None:
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor_hidp(tmp_path, modulo=modulo, staged=False, kernel=kernel)
    assert "[WARN]" in saida, saida
    assert "microfone do DualSense pelo rádio" in saida, saida
    assert "não está entre os conferidos" in saida, saida
    assert f"o kernel {kernel}" in saida, saida
    assert "[ OK ]" not in saida, saida


def test_o_aviso_lista_os_conferidos_da_baseline(tmp_path: Path) -> None:
    """A lista da frase é a do BASELINE, não uma cópia: a que o pino do `dkms.conf` aceita."""
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor_hidp(
        tmp_path, modulo=modulo, staged=False, kernel=KERNELS_NOVOS[0]
    )
    assert _validados(), "o BASELINE não nomeia nenhum kernel conferido"
    assert f"({' '.join(_validados())})" in saida, saida


def test_o_aviso_diz_como_voltar(tmp_path: Path) -> None:
    """A frase não só diz que o microfone caiu: diz o que faz ele voltar."""
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor_hidp(
        tmp_path, modulo=modulo, staged=False, kernel=KERNELS_NOVOS[0]
    )
    assert "Para o microfone voltar" in saida, saida
    assert "kernel dessa lista" in saida, saida


@pytest.mark.parametrize(
    "kernel", ["7.1.5-76070105-generic", "7.2.6-76070206-generic", *KERNELS_NOVOS]
)
def test_com_a_copia_do_hefesto_o_aviso_some(tmp_path: Path, kernel: str) -> None:
    modulo = _sys_do_modulo(tmp_path, marca="Y")
    saida = _doctor_hidp(tmp_path, modulo=modulo, staged=True, kernel=kernel)
    assert "[WARN]" not in saida, saida
    assert "[ OK ]" in saida and "descarta o áudio do microfone" in saida, saida


def test_a_regex_do_pino_e_os_conferidos_dizem_o_mesmo() -> None:
    """Nenhum kernel novo entra num lado só: o `dkms.conf` e o BASELINE andam juntos."""
    conf = (RAIZ / "assets" / "dkms" / "hid-playstation" / "dkms.conf").read_text(
        encoding="utf-8"
    )
    achou = re.search(r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', conf, re.MULTILINE)
    assert achou, "o dkms.conf perdeu o BUILD_EXCLUSIVE_KERNEL"
    regex = re.compile(achou.group(1))
    for um in _validados():
        assert regex.match(f"{um}-generic"), (um, achou.group(1))
    for novo in KERNELS_NOVOS:
        conferido = any(novo.startswith(f"{um}-") for um in _validados())
        assert bool(regex.match(novo)) == conferido, (
            f"{novo}: o pino e o BASELINE discordam, e o doctor avisaria errado"
        )
