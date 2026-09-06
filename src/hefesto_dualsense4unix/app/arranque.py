"""O que se acerta no AMBIENTE antes de a primeira janela GTK nascer.

DE ONDE ISTO VEIO, e por que não morreu com a janela — 06/09/2026, `GTK-3`
---------------------------------------------------------------------------

Estas funções moravam no topo de `app/main.py`, o entry point da janela GTK que
a decisão dela (`D-0609-GTK-LEVA-INTEIRA`) aposentou: *"a ideia sempre foi
reaproveitar o que fiz no gtk e não apontar nada mais pra lá mas pro html"*.

**Nenhuma delas monta janela**, e é essa a régua que decide o que sai e o que
fica: elas acertam VARIÁVEL DE AMBIENTE de PROCESSO, e o processo da interface
nova é uma `Gtk.Window` com um `WebKit2.WebView` dentro — tem exatamente os dois
problemas que elas curam. `app/main.py` era o único chamador, e por isso elas
mudam de casa em vez de morrer: o conhecimento é medido, o endereço é que estava
errado.

QUEM CHAMA ISTO HOJE: NINGUÉM EM PYTHON, e a razão está medida
---------------------------------------------------------------

O caminho que ela clica é `packaging/*.desktop` → `interface.sh` → `run.sh
--gui` → `scripts/abrir_interface.py` → `interface/hefesto_vivo.py`, e o
`run.sh` já faz as DUAS curas **em shell, com critério grosso**, antes de o
Python subir:

* `run.sh:63-68` desarma o `GDK_PIXBUF_MODULE_FILE` quando TODOS os módulos do
  cache moram em `/snap` e o processo não está lá dentro;
* `run.sh:82-86` força `GDK_BACKEND=x11` no COSMIC **sem conferir se há X vivo**.

O que este módulo tem a mais é o critério FINO, e ele é o que a bancada mediu:
`forcar_xwayland_no_cosmic` **recusa** quando o `DISPLAY` existe e está morto
(T-02, ONDA0-Z7) — o caso em que forçar faz a janela não abrir; e
`sanear_loaders_do_gdk_pixbuf` também descarta o cache cujos `.so` são de OUTRO
confinamento, que é o caso em que o GTK **aborta o processo inteiro** em vez de
desenhar um ícone vazio.

**Ligar a versão fina ao lançador é mudança de comportamento e não foi pedida —
a `GTK-3` mudou o endereço, não o produto.** Quem for costurar o lançador novo
começa por `scripts/abrir_interface.py`, que já é quem veste prgname, WM_CLASS e
ícone no processo antes da primeira janela.

O QUE **NÃO** VEIO JUNTO, e está escrito para ninguém procurar
---------------------------------------------------------------

`_kill_previous_instances` e `_is_systemd_managed` ficaram em `app/main.py` e
morreram com ele. Eles matavam por `pgrep -f` **a janela anterior**, que é o que
deixou de existir; o mecanismo de instância única desta casa é
`utils/single_instance.py`, vivo e com régua própria
(`tests/unit/test_single_instance.py`). A lista de padrões continua onde estava,
em `utils.identidade.atual().padroes_de_matanca`.
"""
from __future__ import annotations

import os

#: O opt-out da cura do XWayland. O `portao_a_casa_sabe_e_o_produto_nao_faz`
#: cobra que toda chave declarada tenha endereço vivo, e este é o dela.
CHAVE_SEM_XWAYLAND = "HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND"


def x11_alcancavel(display: str, timeout: float = 0.2) -> bool:
    """Confere BARATO se há servidor X ouvindo em `display` (T-02, ONDA0-Z7).

    Sem abrir janela e sem `gi` — ela roda ANTES de qualquer import de
    `gi.repository`, cuja cadeia já abre um `GdkDisplay`: usar `gi` aqui faria o
    remédio virar a doença. Só sabe testar o caminho comum de displays LOCAIS
    (`:N` ou `:N.M`, socket UNIX em `/tmp/.X11-unix/X<N>`, medido ao vivo em
    23/08). Um display remoto (`host:N`) devolve `True` — a régua desta função é
    só RECUSAR diante de PROVA de que não há ninguém do outro lado; incerteza
    não é prova, e o padrão da casa é não mexer no ambiente sem saber.
    """
    numero = display[1:].split(".", 1)[0] if display.startswith(":") else ""
    if not numero.isdigit():
        return True
    import socket

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(f"/tmp/.X11-unix/X{numero}")
    except OSError:
        return False
    else:
        return True
    finally:
        sock.close()


def forcar_xwayland_no_cosmic() -> bool:
    """Força GDK_BACKEND=x11 (XWayland) quando a sessão é COSMIC E há X vivo.

    No cosmic-comp (Wayland nativo), os popups de GtkComboBox/GtkMenu abrem
    com fundo claro, mal-posicionados e com grab quebrado (fecham sozinhos,
    exigem "segurar o clique"). Rodar sob XWayland contorna o bug.

    IMPORTANTE: a própria sessão COSMIC do Pop!_OS exporta
    `GDK_BACKEND=wayland,x11` (lista de fallback que PREFERE wayland) — que é
    exatamente o que dispara o bug. Por isso sobrescrevemos esse valor; só não
    mexemos se já for `x11` puro ou se ela pediu opt-out via
    `HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND=1` (ex.: um COSMIC futuro que conserte
    o grab de popups e queira Wayland nativo de volta).

    T-02 (ONDA0-Z7, 24/08): a bancada mediu a janela NÃO ABRIR nesta máquina —
    `Gtk.init_check()` devolve `False` sob `GDK_BACKEND=x11` quando não há
    XWayland do outro lado, e o produto forçava sem conferir. Por isso, antes de
    sobrescrever, confere se `DISPLAY` existe E se há alguém ouvindo nele
    (`x11_alcancavel`, barata, sem abrir janela). Sem prova de X vivo, NÃO mexe
    em `GDK_BACKEND` — a tela sobe em Wayland nativo, com o bug de popup do
    cosmic-comp, que é infinitamente melhor que não subir.

    Devolve True se aplicou — quem chamar registra depois que o log subir, e é
    por isso que ela não loga sozinha: ela roda antes do `configure_logging`.
    """
    if os.environ.get(CHAVE_SEM_XWAYLAND) == "1":
        return False
    if os.environ.get("GDK_BACKEND", "") == "x11":
        return False  # já é XWayland puro — nada a fazer
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + os.environ.get("XDG_SESSION_DESKTOP", "")
    ).lower()
    if "cosmic" not in desktop:
        return False
    display = os.environ.get("DISPLAY")
    if not display:
        return False  # sem DISPLAY: não há X para forçar
    if not x11_alcancavel(display):
        return False  # DISPLAY presente e MORTO conta como inválido (item 7)
    os.environ["GDK_BACKEND"] = "x11"
    return True


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
    "CHAVE_SEM_XWAYLAND",
    "de_outro_confinamento",
    "forcar_xwayland_no_cosmic",
    "sanear_loaders_do_gdk_pixbuf",
    "x11_alcancavel",
]
