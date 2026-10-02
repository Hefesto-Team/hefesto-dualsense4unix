"""A pele do cartão não pode ficar com a cor de OUTRO modelo."""

from __future__ import annotations

import sys
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

import monta

from hefesto_dualsense4unix.interface.pacotes import (
    a01_jogar,
    a03_gatilhos,
    a04_iluminacao,
    a06_navegacao,
)

QUEM_PINTA = {
    "01-jogar": a01_jogar._cor_do_plastico,
    "03-gatilhos": a03_gatilhos._cor_do_plastico,
    "04-iluminacao": a04_iluminacao._cor_do_plastico,
    "06-navegacao": a06_navegacao.cor_do_plastico,
}

TODOS = tuple(monta.DS_SLUGS) if hasattr(monta, "DS_SLUGS") else ()


def _todos_os_modelos() -> list[str]:
    """Os slugs que a folha publica, lidos dela."""
    import re

    return sorted(set(re.findall(r'svg\[data-colorway="([^"]+)"\]', monta.DS)))


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_nenhuma_aba_manda_url_para_campo_de_cor(aba: str) -> None:
    """Nenhum dos 28 modelos faz a aba emitir algo que o CSS recusa."""
    pinta = QUEM_PINTA[aba]
    ruins = {m: v for m in _todos_os_modelos()
             if (v := pinta(m)) and not v.startswith("#")}
    assert not ruins, (
        f"a aba {aba} manda para um campo de COR um valor que o CSS não "
        f"aceita: {ruins}. O CSSOM recusa em silêncio e a pele fica com o hexa "
        "do mockup — outro modelo, afirmado com confiança")


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_os_oito_sem_amostragem_calam_em_vez_de_mentir(aba: str) -> None:
    """Sem hexa amostrado, a resposta é `""` — a regra dela."""
    sem_hexa = [m for m in _todos_os_modelos()
                if not str(monta.cor_da_zona(m)).startswith("#")]
    assert sem_hexa, "nenhum modelo sem hexa — a folha mudou de forma"
    for modelo in sem_hexa:
        assert QUEM_PINTA[aba](modelo) == "", (
            f"{aba} responde algo para {modelo}, que não tem hexa amostrado")


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_quem_tem_hexa_continua_vestindo(aba: str) -> None:
    """A cura não pode ter calado quem TINHA cor."""
    com_hexa = [m for m in _todos_os_modelos()
                if str(monta.cor_da_zona(m)).startswith("#")]
    assert len(com_hexa) >= 20, f"só {len(com_hexa)} modelos com hexa"
    for modelo in com_hexa:
        assert QUEM_PINTA[aba](modelo) == monta.cor_da_zona(modelo), (
            f"{aba} deixou de vestir {modelo}, que TEM hexa no mapa dela")


def test_as_quatro_abas_respondem_igual() -> None:
    """As quatro leem o mesmo dado, então não podem divergir."""
    for modelo in _todos_os_modelos():
        respostas = {aba: f(modelo) for aba, f in QUEM_PINTA.items()}
        assert len(set(respostas.values())) == 1, (
            f"as abas discordam sobre {modelo}: {respostas}")


def test_o_desenho_continua_recebendo_os_oito() -> None:
    """Calar a PELE não pode ter calado o DESENHO."""
    sem_hexa = [m for m in _todos_os_modelos()
                if not str(monta.cor_da_zona(m)).startswith("#")]
    for modelo in sem_hexa:
        assert a01_jogar._colorway_do_desenho(modelo) == modelo, (
            f"o desenho deixou de receber {modelo} — a hachura vale no SVG")
