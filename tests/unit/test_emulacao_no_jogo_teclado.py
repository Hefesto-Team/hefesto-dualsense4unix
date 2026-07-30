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
    CALADA_VPAD_SUSPENSO,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import keyboard as kbd_mod
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session


#: Tiques de poll que o cenário precisa completar para que o gate de despacho
#: tenha sido exercitado de verdade. Baixo de propósito: o que importa é que o
#: laço RODOU, não que rodou rápido.
TIQUES_MINIMOS = 3


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona `config_dir` do session para tmp_path (molde do mouse)."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# E1 (b) — a flag que o teclado nunca teve
# ---------------------------------------------------------------------------


def test_flag_roundtrip_liga_desliga(tmp_config: Path) -> None:
    """Escreve False, lê False — e o "off" fica GRAVADO, não apagado."""
    session.save_keyboard_emulation(False)
    flag = tmp_config / "keyboard_emulation.flag"
    assert flag.exists()
    assert json.loads(flag.read_text("utf-8")) == {"enabled": False}
    assert session.load_keyboard_preference() is False
    assert session.load_keyboard_emulation_enabled() is False

    session.save_keyboard_emulation(True)
    assert session.load_keyboard_preference() is True
    assert session.load_keyboard_emulation_enabled() is True


def test_flag_ausente_e_nunca_configurada(tmp_config: Path) -> None:
    """Sem arquivo = "nunca decidiu": o default histórico (LIGADO) vale.

    Espelho da assimetria deliberada com o mouse (que devolve False nesse caso):
    desligar o teclado num upgrade silencioso tiraria o teclado virtual do
    sistema (L3/R3) e as três regiões do touchpad de quem já os usava.
    """
    assert session.load_keyboard_preference() is None
    assert session.load_keyboard_emulation_enabled() is True
    assert session.load_keyboard_emulation_enabled(default=False) is False


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
    session.save_keyboard_emulation(False)  # não levanta
    assert session.load_keyboard_preference() is None


# ---------------------------------------------------------------------------
# E1 (a) — o interruptor passa a ter dentes: o device não nasce desligado
# ---------------------------------------------------------------------------


class _DaemonStub:
    """Dublê mínimo para o subsystem de teclado (sem /dev/uinput)."""

    def __init__(self, enabled: bool) -> None:
        self.config = DaemonConfig(keyboard_emulation_enabled=enabled)
        self._keyboard_device: Any = None
        self._osk_controller: Any = None
        self._touchpad_reader: Any = None


