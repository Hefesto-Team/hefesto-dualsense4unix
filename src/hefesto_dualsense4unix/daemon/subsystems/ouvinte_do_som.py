"""O servidor de som AVISA, e até hoje ninguém escutava."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.integrations import retrato_do_som
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

ESPERA_PARA_RELIGAR_S: float = 3.0

RAJADA_S: float = 0.05

EVENTOS_QUE_IMPORTAM = ("server", "sink", "source")

_TIPOS_DO_PADRAO = frozenset(
    retrato_do_som.TIPO_DO_EVENTO[e] for e in EVENTOS_QUE_IMPORTAM)


@dataclass(frozen=True)
class SomDoSistema:
    """A saída e a entrada padrão do sistema, como o servidor as diz."""

    saida: str = ""
    entrada: str = ""
    saida_nome: str = ""
    entrada_nome: str = ""

    def como_dicionario(self) -> dict[str, str]:
        return {"saida": self.saida, "entrada": self.entrada,
                "saida_nome": self.saida_nome, "entrada_nome": self.entrada_nome}


def _ambiente() -> dict[str, str]:
    """O ambiente das leituras, com o idioma preso em C. Ver o cabeçalho."""
    return {**os.environ, "LC_ALL": "C", "LANG": "C"}


async def ler_o_padrao() -> SomDoSistema:
    """A saída e a entrada padrão, com os nomes de gente — pelo RETRATO, sem `pactl`."""
    return await asyncio.to_thread(_o_padrao_do_retrato)


def _o_padrao_do_retrato() -> SomDoSistema:
    """O corpo de :func:`ler_o_padrao`, que pode bloquear. Fora do laço sempre."""
    retrato = retrato_do_som.RETRATO
    saida = retrato.padrao("sink") or ""
    entrada = retrato.padrao("source") or ""
    descricoes = retrato.descricoes()
    return SomDoSistema(
        saida=saida, entrada=entrada,
        saida_nome=descricoes.get(saida, ""),
        entrada_nome=descricoes.get(entrada, ""))


def tipo_do_evento(linha: str) -> str | None:
    """O tipo do retrato que esta linha do `subscribe` manda reler, ou `None`."""
    partes = linha.split()
    if len(partes) < 4 or partes[0] != "Event":
        return None
    return retrato_do_som.TIPO_DO_EVENTO.get(partes[3])


async def _publicar(daemon: Any, agora: SomDoSistema) -> None:
    bus = getattr(daemon, "bus", None)
    if bus is None:
        return
    publicar = getattr(bus, "publish", None)
    if publicar is None:
        return
    resultado = publicar(EventTopic.SOM_DO_SISTEMA, agora.como_dicionario())
    if asyncio.iscoroutine(resultado):
        await resultado


async def ouvinte_do_som_loop(daemon: Any) -> None:
    """Segue o `pactl subscribe`, mantém o retrato em dia e publica toda mudança de padrão.

    **O ESTADO VIVE NO DAEMON, não aqui**: `daemon.som_do_sistema` é lido pelo
    `state_full` a cada tique da janela, e guardar uma cópia neste módulo daria
    dois donos do mesmo fato.

    **A PRIMEIRA LEITURA É ANTES DE ESCUTAR QUALQUER EVENTO**, e a ordem é a
    entrega: sem ela a tela ficaria sem resposta até a primeira mudança
    acontecer — que pode ser nunca.

    **QUEM PARA O LAÇO SOLTA O RETRATO**: sem ouvinte não há evento, e uma
    foto que ninguém mantém responderia sobre o passado.
    """
    sem_pactl = False
    try:
        while True:
            if shutil.which("pactl") is None:
                if not sem_pactl:
                    sem_pactl = True
                    retrato_do_som.RETRATO.soltar()
                    logger.info("ouvinte_do_som_sem_pactl")
                await asyncio.sleep(ESPERA_PARA_RELIGAR_S)
                continue
            if sem_pactl:
                sem_pactl = False
                logger.info("ouvinte_do_som_achou_o_pactl")
            try:
                await _uma_volta(daemon)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("ouvinte_do_som_caiu", exc_info=True)
            await asyncio.sleep(ESPERA_PARA_RELIGAR_S)
    finally:
        retrato_do_som.RETRATO.soltar()


async def _carregar_o_retrato(retrato: retrato_do_som.RetratoDoSom) -> bool:
    """A leitura inteira, fora do laço de eventos. True = o retrato assumiu."""
    completo = await asyncio.to_thread(retrato.carregar)
    if completo or retrato.algum_em_dia():
        retrato.assumir(asyncio.get_running_loop())
        return True
    return False


async def _uma_volta(daemon: Any) -> None:
    """Uma sessão de `subscribe`, do início até o `pactl` morrer."""
    retrato = retrato_do_som.RETRATO
    proc = await asyncio.create_subprocess_exec(
        "pactl", "subscribe",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_ambiente())
    pendentes: set[str] = set()
    tarefas: list[asyncio.Task[None]] = []
    try:
        await _carregar_o_retrato(retrato)
        anterior = await ler_o_padrao()
        _guardar(daemon, anterior)
        await _publicar(daemon, anterior)
        logger.info("ouvinte_do_som_ligado", saida=anterior.saida,
                    entrada=anterior.entrada, retrato=retrato.vivo)

        async def aplicar() -> None:
            nonlocal anterior
            tipos = set(pendentes)
            pendentes.clear()
            tipos.update(retrato.faltando())
            await asyncio.to_thread(retrato.reler, tipos)
            if not retrato.vivo and retrato.algum_em_dia():
                retrato.assumir(asyncio.get_running_loop())
            if not tipos & _TIPOS_DO_PADRAO:
                return
            agora = await ler_o_padrao()
            if agora == anterior:
                return
            anterior = agora
            _guardar(daemon, agora)
            await _publicar(daemon, agora)
            logger.info("som_do_sistema_mudou", saida=agora.saida,
                        entrada=agora.entrada)

        async def descarregar() -> None:
            while pendentes:
                await asyncio.sleep(RAJADA_S)
                await aplicar()

        async def insistir() -> None:
            while not retrato.completo():
                await asyncio.sleep(ESPERA_PARA_RELIGAR_S)
                pendentes.update(retrato.faltando())
                await aplicar()

        if not retrato.completo():
            tarefas.append(asyncio.create_task(insistir()))
        vez: asyncio.Task[None] | None = None
        assert proc.stdout is not None
        async for bruto in proc.stdout:
            tipo = tipo_do_evento(bruto.decode("utf-8", "replace").strip())
            if tipo is None:
                continue
            pendentes.add(tipo)
            if vez is None or vez.done():
                _podar(tarefas)
                vez = asyncio.create_task(descarregar())
                tarefas.append(vez)
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
        tarefas.clear()
        if pendentes:
            await aplicar()
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
        retrato.perdeu_o_servidor()
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()


def _podar(tarefas: list[asyncio.Task[None]]) -> None:
    """Tira da lista da volta as tarefas que acabaram — e diz a falha de quem caiu."""
    vivas: list[asyncio.Task[None]] = []
    for tarefa in tarefas:
        if not tarefa.done():
            vivas.append(tarefa)
        elif not tarefa.cancelled() and tarefa.exception() is not None:
            logger.warning("ouvinte_do_som_rajada_caiu", err=str(tarefa.exception()))
    tarefas[:] = vivas


def _guardar(daemon: Any, agora: SomDoSistema) -> None:
    with contextlib.suppress(Exception):
        daemon.som_do_sistema = agora


def som_do_sistema_payload(daemon: Any) -> dict[str, str]:
    """O bloco do `state_full` — `{"saida": …, "entrada": …}`.

    Sem ouvinte de pé (daemon velho, `pactl` fora do PATH), os dois campos
    voltam vazios — que é *"não sei"*, e não *"não há"*. A tela já sabe pintar
    a diferença, e afirmar o segundo faria a pessoa parar de procurar.
    """
    guardado = getattr(daemon, "som_do_sistema", None)
    if isinstance(guardado, SomDoSistema):
        return guardado.como_dicionario()
    return SomDoSistema().como_dicionario()


def start_ouvinte_do_som(daemon: Any) -> None:
    """Sobe o laço. Idempotente do ponto de vista de quem chama."""
    tarefa = asyncio.create_task(ouvinte_do_som_loop(daemon),
                                 name="ouvinte_do_som_loop")
    daemon._tasks.append(tarefa)
    logger.info("ouvinte_do_som_iniciado")


__all__ = [
    "ESPERA_PARA_RELIGAR_S",
    "EVENTOS_QUE_IMPORTAM",
    "RAJADA_S",
    "SomDoSistema",
    "ler_o_padrao",
    "ouvinte_do_som_loop",
    "som_do_sistema_payload",
    "start_ouvinte_do_som",
    "tipo_do_evento",
]
