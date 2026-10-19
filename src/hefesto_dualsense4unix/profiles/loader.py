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
acentuado; o arquivo é o que `arquivo_do_perfil` acha, em quatro pernas.
"""
from __future__ import annotations

import asyncio
import calendar
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from filelock import FileLock
from pydantic import ValidationError

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.core.formas_do_endereco import mascarar as _mascarar
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.slug import slugify
from hefesto_dualsense4unix.profiles.steam_app import (
    e_janela_do_cliente_steam,
    steam_appid_from_wm_class,
)
from hefesto_dualsense4unix.utils.leitura_pela_assinatura import LeituraPelaAssinatura
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import bases_de_instalacao
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal

logger = get_logger(__name__)

LOCK_SUFFIX = ".lock"

_PROFILE_DECODE_ERRORS: tuple[type[BaseException], ...] = (
    json.JSONDecodeError,
    ValidationError,
    UnicodeDecodeError,
)

_FORBIDDEN_IDENTIFIER_TOKENS = ("/", "\\", "\x00")


def _reject_traversal(identifier: str) -> None:
    """Rejeita identifier que tente path traversal no diretório de perfis."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("identifier de perfil vazio ou inválido")
    for token in _FORBIDDEN_IDENTIFIER_TOKENS:
        if token in identifier:
            raise ValueError(
                f"identifier de perfil contém caractere proibido: {token!r}"
            )
    if ".." in identifier:
        raise ValueError("identifier de perfil contém sequência '..'")


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + LOCK_SUFFIX)


# FIX-PACKAGING-SEED-PARITY-01: semeadura em RUNTIME dos presets default.
SEED_MARKER_NAME = ".seeded_presets"

# em 05/09: 33 perfis, e SÓ DOIS são catch-all (`fallback` prio 0 e
NOME_DO_PADRAO = "Freestyle"
ARQUIVO_DO_PADRAO = "freestyle.json"
SLUG_DO_PADRAO = "freestyle"
NOME_DO_PERSONALIZADO = "Personalizado"
ARQUIVO_DO_PERSONALIZADO = "personalizado.json"
SLUG_DO_PERSONALIZADO = "personalizado"
NOME_ANTIGO_DO_PADRAO = "meu_perfil"
ARQUIVO_ANTIGO_DO_PADRAO = "meu_perfil.json"

BACKUP_DO_PADRAO = "meu_perfil.json.antes-de-personalizado"

_RENAME_PADRAO_MARKER = ".perfil_padrao_renomeado"

SEED_SKIP_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"

def _fontes_de_fabrica(subpasta: str) -> tuple[Path, ...]:
    """Onde mora `assets/<subpasta>` nesta instalação: as bases de `repo_files`.

    A pergunta «o que esta instalação tem ao lado do código?» tem UM dono
    (`bases_de_instalacao`): o checkout, o `share/` do venv ou do pipx, o
    `/app/share` do Flatpak, o `share/` do usuário e o `/usr/share` dos pacotes.
    Uma lista própria aqui deixava de fora o que o dono já sabia.
    """
    return tuple(base / "assets" / subpasta for base in bases_de_instalacao())


_DEFAULT_SEED_SOURCE_DIRS: tuple[Path, ...] = _fontes_de_fabrica("profiles_default")

_ESTILO_DE_JOGO_SOURCE_DIRS: tuple[Path, ...] = _fontes_de_fabrica("estilos_de_jogo")

ARQUIVOS_DOS_ESTILOS_DE_JOGO: tuple[str, ...] = (
    "acao.json",
    "aventura.json",
    "corrida.json",
    "esportes.json",
    "fallback.json",
    "fps.json",
    "navegacao.json",
    "point_and_click.json",
)


@dataclass(frozen=True)
class MoldeDePerfil:
    """Um molde de fábrica da tela «Mapa do controle»: o ponto de partida de um perfil de botões.

    O molde NÃO é arquivo: não semeia nada em `~/.config`, não aparece na aba Perfis e não casa
    com janela. Escolhê-lo na tela e guardar cria um perfil de verdade (`perfil_do_molde`), dela,
    com o nome que ela der. Os nomes são os MESMOS da lista «Perfil jogo - navegação» da
    aba Navegação (a régua `test_a_aba_mapa_do_controle_do_todo` confere os dois lados).
    """

    chave: str
    nome: str
    button_actions: Mapping[str, str]
    velocidade: int = 8
    rolagem: int = 1


#: O que cada molde troca, só em fichas que o motor sabe fazer (`core/acoes_de_botao.ACOES`).
#: O resto herda o de fábrica, como em todo `button_actions`.
MOLDES_DE_PERFIL: tuple[MoldeDePerfil, ...] = (
    MoldeDePerfil("point_and_click", "Point and click", {
        "cross": "BTN_LEFT", "circle": "BTN_RIGHT", "triangle": "KEY_ESC",
        "l3_direcao": "__CURSOR__", "r3_direcao": "__ROLAGEM__"}),
    MoldeDePerfil("visual_novel", "Visual novel", {
        "cross": "BTN_LEFT", "circle": "BTN_RIGHT", "square": "KEY_LEFTCTRL",
        "triangle": "KEY_ESC", "l3_direcao": "__CURSOR__", "r3_direcao": "__ROLAGEM__"}),
    # AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01 (N6): o Adulto nasce com o mapa do Visual novel, que é
    # o jeito de jogar dos dois (decisão por delegação, a validar pelo usuário).
    MoldeDePerfil("adulto", "Adulto", {
        "cross": "BTN_LEFT", "circle": "BTN_RIGHT", "square": "KEY_LEFTCTRL",
        "triangle": "KEY_ESC", "l3_direcao": "__CURSOR__", "r3_direcao": "__ROLAGEM__"}),
    MoldeDePerfil("mouse", "Mouse", {
        "cross": "BTN_LEFT", "circle": "BTN_RIGHT",
        "l3_direcao": "__CURSOR__", "r3_direcao": "__ROLAGEM__"}),
    MoldeDePerfil("mouse_e_teclado", "Mouse e teclado", {
        "cross": "BTN_LEFT", "circle": "KEY_ESC", "square": "KEY_SPACE",
        "triangle": "KEY_ENTER", "dpad_up": "KEY_UP", "dpad_down": "KEY_DOWN",
        "dpad_left": "KEY_LEFT", "dpad_right": "KEY_RIGHT", "l3_direcao": "__CURSOR__"}),
)

MOLDE_POR_CHAVE: dict[str, MoldeDePerfil] = {m.chave: m for m in MOLDES_DE_PERFIL}


def perfil_do_molde(chave: str, nome: str, *, prioridade: int = 0) -> Profile:
    """O perfil novo que o molde ``chave`` faz nascer, só-manual até ela dar um jogo a ele."""
    from hefesto_dualsense4unix.profiles.schema import MatchManual, ProfileMouseConfig

    molde = MOLDE_POR_CHAVE[chave]
    return Profile(
        name=nome,
        match=MatchManual(),
        priority=prioridade,
        button_actions=dict(molde.button_actions),
        mouse=ProfileMouseConfig(
            enabled=True, speed=molde.velocidade, scroll_speed=molde.rolagem),
    )

ESTILOS_DE_JOGO_DIR_NAME = "estilos-de-jogo"

_ESTILOS_MIGRATION_MARKER = ".generos_viraram_estilo_de_jogo"

_seed_attempted: bool = False

# Uma vez por processo: a falta da fábrica não pode ser muda, nem inundar o diário.
_sem_fonte_avisada: bool = False


def _seed_source_file(
    fname: str, source_dirs: Sequence[Path] | None = None
) -> Path | None:
    """Resolve um asset de preset no primeiro diretório-fonte existente."""
    candidates = (
        (*_DEFAULT_SEED_SOURCE_DIRS, *_ESTILO_DE_JOGO_SOURCE_DIRS)
        if source_dirs is None
        else tuple(source_dirs)
    )
    for base in candidates:
        p = base / fname
        if p.is_file():
            return p
    return None


def seed_default_presets(
    dest_dir: Path | None = None,
    source_dirs: Sequence[Path] | None = None,
) -> list[str]:
    """Copia presets default AUSENTES para o diretório de perfis do usuário."""
    global _sem_fonte_avisada
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    candidates = _DEFAULT_SEED_SOURCE_DIRS if source_dirs is None else tuple(source_dirs)
    source = next((c for c in candidates if c.is_dir()), None)
    if source is None:
        if not _sem_fonte_avisada:
            _sem_fonte_avisada = True
            logger.warning(
                "perfis_de_fabrica_sem_fonte",
                bases=[str(c) for c in candidates],
                efeito="o Freestyle e os estilos de jogo de fábrica não foram semeados",
            )
        return []

    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / SEED_MARKER_NAME
    copied: list[str] = []
    with FileLock(str(_lock_path(marker))):
        seeded: set[str] = set()
        if marker.exists():
            seeded = set(marker.read_text(encoding="utf-8").splitlines())
        new_entries: list[str] = []
        for src in sorted(source.glob("*.json")):
            fname = src.name
            if fname in seeded:
                continue
            if fname == ARQUIVO_DO_PADRAO and _o_slot_dela_tem_nome_antigo(directory):
                new_entries.append(fname)
                continue
            dest = directory / fname
            if dest.exists():
                new_entries.append(fname)
                continue
            shutil.copyfile(src, dest)
            new_entries.append(fname)
            copied.append(fname)
        if new_entries or not marker.exists():
            with marker.open("a", encoding="utf-8") as fh:
                for fname in new_entries:
                    fh.write(f"{fname}\n")
    if copied:
        logger.info("presets_seeded", copied=copied, source=str(source))
    return copied


# justificada pela H1 da auditoria pré-release ("a máscara DualSense faz o jogo


def _repontar_a_sessao_para_o_padrao_novo() -> None:
    """Faz `session.json` e `active_profile.txt` seguirem o perfil renomeado."""
    from hefesto_dualsense4unix.utils.session import (
        load_last_profile,
        read_active_marker,
        save_active_marker,
        save_last_profile,
    )

    with contextlib.suppress(Exception):
        if load_last_profile() == NOME_ANTIGO_DO_PADRAO:
            save_last_profile(NOME_DO_PADRAO)
    with contextlib.suppress(Exception):
        if read_active_marker() == NOME_ANTIGO_DO_PADRAO:
            save_active_marker(NOME_DO_PADRAO)


