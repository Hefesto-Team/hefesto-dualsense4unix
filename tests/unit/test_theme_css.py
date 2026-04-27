"""Testes para src/hefesto_dualsense4unix/gui/theme.css e src/hefesto_dualsense4unix/app/theme.py.

Checks:
  (a) arquivo theme.css existe no path esperado;
  (b) Gtk.CssProvider carrega sem levantar exceção (ambiente headless);
  (c) seletores esperados estão presentes no conteúdo do CSS.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "gui" / "theme.css"  # noqa: E501

SELECTORS_ESPERADOS = [
    ".hefesto-dualsense4unix-window",
    "#bd93f9",
    ".hefesto-dualsense4unix-card",
    ".hefesto-dualsense4unix-log",
    ".hefesto-dualsense4unix-status-ok",
    ".hefesto-dualsense4unix-accent-purple",
]


def test_theme_css_existe() -> None:
    """Arquivo theme.css deve existir no diretório gui/."""
    assert CSS_PATH.exists(), f"theme.css não encontrado em {CSS_PATH}"
    assert CSS_PATH.stat().st_size > 0, "theme.css está vazio"


def test_theme_css_carrega_sem_erro() -> None:
    """Gtk.CssProvider deve carregar o theme.css sem GLib.Error.

    Pula se GTK não está disponível ou se o módulo foi mockado pela suite
    (AttributeError indica mock parcial instalado por outro teste).
    """
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        if not hasattr(Gtk, "CssProvider"):
            pytest.skip("Gtk.CssProvider indisponível neste ambiente (mock parcial)")

        provider = Gtk.CssProvider()
        # load_from_path levanta GLib.Error em CSS inválido
        provider.load_from_path(str(CSS_PATH))
    except (ImportError, ValueError, AttributeError):
        pytest.skip("GTK não disponível neste ambiente")


def test_theme_css_contem_selectors_esperados() -> None:
    """CSS deve conter todos os seletores canônicos da paleta Drácula."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    faltando = [s for s in SELECTORS_ESPERADOS if s not in conteúdo]
    assert not faltando, f"Seletores ausentes no theme.css: {faltando}"


def test_theme_css_cor_roxa_presente() -> None:
    """CSS deve conter a cor roxa Drácula #bd93f9 ao menos uma vez."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    matches = re.findall(r"#bd93f9", conteúdo, re.IGNORECASE)
    assert len(matches) >= 1, "Cor #bd93f9 (roxo Drácula) não encontrada no CSS"
