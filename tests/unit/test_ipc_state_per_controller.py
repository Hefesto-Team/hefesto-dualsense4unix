"""STATUS-01 + COR-05 + BT-03 — `daemon.state_full` POR CONTROLE físico.

Cada entrada de `controllers` passa a carregar: `player_slot` (registro de
identidade, consulta defensiva), `lightbar_rgb`/`lightbar_on`/
`lightbar_source` (cor efetiva conhecida, decidida pelo DONO DA ESCRITA —
refutação 1 do sprint: `multi_intensity` só é verdade quando fomos NÓS que
escrevemos via classe LED), `inputs` ao vivo (primário espelha
`daemon._last_state`; secundários via `CoopManager.live_snapshots()`) e
`vpad_backend`/`vpad_motivo` por jogador (BT-03 — estende o `dedup_status`
da Fase 2 de agregado para por-controle).

Hermético: nós sysfs são fakes com contador de I/O (nunca o `/sys` real — na
máquina da mantenedora há DualSense de verdade plugado); o teste do discover
real usa `HEFESTO_DUALSENSE4UNIX_LEDS_ROOT` fake via monkeypatch do ATRIBUTO
`sysfs_leds.LEDS_ROOT` (o env é lido no IMPORT do módulo — setar o env aqui
não teria efeito). MACs sempre fake (aa:bb:cc:...), regra da casa.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

# MACs fake (regra da casa: jamais gravar MAC real 14:3a de controle).
KEY1 = "AA:BB:CC:00:00:01"
KEY2 = "AA:BB:CC:00:00:02"
MAC1 = "aabbcc000001"
MAC2 = "aabbcc000002"


class _FakeLedNode:
    """Nó LED fake com contadores de I/O (o gate anti-caminho-quente)."""

    def __init__(
        self,
        rgb: tuple[int, int, int] = (0, 0, 0),
        *,
        brightness: int = 255,
        writable: bool = True,
        indicator_dir: str = "",
    ) -> None:
        self.rgb = rgb
        self.brightness = brightness
        self._writable = writable
        self.indicator_dir = indicator_dir or f"/fake/leds/input{id(self)}:rgb:indicator"
        self.reads = 0
        self.writes: list[tuple[int, int, int]] = []
        self.player_writes: list[tuple[bool, ...]] = []

    def writable(self) -> bool:
        return self._writable

    def get_rgb(self) -> tuple[int, int, int] | None:
        self.reads += 1
        return self.rgb

    def is_on(self) -> bool:
        return self.brightness > 0

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb = (r, g, b)
        self.brightness = 255
        self.writes.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.player_writes.append(tuple(bits))
        return True


def _make_state(**kw: Any) -> ControllerState:
    base: dict[str, Any] = {
        "battery_pct": 80,
        "l2_raw": 0,
        "r2_raw": 0,
        "connected": True,
        "transport": "usb",
        "raw_lx": 128,
        "raw_ly": 128,
        "raw_rx": 128,
        "raw_ry": 128,
        "buttons_pressed": frozenset(),
    }
    base.update(kw)
    return ControllerState(**base)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    """Servidor IPC real com FakeController — o padrão de contrato da casa."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield server, socket_path, fc, store, daemon_mock
    finally:
        await server.stop()


def _describe_dois(fc: FakeController) -> None:
    fc.describe_controllers = lambda: [
        {"index": 0, "connected": True, "transport": "usb",
         "is_primary": True, "uniq": MAC1},
        {"index": 1, "connected": True, "transport": "bt",
         "is_primary": False, "uniq": MAC2},
    ]


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    assert isinstance(result, dict)
    return result


# --- lightbar: o DONO DA ESCRITA decide a fonte ------------------------------


