"""Os atos da bandeja que o controle também faz: abrir o painel e o serviço."""
from __future__ import annotations

import subprocess
import sys

from rich.console import Console

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

console = Console()

LANCADOR_DO_PAINEL = "hefesto-dualsense4unix-gui"

VERBOS: dict[str, str] = {"reiniciar": "restart", "parar": "stop", "ativar": "start"}


def abrir_o_painel() -> None:
    """O «Abrir painel» — a diferença que mais pesa entre os dois trays."""
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
    return pegou


def repor_o_lancador() -> None:
    """O «Reiniciar» da bandeja repõe o lançador, como o da aba Sistema."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    try:
        console.print(rl.frase_do_recibo(rl.repor()))
    except Exception as erro:
        console.print(f"[yellow]não consegui repor o lançador:[/] {erro}")


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
    "mexer_no_servico",
    "repor_o_lancador",
]


if __name__ == "__main__":  # pragma: no cover - o gesto do controle
    raise SystemExit(main())
