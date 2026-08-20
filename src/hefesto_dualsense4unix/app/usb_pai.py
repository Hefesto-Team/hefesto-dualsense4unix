"""Reexporta `integrations.usb_pai` — o módulo mudou de camada, não de dono.

MIC-DA-MESA-CHEIA-01 (20/08/2026). O casamento entre uma placa de som e o
controle que a pendura (o dispositivo USB pai) nasceu do lado da GUI porque foi
a janela que precisou dele primeiro: sem ele, mic e botão de saída sumiam de
TODOS os controles assim que havia dois no cabo (medido em 15/08).

Só que o DAEMON precisa exatamente da mesma resposta, e o daemon **não importa
nada de `app/`** — a camada é limpa e vai continuar sendo. Duplicar a lógica
criaria duas verdades sobre o mesmo sysfs, que é como esta casa fabrica
divergência silenciosa. Então a peça desceu para `integrations/`, que é a camada
neutra, e este arquivo fica como ponte para quem já importava daqui.

Nada mudou de comportamento: é o mesmo módulo, no mesmo estado, com outro
endereço.
"""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.usb_pai import (
    RAIZ_HIDRAW,
    RAIZ_SYSFS,
    dispositivo_usb_pai,
    nos_e_sysfs,
    usb_pai_por_no,
    usb_pai_por_uniq,
)

__all__ = [
    "RAIZ_HIDRAW",
    "RAIZ_SYSFS",
    "dispositivo_usb_pai",
    "nos_e_sysfs",
    "usb_pai_por_no",
    "usb_pai_por_uniq",
]
