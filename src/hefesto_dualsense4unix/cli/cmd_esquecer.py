"""``hefesto-dualsense4unix esquecer-controles`` — a primeira vez, de novo.

ESQUECER-OS-CONTROLES-01 (25/09/2026). O produto passa a se comportar como numa
máquina que nunca viu um controle: a memória dos controles sai para uma pasta
datada (movida, nunca apagada) e volta com ``--restaurar``, byte a byte.

O QUE É «A MEMÓRIA DOS CONTROLES» não mora aqui: é o inventário de
``utils/memoria_dos_controles.py``, e este arquivo só o executa. O daemon é
parado e religado pelo dono de sempre (``daemon/service_install.py``); um
daemon rodando fora do systemd faz o comando RECUSAR, porque ele regravaria o
que está sendo movido.
"""
from __future__ import annotations

import contextlib
import subprocess

import typer

from hefesto_dualsense4unix.utils import memoria_dos_controles as memoria


class SistemaDoProduto(memoria.Sistema):
    """O :class:`memoria.Sistema`, com o daemon pelo dono de sempre."""

    def daemon_ativo(self) -> bool:
        return not self.ensaio and self._pid_vivo() is not None

    def parar_daemon(self) -> None:
        from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

        if self.ensaio:
            return

        # Sem systemd de usuário a parada falha calada: a conferência abaixo decide.
        with contextlib.suppress(OSError, RuntimeError, subprocess.SubprocessError):
            ServiceInstaller().stop()
        pid = self._pid_vivo()
        if pid is not None:
            raise memoria.RecusaError(
                f"o daemon continua rodando (pid {pid}) fora do systemd — pare-o "
                "(Ctrl+C no terminal dele) e repita"
            )

    def subir_daemon(self) -> None:
        from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

        if self.ensaio:
            return

        try:
            ServiceInstaller().start()
        except (OSError, RuntimeError, subprocess.SubprocessError):
            typer.echo("não consegui subir o daemon pelo systemd — suba-o como de costume")

    @staticmethod
    def _pid_vivo() -> int | None:
        from hefesto_dualsense4unix.daemon.main import single_instance_name
        from hefesto_dualsense4unix.utils import single_instance

        caminho = single_instance._pid_file(single_instance_name())
        pid = single_instance._read_existing_pid(caminho)
        if pid is None or not single_instance.is_alive(pid):
            return None
        if not single_instance._is_hefesto_dualsense4unix_process(pid):
            return None
        return pid


def esquecer_cmd(*, restaurar: bool, pasta: str | None, seco: bool) -> None:
    """Esquece (ou devolve) a memória dos controles."""
    raizes = memoria.Raizes.do_ambiente()
    sistema = SistemaDoProduto()
    try:
        if restaurar:
            relato = memoria.devolver(raizes, sistema, pasta, seco=seco,
                                      alcance=memoria.CONTROLES)
        else:
            if pasta:
                raise memoria.RecusaError(
                    "a pasta só vale com --restaurar; para esquecer, rode sem ela"
                )
            relato = memoria.guardar(raizes, memoria.CONTROLES, sistema, seco=seco)
    except memoria.RecusaError as erro:
        typer.echo(f"recusado: {erro}", err=True)
        raise typer.Exit(code=2) from erro
    for linha in relato.linhas:
        typer.echo(linha)
    if not seco and not restaurar and relato.pasta is not None:
        typer.echo("para devolver: hefesto-dualsense4unix esquecer-controles --restaurar")
