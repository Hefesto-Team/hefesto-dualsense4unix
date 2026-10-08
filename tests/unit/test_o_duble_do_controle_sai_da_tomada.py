"""O `FakeController` tem tomada: desplugado, o `connect()` falha; plugado, liga como sempre.

O dublê religava sozinho (o `connect()` punha `_connected = True` sem aparelho), então todo
teste de queda via o controle de volta antes de o laço de poll a notar. A tomada mora no dublê,
para o teste de queda não reinventar a sua.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from hefesto_dualsense4unix.testing.fake_controller import FakeController


def test_plugado_o_connect_liga_como_sempre() -> None:
    fc = FakeController()
    assert fc.plugado is True
    fc.connect()
    assert fc.is_connected() is True
    assert fc.read_state().connected is True


def test_desplugado_o_connect_levanta_e_nao_liga() -> None:
    fc = FakeController()
    fc.connect()
    fc.desplugar()
    assert fc.is_connected() is False
    with pytest.raises(RuntimeError, match="desplugado"):
        fc.connect()
    assert fc.is_connected() is False
    assert fc.tentativas_de_conexao == 2


def test_nasce_desplugado_quando_o_teste_pede() -> None:
    fc = FakeController(plugado=False)
    with pytest.raises(RuntimeError):
        fc.connect()
    fc.plugar()
    assert fc.is_connected() is False, "plugar() não conecta: quem conecta é o connect() da sonda"
    fc.connect()
    assert fc.is_connected() is True


def test_a_sonda_ja_em_voo_nao_religa_depois_da_queda() -> None:
    """A sonda que já tinha pegado o `connect` (na fila do executor) roda DEPOIS do desplugar."""
    fc = FakeController()
    fc.connect()
    saiu_da_tomada = threading.Event()
    sonda_pronta = threading.Event()

    def _sonda() -> None:
        sonda_pronta.set()
        saiu_da_tomada.wait(timeout=5.0)
        fc.connect()

    with ThreadPoolExecutor(max_workers=1) as ex:
        futuro = ex.submit(_sonda)
        assert sonda_pronta.wait(timeout=5.0)
        fc.desplugar()
        saiu_da_tomada.set()
        with pytest.raises(RuntimeError, match="desplugado"):
            futuro.result(timeout=5.0)
    assert fc.is_connected() is False


def test_o_desplugar_e_o_connect_concorrentes_nunca_deixam_religado() -> None:
    """Dez rodadas de sondas disputando a trava com o desplugar: ninguém termina religado."""
    for _ in range(10):
        fc = FakeController()
        fc.connect()
        corrida = threading.Barrier(5)

        def _sonda(fc: FakeController = fc, corrida: threading.Barrier = corrida) -> None:
            corrida.wait(timeout=5.0)
            time.sleep(0.001)
            try:
                fc.connect()
            except RuntimeError:
                pass

        with ThreadPoolExecutor(max_workers=5) as ex:
            futuros = [ex.submit(_sonda) for _ in range(4)]
            corrida.wait(timeout=5.0)
            fc.desplugar()
            for f in futuros:
                f.result(timeout=5.0)
        # as sondas que rodaram ANTES do desplugar ligaram e o desplugar derrubou; as que
        # rodaram DEPOIS levantaram: o fim é sempre desligado
        assert fc.is_connected() is False
