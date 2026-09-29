"""O que se acerta no AMBIENTE antes de a primeira janela GTK nascer.

DE ONDE ISTO VEIO — 06/09/2026, `GTK-3`
---------------------------------------

Estas funções moravam no topo de `app/main.py`, o entry point da janela GTK que
a decisão dela (`D-0609-GTK-LEVA-INTEIRA`) aposentou: *"a ideia sempre foi
reaproveitar o que fiz no gtk e não apontar nada mais pra lá mas pro html"*.
Elas não montam janela: acertam VARIÁVEL DE AMBIENTE de PROCESSO, e o processo
da interface nova é uma `Gtk.Window` com um `WebKit2.WebView` dentro.

QUEM CHAMA ISTO HOJE — 28/09/2026
---------------------------------

O caminho que ela clica é `packaging/*.desktop` → `run.sh --gui` →
`scripts/abrir_interface.py` → `interface/hefesto_vivo.py`. O
`scripts/abrir_interface.py` chama `sanear_loaders_do_gdk_pixbuf` antes de
qualquer import de `gi.repository`
(O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01). O `run.sh` já faz uma versão GROSSA da
mesma limpeza em shell (só desarma quando todos os módulos do cache moram em
`/snap`), e ela continua servindo o que roda antes do Python subir; a FINA, que
descarta também o cache cujos `.so` são de outro confinamento, é esta.

O QUE SAIU, e está escrito para ninguém procurar
------------------------------------------------

`forcar_xwayland_no_cosmic` e `x11_alcancavel` saíram em 28/09/2026. A primeira
forçava `GDK_BACKEND=x11` em toda sessão COSMIC, e a razão dela (os popups de
`GtkMenu`/`GtkComboBox` no cosmic-comp) morreu com a janela GTK: a interface
nova não tem nenhum dos dois. Por ordem dela de 19/09 (*"o certo é tirar dos
dois. Faça"*), o XWayland deixou de ser o padrão no `run.sh` e no `.desktop`, e
ligar a função ao lançador DESFARIA essa ordem. O opt-in que fica é o do
`run.sh` (`HEFESTO_DUALSENSE4UNIX_XWAYLAND=1`, ou o `--force-xwayland` do
`install.sh`). A chave `HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND`, que só esta
função lia, saiu junto.

`_kill_previous_instances` e `_is_systemd_managed` ficaram em `app/main.py` e
morreram com ele. O mecanismo de instância única desta casa é
`utils/single_instance.py`.
"""
from __future__ import annotations

import os


def sanear_loaders_do_gdk_pixbuf() -> bool:
    """Descarta um `GDK_PIXBUF_MODULE_FILE` herdado que não saiba ler SVG.

    BUG-TRAY-ICONE-INVISIVEL-01 (medido em 18/08/2026, Pop!_OS 22.04): o snap do
    terminal exporta essa variável apontando para um cache de loaders PRÓPRIO,
    dentro do confinamento dele. Todo processo GTK lançado daquele terminal
    herda o apontamento e perde o loader de SVG do sistema — o `rsvg-convert`
    renderiza o ícone sem reclamar, e o mesmo arquivo falha no `GdkPixbuf` com
    "Couldn't recognize the image file format".

    O estrago é silencioso e não é só o ícone da bandeja, que some da barra sem
    erro nenhum no log: qualquer SVG da tela cai junto — e são 38 glifos de
    botão nas dez abas.

    A variável só é removida quando o cache apontado REALMENTE não declara svg —
    quem tiver um cache próprio legítimo e completo continua com ele de pé. E a
    remoção tem de acontecer ANTES de o GdkPixbuf inicializar: depois disso ele
    já leu o cache e a correção chega tarde.
    """
    caminho = os.environ.get("GDK_PIXBUF_MODULE_FILE")
    if not caminho:
        return False
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            cache = arquivo.read()
    except OSError:
        # Ilegível conta como inútil: melhor cair no padrão do sistema.
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True

    # Não basta o cache MENCIONAR svg — o do snap menciona. O que importa é se
    # os módulos que ele aponta são carregáveis AQUI. Um loader empacotado
    # dentro do confinamento traz o librsvg dele, ligado a uma glibc mais nova
    # que a do hospedeiro, e o dlopen falha com "version `GLIBC_2.xx' not
    # found". O GTK não trata isso como ícone faltando: ele aborta o processo
    # inteiro no `ensure_surface_for_gicon`, e a janela morre ao abrir.
    modulos = [
        linha.strip().strip('"')
        for linha in cache.splitlines()
        if linha.strip().startswith('"/') and linha.rstrip().endswith('.so"')
    ]
    if modulos and all(not os.path.exists(m) or de_outro_confinamento(m) for m in modulos):
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True
    if "svg" not in cache:
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True
    return False


def de_outro_confinamento(modulo: str) -> bool:
    """O módulo mora dentro de um pacote confinado que não é o nosso processo."""
    for raiz in ("/snap/", "/var/lib/snapd/snap/"):
        if modulo.startswith(raiz):
            return not (os.environ.get("SNAP") or "").startswith(raiz)
    return False


__all__ = [
    "de_outro_confinamento",
    "sanear_loaders_do_gdk_pixbuf",
]
