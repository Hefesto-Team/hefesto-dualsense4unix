# Protocolo UDP — compatível com DSX v1

## Endpoint

`127.0.0.1:6969` (UDP). Configurável em `~/.config/hefesto/daemon.toml`.

## Envelope

```json
{
  "version": 1,
  "instructions": [ {"type": "...", "parameters": [...]} ]
}
```

Envelopes com `version != 1` são dropados com `log.warn` (V2 5.10).

## Instruções suportadas

| type                | parameters                                                                       |
|---------------------|----------------------------------------------------------------------------------|
| `TriggerUpdate`     | `[side, mode, p1, p2, p3, p4, p5, p6, p7]` — aridade depende do `mode`           |
| `RGBUpdate`         | `[controller_idx, r, g, b]`                                                      |
| `PlayerLED`         | `[idx, bitmask]`                                                                 |
| `MicLED`            | `[state]`                                                                        |
| `TriggerThreshold`  | `[side, value]`                                                                  |
| `ResetToUserSettings` | `[]`                                                                           |

Validação via pydantic v2 com `discriminator` sobre `type`. Params posicionais mantidos para compat bit-a-bit com o schema DSX original.

## Rate limiting

Dois limites sobrepostos (V3-1):

- Global: 2000 pkt/s agregados.
- Per-IP: 1000 pkt/s.

IPs inativos evictados por `_sweep` periódico (máximo 1x/s).

## Extensões futuras (v2)

Schema nomeado (`{"type": "trigger", "side": "left", "mode": "Rigid", "params": {"position": 5, "force": 200}}`) previsto para v1.x+, sem pressa. Até lá, clientes enviam v1.
