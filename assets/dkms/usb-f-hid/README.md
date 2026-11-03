# hefesto-usb-f-hid (DKMS) — a resposta do GET_REPORT que não fechava

Módulo `usb_f_hid` patchado para que a resposta do GET_REPORT termine no
tamanho do relatório que o Hefesto grava, com o pacote vazio que fecha a
transferência. É a função HID dos pads USB virtuais (os gadgets
`hefesto-pad-*` que o broker monta pelo `usbip-vudc`).

## O defeito, medido em 14/10/2026

Com 4 controles, o jogo no Proton (Sackboy, GE-Proton11-7) subia sem controle
nenhum em 5 rodadas seguidas. O `services.exe` dizia
`Auto-start service L"winebus" failed to start: 1053` (o prazo é de 10 s), e
caía com um `page fault` aos ~72 s.

O `winedevice` pede cada feature com `ioctl(HIDIOCGFEATURE(128))`: o SDL
HIDAPI e o hidraw do winebus usam um buffer de 128 bytes, e o hidraw passa esse
tamanho ao `wLength` do GET_REPORT. Em `drivers/usb/gadget/function/f_hid.c`,
`get_report_workqueue_handler`:

```c
req->zero = 0;
req->length = min_t(unsigned int, min_t(unsigned int, hidg->get_report_req_report_length,
                                                      hidg->report_length),
                                  MAX_REPORT_LENGTH);
```

1. o tamanho ignora o `length` da `struct usb_hidg_report` que o Hefesto grava
   pelo `GADGET_HID_WRITE_GET_REPORT` (`pad_usb.pacote_do_get_report`), e a
   resposta sai sempre com 64 bytes;
2. 64 bytes enchem os pacotes do ep0 (maxpacket 64) e, sem o pacote vazio, o
   host espera o resto até o timeout de 5 s.

| pedido | pad virtual, `f_hid` de fábrica | o físico no cabo | pad virtual, este módulo |
| --- | --- | --- | --- |
| 64 bytes | ok, 2–7 ms | — | ok |
| 128 bytes, 0x05 (41 B) | `-110` aos 5072 ms | 41 B em 204 ms | 41 B, 2–6 ms |
| 128 bytes, 0x09 (20 B) | pendurava, como toda feature | 20 B | 20 B, 2–6 ms |
| 128 bytes, 0x20 (64 B) | pendurava, como toda feature | `-110` aos 5672 ms | 64 B, 2–6 ms |

Com o módulo carregado (r4a e r4c, a condição exata das 5 falhas): 0 timeouts,
nenhum `1053` nem `page fault`, o `winedevice` com os 4 hidraw abertos e a
entrada dos 4 pads a ~170 relatórios/s cada.

## A cura

`f_hidg_size_get_report()`, chamada nos dois ramos antes do `usb_ep_queue`:
corta ao `length` gravado e liga `req->zero` quando a resposta é menor que o
`wLength`.

## A recusa, medida em 02/11/2026 (`patch/0002`)

No hidraw do pad pelo gadget, o `0x22`, que o pad não guarda, voltou como 64
bytes zerados com sucesso. Três ramos davam o buffer zerado: o id gravado com
tamanho zero (o que o Hefesto grava para o id que não serve), o id a que o
espaço de usuário não respondeu em 2500 ms e o pedido que o `hidg_disable`
largou, que ainda liberava o `get_req` e deixava todo GET_REPORT seguinte sem
resposta até o rebind. Um feature zerado com sucesso é o firmware `0x0000` que
o jogo lê; o DualSense no cabo responde `EPIPE` ao id que não serve.

O `0002` troca os três: o id recusado e o sem resposta saem como stall no ep0
(`usb_ep_set_halt`), que o host lê como `EPIPE`; o pedido largado pelo disable
sai sem resposta, e o `get_req` fica para o próximo bind. O pedido largado não
leva stall porque um stall que cruza com o SETUP seguinte faria o `vudc`
reprovar a enumeração. O Hefesto grava a recusa com
`pad_usb.recusar_get_report` (o relatório de tamanho zero); pelo uhid, o mesmo
id volta com `err=EPIPE`, que o kernel entrega ao `hidraw` como `EIO`.

