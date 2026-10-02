"""Subsystem das conexões de rádio — o controle que conecta e não vira controle."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    LinkDeRadio,
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

INTERVALO_S = 5.0

ENV_DESLIGA = "HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI"


QUEM = "vigia-de-zumbis"

PRAZO_DA_TRAVA_S = 10.0


@dataclass
class PonteComTrava(PontePrivilegiada):
    """A ponte do vigia, pela trava do rádio e com rastro no diário comum."""

    interna: PontePrivilegiada = field(default_factory=PontePrivilegiada)
    prazo_s: float = PRAZO_DA_TRAVA_S

    def impedimentos(self) -> list[str]:
        """Os da ponte de verdade: a trava não impede, só põe em fila."""
        return self.interna.impedimentos()

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        """Derruba o link com a trava na mão, e registra o que aconteceu."""
        with contextlib.ExitStack() as pilha:
            sem_trava = False
            try:
                pilha.enter_context(
                    diario_do_radio.trava_do_radio(QUEM, prazo_s=self.prazo_s)
                )
            except diario_do_radio.TravaOcupadaError as erro:
                return False, f"{erro}; tento na próxima volta"
            except OSError:
                logger.debug("conexao_zumbi_sem_trava", exc_info=True)
                sem_trava = True
            agiu, motivo = self.interna.desconectar(link)
            diario_do_radio.registrar(
                QUEM,
                "derrubou o link" if agiu else "tentou derrubar o link",
                "conectou e não virou controle: sem hidraw e sem registro no BlueZ",
                antes={"link": "de pé"},
                depois={"link": "caiu" if agiu else "de pé", "motivo": motivo or None},
                adaptador=link.adaptador,
                controle=link.controle,
                hci=link.hci,
                sem_trava=sem_trava or None,
                trava_comum=diario_do_radio.a_trava_e_comum(
                    diario_do_radio.caminho_da_trava()
                ),
            )
            return agiu, motivo


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
        self._vigia = vigia or VigiaDeZumbis(ponte=PonteComTrava())
        self._olhador = olhador or olhar_a_mesa
        self._intervalo_s = intervalo_s
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self.ultimo_veredito: Veredito | None = None


    def is_enabled(self, config: DaemonConfig) -> bool:
        """Ligado por default; ``…_CONEXAO_ZUMBI=0`` desliga."""
        bruto = os.environ.get(ENV_DESLIGA)
        if bruto is None:
            return True
        # (noqa-acento) na linha do conjunto: "nao" é a digitação de quem não
        negativos = {"0", "false", "no", "nao", "não"}  # (noqa-acento): digitação
        return bruto.strip().lower() not in negativos

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


    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                self.uma_volta(time.monotonic())
            except Exception:
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
    "PRAZO_DA_TRAVA_S",
    "QUEM",
    "ConexoesSubsystem",
    "PonteComTrava",
    "caminho_do_diario",
    "ler_o_diario",
]
