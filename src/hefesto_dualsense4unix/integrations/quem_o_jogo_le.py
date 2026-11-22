"""Quem joga: o processo com a assinatura de jogo no ambiente, ou o que lê um pad virtual.

Só a biblioteca padrão: o ``--ha-jogo`` roda com ``python3 -I``, sem o pacote. Quem segura o nó
de um pad se acha por ``readlink`` e ``os.stat`` do descritor, nunca ``open``; quem não é jogo
se reconhece por propriedade (`por_que_conta`): o Hefesto, a Steam, o dono do soquete Wayland, o
serviço de fundo e, por função, os lançadores, os remapeadores e os teclados da tela.
"""

from __future__ import annotations

import os
import pathlib
import re
import socket
import stat
import struct
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

ENV_DO_JOGO = "STEAM_COMPAT_DATA_PATH"

_STEAM_LAUNCH_RE = re.compile(r"SteamLaunch AppId=\d")

_STEAM_LAUNCH_APPID_RE = re.compile(r"SteamLaunch AppId=\d+")

_TOKEN_DO_INSTALL_SCRIPT = "Install=1"

PHYS_DO_VPAD = "hefesto-vpad"
UNIQS_DO_VPAD: tuple[str, ...] = ("02:fe:", "hefesto-")
MARCA_NO_NOME = "(Hefesto"

__all__ = [
    "AGULHAS_DO_HEFESTO",
    "ARVORE_DA_STEAM",
    "ASSINATURAS_DE_JOGO",
    "ENV_DO_JOGO",
    "FUNCAO_DO_LEITOR",
    "NOME_DO_REAPER",
    "ORCAMENTO_DA_VARREDURA_S",
    "SERVIDORES_DE_TELA",
    "Segurador",
    "conta_como_jogo",
    "descendentes",
    "e_avaliador_do_install_script",
    "ha_jogo_aberto",
    "main",
    "nos_dos_pads_virtuais",
    "pids_de_jogo",
    "pids_dos_compositores",
    "por_que_conta",
    "seguradores",
]


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
RAIZ_SYS = "/sys"
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


_MARCA_DO_JOGO = f"{ENV_DO_JOGO}=".encode()
_LIDOS_POR_PROGRAMA: dict[str, dict[int, tuple[str, bool]]] = {}


def pids_de_jogo(raiz_proc: pathlib.Path | str = "/proc") -> set[int]:
    """Os processos que são JOGO, pelo ambiente e não pelo nome.

    O ambiente de um processo só muda no ``exec``: cada pid se lê uma vez por programa (o alvo
    do ``exe``), e a varredura seguinte só abre o ambiente do processo novo ou do que trocou de
    programa. Guarda só os pids da última varredura da mesma raiz.
    """
    raiz = os.fspath(raiz_proc)
    antes = _LIDOS_POR_PROGRAMA.get(raiz, {})
    agora: dict[int, tuple[str, bool]] = {}
    for nome in _entradas(raiz):
        if not nome.isdigit():
            continue
        pid = int(nome)
        programa = _alvo_do_link(f"{raiz}/{nome}/exe")
        lido = antes.get(pid)
        if lido is None or lido[0] != programa:
            lido = (programa, _MARCA_DO_JOGO in _bruto(f"{raiz}/{nome}/environ"))
        agora[pid] = lido
    _LIDOS_POR_PROGRAMA.clear()
    _LIDOS_POR_PROGRAMA[raiz] = agora
    return {pid for pid, (_, jogo) in agora.items() if jogo}


def e_avaliador_do_install_script(cmd: str) -> bool:
    """A cmdline é o avaliador do install script da Steam, e não um jogo?"""
    achado = _STEAM_LAUNCH_APPID_RE.search(cmd)
    if achado is None:
        return False
    argumentos_do_reaper = cmd[achado.end():].split(" -- ", 1)[0]
    return _TOKEN_DO_INSTALL_SCRIPT in argumentos_do_reaper.split()


def _o_reaper_do_jogo(cmdline: str) -> bool:
    return bool(_STEAM_LAUNCH_RE.search(cmdline)) and not e_avaliador_do_install_script(cmdline)


def _assinatura_de_jogo(raiz_proc: str, pid: int) -> str | None:
    ambiente = _bruto(os.path.join(raiz_proc, str(pid), "environ")).split(b"\0")
    chaves = {item.partition(b"=")[0].decode("utf-8", "replace") for item in ambiente}
    return next((chave for chave in ASSINATURAS_DE_JOGO if chave in chaves), None)


def _pai(raiz_proc: str, pid: int) -> int:
    campos = _texto(os.path.join(raiz_proc, str(pid), "stat")).rpartition(")")[2].split()
    return int(campos[1]) if len(campos) > 1 and campos[1].isdigit() else 0


