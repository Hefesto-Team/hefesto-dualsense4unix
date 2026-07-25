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


def _tokens_definidos(conteúdo: str) -> dict[str, str]:
    """Mapa `nome -> hex` de todo `@define-color` do arquivo."""
    return {
        nome: cor
        for nome, cor in re.findall(
            r"@define-color\s+(\w+)\s+(#[0-9a-fA-F]{3,8})\s*;", conteúdo
        )
    }


def _cor_de_fundo_sólida(corpo: str, conteúdo: str) -> str | None:
    """Hex do `background-color` de um corpo de regra, resolvendo token.

    As cores da interface passaram a ser declaradas por `@define-color` (para
    cada uma ter UM papel documentado), então a regra escreve `@elevated` em vez
    do hex. O que os testes garantem continua sendo o mesmo: a cor é SÓLIDA —
    `transparent` deixa o tema claro do COSMIC vazar por baixo
    (BUG-GUI-COSMIC-WIDGET-CONTRAST-01). Um token só conta se estiver de fato
    definido; token inexistente no GTK3 vira cor indefinida, não um fallback.
    """
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
    """Containers genéricos devem ser cobertos sem quebrar o card.

    O valor esperado do card MUDOU no redesign 1.1: era `#21222c` e passou a ser
    `@bg` (#282a36). A hierarquia estava INVERTIDA — a janela era #282a36 e o
    card #21222c, ou seja, o card ficava mais ESCURO que o fundo e lia como um
    buraco em vez de uma superfície flutuando. Agora a janela é @app_bg
    (#21222c) e o card @bg (#282a36), como no mockup.

    O que o teste continua garantindo é o mesmo de antes: o card tem cor de
    fundo SÓLIDA própria e não foi engolido pela regra genérica que torna
    containers transparentes (BUG-GUI-COSMIC-WIDGET-CONTRAST-01) — `transparent`
    deixa o tema claro do COSMIC vazar por baixo.
    """
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    # box/frame/grid devem aparecer escopados na window com :not(card)
    assert re.search(
        r"\.hefesto-dualsense4unix-window\s+box:not\(\.hefesto-dualsense4unix-card\)",
        conteúdo,
    ), "Regra de containers (box:not(.card)) ausente"
    # o card NÃO pode ter sido transformado em transparente
    m = re.search(r"\.hefesto-dualsense4unix-card\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra .hefesto-dualsense4unix-card ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) == "#282a36", (
        "Card deve ter background sólido @bg (#282a36) — mais CLARO que a janela "
        "(@app_bg #21222c), senão o card afunda em vez de flutuar"
    )


def test_card_declarado_uma_vez_so() -> None:
    """`.hefesto-dualsense4unix-card` tinha DUAS declarações.

    A segunda (FEAT-GUI-HOME-TAB-01, no fim do arquivo) só queria apertar o
    padding e acabava sobrescrevendo padding e raio da primeira — quem editasse
    a declaração "de verdade" não via efeito nenhum na tela e ia caçar
    especificidade que não era o problema. Uma só.
    """
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
    """Quatro níveis de superfície, do fundo para a frente.

    A queixa de origem era "as cores do background": a tela tinha DOIS tons
    chapados (e trocados entre si). O design pede quatro degraus — janela
    @app_bg, cromo @chrome, card @bg, elevado @elevated — e cada um precisa
    existir como token E estar aplicado em algum lugar.
    """
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

    # A janela é o nível MAIS FUNDO (era @bg, o mesmo tom do card).
    m = re.search(r"\.hefesto-dualsense4unix-window\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra .hefesto-dualsense4unix-window ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) == "#21222c", (
        "o fundo da janela é @app_bg (#21222c) — mais fundo que o card"
    )

    # O cromo (barra de título, tira de abas, rodapé) precisa estar aplicado.
    assert "@chrome" in re.sub(r"/\*.*?\*/", "", conteúdo, flags=re.DOTALL), (
        "token @chrome definido mas nunca aplicado — o cromo continua chapado"
    )


