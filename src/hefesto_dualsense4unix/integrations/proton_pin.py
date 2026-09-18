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

try:  # importado como módulo do pacote (GUI/daemon/testes)
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

#: O que SÓ a Steam cria na raiz dela (18/09/2026, INSTALL-UNIVERSAL). Uma pasta
#: chamada `~/.steam/steam` sem nenhum destes não é uma Steam — e o caso que
#: isto cura é exatamente esse: o `--ensure` do install, numa máquina em que a
#: Steam ainda não existia, fazia `mkdir(parents=True)` e CRIAVA a raiz como
#: diretório real, só com o nosso `compatibilitytools.d` dentro. O lançador
#: Debian da Steam lê diretório real em `~/.steam/steam` como o layout
#: histórico e adota `~/.steam` como casa — e o produto inteiro (pino, Steam
#: Input, wrapper, vigia) passa a mirar uma raiz que a Steam não usa.
_MARCAS_DE_STEAM = ("steam.sh", "config/config.vdf", "userdata", "steamapps")

#: Os códigos de saída do `--ensure`, e cada um tem UM significado. Até
#: 18/09/2026 o `1` cobria o checksum E tudo o que saísse como traceback (python
#: sem `filter=` no tarfile, disco cheio na extração de ~1,5 GB) — e o install
#: anunciava *"checksum do Proton NÃO bateu"* sobre um disco cheio.
RC_CHECKSUM = 1
RC_SEM_REDE_E_SEM_CACHE = 2
RC_ADIADO = 4
RC_EXTRACAO_FALHOU = 5
RC_CONF_ILEGIVEL = 6

#: A EXCEÇÃO NOMEADA ao pino — gêmea do `jogos_sem_wrapper.txt` (mesmo formato:
#: um appid por linha, `#` comenta). O `--lock --todos` e o `--manter` do vigia
#: não tocam o que está aqui. Sem este arquivo, um mantenedor que trava a cada
#: saída da Steam brigaria para sempre com qualquer Proton que ela escolhesse
#: depois para um jogo que não roda no GE, e a única saída seria desinstalar.
FORA_DO_PINO_RELPATH = "hefesto-dualsense4unix/jogos_fora_do_pino.txt"

_FORA_DO_PINO_HEADER = """\
# hefesto-dualsense4unix — jogos que ficam FORA do Proton pinado
#
# AppIDs listados aqui não são travados no Proton validado: nem pelo install,
# nem pelo vigia da Steam, nem pelo botão da aba Sistema. O Proton que você
# escolher para eles na janela da Steam fica como está.
#
# Sem o Proton pinado, um upgrade de Proton pode trazer de volta o controle
# duplicado dentro do jogo. Uma linha por AppID; '#' comenta.
"""


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


def e_raiz_de_steam(raiz: Path) -> bool:
    """True se `raiz` é uma Steam de verdade, e não só uma pasta com esse nome.

    Uma Steam deixa marcas que ninguém mais deixa (:data:`_MARCAS_DE_STEAM`):
    o `steam.sh` do bootstrap, o `config/config.vdf` do primeiro login, as
    pastas `userdata` e `steamapps`. Uma sobra do nosso `--ensure` não tem
    nenhuma — e é essa distinção que impede o produto de confundir o próprio
    lixo com a Steam dela.
    """
    try:
        if not raiz.is_dir():
            return False
        return any((raiz / marca).exists() for marca in _MARCAS_DE_STEAM)
    except OSError:
        return False


def default_steam_root(home: Path | None = None) -> Path:
    """Raiz da Steam NATIVA (~/.steam/steam, fallback ~/.local/share/Steam).

    Flatpak/Snap ficam DE FORA de propósito: o Proton extraído no host é
    invisível dentro da sandbox — travar jogos lá num tool inexistente
    quebraria o launch (mesma regra do wrapper, DEDUP-04).

    A raiz com cara de Steam (:func:`e_raiz_de_steam`) vence a que só existe:
    com um `~/.steam/steam` vazio de sobra e a Steam de verdade em
    `~/.local/share/Steam`, é a segunda que manda. Sem nenhuma válida, o
    comportamento é o de sempre — a primeira que existe, senão a nativa.
    """
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
    """``"Flatpak"``/``"Snap"`` quando há uma Steam em sandbox, senão ``None``.

    É a pergunta que separa os dois adiamentos do `--ensure`: com a Steam numa
    caixa, o Proton extraído no host nunca vai servir, e baixar 563 MB seria
    desperdício; sem Steam nenhuma, o download adiantado para o cache é o que
    deixa o vigia instalar o pino sozinho, sem rede, quando ela aparecer.
    """
    base = home or Path.home()
    if (base / ".var/app/com.valvesoftware.Steam/.steam/steam").is_dir():
        return "Flatpak"
    if (base / "snap/steam/common/.steam/steam").is_dir():
        return "Snap"
    return None


