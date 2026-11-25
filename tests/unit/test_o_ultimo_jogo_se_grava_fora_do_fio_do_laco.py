"""O último jogo se grava fora do fio do laço.

Sprint O-ULTIMO-JOGO-SE-GRAVA-FORA-DO-FIO-DO-LACO-01, decisão
D-2211-O-ULTIMO-JOGO-SE-GRAVA-FORA-DO-FIO-DO-LACO.

Medido em 22/11/2026: às 05h31 o laço do serviço parou 38,2 s dentro de
`AutoSwitcher._o_ultimo_jogo_passa_a`, em `lembrar_o_ultimo_jogo`, na escrita inteira (com
`fsync`) do `ultimo_jogo.json`, com o disco lento. O que se prova, com o `AutoSwitcher` de verdade
num laço com batimento de 10 ms e o disco de mentira dormindo no arquivo do último jogo:

1. o batimento não passa de um teto pequeno no lembrar (pelo tique inteiro) e no esquecer;
2. lembrar A, lembrar B, esquecer, lembrar C em sequência rápida termina com C no disco; lembrar
   seguido de esquecer termina sem arquivo; o esquecer de outro nome não apaga o que o lembrar
   pôs (a fila não funde pedidos de nomes diferentes);
3. quem pede fora do laço (o executor do autoswitch, o fio do perfil) espera os pedidos que o
   laço deixou na fila, e a ordem se mantém;
4. a parada do processo não perde a última gravação;
5. a gravação que falha não derruba o tique e deixa uma linha de aviso no diário.

MORDIDAS (25/11/2026): a gravação de volta ao fio do laço (`if no_fio_do_laco()` sempre falso)
reprova os dois casos do batimento; sem o `esperar_a_fila` do pedido de fora do laço reprova o caso
do executor; a fila sem ordem (chave igual em todo pedido) reprova o caso do esquecer de outro
nome; sem o `atexit` do gravador reprova a parada do processo; o aviso que volta a `debug` reprova
o caso da gravação que falha.
"""

from __future__ import annotations

import asyncio
import errno
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.utils import escrita_inteira as ei
from hefesto_dualsense4unix.utils import session
from tests.unit.test_foco_errante_01_a_janela_da_steam_nao_tira_o_perfil import (
    CLASSE_DO_JOGO,
    JANELA_DO_JOGO,
    _ensaio,
    _perfil,
    _switcher,
    perfis_isolados,  # noqa: F401
)

ARQUIVO = "ultimo_jogo.json"
DISCO_LENTO_S = 1.0
TETO_DO_BATIMENTO_S = 0.30
BATIMENTO_S = 0.010
RAIZ = Path(__file__).resolve().parents[2]


class DiscoLento:
    """O `os.replace` e o `unlink` do arquivo do último jogo dormem; os demais seguem."""

    def __init__(self, espera_s: float) -> None:
        self.espera_s = espera_s
        self.falha: OSError | None = None
        self.gravacoes = 0

    def alcanca(self, destino: Any) -> bool:
        return Path(str(destino)).name == ARQUIVO

    def esperar(self) -> None:
        time.sleep(self.espera_s)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> DiscoLento:
    d = DiscoLento(DISCO_LENTO_S)
    troca_real = os.replace
    apaga_real = Path.unlink

    def troca(origem: Any, destino: Any) -> None:
        if d.alcanca(destino):
            d.esperar()
            if d.falha is not None:
                raise d.falha
            d.gravacoes += 1
        troca_real(origem, destino)

    def apaga(self: Path, *args: Any, **kwargs: Any) -> None:
        if d.alcanca(self):
            d.esperar()
        apaga_real(self, *args, **kwargs)

    monkeypatch.setattr(os, "replace", troca)
    monkeypatch.setattr(Path, "unlink", apaga)
    yield d
    ei.esperar_a_fila(10.0)


def _os_perfis() -> list[Any]:
    return [_perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90)]


async def _com_batimento(corpo: Callable[[], Any]) -> float:
    """Roda `corpo` no fio do laço com um batimento de 10 ms; devolve a maior parada."""
    paradas: list[float] = []
    parar = asyncio.Event()

    async def bater() -> None:
        ultimo = time.perf_counter()
        while not parar.is_set():
            await asyncio.sleep(BATIMENTO_S)
            agora = time.perf_counter()
            paradas.append(agora - ultimo)
            ultimo = agora

    tarefa = asyncio.create_task(bater())
    await asyncio.sleep(0.05)
    resultado = corpo()
    if asyncio.iscoroutine(resultado):
        await resultado
    await asyncio.sleep(0.05)
    parar.set()
    await tarefa
    return max(paradas)


def _no_disco() -> str | None:
    return session._ultimo_jogo_cru()


