"""Subsystem das conexões de rádio — o controle que conecta e não vira controle.

CONEXAO-ZUMBI-01. A regra mora em
:mod:`hefesto_dualsense4unix.integrations.conexao_zumbi`; aqui está o que a faz
acontecer no produto: um laço próprio que olha a mesa de tempos em tempos, pede
à ponte privilegiada que derrube o link morto, e ESCREVE O QUE ACONTECEU num
lugar que a aba Conexões consegue ler.

AS TRÊS PONTAS DA RECEITA — e a lista dos subsystems avisa que são três
---------------------------------------------------------------------------
1. a linha em ``daemon/subsystems/__init__.py`` (declarativa);
2. o ``_safe_start`` deste vigia em ``daemon/lifecycle.py`` — é ELE que sobe;
3. o ``_stop_conexoes`` no ``shutdown()`` de ``daemon/connection.py``.
Quem fizer só as duas primeiras sobe uma thread que ninguém para.

POR QUE UM LAÇO PRÓPRIO, E NÃO O TIQUE DO DAEMON
-------------------------------------------------
Porque o ``poll.tick`` NÃO mede o rádio: ele conta o relógio do daemon. E
porque as leituras desta cura chamam processos (``hcitool``, ``busctl``,
``sudo``) — pendurar isso no laço do GTK/asyncio é o defeito que já congelou a
janela dela uma vez (as duas viagens de IPC síncronas, 15/09/2026). A thread é
``daemon=True`` e o ``stop()`` a colhe.

O DIZER É METADE DO TRABALHO
-----------------------------
*"a recusa com motivo não é resposta"*: a pessoa não tem o que fazer com «o
sistema não vê um microfone neste controle». Por isso cada volta deixa um
:class:`~hefesto_dualsense4unix.integrations.conexao_zumbi.Veredito` no disco,
em :func:`caminho_do_diario`, com o que aconteceu **e o gesto que resta** —
quando a cura não basta, a frase já diz "repareie neste adaptador", que é o que
a aba Conexões tem de mostrar.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    PontePrivilegiada,
    Veredito,
    VigiaDeZumbis,
    olhar_a_mesa,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: De quanto em quanto tempo o vigia olha. Cinco segundos dá quatro observações
#: dentro dos 20 s que um suspeito precisa durar para virar zumbi — o bastante
#: para o tempo ser medido, e leve o suficiente para não pesar (as leituras são
#: sysfs e dois processos curtos).
INTERVALO_S = 5.0

#: A chave que desliga. LIGADO POR DEFAULT, e a razão é a ordem dela de
#: 18/09/2026: *"o produto precisa ser inteligente pra evitar problemas como
#: esse"*. A cura só toca em link que NÃO serve a ninguém (as três condições do
#: módulo da regra), então o custo de estar ligada é zero para quem não tem o
#: defeito — e o de estar desligada é o que ela viu: dois controles conectados,
#: ambos jogador 1, ambos com a barra azul.
ENV_DESLIGA = "HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI"


def caminho_do_diario() -> Path:
    """Onde a última volta do vigia fica, para a aba Conexões ler."""
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / "conexao-zumbi.json"


def ler_o_diario() -> dict[str, Any]:
    """A última volta, ou ``{}``. Nunca levanta — é leitura de tela."""
    try:
        with caminho_do_diario().open(encoding="utf-8") as fh:
            dado = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}


def _gravar_o_diario(veredito: Veredito, agora: float) -> None:
    caminho = caminho_do_diario()
    dado = {
        "carimbo": agora,
        "agiu": veredito.agiu,
        "suspeitos": [asdict(link) for link in veredito.suspeitos],
        "zumbis": [asdict(link) for link in veredito.zumbis],
        "derrubados": [asdict(link) for link in veredito.derrubados],
        "segurados_pelo_teto": [asdict(link) for link in veredito.segurados_pelo_teto],
        "impedimentos": list(veredito.impedimentos),
        "diario": list(veredito.diario),
    }
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # Troca atômica: a aba lê este arquivo a qualquer instante, e um leitor
        # que pega o arquivo pela metade mostra "nenhum aviso" sobre um zumbi.
        temporario = caminho.with_suffix(".json.novo")
        with temporario.open("w", encoding="utf-8") as fh:
            json.dump(dado, fh, ensure_ascii=False)
        temporario.replace(caminho)
    except OSError:
        logger.debug("conexao_zumbi_diario_nao_gravou", exc_info=True)


class ConexoesSubsystem:
    """Vigia as conexões de rádio e cura o link que não virou controle."""

    name = "conexoes"  # (noqa-acento): nome ASCII do subsystem, como os irmãos

    def __init__(
        self,
        *,
        vigia: Any = None,
        olhador: Any = None,
        intervalo_s: float = INTERVALO_S,
    ) -> None:
        self._vigia = vigia or VigiaDeZumbis(ponte=PontePrivilegiada())
        self._olhador = olhador or olhar_a_mesa
        self._intervalo_s = intervalo_s
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        #: A última volta, para quem perguntar pelo IPC sem tocar no disco.
        self.ultimo_veredito: Veredito | None = None

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Ligado por default; ``…_CONEXAO_ZUMBI=0`` desliga."""
        bruto = os.environ.get(ENV_DESLIGA)
        if bruto is None:
            return True
        # A forma sem acento entra de propósito: quem digita a chave à mão no
        # terminal raramente acentua, e recusar por isso seria um interruptor
        # que não desliga.
        return bruto.strip().lower() not in {"0", "false", "no", "nao", "não"}  # (noqa-acento): aceita a digitação sem acento de quem escreve no terminal

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread do vigia. Idempotente."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._laco, name="hefesto-conexoes-vigia", daemon=True
        )
        self._thread.start()
        logger.info("conexoes_subsystem_iniciado", intervalo_s=self._intervalo_s)

    async def stop(self) -> None:
        """Para o vigia. Idempotente, e não segura o event loop."""
        self._parar.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
        logger.info("conexoes_subsystem_parado")

    # -- o laço ----------------------------------------------------------

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                self.uma_volta(time.monotonic())
            except Exception:
                # Uma volta que levanta NÃO pode matar o vigia: o defeito que
                # ele cura acontece justamente quando o rádio está estranho.
                logger.debug("conexao_zumbi_volta_falhou", exc_info=True)
            self._parar.wait(self._intervalo_s)

    def uma_volta(self, agora: float) -> Veredito:
        """Olha a mesa, decide e registra. É o que a régua chama."""
        links, com_hid, conhecidos, impedimentos = self._olhador()
        veredito = self._vigia.observar(
            agora, links, com_hid, conhecidos, impedimentos=impedimentos
        )
        self.ultimo_veredito = veredito
        for linha in veredito.diario:
            logger.warning("conexao_zumbi", recado=linha)
        _gravar_o_diario(veredito, agora)
        return veredito


__all__ = [
    "ENV_DESLIGA",
    "INTERVALO_S",
    "ConexoesSubsystem",
    "caminho_do_diario",
    "ler_o_diario",
]
