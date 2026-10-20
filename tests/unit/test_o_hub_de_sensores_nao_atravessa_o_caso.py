"""O hub de sensores e o que um arquivo deixou vivo não atravessam para o caso seguinte.

OS-TRES-VERMELHOS-DE-TEMPO-DO-LINT-TEST-NO-CI-01 (20/10/2026). O `lint-test` do CI roda
`tests/unit` num processo só, e dois restos de um caso pesavam no seguinte:

* o `SensorHub` que o `_garantir_sensor_hub` criou seguia com a manutenção viva (42 no lote
  de 96 arquivos), e no segundo ciclo dentro de um caso de mesa de mentira abria o touchpad
  dela (o inventário e o sysfs reprovavam pelo nó do DualSense aberto);
* as árvores de sintaxe que os portões guardam em cache deixavam 2 milhões de objetos na
  varredura do coletor, e a passada cheia (4,2 s sob carga) caía dentro do prazo de 1 s do
  `daemon.state_full`.

Mordidas:

* tirar o `hub.stop_all` do `IpcServer.stop`: o primeiro caso reprova com a thread viva;
* tirar a fixture `_nenhum_hub_de_sensores_atravessa` do conftest: o terceiro caso acha a
  manutenção que o segundo deixou;
* tirar o `gc.freeze` de `_congelar_o_que_o_arquivo_deixou`: o quarto caso reprova.
"""

from __future__ import annotations

import asyncio
import gc
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

_NOME = "hefesto-sensor-hub"


def _servidor(tmp_path: Path) -> IpcServer:
    fc = FakeController(transport="usb")
    store = StateStore()
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "hub.sock",
        daemon=MagicMock(),
    )


def _manutencoes_vivas() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == _NOME and t.is_alive()]


def test_o_servidor_que_para_leva_o_hub_dele(tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    antes = set(_manutencoes_vivas())
    servidor._garantir_sensor_hub().vigiar()
    [nova] = [t for t in _manutencoes_vivas() if t not in antes]

    asyncio.run(servidor.stop())

    assert not nova.is_alive(), "o servidor parou e a manutenção do hub dele seguiu viva"
    assert servidor._sensor_hub is None


def test_o_caso_que_esquece_o_hub_ligado(tmp_path: Path) -> None:
    """O handler chamado direto, sem servidor de pé: ninguém chama o `stop`."""
    servidor = _servidor(tmp_path)
    servidor._garantir_sensor_hub().vigiar()
    assert _manutencoes_vivas()


def test_o_caso_seguinte_nao_herda_a_manutencao() -> None:
    assert _manutencoes_vivas() == [], "o hub do caso anterior atravessou para este"


def test_o_que_o_arquivo_deixou_vivo_sai_da_varredura() -> None:
    from tests.conftest import _congelar_o_que_o_arquivo_deixou

    guardado: list[list[int]] = [[i] for i in range(50_000)]
    item = SimpleNamespace(path=Path("tests/unit/test_um.py"))
    mesmo = SimpleNamespace(path=item.path)
    outro = SimpleNamespace(path=Path("tests/unit/test_outro.py"))

    assert not _congelar_o_que_o_arquivo_deixou(item, mesmo)
    assert gc.is_tracked(guardado[0])
    varridos_antes = len(gc.get_objects())

    assert _congelar_o_que_o_arquivo_deixou(item, outro)
    varridos_depois = len(gc.get_objects())
    assert varridos_antes - varridos_depois >= len(guardado), (
        f"{varridos_antes} na varredura antes e {varridos_depois} depois: o fim do arquivo "
        "não congelou o que ele deixou vivo"
    )
    assert _congelar_o_que_o_arquivo_deixou(item, None), "o último caso da corrida também congela"
