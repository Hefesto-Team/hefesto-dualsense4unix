#!/usr/bin/env python3
"""A TROCA QUE TIRA A ÚLTIMA SAÍDA DE EMERGÊNCIA DO PS RESPONDE.

Sprint O-QUE-A-NAVEGACAO-VELHA-DEIXOU-SEM-CHAMADOR-01.

A saída de emergência do PS é segurança: Suspender mouse e teclado (PS + Options) e Próximo modo
(PS + R3) tiram o computador das mãos do controle. A aba velha avisava quando nenhum gesto fazia
as duas; a do todo não avisava, e `acoes_do_gesto.saidas_sem_gesto` ficou sem chamador.

O que se mede, com o `machine.declare` de verdade gravando o `maquina.json` do lar de mentira:

1. tirar uma das duas saídas não responde nada, porque a outra segue valendo;
2. tirar a última responde a frase (`RuntimeError`, depois de guardar), na lista e no botão de
   tirar o gesto, em qualquer ordem;
3. um gesto removido não conta: ele deixou de disparar, mesmo guardando o que fazia;
4. outro gesto, novo ou de fábrica, que faça a saída segura a conta;
5. o PS sozinho que faz a saída também a conta.

Vale igual para os quatro controles e nos dois transportes: a tabela é da máquina, e o detector
a lê para todos. MORDIDA: tirar a chamada a `_avisar_se_sem_saida_de_emergencia` de
`acao_do_gesto` reprova 2; a de `remover_gesto`, o botão de tirar.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core import acoes_do_gesto as ag
from hefesto_dualsense4unix.integrations import steam_launcher
from tests.unit.test_o_gesto_novo_do_ps import _daemon, _gesto, _Ponte

SUSPENDER = ag.rotulo(ag.SUSPENDER)
MODO = ag.rotulo(ag.MODO_SEGUINTE)
NADA = ag.rotulo(ag.NADA)
PERFIL = ag.rotulo(ag.PERFIL_SEGUINTE)


@pytest.fixture(autouse=True)
def sem_steam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam", lambda *a, **k: True)


class _PonteQueReaplica(_Ponte):
    """A ponte do `machine.declare` de verdade, mais o que a linha PS pede ao reaplicar."""

    def chamar(self, metodo: str, **params: object) -> bool:
        return True

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> dict[str, str]:
        return {"status": "ok"}


def _ponte() -> _Ponte:
    return _PonteQueReaplica(_daemon())


def _trocar(ponte: _Ponte, gesto: str, rotulo: str) -> None:
    _gesto("acao-do-gesto")({"linha": gesto, "rotulo": rotulo, "valor": rotulo}, ponte)


def _guardado(ponte: _Ponte, gesto: str) -> str:
    """O que a máquina guardou de fato para o gesto, relido do `maquina.json`."""
    from hefesto_dualsense4unix.utils import maquina as mq

    return ag.tabela(mq.carregar_maquina())[gesto].faz


@pytest.mark.parametrize("primeiro,restante", [("ps_options", "ps_r3"), ("ps_r3", "ps_options")])
def test_tirar_a_ultima_saida_responde_e_a_penultima_nao(primeiro: str, restante: str) -> None:
    # D-1710-A-SAIDA-DE-EMERGENCIA-DO-PS-AVISA-NA-LINHA
    ponte = _ponte()
    _trocar(ponte, primeiro, NADA)
    with pytest.raises(RuntimeError) as caiu:
        _trocar(ponte, restante, NADA)
    frase = str(caiu.value)
    assert frase.startswith("guardei, e "), frase
    assert "saída de emergência" in frase, frase
    assert SUSPENDER in frase and MODO in frase, f"a frase não diz quais são: {frase}"
    assert _guardado(ponte, restante) == ag.NADA, "respondeu sem ter guardado o que ela escolheu"


def test_deixar_uma_das_duas_nao_responde() -> None:
    ponte = _ponte()
    _trocar(ponte, "ps_options", NADA)
    assert _guardado(ponte, "ps_r3") == ag.MODO_SEGUINTE


def test_o_botao_de_tirar_o_gesto_responde_igual() -> None:
    ponte = _ponte()
    _gesto("remover-gesto")({"linha": "ps_options"}, ponte)
    with pytest.raises(RuntimeError, match="saída de emergência"):
        _gesto("remover-gesto")({"linha": "ps_r3"}, ponte)


def test_o_gesto_removido_nao_conta_como_saida() -> None:
    """O de fábrica removido guarda o `faz` e não dispara: a lista não pode contá-lo."""
    ponte = _ponte()
    _gesto("remover-gesto")({"linha": "ps_options"}, ponte)
    assert _guardado(ponte, "ps_options") == ag.SUSPENDER
    with pytest.raises(RuntimeError, match="saída de emergência"):
        _trocar(ponte, "ps_r3", NADA)


@pytest.mark.parametrize("quem", ["ps_cima", "ps_l3"])
def test_outro_gesto_que_faz_a_saida_a_conta(quem: str) -> None:
    ponte = _ponte()
    _trocar(ponte, quem, SUSPENDER)
    _trocar(ponte, "ps_options", NADA)
    _trocar(ponte, "ps_r3", NADA)


def test_o_ps_sozinho_que_faz_a_saida_a_conta() -> None:
    ponte = _ponte()
    _gesto("linha-de-botao")({"linha": "ps", "valor": MODO}, ponte)
    _trocar(ponte, "ps_options", NADA)
    _trocar(ponte, "ps_r3", NADA)


def test_trocar_por_outra_saida_nao_responde() -> None:
    ponte = _ponte()
    _trocar(ponte, "ps_options", PERFIL)
    _trocar(ponte, "ps_r3", SUSPENDER)
