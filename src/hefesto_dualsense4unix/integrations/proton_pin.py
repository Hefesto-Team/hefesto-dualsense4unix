"""Proton PINADO: instala a versão validada e trava os jogos nela (PLAT-01).

Sprint 2026-07-18 (plataforma): a v1 de produção não pode depender da versão
de Proton do dia — a semântica do winebus MUDOU entre Proton 9→10
(PROTON_ENABLE_HIDRAW morreu, provado no estudo 2026-07-18) e um upgrade
automático reintroduziria o vazamento do controle físico. Este módulo é o
lado CONTEÚDO da cura; o install/uninstall/doctor (lane de wiring) só chamam
as funções daqui (ou o CLI `--ensure/--lock/--unlock/--report`).

Desenho (decisões que não relaxam):

- `assets/proton-pin.conf` é a fonte da verdade (name/url/sha256). Upgrade é
  SEMPRE deliberado: editar o conf + rodar o install — nunca automático.
- NUNCA extrair binário não verificado: o tarball (do cache offline-first em
  `~/.cache/hefesto-dualsense4unix/proton/` ou baixado na hora) só é extraído
  se o SHA256 bater com o conf. Mismatch = aborta o passo, estado honesto.
- Travamento por jogo com a Steam FECHADA (mesmo gate do
  `apply_wrapper_to_all_games`): `CompatToolMapping` no config.vdf — default
  global (`"0"`) + entradas por appid — com backup `.bak.hefesto-proton-<ts>`
  e escrita tmp+replace. O que NÓS mudamos fica registrado em estado local
  (`~/.local/state/hefesto-dualsense4unix/proton-pin-lock.json`) — marcador
  DENTRO do vdf não sobrevive à Steam, que regrava o arquivo ao sair.
- Unlock simétrico: reverte SÓ o que o registro diz que é nosso; entrada que
  a usuária mudou depois do lock fica intacta (ela assumiu o controle).
- O tarball extraído em compatibilitytools.d NÃO é removido pelo uninstall
  (dado do usuário; o registro/lock sim).

Módulo 100% stdlib DE PROPÓSITO (padrão do steam_launch_options): o
uninstall.sh o executa como script avulso depois de o .venv já ter sido
removido.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .steam_launch_options import steam_game_running, steam_running
except ImportError:  # pragma: no cover - executado como script avulso pelo install/uninstall
    from steam_launch_options import (  # type: ignore[no-redef]
        steam_game_running,
        steam_running,
    )

#: Nome do manifesto que gravamos DENTRO do diretório extraído — é ele que
#: torna o passo idempotente/offline-first (dir presente + sha256 do conf
#: batendo = no-op sem rede).
MANIFEST_BASENAME = ".hefesto-proton-pin.json"

#: Nome do arquivo de estado local do lock (o "marcador próprio" que o
#: uninstall lê para saber EXATAMENTE o que reverter).
LOCK_STATE_BASENAME = "proton-pin-lock.json"

#: Prioridades observadas ao vivo no config.vdf da Steam (2026-07-18): o
#: default global usa 75 e a entrada por jogo usa 250. Reproduzimos os
#: valores nativos para o vdf ficar indistinguível de um escolhido na UI.
_PRIORITY_GLOBAL = "75"
_PRIORITY_PER_APP = "250"

#: Chaves obrigatórias do proton-pin.conf.
_REQUIRED_CONF_KEYS = ("name", "url", "sha256")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Linha `"name"  "<valor>"` de uma entrada do CompatToolMapping, com os
#: grupos prefix/suffix para reescrita preservando a formatação original.
_NAME_LINE_RE = re.compile(
    r'^(?P<prefix>\s*"[Nn]ame"\s+")(?P<value>(?:\\.|[^"\\])*)(?P<suffix>"\s*)$'
)
_PAIR_RE = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s+"(?P<value>(?:\\.|[^"\\])*)"\s*$'
)
_KEY_ONLY_RE = re.compile(r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*$')

#: Tools de compatibilidade com risco de VAZAMENTO winebus: em Proton ≤ 9 o
#: hidraw só some com PROTON_ENABLE_HIDRAW (semântica antiga) — o wrapper
#: emite a semântica NOVA (DISABLE), então jogo em Proton velho = duplicado
#: de volta. `proton_major` extrai o major dos dois esquemas de nome.
_GE_NAME_RE = re.compile(r"^GE-Proton(?P<major>\d+)", re.IGNORECASE)
_VALVE_NAME_RE = re.compile(r"^proton_(?P<digits>\d+)$", re.IGNORECASE)

#: appmanifest cujo "name" casa aqui é ferramenta, não jogo — nunca travar.
_TOOL_MANIFEST_RE = re.compile(
    r"proton|steam linux runtime|steamworks common|steam runtime",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# proton-pin.conf
# --------------------------------------------------------------------------


def parse_pin_conf(text: str) -> dict[str, str]:
    """Parseia o proton-pin.conf (chave=valor, comentários com #).

    Valida o CONTRATO, não só a sintaxe: name/url/sha256 presentes e sha256
    com cara de sha256 (64 hex). Conf corrompido tem que EXPLODIR aqui —
    seguir adiante com sha256 vazio extrairia binário não verificado.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"linha sem '=' no proton-pin.conf: {line!r}")
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    for key in _REQUIRED_CONF_KEYS:
        if not out.get(key):
            raise ValueError(f"proton-pin.conf sem a chave obrigatória {key!r}")
    sha = out["sha256"].lower()
    if _SHA256_RE.match(sha) is None:
        raise ValueError(
            f"sha256 inválido no proton-pin.conf: {out['sha256']!r} (esperado 64 hex)"
        )
    out["sha256"] = sha
    return out


