"""O-TESTAR-DA-VIBRACAO-TOCA-A-FORMA-ESCOLHIDA-E-NAO-CORTA-O-PAR-FIXADO-01.

O botão «Háptica» toca a forma que o controle escolheu em «Efeito háptico» (a mesma leitura e o
mesmo tocador do toque do tiro), cabo e rádio igual, e cada controle com a sua.
"""

from __future__ import annotations

import pytest


from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af_sub
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from tests.unit.test_a_aba_vibracao_tem_o_sensor_haptico_e_dois_testes import (
    _sem_teste_ligado,  # noqa: F401
    com_toque,  # noqa: F401
)
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import mesa  # noqa: F401
from tests.unit.test_no_modo_xbox_a_haptica_fina import (
    _QUATRO,
    _no_cabo_os_quatro,
    _no_radio_os_quatro,
    _Mundo,
    _Tocador,
    mundo,  # noqa: F401
)


def _escolher(monkeypatch: pytest.MonkeyPatch, por_controle: dict[str, str]) -> None:
    """O perfil ativo, na vista que o tato vivo leu: a forma de cada controle."""
    vista = {"controllers": {u: {"rumble": {"efeito_haptico": e}} for u, e in por_controle.items()}}
    monkeypatch.setattr(tato_vivo, "_VISTA_LIDA", ("prova", vista))


def _toques(m: _Mundo, uniq: str) -> list[str]:
    return [t[0] for t in m.tocador(uniq).toques]  # type: ignore[attr-defined]


@pytest.mark.parametrize("escolha", formas.ESCOLHAS)
def test_o_haptica_toca_a_forma_escolhida_e_so_a_daquele_controle(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch, escolha: str  # noqa: F811
) -> None:
    """Cada escolha: a forma vai ao tocador do controle do usuário, e os outros ficam quietos.

    Prova da D-1610-O-TESTAR-DA-HAPTICA-TOCA-A-FORMA-ESCOLHIDA.
    """
    controles = _no_cabo_os_quatro(com_toque)
    com_toque.mesa.volta(*controles)
    outras = {u: formas.ESTALO for u in _QUATRO[1:]}
    _escolher(monkeypatch, {_QUATRO[0]: escolha, **outras})
    resposta = com_toque.sub.testar_a_haptica(_QUATRO[0], True)
    if escolha == formas.SEM_EFEITO:
        assert resposta["status"] == "sem_efeito" and resposta["motivo"]
        assert _Tocador.criados.get(eh.marca_do_aparelho(_QUATRO[0])) is None
        assert dict(com_toque.sub._teste_da_haptica) == {}
        return
    tocador = com_toque.tocador(_QUATRO[0])
    if escolha == formas.SOM_NO_CORPO:
        assert resposta["status"] == "ok" and resposta["forma"] == escolha
        assert tocador.toques == [] and tocador.nivel == (0, 0)  # type: ignore[attr-defined]
        (trecho,) = tocador.corpos  # type: ignore[attr-defined]
        assert len(trecho) > 1000 and 0 < max(trecho) <= formas.TETO_DO_CORPO
    else:
        esperada = formas.TOQUE if escolha == formas.DO_ESTILO else escolha
        assert resposta["status"] == "ok" and resposta["forma"] == esperada
        assert "par" not in resposta
        assert _toques(com_toque, _QUATRO[0]) == [esperada]
        assert tocador.nivel == (0, 0), "o par fixo não toca quando a forma toca"  # type: ignore[attr-defined]
    for outro in _QUATRO[1:]:
        dele = _Tocador.criados.get(eh.marca_do_aparelho(outro))
        assert dele is None or (dele.toques == [] and dele.nivel == (0, 0)), outro  # type: ignore[attr-defined]


