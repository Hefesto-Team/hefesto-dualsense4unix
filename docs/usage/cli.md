# CLI Hefesto - Dualsense4Unix — referência de subcomandos

Esta é a referência canônica da CLI `hefesto-dualsense4unix` (Typer). Cobre os
subcomandos disponíveis após a sprint **FEAT-CLI-PARITY-01** (paridade
CLI-GUI). Para roteiros de uso (primeiros passos, criar perfil,
integrar mods), veja `quickstart.md`, `creating-profiles.md` e
`integrating-mods.md`.

Complemento de scripts: tab-completion funciona em zsh e bash via
`hefesto-dualsense4unix --install-completion <shell>` (herdado do Typer).

> **Escopo.** Esta página cobre o **produto**. A CLI também traz
> **instrumentos de medição** — bancada, não cura: `test`, `lightbar-reset` e
> `player-leds`. Eles não persistem nada, ninguém os chama sozinho, e têm
> **seção própria no fim**. Rodar bancada não conserta o produto: se o efeito
> tem de valer para quem joga, ele vem de perfil, da janela ou dos comandos
> desta parte de cima.

---

## Resumo

| Comando | Descrição |
|---|---|
| `hefesto-dualsense4unix version` | Versão instalada. |
| `hefesto-dualsense4unix status` | Estado do daemon e do controle. |
| `hefesto-dualsense4unix doctor` | Diagnóstico ponta a ponta (`--fix`, `--fix-safe`, `--quiet`, `--perfis`). |
| `hefesto-dualsense4unix battery` | Percentual de bateria. |
| `hefesto-dualsense4unix led --color ...` | Cor da lightbar (com `--brightness` opcional). |
| `hefesto-dualsense4unix mouse on/off/status` | Emulação de mouse via daemon. |
| `hefesto-dualsense4unix profile list/show/activate/create/delete/apply/save` | Gerência de perfis. |
| `hefesto-dualsense4unix profile historico/restore` | Versões guardadas de um perfil — e a volta. |
| `hefesto-dualsense4unix daemon start/stop/restart/status/pause/resume/enable/disable/install-service/uninstall-service` | Ciclo do daemon. |
| `hefesto-dualsense4unix gamepad on/off/status` | Controle virtual (substituiu o antigo `emulate xbox360`). |
| `hefesto-dualsense4unix gamepad steam-input list/remove` | Exceção do Steam Input — a **saída** dela pela linha de comando (marcar é na janela). |
| `hefesto-dualsense4unix native on/off/status` | Modo Nativo — solta o controle para o jogo. |
| `hefesto-dualsense4unix coop on/status` | Co-op local (`coop off` recusa e explica). |
| `hefesto-dualsense4unix controller list/target` | Mira as ações de output num controle específico. |
| `hefesto-dualsense4unix plugin list/reload` | Plugins do daemon. |
| `hefesto-dualsense4unix mic on/off/status/promote/demote/mute/unmute/release/bt/bt-status` | Microfone do controle — política do sistema, mudo de firmware e a ponte por Bluetooth. |
| `hefesto-dualsense4unix speaker status/volume/mute/unmute/release` | Alto-falante e fone do controle — inclusive a DEVOLUÇÃO da posse. |
| `hefesto-dualsense4unix tui` / `hefesto-dualsense4unix tray` | Interfaces alternativas. |