def _reaper_da_steam_acima(raiz_proc: str, pid: int) -> str | None:
    """A linha de comando do reaper da Steam mais perto acima de ``pid``; ``None`` sem nenhum."""
    vistos = {pid}
    atual = _pai(raiz_proc, pid)
    while atual > 1 and atual not in vistos:
        vistos.add(atual)
        pasta = os.path.join(raiz_proc, str(atual))
        if _texto(os.path.join(pasta, "comm")) == NOME_DO_REAPER:
            cmdline = _texto(os.path.join(pasta, "cmdline"))
            if _STEAM_LAUNCH_RE.search(cmdline):
                return cmdline
        atual = _pai(raiz_proc, atual)
    return None


def _descende_do_reaper_do_jogo(raiz_proc: str, pid: int) -> bool:
    acima = _reaper_da_steam_acima(raiz_proc, pid)
    return acima is not None and _o_reaper_do_jogo(acima)


def _descende_do_avaliador_do_install_script(raiz_proc: str, pid: int) -> bool:
    acima = _reaper_da_steam_acima(raiz_proc, pid)
    return acima is not None and e_avaliador_do_install_script(acima)


def _e_do_wine(nome: str) -> bool:
    return nome.startswith("wine") or nome.lower().endswith(".exe")


_DONOS_DOS_SOQUETES: dict[str, tuple[int, int]] = {}


def _modo_e_inode(caminho: str) -> tuple[int, int]:
    try:
        estado = os.stat(caminho)
    except OSError:
        return 0, 0
    return estado.st_mode, estado.st_ino


