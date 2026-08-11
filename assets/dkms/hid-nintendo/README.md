# hefesto-hid-nintendo (DKMS) — Onda T + clone USB

Módulo `hid-nintendo` patchado para curar duas mortes de probe distintas:

- **por Bluetooth** (Onda T), sob interferência 2.4GHz — medida 3× nesta
  máquina: `-110` no `joycon_read_info`, HID não re-proba, controle some até
  power-cycle;
- **por USB** (25/07), nos controles que CLONAM os IDs do Pro Controller — o
  8BitDo Pro em modo Switch se apresenta com o mesmo `057E:2009` e o mesmo
  serial `000000000001` do genuíno, e morre no mesmo `-110`.

## Proveniência

- `hid-nintendo.c` = **vanilla v7.0.11** (idêntico byte a byte ao source do
  kernel `7.0.11-76070011-generic` do Pop!_OS, commit pop-os/linux em
  `patch/BASELINE`) **+ os `patch/000N-*.patch` aplicados NA ORDEM**. Nada
  além dos patches — invariante verificável (revertendo na ordem INVERSA,
  `0003` → `0002` → `0001`) reproduz exatamente o `SHA256_VANILLA_C` do
  `patch/BASELINE`. Comando pronto na seção **Upstream**.
- `hid-ids.h` = header local intocado do mesmo commit (único include local).
- Código C em inglês (convenção do subsistema HID, visando o upstream).

## O que os patches mudam (5 alvos, detalhe nos próprios patches)

- **[D] Registrar LEDs mesmo com SET inicial falho** (`0002-*.patch`, opt-in
  `register_leds_on_set_failure`): em BT congestionado o primeiro set de
  player LEDs dá `-110` e o vanilla PULA o registro — o controle fica sem
  LEDs de player pela conexão inteira (medido 21/07 com 4 controles BT).
  Registrar é local; a próxima escrita de brightness (atribuição de player
  do daemon) cura pelo link já recuperado. Default `N` == vanilla.

- **[B] Não transmitir após esgotar o rate-limit**: hoje o driver esgota as 25
  tentativas ("exceeded max attempts") e transmite mesmo assim, sem ritmo —
  exatamente o que o comentário do próprio driver diz que derruba o link BT.
  Com o patch, o TX é suprimido (o chamador vê o mesmo `-ETIMEDOUT` de sempre).
- **[A] Retry de probe BT** (opt-in): laço com backoff exponencial em volta do
  `joycon_init()` no probe, só bluetooth. Default `bt_probe_retries=0` ==
  comportamento vanilla; a cura entra via
  `assets/modprobe.d/hefesto-hid-nintendo.conf` (`bt_probe_retries=3`).
- **[C] Module params** com defaults idênticos aos valores hardcoded
  (250/25/2/2000/0) — tuning de campo ao vivo em
  `/sys/module/hid_nintendo/parameters/` (presença do diretório = marcador
  "patch carregado" para o doctor; o in-tree tem zero params).

- **[E] Clone USB do Pro Controller** (`0003-*.patch`, 25/07). Ver a seção
  dedicada abaixo.

## [E] O clone USB `057E:2009` — o que morre e por quê

**Leia esta seção como o estado SEM o patch `0003`.** Ela descreve o que foi
medido em 25/07, com o módulo vanilla, e é o que a cura veio curar. **Com o
patch no ar — o caso desta máquina desde então — nada disto acontece:** o clone
proba inteiro pelo cabo, medido em 11/08. Ver a seção de instalação, abaixo.

### O sintoma medido

Dois "Pro Controller" no USB, indistinguíveis por ID (mesmo VID:PID, mesmo
serial `000000000001`, mesmo `HID_NAME`); só o `bcdDevice` difere — `0210` no
Nintendo genuíno, `0200` no 8BitDo. O genuíno conclui a probe em ~1 s. O clone:

```
nintendo 0003:057E:2009.0001: Failed to get joycon info; ret=-110
nintendo 0003:057E:2009.0001: Failed to retrieve controller info; ret=-110
nintendo 0003:057E:2009.0001: Failed to initialize controller; ret=-110
nintendo 0003:057E:2009.0001: probe - fail = -110
```

O device fica **sem driver nenhum**: `/sys/bus/hid/devices/…0001/` tem só
`modalias power report_descriptor subsystem uevent` — nada de hidraw, input,
leds ou power_supply. E o `hid-generic` **não** assume, porque um driver
específico casou. É por isso que "os dois controles viram um só".

### A causa (não é timeout)

