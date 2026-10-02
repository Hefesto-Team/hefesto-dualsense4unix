"""A vibração do jogo não espera a volta inteira do laço para ligar.

HAPTICA-RADIO-INICIO-01 (Z3, prioridade zero) — 19/09/2026.

**O DEFEITO, medido com três DualSense no rádio em 18/09:** fluxo contínuo de
8 s nos canais 3-4 do endpoint de cada controle, e o acelerômetro lido com
relógio — a vibração começou **2, 4 e 5 s** depois de o jogo começar a tocar.
A causa estava escrita no próprio laço: a ponte só troca para o modo háptica
quando `sink_esta_tocando` responde sim, e a pergunta era feita **uma vez por
volta**, a cada `RECONCILIA_S = 5.0`. Um pulso de 1,5 s podia nunca vibrar.

**E O CUSTO FOI MEDIDO ANTES DE ESCOLHER O DESENHO**, porque a sprint pede
explicitamente *"sem multiplicar as chamadas ao servidor de som"*:

    pactl list short sinks         2,9 ms
    pactl list short sink-inputs   2,6 ms

Perguntando um endpoint por vez, a volta de quatro controles gasta OITO
subprocessos. `sinks_que_tocam` responde por todos numa passada de DOIS — o
vigia é mais barato por controle que o laço que já existia.

**O VIGIA SAIU EM 28/09/2026** (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01).
Ele adivinhava o modo de cada controle a cada 0,4 s e acordava a volta quando o
palpite divergia da ponte — e, quando a ponte NÃO PODIA virar o modo dele,
acordava para sempre, o que pediu a espera da tentativa que falhou (26/09). A
volta agora acorda pelo aviso (o retrato do som, o toque de quem entra na
partida) e reconcilia quando o que ELA LEU mudou: os fluxos nos nós dos
controles do rádio. As réguas abaixo medem essa comparação, com os mesmos
casos que o vigia tinha, e o dublê segue respondendo SÓ sobre o que foi
perguntado.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.integrations import alto_falante_bt as bt

P1 = "aabbcc000001"
P2 = "aabbcc000002"


def _pactl_de_mentira(sinks: str, entradas: str) -> Any:
    chamadas: list[list[str]] = []

    def correr(cmd: list[str]) -> str | None:
        chamadas.append(cmd)
        return entradas if "sink-inputs" in cmd else sinks

    correr.chamadas = chamadas  # type: ignore[attr-defined]
    return correr


def test_uma_passada_responde_por_todos_os_sinks() -> None:
    """DOIS subprocessos, qualquer que seja o número de controles."""
    correr = _pactl_de_mentira(
        sinks="7\thef_p1\tdriver\ts16le\tRUNNING\n9\thef_p2\tdriver\ts16le\tIDLE\n",
        entradas="31\t7\t180\tprotocol-native\ts16le\n",
    )
    tocando = bt.sinks_que_tocam(["hef_p1", "hef_p2"], correr)
    assert tocando == {"hef_p1"}
    assert len(correr.chamadas) == 2, (  # type: ignore[attr-defined]
        "o custo voltou a crescer com o número de controles"
    )


def test_servidor_mudo_e_duvida_e_nao_silencio() -> None:
    """``None`` não é conjunto vazio — a diferença decide se a ponte cai."""
    assert bt.sinks_que_tocam(["hef_p1"], lambda _c: None) is None
    assert bt.sinks_que_tocam(["hef_p1"], lambda _c: "") == set()


def test_a_forma_singular_continua_valendo() -> None:
    """`sink_esta_tocando` passou a ser fachada, e o contrato dela não muda."""
    correr = _pactl_de_mentira(
        sinks="7\thef_p1\td\ts\tRUNNING\n", entradas="31\t7\t180\tp\ts\n"
    )
    assert bt.sink_esta_tocando("hef_p1", correr) is True
    assert bt.sink_esta_tocando("hef_p2", correr) is False
    assert bt.sink_esta_tocando("hef_p1", lambda _c: None, na_duvida=True) is True
    assert bt.sink_esta_tocando("hef_p1", lambda _c: None, na_duvida=False) is False


class _Endpoint:
    def __init__(self, nome: str) -> None:
        self.nome = nome


def _subsystem(
    *, endpoints: dict[str, str], no_radio: set[str] | None = None, viu: set[str] | None
) -> Any:
    """O subsystem montado por `__new__`: o que ele lê mora no corpo da classe."""
    quem = object.__new__(af.AltoFalanteSubsystem)
    quem._endpoints = {u: _Endpoint(n) for u, n in endpoints.items()}  # type: ignore[attr-defined]
    quem._no_radio = frozenset(no_radio if no_radio is not None else endpoints)  # type: ignore[attr-defined]
    quem._o_que_a_volta_viu = None if viu is None else frozenset(viu)  # type: ignore[attr-defined]
    return quem


def _som(uniq: str) -> str:
    """O nome do `hefesto_som_<hex6>` daquele controle, como a volta o pede."""
    return bt.nome_do_sink(uniq)


def _com_tocando(monkeypatch: pytest.MonkeyPatch, resposta: object) -> None:
    """O servidor de som de mentira — **e ele só responde sobre o que foi"""

    def falso(nomes: Any) -> Any:
        if isinstance(resposta, Exception):
            raise resposta
        if resposta is None:
            return None
        pedidos = {n for n in nomes if n}
        return {n for n in resposta if n in pedidos}  # type: ignore[union-attr]

    monkeypatch.setattr(bt, "sinks_que_tocam", falso)


def test_o_jogo_que_comeca_a_tocar_acorda_a_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """É o defeito de 18/09: o jogo abre o endpoint e a volta não sabe."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu=set())
    _com_tocando(monkeypatch, {"hef_p1"})
    assert quem._a_mesa_do_som_mudou() is True


