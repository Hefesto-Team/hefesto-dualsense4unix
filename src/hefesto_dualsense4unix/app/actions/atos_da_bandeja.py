"""Os atos da bandeja que o controle também faz: abrir o painel e o serviço.

E o dono da própria bandeja (AS-TELAS-QUE-O-USUARIO-PEDIU-EM-16-10-01, S3 e S4): a escolha de ter o
ícone mora no autostart da sessão (`X-GNOME-Autostart-enabled` para o GNOME e `Hidden` para o
gerador do systemd, que o COSMIC e o Plasma usam; qualquer uma dizendo desligado desliga), a bandeja
viva é a que segura a vez da sessão (uma trava no runtime), e `garantir_a_bandeja` a sobe quando a
escolha está ligada e ninguém segura a vez.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import re
import select
import shlex
import signal
import struct
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from hefesto_dualsense4unix.utils import identidade, pedido_ao_servico
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

console = Console()

LANCADOR_DO_PAINEL = "hefesto-dualsense4unix-gui"

VERBOS: dict[str, str] = {"reiniciar": "restart", "parar": "stop", "ativar": "start"}
MOTIVOS_DA_BANDEJA: dict[str, str] = {
    "restart": "reiniciar-do-menu", "stop": "parar-do-menu", "start": "ativar-do-menu",
}


def abrir_o_painel() -> None:
    """O «Abrir programa» — a diferença que mais pesa entre os dois trays."""
    try:
        subprocess.Popen(
            [LANCADOR_DO_PAINEL],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        console.print(
            f"[yellow]não achei `{LANCADOR_DO_PAINEL}` no PATH[/] — "
            f"o lançador do painel não veio nesta instalação; "
            f"{como_atualizar_esta_instalacao()}.")


def mexer_no_servico(verbo: str) -> bool:
    """`restart` · `stop` · `start` pela unit desta instalação."""
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    unit = identidade.atual().unit_daemon
    janela = DaemonActionsMixin()
    if verbo in ("start", "restart"):
        janela._invoke_systemctl(["reset-failed", unit], check=False)
    pedido_ao_servico.anotar(verbo, "bandeja", MOTIVOS_DA_BANDEJA.get(verbo, verbo))
    resultado = janela._invoke_systemctl([verbo, unit], capture=True)
    pegou = getattr(resultado, "returncode", -1) == 0
    if verbo == "restart" and pegou:
        repor_o_lancador()
    if verbo in ("start", "restart") and pegou:
        garantir_a_bandeja()
    return pegou


def repor_o_lancador() -> None:
    """O «Reiniciar» da bandeja repõe o lançador, como o da aba Sistema."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    try:
        recibo = rl.repor()
    except Exception as erro:
        console.print(f"[yellow]não consegui repor o lançador:[/] {erro}")
        _avisar_no_desktop(f"Não consegui repor o lançador: {erro}")
        return
    frase = rl.frase_do_recibo(recibo)
    console.print(frase)
    if recibo.falhou:
        _avisar_no_desktop(frase)


def _avisar_no_desktop(frase: str) -> None:
    """O recibo que falhou vai à notificação do desktop: o console da bandeja ninguém lê."""
    from hefesto_dualsense4unix.integrations.desktop_notifications import notify

    notify("Reiniciar o serviço", frase)


CHAVE_DO_AUTOSTART = "X-GNOME-Autostart-enabled"
CHAVE_HIDDEN = "Hidden"
_LINHA_DA_CHAVE = re.compile(rf"^{CHAVE_DO_AUTOSTART}=.*$", re.M)
_LINHA_DO_HIDDEN = re.compile(rf"^{CHAVE_HIDDEN}=.*$", re.M)


def _valor_da_chave(linha: re.Pattern[str], texto: str) -> str | None:
    achado = linha.search(texto)
    return achado.group(0).split("=", 1)[1].strip().lower() if achado else None


def _escolha_do_texto(texto: str) -> bool:
    """O dono da leitura: desligada se o GNOME diz `false` ou o gerador diz `Hidden=true`."""
    return not (_valor_da_chave(_LINHA_DA_CHAVE, texto) == "false"
                or _valor_da_chave(_LINHA_DO_HIDDEN, texto) == "true")


def _com_a_chave(linha: re.Pattern[str], chave: str, valor: str, texto: str) -> str:
    nova = f"{chave}={valor}"
    return (linha.sub(nova, texto) if linha.search(texto)
            else texto.rstrip("\n") + f"\n{nova}\n")