def test_cada_controle_toca_a_sua_forma_em_laco_ate_o_parar(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """D-1910-O-TESTE-DA-HAPTICA-E-CONTINUO: a forma volta no tocador até o «Parar».

    O rebate da janela só renova o prazo (não toca por cima), e a forma trocada no meio vale no
    rebate seguinte.
    """
    controles = _no_cabo_os_quatro(com_toque)
    com_toque.mesa.volta(*controles)
    quatro = (formas.IMPACTO, formas.ESTALO, formas.GUARDA, formas.APARO)
    sua = dict(zip(_QUATRO, quatro, strict=True))
    _escolher(monkeypatch, sua)
    for uniq in _QUATRO:
        com_toque.sub.testar_a_haptica(uniq, True)
        com_toque.sub.testar_a_haptica(uniq, True)
    for uniq, forma in sua.items():
        assert _toques(com_toque, uniq) == [forma], f"{uniq}: o rebate tocou por cima"
        assert com_toque.tocador(uniq).tocando_em_laco, uniq  # type: ignore[attr-defined]
        assert com_toque.tocador(uniq).dono == uniq  # type: ignore[attr-defined]
    com_toque.sub.testar_a_haptica(_QUATRO[0], False)
    assert not com_toque.tocador(_QUATRO[0]).tocando_em_laco, "o Parar não soltou o laço"  # type: ignore[attr-defined]
    assert com_toque.tocador(_QUATRO[1]).tocando_em_laco, "o Parar de um soltou o outro"  # type: ignore[attr-defined]
    assert _QUATRO[0] not in dict(com_toque.sub._teste_da_haptica)
    _escolher(monkeypatch, {**sua, _QUATRO[1]: formas.TOQUE})
    com_toque.sub.testar_a_haptica(_QUATRO[1], True)
    assert _toques(com_toque, _QUATRO[1]) == [formas.ESTALO, formas.TOQUE]


def test_a_volta_do_laco_emenda_no_tocador_de_verdade() -> None:
    """O tocador real volta ao começo da forma no fim dela, e o «Parar» cala no bloco seguinte."""
    tocador = eh.TocadorDoRumble("prova")
    volta = af_sub._amostras_do_teste(formas.ESTALO)
    tocador.tocar_em_laco(volta, "centro", sink="", dono="prova", forma=formas.ESTALO)
    quadros = 0
    while quadros < 3 * len(volta):
        tocador.proximo_bloco((0, 0), (0, 0), 0)
        quadros += eh.QUADROS_POR_BLOCO
    assert tocador.tocando_o_toque and tocador.tocando_em_laco, "o laço acabou na primeira volta"
    tocador.tocar_o_toque(1.0, "centro", 40, sink="", dono="tiro")
    assert tocador.tocando_em_laco, "um toque do jogo cortou o teste"
    tocador.soltar_o_laco()
    assert not tocador.tocando_o_toque
    tocador.parar()


def test_sem_escolha_e_do_estilo_tocam_o_toque_do_que_o_jogo_faria(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    com_toque.mesa.volta(*_no_cabo_os_quatro(com_toque))
    _escolher(monkeypatch, {})
    assert com_toque.sub.testar_a_haptica(_QUATRO[0], True)["forma"] == formas.TOQUE
    assert _toques(com_toque, _QUATRO[0]) == [formas.TOQUE]


def test_do_estilo_toca_a_forma_que_o_estilo_do_perfil_pede_como_o_tiro(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """«Do estilo» segue o estilo do perfil ativo pela conta do tiro, e não um Toque digitado."""
    com_toque.mesa.volta(*_no_cabo_os_quatro(com_toque))
    monkeypatch.setattr(formas, "POR_ESTILO", {"estilo-de-prova": formas.IMPACTO})
    escolha = {"rumble": {"efeito_haptico": formas.DO_ESTILO}}
    vista = {"estilo": "estilo-de-prova", "controllers": {_QUATRO[1]: escolha}}
    monkeypatch.setattr(tato_vivo, "_VISTA_LIDA", ("prova", vista))
    assert com_toque.sub.testar_a_haptica(_QUATRO[1], True)["forma"] == formas.IMPACTO
    assert _toques(com_toque, _QUATRO[1]) == [formas.IMPACTO]


def test_o_teste_le_a_escolha_do_perfil_que_esta_ativo_agora(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A vista de outro perfil (a troca ainda não relida) não vale: toca o que o tiro tocaria."""
    com_toque.mesa.volta(*_no_cabo_os_quatro(com_toque))
    vista = {"controllers": {_QUATRO[0]: {"rumble": {"efeito_haptico": formas.SEM_EFEITO}}}}
    monkeypatch.setattr(tato_vivo, "_VISTA_LIDA", ("outro-perfil", vista))
    assert com_toque.sub.testar_a_haptica(_QUATRO[0], True)["forma"] == formas.TOQUE


def test_o_clique_em_outra_grafia_do_endereco_acha_a_escolha_dele(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A janela manda o endereço em maiúsculas; a escolha do perfil está em minúsculas."""
    com_toque.mesa.volta(*_no_radio_os_quatro(com_toque))
    _escolher(monkeypatch, {_QUATRO[3]: formas.APARO})
    resposta = com_toque.sub.testar_a_haptica(_QUATRO[3].upper(), True)
    assert resposta["forma"] == formas.APARO and resposta["uniq"] == _QUATRO[3]
    assert _toques(com_toque, _QUATRO[3]) == [formas.APARO]


def test_no_radio_a_forma_toca_pelo_tocador_do_controle_dela(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    controles = _no_radio_os_quatro(com_toque)
    com_toque.mesa.volta(*controles)
    _escolher(monkeypatch, {_QUATRO[2]: formas.GUARDA})
    resposta = com_toque.sub.testar_a_haptica(_QUATRO[2], True)
    assert resposta["forma"] == formas.GUARDA and "par" not in resposta
    assert _toques(com_toque, _QUATRO[2]) == [formas.GUARDA]


def test_no_radio_sem_fatia_a_forma_longa_cede_dizendo_e_volta_quando_ha(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A Guarda sem fatia livre toca o par e diz; com a fatia de volta ela toca e o par sai."""
    controles = _no_radio_os_quatro(com_toque)
    com_toque.mesa.volta(*controles)
    uniq = _QUATRO[2]
    _escolher(monkeypatch, {uniq: formas.GUARDA})
    com_toque.sub._esperando_vaga = [(uniq, "haptica")]
    resposta = com_toque.sub.testar_a_haptica(uniq, True)
    tocador = com_toque.tocador(uniq)
    assert resposta["par"] == list(af_sub.PAR_DO_TESTE_DA_HAPTICA)
    assert resposta["motivo_da_forma"] and tocador.toques == []  # type: ignore[attr-defined]
    assert tocador.nivel == af_sub.PAR_DO_TESTE_DA_HAPTICA
    com_toque.sub._esperando_vaga = []
    resposta = com_toque.sub.testar_a_haptica(uniq, True)
    assert "par" not in resposta and _toques(com_toque, uniq) == [formas.GUARDA]
    assert tocador.nivel == (0, 0), "o par do rebate anterior não fica por baixo da forma"
    com_toque.sub.testar_a_haptica(uniq, False)
    assert com_toque.sub._teste_no_par == frozenset()


def test_a_forma_curta_toca_no_radio_mesmo_sem_fatia(
    com_toque: _Mundo, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Só a forma LONGA cede ao rádio; o estalo, como no tiro, toca."""
    com_toque.mesa.volta(*_no_radio_os_quatro(com_toque))
    uniq = _QUATRO[0]
    _escolher(monkeypatch, {uniq: formas.ESTALO})
    com_toque.sub._esperando_vaga = [(uniq, "haptica")]
    assert com_toque.sub.testar_a_haptica(uniq, True)["forma"] == formas.ESTALO
    assert _toques(com_toque, uniq) == [formas.ESTALO]
