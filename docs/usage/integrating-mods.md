# Integrando mods DSX

Mods do DSX Windows (Cyberpunk Immersive Triggers, Forza Horizon, Assetto Corsa Competizione, etc.) enviam comandos UDP para `127.0.0.1:6969`. Hefesto - Dualsense4Unix escuta a mesma porta e traduz para HID.

## Protocolo

Ver `docs/protocol/udp-schema.md` para o contrato completo. Envelope:

```json
{
  "version": 1,
  "instructions": [
    {"type": "TriggerUpdate",  "parameters": ["left", "Rigid", 10, 255, 0, 0, 0, 0, 0]},
    {"type": "RGBUpdate",      "parameters": [0, 255, 100, 50]},
    {"type": "TriggerThreshold","parameters": ["right", 128]}
  ]
}
```

`version != 1` é dropado silenciosamente com log warn.

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

## Rate limiting

- Global: 2000 pacotes/s agregados.
- Per-IP: 1000 pacotes/s.
- Excedentes: dropados silenciosamente, contadores em `state_store` (`udp.rate_limited`), log `warn` uma vez por segundo por IP congestionado.

## Mods conhecidos

| Mod                                | Jogo              | Status               |
|------------------------------------|-------------------|----------------------|
| DualSenseAT (Cyberpunk)            | Cyberpunk 2077    | Compatível (v1 schema) |
| CP2077 Immersive Gamepad           | Cyberpunk 2077    | Compatível           |
| Forza Horizon 5 Adaptive Triggers  | Forza Horizon 5   | Compatível           |
| Assetto Corsa ACC Triggers         | Assetto Corsa     | A confirmar          |

## Protocolo v2 (futuro)

Schema nomeado (campos por chave em vez de array posicional) está previsto para Hefesto - Dualsense4Unix v1.x. Até lá, mods seguem v1 posicional.
