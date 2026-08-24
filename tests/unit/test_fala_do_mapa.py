"""Z6-03 — `Fala`, `Pendencia`, `NAO_MEDIDO`: a recusa mora no tipo.

A mordida da sprint: "Construir uma `Pendencia` com valor numérico ou
booleano → tem de levantar; trocar a recusa por `pass` → o teste reprova."
"""
from __future__ import annotations


import pytest

from hefesto_dualsense4unix.app.fala_do_mapa import (
    AFIRMA_NADA,
    AFIRMA_NAO_ACIONA,
    NAO_MEDIDO,
    Fala,
    Numero,
    Pendencia,
    formata_pt_br,
    frase_de_exibicao,
)


def _pendencia(**sobrescreve: object) -> Pendencia:
    base: dict[str, object] = {
        "aberta_em": "2026-08-24",
        "prazo_dias": 30,
        "quem_fecha": "a bancada, com o aparelho na mão",
        "o_que_falta": "o conteúdo do payload",
    }
    base.update(sobrescreve)
    return Pendencia(**base)  # type: ignore[arg-type]


def test_pendencia_valida_constroi() -> None:
    p = _pendencia()
    assert p.prazo_dias == 30


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("prazo_dias", 30.0),
        ("prazo_dias", True),
        ("prazo_dias", -5),
        ("prazo_dias", 0),
        ("aberta_em", 20260824),
        ("aberta_em", False),
        ("quem_fecha", 1),
        ("quem_fecha", ""),
        ("o_que_falta", 0),
    ],
)
def test_pendencia_recusa_valor_numerico_ou_booleano_ou_vazio(campo: str, valor: object) -> None:
    """MORDIDA de Z6-03 (Pendencia): número/booleano onde a casa exige prosa."""
    with pytest.raises((TypeError, ValueError)):
        _pendencia(**{campo: valor})


def test_pendencia_recusa_data_ilegivel() -> None:
    with pytest.raises(ValueError):
        _pendencia(aberta_em="24/08/2026")


def test_fala_recusa_texto_numerico_ou_booleano() -> None:
    with pytest.raises(TypeError):
        Fala(chave="a@b", lado="radio", aba="Status", texto=0, afirma=AFIRMA_NADA, porque="x")
    with pytest.raises(TypeError):
        Fala(chave="a@b", lado="radio", aba="Status", texto=False, afirma=AFIRMA_NADA, porque="x")


def test_fala_com_pendente_exige_texto_nao_medido() -> None:
    with pytest.raises(ValueError):
        Fala(
            chave="a@b",
            lado="radio",
            aba="Status",
            texto="uma frase qualquer",
            afirma=AFIRMA_NADA,
            porque="x",
            pendente=_pendencia(),
        )


def test_fala_nao_medido_exige_pendente() -> None:
    with pytest.raises(ValueError):
        Fala(
            chave="a@b",
            lado="radio",
            aba="Status",
            texto=NAO_MEDIDO,
            afirma=AFIRMA_NADA,
            porque="x",
        )


def test_fala_afirma_nada_exige_porque() -> None:
    with pytest.raises(ValueError):
        Fala(chave="a@b", lado="radio", aba="Status", texto="frase", afirma=AFIRMA_NADA, porque="")


def test_fala_texto_vazio_recusado() -> None:
    with pytest.raises(ValueError):
        Fala(chave="a@b", lado="radio", aba="Status", texto="   ", afirma=AFIRMA_NADA, porque="x")


def test_fala_valida_com_placeholder_constroi_e_exibe_frase_unica() -> None:
    fala = Fala(
        chave="audio.saida_dedicada@dualsense",
        lado="radio",
        aba="Status",
        texto=NAO_MEDIDO,
        afirma=AFIRMA_NADA,
        pendente=_pendencia(),
    )
    assert frase_de_exibicao(fala) == "Ainda não medimos isto no rádio."


def test_fala_valida_com_texto_escrito() -> None:
    fala = Fala(
        chave="identidade.cor_do_aparelho@dualsense",
        lado="radio",
        aba="Início",
        texto="No rádio o controle recusa o pedido da cor. Escolha na lista.",
        afirma=AFIRMA_NAO_ACIONA,
    )
    assert frase_de_exibicao(fala) == fala.texto


def test_numero_e_formata_pt_br() -> None:
    n = Numero(
        constante="HZ_INPUT_SEM_MIC",
        valor=260.4,
        chave="audio.microfone@dualsense",
        coluna="radio_ressalva",
    )
    assert formata_pt_br(n.valor) == "260,4"


def test_numero_recusa_valor_nao_numerico() -> None:
    with pytest.raises(TypeError):
        Numero(constante="X", valor="260,4", chave="a@b", coluna="c")  # type: ignore[arg-type]
