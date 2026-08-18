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
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

#: Caminho estável do wrapper no $HOME (passo de USUÁRIO do install.sh, sem
#: sudo, sem flag; uninstall simétrico). Mudar aqui exige mudar install.sh,
#: uninstall.sh, doctor.sh e assets/hefesto-launch.sh juntos.
WRAPPER_HOME_RELPATH = ".local/share/hefesto-dualsense4unix/bin/hefesto-launch"

#: O miolo `sh -c` da string constante: roda o wrapper se ele existir e for
#: executável; senão degrada para `exec env "$@"` (o jogo SEMPRE abre — o
#: modo de falha "caminho órfão no vdf = jogo que não abre" foi apontado
#: pela revisão e é isto que o mata). `exec env` (nunca `exec "$@"`): uma
#: LaunchOption pré-existente `VAR=VAL %command%` vira `$1` e o env(1) a
#: processa como assignment em vez de tentar executá-la (ENOENT).
_WRAPPER_INNER = (
    'W="$HOME/' + WRAPPER_HOME_RELPATH + '"; '
    '[ -x "$W" ] && exec "$W" "$@"; exec env "$@"'
)

#: Prefixo da string constante (sem o `%command%` final) — é o que a migração
#: PREPENDE a LaunchOptions existentes.
WRAPPER_PREFIX = "sh -c '" + _WRAPPER_INNER + "' hefesto-launch"

#: A string constante completa — o que o botão da GUI copia e o que fica no
#: vdf de um jogo sem outras opções. Idêntica para QUALQUER máscara/backend
#: (critério (g) do DEDUP-04): quem varia é o arquivo de env materializado
#: que o wrapper lê na hora do launch.
WRAPPER_LAUNCH = WRAPPER_PREFIX + " %command%"

#: Assinatura hefesto-específica do veneno (cirúrgica por VID/PID do
#: DualSense físico). É o ÚNICO gatilho de migração/strip — tokens
#: adjacentes só saem em linhas que a contenham.
IGNORE_SIGNATURE = "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"

#: Tokens que o compose_launch de ondas anteriores emitia JUNTO da
#: assinatura. Removidos apenas como co-ocorrentes (nunca caçados soltos).
_COOCCURRING_TOKENS = ("SDL_JOYSTICK_HIDAPI=0", "PROTON_ENABLE_HIDRAW=1")

#: Preload de shaders (inócuo). Sai na MIGRAÇÃO (o wrapper repõe via env
#: materializada) mas é PRESERVADO no strip do uninstall (UX-04).
_PRELOAD_TOKENS = (
    "__GL_SHADER_DISK_CACHE=1",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1",
)

#: Globs de localconfig.vdf (mesma cobertura do disable_steam_input.sh).
_VDF_GLOB_PATTERNS = (
    ".steam/steam/userdata/*/config/localconfig.vdf",
    ".local/share/Steam/userdata/*/config/localconfig.vdf",
    ".var/app/com.valvesoftware.Steam/.steam/steam/userdata/*/config/localconfig.vdf",
    "snap/steam/common/.steam/steam/userdata/*/config/localconfig.vdf",
)

#: Layouts sandboxed: a migração é PROIBIDA (o wrapper do host é invisível
#: dentro do Flatpak/Snap — caminho órfão quebraria o launch); strip OK.
_SANDBOXED_MARKERS = ("/.var/app/", "/snap/steam/")

_LAUNCH_OPTIONS_RE = re.compile(
    r'^(?P<prefix>\s*"LaunchOptions"\s+")(?P<value>(?:\\.|[^"\\])*)(?P<suffix>"\s*)$'
)

