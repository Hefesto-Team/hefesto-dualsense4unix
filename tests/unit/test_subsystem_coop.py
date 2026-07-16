"""FEAT-DSX-COOP-LOCAL-01 + FEAT-DSX-CONTROLLER-IDENTITY-01 — CoopManager.

Cobre a reconciliação (sync) com fakes de EvdevReader/UinputGamepad: cria um
jogador por controle físico ALÉM do primário (keyed por IDENTIDADE/MAC, cada um
com reader+grab+vpad próprios), repassa o input ao vpad certo (forward_all),
desmonta no hotplug-out / ao desligar o co-op / sem gamepad virtual e recria
quando o node evdev do MESMO controle muda (re-enumeração). Sem hardware real.

BUG-COOP-GRAB-PENDING-VPAD-01: o vpad NUNCA nasce sem grab CONFIRMADO ("held").
Grab "pending" registra o jogador sem vpad (promovido no tick quando o grab
confirma); "pending" → "failed" derruba sem jamais criar vpad (retry no sync).

FEAT-COOP-PLAYER-LED-01: com o co-op ativo cada controle acende o padrão
canônico do SEU jogador (P1 primário, P2.. secundários) via sysfs (fakeado
aqui — hermético); desligar o co-op / perder um jogador restaura o padrão do
perfil ativo.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, player_led_pattern

MAC_P1 = "aabbcc001100"
MAC_P2 = "aabbcc001122"
MAC_P3 = "aabbcc001133"
MAC_P4 = "aabbcc001144"

PROFILE_LEDS = (False, False, False, False, True)


class _FakeReader:
    grab_ok: bool = True  # knob de classe: EVIOCGRAB aceita?
    # knob de classe: estado após set_grab(True) bem-sucedido — "held" simula o
    # device já aberto (grab imediato); "pending" simula a thread do reader
    # ainda sem abrir o device (BUG-COOP-GRAB-PENDING-VPAD-01).
    grab_result: str = "held"

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.started = False
        self.grabbed: bool | None = None
        self.stopped = False
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=200, ly=50, rx=128, ry=128, l2_raw=10, r2_raw=20,
            buttons_pressed=frozenset({"cross"}),
        )

    def start(self) -> bool:
        self.started = True
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grabbed = grab
        if grab and not type(self).grab_ok:
            self.grab_state = "failed"
            return False
        self.grab_state = type(self).grab_result if grab else "off"
        return True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> Any:
        return self.snap


class _FakeVpad:
    #: Registro de TODOS os vpads criados (invariante "nunca vpad sem held").
    created: ClassVar[list[_FakeVpad]] = []

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.flavor = ""
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []
        # FEAT-VPAD-FF-PASSTHROUGH-01: sink de rumble injetado + nº de pumps.
        self.rumble_sink: Any = None
        self.ff_pumps = 0

    @classmethod
    def for_flavor(cls, flavor: str, *, rumble_sink: Any = None) -> _FakeVpad:
        inst = cls()
        inst.flavor = flavor
        inst.rumble_sink = rumble_sink
        cls.created.append(inst)
        return inst

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.stopped = True

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)

    def pump_ff(self) -> None:
        self.ff_pumps += 1


class _FakeLedNode:
    """Nó sysfs falso: registra os padrões de player-LED escritos nele."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.patterns: list[tuple[bool, bool, bool, bool, bool]] = []

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.patterns.append(bits)
        return self.ok


def _make_daemon(
    *,
    coop: bool = True,
    gamepad: bool = True,
    primary_uniq: str | None = MAC_P1,
    primary_path: str | None = "/dev/input/event5",
    desired_leds: tuple[bool, bool, bool, bool, bool] | None = None,
) -> Any:
    evdev = SimpleNamespace(
        _device_path=Path(primary_path) if primary_path else None
    )
    led_calls: list[tuple[bool, bool, bool, bool, bool]] = []
    controller = SimpleNamespace(
        _evdev=evdev,
        primary_uniq=primary_uniq,
        # FEAT-COOP-PLAYER-LED-01: o backend guarda o último padrão broadcast
        # em `_desired.player_leds`; o coop o relê para reverter.
        _desired=SimpleNamespace(player_leds=desired_leds),
        set_player_leds=led_calls.append,
    )
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=coop, gamepad_flavor="dualsense"),
        _gamepad_device=object() if gamepad else None,
        controller=controller,
        _coop_manager=None,
        led_calls=led_calls,
    )


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeReader.grab_ok = True
    _FakeReader.grab_result = "held"
    _FakeVpad.created = []
    # O gate de listdir (InputDirWatch) fica sempre "sujo" nos testes: aqui o
    # hotplug é simulado trocando o mapping de discover, não mexendo em
    # /dev/input real.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
        lambda self: True,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.UinputGamepad", _FakeVpad
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.normalize_flavor",
        lambda f: f or "dualsense",
    )
    # Hermético: NUNCA tocar o /sys/class/leds real (na máquina da mantenedora
    # há um DualSense de verdade plugado). Testes de LED sobrescrevem com nós
    # falsos via _set_led_nodes.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {}
    )