Fora da tabela porque **não são produto** — `test trigger/led/rumble`,
`lightbar-reset` e `player-leds` são bancada, e estão na
[seção dos instrumentos](#instrumentos-de-medição--não-são-cura).

---

## `hefesto-dualsense4unix led`

Aplica cor (e opcionalmente luminosidade) na lightbar.

```bash
hefesto-dualsense4unix led --color '#ff8800'
hefesto-dualsense4unix led --color '#ff8800' --brightness 50
hefesto-dualsense4unix led --color '255,136,0'          # CSV também aceito
```

- Quando o daemon está rodando: envia `led.set` via IPC. Perfis e
  autoswitch continuam funcionando em paralelo.
- Quando o daemon está offline: aplica direto no hardware.
- `--brightness` é um multiplicador do RGB (`100%` = cor pura, `0%` =
  apagado). Não existe canal de luminosidade separado no hardware nesta
  implementação: o nó `brightness` do LED multicolor fica fixo em 255 e
  quem carrega o nível é a própria cor. O handler `led.set` do daemon
  faz exatamente a mesma escala linear que o caminho offline.
- A CLI fala porcentagem (0–100) com quem usa e converte para fração (0.0–1.0)
  antes de mandar o `led.set`, que é o contrato do daemon: `--brightness 1`
  acende 1%, com o daemon rodando ou parado. As duas pontas estão travadas por
  `tests/unit/test_cli_led_brightness.py`
  (`test_led_brightness_1_por_cento_nao_vira_100`) desde 25/07/2026.

Exit codes:

- `0` — sucesso.
- Outro — erro de parsing do RGB ou hardware indisponível.

## `hefesto-dualsense4unix mouse`

Controla a emulação de mouse+teclado (FEAT-MOUSE-01). Tudo via IPC.

```bash
hefesto-dualsense4unix mouse on                             # speed/scroll padrão do daemon
hefesto-dualsense4unix mouse on --speed 8 --scroll-speed 3
hefesto-dualsense4unix mouse off
hefesto-dualsense4unix mouse status
hefesto-dualsense4unix mouse status --json                  # para scripts
```

Flags:

- `--speed INT` (1-12) — velocidade do cursor.
- `--scroll-speed INT` (1-5) — velocidade de scroll.

Exit codes:

- `0` — sucesso.
- `1` — daemon respondeu sem habilitar (uinput indisponível?) OU
  estado não consultável em `status`.
- `2` — daemon recusou chamada (parâmetros inválidos, estado
  incorreto).
- `3` — daemon offline (socket IPC inacessível).

Saída `--json`:

```json
{"enabled": true, "speed": 8, "scroll_speed": 3}
```

## `hefesto-dualsense4unix profile`

Gerência de perfis. Mix de operações de disco e IPC.

```bash
# Leitura / listagem
hefesto-dualsense4unix profile list
hefesto-dualsense4unix profile show <nome>

# Mutação
hefesto-dualsense4unix profile create <nome> [--match-class X] [--match-exe X] [--match-regex ...] [--priority N] [--fallback]
hefesto-dualsense4unix profile create <nome> --manual        # nunca ativa sozinho: só pela janela ou pelo activate
hefesto-dualsense4unix profile create <nome> --force         # `--force` existe em create, apply e save
hefesto-dualsense4unix profile delete <nome> --yes

# Aplicação
hefesto-dualsense4unix profile activate <nome>              # ativa + grava marker
hefesto-dualsense4unix profile apply --file draft.json      # valida, salva e ativa
hefesto-dualsense4unix profile apply --file draft.json --no-save   # ativa sem persistir (exige o mesmo `name` ja em disco)

# Snapshot
hefesto-dualsense4unix profile save <novo_nome> --from-active     # clona o perfil ativo

# Histórico (automático, uma cópia por gravação)
hefesto-dualsense4unix profile historico <nome>                   # o que este perfil ja foi
hefesto-dualsense4unix profile restore <nome>                     # volta a versao ANTERIOR a ultima gravacao
hefesto-dualsense4unix profile restore <nome> --em <carimbo>      # volta a uma versao especifica
```

### `profile apply --file`

Fluxo:

1. Lê o JSON do `--file`. Erros de I/O ou parse → exit `1`.
2. Valida via schema pydantic de `Profile`. Falha → exit `1` com detalhes.
3. Por padrão (`--save`), grava no diretório XDG (`~/.config/hefesto-dualsense4unix/profiles/<name>.json`).
4. Chama `profile.switch` via IPC. Se daemon offline ou recusar, grava
   o marker local (`active_profile.txt`) para aplicar na próxima
   inicialização do daemon.

Use `--no-save` apenas quando o perfil `name` já está presente no XDG
e você só quer forçar reativação.

### `profile save --from-active`

Clona o perfil marcado como ativo (`active_profile.txt`) para um novo
nome. Útil para snapshots antes de experimentar mudanças:

```bash
hefesto-dualsense4unix profile save backup_pre_exp --from-active
# edite o perfil ativo à vontade...
hefesto-dualsense4unix profile activate backup_pre_exp   # volta ao snapshot se der ruim
```

Exit codes:

- `0` — clone salvo com sucesso.
- `1` — nenhum perfil ativo marcado OU perfil ativo ausente do disco.
- `2` — flag `--from-active` ausente. Sem ela a operação é recusada: clonar
  um perfil por nome arbitrário não está implementado, e não há trabalho em
  andamento para isso.

### `profile historico` e `profile restore` (a volta de uma gravação)

Diferente do `profile save --from-active`, que é um snapshot que **você** pede:
o histórico é **automático**. Desde a `PERFIL-SEM-RASTRO-01`, toda gravação de
perfil copia a versão **anterior** para
`~/.config/hefesto-dualsense4unix/profiles/.historico/<slug>/`, guardando as
**dez** mais recentes. É a resposta para *"o que este perfil era ontem?"* e para
*"desfaça o que a janela acabou de fazer com meu perfil"*.

```bash
hefesto-dualsense4unix profile historico sackboy_nativo
hefesto-dualsense4unix profile restore sackboy_nativo
hefesto-dualsense4unix profile restore sackboy_nativo --em 20260805T031500_123456.json
```

O `historico` recebe **nome ou slug** e imprime uma tabela com *Quando*, *Match*,
*Prioridade* e *Arquivo* — a mais recente por último. A coluna *Match* é o que
importa quando um perfil de jogo vira `any` sozinho. Uma versão que não valida
contra o schema aparece como **ilegível** em vez de sumir da lista: é
justamente ela o retrato da corrupção.

O `restore` **sem `--em` volta à mais recente**, que é a versão de antes da
última gravação. Com `--em`, recebe o carimbo da coluna *Arquivo*. A versão que
está em disco agora é arquivada **antes** de ser substituída — restaurar por
engano também tem volta —, e os bytes voltam **como estavam**, sem
reserialização: um instrumento de perícia que altera a prova não é instrumento.

Exit codes do `restore`:

- `0` — perfil restaurado (imprime o arquivo e o carimbo da versão usada).
- `1` — não há histórico para esse perfil, o carimbo não existe, **ou** a versão
  guardada não valida contra o schema (lixo guardado não volta ao disco).

Notas:

- **o histórico nasce na PRÓXIMA vez que o perfil for salvo.** Um perfil que
  nunca foi regravado desde a instalação desta versão não tem versão nenhuma
  guardada, e o `historico` diz isso;
- **`profile delete` também arquiva** antes de apagar — apagar é a gravação mais
  destrutiva de todas;
- o `.historico/` fica **dentro** de `profiles/` de propósito: quem faz backup
  do `~/.config` leva o histórico junto. Ele é invisível às varreduras de perfil,
  que são todas não recursivas;
- o arquivamento é *best-effort*: disco cheio ou permissão negada **não impedem
  você de salvar o perfil**. A falha vira `profile_backup_failed` no journal, e a
  linha `profile_salvo` registra `backup=None` em vez de mentir.

## `hefesto-dualsense4unix daemon`

Controle do daemon via `systemd --user` (quando instalado como unit):

```bash
hefesto-dualsense4unix daemon install-service
hefesto-dualsense4unix daemon start            # foreground, sem systemd
hefesto-dualsense4unix daemon stop             # systemctl --user stop hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon restart          # systemctl --user restart hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon status           # systemctl --user status hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon pause            # para o despacho de input; o daemon segue vivo
hefesto-dualsense4unix daemon resume           # retoma o despacho
hefesto-dualsense4unix daemon disable          # para o daemon e desliga o auto-start
hefesto-dualsense4unix daemon enable           # religa o auto-start e inicia
hefesto-dualsense4unix daemon uninstall-service
```

`daemon start` roda o daemon em foreground (útil para debug). Para rodar
como serviço em background, instale a unit e use `start`/`stop`/`restart`
via subcomandos acima — eles despacham `systemctl --user` por baixo.

`pause`/`resume` falam por IPC e exigem o daemon rodando (saem com código
`1` se ele estiver offline). `disable`/`enable` mexem na unit do systemd.

Não existe `daemon reload` na linha de comando. O que existe é o método
IPC `daemon.reload`, que aceita `config_overrides` com um subconjunto dos
campos de `DaemonConfig` — ver a seção de configuração em
[`hotkeys.md`](hotkeys.md).

## `hefesto-dualsense4unix gamepad` (o controle virtual)

Substituiu o antigo `emulate xbox360`, que subia um processo avulso e abria um
**segundo** leitor do mesmo controle (double input). Agora quem cria o controle
virtual é o daemon:

```bash
hefesto-dualsense4unix gamepad on                     # máscara padrão
hefesto-dualsense4unix gamepad on --flavor xbox       # o jogo vê um Xbox
hefesto-dualsense4unix gamepad on --flavor dualsense  # o jogo vê um DualSense
hefesto-dualsense4unix gamepad off
hefesto-dualsense4unix gamepad status
```

### `gamepad steam-input` — a exceção do Steam Input

Os jogos em que a Steam entrega o controle, e por isso o jogador vê os controles
**dobrados**. Um jogo marcado tem os controles físicos escondidos dele.

**São duas ações, não três: `list` e `remove`.** Não existe
`steam-input add` — **marcar é na janela**, pelo botão *"Este jogo não
funciona"* ou pela caixinha do editor de perfil (aba **Perfis**, desde
07/08/2026). A linha de comando é a **porta de saída**: a allowlist é um arquivo
de appids, e sem `remove` desmarcar exigia editar
`~/.config/hefesto-dualsense4unix/steam_input_apps.txt` à mão.