#: Par chave-valor de UMA linha KeyValues (`"chave"  "valor"`), com o mesmo
#: escaping de `_LAUNCH_OPTIONS_RE`. Usado pela leitura POR APPID (read-only).
_VDF_PAIR_RE = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s+"(?P<value>(?:\\.|[^"\\])*)"\s*$'
)
#: Linha só-chave (`"chave"`) que abre um bloco `{` na linha seguinte.
_VDF_KEY_ONLY_RE = re.compile(r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*$')


def _vdf_unescape(value: str) -> str:
    """Desfaz o escaping de KeyValues da Steam (\\\" e \\\\)."""
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _vdf_escape(value: str) -> str:
    """Aplica o escaping de KeyValues da Steam (a string do wrapper tem aspas)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _token_re(token: str) -> re.Pattern[str]:
    """Regex que casa `token` como token COMPLETO (delimitado por espaço ou
    início/fim da string). `IGNORE_DEVICES=0x054c/0x0ce6,0x057e/...` — a lista
    que a usuária ESTENDEU por vírgula — NÃO casa: remover só o nosso pedaço
    deixaria `,0x057e/...` (sem `=`) pendurado, que o env(1)/sh tenta EXECUTAR
    → ENOENT → o jogo NUNCA MAIS abre (reproduzido pela revisão adversarial).
    """
    return re.compile(r"(?<!\S)" + re.escape(token) + r"(?!\S)")


def _token_presente(value: str, token: str) -> bool:
    """True quando `token` aparece como token completo em `value`."""
    return _token_re(token).search(value) is not None


def _remove_token(value: str, token: str) -> str:
    """Remove UMA ocorrência de `token` COMPLETO preservando o resto byte a byte.

    Prefere comer o espaço à direita (o formato emitido era sempre
    `TOK1 TOK2 ... %command%`); cai no espaço à esquerda quando o token é o
    último; token isolado sai seco. Ocorrência que NÃO é token completo (lista
    estendida por vírgula, substring de outra opção) fica INTACTA.
    """
    m = _token_re(token).search(value)
    if m is None:
        return value
    start, end = m.span()
    if end < len(value) and value[end] == " ":
        return value[:start] + value[end + 1:]
    if start > 0 and value[start - 1] == " ":
        return value[: start - 1] + value[end:]
    return value[:start] + value[end:]


def has_poison(value: str) -> bool:
    """True se a LaunchOptions carrega a assinatura do veneno como token
    COMPLETO — o único formato que migrate/strip sabem remover com segurança."""
    return _token_presente(value, IGNORE_SIGNATURE)


def has_extended_ignore(value: str) -> bool:
    """True quando a assinatura existe mas foi ESTENDIDA (ex.: `,0x057e/...`).

    Linha INTOCÁVEL para migrate/strip: mexer deixaria um fragmento-comando
    pendurado (jogo que não abre — o pior modo de falha do sprint doc). O
    fluxo reporta honestamente e pede migração manual.
    """
    return IGNORE_SIGNATURE in value and not _token_presente(value, IGNORE_SIGNATURE)


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
    """
    out = value
    if WRAPPER_PREFIX in out:
        out = _remove_token(out, WRAPPER_PREFIX)
    if has_poison(out):
        out = _remove_token(out, IGNORE_SIGNATURE)
        for token in _COOCCURRING_TOKENS:
            out = _remove_token(out, token)
    if out.strip() == "%command%":
        return ""
    return out.strip() if out != value else out


def migrate_value(value: str) -> str:
    """Migra UMA LaunchOptions envenenada para a chamada do wrapper.

    DEDUP-05: remove as strings NOSSAS conhecidas (assinatura, co-ocorrentes
    e preload — o wrapper repõe o preload via env materializada) ANTES do
    prepend; preserva as opções genuinamente do usuário. Idempotente: linha
    que já chama o wrapper só perde o veneno residual.

    As DUAS semânticas de LaunchOptions são respeitadas:
    - com `%command%`: prepend do WRAPPER_PREFIX (o placeholder existente
      continua sendo o comando; opções do usuário viram args do env(1));
    - sem `%command%` (opções são ARGUMENTOS do jogo): a migração explicita
      `%command%` antes delas — semântica idêntica, agora embrulhada.

    Lista de IGNORE ESTENDIDA pela usuária (`...0x0ce6,0x057e/...`): a linha
    volta INTACTA — remover só o nosso pedaço deixaria fragmento-comando
    (jogo não abre) e embrulhar manteria o veneno ativo por fora do wrapper.
    O chamador reporta via `has_extended_ignore`/`count_extended_ignore`.
    """
    if has_extended_ignore(value):
        return value
    out = value
    if has_poison(out):
        out = _remove_token(out, IGNORE_SIGNATURE)
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


def transform_vdf_text(text: str, mode: str) -> tuple[str, int]:
    """Aplica `migrate`/`strip` a TODAS as linhas LaunchOptions de um vdf.

    Retorna (texto novo, nº de linhas alteradas). Só toca linhas que contêm
    o nosso trecho — `migrate` exige a assinatura do veneno OU uma chamada
    de wrapper já presente; `strip` idem. O resto do arquivo passa intacto
    byte a byte (o parse é por LINHA, com o escaping de KeyValues).
    """
    if mode not in ("migrate", "strip"):
        raise ValueError(f"modo desconhecido: {mode}")
    changed = 0
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        m = _LAUNCH_OPTIONS_RE.match(body)
        if m is None:
            continue
        value = _vdf_unescape(m.group("value"))
        if not (has_poison(value) or WRAPPER_PREFIX in value):
            continue
        new_value = migrate_value(value) if mode == "migrate" else strip_value(value)
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


#: O caminho da ÚNICA árvore `apps` que a Steam lê para `LaunchOptions`, de
#: dentro para fora. Ver `e_a_arvore_canonica` — e o defeito que a criou.
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
       **"faltantes: 0"** com o defeito vivo, e o jogo dela sem reconhecer o
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
    """Mapeia appid → LaunchOptions de um localconfig.vdf, **incluindo os apps
    que NÃO têm a linha** (valor ``None``).

    Leitura ESTRUTURAL e read-only: o `_LAUNCH_OPTIONS_RE` de migrate/strip
    enxerga linhas soltas sem saber de QUAL jogo são; aqui um parser mínimo de
    KeyValues (pilha de blocos por linha) liga cada LaunchOptions ao appid do
    bloco pai. Só entram chaves NUMÉRICAS penduradas na árvore CANÔNICA
    ``Software/Valve/Steam/apps`` — ver `e_a_arvore_canonica`, e o defeito
    ARVORE-ERRADA-01 que essa âncora fecha.
    Nunca escreve nada; conteúdo fora do padrão é ignorado em silêncio.

    **Por que o `None` importa** (SENTINELA-WRAPPER-01, 16/08/2026): a
    `read_launch_options_by_appid` abaixo devolve só quem TEM a linha, e por
    isso não sabe distinguir "este jogo não existe na biblioteca" de "a linha
    deste jogo foi APAGADA". As duas coisas são a mesma ausência para ela, e a
    segunda é justamente a regressão que o censo do wrapper precisa enxergar.
    """
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
    """Mapeia appid → LaunchOptions (desescapado) — só os apps que TÊM a linha.

    Consumida pelo lembrete do wrapper "1x por jogo" (DEDUP-05, item 4). É o
    filtro de `read_apps_by_appid`; a semântica é a de sempre.
    """
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
    nada é escrito neles — o produto não briga com a dona da máquina. A lista
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
    #: (índice da linha `}` do app, linha nova a inserir ANTES dela)
    insertions: list[tuple[int, str]] = []

    stack: list[str] = []
    pending: str | None = None
    #: frame do app aberto: (appid, profundidade, idx da linha `{`, idx da
    #: linha LaunchOptions ou None)
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
                    # App sem LaunchOptions: a linha nova entra no fim do
                    # bloco, indentada como o `{` de abertura + 1 tab.
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
                # A vontade dela vem ANTES de qualquer diagnóstico nosso: nem
                # "já tem" nem "estendido" — ela disse que não quer, e ponto.
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
            if m is None:  # linha fora do formato conhecido — não arriscar
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
            # ValueError cobre UnicodeDecodeError: um localconfig.vdf não-UTF-8
            # (byte latin-1 legado / multi-usuário) vira erro POR-VDF, não
            # aborta a varredura inteira. NÃO usamos errors="replace" aqui —
            # este vdf é REESCRITO adiante e trocar bytes por U+FFFD corromperia
            # o conteúdo alheio.
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
        for appid in applied:
            result["applied"].append({"vdf": str(vdf), "appid": appid, "reason": ""})
    return result


def appid_needs_wrapper(appid: str, home: Path | None = None) -> bool:
    """True quando o lembrete do wrapper se aplica ao jogo `appid` (read-only).

    Consumido pelo diálogo "1x por jogo" da GUI (DEDUP-05, item 4): existe ao
    menos um localconfig.vdf ELEGÍVEL (Steam nativa — Flatpak/Snap ficam de
    fora: a sandbox não enxerga o wrapper do host e a própria migração é
    recusada lá) e NENHUM deles chama o wrapper nas LaunchOptions deste
    appid. Jogo sem entrada no vdf conta como "precisa" (LaunchOptions nunca
    configurada). vdf ilegível é pulado (best-effort: o pior caso é lembrar
    uma vez à toa — e o anti-spam da GUI limita a 1 exibição por sessão).
    """
    eligible = [v for v in discover_vdfs(home) if not is_sandboxed_layout(v)]
    if not eligible:
        return False
    alvo = str(appid).strip()
    for vdf in eligible:
        try:
            text = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError):
            # best-effort read-only: vdf ilegível OU não-UTF-8 é pulado (o pior
            # caso é lembrar uma vez à toa, e a GUI limita a 1x por sessão).
            continue
        value = read_launch_options_by_appid(text).get(alvo)
        if value is not None and WRAPPER_PREFIX in value:
            return False
    return True