@pytest.fixture()
def uinput_de_mentira(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """`UinputKeyboardDevice` que sempre sobe — senão o gate seria invisível.

    Sem isto o teste passaria por ausência de `/dev/uinput` no runner (o start
    real falharia e o device ficaria None de qualquer jeito), e arrancar a cura
    NÃO reprovaria — teste que não morde.
    """
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
    # É o par save/load que faz a escolha atravessar o restart — sem ele o
    # default True voltava a valer a cada boot.
    assert session.load_keyboard_preference() is False


# ---------------------------------------------------------------------------
# E1 (b) — o boot obedece à flag
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# E1 (c)/(d) — IPC e estado publicado
# ---------------------------------------------------------------------------


class _FakeDaemonIpc:
    def __init__(self, enabled: bool = True, ok: bool = True) -> None:
        self.config = DaemonConfig(keyboard_emulation_enabled=enabled)
        self._keyboard_device: Any = MagicMock() if enabled else None
        self._emulation_suppressed = False
        self._steam_input_vpad_suspenso = False
        self.chamadas: list[bool] = []
        self._ok = ok

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        self.chamadas.append(enabled)
        self.config.keyboard_emulation_enabled = enabled
        self._keyboard_device = MagicMock() if (enabled and self._ok) else None
        return self._ok if enabled else True

    def _jogo_no_controle_do_desktop(self) -> str | None:
        return CALADA_VPAD_SUSPENSO if self._steam_input_vpad_suspenso else None


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
    """O handler existe E está no dicionário do dispatcher.

    Sem o registro em `ipc_server.py` o método responde "método desconhecido" e
    a janela não tem como falar com ele.
    """
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    srv = IpcServer.__new__(IpcServer)
    IpcServer.__post_init__(srv)
    assert "keyboard.emulation.set" in srv._handlers


def test_payload_diz_o_motivo_do_silencio() -> None:
    """Os quatro estados de `bloqueio`, incluindo o defeito medido de 29/07."""
    d = _FakeDaemonIpc(enabled=True)
    h = _Handlers(d)

    assert h._keyboard_emulation_payload()["bloqueio"] is None

    d._emulation_suppressed = True
    assert h._keyboard_emulation_payload()["bloqueio"] == "modo_jogo"
    d._emulation_suppressed = False

    d._steam_input_vpad_suspenso = True
    payload = h._keyboard_emulation_payload()
    assert payload["bloqueio"] == CALADA_VPAD_SUSPENSO
    assert payload["despachando"] is False
    assert payload["enabled"] is True  # o interruptor dela continua LIGADO
    d._steam_input_vpad_suspenso = False

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
    assert res["keyboard_emulation"] == {
        "enabled": True,
        "device_ativo": True,
        "despachando": True,
        "bloqueio": None,
    }
    # E o par da queixa dela: com o vpad suspenso pelo Steam Input, o mesmo
    # status passa a dizer POR QUE o teclado está calado.
    daemon._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    res = await h._handle_daemon_status({})
    assert res["keyboard_emulation"]["bloqueio"] == CALADA_VPAD_SUSPENSO


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
    # JOGO-01/Entrega 2: o PAR que explica "a emulação parece desligada com o
    # jogo aberto" — é o dado de que a aba Emulação precisa para não chamar a
    # partida de "Controlar o PC" (e não deixar cinza o botão que a cura).
    assert cheio["steam_input"] == {"excecao_ativa": False, "vpad_suspenso": False}
    daemon._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    daemon._steam_input_excecao = True  # type: ignore[attr-defined]
    cheio = await h._handle_daemon_state_full({})
    assert cheio["steam_input"] == {"excecao_ativa": True, "vpad_suspenso": True}
    assert cheio["keyboard_emulation"]["bloqueio"] == CALADA_VPAD_SUSPENSO


# ---------------------------------------------------------------------------
# E2 — a exclusão mútua para de ler "vpad ausente" como permissão
# ---------------------------------------------------------------------------


class _SnapR1:
    buttons_pressed: ClassVar[list[str]] = ["r1"]


async def _um_tique_com_r1(
    monkeypatch: pytest.MonkeyPatch, *, vpad_suspenso: bool
) -> list[frozenset[str]]:
    """Roda o poll loop com R1 pressionado e devolve o que o teclado recebeu.

    Cenário exato do journal dela: `_gamepad_device` None (a exceção do Steam
    Input derrubou o vpad), modo jogo DESLIGADO, teclado de desktop vivo.
    """
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
            keyboard_emulation_enabled=False,  # device injetado abaixo
        ),
    )
    despachos: list[frozenset[str]] = []
    kbd = MagicMock()
    kbd.dispatch.side_effect = lambda bp: despachos.append(bp)
    daemon._keyboard_device = kbd
    daemon._gamepad_device = None
    daemon._emulation_suppressed = False
    daemon._steam_input_vpad_suspenso = vpad_suspenso  # type: ignore[attr-defined]

    task = asyncio.create_task(daemon.run())
    # ESPERA POR CONDIÇÃO, não por relógio. A primeira versão dormia 0,06 s fixo
    # e conferia `poll.tick >= 3` depois — com 200 Hz isso "deveria" dar doze
    # tiques. Passou aqui, passou no CI em 3.11 e 3.12, e REPROVOU em 3.10 no
    # mesmo run da tag v0.4.0: runner carregado não garante fatia de CPU, e o
    # agendamento de tasks do asyncio mudou entre as versões. Teste de gate de
    # despacho não pode depender de quanto o runner estava ocupado.
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
async def test_teclado_nao_emite_com_o_vpad_suspenso_pelo_steam_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O R1 NÃO chega ao teclado virtual dentro do jogo da allowlist.

    MORDE: sem o termo novo do predicado (`if not gamepad_dispatched:` sozinho),
    o teclado recebe `{"r1"}` a cada tique — que no mapa default é
    `KEY_LEFTALT`+`KEY_TAB`, o Alt+Tab que arrancava o foco da partida dela.
    """
    despachos = await _um_tique_com_r1(monkeypatch, vpad_suspenso=True)
    assert all("r1" not in bp for bp in despachos), despachos
    # O flush da borda (solta o que estiver preso) é um dispatch VAZIO, e é ele
    # que impede o `KEY_LEFTALT` de ficar segurado 18 s como no journal dela.
    assert frozenset() in despachos


@pytest.mark.asyncio
async def test_teclado_emite_no_desktop_no_mesmo_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Espelho legítimo: sem jogo com autoridade, o R1 continua chegando.

    É o assert que impede a cura de virar "desligar o teclado para sempre" — um
    teste que só olhasse o caso suspenso passaria com o gate quebrado ao
    contrário.
    """
    despachos = await _um_tique_com_r1(monkeypatch, vpad_suspenso=False)
    assert any("r1" in bp for bp in despachos), despachos


