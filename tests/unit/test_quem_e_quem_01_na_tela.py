"""QUEM-É-QUEM-01 na TELA — a FIAÇÃO, com GTK real.

O irmão `test_quem_alimenta_quem_01.py` trava a peça (`dica_do_titulo`, função
pura). Este trava a fiação: que o card de verdade PENDURA a dica no rótulo do
título quando o `state_full` traz a lista.

O arquivo existe separado por um motivo só, e ele é mecânico: `exigir_gi_real`
pula o MÓDULO inteiro no CI headless, e as checagens do daemon do irmão não
podem ir junto para o ralo.

**Por que a fiação merece teste próprio.** O precedente desta casa é o rumble:
um teste que chamava a peça e não a fiação passou com a cura arrancada. Aqui a
forma do defeito seria a mesma — a função pura devolvendo a frase certa e o
`set_tooltip_text` nunca chamado, com a tela calada e a suíte verde.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("dica do título do card")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets.controller_card import (
    DICA_TITULO_SEM_VPAD,
    ControllerCard,
)

#: Faixa forjada da casa, no formato REAL do payload (`norm_mac`, sem
#: separador) — o mesmo de `controllers[].uniq`.
MAC = "aabbcc000002"
#: Faixa localmente administrada que o PRODUTO carimba no vpad uhid
#: (`uhid_gamepad.player_mac`): forjada por construção, não é hardware.
VPAD = "02:fe:00:00:00:02"

_janelas_vivas: list[Any] = []


def _entry() -> dict[str, Any]:
    return {
        "index": 1,
        "connected": True,
        "transport": "usb",
        "is_primary": False,
        "uniq": MAC,
        "battery_pct": 80,
        "player": 2,
        "player_slot": 2,
        "lightbar_rgb": [255, 121, 198],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": None,
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }


def _estado(**troca: Any) -> dict[str, Any]:
    jogador: dict[str, Any] = {
        "player": 2,
        "uniq": MAC,
        "is_primary": False,
        "vpad_backend": "uhid",
        "vpad_uniq": VPAD,
        "vpad_nome": "DualSense Wireless Controller (Hefesto P2)",
        "vpad_indice": 2,
        "aguardando_grab": False,
        "nome_divergente": False,
    }
    jogador.update(troca)
    return {"native_mode": False, "coop": {"players": 2, "mesa": [jogador]}}


def _card_montado() -> Any:
    card = ControllerCard(compact=True)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    # Sob Xvfb não há gerenciador de janelas — a `OffscreenWindow` é o que se
    # auto-aloca (armadilha nº 2 da casa). E a referência tem de sobreviver ao
    # fim da função, senão o GC leva o card junto.
    _janelas_vivas.append(janela)
    return card


def test_o_rotulo_do_titulo_ganha_a_dica_com_o_endereco_do_vpad() -> None:
    """A MORDIDA da fiação: sem o `set_tooltip_text` no `_update_titulo`, a
    frase existe na função pura e a tela continua sem dizer qual vpad é qual.
    """
    card = _card_montado()

    card.update(_entry(), _estado())

    dica = card._title_label.get_tooltip_text()
    assert dica is not None, "a dica tem de estar PENDURADA, não só calculada"
    assert "Jogador 2" in dica
    assert VPAD in dica


def test_a_dica_some_quando_o_controle_deixa_a_mesa_de_jogadores() -> None:
    """Diff próprio: a dica muda por motivo diferente do título (o título deste
    card não muda entre as duas chamadas). Pendurada no diff do TÍTULO, ela
    ficaria congelada na frase da chamada anterior."""
    card = _card_montado()

    card.update(_entry(), _estado())
    assert card._title_label.get_tooltip_text() is not None

    card.update(_entry(), {"native_mode": False, "coop": {"players": 1}})
    assert card._title_label.get_tooltip_text() is None


def test_aguardando_grab_chega_a_tela_com_a_frase_propria() -> None:
    """O físico já está na mesa e o vpad ainda não nasceu — e a tela diz isso,
    em vez de calar como se não soubesse."""
    card = _card_montado()

    card.update(
        _entry(),
        _estado(vpad_backend=None, vpad_uniq=None, aguardando_grab=True),
    )

    assert card._title_label.get_tooltip_text() == DICA_TITULO_SEM_VPAD
