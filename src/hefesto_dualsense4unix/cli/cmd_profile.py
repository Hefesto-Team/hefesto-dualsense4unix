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

import functools
import json as _json
from collections.abc import Callable
from datetime import datetime as _datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from hefesto_dualsense4unix.utils import identidade

if TYPE_CHECKING:
    from hefesto_dualsense4unix.profiles.schema import Match, Profile

app = typer.Typer(name="profile", help="Gerencia perfis Hefesto - DualSense4Unix.", no_args_is_help=True)  # noqa: E501
console = Console()

_Comando = TypeVar("_Comando", bound=Callable[..., Any])


def _o_arquivo_do_pedido(pedido: object) -> str | None:
    """O nome do arquivo que o pedido (nome, slug ou caminho) aponta, ou ``None``."""
    if isinstance(pedido, Path):
        return pedido.name
    if not isinstance(pedido, str):
        return None
    from hefesto_dualsense4unix.profiles.loader import arquivo_do_perfil

    try:
        alvo = arquivo_do_perfil(pedido)
    except (ValueError, OSError):
        alvo = None
    return alvo.name if alvo is not None else None


def _com_a_frase_no_lugar_do_traceback(comando: _Comando) -> _Comando:
    """O erro de leitura ou de nome vira UMA frase com o arquivo e sai com rc=1, sem traceback."""
    from pydantic import ValidationError as _Invalido

    @functools.wraps(comando)
    def _envolvido(*args: Any, **kwargs: Any) -> Any:
        try:
            return comando(*args, **kwargs)
        except (ValueError, _Invalido, UnicodeDecodeError) as exc:
            from hefesto_dualsense4unix.profiles.loader import frase_do_perfil_ilegivel

            pedido = kwargs.get("file", kwargs.get("name"))
            arquivo = _o_arquivo_do_pedido(pedido) or (str(pedido) if pedido else "")
            quem = f"{arquivo}: " if arquivo else ""
            console.print(f"[red]{escape(quem + frase_do_perfil_ilegivel(exc))}[/red]")
            raise typer.Exit(code=1) from None

    return _envolvido  # type: ignore[return-value]


def _guarda_slug(name: str, *, force: bool, atualiza: bool = False) -> None:
    """Recusa gravar sobre um nome que a pasta já ocupa, pela mesma pergunta da janela.

    O dono da pergunta «este nome está livre?» é ``loader.nome_ocupado`` (o mesmo critério do
    ``nome_livre``): o perfil legível e o arquivo ilegível do mesmo arquivo ocupam o nome.
    ``atualiza`` deixa passar o perfil legível de MESMO nome (o ``save`` que o atualiza).
    """
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, nome_ocupado
    from hefesto_dualsense4unix.profiles.slug import find_by_slug, slugify

    if force:
        return
    legiveis = load_all_profiles()
    if not nome_ocupado(name, legiveis):
        return
    ocupante = find_by_slug(name, legiveis)
    if atualiza and ocupante is not None and ocupante.name == name:
        return
    arquivo = f"{slugify(name)}.json"
    if ocupante is None:
        console.print(
            f"[red]o arquivo {arquivo} já ocupa o nome '{name}' e não abre como perfil[/red] "
            "— salvar assim apagaria esse arquivo."
        )
    elif ocupante.name == name:
        console.print(f"[red]o perfil '{name}' já existe[/red] ({arquivo}).")
    else:
        console.print(
            f"[red]'{name}' e '{ocupante.name}' são o MESMO arquivo[/red] ({arquivo}) "
            f"— salvar assim apagaria '{ocupante.name}'."
        )
    console.print(
        "[dim]escolha outro nome ou repita com --force para sobrescrever.[/dim]"
    )
    raise typer.Exit(code=1)


def _diz_que_a_anterior_ficou(nome: str, existia: bool) -> None:
    """Gravar por cima com ``--force`` diz onde a versão de antes ficou."""
    if existia:
        from hefesto_dualsense4unix.profiles.slug import slugify

        console.print(
            f"[dim]a versão anterior de '{escape(nome)}' ficou no histórico "
            f"(profile historico {escape(slugify(nome))}).[/dim]"  # (noqa-acento)
        )


