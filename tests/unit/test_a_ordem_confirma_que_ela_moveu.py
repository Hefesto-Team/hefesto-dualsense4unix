""""Já movi" responde quatro coisas, e nenhuma delas é repetir a ordem.

Um card que simplesmente some é indistinguível de um card que nunca foi
desenhado. É o F7 aplicado ao próprio gesto dela: ela apertou um botão e precisa
ver o que ele fez. Por isso as quatro respostas existem como CHAVE, e não como
frase — a frase é da frente do léxico, a chave é contrato.

E a dispensa segue a mesma disciplina: ela vale para o ARRANJO que ela viu, e
não para a recomendação. Chavear só pelo slug faria a decisão de ontem calar uma
medição de hoje.

ESTE ARQUIVO NÃO MONTA TELA
----------------------------

A metade GTK da ORDEM-6 (os dois botões, o card que fica) **aguarda o olho
dela** — é texto novo na tela, e PROVA-DE-TELA-01 manda foto antes e depois. O
que se prova aqui é a LÓGICA que a tela vai consumir, que é pura e fecha sozinha.
"""
from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# As quatro respostas.
# ---------------------------------------------------------------------------


def test_a_regra_parou_de_disparar_e_o_produto_confirma() -> None:
    """Passagem 1: ela moveu, a regra calou. Verde, e a frase FICA na tela."""
    antes = ordem(arranjo="4-1.1.2|3-1.1.4")
    assert ordens.resposta_ao_ja_movi(antes, None) == ordens.CONFIRMEI


def test_arranjo_diferente_e_moveu_e_continua_apertado() -> None:
    """Passagem 2: ela moveu e continua apertado — o card NOVO, não o velho.

    Fazer o card sumir em silêncio aqui é o defeito: ela apertou o botão, mudou
    o mundo, e o produto tem de dizer o que mudou.
    """
    antes = ordem(arranjo="4-1.1.2|3-1.1.4")
    depois = ordem(arranjo="4-1.1.2|3-1.2")
    assert ordens.resposta_ao_ja_movi(antes, depois) == ordens.MOVEU_E_CONTINUA


def test_mesmo_arranjo_e_nao_vi_mudanca() -> None:
    """Passagem 3: nada mudou. O card fica, com essa linha somada."""
    antes = ordem(arranjo="4-1.1.2|3-1.1.4")
    depois = ordem(arranjo="4-1.1.2|3-1.1.4")
    assert ordens.resposta_ao_ja_movi(antes, depois) == ordens.SEM_MUDANCA


@pytest.mark.parametrize("depois_existe", [True, False])
def test_tripla_ambigua_nunca_confirma(depois_existe: bool) -> None:
    """Passagem 4: dois aparelhos iguais na mesa — **nunca** "Confirmei".

    A ambiguidade vence tudo, e vence ANTES das três respostas do arranjo: com
    duas triplas iguais o produto não sabe qual dos dois ela moveu, e "Confirmei"
    ali seria afirmação sem base. Deixar a ambiguidade por último faz o caso
    `agora is None` responder "Confirmei", e reprova.
    """
    antes = ordem(arranjo="4-1.1.2|3-1.1.4", ambigua=True)
    depois = ordem(arranjo="4-1.1.2|3-1.1.4", ambigua=True) if depois_existe else None
    assert ordens.resposta_ao_ja_movi(antes, depois) == ordens.NAO_CONSEGUI_CONFIRMAR


def test_a_ambiguidade_que_nasce_depois_tambem_impede_confirmar() -> None:
    """Ela encaixou um segundo aparelho igual: o produto perde a certeza."""
    antes = ordem(arranjo="4-1.1.2|3-1.1.4")
    depois = ordem(arranjo="4-1.1.2|3-1.2", ambigua=True)
    assert ordens.resposta_ao_ja_movi(antes, depois) == ordens.NAO_CONSEGUI_CONFIRMAR


