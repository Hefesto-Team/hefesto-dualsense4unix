"""O Salvar de qualquer aba leva de volta a acessibilidade do perfil.

MEDIDO EM 16/10/2026, na conferência final do conjunto da acessibilidade: o modo do
botão, a curva dos analógicos e o cursor nasceram no esquema, mas o ``DraftConfig``
não os conhecia. Toda aba que grava pelo rascunho (o rodapé, a 02, a 05) monta o
perfil por ``DraftConfig.from_profile`` e ``to_profile``, então mudar a cor da luz de
um perfil com o clique travado apagava o clique travado do disco. A cura é a mesma
passagem do ``movimento``: o rascunho não as edita, só as leva de volta, com o mesmo
nome ou com um nome novo.

A MORDIDA: apague de ``to_profile`` a linha que passa uma das três seções e o caso dela
reprova.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileAnalogicosConfig,
    ProfileAtivacaoConfig,
    ProfileCursorConfig,
)

_SECOES = {
    "ativacao": ProfileAtivacaoConfig(alternar=["l1"], repique_ms=40),  # (noqa-acento)
    "analogicos": ProfileAnalogicosConfig(zona_morta=12, curva="precisa"),
    "cursor": ProfileCursorConfig(precisao_botao="r1", clique_travado="l3", permanencia_ms=800),
}


@pytest.mark.parametrize("secao", sorted(_SECOES))
@pytest.mark.parametrize("nome", ["Com Ajuda", "Outro Nome"])
def test_a_secao_sobrevive_ao_rascunho(secao: str, nome: str) -> None:
    perfil = Profile(name="Com Ajuda", match=MatchAny(type="any"), **{secao: _SECOES[secao]})
    salvo = DraftConfig.from_profile(perfil).to_profile(nome, priority=perfil.priority)
    assert getattr(salvo, secao) == _SECOES[secao], (
        f"o Salvar pelo rascunho apagou a seção {secao!r} do perfil")


def test_o_perfil_sem_a_secao_nao_ganha_uma() -> None:
    """Perfil sem opinião sai sem opinião: nada de seção fantasma no disco."""
    perfil = Profile(name="Sem Ajuda", match=MatchAny(type="any"))
    salvo = DraftConfig.from_profile(perfil).to_profile("Sem Ajuda")
    for secao in _SECOES:
        assert getattr(salvo, secao) is None
