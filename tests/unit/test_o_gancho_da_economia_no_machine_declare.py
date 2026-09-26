"""O ``machine.declare`` que muda a economia reaplica o perfil na hora.

O-MODO-ECONOMIA-POR-CONTROLE-01 (25/09/2026): a economia — a da mesa («Bateria
longa») e a de cada controle — é lida na ativação do perfil. A conferência da
frente deixou o gancho para a costura: sem ele, o botão da economia na aba 08 e
a «Bateria longa» da aba 09 só chegariam ao aparelho na próxima troca de janela.

A régua usa a decisão REAL (`Daemon.reaplicar_se_a_economia_mudou`) e troca só
a ponta que fala com o aparelho (`_reapply_last_profile`) por um contador.

MORDIDA: sem as duas linhas do gancho em `_handle_machine_declare`, o primeiro
teste reprova com zero reaplicações.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, caminho_da_maquina

#: Um rosto da faixa forjada, na forma em que a chave vai ao disco.
CHAVE = "aabbcc00beef"


class _DaemonVivo:
    """O mínimo do daemon que o gancho toca, com a decisão real emprestada."""

    reaplicar_se_a_economia_mudou = Daemon.reaplicar_se_a_economia_mudou

    def __init__(self) -> None:
        self._maquina = MaquinaConfig()
        self._native_mode = False
        self.reaplicou = 0

    def _reapply_last_profile(self) -> None:
        self.reaplicou += 1


class _Servidor(IpcHandlersMixin):
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon


def _declarar(daemon: _DaemonVivo, maquina: dict[str, Any]) -> dict[str, Any]:
    servidor = _Servidor(daemon)
    return asyncio.run(servidor._handle_machine_declare({"maquina": maquina}))


def test_a_economia_de_um_controle_reaplica_na_hora(tmp_path: Path) -> None:
    assert tmp_path in caminho_da_maquina().parents, "o maquina.json escapou do tmp"
    daemon = _DaemonVivo()

    assert _declarar(daemon, {"controles": {CHAVE: {"economia": True}}})["ok"]
    assert daemon.reaplicou == 1, (
        "a economia do controle mudou no disco e o perfil não foi reaplicado: o "
        "botão da aba 08 só chegaria ao aparelho na próxima troca de janela")

    assert _declarar(daemon, {"controles": {CHAVE: {"economia": None}}})["ok"]
    assert daemon.reaplicou == 2, "desligar a economia também tem de valer na hora"


def test_a_bateria_longa_da_mesa_reaplica_na_hora(tmp_path: Path) -> None:
    assert tmp_path in caminho_da_maquina().parents
    daemon = _DaemonVivo()

    assert _declarar(daemon, {"orcamento": {"teto": "economia"}})["ok"]
    assert daemon.reaplicou == 1


def test_declarar_outra_coisa_nao_reaplica(tmp_path: Path) -> None:
    assert tmp_path in caminho_da_maquina().parents
    daemon = _DaemonVivo()

    assert _declarar(daemon, {"mesa": {"altura_da_antena": "acima"}})["ok"]
    assert daemon.reaplicou == 0, "a antena não muda a economia; reaplicar seria ruído"
