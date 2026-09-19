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
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.integrations import alto_falante_bt as bt

P1 = "aabbcc000001"
P2 = "aabbcc000002"


# ---------------------------------------------------------------------------
# A forma plural — uma passada para todos
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# O vigia — encurta a espera, e só isso
# ---------------------------------------------------------------------------


class _Endpoint:
    def __init__(self, nome: str) -> None:
        self.nome = nome


def _subsystem(*, endpoints: dict[str, str], modos: dict[str, str]) -> Any:
    quem = object.__new__(af.AltoFalanteSubsystem)
    quem._endpoints = {u: _Endpoint(n) for u, n in endpoints.items()}  # type: ignore[attr-defined]
    quem._modo_da_ponte = dict(modos)  # type: ignore[attr-defined]
    return quem


def _com_tocando(monkeypatch: pytest.MonkeyPatch, resposta: object) -> None:
    def falso(_nomes: Any) -> Any:
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(bt, "sinks_que_tocam", falso)


def test_o_jogo_que_comeca_a_tocar_acorda_a_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """É o defeito de 18/09: a ponte em «som» com o jogo já tocando."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "som"})
    _com_tocando(monkeypatch, {"hef_p1"})
    assert quem._o_modo_de_alguem_mudou() is True


def test_o_jogo_que_fecha_tambem_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: sem ele o alto-falante fica mudo até a volta inteira."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "haptica"})
    _com_tocando(monkeypatch, set())
    assert quem._o_modo_de_alguem_mudou() is True


def test_nada_mudou_nao_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acordar a cada fatia devolveria a tempestade de `pactl` que a sprint veta."""
    quem = _subsystem(
        endpoints={P1: "hef_p1", P2: "hef_p2"},
        modos={P1: "haptica", P2: "som"},
    )
    _com_tocando(monkeypatch, {"hef_p1"})
    assert quem._o_modo_de_alguem_mudou() is False


def test_servidor_mudo_nao_mexe_em_ponte_nenhuma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um `pactl` que falhou não pode derrubar a ponte de um jogo aberto."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "haptica"})
    _com_tocando(monkeypatch, None)
    assert quem._o_modo_de_alguem_mudou() is False


def test_sem_endpoint_nem_pergunta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem endpoint não há o que vigiar — e nenhum subprocesso é gasto."""
    chamou: list[int] = []
    monkeypatch.setattr(
        bt, "sinks_que_tocam", lambda _n: chamou.append(1) or set()
    )
    quem = _subsystem(endpoints={}, modos={})
    assert quem._o_modo_de_alguem_mudou() is False
    assert chamou == [], "perguntou ao servidor de som sem ter o que perguntar"


def test_a_excecao_nao_derruba_a_thread_do_som(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "som"})
    _com_tocando(monkeypatch, RuntimeError("sem servidor"))
    assert quem._o_modo_de_alguem_mudou() is False


def test_a_cadencia_cabe_na_prova_de_pronto() -> None:
    """*"a vibração ligando em menos de 0,5 s"* — a sprint, virada número."""
    assert af.VIGIA_DO_MODO_S <= 0.5
    assert af.VIGIA_DO_MODO_S < af.RECONCILIA_S
    fatias = int(af.RECONCILIA_S / af.VIGIA_DO_MODO_S)
    assert fatias >= 10, "poucas fatias: a espera volta a ser a volta inteira"
