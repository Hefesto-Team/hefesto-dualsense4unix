"""utils/color_contrast.py — fundação de contraste mínimo para tinting (STATUS-03).

A aba Status pinta os traços dos widgets ao vivo (StickPreview, glyphs, barras
L2/R2) com a cor do lightbar de cada controle. Cores de lightbar são livres —
a cor real medida ao vivo na máquina de referência é ``(16, 32, 72)``, com
contraste WCAG 1.12:1 contra o fundo Drácula ``#282a36``: invisível crua.
Este módulo garante o mínimo legível SEM trair a identidade da cor: sobe a
LUMINOSIDADE em HLS preservando o matiz (decisão D8 do sprint de cores:
o swatch do card mostra a cor CRUA; só os traços recebem a cor AJUSTADA).

Pior caso de fundo (constante ``PIOR_FUNDO``)
---------------------------------------------

Os traços tintados assentam em dois fundos reais distintos:

* ``#282a36`` — o ``StickPreviewGtk`` pinta o próprio fundo no cairo
  (``FUNDO_STICK_PREVIEW``);
* o fundo do tema GTK escuro forçado — o app pede
  ``gtk-application-prefer-dark-theme`` e sobrepõe o CSS Drácula com
  prioridade APPLICATION, mas nós internos não cobertos pelo nosso CSS
  (ex.: trough de ``GtkProgressBar``) resolvem contra o tema do sistema.
  Medido ao vivo (2026-07-17, adw-gtk3-dark recolorido pelo COSMIC):
  ``theme_bg_color = #313250``. Como esse valor varia por máquina/accent,
  adotamos o ENVELOPE ``#353535`` (bg canônico do Adwaita-dark, GTK3), que
  domina em luminância todos os fundos escuros reais observados:
  ``#282a36`` (0.0237) < ``#303030`` stock (0.0295) < ``#313250`` medido
  (0.0351) <= ``#353535`` (0.0356). Garantir 3.0:1 contra o envelope garante
  >= 3.0:1 contra todos eles (``FUNDO_TEMA_GTK_ESCURO``).

Pressuposto documentado (edge case aceito no STATUS-03): a garantia vale com
o tema Drácula do app carregado (ou qualquer tema ESCURO <= envelope). Se o
``theme.css`` falhar na carga o app loga e segue — e se além disso o
``prefer-dark-theme`` não pegar, os widgets caem no tema claro do sistema e
a régua contra fundo escuro deixa de valer.

Accent neutro
-------------

``ACCENT_NEUTRO`` (``#6272a4``, o "comment" da paleta Drácula) é o accent dos
rótulos "Lightbar: apagada" (rgb 0,0,0 escrito por nós) e "cor desconhecida"
(``lightbar_source == "desconhecida"``) — contrato do card por controle
(STATUS-02/03; a integração é da frente dos cards). Cru ele rende ~2.6:1
contra o envelope: para TRAÇOS, passe-o por ``ensure_min_contrast`` como
qualquer accent (idempotente para cores já legíveis, clareia o resto).
"""
from __future__ import annotations

import colorsys
from collections.abc import Sequence
from typing import Any, Final

RGB = tuple[int, int, int]

#: Razão de contraste WCAG mínima para elementos gráficos (WCAG 1.4.11).
RATIO_MINIMO: Final[float] = 3.0

#: Fundo que o StickPreviewGtk pinta no próprio cairo (#282a36, Drácula).
FUNDO_STICK_PREVIEW: Final[RGB] = (0x28, 0x2A, 0x36)

#: Envelope do fundo do tema GTK escuro (#353535, Adwaita-dark canônico) —
#: domina em luminância o theme_bg_color medido ao vivo (#313250) e o
#: adw-gtk3-dark stock (#303030). Ver docstring do módulo.
FUNDO_TEMA_GTK_ESCURO: Final[RGB] = (0x35, 0x35, 0x35)

#: Accent neutro Drácula (#6272a4) dos rótulos "apagada"/"desconhecida".
ACCENT_NEUTRO: Final[RGB] = (0x62, 0x72, 0xA4)

#: Cor do trough normalizado pelo helper de barras (#21222c — card Drácula,
#: mais escuro que o pior fundo: o preenchimento tintado ganha contraste).
TROUGH_HEX: Final[str] = "#21222c"


def _valida_rgb(rgb: Sequence[int]) -> RGB:
    """Normaliza uma cor 8-bit (aceita tuple/list do IPC), com clamp 0-255."""
    if len(rgb) != 3:
        raise ValueError(f"cor RGB precisa de 3 canais, veio {len(rgb)}: {rgb!r}")
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return (r, g, b)


def _linearizar(canal: float) -> float:
    """Lineariza um canal sRGB em [0,1] (fórmula WCAG 2.x)."""
    if canal <= 0.03928:
        return canal / 12.92
    return float(((canal + 0.055) / 1.055) ** 2.4)


def luminancia_relativa(rgb: Sequence[int]) -> float:
    """Luminância relativa WCAG de uma cor 8-bit (0.0 = preto, 1.0 = branco)."""
    r, g, b = _valida_rgb(rgb)
    return (
        0.2126 * _linearizar(r / 255)
        + 0.7152 * _linearizar(g / 255)
        + 0.0722 * _linearizar(b / 255)
    )


def razao_contraste(cor_a: Sequence[int], cor_b: Sequence[int]) -> float:
    """Razão de contraste WCAG entre duas cores 8-bit (1.0 a 21.0)."""
    la = luminancia_relativa(cor_a)
    lb = luminancia_relativa(cor_b)
    claro, escuro = (la, lb) if la >= lb else (lb, la)
    return (claro + 0.05) / (escuro + 0.05)


