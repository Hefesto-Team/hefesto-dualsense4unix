"""Subsystem de métricas Prometheus — HTTP exposition text format (sem dep externa)."""
from __future__ import annotations

import http.server
import os
import socketserver
import threading
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

_BIND_HOST = "127.0.0.1"

ENV_METRICS_PORT = "HEFESTO_DUALSENSE4UNIX_METRICS_PORT"

_LabeledSeries = list[tuple[dict[str, str], int | float]]


def _porta_efetiva(porta_da_config: int) -> int:
    """A porta do endpoint, com a variável de ambiente vencendo a config."""
    bruto = os.environ.get(ENV_METRICS_PORT)
    if bruto is None:
        return porta_da_config
    try:
        porta = int(bruto)
    except ValueError:
        logger.warning(
            "metrics_port_env_invalida", valor=bruto, usando=porta_da_config
        )
        return porta_da_config
    if not 1 <= porta <= 65535:
        logger.warning(
            "metrics_port_env_fora_da_faixa", valor=porta, usando=porta_da_config
        )
        return porta_da_config
    return porta


def _format_counter(name: str, help_text: str, value: int | float) -> str:
    """Formata um contador simples em Prometheus text exposition."""
    return (
        f"# HELP {name} {help_text}\n"
        f"# TYPE {name} counter\n"
        f"{name} {value}\n"
    )


def _format_gauge(name: str, help_text: str, value: int | float) -> str:
    """Formata um gauge simples em Prometheus text exposition."""
    return (
        f"# HELP {name} {help_text}\n"
        f"# TYPE {name} gauge\n"
        f"{name} {value}\n"
    )


def _render_labeled(
    name: str, help_text: str, metric_type: str, series: _LabeledSeries
) -> str:
    """Renderiza uma família de métricas com labels em text exposition."""
    lines: list[str] = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} {metric_type}",
    ]
    for label_dict, value in series:
        label_str = ",".join(f'{k}="{v}"' for k, v in label_dict.items())
        lines.append(f"{name}{{{label_str}}} {value}")
    lines.append("")
    return "\n".join(lines)


class MetricsCollector:
    """Coleta métricas do StateStore e do estado do controller."""

    def __init__(self, store: Any, controller: Any) -> None:
        self._store = store
        self._controller = controller

    def collect(self) -> str:
        """Gera o payload completo em Prometheus text exposition format."""
        snap = self._store.snapshot()
        counters = snap.counters

        parts: list[str] = []

        parts.append(
            _format_counter(
                "hefesto_poll_ticks_total",
                "Total de ticks do poll loop",
                counters.get("poll.tick", 0),
            )
        )

        transport = "unknown"
        connected = 0
        try:
            if snap.controller is not None:
                connected = 1
                transport = getattr(snap.controller, "transport", "usb") or "usb"
        except Exception:
            connected = 0
        parts.append(
            _render_labeled(
                "hefesto_controller_connected",
                "1 se o controller está conectado, 0 caso contrário",
                "gauge",
                [
                    ({"transport": str(transport)}, connected),
                ],
            )
        )

        # -- battery_pct -----------------------------------------------------
        battery = snap.last_battery_pct if snap.last_battery_pct is not None else -1
        parts.append(
            _format_gauge(
                "hefesto_battery_pct",
                "Nível de bateria atual em porcentagem (-1 se desconhecido)",
                battery,
            )
        )

        ipc_series: _LabeledSeries = []
        for key, value in counters.items():
            if key.startswith("ipc.") and key.count(".") >= 2:
                rest = key[len("ipc."):]
                last_dot = rest.rfind(".")
                method = rest[:last_dot]
                status = rest[last_dot + 1:]
                ipc_series.append(({"method": method, "status": status}, value))

        if ipc_series:
            parts.append(
                _render_labeled(
                    "hefesto_ipc_requests_total",
                    "Requisições IPC recebidas por método e status",
                    "counter",
                    ipc_series,
                )
            )
        else:
            parts.append(
                _format_counter(
                    "hefesto_ipc_requests_total",
                    "Requisições IPC recebidas",
                    0,
                )
            )

        udp_accepted = counters.get("udp.accepted", 0)
        udp_limited = counters.get("udp.rate_limited", 0)
        parts.append(
            _render_labeled(
                "hefesto_udp_packets_total",
                "Pacotes UDP recebidos por resultado",
                "counter",
                [
                    ({"result": "accepted"}, udp_accepted),
                    ({"result": "rate_limited"}, udp_limited),
                ],
            )
        )

        event_series: _LabeledSeries = []
        for key, value in counters.items():
            if key.startswith("event."):
                topic = key[len("event."):]
                event_series.append(({"topic": topic}, value))

        if event_series:
            parts.append(
                _render_labeled(
                    "hefesto_events_dispatched_total",
                    "Eventos publicados no bus por tópico",
                    "counter",
                    event_series,
                )
            )
        else:
            parts.append(
                _format_counter(
                    "hefesto_events_dispatched_total",
                    "Eventos publicados no bus",
                    0,
                )
            )

        parts.append(
            _format_counter(
                "hefesto_button_down_emitted_total",
                "Total de eventos de botão pressionado emitidos",
                counters.get("button.down.emitted", 0),
            )
        )
        parts.append(
            _format_counter(
                "hefesto_button_up_emitted_total",
                "Total de eventos de botão liberado emitidos",
                counters.get("button.up.emitted", 0),
            )
        )

        return "\n".join(parts)


def _make_handler(collector: MetricsCollector) -> type[http.server.BaseHTTPRequestHandler]:
    """Retorna uma classe de handler com o collector embutido via closure."""

    class _MetricsHandler(http.server.BaseHTTPRequestHandler):
        """Handler HTTP que serve o endpoint /metrics."""

        def do_GET(self) -> None:
            if self.path == "/metrics":
                try:
                    payload = collector.collect().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as exc:
                    logger.warning("metrics_handler_error", err=str(exc))
                    self.send_error(500, str(exc))
            else:
                self.send_error(404, "somente /metrics está disponível")

        def log_message(self, fmt: str, *args: Any) -> None:
            """Silencia logs do http.server para não poluir structlog."""

    return _MetricsHandler


class MetricsSubsystem:
    """Subsystem que expõe métricas em formato Prometheus via HTTP."""

    name = "metrics"

    def __init__(self) -> None:
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o servidor HTTP de métricas em thread daemon."""
        cfg = ctx.config
        port: int = _porta_efetiva(getattr(cfg, "metrics_port", 9090))
        collector = MetricsCollector(store=ctx.store, controller=ctx.controller)
        handler_cls = _make_handler(collector)

        try:
            server = socketserver.TCPServer((_BIND_HOST, port), handler_cls)
            server.allow_reuse_address = True
        except OSError as exc:
            logger.warning(
                "metrics_bind_failed",
                host=_BIND_HOST,
                port=port,
                err=str(exc),
            )
            return

        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
            name=f"hefesto-metrics-{port}",
        )
        self._thread.start()
        logger.info("metrics_subsystem_started", host=_BIND_HOST, port=port)

    async def stop(self) -> None:
        """Para o servidor HTTP de forma limpa. Idempotente."""
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as exc:
                logger.warning("metrics_stop_error", err=str(exc))
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("metrics_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Habilitado só com ``metrics_enabled`` — a mão é ``hefesto metrics ligar``."""
        return bool(getattr(config, "metrics_enabled", False))


__all__ = ["MetricsCollector", "MetricsSubsystem"]