def raiz_envenenada(home: Path | None = None) -> Path | None:
    """`~/.steam/steam` quando ele é SOBRA NOSSA, e não uma Steam — ou ``None``.

    A forma medida (18/09/2026, INSTALL-UNIVERSAL): o `--ensure` de antes desta
    cura, rodado sem Steam na máquina, deixava `~/.steam/steam` como diretório
    REAL, sem nenhuma marca de Steam, com só o `compatibilitytools.d` dentro —
    e nele só o que nós extraímos (o manifesto diz `installed_by`) ou o resto
    de uma extração nossa interrompida. O lançador Debian lê isso como o layout
    histórico e passa a usar `~/.steam` como casa da Steam.

    A régua é estreita DE PROPÓSITO: qualquer coisa que não seja nossa lá
    dentro — um Proton de outro instalador, um arquivo solto — devolve
    ``None``, porque quem recebe a resposta é mandado tirar a pasta do caminho.
    """
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
                continue  # extração nossa interrompida
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
    """``(raiz, motivo)`` — só um dos dois não é ``None`` (T-09, ONDA0-Z7).

    Espelha o formato de recusa da Z1 (§9.1 da sprint O AMBIENTE PRESUMIDO
    01): :func:`steam_root_ou_recusa` NUNCA silencia o motivo quando não há
    raiz. Devolver ``(None, None)`` seria repetir o defeito **F1**
    ("aplicado" é palavra sem prova) na sua forma negativa — um botão que não
    pode funcionar e não diz por quê.
    """

    raiz: Path | None
    motivo: str | None


def steam_root_ou_recusa(home: Path | None = None) -> RaizDaSteamOuRecusa:
    """:func:`default_steam_root`, mas dizendo POR QUE quando não há onde travar.

    T-09 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026). :func:`default_steam_root`
    CONTINUA excluindo Flatpak/Snap — decisão medida, ver o docstring dela: o
    Proton que o Hefesto extrai no host é invisível dentro da sandbox, e
    travar lá quebraria o launch (mesma regra do wrapper, DEDUP-04). O que
    faltava era a TELA saber dizer por quê: medido em 23/08/2026 (§3.5 da
    sprint), "Travar Proton validado" cala nos três layouts fora do nativo.

    Devolve ``(raiz, None)`` quando há uma Steam NATIVA de verdade (o
    diretório existe); ``(None, motivo)`` caso contrário — e o motivo
    diferencia "achei uma Steam, mas ela está numa caixa" de "não achei
    Steam nenhuma", porque as duas pedem ações diferentes de quem lê.

    A FRASE é vocabulário de tela — a palavra final é da **Z1**, que já tem
    o formato de recusa que esta função replica (ver §8 do protocolo de
    execução desta casa: decisão de produto não se escolhe em silêncio).
    Quem liga esta função ao botão "Travar Proton validado" é a **Onda 5 ·
    Emulação** (§10 da sprint) — Z7-C só entrega a primitiva.
    """
    base = home or Path.home()
    raiz = default_steam_root(base)
    # "EXISTE" NÃO BASTA — 18/09/2026. Este teste era `raiz.is_dir()`, e a
    # sobra do nosso próprio `--ensure` (um `~/.steam/steam` só com o
    # `compatibilitytools.d`) passava por Steam nativa.
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
    """Os appids que ela NOMEOU como fora do pino. Nunca levanta.

    Arquivo ausente ou ilegível = lista vazia, pela mesma razão do
    `ler_jogos_sem_wrapper`: o pior caso de uma leitura falha é travar um jogo
    no pino, e isso se desfaz com `--unlock`.
    """
    destino = path if path is not None else fora_do_pino_path()
    try:
        return [
            a for a in parse_steam_input_allowlist(destino.read_text(encoding="utf-8"))
            if a.isdigit()
        ]
    except (OSError, ValueError):
        return []

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

    18/09/2026: ``em_cache`` (tarball conferido no cache, nada extraído — é o
    que sobra quando ainda não há Steam nativa onde extrair), ``adiado`` (há
    tarball conferido, mas a raiz da Steam não existe) e ``extracao_falhou``
    (o tarball bateu e a extração quebrou: disco cheio, permissão, tar
    corrompido depois do download). Nenhum dos três é checksum.
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


def _conferir_nomes_do_tar(tar: tarfile.TarFile) -> None:
    """Recusa membro com nome absoluto, com `..` ou que seja nó de dispositivo.

    É a parte do filtro "tar" que importa aqui, para o python que não tem
    filtro nenhum. Levanta `tarfile.TarError`, que o ensure traduz em
    ``extracao_falhou`` — nunca em checksum.
    """
    for membro in tar.getmembers():
        nome = membro.name
        if nome.startswith("/") or ".." in Path(nome).parts:
            raise tarfile.TarError(f"membro fora do destino no tarball: {nome!r}")
        if membro.isdev():
            raise tarfile.TarError(f"nó de dispositivo no tarball: {nome!r}")


