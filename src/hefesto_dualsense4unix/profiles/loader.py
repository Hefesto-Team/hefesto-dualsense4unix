"""Read/write de perfis em JSON com `filelock` para evitar races.

Padrão:
    profiles = load_all_profiles()               # lista Profile
    save_profile(profile)                        # grava <slug(name)>.json
    delete_profile("shooter")                    # remove arquivo
    profile = load_profile("shooter")            # lê um específico

Paths via `hefesto_dualsense4unix.utils.xdg_paths.profiles_dir()`. Escritas fazem write
atômico (tmpfile + rename) para evitar arquivos truncados em crash.

PROFILE-SLUG-SEPARATION-01: filename é derivado de `slugify(profile.name)`.
`load_profile` aceita tanto slug direto (literal ASCII) quanto display name
acentuado via busca adaptativa em três camadas.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from filelock import FileLock
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.profiles.slug import slugify
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

logger = get_logger(__name__)

LOCK_SUFFIX = ".lock"

# PROFILE-LOADER-UX-01: exceções esperadas ao decodificar um perfil. Capturar
# essas (e só essas) preserva tracebacks de bugs reais (PermissionError,
# OSError não-ENOENT, KeyboardInterrupt) e ainda permite que perfis válidos
# sigam carregando enquanto um corrompido emite warning estruturado.
_PROFILE_DECODE_ERRORS: tuple[type[BaseException], ...] = (
    json.JSONDecodeError,
    ValidationError,
    UnicodeDecodeError,
)

# AUDIT-FINDING-PROFILE-PATH-TRAVERSAL-01: tokens proibidos em identifier.
# Path('/dir') / '/etc/passwd' devolve '/etc/passwd' (escape absoluto);
# '..' escapa relativo após resolve(). Null byte quebra syscalls de fs.
_FORBIDDEN_IDENTIFIER_TOKENS = ("/", "\\", "\x00")


def _reject_traversal(identifier: str) -> None:
    """Rejeita identifier que tente path traversal no diretório de perfis.

    Display names acentuados (ex.: "Ação Rápida") são permitidos — o pipeline
    do loader normaliza via `slugify()`. O que NÃO é permitido: separadores
    de path, componentes `..`, null bytes. Defesa em boundary antes de qualquer
    `directory / identifier`.
    """
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("identifier de perfil vazio ou inválido")
    for token in _FORBIDDEN_IDENTIFIER_TOKENS:
        if token in identifier:
            raise ValueError(
                f"identifier de perfil contém caractere proibido: {token!r}"
            )
    # '..' em qualquer posição (ex.: '../x', 'x/..', '..', '..bar', 'foo..bar').
    # Display names legítimos nunca contêm '..'; separadores já foram rejeitados.
    if ".." in identifier:
        raise ValueError("identifier de perfil contém sequência '..'")


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + LOCK_SUFFIX)


# FIX-PACKAGING-SEED-PARITY-01: semeadura em RUNTIME dos presets default.
# O caminho nativo roda scripts/install_profiles.sh no install.sh, mas o .deb e
# o AppImage não têm gancho por-usuário (o postinst roda como root e não conhece
# o $HOME de quem vai usar) — sem isto, quem instala pelo .deb nunca recebe
# sackboy_nativo/coop_local/point_and_click etc. A semântica é IDÊNTICA à do
# shell script (copy-if-absent + marker `.seeded_presets` que respeita deleção
# proposital da usuária); o formato do marker (um filename por linha) é contrato
# COMPARTILHADO entre os dois semeadores — mantê-los em sincronia.
SEED_MARKER_NAME = ".seeded_presets"

# Opt-out explícito da semeadura automática ("1" desliga). Usado pela suíte de
# testes (hermetismo: um teste que carrega perfis não pode receber os presets
# do repo no seu tmp) e disponível para quem quiser um config 100% manual.
SEED_SKIP_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"

# Fontes candidatas, na ordem: assets/ do repo (dev / install editável via
# install.sh), o share RELATIVO ao interpretador (AppImage/venv — sys.prefix
# aponta para dentro do bundle montado, mesmo padrão dos glyphs) e o share do
# sistema (.deb — build_deb.sh copia assets/ inteiro para
# /usr/share/hefesto-dualsense4unix/assets/). A primeira que existir vence;
# nenhuma existente → no-op silencioso.
_DEFAULT_SEED_SOURCE_DIRS: tuple[Path, ...] = (
    Path(__file__).resolve().parents[3] / "assets" / "profiles_default",
    Path(sys.prefix) / "share" / "hefesto-dualsense4unix" / "assets"
    / "profiles_default",
    Path("/usr/share/hefesto-dualsense4unix/assets/profiles_default"),
)

# Flag once-per-process: a semeadura roda no máximo uma vez por processo
# (daemon, GUI, CLI…), na primeira carga de perfis.
_seed_attempted: bool = False


def _seed_source_file(
    fname: str, source_dirs: Sequence[Path] | None = None
) -> Path | None:
    """Resolve um asset de preset no primeiro diretório-fonte existente.

    Mesma cascata de `seed_default_presets` (repo editable → prefix → /usr).
    None se nenhum diretório existe ou o arquivo não está em nenhum deles.
    """
    candidates = _DEFAULT_SEED_SOURCE_DIRS if source_dirs is None else tuple(source_dirs)
    for base in candidates:
        p = base / fname
        if p.is_file():
            return p
    return None


def seed_default_presets(
    dest_dir: Path | None = None,
    source_dirs: Sequence[Path] | None = None,
) -> list[str]:
    """Copia presets default AUSENTES para o diretório de perfis do usuário.

    Réplica fiel de scripts/install_profiles.sh (INSTALL-PROFILES-COPY-IF-
    ABSENT-01 + INSTALL-PROFILES-RESPECT-DELETION-01):

    - NUNCA sobrescreve um perfil existente (preserva edições da usuária).
    - O marker `.seeded_presets` registra cada preset já semeado: um preset
      que a usuária DELETOU de propósito não é ressuscitado.
    - Preset já presente na 1ª execução (instalação antiga/editado) é
      registrado no marker SEM cópia — deleções posteriores são respeitadas.

    Usa o primeiro diretório existente de `source_dirs`; nenhum existente →
    no-op (retorna lista vazia). Paths injetáveis para testes herméticos.
    Retorna os filenames efetivamente copiados.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    candidates = _DEFAULT_SEED_SOURCE_DIRS if source_dirs is None else tuple(source_dirs)
    source = next((c for c in candidates if c.is_dir()), None)
    if source is None:
        return []

    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / SEED_MARKER_NAME
    copied: list[str] = []
    # FileLock serializa daemon + GUI semeando ao mesmo tempo no primeiro boot.
    with FileLock(str(_lock_path(marker))):
        seeded: set[str] = set()
        if marker.exists():
            seeded = set(marker.read_text(encoding="utf-8").splitlines())
        new_entries: list[str] = []
        for src in sorted(source.glob("*.json")):
            fname = src.name
            # Já semeado antes → respeita a decisão da usuária (inclusive deletar).
            if fname in seeded:
                continue
            dest = directory / fname
            if dest.exists():
                # Presente na 1ª execução: registra sem copiar.
                new_entries.append(fname)
                continue
            shutil.copyfile(src, dest)
            new_entries.append(fname)
            copied.append(fname)
        # Espelha o `touch` do shell script: o marker passa a existir mesmo
        # quando nada foi copiado (registra que a semeadura já rodou aqui).
        if new_entries or not marker.exists():
            with marker.open("a", encoding="utf-8") as fh:
                for fname in new_entries:
                    fh.write(f"{fname}\n")
    if copied:
        logger.info("presets_seeded", copied=copied, source=str(source))
    return copied


