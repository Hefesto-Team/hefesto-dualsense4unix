"""O Mapear não congela a janela — O-MAPEAR-NAO-CONGELA-A-JANELA-01 (26/09/2026).

A queixa dela: *«o mapear entradas toda hora tá fechando o app. dá um crash
feio. acho que é se eu continuar nessa tela e trocar antes de fechar essa tela
de mapear.»* <!-- noqa-acento: citação literal dela -->

Medido: não era crash. O tique da aba 08 lia o ``/sys`` USB no fio da janela
(o censo lê ``product`` e ``bMaxPower``, que o kernel serve sob o lock do
aparelho), e com ela trocando o DualSense de entrada o kernel segurava o lock
enquanto enumerava: o tique custava 5, 10 e 15 s e o COSMIC derrubava a
janela.

O ``/sys`` DE MENTIRA DESTA RÉGUA É O GABINETE DA 02 (os leitores de verdade
sobre uma árvore no ``tmp_path``) atrás de um :class:`Portao`: a leitura dorme
até 6 s, como o lock do kernel, e a régua a solta quando termina de medir.

AS MORDIDAS, uma por teste:

* :func:`test_o_tique_do_mapear_volta_na_hora_com_o_sys_preso` — devolva a
  leitura ao tique (``campos_do_mapear`` chamando ``estado()``/``olhar()`` do
  dono) e o primeiro tique leva 12 s.
* :func:`test_terminar_nao_espera_o_sys` — ponha a leitura de ``olhar``,
  ``estado`` ou ``gravar`` de volta dentro do ``with self._trava:`` e o
  ``parar()`` espera o sono inteiro.
* :func:`test_o_tique_da_cerimonia_volta_na_hora_com_o_sys_preso` — devolva o
  ``laco.olhar()`` a ``_campos_da_cerimonia``.
* :func:`test_a_cerimonia_fecha_sem_esperar_o_sys` — leia o censo do laço
  dentro da trava.
* :func:`test_o_censo_da_aba_nao_e_lido_no_fio_da_janela` — devolva ao
  ``_censo`` a leitura na hora quando ``_CENSO`` é ``None``.
* :func:`test_a_leitura_que_passa_do_folego_esconde_a_porta_de_antes` — tire
  o ``demorando()`` de ``MapearAsPortas._foto_de_agora``.
* :func:`test_o_salvar_vai_para_onde_o_controle_esta` — tire o
  ``self._andar(censo, lidas)`` do ``gravar``: o nome da segunda porta vai
  para a primeira.

Faixa sintética da casa: controladores ``0000:0a:00.0`` e ``0000:0b:00.0``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina, carregar_maquina, lugar_de
from tests.unit.test_entrada_a_entrada_02_as_telas_aprovadas import (
    BOOT_1,
    DUALSENSE,
    PCI_A,
    TECLADO,
    Gabinete,
)

#: O teto do tique, o da sprint: a janela não pode esperar o ``/sys``.
TETO_S = 0.05
#: O sono do lock do kernel: o ``tique lento`` dela chegou a 15 s.
SONO_S = 6.0


class Portao:
    """O ``/sys`` que o kernel segura: a leitura dorme até :data:`SONO_S`.

    Aberto, lê na hora. ``segurar`` fecha: a próxima leitura entra (``entrou``)
    e dorme até ``soltar`` ou até o sono acabar — o mesmo que o
    ``usb_lock_device_interruptible`` faz com quem lê ``bMaxPower``.
    """

    def __init__(self, ler: Callable[[], Any]) -> None:
        self._ler = ler
        self._aberto = threading.Event()
        self._aberto.set()
        self.entrou = threading.Event()
        self._conta = threading.Lock()
        self.leituras = 0

    def segurar(self) -> None:
        self.entrou.clear()
        self._aberto.clear()

    def soltar(self) -> None:
        self._aberto.set()

    def __call__(self) -> Any:
        with self._conta:
            self.leituras += 1
        self.entrou.set()
        self._aberto.wait(SONO_S)
        return self._ler()


def _pac() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _esperar(pergunta: Callable[[], Any], prazo: float = 3.0) -> Any:
    """Pergunta até ter resposta verdadeira — a volta do fio, sem dormir a mais."""
    fim = time.monotonic() + prazo
    while True:
        resposta = pergunta()
        if resposta or time.monotonic() > fim:
            return resposta
        time.sleep(0.01)


def _medir(chamar: Callable[[], Any], vezes: int = 10) -> tuple[list[float], Any]:
    custos, ultimo = [], None
    for _ in range(vezes):
        t0 = time.perf_counter()
        ultimo = chamar()
        custos.append(time.perf_counter() - t0)
    return custos, ultimo


def _pousou(dono: Any) -> bool:
    """Nenhuma leitura do dono no ar — para a régua não deixar fio para a próxima."""
    return _esperar(lambda: not dono._voo.no_ar())


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    return alvo


@pytest.fixture()
def gabinete(tmp_path: Path) -> Gabinete:
    return Gabinete(tmp_path / "sys", BOOT_1)


def _fluxo(gabinete: Gabinete, portao: Portao) -> ee.MapearAsPortas:
    return ee.MapearAsPortas(
        ler=portao, entradas=gabinete.entradas, storm={}, adaptadores=lambda: ()
    )


# ---------------------------------------------------------------------------
# E1 — o tique do Mapear volta em milissegundos com o /sys preso
# ---------------------------------------------------------------------------


def test_o_tique_do_mapear_volta_na_hora_com_o_sys_preso(
    gabinete: Gabinete, disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pac = _pac()
    gabinete.plugar(1, "5", DUALSENSE)
    portao = Portao(gabinete.ler)
    fluxo = _fluxo(gabinete, portao)
    monkeypatch.setattr(pac, "_o_mapa", lambda: fluxo)
    monkeypatch.setattr(pac, "_LOGICA", None)
    pac.campos_do_mapear({"estado": "parado", "portas": []})  # os imports, fora da conta

    portao.segurar()
    try:
        pac.mapear_comecar(None, {}, None)
        assert portao.leituras == 0, "o gesto só abre: quem lê é o fio do dono"
        custos, campos = _medir(pac.campos_do_mapear)
        assert max(custos) < TETO_S, (
            f"o tique esperou o /sys: {[round(c * 1000) for c in custos]} ms")
        assert campos["mapear-diz"] == pac.MAPEAR_DIZ["procurando"]
        assert campos["mapear-estado"] == "esperando", "a luz pulsa enquanto procura"
        assert "Entrada" not in campos["mapear-porta"] + campos["mapear-lista"], (
            "sem leitura nenhuma, a tela não afirma porta nem lista")
        assert portao.entrou.wait(2), "o tique não pediu a leitura ao fio"
        assert portao.leituras == 1, "dez tiques, UMA leitura no ar"
    finally:
        portao.soltar()

    campos = _esperar(lambda: (c := pac.campos_do_mapear())["mapear-estado"] == "porta" and c)
    assert campos, "a foto nova não apareceu quando o sono acabou"
    assert "Entrada" in campos["mapear-porta"]
    assert campos["mapear-diz"] == pac.MAPEAR_DIZ["porta"]
    fluxo.parar()
    assert _pousou(fluxo)


# ---------------------------------------------------------------------------
# E2 — o «Terminar» nunca espera o /sys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gesto", ["olhar", "estado", "gravar"])
def test_terminar_nao_espera_o_sys(gabinete: Gabinete, disco: Path, gesto: str) -> None:
    gabinete.plugar(1, "5", DUALSENSE)
    portao = Portao(gabinete.ler)
    fluxo = _fluxo(gabinete, portao)
    assert fluxo.comecar()["estado"] == ee.NA_PORTA

    def ler_preso() -> None:
        if gesto == "gravar":
            fluxo.gravar(nome="Frente", lugar=ee.LUGAR_FRENTE)
        else:
            getattr(fluxo, gesto)()

    portao.segurar()
    fio = threading.Thread(target=ler_preso, daemon=True)
    fio.start()
    try:
        assert portao.entrou.wait(2)
        t0 = time.perf_counter()
        fluxo.parar()
        custo = time.perf_counter() - t0
        assert custo < TETO_S, f"o Terminar esperou o /sys de `{gesto}`: {custo * 1000:.0f} ms"
    finally:
        portao.soltar()
        fio.join(SONO_S)
    assert fluxo.foto_sem_esperar()["estado"] == ee.PARADO, (
        "a leitura de antes do Terminar reabriu o fluxo")
    dela = carregar_maquina().lugares.get(lugar_de(PCI_A, "5"))
    if gesto == "gravar":
        assert dela is not None and dela.nome == "Frente", (
            "o Salvar clicado antes do Terminar se perdeu — e nada se perde")
    else:
        assert dela is None, f"`{gesto}` gravou alguma coisa"


# ---------------------------------------------------------------------------
# A cerimônia («Mapear Entrada a Entrada») — o mesmo tique, a mesma cura
# ---------------------------------------------------------------------------


def test_o_tique_da_cerimonia_volta_na_hora_com_o_sys_preso(
    gabinete: Gabinete, disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pac = _pac()
    gabinete.plugar(1, "3", TECLADO)
    portao = Portao(gabinete.ler)
    laco = ee.LacoDaEntrada(ler=portao, entradas=gabinete.entradas)
    monkeypatch.setattr(pac, "_laco", lambda: laco)
    assert laco.comecar()["estado"] == ee.SENTADA
    pac._campos_da_cerimonia()  # os imports, fora da conta
    assert _pousou(laco)

    antes = portao.leituras
    portao.segurar()
    try:
        custos, campos = _medir(pac._campos_da_cerimonia)
        assert max(custos) < TETO_S, (
            f"o tique da cerimônia esperou o /sys: {[round(c * 1000) for c in custos]} ms")
        assert campos["entrada-tela"] == ee.TELAS[ee.SENTADA], "a tela aberta continua a dela"
        assert portao.entrou.wait(2), "o tique não pediu a leitura ao fio"
        assert portao.leituras == antes + 1, "dez tiques, UMA leitura no ar"
    finally:
        portao.soltar()
    laco.parar()
    assert _pousou(laco)


def test_a_cerimonia_fecha_sem_esperar_o_sys(gabinete: Gabinete, disco: Path) -> None:
    gabinete.plugar(1, "3", TECLADO)
    portao = Portao(gabinete.ler)
    laco = ee.LacoDaEntrada(ler=portao, entradas=gabinete.entradas)
    assert laco.comecar()["estado"] == ee.SENTADA

    portao.segurar()
    fio = threading.Thread(target=laco.olhar, daemon=True)
    fio.start()
    try:
        assert portao.entrou.wait(2)
        t0 = time.perf_counter()
        laco.parar()
        custo = time.perf_counter() - t0
        assert custo < TETO_S, f"o «Já chega por hoje» esperou o /sys: {custo * 1000:.0f} ms"
    finally:
        portao.soltar()
        fio.join(SONO_S)
    assert laco.foto_sem_esperar()["estado"] == ee.PARADO, (
        "a leitura de antes do fechar reabriu a cerimônia")


# ---------------------------------------------------------------------------
# O censo da aba — a primeira leitura também sai do fio da janela
# ---------------------------------------------------------------------------


def test_o_censo_da_aba_nao_e_lido_no_fio_da_janela(
    gabinete: Gabinete, monkeypatch: pytest.MonkeyPatch
) -> None:
    pac = _pac()
    from hefesto_dualsense4unix.integrations import censo_do_barramento

    lido = gabinete.ler()
    assert isinstance(lido, Censo) and lido.aparelhos, "o gabinete de mentira não leu nada"
    portao = Portao(lambda: lido)
    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", lambda *_a, **_k: portao())
    monkeypatch.setattr(pac, "_CENSO", None)
    monkeypatch.setattr(pac, "LER_NA_HORA", False)
    monkeypatch.setattr(pac, "_FUNDO", {})
    monkeypatch.setattr(pac, "_FUNDO_EM_VOO", set())
    monkeypatch.setattr(pac, "_GERACAO", {})

    portao.segurar()
    try:
        custos, visto = _medir(pac._censo)
        assert max(custos) < TETO_S, (
            f"o censo foi lido no fio da janela: {[round(c * 1000) for c in custos]} ms")
        assert visto is None, "antes de a leitura voltar, o censo é «não sei»"
        assert portao.entrou.wait(2) and portao.leituras == 1, "UMA leitura no ar"
    finally:
        portao.soltar()
    assert _esperar(lambda: pac._censo() is lido), "a leitura voltou e o censo não chegou"
    assert _esperar(lambda: "censo" not in pac._FUNDO_EM_VOO)


# ---------------------------------------------------------------------------
# O que a cura abriu, e fecha: a porta de antes na tela enquanto o kernel lê
# ---------------------------------------------------------------------------


def test_a_leitura_que_passa_do_folego_esconde_a_porta_de_antes(
    gabinete: Gabinete, disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ela tira o controle da porta e o encaixa noutra: o kernel segura o
    ``/sys`` por segundos. A tela não pode continuar dizendo «Entrada
    encontrada» sobre a porta de ANTES — ela diz «Procurando…», sem a porta,
    e a lista do que já foi salvo fica."""
    pac = _pac()
    monkeypatch.setattr(ee, "FOLEGO_DA_LEITURA_S", 0.05)
    gabinete.plugar(1, "5", DUALSENSE)
    portao = Portao(gabinete.ler)
    fluxo = _fluxo(gabinete, portao)
    monkeypatch.setattr(pac, "_o_mapa", lambda: fluxo)
    assert fluxo.comecar()["estado"] == ee.NA_PORTA
    assert fluxo.gravar(nome="Frente de baixo", lugar=ee.LUGAR_FRENTE).gravou
    antes = pac.campos_do_mapear()
    assert antes["mapear-estado"] == "porta" and "Frente de baixo" in antes["mapear-lista"]
    assert _pousou(fluxo)

    portao.segurar()
    try:
        pac.campos_do_mapear()
        assert portao.entrou.wait(2)
        assert _esperar(lambda: fluxo._voo.demorando())
        campos = pac.campos_do_mapear()
        assert campos["mapear-diz"] == pac.MAPEAR_DIZ["procurando"]
        assert campos["mapear-porta"] == pac.html_da_porta_medida(None), (
            "a leitura passou do fôlego e a tela ainda mostra a porta de antes")
        assert campos["mapear-lista"] == antes["mapear-lista"], "a lista do que já foi salvo fica"
    finally:
        portao.soltar()
    assert _esperar(lambda: pac.campos_do_mapear()["mapear-diz"] == pac.MAPEAR_DIZ["porta"])
    fluxo.parar()
    assert _pousou(fluxo)