def migrate_default_profile_name(dest_dir: Path | None = None) -> str | None:
    """One-shot: o perfil padrão deixa de se chamar `meu_perfil`."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _RENAME_PADRAO_MARKER
    if marker.exists():
        return None
    antigo = directory / ARQUIVO_ANTIGO_DO_PADRAO
    novo = directory / ARQUIVO_DO_PADRAO
    renomeado: str | None = None
    desfecho = "sem_perfil_antigo"
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return None
        if (novo.exists() and antigo.is_file()
                and not _e_o_de_fabrica_intocado(novo)):
            desfecho = "padrao_ja_existe"
        elif antigo.is_file():
            dados: object = None
            try:
                dados = json.loads(antigo.read_text(encoding="utf-8"))
            except Exception as exc:
                desfecho = "ilegivel"
                logger.warning("perfil_padrao_rename_ilegivel", err=str(exc))
            if isinstance(dados, dict):
                if dados.get("name") == NOME_ANTIGO_DO_PADRAO:
                    dados["name"] = NOME_DO_PADRAO
                    _o_freestyle_vale_fora_do_jogo(dados)
                    fd, tmp = tempfile.mkstemp(
                        dir=str(directory), prefix=".personalizado_"
                    )
                    try:
                        os.write(
                            fd,
                            (
                                json.dumps(dados, ensure_ascii=False, indent=2)
                                + "\n"
                            ).encode("utf-8"),
                        )
                    finally:
                        os.close(fd)
                    os.replace(tmp, novo)
                    antigo.replace(directory / BACKUP_DO_PADRAO)
                    renomeado = NOME_DO_PADRAO
                    desfecho = "renomeado"
                else:
                    desfecho = "nome_mudado_pela_usuaria"
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    if renomeado:
        _repontar_a_sessao_para_o_padrao_novo()
    logger.info(
        "perfil_padrao_renomeado",
        desfecho=desfecho,
        de=NOME_ANTIGO_DO_PADRAO,
        para=NOME_DO_PADRAO if renomeado else None,
        backup=BACKUP_DO_PADRAO if renomeado else None,
    )
    return renomeado



_PERSONALIZADO_VIROU_FREESTYLE_MARKER = ".personalizado_virou_freestyle"


def _o_slot_dela_tem_nome_antigo(directory: Path) -> bool:
    """O padrão de produto ainda mora sob `meu_perfil.json` ou `personalizado.json`?"""
    return any((directory / nome).exists()
               for nome in (ARQUIVO_ANTIGO_DO_PADRAO, ARQUIVO_DO_PERSONALIZADO))


def _fabrica_antiga(
    prioridade: int,
    barra: list[int],
    lampadas: list[bool],
    brilho: float,
    *,
    com_teclas: bool,
    gatilho: dict[str, object] | None = None,
) -> dict[str, object]:
    """Uma versão que a fábrica JÁ ENTREGOU para o lugar do padrão, com o nome de hoje."""
    lado = gatilho if gatilho is not None else {"mode": "Off", "params": []}
    dados: dict[str, object] = {
        "name": NOME_DO_PADRAO,
        "version": 1,
        "match": {"type": "any"},
        "priority": prioridade,
        "triggers": {"left": dict(lado), "right": dict(lado)},
        "leds": {"lightbar": barra, "player_leds": lampadas,
                 "lightbar_brightness": brilho},
        "rumble": {"passthrough": True},
    }
    if com_teclas:
        dados["key_bindings"] = None
    return dados


_FABRICAS_ANTERIORES_DO_FREESTYLE: tuple[dict[str, object], ...] = (
    _fabrica_antiga(5, [97, 53, 131], [True, False, False, False, False], 1.0,
                    com_teclas=False),
    _fabrica_antiga(0, [40, 80, 180], [False, False, True, False, False], 0.4,
                    com_teclas=False),
    _fabrica_antiga(0, [40, 80, 180], [False, False, True, False, False], 0.4,
                    com_teclas=True),
    _fabrica_antiga(1, [40, 80, 180], [False, False, True, False, False], 0.4,
                    com_teclas=True),
    _fabrica_antiga(1, [40, 80, 180], [False, False, True, False, False], 1.0,
                    com_teclas=True),
    _fabrica_antiga(1, [40, 80, 180], [False, False, True, False, False], 1.0,
                    com_teclas=True,
                    gatilho={"mode": "Rigid", "params": [5, 200]}),
)


def _e_o_de_fabrica_intocado(path: Path) -> bool:
    """`freestyle.json` é UMA cópia de fábrica, sem nenhum ajuste dela?"""
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if dados in _FABRICAS_ANTERIORES_DO_FREESTYLE:
        return True
    asset = _seed_source_file(ARQUIVO_DO_PADRAO)
    if asset is None:
        return False
    try:
        return bool(dados == json.loads(asset.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def _o_freestyle_vale_fora_do_jogo(dados: dict[str, object]) -> None:
    """A regra que só aponta a janela do PRÓPRIO Hefesto vira `any` — no lugar."""
    match = dados.get("match")
    if not isinstance(match, dict) or match.get("type") != "criteria":
        return
    if match.get("window_title_regex") or match.get("process_name"):
        return
    classes = match.get("window_class")
    if not isinstance(classes, list) or not classes:
        return
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    if all(isinstance(c, str) and c.strip().casefold() in OWN_GUI_WM_CLASSES
           for c in classes):
        dados["match"] = {"type": "any"}


def _e_o_personalizado(nome: object) -> bool:
    """O nome guardado aponta o Personalizado? Por slug, sem levantar."""
    if not isinstance(nome, str) or not nome.strip():
        return False
    try:
        return slugify(nome) == SLUG_DO_PERSONALIZADO
    except ValueError:
        return False


def _repontar_a_sessao_do_personalizado() -> None:
    """`session.json` e `active_profile.txt` passam a apontar o «Freestyle»."""
    from hefesto_dualsense4unix.utils.session import (
        load_last_profile,
        read_active_marker,
        save_active_marker,
        save_last_profile,
    )

    with contextlib.suppress(Exception):
        if _e_o_personalizado(load_last_profile()):
            save_last_profile(NOME_DO_PADRAO)
    with contextlib.suppress(Exception):
        if _e_o_personalizado(read_active_marker()):
            save_active_marker(NOME_DO_PADRAO)


def _trocar_o_personalizado(directory: Path) -> tuple[str, Path | None]:
    """O miolo da troca, com os dois locks já tomados. Devolve `(desfecho, cópia)`."""
    antigo = directory / ARQUIVO_DO_PERSONALIZADO
    novo = directory / ARQUIVO_DO_PADRAO
    bruto = _bytes_se_existe(antigo)
    if bruto is None:
        return "sem_personalizado", None
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        logger.warning("personalizado_ilegivel", err=str(exc))
        return "ilegivel", None
    if not isinstance(dados, dict):
        return "ilegivel", None
    if not _e_o_personalizado(dados.get("name")):
        return "nome_mudado_pela_usuaria", None
    if novo.exists() and not _e_o_de_fabrica_intocado(novo):
        return "freestyle_ja_existe", None
    copia = _arquivar_versao(SLUG_DO_PERSONALIZADO, bruto, raiz=directory)
    if copia is None:
        return "sem_copia", None
    dados["name"] = NOME_DO_PADRAO
    _o_freestyle_vale_fora_do_jogo(dados)
    _atomic_write_json(novo, dados)
    antigo.unlink()
    return "renomeado", copia


def o_personalizado_vira_freestyle(dest_dir: Path | None = None) -> Path | None:
    """One-shot: o `personalizado.json` vira o `freestyle.json`, com a cópia."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _PERSONALIZADO_VIROU_FREESTYLE_MARKER
    if marker.exists():
        return None
    antigo = directory / ARQUIVO_DO_PERSONALIZADO
    copia: Path | None = None
    desfecho = "sem_personalizado"
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return None
        if antigo.is_file():
            with FileLock(str(_lock_path(antigo))):
                desfecho, copia = _trocar_o_personalizado(directory)
            if copia is not None:
                _lock_path(antigo).unlink(missing_ok=True)
        if desfecho != "sem_copia":
            with contextlib.suppress(Exception):
                marker.write_text("done\n", encoding="utf-8")
    if copia is not None:
        _repontar_a_sessao_do_personalizado()
    logger.info(
        "personalizado_virou_freestyle",
        desfecho=desfecho,
        copia=str(copia) if copia is not None else None,
    )
    return copia


def o_perfil_de_fora_do_jogo() -> str | None:
    """O nome do «Freestyle» quando ele está no disco; `None` quando não."""
    _maybe_seed_presets()
    with contextlib.suppress(Exception):
        if (profiles_dir() / ARQUIVO_DO_PADRAO).is_file():
            return NOME_DO_PADRAO
    return None


_FREESTYLE_DE_FABRICA_NASCE_LIGADO_MARKER = ".freestyle_de_fabrica_nasce_ligado"


