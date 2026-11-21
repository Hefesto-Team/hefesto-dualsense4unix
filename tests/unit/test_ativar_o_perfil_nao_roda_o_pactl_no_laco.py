"""ATIVAR-O-PERFIL-NAO-RODA-O-PACTL-NO-LACO-01.

O volume do microfone do perfil (a fonte no grafo do som e o ``pactl set-source-volume``) sai do fio
de quem ativa: o laço segue atendendo com o ``pactl`` dormindo, e o volume que fica é o da última
ativação, de cada controle.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``).
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile, ProfileMicConfig

DORME_S = 1.0
TETO_IPC_S = 0.4
_P1 = "aa:bb:cc:00:00:01"
_P2 = "aa:bb:cc:00:00:02"


class _PactlLento:
    """O ``pactl`` trocado por um que dorme ``DORME_S``; anota o fio e o volume de cada chamada."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, dorme_s: float = DORME_S) -> None:
        from hefesto_dualsense4unix.integrations import audio_control

        self.dorme_s = dorme_s
        self.chamadas: list[tuple[str, str, int]] = []
        self.solta = threading.Event()
        self.solta.set()
        monkeypatch.setattr(audio_control, "fonte_de_captura_do_uniq", lambda uniq, **_k: uniq)
        monkeypatch.setattr(audio_control, "fonte_de_captura_do_controle", lambda: "global")
        monkeypatch.setattr(audio_control, "definir_volume_da_captura", self._definir)

    def _definir(self, volume: int, *, fonte: str | None) -> bool:
        self.chamadas.append((threading.current_thread().name, str(fonte), volume))
        time.sleep(self.dorme_s)
        self.solta.wait(10.0)
        return True

    def volumes(self, fonte: str) -> list[int]:
        return [v for _fio, f, v in self.chamadas if f == fonte]


@pytest.fixture
def pactl(monkeypatch: pytest.MonkeyPatch) -> _PactlLento:
    return _PactlLento(monkeypatch)


def _servidor(tmp_path: Path) -> Any:
    """O ``Daemon`` e o ``IpcServer`` do produto, com o applier de microfone de verdade."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    gerente.mic_applier = daemon.apply_profile_mic
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "p.sock", daemon=daemon)
    daemon._ipc_server = servidor
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    servidor.store.set_active_profile("Ensaio")
    return servidor


def _perfil(nome: str, volume: int) -> None:
    mic = ProfileMicConfig(button_toggles_system=False, volume=volume)
    loader.save_profile(Profile(name=nome, match=MatchAny(type="any"), mic=mic))


async def _o_status_durante(
    servidor: Any, coro: Coroutine[Any, Any, Any]
) -> tuple[float, bool, Any]:
    t0 = time.perf_counter()
    tarefa = asyncio.ensure_future(coro)
    await asyncio.sleep(0.05)
    await servidor._handlers["daemon.status"]({})
    gasto = time.perf_counter() - t0
    corria = not tarefa.done()
    return gasto, corria, await tarefa


def test_o_profile_switch_com_volume_responde_enquanto_o_pactl_dorme(
    tmp_path: Path, pactl: _PactlLento
) -> None:
    servidor = _servidor(tmp_path)
    _perfil("Com Volume", 40)

    gasto, _corria, resposta = asyncio.run(_o_status_durante(
        servidor, servidor._handlers["profile.switch"]({"name": "Com Volume"})))

    assert gasto < TETO_IPC_S, f"o profile.switch parou o laço {gasto:.2f} s"
    assert resposta["secoes"]["mic"] == "pedido", resposta
    from hefesto_dualsense4unix.profiles.manager import PEDIDOS_DO_VOLUME_DO_MIC

    assert PEDIDOS_DO_VOLUME_DO_MIC.esperar(DORME_S * 5)
    assert pactl.chamadas
    assert {fio for fio, _f, _v in pactl.chamadas} == {"hefesto-volume-do-mic"}, pactl.chamadas
    assert pactl.volumes("global") == [40]


def test_a_ultima_ativacao_vence_o_volume(tmp_path: Path, pactl: _PactlLento) -> None:
    from hefesto_dualsense4unix.profiles.manager import PEDIDOS_DO_VOLUME_DO_MIC

    servidor = _servidor(tmp_path)
    for nome, volume in (("Um", 10), ("Dois", 20), ("Terceiro", 30), ("Quatro", 70)):
        _perfil(nome, volume)
    pactl.solta.clear()

    async def corpo() -> None:
        for nome in ("Um", "Dois", "Terceiro", "Quatro"):
            await servidor._handlers["profile.switch"]({"name": nome})
            await asyncio.sleep(0.02)
        pactl.solta.set()

    asyncio.run(corpo())

    assert PEDIDOS_DO_VOLUME_DO_MIC.esperar(DORME_S * 6)
    assert pactl.volumes("global")[-1] == 70, pactl.chamadas
    assert len(pactl.volumes("global")) <= 2, pactl.chamadas


def test_cada_controle_guarda_o_volume_da_sua_ultima_ativacao(
    pactl: _PactlLento,
) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.manager import PEDIDOS_DO_VOLUME_DO_MIC
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(transport="bt"))  # type: ignore[arg-type]
    pactl.solta.clear()
    for uniq, volume in ((_P1, 11), (_P2, 22), (_P1, 33), (_P2, 44)):
        daemon.apply_profile_mic(volume, None, uniq=uniq)
    pactl.solta.set()

    assert PEDIDOS_DO_VOLUME_DO_MIC.esperar(DORME_S * 6)
    assert pactl.volumes(_P1)[-1] == 33, pactl.chamadas
    assert pactl.volumes(_P2)[-1] == 44, pactl.chamadas
