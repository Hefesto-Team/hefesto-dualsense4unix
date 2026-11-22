"""A-VIBRACAO-FINA-NAO-SE-CORTA-NO-TETO-01: a soma do bloco passa por um limitador.

O tocador é o real, sem processo (``argv_de`` vazio) e sem placa de som: a cada tique de 10 ms
o corpo leva 480 amostras e sai um bloco do rumble com o toque, o corpo e os lados somados. O
ganho da háptica de cada controle (o do laço do cabo e o da ponte do rádio) entra por
``ganho_da_via``, que no produto é o do perfil.

D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: a soma que passa do teto de 0,9 entra num limitador
com ataque, soltura e joelho, e nenhum canal fica no teto por mais de um quadro.
D-2211-O-TETO-DA-MISTURA-DESCONTA-O-GANHO-DA-VIA: o teto dos dois motores é o teto sobre o ganho
da via, porque o ganho multiplica o bloco depois da soma.

AS MORDIDAS (executadas, uma a uma, com o md5 conferido na volta):

* o corte em ±1 de volta no ``misturar_o_toque`` e no ``somar_os_corpos`` (e o limitador fora do
  ``proximo_bloco``) → ``test_a_soma_acima_do_teto_nao_fica_no_teto_nem_da_degrau``;
* o ``tetos_da_mistura`` sem o ganho → ``test_o_pico_depois_do_ganho_da_via_fica_no_teto``;
* o ganho único de todos os tocadores (o limitador compartilhado) →
  ``test_um_controle_alto_nao_abaixa_o_do_lado``.
"""
from __future__ import annotations

import math
from array import array

import numpy as np
import pytest

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.alto_falante_bt import CANAIS_DA_HAPTICA

Q = eh.QUADROS_POR_BLOCO
TETO = eh.TETO_DA_MISTURA
QUATRO = (
    ("APARELHOAAAAAA", "aa:bb:cc:00:00:11", 1.0),
    ("APARELHOBBBBBB", "aa:bb:cc:00:00:12", 1.5),
    ("APARELHOCCCCCC", "aa:bb:cc:00:00:13", 2.0),
    ("APARELHODDDDDD", "aa:bb:cc:00:00:14", 0.3),
)


def _tocador(marca: str = "APARELHOTESTEX", ganho: float = 1.0) -> eh.TocadorDoRumble:
    return eh.TocadorDoRumble(
        marca, argv_de=lambda *_a: [], ganho_da_via=lambda _dono: ganho
    )


def _corpo(i: int, amplitude: float) -> array[float]:
    return array(
        "f",
        [amplitude * math.sin(2 * math.pi * 60 * (i * Q + k) / 48000) for k in range(Q)],
    )


def _tocar_a_soma(
    tocador: eh.TocadorDoRumble,
    dono: str,
    *,
    blocos: int = 100,
    rumble: tuple[int, int] = (255, 255),
    corpo: float = 0.7,
    toque: float = 1.0,
    lados: tuple[int, int] = (200, 200),
) -> np.ndarray:
    saida, antes, fase = [], (0, 0), 0
    try:
        for i in range(blocos):
            if corpo:
                tocador.levar_o_corpo(_corpo(i, corpo), "centro", sink="", dono=dono, fonte="som")
            if toque and i % 20 == 0:
                tocador.tocar_o_toque(toque, "centro", 40, sink="", dono=dono)
            if any(lados):
                tocador.levar_os_lados(*lados, sink="", dono=dono)
            saida.append(tocador.proximo_bloco(rumble, antes, fase))
            antes, fase = rumble, (fase + Q) % eh.QUADROS_DO_CICLO
    finally:
        tocador.parar()
    return np.frombuffer(b"".join(saida), "<f4").reshape(-1, CANAIS_DA_HAPTICA).astype(np.float64)


def _mais_longa_no_teto(x: np.ndarray, teto: float) -> int:
    maior = atual = 0
    for no_teto in np.abs(x) >= teto - 1e-3:
        atual = atual + 1 if no_teto else 0
        maior = max(maior, atual)
    return maior


