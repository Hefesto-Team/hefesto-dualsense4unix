"""O estado bom sabe se dizer, e o "não sei" não se disfarça dele."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens


def uma_ordem(chave: str = "radio_largo_no_mesmo_hub") -> ordens.Ordem:
    linha = ordens.Linha(texto="tanto faz", selo=ordens.MEDIDO_AQUI)
    return ordens.Ordem(
        chave=chave,
        acao="Mova",
        o_que_eu_vi=linha,
        por_que_importa=linha,
        ganho_esperado=linha,
    )


AS_QUATRO = {
    ordens.TOPO_HA_ORDENS: {
        "ordens": [uma_ordem()],
        "conferidas": 5,
        "sem_resposta": 0,
        "dispensadas": 0,
    },
    ordens.TOPO_ALGUMA_NAO_SOUBE: {
        "ordens": [],
        "conferidas": 5,
        "sem_resposta": 2,
        "dispensadas": 0,
    },
    ordens.TOPO_NADA_NOVO: {
        "ordens": [],
        "conferidas": 5,
        "sem_resposta": 0,
        "dispensadas": 1,
    },
    ordens.TOPO_NADA_A_MUDAR: {
        "ordens": [],
        "conferidas": 5,
        "sem_resposta": 0,
        "dispensadas": 0,
    },
}


@pytest.mark.parametrize("esperada", list(AS_QUATRO))
def test_cada_situacao_produz_o_seu_cabecalho(esperada: str) -> None:
    """Quatro situações, quatro chaves. Colapsar duas reprova aqui."""
    topo = ordens.cabecalho(**AS_QUATRO[esperada])  # type: ignore[arg-type]
    assert topo.chave == esperada


def test_as_quatro_frases_sao_distintas_duas_a_duas() -> None:
    """A MORDIDA DA ORDEM-8: colapsar o terceiro caso no segundo reprova."""
    frases = [
        ordens.cabecalho(**campos).texto  # type: ignore[arg-type]
        for campos in AS_QUATRO.values()
    ]
    assert len(set(frases)) == 4, f"duas frases colidiram: {frases}"


def test_o_nao_sei_nunca_e_verde() -> None:
    """F7: o estado em que o produto não soube **não** pode ser o estado bom."""
    topo = ordens.cabecalho(**AS_QUATRO[ordens.TOPO_ALGUMA_NAO_SOUBE])  # type: ignore[arg-type]
    assert topo.estado == "nao_sei"
    assert topo.estado != "certo"


def test_o_sem_resposta_passa_a_frente_da_dispensa() -> None:
    """A precedência é de HONESTIDADE, e não de gravidade."""
    topo = ordens.cabecalho(
        ordens=[], conferidas=5, sem_resposta=1, dispensadas=1
    )
    assert topo.chave == ordens.TOPO_ALGUMA_NAO_SOUBE
    assert topo.estado == "nao_sei"


def test_a_ordem_passa_a_frente_de_tudo() -> None:
    """Havendo o que fazer, o topo diz o que fazer — mesmo com pendências."""
    topo = ordens.cabecalho(
        ordens=[uma_ordem()], conferidas=5, sem_resposta=3, dispensadas=2
    )
    assert topo.chave == ordens.TOPO_HA_ORDENS
    assert topo.estado == "atencao"  # (noqa-acento): chave de máquina


def test_o_estado_bom_diz_quanta_coisa_conferiu() -> None:
    """A queixa dela, curada: o número e o botão. "Tudo certo" sozinho não volta."""
    topo = ordens.cabecalho(**AS_QUATRO[ordens.TOPO_NADA_A_MUDAR])  # type: ignore[arg-type]
    assert "5" in topo.texto
    assert topo.botao, "o estado bom precisa abrir a lista do que foi conferido"
    assert "está tudo certo" not in topo.texto.lower()


def test_o_estado_bom_com_dispensa_conta_a_decisao_dela() -> None:
    """Dispensa que some sem deixar marca some com uma decisão dela junto."""
    topo = ordens.cabecalho(**AS_QUATRO[ordens.TOPO_NADA_NOVO])  # type: ignore[arg-type]
    assert "1" in topo.texto
    assert topo.botao


def test_o_cabecalho_de_ordens_conta_quantas() -> None:
    topo = ordens.cabecalho(
        ordens=[uma_ordem("a"), uma_ordem("b")],
        conferidas=5,
        sem_resposta=0,
        dispensadas=0,
    )
    assert "2" in topo.texto
    assert "recomendadas" in topo.texto


def test_o_singular_e_o_plural_concordam() -> None:
    """Português: uma mudança recomendada, duas mudanças recomendadas."""
    uma = ordens.cabecalho(
        ordens=[uma_ordem()], conferidas=1, sem_resposta=0, dispensadas=0
    )
    assert "1 mudança recomendada" in uma.texto

    duas = ordens.cabecalho(
        ordens=[uma_ordem("a"), uma_ordem("b")],
        conferidas=1,
        sem_resposta=0,
        dispensadas=0,
    )
    assert "2 mudanças recomendadas" in duas.texto


def test_o_estado_de_cada_cabecalho_e_o_vocabulario_do_exame() -> None:
    """As três palavras são as de `exame_da_mesa`, e vêm de UM lugar só."""
    for campos in AS_QUATRO.values():
        topo = ordens.cabecalho(**campos)  # type: ignore[arg-type]
        assert topo.estado in {"certo", "atencao", "nao_sei"}  # (noqa-acento) estado do daemon
