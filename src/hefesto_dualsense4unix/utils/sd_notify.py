"""O aviso do daemon ao systemd («pronto», «vivo», «parando») e o depósito de descritores.

Dono ÚNICO do aviso e do soquete: ``guardar_o_soquete``, na entrada do daemon, tira o
``NOTIFY_SOCKET`` (e o ``LISTEN_*``) de ``os.environ``, e nenhum filho o herda. Sem soquete (o
daemon avulso, os testes) não faz nada e não levanta. O broker segue com o ``_sd_notify`` dele.
O nó do controle virtual se guarda no systemd (``FDSTORE``, :func:`guardar_descritor`) e o
serviço que volta o recebe pelo nome (:func:`tomar_herdado`); o que nenhum controle toma em
``PRAZO_DOS_HERDADOS_S`` se fecha. OS-PADS-VIRTUAIS-SOBREVIVEM-A-QUEDA-DO-SERVICO-01.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import re
import socket
import struct
import threading

PRAZO_DA_PARTIDA_S = 30.0

PRAZO_DOS_HERDADOS_S = 20.0

PRIMEIRO_DESCRITOR_HERDADO = 3

VARIAVEIS_DO_PRINCIPAL: tuple[str, ...] = (
    "NOTIFY_SOCKET", "WATCHDOG_PID", "WATCHDOG_USEC", "LISTEN_PID", "LISTEN_FDS",
    "LISTEN_FDNAMES",
)

_guardadas: dict[str, str] = {}
_herdados: dict[str, int] = {}
_no_deposito: set[str] = set()
_trava = threading.Lock()
_estado = {"parando": False}
_FORA_DO_NOME = re.compile(r"[^A-Za-z0-9_.-]")


def guardar_o_soquete() -> None:
    """Tira de ``os.environ`` as variáveis do principal e as guarda para o aviso.

    Idempotente: a segunda chamada, com o ambiente já limpo, não perde o que guardou. Sem
    ``NOTIFY_SOCKET`` (o daemon avulso, os testes) não faz nada.
    """
    for nome in VARIAVEIS_DO_PRINCIPAL:
        valor = os.environ.pop(nome, None)
        if valor:
            _guardadas[nome] = valor
    herdados = ler_os_herdados(
        {nome: _guardadas.pop(nome) for nome in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES")
         if nome in _guardadas}
    )
    if herdados:
        with _trava:
            _herdados.update(herdados)
            _no_deposito.update(herdados)
        vigia = threading.Timer(PRAZO_DOS_HERDADOS_S, fechar_os_herdados_que_sobraram)
        vigia.daemon = True
        vigia.name = "hefesto-herdados-do-deposito"
        vigia.start()


def ler_os_herdados(
    ambiente: dict[str, str], primeiro: int = PRIMEIRO_DESCRITOR_HERDADO
) -> dict[str, int]:
    """``{nome: fd}`` dos descritores que o systemd passou a ESTE processo (``LISTEN_*``).

    Só vale com ``LISTEN_PID`` igual ao pid de agora; os fds começam em ``primeiro`` e ganham
    ``FD_CLOEXEC`` (nenhum filho os herda). Nome repetido fica com o primeiro; o resto se fecha.
    """
    if ambiente.get("LISTEN_PID") != str(os.getpid()):
        return {}
    try:
        quantos = int(ambiente.get("LISTEN_FDS", "0"))
    except ValueError:
        return {}
    nomes = ambiente.get("LISTEN_FDNAMES", "").split(":")
    herdados: dict[str, int] = {}
    for i in range(max(0, quantos)):
        fd = primeiro + i
        with contextlib.suppress(OSError):
            fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
        nome = nomes[i] if i < len(nomes) else ""
        if not nome or nome in herdados:
            with contextlib.suppress(OSError):
                os.close(fd)
            continue
        herdados[nome] = fd
    return herdados


def nome_no_deposito(*partes: object) -> str:
    """O ``FDNAME`` de um nó: as partes unidas por ``-``, só com o que o systemd aceita."""
    return _FORA_DO_NOME.sub("", "-".join(str(p) for p in partes))[:255]


def guardar_descritor(fd: int, nome: str) -> bool:
    """Guarda ``fd`` no depósito do systemd sob ``nome`` (``FDSTORE=1``). True = saiu."""
    alvo = _soquete()
    if not alvo or not nome:
        return False
    if alvo.startswith("@"):
        alvo = "\0" + alvo[1:]
    mensagem = f"FDSTORE=1\nFDNAME={nome}".encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as soquete:
            soquete.sendmsg(
                [mensagem], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", fd))],
                0, alvo,
            )
    except OSError:
        return False
    with _trava:
        _no_deposito.add(nome)
    return True


def soltar_descritor(nome: str) -> bool:
    """Tira ``nome`` do depósito (``FDSTOREREMOVE=1``): o nó deixa de sobreviver ao serviço."""
    with _trava:
        estava = nome in _no_deposito
        _no_deposito.discard(nome)
    return estava and notificar(f"FDSTOREREMOVE=1\nFDNAME={nome}")


def no_deposito(nome: str | None) -> bool:
    """O nó ``nome`` está guardado no systemd (guardado aqui ou herdado)."""
    with _trava:
        return bool(nome) and nome in _no_deposito


def tomar_herdado(nome: str | None) -> int | None:
    """O fd herdado de ``nome``, uma vez só; ``None`` sem herdado com esse nome."""
    if not nome:
        return None
    with _trava:
        return _herdados.pop(nome, None)


def fechar_os_herdados_que_sobraram() -> list[str]:
    """Fecha o herdado que nenhum controle tomou e o tira do depósito: o nó dele sai do kernel."""
    with _trava:
        sobras = dict(_herdados)
        _herdados.clear()
    for nome, fd in sobras.items():
        soltar_descritor(nome)
        with contextlib.suppress(OSError):
            os.close(fd)
    return sorted(sobras)


def esta_parando() -> bool:
    """O desligamento do serviço começou (:func:`parando`, com o soquete do systemd): o nó
    guardado fica para o systemd decidir. Fora do systemd, nunca."""
    return _estado["parando"] and _soquete() is not None


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
    """``STOPPING=1``: o desligamento começou. O nó guardado no depósito deixa de se desfazer
    na parada: o systemd o fecha no ``stop`` e o devolve no reinício."""
    _estado["parando"] = True
    return notificar("STOPPING=1")


def vivo() -> bool:
    """``WATCHDOG=1``: o laço anda; sem ele no prazo do ``WatchdogSec``, o systemd reinicia."""
    return notificar("WATCHDOG=1")


def prazo_do_watchdog() -> float | None:
    """O ``WatchdogSec`` da unit em segundos, se for deste processo; ``None`` sem watchdog."""
    pid = _guardadas.get("WATCHDOG_PID") or os.environ.get("WATCHDOG_PID")
    micros = _guardadas.get("WATCHDOG_USEC") or os.environ.get("WATCHDOG_USEC")
    if not micros or not micros.isdigit() or int(micros) == 0:
        return None
    if pid and pid != str(os.getpid()):
        return None
    return int(micros) / 1e6


__all__ = [
    "PRAZO_DA_PARTIDA_S",
    "PRAZO_DOS_HERDADOS_S",
    "VARIAVEIS_DO_PRINCIPAL",
    "esta_parando",
    "fechar_os_herdados_que_sobraram",
    "guardar_descritor",
    "guardar_o_soquete",
    "ler_os_herdados",
    "no_deposito",
    "nome_no_deposito",
    "notificar",
    "parando",
    "prazo_do_watchdog",
    "pronto",
    "soltar_descritor",
    "tomar_herdado",
    "vivo",
]
