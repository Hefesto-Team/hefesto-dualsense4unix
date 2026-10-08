"""Launch Options da Steam: string do wrapper + migração do veneno legado.

DEDUP-04/DEDUP-05 (sprint 2026-07-16-sprint-dedup-sem-launch-option.md) e
UX-04/UX-05 (sprint autoswitch-e-launch-options): a desduplicação deixa de ser
uma env ESTÁTICA colada por jogo e vira o wrapper `hefesto-launch %command%`
— string CONSTANTE que decide as envs NA HORA consultando o daemon via IPC.

Este módulo concentra:

1. A string constante do wrapper (`WRAPPER_LAUNCH`) — consumida pelo botão
   "Copiar opções para os jogos" da GUI (`compose_launch`) e pela migração. Ela
   degrada sozinha: se o wrapper não existir no caminho, o `sh -c` cai em
   `exec env "$@"` e o jogo abre do mesmo jeito (pior caso: controle
   duplicado, nunca zero controles nem launch quebrado).
2. A MIGRAÇÃO do veneno persistido no `localconfig.vdf` (a variante de ondas
   anteriores com `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` esconde o
   único controle quando o vpad degrada — "em BT nada funciona", provado ao
   vivo). `--migrate` troca as linhas envenenadas pela chamada do wrapper;
   `--strip` (uninstall) remove o nosso trecho — novo E legado — deixando o
   resto intacto.
3. A APLICAÇÃO em massa (`--apply`, `apply_wrapper_to_all_games`): põe a
   chamada do wrapper em TODOS os jogos do bloco `apps`, inclusive nos que
   nunca tiveram LaunchOptions. É o que o botão "Aplicar aos jogos da Steam"
   da GUI faz e — desde a JOGO-COMPLETO-01/E4 — o que o `install.sh` faz sem
   flag: a migração sozinha não põe NADA numa instalação limpa (não há veneno
   legado a migrar), e sem o wrapper as envs que o projeto materializa nunca
   são exportadas — todo jogo enxerga dois DualSense.

Decisões herdadas da revisão adversarial (não relaxar):

- "Nunca clobberar" vale só para opções genuinamente do usuário (MANGOHUD
  etc.): elas são preservadas e continuam funcionando porque o wrapper
  termina em `exec env "$@"` — `VAR=VAL` pré-existente vira argumento do
  env(1), nunca um comando a executar.
- O strip NUNCA caça `SDL_JOYSTICK_HIDAPI=0`/`PROTON_ENABLE_HIDRAW=1`
  soltos: só em linhas que contenham a assinatura do IGNORE (o primeiro é
  fix comum de controles de terceiros; o segundo é o enabler do hidraw).
- `__GL_SHADER_*` é preservado byte a byte no strip do uninstall (não é
  veneno); na MIGRAÇÃO ele sai da linha envenenada porque o wrapper repõe o
  preload via arquivo de env materializado.
- Steam aberta => recusa com mensagem honesta (a Steam regrava o vdf ao
  sair e pisaria a edição). `--stop-steam` (install/uninstall) fecha e
  reabre com o mesmo fluxo do precedente `scripts/disable_steam_input.sh`.
- Steam Flatpak/Snap: a MIGRAÇÃO não escreve o wrapper (o caminho do host
  num vdf cuja sandbox não enxerga o wrapper quebraria o launch) mas ainda
  REMOVE o veneno legado — pular o vdf por completo o deixaria gravado para
  sempre; o strip é sempre permitido (remover é seguro).

Módulo 100% stdlib DE PROPÓSITO: o uninstall.sh o executa como script
avulso (`python3 src/.../steam_launch_options.py --strip`) depois de o
.venv já ter sido removido.
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

try:
    from . import fora_do_servico
    from .ambiente_do_jogo import ambiente_limpo
except ImportError:  # pragma: no cover - executado como script avulso pelo install/uninstall
    import fora_do_servico  # type: ignore[no-redef]
    from ambiente_do_jogo import ambiente_limpo  # type: ignore[no-redef]

WRAPPER_HOME_RELPATH = ".local/share/hefesto-dualsense4unix/bin/hefesto-launch"

#: O motivo de erro de quem foi gravado e, relido do disco, não está como gravamos.
MOTIVO_NAO_FIRMOU = "nao_firmou"

#: LaunchOption pré-existente `VAR=VAL %command%` vira `$1` e o env(1) a
#: processa como assignment em vez de tentar executá-la (ENOENT).
_WRAPPER_INNER = (
    'W="$HOME/' + WRAPPER_HOME_RELPATH + '"; '
    '[ -x "$W" ] && exec "$W" "$@"; exec env "$@"'
)

#: Prefixo da string constante (sem o `%command%` final) — é o que a migração
WRAPPER_PREFIX = "sh -c '" + _WRAPPER_INNER + "' hefesto-launch"

#: A string constante completa — o que o botão da GUI copia e o que fica no
WRAPPER_LAUNCH = WRAPPER_PREFIX + " %command%"

#: DualSense físico). Ela cola a variável ao par, e por isso só enxerga o
IGNORE_SIGNATURE = "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"

#: DualSense físico) separados. A separação é o mecanismo inteiro da
IGNORE_VAR = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
IGNORE_PAR_HEFESTO = "0x054c/0x0ce6"

_IGNORE_ASSIGN_RE = re.compile(
    r"(?<!\S)" + re.escape(IGNORE_VAR) + r"=(?P<lista>\S*)(?!\S)"
)

_COOCCURRING_TOKENS = ("SDL_JOYSTICK_HIDAPI=0", "PROTON_ENABLE_HIDRAW=1")

_PRELOAD_TOKENS = (
    "__GL_SHADER_DISK_CACHE=1",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1",
)

RAIZES_STEAM_RELATIVAS = (
    ".steam/steam",
    ".local/share/Steam",
    ".var/app/com.valvesoftware.Steam/.steam/steam",
    "snap/steam/common/.steam/steam",
)

_VDF_GLOB_PATTERNS = tuple(
    f"{raiz}/userdata/*/config/localconfig.vdf" for raiz in RAIZES_STEAM_RELATIVAS
)

_SANDBOXED_MARKERS = ("/.var/app/", "/snap/steam/")

_LAUNCH_OPTIONS_RE = re.compile(
    r'^(?P<prefix>\s*"LaunchOptions"\s+")(?P<value>(?:\\.|[^"\\])*)(?P<suffix>"\s*)$'
)

_VDF_PAIR_RE = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s+"(?P<value>(?:\\.|[^"\\])*)"\s*$'
)
_VDF_KEY_ONLY_RE = re.compile(r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*$')


def _vdf_unescape(value: str) -> str:
    """Desfaz o escaping de KeyValues da Steam (\\\" e \\\\)."""
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _vdf_escape(value: str) -> str:
    """Aplica o escaping de KeyValues da Steam (a string do wrapper tem aspas)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _token_re(token: str) -> re.Pattern[str]:
    """Regex que casa `token` como token COMPLETO (delimitado por espaço ou"""
    return re.compile(r"(?<!\S)" + re.escape(token) + r"(?!\S)")


def _token_presente(value: str, token: str) -> bool:
    """True quando `token` aparece como token completo em `value`."""
    return _token_re(token).search(value) is not None


def _remove_token(value: str, token: str) -> str:
    """Remove UMA ocorrência de `token` COMPLETO preservando o resto byte a byte."""
    m = _token_re(token).search(value)
    if m is None:
        return value
    start, end = m.span()
    if end < len(value) and value[end] == " ":
        return value[:start] + value[end + 1:]
    if start > 0 and value[start - 1] == " ":
        return value[: start - 1] + value[end:]
    return value[:start] + value[end:]


def subtrair_nosso_ignore(value: str) -> str:
    """Tira o NOSSO par de dentro da lista de IGNORE, deixando a dela intacta."""
    out = value
    for m in reversed(list(_IGNORE_ASSIGN_RE.finditer(value))):
        itens = m.group("lista").split(",")
        restantes = [i for i in itens if i.strip().lower() != IGNORE_PAR_HEFESTO]
        if len(restantes) == len(itens):
            continue
        restantes = [i for i in restantes if i.strip()]
        start, end = m.span()
        if restantes:
            out = out[:start] + IGNORE_VAR + "=" + ",".join(restantes) + out[end:]
            continue
        if end < len(out) and out[end] == " ":
            out = out[:start] + out[end + 1:]
        elif start > 0 and out[start - 1] == " ":
            out = out[: start - 1] + out[end:]
        else:
            out = out[:start] + out[end:]
    return out


def has_poison(value: str) -> bool:
    """A linha carrega a NOSSA variável de IGNORE e o NOSSO par?

    **A PERGUNTA ERA ESTREITA E FICOU LARGA — 06/09/2026, ONDA5-07-01.** Até
    aqui ela cobrava a `IGNORE_SIGNATURE` como TOKEN COMPLETO, o que na prática
    quer dizer *"a atribuição tem o nosso par SOZINHO na lista"*. A assinatura
    cola `VAR=` ao par, e daí saía um ponto cego estrutural: numa linha
    `VAR=0x057e/0x2009,0x054c/0x0ce6` — o nosso par em SEGUNDO — a substring
    nem aparece.

    **Medido antes da cura:** `has_poison` e `has_extended_ignore` respondiam
    **os dois `False`**, o produto não via o próprio veneno, e `migrate_value`
    EMBRULHAVA a linha inteira — pondo o par que manda ignorar o DualSense do usuário
    como argumento do `env(1)` de dentro do wrapper. O jogo continuava cego para
    o controle, com a tela dizendo que o atalho de inicialização estava no
    lugar.

    A largura é de propósito, e ela é a rede: pega inclusive a forma que a
    subtração não sabe desmontar (uma lista entre aspas, por exemplo), e é
    `has_extended_ignore` quem separa essa do resto. **Quem AGE é
    `subtrair_nosso_ignore`**, que nunca remove substring — a proteção contra o
    fragmento-comando mora nela, não mais nesta pergunta.

    `IGNORE_SIGNATURE` continua existindo: é o texto que a documentação, o
    `launch_env` e o `doctor.sh` citam.
    """
    return IGNORE_VAR in value and IGNORE_PAR_HEFESTO in value


def has_extended_ignore(value: str) -> bool:
    """True quando o nosso par está lá e a SUBTRAÇÃO NÃO O ALCANÇA."""
    return has_poison(value) and subtrair_nosso_ignore(value) == value


def count_extended_ignore(text: str) -> int:
    """Nº de linhas LaunchOptions de um vdf com a assinatura estendida."""
    n = 0
    for line in text.splitlines():
        m = _LAUNCH_OPTIONS_RE.match(line.rstrip("\r\n"))
        if m is None:
            continue
        if has_extended_ignore(_vdf_unescape(m.group("value"))):
            n += 1
    return n


def strip_value(value: str) -> str:
    """Remove o NOSSO trecho (wrapper novo E veneno legado) de uma LaunchOptions.

    UX-04 (uninstall, incondicional): tira a assinatura + co-ocorrentes da
    MESMA linha, preserva `__GL_SHADER_*` e opções do usuário byte a byte.
    Linha que era só nossa colapsa para "" (um `%command%` órfão é resíduo).

    A LISTA ESTENDIDA TAMBÉM, E A RAZÃO É A DESINSTALAÇÃO — ONDA5-07-01,
    06/09/2026. Enquanto a `has_poison` era o portão, numa linha estendida este
    caminho não tirava nada: o nosso par ficava na lista dela **para sempre
    depois de desinstalar** — e sem o wrapper, aquele par manda o jogo ignorar o
    DualSense FÍSICO dela. Deixar sujeira nossa numa máquina de onde fomos
    embora é o oposto de desinstalar.
    """
    out = value
    if WRAPPER_PREFIX in out:
        out = _remove_token(out, WRAPPER_PREFIX)
    subtraida = subtrair_nosso_ignore(out)
    if subtraida != out:
        out = subtraida
        for token in _COOCCURRING_TOKENS:
            out = _remove_token(out, token)
    if out.strip() == "%command%":
        return ""
    return out.strip() if out != value else out


def migrate_value(value: str) -> str:
    """Migra UMA LaunchOptions envenenada para a chamada do wrapper."""
    if has_extended_ignore(value):
        return value
    out = value
    subtraida = subtrair_nosso_ignore(out)
    if subtraida != out:
        out = subtraida
        for token in (*_COOCCURRING_TOKENS, *_PRELOAD_TOKENS):
            out = _remove_token(out, token)
    out = out.strip()
    if WRAPPER_PREFIX in out:
        return out
    if not out:
        return WRAPPER_LAUNCH
    if "%command%" in out:
        return WRAPPER_PREFIX + " " + out
    return WRAPPER_LAUNCH + " " + out


def transform_vdf_text(
    text: str, mode: str, *, so_os_jogos: Collection[str] | None = None
) -> tuple[str, int]:
    """Aplica `migrate`/`strip` às linhas LaunchOptions de um vdf."""
    if mode not in ("migrate", "strip", "recolher"):
        raise ValueError(f"modo desconhecido: {mode}")
    changed = 0
    lines = text.splitlines(keepends=True)
    pilha: list[str] = []
    pendente: str | None = None
    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        enxuta = body.strip()
        if enxuta == "{":
            pilha.append(pendente if pendente is not None else "")
            pendente = None
            continue
        if enxuta == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        m = _LAUNCH_OPTIONS_RE.match(body)
        if m is None:
            so_chave = _VDF_KEY_ONLY_RE.match(enxuta)
            pendente = (
                _vdf_unescape(so_chave.group("key")) if so_chave is not None else None
            )
            continue
        pendente = None
        if so_os_jogos is not None and (not pilha or pilha[-1] not in so_os_jogos):
            continue
        na_canonica = (
            bool(pilha) and pilha[-1].isdigit() and e_a_arvore_canonica(pilha[:-1])
        )
        if mode == "recolher":
            if na_canonica:
                continue
            lines[i] = ""
            changed += 1
            continue
        value = _vdf_unescape(m.group("value"))
        if not (has_poison(value) or WRAPPER_PREFIX in value):
            continue
        modo_aqui = mode if na_canonica else "strip"
        new_value = (
            migrate_value(value) if modo_aqui == "migrate" else strip_value(value)
        )
        if new_value == value:
            continue
        lines[i] = (
            m.group("prefix") + _vdf_escape(new_value) + m.group("suffix") + eol
        )
        changed += 1
    return "".join(lines), changed


def discover_vdfs(home: Path | None = None) -> list[Path]:
    """Localiza os localconfig.vdf de todos os layouts, deduplicando symlinks."""
    base = home or Path.home()
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in _VDF_GLOB_PATTERNS:
        for candidate in sorted(base.glob(pattern)):
            try:
                real = candidate.resolve()
            except OSError:
                continue
            if real in seen or not real.is_file():
                continue
            seen.add(real)
            out.append(real)
    return out


def is_sandboxed_layout(vdf: Path) -> bool:
    """True para vdf de Steam Flatpak/Snap (migração proibida — DEDUP-04)."""
    text = str(vdf)
    return any(marker in text for marker in _SANDBOXED_MARKERS)


_CAMINHO_CANONICO = ("apps", "steam", "valve", "software")


def e_a_arvore_canonica(pilha: Sequence[str]) -> bool:
    """A posição atual do parser é ``…/Software/Valve/Steam/apps/<appid>``?

    ARVORE-ERRADA-01 (16/08/2026). O `localconfig.vdf` dela tem **três** blocos
    chamados `apps`, e só um deles é o que a Steam consulta::

        UserLocalConfigStore/Software/Valve/Steam/apps   63 jogos  <- este
        UserLocalConfigStore/apps                        11 jogos
        UserLocalConfigStore/WebStorage/apps              3 jogos

    O leitor e o escritor deste módulo conferiam só o pai imediato
    (``stack[-2] == "apps"``), então os três valiam. As consequências, as duas
    medidas na mesma noite:

    1. **O escritor sujou.** Os 11 blocos de ``UserLocalConfigStore/apps`` são
       da Steam (guardam `UseSteamControllerConfig` e `SteamControllerRumble`);
       recebendo um `LaunchOptions` nosso, ganharam uma chave que ninguém lê.
       Inócuo, mas é escrever em arquivo de outro dono sem saber onde.
    2. **O leitor MENTIU, e essa é a cara.** Um appid presente nas duas árvores
       era lido duas vezes, e o dicionário guardava o ÚLTIMO — a árvore errada,
       que vem depois no arquivo. O PRAGMATA estava assim: sem o wrapper na
       árvore canônica (o ``VKD3D_CONFIG=no_upload_hvv`` dela o havia comido de
       novo) e com o wrapper na outra. O `censo_do_wrapper` respondeu
       **"faltantes: 0"** com o defeito vivo, e o jogo do usuário sem reconhecer o
       controle no rádio.

    É a família do `WRAPPER-EM-TODOS-01`: o portão que passa verde porque olha
    para o lugar errado é pior que portão nenhum, porque encerra a busca.

    A âncora é por SUFIXO, não pelo caminho inteiro, para não depender do nome
    da raiz (`UserLocalConfigStore` aqui; outras contas de Steam já foram vistas
    com outro) — o que se exige é que `apps` esteja pendurado em
    `Software/Valve/Steam`.
    """
    if len(pilha) < len(_CAMINHO_CANONICO):
        return False
    return all(
        pilha[-1 - i].lower() == esperado
        for i, esperado in enumerate(_CAMINHO_CANONICO)
    )


def read_apps_by_appid(text: str) -> dict[str, str | None]:
    """Mapeia appid → LaunchOptions de um localconfig.vdf, **incluindo os apps"""
    out: dict[str, str | None] = {}
    stack: list[str] = []
    pending: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "{":
            stack.append(pending if pending is not None else "")
            pending = None
            if stack[-1].isdigit() and e_a_arvore_canonica(stack[:-1]):
                out.setdefault(stack[-1], None)
            continue
        if line == "}":
            if stack:
                stack.pop()
            pending = None
            continue
        pair = _VDF_PAIR_RE.match(line)
        if pair is not None:
            pending = None
            if _vdf_unescape(pair.group("key")).lower() != "launchoptions":
                continue
            if not stack or not e_a_arvore_canonica(stack[:-1]):
                continue
            appid = stack[-1]
            if appid.isdigit():
                out[appid] = _vdf_unescape(pair.group("value"))
            continue
        key_only = _VDF_KEY_ONLY_RE.match(line)
        if key_only is not None:
            pending = _vdf_unescape(key_only.group("key"))
    return out


def read_launch_options_by_appid(text: str) -> dict[str, str]:
    """Mapeia appid → LaunchOptions (desescapado) — só os apps que TÊM a linha."""
    return {a: v for a, v in read_apps_by_appid(text).items() if v is not None}


def apply_wrapper_vdf_text(
    text: str, *, excluir: Sequence[str] | None = None
) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Aplica o wrapper a todos os jogos da árvore CANÔNICA de UM vdf (puro).

    "Canônica" é literal e é âncora de caminho: só
    ``…/Software/Valve/Steam/apps/<appid>``. As outras árvores `apps` do mesmo
    arquivo pertencem à Steam e não são lidas para `LaunchOptions` — escrever
    nelas é sujar arquivo de outro dono à toa. Ver `e_a_arvore_canonica`.

    PATH-06 item 2: a via em-massa consentida. Diferente de ``transform_vdf_text``
    (que só toca linhas já NOSSAS), aqui todo app do vdf entra:

    - app COM LaunchOptions: prefixa via ``migrate_value`` (preserva as opções
      do usuário; remove veneno legado se houver). Já chama o wrapper => skip
      (idempotente). Lista de IGNORE estendida => skip honesto (mexer quebraria
      o launch — mesma regra do migrate).
    - app SEM a linha LaunchOptions: insere ``"LaunchOptions" "<wrapper>"`` no
      fim do bloco do app, com a indentação dos vizinhos.

    ``excluir``: appids que a USUÁRIA marcou como "não quero o wrapper neste
    jogo" (SENTINELA-WRAPPER-01). Saem com o motivo ``opt_out_da_usuaria`` e
    nada é escrito neles — o produto não briga com a dona da máquina. (Quem
    TIRA o atalho que eles já têm é o `tirar_o_atalho_dos_jogos`, chamado pelo
    reparo do vigia desde 21/09/2026; aqui só se pula.) A lista
    vem do `jogos_sem_wrapper.txt`; ``None`` significa "não excluir ninguém"
    (o comportamento histórico), nunca "leia o arquivo real" — quem lê o
    arquivo é o chamador, para esta função continuar pura.

    Retorna ``(texto_novo, appids_aplicados, [(appid, motivo_skip), ...])``.
    O parse de blocos é o MESMO do ``read_launch_options_by_appid`` (pilha por
    linha); conteúdo fora do padrão passa intacto byte a byte.
    """
    fora = {str(a).strip() for a in (excluir or ())}
    lines = text.splitlines(keepends=True)
    applied: list[str] = []
    skipped: list[tuple[str, str]] = []
    replacements: dict[int, str] = {}
    insertions: list[tuple[int, str]] = []

    stack: list[str] = []
    pending: str | None = None
    frame: tuple[str, int, int, int | None] | None = None
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if line == "{":
            stack.append(pending if pending is not None else "")
            pending = None
            if (
                frame is None
                and stack[-1].isdigit()
                and e_a_arvore_canonica(stack[:-1])
            ):
                frame = (stack[-1], len(stack), idx, None)
            continue
        if line == "}":
            if frame is not None and len(stack) == frame[1]:
                appid, _, open_idx, lo_idx = frame
                if lo_idx is None and appid in fora:
                    skipped.append((appid, "opt_out_da_usuaria"))
                elif lo_idx is None:
                    body = lines[open_idx].rstrip("\r\n")
                    eol = lines[open_idx][len(body):] or "\n"
                    indent = body[: len(body) - len(body.lstrip())] + "\t"
                    insertions.append((
                        idx,
                        f'{indent}"LaunchOptions"\t\t'
                        f'"{_vdf_escape(WRAPPER_LAUNCH)}"{eol}',
                    ))
                    applied.append(appid)
                frame = None
            if stack:
                stack.pop()
            pending = None
            continue
        pair = _VDF_PAIR_RE.match(line)
        if pair is not None:
            pending = None
            if (
                frame is None
                or len(stack) != frame[1]
                or _vdf_unescape(pair.group("key")).lower() != "launchoptions"
            ):
                continue
            appid = frame[0]
            frame = (appid, frame[1], frame[2], idx)
            value = _vdf_unescape(pair.group("value"))
            if appid in fora:
                skipped.append((appid, "opt_out_da_usuaria"))
                continue
            if has_extended_ignore(value):
                skipped.append((appid, "ignore_estendido"))
                continue
            if WRAPPER_PREFIX in value:
                skipped.append((appid, "ja_tem_wrapper"))
                continue
            new_value = migrate_value(value)
            if new_value == value:
                skipped.append((appid, "ja_tem_wrapper"))
                continue
            body = lines[idx].rstrip("\r\n")
            eol = lines[idx][len(body):]
            m = _LAUNCH_OPTIONS_RE.match(body)
            if m is None:
                skipped.append((appid, "linha_fora_do_padrao"))
                continue
            replacements[idx] = (
                m.group("prefix") + _vdf_escape(new_value) + m.group("suffix") + eol
            )
            applied.append(appid)
            continue
        key_only = _VDF_KEY_ONLY_RE.match(line)
        if key_only is not None:
            pending = _vdf_unescape(key_only.group("key"))

    if not replacements and not insertions:
        return text, applied, skipped
    out: list[str] = []
    insert_by_idx = dict(insertions)
    for idx, raw in enumerate(lines):
        if idx in insert_by_idx:
            out.append(insert_by_idx[idx])
        out.append(replacements.get(idx, raw))
    return "".join(out), applied, skipped


def nao_firmaram(vdf: Path, appids: Sequence[str], *, com_wrapper: bool) -> list[str]:
    """Relê o ``vdf`` do disco e devolve os appids que NÃO ficaram como gravamos.

    CONVERGE PELO ESTADO LIDO (07/10/2026). Gravar com ``tmp.replace`` e dar o jogo por aplicado
    é dar por feito o que ninguém leu de volta: a Steam já apagou o wrapper de um jogo sem aviso
    (memória de 17/09), e o arquivo é do usuário. ``com_wrapper=True`` pergunta quem NÃO tem o wrapper
    na linha; ``False``, quem ainda o tem. Arquivo que não abre devolve todos: sem leitura não há
    prova de que firmou.
    """
    try:
        lidos = read_apps_by_appid(vdf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(appids)
    return [
        a for a in appids
        if (WRAPPER_PREFIX in (lidos.get(a) or "")) != com_wrapper
    ]


def apply_wrapper_to_all_games(
    home: Path | None = None,
    vdfs: list[Path] | None = None,
    *,
    dry_run: bool = False,
    excluir: Sequence[str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Aplica o wrapper a todos os jogos dos localconfig.vdf elegíveis.

    PATH-06 item 2 (a via em-massa consentida do botão "Aplicar aos jogos da
    Steam"): SOMENTE com a Steam fechada (mesmo gate de processo do
    migrate/strip — a Steam viva regrava o vdf ao sair e a edição seria
    perdida; com um JOGO aberto nem se cogita). vdf sandbox (Flatpak/Snap) é
    pulado inteiro: o wrapper do host é invisível lá dentro (DEDUP-04).

    ``excluir``: os appids do `jogos_sem_wrapper.txt` (SENTINELA-WRAPPER-01).
    O `main()` os lê e passa por default — inclusive no passo sem flag do
    install —, para que "não quero o wrapper neste jogo" sobreviva ao próximo
    `./install.sh` em vez de ser desfeito por ele.

    Retorna ``{"applied": [...], "skipped": [...], "errors": [...]}`` — cada
    item é ``{"vdf": ..., "appid": ..., "reason": ...}`` (``reason`` vazio nos
    aplicados). Backups ``.bak.hefesto-launch-<ts>`` ao lado de cada vdf
    tocado, como o ``process_vdf``.
    """
    result: dict[str, list[dict[str, str]]] = {
        "applied": [],
        "skipped": [],
        "errors": [],
    }
    invalidar_varredura_de_proc()
    if not dry_run and steam_game_running():
        result["errors"].append(
            {"vdf": "", "appid": "", "reason": "jogo_da_steam_aberto"}
        )
        return result
    if not dry_run and steam_running():
        result["errors"].append({"vdf": "", "appid": "", "reason": "steam_aberta"})
        return result
    for vdf in vdfs if vdfs is not None else discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            result["skipped"].append(
                {"vdf": str(vdf), "appid": "", "reason": "sandbox"}
            )
            continue
        try:
            original = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            result["errors"].append(
                {"vdf": str(vdf), "appid": "", "reason": str(exc)}
            )
            continue
        new_text, applied, skipped = apply_wrapper_vdf_text(original, excluir=excluir)
        for appid, reason in skipped:
            result["skipped"].append(
                {"vdf": str(vdf), "appid": appid, "reason": reason}
            )
        if not applied:
            continue
        if not dry_run:
            try:
                backup = vdf.with_name(
                    vdf.name + f".bak.hefesto-launch-{int(time.time())}"
                )
                shutil.copy2(vdf, backup)
                tmp = vdf.with_name(vdf.name + ".hefesto-tmp")
                tmp.write_text(new_text, encoding="utf-8")
                shutil.copymode(vdf, tmp)
                tmp.replace(vdf)
            except OSError as exc:
                result["errors"].append(
                    {"vdf": str(vdf), "appid": "", "reason": str(exc)}
                )
                continue
        if not dry_run:
            soltos = set(nao_firmaram(vdf, applied, com_wrapper=True))
            for appid in applied:
                if appid in soltos:
                    result["errors"].append(
                        {"vdf": str(vdf), "appid": appid, "reason": MOTIVO_NAO_FIRMOU}
                    )
            applied = [a for a in applied if a not in soltos]
        for appid in applied:
            result["applied"].append({"vdf": str(vdf), "appid": appid, "reason": ""})
    return result


def tirar_o_atalho_dos_jogos(
    appids: Sequence[str],
    home: Path | None = None,
    vdfs: list[Path] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, list[dict[str, str]]]:
    """Tira o NOSSO trecho da `LaunchOptions` destes jogos, e só deles.

    OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01, 21/09/2026 (§11.2). Até
    aqui o atalho só saía em massa (``--strip``, o do desinstalar), e a lista
    `jogos_sem_wrapper.txt` só fazia o jogo ser PULADO: um jogo que já tinha o
    atalho continuava com ele depois de entrar na lista. Excluir um jogo do
    Hefesto tem de tirar o que ele já tem.

    Tira o que o ``strip`` tira — o wrapper e o veneno legado —, preserva as
    opções dela na mesma linha byte a byte (``strip_value``) e só toca o bloco
    destes appids, em todas as árvores. Os portões são os do
    ``apply_wrapper_to_all_games``, na mesma ordem: jogo aberto, depois Steam
    aberta — a Steam viva regrava o vdf ao sair e engoliria a edição.

    Retorna ``{"removed": [...], "skipped": [...], "errors": [...]}``, cada
    item ``{"vdf", "appid", "reason"}``. Backup ``.bak.hefesto-launch-<ts>``
    ao lado de cada vdf tocado. Nunca levanta.
    """
    result: dict[str, list[dict[str, str]]] = {
        "removed": [],
        "skipped": [],
        "errors": [],
    }
    alvo = {str(a).strip() for a in appids if str(a).strip()}
    if not alvo:
        return result
    invalidar_varredura_de_proc()
    if not dry_run and steam_game_running():
        result["errors"].append(
            {"vdf": "", "appid": "", "reason": "jogo_da_steam_aberto"}
        )
        return result
    if not dry_run and steam_running():
        result["errors"].append({"vdf": "", "appid": "", "reason": "steam_aberta"})
        return result
    for vdf in vdfs if vdfs is not None else discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            result["skipped"].append(
                {"vdf": str(vdf), "appid": "", "reason": "sandbox"}
            )
            continue
        try:
            original = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            result["errors"].append(
                {"vdf": str(vdf), "appid": "", "reason": str(exc)}
            )
            continue
        novo, mudadas = transform_vdf_text(original, "strip", so_os_jogos=alvo)
        if mudadas == 0:
            continue
        antes = read_apps_by_appid(original)
        depois = read_apps_by_appid(novo)
        tirados = sorted(a for a in alvo if antes.get(a) != depois.get(a))
        if not dry_run:
            try:
                backup = vdf.with_name(
                    vdf.name + f".bak.hefesto-launch-{int(time.time())}"
                )
                shutil.copy2(vdf, backup)
                tmp = vdf.with_name(vdf.name + ".hefesto-tmp")
                tmp.write_text(novo, encoding="utf-8")
                shutil.copymode(vdf, tmp)
                tmp.replace(vdf)
            except OSError as exc:
                result["errors"].append(
                    {"vdf": str(vdf), "appid": "", "reason": str(exc)}
                )
                continue
        if not dry_run:
            soltos = set(nao_firmaram(vdf, tirados, com_wrapper=False))
            for appid in tirados:
                if appid in soltos:
                    result["errors"].append(
                        {"vdf": str(vdf), "appid": appid, "reason": MOTIVO_NAO_FIRMOU}
                    )
            tirados = [a for a in tirados if a not in soltos]
        for appid in tirados:
            result["removed"].append({"vdf": str(vdf), "appid": appid, "reason": ""})
    return result


PROC = Path("/proc")

_PASTAS_DO_CLIENTE = frozenset({"ubuntu12_32", "steamrt64"})


@dataclass(frozen=True)
class ProcessoDaSteam:
    """Um processo da Steam deste usuário."""

    pid: int
    papel: str
    lar: str
    inicio: str


def _texto(arquivo: Path) -> str:
    try:
        return arquivo.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def _uid_real(pasta: Path) -> int | None:
    for linha in _texto(pasta / "status").splitlines():
        if linha.startswith("Uid:"):
            campos = linha.split()
            return int(campos[1]) if len(campos) > 1 and campos[1].isdigit() else None
    return None


def _inicio(pasta: Path) -> str:
    stat_ = _texto(pasta / "stat")
    depois = stat_.rpartition(")")[2].split()
    return depois[19] if len(depois) > 19 else ""


_MARCAS_DO_LAR = ("/.var/app/", "/snap/", "/.steam/", "/.local/share/Steam/")


def _lar_pelo_binario(pasta: Path, argv: list[str]) -> str:
    """O lar pela pasta do binário (`<lar>/.steam/…/steamwebhelper`); ``""`` = não se sabe."""
    caminho = argv[0] if argv and argv[0].startswith("/") else ""
    if not caminho:
        try:
            caminho = os.readlink(pasta / "exe")
        except OSError:
            return ""
    for marca in _MARCAS_DO_LAR:
        antes, achou, _ = caminho.partition(marca)
        if achou and antes.startswith("/"):
            return antes
    return ""


def _lar_do_processo(pasta: Path) -> str:
    """O `HOME` do processo; ``""`` = não se sabe."""
    for item in _texto(pasta / "environ").split("\0"):
        if item.startswith("HOME="):
            return item[5:]
    return _lar_pelo_binario(
        pasta, [a for a in _texto(pasta / "cmdline").split("\0") if a])


def processos_da_steam(proc: Path = PROC) -> list[ProcessoDaSteam]:
    """O cliente e os webhelpers da Steam DESTE usuário, com o `HOME` de cada um."""
    uid = os.getuid()
    achados: dict[int, ProcessoDaSteam] = {}
    referidos: set[int] = set()
    dono_do_webhelper: dict[int, int] = {}
    try:
        pastas = [x for x in proc.iterdir() if x.name.isdigit()]
    except OSError:
        return []
    for pasta in pastas:
        if _uid_real(pasta) != uid:
            continue
        comm = _texto(pasta / "comm").strip()
        argv = [a for a in _texto(pasta / "cmdline").split("\0") if a]
        if comm == "steamwebhelper":
            papel = "webhelper"
            donos = [int(a.split("=", 1)[1]) for a in argv
                     if a.startswith("-steampid=") and a.split("=", 1)[1].isdigit()]
            referidos.update(donos)
            if donos:
                dono_do_webhelper[int(pasta.name)] = donos[0]
        elif comm == "steam" and argv and Path(argv[0]).parent.name in _PASTAS_DO_CLIENTE:
            papel = "cliente"
        else:
            continue
        achados[int(pasta.name)] = ProcessoDaSteam(
            int(pasta.name), papel, _lar_do_processo(pasta), _inicio(pasta))
    for pid in referidos - set(achados):
        pasta = proc / str(pid)
        if _uid_real(pasta) == uid and _texto(pasta / "comm").strip() == "steam":
            achados[pid] = ProcessoDaSteam(pid, "cliente", _lar_do_processo(pasta),
                                           _inicio(pasta))
    for pid, cliente in dono_do_webhelper.items():
        dele = achados.get(cliente)
        if dele is not None and dele.lar and not achados[pid].lar:
            achados[pid] = replace(achados[pid], lar=dele.lar)
    return sorted(achados.values(), key=lambda x: (x.papel != "cliente", x.pid))


def do_meu_lar(lar_do_processo: str, lar: Path | None = None) -> bool:
    """O `HOME` deste processo é o de quem pergunta (ou fica dentro dele)?"""
    if not lar_do_processo:
        return False
    meu = Path.home() if lar is None else lar
    try:
        dele, meu = Path(lar_do_processo).resolve(), meu.resolve()
    except OSError:  # pragma: no cover - caminho impossível
        return False
    return dele == meu or meu in dele.parents


def e_deste_lar(pid: int, proc: Path = PROC, lar: Path | None = None) -> bool:
    """Este processo é deste usuário e deste `HOME`? — a conferência antes do sinal."""
    pasta = proc / str(pid)
    if _uid_real(pasta) != os.getuid():
        return False
    dele = _lar_do_processo(pasta) or next(
        (x.lar for x in processos_da_steam(proc) if x.pid == pid), "")
    return do_meu_lar(dele, lar) if dele else True


def steam_deste_lar(proc: Path = PROC, lar: Path | None = None) -> list[ProcessoDaSteam]:
    """Os processos da Steam do `HOME` de quem pergunta — os que levam sinal."""
    return [x for x in processos_da_steam(proc) if do_meu_lar(x.lar, lar)]


def steam_de_pe(proc: Path = PROC, lar: Path | None = None) -> bool:
    """Há Steam de pé para quem pergunta? A deste lar, ou uma cujo lar não se lê."""
    return any(not x.lar or do_meu_lar(x.lar, lar) for x in processos_da_steam(proc))


def steam_running() -> bool:
    """A Steam DESTE lar está aberta? O cliente, ou o webhelper que ele pôs de pé.

    É A PERGUNTA SÓ, e todos a fazem: o `stop_steam`, o `with_steam_closed`
    (que decide se reabre), o «abrir ou focar» e o «Reiniciar o serviço». O
    `disable_steam_input.sh` tem a dele, em shell.
    """
    return steam_de_pe()


_STEAM_LAUNCH_RE = re.compile(r"SteamLaunch AppId=\d")

_STEAM_LAUNCH_APPID_RE = re.compile(r"SteamLaunch AppId=\d+")

_TOKEN_DO_INSTALL_SCRIPT = "Install=1"


def e_avaliador_do_install_script(cmd: str) -> bool:
    """A cmdline é o avaliador do install script da Steam, e não um jogo?"""
    achado = _STEAM_LAUNCH_APPID_RE.search(cmd)
    if achado is None:
        return False
    argumentos_do_reaper = cmd[achado.end():].split(" -- ", 1)[0]
    return _TOKEN_DO_INSTALL_SCRIPT in argumentos_do_reaper.split()

VALIDADE_DA_VARREDURA_S: float = 5.0

_ultima_varredura: tuple[float, int | None] | None = None

TETO_DO_NEGATIVO_DE_EXIBICAO_S: float = 60.0

_marcador_do_negativo: tuple[float, object] | None = None


def _agora() -> float:
    """O relógio da foto (`time.monotonic`); costura de teste das duas perguntas."""
    return time.monotonic()


def _o_dono_do_evento_armado() -> bool:
    """O dono do evento do processo está armado? False no modo avulso."""
    try:
        from hefesto_dualsense4unix.core.o_dono_do_evento import armado
    except ImportError:
        return False
    return armado()


def _assinatura_do_marcador() -> object:
    """A assinatura do `stat` do marker `last_run`; None se não se sabe."""
    try:
        from hefesto_dualsense4unix.daemon.launch_env import (
            assinatura_do_ultimo_lancamento,
        )
    except ImportError:
        return None
    try:
        return assinatura_do_ultimo_lancamento()
    except OSError:
        return None


def invalidar_varredura_de_proc() -> None:
    """Joga fora a foto da varredura: a próxima pergunta varre `/proc` de novo."""
    global _ultima_varredura
    _ultima_varredura = None


def cmdline_de_pid(pid: str | int) -> str:
    """Cmdline de um pid, com os NUL virando espaço. `""` se não der para ler."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read().decode("utf-8", "replace").replace("\0", " ")
    except OSError:
        return ""


_cmdline_of = cmdline_de_pid


def _steam_launch_cmdline(
    *, agora: float | None = None, exibicao: bool = False
) -> str | None:
    """A cmdline do launch da Steam em curso, ou None. Sem forkar nada.

    PERF-PROC-SCAN-01 (12/08/2026). Isto substitui um `pgrep -f` que o daemon
    forkava **a cada 2 segundos, para sempre**. O custo medido do jeito antigo,
    com `strace -c -f` no daemon vivo:

      - 1.287 `openat`/s — o `pgrep` lê CINCO arquivos por processo
        (`status`, `stat`, `cmdline`, `cgroup`, `ctty`) mais um `/proc/uptime`,
        vezes ~425 pids, duas vezes por segundo;
      - 12 `execve` em 5 s, dos quais 10 são LIXO: o `PATH` erra cinco vezes
        (`~/.cargo/bin`, `~/.local/bin`, `/usr/local/sbin`, `/usr/local/bin`,
        `/usr/sbin`) antes de achar o `pgrep` em `/usr/bin`;
      - 912 contextos voluntários/s — mesma ordem de grandeza do applet
        eyedropper que o "Guia — Diagnóstico de lentidão" condenou (1.148/s).

    O mecanismo pelo qual isso morde um jogo é ler `/proc/<pid>/cmdline` de
    TODO processo: cada leitura toma o `mmap_read_lock` do alvo, inclusive o do
    jogo. Honestidade sobre a evidência: o teste de causalidade (SIGSTOP no
    daemon, 12 s, SIGCONT) **não** condenou o daemon — mas rodou sem jogo
    aberto, então ele não absolve também. O que segue é redução de custo com
    semântica idêntica, não uma cura de bug provado.

    QUATRO camadas, nesta ordem (as duas do meio são da BG-03, 25/08/2026):

    1. **Marker do wrapper** — o `hefesto-launch` já grava `appid` e `pid` em
       `launch_env/last_run` justamente para isto. Confirmamos lendo a cmdline
       DESSE pid: se ela casa a agulha E o appid, acabou em 3 `open` (dois do
       marker, um da cmdline). A confirmação é o que elimina o "pid reuse" que o
       NUMA-01 documenta — aqui não precisamos do `last_exit`, porque não
       confiamos no pid sozinho.
    2. **Reconfirmação do pid que a última varredura achou** — mesmo truque da
       camada 1, para o jogo que NÃO veio pelo wrapper: um `open` na cmdline
       daquele pid. **Isto nunca devolve resposta velha** — se o pid morreu ou
       foi reusado, a agulha não casa e caímos adiante. É a camada que apaga a
       varredura completa enquanto um jogo fora do wrapper está aberto, que é
       justo o caso em que a varredura toma o `mmap_read_lock` DO JOGO.
    3. **Negativo ainda fresco** — varreu há menos de
       `VALIDADE_DA_VARREDURA_S` e não achou nada: devolve None sem varrer de
       novo. É o estado permanente de um daemon 24/7 (jogo fechado).
    4. **Varredura em Python** — quando nenhuma das três resolveu, varremos
       `/proc` lendo UM arquivo por pid em vez de cinco, e sem `fork`/`execve`.

    Números honestos, medidos nesta máquina (auditoria de 12/08/2026 corrigiu a
    versão anterior desta frase, que anunciava o melhor caso como se fosse o
    comum):

      - **Jogo aberto pelo wrapper**: ~3 `openat` por tique (era ~1.287).
      - **Estado permanente de um daemon 24/7, ou seja jogo FECHADO**: o marker
        é global e sobrevive ao jogo, então o pid dele está morto, o caminho
        rápido falha e caímos na varredura — **400 `openat`, 4,2 ms por tique**.
        Contra os ~2.100 do `pgrep`, ainda é ~5x menos, e sem `fork`/`execve`.
        **A camada 3 divide esse resto por ~3** (a varredura passa a sair a
        cada 5 s em vez de a cada 2 s, e o poll loop faz DUAS perguntas por
        tique — a segunda deixa de custar qualquer coisa).
      - **Jogo aberto FORA do wrapper**: era a varredura completa a cada tique;
        com a camada 2 passa a ser **1 `openat`** — o do próprio jogo.

    **O preço da camada 3, dito antes que alguém descubra do jeito caro:** um
    jogo lançado **fora** do wrapper pode demorar até `VALIDADE_DA_VARREDURA_S`
    para ser notado. Pelo wrapper (o caminho normal) não há atraso nenhum: a
    camada 1 vê o marker no primeiro tique, sem tocar na foto.

    Onde a resposta guarda um gesto destrutivo — `steam -shutdown` com jogo
    aberto MATA o jogo — o chamador tem de gastar `invalidar_varredura_de_proc()`
    antes de perguntar: um `openat` a mais num clique não se compara a fechar um
    jogo do usuário. **Os três caminhos DESTE módulo já gastam** (`--apply` da CLI,
    `apply_wrapper_to_all_games`, `with_steam_closed`). **Quatro caminhos FORA
    dele ainda não**, e é dívida declarada da BG-03, não descuido:
    `proton_pin._steam_gate`, `app/actions/daemon_actions.py`,
    `app/actions/emulation_actions.py` e `app/actions/carona_do_wrapper.py` —
    os quatro tinham dono em outra árvore em 25/08/2026, e R1 manda relatar em
    vez de editar.

    O retorno é a cmdline crua para o chamador extrair o que quiser — é o que
    permite `steam_game_running` e `steam_game_running_appid` compartilharem uma
    varredura só, e é por isso que ambas enxergam exatamente o mesmo processo.

    `exibicao` é a pergunta de quem MOSTRA (O-REPOUSO-ESPERA-O-EVENTO-01,
    família 4): com o dono do evento armado, o negativo vale até
    `TETO_DO_NEGATIVO_DE_EXIBICAO_S` enquanto o marker do lançamento não mudar.
    Sem o dono (a janela, a CLI, o modo avulso), a camada 3 de sempre.
    """
    global _ultima_varredura, _marcador_do_negativo
    try:
        from hefesto_dualsense4unix.daemon.launch_env import (
            read_last_run_marker,
            read_last_run_pid,
        )

        marker = read_last_run_marker()
        pid = read_last_run_pid()
    except (ImportError, OSError):
        marker = None
        pid = None

    if marker is not None and pid is not None:
        appid = marker[0]
        cmd = _cmdline_of(pid)
        if _STEAM_LAUNCH_RE.search(cmd) and re.search(rf"AppId={appid}\b", cmd):
            return cmd

    agora = _agora() if agora is None else float(agora)
    foto = _ultima_varredura

    if foto is not None and foto[1] is not None:
        cmd = _cmdline_of(foto[1])
        if _STEAM_LAUNCH_RE.search(cmd):
            if not e_avaliador_do_install_script(cmd):
                return cmd
            foto = None
        else:
            _ultima_varredura = foto = (foto[0], None)

    if foto is not None and (agora - foto[0]) < VALIDADE_DA_VARREDURA_S:
        return None
    armado = _o_dono_do_evento_armado()
    if (
        exibicao
        and armado
        and foto is not None
        and foto[1] is None
        and (agora - foto[0]) < TETO_DO_NEGATIVO_DE_EXIBICAO_S
    ):
        guardado = _marcador_do_negativo
        if (
            guardado is not None
            and guardado[0] == foto[0]
            and guardado[1] == _assinatura_do_marcador()
        ):
            return None

    marcador_antes = _assinatura_do_marcador() if armado else None
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    avaliador: tuple[int, str] | None = None
    for entry in entries:
        if not entry.isdigit():
            continue
        cmd = _cmdline_of(entry)
        if not _STEAM_LAUNCH_RE.search(cmd):
            continue
        if e_avaliador_do_install_script(cmd):
            if avaliador is None:
                avaliador = (int(entry), cmd)
            continue
        _ultima_varredura = (agora, int(entry))
        return cmd
    if avaliador is not None:
        _ultima_varredura = (agora, avaliador[0])
        return avaliador[1]
    _ultima_varredura = (agora, None)
    if armado:
        _marcador_do_negativo = (agora, marcador_antes)
    return None


def steam_game_running() -> bool:
    """True quando há um JOGO da Steam em execução (não só a Steam)."""
    return _steam_launch_cmdline() is not None


def steam_game_running_appid() -> int | None:
    """O appid do jogo da Steam em execução, ou None."""
    cmd = _steam_launch_cmdline(exibicao=True)
    if cmd is None or e_avaliador_do_install_script(cmd):
        return None
    achado = re.search(r"SteamLaunch AppId=(\d+)", cmd)
    return int(achado.group(1)) if achado else None


def stop_steam(
    *,
    proc: Path | None = None,
    lar: Path | None = None,
    dormir: Callable[[float], None] | None = None,
    sinalizar: Callable[[int, int], None] | None = None,
) -> bool:
    """Fecha a Steam DESTE lar. True = nenhum processo dela de pé."""
    pasta = PROC if proc is None else proc
    esperar = time.sleep if dormir is None else dormir
    tiro = os.kill if sinalizar is None else sinalizar

    def de_pe() -> bool:
        if proc is None and lar is None:
            return steam_running()
        return steam_de_pe(pasta, lar)

    if not de_pe():
        return True
    if shutil.which("steam") is not None:
        subprocess.Popen(
            ["steam", "-shutdown"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=ambiente_limpo(os.environ),
        )
        for _ in range(15):
            esperar(2)
            if not de_pe():
                break
    if de_pe():
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for alvo in steam_deste_lar(pasta, lar):
                if _inicio(pasta / str(alvo.pid)) != alvo.inicio:
                    continue
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    tiro(alvo.pid, sig)
            esperar(3)
            if not de_pe():
                break
    esperar(2)
    return not de_pe()


#: Quanto esperar a Steam aparecer de pé depois do pedido de reabrir, e o passo da conferência.
ESPERA_DA_STEAM_S: float = 15.0
PASSO_DA_STEAM_S: float = 0.5

#: As portas de reabrir, na ordem: o binário e a URL ``steam://`` (a que o `.desktop` da Flatpak e
#: da Snap registra). Cada uma só vale o que o estado lido diz: a Steam de pé.
_PORTAS_DE_REABRIR: tuple[tuple[str, ...], ...] = (
    ("steam",),
    ("xdg-open", "steam://open/main"),
)


def ha_porta_de_reabrir() -> bool:
    """Esta máquina tem alguma porta de reabrir a Steam no PATH (o `steam` ou o `xdg-open`)?

    Separa as duas razões de o ``reopen_steam`` devolver ``False``: não haver porta nenhuma, e
    a porta existir e a Steam não ter ficado de pé no tempo da conferência.
    """
    return any(shutil.which(cmd[0]) is not None for cmd in _PORTAS_DE_REABRIR)


def reopen_steam(
    *,
    de_pe: Callable[[], bool] | None = None,
    dormir: Callable[[float], None] | None = None,
    espera_s: float = ESPERA_DA_STEAM_S,
) -> bool:
    """Reabre a Steam desanexada e CONFERE que ela voltou. True = a Steam está de pé.

    CONVERGE PELO ESTADO LIDO (07/10/2026, A-STEAM-E-OS-LANCADORES-SEM-ARQUIVO-INTERNO-01).
    Até aqui o retorno dizia só que o PEDIDO saiu: o ``Popen`` do ``steam`` ou do ``xdg-open``
    voltava ``True`` e ninguém olhava se a Steam subiu. Agora cada porta é seguida da pergunta
    que o ``stop_steam`` já faz (a Steam deste lar está de pé?), e a porta seguinte só é
    tentada quando a anterior não levantou a Steam dentro de ``espera_s``. Com a Steam já de
    pé o pedido é repassado a ela e a conferência responde na hora.

    AMBIENTE-PRESUMIDO-01 (23/08/2026): isto exigia o binário ``steam`` no
    PATH e, quando não achava, voltava MUDO. Quem instalou a Steam pela
    Flatpak ou pela Snap não tem esse binário — então `with_steam_closed`
    fechava a Steam do usuário, fazia o trabalho, e a deixava fechada sem uma
    palavra. O fallback é a URL `steam://` pelo `xdg-open`, que é ela que o
    `.desktop` da Flatpak/Snap registra.

    Sobra um caso sem voz — nem ``steam`` nem ``xdg-open`` no PATH —, e é por
    isso que o retorno é `bool`: os três chamadores de `with_steam_closed`
    ainda o ignoram, e enquanto ignorarem a Steam pode ficar fechada sem uma
    palavra na tela. Fechar esse último palmo é mudar o contrato de
    `with_steam_closed`, que mora em `app/actions/daemon_actions.py` também.

    AMBIENTE-DO-JOGO-01 (18/09/2026): o install chama isto de dentro do
    terminal da pessoa (`--migrate/--apply --stop-steam`), e a Steam reaberta
    herdava daquele terminal a venv, o conda ou o pyenv ativo — e todo jogo da
    sessão com ela. Ela nasce agora com `ambiente_limpo`, que tira só essa
    classe e deixa a tela e o barramento de sessão como estão.

    STEAM-FORA-DO-SERVICO-01 (26/09/2026): e nasce por
    `fora_do_servico.abrir` — de dentro de um serviço (a bandeja do autostart
    é um), numa unidade própria; do terminal ou do painel, pelo `Popen`.

    COM A STEAM DESTE LAR DE PÉ, O PEDIDO VAI A ELA (01/10/2026): o `steam`
    repassa à instância viva, que se mostra, e sai sem abrir outra. É o
    «Abrir o lançador» do cartão da Steam com ela na bandeja, e é a mesma
    decisão do PS da bandeja (`steam_launcher.open_or_focus_steam`). Quem
    decide SE reabre é quem fechou (`with_steam_closed`, pelo `steam_running`).
    """
    de_pe_agora = steam_running if de_pe is None else de_pe
    esperar = time.sleep if dormir is None else dormir
    for cmd in _PORTAS_DE_REABRIR:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            fora_do_servico.abrir(
                list(cmd), env=ambiente_limpo(os.environ), popen=subprocess.Popen
            )
        except (OSError, subprocess.SubprocessError):
            continue
        for _ in range(max(1, int(espera_s / PASSO_DA_STEAM_S))):
            if de_pe_agora():
                return True
            esperar(PASSO_DA_STEAM_S)
        if de_pe_agora():
            return True
    return False


#: Status possíveis de `with_steam_closed` — contrato do chamador (a GUI faz
STEAM_JANELA_OK = "ok"
STEAM_JANELA_JOGO_ABERTO = "jogo_aberto"
STEAM_JANELA_NAO_FECHOU = "nao_fechou"


def with_steam_closed(
    tarefa: Callable[[], Any], *, reopen: bool = True
) -> tuple[str, Any]:
    """Roda `tarefa()` com a Steam garantidamente FECHADA e a reabre depois."""
    invalidar_varredura_de_proc()
    if steam_game_running():
        return STEAM_JANELA_JOGO_ABERTO, None
    estava_rodando = steam_running()
    if estava_rodando and not stop_steam():
        return STEAM_JANELA_NAO_FECHOU, None
    try:
        return STEAM_JANELA_OK, tarefa()
    finally:
        if estava_rodando and reopen:
            reopen_steam()


STEAM_INPUT_ALLOWLIST_RELPATH = "hefesto-dualsense4unix/steam_input_apps.txt"

_ALLOWLIST_HEADER = """\
# hefesto-dualsense4unix — allowlist do Steam Input per-app
# (STEAM-INPUT-ALLOWLIST-01)
#
# AppIDs listados aqui NÃO têm o "UseSteamControllerConfig" revertido pelo
# guard (disable_steam_input.sh), e o Hefesto NÃO esconde o controle físico
# destes jogos. Use para jogos cuja via oficial de DualSense é o Steam Input.
# Uma linha por AppID; '#' comenta.
"""


def steam_input_allowlist_path(config_home: Path | None = None) -> Path:
    """Caminho do `steam_input_apps.txt` (XDG), sem tocar no disco."""
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / STEAM_INPUT_ALLOWLIST_RELPATH


def parse_steam_input_allowlist(text: str) -> list[str]:
    """AppIDs de um conteúdo de allowlist (uma linha por id; `#` comenta)."""
    out: list[str] = []
    for linha in text.splitlines():
        token = linha.split("#", 1)[0].strip()
        if token and token not in out:
            out.append(token)
    return out


_PAR_ACF = re.compile(r'^\s*"(?P<chave>[^"]+)"\s+"(?P<valor>.*)"\s*$')


def _desescapar_acf(valor: str) -> str:
    """Desfaz o escape de VDF (`\\\\` e `\\"`) — mesmo critério do proton_pin."""
    return valor.replace('\\\\', '\\').replace('\\"', '"')


def _real(caminho: Path) -> Path:
    """O diretório de verdade. Link ilegível vale por si mesmo."""
    try:
        return caminho.resolve()
    except OSError:  # pragma: no cover - link quebrado ou permissão
        return caminho


def raizes_de_jogos(home: Path | None = None) -> list[Path]:
    """TODA raiz de Steam que EXISTE neste HOME — nativa, Flatpak e Snap."""
    base = home or Path.home()
    achadas: list[Path] = []
    vistas: set[Path] = set()
    for relativo in RAIZES_STEAM_RELATIVAS:
        caminho = base / relativo
        if not caminho.is_dir():
            continue
        real = _real(caminho)
        if real in vistas:
            continue
        vistas.add(real)
        achadas.append(caminho)
    return achadas


def pastas_steamapps(home: Path | None = None) -> list[Path]:
    """A `steamapps` de CADA raiz de Steam mais as bibliotecas do `libraryfolders.vdf`."""
    try:
        from .proton_pin import default_steam_root
    except ImportError:  # pragma: no cover - executado como script avulso
        from proton_pin import default_steam_root  # type: ignore[no-redef]

    raizes = raizes_de_jogos(home)
    if not raizes:
        raizes = [default_steam_root(home)]
    pastas: list[Path] = []
    vistas: set[Path] = set()
    for raiz in raizes:
        base_apps = raiz / "steamapps"
        if _real(base_apps) not in vistas:
            pastas.append(base_apps)
            vistas.add(_real(base_apps))
        with contextlib.suppress(OSError):
            texto = (base_apps / "libraryfolders.vdf").read_text(
                encoding="utf-8", errors="replace"
            )
            for linha in texto.splitlines():
                par = _PAR_ACF.match(linha)
                if par is None or par.group("chave").lower() != "path":
                    continue
                candidata = Path(_desescapar_acf(par.group("valor"))) / "steamapps"
                if candidata.is_dir() and _real(candidata) not in vistas:
                    pastas.append(candidata)
                    vistas.add(_real(candidata))
    return pastas


def nome_do_appid(appid: str, home: Path | None = None) -> str | None:
    """Nome do jogo pelo `appmanifest_<appid>.acf`. `None` = não instalado."""
    for steamapps in pastas_steamapps(home):
        manifesto = steamapps / f"appmanifest_{appid}.acf"
        try:
            texto = manifesto.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            par = _PAR_ACF.match(linha)
            if par is not None and par.group("chave").lower() == "name":
                nome = _desescapar_acf(par.group("valor")).strip()
                if nome:
                    return nome
    return None


def rotulo_do_jogo(appid: object, home: Path | None = None) -> str:
    """Como o jogo aparece numa frase de tela: nome quando dá, appid sempre."""
    bruto = str(appid).strip()
    nome = nome_do_appid(bruto, home) if bruto else None
    return f"{nome} (appid {bruto})" if nome else f"appid {bruto}"


def juntar_rotulos(rotulos: Sequence[str]) -> str:
    """`["A", "B", "C"]` -> ``"A, B e C"``. Vazio -> ``""``. Pura (sem disco)."""
    lista = list(rotulos)
    if not lista:
        return ""
    if len(lista) == 1:
        return lista[0]
    return f"{', '.join(lista[:-1])} e {lista[-1]}"


def lista_de_jogos(appids: Sequence[object], home: Path | None = None) -> str:
    """`[a, b, c]` -> ``"Jogo A (appid a), Jogo B (appid b) e ..."``."""
    return juntar_rotulos([rotulo_do_jogo(a, home) for a in appids])


def add_appid_to_steam_input_allowlist(
    appid: int | str,
    *,
    path: Path | None = None,
    nota: str = "",
    cabecalho: str | None = None,
) -> str:
    """Acrescenta um appid à allowlist. Retorna o status para o toast.

    Status: ``"adicionado"`` | ``"ja_estava"`` | ``"appid_invalido"`` |
    ``"erro"``. Nunca levanta — quem chama é um clique de botão.

    Regras (as três armadilhas do arquivo, todas com dono aqui):

    - **duplicata**: o appid já presente devolve ``"ja_estava"`` sem reescrever
      nada (o arquivo é lido por um awk a cada `--apply`; linha repetida não
      quebra, mas o arquivo é da usuária e não vai virar lixão);
    - **comentários**: `#` comenta — a checagem de duplicata ignora comentário,
      então um appid comentado ("desliguei este") é RE-adicionado como linha
      viva em vez de ser considerado presente;
    - **cabeçalho**: preservado byte a byte num arquivo existente (só append);
      escrito do zero apenas quando o arquivo não existe. O parâmetro
      `cabecalho` troca o texto desse cabeçalho — é o que deixa o
      `jogos_sem_wrapper.txt` (SENTINELA-WRAPPER-01) reusar esta escrita, que
      já tem as três armadilhas resolvidas, em vez de clonar o corpo dela.
    """
    alvo = str(appid).strip()
    if not alvo.isdigit():
        return "appid_invalido"
    destino = path if path is not None else steam_input_allowlist_path()
    try:
        try:
            atual = destino.read_text(encoding="utf-8")
        except FileNotFoundError:
            atual = ""
        if alvo in parse_steam_input_allowlist(atual):
            return "ja_estava"
        corpo = (
            (atual if atual.endswith("\n") else atual + "\n")
            if atual
            else (cabecalho if cabecalho is not None else _ALLOWLIST_HEADER)
        )
        if nota:
            corpo += f"# {nota}\n"
        corpo += f"{alvo}\n"
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".hefesto-tmp")
        tmp.write_text(corpo, encoding="utf-8")
        tmp.replace(destino)
        return "adicionado"
    except OSError:
        return "erro"


def remove_appid_from_steam_input_allowlist(
    appid: int | str,
    *,
    path: Path | None = None,
) -> str:
    """Tira um appid da allowlist — o gêmeo do `add`. Status para o toast.

    Status: ``"removido"`` | ``"nao_estava"`` | ``"appid_invalido"`` |
    ``"erro"``. Nunca levanta — quem chama é um clique de botão.

    JOGO-01 (Entrega 3): a allowlist tinha escritor só para um lado. Pôr um jogo
    nela é um clique ("Este jogo não funciona"); tirar exigia abrir
    `~/.config/hefesto-dualsense4unix/steam_input_apps.txt` num editor de texto —
    ou seja, na prática o opt-in era irreversível para quem não mexe em arquivo
    de configuração. E ele PRECISA ser reversível: entrar na allowlist mudou de
    preço com a JOGO-01 (o Hefesto retira o gamepad virtual daquele jogo), então
    um jogo marcado por engano deixa de ter cor, gatilhos e co-op do Hefesto até
    ser desmarcado.

    Regras (espelham as três armadilhas do `add`, pelo avesso):

    - **só linha VIVA conta**: `# 620` é comentário, não presença — appid apenas
      comentado devolve ``"nao_estava"`` (idêntico ao critério de duplicata do
      `add`, que re-adiciona um appid comentado);
    - **comentário inline sai junto**: `620 # marcado pela GUI` é UMA linha cujo
      appid é 620; remover metade dela deixaria lixo sintático;
    - **comentários NÃO são adivinhados**: o `add` escreve a nota como linha `#`
      logo acima do appid, mas o arquivo é dela e pode ter anotações próprias
      (a instalação nasce com um cabeçalho de sete linhas de comentário coladas
      no primeiro appid). Apagar "o comentário de cima" acertaria a nota nossa
      e o cabeçalho dela com a mesma facilidade, então preservamos TUDO: o preço
      é uma nota órfã, que não muda o comportamento de leitor nenhum;
    - **arquivo ausente** é allowlist vazia ⇒ ``"nao_estava"``, sem criar nada
      (criar um arquivo para dizer que ele não tem o appid seria absurdo).

    Escrita atômica pelo mesmo motivo do `add`: o guard (path unit) pode estar
    lendo o arquivo neste instante, e meia leitura viraria allowlist vazia.

    Superfície pendente (a GUI está com outro dono nesta sprint): quem for ligar
    o botão chama esta função no mesmo lugar em que `on_steam_game_broken`
    (`app/actions/daemon_actions.py`) chama `add_appid_to_steam_input_allowlist`
    — inclusive com o mesmo `_recarregar_apos_allowlist` depois, que é o que faz
    a mudança valer sem reiniciar nada (o daemon rematerializa o
    `steam_app_<appid>.env` no `launch_env.refresh`). Falta só o gatilho e a
    frase do toast; a decisão e a escrita moram aqui.
    """
    alvo = str(appid).strip()
    if not alvo.isdigit():
        return "appid_invalido"
    destino = path if path is not None else steam_input_allowlist_path()
    try:
        try:
            atual = destino.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "nao_estava"
        if alvo not in parse_steam_input_allowlist(atual):
            return "nao_estava"
        mantidas = [
            linha
            for linha in atual.splitlines(keepends=True)
            if linha.split("#", 1)[0].strip() != alvo
        ]
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".hefesto-tmp")
        tmp.write_text("".join(mantidas), encoding="utf-8")
        tmp.replace(destino)
        return "removido"
    except OSError:
        return "erro"


SEM_WRAPPER_RELPATH = "hefesto-dualsense4unix/jogos_sem_wrapper.txt"

_SEM_WRAPPER_HEADER = """\
# hefesto-dualsense4unix — jogos que NÃO devem receber o wrapper de launch
# (SENTINELA-WRAPPER-01)
#
# AppIDs listados aqui ficam de fora do "Aplicar aos jogos da Steam", do passo
# sem flag do install e do reparo automático — e o aviso de "este jogo perdeu
# as opções de inicialização" não aparece para eles. O jogo que já tinha o
# atalho o perde quando a Steam fechar; as outras opções da linha ficam.
#
# Um jogo sem o wrapper NÃO recebe as envs do Hefesto: no Bluetooth ele tende
# a não enxergar controle nenhum, com o perfil e a luz seguindo acesos.
# Uma linha por AppID; '#' comenta.
"""


def sem_wrapper_path(config_home: Path | None = None) -> Path:
    """Caminho do `jogos_sem_wrapper.txt` (XDG), sem tocar no disco."""
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / SEM_WRAPPER_RELPATH


def ler_jogos_sem_wrapper(path: Path | None = None) -> list[str]:
    """AppIDs que ela marcou como "não quero o wrapper aqui". Nunca levanta."""
    destino = path if path is not None else sem_wrapper_path()
    try:
        return parse_steam_input_allowlist(destino.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def marcar_jogo_sem_wrapper(
    appid: int | str, *, path: Path | None = None, nota: str = ""
) -> str:
    """"Não quero o wrapper neste jogo" — o botão de recusa da GUI.

    Status: ``"adicionado"`` | ``"ja_estava"`` | ``"appid_invalido"`` |
    ``"erro"``. Mesmas três armadilhas (e mesmas respostas) do
    `add_appid_to_steam_input_allowlist`: duplicata não reescreve nada, appid
    apenas COMENTADO é re-adicionado como linha viva, e o cabeçalho de um
    arquivo existente é preservado byte a byte.
    """
    return add_appid_to_steam_input_allowlist(
        appid,
        path=path if path is not None else sem_wrapper_path(),
        nota=nota,
        cabecalho=_SEM_WRAPPER_HEADER,
    )


def desmarcar_jogo_sem_wrapper(appid: int | str, *, path: Path | None = None) -> str:
    """"Pode pôr o wrapper de volta" — o avesso do `marcar_jogo_sem_wrapper`."""
    return remove_appid_from_steam_input_allowlist(
        appid, path=path if path is not None else sem_wrapper_path()
    )


def process_vdf(vdf: Path, mode: str, *, dry_run: bool = False) -> tuple[int, str]:
    """Transforma UM vdf com backup ao lado. Retorna (linhas alteradas, diff)."""
    original = vdf.read_text(encoding="utf-8")
    new_text, changed = transform_vdf_text(original, mode)
    if changed == 0:
        return 0, ""
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(vdf),
            tofile=f"{vdf} ({mode})",
            n=0,
        )
    )
    if dry_run:
        return changed, diff
    backup = vdf.with_name(vdf.name + f".bak.hefesto-launch-{int(time.time())}")
    shutil.copy2(vdf, backup)
    tmp = vdf.with_name(vdf.name + ".hefesto-tmp")
    tmp.write_text(new_text, encoding="utf-8")
    shutil.copymode(vdf, tmp)
    tmp.replace(vdf)
    _, resto = transform_vdf_text(vdf.read_text(encoding="utf-8"), mode)
    if resto:
        raise OSError(
            f"{MOTIVO_NAO_FIRMOU}: a releitura de {vdf} ainda pede {resto} LaunchOptions "
            "do que acabei de gravar"
        )
    return changed, diff


def _report_status(vdfs: list[Path]) -> int:
    poisoned = 0
    for vdf in vdfs:
        try:
            text = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(f"[launch-options] ERRO lendo {vdf}: {exc}")
            continue
        n_poison = text.count(IGNORE_SIGNATURE)
        n_wrapper = text.count(_vdf_escape(WRAPPER_PREFIX))
        print(f"[launch-options] {vdf}")
        print(f"    veneno estático (IGNORE 0x054c/0x0ce6): {n_poison}")
        print(f"    chamadas do wrapper hefesto-launch:     {n_wrapper}")
        _warn_extended(vdf, text)
        poisoned += n_poison
    if poisoned:
        print(
            "[launch-options] ação sugerida: --migrate (com a Steam fechada) — "
            "troca o veneno pela chamada do wrapper"
        )
    else:
        print("[launch-options] nenhum veneno estático persistido")
    return 0


def _warn_extended(vdf: Path, text: str) -> None:
    """Reporta (sem tocar) o que a subtração do nosso par NÃO alcança."""
    n = count_extended_ignore(text)
    if n:
        print(
            f"[launch-options] ATENÇÃO: {n} LaunchOptions com IGNORE_DEVICES "
            f"numa forma que não sei desmontar em {vdf} — não tocadas de "
            "propósito (remover só o trecho do Hefesto quebraria o launch); "
            "migre manualmente para o wrapper mantendo a sua parte da lista."
        )


#: Motivos de RECUSA do `apply_wrapper_to_all_games` (nada foi tocado) e a
_APPLY_RECUSAS = {
    "jogo_da_steam_aberto": (
        "há um JOGO da Steam em execução — fechar a Steam agora MATARIA o jogo "
        "(progresso não salvo perdido). Feche o jogo e rode de novo."
    ),
    "steam_aberta": (
        "a Steam está aberta — feche-a e rode de novo (ou use --stop-steam). "
        "Não vou editar o vdf agora porque a Steam regrava o arquivo ao sair e "
        "a edição seria perdida (ou pior, corrompida)."
    ),
}


def _report_apply(
    resultado: dict[str, list[dict[str, str]]], *, dry_run: bool
) -> int:
    """Imprime o relatório do `--apply` (estilo do `_report_status`) e dá o rc."""
    for erro in resultado["errors"]:
        motivo = _APPLY_RECUSAS.get(erro["reason"])
        if motivo is not None:
            print(f"[launch-options] ERRO: {motivo}")
            return 3

    aplicados_por_vdf: dict[str, list[str]] = {}
    for item in resultado["applied"]:
        aplicados_por_vdf.setdefault(item["vdf"], []).append(item["appid"])
    pulados_por_vdf: dict[str, list[tuple[str, str]]] = {}
    for item in resultado["skipped"]:
        pulados_por_vdf.setdefault(item["vdf"], []).append(
            (item["appid"], item["reason"])
        )

    for vdf in dict.fromkeys([*aplicados_por_vdf, *pulados_por_vdf]):
        aplicados = aplicados_por_vdf.get(vdf, [])
        pulados = pulados_por_vdf.get(vdf, [])
        print(f"[launch-options] {vdf}")
        verbo = "receberiam" if dry_run else "receberam"
        detalhe = f" ({', '.join(aplicados)})" if aplicados else ""
        print(f"    jogos que {verbo} o wrapper: {len(aplicados)}{detalhe}")
        if pulados:
            dito = ", ".join(
                f"{appid or 'vdf inteiro'}: {motivo}" for appid, motivo in pulados
            )
            print(f"    pulados: {len(pulados)} ({dito})")

    total = len(resultado["applied"])
    if not total:
        print(
            "[launch-options] nada a fazer: nenhum jogo sem a chamada do wrapper"
        )
    elif dry_run:
        print(
            f"[launch-options] --dry-run: {total} jogos receberiam o wrapper "
            "(nada foi escrito)"
        )
    else:
        print(
            f"[launch-options] wrapper aplicado a {total} jogos "
            "(backup .bak.hefesto-launch-<ts> ao lado de cada vdf)"
        )

    rc = 0
    for erro in resultado["errors"]:
        if erro["reason"] == MOTIVO_NAO_FIRMOU:
            print(
                f"[launch-options] ERRO em {erro['vdf']}: o jogo {erro['appid']} não "
                "ficou como gravei (a releitura do arquivo não bate); rode de novo "
                "com a Steam fechada"
            )
        else:
            print(f"[launch-options] ERRO em {erro['vdf']}: {erro['reason']}")
        rc = 1
    return rc


RC_STEAM_FECHADA_AGORA = 0
RC_STEAM_JA_FECHADA = 4
RC_STEAM_NAO_FECHOU = 3


def _fechar_a_steam_uma_vez() -> int:
    """A janela de Steam fechada do install, aberta UMA vez para todos os passos.

    d172d9fb8, item (c) da conferência (18/09/2026). O install fechava e reabria a
    Steam em cada passo que edita os arquivos dela (11, 11b, 11b-bis) — e a
    reabria ANTES do 11b-ter e do 11c. Resultado medido no código: numa máquina
    em que a Steam estava aberta, a sentinela e a trava `--todos` do Proton
    ADIAVAM sempre (rc 3), e nada tentava de novo. Com a janela única, os
    passos rodam com a Steam fechada e ela reabre uma vez, no fim.

    Mesma ordem do `main` e do `with_steam_closed`: o jogo aberto vem ANTES de
    qualquer decisão — fechar a Steam com um jogo aberto o mataria.
    """
    invalidar_varredura_de_proc()
    if steam_game_running():
        print(
            "[launch-options] há um JOGO da Steam aberto — não fecho a Steam "
            "(o jogo morreria com ela); os passos que editam os arquivos dela "
            "vão adiar, cada um com o comando para depois."
        )
        return RC_STEAM_NAO_FECHOU
    if not steam_running():
        print("[launch-options] a Steam já está fechada — nada a reabrir no fim")
        return RC_STEAM_JA_FECHADA
    if not stop_steam():
        print(
            "[launch-options] a Steam não fechou — os passos que editam os "
            "arquivos dela vão adiar (editar com ela viva seria edição perdida)."
        )
        return RC_STEAM_NAO_FECHOU
    print("[launch-options] Steam fechada — ela reabre no fim do install")
    return RC_STEAM_FECHADA_AGORA


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_launch_options",
        description=(
            "Aplica/migra/remove as Launch Options do Hefesto nos "
            "localconfig.vdf (DEDUP-05/UX-04, JOGO-COMPLETO-01/E4). Sem "
            "argumentos, --status."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--status", action="store_true", help="só relata (não modifica nada)"
    )
    group.add_argument(
        "--migrate",
        action="store_true",
        help="troca o veneno estático pela chamada do wrapper (exige Steam fechada)",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help=(
            "põe a chamada do wrapper em TODOS os jogos da Steam nativa, "
            "inclusive nos que nunca tiveram Launch Options (idempotente; "
            "exige Steam fechada)"
        ),
    )
    group.add_argument(
        "--strip",
        action="store_true",
        help="remove o nosso trecho — wrapper E veneno legado (uninstall; exige Steam fechada)",
    )
    group.add_argument(
        "--recolher-fora-da-arvore-viva",
        dest="recolher",
        action="store_true",
        help=(
            "APAGA as linhas LaunchOptions que estão fora de "
            "Software/Valve/Steam/apps — a Steam nunca as leu, e foi um "
            "escritor nosso sem âncora que as pôs lá (exige Steam fechada)"
        ),
    )
    group.add_argument(
        "--fechar-steam",
        action="store_true",
        help=(
            "fecha a Steam UMA vez para os passos do install que editam os "
            "arquivos dela (rc 0 = fechei, reabra no fim; 4 = já estava "
            "fechada; 3 = jogo aberto ou ela não fechou, nada foi fechado)"
        ),
    )
    group.add_argument(
        "--reabrir-steam",
        action="store_true",
        help="reabre a Steam desanexada (o par do --fechar-steam)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="imprime o diff sem tocar nos arquivos",
    )
    parser.add_argument(
        "--stop-steam",
        action="store_true",
        help="fecha a Steam antes de editar e reabre depois (fluxo do install/uninstall)",
    )
    parser.add_argument(
        "--vdf",
        action="append",
        type=Path,
        default=None,
        metavar="ARQUIVO",
        help="localconfig.vdf explícito (repetível; default: descoberta automática)",
    )
    args = parser.parse_args(argv)

    if args.fechar_steam:
        return _fechar_a_steam_uma_vez()
    if args.reabrir_steam:
        return 0 if reopen_steam() else 1

    vdfs = args.vdf if args.vdf else discover_vdfs()
    if not vdfs:
        print("[launch-options] nenhum localconfig.vdf encontrado — nada a fazer")
        return 0

    if args.migrate:
        mode = "migrate"
    elif args.strip:
        mode = "strip"
    elif args.recolher:
        mode = "recolher"
    elif args.apply:
        mode = "apply"
    else:
        return _report_status(vdfs)

    was_running = False
    if not args.dry_run:
        invalidar_varredura_de_proc()
        if steam_game_running():
            print(
                "[launch-options] ERRO: há um JOGO da Steam em execução — "
                "fechar a Steam agora MATARIA o jogo (progresso não salvo "
                "perdido). Feche o jogo e rode de novo."
            )
            return 3
        if args.stop_steam:
            was_running = steam_running()
            if was_running and not stop_steam():
                print(
                    "[launch-options] ERRO: a Steam não fechou — não vou editar "
                    "o vdf com ela viva (ela regravaria o arquivo por cima)."
                )
                return 3
        elif steam_running():
            print(
                "[launch-options] a Steam está aberta — feche-a e rode de novo. "
                "Não vou editar o vdf agora porque a Steam regrava o arquivo ao "
                "sair e a edição seria perdida (ou pior, corrompida)."
            )
            return 3

    if mode == "apply":
        # de Steam/jogo aberto de `apply_wrapper_to_all_games` é a segunda
        recusados = ler_jogos_sem_wrapper()
        if recusados:
            print(
                "[launch-options] fora do wrapper por escolha dela "
                f"(jogos_sem_wrapper.txt): {', '.join(recusados)}"
            )
        try:
            return _report_apply(
                apply_wrapper_to_all_games(
                    vdfs=vdfs, dry_run=args.dry_run, excluir=recusados
                ),
                dry_run=args.dry_run,
            )
        finally:
            if args.stop_steam and was_running and not args.dry_run:
                reopen_steam()

    rc = 0
    total = 0
    for vdf in vdfs:
        effective_mode = mode
        if mode == "migrate" and is_sandboxed_layout(vdf):
            effective_mode = "strip"
            print(
                f"[launch-options] Steam Flatpak/Snap: {vdf} — o wrapper do host "
                "é invisível dentro da sandbox, então aqui só REMOVO o veneno "
                "legado (não escrevo o wrapper)."
            )
        try:
            changed, diff = process_vdf(vdf, effective_mode, dry_run=args.dry_run)
        except (OSError, ValueError) as exc:
            print(f"[launch-options] ERRO em {vdf}: {exc}")
            rc = 1
            continue
        with contextlib.suppress(OSError):
            _warn_extended(vdf, vdf.read_text(encoding="utf-8"))
        if changed == 0:
            print(f"[launch-options] ok (nada a fazer): {vdf}")
            continue
        total += changed
        verb = "migraria" if args.dry_run else "migrado"
        if effective_mode == "strip":
            verb = "limparia" if args.dry_run else "limpo"
        elif effective_mode == "recolher":
            verb = "apagaria" if args.dry_run else "apagado"
        print(f"[launch-options] {verb}: {changed} LaunchOptions em {vdf}")
        if args.dry_run and diff:
            print(diff, end="")
    if not args.dry_run and total:
        print(
            f"[launch-options] {total} LaunchOptions atualizadas "
            "(backup .bak.hefesto-launch-<ts> ao lado de cada vdf)"
        )
    if args.stop_steam and was_running and not args.dry_run:
        reopen_steam()
    return rc


if __name__ == "__main__":  # pragma: no cover - entrypoint do install/uninstall
    sys.exit(main())
