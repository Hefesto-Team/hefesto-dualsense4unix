# Units systemd de terceiros, copiadas como dublê

Cópias byte a byte de units que vêm de pacotes do sistema, tiradas da máquina
dela em 27/09/2026 (Pop!_OS 24.04, systemd 255.4). Elas são a hospedeira
declarada de `tests/unit/test_bt_sandbox_cobre_o_que_os_ganchos_escrevem.py`:
o sandbox que o nosso drop-in tem de cobrir sai de LER a cópia, e não de uma
tabela digitada nem do systemd de quem roda a suíte — o runner do CI não tem
bluez, e o `systemctl show` de uma unit ausente responde `ProtectSystem=no`.

| arquivo | pacote | licença |
| --- | --- | --- |
| `bluetooth.service` | `bluez` 5.86-0ubuntu0.1~hefesto24.04.4 (`/usr/lib/systemd/system/`) | GPL-2.0-or-later (BlueZ) |

A `bluetooth.service` do `bluez` 5.72-0ubuntu5.5 do Ubuntu 24.04, o que qualquer
Pop!_OS 24.04 sem o backport da casa tem, é idêntica byte a byte a esta
(conferido em 27/09/2026 com `apt-get download`).

Não edite: o valor delas é serem as de verdade. Para atualizar, copie de novo
de `/usr/lib/systemd/system/` e diga a versão aqui. Numa máquina com o bluez
carregado, `test_a_hospedeira_declarada_bate_com_a_maquina` confere a cópia
contra o systemd vivo e reprova quando ela envelhece.