def _set_evdevs(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {mac: Path(p) for mac, p in mapping.items()},
    )


def _set_led_nodes(
    monkeypatch: pytest.MonkeyPatch, *macs: str
) -> dict[str, _FakeLedNode]:
    nodes = {mac: _FakeLedNode() for mac in macs}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: nodes
    )
    return nodes


def _watch_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula tick quieto: /dev/input não mudou desde o último poll."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
        lambda self: False,
    )


def test_sync_cria_secundario_excluindo_o_primario(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1))
    mgr.sync()

    assert mgr.player_count() == 2  # P1 (primário) + 1 secundário
    assert list(mgr._players) == [MAC_P2]  # primário (por MAC) excluído
    player = mgr._players[MAC_P2]
    assert player.reader.started is True
    assert player.reader.grabbed is True  # grab: jogo vê só o vpad, não o cru
    assert player.reader.target_uniq == MAC_P2  # reconexões miram ESTE controle
    assert player.player_index == 2
    assert player.vpad is not None and player.vpad.started is True


def test_sync_exclui_primario_por_mac_mesmo_com_path_stale(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Raiz da duplicação do 3º controle: o path do reader do primário fica
    # None/stale durante hotplug. Com identidade por MAC, o primário continua
    # excluído e NÃO nasce vpad duplicado para o controle do P1.
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1, primary_path=None))
    mgr.sync()

    assert list(mgr._players) == [MAC_P2]


