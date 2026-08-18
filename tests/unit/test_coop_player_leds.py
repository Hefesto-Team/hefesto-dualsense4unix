"""PERFIL-06 — precedência co-op vs override por-uniq e revert POR CONTROLE.

Fecha o "caminho (4)" do COR-02: o revert do co-op re-aplicava o padrão GLOBAL
de player-LED em todos os controles — por cima do override por-uniq do perfil
(PERFIL-01/02) — e, pior, o broadcast público (`set_player_leds`) APAGAVA o
campo `player_leds` de todos os overrides registrados no backend.

Cobre, com o backend REAL (`PyDualSenseController`, handles stub) + fakes de
reader/vpad/nós sysfs (mesmo padrão hermético de `test_subsystem_coop.py`):

(a) co-op ativo VENCE o override do perfil (LED mostra o número do JOGADOR);
(b) co-op desligado → cada controle volta ao SEU padrão resolvido (override
    por-uniq onde há, default global onde não) e o override SOBREVIVE no mapa;
(c) um jogador que sai (disconnect) tem o por-uniq DELE restaurado;
(d) regressão: sem override nenhum, o revert broadcast do default permanece;
(e) key sem MAC (`path:...`) fica fora do mapa, com log em vez de silêncio
    (comportamento existente do backend, coberto aqui por teste — item 3 do
    PERFIL-06); e o gate `output_mute` do Modo Nativo é respeitado (D12).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, player_led_pattern

# MACs fake (regra da casa: jamais gravar MAC real de controle).
KEY1 = "AA:BB:CC:00:00:01"  # key do handle no backend (formato do serial hidapi)
KEY2 = "AA:BB:CC:00:00:02"
MAC1 = "aabbcc000001"  # normalizado (uniq) — o mesmo que o coop/sysfs usam
MAC2 = "aabbcc000002"

#: Padrão GLOBAL do perfil (default broadcast) — distinto dos canônicos do co-op.
DEFAULT_BITS = (False, False, False, False, True)
#: Override por-uniq do perfil para o controle 2 — distinto do default e dos canônicos.
OVERRIDE_BITS = (True, False, False, False, True)


class _FakeReader:
    """Reader evdev falso (mesmo contrato do usado em test_subsystem_coop)."""

    grab_ok: bool = True

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.stopped = False
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        if grab and not type(self).grab_ok:
            self.grab_state = "failed"
            return False
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> Any:
        return self.snap


class _FakeVpad:
    """Vpad falso devolvido pela factory patchada (nunca uhid/uinput reais)."""

    created: ClassVar[list[_FakeVpad]] = []

    def __init__(self, flavor: str, rumble_sink: Any = None) -> None:
        self.flavor = flavor
        self.rumble_sink = rumble_sink
        self.stopped = False
        type(self).created.append(self)

    def stop(self) -> None:
        self.stopped = True

    def forward_analog(self, **kw: int) -> None:
        return

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        return

    def pump_ff(self) -> None:
        return


class _FakeLedNode:
    """Nó sysfs falso: registra os padrões de player-LED escritos nele."""

    def __init__(self) -> None:
        self.patterns: list[tuple[bool, bool, bool, bool, bool]] = []

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.patterns.append(bits)
        return True

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        return True


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeReader.grab_ok = True
    _FakeVpad.created = []
    # Hotplug simulado pelo mapping do discover, nunca por /dev/input real.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
        lambda self: True,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader
    )
    # Nunca criar vpad REAL (uhid registraria um DualSense Edge no kernel da
    # máquina; uinput idem) — o backend real do teste tem `hidraw_path`, então
    # `controller_allows_uhid` liberaria o uhid sem este patch.
    # `**_sinks` cobre os sinks de replicação do REPLICA-03 (o co-op passa
    # trigger/lightbar/player_led/session_end junto do rumble_sink).
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, *, rumble_sink=None, player=1, allow_uhid=True, **_sinks: (
            _FakeVpad(str(flavor), rumble_sink)
        ),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.normalize_flavor",
        lambda f: f or "dualsense",
    )
    # Nunca materializar envs do wrapper em ~/.config da usuária (DEDUP-04 é
    # best-effort e fora do assunto deste arquivo).
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    # Hermético: NUNCA tocar o /sys/class/leds real (na máquina da mantenedora
    # há um DualSense de verdade plugado). Cada teste sobrepõe com nós falsos.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {}
    )


def _set_evdevs(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(mapping),
    )


def _set_led_nodes(
    monkeypatch: pytest.MonkeyPatch, *macs: str
) -> dict[str, _FakeLedNode]:
    nodes = {mac: _FakeLedNode() for mac in macs}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: nodes
    )
    return nodes


def _stub_handle() -> Any:
    """Handle pydualsense stub — só o que os caminhos exercitados tocam."""
    return SimpleNamespace(
        connected=True,
        light=SimpleNamespace(playerNumber=None, setColorI=lambda *a: None),
    )


def _backend_real(nodes: dict[str, _FakeLedNode]) -> tuple[Any, Any, Any]:
    """`PyDualSenseController` REAL com 2 handles stub e nós sysfs mapeados.

    O mapa `_sysfs` (keyed pela KEY do handle) recebe os MESMOS nós falsos que
    o coop enxerga via `sysfs_leds.discover()` (keyed por MAC) — como em
    produção após `_refresh_sysfs_leds`.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    backend = PyDualSenseController(evdev_reader=_FakeReader(device_path=None))
    h1, h2 = _stub_handle(), _stub_handle()
    backend._handles = {KEY1: h1, KEY2: h2}
    backend._primary_key = KEY1
    backend._sysfs = {KEY1: nodes[MAC1], KEY2: nodes[MAC2]}
    return backend, h1, h2


