"""O laço parado se denuncia — O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01, cura 6.

Em 30/09/2026 o laço do serviço parou 3 min 30 s calado: nenhuma linha no
diário, a fila do soquete cheia, e só o SIGKILL do install o tirou dali. A
vigia (``daemon/subsystems/vigia_do_laco.py``) escreve ``laco_parado``, a pilha
de todos os fios e ``laco_voltou``.

Cada caso roda num PROCESSO FILHO, com a vigia de 1 s de limite em volta de
uma corrotina que para o laço de verdade: o ``faulthandler`` é um só por
processo, e a régua não arma o relógio de C no processo da suíte. Nada lê a
saída da própria vigia por dentro: a régua lê o ``stderr`` do filho, que é o
que o ``journalctl`` do serviço lê.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time

import pytest

#: O começo de todo filho: o diário no ``stderr`` (como no serviço) e a vigia.
COMECO = textwrap.dedent("""
    import asyncio, os, re, signal, sys, time
    from hefesto_dualsense4unix.utils.logging_config import configure_logging
    configure_logging()
    from hefesto_dualsense4unix.daemon.subsystems.vigia_do_laco import vigiado

    def marca(texto):
        os.write(2, ("@@ " + texto + "\\n").encode())
""")


def _filho(corpo: str, *, prazo_s: float = 90.0) -> str:
    """Roda ``corpo`` num filho e devolve o ``stderr`` dele."""
    feito = subprocess.run([sys.executable, "-c", COMECO + textwrap.dedent(corpo)],
                           capture_output=True, text=True, timeout=prazo_s,
                           env={**os.environ, "PYTHONUNBUFFERED": "1"}, check=False)
    assert feito.returncode == 0, feito.stderr[-3000:]
    return feito.stderr


def _pilhas(stderr: str) -> int:
    """Quantas vezes o relógio de C escreveu a pilha (``Timeout (0:00:01)!``)."""
    return stderr.count("Timeout (")


def test_o_laco_parado_sem_o_gil_diz_onde_uma_vez_e_diz_que_voltou() -> None:
    """Uma corrotina que dorme 3 s sem devolver o laço (o GIL solto): sai
    ``laco_parado`` UMA vez, a pilha com o nome dela UMA vez, e depois
    ``laco_voltou``.

    MORDIDA: tire o ``dump_traceback_later`` do ``_armar`` — a pilha some.
    """
    saida = _filho("""
        async def a_corrotina_que_dorme_no_laco():
            await asyncio.sleep(1.5)
            time.sleep(3)
            await asyncio.sleep(1.5)

        asyncio.run(vigiado(a_corrotina_que_dorme_no_laco(), limite_s=1.0, passo_s=0.2))
    """)
    assert saida.count("laco_parado") == 1, saida
    assert _pilhas(saida) == 1, saida
    assert "a_corrotina_que_dorme_no_laco" in saida
    assert saida.count("laco_voltou") == 1, saida
    assert saida.index("laco_parado") < saida.index("laco_voltou")


def test_o_laco_parado_com_o_gil_preso_ainda_deixa_a_pilha() -> None:
    """Uma corrotina presa ~3 s numa chamada em C que segura o GIL (uma regex
    de retrocesso catastrófico, calibrada aqui): o fio de Python não roda, e a
    pilha sai do relógio de C — ANTES de a regex acabar.

    MORDIDA: tire o ``dump_traceback_later`` do ``_armar`` — a pilha some.
    """
    saida = _filho("""
        def tempo_da_regex(n):
            comeco = time.perf_counter()
            re.match(r"(a+)+$", "a" * n + "b")
            return time.perf_counter() - comeco

        n = 16
        while tempo_da_regex(n) < 0.2:
            n += 1
        while tempo_da_regex(n) < 0.4 and n < 40:
            n += 1
        # cada letra a mais dobra o tempo: daqui a ~3 s
        n += 3

        async def a_corrotina_que_segura_o_gil():
            await asyncio.sleep(1.5)
            marca("a regex começou")
            re.match(r"(a+)+$", "a" * n + "b")
            marca("a regex acabou")
            await asyncio.sleep(1.5)

        asyncio.run(vigiado(a_corrotina_que_segura_o_gil(), limite_s=1.0, passo_s=0.2))
    """, prazo_s=180.0)
    assert _pilhas(saida) == 1, saida
    comeco, pilha, fim = (saida.index("@@ a regex começou"), saida.index("Timeout ("),
                          saida.index("@@ a regex acabou"))
    assert comeco < pilha < fim, "a pilha não saiu com o laço parado"
    assert "a_corrotina_que_segura_o_gil" in saida[pilha:fim]


def test_o_laco_sao_nao_acusa_nada() -> None:
    """Trinta segundos de laço são, com tarefas de 10 ms de CPU: zero
    ``laco_parado`` e zero pilha.

    MORDIDAS, uma por vez: tire a batida (o ``_batida`` que não anda — a vigia
    acusa o laço são); tire o rearmar do ``_bater`` (a pilha da primeira armada
    sai no laço são).
    """
    saida = _filho("""
        async def trabalho(fim):
            while time.monotonic() < fim:
                comeco = time.perf_counter()
                while time.perf_counter() - comeco < 0.010:
                    pass
                await asyncio.sleep(0)

        async def o_laco_sao():
            fim = time.monotonic() + 30.0
            await asyncio.gather(*(trabalho(fim) for _ in range(4)))

        asyncio.run(vigiado(o_laco_sao(), limite_s=1.0, passo_s=0.2))
        marca("acabou")
    """)
    assert "@@ acabou" in saida
    assert "laco_parado" not in saida, saida
    assert _pilhas(saida) == 0, saida


def test_o_sigterm_continua_parando_o_servico() -> None:
    """O serviço de mentira atende o SIGTERM pelo laço (como o ``lifecycle``)
    e sai em menos de 2 s com a vigia ligada: o fio dela não segura a saída."""
    codigo = COMECO + textwrap.dedent("""
        async def o_servico():
            parar = asyncio.Event()
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, parar.set)
            marca("pronto")
            await parar.wait()

        asyncio.run(vigiado(o_servico(), limite_s=1.0, passo_s=0.2))
        marca("saiu")
    """)
    filho = subprocess.Popen([sys.executable, "-c", codigo], stderr=subprocess.PIPE,
                             text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    try:
        assert filho.stderr is not None
        linha = ""
        prazo = time.monotonic() + 60.0
        while "@@ pronto" not in linha and time.monotonic() < prazo:
            linha = filho.stderr.readline()
            if not linha and filho.poll() is not None:
                break
        assert "@@ pronto" in linha, "o serviço de mentira não subiu"
        time.sleep(1.5)  # a vigia batendo
        comeco = time.monotonic()
        filho.send_signal(signal.SIGTERM)  # o PID é o do filho que esta régua abriu
        filho.wait(timeout=10)
        demorou = time.monotonic() - comeco
        resto = filho.stderr.read()
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait()
    assert filho.returncode == 0, resto
    assert "@@ saiu" in resto
    assert demorou < 2.0, demorou


@pytest.mark.parametrize("passo_s", [0.2, 1.0])
def test_o_olho_diz_a_parada_uma_vez_pelo_relogio_dado(passo_s: float) -> None:
    """O olho, sem laço nem fio: com o relógio dado, a parada sai uma vez por
    parada, e a volta, uma vez — o ``passo_s`` não muda a conta."""
    from hefesto_dualsense4unix.daemon.subsystems.vigia_do_laco import VigiaDoLaco

    agora = [100.0]
    ditos: list[tuple[str, dict[str, object]]] = []
    vigia = VigiaDoLaco(limite_s=10.0, passo_s=passo_s, relogio=lambda: agora[0],
                        avisar=lambda evento, **campos: ditos.append((evento, campos)))
    for _ in range(3):
        agora[0] += 11.0
        vigia.olhar()
    vigia._batida = agora[0]
    vigia.olhar()
    vigia.olhar()
    assert ditos == [("laco_parado", {"segundos": 11}), ("laco_voltou", {"parado_s": 33.0})]
