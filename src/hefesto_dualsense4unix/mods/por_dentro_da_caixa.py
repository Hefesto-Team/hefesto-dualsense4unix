"""Muda a caixa aberta de uma extensão por dentro, sem reabri-la: cobre o aparelho que o hub vivo
passou a mostrar e refaz os links da pasta sintética do HID.

Roda à parte (``python -I -S por_dentro_da_caixa.py <pid>``), numa linha só de execução, como o
``setns`` pede: entra no espaço de montagem de ``pid`` e no de usuário DONO dele
(``NS_GET_USERNS``); o ``chroot`` na raiz da caixa não deixa link de dentro apontar para fora.
Lê da entrada ``{"cobrir": [pasta], "pasta_dos_links": pasta, "ligar": {nome: alvo},
"desligar": [nome]}`` e escreve ``{"cobertos": [pasta], "falhas": [frase]}``.
"""
from __future__ import annotations

import ctypes
import fcntl
import json
import os
import sys

NS_GET_USERNS = 0xB701

MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC = 1, 2, 4, 8


def entrar(pid: int) -> None:
    """Entra no espaço de usuário dono do espaço de montagem de ``pid`` e na raiz dele."""
    montagem = os.open(f"/proc/{pid}/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    usuario = fcntl.ioctl(montagem, NS_GET_USERNS)
    raiz = os.open(f"/proc/{pid}/root", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    os.setns(usuario, os.CLONE_NEWUSER)
    os.setns(montagem, os.CLONE_NEWNS)
    os.fchdir(raiz)
    os.chroot(".")
    os.chdir("/")


def cobrir(pasta: str) -> str | None:
    """Um ``tmpfs`` só de leitura por cima de ``pasta``; ``None``, ou a frase da falha."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.mount(b"tmpfs", os.fsencode(pasta), b"tmpfs",
                  MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, b"mode=0555") == 0:
        return None
    erro = ctypes.get_errno()
    return f"{pasta}: {os.strerror(erro)}"


def refazer_os_links(pasta: str, ligar: dict[str, str], desligar: list[str]) -> list[str]:
    """Tira os links ``desligar`` e põe os ``ligar`` em ``pasta``; devolve as falhas."""
    falhas: list[str] = []
    try:
        dono = os.open(pasta, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError as exc:
        return [f"{pasta}: {exc.strerror}"]
    try:
        for nome in desligar:
            if "/" not in nome and os.path.islink(os.path.join(pasta, nome)):
                os.unlink(nome, dir_fd=dono)
        for nome, alvo in ligar.items():
            if "/" in nome or nome in (".", ".."):
                falhas.append(f"{nome}: nome de link inválido")
                continue
            if os.path.islink(os.path.join(pasta, nome)):
                os.unlink(nome, dir_fd=dono)
            os.symlink(alvo, nome, dir_fd=dono)
    except OSError as exc:
        falhas.append(f"{pasta}: {exc.strerror}")
    finally:
        os.close(dono)
    return falhas


def main() -> int:
    pedido = json.load(sys.stdin)
    try:
        entrar(int(sys.argv[1]))
    except (OSError, ValueError, IndexError) as exc:
        print(json.dumps({"cobertos": [], "falhas": [f"entrar: {exc}"]}))
        return 1
    cobertos: list[str] = []
    falhas: list[str] = []
    for pasta in pedido.get("cobrir", []):
        falha = cobrir(pasta)
        if falha is None:
            cobertos.append(pasta)
        else:
            falhas.append(falha)
    if pedido.get("pasta_dos_links"):
        falhas += refazer_os_links(pedido["pasta_dos_links"], pedido.get("ligar", {}),
                                   pedido.get("desligar", []))
    print(json.dumps({"cobertos": cobertos, "falhas": falhas}))
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
