"""Subcomando `hefesto-dualsense4unix doctor` — health-check no CLI."""
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

#: O rc do `doctor` é o pior veredito: 0 tudo OK, 1 algum aviso, 2 alguma falha.
_GRAVIDADE_WARN = 1
_GRAVIDADE_FAIL = 2


def _gravidade_das_linhas(linhas: list[tuple[str, str]]) -> int:
    """A pior gravidade entre as linhas ``(tag, mensagem)`` de um bloco."""
    pior = 0
    for tag, _mensagem in linhas:
        marca = tag.strip().strip("[]").strip().upper()
        if marca == "FAIL":
            pior = max(pior, _GRAVIDADE_FAIL)
        elif marca == "WARN":
            pior = max(pior, _GRAVIDADE_WARN)
    return pior


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
    """Diz que um script não veio nesta instalação — e ONDE se procurou."""
    console.print(f"[yellow]{relpath} não veio nesta instalação — {consequencia}[/yellow]")
    console.print("[dim]       procurei o share do Hefesto em:[/dim]")
    for base in bases_de_instalacao():
        console.print(f"[dim]         {base}[/dim]", soft_wrap=True, highlight=False)


_PREFIXO_DO_RELOGIO = "poll.tique.relogio."


def _linha_do_tique(counters: Any) -> tuple[str, str] | None:
    """O tique do daemon em uma linha, dos contadores do ``state_full``.

    O `_poll_loop` mede cada tique: quantos passaram do orçamento de 16,7 ms, o
    p99 e o pior da última janela, e o relógio lento que estava no pior tique.
    ``None`` quando o daemon ainda não mediu (ou não conhece a medida). Antes de a
    primeira janela fechar, o p99 e o pior ainda não existem, e a linha fica só
    com a contagem: medida que não há não sai como zero.
    """
    if not isinstance(counters, dict):
        return None
    medidos = counters.get("poll.tique.medidos")
    if not isinstance(medidos, int) or isinstance(medidos, bool) or medidos <= 0:
        return None

    def ms(chave: str) -> str:
        valor = counters.get(chave)
        quanto = valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
        return f"{quanto / 1000:.1f}".replace(".", ",")

    estouros = counters.get("poll.tique.estouros", 0)
    contagem = f"tique do laço: {estouros} de {medidos} acima de 16,7 ms"
    if "poll.tique.p99_us" not in counters:
        return ("[ OK ]", contagem)
    relogios = {
        chave[len(_PREFIXO_DO_RELOGIO):]: valor
        for chave, valor in counters.items()
        if chave.startswith(_PREFIXO_DO_RELOGIO)
        and isinstance(valor, int)
        and not isinstance(valor, bool)
        and valor > 0
    }
    onde = ""
    if relogios:
        pior = max(relogios, key=lambda nome: relogios[nome])
        onde = f", o pior com «{pior.replace('_', ' ')}»"
    return (
        "[ OK ]",
        f"{contagem}; p99 {ms('poll.tique.p99_us')} ms, pior {ms('poll.tique.pior_us')} ms{onde}",
    )


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
            lista = profiles.get("profiles") if isinstance(profiles, dict) else None
            if isinstance(lista, list):
                rows.append(("[ OK ]", f"perfis listáveis via IPC ({len(lista)})"))
            else:
                rows.append(("[WARN]", "o daemon não respondeu a lista de perfis"))
            try:
                estado = await client.call("daemon.state_full")
            except IpcError:
                estado = None
            linha_do_tique = _linha_do_tique(
                estado.get("counters") if isinstance(estado, dict) else None
            )
            if linha_do_tique is not None:
                rows.append(linha_do_tique)
    except IpcError as exc:
        from hefesto_dualsense4unix.app.ipc_bridge import prazo_vencido

        if prazo_vencido(exc):
            # Atende a conexão e não responde: parado ou travado. Não é «offline».
            rows.append(("[FAIL]", f"{exc.message} — o serviço está parado ou travado"))
        else:
            rows.append(("[WARN]", "daemon offline — checks de runtime pulados"))
    except (FileNotFoundError, ConnectionError):
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


def _print_storm_block() -> int:
    """Diagnóstico storm (FEAT-DSX-UNIFY-01) — read-only, sem sudo. Devolve a gravidade."""
    from hefesto_dualsense4unix.integrations import storm_doctor

    # MESA-CHEIA-11/E3: o check de áudio conta as placas DualSense contra os
    no_cabo = storm_doctor.controles_no_cabo(asyncio.run(_state_full_ou_none()))
    console.print("\n== anti-storm / sistema ==")
    linhas = storm_doctor.storm_report(controles_no_cabo=no_cabo)
    for tag, message in linhas:
        console.print(f"{tag} {message}")
    return _gravidade_das_linhas(linhas)


def _linhas_perfis() -> tuple[list[tuple[str, str]], bool]:
    """Verificação SEMÂNTICA dos perfis. Devolve (linhas, houve_erro)."""
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


def _print_bloco_contratos() -> int:
    """Os contratos de fora (BlueZ, PipeWire, systemd, kernel, Steam, Proton, COSMIC).

    Devolve a gravidade do bloco.
    """
    from hefesto_dualsense4unix.integrations import contratos_de_fora

    console.print("\n== contratos de fora (o que o Hefesto assume dos outros) ==")
    linhas = contratos_de_fora.linhas_do_doctor()
    for tag, mensagem in linhas:
        console.print(f"{tag} {mensagem}", soft_wrap=True, highlight=False)
    return _gravidade_das_linhas(linhas)


def doctor_cmd(
    fix: bool = False,
    quiet: bool = False,
    fix_safe: bool = False,
    perfis: bool = False,
) -> None:
    """Roda `scripts/doctor.sh` (infra) + diagnóstico storm + checks do daemon."""
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
        # O doctor.sh sai com rc != 0 só quando reprova (FAIL); aviso não o muda.
        rc = _GRAVIDADE_FAIL if subprocess.run(args, check=False).returncode else 0
    else:
        _avisar_ausente("scripts/doctor.sh", "só os checks do daemon")

    rc = max(rc, _print_storm_block())

    # PERFIL-NASCE-CERTO-01/E4: o detector também roda no doctor COMPLETO — a
    if _print_bloco_perfis():
        rc = _GRAVIDADE_FAIL

    rc = max(rc, _print_bloco_contratos())

    console.print("\n== daemon (via IPC) ==")
    linhas_do_daemon = asyncio.run(_daemon_checks())
    for tag, message in linhas_do_daemon:
        console.print(f"{tag} {message}")
    rc = max(rc, _gravidade_das_linhas(linhas_do_daemon))

    if fix_safe:
        console.print("\n== fix-safe (sem sudo) ==")
        _run_script("scripts/disable_steam_input.sh", "--apply-quiet")
        # --install: DualSense não-default, microfone preservado.
        _run_script("scripts/fix_wireplumber_default_source.sh", "--install")
        _run_script("scripts/install_snd_quirk.sh", "--runtime")
        rc = max(rc, _print_storm_block())

    raise typer.Exit(code=rc)


__all__ = ["doctor_cmd"]
