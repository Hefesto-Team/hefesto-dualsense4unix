"""Lápide do shim `xlib_window` — retirado de propósito (CODIGO-MORTO-01, 29/07)."""
from __future__ import annotations

_MENSAGEM_LAPIDE = (
    "hefesto_dualsense4unix.integrations.xlib_window foi retirado "
    "(CODIGO-MORTO-01, 29/07): a XlibClient lia _NET_ACTIVE_WINDOW sem gate de "
    "foco, o defeito que o UX-02/FOCO-01 curaram. Use "
    "hefesto_dualsense4unix.integrations.window_detect.build_window_reader() "
    "para leitura contínua, ou window_detect.get_active_window_info() para "
    "leitura pontual."
)

raise ImportError(_MENSAGEM_LAPIDE)
