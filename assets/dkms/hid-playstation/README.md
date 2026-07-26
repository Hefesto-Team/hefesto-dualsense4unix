# hefesto-hid-playstation (DKMS) — probe que não joga o controle fora

Módulo `hid-playstation` patchado contra **dois** modos de perder um controle
inteiro na janela de probe. Os dois são independentes, cada um com o seu
`patch/` e os seus module params:

| patch | defeito | transporte |
|---|---|---|
| `0001` | contenção do canal de controle quando **dois ou mais controles pareiam quase juntos** no mesmo adaptador | Bluetooth |
| `0002` | **clone** que responde o pairing info **curto** e nunca completa (8BitDo Pro em modo DirectInput/PS4, `054c:05c4`) | USB |

O `0001` é motivado pelo alvo do projeto — **quatro controles por Bluetooth
simultâneos, um por jogador** —, cenário em que a disputa deixa de ser
exceção. O `0002` é o mesmo controle do `0001` visto pelo outro lado: por
Bluetooth ele sobe, no cabo ele morre.

> ##  Leia primeiro: contra a contenção BT, este DKMS é a cura de SEGUNDA linha
>
> Existem **duas** curas para o mesmo problema, com **níveis de confiança
> diferentes**. Elas não se misturam:
>
> | | cura | estado |
> |---|---|---|
> | **1ª linha** | `scripts/bt_rebind_orphans.sh` — rebind do device órfão no driver **vanilla**, em userspace |  **VALIDADA AO VIVO** em 25/07 12:06 |
> | **2ª linha** | este DKMS (`feature_retries`) — retry dentro da probe |  **NÃO validada**; o teste real é o próximo boot |
>
> **A de primeira linha basta na maioria dos casos e é a que está provada.**
> Ela não exige patch de kernel, não exige reboot, não recarrega módulo e não
> toca em controle que está funcionando. Detalhes na seção
> [A cura de primeira linha](#a-cura-de-primeira-linha-rebind-validada-ao-vivo).
>
> Este DKMS é a cura **estrutural** — evita a janela em que o controle fica
> sem driver, em vez de consertar depois. É o certo a longo prazo, mas hoje
> ainda é **hipótese fundamentada**, não fato medido.
>
> **Isso vale só para o `0001`.** Para o clone no cabo (`0002`) **não existe
> cura de primeira linha**: o `bt_rebind_orphans.sh` só toca barramento `0005`
> (Bluetooth), e rebind não ajudaria de qualquer forma — a resposta curta é
> determinística, o próximo probe falha igual.

## Proveniência

- `hid-playstation.c` = **vanilla v7.0.11** (baixado de `pop-os/linux` no
  commit registrado em `patch/BASELINE`) **+ os `patch/000N-*.patch` aplicados
  NA ORDEM**. Invariante verificável: revertendo na ordem INVERSA reproduz
  exatamente o `SHA256_VANILLA_C`. Comando pronto na seção **Upstream**.
- `hid-ids.h` = header local intocado do MESMO commit. Ele bateu **byte a
  byte** com o `hid-ids.h` já vendorado em `assets/dkms/hid-nintendo/`
  (mesmo `SHA256_HID_IDS_H` nos dois pacotes) — é essa coincidência que prova
  que o commit baixado é o certo. É vendorado porque `drivers/hid/hid-ids.h`
  é header PRIVADO do subsistema: não é exportado e **não vem** no
  `linux-headers`, então um build out-of-tree não o alcança.
- Código C em inglês (convenção do subsistema HID, visando o upstream).

>  **`srcversion` NÃO serve para conferir proveniência.** Ele não é
> reprodutível entre build in-tree e out-of-tree. Controle feito em 25/07: o
> `hid-nintendo` **vanilla**, revertido dos patches e com `sha256` batendo o
> `SHA256_VANILLA_C` do pacote vizinho, compilou para
> `E510116794E5943C26F761D` contra `098AB755D743D99788D82ED` do in-tree do
> Pop!\_OS. O juiz da identidade do fonte é o **sha256 do `.c`**, e só ele.

## O sintoma medido (25/07)

Dois DualSense conectando no mesmo adaptador com ~1 s de diferença. O primeiro
(`.0008`) concluiu a probe em **74 ms**. O segundo (`.0009`) pegou o pairing
info (reportID 9) e perdeu o firmware info (reportID 32):

```
[164.366] playstation 0005:054C:0CE6.0008: hidraw6: BLUETOOTH HID v1.00 Gamepad
[164.440] playstation 0005:054C:0CE6.0008: Registered DualSense controller ...
[165.539] playstation 0005:054C:0CE6.0009: hidraw7: BLUETOOTH HID v1.00 Gamepad
[168.799] playstation 0005:054C:0CE6.0009: Failed to retrieve feature with reportID 32: -5
[168.799] playstation 0005:054C:0CE6.0009: Failed to retrieve DualSense firmware info: -5
[168.799] playstation 0005:054C:0CE6.0009: Failed to create dualsense.
[168.799] playstation 0005:054C:0CE6.0009: probe with driver playstation failed with error -5
```

O controle some: sem `hidraw`, sem `input`, sem LED, sem bateria.

## A causa (o `-5` é máscara, não diagnóstico)

Três medidas encadeadas, todas verificadas nesta máquina:

1. **O erro real não é `-EIO`.** Por Bluetooth o `hid_hw_raw_request()` cai no
   `uhid`, e o `uhid_hid_get_report()` do kernel achata **qualquer** erro que o
   transporte reporte:

   ```c
   req = &uhid->report_buf.u.get_report_reply;
   if (req->err)
           ret = -EIO;
   ```

2. **Não foi o timeout do kernel.** Entre o pedido e a falha passaram
   **3,26 s** (`165.539` → `168.799`). A espera do `uhid` é de **5 s**
   (`__uhid_report_queue_and_wait`, `5 * HZ`) — ou seja, o kernel ainda
   esperava; quem desistiu foi o userspace.

3. **Foi o BlueZ, e ele registrou.** O `journalctl -u bluetooth` do mesmo
   segundo:

   ```
   bluetoothd: profiles/input/device.c:hidp_report_req_timeout()
               Device A0:FA:9C:00:00:02 HIDP GET_REPORT request timed out
   ```

   `REPORT_REQ_TIMEOUT` é **3 s** no `profiles/input/device.c` do BlueZ 5.86 —
   exatamente os 3,26 s medidos. O BlueZ responde `ETIMEDOUT`, e o kernel
   entrega `-EIO` ao driver.

**Conclusão:** o controle estava alcançável — tinha acabado de responder o
feature report anterior — e só não ganhou o canal de controle L2CAP dentro de
3 s enquanto o outro pad subia no mesmo rádio. É transiente, e é exatamente o
tipo de falha que escala com o número de controles pareando juntos.

## A cura de primeira linha: rebind (VALIDADA ao vivo)

A prova de que a contenção é transiente veio do experimento mais barato
possível — **rebind no driver vanilla in-tree**, sem patch nenhum, no mesmo
controle que o bug tinha matado minutos antes:

```
echo "0005:054C:0CE6.000F" > /sys/bus/hid/drivers/playstation/bind
```

```
[25/07 12:06:28] playstation 0005:054C:0CE6.000F: hidraw9: BLUETOOTH HID v81.00 Gamepad [DualSense Wireless Controller]
[25/07 12:06:28] playstation 0005:054C:0CE6.000F: Registered DualSense controller hw_version=0x00000710 fw_version=0x0110002a
[25/07 12:06:28] playstation 0003:054C:0DF2.0010: hidraw10: [Hefesto Virtual DualSense P2]
```

**Subiu de primeira, sem retry nenhum**, e o daemon criou o vpad em seguida —
os 4 controles vivos com slots 1-4 distintos.

Isso estabelece dois fatos:

1. **O device permanece plenamente utilizável.** A falha é só na **janela de
   probe** — não no controle, não no bond, não no link. Nada de hardware
   travado, nada de re-pareamento.
2. **Passada a janela, o mesmo GET_REPORT passa.** Ou seja, a contenção some
   sozinha assim que o outro pad termina de subir.

Por isso o rebind é a cura de primeira linha, e está automatizado em
`scripts/bt_rebind_orphans.sh`:

- **detecção precisa e barata**: device em `/sys/bus/hid/devices` **sem**
  symlink `driver`. Esse estado é anômalo por construção — o `hid-generic` não
  assume porque um driver específico deu match, que é justamente o que torna o
  sintoma inconfundível;
- **escopo estreito**: só barramento `0005` (Bluetooth) + vendor `054C`
  (Sony). O barramento exclui por construção o vpad do próprio hefesto, que
  nasce por uhid no `0003`. Órfão fora do escopo é reportado, nunca tocado;
- **guarda contra laço**: no máximo 3 rebinds por device, contador em `/run`,
  e depois disso desiste **logando uma vez** (o histórico do projeto tem laço
  de 1 Hz que encheu log por 45 min — mesma disciplina do circuit-breaker do
  `hid-nintendo`). Como o id do device muda a cada reconexão, reconectar dá
  orçamento novo, que é o comportamento certo;
- **nunca carrega/descarrega módulo** — recarregar `hid_playstation`
  derrubaria todos os DualSense, inclusive os por Bluetooth.

Roda sozinho pela vigia 4 do `bt_health_watchdog.sh` (timer de 2 min, já
existente). À mão:

```bash
sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh          # cura
scripts/bt_rebind_orphans.sh --dry-run                                  # só relata
```

**Limite conhecido:** o watchdog passa a cada 2 min, então no pior caso o
controle fica órfão por até 2 min antes da cura automática. Se isso incomodar
com 4 jogadores, o degrau seguinte é uma regra udev reagindo ao `add` do HID —
o script já é idempotente e seguro para ser chamado dali.

## A cura: `feature_retries` (opt-in, default == vanilla)

| param | o que faz | default |
|---|---|---|
| `feature_retries` | tentativas EXTRA quando um feature report da probe falha; backoff 100 ms dobrando | `0` (uma tentativa, == vanilla) |

**Por que é seguro repetir.** Ler feature report é operação de LEITURA pura,
sem efeito colateral no controle. E quando o timeout do BlueZ dispara, ele já
limpou o `report_req_pending` (`hidp_report_req_timeout()` zera antes de
retornar), então a nova tentativa é **aceita na hora** em vez de recusada com
`EBUSY`.

**Por que não trava o `bluetoothd`.** A probe roda num *worker* do `uhid` — o
`uhid_dev_create2()` agenda o `hid_add_device()` via `schedule_work()`
justamente para que drivers possam fazer feature request no `.probe` sem
deadlock. Dormir entre tentativas não segura o laço principal do daemon que
precisa responder.

**Por que TODAS as falhas são repetidas**, não só o erro de transporte: erro
curto, `reportID` trocado e CRC ruim descrevem a mesma coisa — uma
transferência que não chegou inteira.

**Custo no pior caso:** com `feature_retries=2`, um controle de fato morto
gasta 3 tentativas × 3 s + 100 ms + 200 ms ≈ **9,3 s** de probe antes de
desistir (contra 3,3 s hoje). Em workqueue, sem segurar nada crítico.

## O que foi avaliado e REJEITADO (no `0001`)

**Degradar como o `usb_probe_degrade` do `hid-nintendo`** — deixar o firmware
info falhar e seguir com valores default. Rejeitado: o `update_version` que
vem nesse report decide `use_vibration_v2`, ou seja, **qual motor de vibração
o driver usa**. Errar isso silenciosamente entrega um controle que vibra
diferente, e vibração é área com histórico de regressão neste projeto
(`SPRINT-GAME-RUMBLE-01`). Um retry conserta a causa real; degradar trocaria
uma falha honesta e visível por um comportamento errado e mudo. Se no futuro
ficar provado que a contenção sobrevive ao retry com 4 controles, a discussão
volta — mas aí com medição, não por precaução.

> **Por que o `0002` degrada, então?** Porque o que ele salva é outra coisa: o
> **endereço**, não a versão de firmware. Nenhum comportamento do driver é
> escolhido pelo endereço — ele vira `uniq`, nome da bateria e chave de
> duplicata. Não há motor errado para ligar silenciosamente. E a alternativa
> não é "falha honesta e visível": é o device sem driver nenhum, que é
> justamente o estado mais mudo possível. No DualShock 4 o endereço é também
> o **único** passo fatal que sobrou no cabo — firmware info e calibração já
> degradam para aviso no vanilla.

## Limite honesto (o que este patch NÃO promete)

Separando o que é **fato medido** do que é **hipótese fundamentada**:

**Medido (fato):**

- a cadeia causal inteira — as 3 medidas da seção anterior, incluindo a linha
  do `bluetoothd` nomeando o `REPORT_REQ_TIMEOUT`;
- que a contenção é **transiente**, porque o rebind no driver **vanilla**
  ressuscitou o controle de primeira;
- que o `.c` compila limpo, o `dkms status` fica `installed`, o `modinfo`
  resolve para `updates/dkms` e o patch faz round-trip byte a byte.

**NÃO medido (hipótese):**

- **que `feature_retries=2` de fato cura.** É altamente plausível — o mesmo
  GET_REPORT passou no rebind segundos depois, que é exatamente o que um retry
  faz mais cedo — mas *plausível não é medido*. Validar exige recarregar o
  `hid_playstation`, o que derruba os DualSense conectados, e a regra do
  projeto proíbe isso com controle em uso. **A validação é o próximo boot** —
  ver a seção de validação abaixo.

Enquanto isso não acontecer, **a cura que está funcionando é o rebind**, não
este módulo.

Se com 4 controles a contenção passar de 3 s mesmo com retries, o próximo
degrau **não** é mais retry: é atacar o `REPORT_REQ_TIMEOUT` do BlueZ (o
projeto já mantém um backport 5.86, então é alcançável) ou serializar a subida
dos controles no daemon do hefesto.

## O segundo defeito: o clone no cabo (patch `0002`)

### O sintoma medido (25/07 ~21:02)

8BitDo Pro clone em modo DirectInput/PS4, **no cabo**. Ele se anuncia com os
IDs da Sony (`054c:05c4`), então cai neste driver:

```
usb 3-2: New USB device found, idVendor=054c, idProduct=05c4
playstation 0003:054C:05C4.0012: hidraw9: USB HID v1.11 Gamepad [Sony Computer Entertainment Wireless Controller]
playstation 0003:054C:05C4.0012: Invalid byte count transferred, expected 16 got 9
playstation 0003:054C:05C4.0012: retrying feature reportID 18 in 100 ms (2 attempt(s) left)
playstation 0003:054C:05C4.0012: Invalid byte count transferred, expected 16 got 9
playstation 0003:054C:05C4.0012: retrying feature reportID 18 in 200 ms (1 attempt(s) left)
playstation 0003:054C:05C4.0012: Invalid byte count transferred, expected 16 got 9
playstation 0003:054C:05C4.0012: Failed to retrieve DualShock4 pairing info: -22
playstation 0003:054C:05C4.0012: Failed to get MAC address from DualShock4
playstation 0003:054C:05C4.0012: Failed to create dualshock4.
playstation 0003:054C:05C4.0012: probe with driver playstation failed with error -22
```

Mesmo desfecho do outro defeito — device sem driver nenhum, sem `hidraw`, sem
`input`, sem LED, sem bateria — por uma causa **oposta**.

### A causa: resposta curta, não atraso

O report `0x12` é o **pairing info**, e no cabo ele é a **única** fonte do
endereço para o `dualshock4_get_mac_address()`. O clone responde **9 bytes**
onde o driver pediu 16, o `__ps_get_report()` devolve `-EINVAL` e a probe
desmonta.

Três leituras que fecham o diagnóstico:

1. **Não é timing.** As linhas `retrying feature reportID 18` são o
   `feature_retries=2` do `0001` em ação: as três tentativas trouxeram **os
   mesmos 9 bytes**. Resposta curta e determinística — esperar mais não muda
   nada. (Preço: 300 ms por conexão, que é o que põe a prova no log.)
2. **Dos 16 bytes o driver usa 7.** Report ID + 6 do endereço. O resto é o
   endereço do **host** com quem o controle pareou por último, que este driver
   nunca lê. Uma resposta de 9 bytes **pode** trazer tudo o que é usado.
3. **Por Bluetooth esse report nem é lido.** Lá o endereço vem do `uniq` do
   HIDP. É por isso que o **mesmo** controle sobe por BT e só morre no cabo —
   e é a prova de que o aparelho está inteiro; o que falta é um campo de um
   report que o firmware clone não implementa até o fim.

### A cura (opt-in, defaults == vanilla)

| param | o que faz | default |
|---|---|---|
| `ds4_short_pairing_info` | aceita a resposta curta **quando ela traz o endereço** (report ID certo + campo não-zerado) | `N` (exige os 16 bytes, == vanilla) |
| `ds4_synthetic_mac` | quando não traz nada aproveitável, fabrica `02:VID:PID:bus` | `N` (falha a probe, == vanilla) |

**Por que o report ID tem que bater.** Aplicações `hidraw` (a Steam, entre
elas) emitem feature request próprios — é exatamente por isso que o
`dualshock4_get_calibration_data()` do vanilla já retenta. Endereço tirado da
resposta de **outro** report seria pior do que endereço nenhum.

**Por que ler o buffer depois do erro é seguro.** Ele é `kzalloc`, e o
transporte copia só os bytes que chegaram: o que está lá é o que o controle
mandou, e o resto é zero. Se nem o transporte funcionou, o buffer segue zerado
e o `buf[0]` não bate com `0x12` — cai no ramo do endereço sintetizado.

**O endereço fabricado NÃO é identidade.** `02:05:4C:05:C4:03` = `02` + VID +
PID + barramento: zero bits do aparelho. É a **mesma convenção** do
`usb_probe_degrade` do `hid-nintendo`, de propósito — o hefesto já trata MAC
começando em `02` como identidade **volátil** (ganha número na sessão, nunca
vai ao disco) e cai para a instância HID na deduplicação. Divergir da
convenção aqui desarmaria essa cura em silêncio.

**Custo conhecido:** dois clones idênticos no mesmo barramento recebem o
**mesmo** endereço, e o segundo é recusado pelo `ps_devices_list_add()` com
`-EEXIST`. É **um** controle perdido onde hoje se perdem os dois — melhora
estrita, não perfeição.

**Por que não toca no DualShock 4 genuíno.** Ele responde os 16 bytes: o
`if (ret)` nem é tomado, e nenhum dos dois ramos existe para ele. Com os dois
params em `N` o desfecho é byte a byte o de hoje, inclusive as mensagens de
erro. E os dois ramos vivem dentro do `if (hdev->bus == BUS_USB)`, então
Bluetooth não é alcançado de forma alguma.

### Limite honesto do `0002`

**Medido (fato):** o sintoma acima; que os retries trazem sempre 9 bytes; que
o mesmo controle sobe por Bluetooth; que o `.c` com o patch compila limpo
contra `7.0.11-76070011-generic`, sem warning, e o `modinfo` do `.ko` mostra
os dois params novos como `bool`.

**NÃO medido (hipótese):**

- **quais 9 bytes o clone manda.** Se os 6 do endereço vierem preenchidos,
  quem cura é o `ds4_short_pairing_info`; se vierem zerados, é o
  `ds4_synthetic_mac`. Os dois estão ligados na conf porque o segundo é o
  fallback do primeiro — mas **qual dos dois de fato entra é o dmesg que vai
  dizer**, na linha `DualShock4 MAC = ... (truncated pairing info)` ou
  `(synthesized)`;
- **que a probe completa depois do endereço.** É altamente plausível — os
  passos seguintes já degradam para aviso no vanilla —, mas plausível não é
  medido. Validar exige o módulo patchado carregado, e trocar o
  `hid_playstation` em memória derruba todos os DualSense. **A validação é o
  próximo boot.**

## Build / instalação

- Instala via `install.sh` (DEFAULT; opt-out `--no-dkms`) usando
  `scripts/dkms_lib.sh`; vai para `updates/dkms`, que vence o in-tree
  (`/etc/depmod.d/ubuntu.conf`). Uninstall simétrico.
- **O `install.sh` regenera o initramfs** depois de mexer no DKMS
  (INITRAMFS-01): sem isso o boot carregaria a cópia antiga do módulo.
- Prova de build manual (sem instalar nada):
  ```bash
  B=$(mktemp -d) && cp assets/dkms/hid-playstation/{hid-playstation.c,hid-ids.h,Makefile} "$B"/
  make -C /lib/modules/$(uname -r)/build M="$B" modules && rm -rf "$B"
  ```
- `Makefile` replica `CONFIG_PLAYSTATION_FF=y` do in-tree via
  `-DCONFIG_PLAYSTATION_FF=1` (sem isso o rumble sumiria).
- Fail-safe: build falhou em kernel novo → o in-tree continua.

###  Ativação: NUNCA por reload com DualSense conectado

Trocar o `hid_playstation` em memória derruba **todos** os DualSense — os por
Bluetooth perdem o link. Rotas:

- **(a) preferida — REBOOT.**
- **(b) sem reboot, SÓ com nenhum DualSense conectado (nem USB nem BT):**
  ```bash
  lsmod | grep hid_playstation          # refcount tem que estar zerado
  sudo modprobe -r hid_playstation && sudo modprobe hid_playstation
  ```

### Validar que a cura entrou (próximo boot)

```bash
cat /sys/module/hid_playstation/parameters/feature_retries          # tem que ser > 0
cat /sys/module/hid_playstation/parameters/ds4_short_pairing_info   # tem que ser Y
cat /sys/module/hid_playstation/parameters/ds4_synthetic_mac        # tem que ser Y
modinfo -F filename hid-playstation                                 # tem que dizer updates/dkms
```

Para o clone no cabo (`0002`), o gatilho é **plugar o 8BitDo em modo
DirectInput/PS4**; sucesso é o `probe ... failed with error -22` dar lugar a:

```bash
sudo dmesg -T | grep -E "DualShock4 MAC|Registered DualShock4"
```

A linha diz qual ramo entrou — `(truncated pairing info)` se os 9 bytes
traziam o endereço, `(synthesized)` se não traziam. As duas contam como cura;
a segunda avisa que o endereço é volátil e não vai ao disco.

Para a contenção BT (`0001`), **conecte os controles por BT quase juntos** (é
o gatilho) e leia:

```bash
sudo dmesg -T | grep -iE "playstation|retrying feature"
sudo journalctl -u bluetooth | grep -i "GET_REPORT request timed out"
```

Sucesso é ver `retrying feature reportID 32 ...` **seguido de**
`Registered DualSense controller` — ou seja, o timeout do BlueZ aconteceu e o
controle subiu assim mesmo. Se aparecer `probe ... failed with error -5`
mesmo com retries, aumente `feature_retries` (vale na hora, é `0644`, lido a
cada probe — basta reconectar o controle, sem reload):

```bash
echo 4 | sudo tee /sys/module/hid_playstation/parameters/feature_retries
```

### Voltar atrás

1. **Desligar as curas ao vivo** (valem na próxima conexão, sem reload):
   ```bash
   echo 0 | sudo tee /sys/module/hid_playstation/parameters/feature_retries
   echo N | sudo tee /sys/module/hid_playstation/parameters/ds4_short_pairing_info
   echo N | sudo tee /sys/module/hid_playstation/parameters/ds4_synthetic_mac
   ```
   Isso devolve o comportamento **vanilla** em cada um dos três eixos, de
   forma independente (é assim que se faz o A/B: um param por vez).
2. **Desligar no boot**: tirar a `options` correspondente de
   `/etc/modprobe.d/hefesto-hid-playstation.conf` — são **duas** linhas, uma
   por cura, e o `kmod` concatena as duas.
3. **Remover o módulo patchado** (volta ao in-tree):
   ```bash
   sudo dkms remove hefesto-hid-playstation/1.0.0 --all
   sudo depmod -a && sudo update-initramfs -u && sudo reboot
   ```

## Rebase (kernel novo)

`patch/BASELINE` guarda kernel base, commit, os sha256 e a **ordem** da série
(uma linha `PATCH=` por patch). Rota: baixar o vanilla novo, aplicar
`0001` e depois `0002` com `patch -p3`, resolver fuzz, atualizar BASELINE, e
re-provar o build. O `patch/` não entra no build (o helper DKMS o exclui do
source copiado).

## Upstream

O `patch/*.patch` está em formato `git format-patch` (caminho
`a/drivers/hid/hid-playstation.c`, `git am` direto) para submissão a
`linux-input@vger.kernel.org`. O Signed-off-by é o placeholder anônimo do
projeto; a submissão real exige trocar o SoB por nome real de pessoa (DCO) —
decisão da mantenedora, fora do repo.

O caso upstream do `0001` é bom: o commit message carrega a cadeia causal
inteira medida (uhid achatando `ETIMEDOUT` em `-EIO`, os 3,26 s, e a linha do
`bluetoothd` nomeando o `REPORT_REQ_TIMEOUT`), que é justamente o que falta
nos relatos de "DualSense não conecta às vezes". Vale considerar propor o
retry **sem** o module param — "um GET_REPORT que expirou no canal de controle
não é motivo para perder o device" é argumento forte o bastante sozinho.

O do `0002` é mais delicado, e a mensagem já diz por quê: o aparelho é um
clone, e upstream costuma resistir a acomodar firmware de terceiro. Os dois
argumentos que sobrevivem a isso: (a) o driver joga fora um device inteiro por
um campo que ele consegue recuperar sozinho, e (b) por Bluetooth ele **já**
funciona sem ler esse report — a assimetria é do driver, não do controle. O
`hid-nintendo` tem a mesma classe de falha aberta há anos (issues 10, 16 e 51
de `DanielOgorchock/linux`), o que ajuda a mostrar que não é caso isolado.

Antes de submeter, revalidar a paridade da série (reverte na ordem INVERSA):

```bash
cd assets/dkms/hid-playstation && cp hid-playstation.c /tmp/v.c
patch -R -p3 /tmp/v.c < patch/0002-*.patch
patch -R -p3 /tmp/v.c < patch/0001-*.patch
sha256sum /tmp/v.c   # tem que bater com SHA256_VANILLA_C do patch/BASELINE
```