#: O MAIS DESFAVORÁVEL dos fundos reais: o de maior luminância exige mais
#: claridade do traço. Hoje é o envelope do tema (#353535 > #282a36).
PIOR_FUNDO: Final[RGB] = max(
    (FUNDO_STICK_PREVIEW, FUNDO_TEMA_GTK_ESCURO),
    key=luminancia_relativa,
)


def _hls_para_rgb8(h: float, luz: float, s: float) -> RGB:
    """Converte HLS (frações 0-1) para RGB 8-bit arredondado."""
    r, g, b = colorsys.hls_to_rgb(h, luz, s)
    return (round(r * 255), round(g * 255), round(b * 255))


def ensure_min_contrast(
    rgb: Sequence[int],
    ratio: float = RATIO_MINIMO,
    *,
    fundo: Sequence[int] | None = None,
) -> RGB:
    """Clareia ``rgb`` até o contraste WCAG contra o pior fundo ser >= ``ratio``.

    Contrato (STATUS-03, item 8 do desenho):

    * sobe SÓ a luminosidade em HLS, preservando matiz (Δmatiz <= 4° para
      cores cromáticas — o desvio residual vem só do arredondamento 8-bit)
      e saturação;
    * cores JÁ legíveis passam intactas (idempotência: ``f(f(x)) == f(x)``);
    * preto/cinza-escuro (acromáticas, saturação 0) clareiam para um cinza
      neutro legível — nunca ganham matiz inventado;
    * a claridade final é a MÍNIMA que atinge ``ratio`` (busca binária sobre
      a luminosidade + ajuste fino pós-arredondamento);
    * best-effort: se ``ratio`` for inatingível mesmo no branco (> ~12.3
      contra o envelope escuro), devolve o mais claro possível do matiz.

    ``fundo`` (keyword-only) troca a referência — o default é ``PIOR_FUNDO``,
    o mais desfavorável dos fundos reais dos traços (ver módulo).

    Aceita tuple ou list (o IPC entrega ``[r, g, b]``); devolve sempre tuple.
    """
    alvo: RGB = PIOR_FUNDO if fundo is None else _valida_rgb(fundo)
    cor = _valida_rgb(rgb)
    if razao_contraste(cor, alvo) >= ratio:
        return cor

    h, luz, s = colorsys.rgb_to_hls(cor[0] / 255, cor[1] / 255, cor[2] / 255)
    # Cada canal RGB é não-decrescente na luminosidade HLS (h, s fixos), logo
    # a luminância WCAG também é — a busca binária encontra a menor luz viável.
    lo, hi = luz, 1.0
    for _ in range(32):
        meio = (lo + hi) / 2
        if razao_contraste(_hls_para_rgb8(h, meio, s), alvo) >= ratio:
            hi = meio
        else:
            lo = meio
    candidata = _hls_para_rgb8(h, hi, s)
    # Ajuste fino: o arredondamento 8-bit pode deixar a candidata um fio
    # abaixo do ratio; empurra a luminosidade em passos de 1/255.
    while razao_contraste(candidata, alvo) < ratio and hi < 1.0:
        hi = min(1.0, hi + 1 / 255)
        candidata = _hls_para_rgb8(h, hi, s)
    return candidata


def rgb_para_hex(rgb: Sequence[int]) -> str:
    """Formata uma cor 8-bit como ``#rrggbb`` (minúsculo)."""
    r, g, b = _valida_rgb(rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def tintar_progressbar(
    barra: Any,
    rgb: Sequence[int],
    ratio: float = RATIO_MINIMO,
) -> str:
    """Tinta o preenchimento de uma ``Gtk.ProgressBar`` com a cor ajustada.

    Helper reutilizável para as barras L2/R2 do card por controle (a
    integração é da frente STATUS-02; aqui só o mecanismo):

    * a cor é ajustada por :func:`ensure_min_contrast` (traços recebem a cor
      AJUSTADA; o swatch do card mostra a crua — decisão D8);
    * ``Gtk.CssProvider`` POR WIDGET (não por screen), cobrindo os nós
      internos ``trough``/``progress`` — validado ao vivo por render
      offscreen; o trough é normalizado para ``TROUGH_HEX`` (mais escuro que
      o pior fundo) para a garantia de contraste valer dentro da barra;
    * atualizado SÓ quando a cor efetiva muda: chamar de novo com a mesma
      cor (mesmo hex ajustado) é no-op — seguro no tick de 10 Hz;
    * devolve o hex efetivamente aplicado (ex.: para testes/diagnóstico).

    O import do GTK é tardio: este módulo continua importável em ambiente
    sem display (daemon/CLI/testes puros).
    """
    hex_cor = rgb_para_hex(ensure_min_contrast(rgb, ratio))
    if getattr(barra, "_hefesto_tint_hex", None) == hex_cor:
        return hex_cor

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    css = (
        f"progressbar trough {{ background-color: {TROUGH_HEX};"
        f" background-image: none; }}\n"
        f"progressbar trough progress {{ background-color: {hex_cor};"
        f" background-image: none; }}\n"
    )
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    contexto = barra.get_style_context()
    anterior = getattr(barra, "_hefesto_tint_provider", None)
    if anterior is not None:
        contexto.remove_provider(anterior)
    contexto.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    barra._hefesto_tint_provider = provider
    barra._hefesto_tint_hex = hex_cor
    return hex_cor
