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

### `uniq` — o alvo por controle (PERFIL-05 / R-17 / ABAS-06)

Os comandos de SAÍDA aceitam um `uniq` opcional (o MAC normalizado, 12 hex) e,
com ele, escrevem SÓ naquele controle, registrando o override por-MAC —
`trigger.set`, `trigger.reset`, `led.set` e `led.player_set`. Omitido, vale o
comportamento global clássico ("Todos"). É o eixo que a persistência já usava:
sem ele, o pedido cai em broadcast e "configurei o Controle 2 e mudou todos".

`mic.set` e `speaker.set` também aceitam `uniq`, com uma diferença que vale
registrar: neles, omitir NÃO é broadcast — é o controle **primário**. O áudio
mora num handle só (`_handle_for`), não numa lista, então nunca houve o risco de
"mexi num e mudou todos" que os outros quatro tinham.

`trigger.reset` foi o último a ganhar o parâmetro (ABAS-06, 25/07) — o botão
"Desligar" da aba Gatilhos zerava o gatilho dos quatro enquanto o "Aplicar" ao
lado mandava para um só. Ele também é o único que LIBERA a trava manual de 30 s,
e libera apenas a categoria `trigger` (ABAS-05): desligar um gatilho não pode
destravar o LED nem a vibração que ela ajustou em outra aba.

### `mic.set` / `speaker.set` — o áudio do controle (D4 / MIC-USB-01)

| Método        | Parâmetros                                      | Retorno                                        |
|---------------|-------------------------------------------------|------------------------------------------------|
| `mic.set`     | `{muted: bool\|null, uniq?: str}`               | `{status, audio, mic_mudo_desejado}`           |
| `speaker.set` | `{volume?: 0-255, muted?: bool, uniq?: str}`    | `{status, speaker}`                            |

Os dois escrevem no MESMO bloco de posse do report de saída (`common[4..9]`,
AUDIO-OWNER-01) e seguem a mesma disciplina: o hefesto só toca o campo depois de
alguém pedir, e o que não tem dono sai com o bit de validação apagado — o
firmware conserva o que tinha.

**`mic.set` tem TRÊS estados, e `false` não é "não mexer":**

- `muted: true` — muta no firmware;
- `muted: false` — **desmuta**. É uma ordem: enquanto vigorar, nós somos os
  donos do registrador e o botão físico do controle não manda mais;
- `muted: null` — **devolve a posse** ao `hid-playstation`, que volta a alternar
  o mudo na borda do botão físico. É o default de fábrica.

A chave `muted` é **obrigatória** (omiti-la é erro `-32003`, não um `false`
silencioso). Confundir `false` com `null` foi o defeito dos dois escritores do
byte de mute (`3d9bb7e`): o keepalive do upstream mandava `common[9]=0x00` a
60 Hz por cima do kernel, e o botão de microfone do controle parecia não
funcionar.

`status` é `"ok"` quando algum controle recebeu o pedido e `"sem_controle"`
quando não havia handle para o `uniq` (ou nenhum controle conectado). O campo
`audio` da resposta é a **leitura** do byte de estado do report de INPUT e pode
vir um report atrás da escrita — não é o eco do que foi mandado.

**Estado em `daemon.state_full`**, por controle, dentro de `audio`:

- `mic_mudo` — o que o firmware **declara** agora (leitura de verdade);
- `mic_mudo_desejado` — **quem manda**: `true`/`false` = o hefesto está
  afirmando esse valor em todo report; `null` = a posse é do kernel. A chave só
  aparece quando o backend sabe respondê-la. Sem ela a tela não tem como
  escolher entre "aperte o botão do controle" e "desmute pela janela" — as duas
  frases descrevem `mic_mudo: true`, e só uma resolve.

`speaker` só entra no payload **depois** de um `speaker.set`: o DualSense não
devolve o volume (não há report de input nem feature report que o leia), então
antes disso qualquer número seria chute.

**O que o IPC NÃO alcança.** O mudo do firmware é só a **camada 3** das três que
deixavam o microfone mudo em 25/07. As outras duas são do WirePlumber e se curam
por fora — `scripts/doctor.sh --fix-mic`:

1. `"mute":true` persistido por **rota** em
   `~/.local/state/wireplumber/default-routes`, restaurado a cada conexão sem
   nada no log;
2. perfil da placa preso em `input:iec958-stereo` (S/PDIF, **sem sinal**) porque
   o WirePlumber marca a entrada analógica indisponível sem fone plugado — mas o
   microfone embutido usa esse mesmo caminho.

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
