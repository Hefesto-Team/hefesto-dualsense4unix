"""OS-QUATRO-NO-AR-01 §2 — os quatro alto-falantes tocam juntos.

A resposta dela (citada no topo da sprint) pediu *"a mesma coisa"* para o
alto-falante. O §2 manda MEDIR antes de curar, e só curar se aparecer regra de
um-por-vez no som.

**O QUE A LEITURA DO FONTE ACHOU, 13/09/2026, e é por isso que este arquivo não
tem cura ao lado:** o `AltoFalanteSubsystem` constrói um nó e uma
`PonteDeSomPorRadio` POR `uniq` (`_casar_as_pontes`, `GerenciadorDeNosDeSom`);
cada ponte lê o monitor do nó do próprio controle e pergunta pelo microfone do
próprio controle a cada report (`functools.partial(o_microfone_esta_no_ar,
uniq)`). Não há, em `daemon/subsystems/alto_falante.py` nem em
`integrations/alto_falante_bt.py`, estado de módulo que escolha um controle:
os globais de lá são a biblioteca Opus carregada e o gancho da fonte, que
responde por `uniq`.

Então a régua fica como prova, e ela mede três coisas com quatro controles:

1. quatro nós de nome próprio e uma ponte de rádio por controle no rádio, DE PÉ
   AO MESMO TEMPO, cada uma lendo o monitor do SEU nó (as pontes são as do
   produto, secas: nenhum byte vai a aparelho nenhum);
2. o bit 0 dos enables do `0x35` — o microfone — sai em cada report com o
   estado do microfone DAQUELE controle, e não do vizinho;
3. a cena inteira: os quatro microfones postos no ar pelo ATO do produto
   (`hotkey.ligar_o_microfone`), e os quatro reports de som levando o bit do
   microfone ligado. Antes da cura do §1, só o último ligado levava.

**NENHUM TESTE DAQUI FALA COM O MUNDO**: `subprocess.run` e `subprocess.Popen`
recusam, o hidraw é `/dev/null` e a fonte de PCM é silêncio.
"""

from __future__ import annotations

import inspect
import os
import subprocess
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante, bt_mic
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele
from tests.unit.test_os_quatro_microfones_ficam_no_ar import (
    MESA_DELA,
    P1,
    P2,
    P3,
    P4,
    _apertar,
    _Backend,
    _Daemon,
    _PipeWire,
)

RADIO = "bluetooth"
CABO = "usb"

MESAS: dict[str, tuple[tuple[str, str], ...]] = {
    "a-mesa-dela": MESA_DELA,
    "os-quatro-no-radio": tuple((u, RADIO) for u, _ in MESA_DELA),
}

#: Onde mora o byte dos enables no `0x35` montado — o mesmo endereço que
#: `test_o_som_nao_desliga_o_microfone.py` lê.
POS_ENABLES = 4


@pytest.fixture(autouse=True)
def _ninguem_roda_processo(monkeypatch: pytest.MonkeyPatch) -> None:
    def _recusa(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"um teste desta régua tentou rodar processo: {args!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)


def _controles(mesa: tuple[tuple[str, str], ...]) -> list[Any]:
    return [
        SimpleNamespace(uniq=u, transporte=t, caminho=f"/dev/hidraw{i}")
        for i, (u, t) in enumerate(mesa)
    ]


class _NoDeSom:
    """O nó publicado, sem `pactl`: nome e rota do produto, `iniciar` mudo."""

    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.nome = af.nome_do_sink(uniq)
        self.rota = SimpleNamespace(tem_rota=True, motivo="")

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        return None


class _PonteDeMicComEfeito:
    """A ponte de microfone por rádio no que o SOM pergunta: `mic_no_ar`.

    Como a do produto, ela responde pelo que foi pedido por último: a palavra
    `True` põe no ar; `False` ou `None` (sem ouvinte, no dublê) não.
    """

    def __init__(self, uniq: str, caminho: str) -> None:
        self.no = SimpleNamespace(uniq=uniq, caminho=caminho)
        self.mic_no_ar = False

    def dizer_o_pedido_dela(self, ligado: bool | None) -> None:
        self.mic_no_ar = ligado is True


class _GerenciadorDeMic:
    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, nos: list[Any]) -> None:
        for no in nos:
            self.pontes.setdefault(no.caminho, _PonteDeMicComEfeito(no.uniq, no.caminho))


def _enables(com_microfone: Any) -> int:
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_035,
        fonte=lambda n: bytes(n),
        com_microfone=com_microfone,
    )
    report = bomba.um_report()
    assert report is not None, "a bomba não montou report nenhum"
    return report[POS_ENABLES]