#: SPRINT-GAME-RUMBLE-01: presets de jogo cuja máscara migrou dualsense->xbox
#: (a DualSense faz o jogo ignorar o vpad e matar a vibração). Marker próprio para
#: a migração rodar UMA vez em quem já tinha o preset semeado com o valor antigo.
_FLAVOR_MIGRATION_MARKER = ".flavor_xbox_migrated"
_FLAVOR_MIGRATION_PRESETS = ("sackboy_nativo.json", "coop_local.json")


def migrate_game_presets_to_xbox(dest_dir: Path | None = None) -> list[str]:
    """One-shot: troca `gamepad_flavor` dualsense->xbox nos presets de JOGO.

    H1 da auditoria: `seed_default_presets` NUNCA sobrescreve, então quem já tinha
    `sackboy_nativo`/`coop_local` semeados com `dualsense` continuaria com a
    vibração morta mesmo após o bump. Esta migração corrige o valor UMA vez.

    Conservadora: só reescreve quando o preset ainda está EXATAMENTE em
    `"gamepad_flavor": "dualsense"` dentro de um `mode.kind=="gamepad"` — se a
    usuária mudou o modo/flavor na mão, não toca. Idempotente via marker próprio.
    Best-effort: falha loga e segue. Retorna os arquivos migrados.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _FLAVOR_MIGRATION_MARKER
    if marker.exists():
        return []
    migrated: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return []
        for fname in _FLAVOR_MIGRATION_PRESETS:
            path = directory / fname
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            mode = data.get("mode")
            if (
                isinstance(mode, dict)
                and mode.get("kind") == "gamepad"
                and mode.get("gamepad_flavor") == "dualsense"
            ):
                mode["gamepad_flavor"] = "xbox"
                with contextlib.suppress(Exception):
                    path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    migrated.append(fname)
        with contextlib.suppress(Exception):
            marker.write_text("xbox\n", encoding="utf-8")
    if migrated:
        logger.info("game_presets_flavor_migrated", files=migrated)
    return migrated


#: R-12 (auditoria 23/07): marker da migração do `match` inalcançável do
#: coop_local. O preset de fábrica de 14/07 saiu com `MatchCriteria` de campos
#: TODOS vazios — `matches()` devolve False sem condição alguma (schema.py:52),
#: então o autoswitch NUNCA o escolhe. O asset novo tem o regex de jogos de
#: co-op; `seed_default_presets` não sobrescreve (está no `.seeded_presets`),
#: então o arquivo LOCAL de quem já tinha o preset velho fica preso — por isso
#: esta migração one-shot.
_COOP_LOCAL_MATCH_MIGRATION_MARKER = ".coop_local_match_migrated"


def migrate_coop_local_match(dest_dir: Path | None = None) -> list[str]:
    """One-shot: dá um `match` alcançável ao coop_local que veio VAZIO de fábrica.

    R-12 (auditoria 23/07). Só reescreve quando o preset ainda está EXATAMENTE
    no estado inalcançável de fábrica — `MatchCriteria` com os três campos
    vazios/ausentes E `mode.kind == "gamepad"` com `coop: true` (isto é:
    intocado pela usuária). Qualquer edição dela = não toca. Copia `match` e
    `priority` do ASSET (a fonte da verdade), sem mexer em cor/gatilho/mode.

    Idempotente via marker próprio. Best-effort: falha loga e segue. Retorna
    os arquivos migrados.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _COOP_LOCAL_MATCH_MIGRATION_MARKER
    if marker.exists():
        return []
    migrated: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return []
        path = directory / "coop_local.json"
        asset = _seed_source_file("coop_local.json")
        if path.is_file() and asset is not None:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                asset_data = json.loads(asset.read_text(encoding="utf-8"))
            except Exception:
                data = asset_data = None
            if data is not None and _coop_local_intocado(data):
                data["match"] = asset_data.get("match", data.get("match"))
                data["priority"] = asset_data.get("priority", data.get("priority"))
                with contextlib.suppress(Exception):
                    path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    migrated.append("coop_local.json")
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    if migrated:
        logger.info("coop_local_match_migrated", files=migrated)
    return migrated


