"""Subcomando `hefesto-dualsense4unix profile ...`.

Opera diretamente no diretório de perfis (XDG) sem falar com o daemon
em execução. Para "ativar" via daemon rodando, W4.2 adicionará uma
implementação que envia `profile.switch` via IPC; por enquanto, o
comando `activate` grava a marca de perfil ativo em um arquivo-estado
local e, se houver hardware/daemon acessível, aplica direto.

FEAT-CLI-PARITY-01: adiciona `apply --file <json>` (carrega JSON, valida
via pydantic, salva e ativa via IPC/hardware) e `save <nome>
--from-active` (clona o perfil marcado como ativo para um novo nome).
"""
from __future__ import annotations

import json as _json
from datetime import datetime as _datetime
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from hefesto_dualsense4unix.cli.ipc_client import IpcError
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    listar_historico,
    load_all_profiles,
    load_profile,
    restaurar_do_historico,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.profiles.slug import find_by_slug, slugify

app = typer.Typer(name="profile", help="Gerencia perfis Hefesto - Dualsense4Unix.", no_args_is_help=True)  # noqa: E501
console = Console()


def _guarda_slug(name: str, *, force: bool) -> None:
    """Recusa gravar por cima de OUTRO perfil que já ocupa o mesmo arquivo.

    R-10 (auditoria 23/07): o filename é `<slugify(name)>.json`, então
    "Navegacao" e "Navegação" são o MESMO arquivo. `save_profile` sobrescreve
    sem perguntar — na GUI isso virou perda silenciosa, e no CLI era pior
    ainda: `profile create "Navegacao"` apagava a "Navegação" da usuária e
    imprimia "perfil criado" em verde. Só recusa quando o ocupante tem outro
    nome de exibição (mesmo nome = edição in-place, comportamento de sempre).
    """
    if force:
        return
    ocupante = find_by_slug(name, load_all_profiles())
    if ocupante is None or ocupante.name == name:
        return
    try:
        arquivo = f"{slugify(name)}.json"
    except ValueError:  # nome sem slug nem chega aqui (o schema recusa antes)
        arquivo = "?"
    console.print(
        f"[red]'{name}' e '{ocupante.name}' são o MESMO arquivo[/red] ({arquivo}) "
        f"— salvar assim apagaria '{ocupante.name}'."
    )
    console.print(
        "[dim]escolha outro nome ou repita com --force para sobrescrever.[/dim]"
    )
    raise typer.Exit(code=1)


@app.command("list")
def cmd_list() -> None:
    """Lista perfis no diretório XDG."""
    profiles = load_all_profiles()
    if not profiles:
        console.print("[dim]nenhum perfil encontrado[/dim]")
        return

    table = Table(title="Perfis Hefesto - Dualsense4Unix")
    table.add_column("Nome", style="cyan")
    table.add_column("Prioridade", justify="right")
    table.add_column("Match", style="magenta")
    table.add_column("Triggers", style="yellow")

    for p in profiles:
        match_desc = _describe_match(p)
        triggers_desc = f"L={p.triggers.left.mode} R={p.triggers.right.mode}"
        table.add_row(p.name, str(p.priority), match_desc, triggers_desc)

    console.print(table)


@app.command("show")
def cmd_show(name: str) -> None:
    """Mostra o JSON bruto de um perfil."""
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    console.print_json(data=profile.model_dump(mode="json"))


@app.command("activate")
def cmd_activate(name: str) -> None:
    """Ativa um perfil. Prefere o daemon vivo (profile.switch via IPC).

    Com o daemon rodando, `profile.switch` faz a troca DE VERDADE no processo
    vivo (grava session + marker e aplica no controle). Antes, este comando
    abria um 2º controller local e gravava só o marker — o daemon vivo
    sobrescrevia o controle logo em seguida, e o perfil em uso não mudava.
    Só caímos no fallback (controller local + marker) quando o daemon está
    offline; nesse caso o comportamento é 100% o de antes.
    """
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None

    # Caminho online: deixa o daemon vivo trocar o perfil (e persistir o marker).
    from hefesto_dualsense4unix.app.ipc_bridge import profile_switch

    if profile_switch(name):
        console.print(f"[green]perfil ativado via daemon:[/green] {name}")
        return

    # Fallback offline: aplica direto no hardware (se houver) e grava o marker.
    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        controller = PyDualSenseController()
        controller.connect()
        manager = ProfileManager(controller=controller)
        manager.apply(profile)
        controller.disconnect()
        console.print(f"[green]perfil aplicado no controle: {name}[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]perfil não aplicado (hardware não detectado): {exc}[/yellow]"
        )

    _write_active_marker(name)


