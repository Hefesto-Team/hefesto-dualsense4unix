# Protocolo — Trigger Modes canônicos

> Tabela de referência dos 19 modos de gatilho adaptativo do DualSense. Fonte: README do DSX Paliverse + enum `TriggerMode` do `pydualsense`. **Esta tabela é bloqueante para W2.1** — precisa revisão do mantenedor humano antes do primeiro commit de `trigger_effects.py`.

## Status

- Levantamento inicial: concluído (pydualsense 0.7.5).
- Revisão humana dos intervalos: **PENDENTE**.
- Testes em controle físico: pendentes até W2.2.

## Tabela

| ID | Nome             | Arity | Parâmetros                                                                                                            | Observações                                          |
|----|------------------|-------|-----------------------------------------------------------------------------------------------------------------------|------------------------------------------------------|
| 0  | `Off`            | 0     | —                                                                                                                     | Desliga efeito                                       |
| 1  | `Rigid`          | 2     | `position (0–9)`, `force (0–255)`                                                                                     | Barreira rígida numa posição                         |
| 2  | `Pulse`          | 0     | —                                                                                                                     | Pulso único                                          |
| 3  | `PulseA`         | 3     | `start_pos`, `end_pos`, `force`                                                                                       | Pulso entre posições                                 |
| 4  | `PulseB`         | 3     | Semelhante a PulseA com curva diferente                                                                               | Confirmar parâmetros com `pydualsense.TriggerMode`   |
| 5  | `Resistance`     | 2     | `start_pos (0–9)`, `force (0–8)`                                                                                      | Resistência constante a partir da posição            |
| 6  | `Bow`            | 4     | `start_pos (0–8)`, `end_pos (1–9, > start)`, `force (0–8)`, `snap_force (0–8)`                                        | Simula arco; snap ao soltar                          |
| 7  | `Galloping`      | 5     | `start_pos (0–8)`, `end_pos (1–9, > start)`, `first_foot (0–7)`, `second_foot (0–7)`, `frequency (0–255)`             | Cadência de galope; 5 params — versão canônica       |
| 8  | `SemiAutomaticGun` | 3   | `start_pos (2–7)`, `end_pos (>= start+1, <= 8)`, `force (0–8)`                                                        |                                                     |
| 9  | `AutomaticGun`   | 3     | `start_pos (0–9)`, `strength (0–8)`, `frequency (0–255)`                                                              | Vibração automática                                  |
| 10 | `Machine`        | 6     | `start_pos`, `end_pos`, `amp_a`, `amp_b`, `frequency`, `period`                                                       | 6 params — confirmar ordem com pydualsense           |
| 11 | `Feedback`       | 2     | `position (0–9)`, `strength (0–8)`                                                                                    | Feedback simples                                     |
| 12 | `Weapon`         | 3     | `start_pos`, `end_pos`, `force`                                                                                       | Disparo de arma                                      |
| 13 | `Vibration`      | 3     | `position (0–9)`, `amplitude (0–8)`, `frequency (0–255)`                                                              | Vibração contínua                                    |
| 14 | `SlopeFeedback`  | 4     | `start_pos`, `end_pos`, `start_strength (1–8)`, `end_strength (1–8)`                                                  | Feedback em rampa                                    |
| 15 | `MultiplePositionFeedback` | 10 | Array com 10 strengths, 1 por posição                                                                       | Perfil customizado por posição                       |
| 16 | `MultiplePositionVibration` | 11 | `frequency`, array 10 strengths                                                                            |                                                      |
| 17 | `CustomTriggerValue` | variável | Bytes brutos — depende do modo interno                                                                          | Avançado; não expor na UI v0.x                       |
| 18 | `SimpleRigid`    | 1     | `strength (0–8)`                                                                                                      | Atalho simplificado de `Rigid`                       |

## Fonte canônica no código

`src/hefesto/core/trigger_effects.py` exporta `TriggerMode` (enum) e dataclasses por modo. Factory functions correspondem linha a linha aos IDs acima. Validação de ranges é responsabilidade do dataclass (pydantic v2 ou `__post_init__`).

## Itens pendentes de validação humana

1. Arity de `Machine` — 6 params é a versão do DSX Paliverse; conferir contra `pydualsense` que pode expor 7 (um extra de phase).
2. Ordem dos params de `PulseB` — divergências entre docs online e código da lib.
3. Limites absolutos de `frequency` — README do DSX diz `0–255`, alguns fóruns reportam saturação em `0–160`.
4. `CustomTriggerValue` — decidir se exporta na CLI ou só no UDP passthrough.
