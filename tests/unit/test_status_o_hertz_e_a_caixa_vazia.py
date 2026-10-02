"""STATUS-DIZ-O-QUE-VÊ-01/T1 e T2 — a caixa vazia de 910px e o hertz que sumiu."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status: o hertz e a caixa vazia")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard
from tests.unit.test_status_faixa_blocos import _ENTRY

LARGURA_DA_TELA_DELA = 1870

TETO_DO_VAO_MORTO = 4

#: grandeza real do IMU do DualSense, e é o número que a sprint cita.
HZ_DA_FIXTURE = 194.0

#: única configuração em que `texto_motion` tem hertz para dizer.
_ESTADO_COM_GIRO: dict[str, Any] = {
    "native_mode": False,
    "rumble_ff": {
        "per_vpad": [
            {"player": 1, "motion_streaming": True, "motion_hz": HZ_DA_FIXTURE}
        ]
    },
}

_ESTADO_SEM_GIRO: dict[str, Any] = {"native_mode": False, "rumble_ff": {"per_vpad": []}}

_janelas_vivas: list[Any] = []


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


def _card_como_a_aba_monta(estado: dict[str, Any]) -> Any:
    """O card do jeito que `status_actions._sync_status_cards` o constrói."""
    card = ControllerCard(compact=False, mostrar_estado_global=True)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, estado, LeituraMic(nivel=0.6, muted=False))
    janela.resize(LARGURA_DA_TELA_DELA, 900)
    for _ in range(2):
        while Gtk.events_pending():
            Gtk.main_iteration()
    return card


def _sem_conteudo(widget: Any) -> bool:
    """True quando o widget não tem NADA dentro para mostrar."""
    if isinstance(widget, Gtk.Label):
        return not widget.get_text().strip()
    if isinstance(widget, Gtk.Container):
        return not [f for f in widget.get_children() if f.get_visible()]
    return False


def _textos_da_arvore(widget: Any) -> list[str]:
    """Todo `get_text()` VISÍVEL da árvore, de cima para baixo."""
    achados: list[str] = []
    if not widget.get_visible():
        return achados
    ler = getattr(widget, "get_text", None)
    if callable(ler):
        try:
            texto = ler()
        except TypeError:  # pragma: no cover — `get_text` de outra assinatura
            texto = None
        if isinstance(texto, str) and texto.strip():
            achados.append(texto)
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            achados.extend(_textos_da_arvore(filho))
    return achados


def test_status_faixa_gyro_bateria() -> None:
    """Nenhum widget sem conteúdo paga largura na faixa da bateria."""
    card = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)
    faixa = card._faixa_gyro_bateria
    largura_da_faixa = faixa.get_allocation().width

    assert largura_da_faixa > 100, (
        "a faixa não foi alocada de verdade (mediu "
        f"{largura_da_faixa}px): widget sem alocação devolve 1x1 e a asserção "
        "abaixo passaria com qualquer desenho"
    )

    vaos_mortos = {
        type(filho).__name__: filho.get_allocation().width
        for filho in faixa.get_children()
        if filho is not card._battery_row
        and filho.get_visible()
        and _sem_conteudo(filho)
    }
    caros = {nome: px for nome, px in vaos_mortos.items() if px > TETO_DO_VAO_MORTO}

    assert not caros, (
        f"a faixa da bateria (largura {largura_da_faixa}px) paga largura a "
        f"widget SEM NENHUM CONTEÚDO: {caros}. O teto é "
        f"{TETO_DO_VAO_MORTO}px — o que expande tem de ter o que mostrar"
    )


def test_a_bateria_fica_ancorada_na_direita_com_a_linha_calada() -> None:
    """A bateria não salta quando o giroscópio se cala."""
    com = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    sem = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)

    def direita_da_bateria(card: Any) -> int:
        alloc = card._battery_row.get_allocation()
        return alloc.x + alloc.width

    assert direita_da_bateria(com) == direita_da_bateria(sem), (
        "a bateria mudou de lugar entre o giroscópio fluindo "
        f"(direita em x={direita_da_bateria(com)}) e o giroscópio calado "
        f"(x={direita_da_bateria(sem)}): ela tem de ficar ancorada na direita "
        "nos dois estados"
    )


def test_o_hertz_chega_a_tela() -> None:
    """O número do giroscópio aparece no card que a aba monta."""
    card = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    textos = _textos_da_arvore(card)
    com_hz = [t for t in textos if "Hz" in t]

    assert com_hz, (
        "o hertz do giroscópio não chega à tela do card único: nenhum dos "
        f"{len(textos)} textos visíveis contém 'Hz'. Árvore: {textos}"
    )
    assert any(str(int(HZ_DA_FIXTURE)) in t for t in com_hz), (
        f"a tela diz 'Hz' mas não o número alimentado ({int(HZ_DA_FIXTURE)}): "
        f"{com_hz}"
    )


def test_o_hertz_se_cala_quando_o_giroscopio_nao_flui() -> None:
    """Sem espelho de motion, a linha some — não inventa número nenhum."""
    card = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)
    com_hz = [t for t in _textos_da_arvore(card) if "Hz" in t]

    assert not com_hz, (
        "o card afirma hertz com o espelho de motion DESLIGADO no vpad: "
        f"{com_hz}"
    )


#: sobreviveram oito dias porque nada as media.  (noqa-acento: verbo medir, imperfeito)
_PROMESSAS_CADUCAS: tuple[str, ...] = (
    "o giroscópio é dito pela linha da verdade",
    "quem a empacota é o bloco do motion",
    "o lugar dela é a faixa da linha 2",
)


def test_nenhum_comentario_promete_a_linha_da_verdade_na_tela() -> None:
    """T3 — a régua que faltava em 17/08: o comentário casa com a árvore."""
    import inspect
    import re

    from hefesto_dualsense4unix.app.widgets import controller_card as modulo

    achatado: list[str] = []
    linha_do_caractere: list[int] = []
    for numero, linha in enumerate(inspect.getsource(modulo).splitlines(), start=1):
        pedaco = re.sub(r"\s+", " ", linha.lstrip().lstrip("#").strip())
        if not pedaco:
            continue
        if achatado:
            achatado.append(" ")
            linha_do_caractere.append(numero)
        achatado.append(pedaco)
        linha_do_caractere.extend([numero] * len(pedaco))
    texto_achatado = "".join(achatado)

    achados = []
    for frase in _PROMESSAS_CADUCAS:
        onde = texto_achatado.find(frase)
        if onde >= 0:
            achados.append(
                f"{modulo.__name__}:{linha_do_caractere[onde]}: {frase!r}"
            )
    assert not achados, (
        "o código volta a afirmar que a linha da VERDADE diz o giroscópio na "
        "tela do card único — falso desde 17/08/2026 (SEM-BARRA-DA-VERDADE-01 "
        f"a desempacotou a pedido dela): {achados}"
    )

    card = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    assert card._verdade_label is not None, (
        "o `_verdade_label` sumiu do card único: ele é decisão medida de "
        "01/08 guardada de propósito (o caminho de volta), e apagá-lo pede "
        "sprint própria — não é efeito colateral de T1/T2"
    )
    assert card._verdade_label.get_parent() is None, (
        "o `_verdade_label` voltou à tela e os comentários deste módulo ainda "
        "dizem que ele está fora dela. Se a volta é intencional, reescreva os "
        "comentários do `_montar_ui`, do `_montar_estado_global` e do "
        "`_update_motion` — foi o que ninguém fez em 17/08"
    )
