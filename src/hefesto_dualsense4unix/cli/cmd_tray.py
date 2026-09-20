"""Subcomando `hefesto-dualsense4unix tray` — o ícone de bandeja do produto.

**ELE PASSOU A SUBIR O `AppTray` EM 19/09/2026** (`TRAY-ORFAO-01`), e a troca é
a resposta à queixa dela: *"o tray sumiu, não o portamos"*.

## O QUE MUDOU, e por que o outro não servia

Até aqui este comando subia o `integrations.tray.TrayController`, que é
**estritamente mais pobre** que o `app.tray.AppTray`:

| | `TrayController` (saiu) | `AppTray` (entrou) |
| --- | --- | --- |
| clique no ícone | abre a **TUI** no terminal | abre o **painel** — a interface que ela usa |
| perfis | lista de nomes, sem marca do ativo | submenu com o ativo marcado, e troca por clique |
| estado | uma linha remontada aqui | `N controles`, bateria e perfil, do dono |
| atualização | thread própria a cada 2 s | `GLib.timeout_add_seconds` interno |
| COSMIC | cria o indicador na hora | **espera o watcher aparecer** — o
  `cosmic-applet-status-area` registra o `org.kde.StatusNotifierWatcher` alguns
  ms depois do login, e quem cria antes perde a primeira fase |

O `AppTray` era **órfão** desde 06/09, quando a janela GTK saiu do disco
(`D-0609-GTK-LEVA-INTEIRA`) levando junto o único chamador dele
(`app/app.py:1794`). O censo de 19/09 o encontrou com zero chamadores de
produção — e a cura não é arquivá-lo, é **dar-lhe o dono que faltava**.

## O FATO QUE CAIU, e ele é do `CLAUDE.md`

Estava escrito que em Pop!_OS COSMIC *"o `org.kde.StatusNotifierWatcher` D-Bus
que o libayatana usa não existe, então o tray clássico fica oculto"* — foi essa
premissa que fez a janela compacta nascer como surrogate. **Medido em
19/09/2026, na sessão dela:**

```
org.kde.StatusNotifierWatcher              PID 4212  cosmic-applet-s
com.system76.CosmicStatusNotifierWatcher   PID 4212  cosmic-applet-s
```

O watcher existe. O COSMIC passou a trazê-lo, e o tray clássico funciona.

## A THREAD DE `refresh` SUMIU, e isso é a metade que barateia

O `TrayController` não se atualizava sozinho, então este arquivo mantinha uma
thread chamando `asyncio.run` a cada 2 s. O `AppTray` tem `_tick_refresh`
próprio no laço do GTK, e as chamadas de IPC saem dele pelos callbacks abaixo —
um lugar só, no fio do GTK, sem `Event` para desarmar no fim.
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

console = Console()

#: O LANÇADOR QUE O `install.sh` ESCREVE, e é o mesmo que o atalho do menu
#: dela chama. Apontar para o `interface.sh` da árvore seria amarrar o tray a
#: um caminho de desenvolvimento; apontar para o binário instalado é o que faz
#: o «Abrir painel» funcionar em qualquer computador.
LANCADOR_DO_PAINEL = "hefesto-dualsense4unix-gui"


def _chamar(metodo: str, argumentos: dict[str, Any] | None = None) -> Any:
    """Uma chamada de IPC ao daemon, com o silêncio certo quando ele não está.

    **O SILÊNCIO É `None`, E NÃO UMA EXCEÇÃO:** estes callbacks rodam dentro do
    laço do GTK, e uma exceção que suba dali derruba o menu no meio do clique
    dela. O `AppTray` já sabe tratar `None` — é o que ele recebe quando o
    daemon está parado.
    """
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _ir() -> Any:
        async with IpcClient.connect() as cliente:
            return await cliente.call(metodo, argumentos or {})

    try:
        return asyncio.run(_ir())
    except (FileNotFoundError, ConnectionError, IpcError, OSError, RuntimeError):
        return None


def _abrir_o_painel() -> None:
    """O «Abrir painel» — a diferença que mais pesa entre os dois trays.

    `setsid` E `start_new_session` PORQUE O TRAY PODE MORRER DEPOIS: sem
    desligar a sessão de processos, fechar o tray fecharia a janela que ele
    abriu. É o mesmo desenho do lançador que o `install.sh` escreve.
    """
    try:
        # O LANÇADOR É NOSSO e não recebe argumento de fora — nada a escapar.
        subprocess.Popen(
            [LANCADOR_DO_PAINEL],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # BG-INSTALL-01 (20/09/2026): esta frase nasceu com o tray, em
        # 19/09, escrita de dentro de um checkout — e cravava o instalador.
        # Em cinco dos seis formatos deste produto (`.deb`, `.rpm`, Arch, Nix
        # e o pip) o arquivo não está na máquina de quem está lendo, e o
        # conselho vira impossível. Quem sabe o gesto desta instalação é o
        # `utils/repo_files`, que responde pelo formato REAL dela.
        console.print(
            f"[yellow]não achei `{LANCADOR_DO_PAINEL}` no PATH[/] — "
            f"o lançador do painel não veio nesta instalação; "
            f"{como_atualizar_esta_instalacao()}.")


def _listar_perfis() -> list[dict[str, Any]]:
    resposta = _chamar("profile.list")
    if not isinstance(resposta, dict):
        return []
    perfis = resposta.get("profiles")
    return perfis if isinstance(perfis, list) else []


def _trocar_de_perfil(nome: str) -> bool:
    """Troca pelo IPC; se o daemon não responder, tenta pela CLI.

    A RESERVA PELA CLI É A DO ARQUIVO ANTIGO, e ela fica: o caminho da CLI
    sobe o daemon quando ele está parado, o que é exatamente o caso em que o
    IPC falha.
    """
    if _chamar("profile.switch", {"name": nome}) is not None:
        return True
    try:
        # O NOME VEM DA LISTA DO PRÓPRIO DAEMON, não de entrada livre.
        subprocess.Popen(
            ["hefesto-dualsense4unix", "profile", "activate", nome],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return False
    return True


def _estado() -> dict[str, Any] | None:
    """O snapshot que vira `N controles · Bat N% · Perfil` no menu.

    `daemon.state_full` E NÃO `daemon.status`: o `status` não traz a lista de
    controles, e o `AppTray._controllers_suffix_from_state` a lê para dizer
    quantos estão na mesa. Pedir o menor dos dois faria o tray mostrar sempre
    «1 controle».
    """
    resposta = _chamar("daemon.state_full")
    return resposta if isinstance(resposta, dict) else None


def tray_cmd() -> None:
    """Sobe o ícone de bandeja e fica em primeiro plano até `Sair`."""
    from hefesto_dualsense4unix.app.tray import AppTray
    from hefesto_dualsense4unix.integrations.tray import probe_gi_availability

    ok, motivo = probe_gi_availability()
    if not ok:
        console.print(f"[yellow]Tray indisponível:[/] {motivo}")
        raise typer.Exit(code=2)

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    bandeja = AppTray(
        on_show_window=_abrir_o_painel,
        on_quit=Gtk.main_quit,
        on_list_profiles=_listar_perfis,
        on_switch_profile=_trocar_de_perfil,
        on_state=_estado,
    )
    if not bandeja.start():
        console.print(
            "[red]não consegui criar o ícone de bandeja[/] — "
            "não há quem hospede o `org.kde.StatusNotifierWatcher` nesta sessão")
        raise typer.Exit(code=3)

    console.print("[green]tray ativo[/] — clique no ícone para abrir o menu.")
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    finally:
        bandeja.stop()


__all__ = ["tray_cmd"]
