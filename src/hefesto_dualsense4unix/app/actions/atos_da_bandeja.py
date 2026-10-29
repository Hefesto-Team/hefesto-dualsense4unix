"""Os atos da bandeja que o controle também faz: abrir o painel e o serviço.

E o dono da própria bandeja (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, S3 e S4): a escolha de ter o
ícone mora no autostart da sessão (`X-GNOME-Autostart-enabled`), a bandeja viva é o PID que ela
grava em `$XDG_RUNTIME_DIR` mais `kill -0`, e `garantir_a_bandeja` a sobe quando a escolha está
ligada e não há nenhuma viva.
"""
from __future__ import annotations

import contextlib
import os
import re
import shlex
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

console = Console()

LANCADOR_DO_PAINEL = "hefesto-dualsense4unix-gui"

VERBOS: dict[str, str] = {"reiniciar": "restart", "parar": "stop", "ativar": "start"}


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
        console.print(rl.frase_do_recibo(rl.repor()))
    except Exception as erro:
        console.print(f"[yellow]não consegui repor o lançador:[/] {erro}")


CHAVE_DO_AUTOSTART = "X-GNOME-Autostart-enabled"
_LINHA_DA_CHAVE = re.compile(rf"^{CHAVE_DO_AUTOSTART}=.*$", re.M)


def caminho_do_autostart() -> Path:
    """O `.desktop` que a sessão lê ao entrar, o mesmo que o `install.sh` escreve."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{identidade.atual().app_id}-tray.desktop"


def caminho_do_pid() -> Path:
    """Onde a bandeja viva deixa o PID dela: some com a sessão, como ela."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/{identidade.atual().app_id}-{os.getuid()}"
    return Path(base) / f"{identidade.atual().app_id}-tray.pid"


def bandeja_ligada() -> bool:
    """A escolha «Ícone na bandeja»: o autostart existe e não diz `false`."""
    try:
        texto = caminho_do_autostart().read_text(encoding="utf-8")
    except OSError:
        return False
    achado = _LINHA_DA_CHAVE.search(texto)
    return not (achado and achado.group(0).split("=", 1)[1].strip().lower() == "false")


def _pid_anotado() -> int:
    """O PID que a bandeja anotou ao subir, ou 0 sem anotação legível."""
    alvo = caminho_do_pid()
    texto = alvo.read_text(encoding="ascii").strip() if alvo.is_file() else ""
    return int(texto) if texto.isdigit() else 0


def bandeja_viva() -> int | None:
    """O PID da bandeja que está de pé, ou `None`. O PID reciclado por outro processo não conta."""
    pid = _pid_anotado()
    linha = Path(f"/proc/{pid}/cmdline")
    argv = linha.read_bytes().split(b"\0") if pid > 0 and linha.is_file() else []
    return pid if {b"tray", b"--tray"} & set(argv) else None


def anotar_a_bandeja_viva() -> None:
    """Chamado pela bandeja ao subir: o PID dela vira o endereço que os outros conferem."""
    alvo = caminho_do_pid()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(f"{os.getpid()}\n", encoding="ascii")


def esquecer_a_bandeja() -> None:
    """Chamado pela bandeja ao sair, só se o PID anotado ainda for o dela."""
    if _pid_anotado() == os.getpid():
        caminho_do_pid().unlink(missing_ok=True)


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
    filho por `Popen` morre com ela. Diz se subiu."""
    if not bandeja_ligada() or bandeja_viva() is not None:
        return False
    from hefesto_dualsense4unix.integrations import fora_do_servico

    try:
        abertura = (abrir or fora_do_servico.abrir)(
            _linha_da_bandeja(), env=dict(os.environ), aplicativo="bandeja")
    except OSError as erro:
        console.print(f"[yellow]não consegui subir a bandeja:[/] {erro}")
        return False
    filho = getattr(abertura, "processo", None)
    if filho is not None:
        with contextlib.suppress(OSError):
            caminho_do_pid().parent.mkdir(parents=True, exist_ok=True)
            caminho_do_pid().write_text(f"{filho.pid}\n", encoding="ascii")
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
    linha = f"{CHAVE_DO_AUTOSTART}={'true' if ligada else 'false'}"
    texto = (_LINHA_DA_CHAVE.sub(linha, texto) if _LINHA_DA_CHAVE.search(texto)
             else texto.rstrip("\n") + f"\n{linha}\n")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")
    if ligada:
        garantir_a_bandeja()
        return
    pid = bandeja_viva()
    if pid is not None:
        os.kill(pid, signal.SIGTERM)


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
    "anotar_a_bandeja_viva",
    "argv_do_ato",
    "bandeja_ligada",
    "bandeja_viva",
    "escolher_a_bandeja",
    "esquecer_a_bandeja",
    "garantir_a_bandeja",
    "mexer_no_servico",
    "repor_o_lancador",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
