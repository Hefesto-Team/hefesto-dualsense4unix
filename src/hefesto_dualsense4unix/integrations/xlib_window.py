"""Lápide do shim `xlib_window` — retirado de propósito (CODIGO-MORTO-01, 29/07).

Este módulo nasceu como shim de compatibilidade da camada 1 do ADR-014 e virou
código morto: nenhum código de produção o importava. O problema é que ele não
era só inútil — a classe `XlibClient` que morava aqui lia o `_NET_ACTIVE_WINDOW`
da raiz **sem gate de foco**, exatamente o defeito que o UX-02 e o FOCO-01
curaram no backend vivo (`integrations/window_backends/xlib.py`, que só aceita a
leitura quando o `get_input_focus()` e o `_NET_ACTIVE_WINDOW` concordam, subindo
a árvore X até o primeiro top-level com `WM_CLASS`). Quem importasse este módulo
reintroduziria o ping-pong de perfil sem perceber, com a suíte verde.

A lápide fica no lugar do arquivo apagado porque nesta casa o registro do porquê
vale mais do que a linha em branco: quem procurar por `xlib_window` — num script
antigo, num traceback, num `grep` — cai aqui e lê o substituto, em vez de
receber um `ModuleNotFoundError` mudo. E o `raise` no topo garante que a leitura
cega não volta por engano: o erro é no import, não numa leitura errada às 2 Hz.

Substituto para uso contínuo (autoswitch, poll):

    from hefesto_dualsense4unix.integrations.window_detect import build_window_reader

    ler_janela = build_window_reader()   # backend instanciado UMA vez
    info = ler_janela()                  # wm_class / wm_name / pid / exe_basename

Para leitura pontual (CLI, doctor), `window_detect.get_active_window_info()`
mantém a assinatura do antigo `xlib_window.get_active_window_info`.
"""
from __future__ import annotations

#: Mensagem do erro de import. Cita o substituto de propósito: o valor de uma
#: lápide é apontar para onde ir, e é isso que o teste desta sprint exige.
_MENSAGEM_LAPIDE = (
    "hefesto_dualsense4unix.integrations.xlib_window foi retirado "
    "(CODIGO-MORTO-01, 29/07): a XlibClient lia _NET_ACTIVE_WINDOW sem gate de "
    "foco, o defeito que o UX-02/FOCO-01 curaram. Use "
    "hefesto_dualsense4unix.integrations.window_detect.build_window_reader() "
    "para leitura contínua, ou window_detect.get_active_window_info() para "
    "leitura pontual."
)

raise ImportError(_MENSAGEM_LAPIDE)