def test_a_soma_acima_do_teto_nao_fica_no_teto_nem_da_degrau() -> None:
    """D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: a soma passa de 1 e sai sem platô."""
    y = _tocar_a_soma(_tocador(), "d")
    for canal in (2, 3):
        x = y[:, canal]
        assert np.abs(x).max() > 0.5, "o canal ficou mudo: o limitador matou o sinal"
        assert np.abs(x).max() <= TETO + 1e-6, f"canal {canal}: passou do teto"
        assert _mais_longa_no_teto(x, TETO) <= 1, f"canal {canal}: o teto virou platô"
        assert np.abs(np.diff(x)).max() <= 0.5, f"canal {canal}: salto entre quadros"
    assert np.abs(y[:, :2]).max() == 0.0


@pytest.mark.parametrize(("marca", "dono", "ganho"), QUATRO)
def test_o_pico_depois_do_ganho_da_via_fica_no_teto(marca: str, dono: str, ganho: float) -> None:
    """D-2211-O-TETO-DA-MISTURA-DESCONTA-O-GANHO-DA-VIA: o bloco vezes o ganho fica no teto."""
    y = _tocar_a_soma(_tocador(marca, ganho), dono)
    for canal in (2, 3):
        depois = y[:, canal] * ganho
        assert np.abs(depois).max() <= TETO + 1e-6, f"{dono} canal {canal}: o ganho passou o teto"
        assert _mais_longa_no_teto(depois, TETO) <= 1, f"{dono} canal {canal}: platô depois"
        assert np.abs(np.diff(depois)).max() <= 0.5


def test_os_tetos_dos_motores_descontam_o_ganho_e_o_ganho_abaixo_de_um_nao_sobe_o_teto() -> None:
    """D-2211-O-TETO-DA-MISTURA-DESCONTA-O-GANHO-DA-VIA: 2,0 divide o teto, menos de 1 não."""
    assert _tocador(ganho=2.0).tetos_da_mistura().tolist() == pytest.approx(
        [TETO, TETO, TETO / 2, TETO / 2]
    )
    assert _tocador(ganho=0.3).tetos_da_mistura().tolist() == pytest.approx([TETO] * 4)

    def quebra(_dono: str) -> float:
        raise RuntimeError("perfil ilegível")

    sem_perfil = eh.TocadorDoRumble("APARELHOTESTEX", argv_de=lambda *_a: [], ganho_da_via=quebra)
    assert sem_perfil.tetos_da_mistura().tolist() == pytest.approx([TETO] * 4)
    nao_finito = eh.TocadorDoRumble(
        "APARELHOTESTEX", argv_de=lambda *_a: [], ganho_da_via=lambda _d: float("nan")
    )
    assert nao_finito.tetos_da_mistura().tolist() == pytest.approx([TETO] * 4)