@app.command("create")
def cmd_create(
    name: str = typer.Argument(..., help="Nome do perfil."),
    priority: int = typer.Option(5, help="Prioridade para resolução de match."),
    match_regex: str | None = typer.Option(None, help="Regex contra wm_name."),
    match_class: list[str] = typer.Option(  # noqa: B008
        default_factory=list, help="Window class (repetir para multiplos)."
    ),
    match_exe: list[str] = typer.Option(  # noqa: B008
        default_factory=list, help="Basename de exe (repetir)."
    ),
    fallback: bool = typer.Option(False, "--fallback", help="Perfil com MatchAny (prioridade 0)."),
    manual: bool = typer.Option(
        False,
        "--manual",
        help="Perfil só-manual: nunca ativa sozinho (sentinel {\"type\": \"manual\"}).",
    ),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve o perfil que já ocupa o mesmo arquivo."
    ),
) -> None:
    """Cria um perfil mínimo (triggers Off, leds apagados). Edite o JSON depois."""
    # R-10: "Navegacao" e "Navegação" são o mesmo .json — não criar por cima.
    _guarda_slug(name, force=force)
    match: Match
    if fallback:
        match = MatchAny()
        priority = 0
    elif manual:
        # R-12 item 3: dizer "só ativo na mão" sem depender do efeito colateral
        # de um criteria vazio (que o doctor passa a acusar como inalcançável).
        match = MatchManual()
    else:
        match = MatchCriteria(
            window_class=match_class or [],
            window_title_regex=match_regex,
            process_name=match_exe or [],
        )

    profile = Profile(
        name=name,
        match=match,
        priority=priority,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        leds=LedsConfig(lightbar=(0, 0, 0)),
    )
    path = save_profile(profile)
    console.print(f"[green]perfil criado: {path}[/green]")
    if isinstance(match, MatchCriteria) and profile.e_catch_all:
        # R-12: `create` sem nenhum critério grava um match que NUNCA casa, e
        # até aqui saía só o "perfil criado" em verde — o perfil nascia morto
        # para o autoswitch e nada dizia isso (foi assim que o preset
        # `coop_local` de fábrica passou meses inalcançável).
        console.print(
            "[yellow]sem --match-class/--match-regex/--match-exe: este perfil "
            "nunca ativa sozinho.[/yellow] Dê um alvo, ou recrie com --manual "
            "para declarar que ele é só para ativar na mão."
        )


@app.command("delete")
def cmd_delete(
    name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirma delete."),
) -> None:
    """Remove um perfil."""
    if not yes:
        typer.confirm(f"Deletar perfil {name!r}?", abort=True)
    try:
        delete_profile(name)
        console.print(f"[green]perfil deletado: {name}[/green]")
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None


@app.command("historico")  # (noqa-acento): nome de subcomando e ASCII
def cmd_historico(
    name: str = typer.Argument(..., help="Nome ou slug do perfil."),
) -> None:
    """Lista as versões guardadas de um perfil (a mais recente por último).

    PERFIL-SEM-RASTRO-01: cada gravação copia o arquivo ANTERIOR para
    `profiles/.historico/<slug>/`. Esta é a janela para esse histórico — e a
    resposta para "o que este perfil era ontem?".
    """
    versoes = listar_historico(name)
    if not versoes:
        console.print(f"[dim]sem histórico guardado para {name!r}[/dim]")
        console.print(
            "[dim]o histórico nasce na PRÓXIMA vez que este perfil for salvo.[/dim]"
        )
        return

    tabela = Table(title=f"Histórico de {name}")
    tabela.add_column("Quando", style="cyan")
    tabela.add_column("Match", style="magenta")
    tabela.add_column("Prioridade", justify="right")
    tabela.add_column("Arquivo", style="dim")

    for versao in versoes:
        tipo, prioridade = _resumo_da_versao(versao)
        tabela.add_row(_quando_legivel(versao.stem), tipo, prioridade, versao.name)

    console.print(tabela)
    console.print(
        f"[dim]restaurar a mais recente: profile restore {name}[/dim]"
    )


