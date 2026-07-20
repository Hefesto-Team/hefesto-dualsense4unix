"""NUMA-05 — `game_signal` no `daemon.state_full` (autoridade de exibição).

A síntese da Onda N (docs/process/sprints/2026-07-19-sprint-numeracao-una.md)
decidiu um sinal global de três estados ('game'/'daemon'/'unknown') que o
NUMA-01 (ainda não fiado neste tree) vai popular via property PÚBLICA
`daemon.display_authority` + diagnóstico rico opcional em
`daemon._game_signal.diagnostico()`. Este módulo cobre SÓ a exposição no
`state_full` (a parte de NUMA-05) — deliberadamente NÃO testa `classify()`
nem a casca `GameSignal` (isso é NUMA-01, ainda inexistente):

1. Sem `display_authority` (daemon None, ou atributo ausente) — degrada para
   `authority="unknown"`, `degradado=True`, `motivo="sinal_nao_wireado"`
   (fail-safe: NUNCA inventa 'game'/'daemon').
2. `display_authority` com valor válido — passa direto, `degradado=False`,
   `motivo=None` (sem diagnóstico rico).
3. `display_authority` com valor FORA da tabela ('game'/'daemon'/'unknown')
   degrada pela MESMA regra do item 1 — dublê de teste bronco ou versão
   futura desalinhada não vira autoridade fantasma.
4. Diagnóstico rico (`daemon._game_signal.diagnostico()`) populando
   evidencia/motivo/desde/degradado quando presente.
5. Diagnóstico que LEVANTA não derruba o `state_full` — só os campos ricos
   ficam no default (a `authority` já foi lida antes, independente).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def ipc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IpcServer:
    """IpcServer mínimo (sem socket no ar) para chamar `_handle_daemon_state_full`."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


class _FakeDaemon:
    """Dublê mínimo do `Daemon` real — só o suficiente pro `state_full` não
    estourar (`is_paused`/`is_native_mode` são chamados incondicionalmente
    quando `self.daemon` não é None). Atributos extras (``display_authority``,
    ``_game_signal``) entram por kwargs — o resto do `state_full` já trata
    tudo mais via `getattr` defensivo.
    """

    def __init__(self, **kwargs: Any) -> None:
        for chave, valor in kwargs.items():
            setattr(self, chave, valor)

    def is_paused(self) -> bool:
        return False

    def is_native_mode(self) -> bool:
        return False


def _com_daemon(server: IpcServer, daemon: Any) -> IpcServer:
    server.daemon = daemon
    return server


async def test_sem_daemon_degrada_para_unknown(ipc_server: IpcServer) -> None:
    """FALHA-SEM: no HEAD pré-NUMA-05, `state_full` nem tinha a chave
    `game_signal` — este teste estoura KeyError sem a mudança."""
    result = await ipc_server._handle_daemon_state_full({})
    assert result["game_signal"] == {
        "authority": "unknown",
        "evidencia": None,
        "motivo": "sinal_nao_wireado",
        "desde": None,
        "degradado": True,
    }


async def test_atributo_ausente_degrada_igual_a_daemon_none(
    ipc_server: IpcServer,
) -> None:
    daemon = _FakeDaemon()  # sem display_authority nenhum
    _com_daemon(ipc_server, daemon)
    result = await ipc_server._handle_daemon_state_full({})
    assert result["game_signal"]["authority"] == "unknown"
    assert result["game_signal"]["degradado"] is True
    assert result["game_signal"]["motivo"] == "sinal_nao_wireado"


@pytest.mark.parametrize("valor", ["game", "daemon"])
async def test_authority_wireada_passa_direto(
    ipc_server: IpcServer, valor: str
) -> None:
    _com_daemon(ipc_server, _FakeDaemon(display_authority=valor))
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == valor
    assert gs["degradado"] is False
    # Wireado com sucesso: o motivo genérico de "sem sinal" NÃO aparece —
    # sem diagnóstico rico, fica None (nunca "sinal_nao_wireado" fantasma).
    assert gs["motivo"] is None


async def test_authority_unknown_wireada_e_degradado_mesmo_sem_motivo(
    ipc_server: IpcServer,
) -> None:
    """`unknown` GENUÍNO (classify() real, `display_authority` wireado) é
    degradado por definição da síntese — mesmo sem diagnóstico rico (motivo
    fica None, não "sinal_nao_wireado" — essa string é EXCLUSIVA do "nem
    wireado ainda")."""
    _com_daemon(ipc_server, _FakeDaemon(display_authority="unknown"))
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "unknown"
    assert gs["degradado"] is True
    assert gs["motivo"] is None


async def test_authority_invalida_degrada_para_unknown(
    ipc_server: IpcServer,
) -> None:
    """Valor fora da tabela ('game'/'daemon'/'unknown') — dublê de teste
    bronco ou versão futura desalinhada — NUNCA vira autoridade fantasma."""
    _com_daemon(
        ipc_server, _FakeDaemon(display_authority="qualquer_coisa")
    )
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "unknown"
    assert gs["degradado"] is True
    assert gs["motivo"] == "sinal_nao_wireado"


async def test_diagnostico_rico_populado_quando_presente(
    ipc_server: IpcServer,
) -> None:
    diag = SimpleNamespace(
        diagnostico=lambda: {
            "evidencia": "wm_class_steam_app",
            "motivo": None,
            "desde": 123.5,
            "degradado": False,
        }
    )
    _com_daemon(
        ipc_server,
        _FakeDaemon(display_authority="game", _game_signal=diag),
    )
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "game"
    assert gs["evidencia"] == "wm_class_steam_app"
    assert gs["desde"] == 123.5
    assert gs["degradado"] is False


async def test_diagnostico_com_motivo_de_queda(ipc_server: IpcServer) -> None:
    diag = SimpleNamespace(
        diagnostico=lambda: {
            "evidencia": None,
            "motivo": "detector_de_janela_cego",
            "desde": 900.0,
            "degradado": True,
        }
    )
    _com_daemon(
        ipc_server,
        _FakeDaemon(display_authority="unknown", _game_signal=diag),
    )
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "unknown"
    assert gs["motivo"] == "detector_de_janela_cego"
    assert gs["degradado"] is True


async def test_diagnostico_que_levanta_nao_derruba_state_full(
    ipc_server: IpcServer,
) -> None:
    """Exceção em `diagnostico()` é suprimida — `authority` (já lida antes)
    segue correta; só os campos ricos ficam no default."""

    def bomba() -> dict[str, Any]:
        raise RuntimeError("marker ilegível")

    _com_daemon(
        ipc_server,
        _FakeDaemon(
            display_authority="daemon", _game_signal=SimpleNamespace(diagnostico=bomba)
        ),
    )
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "daemon"
    assert gs["degradado"] is False
    assert gs["evidencia"] is None
    assert gs["desde"] is None


async def test_diagnostico_nao_dict_e_ignorado(ipc_server: IpcServer) -> None:
    """Retorno que não é dict (mock broncó) — ignorado, sem exceção."""
    _com_daemon(
        ipc_server,
        _FakeDaemon(
            display_authority="game",
            _game_signal=SimpleNamespace(diagnostico=lambda: "nao e dict"),
        ),
    )
    result = await ipc_server._handle_daemon_state_full({})
    gs = result["game_signal"]
    assert gs["authority"] == "game"
    assert gs["evidencia"] is None
