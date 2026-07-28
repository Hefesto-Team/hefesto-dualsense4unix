"""Subcomando `hefesto-dualsense4unix gamepad steam-input ...` — o desfazer.

BOTAO-QUE-NAO-MENTE-01 (entrega 2) e STEAM-INPUT-01 (entrega 3).

`integrations/steam_launch_options.remove_appid_from_steam_input_allowlist`
foi escrita, testada com nove casos — e nunca ligada. Grep em `src/` achava
**zero** chamadores. Consequência medida: pôr um jogo na exceção do Steam Input
é um clique ("Este jogo não funciona"); tirar exigia abrir
`~/.config/hefesto-dualsense4unix/steam_input_apps.txt` num editor de texto. Na
prática o opt-in era irreversível para quem não mexe em arquivo de configuração
— e o preço de um jogo marcado por engano é alto: ele deixa de ter cor,
gatilhos e co-op do Hefesto até ser desmarcado.

Este módulo é a primeira porta de saída, pela linha de comando:

    hefesto-dualsense4unix gamepad steam-input list
    hefesto-dualsense4unix gamepad steam-input remove 2111190
    hefesto-dualsense4unix gamepad steam-input remove "mullet"

**Por nome, não por número.** A allowlist é um arquivo de appids; um appid não
diz nada para quem joga. O nome vem do `appmanifest_<appid>.acf` da Steam
(leitura pura, sem rede) e serve para os dois lados: a listagem mostra o nome, e
o `remove` aceita o nome no lugar do número. Jogo desinstalado não tem manifest
— nesse caso a linha diz "(não instalado)" em vez de inventar: o comentário que
o `add` escreve acima do appid é texto livre da mantenedora (a instalação nasce
com sete linhas de cabeçalho) e adivinhar nome ali erraria com facilidade.

**Onde este comando mora, e por quê.** O lugar natural seria um `steam` de
primeiro nível, mas registrar sub-app novo exige mexer em `cli/app.py`, que
nesta leva tem outro dono. Fica pendurado em `gamepad` — que é exatamente o
domínio da allowlist: ela decide *quem entrega o controle ao jogo*, o gamepad
virtual do Hefesto ou o Steam Input.
"""
from __future__ import annotations

import contextlib
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

app = typer.Typer(
    name="steam-input",
    help="Exceção do Steam Input — os jogos em que o Hefesto sai da frente.",
    no_args_is_help=True,
)
console = Console()

#: Linha `"chave"<tab>"valor"` de .acf/.vdf. O valor pode conter espaço.
_PAR_VDF = re.compile(r'^\s*"(?P<chave>[^"]+)"\s+"(?P<valor>.*)"\s*$')


def _desescapar(valor: str) -> str:
    """Desfaz o escape de VDF (`\\\\` e `\\"`) — mesmo critério do proton_pin."""
    return valor.replace('\\\\', '\\').replace('\\"', '"')