@app.command("restore")
def cmd_restore(
    name: str = typer.Argument(..., help="Nome ou slug do perfil."),
    em: str | None = typer.Option(
        None, "--em",
        help="Carimbo da versão (coluna Arquivo do `profile historico`). "  # (noqa-acento)
             "Sem isto, volta a MAIS RECENTE.",
    ),
) -> None:
    """Devolve ao perfil uma versão guardada (byte a byte).

    A versão atual é arquivada antes de ser substituída: restaurar por engano
    também tem volta.
    """
    try:
        alvo, versao = restaurar_do_historico(name, em)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(
            f"[dim]veja o que existe com: profile historico {name}[/dim]"  # (noqa-acento)
        )
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        console.print(f"[red]versão guardada não valida contra o schema:[/red] {exc}")
        raise typer.Exit(code=1) from None
    console.print(
        f"[green]perfil restaurado:[/green] {alvo} "
        f"[dim](versão {versao.name})[/dim]"
    )


def _resumo_da_versao(versao: Path) -> tuple[str, str]:
    """(`match.type`, prioridade) de uma versão guardada, sem levantar.

    Lê o JSON cru de propósito: uma versão que NÃO valida contra o schema é
    exatamente a que se quer ver na lista (é o retrato da corrupção), então ela
    aparece como "ilegível" em vez de sumir.
    """
    try:
        dados = _json.loads(versao.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError, UnicodeDecodeError):
        return ("[red]ilegível[/red]", "?")
    if not isinstance(dados, dict):
        return ("[red]ilegível[/red]", "?")
    match = dados.get("match")
    tipo = match.get("type") if isinstance(match, dict) else None
    prioridade = dados.get("priority")
    return (
        str(tipo) if isinstance(tipo, str) else "[red]sem match[/red]",
        str(prioridade) if isinstance(prioridade, int) else "?",
    )


def _quando_legivel(carimbo: str) -> str:
    """``20260805T031500_123456`` -> ``05/08/2026 03:15:00``. Cru se não casar."""
    base = carimbo.split("_", 1)[0].split("-", 1)[0]
    try:
        quando = _datetime.strptime(base, "%Y%m%dT%H%M%S")
    except ValueError:
        return carimbo
    return quando.strftime("%d/%m/%Y %H:%M:%S")