def test_sync_terceiro_controle_vira_p3(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    assert mgr.player_count() == 2

    _set_evdevs(
        monkeypatch,
        {
            MAC_P1: "/dev/input/event5",
            MAC_P2: "/dev/input/event7",
            MAC_P3: "/dev/input/event9",
        },
    )
    mgr.sync()
    assert mgr.player_count() == 3
    assert set(mgr._players) == {MAC_P2, MAC_P3}
    assert mgr._players[MAC_P3].player_index == 3


def test_sync_recria_quando_node_do_mesmo_mac_muda(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    old = mgr._players[MAC_P2]

    # Re-enumeração (storm/replug): mesmo MAC, node novo.
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event25"})
    mgr.sync()

    assert old.reader.stopped is True
    assert old.vpad is not None and old.vpad.stopped is True
    assert mgr._players[MAC_P2].evdev_path == "/dev/input/event25"


def test_spawn_sem_grab_confirmado_nao_cria_vpad(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BUG-COOP-GRAB-SILENT-FAIL-01: EVIOCGRAB recusado → sem vpad (o físico
    # dobraria o input no jogo); retry natural no próximo sync.
    _FakeReader.grab_ok = False
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()

    assert mgr.player_count() == 1
    assert mgr._players == {}
    assert _FakeVpad.created == []  # NUNCA nasceu vpad sem grab confirmado

    # Grab voltou a funcionar → o retry do sync cria o jogador.
    _FakeReader.grab_ok = True
    mgr.sync()
    assert mgr.player_count() == 2


def test_grab_pendente_registra_jogador_sem_vpad(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BUG-COOP-GRAB-PENDING-VPAD-01: set_grab "aceito" com device ainda não
    # aberto (pending) NÃO pode criar o vpad — antes, uma recusa tardia
    # (EBUSY) deixava até ~2s de input dobrado no jogo.
    _FakeReader.grab_result = "pending"
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()

    player = mgr._players[MAC_P2]
    assert player.vpad is None
    assert _FakeVpad.created == []
    # forward_all com jogador pendente: não repassa nada e não explode.
    mgr.forward_all()
    assert player.vpad is None


def test_grab_pendente_promovido_quando_held_no_forward_all(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeReader.grab_result = "pending"
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players[MAC_P2]
    assert player.vpad is None

    # A thread do reader abriu o device e o EVIOCGRAB confirmou.
    player.reader.grab_state = "held"
    mgr.forward_all()  # promoção acontece no tick, sem esperar o sync (~2s)

    assert player.vpad is not None and player.vpad.started is True
    assert player.vpad.analog[-1] == {
        "lx": 200, "ly": 50, "rx": 128, "ry": 128, "l2": 10, "r2": 20
    }


def test_grab_pendente_promovido_no_sync_em_tick_quieto(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeReader.grab_result = "pending"
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players[MAC_P2]

    # Tick quieto (/dev/input não mudou): a promoção NÃO depende do watch —
    # confirmar o grab não altera o conteúdo de /dev/input.
    _watch_quiet(monkeypatch)
    player.reader.grab_state = "held"
    mgr.sync()

    assert player.vpad is not None and player.vpad.started is True


def test_grab_pendente_que_falha_nunca_cria_vpad_e_respawna(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeReader.grab_result = "pending"
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players[MAC_P2]

    # O EVIOCGRAB real (na thread do reader) foi recusado: pending → failed.
    player.reader.grab_state = "failed"
    mgr.forward_all()

    assert MAC_P2 not in mgr._players  # derrubado…
    assert _FakeVpad.created == []  # …sem NUNCA ter criado vpad
    assert player.reader.stopped is True

    # Retry: mesmo em tick quieto, o próximo sync respawna (grab agora ok).
    _watch_quiet(monkeypatch)
    _FakeReader.grab_result = "held"
    mgr.sync()
    new = mgr._players[MAC_P2]
    assert new.vpad is not None and new.vpad.started is True


def test_sync_derruba_player_cujo_grab_degradou(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players[MAC_P2]

    # O loop de reconexão do reader reportou falha de grab (ex.: EBUSY).
    player.reader.grab_state = "failed"
    mgr.sync()

    assert player.reader.stopped is True
    # Recriado limpo no mesmo ciclo (retry imediato do hotplug-IN).
    assert MAC_P2 in mgr._players and mgr._players[MAC_P2] is not player


def test_forward_all_repassa_snapshot_ao_vpad(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    mgr.forward_all()

    vpad = mgr._players[MAC_P2].vpad
    assert vpad is not None
    assert vpad.analog[-1] == {"lx": 200, "ly": 50, "rx": 128, "ry": 128, "l2": 10, "r2": 20}
    assert vpad.buttons[-1] == frozenset({"cross"})
    # FEAT-VPAD-FF-PASSTHROUGH-01: o vpad do jogador nasce com sink de rumble
    # (FF do jogo → controle DELE) e o tick bombeia o FF.
    assert vpad.rumble_sink is not None
    assert vpad.ff_pumps == 1


def test_sync_remove_no_hotplug_out(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon())
    mgr.sync()
    player = mgr._players[MAC_P2]

    # Secundário desconectou: só o primário sobrou.
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5"})
    mgr.sync()

    assert mgr.player_count() == 1
    assert player.reader.grabbed is False  # soltou o grab
    assert player.reader.stopped is True
    assert player.vpad is not None and player.vpad.stopped is True


def test_desligar_coop_desmonta_tudo(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    daemon = _make_daemon(coop=True)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert mgr.player_count() == 2

    daemon.config.coop_enabled = False
    mgr.sync()  # should_be_active=False → desmonta
    assert mgr.player_count() == 1
    assert mgr._players == {}


def test_should_be_active_gates(patched: None) -> None:
    assert CoopManager(_make_daemon(coop=True, gamepad=True)).should_be_active() is True
    assert CoopManager(_make_daemon(coop=False, gamepad=True)).should_be_active() is False
    assert CoopManager(_make_daemon(coop=True, gamepad=False)).should_be_active() is False


def test_sync_sem_gamepad_nao_cria(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon(gamepad=False))
    mgr.sync()
    assert mgr.player_count() == 1  # gamepad virtual desligado → co-op inativo


# --- player LEDs por jogador (FEAT-COOP-PLAYER-LED-01) ----------------------


def test_padroes_canonicos_por_indice() -> None:
    assert player_led_pattern(1) == (False, False, True, False, False)
    assert player_led_pattern(2) == (False, True, False, True, False)
    assert player_led_pattern(3) == (True, False, True, False, True)
    assert player_led_pattern(4) == (True, True, False, True, True)
    # P5+ sem padrão oficial → todos acesos (nunca colide com P1..P4).
    assert player_led_pattern(5) == (True, True, True, True, True)


def test_coop_aplica_padrao_canonico_por_jogador(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes = _set_led_nodes(monkeypatch, MAC_P1, MAC_P2, MAC_P3)
    _set_evdevs(
        monkeypatch,
        {
            MAC_P1: "/dev/input/event5",
            MAC_P2: "/dev/input/event7",
            MAC_P3: "/dev/input/event9",
        },
    )
    mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1))
    mgr.sync()

    # Cada controle mostra o padrão do SEU jogador — dá pra saber quem é quem.
    assert nodes[MAC_P1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC_P2].patterns[-1] == player_led_pattern(2)
    assert nodes[MAC_P3].patterns[-1] == player_led_pattern(3)


def test_indice_de_jogador_estavel_e_reusado_apos_saida(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes = _set_led_nodes(monkeypatch, MAC_P1, MAC_P2, MAC_P3, MAC_P4)
    _set_evdevs(
        monkeypatch,
        {
            MAC_P1: "/dev/input/event5",
            MAC_P2: "/dev/input/event7",
            MAC_P3: "/dev/input/event9",
        },
    )
    mgr = CoopManager(_make_daemon())
    mgr.sync()

    # P2 sai; P3 NÃO é renumerado (segue jogador 3)…
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P3: "/dev/input/event9"})
    mgr.sync()
    assert mgr._players[MAC_P3].player_index == 3

    # …e o próximo controle que entrar reusa o índice 2 (menor livre).
    _set_evdevs(
        monkeypatch,
        {
            MAC_P1: "/dev/input/event5",
            MAC_P3: "/dev/input/event9",
            MAC_P4: "/dev/input/event11",
        },
    )
    mgr.sync()
    assert mgr._players[MAC_P4].player_index == 2
    assert nodes[MAC_P4].patterns[-1] == player_led_pattern(2)
    assert nodes[MAC_P3].patterns[-1] == player_led_pattern(3)


def test_desligar_coop_reverte_player_leds_do_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_led_nodes(monkeypatch, MAC_P1, MAC_P2)
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    daemon = _make_daemon(desired_leds=PROFILE_LEDS)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert daemon.led_calls == []  # co-op ativo: nada de broadcast

    daemon.config.coop_enabled = False
    mgr.sync()

    # Reversão = re-emitir o padrão do perfil pelo caminho público broadcast.
    assert daemon.led_calls == [PROFILE_LEDS]
    # Idempotente: novo tick inativo não re-emite.
    mgr.sync()
    assert daemon.led_calls == [PROFILE_LEDS]


def test_desligar_coop_sem_padrao_do_perfil_nao_emite_nada(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Nenhum perfil setou player-LED ainda (None): não há o que restaurar —
    # o próximo apply de perfil / reassert do backend cobre.
    _set_led_nodes(monkeypatch, MAC_P1, MAC_P2)
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    daemon = _make_daemon(desired_leds=None)
    mgr = CoopManager(daemon)
    mgr.sync()

    daemon.config.coop_enabled = False
    mgr.sync()
    assert daemon.led_calls == []


def test_jogador_derrubado_tem_led_revertido_ao_padrao_do_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes = _set_led_nodes(monkeypatch, MAC_P1, MAC_P2)
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon(desired_leds=PROFILE_LEDS))
    mgr.sync()
    assert nodes[MAC_P2].patterns[-1] == player_led_pattern(2)

    # Grab degradou E o respawn é recusado: o controle continua plugado mas
    # deixa de ser jogador — o LED volta ao padrão do perfil, não fica preso
    # no padrão de P2.
    mgr._players[MAC_P2].reader.grab_state = "failed"
    _FakeReader.grab_ok = False
    mgr.sync()

    assert MAC_P2 not in mgr._players
    assert nodes[MAC_P2].patterns[-1] == PROFILE_LEDS


def test_sysfs_indisponivel_nao_derruba_o_coop(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Falha de sysfs (BT sem nó, permissão, ambiente sem /sys) = warning e
    # segue: o co-op continua funcional, só sem o LED por jogador.
    def _boom() -> dict[str, Any]:
        raise RuntimeError("sem /sys")

    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", _boom)
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"})
    mgr = CoopManager(_make_daemon(desired_leds=PROFILE_LEDS))
    mgr.sync()

    assert mgr.player_count() == 2
    player = mgr._players[MAC_P2]
    assert player.vpad is not None and player.vpad.started is True


# ---------------------------------------------------------------------------
# LEIGO-01b — o número do jogador tem de ser o que o JOGO vê
# ---------------------------------------------------------------------------


class TestPlayerIndexes:
    """`player_indexes` é a fonte do número no card (nunca a posição na lista)."""

    def test_primario_e_p1_e_secundarios_seguem_o_indice_do_jogador(
        self, patched: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_evdevs(
            monkeypatch,
            {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7",
             MAC_P3: "/dev/input/event9"},
        )
        mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1))
        mgr.sync()

        assert mgr.player_indexes() == {MAC_P1: 1, MAC_P2: 2, MAC_P3: 3}

    def test_indice_reusado_diverge_da_ordem_da_lista(
        self, patched: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso que o `idx+1` da GUI mentia: P2 sai, entra outro e reusa o 2.

        Depois do rodízio, o controle que está em SEGUNDO na lista (MAC_P3) é o
        jogador 3, e o TERCEIRO (MAC_P4) é o jogador 2 — rotular por posição
        trocaria os dois de personagem.
        """
        _set_evdevs(
            monkeypatch,
            {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7",
             MAC_P3: "/dev/input/event9"},
        )
        mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1))
        mgr.sync()
        assert mgr.player_indexes()[MAC_P2] == 2

        # P2 despluga; P4 entra e reusa o índice 2 que ficou livre.
        _set_evdevs(
            monkeypatch,
            {MAC_P1: "/dev/input/event5", MAC_P3: "/dev/input/event9",
             MAC_P4: "/dev/input/event11"},
        )
        mgr.sync()

        assert mgr.player_indexes() == {MAC_P1: 1, MAC_P3: 3, MAC_P4: 2}

    def test_jogador_aguardando_grab_ainda_nao_tem_numero(
        self, patched: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem vpad o jogo não vê jogador nenhum — melhor calar que mentir."""
        _FakeReader.grab_result = "pending"
        _set_evdevs(
            monkeypatch,
            {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"},
        )
        mgr = CoopManager(_make_daemon(primary_uniq=MAC_P1))
        mgr.sync()

        assert mgr._players[MAC_P2].vpad is None
        assert mgr.player_indexes() == {MAC_P1: 1}


class TestResolvePlayerNumbers:
    """A tradução "payload de controllers -> número por card"."""

    @staticmethod
    def _ctrl(uniq: str | None, connected: bool = True) -> dict[str, Any]:
        return {"uniq": uniq, "connected": connected}

    def test_sem_gamepad_virtual_ninguem_e_jogador(self) -> None:
        """Modo desktop/nativo: o controle mexe no PC ou fala direto com o jogo."""
        from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers

        daemon = _make_daemon(gamepad=False)
        assert resolve_player_numbers(
            daemon, [self._ctrl(MAC_P1), self._ctrl(MAC_P2)]
        ) == [None, None]

    def test_coop_desligado_todos_sao_o_jogador_1(self) -> None:
        """O que o jogo vê de verdade: um vpad só, alimentado pelo primário.

        Era exatamente aqui que a GUI mentia — rotulava P1/P2 por posição com o
        co-op DESLIGADO, quando os dois controles moviam o mesmo personagem.
        """
        from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers

        daemon = _make_daemon(coop=False)
        assert resolve_player_numbers(
            daemon, [self._ctrl(MAC_P1), self._ctrl(MAC_P2)]
        ) == [1, 1]

    def test_desconectado_nao_tem_numero(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers

        daemon = _make_daemon(coop=False)
        assert resolve_player_numbers(
            daemon, [self._ctrl(MAC_P1), self._ctrl(MAC_P2, connected=False)]
        ) == [1, None]

    def test_coop_ligado_usa_o_numero_do_daemon(
        self, patched: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers

        _set_evdevs(
            monkeypatch,
            {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7"},
        )
        daemon = _make_daemon(primary_uniq=MAC_P1)
        mgr = CoopManager(daemon)
        daemon._coop_manager = mgr
        mgr.sync()

        assert resolve_player_numbers(
            daemon, [self._ctrl(MAC_P1), self._ctrl(MAC_P2)]
        ) == [1, 2]

    def test_controle_sem_mac_nao_recebe_numero_chutado(
        self, patched: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.coop import resolve_player_numbers

        _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5"})
        daemon = _make_daemon(primary_uniq=MAC_P1)
        mgr = CoopManager(daemon)
        daemon._coop_manager = mgr
        mgr.sync()

        assert resolve_player_numbers(
            daemon, [self._ctrl(MAC_P1), self._ctrl(None)]
        ) == [1, None]
