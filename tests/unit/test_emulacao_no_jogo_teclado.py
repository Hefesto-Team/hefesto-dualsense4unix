"""EMULACAO-NO-JOGO-01 — o R1 trocava de aplicativo em vez de jogar.

Queixa dela, 29/07: *"inicio o jogo e ele quando aperto r1 muda de app ao invés
de funcionar no jogo"*; e, no mesmo relato, o raciocínio que aponta o defeito —
com o modo mouse/teclado desligado, isso não deveria impactar. A transcrição
literal (sem correção de grafia) está na sprint
`docs/process/sprints/2026-07-29-EMULACAO-NO-JOGO-01-*`; aqui ela vem acentuada
porque o portão de acentuação varre este arquivo.

Não deveria — e o motivo de impactar era que aquele interruptor governa só o
MOUSE. O teclado emulado não tinha interruptor nenhum (sem gate de criação, sem
flag em disco, sem IPC, sem chave no `state_full`), e a exclusão mútua do poll
loop era `if not gamepad_dispatched:` — a AUSÊNCIA do vpad lida como PERMISSÃO
para o desktop entrar, justamente quando a exceção do Steam Input derruba o vpad
DE PROPÓSITO para o jogo assumir. Medição do journal dela: 9 de 9 pressionamentos
de R1 em 7 dias caíram dentro de `steam_input_vpad_suspenso`, zero fora.

Cada teste aqui MORDE: existe um par "com a cura" / "sem a cura" (ou uma asserção
de espelho) que reprova tanto a regressão quanto a cura exagerada de "desligar o
teclado para sempre".
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import (
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import keyboard as kbd_mod
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session


TIQUES_MINIMOS = 3


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona `config_dir` do session para tmp_path (molde do mouse)."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def test_flag_roundtrip_liga_desliga(tmp_config: Path) -> None:
    """Escreve False, lê False — e o "off" fica GRAVADO, não apagado."""
    session.save_keyboard_emulation(False)
    flag = tmp_config / "keyboard_emulation.flag"
    assert flag.exists()
    assert json.loads(flag.read_text("utf-8")) == {"enabled": False}
    assert session.load_keyboard_preference() is False

    session.save_keyboard_emulation(True)
    assert session.load_keyboard_preference() is True


def test_flag_ausente_e_nunca_configurada(tmp_config: Path) -> None:
    """Sem arquivo = "nunca decidiu": o default histórico (LIGADO) vale."""
    assert session.load_keyboard_preference() is None
    # `load_keyboard_emulation_enabled`, que ninguém em produção chamava. O
    assert DaemonConfig().keyboard_emulation_enabled is True


def test_conteudo_legado_e_lixo_contam_como_ligada(tmp_config: Path) -> None:
    flag = tmp_config / "keyboard_emulation.flag"
    flag.write_text("1\n", encoding="utf-8")
    assert session.load_keyboard_preference() is True
    flag.write_text("{nao é json", encoding="utf-8")
    assert session.load_keyboard_preference() is True
    flag.write_text(json.dumps({"enabled": "sim"}), encoding="utf-8")
    assert session.load_keyboard_preference() is True


def test_save_e_load_sao_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """I/O quebrado não derruba o boot nem o IPC — e vira "nunca decidiu"."""

    def _boom(*_a: object, **_k: object) -> Path:
        raise OSError("config dir indisponível")

    monkeypatch.setattr(session, "config_dir", _boom)
    session.save_keyboard_emulation(False)
    assert session.load_keyboard_preference() is None


class _DaemonStub:
    """Dublê mínimo para o subsystem de teclado (sem /dev/uinput)."""

    def __init__(self, enabled: bool) -> None:
        self.config = DaemonConfig(keyboard_emulation_enabled=enabled)
        self._keyboard_device: Any = None
        self._osk_controller: Any = None
        self._touchpad_reader: Any = None


@pytest.fixture()
def uinput_de_mentira(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """`UinputKeyboardDevice` que sempre sobe — senão o gate seria invisível."""
    fabrica = MagicMock()
    device = MagicMock()
    device.start.return_value = True
    fabrica.return_value = device
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_keyboard.UinputKeyboardDevice",
        fabrica,
    )
    monkeypatch.setattr(kbd_mod, "_start_touchpad_reader", lambda _d: None)
    return fabrica


def test_start_recusa_criar_device_com_interruptor_desligado(
    uinput_de_mentira: MagicMock,
) -> None:
    """Molde de `subsystems/mouse.py`: desligada, o device NÃO nasce."""
    d = _DaemonStub(enabled=False)
    assert kbd_mod.start_keyboard_emulation(d) is False  # type: ignore[arg-type]
    assert d._keyboard_device is None
    assert uinput_de_mentira.call_count == 0


def test_start_cria_device_com_interruptor_ligado(
    uinput_de_mentira: MagicMock,
) -> None:
    """Espelho — impede a cura de virar "o teclado nunca mais sobe"."""
    d = _DaemonStub(enabled=True)
    assert kbd_mod.start_keyboard_emulation(d) is True  # type: ignore[arg-type]
    assert d._keyboard_device is not None
    assert uinput_de_mentira.call_count == 1


def test_setter_desliga_destroi_o_device_e_persiste(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`set_keyboard_emulation(False)`: device destruído + escolha em disco."""
    paradas: list[bool] = []

    def fake_start(daemon: Any) -> bool:
        daemon._keyboard_device = MagicMock()
        return True

    def fake_stop(daemon: Any) -> None:
        daemon._keyboard_device = None
        paradas.append(True)

    monkeypatch.setattr(kbd_mod, "start_keyboard_emulation", fake_start)
    monkeypatch.setattr(kbd_mod, "stop_keyboard_emulation", fake_stop)

    daemon = Daemon(controller=FakeController(transport="usb"))
    assert daemon.set_keyboard_emulation(True) is True
    assert daemon._keyboard_device is not None
    assert session.load_keyboard_preference() is True

    assert daemon.set_keyboard_emulation(False) is True
    assert daemon._keyboard_device is None
    assert daemon.config.keyboard_emulation_enabled is False
    assert paradas == [True]
    assert session.load_keyboard_preference() is False


