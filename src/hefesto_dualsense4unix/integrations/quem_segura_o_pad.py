"""Quem segura os nós dos pads virtuais deste produto, e se é o jogo que lê o controle.

O processo com o inode de um pad (`no_do_vpad`) em ``/proc/<pid>/fd`` lê o controle; a varredura
faz ``readlink`` e ``os.stat`` do descritor, nunca ``open``. Quem não é jogo se reconhece por
propriedade (`por_que_conta`): o Hefesto, a Steam, o dono do soquete Wayland, o serviço de fundo
e, por função, os lançadores, os remapeadores e os teclados da tela.
"""

from __future__ import annotations

import os
import socket
import stat
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.no_do_vpad import resolver_no_do_vpad
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    _STEAM_LAUNCH_RE,
    e_avaliador_do_install_script,
)

ARVORE_DA_STEAM: frozenset[str] = frozenset({"steam", "steamwebhelper"})

NOME_DO_REAPER = "reaper"

AGULHAS_DO_HEFESTO: tuple[str, ...] = (
    "hefesto_dualsense4unix",
    "hefesto-dualsense4unix",
    "hefesto-hidraw-broker",
)

ASSINATURAS_DE_JOGO: tuple[str, ...] = (
    "STEAM_COMPAT_DATA_PATH",
    "SteamGameId",
    "UMU_ID",
    "LUTRIS_GAME_UUID",
)

SERVIDORES_DE_TELA: frozenset[str] = frozenset({"Xwayland", "Xorg"})

FUNCAO_DO_LEITOR: dict[str, str] = {
    "heroic": "lançador",
    "lutris": "lançador",
    "bottles": "lançador",
    "itch": "lançador",
    "chrome": "navegador",
    "chromium": "navegador",
    "electron": "aplicativo Electron",
    "input-remapper": "remapeador de entrada",
    "antimicrox": "remapeador de entrada",
    "joystickwake": "remapeador de entrada",
    "cosmic-osk": "teclado da tela",
    "onboard": "teclado da tela",
    "squeekboard": "teclado da tela",
    "maliit-server": "teclado da tela",
    "wvkbd": "teclado da tela",
}

ORCAMENTO_DA_VARREDURA_S: float = 0.5

RAIZ_PROC = "/proc"
RAIZ_DEV = "/dev"
RAIZ_RUNTIME: str | None = None


@dataclass(frozen=True)
class Segurador:
    """Um processo que segura o nó de um pad virtual."""

    pid: int
    nome: str
    no: str


def _bruto(caminho: str) -> bytes:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read()
    except OSError:
        return b""


def _texto(caminho: str) -> str:
    return _bruto(caminho).replace(b"\0", b" ").decode("utf-8", "replace").strip()


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


def _o_reaper_do_jogo(cmdline: str) -> bool:
    return bool(_STEAM_LAUNCH_RE.search(cmdline)) and not e_avaliador_do_install_script(cmdline)


def _assinatura_de_jogo(raiz_proc: str, pid: int) -> str | None:
    ambiente = _bruto(os.path.join(raiz_proc, str(pid), "environ")).split(b"\0")
    chaves = {item.partition(b"=")[0].decode("utf-8", "replace") for item in ambiente}
    return next((chave for chave in ASSINATURAS_DE_JOGO if chave in chaves), None)


def _pai(raiz_proc: str, pid: int) -> int:
    campos = _texto(os.path.join(raiz_proc, str(pid), "stat")).rpartition(")")[2].split()
    return int(campos[1]) if len(campos) > 1 and campos[1].isdigit() else 0


def _descende_do_reaper_do_jogo(raiz_proc: str, pid: int) -> bool:
    vistos = {pid}
    atual = _pai(raiz_proc, pid)
    while atual > 1 and atual not in vistos:
        vistos.add(atual)
        pasta = os.path.join(raiz_proc, str(atual))
        if _texto(os.path.join(pasta, "comm")) == NOME_DO_REAPER and _o_reaper_do_jogo(
            _texto(os.path.join(pasta, "cmdline"))
        ):
            return True
        atual = _pai(raiz_proc, atual)
    return False


def _e_do_wine(nome: str) -> bool:
    return nome.startswith("wine") or nome.lower().endswith(".exe")


_DONOS_DOS_SOQUETES: dict[str, tuple[int, int]] = {}