Timeout foi testado e REFUTADO: esta máquina já roda `sync_send_tries=4
probe_info_timeout_ms=4000`, ou seja 4 tentativas de 4 s, e falha igual.

A causa está uma etapa antes, no `joycon_init()`:

```c
if (joycon_using_usb(ctlr) && !joycon_send_usb(ctlr, JC_USB_CMD_HANDSHAKE, HZ))
```

Para o clone essa condição é **falsa** — o handshake não é respondido — e o
driver cai no ramo *"assume ble pro controller"*, indo direto ao
`joycon_read_info()` **sem nunca ter posto o controle em modo USB**. O `-110`
é consequência, não causa. A prova negativa está no próprio dmesg: não há
`Failed to set baudrate` nem `Failed handshake`, que só existem no ramo USB —
logo o ramo não foi tomado. E o handshake falha em SILÊNCIO: o
`joycon_send_usb()` só reporta em `hid_dbg`.

### As três curas (todas opt-in, default == vanilla)

| param | o que faz | aposta |
|---|---|---|
| `usb_cmd_pad_to_report` | manda o output report `0x80` com os **64 bytes** que o próprio descritor do controle declara, em vez de só 2 | **alta** |
| `usb_send_conn_status` | manda `0x80 0x01` (status de conexão) **antes** do handshake, como um console faz; guarda o MAC da resposta | média |
| `usb_probe_degrade` | se a info do device não vier, **sintetiza a identidade e segue** em vez de perder o device | rede de segurança |

