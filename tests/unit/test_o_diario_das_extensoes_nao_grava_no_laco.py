"""O-DIARIO-DAS-EXTENSOES-NAO-GRAVA-NO-LACO-01 — as réguas.

O laço lê o cano e enfileira; o disco é do fio de cada extensão. Com o ``write`` preso 2 s, o
cano segue, o tique segue, e a ordem e a hora de cada linha são as mesmas.
MORDIDA: fazer ``_EscritorDoDiario.por`` gravar no laço reprova as que medem o tique.
"""
from __future__ import annotations

import asyncio
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import supervisor as supervisor_mod

_TETO_DO_FURO_S = 0.25


class _Arquivo:
    """Um ``open`` de verdade com o ``write`` mais lento, do jeito de um disco cheio."""

    def __init__(self, real: Any, ao_escrever: Callable[[], None]) -> None:
        self.real = real
        self.ao_escrever = ao_escrever

    def __enter__(self) -> _Arquivo:
        return self

    def __exit__(self, *_: object) -> None:
        self.real.close()

    def write(self, dados: bytes) -> int:
        self.ao_escrever()
        return self.real.write(dados)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Callable[[], None]]]:
    """Por nome de pasta, o que o ``write`` do diário faz antes de escrever."""
    atrasos: dict[str, Callable[[], None]] = {}
    abrir = Path.open

    def _open(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        real = abrir(self, mode, *a, **k)
        atraso = atrasos.get(self.parent.name)
        return _Arquivo(real, atraso) if atraso is not None and mode == "ab" else real

    monkeypatch.setattr(Path, "open", _open)
    yield atrasos


async def _tique(furos: list[float], fim: asyncio.Event) -> None:
    antes = time.monotonic()
    while not fim.is_set():
        await asyncio.sleep(0.005)
        agora = time.monotonic()
        furos.append(agora - antes)
        antes = agora


def _diario(tmp_path: Path, nome: str = "uma") -> Path:
    pasta = tmp_path / nome
    pasta.mkdir(exist_ok=True)
    return pasta / "diario.log"


def _textos(diario: Path) -> list[str]:
    return [linha[20:] for linha in diario.read_text(encoding="utf-8").splitlines()]


def _esperar_o_fio(teto: float = 5.0) -> None:
    prazo = time.monotonic() + teto
    while any(f.name.startswith("mods-diario-") for f in threading.enumerate()):
        assert time.monotonic() < prazo, "o escritor do diário não saiu"
        time.sleep(0.01)


def test_o_write_de_2_s_nao_para_o_laco_nem_o_cano(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 5.0)
    disco["uma"] = lambda: time.sleep(2.0)
    diario = _diario(tmp_path)
    furos: list[float] = []

    async def corrida() -> tuple[float, int]:
        fim = asyncio.Event()
        tique = asyncio.create_task(_tique(furos, fim))
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diario))
        t0 = time.monotonic()
        for i in range(40):
            leitor.feed_data(f"linha {i}\n".encode())
            await asyncio.sleep(0.01)
        no_cano = len(leitor._buffer)
        leitor.feed_eof()
        gasto = time.monotonic() - t0
        await copia
        fim.set()
        await tique
        return gasto, no_cano

    gasto, no_cano = asyncio.run(corrida())
    assert no_cano == 0, "o cano parou de ser lido enquanto o disco escrevia"
    assert gasto < 1.5, gasto
    assert max(furos) < _TETO_DO_FURO_S, f"o laço parou {max(furos):.3f} s"
    assert _textos(diario) == [f"linha {i}" for i in range(40)]


