#!/usr/bin/env python3
"""Sobe a Steam com o ambiente da SESSÃO GRÁFICA, nunca com o do shell do agente.

**A ARMADILHA QUE ISTO EXISTE PARA MATAR — 17/09/2026.** Um assistente fechou a
Steam dela e reabriu com `setsid steam` do próprio Bash. A Steam herdou o
ambiente inteiro do shell do assistente, e **todo jogo lançado por ela herdou
junto**. Medido no `environ` do `PRAGMATA.exe`:

    CLAUDECODE=1 · AI_AGENT=…_agent · PYENV_ROOT=…
    VIRTUAL_ENV=/mnt/Apate/…/venv        ← apontando para uma venv que NÃO EXISTE
    SYSTEM_PATH=/mnt/Apate/…/venv/bin:…  ← a venv na frente do PATH

O `proton` é um script Python. Um lançamento com essa bagagem **não é o mesmo
experimento** que o clique dela no ícone — e uma hora de investigação comparou
rodadas viciadas entre si, acusando o gadget USB, o UCM, o ACL e o daemon de um
defeito que nenhum deles causava.

**Por que `execve` e não `env -i` no shell:** variáveis com espaço (`LS_COLORS`,
`COSMIC_*`) são quebradas pelo word splitting do shell, e a linha montada com
`$(...)` sai errada — foi a primeira tentativa, e a Steam não subiu.
`os.execve` recebe o dicionário inteiro, sem shell no meio.

**A fonte do ambiente limpo** é um processo nascido da sessão gráfica dela. É o
mais perto que se chega de reproduzir o clique no ícone sem tocar no mouse.

Uso:
    scripts/subir-steam-limpa.py              # acha a fonte sozinho
    scripts/subir-steam-limpa.py --conferir   # só mede, não sobe nada
"""
from __future__ import annotations

import argparse
import contextlib
import os
import pathlib

#: O que NUNCA pode chegar a um jogo. Se uma destas está no ambiente, quem
#: lançou foi o agente — e a medição que sair dali não vale.
SUJEIRA = (
    "CLAUDECODE",
    "AI_AGENT",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_ENTRYPOINT",
    "VIRTUAL_ENV",
    "PYENV_ROOT",
    "STARSHIP_SHELL",
    "ALACRITTY_WINDOW_ID",
)

#: Sem estas a Steam não sobe. Medir ANTES de matar a que está de pé.
ESSENCIAIS = ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "HOME", "PATH")

#: Candidatos a doador do ambiente, em ordem de preferência. Todos nascem da
#: sessão gráfica; o primeiro que existir e passar na conferência é usado.
DOADORES = ("cosmic-panel", "cosmic-comp", "cosmic-bg", "cosmic-osd")

STEAM = "/usr/games/steam"


def ambiente_de(pid: int) -> dict[str, str]:
    """O `environ` de um processo, como dicionário."""
    cru = pathlib.Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for par in cru.split(b"\0"):
        if par and b"=" in par:
            k, v = par.split(b"=", 1)
            env[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")
    return env


def pid_de(nome: str) -> int | None:
    """O PID do primeiro processo cujo `comm` é exatamente `nome`.

    Lê `/proc/*/comm`, nunca `pgrep -f`: o `-f` casa a linha de comando
    inteira, e um script que procura por um nome encontra A SI MESMO — foi o
    que fez um medidor declarar o jogo de pé na volta zero.
    """
    for p in pathlib.Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / "comm").read_text().strip() == nome:
                return int(p.name)
        except OSError:
            continue
    return None


def colher() -> tuple[int, str, dict[str, str]]:
    """Ambiente limpo do primeiro doador que servir. Levanta se nenhum servir."""
    recusas = []
    for nome in DOADORES:
        pid = pid_de(nome)
        if pid is None:
            recusas.append(f"{nome}: não está de pé")
            continue
        env = ambiente_de(pid)
        if faltando := [v for v in ESSENCIAIS if v not in env]:
            recusas.append(f"{nome} (pid {pid}): sem {faltando}")
            continue
        if suja := [v for v in SUJEIRA if v in env]:
            recusas.append(f"{nome} (pid {pid}): CONTAMINADO com {suja}")
            continue
        return pid, nome, env
    raise SystemExit("nenhum doador serviu:\n  " + "\n  ".join(recusas))


def conferir_a_steam_viva() -> None:
    """Diz se a Steam que está de pé AGORA foi lançada suja."""
    pid = pid_de("steam")
    if pid is None:
        print("a Steam não está de pé")
        return
    env = ambiente_de(pid)
    suja = [v for v in SUJEIRA if v in env]
    if suja:
        print(f"A STEAM VIVA (pid {pid}) ESTÁ CONTAMINADA: {suja}")
        print("  todo jogo lançado por ela herda isso — feche e suba com este script")
        raise SystemExit(1)
    print(f"a Steam viva (pid {pid}) está limpa")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--conferir", action="store_true", help="só mede a Steam viva; não sobe nada")
    args = p.parse_args()

    if args.conferir:
        conferir_a_steam_viva()
        return

    pid, nome, env = colher()
    print(f"ambiente colhido de {nome} (pid {pid}): {len(env)} variáveis, sem {list(SUJEIRA)}")

    # O doador é um painel/compositor; a Steam não herda os descritores dele.
    env.pop("PANEL_NOTIFICATIONS_FD", None)
    for k in [k for k in env if k.startswith("COSMIC_PANEL")]:
        del env[k]

    with contextlib.suppress(PermissionError):
        os.setsid()  # já somos líder de sessão (rodado sob `setsid`)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 0), os.dup2(fd, 1), os.dup2(fd, 2)
    os.execve(STEAM, ["steam"], env)


if __name__ == "__main__":
    main()
