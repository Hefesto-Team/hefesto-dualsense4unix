"""O leitor único de texto do ``/sys``: ``""`` em qualquer erro, o sysfs some sob a mão."""

from __future__ import annotations


def ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; ``""`` em qualquer erro (o nó some entre o listdir e o open)."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = ["ler_texto"]
