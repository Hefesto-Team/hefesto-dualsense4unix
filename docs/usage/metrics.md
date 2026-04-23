# Métricas Prometheus

O daemon Hefesto expõe métricas no formato Prometheus text exposition via HTTP
em `127.0.0.1:<metrics_port>/metrics`. Por padrão o endpoint está **desligado**;
é necessário habilitá-lo explicitamente.

---

## Habilitando as métricas

### Via arquivo de configuração do daemon

Edite (ou crie) `~/.config/hefesto/daemon.toml`:

```toml
[daemon]
metrics_enabled = true
metrics_port    = 9090   # padrão; altere se houver conflito
```

Reinicie o daemon:

```bash
systemctl --user restart hefesto.service
```

### Via variável de ambiente (temporário)

```bash
HEFESTO_METRICS=1 hefesto daemon start
```

> A variável `HEFESTO_METRICS=1` equivale a `metrics_enabled=true` com porta padrão.

---

## Verificando o endpoint

```bash
curl -s http://127.0.0.1:9090/metrics | head -30
```

Saída esperada (trecho):

```
# HELP hefesto_poll_ticks_total Total de ticks do poll loop
# TYPE hefesto_poll_ticks_total counter
hefesto_poll_ticks_total 3600

# HELP hefesto_controller_connected 1 se o controller está conectado, 0 caso contrário
# TYPE hefesto_controller_connected gauge
hefesto_controller_connected{transport="usb"} 1

# HELP hefesto_battery_pct Nível de bateria atual em porcentagem (-1 se desconhecido)
# TYPE hefesto_battery_pct gauge
hefesto_battery_pct 85
```

---

## Métricas disponíveis

| Métrica | Tipo | Descrição |
|---|---|---|
| `hefesto_poll_ticks_total` | counter | Ticks do poll loop desde o início |
| `hefesto_controller_connected{transport}` | gauge | 1 se conectado, 0 se desconectado |
| `hefesto_battery_pct` | gauge | Nível de bateria em % (-1 se desconhecido) |
| `hefesto_ipc_requests_total{method,status}` | counter | Requisições IPC por método e status |
| `hefesto_udp_packets_total{result}` | counter | Pacotes UDP por resultado |
| `hefesto_events_dispatched_total{topic}` | counter | Eventos publicados no bus por tópico |
| `hefesto_button_down_emitted_total` | counter | Eventos de botão pressionado |
| `hefesto_button_up_emitted_total` | counter | Eventos de botão liberado |

---

## Configurando o Prometheus

Adicione ao `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "hefesto"
    static_configs:
      - targets: ["127.0.0.1:9090"]
    scrape_interval: 15s
    metrics_path: /metrics
```

Intervalo recomendado: **15 segundos**. O daemon executa poll a 60 Hz; contadores
de tick crescem ~3600/min. Intervalos menores que 5s oferecem pouco benefício
extra e aumentam o custo de parse.

> **Nota de porta:** a porta padrão 9090 é usada por muitos componentes
> Prometheus. Se houver conflito, altere `metrics_port` na config do daemon
> e ajuste o `targets` acima.

---

## Scraping remoto

O endpoint só aceita conexões de `127.0.0.1` (loopback). Para expor a um
servidor Prometheus remoto, use um reverse proxy local:

### Exemplo com nginx

```nginx
server {
    listen 9091;
    location /metrics {
        proxy_pass http://127.0.0.1:9090/metrics;
        allow <ip-do-prometheus>;
        deny all;
    }
}
```

---

## Dashboard Grafana (referência)

Um dashboard básico pode ser construído com os painéis:

1. **Poll rate** — `rate(hefesto_poll_ticks_total[1m])` (linha, Hz alvo: ~60).
2. **Bateria** — `hefesto_battery_pct` (gauge 0-100).
3. **Conexão** — `hefesto_controller_connected` (stat, vermelho=0 verde=1).
4. **IPC por método** — `rate(hefesto_ipc_requests_total[5m])` agrupado por `method`.
5. **UDP aceito vs limitado** — `rate(hefesto_udp_packets_total[5m])` por `result`.

Dashboard Grafana preparado (JSON) sera adicionado em `docs/grafana/` em sprint futura.

---

## Segurança

- Bind exclusivo em `127.0.0.1` — nunca em `0.0.0.0`.
- Sem autenticação no endpoint. Acesso local apenas.
- Não há informações sensíveis nas métricas (sem PID, paths ou dados de usuario).
