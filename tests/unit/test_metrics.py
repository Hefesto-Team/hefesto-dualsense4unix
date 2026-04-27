"""Testes unitários do subsystem de métricas Prometheus.

Cobre:
  - MetricsCollector.collect() gera texto válido em Prometheus exposition format.
  - Todas as métricas canônicas estão presentes no payload.
  - Labels são corretamente renderizadas (transport, result, topic, etc.).
  - MetricsSubsystem.is_enabled() segue config.metrics_enabled.
  - MetricsSubsystem sobe servidor HTTP em porta alta e responde /metrics.
  - MetricsSubsystem.stop() é idempotente (sem servidor levantado).
  - Rota inexistente devolve 404.
  - Porta ocupada não derruba o daemon (no-op com warning).
"""
from __future__ import annotations

import re
import socket
import urllib.request
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.metrics import (
    _BIND_HOST,
    MetricsCollector,
    MetricsSubsystem,
)

# ---------------------------------------------------------------------------
# Fixtures auxiliares
# ---------------------------------------------------------------------------


def _make_store(
    *,
    poll_ticks: int = 0,
    battery: int | None = None,
    controller_state: object | None = None,
    extra_counters: dict[str, int] | None = None,
) -> StateStore:
    """Cria um StateStore pré-populado para testes."""
    store = StateStore()
    if poll_ticks:
        for _ in range(poll_ticks):
            store.bump("poll.tick")
    if battery is not None:
        mock_cs = MagicMock()
        mock_cs.battery_pct = battery
        mock_cs.buttons_pressed = frozenset()
        mock_cs.transport = "usb"
        store.update_controller_state(mock_cs)
    if extra_counters:
        for key, value in extra_counters.items():
            store.bump(key, value)
    return store


def _free_port() -> int:
    """Retorna uma porta TCP livre em 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get_metrics(port: int) -> str:
    """Faz GET em http://127.0.0.1:<port>/metrics e retorna o body como string."""
    url = f"http://127.0.0.1:{port}/metrics"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Testes do MetricsCollector (sem rede)
# ---------------------------------------------------------------------------


class TestMetricsCollector:
    def _collector(self, **kwargs: object) -> MetricsCollector:
        store = _make_store(**kwargs)  # type: ignore[arg-type]
        controller = MagicMock()
        return MetricsCollector(store=store, controller=controller)

    def test_payload_tem_metricas_canonicas(self) -> None:
        """Payload contém pelo menos as 7 métricas canônicas da sprint."""
        payload = self._collector(poll_ticks=10, battery=80).collect()
        metricas = [
            "hefesto_poll_ticks_total",
            "hefesto_controller_connected",
            "hefesto_battery_pct",
            "hefesto_ipc_requests_total",
            "hefesto_udp_packets_total",
            "hefesto_events_dispatched_total",
            "hefesto_button_down_emitted_total",
            "hefesto_button_up_emitted_total",
        ]
        for metrica in metricas:
            assert metrica in payload, f"métrica ausente: {metrica}"

    def test_formato_help_e_type(self) -> None:
        """Cada bloco de métrica contém linhas # HELP e # TYPE."""
        payload = self._collector().collect()
        assert "# HELP hefesto_poll_ticks_total" in payload
        assert "# TYPE hefesto_poll_ticks_total counter" in payload

    def test_poll_ticks_reflete_contador(self) -> None:
        payload = self._collector(poll_ticks=42).collect()
        match = re.search(r"hefesto_poll_ticks_total (\d+)", payload)
        assert match is not None
        assert int(match.group(1)) == 42

    def test_battery_pct_com_controller_conectado(self) -> None:
        payload = self._collector(battery=75).collect()
        match = re.search(r"hefesto_battery_pct (\d+)", payload)
        assert match is not None
        assert int(match.group(1)) == 75

    def test_battery_pct_sem_controller(self) -> None:
        """Sem controller_state, battery_pct deve ser -1."""
        store = StateStore()
        collector = MetricsCollector(store=store, controller=MagicMock())
        payload = collector.collect()
        match = re.search(r"hefesto_battery_pct (-?\d+)", payload)
        assert match is not None
        assert int(match.group(1)) == -1

    def test_controller_connected_gauge_label_transport(self) -> None:
        """hefesto_controller_connected deve ter label transport='usb' quando conectado."""
        payload = self._collector(battery=80).collect()
        assert 'transport="usb"' in payload
        match = re.search(r'hefesto_controller_connected\{transport="usb"\} (\d)', payload)
        assert match is not None
        assert int(match.group(1)) == 1

    def test_controller_disconnected_gauge(self) -> None:
        """Sem controller, hefesto_controller_connected deve ser 0."""
        store = StateStore()
        collector = MetricsCollector(store=store, controller=MagicMock())
        payload = collector.collect()
        match = re.search(
            r'hefesto_controller_connected\{transport="([^"]+)"\} (\d)', payload
        )
        assert match is not None
        assert int(match.group(2)) == 0

    def test_udp_packets_total_tem_labels_result(self) -> None:
        """hefesto_udp_packets_total deve ter labels result=accepted e rate_limited."""
        payload = self._collector(
            extra_counters={"udp.accepted": 100, "udp.rate_limited": 5}
        ).collect()
        assert 'result="accepted"' in payload
        assert 'result="rate_limited"' in payload
        match_acc = re.search(r'hefesto_udp_packets_total\{result="accepted"\} (\d+)', payload)
        assert match_acc is not None
        assert int(match_acc.group(1)) == 100

    def test_ipc_requests_sem_counters_retorna_zero(self) -> None:
        """Sem contadores ipc.*, hefesto_ipc_requests_total deve ser 0."""
        payload = self._collector().collect()
        match = re.search(r"hefesto_ipc_requests_total (\d+)", payload)
        assert match is not None
        assert int(match.group(1)) == 0

    def test_ipc_requests_com_counters_tem_labels(self) -> None:
        """Com contadores ipc.*, payload deve ter labels method/status.

        Convenção: chave "ipc.<method>.<status>" onde status é o último
        segmento (após o último ponto) e method é o restante.
        Ex.: "ipc.daemon.status.ok" → method="daemon.status", status="ok".
        """
        payload = self._collector(
            extra_counters={"ipc.daemon.status.ok": 10}
        ).collect()
        assert 'method="daemon.status"' in payload
        assert 'status="ok"' in payload

    def test_events_dispatched_com_topic(self) -> None:
        """hefesto_events_dispatched_total deve expor tópicos como labels."""
        payload = self._collector(
            extra_counters={"event.battery_change": 7}
        ).collect()
        assert 'topic="battery_change"' in payload

    def test_button_down_up_contadores(self) -> None:
        """Contadores de botão refletem bumps em button.down.emitted e button.up.emitted."""
        payload = self._collector(
            extra_counters={"button.down.emitted": 15, "button.up.emitted": 12}
        ).collect()
        m_down = re.search(r"hefesto_button_down_emitted_total (\d+)", payload)
        m_up = re.search(r"hefesto_button_up_emitted_total (\d+)", payload)
        assert m_down is not None and int(m_down.group(1)) == 15
        assert m_up is not None and int(m_up.group(1)) == 12

    def test_minimo_cinco_linhas_hefesto_no_payload(self) -> None:
        """Requisito de integração: ao menos 5 linhas começando com hefesto_."""
        payload = self._collector(poll_ticks=5, battery=90).collect()
        linhas_hefesto = [linha for linha in payload.splitlines() if linha.startswith("hefesto_")]
        assert len(linhas_hefesto) >= 5, (
            f"esperado >= 5 linhas hefesto_, obtido {len(linhas_hefesto)}"
        )