@app.command("apply")
def cmd_apply(
    file: Path = typer.Option(  # noqa: B008
        ..., "--file", "-f", exists=True, readable=True, dir_okay=False,
        help="Caminho para um JSON de perfil (mesmo schema de `profile show`).",
    ),
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Se gravar o perfil no diretório XDG antes de ativar (default: sim).",
    ),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve o perfil que já ocupa o mesmo arquivo."
    ),
) -> None:
    """Valida um JSON de perfil, salva no disco e ativa via daemon (se online).

    Útil para aplicar drafts exportados pela GUI ou gerados por scripts.
    Em `--no-save`, o perfil é validado mas NÃO persistido — apenas o
    JSON de origem é usado, e a ativação requer que o perfil JÁ exista
    no XDG com o mesmo `name` (caso contrário, exit 1).
    """
    try:
        raw = _json.loads(file.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as exc:
        console.print(f"[red]falha ao ler JSON:[/red] {exc}")
        raise typer.Exit(code=1) from None

    try:
        profile = Profile.model_validate(raw)
    except ValidationError as exc:
        console.print(f"[red]JSON não valida contra schema do perfil:[/red]\n{exc}")
        raise typer.Exit(code=1) from None

    if save:
        # R-10: um JSON exportado com o nome sem acento não pode comer o perfil
        # acentuado que já ocupa o arquivo.
        _guarda_slug(profile.name, force=force)
        path = save_profile(profile)
        console.print(f"[green]perfil salvo:[/green] {path}")
    else:
        # Sem gravar: só garante que existe no XDG para o profile.switch pegar.
        try:
            load_profile(profile.name)
        except FileNotFoundError:
            console.print(
                f"[red]--no-save exige perfil ja presente no XDG:[/red] "
                f"{profile.name!r} não encontrado."
            )
            raise typer.Exit(code=1) from None

    _activate_via_ipc_or_fallback(profile.name)


@app.command("save")
def cmd_save(
    name: str = typer.Argument(..., help="Nome do novo perfil a criar."),
    from_active: bool = typer.Option(
        False, "--from-active",
        help="Clona o perfil ativo (marker XDG) com o novo nome.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve o perfil que já ocupa o mesmo arquivo."
    ),
) -> None:
    """Cria um perfil clonando o ativo (snapshot do que está em uso)."""
    if not from_active:
        console.print(
            "[red]profile save requer --from-active[/red] "
            "(clone de outro perfil pelo nome chega em sprint futura)."
        )
        raise typer.Exit(code=2)

    active_name = read_active_marker()
    if active_name is None:
        console.print(
            "[red]nenhum perfil ativo marcado.[/red] "
            "Rode `hefesto-dualsense4unix profile activate <nome>` antes."
        )
        raise typer.Exit(code=1)

    try:
        source = load_profile(active_name)
    except FileNotFoundError:
        console.print(
            f"[red]perfil ativo ausente no disco:[/red] {active_name}"
        )
        raise typer.Exit(code=1) from None

    # R-10: clonar para um nome que cai no MESMO arquivo de outro perfil
    # apagaria aquele perfil e imprimiria "perfil clonado" em verde.
    _guarda_slug(name, force=force)

    # Clone imutável via pydantic: serializa, troca o nome, revalida.
    # R-09 (mesmo defeito da GUI, `profiles_actions`): `model_dump` DENSIFICA —
    # os defaults do schema saem marcados como explícitos e o
    # `model_fields_set` das entradas de `controllers` se perde. Um override
    # por-controle PARCIAL (só brilho) vira `lightbar:[0,0,0]` e APAGA a
    # lightbar daquele controle no clone. Reinjetar as instâncias validadas é a
    # mesma guarda de `draft_config.to_profile`.
    payload = source.model_dump(mode="json")
    payload["name"] = name
    if source.controllers:
        payload["controllers"] = source.controllers
    try:
        clone = Profile.model_validate(payload)
    except ValidationError as exc:
        console.print(f"[red]falha ao clonar perfil:[/red] {exc}")
        raise typer.Exit(code=1) from None

    path = save_profile(clone)
    console.print(
        f"[green]perfil clonado:[/green] {active_name} -> {name} ({path})"
    )


def _activate_via_ipc_or_fallback(name: str) -> None:
    """Tenta `profile.switch` no daemon; em falha, grava marker e avisa.

    Mantido em função isolada para reuso em `apply`. Mensagens claras
    (sem traceback) para todos os modos de falha.
    """
    # Import adiado para não pagar custo de asyncio/socket em `profile list`.
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    try:
        _run_call("profile.switch", {"name": name}, timeout=1.0)
        console.print(f"[green]perfil ativado via daemon:[/green] {name}")
        _write_active_marker(name)
        return
    except IpcError as exc:
        # Fix do review (2026-07-16, MED): recusa ≠ ativação. O daemon está
        # VIVO e disse não (perfil inexistente/corrompido) — gravar o marker
        # aqui registrava um switch que nunca aconteceu, e o marker tem
        # autoridade de boot (resolve_boot_profile): um marker envenenado
        # desviava o restore de TODO boot seguinte.
        console.print(f"[yellow]daemon recusou profile.switch:[/yellow] {exc.message}")
        console.print(
            "[dim]nada foi ativado — o marker local ficou como estava.[/dim]"
        )
        return
    except (FileNotFoundError, ConnectionError, OSError):
        console.print(
            "[yellow]daemon offline — gravando marker local apenas.[/yellow]"
        )

    _write_active_marker(name)
    console.print(
        f"[dim]marker local atualizado: próxima inicialização do daemon usara '{name}'[/dim]"
    )


def _describe_match(profile: Profile) -> str:
    m = profile.match
    if isinstance(m, MatchAny):
        return "[dim]any[/dim]"
    # R-12 item 3: o sentinel não tem os campos de critério — sem este ramo o
    # `profile list` estouraria com AttributeError num perfil só-manual.
    if isinstance(m, MatchManual):
        return "[dim]manual (nunca ativa sozinho)[/dim]"
    parts: list[str] = []
    if m.window_class:
        parts.append(f"class={','.join(m.window_class)}")
    if m.window_title_regex:
        parts.append(f"title~={m.window_title_regex}")
    if m.process_name:
        parts.append(f"exe={','.join(m.process_name)}")
    return " ".join(parts) if parts else "[dim]vazio[/dim]"


def _write_active_marker(name: str) -> None:
    """Wrapper compat — delega para `utils.session.save_active_marker`.

    CLUSTER-IPC-STATE-PROFILE-01 (Bug B): centralizou a escrita do marker
    em `utils.session` para que o handler IPC `profile.switch` possa usá-lo
    sem importar `cli.*` (CLI deveria depender do daemon, não o contrário).
    """
    from hefesto_dualsense4unix.utils.session import save_active_marker

    save_active_marker(name)


def read_active_marker() -> str | None:
    """Wrapper compat — delega para `utils.session.read_active_marker`."""
    from hefesto_dualsense4unix.utils.session import (
        read_active_marker as _read,
    )

    return _read()


__all__ = ["app", "read_active_marker"]
