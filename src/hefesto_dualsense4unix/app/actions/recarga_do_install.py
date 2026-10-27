"""O fim do install: a janela e a bandeja que estavam abertas fecham e voltam com o código novo."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from hefesto_dualsense4unix.app.actions import atos_da_bandeja as bandeja
from hefesto_dualsense4unix.utils import single_instance as si
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

PRAZO_DA_BANDEJA_S = 10.0

VARIAVEIS_DA_TELA = (
    "WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY", "GDK_BACKEND",
    "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
)


def janelas_abertas() -> list[int]:
    """Os PIDs das janelas de pé, um por tela, pelos `gui-*.pid` conferidos no `/proc`."""
    pids: list[int] = []
    for arquivo in sorted(runtime_dir().glob("gui-*.pid")):
        pid = si._read_existing_pid(arquivo)
        if pid and si.is_alive(pid) and si._is_hefesto_dualsense4unix_process(pid):
            pids.append(pid)
    return pids


def a_tela_de(pid: int) -> dict[str, str]:
    """As variáveis da tela em que a janela `pid` está, para ela voltar no mesmo lugar."""
    try:
        bruto = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    tela: dict[str, str] = {}
    for item in bruto.split(b"\0"):
        nome, _, valor = item.partition(b"=")
        chave = nome.decode(errors="replace")
        if chave in VARIAVEIS_DA_TELA:
            tela[chave] = valor.decode(errors="replace")
    return tela


def terminar(pid: int, prazo: float) -> bool:
    """SIGTERM e a espera pelo fim limpo, sem SIGKILL. Diz se o processo saiu."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if not si.is_alive(pid):
            return True
        time.sleep(si.SIGTERM_POLL_INTERVAL_SEC)
    return not si.is_alive(pid)


def abrir_a_janela(tela: dict[str, str]) -> bool:
    """Abre a janela pelo lançador, desprendida, na tela que ela ocupava. Diz se abriu."""
    lancador = shutil.which(bandeja.LANCADOR_DO_PAINEL) or str(
        Path.home() / ".local" / "bin" / bandeja.LANCADOR_DO_PAINEL)
    if not Path(lancador).is_file():
        return False
    ambiente = {**os.environ, **tela, "HEFESTO_NA_TELA": "1"}
    try:
        subprocess.Popen(
            [lancador], env=ambiente, start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def recarregar(
    abrir: Callable[[dict[str, str]], bool] = abrir_a_janela,
    subir_a_bandeja: Callable[[], bool] = bandeja.garantir_a_bandeja,
) -> list[str]:
    """Fecha e reabre a janela e a bandeja que estavam abertas. Devolve uma frase por peça."""
    janelas = janelas_abertas()
    frases: list[str] = [] if janelas else ["janela: nenhuma aberta"]
    for pid in janelas:
        tela = a_tela_de(pid)
        if not terminar(pid, si.PRAZO_DO_DESLIGAMENTO_S):
            frases.append(f"janela: não fechou em {si.PRAZO_DO_DESLIGAMENTO_S:.0f} s")
            continue
        frases.append("janela: fechada e reaberta" if abrir(tela)
                      else "janela: fechada, mas não achei o lançador para reabrir")
    viva = bandeja.bandeja_viva()
    if viva is not None and not terminar(viva, PRAZO_DA_BANDEJA_S):
        frases.append(f"ícone na bandeja: não fechou em {PRAZO_DA_BANDEJA_S:.0f} s")
        return frases
    subiu = subir_a_bandeja()
    if viva is not None:
        frases.append("ícone na bandeja: fechado e reaberto" if subiu
                      else "ícone na bandeja: fechado, e não subiu de novo")
    else:
        frases.append("ícone na bandeja: subiu" if subiu
                      else "ícone na bandeja: desligado pela escolha")
    return frases


def main() -> int:
    """``python -m …recarga_do_install`` — uma frase por linha."""
    for frase in recarregar():
        print(frase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
