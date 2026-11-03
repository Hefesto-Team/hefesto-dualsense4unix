"""Quem segura os nós dos pads virtuais deste produto: o jogo que lê o controle.

O-JOGO-QUE-SEGURA-O-PAD-VIRTUAL-E-JOGO-VENHA-DE-ONDE-VIER-01 (03/11/2026): o processo com o
inode de um pad (`no_do_vpad`) em ``/proc/<pid>/fd`` está lendo o controle, venha o jogo de onde
vier. A varredura faz ``readlink`` e ``os.stat`` do descritor, nunca ``open``: não dispara
``UHID_OPEN`` nem entra na conta de quem fecha por último. Não contam: os leitores medidos numa
mesa sem jogo, a árvore da Steam e os processos do próprio Hefesto.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.no_do_vpad import resolver_no_do_vpad
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    _STEAM_LAUNCH_RE,
    e_avaliador_do_install_script,
)

LEITORES_SEM_JOGO: frozenset[str] = frozenset({"cosmic-osk", "cosmic-comp", "systemd-logind"})

ARVORE_DA_STEAM: frozenset[str] = frozenset({"steam", "steamwebhelper"})

NOME_DO_REAPER = "reaper"

AGULHAS_DO_HEFESTO: tuple[str, ...] = (
    "hefesto_dualsense4unix",
    "hefesto-dualsense4unix",
    "hefesto-hidraw-broker",
)

ORCAMENTO_DA_VARREDURA_S: float = 0.5

RAIZ_PROC = "/proc"
RAIZ_DEV = "/dev"


@dataclass(frozen=True)
class Segurador:
    """Um processo que segura o nó de um pad virtual."""

    pid: int
    nome: str
    no: str


def _texto(caminho: str) -> str:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _entradas(pasta: str) -> list[str]:
    """O ``listdir``; ``[]`` quando o processo saiu entre a lista e a leitura."""
    try:
        return os.listdir(pasta)
    except OSError:
        return []


def _alvo_do_link(link: str) -> str:
    """O ``readlink``; ``""`` quando o descritor fechou no meio da varredura."""
    try:
        return os.readlink(link)
    except OSError:
        return ""


def _inode(caminho: str) -> int:
    """O inode por ``os.stat``, que não abre o nó; ``0`` (nenhum inode válido) quando ele sumiu."""
    try:
        return os.stat(caminho).st_ino
    except OSError:
        return 0


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
    - uinput (Xbox): o nó que o próprio dispositivo criou (``UI_GET_SYSNAME``, lido pelo evdev),
      que vale com os pads homônimos do co-op e nunca casa um Xbox de verdade pelo nome.
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
    do_uinput = getattr(getattr(vpad, "_device", None), "device", None)
    caminho_uinput = _caminho(getattr(do_uinput, "path", None))
    if caminho_uinput:
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


def conta_como_jogo(nome: str, cmdline: str, *, pid: int, meu_pid: int) -> bool:
    """O processo que segura o nó é um jogo, e não a mesa, a Steam ou o Hefesto?"""
    if pid == meu_pid or nome in LEITORES_SEM_JOGO or nome in ARVORE_DA_STEAM:
        return False
    if any(agulha in cmdline for agulha in AGULHAS_DO_HEFESTO):
        return False
    if nome == NOME_DO_REAPER:
        return bool(_STEAM_LAUNCH_RE.search(cmdline)) and not e_avaliador_do_install_script(cmdline)
    return True


def seguradores(
    alvos: dict[int, str],
    *,
    raiz_proc: str = RAIZ_PROC,
    relogio: Callable[[], float] = time.monotonic,
    orcamento_s: float = ORCAMENTO_DA_VARREDURA_S,
    todos_os_nos: bool = False,
) -> list[Segurador]:
    """Todo processo com um descritor num dos ``alvos`` (``{inode: caminho}``), sem abrir o nó.

    Com ``todos_os_nos``, um processo entra uma vez por nó que segura; sem, só pelo primeiro.
    """
    if not alvos:
        return []
    nomes_dos_nos = {os.path.basename(caminho) for caminho in alvos.values()}
    achados: list[Segurador] = []
    prazo = relogio() + orcamento_s
    for entrada in _entradas(raiz_proc):
        if not entrada.isdigit():
            continue
        pasta = os.path.join(raiz_proc, entrada, "fd")
        vistos: set[str] = set()
        for descritor in _entradas(pasta):
            if relogio() > prazo:
                return achados
            link = os.path.join(pasta, descritor)
            if os.path.basename(_alvo_do_link(link)) not in nomes_dos_nos:
                continue
            ino = _inode(link)
            no = alvos.get(ino)
            if no is None or no in vistos:
                continue
            vistos.add(no)
            nome = _texto(os.path.join(raiz_proc, entrada, "comm"))
            achados.append(Segurador(pid=int(entrada), nome=nome, no=no))
            if not todos_os_nos:
                break
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
    e_jogo: dict[int, bool] = {}
    achados: dict[str, Segurador] = {}
    for segurador in seguradores(alvos, raiz_proc=raiz_proc, todos_os_nos=True):
        dono = dono_do_no.get(segurador.no)
        if dono is None or dono in achados:
            continue
        if segurador.pid not in e_jogo:
            cmdline = _texto(os.path.join(raiz_proc, str(segurador.pid), "cmdline"))
            e_jogo[segurador.pid] = conta_como_jogo(
                segurador.nome, cmdline, pid=segurador.pid, meu_pid=eu
            )
        if e_jogo[segurador.pid]:
            achados[dono] = segurador
    return achados


def jogo_no_pad(
    vpads: Iterable[Any],
    *,
    raiz_proc: str | None = None,
    resolver: Callable[..., dict[str, Any]] = resolver_no_do_vpad,
    raiz_dev: str | None = None,
    meu_pid: int | None = None,
) -> Segurador | None:
    """O primeiro processo de JOGO que segura o nó de um dos ``vpads``, ou ``None``."""
    por_pad = jogos_por_pad(
        {str(indice): vpad for indice, vpad in enumerate(vpads)},
        raiz_proc=raiz_proc,
        resolver=resolver,
        raiz_dev=raiz_dev,
        meu_pid=meu_pid,
    )
    return next(iter(por_pad.values()), None)


__all__ = [
    "AGULHAS_DO_HEFESTO",
    "ARVORE_DA_STEAM",
    "LEITORES_SEM_JOGO",
    "NOME_DO_REAPER",
    "ORCAMENTO_DA_VARREDURA_S",
    "Segurador",
    "conta_como_jogo",
    "inodes",
    "jogo_no_pad",
    "jogos_por_pad",
    "nos_do_pad",
    "seguradores",
]
