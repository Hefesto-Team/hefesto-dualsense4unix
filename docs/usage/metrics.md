# Métricas Prometheus

O serviço pode expor métricas no formato do Prometheus em
`http://127.0.0.1:<porta>/metrics`. Elas vêm desligadas.

## Ligar

```bash
hefesto-dualsense4unix metrics ligar
systemctl --user restart hefesto-dualsense4unix.service
```

O verbo grava `metrics.flag` na pasta de configuração, e o serviço lê a escolha
quando sobe: ligar exige reiniciar o serviço, porque o `daemon.reload` não sobe o
servidor de métricas. `hefesto-dualsense4unix metrics desligar` desfaz.

`HEFESTO_DUALSENSE4UNIX_METRICS_PORT` escolhe a porta (o padrão é 9090). Um valor
inválido não derruba o serviço: ele fica na porta padrão e registra o motivo no
diário. Essa variável é lida quando o serviço sobe.

O serviço constrói o `DaemonConfig` com cinco parâmetros (`poll_hz`,
`ps_long_press_ms`, `keyboard_emulation_enabled`,
`plugins_enabled` e `metrics_enabled`), e os dois últimos vêm dos arquivos que
`plugin ligar` e `metrics ligar` gravam.

## Conferir

```bash
curl -s http://127.0.0.1:9090/metrics | head -30
```

## As métricas

| Métrica | Tipo | O que conta |
|---|---|---|
| `hefesto_poll_ticks_total` | counter | leituras do controle desde a subida |
| `hefesto_controller_connected{jogador,transport}` | gauge | 1 com o controle desse jogador conectado, 0 sem |
| `hefesto_battery_pct{jogador}` | gauge | bateria desse controle em %, -1 se desconhecida |
| `hefesto_ipc_requests_total{method,status}` | counter | pedidos ao socket, por método e resultado |
| `hefesto_udp_packets_total{result}` | counter | pacotes UDP: `accepted` passou do limitador de taxa, `rate_limited` foi barrado |
| `hefesto_events_dispatched_total{topic}` | counter | eventos publicados no barramento, por tópico (contados com ou sem assinante) |
| `hefesto_button_down_emitted_total` | counter | botões apertados |
| `hefesto_button_up_emitted_total` | counter | botões soltos |

O rótulo `jogador` (1 a 4) é o número do cartão «Controle N» da janela, a mesma
lista por controle que o `daemon.state_full` publica: cabo e rádio, de P1 a P4. Com
nenhum controle conectado sai uma linha só, de `jogador="1"`, com conexão 0 e bateria -1.

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
perto de 60 Hz), `hefesto_battery_pct` (uma linha por jogador), `hefesto_controller_connected` e
`rate(hefesto_ipc_requests_total[5m])` por método.
