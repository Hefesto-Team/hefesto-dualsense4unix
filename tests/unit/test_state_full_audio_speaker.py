"""D4 + HOTKEY-EXPOSE-01 + MIC-EXPOSE-01 — o áudio do controle sobe ao payload.

Três coisas que existiam no código e não chegavam a superfície nenhuma:

1. o byte de estado de áudio do report de INPUT (fone plugado / mic externo /
   mic MUDO) era decodificado dentro da ponte de mic por BT e morria lá;
2. o alto-falante não tinha backend NENHUM (`BLOCO_SPEAKER = 0x13` estava
   declarado com um comentário "não usamos");
3. o buffer do combo e o passthrough da emulação eram texto fixo na GUI, e
   `mic_button_toggles_system` não aparecia em lugar algum.

O contrato duro do `speaker`: a chave só existe quando o volume é CONHECIDO, e
ele só é conhecido depois de nós o escrevermos — o DualSense não tem caminho
de leitura para esse registrador. Publicar um número antes disso seria chute,
e a disciplina da casa é sumir em vez de mentir.

MACs fake (regra da casa).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

MAC1 = "aabbcc000001"
MAC2 = "aabbcc000002"


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()
    monkeypatch.setattr(
        loader_module, "profiles_dir", lambda ensure=False: target
    )
    return target


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="bt")
    fc.connect()
    fc.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"index": 0, "connected": True, "transport": "bt",
         "is_primary": True, "uniq": MAC1},
        {"index": 1, "connected": True, "transport": "bt",
         "is_primary": False, "uniq": MAC2},
    ]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock._bt_mic_subsystem = None
    daemon_mock._hotkey_manager = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False, mouse_speed=6, mouse_scroll_speed=1,
        rumble_policy="balanceado", rumble_policy_custom_mult=0.7,
        mic_button_toggles_system=True, bt_mic_enabled=False,
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=socket_path, daemon=daemon_mock,
    )
    await server.start()
    try:
        yield server, socket_path, fc, daemon_mock
    finally:
        await server.stop()


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    assert isinstance(result, dict)
    return result


def _entrada(payload: dict[str, Any], uniq: str) -> dict[str, Any]:
    for entry in payload["controllers"]:
        if entry.get("uniq") == uniq:
            return entry
    raise AssertionError(f"controle {uniq} ausente do payload")


class TestSpeaker:
    @pytest.mark.asyncio
    async def test_sem_volume_conhecido_a_chave_nao_vem(
        self, running_server: Any
    ) -> None:
        """Backend sem posse do volume ⇒ nada de `speaker` (GUI esconde)."""
        _server, socket_path, fc, _daemon = running_server
        fc.speaker_state_for = lambda uniq=None: None  # type: ignore[attr-defined]
        payload = await _state_full(socket_path)
        assert "speaker" not in _entrada(payload, MAC1)

    @pytest.mark.asyncio
    async def test_backend_sem_o_metodo_nao_quebra_o_payload(
        self, running_server: Any
    ) -> None:
        """FakeController/daemon antigo: ausência do método é só ausência."""
        _server, socket_path, _fc, _daemon = running_server
        payload = await _state_full(socket_path)
        assert "speaker" not in _entrada(payload, MAC1)
        assert "audio" not in _entrada(payload, MAC1)
        # O resto do payload continua íntegro (o merge é aditivo).
        assert len(payload["controllers"]) == 2

    @pytest.mark.asyncio
    async def test_contrato_volume_muted_por_controle(
        self, running_server: Any
    ) -> None:
        """`{"volume": int 0-255, "muted": bool}` — o contrato da FRENTE B."""
        _server, socket_path, fc, _daemon = running_server
        estados = {
            MAC1: {"volume": 200, "muted": False},
            MAC2: {"volume": 0, "muted": True},
        }
        fc.speaker_state_for = lambda uniq=None: estados.get(uniq)  # type: ignore[attr-defined]
        payload = await _state_full(socket_path)

        um = _entrada(payload, MAC1)["speaker"]
        assert um["volume"] == 200 and um["muted"] is False
        dois = _entrada(payload, MAC2)["speaker"]
        assert dois["volume"] == 0 and dois["muted"] is True

    @pytest.mark.asyncio
    async def test_espelho_em_inputs(self, running_server: Any) -> None:
        """A GUI acha a chave tanto em `entry` quanto em `entry["inputs"]`."""
        _server, socket_path, fc, daemon = running_server
        from hefesto_dualsense4unix.core.controller import ControllerState

        daemon._last_state = ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="bt",
            raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
            buttons_pressed=frozenset(),
        )
        fc.speaker_state_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "volume": 96, "muted": False
        }
        payload = await _state_full(socket_path)
        entrada = _entrada(payload, MAC1)
        assert entrada["speaker"]["volume"] == 96
        assert entrada["inputs"]["speaker"]["volume"] == 96

    @pytest.mark.asyncio
    async def test_volume_invalido_e_descartado(self, running_server: Any) -> None:
        """Dublê devolvendo lixo não vira valor fantasma no payload."""
        _server, socket_path, fc, _daemon = running_server
        fc.speaker_state_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "volume": "alto", "muted": False
        }
        payload = await _state_full(socket_path)
        assert "speaker" not in _entrada(payload, MAC1)


class TestStatusDeAudio:
    @pytest.mark.asyncio
    async def test_status_do_report_de_input_sobe_como_audio(
        self, running_server: Any
    ) -> None:
        """`audio` é leitura de verdade e independe da posse do volume."""
        _server, socket_path, fc, _daemon = running_server
        fc.audio_status_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "fone_plugado": True, "mic_externo": True, "mic_mudo": False
        }
        payload = await _state_full(socket_path)
        audio = _entrada(payload, MAC1)["audio"]
        assert audio == {
            "fone_plugado": True, "mic_externo": True, "mic_mudo": False
        }

    @pytest.mark.asyncio
    async def test_audio_enriquece_o_speaker_quando_ha_os_dois(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _daemon = running_server
        fc.audio_status_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "fone_plugado": True, "mic_externo": False, "mic_mudo": False
        }
        fc.speaker_state_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "volume": 128, "muted": False
        }
        payload = await _state_full(socket_path)
        speaker = _entrada(payload, MAC1)["speaker"]
        assert speaker["volume"] == 128
        assert speaker["fone_plugado"] is True

    @pytest.mark.asyncio
    async def test_sem_report_lido_nao_ha_chave_audio(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _daemon = running_server
        fc.audio_status_for = lambda uniq=None: None  # type: ignore[attr-defined]
        payload = await _state_full(socket_path)
        assert "audio" not in _entrada(payload, MAC1)


class TestHotkeyEMic:
    @pytest.mark.asyncio
    async def test_bloco_hotkey_vem_do_manager_vivo(
        self, running_server: Any
    ) -> None:
        """HOTKEY-EXPOSE-01: buffer_ms/passthrough deixam de ser texto fixo."""
        from hefesto_dualsense4unix.integrations.hotkey_daemon import (
            HotkeyConfig,
            HotkeyManager,
        )

        _server, socket_path, _fc, daemon = running_server
        daemon._hotkey_manager = HotkeyManager(
            config=HotkeyConfig(buffer_ms=275, passthrough_in_emulation=True)
        )
        payload = await _state_full(socket_path)
        assert payload["hotkey"] == {
            "buffer_ms": 275, "passthrough_in_emulation": True
        }

    @pytest.mark.asyncio
    async def test_sem_manager_a_chave_hotkey_some(
        self, running_server: Any
    ) -> None:
        """Daemon sem HotkeyManager: ausência, nunca o default disfarçado."""
        _server, socket_path, _fc, daemon = running_server
        daemon._hotkey_manager = None
        payload = await _state_full(socket_path)
        assert "hotkey" not in payload

    @pytest.mark.asyncio
    async def test_mic_button_toggles_system_e_bt_mic_no_payload(
        self, running_server: Any
    ) -> None:
        _server, socket_path, _fc, daemon = running_server
        daemon.config.mic_button_toggles_system = False
        payload = await _state_full(socket_path)
        assert payload["mic_button_toggles_system"] is False
        assert payload["bt_mic"] == {"enabled": False, "running": False}


class TestSpeakerSet:
    @pytest.mark.asyncio
    async def test_speaker_set_escreve_e_devolve_o_estado(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _daemon = running_server
        pedidos: list[Any] = []

        def _set(volume: Any = None, *, muted: Any = None, uniq: Any = None) -> bool:
            pedidos.append((volume, muted, uniq))
            return True

        fc.set_speaker_volume = _set  # type: ignore[attr-defined]
        fc.speaker_state_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "volume": 180, "muted": False
        }
        async with IpcClient.connect(socket_path) as client:
            res = await client.call("speaker.set", {"volume": 180, "uniq": MAC1})
        assert res["status"] == "ok"
        assert res["speaker"] == {"volume": 180, "muted": False}
        assert pedidos == [(180, None, MAC1)]

    @pytest.mark.asyncio
    async def test_speaker_set_rejeita_volume_fora_de_faixa(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _daemon = running_server
        fc.set_speaker_volume = lambda *a, **k: True  # type: ignore[attr-defined]
        async with IpcClient.connect(socket_path) as client:
            with pytest.raises(RuntimeError, match="0-255"):
                await client.call("speaker.set", {"volume": 999})


class TestExternosNoPayload:
    """EXT-COUNT-01 — "2 jogadores" não pode ser lido como "2 controles"."""

    @pytest.mark.asyncio
    async def test_conta_externos_sem_inflar_players(
        self, running_server: Any
    ) -> None:
        _server, socket_path, _fc, daemon = running_server
        daemon._coop_manager = MagicMock()
        daemon._coop_manager.player_count.return_value = 2
        daemon.external_registry = MagicMock()
        daemon.external_registry.snapshot_connected.return_value = {
            "aabbcc0000e1", "aabbcc0000e2"
        }
        payload = await _state_full(socket_path)
        assert payload["coop"]["players"] == 2
        assert payload["coop"]["externals"] == 2

    @pytest.mark.asyncio
    async def test_sem_registro_de_externos_a_chave_some(
        self, running_server: Any
    ) -> None:
        _server, socket_path, _fc, daemon = running_server
        daemon.external_registry = None
        payload = await _state_full(socket_path)
        assert "externals" not in payload["coop"]
