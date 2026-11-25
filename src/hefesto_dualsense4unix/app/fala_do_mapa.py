"""fala_do_mapa.py — o número medido que a tela mostra e a célula do mapa que o diz."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Numero:
    """Amarra uma constante Python MEDIDA a uma célula em prosa do mapa (Z6-08)."""

    constante: str
    valor: float
    chave: str
    coluna: str

    def __post_init__(self) -> None:
        if isinstance(self.valor, bool) or not isinstance(self.valor, (int, float)):
            raise TypeError(f"Numero.valor tem de ser numérico, não {self.valor!r}.")
        if not self.constante.strip() or not self.chave.strip() or not self.coluna.strip():
            raise ValueError("Numero.constante/chave/coluna não podem ser vazios.")


def formata_pt_br(valor: float) -> str:
    """`260.4` → `"260,4"` — uma casa decimal, vírgula. **O DONO ÚNICO.**"""
    return f"{valor:.1f}".replace(".", ",")
