"""GYRO-03 — telemetria do espelho de motion: emit_hz, state_full e o card.

Três contratos herméticos (sem hardware, sem GTK, sem daemon real):

1. `PhysicalReportReader.emit_hz` — taxa de emissão por EMA com relógio
   injetado: converge para a taxa real de entrega, zera quando o fluxo para
   (>1 s sem entrega) e recomeça do zero depois de um buraco (a EMA velha de
   um fluxo morto não pode "vazar" na taxa nova).
2. `daemon.state_full` publica `motion_streaming`/`motion_hz` POR VPAD no
   bloco `rumble_ff.per_vpad` (P1 via `daemon._motion_reader`; jogador do
   co-op via `player.motion_reader`), com tipagem estrita — um MagicMock no
   lugar do vpad/reader nunca vira True/taxa fantasma no payload.
3. `texto_motion` (função pura do ControllerCard) — a linha discreta da GUI
   só aparece com o espelho ATIVO no vpad DESTE controle; nunca acusa
   ausência (isso é papel do doctor, não do card).

Padrão do repo: NUNCA `import gi` no topo — `texto_motion` é função pura e o
módulo do card resolve GTK internamente (stub em headless).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import texto_motion
from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.physical_report_reader import PhysicalReportReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


class _RelogioFake:
    """Relógio monotônico controlado pelo teste."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def avancar(self, dt: float) -> None:
        self.now += dt


class _VpadGravador:
    """Vpad mínimo do contrato do reader (forward_motion + streaming)."""

    player = 1

    def __init__(self) -> None:
        self.janelas: list[bytes] = []

    def forward_motion(self, window: bytes) -> None:
        self.janelas.append(window)

    def set_motion_streaming(self, on: bool) -> None:  # pragma: no cover - n/u
        pass


def _reader(relogio: _RelogioFake, max_hz: float = 250.0) -> PhysicalReportReader:
    return PhysicalReportReader(
        path_provider=lambda: None,
        vpad=_VpadGravador(),
        max_hz=max_hz,
        time_fn=relogio,
    )


def _janela(i: int) -> bytes:
    """Janela de 25 B distinta por índice (fura o dedup por valor)."""
    return bytes([i & 0xFF]) + bytes(24)


class TestEmitHz:
    def test_sem_nenhuma_emissao_e_zero(self) -> None:
        relogio = _RelogioFake()
        assert _reader(relogio).emit_hz == 0.0

    def test_primeira_emissao_ainda_nao_tem_taxa(self) -> None:
        """Taxa exige um INTERVALO — com uma entrega só, segue 0.0."""
        relogio = _RelogioFake()
        reader = _reader(relogio)
        reader._maybe_emit(_janela(0))
        assert reader.emit_hz == 0.0

    def test_converge_para_a_taxa_real_de_entrega(self) -> None:
        """Entregas a 100 Hz cravadas → emit_hz ≈ 100 (EMA de intervalos)."""
        relogio = _RelogioFake()
        reader = _reader(relogio)
        for i in range(50):
            reader._maybe_emit(_janela(i))
            relogio.avancar(0.01)
        assert reader.emit_hz == pytest.approx(100.0, rel=0.05)

    def test_zera_quando_o_fluxo_para(self) -> None:
        """>1 s sem entrega: reportar a EMA antiga mentiria um gyro vivo."""
        relogio = _RelogioFake()
        reader = _reader(relogio)
        for i in range(10):
            reader._maybe_emit(_janela(i))
            relogio.avancar(0.01)
        assert reader.emit_hz > 0.0
        relogio.avancar(1.5)
        assert reader.emit_hz == 0.0

    def test_buraco_no_fluxo_recomeca_a_medicao_do_zero(self) -> None:
        """Retomada pós-buraco NÃO herda a EMA de antes (taxa distorcida)."""
        relogio = _RelogioFake()
        reader = _reader(relogio)
        for i in range(10):
            reader._maybe_emit(_janela(i))
            relogio.avancar(0.01)
        relogio.avancar(5.0)
        reader._maybe_emit(_janela(200))  # 1ª entrega pós-buraco: reseta
        assert reader.emit_hz == 0.0
        # Duas entregas a 50 Hz já medem a taxa NOVA, sem herança dos 100 Hz.
        relogio.avancar(0.02)
        reader._maybe_emit(_janela(201))
        assert reader.emit_hz == pytest.approx(50.0, rel=0.05)


# ---------------------------------------------------------------------------
# state_full → rumble_ff.per_vpad[*].motion_streaming/motion_hz
# ---------------------------------------------------------------------------


