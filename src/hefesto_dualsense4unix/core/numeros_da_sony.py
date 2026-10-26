"""Os números da Sony, num lugar só: o fabricante, os produtos e o pad que é nosso.

Quem precisa do VID/PID do DualSense importa daqui e não escreve o literal. Uma revisão
de hardware com PID novo muda UM arquivo, e `scripts/check_numeros_da_sony.py` conta
quantas linhas ainda carregam o literal fora deste dono (a catraca só desce).

O pad virtual veste uma ROUPA (o Edge, o padrão, ou o DualSense de linha) e divide o PID
com um físico nas duas. Quem separa o físico do nosso nunca é o PID: é a posse (o
``HID_PHYS`` do uhid, o serial do gadget), com dono em `integrations/pad_usb.e_pad_nosso`.
"""

from __future__ import annotations

VENDOR_SONY = 0x054C

PID_DUALSENSE = 0x0CE6

PID_DUALSENSE_EDGE = 0x0DF2

PIDS_DUALSENSE = frozenset({PID_DUALSENSE, PID_DUALSENSE_EDGE})

PID_DO_PAD_VIRTUAL = PID_DUALSENSE_EDGE

ROUPA_EDGE = PID_DUALSENSE_EDGE

ROUPA_COMUM = PID_DUALSENSE

ROUPAS_DO_PAD = frozenset({ROUPA_EDGE, ROUPA_COMUM})

ROUPA_PADRAO = ROUPA_EDGE

PAR_DUALSENSE_FISICO = (VENDOR_SONY, PID_DUALSENSE)

HID_PHYS_DO_PAD = "hefesto-vpad"


def roupa_normalizada(roupa: object) -> int:
    """A roupa pedida, se for uma que o pad sabe vestir; qualquer outra coisa veste a padrão."""
    if isinstance(roupa, int) and not isinstance(roupa, bool) and roupa in ROUPAS_DO_PAD:
        return roupa
    return ROUPA_PADRAO


__all__ = [
    "HID_PHYS_DO_PAD",
    "PAR_DUALSENSE_FISICO",
    "PIDS_DUALSENSE",
    "PID_DO_PAD_VIRTUAL",
    "PID_DUALSENSE",
    "PID_DUALSENSE_EDGE",
    "ROUPAS_DO_PAD",
    "ROUPA_COMUM",
    "ROUPA_EDGE",
    "ROUPA_PADRAO",
    "VENDOR_SONY",
    "roupa_normalizada",
]