```bash
hefesto-dualsense4unix gamepad steam-input list                    # os jogos marcados, pelo nome
hefesto-dualsense4unix gamepad steam-input remove 2111190          # por appid
hefesto-dualsense4unix gamepad steam-input remove 'mullet'         # ou por parte do nome
```

O nome vem do `appmanifest_<appid>.acf` da Steam (leitura pura, sem rede). Jogo
desinstalado não tem manifest: a linha diz **"(não instalado)"** em vez de
inventar nome. Ver [`jogos-e-mascaras.md`](jogos-e-mascaras.md).

## Demais comandos

- `hefesto-dualsense4unix status` — estado do daemon via IPC (fallback local se offline).
- `hefesto-dualsense4unix doctor` — diagnóstico ponta a ponta (`--fix`,
  `--fix-safe`, `--quiet`). O bloco **perfis (coerência entre eles)** sai junto,
  mas **não** muda o código de saída aqui.
- `hefesto-dualsense4unix doctor --perfis` — **só** a coerência dos perfis entre
  si: sem `doctor.sh`, sem diagnóstico de storm e sem IPC. É o caminho rápido
  para responder *"meus perfis estão sãos?"* — read-only, não toca em arquivo
  nenhum. Compara os perfis **uns com os outros** e acusa catch-all vencendo
  perfil de jogo, catch-all com cara de jogo, prioridades empatadas, prioridade
  fora da faixa e catch-all demais. **Sai com código `1` quando há achado
  grave** e `0` quando não há — é o único bloco do `doctor` feito para virar
  portão. Ele **avisa e não corrige**: os seus arquivos de perfil não são
  reescritos por este comando.
