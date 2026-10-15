# ADR-023: o pad USB virtual usa o `usb_f_hid` da casa

**Status:** aceito · **Data:** 2026-10-14

## Contexto

O pad virtual nasce no gadget USB (`usbip_vudc` + `vhci_hcd`, uma função HID por
pad). Quem responde ao pedido de feature do jogo é o `usb_f_hid` do kernel, com o
relatório que o Hefesto grava pelo `GADGET_HID_WRITE_GET_REPORT`.

Medido em 14/10/2026: o Wine e o SDL pedem as features com `wLength` 128. O
`usb_f_hid` de fábrica responde sempre com 64 bytes, sem o pacote vazio, e cada
pedido volta ETIMEDOUT aos ~5 s. Com 4 controles, o `winebus` estoura o prazo do
`services.exe`, e o jogo no Proton sobe sem controle nenhum. O registro está em
[pilha-steam-input-xpad-sdl.md §6-ter](../protocol/pilha-steam-input-xpad-sdl.md).

## Decisão

- O `usb_f_hid` do stable v7.1.5 com um patch próprio vai por DKMS
  (`assets/dkms/usb-f-hid/`), no molde do `hid-playstation` e do `uhid`. O patch
  fecha a resposta no tamanho gravado e manda o pacote vazio quando falta.
- Ele só se constrói nos kernels conferidos (`BUILD_EXCLUSIVE_KERNEL` e o ritual do
  `patch/BASELINE`). Fora deles, o de fábrica assume.
- A marca `get_report_sized` (0444, sempre Y) separa o curado do de fábrica. O pad
  a mede ao montar e o `daemon.state_full` a publica. O `doctor` dá `[FAIL]` sem
  ela.
- O install troca o módulo a quente, e a troca é idempotente. Com a marca, não
  toca. Sem a marca, para o daemon, espera o broker soltar os pads, troca e sobe o
  daemon. Com gadget alheio, ou com o módulo preso, não troca e diz «reinicie».
- Os pads sobem com o de fábrica também. Com 1 controle cabia no prazo, e o pad
  não depende do módulo para existir.

## Consequências

- Kernel novo exige o ritual do BASELINE. Até lá, o `doctor` diz `[FAIL]` com a
  causa e a cura.
- O NixOS fica sem a cura: não há DKMS ali (`packaging/nix/README.md`).
- O defeito é do upstream. Mandar o patch ao linux-usb é decisão aberta.