def _pastas_steamapps(home: Path | None = None) -> list[Path]:
    """A `steamapps` padrão mais as bibliotecas extras do `libraryfolders.vdf`.

    Best-effort e read-only: biblioteca ilegível ou ausente é pulada em
    silêncio — listar jogo é conveniência, não pode derrubar o comando.
    """
    from hefesto_dualsense4unix.integrations.proton_pin import default_steam_root

    raiz = default_steam_root(home) / "steamapps"
    pastas = [raiz]
    with contextlib.suppress(OSError):
        texto = (raiz / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        for linha in texto.splitlines():
            par = _PAR_VDF.match(linha)
            if par is None or par.group("chave").lower() != "path":
                continue
            candidata = Path(_desescapar(par.group("valor"))) / "steamapps"
            if candidata.is_dir() and candidata not in pastas:
                pastas.append(candidata)
    return pastas


def nome_do_appid(appid: str, home: Path | None = None) -> str | None:
    """Nome do jogo pelo `appmanifest_<appid>.acf`. `None` = não instalado.

    Sem rede e sem cache: o manifest é a fonte que a própria Steam mantém em
    disco. Se o jogo foi desinstalado, devolver `None` é a resposta honesta.
    """
    for steamapps in _pastas_steamapps(home):
        manifesto = steamapps / f"appmanifest_{appid}.acf"
        try:
            texto = manifesto.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            par = _PAR_VDF.match(linha)
            if par is not None and par.group("chave").lower() == "name":
                nome = _desescapar(par.group("valor")).strip()
                if nome:
                    return nome
    return None


def _entradas() -> list[tuple[str, str | None]]:
    """A allowlist como `[(appid, nome ou None)]`, na ordem do arquivo."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        parse_steam_input_allowlist,
        steam_input_allowlist_path,
    )

    caminho = steam_input_allowlist_path()
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError:
        texto = ""
    return [(appid, nome_do_appid(appid)) for appid in parse_steam_input_allowlist(texto)]


def _rotulo(appid: str, nome: str | None) -> str:
    """Uma linha por jogo, com nome — o formato que a sprint pediu."""
    return f"{escape(nome)} (appid {appid})" if nome else f"appid {appid} (não instalado)"


def _resolver(alvo: str, entradas: list[tuple[str, str | None]]) -> str | None:
    """Traduz o que a pessoa digitou em appid. `None` = não deu para decidir.

    Número passa direto (inclusive appid que nem está na allowlist — quem julga
    presença é a função de remoção, que tem o status `nao_estava`). Texto casa
    contra os NOMES da allowlist: primeiro igualdade exata (sem caixa), depois
    trecho contido. Empate não é resolvido no chute — o comando mostra os
    candidatos e sai sem mexer em nada.
    """
    bruto = alvo.strip()
    if bruto.isdigit():
        return bruto
    procurado = bruto.casefold()
    exatos = [appid for appid, nome in entradas if nome and nome.casefold() == procurado]
    if len(exatos) == 1:
        return exatos[0]
    parciais = [appid for appid, nome in entradas if nome and procurado in nome.casefold()]
    if len(parciais) == 1:
        return parciais[0]
    candidatos = exatos or parciais
    if not candidatos:
        console.print(f"[red]nenhum jogo da exceção casa com[/red] {escape(bruto)!r}")
        console.print("[dim]veja os nomes com 'gamepad steam-input list'.[/dim]")
        return None
    console.print(f"[yellow]{escape(bruto)!r} casa com mais de um jogo:[/yellow]")
    por_appid = dict(entradas)
    for appid in candidatos:
        console.print(f"  {_rotulo(appid, por_appid.get(appid))}")
    console.print("[dim]repita usando o appid.[/dim]")
    return None


def _avisar_daemon() -> None:
    """Faz a mudança valer agora, sem reiniciar nada (best-effort).

    A allowlist é relida do disco a cada consulta; o que NÃO é relido é a
    materialização do `steam_app_<appid>.env`, que só nasce em
    `materialize_launch_env`. Mesmo aviso que a GUI manda em
    `_recarregar_apos_allowlist`. Daemon offline é normal — ele rematerializa
    sozinho no próximo boot.
    """
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.app.ipc_bridge import _run_call

        _run_call("launch_env.refresh", {}, timeout=1.0)


@app.command("list")
def cmd_list() -> None:
    """Lista os jogos da exceção do Steam Input, um por linha, pelo nome."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        steam_input_allowlist_path,
    )

    entradas = _entradas()
    caminho = steam_input_allowlist_path()
    if not entradas:
        console.print("[dim]Nenhum jogo na exceção do Steam Input.[/dim]")
        console.print(
            "[dim]O Hefesto entrega o controle em todos os jogos. "
            "A exceção nasce do botão 'Este jogo não funciona'.[/dim]"
        )
        return

    console.print("Jogos em que o Hefesto sai da frente (o controle vem da Steam):")
    for appid, nome in entradas:
        console.print(f"  {_rotulo(appid, nome)} — controle entregue pela Steam, sem co-op")
    console.print(f"\n[dim]arquivo: {caminho}[/dim]")
    console.print(
        "[dim]para desfazer: 'gamepad steam-input remove <nome ou appid>'.[/dim]"
    )


@app.command("remove")
def cmd_remove(
    jogo: str = typer.Argument(
        ...,
        metavar="JOGO",
        help="AppID (2111190) ou parte do nome do jogo ('mullet').",
    ),
) -> None:
    """Tira um jogo da exceção — o Hefesto volta a entregar o controle nele."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        remove_appid_from_steam_input_allowlist,
    )

    entradas = _entradas()
    appid = _resolver(jogo, entradas)
    if appid is None:
        raise typer.Exit(code=1)

    rotulo = _rotulo(appid, dict(entradas).get(appid))
    status = remove_appid_from_steam_input_allowlist(appid)

    if status == "removido":
        console.print(f"[green]desfeito:[/green] {rotulo} saiu da exceção.")
        console.print(
            "[dim]o Hefesto volta a entregar o gamepad virtual nesse jogo "
            "(cor, gatilhos e co-op).[/dim]"
        )
        _avisar_daemon()
        return

    if status == "nao_estava":
        console.print(f"[yellow]{rotulo} já não estava na exceção[/yellow] — nada a desfazer.")
        raise typer.Exit(code=1)
    if status == "appid_invalido":
        console.print(f"[red]appid inválido:[/red] {escape(appid)!r}")
        raise typer.Exit(code=2)
    console.print("[red]não deu para escrever a allowlist[/red] (permissão? disco cheio?).")
    raise typer.Exit(code=1)


__all__ = ["app", "nome_do_appid"]
