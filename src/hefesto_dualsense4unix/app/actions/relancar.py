"""O que só vale quando o jogo reabre — a decisão, pura e sem GTK."""

from __future__ import annotations

from typing import Final, Literal

Escolha = Literal["fechar_e_abrir", "na_proxima_abertura", "cancelar"]

MARCADOR_PENDENTE: Final = "●"


def texto_do_pendente(*, modo: str | None = None, mascara: str | None = None) -> str:
    """A linha que diz o que ainda NÃO valeu — função pura, sem GTK."""
    partes = [p for p in (modo, mascara) if p]
    if not partes:
        return ""
    return f"{MARCADOR_PENDENTE} vai mudar para: " + ", ".join(partes)


TITULO: Final = "Posso fechar o jogo e abrir de novo?"

ROTULO_FECHAR: Final = "Aplicar agora e reiniciar o jogo"


