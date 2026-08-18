# Protocolo IPC — Unix Socket JSON-RPC 2.0

## Endpoint

`$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock` (Unix
socket, stream). Permissão `0600` (só o dono). Repare no **diretório próprio**:
o socket não fica solto na raiz do `XDG_RUNTIME_DIR`, e sim numa pasta com o
nome do projeto, ao lado de `daemon.pid` e `gui.pid`.

O caminho é montado por `utils/xdg_paths.py` (`ipc_socket_path`), fonte única —
nada no código escreve esse caminho à mão:

- **Diretório**: `runtime_dir()` = `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`.
  Sem `XDG_RUNTIME_DIR` no ambiente, cai em `<cache>/runtime/`.
- **Nome-base**: `ipc_socket_name()`, nesta ordem de precedência —
  1. `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME`, se explícita e sem `/`;
  2. modo fake (`HEFESTO_DUALSENSE4UNIX_FAKE=1`) sem override →
     `hefesto-dualsense4unix-fake.sock`, isolado do daemon real;
  3. produção → `hefesto-dualsense4unix.sock`.

O passo 2 é o que impede um daemon fake de sequestrar o socket de produção
(BUG-FAKE-SOCKET-SYNC-01): quem for falar com o daemon deve **derivar** o
caminho dessas funções, não concatenar a string.

## Formato de fio

NDJSON UTF-8 (V2-3): uma requisição ou resposta por linha, terminada por `\n`. JSON escapa `\n` interno das strings como `\\n`, então não há ambiguidade.

## Todos os métodos — esta lista é GERADA do dispatcher

Não a edite: ela sai do dicionário `_handlers` de `daemon/ipc_server.py` por
`scripts/gerar-contrato-ipc.py`, e o `--check` dele reprova quando o publicado
deixa de ser o que o código produz. A razão de ser gerada está escrita no
cabeçalho do gerador e é curta: a contagem de métodos sem contrato já saiu 15,
17, 18 e 14 no mesmo dia, sem commit no meio. Número que quatro réguas não
reproduzem não se escreve à mão.

A coluna **Contrato em prosa** diz se o método aparece em alguma outra parte
deste documento. `**não**` é dívida, e a lista abaixo é o único lugar onde ela
aparece contada.

<!-- BLOCO GERADO por scripts/gerar-contrato-ipc.py — não edite à mão -->

**37 métodos** estão registrados no dicionário `_handlers` de `daemon/ipc_server.py`. Destes, **18** ainda não são citados em nenhuma outra parte deste documento, e **4** têm handler sem docstring.

Esta tabela é **gerada**. O número acima nunca foi digitado por ninguém — e é por isso que ele está aqui: escrito à mão, ele já saiu 15, 17, 18 e 14 em levantamentos do mesmo dia.