def test_o_ganho_vem_do_perfil_do_dono_do_nivel(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2211-O-TETO-DA-MISTURA-DESCONTA-O-GANHO-DA-VIA: sem ``ganho_da_via``, lê o do perfil."""
    from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO

    lidos: list[str | None] = []

    def fator(uniq: str | None) -> float:
        lidos.append(uniq)
        return 2.0 if uniq == "aa:bb:cc:00:00:13" else 1.0

    monkeypatch.setattr(GANHO, "fator", fator)
    tocador = eh.TocadorDoRumble("APARELHOTESTEX", argv_de=lambda *_a: [])
    try:
        tocador.levar(10, 10, sink="", dono="aa:bb:cc:00:00:13")
        assert tocador.tetos_da_mistura()[2] == pytest.approx(TETO / 2)
        tocador.levar(10, 10, sink="", dono="aa:bb:cc:00:00:11")
        assert tocador.tetos_da_mistura()[2] == pytest.approx(TETO)
    finally:
        tocador.parar()
    assert lidos == ["aa:bb:cc:00:00:13", "aa:bb:cc:00:00:11"]


def test_o_que_cabe_sob_o_joelho_sai_byte_a_byte() -> None:
    """D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: sob o joelho o limitador não toca no bloco."""
    tocador = _tocador()
    try:
        bloco = tocador.proximo_bloco((60, 60), (60, 60), 0)
    finally:
        tocador.parar()
    assert bloco == eh.bloco_da_haptica(60, 60, fase=0, antes=(60, 60))
    limitador = eh.LimitadorSuave()
    quadros = np.full((Q, CANAIS_DA_HAPTICA), 0.5)
    assert limitador.passar(quadros, np.full(CANAIS_DA_HAPTICA, TETO)) is quadros
    assert limitador.ganho.tolist() == [1.0] * CANAIS_DA_HAPTICA


def test_a_soltura_devolve_o_ganho_sem_degrau_e_o_baixo_volta_intacto() -> None:
    """D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: passado o pico, o ganho sobe liso a 1."""
    limitador = eh.LimitadorSuave()
    tetos = np.full(CANAIS_DA_HAPTICA, TETO)
    fase = np.arange(Q * 400, dtype=np.float64)
    onda = np.sin(2 * math.pi * 70 * fase / 48000)
    entrada = np.zeros((Q * 400, CANAIS_DA_HAPTICA))
    entrada[: Q * 20, 2] = 1.8 * onda[: Q * 20]
    entrada[Q * 20:, 2] = 0.3 * onda[Q * 20:]
    saida = np.concatenate(
        [limitador.passar(entrada[i * Q:(i + 1) * Q], tetos) for i in range(400)]
    )
    assert np.abs(saida[: Q * 20, 2]).max() <= TETO + 1e-9
    cauda_in, cauda_out = entrada[Q * 20:, 2], saida[Q * 20:, 2]
    razao = cauda_out[np.abs(cauda_in) > 0.05] / cauda_in[np.abs(cauda_in) > 0.05]
    assert razao[0] < 0.75, "o ganho não estava reduzido quando o pico acabou"
    assert razao[-1] == pytest.approx(1.0, abs=1e-3), "o ganho não voltou a 1"
    assert np.abs(np.diff(saida[:, 2])).max() <= 0.5
    assert limitador.ganho[2] == 1.0
    assert np.array_equal(saida[-Q:, 2], entrada[-Q:, 2]), "o baixo não voltou intacto"


def test_um_controle_alto_nao_abaixa_o_do_lado() -> None:
    """D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: cada tocador tem o limitador dele."""
    tocadores = [_tocador(marca, ganho) for marca, _dono, ganho in QUATRO]
    quietos = [eh.bloco_da_haptica(60, 60, fase=0, antes=(60, 60)) for _ in QUATRO]
    try:
        for i in range(30):
            tocadores[0].levar_o_corpo(
                _corpo(i, 1.5), "centro", sink="", dono=QUATRO[0][1], fonte="som"
            )
            alto = tocadores[0].proximo_bloco((255, 255), (255, 255), 0)
            assert np.abs(np.frombuffer(alto, "<f4")).max() <= TETO + 1e-6
            for t, esperado in zip(tocadores[1:], quietos[1:], strict=True):
                assert t.proximo_bloco((60, 60), (60, 60), 0) == esperado
        assert tocadores[0]._limitador.ganho[2] < 1.0
        assert all(t._limitador.ganho.tolist() == [1.0] * 4 for t in tocadores[1:])
    finally:
        for t in tocadores:
            t.parar()


def test_sem_nada_tocando_o_bloco_e_mudo_e_o_limitador_nao_levanta() -> None:
    """D-2211-A-MISTURA-DA-HAPTICA-LIMITA-SEM-DEGRAU: o mudo e o vazio atravessam o limitador."""
    tocador = _tocador()
    try:
        assert tocador.proximo_bloco((0, 0), (0, 0), 0) == bytes(Q * 16)
    finally:
        tocador.parar()
    limitador = eh.LimitadorSuave()
    vazio = np.zeros((0, CANAIS_DA_HAPTICA))
    assert limitador.passar(vazio, np.full(CANAIS_DA_HAPTICA, TETO)) is vazio

