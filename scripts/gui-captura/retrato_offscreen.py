#!/usr/bin/env python3
"""Renderiza as nove abas num GtkOffscreenWindow de 1920x1080 e salva PNG.

É o enquadramento da janela maximizada dela, sem depender do compositor - o
COSMIC recusou maximizar por atalho, por duplo clique e por F11 nesta sessão.
E o mesmo método do retrato das nove abas de 26/07, que e a convenção da casa.

uso: retrato_offscreen.py <diretório-de-saída>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# A raiz sai do PRÓPRIO arquivo, nunca de um caminho de disco de ninguém: este
# script mora em `scripts/gui-captura/`, dois níveis abaixo da raiz. Antes de
# 22/08/2026 o default era o `$HOME` da mantenedora, e só resolvia aqui porque
# há um symlink — quem clonasse o repo e seguisse o `CLAUDE.md` morria no
# `add_from_file` do `main.glade` na primeira tentativa
# (UMA-FAIXA-NÃO-É-UM-FABRICANTE-01, A4). O vizinho `retratar_abas.py` já fazia
# assim. `HEFESTO_RAIZ` continua vencendo, para quem roda de fora da árvore.
_RAIZ_PADRAO = Path(__file__).resolve().parents[2]
RAIZ = Path(os.environ.get("HEFESTO_RAIZ") or _RAIZ_PADRAO)
sys.path.insert(0, str(RAIZ / "src"))

GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"
LARGURA, ALTURA = 1920, 1080


def aplicar_tema(janela) -> str:
    """O apply_theme mudou de assinatura entre versões; tenta as duas."""
    try:
        from hefesto_dualsense4unix.app.theme import apply_theme
    except Exception as exc:
        return f"tema indisponível: {exc}"
    for tentativa in (lambda: apply_theme(janela), lambda: apply_theme()):
        try:
            tentativa()
            return "tema aplicado"
        except TypeError:
            continue
        except Exception as exc:
            return f"tema falhou: {exc}"
    return "tema não aplicado"


def assentar() -> None:
    for _ in range(4):
        while Gtk.events_pending():
            Gtk.main_iteration()


def main(destino: str) -> int:
    saida = Path(destino)
    saida.mkdir(parents=True, exist_ok=True)

    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    notebook = builder.get_object("main_notebook")

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(LARGURA, ALTURA)
    print(aplicar_tema(janela))
    janela.show_all()
    assentar()

    for i in range(notebook.get_n_pages()):
        notebook.set_current_page(i)
        assentar()
        página = notebook.get_nth_page(i)
        rotulo = (notebook.get_tab_label_text(página) or f"página{i}").lower()
        rotulo = (
            rotulo.replace(" ", "-")
            .replace("ç", "c")
            .replace("ã", "a")
            .replace("í", "i")
            .replace("ú", "u")
        )
        pix = janela.get_pixbuf()
        nome = saida / f"aba-{i:02d}-{rotulo}.png"
        pix.savev(str(nome), "png", [], [])
        aloc = página.get_allocation()
        nat = página.get_preferred_height()[1]
        print(
            f"  {i} {rotulo:<16} recebe={aloc.height:>5}  "
            f"natural={nat:>5}  vao={aloc.height - nat:>5}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/retrato"))
