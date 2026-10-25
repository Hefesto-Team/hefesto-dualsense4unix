"""O aviso ao systemd é só do daemon e não vaza aos filhos.

O defeito de 25/10/2026: a unit é `Type=notify` com `NotifyAccess=main`, mas os filhos do daemon
herdavam o `NOTIFY_SOCKET`. `systemctl`, `udevadm`, `busctl` e `systemd-run` mandam
`EXIT_STATUS=0` ao sair (o `sudo`, `READY=1`), e o diário do serviço enchia de «Got notification
message from PID N, but reception only permitted for main PID M». A cura: a entrada do daemon
tira o soquete do ambiente e o guarda em `utils/sd_notify`, antes de qualquer filho.

Tudo aqui roda com um soquete abstrato de mentira e filhos `python -c`: nenhum `systemctl`,
nenhum serviço de verdade, nenhum daemon de pé.
"""
from __future__ import annotations

import asyncio
import os
import re
import secrets
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import main as entrada
from hefesto_dualsense4unix.utils import sd_notify

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "hefesto-dualsense4unix.service"

#: O filho que faz o que o `systemctl` faz ao sair: manda um aviso ao `NOTIFY_SOCKET` herdado.
_FILHO_QUE_AVISA = """
import os, socket
alvo = os.environ.get("NOTIFY_SOCKET")
if alvo:
    if alvo.startswith("@"):
        alvo = "\\0" + alvo[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
        s.sendto(b"EXIT_STATUS=0", alvo)
"""


@pytest.fixture
def ouvinte(monkeypatch: pytest.MonkeyPatch) -> Iterator[socket.socket]:
    """O `NOTIFY_SOCKET` de mentira, abstrato como o do systemd de usuário, e o guardado limpo."""
    nome = f"hefesto-teste-aviso-{os.getpid()}-{secrets.token_hex(4)}"
    soquete = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    soquete.bind("\0" + nome)
    soquete.setblocking(False)
    monkeypatch.setattr(sd_notify, "_guardadas", {})
    monkeypatch.setenv("NOTIFY_SOCKET", "@" + nome)
    try:
        yield soquete
    finally:
        soquete.close()


def _recebidas(soquete: socket.socket) -> list[str]:
    saiu: list[str] = []
    while True:
        try:
            saiu.append(soquete.recv(256).decode("utf-8"))
        except BlockingIOError:
            return saiu


def _pelo_subprocess() -> None:
    subprocess.run([sys.executable, "-c", _FILHO_QUE_AVISA], check=True, timeout=30)


def _pelo_asyncio() -> None:
    async def _corre() -> int:
        filho = await asyncio.create_subprocess_exec(sys.executable, "-c", _FILHO_QUE_AVISA)
        return await filho.wait()

    assert asyncio.run(_corre()) == 0


def _pelo_spawn() -> None:
    assert os.spawnv(os.P_WAIT, sys.executable, [sys.executable, "-c", _FILHO_QUE_AVISA]) == 0


CAMINHOS: dict[str, Callable[[], None]] = {
    "subprocess": _pelo_subprocess,
    "asyncio": _pelo_asyncio,
    "os.spawn": _pelo_spawn,
}


# -- a cura -----------------------------------------------------------------------------


@pytest.mark.parametrize("caminho", sorted(CAMINHOS))
def test_o_filho_nao_alcanca_o_soquete_e_o_pronto_alcanca(
        ouvinte: socket.socket, caminho: str) -> None:
    """MORDIDA: deixe o `NOTIFY_SOCKET` em `os.environ` e o `EXIT_STATUS=0` do filho chega."""
    sd_notify.guardar_o_soquete()
    CAMINHOS[caminho]()
    assert _recebidas(ouvinte) == [], f"o filho lançado por {caminho} herdou o soquete"
    assert "NOTIFY_SOCKET" not in os.environ
    assert sd_notify.pronto() is True
    assert sd_notify.parando() is True
    assert _recebidas(ouvinte) == ["READY=1", "STOPPING=1"]


def test_o_controle_sem_a_cura_o_filho_alcanca(ouvinte: socket.socket) -> None:
    """O instrumento mede: com o soquete no ambiente, o filho de mentira chega a ele."""
    _pelo_subprocess()
    assert _recebidas(ouvinte) == ["EXIT_STATUS=0"]


def test_as_variaveis_do_watchdog_tambem_saem(
        ouvinte: socket.socket, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()))
    monkeypatch.setenv("WATCHDOG_USEC", "30000000")
    sd_notify.guardar_o_soquete()
    for nome in sd_notify.VARIAVEIS_DO_PRINCIPAL:
        assert nome not in os.environ, nome
    assert sd_notify.pronto() is True
    assert _recebidas(ouvinte) == ["READY=1"]


def test_guardar_duas_vezes_nao_perde_o_soquete(ouvinte: socket.socket) -> None:
    sd_notify.guardar_o_soquete()
    sd_notify.guardar_o_soquete()
    assert "NOTIFY_SOCKET" not in os.environ
    assert sd_notify.pronto() is True
    assert _recebidas(ouvinte) == ["READY=1"]


def test_sem_notify_socket_guardar_nao_levanta_nem_avisa(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon avulso e o `--foreground` à mão não têm soquete: nada muda."""
    monkeypatch.setattr(sd_notify, "_guardadas", {})
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    sd_notify.guardar_o_soquete()
    sd_notify.guardar_o_soquete()
    assert sd_notify.pronto() is False
    assert sd_notify.parando() is False


# -- a entrada do daemon ----------------------------------------------------------------


class _ParouNoPrimeiroPassoError(Exception):
    pass


def test_a_entrada_do_daemon_tira_o_soquete_antes_de_tudo(
        ouvinte: socket.socket, monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_daemon` guarda o soquete antes do primeiro passo dele (o `configure_logging`).

    MORDIDA: tire o `guardar_o_soquete()` de `run_daemon` e o soquete ainda está no ambiente
    quando o daemon começa.
    """
    visto: list[str | None] = []

    def _primeiro_passo() -> None:
        visto.append(os.environ.get("NOTIFY_SOCKET"))
        raise _ParouNoPrimeiroPassoError

    monkeypatch.setattr(entrada, "configure_logging", _primeiro_passo)
    with pytest.raises(_ParouNoPrimeiroPassoError):
        entrada.run_daemon()
    assert visto == [None]
    assert sd_notify.pronto() is True
    assert _recebidas(ouvinte) == ["READY=1"]


# -- a unit -----------------------------------------------------------------------------


def test_o_comentario_da_unit_diz_quem_tira_o_soquete() -> None:
    """O comentário prometia que o `fora_do_servico` segurava o soquete; quem segura é a entrada."""
    texto = " ".join(
        linha.lstrip("# ").strip()
        for linha in UNIT.read_text(encoding="utf-8").splitlines()
        if linha.startswith("#")
    )
    assert re.search(r"NOTIFY_SOCKET.*daemon/main\.run_daemon", texto)
    assert "sd_notify.guardar_o_soquete" in texto
    assert callable(getattr(sd_notify, "guardar_o_soquete", None))
