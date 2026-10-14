"""Paths XDG do Hefesto - DualSense4Unix, via `platformdirs`.

Centraliza config / data / cache / runtime paths. `ensure_dir=True`
cria o diretório se não existir.
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import identidade

# state, perfis e o diretório do socket IPC saem todos daqui. Por isso ele não
_DIRS = PlatformDirs(identidade.atual().slug)


IPC_SOCKET_DEFAULT_NAME = "hefesto-dualsense4unix.sock"
IPC_SOCKET_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME"

FAKE_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_FAKE"
IPC_SOCKET_FAKE_NAME = "hefesto-dualsense4unix-fake.sock"


def fake_mode_enabled() -> bool:
    """True se o backend fake está ligado via `HEFESTO_DUALSENSE4UNIX_FAKE=1`."""
    return os.environ.get(FAKE_ENV_VAR) == "1"


def ipc_socket_name() -> str:
    """Nome-base do socket IPC, com isolamento AUTOMÁTICO no modo fake."""
    explicit = os.environ.get(IPC_SOCKET_ENV_VAR, "").strip()
    if explicit and "/" not in explicit and explicit not in ("..", "."):
        return explicit
    if fake_mode_enabled():
        return IPC_SOCKET_FAKE_NAME
    return IPC_SOCKET_DEFAULT_NAME


def config_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_config_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_data_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_cache_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def runtime_dir(ensure: bool = False) -> Path:
    """XDG_RUNTIME_DIR/hefesto-dualsense4unix; fallback p/ cache/runtime se ausente.

    O ``XDG_RUNTIME_DIR`` declarado é lido aqui, e não pelo ``platformdirs``: do
    4.12 em diante ele troca a pasta que não é 0700 pela ``/run/user/<uid>``, e o
    socket e os pid files iriam para um lugar diferente do que o resto do produto
    lê pela mesma variável.
    """
    declarado = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if os.path.isabs(declarado):
        p = Path(declarado) / _DIRS.appname
    else:
        runtime = _DIRS.user_runtime_dir
        p = Path(runtime) if runtime else cache_dir() / "runtime"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def state_dir(ensure: bool = False) -> Path:
    """XDG_STATE_HOME/hefesto-dualsense4unix (~/.local/state/... por default)."""
    p = Path(_DIRS.user_state_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def launch_env_dir(ensure: bool = False) -> Path:
    """Diretório dos arquivos de env materializados para o wrapper de launch."""
    p = state_dir() / "launch_env"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def profiles_dir(ensure: bool = False) -> Path:
    p = config_dir() / "profiles"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


#: A variável que desvia as pastas de sistema do WirePlumber (lista separada por
#: ``:``). Existe para o teste e para a bancada: o lar de mentira declara um
#: ``/usr/share/wireplumber`` falso em vez de ler o da máquina.
WIREPLUMBER_SISTEMA_ENV_VAR = "HEFESTO_WIREPLUMBER_SISTEMA"
_WIREPLUMBER_SISTEMA = ("/usr/share/wireplumber", "/etc/wireplumber")

FORMA_CONF = "conf"
FORMA_LUA = "lua"


def wireplumber_forma() -> str:
    """A forma que o WirePlumber INSTALADO lê: ``"lua"`` ou ``"conf"``.

    Pergunta pela capacidade, não pela versão: o 0.4 (Ubuntu 24.04, Linux Mint 22,
    Debian 12) lê Lua em ``main.lua.d/`` e ignora ``wireplumber.conf.d/`` sem
    erro; o 0.5 em diante lê SPA-JSON em ``wireplumber.conf.d/`` e não traz o
    ``main.lua.d``. A configuração de sistema que o próprio WirePlumber traz diz
    qual: a pasta ``main.lua.d`` é a pilha Lua, e só o 0.4 a entrega. Sem
    WirePlumber à vista a resposta é ``"conf"``, a de hoje.

    A PRIMEIRA raiz que traz configuração decide, e as outras não votam: um 0.5
    com ``main.lua.d`` esquecido em ``/etc/wireplumber`` (o Arch que subiu do 0.4)
    é ``"conf"``, porque o ``/usr/share`` dele traz o ``wireplumber.conf`` sem a
    pilha Lua. Uma raiz sem ``main.lua.d``, sem ``wireplumber.conf`` e sem
    ``wireplumber.conf.d`` não traz configuração nenhuma e passa a vez.
    """
    bruto = os.environ.get(WIREPLUMBER_SISTEMA_ENV_VAR, "").strip()
    raizes = [r for r in bruto.split(":") if r] if bruto else list(_WIREPLUMBER_SISTEMA)
    for raiz in raizes:
        base = Path(raiz)
        if (base / "main.lua.d").is_dir():
            return FORMA_LUA
        if (base / "wireplumber.conf").is_file() or (base / "wireplumber.conf.d").is_dir():
            return FORMA_CONF
    return FORMA_CONF


def _raiz_da_config(config_home: Path | None) -> Path:
    if config_home is not None:
        return config_home
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return Path(base) if base else Path.home() / ".config"


def wireplumber_pasta_da_forma(forma: str, config_home: Path | None = None) -> Path:
    """A pasta de drop-ins do usuário para ``forma`` (sem criar)."""
    sub = "main.lua.d" if forma == FORMA_LUA else "wireplumber.conf.d"
    return _raiz_da_config(config_home) / "wireplumber" / sub


def wireplumber_nome_do_dropin(nome_conf: str, forma: str | None = None) -> str:
    """O nome do drop-in na forma pedida (a de agora, se omitida).

    O nome canônico é o do asset SPA-JSON (``51-….conf``); na forma Lua o mesmo
    nome troca a extensão para ``.lua``. Aceita o nome em qualquer das duas.
    """
    forma = forma or wireplumber_forma()
    base, _, ext = nome_conf.rpartition(".")
    if ext not in ("conf", "lua"):
        base = nome_conf
    return f"{base}.lua" if forma == FORMA_LUA else f"{base}.conf"


def wireplumber_dropin(nome_conf: str, config_home: Path | None = None) -> Path:
    """Onde o drop-in ``nome_conf`` mora, na pasta e na forma que o WirePlumber lê."""
    forma = wireplumber_forma()
    return wireplumber_pasta_da_forma(forma, config_home) / wireplumber_nome_do_dropin(
        nome_conf, forma
    )


def wireplumber_config_dir(ensure: bool = False) -> Path:
    """Diretório dos drop-ins do WirePlumber — honra `XDG_CONFIG_HOME` (T-05,
    ONDA0-Z7, 24/08/2026), na forma que o WirePlumber instalado lê.

    O WirePlumber em si HONRA `XDG_CONFIG_HOME`; dois pontos do Hefesto
    escreviam/liam nele calados, incondicionalmente em `Path.home() /
    ".config"` — `integrations/storm_doctor.check_wireplumber` e
    `app/actions/emulation_actions._wp_dropin_dir` (medido em 23/08/2026,
    §3.4 da sprint O AMBIENTE PRESUMIDO 01: quem move `XDG_CONFIG_HOME` leva
    o drop-in do microfone, e o Hefesto continuava olhando o lugar velho).
    Um dono só, chamado pelos dois — mesmo padrão de `${XDG_CONFIG_HOME:-
    $HOME/.config}` que os shells desta casa já resolvem
    (`scripts/disable_steam_input.sh:257`, `scripts/doctor.sh`).

    A pasta é ``wireplumber.conf.d`` (0.5 em diante) ou ``main.lua.d`` (0.4):
    ver :func:`wireplumber_forma`. O nome do arquivo nela é o de
    :func:`wireplumber_nome_do_dropin`.
    """
    p = wireplumber_pasta_da_forma(wireplumber_forma())
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ipc_socket_path() -> Path:
    """Resolve o path do socket IPC."""
    return runtime_dir(ensure=True) / ipc_socket_name()


def mods_codigo_dir() -> Path:
    """O código de cada modificação instalada: ``<dados>/mods/<id>/``."""
    return data_dir() / "mods"


def mods_dados_dir() -> Path:
    """Os dados graváveis de cada modificação: ``<estado>/mods/<id>/``."""
    return state_dir() / "mods"


def mods_registro_path() -> Path:
    """O registro das modificações instaladas (origem, commit, permissões, ligada)."""
    return config_dir() / "mods.json"


def mods_socket_path() -> Path:
    """A porta das modificações, separada do socket principal."""
    return runtime_dir() / "mods.sock"


def mods_estado_path() -> Path:
    """O estado vivo das modificações, escrito pelo supervisor do serviço."""
    return runtime_dir() / "mods-estado.json"


__all__ = [
    "FAKE_ENV_VAR",
    "FORMA_CONF",
    "FORMA_LUA",
    "IPC_SOCKET_DEFAULT_NAME",
    "IPC_SOCKET_ENV_VAR",
    "IPC_SOCKET_FAKE_NAME",
    "WIREPLUMBER_SISTEMA_ENV_VAR",
    "cache_dir",
    "config_dir",
    "data_dir",
    "fake_mode_enabled",
    "ipc_socket_name",
    "ipc_socket_path",
    "launch_env_dir",
    "mods_codigo_dir",
    "mods_dados_dir",
    "mods_estado_path",
    "mods_registro_path",
    "mods_socket_path",
    "profiles_dir",
    "runtime_dir",
    "state_dir",
    "wireplumber_config_dir",
    "wireplumber_dropin",
    "wireplumber_forma",
    "wireplumber_nome_do_dropin",
    "wireplumber_pasta_da_forma",
]
