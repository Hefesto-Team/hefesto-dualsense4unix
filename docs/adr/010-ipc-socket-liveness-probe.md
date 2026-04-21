# ADR-010: Socket IPC com probe de vivacidade e isolamento do smoke

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
