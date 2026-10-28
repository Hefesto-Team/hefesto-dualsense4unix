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

O passo 2 é o que impede um daemon fake de sequestrar o socket de produção:
quem for falar com o daemon deve **derivar** o
caminho dessas funções, não concatenar a string.

## Formato de fio

NDJSON UTF-8 (V2-3): uma requisição ou resposta por linha, terminada por `\n`. JSON escapa `\n` interno das strings como `\\n`, então não há ambiguidade.

## Todos os métodos — esta lista é GERADA do dispatcher

Não a edite: ela sai do dicionário `_handlers` de `daemon/ipc_server.py` por
`scripts/gerar-contrato-ipc.py`, e o `--check` dele reprova quando o publicado
deixa de ser o que o código produz. A razão de ser gerada está escrita no
cabeçalho do gerador e é curta: a contagem de métodos sem contrato já saiu 15,
17, 18 e 14 no mesmo dia, sem commit no meio. Número que quatro verificações não
reproduzem não se escreve à mão.

A coluna **Contrato em prosa** diz se o método aparece em alguma outra parte
deste documento. `**não**` é dívida, e a lista abaixo é o único lugar onde ela
aparece contada.

<!-- BLOCO GERADO por scripts/gerar-contrato-ipc.py — não edite à mão -->

**69 métodos** estão registrados no dicionário `_handlers` de `daemon/ipc_server.py`. Destes, **28** ainda não são citados em nenhuma outra parte deste documento, e **4** têm handler sem docstring.

Esta tabela é **gerada**. O número acima nunca foi digitado por ninguém — e é por isso que ele está aqui: escrito à mão, ele já saiu 15, 17, 18 e 14 em levantamentos do mesmo dia.