def test_as_quatro_respostas_sao_distintas_e_tem_frase() -> None:
    """Quatro chaves, quatro frases, e nenhuma repetida."""
    todas = (
        ordens.CONFIRMEI,
        ordens.MOVEU_E_CONTINUA,
        ordens.SEM_MUDANCA,
        ordens.NAO_CONSEGUI_CONFIRMAR,
    )
    assert len(set(todas)) == 4
    frases = [ordens.FRASE_DA_RESPOSTA[chave] for chave in todas]
    assert len(set(frases)) == 4
    assert all(frase.strip() for frase in frases)


def test_so_a_confirmacao_afirma_ter_confirmado() -> None:
    """"Não consegui confirmar" não pode ler como "Confirmei" de relance."""
    assert ordens.FRASE_DA_RESPOSTA[ordens.CONFIRMEI].startswith("Confirmei")
    assert ordens.FRASE_DA_RESPOSTA[ordens.NAO_CONSEGUI_CONFIRMAR].startswith(
        "Não consegui"
    )


# ---------------------------------------------------------------------------
# A dispensa — `D-ORDEM-IGNORADA-VOLTA`.
# ---------------------------------------------------------------------------


def test_a_dispensa_cala_a_ordem_no_arranjo_que_ela_viu() -> None:
    uma = ordem(arranjo="4-1.1.2|3-1.1.4")
    dispensadas = {uma.chave: uma.arranjo}
    assert ordens.ordens_novas([uma], dispensadas) == ()
    assert ordens.ordens_caladas([uma], dispensadas) == (uma,)


def test_a_dispensa_volta_quando_o_arranjo_muda() -> None:
    """A MORDIDA: chavear a dispensa só pelo slug reprova aqui.

    A dispensa vale para o que ela viu. Se ela mexer nos cabos e a mesma regra
    disparar com arranjo novo, é FATO NOVO — e a decisão de ontem não pode calar
    uma medição de hoje.
    """
    dispensadas = {"radio_largo_no_mesmo_hub": "4-1.1.2|3-1.1.4"}
    depois = ordem(arranjo="4-1.1.2|3-1.2")
    assert ordens.ordens_novas([depois], dispensadas) == (depois,)
    assert ordens.ordens_caladas([depois], dispensadas) == ()


def test_a_dispensa_de_uma_regra_nao_cala_outra() -> None:
    dispensadas = {"radio_largo_no_mesmo_hub": "x"}
    outra = ordem(chave="teclado_so_no_hub", arranjo="x")
    assert ordens.ordens_novas([outra], dispensadas) == (outra,)


def test_a_ordem_calada_continua_contada() -> None:
    """Dispensa que some sem deixar marca é o mesmo defeito do card que some.

    Ela deixaria de saber que existe uma decisão dela ali — e por isso o
    cabeçalho da §8.3 CONTA as dispensadas.
    """
    uma = ordem(arranjo="a")
    outra = ordem(chave="teclado_so_no_hub", arranjo="b")
    dispensadas = {"radio_largo_no_mesmo_hub": "a"}
    novas = ordens.ordens_novas([uma, outra], dispensadas)
    caladas = ordens.ordens_caladas([uma, outra], dispensadas)
    assert len(novas) + len(caladas) == 2


# ---------------------------------------------------------------------------
# O arranjo é assinatura de CABO — e não carrega identidade.
# ---------------------------------------------------------------------------


def test_o_arranjo_nao_carrega_serial_nem_endereco() -> None:
    """A tela desta aba vira PNG versionado; o arranjo entra nela."""
    from tests.unit import bancada_das_ordens as bancada

    leitura = ordens.Leitura(censo=bancada.censo(), entradas=bancada.entradas())
    for uma in ordens.catalogo(leitura):
        for serial in bancada.SERIAIS.values():
            assert serial.lower() not in uma.arranjo.lower()
