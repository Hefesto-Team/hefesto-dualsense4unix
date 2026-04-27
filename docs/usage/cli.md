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
| `hefesto-dualsense4unix trigger/rumble` (subgrupo `test`) | Efeitos direto no hardware. |
| `hefesto-dualsense4unix daemon start/stop/restart/status/install-service/uninstall-service` | Ciclo do daemon. |
| `hefesto-dualsense4unix emulate xbox360` | Gamepad virtual Xbox360. |
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
- Quando o daemon está offline: aplica direto no hardware. Se
  `--brightness` for fornecido, faz escala linear do RGB como
  aproximação (`100%%` = cor pura, `0%%` = apagado).
- Pós FEAT-LED-BRIGHTNESS-01 (ainda não mergeada na escrita desta
  sprint): o daemon honrará `brightness` nativamente, sem distorcer
  a matiz.

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
- `2` — flag `--from-active` ausente (sem ela a operação é recusada;
  clone por nome arbitrário fica para sprint futura).

## `hefesto-dualsense4unix daemon`

Controle do daemon via `systemd --user` (quando instalado como unit):

```bash
hefesto-dualsense4unix daemon install-service
hefesto-dualsense4unix daemon start            # foreground, sem systemd
hefesto-dualsense4unix daemon stop             # systemctl --user stop hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon restart          # systemctl --user restart hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon status           # systemctl --user status hefesto-dualsense4unix.service
hefesto-dualsense4unix daemon uninstall-service
```

`daemon start` roda o daemon em foreground (útil para debug). Para rodar
como serviço em background, instale a unit e use `start`/`stop`/`restart`
via subcomandos acima — eles despacham `systemctl --user` por baixo.

## `hefesto-dualsense4unix test` (efeitos direto no hardware)

Pulam o daemon: conectam ao DualSense direto. Úteis para troubleshooting.

```bash
hefesto-dualsense4unix test trigger --side right --mode Rigid --params '5,200'
hefesto-dualsense4unix test led --color '#ff0000'
hefesto-dualsense4unix test led --color '#ff0000' --brightness 40
hefesto-dualsense4unix test rumble --weak 128 --strong 64
```

## `hefesto-dualsense4unix emulate`

```bash
hefesto-dualsense4unix emulate xbox360           # cria gamepad virtual Xbox360 via uinput
hefesto-dualsense4unix emulate xbox360 --off
```

## Demais comandos

- `hefesto-dualsense4unix status` — estado do daemon via IPC (fallback local se offline).
- `hefesto-dualsense4unix battery` — percentual de bateria.
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
