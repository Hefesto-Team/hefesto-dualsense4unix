"""O ALTO-FALANTE DIZ ATIVO — O-ALTO-FALANTE-DIZ-ATIVO-01 (23/09/2026).

A queixa dela, com a foto da aba Controles:

    *"E pq o autofalante do controle iniciou como canal dormindo ao invés de
    ativo (esse dormindo deveria ser Desativado) tipo o termo do botão."*
    <!-- noqa-acento: citação literal dela -->

Esta régua cobra as duas metades da sprint:

1. **O PEDIDO DE VAGA NÃO DERRUBA A PONTE.** O ``pedir_vaga`` do governador roda
   o ``plano_de_radio`` sem ``try``, e o chamador em
   ``daemon/subsystems/alto_falante.py`` não protegia: a exceção subia até
   ``_reconciliar`` e nenhuma ponte da mesa subia naquela volta — nem o nó era
   publicado. **A mordida:** tire o ``try`` em volta do ``pedir_vaga`` e os dois
   testes da seção 1 reprovam com a exceção do governador.

Nada aqui abre socket de Bluetooth, fala com o servidor de som dela nem escreve
no diário dela: a ponte, a fonte e o servidor são dublês, e o governador que
levanta é o de verdade com o ``plano_de_radio`` trocado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import plano_de_radio

ADAPTADOR_A = "aa:bb:cc:00:00:a1"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
CONTROLE_4 = "aa:bb:cc:00:00:04"


# ---------------------------------------------------------------------------
# 1. o pedido de vaga que levanta não derruba a ponte
# ---------------------------------------------------------------------------
@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


class _PonteDeMentira:
    """A ponte do rádio sem hidraw: sobe, guarda a vaga e a devolve ao descer."""

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.vaga = kw.get("vaga")
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        if self.vaga is not None:
            self.vaga.subiu("som")
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        if self.vaga is not None:
            self.vaga.soltar("desceu")
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    def terminou_sozinha(self) -> bool:
        return False


class _GovernadorQueLevanta:
    """A régua que a sprint pede: todo pedido de vaga levanta.

    Tem a mesma assinatura do ``GovernadorDoRadio.pedir_vaga`` — e só ela,
    porque ``_casar_as_pontes`` só chama ela.
    """

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str]] = []

    def pedir_vaga(self, uniq: str, tipo: str) -> Any:
        self.pedidos.append((uniq, tipo))
        raise RuntimeError("o plano do rádio caiu")


@pytest.fixture
def som(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O subsystem com todo contato com o sistema trocado por dublê."""
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import filho_de_som as fs

    _PonteDeMentira.criadas = []

    def _fonte(no: str, **_kw: Any) -> tuple[Any, str, str]:
        return (lambda _n: b""), f"gravador:{no}", ""

    # ALGUÉM ESTÁ TOCANDO em todo controle: é o único caso em que a ponte do som
    # sob demanda (RADIO-AFOGADO-01) chega a pedir vaga.
    monkeypatch.setattr(af, "sink_esta_tocando", lambda nome, *_a, **_k: True)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(fs, "derrubar_leitor_de_pipe", lambda *_a, **_k: None)
    monkeypatch.setattr(eh, "ancoras", lambda *a, **k: [])
    monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
    monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
    monkeypatch.setattr(af, "sinks_com_motores", lambda *a, **k: [])
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    return mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])


def test_o_governador_que_levanta_nao_derruba_a_ponte(som: Any) -> None:
    """Todo pedido levanta, e as duas pontes sobem como antes do governador.

    SEM VAGA, e é o «não sei»: a ponte que sobe aqui é a mesma que subia antes
    de o governador existir — e a mesma do dublê montado por ``__new__``.

    MORDIDA: tire o ``try`` em volta do ``pedir_vaga`` e a volta levanta
    ``RuntimeError: o plano do rádio caiu``.
    """
    governador = _GovernadorQueLevanta()
    som.governador = governador
    som._casar_as_pontes([_Controle(CONTROLE_2), _Controle(CONTROLE_3)])
    assert sorted(som._pontes) == [CONTROLE_2, CONTROLE_3], (
        "o pedido de vaga que levanta derrubou a subida da ponte"
    )
    assert all(p.vaga is None for p in som._pontes.values())
    assert governador.pedidos == [(CONTROLE_2, "som"), (CONTROLE_3, "som")]
    assert som._esperando_vaga == frozenset(), "«não sei» virou espera por vaga"
    assert not som._ponte_recusada, "«não sei» virou recusa, e a recusa apaga o nó"


def test_o_plano_do_radio_que_levanta_no_governador_de_verdade(
    som: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho REAL da exceção: o terceiro controle no mesmo adaptador.

    As duas primeiras pontes cabem no adaptador e ganham vaga sem perguntar a
    ninguém. A terceira chega ao adaptador cheio, e é aí — só aí — que o
    governador pergunta ao ``plano_de_radio`` para onde mover. Se o plano cai,
    a terceira sobe sem vaga e as duas primeiras ficam com as delas.

    MORDIDA: tire o ``try`` em volta do ``pedir_vaga`` e a volta levanta
    ``RuntimeError: o plano do rádio caiu`` no terceiro controle.
    """

    def _plano_que_cai(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("o plano do rádio caiu")

    monkeypatch.setattr(plano_de_radio, "plano_por_adaptador", _plano_que_cai)
    diario: list[tuple[Any, ...]] = []
    som.governador = gov.GovernadorDoRadio(
        medidor=None,
        adaptador_de=lambda _uniq: ADAPTADOR_A,
        registrar=lambda *a, **k: diario.append((a, k)),
        relogio=lambda: 100.0,
    )
    controles = [_Controle(u) for u in (CONTROLE_2, CONTROLE_3, CONTROLE_4)]
    som._casar_as_pontes(controles)
    assert sorted(som._pontes) == [CONTROLE_2, CONTROLE_3, CONTROLE_4], (
        "o plano do rádio que levanta derrubou a subida das pontes"
    )
    com_vaga = sorted(u for u, p in som._pontes.items() if p.vaga is not None)
    assert com_vaga == [CONTROLE_2, CONTROLE_3], (
        "as duas pontes que cabiam no adaptador perderam a vaga"
    )
    assert som._pontes[CONTROLE_4].vaga is None
