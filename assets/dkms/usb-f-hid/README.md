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
`wLength`. Sem relatório gravado para o id, o tamanho fica o de antes (o
buffer zerado).

**A marca:** `get_report_sized` (0444, sempre Y), em
`/sys/module/usb_f_hid/parameters/get_report_sized`. Nada mais no sysfs separa
este módulo do de fábrica. O daemon a guarda no `daemon.state_full`
(`gamepad_emulation.get_report_sized`), e o doctor reprova sem ela
(`check_hefesto_usb_f_hid_dkms`).

## A troca a quente

O install (`install_dkms_usb_f_hid_host`, em `scripts/lib/camada_de_maquina.sh`)
troca o módulo carregado quando ele não tem a marca e o curado está em
`updates/dkms`:

- sem gadget nenhum (refcnt 0): troca na hora;
- com gadgets `hefesto-pad-*`: para o daemon de usuário, o broker desmonta os
  pads no EOF da conexão, o refcnt chega a 0 (com prazo), troca e sobe o
  daemon se ele estava no ar;
- com gadget alheio: não troca, e o módulo curado vale no próximo boot;
- com a marca: não toca. Rodar o install duas vezes dá o mesmo estado.

A troca mora na função do host e nunca no `scripts/dkms_lib.sh`, cujo
contrato proíbe `modprobe` e `rmmod`.

## Proveniência

- `f_hid.c` = **o de fábrica do stable v7.1.5** + `patch/0001-*.patch`.
  `u_hid.h` = o de fábrica, sem modificação (o `linux-headers` não o traz).
  Invariante verificável:

  ```bash
  cp f_hid.c /tmp/prova.c
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

- **Só nos kernels conferidos** (`BUILD_EXCLUSIVE_KERNEL` do `dkms.conf`, a
  mesma lista do `KERNELS_VALIDADOS` do `patch/BASELINE`): hoje, só o
  7.1.5-76070105. Fora da lista o DKMS pula e o de fábrica assume. O ritual
  para acrescentar um kernel está no `BASELINE`, e a régua é
  `tests/unit/test_o_usb_f_hid_fecha_a_resposta.py`.

- A decisão está no [ADR-023](../../../docs/adr/023-o-pad-usb-virtual-usa-o-usb-f-hid-da-casa.md),
  e a troca a quente, o doctor e o pad se medem em
  `tests/unit/test_o_usb_f_hid_curado_troca_a_quente.py`.
