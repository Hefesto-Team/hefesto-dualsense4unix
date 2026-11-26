"""A-ABA-LANCADORES-NAO-PINTA-NO-FIO-DO-GTK-01: o tique da 07 não espera o serviço nem o disco.

O arrastar do controle livre de uma extensão segura a chamada ao serviço; o tique que lê o que
espera, o modo e o que se arrastou (`_Viva.esperando`, `modo_de`, `ao_vivo`) volta na hora, e as
chamadas seguem na ordem em que foram aceitas. Com o registro das extensões lento, o tique da
janela não espera e o `[pacote lento]` diz a etapa que custou.

Mordida: devolver a chamada ao serviço para dentro da trava do estado em `_Viva.enviar`
(`with self._trava:` no lugar de `with self._envio:`) faz a primeira régua reprovar.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.interface.pacotes import fios
from tests.unit.test_o_pacote_de_toda_aba_se_monta_fora_do_fio_do_gtk import (
    _esperar_a_montagem,
    _piloto,
    _tique,
)

MOD = "toque"
TETO_S = 0.02
PRESO_S = 1.0


class _PontePresa:
    """O serviço que só responde quando a régua solta, e anota a ordem das chamadas."""

    def __init__(self) -> None:
        self.solta = threading.Event()
        self.chamadas: list[float] = []
        self.entrou = threading.Event()

    def chamar_com_o_corpo(self, metodo: str, **corpo: Any) -> tuple[bool, None, dict[str, Any]]:
        self.chamadas.append(float(corpo["valor"]))
        self.entrou.set()
        self.solta.wait(5)
        return True, None, {}


def _arrastar(viva: Any, ponte: _PontePresa, valor: float, carimbo: float) -> threading.Thread:
    fio = threading.Thread(target=viva.enviar, args=(MOD, "forca", valor),
                           kwargs={"vivo": int(carimbo), "carimbo": carimbo, "soltou": False,
                                   "ponte": ponte}, daemon=True)
    fio.start()
    return fio


def test_o_que_o_tique_le_da_extensao_nao_espera_o_servico() -> None:
    """Com o serviço preso no arrastar, `esperando`, `modo_de` e `ao_vivo` voltam na hora."""
    viva = a07._Viva()
    viva.marcar(MOD, "acender", "", 1)
    ponte = _PontePresa()
    fio = _arrastar(viva, ponte, 0.5, 1.0)
    try:
        assert ponte.entrou.wait(5), "o arrastar não chegou ao serviço"
        for nome, ler in (("esperando", lambda: viva.esperando(MOD, None)),
                          ("modo_de", lambda: viva.modo_de(MOD)),
                          ("ao_vivo", lambda: viva.ao_vivo(MOD))):
            t0 = time.perf_counter()
            ler()
            gasto = time.perf_counter() - t0
            assert gasto < TETO_S, f"`{nome}` esperou o serviço: {gasto * 1000:.0f} ms"
        assert viva.esperando(MOD, None) == frozenset({("acender", "")})
        assert viva.ao_vivo(MOD).valor == 0.5
    finally:
        ponte.solta.set()
        fio.join(5)


def test_as_chamadas_ao_servico_seguem_a_ordem_aceita() -> None:
    """O segundo arrastar espera o primeiro chegar ao serviço: a ordem não se inverte."""
    viva = a07._Viva()
    ponte = _PontePresa()
    primeiro = _arrastar(viva, ponte, 0.2, 1.0)
    assert ponte.entrou.wait(5)
    segundo = _arrastar(viva, ponte, 0.7, 2.0)
    time.sleep(0.1)
    assert ponte.chamadas == [0.2], "o segundo arrastar passou à frente do primeiro"
    ponte.solta.set()
    primeiro.join(5)
    segundo.join(5)
    assert ponte.chamadas == [0.2, 0.7]


def test_o_registro_lento_nao_prende_o_tique_e_o_diario_diz_a_etapa(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """O registro das extensões leva 1 s: o tique da 07 volta na hora e o diário diz a etapa."""
    def lento() -> tuple[Any, ...]:
        time.sleep(PRESO_S)
        return ()

    monkeypatch.setattr(a07, "_ler_as_instaladas", lento)
    monkeypatch.setattr(a07, "REGISTRO", a07._Registro())

    def da_07(pagina: str, ctx: Any) -> dict[str, Any]:
        return a07.pacote(ctx)

    fios.ligar_a_janela()
    try:
        piloto = _piloto(monkeypatch, da_07)  # type: ignore[arg-type]
        piloto.pagina = "07-lancadores.html"
        t0 = time.perf_counter()
        _tique(piloto)
        gasto = time.perf_counter() - t0
        assert gasto < 0.1, f"o tique da 07 esperou o registro: {gasto * 1000:.0f} ms"
        _esperar_a_montagem(piloto)
    finally:
        fios.ligar_a_janela(False)
    linhas = [ln for ln in capsys.readouterr().err.splitlines() if "[pacote lento]" in ln]
    assert linhas and "07-lancadores.html" in linhas[0] and "registro" in linhas[0], linhas
