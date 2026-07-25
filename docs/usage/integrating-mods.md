# Integrando mods DSX

O daemon escuta UDP em `127.0.0.1:6969` — a mesma porta do DSX no Windows — e traduz as instruções para HID.

**O formato canônico do DSX é aceito.** O pacote que o SDK da Paliverse emite (sem campo `version`, `type` como ordinal do enum, `parameters[0]` = `controllerIndex`) chega e é executado. O dialeto textual do Hefesto continua valendo em paralelo, na mesma porta.

O que **ainda não** funciona sem adaptação está na tabela "Fidelidade ao DSX original — o que falta" em `docs/protocol/udp-schema.md`. O item que mais pesa: os modos de gatilho "prontos" do DSX (`Hard`, `Soft`, `Rigid`, `GameCube` e cia) não estão implementados e devolvem erro.

## Protocolo

Ver `docs/protocol/udp-schema.md` para o contrato completo.

Envelope do **DSX canônico** — o que um mod C# já emite hoje:

```json
{
  "instructions": [
    {"type": 1, "parameters": [0, 2, 15, 0, 9, 6, 7, 10]},
    {"type": 2, "parameters": [0, 255, 100, 50]},
    {"type": 4, "parameters": [0, 2, 128]}
  ]
}
```

Envelope do **dialeto do Hefesto** — textual, o mesmo efeito:

```json
{
  "version": 1,
  "instructions": [
    {"type": "TriggerUpdate",  "parameters": ["right", "Galloping", 0, 9, 6, 7, 10]},
    {"type": "RGBUpdate",      "parameters": [0, 255, 100, 50]},
    {"type": "TriggerThreshold","parameters": ["right", 128]}
  ]
}
```

`version` ausente = envelope do DSX. `version` presente e diferente de `1` é dropado com log warn.

## `TriggerThreshold`: leia antes de usar

Vira **deadzone do gatilho no gamepad virtual**, igual ao DSX: abaixo do limiar o jogo lê zero, do limiar em diante o valor bruto passa intacto (sem reescala). Três coisas que o exemplo acima não conta:

- **Só tem efeito com a emulação de gamepad ligada.** Em Modo Nativo não existe pad virtual: o limiar é guardado e não faz nada. O daemon loga `udp_trigger_threshold` em `info` a cada mudança — é assim que se confere.
- **Vale para o jogador 1.** O índice de controle é descartado.
- **É pegajoso:** sobrevive à saída do mod. Mande `ResetToUserSettings` ao encerrar (ou reinicie o daemon) para voltar ao padrão `0`.

O layout canônico do DSX (`[controllerIndex, side, value]`, com `side` em 1=Left / 2=Right) também é aceito.

## Jogos via Proton

Quando o jogo roda dentro do Proton, a rede é host-shared: o mod manda UDP para `127.0.0.1:6969` do Windows virtual, mas o socket vaza para o host Linux. Não precisa configuração extra.

## Exemplo Python

```python
import socket, json

pkt = {
    "version": 1,
    "instructions": [
        {"type": "TriggerUpdate", "parameters": ["right", "Galloping", 0, 9, 7, 7, 10, 0, 0]},
        {"type": "RGBUpdate", "parameters": [0, 255, 80, 0]},
    ],
}
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(json.dumps(pkt).encode(), ("127.0.0.1", 6969))
```

## Como saber se o daemon aceitou

Não há resposta no fio — UDP fire-and-forget, como no DSX. O que existe são contadores no `state_store`, visíveis pelo IPC de estado:

- `udp.applied.<type>` — instrução executada.
- `udp.error.<type>` — instrução conhecida que falhou na validação (parâmetro fora de range, preset inexistente, modo de gatilho sem tradução).
- `udp.unknown_instruction` — `type` que este daemon não conhece (também vai para o log `warn`).
- `udp.dsx_envelope` — pacote chegou no formato canônico do DSX (sem `version`).
- `udp.controller_index_ignorado` — o mod endereçou um controle que não o primário.
- `udp.mic_led.pulse_degradado` — pediu `Pulse` no LED do mic e recebeu aceso fixo.
- `udp.reset_parcial` — `ResetToUserSettings` rodou; o log diz o que voltou e o que não.
- `udp.unsupported_version`, `udp.parse_error`, `udp.oversize`, `udp.rate_limited` — descarte antes do dispatch.

## Rate limiting

- Global: 2000 pacotes/s agregados.
- Per-IP: 1000 pacotes/s.
- Excedentes: dropados, contadores em `state_store` (`udp.rate_limited`), log `warn` uma vez por segundo por IP congestionado.

## Mods conhecidos

Nenhum mod do DSX Windows foi executado ponta a ponta contra este daemon. O que **foi** verificado é o formato do fio: o pacote canônico do SDK (envelope sem `version`, `type` ordinal, `parameters` na ordem do `Instruction.cs`) é aceito e aplicado, com teste automatizado e medição em socket real.

Se um mod específico funciona depende dos **modos de gatilho** que ele usa: os paramétricos (`Resistance`, `Bow`, `Galloping`, `SemiAutomaticGun`, `AutomaticGun`, `Machine`, `CustomTriggerValue`) estão traduzidos; os "prontos" (`Hard`, `Soft`, `Rigid`, …) não.

| Mod                                | Jogo              | Status                                    |
|------------------------------------|-------------------|-------------------------------------------|
| DualSenseAT (Cyberpunk)            | Cyberpunk 2077    | Não executado — depende dos modos usados  |
| CP2077 Immersive Gamepad           | Cyberpunk 2077    | Não executado — depende dos modos usados  |
| Forza Horizon 5 Adaptive Triggers  | Forza Horizon 5   | Não executado — depende dos modos usados  |
| Assetto Corsa ACC Triggers         | Assetto Corsa     | Não executado — depende dos modos usados  |

Para descobrir onde um mod cai, olhe os contadores: `udp.applied.*` sobe quando a instrução foi executada, `udp.error.TriggerUpdate` quando o modo não tem tradução (o log nomeia o modo).

## Protocolo v2

Não existe, e não há trabalho em andamento. A ideia — schema nomeado, campos por chave em vez de array posicional — está registrada como *extensão futura* em `docs/protocol/udp-schema.md`; não há implementação, spec fechada nem prazo. O contrato em vigor é o v1 posicional, e `version != 1` continua sendo descartado com log de aviso.
