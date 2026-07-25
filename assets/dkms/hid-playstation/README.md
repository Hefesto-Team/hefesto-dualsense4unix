# hefesto-hid-playstation (DKMS) — contenção de Bluetooth na probe

Módulo `hid-playstation` patchado para curar a perda de um DualSense inteiro
quando **dois ou mais controles pareiam quase ao mesmo tempo no mesmo
adaptador**. Motivado pelo alvo do projeto: **quatro controles por Bluetooth
simultâneos, um por jogador** — nesse cenário a disputa deixa de ser exceção.

> ##  Leia primeiro: este DKMS é a cura de SEGUNDA linha
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

## O que foi avaliado e REJEITADO

**Degradar como o `usb_probe_degrade` do `hid-nintendo`** — deixar o firmware
info falhar e seguir com valores default. Rejeitado: o `update_version` que
vem nesse report decide `use_vibration_v2`, ou seja, **qual motor de vibração
o driver usa**. Errar isso silenciosamente entrega um controle que vibra
diferente, e vibração é área com histórico de regressão neste projeto
(`SPRINT-GAME-RUMBLE-01`). Um retry conserta a causa real; degradar trocaria
uma falha honesta e visível por um comportamento errado e mudo. Se no futuro
ficar provado que a contenção sobrevive ao retry com 4 controles, a discussão
volta — mas aí com medição, não por precaução.

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
cat /sys/module/hid_playstation/parameters/feature_retries   # tem que ser > 0
modinfo -F filename hid-playstation                          # tem que dizer updates/dkms
```

Depois **conecte os controles por BT quase juntos** (é o gatilho) e leia:

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

1. **Desligar a cura ao vivo** (vale na próxima conexão, sem reload):
   ```bash
   echo 0 | sudo tee /sys/module/hid_playstation/parameters/feature_retries
   ```
   Isso devolve o comportamento **vanilla** (uma tentativa).
2. **Desligar no boot**: tirar `feature_retries=` de
   `/etc/modprobe.d/hefesto-hid-playstation.conf`.
3. **Remover o módulo patchado** (volta ao in-tree):
   ```bash
   sudo dkms remove hefesto-hid-playstation/1.0.0 --all
   sudo depmod -a && sudo update-initramfs -u && sudo reboot
   ```

## Rebase (kernel novo)

`patch/BASELINE` guarda kernel base, commit e os sha256. Rota: baixar o vanilla
novo, `patch -p3 < patch/0001-*.patch`, resolver fuzz, atualizar BASELINE, e
re-provar o build. O `patch/` não entra no build (o helper DKMS o exclui do
source copiado).

## Upstream

O `patch/*.patch` está em formato `git format-patch` (caminho
`a/drivers/hid/hid-playstation.c`, `git am` direto) para submissão a
`linux-input@vger.kernel.org`. O Signed-off-by é o placeholder anônimo do
projeto; a submissão real exige trocar o SoB por nome real de pessoa (DCO) —
decisão da mantenedora, fora do repo.

O caso upstream é bom: o commit message carrega a cadeia causal inteira
medida (uhid achatando `ETIMEDOUT` em `-EIO`, os 3,26 s, e a linha do
`bluetoothd` nomeando o `REPORT_REQ_TIMEOUT`), que é justamente o que falta
nos relatos de "DualSense não conecta às vezes". Vale considerar propor o
retry **sem** o module param — "um GET_REPORT que expirou no canal de controle
não é motivo para perder o device" é argumento forte o bastante sozinho.

Antes de submeter, revalidar a paridade:

```bash
cd assets/dkms/hid-playstation && cp hid-playstation.c /tmp/v.c
patch -R -p3 /tmp/v.c < patch/0001-*.patch
sha256sum /tmp/v.c   # tem que bater com SHA256_VANILLA_C do patch/BASELINE
```