# ---------------------------------------------------------------------------
# Testes do MetricsSubsystem (com servidor HTTP real)
# ---------------------------------------------------------------------------


class TestMetricsSubsystem:
    def _make_config(self, *, enabled: bool = True, port: int = 0) -> MagicMock:
        cfg = MagicMock()
        cfg.metrics_enabled = enabled
        cfg.metrics_port = port
        return cfg

    def _make_ctx(self, port: int) -> MagicMock:
        store = _make_store(poll_ticks=3, battery=70)
        ctx = MagicMock()
        ctx.store = store
        ctx.controller = MagicMock()
        ctx.config = self._make_config(enabled=True, port=port)
        return ctx

    def test_is_enabled_true(self) -> None:
        subsystem = MetricsSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = MetricsSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_servidor(self) -> None:
        """stop() sem servidor ativo não deve lançar exceção."""
        subsystem = MetricsSubsystem()
        await subsystem.stop()  # _server is None — idempotente

    @pytest.mark.asyncio
    async def test_servidor_sobe_e_responde_metrics(self) -> None:
        """Servidor HTTP sobe na porta livre e /metrics retorna 200."""
        port = _free_port()
        subsystem = MetricsSubsystem()
        ctx = self._make_ctx(port)
        await subsystem.start(ctx)
        try:
            payload = _get_metrics(port)
            assert "hefesto_poll_ticks_total" in payload
        finally:
            await subsystem.stop()

    @pytest.mark.asyncio
    async def test_metricas_tem_pelo_menos_cinco_linhas_hefesto(self) -> None:
        """Requisito principal da sprint: >= 5 linhas começando com hefesto_."""
        port = _free_port()
        subsystem = MetricsSubsystem()
        ctx = self._make_ctx(port)
        await subsystem.start(ctx)
        try:
            payload = _get_metrics(port)
            linhas = [ln for ln in payload.splitlines() if ln.startswith("hefesto_")]
            assert len(linhas) >= 5, (
                f"esperado >= 5 linhas hefesto_, obtido {len(linhas)}: {linhas}"
            )
        finally:
            await subsystem.stop()

    @pytest.mark.asyncio
    async def test_bind_somente_127_0_0_1(self) -> None:
        """Servidor deve bindar em 127.0.0.1 (constante _BIND_HOST)."""
        assert _BIND_HOST == "127.0.0.1", "bind host não pode ser 0.0.0.0"

    @pytest.mark.asyncio
    async def test_rota_inexistente_retorna_404(self) -> None:
        """GET /outra-rota deve retornar 404."""
        import urllib.error

        port = _free_port()
        subsystem = MetricsSubsystem()
        ctx = self._make_ctx(port)
        await subsystem.start(ctx)
        try:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/outra", timeout=5)
            assert exc_info.value.code == 404
        finally:
            await subsystem.stop()

    @pytest.mark.asyncio
    async def test_porta_ocupada_nao_derruba_daemon(self) -> None:
        """Se a porta estiver ocupada, MetricsSubsystem vira no-op (não lança)."""
        # Abre socket para ocupar a porta
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]

        subsystem = MetricsSubsystem()
        ctx = self._make_ctx(port)
        try:
            # Não deve lançar — deve apenas logar warning e ficar no-op
            await subsystem.start(ctx)
            assert subsystem._server is None, "servidor deveria ser None (porta ocupada)"
        finally:
            s.close()
            await subsystem.stop()

    @pytest.mark.asyncio
    async def test_stop_duplo_idempotente(self) -> None:
        """Chamar stop() duas vezes não deve lançar exceção."""
        port = _free_port()
        subsystem = MetricsSubsystem()
        ctx = self._make_ctx(port)
        await subsystem.start(ctx)
        await subsystem.stop()
        await subsystem.stop()  # segundo stop — deve ser silencioso