def _coop_local_intocado(data: dict[str, object]) -> bool:
    """True quando o coop_local ainda está no estado de fábrica inalcançável.

    Match `criteria` com os três campos vazios/ausentes E `mode.kind=="gamepad"`
    com `coop: true`. Qualquer desvio = a usuária mexeu, e a migração recua.
    """
    match = data.get("match")
    if not isinstance(match, dict) or match.get("type") != "criteria":
        return False
    if (
        match.get("window_class")
        or match.get("window_title_regex")
        or match.get("process_name")
    ):
        return False
    mode = data.get("mode")
    return (
        isinstance(mode, dict)
        and mode.get("kind") == "gamepad"
        and bool(mode.get("coop", False))
    )


#: LEIGO-01: marker da migração do default de `mode.coop` (False -> True).
_COOP_DEFAULT_MIGRATION_MARKER = ".coop_default_on_migrated"


def migrate_profiles_coop_default(dest_dir: Path | None = None) -> list[str]:
    """One-shot: apaga o `"coop": false` herdado do default antigo dos perfis.

    LEIGO-01: até aqui `ProfileModeConfig.coop` nascia False, então **todo**
    perfil salvo pela GUI gravava `"coop": false` — e ativá-lo desligava o co-op
    da usuária sem ela ter pedido nada. Trocar o default no esquema não basta:
    os `false` já GRAVADOS continuam no disco e continuariam vencendo. Com o
    checkbox fora da tela, não sobraria caminho para religar.

    Apaga a chave em vez de gravar `true`: o perfil passa a **herdar** o padrão,
    então um default futuro volta a valer sem uma segunda migração.

    Conservadora: só toca em seções `mode.kind == "gamepad"` com `coop` ainda
    exatamente em `false` — é a única combinação que desliga o co-op ao ativar
    (os outros kinds nem leem o campo). Idempotente via marker próprio.
    Best-effort: falha loga e segue. Retorna os arquivos migrados.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _COOP_DEFAULT_MIGRATION_MARKER
    if marker.exists():
        return []
    migrated: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return []
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            mode = data.get("mode")
            if (
                isinstance(mode, dict)
                and mode.get("kind") == "gamepad"
                and mode.get("coop") is False
            ):
                del mode["coop"]
                with contextlib.suppress(Exception):
                    path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    migrated.append(path.name)
        with contextlib.suppress(Exception):
            marker.write_text("coop-default-on\n", encoding="utf-8")
    if migrated:
        logger.info("profiles_coop_default_migrated", files=migrated)
    return migrated


def _maybe_seed_presets() -> None:
    """Dispara a semeadura uma vez por processo, antes da primeira carga.

    Best-effort por contrato: uma falha aqui (disco cheio, permissão, marker
    corrompido) NUNCA pode impedir a carga dos perfis existentes — loga warning
    e segue. O flag é marcado ANTES da tentativa para não re-tentar em loop a
    cada `load_*` num ambiente permanentemente quebrado.
    """
    global _seed_attempted
    if _seed_attempted or os.environ.get(SEED_SKIP_ENV_VAR) == "1":
        return
    _seed_attempted = True
    try:
        seed_default_presets()
        # H1: corrige a máscara dos presets de jogo já semeados (one-shot).
        with contextlib.suppress(Exception):
            migrate_game_presets_to_xbox()
        # LEIGO-01: apaga o `coop: false` que o default antigo gravou (one-shot).
        with contextlib.suppress(Exception):
            migrate_profiles_coop_default()
        # R-12: dá um match alcançável ao coop_local que veio vazio de fábrica
        # (o preset de 14/07 era inalcançável pelo autoswitch). One-shot.
        with contextlib.suppress(Exception):
            migrate_coop_local_match()
    except Exception as exc:  # boundary best-effort (ver docstring)
        logger.warning(
            "presets_seed_failed",
            err=str(exc),
            err_type=type(exc).__name__,
        )


def _profile_path(identifier: str | Profile) -> Path:
    """Resolve filename a partir de slug direto ou de Profile.

    - Se `identifier` é `Profile`, deriva slug de `profile.name`.
    - Se `identifier` é `str`, assume que já é slug (ou filename ASCII).
    """
    if isinstance(identifier, Profile):
        return profiles_dir(ensure=True) / f"{slugify(identifier.name)}.json"
    _reject_traversal(identifier)
    return profiles_dir(ensure=True) / f"{identifier}.json"


def _read_profile(path: Path) -> Profile:
    with FileLock(str(_lock_path(path))):
        raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


def load_profile(identifier: str) -> Profile:
    """Carrega perfil por slug direto ou por display name.

    Ordem de busca:
    1. `<identifier>.json` direto (assume que `identifier` já é slug/filename).
    2. `<slugify(identifier)>.json` (se `identifier` era display name acentuado).
    3. Varredura fallback: itera o diretório buscando `profile.name` cujo
       slug bata com `slugify(identifier)`. Cobre arquivos cujo filename
       não acompanhou o slug atual (ex.: `meu-perfil.json` com name "Meu Perfil").
    """
    _reject_traversal(identifier)
    _maybe_seed_presets()
    directory = profiles_dir(ensure=True)
    direct = directory / f"{identifier}.json"
    # Defesa em profundidade: mesmo após rejeição de tokens, confirmar que o
    # path resolvido não escapa do diretório de perfis (ex.: symlink hostil).
    directory_resolved = directory.resolve()
    if not direct.resolve().is_relative_to(directory_resolved):
        raise ValueError("identifier de perfil escapa do diretório de perfis")
    if direct.exists():
        return _read_profile(direct)

    try:
        slug = slugify(identifier)
    except ValueError:
        raise FileNotFoundError(f"perfil não encontrado: {identifier}") from None

    slugged = directory / f"{slug}.json"
    if slugged.exists():
        return _read_profile(slugged)

    # `sorted` torna a varredura determinística (importante para testes e logs
    # reproduzíveis quando múltiplos perfis existem).
    for path in sorted(directory.glob("*.json")):
        try:
            profile = _read_profile(path)
        except _PROFILE_DECODE_ERRORS as exc:
            logger.warning(
                "profile_invalid",
                path=str(path),
                err=str(exc),
                err_type=type(exc).__name__,
            )
            continue
        try:
            if slugify(profile.name) == slug:
                return profile
        except ValueError:
            continue

    raise FileNotFoundError(f"perfil não encontrado: {identifier}")


def load_all_profiles() -> list[Profile]:
    """Lê todos os perfis JSON do diretório, pulando os inválidos com warning.

    PROFILE-LOADER-UX-01: um perfil corrompido não deve impedir o carregamento
    dos demais. Emite `WARN profile_invalid path=... err=...` para cada arquivo
    que falhar a decodificação ou validação Pydantic.
    """
    _maybe_seed_presets()
    directory = profiles_dir(ensure=True)
    profiles: list[Profile] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with FileLock(str(_lock_path(path))):
                raw = json.loads(path.read_text(encoding="utf-8"))
            profiles.append(Profile.model_validate(raw))
        except _PROFILE_DECODE_ERRORS as exc:
            logger.warning(
                "profile_invalid",
                path=str(path),
                err=str(exc),
                err_type=type(exc).__name__,
            )
            continue
    return profiles


def audit_profiles() -> list[tuple[str, str]]:
    """Valida todos os perfis sem carregá-los para uso, coletando os inválidos.

    FEAT-CONFIG-AUDIT-BOOT-01: usado no boot para AVISAR sobre perfis corrompidos
    em vez de só pulá-los no fallback. Retorna [(nome, erro)] dos perfis que
    falham decode/validação. Nunca levanta.
    """
    # Semeia ANTES de auditar: no primeiro boot pós-.deb, os presets precisam
    # existir quando o daemon montar o relatório de perfis.
    _maybe_seed_presets()
    directory = profiles_dir(ensure=True)
    invalid: list[tuple[str, str]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with FileLock(str(_lock_path(path))):
                raw = json.loads(path.read_text(encoding="utf-8"))
            Profile.model_validate(raw)
        except _PROFILE_DECODE_ERRORS as exc:
            invalid.append((path.name, f"{type(exc).__name__}: {exc}"))
    return invalid


def save_profile(profile: Profile) -> Path:
    """Grava perfil em `<slugify(profile.name)>.json` de forma atômica.

    PERFIL-02 (sprint perfis-por-controle): o campo aditivo ``controllers``
    é OMITIDO do JSON quando None/vazio — requisito de COMPATIBILIDADE, não
    estética. `model_dump` sem exclude emitiria ``"controllers": null`` em
    TODO save, e binário antigo (``extra="forbid"``) rejeitaria TODO perfil
    no downgrade; com a omissão, só perfis que USAM o mapa ficam
    incompatíveis, e perfis antigos seguem round-trip load→save sem ganhar
    a chave.

    Fix do review (2026-07-16, MED): as ENTRADAS do mapa são serializadas
    com ``exclude_unset`` — um override PARCIAL escrito à mão (só
    ``lightbar``, só ``left``...) continua parcial no disco. O dump denso
    marcava os defaults do schema como explícitos no próximo load e a
    ativação pisava o global do controle (player-LEDs apagados, brilho 1.0)
    — a resolução-por-objeto refutada pelo sprint doc, reintroduzida pela
    serialização. Overrides criados pela GUI são densos por semeadura (o que
    ela vê é o que salva) e saem com os mesmos campos de antes; a única
    diferença cosmética é a seção nunca-escrita (ex.: ``"triggers": null``)
    deixar de aparecer — o load é semanticamente idêntico.
    """
    path = _profile_path(profile)
    payload = profile.model_dump(mode="json")
    if not payload.get("controllers"):
        payload.pop("controllers", None)
    else:
        payload["controllers"] = {
            uniq: cfg.model_dump(mode="json", exclude_unset=True)
            for uniq, cfg in (profile.controllers or {}).items()
        }
    with FileLock(str(_lock_path(path))):
        _atomic_write_json(path, payload)
    return path


def delete_profile(identifier: str) -> None:
    """Remove o arquivo do perfil. Aceita slug ou display name.

    Resolve o path via `load_profile` para garantir que o filename correto
    seja alvo do unlink — importante para perfis cujo filename não casa
    com o slug do `name` atual.
    """
    try:
        profile = load_profile(identifier)
    except FileNotFoundError:
        raise FileNotFoundError(f"perfil não encontrado: {identifier}") from None

    directory = profiles_dir(ensure=True)
    slug = slugify(profile.name)
    candidate = directory / f"{slug}.json"
    if not candidate.exists():
        direct = directory / f"{identifier}.json"
        if direct.exists():
            candidate = direct
        else:
            for path in directory.glob("*.json"):
                try:
                    other = _read_profile(path)
                except _PROFILE_DECODE_ERRORS as exc:
                    logger.warning(
                        "profile_invalid",
                        path=str(path),
                        err=str(exc),
                        err_type=type(exc).__name__,
                    )
                    continue
                if other.name == profile.name:
                    candidate = path
                    break

    with FileLock(str(_lock_path(candidate))):
        candidate.unlink()


def _atomic_write_json(target: Path, payload: object) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink(missing_ok=True)
        raise


__all__ = [
    "SEED_MARKER_NAME",
    "SEED_SKIP_ENV_VAR",
    "delete_profile",
    "load_all_profiles",
    "load_profile",
    "migrate_coop_local_match",
    "migrate_game_presets_to_xbox",
    "migrate_profiles_coop_default",
    "save_profile",
    "seed_default_presets",
]
