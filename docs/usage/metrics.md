# Métricas Prometheus

O daemon Hefesto - Dualsense4Unix expõe métricas no formato Prometheus text exposition via HTTP
em `127.0.0.1:<metrics_port>/metrics`. Por padrão o endpoint está **desligado**;
é necessário habilitá-lo explicitamente.

---

## Habilitando as métricas — o estado real hoje

> **Não há caminho de usuário para ligar isto.** Versões anteriores desta página
> ensinavam duas receitas — um bloco `[daemon]` no `daemon.toml` e a variável
> `HEFESTO_DUALSENSE4UNIX_METRICS=1`. <!-- ref-externa: a variável é citada aqui JUSTAMENTE por não existir; a ausência dela é o assunto do parágrafo -->
> **Nenhuma das duas funciona, e nenhuma nunca funcionou.** Conferido no código
> em 25/07/2026:
>
> - O daemon **não lê `daemon.toml`** (o arquivo é referência; ele mesmo diz
>   isso no cabeçalho que a GUI escreve).
> - `HEFESTO_DUALSENSE4UNIX_METRICS` **não existe** no código: zero ocorrências em `src/`. <!-- ref-externa: idem — a ausência é a informação -->
> - `daemon/main.py` constrói o `DaemonConfig` com quatro parâmetros —
>   `poll_hz`, `auto_reconnect`, `ps_long_press_ms` e
>   `keyboard_emulation_enabled`. `metrics_enabled` fica no default `False` e
>   nada o alcança.
> - O `MetricsSubsystem` só é instanciado **na subida** do daemon
>   (`_start_metrics`, na sequência de start). O `reload_config` não o
>   reinicia — então nem o `daemon.reload` via IPC, que aceita
>   `config_overrides` com qualquer campo do `DaemonConfig`, sobe o servidor
>   num daemon que já está rodando.
>
> **Recontagem de 01/08/2026 (DOC-VERDADE-02, E7):** o terceiro item dizia
> "três" e listava só os três primeiros. Ficou falso em 29/07, quando
> a EMULACAO-NO-JOGO-01 acrescentou `keyboard_emulation_enabled` à construção do
> `DaemonConfig` — o campo que desliga o teclado emulado dentro da partida. A
> confissão continua inteira; só a contagem mudou.

Consequência honesta: **subir o endpoint hoje exige mexer no código** — passar
`metrics_enabled=True` na construção do `DaemonConfig` em
`daemon/main.py` — e reiniciar o daemon. Tudo o que vem abaixo (formato,
métricas, scraping, dashboard) descreve corretamente o que o
`MetricsSubsystem` faz **quando ele sobe**; só a chave de ligar é que falta.

O que falta para isto virar recurso de usuário é pequeno e está identificado:
uma variável de ambiente lida em `daemon/main.py` — como `poll_hz`,
`ps_long_press_ms` e `keyboard_emulation_enabled` já são (`auto_reconnect` é o
único dos quatro que vem do argumento da linha de comando, não do ambiente) —
ou o `reload_config` passando a parar/subir o `MetricsSubsystem` quando
`metrics_enabled` muda. Nenhum dos dois foi feito.

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
> Prometheus. Se houver conflito, altere `metrics_port` no `DaemonConfig` —
> vale a mesma ressalva da seção "Habilitando": esse campo também não tem
> hoje chave de usuário.

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