| Método | Handler | O que o handler diz de si | Contrato em prosa |
|---|---|---|---|
| `profile.switch` | `daemon/ipc_handlers.py:530` (`_handle_profile_switch`) | Aplica perfil escolhido pelo usuário (entrada manual via IPC). | sim |
| `profile.list` | `daemon/ipc_handlers.py:579` (`_handle_profile_list`) | _(o handler não tem docstring)_ | sim |
| `profile.reaplicar` | `daemon/ipc_handlers.py:594` (`_handle_profile_reaplicar`) | O «Aplicar»: o perfil inteiro de novo aos controles, sem virar escolha | **não** |
| `trigger.set` | `daemon/ipc_handlers.py:796` (`_handle_trigger_set`) | _(o handler não tem docstring)_ | sim |
| `trigger.reset` | `daemon/ipc_handlers.py:831` (`_handle_trigger_reset`) | Grava ``Off`` no gatilho: sem efeito do Hefesto, e o jogo decide (R-19). | sim |
| `led.set` | `daemon/ipc_handlers.py:897` (`_handle_led_set`) | _(o handler não tem docstring)_ | sim |
| `led.auto_release` | `daemon/ipc_handlers.py:1036` (`_handle_led_auto_release`) | Só registra no diário: a luz não tem trava a soltar. | sim |
| `rumble.set` | `daemon/ipc_handlers.py:3363` (`_handle_rumble_set`) | Fixa a vibração; RECUSA no Modo Nativo. | sim |
| `rumble.stop` | `daemon/ipc_handlers.py:3474` (`_handle_rumble_stop`) | Para o rumble e fixa (0, 0); no Modo Nativo SOLTA o par. | sim |
| `rumble.passthrough` | `daemon/ipc_handlers.py:3525` (`_handle_rumble_passthrough`) | Libera controle de rumble para jogo/UDP. | sim |
| `rumble.policy_set` | `daemon/ipc_handlers.py:3552` (`_handle_rumble_policy_set`) | Altera política global de intensidade de rumble. | **não** |
| `rumble.policy_custom` | `daemon/ipc_handlers.py:3568` (`_handle_rumble_policy_custom`) | Define política "custom" com multiplicador explícito. | **não** |
| `rumble.motores.set` | `daemon/ipc_handlers.py:3614` (`_handle_rumble_motores_set`) | `rumble.motores.set` — a barra de CADA motor, no perfil. | sim |
| `sensor.set` | `daemon/ipc_handlers.py:3777` (`_handle_sensor_set`) | `sensor.set` — desliga giroscópio, acelerômetro e touchpad DE VERDADE, por controle. | **não** |
| `daemon.status` | `daemon/ipc_handlers.py:1467` (`_handle_daemon_status`) | _(o handler não tem docstring)_ | sim |
| `daemon.state_full` | `daemon/ipc_handlers.py:1740` (`_handle_daemon_state_full`) | Estado completo pra GUI consumir a 20Hz. | sim |
| `daemon.pause` | `daemon/ipc_handlers.py:1652` (`_handle_daemon_pause`) | Pausa o despacho de input sem matar o daemon. | **não** |
| `daemon.resume` | `daemon/ipc_handlers.py:1657` (`_handle_daemon_resume`) | Retoma o despacho de input. | **não** |
| `freestyle.set` | `daemon/ipc_handlers.py:1662` (`_handle_freestyle_set`) | Liga/desliga o Modo Freestyle — o botão «Modo Freestyle» da aba Jogar. | sim |
| `native.mode.set` | `daemon/ipc_handlers.py:1720` (`_handle_native_mode_set`) | Liga/desliga o Modo Nativo — "release total" do controle. | sim |
| `controller.list` | `daemon/ipc_handlers.py:3193` (`_handle_controller_list`) | Lista os controles do daemon; opt-in `external` soma o inventário 8BIT-01. | sim |
| `controller.target.set` | `daemon/ipc_handlers.py:3306` (`_handle_controller_target_set`) | Define o ALVO das ações de output. | **não** |
| `daemon.reload` | `daemon/ipc_handlers.py:3952` (`_handle_daemon_reload`) | Aplica overrides parciais de config em runtime. | sim |
| `launch_env.refresh` | `daemon/ipc_handlers.py:3980` (`_handle_launch_env_refresh`) | Rematerializa as envs de launch do wrapper sob demanda. | **não** |
| `lightbar.reset` | `daemon/ipc_handlers.py:3340` (`_handle_lightbar_reset`) | Manda o Reset LED state (0x08) sob demanda — INSTRUMENTO de medição. | **não** |
| `debug.player_leds` | `daemon/ipc_handlers.py:3351` (`_handle_debug_player_leds`) | Liga/desliga a escrita do LED de JOGADOR — INSTRUMENTO de eliminação. | **não** |
| `speaker.set` | `daemon/ipc_handlers.py:3997` (`_handle_speaker_set`) | `speaker.set` — volume/mudo/devolução do alto-falante. | sim |
| `mic.set` | `daemon/ipc_handlers.py:4147` (`_handle_mic_set`) | `mic.set` — mudo do microfone no FIRMWARE do controle. | sim |
| `mic.canal.set` | `daemon/ipc_handlers.py:4200` (`_handle_mic_canal_set`) | `mic.canal.set` — O ATO INTEIRO do microfone. | **não** |
| `mic.led.set` | `daemon/ipc_handlers.py:4277` (`_handle_mic_led_set`) | `mic.led.set` — o LED do botão de mudo, e a DEVOLUÇÃO da posse dele. | sim |
| `mic.volume.set` | `daemon/ipc_handlers.py:4325` (`_handle_mic_volume_set`) | `mic.volume.set` — volume da CAPTURA no sistema. | sim |
| `mouse.emulation.set` | `daemon/ipc_handlers.py:4412` (`_handle_mouse_emulation_set`) | Liga/desliga emulação de mouse+teclado. | sim |
| `mouse.emulation.restore` | `daemon/ipc_handlers.py:4471` (`_handle_mouse_emulation_restore`) | Restaura a emulação de mouse conforme a preferência persistida. | **não** |
| `desktop.arranjo.apply` | `daemon/ipc_handlers.py:4488` (`_handle_desktop_arranjo_apply`) | Carrega no aparelho o arranjo do `desktop`: a Navegação ou o Point and click. | sim |
| `desktop.arranjo.repor` | `daemon/ipc_handlers.py:6030` (`_handle_desktop_arranjo_repor`) | Repõe a tabela do Point and click, se é o arranjo de agora: o serviço decide. | **não** |
| `keyboard.emulation.set` | `daemon/ipc_handlers.py:4691` (`_handle_keyboard_emulation_set`) | Liga/desliga a emulação de TECLADO. | **não** |
| `desktop.status.set` | `daemon/ipc_handlers.py:4518` (`_handle_desktop_status_set`) | O «Status do Modo» da aba Navegação: mouse e teclado, e o perfil. | sim |
| `navegacao.interna.set` | `daemon/ipc_handlers.py:4566` (`_handle_navegacao_interna_set`) | Liga a Navegação Interna, ou troca o tipo («Interna» ou «Uso geral» da aba 06). | sim |
| `navegacao.foco` | `daemon/ipc_handlers.py:4590` (`_handle_navegacao_foco`) | A janela diz se está na frente; a resposta traz os toques de cada controle. | sim |
| `navegacao.big_picture.set` | `daemon/ipc_handlers.py:4668` (`_handle_navegacao_big_picture_set`) | Liga ou desliga o Modo Big Picture na Steam. | sim |
| `gamepad.emulation.set` | `daemon/ipc_handlers.py:4747` (`_handle_gamepad_emulation_set`) | Liga/desliga o gamepad virtual e define a máscara. | sim |
| `gamepad.mask.set` | `daemon/ipc_handlers.py:4719` (`_handle_gamepad_mask_set`) | O MODO ÚNICO de todos os controles: `gamepad.mask.set {flavor}`. | sim |
| `coop.set` | `daemon/ipc_handlers.py:4845` (`_handle_coop_set`) | Liga o co-op local; RECUSA desligar. | sim |
| `coop.sync` | `daemon/ipc_handlers.py:4875` (`_handle_coop_sync`) | Roda UM ciclo cheio de reconciliação do co-op (`sync(force=True)`). | sim |
| `daemon.emulation.suppress` | `daemon/ipc_handlers.py:4891` (`_handle_emulation_suppress`) | Liga/desliga o modo jogo (suprime emulação mouse/teclado). | sim |
| `led.player_set` | `daemon/ipc_handlers.py:936` (`_handle_led_player_set`) | Aplica bitmask de 5 LEDs de player no controle. | sim |
| `led.player_brightness_set` | `daemon/ipc_handlers.py:966` (`_handle_led_player_brightness_set`) | O brilho das cinco luzes de número: Fraco, Médio ou Forte. | sim |
| `identity.renumber` | `daemon/ipc_handlers.py:1049` (`_handle_identity_renumber`) | Reordena a FILA de preferência (DualSense + externos). | sim |
| `identity.number.set` | `daemon/ipc_handlers.py:1206` (`_handle_identity_number_set`) | Atribui o NÚMERO EXIBIDO de UM controle. | sim |
| `machine.declare` | `daemon/ipc_handlers.py:4903` (`_handle_machine_declare`) | Grava no `maquina.json` o que o usuário declarou sobre a máquina. | sim |
| `plugin.list` | `daemon/ipc_handlers.py:4967` (`_handle_plugin_list`) | Lista plugins carregados no daemon. | **não** |
| `plugin.reload` | `daemon/ipc_handlers.py:4975` (`_handle_plugin_reload`) | Recarrega plugins do disco. | **não** |
| `mods.agora` | `daemon/ipc_handlers.py:4993` (`_handle_mods_agora`) | A coluna «Agora» da janela de uma extensão: o último ``acessorios.estado`` publicado. | **não** |
| `mods.parar_tudo` | `daemon/ipc_handlers.py:5008` (`_handle_mods_parar_tudo`) | O «Parar tudo» da janela: o gesto ``para`` vai só à extensão ``{mod}``. | **não** |
| `mods.jogos` | `daemon/ipc_handlers.py:5033` (`_handle_mods_jogos`) | Os jogos da extensão de lançador ``{mod}``: o último ``lancador.jogos`` publicado. | **não** |
| `mods.acao` | `daemon/ipc_handlers.py:6062` (`_handle_mods_acao`) | O clique numa ação da janela: ``extensao.acao`` vai só à extensão ``{mod}``. | **não** |
| `mods.livre` | `daemon/ipc_handlers.py:6089` (`_handle_mods_livre`) | O arrastar do controle livre: ``extensao.livre`` só à extensão ``{mod}``. | **não** |
| `radio.ponte.ligar_aqui` | `daemon/ipc_handlers.py:5338` (`_handle_radio_ponte_ligar_aqui`) | «Ligar aqui»: a ponte deste controle sobe além do limite do adaptador. | **não** |
| `radio.mover` | `daemon/ipc_handlers.py:5368` (`_handle_radio_mover`) | «Mover» um aparelho para um adaptador, ou o «Conectar» (D8). | sim |
| `mira.set` | `daemon/ipc_handlers.py:5461` (`_handle_mira_set`) | `mira.set` — o chip «Analógico Virtual» e os ajustes da Calibrar, POR CONTROLE. | sim |
| `haptica.testar` | `daemon/ipc_handlers.py:5669` (`_handle_haptica_testar`) | `haptica.testar` — o botão «Háptica» da aba Vibração, num controle. | sim |
| `radio.busca.set` | `daemon/ipc_handlers.py:5700` (`_handle_radio_busca_set`) | O «Procurar»: liga ou desliga a busca do rádio, com valor absoluto. | sim |
| `radio.dispensar` | `daemon/ipc_handlers.py:5715` (`_handle_radio_dispensar`) | O X do «Não Conectou»: o movimento acabado do aparelho sai da publicação. | **não** |
| `motion.calibrate` | `daemon/ipc_handlers.py:5796` (`_handle_motion_calibrate`) | `motion.calibrate {uniq}` — mede o repouso de UM controle e guarda o zero dele. | sim |
| `perfil.ativacao.set` | `daemon/ipc_handlers.py:5970` (`_handle_perfil_ativacao_set`) | `perfil.ativacao.set` — o modo e o filtro do botão, no perfil ou numa peça. | **não** |
| `perfil.analogicos.set` | `daemon/ipc_handlers.py:5975` (`_handle_perfil_analogicos_set`) | `perfil.analogicos.set` — a zona morta, a curva e a mão, no perfil ou numa peça. | **não** |
| `perfil.cursor.set` | `daemon/ipc_handlers.py:5980` (`_handle_perfil_cursor_set`) | `perfil.cursor.set` — a precisão, a permanência e o clique travado do cursor. | **não** |
| `sequencia.gravar` | `daemon/ipc_handlers.py:5985` (`_handle_sequencia_gravar`) | `sequencia.gravar` — ouve os botões de um controle e devolve os passos e os tempos. | **não** |
| `sequencia.tocar` | `daemon/ipc_handlers.py:6006` (`_handle_sequencia_tocar`) | `sequencia.tocar` — toca uma vez, no pad virtual, a sequência que a tela mostra. | **não** |

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
| `controller.list`   | `{}`                                          | `{controllers: [{vid, pid, transport, firmware, edge}]}` |
| `daemon.reload`     | `{}`                                          | `{status}`                             |
| `mouse.emulation.set` | `{enabled?: bool, speed?: 1-12, scroll_speed?: 1-5}` | `{status, enabled}`             |
| `native.mode.set`   | `{enabled?: bool}` (ausente = toggle)         | `{status, native_mode}`                |
| `freestyle.set`     | `{ligado?: bool}` (ausente = inverte)         | `{status, freestyle_ligado, active_profile}` |

