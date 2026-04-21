# ADR-004: Daemon como `systemd --user` service

## Contexto
Rodar o daemon como serviço do sistema (`system`) exigiria root e criaria um vetor de privilégio. Rodar manualmente a cada login é frágil. `systemd --user` resolve: auto-start na sessão, acesso ao `DISPLAY` do usuário, sem privilégios elevados.

## Decisão
Unidade única `hefesto.service` (`WantedBy=graphical-session.target`). Instalada por `hefesto daemon install-service` em `~/.config/systemd/user/`.

Revisão SIMPLIFY-UNIT-01 (2026-04-21): a dualidade histórica normal/headless (com `Conflicts=` mútuo) foi eliminada. O Hefesto é inerentemente um daemon desktop com DualSense num ambiente gráfico; variante headless só fazia sentido em laboratório/CI, já coberto por pytest. A flag `--headless` do `daemon start` permanece em tempo de execução (apenas seta `HEFESTO_NO_WINDOW_DETECT=1` para desligar auto-switch X11), mas sem unit file dedicada.

## Consequências
Funciona no login gráfico sem sudo. Distros sem `systemd-logind` (Alpine, Void) não são suportadas — ver ADR-009. Uso via SSH/Big Picture sem sessão gráfica requer ajuste manual do `WantedBy` pelo usuário avançado (fora do happy path).
