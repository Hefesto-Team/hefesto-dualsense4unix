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


# ---------------------------------------------------------------------------
# BUG-GUI-COSMIC-WIDGET-CONTRAST-01: botões/toggles/dropdowns legíveis no COSMIC
# (tema claro do sistema). Regex confirma a entrega: fundo sólido (não
# `transparent`), estado :checked p/ toggle, combobox display coberto.
# ---------------------------------------------------------------------------


def test_botao_tem_fundo_solido_nao_transparente() -> None:
    """A regra base de `button` deve usar fundo sólido escuro, NÃO transparent.

    Causa-raiz do branco-sobre-branco no COSMIC: `background-color: transparent`
    fazia o botão exibir o container claro do tema do sistema atrás dele.
    """
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"\.hefesto-dualsense4unix-window\s+button\s*\{([^}]*)\}",
        conteúdo,
    )
    assert m is not None, "Regra base '.hefesto-dualsense4unix-window button' ausente"
    corpo = m.group(1)
    assert "transparent" not in corpo, (
        "button não deve usar background-color: transparent (vaza tema claro do COSMIC)"
    )
    assert re.search(r"background-color:\s*#[0-9a-fA-F]{3,6}", corpo), (
        "button deve ter background-color sólido (hex) na regra base"
    )


def test_toggle_checked_destacado() -> None:
    """Deve existir regra :checked para distinguir a política de rumble ativa."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    assert re.search(
        r"\.hefesto-dualsense4unix-window\s+button:checked\s*\{",
        conteúdo,
    ), "Regra '.hefesto-dualsense4unix-window button:checked' ausente (toggle ativo)"


def test_combobox_display_coberto() -> None:
    """O display fechado do combobox deve ter fundo/cor explícitos (não herdar claro)."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    assert re.search(
        r"\.hefesto-dualsense4unix-window\s+combobox\s+button\b",
        conteúdo,
    ), "Cobertura do display do combobox (.hefesto-dualsense4unix-window combobox button) ausente"


def test_footer_btn_sobre_fundo_escuro() -> None:
    """Os .btn-* do footer devem reafirmar fundo escuro sólido sob o gradiente.

    Antes o gradiente alpha-baixo era pintado sobre transparent => sumia no
    claro do COSMIC.
    """
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    for cls in ("btn-apply", "btn-save", "btn-import", "btn-restore"):
        m = re.search(
            r"\.hefesto-dualsense4unix-window\s+button\."
            + re.escape(cls)
            + r"\s*\{([^}]*)\}",
            conteúdo,
        )
        assert m is not None, f"Regra do footer .{cls} (escopada na window) ausente"
        assert "background-color" in m.group(1), (
            f".{cls} deve fixar background-color escuro sob o gradiente"
        )


def test_containers_internos_cobertos() -> None:
    """Containers genéricos devem ser cobertos sem quebrar o card (#21222c)."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    # box/frame/grid devem aparecer escopados na window com :not(card)
    assert re.search(
        r"\.hefesto-dualsense4unix-window\s+box:not\(\.hefesto-dualsense4unix-card\)",
        conteúdo,
    ), "Regra de containers (box:not(.card)) ausente"
    # o card NÃO pode ter sido transformado em transparente
    m = re.search(r"\.hefesto-dualsense4unix-card\s*\{([^}]*)\}", conteúdo)
    assert m is not None and "#21222c" in m.group(1), (
        "Card deve manter background #21222c (não pode ser sobrescrito p/ transparent)"
    )


def test_theme_css_sem_regra_at_rule_proibida() -> None:
    """GTK3 falha a carga inteira com a at-rule de query proibida.

    O arquivo pode documentar em comentários POR QUE não a usa; este teste
    ignora comentários (/* ... */) e procura a at-rule real fora deles.
    """
    at_rule = "@" + "med" + "ia"  # monta a at-rule proibida por partes
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    css_sem_blocos = re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL)
    assert at_rule not in css_sem_blocos, (
        "at-rule de query quebra o parser CSS do GTK3 (falha a carga inteira)"
    )