- `hefesto-dualsense4unix battery` — percentual de bateria.
- `hefesto-dualsense4unix mic <ação>` — microfone embutido do DualSense. São
  **dez ações em quatro grupos**, e eles respondem perguntas diferentes:
  - **política do WirePlumber** (`on` · `off` · `status`) — valem no cabo, onde
    o mic é um dispositivo de áudio USB comum;
  - **quem é o microfone padrão do sistema** (`promote` · `demote`) — `promote`
    eleva o mic do controle a entrada padrão; `demote` devolve a política de
    fábrica, que rebaixa a prioridade dele para não ser eleito sozinho;
  - **mudo do FIRMWARE do controle** (`mute` · `unmute` · `release`) — o mesmo
    estado que o botão físico alterna e que acende o LED. Os três são pedidos
    **diferentes**: `unmute` não é `release`. **`release` devolve a posse** — e
    o preço é que, enquanto ela não voltar a nós, o botão do controle não
    responde;
  - **a ponte por Bluetooth** (`bt` · `bt-status`) — `bt` sobe a ponte que
    decodifica o Opus tunelado nos relatórios HID e publica o microfone no
    PipeWire (Ctrl-C encerra); `bt-status` só diagnostica as pré-condições, sem
    mexer em nada. Ver [`bluetooth.md`](bluetooth.md).

  Com mais de um controle na mesa, `--uniq <MAC normalizado>` escolhe qual deles
  recebe `mute`/`unmute`/`release`; sem a opção, vale o primário.
