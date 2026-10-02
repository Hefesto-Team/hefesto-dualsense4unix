"""O card NÃO oferece a ponte de mic por BT — lido da árvore de widgets real."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o bloco do microfone, no card")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard

MAC = "aa:bb:cc:00:11:22"


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_vivos: list[Any] = []


def _assentar(vezes: int = 6) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _entry(transporte: str) -> dict[str, Any]:
    return {
        "index": 0,
        "connected": True,
        "transport": transporte,
        "uniq": MAC,
        "battery_pct": 80,
        "audio": {"mic_mudo": False},
    }


def _card(transporte: str = "bt", *, compacto: bool = False) -> ControllerCard:
    card = ControllerCard(compact=compacto)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(900, 600)
    janela.show_all()
    _vivos.append(janela)
    card.update(_entry(transporte), {}, None)
    _assentar()
    return card


def _descendentes(raiz: Any) -> list[Any]:
    """Todo widget abaixo de ``raiz``, ela inclusive."""
    achados = [raiz]
    if isinstance(raiz, Gtk.Container):
        for filho in raiz.get_children():
            achados.extend(_descendentes(filho))
    return achados


@pytest.mark.parametrize("transporte", ["bt", "usb"])
@pytest.mark.parametrize("compacto", [False, True])
def test_o_bloco_do_microfone_nao_tem_interruptor(
    transporte: str, compacto: bool
) -> None:
    """A MORDIDA: devolva o `Gtk.Switch` ao `_montar_mic` e isto reprova."""
    card = _card(transporte, compacto=compacto)

    interruptores = [
        peca for peca in _descendentes(card._mic_box) if isinstance(peca, Gtk.Switch)
    ]

    assert interruptores == [], (
        "voltou um interruptor ao bloco do microfone. Enquanto a posse do "
        "hidraw e a sequência do report 0x32 tiverem dois donos, a ponte não "
        "tem lugar na janela — leia o estudo 2026-08-16-O-PS-PRESO antes de "
        "religar isto"
    )


@pytest.mark.parametrize("compacto", [False, True])
def test_nenhuma_peca_do_card_diz_pelo_radio(compacto: bool) -> None:
    """O rótulo era o convite ao gesto — e, para ela, protocolo vazando na tela."""
    card = _card(compacto=compacto)

    rotulos = [
        peca.get_text()
        for peca in _descendentes(card)
        if isinstance(peca, Gtk.Label) and "rádio" in (peca.get_text() or "").lower()
    ]

    assert rotulos == [], f"a tela voltou a falar de transporte no som: {rotulos}"


def test_a_linha_do_microfone_tem_o_controle_e_o_botao_nessa_ordem() -> None:
    """*"Ali onde temos o botão por rádio trocamos por Silenciar"* — na ordem."""
    card = _card()

    linha = card._mic_escala.get_parent()
    filhos = linha.get_children()

    assert filhos == [card._mic_escala, card._mic_botao], (
        "a linha do microfone deixou de ser (controle deslizante, botão): "
        f"{filhos}"
    )


def test_o_controle_deslizante_ficou_com_o_trilho_que_sobrou() -> None:
    """A largura devolvida pelo interruptor tinha de ir para o trilho."""
    card = _card()

    assert card._mic_escala.get_hexpand() is True, (
        "o controle deslizante parou de crescer: quem ganha o espaço livre da "
        "linha tem de ser ele, não o botão"
    )
    largura = card._mic_escala.get_allocation().width
    assert largura >= 80, (
        f"o controle deslizante ficou com {largura}px de trilho — é a bolinha "
        "sem trilho de novo"
    )


def test_o_botao_de_silenciar_continua_de_pe_no_mesmo_bloco() -> None:
    """Tirar o interruptor não pode ter levado o mudo junto."""
    card = _card()

    assert card._mic_botao in _descendentes(card._mic_box)
    assert card._mic_botao.get_visible() is True
    assert card._mic_botao.get_sensitive() is True
