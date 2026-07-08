# Criando perfis

## Estrutura

Perfis ficam em `~/.config/hefesto-dualsense4unix/profiles/<nome>.json`. Schema v1:

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

## Seção opcional `mouse` e `suppress_desktop_emulation`

Desde a wave V3.11 (FEAT-POINT-AND-CLICK-01) o perfil pode controlar a emulação
de mouse e o modo-jogo:

```json
{
  "mouse": {"enabled": true, "speed": 8, "scroll_speed": 1},
  "suppress_desktop_emulation": false
}
```

- `mouse` ausente (ou `null`) → ativar o perfil **não toca** no estado da
  emulação (comportamento de sempre). Presente → liga/desliga com `speed`
  (1-12) e `scroll_speed` (1-5) do perfil, em qualquer rota de ativação
  (autoswitch por janela, `profile activate`, hotkey PS+D-pad, restore no boot).
- `suppress_desktop_emulation: true` → ativa o modo-jogo (suprime os bindings
  de teclado/mouse no desktop) — útil para jogos de **gamepad** que leem o
  controle cru. Perfil sem o campo libera a supressão apenas quando ela veio de
  outro perfil; o toggle manual (PS+Options, GUI, CLI) é sempre respeitado e
  trava mudanças por perfil por 30 s. Atenção: este campo NÃO desliga o gamepad
  virtual (footgun documentado — o gamepad do jogo morreria no meio da partida).

## Perfil default `point_and_click` (Grim Fandango e afins)

Instalado com os presets, casa `window_class` `GrimFandango`/`grim` com
`priority: 60` (acima de `navegacao`, 50). O match é Grim-específico de
propósito: o port Linux do Grim Fandango Remastered é NATIVO (não roda sob
ScummVM), e casar `scummvm`/`residualvm` genéricos sequestraria QUALQUER jogo
ScummVM — inclusive os que você joga de gamepad, ligando o modo mouse e matando
o gamepad virtual. Para levar o point-and-click a outra aventura, adicione o
`window_class` dela ao perfil pela GUI. Ao focar o jogo:

- **Mouse liga** com `speed: 8` — stick move o cursor; X/L2 = clique esquerdo
  (andar/interagir), Triângulo/R2 = clique direito, R3 = botão do meio,
  Círculo = Enter, Quadrado = Esc, D-pad = setas (mapeamentos fixos do device
  de mouse).
- **Teclado do jogo** (override completo — nada de Super/Alt+Tab/PrintScreen
  vazando para o desktop): L1 = Shift (correr), R1 = `.` (pular diálogo),
  Options = Esc (menu), Create = I (inventário), touchpad esquerda/meio/
  direita = E (examinar) / U (usar) / P (pegar).
- Gatilhos Off/Off, rumble passthrough, lightbar âmbar.

Notas para o Grim Fandango Remastered:

- O port Linux é nativo e tem point-and-click por mouse oficial (código do mod
  Grim Mouse, 2015) — o modo mouse é o caminho preferido neste jogo.
- **Steam Input permanece OFF** para este título: a combinação é incompatível
  no Linux (bug conhecido desde 2019) e quebra o controle dentro do jogo.
- Rota alternativa de **gamepad nativo** (jogos de gamepad com SDL antigo): o
  `controllerdef.txt` embarcado não conhece o DualSense, mas conhece o X360 —
  ligue o gamepad virtual com máscara xbox360 (`hefesto-dualsense4unix emulate
  --flavor xbox` ou aba Emulação) e abra o jogo **depois** de o device virtual
  existir (SDL 2.0.3 só enumera na inicialização). Não é o caminho preferido
  para o Grim; fica registrado para títulos sem suporte a mouse.

Antes de confiar no match, confirme o `wm_class` real da janela com o jogo
aberto (ver seção abaixo) — ports via Proton/ScummVM usam classes diferentes.

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

O segundo valor de `WM_CLASS` é o que o Hefesto - Dualsense4Unix usa. Apps Qt/GTK podem ter `instance` e `class` idênticos; outros divergem (Steam aparece como `Steam` no campo `class`).

## Criando via CLI

```bash
hefesto-dualsense4unix profile create driving \
    --priority 10 \
    --match-class "steam_app_1091500" \
    --match-regex "Cyberpunk|Forza" \
    --match-exe "Cyberpunk2077.exe"
```

Perfis criados via CLI abrem com triggers `Off`; edite o JSON para ajustar.

## Listando, ativando, removendo

```bash
hefesto-dualsense4unix profile list                        # tabela rich
hefesto-dualsense4unix profile show shooter                # JSON pretty
hefesto-dualsense4unix profile activate shooter            # aplica direto (via IPC se daemon ativo)
hefesto-dualsense4unix profile delete old_one --yes        # remove arquivo
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
