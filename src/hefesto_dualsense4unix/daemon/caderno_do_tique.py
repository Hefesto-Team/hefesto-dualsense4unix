"""O caderno do tique: as portas do laço leem memória, e o disco fica com um fio próprio."""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TETO_DA_ESPERA_S = 1.0


@dataclass
class _Porta:
    pergunta: Hashable
    ler: Callable[[], Any]
    periodo_s: float
    resposta: Any
    lida_em: float = float("-inf")
    em_aberto: bool = True
    chegou: bool = False


class CadernoDoTique:
    """O fio que relê cada porta no período próprio; a pergunta nova acorda o fio na hora.

    Até a leitura voltar, a porta responde o que tinha. A leitura que falha mantém a resposta de
    antes, e um disco preso atrasa só o caderno: o laço segue na memória.
    """

    def __init__(self, laco: asyncio.AbstractEventLoop) -> None:
        self._laco = laco
        self._portas: dict[str, _Porta] = {}
        self._acordar = threading.Event()
        self._fio = threading.Thread(
            target=self._ler_sempre, name="hefesto-caderno-do-tique", daemon=True
        )
        self._fio.start()

    def atende_aqui(self) -> bool:
        """Quem pergunta está no laço deste caderno, e o fio segue lendo?"""
        try:
            return asyncio.get_running_loop() is self._laco and self._fio.is_alive()
        except RuntimeError:
            return False

    def resposta(
        self, porta: str, pergunta: Hashable, ler: Callable[[], Any], periodo_s: float, vazio: Any,
    ) -> Any:
        """A última resposta da `porta`, ou `vazio` antes da primeira."""
        atual = self._portas.get(porta)
        if atual is None:
            self._portas[porta] = _Porta(pergunta, ler, periodo_s, vazio)
            self._acordar.set()
            return vazio
        atual.ler = ler
        if atual.pergunta != pergunta:
            atual.pergunta, atual.lida_em, atual.em_aberto = pergunta, float("-inf"), True
            self._acordar.set()
        return atual.resposta

    def respondeu(self, porta: str) -> bool:
        """A pergunta nova da `porta` acabou de ter resposta? Diz uma vez só."""
        atual = self._portas.get(porta)
        if atual is None or not atual.chegou:
            return False
        atual.chegou = False
        return True

    def _ler_sempre(self) -> None:
        while not self._laco.is_closed():
            self._acordar.clear()
            for porta in list(self._portas.values()):
                if time.monotonic() - porta.lida_em >= porta.periodo_s:
                    self._ler(porta)
            self._acordar.wait(self._a_espera())

    def _a_espera(self) -> float:
        agora = time.monotonic()
        faltam = [p.lida_em + p.periodo_s - agora for p in list(self._portas.values())]
        return max(0.0, min([TETO_DA_ESPERA_S, *faltam]))

    @staticmethod
    def _ler(porta: _Porta) -> None:
        pergunta, ler = porta.pergunta, porta.ler
        try:
            resposta = ler()
        except Exception:
            logger.debug("caderno_do_tique_leitura_falhou", exc_info=True)
            porta.lida_em = time.monotonic()
            return
        if porta.pergunta == pergunta:
            porta.resposta = resposta
            porta.lida_em = time.monotonic()
            porta.chegou, porta.em_aberto = porta.chegou or porta.em_aberto, False


def no_caderno(
    daemon: Any,
    porta: str,
    pergunta: Hashable,
    ler: Callable[[], Any],
    *,
    periodo_s: float,
    vazio: Any = None,
) -> Any:
    """A resposta da `porta` para o tique. Sem laço rodando não há entrada a segurar: lê na hora."""
    try:
        laco = asyncio.get_running_loop()
    except RuntimeError:
        return ler()
    caderno = getattr(daemon, "_caderno_do_tique", None)
    if not (isinstance(caderno, CadernoDoTique) and caderno.atende_aqui()):
        caderno = CadernoDoTique(laco)
        daemon._caderno_do_tique = caderno
    return caderno.resposta(porta, pergunta, ler, periodo_s, vazio)


def a_resposta_chegou(daemon: Any, porta: str) -> bool:
    """A pergunta nova da `porta` foi respondida? A porta relê agora, sem esperar o período."""
    caderno = getattr(daemon, "_caderno_do_tique", None)
    return isinstance(caderno, CadernoDoTique) and caderno.respondeu(porta)


__all__ = ["CadernoDoTique", "a_resposta_chegou", "no_caderno"]