def _impressao_dos_dados(dados: object) -> str:
    """A impressão de um JSON já lido: o canônico, com as chaves em ordem."""
    canonico = json.dumps(dados, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _impressao_do_asset(asset: Path) -> str | None:
    """A impressão do asset lido como JSON — um empacotador que reformate não a muda."""
    try:
        dados = json.loads(asset.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _impressao_dos_dados(dados)


def _a_marca_ja_levou(marker: Path, impressao: str | None) -> bool:
    """A marca diz que ESTE asset já foi levado? Marca de antes (`done`) diz que não."""
    try:
        return marker.read_text(encoding="utf-8").strip() == impressao
    except OSError:
        return False


def _a_fabrica_que_a_marca_guarda(marker: Path) -> str | None:
    """A impressão da fábrica entregue antes nesta máquina; `None` sem marca ou com `done`."""
    bruto = _bytes_se_existe(marker)
    guardada = bruto.decode("utf-8", "replace").strip() if bruto is not None else ""
    return guardada if re.fullmatch(r"[0-9a-f]{64}", guardada) else None


def _levar_a_fabrica_nova(
    alvo: Path, asset: Path, directory: Path, fabrica_anterior: str | None = None
) -> tuple[str, Path | None]:
    """O miolo, com os dois locks tomados. Devolve `(desfecho, cópia)`.

    É de fábrica o `freestyle.json` com a impressão da fábrica que a marca guardou (a entregue
    antes aqui) ou igual a uma da tupla, que só serve às marcas de antes da impressão.
    """
    bruto = _bytes_se_existe(alvo)
    if bruto is None:
        return "sem_freestyle", None
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "ilegivel", None
    da_marca = fabrica_anterior is not None and _impressao_dos_dados(dados) == fabrica_anterior
    if not da_marca and dados not in _FABRICAS_ANTERIORES_DO_FREESTYLE:
        return "nao_e_a_fabrica_antiga", None
    copia = _arquivar_versao(SLUG_DO_PADRAO, bruto, raiz=directory)
    if copia is None:
        return "sem_copia", None
    _atomic_write_bytes(alvo, asset.read_bytes())
    return "fabrica_nova", copia


def o_freestyle_de_fabrica_nasce_ligado(dest_dir: Path | None = None) -> Path | None:
    """One-shot: a cópia de fábrica ANTIGA do Freestyle vira a de hoje."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _FREESTYLE_DE_FABRICA_NASCE_LIGADO_MARKER
    asset = _seed_source_file(ARQUIVO_DO_PADRAO)
    if asset is None:
        return None
    impressao = _impressao_do_asset(asset)
    if _a_marca_ja_levou(marker, impressao):
        return None
    alvo = directory / ARQUIVO_DO_PADRAO
    copia: Path | None = None
    desfecho = "sem_freestyle"
    with FileLock(str(_lock_path(marker))):
        if _a_marca_ja_levou(marker, impressao):
            return None
        anterior = _a_fabrica_que_a_marca_guarda(marker)
        if alvo.is_file():
            with FileLock(str(_lock_path(alvo))):
                desfecho, copia = _levar_a_fabrica_nova(alvo, asset, directory, anterior)
        if desfecho != "sem_copia":
            with contextlib.suppress(Exception):
                marker.write_text(f"{impressao}\n", encoding="utf-8")
    logger.info(
        "freestyle_de_fabrica_nasce_ligado",
        desfecho=desfecho,
        copia=str(copia) if copia is not None else None,
    )
    return copia


_COOP_LOCAL_MATCH_MIGRATION_MARKER = ".coop_local_match_migrated"


def _relatar_migracao_aposentada(migracao: str, arquivo: str) -> None:
    """Diz no journal que uma migração one-shot perdeu o asset que a alimenta."""
    logger.info(
        "migracao_aposentada_sem_asset",
        migracao=migracao,
        arquivo=arquivo,
        motivo="o preset de fábrica foi podado em 26/08/2026",
        efeito="o perfil local fica como está — nada é reescrito",
    )


def migrate_coop_local_match(dest_dir: Path | None = None) -> list[str]:
    """One-shot: dá um `match` alcançável ao coop_local que veio VAZIO de fábrica."""
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
        if path.is_file() and asset is None:
            _relatar_migracao_aposentada("coop_local_match", "coop_local.json")
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
    """True quando o coop_local ainda está no estado de fábrica inalcançável."""
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
    return isinstance(mode, dict) and mode.get("kind") == "gamepad"


_MODO_JOGO_MIGRATION_MARKER = ".modo_jogo_nos_presets_migrated"

_PRESETS_DE_JOGO = ("fps", "aventura", "acao", "corrida", "esportes")  # (noqa-acento)

_COOP_LOCAL_APOSENTADO = "coop_local"


def migrate_modo_jogo_nos_presets(dest_dir: Path | None = None) -> list[str]:
    """One-shot: leva `mode` e prioridade novos aos presets JÁ instalados (MODO-01)."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _MODO_JOGO_MIGRATION_MARKER
    if marker.exists():
        return []
    migrated: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return []
        for nome in (*_PRESETS_DE_JOGO, _COOP_LOCAL_APOSENTADO):
            arquivo = f"{nome}.json"
            path = directory / arquivo
            asset = _seed_source_file(arquivo)
            if path.is_file() and asset is None:
                _relatar_migracao_aposentada("modo_jogo_nos_presets", arquivo)
            if not path.is_file() or asset is None:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                asset_data = json.loads(asset.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict) or not isinstance(asset_data, dict):
                continue
            mudou = False
            if nome in _PRESETS_DE_JOGO and data.get("mode") in (None, {}):
                modo_asset = asset_data.get("mode")
                if isinstance(modo_asset, dict):
                    data["mode"] = modo_asset
                    mudou = True
            if nome == _COOP_LOCAL_APOSENTADO and data.get("priority") == 45:
                data["priority"] = asset_data.get("priority", 75)
                mudou = True
            if mudou:
                with contextlib.suppress(Exception):
                    path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    migrated.append(arquivo)
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    if migrated:
        logger.info("modo_jogo_nos_presets_migrated", files=migrated)
    return migrated


@dataclass(frozen=True)
class ResultadoDosEstilos:
    """O que a migração dos gêneros fez com CADA arquivo — e por quê."""

    movidos: tuple[str, ...] = ()
    dela: tuple[str, ...] = ()
    sem_fabrica: tuple[str, ...] = ()
    ocupados: tuple[str, ...] = ()


def _e_o_estilo_de_fabrica(local: Path, fabrica: Path) -> bool:
    """True quando o arquivo local ainda é o de fábrica — ela não o editou."""
    try:
        if local.read_bytes() == fabrica.read_bytes():
            return True
        return bool(
            json.loads(local.read_text(encoding="utf-8"))
            == json.loads(fabrica.read_text(encoding="utf-8"))
        )
    except Exception:
        return False


def migrar_generos_para_estilos_de_jogo(
    dest_dir: Path | None = None,
) -> ResultadoDosEstilos:
    """One-shot: os oito gêneros já semeados saem da LISTA, sem sair do disco."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _ESTILOS_MIGRATION_MARKER
    if marker.exists():
        return ResultadoDosEstilos()
    movidos: list[str] = []
    dela: list[str] = []
    sem_fabrica: list[str] = []
    ocupados: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return ResultadoDosEstilos()
        destino = directory / ESTILOS_DE_JOGO_DIR_NAME
        for arquivo in ARQUIVOS_DOS_ESTILOS_DE_JOGO:
            local = directory / arquivo
            if not local.is_file():
                continue
            fabrica = _seed_source_file(arquivo)
            if fabrica is None:
                sem_fabrica.append(arquivo)
                _relatar_migracao_aposentada("generos_viram_estilo_de_jogo", arquivo)
                continue
            if not _e_o_estilo_de_fabrica(local, fabrica):
                dela.append(arquivo)
                continue
            alvo = destino / arquivo
            if alvo.exists():
                ocupados.append(arquivo)
                continue
            try:
                destino.mkdir(parents=True, exist_ok=True)
                os.replace(local, alvo)
            except OSError as exc:
                logger.warning(
                    "genero_nao_virou_estilo",
                    arquivo=arquivo,
                    err=str(exc),
                    err_type=type(exc).__name__,
                )
                continue
            movidos.append(arquivo)
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    resultado = ResultadoDosEstilos(
        movidos=tuple(movidos),
        dela=tuple(dela),
        sem_fabrica=tuple(sem_fabrica),
        ocupados=tuple(ocupados),
    )
    with contextlib.suppress(Exception):
        logger.info(
            "generos_viraram_estilo_de_jogo",
            movidos=list(movidos),
            editados_por_ela=list(dela),
            sem_asset_de_fabrica=list(sem_fabrica),
            destino_ocupado=list(ocupados),
            destino=ESTILOS_DE_JOGO_DIR_NAME,
            efeito="saíram da lista de perfis; nenhum arquivo foi apagado",
        )
    return resultado


CHAVES_DO_PERFIL_DE_JOGO: tuple[str, ...] = ("name", "match", "priority")

CHAVES_DAS_DATAS: tuple[str, ...] = ("criado_em", "modificado_em")

# Quem salva por conta própria, sem ela ter pedido: não mexe na data da última mudança.
ORIGENS_SEM_GESTO: frozenset[str] = frozenset({"lancador_agnostico", "migracao-do-computador"})

_JOGOS_ENXUTOS_MARKER = ".perfis_de_jogo_so_nome_e_id"


def _classes_de_jogo_do_match(dados: dict[str, object]) -> list[str] | None:
    """As `window_class` quando o `match` é EXATAMENTE um jogo da Steam.

    None em todo o resto — `type` que não é `criteria`, mais de uma classe,
    classe que não é `steam_app_<n>`, ou qualquer outro campo de critério
    preenchido. Um perfil com `process_name` junto é regra que o usuário escreveu, e
    enxugar o que o usuário escreveu é o oposto do pedido.
    """
    match = dados.get("match")
    if not isinstance(match, dict) or match.get("type") != "criteria":
        return None
    if match.get("window_title_regex") or match.get("process_name"):
        return None
    classes = match.get("window_class")
    if not isinstance(classes, list) or len(classes) != 1:
        return None
    if steam_appid_from_wm_class(classes[0]) is None:
        return None
    return [str(classes[0])]


def _e_perfil_de_jogo_intocado(dados: dict[str, object]) -> bool:
    """True quando o perfil de jogo ainda é o molde que a semeadura gerou."""
    classes = _classes_de_jogo_do_match(dados)
    if classes is None:
        return False
    nome = dados.get("name")
    if not isinstance(nome, str) or not nome:
        return False
    molde = _payload_do_perfil(
        Profile(
            name=nome,
            match=MatchCriteria(window_class=classes),
            priority=PRIORIDADE_DO_PERFIL_DE_JOGO,
        )
    )
    resto_do_disco = {
        k: v for k, v in dados.items()
        if k not in CHAVES_DO_PERFIL_DE_JOGO and k not in CHAVES_DAS_DATAS
    }
    resto_do_molde = {
        k: v for k, v in molde.items() if k not in CHAVES_DO_PERFIL_DE_JOGO
    }
    return resto_do_disco == resto_do_molde


def e_perfil_de_jogo_automatico(profile: Profile) -> bool:
    """True para o perfil de jogo que a semeadura fez e ela nunca mexeu; a prioridade não conta."""
    return _e_perfil_de_jogo_intocado(_payload_do_perfil(profile))


def enxugar_perfis_de_jogo(dest_dir: Path | None = None) -> list[str]:
    """One-shot: o perfil de jogo intocado fica só com nome, id e prioridade."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _JOGOS_ENXUTOS_MARKER
    if marker.exists():
        return []
    enxutos: list[str] = []
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return []
        for path in sorted(directory.glob("*.json")):
            dados = _dados_crus_do_perfil(path)
            if dados is None or not _e_perfil_de_jogo_intocado(dados):
                continue
            payload = {
                k: dados[k] for k in (*CHAVES_DO_PERFIL_DE_JOGO, *CHAVES_DAS_DATAS) if k in dados
            }
            try:
                _atomic_write_json(path, payload)
            except OSError as exc:
                logger.warning(
                    "perfil_de_jogo_nao_enxugou",
                    arquivo=path.name,
                    err=str(exc),
                    err_type=type(exc).__name__,
                )
                continue
            enxutos.append(path.name)
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    if enxutos:
        logger.info(
            "perfis_de_jogo_so_nome_e_id",
            arquivos=enxutos,
            efeito="o resto era cópia do default do esquema — nada mudou de valor",
        )
    return enxutos


_MUDO_FOI_PARA_O_CONTROLE_MARKER = ".mudo_do_microfone_foi_para_o_controle"


def _mudos_do_perfil(dados: dict[str, object], conhecidos: set[str]) -> dict[str, bool]:
    """``{chave do controle: mudo}`` que um perfil cru guarda — a peça vence o global."""
    from hefesto_dualsense4unix.utils.maquina import chave_do_controle

    mudos: dict[str, bool] = {}
    controles = dados.get("controllers")
    if isinstance(controles, dict):
        for chave, cfg in controles.items():
            mic = cfg.get("mic") if isinstance(cfg, dict) else None
            valor = mic.get("muted") if isinstance(mic, dict) else None
            dono = chave_do_controle(chave)
            if isinstance(valor, bool) and dono is not None:
                mudos[dono] = valor
    mic_global = dados.get("mic")
    valor_global = mic_global.get("muted") if isinstance(mic_global, dict) else None
    if isinstance(valor_global, bool):
        for chave in sorted(conhecidos):
            mudos.setdefault(chave, valor_global)
    return mudos


def _e_copia_de_fabrica(path: Path, dados: dict[str, object]) -> bool:
    """O perfil cru é o asset do mesmo nome, sem nenhum ajuste dela?"""
    asset = _seed_source_file(path.name)
    if asset is None:
        return False
    try:
        return bool(dados == json.loads(asset.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def _sem_o_mudo_do_microfone(dados: dict[str, object]) -> dict[str, object]:
    """O perfil cru sem o `muted` do microfone — e só sem ele."""
    novo: dict[str, object] = json.loads(json.dumps(dados))
    mic = novo.get("mic")
    if isinstance(mic, dict):
        mic.pop("muted", None)
    controles = novo.get("controllers")
    if isinstance(controles, dict):
        for chave in list(controles):
            cfg = controles[chave]
            if not isinstance(cfg, dict):
                continue
            dele = cfg.get("mic")
            if isinstance(dele, dict) and "muted" in dele:
                dele.pop("muted")
                if not dele:
                    cfg.pop("mic")
                if not cfg:
                    controles.pop(chave)
        if not controles:
            novo.pop("controllers")
    return novo


def o_mudo_do_microfone_vai_para_o_controle(
    dest_dir: Path | None = None, *, ativo: str | None = None
) -> dict[str, bool] | None:
    """Leva o mudo dos perfis ao dono (`maquina.json`), uma vez. Ver o bloco acima."""
    from hefesto_dualsense4unix.utils import maquina as _maquina

    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    marker = directory / _MUDO_FOI_PARA_O_CONTROLE_MARKER
    if marker.exists():
        return None
    with FileLock(str(_lock_path(marker))):
        if marker.exists():
            return None
        if ativo is None:
            from hefesto_dualsense4unix.utils.session import resolve_boot_profile

            ativo = resolve_boot_profile()
        declarado = _maquina.carregar_maquina()
        dados_do_ativo: dict[str, object] | None = None
        if ativo:
            caminho = arquivo_do_perfil(ativo, directory)
            dados_do_ativo = _dados_crus_do_perfil(caminho) if caminho else None
            if caminho and dados_do_ativo and _e_copia_de_fabrica(caminho, dados_do_ativo):
                dados_do_ativo = None
        conhecidos = set(declarado.controles or {})
        for path in sorted(directory.glob("*.json")):
            pecas = (_dados_crus_do_perfil(path) or {}).get("controllers")
            if isinstance(pecas, dict):
                conhecidos |= {
                    c for c in (_maquina.chave_do_controle(k) for k in pecas)
                    if c is not None
                }
        mudos = _mudos_do_perfil(dados_do_ativo or {}, conhecidos)
        levados: dict[str, bool] = {}
        for chave, mudo in sorted(mudos.items()):
            if _maquina.mudo_do_microfone(chave, declarado) is not None:
                continue
            if not _maquina.gravar_o_mudo_do_microfone(chave, mudo):
                logger.warning("mic_mudo_nao_foi_para_o_controle", uniq=chave)
                return None
            levados[chave] = mudo
        tirados: list[str] = []
        for path in sorted(directory.glob("*.json")):
            dados = _dados_crus_do_perfil(path)
            if dados is None or _e_copia_de_fabrica(path, dados):
                continue
            novo = _sem_o_mudo_do_microfone(dados)
            if novo == dados:
                continue
            try:
                Profile.model_validate(novo)
                bruto = path.read_bytes()
                _arquivar_versao(path.stem, bruto, raiz=directory)
                _atomic_write_json(path, novo)
            except (ValidationError, OSError, ValueError) as exc:
                logger.warning(
                    "mic_mudo_nao_saiu_do_perfil", arquivo=path.name, err=str(exc)[:200]
                )
                continue
            tirados.append(path.name)
        with contextlib.suppress(Exception):
            marker.write_text("done\n", encoding="utf-8")
    logger.info(
        "mic_mudo_saiu_dos_perfis",
        perfil_ativo=ativo,
        levados_ao_controle=levados,
        perfis=tirados,
        nota="o mudo do microfone é do controle (O-MUDO-E-DO-CONTROLE-01); "
             "a versão de antes de cada perfil está no .historico",
    )
    return levados


def _maybe_seed_presets() -> None:
    """Dispara a semeadura uma vez por processo, antes da primeira carga."""
    global _seed_attempted
    if _seed_attempted or os.environ.get(SEED_SKIP_ENV_VAR) == "1":
        return
    _seed_attempted = True
    try:
        with contextlib.suppress(Exception):
            migrate_default_profile_name()
        with contextlib.suppress(Exception):
            o_personalizado_vira_freestyle()
        with contextlib.suppress(Exception):
            o_freestyle_de_fabrica_nasce_ligado()
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import migrar_a_escolha_dela

            migrar_a_escolha_dela()
        seed_default_presets()
        with contextlib.suppress(Exception):
            migrate_coop_local_match()
        with contextlib.suppress(Exception):
            migrate_modo_jogo_nos_presets()
        with contextlib.suppress(Exception):
            migrar_generos_para_estilos_de_jogo()
        with contextlib.suppress(Exception):
            enxugar_perfis_de_jogo()
        with contextlib.suppress(Exception):
            o_mudo_do_microfone_vai_para_o_controle()
    except Exception as exc:
        logger.warning(
            "presets_seed_failed",
            err=str(exc),
            err_type=type(exc).__name__,
        )


#   `load_all_profiles()` é chamado a cada troca de janela pelo

MARCA_DE_SEMEADURA_DE_JOGOS = ".perfis_de_jogo_semeados"

PREFIXO_DA_CHAVE_DE_JANELA = "janela:"

PRIORIDADE_DO_PERFIL_DE_JOGO = 80

INTERVALO_MINIMO_DA_VARREDURA_S = 300.0

DesfechoDaSemeadura = Literal[
    "criado",
    "ja_tinha_perfil",
    "ja_semeado",
    "nome_ocupado",
    "casa_com_a_loja",
    "sem_slug",
    "sem_endereco",
]

_DESFECHOS_QUE_MARCAM: frozenset[str] = frozenset({"criado", "ja_tinha_perfil"})


@dataclass(frozen=True)
class PerfilSemeado:
    """O que aconteceu com UM jogo na varredura — e por quê."""

    appid: str
    jogo: str
    desfecho: DesfechoDaSemeadura
    arquivo: str = ""
    chave: str = ""

    @property
    def identidade(self) -> str:
        """A linha da marca deste jogo — `appid`, ou ``janela:<classe>``."""
        return _identidade(self.appid, self.chave)


@dataclass(frozen=True)
class ResultadoDaSemeadura:
    """O relatório inteiro de uma varredura."""

    linhas: tuple[PerfilSemeado, ...] = ()
    criados: tuple[str, ...] = ()
    avisos_da_loja: tuple[tuple[str, str, tuple[str, ...]], ...] = ()

    def por_desfecho(self, desfecho: str) -> tuple[PerfilSemeado, ...]:
        """As linhas de um desfecho — o que os testes e a tela perguntam."""
        return tuple(linha for linha in self.linhas if linha.desfecho == desfecho)


_ultima_varredura_de_jogos: float | None = None
_assinatura_da_biblioteca_vista: tuple[object, ...] | None = None


def _caminho_da_marca(directory: Path) -> Path:
    return directory / MARCA_DE_SEMEADURA_DE_JOGOS


def _identidade(appid: str, chave: str) -> str:
    """A identidade de UM jogo na marca — e as duas formas não se confundem.

    O dono ÚNICO da forma: a janela ``steam_app_<N>`` é o jogo do appid
    ``<N>`` (a mesma identidade que o perfil dele grava), e nenhum chamador
    converte por conta própria.
    """
    if appid.strip():
        return appid.strip()
    da_steam = steam_appid_from_wm_class(chave)
    if da_steam is not None:
        return str(da_steam)
    if chave.strip():
        return f"{PREFIXO_DA_CHAVE_DE_JANELA}{chave.strip().casefold()}"
    return ""


def _identidade_valida(identidade: str) -> bool:
    """A linha da marca é uma das duas formas conhecidas?"""
    if identidade.isdigit():
        return True
    return (
        identidade.startswith(PREFIXO_DA_CHAVE_DE_JANELA)
        and len(identidade) > len(PREFIXO_DA_CHAVE_DE_JANELA)
    )


def _linhas_da_marca(marca: Path) -> list[tuple[str, str]]:
    """``[(identidade, arquivo)]`` da marca. Ausente/ilegível = vazio."""
    try:
        bruto = marca.read_text(encoding="utf-8")
    except OSError:
        return []
    lidas: list[tuple[str, str]] = []
    for linha in bruto.splitlines():
        identidade, _, arquivo = linha.strip().partition("\t")
        if not _identidade_valida(identidade):
            continue
        if identidade.startswith(PREFIXO_DA_CHAVE_DE_JANELA):
            # A marca de antes de 03/10 gravou o jogo da janela `steam_app_<N>`
            # na forma da janela; lida pelo mesmo dono, é a identidade `<N>`.
            identidade = _identidade("", identidade[len(PREFIXO_DA_CHAVE_DE_JANELA) :])
        lidas.append((identidade, arquivo.strip()))
    return lidas


def classes_de_jogo_da_marca(dest_dir: Path | None = None) -> list[str]:
    """As `wm_class` de jogo que a marca já conhece — sem a Steam."""
    directory = dest_dir if dest_dir is not None else profiles_dir()
    return [
        identidade[len(PREFIXO_DA_CHAVE_DE_JANELA) :]
        for identidade, _ in _linhas_da_marca(_caminho_da_marca(directory))
        if identidade.startswith(PREFIXO_DA_CHAVE_DE_JANELA)
    ]


def perfis_de_jogo_semeados(dest_dir: Path | None = None) -> dict[str, str]:
    """``{identidade: arquivo}`` do que o PRODUTO criou — nunca do que é do usuário."""
    directory = dest_dir if dest_dir is not None else profiles_dir()
    return {
        identidade: arquivo
        for identidade, arquivo in _linhas_da_marca(_caminho_da_marca(directory))
        if arquivo
    }


def _dados_crus_do_perfil(path: Path) -> dict[str, object] | None:
    """O JSON do perfil sem validar pelo schema. None se não der para ler."""
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


def _classes_do_match(dados: dict[str, object]) -> list[str]:
    """As `window_class` declaradas no `match` cru. Formato torto = lista vazia."""
    match = dados.get("match")
    if not isinstance(match, dict):
        return []
    classes = match.get("window_class")
    if not isinstance(classes, list):
        return []
    return [c for c in classes if isinstance(c, str)]


def _donos_dos_jogos(directory: Path) -> dict[str, str]:
    """``{identidade: arquivo}`` de TODO jogo que já tem perfil no diretório."""
    donos: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        dados = _dados_crus_do_perfil(path)
        if dados is None:
            continue
        for classe in _classes_do_match(dados):
            identidade = _identidade("", classe)
            if identidade:
                donos.setdefault(identidade, path.name)
    return donos


def perfis_que_casam_com_o_cliente_steam(
    dest_dir: Path | None = None,
) -> list[tuple[str, str, tuple[str, ...]]]:
    """``[(arquivo, nome, classes)]`` dos perfis que casam com a LOJA."""
    directory = dest_dir if dest_dir is not None else profiles_dir()
    achados: list[tuple[str, str, tuple[str, ...]]] = []
    try:
        arquivos = sorted(directory.glob("*.json"))
    except OSError:
        return []
    for path in arquivos:
        dados = _dados_crus_do_perfil(path)
        if dados is None:
            continue
        culpadas = tuple(
            c for c in _classes_do_match(dados) if e_janela_do_cliente_steam(c)
        )
        if not culpadas:
            continue
        nome = dados.get("name")
        achados.append((path.name, nome if isinstance(nome, str) else path.stem, culpadas))
    return achados


def classes_do_perfil_do_jogo(appid: str) -> list[str]:
    """As `window_class` do perfil semeado. UMA, e é o endereço do jogo."""
    return [f"steam_app_{appid}"]


def classes_do_perfil_do_jogo_de_lancador(chave: str) -> list[str]:
    """As `window_class` do perfil semeado para um jogo de LANÇADOR.

    UMA, e é a `wm_class` que a janela do jogo anuncia — ``gotg.exe``, o
    basename do `install.executable` do Heroic. É a MESMA forma que o botão
    «Detectar» grava (a sexta forma do `simple_match`, ``"janela"``) e a mesma
    que `MatchCriteria(window_class=[…])` compara sem caixa.

    **A CAIXA VAI COMO VEIO DO DISCO, sem `.casefold()`**, e é a mesma decisão
    do `simple_match.from_simple_choice`: quem compara sem caixa é o matcher do
    esquema, não quem escreve a regra. Minúsculas só na IDENTIDADE da marca
    (`_identidade`), que é chave de dicionário e não regra.
    """
    return [chave.strip()]


def _classes_do_perfil(jogo: JogoLocal) -> list[str]:
    """O `match` que serve a ESTE jogo — a Steam por appid, o resto por janela."""
    if jogo.appid.strip():
        return classes_do_perfil_do_jogo(jogo.appid)
    return classes_do_perfil_do_jogo_de_lancador(jogo.chave)


def _perfil_do_jogo(jogo: JogoLocal) -> Profile:
    """O perfil que nasce para um jogo — e SÓ o que o pedido manda."""
    return Profile(
        name=jogo.nome,
        match=MatchCriteria(window_class=_classes_do_perfil(jogo)),
        priority=PRIORIDADE_DO_PERFIL_DE_JOGO,
        criado_em=_agora_local(),
    )


def _payload_do_perfil_de_jogo(profile: Profile) -> dict[str, object]:
    """O que vai para o disco quando um perfil de JOGO nasce: nome, id, prioridade, datas."""
    payload = _payload_do_perfil(profile)
    return {k: payload[k] for k in (*CHAVES_DO_PERFIL_DE_JOGO, *CHAVES_DAS_DATAS) if k in payload}


def _agora_local() -> str:
    """A hora local em ISO 8601, ao segundo, com o fuso."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _datas_do_arquivo(bruto: bytes) -> tuple[str | None, str | None]:
    """`(criado_em, modificado_em)` que o arquivo já tem; ilegível ou ausente é None."""
    with contextlib.suppress(ValueError, UnicodeDecodeError):
        dados = json.loads(bruto.decode("utf-8"))
        if isinstance(dados, dict):
            criado, mudado = dados.get("criado_em"), dados.get("modificado_em")
            return (criado if isinstance(criado, str) else None,
                    mudado if isinstance(mudado, str) else None)
    return None, None


def _com_as_datas(
    profile: Profile, anterior: bytes | None, origem: str | None, *, enxuto: bool
) -> Profile:
    """O perfil com as duas datas no que o salvar vai gravar.

    Arquivo novo nasce com `criado_em`. Arquivo que já existia guarda as datas dele; a
    `modificado_em` só vira agora no gesto do usuário e quando o conteúdo de fato muda.
    """
    if anterior is None:
        return profile.model_copy(update={"criado_em": _agora_local(), "modificado_em": None})
    criado, mudado = _datas_do_arquivo(anterior)
    guardado = profile.model_copy(update={"criado_em": criado, "modificado_em": mudado})
    if not gesto_de_agora.get() or origem in ORIGENS_SEM_GESTO:
        return guardado
    payload = _payload_do_perfil_de_jogo(guardado) if enxuto else _payload_do_perfil(guardado)
    if _bytes_do_payload(payload) == anterior:
        return guardado
    return guardado.model_copy(update={"modificado_em": _agora_local()})


def _gravar_sem_pisar(alvo: Path, payload: object) -> bool:
    """Grava o JSON SÓ se `alvo` ainda não existe. ``True`` = gravou."""
    bruto = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_nome = tempfile.mkstemp(
        prefix=f".{alvo.name}.", suffix=".tmp", dir=str(alvo.parent)
    )
    tmp = Path(tmp_nome)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(bruto)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, alvo)
        except FileExistsError:
            return False
        except OSError:  # pragma: no cover - fs sem hardlink
            try:
                fd_excl = os.open(alvo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return False
            with os.fdopen(fd_excl, "wb") as fh:
                fh.write(bruto)
                fh.flush()
                os.fsync(fh.fileno())
        return True
    finally:
        tmp.unlink(missing_ok=True)


def lancadores_sem_perfil_por_jogo() -> frozenset[str]:
    """Os cartões da aba 07 com «Cada jogo ganha o seu perfil» desligado no ``maquina.json``."""
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        escolha = carregar_maquina().perfil_por_jogo
    except Exception as exc:
        logger.warning("perfil_por_jogo_ilegivel", err=str(exc))
        return frozenset()
    return frozenset(chave for chave, ligado in escolha.items() if not ligado)


def _so_os_de_lancador_com_perfil(jogos: Sequence[JogoLocal]) -> list[JogoLocal]:
    """Tira os jogos do lançador desligado; eles não entram na marca, e religar os semeia."""
    desligados = lancadores_sem_perfil_por_jogo()
    if not desligados:
        return list(jogos)
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import lancador_do_jogo

    return [j for j in jogos if lancador_do_jogo(j.fonte, j.appid) not in desligados]


def semear_perfis_dos_jogos(
    dest_dir: Path | None = None,
    home: Path | None = None,
    jogos: Sequence[JogoLocal] | None = None,
) -> ResultadoDaSemeadura:
    """Cria um perfil para cada jogo INSTALADO que ainda não tem — venha de onde vier."""
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    directory.mkdir(parents=True, exist_ok=True)
    if jogos is None:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            jogos_com_janela,
            jogos_da_biblioteca_steam,
        )

        # As três origens: a biblioteca da Steam, os lançadores e o jogo
        # instalado aqui (o `.desktop`). Com um `home` dado, os atalhos são
        # os DELE, nunca os desta máquina.
        pastas = None if home is None else [Path(home) / ".local/share/applications"]
        jogos = [*jogos_da_biblioteca_steam(home), *jogos_com_janela(home, pastas)]
        jogos = _so_os_de_lancador_com_perfil(jogos)

    marca = _caminho_da_marca(directory)
    linhas: list[PerfilSemeado] = []
    criados: list[str] = []
    with FileLock(str(_lock_path(marca))):
        ja_processados = {identidade for identidade, _ in _linhas_da_marca(marca)}
        donos = _donos_dos_jogos(directory)
        ocupados = {p.name for p in directory.glob("*.json")}
        novas: list[tuple[str, str]] = []
        for jogo in sorted(jogos, key=lambda j: (j.nome.casefold(), j.appid, j.chave)):
            linha = _semear_um_jogo(jogo, directory, ja_processados, donos, ocupados)
            linhas.append(linha)
            if linha.desfecho == "criado":
                criados.append(linha.arquivo)
                ocupados.add(linha.arquivo)
                donos[linha.identidade] = linha.arquivo
            if linha.desfecho in _DESFECHOS_QUE_MARCAM:
                novas.append(
                    (
                        linha.identidade,
                        linha.arquivo if linha.desfecho == "criado" else "",
                    )
                )
        if novas or not marca.exists():
            with marca.open("a", encoding="utf-8") as fh:
                for identidade, arquivo in novas:
                    fh.write(f"{identidade}\t{arquivo}\n")

    _declarar_as_classes_de_jogo(directory, jogos)
    avisos = perfis_que_casam_com_o_cliente_steam(directory)
    _relatar_semeadura(linhas, criados, avisos)
    return ResultadoDaSemeadura(
        linhas=tuple(linhas), criados=tuple(criados), avisos_da_loja=tuple(avisos)
    )


def _declarar_as_classes_de_jogo(
    directory: Path, jogos: Sequence[JogoLocal]
) -> None:
    """Diz ao esquema QUAIS `wm_class` de fora da Steam são de jogo."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.profiles.schema import registrar_classes_de_jogo

        da_biblioteca = [j.chave for j in jogos if not j.appid.strip() and j.chave]
        registrar_classes_de_jogo(
            [*da_biblioteca, *classes_de_jogo_da_marca(dest_dir=directory)]
        )


def _semear_um_jogo(
    jogo: JogoLocal,
    directory: Path,
    ja_processados: set[str],
    donos: dict[str, str],
    ocupados: set[str],
) -> PerfilSemeado:
    """A decisão de UM jogo. Ver `semear_perfis_dos_jogos` para as recusas."""
    identidade = _identidade(jogo.appid, jogo.chave)
    if not identidade:
        return PerfilSemeado(jogo.appid, jogo.nome, "sem_endereco", "", jogo.chave)
    if identidade in ja_processados:
        return PerfilSemeado(
            jogo.appid, jogo.nome, "ja_semeado", donos.get(identidade, ""), jogo.chave
        )
    dono = donos.get(identidade)
    if dono is not None:
        return PerfilSemeado(jogo.appid, jogo.nome, "ja_tinha_perfil", dono, jogo.chave)
    try:
        slug = slugify(jogo.nome)
    except ValueError:
        return PerfilSemeado(jogo.appid, jogo.nome, "sem_slug", "", jogo.chave)
    arquivo = f"{slug}.json"
    if arquivo in ocupados:
        return PerfilSemeado(jogo.appid, jogo.nome, "nome_ocupado", arquivo, jogo.chave)
    if any(e_janela_do_cliente_steam(c) for c in _classes_do_perfil(jogo)):
        return PerfilSemeado(
            jogo.appid, jogo.nome, "casa_com_a_loja", arquivo, jogo.chave
        )
    perfil = _perfil_do_jogo(jogo)
    if not _gravar_sem_pisar(directory / arquivo, _payload_do_perfil_de_jogo(perfil)):
        return PerfilSemeado(jogo.appid, jogo.nome, "nome_ocupado", arquivo, jogo.chave)
    return PerfilSemeado(jogo.appid, jogo.nome, "criado", arquivo, jogo.chave)


def _relatar_semeadura(
    linhas: Sequence[PerfilSemeado],
    criados: Sequence[str],
    avisos: Sequence[tuple[str, str, tuple[str, ...]]],
) -> None:
    """Diz o que a varredura fez — inclusive quando não fez nada de novo."""
    contagem: dict[str, int] = {}
    for linha in linhas:
        contagem[linha.desfecho] = contagem.get(linha.desfecho, 0) + 1
    with contextlib.suppress(Exception):
        logger.info(
            "perfis_de_jogo_semeados",
            jogos=len(linhas),
            criados=list(criados),
            desfechos=contagem,
        )
        for linha in linhas:
            if linha.desfecho in {
                "nome_ocupado",
                "casa_com_a_loja",
                "sem_slug",
                "sem_endereco",
            }:
                logger.warning(
                    "perfil_de_jogo_recusado",
                    appid=linha.appid,
                    endereco=linha.identidade,
                    jogo=linha.jogo,
                    motivo=linha.desfecho,
                    arquivo=linha.arquivo or None,
                )
        for arquivo, nome, classes in avisos:
            logger.warning(
                "perfil_casa_com_a_loja",
                arquivo=arquivo,
                perfil=nome,
                classes=list(classes),
                efeito=(
                    "a janela invisível do steamwebhelper ativa este perfil no "
                    "meio da partida"
                ),
            )


def _talvez_semear_jogos() -> None:
    """O gatilho automático: barato quando nada mudou, best-effort sempre.

    No laço do serviço não semeia: quem anda a semeadura ali é o passo fora do laço da troca
    automática (`AutoSwitcher._ler_fora_do_laco`). Vale para toda leitura de perfil feita no laço,
    a varredura e a carga do perfil que a troca ativa.
    """
    global _ultima_varredura_de_jogos, _assinatura_da_biblioteca_vista
    if os.environ.get(SEED_SKIP_ENV_VAR) == "1" or _no_laco_do_servico():
        return
    agora = time.monotonic()
    if (
        _ultima_varredura_de_jogos is not None
        and agora - _ultima_varredura_de_jogos < INTERVALO_MINIMO_DA_VARREDURA_S
    ):
        return
    _ultima_varredura_de_jogos = agora
    try:
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            assinatura_das_bibliotecas,
        )
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            assinatura_da_biblioteca,
            assinatura_das_janelas,
        )

        assinatura = (
            assinatura_da_biblioteca(),
            assinatura_das_bibliotecas(),
            assinatura_das_janelas(),
            lancadores_sem_perfil_por_jogo(),
        )
        if assinatura == _assinatura_da_biblioteca_vista:
            return
        semear_perfis_dos_jogos()
        reapontar_perfis_com_chave_de_executavel()
        _assinatura_da_biblioteca_vista = assinatura
    except Exception as exc:
        logger.warning(
            "semeadura_de_jogos_falhou",
            err=str(exc),
            err_type=type(exc).__name__,
        )


def reapontar_perfis_com_chave_de_executavel(
    catalogo: Sequence[tuple[str, object]] | None = None,
) -> tuple[str, ...]:
    """Conserta os perfis que nasceram com o basename do `.exe` como janela.

    **A QUEIXA, 21/09/2026:** *"GUARDIÃES DA GALAXIA ABERTO E AO INVÉS DE
    IDENTIFICAR ID DO JOGO AUTOMATICAMENTE COMO É NA STEAM NÃO OCORRRE ISSO E
    POR CONSEQUENCIA O HEFESTO NÃO É IDENTIFICADO E NÃO FUNCIONA LÁ."*

    O perfil do usuário tinha ``window_class: ["gotg.exe"]`` — a derivação que a
    LANCADOR-AGNOSTICO-01 derrubou. A janela do jogo anuncia
    ``steam_app_1088850``, e a regra nunca casava: nenhum perfil ativava e
    nenhuma feature chegava ao jogo.

    Curar a origem faz o PRÓXIMO perfil nascer certo. Este consertos os que já
    estão no disco — sem o qual a cura chegaria só para quem instalasse o
    produto do zero.

    **AS TRÊS GUARDAS, e todas são de não-atropelar:**

    1. **Só uma entrada, e ela termina em `.exe`.** Um `.exe` vai por
       Proton/wine em qualquer lançador, e nesse caminho quem nomeia a janela é
       o Proton — a única forma que a derivação produzia. Regra com duas
       entradas, ou com uma que não seja `.exe`, é escolha de alguém.
    2. **O censo tem de RECONHECER o executável**, pelo basename, num jogo que
       hoje tem chave. Sem isso não há para onde reapontar, e chutar seria
       repetir o defeito que esta função conserta.
    3. **A chave nova tem de ser diferente.** Regravar um perfil idêntico troca
       a data do arquivo por nada — a mesma guarda do `_lembrar_do_som`.

    **LÊ OS ARQUIVOS, E NÃO `load_all_profiles()` — e a razão é reentrância.**
    Quem chama esta função é `_talvez_semear_jogos`, que é chamado DE DENTRO de
    `load_all_profiles`. Voltar por lá reentra no semeador de presets
    (`_maybe_seed_presets`) no meio de uma varredura — medido em 21/09: um
    `personalizado.json` nascia no disco durante o conserto, fora de hora e sem
    ninguém ter pedido. A leitura direta faz exatamente o que esta função
    precisa e não acorda mais nada.

    Devolve os nomes dos perfis consertados. NUNCA LEVANTA: quem chama é o laço
    do daemon.
    """
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        jogos_com_chave_de_janela,
    )

    consertados: list[str] = []
    try:
        lista = (list(catalogo) if catalogo is not None
                 else list(jogos_com_chave_de_janela()))
    except Exception:  # pragma: no cover - disco hostil
        return ()
    por_exe: dict[str, str] = {}
    for _lancador, jogo in lista:
        exe = str(getattr(jogo, "executavel", "") or "")
        chave = str(getattr(jogo, "classe_de_janela", "") or "")
        if exe and chave:
            por_exe.setdefault(
                exe.replace("\\", "/").rsplit("/", 1)[-1].casefold(), chave)
    if not por_exe:
        return ()
    try:
        arquivos = sorted(profiles_dir(ensure=False).glob("*.json"))
    except Exception:  # pragma: no cover - disco hostil
        return ()
    perfis: list[Profile] = []
    for caminho in arquivos:
        try:
            with FileLock(str(_lock_path(caminho))):
                bruto = json.loads(caminho.read_text(encoding="utf-8"))
            perfis.append(Profile.model_validate(bruto))
        except _PROFILE_DECODE_ERRORS:
            continue
    for prof in perfis:
        classes = list(getattr(getattr(prof, "match", None), "window_class", None) or [])
        if len(classes) != 1:
            continue
        velha = str(classes[0] or "").strip()
        if not velha.casefold().endswith(".exe"):
            continue
        nova = por_exe.get(velha.casefold())
        if not nova or nova.casefold() == velha.casefold():
            continue
        try:
            novo = prof.model_copy(
                update={"match": prof.match.model_copy(
                    update={"window_class": [nova]})})
            save_profile(novo, origem="lancador_agnostico")
        except Exception as exc:  # pragma: no cover - disco hostil
            logger.warning(
                "reaponte_de_chave_falhou", profile=prof.name, err=str(exc))
            continue
        consertados.append(prof.name)
        logger.info(
            "perfil_reapontado_para_a_janela_de_verdade",
            profile=prof.name, de=velha, para=nova)
    return tuple(consertados)


def _profile_path(identifier: str | Profile) -> Path:
    """Resolve filename a partir de slug direto ou de Profile."""
    if isinstance(identifier, Profile):
        return profiles_dir(ensure=True) / f"{slugify(identifier.name)}.json"
    _reject_traversal(identifier)
    return profiles_dir(ensure=True) / f"{identifier}.json"


#: ``caminho -> (mtime, tamanho)`` do perfil inválido que já foi avisado. O gerente
#: relê a pasta no laço; sem esta memória cada arquivo ruim gerava um aviso a cada
#: leitura (~43 mil linhas por dia). O arquivo não é renomeado nem isolado: pode
#: estar no meio de uma edição à mão. Quem pergunta (`audit_profiles`, o `doctor`)
#: continua vendo a lista inteira.
_INVALIDOS_JA_AVISADOS: dict[str, tuple[int, int]] = {}
_INVALIDOS_TRAVA = threading.Lock()


def _avisa_perfil_invalido(path: Path, exc: BaseException) -> None:
    """O `profile_invalid` no diário: uma vez por arquivo, e de novo quando ele muda."""
    try:
        estado = path.stat()
        assinatura = (estado.st_mtime_ns, estado.st_size)
    except OSError:
        assinatura = (-1, -1)
    chave = str(path)
    with _INVALIDOS_TRAVA:
        if _INVALIDOS_JA_AVISADOS.get(chave) == assinatura:
            return
        _INVALIDOS_JA_AVISADOS[chave] = assinatura
    logger.warning(
        "profile_invalid",
        path=chave,
        err=str(exc),
        err_type=type(exc).__name__,
    )


def _read_profile(path: Path) -> Profile:
    with FileLock(str(_lock_path(path))):
        raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


def arquivo_do_perfil(identifier: str, directory: Path | None = None) -> Path | None:
    """O ARQUIVO que `load_profile(identifier)` lê, ou ``None`` quando não há."""
    _reject_traversal(identifier)
    pasta = profiles_dir() if directory is None else directory
    direct = pasta / f"{identifier}.json"
    if not direct.resolve().is_relative_to(pasta.resolve()):
        raise ValueError("identifier de perfil escapa do diretório de perfis")
    if direct.exists():
        return direct

    try:
        slug = slugify(identifier)
    except ValueError:
        return None

    slugged = pasta / f"{slug}.json"
    if slugged.exists():
        return slugged

    for path in sorted(pasta.glob("*.json")):
        try:
            profile = _read_profile(path)
        except _PROFILE_DECODE_ERRORS as exc:
            _avisa_perfil_invalido(path, exc)
            continue
        try:
            if slugify(profile.name) == slug:
                return path
        except ValueError:
            continue

    estilo = pasta / ESTILOS_DE_JOGO_DIR_NAME / f"{slug}.json"
    if estilo.is_file():
        return estilo
    return None


def load_profile(identifier: str) -> Profile:
    """Carrega perfil por slug direto ou por display name."""
    _reject_traversal(identifier)
    _maybe_seed_presets()
    _talvez_semear_jogos()
    alvo = arquivo_do_perfil(identifier, profiles_dir(ensure=True))
    if alvo is None:
        raise FileNotFoundError(f"perfil não encontrado: {identifier}")
    return _read_profile(alvo)


def perfil_em_disco(identifier: str) -> Profile | None:
    """O perfil que está NO ARQUIVO agora — sem semear, sem varrer, sem levantar."""
    try:
        alvo = profiles_dir(ensure=True) / f"{slugify(identifier)}.json"
    except ValueError:
        return None
    if not alvo.exists():
        return None
    try:
        return _read_profile(alvo)
    except _PROFILE_DECODE_ERRORS as exc:
        _avisa_perfil_invalido(alvo, exc)
        return None


def _trava_do_perfil(path: Path) -> FileLock:
    """O `FileLock` do perfil, o mesmo da leitura de sempre."""
    return FileLock(str(_lock_path(path)))


def _decodificar_o_perfil(path: Path) -> Profile:
    """O perfil do arquivo, lido e validado (a exceção de decodificação sobe)."""
    return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))


