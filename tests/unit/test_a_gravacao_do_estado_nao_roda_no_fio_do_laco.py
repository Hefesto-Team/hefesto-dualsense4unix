"""A gravação do estado não roda no fio do laço: o tique entrega e volta, o gravador espera o disco.

D-1911-O-ESTADO-SE-GRAVA-INTEIRO: o arquivo novo inteiro ou o de antes. O disco de mentira fica
parado numa porta (`threading.Event`) enquanto quatro controles, dois por cabo e dois por rádio,
entram e saem pelo tique do laço: o tique não passa de 50 ms, e depois da porta aberta o arquivo
é o da última gravação.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.utils import escrita_inteira as ei

LIMITE_DO_TIQUE_S = 0.050
FRASE = "a gravação parou o laço"
CABO_1 = "aa:bb:cc:00:00:01"
RADIO_2 = "AA:BB:CC:00:00:02"
CABO_3 = "aa:bb:cc:00:00:03"
RADIO_4 = "AA:BB:CC:00:00:04"


class Disco:
    """O disco de mentira: o `os.replace` do alvo espera a porta abrir (ou falha)."""

    def __init__(self) -> None:
        self.porta = threading.Event()
        self.chegou = threading.Event()
        self.falha: OSError | None = None
        self.trocas = 0

    def abrir(self) -> None:
        self.porta.set()


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "boot-teste")
    monkeypatch.setattr(id_mod, "_session_anchor", lambda: "boot-teste")
    return tmp_path


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> Iterator[Disco]:
    d = Disco()
    real = os.replace

    def lento(origem: Any, destino: Any) -> None:
        if str(destino).endswith(("controllers.json", "alvo.json")):
            d.chegou.set()
            d.porta.wait(2.0)
            if d.falha is not None:
                raise d.falha
            d.trocas += 1
        real(origem, destino)

    monkeypatch.setattr(os, "replace", lento)
    yield d
    d.abrir()
    ei.esperar_a_fila(5.0)


def _fila(pasta: Path) -> dict[str, int]:
    dados = json.loads((pasta / "controllers.json").read_text(encoding="utf-8"))
    return {e["addr"]: e["rank"] for e in dados[id_mod.ORDER_FIELD]}


def _tique(registro: id_mod.ControllerIdentityRegistry, uniqs: list[str]) -> float:
    antes = time.perf_counter()
    registro.sync_connected(uniqs)
    return time.perf_counter() - antes


def test_o_tique_com_quatro_controles_nao_espera_o_disco(config: Path, disco: Disco) -> None:
    registro = id_mod.ControllerIdentityRegistry()
    registro.load()
    sequencia = [
        [CABO_1],
        [CABO_1, RADIO_2],
        [CABO_1, RADIO_2, CABO_3],
        [CABO_1, RADIO_2, CABO_3, RADIO_4],
        [RADIO_2, CABO_3, RADIO_4],
        [RADIO_4, CABO_1],
        [CABO_3, RADIO_4, CABO_1, RADIO_2],
    ]

    async def laco() -> list[float]:
        return [_tique(registro, uniqs) for uniqs in sequencia]

    duracoes = asyncio.run(laco())
    assert max(duracoes) < LIMITE_DO_TIQUE_S, FRASE
    disco.abrir()
    assert ei.esperar_a_fila(5.0)
    assert sorted(_fila(config).values()) == [1, 2, 3, 4]


def test_o_tique_nao_espera_a_trava_do_arquivo(config: Path) -> None:
    registro = id_mod.ControllerIdentityRegistry()
    registro.load()
    segurada, solta = threading.Event(), threading.Event()

    def outro_fio() -> None:
        with id_mod.CONTROLLERS_FILE_LOCK:
            segurada.set()
            solta.wait(5.0)

    fio = threading.Thread(target=outro_fio)
    fio.start()
    segurada.wait(5.0)

    async def laco() -> float:
        return _tique(registro, [CABO_1])

    try:
        duracao = asyncio.run(laco())
    finally:
        solta.set()
        fio.join()
    assert duracao < LIMITE_DO_TIQUE_S, FRASE
    assert ei.esperar_a_fila(5.0)
    assert list(_fila(config).values()) == [1]


def test_fora_do_laco_a_gravacao_e_sincrona(config: Path) -> None:
    registro = id_mod.ControllerIdentityRegistry()
    registro.load()
    registro.sync_connected([CABO_1, RADIO_2])
    assert sorted(_fila(config).values()) == [1, 2]


def test_a_falha_do_disco_deixa_o_arquivo_de_antes_inteiro_e_sem_temporario(
    config: Path, disco: Disco, monkeypatch: pytest.MonkeyPatch
) -> None:
    registro = id_mod.ControllerIdentityRegistry()
    registro.load()
    disco.abrir()
    registro.sync_connected([CABO_1])
    antes = (config / "controllers.json").read_bytes()
    dito: list[str] = []
    monkeypatch.setattr(
        id_mod.logger, "debug", lambda evento, **_kw: dito.append(evento)
    )
    disco.falha = OSError(28, "sem espaço")

    async def laco() -> None:
        registro.sync_connected([CABO_1, RADIO_2])

    asyncio.run(laco())
    assert ei.esperar_a_fila(5.0)
    assert (config / "controllers.json").read_bytes() == antes
    assert [p.name for p in config.iterdir() if p.name.startswith(".controllers_")] == []
    assert "identity_save_falhou" in dito


def test_a_falha_do_gravador_chega_pelo_futuro_e_fora_do_laco_levanta(tmp_path: Path) -> None:
    def quebra() -> None:
        raise OSError(5, "disco")

    async def laco() -> Future[None] | None:
        return ei.gravar_sem_parar_o_laco("chave", quebra)

    futuro = asyncio.run(laco())
    assert futuro is not None
    with pytest.raises(OSError, match="disco"):
        futuro.result(5.0)
    with pytest.raises(OSError, match="disco"):
        ei.gravar_sem_parar_o_laco("chave", quebra)


def test_duas_gravacoes_do_mesmo_alvo_na_fila_viram_a_ultima(
    tmp_path: Path, disco: Disco
) -> None:
    alvo = tmp_path / "alvo.json"

    async def laco() -> list[bytes | None]:
        ei.escrever_inteiro_sem_parar_o_laco(alvo, "um")
        await asyncio.to_thread(disco.chegou.wait, 5.0)
        ei.escrever_inteiro_sem_parar_o_laco(alvo, "dois")
        ei.escrever_inteiro_sem_parar_o_laco(alvo, "três")
        return [ei.ler_o_que_esta_na_fila(alvo)]

    (lido,) = asyncio.run(laco())
    assert lido == "três".encode()
    disco.abrir()
    assert ei.esperar_a_fila(5.0)
    assert alvo.read_bytes() == "três".encode()
    assert disco.trocas == 2
    assert ei.ler_o_que_esta_na_fila(alvo) is None


def test_a_parada_espera_a_fila_esvaziar(tmp_path: Path, disco: Disco) -> None:
    alvo = tmp_path / "alvo.json"

    async def laco() -> None:
        ei.escrever_inteiro_sem_parar_o_laco(alvo, "x")

    asyncio.run(laco())
    assert ei.esperar_a_fila(0.05) is False
    disco.abrir()
    assert ei.esperar_a_fila(5.0) is True
    assert alvo.read_bytes() == b"x"


def test_fora_do_laco_o_escrever_sem_parar_grava_e_levanta_na_hora(tmp_path: Path) -> None:
    alvo = tmp_path / "alvo.json"
    assert ei.escrever_inteiro_sem_parar_o_laco(alvo, "inteiro") is None
    assert alvo.read_bytes() == b"inteiro"
    assert ei.ler_o_que_esta_na_fila(alvo) is None


def test_o_gesto_explicito_de_renumerar_responde_depois_de_gravar(config: Path) -> None:
    registro = id_mod.ControllerIdentityRegistry()
    registro.load()
    registro.sync_connected([CABO_1, RADIO_2])
    antes = _fila(config)
    trocado = {chave: 3 - lugar for chave, lugar in registro.snapshot().items()}

    async def laco() -> dict[str, int]:
        registro.compact(trocado)
        return _fila(config)

    depois = asyncio.run(laco())
    assert sorted(depois.values()) == [1, 2]
    assert depois != antes
