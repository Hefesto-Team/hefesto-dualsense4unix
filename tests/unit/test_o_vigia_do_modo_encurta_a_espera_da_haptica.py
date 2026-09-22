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


def _subsystem(
    *, endpoints: dict[str, str], modos: dict[str, str], jogando: set[str] | None = None
) -> Any:
    quem = object.__new__(af.AltoFalanteSubsystem)
    quem._endpoints = {u: _Endpoint(n) for u, n in endpoints.items()}  # type: ignore[attr-defined]
    quem._modo_da_ponte = dict(modos)  # type: ignore[attr-defined]
    if jogando is not None:
        quem._jogando = frozenset(j.lower() for j in jogando)  # type: ignore[attr-defined]
    return quem


def _som(uniq: str) -> str:
    """O nome do `hefesto_som_<hex6>` daquele controle, como o vigia o pede."""
    return bt.nome_do_sink(uniq)


def _com_tocando(monkeypatch: pytest.MonkeyPatch, resposta: object) -> None:
    """O servidor de som de mentira — **e ele só responde sobre o que foi
    PERGUNTADO**.

    RADIO-AFOGADO-01, 22/09/2026, e isto foi achado pela mordida: até aqui o
    dublê devolvia a resposta inteira ignorando os nomes recebidos, e por isso
    era mais FROUXO que o produto. Com ele, arrancar `nome_do_sink` da pergunta
    do vigia deixava as catorze réguas VERDES — a régua do alto-falante passava
    sobre uma pergunta que nunca fora feita.
    """

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
    """É o defeito de 18/09: a ponte em «som» com o jogo já tocando."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "som"}, jogando={P1})
    _com_tocando(monkeypatch, {"hef_p1", _som(P1)})
    assert quem._o_modo_de_alguem_mudou() is True


def test_o_som_que_comeca_acorda_a_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """RADIO-AFOGADO-01, 22/09/2026 — o lado que o vigia não via.

    A ponte do som passou a só existir com som; sem esta linha, o primeiro som
    de cada partida espera a volta INTEIRA (`RECONCILIA_S`, 5 s) em vez de
    `VIGIA_DO_MODO_S` (0,4 s).

    MORDIDA: tire `nome_do_sink` da pergunta do vigia — o alto-falante some da
    passada, o vigia não vê nada mudar e devolve `False`.
    """
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={})
    _com_tocando(monkeypatch, {_som(P1)})
    assert quem._o_modo_de_alguem_mudou() is True


def test_a_mesa_ociosa_nao_acorda_a_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quatro controles parados, nenhuma ponte: não há o que reconciliar.

    Sem isto a cura se pagaria com uma reconciliação a cada 0,4 s — a
    tempestade de `pactl` que a sprint do vigia veta.
    """
    quem = _subsystem(endpoints={P1: "hef_p1", P2: "hef_p2"}, modos={})
    _com_tocando(monkeypatch, set())
    assert quem._o_modo_de_alguem_mudou() is False


def test_o_som_que_para_derruba_a_ponte(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: ponte de pé sem ninguém tocando é a enxurrada de volta."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "som"})
    _com_tocando(monkeypatch, set())
    assert quem._o_modo_de_alguem_mudou() is True


def test_o_endpoint_de_quem_o_jogo_nao_le_nao_acorda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O palpite do vigia usa os DOIS sinais, como a volta.

    Sem `self._jogando`, um endpoint tocando num controle que o jogo não lê
    faria o vigia pedir háptica, a volta recusar, e o vigia pedir de novo — 2,5
    reconciliações por segundo, para sempre.
    """
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={}, jogando=set())
    _com_tocando(monkeypatch, {"hef_p1"})
    assert quem._o_modo_de_alguem_mudou() is False


def test_o_jogo_que_fecha_tambem_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: sem ele o alto-falante fica mudo até a volta inteira."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "haptica"}, jogando={P1})
    _com_tocando(monkeypatch, set())
    assert quem._o_modo_de_alguem_mudou() is True


def test_nada_mudou_nao_acorda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acordar a cada fatia devolveria a tempestade de `pactl` que a sprint veta."""
    quem = _subsystem(
        endpoints={P1: "hef_p1", P2: "hef_p2"},
        modos={P1: "haptica", P2: "som"},
        jogando={P1},
    )
    _com_tocando(monkeypatch, {"hef_p1", _som(P2)})
    assert quem._o_modo_de_alguem_mudou() is False


def test_servidor_mudo_nao_mexe_em_ponte_nenhuma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um `pactl` que falhou não pode derrubar a ponte de um jogo aberto."""
    quem = _subsystem(endpoints={P1: "hef_p1"}, modos={P1: "haptica"}, jogando={P1})
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
