# Protocolo IPC — Unix Socket JSON-RPC 2.0

## Endpoint

`$XDG_RUNTIME_DIR/hefesto.sock` (Unix socket, stream). Permissão `0600` (só o dono).

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

## Erros

Código padrão JSON-RPC 2.0. Convenções do Hefesto:

- `-32001`: daemon não conectado ao controle.
- `-32002`: perfil não encontrado.
- `-32003`: parâmetros inválidos (ex: `params` fora do range do mode).
- `-32004`: controle desconectou durante execução.
