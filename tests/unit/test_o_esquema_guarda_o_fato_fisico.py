"""O esquema aprende o fato físico — ``perto``, ``alto`` e a IRMÃ de cada entrada."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    irmas_de,
    vizinhas_de_verdade,
)
from hefesto_dualsense4unix.utils.maquina import (
    CALCULADOS_DA_ENTRADA,
    MapaDaMesa,
    carregar_maquina,
    gravar_maquina,
)
from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora, mapa_dela

PARES_DO_MOCKUP: dict[str, str] = {
    "1": "2", "2": "1",
    "3": "4", "4": "3",
    "5": "6", "6": "5",
    "7": "8", "8": "7",
    "9": "10", "10": "9",
    "11": "12", "12": "11",
    "13": "14", "14": "13",
}


def test_a_face_guarda_perto_e_alto() -> None:
    """``perto`` e ``alto`` entram no esquema, e são fato DO USUÁRIO."""
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [
                {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                {"nome": "Traseira", "portas": ["3", "4"]},
                {"nome": "Hub", "portas": ["9", "10"], "alto": True},
            ]
        }
    )
    frente, traseira, hub = mapa.faces
    assert (frente.perto, frente.alto) == (True, False)
    assert (traseira.perto, traseira.alto) == (False, False), (
        "face que ela não marcou tem de nascer sem bônus nenhum"
    )
    assert (hub.perto, hub.alto) == (False, True)


def test_o_fato_fisico_sobrevive_ao_disco() -> None:
    """Ida e volta pelo ``maquina.json``: o que ela marcou continua marcado."""
    assert gravar_maquina(
        {
            "mapa": {
                "faces": [
                    {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                    {"nome": "Hub", "portas": ["9"], "alto": True},
                ],
                "portas": {"9": {"nos": ["usb1-port5", "usb2-port1"]}},
            }
        }
    )
    de_volta = carregar_maquina().mapa
    assert [(f.nome, f.perto, f.alto) for f in de_volta.faces] == [
        ("Frente", True, False),
        ("Hub", False, True),
    ]
    assert de_volta.portas["9"].nos == ["usb1-port5", "usb2-port1"]


def test_a_entrada_vazia_existe_no_esquema_sem_caminho_nenhum() -> None:
    """Uma entrada sem aparelho tem lugar no mapa — pelo NÓ, não pelo caminho."""
    mapa = MapaDaMesa.model_validate(
        {"portas": {"7": {"nos": ["usb1-port7", "usb2-port3"]}}}
    )
    vazia = mapa.portas["7"]
    assert vazia.nos == ["usb1-port7", "usb2-port3"]
    assert vazia.caminho == "1-7", "o caminho do buraco é o do lado 2.0 dos nós"
    assert "caminho" not in vazia.model_dump(exclude=set(CALCULADOS_DA_ENTRADA))


@pytest.mark.parametrize(
    "nos",
    [
        pytest.param(["porta5"], id="nome-que-nao-e-de-no"),
        pytest.param(["3-1.2"], id="caminho-de-aparelho-no-lugar-do-no"),
        pytest.param(["usb1-port5", "usb1-port5"], id="no-repetido"),
        pytest.param([f"usb1-port{n}" for n in range(9)], id="acima-do-teto"),
    ],
)
def test_o_no_torto_e_recusado(nos: list[str]) -> None:
    """A régua sabe RECUSAR — chave sem validador herda lixo."""
    with pytest.raises(ValidationError):
        MapaDaMesa.model_validate({"portas": {"7": {"nos": nos}}})


def test_a_irma_bate_com_o_desenho_dela_entrada_por_entrada() -> None:
    """As catorze irmãs saem iguais às que o usuário escreveu à mão no mockup."""
    achadas = irmas_de(mapa_dela())
    assert achadas == PARES_DO_MOCKUP, (
        "a irmã derivada divergiu do desenho dela: "
        f"faltam {sorted(set(PARES_DO_MOCKUP) - set(achadas))}, "
        f"sobram {sorted(set(achadas) - set(PARES_DO_MOCKUP))}"
    )


def test_a_irma_responde_com_o_gabinete_inteiro_vazio() -> None:
    """Nenhum aparelho na mesa, e as catorze irmãs continuam de pé."""
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [
                {"nome": "Frente", "portas": ["1", "2"], "perto": True},
                {"nome": "Traseira", "portas": ["3", "4", "5", "6", "7", "8"]},
            ]
        }
    )
    assert vizinhas_de_verdade(mapa, bancada_de_agora().censo()) == ()
    assert irmas_de(mapa) == {
        "1": "2", "2": "1", "3": "4", "4": "3", "5": "6", "6": "5", "7": "8",
        "8": "7",
    }


def test_a_fileira_impar_deixa_a_ultima_sem_irma_e_a_esticada_de_fora() -> None:
    """A ``15`` não tem irmã, e a ``15a`` também não — as duas por motivos."""
    irmas = irmas_de(mapa_dela())
    assert "15" not in irmas
    assert "15a" not in irmas


def test_a_irma_nao_e_a_vizinha_da_fileira() -> None:
    """Na fileira do hub, a ``9`` é irmã da ``10`` — e NÃO da ``11``."""
    irmas = irmas_de(mapa_dela())
    assert irmas["9"] == "10"
    assert irmas["10"] == "9", "a relação tem de ser recíproca"
    assert irmas["11"] == "12"


def test_o_mapa_de_ontem_continua_valendo() -> None:
    """Campo novo sem bump de versão: o mapa dela, sem ``perto`` nem ``nos``."""
    antigo = mapa_dela()
    assert all(not f.perto and not f.alto for f in antigo.faces)
    assert antigo.portas["1"].nos == ["usb1-port3"] and antigo.portas["1"].caminho == "1-3"
    assert antigo.portas["7"].nos == ["usb4-port4"] and antigo.portas["7"].caminho == "4-4"
    assert irmas_de(antigo)["1"] == "2", (
        "o desenho dela responde sem uma linha de campo novo declarada"
    )
