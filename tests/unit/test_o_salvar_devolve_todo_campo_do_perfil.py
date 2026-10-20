"""O Salvar devolve todo campo do perfil que o rascunho não edita.

Medido em 17/10/2026 (item 66 das pendências de 16/10): `DraftConfig.to_profile` não emitia
`meus_toques`, `estilo`, `receita_do_tato`, `alvo`, `evento` nem `evento_comando`, e
os três Salvar que passam por ele (o do rodapé, o da Vibração e o da Controles) os apagavam do
disco: um perfil com «Meus toques» ligado, ou com o estilo de jogo escolhido, saía do Salvar sem
eles. O draft agora os leva da origem (`CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE`) e os devolve.

A MORDIDA: tire o `**self.source_so_devolve` do `to_profile` e
:func:`test_os_campos_que_o_rascunho_nao_edita_voltam_do_salvar` reprova; acrescente um campo ao
`Profile` sem levá-lo ao `to_profile` nem à lista e
:func:`test_todo_campo_do_perfil_tem_quem_o_devolva` reprova.
"""
from __future__ import annotations

import inspect
import re

from hefesto_dualsense4unix.app.draft_config import (
    CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE,
    DraftConfig,
)
from hefesto_dualsense4unix.profiles.schema import Profile

#: Os campos que o carregador escreve na gravação, nunca o rascunho.
DO_CARREGADOR = {"version", "criado_em", "modificado_em"}

PERFIL = {
    "name": "Do jogo",
    "match": {"type": "any"},
    "meus_toques": {"modo": "jogo_e_meus_toques", "forca": 55},
    "estilo": "terror",
    "receita_do_tato": {"chuva": 3},
    "alvo": "eventos",
    "evento": "meu_comando",
    "evento_comando": "true",
}


def test_os_campos_que_o_rascunho_nao_edita_voltam_do_salvar() -> None:
    origem = Profile.model_validate(PERFIL)
    salvo = DraftConfig.from_profile(origem).to_profile(origem.name)
    for campo in CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE:
        assert getattr(salvo, campo) == getattr(origem, campo), f"o Salvar apagou `{campo}`"


def test_o_perfil_sem_os_campos_segue_sem_eles() -> None:
    origem = Profile.model_validate({"name": "Simples", "match": {"type": "any"}})
    salvo = DraftConfig.from_profile(origem).to_profile(origem.name)
    for campo in CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE:
        assert getattr(salvo, campo) is None, f"o Salvar inventou `{campo}`"


def test_todo_campo_do_perfil_tem_quem_o_devolva() -> None:
    fonte = inspect.getsource(DraftConfig.to_profile)
    sem_dono = [
        campo for campo in Profile.model_fields
        if campo not in DO_CARREGADOR
        and campo not in CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE
        and not re.search(rf"\b{campo}=", fonte)
    ]
    assert not sem_dono, f"campos do perfil que o Salvar apagaria: {sem_dono}"