def _mk_states(n: int) -> list[Any]:
    from hefesto_dualsense4unix.core.controller import ControllerState

    return [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(n)
    ]


async def _boot_com_preferencia(
    monkeypatch: pytest.MonkeyPatch, pref: bool | None
) -> tuple[Daemon, list[Any]]:
    starts: list[Any] = []

    def fake_start(daemon: Any) -> bool:
        starts.append(daemon)
        daemon._keyboard_device = MagicMock()
        return True

    async def noop_restore(daemon: Any) -> None:
        return None

    monkeypatch.setattr(kbd_mod, "start_keyboard_emulation", fake_start)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.connection.restore_last_profile", noop_restore
    )
    monkeypatch.setattr(session, "load_keyboard_preference", lambda: pref)

    daemon = Daemon(
        controller=FakeController(transport="usb", states=_mk_states(40)),
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=True,
        ),
    )
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    daemon.stop()
    await task
    return daemon, starts


@pytest.mark.asyncio
async def test_boot_respeita_flag_desligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag `{"enabled": false}` vence o default True — e o device não sobe."""
    daemon, starts = await _boot_com_preferencia(monkeypatch, False)
    assert daemon.config.keyboard_emulation_enabled is False
    assert starts == []


@pytest.mark.asyncio
async def test_boot_sem_flag_mantem_o_teclado_ligado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Espelho: sem decisão dela nada muda (compat com o histórico)."""
    daemon, starts = await _boot_com_preferencia(monkeypatch, None)
    assert daemon.config.keyboard_emulation_enabled is True
    assert len(starts) == 1


class _FakeDaemonIpc:
    def __init__(self, enabled: bool = True, ok: bool = True) -> None:
        self.config = DaemonConfig(keyboard_emulation_enabled=enabled)
        self._keyboard_device: Any = MagicMock() if enabled else None
        self._emulation_suppressed = False
        self.chamadas: list[bool] = []
        self._ok = ok

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        self.chamadas.append(enabled)
        self.config.keyboard_emulation_enabled = enabled
        self._keyboard_device = MagicMock() if (enabled and self._ok) else None
        return self._ok if enabled else True


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: object) -> None:
        self.daemon = daemon  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_ipc_keyboard_emulation_set_desliga_e_reporta() -> None:
    d = _FakeDaemonIpc(enabled=True)
    res = await _Handlers(d)._handle_keyboard_emulation_set({"enabled": False})
    assert d.chamadas == [False]
    assert res["status"] == "ok"
    assert res["enabled"] is False
    assert res["keyboard_emulation"]["enabled"] is False
    assert res["keyboard_emulation"]["bloqueio"] == "desligada"


@pytest.mark.asyncio
async def test_ipc_keyboard_emulation_set_liga() -> None:
    d = _FakeDaemonIpc(enabled=False)
    res = await _Handlers(d)._handle_keyboard_emulation_set({"enabled": True})
    assert d.chamadas == [True]
    assert res["enabled"] is True
    assert res["keyboard_emulation"]["despachando"] is True
    assert res["keyboard_emulation"]["bloqueio"] is None


