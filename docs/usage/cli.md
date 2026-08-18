# CLI Hefesto - Dualsense4Unix — referência de subcomandos

Esta é a referência canônica da CLI `hefesto-dualsense4unix` (Typer). Cobre os
subcomandos disponíveis após a sprint **FEAT-CLI-PARITY-01** (paridade
CLI-GUI). Para roteiros de uso (primeiros passos, criar perfil,
integrar mods), veja `quickstart.md`, `creating-profiles.md` e
`integrating-mods.md`.

Complemento de scripts: tab-completion funciona em zsh e bash via
`hefesto-dualsense4unix --install-completion <shell>` (herdado do Typer).

---

## Resumo

| Comando | Descrição |
|---|---|
| `hefesto-dualsense4unix version` | Versão instalada. |
| `hefesto-dualsense4unix status` | Estado do daemon e do controle. |
| `hefesto-dualsense4unix battery` | Percentual de bateria. |
| `hefesto-dualsense4unix led --color ...` | Cor da lightbar (com `--brightness` opcional). |
| `hefesto-dualsense4unix mouse on/off/status` | Emulação de mouse via daemon. |
| `hefesto-dualsense4unix profile list/show/activate/create/delete/apply/save` | Gerência de perfis. |
| `hefesto-dualsense4unix profile historico/restore` | Versões guardadas de um perfil — e a volta. |
| `hefesto-dualsense4unix trigger/rumble` (subgrupo `test`) | Efeitos direto no hardware. |
| `hefesto-dualsense4unix daemon start/stop/restart/status/pause/resume/enable/disable/install-service/uninstall-service` | Ciclo do daemon. |
| `hefesto-dualsense4unix gamepad on/off/status` | Controle virtual (substituiu o antigo `emulate xbox360`). |
| `hefesto-dualsense4unix mic on/off/status/bt/bt-status` | Microfone do controle — no cabo (política) e por Bluetooth (ponte). |
| `hefesto-dualsense4unix speaker status/volume/mute/unmute/release` | Alto-falante e fone do controle — inclusive a DEVOLUÇÃO da posse. |
| `hefesto-dualsense4unix tui` / `hefesto-dualsense4unix tray` | Interfaces alternativas. |

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

> **Falha conhecida, não corrigida: as duas pontas usam unidades
> diferentes.** A CLI aceita `--brightness` em 0–100 e manda esse número
> cru no `led.set`; o handler do daemon valida `0.0 ≤ brightness ≤ 1.0` e
> recusa qualquer coisa acima de 1. Efeito prático com o daemon rodando:
> `--brightness 50` faz a chamada IPC falhar e o comando cai em silêncio
> no caminho de hardware direto (onde a conversão para 0–1 acontece, e o
> resultado sai certo); `--brightness 1` é aceito pelo daemon como 100%,
> não como 1%. Medido em 25/07/2026 lendo `cli/cmd_test.py` e
> `daemon/ipc_handlers.py`. Enquanto isso não for arrumado no código, a
> luminosidade só é confiável com o daemon **parado**.

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
hefesto-dualsense4unix profile create <nome> [--match-class X] [--match-regex ...] [--fallback]
hefesto-dualsense4unix profile delete <nome> --yes

# Aplicação
hefesto-dualsense4unix profile activate <nome>              # ativa + grava marker
hefesto-dualsense4unix profile apply --file draft.json      # valida, salva e ativa
hefesto-dualsense4unix profile apply --file draft.json --no-save   # ativa sem persistir (exige --name ja em disco)

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

## `hefesto-dualsense4unix test` (efeitos direto no hardware)

Pulam o daemon: conectam ao DualSense direto. Úteis para troubleshooting.

```bash
hefesto-dualsense4unix test trigger --side right --mode Rigid --params '5,200'
hefesto-dualsense4unix test led --color '#ff0000'
hefesto-dualsense4unix test led --color '#ff0000' --brightness 40
hefesto-dualsense4unix test rumble --weak 128 --strong 64
```

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
- `hefesto-dualsense4unix mic on|off|status|bt|bt-status` — microfone embutido
  do DualSense. `on`/`off`/`status` são **política do WirePlumber** e valem no
  cabo, onde o mic é um dispositivo de áudio USB comum. `bt` é outra coisa: sobe
  a **ponte** que decodifica o Opus tunelado nos relatórios HID e publica o
  microfone no PipeWire (Ctrl-C encerra); `bt-status` só diagnostica as
  pré-condições, sem mexer em nada. Ver [`bluetooth.md`](bluetooth.md).
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
  reporta), e por Bluetooth não existe fluxo de áudio de saída nenhum.
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
- `hefesto-dualsense4unix controller list|target` — mira as ações num controle específico.
- `hefesto-dualsense4unix plugin list|reload` — plugins do daemon.
- `hefesto-dualsense4unix tui` — abre a TUI Textual.
- `hefesto-dualsense4unix tray` — abre o tray GTK3 (extra `[tray]`).
- `hefesto-dualsense4unix version` — versão instalada.

---

## Convenções

- Todas as mensagens em PT-BR.
- Erros de IPC mostram causa curta, sem traceback (exit codes documentados por subcomando).
- Saída colorida via `rich`; suprima com `--no-color` global do Typer
  quando redirecionar para pipe.
- `--help` funciona em todos os níveis: `hefesto-dualsense4unix --help`, `hefesto-dualsense4unix mouse --help`, etc.