def steam_running() -> bool:
    """Detecção idêntica à do disable_steam_input.sh (pgrep, nunca -f solto).

    `steamrt64/steam` casa pelo PATH do runtime; `steamwebhelper` por nome
    EXATO (-x) — o -f pegaria qualquer processo que apenas MENCIONE o nome
    (ex.: earlyoom), o falso-positivo histórico.
    """
    for args in (["pgrep", "-af", "steamrt64/steam"], ["pgrep", "-x", "steamwebhelper"]):
        try:
            proc = subprocess.run(args, capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            return True
    return False


#: Agulha que identifica a cmdline de launch da Steam. `reaper SteamLaunch
#: AppId=<id>` embrulha todo jogo lançado pela Steam (Proton E nativo).
#:
#: **O `\d` final não é enfeite — é o que separa o jogo das ISCAS.** Auditoria de
#: 12/08/2026: a substring solta `"SteamLaunch AppId="` casa a cmdline de quem
#: está PROCURANDO por ela, e há dois desses vivos nesta máquina, sem o truque
#: do `[ ]`:
#:
#:   - `~/.local/bin/aurora-game-watch-daemon.sh:16` — `pgrep -f 'reaper
#:     SteamLaunch AppId='`, a cada 15 s, com o serviço active/running;
#:   - `scripts/disable_steam_input.sh:167` — idem, a cada 30 min.
#:
#: (`pgrep` exclui o próprio pid, nunca o do vizinho.) Como a varredura devolve
#: UMA cmdline — a primeira em ordem de pid —, uma isca com pid menor que o do
#: jogo fazia `steam_game_running()` dizer True e `steam_game_running_appid()`
#: dizer None, ao mesmo tempo. Consequências medidas: o botão "Fechar o jogo e
#: abrir de novo" (`app/actions/base.py`) FECHAVA E NÃO REABRIA, que é
#: literalmente o defeito que a RELANCAR-AGORA-01 existe para curar; e o tique
#: de 2 s do daemon chamava `set_steam_jogo_appid(None)`, sumindo com a aba "No
#: jogo" no meio da partida.
#:
#: Exigir um dígito depois do `=` derruba as duas iscas (elas terminam a string
#: no `=`) e torna `running()`/`appid()` consistentes por construção: se casou,
#: há appid para extrair.
#:
#: Risco residual, idêntico ao do `pgrep -f` que isto substituiu e não removível
#: por regex: qualquer cmdline que apenas MENCIONE `SteamLaunch AppId=<dígito>`
#: casa. É o mesmo contrato de antes, não uma regressão.
_STEAM_LAUNCH_RE = re.compile(r"SteamLaunch AppId=\d")


def _cmdline_of(pid: str | int) -> str:
    """Cmdline de um pid, com os NUL virando espaço. `""` se não der para ler.

    Nunca levanta: pid que morreu entre o `listdir` e o `open` é o caso comum,
    não a exceção, e um processo de outro usuário devolve EACCES.
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read().decode("utf-8", "replace").replace("\0", " ")
    except OSError:
        return ""


def _steam_launch_cmdline() -> str | None:
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

    Duas camadas, nesta ordem:

    1. **Marker do wrapper** — o `hefesto-launch` já grava `appid` e `pid` em
       `launch_env/last_run` justamente para isto. Confirmamos lendo a cmdline
       DESSE pid: se ela casa a agulha E o appid, acabou em 3 `open` (dois do
       marker, um da cmdline). A confirmação é o que elimina o "pid reuse" que o
       NUMA-01 documenta — aqui não precisamos do `last_exit`, porque não
       confiamos no pid sozinho.
    2. **Varredura em Python** — quando o marker falta (jogo lançado fora do
       wrapper, atalho não-Steam, marker de um launch já morto), varremos
       `/proc` lendo UM arquivo por pid em vez de cinco, e sem `fork`/`execve`.

    Números honestos, medidos nesta máquina (auditoria de 12/08/2026 corrigiu a
    versão anterior desta frase, que anunciava o melhor caso como se fosse o
    comum):

      - **Jogo aberto pelo wrapper**: ~3 `openat` por tique (era ~1.287).
      - **Estado permanente de um daemon 24/7, ou seja jogo FECHADO**: o marker
        é global e sobrevive ao jogo, então o pid dele está morto, o caminho
        rápido falha e caímos na varredura — **400 `openat`, 4,2 ms por tique**.
        Contra os ~2.100 do `pgrep`, ainda é ~5x menos, e sem `fork`/`execve`.

    O retorno é a cmdline crua para o chamador extrair o que quiser — é o que
    permite `steam_game_running` e `steam_game_running_appid` compartilharem uma
    varredura só, e é por isso que ambas enxergam exatamente o mesmo processo.
    """
    # 1) Caminho rápido: o marker que o próprio wrapper grava no launch.
    #
    #    Import TARDIO porque este módulo é stdlib puro de propósito (ver o
    #    cabeçalho do arquivo): o `uninstall.sh` o executa avulso DEPOIS de
    #    apagar o `.venv`, e um import de `hefesto_dualsense4unix.daemon` no
    #    topo quebraria esse uso. [Correção de 12/08/2026: a versão anterior
    #    deste comentário alegava import circular. É falso — `daemon/launch_env`
    #    não importa nada deste módulo. A razão é o modo avulso.]
    #
    #    `ImportError` é o caminho ESPERADO (rodando sem venv). `OSError` cobre
    #    marker ilegível. Qualquer outra exceção sobe: engolir tudo aqui faria
    #    um rename futuro em `read_last_run_*` degradar em silêncio para a
    #    varredura completa, para sempre, sem uma linha de log.
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
        # `AppId={appid} ` com a fronteira à direita: sem ela, um marker de
        # appid 159 confirmaria contra um jogo 1599660 (casamento por prefixo).
        # Inofensivo na prática, porque o appid devolvido é reextraído da
        # cmdline logo abaixo — mas confirmar coisa errada não se deixa passar.
        if _STEAM_LAUNCH_RE.search(cmd) and re.search(rf"AppId={appid}\b", cmd):
            return cmd

    # 2) Varredura direta, sem forkar. Um `open` por pid.
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    for entry in entries:
        if not entry.isdigit():
            continue
        cmd = _cmdline_of(entry)
        if _STEAM_LAUNCH_RE.search(cmd):
            return cmd
    return None


def steam_game_running() -> bool:
    """True quando há um JOGO da Steam em execução (não só a Steam).

    DEDUP-05, exigência 2 da revisão: `steam -shutdown` com jogo aberto MATA o
    jogo (progresso não salvo perdido) — o fluxo de migrate/strip RECUSA em vez
    de derrubar. Detecção pelo processo lançador `reaper SteamLaunch AppId=<id>`
    que embrulha todo jogo lançado pela Steam (Proton E nativo).

    A detecção em si mora em `_steam_launch_cmdline` desde PERF-PROC-SCAN-01
    (12/08/2026) — mesma semântica de antes, sem forkar `pgrep`.
    """
    return _steam_launch_cmdline() is not None



def steam_game_running_appid() -> int | None:
    """O appid do jogo da Steam em execução, ou None.

    RELANCAR-AGORA-01 (08/08/2026). A `steam_game_running` acima já casava
    ``SteamLaunch AppId=<id>`` e **jogava o id fora**, devolvendo só um booleano.
    Isso bastava para RECUSAR ("há jogo aberto, não mexo"), e não basta para
    OFERECER: quem promete reabrir o jogo precisa saber qual é.

    Ela apontou o defeito olhando o botão: *"pior que essa terceira opção nem faz
    isso né? Só fecha mesmo"*. Estava certa — o botão dizia "Fechar o jogo e
    abrir de novo" e só fechava.

    Devolve o PRIMEIRO appid encontrado. Com dois jogos abertos a escolha é
    arbitrária, e é aceitável: o diálogo que consome isto nasce de um gesto dela
    sobre o jogo que está na frente, e a alternativa — recusar quando há dois —
    tiraria a cura no caso comum por causa do raro.

    PERF-PROC-SCAN-01 (12/08/2026): esta é a função que o poll loop do daemon
    chama a cada 2 s (`lifecycle._sync_game_signal`), e por isso era ela que
    pagava o `pgrep -af` — 1.287 `openat`/s varrendo `/proc` inteiro. A
    varredura foi para `_steam_launch_cmdline`, que resolve pelo marker do
    wrapper quando ele existe. Semântica de retorno intacta.
    """
    cmd = _steam_launch_cmdline()
    if cmd is None:
        return None
    achado = re.search(r"SteamLaunch AppId=(\d+)", cmd)
    return int(achado.group(1)) if achado else None


def start_steam_game(appid: int) -> bool:
    """Pede à Steam que abra o jogo. True = o pedido saiu.

    RELANCAR-AGORA-01. Usa a URL `steam://rungameid/<appid>`, que é o caminho
    que a própria Steam usa nos atalhos do menu — e é o que faz o jogo nascer
    COM o wrapper do Hefesto, lendo o `launch_env` novo. Chamar o executável
    direto puralaria o wrapper e a mudança dela não valeria, que é o oposto do
    ponto.

    **Não espera o jogo subir**: a Steam leva de segundos a minutos (shader
    cache, atualização), e bloquear a janela por isso seria pior que o defeito.
    O True diz "o pedido saiu", nunca "o jogo abriu" — e o texto da tela precisa
    dizer a mesma coisa, sob pena de mentir.
    """
    url = f"steam://rungameid/{int(appid)}"
    for cmd in (["steam", url], ["xdg-open", url]):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def stop_steam() -> bool:
    """Fecha a Steam (steam -shutdown, espera até 30 s). True = fechada."""
    if not steam_running():
        return True
    if shutil.which("steam") is not None:
        subprocess.Popen(
            ["steam", "-shutdown"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(15):
            time.sleep(2)
            if not steam_running():
                break
    if steam_running():
        # Fallback do precedente: TERM/KILL nos processos do runtime. O
        # webhelper por nome EXATO (-x), nunca -f (earlyoom cita o nome).
        for sig in ("-TERM", "-KILL"):
            subprocess.run(
                ["pkill", sig, "-f", "steamrt64/steam"],
                capture_output=True, check=False,
            )
            subprocess.run(
                ["pkill", sig, "-x", "steamwebhelper"],
                capture_output=True, check=False,
            )
            time.sleep(3)
            if not steam_running():
                break
    time.sleep(2)  # margem para a Steam terminar de gravar o vdf
    return not steam_running()


def reopen_steam() -> None:
    """Reabre a Steam desanexada (best-effort, espelho do precedente)."""
    if shutil.which("steam") is None:
        return
    subprocess.Popen(
        ["steam"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


#: Status possíveis de `with_steam_closed` — contrato do chamador (a GUI faz
#: o toast a partir daqui e NUNCA inventa "Pronto" sobre um destes).
STEAM_JANELA_OK = "ok"
STEAM_JANELA_JOGO_ABERTO = "jogo_aberto"
STEAM_JANELA_NAO_FECHOU = "nao_fechou"


def with_steam_closed(
    tarefa: Callable[[], Any], *, reopen: bool = True
) -> tuple[str, Any]:
    """Roda `tarefa()` com a Steam garantidamente FECHADA e a reabre depois.

    HONESTIDADE-STEAM-01 (25/07). A maquinaria de fechar/reabrir já existia e
    era exercitada só pelo `install.sh --migrate --stop-steam`; a GUI, que é
    onde a usuária clica, nunca a usava — os botões ou recusavam ("feche-a e
    clique de novo") ou rodavam um `--apply-quiet` que ADIAVA em silêncio e
    ainda assim anunciavam sucesso. Este helper é aquele MESMO fluxo provado,
    numa função só, para que os três botões da GUI (desligar Steam Input,
    aplicar o wrapper, "deixar tudo pronto") fechem a Steam UMA vez, façam
    tudo, e reabram UMA vez — em vez de cada um brigar com a Steam por conta.

    Ordem deliberada (idêntica à do `main()`): o gate de JOGO aberto vem
    ANTES de qualquer decisão sobre a Steam — `steam -shutdown` com jogo
    aberto MATA o jogo (progresso não salvo perdido). Só depois se avalia se
    a Steam precisa ser fechada.

    O consentimento NÃO mora aqui: quem chama tem de ter perguntado antes (a
    GUI mostra um diálogo dizendo "preciso fechar a Steam por ~20 s"). Esta
    função é o mecanismo, não a política — o `stop_steam()` escala para
    `pkill -TERM/-KILL` depois de 30 s e isso jamais pode acontecer sem a
    usuária ter dito sim.

    Retorna ``(status, resultado_da_acao)``:

    - ``("jogo_aberto", None)``   — recusado, NADA foi tocado;
    - ``("nao_fechou", None)``    — a Steam resistiu, NADA foi tocado (editar
      com ela viva é edição perdida: ela regrava o vdf ao sair);
    - ``("ok", <retorno de tarefa()>)``.

    A reabertura é `finally`: uma exceção na ação não pode deixar a usuária
    sem Steam.
    """
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


# --- allowlist do Steam Input per-app (STEAM-INPUT-ALLOWLIST-01) ------------
# O arquivo existia e era LIDO por três lados (disable_steam_input.sh,
# integrations/storm_doctor, daemon/launch_env) — e por NINGUÉM escrito. Editar
# `~/.config/.../steam_input_apps.txt` na mão era a única via de "a entrada
# deste jogo vem da Steam", o que na prática significa que a usuária final
# nunca a tinha. O botão "Este jogo não funciona" escreve aqui.
#
# NOTA DATADA — 07/08/2026: este comentário dizia "este jogo é entregue pela
# Steam, sai da frente". A segunda metade caiu com a medição dela de 06/08
# (CONTROLE-SONY-MEDIDO-01, seção A INVERSÃO, grau MEDIDO): o que a lista
# entrega à Steam é a ENTRADA; a saída (cor, gatilhos, vibração) continua do
# Hefesto durante a exceção inteira.

#: Caminho relativo ao diretório de config XDG (mesma convenção do
#: `disable_steam_input.sh`, que resolve `${XDG_CONFIG_HOME:-$HOME/.config}`).
STEAM_INPUT_ALLOWLIST_RELPATH = "hefesto-dualsense4unix/steam_input_apps.txt"

#: Cabeçalho canônico — só é escrito quando o arquivo AINDA NÃO existe. Num
#: arquivo existente, o cabeçalho (e os comentários da usuária) são preservados
#: byte a byte: só acrescentamos linhas no fim.
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
    """Caminho do `steam_input_apps.txt` (XDG), sem tocar no disco.

    Resolve `XDG_CONFIG_HOME` como o shell script faz — assim GUI, guard e
    daemon apontam para o MESMO arquivo (e os testes ficam herméticos).
    """
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / STEAM_INPUT_ALLOWLIST_RELPATH


def parse_steam_input_allowlist(text: str) -> list[str]:
    """AppIDs de um conteúdo de allowlist (uma linha por id; `#` comenta).

    Mesmo formato do `storm_doctor.steam_input_allowlist` e do awk do
    `disable_steam_input.sh` — repetido aqui (e não importado) porque este
    módulo é 100% stdlib DE PROPÓSITO: o uninstall.sh o roda como script
    avulso depois de o .venv já ter sido apagado.
    """
    out: list[str] = []
    for linha in text.splitlines():
        token = linha.split("#", 1)[0].strip()
        if token and token not in out:
            out.append(token)
    return out


# --- appid -> nome do jogo (D-33, 05/08/2026) -------------------------------
# A tradução existia, mas SÓ dentro da CLI (`cli/cmd_steam.py`), que importa
# typer e rich no topo — inimportável de dentro do doctor ou da janela. Por
# isso as três mensagens do Steam Input falavam em "1 perfil(is)" e em "Ligado"
# sem dizer DE QUAL JOGO. A leitura mudou de casa para cá (o módulo que já é o
# dono da allowlist), e a CLI passou a importá-la daqui.
#
# Sem rede e sem cache: a fonte é o `appmanifest_<appid>.acf` que a própria
# Steam mantém em disco. Jogo desinstalado não tem manifest — nesse caso o
# appid CRU é a resposta honesta, e inventar nome não é.

#: Linha `"chave"<tab>"valor"` de .acf/.vdf. O valor pode conter espaço.
_PAR_ACF = re.compile(r'^\s*"(?P<chave>[^"]+)"\s+"(?P<valor>.*)"\s*$')


def _desescapar_acf(valor: str) -> str:
    """Desfaz o escape de VDF (`\\\\` e `\\"`) — mesmo critério do proton_pin."""
    return valor.replace('\\\\', '\\').replace('\\"', '"')


def pastas_steamapps(home: Path | None = None) -> list[Path]:
    """A `steamapps` padrão mais as bibliotecas extras do `libraryfolders.vdf`.

    Best-effort e read-only: biblioteca ilegível ou ausente é pulada em
    silêncio — traduzir appid em nome é conveniência, não pode derrubar nada.

    **Sem pasta repetida, e a comparação é pelo diretório REAL** (16/08/2026).
    Nesta máquina ``~/.steam/steam`` é um link para
    ``~/.steam/debian-installation``, e o `libraryfolders.vdf` lista o segundo:
    dois caminhos com texto diferente, um diretório só. O ``not in pastas``
    comparava o texto, então a lista saía com a mesma `steamapps` duas vezes e
    todo `.acf` dela era lido em dobro. Os dois consumidores de então
    (`nome_do_appid`, que para no primeiro achado, e `jogos_da_biblioteca_steam`,
    que faz `setdefault` por appid) não erravam a conta por sorte de forma — mas
    um censo escrito depois contou 65 jogos onde havia 33, e essa é exatamente a
    armadilha do `WRAPPER-EM-TODOS-01`: um número que parece cobertura.
    O caminho devolvido continua sendo o PRIMEIRO visto, não o resolvido, porque
    é ele que aparece nas mensagens de erro e no relatório.
    """
    # Import TARDIO e com fallback avulso, como o `proton_pin` faz com este
    # módulo: o cabeçalho promete "100% stdlib, roda como script solto", e um
    # `from hefesto_dualsense4unix…` cru quebrava essa promessa com
    # ModuleNotFoundError. Latente até 16/08/2026, quando o `--relatorio` da
    # sentinela — rodado pelo install e pelo doctor com o python3 do SISTEMA —
    # passou a traduzir appid em nome de jogo por este caminho.
    try:
        from .proton_pin import default_steam_root
    except ImportError:  # pragma: no cover - executado como script avulso
        from proton_pin import default_steam_root  # type: ignore[no-redef]

    def real(caminho: Path) -> Path:
        """O diretório de verdade. Link ilegível vale por si mesmo."""
        try:
            return caminho.resolve()
        except OSError:  # pragma: no cover - link quebrado ou permissão
            return caminho

    raiz = default_steam_root(home) / "steamapps"
    pastas = [raiz]
    vistas = {real(raiz)}
    with contextlib.suppress(OSError):
        texto = (raiz / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        for linha in texto.splitlines():
            par = _PAR_ACF.match(linha)
            if par is None or par.group("chave").lower() != "path":
                continue
            candidata = Path(_desescapar_acf(par.group("valor"))) / "steamapps"
            if candidata.is_dir() and real(candidata) not in vistas:
                pastas.append(candidata)
                vistas.add(real(candidata))
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
    """Como o jogo aparece numa frase de tela: nome quando dá, appid sempre.

    ``"Mullet Mad Jack (appid 2111190)"`` quando o manifest existe; o cru
    ``"appid 2111190"`` quando não. O appid NUNCA some da frase: é o número
    que ela precisa para conferir na Steam e o único identificador que os três
    cadastros do projeto (vdf, allowlist, env materializado) compartilham.
    """
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
        # Arquivo existente: append puro (cabeçalho e comentários da usuária
        # intactos), garantindo o \n final que um editor manual pode ter
        # comido. Arquivo ausente: nasce com o cabeçalho canônico.
        corpo = (
            (atual if atual.endswith("\n") else atual + "\n")
            if atual
            else (cabecalho if cabecalho is not None else _ALLOWLIST_HEADER)
        )
        if nota:
            corpo += f"# {nota}\n"
        corpo += f"{alvo}\n"
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Escrita atômica: o guard (path unit) pode estar lendo o arquivo neste
        # instante — meio arquivo lido viraria allowlist vazia e o opt-in seria
        # revertido justamente no clique que o criou.
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
        # `keepends` preserva byte a byte o que fica (inclusive um arquivo sem
        # `\n` final, que o `add` também tolera).
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


# --- "não quero o wrapper NESTE jogo" (SENTINELA-WRAPPER-01, 16/08/2026) ----
# O censo do wrapper (integrations/sentinela_do_wrapper) sabe dizer quais jogos
# perderam a chamada do `hefesto-launch`. Sabendo disso, ele PRECISA saber
# também quando a ausência é vontade dela — senão o produto vira um assistente
# que desfaz a escolha da dona da máquina a cada `./install.sh`.
#
# A regra, e ela é dura de propósito: **intenção nunca é inferida**. Uma linha
# que sumiu é sempre tratada como estrago (a Steam guarda UMA linha por jogo e
# a sobrescreve sem avisar — foi assim que o Pragmata perdeu o wrapper em
# 15/08). O ÚNICO jeito de dizer "não quero" é este arquivo, que a GUI escreve
# com um clique. Adivinhar seria escolher entre dois erros: ou desfazer a
# escolha dela, ou deixar um jogo quebrado calado.
#
# Formato IDÊNTICO ao da allowlist do Steam Input (um appid por linha, `#`
# comenta) porque é o formato que ela já conhece deste projeto — e o parser é
# literalmente o mesmo (`parse_steam_input_allowlist`).

#: Caminho relativo ao diretório de config XDG (mesma convenção da allowlist).
SEM_WRAPPER_RELPATH = "hefesto-dualsense4unix/jogos_sem_wrapper.txt"

_SEM_WRAPPER_HEADER = """\
# hefesto-dualsense4unix — jogos que NÃO devem receber o wrapper de launch
# (SENTINELA-WRAPPER-01)
#
# AppIDs listados aqui ficam de fora do "Aplicar aos jogos da Steam", do passo
# sem flag do install e do reparo automático — e o aviso de "este jogo perdeu
# as opções de inicialização" não aparece para eles.
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
    """AppIDs que ela marcou como "não quero o wrapper aqui". Nunca levanta.

    Arquivo ausente/ilegível = lista vazia: o pior caso de uma leitura falha é
    aplicar o wrapper num jogo que ela não queria, e isso é reversível com um
    clique; o oposto (falhar aberto e deixar 60 jogos sem wrapper) não é.
    """
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
    """"Pode pôr o wrapper de volta" — o avesso do `marcar_jogo_sem_wrapper`.

    Status: ``"removido"`` | ``"nao_estava"`` | ``"appid_invalido"`` |
    ``"erro"``. Reversível é requisito, não conveniência: um jogo marcado por
    engano ficaria sem controle no Bluetooth para sempre, e o conserto não
    pode exigir abrir um arquivo de configuração num editor de texto.
    """
    return remove_appid_from_steam_input_allowlist(
        appid, path=path if path is not None else sem_wrapper_path()
    )


def process_vdf(vdf: Path, mode: str, *, dry_run: bool = False) -> tuple[int, str]:
    """Transforma UM vdf com backup ao lado. Retorna (linhas alteradas, diff).

    Backup `.bak.hefesto-launch-<ts>` (padrão do disable_steam_input.sh).
    `dry_run=True` não toca no arquivo — só devolve o diff unificado.
    """
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
    return changed, diff


def _report_status(vdfs: list[Path]) -> int:
    poisoned = 0
    for vdf in vdfs:
        try:
            text = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            # best-effort read-only: vdf ilegível OU não-UTF-8 é reportado e
            # pulado, sem abortar o relatório dos demais.
            print(f"[launch-options] ERRO lendo {vdf}: {exc}")
            continue
        n_poison = text.count(IGNORE_SIGNATURE)
        # O vdf guarda a string ESCAPADA (aspas viram \") — contar a forma crua
        # daria sempre zero.
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
    """Reporta (sem tocar) LaunchOptions com a lista de IGNORE estendida."""
    n = count_extended_ignore(text)
    if n:
        print(
            f"[launch-options] ATENÇÃO: {n} LaunchOptions com IGNORE_DEVICES "
            f"ESTENDIDO (lista com vírgula) em {vdf} — não tocadas de propósito "
            "(remover só o trecho do Hefesto quebraria o launch); migre "
            "manualmente para o wrapper mantendo a sua parte da lista."
        )


#: Motivos de RECUSA do `apply_wrapper_to_all_games` (nada foi tocado) e a
#: frase honesta de cada um. Espelham palavra por palavra as recusas do
#: migrate/strip no `main` — é o MESMO fato, dito do mesmo jeito.
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
    """Imprime o relatório do `--apply` (estilo do `_report_status`) e dá o rc.

    Os códigos de saída são os MESMOS do migrate/strip, porque o `install.sh`
    trata os três do mesmo jeito:

    - **3** — recusa de porta (Steam ou jogo aberto): NADA foi tocado;
    - **1** — houve erro POR-VDF (vdf ilegível/não-UTF-8); os demais seguiram;
    - **0** — sucesso, inclusive quando não havia nada a fazer. Rodar duas
      vezes é sucesso, não falha: o passo do install roda sem flag e a
      idempotência é requisito dela.
    """
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
            # `appid` vazio = o vdf INTEIRO foi pulado (sandbox Flatpak/Snap).
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
        print(f"[launch-options] ERRO em {erro['vdf']}: {erro['reason']}")
        rc = 1
    return rc


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

    vdfs = args.vdf if args.vdf else discover_vdfs()
    if not vdfs:
        print("[launch-options] nenhum localconfig.vdf encontrado — nada a fazer")
        return 0

    if args.migrate:
        mode = "migrate"
    elif args.strip:
        mode = "strip"
    elif args.apply:
        mode = "apply"
    else:
        return _report_status(vdfs)

    was_running = False
    if not args.dry_run:
        # DEDUP-05 exigência 2: com um JOGO aberto, tanto o `--stop-steam`
        # (que mataria o jogo via steam -shutdown/pkill) quanto a edição em
        # si são recusados — antes de qualquer decisão sobre a Steam.
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
            # Recusa honesta (DEDUP-05): editar com a Steam viva é edição
            # perdida — ela regrava o localconfig.vdf ao sair.
            print(
                "[launch-options] a Steam está aberta — feche-a e rode de novo. "
                "Não vou editar o vdf agora porque a Steam regrava o arquivo ao "
                "sair e a edição seria perdida (ou pior, corrompida)."
            )
            return 3

    if mode == "apply":
        # A via em-massa tem função PRÓPRIA (parse por bloco de app, para
        # alcançar também o jogo que nunca teve LaunchOptions) — o loop de
        # migrate/strip abaixo é por LINHA e não saberia onde inserir. O gate
        # de Steam/jogo aberto de `apply_wrapper_to_all_games` é a segunda
        # muralha: o `--stop-steam` acima pode ter dito que fechou sem ter
        # fechado, e aí nada é tocado.
        # A recusa dela é lida AQUI (e não lá dentro) para a função continuar
        # pura e testável: o passo sem flag do install passa por este `main`,
        # então "não quero o wrapper neste jogo" sobrevive ao reinstall.
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
            # Espelho do rodapé do migrate/strip: quem fechou a Steam a reabre
            # — e reabre mesmo se o relatório levantar, para nunca deixá-la
            # sem Steam por causa de um erro nosso.
            if args.stop_steam and was_running and not args.dry_run:
                reopen_steam()

    rc = 0
    total = 0
    for vdf in vdfs:
        effective_mode = mode
        if mode == "migrate" and is_sandboxed_layout(vdf):
            # Steam Flatpak/Snap: escrever o caminho do wrapper do host num vdf
            # que a sandbox não enxerga quebraria o launch — então, em vez de
            # PULAR (o que deixaria o veneno legado gravado para sempre), aqui
            # fazemos só o STRIP: remover o veneno é seguro e o wrapper NÃO é
            # escrito na sandbox.
            effective_mode = "strip"
            print(
                f"[launch-options] Steam Flatpak/Snap: {vdf} — o wrapper do host "
                "é invisível dentro da sandbox, então aqui só REMOVO o veneno "
                "legado (não escrevo o wrapper)."
            )
        try:
            changed, diff = process_vdf(vdf, effective_mode, dry_run=args.dry_run)
        except (OSError, ValueError) as exc:
            # ValueError cobre UnicodeDecodeError: um localconfig.vdf não-UTF-8
            # vira ERRO por-vdf (rc=1) e o loop segue limpando os demais, em vez
            # de estourar traceback e deixar o veneno IGNORE nos vdfs restantes
            # (o "jogo com zero controles pós-uninstall" que o --strip evita).
            print(f"[launch-options] ERRO em {vdf}: {exc}")
            rc = 1
            continue
        # Honestidade: linha com IGNORE estendido fica intacta e é DITA, nunca
        # sucesso silencioso (o gate por token completo pulou essas linhas).
        with contextlib.suppress(OSError):
            _warn_extended(vdf, vdf.read_text(encoding="utf-8"))
        if changed == 0:
            print(f"[launch-options] ok (nada a fazer): {vdf}")
            continue
        total += changed
        verb = "migraria" if args.dry_run else "migrado"
        if effective_mode == "strip":
            verb = "limparia" if args.dry_run else "limpo"
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
