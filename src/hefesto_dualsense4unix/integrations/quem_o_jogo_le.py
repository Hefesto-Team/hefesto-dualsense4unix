"""Os processos que são JOGO, pelo ambiente (``STEAM_COMPAT_DATA_PATH``) e não pelo nome.

Não há mais portão de quem joga (A-HAPTICA-E-DO-JOGO-SEM-PORTAO-DE-QUEM-MEXE-01, 26/10/2026):
o que o jogo toca no endpoint de um controle chega a esse controle. Restou a pergunta dos pids,
que a guarda do rótulo, o transiente e o pad uhid fazem. A história do sinal do evdev (20 a
25/09) está em ``docs/research/o-porque-dos-modulos.md``, seção ``quem_o_jogo_le``.
"""

from __future__ import annotations

import pathlib

__all__ = ["ENV_DO_JOGO", "pids_de_jogo"]

ENV_DO_JOGO = "STEAM_COMPAT_DATA_PATH"


def _ambiente(pid: int, raiz_proc: pathlib.Path) -> str:
    try:
        return (raiz_proc / str(pid) / "environ").read_bytes().decode(
            "utf-8", "replace"
        )
    except OSError:
        return ""


def pids_de_jogo(raiz_proc: pathlib.Path | str = "/proc") -> set[int]:
    """Os processos que são JOGO, pelo ambiente e não pelo nome."""
    raiz = pathlib.Path(raiz_proc)
    achados: set[int] = set()
    try:
        entradas = list(raiz.iterdir())
    except OSError:
        return achados
    for entrada in entradas:
        if not entrada.name.isdigit():
            continue
        pid = int(entrada.name)
        if f"{ENV_DO_JOGO}=" in _ambiente(pid, raiz):
            achados.add(pid)
    return achados