_PERFIS_PELA_ASSINATURA: LeituraPelaAssinatura[Profile] = LeituraPelaAssinatura(
    _decodificar_o_perfil, copiar=lambda perfil: perfil.model_copy(deep=True)
)
_ode.ao_desarmar(_PERFIS_PELA_ASSINATURA.esquecer)

_LEITURA_LIGADA_PELO_PROCESSO = False


def ligar_a_leitura_pela_assinatura() -> None:
    """Liga a leitura dos perfis pela assinatura neste processo (a janela, ao subir)."""
    global _LEITURA_LIGADA_PELO_PROCESSO
    _LEITURA_LIGADA_PELO_PROCESSO = True


def desligar_a_leitura_pela_assinatura() -> None:
    """Desliga a leitura pela assinatura e esquece o guardado (a janela, ao sair)."""
    global _LEITURA_LIGADA_PELO_PROCESSO
    _LEITURA_LIGADA_PELO_PROCESSO = False
    _PERFIS_PELA_ASSINATURA.esquecer()


def load_all_profiles() -> list[Profile]:
    """Lê todos os perfis JSON do diretório, pulando os inválidos com warning."""
    _maybe_seed_presets()
    _talvez_semear_jogos()
    return _ler_todos_os_perfis(copiar=True)


def perfis_para_consulta() -> list[Profile]:
    """Os perfis para quem só os CONSULTA (a escolha pela janela), sem cópia profunda.

    Pela assinatura, cada perfil devolvido é o próprio guardado da leitura: quem o recebe não o
    edita, e copia o que for usar (a escolha copia só o perfil escolhido). Fora da leitura pela
    assinatura, cada chamada lê do disco, como o :func:`load_all_profiles`.
    """
    _maybe_seed_presets()
    _talvez_semear_jogos()
    return _ler_todos_os_perfis(copiar=False)


