# Criando perfis

## Estrutura

Perfis ficam em `~/.config/hefesto/profiles/<nome>.json`. Schema v1:

```json
{
  "name": "cyberpunk_driving",
  "version": 1,
  "match": {
    "type": "criteria",
    "window_class": ["steam_app_1091500"],
    "window_title_regex": "Cyberpunk",
    "process_name": ["Cyberpunk2077.exe"]
  },
  "priority": 10,
  "triggers": {
    "left":  {"mode": "Medium", "params": []},
    "right": {"mode": "Galloping", "params": [0, 9, 7, 7, 10]}
  },
  "leds": {
    "lightbar": [255, 80, 0],
    "player_leds": [false, true, true, true, false]
  },
  "rumble": {"passthrough": true}
}
```

Arquivo fallback com `match.type = "any"` e `priority: 0` é obrigatório para garantir que algum perfil sempre case.

## Semântica de match

- **AND entre campos preenchidos**: se `window_class` E `process_name` estão setados, ambos precisam bater.
- **OR dentro de cada lista**: `window_class: ["a", "b"]` casa qualquer um.
- **Regex**: `window_title_regex` usa `re.search` (padrões com `.*` são redundantes).
- **Basename**: `process_name` casa com o basename de `/proc/PID/exe`, não `comm` truncado.
- **Prioridade**: perfil com maior `priority` vence em empate.

## Descobrindo wm_class / title / exe

Com a janela-alvo em foco, rode:

```bash
xprop WM_CLASS                              # clique na janela; retorna ("instance", "Class")
xdotool getactivewindow getwindowname       # título atual
xdotool getactivewindow getwindowpid        # pid → readlink /proc/<pid>/exe
```

O segundo valor de `WM_CLASS` é o que o Hefesto usa. Apps Qt/GTK podem ter `instance` e `class` idênticos; outros divergem (Steam aparece como `Steam` no campo `class`).

## Criando via CLI

```bash
hefesto profile create driving \
    --priority 10 \
    --match-class "steam_app_1091500" \
    --match-regex "Cyberpunk|Forza" \
    --match-exe "Cyberpunk2077.exe"
```

Perfis criados via CLI abrem com triggers `Off`; edite o JSON para ajustar.

## Listando, ativando, removendo

```bash
hefesto profile list                        # tabela rich
hefesto profile show shooter                # JSON pretty
hefesto profile activate shooter            # aplica direto (via IPC se daemon ativo)
hefesto profile delete old_one --yes        # remove arquivo
```

## Fallback

```json
{
  "name": "fallback",
  "version": 1,
  "match": {"type": "any"},
  "priority": 0,
  "triggers": {
    "left":  {"mode": "Off", "params": []},
    "right": {"mode": "Off", "params": []}
  },
  "leds": {"lightbar": [40, 40, 40], "player_leds": [false, false, true, false, false]},
  "rumble": {"passthrough": true}
}
```

Sem fallback, `select_for_window` retorna `None` e nenhum perfil é aplicado quando a janela ativa não casa com nenhum matcher específico.

## Modos de trigger

Ver `docs/protocol/trigger-modes.md` para a tabela completa dos 19 presets nomeados + conversão para 10 modos HID low-level.

Presets comuns:

| Preset       | Arity | Exemplo                                    |
|--------------|-------|--------------------------------------------|
| `Off`        | 0     | `[]`                                       |
| `Rigid`      | 2     | `[5, 200]` (position, force)               |
| `Resistance` | 2     | `[3, 5]` (start, force 0-8)                |
| `Bow`        | 4     | `[1, 7, 8, 8]` (start, end, force, snap)   |
| `Galloping`  | 5     | `[0, 9, 7, 7, 10]` (start, end, f1, f2, freq) |
| `Machine`    | 6     | `[0, 9, 3, 3, 50, 8]`                      |
| `Weapon`     | 3     | `[2, 5, 200]`                              |
| `Vibration`  | 3     | `[3, 4, 40]` (pos, amp, freq)              |

Valores fora de range levantam `ValueError` na carga do perfil.