def _dono_do_soquete(caminho: str) -> int:
    """O pid do processo que escuta no soquete, pelo ``SO_PEERCRED``; ``0`` sem resposta."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cliente:
        cliente.setblocking(False)
        try:
            cliente.connect(caminho)
            credenciais = cliente.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
        except OSError:
            return 0
    return int(struct.unpack("3i", credenciais)[0])


def pids_dos_compositores(raiz_runtime: str | None = None) -> set[int]:
    """Os donos dos soquetes Wayland da sessão (``$WAYLAND_DISPLAY`` e todo ``wayland-*``)."""
    raiz = raiz_runtime or RAIZ_RUNTIME or os.environ.get("XDG_RUNTIME_DIR") or ""
    nomes = {nome for nome in _entradas(raiz) if nome.startswith("wayland-")}
    nomes.add(os.environ.get("WAYLAND_DISPLAY", ""))
    pids: set[int] = set()
    for nome in nomes - {""}:
        caminho = os.path.join(raiz, nome)
        try:
            estado = os.stat(caminho)
        except OSError:
            continue
        if not stat.S_ISSOCK(estado.st_mode):
            continue
        guardado = _DONOS_DOS_SOQUETES.get(caminho)
        if guardado is None or guardado[0] != estado.st_ino:
            guardado = (estado.st_ino, _dono_do_soquete(caminho))
            _DONOS_DOS_SOQUETES[caminho] = guardado
        if guardado[1]:
            pids.add(guardado[1])
    return pids


def _funcao(nome: str, cmdline: str) -> str | None:
    argumentos = cmdline.split()
    candidatos = {nome, *(os.path.basename(a) for a in argumentos[:2])}
    for chave, funcao in FUNCAO_DO_LEITOR.items():
        if any(c == chave or c.startswith(chave + "-") for c in candidatos):
            return funcao
    return None


def _unidade(raiz_proc: str, pid: int) -> str | None:
    """A unidade do systemd mais funda no ``cgroup`` do processo; ``None`` sem leitura."""
    linhas = _texto(os.path.join(raiz_proc, str(pid), "cgroup")).splitlines()
    linha = next((x for x in linhas if x.startswith("0::")), linhas[0] if linhas else "")
    partes = [p for p in linha.partition("::")[2].split("/") if p.endswith((".service", ".scope"))]
    return partes[-1] if partes else None


def por_que_conta(
    nome: str,
    cmdline: str,
    *,
    pid: int,
    meu_pid: int,
    raiz_proc: str | None = None,
    compositores: Callable[[], set[int]] = pids_dos_compositores,
) -> tuple[bool, str]:
    """``(é jogo, por quê)`` do processo que segura o nó de um pad virtual."""
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    if pid == meu_pid or any(agulha in cmdline for agulha in AGULHAS_DO_HEFESTO):
        return False, "o Hefesto"
    if nome in ARVORE_DA_STEAM:
        return False, "a Steam"
    if nome == NOME_DO_REAPER:
        if _o_reaper_do_jogo(cmdline):
            return True, "o reaper do jogo"
        return False, "o reaper fora de jogo"
    assinatura = _assinatura_de_jogo(raiz, pid)
    if assinatura is not None:
        return True, f"{assinatura} no ambiente"
    if _descende_do_reaper_do_jogo(raiz, pid):
        return True, "descende do reaper do jogo"
    if _e_do_wine(nome):
        return True, "o Wine"
    if nome in SERVIDORES_DE_TELA or pid in compositores():
        return False, "o compositor da sessão"
    funcao = _funcao(nome, cmdline)
    if funcao is not None:
        return False, funcao
    if "--type=" in cmdline:
        return False, "processo auxiliar do Chromium ou do Electron"
    unidade = _unidade(raiz, pid)
    if unidade is not None and unidade.endswith(".service") and not unidade.startswith("app-"):
        return False, f"serviço de fundo ({unidade})"
    return True, "aplicativo aberto que lê o controle"


def conta_como_jogo(
    nome: str, cmdline: str, *, pid: int, meu_pid: int, raiz_proc: str | None = None
) -> bool:
    """O processo que segura o nó é um jogo? (`por_que_conta`)."""
    return por_que_conta(nome, cmdline, pid=pid, meu_pid=meu_pid, raiz_proc=raiz_proc)[0]


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
                segurador.nome, cmdline, pid=segurador.pid, meu_pid=eu, raiz_proc=raiz_proc
            )
        if e_jogo[segurador.pid]:
            achados[dono] = segurador
    return achados


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
    "AGULHAS_DO_HEFESTO",
    "ARVORE_DA_STEAM",
    "ASSINATURAS_DE_JOGO",
    "FUNCAO_DO_LEITOR",
    "NOME_DO_REAPER",
    "ORCAMENTO_DA_VARREDURA_S",
    "SERVIDORES_DE_TELA",
    "Segurador",
    "conta_como_jogo",
    "inodes",
    "jogos_por_pad",
    "nos_do_pad",
    "pids_dos_compositores",
    "por_que_conta",
    "quem_segura",
    "seguradores",
]
