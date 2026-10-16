"""O aviso do daemon ao systemd: «estou pronto» e «estou parando».

A unit do daemon é ``Type=notify`` (``assets/hefesto-dualsense4unix.service``): o
``systemctl start`` só volta quando o daemon manda ``READY=1``, e o pronto é o soquete do
IPC escutando. Sem isso o ``simple`` dizia «ligado» no ``fork``, ~0,5 s antes de o soquete
existir, e cada chamador do ``start`` tinha de esperar por conta própria.

Este módulo é o dono ÚNICO do aviso do daemon. Sem ``NOTIFY_SOCKET`` (o daemon avulso, o
``--foreground`` à mão, os testes) não faz nada e não levanta. O broker segue com o
``_sd_notify`` dele de propósito: roda como root e não importa módulo do produto.
"""
from __future__ import annotations

import os
import socket

#: O prazo que a unit dá à subida (``TimeoutStartSec``). Estourado, o systemd derruba o daemon
#: que travou antes do pronto; o ``start`` de quem chama tem de caber nele (um teste confere os
#: dois, como o ``PRAZO_DO_DESLIGAMENTO_S`` confere o ``TimeoutStopSec``).
PRAZO_DA_PARTIDA_S = 30.0


def notificar(mensagem: str) -> bool:
    """Manda ``mensagem`` ao ``NOTIFY_SOCKET``. ``True`` só se o datagrama saiu.

    Melhor esforço: o aviso perdido não derruba o daemon (o systemd, sem o pronto, estoura o
    ``TimeoutStartSec`` e o diário diz isso).
    """
    alvo = os.environ.get("NOTIFY_SOCKET")
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


__all__ = ["PRAZO_DA_PARTIDA_S", "notificar", "parando", "pronto"]
