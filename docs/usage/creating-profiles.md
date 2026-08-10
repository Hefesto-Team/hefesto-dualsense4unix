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
    "left":  {"mode": "Resistance", "params": [3, 5]},
    "right": {"mode": "Galloping", "params": [0, 9, 7, 7, 10]}
  },
  "leds": {
    "lightbar": [255, 80, 0],
    "player_leds": [false, true, true, true, false]
  },
  "rumble": {"passthrough": true}
}
```

O `mode` de cada gatilho é validado na carga do perfil contra
`PRESET_FACTORIES` (`src/hefesto_dualsense4unix/core/trigger_effects.py`), a
fonte única dos nomes aceitos — 19 exatamente, listados na seção "Modos de
trigger" abaixo. Nome fora dessa lista faz `Profile.model_validate` levantar
`ValidationError` citando os válidos, e o perfil não carrega.

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

> **Desde 09/08/2026 a janela guarda o modo jogo — inclusive em perfil "Vale
> sempre".** O interruptor de modo jogo da aba Emulação escreve no rascunho, e o
> **Salvar Perfil** do rodapé o persiste neste campo. Até então a janela
> **recusava** o gesto em perfil catch-all; a recusa caiu por decisão dela — *"a
> vontade na GUI prevalece sempre"*. **O raciocínio que ela carregava não era
> capricho e fica registrado:** com `suppress: true` num perfil "vale sempre", a
> supressão entraria em toda ativação (o restauro do boot inclusive) e o caminho
> de volta estaria fechado — mouse e teclado suspensos no desktop sem ninguém
> pedir. **O que caducou foi a premissa, não o medo:** o gate que fecha esse
> alçapão existe no daemon desde 05/08. **O preço que sobra vai para a tela:**
> num catch-all o valor fica guardado no arquivo, mas o daemon **não o liga
> sozinho** na ativação seguinte — e é exatamente isso que impede o desktop de
> acordar sem ponteiro.

## Seção opcional `speaker` (alto-falante e fone do controle)

```json
{
  "speaker": {"volume": 180, "muted": false, "rota": 2}
}
```

Perfil **sem** a seção não tem opinião: ativá-lo não toca no volume e **não toma
a posse** dos bytes de áudio do report de saída.

- `volume` (0-255) é **obrigatório**, e a recusa é na borda do esquema, com a
  razão medida: uma chamada com `muted` e sem `volume` faz a preferência cair a
  zero, toma a posse e tranca o alto-falante — e nem o próprio mudo o solta.
  Quem quer "mudo" escreve o volume que quer de volta: `{"volume": 180,
  "muted": true}`.
- `rota` (0-3) é o canal de saída (`OUTPUT_PATH_SEL`): `0` estéreo → fone; `1`
  canal L → fone (mono); `2` L → fone e R → alto-falante interno (o caso
  Zelda / "Sons do jogo"); `3` canal R → alto-falante interno ("Todo o som do
  PC"). Ausente significa **não tocar no byte** — ele guarda também o caminho
  do microfone.

> **Nota datada — 09/08/2026: até esta data a janela não gravava nada disso.**
> A função que escreveria a seção tinha **zero chamadores desde 21/04**: você
> ajustava o volume, o mudo ou o canal, clicava em Salvar Perfil, e o arquivo
> guardava o valor **velho** — que voltava ao hardware na ativação seguinte. O
> gesto era desfeito pelo próprio gesto de salvar. Hoje os três chegam ao
> perfil.

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

> **NOTA DATADA — 09/08/2026: as três regiões de touchpad deste preset não
> disparam mais.** O `point_and_click.json` continua trazendo
> `touchpad_left_press`/`middle`/`right` (E / U / P) e o schema continua
> aceitando o campo — decisão medida não se apaga. O que caducou é o efeito: o
> touchpad do DualSense voltou a ser o touchpad do **sistema** em todos os
> modos (decisão dela, `TOUCHPAD-DO-SISTEMA-01`), e o daemon **cala** as
> regiões quando o ponteiro é do sistema — quem responde é o estado real do nó
> (`core/evdev_reader.py: ponteiro_do_sistema`), não o modo. A razão é que o
> clique do touchpad já é clique de mouse pelo libinput; somar a tecla faria um
> clique disparar duas coisas. As três regiões também saíram da aba
> **Navegação**, porque listar um botão que o produto não dispara mais é a
> janela mentindo. Para o Grim Fandango, use os outros botões — ou desfaça a
> devolução do touchpad ao sistema (a reversão está escrita no cabeçalho de
> `assets/76-dualsense-touchpad-libinput-ignore.rules`), lembrando que as duas
> coisas andam juntas.

Notas para o Grim Fandango Remastered:

- O port Linux é nativo e tem point-and-click por mouse oficial (código do mod
  Grim Mouse, 2015) — o modo mouse é o caminho preferido neste jogo.
- **Steam Input permanece OFF** para este título: a combinação é incompatível
  no Linux (bug conhecido desde 2019) e quebra o controle dentro do jogo.
- Rota alternativa de **gamepad nativo** (jogos de gamepad com SDL antigo): o
  `controllerdef.txt` embarcado não conhece o DualSense, mas conhece o X360 —
  ligue o gamepad virtual com máscara xbox360 (`hefesto-dualsense4unix gamepad
  on --flavor xbox` ou aba Emulação) e abra o jogo **depois** de o device virtual
  existir (SDL 2.0.3 só enumera na inicialização). Não é o caminho preferido
  para o Grim; fica registrado para títulos sem suporte a mouse.

Antes de confiar no match, confirme o `wm_class` real da janela com o jogo
aberto (ver seção abaixo) — ports via Proton/ScummVM usam classes diferentes.

## Semântica de match

- **AND entre campos preenchidos**: se `window_class` E `process_name` estão setados, ambos precisam bater.
- **OR dentro de cada lista**: `window_class: ["a", "b"]` casa qualquer um.
- **Regex**: `window_title_regex` usa `re.search` (padrões com `.*` são redundantes).
- **Basename**: `process_name` casa com o basename de `/proc/PID/exe`, não `comm` truncado.
- **Prioridade**: perfil com maior `priority` vence em empate. É o **segundo**
  critério, nunca o primeiro: um perfil com regra de janela sempre vence um
  perfil "Sempre" (catch-all), por mais alta que seja a prioridade deste.

### A armadilha do `process_name` em jogo da Steam (MEDIDO em 10/08/2026)

**O AND não estreita: ele anula.** Um perfil de jogo da Steam que traga
`window_class: ["steam_app_XXXXXXX"]` **e** `process_name: ["JOGO.exe"]` pode
nunca ativar — e o exemplo no topo desta página (`cyberpunk_driving`) é
exatamente esse formato.

O motivo é o Proton: o `process_name` casa com o basename de `/proc/PID/exe`, e
sob Proton esse binário **nunca** é o `.exe` do jogo — é o binário do wine. No
journal dela, com a janela do Pragmata em foco: `window_class` batia
(`steam_app_3357650`), `process_name` exigia `PRAGMATA.exe`, a máquina via
`wine64-preloader`, e o resultado foi
`profile_select_catch_all_sem_autoridade_em_jogo candidatos=['fallback']`. O
perfil do jogo **não era candidato ao próprio jogo**. Tirando só o
`process_name`, os candidatos viraram `['fallback', 'Pragmata']`.

O tamanho do problema, medido no journal de 30 dias dela: **todos** os perfis
que o autoswitch já elegeu sozinho são identificados por `window_class`, nenhum
com `process_name`. E os cinco que **só** têm `process_name` (Ação, Aventura,
Corrida, Esportes, FPS) nunca ativaram, nenhuma vez.

**A regra prática:** para jogo da Steam, use **só** a `window_class`
`steam_app_<appid>`. Se o perfil tiver `process_name` junto, tire-o pelo **Modo
avançado** da aba Perfis — a janela **não** o apaga sozinha, porque apagar em
silêncio o que você escreveu seria mudança que você não pediu.

**Como perceber isso sem ler journal:** a aba [**No jogo**](interface.md#no-jogo)
diz, com o jogo na frente, qual perfil daquele jogo não entrou e o que ele
exigiu, lado a lado com o que a máquina vê.

> Um efeito colateral do mesmo campo, corrigido em 10/08/2026: com
> `process_name` junto, o editor da aba Perfis não reconhecia mais o perfil como
> jogo da Steam — abria no **Modo avançado**, o seletor "Aplica a:" ia para
> "Vale sempre" e a caixinha do Steam Input sumia da tela. Hoje o
> reconhecimento aceita o `process_name` ao lado do appid, e o campo é
> preservado no round-trip do salvar. Regex de título junto continua indo para
> o editor avançado, que é o que aquela recusa protegia de verdade.

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

Os 19 nomes aceitos, como estão em `PRESET_FACTORIES`: `Off`, `Rigid`,
`SimpleRigid`, `Pulse`, `PulseA`, `PulseB`, `Resistance`, `Bow`, `Galloping`,
`SemiAutoGun`, `AutoGun`, `Machine`, `Feedback`, `Weapon`, `Vibration`,
`SlopeFeedback`, `MultiPositionFeedback`, `MultiPositionVibration`, `Custom`.

Cuidado com o vocabulário do DSX: `Medium`, `Soft`, `Hard`, `VeryHard`,
`Hardest`, `Choppy`, `GameCube` e afins são nomes do enum `TriggerMode` do DSX,
**não** presets do Hefesto — nenhum deles existe em `PRESET_FACTORIES` e um
perfil que os use não carrega. O motivo de não estarem traduzidos (curvas de
força fechadas, sem parâmetro, cuja única transcrição pública está num
repositório sem licença) está em `docs/protocol/udp-schema.md`.

## Modo Nativo — jogar com os gatilhos nativos da Sony (Sackboy & cia)

Para jogos que dirigem os gatilhos adaptativos por conta própria (ex.: Sackboy:
Uma Grande Aventura), o hefesto pode SOLTAR o controle por completo:

```
hefesto-dualsense4unix native on      # solta o controle pro jogo
hefesto-dualsense4unix native off     # o hefesto reassume o teu perfil
hefesto-dualsense4unix native status
```

Com o Modo Nativo ligado: gatilhos neutros (o jogo impõe os dele), rumble do
jogo (o hefesto não re-asserta), emulação de mouse/gamepad desligada (libera o
grab), autoswitch/hotkey de perfil travados, e o dispatch de input congelado. O
estado da tua emulação (gamepad/mouse) é guardado e RESTAURADO ao desligar. O
modo sobrevive a reboot (o controle segue solto até você fazer `native off`).

## Anti-storm (dsx) via `doctor`

O diagnóstico do storm -71 e os fixes seguros também vivem no CLI:

```
hefesto-dualsense4unix doctor              # inclui o bloco "anti-storm / sistema"
hefesto-dualsense4unix doctor --fix-safe   # SEM sudo: Steam Input OFF + WirePlumber
hefesto-dualsense4unix doctor --fix        # aplica os fixes do doctor.sh
hefesto-dualsense4unix doctor --quiet      # só o resumo
```

> **`--reapply-all` não existe mais.** Ele invocava um `scripts/dsx.sh` que <!-- ref-externa: a ausência deste script é o assunto do aviso -->
> também não existe mais no repositório. A cura do storm `-71` migrou para o
> quirk do `snd_usb_audio` — instalado por padrão e reaplicável por `--fix-safe`.
> Se você tem esse comando na memória muscular, o substituto é `--fix-safe`.
