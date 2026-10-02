"""Qual é a área de trabalho desta sessão — e o que dizer sobre a barra do sistema."""
from __future__ import annotations

import os
from collections.abc import Mapping

from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs

CHAVE_AMBIENTE = "ambiente_corrigido"

AMBIENTES: tuple[tuple[str, str], ...] = (
    ("cosmic", "COSMIC"),
    ("gnome", "GNOME"),
    ("outro", "Outro"),
)

NOMES_DE_TELA: dict[str, str] = dict(AMBIENTES)

_VARIAVEIS_DA_SESSAO = ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP")


def ambiente_lido(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O que a sessão declara, cru, como `tray.py:92-97` já lê."""
    fonte = os.environ if variaveis is None else variaveis
    partes = [fonte.get(nome, "") for nome in _VARIAVEIS_DA_SESSAO]
    return ":".join(parte for parte in partes if parte)


def ambiente_normalizado(bruto: str | None) -> str:
    """Reduz a declaração crua a um dos três ids de `AMBIENTES`."""
    texto = (bruto or "").lower()
    if "cosmic" in texto:
        return "cosmic"
    if "gnome" in texto:
        return "gnome"
    return "outro"


def ambiente_efetivo(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O ambiente que vale para a tela: a correção dela vence a detecção."""
    escolha = load_gui_prefs().get(CHAVE_AMBIENTE)
    if isinstance(escolha, str) and escolha in NOMES_DE_TELA:
        return escolha
    return ambiente_normalizado(ambiente_lido(variaveis=variaveis))


__all__ = [
    "AMBIENTES",
    "CHAVE_AMBIENTE",
    "NOMES_DE_TELA",
    "ambiente_efetivo",
    "ambiente_lido",
    "ambiente_normalizado",
]
