"""O ambiente de interpretador de quem chamou não vai para a Steam nem para o jogo."""
from __future__ import annotations

from collections.abc import Mapping

VARIAVEIS_DO_INTERPRETADOR: tuple[str, ...] = (
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "CONDA_SHLVL",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYENV_VERSION",
)

PREFIXOS_COM_BIN_NO_PATH: tuple[str, ...] = ("VIRTUAL_ENV", "CONDA_PREFIX")

VARIAVEIS_DE_BUSCA: tuple[str, ...] = ("PATH", "SYSTEM_PATH")


def _bins_do_chamador(environ: Mapping[str, str]) -> frozenset[str]:
    """Os `<prefixo>/bin` que a ativação do chamador pôs no `PATH`."""
    bins: set[str] = set()
    for nome in PREFIXOS_COM_BIN_NO_PATH:
        base = environ.get(nome, "").removesuffix("/")
        if base:
            bins.add(f"{base}/bin")
    return frozenset(bins)


def _podar(caminho: str, bins: frozenset[str]) -> str:
    """`caminho` sem as entradas de `bins` (com ou sem barra final)."""
    novo = ":".join(e for e in caminho.split(":") if e.removesuffix("/") not in bins)
    return novo or caminho


def ambiente_limpo(environ: Mapping[str, str]) -> dict[str, str]:
    """Uma cópia de `environ` sem o ambiente de interpretador do chamador."""
    env = dict(environ)
    bins = _bins_do_chamador(env)
    for nome in VARIAVEIS_DO_INTERPRETADOR:
        env.pop(nome, None)
    if bins:
        for nome in VARIAVEIS_DE_BUSCA:
            caminho = env.get(nome)
            if caminho:
                env[nome] = _podar(caminho, bins)
    return env


__all__ = [
    "PREFIXOS_COM_BIN_NO_PATH",
    "VARIAVEIS_DE_BUSCA",
    "VARIAVEIS_DO_INTERPRETADOR",
    "ambiente_limpo",
]