**Por que o padding é a aposta forte.** O descritor do próprio controle declara
63 bytes de dados para o report `0x80` (`85 80 09 05 75 08 95 3f 91 83`) e o
endpoint OUT é `wMaxPacketSize=0x0040` — um comando é para ser exatamente um
pacote cheio. O driver monta `u8 buf[2]` e transmite 2 bytes. O firmware
genuíno perdoa; o clone parece ignorar. Robert Swiecki reportou exatamente isso
na linux-input em 26/04/2023 (*"the following func sends 2 bytes in the
JC_OUTPUT_USB_CMD, while the adapter expects 64 bytes"*) e **nunca virou
patch**; o yuzu manda 64 por hidraw e funciona. Custo do padding: 62 bytes
zerados em 1 frame de 8 ms por comando, só durante a probe.

**O `usb_probe_degrade` em detalhe.** Vale **só para USB** (em BT a cura
continua sendo o `bt_probe_retries`; lá uma falha significa link degradado, e
fingir que o controle respondeu seria mentira). Quando ligado:

- `joycon_read_info` falhou → tipo vem do **PID**, MAC vem do status de conexão
  ou, na falta dele, de um endereço **sintético e estável** `02:05:7E:20:09:03`
  (bit de "localmente administrado" ligado, então nunca colide com OUI real; e
  estável entre replugs, que é o que a numeração por-MAC do hefesto precisa);
- IMU, report mode e rumble falhando viram **aviso**, não morte.

 **Dependência:** `usb_probe_degrade=1` só entrega o device se
`register_leds_on_set_failure=1` também estiver ligado — senão a probe ainda
morreria no `joycon_leds_create`. Os dois já vão juntos no
`assets/modprobe.d/hefesto-hid-nintendo.conf`.

 **Limite honesto:** se o controle não aceitar o `set_report_mode`, o driver
só verá input se ele transmitir reports `0x30` por conta própria — o parser só
entende `0x30`/`0x21`/`0x31`, nunca `0x3F`. É plausível que transmita (é o que
faz o clone funcionar sob `hid-generic`), mas **não foi validado**. O log diz
qual dos dois casos aconteceu.

### A/B sem reload e sem reboot

Os três params são lidos **na probe**. Então basta escrever no sysfs e
**replugar** o controle — nunca é preciso `modprobe -r` (proibido com BT vivo):

```bash
echo 0 | sudo tee /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report
# desplugar e replugar o clone; conferir o dmesg
```

Escada de diagnóstico, se o clone continuar morrendo com tudo ligado:

1. `dmesg | grep -i nintendo` — se aparecer **`USB handshake got no reply`**, o
   padding não convenceu o firmware (essa linha é nova; o vanilla era mudo).
2. Se aparecer o handshake OK mas ainda `Failed to retrieve controller info`,
   o problema é só o `REQ_DEV_INFO` — aí o `usb_probe_degrade` é que decide, e
   o dmesg deve mostrar `falling back to a synthesized identity`.
3. Para isolar qual param curou: desligue um de cada vez e replugue.

## Quem é quem: `bcdDevice` (fora do módulo)

VID, PID, serial, nome e modalias COLIDEM entre genuíno e clone. O único
atributo textual, estável e legível **antes** da probe é o `bcdDevice`
(`0210` genuíno × `0200` clone). A regra `assets/84-nintendo-pro-variant.rules`
usa isso para marcar `HEFESTO_CONTROLLER_VARIANT` nos devices USB/hid/hidraw/
input e criar `/dev/hefesto/nintendo-pro` e `/dev/hefesto/8bitdo-pro-clone`.
A marca funciona **mesmo com a probe quebrada** (o nível USB/hid existe sem
driver), então serve para diagnosticar o estado ruim, não só o curado.
Caminho USB (`3-1`, `1-4`) **não** serve de chave: ela troca de porta.

## Build / instalação

- Instala via `install.sh` (DEFAULT; opt-out `--no-dkms`) usando
  `scripts/dkms_lib.sh`; vai para `updates/dkms`, que vence o in-tree
  automaticamente (`/etc/depmod.d/ubuntu.conf`). Uninstall simétrico.
- Prova de build manual (sem instalar nada):
  `make -C /usr/src/linux-headers-$(uname -r) M=$PWD modules`
- `Makefile` replica `CONFIG_NINTENDO_FF=y` do in-tree via
  `-DCONFIG_NINTENDO_FF=1` (sem isso o rumble sumiria).
- Fail-safe: build DKMS falhou num kernel novo → o in-tree continua (nunca
  ficar sem controle); se o in-tree carregar com a conf presente, o kernel só
  loga `unknown parameter 'bt_probe_retries' ignored` e sobe normal.
- Ativação NUNCA por reload com controles em uso — vale no próximo boot
  (se o módulo estiver descarregado, entra sozinho no próximo plug).

### Instalar o patch 0003 (passo MANUAL, com o Bluetooth em paz)

**O patch 0003 está NO AR nesta máquina, e funcionou.** Conferido em 11/08/2026:
`modinfo -F filename hid_nintendo` aponta para `updates/dkms`, e os três
parâmetros dele estão vivos e ligados —
`usb_cmd_pad_to_report=Y usb_send_conn_status=Y usb_probe_degrade=Y`. Com ele no
ar, o 8BitDo pelo cabo em modo Switch **proba inteiro**: dois inputs, `hidraw`,
cinco LEDs, bateria e calibração de fábrica lida — em vez do diretório com só
`modalias power report_descriptor subsystem uevent` que a seção do sintoma
descreve. A medição está em
`docs/protocol/externos-referencia-canonica.md`, seção 5.1.

O que segue é o procedimento, e ele continua valendo para **outra máquina, outro
kernel ou uma reinstalação**: o passo exige `dkms install` mais módulo novo em
memória, e trocar o `hid-nintendo` com controle BT vivo é proibido no projeto (a
regra dura: `rmmod`/`modprobe -r` de driver HID com BT conectado derruba o link
e come bond). Faça isto com jogo fechado, e de preferência com os controles BT
desconectados:

```bash
cd ~/Desenvolvimento/hefesto-dualsense4unix

# 1) prova de build (não instala nada, seguro a qualquer hora).
#    Fora do repo, para não sujar o working tree com .o/.ko/.mod:
B=$(mktemp -d) && cp assets/dkms/hid-nintendo/{hid-nintendo.c,hid-ids.h,Makefile} "$B"/
make -C /lib/modules/$(uname -r)/build M="$B" modules && rm -rf "$B"

# 2) instalar de fato: source novo p/ DKMS + modprobe.d novo
sudo bash install.sh          # DEFAULT já cobre DKMS + modprobe.d + udev
sudo udevadm control --reload-rules

# 3) ativar. NÃO faça modprobe -r com BT vivo. Duas rotas:
#    (a) preferida — REBOOT;
#    (b) sem reboot, SÓ se nenhum controle Nintendo estiver conectado
#        (nem USB nem BT) e nenhum jogo aberto:
#            lsmod | grep hid_nintendo      # tem que aparecer refcount 0
#            sudo modprobe -r hid_nintendo && sudo modprobe hid_nintendo

# 4) conferir que o módulo NOVO está no ar
grep . /sys/module/hid_nintendo/parameters/usb_*     # 3 params, todos "Y"
modinfo -F filename hid-nintendo                     # tem que dizer updates/dkms
```

Só então **plugue o 8BitDo** e leia o `dmesg`. Sucesso é: `probe - success`,
um `hidraw`/`input` novo, e `/dev/hefesto/8bitdo-pro-clone` existindo.

**E o sucesso aqui foi maior do que este parágrafo previa**, medido em 11/08: a
identidade veio **real**, não sintetizada. A prova está na forma da linha de
log. O journal traz

```
nintendo 0003:057E:2009.0008: controller MAC = E4:17:D8:00:00:1A
```

que é o `hid_info` de dentro do `joycon_read_info` (`hid-nintendo.c:2727`), **e
não** a forma do caminho degradado (`:2831`), que acrescentaria
`(USB connection status)` ou `(synthesized)` mais `type = ... (from product ID)`.
Não há nenhuma linha de `falling back to a synthesized identity` (`:2906`) no
boot inteiro. **Logo o clone respondeu ao `REQ_DEV_INFO` (`0x02`)** — ou seja, o
controle foi de fato posto em modo USB, e o `usb_probe_degrade` está ligado como
rede de segurança **sem ter precisado entrar em ação**.

**O que isto NÃO separa:** das duas curas que agem antes do `read_info` — o
padding do `usb_cmd_pad_to_report` e o `0x80 0x01` do `usb_send_conn_status` —
não dá para dizer qual fez o handshake passar, porque as duas estavam ligadas.
Separar custa um A/B: desligar uma pelo `sysfs`, replugar, ler o `dmesg`, e
devolver. Enquanto isso não for feito, *"o padding é a aposta forte"* segue
sendo aposta, e não medição.

### Voltar atrás (se travar)

Ordem do mais barato para o mais definitivo — as duas primeiras não mexem no
módulo carregado, então são seguras mesmo com BT vivo:

1. **Desligar as curas ao vivo** (valem no próximo *plug* do controle, sem
   reload):
   ```bash
   for p in usb_cmd_pad_to_report usb_send_conn_status usb_probe_degrade; do
       echo 0 | sudo tee /sys/module/hid_nintendo/parameters/$p
   done
   ```
   Isso devolve o comportamento **vanilla** do caminho USB inteiro.
2. **Desligar no boot**: editar a linha `options hid_nintendo …` de
   `/etc/modprobe.d/hefesto-hid-nintendo.conf` tirando os três `usb_*=1`.
3. **Remover o módulo patchado** (volta ao `hid-nintendo` in-tree):
   ```bash
   sudo dkms remove hefesto-hid-nintendo/1.0.0 --all
   sudo depmod -a && sudo reboot
   ```
4. **Remover a regra de nomes**: `sudo rm /etc/udev/rules.d/84-nintendo-pro-variant.rules
   && sudo udevadm control --reload-rules` (só define propriedade e symlink;
   remover não afeta input, LED nem energia).

Se o genuíno regredir em qualquer ponto, o passo 1 sozinho já o restaura — os
defaults dentro do módulo são vanilla e nada do patch 0003 toca o caminho
Bluetooth.

## Rebase (kernel novo)

`patch/BASELINE` guarda kernel base, commit e os sha256. Rota: baixar o
vanilla novo, `patch -p3 < patch/0001-*.patch`, resolver fuzz, atualizar
BASELINE + `PACKAGE_VERSION` no `dkms.conf`, re-provar o build. O `patch/`
não entra no build (o helper DKMS o exclui do source copiado).

## Upstream

Todos os `patch/*.patch` estão em formato `git format-patch` (caminho
`a/drivers/hid/hid-nintendo.c`, `git am` direto) para submissão a
`linux-input@vger.kernel.org` (cc Daniel J. Ogorchock). O Signed-off-by é o
placeholder anônimo do projeto; a submissão real exige trocar o SoB por nome
real de pessoa (DCO) — decisão da mantenedora, fora do repo. Recomendação:
quebrar em série de 3 ([B] correção, [A] retry opt-in, [C] params).

O `0003-*.patch` tem o melhor caso upstream dos três, porque o padding é
**correção de conformidade com o descritor do próprio device**, não tuning: já
foi reportado na linux-input em 2023 e nunca virou patch, e as issues
`DanielOgorchock/linux` #10, #16 e #51 são todas o mesmo `-110` sem resposta.
Vale mandar o padding sozinho primeiro (e, nesse envio, considerar propô-lo
**sem** o module param — em upstream o argumento "o descritor manda 64" é forte
o bastante para virar o comportamento único).

Antes de submeter, revalidar a paridade:

```bash
cd assets/dkms/hid-nintendo && cp hid-nintendo.c /tmp/v.c
for p in 0003 0002 0001; do patch -R -p3 /tmp/v.c < patch/$p-*.patch; done
sha256sum /tmp/v.c   # tem que bater com SHA256_VANILLA_C do patch/BASELINE
```
