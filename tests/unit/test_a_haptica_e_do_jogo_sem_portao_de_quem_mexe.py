"""A háptica do jogo chega ao controle antes do primeiro toque, no cabo e no rádio.

O portão de quem mexeu (D-2609-QUEM-JOGA-E-QUEM-MEXE) segurava a háptica de um
controle até a mão dele se mover. Era um veto ao que o jogo toca no endpoint
dele (o Sackboy abre a cena sem ninguém tocar). Estas réguas fixam o contrário:
o que o jogo toca no endpoint de um controle chega a ele, e só a ele.

MORDIDAS: ``_abre`` de volta no laço do cabo (``_casar_o_cabo``) com
``quem_mexe``, e o ``este_joga`` de volta na condição ``leva`` da ponte.
"""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.haptica_do_cabo import VOLUME_ABERTO
from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import (  # noqa: F401
    _P1,
    _P2,
    _P3,
    _P4,
    _Controle,
    _Mesa,
    _no_cabo,
    mesa,
)

_QUATRO = (_P1, _P2, _P3, _P4)
_PADRAO = f"{HAPTICA_PCT_PADRAO / 100:.4f}"
_APARELHOS = (("3-8", 28), ("3-7", 29), ("3-6", 30), ("3-5", 31))
_FONTE = pathlib.Path(mod.__file__)


def _volumes(m: _Mesa, uniq: str) -> list[str]:
    return m.servidor.volumes[m.servidor.fluxo_do_laco(uniq)]


def _no_radio(m: _Mesa, numero: int) -> _Controle:
    uniq = _QUATRO[numero - 1]
    m.assentos[uniq] = numero
    return _Controle(uniq, "bt", f"/dev/hidraw{numero}")


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_no_cabo_a_haptica_do_jogo_chega_sem_toque_a_todo_controle(
    mesa: _Mesa, quantos: int  # noqa: F811
) -> None:
    """Fluxo no endpoint e nenhum toque: os traseiros do laço levam o ganho."""
    controles = [
        _no_cabo(mesa, uniq, n, *_APARELHOS[n - 1]) for n, uniq in enumerate(_QUATRO[:quantos], 1)
    ]
    mesa.servidor.jogo_em.update(eh.nome_do_endpoint(u) for u in _QUATRO[:quantos])
    mesa.volta(*controles)
    for uniq in _QUATRO[:quantos]:
        assert _volumes(mesa, uniq) == [VOLUME_ABERTO, VOLUME_ABERTO, _PADRAO, _PADRAO], (
            f"o laço de {uniq} segurou a háptica do jogo"
        )


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_no_radio_a_ponte_sobe_e_leva_a_haptica_sem_toque(
    mesa: _Mesa, quantos: int  # noqa: F811
) -> None:
    """Fluxo no endpoint e nenhum toque: a ponte do rádio sobe e leva a háptica."""
    controles = [_no_radio(mesa, n) for n in range(1, quantos + 1)]
    mesa.servidor.jogo_em.update(eh.nome_do_endpoint(u) for u in _QUATRO[:quantos])
    mesa.volta(*controles)
    for uniq in _QUATRO[:quantos]:
        assert uniq in mesa.sub._pontes, f"a ponte de {uniq} não subiu antes do primeiro toque"
        assert mesa.sub._leva_da_ponte.get(uniq) is True
        assert uniq not in mesa.sub._sem_ponte_porque


def test_so_quem_tem_fluxo_no_endpoint_recebe_no_radio(mesa: _Mesa) -> None:  # noqa: F811
    """Jogo individualizado: o fluxo do P2 e do P4 chega a eles, e o P1 e o P3 ficam sem."""
    controles = [_no_radio(mesa, n) for n in range(1, 5)]
    mesa.servidor.jogo_em.update({eh.nome_do_endpoint(_P2), eh.nome_do_endpoint(_P4)})
    mesa.volta(*controles)
    assert {u for u in _QUATRO if mesa.sub._leva_da_ponte.get(u) is True} == {_P2, _P4}
    assert _P1 in mesa.sub._sem_ponte_porque and _P3 in mesa.sub._sem_ponte_porque


def test_no_cabo_o_laco_de_cada_um_leva_o_endpoint_do_proprio_dono(mesa: _Mesa) -> None:  # noqa: F811
    """Dois no cabo, fluxo só no P2: o laço do P2 captura o endpoint do P2, e só ele."""
    p1 = _no_cabo(mesa, _P1, 1, *_APARELHOS[0])
    p2 = _no_cabo(mesa, _P2, 2, *_APARELHOS[1])
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_P2))
    mesa.volta(p1, p2)
    capturas = {lig[0]: lig[1] for lig in mesa.lacos.ligacoes}
    assert len(capturas) == 2
    assert str(mesa.servidor.indice(eh.nome_do_endpoint(_P2))) in capturas.values()
    assert str(mesa.servidor.indice(eh.nome_do_endpoint(_P1))) in capturas.values()


def test_o_portao_de_quem_mexe_nao_existe_mais_no_codigo() -> None:
    """MORDIDA: devolva ``quem_mexe`` ao laço do cabo ou à condição da ponte do rádio."""
    fonte = _FONTE.read_text(encoding="utf-8")
    assert "quem_mexe" not in fonte, "o alto-falante voltou a importar o portão"
    corpo = fonte[fonte.index("def _casar_o_cabo") :]
    corpo = corpo[: corpo.index("\n    def ", 1)]
    assert "_abre" not in corpo and "jogando" not in corpo
    ponte = fonte[fonte.index("def _casar_as_pontes") :]
    ponte = ponte[: ponte.index("\n    def ", 1)]
    assert "este_joga" not in ponte
    assert not hasattr(mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida")