| Método | Handler | O que o handler diz de si | Contrato em prosa |
|---|---|---|---|
| `profile.switch` | `daemon/ipc_handlers.py:695` (`_handle_profile_switch`) | Aplica perfil escolhido pelo usuário (entrada manual via IPC). | sim |
| `profile.list` | `daemon/ipc_handlers.py:815` (`_handle_profile_list`) | _(o handler não tem docstring)_ | sim |
| `profile.apply_draft` | `daemon/ipc_handlers.py:832` (`_handle_profile_apply_draft`) | Aplica draft completo em ordem canonica: leds -> triggers -> rumble -> mouse. | **não** |
| `trigger.set` | `daemon/ipc_handlers.py:1085` (`_handle_trigger_set`) | _(o handler não tem docstring)_ | sim |
| `trigger.reset` | `daemon/ipc_handlers.py:1134` (`_handle_trigger_reset`) | Devolve o gatilho ao perfil e LIBERA a trava manual dele (R-19). | sim |
| `led.set` | `daemon/ipc_handlers.py:1187` (`_handle_led_set`) | _(o handler não tem docstring)_ | sim |
| `rumble.set` | `daemon/ipc_handlers.py:3590` (`_handle_rumble_set`) | Aplica rumble com política de intensidade (FEAT-RUMBLE-POLICY-01). | **não** |
| `rumble.stop` | `daemon/ipc_handlers.py:3623` (`_handle_rumble_stop`) | Para rumble e persiste estado (0, 0) (BUG-RUMBLE-APPLY-IGNORED-01). | **não** |
| `rumble.passthrough` | `daemon/ipc_handlers.py:3678` (`_handle_rumble_passthrough`) | Libera controle de rumble para jogo/UDP (BUG-RUMBLE-APPLY-IGNORED-01). | **não** |
| `rumble.policy_set` | `daemon/ipc_handlers.py:3719` (`_handle_rumble_policy_set`) | Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01). | **não** |
| `rumble.policy_custom` | `daemon/ipc_handlers.py:3742` (`_handle_rumble_policy_custom`) | Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01). | **não** |
| `daemon.status` | `daemon/ipc_handlers.py:1830` (`_handle_daemon_status`) | _(o handler não tem docstring)_ | sim |
| `daemon.state_full` | `daemon/ipc_handlers.py:2098` (`_handle_daemon_state_full`) | Estado completo pra GUI consumir a 20Hz. | sim |
| `daemon.pause` | `daemon/ipc_handlers.py:2049` (`_handle_daemon_pause`) | Pausa o despacho de input sem matar o daemon (FEAT-DAEMON-PAUSE-RESUME-01). | **não** |
| `daemon.resume` | `daemon/ipc_handlers.py:2054` (`_handle_daemon_resume`) | Retoma o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01). | **não** |
| `autoswitch.lock` | `daemon/ipc_handlers.py:2059` (`_handle_autoswitch_lock`) | Congela/descongela a troca AUTOMÁTICA de perfil (FEAT-AUTOSWITCH-LOCK-01). | **não** |
| `native.mode.set` | `daemon/ipc_handlers.py:2079` (`_handle_native_mode_set`) | Liga/desliga o Modo Nativo — "release total" do controle (FEAT-NATIVE-MODE-01). | sim |
| `controller.list` | `daemon/ipc_handlers.py:3449` (`_handle_controller_list`) | Lista os controles do daemon; opt-in `external` soma o inventário 8BIT-01. | sim |
| `controller.target.set` | `daemon/ipc_handlers.py:3511` (`_handle_controller_target_set`) | Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01). | **não** |
| `daemon.reload` | `daemon/ipc_handlers.py:3790` (`_handle_daemon_reload`) | Aplica overrides parciais de config em runtime (REFACTOR-DAEMON-RELOAD-01). | sim |
| `launch_env.refresh` | `daemon/ipc_handlers.py:3834` (`_handle_launch_env_refresh`) | Rematerializa as envs de launch do wrapper (DEDUP-04) sob demanda. | **não** |
| `lightbar.reset` | `daemon/ipc_handlers.py:3541` (`_handle_lightbar_reset`) | Manda o Reset LED state (0x08) sob demanda — INSTRUMENTO de medição. | **não** |
| `debug.player_leds` | `daemon/ipc_handlers.py:3569` (`_handle_debug_player_leds`) | Liga/desliga a escrita do LED de JOGADOR — INSTRUMENTO de eliminação. | **não** |
| `speaker.set` | `daemon/ipc_handlers.py:3856` (`_handle_speaker_set`) | `speaker.set` — volume/mudo/devolução do alto-falante (D4 + SOM-02). | sim |
| `mic.set` | `daemon/ipc_handlers.py:4022` (`_handle_mic_set`) | `mic.set` — mudo do microfone no FIRMWARE do controle (MIC-USB-01). | sim |
| `mouse.emulation.set` | `daemon/ipc_handlers.py:4095` (`_handle_mouse_emulation_set`) | Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01). | sim |
| `mouse.emulation.restore` | `daemon/ipc_handlers.py:4139` (`_handle_mouse_emulation_restore`) | Restaura a emulação de mouse conforme a preferência persistida (HARM-06). | **não** |
| `keyboard.emulation.set` | `daemon/ipc_handlers.py:4160` (`_handle_keyboard_emulation_set`) | Liga/desliga a emulação de TECLADO (EMULACAO-NO-JOGO-01). | **não** |
| `gamepad.emulation.set` | `daemon/ipc_handlers.py:4196` (`_handle_gamepad_emulation_set`) | Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01). | **não** |
| `coop.set` | `daemon/ipc_handlers.py:4272` (`_handle_coop_set`) | Liga o co-op local; RECUSA desligar (FEAT-DSX-COOP-LOCAL-01). | sim |
| `coop.sync` | `daemon/ipc_handlers.py:4326` (`_handle_coop_sync`) | Roda UM ciclo cheio de reconciliação do co-op (`sync(force=True)`). | sim |
| `daemon.emulation.suppress` | `daemon/ipc_handlers.py:4363` (`_handle_emulation_suppress`) | Liga/desliga o modo jogo (suprime emulação mouse/teclado). | sim |
| `led.player_set` | `daemon/ipc_handlers.py:1261` (`_handle_led_player_set`) | Aplica bitmask de 5 LEDs de player no controle. | sim |
| `identity.renumber` | `daemon/ipc_handlers.py:1315` (`_handle_identity_renumber`) | Reordena a FILA de preferência (DualSense + externos) — ONDA-U/NUM-01. | sim |
| `identity.number.set` | `daemon/ipc_handlers.py:1468` (`_handle_identity_number_set`) | Atribui o NÚMERO EXIBIDO de UM controle (PLAYER-01, 25/07). | sim |
| `plugin.list` | `daemon/ipc_handlers.py:4380` (`_handle_plugin_list`) | Lista plugins carregados no daemon (FEAT-PLUGIN-01). | **não** |
| `plugin.reload` | `daemon/ipc_handlers.py:4392` (`_handle_plugin_reload`) | Recarrega plugins do disco (FEAT-PLUGIN-01). | **não** |