def _no_laco_do_servico() -> bool:
    """Esta leitura corre no laço asyncio do serviço (o do pad virtual de P1 a P4)?"""
    if not _ode.armado():
        return False
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _ler_todos_os_perfis(*, copiar: bool) -> list[Profile]:
    """O miolo das duas leituras, depois das semeaduras que cada porta dispara."""
    directory = profiles_dir(ensure=True)
    profiles: list[Profile] = []
    pela_assinatura = _ode.armado() or _LEITURA_LIGADA_PELO_PROCESSO
    vistos: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            if pela_assinatura:
                vistos.append(str(path))
                profiles.append(_PERFIS_PELA_ASSINATURA.ler(
                    path, trava=partial(_trava_do_perfil, path), copiar=copiar))
                continue
            with FileLock(str(_lock_path(path))):
                raw = json.loads(path.read_text(encoding="utf-8"))
            profiles.append(Profile.model_validate(raw))
        except _PROFILE_DECODE_ERRORS as exc:
            _avisa_perfil_invalido(path, exc)
            continue
    if pela_assinatura:
        _PERFIS_PELA_ASSINATURA.manter_so(vistos)
    return profiles


def audit_profiles() -> list[tuple[str, str]]:
    """Valida todos os perfis sem carregá-los para uso, coletando os inválidos."""
    _maybe_seed_presets()
    _talvez_semear_jogos()
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


