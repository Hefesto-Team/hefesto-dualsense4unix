"""O perfil de evento entra quando o evento chega.

OS-EVENTOS-DO-PERFIL-ENTRAM-PELO-QUE-O-DAEMON-JA-SABE-01: «Controle conectado» entra ao
`controller.connected` (cabo ou rádio); «Programa aberto» é o `match` pelo autoswitch; «Meu
comando» entra quando o comando dela passa a sair com 0 (sem shell, a cada 15 s, prazo de 5 s).
Cena, Menu, Pausa e Hora marcada gravam sem motor: falta a fonte. Nenhum evento tira o perfil de
um jogo em cena, a escolha manual dos últimos 30 s nem o Modo Nativo; o motor sobe depois do
controle, e a conexão do boot é a da sessão restaurada.
"""
from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import shlex
import signal
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

INTERVALO_DO_COMANDO_S = 15.0
PRAZO_DO_COMANDO_S = 5.0
CONTROLE_CONECTADO = "controle_conectado"
MEU_COMANDO = "meu_comando"


def perfis_do_momento(momento: str, perfis: Iterable[Any]) -> list[Any]:
    """Os perfis de evento deste momento, do que vale primeiro (prioridade, depois o nome)."""
    achados = [p for p in perfis
               if getattr(p, "alvo", None) == "eventos" and getattr(p, "evento", None) == momento]
    return sorted(achados, key=lambda p: (-int(getattr(p, "priority", 0) or 0), p.name))


def argv_do_comando(texto: str) -> list[str] | None:
    """O comando dela em argumentos, sem shell; `None` quando vazio ou com aspas abertas."""
    try:
        partes = shlex.split(texto or "")
    except ValueError:
        return None
    if not partes:
        return None
    if os.path.isabs(partes[0]) and partes[0].endswith(".sh"):
        return ["bash", *partes]
    return partes


async def rodar_o_comando(texto: str, prazo: float = PRAZO_DO_COMANDO_S) -> tuple[bool, str]:
    """Roda o comando uma vez: `(saiu com 0, o porquê)`. Nunca levanta."""
    argv = argv_do_comando(texto)
    if argv is None:
        return False, "comando vazio ou com aspas abertas"
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        return False, f"não abriu: {exc}"
    try:
        saida, _ = await asyncio.wait_for(proc.communicate(), prazo)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        return False, f"passou do prazo de {prazo:g} s"
    fim = (saida or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, f"saiu com {proc.returncode}: {fim[0][:200]}".rstrip(": ")


class EventosDoPerfil:
    """O motor: ouve o barramento, pergunta os comandos e ativa o perfil do evento."""

    def __init__(
        self,
        daemon: Any,
        ativar: Callable[[str], Awaitable[Any]],
        ler_perfis: Callable[[], Iterable[Any]],
        rodar: Callable[[str], Awaitable[tuple[bool, str]]] = rodar_o_comando,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._daemon = daemon
        self._ativar = ativar
        self._ler_perfis = ler_perfis
        self._rodar = rodar
        self._relogio = relogio
        #: O último resultado de cada comando: `(nome do perfil, comando) → (deu certo, porquê)`.
        self._comandos: dict[tuple[str, str], tuple[bool, str]] = {}

    def _recusa(self) -> str | None:
        """Por que um evento não pode trocar o perfil agora, ou `None`."""
        appid = getattr(self._daemon, "appid_em_cena", None)
        if isinstance(appid, int) and not isinstance(appid, bool) and appid > 0:
            return "jogo_em_cena"
        store = getattr(self._daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            return "modo_nativo"
        trava = getattr(store, "manual_profile_lock_active", None)
        if callable(trava) and trava(self._relogio()):
            return "escolha_dela_recente"
        return None

    async def _entrar(self, perfil: Any, momento: str) -> bool:
        ativo = getattr(getattr(self._daemon, "store", None), "active_profile", None)
        if ativo == perfil.name:
            return False
        recusa = self._recusa()
        if recusa is not None:
            logger.info("perfil_de_evento_recusado", perfil=perfil.name, momento=momento,
                        porque=recusa)
            return False
        await self._ativar(perfil.name)
        logger.info("perfil_de_evento_entrou", perfil=perfil.name, momento=momento)
        return True

    async def ao_conectar(self) -> bool:
        """Um controle conectou: entra o primeiro perfil de «Controle conectado»."""
        perfis = perfis_do_momento(CONTROLE_CONECTADO, self._ler_perfis())
        return bool(perfis) and await self._entrar(perfis[0], CONTROLE_CONECTADO)

    async def ver_os_comandos(self) -> list[str]:
        """Pergunta cada «Meu comando»; entra o primeiro que PASSOU a sair com 0 (devolve quem)."""
        perfis = perfis_do_momento(MEU_COMANDO, self._ler_perfis())
        vistos: set[tuple[str, str]] = set()
        entraram: list[str] = []
        for perfil in perfis:
            chave = (perfil.name, str(getattr(perfil, "evento_comando", None) or ""))
            vistos.add(chave)
            certo, porque = await self._rodar(chave[1])
            antes = self._comandos.get(chave)
            self._comandos[chave] = (certo, porque)
            if antes is None or antes[0] != certo:
                logger.info("perfil_de_evento_comando", perfil=perfil.name, deu_certo=certo,
                            porque=porque)
            passou = certo and (antes is None or not antes[0])
            if passou and not entraram and await self._entrar(perfil, MEU_COMANDO):
                entraram.append(perfil.name)
        for chave in set(self._comandos) - vistos:
            del self._comandos[chave]
        return entraram

    async def ouvir_as_conexoes(self) -> None:
        bus = self._daemon.bus
        fila = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
        try:
            while True:
                await fila.get()
                try:
                    await self.ao_conectar()
                except Exception as exc:
                    logger.warning("perfil_de_evento_falhou", momento=CONTROLE_CONECTADO,
                                   err=str(exc))
        finally:
            bus.unsubscribe(EventTopic.CONTROLLER_CONNECTED, fila)

    async def perguntar_os_comandos(self, intervalo: float = INTERVALO_DO_COMANDO_S) -> None:
        while True:
            try:
                await self.ver_os_comandos()
            except Exception as exc:
                logger.warning("perfil_de_evento_falhou", momento=MEU_COMANDO, err=str(exc))
            await asyncio.sleep(intervalo)


def start_eventos_do_perfil(daemon: Any) -> None:
    """Sobe os dois laços; as tarefas caem com as do serviço (`tarefas` na lista de parada)."""
    from hefesto_dualsense4unix.profiles.loader import perfis_para_consulta
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    manager = gerente_do_daemon(daemon, store=daemon.store)

    async def ativar(nome: str) -> Any:
        return await daemon._run_blocking(
            functools.partial(manager.activate, nome, origin="autoswitch"))

    motor = EventosDoPerfil(daemon, ativar, perfis_para_consulta)
    daemon._eventos_do_perfil = motor
    for laco, nome in ((motor.ouvir_as_conexoes(), "eventos_do_perfil_conexoes"),
                       (motor.perguntar_os_comandos(), "eventos_do_perfil_comandos")):
        daemon._tasks.append(asyncio.create_task(laco, name=nome))
    logger.info("eventos_do_perfil_iniciado")


__all__ = [
    "INTERVALO_DO_COMANDO_S",
    "PRAZO_DO_COMANDO_S",
    "EventosDoPerfil",
    "argv_do_comando",
    "perfis_do_momento",
    "rodar_o_comando",
    "start_eventos_do_perfil",
]