def _esperar_a_fila() -> None:
    assert ei.esperar_a_fila(15.0), "a fila do gravador não esvaziou"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_tique_que_lembra_o_jogo_nao_espera_o_disco(disco: DiscoLento) -> None:
    """D-2211-O-ULTIMO-JOGO-SE-GRAVA-FORA-DO-FIO-DO-LACO."""
    manager, store = _ensaio(_os_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)

    def tiques() -> None:
        sw._tick(dict(JANELA_DO_JOGO), 0.0)
        sw._tick(dict(JANELA_DO_JOGO), 1.0)

    parada = asyncio.run(_com_batimento(tiques))
    assert store.active_profile == "sackboy", "premissa: o autoswitch entrou no jogo"
    assert parada < TETO_DO_BATIMENTO_S, f"o laço parou {parada:.2f} s esperando o disco"
    _esperar_a_fila()
    assert _no_disco() == "sackboy", "a gravação saiu do laço mas tem de chegar ao disco"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_esquecer_do_autoswitch_nao_espera_o_disco(disco: DiscoLento) -> None:
    manager, store = _ensaio(_os_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    disco.espera_s = 0.0
    session.lembrar_o_ultimo_jogo("sackboy")
    assert _no_disco() == "sackboy"
    sw._o_ultimo_jogo_passa_a("sackboy")
    disco.espera_s = DISCO_LENTO_S

    parada = asyncio.run(_com_batimento(lambda: sw._o_ultimo_jogo_passa_a(None)))
    assert parada < TETO_DO_BATIMENTO_S, f"o laço parou {parada:.2f} s esperando o disco"
    _esperar_a_fila()
    assert _no_disco() is None, "o esquecer saiu do laço mas tem de apagar o arquivo"


def test_a_ordem_dos_pedidos_do_laco_e_a_do_disco(disco: DiscoLento) -> None:
    disco.espera_s = 0.15

    def sequencia() -> None:
        session.lembrar_o_ultimo_jogo("jogo-a")
        session.lembrar_o_ultimo_jogo("jogo-b")
        session.esquecer_o_ultimo_jogo()
        session.lembrar_o_ultimo_jogo("jogo-c")

    asyncio.run(_com_batimento(sequencia))
    _esperar_a_fila()
    assert _no_disco() == "jogo-c"


def test_lembrar_e_esquecer_termina_sem_arquivo(disco: DiscoLento) -> None:
    disco.espera_s = 0.15

    def sequencia() -> None:
        session.lembrar_o_ultimo_jogo("jogo-a")
        session.esquecer_o_ultimo_jogo()

    asyncio.run(_com_batimento(sequencia))
    _esperar_a_fila()
    assert _no_disco() is None


def test_o_esquecer_de_outro_nome_nao_apaga_o_que_o_lembrar_pos(disco: DiscoLento) -> None:
    disco.espera_s = 0.15

    def sequencia() -> None:
        session.lembrar_o_ultimo_jogo("jogo-a")
        session.lembrar_o_ultimo_jogo("jogo-b")
        session.esquecer_o_ultimo_jogo("jogo-a")

    asyncio.run(_com_batimento(sequencia))
    _esperar_a_fila()
    assert _no_disco() == "jogo-b", "o esquecer de outro nome funde com o lembrar e o apaga"


def test_quem_pede_fora_do_laco_espera_o_que_o_laco_deixou_na_fila(disco: DiscoLento) -> None:
    disco.espera_s = 0.4

    async def principal() -> None:
        loop = asyncio.get_running_loop()
        session.lembrar_o_ultimo_jogo("jogo-a")
        await loop.run_in_executor(None, session.esquecer_o_ultimo_jogo)

    asyncio.run(principal())
    _esperar_a_fila()
    assert _no_disco() is None, "o esquecer do executor passou na frente do lembrar do laço"


def test_o_pedido_fora_de_um_laco_grava_na_hora() -> None:
    session.lembrar_o_ultimo_jogo("jogo-a")
    assert _no_disco() == "jogo-a"
    session.esquecer_o_ultimo_jogo()
    assert _no_disco() is None


def test_a_parada_do_processo_nao_perde_a_ultima_gravacao(tmp_path: Path) -> None:
    config = tmp_path / "config"
    codigo = (
        "import asyncio, os, time\n"
        "from pathlib import Path\n"
        "from hefesto_dualsense4unix.utils import session\n"
        "troca = os.replace\n"
        "def lento(origem, destino):\n"
        f"    if Path(str(destino)).name == {ARQUIVO!r}:\n"
        "        time.sleep(0.8)\n"
        "    troca(origem, destino)\n"
        "os.replace = lento\n"
        "async def principal():\n"
        "    session.lembrar_o_ultimo_jogo('jogo-final')\n"
        "asyncio.run(principal())\n"
    )
    ambiente = {
        **os.environ,
        "XDG_CONFIG_HOME": str(config),
        "PYTHONPATH": str(RAIZ / "src"),
    }
    saida = subprocess.run(
        [sys.executable, "-c", codigo], env=ambiente, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert saida.returncode == 0, saida.stderr
    gravado = list(config.rglob(ARQUIVO))
    assert len(gravado) == 1, "o processo saiu antes de a gravação pendente chegar ao disco"
    assert "jogo-final" in gravado[0].read_text(encoding="utf-8")


@pytest.mark.usefixtures("perfis_isolados")
def test_a_gravacao_que_falha_nao_derruba_o_tique_e_deixa_um_aviso(disco: DiscoLento) -> None:
    manager, store = _ensaio(_os_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    disco.espera_s = 0.0
    disco.falha = OSError(errno.ENOSPC, "disco cheio de mentira")

    def tiques() -> None:
        sw._tick(dict(JANELA_DO_JOGO), 0.0)
        sw._tick(dict(JANELA_DO_JOGO), 1.0)

    with capture_logs() as registros:
        asyncio.run(_com_batimento(tiques))
        _esperar_a_fila()
    assert store.active_profile == "sackboy", "a gravação que falha derrubou o autoswitch"
    avisos = [r for r in registros if r.get("event") == "o_ultimo_jogo_nao_gravado"]
    assert avisos, "a gravação que falhou não deixou linha no diário"
    assert avisos[0]["log_level"] == "warning"
    assert avisos[0]["perfil"] == "sackboy"
    assert _no_disco() is None
