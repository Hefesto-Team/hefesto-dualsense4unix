#!/usr/bin/env python3
"""ver.py — a interface nova, para ela clicar.

As dez abas do mockup dentro de uma janela GTK3 de verdade, com o `WebView` que
a decisão de 29/08/2026 escolheu (`D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK`).

Não é o produto: é o desenho aprovado rodando no motor que vai carregá-lo, para
ela ver e apontar o que está errado antes de alguém ligar um dado sequer.

    src/hefesto_dualsense4unix/interface/ver.py            # abre na Jogar; a tira navega
    src/hefesto_dualsense4unix/interface/ver.py 08         # abre já na Conexões

**A JANELA NASCE NA TELA DELA, E É DE PROPÓSITO** — ela é quem manda abrir. Todo
o resto desta casa parqueia no workspace `OS`; este não, porque o objetivo é
justamente que ela veja.

OS QUATRO PINOS SÃO OBRIGATÓRIOS, e a razão foi medida em 29/08: com o GTK4
instalado ao lado, um `from gi.repository import Gdk` sem pino carrega o 4.0 e
mata o Gtk 3.0 com `ImportError`. A ordem importa — o `Gdk` depois do `Gtk`.
"""
from __future__ import annotations

import pathlib
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gtk, WebKit2  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

# ABRE A BANCADA (`mockup/`) — o desenho de hoje, que é o que ela olha.
D = onde.BANCADA

#: As dez, na ordem da tira que ela aprovou (`D-A-ORDEM-DA-TIRA-E-A-DO-MOCKUP`).
ABAS = [
    ("Jogar", "01-jogar.html"),
    ("Controles", "02-controles.html"),
    ("Gatilhos", "03-gatilhos.html"),
    ("Iluminação", "04-iluminacao.html"),
    ("Vibração", "05-vibracao.html"),
    ("Navegação", "06-navegacao.html"),
    ("Lançadores", "07-lancadores.html"),
    ("Conexões", "08-conexoes.html"),
    ("Sistema", "09-sistema.html"),
    ("Perfis", "10-perfis.html"),
]

#: A janela do produto. O mockup foi desenhado para caber exatamente aqui.
LARGURA, ALTURA = 1180, 757


def _pagina(arquivo: str) -> Gtk.Widget:
    """O `WebView` com o HTML, sem cromo de navegador.

    É UM SÓ para as dez abas, porque a tira do desenho navega por `href` — o
    WebView troca de página sozinho. Medido em 29/08: a primeira carga leva ~1 s
    (fria) e as trocas seguintes 15-79 ms, então não há o que pré-carregar.
    """
    view = WebKit2.WebView()
    caminho = D / arquivo

    # A `.nota` é o caderno de decisões que cada mockup carrega no fim: ela é
    # para quem lê o arquivo, não para quem olha a tela. O `olhar.py` a esconde
    # pelo mesmo motivo, e aqui a régua tem de ser a mesma.
    folha = WebKit2.UserStyleSheet(
        ".nota{display:none !important}",
        WebKit2.UserContentInjectedFrames.TOP_FRAME,
        WebKit2.UserStyleLevel.USER,
        None,
        None,
    )
    view.get_user_content_manager().add_style_sheet(folha)

    # `<select>` — MEDIDO em 29/08 e é o preço conhecido desta rota: o
    # WebKitGTK relata as cores do autor e desenha o tema do SISTEMA, o que sai
    # como caixa BRANCA com texto quase invisível. `appearance:none` devolve o
    # controle ao CSS dela. São 117 nas dez abas; sem isto ela veria um defeito
    # que não é do desenho.
    view.get_user_content_manager().add_style_sheet(
        WebKit2.UserStyleSheet(
            "select{appearance:none;-webkit-appearance:none}",
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserStyleLevel.USER,
            None,
            None,
        )
    )

    # A DICA DA CASA TAMBÉM AQUI — TOOLTIP-C1, 11/09/2026, e ela não é enfeite
    # neste visor: ele existe para ela OLHAR o desenho e apontar o que está
    # errado, e a dica é metade do que há para olhar (665 `title` e 1.756
    # `<title>` de SVG nas dez páginas). Um visor que ainda usasse o popup do
    # sistema mostraria a ela uma tela que o produto já não tem.
    #
    # POR `UserScript`, e não por uma chamada depois da carga: este visor não
    # tem tique nem ponte para reinstalar nada, e a tira do desenho navega
    # sozinha por `href` — a camada morre com o documento a cada troca de aba.
    # O `UserScript` nasce com cada página, que é exatamente o que o
    # `_instalado` do piloto faz do outro lado.
    from hefesto_dualsense4unix.interface.hefesto_vivo import DICA_DA_CASA

    view.get_user_content_manager().add_script(
        WebKit2.UserScript(
            DICA_DA_CASA,
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.END,
            None,
            None,
        )
    )

    view.load_uri(caminho.as_uri())
    return view