class TestLightbarPorControle:
    @pytest.mark.asyncio
    async def test_no_gravavel_escrito_por_nos_sai_como_sysfs(
        self, running_server: Any
    ) -> None:
        """Nó em `_sysfs` + rastreio `_sysfs_written` → a classe LED é a verdade."""
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)
        node = _FakeLedNode(rgb=(16, 32, 72))
        fc._sysfs = {KEY1: node}
        fc._sysfs_written = {KEY1: (16, 32, 72)}

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["lightbar_source"] == "sysfs"
        assert c1["lightbar_rgb"] == [16, 32, 72]
        assert c1["lightbar_on"] is True

    @pytest.mark.asyncio
    async def test_no_zerado_sem_escrita_nossa_e_desconhecida_nunca_apagada(
        self, running_server: Any
    ) -> None:
        """Refutação 1 do sprint: classe zerada do probe NÃO é "apagada".

        O kernel registra o LED multicolor zerado e acende a lightbar de azul
        por fora da classe — `0 0 0` sem rastreio nosso é estado desconhecido
        (rgb None), nunca um `[0, 0, 0]` apresentável como "apagada".
        """
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)
        node = _FakeLedNode(rgb=(0, 0, 0))  # recém-registrado pelo probe
        fc._sysfs = {KEY1: node}
        fc._sysfs_written = {}

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["lightbar_source"] == "desconhecida"
        assert c1["lightbar_rgb"] is None
        assert c1["lightbar_on"] is False

    @pytest.mark.asyncio
    async def test_zero_zero_zero_escrito_por_nos_e_apagada_legitima(
        self, running_server: Any
    ) -> None:
        """`0 0 0` COM rastreio é o único estado que significa "apagada"."""
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)
        node = _FakeLedNode(rgb=(0, 0, 0))
        fc._sysfs = {KEY1: node}
        fc._sysfs_written = {KEY1: (0, 0, 0)}

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["lightbar_source"] == "sysfs"
        assert c1["lightbar_rgb"] == [0, 0, 0]
        assert c1["lightbar_on"] is False  # brightness 255, mas cor preta

    @pytest.mark.asyncio
    async def test_no_nao_gravavel_cai_no_desired_via_resolved_led_for(
        self, running_server: Any
    ) -> None:
        """Fora do mapa sysfs (escrita por hidraw → classe stale) → `desired`."""
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)
        fc._sysfs = {}
        fc._sysfs_written = {}
        fc.resolved_led_for = (
            lambda uniq: (40, 80, 180) if uniq == MAC1 else None
        )

        result = await _state_full(socket_path)

        c1, c2 = result["controllers"]
        assert c1["lightbar_source"] == "desired"
        assert c1["lightbar_rgb"] == [40, 80, 180]
        assert c1["lightbar_on"] is True
        # Sem nó E sem desired: nada conhecido.
        assert c2["lightbar_source"] == "desconhecida"
        assert c2["lightbar_rgb"] is None

    @pytest.mark.asyncio
    async def test_cache_ttl_no_maximo_uma_leitura_por_no_por_segundo(
        self, running_server: Any
    ) -> None:
        """N chamadas em < 1 s = 1 leitura sysfs por nó (o tick é 10 Hz)."""
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)
        node = _FakeLedNode(rgb=(10, 20, 30))
        fc._sysfs = {KEY1: node}
        fc._sysfs_written = {KEY1: (10, 20, 30)}

        for _ in range(5):
            result = await _state_full(socket_path)
            assert result["controllers"][0]["lightbar_rgb"] == [10, 20, 30]

        assert node.reads == 1


# --- inputs ao vivo -----------------------------------------------------------


class TestInputsPorControle:
    @pytest.mark.asyncio
    async def test_primario_espelha_last_state_do_daemon(
        self, running_server: Any
    ) -> None:
        """A MESMA fonte do topo do payload — nunca um snapshot paralelo."""
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._last_state = _make_state(
            raw_lx=200, raw_ly=50, l2_raw=180, buttons_pressed=frozenset({"cross"})
        )

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["inputs"] == {
            "lx": 200, "ly": 50, "rx": 128, "ry": 128,
            "l2_raw": 180, "r2_raw": 0, "buttons": ["cross"],
        }
        # Espelho do topo, literal:
        assert c1["inputs"]["lx"] == result["lx"]
        assert c1["inputs"]["buttons"] == result["buttons"]

    @pytest.mark.asyncio
    async def test_secundario_vem_do_live_snapshots_do_coop(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        snap = SimpleNamespace(
            lx=10, ly=20, rx=30, ry=40, l2_raw=50, r2_raw=60,
            buttons_pressed=frozenset({"square", "l1"}),
        )
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {MAC2: snap},
            _players={},
            player_count=lambda: 2,
        )

        result = await _state_full(socket_path)

        c2 = result["controllers"][1]
        assert c2["inputs"] == {
            "lx": 10, "ly": 20, "rx": 30, "ry": 40,
            "l2_raw": 50, "r2_raw": 60, "buttons": ["l1", "square"],
        }

    @pytest.mark.asyncio
    async def test_sem_leitor_inputs_e_none(self, running_server: Any) -> None:
        """Sem reader (co-op off/pending): None — o card mostra "—"."""
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._last_state = None
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {}, _players={}, player_count=lambda: 1
        )

        result = await _state_full(socket_path)

        assert result["controllers"][0]["inputs"] is None
        assert result["controllers"][1]["inputs"] is None