def test_log_textview_nao_herda_o_branco_do_sistema() -> None:
    """BUG-GUI-LOG-TEXTVIEW-BRANCO-01.

    A classe `.hefesto-dualsense4unix-log` está no PRÓPRIO GtkTextView (glade),
    então o seletor DESCENDENTE `.hefesto-dualsense4unix-log textview` nunca
    casava: a caixa de log da aba Sistema saía BRANCA no meio do tema escuro.
    Tem de existir a forma `textview.hefesto-dualsense4unix-log` e a do nó
    filho `text`, que é onde o GTK3 pinta o fundo de verdade.
    """
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
    """`.dim-label` é usada em ~20 lugares e não existia no theme.css.

    Sem definição nossa ela caía no `.dim-label { opacity: 0.55 }` do tema do
    sistema: o rótulo virava o foreground branco a 55%, um cinza que não é
    nenhum dos tokens de texto do design (@text_soft/@text_muted/@comment).
    Precisa fixar cor E `opacity: 1` — sem o opacity o tema do sistema continua
    apagando por cima da cor certa.
    """
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
    """C2: os tamanhos de fonte são NOMEADOS e absolutos.

    Antes não havia escala nenhuma — quatro tamanhos RELATIVOS de Pango
    (`size="small"`, `xx-large`, `92%`) espalhados pelo código, cada um
    dependendo da fonte que a distribuição tivesse configurado. Os px são os do
    mockup (`novo-layout/Telas Hefesto.dc.html`).
    """
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    esperado = {
        ".hefesto-titulo": "21px",
        ".hefesto-titulo-painel": "15px",
        ".hefesto-titulo-secao": "14px",
        ".hefesto-corpo": "13px",
        ".hefesto-rotulo": "12px",
        ".hefesto-rotulo-secao": "12px",
        ".hefesto-rotulo-longo": "11.5px",
        ".hefesto-subtitulo": "11px",
        ".hefesto-dica": "11px",
        ".hefesto-micro": "10px",
        ".hefesto-selo": "9px",
        ".hefesto-valor-mono": "12px",
        ".hefesto-valor-mono-peq": "11px",
    }
    for classe, tamanho in esperado.items():
        m = re.search(
            r"^" + re.escape(classe) + r"\s*\{([^}]*)\}", conteúdo, re.MULTILINE
        )
        assert m is not None, f"degrau {classe} ausente da escala tipográfica"
        assert f"font-size: {tamanho}" in m.group(1), (
            f"{classe} deveria ser {tamanho}; corpo: {m.group(1).strip()!r}"
        )


def test_subpainel_disponivel_para_os_blocos_do_card() -> None:
    """C4: a classe que dá corpo aos blocos de dentro do card de Status.

    Contrato com quem monta os widgets (giroscópio, microfone, touchpad,
    lightbar, alto-falante, analógicos, painel de botões): `.hefesto-subpainel`
    = borda @border_soft + raio 10px + fundo @app_bg + padding 8px 12px.
    Renomear aqui quebra a GUI em silêncio — o CSS não erra, só não pinta.
    """
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


# ---------------------------------------------------------------------------
# GUI-05/P5: diálogos temados no top-level (padrão dos menus) — o nó
# `messagedialog` é toplevel próprio e não herda o escopo da window; sem o
# bloco, um diálogo futuro sem a classe herdaria o Adwaita claro do XWayland.
# ---------------------------------------------------------------------------


def test_messagedialog_top_level_coberto() -> None:
    """Bloco top-level `messagedialog` com fundo escuro Drácula presente."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"^messagedialog[^{]*\{([^}]*)\}", conteúdo, re.MULTILINE)
    assert m is not None, "Bloco top-level 'messagedialog' ausente no theme.css"
    corpo = m.group(1)
    assert "#282a36" in corpo, "messagedialog deve ter o fundo Drácula #282a36"
    assert "#f8f8f2" in corpo, "messagedialog deve ter o foreground #f8f8f2"


def test_messagedialog_botoes_cobertos() -> None:
    """Os botões do diálogo também precisam de regra própria (não herdam da
    window) — sem ela, 'Cancelar/Aplicar' vinham no claro do sistema."""
    conteúdo = CSS_PATH.read_text(encoding="utf-8")
    m = re.search(r"messagedialog\s+button\s*\{([^}]*)\}", conteúdo)
    assert m is not None, "Regra 'messagedialog button' ausente"
    assert _cor_de_fundo_sólida(m.group(1), conteúdo) is not None, (
        "messagedialog button deve ter fundo sólido escuro"
    )


def test_segmentado_read_only_mantem_o_destaque() -> None:
    """GUI-05/P4: o modo detectado (botão :checked) do segmentado READ-ONLY
    (ficha do externo, insensitive) continua destacado — sem a regra
    :checked:disabled, o :disabled apagava o roxo e nada parecia marcado."""
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