def test_o_salvar_vai_para_onde_o_controle_esta(gabinete: Gabinete, disco: Path) -> None:
    """Ela levou o DualSense para a próxima porta e, antes de a foto voltar,
    deu o nome e salvou: o nome vai para onde o controle ESTÁ, e a primeira
    porta continua com o nome dela."""
    fluxo = ee.MapearAsPortas(
        ler=gabinete.ler, entradas=gabinete.entradas, storm={}, adaptadores=lambda: ()
    )
    fluxo.comecar()
    gabinete.plugar(1, "5", DUALSENSE)
    assert fluxo.olhar()["porta"]["aparelho"] == "1-5"
    assert fluxo.gravar(nome="Frente de baixo", lugar=ee.LUGAR_FRENTE).gravou

    gabinete.tirar("1-5")
    gabinete.plugar(1, "3", DUALSENSE)
    # nenhum `olhar`: o fio do tique ainda está preso no kernel
    assert fluxo.gravar(nome="Frente de cima", lugar=ee.LUGAR_FRENTE).gravou

    documento = carregar_maquina()
    assert documento.lugares[lugar_de(PCI_A, "5")].nome == "Frente de baixo", (
        "o Salvar da segunda porta renomeou a primeira")
    assert documento.lugares[lugar_de(PCI_A, "3")].nome == "Frente de cima"
    assert fluxo.foto_sem_esperar()["porta"]["aparelho"] == "1-3", (
        "a foto do tique seguinte não mostra o que ela acabou de salvar")
    fluxo.parar()
