"""O ambiente de interpretador de quem chamou não vai para a Steam nem para o jogo.

AMBIENTE-DO-JOGO-01 (18/09/2026). Medido em 17/09 no `environ` do
`PRAGMATA.exe`: uma Steam aberta a partir de um terminal leva o ambiente desse
terminal para TODO jogo que ela lança — `VIRTUAL_ENV` apontando para uma venv
que nem existia, com o `bin/` dela na frente do `PATH`. O `proton` é um script
Python (`#!/usr/bin/env python3`), então quem o roda passa a ser o `python3`
que o terminal escolheu, e não o da máquina. A Steam aberta pelo ícone não
carrega nada disso; a que o produto reabre de dentro de um terminal, sim.

O produto reabre a Steam de dentro de um terminal da pessoa: o `install.sh`
roda `steam_launch_options.py --migrate/--apply --stop-steam` e
`scripts/disable_steam_input.sh --apply`, os dois fecham e reabrem a Steam, e
um conda com `auto_activate_base` (o caso comum de quem clona repositório)
põe `CONDA_PREFIX` e o `bin/` dele em todo terminal. O efeito é pior que
"terminal sujo": o produto pega uma Steam que a pessoa abriu pelo ícone, limpa,
e a devolve com o ambiente do terminal do install.

A CLASSE, e não o caso: variável com que o chamador ESCOLHEU um interpretador.
Não entram `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_*` nem `DBUS_*`, de que a Steam
precisa para abrir; nem variáveis de agente, que não são assunto do produto.

Módulo 100% stdlib DE PROPÓSITO: `steam_launch_options.py` o importa, e o
install/uninstall rodam aquele arquivo como script avulso com o `python3` do
sistema.

As duas pontas em shell repetem esta lista, porque não podem importar Python:
`assets/hefesto-launch.sh` (o gancho por onde todo jogo passa, e que limpa
também a Steam que a PESSOA abriu de um terminal) e
`scripts/disable_steam_input.sh` (que reabre a Steam no install). A régua
`tests/unit/test_ambiente_do_jogo_01_o_terminal_nao_vai_junto.py` confere as
três contra esta.
"""
from __future__ import annotations

from collections.abc import Mapping

#: Variáveis que escolhem o interpretador do chamador. Saem inteiras.
VARIAVEIS_DO_INTERPRETADOR: tuple[str, ...] = (
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "CONDA_SHLVL",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYENV_VERSION",
)

#: Das variáveis acima, as que apontam uma pasta cujo `bin/` a ativação pôs no
#: `PATH`. Tirar a variável e deixar o `bin/` não cura nada: é o `PATH` que
#: decide qual `python3` o `/usr/bin/env` do `proton` acha.
PREFIXOS_COM_BIN_NO_PATH: tuple[str, ...] = ("VIRTUAL_ENV", "CONDA_PREFIX")


def _bins_do_chamador(environ: Mapping[str, str]) -> frozenset[str]:
    """Os `<prefixo>/bin` que a ativação do chamador pôs no `PATH`.

    Uma barra final no prefixo não muda a pasta; um prefixo que é só `/` daria
    `/bin`, que é da máquina, e fica de fora.
    """
    bins: set[str] = set()
    for nome in PREFIXOS_COM_BIN_NO_PATH:
        base = environ.get(nome, "").removesuffix("/")
        if base:
            bins.add(f"{base}/bin")
    return frozenset(bins)


def ambiente_limpo(environ: Mapping[str, str]) -> dict[str, str]:
    """Uma cópia de `environ` sem o ambiente de interpretador do chamador.

    Não muda `environ`. O `PATH` perde só as entradas `<prefixo>/bin` (com ou
    sem barra final) e guarda a ordem e as entradas vazias do resto. Se tirar
    essas entradas deixasse o `PATH` vazio, ele fica como estava: uma Steam sem
    `PATH` não abre, e isso seria pior que o defeito.
    """
    env = dict(environ)
    bins = _bins_do_chamador(env)
    for nome in VARIAVEIS_DO_INTERPRETADOR:
        env.pop(nome, None)
    caminho = env.get("PATH")
    if bins and caminho:
        novo = ":".join(
            e for e in caminho.split(":") if e.removesuffix("/") not in bins
        )
        if novo:
            env["PATH"] = novo
    return env


__all__ = [
    "PREFIXOS_COM_BIN_NO_PATH",
    "VARIAVEIS_DO_INTERPRETADOR",
    "ambiente_limpo",
]