def _escolha_no_texto(texto: str, ligada: bool) -> str:
    """O dono da escrita: as duas chaves juntas, para valer em toda sessão."""
    texto = _com_a_chave(_LINHA_DA_CHAVE, CHAVE_DO_AUTOSTART, "true" if ligada else "false", texto)
    return _com_a_chave(_LINHA_DO_HIDDEN, CHAVE_HIDDEN, "false" if ligada else "true", texto)


def caminho_do_autostart() -> Path:
    """O `.desktop` que a sessão lê ao entrar, o mesmo que o `install.sh` escreve."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{identidade.atual().app_id}-tray.desktop"


def caminho_da_vez() -> Path:
    """A trava da bandeja da sessão: some com a sessão, como a bandeja."""
    return runtime_dir() / "bandeja.vez"


_VEZ: list[int] = []
_TRAVA = struct.Struct("hhqqi4x")


def _abrir_a_vez() -> int:
    alvo = caminho_da_vez()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    return os.open(alvo, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


def _a_trava(tipo: int) -> bytes:
    return _TRAVA.pack(tipo, os.SEEK_SET, 0, 0, 0)


def tomar_a_vez() -> bool:
    """A bandeja que vai subir segura a vez da sessão; com outra de pé, diz que não.

    A vez é uma trava de descrição de arquivo aberto (`F_OFD_SETLK`): a pergunta
    (`bandeja_viva`) usa o `F_OFD_GETLK`, que não segura nada, e a tomada vale de primeira."""
    fd = _abrir_a_vez()
    try:
        fcntl.fcntl(fd, fcntl.F_OFD_SETLK, _a_trava(fcntl.F_WRLCK))
    except BlockingIOError:
        os.close(fd)
        return False
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode("ascii"))
    _VEZ.append(fd)
    return True


def soltar_a_vez() -> None:
    while _VEZ:
        os.close(_VEZ.pop())


def bandeja_ligada() -> bool:
    """A escolha «Ícone na bandeja»: o autostart existe e nenhuma das duas chaves o desliga."""
    try:
        texto = caminho_do_autostart().read_text(encoding="utf-8")
    except OSError:
        return False
    return _escolha_do_texto(texto)


def bandeja_desligada_pela_escolha() -> bool:
    """O autostart existe e diz desligado; sem arquivo não há escolha e a bandeja pedida sobe."""
    try:
        texto = caminho_do_autostart().read_text(encoding="utf-8")
    except OSError:
        return False
    return not _escolha_do_texto(texto)


def bandeja_viva() -> int | None:
    """O PID da bandeja que segura a vez da sessão, ou `None` se ninguém segura."""
    try:
        fd = _abrir_a_vez()
    except OSError as erro:
        console.print(f"[yellow]não consegui perguntar pela vez da bandeja:[/] {erro}")
        return None
    try:
        tipo = _TRAVA.unpack(fcntl.fcntl(fd, fcntl.F_OFD_GETLK, _a_trava(fcntl.F_RDLCK)))[0]
        if tipo == fcntl.F_UNLCK:
            return None
        texto = os.read(fd, 32).decode("ascii", "replace").strip()
        return int(texto) if texto.isdigit() else 0
    finally:
        os.close(fd)


def _e_a_linha_da_bandeja(argv: list[bytes]) -> bool:
    for i, arg in enumerate(argv):
        seguinte = argv[i + 1:i + 2]
        nome = os.path.basename(arg)
        if ((arg == b"hefesto_dualsense4unix.cli.app" and argv[i - 1:i] == [b"-m"])
                or nome == b"hefesto-dualsense4unix") and seguinte == [b"tray"]:
            return True
        if nome == b"run.sh" and seguinte == [b"--tray"]:
            return True
    return False


def _e_bandeja_da_sessao(pasta: Path, sessao: bytes) -> bool:
    """O processo de `pasta` é uma bandeja desta sessão; o que saiu no meio da leitura não é."""
    try:
        return (pasta.stat().st_uid == os.getuid()
                and _e_a_linha_da_bandeja((pasta / "cmdline").read_bytes().split(b"\0"))
                and sessao in (pasta / "environ").read_bytes().split(b"\0"))
    except (FileNotFoundError, ProcessLookupError):
        return False
    except OSError as erro:
        console.print(f"[yellow]não consegui ler o processo {pasta.name}:[/] {erro}")
        return False


def bandejas_da_sessao() -> list[int]:
    """As bandejas desta sessão pelo `/proc`: o mesmo usuário e o mesmo `XDG_RUNTIME_DIR`."""
    sessao = f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR', '')}".encode()
    return sorted(
        int(pasta.name) for pasta in Path("/proc").iterdir()
        if pasta.name.isdigit() and int(pasta.name) != os.getpid()
        and _e_bandeja_da_sessao(pasta, sessao))


def fechar_as_bandejas(pids: list[int], prazo: float) -> list[int]:
    """SIGTERM a cada uma e uma espera só, sem SIGKILL. Devolve as que ficaram de pé.

    A espera é pelo `pidfd`, que só acende com o último fio do processo fora: a vez solta com
    ele, e o fio principal que sai antes dos outros (o `Z` do `/proc`) ainda a segura."""
    abertas: dict[int, int] = {}
    espera = select.poll()
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            fd = os.pidfd_open(pid)
            abertas[fd] = pid
            espera.register(fd, select.POLLIN)
            signal.pidfd_send_signal(fd, signal.SIGTERM)
    fim = time.monotonic() + prazo
    try:
        while abertas and (resta := fim - time.monotonic()) > 0:
            for fd, _evento in espera.poll(resta * 1000):
                espera.unregister(fd)
                os.close(fd)
                del abertas[fd]
    finally:
        for fd in abertas:
            os.close(fd)
    return sorted(abertas.values())


def _linha_da_bandeja() -> list[str]:
    """O `Exec=` do autostart, que é o jeito como a sessão a sobe; sem ele, o módulo."""
    try:
        texto = caminho_do_autostart().read_text(encoding="utf-8")
    except OSError:
        texto = ""
    achado = re.search(r"^Exec=(.+)$", texto, re.M)
    if achado:
        argv = shlex.split(achado.group(1))
        if argv and Path(argv[0]).is_file():
            return argv
    return [sys.executable, "-m", "hefesto_dualsense4unix.cli.app", "tray"]


def garantir_a_bandeja(abrir: Callable[..., Any] | None = None) -> bool:
    """Sobe a bandeja, fora da unidade de quem chama, se a escolha está ligada e nenhuma está viva.

    Pelo `fora_do_servico`, como a janela da recarga: de dentro de uma unidade que termina, um
    filho por `Popen` morre com a unidade. Diz se subiu."""
    if not bandeja_ligada() or bandeja_viva() is not None:
        return False
    from hefesto_dualsense4unix.integrations import fora_do_servico

    try:
        (abrir or fora_do_servico.abrir)(
            _linha_da_bandeja(), env=dict(os.environ), aplicativo="bandeja")
    except OSError as erro:
        console.print(f"[yellow]não consegui subir a bandeja:[/] {erro}")
        return False
    return True


def _o_autostart_de_fabrica() -> str:
    from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

    app_id = identidade.atual().app_id
    fonte = encontrar_arquivo_do_repo(f"packaging/{app_id}-tray.desktop")
    if fonte is None:
        raise RuntimeError(
            f"Não achei o modelo do ícone na bandeja nesta instalação; "
            f"{como_atualizar_esta_instalacao()}.")
    raiz = fonte.parent.parent
    return fonte.read_text(encoding="utf-8").replace("@RAIZ@", str(raiz))


def escolher_a_bandeja(ligada: bool) -> None:
    """O interruptor «Ícone na bandeja»: grava a escolha no autostart e faz valer agora."""
    alvo = caminho_do_autostart()
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        texto = _o_autostart_de_fabrica()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(_escolha_no_texto(texto, ligada), encoding="utf-8")
    if ligada:
        garantir_a_bandeja()
        return
    fechar_as_bandejas(bandejas_da_sessao(), 0)


def argv_do_ato(ato: str) -> list[str]:
    """A linha que roda ``ato`` (``abrir``, ``reiniciar``, ``parar``) noutro processo."""
    return [sys.executable, "-m", __name__, ato]


def main(argv: list[str] | None = None) -> int:
    """``python -m …atos_da_bandeja abrir|reiniciar|parar`` — o gesto do controle."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        console.print("uso: atos_da_bandeja abrir|reiniciar|parar")
        return 2
    ato = args[0]
    if ato == "abrir":
        abrir_o_painel()
        return 0
    verbo = VERBOS.get(ato)
    if verbo is None:
        console.print(f"ato desconhecido: {ato}")
        return 2
    return 0 if mexer_no_servico(verbo) else 1


__all__ = [
    "LANCADOR_DO_PAINEL",
    "abrir_o_painel",
    "argv_do_ato",
    "bandeja_desligada_pela_escolha",
    "bandeja_ligada",
    "bandeja_viva",
    "bandejas_da_sessao",
    "escolher_a_bandeja",
    "fechar_as_bandejas",
    "garantir_a_bandeja",
    "mexer_no_servico",
    "repor_o_lancador",
    "soltar_a_vez",
    "tomar_a_vez",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