<!-- FIM DO BLOCO GERADO -->

## Métodos v1 — os parâmetros e o retorno

Escrita à mão, e continua sendo: parâmetro e retorno não se derivam do
dispatcher. Ela cobre o subconjunto v1 — a lista COMPLETA é a de cima.

| Método              | Parâmetros                                    | Retorno                                |
|---------------------|-----------------------------------------------|----------------------------------------|
| `profile.switch`    | `{name: str}`                                 | `{status: "ok", active_profile: str}`  |
| `profile.list`      | `{}`                                          | `{profiles: [{name, priority, match}]}` |
| `trigger.set`       | `{side, mode, params: [int]}`                 | `{status, aplicado_em, guardado_em}`   |
| `trigger.reset`     | `{side?: "left"\|"right"\|"both"}`            | `{status, aplicado_em, guardado_em}`   |
| `led.set`           | `{rgb: [r,g,b], player_leds?: [bool]*5}`      | `{status, aplicado_em, guardado_em}`   |
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

### `aplicado_em` e `guardado_em` — o que a resposta AFIRMA (MESA-CHEIA-09)

Os quatro comandos de saída por-MAC (`trigger.set`, `trigger.reset`, `led.set`,
`led.player_set`) devolvem **duas listas de MAC**, e a diferença entre elas é a
diferença que a janela precisava para parar de mentir:

| campo | quer dizer | a tela diz |
|---|---|---|
| `aplicado_em` | **o byte saiu** para aquele controle | *aplicado* |
| `guardado_em` | o override ficou REGISTRADO e vale DEPOIS: quando o controle voltar (hotplug) **ou** quando o Modo Nativo sair (desmute) | *guardado* (D-9) |
| as duas VAZIAS | escrita global sem registro por controle (pedido sem `uniq`, backend sem a API por-MAC); **ou** a escrita levantou (`falhou`) | o texto histórico |

