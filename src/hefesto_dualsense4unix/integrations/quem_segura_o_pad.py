"""Quem segura os nós de cada pad virtual deste produto; o veredito é o de `quem_o_jogo_le`."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.integrations.no_do_vpad import resolver_no_do_vpad
from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
    Segurador,
    _inode,
    _texto,
    conta_como_jogo,
    por_que_conta,
    seguradores,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

RAIZ_PROC = "/proc"
RAIZ_DEV = "/dev"

_APROVADOS_NO_DIARIO: dict[str, tuple[int, str, str]] = {}


def _caminho(valor: Any) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def nos_do_pad(
    vpad: Any,
    *,
    resolver: Callable[..., dict[str, Any]] = resolver_no_do_vpad,
    raiz_dev: str | None = None,
) -> dict[str, int | None]:
    """``{caminho do nó: inode}`` de um pad virtual, em todo caminho do produto.

    - uhid (DualSense e Edge): o ``evdev`` e o ``hidraw`` do `no_do_vpad`, pelo ``uniq`` forjado;
    - gadget USB: o mesmo, e o ``hidraw`` do lado do jogo que o gadget anotou;
    - uinput (Xbox): os ``event`` e ``js`` do ``inputN`` que o kernel deu ao pad
      (``UI_GET_SYSNAME``, pelo `_nos_do_uinput`), que vale com os pads homônimos do co-op e
      nunca casa um Xbox de verdade pelo nome.
    """
    raiz_dev = RAIZ_DEV if raiz_dev is None else raiz_dev
    nos: dict[str, int | None] = {}
    uniq = _caminho(getattr(vpad, "mac", None))
    nome = _caminho(getattr(vpad, "name", None))
    if uniq:
        resolvido = resolver(uniq=uniq, nome=nome)
        for chave_no, chave_ino in (("evdev", "ino"), ("hidraw", "hidraw_ino")):
            caminho = _caminho(resolvido.get(chave_no))
            if caminho:
                ino = resolvido.get(chave_ino)
                nos[caminho] = ino if isinstance(ino, int) else None
    gadget = getattr(vpad, "_gadget", None)
    hidraw_do_gadget = _caminho(getattr(gadget, "hidraw", None))
    if hidraw_do_gadget:
        nos.setdefault(os.path.join(raiz_dev, os.path.basename(hidraw_do_gadget)), None)
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad, _nos_do_uinput

    if isinstance(vpad, UinputGamepad):
        for caminho_uinput in _nos_do_uinput(vpad):
            nos.setdefault(caminho_uinput, None)
    return nos


def inodes(nos: dict[str, int | None]) -> dict[int, str]:
    """``{inode: caminho}``: o publicado pelo `no_do_vpad`, ou o ``os.stat``, que não abre o nó."""
    achados: dict[int, str] = {}
    for caminho, ino in nos.items():
        if ino is None:
            ino = _inode(caminho)
        if ino:
            achados[ino] = caminho
    return achados


def jogos_por_pad(
    pads: dict[str, Any],
    *,
    raiz_proc: str | None = None,
    resolver: Callable[..., dict[str, Any]] = resolver_no_do_vpad,
    raiz_dev: str | None = None,
    meu_pid: int | None = None,
) -> dict[str, Segurador]:
    """``{chave: jogo}`` de cada pad de ``pads`` (``{chave: vpad}``) que um jogo segura.

    Uma varredura só para todos os pads; o primeiro valor é o primeiro jogo achado no ``/proc``.
    """
    raiz_proc = RAIZ_PROC if raiz_proc is None else raiz_proc
    raiz_dev = RAIZ_DEV if raiz_dev is None else raiz_dev
    alvos: dict[int, str] = {}
    dono_do_no: dict[str, str] = {}
    for chave, vpad in pads.items():
        for ino, caminho in inodes(nos_do_pad(vpad, resolver=resolver, raiz_dev=raiz_dev)).items():
            alvos[ino] = caminho
            dono_do_no[caminho] = chave
    eu = os.getpid() if meu_pid is None else meu_pid
    e_jogo: dict[int, tuple[bool, str]] = {}
    achados: dict[str, Segurador] = {}
    for segurador in seguradores(alvos, raiz_proc=raiz_proc, todos_os_nos=True):
        dono = dono_do_no.get(segurador.no)
        if dono is None or dono in achados:
            continue
        if segurador.pid not in e_jogo:
            cmdline = _texto(os.path.join(raiz_proc, str(segurador.pid), "cmdline"))
            e_jogo[segurador.pid] = por_que_conta(
                segurador.nome, cmdline, pid=segurador.pid, meu_pid=eu, raiz_proc=raiz_proc
            )
        if e_jogo[segurador.pid][0]:
            achados[dono] = segurador
    _diz_quem_aprovou(achados, e_jogo, dono_do_no)
    return achados


def _diz_quem_aprovou(
    achados: dict[str, Segurador],
    e_jogo: dict[int, tuple[bool, str]],
    dono_do_no: dict[str, str],
) -> None:
    """Registra, só quando muda, o processo que segura cada pad como jogo e o motivo."""
    for dono in set(dono_do_no.values()) - set(achados):
        _APROVADOS_NO_DIARIO.pop(dono, None)
    for dono, segurador in achados.items():
        motivo = e_jogo[segurador.pid][1]
        marca = (segurador.pid, segurador.nome, motivo)
        if _APROVADOS_NO_DIARIO.get(dono) == marca:
            continue
        _APROVADOS_NO_DIARIO[dono] = marca
        logger.info(
            "pad_segurado_por_jogo",
            pad=dono,
            processo=segurador.nome,
            pid=segurador.pid,
            motivo=motivo,
        )


def quem_segura(
    nos: dict[str, int | None],
    *,
    raiz_proc: str | None = None,
    meu_pid: int | None = None,
) -> list[tuple[Segurador, bool, str]]:
    """Cada processo que segura um dos ``nos``, se conta como jogo e por quê."""
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    eu = os.getpid() if meu_pid is None else meu_pid
    vereditos = []
    for segurador in seguradores(inodes(nos), raiz_proc=raiz):
        cmdline = _texto(os.path.join(raiz, str(segurador.pid), "cmdline"))
        jogo, motivo = por_que_conta(
            segurador.nome, cmdline, pid=segurador.pid, meu_pid=eu, raiz_proc=raiz
        )
        vereditos.append((segurador, jogo, motivo))
    return vereditos


__all__ = [
    "Segurador",
    "conta_como_jogo",
    "inodes",
    "jogos_por_pad",
    "nos_do_pad",
    "quem_segura",
]