def _extract_verified_tarball(
    tarball: Path, name: str, compat_dir: Path
) -> None:
    """Extrai o tarball JÁ VERIFICADO em compat_dir/<name>/ (tmp + rename).

    `filter="data"` do tarfile bloqueia path traversal/links absolutos. A
    extração acontece num tmp irmão e só vira o nome final depois de validada
    (tem `proton` executável) e com o manifesto gravado — crash no meio nunca
    deixa um dir meio-extraído com o nome bom.

    A RAIZ DA STEAM NÃO NASCE AQUI — 18/09/2026. Isto era
    `compat_dir.mkdir(parents=True)`, e numa máquina sem Steam o `parents=True`
    criava `~/.steam/steam` como diretório real: a sobra que o lançador Debian
    adota como casa (ver :func:`raiz_envenenada`). Agora só o
    `compatibilitytools.d` pode nascer, e só dentro de uma raiz que já existe.
    """
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
        # O data_filter do Python 3.10 erra o cálculo de symlink relativo e
        # recusa links internos legítimos do GE-Proton (start.exe em
        # files/share/default_pfx/... aponta 5 níveis acima, e cai dentro de
        # files/lib/wine/). O 3.11+ acerta. Como o tarball já passou pelo SHA256
        # fixado antes de chegar aqui, no 3.10 usamos "tar", que continua
        # barrando caminho absoluto e path traversal do próprio nome.
        _filtro: Literal["data", "tar"] = (
            "data" if sys.version_info >= (3, 11) else "tar"
        )
        with tarfile.open(tarball, mode="r:gz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=tmp_root, filter=_filtro)
            else:
                # PYTHON SEM `filter=` (anterior ao 3.10.12/3.11.4, que ainda
                # existe em distro de suporte longo): o `extractall(filter=)`
                # levantava TypeError, que ninguém capturava, e o install lia o
                # rc=1 como *"checksum NÃO bateu"*. O tarball já passou pelo
                # SHA256 fixado; a barreira que o "tar" daria — nome absoluto
                # ou com `..` — é conferida à mão antes de extrair.
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
    6. Tarball conferido e a raiz da Steam (``compat_dir.parent``) ausente →
       ``adiado``, com o tarball no cache. Extração quebrada →
       ``extracao_falhou``.
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
        # O tarball BATEU com o SHA256: o que falhou foi a escrita (~1,5 GB
        # extraídos) ou o próprio tar. Nada disso é checksum, e dizer que era
        # mandava a pessoa apagar um cache bom.
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
    """O tarball do pino no cache, CONFERIDO — baixando se preciso. Nunca extrai.

    Devolve ``(tarball, resultado)``. Com tarball, ``resultado.state`` é
    ``em_cache`` (já estava) ou ``baixado``; sem, é ``checksum_mismatch`` ou
    ``unavailable``. É a metade do ensure que não precisa da Steam, e é por
    isso que ela mora sozinha: sem Steam nativa, o install ainda adianta o
    download, e o vigia extrai depois, offline.
    """
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

    # Download SEMPRE para um tmp; só vira cache com o sha256 conferido — um
    # cache envenenado nunca nasce daqui.
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
    """Baixa e confere o tarball SÓ para o cache — não extrai, não toca na Steam.

    O caminho do `--ensure` quando ainda não existe Steam nativa (18/09/2026).
    Antes, o mesmo `--ensure` extraía assim mesmo e criava `~/.steam/steam`
    como diretório real (ver :func:`raiz_envenenada`). Agora o download é
    adiantado — é ele que leva minutos, e com ele no cache o `--manter` do
    vigia instala o pino sem rede no dia em que a Steam aparecer.

    Estados: ``em_cache`` (conferido; já estava ou acabou de chegar),
    ``checksum_mismatch`` e ``unavailable``.
    """
    tarball, obtido = _tarball_conferido_no_cache(
        conf, cache_dir=cache_dir, downloader=downloader, verifier=verifier
    )
    if tarball is None:
        return obtido
    return EnsureResult("em_cache", str(tarball))


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


def e_da_familia_proton(tool_name: str) -> bool:
    """True se a ferramenta é um Proton (da Valve, GE ou outro) — o que o pino troca.

    A CLASSE DO "TODO JOGO" (18/09/2026, decisão registrada na
    INSTALL-UNIVERSAL). O pino existe por causa do winebus, e só jogo que
    atravessa o Wine atravessa o winebus. Uma entrada que aponta para
    `steamlinuxruntime_*`, `luxtorpeda` ou outra ferramenta que não é Proton é
    a escolha de rodar NATIVO, e trocá-la pelo GE faria o jogo baixar a versão
    Windows e mudar os saves de lugar, em silêncio. O critério é o nome, sem
    diferenciar maiúsculas: `proton_11`, `proton_experimental`,
    `GE-Proton11-7-x86_64` e `Proton-tkg` são da família; o resto não é.
    """
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
    """Trava o global (`"0"`) + cada appid em `tool_name`, **sem** atropelar escolha.

    Retorna ``(texto_novo, mudanças)`` — mudanças é o registro que o lock
    persiste para o unlock reverter SÓ o nosso:
    ``{appid: {"action": "added"|"replaced"|"preservado", "previous_name": "…"}}``.
    Idempotente: entrada já apontando para `tool_name` não gera mudança; o
    resto do arquivo passa intacto byte a byte (edição por linha).

    ESCOLHA DELA NÃO SE ATROPELA (19/08/2026). Até aqui, uma entrada que já
    apontava para OUTRA ferramenta era **substituída** sem perguntar. O preço foi
    medido na máquina dela: em 14/08/2026 03:04 o lock trocou o Proton de TRÊS
    jogos que tinham escolha deliberada — o DON'T SCREAM (appid 2497900) saiu de
    ``proton_11`` para ``GE-Proton10-34``, e nesse Proton o motor Unreal registra
    ``No Audio Capture implementations found`` e ZERO ``WasapiCapture``: o
    microfone do jogo, que é a mecânica inteira dele, morreu. Ela zerou o jogo no
    ``proton_11``; o produto lhe tirou o caminho e não avisou. Os outros 16 jogos
    da mesma leva eram ``added`` (não tinham nada) e não sofreram.

    Agora o padrão é **preservar**: entrada DE JOGO com nome diferente vira
    ``action="preservado"``, o arquivo não muda naquela linha, e quem chamou
    recebe o registro para poder CONTAR o que respeitou. O unlock ignora
    ``preservado`` de propósito — não há o que reverter onde nada foi escrito.

    A entrada global ``"0"`` NÃO entra nessa guarda: travar o padrão do Steam
    Play é a função declarada deste recurso, e ela já tem caminho de volta (o
    ``previous_name`` do ``"0"`` sobrevive a re-locks e o uninstall o restaura).
    O dano de 14/08 foi por jogo, não no global.

    ``atropelar_escolha_dela=True`` restaura o comportamento antigo. Ele existia
    para o caso em que ELA pedisse, explicitamente, "troque tudo para o Proton
    validado" — e aí a palavra seria dela.

    **ELA PEDIU, EM 17/09/2026**, vendo o DON'T SCREAM ficar no ``proton_11``
    enquanto os outros 24 subiam para o ``GE-Proton11-7-x86_64``: *"mas não era
    pra todos ficarem sobre o novo proton?"*, e em seguida *"ele e todo o resto
    de agora em diante."*

    O CLI expõe isso como ``--todos``, e o ``install.sh`` passa a usá-lo. A
    guarda continua no código, e continua sendo o padrão da função: ela protege
    quem chamar sem pedir. O que mudou é que o PRODUTO agora pede, porque essa
    é a ordem dela — e uma exceção, daqui em diante, tem de ser NOMEADA e
    DATADA por ela, nunca inferida da forma do arquivo.

    **O QUE ELA PRECISA SABER, e está medido aqui embaixo:** o dano de 14/08
    foi num appid que ela usa (o DON'T SCREAM, cujo jogo inteiro é o microfone)
    e a queixa foi *"não anda. nem o microfone."*. A sprint que o registrou
    guarda uma ressalva do próprio autor — *"que a troca de Proton tenha sido o
    que matou o microfone NÃO está provado pelos logs"* —, e eram TRÊS portões
    em série, dos quais dois já foram curados. Mais: o microfone dela hoje sai
    pelo nó ``hefesto_mic_*`` do PipeWire (report ``0x32``, medido em 03/09 e
    06/09), caminho que não passa pelo Proton. O risco é menor do que era e
    continua existindo; a volta é ``--unlock``.

    ``pinos_nossos`` — O PINO VELHO NÃO É ESCOLHA DELA (16/09/2026), e esta é a
    diferença entre preservar e ficar parado. MEDIDO na máquina dela no dia em
    que o pino subiu de ``GE-Proton10-34`` para ``GE-Proton11-6-x86_64``: o lock
    respondeu *"locked"*, e **os 25 jogos continuaram no Proton velho**, com
    ``action="preservado"`` em cada um. Estavam ali porque o PRÓPRIO produto os
    escreveu — os backups do `config.vdf` mostram as entradas em
    ``GE-Proton10-34`` crescendo install a install desde 19/07 —, e a guarda de
    19/08 as leu como decisão dela.

    O efeito, dito por inteiro: **subir o pino nunca alcançava jogo nenhum**. Só
    o global mudava, e a versão nova ficava instalada sem ser usada por
    ninguém — que foi exatamente o que o pedido do dia (o som do alto-falante
    dentro do jogo, que só existe do 11-4 em diante) precisava que NÃO
    acontecesse.

    A cura é fina de propósito: entrada cujo valor está em ``pinos_nossos`` é
    NOSSA e migra (``action="migrado"``); entrada com qualquer outro valor
    continua ``preservado``, e o dano de 14/08 — o ``DON'T SCREAM`` em
    ``proton_11``, cujo microfone morre no outro Proton — segue impossível. O
    histórico de pinos vive no registro do lock (``pinos_do_hefesto``) e cresce
    sozinho a cada subida; ``migrar_de`` no CLI é a semente para a primeira,
    feita quando o registro ainda não conhecia o pino anterior.

    **O "TODO JOGO" TEM CLASSE — 18/09/2026, INSTALL-UNIVERSAL.** Numa
    biblioteca que não é a dela, `--todos` passava todo título com versão
    Linux nativa para a versão Windows pelo Proton, em silêncio (novo download,
    saves no prefixo). Medido na máquina dela: o 316790 declara
    `windows,macos,linux` no `appinfo.vdf` e estava forçado no GE desde 19/07.
    Três regras, e nenhuma remove entrada:

    - entrada EXISTENTE só é trocada com ``atropelar_escolha_dela`` se a
      ferramenta atual é da família Proton (:func:`e_da_familia_proton`) — ou
      se é um pino nosso, com ou sem a flag. Ferramenta que não é Proton vira
      ``preservado``;
    - entrada NOVA não nasce para quem está em ``sem_entrada_nova`` (o jogo
      nativo do Linux: quem decide é :func:`jogos_sem_entrada_nova`). O global
      ``"0"`` já não se aplica a título com versão Linux, então ele fica
      nativo;
    - appid em ``excluir`` (a exceção NOMEADA, ``jogos_fora_do_pino.txt``) não
      é tocado de jeito nenhum — nem entra no registro.

    A entrada que já existe NUNCA é apagada: o 316790 dela fica no GE, porque
    tirá-lo de lá mudaria os saves de lugar outra vez.

    `config.vdf` sem bloco Software/Valve/Steam = ValueError (arquivo que não
    é um config.vdf de verdade — melhor explodir que "criar" a árvore).
    """
    lines = config_vdf_text.splitlines(keepends=True)
    layout = _parse_ctm_layout(lines)
    if layout.steam_open_idx is None or layout.steam_close_idx is None:
        raise ValueError("config.vdf sem bloco Software/Valve/Steam")

    excluidos = {str(a) for a in excluir}
    nativos = {str(a) for a in sem_entrada_nova}
    targets = ["0", *[a for a in appids if a != "0" and a not in excluidos]]
    if atropelar_escolha_dela:
        # "TODO O RESTO" INCLUI A ENTRADA ÓRFÃ — e ela é o caso que faz a ordem
        # dela valer "de agora em diante". Medido em 17/09/2026, logo depois do
        # primeiro `--lock --todos`: três entradas ficaram em `proton_11` e no
        # `GE-Proton10-34` porque os jogos NÃO ESTÃO INSTALADOS, e `appids` nasce
        # de `list_installed_appids`. A escolha velha continua no mapa; quando
        # ela reinstalar, é ELA que a Steam lê, e o jogo nasce fora do pino sem
        # que ninguém veja.
        #
        # Sem `--todos` isto não muda nada: a guarda `preservado` é o padrão da
        # função, e quem não pede continua protegido.
        #
        # A ÓRFÃ ENTRA PELA FERRAMENTA QUE ELA JÁ TEM (18/09/2026). Um jogo
        # desinstalado pode nem estar no `appinfo.vdf`, mas a entrada dele diz
        # a classe: apontando para um Proton, ele roda pelo Wine e volta no
        # pino; apontando para `steamlinuxruntime`, a escolha foi rodar nativo,
        # e reinstalá-lo forçado no GE seria o defeito da classe errada.
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
                    # Jogo nativo do Linux sem entrada: fica sem — o global
                    # não o alcança, e é assim que ele segue nativo.
                    continue
                new_entries.append(_entry_block(appid, tool_name, entry_indent, eol))
                changes[appid] = {"action": "added", "previous_name": ""}
                continue
            if entry.name_idx is None:
                # Entrada sem "name" (fora do padrão) — não arriscar.
                continue
            if entry.name_value == tool_name:
                continue
            nossa = entry.name_value in pinos_nossos
            troca_pedida = atropelar_escolha_dela and e_da_familia_proton(
                entry.name_value
            )
            if appid != "0" and not troca_pedida and not nossa:
                # A entrada existe e aponta para OUTRA ferramenta: sem
                # `--todos`, é escolha dela POR JOGO; com `--todos`, só chega
                # aqui a ferramenta que não é Proton (a escolha de rodar
                # nativo). Registra e NÃO escreve.
                #
                # A entrada global `"0"` fica de fora desta guarda de propósito:
                # travar o padrão do Steam Play é a função declarada do recurso,
                # e ela tem caminho de volta — o `previous_name` do `"0"` sobrevive
                # a re-locks e o uninstall o restaura. O dano medido em 14/08 foi
                # POR JOGO (3 appids com escolha própria), não no global.
                changes[appid] = {
                    "action": "preservado",
                    "previous_name": entry.name_value,
                }
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
                # `migrado` é `replaced` com a procedência dita: o valor que
                # saiu era NOSSO, de um pino anterior. Quem conta separa os
                # baldes, e o unlock trata os dois igual — os dois voltam ao
                # `previous_name`, que é o que a usuária tinha antes de nós.
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

    # Sem CompatToolMapping: cria o bloco inteiro antes do `}` do Steam.
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
    migrar_de: Sequence[str] = (),
    todos: bool = False,
    excluir: Collection[str] = (),
    sem_entrada_de: Callable[[Sequence[str]], Collection[str]] | None = None,
) -> dict[str, object]:
    """Trava global + appids no pin, com gate de Steam fechada e registro.

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
    if not dry_run:
        refusal = _steam_gate()
        if refusal is not None:
            result["status"] = "recusado"
            result["reason"] = refusal
            return result
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


@contextlib.contextmanager
def _uma_trava_por_vez(state: Path, *, ativa: bool) -> Iterator[None]:
    """Um `flock` exclusivo em volta de ler-mudar-gravar o `config.vdf`.

    POR QUE AGORA (18/09/2026): o lock passou a ter três donos que podem rodar
    juntos — o install, o botão da aba Sistema e o `--manter` do vigia, que
    dispara justamente quando a Steam sai (e o install a fecha). Dois
    processos escrevendo o mesmo `config.vdf.hefesto-tmp` ao mesmo tempo
    podiam trocar o arquivo da Steam por um meio escrito. A trava fica ao lado
    do registro, que é arquivo nosso. Sem `fcntl` (fora do Linux), segue sem.
    """
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
        fcntl.flock(fd, fcntl.LOCK_EX)
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
    # OS PINOS QUE JÁ FORAM NOSSOS: o histórico do registro mais o que o
    # chamador semeia. O `tool_name` de hoje entra por completude — se ele
    # aparecer numa entrada, ela já está certa e nem chega ao ramo da migração.
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
        # Registro ANTES do vdf: se a persistência do estado falhar (OSError),
        # o config.vdf continua INTACTO (não pinado) e o lock volta com "erro"
        # — falha segura. A ordem inversa deixava o Proton pinado no vdf sem
        # registro, e como re-lock é idempotente (noop, nunca regrava estado)
        # o unlock/uninstall NUNCA mais conseguiria reverter. Se, ao contrário,
        # o estado for gravado mas a escrita do vdf falhar, o vdf fica original
        # e o unlock apenas não acha o que reverter (reverted=0) e limpa o
        # estado — a direção segura da invariante.
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
    """Os Protons que ESTE produto já pinou, na ordem em que apareceram.

    É a memória que faz a subida de pino alcançar os jogos (ver
    `build_compat_tool_mapping`): o que está aqui é nosso, não é escolha dela.
    Registro ilegível ou antigo (sem a chave) devolve vazio — e aí o lock se
    comporta como antes, preservando tudo. Falha para o lado seguro.
    """
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    pinos = data.get("pinos_do_hefesto")
    conhecidos = [p for p in pinos if isinstance(p, str)] if isinstance(pinos, list) else []
    atual = data.get("tool_name")
    if isinstance(atual, str) and atual and atual not in conhecidos:
        # Registro anterior à chave: o `tool_name` gravado por ele É um pino
        # nosso, e ignorá-lo repetiria o defeito de 16/09 na próxima subida.
        conhecidos.append(atual)
    return tuple(dict.fromkeys(conhecidos))


def _fundir_marcas(
    agora: dict[str, dict[str, str]],
    antes: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Funde as marcas do lock POR CAMPO, porque cada campo tem dono diferente.

    O DEFEITO que isto cura, medido em 16/09/2026: a fusão era por ENTRADA
    (``merged.update(existing)``), e o registro da corrida anterior vencia
    inteiro. Depois de 24 jogos migrarem de verdade para o pino novo, o registro
    ainda dizia ``preservado`` para os 24 — a marca da corrida que falhara.
    **Um registro que descreve a corrida errada não desfaz coisa nenhuma.**

    Quem é dono de quê:

    ``action``
        a corrida de AGORA. É o que acabou de acontecer com o appid.
    ``previous_name``
        a corrida MAIS ANTIGA que o conheceu. É o valor pré-hefesto — o que
        estava lá antes de este produto encostar — e é ele que desfaz TUDO.
    ``veio_de``
        a corrida de AGORA, e só quando ela escreveu. É de onde o appid saiu
        NESTA subida, e é ele que desfaz UMA subida. Ausente quer dizer "esta
        corrida não mexeu"; vazio quer dizer "a entrada não existia".
    """
    #: As ações que ESCREVERAM no `config.vdf` — as únicas com o que desfazer.
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
        # Lê-se o registro ANTERIOR mesmo quando ele é de outro pino: o
        # `previous_name` pré-hefesto pertence ao APPID, não à versão do Proton.
        # Enquanto a leitura exigia `tool_name` igual, toda subida de pino
        # apagava a única pista de como devolver o jogo ao estado de antes.
        if isinstance(data.get("changes"), dict):
            existing = data["changes"]
    except (OSError, ValueError):
        pass
    merged = _fundir_marcas(changes, existing)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_name": tool_name,
        # O histórico NUNCA encolhe: é ele que permite a próxima subida de pino
        # reconhecer o trabalho desta.
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
) -> dict[str, object]:
    """Conveniência ZERO-ARG do botão "Travar Proton validado" da GUI (PLAT-01).

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
    )
    changes = result.get("changes")
    if isinstance(changes, dict):
        # `preservado` NÃO é travado: é jogo em que ela já tinha escolhido, e o
        # produto respeitou. Contar os dois juntos diria "travei 19" numa leva em
        # que 3 ficaram intactos de propósito — e foi assim que o atropelo de
        # 14/08 passou despercebido. Cada balde conta o que ele é.
        # `migrado` conta à parte pela mesma razão do `preservado`: ele é o
        # jogo que estava num pino NOSSO antigo e passou para o de hoje. Somá-lo
        # ao `locked` esconderia justamente o número que prova que a subida de
        # pino chegou aos jogos — e foi a ausência desse número que deixou o
        # defeito de 16/09 invisível.
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
    # T-04 (SISTEMA-O-VIGIA-VIVO-01, 25/08/2026): `status` e `reason` passam
    # para fora. Antes só sobrevivia `errors = 1 if status == "erro" else 0`, e
    # RECUSA não é erro para essa contagem — então uma recusa chegava à tela
    # como `{locked:0, skipped:0, errors:0}`, indistinguível de "não havia
    # nada a fazer". `format_proton_lock_result` caía no ramo `elif errors ==
    # 0` e comemorava *"os jogos já estão no Proton validado"* logo depois de
    # o gate ter recusado por causa de um jogo aberto. A verdade já estava
    # calculada aqui dentro; a ponte é que a jogava fora.
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
    if not dry_run:
        # O arquivo da trava sai junto com o registro: o uninstall é simétrico.
        with contextlib.suppress(OSError):
            state.with_name(state.name + ".trava").unlink(missing_ok=True)
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


# --------------------------------------------------------------------------
# appinfo.vdf — a plataforma de cada jogo, lida do cache binário da Steam
# --------------------------------------------------------------------------

#: `appcache/appinfo.vdf` v28 e v29 (a v29 guarda as CHAVES numa tabela de
#: strings no fim do arquivo; os valores continuam inline). Formato de
#: SteamDatabase/SteamAppInfo. Versão desconhecida = ilegível, e quem chama cai
#: na reserva do `compatdata`.
_APPINFO_MAGICS = {0x07564428: 28, 0x07564429: 29}

#: Da entrada de cada app, o que vem antes do VDF binário: infoState (4),
#: lastUpdated (4), picsToken (8), SHA1 do texto (20), changeNumber (4) e SHA1
#: do binário (20). O `size` da entrada conta a partir do infoState.
_APPINFO_CABECALHO_DA_ENTRADA = 60


def _ler_cstring(buf: bytes, pos: int) -> tuple[str, int]:
    fim = buf.index(b"\0", pos)
    return buf[pos:fim].decode("utf-8", "replace"), fim + 1


def _ler_vdf_binario(
    buf: bytes, pos: int, chaves: list[str] | None, profundidade: int = 0
) -> tuple[dict[str, object], int]:
    """Um mapa do KeyValues binário da Steam, a partir de `pos`, até o `0x08`.

    ``chaves`` é a tabela de strings da v29 (a chave é um índice u32); na v28 é
    ``None`` e a chave vem inline. Só string e inteiro viram valor — o resto é
    pulado pelo tamanho, porque ninguém aqui precisa dele.
    """
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
            while buf[fim:fim + 2] != b"\0\0":
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
    """O `common/oslist` de cada appid pedido, lido do `appinfo.vdf` binário.

    ``None`` quando o arquivo não existe, não se lê ou é de uma versão que
    este leitor não conhece — e aí quem chama não pode concluir nada dele. App
    que não está no cache simplesmente não aparece no dicionário; app que está
    e não declara `oslist` aparece com ``""``.

    Lê só o cabeçalho de cada entrada e pula as que não interessam pelo
    tamanho: o vigia chama isto, e um `appinfo.vdf` de biblioteca grande tem
    dezenas de MB. Stdlib pura, como o resto do módulo.
    """
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
    """Dos `appids`, os que NÃO ganham entrada nova por jogo no pino.

    A CLASSE DO "TODO JOGO" — 18/09/2026, decisão registrada na
    INSTALL-UNIVERSAL, e ela se afasta da letra de propósito: o pino existe por
    causa do winebus, e jogo nativo não atravessa o Wine. Travá-lo no GE fazia
    a Steam baixar a versão Windows e guardar os saves no prefixo, em silêncio.

    A fonte é o `common/oslist` do `appcache/appinfo.vdf` (:func:`oslist_do_appinfo`):
    declara `linux` → nativo. Quando o appinfo não diz — ilegível, versão nova,
    ou o app fora do cache —, a reserva é a pegada do Proton: existe
    `steamapps/compatdata/<appid>` em alguma biblioteca? Então ele já rodou pelo
    Proton e ganha a entrada. Sem nenhuma das duas provas, fica sem entrada: o
    global `"0"` já cobre todo título SEM versão Linux, inclusive os que forem
    instalados depois.
    """
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
    """Diz, no log do install e do vigia, onde está a sobra que cega a Steam.

    A máquina que já passou pelo `--ensure` de antes desta cura continua com o
    `~/.steam/steam` falso, e reinstalar não o tira: sem esta linha, o install
    diria só "não há Steam nativa" numa máquina que TEM Steam — em `~/.steam`.
    """
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
        # Destino explícito: quem o passou responde pela raiz. A segunda
        # muralha continua valendo — o `_extract_verified_tarball` não cria a
        # pasta de cima.
        compat = args.compat_dir
    else:
        # A PERGUNTA QUE O 11c NÃO FAZIA — 18/09/2026: existe Steam nativa?
        # Sem ela, o ensure antigo baixava 563 MB, extraía, e o
        # `mkdir(parents=True)` deixava `~/.steam/steam` como diretório real —
        # a sobra que estraga a primeira execução da Steam.
        raiz, motivo = steam_root_ou_recusa()
        if raiz is None:
            _avisar_da_raiz_envenenada()
            if steam_em_caixa() is not None:
                print(
                    f"[proton-pin] {conf['name']}: adiado ({motivo}) — nada "
                    "baixado: o Proton extraído no host não serve dentro da caixa"
                )
                return RC_ADIADO
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
                "Steam (ou o próximo ./install.sh) extrai e trava, sem rede."
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
    """O que o vigia da Steam roda: repõe o pino sem rede, e trava todo jogo.

    692cf5343 + 7b27bb58d, a metade que faltava (18/09/2026). A trava `--todos`
    só acontecia no passo 11c do install, e só com a Steam fechada — e NADA
    tentava de novo. Este é o terceiro passo do vigia (o `.path` dispara quando
    a Steam sai, o `.timer` a cada 30 min), na carona do Steam Input e do
    wrapper: o instante em que a Steam acaba de sair é o único em que uma
    edição do `config.vdf` sobrevive.

    Nunca baixa (é `--offline`: o tarball vem do cache que o install adiantou),
    nunca abre nem fecha a Steam (o portão do lock ADIA com ela ou um jogo
    abertos, rc 3), e respeita o `jogos_fora_do_pino.txt`. Sem Steam nativa,
    não há o que manter: sai 0.
    """
    conf = _conf_ou_rc(args)
    if isinstance(conf, int):
        return conf
    raiz, motivo = steam_root_ou_recusa()
    if raiz is None:
        _avisar_da_raiz_envenenada()
        print(f"[proton-pin] manter: nada a fazer — {motivo}")
        return 0
    name = conf["name"]
    compat = raiz / "compatibilitytools.d"
    if not pinned_proton_installed(name, compat):
        cache = args.cache_dir if args.cache_dir else default_cache_dir()
        result = ensure_pinned_proton(
            conf, compat_dir=compat, cache_dir=cache, downloader=None
        )
        print(f"[proton-pin] manter: {name}: {result.state}"
              + (f" ({result.detail})" if result.detail else ""))
        if not pinned_proton_installed(name, compat):
            return _rc_do_ensure(result)
    vdf = args.config_vdf if args.config_vdf else raiz / "config" / "config.vdf"
    if not vdf.is_file():
        # Steam instalada que nunca entrou numa conta: ainda não há onde travar.
        print(f"[proton-pin] manter: {vdf} ainda não existe — nada a travar")
        return 0
    appids = list_installed_appids()
    return _travar_e_contar(
        lock_games_to_pinned_proton(
            tool_name=name,
            appids=appids,
            config_vdf=vdf,
            state_path=args.state,
            todos=True,
            excluir=ler_jogos_fora_do_pino(),
            sem_entrada_de=jogos_sem_entrada_nova,
        ),
        mirados=len(appids),
        prefixo="manter",
    )


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
        # A exceção nomeada vale para todo caminho que trava; `--appids`
        # explícito é a escolha de quem chamou, e ali a classe não se infere.
        excluir=ler_jogos_fora_do_pino(),
        sem_entrada_de=None if explicitos else jogos_sem_entrada_nova,
    )
    return _travar_e_contar(result, mirados=len(appids), prefixo="lock")


def _travar_e_contar(
    result: dict[str, object], *, mirados: int | None, prefixo: str
) -> int:
    """Imprime o que o lock FEZ, balde por balde, e devolve o rc do CLI."""
    # A LINHA DIZ O QUE ACONTECEU, NÃO O QUE FOI MIRADO — 16/09/2026. Ela
    # imprimia `len(appids)`, o tamanho do ALVO: no dia em que o pino subiu,
    # anunciou *"locked — 25 jogos + default global"* enquanto os 25 ficavam
    # onde estavam (`action="preservado"`) e só o global mudava. É a família de
    # defeito que esta casa persegue há meses: o instrumento dizendo o que não
    # fez. Agora cada balde sai com o seu nome, e `0` aparece quando é 0.
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
    if result["status"] == "recusado":
        print(
            "[proton-pin] feche a Steam (e o jogo) e rode de novo — editar o "
            "config.vdf com ela viva perderia a edição."
        )
        return 3
    if result["reason"] == "config_vdf_ausente":
        # Steam instalada que nunca entrou numa conta: não há falha, há espera.
        # O install dizia "trava do Proton falhou" numa máquina recém-montada.
        print(
            "[proton-pin] a Steam ainda não tem config.vdf (nunca entrou numa "
            "conta) — a trava espera; o vigia da Steam trava quando ela sair."
        )
        return RC_ADIADO
    return 0 if result["status"] in ("locked", "noop") else 1


def _cmd_fora_do_pino(args: argparse.Namespace) -> int:
    """Nomeia um jogo como fora do pino, com a data na linha de comentário."""
    appid = str(args.fora_do_pino).strip()
    status = add_appid_to_steam_input_allowlist(
        appid,
        path=fora_do_pino_path(),
        nota=f"{time.strftime('%d/%m/%Y')} — fora do Proton pinado a pedido (--fora-do-pino)",
        cabecalho=_FORA_DO_PINO_HEADER,
    )
    print(f"[proton-pin] fora do pino: {appid}: {status} ({fora_do_pino_path()})")
    if status in ("appid_invalido", "erro"):
        return 1
    print(
        "[proton-pin] a entrada que ele já tem no config.vdf fica como está; "
        "escolha o Proton dele na janela da Steam."
    )
    return 0


def _cmd_de_volta_ao_pino(args: argparse.Namespace) -> int:
    """Desfaz o `--fora-do-pino`: o próximo lock volta a alcançar o jogo."""
    appid = str(args.de_volta_ao_pino).strip()
    status = remove_appid_from_steam_input_allowlist(appid, path=fora_do_pino_path())
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
        # Disco cheio ou permissão fora dos lugares que já dizem o próprio
        # desfecho: o rc 1 é do checksum e da falha genérica do lock, e o
        # install não pode ler um disco cheio como "checksum não bateu".
        print(f"[proton-pin] ERRO de disco: {exc}")
        return RC_EXTRACAO_FALHOU


if __name__ == "__main__":  # pragma: no cover - entrypoint do install/uninstall
    sys.exit(main())