**O que mudou em 14/08:** no ramo por-`uniq`, `aplicado_em` era `[uniq]`
SEMPRE — inclusive com o controle desconectado, em que nenhum byte sai e o
override só fica guardado (`core/backend_pydualsense.apply_output_for`). O
campo criado para o daemon parar de mentir mentia nesse caso, e a tela repetia
a afirmação. Agora `aplicado_em` significa a mesma coisa nos dois ramos — o do
broadcast já listava só quem está conectado.

**Por que duas listas e não uma:** "não escreveu" tem duas causas com destinos
opostos na tela — o que ficou guardado e vai valer, e o que não guardou nada
(sem MAC estável). Uma lista só obrigaria a chamar uma das duas pelo nome da
outra.

**O conserto de 14/08 (à tarde):** a primeira leva matou DUAS das três
condições da tabela de mentiras da sprint e deixou a terceira — **Modo Nativo
com o output mutado** — respondendo `aplicado_em`. Mutado, a rota sysfs do LED
está desabilitada, o report `0x31` avulso é pulado e o `report_thread` não
escreve nada: nenhum byte sai, e o desejado é re-escrito no desmute. Isso é
`guardado_em`, pela mesma definição do controle fora da mesa — o que muda é o
evento que o libera. Na mesma leva, a escrita que LEVANTA (o `hidraw` que some
debaixo dela) deixou de contar como aplicada: o backend devolve `falhou` e as
duas listas saem vazias, porque prometer "guardado" ali seria mandá-la esperar
um evento que pode nunca vir.

### `mic.set` / `speaker.set` — o áudio do controle (D4 / MIC-USB-01)

| Método        | Parâmetros                                                       | Retorno                                        |
|---------------|------------------------------------------------------------------|------------------------------------------------|
| `mic.set`     | `{muted: bool\|null, uniq?: str}`                                | `{status, audio, mic_mudo_desejado}`           |
| `speaker.set` | `{volume?: 0-255, muted?: bool, release?: bool, uniq?: str}`     | `{status, speaker}`                            |

Os dois escrevem no MESMO bloco do report de saída (`common[4..9]`,
AUDIO-OWNER-01) e seguem a mesma disciplina: o hefesto só toca o campo depois de
alguém pedir, e o que não tem dono sai com o bit de validação apagado — o
firmware conserva o que tinha.

**A posse, porém, é por BYTE e por BIT — não é do bloco inteiro** (medido na
SOM-02, 29/07). Este documento tratava `common[4..9]` como uma coisa só, e para
efeito de disciplina isso está certo; para efeito de PREÇO, não:

| Campo                    | Byte        | Bit de autoridade | Quem toma     |
|--------------------------|-------------|-------------------|---------------|
| volume do fone           | `common[4]` | `flag0 0x10`      | `speaker.set` |
| volume do alto-falante   | `common[5]` | `flag0 0x20`      | `speaker.set` |
| volume do microfone      | `common[6]` | `flag0 0x40`      | ninguém hoje  |
| roteamento de áudio      | `common[7]` | `flag0 0x80`      | ninguém hoje  |
| mudo do microfone        | `common[9]` | `flag1 0x02`      | `mic.set`     |

Fontes: `core/ds_output_report.py:74-101`, a aplicação por byte em
`core/backend_pydualsense.py` (`_build_common`) e o mudo do microfone em ramo
separado, logo abaixo dela.

**A consequência prática, que a tela precisa dizer do jeito certo: mexer no
volume pela janela NÃO mata o botão de microfone do controle.** São bits
diferentes. O que a MIC-USB-01 viveu — `mic unmute` toma a posse e o botão
físico para de valer até `mic release` — vale para o MICROFONE. O alto-falante
tem um preço próprio, menor e diferente: ele toma o volume do fone junto (é o
mesmo valor nos dois bytes, de propósito), e não toca `common[6]` nem
`common[7]` — o roteamento fica de fora porque não sabemos o valor neutro dele e
chutar mudaria o caminho do áudio.

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

**`speaker.set` tem uma quarta chave, `release` (SOM-02, 31/07):**