### `uniq` — o alvo por controle

Os comandos de SAÍDA aceitam um `uniq` opcional (o MAC normalizado, 12 hex) e,
com ele, escrevem SÓ naquele controle, registrando o override por-MAC —
`trigger.set`, `trigger.reset`, `led.set` e `led.player_set`. Omitido, vale o
comportamento global clássico ("Todos"). É o eixo que a persistência já usava:
sem ele, o pedido cai em broadcast e "configurei o Controle 2 e mudou todos".

`mic.set` e `speaker.set` também aceitam `uniq`, com uma diferença que vale
registrar: neles, omitir NÃO é broadcast — é o controle **primário**. O áudio
mora num handle só (`_handle_for`), não numa lista, então nunca houve o risco de
"mexi num e mudou todos" que os outros quatro tinham.

`rumble.set`, `rumble.stop` e `rumble.passthrough` aceitam `uniq` desde 03/10/2026: com ele, o par fixado é
SÓ daquele controle, e o «Testar» do P2 não cala a vibração do jogo no P1. Omitido,
`rumble.set` e `rumble.stop` valem para o alvo de agora, e `rumble.passthrough` solta
os pares de todos.

`trigger.reset` foi o último dos quatro primeiros a ganhar o parâmetro (25/07) — o botão
"Desligar" da aba Gatilhos zerava o gatilho dos quatro enquanto o "Aplicar" ao
lado mandava para um só. Ele grava `Off` na camada `usuaria` só do gatilho
pedido: a luz e a vibração que ela ajustou em outra aba ficam como estão.

### `led.auto_release` — só registra

`{}` → `{status, categoria: "led", escopo}`. **Não escreve byte nenhum no
controle, não aceita `uniq` e não solta nada**: desde 14/09 ele é uma linha no
diário (`led_auto_release`) e a resposta: a trava manual por categoria saiu
inteira (D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO). O `led.set` e o
`led.player_set` entram na camada `usuaria` de cada controle que alcançam, e quem
a solta é a ativação de um perfil pela mão (`origin` `manual`). Nenhum
código do produto o chama; o método fica no contrato para quem ainda o usa, e
`escopo` diz na resposta que nada aqui é por controle. O que está guardado por
controle se lê em `controllers[].camada_da_usuaria` do `daemon.state_full`: a
lista dos campos (`led`, `player_leds`, `trigger_left`…) que a usuária fixou e
ainda valem, vazia quando o controle não tem ajuste próprio.

### `aplicado_em` e `guardado_em` — o que a resposta AFIRMA

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
condições da tabela de mentiras e deixou a terceira — **Modo Nativo
com o output mutado** — respondendo `aplicado_em`. Mutado, a rota sysfs do LED
está desabilitada, o report `0x31` avulso é pulado e o `report_thread` não
escreve nada: nenhum byte sai, e o desejado é re-escrito no desmute. Isso é
`guardado_em`, pela mesma definição do controle fora da mesa — o que muda é o
evento que o libera. Na mesma leva, a escrita que LEVANTA (o `hidraw` que some
debaixo da escrita) deixou de contar como aplicada: o backend devolve `falhou` e as
duas listas saem vazias, porque prometer "guardado" ali seria mandá-la esperar
um evento que pode nunca vir.

### `led.player_brightness_set` — o brilho das luzes de número

