"""Os números da Sony, num lugar só: o fabricante, os produtos e o pad que é nosso.

Quem precisa do VID/PID do DualSense importa daqui e não escreve o literal. Uma revisão
de hardware com PID novo muda UM arquivo, e `scripts/check_numeros_da_sony.py` conta
quantas linhas ainda carregam o literal fora deste dono (a catraca só desce).

O Edge físico e o nosso pad virtual compartilham o PID Edge: o `hid_playstation` registra
o pad forjado como DualSense completo, e quem separa o físico do nosso nunca é o PID: é o
``HID_PHYS`` do nó, e a pergunta inteira (o uhid e o gadget) tem dono em
`integrations/pad_usb.e_pad_nosso`.
"""

from __future__ import annotations

#: O fabricante (USB-IF): Sony Interactive Entertainment.
VENDOR_SONY = 0x054C

#: O DualSense de linha.
PID_DUALSENSE = 0x0CE6

#: O DualSense Edge físico, e também o PID que o nosso pad virtual declara.
PID_DUALSENSE_EDGE = 0x0DF2

#: Os produtos de DualSense físico que o produto reconhece (o Edge entra).
PIDS_DUALSENSE = frozenset({PID_DUALSENSE, PID_DUALSENSE_EDGE})

#: O PID do pad virtual do Hefesto (a máscara DualSense do uhid).
PID_DO_PAD_VIRTUAL = PID_DUALSENSE_EDGE

#: O par (VID, PID) do DualSense de linha, como as listas de ignorar do SDL e do Proton pedem.
PAR_DUALSENSE_FISICO = (VENDOR_SONY, PID_DUALSENSE)

#: O começo do ``HID_PHYS`` que o uhid do pad declara. É a identidade do nosso pad, não o PID.
HID_PHYS_DO_PAD = "hefesto-vpad"


__all__ = [
    "HID_PHYS_DO_PAD",
    "PAR_DUALSENSE_FISICO",
    "PIDS_DUALSENSE",
    "PID_DO_PAD_VIRTUAL",
    "PID_DUALSENSE",
    "PID_DUALSENSE_EDGE",
    "VENDOR_SONY",
]
