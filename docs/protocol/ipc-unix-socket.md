# Protocolo IPC — Unix Socket JSON-RPC 2.0

## Endpoint

`$XDG_RUNTIME_DIR/hefesto-dualsense4unix.sock` (Unix socket, stream). Permissão `0600` (só o dono).

## Formato de fio

NDJSON UTF-8 (V2-3): uma requisição ou resposta por linha, terminada por `\n`. JSON escapa `\n` interno das strings como `\\n`, então não há ambiguidade.

## Métodos v1

| Método              | Parâmetros                                    | Retorno                                |
|---------------------|-----------------------------------------------|----------------------------------------|
| `profile.switch`    | `{name: str}`                                 | `{status: "ok", active_profile: str}`  |
| `profile.list`      | `{}`                                          | `{profiles: [{name, priority, match}]}` |
| `trigger.set`       | `{side, mode, params: [int]}`                 | `{status}`                             |
| `trigger.reset`     | `{side?: "left"\|"right"\|"both"}`            | `{status}`                             |
| `led.set`           | `{rgb: [r,g,b], player_leds?: [bool]*5}`      | `{status}`                             |
| `daemon.status`     | `{}`                                          | `{connected, battery_pct, transport, active_profile}` |
| `controller.list`   | `{}`                                          | `{controllers: [{vid, pid, transport}]}` |
| `daemon.reload`     | `{}`                                          | `{status}`                             |
| `mouse.emulation.set` | `{enabled?: bool, speed?: 1-12, scroll_speed?: 1-5}` | `{status, enabled}`             |
| `native.mode.set`   | `{enabled?: bool}` (ausente = toggle)         | `{status, native_mode}`                |

### `native.mode.set` — Modo Nativo (FEAT-NATIVE-MODE-01)

"Release total" do controle: solta o DualSense para o jogo usar os gatilhos
adaptativos NATIVOS da Sony (Sackboy & cia). `enabled=true` → gatilhos Off/Off,
rumble passthrough, emulação (mouse/gamepad) desligada, autoswitch/hotkey
gateados e daemon pausado; persiste em `native_mode.flag` (sobrevive a restart).
`enabled=false` → restaura o último perfil. `daemon.state_full` e `daemon.status`
expõem `native_mode: bool`.

### `mouse.emulation.set` — `enabled` é OPCIONAL (BUG-MOUSE-GUI-SYNC-01 A4)

- **com `enabled`** (bool): liga/desliga a emulação de mouse (cria/destrói o
  device virtual, persiste o flag). Ligar desliga o gamepad virtual (mútua
  exclusão).
- **sem `enabled`** (rota *speed-only*, usada pelos sliders da GUI): atualiza
  apenas `speed`/`scroll_speed` da emulação — **nunca** liga/desliga nem cria o
  device, e só re-persiste o flag se a emulação já estava ligada. Impede que
  arrastar um slider religue uma emulação desligada.

## Perfil com seção `mouse` (FEAT-POINT-AND-CLICK-01)

O schema de perfil aceita uma seção opcional `mouse`
(`{"enabled": bool, "speed": 1-12, "scroll_speed": 1-5}`) e o campo booleano
`suppress_desktop_emulation`. Nas rotas de ativação em runtime (`profile.switch`,
autoswitch por janela, hotkey PS+D-pad):

- perfil **com** seção `mouse` → a emulação de mouse é ligada/desligada com as
  velocidades do perfil (mesmo efeito de `mouse.emulation.set` com `enabled`),
  respeitando o **lock manual** (BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01): se a
  usuária mexeu na emulação (mouse OU gamepad) manualmente há menos de 30 s, o
  perfil NÃO toca no estado — não sequestra um gamepad virtual ligado na mão. É
  idempotente (não recria o device a cada tick do autoswitch);
- perfil **sem** seção `mouse` → o estado da emulação NÃO é tocado;
- **restore no boot** (BUG-BOOT-RESTORE-FLIPS-EMULATION-01): a seção `mouse` do
  último perfil NÃO é reaplicada — o estado da emulação no boot vem dos **flags
  persistidos** (`mouse_emulation.flag`/`gamepad_emulation.flag`), não do perfil.
  Reaplicar matava o gamepad recém-restaurado e invertia a escolha da usuária a
  cada boot. O perfil ainda restaura triggers/LEDs/teclado;
- `suppress_desktop_emulation: true` → modo-jogo ligado (equivale a
  `daemon.emulation.suppress`); trocar para um perfil sem o campo libera a
  supressão **somente se ela veio de perfil** — um toggle manual da usuária
  (hotkey/GUI/CLI) nunca é revertido por perfil, e qualquer toggle manual há
  menos de 30 s congela a supressão (mesma janela do lock de perfil manual).

## Erros

Código padrão JSON-RPC 2.0. Convenções do Hefesto - Dualsense4Unix:

- `-32001`: daemon não conectado ao controle.
- `-32002`: perfil não encontrado.
- `-32003`: parâmetros inválidos (ex: `params` fora do range do mode).
- `-32004`: controle desconectou durante execução.
