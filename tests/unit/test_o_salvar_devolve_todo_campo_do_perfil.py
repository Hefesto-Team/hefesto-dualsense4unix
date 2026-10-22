"""O Salvar devolve todo campo do perfil que o rascunho não edita.

Medido em 17/10/2026 (item 66 das pendências de 16/10): `DraftConfig.to_profile` não emitia
`meus_toques`, `estilo`, `receita_do_tato`, `alvo`, `evento` nem `evento_comando` (e, desde
20/10/2026, o `nome_do_jogo` que a aba Lançadores grava), e
os três Salvar que passam por ele (o do rodapé, o da Vibração e o da Controles) os apagavam do
disco: um perfil com «Meus toques» ligado, ou com o estilo de jogo escolhido, saía do Salvar sem
eles. O draft agora os leva da origem (`CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE`) e os devolve.

A MORDIDA: tire o `**self.source_so_devolve` do `to_profile` e
:func:`test_os_campos_que_o_rascunho_nao_edita_voltam_do_salvar` reprova; acrescente um campo ao
`Profile` sem levá-lo ao `to_profile` nem à lista e
:func:`test_todo_campo_do_perfil_tem_quem_o_devolva` reprova.

Medido em 22/10/2026 no perfil do Sackboy: o mesmo buraco DENTRO das seções. O rascunho não
levava `triggers.modo`, `triggers.intensidade`, `leds.modo`, `leds.efeito` nem
`leds.lightbar_para_o_numero`, e todo Salvar devolvia o «Modo automático» dos Gatilhos e da
Iluminação a `null` no disco. A MORDIDA: tire o laço de `source_secoes_so_devolve` do `to_profile` e
:func:`test_os_campos_de_secao_que_o_rascunho_nao_edita_voltam_do_salvar` reprova; acrescente um
campo a uma seção sem levá-lo ao rascunho nem à lista e
:func:`test_todo_campo_de_secao_tem_quem_o_devolva` reprova.
"""
from __future__ import annotations

import inspect
import re

from hefesto_dualsense4unix.app.draft_config import (
    CAMPOS_DA_SECAO_QUE_O_RASCUNHO_SO_DEVOLVE,
    CAMPOS_QUE_O_RASCUNHO_SO_DEVOLVE,
    DraftConfig,
)
from hefesto_dualsense4unix.profiles.schema import (
    TODAS_AS_BASES_DA_LUZ,
    LedsConfig,
    Profile,
    RumbleConfig,
    TriggersConfig,
    escrever_o_efeito_da_luz,
)

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
    "nome_do_jogo": "Jogo de emulador",
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


#: Os campos de cada seção que o rascunho EDITA (e por isso devolve pelo próprio sub-draft).
EDITADOS_PELO_RASCUNHO = {
    "triggers": {"left", "right"},
    "leds": {"lightbar", "player_leds", "lightbar_brightness", "auto_player_colors",
             "player_led_brightness"},
    "rumble": {"passthrough", "policy", "custom_mult", "modo"},
}
SECOES = {"triggers": TriggersConfig, "leds": LedsConfig, "rumble": RumbleConfig}


def test_os_campos_de_secao_que_o_rascunho_nao_edita_voltam_do_salvar() -> None:
    origem = Profile.model_validate({
        "name": "Sackboy",
        "match": {"type": "any"},
        "triggers": {"modo": "automatico", "intensidade": 1.5},  # (noqa-acento) chave ASCII
        "leds": {
            "modo": "automatico",  # (noqa-acento) chave ASCII
            "efeito": escrever_o_efeito_da_luz(TODAS_AS_BASES_DA_LUZ[0], ["FF0000"], 3),
            "lightbar_para_o_numero": 2,
        },
        "rumble": {"modo": "automatico"},  # (noqa-acento) chave ASCII
    })
    assert origem.leds.efeito is not None, "o efeito de exemplo não é válido"
    salvo = DraftConfig.from_profile(origem).to_profile(origem.name)
    for secao, campos in CAMPOS_DA_SECAO_QUE_O_RASCUNHO_SO_DEVOLVE.items():
        for campo in campos:
            antes = getattr(getattr(origem, secao), campo)
            assert getattr(getattr(salvo, secao), campo) == antes, (
                f"o Salvar apagou `{secao}.{campo}`")
    assert salvo.rumble.modo == "automatico"  # (noqa-acento) chave ASCII


def test_a_secao_sem_os_campos_segue_sem_eles() -> None:
    origem = Profile.model_validate({"name": "Simples", "match": {"type": "any"}})
    salvo = DraftConfig.from_profile(origem).to_profile(origem.name)
    assert salvo.model_dump(mode="json")["triggers"] == origem.model_dump(mode="json")["triggers"]
    assert salvo.model_dump(mode="json")["leds"] == origem.model_dump(mode="json")["leds"]


def test_todo_campo_de_secao_tem_quem_o_devolva() -> None:
    sem_dono = [
        f"{secao}.{campo}"
        for secao, modelo in SECOES.items()
        for campo in modelo.model_fields
        if campo not in EDITADOS_PELO_RASCUNHO[secao]
        and campo not in CAMPOS_DA_SECAO_QUE_O_RASCUNHO_SO_DEVOLVE.get(secao, ())
    ]
    assert not sem_dono, f"campos de seção que o Salvar apagaria: {sem_dono}"