def test_predicado_nomeia_o_motivo() -> None:
    daemon = Daemon(controller=FakeController(transport="usb"))
    assert daemon._jogo_no_controle_do_desktop() is None
    daemon._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    assert daemon._jogo_no_controle_do_desktop() == CALADA_VPAD_SUSPENSO


def test_autoridade_sticky_sozinha_nao_cala_o_desktop() -> None:
    """`display_authority == "game"` NÃO é o sinal deste gate — de propósito.

    Ele é sticky e tem defeito conhecido e não corrigido: cai de `game` para
    `daemon` ~30 s depois COM O JOGO ABERTO (ver `reverter_modo_jogo_padrao`),
    e os R1 dela saíram 4,5 min depois da suspensão — a cura falharia no caso
    que a motivou. E, na saída do jogo, a stickiness deixaria mouse/teclado
    mudos por até 30 s ("o controle morreu"). Este teste é o cadeado contra a
    troca silenciosa de sinal.
    """
    daemon = Daemon(controller=FakeController(transport="usb"))

    class _Sinal:
        authority = "game"

    daemon._game_signal = _Sinal()  # type: ignore[assignment]
    assert daemon.display_authority == "game"
    assert daemon._jogo_no_controle_do_desktop() is None


def test_flush_e_log_uma_vez_por_episodio() -> None:
    """Borda: solta a tecla presa 1x; a 60 Hz não pode inundar o journal."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    kbd = MagicMock()
    daemon._keyboard_device = kbd

    daemon._calar_emulacao_de_desktop(CALADA_VPAD_SUSPENSO, frozenset({"r1"}))
    assert daemon._emu_calada_motivo == CALADA_VPAD_SUSPENSO
    assert kbd.dispatch.call_args_list[0][0][0] == frozenset()
    chamadas_apos_borda = kbd.dispatch.call_count

    for _ in range(30):
        daemon._calar_emulacao_de_desktop(CALADA_VPAD_SUSPENSO, frozenset({"r1"}))
    assert kbd.dispatch.call_count == chamadas_apos_borda

    # Saída do episódio: semeia o baseline sem emitir (prime), senão um botão
    # ainda segurado viraria press NOVO — Alt+Tab fantasma ao fechar o jogo.
    daemon._liberar_emulacao_de_desktop(frozenset({"r1"}))
    assert daemon._emu_calada_motivo == ""
    kbd.prime.assert_called_once_with(frozenset({"r1"}))


# "Nada em excesso." — Sólon de Atenas
