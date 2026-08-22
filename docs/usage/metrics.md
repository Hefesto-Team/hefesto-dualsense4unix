# Métricas Prometheus

O daemon Hefesto - Dualsense4Unix expõe métricas no formato Prometheus text exposition via HTTP
em `127.0.0.1:<metrics_port>/metrics`. Por padrão o endpoint está **desligado**;
é necessário habilitá-lo explicitamente.

---

## Habilitando as métricas — o estado real hoje

**Existem duas variáveis de ambiente, desde 01/08/2026** (PROMESSA-NÃO-CUMPRIDA-01/C1).
Conferido rodando o código em 22/08/2026:

```bash
# ligar (só o valor "1" liga — "true" não liga, igual aos plugins)
HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED=1 hefesto-dualsense4unix daemon start

# e, se a 9090 estiver ocupada, escolher a porta
HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED=1 \
HEFESTO_DUALSENSE4UNIX_METRICS_PORT=19199 hefesto-dualsense4unix daemon start
```

Num serviço systemd, as mesmas duas linhas vão em `Environment=` na unit, antes
de o daemon subir.

> **A ressalva que continua de pé: existe chave, não existe botão.** Nada na
> árvore escreve estas variáveis por você — nem o `install.sh`, nem a unit
> systemd, nem a janela. Quem quiser as métricas exporta a variável à mão (ou
> edita a unit) antes de iniciar o daemon. Medido em 12/08/2026 e reconferido em
> 22/08/2026: a única ocorrência fora de `src/` é changelog de pacote, e ela não
> liga nada.
>
> **E ligar exige reiniciar o daemon.** O `MetricsSubsystem` só é instanciado na
> subida (`_start_metrics`, no caminho de start, que consulta
> `MetricsSubsystem.is_enabled`). O `reload_config` não o toca — zero ocorrências
> de `metrics` no corpo dele — então o `daemon.reload` via IPC, mesmo aceitando
> `config_overrides` com qualquer campo do `DaemonConfig`, **não** sobe o servidor
> num daemon que já está rodando. Esse é o segundo dos "dois que faltavam", e ele
> não foi feito.

**Por que a variável é o único caminho.** O `daemon/main.py` constrói o
`DaemonConfig` com quatro parâmetros — `poll_hz`, `auto_reconnect`,
`ps_long_press_ms` e `keyboard_emulation_enabled` — e `metrics_enabled` não é
nenhum deles: ele fica no default `False` e nada de fora do código o alcança. É
essa lacuna que o `MetricsSubsystem.is_enabled` cobre lendo a variável de
ambiente por cima da config.

O outro caminho, sem variável nenhuma, continua sendo `metrics_enabled=True` na
construção do `DaemonConfig` em `daemon/main.py` — mas isso é mexer no código.
Tudo o que vem abaixo (formato, métricas, scraping, dashboard) descreve o que o
`MetricsSubsystem` faz **quando ele sobe**.

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
  - job_name: "hefesto-dualsense4unix"
    static_configs:
      - targets: ["127.0.0.1:9090"]
    scrape_interval: 15s
    metrics_path: /metrics
```

Intervalo recomendado: **15 segundos**. O daemon executa poll a 60 Hz; contadores
de tick crescem ~3600/min. Intervalos menores que 5s oferecem pouco benefício
extra e aumentam o custo de parse.

> **Nota de porta:** a porta padrão 9090 é usada por muitos componentes
> Prometheus. Se houver conflito, exporte
> `HEFESTO_DUALSENSE4UNIX_METRICS_PORT` — ela vence o `metrics_port` do
> `DaemonConfig` (conferido em 22/08/2026: com a variável em `19199`, o endpoint
> sobe na 19199 e não na 9090). Valor não numérico ou fora da faixa 1–65535 não
> derruba o daemon: ele loga `metrics_port_env_invalida` ou
> `metrics_port_env_fora_da_faixa` e usa a porta da config.

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

Não há JSON de dashboard pronto no repositório. `docs/grafana/` foi anunciado em
versões anteriores desta página como algo que viria "em sprint futura" e nunca
existiu — os cinco painéis acima são a receita para montar o seu.

---

## Segurança

- Bind exclusivo em `127.0.0.1` — nunca em `0.0.0.0`.
- Sem autenticação no endpoint. Acesso local apenas.
- Não há informações sensíveis nas métricas (sem PID, paths ou dados de usuário).