`{brilho: "fraco" | "medio" | "forte", uniq?}` → `{status, brilho,
aplicado_em, guardado_em}`. Decisão de 24/09/2026
(`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): Fraco, Médio e Forte na linha
LEDs, nascendo no Fraco. A palavra é a do perfil
(`leds.player_led_brightness`); a tradução para o degrau do firmware
(`common[42]`: 0 forte, 1 médio, 2 fraco) é de
`core/led_control.degrau_do_brilho_das_luzes`, que recusa palavra fora das três
dizendo quais são.

Com `uniq`, vale só naquele controle, pela mesma porta e com as mesmas duas
listas do `led.player_set`. Sem `uniq`, é o «Todos»: vira o padrão de quem
chegar depois (hotplug) e é escrito em cada conectado — senão um override
guardado no perfil venceria o «Todos» que acabou de ser pedido. Antes de
escrever, o «Todos» pergunta o seletor de saída do backend, como o `led.set` e
o `led.player_set`: com o seletor num controle, o pedido vale só nele; com o
alvo escolhido fora da mesa, ninguém recebe e o valor fica guardado no override
dele (`guardado_em`). Sem seletor, o `guardado_em` sai vazio.

O pedido NÃO grava no perfil — quem grava é o gesto da aba Iluminação, antes
de chamar o método. E ele entra na camada da usuária, como o `led.player_set`:
atravessa a troca AUTOMÁTICA de perfil (a janela do jogo) e sai na troca manual
(medido na conferência de 25/09/2026).

O degrau sai pelos caminhos do número, nos dois transportes: no cabo sem nó de
LED gravável, no fluxo; no cabo com o nó do kernel, num `0x02` avulso logo
depois do número (o nó do `hid_playstation` é 0/1 por lâmpada e não escolhe
brilho); no rádio, no `0x31` que acende o número. O `flag2` leva só o bit0
(`SET_PLAYER_LED_BRIGHTNESS`), nunca o 0x02 do LIGHTBAR_SETUP.

Quem chama é a pílula da aba Iluminação, e ela grava a palavra no override do
controle ANTES de chamar: uma troca de perfil reaplica o que o perfil diz, que é
o que o usuário escolheu.

**A leitura de volta é o `state_full`**: cada
controle traz `brilho_das_luzes` (`"fraco"`, `"medio"` ou `"forte"`, o degrau
que o merge manda ao aparelho) e `brilho_da_barra` (`0.0`-`1.0`, o brilho em
que a cor de `lightbar_rgb` foi acesa). Os dois saem do dono do merge, com a
camada da usuária — a que atravessa a troca automática de perfil —, e `null`
quer dizer «não sei»: a aba Iluminação cai no perfil do disco. O `led.set`
leva o `brightness` até o backend para isso, e a cor que chega sem ele (a CLI
antiga) publica `null`.

### `rumble.motores.set` — a BARRA de cada motor

| Método               | Parâmetros                                         | Retorno                                                        |
|----------------------|----------------------------------------------------|----------------------------------------------------------------|
| `rumble.motores.set` | `{uniq?: str, forte_pct?: 0-100, fraco_pct?: 0-100, haptica_pct?: 0-200, efeito_haptico?: str, efeito_imersao?: str}` | `{status, uniq, perfil, gravado, forte_pct, fraco_pct, haptica_pct, efeito_haptico, efeito_imersao}` |

Decisão, 04/09/2026. **A barra não é um comando: é POLÍTICA**, e ela
MULTIPLICA o degrau da coluna — `efetivo(motor) = degrau x barra(motor)`. Com o
degrau em `Máximo` (150 %), barra fraca 100 % e barra forte 50 %, o motor fraco
recebe 150 % e o forte 75 %.

Por isso o valor vai para o **perfil**, por peça
(`ControllerRumbleOverride.motor_forte_pct` / `motor_fraco_pct`), e não para o
`DaemonConfig`: `rumble.set {weak, strong}` continua sendo o comando de tremer
AGORA, e este método não o chama — camadas diferentes, pela mesma razão que
separa `mic.set` de `mic.volume.set`.

**Campo omitido não mexe naquela barra**; `100` nos dois **apaga** os campos (no
aparelho "escreveu 100" e "não escreveu" são o mesmo fator 1,0, e a chave a
menos é o que mantém o downgrade possível). A seção `rumble` da peça só cai
inteira quando fica vazia — o degrau daquela peça (`policy`, o teto do card do
cabo) mora ali e não é deste gesto. Nada mudou = `gravado: false`, sem regravar:
um `save` troca a data do arquivo e faz o daemon reaplicar o perfil.

`status` pode ser `"ok"`, `"sem_controle"` (mesa vazia), `"sem_endereco"` (o
alvo não é um MAC de peça de plástico) ou `"sem_perfil"`; os três últimos vêm
com `motivo`. A faixa 0-100 é recusada na BORDA do esquema, com a frase que
EXPLICA por que a barra não passa de 100 — ela é o segundo fator, e quem
amplifica é o degrau.

**A leitura de volta é o `state_full`**: `rumble_motores` traz `{uniq:
{forte_pct, fraco_pct}}` **só de quem tem opinião**, e `rumble_motor_pct_padrao`
traz o 100 do "sem opinião" para a tela não digitá-lo. A fonte é a MESMA que
`apply_game_rumble` multiplica (`gamepad._motores_do_perfil_ativo`), e não uma
segunda leitura do disco: duas leituras podem divergir, e a tela pintaria o que
o motor não usa.

**As duas listas da aba Vibração vão no mesmo pedido** (15/10/2026): `efeito_haptico` (a forma do
toque háptico: toque, impacto, estalo, guarda, aparo, som_no_corpo) e `efeito_imersao` (o padrão dos
motores: tranco, batida, onda, coice, pancada_do_lado, ressoar, ricochete), e as duas aceitam `sem_efeito` e `do_estilo`.
`do_estilo` é o padrão e **apaga** a chave (sem escolha vale o automático, nunca o `sem_efeito`); chave
que não existe é recusada com a lista das que existem. A leitura volta na resposta; a tela as lê do
perfil.

**O ganho da háptica por áudio vai no mesmo pedido** (29/09/2026): `haptica_pct`, de 0 a 200, com o mesmo contrato (omitido não mexe; o
padrão, 150, apaga a chave). Ele não multiplica o degrau: no PCM do jogo a Força não
alcança, e esta barra é o único fator. Quem o aplica é o dono do ganho
(`daemon/ganho_da_haptica.py`), relido no mesmo ato: os traseiros do fluxo do laço daquele
controle no cabo, em fator linear (a placa fica cheia), e o conversor da ponte no rádio, antes do int8. No
`state_full`, cada controle traz `haptica_pct` (o que o usuário escolheu), `haptica_vale_pct`
(o que vale: na Economia, no máximo 30), `haptica_alcanca` (o Hefesto está no caminho
dele) e `haptica_no_ar` (há háptica chegando a ele agora: no cabo, o monitor da placa
dele; no rádio, a ponte em háptica com sinal), e `haptica_pct_padrao` traz o padrão.

### `mic.set` / `speaker.set` — o áudio do controle

| Método        | Parâmetros                                                       | Retorno                                        |
|---------------|------------------------------------------------------------------|------------------------------------------------|
| `mic.set`     | `{muted: bool\|null, uniq?: str}`                                | `{status, audio, mic_mudo_desejado}`           |
| `mic.led.set` | `{aceso: bool\|null, uniq?: str}`                                | `{status, aceso}`                              |
| `speaker.set` | `{volume?: 0-255, muted?: bool, release?: bool, uniq?: str}`     | `{status, speaker}`                            |

Os dois escrevem no MESMO bloco do report de saída (`common[4..9]`) e seguem a mesma disciplina: o hefesto só toca o campo depois de
alguém pedir, e o que não tem dono sai com o bit de validação apagado — o
firmware conserva o que tinha.

**A posse, porém, é por BYTE e por BIT — não é do bloco inteiro** (medido em 29/07). Este documento tratava `common[4..9]` como uma coisa só, e para
efeito de disciplina isso está certo; para efeito de PREÇO, não:

| Campo                    | Byte        | Bit de autoridade | Quem toma     |
|--------------------------|-------------|-------------------|---------------|
| volume do fone           | `common[4]` | `flag0 0x10`      | `speaker.set` |
| volume do alto-falante   | `common[5]` | `flag0 0x20`      | `speaker.set` |
| volume do microfone      | `common[6]` | `flag0 0x40`      | ninguém hoje  |
| roteamento de áudio      | `common[7]` | `flag0 0x80`      | ninguém hoje  |
| LED do botão de mudo     | `common[8]` | `flag1 0x01`      | `mic.led.set` |
| mudo do microfone        | `common[9]` | `flag1 0x02`      | `mic.set`     |

Fontes: `core/ds_output_report.py:54-54`, a aplicação por byte em
`core/backend_pydualsense.py` (`_build_common`) e o mudo do microfone em ramo
separado, logo abaixo desse bloco.

**A consequência prática, que a tela precisa dizer do jeito certo: mexer no
volume pela janela NÃO mata o botão de microfone do controle.** São bits
diferentes. O que se mediu no microfone — `mic unmute` toma a posse e o botão
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

**`mic.led.set` é o BYTE VIZINHO, e acender NÃO muta** (01/09/2026). `common[8]` e `common[9]` têm bits de autorização diferentes, e é
por isso que a inversão que o usuário pediu — *"as pessoas precisam ter um aviso
visual que o mic tá funcionando"* — cabe sem escrever uma linha no byte do mudo.
**Neste projeto, ACESO = este microfone está VIVO**, ao contrário da convenção da
Sony; o contrato do byte não inverteu, quem decide o argumento é o chamador.

Os três estados são os mesmos, com o mesmo cuidado:

- `aceso: true` — acende, e a posse do `common[8]` passa a ser nossa;
- `aceso: false` — apaga. É uma ORDEM, e o kernel deixa de mandar na luz;
- `aceso: null` — **devolve a posse** ao `hid-playstation`, que escreve
  `mute_button_led = ds->mic_muted` a cada borda do botão físico.

A chave `aceso` é **obrigatória**, pela mesma cicatriz do `3d9bb7e`. E isto
**não** é o `RELEASE_LEDS` (0x31): aquele só existe no rádio, apaga os
player-LEDs sempre e trava a lightbar na janela pós-conexão. Aqui só o bit
`0x01` do flag1 cai, nos dois transportes.

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

**`speaker.set` tem uma quarta chave, `release` (31/07):**

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
não rigor: medido, mudo como PRIMEIRA escrita manda zero e guarda zero
como preferência — o "desmudo" seguinte restaura zero e o próprio par
mudo/desmudo não solta mais o alto-falante. Mande um `volume` antes. Pela mesma
razão, nada no produto manda `speaker.set` **vazio**: a chamada sem `volume`
toma a posse e manda ZERO.

`speaker.set` não arma trava nenhuma: a trava manual por categoria saiu inteira
em 14/09 (D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO), e o perfil ativado
aplica o volume que guarda.

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
2. perfil da placa preso em `input:iec958-stereo` (que capta: o «sem sinal» de 25/07 era o mudo do firmware, e em 26/07 ele gravou pico 4606) porque
   o WirePlumber marca a entrada analógica indisponível sem fone plugado — mas o
   microfone embutido usa esse mesmo caminho.

### `identity.renumber` / `identity.number.set` — o número do controle

| Método                | Parâmetros              | Retorno                                                   |
|-----------------------|-------------------------|-----------------------------------------------------------|
| `identity.renumber`   | `{}`                    | `{ok: true, renumbered: {addr: lugar}}` \| `{ok: false, reason}` |
| `identity.number.set` | `{uniq: str, number: int}` | `{ok: true, number, changed: {addr: lugar}}` \| `{ok: false, reason}` |

Os dois escrevem o MESMO estado — a **fila de preferência** do
`controllers.json` (schema 3, campo `order`), compartilhada entre DualSense e
externos. Desde a numeração por lugar na fila, o que se grava é o **lugar na fila**, nunca um número
absoluto: o número que a janela mostra é a *colocação desse lugar entre quem está
presente agora*. É por isso que um controle sozinho na mesa é sempre o 1.

- `identity.renumber` **compacta todo mundo** para 1..N preservando a ordem
  relativa, e empurra quem está ausente para o fim da fila. É o acabamento do
  botão **"Reconectar Controles"** da aba Jogar — um gesto de faxina (ver
  `coop.sync`, abaixo).
- `identity.number.set` (25/07) atribui o número de **UM** controle:
  permuta entre si os lugares que os PRESENTES já ocupam, pondo o alvo na
  posição pedida. Os lugares de quem está ausente ficam intocados — este gesto
  não rebaixa ninguém que está na gaveta.

Ele é `number` e não `player` de propósito: "jogador" nomeia outra PERGUNTA
neste projeto — "este controle está jogando agora?" —, respondida pelo campo
`controllers[].player` do `state_full`, que é `null` fora do co-op.

O que mudou em **15/08/2026**: os dois deixaram de ser espaços
de numeração diferentes. Até ali o `player` saía do índice de alocação do vpad
do co-op (`_next_player_index`, ordem em que o grab confirmou na sessão) e a
barra de LED do controle saía desta fila — e, com os quatro DualSense do usuário no
rádio, três dos quatro acendiam um número e eram chamados de outro. Agora
`CoopManager.numeros_de_jogador()` é a fonte única dos dois: quando `player`
existe, ele é igual ao `player_slot`. A ordem de chegada é a verdade, e a barra
é função dessa ordem.

**Recusas** (nenhuma escreve nada):

| `reason`                | quando                                                      |
|-------------------------|-------------------------------------------------------------|
| `sessao_de_jogo_aberta` | `display_authority == "game"` — repintar o LED do controle que o jogo está usando no meio da partida é um erro já curado |
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

**O co-op sem interruptor (06/08/2026, decisão de produto):** o co-op local
não é mais uma opção — cada controle conectado é um jogador, sempre. Palavra
de produto: *"se eu conecto 4 controles no PC eu espero, com 4 pessoas jogando, que
cada um controle o próprio personagem"*.

- `coop.set {enabled: true}` continua ligando/reconciliando e **persiste** o
  gesto manual (é gesto do usuário: toma a posse do eixo `mode`).
- `coop.set {enabled: false}` é **recusado em voz alta** — `status: "recusado"`,
  com `motivo` legível. A FORMA do retorno é preservada de propósito
  (`players` continua lá): quem lê o contrato não quebra, e quem esperava o
  desligamento não é enganado por um `"ok"`.
- `coop.sync {}` roda **um ciclo cheio** de reconciliação
  (`CoopManager.sync(force=True)`): recria o jogador cujo grab foi recusado ou
  cujo vpad morreu, sem esperar o próximo hotplug. Não liga nem desliga nada,
  não persiste preferência e não toma a posse do eixo `mode`. É o botão
  **"Reconectar Controles"** da aba Jogar, e é o gesto de recuperação do
  jogador que nasce e morre em dois segundos.

`active` no retorno de `coop.sync` é o `should_be_active()` do gate — `false`
quando não há gamepad virtual de pé (modo desktop/nativo) ou quando a exceção
de Steam Input suspendeu os vpads. Nesse estado o ciclo apenas desmonta o que
sobrou: reconciliar **nunca** ressuscita o que o jogo suspendeu (a suspensão é
`CoopManager.disable()`, que não depende da flag).

### `native.mode.set` — Modo Nativo

"Release total" do controle: solta o DualSense para o jogo usar os gatilhos
adaptativos NATIVOS da Sony (Sackboy & cia). `enabled=true` → gatilhos Off/Off,
rumble passthrough, emulação (mouse/gamepad) desligada, autoswitch/hotkey
gateados e daemon pausado; persiste em `native_mode.flag` (sobrevive a restart).
`enabled=false` → restaura o último perfil. `daemon.state_full` e `daemon.status`
expõem `native_mode: bool`. Com `origin: "manual"`, ligar grava o modo
`native` no perfil ativo depois do aparelho, como o `gamepad.emulation.set` e o
`desktop.arranjo.apply` à mão gravam o modo deles.

### `freestyle.set` — o Modo Freestyle

O botão «Modo Freestyle» da aba Jogar. Substitui o `autoswitch.lock` (o cadeado
de 23/07, que cedia a todo perfil de jogo) desde 28/09/2026. `ligado=true` é o
`profile.switch` do Freestyle, o mesmo gesto do «Ativar» na aba Perfis: ligado,
o Freestyle vale para os quatro controles, no cabo e no rádio, e nenhum caminho
automático troca o perfil (autoswitch, lançamento, restauro, perfil de janela).
`ligado=false` solta a trava de 30 s da troca à mão e devolve o jogo vivo do
lançamento com o perfil dele. Persiste em `freestyle_ligado.flag`; o
`autoswitch_locked.flag` de antes é migrado uma vez no boot. `daemon.state_full`
e `daemon.status` expõem `freestyle_ligado: bool` (no lugar de
`autoswitch_locked`).

### `mouse.emulation.set` — `enabled` é OPCIONAL

- **com `enabled`** (bool): liga/desliga a emulação de mouse (cria/destrói o
  device virtual, persiste o flag). Ligar desliga o gamepad virtual (mútua
  exclusão).
- **sem `enabled`** (rota *speed-only*, usada pelos sliders da GUI): atualiza
  apenas `speed`/`scroll_speed` da emulação — **nunca** liga/desliga nem cria o
  device, e só re-persiste o flag se a emulação já estava ligada. Impede que
  arrastar um slider religue uma emulação desligada.

### `machine.declare` — o que o Hefesto NÃO tem como medir

O único método que escreve o `maquina.json` (`utils/maquina.py`), o terceiro
arquivo de `config_dir()` depois de `controllers.json` e `controller_masks.json`.
Ele guarda o que nenhum barramento sabe: altura da antena, linha de visada, o que
é cada rádio vizinho, o modo da chave física de um controle genérico, a cor do
plástico quando a leitura do firmware falha, o teto de orçamento da mesa e o
ambiente de área de trabalho. Não é configuração de perfil — não muda com o jogo
aberto.

| Método            | Parâmetros                          | Retorno                                  |
|-------------------|-------------------------------------|------------------------------------------|
| `machine.declare` | `{maquina: {...}}` (declaração parcial) | `{ok: true}` ou `{ok: false, reason}` |

A declaração é **parcial de propósito**: cada seção da aba manda só o que mudou, e
a fusão acontece contra o disco sob lock, dicionário com dicionário. Sem isso, a
última seção a gravar apagaria o que as outras quatro tinham declarado. `null`
presente é escolha ("voltei para 'Não sei'") e sobrescreve; só a AUSÊNCIA da chave
preserva o que havia.

Os três `reason` possíveis são `declaracao_invalida`, `versao_desconhecida` e
`falha_ao_gravar`, e **todos vêm no corpo, nunca como erro JSON-RPC** — a ponte da
GUI usa `_safe_call`, que colapsa erro de protocolo e daemon morto no mesmo
`(False, None)`, e a janela anunciaria "daemon offline?" para um daemon vivo. A
frase de tela de cada motivo mora do lado da GUI (`_MOTIVOS_MAQUINA`,
`app/ipc_bridge.py`): o daemon não conhece o texto da janela. `versao_desconhecida`
é a recusa que importa — um arquivo escrito por uma versão futura não é lido **nem
sobrescrito**, e os bytes ficam intactos.

A declaração **não** entra no `daemon.state_full`: aquilo é o tique de 20 Hz, e
isto muda por gesto do usuário. O daemon lê o arquivo uma vez no boot
(`daemon/lifecycle.py`, ao lado dos flags de sessão).

### `radio.mover` — mover UM aparelho, ou conectar um novo

O motor é `integrations/central_do_radio.py`: pareia no destino, confere pelo
`HID_PHYS` e pelo movimento chegando, e só então esquece a origem, com a lápide.

| Método        | Parâmetros                                   | Retorno                                     |
|---------------|----------------------------------------------|---------------------------------------------|
| `radio.mover` | `{aparelho?: "aa:bb:…" ou uniq, destino?: "aa:bb:…"}` | `{status, movimento}` ou `{status: "sem_central"}` |

Sem `aparelho` é o «Conectar»: a busca abre no adaptador da D8 (mais vaga de ponte; no
empate, menos controles; quem varre por último), e nada pareia sem o clique do usuário: com
`aparelho` que a janela viu, no destino da busca, é o «Parear» do usuário; o «Parear de Novo» pede o mesmo antes de a janela ver o aparelho, que esteja fora do ar em todo adaptador, e o `Pair` só sai quando a janela o vê. Sem `destino`, a escolha automática do destino escolhe
também no mover. `status: "ocupado"` é a recusa, e ela tem duas causas: OUTRO
movimento está em curso, ou outro motor segurou a trava do rádio por mais de 5 s.
Um por vez vale também para o arrastar e para o «Conectar». Nos dois casos o botão treme e nada mudou. O mesmo
pedido feito de novo devolve o mesmo movimento, e não uma recusa.

A resposta volta assim que a trava vem, com o movimento em `esperando`; o resto
chega por `daemon.state_full`, na chave `radio_central`:
`{movimentos: [...], em_curso, proposta}`. Cada movimento tem `estado`
(`esperando`, `chegou` ou `nao_chegou`), `passo`, `motivo`, `aparelho`, `destino`,
`origens`, `e_controle` e `quando`. `e_controle` é um booleano: controle se confere
pelo `HID_PHYS`, outro aparelho pelo `Connected`. `controle` só existe na `proposta`,
e lá é o `uniq`. `proposta` é o «Equilibrar» — UM movimento, com `controle` e
`destino`, que a tela aplica chamando `radio.mover` com esses dois —, ou `null`,
e é sempre `null` enquanto um movimento está `esperando`. `busca` é a busca do
«Procurar»: `{adaptador, desde, ate}` enquanto a janela de um movimento SEM
aparelho está aberta, ou `null`.

### `radio.busca.set` — o «Procurar» da aba Conexões

| Método            | Parâmetros                                 | Retorno                         |
|-------------------|--------------------------------------------|---------------------------------|
| `radio.busca.set` | `{ligada: bool, destino?: "aa:bb:…"}`      | `{status, busca}`               |

Valor absoluto, como o `freestyle.set`. Ligada, é o «Conectar» sem aparelho no
`destino` (sem ele, a D8), até ela desligar ou até o teto de 120 s; com a busca
de pé noutro adaptador, ela vai para o `destino`. Desligada, a janela fecha
agora, e o movimento acaba em `desligada`, que não é falha (a tela não faz «Não
Conectou» dele). Pedir o estado que já vale responde `ok` sem tocar no rádio. A
resposta traz a `busca` que ficou valendo; `status` diferente de `ok` é a
recusa (`ocupado`, com um «Mover» em curso; `sem_destino`; `sem_central`).

### `radio_receptores` — a saúde do receptor 2.4G

Chave do `daemon.state_full`, sem método: `{ "usb:<vid>:<pid>": {teclas_presas, buracos, janela_s,
lendo} }` para cada receptor 2.4G de teclado e mouse que o censo reconhece. `teclas_presas` conta
as vezes, na última hora (`janela_s`, 3600), em que uma tecla repetiu por mais de 1 s, solte ou não
depois; `buracos`, os vazios de 8 ms e 4× o intervalo do próprio mouse, ou mais, no movimento contínuo.
`lendo` é falso quando o `/dev/input` dele não abriu (sem leitura não há número). **Nunca** leva o
código de uma tecla nem texto: só contagens. A chave é `{}` sob a suíte e no modo falso.

### `mira.set` — o chip «Analógico Virtual», por controle

A palavra, 23/09/2026: um botão ao lado de Giroscópio e Acelerômetro, no
cartão de cada controle — o movimento do controle vira um **analógico**
daquele controle, para quem não alcança o analógico. Desde 08/10/2026
o chip é o «Analógico
Virtual», um só: o giro e a inclinação vão juntos ao lado escolhido.

| Método     | Parâmetros                                                                 | Retorno                                                                                    |
|------------|----------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `mira.set` | `{uniq?: str, ligada?: bool, lado?: "analogico_esquerdo" \| "analogico_direito", sensibilidade?: 1-12, zona_morta_graus_s?: 0-60, gatilho?: str \| null, inverter_horizontal?: bool, inverter_vertical?: bool, inclinacao?: "nenhum" \| "analogico_esquerdo" \| "analogico_direito", toque?: "nenhum" \| "cursor" \| "zonas", mesmo_parado?: bool}` | `{status, uniq, perfil, gravado, ligada, virtual, lado, sensibilidade, zona_morta_graus_s, gatilho, inverter_horizontal, inverter_vertical, toque, inclinacao, mesmo_parado, alcance, ressalva}` |

`ligada: true` grava o giro (`destino`) e a inclinação (`acelerometro`) no
lado guardado da peça (`lado`; o direito, se nunca se escolheu), e `false`
grava `nenhum` nos dois — com opinião: a peça que apagou o chip não mira nem
pela mira do perfil. `lado` grava o lado e acende o chip nele (o «Esquerdo» e
o «Direito» da Calibrar); uma `inclinacao` explícita no mesmo pedido vence o
lado na inclinação. `mesmo_parado` é o «Mesmo parado»: com ele, a inclinação
não pausa quando o controle fica largado na mesa. `sensibilidade` e `zona_morta_graus_s` são os dois deslizantes da tela
Calibrar sensores («O quanto um gesto anda» e «Ignorar tremor até»); `gatilho`
é o «Só enquanto eu segurar» (um botão de `REMAPEAVEIS`, ou `null` para a mira
andar sempre — o PS é recusado), e `inverter_horizontal`/`inverter_vertical`
são os dois «Inverter». `inclinacao` e
`toque` são os dois arranjos da resposta de 28/09/2026:
`inclinacao` grava o `acelerometro` da peça —
o analógico que a inclinação do controle move, `"analogico_esquerdo"` ou
`"analogico_direito"` (o chip embaixo de cada um), ou `"nenhum"` —, e `toque`
grava o destino do touchpad —
`"cursor"` (o dedo move o cursor pelo Hefesto, e o clique é o botão esquerdo),
`"zonas"` (o dedo apoiado aperta o direcional nos dois terços da esquerda, o L1
em cima e o L2 embaixo no terço da direita) ou `"nenhum"` (o touchpad do
computador). Os dois valem onde há controle virtual (modo DualSense e Xbox), do
P1 ao P4. **Campo omitido não
mexe naquele campo**, e qualquer outra chave é recusada: o resto do arranjo
(eixo, teto, pixels por grau) mora no perfil, e o IPC não abre uma porta que a
tela não tem. Sem `uniq` vale o alvo de saída e, sem ele, o primário.

As duas escritas, na ordem: o **perfil** (`controllers[uniq].movimento`, só os
campos escritos — nada mudou = `gravado: false`) e o **vivo** (o mapa por peça
do `store`, que o tique pergunta com o `uniq` de cada jogador, e o filtro do
report, que tira o giroscópio nativo da janela de quem mira — a câmera não anda
em dobro no caminho Virtual). **Em Modo Nativo o pedido com `ligada` é
recusado inteiro** (e o com `lado`, `inclinacao` ou `toque`, que também
precisam do controle virtual), sem escrita nenhuma, com `status: "nativo"` — palavra
de 24/09/2026 (`D-2409-NO-NATIVO-A-MIRA-FICA-CINZA`): no Nativo o chip fica
cinza e não grava. Os ajustes sem `ligada` gravam também no Nativo, com
`alcance.tique = "nao_se_aplica"` e a `ressalva` dizendo que valem quando o
modo voltar. `status` pode ser `"ok"`, `"nativo"`, `"sem_controle"` ou
`"sem_endereco"`, os três últimos com `motivo`.

**A leitura de volta é o `state_full`**: cada controle traz `mira: {ligada,
virtual, lado, destino, toque, inclinacao, sensibilidade, zona_morta_graus_s,
gatilho, inverter_horizontal, inverter_vertical, inclinacao_parada,
mesmo_parado}` — o que vale AGORA para aquela peça
(`ligada` e `destino` são o giro; `toque` e `inclinacao`, os outros dois, e
`inclinacao` diz o analógico que ela move, como no pedido; `virtual` é o chip
aceso, com o giro ou a inclinação num analógico, e `lado` é o lado que ele
acende), pela mesma pergunta que o tique faz (`roteador_de_movimento.da_peca`),
e os números mesmo com a mira apagada. `inclinacao_parada` é verdadeiro
enquanto a inclinação está pausada porque o controle ficou parado (3 s sem
mexer; a mão que pega o controle a devolve), e nunca com `mesmo_parado`.

Cada controle traz também `no_jogo: {lx, ly, rx, ry}` — os quatro eixos que o
pad virtual DAQUELE controle mandou ao jogo no último envio —, ou
`null` sem pad (o Nativo, a Navegação), com o jogador cedido ao primário, ou
antes do primeiro envio. É o segundo ponto do círculo do analógico na aba
Controles: o que o jogo vê, ao lado do que a mão faz.

### `haptica.testar` — o botão «Háptica» da aba Vibração

| Método           | Parâmetros                     | Retorno                                                        |
|------------------|--------------------------------|----------------------------------------------------------------|
| `haptica.testar` | `{uniq: str, ligado: bool}`    | `{status, uniq, ligado, leva, forma, par?, motivo_da_forma?}`  |

Decisão de produto de 29/09/2026: o «Testar agora» tem dois botões, «Vibração» e
«Háptica». Ligado, o tocador do aparelho daquele controle toca, a cada rebate, a
forma que ele escolheu em «Efeito háptico» (`forma`), lida e tocada como o toque
do tiro (`tato_vivo.escolhas_ativas`, `tocar_o_toque`): «Do estilo» e sem escolha
tocam a forma do estilo (o Toque), o Som no corpo toca um grave fixo, e «Sem
efeito» recusa com `status: "sem_efeito"` e `motivo`. O par `(127, 127)` só entra
quando a forma não pode tocar (a longa no rádio sem fatia livre), com `par` e
`motivo_da_forma` (a amplitude é `nível / 255`, e com o ganho no teto, 200 %, dá
0,996, sem cortar). O ganho da linha «Sensor Háptico» vale depois (a placa no
cabo, o conversor da ponte no rádio), com as recusas do rumble convertido do modo
Xbox: o endpoint com fluxo de jogo, o alto-falante tocando pelo rádio e o ganho
em 0 deixam o tocador calado, e `leva` diz se o caminho até o controle está de pé
agora. `ligado: false` cala.

**O teste que ninguém rebate solta sozinho**: a janela manda o `ligado: true` a
cada segundo, e o daemon cala o tocador do teste que passou do teto do rumble
fixado (`rumble.TETO_DO_RUMBLE_FIXADO_S`) sem rebate. `status` pode ser `"ok"`,
`"sem_efeito"`, `"sem_controle"` (o controle fora da mesa, ou sem háptica) ou
`"sem_som"` (o subsystem do som fora do ar), os três últimos com `motivo`. Sem
`uniq` ou sem `ligado` booleano, o erro é de parâmetro.

### `navegacao.interna.set` / `navegacao.foco` — a Navegação Interna

| Método                   | Parâmetros                                   | Retorno                                        |
|--------------------------|----------------------------------------------|------------------------------------------------|
| `navegacao.interna.set`  | `{ligada?: bool, tipo?: "interna" \| "computador"}` | `{status, navegacao: {interna_ligada, tipo, foco}}` |
| `navegacao.foco`         | `{ativa: bool}`                              | `{status, foco, toques: {uniq: {r1, l1, x, o, quadrado, triangulo, cima, baixo, esquerda, direita, start}}}` |

`navegacao.interna.set`
é o «Status da navegação» no tipo Interna (`ligada`) e a lista «Tipo de navegação»
(`tipo`, que só grava o tipo); exige ao menos um dos dois. A Interna é da máquina e
não do perfil: trocar de perfil não a desliga, e ela não mexe no mouse.

`navegacao.foco` é a janela dizendo que está na frente: um pulso quando ganha ou perde
o foco, e uma renovação a cada tique da janela com a Interna ligada. Sem renovação por
1 s (`PRAZO_DO_FOCO_S`) o daemon larga o foco sozinho, e uma janela que morre sem se
despedir não deixa botão roubado. Com a Interna ligada e o foco vivo, os botões que
navegam (R1, L1, X, O, quadrado, triângulo, o direcional e o Start) não chegam ao
jogo, e o R1 e o L1 não saem como Alt+Tab. `toques` são contadores que só sobem, por
controle, contados só com a Interna agindo: a janela aplica a diferença com o que
leu antes, e um toque curto entre dois tiques da janela não se perde.

O `state_full` traz o bloco `navegacao: {interna_ligada, tipo, foco}`; sem o dono no
daemon, o bloco não sai.

### `navegacao.big_picture.set` — o Modo Big Picture na Steam

| Método                      | Parâmetros        | Retorno                                            |
|-----------------------------|-------------------|----------------------------------------------------|
| `navegacao.big_picture.set` | `{ligado: bool}`  | `{status, big_picture: {ligado, agindo, quem_le}}` |

É a lista
«Modo Big Picture na Steam» da aba Navegação, da máquina e não do perfil (a flag
`big_picture.flag` guarda a escolha). `quem_le` diz quem lê o controle no modo vigente:
`"steam"` (Nativo e Steam Input: a Steam lê o físico e o Hefesto não entra) ou
`"hefesto"` (Sony DualSense, Xbox e Navegação). `agindo` é verdadeiro com o modo
ligado, a janela do cliente da Steam na frente e `quem_le == "hefesto"`: então o
direcional, a Cruz e o Círculo de qualquer controle (P1 a P4) viram setas, Enter e Esc
num teclado virtual e saem do pad e do mouse virtuais, para o Big Picture não andar
dois passos por aperto. Sem `/dev/uinput` para o teclado, nada é roubado.

O `state_full` traz o mesmo bloco na chave `big_picture` do bloco `navegacao`.

### `motion.calibrate` — o «Começar» da Calibrar

| Método             | Parâmetros      | Retorno                          |
|--------------------|-----------------|----------------------------------|
| `motion.calibrate` | `{uniq: str}`   | `{status: "medindo", uniq, segundos}` |

Mede o repouso de UM
controle por 5 s (`SEGUNDOS_DO_ZERO`, uma amostra a cada 20 ms) e guarda o zero
dele: o viés do giroscópio, que o motor desconta antes do Analógico Virtual e da
inclinação (só o giro se desconta; a gravidade do repouso fica guardada junto). A resposta volta na hora; um segundo pedido no
meio da medida responde a mesma medida. O critério é o do parado: o controle que
mexeu durante a medida não guarda nada. O zero vai ao
`~/.config/hefesto-dualsense4unix/zeros-dos-sensores.json`, por controle, e volta no
boot. No Nativo mede e guarda igual: o zero vale quando o Hefesto volta a traduzir.
Sem `uniq` de um controle, o erro é de parâmetro.

O fim chega pelo `state_full`: cada controle traz `zero: {estado, guardado}`, com
`estado` em `medindo`, `pronto` (o zero guardado, nesta medida ou numa de antes),
`mexeu` (a medida não guardou nada) ou `parado` (sem zero e sem medida nesta sessão,
ou a medida sem leitura), e `guardado` dizendo se há zero deste controle; `zero` é `null` para o controle sem endereço.

### `gamepad.mask.set` — o modo único, para todos os controles

| Método             | Parâmetros                         | Retorno |
|--------------------|------------------------------------|---------|
| `gamepad.mask.set` | `{flavor: "dualsense" \| "xbox" \| "nintendo", uniq?: str}` | o do `gamepad.emulation.set`; `motivo: "aparelho_nao_vestiu"` quando o modo não subiu |

Desde 27/10/2026 (D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES) o `flavor` é o modo
de TODOS os controles, gravado no perfil ativo pelo mesmo escritor do PS + L3 e do chip
de modo; o `uniq` não escolhe controle. Modo vazio ou desconhecido é erro de parâmetro.
O `gamepad.emulation.set` manual com `flavor` ou `caminho` passa pelo mesmo escritor, e
o par (caminho, máscara) se grava junto. O `controller_masks.json` de antes vira o modo
no boot e sai do disco.

## Perfil com seção `mouse`

O schema de perfil aceita uma seção opcional `mouse`
(`{"enabled": bool, "speed": 1-12, "scroll_speed": 1-5}`) e o campo booleano
`suppress_desktop_emulation`. Nas rotas de ativação em runtime (`profile.switch`,
autoswitch por janela, hotkey PS+D-pad):

- perfil **com** seção `mouse` → as velocidades do perfil entram, e o
  liga/desliga só quando o perfil diz Navegação (`mode.kind: desktop`): fora
  da Navegação quem desliga o mouse é a exclusão mútua do modo, e um perfil sem opinião
  de modo não desliga o mouse da Navegação (29/09/2026). Tudo respeitando o **lock manual**:
  se a usuária mexeu na emulação (mouse
  OU gamepad) manualmente há menos de 30 s, o perfil NÃO toca no estado — não
  sequestra um gamepad virtual ligado na mão. É idempotente (não recria o
  device a cada tick do autoswitch);
- perfil **sem** seção `mouse` → o estado da emulação NÃO é tocado, salvo o
  perfil que diz Navegação: ele liga o mouse com as velocidades da flag de
  sessão, como a entrada pelo chip;
- **a entrada na Navegação** (`desktop.arranjo.apply` e o PS + R3) liga o mouse
  sempre, com as velocidades do perfil ou da flag de sessão
  (D-2909-A-NAVEGACAO-LIGA-O-MOUSE); o «Status do Modo» (`desktop.status.set`)
  o desliga enquanto ela estiver lá, e com `origin: manual` grava o `enabled`
  da seção `mouse` e o `teclado_emulado` no perfil ativo;
- **restore no boot**: a seção `mouse` do
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

Código padrão JSON-RPC 2.0. Convenções do Hefesto - DualSense4Unix:

- `-32001`: daemon não conectado ao controle.
- `-32002`: perfil não encontrado.
- `-32003`: parâmetros inválidos (ex: `params` fora do range do mode).
- `-32004`: controle desconectou durante execução.
