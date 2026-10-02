"""O número que ela escreveu no gabinete responde pelo aparelho."""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    caminho_de,
    filhas_de,
    porta_de,
    portas_livres,
    resumo_do_mapa,
    vizinhas_de_verdade,
)
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_mapa_a_bancada_de_mentira import (
    bancada_de_agora,
    mapa_dela,
)


def test_o_caminho_vira_numero_e_o_numero_vira_caminho() -> None:
    """As duas pontas da mesma amarração, incluindo a entrada por extensão."""
    mapa = mapa_dela()

    assert porta_de(mapa, "3-1.1.4") == "15a"
    assert porta_de(mapa, "3-1.2") == "9"
    assert porta_de(mapa, "1-6") == "2"
    assert caminho_de(mapa, "15a") == "3-1.1.4"
    assert caminho_de(mapa, "4") == "3-1"
    assert filhas_de(mapa, "15") == ("15a",)


def test_caminho_que_ela_nao_declarou_devolve_nada() -> None:
    """Sem declaração não há número — e a tela volta a falar como fala hoje."""
    mapa = mapa_dela()

    assert porta_de(mapa, "9-9") is None
    assert porta_de(mapa, "") is None, "caminho vazio casou com alguma entrada"
    assert caminho_de(mapa, "42") is None
    assert porta_de(MapaDaMesa(), "3-1.1.4") is None, (
        "quem nunca desenhou a mesa recebeu um número mesmo assim"
    )


def test_as_entradas_vazias_sao_as_que_ela_pode_usar() -> None:
    """A resposta que a ordem de serviço consome: onde ainda cabe um dongle."""
    livres = portas_livres(mapa_dela(), bancada_de_agora().censo())

    assert livres == ("3", "5", "6", "8", "10", "11", "12", "14"), (
        f"a lista de entradas livres mudou: {livres}"
    )
    assert "15" not in livres, (
        "a entrada que hospeda a extensão foi anunciada como livre"
    )


def test_as_duas_entradas_da_frente_sao_vizinhas_e_o_sysfs_nao_sabe() -> None:
    """O par que só o desenho DELA enxerga — e é o ponto do mapa inteiro."""
    from hefesto_dualsense4unix.integrations.mesa_de_radio import (
        vizinhancas_apertadas,
    )

    bancada = bancada_de_agora()
    mesa = bancada.mesa()

    pares = vizinhas_de_verdade(mapa_dela(), bancada.censo())

    assert pares == (("1", "2"), ), (
        f"a vizinhança pelo desenho dela mudou: {pares}"
    )
    assert vizinhancas_apertadas([*mesa.adaptadores, *mesa.radios]) == [], (
        "a vizinhança pelo sysfs passou a ver o par da frente; se isso mudou, "
        "a razão de ser da vizinhança pelo mapa mudou junto e tem de ser remedida"
    )


def test_a_entrada_por_extensao_nao_e_vizinha_da_fileira() -> None:
    """Uma entrada por extensão está a três metros de quem ficou na fileira."""
    mapa = MapaDaMesa.model_validate(
        {
            "faces": [{"nome": "Hub", "portas": ["13", "14", "15"]}],
            "portas": {
                "14": {"caminho": "3-1.1.1"},
                "15a": {"caminho": "3-1.1.4", "filha_de": "15"},
            },
        }
    )

    pares = vizinhas_de_verdade(mapa, bancada_de_agora().censo())

    assert pares == (), (
        "o dongle na ponta da extensão virou vizinho de quem ficou na fileira: "
        f"{pares}. O produto pinta de laranja um par que está a três metros"
    )


def test_o_resumo_conta_faces_entradas_e_aparelhos_colocados() -> None:
    """Os três números da linha-resumo, e nada de texto."""
    resumo = resumo_do_mapa(mapa_dela(), bancada_de_agora().censo())

    assert (resumo.faces, resumo.entradas, resumo.colocados) == (3, 15, 7), (
        f"o resumo mudou: {resumo}"
    )
    assert not resumo.vazio


def test_quem_nunca_desenhou_tem_resumo_vazio() -> None:
    """Zero entradas declaradas é estado legítimo, e a tela tem de saber disso."""
    resumo = resumo_do_mapa(MapaDaMesa(), bancada_de_agora().censo())

    assert resumo.vazio, f"o mapa vazio não se reconheceu vazio: {resumo}"
    assert (resumo.faces, resumo.entradas, resumo.colocados) == (0, 0, 0)