#: A ponte DO PRODUTO, guardada antes de qualquer `monkeypatch` a trocar.
_PONTE_DO_PRODUTO = af.PonteDeSomPorRadio


def _o_microfone_no_report(pontes: dict[str, Any]) -> dict[str, bool]:
    """O bit 0 de um report montado com o que cada ponte RECEBEU na construção.

    Sem `com_microfone` a ponte do produto usa o padrão dela — lido da
    assinatura, não digitado —, para a régua reprovar pelo bit e não por uma
    chave ausente no dublê.
    """
    padrao = inspect.signature(_PONTE_DO_PRODUTO).parameters["com_microfone"].default
    return {
        uniq: _enables(kw.get("com_microfone", padrao)) == af.ENABLES_COM_MIC
        for uniq, kw in pontes.items()
    }


@pytest.fixture()
def som(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O `AltoFalanteSubsystem` do produto, com as pontes do produto SECAS."""
    lidos: dict[str, int] = {}
    fios: list[tuple[str, str]] = []
    trava = threading.Lock()

    def _fonte_do_monitor(id_do_no: str, **_k: Any) -> Any:
        def _ler(quantos: int) -> bytes:
            with trava:
                lidos[id_do_no] = lidos.get(id_do_no, 0) + 1
            threading.Event().wait(0.005)
            return bytes(quantos)

        _ler.no = id_do_no  # type: ignore[attr-defined]
        return _ler, None, ""

    verdadeira = af.PonteDeSomPorRadio

    def _ponte_seca(**kw: Any) -> Any:
        fios.append((kw["uniq"], kw["fonte_de_pcm"].no))
        kw["seco"] = True
        return verdadeira(**kw)

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte_do_monitor)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _ponte_seca)
    return SimpleNamespace(lidos=lidos, fios=fios)


def _subir(mesa: tuple[tuple[str, str], ...]) -> Any:
    sub = alto_falante.AltoFalanteSubsystem(fonte_de_controles=lambda: _controles(mesa))
    sub._abrir_hidraw = lambda _caminho: os.open(os.devnull, os.O_WRONLY)  # type: ignore[method-assign]
    gerenciador = alto_falante.GerenciadorDeNosDeSom(
        fabrica=_NoDeSom, ponte_do_radio_por_controle=sub._ponte_do_radio_de
    )
    sub._reconciliar(gerenciador)
    return sub, gerenciador


# ---------------------------------------------------------------------------
# 1. Quatro nós, uma ponte por controle no rádio, todas de pé juntas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome_da_mesa", list(MESAS))
def test_os_quatro_nos_e_as_pontes_do_radio_ficam_de_pe_juntos(
    som: Any, nome_da_mesa: str
) -> None:
    """Quatro nós de nome próprio; cada controle no rádio com a SUA ponte, de pé.

    MORDIDA: em `AltoFalanteSubsystem._casar_as_pontes`, troque
    `fonte_do_monitor_do_no(nome_do_sink(uniq))` por um nó fixo do primeiro
    controle — todas as pontes passam a ler o mesmo monitor, e o som do P1 sai
    nos quatro alto-falantes.
    """
    mesa = MESAS[nome_da_mesa]
    radio = sorted(u for u, t in mesa if t == RADIO)
    sub, gerenciador = _subir(mesa)
    try:
        assert sorted(gerenciador.nos) == sorted(u for u, _ in mesa)
        assert {no.nome for no in gerenciador.nos.values()} == {
            af.nome_do_sink(u) for u, _ in mesa
        }, "dois controles dividem o mesmo nó de som"

        pontes = sub._pontes
        assert sorted(pontes) == radio, f"pontes fora do rádio, ou faltando: {sorted(pontes)}"
        assert len({id(p) for p in pontes.values()}) == len(radio)
        assert sorted(som.fios) == sorted((u, af.nome_do_sink(u)) for u in radio), (
            f"uma ponte ficou com o monitor do nó de outro controle: {som.fios}"
        )

        prazo = time.monotonic() + 3.0
        while time.monotonic() < prazo and not (
            all(p.esta_de_pe() for p in pontes.values())
            and all(som.lidos.get(af.nome_do_sink(u), 0) > 2 for u in radio)
        ):
            threading.Event().wait(0.01)
        de_pe = {u: p.esta_de_pe() for u, p in pontes.items()}
        assert all(de_pe.values()), f"as pontes não ficaram de pé juntas: {de_pe}"
        assert set(som.lidos) == {af.nome_do_sink(u) for u in radio}, som.lidos
        assert all(som.lidos[af.nome_do_sink(u)] > 2 for u in radio), (
            f"alguma ponte não está bombeando junto com as outras: {som.lidos}"
        )
    finally:
        for ponte in list(sub._pontes.values()):
            ponte.descer(esperar_s=1.0)


# ---------------------------------------------------------------------------
# 2. O bit do microfone de cada report é o do PRÓPRIO controle
# ---------------------------------------------------------------------------


@pytest.fixture()
def fiacao(monkeypatch: pytest.MonkeyPatch) -> Any:
    """As pontes de som como o subsystem as constrói, sem thread nenhuma."""
    criadas: dict[str, dict[str, Any]] = {}

    class _PonteQueGuarda:
        def __init__(self, **kw: Any) -> None:
            criadas[kw["uniq"]] = kw
            self.motivo = ""

        def subir(self) -> bool:
            return True

        def descer(self, **_k: Any) -> bool:
            return True

    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteQueGuarda)
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda _no, **_k: ((lambda n: bytes(n)), None, "")
    )
    return criadas


def test_o_bit_do_microfone_de_cada_report_e_o_do_proprio_controle(fiacao: Any) -> None:
    """Quatro no rádio: dois microfones no ar, dois não — e cada report sabe qual.

    MORDIDA: em `_casar_as_pontes`, tire o `com_microfone=` da construção da
    ponte (ela volta ao padrão `False`) — os quatro reports saem com o
    microfone desligado, inclusive os dois que estão no ar.
    """
    mesa = MESAS["os-quatro-no-radio"]
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub_mic = bt_mic.BtMicSubsystem(registro=registro)
    sub_mic._gerenciador = _GerenciadorDeMic()
    sub_mic._gerenciador.reconciliar(_controles(mesa))
    anterior = bt.registrar_ouvinte_do_microfone(sub_mic.microfone_no_ar)
    try:
        sub = alto_falante.AltoFalanteSubsystem()
        sub._casar_as_pontes(_controles(mesa))
        assert sorted(fiacao) == sorted(u for u, _ in mesa)

        sub_mic.no_ar(P1, True)
        sub_mic.no_ar(P3, True)
        assert _o_microfone_no_report(fiacao) == {P1: True, P2: False, P3: True, P4: False}

        sub_mic.no_ar(P2, True)
        sub_mic.no_ar(P4, True)
        sub_mic.no_ar(P1, False)
        assert _o_microfone_no_report(fiacao) == {P1: False, P2: True, P3: True, P4: True}
    finally:
        bt.registrar_ouvinte_do_microfone(anterior)


# ---------------------------------------------------------------------------
# 3. A cena inteira: os quatro no ar pelo ATO, e o som levando os quatro
# ---------------------------------------------------------------------------


def test_os_quatro_no_ar_pelo_ato_e_os_quatro_reports_de_som_levam_o_microfone(
    fiacao: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O botão de cada um dos quatro, e depois o som de cada um dos quatro.

    O ato é o do produto (`hotkey.ligar_o_microfone`), com o eleitor do
    produto e o registro do produto; a ponte de microfone recebe a palavra pelo
    `_aplicar_a_palavra_dela` do supervisor; o som pergunta pelo gancho.

    MORDIDA: a do §1 — devolva o `esquecer_a_palavra` na perda do padrão (a
    guarda de `MicrofonesNoAr` em `_apagar_a_luz_de_quem_perdeu_o_canal`) e só
    o report do P4, o último ligado, sai com o microfone.
    """
    mesa = MESAS["os-quatro-no-radio"]
    pipewire = _PipeWire(monkeypatch)
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub_mic = bt_mic.BtMicSubsystem(registro=registro)
    sub_mic._gerenciador = _GerenciadorDeMic()
    backend = _Backend()
    sub_mic._backend = backend
    m = SimpleNamespace(pipewire=pipewire, backend=backend, daemon=_Daemon(backend))
    ganchos = ele.registrar_dizedor_do_no_ar(
        sub_mic.no_ar, sub_mic.esquecer_a_palavra, sub_mic.palavra_no_ar
    )
    ouvinte = bt.registrar_ouvinte_do_microfone(sub_mic.microfone_no_ar)
    try:
        for uniq, _ in mesa:
            assert _apertar(m, uniq, ligado=True).feito, uniq
        sub_mic._gerenciador.reconciliar(_controles(mesa))
        sub_mic._aplicar_a_palavra_dela()

        sub = alto_falante.AltoFalanteSubsystem()
        sub._casar_as_pontes(_controles(mesa))

        assert _o_microfone_no_report(fiacao) == {u: True for u, _ in mesa}, (
            "com os quatro microfones no ar, algum report de som saiu com o "
            "microfone desligado"
        )
        assert m.daemon._eleitor_de_microfone.eleito == P4
    finally:
        ele.registrar_dizedor_do_no_ar(*ganchos)
        bt.registrar_ouvinte_do_microfone(ouvinte)
