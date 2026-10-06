"""A dispensa de uma ordem é fato de TOPOLOGIA, e mora com os outros."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    MesaDeclarada,
    OrdemDispensada,
)


def test_a_dispensa_guarda_a_data_e_o_arranjo() -> None:
    mesa = MesaDeclarada(
        ordens_dispensadas={
            "radio_largo_no_mesmo_hub": OrdemDispensada(
                quando="2026-08-25", arranjo="4-1.1.2|3-1.1.4"
            )
        }
    )
    guardada = mesa.ordens_dispensadas["radio_largo_no_mesmo_hub"]
    assert guardada.quando == "2026-08-25"
    assert guardada.arranjo == "4-1.1.2|3-1.1.4"


def test_a_mesa_sem_dispensa_nenhuma_continua_valida() -> None:
    """O campo é aditivo: um `maquina.json` de ontem carrega sem reclamar."""
    assert MesaDeclarada().ordens_dispensadas == {}
    assert MesaDeclarada.model_validate({"radios": {}}).ordens_dispensadas == {}


def test_a_dispensa_atravessa_o_arquivo_inteiro() -> None:
    """Ida e volta pelo `MaquinaConfig`, que é o que vai a disco."""
    bruto = {
        "mesa": {
            "ordens_dispensadas": {
                "teclado_so_no_hub": {
                    "quando": "2026-08-25",
                    "arranjo": "3-1.4",
                }
            }
        }
    }
    config = MaquinaConfig.model_validate(bruto)
    assert config.mesa is not None
    assert config.mesa.ordens_dispensadas["teclado_so_no_hub"].arranjo == "3-1.4"
    assert config.model_dump()["mesa"]["ordens_dispensadas"]


@pytest.mark.parametrize(
    "chave",
    [
        "aquela recomendação chata",
        "Radio_Largo",
        "radio-largo-no-mesmo-hub",
        "",
        "1_comeca_com_numero",
        "x" * 65,
    ],
)
def test_chave_que_nao_e_slug_de_regra_nao_entra_no_disco(chave: str) -> None:
    """A MORDIDA: sem o validador, o disco aceita lixo que nenhuma regra reclama."""
    with pytest.raises(ValidationError):
        MesaDeclarada(
            ordens_dispensadas={chave: OrdemDispensada(arranjo="3-1.4")}
        )


@pytest.mark.parametrize(
    "chave",
    [
        "radio_largo_no_mesmo_hub",
        "dois_radios_colados",
        "dongle_atras_de_hub",
        "teclado_so_no_hub",
        "dongle_dorme",
        "entrada_reclamou_de_corrente",
    ],
)
def test_as_seis_chaves_do_catalogo_passam(chave: str) -> None:
    """O validador tem de aceitar exatamente as regras que existem."""
    mesa = MesaDeclarada(
        ordens_dispensadas={chave: OrdemDispensada(arranjo="3-1.4")}
    )
    assert chave in mesa.ordens_dispensadas


def test_as_seis_chaves_sao_as_do_modulo_das_ordens() -> None:
    """Um dono só para o slug: o disco e o catálogo não podem divergir."""
    from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens

    do_catalogo = {
        ordens.R1_RADIO_LARGO_NO_MESMO_HUB,
        ordens.R2_DOIS_RADIOS_COLADOS,
        ordens.R3_DONGLE_ATRAS_DE_HUB,
        ordens.R4_TECLADO_SO_NO_HUB,
        ordens.R5_DONGLE_DORME,
        ordens.R6_ENTRADA_RECLAMOU_DE_CORRENTE,
    }
    mesa = MesaDeclarada(
        ordens_dispensadas={
            chave: OrdemDispensada(arranjo="3-1.4") for chave in do_catalogo
        }
    )
    assert set(mesa.ordens_dispensadas) == do_catalogo


@pytest.mark.parametrize(
    "quando", ["25/08/2026", "2026-08-25T03:14:00", "ontem", "2026-8-5"]
)
def test_data_que_nao_e_iso_nao_entra(quando: str) -> None:
    with pytest.raises(ValidationError):
        OrdemDispensada(quando=quando, arranjo="3-1.4")


def test_a_hora_nao_entra_junto_com_a_data() -> None:
    """Hora não muda decisão nenhuma do produto, e é rotina dela num arquivo"""
    with pytest.raises(ValidationError):
        OrdemDispensada(quando="2026-08-25 03:14", arranjo="3-1.4")


def test_a_assinatura_nao_aceita_serial_nem_endereco() -> None:
    """A MORDIDA DO ANONIMATO: doze hex é a forma de um serial, e ela não passa."""
    with pytest.raises(ValidationError):
        OrdemDispensada(arranjo="d0f1a2b3c4d5")
    with pytest.raises(ValidationError):
        OrdemDispensada(arranjo="4-1.1.2|D0F1A20000C4")


def test_a_assinatura_de_caminho_de_barramento_passa() -> None:
    """O que a assinatura REALMENTE carrega tem de continuar entrando."""
    assert OrdemDispensada(arranjo="4-1.1.2|3-1.1.4 4-1.1.2|3-1.2").arranjo


def test_a_assinatura_tem_teto_de_tamanho() -> None:
    with pytest.raises(ValidationError):
        OrdemDispensada(arranjo="3-1.4 " * 200)


def test_campo_desconhecido_na_dispensa_nao_entra() -> None:
    """`extra="forbid"`: um campo que o produto não conhece é lixo herdado."""
    with pytest.raises(ValidationError):
        OrdemDispensada.model_validate(
            {"quando": "2026-08-25", "arranjo": "3-1.4", "motivo": "não quero"}
        )
