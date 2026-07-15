"""O vpad do P1 vira uhid quando o hidraw aparece (SPRINT-UHID-VPAD-01).

Sem isto o caminho uhid — a razão de existir do sprint, a vibração da máscara
DualSense — ficava MORTO no boot normal. A ordem do `lifecycle` é:

    linha ~346:  _safe_start("gamepad")   -> cria o vpad
    linha ~370:  controller.connect()     -> só AGORA existe hidraw

Então o vpad do P1 nascia sem blueprint de onde copiar e caía no uinput, para
sempre (o backend era escolhido uma vez). Medido ao vivo em todo boot:
``vpad_uhid_sem_hidraw_usando_uinput player=1``.

Depois do fix, o log do boot real vira:
``vpad_promovendo_para_uhid -> uhid_device_created mac=02:fe:00:00:00:01``
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp


class _FakeUinputPad:
    flavor = "dualsense"

    def __init__(self) -> None:
        self.parado = False

    def stop(self) -> None:
        self.parado = True


class _FakeDaemon:
    def __init__(self, device: Any) -> None:
        self._gamepad_device = device
        self.config = type("_Cfg", (), {"gamepad_flavor": "dualsense",
                                        "gamepad_emulation_enabled": True})()


@pytest.fixture()
def sem_efeitos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Neutraliza o start/stop reais; registra o que foi chamado."""
    chamadas: dict[str, Any] = {"stop": 0, "start": []}

    def _stop(_daemon: Any, **kwargs: Any) -> None:
        chamadas["stop"] += 1
        chamadas["stop_kwargs"] = kwargs

    def _start(_daemon: Any, flavor: str | None = None) -> bool:
        chamadas["start"].append(flavor)
        return True

    monkeypatch.setattr(gp, "stop_gamepad_emulation", _stop)
    monkeypatch.setattr(gp, "start_gamepad_emulation", _start)
    return chamadas


class TestPromocao:
    def test_promove_quando_o_hidraw_aparece(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        """O caso do boot: vpad uinput + controle que acabou de conectar."""
        monkeypatch.setattr(gp, "resolve_hidraw_path", lambda _d, _u: "/dev/hidraw4")
        daemon = _FakeDaemon(_FakeUinputPad())

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert sem_efeitos["start"] == ["dualsense"]
        # Não persiste (a preferência não mudou) nem solta o grab (o controle
        # físico voltaria para o jogo no meio da troca).
        assert sem_efeitos["stop_kwargs"] == {"persist": False, "release_grab": False}

    def test_sem_hidraw_nao_mexe(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        monkeypatch.setattr(gp, "resolve_hidraw_path", lambda _d, _u: None)
        daemon = _FakeDaemon(_FakeUinputPad())

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_mascara_xbox_fica_no_uinput(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        """O hid_playstation não faz bind em VID/PID da Microsoft — por design."""
        monkeypatch.setattr(gp, "resolve_hidraw_path", lambda _d, _u: "/dev/hidraw4")
        pad = _FakeUinputPad()
        pad.flavor = "xbox"
        daemon = _FakeDaemon(pad)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_sem_gamepad_ligado_nao_mexe(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        monkeypatch.setattr(gp, "resolve_hidraw_path", lambda _d, _u: "/dev/hidraw4")
        daemon = _FakeDaemon(None)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_vpad_que_ja_e_uhid_nao_e_recriado(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        """Idempotente: recriar no replug faria o jogo perder o device à toa."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        monkeypatch.setattr(gp, "resolve_hidraw_path", lambda _d, _u: "/dev/hidraw4")
        daemon = _FakeDaemon(UhidDualSense(player=1, blueprint=None))

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0


def test_o_lifecycle_promove_quando_o_controle_conecta() -> None:
    """O gancho existe no ponto certo — senão o fix não vale nada no boot real."""
    from pathlib import Path

    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")
    idx_connect = fonte.index("controller_connected")
    trecho = fonte[idx_connect:idx_connect + 700]
    assert "upgrade_primary_vpad_to_uhid" in trecho, (
        "a promoção saiu do caminho do controller_connected — o vpad do P1 volta "
        "a ficar preso no uinput em todo boot"
    )