def _daemon_com_backend(backend: Any, *, coop: bool = True) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=coop, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=backend,
        _coop_manager=None,
    )


def _cenario_com_override(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, _FakeLedNode], Any, Any]:
    """Perfil aplicado: default broadcast + override de player_leds na key2."""
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)
    backend.set_player_leds(DEFAULT_BITS)  # padrão global do perfil
    backend.apply_output_for(MAC2, OutputSpec(player_leds=OVERRIDE_BITS))
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    daemon = _daemon_com_backend(backend)
    return nodes, backend, daemon


# --- (a) precedência: o runtime do co-op VENCE o override do perfil ---------


def test_coop_ativo_vence_o_override_por_uniq(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes, _backend, daemon = _cenario_com_override(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()

    # Com o co-op ativo cada controle mostra o número do SEU jogador — o
    # override do perfil (OVERRIDE_BITS na key2) fica suspenso até o revert.
    assert nodes[MAC1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)


# --- (b) co-op desligado: por-uniq onde há override, default onde não -------


def test_desligar_coop_restaura_por_uniq_e_default(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes, backend, daemon = _cenario_com_override(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()

    daemon.config.coop_enabled = False
    mgr.sync()  # should_be_active=False → disable() → revert

    # key2 volta ao override POR-UNIQ dela; key1 ao default global do perfil
    # — nunca o broadcast cego do global nas duas.
    assert nodes[MAC2].patterns[-1] == OVERRIDE_BITS
    assert nodes[MAC1].patterns[-1] == DEFAULT_BITS
    # O coração do PERFIL-06: o revert NÃO apagou o override registrado no
    # backend (o broadcast antigo via `set_player_leds` limpava o campo).
    assert backend._desired_by_uniq[MAC2].player_leds == OVERRIDE_BITS
    # E o default broadcast segue intacto.
    assert backend._desired_default.player_leds == DEFAULT_BITS


def test_revert_e_idempotente_apos_desligar(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes, _backend, daemon = _cenario_com_override(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()
    daemon.config.coop_enabled = False
    mgr.sync()
    escritas_1 = len(nodes[MAC1].patterns)
    escritas_2 = len(nodes[MAC2].patterns)

    mgr.sync()  # novo tick inativo: nada a reverter de novo

    assert len(nodes[MAC1].patterns) == escritas_1
    assert len(nodes[MAC2].patterns) == escritas_2


# --- (c) um jogador sai: restaura o por-uniq DAQUELE mac ---------------------


def test_jogador_desconectado_tem_o_por_uniq_dele_restaurado(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes, _backend, daemon = _cenario_com_override(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)

    # O controle 2 desconecta (hotplug-out): o teardown restaura o padrão
    # RESOLVIDO do mac dele — o override, não o default. (Best-effort: em
    # produção o nó sysfs pode já ter sumido junto; aqui ele segue visível
    # para observarmos QUAL padrão o revert escolhe.)
    _set_evdevs(monkeypatch, {MAC1: "/dev/input/event5"})
    mgr.sync()

    assert MAC2 not in mgr._players
    assert nodes[MAC2].patterns[-1] == OVERRIDE_BITS
    # R-20/R-13 item 4 (auditoria 23/07): CONTRATO MUDADO DE PROPÓSITO.
    #
    # Antes, quando o último secundário saía, o primário ficava PRESO no
    # padrão player-1 (o `if not self._players: return` só parava de escrever,
    # sem reverter). O plano nomeia isso como bug ("SEM SECUNDÁRIO NÃO HÁ
    # CO-OP... deixa o primário preso em P1"): um único DualSense com o Pro
    # Nintendo no slot 1 do registry acendia DOIS "player 1".
    #
    # Com a camada de saída (R-20), esvaziar `_players` REVOGA a camada do
    # co-op inteira, e o backend reescreve cada controle para o resolvido SEM
    # o co-op. O primário, sem override, volta ao DEFAULT do perfil — não fica
    # mais fingindo ser jogador 1 sozinho.
    assert nodes[MAC1].patterns[-1] == DEFAULT_BITS


# --- (d) regressão: sem override nenhum, o revert broadcast permanece --------


def test_regressao_sem_override_revert_broadcast_do_default(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)
    backend.set_player_leds(DEFAULT_BITS)  # só o padrão global, sem overrides
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    daemon = _daemon_com_backend(backend)
    mgr = CoopManager(daemon)
    mgr.sync()

    daemon.config.coop_enabled = False
    mgr.sync()

    # Comportamento histórico preservado: os dois voltam ao default broadcast…
    assert nodes[MAC1].patterns[-1] == DEFAULT_BITS
    assert nodes[MAC2].patterns[-1] == DEFAULT_BITS
    # …sem poluir o mapa por-uniq com "overrides fantasma" da restauração.
    assert backend._desired_by_uniq == {}


def test_resolvedor_sem_api_cai_no_padrao_broadcast() -> None:
    """Backend legado (sem `resolved_player_leds_for`) → padrão broadcast.

    É o fallback que mantém os fakes/backends antigos no comportamento
    histórico (a regressão coberta pelos testes de `test_subsystem_coop.py`).
    """
    daemon = SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=SimpleNamespace(
            _desired=SimpleNamespace(player_leds=DEFAULT_BITS)
        ),
        _coop_manager=None,
    )
    mgr = CoopManager(daemon)
    assert mgr._resolved_player_leds(MAC2) == DEFAULT_BITS


# --- (e) key sem MAC (`path:`) fora do mapa, com log — e gate do Nativo ------


class _LoggerEspiao:
    """Dublê do logger structlog do módulo: registra (evento, kwargs) por nível.

    Captura determinística — independe de fd/stream (o structlog do projeto
    cacheia o stderr do momento do import, o que torna capsys/capfd frágeis).
    """

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict[str, Any]]] = []

    def _registra(self, nivel: str, evento: str, **kw: Any) -> None:
        self.eventos.append((nivel, evento, kw))

    def debug(self, evento: str, **kw: Any) -> None:
        self._registra("debug", evento, **kw)

    def info(self, evento: str, **kw: Any) -> None:
        self._registra("info", evento, **kw)

    def warning(self, evento: str, **kw: Any) -> None:
        self._registra("warning", evento, **kw)

    def nomes(self) -> list[str]:
        return [evento for _nivel, evento, _kw in self.eventos]


def test_apply_output_for_key_path_e_ignorada_com_log(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 3 do PERFIL-06: o comportamento JÁ existe no backend — coberto.

    O schema do perfil rejeita keys não-12-hex antes (profiles/schema.py);
    quem chega por API programática cai nestes logs, nunca em silêncio.
    """
    espiao = _LoggerEspiao()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.backend_pydualsense.logger", espiao
    )
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)

    backend.apply_output_for(
        "path:/dev/hidraw3", OutputSpec(player_leds=OVERRIDE_BITS)
    )
    assert backend._desired_by_uniq == {}
    assert "apply_output_for_sem_mac_ignorado" in espiao.nomes()

    backend.reset_output_overrides(
        {"path:/dev/hidraw3": OutputSpec(player_leds=OVERRIDE_BITS)}
    )
    assert backend._desired_by_uniq == {}
    assert "override_por_controle_sem_mac_ignorado" in espiao.nomes()


def test_resolved_player_leds_for_key_path_devolve_o_default(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Key sem MAC não tem override possível: comporta-se como hoje (só global)."""
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)
    backend.set_player_leds(DEFAULT_BITS)
    backend.apply_output_for(MAC2, OutputSpec(player_leds=OVERRIDE_BITS))

    assert backend.resolved_player_leds_for("path:/dev/hidraw3") == DEFAULT_BITS
    # E o merge por-uniq de verdade, para contraste:
    assert backend.resolved_player_leds_for(MAC2) == OVERRIDE_BITS
    assert backend.resolved_player_leds_for(MAC1) == DEFAULT_BITS


def test_revert_single_com_identidade_path_nao_escreve(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[int] = []

    def _discover() -> dict[str, Any]:
        chamadas.append(1)
        return {}

    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", _discover)
    nodes_stub: dict[str, _FakeLedNode] = {MAC1: _FakeLedNode(), MAC2: _FakeLedNode()}
    backend, _h1, _h2 = _backend_real(nodes_stub)
    backend.set_player_leds(DEFAULT_BITS)
    mgr = CoopManager(_daemon_com_backend(backend))
    mgr._leds_overridden = True

    mgr._revert_single_player_led("path:/dev/input/event7")

    assert chamadas == []  # nem consultou o sysfs — identidade sem MAC é ignorada


def test_revert_em_modo_nativo_respeita_output_mute(
    patched: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D12: mutado (Modo Nativo), o revert NÃO escreve LED nenhum via sysfs —
    o estado desejado fica no backend e o unmute re-aplica o resolvido."""
    nodes, backend, daemon = _cenario_com_override(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()

    backend.set_output_mute(True)
    escritas_1 = len(nodes[MAC1].patterns)
    escritas_2 = len(nodes[MAC2].patterns)
    daemon.config.coop_enabled = False
    mgr.sync()  # disable → reverts com o gate do mute

    assert len(nodes[MAC1].patterns) == escritas_1
    assert len(nodes[MAC2].patterns) == escritas_2
    # O override segue guardado para o unmute restaurar.
    assert backend._desired_by_uniq[MAC2].player_leds == OVERRIDE_BITS
