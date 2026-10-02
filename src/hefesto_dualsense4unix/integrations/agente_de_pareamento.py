"""agente_de_pareamento.py — o ``org.bluez.Agent1`` NOSSO (R5)."""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

from hefesto_dualsense4unix.integrations.bluez_dbus import (
    AGENTE,
    ERRO_JA_EXISTE,
    ERRO_REJEITADO,
    ESPERA_DO_BUSCTL_S,
    GERENTE_DE_AGENTES,
    RAIZ_DO_BLUEZ,
    SERVICO,
    Barramento,
    RecusaNoBarramento,
    a_suite_esta_rodando,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

CAMINHO_DO_AGENTE = "/io/github/hefesto_team/hefesto_dualsense4unix/agente"

CAPACIDADE = "NoInputNoOutput"

_XML = (
    f"<node><interface name='{AGENTE}'>"
    "<method name='Release'/>"
    "<method name='RequestPinCode'><arg type='o' direction='in'/>"
    "<arg type='s' direction='out'/></method>"
    "<method name='DisplayPinCode'><arg type='o' direction='in'/>"
    "<arg type='s' direction='in'/></method>"
    "<method name='RequestPasskey'><arg type='o' direction='in'/>"
    "<arg type='u' direction='out'/></method>"
    "<method name='DisplayPasskey'><arg type='o' direction='in'/>"
    "<arg type='u' direction='in'/><arg type='q' direction='in'/></method>"
    "<method name='RequestConfirmation'><arg type='o' direction='in'/>"
    "<arg type='u' direction='in'/></method>"
    "<method name='RequestAuthorization'><arg type='o' direction='in'/></method>"
    "<method name='AuthorizeService'><arg type='o' direction='in'/>"
    "<arg type='s' direction='in'/></method>"
    "<method name='Cancel'/>"
    "</interface></node>"
)

_ACEITA_O_ESPERADO = frozenset({"RequestConfirmation", "RequestAuthorization", "AuthorizeService"})

_PEDE_DIGITAR = frozenset({"RequestPinCode", "RequestPasskey"})

_SO_MOSTRA = frozenset({"DisplayPinCode", "DisplayPasskey"})


def _mascara(caminho: str) -> str:
    from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar

    return mascarar(caminho.rsplit("/dev_", 1)[-1].replace("_", ":"))


class AgenteDePareamento:
    """Um ``Agent1`` exportado na conexão do dono, sem virar o padrão."""

    def __init__(
        self,
        barramento: Barramento,
        dono_do_bluez: Callable[[], str],
        *,
        caminho: str = CAMINHO_DO_AGENTE,
    ) -> None:
        self._barramento = barramento
        self._dono_do_bluez = dono_do_bluez
        self.caminho = caminho
        self._tranca = threading.Lock()
        self._registrado = False
        self._esperado = ""
        self.historico: deque[tuple[str, bool]] = deque(maxlen=32)

    @property
    def registrado(self) -> bool:
        return self._registrado

    def registrar(self) -> bool:
        """Exporta o objeto e pede ``RegisterAgent`` — nunca ``RequestDefaultAgent``."""
        with self._tranca:
            if self._registrado:
                return True
            if getattr(self._barramento, "e_do_sistema", False) and a_suite_esta_rodando():
                return False
            if not self._barramento.exportar(self.caminho, _XML, self._atender):
                return False
            escrita = self._barramento.chamar(
                SERVICO,
                RAIZ_DO_BLUEZ,
                GERENTE_DE_AGENTES,
                "RegisterAgent",
                "os",
                (self.caminho, CAPACIDADE),
                espera=ESPERA_DO_BUSCTL_S,
            )
            self._registrado = escrita.feita or escrita.erro == ERRO_JA_EXISTE
            if not self._registrado:
                logger.warning("agente_proprio_nao_registrou", erro=escrita.erro)
            return self._registrado

    def desregistrar(self) -> None:
        """``UnregisterAgent`` e retira o objeto. Idempotente, nunca levanta."""
        with self._tranca:
            if self._registrado:
                self._barramento.chamar(
                    SERVICO,
                    RAIZ_DO_BLUEZ,
                    GERENTE_DE_AGENTES,
                    "UnregisterAgent",
                    "o",
                    (self.caminho,),
                    espera=ESPERA_DO_BUSCTL_S,
                )
            self._registrado = False
            with contextlib.suppress(Exception):
                self._barramento.retirar(self.caminho)

    def invalidar(self) -> None:
        """O ``bluetoothd`` saiu, e o registro saiu com ele."""
        with self._tranca:
            self._registrado = False

    @contextlib.contextmanager
    def esperando(self, caminho_do_aparelho: str) -> Iterator[None]:
        """Durante o bloco, ESTE aparelho é o que se pareia — e só ele é aceito."""
        with self._tranca:
            self._esperado = caminho_do_aparelho
        try:
            yield
        finally:
            with self._tranca:
                self._esperado = ""

    def _atender(self, remetente: str, metodo: str, argumentos: tuple[Any, ...]) -> tuple[Any, ...]:
        """O BlueZ chamando. Devolve os argumentos de saída, ou levanta a recusa."""
        dono = self._dono_do_bluez()
        if not dono or remetente != dono:
            self.historico.append((metodo, False))
            raise RecusaNoBarramento(ERRO_REJEITADO, "só o bluetoothd fala com este agente")
        if metodo == "Release":
            self.invalidar()
            return ()
        if metodo == "Cancel":
            logger.info("agente_proprio_cancelado")
            return ()
        aparelho = str(argumentos[0]) if argumentos else ""
        with self._tranca:
            esperado = self._esperado
        aceito = metodo in _ACEITA_O_ESPERADO and bool(esperado) and aparelho == esperado
        self.historico.append((metodo, aceito or metodo in _SO_MOSTRA))
        logger.info(
            "agente_proprio_atendeu", metodo=metodo, aparelho=_mascara(aparelho), aceito=aceito
        )
        if metodo in _SO_MOSTRA:
            return ()
        if metodo in _PEDE_DIGITAR:
            raise RecusaNoBarramento(ERRO_REJEITADO, "este agente não tem onde digitar")
        if aceito:
            return ()
        raise RecusaNoBarramento(ERRO_REJEITADO, "não é o aparelho que o Hefesto está pareando")


__all__ = ["CAMINHO_DO_AGENTE", "CAPACIDADE", "AgenteDePareamento"]
