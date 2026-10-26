"""Subcomando `hefesto-dualsense4unix doctor` — health-check no CLI."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.utils.repo_files import (
    bases_de_instalacao,
    encontrar_arquivo_do_repo,
)

console = Console()

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


def _linha_do_nascimento(counters: Any) -> tuple[str, str] | None:
    """Os pads que nasceram fora do tique e a média do nascimento, dos contadores do store.

    O `vpad.nascimento_ms_total` é a SOMA dos nascimentos, não a última medida.
    ``None`` enquanto nenhum pad nasceu pelo fio.
    """
    if not isinstance(counters, dict):
        return None
    nascidos = counters.get("vpad.nascimentos")
    total = counters.get("vpad.nascimento_ms_total", 0)
    if not isinstance(nascidos, int) or isinstance(nascidos, bool) or nascidos <= 0:
        return None
    if not isinstance(total, int) or isinstance(total, bool):
        return None
    return (
        "[ OK ]",
        f"nascimento do pad fora do tique: {nascidos}, média {formata_pt_br(total / nascidos)} ms",
    )


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
        return formata_pt_br(quanto / 1000)

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


def _linha_da_mascara_pro(estado: Any) -> tuple[str, str] | None:
    """O que a máscara Pro Controller entrega, quando algum controle a mostra ao jogo agora."""
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        LINHA_DA_PRO_NO_UINPUT,
        o_jogo_ve_a_pro,
    )

    emulacao = estado.get("gamepad_emulation") if isinstance(estado, dict) else None
    if not isinstance(emulacao, dict) or not emulacao.get("enabled"):
        return None
    por_aparelho = emulacao.get("por_aparelho")
    if isinstance(por_aparelho, dict) and por_aparelho:
        mascaras = list(por_aparelho.values())
    else:
        mascaras = [emulacao.get("flavor")]
    if not o_jogo_ve_a_pro(emulacao.get("caminho"), mascaras):
        return None
    return ("[INFO]", LINHA_DA_PRO_NO_UINPUT)


_ROTULO_DO_TRANSPORTE = {"usb": "cabo", "bt": "rádio"}


def _linhas_do_firmware(controles: Any) -> list[tuple[str, str]]:
    """A versão do firmware de cada controle, do ``controller.list`` do daemon.

    A-VERSAO-DO-FIRMWARE-APARECE-NO-DOCTOR-E-NUNCA-SE-ATUALIZA-DAQUI-01. O daemon lê o
    ``update_version`` (feature 0x20) quando o controle conecta, e a versão chega aqui em
    ``firmware``; o doctor só LÊ o que ele disse, nunca escreve nada no controle. Abaixo do
    ``LIMITE_DA_VIBRACAO_V2`` o SDL e o jogo tratam o controle de outro jeito, e o defeito de um
    firmware velho parece defeito do Hefesto: o aviso diz onde se atualiza. O Edge é sempre v2 e
    tem outra numeração: ele mostra a versão e nunca avisa. Versão não lida é ``[INFO]``.
    """
    if not isinstance(controles, list):
        return []
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        LIMITE_DA_VIBRACAO_V2,
        fala_a_vibracao_v2,
    )

    linhas: list[tuple[str, str]] = []
    for posicao, controle in enumerate(controles):
        if not isinstance(controle, dict) or not controle.get("connected"):
            continue
        numero = controle.get("numero")
        if not isinstance(numero, int) or isinstance(numero, bool):
            numero = posicao + 1
        via = _ROTULO_DO_TRANSPORTE.get(str(controle.get("transport")))
        nome = f"controle {numero}" + (f" ({via})" if via else "")
        versao = controle.get("firmware")
        if not isinstance(versao, int) or isinstance(versao, bool):
            linhas.append(("[INFO]", f"{nome}: a versão do firmware ainda não foi lida"))
        elif not fala_a_vibracao_v2(versao, edge=bool(controle.get("edge"))):
            linhas.append((
                "[WARN]",
                f"{nome}: firmware 0x{versao:04x}, anterior ao 0x{LIMITE_DA_VIBRACAO_V2:04x}: o "
                "controle vibra no modo antigo e o SDL o trata de outro jeito. Atualize pelo PS5 "
                "ou pelo aplicativo da Sony no Windows; o Hefesto nunca atualiza firmware",
            ))
        else:
            linhas.append(("[ OK ]", f"{nome}: firmware 0x{versao:04x}"))
    return linhas


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
            linha_do_nascimento = _linha_do_nascimento(
                estado.get("counters") if isinstance(estado, dict) else None
            )
            if linha_do_nascimento is not None:
                rows.append(linha_do_nascimento)
            linha_da_pro = _linha_da_mascara_pro(estado)
            if linha_da_pro is not None:
                rows.append(linha_da_pro)
            try:
                controles = await client.call("controller.list")
            except IpcError:
                controles = None
            rows.extend(
                _linhas_do_firmware(
                    controles.get("controllers") if isinstance(controles, dict) else None
                )
            )
    except IpcError as exc:
        from hefesto_dualsense4unix.app.ipc_bridge import prazo_vencido

        if prazo_vencido(exc):
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


def _print_bloco_proton_fixado() -> int:
    """O Proton fixado e o que o recibo diz de cada versão. Devolve a gravidade do bloco."""
    from hefesto_dualsense4unix.integrations import qualificar_proton

    console.print("\n== Proton fixado (o recibo de cada versão) ==")
    linhas = qualificar_proton.linhas_do_doctor_desta_maquina()
    for tag, mensagem in linhas:
        console.print(f"{tag} {mensagem}", soft_wrap=True, highlight=False)
    return _gravidade_das_linhas(linhas)


def _print_bloco_entrada() -> int:
    """A permissão de ler o teclado e o pedal do «Usar como botões de». Devolve a gravidade."""
    from hefesto_dualsense4unix.core.system_check import permissao_de_ler_a_entrada

    console.print("\n== teclado e pedal (o acionador da aba Conexões) ==")
    linhas = [permissao_de_ler_a_entrada()]
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
        rc = _GRAVIDADE_FAIL if subprocess.run(args, check=False).returncode else 0
    else:
        _avisar_ausente("scripts/doctor.sh", "só os checks do daemon")

    rc = max(rc, _print_storm_block())

    if _print_bloco_perfis():
        rc = _GRAVIDADE_FAIL

    rc = max(rc, _print_bloco_contratos())

    rc = max(rc, _print_bloco_proton_fixado())

    rc = max(rc, _print_bloco_entrada())

    console.print("\n== daemon (via IPC) ==")
    linhas_do_daemon = asyncio.run(_daemon_checks())
    for tag, message in linhas_do_daemon:
        console.print(f"{tag} {message}")
    rc = max(rc, _gravidade_das_linhas(linhas_do_daemon))

    if fix_safe:
        console.print("\n== fix-safe (sem sudo) ==")
        _run_script("scripts/disable_steam_input.sh", "--apply-quiet")
        _run_script("scripts/fix_wireplumber_default_source.sh", "--install")
        _run_script("scripts/install_snd_quirk.sh", "--runtime")
        rc = max(rc, _print_storm_block())

    raise typer.Exit(code=rc)


__all__ = ["doctor_cmd"]
