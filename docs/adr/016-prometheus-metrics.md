# ADR-016 — Endpoint de métricas Prometheus

**Status:** aceito
**Data:** 2026-04-22
**Sprint:** FEAT-METRICS-01

---

## Contexto

O daemon Hefesto não expunha dados quantitativos de saúde. Para diagnosticar
lentidão, alta carga de CPU ou perda de pacotes UDP, o usuário precisava
cruzar `top`/`htop` com logs estruturados manualmente. Sem métrica de poll
tick ou latência de loop, é impossível distinguir "controle lento por USB" de
"controle lento por daemon sobrecarregado".

Meta-regra 9.4 do projeto: "sistema adaptativo sem métrica de saúde é
bomba-relógio".

---

## Decisão

Implementar um servidor HTTP minimalista em `127.0.0.1:<metrics_port>/metrics`
que serializa contadores e gauges do `StateStore` no formato
**Prometheus text exposition 0.0.4** (text/plain, sem dep externa).

Características principais:

- Bind exclusivo em `127.0.0.1` — scraping remoto exige reverse proxy.
- Padrão desligado (`metrics_enabled=False`). Opt-in via config ou env.
- Porta padrão: `9090` (`metrics_port` em `DaemonConfig`).
- Se a porta estiver ocupada, o subsystem vira no-op (loga warning, daemon continua).
- Não adiciona `prometheus_client` como dep obrigatória. Extra opcional
  `[metrics]` em `pyproject.toml` para quem quiser usar a biblioteca oficial.

---

## Esquema de métricas

### Contadores (sempre crescentes)

| Métrica | Labels | Origem no StateStore |
|---|---|---|
| `hefesto_poll_ticks_total` | — | `poll.tick` |
| `hefesto_ipc_requests_total` | `method`, `status` | `ipc.<method>.<status>` |
| `hefesto_udp_packets_total` | `result` | `udp.accepted`, `udp.rate_limited` |
| `hefesto_events_dispatched_total` | `topic` | `event.<topic>` |
| `hefesto_button_down_emitted_total` | — | `button.down.emitted` |
| `hefesto_button_up_emitted_total` | — | `button.up.emitted` |

### Gauges (valor instantâneo)

| Métrica | Labels | Origem |
|---|---|---|
| `hefesto_controller_connected` | `transport` | `StateStore.snapshot().controller is not None` |
| `hefesto_battery_pct` | — | `StateStore.last_battery_pct` |

---

## Convenção de nomes

- Prefixo obrigatório: `hefesto_`.
- Sufixo de unidade (quando aplicável): `_total` para counters, `_seconds`, `_pct`.
- Labels em snake_case ASCII; valores em lowercase.
- Chaves de contador no StateStore seguem o padrão `<subsistema>.<campo>`:
  - `poll.tick`, `button.down.emitted`, `udp.accepted`, `ipc.daemon.status.ok`.
  - Para IPC: `ipc.<method>.<status>` onde `status` é o último segmento e
    `method` é tudo entre o prefixo e o status. Ex.: `ipc.daemon.status.ok`
    → `method="daemon.status"`, `status="ok"`.

---

## Arquitetura

```
DaemonConfig
  metrics_enabled: bool = False
  metrics_port:    int  = 9090

MetricsSubsystem (subsystems/metrics.py)
  is_enabled(config) → config.metrics_enabled
  start(ctx)         → sobe TCPServer em thread daemon em 127.0.0.1:port
  stop()             → server.shutdown() + thread.join(3s) — idempotente

MetricsCollector
  collect()          → lê StateStore.snapshot() → serializa texto Prometheus
  (instanciada dentro de start(); injetada no handler via closure)

_make_handler(collector)
  → classe _MetricsHandler(BaseHTTPRequestHandler)
  → do_GET: "/metrics" → 200 text/plain; outros → 404
  → log_message() silenciado (sem poluir structlog)
```

---

## Alternativas consideradas

### Usar `prometheus_client`

**Rejeitada para dep obrigatória.** A biblioteca adiciona ~800 KB e threads
internas que duplicariam o servidor HTTP. Para o nível V1, a serialização manual
é suficiente e evita uma dep nova no core. Disponível como extra opcional.

### Expor via socket Unix (não HTTP)

Rejeitada. Prometheus scraper padrão faz HTTP. Socket Unix exigiria exporter
intermediário.

### Bind em `0.0.0.0`

Rejeitada. Porta de métricas em rede local sem autenticação é superfície de
ataque desnecessária. Reverse proxy (nginx, caddy) é o caminho para scraping remoto.

---

## Consequências

**Positivas:**
- Diagnóstico quantitativo de poll rate, latência e tráfego IPC/UDP.
- Compatível com Prometheus + Grafana sem instalação de agent extra.
- Zero dep nova obrigatória.

**Negativas / limitações:**
- Sem histograma de latência por tick (poll_duration_seconds). Previsto para V2.1.
- Sem autenticação no endpoint. Mitigado pelo bind localhost-only.
- Porta 9090 colide com Prometheus server padrão. Documentado em `docs/usage/metrics.md`.

---

## Referências

- [Prometheus text exposition format 0.0.4](https://prometheus.io/docs/instrumenting/exposition_formats/)
- `src/hefesto_dualsense4unix/daemon/subsystems/metrics.py`
- `docs/usage/metrics.md`
- Sprint FEAT-METRICS-01

## Nota de verificação — 2026-07-25

A decisão diz "opt-in via config ou env". **Nenhuma das duas existe.** Não há
variável de ambiente de métricas no código (`HEFESTO_DUALSENSE4UNIX_METRICS`
tem zero ocorrências em `src/`), e o daemon não lê arquivo de configuração. O
`DaemonConfig` é construído com três parâmetros (`poll_hz`, `auto_reconnect`,
`ps_long_press_ms`), então `metrics_enabled` fica preso no default `False`. O
`MetricsSubsystem` só é instanciado na sequência de start, e o `reload_config`
não o reinicia — logo nem o `daemon.reload` via IPC liga o endpoint num daemon
já rodando.

> **Essa contagem caducou quatro dias depois** — hoje são quatro parâmetros.
> Ver a nota de 2026-08-01, abaixo.

Consequência prática: hoje o endpoint só sobe mexendo no código. O item
"histograma de latência por tick, previsto para V2.1" também não foi feito, e
não há trabalho em andamento. Detalhe em `docs/usage/metrics.md`.

## Nota de verificação — 2026-08-01

Corrige um número da nota anterior, e só ele. O veredito de 25/07 continua de
pé: não há chave de usuário para as métricas, e subir o endpoint exige mexer no
código.

O `DaemonConfig` é construído em `daemon/main.py` com **quatro** parâmetros, não
três: `poll_hz`, `auto_reconnect`, `ps_long_press_ms` e
`keyboard_emulation_enabled`. O quarto entrou em 29/07 com a
EMULACAO-NO-JOGO-01 — é o campo que desliga o teclado emulado dentro da
partida, lido de `HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION`.

Vale registrar por que o erro passou: esta ADR, o `README.md` e o
`docs/usage/metrics.md` são as três páginas **mais honestas** do projeto, e
erram por serem específicas. Uma frase que diz "três, e são estas" envelhece no
dia em que nasce a quarta; uma frase vaga nunca envelhece porque nunca afirmou
nada. A cura não é voltar a ser vago — é o teste que conta os parâmetros no
código e cobra o mesmo número aqui
(`tests/unit/test_doc_verdade_02_contagens_derivadas.py`).