def _vpad_ns(
    *, streaming: Any, backend: str = "uhid", ff_play_count: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(
        backend=backend,
        flavor="dualsense",
        ff_supported=True,
        ff_play_count=ff_play_count,
        output_count=0,
        trigger_replicas=0,
        lightbar_replicas=0,
        player_led_replicas=0,
        ff_last_sent=(0, 0),
        motion_streaming=streaming,
    )


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
async def servidor_com_motion(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    """IpcServer vivo com daemon dublado: P1 streaming + co-op P2 sem espelho."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        rumble_active=None,
    )
    daemon_mock._gamepad_device = _vpad_ns(streaming=True)
    daemon_mock._motion_reader = SimpleNamespace(emit_hz=248.3)
    daemon_mock._coop_manager = SimpleNamespace(
        _players={
            "aa:bb:cc:dd:ee:02": SimpleNamespace(
                player_index=2,
                vpad=_vpad_ns(streaming=False),
                motion_reader=None,
            ),
        },
        player_count=lambda: 2,
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
        yield socket_path, daemon_mock
    finally:
        await server.stop()


async def _per_vpad(socket_path: Path) -> list[dict[str, Any]]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    per_vpad = result["rumble_ff"]["per_vpad"]
    assert isinstance(per_vpad, list)
    return per_vpad


@pytest.mark.asyncio
async def test_state_full_publica_motion_por_vpad(servidor_com_motion: Any) -> None:
    """P1 com espelho ATIVO carrega streaming=True e a taxa do reader dele;
    o jogador 2 (sem reader) carrega False/0.0 — nunca herda a taxa do P1."""
    socket_path, _daemon = servidor_com_motion
    per_vpad = await _per_vpad(socket_path)
    por_jogador = {item["player"]: item for item in per_vpad}
    assert por_jogador[1]["motion_streaming"] is True
    assert por_jogador[1]["motion_hz"] == pytest.approx(248.3)
    assert por_jogador[2]["motion_streaming"] is False
    assert por_jogador[2]["motion_hz"] == 0.0


@pytest.mark.asyncio
async def test_state_full_motion_defensivo_contra_mock(
    servidor_com_motion: Any,
) -> None:
    """Vpad/reader dublados com MagicMock (atributo vira mock truthy) NÃO
    podem virar streaming=True nem taxa fantasma — tipagem estrita."""
    socket_path, daemon = servidor_com_motion
    daemon._gamepad_device = _vpad_ns(streaming=MagicMock())
    daemon._motion_reader = SimpleNamespace(emit_hz=MagicMock())
    per_vpad = await _per_vpad(socket_path)
    por_jogador = {item["player"]: item for item in per_vpad}
    assert por_jogador[1]["motion_streaming"] is False
    assert por_jogador[1]["motion_hz"] == 0.0


@pytest.mark.asyncio
async def test_state_full_ff_play_count_e_motion_hz_sao_por_vpad(
    servidor_com_motion: Any,
) -> None:
    """G3: `ff_play_count`/`motion_hz` são campos OPCIONAIS por-item de
    `per_vpad` — cada vpad carrega o SEU próprio contador/taxa, nunca o
    agregado (que segue existindo em `rumble_ff.plays`, para compat)."""
    socket_path, daemon = servidor_com_motion
    # P1 e o jogador 2 do co-op com contadores DIFERENTES — se algum dia a
    # leitura voltasse a agregar, os dois ficariam iguais (ao agregado).
    daemon._gamepad_device = _vpad_ns(streaming=True, ff_play_count=7)
    daemon._motion_reader = SimpleNamespace(emit_hz=248.3)
    daemon._coop_manager = SimpleNamespace(
        _players={
            "aa:bb:cc:dd:ee:02": SimpleNamespace(
                player_index=2,
                vpad=_vpad_ns(streaming=False, ff_play_count=3),
                motion_reader=SimpleNamespace(emit_hz=120.0),
            ),
        },
        player_count=lambda: 2,
    )
    per_vpad = await _per_vpad(socket_path)
    por_jogador = {item["player"]: item for item in per_vpad}
    for item in per_vpad:
        # Shape: os dois campos sempre presentes (opcionais só no SENTIDO de
        # nunca quebrarem consumidor antigo que os ignora — nunca ausentes).
        assert "ff_play_count" in item
        assert "motion_hz" in item
    assert por_jogador[1]["ff_play_count"] == 7
    assert por_jogador[1]["motion_hz"] == pytest.approx(248.3)
    assert por_jogador[2]["ff_play_count"] == 3
    assert por_jogador[2]["motion_hz"] == pytest.approx(120.0)
    # Agregado de compat segue somando os dois (não é o que este teste cobre,
    # só confirma que a introdução do per-vpad não o quebrou).
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    assert result["rumble_ff"]["plays"] == 10


# ---------------------------------------------------------------------------
# texto_motion — a linha discreta do card (função pura, sem GTK)
# ---------------------------------------------------------------------------


def _state(per_vpad: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rumble_ff": {"per_vpad": per_vpad}}


class TestTextoMotion:
    def test_primario_com_espelho_ativo_mostra_taxa(self) -> None:
        texto = texto_motion(
            {"is_primary": True},
            _state([{"player": 1, "motion_streaming": True, "motion_hz": 248.3}]),
        )
        assert texto == "Giroscópio: fluindo para o jogo (~248 Hz)"

    def test_jogador_do_coop_casa_pelo_numero_do_player(self) -> None:
        estado = _state(
            [
                {"player": 1, "motion_streaming": True, "motion_hz": 250.0},
                {"player": 2, "motion_streaming": True, "motion_hz": 120.0},
            ]
        )
        assert texto_motion({"player": 2}, estado) == (
            "Giroscópio: fluindo para o jogo (~120 Hz)"
        )

    def test_streaming_ativo_sem_taxa_ainda_mostra_sem_hz(self) -> None:
        """Logo após abrir o device a EMA ainda é 0 — a linha aparece sem
        número (mentir uma taxa seria pior que omiti-la)."""
        texto = texto_motion(
            {"is_primary": True},
            _state([{"player": 1, "motion_streaming": True, "motion_hz": 0.0}]),
        )
        assert texto == "Giroscópio: fluindo para o jogo"

    def test_sem_streaming_a_linha_some(self) -> None:
        """Ausência NUNCA vira alarme no card (uinput/xbox/Nativo não têm
        espelho por design) — quem acusa silêncio anômalo é o doctor."""
        texto = texto_motion(
            {"is_primary": True},
            _state([{"player": 1, "motion_streaming": False, "motion_hz": 0.0}]),
        )
        assert texto is None

    def test_controle_sem_vpad_proprio_nao_mostra_nada(self) -> None:
        """Não-primário sem número de jogador não tem vpad para falar."""
        estado = _state([{"player": 1, "motion_streaming": True, "motion_hz": 250.0}])
        assert texto_motion({"is_primary": False}, estado) is None
        assert texto_motion({}, estado) is None

    def test_secundario_com_player_1_de_coop_off_nao_mostra(self) -> None:
        """GYRO-03-FIX: co-op OFF numera TODOS os conectados como jogador 1
        (payload REAL tem player=1 + is_primary=False no secundário), mas o
        espelho do vpad P1 lê só o hidraw do PRIMÁRIO — a linha num
        secundário seria telemetria mentindo."""
        estado = _state([{"player": 1, "motion_streaming": True, "motion_hz": 250.0}])
        assert texto_motion({"is_primary": False, "player": 1}, estado) is None

    def test_primario_com_player_1_de_coop_off_mostra(self) -> None:
        """O payload real do primário (player=1 + is_primary=True) mantém a
        linha — o guarda do secundário não pode calar quem TEM o espelho."""
        estado = _state([{"player": 1, "motion_streaming": True, "motion_hz": 250.0}])
        assert texto_motion({"is_primary": True, "player": 1}, estado) == (
            "Giroscópio: fluindo para o jogo (~250 Hz)"
        )

    def test_dois_dualsense_coop_off_so_o_primario_mostra(self) -> None:
        """Cenário do achado: 2 DualSense, co-op off, espelho do P1 vivo —
        exatamente UM card (o do primário) mostra a linha de giroscópio."""
        estado = _state([{"player": 1, "motion_streaming": True, "motion_hz": 248.0}])
        entries = [
            {"is_primary": True, "player": 1, "uniq": "aa:bb:cc:dd:ee:01"},
            {"is_primary": False, "player": 1, "uniq": "aa:bb:cc:dd:ee:02"},
        ]
        textos = [texto_motion(e, estado) for e in entries]
        assert textos[0] == "Giroscópio: fluindo para o jogo (~248 Hz)"
        assert textos[1] is None

    def test_payload_malformado_nao_explode(self) -> None:
        assert texto_motion({"is_primary": True}, {}) is None
        assert texto_motion({"is_primary": True}, {"rumble_ff": None}) is None
        assert (
            texto_motion(
                {"is_primary": True}, {"rumble_ff": {"per_vpad": "lixo"}}
            )
            is None
        )
        assert (
            texto_motion({"is_primary": True}, _state(["lixo", None])) is None
        )

    def test_hz_malformado_cai_na_linha_sem_numero(self) -> None:
        texto = texto_motion(
            {"is_primary": True},
            _state([{"player": 1, "motion_streaming": True, "motion_hz": "x"}]),
        )
        assert texto == "Giroscópio: fluindo para o jogo"


class TestFiacaoNoCard:
    """Contrato de fonte (padrão do repo): o widget REAL e o stub consomem a
    MESMA função pura — sem GTK no processo de teste."""

    def _fonte(self) -> str:
        from hefesto_dualsense4unix.app.widgets import controller_card

        return Path(controller_card.__file__).read_text(encoding="utf-8")

    def test_widget_real_atualiza_a_linha_no_update(self) -> None:
        fonte = self._fonte()
        assert "self._update_motion(entry, state_global)" in fonte
        assert "self._motion_label" in fonte

    def test_linha_e_inline_dim_label_nunca_popup(self) -> None:
        """Veto cosmic-comp: indicador inline (dim-label), sem Popover/Popup."""
        fonte = self._fonte()
        inicio = fonte.index("GYRO-03: linha discreta")
        trecho = fonte[inicio : inicio + 600]
        assert 'add_class("dim-label")' in trecho
        assert "Popover" not in fonte

    def test_stub_espelha_a_semantica(self) -> None:
        assert "self.motion = texto_motion(entry, state_global)" in self._fonte()
