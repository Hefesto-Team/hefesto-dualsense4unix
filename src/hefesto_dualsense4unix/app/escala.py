"""A escala da fonte da interface: o dado e a leitura do disco, sem GTK."""
from __future__ import annotations

from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

CHAVE_ESCALA = "escala_fonte"

ESCALA_PADRAO = 3

ESCALA_MAXIMA = 8

DEGRAUS_DE_ESCALA: dict[str, int] = {
    "compacto": 0,
    "normal": ESCALA_PADRAO,
    "grande": 6,
}


def escala_gravada() -> int:
    """Delta de tamanho da fonte que está NO DISCO agora, sem cache."""
    bruto = load_gui_prefs().get(CHAVE_ESCALA, ESCALA_PADRAO)
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        logger.warning("theme_escala_invalida", valor=repr(bruto))
        bruto = ESCALA_PADRAO
    delta = int(bruto)
    if delta < 0 or delta > ESCALA_MAXIMA:
        logger.warning("theme_escala_fora_da_faixa", valor=delta)
        delta = max(0, min(ESCALA_MAXIMA, delta))
    return delta


def degrau_da_escala(delta: int) -> str:
    """O degrau de `DEGRAUS_DE_ESCALA` mais perto de `delta`."""
    return min(DEGRAUS_DE_ESCALA, key=lambda nome: abs(DEGRAUS_DE_ESCALA[nome] - delta))
