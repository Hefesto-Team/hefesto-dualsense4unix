"""O diário de toda extensão tem a hora de cada linha.

Sprint O-DIARIO-DE-CADA-EXTENSAO-TEM-A-HORA-DE-CADA-LINHA-01. Um processo de mentira escreve no
cano que o supervisor copia; o diário é de uma pasta temporária e nada fala com o serviço dela.
"""
from __future__ import annotations

import asyncio
import re
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as supervisor_mod

_HORA = re.compile(r"^\d{2}:\d{2}:\d{2} ")
_DATA_E_HORA = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")

_O_FILHO = textwrap.dedent('''
    import sys, time
    sys.stdout.write("primeira inteira\\nsegunda inteira\\n")
    sys.stdout.flush()
    time.sleep(0.3)
    sys.stdout.write("a partida ")
    sys.stdout.flush()
    time.sleep(0.3)
    sys.stdout.write("chega inteira\\n")
    sys.stdout.flush()
    time.sleep(0.3)
    sys.stdout.write("o fim sem quebra")
    sys.stdout.flush()
''')


def _relogio(*instantes: str) -> Callable[[], time.struct_time]:
    fila: Iterator[str] = iter(instantes)
    ultimo = [instantes[-1]]

    def agora() -> time.struct_time:
        ultimo[0] = next(fila, ultimo[0])
        return time.strptime(ultimo[0], "%Y-%m-%d %H:%M:%S")

    return agora


def _copiar(diario: Path, relogio: Callable[[], time.struct_time] | None = None) -> list[str]:
    async def corrida() -> None:
        processo = await asyncio.create_subprocess_exec(
            sys.executable, "-c", _O_FILHO,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert processo.stdout is not None
        if relogio is None:
            await supervisor_mod._copiar_para_o_diario(processo.stdout, diario)
        else:
            await supervisor_mod._copiar_para_o_diario(processo.stdout, diario, relogio=relogio)
        await processo.wait()

    asyncio.run(corrida())
    return diario.read_text(encoding="utf-8").splitlines()


def _sem_a_hora(linha: str) -> str:
    return _HORA.sub("", _DATA_E_HORA.sub("", linha))


def test_toda_linha_do_diario_comeca_pela_hora(tmp_path: Path) -> None:
    linhas = _copiar(tmp_path / "diario.log")
    assert len(linhas) == 4, linhas
    assert _DATA_E_HORA.match(linhas[0]), linhas[0]
    assert all(_HORA.match(linha) for linha in linhas[1:]), linhas


def test_a_linha_partida_sai_inteira_com_uma_hora_so(tmp_path: Path) -> None:
    linhas = _copiar(tmp_path / "diario.log")
    esperadas = ("primeira inteira", "segunda inteira", "a partida chega inteira",
                 "o fim sem quebra")
    assert len(linhas) == len(esperadas), linhas
    for linha, texto in zip(linhas, esperadas, strict=True):
        assert re.fullmatch(r"(\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} " + re.escape(texto),
                            linha), linhas


def test_o_pedaco_sem_quebra_entra_quando_o_processo_fecha(tmp_path: Path) -> None:
    diario = tmp_path / "diario.log"
    linhas = _copiar(diario)
    assert _sem_a_hora(linhas[-1]) == "o fim sem quebra", linhas
    assert diario.read_bytes().endswith(b"o fim sem quebra\n")


def test_a_data_volta_quando_o_dia_muda(tmp_path: Path) -> None:
    linhas = _copiar(tmp_path / "diario.log", _relogio(
        "2026-10-26 23:59:58", "2026-10-26 23:59:59", "2026-10-27 00:00:01",
        "2026-10-27 00:00:02",
    ))
    assert linhas == [
        "2026-10-26 23:59:58 primeira inteira",
        "23:59:59 segunda inteira",
        "2026-10-27 00:00:01 a partida chega inteira",
        "00:00:02 o fim sem quebra",
    ], linhas


def test_a_ultima_linha_que_a_tela_mostra_vem_sem_a_hora(tmp_path: Path) -> None:
    diario = tmp_path / "diario.log"
    diario.write_text("2026-10-26 13:19:00 o adaptador USB não conecta\n13:19:01 \n",
                      encoding="utf-8")
    assert supervisor_mod.ultima_linha_do_diario(diario, hora=True) == (
        "o adaptador USB não conecta")
    assert supervisor_mod.ultima_linha_do_diario(diario).startswith("13:19:01")


def test_o_teto_conta_a_hora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    teto = 4096
    monkeypatch.setattr(supervisor_mod, "TETO_DO_DIARIO_BYTES", teto)
    diario = tmp_path / "diario.log"

    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        leitor.feed_data(b"\n" * (teto // 4))
        leitor.feed_data(b"a linha final\n")
        leitor.feed_eof()
        await supervisor_mod._copiar_para_o_diario(leitor, diario)

    asyncio.run(corrida())
    assert diario.stat().st_size <= teto, diario.stat().st_size
    assert _sem_a_hora(diario.read_text(encoding="utf-8").splitlines()[-1]) == "a linha final"
