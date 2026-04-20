# ADR-004: Daemon como `systemd --user` service

## Contexto
Rodar o daemon como serviço do sistema (`system`) exigiria root e criaria um vetor de privilégio. Rodar manualmente a cada login é frágil. `systemd --user` resolve: auto-start na sessão, acesso ao `DISPLAY` do usuário, sem privilégios elevados.

## Decisão
Duas units mutuamente exclusivas (via `Conflicts=`):
- `hefesto.service`: `WantedBy=graphical-session.target`, default.
- `hefesto-headless.service`: `WantedBy=default.target`, desliga auto-switch X11 (env `HEFESTO_NO_WINDOW_DETECT=1`).

`hefesto daemon install-service [--headless]` desabilita a oposta antes de habilitar a escolhida.

## Consequências
Funciona no login gráfico sem sudo. Headless cobre SSH + Steam Big Picture remoto. Distros sem `systemd-logind` (Alpine, Void) não são suportadas — ver ADR-009.
