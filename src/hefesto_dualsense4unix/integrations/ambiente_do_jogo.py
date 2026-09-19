"""O ambiente de interpretador de quem chamou não vai para a Steam nem para o jogo.

AMBIENTE-DO-JOGO-01 (18/09/2026). Medido em 17/09 no `environ` do
`PRAGMATA.exe`: uma Steam aberta a partir de um terminal leva o ambiente desse
terminal para TODO jogo que ela lança — `VIRTUAL_ENV` apontando para uma venv
que nem existia, e o `bin/` dela na frente do `SYSTEM_PATH`. O `proton` é um
script Python (`#!/usr/bin/env python3`), então quem o roda passa a ser o
`python3` que o terminal escolheu, e não o da máquina. A Steam aberta pelo
ícone não carrega nada disso; a que o produto reabre de dentro de um terminal,
sim.

O portador medido foi o `SYSTEM_PATH`, e não o `PATH`, e a diferença decide a
cura. O `steam.sh` guarda o `PATH` com que a Steam subiu
(`export SYSTEM_PATH="$PATH"`), e a Steam Linux Runtime, que todo Proton
exige, o devolve ao `PATH` DEPOIS do gancho do jogo e antes do `proton`
(`pressure-vessel-unruntime`: `export PATH="$SYSTEM_PATH"`). Podar só o `PATH`
no gancho não chega ao `proton`: as duas variáveis de busca saem podadas.

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
três contra esta: os nomes, e o comportamento de borda caso a caso, com esta
função como oráculo.
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

#: As listas de busca de executável de onde os `bin/` acima saem. O `PATH`, e
#: o `SYSTEM_PATH`: o `steam.sh` o grava ao subir (`export SYSTEM_PATH="$PATH"`)
#: e o `pressure-vessel-unruntime` da Steam Linux Runtime faz
#: `export PATH="$SYSTEM_PATH"` depois do gancho, antes do `proton`. Uma que
#: não esteja no ambiente continua fora dele.
VARIAVEIS_DE_BUSCA: tuple[str, ...] = ("PATH", "SYSTEM_PATH")


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


def _podar(caminho: str, bins: frozenset[str]) -> str:
    """`caminho` sem as entradas de `bins` (com ou sem barra final).

    Guarda a ordem e as entradas vazias do resto. Se não sobrar nada, devolve
    `caminho` como veio: uma lista de busca vazia não acha nem o `sh`, e isso
    seria pior que o defeito.
    """
    novo = ":".join(e for e in caminho.split(":") if e.removesuffix("/") not in bins)
    return novo or caminho


def ambiente_limpo(environ: Mapping[str, str]) -> dict[str, str]:
    """Uma cópia de `environ` sem o ambiente de interpretador do chamador.

    Não muda `environ`. Cada lista de `VARIAVEIS_DE_BUSCA` perde só as
    entradas `<prefixo>/bin`; o que ela faz com a borda (barra final, entrada
    vazia, lista que ficaria vazia) está em `_podar`.
    """
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
