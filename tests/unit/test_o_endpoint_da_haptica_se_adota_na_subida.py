"""O-ENDPOINT-DA-HAPTICA-SE-ADOTA-NA-SUBIDA-01: a subida não derruba o nó do aparelho da mesa.

O serviço sobe com o nó da háptica de um controle da mesa de pé (o jogo escreve nele) e o
gadget ainda não montado: a varredura dos órfãos o deixa vivo, e quando a porta monta o
``iniciar`` o adota pela âncora declarada. O ``pactl`` é o de mentira da mesa da háptica.

A MORDIDA (executada, com o md5 conferido na volta): a lista do que se espera de volta a só
quem tem porta ou endpoint na memória → ``test_a_subida_sem_o_gadget_nao_derruba_o_no_da_mesa``
reprova com o ``unload-module``.
"""
from __future__ import annotations

from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit import porta_de_mentira as porta
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h
from tests.unit.test_todo_pad_tem_porta_propria import _chega, mesa  # noqa: F401


def _no_da_sessao_de_antes(m: Any, uniq: str, interface: str) -> str:
    """O nó que o serviço de antes deixou de pé na porta do aparelho, com o relógio dele."""
    props = " ".join(f"{k}={v}" for k, v in h._SONY.items())
    resposta = m.servidor([
        "pactl", "load-module", "module-null-sink", f"sink_name={eh.nome_do_endpoint(uniq)}",
        "channels=4", f'sink_properties="{props} sysfs.path={interface} '
        f'priority.driver={eh.PRIORIDADE_DO_RELOGIO}"',
    ])
    m.servidor.cargas.clear()
    return str(resposta).strip()


@pytest.mark.parametrize("uniq", [h._P1, h._P2, h._P3, h._P4])
def test_a_subida_sem_o_gadget_nao_derruba_o_no_da_mesa(mesa: Any, uniq: str) -> None:  # noqa: F811
    """D-1911-O-NO-DA-MESA-ESPERA-A-PORTA-PARA-SE-ADOTAR: a subida deixa o nó, a porta o adota."""
    interface = porta.interface_da_porta(h._LUGAR[uniq])
    herdado = _no_da_sessao_de_antes(mesa, uniq, interface)
    controle = _chega(mesa, uniq)
    with structlog.testing.capture_logs() as registros:
        mesa.volta(controle)
    assert mesa.servidor.quedas == [], "a subida derrubou o nó em que o jogo escreve"
    assert not [r for r in registros if r["event"] == "haptica_endpoints_orfaos_derrubados"]
    porta.dar_porta(uniq, h._LUGAR[uniq])
    with structlog.testing.capture_logs() as registros:
        mesa.volta(controle)
    adotados = [r for r in registros if r["event"] == "haptica_endpoint_adotado"]
    assert [r["controle"] for r in adotados] == [eh.marca_do_aparelho(uniq)]
    assert herdado not in mesa.servidor.quedas
    assert eh.nome_do_endpoint(uniq) not in mesa.servidor.cargas, "o nó subiu de novo"


def test_o_no_de_quem_saiu_da_mesa_cai(mesa: Any) -> None:  # noqa: F811
    """D-1911-O-NO-DA-MESA-ESPERA-A-PORTA-PARA-SE-ADOTAR: o nó de quem saiu da mesa cai."""
    herdado = _no_da_sessao_de_antes(mesa, h._P2, porta.interface_da_porta(2))
    mesa.volta(_chega(mesa, h._P3))
    assert herdado in mesa.servidor.quedas


def test_o_no_na_porta_de_outro_da_mesa_cai(mesa: Any) -> None:  # noqa: F811
    """D-1911-O-NO-DA-MESA-ESPERA-A-PORTA-PARA-SE-ADOTAR: a porta de outro nunca é dele."""
    alheia = porta.dar_porta(h._P1, 1)
    herdado = _no_da_sessao_de_antes(mesa, h._P3, alheia)
    mesa.volta(_chega(mesa, h._P1), _chega(mesa, h._P3))
    assert herdado in mesa.servidor.quedas