**As marcas:** `get_report_sized` (o `0001`) e `get_report_refuses` (o
`0002`), as duas 0444 e sempre Y, em `/sys/module/usb_f_hid/parameters/`. Nada
mais no sysfs separa este módulo do de fábrica, e a segunda é a versão que o
daemon e o doctor podem ler: a `PACKAGE_VERSION` fica em 1.0.0 (o motivo está
no `dkms.conf`). O daemon só chama de curado o módulo com as duas: o
`daemon.state_full` diz `gamepad_emulation.get_report_sized` (todas as marcas
no ar) e `gamepad_emulation.f_hid_marcas_que_faltam`, e o doctor reprova
nomeando a marca que falta (`check_hefesto_usb_f_hid_dkms`). A lista das
marcas tem um dono só: `DKMS_MARCAS_DO_USB_F_HID`, em `scripts/dkms_lib.sh`; a
`pad_usb.MARCAS_DO_F_HID` do daemon é conferida contra essa lista e contra o
`f_hid.c` (`tests/unit/test_o_daemon_olha_todas_as_marcas_do_f_hid.py`).

## A troca a quente

O install (`install_dkms_usb_f_hid_host`, em `scripts/lib/camada_de_maquina.sh`)
troca o módulo carregado quando falta a ele uma das marcas e o curado está em
`updates/dkms`:

- sem gadget nenhum (refcnt 0): troca na hora;
- com o refcnt acima de 0, com ou sem gadget `hefesto-pad-*`: para o daemon
  de usuário, espera o processo dele sair e o refcnt chegar a 0 (com prazo; o
  broker desmonta os pads no EOF da conexão, e o `/dev/hidgN` se fecha com o
  processo), desmonta o `hefesto-pad-*` que sobrou sem ninguém com o
  `/dev/hidg*` aberto, troca e sobe o daemon se ele estava no ar;
- quem ainda abre um `/dev/hidg*` depois disso impede a troca: o aviso diz o
  PID e o nome (de `/proc/*/fd`), e o curado vale no próximo boot;
- com gadget alheio: não troca, e o módulo curado vale no próximo boot;
- com todas as marcas: não toca. Rodar o install duas vezes dá o mesmo estado.

Com o `0001` carregado (só a `get_report_sized`), o módulo com o `0002` entra
na mesma troca, sem reiniciar.

A troca mora na função do host e nunca no `scripts/dkms_lib.sh`, cujo
contrato proíbe `modprobe` e `rmmod`.

## Proveniência

- `f_hid.c` = **o de fábrica do stable v7.1.5** + a série `PATCH=` do
  `patch/BASELINE`, na ordem (`0001` e `0002`).
  `u_hid.h` = o de fábrica, sem modificação (o `linux-headers` não o traz).
  Invariante verificável:

  ```bash
  cp f_hid.c /tmp/prova.c
  patch -R -p5 /tmp/prova.c < patch/0002-*.patch
  patch -R -p5 /tmp/prova.c < patch/0001-*.patch
  sha256sum /tmp/prova.c   # == SHA256_VANILLA_C de patch/BASELINE
  ```

- O de fábrica se confere sem baixar o tarball do kernel, na árvore STABLE e
  com o tag da versão EXATA:

  ```bash
  curl -fsSL 'https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/usb/gadget/function/f_hid.c?h=v7.1.5'
  ```

- Código C e comentários do patch em **inglês**, a convenção do subsistema
  USB gadget. O envio ao linux-usb não foi feito: é decisão a tomar.

- **No kernel que roda.** Este `f_hid.c` é o cache dos kernels conferidos
  (`fonte-por-kernel/raiz.txt`, a mesma lista do `KERNELS_VALIDADOS` do
  `patch/BASELINE`): hoje, o 7.1.5-76070105 e o 7.2.6-76070206 (o `f_hid.c` de
  fábrica dos dois é o mesmo byte a byte). Fora do cache, o
  `preparar-o-fonte.py` (o `PRE_BUILD`) acha o `f_hid.c` de fábrica do kernel
  que roda, confere pelo `srcversion` e aplica a série; quando não acha ou a
  série não aplica, o DKMS pula, o de fábrica assume e o doctor diz o motivo. O
  ritual do rebase está no `BASELINE`, e a régua é
  `tests/unit/test_o_usb_f_hid_fecha_a_resposta.py`.

- A decisão está no [ADR-023](../../../docs/adr/023-o-pad-usb-virtual-usa-o-usb-f-hid-da-casa.md),
  e a troca a quente, o doctor e o pad se medem em
  `tests/unit/test_o_usb_f_hid_curado_troca_a_quente.py`.