def default_pin_conf_path() -> Path | None:
    """Localiza assets/proton-pin.conf subindo a partir deste arquivo.

    Cobre o layout do repositório (src/…/integrations/ → raiz/assets/). Se o
    pacote estiver instalado longe do repo, o chamador passa `--conf`.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "assets" / "proton-pin.conf"
        if candidate.is_file():
            return candidate
    return None


# --------------------------------------------------------------------------
# Descoberta de caminhos da Steam (stdlib, sem platformdirs)
# --------------------------------------------------------------------------


def default_steam_root(home: Path | None = None) -> Path:
    """Raiz da Steam NATIVA (~/.steam/steam, fallback ~/.local/share/Steam).

    Flatpak/Snap ficam DE FORA de propósito: o Proton extraído no host é
    invisível dentro da sandbox — travar jogos lá num tool inexistente
    quebraria o launch (mesma regra do wrapper, DEDUP-04).
    """
    base = home or Path.home()
    primary = base / ".steam/steam"
    if primary.is_dir():
        return primary
    fallback = base / ".local/share/Steam"
    if fallback.is_dir():
        return fallback
    return primary


def default_compat_dir(home: Path | None = None) -> Path:
    """compatibilitytools.d da Steam nativa (onde o pin é extraído)."""
    return default_steam_root(home) / "compatibilitytools.d"


def default_cache_dir(home: Path | None = None) -> Path:
    """Cache offline-first do tarball (~/.cache/hefesto-dualsense4unix/proton)."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    cache_home = Path(xdg) if xdg and home is None else base / ".cache"
    return cache_home / "hefesto-dualsense4unix" / "proton"


def default_config_vdf(home: Path | None = None) -> Path:
    """config.vdf da Steam nativa (onde vive o CompatToolMapping)."""
    return default_steam_root(home) / "config" / "config.vdf"


def default_lock_state_path(home: Path | None = None) -> Path:
    """Estado local do lock (~/.local/state/hefesto-dualsense4unix/…)."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    state_home = Path(xdg) if xdg and home is None else base / ".local/state"
    return state_home / "hefesto-dualsense4unix" / LOCK_STATE_BASENAME


# --------------------------------------------------------------------------
# ensure_pinned_proton — instala a versão pinada (cache → download), nunca
# extrai binário não verificado
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EnsureResult:
    """Resultado do ensure: `state` é o contrato com o install/doctor.

    Estados: ``already`` (pin já presente e íntegro — no-op offline),
    ``installed_from_cache``, ``downloaded``, ``checksum_mismatch`` (NADA foi
    extraído) e ``unavailable`` (sem cache válido e sem downloader/download
    falhou — o install segue com aviso honesto, nunca trava a máquina).
    """

    state: str
    detail: str = ""


def sha256_of_file(path: Path) -> str:
    """SHA256 hex de um arquivo, em blocos (o tarball tem ~500 MB)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def curl_downloader(url: str, dest: Path) -> None:
    """Downloader padrão do install: curl com resume (-C -) e fail explícito.

    Injetável de propósito: os testes passam um fake; o ensure NUNCA confia
    no download — o sha256 é conferido depois, sempre.
    """
    proc = subprocess.run(
        ["curl", "-L", "--fail", "-C", "-", "-o", str(dest), url],
        check=False,
    )
    if proc.returncode != 0:
        raise OSError(f"curl falhou (rc={proc.returncode}) baixando {url}")


def pinned_proton_installed(name: str, compat_dir: Path) -> bool:
    """True se compat_dir/<name>/ tem cara de instalação de Proton válida."""
    root = compat_dir / name
    return (root / "proton").is_file() and (root / "version").is_file()


def _read_manifest_sha256(name: str, compat_dir: Path) -> str | None:
    """sha256 registrado no nosso manifesto dentro do dir extraído (ou None)."""
    manifest = compat_dir / name / MANIFEST_BASENAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    sha = data.get("sha256")
    return sha if isinstance(sha, str) else None


def _extract_verified_tarball(
    tarball: Path, name: str, compat_dir: Path
) -> None:
    """Extrai o tarball JÁ VERIFICADO em compat_dir/<name>/ (tmp + rename).

    `filter="data"` do tarfile bloqueia path traversal/links absolutos. A
    extração acontece num tmp irmão e só vira o nome final depois de validada
    (tem `proton` executável) e com o manifesto gravado — crash no meio nunca
    deixa um dir meio-extraído com o nome bom.
    """
    compat_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = compat_dir / f".{name}.hefesto-extract-{os.getpid()}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    try:
        with tarfile.open(tarball, mode="r:gz") as tar:
            tar.extractall(path=tmp_root, filter="data")
        extracted = tmp_root / name
        if not (extracted / "proton").is_file():
            raise OSError(
                f"tarball verificado mas sem {name}/proton dentro — release inesperado"
            )
        manifest = {
            "name": name,
            "sha256": sha256_of_file(tarball),
            "installed_at": int(time.time()),
            "installed_by": "hefesto-dualsense4unix",
        }
        (extracted / MANIFEST_BASENAME).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        final = compat_dir / name
        if final.exists():
            shutil.rmtree(final)
        extracted.rename(final)
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)


