# Protocolo — Trigger Modes (dois níveis)

> Fonte canônica: `pydualsense >= 0.7.5` (`.venv/lib/.../pydualsense/enums.py`) para HID e README do DSX Paliverse para presets de alto nível. Esta tabela é referência para W2.1.

## Arquitetura em dois níveis

O DualSense aceita via HID apenas **10 modos low-level** + array de **7 forces** (bytes 0–255). Os "19 modos" documentados no DSX Paliverse são **presets de alto nível**: combinações específicas de `(mode, forces)` com semântica reconhecível (Galloping, Machine, Bow, etc.). Hefesto implementa os dois níveis:

- `hefesto.core.controller.IController.set_trigger(side, mode, forces)` — low-level direto.
- `hefesto.core.trigger_effects.TriggerEffect` + factories (`galloping(...)`, `machine(...)`, etc.) — high-level, traduzem para `(mode, forces)`.

---

## Nível 1 — HID low-level (pydualsense canônico)

10 modos; todos aceitam 7 bytes de `forces` (posições 0–6).

| ID     | `TriggerModes` enum | Valor | Descrição                                        |
|--------|---------------------|-------|--------------------------------------------------|
| 0x00   | `Off`               | 0     | Sem resistência                                  |
| 0x01   | `Rigid`             | 1     | Resistência contínua                             |
| 0x02   | `Pulse`             | 2     | Resistência em secção                            |
| 0x21   | `Rigid_A`           | 33    | Rigid + modifier A (bit 0x20)                    |
| 0x05   | `Rigid_B`           | 5     | Rigid + modifier B (bit 0x04)                    |
| 0x25   | `Rigid_AB`          | 37    | Rigid + A + B                                    |
| 0x22   | `Pulse_A`           | 34    | Pulse + modifier A                               |
| 0x06   | `Pulse_B`           | 6     | Pulse + modifier B                               |
| 0x26   | `Pulse_AB`          | 38    | Pulse + A + B (base para presets customizados)   |
| 0xFC   | `Calibration`       | 252   | Uso interno de calibração; não expor ao usuário  |

**Report layout** (confirmado em `pydualsense.py:551-567` e `:615-622`):
- `outReport[11]` ou `[12]`: `triggerR.mode.value`.
- `outReport[12..17, 20]` ou `[13..18, 21]`: `triggerR.forces[0..6]`.
- Análogo para `triggerL` nos offsets posteriores (USB) e 9 bytes adiante (BT).

## Nível 2 — Presets de alto nível (DSX Paliverse)

Os 19 efeitos nomeados do DSX são construídos por factories que produzem `(mode_low_level, forces_array)`. Factories vivem em `src/hefesto/core/trigger_effects.py`. Validação de ranges (via pydantic v2 ou `__post_init__`) protege o usuário de valores nocivos ao controle.

