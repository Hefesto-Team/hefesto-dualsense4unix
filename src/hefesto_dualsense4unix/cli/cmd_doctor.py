"""Subcomando `hefesto-dualsense4unix doctor` — health-check no CLI.

Reusa `scripts/doctor.sh` (infra: daemon, udev, uinput, applet COSMIC, WirePlumber,
controle) e adiciona checks "do daemon" via IPC (responde? pausado? perfis
listáveis?), generalizando a sacada do doctor para as features que só o daemon
conhece em runtime. FEAT-DOCTOR-CLI-AND-CHECKS-01.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.utils.repo_files import (
    bases_de_instalacao,
    encontrar_arquivo_do_repo,
)

console = Console()


def _find_doctor_sh() -> Path | None:
    """Localiza `scripts/doctor.sh` na instalação que está rodando.

    BG-05 (25/08/2026): a busca era uma cópia LOCAL que conhecia três layouts
    — checkout, `/usr/share` e `/usr/local/share`. O Flatpak não é nenhum dos
    três, e a cópia gêmea em `app/actions/daemon_actions.py` já havia ganhado
    `/app/share` na T-02(b) do mesmo dia: duas respostas para a mesma pergunta,
    divergindo em silêncio. A resposta agora tem dono único, em
    `utils/repo_files.py`.
    """
    return encontrar_arquivo_do_repo("scripts/doctor.sh")


def _avisar_ausente(relpath: str, consequencia: str) -> None:
    """Diz que um script não veio nesta instalação — e ONDE se procurou.

    A frase antiga era "`{relpath}` não encontrado — pulado", e ela deixava
    quem lê sem saber se o arquivo não foi instalado ou se o produto procurou
    no lugar errado. Como o defeito desta frente foi exatamente o segundo
    caso, a lista dos diretórios consultados é o dado que fecha a pergunta —
    e é o próprio doctor, cujo trabalho é diagnosticar, quem a imprime.

    Só os DIRETÓRIOS-base saem na lista: o nome do arquivo já está na primeira
    linha, e repeti-lo seis vezes só faz o `rich` quebrar caminho no meio. Por
    isso também o `soft_wrap` — caminho partido ao meio não se copia nem se
    cola.
    """
    console.print(f"[yellow]{relpath} não veio nesta instalação — {consequencia}[/yellow]")
    console.print("[dim]       procurei o share do Hefesto em:[/dim]")
    for base in bases_de_instalacao():
        console.print(f"[dim]         {base}[/dim]", soft_wrap=True, highlight=False)


async def _daemon_checks() -> list[tuple[str, str]]:
    """Checks que só o daemon conhece (via IPC). Retorna [(tag, mensagem)]."""
    rows: list[tuple[str, str]] = []
    try:
        async with IpcClient.connect() as client:
            status = await client.call("daemon.status")
            rows.append(("[ OK ]", "IPC responde (daemon.status atendido)"))
            if isinstance(status, dict) and status.get("paused"):
                rows.append(
                    ("[WARN]", "daemon PAUSADO — input suspenso ('daemon resume' p/ retomar)")
                )
            profiles = await client.call("profile.list")
            count = len(profiles.get("profiles", [])) if isinstance(profiles, dict) else 0
            if count > 0:
                rows.append(("[ OK ]", f"perfis listáveis via IPC ({count})"))
            else:
                rows.append(("[WARN]", "nenhum perfil listado pelo daemon"))
    except (FileNotFoundError, ConnectionError, IpcError):
        rows.append(("[WARN]", "daemon offline — checks de runtime pulados"))
    return rows


def _run_script(relpath: str, *args: str, confirm: str | None = None) -> int:
    """Roda um script do repo. `confirm` != None pede confirmação antes."""
    script = encontrar_arquivo_do_repo(relpath)
    if script is None:
        _avisar_ausente(relpath, "pulado")
        return 0
    if confirm is not None and not typer.confirm(confirm):
        console.print("[dim]cancelado.[/dim]")
        return 0
    return subprocess.run(["bash", str(script), *args], check=False).returncode


async def _state_full_ou_none() -> dict[str, Any] | None:
    """`daemon.state_full` via IPC; ``None`` com o daemon offline (best-effort)."""
    try:
        async with IpcClient.connect() as client:
            estado = await client.call("daemon.state_full")
            return estado if isinstance(estado, dict) else None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def _print_storm_block() -> None:
    """Diagnóstico storm (FEAT-DSX-UNIFY-01) — read-only, sem sudo."""
    from hefesto_dualsense4unix.integrations import storm_doctor

    # MESA-CHEIA-11/E3: o check de áudio conta as placas DualSense contra os
    # controles NO CABO. O denominador vem do daemon; sem daemon ele é None e o
    # check volta a responder presente/ausente, sem inventar fração.
    no_cabo = storm_doctor.controles_no_cabo(asyncio.run(_state_full_ou_none()))
    console.print("\n== anti-storm / sistema ==")
    for tag, message in storm_doctor.storm_report(controles_no_cabo=no_cabo):
        console.print(f"{tag} {message}")


def _linhas_perfis() -> tuple[list[tuple[str, str]], bool]:
    """Verificação SEMÂNTICA dos perfis. Devolve (linhas, houve_erro).

    PERFIL-NASCE-CERTO-01/E4 — o detector de armadilha que a sprint desenhou e
    ninguém escreveu. Read-only e sem daemon: lê o diretório de perfis e
    compara os perfis ENTRE SI (catch-all vencendo perfil de jogo, prioridade
    fora da faixa da janela, empates). Ver `profiles/sanidade.py`.
    """
    from hefesto_dualsense4unix.profiles import sanidade
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles

    try:
        perfis = load_all_profiles()
    except OSError as exc:
        return ([("[WARN]", f"não deu para ler os perfis: {exc}")], False)
    achados = sanidade.verificar_perfis(perfis)
    linhas = sanidade.linhas_de_relatorio(achados, total_perfis=len(perfis))
    houve_erro = any(a.gravidade == "erro" for a in achados)
    return (linhas, houve_erro)


def _print_bloco_perfis() -> bool:
    """Imprime o bloco de perfis. True quando há achado GRAVE (exit != 0)."""
    linhas, houve_erro = _linhas_perfis()
    console.print("\n== perfis (coerência entre eles) ==")
    for tag, mensagem in linhas:
        console.print(f"{tag} {mensagem}")
    return houve_erro


def doctor_cmd(
    fix: bool = False,
    quiet: bool = False,
    fix_safe: bool = False,
    perfis: bool = False,
) -> None:
    """Roda `scripts/doctor.sh` (infra) + diagnóstico storm + checks do daemon.

    FEAT-DSX-UNIFY-01:
    - `--fix-safe`: aplica só o SEGURO (sem sudo) — Steam Input OFF (se a Steam
      não estiver rodando) + drop-in do WirePlumber + cura de raiz a quente.
      Reversível/idempotente.

    O antigo `--reapply-all` (que invocava o dsx.sh) foi REMOVIDO: o dsx.sh era
    baseado na teoria de HW já refutada (I/O die / power). A cura real é o quirk
    do snd_usb_audio, instalado por padrão e aplicável por `--fix-safe`.

    PERFIL-NASCE-CERTO-01/E4:
    - `--perfis`: SÓ a coerência dos perfis entre si, sem doctor.sh, sem storm
      e sem IPC. É o caminho rápido para responder "meus perfis estão sãos?" —
      e sai com código 1 quando há achado grave, para poder virar portão.
    """
    if perfis:
        raise typer.Exit(code=1 if _print_bloco_perfis() else 0)

    rc = 0
    sh = _find_doctor_sh()
    if sh is not None:
        args = ["bash", str(sh)]
        if fix:
            args.append("--fix")
        if quiet:
            args.append("--quiet")
        rc = subprocess.run(args, check=False).returncode
    else:
        _avisar_ausente("scripts/doctor.sh", "só os checks do daemon")

    _print_storm_block()

    # PERFIL-NASCE-CERTO-01/E4: o detector também roda no doctor COMPLETO — a
    # armadilha de perfil não avisa sozinha, e quem só roda `doctor` uma vez
    # por mês precisa ouvir dela ali. Não mexe no `rc` (mesma política do bloco
    # de storm): quem quiser portão usa `doctor --perfis`.
    _print_bloco_perfis()

    console.print("\n== daemon (via IPC) ==")
    for tag, message in asyncio.run(_daemon_checks()):
        console.print(f"{tag} {message}")

    if fix_safe:
        console.print("\n== fix-safe (sem sudo) ==")
        # --apply-quiet: só edita se a Steam NÃO estiver rodando (não a fecha).
        _run_script("scripts/disable_steam_input.sh", "--apply-quiet")
        # --install: DualSense não-default, microfone preservado.
        _run_script("scripts/fix_wireplumber_default_source.sh", "--install")
        # Cura de raiz do storm a quente (sysfs) — best-effort, sem senha.
        _run_script("scripts/install_snd_quirk.sh", "--runtime")
        _print_storm_block()

    raise typer.Exit(code=rc)


__all__ = ["doctor_cmd"]