def test_o_processo_que_fala_muito_nao_trava_no_print(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cano de verdade: 1 MiB passa do que o kernel segura, e o ``print`` só volta lido."""
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 5.0)
    so_o_primeiro = iter([2.0])
    disco["uma"] = lambda: time.sleep(next(so_o_primeiro, 0.0))
    diario = _diario(tmp_path)
    fala = "for i in range(20000):\n    print('x' * 50, i, flush=True)\n"

    async def corrida() -> float:
        processo = await asyncio.create_subprocess_exec(
            sys.executable, "-S", "-c", fala, stdout=asyncio.subprocess.PIPE)
        assert processo.stdout is not None
        copia = asyncio.create_task(
            supervisor_mod._copiar_para_o_diario(processo.stdout, diario))
        t0 = time.monotonic()
        await processo.wait()
        gasto = time.monotonic() - t0
        await copia
        return gasto

    gasto = asyncio.run(corrida())
    assert gasto < 1.9, f"o processo ficou {gasto:.2f} s preso no print"
    assert _textos(diario)[-1].endswith(" 19999")


def test_a_hora_de_cada_linha_e_a_da_chegada(
    tmp_path: Path, disco: dict[str, Callable[[], None]],
) -> None:
    disco["uma"] = lambda: time.sleep(0.2)
    diario = _diario(tmp_path)
    horas = iter(time.strptime(f"2026-11-06 10:00:0{i}", "%Y-%m-%d %H:%M:%S") for i in range(5))

    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(
            leitor, diario, relogio=lambda: next(horas)))
        for i in range(3):
            leitor.feed_data(f"linha {i}\n".encode())
            await asyncio.sleep(0.02)
        leitor.feed_eof()
        await copia

    asyncio.run(corrida())
    assert diario.read_text(encoding="utf-8").splitlines() == [
        f"2026-11-06 10:00:0{i} linha {i}" for i in range(3)]


def test_a_fila_tem_teto_e_o_diario_conta_quantas_sairam(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    teto = 4096
    monkeypatch.setattr(supervisor_mod, "TETO_DO_DIARIO_BYTES", teto)
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 5.0)
    solta = threading.Event()
    disco["uma"] = lambda: solta.wait(5.0) and None
    diario = _diario(tmp_path)
    total = 200

    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diario))
        await asyncio.sleep(0.01)
        leitor.feed_data(b"a primeira\n")
        await asyncio.sleep(0.05)
        for i in range(total):
            leitor.feed_data(f"{i:04d} ".encode() + b"." * 94 + b"\n")
            await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        solta.set()
        leitor.feed_eof()
        await copia

    asyncio.run(corrida())
    linhas = _textos(diario)
    assert linhas[0] == "a primeira", linhas[:2]
    assert linhas[1].startswith("("), linhas[:3]
    numeros = [int(x[:4]) for x in linhas[2:]]
    perdidas = total - len(numeros)
    assert perdidas > 0
    assert linhas[1] == f"({perdidas} linhas saíram: o disco não acompanhou)"
    assert numeros == list(range(perdidas, total)), "saiu outra além da mais velha"
    assert not linhas[-1].startswith("("), "a tela mostraria a conta como a última linha"
    assert diario.stat().st_size <= teto


def test_o_disco_que_recusa_vai_ao_log_uma_vez_e_o_cano_segue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    avisos: list[str] = []
    monkeypatch.setattr(supervisor_mod.logger, "warning",
                        lambda nome, **_k: avisos.append(nome))
    pasta = tmp_path / "e-um-arquivo"
    pasta.write_text("não é pasta")

    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(
            supervisor_mod._copiar_para_o_diario(leitor, pasta / "diario.log"))
        for i in range(5):
            leitor.feed_data(f"linha {i}\n".encode())
            await asyncio.sleep(0.01)
        leitor.feed_eof()
        await copia

    asyncio.run(corrida())
    assert avisos == ["mods_diario_recusado"]


def test_cancelar_a_copia_escoa_a_fila(
    tmp_path: Path, disco: dict[str, Callable[[], None]],
) -> None:
    disco["uma"] = lambda: time.sleep(0.1)
    diario = _diario(tmp_path)

    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diario))
        for pedaco in (b"primeira\n", b"segunda\n", b"sem quebra"):
            leitor.feed_data(pedaco)
            await asyncio.sleep(0.01)
        copia.cancel()
        with pytest.raises(asyncio.CancelledError):
            await copia

    asyncio.run(corrida())
    assert _textos(diario) == ["primeira", "segunda", "sem quebra"]


def test_esvaziar_volta_so_com_a_fila_vazia(
    tmp_path: Path, disco: dict[str, Callable[[], None]],
) -> None:
    disco["uma"] = lambda: time.sleep(0.3)
    diario = _diario(tmp_path)

    async def corrida() -> list[str]:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diario))
        leitor.feed_data(b"primeira\n")
        await asyncio.sleep(0.01)
        leitor.feed_data(b"segunda\n")
        await asyncio.sleep(0.01)
        leitor.feed_eof()
        await supervisor_mod._esvaziar_a_copia(copia, supervisor_mod.ESPERA_DO_DIARIO_S)
        return _textos(diario)

    assert asyncio.run(corrida()) == ["primeira", "segunda"]


def test_esvaziar_volta_no_prazo_e_o_escritor_termina_sozinho(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 0.1)
    disco["uma"] = lambda: time.sleep(0.8)
    diario = _diario(tmp_path)

    async def corrida() -> float:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diario))
        leitor.feed_data(b"primeira\n")
        await asyncio.sleep(0.01)
        leitor.feed_data(b"segunda\n")
        await asyncio.sleep(0.01)
        t0 = time.monotonic()
        await supervisor_mod._esvaziar_a_copia(copia, 0.1)
        return time.monotonic() - t0

    gasto = asyncio.run(corrida())
    assert gasto < 0.6, gasto
    _esperar_o_fio()
    assert _textos(diario) == ["primeira", "segunda"]


def test_a_reabertura_nao_escreve_junto_com_o_escritor_que_sobrou(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A extensão caiu com o disco preso e reabriu: o diário tem um escritor por vez."""
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 0.05)
    diario = _diario(tmp_path)
    dentro = [0]
    pico = [0]
    conta = threading.Lock()

    def lento() -> None:
        with conta:
            dentro[0] += 1
            pico[0] = max(pico[0], dentro[0])
        time.sleep(0.2)
        with conta:
            dentro[0] -= 1

    disco["uma"] = lento

    async def abrir_e_cair(texto: bytes) -> None:
        leitor = asyncio.StreamReader()
        leitor.feed_data(texto)
        leitor.feed_eof()
        await supervisor_mod._copiar_para_o_diario(leitor, diario)

    async def corrida() -> None:
        await abrir_e_cair(b"da primeira abertura\n")
        await abrir_e_cair(b"da segunda abertura\n")

    asyncio.run(corrida())
    _esperar_o_fio()
    assert pico[0] == 1, "dois escritores no mesmo diário ao mesmo tempo"
    assert sorted(_textos(diario)) == ["da primeira abertura", "da segunda abertura"]