- `release: true` — **devolve a posse** dos bytes de volume. Os bits de áudio do
  `flag0` voltam a sair zerados, o firmware volta a mandar no bloco e a chave
  `speaker` **some** do `daemon.state_full` no tique seguinte;
- `release` **não se combina** com `volume`/`muted`: a mistura é erro `-32003`.
  "Pare de mandar E mande isto" não tem significado honesto, e eleger um vencedor
  em silêncio esconderia um chamador confuso — são dois pedidos;
- por que uma chave nova, e não `muted: null` como no `mic.set`: aqui `muted` é
  **opcional** e a ausência já quer dizer "não mexer"; lá a chave é obrigatória e
  a ausência é erro. Reusar o `null` daria duas leituras para o mesmo payload.

**O que a devolução faz, e o que ela não faz.** Ela devolve o CONTROLE, não o
valor: como não existe leitura desse registrador, ninguém pode saber qual era o
volume antes de nós, e o firmware fica com o ÚLTIMO número que mandamos até o
controle desconectar. Nenhum texto do produto pode prometer restauração.

`muted` **sem volume conhecido é recusado** (erro `-32003`), e isso é entrega, e
não rigor: medido na SOM-02, mudo como PRIMEIRA escrita manda zero e guarda zero
como preferência — o "desmudo" seguinte restaura zero e o próprio par
mudo/desmudo não solta mais o alto-falante. Mande um `volume` antes. Pela mesma
razão, nada no produto manda `speaker.set` **vazio**: a chamada sem `volume`
toma a posse e manda ZERO.

`speaker.set` arma a trava manual na categoria `audio` (a quarta, ao lado de
`trigger`/`led`/`rumble`): volume é ajuste manual como qualquer outro, e o
autoswitch não pode pisá-lo reaplicando o perfil na próxima troca de janela.
`profile.switch` explícito continua limpando tudo.

Fora da janela, a linha de comando cobre o mesmo caminho:
`hefesto-dualsense4unix speaker status|volume <0-100>|mute|unmute|release`
(`--uniq` escolhe o controle). O `release` é a saída de emergência sem GUI, o
irmão do `mic release`; o `mute` do CLI traz a mesma guarda da janela e recusa
quando não há volume conhecido.

**O que o IPC NÃO alcança.** O mudo do firmware é só a **camada 3** das três que
deixavam o microfone mudo em 25/07. As outras duas são do WirePlumber e se curam
por fora — `scripts/doctor.sh --fix-mic`:

1. `"mute":true` persistido por **rota** em
   `~/.local/state/wireplumber/default-routes`, restaurado a cada conexão sem
   nada no log;
2. perfil da placa preso em `input:iec958-stereo` (S/PDIF, **sem sinal**) porque
   o WirePlumber marca a entrada analógica indisponível sem fone plugado — mas o
   microfone embutido usa esse mesmo caminho.

### `identity.renumber` / `identity.number.set` — o número do controle

| Método                | Parâmetros              | Retorno                                                   |
|-----------------------|-------------------------|-----------------------------------------------------------|
| `identity.renumber`   | `{}`                    | `{ok: true, renumbered: {addr: lugar}}` \| `{ok: false, reason}` |
| `identity.number.set` | `{uniq: str, number: int}` | `{ok: true, number, changed: {addr: lugar}}` \| `{ok: false, reason}` |

Os dois escrevem o MESMO estado — a **fila de preferência** do
`controllers.json` (schema 3, campo `order`), compartilhada entre DualSense e
externos. Desde a NUM-01 o que se grava é o **lugar na fila**, nunca um número
absoluto: o número que a janela mostra é a *colocação desse lugar entre quem está
presente agora*. É por isso que um controle sozinho na mesa é sempre o 1.

- `identity.renumber` **compacta todo mundo** para 1..N preservando a ordem
  relativa, e empurra quem está ausente para o fim da fila. É o acabamento do
  botão **"Reconciliar jogadores"** da aba Início — um gesto de faxina.
  (Até 06/08/2026 o botão se chamava *"Renumerar agora"* e disparava só este
  método; ver `coop.sync`, abaixo.)