def _igual_ao_que_esta_no_disco(profile: Profile) -> bool:
    """O perfil de MESMO nome que já está na pasta tem o conteúdo deste (fora as datas)?"""
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    ocupante = find_by_slug(profile.name, load_all_profiles())
    if ocupante is None or ocupante.name != profile.name:
        return False
    fora = {"criado_em", "modificado_em"}
    return ocupante.model_dump(mode="json", exclude=fora) == profile.model_dump(
        mode="json", exclude=fora)


@app.command("list")
def cmd_list(
    como_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Lista os perfis a escolher no diretório XDG — o Freestyle é o botão, não linha."""
    from hefesto_dualsense4unix.profiles.loader import (
        load_all_profiles,
        perfis_de_versao_mais_nova,
        perfis_ilegiveis,
    )
    from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher

    profiles = os_perfis_de_escolher(load_all_profiles())
    mais_novos = perfis_de_versao_mais_nova()
    ilegiveis = perfis_ilegiveis()
    if como_json:
        console.print_json(data=[
            {
                "nome": p.name,
                "prioridade": p.priority,
                "tipo": p.match.type,
                "gatilho_esquerdo": p.triggers.left.mode,
                "gatilho_direito": p.triggers.right.mode,
            }
            for p in profiles
        ] + [
            {"nome": n.nome, "de_versao_mais_nova": True, "formato": n.versao}
            for n in mais_novos
        ] + [
            {"nome": Path(i.arquivo).stem, "arquivo": i.arquivo, "ilegivel": True,
             "motivo": i.motivo}
            for i in ilegiveis
        ])
        return
    if not profiles and not mais_novos and not ilegiveis:
        console.print("[dim]nenhum perfil encontrado[/dim]")
        return

    table = Table(title=f"Perfis {identidade.atual().nome_longo}")
    table.add_column("Nome", style="cyan")
    table.add_column("Prioridade", justify="right")
    table.add_column("Match", style="magenta")
    table.add_column("Triggers", style="yellow")

    for p in profiles:
        match_desc = _describe_match(p)
        triggers_desc = f"L={p.triggers.left.mode} R={p.triggers.right.mode}"
        table.add_row(p.name, str(p.priority), match_desc, triggers_desc)

    if profiles:
        console.print(table)
    for n in mais_novos:
        console.print(
            f"[yellow]{n.nome}[/yellow]: de uma versão mais nova do Hefesto "
            f"(formato {n.versao}); esta versão não o usa."
        )
    for i in ilegiveis:
        console.print(f"[yellow]{escape(i.arquivo)}[/yellow]: ilegível: {escape(i.motivo)}")


@app.command("show")
@_com_a_frase_no_lugar_do_traceback
def cmd_show(name: str) -> None:
    """Mostra o JSON bruto de um perfil."""
    from hefesto_dualsense4unix.profiles.loader import (
        PerfilDeVersaoMaisNovaError,
        load_profile,
    )

    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    except PerfilDeVersaoMaisNovaError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None
    console.print_json(data=profile.model_dump(mode="json"))


@app.command("activate")
@_com_a_frase_no_lugar_do_traceback
def cmd_activate(name: str) -> None:
    """Ativa um perfil pelo daemon vivo (`profile.switch`), que troca no processo e grava a escolha.

    Só com o daemon comprovadamente parado (socket ausente ou conexão recusada) aplica no
    controle local e grava a escolha pelo dono. Recusa sai com o motivo (rc 2) e serviço que não
    responde a tempo, com a frase do prazo (rc 1): nada se grava por baixo do serviço vivo.
    """
    from hefesto_dualsense4unix.profiles.loader import (
        PerfilDeVersaoMaisNovaError,
        load_profile,
    )

    try:
        profile = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    except PerfilDeVersaoMaisNovaError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    from hefesto_dualsense4unix.app.ipc_bridge import ATENDEU, pedir_ao_servico
    from hefesto_dualsense4unix.cli.chamada_ao_servico import sair_se_o_servico_vive

    desfecho = pedir_ao_servico("profile.switch", {"name": name})
    sair_se_o_servico_vive(console, desfecho)
    if desfecho.estado == ATENDEU:
        console.print(f"[green]perfil ativado via daemon:[/green] {name}")
        return

    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        controller = PyDualSenseController()
        controller.connect()
        manager = ProfileManager(controller=controller)
        manager.apply(o_que_vale(profile))
        controller.disconnect()
        console.print(f"[green]perfil aplicado no controle: {name}[/green]")
    except Exception as exc:
        console.print(
            f"[yellow]perfil não aplicado (hardware não detectado): {exc}[/yellow]"
        )

    _gravar_a_escolha_sem_o_daemon(name)


@app.command("create")
@_com_a_frase_no_lugar_do_traceback
def cmd_create(
    name: str = typer.Argument(..., help="Nome do perfil."),
    priority: int = typer.Option(
        5, min=0, max=200, help="Prioridade para resolução de match (0 a 200)."
    ),
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
    """Cria um perfil enxuto: só nome, alvo e prioridade; o resto herda o computador."""
    from hefesto_dualsense4unix.profiles.loader import nome_ocupado, save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        MatchAny,
        MatchCriteria,
        MatchManual,
        Profile,
    )

    _guarda_slug(name, force=force)
    existia = force and nome_ocupado(name)
    match: Match
    if fallback:
        match = MatchAny()
        priority = 0
    elif manual:
        match = MatchManual()
    else:
        try:
            match = MatchCriteria(
                window_class=match_class or [],
                window_title_regex=match_regex,
                process_name=match_exe or [],
            )
        except ValidationError as exc:
            console.print(f"[red]{exc.errors()[0]['msg'].removeprefix('Value error, ')}[/red]")
            raise typer.Exit(code=1) from exc

    profile = Profile(name=name, match=match, priority=priority)
    path = save_profile(profile, enxuto=True)
    console.print(f"[green]perfil criado: {path}[/green]")
    _diz_que_a_anterior_ficou(name, existia)
    if isinstance(match, MatchCriteria) and profile.e_catch_all:
        console.print(
            "[yellow]sem --match-class/--match-regex/--match-exe: este perfil "
            "nunca ativa sozinho.[/yellow] Dê um alvo, ou recrie com --manual "
            "para declarar que ele é só para ativar na mão."
        )


@app.command("delete")
@_com_a_frase_no_lugar_do_traceback
def cmd_delete(
    name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirma delete."),
) -> None:
    """Remove um perfil. O que está valendo agora é recusado, como na aba Perfis."""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        frase_da_remocao_do_perfil_ativo,
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.loader import (
        OFreestyleNaoSeApagaError,
        delete_profile,
    )
    from hefesto_dualsense4unix.profiles.manager import esquecer_o_perfil_apagado

    aviso = frase_da_remocao_do_perfil_ativo(name, perfil_que_esta_valendo(_estado_do_daemon()))
    if aviso:
        console.print(f"[red]{aviso}[/red]")
        raise typer.Exit(code=1)
    if not yes:
        typer.confirm(f"Deletar perfil {name!r}?", abort=True)
    try:
        apagado = delete_profile(name)
    except FileNotFoundError:
        console.print(f"[red]perfil não encontrado: {name}[/red]")
        raise typer.Exit(code=1) from None
    except OFreestyleNaoSeApagaError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None
    esquecer_o_perfil_apagado(name)
    console.print(
        f"[green]perfil deletado: {name}[/green] [dim](arquivo {escape(apagado.name)}; "
        f"a cópia fica no histórico)[/dim]"
    )


def _estado_do_daemon() -> dict[str, object] | None:
    """O estado do daemon, ou ``None`` sem resposta (fora do ar ou prazo vencido).

    Sem resposta, quem diz o que vale é o marcador em disco (`perfil_que_esta_valendo`).
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _safe_call, teto_da_linha_de_comando

    metodo = "daemon.state_full"
    ok, estado = _safe_call(metodo, None, timeout=teto_da_linha_de_comando(metodo))
    return estado if ok and isinstance(estado, dict) else None


@app.command("historico")  # (noqa-acento)
@_com_a_frase_no_lugar_do_traceback
def cmd_historico(
    name: str = typer.Argument(..., help="Nome ou slug do perfil."),
) -> None:
    """Lista as versões guardadas de um perfil (a mais recente por último)."""
    from hefesto_dualsense4unix.profiles.loader import listar_historico

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
@_com_a_frase_no_lugar_do_traceback
def cmd_restore(
    name: str = typer.Argument(..., help="Nome ou slug do perfil."),
    em: str | None = typer.Option(
        None, "--em",
        help="Carimbo da versão (coluna Arquivo do `profile historico`). "  # (noqa-acento)
             "Sem isto, volta a MAIS RECENTE.",
    ),
) -> None:
    """Devolve ao perfil uma versão guardada (byte a byte)."""
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico

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
    """(`match.type`, prioridade) de uma versão guardada, sem levantar."""
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
@_com_a_frase_no_lugar_do_traceback
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
    """Valida um JSON de perfil, salva no disco e ativa via daemon (se online)."""
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.loader import (
        load_profile,
        nome_livre,
        nome_ocupado,
        save_profile,
    )
    from hefesto_dualsense4unix.profiles.schema import Profile

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
        if not force and nome_ocupado(profile.name):
            if _igual_ao_que_esta_no_disco(profile):
                console.print(f"[green]perfil já igual no disco:[/green] {profile.name}")
            else:
                nome = nome_livre(profile.name)
                console.print(
                    f"[yellow]'{profile.name}' já existe: gravado como '{nome}'[/yellow] "
                    "(repita com --force para sobrescrever)."
                )
                profile = profile.model_copy(update={"name": nome})
                path = save_profile(profile)
                console.print(f"[green]perfil salvo:[/green] {path}")
        else:
            existia = force and nome_ocupado(profile.name)
            path = save_profile(profile)
            console.print(f"[green]perfil salvo:[/green] {path}")
            _diz_que_a_anterior_ficou(profile.name, existia)
    else:
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
@_com_a_frase_no_lugar_do_traceback
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
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.loader import load_profile, nome_ocupado, save_profile
    from hefesto_dualsense4unix.profiles.schema import Profile

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

    _guarda_slug(name, force=force, atualiza=True)
    existia = force and nome_ocupado(name)

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
    _diz_que_a_anterior_ficou(name, existia)


def _activate_via_ipc_or_fallback(name: str) -> None:
    """Tenta `profile.switch` no daemon; parado, grava a escolha e avisa.

    Mantido em função isolada para reuso em `apply`. Recusa sai com o motivo
    (rc 2) e serviço mudo com a frase do prazo (rc 1): nada se grava por baixo
    do serviço vivo.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import ATENDEU, pedir_ao_servico
    from hefesto_dualsense4unix.cli.chamada_ao_servico import sair_se_o_servico_vive

    desfecho = pedir_ao_servico("profile.switch", {"name": name})
    sair_se_o_servico_vive(console, desfecho)
    if desfecho.estado == ATENDEU:
        console.print(f"[green]perfil ativado via daemon:[/green] {name}")
        return

    console.print(
        "[yellow]daemon offline — gravando a escolha local apenas.[/yellow]"
    )
    _gravar_a_escolha_sem_o_daemon(name)
    console.print(
        f"[dim]escolha gravada: a próxima inicialização do daemon usará '{name}'[/dim]"
    )


def _describe_match(profile: Profile) -> str:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchManual

    m = profile.match
    if isinstance(m, MatchAny):
        return "[dim]any[/dim]"
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


def _gravar_a_escolha_sem_o_daemon(name: str) -> None:
    """A ativação à mão com o daemon fora do ar: a escolha do usuário, pelo dono."""
    from hefesto_dualsense4unix.profiles.manager import e_o_freestyle, ligar_o_freestyle
    from hefesto_dualsense4unix.utils.session import gravar_a_escolha

    ligar_o_freestyle(None, e_o_freestyle(name))
    gravar_a_escolha(name)


def read_active_marker() -> str | None:
    """Wrapper compat — delega para `utils.session.read_active_marker`."""
    from hefesto_dualsense4unix.utils.session import (
        read_active_marker as _read,
    )

    return _read()


__all__ = ["app", "read_active_marker"]
