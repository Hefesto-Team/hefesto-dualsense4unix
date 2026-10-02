"""O que se acerta no AMBIENTE antes de a primeira janela GTK nascer."""
from __future__ import annotations

import os


def sanear_loaders_do_gdk_pixbuf() -> bool:
    """Descarta um `GDK_PIXBUF_MODULE_FILE` herdado que não saiba ler SVG."""
    caminho = os.environ.get("GDK_PIXBUF_MODULE_FILE")
    if not caminho:
        return False
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            cache = arquivo.read()
    except OSError:
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True

    modulos = [
        linha.strip().strip('"')
        for linha in cache.splitlines()
        if linha.strip().startswith('"/') and linha.rstrip().endswith('.so"')
    ]
    if modulos and all(not os.path.exists(m) or de_outro_confinamento(m) for m in modulos):
        del os.environ["GDK_PIXBUF_MODULE_FILE"]
        return True
    formatos = [
        linha for linha in cache.splitlines()
        if linha.strip() and not linha.lstrip().startswith(('"/', "#"))
    ]
    if not any("svg" in linha for linha in formatos):
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
