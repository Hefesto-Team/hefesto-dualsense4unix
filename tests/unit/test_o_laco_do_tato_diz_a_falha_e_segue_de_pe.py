"""O laço do tato e o da telemetria dizem a falha e seguem de pé.

Cada passo do laço do tato (a volta dos acessórios, o tique do passo, a fonte de fora, a pergunta
do repouso) roda sob o seu próprio ``try``: a falha que se repete diz uma linha de aviso por
minuto, com a pilha e a conta das repetições, e o laço segue com os outros passos, para toda
extensão e controle. Os meus toques dizem a falha do mesmo jeito. A telemetria abre a porta com o
``socket()`` dentro do ``try``, tenta de novo a cada 5 s, diz a borda uma vez e põe o motivo no
estado; a volta do laço da telemetria também não termina calada.

MORDIDAS: sem o ``seguro`` da fonte de fora a tarefa termina; sem o ``AvisoPorMinuto`` no tique
cada falha vira uma linha; sem o recuo da abertura a porta ocupada recebe uma tentativa por volta;
sem o ``try`` da volta da telemetria a tarefa termina; sem o ``socket()`` dentro do ``try`` o erro
de criação escapa.
"""
from __future__ import annotations

import asyncio
import socket
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon.subsystems import meus_toques as mt
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems import telemetria_do_jogo as tj

UNIQS = tuple(f"aa:bb:cc:00:00:{n:02x}" for n in (0x71, 0x72, 0x73, 0x74))


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _avisos(diario: list[dict[str, Any]], evento: str) -> list[dict[str, Any]]:
    return [e for e in diario if e["event"] == evento and e["log_level"] == "warning"]


def test_o_aviso_diz_uma_linha_por_minuto_e_conta_as_repeticoes() -> None:
    relogio = _Relogio()
    aviso = tv.AvisoPorMinuto(relogio)
    with capture_logs() as diario:
        for _ in range(120):
            relogio.agora += 1.0
            try:
                raise ValueError("falha")
            except ValueError as falha:
                aviso.dizer("tato_x_falhou", falha)
        try:
            raise KeyError("outra")
        except KeyError as falha:
            aviso.dizer("tato_x_falhou", falha)
    linhas = _avisos(diario, "tato_x_falhou")
    assert len(linhas) == 3, f"a falha repetida disse {len(linhas)} linhas em 120 s"
    assert [linha["repetidas"] for linha in linhas] == [0, 59, 0]


async def _laco_com(
    monkeypatch: pytest.MonkeyPatch, motor: tv.TatoVivo, voltas: int,
) -> tuple[list[float], asyncio.Task[None], asyncio.Event]:
    tiques: list[float] = []
    monkeypatch.setattr(tv.Passo, "ocioso", lambda _p: False)
    monkeypatch.setattr(
        tv.Passo, "__call__", lambda _p, agora: tiques.append(agora) or 0)
    parar = asyncio.Event()
    daemon = SimpleNamespace(_is_stopping=parar.is_set, bus=None)
    motor.ouvido = SimpleNamespace(parar=lambda: None)
    tarefa = asyncio.create_task(tv.tato_vivo_loop(daemon, motor))
    for _ in range(2000):
        if len(tiques) >= voltas:
            break
        await asyncio.sleep(0.005)
    return tiques, tarefa, parar


def test_a_fonte_de_fora_que_levanta_uma_vez_nao_derruba_o_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def corrida() -> tuple[int, bool]:
        motor = tv.TatoVivo([])
        chamadas = {"n": 0}
        original = motor.de_fora.andar

        def andar(agora: float) -> int:
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise RuntimeError("falha de uma extensão")
            return original(agora)

        monkeypatch.setattr(motor.de_fora, "andar", andar)
        tiques, tarefa, parar = await _laco_com(monkeypatch, motor, 40)
        vivo = not tarefa.done()
        antes = len(tiques)
        await asyncio.sleep(0.2)
        parar.set()
        await asyncio.wait_for(tarefa, 3.0)
        return len(tiques) - antes, vivo

    with capture_logs() as diario:
        depois, vivo = asyncio.run(corrida())
    assert vivo, "a tarefa do tato terminou calada com a falha da fonte de fora"
    assert depois >= 3, "o laço parou de andar depois da falha"
    linhas = _avisos(diario, "tato_vivo_laco_de_fora_falhou")
    assert len(linhas) == 1 and linhas[0]["exc_info"], "a falha não deixou a linha com a pilha"


def test_o_tique_que_levanta_sempre_diz_uma_linha_por_minuto_e_o_laco_segue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = _Relogio()
    motor = tv.TatoVivo([])
    passo = tv.Passo(SimpleNamespace(bus=None), motor)
    passo.aviso = tv.AvisoPorMinuto(relogio)

    def quebrar(_agora: float) -> int:
        raise RuntimeError("o tique quebra sempre")

    monkeypatch.setattr(tv.Passo, "__call__", lambda _p, agora: quebrar(agora))
    with capture_logs() as diario:
        for _ in range(120):
            relogio.agora += 1.0
            assert passo.tique_do_laco(relogio.agora) == 0
    linhas = _avisos(diario, "tato_vivo_tique_falhou")
    assert len(linhas) == 2, f"o tique que levanta sempre disse {len(linhas)} linhas em 120 s"
    assert linhas[0]["exc_info"]