def test_o_som_que_comeca_acorda_a_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """RADIO-AFOGADO-01, 22/09/2026 — o nó de som também é entrada da volta."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu=set())
    _com_tocando(monkeypatch, {_som(P1)})
    assert quem._a_mesa_do_som_mudou() is True


def test_o_som_de_quem_nao_tem_endpoint_tambem_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem âncora USB não há endpoint de háptica, e o alto-falante segue sendo dele."""
    quem = _subsystem(endpoints={}, no_radio={P2}, viu=set())
    _com_tocando(monkeypatch, {_som(P2)})
    assert quem._a_mesa_do_som_mudou() is True


def test_a_mesa_ociosa_nao_acorda_a_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quatro controles parados, nenhum fluxo: não há o que reconciliar."""
    quem = _subsystem(endpoints={P1: "hef_p1", P2: "hef_p2"}, viu=set())
    _com_tocando(monkeypatch, set())
    assert quem._a_mesa_do_som_mudou() is False


def test_o_som_que_para_acorda_para_derrubar_a_ponte(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: ponte de pé sem ninguém tocando desce na volta, e não em 5 s."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu={_som(P1)})
    _com_tocando(monkeypatch, set())
    assert quem._a_mesa_do_som_mudou() is True


def test_o_jogo_que_fecha_tambem_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem ele o alto-falante fica mudo até a volta inteira."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu={"hef_p1"})
    _com_tocando(monkeypatch, set())
    assert quem._a_mesa_do_som_mudou() is True


def test_nada_mudou_nao_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acordar sem mudança devolveria a tempestade que a sprint do vigia vetou."""
    quem = _subsystem(endpoints={P1: "hef_p1", P2: "hef_p2"}, viu={"hef_p1", _som(P2)})
    _com_tocando(monkeypatch, {"hef_p1", _som(P2)})
    assert quem._a_mesa_do_som_mudou() is False


def test_servidor_mudo_nao_mexe_em_ponte_nenhuma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um `pactl` que falhou não pode derrubar a ponte de um jogo aberto."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu={"hef_p1"})
    _com_tocando(monkeypatch, None)
    assert quem._a_mesa_do_som_mudou() is False


def test_sem_no_nenhum_nem_pergunta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem controle no rádio não há o que olhar — e nenhum subprocesso é gasto."""
    chamou: list[int] = []
    monkeypatch.setattr(
        bt, "sinks_que_tocam", lambda _n: chamou.append(1) or set()
    )
    quem = _subsystem(endpoints={}, no_radio=set(), viu=set())
    assert quem._a_mesa_do_som_mudou() is False
    assert chamou == [], "perguntou ao servidor de som sem ter o que perguntar"


def test_a_excecao_nao_derruba_a_thread_do_som(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quem = _subsystem(endpoints={P1: "hef_p1"}, viu=set())
    _com_tocando(monkeypatch, RuntimeError("sem servidor"))
    assert quem._a_mesa_do_som_mudou() is False
