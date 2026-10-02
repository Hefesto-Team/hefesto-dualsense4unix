"""Testes para src/hefesto_dualsense4unix/gui/theme.css e src/hefesto_dualsense4unix/app/theme.py.
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


def _tokens_definidos(conteúdo: str) -> dict[str, str]:
    """Mapa `nome -> hex` de todo `@define-color` do arquivo."""
    return {
        nome: cor
        for nome, cor in re.findall(
            r"@define-color\s+(\w+)\s+(#[0-9a-fA-F]{3,8})\s*;", conteúdo
        )
    }


def _cor_de_fundo_sólida(corpo: str, conteúdo: str) -> str | None:
    """Hex do `background-color` de um corpo de regra, resolvendo token."""
    m = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8}|@\w+)\s*;", corpo)
    if m is None:
        return None
    valor = m.group(1)
    if valor.startswith("#"):
        return valor
    return _tokens_definidos(conteúdo).get(valor[1:])


def test_theme_css_existe() -> None:
    """Arquivo theme.css deve existir no diretório gui/."""
    assert CSS_PATH.exists(), f"theme.css não encontrado em {CSS_PATH}"
    assert CSS_PATH.stat().st_size > 0, "theme.css está vazio"


def test_theme_css_carrega_sem_erro() -> None:
    """Gtk.CssProvider deve carregar o theme.css sem GLib.Error."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        if not hasattr(Gtk, "CssProvider"):
            pytest.skip("Gtk.CssProvider indisponível neste ambiente (mock parcial)")

        provider = Gtk.CssProvider()
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


def test_botao_tem_fundo_solido_nao_transparente() -> None:
    """A regra base de `button` deve usar fundo sólido escuro, NÃO transparent."""
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
    assert _cor_de_fundo_sólida(corpo, conteúdo) is not None, (
        "button deve ter background-color sólido (hex ou token @define-color) na regra base"
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
    """Os .btn-* do footer devem reafirmar fundo escuro sólido sob o gradiente."""
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
    """Containers genéricos devem ser cobertos sem quebrar o card."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    assert re.search(
        r"\.hefesto-dualsense4unix-window\s+box:not\(\.hefesto-dualsense4unix-card\)",
        conteúdo,
    ), "Regra de containers (box:not(.card)) ausente"
    m = re.search(r"\.hefesto-dualsense4unix-card\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra .hefesto-dualsense4unix-card ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) == "#282a36", (
        "Card deve ter background sólido @bg (#282a36) — mais CLARO que a janela "
        "(@app_bg #21222c), senão o card afunda em vez de flutuar"
    )


def test_card_declarado_uma_vez_so() -> None:
    """`.hefesto-dualsense4unix-card` tinha DUAS declarações."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    sem_comentarios = re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL)
    declarações = re.findall(
        r"^\s*\.hefesto-dualsense4unix-card\s*\{", sem_comentarios, re.MULTILINE
    )
    assert len(declarações) == 1, (
        f"`.hefesto-dualsense4unix-card` declarada {len(declarações)}x — "
        "unifique numa regra só"
    )


def test_hierarquia_de_profundidade() -> None:
    """Quatro níveis de superfície, do fundo para a frente."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    tokens = _tokens_definidos(conteúdo)
    esperado = {
        "app_bg": "#21222c",
        "chrome": "#242630",
        "bg": "#282a36",
        "elevated": "#2b2d3a",
        "border_soft": "#343746",
    }
    for nome, hexa in esperado.items():
        assert tokens.get(nome, "").lower() == hexa, (
            f"token @{nome} deveria valer {hexa}, veio {tokens.get(nome)!r}"
        )

    m = re.search(r"\.hefesto-dualsense4unix-window\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra .hefesto-dualsense4unix-window ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) == "#21222c", (
        "o fundo da janela é @app_bg (#21222c) — mais fundo que o card"
    )

    assert "@chrome" in re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL), (
        "token @chrome definido mas nunca aplicado — o cromo continua chapado"
    )


def test_log_textview_nao_herda_o_branco_do_sistema() -> None:
    """BUG-GUI-LOG-TEXTVIEW-BRANCO-01."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    sem_comentarios = re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL)
    assert "textview.hefesto-dualsense4unix-log" in sem_comentarios, (
        "falta o seletor direto textview.hefesto-dualsense4unix-log "
        "(a classe está no próprio textview, não num container)"
    )
    assert re.search(
        r"textview\.hefesto-dualsense4unix-log\s+text\b", sem_comentarios
    ), "falta cobrir o nó filho `text` do textview (é ele que pinta o fundo)"


def test_dim_label_definida() -> None:
    """`.dim-label` é usada em ~20 lugares e não existia no theme.css."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"^\.dim-label\s*\{([^}]*)\}", conteúdo, re.MULTILINE)
    assert m is not None, "`.dim-label` não definida no theme.css"
    corpo = m.group(1)
    assert "opacity" in corpo and "1" in corpo, (
        "`.dim-label` precisa de `opacity: 1` p/ vencer o 0.55 do tema do sistema"
    )
    assert re.search(r"color:\s*@(text_muted|text_soft|comment)", corpo), (
        "a cor de `.dim-label` deve sair de um token de texto do design"
    )


def test_escala_tipografica_existe() -> None:
    """C2: os tamanhos de fonte são NOMEADOS e absolutos."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    ordem_decrescente = [
        ".hefesto-titulo",
        ".hefesto-titulo-painel",
        ".hefesto-titulo-secao",
        ".hefesto-corpo",
        ".hefesto-rotulo",
        ".hefesto-rotulo-longo",
        ".hefesto-dica",
        ".hefesto-selo",
    ]
    piso_px = 11.0

    def _tamanho_do_degrau(classe: str) -> float:
        m = re.search(
            r"^" + re.escape(classe) + r"[^{]*\{([^}]*)\}", conteúdo, re.MULTILINE
        )
        assert m is not None, f"degrau {classe} ausente da escala tipográfica"
        tam = re.search(r"font-size:\s*([0-9]+(?:\.[0-9]+)?)px", m.group(1))
        assert tam is not None, (
            f"{classe} precisa de `font-size` ABSOLUTO em px — tamanho relativo "
            f"de Pango depende da fonte da distribuição; corpo: "
            f"{m.group(1).strip()!r}"
        )
        return float(tam.group(1))

    fora_da_cadeia = [
        ".hefesto-rotulo-secao",
        ".hefesto-subtitulo",
        ".hefesto-micro",
        ".hefesto-kicker",
        ".hefesto-valor-mono",
        ".hefesto-valor-mono-peq",
    ]

    anterior: float | None = None
    for classe in ordem_decrescente:
        atual = _tamanho_do_degrau(classe)
        if anterior is not None:
            assert atual <= anterior, (
                f"a escala inverteu: {classe} ({atual}px) é MAIOR que o degrau "
                f"acima dele ({anterior}px)"
            )
        anterior = atual

    for classe in ordem_decrescente + fora_da_cadeia:
        tamanho = _tamanho_do_degrau(classe)
        assert tamanho >= piso_px, (
            f"{classe} está em {tamanho}px, abaixo do piso de {piso_px}px. "
            f"Foi assim que o selo do microfone chegou a 9px e a mantenedora "
            f"parou de conseguir ler o estado do controle (LEGIBILIDADE-01)."
        )