def _dono_do_soquete(caminho: str) -> int:
    """O pid do processo que escuta no soquete, pelo ``SO_PEERCRED``; ``0`` sem resposta."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cliente:
            cliente.setblocking(False)
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
        modo, ino = _modo_e_inode(caminho)
        if not stat.S_ISSOCK(modo):
            continue
        guardado = _DONOS_DOS_SOQUETES.get(caminho)
        if guardado is None or guardado[0] != ino:
            guardado = (ino, _dono_do_soquete(caminho))
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
    if _descende_do_avaliador_do_install_script(raiz, pid):
        return False, "o avaliador do script de instalação da Steam"
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


def _varrer(
    alvos: dict[int, str], raiz_proc: str, todos_os_nos: bool
) -> tuple[list[Segurador], bool]:
    """Os seguradores de ``alvos`` e se a varredura chegou ao fim dentro do orçamento."""
    nomes_dos_nos = {os.path.basename(caminho) for caminho in alvos.values()}
    achados: list[Segurador] = []
    prazo = time.monotonic() + ORCAMENTO_DA_VARREDURA_S
    for entrada in _entradas(raiz_proc):
        if not entrada.isdigit():
            continue
        pasta = os.path.join(raiz_proc, entrada, "fd")
        vistos: set[str] = set()
        for descritor in _entradas(pasta):
            if time.monotonic() > prazo:
                return achados, False
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
    return achados, True


def seguradores(
    alvos: dict[int, str], *, raiz_proc: str | None = None, todos_os_nos: bool = False
) -> list[Segurador]:
    """Todo processo com um descritor num dos ``alvos`` (``{inode: caminho}``), sem abrir o nó.

    Com ``todos_os_nos``, um processo entra uma vez por nó que segura; sem, só pelo primeiro.
    """
    if not alvos:
        return []
    return _varrer(alvos, RAIZ_PROC if raiz_proc is None else raiz_proc, todos_os_nos)[0]


def _e_do_hefesto(phys: str, uniq: str, nome: str) -> bool:
    uniq = uniq.casefold()
    return (
        phys.casefold().startswith(PHYS_DO_VPAD)
        or uniq.startswith(UNIQS_DO_VPAD)
        or MARCA_NO_NOME in nome
    )


def nos_dos_pads_virtuais(
    raiz_sys: str | None = None, raiz_dev: str | None = None
) -> dict[int, str]:
    """``{inode: nó}`` de todo ``hidraw``, ``event`` e ``js`` de um pad virtual do Hefesto."""
    sys_ = RAIZ_SYS if raiz_sys is None else raiz_sys
    dev = RAIZ_DEV if raiz_dev is None else raiz_dev
    nos: list[str] = []
    classe = os.path.join(sys_, "class", "hidraw")
    for no in _entradas(classe):
        campos = dict(
            linha.partition("=")[::2]
            for linha in _texto(os.path.join(classe, no, "device", "uevent")).splitlines()
        )
        if _e_do_hefesto(campos.get("HID_PHYS", ""), campos.get("HID_UNIQ", ""),
                         campos.get("HID_NAME", "")):
            nos.append(os.path.join(dev, no))
    classe = os.path.join(sys_, "class", "input")
    for no in _entradas(classe):
        if not no.startswith(("event", "js")):
            continue
        aparelho = os.path.join(classe, no, "device")
        if _e_do_hefesto(*(_texto(os.path.join(aparelho, f)) for f in ("phys", "uniq", "name"))):
            nos.append(os.path.join(dev, "input", no))
    return {ino: no for no in nos if (ino := _inode(no))}


class NaoSeiError(Exception):
    """A pergunta do jogo ficou sem resposta: «não sei» é jogo para quem pergunta."""


def _pids_da_raiz(raiz: str) -> list[int]:
    """Os pids da raiz do ``/proc``; ``NaoSeiError`` quando a raiz não se lê."""
    try:
        nomes = os.listdir(raiz)
    except OSError as erro:
        raise NaoSeiError(f"{raiz} não se lê") from erro
    return [int(nome) for nome in nomes if nome.isdigit()]


def ha_jogo_aberto(
    raiz_proc: str | None = None,
    raiz_sys: str | None = None,
    raiz_dev: str | None = None,
    *,
    meu_pid: int | None = None,
    levanta_na_duvida: bool = False,
) -> bool:
    """Há jogo: a assinatura de jogo no ambiente, ou quem segura um pad virtual e conta como jogo.

    «Não sei» é jogo: a raiz do ``/proc`` que não se lê e a varredura que estoura o orçamento.
    Com ``levanta_na_duvida``, o «não sei» levanta ``NaoSeiError``.
    """
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    eu = os.getpid() if meu_pid is None else meu_pid
    try:
        pids = _pids_da_raiz(raiz)
    except NaoSeiError:
        if levanta_na_duvida:
            raise
        return True
    candidatos = {pid for pid in pids if _assinatura_de_jogo(raiz, pid)}
    alvos = nos_dos_pads_virtuais(raiz_sys, raiz_dev)
    if alvos:
        achados, inteira = _varrer(alvos, raiz, False)
        if not inteira:
            if levanta_na_duvida:
                raise NaoSeiError("a varredura dos pads virtuais estourou o orçamento")
            return True
        candidatos.update(s.pid for s in achados)
    return any(
        conta_como_jogo(
            _texto(os.path.join(raiz, str(pid), "comm")),
            _texto(os.path.join(raiz, str(pid), "cmdline")),
            pid=pid, meu_pid=eu, raiz_proc=raiz,
        )
        for pid in candidatos
    )


def descendentes(pids: Iterable[int], raiz_proc: str | None = None) -> list[int]:
    """Os processos abaixo de ``pids`` pela cadeia de ``PPid``, sem os próprios ``pids``."""
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    filhos: dict[int, list[int]] = {}
    for entrada in _entradas(raiz):
        if entrada.isdigit():
            filhos.setdefault(_pai(raiz, int(entrada)), []).append(int(entrada))
    fila, achados = list(pids), []
    vistos = set(fila)
    while fila:
        for filho in filhos.get(fila.pop(), []):
            if filho not in vistos:
                vistos.add(filho)
                achados.append(filho)
                fila.append(filho)
    return achados


COM_JOGO = 0
SEM_JOGO = 10
USO = 2
NAO_SEI = 3


def main(argv: list[str] | None = None) -> int:
    """``--ha-jogo [--proc RAIZ] [--sys RAIZ] [--dev RAIZ]``: o que a saída diz.

    ``COM_JOGO`` (0) com jogo em cena, ``SEM_JOGO`` (10) sem jogo, ``USO`` (2) para argumento
    inválido e ``NAO_SEI`` (3) quando a leitura levantou ou não soube (``NaoSeiError``). Só o
    ``SEM_JOGO`` exato libera quem pergunta: qualquer outra saída, inclusive o 1 de um
    interpretador que morreu antes do ``main``, é jogo aberto.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    raizes = dict(zip(args[1::2], args[2::2], strict=False))
    if not args or args[0] != "--ha-jogo" or set(raizes) - {"--proc", "--sys", "--dev"}:
        print("uso: quem_o_jogo_le.py --ha-jogo [--proc RAIZ] [--sys RAIZ] [--dev RAIZ]",
              file=sys.stderr)
        return USO
    try:
        jogo = ha_jogo_aberto(raizes.get("--proc"), raizes.get("--sys"), raizes.get("--dev"),
                              levanta_na_duvida=True)
    except Exception as erro:
        print(f"quem_o_jogo_le.py: não sei se há jogo ({type(erro).__name__})", file=sys.stderr)
        return NAO_SEI
    return COM_JOGO if jogo else SEM_JOGO


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