def main() -> int:
    inicial = "01-jogar.html"
    if len(sys.argv) > 1:
        alvo = sys.argv[1].zfill(2)
        for _, arquivo in ABAS:
            if arquivo.startswith(alvo):
                inicial = arquivo
                break

    if not (D / inicial).exists():
        print(f"não achei {inicial}", file=sys.stderr)
        print("rode antes: src/hefesto_dualsense4unix/interface/regerar.py", file=sys.stderr)
        return 1

    # A TRAVA DA TELA DELA — 02/09/2026. Este visor abre VISÍVEL de propósito
    # (é ela quem manda abrir, e o fim dele é ser visto), então aqui a trava
    # RECUSA em vez de esconder: abrir oculto um visor que existe para ser
    # olhado devolveria uma janela que ninguém vê e um sucesso que mente.
    #
    # Quem exporta `HEFESTO_SEM_JANELA` é quem trabalha NA máquina dela — uma
    # leva de agente, um portão, um ensaio. Nesse ambiente, o certo é não abrir.
    from hefesto_dualsense4unix.gui.ponte_da_tela import (
        SEM_JANELA_NA_TELA,
        janela_proibida_na_tela,
    )

    if janela_proibida_na_tela():
        print(
            f"recusado: {SEM_JANELA_NA_TELA} está no ambiente, e este visor só "
            "serve aberto na tela dela.\n"
            "Para OLHAR sem aparecer, use o piloto com `--oculta --foto`:\n"
            "  src/hefesto_dualsense4unix/interface/hefesto_vivo.py "
            f"--oculta --abre {inicial} --segundos 8 --foto /tmp/aba.png",
            file=sys.stderr,
        )
        return 2

    janela = Gtk.Window(title="Hefesto — a interface nova (mockup no motor de verdade)")
    janela.set_default_size(LARGURA, ALTURA)
    janela.connect("destroy", Gtk.main_quit)

    # A BARRA DE TÍTULO É DO APP, E É POR ISSO QUE ELA PARECE COSMIC.
    #
    # Pedido dela, 29/08: *"os botoes de navegacao da interface minimizar
    # maximizar e fechar tem que obedecer o mesmo estilo do cosmic"*.
    #
    # Sem `set_titlebar`, a janela recebe decoracao do SERVIDOR: o compositor
    # desenha os botoes com o desenho dele e na posicao do
    # `org.gnome.desktop.wm.preferences button-layout`, que nesta maquina esta
    # em `close,maximize,minimize:` — os dois pontos no fim mandam tudo para a
    # ESQUERDA, e foi o que ela viu. Os apps do COSMIC (o terminal, o gestor de
    # arquivos) desenham a própria barra e poem os botoes a DIREITA.
    #
    # Com `Gtk.HeaderBar` a janela passa a desenhar a própria decoracao (CSD),
    # que e o que todo app GTK moderno faz e o que o COSMIC espera — e os
    # botoes ganham o tema do sistema em vez do desenho do compositor.
    barra = Gtk.HeaderBar()
    barra.set_show_close_button(True)
    # O NOME INTEIRO NA BARRA — 11/09/2026, ordem dela: *"no nome da
    # janela não conseguimos deixar Hefesto - DualSense4Unix ao invés de só
    # hefesto?"*  (noqa-acento) citação literal dela
    #
    # O `<h1>` das dez páginas já dizia exatamente isto; quem ficou para
    # trás foi a barra da janela, que é o primeiro lugar em que o produto
    # se apresenta.
    #
    # A DÍVIDA FECHOU — `F6-O-NOME-TEM-UM-DONO`, 11/09/2026. Esta linha e a
    # irmã dela na ponte da tela nasceram com o nome DIGITADO porque
    # `utils/identidade.py` escrevia o `S` do DualSense em minúscula, em 427
    # linhas de 174 arquivos, e ler do dono poria a grafia errada na barra
    # dela. A grafia foi curada e o dono passou a carregar a string EXATA que
    # a barra mostra — travessão incluído. Agora a barra LÊ. Quem digitar de
    # novo é barrado por `scripts/check_a_grafia_do_nome.py`.
    from hefesto_dualsense4unix.utils import identidade

    barra.set_title(identidade.atual().nome_longo)
    barra.set_subtitle("a interface nova · mockup no motor de verdade")
    janela.set_titlebar(barra)

    # UM WebView, SEM `Gtk.Notebook`. A primeira versão punha um notebook do GTK
    # por cima, e ela viu o defeito na hora: **as abas apareciam duas vezes** —
    # a tira do GTK em cima e a tira do desenho dentro.
    #
    # E o notebook nunca foi necessário: a tira do mockup já é
    # `<a href="02-controles.html">`, ou seja, ela JÁ NAVEGA. O WebView segue o
    # link relativo e troca de aba sozinho, que é exatamente como o produto vai
    # se comportar quando a tira for a tira de verdade.
    view = _pagina(inicial)
    janela.add(view)
    janela.show_all()
    Gtk.main()
    return 0