#: vezes em cinco semanas (``teclado_emulado`` em 24/08, ``button_actions`` em
#: 01/09, e o próprio comentário de ``button_actions`` diz "a terceira vez que
_SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE: tuple[str, ...] = (
    "speaker",
    "mouse",
    "mic",
    "mode",
    "key_bindings",
    "teclado_emulado",
    "teclado_so_no_jogo",
    "teclado_sempre",
    "tabela_no_jogo",
    # gravar `"button_actions": null` e um binário anterior a esta feature
    "button_actions",
)


_SECOES_DE_TOPO_QUE_NASCEM_DENSAS: tuple[str, ...] = (
    "name",
    "version",
    "match",
    "priority",
    "triggers",
    "leds",
    "rumble",
    "suppress_desktop_emulation",
)


def _secoes_de_topo_omitidas_quando_none(payload: dict[str, object]) -> tuple[str, ...]:
    """As chaves de topo que saem do arquivo — DERIVADAS, não listadas."""
    return tuple(nome for nome, valor in payload.items() if valor is None)


HISTORICO_DIR_NAME = ".historico"

HISTORICO_MAX_VERSOES = 10

HISTORICO_DIAS = 14

# Uma semana inteira, versão por versão — a pergunta «quem mudou este campo
# entre as 14h e as 19h» não se responde com um ponto por dia. O teto de
# versões por perfil (~2,3 KB cada, ~1 MB no pior caso) segura a rajada.
HISTORICO_SEMANA_DIAS = 7

