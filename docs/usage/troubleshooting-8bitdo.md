# O 8BitDo SN30 Pro

O Hefesto não gerencia o 8BitDo: ele aparece na lista de controles externos
(`hefesto-dualsense4unix controller list --external`) e chega ao jogo como o
controle que já é. Esta página diz qual modo usar e como reconhecer os
problemas conhecidos.

## Qual modo usar

| Modo | Como ligar | O kernel vê | Pelo cabo | Pelo Bluetooth |
|---|---|---|---|---|
| **DirectInput/PS4** | `Start + A` | DualShock 4 (`054c:05c4`, driver `hid-playstation`) | não medido | **o recomendado**: conecta de primeira |
| Switch | `Y + Start` | Pro Controller (`057e:2009`, driver `hid-nintendo`) | **estável**, com giroscópio | cai sob carga |
| X-input | `X + Start` | Xbox 360 (`045e:028e` no cabo, `045e:02e0` no rádio) | não medido | não medido |

Pelo Bluetooth, use o modo DirectInput/PS4. Pelo cabo, o modo Switch é o estável
e é o único com giroscópio. Os combos podem mudar de um modelo de 8BitDo para
outro; o `Start + A` foi conferido no SN30 Pro.

O Hefesto só adota controles Sony com o PID do DualSense e do DualSense Edge
(`0ce6` e `0df2`). No modo DirectInput/PS4 o 8BitDo tem o fabricante da Sony,
mas o PID do DualShock 4, e por isso continua externo.

### O que o modo DirectInput/PS4 custa

- **Não há luz de jogador**: o DualShock 4 só tem a barra de luz.
- **O endereço Bluetooth muda com o modo.** Cada modo é um pareamento, e o
  Hefesto vê os dois como controles diferentes. Se os números saírem trocados,
  use **Reconectar Controles**, na aba Jogar.
- Conectar está medido; horas de uso contínuo neste modo, não.

## Identificar o modo agora

O fabricante e o produto que o controle anuncia mudam com o modo. O que não muda
é o prefixo do endereço (o `E4:17:D8` é da 8BitDo).

```bash
# o dispositivo e o driver (bus 0003 é o cabo, 0005 é o Bluetooth)
for d in /sys/bus/hid/devices/*; do
  printf '%s driver=%s\n' "$(basename "$d")" "$(basename "$(readlink -f "$d/driver")")"
done
# o nome e o endereço de cada um
grep -H . /sys/bus/hid/devices/*/uevent | grep -E 'HID_NAME|HID_UNIQ'
```

## O controle morre pelo Bluetooth no modo Switch

O controle para de responder e o `bluetoothctl` continua dizendo
`Connected: yes`. No diário do kernel aparece, na mesma instância, uma série de
timeouts terminando no limitador do `hid-nintendo`:

```text
nintendo 0005:057E:2009.0014: timeout waiting for input report
nintendo 0005:057E:2009.0014: joycon_enforce_subcmd_rate: exceeded max attempts
```

```bash
journalctl -b -k --no-pager | grep -aE 'nintendo|joycon'
```

Uma linha `exceeded max attempts` sozinha não é a morte; a série é. O
`hefesto-dualsense4unix doctor` faz essa leitura e avisa quando a acha. Fechar
a Steam não resolve (a morte acontece sem ela), e o Hefesto não está no caminho:
o `src/` tem mais de uma centena de linhas sobre controles Nintendo e 8BitDo,
mas as únicas duas escritas em controle externo são a luz de jogador (desligada)
e a ativação do giroscópio, só no Pro Controller original e só pelo cabo.

A saída é o modo DirectInput/PS4 pelo Bluetooth, ou o modo Switch pelo cabo.
Não ponha o `hid_nintendo` na lista negra do kernel: isso mata o controle para
todos os programas.

## O pareamento sumiu sem o Bluetooth travar

`Host is down (112)` repetido no diário do `bluetoothd`, e o controle some da
lista de pareados. Acontece com o controle pareado pelo Bluetooth e em uso pelo
cabo: o BlueZ insiste em procurar o rádio desligado e desiste do controle.
Pareie de novo, ou restaure a cópia com `sudo scripts/bt_bonds_restore.sh
--list` e `--latest` (ele para o Bluetooth por um instante).

## O giroscópio no jogo

O giroscópio do 8BitDo existe no modo Switch e só chega ao jogo com o Steam
Input daquele jogo ligado. O vigia do Steam Input do Hefesto volta a desligá-lo
quando a Steam fecha e a cada 30 minutos. Para manter o giroscópio, desligue o
vigia:

```bash
systemctl --user disable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer
```

A aba Sistema não reclama de um vigia desligado assim. O `install.sh` o religa;
rode-o com `--keep-steam-input` para não religar.

Se o jogo mostrar o 8BitDo como «Xbox», o nome vem da camada acima do kernel
(o Steam Input ou o Proton), e não diz o modo do controle: use os comandos de
«Identificar o modo agora».