def test_subpainel_disponivel_para_os_blocos_do_card() -> None:
    """C4: a classe que dá corpo aos blocos de dentro do card de Status."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"^\.hefesto-subpainel[^{]*\{([^}]*)\}", conteúdo, re.MULTILINE)
    assert m is not None, "`.hefesto-subpainel` ausente do theme.css"
    corpo = m.group(1)
    assert _cor_de_fundo_sólida(corpo, conteúdo) == "#21222c", (
        "sub-painel volta ao @app_bg (#21222c): é um recorte AFUNDADO no card"
    )
    assert "border-radius: 10px" in corpo, "sub-painel usa raio 10px (mockup)"
    assert "padding: 8px 12px" in corpo, "sub-painel usa padding 8px 12px (mockup)"
    assert "@border_soft" in corpo, "a borda do sub-painel é @border_soft"


def test_messagedialog_top_level_coberto() -> None:
    """Bloco top-level `messagedialog` com fundo escuro Drácula presente."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"^messagedialog[^{]*\{([^}]*)\}", conteúdo, re.MULTILINE)
    assert m is not None, "Bloco top-level 'messagedialog' ausente no theme.css"
    corpo = m.group(1)
    assert "#282a36" in corpo, "messagedialog deve ter o fundo Drácula #282a36"
    assert "#f8f8f2" in corpo, "messagedialog deve ter o foreground #f8f8f2"


def test_messagedialog_botoes_cobertos() -> None:
    """Os botões do diálogo também precisam de regra própria (não herdam da"""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"messagedialog\s+button\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra 'messagedialog button' ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) is not None, (
        "messagedialog button deve ter fundo sólido escuro"
    )


def test_segmentado_read_only_mantem_o_destaque() -> None:
    """GUI-05/P4: o modo detectado (botão :checked) do segmentado READ-ONLY"""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"\.hefesto-dualsense4unix-window\s+button:checked:disabled\s*\{([^}]*)\}",
        conteúdo,
    )
    assert m is not None, "Regra button:checked:disabled ausente"
    corpo = m.group(1)
    roxo = _tokens_definidos(conteúdo).get("purple", "#bd93f9")
    assert "@purple" in corpo or roxo in corpo, (
        "o destaque do modo detectado deve manter o accent roxo"
    )


def test_theme_css_sem_regra_at_rule_proibida() -> None:
    """GTK3 falha a carga inteira com a at-rule de query proibida."""
    at_rule = "@" + "med" + "ia"
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    css_sem_blocos = re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL)
    assert at_rule not in css_sem_blocos, (
        "at-rule de query quebra o parser CSS do GTK3 (falha a carga inteira)"
    )