HISTORICO_TETO_POR_PERFIL = 500

# O gesto em curso, posto por quem sabe (o `trabalhar` da janela, o `_dispatch`
# do IPC) e lido por `save_profile`: um `ContextVar` atravessa `asyncio.to_thread`,
# e quem não o põe (CLI, migração) deixa o campo vazio no `profile_salvo`.
gesto_de_agora: ContextVar[str | None] = ContextVar("hefesto_gesto_de_agora", default=None)


def historico_dir(slug: str, *, ensure: bool = False) -> Path:
    """Diretório do histórico de UM perfil: ``profiles/.historico/<slug>/``."""
    _reject_traversal(slug)
    destino = profiles_dir(ensure=ensure) / HISTORICO_DIR_NAME / slug
    if ensure:
        destino.mkdir(parents=True, exist_ok=True)
    return destino


def _carimbo_de_versao() -> str:
    """Carimbo ordenável lexicograficamente: ``20260805T031500_123456``."""
    return datetime.now().strftime("%Y%m%dT%H%M%S_%f")


def listar_historico(identifier: str) -> list[Path]:
    """Versões guardadas de um perfil, da MAIS ANTIGA para a mais recente."""
    slug = _slug_para_historico(identifier)
    destino = historico_dir(slug)
    if not destino.is_dir():
        return []
    return sorted(destino.glob("*.json"))


def _slug_para_historico(identifier: str) -> str:
    """Resolve o identifier para o slug que nomeia o arquivo do perfil."""
    _reject_traversal(identifier)
    raiz = profiles_dir() / HISTORICO_DIR_NAME
    if (raiz / identifier).is_dir():
        return identifier
    try:
        return slugify(identifier)
    except ValueError:
        return identifier


def _as_primeiras_de_cada_dia(versoes: list[Path], dias: int) -> set[Path]:
    """A primeira versão de cada um dos `dias` mais novos que têm gravação."""
    primeiras: dict[str, Path] = {}
    for versao in versoes:
        dia = versao.name[:8]
        if dia.isdigit() and len(dia) == 8:
            primeiras.setdefault(dia, versao)
    return {primeiras[dia] for dia in sorted(primeiras)[-dias:]} if dias > 0 else set()


_CARIMBO_DO_NOME = re.compile(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})")


def _o_instante_da_versao(versao: Path) -> datetime | None:
    """O instante que o carimbo do nome conta, ou None se o nome não é um carimbo.

    O carimbo se confere na porta, campo a campo, antes de virar data: um nome
    fora da forma de :func:`_carimbo_de_versao` não chega ao construtor.
    """
    achado = _CARIMBO_DO_NOME.match(versao.name)
    if achado is None:
        return None
    ano, mes, dia, hora, minuto, segundo = (int(campo) for campo in achado.groups())
    if not (ano >= 1 and 1 <= mes <= 12 and hora < 24 and minuto < 60 and segundo < 60):
        return None
    if not 1 <= dia <= calendar.monthrange(ano, mes)[1]:
        return None
    return datetime(ano, mes, dia, hora, minuto, segundo)


def _as_da_semana(versoes: list[Path], dias: int) -> list[Path]:
    """Toda versão dos últimos `dias` dias, contados da MAIS NOVA do histórico.

    O relógio é o da própria pasta: a poda roda logo depois de arquivar, então
    a mais nova é o «agora» — e a régua não depende da hora da máquina.
    """
    if dias <= 0:
        return []
    instantes = [(v, _o_instante_da_versao(v)) for v in versoes]
    datados = [i for _, i in instantes if i is not None]
    if not datados:
        return []
    limite = max(datados) - timedelta(days=dias)
    return [v for v, i in instantes if i is not None and i >= limite]


def _podar_historico(
    destino: Path,
    manter: int,
    *,
    dias: int = HISTORICO_DIAS,
    semana: int = HISTORICO_SEMANA_DIAS,
    teto: int = HISTORICO_TETO_POR_PERFIL,
) -> list[Path]:
    """Apaga as versões fora de: as `manter` mais novas, a primeira de cada dia, a semana.

    A semana inteira entra até o `teto` por perfil (as mais velhas dela saem
    primeiro); as `manter` mais novas e as primeiras do dia nunca saem.
    """
    versoes = sorted(destino.glob("*.json"))
    ficam = set(versoes[-manter:]) if manter > 0 else set()
    ficam |= _as_primeiras_de_cada_dia(versoes, dias)
    da_semana = [v for v in _as_da_semana(versoes, semana) if v not in ficam]
    vagas = max(0, teto - len(ficam))
    ficam |= set(da_semana[-vagas:]) if vagas else set()
    apagadas: list[Path] = []
    for velha in versoes:
        if velha in ficam:
            continue
        with contextlib.suppress(OSError):
            velha.unlink()
            apagadas.append(velha)
    return apagadas


def _arquivar_versao(
    slug: str, bruto: bytes, *, raiz: Path | None = None
) -> Path | None:
    """Guarda os BYTES da versão atual do perfil no histórico."""
    try:
        if raiz is None:
            destino = historico_dir(slug, ensure=True)
        else:
            _reject_traversal(slug)
            destino = raiz / HISTORICO_DIR_NAME / slug
            destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / f"{_carimbo_de_versao()}.json"
        sufixo = 1
        while alvo.exists():
            alvo = destino / f"{_carimbo_de_versao()}-{sufixo}.json"
            sufixo += 1
        alvo.write_bytes(bruto)
        _podar_historico(destino, HISTORICO_MAX_VERSOES)
        return alvo
    except OSError as exc:
        logger.warning(
            "profile_backup_failed",
            slug=slug,
            err=str(exc),
            err_type=type(exc).__name__,
        )
        return None


