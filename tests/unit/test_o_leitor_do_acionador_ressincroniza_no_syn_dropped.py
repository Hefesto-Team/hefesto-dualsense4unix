"""O-LEITOR-DO-ACIONADOR-RESSINCRONIZA-NO-SYN-DROPPED-01: a tecla perdida no buraco não fica presa.

O leitor do acionador (teclado, pedal, acionador adaptado) ignorava o ``SYN_DROPPED``: o
soltar que o kernel jogou fora deixava a tecla em ``apertadas`` para sempre, e o botão do
jogador ficava preso. Agora o buraco se descarta até o ``SYN_REPORT`` seguinte, e o estado
das teclas se relê pelo ``active_keys`` do aparelho.

A régua nunca abre o ``/dev/input`` nem o ``/sys`` da máquina: o ``/sys/class/input`` é uma
pasta de mentira e o aparelho é um dublê com a fila e o ``active_keys`` do evdev.

MORDIDA: tirar o ramo do ``SYN_DROPPED`` do ``_ler`` reprova os quatro jogadores com a Cruz
presa; aplicar a tecla que chega no buraco (sem o ``or aberto.no_buraco``) reprova o pedal
apertado antes do fim do quadro.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core.remapeamento_de_botao import chave
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.utils.maquina import chave_do_acionador

UNIQS = tuple(f"aabbcc00000{n}" for n in range(1, 5))
NOME, FISICO, VENDOR, PRODUCT = "Pedal de mentira", "usb-0000:00:14.0-9/input0", "1234", "abcd"
CHAVE = chave_do_acionador(VENDOR, PRODUCT, NOME, FISICO)
TECLA, PEDAL = ecodes.KEY_ENTER, ecodes.KEY_SPACE


def _ev(tipo: int, codigo: int, valor: int = 0) -> Any:
    return SimpleNamespace(type=tipo, code=codigo, value=valor)


def _tecla(codigo: int, valor: int) -> list[Any]:
    return [_ev(ecodes.EV_KEY, codigo, valor), _ev(ecodes.EV_SYN, ecodes.SYN_REPORT)]


BURACO = _ev(ecodes.EV_SYN, ecodes.SYN_DROPPED)
FIM_DO_QUADRO = _ev(ecodes.EV_SYN, ecodes.SYN_REPORT)


class _Acionador:
    def __init__(self) -> None:
        self.fila: list[Any] = []
        self.ativas: list[int] = []

    def read_one(self) -> Any:
        return self.fila.pop(0) if self.fila else None

    def active_keys(self) -> list[int]:
        return list(self.ativas)

    def grab(self) -> None:
        pass

    def ungrab(self) -> None:
        pass

    def close(self) -> None:
        pass


def _ponte(tmp_path: Path, uniq: str) -> tuple[gp.PonteDosAcionadores, _Acionador, Any]:
    dentro = tmp_path / "event7" / "device"
    (dentro / "id").mkdir(parents=True)
    (dentro / "name").write_text(NOME + "\n")
    (dentro / "phys").write_text(FISICO + "\n")
    (dentro / "id" / "vendor").write_text(VENDOR + "\n")
    (dentro / "id" / "product").write_text(PRODUCT + "\n")
    aparelho = _Acionador()
    ponte = gp.PonteDosAcionadores(raiz=tmp_path, abrir=lambda _e: aparelho, relogio=lambda: 0.0)
    declarados = {CHAVE: SimpleNamespace(
        controle=chave(uniq), teclas={str(TECLA): "cross", str(PEDAL): "l2"})}
    return ponte, aparelho, declarados


@pytest.mark.parametrize("uniq", UNIQS)
def test_o_soltar_perdido_no_buraco_nao_prende_o_botao(tmp_path: Path, uniq: str) -> None:
    """D-1911-O-ACIONADOR-RELE-O-KERNEL-NO-BURACO: o soltar perdido não prende a Cruz."""
    ponte, aparelho, declarados = _ponte(tmp_path, uniq)
    aparelho.fila = _tecla(TECLA, 1)
    ponte.andar(declarados, lambda: False)
    assert ponte.apertados(uniq) == frozenset({"cross"})

    aparelho.fila = [BURACO, _ev(ecodes.EV_KEY, PEDAL, 1), FIM_DO_QUADRO]
    aparelho.ativas = []
    ponte.andar(declarados, lambda: False)

    assert ponte.apertados(uniq) == frozenset()


def test_o_que_o_kernel_diz_apertado_depois_do_buraco_vale(tmp_path: Path) -> None:
    """D-1911-O-ACIONADOR-RELE-O-KERNEL-NO-BURACO: a releitura traz o pedal apertado no buraco."""
    ponte, aparelho, declarados = _ponte(tmp_path, UNIQS[0])
    aparelho.fila = [*_tecla(TECLA, 1), BURACO, _ev(ecodes.EV_KEY, TECLA, 1), FIM_DO_QUADRO,
                     *_tecla(TECLA, 0)]
    aparelho.ativas = [TECLA, PEDAL]
    ponte.andar(declarados, lambda: False)

    assert ponte.apertados(UNIQS[0]) == frozenset({"l2_btn"})


def test_o_evento_do_buraco_nao_aperta_antes_do_fim_do_quadro(tmp_path: Path) -> None:
    """D-1911-O-ACIONADOR-RELE-O-KERNEL-NO-BURACO: o que chega no buraco não vale até o kernel."""
    ponte, aparelho, declarados = _ponte(tmp_path, UNIQS[0])
    aparelho.fila = [BURACO, _ev(ecodes.EV_KEY, PEDAL, 1)]
    ponte.andar(declarados, lambda: False)
    assert ponte.apertados(UNIQS[0]) == frozenset()

    aparelho.fila = [FIM_DO_QUADRO]
    aparelho.ativas = [TECLA]
    ponte.andar(declarados, lambda: False)
    assert ponte.apertados(UNIQS[0]) == frozenset({"cross"})