- `identity.number.set` (PLAYER-01, 25/07) atribui o número de **UM** controle:
  permuta entre si os lugares que os PRESENTES já ocupam, pondo o alvo na
  posição pedida. Os lugares de quem está ausente ficam intocados — este gesto
  não rebaixa ninguém que está na gaveta.

Ele é `number` e não `player` de propósito: "jogador" nomeia outra PERGUNTA
neste projeto — "este controle está jogando agora?" —, respondida pelo campo
`controllers[].player` do `state_full`, que é `null` fora do co-op.

O que mudou em **15/08/2026 (MESA-CHEIA-12)**: os dois deixaram de ser espaços
de numeração diferentes. Até ali o `player` saía do índice de alocação do vpad
do co-op (`_next_player_index`, ordem em que o grab confirmou na sessão) e a
barra de LED do controle saía desta fila — e, com os quatro DualSense dela no
rádio, três dos quatro acendiam um número e eram chamados de outro. Agora
`CoopManager.numeros_de_jogador()` é a fonte única dos dois: quando `player`
existe, ele é igual ao `player_slot`. A ordem de chegada é a verdade, e a barra
é função dela.

**Recusas** (nenhuma escreve nada):

| `reason`                | quando                                                      |
|-------------------------|-------------------------------------------------------------|
| `sessao_de_jogo_aberta` | `display_authority == "game"` — repintar o LED do controle que o jogo está usando no meio da partida é o erro que o NUMA-03 fechou |
| `controle_ausente`      | o `uniq` não está entre os presentes; número exibido só existe para quem está na mesa |
| `numero_fora_da_mesa`   | `number` maior que a quantidade de presentes (a resposta traz `max`) |
| `lock_timeout`          | os `RLock` dos registros não vieram em 5 s (mesmo teto do renumber) |

`changed` traz apenas os endereços cujo lugar MUDOU — a mesma disciplina do R-15
no renumber, para a interface não anunciar sucesso de um no-op.

### `coop.set` / `coop.sync` — o co-op local

| Método      | Parâmetros        | Retorno                                          |
|-------------|-------------------|--------------------------------------------------|
| `coop.set`  | `{enabled: bool}` | `{status: "ok", enabled: true, players}` \| `{status: "recusado", enabled: true, players, motivo}` |
| `coop.sync` | `{}`              | `{status: "ok", players, active}`                 |

**COOP-SEM-INTERRUPTOR-01 (06/08/2026, decisão da mantenedora):** o co-op local
não é mais uma opção — cada controle conectado é um jogador, sempre. Palavra
dela: *"se eu conecto 4 controles no PC eu espero, com 4 pessoas jogando, que
cada um controle o próprio personagem"*.

- `coop.set {enabled: true}` continua ligando/reconciliando e **persiste** o
  gesto manual (é gesto DELA: toma a posse do eixo `mode`).
- `coop.set {enabled: false}` é **recusado em voz alta** — `status: "recusado"`,
  com `motivo` legível. A FORMA do retorno é preservada de propósito
  (`players` continua lá): quem lê o contrato não quebra, e quem esperava o
  desligamento não é enganado por um `"ok"`.
- `coop.sync {}` roda **um ciclo cheio** de reconciliação
  (`CoopManager.sync(force=True)`): recria o jogador cujo grab foi recusado ou
  cujo vpad morreu, sem esperar o próximo hotplug. Não liga nem desliga nada,
  não persiste preferência e não toma a posse do eixo `mode`. É o botão
  **"Reconciliar jogadores"** da aba Início, e é o gesto de recuperação do
  jogador que nasce e morre em dois segundos.

`active` no retorno de `coop.sync` é o `should_be_active()` do gate — `false`
quando não há gamepad virtual de pé (modo desktop/nativo) ou quando a exceção
de Steam Input suspendeu os vpads. Nesse estado o ciclo apenas desmonta o que
sobrou: reconciliar **nunca** ressuscita o que o jogo suspendeu (a suspensão é
`CoopManager.disable()`, que não depende da flag).

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