def _bytes_se_existe(path: Path) -> bytes | None:
    """Conteúdo bruto do alvo, ou None quando o perfil ainda não existe."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning(
            "profile_read_before_save_failed",
            path=str(path),
            err=str(exc),
            err_type=type(exc).__name__,
        )
        return None


def _estado_gravado(bruto: bytes | None) -> tuple[str | None, int | None]:
    """(discriminador do `match`, `priority`) do que está NO DISCO agora."""
    if bruto is None:
        return (None, None)
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ("ilegivel", None)
    if not isinstance(dados, dict):
        return ("ilegivel", None)
    match = dados.get("match")
    tipo = match.get("type") if isinstance(match, dict) else None
    prioridade = dados.get("priority")
    return (
        str(tipo) if isinstance(tipo, str) else "ilegivel",
        prioridade if isinstance(prioridade, int) else None,
    )


def _origem_do_processo() -> str:
    """Quem é o processo que está gravando — ``hefesto-gui``, ``pytest``..."""
    try:
        nome = Path(sys.argv[0]).name
    except (IndexError, ValueError):  # pragma: no cover — argv sempre tem [0]
        nome = ""
    return nome or "desconhecida"


def _payload_do_perfil(profile: Profile) -> dict[str, object]:
    """O DICIONÁRIO que vai para o disco — as regras de omissão num lugar só."""
    payload: dict[str, object] = profile.model_dump(mode="json")
    for secao in _secoes_de_topo_omitidas_quando_none(payload):
        payload.pop(secao, None)
    mouse = payload.get("mouse")
    if isinstance(mouse, dict) and mouse.get("point_and_click") is None:
        mouse.pop("point_and_click", None)  # campo aditivo: sem escolha, o arquivo não o diz
    if not payload.get("controllers"):
        payload.pop("controllers", None)
    else:
        payload["controllers"] = {
            uniq: cfg.model_dump(mode="json", exclude_unset=True)
            for uniq, cfg in (profile.controllers or {}).items()
        }
    return payload


_FOLHAS_NA_LINHA = 12

_CAMPOS_DE_TEXTO_LIVRE = frozenset({
    "name", "nome", "apelido", "label", "window_title_regex",
    "o_que_faz", "razao", "falta", "onde", "dono",
})

_VALOR_CURTO = re.compile(r"[A-Za-z0-9_.:+\-]{1,24}")


def _sha_curto(bruto: bytes | None) -> str | None:
    """16 hex do sha256 (nunca 12: é a forma de endereço que os portões leem)."""
    return hashlib.sha256(bruto).hexdigest()[:16] if bruto is not None else None


def _o_valor_na_linha(chave: str, valor: object) -> str | None:
    """O valor que entra na linha, ou None quando só o CAMINHO deve entrar.

    Número, booleano e cadeia curta de uma palavra entram; nome e texto livre
    (e lista, e seção inteira) entram só como caminho.
    """
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return repr(valor)
    if (
        isinstance(valor, str)
        and chave not in _CAMPOS_DE_TEXTO_LIVRE
        and _VALOR_CURTO.fullmatch(valor)
    ):
        return valor
    return None


def _as_folhas_que_diferem(
    antes: object, depois: object, caminho: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], object, object]]:
    """Cada folha (caminho, antes, depois) em que os dois JSON divergem."""
    ausente = _AUSENTE
    if isinstance(antes, dict) and isinstance(depois, dict):
        achadas: list[tuple[tuple[str, ...], object, object]] = []
        for chave in sorted(set(antes) | set(depois)):
            achadas += _as_folhas_que_diferem(
                antes.get(chave, ausente), depois.get(chave, ausente), (*caminho, str(chave))
            )
        return achadas
    # A seção que NASCE (ou some) inteira desce até as folhas dela: o primeiro
    # brilho de um controle no perfil é `controllers` de nada a um dicionário, e
    # a linha tem de dizer qual campo, não só «controllers».
    if isinstance(depois, dict) and (antes is None or antes is ausente):
        return _as_folhas_que_diferem({}, depois, caminho) or [(caminho, antes, depois)]
    if isinstance(antes, dict) and (depois is None or depois is ausente):
        return _as_folhas_que_diferem(antes, {}, caminho) or [(caminho, antes, depois)]
    if isinstance(antes, list) and isinstance(depois, list) and len(antes) == len(depois):
        achadas = []
        for indice, (a, d) in enumerate(zip(antes, depois, strict=True)):
            achadas += _as_folhas_que_diferem(a, d, (*caminho, str(indice)))
        return achadas
    return [] if antes == depois else [(caminho, antes, depois)]


_AUSENTE = object()


def _o_que_mudou(anterior: bytes | None, novos: bytes) -> str:
    """As folhas que diferem entre o que ESTÁ no disco e o que vai para ele.

    `caminho.pontilhado:antes->depois` para número, booleano e cadeia curta; nome
    e texto livre só pelo caminho. A chave de controle e todo valor passam pela
    máscara da casa. Teto de `_FOLHAS_NA_LINHA`, e `+N` para o resto. Vazio
    quando nada mudou, quando o perfil nasce e quando o disco não era legível
    (esse caso diz `ilegivel`).
    """
    if anterior is None:
        return ""
    try:
        antes = json.loads(anterior.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "ilegivel"
    depois = json.loads(novos.decode("utf-8"))
    folhas = _as_folhas_que_diferem(antes, depois)
    itens: list[str] = []
    for caminho, de, para in folhas[:_FOLHAS_NA_LINHA]:
        texto = _mascarar(".".join(caminho))
        valores = [
            None if v is _AUSENTE else _o_valor_na_linha(caminho[-1] if caminho else "", v)
            for v in (de, para)
        ]
        if all(v is None for v in valores) and (de is not _AUSENTE and para is not _AUSENTE):
            itens.append(texto)
            continue
        a_ = "ausente" if de is _AUSENTE else valores[0]
        d_ = "ausente" if para is _AUSENTE else valores[1]
        if a_ is None or d_ is None:
            itens.append(texto)
        else:
            itens.append(f"{texto}:{_mascarar(a_)}->{_mascarar(d_)}")
    if len(folhas) > _FOLHAS_NA_LINHA:
        itens.append(f"+{len(folhas) - _FOLHAS_NA_LINHA}")
    return ";".join(itens)


def _bytes_do_payload(payload: object) -> bytes:
    """Os bytes que `_atomic_write_json` grava — o mesmo texto, sem escrever."""
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def save_profile(
    profile: Profile, *, origem: str | None = None, enxuto: bool = False
) -> Path:
    """Grava perfil em `<slugify(profile.name)>.json` de forma atômica.

    Não arquiva a versão de antes quando ela é BYTE A BYTE a que vai para o
    disco: a gravação que não mudou nada não gasta as vagas do histórico.

    ``enxuto=True`` grava só nome, alvo e prioridade (a forma do perfil de jogo
    semeado): o que o perfil não diz, herda do padrão do computador.
    """
    path = _profile_path(profile)
    with FileLock(str(_lock_path(path))):
        anterior = _bytes_se_existe(path)
        profile = _com_as_datas(profile, anterior, origem, enxuto=enxuto)
        payload = (
            _payload_do_perfil_de_jogo(profile) if enxuto else _payload_do_perfil(profile)
        )
        novos = _bytes_do_payload(payload)
        igual = anterior is not None and anterior == novos
        backup = (
            _arquivar_versao(path.stem, anterior)
            if anterior is not None and not igual
            else None
        )
        _atomic_write_json(path, payload)
    _registrar_gravacao(profile, path, anterior, backup, origem, novos, igual=igual)
    return path


def _registrar_gravacao(
    profile: Profile,
    path: Path,
    anterior: bytes | None,
    backup: Path | None,
    origem: str | None,
    novos: bytes,
    *,
    igual: bool,
) -> None:
    """Emite o `profile_salvo` — a linha de journal que NÃO existia."""
    match_antes, priority_antes = _estado_gravado(anterior)
    with contextlib.suppress(Exception):
        logger.info(
            "profile_salvo",
            nome=profile.name,
            arquivo=path.name,
            criado=anterior is None,
            match_antes=match_antes,
            match_depois=profile.match.type,
            priority_antes=priority_antes,
            priority_depois=profile.priority,
            origem=origem or _origem_do_processo(),
            gesto=gesto_de_agora.get() or "",
            mudou=_o_que_mudou(anterior, novos),
            igual=igual,
            sha_antes=_sha_curto(anterior),
            sha_depois=_sha_curto(novos),
            pid=os.getpid(),
            backup=str(backup) if backup is not None else None,
        )


def restaurar_do_historico(
    identifier: str, carimbo: str | None = None
) -> tuple[Path, Path]:
    """Devolve ao perfil uma versão guardada. Retorna ``(alvo, versão usada)``.

    PERFIL-SEM-RASTRO-01. Sem `carimbo`, restaura a MAIS RECENTE — que é a
    versão de antes da última gravação, e portanto a resposta certa para
    "desfaça o que a janela acabou de fazer com meu perfil".

    Escreve os BYTES ORIGINAIS, não uma reserialização: a restauração tem de
    ser idêntica ao que foi guardado, inclusive na formatação, senão comparar
    antes e depois deixa de provar coisa alguma. A validação acontece mesmo
    assim (`Profile.model_validate`) para recusar devolver lixo ao disco.

    A versão ATUAL é arquivada antes de ser substituída — restaurar por engano
    também tem volta.
    """
    slug = _slug_para_historico(identifier)
    versoes = listar_historico(slug)
    if not versoes:
        raise FileNotFoundError(f"perfil sem histórico guardado: {identifier}")

    if carimbo is None:
        escolhida = versoes[-1]
    else:
        alvos = {carimbo, f"{carimbo}.json"}
        escolhida_ou_nada = next((v for v in versoes if v.name in alvos), None)
        if escolhida_ou_nada is None:
            raise FileNotFoundError(
                f"versão {carimbo!r} não existe no histórico de {identifier}"
            )
        escolhida = escolhida_ou_nada

    bruto = escolhida.read_bytes()
    try:
        Profile.model_validate(json.loads(bruto.decode("utf-8")))
    except _PROFILE_DECODE_ERRORS as exc:
        raise ValueError(
            f"versão {escolhida.name} não valida contra o schema: {exc}"
        ) from exc

    alvo = profiles_dir(ensure=True) / f"{slug}.json"
    with FileLock(str(_lock_path(alvo))):
        atual = _bytes_se_existe(alvo)
        if atual is not None:
            _arquivar_versao(slug, atual)
        _atomic_write_bytes(alvo, bruto)
    with contextlib.suppress(Exception):
        logger.info(
            "profile_restaurado",
            arquivo=alvo.name,
            versao=escolhida.name,
            origem=_origem_do_processo(),
            pid=os.getpid(),
        )
    return (alvo, escolhida)


def delete_profile(identifier: str) -> None:
    """Remove o arquivo do perfil. Aceita slug ou display name."""
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
                    _avisa_perfil_invalido(path, exc)
                    continue
                if other.name == profile.name:
                    candidate = path
                    break

    lock_file = _lock_path(candidate)
    with FileLock(str(lock_file)):
        conteudo = _bytes_se_existe(candidate)
        backup = (
            _arquivar_versao(candidate.stem, conteudo) if conteudo is not None else None
        )
        candidate.unlink()
    lock_file.unlink(missing_ok=True)
    with contextlib.suppress(Exception):
        logger.info(
            "profile_apagado",
            nome=profile.name,
            arquivo=candidate.name,
            origem=_origem_do_processo(),
            pid=os.getpid(),
            backup=str(backup) if backup is not None else None,
        )


def _atomic_write_json(target: Path, payload: object) -> None:
    _atomic_write_bytes(target, _bytes_do_payload(payload))


def _atomic_write_bytes(target: Path, bruto: bytes) -> None:
    """Escrita atômica de bytes crus (tmpfile + fsync + rename)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(bruto)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink(missing_ok=True)
        raise


__all__ = [
    "ARQUIVOS_DOS_ESTILOS_DE_JOGO",
    "CHAVES_DO_PERFIL_DE_JOGO",
    "ESTILOS_DE_JOGO_DIR_NAME",
    "HISTORICO_DIAS",
    "HISTORICO_DIR_NAME",
    "HISTORICO_MAX_VERSOES",
    "HISTORICO_SEMANA_DIAS",
    "HISTORICO_TETO_POR_PERFIL",
    "INTERVALO_MINIMO_DA_VARREDURA_S",
    "MARCA_DE_SEMEADURA_DE_JOGOS",
    "MOLDES_DE_PERFIL",
    "MOLDE_POR_CHAVE",
    "PREFIXO_DA_CHAVE_DE_JANELA",
    "PRIORIDADE_DO_PERFIL_DE_JOGO",
    "SEED_MARKER_NAME",
    "SEED_SKIP_ENV_VAR",
    "MoldeDePerfil",
    "PerfilSemeado",
    "ResultadoDaSemeadura",
    "ResultadoDosEstilos",
    "arquivo_do_perfil",
    "classes_de_jogo_da_marca",
    "classes_do_perfil_do_jogo",
    "classes_do_perfil_do_jogo_de_lancador",
    "delete_profile",
    "e_perfil_de_jogo_automatico",
    "enxugar_perfis_de_jogo",
    "gesto_de_agora",
    "historico_dir",
    "listar_historico",
    "load_all_profiles",
    "load_profile",
    "migrar_generos_para_estilos_de_jogo",
    "migrate_coop_local_match",
    "migrate_default_profile_name",
    "o_freestyle_de_fabrica_nasce_ligado",
    "o_mudo_do_microfone_vai_para_o_controle",
    "o_perfil_de_fora_do_jogo",
    "o_personalizado_vira_freestyle",
    "perfil_do_molde",
    "perfis_de_jogo_semeados",
    "perfis_para_consulta",
    "perfis_que_casam_com_o_cliente_steam",
    "reapontar_perfis_com_chave_de_executavel",
    "restaurar_do_historico",
    "save_profile",
    "seed_default_presets",
    "semear_perfis_dos_jogos",
]
