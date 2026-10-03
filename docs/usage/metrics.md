# Métricas Prometheus

O serviço pode expor métricas no formato do Prometheus em
`http://127.0.0.1:<porta>/metrics`. Elas vêm desligadas.

## Ligar

Duas variáveis de ambiente, lidas quando o serviço sobe:

- `HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED=1` liga (só o valor `1` liga);
- `HEFESTO_DUALSENSE4UNIX_METRICS_PORT` escolhe a porta (o padrão é 9090). Um
  valor inválido não derruba o serviço: ele fica na porta padrão e registra o
  motivo no diário.

```bash
systemctl --user set-environment HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED=1 \
                                 HEFESTO_DUALSENSE4UNIX_METRICS_PORT=19199
systemctl --user restart hefesto-dualsense4unix.service
```

Nada no instalador nem na janela liga as métricas por você, e ligar exige
reiniciar o serviço: o `daemon.reload` não sobe o servidor de métricas.

As variáveis são o único caminho porque o serviço constrói o `DaemonConfig` com
cinco parâmetros (`poll_hz`, `auto_reconnect`, `ps_long_press_ms`,
`keyboard_emulation_enabled` e `plugins_enabled`), e `metrics_enabled` não é um
deles.

## Conferir

```bash
curl -s http://127.0.0.1:9090/metrics | head -30
```

## As métricas

| Métrica | Tipo | O que conta |
|---|---|---|
| `hefesto_poll_ticks_total` | counter | leituras do controle desde a subida |
| `hefesto_controller_connected{transport}` | gauge | 1 com o controle conectado, 0 sem |
| `hefesto_battery_pct` | gauge | bateria em %, -1 se desconhecida |
| `hefesto_ipc_requests_total{method,status}` | counter | pedidos ao socket, por método e resultado |
| `hefesto_udp_packets_total{result}` | counter | pacotes UDP, por resultado |
| `hefesto_events_dispatched_total{topic}` | counter | eventos internos, por tópico |
| `hefesto_button_down_emitted_total` | counter | botões apertados |
| `hefesto_button_up_emitted_total` | counter | botões soltos |

## Prometheus

```yaml
scrape_configs:
  - job_name: "hefesto-dualsense4unix"
    static_configs:
      - targets: ["127.0.0.1:9090"]
    scrape_interval: 15s
```

O endpoint só escuta em `127.0.0.1` e não tem autenticação. Para um Prometheus
em outra máquina, ponha um proxy reverso local na frente dele. As métricas não
levam caminho, PID nem dado pessoal.

Painéis úteis: `rate(hefesto_poll_ticks_total[1m])` (a frequência de leitura,
perto de 60 Hz), `hefesto_battery_pct`, `hefesto_controller_connected` e
`rate(hefesto_ipc_requests_total[5m])` por método.