def test_o_laco_real_com_o_tique_que_levanta_sempre_segue_de_pe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def corrida() -> tuple[int, bool]:
        motor = tv.TatoVivo([])
        chamadas = {"n": 0}

        def quebrar(_p: Any, _agora: float) -> int:
            chamadas["n"] += 1
            raise RuntimeError("o tique quebra sempre")

        monkeypatch.setattr(tv.Passo, "__call__", quebrar)
        monkeypatch.setattr(tv.Passo, "ocioso", lambda _p: False)
        parar = asyncio.Event()
        motor.ouvido = SimpleNamespace(parar=lambda: None)
        tarefa = asyncio.create_task(
            tv.tato_vivo_loop(SimpleNamespace(_is_stopping=parar.is_set, bus=None), motor))
        await asyncio.sleep(0.5)
        vivo = not tarefa.done()
        parar.set()
        await asyncio.wait_for(tarefa, 3.0)
        return chamadas["n"], vivo

    with capture_logs() as diario:
        chamadas, vivo = asyncio.run(corrida())
    assert vivo and chamadas >= 10, f"o laço rodou o tique {chamadas} vezes"
    linhas = _avisos(diario, "tato_vivo_tique_falhou")
    assert len(linhas) == 1, f"{len(linhas)} linhas: uma por tique, não uma por minuto"


def test_os_meus_toques_que_falham_dizem_uma_linha_por_minuto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = _Relogio()
    monkeypatch.setattr(mt, "_AVISO", tv.AvisoPorMinuto(relogio))
    meus = mt.meus_toques_de_producao(SimpleNamespace(bus=None))

    def quebrar(_entrada: Any, _agora: float) -> None:
        raise RuntimeError("o toque quebra")

    monkeypatch.setattr(meus, "_andar", quebrar)
    entradas = [SimpleNamespace(uniq=u) for u in UNIQS]
    with capture_logs() as diario:
        for _ in range(60):
            relogio.agora += 1.0
            meus.tique(entradas, relogio.agora)
    linhas = _avisos(diario, "meus_toques_tique_falhou")
    assert len(linhas) == 1, f"os meus toques disseram {len(linhas)} linhas em 60 s"


@pytest.fixture
def porta_ocupada() -> Any:
    ocupante = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ocupante.bind((tj.ENDERECO, 0))
    try:
        yield ocupante.getsockname()[1]
    finally:
        ocupante.close()


def test_a_porta_ocupada_tenta_de_5_em_5_s_diz_a_borda_uma_vez_e_a_solta_abre(
    porta_ocupada: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    tel = tj.TelemetriaDoJogo(porta=porta_ocupada)
    tentativas: list[int] = []
    criar = socket.socket

    def contar(*args: Any, **kwargs: Any) -> socket.socket:
        tentativas.append(1)
        return criar(*args, **kwargs)

    monkeypatch.setattr(tj.socket, "socket", contar)
    with capture_logs() as diario:
        for volta in range(120):
            assert tel.andar(float(volta) / 60.0 * 1.0, "corrida") == 0
    assert len(tentativas) == 1, f"{len(tentativas)} tentativas de bind em 120 voltas de 60 Hz"
    assert len(_avisos(diario, "telemetria_porta_ocupada")) == 1
    assert tel.estado()["motivo"] == "OSError"
    assert not tel.aberta
    for agora in (3.0, 7.0, 10.0, 13.0, 19.0):
        tel.andar(agora, "corrida")
    assert len(tentativas) == 4, "a porta ocupada não voltou a tentar a cada 5 s"
    assert len(_avisos(diario, "telemetria_porta_ocupada")) == 1, "a borda saiu mais de uma vez"
    monkeypatch.undo()
    tel.porta = 0
    assert tel.andar(30.0, "corrida") == 0
    assert tel.aberta and tel.estado()["motivo"] is None
    tel.fechar()


def test_o_socket_que_nao_se_cria_nao_escapa_da_abertura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def sem_socket(*_a: Any, **_k: Any) -> socket.socket:
        raise OSError(24, "sem descritores")

    monkeypatch.setattr(tj.socket, "socket", sem_socket)
    tel = tj.TelemetriaDoJogo()
    assert tel.abrir(1.0) is False
    assert tel.estado()["motivo"] == "OSError"


def test_a_volta_da_telemetria_que_levanta_nao_termina_a_tarefa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def corrida() -> tuple[int, bool]:
        tel = tj.TelemetriaDoJogo()
        chamadas = {"n": 0}

        def andar(_agora: float, _estilo: Any) -> int:
            chamadas["n"] += 1
            raise RuntimeError("a volta quebra sempre")

        monkeypatch.setattr(tel, "andar", andar)
        monkeypatch.setattr(tj._tv, "estilo_ativo", lambda _d: "corrida")
        parar = asyncio.Event()
        tarefa = asyncio.create_task(
            tj.telemetria_loop(SimpleNamespace(_is_stopping=parar.is_set), tel))
        await asyncio.sleep(0.3)
        vivo = not tarefa.done()
        parar.set()
        await asyncio.wait_for(tarefa, 3.0)
        return chamadas["n"], vivo

    with capture_logs() as diario:
        chamadas, vivo = asyncio.run(corrida())
    assert vivo, "a tarefa da telemetria terminou calada"
    assert chamadas >= 5
    assert len(_avisos(diario, "telemetria_laco_falhou")) == 1
