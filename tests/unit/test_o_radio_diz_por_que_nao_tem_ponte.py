"""OS-QUATRO-EM-HARMONIA-01, item 3: o controle pelo rádio sem ponte diz por quê.

Medido em 14/10/2026 (10h42 a 10h45): com quatro controles na mesa, o Cosmic Red
pelo rádio passou a rodada inteira sem ponte de som e vibração, e o diário não
tinha uma linha sobre ele. O laço das pontes caía num ``continue`` calado. Agora
cada controle diz, com o endereço dele e só na borda, o que falta: o jogo não
abriu o endpoint dele, o jogo não joga com ele, a vibração em 0, a recusa do
governador do rádio. Vale de 1 a 4 controles, cada um com o seu motivo.
"""

from __future__ import annotations

from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
    MOTIVO_SEM_MEDIDA,
    Recusa,
)
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import mesa  # noqa: F401

_QUATRO = (h._P1, h._P2, h._P3, h._P4)


def _no_radio(n: int) -> Any:
    return h._Controle(_QUATRO[n], "bt", f"/dev/hidraw{n + 1}")


def _sem_ponte(diario: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(r["uniq"], r["motivo"]) for r in diario if r["event"] == "som_radio_sem_ponte"]


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_cada_um_sem_ponte_diz_por_que_uma_vez(mesa: h._Mesa, quantos: int) -> None:  # noqa: F811
    """O jogo aberto só no último: os outros dizem que o jogo não abriu o deles.

    MORDIDA: tire o ``_dizer_por_que_sem_ponte`` da ponte ociosa em
    ``_casar_as_pontes`` e o diário fica calado sobre quem não tem ponte.
    """
    controles = [_no_radio(n) for n in range(quantos)]
    ultimo = _QUATRO[quantos - 1]
    mesa.volta(*controles)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(ultimo))
    with structlog.testing.capture_logs() as diario:
        mesa.volta(*controles)
        mesa.volta(*controles)
    ditos = _sem_ponte(diario)
    assert [u for u, _m in ditos] == [], "a borda já foi dita na primeira volta"
    assert ultimo in mesa.sub._pontes, "premissa: o jogo abriu o endpoint do último"
    assert set(mesa.sub._sem_ponte_porque) == set(_QUATRO[: quantos - 1])
    for uniq in _QUATRO[: quantos - 1]:
        assert "não abriu" in mesa.sub._sem_ponte_porque[uniq]


def test_a_borda_volta_quando_o_jogo_fecha(mesa: h._Mesa) -> None:  # noqa: F811
    um = _no_radio(0)
    with structlog.testing.capture_logs() as diario:
        mesa.volta(um)
    assert [u for u, _m in _sem_ponte(diario)] == [h._P1]
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(h._P1))
    mesa.volta(um)
    assert h._P1 not in mesa.sub._sem_ponte_porque, "a ponte subiu e o motivo ficou"
    mesa.servidor.jogo_em.clear()
    with structlog.testing.capture_logs() as diario:
        mesa.volta(um)
    assert [u for u, _m in _sem_ponte(diario)] == [h._P1]


def test_a_recusa_do_governador_vai_ao_diario_com_a_frase(mesa: h._Mesa) -> None:  # noqa: F811
    class _Cheio:
        def pedir_vaga(self, uniq: str, tipo: str) -> Recusa:
            return Recusa(uniq=uniq, adaptador="", tipo=tipo, motivo=MOTIVO_SEM_MEDIDA, n_max=2)

    mesa.sub.governador = _Cheio()
    um, dois = _no_radio(0), _no_radio(1)
    mesa.volta(um, dois)
    mesa.servidor.jogo_em.update({eh.nome_do_endpoint(h._P1), eh.nome_do_endpoint(h._P2)})
    with structlog.testing.capture_logs() as diario:
        mesa.volta(um, dois)
        mesa.volta(um, dois)
    ditos = _sem_ponte(diario)
    assert sorted(u for u, _m in ditos) == [h._P1, h._P2], ditos
    assert all("recusou a vaga" in m and "2 controles" in m for _u, m in ditos), ditos