- `hefesto-dualsense4unix speaker status|volume <0-100>|mute|unmute|release` —
  alto-falante **e fone** do controle (é um volume só: o mesmo valor vai nos dois
  bytes). Exige o daemon. O volume mora no firmware e o controle **não o
  devolve**: a única forma de saber o valor é termos sido nós a mandá-lo, e por
  isso a primeira escrita assume a posse — daí em diante o hefesto manda o volume
  em todo report. `speaker release` é a saída, o irmão do `mic release`: devolve
  o CONTROLE, não o valor (o firmware fica com o último número que mandamos até o
  controle desconectar). `speaker mute` exige um volume conhecido — mudo como
  primeira escrita trancaria o alto-falante em zero e o próprio mudo não o
  soltaria. Se nenhum som sair mesmo com volume alto, o problema é a outra
  camada: o sink do controle no PipeWire pode estar mudo (`scripts/doctor.sh`
  reporta), e por Bluetooth não existe fluxo de áudio de saída nenhum. Também
  aceita `--uniq <MAC normalizado>` para mirar um controle na mesa cheia.
- `hefesto-dualsense4unix native on|off|status` — Modo Nativo (solta o controle para o jogo).
- `hefesto-dualsense4unix coop on|status` — co-op local (cada controle = um
  jogador). O `on` reconcilia os jogadores agora; o `status` conta quantos há.
  **`coop off` não desliga mais** (06/08/2026): ele explica por quê e sai com
  código 2. Cada controle conectado é um jogador, sempre — quem quer um controle
  de reserva o deixa desconectado. Nos jogos com exceção de Steam Input o co-op
  **continua de pé**: desde 09/08/2026 a exceção esconde o controle físico e
  mantém os virtuais, então o jogador 2 não cai.

  > **NOTA DATADA — 06/08/2026: "cada controle = um jogador" vale para
  > DualSense.** A frase fica registrada porque decisão medida não se apaga.
  > **GRAU: MEDIDO** em 06/08/2026 às 22h40, com um DualSense, um Nintendo Pro e
  > um 8BitDo ligados: `coop status` respondeu **"jogadores ativos: 1"** e
  > `controller list` mostrou **um** controle. O número que o `status` conta vem
  > só dos DualSense descobertos; controle de outra marca aparece em
  > `controller list --external`, recebe número e luz, e **não entra nessa
  > conta**. Medição inteira na
  > [LUGAR-À-MESA-01](../process/sprints/2026-08-06-LUGAR-A-MESA-01-tres-controles-ligados-e-um-jogador-so.md).
