# ADR-010: Socket IPC com probe de vivacidade e isolamento do smoke

**Status:** aceito

## Contexto

O daemon expõe IPC via Unix socket em `$XDG_RUNTIME_DIR/hefesto/hefesto.sock`. A versão original fazia `unlink()` cego no `start()` e no `stop()`: se dois processos daemon rodassem simultaneamente com o mesmo path (tipicamente o service systemd + um `./run.sh --smoke` ad-hoc), o segundo apagava o socket do primeiro e ninguém mais conseguia conectar via filesystem. Sintoma observado em 2026-04-21: `systemctl --user is-active hefesto.service` retornava `active` enquanto a GUI mostrava "daemon offline" por horas. Viola meta-regra 9.3 (soberania de subsistema).

## Decisão

1. **Liveness probe no `start()`**: antes de `unlink()`, tentar `AF_UNIX/SOCK_STREAM connect` com timeout 0.1 s no path. Se conecta, levantar `RuntimeError("socket ocupado por outro daemon em <path>")`. Se devolve `ConnectionRefusedError` ou `FileNotFoundError`, tratar como socket-resto e seguir com unlink + listener novo.
2. **Inode sovereign no `stop()`**: registrar `st_ino` do socket criado no `start()`. Em `stop()`, só `unlink()` se o inode atual do path ainda for o registrado. Se outro daemon reciclou o path, apenas logar `ipc_socket_inode_divergente_skip_unlink` — não deletar.
3. **Isolamento do smoke** via env var `HEFESTO_IPC_SOCKET_NAME` (default `hefesto.sock`). `run.sh --smoke` exporta `hefesto-smoke.sock` antes de bootar o daemon ad-hoc. Daemon de produção mantém o default; dois processos nunca mais pisam no mesmo path em uso normal.

## Consequências

(+) Daemon de produção nunca é derrubado silenciosamente por smoke/test runner.
(+) Duas instâncias concorrentes não se destroem — a segunda falha rápido com erro claro.
(+) Test runner fica livre para rodar em paralelo com daemon real sem workaround.
(−) Um probe de 100 ms é somado ao startup. Aceitável — startup já custa > 500 ms por conta do `controller.connect()`.
(−) Mais código a manter (helper `_probe_socket_and_cleanup` + `_socket_inode` tracking). Coberto por 5 testes unitários específicos.

## Nota de verificação — 2026-08-01

O mecanismo continua válido: probe de vivacidade antes do `unlink()`, inode
soberano no `stop()` e isolamento por nome de socket. **O que caducou foram os
três nomes**, todos do layout curto legado — o projeto se chama
`hefesto-dualsense4unix` e nada mais atende por `hefesto` puro.

| na ADR | real, conferido em `utils/xdg_paths.py` |
|---|---|
| `$XDG_RUNTIME_DIR/hefesto/hefesto.sock` | `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock` — diretório de `runtime_dir()`, nome-base de `ipc_socket_name()` |
| variável `HEFESTO_IPC_SOCKET_NAME` | `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME` (constante `IPC_SOCKET_ENV_VAR`) |
| default `hefesto.sock` | `hefesto-dualsense4unix.sock` (constante `IPC_SOCKET_DEFAULT_NAME`) |
| unidade `hefesto.service` | `hefesto-dualsense4unix.service` (constante `SERVICE_NORMAL` em `daemon/service_install.py`) |

Ninguém deve digitar esse caminho: `ipc_socket_path()` é a fonte única e o
`docs/protocol/ipc-unix-socket.md` deriva dela. Quem concatenar a string à mão
erra o modo fake — ver abaixo.

**Uma coisa que a ADR não previa, e é o motivo de o isolamento ter mudado de
forma.** O item 3 descrevia um isolamento MANUAL: o `run.sh --smoke` exportava
o nome do socket antes de subir o daemon ad-hoc. Isso dependia de duas
variáveis andarem em sincronia (`…_FAKE=1` **e** `…_IPC_SOCKET_NAME`), e um
`daemon start` cru só com `FAKE=1` caía no socket de PRODUÇÃO e sequestrava o
daemon real — a janela mostrava um "Conectado Via USB" fantasma vindo do
`FakeController` (BUG-FAKE-SOCKET-SYNC-01). Hoje `ipc_socket_name()` deriva o
socket do próprio switch de fake: com `HEFESTO_DUALSENSE4UNIX_FAKE=1` e sem
override explícito, o nome-base vira `hefesto-dualsense4unix-fake.sock`
sozinho. O override manual continua existindo e tem precedência — só deixou de
ser obrigatório.

O `hefesto-smoke.sock` citado no item 3 não existe mais como nome fixo.
