"""O aviso do daemon ao systemd: «estou pronto» e «estou parando».

A unit é ``Type=notify`` com ``NotifyAccess=main``: o ``start`` só volta com ``READY=1`` (o IPC
escutando). Este módulo é o dono ÚNICO do aviso e do soquete: ``guardar_o_soquete``, na entrada
do daemon, tira o ``NOTIFY_SOCKET`` de ``os.environ`` e o guarda, e nenhum filho o herda (o
``systemctl`` e o ``udevadm`` mandam ``EXIT_STATUS=0`` ao sair). Sem soquete (o daemon avulso,
os testes) não faz nada e não levanta. O broker segue com o ``_sd_notify`` dele: roda como root
e não importa módulo do produto.
"""
from __future__ import annotations

import os
import socket

PRAZO_DA_PARTIDA_S = 30.0

VARIAVEIS_DO_PRINCIPAL: tuple[str, ...] = ("NOTIFY_SOCKET", "WATCHDOG_PID", "WATCHDOG_USEC")

_guardadas: dict[str, str] = {}


def guardar_o_soquete() -> None:
    """Tira de ``os.environ`` as variáveis do principal e as guarda para o aviso.

    Idempotente: a segunda chamada, com o ambiente já limpo, não perde o que guardou. Sem
    ``NOTIFY_SOCKET`` (o daemon avulso, os testes) não faz nada.
    """
    for nome in VARIAVEIS_DO_PRINCIPAL:
        valor = os.environ.pop(nome, None)
        if valor:
            _guardadas[nome] = valor


def _soquete() -> str | None:
    return os.environ.get("NOTIFY_SOCKET") or _guardadas.get("NOTIFY_SOCKET")


def notificar(mensagem: str) -> bool:
    """Manda ``mensagem`` ao ``NOTIFY_SOCKET``. ``True`` só se o datagrama saiu.

    Melhor esforço: o aviso perdido não derruba o daemon (o systemd, sem o pronto, estoura o
    ``TimeoutStartSec`` e o diário diz isso).
    """
    alvo = _soquete()
    if not alvo:
        return False
    if alvo.startswith("@"):
        alvo = "\0" + alvo[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as soquete:
            soquete.sendto(mensagem.encode("utf-8"), alvo)
    except OSError:
        return False
    return True


def pronto() -> bool:
    """``READY=1``: o IPC escuta e o serviço atende."""
    return notificar("READY=1")


def parando() -> bool:
    """``STOPPING=1``: o desligamento começou."""
    return notificar("STOPPING=1")


__all__ = [
    "PRAZO_DA_PARTIDA_S",
    "VARIAVEIS_DO_PRINCIPAL",
    "guardar_o_soquete",
    "notificar",
    "parando",
    "pronto",
]
