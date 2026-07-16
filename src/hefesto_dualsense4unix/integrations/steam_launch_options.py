"""Launch Options da Steam: string do wrapper + migração do veneno legado.

DEDUP-04/DEDUP-05 (sprint 2026-07-16-sprint-dedup-sem-launch-option.md) e
UX-04/UX-05 (sprint autoswitch-e-launch-options): a desduplicação deixa de ser
uma env ESTÁTICA colada por jogo e vira o wrapper `hefesto-launch %command%`
— string CONSTANTE que decide as envs NA HORA consultando o daemon via IPC.

Este módulo concentra:

1. A string constante do wrapper (`WRAPPER_LAUNCH`) — consumida pelo botão
   "Copiar opções p/ jogos" da GUI (`compose_launch`) e pela migração. Ela
   degrada sozinha: se o wrapper não existir no caminho, o `sh -c` cai em
   `exec env "$@"` e o jogo abre do mesmo jeito (pior caso: controle
   duplicado, nunca zero controles nem launch quebrado).
2. A MIGRAÇÃO do veneno persistido no `localconfig.vdf` (a variante de ondas
   anteriores com `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` esconde o
   único controle quando o vpad degrada — "em BT nada funciona", provado ao
   vivo). `--migrate` troca as linhas envenenadas pela chamada do wrapper;
   `--strip` (uninstall) remove o nosso trecho — novo E legado — deixando o
   resto intacto.

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
- Steam Flatpak/Snap: recusa a MIGRAÇÃO (escrever caminho do host num vdf
  cuja sandbox não enxerga o wrapper quebraria o launch); o strip é sempre
  permitido (remover é seguro).

Módulo 100% stdlib DE PROPÓSITO: o uninstall.sh o executa como script
avulso (`python3 src/.../steam_launch_options.py --strip`) depois de o
.venv já ter sido removido.
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

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


def steam_game_running() -> bool:
    """True quando há um JOGO da Steam em execução (não só a Steam).

    DEDUP-05, exigência 2 da revisão: `steam -shutdown` com jogo aberto MATA o
    jogo (progresso não salvo perdido) — o fluxo de migrate/strip RECUSA em vez
    de derrubar. Detecção pelo processo lançador `reaper SteamLaunch AppId=<id>`
    que embrulha todo jogo lançado pela Steam (Proton E nativo). O `pgrep -f`
    aqui é seguro: a string `SteamLaunch AppId=` só existe em cmdline de launch
    real — o falso-positivo histórico (earlyoom) era com NOMES de processo.
    """
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "SteamLaunch AppId="],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


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
        except OSError as exc:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_launch_options",
        description=(
            "Migra/remove as Launch Options do Hefesto nos localconfig.vdf "
            "(DEDUP-05/UX-04). Sem argumentos, --status."
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

    rc = 0
    total = 0
    for vdf in vdfs:
        if mode == "migrate" and is_sandboxed_layout(vdf):
            print(
                f"[launch-options] PULADO (Steam Flatpak/Snap): {vdf} — o wrapper "
                "do host é invisível dentro da sandbox; escrever o caminho lá "
                "quebraria o launch. O strip do uninstall continua cobrindo esse vdf."
            )
            continue
        try:
            changed, diff = process_vdf(vdf, mode, dry_run=args.dry_run)
        except OSError as exc:
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
        if mode == "strip":
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
