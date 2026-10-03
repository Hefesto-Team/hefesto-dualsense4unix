"""A dispensa de uma ordem: cala no arranjo que ela viu, volta quando ele muda."""
from __future__ import annotations


from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens


def ordem(
    *, chave: str = "radio_largo_no_mesmo_hub", arranjo: str, ambigua: bool = False
) -> ordens.Ordem:
    """Uma ordem mínima — só o que as quatro respostas olham."""
    linha = ordens.Linha(texto="tanto faz", selo=ordens.MEDIDO_AQUI)
    return ordens.Ordem(
        chave=chave,
        acao="Mova",
        o_que_eu_vi=linha,
        por_que_importa=linha,
        ganho_esperado=linha,
        alvo=ordens.Identidade(vid="2357", pid="012d", caminho="4-1.1.2",
                               ambigua=ambigua),
        arranjo=arranjo,
    )


def test_a_dispensa_cala_a_ordem_no_arranjo_que_ela_viu() -> None:
    uma = ordem(arranjo="4-1.1.2|3-1.1.4")
    dispensadas = {uma.chave: uma.arranjo}
    assert ordens.ordens_novas([uma], dispensadas) == ()
    assert ordens.ordens_caladas([uma], dispensadas) == (uma,)


def test_a_dispensa_volta_quando_o_arranjo_muda() -> None:
    """A MORDIDA: chavear a dispensa só pelo slug reprova aqui. (D-ORDEM-IGNORADA-VOLTA)"""
    dispensadas = {"radio_largo_no_mesmo_hub": "4-1.1.2|3-1.1.4"}
    depois = ordem(arranjo="4-1.1.2|3-1.2")
    assert ordens.ordens_novas([depois], dispensadas) == (depois,)
    assert ordens.ordens_caladas([depois], dispensadas) == ()


def test_a_dispensa_de_uma_regra_nao_cala_outra() -> None:
    dispensadas = {"radio_largo_no_mesmo_hub": "x"}
    outra = ordem(chave="teclado_so_no_hub", arranjo="x")
    assert ordens.ordens_novas([outra], dispensadas) == (outra,)


def test_a_ordem_calada_continua_contada() -> None:
    """Dispensa que some sem deixar marca é o mesmo defeito do card que some."""
    uma = ordem(arranjo="a")
    outra = ordem(chave="teclado_so_no_hub", arranjo="b")
    dispensadas = {"radio_largo_no_mesmo_hub": "a"}
    novas = ordens.ordens_novas([uma, outra], dispensadas)
    caladas = ordens.ordens_caladas([uma, outra], dispensadas)
    assert len(novas) + len(caladas) == 2


def test_o_arranjo_nao_carrega_serial_nem_endereco() -> None:
    """A tela desta aba vira PNG versionado; o arranjo entra nela."""
    from tests.unit import bancada_das_ordens as bancada

    leitura = ordens.Leitura(censo=bancada.censo(), entradas=bancada.entradas())
    for uma in ordens.catalogo(leitura):
        for serial in bancada.SERIAIS.values():
            assert serial.lower() not in uma.arranjo.lower()
