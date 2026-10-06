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
import contextlib
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

try:
    from .steam_launch_options import (
        add_appid_to_steam_input_allowlist,
        parse_steam_input_allowlist,
        remove_appid_from_steam_input_allowlist,
        steam_game_running,
        steam_running,
    )
except ImportError:  # pragma: no cover - executado como script avulso pelo install/uninstall
    from steam_launch_options import (  # type: ignore[no-redef]
        add_appid_to_steam_input_allowlist,
        parse_steam_input_allowlist,
        remove_appid_from_steam_input_allowlist,
        steam_game_running,
        steam_running,
    )

MANIFEST_BASENAME = ".hefesto-proton-pin.json"

LOCK_STATE_BASENAME = "proton-pin-lock.json"

_PRIORITY_GLOBAL = "75"
_PRIORITY_PER_APP = "250"

_REQUIRED_CONF_KEYS = ("name", "url", "sha256")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_NAME_LINE_RE = re.compile(
    r'^(?P<prefix>\s*"[Nn]ame"\s+")(?P<value>(?:\\.|[^"\\])*)(?P<suffix>"\s*)$'
)
_PAIR_RE = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s+"(?P<value>(?:\\.|[^"\\])*)"\s*$'
)
_KEY_ONLY_RE = re.compile(r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*$')

_GE_NAME_RE = re.compile(r"^GE-Proton(?P<major>\d+)", re.IGNORECASE)
_VALVE_NAME_RE = re.compile(r"^proton_(?P<digits>\d+)$", re.IGNORECASE)

_TOOL_MANIFEST_RE = re.compile(
    r"proton|steam linux runtime|steamworks common|steam runtime",
    re.IGNORECASE,
)

_MARCAS_DE_STEAM = ("steam.sh", "config/config.vdf", "userdata", "steamapps")

RC_CHECKSUM = 1
RC_SEM_REDE_E_SEM_CACHE = 2
RC_ADIADO = 4
RC_EXTRACAO_FALHOU = 5
RC_CONF_ILEGIVEL = 6
RC_STEAM_NA_CAIXA = 7

#: A EXCEÇÃO NOMEADA ao pino — gêmea do `jogos_sem_wrapper.txt` (mesmo formato:
FORA_DO_PINO_RELPATH = "hefesto-dualsense4unix/jogos_fora_do_pino.txt"

_FORA_DO_PINO_HEADER = """\
# hefesto-dualsense4unix — jogos que ficam FORA do Proton pinado
#
# AppIDs listados aqui não são travados no Proton validado: nem pelo install,
# nem pelo vigia da Steam, nem pelo botão da aba Sistema. O Proton que você
# escolher para eles na janela da Steam fica como está — e o jogo que já
# estava no Proton validado volta ao de antes quando a Steam fechar.
#
# Sem o Proton pinado, um upgrade de Proton pode trazer de volta o controle
# duplicado dentro do jogo. Uma linha por AppID; '#' comenta.
"""


def parse_pin_conf(text: str) -> dict[str, str]:
    """Parseia o proton-pin.conf (chave=valor, comentários com #)."""
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
    """Localiza assets/proton-pin.conf subindo a partir deste arquivo."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "assets" / "proton-pin.conf"
        if candidate.is_file():
            return candidate
    return None


def e_raiz_de_steam(raiz: Path) -> bool:
    """True se `raiz` é uma Steam de verdade, e não só uma pasta com esse nome."""
    try:
        if not raiz.is_dir():
            return False
        return any((raiz / marca).exists() for marca in _MARCAS_DE_STEAM)
    except OSError:
        return False


def default_steam_root(home: Path | None = None) -> Path:
    """Raiz da Steam NATIVA (~/.steam/steam, fallback ~/.local/share/Steam)."""
    base = home or Path.home()
    primary = base / ".steam/steam"
    fallback = base / ".local/share/Steam"
    for candidata in (primary, fallback):
        if e_raiz_de_steam(candidata):
            return candidata
    for candidata in (primary, fallback):
        if candidata.is_dir():
            return candidata
    return primary


def steam_em_caixa(home: Path | None = None) -> str | None:
    """``"Flatpak"``/``"Snap"`` quando há uma Steam em sandbox, senão ``None``."""
    base = home or Path.home()
    if (base / ".var/app/com.valvesoftware.Steam/.steam/steam").is_dir():
        return "Flatpak"
    if (base / "snap/steam/common/.steam/steam").is_dir():
        return "Snap"
    return None


def raiz_envenenada(home: Path | None = None) -> Path | None:
    """`~/.steam/steam` quando ele é SOBRA NOSSA, e não uma Steam — ou ``None``."""
    base = home or Path.home()
    alvo = base / ".steam/steam"
    try:
        if alvo.is_symlink() or not alvo.is_dir() or e_raiz_de_steam(alvo):
            return None
        if sorted(p.name for p in alvo.iterdir()) != ["compatibilitytools.d"]:
            return None
        compat = alvo / "compatibilitytools.d"
        for item in compat.iterdir():
            if item.name.startswith(".") and ".hefesto-extract-" in item.name:
                continue
            manifesto = item / MANIFEST_BASENAME
            try:
                dono = json.loads(manifesto.read_text(encoding="utf-8")).get(
                    "installed_by"
                )
            except (OSError, ValueError, AttributeError):
                return None
            if dono != "hefesto-dualsense4unix":
                return None
    except OSError:
        return None
    return alvo


class RaizDaSteamOuRecusa(NamedTuple):
    """``(raiz, motivo)`` — só um dos dois não é ``None`` (T-09, ONDA0-Z7)."""

    raiz: Path | None
    motivo: str | None


def steam_root_ou_recusa(home: Path | None = None) -> RaizDaSteamOuRecusa:
    """:func:`default_steam_root`, mas dizendo POR QUE quando não há onde travar."""
    base = home or Path.home()
    raiz = default_steam_root(base)
    if e_raiz_de_steam(raiz):
        return RaizDaSteamOuRecusa(raiz, None)

    caixa = steam_em_caixa(base)
    if caixa is not None:
        return RaizDaSteamOuRecusa(
            None,
            f"a sua Steam está instalada pela {caixa}, e o Proton que o "
            "Hefesto extrai fica fora da caixa dela",
        )
    return RaizDaSteamOuRecusa(None, "nenhuma Steam encontrada nesta máquina")


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


def fora_do_pino_path(home: Path | None = None) -> Path:
    """Caminho do `jogos_fora_do_pino.txt` (XDG_CONFIG_HOME), sem tocar no disco."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    config_home = Path(xdg) if xdg and home is None else base / ".config"
    return config_home / FORA_DO_PINO_RELPATH


def ler_jogos_fora_do_pino(path: Path | None = None) -> list[str]:
    """Os appids que ela NOMEOU como fora do pino. Nunca levanta."""
    destino = path if path is not None else fora_do_pino_path()
    try:
        return [
            a for a in parse_steam_input_allowlist(destino.read_text(encoding="utf-8"))
            if a.isdigit()
        ]
    except (OSError, ValueError):
        return []


@dataclass(frozen=True)
class EnsureResult:
    """Resultado do ensure: `state` é o contrato com o install/doctor."""

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
    """Downloader padrão do install: curl com resume (-C -) e fail explícito."""
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


def pino_instalado_nesta_maquina(home: Path | None = None) -> bool:
    """O Proton do `proton-pin.conf` está na Steam nativa desta máquina?

    A mesma pergunta que :func:`lock_proton_for_all_games` faz antes de
    travar, para o botão perguntar ANTES de armar (18/09/2026). Sem
    `proton-pin.conf` legível, `_load_conf` levanta.
    """
    return pinned_proton_installed(_load_conf(None)["name"], default_compat_dir(home))


def _read_manifest_sha256(name: str, compat_dir: Path) -> str | None:
    """sha256 registrado no nosso manifesto dentro do dir extraído (ou None)."""
    manifest = compat_dir / name / MANIFEST_BASENAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    sha = data.get("sha256")
    return sha if isinstance(sha, str) else None


def _escapa_da_raiz(caminho: str) -> bool:
    """True se `caminho`, relativo à raiz da extração, sai dela (ou é absoluto)."""
    if caminho.startswith("/"):
        return True
    normal = os.path.normpath(caminho)
    return normal == ".." or normal.startswith("../")


def _conferir_nomes_do_tar(tar: tarfile.TarFile) -> None:
    """A parte LEXICAL do filtro "tar", para o python que não tem filtro."""
    for membro in tar.getmembers():
        nome = membro.name
        if nome.startswith("/") or ".." in Path(nome).parts:
            raise tarfile.TarError(f"membro fora do destino no tarball: {nome!r}")
        if membro.isdev():
            raise tarfile.TarError(f"nó de dispositivo no tarball: {nome!r}")
        if membro.issym():
            alvo = os.path.join(os.path.dirname(nome), membro.linkname)
        elif membro.islnk():
            alvo = membro.linkname
        else:
            continue
        if _escapa_da_raiz(alvo):
            raise tarfile.TarError(
                f"link que aponta para fora do destino no tarball: "
                f"{nome!r} -> {membro.linkname!r}"
            )


def _extract_verified_tarball(
    tarball: Path, name: str, compat_dir: Path
) -> None:
    """Extrai o tarball JÁ VERIFICADO em compat_dir/<name>/ (tmp + rename)."""
    if not compat_dir.parent.is_dir():
        raise FileNotFoundError(
            f"a raiz da Steam ({compat_dir.parent}) não existe — não crio a "
            "casa da Steam; o pino espera a Steam nativa existir"
        )
    compat_dir.mkdir(exist_ok=True)
    tmp_root = compat_dir / f".{name}.hefesto-extract-{os.getpid()}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    try:
        _filtro: Literal["data", "tar"] = (
            "data" if sys.version_info >= (3, 11) else "tar"
        )
        with tarfile.open(tarball, mode="r:gz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=tmp_root, filter=_filtro)
            else:
                _conferir_nomes_do_tar(tar)
                tar.extractall(path=tmp_root)
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
    """Garante compat_dir/<name>/ íntegro. NUNCA extrai sem o sha256 bater."""
    name = conf["name"]
    expected = conf["sha256"].lower()

    manifest_sha = _read_manifest_sha256(name, compat_dir)
    if manifest_sha == expected and pinned_proton_installed(name, compat_dir):
        return EnsureResult("already", "manifesto confere com o proton-pin.conf")
    if manifest_sha is None and pinned_proton_installed(name, compat_dir):
        return EnsureResult(
            "already", "instalação pré-existente sem manifesto (mantida)"
        )

    tarball, obtido = _tarball_conferido_no_cache(
        conf, cache_dir=cache_dir, downloader=downloader, verifier=verifier
    )
    if tarball is None:
        return obtido
    if not compat_dir.parent.is_dir():
        return EnsureResult(
            "adiado",
            f"a raiz da Steam ({compat_dir.parent}) não existe; o tarball "
            f"conferido ficou em {tarball}",
        )
    try:
        _extract_verified_tarball(tarball, name, compat_dir)
    except (OSError, tarfile.TarError) as exc:
        return EnsureResult("extracao_falhou", f"{exc} (disco cheio?)")
    if obtido.state == "em_cache":
        return EnsureResult("installed_from_cache", str(tarball))
    return EnsureResult("downloaded", conf["url"])


def _tarball_conferido_no_cache(
    conf: dict[str, str],
    *,
    cache_dir: Path,
    downloader: Callable[[str, Path], None] | None,
    verifier: Callable[[Path], str],
) -> tuple[Path | None, EnsureResult]:
    """O tarball do pino no cache, CONFERIDO — baixando se preciso. Nunca extrai."""
    name = conf["name"]
    expected = conf["sha256"].lower()
    cache_dir.mkdir(parents=True, exist_ok=True)
    tarball = cache_dir / f"{name}.tar.gz"
    mismatch_detail = ""
    if tarball.is_file():
        got = verifier(tarball).lower()
        if got == expected:
            return tarball, EnsureResult("em_cache", str(tarball))
        mismatch_detail = f"cache {tarball}: sha256 {got} != {expected}"

    if downloader is None:
        if mismatch_detail:
            return None, EnsureResult("checksum_mismatch", mismatch_detail)
        return None, EnsureResult(
            "unavailable", "sem cache local e sem downloader (offline?)"
        )

    partial = cache_dir / f"{name}.tar.gz.hefesto-download"
    try:
        downloader(conf["url"], partial)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        return None, EnsureResult("unavailable", f"download falhou: {exc}")
    got = verifier(partial).lower()
    if got != expected:
        partial.unlink(missing_ok=True)
        return None, EnsureResult(
            "checksum_mismatch",
            f"download de {conf['url']}: sha256 {got} != {expected}",
        )
    partial.replace(tarball)
    return tarball, EnsureResult("baixado", conf["url"])


def adiantar_para_o_cache(
    conf: dict[str, str],
    *,
    cache_dir: Path,
    downloader: Callable[[str, Path], None] | None = None,
    verifier: Callable[[Path], str] = sha256_of_file,
) -> EnsureResult:
    """Baixa e confere o tarball SÓ para o cache — não extrai, não toca na Steam."""
    tarball, obtido = _tarball_conferido_no_cache(
        conf, cache_dir=cache_dir, downloader=downloader, verifier=verifier
    )
    if tarball is None:
        return obtido
    return EnsureResult("em_cache", str(tarball))


@dataclass(frozen=True)
class _CtmEntry:
    """Uma entrada `"<appid>" { "name" … }` do CompatToolMapping."""

    appid: str
    key_idx: int
    open_idx: int
    close_idx: int
    name_idx: int | None
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
    """Localiza Software/Valve/Steam/CompatToolMapping por pilha de blocos."""
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
    """Mapeia appid → nome do tool no CompatToolMapping (read-only)."""
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


def e_da_familia_proton(tool_name: str) -> bool:
    """True se a ferramenta é um Proton (da Valve, GE ou outro) — o que o pino troca."""
    return "proton" in tool_name.lower()


def build_compat_tool_mapping(
    config_vdf_text: str,
    *,
    tool_name: str,
    appids: Sequence[str],
    atropelar_escolha_dela: bool = False,
    pinos_nossos: Sequence[str] = (),
    sem_entrada_nova: Collection[str] = (),
    excluir: Collection[str] = (),
) -> tuple[str, dict[str, dict[str, str]]]:
    """Trava o global (`"0"`) + cada appid em `tool_name`, **sem** atropelar escolha."""
    lines = config_vdf_text.splitlines(keepends=True)
    layout = _parse_ctm_layout(lines)
    if layout.steam_open_idx is None or layout.steam_close_idx is None:
        raise ValueError("config.vdf sem bloco Software/Valve/Steam")

    excluidos = {str(a) for a in excluir}
    nativos = {str(a) for a in sem_entrada_nova}
    targets = ["0", *[a for a in appids if a != "0" and a not in excluidos]]
    if atropelar_escolha_dela:
        ja_no_mapa = sorted(
            (
                a
                for a, e in layout.entries.items()
                if a != "0"
                and a not in targets
                and a not in excluidos
                and e.name_idx is not None
                and (e_da_familia_proton(e.name_value) or e.name_value in pinos_nossos)
            ),
            key=lambda s: (int(s) if s.isdigit() else 0, s),
        )
        targets.extend(ja_no_mapa)
    changes: dict[str, dict[str, str]] = {}
    replacements: dict[int, str] = {}
    new_entries: list[str] = []

    if layout.ctm_open_idx is not None and layout.ctm_close_idx is not None:
        entry_indent = _indent_of(lines[layout.ctm_open_idx]) + "\t"
        eol = _eol_of(lines[layout.ctm_open_idx])
        for appid in targets:
            entry = layout.entries.get(appid)
            if entry is None:
                if appid in nativos:
                    continue
                new_entries.append(_entry_block(appid, tool_name, entry_indent, eol))
                changes[appid] = {"action": "added", "previous_name": ""}
                continue
            if entry.name_idx is None:
                continue
            if entry.name_value == tool_name:
                continue
            nossa = entry.name_value in pinos_nossos
            troca_pedida = atropelar_escolha_dela and e_da_familia_proton(
                entry.name_value
            )
            if appid != "0" and not troca_pedida and not nossa:
                changes[appid] = {
                    "action": "preservado",
                    "previous_name": entry.name_value,
                }
                continue
            body = lines[entry.name_idx].rstrip("\r\n")
            line_eol = lines[entry.name_idx][len(body):]
            m = _NAME_LINE_RE.match(body)
            if m is None:
                continue
            replacements[entry.name_idx] = (
                m.group("prefix")
                + _vdf_escape(tool_name)
                + m.group("suffix")
                + line_eol
            )
            changes[appid] = {
                "action": "migrado" if nossa and appid != "0" else "replaced",
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

    block_indent = _indent_of(lines[layout.steam_open_idx]) + "\t"
    eol = _eol_of(lines[layout.steam_open_idx])
    entry_indent = block_indent + "\t"
    parts = [f'{block_indent}"CompatToolMapping"{eol}', f"{block_indent}{{{eol}"]
    for appid in targets:
        if appid in nativos and appid != "0":
            continue
        parts.append(_entry_block(appid, tool_name, entry_indent, eol))
        changes[appid] = {"action": "added", "previous_name": ""}
    parts.append(f"{block_indent}}}{eol}")
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
    """Reverte SÓ as mudanças registradas pelo lock. Retorna (texto, nº)."""
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
            continue
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
            drop.add(j)
    if not drop and not replacements:
        return config_vdf_text, 0
    out = [
        replacements.get(idx, raw)
        for idx, raw in enumerate(lines)
        if idx not in drop
    ]
    return "".join(out), reverted


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
    migrar_de: Sequence[str] = (),
    todos: bool = False,
    excluir: Collection[str] = (),
    sem_entrada_de: Callable[[Sequence[str]], Collection[str]] | None = None,
    compat_dir: Path | None = None,
) -> dict[str, object]:
    """Trava global + appids no pin, com gate de Steam fechada e registro.

    ``compat_dir`` é onde o pino tem de EXISTIR para a trava valer — 18/09/2026,
    INSTALL-UNIVERSAL. Travar num Proton que não está em `compatibilitytools.d`
    aponta o default global e cada jogo Windows para uma ferramenta que não
    existe, e a Steam deixa de abrir todos eles. Com ele, a trava RECUSA
    (``reason="pino_ausente"``) antes do portão da Steam, e o `config.vdf`
    fica intacto. Todo chamador do PRODUTO o passa (`lock_proton_for_all_games`,
    `--lock`, `--manter`), e uma régua reprova o chamador novo que não passar;
    ``None`` fica para quem mede o miolo do lock sem uma Steam montada. O
    ``dry_run`` não pergunta, pela mesma razão por que pula o portão da Steam:
    ele diz o que MUDARIA no arquivo, e não escreve nada.

    ``excluir`` é a exceção nomeada (`jogos_fora_do_pino.txt`), e
    ``sem_entrada_de`` recebe os appids que AINDA NÃO têm entrada e devolve os
    que não devem ganhar uma (o jogo nativo do Linux, ver
    :func:`jogos_sem_entrada_nova`). Ele é chamado só com os que faltam, e só
    quando falta algum: é o vigia que roda isto a cada meia hora, e o
    `appinfo.vdf` só precisa ser lido quando há jogo novo.

    ``todos=True`` alcança TODO jogo, inclusive o que aponta para uma
    ferramenta que o Hefesto nunca escreveu — ordem dela de 17/09/2026:
    *"ele e todo o resto de agora em diante."* Sem ele, a guarda `preservado`
    continua valendo, e ela é o padrão da função de propósito: quem chamar sem
    pedir não atropela ninguém.

    E ele alcança a entrada ÓRFÃ: a escolha que ficou no `CompatToolMapping`
    de um jogo que não está mais instalado. `appids` vem de
    `list_installed_appids`, então a primeira corrida de `--todos` deixou três
    de fora — e são justamente as que a Steam vai ler quando ela reinstalar.

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
    if (
        compat_dir is not None
        and not dry_run
        and not pinned_proton_installed(tool_name, compat_dir)
    ):
        result["status"] = "recusado"
        result["reason"] = "pino_ausente"
        result["pino"] = str(compat_dir / tool_name)
        return result
    if not dry_run:
        refusal = _steam_gate()
        if refusal is not None:
            result["status"] = "recusado"
            result["reason"] = refusal
            return result
    try:
        with _uma_trava_por_vez(state, ativa=not dry_run):
            return _lock_dentro_da_trava(
                vdf=vdf,
                state=state,
                result=result,
                tool_name=tool_name,
                appids=appids,
                dry_run=dry_run,
                migrar_de=migrar_de,
                todos=todos,
                excluir=excluir,
                sem_entrada_de=sem_entrada_de,
            )
    except _TravaOcupadaError:
        result["status"] = "recusado"
        result["reason"] = "outra_trava_em_curso"
        return result


#: que isto está preso, e esperar para sempre prenderia junto quem espera: o
#: vigia é um oneshot sem prazo (o `.timer` e o `.path` não o disparam de novo
#: enquanto ele não sai, e com ele param o Steam Input e a sentinela), e o
#: install ficaria parado no 11c com a Steam fechada.
_PACIENCIA_DA_TRAVA_S = 30.0


class _TravaOcupadaError(Exception):
    """Outro processo segurou a trava do `config.vdf` além da paciência."""


@contextlib.contextmanager
def _uma_trava_por_vez(state: Path, *, ativa: bool) -> Iterator[None]:
    """Um `flock` exclusivo em volta de ler-mudar-gravar o `config.vdf`."""
    if not ativa:
        yield
        return
    try:
        import fcntl
    except ImportError:  # pragma: no cover - só Linux roda isto
        yield
        return
    alvo = state.with_name(state.name + ".trava")
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(alvo, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        yield
        return
    try:
        prazo = time.monotonic() + _PACIENCIA_DA_TRAVA_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= prazo:
                    raise _TravaOcupadaError(str(alvo)) from None
                time.sleep(0.05)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _lock_dentro_da_trava(
    *,
    vdf: Path,
    state: Path,
    result: dict[str, object],
    tool_name: str,
    appids: Sequence[str],
    dry_run: bool,
    migrar_de: Sequence[str],
    todos: bool,
    excluir: Collection[str],
    sem_entrada_de: Callable[[Sequence[str]], Collection[str]] | None,
) -> dict[str, object]:
    """O corpo do lock, já com a trava na mão (ver `lock_games_to_pinned_proton`)."""
    pinos_nossos = tuple(
        dict.fromkeys([*_pinos_ja_usados(state), *migrar_de, tool_name])
    )
    try:
        original = vdf.read_text(encoding="utf-8")
        sem_entrada_nova: Collection[str] = ()
        if sem_entrada_de is not None:
            ja_no_mapa = extract_compat_tool_mapping(original)
            faltam = [a for a in appids if a != "0" and a not in ja_no_mapa]
            if faltam:
                sem_entrada_nova = sem_entrada_de(faltam)
        new_text, changes = build_compat_tool_mapping(
            original,
            tool_name=tool_name,
            appids=appids,
            pinos_nossos=pinos_nossos,
            atropelar_escolha_dela=todos,
            sem_entrada_nova=sem_entrada_nova,
            excluir=excluir,
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
        _merge_lock_state(
            state, tool_name=tool_name, changes=changes, pinos_nossos=pinos_nossos
        )
        result["backup"] = str(_write_vdf_with_backup(vdf, new_text))
    except OSError as exc:
        result["reason"] = str(exc)
        return result
    result["status"] = "locked"
    return result


def _pinos_ja_usados(state_path: Path) -> tuple[str, ...]:
    """Os Protons que ESTE produto já pinou, na ordem em que apareceram."""
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    pinos = data.get("pinos_do_hefesto")
    conhecidos = [p for p in pinos if isinstance(p, str)] if isinstance(pinos, list) else []
    atual = data.get("tool_name")
    if isinstance(atual, str) and atual and atual not in conhecidos:
        conhecidos.append(atual)
    return tuple(dict.fromkeys(conhecidos))


def _fundir_marcas(
    agora: dict[str, dict[str, str]],
    antes: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Funde as marcas do lock POR CAMPO, porque cada campo tem dono diferente."""
    escreveram = ("added", "replaced", "migrado")
    fundidas: dict[str, dict[str, str]] = {}
    for appid in {*agora, *antes}:
        desta = agora.get(appid)
        daquela = antes.get(appid)
        if desta is None:
            fundidas[appid] = dict(daquela or {})
            continue
        marca = dict(desta)
        if daquela and daquela.get("previous_name"):
            marca["previous_name"] = daquela["previous_name"]
        if desta.get("action") in escreveram:
            marca["veio_de"] = desta.get("previous_name", "")
        elif daquela and "veio_de" in daquela:
            marca["veio_de"] = daquela["veio_de"]
        fundidas[appid] = marca
    return fundidas


def _merge_lock_state(
    state_path: Path,
    *,
    tool_name: str,
    changes: dict[str, dict[str, str]],
    pinos_nossos: Sequence[str] = (),
) -> None:
    """Persiste o registro do lock SEM sobrescrever previous_name antigos."""
    existing: dict[str, dict[str, str]] = {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(data.get("changes"), dict):
            existing = data["changes"]
    except (OSError, ValueError):
        pass
    merged = _fundir_marcas(changes, existing)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_name": tool_name,
        "pinos_do_hefesto": list(
            dict.fromkeys([*_pinos_ja_usados(state_path), *pinos_nossos, tool_name])
        ),
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
    migrar_de: Sequence[str] = (),
    todos: bool = False,
    compat_dir: Path | None = None,
) -> dict[str, object]:
    """Conveniência ZERO-ARG do botão "Travar Proton validado" da GUI (PLAT-01).

    SEM O PINO INSTALADO, RECUSA — 18/09/2026. ``compat_dir`` (padrão: o
    `compatibilitytools.d` da Steam nativa) é repassado ao lock, que devolve
    ``recusado``/``pino_ausente`` em vez de apontar os jogos para um Proton
    que não existe. É aqui, e não em cada botão, para que o da aba Sistema e o
    worker da GTK herdem a guarda sem frase nova de tela.

    ``todos`` É REPASSADO — 18/09/2026. Até aqui esta função nem tinha o
    parâmetro, e o botão que o install manda usar quando a trava é adiada
    rodava com a guarda `preservado` que a ordem de 17/09 revogou: o conselho
    do terminal dizia `--lock --todos`, e o botão fazia outra coisa. O padrão
    continua `False` (quem chama sem pedir não atropela ninguém); os chamadores
    do PRODUTO pedem `todos=True`.

    O que ela nomeou em `jogos_fora_do_pino.txt` fica de fora, e jogo nativo
    do Linux não ganha entrada nova (:func:`jogos_sem_entrada_nova`).

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
        migrar_de=migrar_de,
        todos=todos,
        excluir=ler_jogos_fora_do_pino(fora_do_pino_path(home)),
        sem_entrada_de=lambda faltam: jogos_sem_entrada_nova(faltam, home=home),
        compat_dir=compat_dir if compat_dir is not None else default_compat_dir(home),
    )
    changes = result.get("changes")
    if isinstance(changes, dict):
        locked = sum(
            1 for c in changes.values()
            if isinstance(c, dict) and c.get("action") not in ("preservado", "migrado")
        )
        migrados = sum(
            1 for c in changes.values()
            if isinstance(c, dict) and c.get("action") == "migrado"
        )
        preservados = sum(
            1 for c in changes.values()
            if isinstance(c, dict) and c.get("action") == "preservado"
        )
    else:
        locked = 0
        migrados = 0
        preservados = 0
    status = result.get("status")
    return {
        "locked": locked,
        "migrated": migrados,
        "skipped": preservados,
        "errors": 1 if status == "erro" else 0,
        "status": status,
        "reason": result.get("reason"),
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
    """Uninstall simétrico: reverte SÓ o que o registro do lock diz ser nosso."""
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
        with _uma_trava_por_vez(state, ativa=not dry_run):
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
    except _TravaOcupadaError:
        result["status"] = "recusado"
        result["reason"] = "outra_trava_em_curso"
        return result
    if not dry_run:
        with contextlib.suppress(OSError):
            state.with_name(state.name + ".trava").unlink(missing_ok=True)
    result["status"] = "unlocked"
    return result


def destravar_um_jogo(
    appid: int | str,
    *,
    config_vdf: Path | None = None,
    state_path: Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """O `unlock` para UM jogo: devolve ESTE appid ao Proton que tinha antes."""
    alvo = str(appid).strip()
    vdf = config_vdf if config_vdf is not None else default_config_vdf(home)
    state = state_path if state_path is not None else default_lock_state_path(home)
    result: dict[str, object] = {
        "status": "erro", "reason": "", "vdf": str(vdf), "reverted": 0, "backup": "",
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
    if not tool_name or not isinstance(changes, dict) or alvo not in changes:
        result["status"] = "noop"
        result["reason"] = "nao_era_nosso"
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
        with _uma_trava_por_vez(state, ativa=not dry_run):
            try:
                original = vdf.read_text(encoding="utf-8")
                new_text, reverted = remove_compat_tool_mapping(
                    original, tool_name=tool_name, changes={alvo: changes[alvo]}
                )
            except OSError as exc:
                result["reason"] = str(exc)
                return result
            result["reverted"] = reverted
            if dry_run:
                result["status"] = "destravado"
                result["reason"] = "dry_run"
                return result
            try:
                if reverted:
                    result["backup"] = str(_write_vdf_with_backup(vdf, new_text))
                restante = {k: v for k, v in changes.items() if k != alvo}
                tmp = state.with_name(state.name + ".tmp")
                tmp.write_text(
                    json.dumps({**data, "changes": restante,
                                "updated_at": int(time.time())}, indent=2) + "\n",
                    encoding="utf-8",
                )
                tmp.replace(state)
            except OSError as exc:
                result["reason"] = str(exc)
                return result
    except _TravaOcupadaError:
        result["status"] = "recusado"
        result["reason"] = "outra_trava_em_curso"
        return result
    result["status"] = "destravado"
    return result


def destravar_os_de_fora(
    *,
    config_vdf: Path | None = None,
    state_path: Path | None = None,
    home: Path | None = None,
    fora: Sequence[str] | None = None,
) -> list[str]:
    """Tira do NOSSO pino os jogos de `jogos_fora_do_pino.txt`. Nunca levanta."""
    nomes = list(fora) if fora is not None else ler_jogos_fora_do_pino(
        fora_do_pino_path(home)
    )
    destravados: list[str] = []
    for appid in nomes:
        resultado = destravar_um_jogo(
            appid, config_vdf=config_vdf, state_path=state_path, home=home
        )
        if resultado.get("status") == "destravado":
            destravados.append(str(appid).strip())
    return destravados


def proton_major(tool_name: str) -> int | None:
    """Major do Proton a partir do nome do tool (GE e Valve); None = ignoto."""
    m = _GE_NAME_RE.match(tool_name)
    if m is not None:
        return int(m.group("major"))
    m = _VALVE_NAME_RE.match(tool_name)
    if m is None:
        return None
    digits = m.group("digits")
    if len(digits) == 1:
        return int(digits)
    if len(digits) == 2 and digits[0] in "12":
        return int(digits)
    return int(digits[0])


def list_installed_appids(home: Path | None = None) -> list[str]:
    """appids dos JOGOS instalados (appmanifest_*.acf de todas as libraries)."""
    out: set[str] = set()
    for library in _pastas_de_biblioteca(home):
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


def _pastas_de_biblioteca(home: Path | None = None) -> list[Path]:
    """A `steamapps` da Steam nativa mais as do `libraryfolders.vdf`."""
    steamapps = default_steam_root(home) / "steamapps"
    library_dirs = [steamapps]
    libraries_vdf = steamapps / "libraryfolders.vdf"
    try:
        for raw in libraries_vdf.read_text(encoding="utf-8").splitlines():
            pair = _PAIR_RE.match(raw.strip())
            if pair is not None and _vdf_unescape(pair.group("key")).lower() == "path":
                candidate = Path(_vdf_unescape(pair.group("value"))) / "steamapps"
                if candidate.is_dir() and candidate not in library_dirs:
                    library_dirs.append(candidate)
    except OSError:
        pass
    return library_dirs


_APPINFO_MAGICS = {0x07564428: 28, 0x07564429: 29}

_APPINFO_CABECALHO_DA_ENTRADA = 60


def _ler_cstring(buf: bytes, pos: int) -> tuple[str, int]:
    fim = buf.index(b"\0", pos)
    return buf[pos:fim].decode("utf-8", "replace"), fim + 1


def _ler_vdf_binario(
    buf: bytes, pos: int, chaves: list[str] | None, profundidade: int = 0
) -> tuple[dict[str, object], int]:
    """Um mapa do KeyValues binário da Steam, a partir de `pos`, até o `0x08`."""
    if profundidade > 64:
        raise ValueError("appinfo.vdf aninhado demais")
    out: dict[str, object] = {}
    while True:
        tipo = buf[pos]
        pos += 1
        if tipo in (0x08, 0x0B):
            return out, pos
        if chaves is None:
            chave, pos = _ler_cstring(buf, pos)
        else:
            (indice,) = struct.unpack_from("<I", buf, pos)
            pos += 4
            chave = chaves[indice]
        valor: object
        if tipo == 0x00:
            valor, pos = _ler_vdf_binario(buf, pos, chaves, profundidade + 1)
        elif tipo == 0x01:
            valor, pos = _ler_cstring(buf, pos)
        elif tipo == 0x02:
            (valor,) = struct.unpack_from("<i", buf, pos)
            pos += 4
        elif tipo in (0x03, 0x04, 0x06):
            valor, pos = None, pos + 4
        elif tipo in (0x07, 0x0A):
            valor, pos = None, pos + 8
        elif tipo == 0x05:
            fim = pos
            while True:
                if fim + 2 > len(buf):
                    raise ValueError("string larga sem fim no appinfo.vdf")
                if buf[fim:fim + 2] == b"\0\0":
                    break
                fim += 2
            valor = buf[pos:fim].decode("utf-16-le", "replace")
            pos = fim + 2
        else:
            raise ValueError(f"tipo {tipo:#x} desconhecido no appinfo.vdf")
        out[chave] = valor


def _chave(mapa: object, nome: str) -> object:
    """`mapa[nome]` sem diferenciar maiúsculas (a Steam não é constante nisso)."""
    if not isinstance(mapa, dict):
        return None
    for k, v in mapa.items():
        if isinstance(k, str) and k.lower() == nome:
            return v
    return None


def oslist_do_appinfo(
    appinfo: Path, appids: Collection[str]
) -> dict[str, str] | None:
    """O `common/oslist` de cada appid pedido, lido do `appinfo.vdf` binário."""
    procurados = {str(a) for a in appids}
    if not procurados:
        return {}
    achados: dict[str, str] = {}
    try:
        with appinfo.open("rb") as fh:
            cabeca = fh.read(8)
            if len(cabeca) < 8:
                return None
            magia, _universo = struct.unpack("<II", cabeca)
            versao = _APPINFO_MAGICS.get(magia)
            if versao is None:
                return None
            chaves: list[str] | None = None
            if versao >= 29:
                (tabela,) = struct.unpack("<q", fh.read(8))
                inicio_das_entradas = fh.tell()
                fh.seek(tabela)
                bruto = fh.read()
                (quantas,) = struct.unpack_from("<I", bruto, 0)
                chaves = [
                    s.decode("utf-8", "replace")
                    for s in bruto[4:].split(b"\0")[:quantas]
                ]
                fh.seek(inicio_das_entradas)
            while procurados - achados.keys():
                par = fh.read(8)
                if len(par) < 4:
                    break
                (appid,) = struct.unpack_from("<I", par, 0)
                if appid == 0 or len(par) < 8:
                    break
                (tamanho,) = struct.unpack_from("<I", par, 4)
                if str(appid) not in procurados:
                    fh.seek(tamanho, os.SEEK_CUR)
                    continue
                entrada = fh.read(tamanho)
                if len(entrada) < tamanho:
                    return None
                vdf, _ = _ler_vdf_binario(
                    entrada, _APPINFO_CABECALHO_DA_ENTRADA, chaves
                )
                oslist = _chave(_chave(_chave(vdf, "appinfo"), "common"), "oslist")
                achados[str(appid)] = oslist if isinstance(oslist, str) else ""
    except (OSError, ValueError, IndexError, struct.error):
        return None
    return achados


def _declara_linux(oslist: str) -> bool:
    return "linux" in {p.strip().lower() for p in oslist.split(",")}


def jogos_sem_entrada_nova(
    appids: Sequence[str], *, home: Path | None = None
) -> set[str]:
    """Dos `appids`, os que NÃO ganham entrada nova por jogo no pino."""
    raiz = default_steam_root(home)
    oslist = oslist_do_appinfo(raiz / "appcache" / "appinfo.vdf", appids)
    compatdatas = [lib / "compatdata" for lib in _pastas_de_biblioteca(home)]
    nativos: set[str] = set()
    for appid in appids:
        declarado = oslist.get(appid) if oslist is not None else None
        if declarado is not None:
            if _declara_linux(declarado):
                nativos.add(appid)
            continue
        if not any((c / appid).is_dir() for c in compatdatas):
            nativos.add(appid)
    return nativos


# desinstalar as outras versoes nao usadas». (noqa-acento: citação literal)

_NOME_INTERNO_RE = re.compile(r'"(?P<nome>(?:\\.|[^"\\])+)"[^\n{]*\n\s*\{')


@dataclass(frozen=True)
class VersaoQueSobra:
    """Uma pasta de `compatibilitytools.d` que nenhum jogo nem o pino usam."""

    pasta: Path
    nomes: tuple[str, ...]
    tamanho: int


def nomes_internos(pasta: Path) -> tuple[str, ...]:
    """Os nomes que a Steam lê no `compatibilitytool.vdf` da pasta."""
    try:
        texto = (pasta / "compatibilitytool.vdf").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (pasta.name,)
    inicio = texto.find('"compat_tools"')
    if inicio < 0:
        return (pasta.name,)
    corpo = texto[inicio + len('"compat_tools"'):]
    abre = corpo.find("{")
    if abre < 0:
        return (pasta.name,)
    nomes: list[str] = []
    nivel = 0
    i = abre
    while i < len(corpo):
        ch = corpo[i]
        if ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                break
        elif ch == '"' and nivel == 1:
            achado = _NOME_INTERNO_RE.match(corpo, i)
            if achado is not None:
                nomes.append(_vdf_unescape(achado.group("nome")))
                i = achado.end() - 1
                continue
            fim = corpo.find('"', i + 1)
            i = fim if fim > 0 else len(corpo)
        elif ch == "/" and corpo.startswith("//", i):
            fim = corpo.find("\n", i)
            i = fim if fim > 0 else len(corpo)
            continue
        i += 1
    return tuple(nomes) or (pasta.name,)


def _tamanho_da_pasta(pasta: Path) -> int:
    total = 0
    for raiz, _dirs, arquivos in os.walk(pasta, followlinks=False):
        for nome in arquivos:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(raiz, nome)).st_size
    return total


def versoes_que_sobram(
    home: Path | None = None,
    *,
    pino: str | None = None,
) -> list[VersaoQueSobra]:
    """As versões do Proton em `compatibilitytools.d` que ninguém usa."""
    raiz, _recusa = steam_root_ou_recusa(home)
    if raiz is None:
        return []
    try:
        nome_do_pino = pino if pino is not None else _load_conf(None)["name"]
        mapa = extract_compat_tool_mapping(
            (raiz / "config" / "config.vdf").read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, KeyError):
        return []
    usadas = {nome_do_pino, *mapa.values()}
    compat = raiz / "compatibilitytools.d"
    try:
        pastas = sorted(p for p in compat.iterdir() if p.is_dir() and not p.is_symlink())
    except OSError:
        return []
    sobras: list[VersaoQueSobra] = []
    for pasta in pastas:
        nomes = nomes_internos(pasta)
        if not all(e_da_familia_proton(n) for n in nomes):
            continue
        if usadas.intersection(nomes) or pasta.name in usadas:
            continue
        sobras.append(VersaoQueSobra(pasta, nomes, _tamanho_da_pasta(pasta)))
    return sobras


def _em_uso(pasta: Path) -> bool:
    """Algum processo vivo roda de dentro da pasta (a fila da Steam, um jogo)?"""
    alvo = str(pasta.resolve())
    prefixo = alvo + os.sep
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        with contextlib.suppress(OSError):
            exe = os.readlink(f"/proc/{pid}/exe")
            if exe == alvo or exe.startswith(prefixo):
                return True
        with contextlib.suppress(OSError):
            linha = Path(f"/proc/{pid}/cmdline").read_bytes()
            if prefixo.encode() in linha:
                return True
    return False


def _para_a_lixeira(pasta: Path) -> str | None:
    """Manda a pasta para a lixeira do usuário. `None` deu certo; senão, o motivo."""
    gio = shutil.which("gio")
    if gio is None:
        return "sem lixeira nesta máquina (falta o gio)"
    proc = subprocess.run([gio, "trash", str(pasta)], check=False,
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or f"gio rc={proc.returncode}").strip()
    return None


def desinstalar_as_que_sobram(
    sobras: Sequence[VersaoQueSobra],
    *,
    lixeira: Callable[[Path], str | None] = _para_a_lixeira,
    em_uso: Callable[[Path], bool] = _em_uso,
) -> tuple[list[VersaoQueSobra], dict[str, str]]:
    """Manda cada sobra para a lixeira. Devolve as que saíram e as recusadas."""
    saiu: list[VersaoQueSobra] = []
    recusadas: dict[str, str] = {}
    for sobra in sobras:
        if sobra.pasta.parent.name != "compatibilitytools.d" or not sobra.pasta.is_dir():
            recusadas[sobra.pasta.name] = "não está mais em compatibilitytools.d"
            continue
        try:
            if em_uso(sobra.pasta):
                recusadas[sobra.pasta.name] = "em uso agora"
                continue
            motivo = lixeira(sobra.pasta)
        except Exception as exc:
            motivo = str(exc) or type(exc).__name__
        if motivo is None:
            saiu.append(sobra)
        else:
            recusadas[sobra.pasta.name] = motivo
    return saiu, recusadas


def proton_pin_report(
    conf: dict[str, str],
    *,
    compat_dir: Path,
    config_vdf_text: str,
    installed_appids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Struct do doctor (puro — quem lê arquivos é a lane de wiring)."""
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


def _load_conf(path: Path | None) -> dict[str, str]:
    conf_path = path if path is not None else default_pin_conf_path()
    if conf_path is None or not conf_path.is_file():
        raise FileNotFoundError(
            "proton-pin.conf não encontrado — passe --conf explicitamente"
        )
    return parse_pin_conf(conf_path.read_text(encoding="utf-8"))


def _conf_ou_rc(args: argparse.Namespace) -> dict[str, str] | int:
    """O conf lido, ou o rc de conf ilegível — que NÃO é o rc de checksum."""
    try:
        return _load_conf(args.conf)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[proton-pin] ERRO: proton-pin.conf ilegível — {exc}")
        return RC_CONF_ILEGIVEL


def _rc_do_ensure(result: EnsureResult) -> int:
    """Traduz o estado do ensure no código de saída, e diz o que ele quer dizer."""
    if result.state == "checksum_mismatch":
        print(
            "[proton-pin] ERRO: o sha256 do tarball NÃO bate com o "
            "proton-pin.conf — nada foi extraído (nunca instalo binário não "
            "verificado). Apague o cache corrompido e rode de novo."
        )
        return RC_CHECKSUM
    if result.state == "unavailable":
        print(
            "[proton-pin] AVISO: sem cache local e sem rede — o pin fica "
            "pendente; rode o install de novo com internet."
        )
        return RC_SEM_REDE_E_SEM_CACHE
    if result.state == "adiado":
        return RC_ADIADO
    if result.state == "extracao_falhou":
        print(
            "[proton-pin] ERRO: o tarball BATEU com o sha256, e a extração "
            "falhou — veja o espaço livre em disco. O cache está bom; rode de "
            "novo depois de liberar espaço."
        )
        return RC_EXTRACAO_FALHOU
    return 0


def _avisar_da_raiz_envenenada() -> None:
    """Diz, no log do install e do vigia, onde está a sobra que cega a Steam."""
    sobra = raiz_envenenada()
    if sobra is not None:
        print(
            f"[proton-pin] AVISO: {sobra} é sobra de um instalador antigo do "
            "Hefesto (só tem o Proton pinado dentro), e com ela no caminho a "
            f"Steam adota {sobra.parent} como casa. Com a Steam FECHADA: "
            f'mv "{sobra}" "{sobra}.sobra-do-hefesto"'
        )


def _cmd_ensure(args: argparse.Namespace) -> int:
    conf = _conf_ou_rc(args)
    if isinstance(conf, int):
        return conf
    cache = args.cache_dir if args.cache_dir else default_cache_dir()
    downloader = None if args.offline else curl_downloader
    if args.compat_dir:
        compat = args.compat_dir
    else:
        raiz, motivo = steam_root_ou_recusa()
        if raiz is None:
            _avisar_da_raiz_envenenada()
            if steam_em_caixa() is not None:
                print(
                    f"[proton-pin] {conf['name']}: adiado ({motivo}) — nada "
                    "baixado: o Proton extraído no host não serve dentro da caixa"
                )
                return RC_STEAM_NA_CAIXA
            result = adiantar_para_o_cache(
                conf, cache_dir=cache, downloader=downloader
            )
            print(f"[proton-pin] {conf['name']}: {result.state}"
                  + (f" ({result.detail})" if result.detail else ""))
            if result.state != "em_cache":
                return _rc_do_ensure(result)
            print(
                f"[proton-pin] pino adiado até a Steam nativa existir ({motivo}): "
                "o tarball conferido ficou no cache, nada foi extraído e nada "
                "foi criado na pasta da Steam. Quando ela existir, o vigia da "
                "Steam (ou o próximo install) extrai e trava, sem rede."
            )
            return RC_ADIADO
        compat = raiz / "compatibilitytools.d"
    result = ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    print(f"[proton-pin] {conf['name']}: {result.state}"
          + (f" ({result.detail})" if result.detail else ""))
    return _rc_do_ensure(result)


def _cmd_manter(args: argparse.Namespace) -> int:
    """O que o vigia da Steam roda: repõe o pino sem rede, e trava todo jogo."""
    conf = _conf_ou_rc(args)
    if isinstance(conf, int):
        return conf
    raiz, motivo = steam_root_ou_recusa()
    if raiz is None:
        _avisar_da_raiz_envenenada()
        print(f"[proton-pin] manter: nada a fazer — {motivo}")
        return 0
    name = conf["name"]
    compat = args.compat_dir if args.compat_dir else raiz / "compatibilitytools.d"
    if not pinned_proton_installed(name, compat):
        cache = args.cache_dir if args.cache_dir else default_cache_dir()
        if not (cache / f"{name}.tar.gz").is_file():
            print(f"[proton-pin] manter: {name} ainda não está em {compat}, e o "
                  f"tarball não está no cache ({cache})")
            return _rc_do_ensure(EnsureResult(
                "unavailable", "sem cache local e sem downloader (offline?)"))
        recusa = _steam_gate()
        if recusa is not None:
            print(
                f"[proton-pin] manter: {name} ainda não está em {compat}, e a "
                f"extração espera a Steam fechar ({recusa})"
            )
            return 3
        result = ensure_pinned_proton(
            conf, compat_dir=compat, cache_dir=cache, downloader=None
        )
        print(f"[proton-pin] manter: {name}: {result.state}"
              + (f" ({result.detail})" if result.detail else ""))
        if not pinned_proton_installed(name, compat):
            return _rc_do_ensure(result)
    vdf = args.config_vdf if args.config_vdf else raiz / "config" / "config.vdf"
    if not vdf.is_file():
        print(f"[proton-pin] manter: {vdf} ainda não existe — nada a travar")
        return 0
    appids = list_installed_appids()
    rc = _travar_e_contar(
        lock_games_to_pinned_proton(
            tool_name=name,
            appids=appids,
            config_vdf=vdf,
            state_path=args.state,
            todos=True,
            excluir=ler_jogos_fora_do_pino(),
            sem_entrada_de=jogos_sem_entrada_nova,
            compat_dir=compat,
        ),
        mirados=len(appids),
        prefixo="manter",
    )
    for appid in destravar_os_de_fora(config_vdf=vdf, state_path=args.state):
        print(f"[proton-pin] manter: {appid} saiu do pino (jogos_fora_do_pino.txt)")
    return rc


def _cmd_lock(args: argparse.Namespace) -> int:
    conf = _load_conf(args.conf)
    explicitos = [a.strip() for a in args.appids.split(",") if a.strip()]
    appids = explicitos or list_installed_appids()
    migrar_de = [t.strip() for t in args.migrar_de.split(",") if t.strip()]
    result = lock_games_to_pinned_proton(
        tool_name=conf["name"],
        appids=appids,
        config_vdf=args.config_vdf,
        state_path=args.state,
        dry_run=args.dry_run,
        migrar_de=migrar_de,
        todos=args.todos,
        excluir=ler_jogos_fora_do_pino(),
        sem_entrada_de=None if explicitos else jogos_sem_entrada_nova,
        compat_dir=args.compat_dir if args.compat_dir else default_compat_dir(),
    )
    return _travar_e_contar(result, mirados=len(appids), prefixo="lock")


def _travar_e_contar(
    result: dict[str, object], *, mirados: int | None, prefixo: str
) -> int:
    """Imprime o que o lock FEZ, balde por balde, e devolve o rc do CLI."""
    mudancas = result.get("changes")
    mudancas = mudancas if isinstance(mudancas, dict) else {}
    baldes: dict[str, int] = {}
    for c in mudancas.values():
        if isinstance(c, dict):
            acao = str(c.get("action", "?"))
            baldes[acao] = baldes.get(acao, 0) + 1
    resumo = ", ".join(f"{n} {a}" for a, n in sorted(baldes.items())) or "nada a mudar"
    alvo = (
        f" (de {mirados} jogos mirados + o default global)"
        if mirados is not None
        else ""
    )
    print(
        f"[proton-pin] {prefixo}: {result['status']}"
        + (f" ({result['reason']})" if result["reason"] else "")
        + f" — {resumo}{alvo}"
        + f" em {result['vdf']}"
    )
    if result["reason"] == "pino_ausente":
        print(
            f"[proton-pin] o Proton pinado não está instalado ({result.get('pino')}) "
            "— nada foi travado: apontar os jogos para uma ferramenta que não "
            "existe impediria cada um de abrir. Instale-o antes (--ensure, ou "
            "o install); o vigia da Steam trava sozinho quando ele estiver lá."
        )
        return RC_ADIADO
    if result["status"] == "recusado":
        if result["reason"] == "outra_trava_em_curso":
            print(
                "[proton-pin] outro processo do Hefesto está editando o "
                "config.vdf agora (o vigia da Steam, o install ou o botão) — "
                "nada foi travado; rode de novo em seguida."
            )
        else:
            print(
                "[proton-pin] feche a Steam (e o jogo) e rode de novo — editar o "
                "config.vdf com ela viva perderia a edição."
            )
        return 3
    if result["reason"] == "config_vdf_ausente":
        print(
            "[proton-pin] a Steam ainda não tem config.vdf (nunca entrou numa "
            "conta) — a trava espera; o vigia da Steam trava quando ela sair."
        )
        return RC_ADIADO
    return 0 if result["status"] in ("locked", "noop") else 1


def nomear_fora_do_pino(appid: int | str, *, nota: str = "") -> str:
    """Põe `appid` no `jogos_fora_do_pino.txt`. O dono da escrita, e o único.

    Status: ``"adicionado"`` | ``"ja_estava"`` | ``"appid_invalido"`` |
    ``"erro"`` — os de `add_appid_to_steam_input_allowlist`, que é quem escreve
    (as três armadilhas do formato estão resolvidas lá). Nunca levanta.

    NASCEU EM 21/09/2026 (OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01): até
    aqui só a linha de comando sabia escrever esta lista, com o cabeçalho
    privado deste módulo. A lista de exclusão precisa escrever nela também, e
    importar o cabeçalho privado seria um segundo dono do formato.

    NÃO DESPINA NA HORA: escreve a lista e só. A entrada que o jogo já tem no
    `config.vdf` sai quando a Steam fechar — o `--manter` do vigia chama
    :func:`destravar_os_de_fora` —, ou na hora, por :func:`destravar_um_jogo`.
    """
    return add_appid_to_steam_input_allowlist(
        appid,
        path=fora_do_pino_path(),
        nota=nota,
        cabecalho=_FORA_DO_PINO_HEADER,
    )


def devolver_ao_pino(appid: int | str) -> str:
    """O avesso de :func:`nomear_fora_do_pino`. Nunca levanta."""
    return remove_appid_from_steam_input_allowlist(appid, path=fora_do_pino_path())


def _cmd_fora_do_pino(args: argparse.Namespace) -> int:
    """Nomeia um jogo como fora do pino, com a data na linha de comentário."""
    appid = str(args.fora_do_pino).strip()
    status = nomear_fora_do_pino(
        appid,
        nota=f"{time.strftime('%d/%m/%Y')} — fora do Proton pinado a pedido (--fora-do-pino)",
    )
    print(f"[proton-pin] fora do pino: {appid}: {status} ({fora_do_pino_path()})")
    if status in ("appid_invalido", "erro"):
        return 1
    print(
        "[proton-pin] se ele já estava no Proton validado, volta ao de antes "
        "quando a Steam fechar; o Proton que você escolher na janela da Steam "
        "fica como está."
    )
    return 0


def _cmd_de_volta_ao_pino(args: argparse.Namespace) -> int:
    """Desfaz o `--fora-do-pino`: o próximo lock volta a alcançar o jogo."""
    appid = str(args.de_volta_ao_pino).strip()
    status = devolver_ao_pino(appid)
    print(f"[proton-pin] de volta ao pino: {appid}: {status} ({fora_do_pino_path()})")
    return 1 if status in ("appid_invalido", "erro") else 0


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
        if result["reason"] == "outra_trava_em_curso":
            print(
                "[proton-pin] outro processo do Hefesto está editando o "
                "config.vdf agora — nada foi revertido; rode de novo em seguida."
            )
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
    group.add_argument(
        "--manter",
        action="store_true",
        help="o que o vigia da Steam roda: repõe o pino do cache (sem rede) e "
             "trava todo jogo (--lock --todos); adia com a Steam aberta",
    )
    group.add_argument(
        "--fora-do-pino", default=None, metavar="APPID",
        help="nomeia um jogo como fora do Proton pinado (jogos_fora_do_pino.txt, "
             "com a data); o lock e o vigia deixam de tocá-lo",
    )
    group.add_argument(
        "--de-volta-ao-pino", default=None, metavar="APPID",
        help="desfaz o --fora-do-pino",
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
    parser.add_argument("--migrar-de", default="", metavar="TOOL,TOOL",
                        help="p/ --lock: Protons que ESTE produto pinou antes e "
                             "que devem migrar para o pino de hoje (o histórico "
                             "do registro já entra sozinho; isto é a semente da "
                             "primeira subida)")
    parser.add_argument(
        "--todos", action="store_true",
        help="--lock alcança TODO jogo que roda por Proton, inclusive os que "
             "apontam para outro Proton (ordem dela, 17/09/2026). Sem isto, "
             "entrada de jogo que aponta para fora do pino é preservada. "
             "Ferramenta que não é Proton (rodar nativo) fica sempre.")
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
        if args.manter:
            return _cmd_manter(args)
        if args.fora_do_pino is not None:
            return _cmd_fora_do_pino(args)
        if args.de_volta_ao_pino is not None:
            return _cmd_de_volta_ao_pino(args)
        return _cmd_report(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[proton-pin] ERRO: {exc}")
        return 1
    except OSError as exc:
        print(f"[proton-pin] ERRO de disco: {exc}")
        return RC_EXTRACAO_FALHOU


if __name__ == "__main__":  # pragma: no cover - entrypoint do install/uninstall
    sys.exit(main())
