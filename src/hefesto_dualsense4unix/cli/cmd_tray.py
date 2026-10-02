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

## O FATO QUE CAIU

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

# OS ATOS DA BANDEJA MORAM EM `app/actions/atos_da_bandeja.py` desde 01/10/2026
# (OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01): o gesto do controle chama os
# mesmos três, e um dono só é o que impede a quarta cópia de divergir. Os
# nomes de cá continuam respondendo — são os MESMOS objetos (`is`).
from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    LANCADOR_DO_PAINEL as LANCADOR_DO_PAINEL,
)
from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    abrir_o_painel as _abrir_o_painel,
)
from hefesto_dualsense4unix.app.actions.atos_da_bandeja import (
    mexer_no_servico as _servico,
)

console = Console()


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


# ---------------------------------------------------------------------------
# TRAY-A-LISTINHA-DELA-01 (21/09/2026) — os quatro atos da bandeja
#
# NENHUMA REGRA NOVA MORA AQUI, e é o contrato deste arquivo: cada função
# abaixo pergunta ao DONO do ato e despacha o que ele responder. O tray é a
# quarta superfície a chamar os mesmos donos (a janela GTK saiu, ficam a aba
# Jogar, a aba Sistema e a CLI) — e a lição que esta casa pagou três vezes é
# que a quarta cópia é a que diverge.
# ---------------------------------------------------------------------------
def _definir_o_modo(ligado: bool) -> bool:
    """O interruptor da aba Jogar, pelo mesmo plano de IPC que ela despacha.

    **O PLANO É DO DONO** (`painel.plano_do_modo` -> `plan_mode_transition`), e
    a ORDEM das chamadas é a entrega: invertidas, *"o vpad nasceria com o
    físico ainda grabado pelo jogo"*. Por isso o laço despacha na ordem em que
    o plano vem, e nunca reordena.

    **LIGAR SOBE O SERVIÇO ANTES**, e vem antes do plano porque sem o daemon de
    pé não há a quem mandar — decisão dela de 03/09/2026: *"Adiciona essa
    função extra quando clicar em ligar"*. A ordem inversa recusaria o clique
    exatamente no caso que ela pediu que passasse a funcionar.
    """
    from hefesto_dualsense4unix.app.actions.jogar.painel import plano_do_modo
    from hefesto_dualsense4unix.app.actions.mode_transition import (
        MODE_GAMEPAD,
        MODE_NATIVE,
    )

    if ligado:
        _servico("start")
    plano = plano_do_modo(MODE_GAMEPAD if ligado else MODE_NATIVE)
    if plano is None:
        return False
    pegou = True
    for metodo, params in plano:
        if _chamar(metodo, params) is None:
            pegou = False
    return pegou


def _reconectar_os_controles() -> bool:
    """O «Reconectar controles» da aba Jogar — os MESMOS dois passos.

    `coop.sync` reconcilia o co-op e `identity.renumber` devolve os números de
    jogador. Ele NÃO manda um `Connect` pelo rádio: reconectar o aparelho é o
    botão PS dela, e isso é decisão de produto registrada no gesto da aba.
    """
    primeiro = _chamar("coop.sync") is not None
    segundo = _chamar("identity.renumber") is not None
    return primeiro and segundo


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
        on_set_modo=_definir_o_modo,
        on_reconectar=_reconectar_os_controles,
        on_servico=_servico,
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