@pytest.mark.parametrize("falando", [1, 2, 3, 4])
def test_as_extensoes_falando_juntas_nao_se_misturam(
    tmp_path: Path, disco: dict[str, Callable[[], None]], monkeypatch: pytest.MonkeyPatch,
    falando: int,
) -> None:
    """O diário não olha controle, transporte nem modo: conta quem fala, de uma a quatro."""
    monkeypatch.setattr(supervisor_mod, "ESPERA_DO_DIARIO_S", 5.0)
    nomes = [f"ext{i}" for i in range(falando)]
    for nome in nomes[:1]:
        disco[nome] = lambda: time.sleep(0.5)
    diarios = {nome: _diario(tmp_path, nome) for nome in nomes}
    furos: list[float] = []

    async def fala(nome: str) -> None:
        leitor = asyncio.StreamReader()
        copia = asyncio.create_task(supervisor_mod._copiar_para_o_diario(leitor, diarios[nome]))
        for i in range(30):
            leitor.feed_data(f"{nome} {i}\n".encode())
            await asyncio.sleep(0.005)
        leitor.feed_eof()
        await copia

    async def corrida() -> None:
        fim = asyncio.Event()
        tique = asyncio.create_task(_tique(furos, fim))
        await asyncio.gather(*(fala(nome) for nome in nomes))
        fim.set()
        await tique

    asyncio.run(corrida())
    assert max(furos) < _TETO_DO_FURO_S, f"o laço parou {max(furos):.3f} s"
    for nome, diario in diarios.items():
        assert _textos(diario) == [f"{nome} {i}" for i in range(30)]
