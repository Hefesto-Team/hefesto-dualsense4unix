"""QUEDA-QUE-PENDURA-01: controle que some do rádio não pode pendurar o daemon.

MEDIDO no journal dela em 04/08/2026. O 8BitDo se desligou sozinho; segundos
depois ela pediu um reinício do daemon, e o systemd registrou:

    00:20:19.601  gamepad_emulation_stopped     <- último suspiro
    (silêncio de 90 s)
    00:21:49      State 'stop-sigterm' timed out. Killing.

O `daemon_stopped` — a última linha do `shutdown()` — nunca saiu.

A cadeia, conferida no código do upstream e no nosso:

    device.read(...)              BLOQUEIA num fd que não entrega mais nada
      -> report_thread.join()     upstream, SEM TETO
        -> handle.close()
          -> disconnect()         segurando o `_io_lock`
            -> shutdown()
              -> systemd: 90 s e SIGKILL

Estes testes travam as três coisas que a cura precisa fazer, e nenhuma a mais:
o join tem teto, o fd fecha **de todo jeito**, e uma thread que não morre não
impede o processo de morrer — que é a mesma doutrina que o `HANG-01` já
aplicava aos dois executores do `shutdown` (`wait=False`).
"""
from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    CLOSE_JOIN_TIMEOUT_SEC,
    _PinnedPyDualSense,
)


class _DeviceMorto:
    """Um `hidapi.Device` cujo `read` nunca volta — o controle que sumiu."""

    def __init__(self, solto: threading.Event) -> None:
        self._solto = solto
        self.fechado = False

    def read(self, _n: int) -> bytes:
        # Espera o `close()` de verdade, sem prazo — é o `read` pendurado.
        self._solto.wait()
        raise OSError("fd fechado")

    def close(self) -> None:
        self.fechado = True
        self._solto.set()  # é FECHAR o fd que desbloqueia o read


def _handle_com_thread_pendurada() -> tuple[Any, _DeviceMorto, threading.Thread]:
    """Monta o mínimo de `_PinnedPyDualSense` para exercitar só o `close()`."""
    ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    solto = threading.Event()
    device = _DeviceMorto(solto)
    ds.device = device
    ds.ds_thread = True

    def _laco() -> None:
        while ds.ds_thread:
            try:
                device.read(64)
            except OSError:
                break

    thread = threading.Thread(target=_laco, daemon=True)
    thread.start()
    ds.report_thread = thread
    # Garante que a thread JÁ está dentro do read antes de fechar.
    for _ in range(200):
        if solto.is_set() or thread.is_alive():
            break
        time.sleep(0.005)
    return ds, device, thread


class TestOCloseNaoPendura:
    def test_o_close_volta_mesmo_com_a_thread_travada_no_read(self) -> None:
        """Mordida: devolver o `join()` sem teto do upstream trava aqui.

        Sem a cura este teste não falha — ele **não termina**, que é
        exatamente o que aconteceu com o daemon dela. O teto abaixo é
        generoso (4x o teto da cura) para não ser flaky em máquina carregada,
        e ainda assim é 20x menor que os 90 s do systemd.
        """
        ds, _device, _thread = _handle_com_thread_pendurada()
        inicio = time.monotonic()
        ds.close()
        gasto = time.monotonic() - inicio
        assert gasto < CLOSE_JOIN_TIMEOUT_SEC * 4, (
            f"o close levou {gasto:.2f}s — o join voltou a ser sem teto"
        )

    def test_o_fd_fecha_mesmo_que_a_thread_nao_saia(self) -> None:
        """Fechar o fd é o que desbloqueia o `read` — não é opcional.

        O upstream fecha DEPOIS do join, então com o join travado o fd nunca
        fechava. Invertida a ordem, o fd fecha e a thread sai sozinha pelo
        `except OSError` que o laço já tinha.
        """
        ds, device, thread = _handle_com_thread_pendurada()
        ds.close()
        assert device.fechado, "o fd ficou aberto — a thread nunca se solta"
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "o OSError não encerrou o laço"

    def test_o_ds_thread_e_baixado_antes_de_tudo(self) -> None:
        """O sinal cooperativo continua sendo a via NORMAL de encerrar.

        Com o controle vivo, o laço vê `ds_thread = False` no ciclo seguinte e
        sai sem que teto nenhum precise disparar. A cura não pode trocar o
        caminho barato pelo caro.
        """
        ds, _device, _thread = _handle_com_thread_pendurada()
        ds.close()
        assert ds.ds_thread is False


class TestOTetoEHonesto:
    def test_o_teto_e_curto_o_bastante_para_nao_ser_notado(self) -> None:
        """Um teto de vários segundos seria trocar 90 s por 10 s — não é cura.

        O laço gira a ~100 Hz: meio segundo é 50 ciclos, folga de sobra para
        um controle que ainda responde, e imperceptível para ela.
        """
        assert 0 < CLOSE_JOIN_TIMEOUT_SEC <= 1.0

    def test_close_sem_thread_nao_explode(self) -> None:
        """Handle que nunca chegou a subir a thread (falha no init) fecha igual."""
        ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
        device = _DeviceMorto(threading.Event())
        ds.device = device
        ds.ds_thread = True
        ds.report_thread = None
        ds.close()
        assert device.fechado

    def test_close_com_device_que_recusa_fechar_nao_propaga(self) -> None:
        """`close()` roda no caminho de desligamento — não pode levantar.

        Todo chamador já o envolve em `suppress(Exception)`; depender disso
        seria deixar a corretude do desligamento na mão de quem chama.
        """

        class _Teimoso:
            def close(self) -> None:
                raise OSError("dispositivo já sumiu")

        ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
        ds.device = _Teimoso()
        ds.ds_thread = True
        ds.report_thread = None
        ds.close()  # não levanta


@pytest.mark.parametrize("vivos", [1, 2, 4])
def test_varios_handles_mortos_somam_um_teto_cada_e_nao_noventa(vivos: int) -> None:
    """Quatro controles na mesa que caem juntos ainda cabem no desligamento.

    É o caso dela: os quatro no rádio, o cabo sai, os outros três caem na
    sequência. Quatro `close()` pendurados eram 4 x infinito; agora são
    4 x meio segundo, e o `TimeoutStopSec` do systemd nem chega perto.
    """
    handles = [_handle_com_thread_pendurada() for _ in range(vivos)]
    inicio = time.monotonic()
    for ds, _device, _thread in handles:
        ds.close()
    gasto = time.monotonic() - inicio
    assert gasto < CLOSE_JOIN_TIMEOUT_SEC * 4 * vivos
    for _ds, device, _thread in handles:
        assert device.fechado
