"""O fio de nascimento fechado não abre fio novo, e o doctor lê a média do nascimento.

O `Daemon.run()` fecha o `FioDeNascimento` depois do `shutdown`. Um `parar_o_pad` que chega
tarde (o `descartar` de um pedido que o laço largou) criava uma thread nova, que nenhum
«fim» fecharia: agora o pad tardio para na hora, e o pedido tardio sai sem pad. O que já
estava na fila antes do `parar()` segue a vez dele.

O `vpad.nascimento_ms_total` SOMA os nascimentos; o doctor mostra a contagem e a média.

A MORDIDA, rodada na entrega:

- volte o `_por` a pôr na fila sem olhar o `_fechado` e
  :func:`test_o_pad_tardio_para_na_hora_sem_fio_novo` e
  :func:`test_o_pedido_tardio_sai_sem_pad_e_sem_fio_novo` reprovam;
- troque a média pela soma no `_linha_do_nascimento` e
  :func:`test_o_doctor_mostra_a_media_do_nascimento` reprova.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.integrations import virtual_pad as vp


class _Pad:
    def __init__(self) -> None:
        self.parado = threading.Event()

    def stop(self) -> None:
        self.parado.set()


def test_o_pad_tardio_para_na_hora_sem_fio_novo() -> None:
    fio = vp.FioDeNascimento()
    fio.parar()
    pad = _Pad()

    fio.parar_o_pad(pad)

    assert pad.parado.is_set(), "o pad tardio para na chamada, sem esperar fio"
    assert fio._thread is None, "o fio fechado não reabre"


def test_o_pedido_tardio_sai_sem_pad_e_sem_fio_novo(monkeypatch: pytest.MonkeyPatch) -> None:
    nasceu: list[Any] = []
    monkeypatch.setattr(vp, "make_virtual_pad", lambda *a, **k: nasceu.append(a) or _Pad())
    fio = vp.FioDeNascimento()
    fio.parar()

    pedido = fio.pedir("dualsense")

    assert pedido.pronto and pedido.pad is None
    assert nasceu == [] and fio._thread is None


def test_o_que_estava_na_fila_antes_de_fechar_segue_a_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solta = threading.Event()

    def _fabrica(*_a: Any, **_k: Any) -> _Pad:
        solta.wait(5.0)
        return _Pad()

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    fio = vp.FioDeNascimento()
    pedido = fio.pedir("dualsense")
    fio.parar()
    solta.set()

    assert pedido.esperar(5.0), "o pedido de antes do parar() é atendido"
    assert isinstance(pedido.pad, _Pad)


def test_o_doctor_mostra_a_media_do_nascimento() -> None:
    linha = cmd_doctor._linha_do_nascimento(
        {"vpad.nascimentos": 4, "vpad.nascimento_ms_total": 1240}
    )
    assert linha == ("[ OK ]", "nascimento do pad fora do tique: 4, média 310,0 ms")
    assert cmd_doctor._linha_do_nascimento({"vpad.nascimentos": 0}) is None
    assert cmd_doctor._linha_do_nascimento(None) is None
