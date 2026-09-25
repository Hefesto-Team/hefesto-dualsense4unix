# Regras udev de terceiros, copiadas como dublê

Cópias byte a byte de arquivos que vêm de pacotes do sistema, tiradas da
máquina dela em 25/09/2026 (Pop!_OS 24.04, systemd/udev 255.4). Elas servem ao
udev de bolso de
`tests/unit/test_o_fisico_nasce_escondido_em_qualquer_maquina.py`, que ordena a
cadeia pelo nome do arquivo, como o udev ordena, e roda o evento de um hidraw
de DualSense por ela.

| arquivo | pacote | licença |
| --- | --- | --- |
| `60-steam-input.rules` | `steam-devices` 1:1.0.0.85 (Valve) | Expat (MIT) |
| `71-sony-controllers.rules` | `game-devices-udev` 0.25 (codeberg.org/fabiscafe/game-devices-udev, dependência do `pop-desktop`) | MIT |
| `70-uaccess.rules`, `71-seat.rules`, `73-seat-late.rules` | `udev` 255.4 (systemd) | LGPL-2.1-or-later |

Não edite: o valor delas é serem as de verdade. Para atualizar, copie de novo
de `/usr/lib/udev/rules.d/` e diga a versão aqui.