@pytest.mark.asyncio
async def test_ipc_exige_enabled_boolean() -> None:
    with pytest.raises(ValueError, match="enabled"):
        await _Handlers(_FakeDaemonIpc())._handle_keyboard_emulation_set(
            {"enabled": "sim"}
        )
    with pytest.raises(ValueError, match="daemon"):
        await _Handlers(None)._handle_keyboard_emulation_set({"enabled": True})


@pytest.mark.asyncio
async def test_metodo_registrado_no_ipc_server() -> None:
    """O handler existe E está no dicionário do dispatcher."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    srv = IpcServer.__new__(IpcServer)
    IpcServer.__post_init__(srv)
    assert "keyboard.emulation.set" in srv._handlers


def test_payload_diz_o_motivo_do_silencio() -> None:
    """Os três estados de `bloqueio`, e o `None` de quando emite."""
    d = _FakeDaemonIpc(enabled=True)
    h = _Handlers(d)

    assert h._keyboard_emulation_payload()["bloqueio"] is None

    d._emulation_suppressed = True
    assert h._keyboard_emulation_payload()["bloqueio"] == "modo_jogo"
    d._emulation_suppressed = False

    d._keyboard_device = None
    assert h._keyboard_emulation_payload()["bloqueio"] == "sem_device"

    d.config.keyboard_emulation_enabled = False
    assert h._keyboard_emulation_payload()["bloqueio"] == "desligada"


class _HandlersStatus(IpcHandlersMixin):
    def __init__(self, daemon: object, store: StateStore, controller: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = store
        self.controller = controller


@pytest.mark.asyncio
async def test_status_publica_o_bloco_do_teclado() -> None:
    """`daemon.status` carrega `keyboard_emulation` — a janela lê daqui."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon._keyboard_device = MagicMock()
    h = _HandlersStatus(daemon, daemon.store, daemon.controller)
    res = await h._handle_daemon_status({})
    bloco = dict(res["keyboard_emulation"])
    assert isinstance(bloco.pop("osk_disponivel"), bool), (
        "o status parou de dizer se existe teclado na tela — a janela volta a "
        "não ter como saber se o L3 abre alguma coisa"
    )
    assert bloco == {
        "enabled": True,
        "device_ativo": True,
        "despachando": True,
        "bloqueio": None,
    }


@pytest.mark.asyncio
async def test_state_full_publica_o_mesmo_bloco() -> None:
    """`daemon.state_full` e `daemon.status` não podem divergir.

    Mesma razão do `_window_detect_payload`: duas respostas com verdades
    diferentes sobre o mesmo estado é o que fazia as abas discordarem.
    """
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon._keyboard_device = MagicMock()
    h = _HandlersStatus(daemon, daemon.store, daemon.controller)
    cheio = await h._handle_daemon_state_full({})
    status = await h._handle_daemon_status({})
    assert cheio["keyboard_emulation"] == status["keyboard_emulation"]
    assert cheio["keyboard_emulation"]["bloqueio"] is None
    assert cheio["steam_input"] == {"excecao_ativa": False}
    daemon._steam_input_excecao = True  # type: ignore[attr-defined]
    cheio = await h._handle_daemon_state_full({})
    assert cheio["steam_input"] == {"excecao_ativa": True}


class _SnapR1:
    buttons_pressed: ClassVar[list[str]] = ["r1"]


async def _um_tique_com_r1(monkeypatch: pytest.MonkeyPatch) -> list[frozenset[str]]:
    """Roda o poll loop com R1 pressionado e devolve o que o teclado recebeu."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
    fc = FakeController(transport="usb", states=_mk_states(80))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _SnapR1()
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    despachos: list[frozenset[str]] = []
    kbd = MagicMock()
    kbd.dispatch.side_effect = lambda bp: despachos.append(bp)
    daemon._keyboard_device = kbd
    daemon._gamepad_device = None
    daemon._emulation_suppressed = False

    task = asyncio.create_task(daemon.run())
    limite = time.monotonic() + 5.0
    while daemon.store.counter("poll.tick") < TIQUES_MINIMOS:
        if time.monotonic() > limite:
            break
        await asyncio.sleep(0.002)
    daemon.stop()
    await task
    assert daemon.store.counter("poll.tick") >= TIQUES_MINIMOS, (
        "o poll loop não completou os tiques mínimos em 5 s — o cenário não "
        "chegou a ser exercitado, então nada abaixo prova coisa alguma"
    )
    return despachos


@pytest.mark.asyncio
async def test_teclado_emite_no_desktop_no_mesmo_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Espelho legítimo: sem jogo com autoridade, o R1 continua chegando."""
    despachos = await _um_tique_com_r1(monkeypatch)
    assert any("r1" in bp for bp in despachos), despachos
