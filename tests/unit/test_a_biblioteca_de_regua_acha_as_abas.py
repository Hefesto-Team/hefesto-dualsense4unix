"""A biblioteca com que se escreve régua de tela tem de ACHAR as abas."""

from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `scripts.regua_de_tela`, que carrega o GTK")

import regua_de_tela as regua


def test_acha_as_dez_abas() -> None:
    """As dez páginas de aba, e não uma a menos."""
    abas = regua.abas_conhecidas()
    assert len(abas) == 10, f"achou {len(abas)}: {[a.name for a in abas]}"


@pytest.mark.parametrize("numero", [f"{n:02d}" for n in range(1, 11)])
def test_cada_aba_tem_candidata(numero: str) -> None:
    """Pedir uma aba pelo número devolve arquivo que existe."""
    candidatas = regua.candidatas_da_aba(numero)
    assert candidatas, f"nenhuma cópia da aba {numero}"
    assert candidatas[0].is_file()
    assert candidatas[0].stem.startswith(numero)


def test_a_arvore_local_vence_o_relogio() -> None:
    """A primeira candidata mora NESTA árvore, mesmo com worktree mais nova."""
    escolhida = regua.candidatas_da_aba("04")[0]
    assert escolhida.is_relative_to(RAIZ), (
        f"a régua escolheu uma cópia de fora desta árvore: {escolhida}")
    assert escolhida.parent in {RAIZ / pasta for pasta in regua.PASTAS_DAS_ABAS}, (
        f"a régua escolheu uma cópia fora das duas casas: {escolhida}")


def test_as_duas_casas_de_hoje_existem() -> None:
    """As pastas que a biblioteca declara têm de estar no disco."""
    for pasta in regua.PASTAS_DAS_ABAS:
        assert (RAIZ / pasta).is_dir(), (
            f"`{pasta}` está declarada em PASTAS_DAS_ABAS e não existe")


def test_a_bancada_vem_antes_do_publicado() -> None:
    """A ordem é decisão desta casa, e está escrita em ``onde.pagina``."""
    assert regua.PASTAS_DAS_ABAS[0] == "mockup"
