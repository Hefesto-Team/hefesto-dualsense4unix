"""A leitura em fundo da Conexões e o leitor do BlueZ, com UM dono.

O que o ``state_full`` (o BlueZ, o diário, o ``kernel.log``, o ``maquina.json``) lê é caro e
lento; a tela não espera por ele. Cada leitura roda num fio, a volta da tela devolve a última
que chegou, e um gesto que grava manda ``esquecer`` a chave para a próxima volta ler de novo.

O cache é genérico e serve a seis leitores da 08 (o censo, a máquina, o wifi, o sino, os zumbis
e o BlueZ) e ao nome do jogador, que lê o ``Alias`` do BlueZ por aqui. Este módulo não importa
a 08 nem o ``nome_do_jogador``: os dois o importam, e o ciclo (o import tardio) não existe.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from . import fios, perfil

_FUNDO: dict[str, tuple[float, Any]] = {}
_FUNDO_EM_VOO: set[str] = set()
_TRAVA_DO_FUNDO = threading.Lock()
_GERACAO: dict[str, int] = {}
LER_NA_HORA = False
VENCIDA = float("-inf")


def em_fundo(chave: str, ler: Callable[[], Any], validade_s: float) -> Any:
    """A última leitura de `chave`; pede outra num fio quando ela venceu."""
    agora = time.monotonic()
    with _TRAVA_DO_FUNDO:
        visto = _FUNDO.get(chave)
        if (visto is not None and agora - visto[0] < validade_s) or chave in _FUNDO_EM_VOO:
            return None if visto is None else visto[1]
        _FUNDO_EM_VOO.add(chave)
        geracao = _GERACAO.get(chave, 0)

    def trabalhar() -> None:
        try:
            valor = ler()
        except Exception:
            valor = None
        with _TRAVA_DO_FUNDO:
            fresca = _GERACAO.get(chave, 0) == geracao
            _FUNDO[chave] = (time.monotonic() if fresca else VENCIDA, valor)
            _FUNDO_EM_VOO.discard(chave)

    if LER_NA_HORA:
        trabalhar()
        return _FUNDO[chave][1]
    fios.soltar(f"radio-{chave}", trabalhar)
    return None if visto is None else visto[1]


def esquecer(*chaves: str) -> None:
    """Depois de um gesto que grava, a próxima volta lê de novo."""
    with _TRAVA_DO_FUNDO:
        for chave in chaves:
            _GERACAO[chave] = _GERACAO.get(chave, 0) + 1
            visto = _FUNDO.get(chave)
            if visto is not None:
                _FUNDO[chave] = (VENCIDA, visto[1])


def lido(chave: str) -> Any:
    """O que a última leitura de `chave` trouxe, sem pedir outra; `None` se nunca chegou."""
    with _TRAVA_DO_FUNDO:
        visto = _FUNDO.get(chave)
    return None if visto is None else visto[1]


def ler_o_bluez() -> tuple[tuple[Any, ...], tuple[Any, ...]] | None:
    """`(adaptadores, aparelhos)` do dono do BlueZ. Sob a suíte, nada: a régua injeta."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import bluez_dbus

    if bluez_dbus.a_suite_esta_rodando():
        return None
    dono = bluez_dbus.dono()
    adaptadores = dono.adaptadores()
    aparelhos = dono.aparelhos()
    if adaptadores is None:
        return None
    return tuple(adaptadores), tuple(aparelhos or ())


def e_controle_do_bluez(a: Any) -> bool:
    """Pergunta à CLASSE (o dono é `gesto_de_pareamento.e_controle`); sem ela, ao ícone."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.gesto_de_pareamento import e_controle

    classe = getattr(a, "classe", None)
    if classe is not None:
        return e_controle(classe)
    icone = str(getattr(a, "icone", "") or "")
    if icone:
        return icone == "input-gaming"
    return "V054C" in str(getattr(a, "modalias", "") or "").upper()
