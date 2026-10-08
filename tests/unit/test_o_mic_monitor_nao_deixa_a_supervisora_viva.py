"""A supervisora do `MicMonitor` não atravessa o caso que a ligou.

O construtor padrão (`auto_supervisao=True`) sobe a thread `hefesto-mic-monitor` no
primeiro `set_ativo`, e só o `stop()` a junta. Os dois casos abaixo rodam em ordem:
o primeiro a liga e não a para; o segundo confere que o `conftest.py` a derrubou
quando o primeiro acabou. Arrancar a fixture `_nenhuma_supervisora_do_mic_atravessa`
reprova o segundo.
"""

from __future__ import annotations

import threading

import pytest

from hefesto_dualsense4unix.app.mic_monitor import MicMonitor

_NOME_DA_THREAD = "hefesto-mic-monitor"

_ESTADO: dict[str, bool] = {"ligou": False}


def _supervisoras() -> list[threading.Thread]:
    return [fio for fio in threading.enumerate() if fio.name == _NOME_DA_THREAD]


def test_1_o_caso_liga_a_supervisora_e_nao_a_para() -> None:
    """O padrão do construtor liga a thread; este caso de propósito não chama `stop()`."""
    monitor = MicMonitor(runner=lambda _argv: "", capturador=lambda *_a, **_k: None)

    monitor.set_ativo(True)

    assert [fio.is_alive() for fio in _supervisoras()] == [True]
    _ESTADO["ligou"] = True


def test_2_o_caso_seguinte_nao_encontra_a_supervisora() -> None:
    """A thread do caso anterior morreu com ele, e não pede nada ao servidor deste."""
    if not _ESTADO["ligou"]:
        pytest.skip("o caso 1 não rodou antes: não há supervisora esquecida para conferir")

    assert _supervisoras() == []