# --- player_slot (registro de identidade, defensivo) --------------------------


class TestPlayerSlot:
    @pytest.mark.asyncio
    async def test_registry_presente_devolve_o_slot(self, running_server: Any) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        chamadas: list[tuple[str, bool]] = []

        def slot_for(uniq: str, assign: bool = True) -> int | None:
            chamadas.append((uniq, assign))
            return {MAC1: 1, MAC2: 2}.get(uniq)

        daemon.identity_registry = SimpleNamespace(slot_for=slot_for)

        result = await _state_full(socket_path)

        assert result["controllers"][0]["player_slot"] == 1
        assert result["controllers"][1]["player_slot"] == 2
        # Leitura NUNCA aloca slot: toda consulta é assign=False.
        assert chamadas and all(assign is False for _uniq, assign in chamadas)

    @pytest.mark.asyncio
    async def test_registry_ausente_devolve_none(self, running_server: Any) -> None:
        """A frente do registry é paralela — sem ele o campo degrada a None."""
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon.identity_registry = None

        result = await _state_full(socket_path)

        assert result["controllers"][0]["player_slot"] is None
        assert result["controllers"][1]["player_slot"] is None

    @pytest.mark.asyncio
    async def test_registry_dublado_por_magicmock_nao_estoura_serializacao(
        self, running_server: Any
    ) -> None:
        """MagicMock auto-atributo devolve mock → coerção para None, sem crash."""
        _server, socket_path, fc, _store, _daemon = running_server
        _describe_dois(fc)  # daemon MagicMock cru: identity_registry auto-mock

        result = await _state_full(socket_path)

        assert result["controllers"][0]["player_slot"] is None


# --- vpad_backend / vpad_motivo por jogador (BT-03) ---------------------------


class TestVpadPorJogador:
    @pytest.mark.asyncio
    async def test_p1_degradado_expoe_uinput_e_motivo(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = SimpleNamespace(
            flavor="dualsense", backend="uinput",
            fallback_motivo="uhid_bind_falhou",
            ff_supported=True, ff_play_count=0, ff_last_sent=(0, 0),
        )

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["vpad_backend"] == "uinput"
        assert c1["vpad_motivo"] == "uhid_bind_falhou"

    @pytest.mark.asyncio
    async def test_p1_saudavel_uhid_sem_motivo(self, running_server: Any) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = SimpleNamespace(
            flavor="dualsense", backend="uhid", fallback_motivo=None,
            ff_supported=True, ff_play_count=0, ff_last_sent=(0, 0),
        )

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["vpad_backend"] == "uhid"
        assert c1["vpad_motivo"] is None

    @pytest.mark.asyncio
    async def test_mascara_xbox_uinput_por_design_sem_motivo(
        self, running_server: Any
    ) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = SimpleNamespace(
            flavor="xbox", backend="uinput", fallback_motivo=None,
            ff_supported=True, ff_play_count=0, ff_last_sent=(0, 0),
        )

        result = await _state_full(socket_path)

        c1 = result["controllers"][0]
        assert c1["vpad_backend"] == "uinput"
        assert c1["vpad_motivo"] is None

    @pytest.mark.asyncio
    async def test_secundario_do_coop_expoe_o_backend_do_vpad_dele(
        self, running_server: Any
    ) -> None:
        """P2 degradado em uinput enquanto o P1 está saudável em uhid."""
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = SimpleNamespace(
            flavor="dualsense", backend="uhid", fallback_motivo=None,
            ff_supported=True, ff_play_count=0, ff_last_sent=(0, 0),
        )
        p2_vpad = SimpleNamespace(
            flavor="dualsense", backend="uinput", fallback_motivo="uhid_indisponivel"
        )
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {},
            _players={MAC2: SimpleNamespace(vpad=p2_vpad, player_index=2)},
            player_count=lambda: 2,
        )

        result = await _state_full(socket_path)

        c1, c2 = result["controllers"]
        assert (c1["vpad_backend"], c1["vpad_motivo"]) == ("uhid", None)
        assert (c2["vpad_backend"], c2["vpad_motivo"]) == (
            "uinput", "uhid_indisponivel",
        )

    @pytest.mark.asyncio
    async def test_controle_sem_vpad_proprio_fica_none(
        self, running_server: Any
    ) -> None:
        """Co-op off: o secundário não alimenta o jogo — nada a declarar."""
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = None
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {}, _players={}, player_count=lambda: 1
        )

        result = await _state_full(socket_path)

        for entry in result["controllers"]:
            assert entry["vpad_backend"] is None
            assert entry["vpad_motivo"] is None