def ensure_pinned_proton(
    conf: dict[str, str],
    *,
    compat_dir: Path,
    cache_dir: Path,
    downloader: Callable[[str, Path], None] | None = None,
    verifier: Callable[[Path], str] = sha256_of_file,
) -> EnsureResult:
    """Garante compat_dir/<name>/ íntegro. NUNCA extrai sem o sha256 bater.

    Ordem (offline antes de online, memória da casa):
    1. Já extraído com o nosso manifesto batendo com o conf → ``already``.
    2. Já extraído VÁLIDO sem manifesto (instalação pré-existente da usuária,
       ex.: via ProtonUp) → ``already`` (dado do usuário; não clobberamos).
    3. Cache local com sha256 batendo → extrai → ``installed_from_cache``.
    4. `downloader` (se houver) baixa para o cache, sha256 confere → extrai →
       ``downloaded`` (o tarball FICA no cache p/ reinstalls offline).
    5. sha256 não bateu (cache E/OU download) → ``checksum_mismatch``, nada
       extraído. Sem downloader e sem cache → ``unavailable``.
    """
    name = conf["name"]
    expected = conf["sha256"].lower()

    manifest_sha = _read_manifest_sha256(name, compat_dir)
    if manifest_sha == expected and pinned_proton_installed(name, compat_dir):
        return EnsureResult("already", "manifesto confere com o proton-pin.conf")
    if manifest_sha is None and pinned_proton_installed(name, compat_dir):
        return EnsureResult(
            "already", "instalação pré-existente sem manifesto (mantida)"
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    tarball = cache_dir / f"{name}.tar.gz"
    mismatch_detail = ""
    if tarball.is_file():
        got = verifier(tarball).lower()
        if got == expected:
            _extract_verified_tarball(tarball, name, compat_dir)
            return EnsureResult("installed_from_cache", str(tarball))
        mismatch_detail = f"cache {tarball}: sha256 {got} != {expected}"

    if downloader is None:
        if mismatch_detail:
            return EnsureResult("checksum_mismatch", mismatch_detail)
        return EnsureResult(
            "unavailable", "sem cache local e sem downloader (offline?)"
        )

    # Download SEMPRE para um tmp; só vira cache com o sha256 conferido — um
    # cache envenenado nunca nasce daqui.
    partial = cache_dir / f"{name}.tar.gz.hefesto-download"
    try:
        downloader(conf["url"], partial)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        return EnsureResult("unavailable", f"download falhou: {exc}")
    got = verifier(partial).lower()
    if got != expected:
        partial.unlink(missing_ok=True)
        return EnsureResult(
            "checksum_mismatch",
            f"download de {conf['url']}: sha256 {got} != {expected}",
        )
    partial.replace(tarball)
    _extract_verified_tarball(tarball, name, compat_dir)
    return EnsureResult("downloaded", conf["url"])


# --------------------------------------------------------------------------
# CompatToolMapping — parser/reescrita do config.vdf (puro)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _CtmEntry:
    """Uma entrada `"<appid>" { "name" … }` do CompatToolMapping."""

    appid: str
    key_idx: int  # linha `"<appid>"`
    open_idx: int  # linha `{`
    close_idx: int  # linha `}`
    name_idx: int | None  # linha `"name" "…"` (None = entrada sem name)
    name_value: str


@dataclass(frozen=True)
class _CtmLayout:
    """Posições do CompatToolMapping (e do bloco Steam) num config.vdf."""

    steam_open_idx: int | None
    steam_close_idx: int | None
    ctm_open_idx: int | None
    ctm_close_idx: int | None
    entries: dict[str, _CtmEntry]


def _vdf_unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _vdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_ctm_layout(lines: list[str]) -> _CtmLayout:
    """Localiza Software/Valve/Steam/CompatToolMapping por pilha de blocos.

    Mesmo parser por LINHA do `read_launch_options_by_appid` — conteúdo fora
    do padrão passa intacto byte a byte. O casamento do caminho é por SUFIXO
    (…/software/valve/steam), tolerante ao nome do bloco raiz.
    """
    stack: list[str] = []
    pending: str | None = None
    pending_idx = -1
    steam_open = steam_close = None
    ctm_open = ctm_close = None
    ctm_depth = -1
    steam_depth = -1
    entries: dict[str, _CtmEntry] = {}
    entry: tuple[str, int, int, int | None, str] | None = None

    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if line == "{":
            stack.append(pending if pending is not None else "")
            lowered = [s.lower() for s in stack]
            if steam_open is None and lowered[-3:] == ["software", "valve", "steam"]:
                steam_open, steam_depth = idx, len(stack)
            elif (
                ctm_open is None
                and len(stack) == (steam_depth + 1 if steam_depth > 0 else -1)
                and lowered[-1] == "compattoolmapping"
            ):
                ctm_open, ctm_depth = idx, len(stack)
            elif (
                ctm_open is not None
                and ctm_close is None
                and len(stack) == ctm_depth + 1
                and entry is None
                and pending is not None
            ):
                entry = (pending, pending_idx, idx, None, "")
            pending = None
            continue
        if line == "}":
            if entry is not None and len(stack) == ctm_depth + 1:
                appid, key_idx, open_idx, name_idx, name_value = entry
                entries[appid] = _CtmEntry(
                    appid, key_idx, open_idx, idx, name_idx, name_value
                )
                entry = None
            if ctm_open is not None and ctm_close is None and len(stack) == ctm_depth:
                ctm_close = idx
            if steam_open is not None and steam_close is None and len(stack) == steam_depth:
                steam_close = idx
            if stack:
                stack.pop()
            pending = None
            continue
        pair = _PAIR_RE.match(line)
        if pair is not None:
            pending = None
            if (
                entry is not None
                and len(stack) == ctm_depth + 1
                and _vdf_unescape(pair.group("key")).lower() == "name"
                and entry[3] is None
            ):
                entry = (
                    entry[0],
                    entry[1],
                    entry[2],
                    idx,
                    _vdf_unescape(pair.group("value")),
                )
            continue
        key_only = _KEY_ONLY_RE.match(line)
        if key_only is not None:
            pending = _vdf_unescape(key_only.group("key"))
            pending_idx = idx

    return _CtmLayout(steam_open, steam_close, ctm_open, ctm_close, entries)


def extract_compat_tool_mapping(config_vdf_text: str) -> dict[str, str]:
    """Mapeia appid → nome do tool no CompatToolMapping (read-only).

    Inclui a chave global `"0"` quando presente. Consumido pelo doctor e
    pelos testes; nunca escreve nada.
    """
    lines = config_vdf_text.splitlines(keepends=True)
    layout = _parse_ctm_layout(lines)
    return {
        appid: entry.name_value
        for appid, entry in layout.entries.items()
        if entry.name_idx is not None
    }


def _indent_of(line: str) -> str:
    body = line.rstrip("\r\n")
    return body[: len(body) - len(body.lstrip())]


def _eol_of(line: str) -> str:
    body = line.rstrip("\r\n")
    return line[len(body):] or "\n"


def _entry_block(appid: str, tool_name: str, indent: str, eol: str) -> str:
    """Bloco novo `"<appid>" { name/config/priority }` no formato nativo."""
    priority = _PRIORITY_GLOBAL if appid == "0" else _PRIORITY_PER_APP
    inner = indent + "\t"
    return (
        f'{indent}"{_vdf_escape(appid)}"{eol}'
        f"{indent}{{{eol}"
        f'{inner}"name"\t\t"{_vdf_escape(tool_name)}"{eol}'
        f'{inner}"config"\t\t""{eol}'
        f'{inner}"priority"\t\t"{priority}"{eol}'
        f"{indent}}}{eol}"
    )


def build_compat_tool_mapping(
    config_vdf_text: str,
    *,
    tool_name: str,
    appids: Sequence[str],
) -> tuple[str, dict[str, dict[str, str]]]:
    """Trava o global (`"0"`) + cada appid em `tool_name`, preservando o resto.

    Retorna ``(texto_novo, mudanças)`` — mudanças é o registro que o lock
    persiste para o unlock reverter SÓ o nosso:
    ``{appid: {"action": "added"|"replaced", "previous_name": "…"}}``.
    Idempotente: entrada já apontando para `tool_name` não gera mudança; o
    resto do arquivo passa intacto byte a byte (edição por linha).

    `config.vdf` sem bloco Software/Valve/Steam = ValueError (arquivo que não
    é um config.vdf de verdade — melhor explodir que "criar" a árvore).
    """
    lines = config_vdf_text.splitlines(keepends=True)
    layout = _parse_ctm_layout(lines)
    if layout.steam_open_idx is None or layout.steam_close_idx is None:
        raise ValueError("config.vdf sem bloco Software/Valve/Steam")

    targets = ["0", *[a for a in appids if a != "0"]]
    changes: dict[str, dict[str, str]] = {}
    replacements: dict[int, str] = {}
    new_entries: list[str] = []

    if layout.ctm_open_idx is not None and layout.ctm_close_idx is not None:
        entry_indent = _indent_of(lines[layout.ctm_open_idx]) + "\t"
        eol = _eol_of(lines[layout.ctm_open_idx])
        for appid in targets:
            entry = layout.entries.get(appid)
            if entry is None:
                new_entries.append(_entry_block(appid, tool_name, entry_indent, eol))
                changes[appid] = {"action": "added", "previous_name": ""}
                continue
            if entry.name_idx is None:
                # Entrada sem "name" (fora do padrão) — não arriscar.
                continue
            if entry.name_value == tool_name:
                continue
            body = lines[entry.name_idx].rstrip("\r\n")
            line_eol = lines[entry.name_idx][len(body):]
            m = _NAME_LINE_RE.match(body)
            if m is None:  # linha fora do formato conhecido — não arriscar
                continue
            replacements[entry.name_idx] = (
                m.group("prefix")
                + _vdf_escape(tool_name)
                + m.group("suffix")
                + line_eol
            )
            changes[appid] = {
                "action": "replaced",
                "previous_name": entry.name_value,
            }
        if not replacements and not new_entries:
            return config_vdf_text, {}
        out: list[str] = []
        for idx, raw in enumerate(lines):
            if idx == layout.ctm_close_idx and new_entries:
                out.extend(new_entries)
            out.append(replacements.get(idx, raw))
        return "".join(out), changes

    # Sem CompatToolMapping: cria o bloco inteiro antes do `}` do Steam.
    block_indent = _indent_of(lines[layout.steam_open_idx]) + "\t"
    eol = _eol_of(lines[layout.steam_open_idx])
    entry_indent = block_indent + "\t"
    parts = [f'{block_indent}"CompatToolMapping"{eol}', f"{block_indent}{{{eol}"]
    for appid in targets:
        parts.append(_entry_block(appid, tool_name, entry_indent, eol))
        changes[appid] = {"action": "added", "previous_name": ""}
    parts.append(f"{block_indent}}}{eol}")
    # Marca (na entrada global "0", que sempre existe aqui) que NÓS criamos o
    # bloco CompatToolMapping inteiro do zero — o unlock usa isso para derrubar
    # também o wrapper (open/close + "CompatToolMapping") quando todas as
    # entradas sobreviventes forem revertidas por nós, em vez de deixar um
    # `CompatToolMapping {}` vazio residual (uninstall simétrico, PLAT-01).
    changes["0"]["ctm_created"] = "1"
    out = []
    for idx, raw in enumerate(lines):
        if idx == layout.steam_close_idx:
            out.extend(parts)
        out.append(raw)
    return "".join(out), changes


def remove_compat_tool_mapping(
    config_vdf_text: str,
    *,
    tool_name: str,
    changes: dict[str, dict[str, str]],
) -> tuple[str, int]:
    """Reverte SÓ as mudanças registradas pelo lock. Retorna (texto, nº).

    Regra de ouro do uninstall simétrico: entrada cujo nome atual NÃO é mais
    `tool_name` foi mudada pela usuária depois do lock — fica intacta (ela
    assumiu o controle). ``added`` remove o bloco inteiro; ``replaced``
    restaura o nome anterior.
    """
    lines = config_vdf_text.splitlines(keepends=True)
    layout = _parse_ctm_layout(lines)
    drop: set[int] = set()
    replacements: dict[int, str] = {}
    reverted = 0
    for appid, change in changes.items():
        entry = layout.entries.get(appid)
        if entry is None or entry.name_idx is None:
            continue
        if entry.name_value != tool_name:
            continue  # a usuária mudou depois do lock — dela agora
        if change.get("action") == "added":
            drop.update(range(entry.key_idx, entry.close_idx + 1))
            reverted += 1
        elif change.get("action") == "replaced" and change.get("previous_name"):
            body = lines[entry.name_idx].rstrip("\r\n")
            line_eol = lines[entry.name_idx][len(body):]
            m = _NAME_LINE_RE.match(body)
            if m is None:
                continue
            replacements[entry.name_idx] = (
                m.group("prefix")
                + _vdf_escape(change["previous_name"])
                + m.group("suffix")
                + line_eol
            )
            reverted += 1
    # Uninstall simétrico (achado #7): se NÓS criamos o bloco inteiro
    # (flag `ctm_created` na entrada global "0") e TODAS as entradas
    # sobreviventes do CTM serão derrubadas por nós, remove também o wrapper
    # vazio (open/close + a linha `"CompatToolMapping"`) — senão sobra um
    # `CompatToolMapping {}` residual no config.vdf. Se a usuária assumiu
    # alguma entrada (name != tool_name, já pulada acima), o key_idx dela NÃO
    # está em `drop`, o bloco não fica vazio e o wrapper é preservado intacto
    # (o caso com CTM pré-existente nunca marca a flag, logo segue inalterado).
    ctm_created = changes.get("0", {}).get("ctm_created") == "1"
    if (
        ctm_created
        and layout.ctm_open_idx is not None
        and layout.ctm_close_idx is not None
        and layout.entries
        and all(e.key_idx in drop for e in layout.entries.values())
    ):
        drop.add(layout.ctm_open_idx)
        drop.add(layout.ctm_close_idx)
        j = layout.ctm_open_idx - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j >= 0:
            drop.add(j)  # a linha `"CompatToolMapping"`
    if not drop and not replacements:
        return config_vdf_text, 0
    out = [
        replacements.get(idx, raw)
        for idx, raw in enumerate(lines)
        if idx not in drop
    ]
    return "".join(out), reverted


# --------------------------------------------------------------------------
# lock/unlock — funções de ARQUIVO (gate Steam fechada, backup, tmp+replace)
# --------------------------------------------------------------------------


def _write_vdf_with_backup(vdf: Path, new_text: str) -> Path:
    """Backup `.bak.hefesto-proton-<ts>` + escrita tmp+replace (padrão da casa)."""
    backup = vdf.with_name(vdf.name + f".bak.hefesto-proton-{int(time.time())}")
    shutil.copy2(vdf, backup)
    tmp = vdf.with_name(vdf.name + ".hefesto-tmp")
    tmp.write_text(new_text, encoding="utf-8")
    shutil.copymode(vdf, tmp)
    tmp.replace(vdf)
    return backup


def _steam_gate() -> str | None:
    """Motivo de recusa (ou None). Jogo aberto tem precedência (nunca matar)."""
    if steam_game_running():
        return "jogo_da_steam_aberto"
    if steam_running():
        return "steam_aberta"
    return None


def lock_games_to_pinned_proton(
    *,
    tool_name: str,
    appids: Sequence[str],
    config_vdf: Path | None = None,
    state_path: Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Trava global + appids no pin, com gate de Steam fechada e registro.

    Retorna ``{"status": "locked"|"noop"|"recusado"|"erro", "reason": …,
    "vdf": …, "changes": {...}, "backup": …}``. O registro (estado local em
    `proton-pin-lock.json`) guarda o `previous_name` ORIGINAL: re-locks não o
    sobrescrevem, então o unlock sempre volta ao estado pré-hefesto.
    """
    vdf = config_vdf if config_vdf is not None else default_config_vdf(home)
    state = state_path if state_path is not None else default_lock_state_path(home)
    result: dict[str, object] = {
        "status": "erro",
        "reason": "",
        "vdf": str(vdf),
        "changes": {},
        "backup": "",
    }
    if not vdf.is_file():
        result["reason"] = "config_vdf_ausente"
        return result
    if not dry_run:
        refusal = _steam_gate()
        if refusal is not None:
            result["status"] = "recusado"
            result["reason"] = refusal
            return result
    try:
        original = vdf.read_text(encoding="utf-8")
        new_text, changes = build_compat_tool_mapping(
            original, tool_name=tool_name, appids=appids
        )
    except (OSError, ValueError) as exc:
        result["reason"] = str(exc)
        return result
    result["changes"] = changes
    if not changes:
        result["status"] = "noop"
        result["reason"] = "ja_travado"
        return result
    if dry_run:
        result["status"] = "locked"
        result["reason"] = "dry_run"
        return result
    try:
        # Registro ANTES do vdf: se a persistência do estado falhar (OSError),
        # o config.vdf continua INTACTO (não pinado) e o lock volta com "erro"
        # — falha segura. A ordem inversa deixava o Proton pinado no vdf sem
        # registro, e como re-lock é idempotente (noop, nunca regrava estado)
        # o unlock/uninstall NUNCA mais conseguiria reverter. Se, ao contrário,
        # o estado for gravado mas a escrita do vdf falhar, o vdf fica original
        # e o unlock apenas não acha o que reverter (reverted=0) e limpa o
        # estado — a direção segura da invariante.
        _merge_lock_state(state, tool_name=tool_name, changes=changes)
        result["backup"] = str(_write_vdf_with_backup(vdf, new_text))
    except OSError as exc:
        result["reason"] = str(exc)
        return result
    result["status"] = "locked"
    return result


def _merge_lock_state(
    state_path: Path, *, tool_name: str, changes: dict[str, dict[str, str]]
) -> None:
    """Persiste o registro do lock SEM sobrescrever previous_name antigos."""
    existing: dict[str, dict[str, str]] = {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if data.get("tool_name") == tool_name and isinstance(data.get("changes"), dict):
            existing = data["changes"]
    except (OSError, ValueError):
        pass
    merged = dict(changes)
    merged.update(existing)  # o registro ORIGINAL vence (pré-hefesto de verdade)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_name": tool_name,
        "changes": merged,
        "updated_at": int(time.time()),
    }
    tmp = state_path.with_name(state_path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def lock_proton_for_all_games(
    *,
    conf: dict[str, str] | None = None,
    home: Path | None = None,
    config_vdf: Path | None = None,
    state_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Conveniência ZERO-ARG do botão "Travar Proton validado" da GUI (PLAT-01).

    O worker da aba Sistema chama ``lock_proton_for_all_games()`` sem
    argumentos — este é o alvo dele. Descobre o `tool_name` pelo
    `proton-pin.conf`, os appids pelos jogos instalados
    (`list_installed_appids`), delega em `lock_games_to_pinned_proton` (que já
    tem o gate de Steam fechada, backup e registro) e TRADUZ o retorno para o
    contrato ``{locked, skipped, errors, tool}`` que
    ``daemon_actions.format_proton_lock_result`` consome (`detail` leva o dict
    cru para os "Detalhes técnicos"). Sem `proton-pin.conf` legível,
    `_load_conf` levanta — a GUI vira isso num toast de falha honesto.
    """
    if conf is None:
        conf = _load_conf(None)
    tool_name = conf["name"]
    appids = list_installed_appids(home)
    result = lock_games_to_pinned_proton(
        tool_name=tool_name,
        appids=appids,
        config_vdf=config_vdf,
        state_path=state_path,
        home=home,
        dry_run=dry_run,
    )
    changes = result.get("changes")
    locked = len(changes) if isinstance(changes, dict) else 0
    status = result.get("status")
    return {
        "locked": locked,
        "skipped": 0,
        "errors": 1 if status == "erro" else 0,
        "tool": tool_name,
        "detail": result,
    }


def unlock_games_from_pinned_proton(
    *,
    config_vdf: Path | None = None,
    state_path: Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Uninstall simétrico: reverte SÓ o que o registro do lock diz ser nosso.

    Sem registro = ``noop`` (nunca escrevemos nada — não tocar no vdf).
    Sucesso remove o arquivo de estado; o Proton extraído FICA (dado do
    usuário — documentado no conf e no relatório do uninstall).
    """
    vdf = config_vdf if config_vdf is not None else default_config_vdf(home)
    state = state_path if state_path is not None else default_lock_state_path(home)
    result: dict[str, object] = {
        "status": "erro",
        "reason": "",
        "vdf": str(vdf),
        "reverted": 0,
        "backup": "",
    }
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except OSError:
        result["status"] = "noop"
        result["reason"] = "sem_estado"
        return result
    except ValueError:
        result["reason"] = "estado_corrompido"
        return result
    tool_name = data.get("tool_name", "")
    changes = data.get("changes", {})
    if not tool_name or not isinstance(changes, dict) or not changes:
        result["status"] = "noop"
        result["reason"] = "estado_vazio"
        return result
    if not vdf.is_file():
        result["reason"] = "config_vdf_ausente"
        return result
    if not dry_run:
        refusal = _steam_gate()
        if refusal is not None:
            result["status"] = "recusado"
            result["reason"] = refusal
            return result
    try:
        original = vdf.read_text(encoding="utf-8")
        new_text, reverted = remove_compat_tool_mapping(
            original, tool_name=tool_name, changes=changes
        )
    except OSError as exc:
        result["reason"] = str(exc)
        return result
    result["reverted"] = reverted
    if dry_run:
        result["status"] = "unlocked"
        result["reason"] = "dry_run"
        return result
    try:
        if reverted:
            result["backup"] = str(_write_vdf_with_backup(vdf, new_text))
        state.unlink(missing_ok=True)
    except OSError as exc:
        result["reason"] = str(exc)
        return result
    result["status"] = "unlocked"
    return result


# --------------------------------------------------------------------------
# Doctor helper (puro) + inventário de jogos instalados
# --------------------------------------------------------------------------


def proton_major(tool_name: str) -> int | None:
    """Major do Proton a partir do nome do tool (GE e Valve); None = ignoto.

    `GE-Proton10-34` → 10; `proton_9` → 9; `proton_63` → 6 (era 6.3);
    `proton_513` → 5; `proton_10`/`proton_11` → 10/11 (a partir do 10 a Valve
    para de colar minor no sufixo). `proton_experimental`, runtimes e tools
    customizados → None (não afirmamos o que não sabemos).
    """
    m = _GE_NAME_RE.match(tool_name)
    if m is not None:
        return int(m.group("major"))
    m = _VALVE_NAME_RE.match(tool_name)
    if m is None:
        return None
    digits = m.group("digits")
    if len(digits) == 1:
        return int(digits)  # proton_7/8/9
    if len(digits) == 2 and digits[0] in "12":
        return int(digits)  # proton_10, proton_11, … (major puro a partir do 10)
    # Nomes antigos com minor colado: proton_316→3.16, proton_42→4.2,
    # proton_411→4.11, proton_513→5.13, proton_63→6.3.
    return int(digits[0])


def list_installed_appids(home: Path | None = None) -> list[str]:
    """appids dos JOGOS instalados (appmanifest_*.acf de todas as libraries).

    Ferramentas (Proton, Steam Linux Runtime, redistributables) ficam de fora
    pelo "name" do manifest — travar o Proton-ferramenta em outro Proton não
    faz sentido. Best-effort read-only: manifest ilegível é pulado.
    """
    steamapps = default_steam_root(home) / "steamapps"
    library_dirs = [steamapps]
    libraries_vdf = steamapps / "libraryfolders.vdf"
    try:
        for raw in libraries_vdf.read_text(encoding="utf-8").splitlines():
            pair = _PAIR_RE.match(raw.strip())
            if pair is not None and _vdf_unescape(pair.group("key")).lower() == "path":
                candidate = Path(_vdf_unescape(pair.group("value"))) / "steamapps"
                if candidate.is_dir():
                    library_dirs.append(candidate)
    except OSError:
        pass
    out: set[str] = set()
    for library in library_dirs:
        for manifest in sorted(library.glob("appmanifest_*.acf")):
            appid = manifest.stem.removeprefix("appmanifest_")
            if not appid.isdigit():
                continue
            try:
                text = manifest.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = ""
            for raw in text.splitlines():
                pair = _PAIR_RE.match(raw.strip())
                if pair is not None and _vdf_unescape(pair.group("key")).lower() == "name":
                    name = _vdf_unescape(pair.group("value"))
                    break
            if _TOOL_MANIFEST_RE.search(name):
                continue
            out.add(appid)
    return sorted(out, key=int)


def proton_pin_report(
    conf: dict[str, str],
    *,
    compat_dir: Path,
    config_vdf_text: str,
    installed_appids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Struct do doctor (puro — quem lê arquivos é a lane de wiring).

    Chaves:
    - ``pinned_name``/``pinned_present``/``pinned_manifest_ok``: a versão do
      conf existe em compatibilitytools.d? com o nosso manifesto batendo?
    - ``global_tool``/``global_is_pinned``: o default global (`"0"`).
    - ``mapping``: appid → tool (como está no vdf).
    - ``games_off_pin``: appids (dos instalados, se fornecidos, senão do
      próprio mapping) cujo tool EFETIVO não é o pinado.
    - ``games_leaky_proton``: ``[(appid, tool)]`` com Proton major ≤ 9 —
      risco REAL de vazamento winebus (PROTON_DISABLE_HIDRAW é semântica do
      10+; no ≤ 9 o físico volta a vazar duplicado).
    """
    name = conf["name"]
    present = pinned_proton_installed(name, compat_dir)
    manifest_ok = _read_manifest_sha256(name, compat_dir) == conf["sha256"].lower()
    mapping = extract_compat_tool_mapping(config_vdf_text)
    global_tool = mapping.get("0", "")
    appids = [str(a) for a in installed_appids] if installed_appids is not None else [
        a for a in mapping if a != "0"
    ]
    off_pin: list[str] = []
    leaky: list[tuple[str, str]] = []
    for appid in appids:
        effective = mapping.get(appid) or global_tool
        if effective != name:
            off_pin.append(appid)
        major = proton_major(effective) if effective else None
        if major is not None and major <= 9:
            leaky.append((appid, effective))
    return {
        "pinned_name": name,
        "pinned_present": present,
        "pinned_manifest_ok": manifest_ok,
        "global_tool": global_tool,
        "global_is_pinned": global_tool == name,
        "mapping": mapping,
        "games_off_pin": off_pin,
        "games_leaky_proton": leaky,
    }


# --------------------------------------------------------------------------
# CLI (o install/uninstall/doctor chamam este arquivo como script avulso)
# --------------------------------------------------------------------------


def _load_conf(path: Path | None) -> dict[str, str]:
    conf_path = path if path is not None else default_pin_conf_path()
    if conf_path is None or not conf_path.is_file():
        raise FileNotFoundError(
            "proton-pin.conf não encontrado — passe --conf explicitamente"
        )
    return parse_pin_conf(conf_path.read_text(encoding="utf-8"))


def _cmd_ensure(args: argparse.Namespace) -> int:
    conf = _load_conf(args.conf)
    compat = args.compat_dir if args.compat_dir else default_compat_dir()
    cache = args.cache_dir if args.cache_dir else default_cache_dir()
    downloader = None if args.offline else curl_downloader
    result = ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    print(f"[proton-pin] {conf['name']}: {result.state}"
          + (f" ({result.detail})" if result.detail else ""))
    if result.state == "checksum_mismatch":
        print(
            "[proton-pin] ERRO: o sha256 do tarball NÃO bate com o "
            "proton-pin.conf — nada foi extraído (nunca instalo binário não "
            "verificado). Apague o cache corrompido e rode de novo."
        )
        return 1
    if result.state == "unavailable":
        print(
            "[proton-pin] AVISO: sem cache local e sem rede — o pin fica "
            "pendente; rode o install de novo com internet."
        )
        return 2
    return 0


def _cmd_lock(args: argparse.Namespace) -> int:
    conf = _load_conf(args.conf)
    appids = (
        [a.strip() for a in args.appids.split(",") if a.strip()]
        if args.appids
        else list_installed_appids()
    )
    result = lock_games_to_pinned_proton(
        tool_name=conf["name"],
        appids=appids,
        config_vdf=args.config_vdf,
        state_path=args.state,
        dry_run=args.dry_run,
    )
    print(
        f"[proton-pin] lock: {result['status']}"
        + (f" ({result['reason']})" if result["reason"] else "")
        + f" — {len(appids)} jogos + default global em {result['vdf']}"
    )
    if result["status"] == "recusado":
        print(
            "[proton-pin] feche a Steam (e o jogo) e rode de novo — editar o "
            "config.vdf com ela viva perderia a edição."
        )
        return 3
    return 0 if result["status"] in ("locked", "noop") else 1


def _cmd_unlock(args: argparse.Namespace) -> int:
    result = unlock_games_from_pinned_proton(
        config_vdf=args.config_vdf,
        state_path=args.state,
        dry_run=args.dry_run,
    )
    print(
        f"[proton-pin] unlock: {result['status']}"
        + (f" ({result['reason']})" if result["reason"] else "")
        + f" — {result['reverted']} entradas revertidas"
    )
    if result["status"] == "recusado":
        return 3
    return 0 if result["status"] in ("unlocked", "noop") else 1


def _cmd_report(args: argparse.Namespace) -> int:
    conf = _load_conf(args.conf)
    compat = args.compat_dir if args.compat_dir else default_compat_dir()
    vdf = args.config_vdf if args.config_vdf else default_config_vdf()
    try:
        text = vdf.read_text(encoding="utf-8")
    except OSError:
        text = ""
    report = proton_pin_report(
        conf,
        compat_dir=compat,
        config_vdf_text=text,
        installed_appids=list_installed_appids() or None,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proton_pin",
        description=(
            "Proton pinado (PLAT-01): instala a versão validada do "
            "proton-pin.conf e trava/destrava os jogos nela."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ensure",
        action="store_true",
        help="instala a versão pinada (cache offline-first; sha256 obrigatório)",
    )
    group.add_argument(
        "--lock",
        action="store_true",
        help="trava default global + jogos na versão pinada (exige Steam fechada)",
    )
    group.add_argument(
        "--unlock",
        action="store_true",
        help="reverte SÓ o que o lock registrou (uninstall; exige Steam fechada)",
    )
    group.add_argument(
        "--report",
        action="store_true",
        help="imprime o relatório JSON do doctor (read-only)",
    )
    parser.add_argument("--conf", type=Path, default=None, metavar="ARQUIVO",
                        help="proton-pin.conf (default: assets/ do repo)")
    parser.add_argument("--compat-dir", type=Path, default=None,
                        help="compatibilitytools.d (default: Steam nativa)")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="cache do tarball (default: ~/.cache/hefesto-dualsense4unix/proton)")
    parser.add_argument("--config-vdf", type=Path, default=None,
                        help="config.vdf explícito (default: Steam nativa)")
    parser.add_argument("--state", type=Path, default=None,
                        help="arquivo de estado do lock (default: ~/.local/state/…)")
    parser.add_argument("--appids", default="", metavar="A,B,C",
                        help="appids explícitos p/ --lock (default: jogos instalados)")
    parser.add_argument("--offline", action="store_true",
                        help="--ensure sem rede (só cache; ausente = pendente)")
    parser.add_argument("--dry-run", action="store_true",
                        help="não escreve nada (lock/unlock)")
    args = parser.parse_args(argv)
    try:
        if args.ensure:
            return _cmd_ensure(args)
        if args.lock:
            return _cmd_lock(args)
        if args.unlock:
            return _cmd_unlock(args)
        return _cmd_report(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[proton-pin] ERRO: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover - entrypoint do install/uninstall
    sys.exit(main())