- `hefesto-dualsense4unix controller list|target` — mira as ações de output num
  controle específico. `target <n|all>` recebe o número da listagem (ou `all`,
  broadcast); `list` aceita `--json` (scripts) e `--external`, que junta o
  inventário read-only dos gamepads de **outras marcas**. Eles não entram em
  `jogadores pelo Hefesto`, mas **entram** em `controles na mesa` — as duas
  contagens que o `coop status` imprime (`cli/cmd_coop.py:135-138`).
- `hefesto-dualsense4unix plugin list|reload` — plugins do daemon.
- `hefesto-dualsense4unix tui` — abre a TUI Textual.
- `hefesto-dualsense4unix tray` — abre o tray GTK3 (extra `[tray]`).
- `hefesto-dualsense4unix version` — versão instalada.

---

## Instrumentos de medição — não são cura

Estes **não são feature de produto**: são bancada. Não persistem nada, não
entram em perfil, e **nenhum caminho automático os chama** — quem os chama é
quem está medindo.

### `hefesto-dualsense4unix test` (exercita o efeito uma vez)

Serve para responder *"o aparelho aceita isto?"* — não para deixar o efeito de
pé: nada disso vira perfil, e a próxima troca de perfil manda os efeitos dela
por cima.

**As três ações tentam o daemon primeiro** (`trigger.set`, `led.set`,
`rumble.set` por IPC) e só caem no hardware direto quando ele não atende —
FEAT-CLI-IPC-FIRST-01, para não abrir um **segundo** leitor do mesmo
`/dev/hidraw` e disputá-lo com o daemon. A exceção é o `--raw`, que não tem
contrato IPC.

```bash
hefesto-dualsense4unix test trigger --side right --mode Rigid --params '5,200'
hefesto-dualsense4unix test trigger --side left --mode 2 --params '0,9,7,7,10,0,0' --raw
hefesto-dualsense4unix test led --color '#ff0000'
hefesto-dualsense4unix test led --color '#ff0000' --brightness 40
hefesto-dualsense4unix test rumble --weak 128 --strong 64
```

- `trigger` exige `--side left|right` e `--mode`; `--params` é CSV de inteiros.
- **`--raw` é recusado com o daemon vivo** (sai com código `1`), e a recusa é a
  entrega: o report OUT
  do DualSense é **atômico** (gatilho, vibração e luz saem no mesmo buffer),
  então o primeiro write do daemon depois do seu leva o seu efeito cru junto —
  e nada avisa quando isso acontece. Antes de 01/08/2026 este comando imprimia
  *"trigger aplicado"* mesmo com o daemon sobrescrevendo o efeito em menos de
  0,5 s: o instrumento brigando com o produto e anunciando sucesso. Para bancada
  crua: `systemctl --user stop hefesto-dualsense4unix`, rode, e religue.
- `test led` faz o mesmo que o `led` de cima, inclusive o `--brightness` 0–100;
  `test rumble` aceita `--weak` e `--strong` em 0–255.

### Os dois instrumentos de eliminação

- `hefesto-dualsense4unix lightbar-reset` — manda o report `0x31` com
  `valid_flag1 = 0x08` ("Reset LED state"), que devolve ao host o claim da
  lightbar. Instrumento da LIGHTBAR-MEDIR-O-0X08-01 (08/08/2026).
- `hefesto-dualsense4unix player-leds` — liga/desliga a **escrita** do LED de
  JOGADOR, para isolar se é ela que trava a barra. Instrumento da
  LIGHTBAR-ISOLAR-OS-PLAYERS-01.

O protocolo por trás deles está em
[`../protocol/ipc-unix-socket.md`](../protocol/ipc-unix-socket.md) e na
[canônica do DualSense](../protocol/dualsense-referencia-canonica.md).

---

## Convenções

- Todas as mensagens em PT-BR.
- Erros de IPC mostram causa curta, sem traceback (exit codes documentados por subcomando).
- Saída colorida via `rich`; suprima com `--no-color` global do Typer
  quando redirecionar para pipe.
- `--help` funciona em todos os níveis: `hefesto-dualsense4unix --help`, `hefesto-dualsense4unix mouse --help`, etc.
