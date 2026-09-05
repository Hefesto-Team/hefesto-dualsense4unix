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
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from filelock import FileLock
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.slug import slugify
from hefesto_dualsense4unix.profiles.steam_app import (
    e_janela_do_cliente_steam,
    steam_appid_from_wm_class,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal

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
# navegacao/fps/point_and_click etc. A semântica é IDÊNTICA à do
# shell script (copy-if-absent + marker `.seeded_presets` que respeita deleção
# proposital da usuária); o formato do marker (um filename por linha) é contrato
# COMPARTILHADO entre os dois semeadores — mantê-los em sincronia.
SEED_MARKER_NAME = ".seeded_presets"

# --- PERFIL-PADRAO-PERSONALIZADO-01 (05/09/2026) ---------------------------
# Decisão dela, literal: *"Meu_perfil como perfil default nao deveria existir.  noqa-acento
# Deixa ou Meu Perfil ou Personalizado. acho esse melhor."*
#
# O nome `meu_perfil` era um SLUG aparecendo cru na lista da aba Perfis — ela
# lê o `Profile.name`, e o asset de fábrica gravava o slug ali. O padrão passa
# a nascer com nome de gente: "Personalizado", que slugifica para
# `personalizado.json`.
#
# O disco de quem já usa o produto é o centro do risco. Medido na máquina dela
# em 05/09: 33 perfis, e SÓ DOIS são catch-all (`fallback` prio 0 e
# `meu_perfil` prio 1) — o `meu_perfil.json` dela NÃO é o asset de fábrica,
# carrega os ajustes por controle (lightbar vermelha num, azul no outro, e as
# políticas de rumble). Semear `personalizado.json` por cima disso daria a ela
# DOIS padrões disputando, que é exatamente o que `profiles.sanidade`
# (`MAX_CATCH_ALL_TOLERADOS = 1`) chama de configuração machucando.
#
# Por isso são DUAS peças, e as duas precisam existir:
#   1. `migrate_default_profile_name` renomeia o arquivo DELA, preservando o
#      conteúdo e guardando o antigo — one-shot, com marker próprio.
#   2. os dois semeadores (aqui e `scripts/install_profiles.sh`) recusam
#      copiar `personalizado.json` enquanto `meu_perfil.json` existir no
#      destino. É a rede embaixo da migração: se ela não tiver rodado ainda
#      (install.sh chama o shell antes de qualquer processo Python carregar
#      perfil), o pior caso é ela continuar com o nome velho — nunca com dois.
NOME_DO_PADRAO = "Personalizado"
NOME_ANTIGO_DO_PADRAO = "meu_perfil"
ARQUIVO_DO_PADRAO = "personalizado.json"
ARQUIVO_ANTIGO_DO_PADRAO = "meu_perfil.json"

#: O arquivo antigo não é apagado: vira este nome. Não termina em `.json`, e
#: por isso some do `glob("*.json")` de TODO leitor de perfil desta casa — a
#: lista dela não ganha uma linha, e o arquivo continua no disco para quem
#: quiser desfazer à mão.
BACKUP_DO_PADRAO = "meu_perfil.json.antes-de-personalizado"

_RENAME_PADRAO_MARKER = ".perfil_padrao_renomeado"

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
            # PERFIL-PADRAO-PERSONALIZADO-01: o slot dela JÁ EXISTE sob o nome
            # antigo. Copiar o asset aqui criaria um SEGUNDO catch-all — e o
            # segundo catch-all é o defeito que `profiles.sanidade` existe
            # para acusar. Registra sem copiar: a migração renomeia o dela.
            if (
                fname == ARQUIVO_DO_PADRAO
                and (directory / ARQUIVO_ANTIGO_DO_PADRAO).exists()
            ):
                new_entries.append(fname)
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


# ---------------------------------------------------------------------------
# A MÁSCARA NÃO É DO PRESET (MASCARA-QUE-GRUDA-01, 22/08/2026) — decisão dela
# ---------------------------------------------------------------------------
# Ela, literal: *"A máscara deve vir da escolha do user. Ele escolhe como quer
# que o jogo reconheça o controle conectado: se deve aparecer como Xbox ou
# DualSense."*
#
# Consequência: **preset de gênero não tem opinião sobre máscara.** Preset é
# sobre gatilho, vibração e luz; quem aplica "Ação" não pode descobrir depois
# que ele também trocou o aparelho que o jogo enxerga. Os sete presets de jogo
# passam a shipar `"gamepad_flavor": null` — que o applier já entende como
# "MANTÉM a máscara que estiver valendo".
#
# O QUE SAIU DAQUI, e por que não volta
# --------------------------------------
# `migrate_game_presets_to_xbox` (SPRINT-GAME-RUMBLE-01) era a one-shot que
# trocava `dualsense`->`xbox` no `sackboy_nativo`/`coop_local` já semeados,
# justificada pela H1 da auditoria pré-release ("a máscara DualSense faz o jogo
# ignorar o gamepad virtual"). Ela FOI removida em 22/08/2026, e o que a
# derruba não é a H1 ter caído — a H1 segue **sem remedição** (E1 da sprint) —
# é a decisão dela: escrever máscara no perfil de alguém é o produto escolhendo
# por ela, e desde `2b11172` essa escolha GRUDA no disco até ela mudar.
#
# O marker `.flavor_xbox_migrated` continua no disco de quem já rodou a
# migração. Ele é inerte: ninguém mais o lê, e apagá-lo não faz nada voltar.
#
# NENHUMA MIGRAÇÃO NOVA ESCREVE MÁSCARA — nem a inversa. Quem tem `xbox` no
# disco pode tê-lo escolhido: o preset shipava `xbox` E o seletor grava `xbox`,
# e nada no arquivo separa os dois casos. Uma migração inversa desfaria em
# silêncio uma escolha real — que é o defeito que esta sprint existe para
# matar, com o sinal trocado. Portão: `test_o_preset_nao_escolhe_a_mascara.py`.


def _repontar_a_sessao_para_o_padrao_novo() -> None:
    """Faz `session.json` e `active_profile.txt` seguirem o perfil renomeado.

    Os dois guardam o NOME do último perfil que ela ativou na mão, e o daemon
    restaura por esse nome no boot (`resolve_boot_profile`). Sem esta linha, a
    renomeação deixaria os dois apontando um perfil que não existe mais: o
    `restore_last_profile` falharia, logaria `last_profile_restore_failed` e o
    boot ficaria SEM perfil — a metade B deste item quebrada pela metade A.

    Só reescreve o que apontava para o nome antigo. Best-effort dos dois lados,
    pelo mesmo contrato de `utils.session`: nunca propaga exceção.
    """
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
    """One-shot: o perfil padrão deixa de se chamar `meu_perfil`.

    PERFIL-PADRAO-PERSONALIZADO-01 (ver o bloco no topo do módulo). Devolve o
    nome novo quando renomeou, `None` em toda recusa.

    O que ela tem no disco é o valor a proteger, então a migração RECUSA em
    quatro casos, e cada recusa tem teste:

    - `meu_perfil.json` ausente — máquina nova, nada a migrar (o semeador
      entrega o `personalizado.json` de fábrica).
    - `personalizado.json` já existe — ela própria criou um perfil com esse
      nome. Sobrescrever seria destruir configuração dela; o velho fica.
    - o JSON não abre, ou o `name` lá dentro não é exatamente `meu_perfil` —
      ela já renomeou o perfil na mão, e a identidade é dela.
    - o marker já existe — a migração é one-shot, como as vizinhas.

    Quando renomeia, a ORDEM é o que garante que ela não perca nada: o arquivo
    novo é escrito e trocado atomicamente ANTES de o antigo sair do caminho. Um
    disco cheio no meio deixa o disco dela exatamente como estava.
    """
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
        if novo.exists() and antigo.is_file():
            desfecho = "personalizado_ja_existe"
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
                    # Só agora o antigo sai de cena — e sai para um nome que
                    # nenhum `glob("*.json")` enxerga, em vez de para o lixo.
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



#: R-12 (auditoria 23/07): marker da migração do `match` inalcançável do
#: coop_local. O preset de fábrica de 14/07 saiu com `MatchCriteria` de campos
#: TODOS vazios — `matches()` devolve False sem condição alguma (schema.py:52),
#: então o autoswitch NUNCA o escolhe. O asset novo tem o regex de jogos de
#: co-op; `seed_default_presets` não sobrescreve (está no `.seeded_presets`),
#: então o arquivo LOCAL de quem já tinha o preset velho fica preso — por isso
#: esta migração one-shot.
#:
#: APOSENTADA em 26/08/2026, e a nota fica porque a decisão foi MEDIDA. A poda
#: da fábrica (palavra dela: *"em termos de perfis de jogo vamos manter os que
#: temos ativos apenas"*) apagou `assets/profiles_default/coop_local.json`, e é
#: desse asset que esta migração copia `match` e `priority`. Sem ele
#: `_seed_source_file` devolve `None` e a migração vira no-op — quem tem um
#: `coop_local` velho no disco fica preso com o `match` inalcançável para
#: sempre. O código NÃO tenta adivinhar o regex perdido: escrever `match` de
#: memória em perfil de alguém é o produto escolhendo por ela. O que ele faz é
#: **relatar** — `migracao_aposentada_sem_asset` no journal, uma vez, com o
#: arquivo e o efeito — porque migração muda é decisão apagada em silêncio, e
#: silêncio é o defeito que esta casa mais paga.
_COOP_LOCAL_MATCH_MIGRATION_MARKER = ".coop_local_match_migrated"


def _relatar_migracao_aposentada(migracao: str, arquivo: str) -> None:
    """Diz no journal que uma migração one-shot perdeu o asset que a alimenta.

    A alternativa era o `continue` mudo, e ele é pior do que parece: o perfil
    velho continua no disco, inalcançável, e nada em lugar nenhum diz por quê.
    Quem for diagnosticar *"por que este perfil nunca entra?"* precisa desta
    linha para não reabrir a investigação do zero.
    """
    logger.info(
        "migracao_aposentada_sem_asset",
        migracao=migracao,
        arquivo=arquivo,
        motivo="o preset de fábrica foi podado em 26/08/2026",
        efeito="o perfil local fica como está — nada é reescrito",
    )


def migrate_coop_local_match(dest_dir: Path | None = None) -> list[str]:
    """One-shot: dá um `match` alcançável ao coop_local que veio VAZIO de fábrica.

    APOSENTADA em 26/08/2026 — o asset de fábrica que a alimenta foi podado, e
    sem ele ela não tem de onde copiar `match`. Continua sendo chamada, e nesse
    estado o que ela faz é RELATAR (`migracao_aposentada_sem_asset`) em vez de
    calar. O porquê inteiro está na nota do marker, acima.

    R-12 (auditoria 23/07). Só reescreve quando o preset ainda está EXATAMENTE
    no estado inalcançável de fábrica — `MatchCriteria` com os três campos
    vazios/ausentes E `mode.kind == "gamepad"` (isto é:
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
        if path.is_file() and asset is None:
            # APOSENTADA (26/08/2026): o asset foi podado. Relata e não mexe.
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
    """True quando o coop_local ainda está no estado de fábrica inalcançável.

    Match `criteria` com os três campos vazios/ausentes E `mode.kind=="gamepad"`.
    Qualquer desvio = a usuária mexeu, e a migração recua.
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
    return isinstance(mode, dict) and mode.get("kind") == "gamepad"


#: MODO-01: marker da migração que leva a seção `mode` aos presets de jogo já
#: semeados, junto com a prioridade nova do co-op.
_MODO_JOGO_MIGRATION_MARKER = ".modo_jogo_nos_presets_migrated"

#: MODO-01: os presets de gênero que ganharam `mode: gamepad`. `coop_local` fica
#: de fora porque já nasce com modo — dele só muda a prioridade.
_PRESETS_DE_JOGO = ("fps", "aventura", "acao", "corrida", "esportes")  # (noqa-acento)

#: O ramo `coop_local` desta migração está APOSENTADO desde 26/08/2026, pelo
#: mesmo motivo da `migrate_coop_local_match`: o asset foi podado da fábrica e
#: a prioridade nova vinha DELE. Os cinco presets de gênero acima continuam
#: sendo migrados normalmente — o asset de cada um segue no repositório.
_COOP_LOCAL_APOSENTADO = "coop_local"


def migrate_modo_jogo_nos_presets(dest_dir: Path | None = None) -> list[str]:
    """One-shot: leva `mode` e prioridade novos aos presets JÁ instalados (MODO-01).

    Sem isto a sprint MODO-01 conserta só quem instalar do zero. A semeadura
    (`seed_default_presets`) não sobrescreve arquivo existente — de propósito,
    é o que impede o projeto de apagar a configuração da usuária —, então na
    máquina de quem já usa o Hefesto os presets de gênero continuariam com
    ``mode: null`` e o `coop_local` com a prioridade que perde para o perfil de
    navegação. Medido na máquina de desenvolvimento em 25/07: 11 dos 13 perfis
    sem `mode`, e `coop_local` em 45 contra `navegacao` em 50 — abrir um jogo de
    co-op pela Steam entregava o perfil de navegação.

    A regra de recuo é a mesma das migrações irmãs, e é o que torna isto seguro:
    só escreve onde o campo ainda está no estado de fábrica. Preset com `mode`
    já definido (por ela ou por migração anterior) não é tocado; prioridade
    diferente da de fábrica antiga significa que ela mexeu, e aí também recua.

    Idempotente por marker próprio. Best-effort: falha loga e segue.
    """
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
                # APOSENTADO (26/08/2026): o asset foi podado. Relata e não mexe.
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
            # `mode` só entra onde ainda não há NENHUM — nunca por cima do dela.
            if nome in _PRESETS_DE_JOGO and data.get("mode") in (None, {}):
                modo_asset = asset_data.get("mode")
                if isinstance(modo_asset, dict):
                    data["mode"] = modo_asset
                    mudou = True
            # A prioridade sobe só se ainda for a de fábrica ANTIGA: qualquer
            # outro número é escolha dela e vence a migração.
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
        # PERFIL-PADRAO-PERSONALIZADO-01: ANTES da semeadura, e a ordem é o
        # ponto. Depois da renomeação o `personalizado.json` dela já existe no
        # destino, então o semeador cai no ramo "presente na 1ª execução" e
        # REGISTRA sem copiar — o asset de fábrica nunca encosta no arquivo
        # dela. Invertida, a ordem faria o semeador entregar o preset nu e a
        # migração recusar por "personalizado_ja_existe", deixando os dois.
        with contextlib.suppress(Exception):
            migrate_default_profile_name()
        seed_default_presets()
        # MASCARA-QUE-GRUDA-01 (22/08/2026): aqui rodava a
        # `migrate_game_presets_to_xbox`. Nenhuma migração escreve máscara em
        # perfil — o motivo inteiro está na nota acima do bloco que a substituiu.
        # R-12: dá um match alcançável ao coop_local que veio vazio de fábrica
        # (o preset de 14/07 era inalcançável pelo autoswitch). One-shot.
        with contextlib.suppress(Exception):
            migrate_coop_local_match()
        # MODO-01: leva `mode: gamepad` aos presets de gênero já instalados e
        # tira o co-op de trás do perfil de navegação. Sem isto a sprint
        # conserta só quem instalar do zero. One-shot.
        with contextlib.suppress(Exception):
            migrate_modo_jogo_nos_presets()
    except Exception as exc:  # boundary best-effort (ver docstring)
        logger.warning(
            "presets_seed_failed",
            err=str(exc),
            err_type=type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# UM PERFIL POR JOGO (22/08/2026) — decisão dela
# ---------------------------------------------------------------------------
# Ela, literal: *"acho que por default já deveria ter um perfil por jogo
# instalado. Por default na nossa lista, e lá eu só ativaria o perfil do jogo,
# sairia modificando as abas pra setar o perfil, salvaria e aplicaria, e todas
# as próximas vezes esse jogo automaticamente abriria com o perfil aplicado pra
# todos os controles."*
#
# É AUTOMÁTICO, e não um botão: ela corrigiu a própria escolha anterior
# ("semear só os que faltam" era um GESTO). O produto cria sozinho, inclusive
# para o jogo que ela instalar amanhã.
#
# QUANDO, e a razão de cada corte:
#
# - a varredura pendura na PRIMEIRA carga de perfis do processo, que é onde a
#   semeadura de presets já mora — isso cobre o arranque do daemon, o da janela
#   e o da CLI sem gancho novo em lugar nenhum;
# - e NÃO para aí. O daemon dela fica dias de pé, e o jogo instalado amanhã não
#   pode esperar um reboot. Então a varredura é RE-TENTÁVEL, com dois freios:
#   um piso de tempo (`INTERVALO_MINIMO_DA_VARREDURA_S`), porque
#   `load_all_profiles()` é chamado a cada troca de janela pelo
#   `profiles/manager.py` e ler 33 `.acf` a cada alt-tab seria disco à toa; e a
#   assinatura da biblioteca (`jogos_locais.assinatura_da_biblioteca`), que são
#   dois `stat()` de diretório — instalar ou desinstalar jogo muda o `mtime` da
#   `steamapps`, e "nada mudou" custa microssegundos.
#
# Varrer só no boot deixaria o jogo de amanhã de fora; varrer a cada carga
# cobraria disco a cada alt-tab. O par piso-de-tempo + assinatura faz as duas
# pontas, e é por isso que ele existe em vez de um `if` só.
#
# O QUE NASCE, e o que NÃO nasce: nome do jogo, `match` pelo appid, prioridade
# 80 — e nada mais. Nem cor, nem gatilho, nem modo. O fluxo dela é *"eu
# ativaria e sairia modificando as abas"*; um perfil semeado com cor decidida
# seria o produto escolhendo por ela.

#: Um registro por jogo já processado, no diretório de perfis. Formato:
#: ``<appid>\t<arquivo.json>`` para o que ESTE produto criou, e ``<appid>\t``
#: (segundo campo vazio) para o jogo que o produto NÃO criou porque ela já
#: tinha um perfil para ele.
#:
#: É a "marca de semeadura" do pedido, e ela responde a duas perguntas que sem
#: marca nenhuma são indistinguíveis: *o que é meu e o que é dela* (só o que
#: tem arquivo no segundo campo é do produto — base de qualquer desfazer do
#: lote) e *o que já foi decidido* (appid registrado não volta a ser semeado,
#: nem depois de ela apagar o perfil — mesmo contrato de `.seeded_presets`:
#: perfil que ela apagou de propósito não ressuscita).
MARCA_DE_SEMEADURA_DE_JOGOS = ".perfis_de_jogo_semeados"

#: A prioridade do perfil semeado. O 80 foi COPIADO, não escolhido: era o do
#: `sackboy_nativo`, o preset de fábrica que mirava um jogo.
#:
#: FONTE APOSENTADA em 26/08/2026 — a poda da fábrica apagou aquele asset, e o
#: número ficou. Ele NÃO se apaga junto: a ordem que o autoswitch precisa
#: continua sendo a mesma, e é ela que justifica o 80 hoje — acima dos presets
#: de gênero (55-70) e da Navegação (50), para que a regra do JOGO ganhe do
#: genérico de desktop. O que caducou foi o endereço de onde o número veio, e
#: por isso ele está escrito aqui em vez de citado num arquivo que já não abre.
PRIORIDADE_DO_PERFIL_DE_JOGO = 80

#: Piso entre duas varreduras no MESMO processo. Cinco minutos é o compromisso
#: entre "ela instalou um jogo agora" e "não custe disco a cada alt-tab" — a
#: assinatura da biblioteca já derruba a varredura para dois `stat()` quando
#: nada mudou, então este piso protege só os dois `stat()`.
INTERVALO_MINIMO_DA_VARREDURA_S = 300.0

#: Cada linha do relatório da semeadura. Ver `PerfilSemeado`.
DesfechoDaSemeadura = Literal[
    "criado",
    "ja_tinha_perfil",
    "ja_semeado",
    "nome_ocupado",
    "casa_com_a_loja",
    "sem_slug",
]

#: Os dois desfechos que ficam GRAVADOS na marca. Os outros são recusas que
#: podem deixar de valer (ela renomeia o perfil que ocupava o nome) e por isso
#: são reavaliadas na próxima mudança da biblioteca, em vez de viverem para
#: sempre num arquivo.
_DESFECHOS_QUE_MARCAM: frozenset[str] = frozenset({"criado", "ja_tinha_perfil"})


@dataclass(frozen=True)
class PerfilSemeado:
    """O que aconteceu com UM jogo na varredura — e por quê.

    ELO-MUDO-01: um contador de criados responderia pelo transporte e não pelo
    efeito. "Nasceram 3 perfis" não distingue *os outros 10 já tinham* de *os
    outros 10 foram recusados por colisão de nome*, e ausência de notícia é
    justamente o que esta casa aprendeu a ler como sucesso falso.
    """

    appid: str
    jogo: str
    desfecho: DesfechoDaSemeadura
    #: O arquivo criado — só no desfecho ``criado``. Nos outros, o arquivo que
    #: EXPLICA a recusa (o perfil dela que já cobre o appid, ou que já ocupa o
    #: nome), ou vazio quando não há arquivo envolvido.
    arquivo: str = ""


@dataclass(frozen=True)
class ResultadoDaSemeadura:
    """O relatório inteiro de uma varredura."""

    linhas: tuple[PerfilSemeado, ...] = ()
    #: Os arquivos que a varredura CRIOU nesta passada.
    criados: tuple[str, ...] = ()
    #: Perfis já existentes cujo `match` casa com a janela do CLIENTE Steam —
    #: o aviso do defeito irmão. Ver `perfis_que_casam_com_o_cliente_steam`.
    avisos_da_loja: tuple[tuple[str, str, tuple[str, ...]], ...] = ()

    def por_desfecho(self, desfecho: str) -> tuple[PerfilSemeado, ...]:
        """As linhas de um desfecho — o que os testes e a tela perguntam."""
        return tuple(linha for linha in self.linhas if linha.desfecho == desfecho)


# Estado por PROCESSO da varredura re-tentável (ver o cabeçalho da seção).
# Nada disso vai para disco: reler 33 `.acf` no arranque custa o mesmo que a
# semeadura de presets que já roda ali, e um arquivo de estado a mais seria uma
# terceira coisa para ficar velha.
_ultima_varredura_de_jogos: float | None = None
_assinatura_da_biblioteca_vista: tuple[tuple[str, int], ...] | None = None


def _caminho_da_marca(directory: Path) -> Path:
    return directory / MARCA_DE_SEMEADURA_DE_JOGOS


def _linhas_da_marca(marca: Path) -> list[tuple[str, str]]:
    """``[(appid, arquivo)]`` do arquivo de marca. Ausente/ilegível = vazio."""
    try:
        bruto = marca.read_text(encoding="utf-8")
    except OSError:
        return []
    lidas: list[tuple[str, str]] = []
    for linha in bruto.splitlines():
        appid, _, arquivo = linha.strip().partition("\t")
        if not appid.isdigit():
            continue
        lidas.append((appid, arquivo.strip()))
    return lidas


def perfis_de_jogo_semeados(dest_dir: Path | None = None) -> dict[str, str]:
    """``{appid: arquivo}`` do que o PRODUTO criou — nunca do que é dela.

    É a resposta de "quais destes perfis eu posso desfazer sem tocar no
    trabalho dela". Um jogo que o produto NÃO criou (porque ela já tinha
    perfil) está na marca com o segundo campo vazio e **não aparece aqui**.

    Esta função só INFORMA. Não apaga nada, e nada nesta entrega apaga: o
    estrago que a leva de 05/08 passou uma semana consertando foi perfil
    apagado, e um caminho automático que apaga não existe aqui nem para o que é
    do próprio produto. O arquivo pode ter sido renomeado ou apagado por ela
    desde então — quem for oferecer o desfazer confere a existência na hora.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir()
    return {
        appid: arquivo
        for appid, arquivo in _linhas_da_marca(_caminho_da_marca(directory))
        if arquivo
    }


def _dados_crus_do_perfil(path: Path) -> dict[str, object] | None:
    """O JSON do perfil sem validar pelo schema. None se não der para ler.

    CRU de propósito: as duas varreduras abaixo (que appid já tem dono, que
    perfil casa com a loja) precisam enxergar TAMBÉM o perfil que o schema
    rejeita. Um perfil corrompido que ocupa o nome ``sea_of_stars.json``
    continua ocupando o nome, e semear por cima dele seria a sobrescrita que
    esta entrega existe para não fazer.
    """
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


def _appids_com_dono(directory: Path) -> dict[str, str]:
    """``{appid: arquivo}`` dos jogos que JÁ têm perfil no diretório.

    **A conferência é pelo APPID, nunca pelo nome do arquivo**, e isso é medido
    no disco dela: o perfil do Sackboy se chamava ``sackboy_nativo``, não
    ``Sackboy: A Big Adventure`` (o preset de fábrica com esse nome foi podado
    em 26/08/2026; o perfil DELA continua lá, com o mesmo descasamento entre
    nome de arquivo e nome de jogo). Uma checagem por nome de arquivo não o
    encontraria, e o produto criaria um SEGUNDO perfil para o mesmo jogo —
    dois perfis empatados em 80 disputando a mesma janela, que é o defeito que
    `profiles/sanidade.py` chama de `prioridades_empatadas`.
    """
    donos: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        dados = _dados_crus_do_perfil(path)
        if dados is None:
            continue
        for classe in _classes_do_match(dados):
            appid = steam_appid_from_wm_class(classe)
            if appid is not None:
                donos.setdefault(str(appid), path.name)
    return donos


def perfis_que_casam_com_o_cliente_steam(
    dest_dir: Path | None = None,
) -> list[tuple[str, str, tuple[str, ...]]]:
    """``[(arquivo, nome, classes)]`` dos perfis que casam com a LOJA.

    O defeito irmão, decisão dela na mesma rodada: *"tirar 'steam' e 'Steam' do
    perfil Navegação"*. Treze trocas de perfil no meio da partida em 54
    minutos, porque uma janela invisível do `steamwebhelper` se anuncia com a
    `wm_class` ``steam``.

    **A FÁBRICA FOI CURADA em 25/08/2026** (``D-STEAM-SAI-DA-NAVEGACAO``,
    decidida por ela em 22/08): ``assets/profiles_default/navegacao.json`` não
    lista mais ``steam`` nem ``Steam``, e quem instalar daqui em diante nasce
    sem o defeito. A mordida que impede o retorno é
    ``tests/unit/test_a_fabrica_nao_casa_com_a_loja.py``.

    **Esta função continua necessária, e é por isso que ela não foi apagada
    junto:** ela olha o diretório VIVO, não a fábrica. Perfil que a pessoa
    escreveu à mão, perfil de instalação antiga que já tem ``steam`` gravado, e
    perfil copiado de outra máquina continuam alcançando o defeito — a fábrica
    curada só protege quem nasce hoje.

    **O arquivo vivo é dela e o produto não o edita.** O que o produto faz é
    DIZER, que é o que faltava: até aqui a troca de perfil acontecia em
    silêncio, e ela levou 54 minutos de partida para descobrir de onde vinha.

    O predicado é `profiles/steam_app.e_janela_do_cliente_steam`, o mesmo que o
    `lifecycle` usa para proteger a partida — não uma segunda lista de nomes.
    """
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
    """As `window_class` do perfil semeado. UMA, e é o endereço do jogo.

    Separada de `_perfil_do_jogo` para que a guarda "isto casa com a loja?"
    possa perguntar ANTES de existir perfil nenhum — e para que o teste da
    guarda tenha o que arrancar.
    """
    return [f"steam_app_{appid}"]


def _perfil_do_jogo(jogo: JogoLocal) -> Profile:
    """O perfil que nasce para um jogo — e SÓ o que o pedido dela manda.

    Nome do jogo como veio do `appmanifest` (o produto não reescreve o nome que
    a Steam dá), `match` pelo appid e prioridade 80. Todo o resto fica no
    default do schema, que é o "sem opinião" desta casa: gatilhos ``Off``,
    `leds` com `auto_player_colors` (cada controle acende a cor do seu slot) e
    as seções opcionais em ``None``, que `_payload_do_perfil` nem grava.
    """
    return Profile(
        name=jogo.nome,
        match=MatchCriteria(window_class=classes_do_perfil_do_jogo(jogo.appid)),
        priority=PRIORIDADE_DO_PERFIL_DE_JOGO,
    )


def _gravar_sem_pisar(alvo: Path, payload: object) -> bool:
    """Grava o JSON SÓ se `alvo` ainda não existe. ``True`` = gravou.

    O `os.link` é o desenho, não detalhe de implementação: ele é atômico e
    falha com `FileExistsError` quando o alvo já está lá, então **não existe
    janela** entre "conferi que não existe" e "escrevi". `_atomic_write_json`
    usa `os.replace`, que PISA — e apagar perfil dela é o estrago que a leva de
    05/08 passou uma semana consertando. Aqui quem recusa é o kernel.

    Sistema de arquivos sem hardlink cai no `O_CREAT|O_EXCL`, que dá a mesma
    recusa (sem a atomicidade da escrita: um crash no meio deixa JSON truncado,
    que `load_all_profiles` pula com `profile_invalid`).
    """
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


def semear_perfis_dos_jogos(
    dest_dir: Path | None = None,
    home: Path | None = None,
    jogos: Sequence[JogoLocal] | None = None,
) -> ResultadoDaSemeadura:
    """Cria um perfil para cada jogo da biblioteca Steam que ainda não tem.

    As quatro recusas, e nenhuma delas apaga nem sobrescreve nada:

    - **`ja_semeado`** — o appid está na marca. Não volta a nascer, nem depois
      de ela apagar o perfil (mesmo contrato de `.seeded_presets`).
    - **`ja_tinha_perfil`** — algum perfil do diretório já mira este appid.
      Fica registrado na marca com o campo de arquivo VAZIO: o produto sabe que
      tratou o jogo, e sabe que o arquivo não é dele.
    - **`nome_ocupado`** — o nome do jogo dá no mesmo arquivo que outro perfil
      já ocupa. Colisão de nome é RECUSA, nunca sobrescrita. Não vai para a
      marca: se ela renomear o perfil que ocupava o nome, a próxima varredura
      tenta de novo.
    - **`casa_com_a_loja`** — guarda de invariante. O `match` que sai daqui é
      sempre ``steam_app_<n>``, que nunca é a janela do cliente Steam; se um
      dia deixar de ser, a semeadura recusa em vez de plantar treze cópias do
      defeito que custou 54 minutos de partida a ela.

    `jogos` injetável para teste hermético — nenhum teste desta entrega toca a
    biblioteca real dela.
    """
    directory = dest_dir if dest_dir is not None else profiles_dir(ensure=True)
    directory.mkdir(parents=True, exist_ok=True)
    if jogos is None:
        # Import TARDIO: `profiles/` não importa `integrations/` no topo — é a
        # mesma disciplina de grafo que `profiles/manager.py` já segue com o
        # `desktop_notifications`.
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            jogos_da_biblioteca_steam,
        )

        jogos = jogos_da_biblioteca_steam(home)

    marca = _caminho_da_marca(directory)
    linhas: list[PerfilSemeado] = []
    criados: list[str] = []
    # O MESMO FileLock da marca segura a varredura inteira: daemon e janela
    # semeando ao mesmo tempo no primeiro boot é o caso normal, não o exótico.
    with FileLock(str(_lock_path(marca))):
        ja_processados = {appid for appid, _ in _linhas_da_marca(marca)}
        donos = _appids_com_dono(directory)
        ocupados = {p.name for p in directory.glob("*.json")}
        novas: list[tuple[str, str]] = []
        for jogo in sorted(jogos, key=lambda j: (j.nome.casefold(), j.appid)):
            linha = _semear_um_jogo(jogo, directory, ja_processados, donos, ocupados)
            linhas.append(linha)
            if linha.desfecho == "criado":
                criados.append(linha.arquivo)
                ocupados.add(linha.arquivo)
                donos[jogo.appid] = linha.arquivo
            if linha.desfecho in _DESFECHOS_QUE_MARCAM:
                novas.append(
                    (jogo.appid, linha.arquivo if linha.desfecho == "criado" else "")
                )
        if novas or not marca.exists():
            with marca.open("a", encoding="utf-8") as fh:
                for appid, arquivo in novas:
                    fh.write(f"{appid}\t{arquivo}\n")

    avisos = perfis_que_casam_com_o_cliente_steam(directory)
    _relatar_semeadura(linhas, criados, avisos)
    return ResultadoDaSemeadura(
        linhas=tuple(linhas), criados=tuple(criados), avisos_da_loja=tuple(avisos)
    )


def _semear_um_jogo(
    jogo: JogoLocal,
    directory: Path,
    ja_processados: set[str],
    donos: dict[str, str],
    ocupados: set[str],
) -> PerfilSemeado:
    """A decisão de UM jogo. Ver `semear_perfis_dos_jogos` para as recusas."""
    if jogo.appid in ja_processados:
        return PerfilSemeado(jogo.appid, jogo.nome, "ja_semeado", donos.get(jogo.appid, ""))
    dono = donos.get(jogo.appid)
    if dono is not None:
        return PerfilSemeado(jogo.appid, jogo.nome, "ja_tinha_perfil", dono)
    try:
        slug = slugify(jogo.nome)
    except ValueError:
        return PerfilSemeado(jogo.appid, jogo.nome, "sem_slug")
    arquivo = f"{slug}.json"
    if arquivo in ocupados:
        return PerfilSemeado(jogo.appid, jogo.nome, "nome_ocupado", arquivo)
    if any(e_janela_do_cliente_steam(c) for c in classes_do_perfil_do_jogo(jogo.appid)):
        return PerfilSemeado(jogo.appid, jogo.nome, "casa_com_a_loja", arquivo)
    perfil = _perfil_do_jogo(jogo)
    if not _gravar_sem_pisar(directory / arquivo, _payload_do_perfil(perfil)):
        # Outro processo criou o arquivo entre o glob e o link. Recusa, e a
        # próxima varredura vai enxergá-lo como dono do appid.
        return PerfilSemeado(jogo.appid, jogo.nome, "nome_ocupado", arquivo)
    return PerfilSemeado(jogo.appid, jogo.nome, "criado", arquivo)


def _relatar_semeadura(
    linhas: Sequence[PerfilSemeado],
    criados: Sequence[str],
    avisos: Sequence[tuple[str, str, tuple[str, ...]]],
) -> None:
    """Diz o que a varredura fez — inclusive quando não fez nada de novo.

    ELO-MUDO-01: cada RECUSA sai nomeada, com o jogo e o arquivo que a explica.
    Um "semeei 0" sem motivo é indistinguível de "nem tentei".
    """
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
            if linha.desfecho in {"nome_ocupado", "casa_com_a_loja", "sem_slug"}:
                logger.warning(
                    "perfil_de_jogo_recusado",
                    appid=linha.appid,
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

    Chamado de toda carga de perfis. A primeira chamada do processo SEMPRE
    varre (a assinatura começa desconhecida), e é ela que cobre o arranque do
    daemon e o da janela; as seguintes só passam do piso de tempo e da
    assinatura quando a biblioteca mudou de verdade.

    Uma falha aqui NUNCA pode impedir a carga dos perfis que já existem —
    mesmo contrato de `_maybe_seed_presets`.
    """
    global _ultima_varredura_de_jogos, _assinatura_da_biblioteca_vista
    if os.environ.get(SEED_SKIP_ENV_VAR) == "1":
        return
    agora = time.monotonic()
    if (
        _ultima_varredura_de_jogos is not None
        and agora - _ultima_varredura_de_jogos < INTERVALO_MINIMO_DA_VARREDURA_S
    ):
        return
    _ultima_varredura_de_jogos = agora
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            assinatura_da_biblioteca,
        )

        assinatura = assinatura_da_biblioteca()
        if assinatura == _assinatura_da_biblioteca_vista:
            return
        semear_perfis_dos_jogos()
        # Só depois de a varredura TERMINAR: uma exceção no meio não pode
        # registrar a biblioteca como já tratada.
        _assinatura_da_biblioteca_vista = assinatura
    except Exception as exc:  # boundary best-effort (ver docstring)
        logger.warning(
            "semeadura_de_jogos_falhou",
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
    _talvez_semear_jogos()
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


def perfil_em_disco(identifier: str) -> Profile | None:
    """O perfil que está NO ARQUIVO agora — sem semear, sem varrer, sem levantar.

    PONTE-SOBREVIVE-A-CORRIDA-01 (28/08/2026). Existe porque as duas memórias
    que a janela tem de um perfil são FOTOGRAFIAS — o ``draft.source_*`` do boot
    e o ``_profiles_cache`` da lista — e há campo que outro processo escreve
    direto no arquivo enquanto ela está aberta (o carimbo de ponte, por
    ``profiles.manager.confirmar_ponte``). Para esses, perguntar ao ARQUIVO é a
    única resposta que não envelhece.

    Por que não é ``load_profile``: ele dispara ``_maybe_seed_presets`` e
    ``_talvez_semear_jogos`` — a segunda VARRE a biblioteca da Steam — e, quando
    não acha de primeira, lê o diretório inteiro. É o carregador do boot. Esta
    aqui é chamada da thread do GTK, no clique de Salvar, onde cabe UM arquivo e
    não uma varredura (PERF-GUI-PROFILE-LOAD-NONBLOCKING-01).

    O alvo é ``<slugify(identifier)>.json``, que é EXATAMENTE o arquivo que
    ``save_profile`` vai escrever: a pergunta é *"o que este Salvar vai
    sobrescrever?"*, e quem responde é o nome do arquivo (R-10). Não há
    varredura de fallback de propósito — um arquivo cujo nome não acompanha o
    slug do ``name`` não é o que este save vai tocar.

    Devolve ``None`` para ausente, ilegível ou inválido: quem chama está
    CONSULTANDO, não carregando, e um perfil corrompido não pode virar exceção
    num caminho de interface. O traversal está fechado pelo contrato do
    ``slugify``, cuja saída é ``[a-z0-9_]`` não-vazia.
    """
    try:
        alvo = profiles_dir(ensure=True) / f"{slugify(identifier)}.json"
    except ValueError:
        return None
    if not alvo.exists():
        return None
    try:
        return _read_profile(alvo)
    except _PROFILE_DECODE_ERRORS as exc:
        logger.warning(
            "profile_invalid",
            path=str(alvo),
            err=str(exc),
            err_type=type(exc).__name__,
        )
        return None


def load_all_profiles() -> list[Profile]:
    """Lê todos os perfis JSON do diretório, pulando os inválidos com warning.

    PROFILE-LOADER-UX-01: um perfil corrompido não deve impedir o carregamento
    dos demais. Emite `WARN profile_invalid path=... err=...` para cada arquivo
    que falhar a decodificação ou validação Pydantic.
    """
    _maybe_seed_presets()
    _talvez_semear_jogos()
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


#: SOM-02/E4: seções OPCIONAIS do perfil que não são gravadas quando valem
#: ``None`` — "sem opinião" é a AUSÊNCIA da chave no arquivo, nunca um `null`.
#: Requisito de compatibilidade para trás (ver `save_profile`), não estética:
#: um binário anterior a qualquer uma delas tem ``extra="forbid"`` no `Profile`
#: e rejeitaria TODOS os perfis no downgrade, não só os que usam a seção.
#: ``controllers`` tem tratamento próprio logo abaixo (mapa vazio também sai).
_SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE: tuple[str, ...] = (
    "speaker",
    "mouse",
    "mic",
    "mode",
    "key_bindings",
    # Z4/T14 (24/08/2026): mesmo requisito de compatibilidade — sem a
    # omissão, TODO save gravaria `"teclado_emulado": null` e um binário
    # anterior a esta sprint (`extra="forbid"`) rejeitaria TODOS os perfis
    # no downgrade. Achado pela própria rede de regressão desta leva
    # (`test_profile_speaker_section.py::test_binario_antigo_...`), não
    # previsto pela sprint.
    "teclado_emulado",
    # FEAT-ACOES-DE-BOTAO-01 (01/09/2026): a terceira vez que a MESMA regra é
    # cobrada pelo mesmo teste, e a terceira vez que ela não foi lembrada por
    # quem escreveu o campo — eu inclusive. O `test_binario_antigo_ainda_carrega
    # _perfil_salvo_por_este` pegou na hora: sem esta linha, todo save passa a
    # gravar `"button_actions": null` e um binário anterior a esta feature
    # rejeitaria TODOS os perfis dela num downgrade, não só os que usam o campo.
    "button_actions",
)


# ---------------------------------------------------------------------------
# PERFIL-SEM-RASTRO-01 (05/08/2026) — histórico versionado de cada gravação
# ---------------------------------------------------------------------------
# O PORQUÊ, medido: os perfis dela foram corrompidos por dentro da janela —
# perderam o `match` (virou ``{"type": "any"}``) e as prioridades escalaram até
# 191. Quando ela perguntou "como sabemos se algum teste ou algo a mais
# corrompeu algo?", NÃO havia resposta possível: `save_profile` fazia
# `os.replace` por cima do arquivo, e a versão anterior deixava de existir no
# mesmo instante. Sem cópia anterior não há nem conserto (voltar ao que estava)
# nem perícia (comparar o antes com o depois).
#
# O custo é desprezível — perfil tem ~1 KB, o arquivamento é uma leitura e uma
# escrita dentro do MESMO FileLock que a gravação já segurava.
HISTORICO_DIR_NAME = ".historico"

#: Quantas versões de CADA perfil ficam guardadas. Dez cobre uma sessão inteira
#: de ajuste fino na janela (que grava a cada confirmação) sem virar depósito.
HISTORICO_MAX_VERSOES = 10


def historico_dir(slug: str, *, ensure: bool = False) -> Path:
    """Diretório do histórico de UM perfil: ``profiles/.historico/<slug>/``.

    Fica DENTRO do diretório de perfis de propósito: quem faz backup do
    ``~/.config`` leva o histórico junto. O nome começa com ponto e é um
    subdiretório, então nenhuma varredura de perfis o enxerga — todas usam
    ``glob("*.json")`` (não recursivo) ou ``find -maxdepth 1``.
    """
    _reject_traversal(slug)
    destino = profiles_dir(ensure=ensure) / HISTORICO_DIR_NAME / slug
    if ensure:
        destino.mkdir(parents=True, exist_ok=True)
    return destino


def _carimbo_de_versao() -> str:
    """Carimbo ordenável lexicograficamente: ``20260805T031500_123456``."""
    return datetime.now().strftime("%Y%m%dT%H%M%S_%f")


def listar_historico(identifier: str) -> list[Path]:
    """Versões guardadas de um perfil, da MAIS ANTIGA para a mais recente.

    Aceita slug direto ou display name acentuado (mesma tolerância do
    `load_profile`). Diretório ausente = lista vazia, nunca exceção.
    """
    slug = _slug_para_historico(identifier)
    destino = historico_dir(slug)
    if not destino.is_dir():
        return []
    return sorted(destino.glob("*.json"))


def _slug_para_historico(identifier: str) -> str:
    """Resolve o identifier para o slug que nomeia o arquivo do perfil.

    Prefere o slug LITERAL quando já existe histórico com esse nome (o
    histórico é indexado pelo arquivo, não pelo display name); só então cai em
    `slugify`, que é o que traduz "Ação Rápida" para ``acao_rapida``.
    """
    _reject_traversal(identifier)
    raiz = profiles_dir() / HISTORICO_DIR_NAME
    if (raiz / identifier).is_dir():
        return identifier
    try:
        return slugify(identifier)
    except ValueError:
        return identifier


def _podar_historico(destino: Path, manter: int) -> list[Path]:
    """Apaga as versões mais antigas além de `manter`. Devolve as apagadas."""
    versoes = sorted(destino.glob("*.json"))
    apagadas: list[Path] = []
    for velha in versoes[: max(0, len(versoes) - manter)]:
        with contextlib.suppress(OSError):
            velha.unlink()
            apagadas.append(velha)
    return apagadas


def _arquivar_versao(slug: str, bruto: bytes) -> Path | None:
    """Guarda os BYTES da versão atual do perfil no histórico.

    Best-effort por contrato, e a razão é a hierarquia de danos: uma falha ao
    arquivar (disco cheio, permissão) não pode impedir a usuária de SALVAR o
    perfil dela. Loga warning e devolve None — o `profile_salvo` do journal
    registra `backup=None`, então a ausência fica visível em vez de silenciosa.
    """
    try:
        destino = historico_dir(slug, ensure=True)
        alvo = destino / f"{_carimbo_de_versao()}.json"
        # Dois saves no MESMO microssegundo são inverossímeis, mas o desempate
        # é barato e evita perder uma versão por colisão de nome.
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
    """(discriminador do `match`, `priority`) do que está NO DISCO agora.

    Devolve ``(None, None)`` quando não havia arquivo, e
    ``("ilegivel", None)`` quando havia mas não decodifica — um perfil
    corrompido é justamente o caso em que saber o "antes" mais importa.
    """
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
    """Quem é o processo que está gravando — ``hefesto-gui``, ``pytest``...

    PERFIL-SEM-RASTRO-01: a pergunta dela era "algum TESTE corrompeu algo?".
    Sem esta linha o journal registraria a mudança sem dizer quem a fez, e a
    resposta continuaria sendo um encolher de ombros.
    """
    try:
        nome = Path(sys.argv[0]).name
    except (IndexError, ValueError):  # pragma: no cover — argv sempre tem [0]
        nome = ""
    return nome or "desconhecida"


def _payload_do_perfil(profile: Profile) -> dict[str, object]:
    """O DICIONÁRIO que vai para o disco — as regras de omissão num lugar só.

    Extraído de `save_profile` quando a semeadura por jogo passou a gravar
    perfil sem passar por ele (UM-PERFIL-POR-JOGO-01). Duplicar as regras de
    omissão daria dois formatos de perfil no mesmo diretório, e o requisito
    que elas atendem é de COMPATIBILIDADE — ver a docstring de `save_profile`.
    """
    payload: dict[str, object] = profile.model_dump(mode="json")
    # SOM-02/E4: seção ausente é seção AUSENTE no arquivo (ver `save_profile`).
    # `is None` e não falsy: `key_bindings: {}` é a ordem "teclado silencioso"
    # e tem de sobreviver ao save.
    for secao in _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE:
        if payload.get(secao) is None:
            payload.pop(secao, None)
    if not payload.get("controllers"):
        payload.pop("controllers", None)
    else:
        payload["controllers"] = {
            uniq: cfg.model_dump(mode="json", exclude_unset=True)
            for uniq, cfg in (profile.controllers or {}).items()
        }
    return payload


def save_profile(profile: Profile, *, origem: str | None = None) -> Path:
    """Grava perfil em `<slugify(profile.name)>.json` de forma atômica.

    PERFIL-02 (sprint perfis-por-controle): o campo aditivo ``controllers``
    é OMITIDO do JSON quando None/vazio — requisito de COMPATIBILIDADE, não
    estética. `model_dump` sem exclude emitiria ``"controllers": null`` em
    TODO save, e binário antigo (``extra="forbid"``) rejeitaria TODO perfil
    no downgrade; com a omissão, só perfis que USAM o mapa ficam
    incompatíveis, e perfis antigos seguem round-trip load→save sem ganhar
    a chave.

    SOM-02/E4 (29/07): a seção ``speaker`` entra na MESMA omissão, e pelo
    mesmo motivo medido. O ``model_dump`` emite todo campo declarado — um
    perfil recém-criado já sai com ``"mouse": null, "mic": null,
    "mode": null`` —, então acrescentar a seção faria TODO save gravar
    ``"speaker": null`` e um binário anterior à sprint (``extra="forbid"``)
    rejeitaria TODOS os perfis num downgrade, inclusive os que nunca ouviram
    falar de alto-falante. Com a omissão, ``load → save`` de um perfil sem a
    seção não acrescenta a chave ao arquivo.

    E as OUTRAS seções opcionais entram junto — ``mouse``, ``mic``, ``mode`` e
    ``key_bindings``. Elas tinham exatamente o mesmo defeito, só que já em
    produção há semanas. Curar só a seção do dia e deixar as vizinhas doentes
    seria escolher a estética em vez do requisito (o downgrade voltar a
    funcionar). MEDIDO antes de entrar, com a suíte de unidade inteira: a
    omissão ampliada não produz UM vermelho novo. O load é semanticamente
    idêntico, porque chave ausente e chave ``null`` produzem o mesmo ``None``
    no esquema; ``key_bindings`` ausente segue valendo "herda os defaults", e
    o que muda comportamento lá é ``{}`` (teclado silencioso) — que não é
    ``None`` e continua sendo gravado.

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
    payload = _payload_do_perfil(profile)
    with FileLock(str(_lock_path(path))):
        # PERFIL-SEM-RASTRO-01: a versão que está no disco AGORA é lida antes de
        # ser pisada — os mesmos bytes servem para o backup e para o `antes` do
        # journal, então a perícia não custa uma segunda leitura.
        anterior = _bytes_se_existe(path)
        backup = _arquivar_versao(path.stem, anterior) if anterior is not None else None
        _atomic_write_json(path, payload)
    _registrar_gravacao(profile, path, anterior, backup, origem)
    return path


def _registrar_gravacao(
    profile: Profile,
    path: Path,
    anterior: bytes | None,
    backup: Path | None,
    origem: str | None,
) -> None:
    """Emite o `profile_salvo` — a linha de journal que NÃO existia.

    PERFIL-SEM-RASTRO-01: foi esta lacuna que impediu decidir se o ``191`` na
    prioridade veio da catraca que sobe sozinha ou do slider da janela. Gravar
    perfil era, até aqui, o único caminho do projeto que mudava o disco da
    usuária sem deixar UMA linha dizendo o quê. As duas transições que mais
    machucaram entram nomeadas: o discriminador do `match`
    (``criteria`` -> ``any`` é a perda da regra) e a prioridade.

    Nunca levanta: registrar não pode derrubar uma gravação que já aconteceu.
    """
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

    lock_file = _lock_path(candidate)
    with FileLock(str(lock_file)):
        # PERFIL-SEM-RASTRO-01: apagar é a gravação mais destrutiva de todas —
        # guarda a última versão antes de sumir com ela, e registra quem apagou.
        conteudo = _bytes_se_existe(candidate)
        backup = (
            _arquivar_versao(candidate.stem, conteudo) if conteudo is not None else None
        )
        candidate.unlink()
    # Z4/T15 (24/08/2026): o `FileLock` LIBERA o lock ao sair do `with`, mas
    # não apaga o `.lock` que ele mesmo criou — a medição de 24/08 achou 37
    # arquivos `.lock` para 34 `.json` no diretório dela, três órfãos sem
    # `.json` correspondente. `unlink` FORA do `with` — apagar o arquivo do
    # lock enquanto ainda o segura é o convite para outro processo, no
    # mesmíssimo instante, achar que destravou algo que nunca existiu.
    # `missing_ok`: o lock pode já não existir (nunca foi tocado nesta rodada,
    # ou outro processo o limpou primeiro) — a ausência não é erro aqui.
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
    texto = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_bytes(target, texto.encode("utf-8"))


def _atomic_write_bytes(target: Path, bruto: bytes) -> None:
    """Escrita atômica de bytes crus (tmpfile + fsync + rename).

    PERFIL-SEM-RASTRO-01: a restauração precisa devolver os bytes EXATOS que
    foram guardados — reserializar mudaria a formatação e uma comparação byte a
    byte deixaria de provar que a versão voltou inteira. O JSON passou a
    escrever por aqui também: é o mesmo tmpfile+fsync+rename de antes, num
    lugar só.
    """
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
    "HISTORICO_DIR_NAME",
    "HISTORICO_MAX_VERSOES",
    "INTERVALO_MINIMO_DA_VARREDURA_S",
    "MARCA_DE_SEMEADURA_DE_JOGOS",
    "PRIORIDADE_DO_PERFIL_DE_JOGO",
    "SEED_MARKER_NAME",
    "SEED_SKIP_ENV_VAR",
    "PerfilSemeado",
    "ResultadoDaSemeadura",
    "classes_do_perfil_do_jogo",
    "delete_profile",
    "historico_dir",
    "listar_historico",
    "load_all_profiles",
    "load_profile",
    "migrate_coop_local_match",
    "migrate_default_profile_name",
    "perfis_de_jogo_semeados",
    "perfis_que_casam_com_o_cliente_steam",
    "restaurar_do_historico",
    "save_profile",
    "seed_default_presets",
    "semear_perfis_dos_jogos",
]
