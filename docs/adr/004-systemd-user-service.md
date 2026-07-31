# ADR-004: Daemon como `systemd --user` service

**Status:** aceito

## Contexto
Rodar o daemon como serviço do sistema (`system`) exigiria root e criaria um vetor de privilégio. Rodar manualmente a cada login é frágil. `systemd --user` resolve: auto-start na sessão, acesso ao `DISPLAY` do usuário, sem privilégios elevados.

## Decisão
Unidade única `hefesto.service` (`WantedBy=graphical-session.target`). Instalada por `hefesto daemon install-service` em `~/.config/systemd/user/`.

Revisão SIMPLIFY-UNIT-01 (2026-04-21): a dualidade histórica normal/headless (com `Conflicts=` mútuo) foi eliminada. O Hefesto é inerentemente um daemon desktop com DualSense num ambiente gráfico; variante headless só fazia sentido em laboratório/CI, já coberto por pytest. A flag `--headless` do `daemon start` permanece em tempo de execução (apenas seta `HEFESTO_NO_WINDOW_DETECT=1` para desligar auto-switch X11), mas sem unit file dedicada.

## Consequências
Funciona no login gráfico sem sudo. Distros sem `systemd-logind` (Alpine, Void) não são suportadas — ver ADR-009. Uso via SSH/Big Picture sem sessão gráfica requer ajuste manual do `WantedBy` pelo usuário avançado (fora do happy path).

## Nota de verificação — 2026-07-31

A decisão continua válida: o daemon é `systemd --user`, unidade única, sem
variante headless. **Os nomes citados acima são todos do layout curto legado** e
não colam num terminal — o projeto foi renomeado para
`hefesto-dualsense4unix` e nada mais atende por `hefesto` puro:

| na ADR | real, conferido no código |
|---|---|
| unidade `hefesto.service` | `hefesto-dualsense4unix.service` (`assets/hefesto-dualsense4unix.service`; constante `SERVICE_NORMAL` em `daemon/service_install.py`) |
| `hefesto daemon install-service` | `hefesto-dualsense4unix daemon install-service` (`cli/app.py`) |
| `HEFESTO_NO_WINDOW_DETECT=1` | `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1` (lida em `profiles/autoswitch.py`; é o que a flag `--headless` seta em `cli/app.py`) |

Uma âncora também mudou, e o motivo está registrado no próprio unit
(BUG-DEB-AUTOSTART-WANTEDBY-DEFAULT-01): o `[Install]` real é
`WantedBy=default.target`, não `graphical-session.target`. O daemon fala com
`/dev/hidraw` e evdev, não com o servidor gráfico — ancorar em `default.target`
dá autostart em qualquer DE e mata a corrida entre o login e a ativação do
`graphical-session.target`. O `After=` preserva a ordem citando os dois. Com
isso, a ressalva final sobre "ajuste manual do `WantedBy` para uso sem sessão
gráfica" perdeu o objeto: o default já cobre esse caso.

O que a ADR diz sobre `--headless` continua verdade: a flag existe em tempo de
execução e só seta a variavel de ambiente — não há unit file dedicada.