| Preset                         | Arity | Parâmetros nomeados                                                                                  | Mapeamento (exemplo)              |
|--------------------------------|-------|------------------------------------------------------------------------------------------------------|-----------------------------------|
| `off()`                        | 0     | —                                                                                                    | `(Off, [0]*7)`                    |
| `rigid(position, force)`       | 2     | `position (0–9)`, `force (0–255)`                                                                    | `(Rigid_B, [position, force, 0, 0, 0, 0, 0])` |
| `simple_rigid(strength)`       | 1     | `strength (0–8)`                                                                                     | atalho de `rigid(0, strength*32)` |
| `pulse()`                      | 0     | —                                                                                                    | `(Pulse, [0]*7)`                  |
| `pulse_a(start, end, force)`   | 3     | `start_pos`, `end_pos`, `force`                                                                      | `(Pulse_A, [start, end, force, 0, 0, 0, 0])` |
| `pulse_b(start, end, force)`   | 3     | `start_pos`, `end_pos`, `force` — ordem confirmada: start, end, force, demais zero                   | `(Pulse_B, [start, end, force, 0, 0, 0, 0])` |
| `resistance(start, force)`     | 2     | `start_pos (0–9)`, `force (0–8)`                                                                     | `(Rigid_AB, [start, force*32, 0, 0, 0, 0, 0])` |
| `bow(start, end, force, snap)` | 4     | `start (0–8)`, `end (1–9, > start)`, `force (0–8)`, `snap (0–8)`                                     | `(Pulse_AB, [start, end, force*32, snap*32, 0, 0, 0])` |
| `galloping(start, end, foot_a, foot_b, frequency)` | 5 | `start (0–8)`, `end (1–9)`, `foot_a (0–7)`, `foot_b (0–7)`, `frequency (0–255)` | `(Pulse_AB, [start, end, foot_a, foot_b, frequency, 0, 0])` |
| `semi_auto_gun(start, end, force)` | 3 | `start (2–7)`, `end (start+1 .. 8)`, `force (0–8)`                                                | `(Pulse_AB, [start, end, force*32, 0, 0, 0, 0])` |
| `auto_gun(start, strength, frequency)` | 3 | `start (0–9)`, `strength (0–8)`, `frequency (0–255)`                                          | `(Pulse_AB, [start, strength*32, frequency, 0, 0, 0, 0])` |
| `machine(start, end, amp_a, amp_b, frequency, period)` | 6 | 6 params; HID usa 7 forces, último sempre 0                                              | `(Pulse_AB, [start, end, amp_a, amp_b, frequency, period, 0])` |
| `feedback(position, strength)` | 2     | `position (0–9)`, `strength (0–8)`                                                                   | `(Rigid_B, [position, strength*32, 0, 0, 0, 0, 0])` |
| `weapon(start, end, force)`    | 3     | `start`, `end`, `force`                                                                              | `(Pulse_B, [start, end, force, 0, 0, 0, 0])` |
| `vibration(position, amplitude, frequency)` | 3 | `position (0–9)`, `amplitude (0–8)`, `frequency (0–255)`                                     | `(Pulse_A, [position, amplitude*32, frequency, 0, 0, 0, 0])` |
| `slope_feedback(start, end, start_strength, end_strength)` | 4 | `start`, `end`, `start_strength (1–8)`, `end_strength (1–8)`                     | `(Rigid_AB, [start, end, start_strength*32, end_strength*32, 0, 0, 0])` |
| `multi_position_feedback(strengths: list[int])` | 1 lista de 10 | Array com strength por posição                                                          | `(Rigid_AB, pack10to7bytes(strengths))` |
| `multi_position_vibration(frequency, strengths: list[int])` | 2 | `frequency`, array 10 strengths                                                      | `(Pulse_A, [frequency] + pack10to6bytes(strengths))` |
| `custom(mode, forces)`         | 2     | Escape hatch: `mode: TriggerModes`, `forces: list[int]` (7 elementos)                                | `(mode, forces)` literal          |

**Notas:**
- Multiplicador `*32` nas amplitudes normaliza `0–8` (DSX nomeado) para `0–255` (HID byte). Factories aplicam a conversão internamente; API pública usa os nomes DSX.
- `multi_position_*` comprime array de 10 valores em bits HID — ver `pack10to7bytes()` em `trigger_effects.py` quando implementado.

---

## Limites e saturação

- `frequency` aceita byte inteiro (0–255) no HID, mas o firmware do DualSense **satura em torno de 150–160 Hz** em modos `Pulse*`. Valores acima mantêm a saturação sem erro.
- `force` e `amplitude` em bytes puros saturam no máximo do motor; não há risco de dano por valores altos.
- Combinações não previstas de `mode` + `forces` podem gerar comportamento indefinido mas não danificar o controle (o firmware ignora bits inválidos).

## `CustomTriggerValue` no CLI

Acesso raw via `hefesto test trigger --raw --mode Pulse_AB --forces 0,9,7,7,10,0,0`. Exposição secundária; usuário comum usa presets nomeados. Documentar no guia de criação de perfis como ferramenta de experimentação.

---

## Status dos 4 pontos da auditoria

| Item | Questão original                       | Resposta fechada em V3                                                                      |
|------|----------------------------------------|---------------------------------------------------------------------------------------------|
| 1    | Arity de `Machine` (6 vs 7)            | **6 params nomeados** no preset; HID sempre recebe 7 forces, última posição preenchida com 0 |
| 2    | Ordem dos params de `PulseB`           | `start, end, force` (3 nomeados) → `forces = [start, end, force, 0, 0, 0, 0]`                |
| 3    | Limite absoluto de `frequency`         | **0–255 aceitos**; saturação de firmware em ~150–160 Hz em modos `Pulse*`                    |
| 4    | Exposição de `CustomTriggerValue` na CLI | **Exposto via `--raw`** em `hefesto test trigger`; presets nomeados continuam o default       |

W2.1 destravado.
