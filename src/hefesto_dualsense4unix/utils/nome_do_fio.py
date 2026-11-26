"""O dono do nome dos fios no kernel: cada fio do serviço aparece com o nome Python dele.

O CPython 3.12 não passa o ``Thread.name`` ao kernel, e todos os fios do serviço saíam em
``/proc/<pid>/task/*/comm`` com o nome do processo; o ``top -H`` e o doctor não diziam qual fio
gastava (OS-FIOS-DO-SERVICO-TEM-NOME-E-CUSTO-MEDIDO-01). ``instalar()`` faz cada fio novo chamar
``prctl(PR_SET_NAME)`` ao nascer, sem mexer em quem cria o fio. O fio principal guarda o nome do
processo: é por ele que a instância única reconhece o serviço.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BYTES_DO_NOME = 15

_PR_SET_NAME = 15

_DO_ALVO = re.compile(r"^Thread-\d+ \((?P<alvo>.+)\)$")

_PREFIXOS_LONGOS = (("ThreadPoolExecutor-", "pool-"),)


def _carregar_o_prctl() -> Any:
    """O ``prctl`` da libc, ou ``None`` fora do Linux."""
    try:
        return ctypes.CDLL("libc.so.6", use_errno=True).prctl
    except (OSError, AttributeError):
        return None


_PRCTL = _carregar_o_prctl()

_original: Callable[[threading.Thread], None] | None = None


def nome_curto(nome: str) -> bytes:
    """O nome que cabe nos 15 bytes do kernel, com o que distingue o fio na frente.

    ``Thread-7 (ler)`` vira ``ler``; ``ThreadPoolExecutor-0_3`` vira ``pool-0_3``; o resto é
    cortado no último caractere inteiro que cabe.
    """
    achado = _DO_ALVO.match(nome)
    if achado is not None:
        nome = achado.group("alvo")
    for longo, curto in _PREFIXOS_LONGOS:
        if nome.startswith(longo):
            nome = curto + nome[len(longo):]
    cru = nome.encode("utf-8")[:BYTES_DO_NOME]
    return cru.decode("utf-8", errors="ignore").encode("utf-8")


def dar_o_nome(nome: str) -> bool:
    """Dá ao fio que chama o nome curto de ``nome`` no kernel. Nunca levanta."""
    prctl = _PRCTL
    if prctl is None:
        return False
    with contextlib.suppress(Exception):
        return int(prctl(_PR_SET_NAME, ctypes.c_char_p(nome_curto(nome)), 0, 0, 0)) == 0
    return False


def instalar() -> bool:
    """Todo fio que nascer daqui em diante leva o próprio nome ao kernel. Idempotente."""
    global _original
    if _original is not None:
        return True
    if _PRCTL is None:
        return False
    original = threading.Thread._bootstrap_inner  # type: ignore[attr-defined]

    def _nascer_com_nome(fio: threading.Thread) -> None:
        dar_o_nome(fio.name)
        original(fio)

    _original = original
    threading.Thread._bootstrap_inner = _nascer_com_nome  # type: ignore[attr-defined]
    return True


def desinstalar() -> None:
    """Devolve o nascimento original dos fios; para os testes."""
    global _original
    if _original is None:
        return
    threading.Thread._bootstrap_inner = _original  # type: ignore[attr-defined]
    _original = None


def nome_no_kernel(tid: int, pid: int | str = "self") -> str | None:
    """O ``comm`` do fio ``tid`` em ``/proc/<pid>/task``; ``None`` se não se lê."""
    try:
        return Path(f"/proc/{pid}/task/{tid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return None


@dataclass(frozen=True)
class CustoDoFio:
    """O que um fio gastou numa janela: o nome no kernel, a fração de um núcleo e as acordadas/s."""

    tid: int
    nome: str
    nucleo: float
    acordadas_s: float


def _leitura_do_fio(pasta: Path) -> tuple[str, int, int] | None:
    """``(comm, tiques de CPU, trocas voluntárias)`` do fio, ou ``None`` se ele já saiu."""
    try:
        nome = (pasta / "comm").read_text(encoding="utf-8").strip()
        stat = (pasta / "stat").read_text(encoding="utf-8")
        campos = stat[stat.rindex(")") + 2:].split()
        tiques = int(campos[11]) + int(campos[12])
        voluntarias = 0
        for linha in (pasta / "status").read_text(encoding="utf-8").splitlines():
            if linha.startswith("voluntary_ctxt_switches:"):
                voluntarias = int(linha.split()[1])
        return nome, tiques, voluntarias
    except (OSError, ValueError, IndexError):
        return None


def _leitura_dos_fios(pid: int | str) -> dict[int, tuple[str, int, int]]:
    leituras: dict[int, tuple[str, int, int]] = {}
    for pasta in Path(f"/proc/{pid}/task").iterdir():
        if not pasta.name.isdigit():
            continue
        lida = _leitura_do_fio(pasta)
        if lida is not None:
            leituras[int(pasta.name)] = lida
    return leituras


def custo_dos_fios(
    pid: int | str,
    janela_s: float,
    dormir: Callable[[float], None] = time.sleep,
) -> list[CustoDoFio]:
    """O custo de cada fio de ``pid`` em ``janela_s``, do que mais gasta ao que menos gasta.

    Lê ``/proc/<pid>/task/*/{comm,stat,status}`` antes e depois da janela; o fio que nasceu ou
    saiu no meio fica de fora. Levanta ``OSError`` se o processo não existe.
    """
    tiques_s = os.sysconf("SC_CLK_TCK")
    antes = _leitura_dos_fios(pid)
    comeco = time.monotonic()
    dormir(janela_s)
    depois = _leitura_dos_fios(pid)
    passou = max(time.monotonic() - comeco, janela_s, 1e-3)
    custos = [
        CustoDoFio(
            tid=tid,
            nome=nome,
            nucleo=max(tiques - antes[tid][1], 0) / tiques_s / passou,
            acordadas_s=max(voluntarias - antes[tid][2], 0) / passou,
        )
        for tid, (nome, tiques, voluntarias) in depois.items()
        if tid in antes
    ]
    return sorted(custos, key=lambda c: (c.nucleo, c.acordadas_s), reverse=True)


__all__ = [
    "BYTES_DO_NOME",
    "CustoDoFio",
    "custo_dos_fios",
    "dar_o_nome",
    "desinstalar",
    "instalar",
    "nome_curto",
    "nome_no_kernel",
]
