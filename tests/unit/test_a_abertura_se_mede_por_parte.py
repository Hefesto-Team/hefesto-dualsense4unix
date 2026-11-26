"""A-PRIMEIRA-PINTURA-SE-MEDE-POR-PARTE-E-ENCURTA-01: a abertura se mede por marco.

A linha `[abertura]` traz os seis marcos (o `committed` da página, as abas importadas, a carga
terminada, o bootstrap instalado, o primeiro estado e a pintura), cada um em ms desde o piloto e
em ordem de chegada. O primeiro `state_full` é pedido quando a janela nasce, junto com a carga da
página, e não depois do bootstrap.

Mordida: tirar o `self._estado_vivo.comecar()` do fim de `Piloto.__init__` faz a segunda régua
reprovar (nenhuma leitura do serviço antes de a página carregar).
"""
from __future__ import annotations

import re
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("constrói o `Piloto` de verdade, com o WebKit")

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from tests.unit.janela_aberta_comum import _args

MARCOS = ("committed", "abas", "carga", "bootstrap", "estado", "pintura")


def test_a_linha_da_abertura_traz_os_seis_marcos_em_ordem(
        capsys: pytest.CaptureFixture[str]) -> None:
    """Os seis marcos saem na linha, na ordem em que chegaram, em ms desde o piloto."""
    relogio = [100.0]
    piloto: Any = SimpleNamespace(_relogio=lambda: relogio[0], _abertura={"piloto": 100.0})
    for passo, marco in zip((0.05, 0.2, 0.3, 3.4, 0.01, 0.02), (
            "janela", "committed", "abas", "estado", "carga", "bootstrap"), strict=True):
        relogio[0] += passo
        hv._marcar_a_abertura(piloto, marco)
    hv._marcar_a_abertura(piloto, "carga")
    relogio[0] += 0.15
    hv.Piloto._contar_a_abertura(piloto)
    linha = next(ln for ln in capsys.readouterr().err.splitlines() if "[abertura]" in ln)
    achados = re.findall(r"(\w+) (\d+)(?= ·|$)", linha.split("marcos:", 1)[1])
    nomes = [n for n, _ in achados]
    assert sorted(nomes) == sorted(MARCOS), linha
    tempos = [int(ms) for _, ms in achados]
    assert tempos == sorted(tempos), linha
    assert dict(achados)["committed"] == "250" and dict(achados)["pintura"] == "4130", linha


def test_o_primeiro_estado_e_pedido_quando_a_janela_nasce(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem rodar o laço do GTK (a página não carrega, o bootstrap não instala), o leitor já leu."""
    leu = threading.Event()

    def estado(*_a: Any, **_k: Any) -> dict[str, Any]:
        leu.set()
        return {"connected": True, "controllers": []}

    monkeypatch.setattr(hv.mesa_viva, "estado_do_daemon", estado)
    piloto = hv.Piloto(_args())
    try:
        assert not piloto.pronto, "o bootstrap instalou sem o laço do GTK"
        assert leu.wait(5), "o primeiro estado só é pedido depois do bootstrap"
        fim = time.monotonic() + 5
        while "estado" not in piloto._abertura and time.monotonic() < fim:
            time.sleep(0.01)
        assert "estado" in piloto._abertura, "o marco do primeiro estado não foi anotado"
    finally:
        piloto._estado_vivo.parar()
        piloto.tela.janela.destroy()