# --- priming + rastreio "escrito por nós" no backend --------------------------


def _stub_handle() -> Any:
    return SimpleNamespace(
        connected=True,
        light=SimpleNamespace(playerNumber=None, setColorI=lambda *a: None),
    )


def _backend_com_nos(
    monkeypatch: pytest.MonkeyPatch, nodes: dict[str, _FakeLedNode]
) -> Any:
    """`PyDualSenseController` real com handles stub e discover fake."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    class _NoEvdev:
        def stop(self) -> None: ...
        def is_available(self) -> bool:
            return False

    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: dict(nodes)
    )
    backend = PyDualSenseController(evdev_reader=_NoEvdev())
    backend._handles = {KEY1: _stub_handle(), KEY2: _stub_handle()}
    backend._primary_key = KEY1
    return backend


class TestPrimingERastreio:
    def test_priming_converge_a_classe_para_o_azul_kernel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hotplug com desired None: o nó novo recebe (0,0,128) e entra no rastreio."""
        node = _FakeLedNode(rgb=(0, 0, 0))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})

        backend._refresh_sysfs_leds()

        assert node.writes == [(0, 0, 128)]
        assert backend._sysfs_written == {KEY1: (0, 0, 128)}

    def test_reassert_com_desired_registra_a_cor_no_rastreio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        node = _FakeLedNode(rgb=(0, 0, 0))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})
        backend._desired_default.led = (40, 80, 180)

        backend._refresh_sysfs_leds()

        assert node.writes == [(40, 80, 180)]
        assert backend._sysfs_written == {KEY1: (40, 80, 180)}

    def test_priming_nao_roda_em_modo_nativo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exceção documentada: mutado, o jogo é dono do LED — nada é escrito."""
        node = _FakeLedNode(rgb=(0, 0, 0))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})
        backend._output_mute = True

        backend._refresh_sysfs_leds()

        assert node.writes == []
        assert backend._sysfs_written == {}

    def test_no_recriado_no_reconnect_bt_e_primado_de_novo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mesmo MAC, `indicator_dir` novo (input30→input75): a classe renasceu
        zerada no probe e converge de novo."""
        node_a = _FakeLedNode(rgb=(0, 0, 0), indicator_dir="/fake/input30:rgb:indicator")
        backend = _backend_com_nos(monkeypatch, {MAC1: node_a})
        backend._refresh_sysfs_leds()
        assert node_a.writes == [(0, 0, 128)]

        node_b = _FakeLedNode(rgb=(0, 0, 0), indicator_dir="/fake/input75:rgb:indicator")
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {MAC1: node_b}
        )
        backend._refresh_sysfs_leds()

        assert node_b.writes == [(0, 0, 128)]
        assert backend._sysfs_written == {KEY1: (0, 0, 128)}

    def test_mesmo_no_nao_e_reprimado_a_cada_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Refresh idempotente: nó já conhecido não recebe escrita nova."""
        node = _FakeLedNode(rgb=(0, 0, 0))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})

        backend._refresh_sysfs_leds()
        backend._refresh_sysfs_leds()

        assert node.writes == [(0, 0, 128)]

    def test_rastreio_e_podado_quando_o_no_some(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Controle desconectou: sem nó não há escrita nossa válida."""
        node = _FakeLedNode(rgb=(0, 0, 0))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})
        backend._refresh_sysfs_leds()
        assert KEY1 in backend._sysfs_written

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {}
        )
        backend._refresh_sysfs_leds()

        assert backend._sysfs_written == {}

    def test_resolved_led_for_espelha_o_merge_por_uniq(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.core.controller import OutputSpec

        backend = _backend_com_nos(monkeypatch, {})
        backend._desired_default.led = (1, 2, 3)
        backend.apply_output_for(MAC2, OutputSpec(led=(9, 8, 7)))

        assert backend.resolved_led_for(MAC1) == (1, 2, 3)  # default puro
        assert backend.resolved_led_for(MAC2) == (9, 8, 7)  # override por-uniq

    def test_describe_controllers_em_loop_nao_le_arquivo_nenhum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`describe_controllers` roda no caminho quente do FF — zero I/O de nó.

        O enriquecimento de cor mora no handler IPC (com cache TTL), nunca
        aqui. O fake conta leituras: N chamadas = 0 leituras.
        """
        node = _FakeLedNode(rgb=(5, 5, 5))
        backend = _backend_com_nos(monkeypatch, {MAC1: node})
        backend._refresh_sysfs_leds()
        node.reads = 0
        discover_chamado = {"n": 0}

        def _discover_conta() -> dict[str, _FakeLedNode]:
            discover_chamado["n"] += 1
            return {MAC1: node}

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover", _discover_conta
        )

        for _ in range(50):
            infos = backend.describe_controllers()
            assert isinstance(infos, list) and infos

        assert node.reads == 0
        assert discover_chamado["n"] == 0


# --- LEDS_ROOT fake de verdade: SysfsLedNode + discover reais -----------------


class TestSysfsLedsLeituraReal:
    def _monta_arvore(self, tmp_path: Path, mac: str) -> tuple[Path, Path]:
        """Réplica mínima do sysfs: HID dev + leds/inputN:rgb:indicator + symlink.

        `discover()` faz glob em `LEDS_ROOT` e `realpath` até o dir do HID
        (que tem `uevent` com HID_UNIQ) — a árvore fake reproduz isso.
        """
        hid = tmp_path / "hid-dev"
        indicator = hid / "leds" / "input30:rgb:indicator"
        indicator.mkdir(parents=True)
        (hid / "uevent").write_text(f"HID_UNIQ={mac}\n")
        (indicator / "multi_intensity").write_text("16 32 72\n")
        (indicator / "brightness").write_text("255\n")
        leds_root = tmp_path / "class-leds"
        leds_root.mkdir()
        os.symlink(indicator, leds_root / "input30:rgb:indicator")
        return leds_root, indicator

    def test_discover_e_get_rgb_com_leds_root_fake(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O env é lido no IMPORT do módulo — o teste patcha o ATRIBUTO."""
        from hefesto_dualsense4unix.core import sysfs_leds

        leds_root, _indicator = self._monta_arvore(tmp_path, "aa:bb:cc:00:00:01")
        monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(leds_root))

        nodes = sysfs_leds.discover()

        assert MAC1 in nodes
        node = nodes[MAC1]
        assert node.get_rgb() == (16, 32, 72)
        assert node.is_on() is True

    def test_get_rgb_tolerante_a_no_que_sumiu(self, tmp_path: Path) -> None:
        """Replug/BT derruba o nó no meio da leitura: None/False, nunca raise."""
        from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode

        node = SysfsLedNode(str(tmp_path / "nao-existe"), [])
        assert node.get_rgb() is None
        assert node.is_on() is False

    def test_get_rgb_tolerante_a_conteudo_corrompido(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode

        indicator = tmp_path / "input1:rgb:indicator"
        indicator.mkdir()
        (indicator / "multi_intensity").write_text("lixo\n")
        (indicator / "brightness").write_text("nan\n")
        node = SysfsLedNode(str(indicator), [])
        assert node.get_rgb() is None
        assert node.is_on() is False


# --- CoopManager.live_snapshots ------------------------------------------------


class TestLiveSnapshots:
    def _manager(self) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

        daemon = SimpleNamespace(
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=object(),
            controller=None,
        )
        return CoopManager(daemon)

    def test_traz_so_jogador_promovido_keyed_por_mac(self) -> None:
        manager = self._manager()
        snap = SimpleNamespace(
            lx=1, ly=2, rx=3, ry=4, l2_raw=5, r2_raw=6, buttons_pressed=frozenset()
        )
        reader_ok = SimpleNamespace(snapshot=lambda: snap)
        manager._players = {
            MAC2: SimpleNamespace(vpad=object(), reader=reader_ok, player_index=2),
            # pendente (sem vpad): o jogo não o vê — fica fora.
            MAC1: SimpleNamespace(vpad=None, reader=reader_ok, player_index=3),
            # sem MAC: não casa com nenhum card — fica fora.
            "path:/dev/input/event9": SimpleNamespace(
                vpad=object(), reader=reader_ok, player_index=4
            ),
        }

        out = manager.live_snapshots()

        assert list(out) == [MAC2]
        assert out[MAC2] is snap

    def test_snapshot_que_falha_nao_derruba_os_outros(self) -> None:
        manager = self._manager()
        bom = SimpleNamespace(
            snapshot=lambda: SimpleNamespace(
                lx=1, ly=2, rx=3, ry=4, l2_raw=0, r2_raw=0,
                buttons_pressed=frozenset(),
            )
        )

        def _explode() -> Any:
            raise OSError("device sumiu")

        ruim = SimpleNamespace(snapshot=_explode)
        manager._players = {
            MAC1: SimpleNamespace(vpad=object(), reader=ruim, player_index=2),
            MAC2: SimpleNamespace(vpad=object(), reader=bom, player_index=3),
        }

        out = manager.live_snapshots()

        assert list(out) == [MAC2]


# --- transição de degradação anunciada (BT-03) --------------------------------


class TestNotifyVpadDegradado:
    def test_publica_no_bus_e_loga(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            notify_vpad_degradado,
        )

        publicados: list[tuple[str, Any]] = []
        daemon = SimpleNamespace(
            bus=SimpleNamespace(publish=lambda topic, payload: publicados.append(
                (topic, payload)
            ))
        )

        notify_vpad_degradado(daemon, player=2, motivo="uhid_bind_falhou")

        assert publicados == [
            ("vpad.degraded", {"player": 2, "motivo": "uhid_bind_falhou"})
        ]

    def test_sem_bus_e_no_op_sem_crash(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            notify_vpad_degradado,
        )

        notify_vpad_degradado(
            SimpleNamespace(), player=1, motivo="sem_uhid"
        )

    def test_promote_player_degradado_anuncia_a_transicao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O vpad de secundário que nasce dualsense+uinput publica no bus."""
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            CoopManager,
            _SecondaryPlayer,
        )

        publicados: list[tuple[str, Any]] = []
        daemon = SimpleNamespace(
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=object(),
            controller=SimpleNamespace(hidraw_path=lambda uniq=None: None),
            bus=SimpleNamespace(
                publish=lambda topic, payload: publicados.append((topic, payload))
            ),
        )
        manager = CoopManager(daemon)
        vpad_degradado = SimpleNamespace(
            flavor="dualsense", backend="uinput",
            fallback_motivo="uhid_indisponivel", stop=lambda: None,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda flavor, *, rumble_sink=None, player=1, allow_uhid=True: vpad_degradado,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
            lambda daemon: None,
        )
        reader = SimpleNamespace(
            grab_state="held", set_grab=lambda g: True, stop=lambda: None,
            snapshot=lambda: None,
        )
        player = _SecondaryPlayer(
            identity=MAC2, evdev_path="/dev/input/event7",
            reader=reader, player_index=2,
        )
        manager._players[MAC2] = player

        manager._promote_player(player)

        assert player.vpad is vpad_degradado
        assert publicados == [
            ("vpad.degraded", {"player": 2, "motivo": "uhid_indisponivel"})
        ]
